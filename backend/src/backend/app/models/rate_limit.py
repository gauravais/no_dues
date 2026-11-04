"""AuthRateLimit model for persistent DB-backed authentication rate limiting."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Index
from backend.app.core.database import Base


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"

    id = Column(Integer, primary_key=True)
    key = Column(String(255), nullable=False, unique=True)
    count = Column(Integer, nullable=False, default=1)
    reset_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_auth_rate_limits_key", "key", unique=True),
        Index("ix_auth_rate_limits_reset_at", "reset_at"),
    )
