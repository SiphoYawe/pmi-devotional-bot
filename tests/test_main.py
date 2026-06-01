from unittest.mock import patch
import pytest
from phaneroo_bot import main, state
from phaneroo_bot.parser import Devotional


def _dev(slug="new-one", date_iso="2026-06-01"):
    return Devotional(
        slug=slug, url=f"https://phaneroo.org/devotion/{slug}/", title="T",
        author="A", scripture="John 3:16", body=["Body."], image_url=None,
        date="1 June 2026", date_iso=date_iso,
    )


@patch("phaneroo_bot.main.telegram.send_devotional")
@patch("phaneroo_bot.main.parser.parse_devotional")
@patch("phaneroo_bot.main.discover.discover")
def test_bootstrap_records_without_sending(mock_disc, mock_parse, mock_send, tmp_path):
    sp = tmp_path / "state.json"
    mock_disc.return_value = ("today-slug", "https://phaneroo.org/devotion/today-slug/")
    mock_parse.return_value = _dev("today-slug")
    action = main.run(state_path=sp, token="TOK", chat_id="42")
    assert action == "bootstrapped"
    mock_send.assert_not_called()
    assert state.load_state(sp)["last_slug"] == "today-slug"


@patch("phaneroo_bot.main.telegram.send_devotional")
@patch("phaneroo_bot.main.parser.parse_devotional")
@patch("phaneroo_bot.main.discover.discover")
def test_noop_when_slug_unchanged(mock_disc, mock_parse, mock_send, tmp_path):
    sp = tmp_path / "state.json"
    state.save_state(sp, slug="same-slug", date_iso="2026-05-31")
    mock_disc.return_value = ("same-slug", "https://phaneroo.org/devotion/same-slug/")
    action = main.run(state_path=sp, token="TOK", chat_id="42")
    assert action == "noop"
    mock_send.assert_not_called()


@patch("phaneroo_bot.main.telegram.send_devotional")
@patch("phaneroo_bot.main.parser.parse_devotional")
@patch("phaneroo_bot.main.discover.discover")
def test_sends_on_new_slug_and_updates_state(mock_disc, mock_parse, mock_send, tmp_path):
    sp = tmp_path / "state.json"
    state.save_state(sp, slug="old-slug", date_iso="2026-05-31")
    mock_disc.return_value = ("new-one", "https://phaneroo.org/devotion/new-one/")
    mock_parse.return_value = _dev("new-one", date_iso="2026-06-01")
    action = main.run(state_path=sp, token="TOK", chat_id="42")
    assert action == "sent"
    mock_send.assert_called_once()
    assert state.load_state(sp)["last_slug"] == "new-one"
    assert state.load_state(sp)["last_date"] == "2026-06-01"


@patch("phaneroo_bot.main.telegram.send_devotional")
@patch("phaneroo_bot.main.parser.parse_devotional")
@patch("phaneroo_bot.main.discover.discover")
def test_skips_when_discovered_date_is_older(mock_disc, mock_parse, mock_send, tmp_path):
    sp = tmp_path / "state.json"
    state.save_state(sp, slug="today-slug", date_iso="2026-06-01")
    # A stale response surfaces an older (yesterday) devotional with a new slug.
    mock_disc.return_value = ("stale-old", "https://phaneroo.org/devotion/stale-old/")
    mock_parse.return_value = _dev("stale-old", date_iso="2026-05-25")
    action = main.run(state_path=sp, token="TOK", chat_id="42")
    assert action == "noop"
    mock_send.assert_not_called()
    assert state.load_state(sp)["last_slug"] == "today-slug"  # unchanged


@patch("phaneroo_bot.main.telegram.send_devotional", side_effect=RuntimeError("telegram down"))
@patch("phaneroo_bot.main.parser.parse_devotional")
@patch("phaneroo_bot.main.discover.discover")
def test_state_not_updated_when_send_fails(mock_disc, mock_parse, mock_send, tmp_path):
    sp = tmp_path / "state.json"
    state.save_state(sp, slug="old-slug", date_iso="2026-05-31")
    mock_disc.return_value = ("new-one", "https://phaneroo.org/devotion/new-one/")
    mock_parse.return_value = _dev("new-one", date_iso="2026-06-01")
    with pytest.raises(RuntimeError):
        main.run(state_path=sp, token="TOK", chat_id="42")
    assert state.load_state(sp)["last_slug"] == "old-slug"  # unchanged
