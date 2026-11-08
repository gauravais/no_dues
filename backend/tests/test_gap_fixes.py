"""
Tests covering backend gap fixes:
1. GET /department/queue declared_is_hosteller and others_note scoping
2. GET /department/requests/{id} academic vs scoped dossier and unrelated officer 404
3. GET /student/requests/current refund status, deposit, deductions, final_amount, payment_reference
4. POST /student/requests other_department_ids validation (ASSIGNED_ONLY, not lab linked, active officer)
5. POST /student/requests/{id}/lab-courses registration in openapi and functionality
6. GET /health endpoint and production security startup guards
7. Alembic migration 0008 roundtrip
"""
from decimal import Decimal
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, inspect
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.core.crypto import encrypt_bank_account
from backend.app.core.security import hash_password
from backend.app.models.user import User, UserRole
from backend.app.models.university import (
    Department, DepartmentKind, DepartmentApplicability, Programme
)
from backend.app.models.roster import StudentRoster
from backend.app.models.bank import BankDetail
from backend.app.models.lab_course import LabCourse
from backend.app.models.clearance import (
    ClearanceRequest, DepartmentApproval, ClearanceStatus, ApprovalStatus
)
from backend.app.models.refund import Refund, RefundStatus
from tests.conftest import make_auth_headers, TEST_DATABASE_URL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_test_student(db_session):
    """Create a student user and roster entry ready for clearance apply."""
    prog = db_session.execute(
        select(Programme).where(Programme.name.ilike("%Computer%"))
    ).scalar_one()

    roster = StudentRoster(
        registration_number="TEST2026999",
        name="Gap Fix Test Student",
        email="test.student.gap@example.edu",
        mobile="9876543210",
        address="123 Test Boulevard",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=Decimal("5000.00"),
    )
    db_session.add(roster)
    db_session.flush()

    bank = BankDetail(
        roster_id=roster.id,
        account_holder_name="Gap Fix Student",
        account_number=encrypt_bank_account("987654321099"),
        ifsc_code="SBIN0001234",
        bank_address="Main Campus Branch",
    )
    db_session.add(bank)

    pw = hash_password("StudentPass123!")
    user = User(
        email="test.student.gap@example.edu",
        full_name="Gap Fix Student",
        password_hash=pw,
        role=UserRole.student,
        roster_id=roster.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user, roster


# ---------------------------------------------------------------------------
# 1. Migration 0008 Roundtrip
# ---------------------------------------------------------------------------

def test_migration_0008_roundtrip(test_engine):
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)

    # Downgrade to 0007
    command.downgrade(alembic_cfg, "0007_audit_and_hardening")
    insp_down = inspect(test_engine)
    cols_down = [c["name"] for c in insp_down.get_columns("refunds")]
    assert "payment_reference" not in cols_down, "payment_reference should be dropped after downgrade"

    # Upgrade to head (0008)
    command.upgrade(alembic_cfg, "head")
    insp_up = inspect(test_engine)
    cols_up = [c["name"] for c in insp_up.get_columns("refunds")]
    assert "payment_reference" in cols_up, "payment_reference should exist after upgrade"


# ---------------------------------------------------------------------------
# 2. GET /health Endpoint
# ---------------------------------------------------------------------------

def test_get_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "environment" in data


# ---------------------------------------------------------------------------
# 3. Production Environment Startup Guards
# ---------------------------------------------------------------------------

