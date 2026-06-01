# Phaneroo Daily Devotional → Telegram Bot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python bot, run on free GitHub Actions, that each morning detects the new Phaneroo daily devotional and delivers its image + full English text + source link to one private Telegram chat.

**Architecture:** A scheduled GitHub Actions workflow runs `python -m phaneroo_bot.main` every 30 min across the morning window. The script discovers the latest devotional slug from the `/daily-devotion/` listing, compares it to a committed `state.json`, and — only when the slug is new — fetches the devotional (clean title + featured image from the WordPress oEmbed endpoint; English body scraped from the page's first language tab) and sends it to Telegram. State is committed back to the repo so reruns no-op.

**Tech Stack:** Python 3.11+, `requests`, `beautifulsoup4`, `python-dotenv` (local dev), `pytest`. Telegram via the plain HTTP Bot API.

---

## Confirmed source facts (from brainstorming recon)

- Latest devotional = the **first** `https://phaneroo.org/devotion/<slug>/` link on `https://phaneroo.org/daily-devotion/` (newest-first).
- **oEmbed** `GET https://phaneroo.org/wp-json/oembed/1.0/embed?url=<devotion_url>&format=json` returns clean `title` and `thumbnail_url` (the dated featured image, e.g. `.../31-May-2026_Web.png`).
- The devotion page body lives in an Elementor tabs widget with 6 language tabs (English, Luganda, Runyankore, Runyoro-Rutooro, Acholi, Lango). **The first `div.elementor-tab-content` is English.** Its `<p>` tags, in order, are: author byline → scripture reference → body paragraphs → `FURTHER STUDY:` → `GOLDEN NUGGET:` → `PRAYER:`.
- No og:image, no JSON-LD, no publish timestamp on the page — detection is **state-based** (compare slug).

## File Structure

```
phaneroo_bot/
  __init__.py          # package marker (empty)
  fetcher.py           # HTTP GET (text + json) with retries/timeout/UA
  discover.py          # listing HTML -> latest (slug, url)
  parser.py            # oEmbed + page HTML -> Devotional dataclass
  telegram.py          # HTML escape, chunking, sendPhoto/sendMessage, send_devotional
  state.py             # read/write state.json (last_slug + timestamp)
  main.py              # orchestration + CLI entrypoint
scripts/
  get_chat_id.py       # one-off helper: print chat IDs from getUpdates
tests/
  conftest.py          # fixture-path helper
  fixtures/
    daily_devotion.html
    devotion_sample.html
    oembed_sample.json
  test_discover.py
  test_parser.py
  test_telegram.py
  test_state.py
  test_main.py
.github/workflows/devotional.yml
state.json             # committed; updated by the workflow
requirements.txt
.gitignore
.env.example
README.md
```

---

## Task 0: Project scaffolding

**Files:**
- Create: `requirements.txt`, `.gitignore`, `.env.example`, `phaneroo_bot/__init__.py`, `tests/conftest.py`

- [ ] **Step 1: Create `requirements.txt`**

```
requests==2.32.3
beautifulsoup4==4.12.3
python-dotenv==1.0.1
pytest==8.3.3
```

- [ ] **Step 2: Create `.gitignore`**

```
__pycache__/
*.pyc
.env
.venv/
venv/
.pytest_cache/
```

- [ ] **Step 3: Create `.env.example`**

```
TELEGRAM_BOT_TOKEN=123456:replace-with-token-from-botfather
TELEGRAM_CHAT_ID=123456789
```

- [ ] **Step 4: Create empty package marker**

`phaneroo_bot/__init__.py` — empty file.

- [ ] **Step 5: Create `tests/conftest.py`** (fixture-path helper)

```python
from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_text():
    def _load(name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")
    return _load
```

- [ ] **Step 6: Set up the virtualenv and install**

Run:
```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
```
Expected: installs without error.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .gitignore .env.example phaneroo_bot/__init__.py tests/conftest.py
git commit -m "chore: project scaffolding"
```

---

## Task 1: Capture real HTML/JSON fixtures

**Files:**
- Create: `tests/fixtures/daily_devotion.html`, `tests/fixtures/devotion_sample.html`, `tests/fixtures/oembed_sample.json`

- [ ] **Step 1: Download the three fixtures**

Run:
```bash
curl -s "https://phaneroo.org/daily-devotion/" -o tests/fixtures/daily_devotion.html
curl -s "https://phaneroo.org/devotion/the-hidden-manna/" -o tests/fixtures/devotion_sample.html
curl -s "https://phaneroo.org/wp-json/oembed/1.0/embed?url=https%3A%2F%2Fphaneroo.org%2Fdevotion%2Fthe-hidden-manna%2F&format=json" -o tests/fixtures/oembed_sample.json
```

- [ ] **Step 2: Verify fixtures are non-trivial**

Run:
```bash
wc -c tests/fixtures/daily_devotion.html tests/fixtures/devotion_sample.html tests/fixtures/oembed_sample.json
```
Expected: listing ~100KB+, devotion ~110KB+, oembed a few hundred bytes (contains `"title"` and `"thumbnail_url"`).

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/
git commit -m "test: add real page fixtures for parser/discover"
```

---

## Task 2: `fetcher.py` — HTTP layer

**Files:**
- Create: `phaneroo_bot/fetcher.py`
- Test: `tests/test_fetcher.py`

- [ ] **Step 1: Write the failing test** (`tests/test_fetcher.py`)

```python
from unittest.mock import MagicMock, patch
import pytest
from phaneroo_bot import fetcher


def _resp(text="<html>ok</html>", json_data=None, status=200):
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.json.return_value = json_data
    r.raise_for_status = MagicMock()
    return r


@patch("phaneroo_bot.fetcher.requests.get")
def test_get_text_returns_body(mock_get):
    mock_get.return_value = _resp(text="<html>hi</html>")
    assert fetcher.get_text("https://x.test") == "<html>hi</html>"
    # sends a real User-Agent
    assert "User-Agent" in mock_get.call_args.kwargs["headers"]


@patch("phaneroo_bot.fetcher.requests.get")
def test_get_json_returns_dict(mock_get):
    mock_get.return_value = _resp(json_data={"title": "T"})
    assert fetcher.get_json("https://x.test") == {"title": "T"}


@patch("phaneroo_bot.fetcher.time.sleep", lambda *_: None)
@patch("phaneroo_bot.fetcher.requests.get")
def test_get_text_retries_then_succeeds(mock_get):
    import requests as r
    mock_get.side_effect = [r.exceptions.ConnectionError("boom"), _resp(text="ok2")]
    assert fetcher.get_text("https://x.test", retries=3) == "ok2"
    assert mock_get.call_count == 2


@patch("phaneroo_bot.fetcher.time.sleep", lambda *_: None)
@patch("phaneroo_bot.fetcher.requests.get")
def test_get_text_raises_after_exhausting_retries(mock_get):
    import requests as r
    mock_get.side_effect = r.exceptions.ConnectionError("boom")
    with pytest.raises(r.exceptions.ConnectionError):
        fetcher.get_text("https://x.test", retries=2)
    assert mock_get.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fetcher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'phaneroo_bot.fetcher'`.

- [ ] **Step 3: Write minimal implementation** (`phaneroo_bot/fetcher.py`)

```python
"""HTTP layer: GET text/JSON with retries, timeout, and a real User-Agent."""
import time
import requests

USER_AGENT = (
    "Mozilla/5.0 (compatible; PhaneerooDevotionalBot/1.0; "
    "+https://github.com/)"
)
DEFAULT_TIMEOUT = 20


def _get(url: str, *, timeout: int, retries: int) -> requests.Response:
    last_exc = None
    for attempt in range(retries):
        try:
            resp = requests.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=timeout
            )
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    raise last_exc


def get_text(url: str, *, timeout: int = DEFAULT_TIMEOUT, retries: int = 3) -> str:
    return _get(url, timeout=timeout, retries=retries).text


def get_json(url: str, *, timeout: int = DEFAULT_TIMEOUT, retries: int = 3) -> dict:
    return _get(url, timeout=timeout, retries=retries).json()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fetcher.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add phaneroo_bot/fetcher.py tests/test_fetcher.py
git commit -m "feat: HTTP fetcher with retries"
```

---

## Task 3: `discover.py` — find the latest devotional

**Files:**
- Create: `phaneroo_bot/discover.py`
- Test: `tests/test_discover.py`

- [ ] **Step 1: Write the failing test** (`tests/test_discover.py`)

```python
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
    import pytest
    with pytest.raises(discover.NoDevotionalFound):
        discover.find_latest("<html><body>nothing</body></html>")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_discover.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'phaneroo_bot.discover'`.

- [ ] **Step 3: Write minimal implementation** (`phaneroo_bot/discover.py`)

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_discover.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add phaneroo_bot/discover.py tests/test_discover.py
git commit -m "feat: discover latest devotional from listing"
```

---

## Task 4: `parser.py` — build the Devotional from oEmbed + page

**Files:**
- Create: `phaneroo_bot/parser.py`
- Test: `tests/test_parser.py`

- [ ] **Step 1: Write the failing test** (`tests/test_parser.py`)

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'phaneroo_bot.parser'`.

- [ ] **Step 3: Write minimal implementation** (`phaneroo_bot/parser.py`)

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_parser.py -v`
Expected: PASS (4 passed). If `test_extract_body_from_fixture` fails on the scripture/author assertions, inspect the first `div.elementor-tab-content` in the fixture and adjust `_AUTHOR_RE`/`_SCRIPTURE_RE` — the fixture is the source of truth.

- [ ] **Step 5: Commit**

```bash
git add phaneroo_bot/parser.py tests/test_parser.py
git commit -m "feat: parse devotional from oEmbed + English tab"
```

---

## Task 5: `telegram.py` — formatting and delivery

**Files:**
- Create: `phaneroo_bot/telegram.py`
- Test: `tests/test_telegram.py`

- [ ] **Step 1: Write the failing test** (`tests/test_telegram.py`)

```python
from unittest.mock import patch
from phaneroo_bot import telegram
from phaneroo_bot.parser import Devotional


def test_escape_html():
    assert telegram.escape_html("a & b < c > d") == "a &amp; b &lt; c &gt; d"


def test_chunk_text_short_is_single_chunk():
    assert telegram.chunk_text("hello", limit=4000) == ["hello"]


def test_chunk_text_splits_on_paragraph_boundary():
    text = "A" * 3000 + "\n\n" + "B" * 3000
    chunks = telegram.chunk_text(text, limit=4000)
    assert len(chunks) == 2
    assert chunks[0] == "A" * 3000
    assert chunks[1] == "B" * 3000
    assert all(len(c) <= 4000 for c in chunks)


def test_chunk_text_hard_splits_oversized_paragraph():
    chunks = telegram.chunk_text("X" * 9000, limit=4000)
    assert all(len(c) <= 4000 for c in chunks)
    assert "".join(chunks) == "X" * 9000


def test_build_messages_structure():
    dev = Devotional(
        slug="s", url="https://phaneroo.org/devotion/s/", title="My <Title>",
        author="Apostle Grace Lubega", scripture="John 3:16 (NKJV): For God...",
        body=["First para.", "GOLDEN NUGGET: x", "PRAYER: y"],
        image_url="https://img.test/x.png",
    )
    caption, body_chunks, link = telegram.build_messages(dev)
    assert "<b>My &lt;Title&gt;</b>" in caption           # title escaped + bold
    assert "Apostle Grace Lubega" in caption
    assert "<b>John 3:16" in body_chunks[0]                 # scripture bold, first
    assert "First para." in "".join(body_chunks)
    assert 'href="https://phaneroo.org/devotion/s/"' in link


@patch("phaneroo_bot.telegram.requests.post")
def test_send_devotional_with_image_sends_photo_then_text(mock_post):
    mock_post.return_value.raise_for_status = lambda: None
    mock_post.return_value.json.return_value = {"ok": True}
    dev = Devotional(
        slug="s", url="https://phaneroo.org/devotion/s/", title="T",
        author="A", scripture="John 3:16", body=["Body."], image_url="https://img/x.png",
    )
    telegram.send_devotional(dev, token="TOK", chat_id="42")
    called = [c.args[0] for c in mock_post.call_args_list]
    assert any("sendPhoto" in u for u in called)
    assert any("sendMessage" in u for u in called)


@patch("phaneroo_bot.telegram.requests.post")
def test_send_devotional_without_image_uses_text_header(mock_post):
    mock_post.return_value.raise_for_status = lambda: None
    mock_post.return_value.json.return_value = {"ok": True}
    dev = Devotional(
        slug="s", url="https://phaneroo.org/devotion/s/", title="T",
        author="A", scripture="John 3:16", body=["Body."], image_url=None,
    )
    telegram.send_devotional(dev, token="TOK", chat_id="42")
    called = [c.args[0] for c in mock_post.call_args_list]
    assert not any("sendPhoto" in u for u in called)
    assert any("sendMessage" in u for u in called)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_telegram.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'phaneroo_bot.telegram'`.

- [ ] **Step 3: Write minimal implementation** (`phaneroo_bot/telegram.py`)

```python
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


def build_messages(dev) -> tuple[str, list[str], str]:
    """Return (photo_caption, body_chunks, link_message), all HTML-formatted."""
    caption = f"<b>{escape_html(dev.title)}</b>"
    if dev.author:
        caption += f"\n<i>{escape_html(dev.author)}</i>"

    parts = []
    if dev.scripture:
        parts.append(f"<b>{escape_html(dev.scripture)}</b>")
    parts.extend(escape_html(p) for p in dev.body)
    body_chunks = chunk_text("\n\n".join(parts))

    link = f'📖 <a href="{dev.url}">Read on phaneroo.org</a>'
    return caption, body_chunks, link


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
    caption, body_chunks, link = build_messages(dev)
    if dev.image_url:
        send_photo(token, chat_id, dev.image_url, caption)
    else:
        send_message(token, chat_id, caption)
    for chunk in body_chunks:
        send_message(token, chat_id, chunk)
    send_message(token, chat_id, link)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_telegram.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add phaneroo_bot/telegram.py tests/test_telegram.py
git commit -m "feat: telegram formatting, chunking, and delivery"
```

---

## Task 6: `state.py` — remember the last slug

**Files:**
- Create: `phaneroo_bot/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: Write the failing test** (`tests/test_state.py`)

```python
from phaneroo_bot import state


def test_load_returns_none_when_missing(tmp_path):
    assert state.load_last_slug(tmp_path / "state.json") is None


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    state.save_last_slug(path, "the-hidden-manna")
    assert state.load_last_slug(path) == "the-hidden-manna"


def test_save_writes_timestamp(tmp_path):
    import json
    path = tmp_path / "state.json"
    state.save_last_slug(path, "x")
    data = json.loads(path.read_text())
    assert data["last_slug"] == "x"
    assert "last_sent_at" in data and data["last_sent_at"].endswith("+00:00") or "Z" in data["last_sent_at"]


def test_load_handles_corrupt_file(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("not json{")
    assert state.load_last_slug(path) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'phaneroo_bot.state'`.

- [ ] **Step 3: Write minimal implementation** (`phaneroo_bot/state.py`)

```python
"""Persist the last devotional slug we sent (committed back by the workflow)."""
import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = Path("state.json")


def load_last_slug(path: Path = DEFAULT_PATH) -> str | None:
    path = Path(path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("last_slug")
    except (json.JSONDecodeError, ValueError):
        return None


def save_last_slug(path: Path, slug: str) -> None:
    path = Path(path)
    data = {
        "last_slug": slug,
        "last_sent_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_state.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add phaneroo_bot/state.py tests/test_state.py
git commit -m "feat: state persistence for last sent slug"
```

---

## Task 7: `main.py` — orchestration

**Files:**
- Create: `phaneroo_bot/main.py`
- Test: `tests/test_main.py`

Behavior contract for `run()` — returns a string action and never sends on bootstrap:
- empty state → save slug, **return `"bootstrapped"`**, no send
- slug unchanged → **return `"noop"`**, no send
- new slug → parse, send, save, **return `"sent"`**
- send failure → state NOT updated, exception propagates

- [ ] **Step 1: Write the failing test** (`tests/test_main.py`)

```python
from unittest.mock import patch
import pytest
from phaneroo_bot import main, state
from phaneroo_bot.parser import Devotional


def _dev(slug="new-one"):
    return Devotional(
        slug=slug, url=f"https://phaneroo.org/devotion/{slug}/", title="T",
        author="A", scripture="John 3:16", body=["Body."], image_url=None,
    )


@patch("phaneroo_bot.main.telegram.send_devotional")
@patch("phaneroo_bot.main.parser.parse_devotional")
@patch("phaneroo_bot.main.discover.discover")
def test_bootstrap_records_without_sending(mock_disc, mock_parse, mock_send, tmp_path):
    sp = tmp_path / "state.json"
    mock_disc.return_value = ("today-slug", "https://phaneroo.org/devotion/today-slug/")
    action = main.run(state_path=sp, token="TOK", chat_id="42")
    assert action == "bootstrapped"
    mock_send.assert_not_called()
    assert state.load_last_slug(sp) == "today-slug"


@patch("phaneroo_bot.main.telegram.send_devotional")
@patch("phaneroo_bot.main.parser.parse_devotional")
@patch("phaneroo_bot.main.discover.discover")
def test_noop_when_slug_unchanged(mock_disc, mock_parse, mock_send, tmp_path):
    sp = tmp_path / "state.json"
    state.save_last_slug(sp, "same-slug")
    mock_disc.return_value = ("same-slug", "https://phaneroo.org/devotion/same-slug/")
    action = main.run(state_path=sp, token="TOK", chat_id="42")
    assert action == "noop"
    mock_send.assert_not_called()


@patch("phaneroo_bot.main.telegram.send_devotional")
@patch("phaneroo_bot.main.parser.parse_devotional")
@patch("phaneroo_bot.main.discover.discover")
def test_sends_on_new_slug_and_updates_state(mock_disc, mock_parse, mock_send, tmp_path):
    sp = tmp_path / "state.json"
    state.save_last_slug(sp, "old-slug")
    mock_disc.return_value = ("new-one", "https://phaneroo.org/devotion/new-one/")
    mock_parse.return_value = _dev("new-one")
    action = main.run(state_path=sp, token="TOK", chat_id="42")
    assert action == "sent"
    mock_send.assert_called_once()
    assert state.load_last_slug(sp) == "new-one"


@patch("phaneroo_bot.main.telegram.send_devotional", side_effect=RuntimeError("telegram down"))
@patch("phaneroo_bot.main.parser.parse_devotional")
@patch("phaneroo_bot.main.discover.discover")
def test_state_not_updated_when_send_fails(mock_disc, mock_parse, mock_send, tmp_path):
    sp = tmp_path / "state.json"
    state.save_last_slug(sp, "old-slug")
    mock_disc.return_value = ("new-one", "https://phaneroo.org/devotion/new-one/")
    mock_parse.return_value = _dev("new-one")
    with pytest.raises(RuntimeError):
        main.run(state_path=sp, token="TOK", chat_id="42")
    assert state.load_last_slug(sp) == "old-slug"  # unchanged
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'phaneroo_bot.main'`.

- [ ] **Step 3: Write minimal implementation** (`phaneroo_bot/main.py`)

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all tests pass (fetcher, discover, parser, telegram, state, main).

- [ ] **Step 6: Commit**

```bash
git add phaneroo_bot/main.py tests/test_main.py
git commit -m "feat: orchestration entrypoint"
```

---

## Task 8: `scripts/get_chat_id.py` — chat ID helper

**Files:**
- Create: `scripts/get_chat_id.py`

- [ ] **Step 1: Write the helper** (`scripts/get_chat_id.py`)

```python
"""Print chat IDs the bot can see. Message the bot first, then run this.

Usage:
    TELEGRAM_BOT_TOKEN=... python scripts/get_chat_id.py
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()
token = os.environ.get("TELEGRAM_BOT_TOKEN")
if not token:
    print("Set TELEGRAM_BOT_TOKEN (env or .env) first", file=sys.stderr)
    raise SystemExit(2)

resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30)
resp.raise_for_status()
updates = resp.json().get("result", [])
if not updates:
    print("No updates. Send any message to your bot in Telegram, then re-run.")
    raise SystemExit(0)

seen = {}
for u in updates:
    msg = u.get("message") or u.get("channel_post") or {}
    chat = msg.get("chat", {})
    if chat.get("id") is not None:
        seen[chat["id"]] = chat.get("title") or chat.get("username") or chat.get("first_name", "")
for cid, name in seen.items():
    print(f"chat_id={cid}  ({name})")
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `python -c "import ast; ast.parse(open('scripts/get_chat_id.py').read())"`
Expected: no output (valid Python).

- [ ] **Step 3: Commit**

```bash
git add scripts/get_chat_id.py
git commit -m "feat: helper to fetch Telegram chat id"
```

---

## Task 9: GitHub Actions workflow + initial `state.json`

**Files:**
- Create: `.github/workflows/devotional.yml`, `state.json`

- [ ] **Step 1: Create the committed empty state** (`state.json`)

```json
{
  "last_slug": null,
  "last_sent_at": null
}
```

(The first scheduled/manual run will bootstrap it to the current top slug without sending.)

- [ ] **Step 2: Create the workflow** (`.github/workflows/devotional.yml`)

```yaml
name: Daily Devotional

on:
  schedule:
    # Every 30 min across the EAT morning window (UTC; EAT = UTC+3).
    # 21:00-06:59 UTC == 00:00-09:59 EAT.
    - cron: "*/30 0-6,21-23 * * *"
  workflow_dispatch: {}

# Prevent overlapping runs from racing on the state commit.
concurrency:
  group: daily-devotional
  cancel-in-progress: false

permissions:
  contents: write

jobs:
  send:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run bot
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python -m phaneroo_bot.main

      - name: Commit updated state
        run: |
          if [[ -n "$(git status --porcelain state.json)" ]]; then
            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"
            git pull --rebase --autostash origin "${GITHUB_REF_NAME}" || true
            git add state.json
            git commit -m "chore: update devotional state [skip ci]"
            git push
          else
            echo "No state change."
          fi
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/devotional.yml state.json
git commit -m "ci: scheduled GitHub Actions workflow + initial state"
```

---

## Task 10: `README.md` — setup & operation docs

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write the README**

````markdown
# Phaneroo Daily Devotional → Telegram Bot

Automatically detects the new [Phaneroo](https://phaneroo.org/) daily devotional each
morning and sends its image + full English text + source link to a private Telegram chat.
Runs on free GitHub Actions — no server required.

## How it works

A scheduled workflow runs every 30 minutes across the morning window (00:00–09:00 EAT).
It reads the latest devotional slug from `https://phaneroo.org/daily-devotion/`, compares
it to `state.json`, and — only when a new one appears — fetches the devotional (title +
featured image via the WordPress oEmbed API; English body scraped from the page) and
sends it to Telegram. The new slug is committed back to `state.json` so later runs no-op.

## Setup

1. **Create the bot:** message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the
   token.
2. **Find your chat ID:** send any message to your new bot, then run:
   ```bash
   TELEGRAM_BOT_TOKEN=<token> python scripts/get_chat_id.py
   ```
   Copy the `chat_id`.
3. **Add GitHub secrets** (repo → Settings → Secrets and variables → Actions):
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. **Push to GitHub.** The workflow's first run (or trigger it manually via the Actions tab
   → *Daily Devotional* → *Run workflow*) **bootstraps**: it records the current top
   devotional without sending, so you don't receive yesterday's. The next new devotional
   is the first one delivered.

