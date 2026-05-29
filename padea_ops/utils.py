from __future__ import annotations
from datetime import date, datetime, timedelta
from pathlib import Path
import re

def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()

def date_window(start: date, days: int) -> tuple[date, date]:
    return start, start + timedelta(days=days - 1)

def iso_now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()

def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_")

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path

def boolish(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"true", "t", "yes", "y", "1", "active"}
