"""Pydantic schemas for clearance requests, approvals, and queue management."""
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, Field
from backend.app.models.clearance import ApprovalStatus, ClearanceStatus
from backend.app.models.refund import RefundStatus


class DepartmentApprovalItem(BaseModel):
    """Detailed approval status for an applicable university department."""
    id: int = Field(..., description="Approval record ID", examples=[101])
    department_id: int = Field(..., description="Department ID", examples=[1])
    department_name: str = Field(..., description="Department title", examples=["Library"])
    department_kind: str = Field(..., description="Department category: academic or service", examples=["service"])
    department_category: str | None = Field(None, description="Department computed category", examples=["UNIVERSITY_OFFICE"])
    department_label: str | None = Field(None, description="Department human-readable category label", examples=["University office"])
    status: ApprovalStatus = Field(..., description="Current approval status", examples=[ApprovalStatus.PENDING])
    remarks: str | None = Field(None, description="Department officer remarks (mandatory on rejection)", examples=["Fine pending: Rs. 150"])
    previous_remarks: str | None = Field(None, description="Previous rejection reason before student resubmitted", examples=["Fine pending: Rs. 150"])
    decided_at: datetime | None = Field(None, description="Timestamp when decision was rendered")
    decided_by_name: str | None = Field(None, description="Full name of officer who decided approval", examples=["Library Officer (Demo)"])
    added_by_user_id: int | None = Field(None, description="User ID of officer or HoD who added this department", examples=[10])
    added_by_name: str | None = Field(None, description="Name of officer or HoD who added this department", examples=["Dr. Meenakshi Sharma"])
    added_reason: str | None = Field(None, description="Reason why department was added to request", examples=["Hardware Lab dues pending"])
    resubmission_count: int = Field(..., description="Number of times student resubmitted to this department", examples=[0])


class CurrentRequestResponse(BaseModel):
    """Status summary and department-by-department breakdown of a clearance request."""
    id: int = Field(..., description="Clearance request ID", examples=[1])
    status: ClearanceStatus = Field(..., description="Overall clearance lifecycle status", examples=[ClearanceStatus.SUBMITTED])
    progress: str = Field(..., description="Progress indicator of approved departments", examples=["8 of 12 approved"])
    submitted_at: datetime = Field(..., description="Timestamp of initial submission")
    hod_remarks: str | None = Field(None, description="Chairperson / HoD remarks (if rejected during HOD review)", examples=["Subject project submission verification pending"])
    approvals: list[DepartmentApprovalItem] = Field(..., description="List of all department clearance reviews")
    refund_status: RefundStatus | None = Field(None, description="Security deposit refund status", examples=[RefundStatus.PENDING_VERIFICATION])
    deposit_amount: Decimal | None = Field(None, description="Security deposit amount", examples=[Decimal("5000.00")])
    deductions: Decimal | None = Field(None, description="Total deductions applied by accounts", examples=[Decimal("250.00")])
    final_amount: Decimal | None = Field(None, description="Net refund amount to be paid to student", examples=[Decimal("4750.00")])
    accounts_note: str | None = Field(None, description="Remarks from accounts branch explaining verification or deductions", examples=["Hostel clearance complete"])
    payment_reference: str | None = Field(None, description="Payment reference (NEFT/RTGS transaction ID) when PROCESSED", examples=["NEFT_SVSU_20261030_0099"])
    paid_on: date | None = Field(None, description="Date payment was disbursed to bank", examples=["2026-11-08"])
    payment_mode: str | None = Field(None, description="Disbursement payment mode: NEFT, IMPS, UPI, CHEQUE, OTHER", examples=["NEFT"])
    failure_reason: str | None = Field(None, description="Reason why bank transaction failed (when PAYMENT_FAILED)", examples=["Bank account inactive"])
    student_confirmed_at: datetime | None = Field(None, description="Timestamp when student confirmed receipt of funds")
    student_issue_note: str | None = Field(None, description="Note provided by student reporting a refund issue")
    student_issue_at: datetime | None = Field(None, description="Timestamp when student reported issue")


