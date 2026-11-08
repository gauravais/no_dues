"""Department officer endpoints: reviewing clearance queue, rendering approval decisions,
and academic department roster & lab catalog delegation.
"""
import csv
import io
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select, func, or_
from sqlalchemy.orm import joinedload, selectinload

from backend.app.api.deps import SessionDep, require_roles, require_academic_officer
from backend.app.core.config import settings
from backend.app.core.security import normalize_email
from backend.app.models.user import User, UserRole
from backend.app.models.clearance import (
    ClearanceRequest,
    ClearanceStatus,
    DepartmentApproval,
    ApprovalStatus,
)
from backend.app.models.university import (
    Department,
    DepartmentKind,
    DepartmentApplicability,
    Programme,
)
from backend.app.models.lab_course import LabCourse
from backend.app.models.roster import StudentRoster
from backend.app.models.audit import AuditLog
from backend.app.schemas.workflow import (
    DepartmentQueueResponse,
    DepartmentQueueItem,
    OfficePendingCount,
    DecisionRequest,
    DepartmentApprovalItem,
    AddOfficeRequest,
    AcademicRequestDetailResponse,
    DepartmentResponse,
    StaffCancelRequest,
    CancelResponse,
)
from backend.app.schemas.admin import (
    RosterUploadResponse,
    RosterUploadRowReport,
)
from backend.app.schemas.department import (
    DepartmentRosterCreate,
    DepartmentRosterPatch,
    DepartmentRosterItem,
    DepartmentRosterListResponse,
    LabCourseCreate,
    LabCoursePatch,
    LabCourseItem,
    LabCourseListResponse,
    LabCourseUploadRowReport,
    LabCourseUploadResponse,
    CreateLabWorkshopRequest,
    UpdateLabWorkshopRequest,
    LabWorkshopOfficeItem,
)
from backend.app.schemas.common import ErrorResponse
from backend.app.services.exceptions import (
    WorkflowNotFoundError,
    WorkflowConflictError,
    WorkflowBadRequestError,
    WorkflowForbiddenError,
)
from backend.app.services.workflow import (
    decide_approval,
    add_office_to_request,
    staff_cancel_request,
    user_department_ids,
    user_academic_department_ids,
    active_officers_for,
    get_user_departments,
)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

router = APIRouter(prefix="/department", tags=["Department Officer"])
require_officer = require_roles(UserRole.dept_officer)


def _format_roster_item(r: StudentRoster) -> DepartmentRosterItem:
    return DepartmentRosterItem(
        id=r.id,
        registration_number=r.registration_number,
        name=r.name,
        email=r.email,
        mobile=r.mobile,
        address=r.address,
        programme_id=r.programme_id,
        programme_name=r.programme.name if r.programme else f"Programme #{r.programme_id}",
        is_hosteller=r.is_hosteller,
        security_deposit_amount=r.security_deposit_amount,
        has_user_account=bool(r.user),
        assigned_department_ids=[d.department_id for d in r.assigned_departments] if r.assigned_departments else [],
    )


