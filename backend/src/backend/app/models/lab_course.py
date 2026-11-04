"""LabCourse model."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, DateTime, Index
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class LabCourse(Base):
    __tablename__ = "lab_courses"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    academic_department_id = Column(
        Integer, ForeignKey("departments.id"), nullable=True
    )
    lab_department_id = Column(
        Integer, ForeignKey("departments.id"), nullable=False
    )
    specialization = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_lab_courses_code", "code"),
        Index("ix_lab_courses_academic_department_id", "academic_department_id"),
        Index("ix_lab_courses_lab_department_id", "lab_department_id"),
    )

    academic_department = relationship(
        "Department",
        foreign_keys=[academic_department_id],
        backref="academic_lab_courses",
    )
    lab_department = relationship(
        "Department",
        foreign_keys=[lab_department_id],
        backref="provided_lab_courses",
    )
