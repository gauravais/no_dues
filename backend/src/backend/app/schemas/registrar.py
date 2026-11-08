"""Pydantic schemas for registrar & accounts refund management."""
import enum
from datetime import datetime, date, timezone
from decimal import Decimal
from pydantic import BaseModel, Field
from backend.app.schemas.workflow import DepartmentApprovalItem


class PaymentMode(str, enum.Enum):
    NEFT = "NEFT"
    IMPS = "IMPS"
    UPI = "UPI"
    CHEQUE = "CHEQUE"
    OTHER = "OTHER"


class RegistrarQueueItem(BaseModel):
    """Clearance record waiting for refund processing."""
    request_id: int = Field(..., description="Unique clearance request ID", examples=[1])
    student_name: str = Field(..., description="Student full name", examples=["Arjun Mehta"])
    registration_number: str = Field(..., description="Student registration number", examples=["DEMO2026001"])
    programme: str = Field(..., description="Enrolled degree programme", examples=["B.Tech Computer Engineering"])
    deposit_amount: Decimal = Field(..., description="Security deposit deposited initially", examples=[Decimal("5000.00")])
    deductions: Decimal | None = Field(None, description="Approved deductions amount if verified", examples=[Decimal("250.00")])
    final_amount: Decimal | None = Field(None, description="Calculated final refund amount if verified", examples=[Decimal("4750.00")])
    cleared_at: datetime | None = Field(None, description="Date cleared by HoD")
    status: str = Field(..., description="Clearance request status", examples=["CLEARED"])
    refund_status: str = Field(..., description="Refund record status", examples=["PENDING_VERIFICATION"])
    student_issue_open: bool = Field(False, description="True if student has an open unresolved refund issue")


class RegistrarQueueCounts(BaseModel):
    """Counts per queue tab."""
    TO_VERIFY: int = Field(0, description="Count of requests waiting for verification")
    TO_PAY: int = Field(0, description="Count of verified refunds ready for payment")
    PAID: int = Field(0, description="Count of disbursed refunds")
    FAILED: int = Field(0, description="Count of failed refund disbursements")
    ALL: int = Field(0, description="Total count across all refund states")


class RegistrarQueueResponse(BaseModel):
    """Paginated list of clearance requests pending refund processing."""
    total: int = Field(..., description="Total count of eligible requests in this tab", examples=[1])
    items: list[RegistrarQueueItem] = Field(..., description="Batch of items")
    counts: RegistrarQueueCounts = Field(default_factory=RegistrarQueueCounts, description="Counts per queue tab")
    total_to_pay_amount: Decimal = Field(Decimal("0.00"), description="Sum of final refund amounts for TO_PAY tab")
    total_paid_amount: Decimal = Field(Decimal("0.00"), description="Sum of final refund amounts for PAID tab")


class VerifyRefundRequest(BaseModel):
    """Payload to verify and compute refund deductions."""
    deposit_amount: Decimal | None = Field(
        None,
        ge=0,
        description="Confirmed security deposit from university official records (optional, defaults to draft deposit)",
        examples=[Decimal("5000.00")],
    )
    deductions: Decimal = Field(
        ...,
        ge=0,
        description="Amount to deduct from deposit (must be between 0 and deposit amount)",
        examples=[Decimal("250.00")],
    )
    remarks: str = Field(
        ...,
        min_length=1,
        max_length=1000,
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


class ReopenVerificationRequest(BaseModel):
    """Payload to reopen a verified refund back to pending verification."""
    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Mandatory justification for reopening verification to correct amounts",
        examples=["Need to correct hostel damage deduction"],
    )


