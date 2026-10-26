"""Student clearance endpoints: initiation, tracking, and resubmissions."""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from backend.app.api.deps import SessionDep, require_roles
from backend.app.core.config import settings
from backend.app.models.user import User, UserRole
from backend.app.models.clearance import ClearanceRequest, ApprovalStatus, ClearanceStatus, DepartmentApproval
from backend.app.models.university import Faculty, Department, Programme
from backend.app.models.bank import BankDetail, mask_account_number
from backend.app.models.certificate import Certificate
from backend.app.models.roster import StudentRoster
from backend.app.schemas.workflow import (
    CurrentRequestResponse,
    DepartmentApprovalItem,
)
from backend.app.schemas.bank import BankDetailRead, BankDetailUpdate
from backend.app.schemas.common import ErrorResponse, MessageResponse
from backend.app.services.exceptions import (
    WorkflowNotFoundError,
    WorkflowConflictError,
    WorkflowBadRequestError,
)
from backend.app.services.workflow import (
    create_request,
    resubmit_department,
    student_resubmit_to_hod,
)
from backend.app.services.certificate_pdf import generate_clearance_certificate_pdf

router = APIRouter(prefix="/student", tags=["Student"])
require_student = require_roles(UserRole.student)


def _format_request_response(req: ClearanceRequest) -> CurrentRequestResponse:
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
            status=a.status,
            remarks=a.remarks,
            decided_at=a.decided_at,
            resubmission_count=a.resubmission_count,
        )
        for a in approvals
    ]

    return CurrentRequestResponse(
        id=req.id,
        status=req.status,
        progress=progress_str,
        submitted_at=req.submitted_at,
        hod_remarks=req.hod_remarks,
        approvals=approval_items,
    )


@router.post(
    "/requests",
    response_model=CurrentRequestResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_clearance_request",
    summary="Apply for No-Dues Clearance",
    description=(
        "Student initiates a clearance application. The system automatically creates parallel clearance "
        "reviews for all applicable departments (always-applicable, hosteller if relevant, assigned labs/workshops, "
        "and their own academic department) and registers a refund entry. Only one active request is allowed."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Student profile or roster missing"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-student roles"},
        409: {"model": ErrorResponse, "description": "Student already has an active clearance request"},
    },
)
def apply_clearance(
    db: SessionDep,
    student_user: User = Depends(require_student),
) -> CurrentRequestResponse:
    try:
        req = create_request(db, student_user)
        return _format_request_response(req)
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
            joinedload(ClearanceRequest.approvals)
        )
        .order_by(ClearanceRequest.created_at.desc())
    ).scalars().first()

    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No clearance request found for your account.",
        )

    return _format_request_response(req)


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
            decided_at=approval.decided_at,
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
        return _format_request_response(req)
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except WorkflowConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)


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
    },
)
def update_bank_details(
    body: BankDetailUpdate,
    db: SessionDep,
    student_user: User = Depends(require_student),
) -> BankDetailRead:
    if not student_user.roster_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Student roster profile not found")

    bank = db.execute(
        select(BankDetail).where(BankDetail.roster_id == student_user.roster_id)
    ).scalars().first()

    if bank:
        bank.account_holder_name = body.account_holder_name.strip()
        bank.account_number = body.account_number.strip()
        bank.ifsc_code = body.ifsc_code.strip().upper()
        bank.bank_address = body.bank_address.strip()
    else:
        bank = BankDetail(
            roster_id=student_user.roster_id,
            account_holder_name=body.account_holder_name.strip(),
            account_number=body.account_number.strip(),
            ifsc_code=body.ifsc_code.strip().upper(),
            bank_address=body.bank_address.strip(),
        )
        db.add(bank)

    db.commit()
    db.refresh(bank)

    return BankDetailRead(
        account_number_masked=mask_account_number(bank.account_number),
        ifsc_code=bank.ifsc_code,
        account_holder_name=bank.account_holder_name,
        bank_address=bank.bank_address,
    )


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

