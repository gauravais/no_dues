"""Administrator management endpoints: Roster upload, staff provisioning, and password resets."""
import codecs
import csv
import io
import re
import secrets
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select, func, or_, delete
from sqlalchemy.orm import joinedload

from backend.app.api.deps import SessionDep, require_roles
from backend.app.core.config import settings
from backend.app.core.security import hash_password, normalize_email
from backend.app.models.user import User, UserRole, UserDepartment
from backend.app.models.roster import StudentRoster, RosterAssignedDepartment
from backend.app.models.university import Faculty, Department, Programme, DepartmentKind, DepartmentApplicability
from backend.app.models.clearance import ClearanceRequest, ClearanceStatus, DepartmentApproval, ApprovalStatus
from backend.app.models.lab_course import LabCourse
from backend.app.models.audit import AuditLog
from backend.app.schemas.common import ErrorResponse, DepartmentBrief
from backend.app.schemas.admin import (
    RosterUploadResponse,
    RosterUploadRowReport,
    RosterListResponse,
    RosterItem,
    RosterUpdateRequest,
    RosterAssignedDepartmentsRequest,
    AdminCreateUserRequest,
    AdminUserResponse,
    AdminUserDetailResponse,
    AddUserDepartmentRequest,
    AdminResetPasswordResponse,
    AdminUserActiveRequest,
    AdminUserListItem,
    AdminOfficeUserSummary,
    AdminOfficeSummary,
    AdminOfficeListResponse,
    AdminUserBulkUploadDetail,
    AdminUserBulkUploadResponse,
    AdminDepartmentListItem,
    AdminDepartmentListResponse,
    AdminCreateDepartmentRequest,
    AdminUpdateDepartmentRequest,
    BulkCategoryRequest,
    BulkCategoryResponse,
    AdminUpdateUserRequest,
    FacultyResponse,
    FacultyCreate,
    FacultyUpdate,
    AcademicDepartmentResponse,
    AcademicDepartmentCreate,
    AcademicDepartmentUpdate,
    ProgrammeResponse,
    ProgrammeCreate,
    ProgrammeUpdate,
)
from backend.app.schemas.department import (
    LabCourseListResponse,
    LabCourseItem,
    LabCourseCreate,
    LabCoursePatch,
    LabCourseUploadResponse,
    LabCourseUploadRowReport,
)

from backend.app.schemas.workflow import StaffCancelRequest, CancelResponse
from backend.app.services.workflow import (
    staff_cancel_request,
    user_department_ids,
    get_user_departments,
    active_officers_for,
    active_hod_for,
)

from backend.app.services.exceptions import (
    WorkflowBadRequestError,
    WorkflowNotFoundError,
    WorkflowForbiddenError,
)

router = APIRouter(prefix="/admin", tags=["Admin"])
require_admin = require_roles(UserRole.admin)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _record_admin_audit(
    db: SessionDep,
    admin_id: int,
    action: str,
    entity_type: str,
    entity_id: int | None,
    details: dict | None,
) -> None:
    audit = AuditLog(
        user_id=admin_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit)


def _format_roster_item(r: StudentRoster, message: str | None = None) -> RosterItem:
    prog_name = r.programme.name if r.programme else "N/A"
    assigned_ids = [ad.department_id for ad in r.assigned_departments or []]
    return RosterItem(
        id=r.id,
        registration_number=r.registration_number,
        name=r.name,
        email=r.email,
        mobile=r.mobile,
        address=r.address,
        programme_id=r.programme_id,
        programme_name=prog_name,
        is_hosteller=r.is_hosteller,
        security_deposit_amount=r.security_deposit_amount,
        assigned_department_ids=assigned_ids,
        message=message,
    )


@router.post(
    "/roster/upload",
    response_model=RosterUploadResponse,
    status_code=status.HTTP_200_OK,
    operation_id="upload_roster_csv",
    summary="Upload Student Roster CSV",
    description=(
        "Uploads a CSV file containing student roster records. Validates each row: non-empty credentials, "
        "valid email format, known programme name, and valid hosteller flag. "
        "Security deposit amounts are ignored (managed exclusively by Accounts). "
        "Performs an upsert based on registration_number and returns a row-by-row status report. "
        "Does NOT create user accounts."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid CSV file format or headers"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
    },
)
async def upload_roster_csv(
    db: SessionDep,
    file: UploadFile = File(..., description="CSV file with student roster records"),
    current_user: User = Depends(require_admin),
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
    required_cols = [
        "registration_number", "name", "email", "mobile",
        "address", "programme", "is_hosteller"
    ]
    for col in required_cols:
        if col not in fieldnames_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required CSV column '{col}'. Required columns: {', '.join(required_cols)}",
            )

    has_deposit_col = "security_deposit_amount" in fieldnames_map

    # Pre-fetch all programmes for fast lookup
    all_programmes = db.execute(select(Programme)).scalars().all()
    prog_map = {p.name.strip().lower(): p.id for p in all_programmes}

    row_reports: list[RosterUploadRowReport] = []
    created_count = 0
    updated_count = 0
    rejected_count = 0

    for idx, row in enumerate(reader, start=1):
        reg_num = (row.get(fieldnames_map["registration_number"]) or "").strip()
        name = (row.get(fieldnames_map["name"]) or "").strip()
        email = normalize_email(row.get(fieldnames_map["email"]))
        mobile = (row.get(fieldnames_map["mobile"]) or "").strip()
        address = (row.get(fieldnames_map["address"]) or "").strip()
        prog_str = (row.get(fieldnames_map["programme"]) or "").strip()
        hosteller_str = (row.get(fieldnames_map["is_hosteller"]) or "").strip().lower()

        # Validations
        if not reg_num:
            row_reports.append(RosterUploadRowReport(row_number=idx, registration_number="UNKNOWN", status="rejected", reason="Registration number cannot be empty"))
            rejected_count += 1
            continue

        if not name or not mobile or not address:
            row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="rejected", reason="Student name, mobile, and address are mandatory"))
            rejected_count += 1
            continue

        if not EMAIL_REGEX.match(email):
            row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="rejected", reason=f"Invalid email format: '{email}'"))
            rejected_count += 1
            continue

        domain = email.split("@")[-1] if "@" in email else ""
        if domain not in settings.allowed_email_domain_list:
            row_reports.append(
                RosterUploadRowReport(
                    row_number=idx,
                    registration_number=reg_num,
                    status="rejected",
                    reason=f"Email domain '@{domain}' is not allowed. Allowed domains: {', '.join(settings.allowed_email_domain_list)}",
                )
            )
            rejected_count += 1
            continue

        prog_id = prog_map.get(prog_str.lower())
        if not prog_id:
            row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="rejected", reason=f"Unknown programme: '{prog_str}'"))
            rejected_count += 1
            continue

        is_hosteller = hosteller_str in ("true", "1", "yes", "y", "t")

        # Upsert
        existing = db.execute(
            select(StudentRoster).where(StudentRoster.registration_number == reg_num)
        ).scalars().first()

        if existing:
            # Check if email is being changed
            if existing.email != email:
                # Check email uniqueness against other roster rows
                email_clash = db.execute(
                    select(StudentRoster).where(
                        func.lower(StudentRoster.email) == email,
                        StudentRoster.id != existing.id,
                    )
                ).scalars().first()
                if email_clash:
                    row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="rejected", reason=f"Email '{email}' is already registered to another student ({email_clash.registration_number})"))
                    rejected_count += 1
                    continue

                # Check if this student already has a user account
                student_user = db.execute(
                    select(User).where(User.roster_id == existing.id)
                ).scalars().first()

                if student_user:
                    # Check if email is taken by another user
                    user_clash = db.execute(
                        select(User).where(
                            func.lower(User.email) == email,
                            User.id != student_user.id,
                        )
                    ).scalars().first()
                    if user_clash:
                        row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="rejected", reason=f"Email '{email}' is already taken by another user account"))
                        rejected_count += 1
                        continue

                    old_user_email = student_user.email
                    student_user.email = email
                    _record_admin_audit(
                        db,
                        current_user.id,
                        action="UPDATE_USER_EMAIL_FROM_ROSTER_CSV",
                        entity_type="users",
                        entity_id=student_user.id,
                        details={"old_email": old_user_email, "new_email": email, "roster_id": existing.id},
                    )

            existing.name = name
            existing.email = email
            existing.mobile = mobile
            existing.address = address
            existing.programme_id = prog_id
            existing.is_hosteller = is_hosteller
            # Security deposit is managed exclusively by Accounts; do not overwrite existing value
            existing.updated_by_user_id = current_user.id
            row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="updated"))
            updated_count += 1
        else:
            # Check email uniqueness against existing roster
            email_clash = db.execute(
                select(StudentRoster).where(func.lower(StudentRoster.email) == email)
            ).scalars().first()
            if email_clash:
                row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="rejected", reason=f"Email '{email}' is already registered to another student ({email_clash.registration_number})"))
                rejected_count += 1
                continue

            # Check email uniqueness against existing users
            user_clash = db.execute(
                select(User).where(func.lower(User.email) == email)
            ).scalars().first()
            if user_clash:
                row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="rejected", reason=f"Email '{email}' is already taken by another user account"))
                rejected_count += 1
                continue

            new_roster = StudentRoster(
                registration_number=reg_num,
                name=name,
                email=email,
                mobile=mobile,
                address=address,
                programme_id=prog_id,
                is_hosteller=is_hosteller,
                security_deposit_amount=Decimal("0.00"),
                source="admin",
                created_by_user_id=current_user.id,
                updated_by_user_id=current_user.id,
            )
            db.add(new_roster)
            row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="created"))
            created_count += 1

    total_rows = len(row_reports)
    _record_admin_audit(
        db,
        current_user.id,
        action="ROSTER_CSV_UPLOAD",
        entity_type="student_roster",
        entity_id=None,
        details={
            "filename": file.filename,
            "total_rows": total_rows,
            "created": created_count,
            "updated": updated_count,
            "rejected": rejected_count,
        },
    )
    db.commit()

    upload_message = (
        "Security deposits are managed by Accounts and any provided deposit amounts were ignored."
        if has_deposit_col
        else None
    )

    return RosterUploadResponse(
        total_rows=total_rows,
        created_count=created_count,
        updated_count=updated_count,
        rejected_count=rejected_count,
        rows=row_reports,
        message=upload_message,
    )


