"""Concurrency control for expensive operations."""

import asyncio
import logging

logger = logging.getLogger(__name__)

# Semaphore to limit concurrent LLM requests
# Ollama can only handle 1-2 concurrent requests efficiently
_llm_semaphore: asyncio.Semaphore | None = None
MAX_CONCURRENT_LLM = 2


def get_llm_semaphore() -> asyncio.Semaphore:
    """Get or create the LLM semaphore."""
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM)
    return _llm_semaphore


async def with_llm_limit(coro):
    """Execute coroutine with LLM concurrency limit."""
    semaphore = get_llm_semaphore()
    async with semaphore:
        return await coro


class QueueFullError(Exception):
    """Raised when too many requests are waiting."""
    pass


async def with_llm_limit_or_reject(coro, timeout: float = 60.0):
    """
    Execute with LLM limit, or reject if queue is full.
    
    Args:
        coro: Coroutine to execute
        timeout: Max time to wait for semaphore
    
    Raises:
        QueueFullError: If timeout waiting for semaphore
    """
    semaphore = get_llm_semaphore()
    
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("LLM queue timeout - rejecting request")
        raise QueueFullError("Server busy, try again later")
    
    try:
        return await coro
    finally:
        semaphore.release()
