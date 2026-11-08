"""Pydantic schemas for university administration."""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, EmailStr, Field
from backend.app.models.user import UserRole
from backend.app.schemas.common import DepartmentBrief



class RosterUploadRowReport(BaseModel):
    """Result per processed CSV row."""
    row_number: int
    registration_number: str
    status: str = Field(..., description="created | updated | rejected")
    reason: str | None = None


class RosterUploadResponse(BaseModel):
    """Aggregate upload summary report."""
    total_rows: int
    created_count: int
    updated_count: int
    rejected_count: int
    rows: list[RosterUploadRowReport]


class RosterItem(BaseModel):
    """Student roster entry."""
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
    assigned_department_ids: list[int] = Field(default_factory=list)


class RosterListResponse(BaseModel):
    """Paginated roster list."""
    total: int
    items: list[RosterItem]


class RosterUpdateRequest(BaseModel):
    """Payload to patch a student roster record."""
    is_hosteller: bool | None = None
    security_deposit_amount: Decimal | None = Field(None, ge=0)
    address: str | None = None
    mobile: str | None = None
    email: EmailStr | None = None


class RosterAssignedDepartmentsRequest(BaseModel):
    """Payload to set assigned labs/workshops for a student."""
    department_ids: list[int] = Field(..., description="List of assigned service department IDs")


class AdminCreateUserRequest(BaseModel):
    """Payload for administrator to provision staff, officer or HoD user."""
    email: EmailStr = Field(..., description="Official university staff email", examples=["officer.lab3@example.edu"])
    full_name: str = Field(..., min_length=1, max_length=255, description="Full name of staff member", examples=["Dr. Meenakshi Sharma"])
    role: UserRole = Field(
        ...,
        description="Allowed staff role: dept_officer, hod, or registrar_accounts",
        examples=[UserRole.dept_officer],
    )
    department_id: int | None = Field(
        None,
        description="Assigned primary department ID (for backward compatibility)",
        examples=[4],
    )
    department_ids: list[int] | None = Field(
        None,
        description="Assigned department IDs (Mandatory for dept_officer and hod; academic only for hod)",
        examples=[[4, 5]],
    )
    google_only: bool = Field(
        False,
        description="When true, account has no password and authenticates exclusively via university Google account",
        examples=[False],
    )


class AdminUserResponse(BaseModel):
    """Created or inspected user record."""
    id: int
    email: str
    full_name: str | None
    role: str
    department_id: int | None
    department_name: str | None = None
    departments: list[DepartmentBrief] = Field(default_factory=list)
    is_active: bool
    temporary_password: str | None = Field(
        None,
        description="One-time generated random temporary password (never returned again and never logged)",
        examples=["k9#dF2!zLp01"],
    )


class AdminUserDetailResponse(BaseModel):
    """Detailed user view for admin."""
    id: int
    email: str
    full_name: str | None = None
    role: str
    department_id: int | None = None
    department_name: str | None = None
    departments: list[DepartmentBrief] = Field(default_factory=list)
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class AddUserDepartmentRequest(BaseModel):
    """Payload to add a department membership to an existing user."""
    department_id: int = Field(..., description="Department ID to add to user memberships", examples=[5])



class AdminResetPasswordResponse(BaseModel):
    """One-time reset temporary password response."""
    user_id: int
    email: str
    temporary_password: str = Field(
        ...,
        description="One-time generated random temporary password",
        examples=["wQ7$mN9@xY24"],
    )


class AdminUserActiveRequest(BaseModel):
    """Payload to activate or deactivate a user account."""
    is_active: bool


class AdminUserListItem(BaseModel):
    """User account item in admin user directory."""
    id: int
    email: str
    full_name: str | None = None
    role: str
    department: str | None = None
    department_name: str | None = None
    department_id: int | None = None
    departments: list[DepartmentBrief] = Field(default_factory=list)
    is_active: bool
    created_at: datetime



class AdminOfficeUserSummary(BaseModel):
    """Summary of an officer or HoD user."""
    id: int
    name: str | None = None
    email: str


class AdminOfficeSummary(BaseModel):
    """Department/office status for university administrators."""
    id: int
    name: str
    kind: str = Field(..., description="academic | service")
    applicability: str
    category: str = Field("UNIVERSITY_OFFICE", description="Computed category")
    label: str = Field("University office", description="Human-readable category label")
    is_active: bool = Field(True, description="Whether department is active")
    description: str | None = None
    active_officers: list[AdminOfficeUserSummary]
    hod: AdminOfficeUserSummary | None = None
    missing_officer: bool = Field(..., description="True if department has no active dealing officer")
    missing_hod: bool = Field(..., description="True if academic department has no active HoD")


class AdminOfficeListResponse(BaseModel):
    """List of all university departments and their staffing status."""
    total: int
    items: list[AdminOfficeSummary]


