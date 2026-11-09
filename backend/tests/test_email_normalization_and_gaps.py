"""
Comprehensive tests for:
1. Email normalization, case-insensitive uniqueness, and credential synchronization (Part A).
2. Workflow bug fixes and endpoint gaps: HoD detail, registrar queue filter, department search,
   /departments listing, /admin/users directory, and decided_by_name tracking (Part B).
"""
import io
import pytest
from sqlalchemy import select
from backend.app.models.user import User, UserRole
from backend.app.models.roster import StudentRoster
from backend.app.models.university import Programme, Department
from backend.app.models.clearance import (
    ClearanceRequest,
    DepartmentApproval,
    ClearanceStatus,
    ApprovalStatus,
)
from backend.app.models.certificate import Certificate
from backend.app.models.refund import Refund, RefundStatus
from backend.app.models.audit import AuditLog
from backend.app.core.security import hash_password
from tests.conftest import make_auth_headers


# ---------------------------------------------------------------------------
# Part A: Email Normalization & Case Insensitivity
# ---------------------------------------------------------------------------

def test_login_with_whitespace_and_mixed_case(client, db_session):
    """Users can log in with mixed case and leading/trailing whitespace in email."""
    # admin@example.edu is seeded in conftest
    res = client.post(
        "/auth/login",
        data={"username": "  AdMiN@Example.Edu  ", "password": "TestPass@123"},
    )
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_with_registration_number_fails(client, db_session):
    """Logging in with a registration number instead of university email returns 401."""
    res = client.post(
        "/auth/login",
        data={"username": "DEMO2026001", "password": "TestPass@123"},
    )
    assert res.status_code == 401
    assert "detail" in res.json()


def test_inactive_user_cannot_login(client, db_session):
    """Inactive users are denied access at login."""
    u = db_session.execute(select(User).where(User.email == "admin@example.edu")).scalar_one()
    u.is_active = False
    db_session.commit()

    res = client.post(
        "/auth/login",
        data={"username": "admin@example.edu", "password": "TestPass@123"},
    )
    assert res.status_code == 401


def test_create_user_case_insensitive_duplicate_rejected(client, db_session):
    """Admin cannot create a staff user whose lowercased email already exists."""
    admin = db_session.execute(select(User).where(User.role == UserRole.admin)).scalar_one()
    headers = make_auth_headers(admin.id)

    # Attempt to create duplicate of library.officer@example.edu with uppercase
    payload = {
        "email": "LIBRARY.OFFICER@EXAMPLE.EDU",
        "full_name": "Duplicate Officer",
        "role": "dept_officer",
        "password": "NewPassword@123",
    }
    res = client.post("/admin/users", json=payload, headers=headers)
    assert res.status_code == 409
    assert "already exists" in res.json()["detail"].lower()


def test_create_user_invalid_domain_rejected(client, db_session):
    """Admin cannot create a user with an unapproved domain."""
    admin = db_session.execute(select(User).where(User.role == UserRole.admin)).scalar_one()
    headers = make_auth_headers(admin.id)

    payload = {
        "email": "hacker@gmail.com",
        "full_name": "Hacker User",
        "role": "dept_officer",
        "password": "Password@123",
    }
    res = client.post("/admin/users", json=payload, headers=headers)
    assert res.status_code == 400
    assert "allowed" in res.json()["detail"].lower()


