from __future__ import annotations

import pytest

from codex_usage_monitor.runtime_prerequisite import is_compatible_runtime, parse_version


def _state(version: str, major: int = 14, minor: int = 44, build: int = 35211, installed: int = 1):
    return {"Installed": installed, "Version": version, "Major": major, "Minor": minor, "Bld": build}


@pytest.mark.parametrize(
    ("state", "architecture", "expected"),
    [
        (_state("v14.44.35211.00"), "x64", True),
        (_state("v14.50.35719.00", 14, 50, 35719), "x64", True),
        (_state("v14.29.30139.00", 14, 29, 30139), "x64", False),
        (None, "x64", False),
        (_state("v14.44.35211.00", installed=0), "x64", False),
        (_state("not-a-version"), "x64", False),
        (_state("v14.44.35211.00"), "x86", False),
        (_state("v14.60.1.0", 14, 60, 1), "AMD64", True),
        (_state("v14.44.35211.00", 14, 44, 35210), "x64", False),
    ],
)
def test_runtime_registry_states(state, architecture, expected):
    assert is_compatible_runtime(state, architecture) is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("v14.50.35719.00", (14, 50, 35719)),
        ("14.44.35211", (14, 44, 35211)),
        ("14.9.99999", (14, 9, 99999)),
        ("v14.44.bad.00", None),
        ("", None),
        (None, None),
    ],
)
def test_version_parser(raw, expected):
    assert parse_version(raw) == expected
