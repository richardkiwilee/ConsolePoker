"""Logging helpers for server/client file logging."""

from __future__ import annotations

import logging
from pathlib import Path

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class LoggerPrefixFilter(logging.Filter):
    def __init__(self, prefix: str) -> None:
        super().__init__()
        self.prefix = prefix

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name.startswith(self.prefix)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def ensure_log_dir() -> Path:
    log_dir = _project_root() / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def configure_server_logging() -> Path:
    log_dir = ensure_log_dir()
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    if not any(getattr(handler, "name", "") == "console_poker_console" for handler in root.handlers):
        console = logging.StreamHandler()
        console.set_name("console_poker_console")
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter(_LOG_FORMAT))
        root.addHandler(console)

    if not any(getattr(handler, "name", "") == "console_poker_server_file" for handler in root.handlers):
        server_log = log_dir / "server.log"
        handler = logging.FileHandler(server_log, encoding="utf-8")
        handler.set_name("console_poker_server_file")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        root.addHandler(handler)

    return log_dir / "server.log"


def configure_client_logging(player_name: str) -> Path:
    safe_name = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in player_name.strip())
    if not safe_name:
        safe_name = "unknown"

    log_dir = ensure_log_dir()
    log_path = log_dir / f"client_{safe_name}.log"
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    for handler in list(root.handlers):
        if getattr(handler, "name", "").startswith("console_poker_client_file_"):
            root.removeHandler(handler)
            handler.close()

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.set_name(f"console_poker_client_file_{safe_name}")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    handler.addFilter(LoggerPrefixFilter("console_poker.client"))
    root.addHandler(handler)
    return log_path
