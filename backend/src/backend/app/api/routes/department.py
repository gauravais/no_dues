"""Department officer endpoints: reviewing clearance queue and rendering approval decisions."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from backend.app.api.deps import SessionDep, require_roles
from backend.app.models.user import User, UserRole
from backend.app.models.clearance import (
    ClearanceRequest,
    DepartmentApproval,
    ApprovalStatus,
)
from backend.app.models.roster import StudentRoster
from backend.app.schemas.workflow import (
    DepartmentQueueResponse,
    DepartmentQueueItem,
    DecisionRequest,
    DepartmentApprovalItem,
)
from backend.app.schemas.common import ErrorResponse
from backend.app.services.exceptions import (
    WorkflowNotFoundError,
    WorkflowConflictError,
    WorkflowBadRequestError,
)
from backend.app.services.workflow import decide_approval

router = APIRouter(prefix="/department", tags=["Department Officer"])
require_officer = require_roles(UserRole.dept_officer)


@router.get(
    "/queue",
    response_model=DepartmentQueueResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_department_clearance_queue",
    summary="Get Department Clearance Queue",
    description=(
        "Retrieves a paginated list of student clearance requests pending review or previously decided "
        "by the officer's assigned department. Returns student identity and programme (never bank details)."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Officer has no department assigned"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-officer roles"},
    },
)
def get_department_queue(
    db: SessionDep,
    current_user: User = Depends(require_officer),
    approval_status: ApprovalStatus | None = Query(None, alias="status", description="Filter by approval status"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> DepartmentQueueResponse:
    if not current_user.department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Officer user is not associated with any department.",
        )

    # Base query for approvals belonging to this department
    base_query = (
        select(DepartmentApproval)
        .where(DepartmentApproval.department_id == current_user.department_id)
        .join(ClearanceRequest, ClearanceRequest.id == DepartmentApproval.request_id)
        .join(StudentRoster, StudentRoster.id == ClearanceRequest.roster_id)
    )

    if approval_status is not None:
        base_query = base_query.where(DepartmentApproval.status == approval_status)

    # Count total
    count_query = select(func.count()).select_from(base_query.subquery())
    total = db.execute(count_query).scalar() or 0

    # Fetch paginated items
    items_query = (
        base_query.options(
            joinedload(DepartmentApproval.request).joinedload(ClearanceRequest.roster_entry).joinedload(StudentRoster.programme)
        )
        .order_by(DepartmentApproval.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    approvals = db.execute(items_query).scalars().all()

    queue_items = []
    for a in approvals:
        r = a.request.roster_entry
        prog_name = r.programme.name if (r and r.programme) else "Unknown"
        queue_items.append(
            DepartmentQueueItem(
                approval_id=a.id,
                request_id=a.request_id,
                student_name=r.name if r else "Unknown",
                registration_number=r.registration_number if r else "Unknown",
                programme_name=prog_name,
                status=a.status,
                submitted_at=a.request.submitted_at,
                resubmission_count=a.resubmission_count,
            )
        )

    return DepartmentQueueResponse(
        items=queue_items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/approvals/{approval_id}/decision",
    response_model=DepartmentApprovalItem,
    status_code=status.HTTP_200_OK,
    operation_id="decide_department_approval",
    summary="Submit Department Decision",
    description=(
        "Department officer approves or rejects an applicable clearance request. "
        "Remarks are strictly mandatory when rejecting. Recomputes the parent request status."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Mandatory remarks missing for rejection"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-officer roles"},
        404: {"model": ErrorResponse, "description": "Approval record not found or does not belong to officer's department"},
        409: {"model": ErrorResponse, "description": "Approval record has already been decided"},
    },
)
def decide_approval_endpoint(
    approval_id: int,
    body: DecisionRequest,
    db: SessionDep,
    current_user: User = Depends(require_officer),
) -> DepartmentApprovalItem:
    try:
        approval = decide_approval(
            session=db,
            officer_user=current_user,
            approval_id=approval_id,
            decision=body.decision,
            remarks=body.remarks,
        )
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
    except WorkflowBadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
