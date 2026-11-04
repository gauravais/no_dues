"""Directory of university departments for authenticated users."""
from fastapi import APIRouter, Depends, status
from sqlalchemy import select

from backend.app.api.deps import SessionDep, get_current_user
from backend.app.models.user import User
from backend.app.models.university import Department, DepartmentApplicability, DepartmentKind
from backend.app.schemas.workflow import DepartmentResponse
from backend.app.schemas.department import AssignedOnlyDepartmentItem
from backend.app.schemas.common import ErrorResponse

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get(
    "",
    response_model=list[DepartmentResponse],
    status_code=status.HTTP_200_OK,
    operation_id="list_departments",
    summary="List University Departments",
    description="Returns all active university departments (academic and service). Accessible to all authenticated users.",
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
def list_departments(
    db: SessionDep,
    current_user: User = Depends(get_current_user),
) -> list[DepartmentResponse]:
    query = select(Department).order_by(Department.id.asc())
    deps = db.execute(query).scalars().all()
    return [
        DepartmentResponse(
            id=d.id,
            name=d.name,
            kind=d.kind.value,
            applicability=d.applicability.value,
            description=d.description,
        )
        for d in deps
    ]


@router.get(
    "/assigned-only",
    response_model=list[AssignedOnlyDepartmentItem],
    status_code=status.HTTP_200_OK,
    operation_id="list_assigned_only_departments",
    summary="List ASSIGNED_ONLY Service Departments",
    description="Returns all service departments that require specific assignment (labs, workshops, specialized centers) with description.",
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
def list_assigned_only_departments(
    db: SessionDep,
    current_user: User = Depends(get_current_user),
) -> list[AssignedOnlyDepartmentItem]:
    query = (
        select(Department)
        .where(
            Department.applicability == DepartmentApplicability.ASSIGNED_ONLY,
            Department.kind == DepartmentKind.service,
        )
        .order_by(Department.name.asc())
    )
    deps = db.execute(query).scalars().all()
    return [
        AssignedOnlyDepartmentItem(
            id=d.id,
            name=d.name,
            description=d.description,
        )
        for d in deps
    ]