def _format_lab_item(c: LabCourse) -> LabCourseItem:
    return LabCourseItem(
        id=c.id,
        code=c.code,
        name=c.name,
        academic_department_id=c.academic_department_id,
        academic_department_name=c.academic_department.name if c.academic_department else None,
        lab_department_id=c.lab_department_id,
        lab_department_name=c.lab_department.name if c.lab_department else None,
        specialization=c.specialization,
        is_active=c.is_active,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


# ---------------------------------------------------------------------------
# OFFICER QUEUE & DECISIONS (All department officers)
# ---------------------------------------------------------------------------


@router.get(
    "/queue",
    response_model=DepartmentQueueResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_department_clearance_queue",
    summary="Get Department Clearance Queue",
    description=(
        "Retrieves a paginated list of student clearance requests pending review or previously decided "
        "by the officer's assigned departments. Returns student identity and programme (never bank details)."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Officer has no department assigned"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-officer roles"},
        404: {"model": ErrorResponse, "description": "Department not found among officer's assigned departments"},
    },
)
def get_department_queue(
    db: SessionDep,
    current_user: User = Depends(require_officer),
    department_id: int | None = Query(None, description="Filter queue to a specific assigned office"),
    approval_status: ApprovalStatus | None = Query(None, alias="status", description="Filter by approval status"),
    search: str | None = Query(None, description="Search by student name or registration number"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> DepartmentQueueResponse:
    officer_dept_ids = user_department_ids(current_user, db)
    if not officer_dept_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Officer user is not associated with any department.",
        )

    if department_id is not None:
        if department_id not in officer_dept_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found among officer's assigned departments.",
            )
        target_dept_ids = [department_id]
    else:
        target_dept_ids = list(officer_dept_ids)

    base_query = (
        select(DepartmentApproval)
        .where(
            DepartmentApproval.department_id.in_(target_dept_ids),
            ClearanceRequest.status != ClearanceStatus.CANCELLED,
        )
        .join(ClearanceRequest, ClearanceRequest.id == DepartmentApproval.request_id)
        .join(StudentRoster, StudentRoster.id == ClearanceRequest.roster_id)
    )

    if approval_status is not None:
        base_query = base_query.where(DepartmentApproval.status == approval_status)

    if search and search.strip():
        search_term = f"%{search.strip()}%"
        base_query = base_query.where(
            or_(
                StudentRoster.name.ilike(search_term),
                StudentRoster.registration_number.ilike(search_term),
            )
        )

    count_query = select(func.count()).select_from(base_query.subquery())
    total = db.execute(count_query).scalar() or 0

    items_query = (
        base_query.options(
            joinedload(DepartmentApproval.department),
            joinedload(DepartmentApproval.request).joinedload(ClearanceRequest.roster_entry).joinedload(StudentRoster.programme),
            joinedload(DepartmentApproval.request).selectinload(ClearanceRequest.declared_lab_courses),
        )
        .order_by(DepartmentApproval.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    approvals = db.execute(items_query).scalars().all()

    # Pre-fetch officer departments for office counts and metadata
    all_officer_depts = db.execute(
        select(Department).where(Department.id.in_(officer_dept_ids)).order_by(Department.name.asc())
    ).scalars().all()
    dept_map = {d.id: d for d in all_officer_depts}

    # Compute office_counts across ALL of the officer's departments
    pending_counts_query = (
        select(
            DepartmentApproval.department_id,
            func.count(DepartmentApproval.id).label("pending_count"),
        )
        .join(ClearanceRequest, ClearanceRequest.id == DepartmentApproval.request_id)
        .where(
            DepartmentApproval.department_id.in_(officer_dept_ids),
            DepartmentApproval.status == ApprovalStatus.PENDING,
            ClearanceRequest.status != ClearanceStatus.CANCELLED,
        )
        .group_by(DepartmentApproval.department_id)
    )
    pending_counts = dict(db.execute(pending_counts_query).all())

    office_counts = [
        OfficePendingCount(
            department_id=d.id,
            department_name=d.name,
            pending=pending_counts.get(d.id, 0),
        )
        for d in all_officer_depts
    ]

    queue_items = []
    for a in approvals:
        req = a.request
        r = req.roster_entry if req else None
        prog_name = r.programme.name if (r and r.programme) else "Unknown"
        d_obj = dept_map.get(a.department_id) or a.department
        d_name = d_obj.name if d_obj else f"Department #{a.department_id}"

        declared_subs = [
            f"{c.code}: {c.name}" if c.code else c.name
            for c in (req.declared_lab_courses or [])
            if c.lab_department_id == a.department_id
        ] if req else []

        # declared_is_hosteller: a bool, only for the officer's office if it is the hostel office, otherwise null
        is_hostel = (d_obj.applicability == DepartmentApplicability.HOSTELLER_ONLY) if d_obj else False
        declared_hostel = bool(req.declared_is_hosteller) if (is_hostel and req) else None

        # others_note: shown only to additional-facility offices
        is_additional_facility = (d_obj.applicability == DepartmentApplicability.ASSIGNED_ONLY) if d_obj else False
        note = req.others_note if (req and is_additional_facility) else None

        queue_items.append(
            DepartmentQueueItem(
                approval_id=a.id,
                request_id=a.request_id,
                department_id=a.department_id,
                department_name=d_name,
                student_name=r.name if r else "Unknown",
                registration_number=r.registration_number if r else "Unknown",
                programme_name=prog_name,
                status=a.status,
                submitted_at=req.submitted_at if req else a.created_at,
                resubmission_count=a.resubmission_count,
                declared_subjects=declared_subs,
                declared_is_hosteller=declared_hostel,
                others_note=note,
            )
        )

    return DepartmentQueueResponse(
        items=queue_items,
        total=total,
        limit=limit,
        offset=offset,
        office_counts=office_counts,
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
            previous_remarks=approval.previous_remarks,
            decided_at=approval.decided_at,
            decided_by_name=current_user.full_name or current_user.email,
            resubmission_count=approval.resubmission_count,
            added_by_user_id=approval.added_by_user_id,
            added_by_name=approval.added_by_user.full_name or approval.added_by_user.email if approval.added_by_user else None,
            added_reason=approval.added_reason,
        )
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except WorkflowConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
    except WorkflowBadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/requests/{request_id}/add-department",
    response_model=DepartmentApprovalItem,
    status_code=status.HTTP_200_OK,
    operation_id="academic_officer_add_department",
    summary="Academic Officer Adds Office to Active Clearance Request",
    description=(
        "Academic department officer adds an office to an active clearance request for a student "
        "enrolled under their department. Justification reason is strictly mandatory."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Mandatory reason missing"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-academic officers"},
        404: {"model": ErrorResponse, "description": "Request not found or not in officer's department"},
        409: {"model": ErrorResponse, "description": "Target office already exists, has no active officer, or request finalized"},
    },
)
def add_department_by_academic_officer(
    request_id: int,
    body: AddOfficeRequest,
    db: SessionDep,
    current_user: User = Depends(require_academic_officer),
) -> DepartmentApprovalItem:
    try:
        approval = add_office_to_request(
            session=db,
            request_id=request_id,
            department_id=body.department_id,
            acting_user=current_user,
            reason=body.reason,
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
            added_by_user_id=approval.added_by_user_id,
            added_by_name=current_user.full_name or current_user.email,
            added_reason=approval.added_reason,
        )
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except WorkflowConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
    except WorkflowBadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/requests/{request_id}",
    response_model=AcademicRequestDetailResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_department_request_detail",
    summary="Department Officer Clearance Request Dossier",
    description=(
        "Returns clearance request dossier. Academic officers of the student's department receive the full dossier "
        "(all departmental approvals and candidate offices to add). Service/non-academic officers whose office is on "
        "the request receive a scoped dossier containing student details, academic department, declared subjects for their "
        "own office, hostel status if they are the hostel office, others note if applicable, and their own approval record. "
        "Officers whose office is not on the request receive 404."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Officer has no department assigned"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-officers"},
        404: {"model": ErrorResponse, "description": "Request not found or office not on request"},
    },
)
def get_department_request_detail(
    request_id: int,
    db: SessionDep,
    current_user: User = Depends(require_officer),
) -> AcademicRequestDetailResponse:
    officer_dept_ids = user_department_ids(current_user, db)
    if not officer_dept_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Officer user is not associated with any department.",
        )

    req = db.execute(
        select(ClearanceRequest)
        .where(ClearanceRequest.id == request_id)
        .options(
            joinedload(ClearanceRequest.roster_entry).joinedload(StudentRoster.programme),
            joinedload(ClearanceRequest.approvals).joinedload(DepartmentApproval.department),
            joinedload(ClearanceRequest.approvals).joinedload(DepartmentApproval.decided_by_user),
            joinedload(ClearanceRequest.approvals).joinedload(DepartmentApproval.added_by_user),
            selectinload(ClearanceRequest.declared_lab_courses),
            joinedload(ClearanceRequest.certificate),
        )
    ).unique().scalar_one_or_none()

    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clearance request not found.",
        )

    r = req.roster_entry
    prog = r.programme if r else None
    student_acad_dept_id = prog.academic_department_id if prog else None
    prog_name = prog.name if prog else "Unknown"

    acad_dept = db.get(Department, student_acad_dept_id) if student_acad_dept_id else None
    acad_dept_name = acad_dept.name if acad_dept else "Unknown Academic Department"

    officer_acad_dept_ids = user_academic_department_ids(current_user, db)

    # 1. Full dossier for academic officer if one of their departments is the student's own academic department
    if student_acad_dept_id and student_acad_dept_id in officer_acad_dept_ids:
        existing_dept_ids = {a.department_id for a in (req.approvals or [])}
        can_depts = db.execute(
            select(Department)
            .where(
                Department.applicability.in_([DepartmentApplicability.LAB_WORKSHOP, DepartmentApplicability.ASSIGNED_ONLY]),
                Department.is_active == True,
            )
            .order_by(Department.name.asc())
        ).scalars().all()
        can_add = [
            DepartmentResponse(
                id=d.id,
                name=d.name,
                kind=d.kind.value,
                applicability=d.applicability.value,
                description=d.description,
                category=d.category,
                label=d.category_label,
                is_active=d.is_active,
            )
            for d in can_depts
            if d.id not in existing_dept_ids
        ]

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
                resubmission_count=a.resubmission_count,
                added_by_user_id=a.added_by_user_id,
                added_by_name=a.added_by_user.full_name or a.added_by_user.email if a.added_by_user else None,
                added_reason=a.added_reason,
            )
            for a in (req.approvals or [])
        ]

        declared_subs = [
            f"{c.code}: {c.name}" if c.code else c.name
            for c in (req.declared_lab_courses or [])
        ]

        cert_code = None
        if req.status in (ClearanceStatus.CLEARED, ClearanceStatus.REFUND_VERIFIED) and req.certificate:
            cert_code = req.certificate.certificate_code

        return AcademicRequestDetailResponse(
            request_id=req.id,
            status=req.status,
            student_name=r.name if r else "Unknown",
            registration_number=r.registration_number if r else "Unknown",
            programme_name=prog_name,
            academic_department=acad_dept_name,
            is_hosteller=bool(req.declared_is_hosteller),
            declared_is_hosteller=bool(req.declared_is_hosteller),
            declared_subjects=declared_subs,
            others_note=req.others_note,
            submitted_at=req.submitted_at,
            hod_remarks=req.hod_remarks,
            certificate_code=cert_code,
            approvals=approval_items,
            can_add_departments=can_add,
        )

    # 2. Scoped / Limited dossier for any officer whose office is on the request
    own_approvals = [
        a for a in (req.approvals or []) if a.department_id in officer_dept_ids
    ]
    if not own_approvals:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clearance request not found for your department.",
        )

    officer_depts = db.execute(
        select(Department).where(Department.id.in_(officer_dept_ids))
    ).scalars().all()

    is_hostel_office = any(
        d.applicability == DepartmentApplicability.HOSTELLER_ONLY
        for d in officer_depts
    )
    hostel_decl = bool(req.declared_is_hosteller) if is_hostel_office else None

    # declared subjects of any of their offices
    own_subjects = [
        f"{c.code}: {c.name}" if c.code else c.name
        for c in (req.declared_lab_courses or [])
        if c.lab_department_id in officer_dept_ids
    ]

    # others_note if applicable (only shown to additional facility offices)
    has_additional_facility = any(
        d.applicability == DepartmentApplicability.ASSIGNED_ONLY
        for d in officer_depts
    )
    note = req.others_note if has_additional_facility else None

    own_approval_items = [
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
            resubmission_count=a.resubmission_count,
            added_by_user_id=a.added_by_user_id,
            added_by_name=a.added_by_user.full_name or a.added_by_user.email if a.added_by_user else None,
            added_reason=a.added_reason,
        )
        for a in own_approvals
    ]

    return AcademicRequestDetailResponse(
        request_id=req.id,
        status=req.status,
        student_name=r.name if r else "Unknown",
        registration_number=r.registration_number if r else "Unknown",
        programme_name=prog_name,
        academic_department=acad_dept_name,
        is_hosteller=hostel_decl,
        declared_is_hosteller=hostel_decl,
        declared_subjects=own_subjects,
        others_note=note,
        submitted_at=req.submitted_at,
        hod_remarks=None,
        certificate_code=None,
        approvals=own_approval_items,
        can_add_departments=[],
    )



