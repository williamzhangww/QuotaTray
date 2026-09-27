"""Validation helpers for the system-installed Microsoft VC++ runtime."""

from __future__ import annotations

import re
from collections.abc import Mapping

MINIMUM_VC_RUNTIME = (14, 44, 0)
VC_RUNTIME_REGISTRY_KEY = r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64"


def parse_version(value: object) -> tuple[int, int, int] | None:
    """Parse Microsoft registry version strings such as v14.50.35719.00."""
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?", value.strip(), re.IGNORECASE)
    if match is None:
        return None
    try:
        return tuple(int(part or 0) for part in match.groups()[:3])
    except ValueError:
        return None


def is_compatible_runtime(
    state: Mapping[str, object] | None,
    architecture: str = "x64",
) -> bool:
    """Require official x64 installed state and numeric v14.44+ version."""
    if architecture.strip().lower() not in {"x64", "amd64"} or not state:
        return False
    if state.get("Installed") != 1:
        return False
    version = parse_version(state.get("Version"))
    major, minor, build = (state.get("Major"), state.get("Minor"), state.get("Bld"))
    if not all(isinstance(part, int) and not isinstance(part, bool) and part >= 0 for part in (major, minor, build)):
        return False
    if version is None or version != (major, minor, build):
        return False
    return version >= MINIMUM_VC_RUNTIME
