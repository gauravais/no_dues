"""SignupOTP model for tracking student self-registration OTPs."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Index
from backend.app.core.database import Base


class SignupOTP(Base):
    __tablename__ = "signup_otps"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False)
    registration_number = Column(String(50), nullable=False)
    code_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_signup_otps_email", "email"),
    )
