"""DocumentPage model for storing extracted text per page."""

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from sqlalchemy import Text, DateTime, Integer, Float, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class PageType(StrEnum):
    """Page classification type."""
    NATIVE = "native"
    SCANNED = "scanned"


class DocumentPage(Base):
    """Extracted text storage per page."""

    __tablename__ = "document_pages"

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
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    page_type: Mapped[PageType] = mapped_column(Text, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_document_page"),
        Index("idx_document_pages_doc", "document_id"),
        Index("idx_document_pages_page", "document_id", "page_number"),
    )

    def __repr__(self) -> str:
        return f"<DocumentPage(document_id={self.document_id}, page={self.page_number}, type={self.page_type})>"
