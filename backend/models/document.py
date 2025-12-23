"""Document model definition."""

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from sqlalchemy import Text, DateTime, BigInteger, Integer, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class DocumentStatus(StrEnum):
    """Document status lifecycle values."""
    UPLOADED = "uploaded"
    VALIDATED = "validated"
    FAILED = "failed"


class Document(Base):
    """
    Document table model.
    
    Note: 'pgcrypto' extension must be enabled in the database for server-side UUID generation.
    Run: CREATE EXTENSION IF NOT EXISTS "pgcrypto";
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    stored_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Text,
        nullable=False, 
        default=DocumentStatus.UPLOADED, 
        index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    # Visual extraction tracking
    visual_extraction_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_pages_processed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visual_extraction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Document(id={self.id}, filename='{self.filename}', "
            f"status='{self.status}', created_at='{self.created_at.isoformat()}')>"
        )
