# Phaneroo Daily Devotional → Telegram Bot — Design

**Date:** 2026-06-01
**Status:** Approved design, pending implementation plan

## 1. Goal

Each morning, automatically detect the new Phaneroo daily devotional, then deliver it
(featured image + full text + source link) to a single private Telegram chat. Runs
entirely on free GitHub Actions infrastructure with no always-on server.

## 2. Source analysis (confirmed during brainstorming)

Findings from probing `https://phaneroo.org`:

- The `devotion` content is a WordPress **custom post type that is NOT exposed** via the
  REST API (`/wp-json/wp/v2/devotion` → 404), has **no dedicated RSS feed**
  (`/devotion/feed/` is empty), and is **absent from the sitemap**
  (`wp-sitemap.xml` lists post/page/product/sermons/events only). Regular `posts` in the
  REST API are stale (latest is 2022), so they are not a usable source.
- **The reliable source is the listing page** `https://phaneroo.org/daily-devotion/`.
  It renders devotionals **newest-first** as `https://phaneroo.org/devotion/<slug>/`
  links. The **first such link is the most recently published devotional.**
- **No reliable publish timestamp** is exposed on listing or detail pages, so "is this
  today's?" cannot be derived from a date. Detection must be **state-based**: remember
  the last slug sent; act only when a new slug appears at the top.
- The detail page (`/devotion/<slug>/`) contains the full title and body as **Elementor
  HTML**. `og:image` is present for the featured image. The `<title>` tag is
  `"<Title> – Phaneroo"`. The WordPress **oEmbed endpoint**
  (`/wp-json/oembed/1.0/embed?url=<page>`) returns title + thumbnail as a clean JSON
  fallback for metadata.

**Important nuance:** The top entry is the most recent *published* devotional, which may
still be *yesterday's* if today's has not been posted yet. The bot must NOT assume the
top entry is "today's" — it sends only when the top slug **changes** from the recorded
state.

## 3. Stack

- **Language:** Python 3.11+
- **Dependencies:** `requests` (HTTP), `beautifulsoup4` (HTML parsing). Standard library
  for everything else. Telegram via the plain HTTP Bot API (no bot framework).
- **Host:** GitHub Actions scheduled workflow (free tier).
- **Test:** `pytest`, with saved-HTML fixtures and mocked network/Telegram.

## 4. Architecture

Small, independently testable modules under a `phaneroo_bot/` package:

| Module | Responsibility | Depends on |
|---|---|---|
| `fetcher.py` | HTTP GET with timeout, retries, and a real User-Agent. Returns response text/bytes. | `requests` |
| `discover.py` | Parse `/daily-devotion/` → `(latest_slug, latest_url)`. | `fetcher` |
| `parser.py` | Parse a `/devotion/<slug>/` page → `Devotional{title, scripture, paragraphs[], image_url, url}`. | `fetcher` |
| `telegram.py` | `send_photo`, `send_message`, message chunking, HTML formatting/escaping. | `requests` |
| `state.py` | Read/write `state.json` (`{last_slug, last_sent_at}`); detect bootstrap (empty state). | stdlib |
| `main.py` | Orchestrate the run; the workflow entrypoint. | all above |

### Data structure

```python
@dataclass
class Devotional:
    slug: str
    url: str
    title: str
    scripture: str | None     # optional; best-effort extraction
    paragraphs: list[str]      # body, in order
    image_url: str | None      # featured image (og:image), optional
```

## 5. Run flow (`main.py`)

