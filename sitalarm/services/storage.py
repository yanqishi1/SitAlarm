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
    correct_seconds: int
    incorrect_seconds: int
    unknown_seconds: int


@dataclass
class PostureEventRow:
    captured_at: str
    status: str
    reasons: tuple[str, ...]
    image_path: str
    confidence: float | None

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
                    correct_seconds INTEGER NOT NULL DEFAULT 0,
                    incorrect_seconds INTEGER NOT NULL DEFAULT 0,
                    unknown_seconds INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS screen_usage_stats (
                    date TEXT PRIMARY KEY,
                    screen_seconds INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                """
            )
            # Migration: older versions used *_minutes columns. Keep them if they exist,
            # but prefer *_seconds going forward.
            self._migrate_daily_stats_minutes_to_seconds(conn)

    @staticmethod
    def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return any(str(row["name"]) == column for row in rows)

    def _migrate_daily_stats_minutes_to_seconds(self, conn: sqlite3.Connection) -> None:
        # If the legacy columns exist, copy minutes -> seconds once.
        if not self._column_exists(conn, "daily_stats", "correct_minutes"):
            return
        if not self._column_exists(conn, "daily_stats", "correct_seconds"):
            # In case daily_stats table was created by old code and lacks seconds columns.
            conn.execute("ALTER TABLE daily_stats ADD COLUMN correct_seconds INTEGER NOT NULL DEFAULT 0")
            conn.execute("ALTER TABLE daily_stats ADD COLUMN incorrect_seconds INTEGER NOT NULL DEFAULT 0")
            conn.execute("ALTER TABLE daily_stats ADD COLUMN unknown_seconds INTEGER NOT NULL DEFAULT 0")

        # Only migrate rows that haven't been migrated.
        conn.execute(
            """
            UPDATE daily_stats
            SET
                correct_seconds = CASE WHEN correct_seconds = 0 THEN correct_minutes * 60 ELSE correct_seconds END,
                incorrect_seconds = CASE WHEN incorrect_seconds = 0 THEN incorrect_minutes * 60 ELSE incorrect_seconds END,
                unknown_seconds = CASE WHEN unknown_seconds = 0 THEN unknown_minutes * 60 ELSE unknown_seconds END
            WHERE (correct_minutes != 0 OR incorrect_minutes != 0 OR unknown_minutes != 0)
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
                INSERT INTO daily_stats(date, correct_seconds, incorrect_seconds, unknown_seconds, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    correct_seconds = correct_seconds + excluded.correct_seconds,
                    incorrect_seconds = incorrect_seconds + excluded.incorrect_seconds,
                    unknown_seconds = unknown_seconds + excluded.unknown_seconds,
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
                SELECT date, correct_seconds, incorrect_seconds, unknown_seconds
                FROM daily_stats
                WHERE date BETWEEN ? AND ?
                ORDER BY date ASC
                """,
                (start_day.isoformat(), today.isoformat()),
            ).fetchall()

        by_date = {
            row["date"]: DailyStatsRow(
                date=str(row["date"]),
                correct_seconds=int(row["correct_seconds"]),
                incorrect_seconds=int(row["incorrect_seconds"]),
                unknown_seconds=int(row["unknown_seconds"]),
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

    def list_posture_events(self, day: date | None = None, limit: int = 200) -> list[PostureEventRow]:
        params: tuple[object, ...]
        sql = (
            "SELECT captured_at, status, reasons, image_path, confidence "
            "FROM posture_events"
        )
        if day is not None:
            start = datetime.combine(day, datetime.min.time()).isoformat()
            end = datetime.combine(day, datetime.max.time()).isoformat()
            sql += " WHERE captured_at BETWEEN ? AND ?"
            params = (start, end)
        else:
            params = ()

        sql += " ORDER BY captured_at DESC LIMIT ?"
        params = (*params, max(1, int(limit)))

        with self._lock, self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        events: list[PostureEventRow] = []
        for row in rows:
            reasons_raw = str(row["reasons"])
            try:
                parsed_reasons = json.loads(reasons_raw)
                reasons = tuple(str(item) for item in parsed_reasons)
            except Exception:
                reasons = ()

            confidence = row["confidence"]
            events.append(
                PostureEventRow(
                    captured_at=str(row["captured_at"]),
                    status=str(row["status"]),
                    reasons=reasons,
                    image_path=str(row["image_path"]),
                    confidence=float(confidence) if confidence is not None else None,
                )
            )
        return events


    def increment_screen_usage(self, day: date, screen_delta: int) -> None:
        seconds = max(0, int(screen_delta))
        if seconds <= 0:
            return
        day_key = day.isoformat()
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO screen_usage_stats(date, screen_seconds, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    screen_seconds = screen_seconds + excluded.screen_seconds,
                    updated_at = excluded.updated_at
                """,
                (day_key, seconds, now),
            )

    def get_screen_usage_seconds(self, day: date) -> int:
        day_key = day.isoformat()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT screen_seconds FROM screen_usage_stats WHERE date = ?",
                (day_key,),
            ).fetchone()
        if row is None:
            return 0
        return int(row["screen_seconds"])

    def set_detection_start_if_missing(self, day: date, started_at: datetime) -> None:
        key = f"detection_start:{day.isoformat()}"
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            existing = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            if existing is not None:
                return
            conn.execute(
                """
                INSERT INTO settings(key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, started_at.isoformat(), now),
            )

    def get_detection_start(self, day: date) -> str | None:
        key = f"detection_start:{day.isoformat()}"
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        return str(row["value"])

    def get_first_posture_event_time(self, day: date) -> str | None:
        start = datetime.combine(day, datetime.min.time()).isoformat()
        end = datetime.combine(day, datetime.max.time()).isoformat()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT captured_at
                FROM posture_events
                WHERE captured_at BETWEEN ? AND ?
                ORDER BY captured_at ASC
                LIMIT 1
                """,
                (start, end),
            ).fetchone()

        if row is None:
            return None
        return str(row["captured_at"])

    def _get_daily_stats_row(self, key: str) -> DailyStatsRow | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT date, correct_seconds, incorrect_seconds, unknown_seconds
                FROM daily_stats
                WHERE date = ?
                """,
                (key,),
            ).fetchone()
        if row is None:
            return None
        return DailyStatsRow(
            date=str(row["date"]),
            correct_seconds=int(row["correct_seconds"]),
            incorrect_seconds=int(row["incorrect_seconds"]),
            unknown_seconds=int(row["unknown_seconds"]),
        )