@router.get(
    "/roster",
    response_model=RosterListResponse,
    status_code=status.HTTP_200_OK,
    operation_id="list_student_roster",
    summary="List and Search Student Roster",
    description="Retrieves a paginated list of student roster records with optional search filter.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
    },
)
def list_roster(
    db: SessionDep,
    current_user: User = Depends(require_admin),
    search: str | None = Query(None, description="Search by registration number, name, or email"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> RosterListResponse:
    query = select(StudentRoster).options(
        joinedload(StudentRoster.programme),
        joinedload(StudentRoster.assigned_departments),
    )

    if search:
        s = f"%{search.strip()}%"
        query = query.where(
            or_(
                StudentRoster.registration_number.ilike(s),
                StudentRoster.name.ilike(s),
                StudentRoster.email.ilike(s),
            )
        )

    count_query = select(func.count(StudentRoster.id))
    if search:
        s = f"%{search.strip()}%"
        count_query = count_query.where(
            or_(
                StudentRoster.registration_number.ilike(s),
                StudentRoster.name.ilike(s),
                StudentRoster.email.ilike(s),
            )
        )

    total = db.scalar(count_query) or 0
    roster_rows = db.execute(
        query.order_by(StudentRoster.registration_number.asc()).limit(limit).offset(offset)
    ).scalars().unique().all()

    items = [_format_roster_item(r) for r in roster_rows]
    return RosterListResponse(total=total, items=items)


@router.patch(
    "/roster/{id}",
    response_model=RosterItem,
    status_code=status.HTTP_200_OK,
    operation_id="update_roster_entry",
    summary="Update Student Roster Profile",
    description="Updates hosteller status, address, or mobile for a roster record. Security deposit amounts are ignored (managed exclusively by Accounts).",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid update values"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        404: {"model": ErrorResponse, "description": "Roster record not found"},
    },
)
def update_roster_entry(
    id: int,
    body: RosterUpdateRequest,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> RosterItem:
    roster = db.execute(
        select(StudentRoster)
        .where(StudentRoster.id == id)
        .options(
            joinedload(StudentRoster.programme),
            joinedload(StudentRoster.assigned_departments),
        )
    ).scalars().first()

    if not roster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roster record not found")

    deposit_message = None
    if body.security_deposit_amount is not None:
        deposit_message = "Security deposits are managed by Accounts."

    changes = {}
    if body.is_hosteller is not None:
        changes["is_hosteller"] = body.is_hosteller
        roster.is_hosteller = body.is_hosteller

    if body.address is not None:
        changes["address"] = body.address.strip()
        roster.address = body.address.strip()

    if body.mobile is not None:
        changes["mobile"] = body.mobile.strip()
        roster.mobile = body.mobile.strip()

    if body.email is not None:
        new_email = normalize_email(str(body.email))
        if not EMAIL_REGEX.match(new_email):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid email format: '{new_email}'")

        domain = new_email.split("@")[-1] if "@" in new_email else ""
        if domain not in settings.allowed_email_domain_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email domain '@{domain}' is not allowed. Allowed domains: {', '.join(settings.allowed_email_domain_list)}",
            )

        if new_email != roster.email:
            # Check clash with another roster entry
            roster_clash = db.execute(
                select(StudentRoster).where(
                    func.lower(StudentRoster.email) == new_email,
                    StudentRoster.id != roster.id,
                )
            ).scalars().first()
            if roster_clash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Email '{new_email}' is already in use by another roster entry ({roster_clash.registration_number}).",
                )

            # Check if student has a linked user account
            student_user = db.execute(
                select(User).where(User.roster_id == roster.id)
            ).scalars().first()

            if student_user:
                user_clash = db.execute(
                    select(User).where(
                        func.lower(User.email) == new_email,
                        User.id != student_user.id,
                    )
                ).scalars().first()
                if user_clash:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Email '{new_email}' is already taken by another user account.",
                    )
                old_user_email = student_user.email
                student_user.email = new_email
                _record_admin_audit(
                    db,
                    current_user.id,
                    action="UPDATE_USER_EMAIL_FROM_ROSTER",
                    entity_type="users",
                    entity_id=student_user.id,
                    details={"old_email": old_user_email, "new_email": new_email, "roster_id": roster.id},
                )
            else:
                user_clash = db.execute(
                    select(User).where(func.lower(User.email) == new_email)
                ).scalars().first()
                if user_clash:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Email '{new_email}' is already taken by another user account.",
                    )

            changes["email"] = new_email
            roster.email = new_email

    roster.updated_by_user_id = current_user.id

    _record_admin_audit(
        db,
        current_user.id,
        action="UPDATE_ROSTER_ENTRY",
        entity_type="student_roster",
        entity_id=roster.id,
        details=changes,
    )
    db.commit()
    db.refresh(roster)

    return _format_roster_item(roster, message=deposit_message)


@router.put(
    "/roster/{id}/assigned-departments",
    response_model=RosterItem,
    status_code=status.HTTP_200_OK,
    operation_id="update_roster_assigned_departments",
    summary="Update Assigned Labs & Workshops",
    description="Replaces assigned laboratory and workshop departments for a student roster profile.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid department ID"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        404: {"model": ErrorResponse, "description": "Roster record not found"},
    },
)
def update_roster_assigned_departments(
    id: int,
    body: RosterAssignedDepartmentsRequest,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> RosterItem:
    roster = db.execute(
        select(StudentRoster)
        .where(StudentRoster.id == id)
        .options(
            joinedload(StudentRoster.programme),
            joinedload(StudentRoster.assigned_departments),
        )
    ).scalars().first()

    if not roster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roster record not found")

    # Validate that all requested departments exist
    if body.department_ids:
        existing_depts = db.execute(
            select(Department.id).where(Department.id.in_(body.department_ids))
        ).scalars().all()
        missing = set(body.department_ids) - set(existing_depts)
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Departments not found for IDs: {sorted(missing)}",
            )

    # Delete existing mappings
    db.execute(
        delete(RosterAssignedDepartment).where(RosterAssignedDepartment.roster_id == roster.id)
    )

    # Insert new mappings
    for did in set(body.department_ids):
        db.add(RosterAssignedDepartment(roster_id=roster.id, department_id=did))

    _record_admin_audit(
        db,
        current_user.id,
        action="ASSIGN_ROSTER_DEPARTMENTS",
        entity_type="student_roster",
        entity_id=roster.id,
        details={"department_ids": body.department_ids},
    )
    db.commit()
    db.refresh(roster)

    return _format_roster_item(roster)


@router.post(
    "/users",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_staff_user",
    summary="Create University Staff User",
    description=(
        "Provisions a new staff user (dept_officer, hod, or registrar_accounts). Department is mandatory for "
        "officers and HoDs. HoDs must be assigned to an academic department. Automatically generates a secure "
        "random temporary password and returns it ONCE in the response (never logged)."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid role, missing department, or non-academic HoD"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        409: {"model": ErrorResponse, "description": "User with this email already exists"},
    },
)
def create_staff_user(
    body: AdminCreateUserRequest,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> AdminUserResponse:
    if body.role not in (UserRole.dept_officer, UserRole.hod, UserRole.registrar_accounts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Admin can only create staff roles: dept_officer, hod, registrar_accounts. Received: {body.role.value}",
        )

    # Normalize and validate email domain
    email_clean = normalize_email(str(body.email))
    domain = email_clean.split("@")[-1] if "@" in email_clean else ""
    if domain not in settings.allowed_email_domain_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email domain '{domain}' is not allowed for staff creation. Allowed domains: {', '.join(settings.allowed_email_domain_list)}",
        )

    # Check email conflict case-insensitively
    existing_user = db.execute(
        select(User).where(func.lower(User.email) == email_clean)
    ).scalars().first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"User with email '{email_clean}' already exists")

    # Department normalization & validation
    if body.department_ids is not None:
        dept_ids = list(dict.fromkeys(body.department_ids))
    elif body.department_id is not None:
        dept_ids = [body.department_id]
    else:
        dept_ids = []

    depts: list[Department] = []
    if body.role in (UserRole.dept_officer, UserRole.hod):
        if not dept_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department ID is mandatory for role '{body.role.value}'",
            )
        for did in dept_ids:
            d = db.get(Department, did)
            if not d:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Department ID {did} not found")
            if body.role == UserRole.hod and d.kind != DepartmentKind.academic:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Chairperson (HoD) user must belong to an academic department. '{d.name}' is a service department.",
                )
            depts.append(d)
    elif body.role == UserRole.registrar_accounts:
        rs_dept = db.execute(
            select(Department).where(func.lower(Department.name).in_(["r&s branch", "registration & scholarship branch"]))
        ).scalars().first()
        if dept_ids:
            for did in dept_ids:
                d = db.get(Department, did)
                if not d:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Department ID {did} not found")
                if rs_dept and d.id != rs_dept.id:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="registrar_accounts must be assigned to R&S Branch")
                depts.append(d)
        elif rs_dept:
            depts.append(rs_dept)
    else:
        if dept_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin and student roles cannot have department assignments.")

    primary_dept_id = depts[0].id if depts else None
    primary_dept = depts[0] if depts else None

    # Handle Google-only accounts vs password accounts
    if body.google_only:
        temp_password = None
        pw_hash = None
        must_change_pw = False
    else:
        temp_password = secrets.token_urlsafe(12)
        pw_hash = hash_password(temp_password)
        must_change_pw = True

    now = datetime.now(timezone.utc)

    user = User(
        email=email_clean,
        full_name=body.full_name.strip(),
        password_hash=pw_hash,
        role=body.role,
        department_id=primary_dept_id,
        roster_id=None,
        is_active=True,
        must_change_password=must_change_pw,
        created_at=now,
    )
    db.add(user)
    db.flush()

    for d in depts:
        db.add(UserDepartment(
            user_id=user.id,
            department_id=d.id,
            created_at=now,
            created_by_user_id=current_user.id,
        ))

    _record_admin_audit(
        db,
        current_user.id,
        action="CREATE_USER",
        entity_type="users",
        entity_id=user.id,
        details={
            "email": user.email,
            "role": user.role.value,
            "department_id": user.department_id,
            "department_ids": [d.id for d in depts],
        },
    )
    db.commit()
    db.refresh(user)

    dept_briefs = [
        DepartmentBrief(id=d.id, name=d.name, kind=d.kind.value)
        for d in depts
    ]

    return AdminUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        department_id=user.department_id,
        department_name=primary_dept.name if primary_dept else None,
        departments=dept_briefs,
        is_active=user.is_active,
        temporary_password=temp_password,
    )



