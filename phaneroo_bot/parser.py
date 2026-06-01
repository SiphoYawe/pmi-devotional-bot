"""Parse a devotional: clean title+image from oEmbed, English body from the page."""
import re
from dataclasses import dataclass, field
from urllib.parse import quote
from bs4 import BeautifulSoup
from phaneroo_bot import fetcher

OEMBED_URL = "https://phaneroo.org/wp-json/oembed/1.0/embed"

# A scripture reference contains a "chapter:verse" like "2:17".
_SCRIPTURE_RE = re.compile(r"\b\d+:\d+\b")
# Author bylines start with a ministry title.
_AUTHOR_RE = re.compile(r"^(Apostle|Pastor|Rev|Reverend|Ps|Bishop|Dr|Evangelist)\b")
_SEPARATORS = {"", "—", "–", "-", "."}


@dataclass
class Devotional:
    slug: str
    url: str
    title: str
    author: str | None = None
    scripture: str | None = None
    body: list[str] = field(default_factory=list)
    image_url: str | None = None


def extract_metadata(oembed_json: dict) -> tuple[str, str | None]:
    """Return (title, image_url) from the oEmbed JSON."""
    title = (oembed_json.get("title") or "").strip()
    image_url = oembed_json.get("thumbnail_url") or None
    return title, image_url


def _english_paragraphs(html: str) -> list[str]:
    """Ordered, non-empty <p> texts from the first (English) language tab."""
    soup = BeautifulSoup(html, "html.parser")
    panel = soup.select_one("div.elementor-tab-content")
    if panel is None:
        return []
    out = []
    for p in panel.find_all("p"):
        text = p.get_text(" ", strip=True)
        if text:
            out.append(text)
    return out


def extract_body(html: str) -> tuple[str | None, str | None, list[str]]:
    """Return (author, scripture, body_paragraphs) from the English tab."""
    paras = [p for p in _english_paragraphs(html) if p not in _SEPARATORS]

    author = None
    if paras and _AUTHOR_RE.match(paras[0]):
        author = paras.pop(0)

    scripture = None
    for i, p in enumerate(paras):
        if _SCRIPTURE_RE.search(p):
            scripture = paras.pop(i)
            break

    return author, scripture, paras


def parse_devotional(
    slug: str,
    url: str,
    *,
    fetch_text=fetcher.get_text,
    fetch_json=fetcher.get_json,
) -> Devotional:
    oembed = fetch_json(f"{OEMBED_URL}?url={quote(url, safe='')}&format=json")
    title, image_url = extract_metadata(oembed)
    author, scripture, body = extract_body(fetch_text(url))
    return Devotional(
        slug=slug,
        url=url,
        title=title,
        author=author,
        scripture=scripture,
        body=body,
        image_url=image_url,
    )
