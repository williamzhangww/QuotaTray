from __future__ import annotations

import json
import logging
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from codex_usage_monitor.models import UsageSnapshot
from codex_usage_monitor.version import __version__

logger = logging.getLogger(__name__)


class CodexUsageProviderError(RuntimeError):
    pass


class CodexUsageProvider:
    def __init__(
        self,
        codex_exe: str | Path | None = None,
        codex_home: str | Path | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        self.codex_exe = find_codex_executable(codex_exe)
        self.codex_home = Path(codex_home) if codex_home else Path.home() / ".codex"
        self.timeout_seconds = timeout_seconds
        self._proc: subprocess.Popen[str] | None = None
        self._responses: "queue.Queue[dict[str, Any]]" = queue.Queue()
        self._reader_thread: threading.Thread | None = None
        self._next_request_id = 1

    def get_usage(self) -> UsageSnapshot:
        self._ensure_process()
        result = self._request("account/rateLimits/read", timeout_seconds=self.timeout_seconds)
        return UsageSnapshot.from_app_server_result(result)

    def close(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    def __enter__(self) -> "CodexUsageProvider":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _ensure_process(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        self.close()
        self._start_process()
        self._initialize()

    def _start_process(self) -> None:
        if not self.codex_exe.is_file():
            raise CodexUsageProviderError(f"Codex executable not found: {self.codex_exe}")

        env = os.environ.copy()
        if self.codex_home.is_dir():
            env["CODEX_HOME"] = str(self.codex_home)

        try:
            logger.info("Starting Codex app-server: %s", self.codex_exe)
            self._proc = subprocess.Popen(
                [str(self.codex_exe), "app-server", "--stdio"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._responses = queue.Queue()
            self._reader_thread = threading.Thread(
                target=self._read_stdout_loop,
                name="codex-app-server-reader",
                daemon=True,
            )
            self._reader_thread.start()
        except OSError as exc:
            raise CodexUsageProviderError(f"Unable to start Codex app-server: {exc}") from exc

    def _initialize(self) -> None:
        self._request(
            "initialize",
            {
                "clientInfo": {
                    "name": "quotatray",
                    "title": "QuotaTray",
                    "version": __version__,
                },
                "capabilities": {
                    "optOutNotificationMethods": [
                        "account/rateLimits/updated",
                        "account/updated",
                    ]
                },
            },
            timeout_seconds=30,
        )
        self._send({"method": "initialized"})

    def _request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        proc = self._require_process()
        request_id = self._next_request_id
        self._next_request_id += 1
        message: dict[str, Any] = {"id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)
        return self._read_response(request_id, timeout_seconds or self.timeout_seconds)

    def _send(self, message: dict[str, Any]) -> None:
        proc = self._require_process()
        if proc.stdin is None:
            raise CodexUsageProviderError("Codex app-server stdin unavailable")
        try:
            proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            proc.stdin.flush()
        except OSError as exc:
            raise CodexUsageProviderError(f"Failed to write to Codex app-server: {exc}") from exc

    def _read_response(self, request_id: int, timeout_seconds: int) -> dict[str, Any]:
        proc = self._require_process()
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                stderr = self._safe_stderr_tail(proc)
                raise CodexUsageProviderError(
                    f"Codex app-server exited unexpectedly with code {proc.returncode}: {stderr}"
                )
            remaining = max(0.01, deadline - time.monotonic())
            try:
                message = self._responses.get(timeout=min(0.25, remaining))
            except queue.Empty:
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                error = message["error"]
                text = error.get("message") if isinstance(error, dict) else str(error)
                raise CodexUsageProviderError(f"Codex app-server error: {text}")
            result = message.get("result", {})
            if not isinstance(result, dict):
                raise CodexUsageProviderError("Codex app-server returned a non-object result")
            return result

        raise CodexUsageProviderError("Timed out waiting for Codex app-server response")

    def _read_stdout_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        for line in proc.stdout:
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._responses.put(message)

    def _require_process(self) -> subprocess.Popen[str]:
        if self._proc is None:
            raise CodexUsageProviderError("Codex app-server is not running")
        return self._proc

    def _safe_stderr_tail(self, proc: subprocess.Popen[str]) -> str:
        if proc.stderr is None:
            return ""
        try:
            text = proc.stderr.read() or ""
        except OSError:
            return ""
        return _redact(text)[-500:]

    @staticmethod
    def _find_codex_exe() -> Path:
        return find_codex_executable()


def find_codex_executable(configured_path: str | Path | None = None) -> Path:
    candidates: list[Path] = []
    if configured_path:
        candidates.append(Path(configured_path))

    env_path = os.environ.get("CODEX_EXE")
    if env_path:
        candidates.append(Path(env_path))

    home = Path.home()
    candidates.extend(
        [
            home / ".codex" / ".sandbox-bin" / "codex.exe",
            home / ".codex" / "plugins" / ".plugin-appserver" / "codex.exe",
        ]
    )

    path_codex = shutil.which("codex.exe") or shutil.which("codex")
    if path_codex:
        candidates.append(Path(path_codex))

    candidates.extend(_windows_app_candidates(home))

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    raise CodexUsageProviderError("Codex executable not found")


def _windows_app_candidates(home: Path) -> list[Path]:
    local_app_data = os.environ.get("LOCALAPPDATA")
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    roots = [
        Path(program_files) / "WindowsApps",
    ]
    if local_app_data:
        roots.append(Path(local_app_data) / "Microsoft" / "WindowsApps")

    candidates: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        try:
            for match in root.glob("OpenAI.Codex_*\\app\\resources\\codex.exe"):
                candidates.append(match)
        except OSError:
            continue
    return candidates


def _redact(text: str) -> str:
    sensitive_words = ("access_token", "authorization", "bearer", "refresh_token")
    lines = []
    for line in text.splitlines():
        lowered = line.lower()
        if any(word in lowered for word in sensitive_words):
            lines.append("<redacted>")
        else:
            lines.append(line)
    return "\n".join(lines)
