"""Pydantic schemas for advanced QA (Phase 5)."""

import uuid

from pydantic import BaseModel, Field, model_validator


class AdvancedQuestionRequest(BaseModel):
    """Request for multi-document QA with conversation support."""
    question: str = Field(..., min_length=1, max_length=1000)
    document_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=10)
    conversation_id: uuid.UUID | None = None


class DocumentSource(BaseModel):
    """Source citation with document attribution."""
    document_id: uuid.UUID
    document_name: str
    page_start: int
    page_end: int
    chunk_id: uuid.UUID

    @model_validator(mode="after")
    def validate_page_range(self):
        if self.page_start > self.page_end:
            raise ValueError("page_start must be <= page_end")
        return self


class AdvancedAnswerResponse(BaseModel):
    """Response with confidence and multi-document sources."""
    answer: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    sources: list[DocumentSource]
    conversation_id: uuid.UUID
    conversation_persisted: bool = True


class ConversationContext(BaseModel):
    """Context extracted from conversation history."""
    entities: list[str]
    last_question: str | None
    last_answer: str | None
    rewritten_question: str
