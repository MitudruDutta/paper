"""Sentry integration for error tracking."""

import logging
import os
from typing import Any

from core.version import VERSION

logger = logging.getLogger(__name__)

# Sentry SDK is optional - gracefully handle if not installed
_sentry_initialized = False

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    sentry_sdk = None


def init_sentry() -> bool:
    """Initialize Sentry if DSN is configured. Returns True if initialized."""
    global _sentry_initialized
    
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        logger.info("Sentry DSN not configured, error tracking disabled")
        return False
    
    if not SENTRY_AVAILABLE:
        logger.warning("sentry-sdk not installed, error tracking disabled")
        return False
    
    environment = os.getenv("ENV", "development")
    release = os.getenv("APP_VERSION", VERSION)
    
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=f"paper@{release}",
        traces_sample_rate=0.1,  # 10% of transactions for performance
        profiles_sample_rate=0.1,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            LoggingIntegration(level=logging.WARNING, event_level=logging.ERROR),
        ],
        # PII scrubbing
        send_default_pii=False,
        before_send=_scrub_sensitive_data,
    )
    
    _sentry_initialized = True
    logger.info(f"Sentry initialized for environment: {environment}")
    return True


def _scrub_sensitive_data(event: dict, hint: dict) -> dict | None:
    """Remove sensitive data before sending to Sentry."""
    # Scrub request body for document content
    if "request" in event and "data" in event["request"]:
        data = event["request"]["data"]
        if isinstance(data, dict):
            # Remove any PDF content or large text fields
            for key in ["content", "text", "extracted_text", "file", "pdf"]:
                if key in data:
                    data[key] = "[REDACTED]"
    
    # Scrub breadcrumbs that might contain document content
    if "breadcrumbs" in event:
        for crumb in event.get("breadcrumbs", {}).get("values", []):
            if crumb.get("category") == "query":
                # Truncate SQL queries that might contain text
                if "message" in crumb and len(crumb["message"]) > 500:
                    crumb["message"] = crumb["message"][:500] + "...[TRUNCATED]"
    
    return event


def capture_exception(error: Exception, **context: Any) -> str | None:
    """Capture an exception to Sentry with optional context."""
    if not _sentry_initialized or not SENTRY_AVAILABLE:
        return None
    
    with sentry_sdk.push_scope() as scope:
        for key, value in context.items():
            scope.set_extra(key, value)
        return sentry_sdk.capture_exception(error)


def capture_message(message: str, level: str = "info", **context: Any) -> str | None:
    """Capture a message to Sentry."""
    if not _sentry_initialized or not SENTRY_AVAILABLE:
        return None
    
    with sentry_sdk.push_scope() as scope:
        for key, value in context.items():
            scope.set_extra(key, value)
        return sentry_sdk.capture_message(message, level=level)


def set_user(user_id: str | None, **extra: Any) -> None:
    """Set user context for Sentry events."""
    if not _sentry_initialized or not SENTRY_AVAILABLE:
        return
    
    sentry_sdk.set_user({"id": user_id, **extra} if user_id else None)


def set_tag(key: str, value: str) -> None:
    """Set a tag for Sentry events."""
    if not _sentry_initialized or not SENTRY_AVAILABLE:
        return
    
    sentry_sdk.set_tag(key, value)
