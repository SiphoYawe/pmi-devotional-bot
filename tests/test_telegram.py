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
