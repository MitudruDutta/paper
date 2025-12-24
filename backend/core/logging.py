"""Structured logging configuration for observability."""

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any

# Context variables for request tracking
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
document_id_var: ContextVar[str | None] = ContextVar("document_id", default=None)
phase_var: ContextVar[str | None] = ContextVar("phase", default=None)


def get_request_id() -> str | None:
    return request_id_var.get()


def set_request_id(rid: str) -> None:
    request_id_var.set(rid)


def get_document_id() -> str | None:
    return document_id_var.get()


def set_document_id(doc_id: str) -> None:
    document_id_var.set(doc_id)


def get_phase() -> str | None:
    return phase_var.get()


def set_phase(phase: str) -> None:
    phase_var.set(phase)


class StructuredFormatter(logging.Formatter):
    """JSON formatter with context injection."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Inject context
        if rid := get_request_id():
            log_data["request_id"] = rid
        if doc_id := get_document_id():
            log_data["document_id"] = doc_id
        if phase := get_phase():
            log_data["phase"] = phase

        # Include extra fields
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "error_type"):
            log_data["error_type"] = record.error_type
        if hasattr(record, "service"):
            log_data["service"] = record.service
        if hasattr(record, "event"):
            log_data["event"] = record.event

        # Include any other extras
        for key in ["metric", "count", "size_mb", "pages", "chunks", "score"]:
            if hasattr(record, key):
                log_data[key] = getattr(record, key)

        # Exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def configure_logging(json_format: bool = True, level: str = "INFO") -> None:
    """Configure structured logging for the application."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if json_format:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
    root.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


class Timer:
    """Context manager for timing operations."""

    def __init__(self) -> None:
        self.start_time: float = 0
        self.duration_ms: float = 0

    def __enter__(self) -> "Timer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.duration_ms = (time.perf_counter() - self.start_time) * 1000


def generate_request_id() -> str:
    """Generate a unique request ID.
    
    Uses first 8 hex chars of UUID4 (~32 bits, ~4 billion combinations).
    Birthday paradox: ~1% collision probability at ~65k concurrent requests.
    Suitable for log correlation in low-to-medium volume scenarios.
    For high-volume production, consider increasing to 12-16 chars.
    """
    return str(uuid.uuid4())[:8]
