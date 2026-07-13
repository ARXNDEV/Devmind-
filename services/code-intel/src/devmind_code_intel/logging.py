"""Structured JSON logging via structlog, with dev-friendly console output."""

import logging
import sys
from typing import Any

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

_SENSITIVE_KEYS = {"authorization", "password", "token", "secret", "cookie", "api_key"}


def _redact(_logger: WrappedLogger, _name: str, event_dict: EventDict) -> EventDict:
    for key in list(event_dict):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_logging(environment: str) -> None:
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _redact,
    ]
    renderer: Any = (
        structlog.dev.ConsoleRenderer()
        if environment == "development"
        else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )
