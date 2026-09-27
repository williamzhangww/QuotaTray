from datetime import datetime, timezone

import pytest

from codex_usage_monitor.models import UsageSnapshot, format_countdown, window_label


def test_parse_usage_snapshot_prefers_codex_bucket() -> None:
    result = {
        "rateLimits": {
            "limitId": "fallback",
            "planType": "plus",
            "primary": {"usedPercent": 99, "windowDurationMins": 60, "resetsAt": 100},
        },
        "rateLimitsByLimitId": {
            "codex": {
                "limitId": "codex",
                "planType": "plus",
                "primary": {
                    "usedPercent": 8,
                    "windowDurationMins": 300,
                    "resetsAt": 1787758835,
                },
                "secondary": {
                    "usedPercent": 1,
                    "windowDurationMins": 10080,
                    "resetsAt": 1788345635,
                },
                "credits": {"hasCredits": False, "unlimited": False, "balance": "0"},
                "rateLimitReachedType": None,
                "spendControlReached": False,
            }
        },
        "rateLimitResetCredits": {
            "availableCount": 1,
            "credits": [
                {
                    "resetType": "codexRateLimits",
                    "status": "available",
                    "grantedAt": 1787349664,
                    "expiresAt": 1789941664,
                    "title": "Full reset",
                }
            ],
        },
    }

    usage = UsageSnapshot.from_app_server_result(result)

    assert usage.plan == "plus"
    assert usage.selected_source == "rateLimitsByLimitId.codex"
    assert usage.primary is not None
    assert usage.primary.used_percent == 8
    assert usage.primary.remaining_percent == 92
    assert usage.primary.label == "5H"
    assert usage.secondary is not None
    assert usage.secondary.label == "WEEK"
    assert usage.credits is not None
    assert usage.credits.balance == "0"
    assert usage.reset_credits is not None
    assert usage.reset_credits.available_count == 1
    assert usage.reset_credits.credits[0].title == "Full reset"


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [
        (300, "5H"),
        (10080, "WEEK"),
        (20160, "2W"),
        (1440, "1D"),
        (90, "90M"),
        (None, "LIMIT"),
    ],
)
def test_window_label(minutes: int | None, expected: str) -> None:
    assert window_label(minutes) == expected


def test_countdown_formatting() -> None:
    now = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
    assert format_countdown(datetime(2026, 8, 26, 12, 31, tzinfo=timezone.utc), now) == "2h 31m"
    assert format_countdown(datetime(2026, 8, 31, 4, 0, tzinfo=timezone.utc), now) == "4d 18h"
    assert format_countdown(datetime(2026, 8, 26, 9, 0, tzinfo=timezone.utc), now) == "now"
    assert format_countdown(None, now) == "unknown"


def test_missing_optional_fields_do_not_crash() -> None:
    usage = UsageSnapshot.from_app_server_result(
        {
            "rateLimits": {
                "limitId": "codex",
                "planType": "plus",
                "primary": None,
                "secondary": {"usedPercent": 0},
            },
            "rateLimitResetCredits": None,
        }
    )

    assert usage.primary is None
    assert usage.secondary is not None
    assert usage.secondary.used_percent == 0
    assert usage.secondary.window_minutes is None
    assert usage.reset_credits is None


def test_invalid_response_raises() -> None:
    with pytest.raises(ValueError):
        UsageSnapshot.from_app_server_result({"rateLimits": "bad"})


def test_remaining_percentage_is_clamped() -> None:
    high = UsageSnapshot.from_app_server_result(
        {"rateLimits": {"primary": {"usedPercent": 150}}}
    )
    low = UsageSnapshot.from_app_server_result(
        {"rateLimits": {"primary": {"usedPercent": -10}}}
    )

    assert high.primary is not None
    assert high.primary.remaining_percent == 0
    assert low.primary is not None
    assert low.primary.remaining_percent == 100
