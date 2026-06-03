"""Format a Devotional and deliver it via the Telegram Bot HTTP API."""
import requests

API = "https://api.telegram.org/bot{token}/{method}"
CAPTION_LIMIT = 1024
MESSAGE_LIMIT = 4096
SAFE_CHUNK = 4000  # stay safely under MESSAGE_LIMIT


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def chunk_text(text: str, limit: int = SAFE_CHUNK) -> list[str]:
    """Split text into <=limit chunks, preferring paragraph (\\n\\n) boundaries."""
    chunks, current = [], ""
    for para in text.split("\n\n"):
        # Oversized single paragraph: hard-split it.
        if len(para) > limit:
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(para), limit):
                chunks.append(para[i : i + limit])
            continue
        candidate = para if not current else current + "\n\n" + para
        if len(candidate) <= limit:
            current = candidate
        else:
            chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks or [""]


def build_messages(dev) -> tuple[str, list[str]]:
    """Return (header_text, body_chunks), all HTML-formatted."""
    header = f"<b>{escape_html(dev.title)}</b>"
    if dev.date:
        header += f"\n📅 {escape_html(dev.date)}"
    if dev.author:
        header += f"\n<i>{escape_html(dev.author)}</i>"

    parts = []
    if dev.scripture:
        parts.append(f"<b>{escape_html(dev.scripture)}</b>")
    parts.extend(escape_html(p) for p in dev.body)
    body_chunks = chunk_text("\n\n".join(parts))
    return header, body_chunks


def _post(token: str, method: str, payload: dict) -> None:
    resp = requests.post(API.format(token=token, method=method), data=payload, timeout=30)
    resp.raise_for_status()


def send_message(token: str, chat_id: str, text: str) -> None:
    _post(token, "sendMessage", {
        "chat_id": chat_id, "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": False,
    })


def send_photo(token: str, chat_id: str, photo_url: str, caption: str) -> None:
    _post(token, "sendPhoto", {
        "chat_id": chat_id, "photo": photo_url,
        "caption": caption[:CAPTION_LIMIT], "parse_mode": "HTML",
    })


def send_devotional(dev, *, token: str, chat_id: str) -> None:
    """Send the devotional as text only — no image (placeholder), no external link.

    The dedicated artwork image is delivered separately via send_artwork() once
    Phaneroo replaces the placeholder with the devotional's real artwork.
    """
    header, body_chunks = build_messages(dev)
    send_message(token, chat_id, header)
    for chunk in body_chunks:
        send_message(token, chat_id, chunk)


def send_artwork(dev, *, token: str, chat_id: str) -> None:
    """Send the devotional's artwork image, captioned with its name (no emoji)."""
    if not dev.image_url:
        return
    caption = f"<b>{escape_html(dev.title)}</b>"
    send_photo(token, chat_id, dev.image_url, caption)
