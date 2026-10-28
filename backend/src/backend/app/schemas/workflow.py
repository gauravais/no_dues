"""Pydantic schemas for clearance requests, approvals, and queue management."""
from datetime import datetime
from pydantic import BaseModel, Field
from backend.app.models.clearance import ApprovalStatus, ClearanceStatus


class DepartmentApprovalItem(BaseModel):
    """Detailed approval status for an applicable university department."""
    id: int = Field(..., description="Approval record ID", examples=[101])
    department_id: int = Field(..., description="Department ID", examples=[1])
    department_name: str = Field(..., description="Department title", examples=["Library"])
    department_kind: str = Field(..., description="Department category: academic or service", examples=["service"])
    status: ApprovalStatus = Field(..., description="Current approval status", examples=[ApprovalStatus.PENDING])
    remarks: str | None = Field(None, description="Department officer remarks (mandatory on rejection)", examples=["Fine pending: Rs. 150"])
    previous_remarks: str | None = Field(None, description="Previous rejection reason before student resubmitted", examples=["Fine pending: Rs. 150"])
    decided_at: datetime | None = Field(None, description="Timestamp when decision was rendered")
    decided_by_name: str | None = Field(None, description="Full name of officer who decided approval", examples=["Library Officer (Demo)"])
    resubmission_count: int = Field(..., description="Number of times student resubmitted to this department", examples=[0])


class CurrentRequestResponse(BaseModel):
    """Status summary and department-by-department breakdown of a clearance request."""
    id: int = Field(..., description="Clearance request ID", examples=[1])
    status: ClearanceStatus = Field(..., description="Overall clearance lifecycle status", examples=[ClearanceStatus.SUBMITTED])
    progress: str = Field(..., description="Progress indicator of approved departments", examples=["8 of 12 approved"])
    submitted_at: datetime = Field(..., description="Timestamp of initial submission")
    hod_remarks: str | None = Field(None, description="Chairperson / HoD remarks (if rejected during HOD review)", examples=["Subject project submission verification pending"])
    approvals: list[DepartmentApprovalItem] = Field(..., description="List of all department clearance reviews")


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


class DepartmentQueueItem(BaseModel):
    """Queue entry for department officers reviewing clearances."""
    approval_id: int = Field(..., description="Approval row ID", examples=[10])
    request_id: int = Field(..., description="Parent clearance request ID", examples=[1])
    student_name: str = Field(..., description="Student full name", examples=["Arjun Mehta"])
    registration_number: str = Field(..., description="Student registration number", examples=["DEMO2026001"])
    programme_name: str = Field(..., description="Student enrolled programme", examples=["Bachelor of Technology (B.Tech.) Computer Engineering"])
    status: ApprovalStatus = Field(..., description="Approval status", examples=[ApprovalStatus.PENDING])
    submitted_at: datetime = Field(..., description="Request submission timestamp")
    resubmission_count: int = Field(..., description="Number of resubmissions", examples=[0])


class DepartmentQueueResponse(BaseModel):
    """Paginated list of department clearance queue items."""
    items: list[DepartmentQueueItem] = Field(..., description="Pending or reviewed clearances for this department")
    total: int = Field(..., description="Total records matching query filter", examples=[1])
    limit: int = Field(..., description="Page size limit", examples=[50])
    offset: int = Field(..., description="Page offset", examples=[0])


class HoDQueueItem(BaseModel):
    """Queue entry for Chairperson / HoD reviewing completed departmental clearances."""
    request_id: int = Field(..., description="Clearance request ID", examples=[1])
    student_name: str = Field(..., description="Student full name", examples=["Arjun Mehta"])
    registration_number: str = Field(..., description="Student registration number", examples=["DEMO2026001"])
    programme_name: str = Field(..., description="Enrolled academic course", examples=["Bachelor of Technology (B.Tech.) Computer Engineering"])
    submitted_at: datetime = Field(..., description="Initial submission timestamp")
    status: ClearanceStatus = Field(..., description="Request status (should be HOD_REVIEW)", examples=[ClearanceStatus.HOD_REVIEW])


class HoDRequestDetailResponse(BaseModel):
    """Full detail view for HoD review of a student clearance request."""
    request_id: int = Field(..., description="Clearance request ID", examples=[1])
    status: ClearanceStatus = Field(..., description="Overall clearance lifecycle status", examples=[ClearanceStatus.HOD_REVIEW])
    student_name: str = Field(..., description="Student full name", examples=["Arjun Mehta"])
    registration_number: str = Field(..., description="Student registration number", examples=["DEMO2026001"])
    programme_name: str = Field(..., description="Enrolled course", examples=["Bachelor of Technology (B.Tech.) Computer Engineering"])
    is_hosteller: bool = Field(..., description="Hosteller status", examples=[True])
    submitted_at: datetime = Field(..., description="Initial submission timestamp")
    hod_remarks: str | None = Field(None, description="Previous HoD rejection remarks if any")
    certificate_code: str | None = Field(None, description="Official clearance certificate UUID code if cleared", examples=["c8e54701-d70c-43a4-8490-6ce3b49725f8"])
    approvals: list[DepartmentApprovalItem] = Field(..., description="Full table of all departmental clearance decisions")


class DepartmentResponse(BaseModel):
    """University department basic metadata."""
    id: int = Field(..., description="Department ID", examples=[1])
    name: str = Field(..., description="Department name", examples=["Central Library"])
    kind: str = Field(..., description="Department kind: academic or service", examples=["service"])
    applicability: str = Field(..., description="Applicability rule", examples=["ALWAYS"])

