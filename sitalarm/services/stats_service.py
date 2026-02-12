from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sitalarm.services.storage import DailyStatsRow, PostureEventRow, Storage
from sitalarm.services.system_usage_service import get_system_screen_time_today


@dataclass(frozen=True)
class DaySummary:
    day: date
    correct_seconds: int
    incorrect_seconds: int
    unknown_seconds: int
    screen_seconds: int = 0


@dataclass(frozen=True)
class PostureRecord:
    captured_at: datetime
    status: str


class StatsService:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage


    def record_screen_usage(self, day: date, seconds: int) -> None:
        self.storage.increment_screen_usage(day, seconds)

    def get_day_screen_usage_seconds(self, day: date) -> int:
        return int(self.storage.get_screen_usage_seconds(day))

    def record_detection_start_if_missing(self, day: date, started_at: datetime) -> None:
        self.storage.set_detection_start_if_missing(day, started_at)

    def record_detection(self, day: date, status: str, interval_seconds: int) -> None:
        seconds = max(0, int(interval_seconds))
        correct = seconds if status == "correct" else 0
        incorrect = seconds if status == "incorrect" else 0
        unknown = seconds if status == "unknown" else 0
        self.storage.increment_daily_stats(day, correct, incorrect, unknown)

    def get_day_summary(self, day: date) -> DaySummary:
        row = self.storage.get_daily_stats(day)
        # Try to get system screen time first, fall back to app-based measurement
        screen_seconds = get_system_screen_time_today()
        if screen_seconds is None or screen_seconds == 0:
            screen_seconds = self.storage.get_screen_usage_seconds(day)
        return self._row_to_summary(row, screen_seconds)

    def get_last_days(self, days: int, today: date) -> list[DaySummary]:
        rows = self.storage.list_daily_stats(days=days, today=today)
        return [self._row_to_summary(row, self.storage.get_screen_usage_seconds(date.fromisoformat(row.date))) for row in rows]

    def get_today_detection_start(self, day: date) -> datetime | None:
        started_at = self.storage.get_detection_start(day)
        if not started_at:
            return None
        try:
            return datetime.fromisoformat(started_at)
        except ValueError:
            return None

    def get_posture_records(self, day: date, limit: int = 200) -> list[PostureRecord]:
        rows = self.storage.list_posture_events(day=day, limit=limit)
        return [self._row_to_record(row) for row in rows]

    @staticmethod
    def _row_to_summary(row: DailyStatsRow, screen_seconds: int = 0) -> DaySummary:
        return DaySummary(
            day=date.fromisoformat(row.date),
            correct_seconds=row.correct_seconds,
            incorrect_seconds=row.incorrect_seconds,
            unknown_seconds=row.unknown_seconds,
            screen_seconds=max(0, int(screen_seconds)),
        )

    @staticmethod
    def _row_to_record(row: PostureEventRow) -> PostureRecord:
        try:
            captured_at = datetime.fromisoformat(row.captured_at)
        except ValueError:
            captured_at = datetime.min
        return PostureRecord(captured_at=captured_at, status=row.status)
