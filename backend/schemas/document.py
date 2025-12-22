"""Pydantic schemas for document API."""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DocumentUploadResponse(BaseModel):
    """Response after successful document upload."""
    document_id: uuid.UUID
    filename: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class DocumentListItem(BaseModel):
    """Document item in list response."""
    id: uuid.UUID
    filename: str
    status: str
    file_size: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDetail(BaseModel):
    """Full document metadata response."""
    id: uuid.UUID
    filename: str
    file_size: int | None
    mime_type: str | None
    page_count: int | None
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentError(BaseModel):
    """Error response for document operations."""
    error: str
    detail: str | None = None
