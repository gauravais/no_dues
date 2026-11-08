"""Faculty, Department, and Programme models."""
import enum
from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, Enum as SAEnum, CheckConstraint, Index, text
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
    LAB_WORKSHOP = "LAB_WORKSHOP"


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
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        # Academic departments MUST have faculty_id and applicability OWN_ACADEMIC
        CheckConstraint(
            "(kind = 'academic' AND faculty_id IS NOT NULL AND applicability = 'OWN_ACADEMIC') OR (kind = 'service' AND faculty_id IS NULL)",
            name="ck_department_kind_faculty_applicability",
        ),
        Index("ix_departments_faculty_id", "faculty_id"),
        Index("ix_departments_created_by_user_id", "created_by_user_id"),
    )

    faculty = relationship("Faculty", back_populates="departments")
    programmes = relationship("Programme", back_populates="department")
    users = relationship("User", back_populates="department", foreign_keys="User.department_id")
    user_memberships = relationship("UserDepartment", back_populates="department", cascade="all, delete-orphan", foreign_keys="UserDepartment.department_id")
    roster_assigned = relationship("RosterAssignedDepartment", back_populates="department")
    approvals = relationship("DepartmentApproval", back_populates="department")
    creator = relationship("User", foreign_keys=[created_by_user_id])

    @property
    def category(self) -> str:
        if self.kind == DepartmentKind.academic or self.applicability == DepartmentApplicability.OWN_ACADEMIC:
            return "ACADEMIC"
        if self.applicability == DepartmentApplicability.ALWAYS:
            return "UNIVERSITY_OFFICE"
        if self.applicability == DepartmentApplicability.HOSTELLER_ONLY:
            return "HOSTEL"
        if self.applicability == DepartmentApplicability.LAB_WORKSHOP:
            return "LAB_WORKSHOP"
        if self.applicability == DepartmentApplicability.ASSIGNED_ONLY:
            return "ADDITIONAL_FACILITY"
        return "ADDITIONAL_FACILITY"

    @property
    def category_label(self) -> str:
        labels = {
            "ACADEMIC": "Academic department",
            "UNIVERSITY_OFFICE": "University office",
            "HOSTEL": "Hostel",
            "LAB_WORKSHOP": "Lab / Workshop",
            "ADDITIONAL_FACILITY": "Additional facility",
        }
        return labels.get(self.category, "Additional facility")

    @property
    def label(self) -> str:
        return self.category_label


class Programme(Base):
    __tablename__ = "programmes"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    academic_department_id = Column(
        Integer, ForeignKey("departments.id"), nullable=False
    )
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))

    __table_args__ = (
        Index("ix_programmes_department_id", "academic_department_id"),
    )

    department = relationship("Department", back_populates="programmes")
    roster_entries = relationship("StudentRoster", back_populates="programme")