@router.post(
    "/users/{id}/reset-password",
    response_model=AdminResetPasswordResponse,
    status_code=status.HTTP_200_OK,
    operation_id="reset_user_password_admin",
    summary="Reset User Password",
    description="Generates a new random temporary password for any user account and returns it once in the response.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
)
def reset_user_password(
    id: int,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> AdminResetPasswordResponse:
    user = db.get(User, id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Password cannot be reset for Google-authenticated accounts without password login.",
        )

    temp_password = secrets.token_urlsafe(12)
    user.password_hash = hash_password(temp_password)
    user.must_change_password = True

    _record_admin_audit(
        db,
        current_user.id,
        action="RESET_USER_PASSWORD",
        entity_type="users",
        entity_id=user.id,
        details={"email": user.email},
    )
    db.commit()

    return AdminResetPasswordResponse(
        user_id=user.id,
        email=user.email,
        temporary_password=temp_password,
    )


@router.get(
    "/users/{id}",
    response_model=AdminUserDetailResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_admin_user_detail",
    summary="Get User Details",
    description="Retrieves full user detail including all department memberships.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
)
def get_admin_user_detail(
    id: int,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> AdminUserDetailResponse:
    user = db.get(User, id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    depts = get_user_departments(user, db)
    dept_briefs = [
        DepartmentBrief(id=d.id, name=d.name, kind=d.kind.value)
        for d in depts
    ]
    primary_dept = db.get(Department, user.department_id) if user.department_id else None

    return AdminUserDetailResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        department_id=user.department_id,
        department_name=primary_dept.name if primary_dept else None,
        departments=dept_briefs,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.patch(
    "/users/{id}",
    response_model=AdminUserDetailResponse,
    status_code=status.HTTP_200_OK,
    operation_id="patch_admin_user",
    summary="Update Staff User Details",
    description="Updates a staff user's full_name and email. Changing email when google_sub is bound requires unlink_google=true. Audited.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid email domain or user is student"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        404: {"model": ErrorResponse, "description": "User not found"},
        409: {"model": ErrorResponse, "description": "Email clash or Google account bound without unlink_google"},
    },
)
def patch_admin_user(
    id: int,
    body: AdminUpdateUserRequest,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> AdminUserDetailResponse:
    user = db.get(User, id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.role == UserRole.student:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only staff user accounts can be edited via this endpoint.")

    old_email = user.email
    old_name = user.full_name
    old_google_sub = user.google_sub

    if body.email is not None:
        new_email = normalize_email(str(body.email))
        if new_email != user.email:
            domain = new_email.split("@")[1].lower() if "@" in new_email else ""
            if domain not in settings.allowed_email_domain_list:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email domain '{domain}' is not allowed for university staff.",
                )

            if user.google_sub and not body.unlink_google:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User has a linked Google account. Pass unlink_google=true to proceed with email change.",
                )

            clash = db.execute(
                select(User).where(func.lower(User.email) == new_email, User.id != user.id)
            ).scalars().first()
            if clash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Email '{new_email}' is already taken.",
                )

            if user.google_sub and body.unlink_google:
                user.google_sub = None

            user.email = new_email

    if body.full_name is not None:
        user.full_name = body.full_name.strip()

    _record_admin_audit(
        db,
        current_user.id,
        action="ADMIN_STAFF_USER_UPDATED",
        entity_type="users",
        entity_id=user.id,
        details={
            "old_email": old_email,
            "new_email": user.email,
            "old_name": old_name,
            "new_name": user.full_name,
            "unlinked_google": (old_google_sub is not None and user.google_sub is None),
        },
    )
    db.commit()
    db.refresh(user)

    depts = get_user_departments(user, db)
    dept_briefs = [
        DepartmentBrief(id=d.id, name=d.name, kind=d.kind.value, category=d.category, label=d.category_label, is_active=d.is_active)
        for d in depts
    ]
    primary_dept = db.get(Department, user.department_id) if user.department_id else None

    return AdminUserDetailResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        department_id=user.department_id,
        department_name=primary_dept.name if primary_dept else None,
        departments=dept_briefs,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.post(
    "/users/{id}/departments",
    response_model=AdminUserDetailResponse,
    status_code=status.HTTP_200_OK,
    operation_id="add_user_department_membership",
    summary="Add Department Membership to User",
    description="Adds a department membership to a user account. HoD accounts must remain academic-only. Audited.",
    responses={
        400: {"model": ErrorResponse, "description": "Department not found or non-academic for HoD"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
)
def add_user_department(
    id: int,
    body: AddUserDepartmentRequest,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> AdminUserDetailResponse:
    user = db.get(User, id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.role in (UserRole.admin, UserRole.student):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot add department memberships to {user.role.value} role.",
        )

    dept = db.get(Department, body.department_id)
    if not dept:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Department ID {body.department_id} not found")

    if user.role == UserRole.hod and dept.kind != DepartmentKind.academic:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chairperson (HoD) user must belong exclusively to academic departments. '{dept.name}' is a service department.",
        )

    # Check if membership already exists
    existing = db.execute(
        select(UserDepartment).where(
            UserDepartment.user_id == user.id,
            UserDepartment.department_id == dept.id,
        )
    ).scalars().first()

    if not existing:
        now = datetime.now(timezone.utc)
        ud = UserDepartment(
            user_id=user.id,
            department_id=dept.id,
            created_at=now,
            created_by_user_id=current_user.id,
        )
        db.add(ud)
        if user.department_id is None:
            user.department_id = dept.id

        _record_admin_audit(
            db,
            current_user.id,
            action="ADD_USER_DEPARTMENT",
            entity_type="users",
            entity_id=user.id,
            details={"department_id": dept.id, "department_name": dept.name},
        )
        db.commit()
        db.refresh(user)

    depts = get_user_departments(user, db)
    dept_briefs = [DepartmentBrief(id=d.id, name=d.name, kind=d.kind.value) for d in depts]
    primary_dept = db.get(Department, user.department_id) if user.department_id else None

    return AdminUserDetailResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        department_id=user.department_id,
        department_name=primary_dept.name if primary_dept else None,
        departments=dept_briefs,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.delete(
    "/users/{id}/departments/{department_id}",
    response_model=AdminUserDetailResponse,
    status_code=status.HTTP_200_OK,
    operation_id="remove_user_department_membership",
    summary="Remove Department Membership from User",
    description="Removes a department membership from a user. Refuses removing the last department of a dept_officer or hod (409). Promotes another department to primary if primary is removed. Audited.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        404: {"model": ErrorResponse, "description": "User or department membership not found"},
        409: {"model": ErrorResponse, "description": "Cannot remove last department; deactivate the user instead"},
    },
)
def remove_user_department(
    id: int,
    department_id: int,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> AdminUserDetailResponse:
    user = db.get(User, id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    membership = db.execute(
        select(UserDepartment).where(
            UserDepartment.user_id == user.id,
            UserDepartment.department_id == department_id,
        )
    ).scalars().first()

    all_memberships = db.execute(
        select(UserDepartment).where(UserDepartment.user_id == user.id)
    ).scalars().all()
    all_dept_ids = {m.department_id for m in all_memberships}
    if user.department_id is not None:
        all_dept_ids.add(user.department_id)

    if department_id not in all_dept_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department membership not found for this user.",
        )

    if user.role in (UserRole.dept_officer, UserRole.hod) and len(all_dept_ids) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Deactivate the user instead",
        )

    if membership:
        db.delete(membership)

    remaining_dept_ids = all_dept_ids - {department_id}
    if user.department_id == department_id:
        user.department_id = sorted(list(remaining_dept_ids))[0] if remaining_dept_ids else None

    _record_admin_audit(
        db,
        current_user.id,
        action="REMOVE_USER_DEPARTMENT",
        entity_type="users",
        entity_id=user.id,
        details={
            "removed_department_id": department_id,
            "new_primary_department_id": user.department_id,
        },
    )
    db.commit()
    db.refresh(user)

    depts = get_user_departments(user, db)
    dept_briefs = [DepartmentBrief(id=d.id, name=d.name, kind=d.kind.value) for d in depts]
    primary_dept = db.get(Department, user.department_id) if user.department_id else None

    return AdminUserDetailResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        department_id=user.department_id,
        department_name=primary_dept.name if primary_dept else None,
        departments=dept_briefs,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )



@router.patch(
    "/users/{id}/active",
    response_model=AdminUserResponse,
    status_code=status.HTTP_200_OK,
    operation_id="toggle_user_active_status",
    summary="Activate or Deactivate User Account",
    description=(
        "Enables or disables a user account. Deactivated accounts are refused login immediately. "
        "An administrator is prevented from deactivating their own account."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Admin cannot deactivate their own account"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
)
def toggle_user_active(
    id: int,
    body: AdminUserActiveRequest,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> AdminUserResponse:
    user = db.get(User, id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == current_user.id and not body.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin cannot deactivate their own account",
        )

    user.is_active = body.is_active

    _record_admin_audit(
        db,
        current_user.id,
        action="UPDATE_USER_ACTIVE_STATUS",
        entity_type="users",
        entity_id=user.id,
        details={"is_active": body.is_active},
    )
    db.commit()
    db.refresh(user)

    dept_name = user.department.name if user.department else None

    return AdminUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        department_id=user.department_id,
        department_name=dept_name,
        is_active=user.is_active,
    )


@router.get(
    "/users",
    response_model=list[AdminUserListItem],
    status_code=status.HTTP_200_OK,
    operation_id="list_admin_users",
    summary="List University Users Directory",
    description=(
        "Retrieves a list of university users (students, officers, HoDs, accounts, admins). "
        "Supports search by email or name, and filtering by role. Password hashes are never returned."
    ),
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
    },
)
def list_admin_users(
    db: SessionDep,
    current_user: User = Depends(require_admin),
    search: str | None = Query(None, description="Search by email or full name"),
    role: UserRole | None = Query(None, description="Filter by user role"),
    department_id: int | None = Query(None, description="Filter by department ID"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> list[AdminUserListItem]:
    stmt = (
        select(User)
        .options(joinedload(User.department))
        .order_by(User.id.asc())
    )

    if role:
        stmt = stmt.where(User.role == role)

    if department_id is not None:
        stmt = (
            stmt.outerjoin(UserDepartment, UserDepartment.user_id == User.id)
            .where(
                or_(
                    User.department_id == department_id,
                    UserDepartment.department_id == department_id,
                )
            )
            .distinct()
        )

    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(User.email).like(term),
                func.lower(User.full_name).like(term),
            )
        )

    stmt = stmt.offset(offset).limit(limit)
    users = db.execute(stmt).scalars().all()

    items = []
    for u in users:
        u_depts = get_user_departments(u, db)
        dept_briefs = [
            DepartmentBrief(id=d.id, name=d.name, kind=d.kind.value)
            for d in u_depts
        ]
        items.append(
            AdminUserListItem(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                role=u.role.value,
                department=u.department.name if u.department else None,
                department_name=u.department.name if u.department else None,
                department_id=u.department_id,
                departments=dept_briefs,
                is_active=u.is_active,
                created_at=u.created_at,
            )
        )

    return items


@router.get(
    "/offices",
    response_model=AdminOfficeListResponse,
    status_code=status.HTTP_200_OK,
    operation_id="list_admin_offices",
    summary="List University Offices and Staffing Status",
    description="Returns all university departments with their active officers, HoD (if academic), and missing staff flags.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
    },
)
def list_admin_offices(
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> AdminOfficeListResponse:
    depts = db.execute(
        select(Department)
        .order_by(Department.id.asc())
    ).unique().scalars().all()

    office_items: list[AdminOfficeSummary] = []
    for d in depts:
        officers = active_officers_for(db, d.id)
        active_officers = [
            AdminOfficeUserSummary(id=u.id, name=u.full_name, email=u.email)
            for u in officers
        ]
        hod = active_hod_for(db, d.id) if d.kind == DepartmentKind.academic else None
        hod_user = AdminOfficeUserSummary(id=hod.id, name=hod.full_name, email=hod.email) if hod else None
        missing_officer = (len(active_officers) == 0)
        missing_hod = (d.kind == DepartmentKind.academic and hod_user is None)

        office_items.append(
            AdminOfficeSummary(
                id=d.id,
                name=d.name,
                kind=d.kind.value,
                applicability=d.applicability.value,
                category=d.category,
                label=d.category_label,
                is_active=d.is_active,
                description=d.description,
                active_officers=active_officers,
                hod=hod_user,
                missing_officer=missing_officer,
                missing_hod=missing_hod,
            )
        )

    return AdminOfficeListResponse(
        total=len(office_items),
        items=office_items,
    )



@router.post(
    "/users/bulk-upload",
    response_model=AdminUserBulkUploadResponse,
    status_code=status.HTTP_200_OK,
    operation_id="bulk_upload_admin_users",
    summary="Bulk Provision University Staff Users",
    description="Uploads a CSV of university staff accounts (dept_officer, hod, registrar_accounts). Returns one-time temporary passwords ONLY in this response.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid CSV structure or missing headers"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
    },
)
async def bulk_upload_admin_users(
    db: SessionDep,
    file: UploadFile = File(..., description="CSV file with staff accounts"),
    google_only: bool = Query(False, description="When true, created accounts have no password and authenticate via Google"),
    current_user: User = Depends(require_admin),
) -> AdminUserBulkUploadResponse:
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
    required_cols = ["email", "full_name", "role"]
    for col in required_cols:
        if col not in fieldnames_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required CSV column '{col}'. Required: {', '.join(required_cols)}",
            )
    if "department" not in fieldnames_map and "departments" not in fieldnames_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required CSV column 'department' or 'departments'.",
        )

    all_depts = db.execute(select(Department)).scalars().all()
    dept_by_name = {d.name.strip().lower(): d for d in all_depts}
    dept_by_id = {d.id: d for d in all_depts}

    row_reports: list[AdminUserBulkUploadDetail] = []
    created_count = 0
    rejected_count = 0

    for idx, row in enumerate(reader, start=1):
        raw_email = row.get(fieldnames_map["email"])
        email = normalize_email(raw_email) if raw_email else ""
        full_name = (row.get(fieldnames_map["full_name"]) or "").strip()
        role_str = (row.get(fieldnames_map["role"]) or "").strip().lower()

        if not email or not full_name:
            row_reports.append(AdminUserBulkUploadDetail(row_number=idx, email=email or "UNKNOWN", status="rejected", reason="Email and full_name are mandatory"))
            rejected_count += 1
            continue

        if not EMAIL_REGEX.match(email):
            row_reports.append(AdminUserBulkUploadDetail(row_number=idx, email=email, status="rejected", reason=f"Invalid email format: '{email}'"))
            rejected_count += 1
            continue

        domain = email.split("@")[-1] if "@" in email else ""
        if domain not in settings.allowed_email_domain_list:
            row_reports.append(AdminUserBulkUploadDetail(row_number=idx, email=email, status="rejected", reason=f"Email domain '@{domain}' is not allowed"))
            rejected_count += 1
            continue

        try:
            role = UserRole(role_str)
        except ValueError:
            row_reports.append(AdminUserBulkUploadDetail(row_number=idx, email=email, status="rejected", reason=f"Invalid role: '{role_str}'"))
            rejected_count += 1
            continue

        if role not in (UserRole.dept_officer, UserRole.hod, UserRole.registrar_accounts):
            row_reports.append(AdminUserBulkUploadDetail(row_number=idx, email=email, status="rejected", reason="Bulk upload only supports staff roles (dept_officer, hod, registrar_accounts)"))
            rejected_count += 1
            continue

        matched_depts: list[Department] = []
        has_dept_error = False

        if "departments" in fieldnames_map and (row.get(fieldnames_map["departments"]) or "").strip():
            raw_depts = [part.strip() for part in (row.get(fieldnames_map["departments"]) or "").split("|") if part.strip()]
            for part in raw_depts:
                m_dept = dept_by_name.get(part.lower())
                if not m_dept and part.isdigit():
                    m_dept = dept_by_id.get(int(part))
                if not m_dept:
                    row_reports.append(AdminUserBulkUploadDetail(row_number=idx, email=email, status="rejected", reason=f"Department '{part}' not found"))
                    rejected_count += 1
                    has_dept_error = True
                    break
                matched_depts.append(m_dept)
        elif "department" in fieldnames_map and (row.get(fieldnames_map["department"]) or "").strip():
            dept_str = (row.get(fieldnames_map["department"]) or "").strip()
            m_dept = dept_by_name.get(dept_str.lower())
            if not m_dept and dept_str.isdigit():
                m_dept = dept_by_id.get(int(dept_str))
            if not m_dept:
                row_reports.append(AdminUserBulkUploadDetail(row_number=idx, email=email, status="rejected", reason=f"Department '{dept_str}' not found (mandatory for {role.value})"))
                rejected_count += 1
                has_dept_error = True
            else:
                matched_depts.append(m_dept)

        if has_dept_error:
            continue

        if role in (UserRole.dept_officer, UserRole.hod):
            if not matched_depts:
                row_reports.append(AdminUserBulkUploadDetail(row_number=idx, email=email, status="rejected", reason=f"Department is mandatory for {role.value}"))
                rejected_count += 1
                continue
            if role == UserRole.hod and any(d.kind != DepartmentKind.academic for d in matched_depts):
                row_reports.append(AdminUserBulkUploadDetail(row_number=idx, email=email, status="rejected", reason="HoD must belong to an academic department"))
                rejected_count += 1
                continue
        elif role == UserRole.registrar_accounts:
            rs_dept = db.execute(
                select(Department).where(func.lower(Department.name).in_(["r&s branch", "registration & scholarship branch"]))
            ).scalars().first()
            if matched_depts:
                if rs_dept and any(d.id != rs_dept.id for d in matched_depts):
                    row_reports.append(AdminUserBulkUploadDetail(row_number=idx, email=email, status="rejected", reason="registrar_accounts must belong to R&S Branch"))
                    rejected_count += 1
                    continue
            elif rs_dept:
                matched_depts = [rs_dept]

        # Check existing user
        exists_user = db.execute(select(User).where(func.lower(User.email) == email)).scalars().first()
        if exists_user:
            row_reports.append(AdminUserBulkUploadDetail(row_number=idx, email=email, status="rejected", reason=f"User with email '{email}' already exists"))
            rejected_count += 1
            continue

        # Check per-row or query-param google_only flag
        row_google_only = google_only
        if "google_only" in fieldnames_map:
            raw_go = (row.get(fieldnames_map["google_only"]) or "").strip().lower()
            if raw_go in ("true", "1", "yes"):
                row_google_only = True
            elif raw_go in ("false", "0", "no"):
                row_google_only = False

        if row_google_only:
            temp_password = None
            hashed_pw = None
            must_change = False
        else:
            temp_password = secrets.token_urlsafe(12)
            hashed_pw = hash_password(temp_password)
            must_change = True

        new_user = User(
            email=email,
            full_name=full_name,
            password_hash=hashed_pw,
            role=role,
            department_id=matched_depts[0].id if matched_depts else None,
            is_active=True,
            must_change_password=must_change,
        )
        db.add(new_user)
        db.flush()

        now = datetime.now(timezone.utc)
        for d in matched_depts:
            db.add(UserDepartment(
                user_id=new_user.id,
                department_id=d.id,
                created_at=now,
                created_by_user_id=current_user.id,
            ))

        # Audit log does NOT store temporary password
        _record_admin_audit(
            db,
            current_user.id,
            action="CREATE_USER_BULK",
            entity_type="users",
            entity_id=new_user.id,
            details={
                "email": new_user.email,
                "role": new_user.role.value,
                "department_id": new_user.department_id,
                "department_ids": [d.id for d in matched_depts],
            },
        )

        row_reports.append(
            AdminUserBulkUploadDetail(
                row_number=idx,
                email=email,
                status="created",
                temporary_password=temp_password,
            )
        )
        created_count += 1


    db.commit()

    return AdminUserBulkUploadResponse(
        total_rows=len(row_reports),
        created_count=created_count,
        rejected_count=rejected_count,
        rows=row_reports,
    )


