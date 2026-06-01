"""Entry point: discover -> compare -> parse -> (date guard) -> send -> persist."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from phaneroo_bot import discover, parser, telegram, state


def run(*, state_path: Path = state.DEFAULT_PATH, token: str, chat_id: str) -> str:
    st = state.load_state(state_path)
    last_slug = st.get("last_slug")
    last_date = st.get("last_date")

    slug, url = discover.discover()

    if not last_slug:
        # First run: record the current top (with its date) without sending,
        # so we never deliver yesterday's devotional on initial deploy.
        dev = parser.parse_devotional(slug, url)
        state.save_state(state_path, slug=slug, date_iso=dev.date_iso)
        print(f"bootstrapped: recorded '{slug}' ({dev.date_iso}) without sending")
        return "bootstrapped"

    if slug == last_slug:
        print(f"noop: '{slug}' already sent")
        return "noop"

    dev = parser.parse_devotional(slug, url)

    # Accuracy guard: never send a devotional dated older than the last one sent
    # (protects against a stale/cached response slipping an old entry to the top).
    if dev.date_iso and last_date and dev.date_iso < last_date:
        print(f"skip: '{slug}' dated {dev.date_iso} is older than last sent {last_date}")
        return "noop"

    telegram.send_devotional(dev, token=token, chat_id=chat_id)
    state.save_state(state_path, slug=slug, date_iso=dev.date_iso)
    print(f"sent: '{slug}' ({dev.date_iso})")
    return "sent"


def main() -> int:
    load_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set", file=sys.stderr)
        return 2
    run(token=token, chat_id=chat_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
