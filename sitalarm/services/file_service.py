from __future__ import annotations

import shutil
from datetime import date, timedelta
from pathlib import Path


def ensure_day_capture_dir(base_dir: Path, target_day: date) -> Path:
    path = base_dir / target_day.isoformat()
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_old_capture_dirs(base_dir: Path, keep_days: int, today: date) -> list[str]:
    if not base_dir.exists():
        return []

    cutoff = today - timedelta(days=max(1, keep_days))
    removed: list[str] = []
    for child in base_dir.iterdir():
        if not child.is_dir():
            continue
        try:
            folder_day = date.fromisoformat(child.name)
        except ValueError:
            continue

        if folder_day < cutoff:
            shutil.rmtree(child, ignore_errors=True)
            removed.append(str(child))
    return removed
