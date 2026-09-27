from datetime import datetime, timedelta, timezone

from codex_usage_monitor.models import RateLimitResetCredits, UsageSnapshot, UsageWindow
from codex_usage_monitor.services import AnalyticsService
from codex_usage_monitor.storage import HistoryRepository


def make_usage(
    captured_at: datetime,
    secondary_used: int | None,
    secondary_reset_at: datetime | None,
    secondary_minutes: int | None = 10080,
    reset_credits: int | None = 1,
) -> UsageSnapshot:
    return UsageSnapshot(
        plan="plus",
        selected_limit_id="codex",
        secondary=UsageWindow(secondary_used, secondary_minutes, secondary_reset_at)
        if secondary_used is not None
        else None,
        reset_credits=RateLimitResetCredits(reset_credits, ()) if reset_credits is not None else None,
        fetched_at=captured_at.astimezone(timezone.utc),
    )


def local_dt(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute).astimezone()


def test_today_usage_since_first_snapshot(tmp_path) -> None:
    repo = HistoryRepository(tmp_path / "usage.db")
    service = AnalyticsService(repo)
    reset = local_dt(2026, 9, 1, 10).astimezone(timezone.utc)

    repo.insert_snapshot(make_usage(local_dt(2026, 8, 26, 9, 32), 12, reset))
    repo.insert_snapshot(make_usage(local_dt(2026, 8, 26, 13, 0), 16, reset))

    analytics = service.build_snapshot(now=local_dt(2026, 8, 26, 13, 1))

    assert analytics.today.consumed_pp == 4
    assert analytics.today.since is not None
    assert analytics.today.complete is False


def test_yesterday_usage_and_comparison_when_covered(tmp_path) -> None:
    repo = HistoryRepository(tmp_path / "usage.db")
    service = AnalyticsService(repo)
    reset = local_dt(2026, 8, 31, 10).astimezone(timezone.utc)

    repo.insert_snapshot(make_usage(local_dt(2026, 8, 25, 0, 5), 10, reset))
    repo.insert_snapshot(make_usage(local_dt(2026, 8, 25, 23, 0), 21, reset))
    repo.insert_snapshot(make_usage(local_dt(2026, 8, 26, 0, 5), 21, reset))
    repo.insert_snapshot(make_usage(local_dt(2026, 8, 26, 12, 0), 27, reset))

    analytics = service.build_snapshot(now=local_dt(2026, 8, 26, 12, 1))

    assert analytics.yesterday.consumed_pp == 11
    assert analytics.today.consumed_pp == 6
    assert analytics.today_vs_yesterday_percent == -45


def test_insufficient_history(tmp_path) -> None:
    repo = HistoryRepository(tmp_path / "usage.db")
    service = AnalyticsService(repo)
    reset = local_dt(2026, 9, 1, 10).astimezone(timezone.utc)

    repo.insert_snapshot(make_usage(local_dt(2026, 8, 26, 10, 0), 12, reset))

    analytics = service.build_snapshot(now=local_dt(2026, 8, 26, 12, 0))

    assert analytics.today.consumed_pp is None
    assert analytics.today.reason == "Not enough history"


def test_weekly_reset_is_new_window_not_negative_usage(tmp_path) -> None:
    repo = HistoryRepository(tmp_path / "usage.db")
    service = AnalyticsService(repo)
    old_reset = local_dt(2026, 8, 26, 1).astimezone(timezone.utc)
    new_reset = local_dt(2026, 9, 2, 1).astimezone(timezone.utc)

    repo.insert_snapshot(make_usage(local_dt(2026, 8, 26, 0, 30), 94, old_reset))
    repo.insert_snapshot(make_usage(local_dt(2026, 8, 26, 1, 30), 2, new_reset))

    analytics = service.build_snapshot(now=local_dt(2026, 8, 26, 2, 0))

    assert analytics.today.consumed_pp == 2


def test_burn_rate_and_projected_usage(tmp_path) -> None:
    repo = HistoryRepository(tmp_path / "usage.db")
    service = AnalyticsService(repo)
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    reset = now + timedelta(days=3, hours=12)
    usage = make_usage(now, 40, reset)

    analytics = service.build_snapshot(usage, now=now)

    assert analytics.burn.burn_rate is not None
    assert round(analytics.burn.burn_rate, 2) == 0.80
    assert analytics.burn.projected_usage_percent == 80
    assert analytics.burn.status == "SAFE"


def test_projected_limit_hit_estimate(tmp_path) -> None:
    repo = HistoryRepository(tmp_path / "usage.db")
    service = AnalyticsService(repo)
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    reset = now + timedelta(days=3, hours=12)
    usage = make_usage(now, 80, reset)

    analytics = service.build_snapshot(usage, now=now)

    assert analytics.burn.projected_usage_percent == 160
    assert analytics.burn.status == "HIGH"
    assert analytics.burn.estimated_limit_hit_at is not None


def test_window_just_started_has_no_projection(tmp_path) -> None:
    repo = HistoryRepository(tmp_path / "usage.db")
    service = AnalyticsService(repo, minimum_burn_elapsed_minutes=30)
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    reset = now + timedelta(minutes=10070)
    usage = make_usage(now, 2, reset)

    analytics = service.build_snapshot(usage, now=now)

    assert analytics.burn.burn_rate is None
    assert analytics.burn.reason == "Collecting data"


def test_timezone_local_day_boundary(tmp_path) -> None:
    repo = HistoryRepository(tmp_path / "usage.db")
    service = AnalyticsService(repo)
    reset = local_dt(2026, 9, 1, 10).astimezone(timezone.utc)

    repo.insert_snapshot(make_usage(local_dt(2026, 8, 25, 23, 55), 10, reset))
    repo.insert_snapshot(make_usage(local_dt(2026, 8, 26, 0, 5), 11, reset))
    repo.insert_snapshot(make_usage(local_dt(2026, 8, 26, 1, 0), 12, reset))

    analytics = service.build_snapshot(now=local_dt(2026, 8, 26, 1, 5))

    assert analytics.today.consumed_pp == 1
    assert analytics.today.complete is True


def test_missing_secondary_window(tmp_path) -> None:
    repo = HistoryRepository(tmp_path / "usage.db")
    service = AnalyticsService(repo)
    usage = make_usage(datetime(2026, 8, 26, 12, tzinfo=timezone.utc), None, None)

    analytics = service.build_snapshot(usage, now=datetime(2026, 8, 26, 12, tzinfo=timezone.utc))

    assert analytics.burn.burn_rate is None
    assert analytics.today.consumed_pp is None


def test_optional_reset_credits_missing_can_be_inserted(tmp_path) -> None:
    repo = HistoryRepository(tmp_path / "usage.db")
    reset = datetime(2026, 9, 2, 10, tzinfo=timezone.utc)
    usage = make_usage(datetime(2026, 8, 26, 10, tzinfo=timezone.utc), 4, reset, reset_credits=None)

    assert repo.insert_snapshot(usage) is True
    latest = repo.get_latest_snapshot()
    assert latest is not None
    assert latest.reset_credit_count is None
