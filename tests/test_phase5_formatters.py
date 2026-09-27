from datetime import datetime, timedelta, timezone

from codex_usage_monitor.models import (
    AnalyticsSnapshot,
    BurnAnalysis,
    DailyQuotaUsage,
    RateLimitResetCredit,
    RateLimitResetCredits,
    UsageSnapshot,
    UsageWindow,
)
from codex_usage_monitor.ui.formatters import (
    build_limit_widget_view,
    build_details_view_model,
    build_usage_widget_view,
    format_burn,
    format_daily_usage,
    format_reset_countdown,
    reset_credit_visible,
    update_status,
)


def test_update_status_is_fresh_with_recent_success() -> None:
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    status = update_status(now - timedelta(minutes=3), 5, now=now)

    assert status.text == "Updated 3m ago"
    assert status.is_stale is False


def test_update_status_is_stale_after_two_refresh_intervals() -> None:
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    status = update_status(now - timedelta(minutes=11), 5, now=now)

    assert status.is_stale is True
    assert status.text.startswith("Data may be stale")


def test_update_status_marks_refresh_failure() -> None:
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    status = update_status(now - timedelta(minutes=1), 5, refresh_failed=True, now=now)

    assert status.is_stale is True
    assert status.text == "Update failed · showing last known data"


def test_reset_credit_visibility_respects_setting_and_availability() -> None:
    usage = UsageSnapshot(reset_credits=RateLimitResetCredits(1, ()))

    assert reset_credit_visible(usage, True) is True
    assert reset_credit_visible(usage, False) is False
    assert reset_credit_visible(UsageSnapshot(reset_credits=RateLimitResetCredits(0, ())), True) is False


def test_daily_and_burn_formatters() -> None:
    since = datetime(2026, 8, 26, 9, 30, tzinfo=timezone.utc)
    assert (
        format_daily_usage(DailyQuotaUsage("Today", consumed_pp=4, since=since))
        == "4% of weekly quota used today since 12:30"
    )
    assert format_burn(BurnAnalysis(0.76, 76, None, "SAFE")) == "0.76x SAFE · projected 76%"


def test_widget_view_model_no_longer_contains_today_or_burn_display() -> None:
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    usage = UsageSnapshot(
        primary=UsageWindow(56, 300, now + timedelta(hours=3, minutes=33)),
        secondary=UsageWindow(24, 10080, now + timedelta(days=6, hours=17)),
        reset_credits=RateLimitResetCredits(0, ()),
    )
    view = build_usage_widget_view(usage, True, 5, now, now=now)

    assert not hasattr(view, "today")
    assert not hasattr(view, "burn")
    text = " ".join(
        [
            view.primary.label,
            view.primary.percent_text,
            view.primary.reset_text,
            view.secondary.label,
            view.secondary.percent_text,
            view.secondary.reset_text,
            view.update_status.text,
            view.reset_credit_text,
        ]
    )
    assert "TODAY" not in text
    assert "BURN" not in text
    assert "SAFE" not in text
    assert "WATCH" not in text
    assert "HIGH" not in text


def test_reset_countdown_copy() -> None:
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)

    assert format_reset_countdown(now + timedelta(hours=3, minutes=42), now) == "Resets in 3h 42m"
    assert format_reset_countdown(now + timedelta(days=6, hours=15), now) == "Resets in 6d 15h"
    assert format_reset_countdown(None, now) == "Reset time unavailable"


def test_widget_limit_formatters() -> None:
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)

    five_hour = build_limit_widget_view("5 HOUR", UsageWindow(56, 300, now + timedelta(hours=3, minutes=33)), now)
    weekly = build_limit_widget_view("WEEKLY", UsageWindow(24, 10080, now + timedelta(days=6, hours=17)), now)

    assert five_hour.label == "5 HOUR"
    assert five_hour.percent_text == "56%"
    assert five_hour.progress_value == 56
    assert five_hour.reset_text == "Resets in 3h 33m"
    assert weekly.label == "WEEKLY"
    assert weekly.percent_text == "24%"
    assert weekly.progress_value == 24
    assert weekly.reset_text == "Resets in 6d 17h"


def test_widget_reset_credit_visibility_text() -> None:
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    hidden = build_usage_widget_view(
        UsageSnapshot(reset_credits=RateLimitResetCredits(0, ())),
        True,
        5,
        now,
        now=now,
    )
    visible = build_usage_widget_view(
        UsageSnapshot(reset_credits=RateLimitResetCredits(1, ())),
        True,
        5,
        now,
        now=now,
    )

    assert hidden.show_reset_credit is False
    assert hidden.reset_credit_text == ""
    assert visible.show_reset_credit is True
    assert visible.reset_credit_text == "RESET                    1"


def test_limit_widget_handles_missing_reset_timestamp() -> None:
    view = build_limit_widget_view("5 HOUR", UsageWindow(24, 300, None))

    assert view.percent_text == "24%"
    assert view.reset_text == "Reset time unavailable"


def test_details_view_model_contains_current_limits_and_reset_credits() -> None:
    now = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    reset = now + timedelta(hours=5)
    usage = UsageSnapshot(
        plan="plus",
        primary=UsageWindow(35, 300, reset),
        secondary=UsageWindow(42, 10080, reset + timedelta(days=6)),
        reset_credits=RateLimitResetCredits(
            1,
            (RateLimitResetCredit(status="available", title="Reset credit", expires_at=reset),),
        ),
        fetched_at=now,
    )
    analytics = AnalyticsSnapshot(
        today=DailyQuotaUsage("Today", consumed_pp=5, complete=True),
        yesterday=DailyQuotaUsage("Yesterday", consumed_pp=8, complete=True),
        today_vs_yesterday_percent=-38,
        burn=BurnAnalysis(0.8, 80, None, "SAFE"),
        window_start=now - timedelta(days=1),
        window_reset=reset,
        last_successful_update=now,
        daily_history=(DailyQuotaUsage("Today", consumed_pp=5, complete=True),),
    )

    model = build_details_view_model(usage, analytics, True, 5, now, now=now)

    assert model.plan == "plus"
    assert any(row.label == "5H used" and row.value == "35%" for row in model.current_limits)
    assert any(row.label == "Burn rate" and "projected 80%" in row.value for row in model.usage_pace)
    assert any(row.label == "Today usage" and "weekly quota used today" in row.value for row in model.usage_pace)
    assert model.show_reset_credits is True
    assert model.history[0].consumed_pp == 5
