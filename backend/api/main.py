"""FastAPI application entry point."""

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Paper API...")
    
    try:
        await init_redis()
        logger.info("Redis initialized")
    except Exception as e:
        logger.error(f"Redis initialization failed: {e}")
    
    try:
        init_qdrant()
        logger.info("Qdrant initialized")
    except Exception as e:
        logger.error(f"Qdrant initialization failed: {e}")
    
    try:
        from models.document import Document
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    
    logger.info("Paper API started successfully")
    
    yield
    
    # Shutdown
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
