"""Administrator management endpoints: Roster upload, staff provisioning, and password resets."""
import codecs
import csv
import io
import re
import secrets
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select, func, or_, delete
from sqlalchemy.orm import joinedload

from backend.app.api.deps import SessionDep, require_roles
from backend.app.core.security import hash_password
from backend.app.models.user import User, UserRole
from backend.app.models.roster import StudentRoster, RosterAssignedDepartment
from backend.app.models.university import Department, Programme, DepartmentKind
from backend.app.models.audit import AuditLog
from backend.app.schemas.common import ErrorResponse
from backend.app.schemas.admin import (
    RosterUploadResponse,
    RosterUploadRowReport,
    RosterListResponse,
    RosterItem,
    RosterUpdateRequest,
    RosterAssignedDepartmentsRequest,
    AdminCreateUserRequest,
    AdminUserResponse,
    AdminResetPasswordResponse,
    AdminUserActiveRequest,
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
        email = (row.get(fieldnames_map["email"]) or "").strip().lower()
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
            existing.name = name
            existing.email = email
            existing.mobile = mobile
            existing.address = address
            existing.programme_id = prog_id
            existing.is_hosteller = is_hosteller
            existing.security_deposit_amount = deposit_amt
            row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="updated"))
            updated_count += 1
        else:
            # Check email uniqueness against existing roster
            email_clash = db.execute(
                select(StudentRoster).where(StudentRoster.email == email)
            ).scalars().first()
            if email_clash:
                row_reports.append(RosterUploadRowReport(row_number=idx, registration_number=reg_num, status="rejected", reason=f"Email '{email}' is already registered to another student ({email_clash.registration_number})"))
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

    # Check email conflict
    email_clean = body.email.strip().lower()
    existing_user = db.execute(
        select(User).where(func.lower(User.email) == email_clean)
    ).scalars().first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"User with email '{email_clean}' already exists")

    # Department validation
    dept = None
    if body.role in (UserRole.dept_officer, UserRole.hod):
        if not body.department_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department ID is mandatory for role '{body.role.value}'",
            )
        dept = db.get(Department, body.department_id)
        if not dept:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Department ID {body.department_id} not found")

        if body.role == UserRole.hod and dept.kind != DepartmentKind.academic:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Chairperson (HoD) user must belong to an academic department. '{dept.name}' is a service department.",
            )
    elif body.department_id:
        dept = db.get(Department, body.department_id)
        if not dept:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Department ID {body.department_id} not found")

    # Generate one-time temporary password (never log this!)
    temp_password = secrets.token_urlsafe(12)
    pw_hash = hash_password(temp_password)
    now = datetime.now(timezone.utc)

    user = User(
        email=email_clean,
        full_name=body.full_name.strip(),
        password_hash=pw_hash,
        role=body.role,
        department_id=body.department_id,
        roster_id=None,
        is_active=True,
        created_at=now,
    )
    db.add(user)
    db.flush()

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
        },
    )
    db.commit()
    db.refresh(user)

    return AdminUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        department_id=user.department_id,
        department_name=dept.name if dept else None,
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

    temp_password = secrets.token_urlsafe(12)
    user.password_hash = hash_password(temp_password)

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