## Local development

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your token + chat id
pytest                 # run the test suite
python -m phaneroo_bot.main   # run once locally
```

## Scheduling

`cron: "*/30 0-6,21-23 * * *"` (UTC) = every 30 min, 00:00–09:59 EAT. Adjust in
`.github/workflows/devotional.yml`. GitHub cron is best-effort and may be delayed a few
minutes under load.

## Notes

- State lives in `state.json`, committed by the workflow with `[skip ci]`.
- The parser targets the page's first language tab (English). If Phaneroo changes the page
  markup, `tests/test_parser.py` (run against `tests/fixtures/`) will catch it — refresh
  the fixtures and adjust selectors.
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: setup and operation README"
```

---

## Final verification

- [ ] **Run the full test suite**

Run: `pytest -v`
Expected: all tests green across all modules.

- [ ] **Smoke-test discovery + parse against the live site (no Telegram send)**

Run:
```bash
python -c "from phaneroo_bot import discover, parser; s,u=discover.discover(); d=parser.parse_devotional(s,u); print(d.title, '|', d.image_url); print('SCRIPTURE:', d.scripture); print('PARAS:', len(d.body))"
```
Expected: prints the current devotional's real title, image URL, scripture, and a non-zero paragraph count.

- [ ] **Optional end-to-end test** (sends a real message to your chat): set `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`, temporarily set `state.json` `last_slug` to any non-current value, then `python -m phaneroo_bot.main`. Reset `state.json` afterward.
````
