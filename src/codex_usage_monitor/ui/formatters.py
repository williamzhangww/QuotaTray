from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from codex_usage_monitor.models import (
    AnalyticsSnapshot,
    BurnAnalysis,
    DailyQuotaUsage,
    UsageSnapshot,
    UsageWindow,
    format_countdown,
)


@dataclass(frozen=True)
class UpdateStatus:
    text: str
    is_stale: bool


@dataclass(frozen=True)
class DetailRow:
    label: str
    value: str
    tooltip: str = ""


@dataclass(frozen=True)
class LimitWidgetView:
    label: str
    percent_text: str
    progress_value: int
    reset_text: str
    tooltip: str = ""


@dataclass(frozen=True)
class UsageWidgetView:
    primary: LimitWidgetView
    secondary: LimitWidgetView
    reset_credit_text: str
    show_reset_credit: bool
    update_status: UpdateStatus


@dataclass(frozen=True)
class TaskbarDockView:
    text: str
    tooltip: str
    is_stale: bool


@dataclass(frozen=True)
class DetailsViewModel:
    plan: str
    current_limits: tuple[DetailRow, ...]
    usage_pace: tuple[DetailRow, ...]
    reset_credits: tuple[DetailRow, ...]
    show_reset_credits: bool
    history: tuple[DailyQuotaUsage, ...]
    update_status: UpdateStatus


