"""Rate limiting middleware using Redis."""

import logging
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from core.redis import get_redis

logger = logging.getLogger(__name__)

# Rate limit settings
RATE_LIMIT_REQUESTS = 10  # requests per window
RATE_LIMIT_WINDOW = 60  # seconds
QA_RATE_LIMIT_REQUESTS = 5  # stricter for QA (LLM calls)
QA_RATE_LIMIT_WINDOW = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting using Redis."""
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)
        
        # Get client identifier (IP or forwarded IP)
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        
        # Determine rate limit based on endpoint
        if "/ask" in request.url.path:
            limit = QA_RATE_LIMIT_REQUESTS
            window = QA_RATE_LIMIT_WINDOW
            key_prefix = "ratelimit:qa"
        else:
            limit = RATE_LIMIT_REQUESTS
            window = RATE_LIMIT_WINDOW
            key_prefix = "ratelimit:api"
        
        key = f"{key_prefix}:{client_ip}"
        
        try:
            redis = get_redis()
            
            # Atomic increment - returns new value after increment
            current = await redis.incr(key)
            
            if current == 1:
                # First request in window - set expiry
                await redis.expire(key, window)
            elif current > limit:
                # Rate limit exceeded
                ttl = await redis.ttl(key)
                logger.warning(f"Rate limit exceeded for {client_ip} on {request.url.path}")
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Try again in {ttl} seconds.",
                    headers={"Retry-After": str(ttl)},
                )
                
        except HTTPException:
            raise
        except Exception as e:
            # Don't block requests if Redis fails
            logger.error(f"Rate limit check failed: {e}")
        
        return await call_next(request)
