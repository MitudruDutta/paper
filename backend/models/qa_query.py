"""QAQuery model for storing question-answer audit trail."""

import hashlib
import uuid
from datetime import datetime, timezone
from sqlalchemy import Text, DateTime, ForeignKey, Index, text, String
from sqlalchemy.dialects.postgresql import UUID, ARRAY, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class QAQuery(Base):
    """Audit trail for question-answering interactions."""

    __tablename__ = "qa_queries"

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
    idempotency_key: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    cited_pages: Mapped[list[int]] = mapped_column(ARRAY(INTEGER), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_qa_queries_document", "document_id"),
    )

    @staticmethod
    def generate_idempotency_key(document_id: uuid.UUID, question: str, answer: str) -> str:
        """Generate deterministic key from content."""
        content = f"{document_id}:{question}:{answer}"
        return hashlib.sha256(content.encode()).hexdigest()

    def __repr__(self) -> str:
        return f"<QAQuery(document_id={self.document_id}, question='{self.question[:30]}...')>"
