"""Common generic schemas and error shapes."""
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard API error payload."""
    detail: str = Field(..., description="Human-readable explanation of the error", examples=["Resource not found"])


class MessageResponse(BaseModel):
    """Generic informational response payload."""
    detail: str = Field(..., description="Status or acknowledgment message", examples=["Action completed successfully"])
