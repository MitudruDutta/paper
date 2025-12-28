"""Embedding service using Gemini."""

import asyncio
import logging
import uuid
from dataclasses import dataclass

import google.generativeai as genai

from core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "models/text-embedding-004"
EMBEDDING_DIMENSION = 768
EMBEDDING_CONCURRENCY = 5

# One-time configuration
_configured = False


def _ensure_configured():
    """Configure Gemini API once."""
    global _configured
    if _configured:
        return
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not configured")
    genai.configure(api_key=settings.gemini_api_key)
    _configured = True


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""
    chunk_id: uuid.UUID
    embedding: list[float]
    success: bool
    error: str | None = None


def _embed_sync(text: str, task_type: str) -> list[float] | None:
    """Synchronous embedding call."""
    _ensure_configured()
    result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=text,
        task_type=task_type,
    )
    return result['embedding']


async def generate_embedding(text: str) -> list[float] | None:
    """Generate embedding for document text using Gemini."""
    try:
        return await asyncio.to_thread(_embed_sync, text, "retrieval_document")
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return None


async def generate_query_embedding(text: str) -> list[float] | None:
    """Generate embedding for a query using Gemini."""
    try:
        return await asyncio.to_thread(_embed_sync, text, "retrieval_query")
    except Exception as e:
        logger.error(f"Query embedding error: {e}")
        return None


def _is_zero_vector(embedding: list[float], tolerance: float = 1e-9) -> bool:
    """Check if embedding is all zeros."""
    return all(abs(v) < tolerance for v in embedding)


async def embed_chunks(
    chunks: list[tuple[uuid.UUID, str]],
) -> list[EmbeddingResult]:
    """Generate embeddings for chunks using Gemini with concurrency."""
    if not chunks:
        return []
    
    logger.info(f"Generating embeddings for {len(chunks)} chunks")
    
    semaphore = asyncio.Semaphore(EMBEDDING_CONCURRENCY)
    
    async def embed_one(chunk_id: uuid.UUID, content: str) -> EmbeddingResult:
        async with semaphore:
            embedding = await generate_embedding(content)
        
        if embedding is None:
            return EmbeddingResult(
                chunk_id=chunk_id, embedding=[], success=False,
                error="Embedding generation failed",
            )
        if len(embedding) != EMBEDDING_DIMENSION:
            return EmbeddingResult(
                chunk_id=chunk_id, embedding=[], success=False,
                error=f"Invalid dimension: {len(embedding)}",
            )
        if _is_zero_vector(embedding):
            return EmbeddingResult(
                chunk_id=chunk_id, embedding=[], success=False,
                error="Zero-vector embedding",
            )
        return EmbeddingResult(chunk_id=chunk_id, embedding=embedding, success=True)
    
    results = await asyncio.gather(*[embed_one(cid, content) for cid, content in chunks])
    
    success_count = sum(1 for r in results if r.success)
    logger.info(f"Generated {success_count}/{len(chunks)} embeddings")
    
    return list(results)
