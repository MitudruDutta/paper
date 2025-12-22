"""Retrieval service for semantic search."""

import asyncio
import logging
import uuid

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
    Filter,
    FilterSelector,
    FieldCondition,
    MatchAny,
)

from services.embedder import generate_embedding, EMBEDDING_DIMENSION

logger = logging.getLogger(__name__)

COLLECTION_NAME = "document_chunks"


def ensure_collection_exists(client: QdrantClient) -> None:
    """Create Qdrant collection if it doesn't exist."""
    collections = client.get_collections().collections
    exists = any(c.name == COLLECTION_NAME for c in collections)
    
    if not exists:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )
        logger.info(f"Created Qdrant collection: {COLLECTION_NAME}")


def store_vectors(
    client: QdrantClient,
    points: list[tuple[uuid.UUID, list[float], dict]],
) -> int:
    """
    Store vectors in Qdrant.
    
    Args:
        client: Qdrant client
        points: List of (id, vector, payload) tuples
    
    Returns:
        Number of points stored
    """
    ensure_collection_exists(client)
    
    qdrant_points = [
        PointStruct(
            id=str(point_id),
            vector=vector,
            payload=payload,
        )
        for point_id, vector, payload in points
    ]
    
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=qdrant_points,
    )
    
    logger.info(f"Stored {len(qdrant_points)} vectors in Qdrant")
    return len(qdrant_points)


def delete_document_vectors(client: QdrantClient, document_id: uuid.UUID) -> None:
    """Delete all vectors for a document."""
    ensure_collection_exists(client)
    
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchAny(any=[str(document_id)]),
                    )
                ]
            )
        ),
    )
    logger.info(f"Deleted vectors for document {document_id}")


def _search_sync(
    client: QdrantClient,
    query_embedding: list[float],
    search_filter: Filter | None,
    top_k: int,
) -> list[tuple[uuid.UUID, float, dict]]:
    """Synchronous search (runs in thread). Also ensures collection exists."""
    ensure_collection_exists(client)
    
    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_embedding,
        query_filter=search_filter,
        limit=top_k,
    )
    return [
        (uuid.UUID(r.id), r.score, r.payload)
        for r in results
    ]


async def search_similar(
    client: QdrantClient,
    query: str,
    document_ids: list[uuid.UUID] | None = None,
    top_k: int = 5,
    http_client: httpx.AsyncClient | None = None,
) -> list[tuple[uuid.UUID, float, dict]]:
    """
    Search for similar chunks.
    
    Args:
        client: Qdrant client
        query: Search query text
        document_ids: Optional list of document IDs to filter
        top_k: Number of results to return
        http_client: Optional shared httpx client for embedding generation
    
    Returns:
        List of (chunk_id, score, payload) tuples
    """
    # Generate query embedding
    if http_client is not None:
        query_embedding = await generate_embedding(http_client, query)
    else:
        async with httpx.AsyncClient(timeout=60.0) as local_client:
            query_embedding = await generate_embedding(local_client, query)
    
    if query_embedding is None:
        logger.error("Failed to generate query embedding")
        return []
    
    # Build filter if document_ids provided
    search_filter = None
    if document_ids:
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="document_id",
                    match=MatchAny(any=[str(d) for d in document_ids]),
                )
            ]
        )
    
    # Run synchronous search in thread (includes ensure_collection_exists)
    return await asyncio.to_thread(
        _search_sync, client, query_embedding, search_filter, top_k
    )
