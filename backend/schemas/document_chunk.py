"""Pydantic schemas for document chunks and search."""

import uuid
from pydantic import BaseModel, ConfigDict, Field


class ChunkInfo(BaseModel):
    """Chunk information."""
    chunk_index: int
    page_start: int
    page_end: int
    content: str
    token_count: int


class IndexingResponse(BaseModel):
    """Response after indexing a document."""
    document_id: uuid.UUID
    chunks_created: int
    status: str

    model_config = ConfigDict(from_attributes=True)


class SearchRequest(BaseModel):
    """Search request body."""
    query: str = Field(..., min_length=1, max_length=1000)
    document_ids: list[uuid.UUID] | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    """Single search result."""
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    page_start: int
    page_end: int
    score: float

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    """Search response."""
    results: list[SearchResult]
    query: str
