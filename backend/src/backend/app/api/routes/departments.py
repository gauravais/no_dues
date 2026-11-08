"""Directory of university departments and academic programmes for authenticated users."""
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from backend.app.api.deps import SessionDep, get_current_user
from backend.app.models.user import User
from backend.app.models.university import Department, DepartmentApplicability, DepartmentKind, Programme
from backend.app.schemas.workflow import DepartmentResponse
from backend.app.schemas.department import AssignedOnlyDepartmentItem
from backend.app.schemas.admin import ProgrammeResponse
from backend.app.schemas.common import ErrorResponse
from backend.app.services.workflow import active_officers_for

router = APIRouter(prefix="/departments", tags=["Departments"])
programmes_router = APIRouter(prefix="/programmes", tags=["Programmes"])


@router.get(
    "",
    response_model=list[DepartmentResponse],
    status_code=status.HTTP_200_OK,
    operation_id="list_departments",
    summary="List University Departments",
    description="Returns all university departments (academic and service) with category, label and active status.",
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
            category=d.category,
            label=d.category_label,
            is_active=d.is_active,
            has_active_officer=bool(active_officers_for(db, d.id)),
        )
        for d in deps
    ]


@router.get(
    "/assigned-only",
    response_model=list[AssignedOnlyDepartmentItem],
    status_code=status.HTTP_200_OK,
    operation_id="list_assigned_only_departments",
    summary="List Active Additional Facilities",
    description="Returns all active additional facility service departments with description.",
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
            Department.is_active == True,
        )
        .order_by(Department.name.asc())
    )
    deps = db.execute(query).scalars().all()
    return [
        AssignedOnlyDepartmentItem(
            id=d.id,
            name=d.name,
            description=d.description,
            category=d.category,
            label=d.category_label,
            is_active=d.is_active,
            has_active_officer=bool(active_officers_for(db, d.id)),
        )
        for d in deps
    ]


@router.get(
    "/additional-facilities",
    response_model=list[AssignedOnlyDepartmentItem],
    status_code=status.HTTP_200_OK,
    operation_id="list_additional_facilities",
    summary="List Active Additional Facilities (Alias)",
    description="Alias endpoint for list_assigned_only_departments.",
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
def list_additional_facilities(
    db: SessionDep,
    current_user: User = Depends(get_current_user),
) -> list[AssignedOnlyDepartmentItem]:
    return list_assigned_only_departments(db=db, current_user=current_user)


@programmes_router.get(
    "",
    response_model=list[ProgrammeResponse],
    status_code=status.HTTP_200_OK,
    operation_id="list_programmes",
    summary="List Academic Programmes",
    description="Returns all academic programmes including faculty and academic department names.",
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
def list_programmes(
    db: SessionDep,
    current_user: User = Depends(get_current_user),
) -> list[ProgrammeResponse]:
    query = (
        select(Programme)
        .options(joinedload(Programme.department).joinedload(Department.faculty))
        .order_by(Programme.name.asc())
    )
    progs = db.execute(query).scalars().all()
    return [
        ProgrammeResponse(
            id=p.id,
            name=p.name,
            academic_department_id=p.academic_department_id,
            academic_department_name=p.department.name if p.department else None,
            faculty_id=p.department.faculty_id if p.department else None,
            faculty_name=p.department.faculty.name if (p.department and p.department.faculty) else None,
            is_active=p.is_active,
        )
        for p in progs
    ]

