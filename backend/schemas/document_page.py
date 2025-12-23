"""Pydantic schemas for document page extraction."""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class PageExtractionResult(BaseModel):
    """Result for a single page extraction."""
    page_number: int
    page_type: str
    confidence: float | None
    text_length: int


class ExtractionResponse(BaseModel):
    """Response after text extraction."""
    document_id: uuid.UUID
    total_pages: int
    native_pages: int
    scanned_pages: int
    skipped_pages: int
    failed_pages: int
    low_confidence_pages: int = 0  # Pages with OCR confidence < 0.7
    avg_confidence: float | None = None
    status: str

    model_config = ConfigDict(from_attributes=True)


class ExtractionStatusResponse(BaseModel):
    """Response for extraction status check."""
    document_id: uuid.UUID
    extraction_status: str
    pages_extracted: int
    total_pages: int | None


class DocumentPageDetail(BaseModel):
    """Full page detail response."""
    id: uuid.UUID
    document_id: uuid.UUID
    page_number: int
    page_type: str
    extracted_text: str
    confidence: float | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentPageSummary(BaseModel):
    """Page summary without full text."""
    page_number: int
    page_type: str
    text_length: int
    confidence: float | None

    model_config = ConfigDict(from_attributes=True)
