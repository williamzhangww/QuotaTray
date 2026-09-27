from datetime import datetime, timedelta, timezone

from codex_usage_monitor.models import RateLimitResetCredits, UsageSnapshot, UsageWindow
from codex_usage_monitor.storage import HistoryRepository


def snapshot(
    captured_at: datetime,
    primary_used: int | None = 10,
    primary_reset_at: datetime | None = None,
    secondary_used: int | None = 20,
    secondary_reset_at: datetime | None = None,
    reset_credits: int | None = 1,
) -> UsageSnapshot:
    return UsageSnapshot(
        plan="plus",
        selected_limit_id="codex",
        primary=UsageWindow(primary_used, 300, primary_reset_at),
        secondary=UsageWindow(secondary_used, 10080, secondary_reset_at),
        reset_credits=RateLimitResetCredits(reset_credits, ()) if reset_credits is not None else None,
        fetched_at=captured_at,
    )


def test_sqlite_initialization(tmp_path) -> None:
    repo = HistoryRepository(tmp_path / "usage.db")

    assert repo.db_path.is_file()
    assert repo.list_snapshots() == []


def test_snapshot_insert_and_read(tmp_path) -> None:
    repo = HistoryRepository(tmp_path / "usage.db")
    captured = datetime(2026, 8, 26, 10, tzinfo=timezone.utc)
    reset = datetime(2026, 9, 2, 10, tzinfo=timezone.utc)

    assert repo.insert_snapshot(snapshot(captured, secondary_reset_at=reset)) is True
    latest = repo.get_latest_snapshot()

    assert latest is not None
    assert latest.plan == "plus"
    assert latest.secondary_used_percent == 20
    assert latest.secondary_reset_at == reset


def test_duplicate_suppression_keeps_heartbeat(tmp_path) -> None:
    repo = HistoryRepository(tmp_path / "usage.db", heartbeat_minutes=45)
    reset = datetime(2026, 9, 2, 10, tzinfo=timezone.utc)
    first = datetime(2026, 8, 26, 10, tzinfo=timezone.utc)

    assert repo.insert_snapshot(snapshot(first, secondary_reset_at=reset)) is True
    assert repo.insert_snapshot(snapshot(first + timedelta(minutes=5), secondary_reset_at=reset)) is False
    assert repo.insert_snapshot(snapshot(first + timedelta(minutes=46), secondary_reset_at=reset)) is True

    assert len(repo.list_snapshots()) == 2


def test_duplicate_suppression_inserts_changed_core_fields(tmp_path) -> None:
    repo = HistoryRepository(tmp_path / "usage.db")
    reset = datetime(2026, 9, 2, 10, tzinfo=timezone.utc)
    first = datetime(2026, 8, 26, 10, tzinfo=timezone.utc)

    assert repo.insert_snapshot(snapshot(first, secondary_used=20, secondary_reset_at=reset)) is True
    assert repo.insert_snapshot(
        snapshot(first + timedelta(minutes=5), secondary_used=21, secondary_reset_at=reset)
    ) is True

    assert len(repo.list_snapshots()) == 2