@router.post(
    "/requests/{id}/cancel",
    response_model=CancelResponse,
    status_code=status.HTTP_200_OK,
    operation_id="department_cancel_clearance_request",
    summary="Academic Officer Cancel Clearance Request",
    description="Allows academic department officers to cancel clearance requests of their own students with mandatory reason.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid state (already cleared/verified) or missing reason"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-academic officers or requests outside officer's department"},
        404: {"model": ErrorResponse, "description": "Clearance request not found"},
    },
)
def department_cancel_request(
    id: int,
    body: StaffCancelRequest,
    db: SessionDep,
    current_user: User = Depends(require_officer),
) -> CancelResponse:
    try:
        req = staff_cancel_request(db, id, current_user, body.reason)
        return CancelResponse(
            detail="Clearance request successfully cancelled.",
            request_id=req.id,
            status=req.status,
        )
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except WorkflowBadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except WorkflowForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)


# ---------------------------------------------------------------------------
# ACADEMIC DEPARTMENT ROSTER DELEGATION (Academic officers only)
# ---------------------------------------------------------------------------


@router.get(
    "/roster/template.csv",
    status_code=status.HTTP_200_OK,
    operation_id="get_department_roster_template_csv",
    summary="Download Academic Roster CSV Template",
    description="Downloads a CSV template formatted for academic department student roster upload.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for service department officers"},
    },
)
def get_department_roster_template(
    current_user: User = Depends(require_academic_officer),
) -> Response:
    csv_content = (
        "registration_number,name,email,mobile,address,programme,is_hosteller,security_deposit_amount\r\n"
        "2026CS901,Sample Student,sample.student@example.edu,9876543210,Campus Hostels,B.Tech Computer Engineering,false,5000.00\r\n"
    )
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="department_roster_template.csv"'},
    )


