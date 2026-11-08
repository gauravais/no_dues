"""Student clearance endpoints: initiation, tracking, and resubmissions."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select, or_
from sqlalchemy.orm import joinedload

from backend.app.api.deps import SessionDep, require_roles
from backend.app.core.config import settings
from backend.app.core.crypto import encrypt_bank_account
from backend.app.models.user import User, UserRole
from backend.app.models.clearance import ClearanceRequest, ApprovalStatus, ClearanceStatus, DepartmentApproval
from backend.app.models.university import Faculty, Department, Programme, DepartmentApplicability, DepartmentKind
from backend.app.models.lab_course import LabCourse
from backend.app.models.bank import BankDetail, mask_account_number
from backend.app.models.certificate import Certificate
from backend.app.models.roster import StudentRoster, RosterAssignedDepartment
from backend.app.models.refund import Refund, RefundStatus
from backend.app.models.audit import AuditLog
from backend.app.schemas.workflow import (
    CurrentRequestResponse,
    DepartmentApprovalItem,
    DeclareLabCoursesRequest,
    StudentCancelRequest,
    DepartmentResponse,
    StudentRefundConfirmRequest,
)
from backend.app.schemas.bank import BankDetailRead, BankDetailUpdate
from backend.app.schemas.department import (
    StudentLabCatalogItem,
    AssignedOnlyDepartmentItem,
    StudentLabCatalogResponse,
    AddDepartmentRequest,
)
from backend.app.schemas.common import ErrorResponse, MessageResponse
from pydantic import BaseModel, Field
from backend.app.services.exceptions import (
    WorkflowNotFoundError,
    WorkflowConflictError,
    WorkflowBadRequestError,
    WorkflowForbiddenError,
)
from backend.app.services.email import notify_student_refund_issue
from backend.app.services.workflow import (
    create_request,
    add_department_to_request,
    student_declare_lab_courses,
    resubmit_department,
    student_resubmit_to_hod,
    student_cancel_request,
    active_officers_for,
)
from backend.app.services.certificate_pdf import generate_clearance_certificate_pdf
from backend.app.services.email import notify_student_refund_issue

router = APIRouter(prefix="/student", tags=["Student"])
require_student = require_roles(UserRole.student)


def _format_request_response(req: ClearanceRequest, db: SessionDep | None = None) -> CurrentRequestResponse:
    approvals = req.approvals or []
    approved_count = sum(1 for a in approvals if a.status == ApprovalStatus.APPROVED)
    total_count = len(approvals)
    progress_str = f"{approved_count} of {total_count} approved"

    approval_items = [
        DepartmentApprovalItem(
            id=a.id,
            department_id=a.department_id,
            department_name=a.department.name if a.department else f"Department #{a.department_id}",
            department_kind=a.department.kind.value if a.department else "service",
            department_category=a.department.category if a.department else None,
            department_label=a.department.category_label if a.department else None,
            status=a.status,
            remarks=a.remarks,
            previous_remarks=a.previous_remarks,
            decided_at=a.decided_at,
            decided_by_name=a.decided_by_user.full_name or a.decided_by_user.email if a.decided_by_user else None,
            added_by_user_id=a.added_by_user_id,
            added_by_name=a.added_by_user.full_name or a.added_by_user.email if a.added_by_user else None,
            added_reason=a.added_reason,
            resubmission_count=a.resubmission_count,
        )
        for a in approvals
    ]

    refund = req.refund
    ref_status = None
    dep_amt = None
    ded_amt = None
    fin_amt = None
    accounts_note = None
    pay_ref = None
    paid_on = None
    payment_mode = None
    failure_reason = None
    student_confirmed_at = None
    student_issue_note = None
    student_issue_at = None

    if refund and refund.status != RefundStatus.PENDING_VERIFICATION:
        ref_status = refund.status
        dep_amt = refund.deposit_amount
        ded_amt = refund.deductions
        fin_amt = refund.final_amount
        accounts_note = refund.accounts_note

        if refund.status == RefundStatus.PROCESSED:
            pay_ref = getattr(refund, "payment_reference", None)
            paid_on = getattr(refund, "paid_on", None)
            payment_mode = getattr(refund, "payment_mode", None)
            if not pay_ref and db is not None:
                audit_entry = db.execute(
                    select(AuditLog)
                    .where(
                        AuditLog.entity_type == "clearance_requests",
                        AuditLog.entity_id == req.id,
                        AuditLog.action == "MARK_REFUND_PROCESSED",
                    )
                    .order_by(AuditLog.created_at.desc())
                ).scalars().first()
                if audit_entry and audit_entry.details:
                    pay_ref = audit_entry.details.get("payment_reference")
        elif refund.status == RefundStatus.PAYMENT_FAILED:
            failure_reason = getattr(refund, "failure_reason", None)

    if refund:
        student_confirmed_at = getattr(refund, "student_confirmed_at", None)
        student_issue_note = getattr(refund, "student_issue_note", None)
        student_issue_at = getattr(refund, "student_issue_at", None)

    return CurrentRequestResponse(
        id=req.id,
        status=req.status,
        progress=progress_str,
        submitted_at=req.submitted_at,
        hod_remarks=req.hod_remarks,
        approvals=approval_items,
        refund_status=ref_status,
        deposit_amount=dep_amt,
        deductions=ded_amt,
        final_amount=fin_amt,
        accounts_note=accounts_note,
        payment_reference=pay_ref,
        paid_on=paid_on,
        payment_mode=payment_mode,
        failure_reason=failure_reason,
        student_confirmed_at=student_confirmed_at,
        student_issue_note=student_issue_note,
        student_issue_at=student_issue_at,
    )


class StudentClearanceApply(BaseModel):
    """Declarations submitted when applying for clearance."""
    is_hosteller: bool = Field(False, description="Declare whether student resided in university hostel")
    lab_course_ids: list[int] | None = Field(None, description="Declared lab course IDs (mapped to their lab offices)", examples=[[1, 2]])
    lab_workshop_department_ids: list[int] | None = Field(default_factory=list, description="Directly declared active Lab / Workshop department IDs", examples=[[5]])
    other_department_ids: list[int] | None = Field(default_factory=list, alias="other_office_ids", description="Optional list of additional ASSIGNED_ONLY department/office IDs", examples=[[26, 27]])
    others_note: str | None = Field(None, max_length=1000, description="Optional note for any additional dues/facilities")
    bank: BankDetailUpdate | None = Field(None, description="Student refund bank details (if not already set)")

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }


@router.post(
    "/requests",
    response_model=CurrentRequestResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_clearance_request",
    summary="Apply for No-Dues Clearance",
    description=(
        "Student initiates a clearance application from their declarations. The system automatically creates parallel clearance "
        "reviews for all applicable departments (always-applicable, hosteller if declared, declared labs/workshops, "
        "and their own academic department) and registers a refund entry. Only one active request is allowed."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Student profile or roster missing, or bank details missing"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-student roles"},
        409: {"model": ErrorResponse, "description": "Student already has an active clearance request, or office lacks active officer"},
    },
)
def apply_clearance(
    db: SessionDep,
    student_user: User = Depends(require_student),
    body: StudentClearanceApply | None = None,
) -> CurrentRequestResponse:
    if body and body.bank and student_user.roster_id:
        roster = db.get(StudentRoster, student_user.roster_id)
        if roster:
            enc_acc = encrypt_bank_account(body.bank.account_number.strip())
            bank = db.execute(
                select(BankDetail).where(BankDetail.roster_id == roster.id)
            ).scalars().first()
            if bank:
                bank.account_holder_name = body.bank.account_holder_name.strip()
                bank.account_number = enc_acc
                bank.ifsc_code = body.bank.ifsc_code.strip().upper()
                bank.bank_address = body.bank.bank_address.strip()
            else:
                bank = BankDetail(
                    roster_id=roster.id,
                    account_holder_name=body.bank.account_holder_name.strip(),
                    account_number=enc_acc,
                    ifsc_code=body.bank.ifsc_code.strip().upper(),
                    bank_address=body.bank.bank_address.strip(),
                )
                db.add(bank)
            db.commit()

    try:
        other_ids = body.other_department_ids if body else None
        lab_workshop_ids = body.lab_workshop_department_ids if body else None
        req = create_request(
            session=db,
            student_user=student_user,
            declared_is_hosteller=bool(body.is_hosteller) if body else False,
            declared_lab_course_ids=body.lab_course_ids if body else None,
            lab_workshop_department_ids=lab_workshop_ids,
            other_department_ids=other_ids,
            others_note=body.others_note if body else None,
        )
        return _format_request_response(req, db)
    except WorkflowConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
    except WorkflowBadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)



@router.get(
    "/requests/current",
    response_model=CurrentRequestResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_current_request",
    summary="Get Current Clearance Progress",
    description=(
        "Returns the active clearance status, progress percentage/ratio, and department-by-department "
        "reviews with status, remarks, and resubmission counts."
    ),
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-student roles"},
        404: {"model": ErrorResponse, "description": "No clearance request found for current student"},
    },
)
def get_current_request(
    db: SessionDep,
    student_user: User = Depends(require_student),
) -> CurrentRequestResponse:
    req = db.execute(
        select(ClearanceRequest)
        .where(ClearanceRequest.roster_id == student_user.roster_id)
        .options(
            joinedload(ClearanceRequest.approvals).joinedload(DepartmentApproval.department),
            joinedload(ClearanceRequest.approvals).joinedload(DepartmentApproval.decided_by_user),
            joinedload(ClearanceRequest.refund),
        )
        .order_by(ClearanceRequest.created_at.desc())
    ).unique().scalars().first()

    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No clearance request found for your account.",
        )

    return _format_request_response(req, db)


@router.post(
    "/requests/{request_id}/departments/{department_id}/resubmit",
    response_model=DepartmentApprovalItem,
    status_code=status.HTTP_200_OK,
    operation_id="resubmit_department_clearance",
    summary="Resubmit to Rejected Department",
    description=(
        "Allows a student to resubmit their clearance only to a department that previously rejected it. "
        "The approval status is reset to PENDING and the resubmission count is incremented. Other departments are untouched."
    ),
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-student roles"},
        404: {"model": ErrorResponse, "description": "Clearance request or department approval not found"},
        409: {"model": ErrorResponse, "description": "Department approval is not currently in REJECTED status"},
    },
)
def resubmit_to_department(
    request_id: int,
    department_id: int,
    db: SessionDep,
    student_user: User = Depends(require_student),
) -> DepartmentApprovalItem:
    try:
        approval = resubmit_department(db, student_user, request_id, department_id)
        return DepartmentApprovalItem(
            id=approval.id,
            department_id=approval.department_id,
            department_name=approval.department.name if approval.department else f"Department #{approval.department_id}",
            department_kind=approval.department.kind.value if approval.department else "service",
            status=approval.status,
            remarks=approval.remarks,
            previous_remarks=approval.previous_remarks,
            decided_at=approval.decided_at,
            decided_by_name=approval.decided_by_user.full_name if approval.decided_by_user else None,
            resubmission_count=approval.resubmission_count,
        )
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except WorkflowConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)


@router.post(
    "/requests/{request_id}/resubmit-to-hod",
    response_model=CurrentRequestResponse,
    status_code=status.HTTP_200_OK,
    operation_id="resubmit_to_hod",
    summary="Resubmit Clearance to Chairperson / HoD",
    description=(
        "When all department approvals are approved but the HoD previously rejected the request with remarks, "
        "the student calls this endpoint to clear the HoD remarks and move the request back into HOD_REVIEW."
    ),
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-student roles"},
        404: {"model": ErrorResponse, "description": "Clearance request not found"},
        409: {"model": ErrorResponse, "description": "Cannot resubmit to HoD until all department rejections are resolved or no HoD remarks pending"},
    },
)
def resubmit_to_hod_endpoint(
    request_id: int,
    db: SessionDep,
    student_user: User = Depends(require_student),
) -> CurrentRequestResponse:
    try:
        req = student_resubmit_to_hod(db, student_user, request_id)
        return _format_request_response(req, db)
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except WorkflowConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)


@router.post(
    "/requests/{request_id}/lab-courses",
    response_model=CurrentRequestResponse,
    status_code=status.HTTP_200_OK,
    operation_id="declare_additional_lab_courses",
    summary="Declare Additional Lab Subjects",
    description=(
        "Student declares additional laboratory subjects while their clearance request is active. "
        "Any newly declared subject belonging to an unassigned lab office automatically triggers a pending clearance review."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid lab course list"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-student roles"},
        404: {"model": ErrorResponse, "description": "Clearance request not found"},
        409: {"model": ErrorResponse, "description": "Clearance request is already finalized or lab department lacks active officer"},
    },
)
def declare_additional_lab_courses(
    request_id: int,
    body: DeclareLabCoursesRequest,
    db: SessionDep,
    student_user: User = Depends(require_student),
) -> CurrentRequestResponse:
    try:
        req = student_declare_lab_courses(
            session=db,
            student_user=student_user,
            request_id=request_id,
            lab_course_ids=body.lab_course_ids,
        )
        return _format_request_response(req, db)
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except WorkflowConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
    except WorkflowBadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/requests/{request_id}/cancel",
    response_model=CurrentRequestResponse,
    status_code=status.HTTP_200_OK,
    operation_id="student_cancel_clearance_request",
    summary="Cancel Clearance Request",
    description="Allows a student to cancel their clearance request provided all departmental approvals are still in PENDING status.",
    responses={
        400: {"model": ErrorResponse, "description": "Cannot cancel: some approvals have already been decided or request finalized"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-student roles or requests belonging to another student"},
        404: {"model": ErrorResponse, "description": "Clearance request not found"},
    },
)
def cancel_clearance_request(
    request_id: int,
    db: SessionDep,
    student_user: User = Depends(require_student),
    body: StudentCancelRequest | None = None,
) -> CurrentRequestResponse:
    try:
        reason = body.reason if body else None
        req = student_cancel_request(db, request_id, student_user, reason)
        return _format_request_response(req, db)
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except WorkflowBadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except WorkflowForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)


@router.get(
    "/bank-details",
    response_model=BankDetailRead,
    status_code=status.HTTP_200_OK,
    operation_id="get_student_bank_details",
    summary="Get Masked Bank Details",
    description=(
        "Returns the student's saved bank account details with the account number securely masked "
        "(e.g., '********1234') along with IFSC, account holder name, and branch address."
    ),
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-student roles"},
        404: {"model": ErrorResponse, "description": "Bank details not found for this student"},
    },
)
def get_bank_details(
    db: SessionDep,
    student_user: User = Depends(require_student),
) -> BankDetailRead:
    if not student_user.roster_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student roster profile not found")

    bank = db.execute(
        select(BankDetail).where(BankDetail.roster_id == student_user.roster_id)
    ).scalars().first()

    if not bank:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank details not found")

    return BankDetailRead(
        account_number_masked=mask_account_number(bank.account_number),
        ifsc_code=bank.ifsc_code,
        account_holder_name=bank.account_holder_name,
        bank_address=bank.bank_address,
    )


@router.put(
    "/bank-details",
    response_model=BankDetailRead,
    status_code=status.HTTP_200_OK,
    operation_id="update_student_bank_details",
    summary="Update Bank Details",
    description=(
        "Updates or sets the student's bank details for security deposit refunds. Accepts full account number "
        "(digits only, length 9 to 18) and standard IFSC code. The full account number is never echoed back."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid bank details or missing roster entry"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-student roles"},
        409: {"model": ErrorResponse, "description": "Bank details cannot be modified after refund has been processed"},
    },
)
def update_bank_details(
    body: BankDetailUpdate,
    db: SessionDep,
    student_user: User = Depends(require_student),
) -> BankDetailRead:
    if not student_user.roster_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Student roster profile not found")

    processed_refund = db.execute(
        select(Refund)
        .join(ClearanceRequest, Refund.request_id == ClearanceRequest.id)
        .where(
            ClearanceRequest.roster_id == student_user.roster_id,
            Refund.status == RefundStatus.PROCESSED,
        )
    ).scalars().first()
    if processed_refund:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bank details cannot be modified after refund has been processed.",
        )

    bank = db.execute(
        select(BankDetail).where(BankDetail.roster_id == student_user.roster_id)
    ).scalars().first()

    enc_acc = encrypt_bank_account(body.account_number.strip())
    if bank:
        bank.account_holder_name = body.account_holder_name.strip()
        bank.account_number = enc_acc
        bank.ifsc_code = body.ifsc_code.strip().upper()
        bank.bank_address = body.bank_address.strip()
    else:
        bank = BankDetail(
            roster_id=student_user.roster_id,
            account_holder_name=body.account_holder_name.strip(),
            account_number=enc_acc,
            ifsc_code=body.ifsc_code.strip().upper(),
            bank_address=body.bank_address.strip(),
        )
        db.add(bank)

    db.flush()

    audit = AuditLog(
        user_id=student_user.id,
        action="UPDATE_BANK_DETAILS",
        entity_type="bank_details",
        entity_id=bank.id,
        details={
            "account_number_masked": mask_account_number(bank.account_number),
            "ifsc_code": bank.ifsc_code,
            "account_holder_name": bank.account_holder_name,
            "bank_address": bank.bank_address,
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(bank)

    return BankDetailRead(
        account_number_masked=mask_account_number(bank.account_number),
        ifsc_code=bank.ifsc_code,
        account_holder_name=bank.account_holder_name,
        bank_address=bank.bank_address,
    )


@router.post(
    "/requests/{request_id}/refund/confirm",
    response_model=CurrentRequestResponse,
    status_code=status.HTTP_200_OK,
    operation_id="confirm_refund_received",
    summary="Confirm Refund Receipt or Report Issue",
    description=(
        "Student confirms receipt of their refunded deposit once PROCESSED, or reports an issue/delay with a mandatory note "
        "when PROCESSED or PAYMENT_FAILED."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Mandatory issue note missing or invalid"},
        403: {"model": ErrorResponse, "description": "Forbidden: not your clearance request"},
        404: {"model": ErrorResponse, "description": "Clearance request or refund record not found"},
        409: {"model": ErrorResponse, "description": "Invalid refund status for this action"},
    },
)
def confirm_or_report_refund(
    request_id: int,
    body: StudentRefundConfirmRequest,
    db: SessionDep,
    student_user: User = Depends(require_student),
) -> CurrentRequestResponse:
    req = db.execute(
        select(ClearanceRequest)
        .where(ClearanceRequest.id == request_id)
        .options(
            joinedload(ClearanceRequest.refund),
            joinedload(ClearanceRequest.approvals).joinedload(DepartmentApproval.department),
            joinedload(ClearanceRequest.approvals).joinedload(DepartmentApproval.decided_by_user),
        )
    ).scalars().first()

    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clearance request not found")

    if req.roster_id != student_user.roster_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this clearance request")

    refund = req.refund
    if not refund:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund record not found for this request")

    now = datetime.now(timezone.utc)
    if body.received:
        if refund.status != RefundStatus.PROCESSED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Refund receipt can only be confirmed when status is PROCESSED (current: {refund.status.value}).",
            )
        refund.student_confirmed_at = now
        audit = AuditLog(
            user_id=student_user.id,
            action="CONFIRM_REFUND_RECEIVED",
            entity_type="clearance_requests",
            entity_id=req.id,
            details={"refund_id": refund.id},
        )
        db.add(audit)
    else:
        if refund.status not in (RefundStatus.PROCESSED, RefundStatus.PAYMENT_FAILED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Refund issues can only be reported when status is PROCESSED or PAYMENT_FAILED (current: {refund.status.value}).",
            )
        cleaned_note = body.note.strip() if body.note else ""
        if not cleaned_note:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A non-empty note is required when reporting a refund issue.",
            )
        refund.student_issue_note = cleaned_note
        refund.student_issue_at = now
        refund.student_issue_resolved_at = None

        notify_student_refund_issue(db, req, cleaned_note)

        audit = AuditLog(
            user_id=student_user.id,
            action="REPORT_REFUND_ISSUE",
            entity_type="clearance_requests",
            entity_id=req.id,
            details={"refund_id": refund.id, "note": cleaned_note},
        )
        db.add(audit)

    db.commit()
    db.refresh(req)
    return _format_request_response(req, db)


@router.get(
    "/requests/{request_id}/certificate.pdf",
    status_code=status.HTTP_200_OK,
    operation_id="download_clearance_certificate_pdf",
    summary="Download Official Clearance Certificate (PDF)",
    description=(
        "Generates and downloads the official university No-Dues Clearance Certificate in PDF format. "
        "Accessible only to the student who owns the request, and only after final clearance (status CLEARED "
        "or REFUND_VERIFIED). Includes an authentic QR code linking to the public verification endpoint."
    ),
    responses={
        200: {"content": {"application/pdf": {}}, "description": "Clearance Certificate in PDF binary format"},
        400: {"model": ErrorResponse, "description": "Request not cleared yet"},
        403: {"model": ErrorResponse, "description": "Forbidden: not your clearance request"},
        404: {"model": ErrorResponse, "description": "Clearance request or certificate record not found"},
    },
)
def download_certificate_pdf(
    request_id: int,
    db: SessionDep,
    student_user: User = Depends(require_student),
) -> Response:
    req = db.execute(
        select(ClearanceRequest)
        .where(ClearanceRequest.id == request_id)
        .options(
            joinedload(ClearanceRequest.certificate),
            joinedload(ClearanceRequest.roster_entry)
            .joinedload(StudentRoster.programme)
            .joinedload(Programme.department)
            .joinedload(Department.faculty),
            joinedload(ClearanceRequest.approvals)
            .joinedload(DepartmentApproval.department),
            joinedload(ClearanceRequest.hod_user),
        )
    ).scalars().first()

    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clearance request not found")

    if req.roster_id != student_user.roster_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only access certificates for your own clearance requests")

    if req.status not in (ClearanceStatus.CLEARED, ClearanceStatus.REFUND_VERIFIED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Certificate is available only for CLEARED or REFUND_VERIFIED requests. Current status: {req.status.value}",
        )

    cert = req.certificate
    if not cert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate record not found for this request")

    roster = req.roster_entry
    programme = roster.programme
    department = programme.department if programme else None
    faculty = department.faculty if department else None

    university_name = "Shri Vishwakarma Skill University (SVSU)"
    student_name = roster.name
    reg_number = roster.registration_number
    programme_name = programme.name if programme else "N/A"
    department_name = department.name if department else "N/A"
    faculty_name = faculty.name if faculty else "Skill Faculty of Engineering & Technology"
    cert_code = cert.certificate_code
    issued_at = cert.issued_at

    approvals_data = []
    for a in req.approvals or []:
        dname = a.department.name if a.department else f"Department #{a.department_id}"
        dstatus = a.status.value
        ddate = a.decided_at.strftime("%Y-%m-%d %H:%M") if a.decided_at else "Approved"
        approvals_data.append((dname, dstatus, ddate))

    # HoD info
    hod_name = "Chairperson (HoD)"
    if cert.hod_user and cert.hod_user.full_name:
        hod_name = cert.hod_user.full_name
    elif req.hod_user and req.hod_user.full_name:
        hod_name = req.hod_user.full_name

    verify_url = f"{settings.PUBLIC_BASE_URL}/verify/{cert_code}"

    pdf_bytes = generate_clearance_certificate_pdf(
        university_name=university_name,
        student_name=student_name,
        registration_number=reg_number,
        programme_name=programme_name,
        department_name=department_name,
        faculty_name=faculty_name,
        certificate_code=cert_code,
        issued_at=issued_at,
        approvals_data=approvals_data,
        hod_name=hod_name,
        verify_url=verify_url,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="clearance_certificate_{cert_code}.pdf"',
        },
    )


@router.get(
    "/lab-catalog",
    response_model=StudentLabCatalogResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_student_lab_catalog",
    summary="Get Available Lab Courses and Fallback Offices",
    description="Returns active lab courses for the student's academic programme, plus all ASSIGNED_ONLY service departments.",
    responses={
        400: {"model": ErrorResponse, "description": "Student roster profile not found"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-students"},
        404: {"model": ErrorResponse, "description": "Student programme not found"},
    },
)
@router.get(
    "/lab-courses",
    response_model=StudentLabCatalogResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_student_lab_catalog(
    db: SessionDep,
    student_user: User = Depends(require_student),
) -> StudentLabCatalogResponse:
    if not student_user.roster_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Student roster profile not found")
    roster = db.get(StudentRoster, student_user.roster_id)
    if not roster or not roster.programme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student academic programme not found")

    academic_dept_id = roster.programme.academic_department_id

    courses = db.execute(
        select(LabCourse)
        .join(Department, LabCourse.lab_department_id == Department.id)
        .where(
            or_(
                LabCourse.academic_department_id == academic_dept_id,
                LabCourse.academic_department_id.is_(None),
            ),
            LabCourse.is_active == True,
            Department.is_active == True,
        )
        .options(joinedload(LabCourse.lab_department))
        .order_by(LabCourse.code.asc())
    ).scalars().all()

    catalog_items = [
        StudentLabCatalogItem(
            id=c.id,
            code=c.code,
            name=c.name,
            lab_department_id=c.lab_department_id,
            lab_department_name=c.lab_department.name if c.lab_department else f"Department #{c.lab_department_id}",
            specialization=c.specialization,
            category=c.lab_department.category if c.lab_department else "LAB_WORKSHOP",
            label=c.lab_department.category_label if c.lab_department else "Lab / Workshop",
        )
        for c in courses
    ]

    direct_depts = db.execute(
        select(Department)
        .where(
            Department.applicability == DepartmentApplicability.LAB_WORKSHOP,
            Department.is_active == True,
        )
        .order_by(Department.name.asc())
    ).scalars().all()

    direct_items = [
        DepartmentResponse(
            id=d.id,
            name=d.name,
            kind=d.kind.value,
            applicability=d.applicability.value,
            description=d.description,
            category=d.category,
            label=d.category_label,
            is_active=d.is_active,
            has_active_officer=bool(active_officers_for(db, d.id)),
        )
        for d in direct_depts
    ]

    assigned_depts = db.execute(
        select(Department)
        .where(
            Department.applicability == DepartmentApplicability.ASSIGNED_ONLY,
            Department.is_active == True,
        )
        .order_by(Department.name.asc())
    ).scalars().all()

    assigned_items = [
        AssignedOnlyDepartmentItem(
            id=d.id,
            name=d.name,
            description=d.description,
            category=d.category,
            label=d.category_label,
            is_active=d.is_active,
            has_active_officer=bool(active_officers_for(db, d.id)),
        )
        for d in assigned_depts
    ]

    return StudentLabCatalogResponse(
        lab_courses=catalog_items,
        assigned_only_departments=assigned_items,
        direct_offices=direct_items,
    )


@router.post(
    "/requests/{request_id}/departments",
    response_model=DepartmentApprovalItem,
    status_code=status.HTTP_201_CREATED,
    operation_id="add_department_to_clearance_request",
    summary="Add Department to Active Clearance Request",
    description="Adds an ASSIGNED_ONLY or applicable department to an active clearance request. Fails with 409 if department already added or has no active dealing officer.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid department or request"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-students"},
        404: {"model": ErrorResponse, "description": "Request or department not found"},
        409: {"model": ErrorResponse, "description": "Department already added, or has no active dealing officer"},
    },
)
def add_department_endpoint(
    request_id: int,
    body: AddDepartmentRequest,
    db: SessionDep,
    student_user: User = Depends(require_student),
) -> DepartmentApprovalItem:
    try:
        approval = add_department_to_request(
            session=db,
            request_id=request_id,
            department_id=body.department_id,
            acting_user=student_user,
        )
        return DepartmentApprovalItem(
            id=approval.id,
            department_id=approval.department_id,
            department_name=approval.department.name if approval.department else f"Department #{approval.department_id}",
            department_kind=approval.department.kind.value if approval.department else "service",
            status=approval.status,
            remarks=approval.remarks,
            previous_remarks=approval.previous_remarks,
            decided_at=approval.decided_at,
            decided_by_name=None,
            resubmission_count=approval.resubmission_count,
        )
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except WorkflowConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
    except WorkflowBadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


