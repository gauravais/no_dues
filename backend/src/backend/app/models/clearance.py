"""ClearanceRequest and DepartmentApproval models."""
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, ForeignKey, Enum as SAEnum,
    DateTime, CheckConstraint, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class ClearanceStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    ACTION_NEEDED = "ACTION_NEEDED"
    HOD_REVIEW = "HOD_REVIEW"
    CLEARED = "CLEARED"
    REFUND_VERIFIED = "REFUND_VERIFIED"


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ClearanceRequest(Base):
    __tablename__ = "clearance_requests"

    id = Column(Integer, primary_key=True)
    roster_id = Column(Integer, ForeignKey("student_roster.id"), nullable=False)
    status = Column(
        SAEnum(ClearanceStatus, name="clearance_status"), nullable=False,
        default=ClearanceStatus.SUBMITTED
    )
    submitted_at = Column(DateTime(timezone=True), nullable=False,
                          default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    hod_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    hod_decided_at = Column(DateTime(timezone=True), nullable=True)
    hod_remarks = Column(String(1000), nullable=True)

    __table_args__ = (
        Index("ix_clearance_requests_roster_id", "roster_id"),
        Index("ix_clearance_requests_status", "status"),
    )

    roster_entry = relationship("StudentRoster", back_populates="clearance_requests")
    hod_user = relationship(
        "User", back_populates="hod_clearances",
        foreign_keys=[hod_user_id]
    )
    approvals = relationship("DepartmentApproval", back_populates="request")
    certificate = relationship("Certificate", back_populates="request", uselist=False)
    refund = relationship("Refund", back_populates="request", uselist=False)


class DepartmentApproval(Base):
    __tablename__ = "department_approvals"

    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey("clearance_requests.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    status = Column(
        SAEnum(ApprovalStatus, name="approval_status"), nullable=False,
        default=ApprovalStatus.PENDING
    )
    remarks = Column(String(1000), nullable=True)
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    resubmission_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("request_id", "department_id", name="uq_approval_request_department"),
        CheckConstraint(
            "status != 'REJECTED' OR (remarks IS NOT NULL AND remarks != '')",
            name="ck_approval_rejected_requires_remarks",
        ),
        Index("ix_department_approvals_request_id", "request_id"),
        Index("ix_department_approvals_department_id", "department_id"),
        Index("ix_department_approvals_status", "status"),
    )

    request = relationship("ClearanceRequest", back_populates="approvals")
    department = relationship("Department", back_populates="approvals")
    decided_by_user = relationship(
        "User", back_populates="decided_approvals",
        foreign_keys=[decided_by]
    )