@router.post(
    "/roster/upload",
    response_model=RosterUploadResponse,
    status_code=status.HTTP_200_OK,
    operation_id="upload_department_roster_csv",
    summary="Upload Academic Department Roster CSV",
    description=(
        "Academic department officer uploads student roster for their own programmes. "
        "Rows for programmes outside their department or foreign department students are strictly rejected. "
        "Returns a row-by-row status report."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid CSV file structure or missing headers"},
        403: {"model": ErrorResponse, "description": "Forbidden for service department officers"},
    },
)
async def upload_department_roster_csv(
    db: SessionDep,
    file: UploadFile = File(..., description="CSV file with student roster records"),
    current_user: User = Depends(require_academic_officer),
) -> RosterUploadResponse:
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to decode CSV file as text")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded CSV file is empty or missing header row")

    fieldnames_map = {f.strip().lower(): f for f in reader.fieldnames if f}
    required_cols = ["registration_number", "name", "email", "mobile", "programme"]
    for col in required_cols:
        if col not in fieldnames_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required CSV column '{col}'. Required: {', '.join(required_cols)}",
            )

    # Programmes belonging to officer's academic departments
    officer_acad_dept_ids = user_academic_department_ids(current_user, db)
    dept_progs = db.execute(
        select(Programme).where(
            Programme.academic_department_id.in_(officer_acad_dept_ids),
            Programme.is_active == True,
        )
    ).scalars().all()
    prog_by_name = {p.name.strip().lower(): p for p in dept_progs}
    prog_by_id = {p.id: p for p in dept_progs}


    row_reports: list[RosterUploadRowReport] = []
    created_count = 0
    updated_count = 0
    rejected_count = 0

    for idx, row in enumerate(reader, start=1):
        reg_num = (row.get(fieldnames_map["registration_number"]) or "").strip()
        name = (row.get(fieldnames_map["name"]) or "").strip()
        raw_email = row.get(fieldnames_map["email"])
        email = normalize_email(raw_email) if raw_email else ""
        mobile = (row.get(fieldnames_map["mobile"]) or "").strip()
        address = (row.get(fieldnames_map.get("address", "")) or "").strip()
        prog_str = (row.get(fieldnames_map["programme"]) or "").strip()
        hosteller_str = (row.get(fieldnames_map.get("is_hosteller", "")) or "").strip().lower()
        deposit_str = (row.get(fieldnames_map.get("security_deposit_amount", "")) or "").strip()

        if not reg_num:
            row_reports.append(RosterUploadRowReport(row_number=idx, registration_number="UNKNOWN", status="rejected", reason="Registration number cannot be empty"))
            rejected_count += 1
            continue

        if not name or not mobile:
            row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="rejected", reason="Student name and mobile are mandatory"))
            rejected_count += 1
            continue

        if not EMAIL_REGEX.match(email):
            row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="rejected", reason=f"Invalid email format: '{email}'"))
            rejected_count += 1
            continue

        domain = email.split("@")[-1] if "@" in email else ""
        if domain not in settings.allowed_email_domain_list:
            row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="rejected", reason=f"Email domain '@{domain}' is not allowed"))
            rejected_count += 1
            continue

        # Match programme (name or id) strictly within officer's academic department
        matched_prog = prog_by_name.get(prog_str.lower())
        if not matched_prog and prog_str.isdigit():
            matched_prog = prog_by_id.get(int(prog_str))

        if not matched_prog:
            row_reports.append(
                RosterUploadRowReport(
                    row_number=idx,
                    registration_number=reg_num,
                    status="rejected",
                    reason=f"Programme '{prog_str}' does not belong to your academic department",
                )
            )
            rejected_count += 1
            continue

        is_hosteller = hosteller_str in ("true", "1", "yes", "y", "t")
        try:
            deposit_amt = Decimal(deposit_str) if deposit_str else Decimal("0.00")
            if deposit_amt < 0:
                raise ValueError()
        except (InvalidOperation, ValueError):
            row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="rejected", reason="Invalid deposit amount"))
            rejected_count += 1
            continue

        # Check existing student
        existing = db.execute(
            select(StudentRoster)
            .where(StudentRoster.registration_number == reg_num)
            .options(joinedload(StudentRoster.programme))
        ).scalars().first()

        if existing:
            # Foreign department student check
            if existing.programme and existing.programme.academic_department_id not in officer_acad_dept_ids:
                row_reports.append(
                    RosterUploadRowReport(
                        row_number=idx,
                        registration_number=reg_num,
                        status="rejected",
                        reason="Student belongs to another department's programme and cannot be modified",
                    )
                )

                rejected_count += 1
                continue

            # If email is changing
            if existing.email != email:
                # User account exists?
                student_user = db.execute(select(User).where(User.roster_id == existing.id)).scalars().first()
                if student_user:
                    row_reports.append(
                        RosterUploadRowReport(
                            row_number=idx,
                            registration_number=reg_num,
                            status="rejected",
                            reason="Cannot change email because student already has an active user account",
                        )
                    )
                    rejected_count += 1
                    continue

                # Email clash with another roster row
                clash = db.execute(
                    select(StudentRoster).where(func.lower(StudentRoster.email) == email, StudentRoster.id != existing.id)
                ).scalars().first()
                if clash:
                    row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="rejected", reason=f"Email '{email}' is already assigned to {clash.registration_number}"))
                    rejected_count += 1
                    continue

                existing.email = email

            existing.name = name
            existing.mobile = mobile
            if address:
                existing.address = address
            existing.programme_id = matched_prog.id
            if hosteller_str:
                existing.is_hosteller = is_hosteller
            if deposit_str:
                existing.security_deposit_amount = deposit_amt
            existing.updated_by_user_id = current_user.id

            # Sync user full_name if exists
            s_user = db.execute(select(User).where(User.roster_id == existing.id)).scalars().first()
            if s_user:
                s_user.full_name = name

            row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="updated"))
            updated_count += 1
        else:
            # Check email uniqueness
            clash = db.execute(select(StudentRoster).where(func.lower(StudentRoster.email) == email)).scalars().first()
            if clash:
                row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="rejected", reason=f"Email '{email}' is already registered"))
                rejected_count += 1
                continue

            user_clash = db.execute(select(User).where(func.lower(User.email) == email)).scalars().first()
            if user_clash:
                row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="rejected", reason=f"Email '{email}' is already registered to a user account"))
                rejected_count += 1
                continue

            new_student = StudentRoster(
                registration_number=reg_num,
                name=name,
                email=email,
                mobile=mobile,
                address=address or "Not provided",
                programme_id=matched_prog.id,
                is_hosteller=is_hosteller,
                security_deposit_amount=deposit_amt,
                source="department_upload",
                created_by_user_id=current_user.id,
                updated_by_user_id=current_user.id,
            )
            db.add(new_student)
            row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="created"))
            created_count += 1

    # Record audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="ACADEMIC_ROSTER_UPLOADED",
        entity_type="StudentRoster",
        entity_id=None,
        details={
            "department_id": current_user.department_id,
            "total_rows": len(row_reports),
            "created": created_count,
            "updated": updated_count,
            "rejected": rejected_count,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    db.commit()

    return RosterUploadResponse(
        total_rows=len(row_reports),
        created_count=created_count,
        updated_count=updated_count,
        rejected_count=rejected_count,
        rows=row_reports,
    )


@router.post(
    "/roster",
    response_model=DepartmentRosterItem,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_department_roster_student",
    summary="Add Student to Academic Roster",
    description="Adds a single student to the roster for an academic programme in the officer's department.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid programme or email domain"},
        403: {"model": ErrorResponse, "description": "Forbidden for service department officers"},
        409: {"model": ErrorResponse, "description": "Registration number or email already exists"},
    },
)
def create_department_roster_student(
    body: DepartmentRosterCreate,
    db: SessionDep,
    current_user: User = Depends(require_academic_officer),
) -> DepartmentRosterItem:
    # Check programme belongs to one of officer's academic departments
    prog = db.get(Programme, body.programme_id)
    if not prog or prog.academic_department_id not in user_academic_department_ids(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Programme does not belong to your academic department.",
        )

    # Normalize email & check domain
    email_clean = normalize_email(str(body.email))
    domain = email_clean.split("@")[-1] if "@" in email_clean else ""
    if domain not in settings.allowed_email_domain_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email domain '@{domain}' is not allowed.",
        )

    # Check registration number uniqueness
    reg_clean = body.registration_number.strip().upper()
    exists_reg = db.execute(
        select(StudentRoster).where(StudentRoster.registration_number == reg_clean)
    ).scalars().first()
    if exists_reg:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Registration number already exists.")

    # Check email uniqueness
    clash_roster = db.execute(select(StudentRoster).where(func.lower(StudentRoster.email) == email_clean)).scalars().first()
    if clash_roster:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Email '{email_clean}' is already registered.")

    clash_user = db.execute(select(User).where(func.lower(User.email) == email_clean)).scalars().first()
    if clash_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Email '{email_clean}' is already registered to a user.")

    student = StudentRoster(
        registration_number=reg_clean,
        name=body.name.strip(),
        email=email_clean,
        mobile=body.mobile.strip(),
        address=body.address.strip() if body.address else "Not provided",
        programme_id=prog.id,
        is_hosteller=body.is_hosteller,
        security_deposit_amount=body.security_deposit_amount,
        source="department_add",
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(student)
    db.flush()

    audit = AuditLog(
        user_id=current_user.id,
        action="ACADEMIC_ROSTER_STUDENT_CREATED",
        entity_type="StudentRoster",
        entity_id=student.id,
        details={"registration_number": student.registration_number, "email": student.email},
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    db.commit()
    db.refresh(student)

    return _format_roster_item(student)


@router.get(
    "/roster",
    response_model=DepartmentRosterListResponse,
    status_code=status.HTTP_200_OK,
    operation_id="list_department_roster",
    summary="List Academic Department Roster",
    description="Returns paginated student roster records belonging strictly to the officer's academic department.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for service department officers"},
        404: {"model": ErrorResponse, "description": "Department not found among your academic departments"},
    },
)
def list_department_roster(
    db: SessionDep,
    current_user: User = Depends(require_academic_officer),
    department_id: int | None = Query(None, description="Filter to a specific academic department"),
    search: str | None = Query(None, description="Search by name, registration number, or email"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> DepartmentRosterListResponse:
    acad_dept_ids = user_academic_department_ids(current_user, db)
    if department_id is not None:
        if department_id not in acad_dept_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found among your academic departments.",
            )
        target_acad_ids = [department_id]
    else:
        target_acad_ids = list(acad_dept_ids)

    base_query = (
        select(StudentRoster)
        .join(Programme, Programme.id == StudentRoster.programme_id)
        .where(Programme.academic_department_id.in_(target_acad_ids))
    )

    if search and search.strip():
        term = f"%{search.strip()}%"
        base_query = base_query.where(
            or_(
                StudentRoster.name.ilike(term),
                StudentRoster.registration_number.ilike(term),
                StudentRoster.email.ilike(term),
            )
        )

    count_query = select(func.count()).select_from(base_query.subquery())
    total = db.execute(count_query).scalar() or 0

    items_query = (
        base_query.options(
            joinedload(StudentRoster.programme),
            joinedload(StudentRoster.user),
            joinedload(StudentRoster.assigned_departments),
        )
        .order_by(StudentRoster.registration_number.asc())
        .offset(offset)
        .limit(limit)
    )
    students = db.execute(items_query).unique().scalars().all()

    return DepartmentRosterListResponse(
        total=total,
        items=[_format_roster_item(s) for s in students],
    )


@router.patch(
    "/roster/{id}",
    response_model=DepartmentRosterItem,
    status_code=status.HTTP_200_OK,
    operation_id="patch_department_roster_student",
    summary="Update Academic Department Roster Record",
    description=(
        "Updates name, mobile, address, or email for a student in the officer's academic department. "
        "Returns 404 if student belongs to another department. "
        "If student already has an active user account, changing email is strictly refused with 409 Conflict."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input format"},
        403: {"model": ErrorResponse, "description": "Forbidden for service department officers"},
        404: {"model": ErrorResponse, "description": "Student not found in your academic department"},
        409: {"model": ErrorResponse, "description": "Email conflict or student already has active user account"},
    },
)
def patch_department_roster_student(
    id: int,
    body: DepartmentRosterPatch,
    db: SessionDep,
    current_user: User = Depends(require_academic_officer),
) -> DepartmentRosterItem:
    student = db.execute(
        select(StudentRoster)
        .where(StudentRoster.id == id)
        .options(joinedload(StudentRoster.programme), joinedload(StudentRoster.user))
    ).scalars().first()

    if not student or not student.programme or student.programme.academic_department_id not in user_academic_department_ids(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student roster record not found in your academic department.",
        )


    if body.email is not None:
        new_email = normalize_email(str(body.email))
        if new_email != student.email:
            # If student has a User account, refuse with 409
            user_acc = db.execute(select(User).where(User.roster_id == student.id)).scalars().first()
            if user_acc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot change email because student already has an active user account.",
                )

            # Check email uniqueness
            clash = db.execute(
                select(StudentRoster).where(func.lower(StudentRoster.email) == new_email, StudentRoster.id != student.id)
            ).scalars().first()
            if clash:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Email '{new_email}' is already taken.")

            clash_u = db.execute(select(User).where(func.lower(User.email) == new_email)).scalars().first()
            if clash_u:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Email '{new_email}' is already taken by a user.")

            student.email = new_email

    if body.name is not None:
        student.name = body.name.strip()
        user_acc = db.execute(select(User).where(User.roster_id == student.id)).scalars().first()
        if user_acc:
            user_acc.full_name = student.name

    if body.mobile is not None:
        student.mobile = body.mobile.strip()

    if body.address is not None:
        student.address = body.address.strip()

    if body.programme_id is not None:
        # Check student has no open clearance request
        open_req = db.execute(
            select(ClearanceRequest).where(
                ClearanceRequest.roster_id == student.id,
                ClearanceRequest.status.not_in([
                    ClearanceStatus.CLEARED,
                    ClearanceStatus.REFUND_VERIFIED,
                    ClearanceStatus.CANCELLED,
                ]),
            )
        ).scalars().first()
        if open_req:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot change programme while student has an open clearance request.",
            )

        officer_acad_dept_ids = user_academic_department_ids(current_user, db)
        target_prog = db.get(Programme, body.programme_id)
        if (
            not target_prog
            or not target_prog.is_active
            or target_prog.academic_department_id not in officer_acad_dept_ids
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Target programme must be active and belong to one of your academic departments.",
            )
        student.programme_id = target_prog.id

    student.updated_by_user_id = current_user.id

    audit = AuditLog(
        user_id=current_user.id,
        action="ACADEMIC_ROSTER_STUDENT_UPDATED",
        entity_type="StudentRoster",
        entity_id=student.id,
        details={"name": student.name, "email": student.email},
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    db.commit()
    db.refresh(student)

    return _format_roster_item(student)


# ---------------------------------------------------------------------------
# ACADEMIC DEPARTMENT LAB CATALOG (Academic officers only)
# ---------------------------------------------------------------------------


@router.get(
    "/lab-courses/template.csv",
    status_code=status.HTTP_200_OK,
    operation_id="get_department_lab_courses_template_csv",
    summary="Download Lab Courses CSV Template",
    description="Downloads a CSV template formatted for lab course catalog upload.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for service department officers"},
    },
)
def get_department_lab_courses_template(
    current_user: User = Depends(require_academic_officer),
) -> Response:
    csv_content = (
        "code,name,lab_office,specialization\r\n"
        "CSE-L101,Advanced Programming Lab,Computing Laboratory,Computer Engineering\r\n"
    )
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="lab_courses_template.csv"'},
    )


