"""Pydantic schemas for academic department roster and lab catalog management."""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, EmailStr, Field
from backend.app.schemas.workflow import DepartmentResponse


class DepartmentRosterCreate(BaseModel):
    """Payload to add a single student to the academic department's roster."""
    registration_number: str = Field(..., min_length=1, max_length=50, examples=["2026CS999"])
    name: str = Field(..., min_length=1, max_length=255, examples=["Amit Verma"])
    email: EmailStr = Field(..., description="Student email", examples=["2026cs999@svsu.ac.in"])
    mobile: str = Field(..., min_length=5, max_length=20, examples=["9876543210"])
    programme_id: int = Field(..., description="Programme ID belonging to the academic department", examples=[1])
    address: str = Field("", max_length=500, examples=["Room 101, Hostel A"])
    is_hosteller: bool = Field(False, description="Whether the student resides in university hostel")
    security_deposit_amount: Decimal | None = Field(
        None,
        description="Ignored; deposit amounts are managed exclusively by Accounts",
    )


class DepartmentRosterPatch(BaseModel):
    """Payload to update an existing student in the academic department's roster."""
    name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = Field(None, description="New email (refused if student user account already exists)")
    mobile: str | None = Field(None, min_length=5, max_length=20)
    address: str | None = Field(None, max_length=500)
    programme_id: int | None = Field(None, description="New enrolled programme ID (refused if student has open request or programme is not active/not in officer's academic department)")
    security_deposit_amount: Decimal | None = Field(
        None,
        description="Ignored; deposit amounts are managed exclusively by Accounts",
    )


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
    message: str | None = Field(None, description="Informational message")


class DepartmentRosterListResponse(BaseModel):
    """Paginated roster list scoped to academic department."""
    total: int
    items: list[DepartmentRosterItem]


class LabCourseCreate(BaseModel):
    """Payload to create a new lab or workshop course."""
    code: str = Field(..., min_length=1, max_length=50, examples=["CSE-L201"])
    name: str = Field(..., min_length=1, max_length=255, examples=["Data Structures & Algorithms Lab"])
    lab_department_id: int = Field(..., description="ID of active LAB_WORKSHOP service department providing the facility", examples=[5])
    academic_department_id: int | None = Field(None, description="Academic department ID (ignored or used by admin)", examples=[1])
    specialization: str | None = Field(None, max_length=255, examples=["AI & Machine Learning"])


class LabCoursePatch(BaseModel):
    """Payload to edit a lab course."""
    code: str | None = Field(None, min_length=1, max_length=50, examples=["CSE-L201"])
    name: str | None = Field(None, min_length=1, max_length=255)
    lab_department_id: int | None = Field(None, description="ID of active LAB_WORKSHOP service department", examples=[5])
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
    offices_to_create: list[str] = Field(default_factory=list, description="Offices that would be/were created")
    offices_without_officers: list[str] = Field(default_factory=list, description="Referenced offices with no active officer")
    dry_run: bool = False


class StudentLabCatalogItem(BaseModel):
    """Lab course option for student declaration."""
    id: int
    code: str
    name: str
    lab_department_id: int
    lab_department_name: str
    specialization: str | None = None
    category: str = "LAB_WORKSHOP"
    label: str = "Lab / Workshop"


class AssignedOnlyDepartmentItem(BaseModel):
    """ASSIGNED_ONLY service department option for direct student declaration."""
    id: int
    name: str
    description: str | None = None
    category: str = "ADDITIONAL_FACILITY"
    label: str = "Additional facility"
    is_active: bool = True
    has_active_officer: bool = Field(True, description="Whether department has at least one active dealing officer")


class StudentLabCatalogResponse(BaseModel):
    """Lab catalog and fallback service offices available for student declaration."""
    lab_courses: list[StudentLabCatalogItem]
    assigned_only_departments: list[AssignedOnlyDepartmentItem]
    direct_offices: list[DepartmentResponse] = Field(default_factory=list, description="Direct active Lab / Workshop offices for fallback")


class AddDepartmentRequest(BaseModel):
    """Payload to add a department to an existing clearance request."""
    department_id: int = Field(..., description="ID of the department to add", examples=[5])


class CreateLabWorkshopRequest(BaseModel):
    """Payload for an academic officer to create a Lab / Workshop office."""
    name: str = Field(..., min_length=3, max_length=80, description="Name of the Lab/Workshop office", examples=["Advanced Computing Lab"])
    description: str | None = Field(None, max_length=500, description="Optional description of the facility")


class UpdateLabWorkshopRequest(BaseModel):
    """Payload for an academic officer to update their Lab / Workshop office."""
    name: str | None = Field(None, min_length=3, max_length=80, description="New name of the office")
    description: str | None = Field(None, max_length=500, description="New description")
    is_active: bool | None = Field(None, description="Deactivate or reactivate the office")


class LabWorkshopOfficeItem(BaseModel):
    """Lab / Workshop office with officer ownership and editable flag."""
    id: int
    name: str
    description: str | None = None
    category: str = "LAB_WORKSHOP"
    label: str = "Lab / Workshop"
    is_active: bool
    editable: bool = Field(..., description="Whether current officer can edit/deactivate this office")
    subject_count: int = Field(0, description="Number of lab courses hosted by this office")
    created_by_me: bool = Field(False, description="Whether current officer created this office")
