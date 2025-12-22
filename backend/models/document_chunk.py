"""DocumentChunk model for storing chunk metadata."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Text, DateTime, Integer, ForeignKey, UniqueConstraint, Index, CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class DocumentChunk(Base):
    """
    Chunk metadata storage.
    
    Each chunk represents a semantic segment of a document's text,
    with page boundary tracking for source attribution.
    """

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk"),
        Index("idx_chunks_document", "document_id"),
        Index("idx_chunks_pages", "document_id", "page_start", "page_end"),
        CheckConstraint("page_start <= page_end", name="ck_page_range"),
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk(document_id={self.document_id}, index={self.chunk_index})>"
