"""Health check endpoint."""

import asyncio
import logging
from fastapi import APIRouter, Response
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
async def health_check(response: Response) -> HealthResponse:
    """
    Check health of all dependencies.
    
    Returns HTTP 200 if all services are healthy.
    Returns HTTP 503 if any service is unreachable.
    """
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

    all_healthy = db_result and redis_result and qdrant_result
    status = "ok" if all_healthy else "degraded"

    if not all_healthy:
        response.status_code = 503
        logger.warning(f"Health check failed: {services.model_dump()}")

    return HealthResponse(status=status, services=services)