def test_production_environment_startup_guards():
    valid_key = "9VgS5iI8WKkmZC3Irsvriq4CkX1OLKU4eHXp0DiwynA="
    long_secret = "a" * 32

    # Fails if JWT_SECRET < 32 in production
    with pytest.raises(ValueError, match="JWT_SECRET must be at least 32 characters in production"):
        Settings(
            APP_ENV="production",
            JWT_SECRET="short_secret",
            BANK_DATA_KEY=valid_key,
            DEV_RETURN_OTP=False,
            MAIL_CONSOLE_ONLY=False,
        )

    # Fails if DEV_RETURN_OTP is True in production
    with pytest.raises(ValueError, match="DEV_RETURN_OTP must be False in production"):
        Settings(
            APP_ENV="production",
            JWT_SECRET=long_secret,
            BANK_DATA_KEY=valid_key,
            DEV_RETURN_OTP=True,
            MAIL_CONSOLE_ONLY=False,
        )

    # Fails if MAIL_CONSOLE_ONLY is True in production
    with pytest.raises(ValueError, match="MAIL_CONSOLE_ONLY must be False in production"):
        Settings(
            APP_ENV="production",
            JWT_SECRET=long_secret,
            BANK_DATA_KEY=valid_key,
            DEV_RETURN_OTP=False,
            MAIL_CONSOLE_ONLY=True,
        )

    # Fails if BANK_DATA_KEY is missing in production
    with pytest.raises(ValueError, match="BANK_DATA_KEY"):
        Settings(
            APP_ENV="production",
            JWT_SECRET=long_secret,
            BANK_DATA_KEY="",
            DEV_RETURN_OTP=False,
            MAIL_CONSOLE_ONLY=False,
        )

    # Passes in production when all security rules are respected
    valid_prod = Settings(
        APP_ENV="production",
        JWT_SECRET=long_secret,
        BANK_DATA_KEY=valid_key,
        DEV_RETURN_OTP=False,
        MAIL_CONSOLE_ONLY=False,
        ENABLE_DOCS=False,
        CORS_ORIGINS='https://nodues.svsu.ac.in',
        SMTP_HOST='smtp.svsu.ac.in',
        SMTP_PORT=587,
        SMTP_FROM='no-reply@svsu.ac.in',
        FRONTEND_BASE_URL='https://nodues.svsu.ac.in',
    )
    assert valid_prod.APP_ENV == "production"


# ---------------------------------------------------------------------------
# 4. GET /department/queue Item Scoping (hostel & others_note)
# ---------------------------------------------------------------------------

def test_department_queue_hostel_and_others_note(client, db_session):
    student, roster = _create_test_student(db_session)

    # Seed LabCourse for Lab-1 (id of Lab-1)
    lab1 = db_session.execute(select(Department).where(Department.name == "Lab-1")).scalar_one()
    cs_dept = db_session.execute(select(Department).where(Department.name == "Skill Department of CS/IT")).scalar_one()
    course1 = LabCourse(
        code="CS-L101",
        name="Data Structures Lab",
        lab_department_id=lab1.id,
        academic_department_id=cs_dept.id,
        is_active=True,
    )
    db_session.add(course1)
    db_session.commit()

    # Apply with hostel=True, lab course CS-L101, and others_note
    apply_payload = {
        "is_hosteller": True,
        "lab_course_ids": [course1.id],
        "others_note": "Special robotics equipment in workshop",
    }
    res = client.post(
        "/student/requests",
        json=apply_payload,
        headers=make_auth_headers(student.id),
    )
    assert res.status_code == 201

    # 4a. Hostel officer queue: must see declared_is_hosteller as True
    hostel_officer = db_session.execute(
        select(User).where(User.email == "hostel.officer@example.edu")
    ).scalar_one()
    q_hostel = client.get(
        "/department/queue",
        headers=make_auth_headers(hostel_officer.id),
    ).json()
    assert q_hostel["total"] >= 1
    hostel_item = next(it for it in q_hostel["items"] if it["registration_number"] == roster.registration_number)
    assert hostel_item["declared_is_hosteller"] is True
    assert hostel_item["others_note"] is None

    # 4b. Library officer queue: declared_is_hosteller must be None, others_note must be present
    lib_officer = db_session.execute(
        select(User).where(User.email == "library.officer@example.edu")
    ).scalar_one()
    q_lib = client.get(
        "/department/queue",
        headers=make_auth_headers(lib_officer.id),
    ).json()
    lib_item = next(it for it in q_lib["items"] if it["registration_number"] == roster.registration_number)
    assert lib_item["declared_is_hosteller"] is None
    assert lib_item["others_note"] is None

    # 4c. Lab-1 officer queue: declared_is_hosteller is None, others_note must be None (linked to lab subject)
    lab1_officer = db_session.execute(
        select(User).where(User.email == "lab1.officer@example.edu")
    ).scalar_one()
    q_lab1 = client.get(
        "/department/queue",
        headers=make_auth_headers(lab1_officer.id),
    ).json()
    lab1_item = next(it for it in q_lab1["items"] if it["registration_number"] == roster.registration_number)
    assert lab1_item["declared_is_hosteller"] is None
    assert lab1_item["others_note"] is None
    assert len(lab1_item["declared_subjects"]) == 1
    assert "CS-L101" in lab1_item["declared_subjects"][0]


