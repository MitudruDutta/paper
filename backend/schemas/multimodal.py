"""Pydantic schemas for multimodal extraction (Phase 6)."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class TableData(BaseModel):
    """Extracted table data."""
    id: uuid.UUID
    page_number: int
    title: str | None
    row_count: int
    column_count: int
    markdown: str


class FigureData(BaseModel):
    """Extracted figure data."""
    id: uuid.UUID
    page_number: int
    figure_type: str
    description: str


class ExtractVisualsRequest(BaseModel):
    """Request for visual extraction."""
    force: bool = Field(default=False, description="Re-extract even if already done")


class ExtractVisualsResponse(BaseModel):
    """Response from visual extraction."""
    document_id: uuid.UUID
    tables_extracted: int
    figures_extracted: int
    pages_processed: int
    status: Literal["completed", "partial", "failed", "processing"]
    errors: list[str] = []


class VisualSource(BaseModel):
    """Source citation for visual elements."""
    source_type: Literal["text", "table", "figure"]
    document_id: uuid.UUID
    document_name: str
    page_number: int
    source_id: uuid.UUID | None = None  # table_id or figure_id


class MultimodalAnswerResponse(BaseModel):
    """Response with multimodal sources."""
    answer: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    sources: list[VisualSource]
    conversation_id: uuid.UUID
    conversation_persisted: bool = True
