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
from backend.app.models.university import Department, Programme, DepartmentKind, DepartmentApplicability
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


def _format_roster_item(r: StudentRoster) -> RosterItem:
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
    )


@router.post(
    "/roster/upload",
    response_model=RosterUploadResponse,
    status_code=status.HTTP_200_OK,
    operation_id="upload_roster_csv",
    summary="Upload Student Roster CSV",
    description=(
        "Uploads a CSV file containing student roster records. Validates each row: non-empty credentials, "
        "valid email format, known programme name, valid hosteller flag, and non-negative deposit. "
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
        "address", "programme", "is_hosteller", "security_deposit_amount"
    ]
    for col in required_cols:
        if col not in fieldnames_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required CSV column '{col}'. Required columns: {', '.join(required_cols)}",
            )

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
        deposit_str = (row.get(fieldnames_map["security_deposit_amount"]) or "").strip()

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

        try:
            deposit_amt = Decimal(deposit_str) if deposit_str else Decimal("0.00")
            if deposit_amt < 0:
                raise ValueError("Negative deposit")
        except (InvalidOperation, ValueError):
            row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="rejected", reason="Security deposit amount cannot be negative or invalid number"))
            rejected_count += 1
            continue

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
            existing.security_deposit_amount = deposit_amt
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
                security_deposit_amount=deposit_amt,
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

    return RosterUploadResponse(
        total_rows=total_rows,
        created_count=created_count,
        updated_count=updated_count,
        rejected_count=rejected_count,
        rows=row_reports,
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
    description="Updates hosteller status, security deposit amount, address, or mobile for a roster record.",
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

    changes = {}
    if body.is_hosteller is not None:
        changes["is_hosteller"] = body.is_hosteller
        roster.is_hosteller = body.is_hosteller

    if body.security_deposit_amount is not None:
        if body.security_deposit_amount < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Security deposit cannot be negative")
        changes["security_deposit_amount"] = str(body.security_deposit_amount)
        roster.security_deposit_amount = body.security_deposit_amount

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

    return _format_roster_item(roster)


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
        "CSE-L101,Advanced Programming Lab,Skill Department of CS/IT,Lab-1,Computer Engineering\r\n"
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
    if not lab_dept or lab_dept.applicability != DepartmentApplicability.ASSIGNED_ONLY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assigned lab office must be a service department with ASSIGNED_ONLY applicability.",
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
    description="Updates a lab course's name, specialization, or active status.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-admin roles"},
        404: {"model": ErrorResponse, "description": "Lab course not found"},
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

    if body.name is not None:
        course.name = body.name.strip()
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


