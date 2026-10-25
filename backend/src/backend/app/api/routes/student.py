"""Student clearance endpoints: initiation, tracking, and resubmissions."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from backend.app.api.deps import SessionDep, require_roles
from backend.app.models.user import User, UserRole
from backend.app.models.clearance import ClearanceRequest, ApprovalStatus
from backend.app.schemas.workflow import (
    CurrentRequestResponse,
    DepartmentApprovalItem,
)
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