# ---------------------------------------------------------------------------
# ADMIN LAB COURSES (Fallback endpoints)
# ---------------------------------------------------------------------------


def _format_admin_lab_item(c: LabCourse) -> LabCourseItem:
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


@router.get(
    "/lab-courses/template.csv",
    status_code=status.HTTP_200_OK,
    operation_id="admin_get_lab_courses_template_csv",
    summary="Download Lab Courses CSV Template (Admin)",
    description="Downloads a CSV template formatted for lab course catalog upload.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
    },
)
def admin_get_lab_courses_template(
    current_user: User = Depends(require_admin),
) -> Response:
    csv_content = (
        "code,name,academic_department,lab_office,specialization\r\n"
        "CSE-L101,Advanced Programming Lab,Skill Department of CS/IT,Computing Laboratory,Computer Engineering\r\n"
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
    operation_id="admin_list_lab_courses",
    summary="List University Lab Courses (Admin)",
    description="Returns all lab courses across all academic departments with optional department and active filters.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
    },
)
def admin_list_lab_courses(
    db: SessionDep,
    current_user: User = Depends(require_admin),
    academic_department_id: int | None = Query(None, description="Filter by academic department ID"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> LabCourseListResponse:
    query = (
        select(LabCourse)
        .options(joinedload(LabCourse.academic_department), joinedload(LabCourse.lab_department))
    )
    if academic_department_id is not None:
        query = query.where(LabCourse.academic_department_id == academic_department_id)
    if is_active is not None:
        query = query.where(LabCourse.is_active == is_active)

    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    courses = db.execute(
        query.order_by(LabCourse.code.asc()).offset(offset).limit(limit)
    ).unique().scalars().all()

    return LabCourseListResponse(
        total=total,
        items=[_format_admin_lab_item(c) for c in courses],
    )


@router.post(
    "/lab-courses",
    response_model=LabCourseItem,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_create_lab_course",
    summary="Create Lab Course (Admin)",
    description="Creates a new lab course mapped to an academic department and an ASSIGNED_ONLY service department.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid department or not ASSIGNED_ONLY"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        409: {"model": ErrorResponse, "description": "Lab course code already exists"},
    },
)
def admin_create_lab_course(
    body: LabCourseCreate,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> LabCourseItem:
    if not body.academic_department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="academic_department_id is required.",
        )
    acad_dept = db.get(Department, body.academic_department_id)
    if not acad_dept or acad_dept.kind != DepartmentKind.academic:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="academic_department_id must be a valid academic department.",
        )

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

    course = LabCourse(
        code=code_clean,
        name=body.name.strip(),
        academic_department_id=acad_dept.id,
        lab_department_id=lab_dept.id,
        specialization=body.specialization.strip() if body.specialization else None,
        is_active=True,
    )
    db.add(course)
    db.flush()

    _record_admin_audit(
        db,
        current_user.id,
        action="ADMIN_LAB_COURSE_CREATED",
        entity_type="LabCourse",
        entity_id=course.id,
        details={"code": course.code, "name": course.name},
    )
    db.commit()
    db.refresh(course)

    return _format_admin_lab_item(course)


