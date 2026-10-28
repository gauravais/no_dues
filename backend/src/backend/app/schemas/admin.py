"""Pydantic schemas for university administration."""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, EmailStr, Field
from backend.app.models.user import UserRole


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
        description="Assigned department ID (Mandatory for dept_officer and hod; academic only for hod)",
        examples=[4],
    )


class AdminUserResponse(BaseModel):
    """Created or inspected user record."""
    id: int
    email: str
    full_name: str | None
    role: str
    department_id: int | None
    department_name: str | None = None
    is_active: bool
    temporary_password: str | None = Field(
        None,
        description="One-time generated random temporary password (never returned again and never logged)",
        examples=["k9#dF2!zLp01"],
    )


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
    is_active: bool
    created_at: datetime
