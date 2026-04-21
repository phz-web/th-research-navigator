"""Structured logging configuration using the Python stdlib logging module.

Call ``setup_logging()`` once at CLI entry-point startup.  All other modules
obtain a logger via ``logging.getLogger(__name__)``.

Log level is controlled by the ``LOG_LEVEL`` environment variable (default
``INFO``).  Messages are emitted as structured key=value pairs on stderr so
they can be parsed by log aggregators without a JSON library dependency on
the transport layer.
"""

from __future__ import annotations

import logging
import sys
from typing import Any


class _KVFormatter(logging.Formatter):
    """Formats log records as  level=INFO  ts=2024-01-02T03:04:05Z  logger=foo  msg=...  key=val ..."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        import datetime

        ts = datetime.datetime.utcfromtimestamp(record.created).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        base = (
            f"level={record.levelname}"
            f"  ts={ts}"
            f"  logger={record.name}"
            f"  msg={record.getMessage()!r}"
        )
        # Append any extra fields attached via logger.info("msg", extra={...})
        extras: dict[str, Any] = {
            k: v
            for k, v in record.__dict__.items()
            if k
            not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "taskName",
            }
        }
        if extras:
            kv = "  ".join(f"{k}={v!r}" for k, v in extras.items())
            base = f"{base}  {kv}"
        if record.exc_info:
            base = f"{base}\n{self.formatException(record.exc_info)}"
        return base


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger.  Call once at process start."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_KVFormatter())
    root = logging.getLogger()
    # Avoid adding duplicate handlers if called twice in tests.
    if root.handlers:
        root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric)
    # Silence noisy third-party loggers.
    for name in ("urllib3", "requests", "psycopg.pool"):
        logging.getLogger(name).setLevel(logging.WARNING)