def update_status(
    last_updated: datetime | None,
    refresh_interval_minutes: int,
    refresh_failed: bool = False,
    now: datetime | None = None,
) -> UpdateStatus:
    if last_updated is None:
        text = "Updated never"
        if refresh_failed:
            text = "Update failed · showing last known data"
        return UpdateStatus(text, True)

    now_utc = _as_utc(now or datetime.now(timezone.utc))
    updated_utc = _as_utc(last_updated)
    age = max(timedelta(0), now_utc - updated_utc)
    local = updated_utc.astimezone()
    if age < timedelta(minutes=1):
        text = "Updated just now"
    else:
        minutes = int(age.total_seconds() // 60)
        if minutes < 60:
            text = f"Updated {minutes}m ago"
        else:
            hours = minutes // 60
            text = f"Updated {hours}h ago"

    is_stale = refresh_failed or age > timedelta(minutes=max(1, refresh_interval_minutes) * 2)
    if refresh_failed:
        text = "Update failed · showing last known data"
    elif is_stale:
        text = f"Data may be stale · Updated {local.strftime('%H:%M')}"
    return UpdateStatus(text, is_stale)


def reset_credit_visible(usage: UsageSnapshot | None, show_reset_credit_section: bool) -> bool:
    return bool(
        show_reset_credit_section
        and usage
        and usage.reset_credits
        and usage.reset_credits.available_count > 0
    )


def format_daily_usage(day: DailyQuotaUsage) -> str:
    if day.consumed_pp is None:
        return day.reason or "Not enough history"
    if day.since is not None:
        return f"{day.consumed_pp}% of weekly quota used today since {day.since.astimezone().strftime('%H:%M')}"
    return f"{day.consumed_pp}% of weekly quota used today"


def format_history_daily_usage(day: DailyQuotaUsage) -> str:
    if day.consumed_pp is None:
        return "No data"
    text = f"{day.consumed_pp}%"
    if not day.complete:
        text += " · Partial"
    return text


def format_burn(burn: BurnAnalysis) -> str:
    if burn.burn_rate is None or burn.projected_usage_percent is None or burn.status is None:
        return burn.reason or "Not enough history"
    return f"{burn.burn_rate:.2f}x {burn.status} · projected {burn.projected_usage_percent}%"


def format_projection_detail(burn: BurnAnalysis) -> str:
    if burn.projected_usage_percent is None:
        return burn.reason or "Not enough history"
    text = f"Projected at reset: {burn.projected_usage_percent}%"
    if burn.estimated_limit_hit_at is not None:
        text += f" · possible limit hit {burn.estimated_limit_hit_at.astimezone().strftime('%Y-%m-%d %H:%M')}"
    return text


def format_reset_countdown(target: datetime | None, now: datetime | None = None) -> str:
    if target is None:
        return "Reset time unavailable"
    return f"Resets in {format_countdown(target, now)}"


def build_limit_widget_view(
    label: str,
    window: UsageWindow | None,
    now: datetime | None = None,
) -> LimitWidgetView:
    if window is None:
        return LimitWidgetView(label, "—", 0, "Reset time unavailable")
    used = window.used_percent_clamped
    return LimitWidgetView(
        label=label,
        percent_text="—" if used is None else f"{used}%",
        progress_value=0 if used is None else used,
        reset_text=format_reset_countdown(window.reset_at, now),
        tooltip=_format_reset_tooltip(window.reset_at),
    )


def build_usage_widget_view(
    usage: UsageSnapshot,
    show_reset_credit_section: bool,
    refresh_interval_minutes: int,
    last_updated: datetime | None,
    refresh_failed: bool = False,
    now: datetime | None = None,
) -> UsageWidgetView:
    reset_credit_text = ""
    show_reset_credit = reset_credit_visible(usage, show_reset_credit_section)
    if show_reset_credit and usage.reset_credits is not None:
        count = usage.reset_credits.available_count
        label = "RESET" if count == 1 else "RESETS"
        reset_credit_text = f"{label}                    {count}"

    return UsageWidgetView(
        primary=build_limit_widget_view("5 HOUR", usage.primary, now),
        secondary=build_limit_widget_view("WEEKLY", usage.secondary, now),
        reset_credit_text=reset_credit_text,
        show_reset_credit=show_reset_credit,
        update_status=update_status(last_updated, refresh_interval_minutes, refresh_failed, now),
    )


def build_taskbar_dock_view(
    usage: UsageSnapshot | None,
    refresh_interval_minutes: int,
    last_updated: datetime | None,
    refresh_failed: bool = False,
    now: datetime | None = None,
) -> TaskbarDockView:
    status = update_status(last_updated, refresh_interval_minutes, refresh_failed, now)
    if usage is None or not usage.is_available:
        text = "Codex unavailable"
        if refresh_failed:
            text += " !"
        return TaskbarDockView(text=text, tooltip="QuotaTray\n\nUsage unavailable", is_stale=True)

    primary = _dock_window_text("5H", usage.primary, now)
    secondary = _dock_window_text("W", usage.secondary, now)
    text = f"{primary} | {secondary}"
    if status.is_stale or usage.stale:
        text += " !"

    tooltip_lines = [
        "QuotaTray",
        "",
        _dock_tooltip_window("5-hour", usage.primary, now),
        "",
        _dock_tooltip_window("Weekly", usage.secondary, now),
        "",
        status.text,
    ]
    if usage.reset_credits and usage.reset_credits.available_count > 0:
        count = usage.reset_credits.available_count
        label = "Reset credit" if count == 1 else "Reset credits"
        tooltip_lines.extend(["", f"{label}: {count}"])
    if usage.stale and usage.error:
        tooltip_lines.extend(["", "Last refresh failed"])
    return TaskbarDockView(
        text=text,
        tooltip="\n".join(tooltip_lines),
        is_stale=status.is_stale or usage.stale,
    )


def build_details_view_model(
    usage: UsageSnapshot | None,
    analytics: AnalyticsSnapshot | None,
    show_reset_credit_section: bool,
    refresh_interval_minutes: int,
    last_updated: datetime | None,
    refresh_failed: bool = False,
    now: datetime | None = None,
) -> DetailsViewModel:
    status = update_status(last_updated, refresh_interval_minutes, refresh_failed, now)
    if usage is None:
        return DetailsViewModel(
            plan="unavailable",
            current_limits=(_row("Status", "unavailable"),),
            usage_pace=(),
            reset_credits=(),
            show_reset_credits=False,
            history=analytics.daily_history if analytics else (),
            update_status=status,
        )

    reset_rows: list[DetailRow] = []
    if usage.reset_credits is not None:
        reset_rows.append(_row("Available", str(usage.reset_credits.available_count)))
        for index, credit in enumerate(usage.reset_credits.credits, start=1):
            label = credit.title or credit.reset_type or f"Credit {index}"
            value = credit.status or "available"
            if credit.expires_at:
                value += f" · expires {credit.expires_at.astimezone().strftime('%Y-%m-%d %H:%M')}"
            reset_rows.append(_row(label, value))

    analytics_rows: list[DetailRow] = []
    if analytics is not None:
        analytics_rows.extend(
            [
                _row("Today usage", format_daily_usage(analytics.today)),
                _row("Yesterday usage", _format_daily_usage_named(analytics.yesterday, "yesterday")),
                _row("Burn rate", format_burn(analytics.burn), format_projection_detail(analytics.burn)),
            ]
        )
        if analytics.today_vs_yesterday_percent is not None:
            analytics_rows.append(_row("Vs yesterday", f"{analytics.today_vs_yesterday_percent:+d}%"))
        if analytics.window_start and analytics.window_reset:
            analytics_rows.append(
                _row(
                    "Window",
                    f"{analytics.window_start.astimezone().strftime('%Y-%m-%d %H:%M')} to "
                    f"{analytics.window_reset.astimezone().strftime('%Y-%m-%d %H:%M')}",
                )
            )

    return DetailsViewModel(
        plan=usage.plan or "unknown",
        current_limits=window_rows("5H", usage.primary) + window_rows("Weekly", usage.secondary),
        usage_pace=tuple(analytics_rows),
        reset_credits=tuple(reset_rows),
        show_reset_credits=reset_credit_visible(usage, show_reset_credit_section),
        history=analytics.daily_history if analytics else (),
        update_status=status,
    )


def window_rows(label: str, window: UsageWindow | None) -> tuple[DetailRow, ...]:
    if window is None:
        return (_row(label, "unavailable"),)
    rows = [
        _row(f"{label} used", "unknown" if window.used_percent is None else f"{window.used_percent}%"),
        _row(f"{label} remaining", "unknown" if window.remaining_percent is None else f"{window.remaining_percent}%"),
        _row(f"{label} window", "unknown" if window.window_minutes is None else _format_duration(window.window_minutes)),
        _row(f"{label} reset", _format_reset_local(window.reset_at), _format_reset_tooltip(window.reset_at)),
    ]
    return tuple(rows)


def _format_daily_usage_named(day: DailyQuotaUsage, name: str) -> str:
    if day.consumed_pp is None:
        return day.reason or "Not enough history"
    return f"{day.consumed_pp}% of weekly quota used {name}"


def _format_duration(minutes: int) -> str:
    if minutes % 10080 == 0:
        weeks = minutes // 10080
        return "1 week" if weeks == 1 else f"{weeks} weeks"
    if minutes % 1440 == 0:
        days = minutes // 1440
        return "1 day" if days == 1 else f"{days} days"
    if minutes % 60 == 0:
        hours = minutes // 60
        return "1 hour" if hours == 1 else f"{hours} hours"
    return f"{minutes} minutes"


def _format_reset_tooltip(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _format_reset_local(value: datetime | None) -> str:
    if value is None:
        return "Reset time unavailable"
    return value.astimezone().strftime("%Y-%m-%d %H:%M %Z")


def _row(label: str, value: str, tooltip: str = "") -> DetailRow:
    return DetailRow(label=label, value=value, tooltip=tooltip)


def _dock_window_text(label: str, window: UsageWindow | None, now: datetime | None) -> str:
    if window is None:
        return f"{label} —"
    used = window.used_percent_clamped
    percent = "—" if used is None else f"{used}%"
    countdown = _compact_countdown(window.reset_at, now)
    return f"{label} {percent} · {countdown}"


def _dock_tooltip_window(label: str, window: UsageWindow | None, now: datetime | None) -> str:
    if window is None:
        return f"{label}: unavailable"
    used = window.used_percent_clamped
    percent = "unknown" if used is None else f"{used}% used"
    return f"{label}: {percent}\nResets in {_readable_countdown(window.reset_at, now)}"


def _compact_countdown(target: datetime | None, now: datetime | None) -> str:
    if target is None:
        return "unknown"
    return format_countdown(target, now).replace(" ", "")


def _readable_countdown(target: datetime | None, now: datetime | None) -> str:
    if target is None:
        return "unknown"
    return format_countdown(target, now)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
