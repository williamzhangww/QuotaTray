from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from codex_usage_monitor.app_paths import database_path
from codex_usage_monitor.models import UsageSnapshot

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SnapshotRecord:
    id: int | None
    captured_at: datetime
    plan: str | None
    selected_limit_id: str | None
    primary_used_percent: int | None
    primary_window_minutes: int | None
    primary_reset_at: datetime | None
    secondary_used_percent: int | None
    secondary_window_minutes: int | None
    secondary_reset_at: datetime | None
    reset_credit_count: int | None

    @property
    def secondary_window_identity(self) -> tuple[int, datetime] | None:
        if self.secondary_window_minutes is None or self.secondary_reset_at is None:
            return None
        return (self.secondary_window_minutes, self.secondary_reset_at)


class HistoryRepository:
    def __init__(
        self,
        db_path: str | Path | None = None,
        heartbeat_minutes: int = 45,
    ) -> None:
        self.db_path = Path(db_path) if db_path else default_database_path()
        self.heartbeat_minutes = heartbeat_minutes
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def insert_snapshot(self, usage: UsageSnapshot) -> bool:
        captured_at = _ensure_utc(usage.fetched_at or datetime.now(timezone.utc))
        candidate = SnapshotRecord(
            id=None,
            captured_at=captured_at,
            plan=usage.plan,
            selected_limit_id=usage.selected_limit_id,
            primary_used_percent=usage.primary.used_percent if usage.primary else None,
            primary_window_minutes=usage.primary.window_minutes if usage.primary else None,
            primary_reset_at=usage.primary.reset_at if usage.primary else None,
            secondary_used_percent=usage.secondary.used_percent if usage.secondary else None,
            secondary_window_minutes=usage.secondary.window_minutes if usage.secondary else None,
            secondary_reset_at=usage.secondary.reset_at if usage.secondary else None,
            reset_credit_count=usage.reset_credits.available_count
            if usage.reset_credits
            else None,
        )

        last = self.get_latest_snapshot()
        if last and _core_fields_equal(last, candidate):
            age = captured_at - last.captured_at
            if age < timedelta(minutes=self.heartbeat_minutes):
                return False

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO usage_snapshots (
                    captured_at,
                    plan,
                    selected_limit_id,
                    primary_used_percent,
                    primary_window_minutes,
                    primary_reset_at,
                    secondary_used_percent,
                    secondary_window_minutes,
                    secondary_reset_at,
                    reset_credit_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _dt_to_text(candidate.captured_at),
                    candidate.plan,
                    candidate.selected_limit_id,
                    candidate.primary_used_percent,
                    candidate.primary_window_minutes,
                    _dt_to_text(candidate.primary_reset_at),
                    candidate.secondary_used_percent,
                    candidate.secondary_window_minutes,
                    _dt_to_text(candidate.secondary_reset_at),
                    candidate.reset_credit_count,
                ),
            )
        return True

    def get_latest_snapshot(self) -> SnapshotRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM usage_snapshots ORDER BY captured_at DESC, id DESC LIMIT 1"
            ).fetchone()
        return _row_to_record(row) if row else None

    def list_snapshots(
        self,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> list[SnapshotRecord]:
        clauses = []
        params: list[str] = []
        if start_at is not None:
            clauses.append("captured_at >= ?")
            params.append(_dt_to_text(_ensure_utc(start_at)))
        if end_at is not None:
            clauses.append("captured_at < ?")
            params.append(_dt_to_text(_ensure_utc(end_at)))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM usage_snapshots {where} ORDER BY captured_at ASC, id ASC",
                params,
            ).fetchall()
        return [_row_to_record(row) for row in rows]

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER NOT NULL
                )
                """
            )
            row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
            if row is None:
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            elif int(row["version"]) != SCHEMA_VERSION:
                raise RuntimeError(
                    f"Unsupported database schema version: {row['version']}"
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    captured_at TEXT NOT NULL,
                    plan TEXT NULL,
                    selected_limit_id TEXT NULL,
                    primary_used_percent INTEGER NULL,
                    primary_window_minutes INTEGER NULL,
                    primary_reset_at TEXT NULL,
                    secondary_used_percent INTEGER NULL,
                    secondary_window_minutes INTEGER NULL,
                    secondary_reset_at TEXT NULL,
                    reset_credit_count INTEGER NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_usage_snapshots_captured_at
                ON usage_snapshots (captured_at)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


def default_database_path() -> Path:
    return database_path()


def _row_to_record(row: sqlite3.Row) -> SnapshotRecord:
    return SnapshotRecord(
        id=row["id"],
        captured_at=_text_to_dt(row["captured_at"]),
        plan=row["plan"],
        selected_limit_id=row["selected_limit_id"],
        primary_used_percent=row["primary_used_percent"],
        primary_window_minutes=row["primary_window_minutes"],
        primary_reset_at=_text_to_dt(row["primary_reset_at"]),
        secondary_used_percent=row["secondary_used_percent"],
        secondary_window_minutes=row["secondary_window_minutes"],
        secondary_reset_at=_text_to_dt(row["secondary_reset_at"]),
        reset_credit_count=row["reset_credit_count"],
    )


def _core_fields_equal(left: SnapshotRecord, right: SnapshotRecord) -> bool:
    return (
        left.primary_used_percent == right.primary_used_percent
        and left.primary_reset_at == right.primary_reset_at
        and left.secondary_used_percent == right.secondary_used_percent
        and left.secondary_reset_at == right.secondary_reset_at
        and left.reset_credit_count == right.reset_credit_count
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _dt_to_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _ensure_utc(value).isoformat().replace("+00:00", "Z")


def _text_to_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