@router.patch(
    "/lab-courses/{id}",
    response_model=LabCourseItem,
    status_code=status.HTTP_200_OK,
    operation_id="admin_patch_lab_course",
    summary="Update Lab Course (Admin)",
    description="Updates a lab course's code, name, lab department, specialization, or active status.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid lab department or applicability"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        404: {"model": ErrorResponse, "description": "Lab course not found"},
        409: {"model": ErrorResponse, "description": "Lab course code already exists"},
    },
)
def admin_patch_lab_course(
    id: int,
    body: LabCoursePatch,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> LabCourseItem:
    course = db.execute(
        select(LabCourse)
        .where(LabCourse.id == id)
        .options(joinedload(LabCourse.academic_department), joinedload(LabCourse.lab_department))
    ).scalars().first()

    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab course not found.")

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

    _record_admin_audit(
        db,
        current_user.id,
        action="ADMIN_LAB_COURSE_UPDATED",
        entity_type="LabCourse",
        entity_id=course.id,
        details={"code": course.code, "is_active": course.is_active},
    )
    db.commit()
    db.refresh(course)

    return _format_admin_lab_item(course)


@router.post(
    "/requests/{id}/cancel",
    response_model=CancelResponse,
    status_code=status.HTTP_200_OK,
    operation_id="admin_cancel_clearance_request",
    summary="Admin Cancel Clearance Request",
    description="Allows administrators to cancel an active clearance request with mandatory reason.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid state (already cleared/verified) or missing reason"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        404: {"model": ErrorResponse, "description": "Clearance request not found"},
    },
)
def admin_cancel_request(
    id: int,
    body: StaffCancelRequest,
    db: SessionDep,
    current_user: User = Depends(require_admin),
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
# ADMIN LAB COURSES UPLOAD
# ---------------------------------------------------------------------------


@router.post(
    "/lab-courses/upload",
    response_model=LabCourseUploadResponse,
    status_code=status.HTTP_200_OK,
    operation_id="admin_upload_lab_courses_csv",
    summary="Upload Lab Courses CSV (Admin)",
    description="Bulk uploads lab courses for any academic department with dry-run and auto-office creation support.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid CSV file structure"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
    },
)
async def admin_upload_lab_courses_csv(
    db: SessionDep,
    file: UploadFile = File(..., description="CSV file with lab courses"),
    dry_run: bool = Query(False, description="Simulate upload without persisting changes"),
    create_missing_offices: bool = Query(False, description="Create missing Lab/Workshop offices automatically"),
    current_user: User = Depends(require_admin),
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

    acad_depts = db.execute(
        select(Department).where(Department.kind == DepartmentKind.academic)
    ).scalars().all()
    acad_by_name = {d.name.strip().lower(): d for d in acad_depts}
    acad_by_id = {d.id: d for d in acad_depts}
    default_acad_id = acad_depts[0].id if acad_depts else None

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
        acad_str = (row.get(fieldnames_map.get("academic_department", "")) or "").strip()

        if not code or not name:
            row_reports.append(LabCourseUploadRowReport(row_number=idx, code=code or "UNKNOWN", status="rejected", reason="Code and name are mandatory"))
            rejected_count += 1
            continue

        if not lab_office_str:
            row_reports.append(LabCourseUploadRowReport(row_number=idx, code=code, status="rejected", reason="Lab office is mandatory"))
            rejected_count += 1
            continue

        target_acad_id = default_acad_id
        if acad_str:
            matched_acad = acad_by_name.get(acad_str.lower())
            if not matched_acad and acad_str.isdigit():
                matched_acad = acad_by_id.get(int(acad_str))
            if not matched_acad:
                row_reports.append(
                    LabCourseUploadRowReport(
                        row_number=idx,
                        code=code,
                        status="rejected",
                        reason=f"Academic department '{acad_str}' not found",
                    )
                )
                rejected_count += 1
                continue
            target_acad_id = matched_acad.id

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
                _record_admin_audit(
                    db,
                    current_user.id,
                    action="ADMIN_DEPARTMENT_CREATED",
                    entity_type="Department",
                    entity_id=new_office.id,
                    details={"name": new_office.name, "category": "LAB_WORKSHOP", "source": "admin_lab_upload"},
                )
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
                if target_acad_id:
                    existing.academic_department_id = target_acad_id
                existing.specialization = specialization
                existing.is_active = True

            row_reports.append(LabCourseUploadRowReport(row_number=idx, code=code, status=status_text))
            updated_count += 1
        else:
            if not dry_run:
                new_course = LabCourse(
                    code=code,
                    name=name,
                    academic_department_id=target_acad_id,
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
        _record_admin_audit(
            db,
            current_user.id,
            action="ADMIN_LAB_COURSES_UPLOADED",
            entity_type="LabCourse",
            entity_id=None,
            details={
                "total_rows": len(row_reports),
                "created": created_count,
                "updated": updated_count,
                "rejected": rejected_count,
                "offices_created": offices_to_create,
            },
        )
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


# ---------------------------------------------------------------------------
# ADMIN DEPARTMENT & OFFICE MANAGEMENT
# ---------------------------------------------------------------------------


@router.get(
    "/departments",
    response_model=AdminDepartmentListResponse,
    status_code=status.HTTP_200_OK,
    operation_id="admin_list_departments",
    summary="List Departments with Management Metrics",
    description="Lists university departments with category, label, active status, staffing and approval metrics.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
    },
)
def admin_list_departments(
    db: SessionDep,
    current_user: User = Depends(require_admin),
    category: str | None = Query(None, description="Filter by category: ACADEMIC, UNIVERSITY_OFFICE, HOSTEL, LAB_WORKSHOP, ADDITIONAL_FACILITY"),
    is_active: bool | None = Query(None, description="Filter by is_active status"),
    search: str | None = Query(None, description="Search by department name"),
) -> AdminDepartmentListResponse:
    query = select(Department).order_by(Department.name.asc())
    if is_active is not None:
        query = query.where(Department.is_active == is_active)
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        query = query.where(func.lower(Department.name).like(term))

    depts = db.execute(query).scalars().all()
    if category:
        depts = [d for d in depts if d.category == category.upper()]

    all_open_approvals = db.execute(
        select(DepartmentApproval.department_id, func.count(DepartmentApproval.id))
        .join(ClearanceRequest, DepartmentApproval.request_id == ClearanceRequest.id)
        .where(
            ClearanceRequest.status.not_in([
                ClearanceStatus.CLEARED,
                ClearanceStatus.REFUND_VERIFIED,
                ClearanceStatus.CANCELLED,
            ])
        )
        .group_by(DepartmentApproval.department_id)
    ).all()
    open_approvals_map = dict(all_open_approvals)

    all_subjects = db.execute(
        select(LabCourse.lab_department_id, func.count(LabCourse.id))
        .group_by(LabCourse.lab_department_id)
    ).all()
    subject_map = dict(all_subjects)

    items = []
    for d in depts:
        officers = active_officers_for(db, d.id)
        officer_count = len(officers)
        hod = active_hod_for(db, d.id) if d.kind == DepartmentKind.academic else None
        missing_officer = (officer_count == 0)
        missing_hod = (d.kind == DepartmentKind.academic and hod is None)
        sub_count = subject_map.get(d.id, 0)
        open_app_count = open_approvals_map.get(d.id, 0)

        items.append(
            AdminDepartmentListItem(
                id=d.id,
                name=d.name,
                kind=d.kind.value,
                applicability=d.applicability.value,
                description=d.description,
                category=d.category,
                label=d.category_label,
                is_active=d.is_active,
                officer_count=officer_count,
                subject_count=sub_count,
                open_approvals_count=open_app_count,
                missing_officer=missing_officer,
                missing_hod=missing_hod,
            )
        )
    return AdminDepartmentListResponse(total=len(items), items=items)


@router.post(
    "/departments",
    response_model=AdminDepartmentListItem,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_create_department",
    summary="Create University Service Department",
    description="Creates a service department under one of: UNIVERSITY_OFFICE, HOSTEL, LAB_WORKSHOP, ADDITIONAL_FACILITY.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid category or name length"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        409: {"model": ErrorResponse, "description": "Department name already exists"},
    },
)
def admin_create_department(
    body: AdminCreateDepartmentRequest,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> AdminDepartmentListItem:
    cat = body.category.upper().strip()
    valid_categories = {
        "UNIVERSITY_OFFICE": DepartmentApplicability.ALWAYS,
        "HOSTEL": DepartmentApplicability.HOSTELLER_ONLY,
        "LAB_WORKSHOP": DepartmentApplicability.LAB_WORKSHOP,
        "ADDITIONAL_FACILITY": DepartmentApplicability.ASSIGNED_ONLY,
    }
    if cat not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category '{body.category}'. Allowed categories: {', '.join(valid_categories.keys())}",
        )

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
        applicability=valid_categories[cat],
        description=body.description.strip() if body.description else None,
        is_active=True,
        created_by_user_id=current_user.id,
    )
    db.add(dept)
    db.flush()

    _record_admin_audit(
        db,
        current_user.id,
        action="ADMIN_DEPARTMENT_CREATED",
        entity_type="Department",
        entity_id=dept.id,
        details={"name": dept.name, "category": cat},
    )
    db.commit()
    db.refresh(dept)

    return AdminDepartmentListItem(
        id=dept.id,
        name=dept.name,
        kind=dept.kind.value,
        applicability=dept.applicability.value,
        description=dept.description,
        category=dept.category,
        label=dept.category_label,
        is_active=dept.is_active,
        officer_count=0,
        subject_count=0,
        open_approvals_count=0,
        missing_officer=True,
        missing_hod=False,
    )


