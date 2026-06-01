import pytest
from phaneroo_bot import discover


def test_find_latest_from_fixture(fixture_text):
    html = fixture_text("daily_devotion.html")
    slug, url = discover.find_latest(html)
    assert slug  # non-empty
    assert url == f"https://phaneroo.org/devotion/{slug}/"
    assert "/devotion/" in url


def test_find_latest_picks_first_devotion_link():
    html = """
    <html><body>
      <a href="https://phaneroo.org/daily-devotion/">All</a>
      <a href="https://phaneroo.org/devotion/first-one/">First</a>
      <a href="https://phaneroo.org/devotion/second-one/">Second</a>
      <a href="https://phaneroo.org/devotion/#respond">Comment</a>
    </body></html>
    """
    slug, url = discover.find_latest(html)
    assert slug == "first-one"
    assert url == "https://phaneroo.org/devotion/first-one/"


def test_find_latest_raises_when_none_found():
    with pytest.raises(discover.NoDevotionalFound):
        discover.find_latest("<html><body>nothing</body></html>")


def test_discover_applies_cache_busting():
    seen = {}

    def fake_fetch(url):
        seen["url"] = url
        return '<a href="https://phaneroo.org/devotion/today/">x</a>'

    slug, url = discover.discover(fetch_text=fake_fetch)
    assert slug == "today"
    assert "nocache=" in seen["url"]
    assert seen["url"].startswith("https://phaneroo.org/daily-devotion/")


def test_discover_falls_back_to_homepage():
    calls = []

    def fake_fetch(url):
        calls.append(url)
        if "daily-devotion" in url:
            return "<html>no devotion links here</html>"
        return '<a href="https://phaneroo.org/devotion/from-home/">x</a>'

    slug, url = discover.discover(fetch_text=fake_fetch)
    assert slug == "from-home"
    assert len(calls) == 2  # tried the listing, then the homepage
