"""Find the latest devotional slug from the /daily-devotion/ listing."""
import re
from bs4 import BeautifulSoup
from phaneroo_bot import fetcher

LISTING_URL = "https://phaneroo.org/daily-devotion/"
# https://phaneroo.org/devotion/<slug>/  (slug = lowercase letters/digits/hyphens)
_DEVOTION_RE = re.compile(r"^https://phaneroo\.org/devotion/([a-z0-9-]+)/$")


class NoDevotionalFound(Exception):
    pass


def find_latest(listing_html: str) -> tuple[str, str]:
    """Return (slug, url) of the newest devotional (first matching link)."""
    soup = BeautifulSoup(listing_html, "html.parser")
    for a in soup.find_all("a", href=True):
        m = _DEVOTION_RE.match(a["href"].strip())
        if m:
            slug = m.group(1)
            return slug, f"https://phaneroo.org/devotion/{slug}/"
    raise NoDevotionalFound("No /devotion/<slug>/ link found on listing page")


def discover(fetch_text=fetcher.get_text) -> tuple[str, str]:
    return find_latest(fetch_text(LISTING_URL))
