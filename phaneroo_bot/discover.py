"""Find the latest devotional slug, bypassing the site's WordPress page cache.

The /daily-devotion/ listing is served from a page cache that can be a day stale,
so we append a unique query param to force a fresh response. The homepage (which
also lists the newest devotional first) is used as a fallback.
"""
import re
import time
from bs4 import BeautifulSoup
from phaneroo_bot import fetcher

LISTING_URL = "https://phaneroo.org/daily-devotion/"
HOMEPAGE_URL = "https://phaneroo.org/"
# https://phaneroo.org/<base>/<slug>/  (slug = lowercase letters/digits/hyphens).
# The permalink base changed from "devotion" to "daily_devotion" on 2026-08-20;
# both are accepted because the old form still 301s to the new one, and matching
# either means a future flip back does not take the bot down. Note the listing
# itself lives at /daily-devotion/ (hyphen) and correctly matches neither.
_DEVOTION_RE = re.compile(
    r"^https://phaneroo\.org/(daily_devotion|devotion)/([a-z0-9-]+)/$"
)


class NoDevotionalFound(Exception):
    pass


def _cache_busted(url: str) -> str:
    """Append a unique query param so the WP page cache returns fresh content."""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}nocache={int(time.time())}"


def find_latest(listing_html: str) -> tuple[str, str]:
    """Return (slug, url) of the newest devotional (first matching link)."""
    soup = BeautifulSoup(listing_html, "html.parser")
    for a in soup.find_all("a", href=True):
        m = _DEVOTION_RE.match(a["href"].strip())
        if m:
            base, slug = m.group(1), m.group(2)
            return slug, f"https://phaneroo.org/{base}/{slug}/"
    raise NoDevotionalFound("No /daily_devotion/<slug>/ link found")


def discover(fetch_text=fetcher.get_text) -> tuple[str, str]:
    """Newest devotional from the cache-busted listing; homepage as fallback."""
    for source in (LISTING_URL, HOMEPAGE_URL):
        try:
            return find_latest(fetch_text(_cache_busted(source)))
        except NoDevotionalFound:
            continue
    raise NoDevotionalFound("No devotional found on listing or homepage")
