from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from codex_usage_monitor.app_paths import ensure_app_dirs, logs_dir

LOG_FILE_NAME = "app.log"
SENSITIVE_WORDS = ("access_token", "authorization", "bearer", "refresh_token", "cookie")


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.msg))
        if record.args:
            record.args = tuple(redact(str(arg)) for arg in record.args)
        return True


def setup_logging() -> None:
    ensure_app_dirs()
    log_path = logs_dir() / LOG_FILE_NAME
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    if any(isinstance(handler, RotatingFileHandler) for handler in root.handlers):
        return

    handler = RotatingFileHandler(
        log_path,
        maxBytes=2 * 1024 * 1024,
        backupCount=4,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    handler.addFilter(RedactingFilter())
    root.addHandler(handler)


def redact(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in SENSITIVE_WORDS):
        return "<redacted>"
    return text
