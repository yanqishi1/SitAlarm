from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sitalarm.services.storage import DailyStatsRow, Storage


@dataclass(frozen=True)
class DaySummary:
    day: date
    correct_seconds: int
    incorrect_seconds: int
    unknown_seconds: int


class StatsService:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def record_detection(self, day: date, status: str, interval_seconds: int) -> None:
        seconds = max(0, int(interval_seconds))
        correct = seconds if status == "correct" else 0
        incorrect = seconds if status == "incorrect" else 0
        unknown = seconds if status == "unknown" else 0
        self.storage.increment_daily_stats(day, correct, incorrect, unknown)

    def get_day_summary(self, day: date) -> DaySummary:
        row = self.storage.get_daily_stats(day)
        return self._row_to_summary(row)

    def get_last_days(self, days: int, today: date) -> list[DaySummary]:
        rows = self.storage.list_daily_stats(days=days, today=today)
        return [self._row_to_summary(row) for row in rows]

    @staticmethod
    def _row_to_summary(row: DailyStatsRow) -> DaySummary:
        return DaySummary(
            day=date.fromisoformat(row.date),
            correct_seconds=row.correct_seconds,
            incorrect_seconds=row.incorrect_seconds,
            unknown_seconds=row.unknown_seconds,
        )
