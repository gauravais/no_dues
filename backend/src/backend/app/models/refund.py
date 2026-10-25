"""Refund model."""
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, ForeignKey, Enum as SAEnum,
    DateTime, Numeric
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class RefundStatus(str, enum.Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    PROCESSED = "PROCESSED"


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True)
    request_id = Column(
        Integer, ForeignKey("clearance_requests.id"), nullable=False, unique=True
    )
    deposit_amount = Column(Numeric(10, 2), nullable=False)
    deductions = Column(Numeric(10, 2), nullable=False, default=0)
    final_amount = Column(Numeric(10, 2), nullable=False)
    status = Column(
        SAEnum(RefundStatus, name="refund_status"), nullable=False,
        default=RefundStatus.PENDING_VERIFICATION
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    request = relationship("ClearanceRequest", back_populates="refund")
