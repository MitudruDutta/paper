"""FastAPI application entry point."""

import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import init_db, close_db
from core.redis import init_redis, close_redis
from core.storage import ensure_storage_dir_exists
from core.rate_limit import RateLimitMiddleware
from api.dependencies import init_qdrant, close_qdrant
from api.routes import health
from api.routes import documents
from api.routes import extraction
from api.routes import retrieval
from api.routes import qa
from api.routes import advanced_qa
from api.routes import multimodal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

VERSION = "0.0.1"


async def _cleanup_on_failure(
    redis_initialized: bool,
    qdrant_initialized: bool,
    db_initialized: bool = False,
) -> None:
    """Clean up successfully initialized services on startup failure."""
    if db_initialized:
        try:
            await close_db()
        except Exception:
            pass
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
    db_initialized = False
    
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
        await _cleanup_on_failure(redis_initialized, False, False)
        sys.exit(1)
    
    try:
        from models.document import Document
        from models.document_page import DocumentPage
        from models.document_chunk import DocumentChunk
        from models.qa_query import QAQuery
        from models.qa_conversation import QAConversation
        from models.qa_message import QAMessage
        from models.document_table import DocumentTable
        from models.document_figure import DocumentFigure
        await init_db()
        db_initialized = True
        logger.info("Database initialized")
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}", extra={"service": "database", "event": "startup_failure"})
        await _cleanup_on_failure(redis_initialized, qdrant_initialized, False)
        sys.exit(1)
    
    # Ensure storage directory exists
    try:
        await ensure_storage_dir_exists()
        logger.info("Storage directory initialized")
    except Exception as e:
        logger.critical(f"Storage initialization failed: {e}", extra={"service": "storage", "event": "startup_failure"})
        await _cleanup_on_failure(redis_initialized, qdrant_initialized, db_initialized)
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

# CORS configuration - use settings-driven origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Rate limiting (after CORS)
app.add_middleware(RateLimitMiddleware)

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(extraction.router)
app.include_router(retrieval.router)
app.include_router(qa.router)
app.include_router(advanced_qa.router)
app.include_router(multimodal.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Paper API",
        "version": VERSION,
    }
