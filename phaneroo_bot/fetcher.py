"""HTTP layer: GET text/JSON with retries, timeout, and a real User-Agent."""
import time
import requests

USER_AGENT = (
    "Mozilla/5.0 (compatible; PhaneerooDevotionalBot/1.0; "
    "+https://github.com/SiphoYawe/pmi-devotional-bot)"
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
