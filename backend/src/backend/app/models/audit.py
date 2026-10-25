"""AuditLog model."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(Integer, nullable=True)
    details = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = ()