class StudentRefundConfirmRequest(BaseModel):
    """Payload for student to confirm refund receipt or report an issue."""
    received: bool = Field(..., description="True if student confirmed funds received, False if reporting issue")
    note: str | None = Field(None, max_length=500, description="Mandatory issue description if received is False")


class DecisionRequest(BaseModel):
    """Payload submitted by a department officer or HoD to record a decision."""
    decision: ApprovalStatus = Field(
        ...,
        description="Approval decision: APPROVED or REJECTED",
        examples=[ApprovalStatus.APPROVED],
    )
    remarks: str | None = Field(
        None,
        description="Remarks explaining the decision (MANDATORY if decision is REJECTED)",
        examples=["All lab instruments returned and verified."],
    )


class OfficePendingCount(BaseModel):
    """Pending count for a single office belonging to an officer."""
    department_id: int = Field(..., description="Office department ID", examples=[4])
    department_name: str = Field(..., description="Office department name", examples=["Central Library"])
    pending: int = Field(..., description="Count of pending approvals in this office", examples=[2])


class DepartmentQueueItem(BaseModel):
    """Queue entry for department officers reviewing clearances."""
    approval_id: int = Field(..., description="Approval row ID", examples=[10])
    request_id: int = Field(..., description="Parent clearance request ID", examples=[1])
    department_id: int = Field(..., description="Department ID of this approval", examples=[4])
    department_name: str = Field(..., description="Department name of this approval", examples=["Central Library"])
    student_name: str = Field(..., description="Student full name", examples=["Arjun Mehta"])
    registration_number: str = Field(..., description="Student registration number", examples=["DEMO2026001"])
    programme_name: str = Field(..., description="Student enrolled programme", examples=["Bachelor of Technology (B.Tech.) Computer Engineering"])
    declared_subjects: list[str] = Field(default_factory=list, description="Subject codes and names belonging to officer's lab department", examples=[["CSE-L101: Data Structures Lab"]])
    declared_is_hosteller: bool | None = Field(None, description="Student hostel residency declaration (boolean for hostel office, null otherwise)", examples=[True])
    others_note: str | None = Field(None, description="Student note for unmapped/additional facilities (null if office is linked to a declared lab subject)", examples=["Robotics workshop access needed"])
    status: ApprovalStatus = Field(..., description="Approval status", examples=[ApprovalStatus.PENDING])
    submitted_at: datetime = Field(..., description="Request submission timestamp")
    resubmission_count: int = Field(..., description="Number of resubmissions", examples=[0])


class DepartmentQueueResponse(BaseModel):
    """Paginated list of department clearance queue items."""
    items: list[DepartmentQueueItem] = Field(..., description="Pending or reviewed clearances for this department")
    total: int = Field(..., description="Total records matching query filter", examples=[1])
    limit: int = Field(..., description="Page size limit", examples=[50])
    offset: int = Field(..., description="Page offset", examples=[0])
    office_counts: list[OfficePendingCount] = Field(default_factory=list, description="Pending clearance counts across officer's assigned offices")



class HoDQueueItem(BaseModel):
    """Queue entry for Chairperson / HoD reviewing completed departmental clearances."""
    request_id: int = Field(..., description="Clearance request ID", examples=[1])
    student_name: str = Field(..., description="Student full name", examples=["Arjun Mehta"])
    registration_number: str = Field(..., description="Student registration number", examples=["DEMO2026001"])
    programme_name: str = Field(..., description="Enrolled academic course", examples=["Bachelor of Technology (B.Tech.) Computer Engineering"])
    submitted_at: datetime = Field(..., description="Initial submission timestamp")
    status: ClearanceStatus = Field(..., description="Request status (should be HOD_REVIEW)", examples=[ClearanceStatus.HOD_REVIEW])


