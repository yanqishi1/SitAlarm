from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

APP_NAME = "SitAlarm"


@dataclass(frozen=True)
class AppSettings:
    capture_interval_minutes: int = 5
    reminder_cooldown_minutes: int = 3
    screen_time_enabled: bool = False
    screen_time_threshold_minutes: int = 60
    retention_days: int = 7
    head_ratio_threshold: float = 0.0


DEFAULT_SETTINGS = AppSettings()


def get_capture_base_dir() -> Path:
    return Path.home() / "Pictures" / APP_NAME


def get_day_capture_dir(target_day: date) -> Path:
    return get_capture_base_dir() / target_day.isoformat()


def get_database_path() -> Path:
    return Path.home() / ".sitalarm" / "sitalarm.db"