@router.patch(
    "/departments/{id}",
    response_model=AdminDepartmentListItem,
    status_code=status.HTTP_200_OK,
    operation_id="admin_patch_department",
    summary="Update Department Details and Active Status",
    description="Updates department name, description, category, or active status with safety guards against open clearance approvals.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input or missing confirmation for core office deactivation"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        404: {"model": ErrorResponse, "description": "Department not found"},
        409: {"model": ErrorResponse, "description": "Open approvals on active requests or name clash"},
    },
)
def admin_patch_department(
    id: int,
    body: AdminUpdateDepartmentRequest,
    db: SessionDep,
    confirm: bool = Query(False, description="Confirmation required when deactivating core university offices"),
    current_user: User = Depends(require_admin),
) -> AdminDepartmentListItem:
    dept = db.get(Department, id)
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found.")

    valid_categories = {
        "UNIVERSITY_OFFICE": DepartmentApplicability.ALWAYS,
        "HOSTEL": DepartmentApplicability.HOSTELLER_ONLY,
        "LAB_WORKSHOP": DepartmentApplicability.LAB_WORKSHOP,
        "ADDITIONAL_FACILITY": DepartmentApplicability.ASSIGNED_ONLY,
    }

    target_cat = body.category.upper().strip() if body.category else None
    if target_cat and target_cat not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category '{body.category}'. Allowed categories: {', '.join(valid_categories.keys())}",
        )

    is_deactivating = (body.is_active is False and dept.is_active is True)
    is_changing_cat = (target_cat is not None and target_cat != dept.category)

    if is_deactivating or is_changing_cat:
        open_count = db.execute(
            select(func.count(DepartmentApproval.id))
            .join(ClearanceRequest, DepartmentApproval.request_id == ClearanceRequest.id)
            .where(
                DepartmentApproval.department_id == dept.id,
                ClearanceRequest.status.not_in([
                    ClearanceStatus.CLEARED,
                    ClearanceStatus.REFUND_VERIFIED,
                    ClearanceStatus.CANCELLED,
                ]),
            )
        ).scalar() or 0
        if open_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot modify office '{dept.name}': it has {open_count} open approvals on active clearance requests.",
            )

    if is_deactivating and dept.applicability in (DepartmentApplicability.ALWAYS, DepartmentApplicability.HOSTELLER_ONLY):
        if not (confirm or body.confirm):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Deactivating core office '{dept.name}' ({dept.label}) requires explicit confirmation. Set confirm=true to proceed.",
            )

    if body.name is not None:
        clean_name = body.name.strip()
        if len(clean_name) < 3 or len(clean_name) > 80:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department name must be between 3 and 80 characters.",
            )
        if clean_name.lower() != dept.name.lower():
            clash = db.execute(
                select(Department).where(func.lower(Department.name) == clean_name.lower(), Department.id != dept.id)
            ).scalars().first()
            if clash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Department '{clean_name}' already exists.",
                )
            dept.name = clean_name

    if body.description is not None:
        dept.description = body.description.strip() if body.description else None

    if target_cat:
        dept.applicability = valid_categories[target_cat]
        dept.kind = DepartmentKind.service

    if body.is_active is not None:
        dept.is_active = body.is_active

    _record_admin_audit(
        db,
        current_user.id,
        action="ADMIN_DEPARTMENT_UPDATED",
        entity_type="Department",
        entity_id=dept.id,
        details={
            "name": dept.name,
            "category": dept.category,
            "is_active": dept.is_active,
        },
    )
    db.commit()
    db.refresh(dept)

    officers = active_officers_for(db, dept.id)
    sub_count = db.execute(
        select(func.count(LabCourse.id)).where(LabCourse.lab_department_id == dept.id)
    ).scalar() or 0
    open_count = db.execute(
        select(func.count(DepartmentApproval.id))
        .join(ClearanceRequest, DepartmentApproval.request_id == ClearanceRequest.id)
        .where(
            DepartmentApproval.department_id == dept.id,
            ClearanceRequest.status.not_in([
                ClearanceStatus.CLEARED,
                ClearanceStatus.REFUND_VERIFIED,
                ClearanceStatus.CANCELLED,
            ]),
        )
    ).scalar() or 0

    return AdminDepartmentListItem(
        id=dept.id,
        name=dept.name,
        kind=dept.kind.value,
        applicability=dept.applicability.value,
        description=dept.description,
        category=dept.category,
        label=dept.category_label,
        is_active=dept.is_active,
        officer_count=len(officers),
        subject_count=sub_count,
        open_approvals_count=open_count,
        missing_officer=(len(officers) == 0),
        missing_hod=False,
    )


