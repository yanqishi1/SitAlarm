from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Generator, Iterable


@dataclass
class DailyStatsRow:
    date: str
    correct_minutes: int
    incorrect_minutes: int
    unknown_minutes: int


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._init_schema()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS posture_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    captured_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reasons TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    confidence REAL
                );

                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT PRIMARY KEY,
                    correct_minutes INTEGER NOT NULL DEFAULT 0,
                    incorrect_minutes INTEGER NOT NULL DEFAULT 0,
                    unknown_minutes INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def list_tables(self) -> set[str]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        return {row["name"] for row in rows}

    def get_setting(self, key: str) -> str | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        return str(row["value"])

    def set_setting(self, key: str, value: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO settings(key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )

    def all_settings(self) -> dict[str, str]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {str(row["key"]): str(row["value"]) for row in rows}

    def insert_posture_event(
        self,
        captured_at: datetime,
        status: str,
        reasons: Iterable[str],
        image_path: Path,
        confidence: float | None,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO posture_events(captured_at, status, reasons, image_path, confidence)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    captured_at.isoformat(),
                    status,
                    json.dumps(list(reasons), ensure_ascii=True),
                    str(image_path),
                    confidence,
                ),
            )

    def increment_daily_stats(
        self,
        day: date,
        correct_delta: int,
        incorrect_delta: int,
        unknown_delta: int,
    ) -> None:
        day_key = day.isoformat()
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO daily_stats(date, correct_minutes, incorrect_minutes, unknown_minutes, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    correct_minutes = correct_minutes + excluded.correct_minutes,
                    incorrect_minutes = incorrect_minutes + excluded.incorrect_minutes,
                    unknown_minutes = unknown_minutes + excluded.unknown_minutes,
                    updated_at = excluded.updated_at
                """,
                (day_key, correct_delta, incorrect_delta, unknown_delta, now),
            )

    def get_daily_stats(self, day: date) -> DailyStatsRow:
        row = self._get_daily_stats_row(day.isoformat())
        if row is None:
            return DailyStatsRow(day.isoformat(), 0, 0, 0)
        return row

    def list_daily_stats(self, days: int, today: date) -> list[DailyStatsRow]:
        start_day = today.fromordinal(today.toordinal() - (days - 1))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT date, correct_minutes, incorrect_minutes, unknown_minutes
                FROM daily_stats
                WHERE date BETWEEN ? AND ?
                ORDER BY date ASC
                """,
                (start_day.isoformat(), today.isoformat()),
            ).fetchall()

        by_date = {
            row["date"]: DailyStatsRow(
                date=str(row["date"]),
                correct_minutes=int(row["correct_minutes"]),
                incorrect_minutes=int(row["incorrect_minutes"]),
                unknown_minutes=int(row["unknown_minutes"]),
            )
            for row in rows
        }
        result: list[DailyStatsRow] = []
        cursor = start_day
        for _ in range(days):
            key = cursor.isoformat()
            result.append(by_date.get(key, DailyStatsRow(key, 0, 0, 0)))
            cursor = cursor.fromordinal(cursor.toordinal() + 1)
        return result

    def _get_daily_stats_row(self, key: str) -> DailyStatsRow | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT date, correct_minutes, incorrect_minutes, unknown_minutes
                FROM daily_stats
                WHERE date = ?
                """,
                (key,),
            ).fetchone()
        if row is None:
            return None
        return DailyStatsRow(
            date=str(row["date"]),
            correct_minutes=int(row["correct_minutes"]),
            incorrect_minutes=int(row["incorrect_minutes"]),
            unknown_minutes=int(row["unknown_minutes"]),
        )
