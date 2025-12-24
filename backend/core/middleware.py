"""Request tracking middleware for observability."""

import logging
import time
import uuid as uuid_module
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.logging import (
    generate_request_id,
    set_request_id,
    set_document_id,
    set_phase,
)
from core.metrics import metrics

logger = logging.getLogger(__name__)


class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """Middleware to track requests with IDs and timing."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate and set request ID
        request_id = request.headers.get("X-Request-ID") or generate_request_id()
        set_request_id(request_id)
        set_document_id(None)  # Reset per request
        set_phase(None)

        # Extract document_id from path if present
        path = request.url.path
        if "/documents/" in path:
            parts = path.split("/documents/")
            if len(parts) > 1:
                doc_part = parts[1].split("/")[0]
                # Validate UUID format
                try:
                    uuid_module.UUID(doc_part)
                    set_document_id(doc_part)
                except ValueError:
                    pass  # Not a valid UUID, skip setting document_id

        # Determine phase from path
        if "/upload" in path:
            set_phase("ingestion")
        elif "/extract-text" in path:
            set_phase("extraction")
        elif "/index" in path:
            set_phase("indexing")
        elif "/search" in path:
            set_phase("retrieval")
        elif "/ask" in path:
            set_phase("qa")
        elif "/extract-visuals" in path:
            set_phase("multimodal")

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            # Log request completion (skip health checks for noise reduction)
            if not path.startswith("/health"):
                logger.info(
                    f"{request.method} {path} {response.status_code}",
                    extra={"duration_ms": round(duration_ms, 2)},
                )

            return response

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"{request.method} {path} failed: {e.__class__.__name__}",
                extra={
                    "duration_ms": round(duration_ms, 2),
                    "error_type": e.__class__.__name__,
                },
                exc_info=True,
            )
            raise
