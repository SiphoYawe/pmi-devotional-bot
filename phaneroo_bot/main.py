"""Entry point: discover -> compare -> parse -> (date guard) -> send -> persist.

Delivery is two-phase. Phaneroo publishes a devotional with a generic placeholder
image first, then later swaps in artwork named with the publish date (e.g.
"03-June-2026_Web.png"). So a parseable date in the image filename is exactly the
signal that the real artwork is up (dev.date_iso is not None).

  - New slug         -> send the text only (no placeholder image, no link). If the
                        artwork is already up, send it too and we're done.
  - Same slug, art   -> still on the placeholder: re-check each run and send the
    pending             artwork the moment it lands, then we're done for the day.
  - Same slug, done  -> noop until tomorrow's devotional appears.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from phaneroo_bot import discover, parser, telegram, state


def run(*, state_path: Path = state.DEFAULT_PATH, token: str, chat_id: str) -> str:
    st = state.load_state(state_path)
    last_slug = st.get("last_slug")
    last_date = st.get("last_date")
    artwork_sent = st.get("artwork_sent")
    if artwork_sent is None:
        # Legacy state predates this flag: a recorded date means it was delivered.
        artwork_sent = last_date is not None

    slug, url = discover.discover()

    if not last_slug:
        # First run: record the current top without sending, so we never deliver
        # yesterday's devotional on initial deploy. Nothing is pending for it.
        dev = parser.parse_devotional(slug, url)
        state.save_state(state_path, slug=slug, date_iso=dev.date_iso, artwork_sent=True)
        print(f"bootstrapped: recorded '{slug}' ({dev.date_iso}) without sending")
        return "bootstrapped"

    if slug == last_slug:
        if artwork_sent:
            print(f"noop: '{slug}' complete for the day")
            return "noop"
        # Text already went out on the placeholder; keep checking for the artwork.
        dev = parser.parse_devotional(slug, url)
        if dev.date_iso is None:
            print(f"noop: '{slug}' artwork not ready yet")
            return "noop"
        telegram.send_artwork(dev, token=token, chat_id=chat_id)
        state.save_state(state_path, slug=slug, date_iso=dev.date_iso, artwork_sent=True)
        print(f"artwork: sent artwork for '{slug}' ({dev.date_iso})")
        return "artwork"

    dev = parser.parse_devotional(slug, url)

    # Accuracy guard: never send a devotional dated older than the last one sent
    # (protects against a stale/cached response slipping an old entry to the top).
    # Only applies once a date is known; during the placeholder phase there is none.
    if dev.date_iso and last_date and dev.date_iso < last_date:
        print(f"skip: '{slug}' dated {dev.date_iso} is older than last sent {last_date}")
        return "noop"

    # New devotional: send the text immediately (earliest publishing).
    telegram.send_devotional(dev, token=token, chat_id=chat_id)
    if dev.date_iso is not None:
        # Artwork was already up at publish time — send it now; nothing left to wait for.
        telegram.send_artwork(dev, token=token, chat_id=chat_id)
        state.save_state(state_path, slug=slug, date_iso=dev.date_iso, artwork_sent=True)
        print(f"sent: '{slug}' text + artwork ({dev.date_iso})")
        return "sent"

    # Placeholder phase: text delivered, artwork still pending.
    state.save_state(state_path, slug=slug, date_iso=None, artwork_sent=False)
    print(f"sent: '{slug}' text only; awaiting artwork")
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