@router.delete(
    "/departments/{id}",
    status_code=status.HTTP_200_OK,
    operation_id="admin_delete_department",
    summary="Delete Department",
    description="Deletes a department only if no records (approvals, lab courses, memberships, roster overrides, programmes) refer to it.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        404: {"model": ErrorResponse, "description": "Department not found"},
        409: {"model": ErrorResponse, "description": "Department has referencing records; deactivate it instead"},
    },
)
def admin_delete_department(
    id: int,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> dict:
    dept = db.get(Department, id)
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found.")

    app_count = db.execute(select(func.count(DepartmentApproval.id)).where(DepartmentApproval.department_id == dept.id)).scalar() or 0
    lc_count = db.execute(select(func.count(LabCourse.id)).where(or_(LabCourse.lab_department_id == dept.id, LabCourse.academic_department_id == dept.id))).scalar() or 0
    mem_count = db.execute(select(func.count(UserDepartment.department_id)).where(UserDepartment.department_id == dept.id)).scalar() or 0
    u_count = db.execute(select(func.count(User.id)).where(User.department_id == dept.id)).scalar() or 0
    roster_overrides = db.execute(select(func.count(RosterAssignedDepartment.department_id)).where(RosterAssignedDepartment.department_id == dept.id)).scalar() or 0
    prog_count = db.execute(select(func.count(Programme.id)).where(Programme.academic_department_id == dept.id)).scalar() or 0

    total_refs = app_count + lc_count + mem_count + u_count + roster_overrides + prog_count
    if total_refs > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete department because existing records refer to it. Deactivate it instead.",
        )

    dept_name = dept.name
    _record_admin_audit(
        db,
        current_user.id,
        action="ADMIN_DEPARTMENT_DELETED",
        entity_type="Department",
        entity_id=dept.id,
        details={"name": dept_name},
    )
    db.delete(dept)
    db.commit()

    return {"detail": f"Department '{dept_name}' successfully deleted."}


@router.post(
    "/departments/bulk-category",
    response_model=BulkCategoryResponse,
    status_code=status.HTTP_200_OK,
    operation_id="admin_bulk_department_category",
    summary="Bulk Update Department Categories",
    description="Bulk updates categories for multiple departments. Refused with 409 if any department has open clearance approvals.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid category"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        409: {"model": ErrorResponse, "description": "Department has open approvals on active requests"},
    },
)
def admin_bulk_department_category(
    body: BulkCategoryRequest,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> BulkCategoryResponse:
    target_cat = body.category.upper().strip()
    valid_categories = {
        "UNIVERSITY_OFFICE": DepartmentApplicability.ALWAYS,
        "HOSTEL": DepartmentApplicability.HOSTELLER_ONLY,
        "LAB_WORKSHOP": DepartmentApplicability.LAB_WORKSHOP,
        "ADDITIONAL_FACILITY": DepartmentApplicability.ASSIGNED_ONLY,
    }
    if target_cat not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category '{body.category}'. Allowed categories: {', '.join(valid_categories.keys())}",
        )

    depts = db.execute(
        select(Department).where(Department.id.in_(body.department_ids))
    ).scalars().all()

    for d in depts:
        if d.category != target_cat:
            open_count = db.execute(
                select(func.count(DepartmentApproval.id))
                .join(ClearanceRequest, DepartmentApproval.request_id == ClearanceRequest.id)
                .where(
                    DepartmentApproval.department_id == d.id,
                    ClearanceRequest.status.not_in([
                        ClearanceStatus.CLEARED,
                        ClearanceStatus.REFUND_VERIFIED,
                        ClearanceStatus.CANCELLED,
                    ]),
                )
            ).scalar() or 0
            if open_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot change category for department '{d.name}': it has {open_count} open approvals on active requests.",
                )

    for d in depts:
        d.applicability = valid_categories[target_cat]
        d.kind = DepartmentKind.service

    _record_admin_audit(
        db,
        current_user.id,
        action="ADMIN_DEPARTMENTS_BULK_CATEGORY_UPDATED",
        entity_type="Department",
        entity_id=None,
        details={"department_ids": body.department_ids, "category": target_cat},
    )
    db.commit()

    return BulkCategoryResponse(
        updated_count=len(depts),
        detail=f"Successfully updated {len(depts)} departments to category {target_cat}.",
    )


# ---------------------------------------------------------------------------
# ACADEMIC STRUCTURE MANAGEMENT (Faculties, Departments, Programmes)
# ---------------------------------------------------------------------------


@router.get(
    "/faculties",
    response_model=list[FacultyResponse],
    status_code=status.HTTP_200_OK,
    operation_id="admin_list_faculties",
    summary="List University Faculties",
    description="Returns all faculties with department counts.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
    },
)
def admin_list_faculties(
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> list[FacultyResponse]:
    faculties = db.execute(select(Faculty).order_by(Faculty.name.asc())).scalars().all()
    dept_counts = dict(
        db.execute(
            select(Department.faculty_id, func.count(Department.id))
            .where(Department.faculty_id.isnot(None))
            .group_by(Department.faculty_id)
        ).all()
    )
    return [
        FacultyResponse(
            id=f.id,
            name=f.name,
            short_code=f.short_code,
            department_count=dept_counts.get(f.id, 0),
        )
        for f in faculties
    ]


@router.post(
    "/faculties",
    response_model=FacultyResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_create_faculty",
    summary="Create Faculty",
    description="Creates a new university faculty.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid format"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        409: {"model": ErrorResponse, "description": "Faculty name or short code already exists"},
    },
)
def admin_create_faculty(
    body: FacultyCreate,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> FacultyResponse:
    clean_name = body.name.strip()
    clean_code = body.short_code.strip().upper()

    clash = db.execute(
        select(Faculty).where(
            or_(
                func.lower(Faculty.name) == clean_name.lower(),
                func.upper(Faculty.short_code) == clean_code,
            )
        )
    ).scalars().first()
    if clash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Faculty with name '{clean_name}' or short code '{clean_code}' already exists.",
        )

    faculty = Faculty(name=clean_name, short_code=clean_code)
    db.add(faculty)
    db.flush()

    _record_admin_audit(
        db,
        current_user.id,
        action="ADMIN_FACULTY_CREATED",
        entity_type="Faculty",
        entity_id=faculty.id,
        details={"name": faculty.name, "short_code": faculty.short_code},
    )
    db.commit()
    db.refresh(faculty)

    return FacultyResponse(id=faculty.id, name=faculty.name, short_code=faculty.short_code, department_count=0)


@router.patch(
    "/faculties/{id}",
    response_model=FacultyResponse,
    status_code=status.HTTP_200_OK,
    operation_id="admin_patch_faculty",
    summary="Update Faculty",
    description="Updates faculty name or short code.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid format"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        404: {"model": ErrorResponse, "description": "Faculty not found"},
        409: {"model": ErrorResponse, "description": "Name or short code conflict"},
    },
)
def admin_patch_faculty(
    id: int,
    body: FacultyUpdate,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> FacultyResponse:
    faculty = db.get(Faculty, id)
    if not faculty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty not found.")

    if body.name is not None:
        clean_name = body.name.strip()
        clash = db.execute(
            select(Faculty).where(func.lower(Faculty.name) == clean_name.lower(), Faculty.id != id)
        ).scalars().first()
        if clash:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Faculty name '{clean_name}' already exists.")
        faculty.name = clean_name

    if body.short_code is not None:
        clean_code = body.short_code.strip().upper()
        clash = db.execute(
            select(Faculty).where(func.upper(Faculty.short_code) == clean_code, Faculty.id != id)
        ).scalars().first()
        if clash:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Faculty short code '{clean_code}' already exists.")
        faculty.short_code = clean_code

    _record_admin_audit(
        db,
        current_user.id,
        action="ADMIN_FACULTY_UPDATED",
        entity_type="Faculty",
        entity_id=faculty.id,
        details={"name": faculty.name, "short_code": faculty.short_code},
    )
    db.commit()
    db.refresh(faculty)

    dept_count = db.execute(
        select(func.count(Department.id)).where(Department.faculty_id == faculty.id)
    ).scalar() or 0

    return FacultyResponse(id=faculty.id, name=faculty.name, short_code=faculty.short_code, department_count=dept_count)


@router.get(
    "/academic-departments",
    response_model=list[AcademicDepartmentResponse],
    status_code=status.HTTP_200_OK,
    operation_id="admin_list_academic_departments",
    summary="List Academic Departments",
    description="Returns all academic departments with programme and student metrics.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
    },
)
def admin_list_academic_departments(
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> list[AcademicDepartmentResponse]:
    depts = db.execute(
        select(Department)
        .where(Department.kind == DepartmentKind.academic)
        .options(joinedload(Department.faculty))
        .order_by(Department.name.asc())
    ).scalars().all()

    prog_counts = dict(
        db.execute(
            select(Programme.academic_department_id, func.count(Programme.id))
            .group_by(Programme.academic_department_id)
        ).all()
    )

    student_counts = dict(
        db.execute(
            select(Programme.academic_department_id, func.count(StudentRoster.id))
            .join(StudentRoster, StudentRoster.programme_id == Programme.id)
            .group_by(Programme.academic_department_id)
        ).all()
    )

    return [
        AcademicDepartmentResponse(
            id=d.id,
            name=d.name,
            faculty_id=d.faculty_id,
            faculty_name=d.faculty.name if d.faculty else None,
            is_active=d.is_active,
            category="ACADEMIC",
            label="Academic department",
            programme_count=prog_counts.get(d.id, 0),
            student_count=student_counts.get(d.id, 0),
        )
        for d in depts
    ]


@router.post(
    "/academic-departments",
    response_model=AcademicDepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_create_academic_department",
    summary="Create Academic Department",
    description="Creates a new academic department bound to a faculty.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input or faculty not found"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        409: {"model": ErrorResponse, "description": "Department name already exists"},
    },
)
def admin_create_academic_department(
    body: AcademicDepartmentCreate,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> AcademicDepartmentResponse:
    faculty = db.get(Faculty, body.faculty_id)
    if not faculty:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Faculty ID {body.faculty_id} not found.")

    clean_name = body.name.strip()
    clash = db.execute(
        select(Department).where(func.lower(Department.name) == clean_name.lower())
    ).scalars().first()
    if clash:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Department '{clean_name}' already exists.")

    dept = Department(
        name=clean_name,
        kind=DepartmentKind.academic,
        applicability=DepartmentApplicability.OWN_ACADEMIC,
        faculty_id=faculty.id,
        is_active=body.is_active,
        created_by_user_id=current_user.id,
    )
    db.add(dept)
    db.flush()

    _record_admin_audit(
        db,
        current_user.id,
        action="ADMIN_ACADEMIC_DEPARTMENT_CREATED",
        entity_type="Department",
        entity_id=dept.id,
        details={"name": dept.name, "faculty_id": faculty.id},
    )
    db.commit()
    db.refresh(dept)

    return AcademicDepartmentResponse(
        id=dept.id,
        name=dept.name,
        faculty_id=dept.faculty_id,
        faculty_name=faculty.name,
        is_active=dept.is_active,
        category="ACADEMIC",
        label="Academic department",
        programme_count=0,
        student_count=0,
    )


@router.patch(
    "/academic-departments/{id}",
    response_model=AcademicDepartmentResponse,
    status_code=status.HTTP_200_OK,
    operation_id="admin_patch_academic_department",
    summary="Update Academic Department",
    description="Updates academic department name, faculty, or active status with safety guards against active students.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input or faculty not found"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        404: {"model": ErrorResponse, "description": "Department not found"},
        409: {"model": ErrorResponse, "description": "Deactivation refused while students or open requests exist, or name clash"},
    },
)
def admin_patch_academic_department(
    id: int,
    body: AcademicDepartmentUpdate,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> AcademicDepartmentResponse:
    dept = db.get(Department, id)
    if not dept or dept.kind != DepartmentKind.academic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic department not found.")

    if body.is_active is False and dept.is_active is True:
        open_reqs = db.execute(
            select(func.count(ClearanceRequest.id))
            .join(StudentRoster, ClearanceRequest.roster_id == StudentRoster.id)
            .join(Programme, StudentRoster.programme_id == Programme.id)
            .where(
                Programme.academic_department_id == dept.id,
                ClearanceRequest.status.not_in([
                    ClearanceStatus.CLEARED,
                    ClearanceStatus.REFUND_VERIFIED,
                    ClearanceStatus.CANCELLED,
                ]),
            )
        ).scalar() or 0
        if open_reqs > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot deactivate academic department '{dept.name}': it has {open_reqs} open clearance requests.",
            )

        active_students = db.execute(
            select(func.count(StudentRoster.id))
            .join(Programme, StudentRoster.programme_id == Programme.id)
            .join(User, StudentRoster.id == User.roster_id)
            .where(
                Programme.academic_department_id == dept.id,
                User.is_active == True,
            )
        ).scalar() or 0
        if active_students > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot deactivate academic department '{dept.name}': it has {active_students} active student accounts.",
            )
        dept.is_active = False
    elif body.is_active is True:
        dept.is_active = True

    if body.name is not None:
        clean_name = body.name.strip()
        clash = db.execute(
            select(Department).where(func.lower(Department.name) == clean_name.lower(), Department.id != id)
        ).scalars().first()
        if clash:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Department '{clean_name}' already exists.")
        dept.name = clean_name

    if body.faculty_id is not None:
        faculty = db.get(Faculty, body.faculty_id)
        if not faculty:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Faculty ID {body.faculty_id} not found.")
        dept.faculty_id = faculty.id

    _record_admin_audit(
        db,
        current_user.id,
        action="ADMIN_ACADEMIC_DEPARTMENT_UPDATED",
        entity_type="Department",
        entity_id=dept.id,
        details={"name": dept.name, "is_active": dept.is_active},
    )
    db.commit()
    db.refresh(dept)

    prog_count = db.execute(
        select(func.count(Programme.id)).where(Programme.academic_department_id == dept.id)
    ).scalar() or 0
    student_count = db.execute(
        select(func.count(StudentRoster.id))
        .join(Programme, StudentRoster.programme_id == Programme.id)
        .where(Programme.academic_department_id == dept.id)
    ).scalar() or 0

    return AcademicDepartmentResponse(
        id=dept.id,
        name=dept.name,
        faculty_id=dept.faculty_id,
        faculty_name=dept.faculty.name if dept.faculty else None,
        is_active=dept.is_active,
        category="ACADEMIC",
        label="Academic department",
        programme_count=prog_count,
        student_count=student_count,
    )


