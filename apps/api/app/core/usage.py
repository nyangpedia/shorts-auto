"""Counts our own free-tier API calls per provider day. Providers don't expose remaining quota,
so this is an estimate shown in the UI, not a guard."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

USAGE_FILE = "_usage.json"
# ponytail: fixed UTC-8 ignores daylight saving (resets an hour early in summer); use zoneinfo+tzdata if that matters.
_RESET_OFFSET = {"llm": timedelta(hours=-8), "tts": timedelta(hours=-8), "image": timedelta(0)}

_lock = threading.Lock()
_path: Path | None = None


def configure(outputs_dir: Path) -> None:
    global _path
    _path = outputs_dir / USAGE_FILE


def _day(kind: str) -> str:
    return (datetime.now(timezone.utc) + _RESET_OFFSET[kind]).date().isoformat()


def _load() -> dict:
    try:
        return json.loads(_path.read_text(encoding="utf-8")) if _path and _path.exists() else {}
    except (OSError, ValueError):
        return {}


def record(kind: str) -> None:
    if _path is None:
        return
    with _lock:
        data = _load()
        day = _day(kind)
        counts = data.get(kind, {})
        data[kind] = {day: counts.get(day, 0) + 1}  # keep only the current day
        _path.write_text(json.dumps(data), encoding="utf-8")


def today() -> dict[str, int]:
    data = _load()
    return {kind: data.get(kind, {}).get(_day(kind), 0) for kind in _RESET_OFFSET}
