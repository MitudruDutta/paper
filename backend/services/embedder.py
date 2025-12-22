"""Embedding service using Ollama."""

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Ollama configuration from environment
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "172.17.0.1")
OLLAMA_URL = f"http://{OLLAMA_HOST}:11434"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

def _parse_int_env(key: str, default: int) -> int:
    """Parse integer from environment with fallback."""
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        logger.warning(f"Invalid {key}={val}, using default {default}")
        return default

EMBEDDING_DIMENSION = _parse_int_env("EMBEDDING_DIMENSION", 768)
EMBEDDING_BATCH_SIZE = _parse_int_env("EMBEDDING_BATCH_SIZE", 10)


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""
    chunk_id: uuid.UUID
    embedding: list[float]
    success: bool
    error: str | None = None


async def generate_embedding(client: httpx.AsyncClient, text: str) -> list[float] | None:
    """Generate embedding for a single text using Ollama."""
    try:
        response = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBEDDING_MODEL, "prompt": text},
        )
        response.raise_for_status()
        data = response.json()
        return data["embedding"]
    except httpx.HTTPStatusError as e:
        logger.error(
            f"Embedding HTTP error: {e.__class__.__name__} "
            f"status={e.response.status_code} body={e.response.text[:200]}"
        )
        return None
    except httpx.RequestError as e:
        logger.error(f"Embedding request error: {e.__class__.__name__} {e}")
        raise  # Re-raise transient network errors
    except (KeyError, ValueError) as e:
        logger.error(f"Embedding parse error: {e.__class__.__name__} {e}")
        return None


async def generate_embeddings_batch(texts: list[str]) -> list[list[float] | None]:
    """Generate embeddings for multiple texts."""
    results: list[list[float] | None] = []
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = texts[i:i + EMBEDDING_BATCH_SIZE]
            
            # Process batch concurrently
            tasks = [generate_embedding(client, text) for text in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Embedding failed for text index {i + j}: {result.__class__.__name__}: {result}")
                    results.append(None)
                else:
                    results.append(result)
    
    return results


def _is_zero_vector(embedding: list[float], tolerance: float = 1e-9) -> bool:
    """Check if embedding is all zeros."""
    return all(abs(v) < tolerance for v in embedding)


async def embed_chunks(
    chunks: list[tuple[uuid.UUID, str]],
) -> list[EmbeddingResult]:
    """
    Generate embeddings for chunks.
    
    Args:
        chunks: List of (chunk_id, content) tuples
    
    Returns:
        List of EmbeddingResult objects
    """
    if not chunks:
        return []
    
    chunk_ids = [c[0] for c in chunks]
    texts = [c[1] for c in chunks]
    
    logger.info(f"Generating embeddings for {len(chunks)} chunks")
    
    embeddings = await generate_embeddings_batch(texts)
    
    results = []
    for chunk_id, embedding in zip(chunk_ids, embeddings):
        # Case 1: Embedding is None or not a list
        if embedding is None or not isinstance(embedding, list):
            results.append(EmbeddingResult(
                chunk_id=chunk_id,
                embedding=[],
                success=False,
                error="Embedding generation failed",
            ))
        # Case 2: Wrong dimension
        elif len(embedding) != EMBEDDING_DIMENSION:
            results.append(EmbeddingResult(
                chunk_id=chunk_id,
                embedding=[],
                success=False,
                error=f"Invalid embedding dimension: {len(embedding)} != {EMBEDDING_DIMENSION}",
            ))
        # Case 3: Zero vector
        elif _is_zero_vector(embedding):
            results.append(EmbeddingResult(
                chunk_id=chunk_id,
                embedding=[],
                success=False,
                error="Zero-vector embedding",
            ))
        # Success
        else:
            results.append(EmbeddingResult(
                chunk_id=chunk_id,
                embedding=embedding,
                success=True,
            ))
    
    success_count = sum(1 for r in results if r.success)
    logger.info(f"Generated {success_count}/{len(chunks)} embeddings successfully")
    
    return results