class DepartmentResponse(BaseModel):
    """University department basic metadata."""
    id: int = Field(..., description="Department ID", examples=[1])
    name: str = Field(..., description="Department name", examples=["Central Library"])
    kind: str = Field(..., description="Department kind: academic or service", examples=["service"])
    applicability: str = Field(..., description="Applicability rule", examples=["ALWAYS"])
    description: str | None = Field(None, description="Department description or location")
    category: str = Field(..., description="Computed category: ACADEMIC, UNIVERSITY_OFFICE, HOSTEL, LAB_WORKSHOP, ADDITIONAL_FACILITY", examples=["UNIVERSITY_OFFICE"])
    label: str = Field(..., description="Human-readable category label", examples=["University office"])
    is_active: bool = Field(True, description="Whether department is active")
    has_active_officer: bool = Field(True, description="Whether department has at least one active dealing officer")


class HoDRequestDetailResponse(BaseModel):
    """Full detail view for HoD and Academic Officer review of a student clearance request."""
    request_id: int = Field(..., description="Clearance request ID", examples=[1])
    status: ClearanceStatus = Field(..., description="Overall clearance lifecycle status", examples=[ClearanceStatus.HOD_REVIEW])
    student_name: str = Field(..., description="Student full name", examples=["Arjun Mehta"])
    registration_number: str = Field(..., description="Student registration number", examples=["DEMO2026001"])
    programme_name: str = Field(..., description="Enrolled course", examples=["Bachelor of Technology (B.Tech.) Computer Engineering"])
    academic_department: str | None = Field(None, description="Student's academic department name", examples=["Skill Department of CS/IT"])
    is_hosteller: bool | None = Field(None, description="Hosteller status (declared)", examples=[True])
    declared_is_hosteller: bool | None = Field(None, description="Student hostel residency declaration", examples=[True])
    declared_subjects: list[str] = Field(default_factory=list, description="All declared lab course codes and names", examples=[["CSE-L101: Data Structures Lab"]])
    others_note: str | None = Field(None, description="Special declaration note from student", examples=["Project submitted in Lab-2"])
    submitted_at: datetime = Field(..., description="Initial submission timestamp")
    hod_remarks: str | None = Field(None, description="Previous HoD rejection remarks if any")
    certificate_code: str | None = Field(None, description="Official clearance certificate UUID code if cleared", examples=["c8e54701-d70c-43a4-8490-6ce3b49725f8"])
    approvals: list[DepartmentApprovalItem] = Field(..., description="Full table of all departmental clearance decisions")
    can_add_departments: list[DepartmentResponse] = Field(default_factory=list, description="Offices that can still be added to the request")


AcademicRequestDetailResponse = HoDRequestDetailResponse


class AddOfficeRequest(BaseModel):
    """Payload for staff to add an office to an active clearance request."""
    department_id: int = Field(..., description="ID of department to add", examples=[5])
    reason: str = Field(..., min_length=1, max_length=500, description="Mandatory justification for adding office", examples=["Workshop dues pending"])


class DeclareLabCoursesRequest(BaseModel):
    """Payload for student to declare additional lab subjects."""
    lab_course_ids: list[int] = Field(..., description="List of lab course IDs to declare", examples=[[1, 2]])


class StudentCancelRequest(BaseModel):
    """Optional payload when student cancels request."""
    reason: str | None = Field(None, description="Optional cancellation reason", examples=["Want to re-declare lab subjects"])


class StaffCancelRequest(BaseModel):
    """Payload when department officer or admin cancels request."""
    reason: str = Field(..., min_length=1, max_length=1000, description="Mandatory reason for cancellation", examples=["Student withdrew application"])


class CancelResponse(BaseModel):
    """Response returned upon cancelling a clearance request."""
    detail: str = Field("Clearance request successfully cancelled.", description="Status message")
    request_id: int = Field(..., description="ID of cancelled request")
    status: ClearanceStatus = Field(ClearanceStatus.CANCELLED, description="Updated status")


