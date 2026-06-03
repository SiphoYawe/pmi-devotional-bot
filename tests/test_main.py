from unittest.mock import patch
import pytest
from phaneroo_bot import main, state
from phaneroo_bot.parser import Devotional


def _dev(slug="new-one", date_iso="2026-06-01", image_url="https://img/x.png"):
    return Devotional(
        slug=slug, url=f"https://phaneroo.org/devotion/{slug}/", title="T",
        author="A", scripture="John 3:16", body=["Body."], image_url=image_url,
        date="1 June 2026" if date_iso else None, date_iso=date_iso,
    )


@patch("phaneroo_bot.main.telegram.send_artwork")
@patch("phaneroo_bot.main.telegram.send_devotional")
@patch("phaneroo_bot.main.parser.parse_devotional")
@patch("phaneroo_bot.main.discover.discover")
def test_bootstrap_records_without_sending(mock_disc, mock_parse, mock_send, mock_art, tmp_path):
    sp = tmp_path / "state.json"
    mock_disc.return_value = ("today-slug", "https://phaneroo.org/devotion/today-slug/")
    mock_parse.return_value = _dev("today-slug")
    action = main.run(state_path=sp, token="TOK", chat_id="42")
    assert action == "bootstrapped"
    mock_send.assert_not_called()
    mock_art.assert_not_called()
    st = state.load_state(sp)
    assert st["last_slug"] == "today-slug"
    assert st["artwork_sent"] is True  # nothing pending for a devotional we didn't send


@patch("phaneroo_bot.main.telegram.send_artwork")
@patch("phaneroo_bot.main.telegram.send_devotional")
@patch("phaneroo_bot.main.parser.parse_devotional")
@patch("phaneroo_bot.main.discover.discover")
def test_new_slug_placeholder_sends_text_only_and_awaits_artwork(
    mock_disc, mock_parse, mock_send, mock_art, tmp_path
):
    sp = tmp_path / "state.json"
    state.save_state(sp, slug="old-slug", date_iso="2026-05-31", artwork_sent=True)
    mock_disc.return_value = ("new-one", "https://phaneroo.org/devotion/new-one/")
    # Placeholder phase: no dated filename, so date_iso is None.
    mock_parse.return_value = _dev("new-one", date_iso=None)
    action = main.run(state_path=sp, token="TOK", chat_id="42")
    assert action == "sent"
    mock_send.assert_called_once()      # text sent
    mock_art.assert_not_called()        # artwork not ready yet
    st = state.load_state(sp)
    assert st["last_slug"] == "new-one"
    assert st["artwork_sent"] is False  # still waiting on artwork


@patch("phaneroo_bot.main.telegram.send_artwork")
@patch("phaneroo_bot.main.telegram.send_devotional")
@patch("phaneroo_bot.main.parser.parse_devotional")
@patch("phaneroo_bot.main.discover.discover")
def test_new_slug_with_artwork_already_up_sends_text_then_artwork(
    mock_disc, mock_parse, mock_send, mock_art, tmp_path
):
    sp = tmp_path / "state.json"
    state.save_state(sp, slug="old-slug", date_iso="2026-05-31", artwork_sent=True)
    mock_disc.return_value = ("new-one", "https://phaneroo.org/devotion/new-one/")
    mock_parse.return_value = _dev("new-one", date_iso="2026-06-01")  # artwork present
    action = main.run(state_path=sp, token="TOK", chat_id="42")
    assert action == "sent"
    mock_send.assert_called_once()
    mock_art.assert_called_once()
    st = state.load_state(sp)
    assert st["last_slug"] == "new-one"
    assert st["last_date"] == "2026-06-01"
    assert st["artwork_sent"] is True


@patch("phaneroo_bot.main.telegram.send_artwork")
@patch("phaneroo_bot.main.telegram.send_devotional")
@patch("phaneroo_bot.main.parser.parse_devotional")
@patch("phaneroo_bot.main.discover.discover")
def test_same_slug_artwork_now_ready_sends_artwork(
    mock_disc, mock_parse, mock_send, mock_art, tmp_path
):
    sp = tmp_path / "state.json"
    # Text was already sent during the placeholder phase; still awaiting artwork.
    state.save_state(sp, slug="cur", date_iso=None, artwork_sent=False)
    mock_disc.return_value = ("cur", "https://phaneroo.org/devotion/cur/")
    mock_parse.return_value = _dev("cur", date_iso="2026-06-03")  # artwork just landed
    action = main.run(state_path=sp, token="TOK", chat_id="42")
    assert action == "artwork"
    mock_send.assert_not_called()       # don't resend the text
    mock_art.assert_called_once()       # send the artwork image
    st = state.load_state(sp)
    assert st["artwork_sent"] is True
    assert st["last_date"] == "2026-06-03"


