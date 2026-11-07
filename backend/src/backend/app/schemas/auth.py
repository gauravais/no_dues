"""Pydantic schemas for authentication and user profiles."""
from decimal import Decimal
from pydantic import BaseModel, EmailStr, Field
from backend.app.schemas.common import DepartmentBrief



class SignupOTPRequest(BaseModel):
    """Payload to request a verification OTP for student self-registration."""
    registration_number: str = Field(
        ...,
        description="Official student registration number as listed on university roster",
        examples=["DEMO2026006"],
    )
    email: EmailStr = Field(
        ...,
        description="Official university email corresponding to the registration number",
        examples=["aman.gupta@example.edu"],
    )


class SignupOTPResponse(BaseModel):
    """Response returned upon requesting a signup OTP."""
    detail: str = Field(
        ...,
        description="Status description regarding dispatch of the OTP",
        examples=["If the details match our records, an OTP has been dispatched to your email."],
    )
    dev_otp: str | None = Field(
        None,
        description="Included only in development mode when DEV_RETURN_OTP=true",
        examples=["123456"],
    )


class SignupVerifyRequest(BaseModel):
    """Payload to verify OTP and establish student account password."""
    registration_number: str = Field(
        ...,
        description="Official student registration number",
        examples=["DEMO2026006"],
    )
    otp: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="6-digit numeric OTP sent to your registered email",
        examples=["123456"],
    )
    password: str = Field(
        ...,
        min_length=10,
        description="New password (minimum 10 characters)",
        examples=["StudentSecure@2026"],
    )


class ChangePasswordRequest(BaseModel):
    """Payload to change password."""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=10, description="New password (minimum 10 characters)")


class TokenResponse(BaseModel):
    """OAuth2 Bearer token response."""
    access_token: str = Field(..., description="JWT Bearer token for authorized requests")
    token_type: str = Field("bearer", description="Token type standard", examples=["bearer"])
    must_change_password: bool = Field(False, description="Whether the user must change password before accessing system")


class GoogleAuthRequest(BaseModel):
    """Payload carrying the Google OAuth2 ID token credential."""
    credential: str = Field(
        ...,
        description="Google OAuth2 ID token credential issued by Google Identity Services",
        examples=["eyJhbGciOiJSUzI1NiIsImtpZCI6Ij..."],
    )


class AuthConfigResponse(BaseModel):
    """Public authentication configuration metadata."""
    google_enabled: bool = Field(..., description="Whether Google OAuth2 sign-in is enabled")
    google_client_id: str | None = Field(None, description="Google OAuth2 client ID for frontend Google Identity Services")
    allowed_domain_hint: str | None = Field(None, description="Primary allowed university email domain hint", examples=["svsu.ac.in"])
    otp_signup_enabled: bool = Field(..., description="Whether legacy student OTP registration is enabled")


class RosterSummary(BaseModel):
    """Academic and financial roster profile summary for a student."""
    name: str = Field(..., description="Student full name", examples=["Arjun Mehta"])
    registration_number: str = Field(..., description="Registration number", examples=["DEMO2026001"])
    programme: str = Field(
        ...,
        description="Enrolled programme name",
        examples=["Bachelor of Technology (B.Tech.) Computer Engineering"],
    )
    department: str = Field(
        ...,
        description="Enrolled academic department name",
        examples=["Skill Department of CS/IT"],
    )
    is_hosteller: bool = Field(..., description="Whether student resides in campus hostel", examples=[True])
    security_deposit_amount: Decimal = Field(
        ...,
        description="Eligible security deposit amount for no-dues clearance refund",
        examples=[Decimal("5000.00")],
    )
    masked_bank_account: str | None = Field(
        None,
        description="Masked bank account number for refund credit (last 4 digits visible)",
        examples=["********0001"],
    )


class UserMeResponse(BaseModel):
    """Current authenticated user profile."""
    id: int = Field(..., description="User unique database ID", examples=[1])
    email: EmailStr = Field(..., description="User login email address", examples=["arjun.mehta@example.edu"])
    full_name: str | None = Field(None, description="User full display name", examples=["Arjun Mehta"])
    role: str = Field(..., description="System role identifier", examples=["student"])
    department_id: int | None = Field(None, description="Assigned department ID (for staff and HoD)", examples=[4])
    department_name: str | None = Field(None, description="Assigned department title", examples=["Skill Department of CS/IT"])
    departments: list[DepartmentBrief] = Field(default_factory=list, description="All department memberships for the user")
    must_change_password: bool = Field(False, description="Whether the user must change password before accessing system")
    roster: RosterSummary | None = Field(None, description="Detailed roster info if user role is student")

