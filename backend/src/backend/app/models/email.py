"""EmailOutbox model for outbox pattern email delivery."""
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class OutboxStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class EmailOutbox(Base):
    __tablename__ = "email_outbox"

    id = Column(Integer, primary_key=True)
    to_email = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    kind = Column(String(50), nullable=False)
    related_request_id = Column(
        Integer,
        ForeignKey("clearance_requests.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(String(20), nullable=False, default=OutboxStatus.PENDING)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    sent_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_email_outbox_status", "status"),
        Index("ix_email_outbox_created_at", "created_at"),
        Index("ix_email_outbox_to_email", "to_email"),
    )

    request = relationship("ClearanceRequest", foreign_keys=[related_request_id])
