import json
from pathlib import Path
from phaneroo_bot import parser

FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_metadata_from_oembed():
    data = json.loads((FIXTURES / "oembed_sample.json").read_text(encoding="utf-8"))
    title, image_url = parser.extract_metadata(data)
    assert title == "The Hidden Manna"
    assert image_url.startswith("https://phaneroo.org/wp-content/uploads/")
    assert image_url.endswith(".png")


def test_extract_metadata_missing_thumbnail():
    title, image_url = parser.extract_metadata({"title": "X"})
    assert title == "X"
    assert image_url is None


def test_extract_metadata_decodes_html_entities():
    title, _ = parser.extract_metadata({"title": "The Believer&#8217;s Authority"})
    assert title == "The Believer’s Authority"


def test_date_from_image_url_hyphen_format():
    display, iso = parser.date_from_image_url(
        "https://phaneroo.org/wp-content/uploads/2026/06/01-June-2026_Web.png"
    )
    assert display == "1 June 2026"
    assert iso == "2026-06-01"


def test_date_from_image_url_underscore_format():
    display, iso = parser.date_from_image_url(
        "https://phaneroo.org/wp-content/uploads/2026/05/21_May_2026_Web.jpg"
    )
    assert display == "21 May 2026"
    assert iso == "2026-05-21"


def test_date_from_image_url_unparseable_is_none():
    assert parser.date_from_image_url("https://x/logo.png") == (None, None)
    assert parser.date_from_image_url(None) == (None, None)


def test_extract_body_from_fixture(fixture_text):
    html = fixture_text("devotion_sample.html")
    author, scripture, body = parser.extract_body(html)
    assert author == "Apostle Grace Lubega"
    assert scripture.startswith("Revelation 2:17")
    # body keeps the named sections, drops byline/scripture/separators
    assert any(p.startswith("GOLDEN NUGGET:") for p in body)
    assert any(p.startswith("PRAYER:") for p in body)
    assert all(p.strip() not in {"", "—", "–", "-"} for p in body)
    assert "Apostle Grace Lubega" not in body
    # Luganda translation must NOT leak in (only the first/English tab)
    assert not any("Okubikkulirwa" in p for p in body)


def test_parse_devotional_assembles_everything(fixture_text):
    oembed = json.loads((FIXTURES / "oembed_sample.json").read_text(encoding="utf-8"))
    page_html = fixture_text("devotion_sample.html")
    dev = parser.parse_devotional(
        "the-hidden-manna",
        "https://phaneroo.org/devotion/the-hidden-manna/",
        fetch_text=lambda url: page_html,
        fetch_json=lambda url: oembed,
    )
    assert dev.slug == "the-hidden-manna"
    assert dev.title == "The Hidden Manna"
    assert dev.author == "Apostle Grace Lubega"
    assert dev.scripture.startswith("Revelation 2:17")
    assert len(dev.body) >= 3
    assert dev.image_url.endswith(".png")
    assert dev.url == "https://phaneroo.org/devotion/the-hidden-manna/"
    # date parsed from the thumbnail (31-May-2026_Web.png)
    assert dev.date == "31 May 2026"
    assert dev.date_iso == "2026-05-31"
