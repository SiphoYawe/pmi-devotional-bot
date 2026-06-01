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
