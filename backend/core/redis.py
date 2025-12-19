"""Redis connection management."""

import logging
from redis.asyncio import Redis

from core.config import settings

logger = logging.getLogger(__name__)

redis_client: Redis | None = None


async def init_redis() -> None:
    """Initialize Redis connection."""
    global redis_client
    try:
        redis_client = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            db=settings.redis_db,
            socket_timeout=settings.redis_socket_timeout,
            socket_connect_timeout=settings.redis_connect_timeout,
            decode_responses=True,
        )
        await redis_client.ping()
        logger.info("Redis connection established successfully")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise


async def close_redis() -> None:
    """Close Redis connection."""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None
        logger.info("Redis connection closed")


async def check_redis_connection() -> bool:
    """Check if Redis is reachable."""
    global redis_client
    try:
        if redis_client:
            await redis_client.ping()
            return True
        return False
    except Exception as e:
        logger.error(f"Redis connection check failed: {e}")
        return False


def get_redis() -> Redis:
    """Get Redis client instance."""
    if redis_client is None:
        raise RuntimeError("Redis client not initialized")
    return redis_client
