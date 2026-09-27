from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DailyQuotaUsage:
    label: str
    consumed_pp: int | None = None
    since: datetime | None = None
    complete: bool = False
    reason: str | None = None

    @property
    def is_available(self) -> bool:
        return self.consumed_pp is not None


@dataclass(frozen=True)
class BurnAnalysis:
    burn_rate: float | None = None
    projected_usage_percent: int | None = None
    estimated_limit_hit_at: datetime | None = None
    status: str | None = None
    reason: str | None = None

    @property
    def is_available(self) -> bool:
        return self.burn_rate is not None and self.projected_usage_percent is not None


@dataclass(frozen=True)
class AnalyticsSnapshot:
    today: DailyQuotaUsage
    yesterday: DailyQuotaUsage
    today_vs_yesterday_percent: int | None
    burn: BurnAnalysis
    window_start: datetime | None
    window_reset: datetime | None
    last_successful_update: datetime | None
    daily_history: tuple[DailyQuotaUsage, ...] = ()
