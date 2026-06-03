# Phaneroo Daily Devotional → Telegram Bot

Automatically detects the new [Phaneroo](https://phaneroo.org/) daily devotional and sends
its full English text to a private Telegram chat at earliest publishing, then follows up
with the devotional's artwork once it's been designed and uploaded. Runs on free GitHub
Actions — no server required.

## How it works

A scheduled workflow runs every 30 minutes from publish through the afternoon (00:00–18:00
EAT). It reads the latest devotional slug from `https://phaneroo.org/daily-devotion/` —
fetched with a **cache-busting query param** because that page is served from a WordPress
cache that can be a day stale (homepage used as fallback) — compares it to `state.json`,
and parses the devotional (title + featured image + date via the WordPress oEmbed API;
English body scraped from the page).

Delivery is **two-phase**, because Phaneroo first publishes a devotional with a generic
placeholder image and only later swaps in artwork named with the publish date (e.g.
`03-June-2026_Web.png`):

1. **Text first.** When a new slug appears, the full devotional **text** is sent right away
   — no placeholder image, no source link.
2. **Artwork when ready.** Each subsequent run re-checks the image. A parseable date in the
   filename means the real artwork is up, so the bot sends that image (captioned with the
   devotional name) and is then done for the day.

A devotional's date (parsed from the image filename) still guards against ever sending an
older-dated entry. State (`last_slug`, `last_date`, `artwork_sent`) is committed back to
`state.json` so later runs no-op.

## Setup

1. **Create the bot:** message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the
   token.
2. **Find your chat ID:** send any message to your new bot, then run:
   ```bash
   TELEGRAM_BOT_TOKEN=<token> python scripts/get_chat_id.py
   ```
   Copy the `chat_id`.
3. **Add GitHub secrets** (repo → Settings → Secrets and variables → Actions):
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. **Push to GitHub.** The workflow's first run (or trigger it manually via the Actions tab
   → *Daily Devotional* → *Run workflow*) **bootstraps**: it records the current top
   devotional without sending, so you don't receive yesterday's. The next new devotional
   is the first one delivered.

## Local development

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your token + chat id
pytest                 # run the test suite
python -m phaneroo_bot.main   # run once locally
```

## Scheduling

`cron: "*/30 0-15,21-23 * * *"` (UTC) = every 30 min, 00:00–18:59 EAT — wide enough to
catch both the text at publish and the artwork whenever it lands later that day. Adjust in
`.github/workflows/devotional.yml`. GitHub cron is best-effort and may be delayed a few
minutes under load.

## Notes

- State lives in `state.json`, committed by the workflow with `[skip ci]`.
- The parser targets the page's first language tab (English). If Phaneroo changes the page
  markup, `tests/test_parser.py` (run against `tests/fixtures/`) will catch it — refresh
  the fixtures and adjust selectors.