class RegistrarRequestDetailResponse(BaseModel):
    """Full request details for registrar review with roster provenance and complete refund timeline."""
    request_id: int = Field(..., description="Clearance request ID", examples=[1])
    status: str = Field(..., description="Clearance request status", examples=["CLEARED"])
    student_name: str = Field(..., description="Student full name", examples=["Arjun Mehta"])
    registration_number: str = Field(..., description="Student registration number", examples=["DEMO2026001"])
    programme: str = Field(..., description="Enrolled degree programme", examples=["B.Tech Computer Engineering"])
    roster_source: str | None = Field(None, description="Provenance source of student roster entry", examples=["department_upload"])
    roster_created_by_user_id: int | None = Field(None, description="User ID who provisioned student roster record", examples=[2])
    roster_created_by_name: str | None = Field(None, description="Name of staff who provisioned student", examples=["Officer CS/IT"])
    account_number_masked: str = Field(..., description="Masked bank account number", examples=["********1234"])
    ifsc_code: str = Field(..., description="Bank IFSC code", examples=["DEMO0001234"])
    account_holder_name: str = Field(..., description="Bank account holder name", examples=["Arjun Mehta"])
    bank_address: str = Field(..., description="Bank branch address", examples=["Campus Branch, Gurugram"])
    deposit_amount: Decimal = Field(..., description="Security deposit amount", examples=[Decimal("5000.00")])
    deductions: Decimal | None = Field(None, description="Approved deductions if verified", examples=[Decimal("250.00")])
    final_amount: Decimal | None = Field(None, description="Final refund amount if verified", examples=[Decimal("4750.00")])
    refund_status: str = Field(..., description="Refund record status", examples=["PENDING_VERIFICATION"])
    approvals: list[DepartmentApprovalItem] = Field(..., description="List of departmental clearance decisions")

    # Complete timeline fields
    verified_at: datetime | None = Field(None, description="Timestamp of refund verification")
    verified_by_name: str | None = Field(None, description="Name of staff who verified refund")
    accounts_note: str | None = Field(None, description="Student-visible accounts remarks")
    paid_at: datetime | None = Field(None, description="Timestamp when refund was marked as processed")
    paid_by_name: str | None = Field(None, description="Name of staff who recorded payment")
    paid_on: date | None = Field(None, description="Date payment was disbursed to bank")
    payment_mode: str | None = Field(None, description="Payment mode used (NEFT, IMPS, UPI, CHEQUE, OTHER)")
    payment_reference: str | None = Field(None, description="Recorded bank transaction reference")
    failure_reason: str | None = Field(None, description="Reason if payment disbursement failed")
    failed_at: datetime | None = Field(None, description="Timestamp of payment failure")
    student_confirmed_at: datetime | None = Field(None, description="Timestamp when student confirmed receipt")
    student_issue_note: str | None = Field(None, description="Note from student reporting refund issue")
    student_issue_at: datetime | None = Field(None, description="Timestamp when student reported issue")
    student_issue_resolved_at: datetime | None = Field(None, description="Timestamp when student issue was resolved")


class RevealBankDetailsResponse(BaseModel):
    """Audited plain bank account details revealed to registrar."""
    account_holder_name: str = Field(..., description="Bank account holder name", examples=["Arjun Mehta"])
    account_number: str = Field(..., description="Full unmasked bank account number", examples=["123456789012"])
    ifsc_code: str = Field(..., description="Bank IFSC code", examples=["DEMO0001234"])
    bank_address: str = Field(..., description="Bank branch address", examples=["Campus Branch, Gurugram"])


class MarkRefundProcessedRequest(BaseModel):
    """Payload to record bank transaction reference for disbursed refund."""
    payment_reference: str = Field(
        ...,
        min_length=6,
        max_length=40,
        pattern=r"^[a-zA-Z0-9\-_]{6,40}$",
        description="Official bank payment reference (6 to 40 letters, digits, hyphens, and underscores)",
        examples=["NEFT-SVSU-20261108-001"],
    )
    paid_on: date = Field(
        default_factory=lambda: datetime.now(timezone.utc).date(),
        description="Date payment was disbursed to bank",
        examples=["2026-11-08"],
    )
    payment_mode: PaymentMode | None = Field(None, description="Disbursement payment mode: NEFT, IMPS, UPI, CHEQUE, OTHER", examples=[PaymentMode.NEFT])


class MarkRefundProcessedResponse(BaseModel):
    """Response after marking refund as processed."""
    request_id: int = Field(..., description="Clearance request ID", examples=[1])
    payment_reference: str = Field(..., description="Recorded payment reference", examples=["NEFT-SVSU-20261108-001"])
    refund_status: str = Field(..., description="Updated refund status", examples=["PROCESSED"])
    paid_on: date | None = Field(None, description="Disbursement date")
    payment_mode: str | None = Field(None, description="Payment mode")
    updated_at: datetime = Field(..., description="Timestamp of completion")


class MarkRefundFailedRequest(BaseModel):
    """Payload to mark a verified or processed refund as failed."""
    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Reason why bank transaction failed",
        examples=["Beneficiary bank account inactive or closed"],
    )


class ResolveStudentIssueRequest(BaseModel):
    """Payload to close an open student issue."""
    note: str | None = Field(
        None,
        max_length=500,
        description="Resolution note by registrar",
        examples=["Contacted student bank branch, reference verified"],
    )

