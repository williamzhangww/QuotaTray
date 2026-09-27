from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta, timezone

from codex_usage_monitor.models.analytics import (
    AnalyticsSnapshot,
    BurnAnalysis,
    DailyQuotaUsage,
)
from codex_usage_monitor.models.usage import UsageSnapshot
from codex_usage_monitor.storage import HistoryRepository, SnapshotRecord


class AnalyticsService:
    def __init__(
        self,
        repository: HistoryRepository,
        minimum_burn_elapsed_minutes: int = 30,
    ) -> None:
        self.repository = repository
        self.minimum_burn_elapsed_minutes = minimum_burn_elapsed_minutes

    def build_snapshot(
        self,
        latest_usage: UsageSnapshot | None = None,
        now: datetime | None = None,
    ) -> AnalyticsSnapshot:
        local_now = _as_local(now or datetime.now().astimezone())
        today_start = datetime.combine(local_now.date(), time.min).astimezone()
        tomorrow_start = today_start + timedelta(days=1)
        yesterday_start = today_start - timedelta(days=1)

        today = self._daily_usage(today_start, min(local_now, tomorrow_start), "Today")
        yesterday = self._daily_usage(yesterday_start, today_start, "Yesterday")
        comparison = _compare_days(today, yesterday)
        burn, window_start, window_reset = self._burn_analysis(latest_usage, local_now)
        daily_history = self.daily_history(days=7, now=local_now)

        latest_record = self.repository.get_latest_snapshot()
        return AnalyticsSnapshot(
            today=today,
            yesterday=yesterday,
            today_vs_yesterday_percent=comparison,
            burn=burn,
            window_start=window_start,
            window_reset=window_reset,
            last_successful_update=latest_record.captured_at if latest_record else None,
            daily_history=tuple(daily_history),
        )

    def daily_history(
        self,
        days: int = 7,
        now: datetime | None = None,
    ) -> list[DailyQuotaUsage]:
        if days <= 0:
            return []
        local_now = _as_local(now or datetime.now().astimezone())
        today_start = datetime.combine(local_now.date(), time.min).astimezone()
        rows: list[DailyQuotaUsage] = []
        for index in range(days - 1, -1, -1):
            start = today_start - timedelta(days=index)
            end = min(start + timedelta(days=1), local_now)
            label = start.strftime("%a")
            if start.date() == local_now.date():
                label = "Today"
            elif start.date() == (local_now.date() - timedelta(days=1)):
                label = "Yesterday"
            rows.append(self._daily_usage(start, end, label))
        return rows

    def _daily_usage(
        self,
        start_local: datetime,
        end_local: datetime,
        label: str,
    ) -> DailyQuotaUsage:
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)
        records = [
            record
            for record in self.repository.list_snapshots(start_utc, end_utc)
            if record.secondary_used_percent is not None
            and record.secondary_window_minutes is not None
            and record.secondary_reset_at is not None
        ]
        if len(records) < 2:
            return DailyQuotaUsage(label=label, reason="Not enough history")

        consumed = _consumed_pp_for_records(records, start_local)
        first_local = records[0].captured_at.astimezone()
        complete = first_local <= start_local + timedelta(minutes=30)
        return DailyQuotaUsage(
            label=label,
            consumed_pp=consumed,
            since=None if complete else first_local,
            complete=complete,
        )

    def _burn_analysis(
        self,
        latest_usage: UsageSnapshot | None,
        local_now: datetime,
    ) -> tuple[BurnAnalysis, datetime | None, datetime | None]:
        if latest_usage is None or latest_usage.secondary is None:
            return BurnAnalysis(reason="Not enough history"), None, None

        window = latest_usage.secondary
        if (
            window.used_percent is None
            or window.window_minutes is None
            or window.window_minutes <= 0
            or window.reset_at is None
        ):
            return BurnAnalysis(reason="Not enough history"), None, None

        window_reset = window.reset_at
        window_start = window_reset - timedelta(minutes=window.window_minutes)
        now_utc = local_now.astimezone(timezone.utc)
        elapsed = now_utc - window_start
        duration = timedelta(minutes=window.window_minutes)
        minimum = timedelta(minutes=self.minimum_burn_elapsed_minutes)
        if elapsed < minimum:
            return BurnAnalysis(reason="Collecting data"), window_start, window_reset
        if elapsed <= timedelta(0) or duration <= timedelta(0):
            return BurnAnalysis(reason="Not enough history"), window_start, window_reset

        time_fraction = min(1.0, elapsed.total_seconds() / duration.total_seconds())
        if time_fraction <= 0:
            return BurnAnalysis(reason="Not enough history"), window_start, window_reset

        usage_fraction = max(0.0, min(1.0, window.used_percent / 100.0))
        burn_rate = usage_fraction / time_fraction
        projected = int(round(min(999.0, (window.used_percent / time_fraction))))
        limit_hit = None
        if projected > 100 and window.used_percent > 0:
            seconds_to_100 = duration.total_seconds() * (1.0 / burn_rate)
            limit_hit = window_start + timedelta(seconds=seconds_to_100)

        return (
            BurnAnalysis(
                burn_rate=burn_rate,
                projected_usage_percent=projected,
                estimated_limit_hit_at=limit_hit,
                status=_status_for_projected(projected),
            ),
            window_start,
            window_reset,
        )


def _consumed_pp_for_records(records: list[SnapshotRecord], day_start_local: datetime) -> int:
    grouped: dict[tuple[int, datetime], list[SnapshotRecord]] = defaultdict(list)
    for record in records:
        identity = record.secondary_window_identity
        if identity is not None:
            grouped[identity].append(record)

    total = 0
    day_start_utc = day_start_local.astimezone(timezone.utc)
    for (window_minutes, reset_at), group in grouped.items():
        ordered = sorted(group, key=lambda item: item.captured_at)
        observed = [item.secondary_used_percent for item in ordered if item.secondary_used_percent is not None]
        if not observed:
            continue
        window_start = reset_at - timedelta(minutes=window_minutes)
        baseline = 0 if window_start >= day_start_utc else observed[0]
        total += max(0, max(observed) - baseline)
    return int(total)


def _compare_days(today: DailyQuotaUsage, yesterday: DailyQuotaUsage) -> int | None:
    if (
        today.consumed_pp is None
        or yesterday.consumed_pp is None
        or not today.complete
        or not yesterday.complete
        or yesterday.consumed_pp == 0
    ):
        return None
    return int(round(((today.consumed_pp - yesterday.consumed_pp) / yesterday.consumed_pp) * 100))


def _status_for_projected(projected: int) -> str:
    if projected <= 85:
        return "SAFE"
    if projected <= 100:
        return "WATCH"
    return "HIGH"


def _as_local(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).astimezone()
    return value.astimezone()
