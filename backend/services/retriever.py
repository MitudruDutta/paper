"""Retrieval service for semantic search."""

import asyncio
import logging
import uuid

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

from services.embedder import generate_query_embedding, EMBEDDING_DIMENSION

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
    """Store vectors in Qdrant."""
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
    """Synchronous search in thread."""
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
) -> list[tuple[uuid.UUID, float, dict]]:
    """Search for similar chunks using Gemini embeddings."""
    query_embedding = await generate_query_embedding(query)
    
    if query_embedding is None:
        logger.error("Failed to generate query embedding")
        return []
    
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
    
    return await asyncio.to_thread(
        _search_sync, client, query_embedding, search_filter, top_k
    )
