"""HTTP layer: GET text/JSON with retries, timeout, and a real User-Agent."""
import json
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
    resp = _get(url, timeout=timeout, retries=retries)
    try:
        return resp.json()
    except ValueError:
        # The oEmbed endpoint intermittently appends output (cache footers,
        # plugin notices) after the JSON body, which trips strict parsing with
        # "Extra data". Decode the leading value and drop the trailing junk; a
        # body that is not JSON at all still raises.
        data, _ = json.JSONDecoder().raw_decode(resp.text.lstrip("﻿ \t\r\n"))
        return data