def test_roster_patch_email_syncs_user_and_audits(client, db_session):
    """PATCH /admin/roster/{id} normalizes email, syncs linked User account, and logs audit."""
    prog = db_session.execute(select(Programme)).scalars().first()
    roster = StudentRoster(
        registration_number="TEST2026001",
        name="Original Student",
        email="original.student@example.edu",
        mobile="9800000010",
        address="123 Test St",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=5000.00,
    )
    db_session.add(roster)
    db_session.flush()

    pw = hash_password("StudentPass@123")
    user = User(
        email="original.student@example.edu",
        full_name="Original Student",
        password_hash=pw,
        role=UserRole.student,
        roster_id=roster.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    admin = db_session.execute(select(User).where(User.role == UserRole.admin)).scalar_one()
    headers = make_auth_headers(admin.id)

    # Update roster email with mixed case and whitespace
    patch_res = client.patch(
        f"/admin/roster/{roster.id}",
        json={"email": "  NEW.STUDENT@SVSU.AC.IN  "},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["email"] == "new.student@svsu.ac.in"

    # Verify student roster in DB
    db_session.refresh(roster)
    db_session.refresh(user)
    assert roster.email == "new.student@svsu.ac.in"
    assert user.email == "new.student@svsu.ac.in"

    # Verify audit log was created
    audit = db_session.execute(
        select(AuditLog).where(AuditLog.action == "UPDATE_USER_EMAIL_FROM_ROSTER")
    ).scalar_one_or_none()
    assert audit is not None
    assert audit.entity_id == user.id

    # Verify the student can log in with new email
    login_res = client.post(
        "/auth/login",
        data={"username": "new.student@svsu.ac.in", "password": "StudentPass@123"},
    )
    assert login_res.status_code == 200

    # Old email cannot log in
    old_login_res = client.post(
        "/auth/login",
        data={"username": "original.student@example.edu", "password": "StudentPass@123"},
    )
    assert old_login_res.status_code == 401


def test_roster_csv_upload_syncs_user_and_audits(client, db_session):
    """Uploading CSV with updated email updates roster AND linked user account."""
    prog = db_session.execute(select(Programme)).scalars().first()
    roster = StudentRoster(
        registration_number="CSV2026001",
        name="CSV Student",
        email="csv.student@example.edu",
        mobile="9800000020",
        address="456 Test Ave",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=5000.00,
    )
    db_session.add(roster)
    db_session.flush()

    pw = hash_password("StudentPass@123")
    user = User(
        email="csv.student@example.edu",
        full_name="CSV Student",
        password_hash=pw,
        role=UserRole.student,
        roster_id=roster.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    admin = db_session.execute(select(User).where(User.role == UserRole.admin)).scalar_one()
    headers = make_auth_headers(admin.id)

    csv_content = (
        "registration_number,name,email,mobile,address,programme,is_hosteller,security_deposit_amount\n"
        f"CSV2026001,CSV Student,CSV.UPDATED@SVSU.AC.IN,9800000020,456 Test Ave,{prog.name},false,5000.00\n"
    )

    upload_res = client.post(
        "/admin/roster/upload",
        files={"file": ("roster.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        headers=headers,
    )
    assert upload_res.status_code == 200
    report = upload_res.json()
    assert report["updated_count"] == 1

    db_session.refresh(roster)
    db_session.refresh(user)
    assert roster.email == "csv.updated@svsu.ac.in"
    assert user.email == "csv.updated@svsu.ac.in"

    # Verify audit log
    audit = db_session.execute(
        select(AuditLog).where(AuditLog.action == "UPDATE_USER_EMAIL_FROM_ROSTER_CSV")
    ).scalar_one_or_none()
    assert audit is not None


# ---------------------------------------------------------------------------
# Part B: Workflow & Endpoint Gaps
# ---------------------------------------------------------------------------

def test_hod_request_detail_returns_200_and_certificate_code(client, db_session):
    """GET /hod/requests/{id} returns full approvals table and certificate_code without 500 error."""
    hod = db_session.execute(select(User).where(User.email == "hod.csit@example.edu")).scalar_one()
    prog = db_session.execute(
        select(Programme).where(Programme.academic_department_id == hod.department_id)
    ).scalars().first()
    roster = StudentRoster(
        registration_number="HOD2026001",
        name="HoD Test Student",
        email="hod.student@example.edu",
        mobile="9800000030",
        address="789 Test Rd",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=5000.00,
    )
    db_session.add(roster)
    db_session.flush()

    pw = hash_password("Pass@123")
    user = User(
        email="hod.student@example.edu",
        full_name="HoD Test Student",
        password_hash=pw,
        role=UserRole.student,
        roster_id=roster.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    req = ClearanceRequest(
        roster_id=roster.id,
        status=ClearanceStatus.CLEARED,
    )
    db_session.add(req)
    db_session.flush()

    cert = Certificate(
        request_id=req.id,
        certificate_code="11111111-2222-3333-4444-555555555555",
        hod_user_id=hod.id,
    )
    db_session.add(cert)

    lib_dept = db_session.execute(select(Department).where(Department.name == "Library")).scalar_one()
    officer = db_session.execute(select(User).where(User.email == "library.officer@example.edu")).scalar_one()
    approval = DepartmentApproval(
        request_id=req.id,
        department_id=lib_dept.id,
        status=ApprovalStatus.APPROVED,
        decided_by=officer.id,
    )
    db_session.add(approval)
    db_session.commit()

    headers = make_auth_headers(hod.id)

    res = client.get(f"/hod/requests/{req.id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["request_id"] == req.id
    assert data["certificate_code"] == "11111111-2222-3333-4444-555555555555"
    assert len(data["approvals"]) >= 1
    assert data["approvals"][0]["decided_by_name"] == officer.full_name


def test_registrar_queue_status_filter_and_amounts(client, db_session):
    """GET /registrar/queue supports ?status= filter and populates deductions/final_amount."""
    prog = db_session.execute(select(Programme)).scalars().first()
    roster = StudentRoster(
        registration_number="REG2026001",
        name="Registrar Student",
        email="reg.student@example.edu",
        mobile="9800000040",
        address="100 Reg St",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=5000.00,
    )
    db_session.add(roster)
    db_session.flush()

    req_cleared = ClearanceRequest(
        roster_id=roster.id,
        status=ClearanceStatus.CLEARED,
    )
    db_session.add(req_cleared)

    roster2 = StudentRoster(
        registration_number="REG2026002",
        name="Refunded Student",
        email="refunded.student@example.edu",
        mobile="9800000041",
        address="101 Reg St",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=5000.00,
    )
    db_session.add(roster2)
    db_session.flush()

    req_refunded = ClearanceRequest(
        roster_id=roster2.id,
        status=ClearanceStatus.REFUND_VERIFIED,
    )
    db_session.add(req_refunded)
    db_session.flush()

    reg_user = db_session.execute(select(User).where(User.role == UserRole.registrar_accounts)).scalar_one()
    refund = Refund(
        request_id=req_refunded.id,
        deposit_amount=5000.00,
        deductions=500.00,
        final_amount=4500.00,
        status=RefundStatus.VERIFIED,
    )
    db_session.add(refund)
    db_session.commit()

    headers = make_auth_headers(reg_user.id)

    # 1. Default queue returns CLEARED
    res_default = client.get("/registrar/queue", headers=headers)
    assert res_default.status_code == 200
    cleared_items = res_default.json()["items"]
    assert any(it["request_id"] == req_cleared.id for it in cleared_items)
    assert not any(it["request_id"] == req_refunded.id for it in cleared_items)

    # 2. Filter status=REFUND_VERIFIED
    res_refunded = client.get("/registrar/queue?status=REFUND_VERIFIED", headers=headers)
    assert res_refunded.status_code == 200
    refunded_items = res_refunded.json()["items"]
    matched = [it for it in refunded_items if it["request_id"] == req_refunded.id]
    assert len(matched) == 1
    assert float(matched[0]["deductions"]) == 500.00
    assert float(matched[0]["final_amount"]) == 4500.00


def test_department_queue_search(client, db_session):
    """GET /department/queue?search= filters records by student name or reg number."""
    prog = db_session.execute(select(Programme)).scalars().first()
    lib_dept = db_session.execute(select(Department).where(Department.name == "Library")).scalar_one()
    officer = db_session.execute(select(User).where(User.email == "library.officer@example.edu")).scalar_one()
    headers = make_auth_headers(officer.id)

    r1 = StudentRoster(
        registration_number="SRCH001",
        name="Unique Alpha",
        email="srch1@example.edu",
        mobile="9800000051",
        address="1 St",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=5000.00,
    )
    r2 = StudentRoster(
        registration_number="SRCH002",
        name="Unique Beta",
        email="srch2@example.edu",
        mobile="9800000052",
        address="2 St",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=5000.00,
    )
    db_session.add_all([r1, r2])
    db_session.flush()

    req1 = ClearanceRequest(roster_id=r1.id, status=ClearanceStatus.SUBMITTED)
    req2 = ClearanceRequest(roster_id=r2.id, status=ClearanceStatus.SUBMITTED)
    db_session.add_all([req1, req2])
    db_session.flush()

    appr1 = DepartmentApproval(request_id=req1.id, department_id=lib_dept.id, status=ApprovalStatus.PENDING)
    appr2 = DepartmentApproval(request_id=req2.id, department_id=lib_dept.id, status=ApprovalStatus.PENDING)
    db_session.add_all([appr1, appr2])
    db_session.commit()

    # Search for Alpha
    res = client.get("/department/queue?search=Alpha", headers=headers)
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["student_name"] == "Unique Alpha"

    # Search by registration number
    res_reg = client.get("/department/queue?search=SRCH002", headers=headers)
    assert res_reg.status_code == 200
    items_reg = res_reg.json()["items"]
    assert len(items_reg) == 1
    assert items_reg[0]["registration_number"] == "SRCH002"


def test_list_departments(client, db_session):
    """GET /departments is accessible to authenticated users and returns department list."""
    admin = db_session.execute(select(User).where(User.role == UserRole.admin)).scalar_one()
    headers = make_auth_headers(admin.id)

    res = client.get("/departments", headers=headers)
    assert res.status_code == 200
    deps = res.json()
    assert isinstance(deps, list)
    assert len(deps) >= 4
    first = deps[0]
    assert "id" in first
    assert "name" in first
    assert "kind" in first
    assert "applicability" in first


def test_admin_list_users_no_passwords(client, db_session):
    """GET /admin/users returns staff/users with department names and never exposes passwords."""
    admin = db_session.execute(select(User).where(User.role == UserRole.admin)).scalar_one()
    headers = make_auth_headers(admin.id)

    res = client.get("/admin/users", headers=headers)
    assert res.status_code == 200
    users = res.json()
    assert len(users) >= 1

    for u in users:
        assert "password" not in u
        assert "password_hash" not in u
        assert "id" in u
        assert "email" in u
        assert "role" in u

    # Test filtering by role
    res_role = client.get("/admin/users?role=dept_officer", headers=headers)
    assert res_role.status_code == 200
    officers = res_role.json()
    assert all(o["role"] == "dept_officer" for o in officers)
    assert any(o["department_name"] == "Library" for o in officers)