@router.get(
    "/lab-courses",
    response_model=LabCourseListResponse,
    status_code=status.HTTP_200_OK,
    operation_id="list_department_lab_courses",
    summary="List Academic Department Lab Courses",
    description="Returns all lab and workshop courses managed by the officer's academic department.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for service department officers"},
        404: {"model": ErrorResponse, "description": "Department not found among your academic departments"},
    },
)
def list_department_lab_courses(
    db: SessionDep,
    current_user: User = Depends(require_academic_officer),
    department_id: int | None = Query(None, description="Filter to a specific academic department"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> LabCourseListResponse:
    acad_dept_ids = user_academic_department_ids(current_user, db)
    if department_id is not None:
        if department_id not in acad_dept_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found among your academic departments.",
            )
        target_acad_ids = [department_id]
    else:
        target_acad_ids = list(acad_dept_ids)

    query = (
        select(LabCourse)
        .where(LabCourse.academic_department_id.in_(target_acad_ids))
        .options(joinedload(LabCourse.academic_department), joinedload(LabCourse.lab_department))
    )
    if is_active is not None:
        query = query.where(LabCourse.is_active == is_active)

    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    courses = db.execute(
        query.order_by(LabCourse.code.asc()).offset(offset).limit(limit)
    ).unique().scalars().all()

    return LabCourseListResponse(
        total=total,
        items=[_format_lab_item(c) for c in courses],
    )


@router.post(
    "/lab-courses",
    response_model=LabCourseItem,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_department_lab_course",
    summary="Create Lab Course",
    description="Creates a new lab course mapped to an ASSIGNED_ONLY service department (lab/workshop office).",
    responses={
        400: {"model": ErrorResponse, "description": "Assigned office is not an ASSIGNED_ONLY service department"},
        403: {"model": ErrorResponse, "description": "Forbidden for service department officers"},
        409: {"model": ErrorResponse, "description": "Lab course code already exists"},
    },
)
def create_department_lab_course(
    body: LabCourseCreate,
    db: SessionDep,
    current_user: User = Depends(require_academic_officer),
) -> LabCourseItem:
    code_clean = body.code.strip().upper()
    exists = db.execute(
        select(LabCourse).where(func.upper(LabCourse.code) == code_clean)
    ).scalars().first()
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lab course code '{code_clean}' already exists.",
        )

    lab_dept = db.get(Department, body.lab_department_id)
    if not lab_dept or not lab_dept.is_active or lab_dept.applicability != DepartmentApplicability.LAB_WORKSHOP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assigned lab office must be an active service department with LAB_WORKSHOP applicability.",
        )

    acad_dept_ids = user_academic_department_ids(current_user, db)
    if body.academic_department_id and body.academic_department_id in acad_dept_ids:
        target_acad_id = body.academic_department_id
    elif acad_dept_ids:
        target_acad_id = sorted(list(acad_dept_ids))[0]
    else:
        target_acad_id = current_user.department_id

    course = LabCourse(
        code=code_clean,
        name=body.name.strip(),
        academic_department_id=target_acad_id,
        lab_department_id=lab_dept.id,
        specialization=body.specialization.strip() if body.specialization else None,
        is_active=True,
    )
    db.add(course)
    db.flush()

    audit = AuditLog(
        user_id=current_user.id,
        action="LAB_COURSE_CREATED",
        entity_type="LabCourse",
        entity_id=course.id,
        details={"code": course.code, "name": course.name, "lab_dept": lab_dept.name},
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    db.commit()
    db.refresh(course)

    return _format_lab_item(course)


@router.post(
    "/lab-courses/upload",
    response_model=LabCourseUploadResponse,
    status_code=status.HTTP_200_OK,
    operation_id="upload_department_lab_courses_csv",
    summary="Upload Lab Courses CSV",
    description="Bulk uploads lab courses for the officer's academic department from CSV.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid CSV file structure"},
        403: {"model": ErrorResponse, "description": "Forbidden for service department officers"},
    },
)
async def upload_department_lab_courses_csv(
    db: SessionDep,
    file: UploadFile = File(..., description="CSV file with lab courses"),
    dry_run: bool = Query(False, description="Simulate upload without persisting changes"),
    create_missing_offices: bool = Query(False, description="Create missing Lab/Workshop offices automatically"),
    current_user: User = Depends(require_academic_officer),
) -> LabCourseUploadResponse:
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to decode CSV file as text")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded CSV file is empty or missing headers")

    fieldnames_map = {f.strip().lower(): f for f in reader.fieldnames if f}
    required_cols = ["code", "name", "lab_office"]
    for col in required_cols:
        if col not in fieldnames_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required CSV column '{col}'. Required: {', '.join(required_cols)}",
            )

    officer_acad_dept_ids = user_academic_department_ids(current_user, db)
    default_acad_id = sorted(list(officer_acad_dept_ids))[0] if officer_acad_dept_ids else current_user.department_id

    row_reports: list[LabCourseUploadRowReport] = []
    created_count = 0
    updated_count = 0
    rejected_count = 0
    offices_to_create: list[str] = []
    offices_without_officers: list[str] = []

    for idx, row in enumerate(reader, start=1):
        code = (row.get(fieldnames_map["code"]) or "").strip().upper()
        name = (row.get(fieldnames_map["name"]) or "").strip()
        lab_office_str = (row.get(fieldnames_map["lab_office"]) or "").strip()
        specialization = (row.get(fieldnames_map.get("specialization", "")) or "").strip() or None

        if not code or not name:
            row_reports.append(LabCourseUploadRowReport(row_number=idx, code=code or "UNKNOWN", status="rejected", reason="Code and name are mandatory"))
            rejected_count += 1
            continue

        if not lab_office_str:
            row_reports.append(LabCourseUploadRowReport(row_number=idx, code=code, status="rejected", reason="Lab office is mandatory"))
            rejected_count += 1
            continue

        matched_dept = db.execute(
            select(Department).where(func.lower(Department.name) == lab_office_str.lower())
        ).scalars().first()
        if not matched_dept and lab_office_str.isdigit():
            matched_dept = db.get(Department, int(lab_office_str))

        if matched_dept:
            if matched_dept.applicability != DepartmentApplicability.LAB_WORKSHOP:
                row_reports.append(
                    LabCourseUploadRowReport(
                        row_number=idx,
                        code=code,
                        status="rejected",
                        reason=f"'{matched_dept.name}' is a {matched_dept.label}, not a Lab / Workshop. Ask the admin to change its type.",
                    )
                )
                rejected_count += 1
                continue
            if not matched_dept.is_active:
                row_reports.append(
                    LabCourseUploadRowReport(
                        row_number=idx,
                        code=code,
                        status="rejected",
                        reason=f"Lab office '{matched_dept.name}' is inactive.",
                    )
                )
                rejected_count += 1
                continue
        else:
            if lab_office_str not in offices_to_create:
                offices_to_create.append(lab_office_str)

            if not create_missing_offices:
                row_reports.append(
                    LabCourseUploadRowReport(
                        row_number=idx,
                        code=code,
                        status="rejected",
                        reason="Office does not exist. Preview and enable 'create missing offices', or ask the admin to create it.",
                    )
                )
                rejected_count += 1
                continue

            if len(lab_office_str) < 3 or len(lab_office_str) > 80:
                row_reports.append(
                    LabCourseUploadRowReport(
                        row_number=idx,
                        code=code,
                        status="rejected",
                        reason="Lab office name must be between 3 and 80 characters.",
                    )
                )
                rejected_count += 1
                continue

            if not dry_run:
                new_office = Department(
                    name=lab_office_str,
                    kind=DepartmentKind.service,
                    applicability=DepartmentApplicability.LAB_WORKSHOP,
                    is_active=True,
                    created_by_user_id=current_user.id,
                )
                db.add(new_office)
                db.flush()
                audit_dept = AuditLog(
                    user_id=current_user.id,
                    action="DEPARTMENT_CREATED",
                    entity_type="Department",
                    entity_id=new_office.id,
                    details={"name": new_office.name, "category": "LAB_WORKSHOP", "source": "lab_catalog_upload"},
                    created_at=datetime.now(timezone.utc),
                )
                db.add(audit_dept)
                matched_dept = new_office
            else:
                matched_dept = Department(
                    id=-(len(offices_to_create)),
                    name=lab_office_str,
                    kind=DepartmentKind.service,
                    applicability=DepartmentApplicability.LAB_WORKSHOP,
                    is_active=True,
                )

        if matched_dept.id > 0:
            officers = active_officers_for(db, matched_dept.id)
            if not officers and matched_dept.name not in offices_without_officers:
                offices_without_officers.append(matched_dept.name)
        else:
            if matched_dept.name not in offices_without_officers:
                offices_without_officers.append(matched_dept.name)

        existing = db.execute(
            select(LabCourse)
            .where(func.upper(LabCourse.code) == code)
            .options(joinedload(LabCourse.lab_department))
        ).scalars().first()

        if existing:
            if existing.academic_department_id not in officer_acad_dept_ids:
                row_reports.append(
                    LabCourseUploadRowReport(
                        row_number=idx,
                        code=code,
                        status="rejected",
                        reason="Lab course code already belongs to another academic department",
                    )
                )
                rejected_count += 1
                continue

            old_office_name = existing.lab_department.name if existing.lab_department else f"Department #{existing.lab_department_id}"
            office_changed = (matched_dept.id > 0 and existing.lab_department_id != matched_dept.id) or (matched_dept.id < 0 and old_office_name.lower() != matched_dept.name.lower())

            if office_changed:
                status_text = f"updated (office changed from {old_office_name} to {matched_dept.name})"
            else:
                status_text = "updated"

            if not dry_run:
                existing.name = name
                if matched_dept.id > 0:
                    existing.lab_department_id = matched_dept.id
                existing.specialization = specialization
                existing.is_active = True

            row_reports.append(LabCourseUploadRowReport(row_number=idx, code=code, status=status_text))
            updated_count += 1
        else:
            if not dry_run:
                new_course = LabCourse(
                    code=code,
                    name=name,
                    academic_department_id=default_acad_id,
                    lab_department_id=matched_dept.id,
                    specialization=specialization,
                    is_active=True,
                )
                db.add(new_course)
            row_reports.append(LabCourseUploadRowReport(row_number=idx, code=code, status="created"))
            created_count += 1

    if dry_run:
        db.rollback()
    else:
        audit = AuditLog(
            user_id=current_user.id,
            action="ACADEMIC_LAB_COURSES_UPLOADED",
            entity_type="LabCourse",
            entity_id=None,
            details={
                "department_id": current_user.department_id,
                "total_rows": len(row_reports),
                "created": created_count,
                "updated": updated_count,
                "rejected": rejected_count,
                "offices_created": offices_to_create,
            },
            created_at=datetime.now(timezone.utc),
        )
        db.add(audit)
        db.commit()

    return LabCourseUploadResponse(
        total_rows=len(row_reports),
        created_count=created_count,
        updated_count=updated_count,
        rejected_count=rejected_count,
        rows=row_reports,
        offices_to_create=offices_to_create,
        offices_without_officers=offices_without_officers,
        dry_run=dry_run,
    )


