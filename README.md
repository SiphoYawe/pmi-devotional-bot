# Phaneroo Daily Devotional → Telegram Bot

Automatically detects the new [Phaneroo](https://phaneroo.org/) daily devotional each
morning and sends its image + full English text + source link to a private Telegram chat.
Runs on free GitHub Actions — no server required.

## How it works

A scheduled workflow runs every 30 minutes across the morning window (00:00–09:00 EAT).
It reads the latest devotional slug from `https://phaneroo.org/daily-devotion/` — fetched
with a **cache-busting query param** because that page is served from a WordPress cache
that can be a day stale (homepage used as fallback) — compares it to `state.json`, and,
only when a genuinely new one appears, fetches the devotional (title + featured image +
date via the WordPress oEmbed API; English body scraped from the page) and sends it to
Telegram. The devotional's date (parsed from the oEmbed image filename) guards against
ever sending an older-dated entry. The new slug + date are committed back to `state.json`
so later runs no-op.

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

`cron: "*/30 0-6,21-23 * * *"` (UTC) = every 30 min, 00:00–09:59 EAT. Adjust in
`.github/workflows/devotional.yml`. GitHub cron is best-effort and may be delayed a few
minutes under load.

## Notes

- State lives in `state.json`, committed by the workflow with `[skip ci]`.
- The parser targets the page's first language tab (English). If Phaneroo changes the page
  markup, `tests/test_parser.py` (run against `tests/fixtures/`) will catch it — refresh
  the fixtures and adjust selectors.
