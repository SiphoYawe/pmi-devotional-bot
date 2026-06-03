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
        image_url="https://img.test/x.png", date="1 June 2026", date_iso="2026-06-01",
    )
    header, body_chunks = telegram.build_messages(dev)
    assert "<b>My &lt;Title&gt;</b>" in header             # title escaped + bold
    assert "1 June 2026" in header                         # date shown
    assert "Apostle Grace Lubega" in header
    assert "<b>John 3:16" in body_chunks[0]                 # scripture bold, first
    assert "First para." in "".join(body_chunks)


@patch("phaneroo_bot.telegram.requests.post")
def test_send_devotional_is_text_only_never_photo(mock_post):
    # First send is text only: no photo (placeholder is skipped) and no link.
    mock_post.return_value.raise_for_status = lambda: None
    mock_post.return_value.json.return_value = {"ok": True}
    dev = Devotional(
        slug="s", url="https://phaneroo.org/devotion/s/", title="T",
        author="A", scripture="John 3:16", body=["Body."],
        image_url="https://img/x.png",  # even with an image present, don't send it
    )
    telegram.send_devotional(dev, token="TOK", chat_id="42")
    called = [c.args[0] for c in mock_post.call_args_list]
    assert not any("sendPhoto" in u for u in called)
    assert any("sendMessage" in u for u in called)


@patch("phaneroo_bot.telegram.requests.post")
def test_send_artwork_sends_photo_captioned_with_name(mock_post):
    mock_post.return_value.raise_for_status = lambda: None
    mock_post.return_value.json.return_value = {"ok": True}
    dev = Devotional(
        slug="s", url="https://phaneroo.org/devotion/s/", title="My <Title>",
        body=["Body."], image_url="https://img/03-June-2026_Web.png",
        date="3 June 2026", date_iso="2026-06-03",
    )
    telegram.send_artwork(dev, token="TOK", chat_id="42")
    called = [c.args[0] for c in mock_post.call_args_list]
    assert any("sendPhoto" in u for u in called)
    assert not any("sendMessage" in u for u in called)
    # Caption is the devotional name (escaped), no emoji.
    photo_call = next(c for c in mock_post.call_args_list if "sendPhoto" in c.args[0])
    caption = photo_call.kwargs["data"]["caption"]
    assert "My &lt;Title&gt;" in caption
    assert "📅" not in caption and "🎨" not in caption


@patch("phaneroo_bot.telegram.requests.post")
def test_send_artwork_noop_without_image(mock_post):
    dev = Devotional(
        slug="s", url="https://phaneroo.org/devotion/s/", title="T",
        body=["Body."], image_url=None,
    )
    telegram.send_artwork(dev, token="TOK", chat_id="42")
    mock_post.assert_not_called()
