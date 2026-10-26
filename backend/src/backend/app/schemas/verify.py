"""Public verification schema."""
from datetime import datetime
from pydantic import BaseModel, Field


class PublicVerificationResponse(BaseModel):
    """Public certificate verification result."""
    valid: bool = Field(
        ...,
        description="Whether the certificate is authentic and registered in the university system",
        examples=[True],
    )
    issued_at: datetime | None = Field(
        None,
        description="Date and time when the certificate was issued by the HoD",
        examples=["2026-10-26T12:00:00Z"],
    )
    masked_registration_number: str | None = Field(
        None,
        description="Masked registration number protecting student identity (all but last 4 digits masked)",
        examples=["*******2001"],
    )
    programme: str | None = Field(
        None,
        description="Degree / Diploma programme completed",
        examples=["Bachelor of Technology (B.Tech.) Computer Engineering"],
    )
    department: str | None = Field(
        None,
        description="Academic department name",
        examples=["Skill Department of CS/IT"],
    )
