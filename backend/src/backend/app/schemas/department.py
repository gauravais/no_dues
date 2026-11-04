"""Pydantic schemas for academic department roster and lab catalog management."""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, EmailStr, Field


class DepartmentRosterCreate(BaseModel):
    """Payload to add a single student to the academic department's roster."""
    registration_number: str = Field(..., min_length=1, max_length=50, examples=["2026CS999"])
    name: str = Field(..., min_length=1, max_length=255, examples=["Amit Verma"])
    email: EmailStr = Field(..., description="Student email", examples=["2026cs999@svsu.ac.in"])
    mobile: str = Field(..., min_length=5, max_length=20, examples=["9876543210"])
    programme_id: int = Field(..., description="Programme ID belonging to the academic department", examples=[1])
    address: str = Field("", max_length=500, examples=["Room 101, Hostel A"])
    is_hosteller: bool = Field(False, description="Whether the student resides in university hostel")
    security_deposit_amount: Decimal = Field(Decimal("0"), ge=0, description="Security deposit amount in INR")


class DepartmentRosterPatch(BaseModel):
    """Payload to update an existing student in the academic department's roster."""
    name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = Field(None, description="New email (refused if student user account already exists)")
    mobile: str | None = Field(None, min_length=5, max_length=20)
    address: str | None = Field(None, max_length=500)


class DepartmentRosterItem(BaseModel):
    """Student roster entry scoped to academic department."""
    id: int
    registration_number: str
    name: str
    email: str
    mobile: str
    address: str
    programme_id: int
    programme_name: str
    is_hosteller: bool
    security_deposit_amount: Decimal
    has_user_account: bool = False
    assigned_department_ids: list[int] = Field(default_factory=list)


class DepartmentRosterListResponse(BaseModel):
    """Paginated roster list scoped to academic department."""
    total: int
    items: list[DepartmentRosterItem]


class LabCourseCreate(BaseModel):
    """Payload to create a new lab or workshop course."""
    code: str = Field(..., min_length=1, max_length=50, examples=["CSE-L201"])
    name: str = Field(..., min_length=1, max_length=255, examples=["Data Structures & Algorithms Lab"])
    lab_department_id: int = Field(..., description="ID of ASSIGNED_ONLY service department providing the facility", examples=[5])
    academic_department_id: int | None = Field(None, description="Academic department ID (ignored or used by admin)", examples=[1])
    specialization: str | None = Field(None, max_length=255, examples=["AI & Machine Learning"])


class LabCoursePatch(BaseModel):
    """Payload to edit a lab course."""
    name: str | None = Field(None, min_length=1, max_length=255)
    specialization: str | None = Field(None, max_length=255)
    is_active: bool | None = None


class LabCourseItem(BaseModel):
    """Lab course item."""
    id: int
    code: str
    name: str
    academic_department_id: int
    academic_department_name: str | None = None
    lab_department_id: int
    lab_department_name: str | None = None
    specialization: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LabCourseListResponse(BaseModel):
    """List of lab courses."""
    total: int
    items: list[LabCourseItem]


class LabCourseUploadRowReport(BaseModel):
    """Result per processed CSV row in lab course upload."""
    row_number: int
    code: str
    status: str = Field(..., description="created | updated | rejected")
    reason: str | None = None


class LabCourseUploadResponse(BaseModel):
    """Aggregate upload report for lab courses."""
    total_rows: int
    created_count: int
    updated_count: int
    rejected_count: int
    rows: list[LabCourseUploadRowReport]


class StudentLabCatalogItem(BaseModel):
    """Lab course option for student declaration."""
    id: int
    code: str
    name: str
    lab_department_id: int
    lab_department_name: str
    specialization: str | None = None


class AssignedOnlyDepartmentItem(BaseModel):
    """ASSIGNED_ONLY service department option for direct student declaration."""
    id: int
    name: str
    description: str | None = None


class StudentLabCatalogResponse(BaseModel):
    """Lab catalog and fallback service offices available for student declaration."""
    lab_courses: list[StudentLabCatalogItem]
    assigned_only_departments: list[AssignedOnlyDepartmentItem]


class AddDepartmentRequest(BaseModel):
    """Payload to add a department to an existing clearance request."""
    department_id: int = Field(..., description="ID of the department to add", examples=[5])