class AdminUserBulkUploadDetail(BaseModel):
    """Row processing result in bulk user provisioning."""
    row_number: int
    email: str
    status: str = Field(..., description="created | rejected")
    reason: str | None = None
    temporary_password: str | None = Field(
        None,
        description="One-time temporary password (only returned in this response)",
    )


class AdminUserBulkUploadResponse(BaseModel):
    """Aggregate response for admin bulk user upload."""
    total_rows: int
    created_count: int
    rejected_count: int
    rows: list[AdminUserBulkUploadDetail]


class AdminDepartmentListItem(BaseModel):
    """Item in admin department management list."""
    id: int
    name: str
    kind: str
    applicability: str
    description: str | None = None
    category: str
    label: str
    is_active: bool
    officer_count: int = 0
    subject_count: int = 0
    open_approvals_count: int = 0
    missing_officer: bool = False
    missing_hod: bool = False


class AdminDepartmentListResponse(BaseModel):
    """List of departments for admin management."""
    total: int
    items: list[AdminDepartmentListItem]


class AdminCreateDepartmentRequest(BaseModel):
    """Payload to create a service department."""
    name: str = Field(..., min_length=3, max_length=80, description="Department name", examples=["Robotics Lab"])
    description: str | None = Field(None, max_length=500, description="Department description")
    category: str = Field(
        ...,
        description="Category: UNIVERSITY_OFFICE, HOSTEL, LAB_WORKSHOP, ADDITIONAL_FACILITY",
        examples=["LAB_WORKSHOP"],
    )


class AdminUpdateDepartmentRequest(BaseModel):
    """Payload to update a department."""
    name: str | None = Field(None, min_length=3, max_length=80)
    description: str | None = Field(None, max_length=500)
    category: str | None = Field(None, description="Category: UNIVERSITY_OFFICE, HOSTEL, LAB_WORKSHOP, ADDITIONAL_FACILITY")
    is_active: bool | None = None
    confirm: bool = Field(False, description="Explicit confirmation when deactivating core university offices")


class BulkCategoryRequest(BaseModel):
    """Payload to bulk-update category of departments."""
    department_ids: list[int] = Field(..., min_length=1)
    category: str = Field(..., description="Target category: UNIVERSITY_OFFICE, HOSTEL, LAB_WORKSHOP, ADDITIONAL_FACILITY")


class BulkCategoryResponse(BaseModel):
    """Response for bulk category update."""
    updated_count: int
    detail: str


class AdminUpdateUserRequest(BaseModel):
    """Payload to update staff user's full name and email."""
    full_name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None
    unlink_google: bool = Field(False, description="When true, unlinks bound Google account on email change")


# Academic Structure Schemas
class FacultyResponse(BaseModel):
    """Faculty structure representation."""
    id: int
    name: str
    short_code: str
    department_count: int = 0


class FacultyCreate(BaseModel):
    """Payload to create a faculty."""
    name: str = Field(..., min_length=2, max_length=255, examples=["Skill Faculty of Engineering and Technology"])
    short_code: str = Field(..., min_length=1, max_length=20, examples=["SFET"])


class FacultyUpdate(BaseModel):
    """Payload to update a faculty."""
    name: str | None = Field(None, min_length=2, max_length=255)
    short_code: str | None = Field(None, min_length=1, max_length=20)


class AcademicDepartmentResponse(BaseModel):
    """Academic department representation."""
    id: int
    name: str
    faculty_id: int
    faculty_name: str | None = None
    is_active: bool = True
    category: str = "ACADEMIC"
    label: str = "Academic department"
    programme_count: int = 0
    student_count: int = 0


class AcademicDepartmentCreate(BaseModel):
    """Payload to create an academic department."""
    name: str = Field(..., min_length=3, max_length=255, examples=["Skill Department of CS/IT"])
    faculty_id: int = Field(..., examples=[1])
    is_active: bool = True


class AcademicDepartmentUpdate(BaseModel):
    """Payload to update an academic department."""
    name: str | None = Field(None, min_length=3, max_length=255)
    faculty_id: int | None = None
    is_active: bool | None = None


class ProgrammeResponse(BaseModel):
    """Academic programme representation."""
    id: int
    name: str
    academic_department_id: int
    academic_department_name: str | None = None
    faculty_id: int | None = None
    faculty_name: str | None = None
    is_active: bool = True
    student_count: int = 0


class ProgrammeCreate(BaseModel):
    """Payload to create a programme."""
    name: str = Field(..., min_length=3, max_length=255, examples=["B.Tech Computer Science and Engineering"])
    academic_department_id: int = Field(..., examples=[1])
    is_active: bool = True


class ProgrammeUpdate(BaseModel):
    """Payload to update a programme."""
    name: str | None = Field(None, min_length=3, max_length=255)
    academic_department_id: int | None = None
    is_active: bool | None = None


