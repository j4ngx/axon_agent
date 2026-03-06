"""Centralised logging configuration.

Call ``setup_logging()`` once at startup to wire up structured JSON output on
*stdout* with automatic secret redaction.
"""

from __future__ import annotations

import logging
import re
import sys

from pythonjsonlogger.json import JsonFormatter

# ---------------------------------------------------------------------------
# Secret redaction filter
# ---------------------------------------------------------------------------

# Patterns that look like API keys / tokens (conservative heuristics).
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(gsk_)[A-Za-z0-9]{20,}", re.ASCII),  # Groq keys
    re.compile(r"(sk-or-v1-)[A-Za-z0-9]{20,}", re.ASCII),  # OpenRouter keys
    re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b"),  # Telegram bot tokens
]

_REDACTED = "***REDACTED***"


class _SecretRedactionFilter(logging.Filter):
    """Replace known secret patterns in log messages with a placeholder."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern in _SECRET_PATTERNS:
                record.msg = pattern.sub(_REDACTED, record.msg)
        if record.args:
            sanitised = []
            for arg in record.args if isinstance(record.args, tuple) else (record.args,):
                if isinstance(arg, str):
                    for pattern in _SECRET_PATTERNS:
                        arg = pattern.sub(_REDACTED, arg)
                sanitised.append(arg)
            record.args = tuple(sanitised)
        return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger with structured JSON output to *stdout*.

    Args:
        level: Logging level name (e.g. ``"INFO"``, ``"DEBUG"``).
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers when called more than once (e.g. in tests).
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(root.level)

    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    handler.setFormatter(formatter)
    handler.addFilter(_SecretRedactionFilter())

    root.addHandler(handler)
