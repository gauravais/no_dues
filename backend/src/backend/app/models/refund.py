"""Refund model."""
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, ForeignKey, Enum as SAEnum,
    DateTime, Numeric, Date
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class RefundStatus(str, enum.Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    PROCESSED = "PROCESSED"
    PAYMENT_FAILED = "PAYMENT_FAILED"


class PaymentMode(str, enum.Enum):
    NEFT = "NEFT"
    IMPS = "IMPS"
    UPI = "UPI"
    CHEQUE = "CHEQUE"
    OTHER = "OTHER"


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
    payment_reference = Column(String(100), nullable=True)
    updated_at = Column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Verification details
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    accounts_note = Column(String(500), nullable=True)

    # Payment details
    paid_at = Column(DateTime(timezone=True), nullable=True)
    paid_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    paid_on = Column(Date, nullable=True)
    payment_mode = Column(String(20), nullable=True)

    # Failure details
    failure_reason = Column(String(500), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)

    # Student feedback and issue resolution
    student_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    student_issue_note = Column(String(500), nullable=True)
    student_issue_at = Column(DateTime(timezone=True), nullable=True)
    student_issue_resolved_at = Column(DateTime(timezone=True), nullable=True)

    request = relationship("ClearanceRequest", back_populates="refund")
    verified_by_user = relationship("User", foreign_keys=[verified_by_user_id])
    paid_by_user = relationship("User", foreign_keys=[paid_by_user_id])
