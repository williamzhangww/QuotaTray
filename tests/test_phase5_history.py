from datetime import datetime, timedelta, timezone

from codex_usage_monitor.models import RateLimitResetCredits, UsageSnapshot, UsageWindow
from codex_usage_monitor.services import AnalyticsService
from codex_usage_monitor.storage import HistoryRepository


def make_usage(
    captured_at: datetime,
    secondary_used: int | None,
    secondary_reset_at: datetime | None,
    secondary_minutes: int | None = 10080,
) -> UsageSnapshot:
    return UsageSnapshot(
        plan="plus",
        selected_limit_id="codex",
        secondary=UsageWindow(secondary_used, secondary_minutes, secondary_reset_at)
        if secondary_used is not None
        else None,
        reset_credits=RateLimitResetCredits(1, ()),
        fetched_at=captured_at.astimezone(timezone.utc),
    )


def local_dt(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute).astimezone()


def test_daily_history_returns_last_seven_local_days(tmp_path) -> None:
    repo = HistoryRepository(tmp_path / "usage.db")
    service = AnalyticsService(repo)
    reset = local_dt(2026, 8, 27, 10).astimezone(timezone.utc)

    start = local_dt(2026, 8, 20, 0, 5)
    for day_index in range(7):
        day = start + timedelta(days=day_index)
        repo.insert_snapshot(make_usage(day, day_index * 5, reset))
        repo.insert_snapshot(make_usage(day + timedelta(hours=12), day_index * 5 + 3, reset))

    history = service.daily_history(days=7, now=local_dt(2026, 8, 26, 13))

    assert len(history) == 7
    assert history[0].label == "Thu"
    assert history[-2].label == "Yesterday"
    assert history[-1].label == "Today"
    assert [day.consumed_pp for day in history] == [3, 3, 3, 3, 3, 3, 3]


def test_daily_history_marks_partial_day_since_first_observation(tmp_path) -> None:
    repo = HistoryRepository(tmp_path / "usage.db")
    service = AnalyticsService(repo)
    reset = local_dt(2026, 8, 27, 10).astimezone(timezone.utc)

    repo.insert_snapshot(make_usage(local_dt(2026, 8, 26, 9, 30), 20, reset))
    repo.insert_snapshot(make_usage(local_dt(2026, 8, 26, 11, 30), 23, reset))

    today = service.daily_history(days=1, now=local_dt(2026, 8, 26, 12))[0]

    assert today.label == "Today"
    assert today.consumed_pp == 3
    assert today.complete is False
    assert today.since is not None
