"""Health check endpoint."""

import asyncio
import logging
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from core.database import check_database_connection
from core.redis import check_redis_connection
from api.dependencies import check_qdrant_connection

logger = logging.getLogger(__name__)

router = APIRouter()


class ServiceStatus(BaseModel):
    """Individual service status."""
    database: str
    redis: str
    qdrant: str


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    services: ServiceStatus
    startup_issues: list[str] = []


async def safe_check(check_func, is_async: bool = True) -> bool:
    """Run a health check safely."""
    try:
        if is_async:
            return await check_func()
        return await asyncio.to_thread(check_func)
    except Exception as e:
        logger.error(f"Health check exception: {e}")
        return False


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request, response: Response) -> HealthResponse:
    """
    Check health of all dependencies.
    
    Returns HTTP 200 if all services are healthy and no startup issues.
    Returns HTTP 503 if any service is unreachable or startup issues exist.
    """
    # Check for startup issues from app state
    startup_issues: list[str] = getattr(request.app.state, "startup_issues", [])
    services_ready: bool = getattr(request.app.state, "services_ready", False)
    
    # If services aren't ready, return degraded immediately
    if not services_ready:
        response.status_code = 503
        logger.warning(
            "Health check failed: services not ready",
            extra={"event": "health_check_failed", "reason": "services_not_ready"}
        )
        return HealthResponse(
            status="degraded",
            services=ServiceStatus(
                database="not_ready",
                redis="not_ready",
                qdrant="not_ready",
            ),
            startup_issues=startup_issues if startup_issues else ["Services not initialized"],
        )
    
    # Run checks concurrently
    db_result, redis_result, qdrant_result = await asyncio.gather(
        safe_check(check_database_connection, is_async=True),
        safe_check(check_redis_connection, is_async=True),
        safe_check(check_qdrant_connection, is_async=False),
    )

    services = ServiceStatus(
        database="connected" if db_result else "unreachable",
        redis="connected" if redis_result else "unreachable",
        qdrant="connected" if qdrant_result else "unreachable",
    )

    all_healthy = db_result and redis_result and qdrant_result and not startup_issues
    status = "ok" if all_healthy else "degraded"

    if not all_healthy:
        response.status_code = 503
        logger.warning(
            f"Health check failed: {services.model_dump()}",
            extra={"event": "health_check_failed", "services": services.model_dump()}
        )

    return HealthResponse(status=status, services=services, startup_issues=startup_issues)
