"""Pydantic schemas for authentication and user profiles."""
from decimal import Decimal
from pydantic import BaseModel, EmailStr, Field


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
        min_length=8,
        description="New password (minimum 8 characters)",
        examples=["StudentSecure@2026"],
    )


class TokenResponse(BaseModel):
    """OAuth2 Bearer token response."""
    access_token: str = Field(..., description="JWT Bearer token for authorized requests")
    token_type: str = Field("bearer", description="Token type standard", examples=["bearer"])


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
    role: str = Field(..., description="System role identifier", examples=["student"])
    department_id: int | None = Field(None, description="Assigned department ID (for staff and HoD)", examples=[4])
    department_name: str | None = Field(None, description="Assigned department title", examples=["Skill Department of CS/IT"])
    roster: RosterSummary | None = Field(None, description="Detailed roster info if user role is student")