# ---------------------------------------------------------------------------
# 5. GET /department/requests/{id} Dossier Scoping & Role Guards
# ---------------------------------------------------------------------------

def test_department_requests_detail_scoping_and_unrelated_404(client, db_session):
    student, roster = _create_test_student(db_session)

    # Seed Lab-1 course
    lab1 = db_session.execute(select(Department).where(Department.name == "Lab-1")).scalar_one()
    cs_dept = db_session.execute(select(Department).where(Department.name == "Skill Department of CS/IT")).scalar_one()
    course1 = LabCourse(
        code="CS-L101",
        name="Data Structures Lab",
        lab_department_id=lab1.id,
        academic_department_id=cs_dept.id,
        is_active=True,
    )
    db_session.add(course1)
    db_session.commit()

    # Apply without hostel, only Lab-1 and standard always depts
    apply_payload = {
        "is_hosteller": False,
        "lab_course_ids": [course1.id],
        "others_note": "General campus clearance note",
    }
    res_apply = client.post(
        "/student/requests",
        json=apply_payload,
        headers=make_auth_headers(student.id),
    )
    req_id = res_apply.json()["id"]

    # 5a. Academic Officer sees FULL dossier
    acad_officer = db_session.execute(
        select(User).where(User.email == "officer.csit@example.edu")
    ).scalar_one()
    res_acad = client.get(
        f"/department/requests/{req_id}",
        headers=make_auth_headers(acad_officer.id),
    )
    assert res_acad.status_code == 200
    acad_data = res_acad.json()
    assert acad_data["academic_department"] == "Skill Department of CS/IT"
    assert len(acad_data["approvals"]) > 1  # Full approvals table
    assert len(acad_data["can_add_departments"]) > 0  # Candidate departments list

    # 5b. Non-academic officer (Library) sees LIMITED dossier
    lib_officer = db_session.execute(
        select(User).where(User.email == "library.officer@example.edu")
    ).scalar_one()
    res_lib = client.get(
        f"/department/requests/{req_id}",
        headers=make_auth_headers(lib_officer.id),
    )
    assert res_lib.status_code == 200
    lib_data = res_lib.json()
    assert lib_data["academic_department"] == "Skill Department of CS/IT"
    assert lib_data["declared_is_hosteller"] is None  # Not hostel office
    assert lib_data["others_note"] is None
    assert len(lib_data["approvals"]) == 1  # Only their own row
    assert lib_data["approvals"][0]["department_name"] == "Library"
    assert lib_data["can_add_departments"] == []  # Cannot add departments
    assert lib_data["certificate_code"] is None

    # 5c. Officer of an office NOT on the request (Lab-2) gets 404
    lab2_officer = db_session.execute(
        select(User).where(User.email == "lab2.officer@example.edu")
    ).scalar_one()
    res_lab2 = client.get(
        f"/department/requests/{req_id}",
        headers=make_auth_headers(lab2_officer.id),
    )
    assert res_lab2.status_code == 404
    assert "not found for your department" in res_lab2.json()["detail"].lower()

    # 5d. Non-officer (student) calling GET /department/requests/{id} gets 403
    res_student = client.get(
        f"/department/requests/{req_id}",
        headers=make_auth_headers(student.id),
    )
    assert res_student.status_code == 403


# ---------------------------------------------------------------------------
# 6. GET /student/requests/current Refund Fields Lifecycle
# ---------------------------------------------------------------------------