@router.get(
    "/programmes",
    response_model=list[ProgrammeResponse],
    status_code=status.HTTP_200_OK,
    operation_id="admin_list_programmes",
    summary="List Programmes (Admin)",
    description="Returns all programmes with academic department, faculty, and student counts.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
    },
)
def admin_list_programmes(
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> list[ProgrammeResponse]:
    progs = db.execute(
        select(Programme)
        .options(joinedload(Programme.department).joinedload(Department.faculty))
        .order_by(Programme.name.asc())
    ).scalars().all()

    student_counts = dict(
        db.execute(
            select(StudentRoster.programme_id, func.count(StudentRoster.id))
            .group_by(StudentRoster.programme_id)
        ).all()
    )

    return [
        ProgrammeResponse(
            id=p.id,
            name=p.name,
            academic_department_id=p.academic_department_id,
            academic_department_name=p.department.name if p.department else None,
            faculty_id=p.department.faculty_id if p.department else None,
            faculty_name=p.department.faculty.name if (p.department and p.department.faculty) else None,
            is_active=p.is_active,
            student_count=student_counts.get(p.id, 0),
        )
        for p in progs
    ]


@router.post(
    "/programmes",
    response_model=ProgrammeResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_create_programme",
    summary="Create Programme",
    description="Creates a new academic programme under an academic department.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input or department not academic"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        409: {"model": ErrorResponse, "description": "Programme name already exists"},
    },
)
def admin_create_programme(
    body: ProgrammeCreate,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> ProgrammeResponse:
    dept = db.get(Department, body.academic_department_id)
    if not dept or dept.kind != DepartmentKind.academic:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department ID {body.academic_department_id} is not a valid academic department.",
        )

    clean_name = body.name.strip()
    clash = db.execute(
        select(Programme).where(func.lower(Programme.name) == clean_name.lower())
    ).scalars().first()
    if clash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Programme '{clean_name}' already exists.",
        )

    prog = Programme(
        name=clean_name,
        academic_department_id=dept.id,
        is_active=body.is_active,
    )
    db.add(prog)
    db.flush()

    _record_admin_audit(
        db,
        current_user.id,
        action="ADMIN_PROGRAMME_CREATED",
        entity_type="Programme",
        entity_id=prog.id,
        details={"name": prog.name, "academic_department_id": dept.id},
    )
    db.commit()
    db.refresh(prog)

    return ProgrammeResponse(
        id=prog.id,
        name=prog.name,
        academic_department_id=dept.id,
        academic_department_name=dept.name,
        faculty_id=dept.faculty_id,
        faculty_name=dept.faculty.name if dept.faculty else None,
        is_active=prog.is_active,
        student_count=0,
    )


@router.patch(
    "/programmes/{id}",
    response_model=ProgrammeResponse,
    status_code=status.HTTP_200_OK,
    operation_id="admin_patch_programme",
    summary="Update Programme",
    description="Updates programme name, academic department, or active status with safety guards against active students.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input or department not academic"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        404: {"model": ErrorResponse, "description": "Programme not found"},
        409: {"model": ErrorResponse, "description": "Moving programme with roster entries refused, or deactivating with active students"},
    },
)
def admin_patch_programme(
    id: int,
    body: ProgrammeUpdate,
    db: SessionDep,
    current_user: User = Depends(require_admin),
) -> ProgrammeResponse:
    prog = db.get(Programme, id)
    if not prog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programme not found.")

    if body.academic_department_id is not None and body.academic_department_id != prog.academic_department_id:
        roster_count = db.execute(
            select(func.count(StudentRoster.id)).where(StudentRoster.programme_id == prog.id)
        ).scalar() or 0
        if roster_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot move programme '{prog.name}' to another academic department: it has {roster_count} student roster entries.",
            )

        target_dept = db.get(Department, body.academic_department_id)
        if not target_dept or target_dept.kind != DepartmentKind.academic:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department ID {body.academic_department_id} is not a valid academic department.",
            )
        prog.academic_department_id = target_dept.id

    if body.is_active is False and prog.is_active is True:
        open_reqs = db.execute(
            select(func.count(ClearanceRequest.id))
            .join(StudentRoster, ClearanceRequest.roster_id == StudentRoster.id)
            .where(
                StudentRoster.programme_id == prog.id,
                ClearanceRequest.status.not_in([
                    ClearanceStatus.CLEARED,
                    ClearanceStatus.REFUND_VERIFIED,
                    ClearanceStatus.CANCELLED,
                ]),
            )
        ).scalar() or 0
        if open_reqs > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot deactivate programme '{prog.name}': it has {open_reqs} open clearance requests.",
            )

        active_students = db.execute(
            select(func.count(StudentRoster.id))
            .join(User, StudentRoster.id == User.roster_id)
            .where(
                StudentRoster.programme_id == prog.id,
                User.is_active == True,
            )
        ).scalar() or 0
        if active_students > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot deactivate programme '{prog.name}': it has {active_students} active student accounts.",
            )
        prog.is_active = False
    elif body.is_active is True:
        prog.is_active = True

    if body.name is not None:
        clean_name = body.name.strip()
        clash = db.execute(
            select(Programme).where(func.lower(Programme.name) == clean_name.lower(), Programme.id != id)
        ).scalars().first()
        if clash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Programme '{clean_name}' already exists.",
            )
        prog.name = clean_name

    _record_admin_audit(
        db,
        current_user.id,
        action="ADMIN_PROGRAMME_UPDATED",
        entity_type="Programme",
        entity_id=prog.id,
        details={"name": prog.name, "is_active": prog.is_active},
    )
    db.commit()
    db.refresh(prog)

    student_count = db.execute(
        select(func.count(StudentRoster.id)).where(StudentRoster.programme_id == prog.id)
    ).scalar() or 0

    dept = prog.department
    return ProgrammeResponse(
        id=prog.id,
        name=prog.name,
        academic_department_id=prog.academic_department_id,
        academic_department_name=dept.name if dept else None,
        faculty_id=dept.faculty_id if dept else None,
        faculty_name=dept.faculty.name if (dept and dept.faculty) else None,
        is_active=prog.is_active,
        student_count=student_count,
    )



