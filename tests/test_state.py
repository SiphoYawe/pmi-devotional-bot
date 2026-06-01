import json
from phaneroo_bot import state


def test_load_returns_none_when_missing(tmp_path):
    assert state.load_last_slug(tmp_path / "state.json") is None


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    state.save_last_slug(path, "the-hidden-manna")
    assert state.load_last_slug(path) == "the-hidden-manna"


def test_save_writes_timestamp(tmp_path):
    path = tmp_path / "state.json"
    state.save_last_slug(path, "x")
    data = json.loads(path.read_text())
    assert data["last_slug"] == "x"
    assert data["last_sent_at"].endswith("+00:00") or "Z" in data["last_sent_at"]


def test_load_handles_corrupt_file(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("not json{")
    assert state.load_last_slug(path) is None
