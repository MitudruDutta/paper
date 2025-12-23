"""Health check endpoint."""

import asyncio
import logging
import os

import httpx
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from core.database import check_database_connection
from core.redis import check_redis_connection
from api.dependencies import check_qdrant_connection

logger = logging.getLogger(__name__)

router = APIRouter()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "172.17.0.1")
OLLAMA_URL = f"http://{OLLAMA_HOST}:11434"


class ServiceStatus(BaseModel):
    """Individual service status."""
    database: str
    redis: str
    qdrant: str
    ollama: str


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


async def check_ollama_connection() -> bool:
    """Check if Ollama is reachable."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Ollama health check failed: {e}")
        return False


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request, response: Response) -> HealthResponse:
    """
    Check health of all dependencies.
    
    Returns HTTP 200 if all core services are healthy.
    Returns HTTP 503 if any core service is unreachable.
    Note: Ollama is optional - degraded but not failed if unavailable.
    """
    startup_issues: list[str] = getattr(request.app.state, "startup_issues", [])
    services_ready: bool = getattr(request.app.state, "services_ready", False)
    
    if not services_ready:
        response.status_code = 503
        return HealthResponse(
            status="degraded",
            services=ServiceStatus(
                database="not_ready",
                redis="not_ready",
                qdrant="not_ready",
                ollama="not_ready",
            ),
            startup_issues=startup_issues if startup_issues else ["Services not initialized"],
        )
    
    # Run checks concurrently
    db_result, redis_result, qdrant_result, ollama_result = await asyncio.gather(
        safe_check(check_database_connection, is_async=True),
        safe_check(check_redis_connection, is_async=True),
        safe_check(check_qdrant_connection, is_async=False),
        check_ollama_connection(),
    )

    services = ServiceStatus(
        database="connected" if db_result else "unreachable",
        redis="connected" if redis_result else "unreachable",
        qdrant="connected" if qdrant_result else "unreachable",
        ollama="connected" if ollama_result else "unreachable",
    )

    # Core services (DB, Redis, Qdrant) must be healthy
    # Ollama is optional - QA will fail gracefully if unavailable
    core_healthy = db_result and redis_result and qdrant_result and not startup_issues
    all_healthy = core_healthy and ollama_result
    
    if all_healthy:
        status = "ok"
    elif core_healthy:
        status = "degraded"  # Ollama down but core works
        startup_issues = startup_issues + ["Ollama unavailable - QA features disabled"]
    else:
        status = "degraded"
        response.status_code = 503

    if not all_healthy:
        logger.warning(f"Health check: {status}, services={services.model_dump()}")

    return HealthResponse(status=status, services=services, startup_issues=startup_issues)
