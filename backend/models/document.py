"""Document model definition."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, text, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


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
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    upload_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50), 
        nullable=False, 
        default="pending", 
        index=True
    )

    def __repr__(self) -> str:
        return (
            f"<Document(id={self.id}, filename='{self.filename}', "
            f"status='{self.status}', upload_date='{self.upload_date.isoformat()}')>"
        )