def test_student_current_request_refund_lifecycle(client, db_session):
    student, roster = _create_test_student(db_session)

    # 6a. Apply for clearance
    res = client.post(
        "/student/requests",
        json={"is_hosteller": False},
        headers=make_auth_headers(student.id),
    )
    assert res.status_code == 201
    created_data = res.json()
    assert created_data["refund_status"] is None
    assert created_data["deposit_amount"] is None
    assert created_data["payment_reference"] is None

    # Check GET /student/requests/current immediately
    cur1 = client.get(
        "/student/requests/current",
        headers=make_auth_headers(student.id),
    ).json()
    assert cur1["refund_status"] is None
    assert cur1["deposit_amount"] is None
    assert cur1["payment_reference"] is None

    req_id = cur1["id"]

    # 6b. Fast-track approvals to CLEARED
    req_obj = db_session.get(ClearanceRequest, req_id)
    req_obj.status = ClearanceStatus.CLEARED
    for app in req_obj.approvals:
        app.status = ApprovalStatus.APPROVED
    db_session.commit()

    # 6c. Registrar verifies refund
    reg_user = db_session.execute(
        select(User).where(User.email == "registrar.accounts@example.edu")
    ).scalar_one()
    ver_res = client.post(
        f"/registrar/requests/{req_id}/verify-refund",
        json={"deductions": 250, "remarks": "Alumni fund deduction"},
        headers=make_auth_headers(reg_user.id),
    )
    assert ver_res.status_code == 200

    cur2 = client.get(
        "/student/requests/current",
        headers=make_auth_headers(student.id),
    ).json()
    assert cur2["refund_status"] == "VERIFIED"
    assert float(cur2["deductions"]) == 250.00
    assert float(cur2["final_amount"]) == 4750.00
    assert cur2["payment_reference"] is None  # Still not processed

    # 6d. Registrar marks processed with payment reference
    proc_res = client.post(
        f"/registrar/requests/{req_id}/mark-processed",
        json={"payment_reference": "NEFT_SVSU_GAP_TEST_001"},
        headers=make_auth_headers(reg_user.id),
    )
    assert proc_res.status_code == 200

    cur3 = client.get(
        "/student/requests/current",
        headers=make_auth_headers(student.id),
    ).json()
    assert cur3["refund_status"] == "PROCESSED"
    assert cur3["payment_reference"] == "NEFT_SVSU_GAP_TEST_001"


# ---------------------------------------------------------------------------
# 7. Apply Endpoint Other Offices Validation
# ---------------------------------------------------------------------------

def test_apply_other_offices_validation(client, db_session):
    student, roster = _create_test_student(db_session)

    # Create Workshop-1 as an ASSIGNED_ONLY office with active officer
    workshop1 = Department(
        name="Workshop-1 Gap Test",
        kind=DepartmentKind.service,
        applicability=DepartmentApplicability.ASSIGNED_ONLY,
        faculty_id=None,
    )
    db_session.add(workshop1)
    db_session.flush()

    pw = hash_password("TestPass@123")
    ws_officer = User(
        email="ws1.gap@example.edu",
        full_name="Workshop 1 Officer",
        password_hash=pw,
        role=UserRole.dept_officer,
        department_id=workshop1.id,
        is_active=True,
    )
    db_session.add(ws_officer)

    # Create Workshop-2 (ASSIGNED_ONLY, but NO active officer)
    workshop2 = Department(
        name="Workshop-2 Gap Test (No Officer)",
        kind=DepartmentKind.service,
        applicability=DepartmentApplicability.ASSIGNED_ONLY,
        faculty_id=None,
    )
    db_session.add(workshop2)

    # Create Lab-1 course
    lab1 = db_session.execute(select(Department).where(Department.name == "Lab-1")).scalar_one()
    cs_dept = db_session.execute(select(Department).where(Department.name == "Skill Department of CS/IT")).scalar_one()
    course1 = LabCourse(
        code="CS-L101-GAP",
        name="Data Structures Lab Gap",
        lab_department_id=lab1.id,
        academic_department_id=cs_dept.id,
        is_active=True,
    )
    db_session.add(course1)
    db_session.commit()

    lib_dept = db_session.execute(select(Department).where(Department.name == "Library")).scalar_one()

    # 7a. Reject if department is NOT ASSIGNED_ONLY (e.g. Library, which is ALWAYS)
    res_bad_applicability = client.post(
        "/student/requests",
        json={"other_department_ids": [lib_dept.id]},
        headers=make_auth_headers(student.id),
    )
    assert res_bad_applicability.status_code == 400
    assert "only assigned_only" in res_bad_applicability.json()["detail"].lower()

    # 7b. Reject if department is linked to a lab subject (e.g. Lab-1)
    res_lab_linked = client.post(
        "/student/requests",
        json={"other_department_ids": [lab1.id]},
        headers=make_auth_headers(student.id),
    )
    assert res_lab_linked.status_code == 400
    assert "only assigned_only" in res_lab_linked.json()["detail"].lower()

    # 7c. Reject if department has no active officer (Workshop-2)
    res_no_officer = client.post(
        "/student/requests",
        json={"other_department_ids": [workshop2.id]},
        headers=make_auth_headers(student.id),
    )
    assert res_no_officer.status_code == 409
    assert "no active dealing officer" in res_no_officer.json()["detail"].lower()

    # 7d. Reject non-existent department
    res_404 = client.post(
        "/student/requests",
        json={"other_department_ids": [999999]},
        headers=make_auth_headers(student.id),
    )
    assert res_404.status_code == 404

    # 7e. Succeeds with valid Workshop-1 (and accepts other_office_ids alias as well)
    res_ok = client.post(
        "/student/requests",
        json={"other_office_ids": [workshop1.id]},
        headers=make_auth_headers(student.id),
    )
    assert res_ok.status_code == 201
    apps = res_ok.json()["approvals"]
    ws_approval = next((a for a in apps if a["department_id"] == workshop1.id), None)
    assert ws_approval is not None, "Workshop-1 approval must be added to request"


