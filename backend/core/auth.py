"""Authentication middleware for API protection."""

import hmac
import logging
import os
from typing import Callable

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError

logger = logging.getLogger(__name__)

# Clerk configuration
CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL")  # e.g., https://your-app.clerk.accounts.dev/.well-known/jwks.json
CLERK_ISSUER = os.getenv("CLERK_ISSUER")  # e.g., https://your-app.clerk.accounts.dev

# Cache for JWKS
_jwks_cache: dict | None = None

# Endpoints that require authentication
PROTECTED_ENDPOINTS = [
    "/ask",
    "/documents/{document_id}/ask",
    "/search",
]

# Endpoints that are always public
PUBLIC_ENDPOINTS = {
    "/",
    "/health",
    "/health/live",
    "/health/ready",
    "/health/deps",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
}

# Prefixes that are always public
PUBLIC_PREFIXES = [
    "/docs",
    "/redoc",
    "/openapi",
]


async def get_jwks() -> dict | None:
    """Fetch and cache Clerk JWKS."""
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    
    if not CLERK_JWKS_URL:
        return None
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(CLERK_JWKS_URL)
            response.raise_for_status()
            _jwks_cache = response.json()
            return _jwks_cache
    except Exception as e:
        logger.error(f"Failed to fetch JWKS: {e}")
        return None


def is_protected_path(path: str) -> bool:
    """Check if path requires authentication."""
    # Exact public endpoints
    if path in PUBLIC_ENDPOINTS:
        return False
    
    # Public prefixes
    for prefix in PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return False
    
    # Check protected patterns
    for endpoint in PROTECTED_ENDPOINTS:
        # Handle path parameters like {document_id}
        pattern_parts = endpoint.split("{")
        if pattern_parts[0] in path or path == endpoint:
            return True
    
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Auth middleware that validates Clerk JWT tokens.
    
    Falls back to simple token presence check if Clerk is not configured.
    """
    
    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        self.api_key = os.getenv("API_KEY")  # Optional API key auth
    
    async def dispatch(self, request: Request, call_next: Callable):
        if not self.enabled:
            return await call_next(request)
        
        path = request.url.path
        
        # Skip auth for public endpoints
        if not is_protected_path(path):
            return await call_next(request)
        
        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        
        # API key auth (for server-to-server)
        if self.api_key:
            api_key_header = request.headers.get("X-API-Key") or ""
            if hmac.compare_digest(api_key_header, self.api_key):
                return await call_next(request)
        
        # Bearer token auth
        if not auth_header:
            logger.warning(f"Missing auth header for {path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not auth_header.startswith("Bearer "):
            logger.warning(f"Invalid auth header format for {path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authentication format"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        # Validate JWT with Clerk if configured
        if CLERK_JWKS_URL and CLERK_ISSUER:
            jwks = await get_jwks()
            if jwks:
                try:
                    # Decode and validate JWT
                    payload = jwt.decode(
                        token,
                        jwks,
                        algorithms=["RS256"],
                        issuer=CLERK_ISSUER,
                        options={"verify_aud": False},  # Clerk doesn't always set aud
                    )
                    # Attach user info to request state
                    request.state.user_id = payload.get("sub")
                    return await call_next(request)
                except JWTError as e:
                    logger.warning(f"JWT validation failed for {path}: {e}")
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid token"},
                        headers={"WWW-Authenticate": "Bearer"},
                    )
        
        # Fallback: simple token presence check (dev mode)
        if not token or len(token) < 10:
            logger.warning(f"Invalid token for {path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.debug(f"Token accepted (no JWKS validation) for {path}")
        return await call_next(request)
