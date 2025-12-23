"""Conversation model for multi-turn QA."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class QAConversation(Base):
    """Conversation session for follow-up questions."""

    __tablename__ = "qa_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    messages: Mapped[list["QAMessage"]] = relationship(
        "QAMessage",
        back_populates="conversation",
        order_by="QAMessage.created_at",
        cascade="all, delete-orphan",
    )