@patch("phaneroo_bot.main.telegram.send_artwork")
@patch("phaneroo_bot.main.telegram.send_devotional")
@patch("phaneroo_bot.main.parser.parse_devotional")
@patch("phaneroo_bot.main.discover.discover")
def test_same_slug_artwork_not_ready_is_noop(
    mock_disc, mock_parse, mock_send, mock_art, tmp_path
):
    sp = tmp_path / "state.json"
    state.save_state(sp, slug="cur", date_iso=None, artwork_sent=False)
    mock_disc.return_value = ("cur", "https://phaneroo.org/devotion/cur/")
    mock_parse.return_value = _dev("cur", date_iso=None)  # still placeholder
    action = main.run(state_path=sp, token="TOK", chat_id="42")
    assert action == "noop"
    mock_send.assert_not_called()
    mock_art.assert_not_called()
    assert state.load_state(sp)["artwork_sent"] is False


@patch("phaneroo_bot.main.telegram.send_artwork")
@patch("phaneroo_bot.main.telegram.send_devotional")
@patch("phaneroo_bot.main.parser.parse_devotional")
@patch("phaneroo_bot.main.discover.discover")
def test_same_slug_already_complete_is_noop(
    mock_disc, mock_parse, mock_send, mock_art, tmp_path
):
    sp = tmp_path / "state.json"
    state.save_state(sp, slug="cur", date_iso="2026-06-03", artwork_sent=True)
    mock_disc.return_value = ("cur", "https://phaneroo.org/devotion/cur/")
    action = main.run(state_path=sp, token="TOK", chat_id="42")
    assert action == "noop"
    mock_parse.assert_not_called()  # done for the day; no need to re-fetch
    mock_send.assert_not_called()
    mock_art.assert_not_called()


@patch("phaneroo_bot.main.telegram.send_artwork")
@patch("phaneroo_bot.main.telegram.send_devotional")
@patch("phaneroo_bot.main.parser.parse_devotional")
@patch("phaneroo_bot.main.discover.discover")
def test_skips_when_discovered_date_is_older(
    mock_disc, mock_parse, mock_send, mock_art, tmp_path
):
    sp = tmp_path / "state.json"
    state.save_state(sp, slug="today-slug", date_iso="2026-06-01", artwork_sent=True)
    # A stale response surfaces an older (yesterday) devotional with a new slug.
    mock_disc.return_value = ("stale-old", "https://phaneroo.org/devotion/stale-old/")
    mock_parse.return_value = _dev("stale-old", date_iso="2026-05-25")
    action = main.run(state_path=sp, token="TOK", chat_id="42")
    assert action == "noop"
    mock_send.assert_not_called()
    mock_art.assert_not_called()
    assert state.load_state(sp)["last_slug"] == "today-slug"  # unchanged


@patch("phaneroo_bot.main.telegram.send_artwork")
@patch("phaneroo_bot.main.telegram.send_devotional", side_effect=RuntimeError("telegram down"))
@patch("phaneroo_bot.main.parser.parse_devotional")
@patch("phaneroo_bot.main.discover.discover")
def test_state_not_updated_when_send_fails(
    mock_disc, mock_parse, mock_send, mock_art, tmp_path
):
    sp = tmp_path / "state.json"
    state.save_state(sp, slug="old-slug", date_iso="2026-05-31", artwork_sent=True)
    mock_disc.return_value = ("new-one", "https://phaneroo.org/devotion/new-one/")
    mock_parse.return_value = _dev("new-one", date_iso="2026-06-01")
    with pytest.raises(RuntimeError):
        main.run(state_path=sp, token="TOK", chat_id="42")
    assert state.load_state(sp)["last_slug"] == "old-slug"  # unchanged


@patch("phaneroo_bot.main.telegram.send_artwork")
@patch("phaneroo_bot.main.telegram.send_devotional")
@patch("phaneroo_bot.main.parser.parse_devotional")
@patch("phaneroo_bot.main.discover.discover")
def test_legacy_state_without_artwork_flag_is_treated_complete(
    mock_disc, mock_parse, mock_send, mock_art, tmp_path
):
    # Pre-existing state files have no `artwork_sent`; a dated last_date means
    # that devotional was fully delivered, so the same slug should be a noop.
    sp = tmp_path / "state.json"
    sp.write_text('{"last_slug": "cur", "last_date": "2026-06-01"}')
    mock_disc.return_value = ("cur", "https://phaneroo.org/devotion/cur/")
    action = main.run(state_path=sp, token="TOK", chat_id="42")
    assert action == "noop"
    mock_send.assert_not_called()
    mock_art.assert_not_called()
