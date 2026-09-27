from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def parse_unix_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def window_label(window_minutes: int | None) -> str:
    if not window_minutes or window_minutes <= 0:
        return "LIMIT"
    if window_minutes % 10080 == 0:
        weeks = window_minutes // 10080
        return "WEEK" if weeks == 1 else f"{weeks}W"
    if window_minutes % 1440 == 0:
        days = window_minutes // 1440
        return f"{days}D"
    if window_minutes % 60 == 0:
        hours = window_minutes // 60
        return f"{hours}H"
    return f"{window_minutes}M"


def format_countdown(target: datetime | None, now: datetime | None = None) -> str:
    if target is None:
        return "unknown"
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)

    seconds = int((target - now).total_seconds())
    if seconds <= 0:
        return "now"

    minutes = (seconds + 59) // 60
    days, remaining_minutes = divmod(minutes, 1440)
    hours, mins = divmod(remaining_minutes, 60)

    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"


@dataclass(frozen=True)
class UsageWindow:
    used_percent: int | None = None
    window_minutes: int | None = None
    reset_at: datetime | None = None

    @property
    def label(self) -> str:
        return window_label(self.window_minutes)

    @property
    def remaining_percent(self) -> int | None:
        if self.used_percent is None:
            return None
        return max(0, min(100, 100 - int(self.used_percent)))

    @property
    def used_percent_clamped(self) -> int | None:
        if self.used_percent is None:
            return None
        return max(0, min(100, int(self.used_percent)))


@dataclass(frozen=True)
class CreditsSnapshot:
    has_credits: bool | None = None
    unlimited: bool | None = None
    balance: str | None = None


@dataclass(frozen=True)
class RateLimitResetCredit:
    reset_type: str | None = None
    status: str | None = None
    granted_at: datetime | None = None
    expires_at: datetime | None = None
    title: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class RateLimitResetCredits:
    available_count: int = 0
    credits: tuple[RateLimitResetCredit, ...] = ()


@dataclass(frozen=True)
class UsageSnapshot:
    plan: str | None = None
    selected_limit_id: str | None = None
    selected_source: str = "rateLimits"
    primary: UsageWindow | None = None
    secondary: UsageWindow | None = None
    credits: CreditsSnapshot | None = None
    reset_credits: RateLimitResetCredits | None = None
    individual_limit: dict[str, Any] | None = None
    rate_limit_reached_type: str | None = None
    spend_control_reached: bool | None = None
    fetched_at: datetime | None = None
    stale: bool = False
    error: str | None = None

    @property
    def is_available(self) -> bool:
        return self.error is None and (self.primary is not None or self.secondary is not None)

    @classmethod
    def from_app_server_result(cls, result: dict[str, Any]) -> "UsageSnapshot":
        if not isinstance(result, dict):
            raise ValueError("account/rateLimits/read result must be an object")

        snapshot, selected_source = _select_codex_snapshot(result)
        if not isinstance(snapshot, dict):
            raise ValueError("rateLimits snapshot missing or invalid")

        return cls(
            plan=snapshot.get("planType"),
            selected_limit_id=snapshot.get("limitId"),
            selected_source=selected_source,
            primary=_parse_window(snapshot.get("primary")),
            secondary=_parse_window(snapshot.get("secondary")),
            credits=_parse_credits(snapshot.get("credits")),
            reset_credits=_parse_reset_credits(result.get("rateLimitResetCredits")),
            individual_limit=snapshot.get("individualLimit")
            if isinstance(snapshot.get("individualLimit"), dict)
            else None,
            rate_limit_reached_type=snapshot.get("rateLimitReachedType"),
            spend_control_reached=snapshot.get("spendControlReached"),
            fetched_at=datetime.now(timezone.utc),
        )

    def mark_stale(self, error: str) -> "UsageSnapshot":
        return UsageSnapshot(
            plan=self.plan,
            selected_limit_id=self.selected_limit_id,
            selected_source=self.selected_source,
            primary=self.primary,
            secondary=self.secondary,
            credits=self.credits,
            reset_credits=self.reset_credits,
            individual_limit=self.individual_limit,
            rate_limit_reached_type=self.rate_limit_reached_type,
            spend_control_reached=self.spend_control_reached,
            fetched_at=self.fetched_at,
            stale=True,
            error=error,
        )


def _select_codex_snapshot(result: dict[str, Any]) -> tuple[dict[str, Any], str]:
    by_id = result.get("rateLimitsByLimitId")
    if isinstance(by_id, dict) and isinstance(by_id.get("codex"), dict):
        return by_id["codex"], "rateLimitsByLimitId.codex"
    rate_limits = result.get("rateLimits")
    if isinstance(rate_limits, dict):
        return rate_limits, "rateLimits"
    raise ValueError("rateLimits snapshot missing")


def _parse_window(value: Any) -> UsageWindow | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("rate limit window must be an object or null")
    used = value.get("usedPercent")
    window = value.get("windowDurationMins")
    return UsageWindow(
        used_percent=_optional_int(used),
        window_minutes=_optional_int(window),
        reset_at=parse_unix_timestamp(value.get("resetsAt")),
    )


def _parse_credits(value: Any) -> CreditsSnapshot | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("credits must be an object or null")
    return CreditsSnapshot(
        has_credits=value.get("hasCredits"),
        unlimited=value.get("unlimited"),
        balance=value.get("balance"),
    )


def _parse_reset_credits(value: Any) -> RateLimitResetCredits | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("rateLimitResetCredits must be an object or null")

    credit_rows = value.get("credits")
    credits: list[RateLimitResetCredit] = []
    if isinstance(credit_rows, list):
        for row in credit_rows:
            if not isinstance(row, dict):
                continue
            credits.append(
                RateLimitResetCredit(
                    reset_type=row.get("resetType"),
                    status=row.get("status"),
                    granted_at=parse_unix_timestamp(row.get("grantedAt")),
                    expires_at=parse_unix_timestamp(row.get("expiresAt")),
                    title=row.get("title"),
                    description=row.get("description"),
                )
            )

    return RateLimitResetCredits(
        available_count=_optional_int(value.get("availableCount")) or 0,
        credits=tuple(credits),
    )


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