@router.patch(
    "/lab-courses/{id}",
    response_model=LabCourseItem,
    status_code=status.HTTP_200_OK,
    operation_id="patch_department_lab_course",
    summary="Update Lab Course",
    description="Updates a lab course's code, name, lab department, specialization, or active status.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid lab department or applicability"},
        403: {"model": ErrorResponse, "description": "Forbidden for service department officers"},
        404: {"model": ErrorResponse, "description": "Lab course not found in your academic department"},
        409: {"model": ErrorResponse, "description": "Lab course code already exists"},
    },
)
def patch_department_lab_course(
    id: int,
    body: LabCoursePatch,
    db: SessionDep,
    current_user: User = Depends(require_academic_officer),
) -> LabCourseItem:
    course = db.execute(
        select(LabCourse)
        .where(LabCourse.id == id)
        .options(joinedload(LabCourse.academic_department), joinedload(LabCourse.lab_department))
    ).scalars().first()

    if not course or course.academic_department_id not in user_academic_department_ids(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab course not found in your academic department.",
        )

    if body.code is not None:
        clean_code = body.code.strip().upper()
        if clean_code != course.code:
            exists = db.execute(
                select(LabCourse).where(func.upper(LabCourse.code) == clean_code, LabCourse.id != course.id)
            ).scalars().first()
            if exists:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Lab course code '{clean_code}' already exists.",
                )
            course.code = clean_code

    if body.name is not None:
        course.name = body.name.strip()

    if body.lab_department_id is not None:
        target_office = db.get(Department, body.lab_department_id)
        if not target_office or not target_office.is_active or target_office.applicability != DepartmentApplicability.LAB_WORKSHOP:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assigned lab office must be an active Lab / Workshop department.",
            )
        course.lab_department_id = target_office.id

    if body.specialization is not None:
        course.specialization = body.specialization.strip() if body.specialization else None

    if body.is_active is not None:
        course.is_active = body.is_active

    audit = AuditLog(
        user_id=current_user.id,
        action="LAB_COURSE_UPDATED",
        entity_type="LabCourse",
        entity_id=course.id,
        details={"code": course.code, "is_active": course.is_active},
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    db.commit()
    db.refresh(course)

    return _format_lab_item(course)


@router.post(
    "/lab-workshops",
    response_model=LabWorkshopOfficeItem,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_officer_lab_workshop",
    summary="Create Lab / Workshop Office",
    description="Academic officers can create a Lab / Workshop office.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid office name"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-academic officers"},
        409: {"model": ErrorResponse, "description": "Department name already exists"},
    },
)
def create_officer_lab_workshop(
    body: CreateLabWorkshopRequest,
    db: SessionDep,
    current_user: User = Depends(require_academic_officer),
) -> LabWorkshopOfficeItem:
    clean_name = body.name.strip()
    if len(clean_name) < 3 or len(clean_name) > 80:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department name must be between 3 and 80 characters.",
        )

    clash = db.execute(
        select(Department).where(func.lower(Department.name) == clean_name.lower())
    ).scalars().first()
    if clash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Department '{clean_name}' already exists.",
        )

    dept = Department(
        name=clean_name,
        kind=DepartmentKind.service,
        applicability=DepartmentApplicability.LAB_WORKSHOP,
        description=body.description.strip() if body.description else None,
        is_active=True,
        created_by_user_id=current_user.id,
    )
    db.add(dept)
    db.flush()

    audit = AuditLog(
        user_id=current_user.id,
        action="LAB_WORKSHOP_OFFICE_CREATED",
        entity_type="Department",
        entity_id=dept.id,
        details={"name": dept.name, "category": "LAB_WORKSHOP"},
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    db.commit()
    db.refresh(dept)

    return LabWorkshopOfficeItem(
        id=dept.id,
        name=dept.name,
        description=dept.description,
        category="LAB_WORKSHOP",
        label="Lab / Workshop",
        is_active=dept.is_active,
        editable=True,
        subject_count=0,
        created_by_me=True,
    )


@router.get(
    "/lab-workshops",
    response_model=list[LabWorkshopOfficeItem],
    status_code=status.HTTP_200_OK,
    operation_id="list_officer_lab_workshops",
    summary="List Officer Lab / Workshop Offices",
    description="Lists Lab / Workshop offices linked to officer's subjects or created by them with editable flag.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-academic officers"},
    },
)
def list_officer_lab_workshops(
    db: SessionDep,
    current_user: User = Depends(require_academic_officer),
) -> list[LabWorkshopOfficeItem]:
    officer_acad_dept_ids = user_academic_department_ids(current_user, db)

    all_courses = db.execute(select(LabCourse)).scalars().all()
    courses_by_dept: dict[int, list[LabCourse]] = {}
    for c in all_courses:
        courses_by_dept.setdefault(c.lab_department_id, []).append(c)

    offices = db.execute(
        select(Department)
        .where(Department.applicability == DepartmentApplicability.LAB_WORKSHOP)
        .order_by(Department.name.asc())
    ).scalars().all()

    items = []
    for d in offices:
        dept_courses = courses_by_dept.get(d.id, [])
        has_own_subject = any(c.academic_department_id in officer_acad_dept_ids for c in dept_courses)
        created_by_me = (d.created_by_user_id == current_user.id)

        if not has_own_subject and not created_by_me:
            continue

        if dept_courses:
            editable = all(c.academic_department_id in officer_acad_dept_ids for c in dept_courses)
        else:
            editable = created_by_me

        items.append(
            LabWorkshopOfficeItem(
                id=d.id,
                name=d.name,
                description=d.description,
                category="LAB_WORKSHOP",
                label="Lab / Workshop",
                is_active=d.is_active,
                editable=editable,
                subject_count=len(dept_courses),
                created_by_me=created_by_me,
            )
        )
    return items


