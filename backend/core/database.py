"""Database configuration and session management."""

import asyncio
import logging
import ssl
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from core.config import settings

logger = logging.getLogger(__name__)

DB_CHECK_TIMEOUT_SECONDS = 3.0


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


def create_ssl_context() -> ssl.SSLContext:
    """Create SSL context for Supabase connection."""
    ssl_context = ssl.create_default_context()
    
    if settings.env == "development":
        logger.warning("SSL certificate verification disabled in development mode.")
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    else:
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        
        if settings.supabase_ca_cert_path:
            try:
                ssl_context.load_verify_locations(settings.supabase_ca_cert_path)
            except (FileNotFoundError, ssl.SSLError, Exception) as e:
                logger.error(f"Failed to load SSL certificate from {settings.supabase_ca_cert_path}: {e}")
                raise RuntimeError(f"Failed to load SSL certificate: {e}") from e
            
    return ssl_context


connect_args = {}
if settings.supabase_db_ssl:
    connect_args["ssl"] = create_ssl_context()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args=connect_args,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=settings.db_pool_pre_ping,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Initialize database tables."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_db() -> None:
    """Close database connection pool."""
    await engine.dispose()
    logger.info("Database connection closed")


async def check_database_connection() -> bool:
    """Check if database is reachable."""
    try:
        async def _check():
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

        await asyncio.wait_for(_check(), timeout=DB_CHECK_TIMEOUT_SECONDS)
        return True
    except asyncio.TimeoutError:
        logger.error(f"Database connection check timed out after {DB_CHECK_TIMEOUT_SECONDS}s.")
        return False
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    async with async_session_maker() as session:
        yield session
