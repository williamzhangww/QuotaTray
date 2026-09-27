from __future__ import annotations

from dataclasses import dataclass

from codex_usage_monitor.version import __version__

APP_NAME = "QuotaTray"
APP_EXE_NAME = "QuotaTray.exe"
APP_PUBLISHER = "QuotaTray Project"
APP_URL = "https://github.com"
APP_DESCRIPTION = "An unofficial Windows tray monitor for OpenAI Codex usage limits."
APP_ID = "F72E59D8-41C1-4A22-9DBA-14F8C331D292"


@dataclass(frozen=True)
class ReleaseMetadata:
    name: str
    version: str
    publisher: str
    url: str
    description: str
    exe_name: str
    app_id: str


def release_metadata() -> ReleaseMetadata:
    return ReleaseMetadata(
        name=APP_NAME,
        version=__version__,
        publisher=APP_PUBLISHER,
        url=APP_URL,
        description=APP_DESCRIPTION,
        exe_name=APP_EXE_NAME,
        app_id=APP_ID,
    )


def version_tuple() -> tuple[int, int, int, int]:
    parts = [int(part) for part in __version__.split(".")]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])  # type: ignore[return-value]