@router.patch(
    "/lab-workshops/{id}",
    response_model=LabWorkshopOfficeItem,
    status_code=status.HTTP_200_OK,
    operation_id="patch_officer_lab_workshop",
    summary="Update Lab / Workshop Office",
    description="Renames, edits description, or deactivates a Lab / Workshop office if owned/editable.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid office name"},
        403: {"model": ErrorResponse, "description": "Forbidden: office subjects belong to other academic departments or not created by user"},
        404: {"model": ErrorResponse, "description": "Office not found"},
        409: {"model": ErrorResponse, "description": "Name clash or open approvals on active requests"},
    },
)
def patch_officer_lab_workshop(
    id: int,
    body: UpdateLabWorkshopRequest,
    db: SessionDep,
    current_user: User = Depends(require_academic_officer),
) -> LabWorkshopOfficeItem:
    office = db.get(Department, id)
    if not office or office.applicability != DepartmentApplicability.LAB_WORKSHOP:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab / Workshop office not found.")

    officer_acad_dept_ids = user_academic_department_ids(current_user, db)
    dept_courses = db.execute(select(LabCourse).where(LabCourse.lab_department_id == office.id)).scalars().all()

    if dept_courses:
        if not all(c.academic_department_id in officer_acad_dept_ids for c in dept_courses):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot edit this lab/workshop office because some of its subjects belong to other academic departments.",
            )
    else:
        if office.created_by_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot edit this lab/workshop office because you did not create it.",
            )

    if body.is_active is False and office.is_active:
        open_approvals_count = db.execute(
            select(func.count(DepartmentApproval.id))
            .join(ClearanceRequest, DepartmentApproval.request_id == ClearanceRequest.id)
            .where(
                DepartmentApproval.department_id == office.id,
                ClearanceRequest.status.not_in([
                    ClearanceStatus.CLEARED,
                    ClearanceStatus.REFUND_VERIFIED,
                    ClearanceStatus.CANCELLED,
                ]),
            )
        ).scalar() or 0
        if open_approvals_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot deactivate office '{office.name}': it has {open_approvals_count} open approvals on active clearance requests.",
            )
        office.is_active = False
    elif body.is_active is True:
        office.is_active = True

    if body.name is not None:
        clean_name = body.name.strip()
        if len(clean_name) < 3 or len(clean_name) > 80:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department name must be between 3 and 80 characters.",
            )
        if clean_name.lower() != office.name.lower():
            clash = db.execute(
                select(Department).where(func.lower(Department.name) == clean_name.lower(), Department.id != office.id)
            ).scalars().first()
            if clash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Department '{clean_name}' already exists.",
                )
        office.name = clean_name

    if body.description is not None:
        office.description = body.description.strip() if body.description else None

    audit = AuditLog(
        user_id=current_user.id,
        action="LAB_WORKSHOP_OFFICE_UPDATED",
        entity_type="Department",
        entity_id=office.id,
        details={"name": office.name, "is_active": office.is_active},
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    db.commit()
    db.refresh(office)

    return LabWorkshopOfficeItem(
        id=office.id,
        name=office.name,
        description=office.description,
        category="LAB_WORKSHOP",
        label="Lab / Workshop",
        is_active=office.is_active,
        editable=True,
        subject_count=len(dept_courses),
        created_by_me=(office.created_by_user_id == current_user.id),
    )

    return _format_lab_item(course)
