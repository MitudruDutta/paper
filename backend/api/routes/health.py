"""Health check endpoints for observability."""

import asyncio
import logging
import os
from enum import Enum

import httpx
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from core.database import check_database_connection
from core.redis import check_redis_connection
from core.metrics import metrics
from api.dependencies import check_qdrant_connection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "172.17.0.1")
OLLAMA_URL = f"http://{OLLAMA_HOST}:11434"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ServiceHealth(BaseModel):
    """Individual service health."""
    status: HealthStatus
    latency_ms: float | None = None
    error: str | None = None


class DependencyHealth(BaseModel):
    """All dependency health statuses."""
    database: ServiceHealth
    redis: ServiceHealth
    qdrant: ServiceHealth
    ollama: ServiceHealth


class HealthResponse(BaseModel):
    """Full health check response."""
    status: HealthStatus
    services: DependencyHealth
    startup_issues: list[str] = []


class LivenessResponse(BaseModel):
    """Liveness probe response."""
    status: str
    pid: int


class ReadinessResponse(BaseModel):
    """Readiness probe response."""
    status: str
    ready: bool
    reason: str | None = None


async def check_service_health(
    name: str,
    check_func,
    is_async: bool = True,
    timeout: float = 5.0,
) -> ServiceHealth:
    """Check a service's health with timing."""
    import time
    start = time.perf_counter()
    try:
        if is_async:
            result = await asyncio.wait_for(check_func(), timeout=timeout)
        else:
            result = await asyncio.wait_for(
                asyncio.to_thread(check_func), timeout=timeout
            )
        latency_ms = (time.perf_counter() - start) * 1000
        
        if result:
            return ServiceHealth(status=HealthStatus.HEALTHY, latency_ms=round(latency_ms, 2))
        return ServiceHealth(status=HealthStatus.UNHEALTHY, latency_ms=round(latency_ms, 2), error="Check returned false")
    except asyncio.TimeoutError:
        return ServiceHealth(status=HealthStatus.UNHEALTHY, error=f"Timeout after {timeout}s")
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        logger.error(f"{name} health check failed: {e}")
        return ServiceHealth(status=HealthStatus.UNHEALTHY, latency_ms=round(latency_ms, 2), error=str(e)[:100])


async def check_ollama_health() -> bool:
    """Check if Ollama is reachable."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(f"{OLLAMA_URL}/api/tags")
        return response.status_code == 200


@router.get("/health/live", response_model=LivenessResponse)
async def liveness_probe() -> LivenessResponse:
    """
    Liveness probe - is the process alive?
    
    Returns 200 if the process is running.
    Used by orchestrators to detect hung processes.
    """
    return LivenessResponse(status="alive", pid=os.getpid())


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_probe(request: Request, response: Response) -> ReadinessResponse:
    """
    Readiness probe - can the service handle requests?
    
    Returns 200 if ready, 503 if not ready.
    Used by load balancers to route traffic.
    """
    services_ready = getattr(request.app.state, "services_ready", False)
    
    if not services_ready:
        response.status_code = 503
        return ReadinessResponse(
            status="not_ready",
            ready=False,
            reason="Services not initialized",
        )
    
    return ReadinessResponse(status="ready", ready=True)


@router.get("/health/deps", response_model=DependencyHealth)
async def dependency_health(response: Response) -> DependencyHealth:
    """
    Detailed dependency health check.
    
    Returns health status and latency for each dependency.
    """
    db_health, redis_health, qdrant_health, ollama_health = await asyncio.gather(
        check_service_health("database", check_database_connection, is_async=True),
        check_service_health("redis", check_redis_connection, is_async=True),
        check_service_health("qdrant", check_qdrant_connection, is_async=False),
        check_service_health("ollama", check_ollama_health, is_async=True),
    )

    deps = DependencyHealth(
        database=db_health,
        redis=redis_health,
        qdrant=qdrant_health,
        ollama=ollama_health,
    )

    # Set 503 if any core service is unhealthy
    core_unhealthy = any(
        s.status == HealthStatus.UNHEALTHY
        for s in [db_health, redis_health, qdrant_health]
    )
    if core_unhealthy:
        response.status_code = 503

    return deps


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request, response: Response) -> HealthResponse:
    """
    Comprehensive health check for all dependencies.
    
    Returns:
    - 200 "healthy": All services operational
    - 200 "degraded": Core services OK, optional services down
    - 503 "unhealthy": Core services down
    """
    startup_issues: list[str] = getattr(request.app.state, "startup_issues", [])
    services_ready: bool = getattr(request.app.state, "services_ready", False)

    if not services_ready:
        response.status_code = 503
        return HealthResponse(
            status=HealthStatus.UNHEALTHY,
            services=DependencyHealth(
                database=ServiceHealth(status=HealthStatus.UNHEALTHY, error="Not initialized"),
                redis=ServiceHealth(status=HealthStatus.UNHEALTHY, error="Not initialized"),
                qdrant=ServiceHealth(status=HealthStatus.UNHEALTHY, error="Not initialized"),
                ollama=ServiceHealth(status=HealthStatus.UNHEALTHY, error="Not initialized"),
            ),
            startup_issues=startup_issues or ["Services not initialized"],
        )

    # Check all services
    db_health, redis_health, qdrant_health, ollama_health = await asyncio.gather(
        check_service_health("database", check_database_connection, is_async=True),
        check_service_health("redis", check_redis_connection, is_async=True),
        check_service_health("qdrant", check_qdrant_connection, is_async=False),
        check_service_health("ollama", check_ollama_health, is_async=True),
    )

    services = DependencyHealth(
        database=db_health,
        redis=redis_health,
        qdrant=qdrant_health,
        ollama=ollama_health,
    )

    # Determine overall status
    core_healthy = all(
        s.status == HealthStatus.HEALTHY
        for s in [db_health, redis_health, qdrant_health]
    )
    all_healthy = core_healthy and ollama_health.status == HealthStatus.HEALTHY

    issues = list(startup_issues)
    if ollama_health.status != HealthStatus.HEALTHY:
        issues.append("Ollama unavailable - QA features may fail")

    if all_healthy:
        status = HealthStatus.HEALTHY
    elif core_healthy:
        status = HealthStatus.DEGRADED
    else:
        status = HealthStatus.UNHEALTHY
        response.status_code = 503

    return HealthResponse(status=status, services=services, startup_issues=issues)


@router.get("/metrics")
async def get_metrics() -> dict:
    """
    Get application metrics.
    
    Returns aggregated metrics for monitoring.
    """
    return metrics.get_all()
