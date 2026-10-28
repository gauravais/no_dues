"""Chairperson / HoD endpoints: queue of student requests in HOD_REVIEW, inspection, and final clearance approval."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from backend.app.api.deps import SessionDep, require_roles
from backend.app.models.user import User, UserRole
from backend.app.models.clearance import (
    ClearanceRequest,
    ClearanceStatus,
    DepartmentApproval,
)
from backend.app.models.roster import StudentRoster
from backend.app.models.university import Programme
from backend.app.schemas.workflow import (
    HoDQueueItem,
    HoDRequestDetailResponse,
    DecisionRequest,
    DepartmentApprovalItem,
)
from backend.app.schemas.common import ErrorResponse
from backend.app.services.exceptions import (
    WorkflowNotFoundError,
    WorkflowConflictError,
    WorkflowBadRequestError,
)
from backend.app.services.workflow import hod_decide

router = APIRouter(prefix="/hod", tags=["HoD"])
require_hod = require_roles(UserRole.hod)


def _format_hod_detail(req: ClearanceRequest) -> HoDRequestDetailResponse:
    r = req.roster_entry
    prog_name = r.programme.name if (r and r.programme) else "Unknown"

    approval_items = [
        DepartmentApprovalItem(
            id=a.id,
            department_id=a.department_id,
            department_name=a.department.name if a.department else f"Department #{a.department_id}",
            department_kind=a.department.kind.value if a.department else "service",
            status=a.status,
            remarks=a.remarks,
            previous_remarks=a.previous_remarks,
            decided_at=a.decided_at,
            decided_by_name=a.decided_by_user.full_name if a.decided_by_user else None,
            resubmission_count=a.resubmission_count,
        )
        for a in (req.approvals or [])
    ]

    cert_code = None
    if req.status in (ClearanceStatus.CLEARED, ClearanceStatus.REFUND_VERIFIED) and req.certificate:
        cert_code = req.certificate.certificate_code

    return HoDRequestDetailResponse(
        request_id=req.id,
        status=req.status,
        student_name=r.name if r else "Unknown",
        registration_number=r.registration_number if r else "Unknown",
        programme_name=prog_name,
        is_hosteller=r.is_hosteller if r else False,
        submitted_at=req.submitted_at,
        hod_remarks=req.hod_remarks,
        certificate_code=cert_code,
        approvals=approval_items,
    )


@router.get(
    "/queue",
    response_model=list[HoDQueueItem],
    status_code=status.HTTP_200_OK,
    operation_id="get_hod_clearance_queue",
    summary="Get HoD Review Queue",
    description=(
        "Returns all clearance requests in HOD_REVIEW status for students enrolled under "
        "the Chairperson / HoD's academic department."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "HoD has no assigned academic department"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-HoD roles"},
    },
)
def get_hod_queue(
    db: SessionDep,
    current_user: User = Depends(require_hod),
) -> list[HoDQueueItem]:
    if not current_user.department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HoD user is not associated with an academic department.",
        )

    # Find requests in HOD_REVIEW whose student's programme academic_department_id matches HoD
    query = (
        select(ClearanceRequest)
        .where(ClearanceRequest.status == ClearanceStatus.HOD_REVIEW)
        .join(StudentRoster, StudentRoster.id == ClearanceRequest.roster_id)
        .join(Programme, Programme.id == StudentRoster.programme_id)
        .where(Programme.academic_department_id == current_user.department_id)
        .options(
            joinedload(ClearanceRequest.roster_entry).joinedload(StudentRoster.programme)
        )
        .order_by(ClearanceRequest.updated_at.asc())
    )

    requests = db.execute(query).scalars().all()

    items = []
    for req in requests:
        r = req.roster_entry
        prog_name = r.programme.name if (r and r.programme) else "Unknown"
        items.append(
            HoDQueueItem(
                request_id=req.id,
                student_name=r.name if r else "Unknown",
                registration_number=r.registration_number if r else "Unknown",
                programme_name=prog_name,
                submitted_at=req.submitted_at,
                status=req.status,
            )
        )

    return items


@router.get(
    "/requests/{request_id}",
    response_model=HoDRequestDetailResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_hod_request_detail",
    summary="Inspect Clearance Request Details",
    description=(
        "Returns the full departmental approval history and student details for an academic clearance request. "
        "Accessible only if the student belongs to the HoD's department."
    ),
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-HoD roles"},
        404: {"model": ErrorResponse, "description": "Clearance request not found or belongs to another department"},
    },
)
def get_hod_request_detail(
    request_id: int,
    db: SessionDep,
    current_user: User = Depends(require_hod),
) -> HoDRequestDetailResponse:
    req = db.execute(
        select(ClearanceRequest)
        .where(ClearanceRequest.id == request_id)
        .options(
            joinedload(ClearanceRequest.roster_entry).joinedload(StudentRoster.programme),
            joinedload(ClearanceRequest.approvals).joinedload(DepartmentApproval.department),
            joinedload(ClearanceRequest.approvals).joinedload(DepartmentApproval.decided_by_user),
            joinedload(ClearanceRequest.certificate),
        )
    ).unique().scalar_one_or_none()

    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clearance request not found.",
        )

    # Validate HoD department matches student's academic department
    student_academic_dept_id = req.roster_entry.programme.academic_department_id
    if student_academic_dept_id != current_user.department_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clearance request does not belong to your academic department.",
        )

    return _format_hod_detail(req)


@router.post(
    "/requests/{request_id}/decision",
    response_model=HoDRequestDetailResponse,
    status_code=status.HTTP_200_OK,
    operation_id="decide_hod_clearance",
    summary="Submit Chairperson / HoD Final Clearance Decision",
    description=(
        "Chairperson / HoD grants final approval or rejection of the clearance application. "
        "Approval sets status to CLEARED and generates an official Certificate record. "
        "Rejection (with mandatory remarks) sets status to ACTION_NEEDED."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Mandatory remarks missing for rejection"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-HoD roles"},
        404: {"model": ErrorResponse, "description": "Request not found or not in HoD's department"},
        409: {"model": ErrorResponse, "description": "Request is not in HOD_REVIEW status"},
    },
)
def decide_hod_endpoint(
    request_id: int,
    body: DecisionRequest,
    db: SessionDep,
    current_user: User = Depends(require_hod),
) -> HoDRequestDetailResponse:
    try:
        req = hod_decide(
            session=db,
            hod_user=current_user,
            request_id=request_id,
            decision=body.decision,
            remarks=body.remarks,
        )
        return _format_hod_detail(req)
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except WorkflowConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
    except WorkflowBadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
