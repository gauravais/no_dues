"""User model."""
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey,
    Enum as SAEnum, DateTime, CheckConstraint, Index, text
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class UserRole(str, enum.Enum):
    student = "student"
    dept_officer = "dept_officer"
    hod = "hod"
    registrar_accounts = "registrar_accounts"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True)
    full_name = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=True)
    google_sub = Column(String(255), nullable=True, unique=True)
    role = Column(SAEnum(UserRole, name="user_role"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    roster_id = Column(
        Integer, ForeignKey("student_roster.id"), nullable=True, unique=True
    )
    is_active = Column(Boolean, nullable=False, default=True)
    must_change_password = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # dept_officer and hod must have department_id
        CheckConstraint(
            "role NOT IN ('dept_officer', 'hod') OR department_id IS NOT NULL",
            name="ck_user_dept_officer_hod_requires_dept",
        ),
        # student must have roster_id
        CheckConstraint(
            "role != 'student' OR roster_id IS NOT NULL",
            name="ck_user_student_requires_roster",
        ),
        Index("ix_users_email", "email"),
        Index("ix_users_department_id", "department_id"),
        Index("ix_users_roster_id", "roster_id"),
        Index("ix_users_google_sub", "google_sub"),
    )

    department = relationship("Department", back_populates="users")
    roster_entry = relationship("StudentRoster", back_populates="user", foreign_keys=[roster_id])
    hod_clearances = relationship(
        "ClearanceRequest", back_populates="hod_user",
        foreign_keys="ClearanceRequest.hod_user_id"
    )
    decided_approvals = relationship(
        "DepartmentApproval", back_populates="decided_by_user",
        foreign_keys="DepartmentApproval.decided_by"
    )
    issued_certificates = relationship(
        "Certificate", back_populates="hod_user",
        foreign_keys="Certificate.hod_user_id"
    )
