"""FastAPI application entry point."""

import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database import init_db, close_db
from core.redis import init_redis, close_redis
from api.dependencies import init_qdrant, close_qdrant
from api.routes import health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

VERSION = "0.0.1"


async def _cleanup_on_failure(redis_initialized: bool, qdrant_initialized: bool) -> None:
    """Clean up successfully initialized services on startup failure."""
    if qdrant_initialized:
        try:
            close_qdrant()
        except Exception:
            pass
    if redis_initialized:
        try:
            await close_redis()
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with fail-fast for required services."""
    logger.info("Starting Paper API...")
    
    redis_initialized = False
    qdrant_initialized = False
    
    # Required services - fail fast if any cannot initialize
    try:
        await init_redis()
        redis_initialized = True
        logger.info("Redis initialized")
    except Exception as e:
        logger.critical(f"Redis initialization failed: {e}", extra={"service": "redis", "event": "startup_failure"})
        sys.exit(1)
    
    try:
        init_qdrant()
        qdrant_initialized = True
        logger.info("Qdrant initialized")
    except Exception as e:
        logger.critical(f"Qdrant initialization failed: {e}", extra={"service": "qdrant", "event": "startup_failure"})
        await _cleanup_on_failure(redis_initialized, False)
        sys.exit(1)
    
    try:
        from models.document import Document
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}", extra={"service": "database", "event": "startup_failure"})
        await _cleanup_on_failure(redis_initialized, qdrant_initialized)
        sys.exit(1)
    
    # All required services initialized
    app.state.startup_issues = []
    app.state.services_ready = True
    logger.info("Paper API started successfully", extra={"event": "startup_complete"})
    
    yield
    
    # Shutdown
    app.state.services_ready = False
    
    try:
        await close_redis()
    except Exception as e:
        logger.error(f"Failed to close Redis connection: {e}")

    try:
        close_qdrant()
    except Exception as e:
        logger.error(f"Failed to close Qdrant connection: {e}")

    try:
        await close_db()
    except Exception as e:
        logger.error(f"Failed to close database connection: {e}")
        
    logger.info("Paper API shutdown complete")


app = FastAPI(
    title="Paper API",
    version=VERSION,
    lifespan=lifespan,
)

# Initialize state defaults (before lifespan runs)
app.state.startup_issues = []
app.state.services_ready = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Paper API",
        "version": VERSION,
    }
