"""Faculty, Department, and Programme models."""
import enum
from sqlalchemy import (
    Column, Integer, String, ForeignKey, Enum as SAEnum, CheckConstraint, Index
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class DepartmentKind(str, enum.Enum):
    academic = "academic"
    service = "service"


class DepartmentApplicability(str, enum.Enum):
    ALWAYS = "ALWAYS"
    HOSTELLER_ONLY = "HOSTELLER_ONLY"
    ASSIGNED_ONLY = "ASSIGNED_ONLY"
    OWN_ACADEMIC = "OWN_ACADEMIC"


class Faculty(Base):
    __tablename__ = "faculties"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    short_code = Column(String(20), nullable=False, unique=True)

    departments = relationship("Department", back_populates="faculty")


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    kind = Column(SAEnum(DepartmentKind, name="department_kind"), nullable=False)
    applicability = Column(
        SAEnum(DepartmentApplicability, name="department_applicability"),
        nullable=False,
    )
    faculty_id = Column(Integer, ForeignKey("faculties.id"), nullable=True)
    description = Column(String(500), nullable=True)

    __table_args__ = (
        # Academic departments MUST have faculty_id and applicability OWN_ACADEMIC
        CheckConstraint(
            "(kind = 'academic' AND faculty_id IS NOT NULL AND applicability = 'OWN_ACADEMIC') OR (kind = 'service' AND faculty_id IS NULL)",
            name="ck_department_kind_faculty_applicability",
        ),
        Index("ix_departments_faculty_id", "faculty_id"),
    )

    faculty = relationship("Faculty", back_populates="departments")
    programmes = relationship("Programme", back_populates="department")
    users = relationship("User", back_populates="department", foreign_keys="User.department_id")
    user_memberships = relationship("UserDepartment", back_populates="department", cascade="all, delete-orphan", foreign_keys="UserDepartment.department_id")
    roster_assigned = relationship("RosterAssignedDepartment", back_populates="department")
    approvals = relationship("DepartmentApproval", back_populates="department")


class Programme(Base):
    __tablename__ = "programmes"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    academic_department_id = Column(
        Integer, ForeignKey("departments.id"), nullable=False
    )

    __table_args__ = (
        Index("ix_programmes_department_id", "academic_department_id"),
    )

    department = relationship("Department", back_populates="programmes")
    roster_entries = relationship("StudentRoster", back_populates="programme")
