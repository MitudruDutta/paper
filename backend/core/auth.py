"""Authentication middleware for API protection."""

import hmac
import logging
import os
from typing import Callable

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

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
    Simple auth middleware that validates Authorization header.
    
    For production, integrate with Clerk/Firebase JWT validation.
    Currently checks for presence of Bearer token.
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
        
        # TODO: Validate JWT token with Clerk/Firebase
        # For now, just check token is non-empty
        # In production, replace with actual JWT validation:
        #   - Verify signature
        #   - Check expiration
        #   - Validate issuer/audience
        
        if not token or len(token) < 10:
            logger.warning(f"Invalid token for {path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Token present - allow request
        # In production, decode and attach user info to request.state
        return await call_next(request)
