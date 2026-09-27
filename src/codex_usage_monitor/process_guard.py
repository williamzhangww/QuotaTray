from __future__ import annotations

import os
import csv
import io
import subprocess
import sys
from pathlib import Path


def terminate_duplicate_app_processes() -> list[int]:
    current_pid = os.getpid()
    current_exe = Path(sys.executable).resolve()
    terminated: list[int] = []
    for pid, path in _quotatray_processes():
        if pid == current_pid:
            continue
        try:
            if Path(path).resolve() != current_exe:
                continue
        except OSError:
            continue
        if _terminate_process(pid):
            terminated.append(pid)
    return terminated


def _quotatray_processes() -> list[tuple[int, str]]:
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-CimInstance Win32_Process -Filter \"Name='QuotaTray.exe'\" "
        "-ErrorAction SilentlyContinue | "
        "Where-Object { $_.CommandLine -notmatch '(?i)(^|\\s)--quit(\\s|$)' } | "
        "Select-Object ProcessId,ExecutablePath | ConvertTo-Csv -NoTypeInformation",
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    rows: list[tuple[int, str]] = []
    for parts in list(csv.reader(io.StringIO(result.stdout)))[1:]:
        if len(parts) != 2:
            continue
        try:
            rows.append((int(parts[0]), parts[1]))
        except ValueError:
            continue
    return rows


def _terminate_process(pid: int) -> bool:
    try:
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            check=False,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0
