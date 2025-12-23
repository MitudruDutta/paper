"""Message model for conversation turns."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Text, DateTime, ForeignKey, Index, text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY, INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class QAMessage(Base):
    """Single message in a conversation."""

    __tablename__ = "qa_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("qa_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    cited_pages: Mapped[list[int] | None] = mapped_column(ARRAY(INTEGER), nullable=True)
    document_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    conversation: Mapped["QAConversation"] = relationship(
        "QAConversation",
        back_populates="messages",
    )

    __table_args__ = (
        CheckConstraint("role in ('user', 'assistant')", name="valid_role"),
        Index("idx_qa_messages_conversation", "conversation_id"),
        Index("idx_qa_messages_created", "conversation_id", "created_at"),
    )
