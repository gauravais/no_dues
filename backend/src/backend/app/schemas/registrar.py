"""Pydantic schemas for registrar & accounts refund management."""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class RegistrarQueueItem(BaseModel):
    """Clearance record waiting for refund processing."""
    request_id: int = Field(..., description="Unique clearance request ID", examples=[1])
    student_name: str = Field(..., description="Student full name", examples=["Arjun Mehta"])
    registration_number: str = Field(..., description="Student registration number", examples=["DEMO2026001"])
    programme: str = Field(..., description="Enrolled degree programme", examples=["B.Tech Computer Engineering"])
    deposit_amount: Decimal = Field(..., description="Security deposit deposited initially", examples=[Decimal("5000.00")])
    cleared_at: datetime | None = Field(None, description="Date cleared by HoD")
    status: str = Field(..., description="Clearance request status", examples=["CLEARED"])
    refund_status: str = Field(..., description="Refund record status", examples=["PENDING_VERIFICATION"])


class RegistrarQueueResponse(BaseModel):
    """Paginated list of clearance requests pending refund processing."""
    total: int = Field(..., description="Total count of eligible requests", examples=[1])
    items: list[RegistrarQueueItem] = Field(..., description="Batch of items")


class VerifyRefundRequest(BaseModel):
    """Payload to verify and compute refund deductions."""
    deductions: Decimal = Field(
        ...,
        ge=0,
        description="Amount to deduct from deposit (must be between 0 and deposit amount)",
        examples=[Decimal("250.00")],
    )
    remarks: str | None = Field(
        None,
        description="Justification or breakdown for deductions",
        examples=["Hostel damage deduction Rs. 250"],
    )


class VerifyRefundResponse(BaseModel):
    """Response after verifying refund calculation."""
    request_id: int = Field(..., description="Clearance request ID", examples=[1])
    deposit_amount: Decimal = Field(..., description="Original deposit amount", examples=[Decimal("5000.00")])
    deductions: Decimal = Field(..., description="Approved deductions", examples=[Decimal("250.00")])
    final_amount: Decimal = Field(..., description="Calculated final refund amount", examples=[Decimal("4750.00")])
    refund_status: str = Field(..., description="New refund status", examples=["VERIFIED"])
    request_status: str = Field(..., description="New request status", examples=["REFUND_VERIFIED"])
    updated_at: datetime = Field(..., description="Timestamp of verification")


class MarkRefundProcessedRequest(BaseModel):
    """Payload to record bank transaction reference for disbursed refund."""
    payment_reference: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Official bank payment / UTR / NEFT reference number",
        examples=["UTR20261026009847"],
    )


class MarkRefundProcessedResponse(BaseModel):
    """Response after marking refund as processed."""
    request_id: int = Field(..., description="Clearance request ID", examples=[1])
    payment_reference: str = Field(..., description="Recorded payment reference", examples=["UTR20261026009847"])
    refund_status: str = Field(..., description="Updated refund status", examples=["PROCESSED"])
    updated_at: datetime = Field(..., description="Timestamp of completion")