1. Load `state.json` → `last_slug` (may be empty on first run).
2. `discover()` → `latest_slug`, `latest_url` from the listing page.
3. **Bootstrap:** if state is empty, write `latest_slug` to state and **exit without
   sending** (prevents sending yesterday's devotional on first deploy).
4. If `latest_slug == last_slug` → **no-op**, exit 0 (the common case for same-day reruns).
5. Else `parse(latest_url)` → `Devotional`.
6. Send to Telegram:
   - `sendPhoto` with `image_url` and a caption of **title + scripture** (caption limit
     1024 chars; if it would overflow, send title/scripture as the first text message
     instead). If no image, skip straight to text.
   - `sendMessage` for the body: join paragraphs and **split at paragraph boundaries**
     into chunks ≤ ~4000 chars (under Telegram's 4096 limit). `parse_mode=HTML`,
     all dynamic text HTML-escaped.
   - Final `sendMessage` with a "📖 Read on phaneroo.org" link to `url`.
7. **Only after all sends succeed**, write `latest_slug` + timestamp to `state.json`.
   (Failure before this point leaves state unchanged so the next run retries rather than
   skipping a day.)

## 6. State persistence — committed `state.json`

GitHub Actions is stateless between runs, so the workflow persists state by committing it
back to the repo:

- File: `state.json` at repo root, e.g. `{"last_slug": "the-hidden-manna", "last_sent_at": "2026-06-01T05:12:00Z"}`.
- After a successful send, a workflow step commits the change as the
  `github-actions[bot]` identity with `[skip ci]` in the message (so the state commit
  doesn't trigger other CI).
- Workflow needs `permissions: contents: write`.
- A `concurrency` group prevents overlapping runs from racing on the commit. The commit
  step fetches/rebases before pushing to avoid conflicts.

Rejected alternatives: GitHub Actions cache (rare eviction → duplicate/missed send);
date-matching with no state (site exposes no reliable publish timestamp).

## 7. Scheduling

- Phaneroo is Uganda-based (**EAT = UTC+3**) and posts early morning. Chosen window:
  **00:00–09:00 EAT**, polled every 30 minutes.
- In UTC this wraps midnight: cron **`*/30 0-6,21-23 * * *`** (covers 21:00–06:59 UTC ≈
  00:00–09:59 EAT).
- Once the day's devotional is sent, the remaining runs in the window no-op via state.
- GitHub cron is UTC and best-effort (can be delayed several minutes under load) — fine
  for a 30-minute cadence.
- A `workflow_dispatch` trigger is included for manual testing/forcing a run.

## 8. Telegram setup (operational, documented in README)

- Create a bot via `@BotFather` → `TELEGRAM_BOT_TOKEN`.
- Obtain the private chat ID: message the bot once, then read it via `getUpdates`
  (a small helper script `scripts/get_chat_id.py` is provided), or use `@userinfobot`.
  → `TELEGRAM_CHAT_ID`.
- Store both as **GitHub Actions repository secrets**. They are read from env in the
  workflow; never committed.

## 9. Error handling

- `fetcher` retries transient failures (a few attempts, short backoff) and raises on
  persistent failure.
- Any failure in discover/parse/send → log to stdout (visible in the Actions run) and
  exit non-zero **without** updating state; the next 30-minute run retries.
- Parser is defensive: `scripture` and `image_url` are optional and degrade gracefully;
  a missing body is treated as a parse failure (don't send an empty devotional).
- Idempotency: state updates only after a fully successful send, so crashes re-send next
  run rather than silently skipping.

## 10. Risks

- **Parser fragility (primary risk):** the detail page is Elementor-generated HTML.
  Mitigation: prefer structured metadata first — JSON-LD `headline`/`articleBody` and
  `og:` tags and the oEmbed endpoint where present — and fall back to extracting text
  widgets from the main content container, explicitly excluding nav/footer/comments/
  share/related-posts blocks. Lock behavior with saved-HTML fixtures so future site
  changes surface as failing tests.
- **Listing structure change:** `discover` depends on `/daily-devotion/` markup. Covered
  by a fixture test; failure is loud (no-op + non-zero exit), not a wrong send.

## 11. Testing strategy (TDD)

Fixtures: real saved HTML of `/daily-devotion/` and one `/devotion/<slug>/` page in
`tests/fixtures/`.

- `test_discover.py` — latest slug/url extracted from the listing fixture; handles
  relative vs absolute URLs.
- `test_parser.py` — title (suffix stripped), scripture (when present), ordered
  paragraphs, image URL; graceful handling when scripture/image absent.
- `test_state.py` — read/write round-trip; bootstrap on empty/missing file.
- `test_telegram.py` — chunking is a pure function (boundaries, ≤4096, paragraph splits,
  HTML escaping); send paths with `requests` mocked.
- `test_main.py` — with `fetcher` + `telegram` mocked: sends once on a new slug, no-ops
  on an unchanged slug, bootstraps (no send) on empty state, and does **not** update
  state when a send fails.

## 12. Project layout

```
phaneroo_bot/
  __init__.py
  fetcher.py
  discover.py
  parser.py
  telegram.py
  state.py
  main.py
scripts/
  get_chat_id.py
tests/
  fixtures/
    daily_devotion.html
    devotion_sample.html
  test_discover.py
  test_parser.py
  test_state.py
  test_telegram.py
  test_main.py
.github/workflows/devotional.yml
state.json            # committed, updated by the workflow
requirements.txt
README.md
```

## 13. Out of scope (YAGNI)

- Multiple recipients, channels, or groups (private chat only for now).
- A subscription/database backend.
- Web dashboard or admin UI.
- Translating/summarizing/reformatting devotional content beyond clean delivery.
