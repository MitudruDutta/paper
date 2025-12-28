"""FastAPI dependencies."""

import logging
from fastapi import Request, HTTPException
from qdrant_client import QdrantClient

from core.config import settings

logger = logging.getLogger(__name__)


async def require_services_ready(request: Request) -> None:
    """
    Dependency that ensures all required services are ready.
    Use this in endpoints that depend on backend services.
    Raises HTTP 503 if services are not ready.
    """
    services_ready: bool = getattr(request.app.state, "services_ready", False)
    if not services_ready:
        logger.warning(
            "Request rejected: services not ready",
            extra={"event": "service_unavailable", "path": request.url.path}
        )
        raise HTTPException(
            status_code=503,
            detail="Service unavailable: backend services not ready"
        )

qdrant_client: QdrantClient | None = None


def init_qdrant() -> None:
    """Initialize Qdrant client."""
    global qdrant_client
    try:
        # Support both local and Qdrant Cloud
        if settings.qdrant_api_key:
            # Qdrant Cloud (HTTPS)
            qdrant_client = QdrantClient(
                url=f"https://{settings.qdrant_host}:{settings.qdrant_port}",
                api_key=settings.qdrant_api_key,
            )
        else:
            # Local/self-hosted
            qdrant_client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
            )
        qdrant_client.get_collections()
        logger.info("Qdrant connection established successfully")
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant: {e}")
        raise


def close_qdrant() -> None:
    """Close Qdrant client connection."""
    global qdrant_client
    if qdrant_client:
        try:
            qdrant_client.close()
            logger.info("Qdrant connection closed")
        except Exception as e:
            logger.error(f"Failed to close Qdrant connection: {e}")
        finally:
            qdrant_client = None


def check_qdrant_connection() -> bool:
    """Check if Qdrant is reachable."""
    try:
        if qdrant_client:
            qdrant_client.get_collections()
            return True
        return False
    except Exception as e:
        logger.error(f"Qdrant connection check failed: {e}")
        return False


def get_qdrant() -> QdrantClient:
    """Get Qdrant client instance."""
    if qdrant_client is None:
        raise RuntimeError("Qdrant client not initialized")
    return qdrant_client
