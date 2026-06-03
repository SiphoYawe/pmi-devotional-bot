"""Persist what we last sent (slug + date), committed back by the workflow."""
import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = Path("state.json")


def load_state(path: Path = DEFAULT_PATH) -> dict:
    """Return the stored state dict, or {} if missing/corrupt."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def save_state(
    path: Path, *, slug: str, date_iso: str | None = None, artwork_sent: bool = False
) -> None:
    path = Path(path)
    data = {
        "last_slug": slug,
        "last_date": date_iso,
        "artwork_sent": artwork_sent,
        "last_sent_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