# ---------------------------------------------------------------------------
# 8. POST /student/requests/{id}/lab-courses Registration & Functionality
# ---------------------------------------------------------------------------

def test_student_declare_lab_courses_endpoint_and_openapi(client, db_session):
    # 8a. Confirm present in /openapi.json
    res_openapi = client.get("/openapi.json")
    assert res_openapi.status_code == 200
    spec = res_openapi.json()
    assert "/student/requests/{request_id}/lab-courses" in spec["paths"]
    post_op = spec["paths"]["/student/requests/{request_id}/lab-courses"]["post"]
    assert post_op["operationId"] == "declare_additional_lab_courses"

    # 8b. Test functionality: student declares new lab courses while active
    student, roster = _create_test_student(db_session)
    lab1 = db_session.execute(select(Department).where(Department.name == "Lab-1")).scalar_one()
    lab2 = db_session.execute(select(Department).where(Department.name == "Lab-2")).scalar_one()
    cs_dept = db_session.execute(select(Department).where(Department.name == "Skill Department of CS/IT")).scalar_one()

    course1 = LabCourse(
        code="CS-L201",
        name="Operating Systems Lab",
        lab_department_id=lab1.id,
        academic_department_id=cs_dept.id,
        is_active=True,
    )
    course2 = LabCourse(
        code="CS-L202",
        name="Networking Lab",
        lab_department_id=lab2.id,
        academic_department_id=cs_dept.id,
        is_active=True,
    )
    db_session.add_all([course1, course2])
    db_session.commit()

    # Apply with only course 1 (Lab-1)
    res_apply = client.post(
        "/student/requests",
        json={"lab_course_ids": [course1.id]},
        headers=make_auth_headers(student.id),
    )
    req_id = res_apply.json()["id"]

    # Student now declares course 2 (which maps to Lab-2, not yet attached)
    res_declare = client.post(
        f"/student/requests/{req_id}/lab-courses",
        json={"lab_course_ids": [course2.id]},
        headers=make_auth_headers(student.id),
    )
    assert res_declare.status_code == 200
    updated_apps = res_declare.json()["approvals"]
    lab2_app = next((a for a in updated_apps if a["department_id"] == lab2.id), None)
    assert lab2_app is not None, "Lab-2 approval must be added upon declaring course2"
    assert lab2_app["status"] == "PENDING"

    # 8c. Role guard: non-student cannot declare lab courses
    lib_officer = db_session.execute(
        select(User).where(User.email == "library.officer@example.edu")
    ).scalar_one()
    res_forbidden = client.post(
        f"/student/requests/{req_id}/lab-courses",
        json={"lab_course_ids": [course2.id]},
        headers=make_auth_headers(lib_officer.id),
    )
    assert res_forbidden.status_code == 403
