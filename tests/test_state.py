import json
from phaneroo_bot import state


def test_load_returns_empty_when_missing(tmp_path):
    assert state.load_state(tmp_path / "state.json") == {}


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    state.save_state(path, slug="the-hidden-manna", date_iso="2026-05-31")
    st = state.load_state(path)
    assert st["last_slug"] == "the-hidden-manna"
    assert st["last_date"] == "2026-05-31"


def test_save_writes_timestamp(tmp_path):
    path = tmp_path / "state.json"
    state.save_state(path, slug="x", date_iso="2026-06-01")
    data = json.loads(path.read_text())
    assert data["last_slug"] == "x"
    assert data["last_sent_at"].endswith("+00:00") or "Z" in data["last_sent_at"]


def test_save_allows_missing_date(tmp_path):
    path = tmp_path / "state.json"
    state.save_state(path, slug="x")
    assert state.load_state(path)["last_date"] is None


def test_save_tracks_artwork_sent(tmp_path):
    path = tmp_path / "state.json"
    state.save_state(path, slug="x", date_iso=None, artwork_sent=False)
    assert state.load_state(path)["artwork_sent"] is False
    state.save_state(path, slug="x", date_iso="2026-06-03", artwork_sent=True)
    assert state.load_state(path)["artwork_sent"] is True


def test_artwork_sent_defaults_false(tmp_path):
    path = tmp_path / "state.json"
    state.save_state(path, slug="x", date_iso="2026-06-03")
    assert state.load_state(path)["artwork_sent"] is False


def test_load_handles_corrupt_file(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("not json{")
    assert state.load_state(path) == {}
