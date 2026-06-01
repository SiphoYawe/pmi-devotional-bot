"""Entry point: discover -> compare -> parse -> send -> persist."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from phaneroo_bot import discover, parser, telegram, state


def run(*, state_path: Path = state.DEFAULT_PATH, token: str, chat_id: str) -> str:
    last_slug = state.load_last_slug(state_path)
    slug, url = discover.discover()

    if last_slug is None:
        # First run: record the current top so we never send yesterday's.
        state.save_last_slug(state_path, slug)
        print(f"bootstrapped: recorded '{slug}' without sending")
        return "bootstrapped"

    if slug == last_slug:
        print(f"noop: '{slug}' already sent")
        return "noop"

    dev = parser.parse_devotional(slug, url)
    telegram.send_devotional(dev, token=token, chat_id=chat_id)
    state.save_last_slug(state_path, slug)  # only after a successful send
    print(f"sent: '{slug}'")
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
