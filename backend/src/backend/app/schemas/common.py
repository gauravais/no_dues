"""Common generic schemas and error shapes."""
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard API error payload."""
    detail: str = Field(..., description="Human-readable explanation of the error", examples=["Resource not found"])


class MessageResponse(BaseModel):
    """Generic informational response payload."""
    detail: str = Field(..., description="Status or acknowledgment message", examples=["Action completed successfully"])


class DepartmentBrief(BaseModel):
    """Brief metadata for a department membership."""
    id: int = Field(..., description="Department ID", examples=[1])
    name: str = Field(..., description="Department name", examples=["Skill Department of CS/IT"])
    kind: str = Field(..., description="Department kind: academic or service", examples=["academic"])
    category: str | None = Field(None, description="Computed category", examples=["ACADEMIC"])
    label: str | None = Field(None, description="Human-readable category label", examples=["Academic department"])
    is_active: bool = Field(True, description="Whether department is active")

