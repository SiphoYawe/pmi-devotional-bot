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
