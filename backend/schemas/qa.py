"""Pydantic schemas for question-answering."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class QuestionRequest(BaseModel):
    """Request body for asking a question."""
    question: str = Field(..., min_length=1, max_length=500)


class SourceInfo(BaseModel):
    """Citation source information."""
    page_start: int
    page_end: int
    chunk_id: uuid.UUID

    @model_validator(mode="after")
    def validate_page_range(self):
        if self.page_start > self.page_end:
            raise ValueError("page_start must be <= page_end")
        return self


class AnswerResponse(BaseModel):
    """Response containing answer and sources."""
    answer: str
    sources: list[SourceInfo]
    confidence: Literal["high", "medium", "low"] = "high"
