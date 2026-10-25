"""StudentRoster and RosterAssignedDepartment models."""
from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey,
    UniqueConstraint, Index, Numeric
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class StudentRoster(Base):
    __tablename__ = "student_roster"

    id = Column(Integer, primary_key=True)
    registration_number = Column(String(50), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    mobile = Column(String(20), nullable=False)
    address = Column(String(500), nullable=False)
    programme_id = Column(Integer, ForeignKey("programmes.id"), nullable=False)
    is_hosteller = Column(Boolean, nullable=False, default=False)
    security_deposit_amount = Column(Numeric(10, 2), nullable=False, default=0)

    __table_args__ = (
        Index("ix_student_roster_registration_number", "registration_number"),
        Index("ix_student_roster_programme_id", "programme_id"),
    )

    programme = relationship("Programme", back_populates="roster_entries")
    assigned_departments = relationship(
        "RosterAssignedDepartment", back_populates="roster_entry"
    )
    user = relationship("User", back_populates="roster_entry", uselist=False)
    bank_detail = relationship("BankDetail", back_populates="roster_entry", uselist=False)
    clearance_requests = relationship("ClearanceRequest", back_populates="roster_entry")


class RosterAssignedDepartment(Base):
    __tablename__ = "roster_assigned_departments"

    roster_id = Column(Integer, ForeignKey("student_roster.id"), primary_key=True)
    department_id = Column(Integer, ForeignKey("departments.id"), primary_key=True)

    __table_args__ = (
        UniqueConstraint("roster_id", "department_id", name="uq_roster_department"),
    )

    roster_entry = relationship("StudentRoster", back_populates="assigned_departments")
    department = relationship("Department", back_populates="roster_assigned")
