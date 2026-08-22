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


@patch("phaneroo_bot.fetcher.requests.get")
def test_get_json_tolerates_trailing_junk(mock_get):
    """The WP oEmbed endpoint intermittently appends output after the JSON body."""
    import requests as r
    resp = _resp(text='{"title": "T", "thumbnail_url": "https://x/i.png"}<!-- cached -->')
    resp.json.side_effect = r.exceptions.JSONDecodeError(
        "Extra data", resp.text, 49
    )
    mock_get.return_value = resp
    assert fetcher.get_json("https://x.test") == {
        "title": "T",
        "thumbnail_url": "https://x/i.png",
    }


@patch("phaneroo_bot.fetcher.requests.get")
def test_get_json_raises_when_body_is_not_json_at_all(mock_get):
    import requests as r
    resp = _resp(text="<html>blocked</html>")
    resp.json.side_effect = r.exceptions.JSONDecodeError(
        "Expecting value", resp.text, 0
    )
    mock_get.return_value = resp
    with pytest.raises(ValueError):
        fetcher.get_json("https://x.test")


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
