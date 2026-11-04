"""Comprehensive test suite for Pilot-Readiness features:
- Outbox pattern email queueing & delivery
- Daily reminder digests & deduplication
- Database-backed authentication rate limiting
- Generic OTP request responses & generic verification errors
- Forced password change (must_change_password) workflows
- Cancellation & reapplication workflows
- First admin creation script
- Alembic migration 0009 roundtrip
"""
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import status
from alembic.config import Config
from alembic import command
from sqlalchemy import select, func, delete

from backend.app.core.config import settings
from backend.app.core.security import hash_password, create_access_token
from backend.app.models.user import User, UserRole
from backend.app.models.university import Faculty, Department, Programme, DepartmentKind, DepartmentApplicability
from backend.app.models.roster import StudentRoster
from backend.app.models.bank import BankDetail
from backend.app.models.clearance import (
    ClearanceRequest,
    DepartmentApproval,
    ClearanceStatus,
    ApprovalStatus,
)
from backend.app.models.email import EmailOutbox, OutboxStatus
from backend.app.models.rate_limit import AuthRateLimit
from backend.app.models.otp import SignupOTP
from backend.app.services.email import deliver_outbox_email, queue_email
from backend.app.services.workflow import (
    create_request,
    decide_approval,
    hod_decide,
    student_cancel_request,
    staff_cancel_request,
)
from scripts.create_first_admin import create_first_admin
from scripts.send_reminders import process_reminders
from tests.conftest import TEST_DATABASE_URL


def test_migration_0009_roundtrip():
    """Verify Alembic migration 0009 downgrades cleanly to 0008 and upgrades back to head."""
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)

    # Downgrade 1 revision back to 0008
    command.downgrade(alembic_cfg, "-1")

    # Upgrade back to head (0009)
    command.upgrade(alembic_cfg, "head")


@pytest.fixture
def base_setup(db_session):
    """Fetches seeded Faculty, Academic Department, Service Department, Programme, and sets up Roster & Users."""
    acad_dept = db_session.execute(
        select(Department).where(Department.kind == DepartmentKind.academic)
    ).scalars().first()
    lib_dept = db_session.execute(
        select(Department).where(Department.applicability == DepartmentApplicability.ALWAYS)
    ).scalars().first()
    prog = db_session.execute(
        select(Programme).where(Programme.academic_department_id == acad_dept.id)
    ).scalars().first()

    roster = StudentRoster(
        registration_number="PILOT2026001",
        name="Rohan Verma",
        email="rohan.verma@svsu.ac.in",
        mobile="9876543210",
        address="123 SVSU Campus, Gurugram",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=Decimal("5000.00"),
    )
    db_session.add(roster)
    db_session.flush()

    # Create bank details
    from backend.app.core.crypto import encrypt_bank_account
    bank = BankDetail(
        roster_id=roster.id,
        account_holder_name="Rohan Verma",
        account_number=encrypt_bank_account("123456789012"),
        ifsc_code="SBIN0001234",
        bank_address="SVSU Campus Branch",
    )
    db_session.add(bank)

    # Create staff users
    acad_officer = User(
        email="officer.csit@svsu.ac.in",
        full_name="CS/IT Officer",
        password_hash=hash_password("OfficerSecure@2026"),
        role=UserRole.dept_officer,
        department_id=acad_dept.id,
        is_active=True,
        must_change_password=False,
    )
    lib_officer = User(
        email="officer.library@svsu.ac.in",
        full_name="Library Officer",
        password_hash=hash_password("OfficerSecure@2026"),
        role=UserRole.dept_officer,
        department_id=lib_dept.id,
        is_active=True,
        must_change_password=False,
    )
    hod = User(
        email="hod.csit@svsu.ac.in",
        full_name="HoD CS/IT",
        password_hash=hash_password("HodSecure@2026"),
        role=UserRole.hod,
        department_id=acad_dept.id,
        is_active=True,
        must_change_password=False,
    )
    admin = User(
        email="admin@svsu.ac.in",
        full_name="System Admin",
        password_hash=hash_password("AdminSecure@2026"),
        role=UserRole.admin,
        is_active=True,
        must_change_password=False,
    )
    db_session.add_all([acad_officer, lib_officer, hod, admin])
    db_session.commit()

    return {
        "acad_dept": acad_dept,
        "lib_dept": lib_dept,
        "programme": prog,
        "roster": roster,
        "acad_officer": acad_officer,
        "lib_officer": lib_officer,
        "hod": hod,
        "admin": admin,
    }


def test_email_outbox_allowlist_and_delivery(db_session):
    """Verify EMAIL_ALLOWLIST filters outbox items to SKIPPED, while allowed addresses send."""
    # When allowlist is set
    original_allowlist = settings.EMAIL_ALLOWLIST
    try:
        settings.EMAIL_ALLOWLIST = "allowed@svsu.ac.in"
        item_skipped = queue_email(
            session=db_session,
            to_email="blocked@svsu.ac.in",
            subject="Test",
            body="Test body",
            kind="test",
        )
        db_session.commit()

        deliver_outbox_email(db_session, item_skipped)
        assert item_skipped.status == OutboxStatus.SKIPPED
        assert "EMAIL_ALLOWLIST" in item_skipped.last_error

        item_allowed = queue_email(
            session=db_session,
            to_email="allowed@svsu.ac.in",
            subject="Test",
            body="Test body",
            kind="test",
        )
        db_session.commit()

        deliver_outbox_email(db_session, item_allowed)
        assert item_allowed.status == OutboxStatus.SENT
    finally:
        settings.EMAIL_ALLOWLIST = original_allowlist


def test_generic_signup_otp_response(client, db_session, base_setup):
    """Verify request_signup_otp returns generic message for non-existent and existent records without leaking."""
    # 1. Non-existent registration number
    res1 = client.post(
        "/auth/signup/request-otp",
        json={"registration_number": "NONEXISTENT", "email": "rohan.verma@svsu.ac.in"},
    )
    assert res1.status_code == 200
    assert "If the details match our records" in res1.json()["detail"]
    assert res1.json().get("dev_otp") is None

    # 2. Existent student matching roster
    res2 = client.post(
        "/auth/signup/request-otp",
        json={"registration_number": "PILOT2026001", "email": "rohan.verma@svsu.ac.in"},
    )
    assert res2.status_code == 200
    assert "If the details match our records" in res2.json()["detail"]

    # Verify outbox item was queued
    outbox_item = db_session.execute(
        select(EmailOutbox).where(EmailOutbox.to_email == "rohan.verma@svsu.ac.in", EmailOutbox.kind == "signup_otp")
    ).scalars().first()
    assert outbox_item is not None
    assert "Your Sign-Up Verification Code" in outbox_item.subject


def test_login_rate_limiting(client, db_session, base_setup):
    """Verify max 5 failed logins within 15 minutes triggers HTTP 429 with Retry-After header."""
    for attempt in range(5):
        res = client.post(
            "/auth/login",
            data={"username": "admin@svsu.ac.in", "password": "WrongPassword!"},
        )
        assert res.status_code == 401

    # 6th attempt must be rate-limited (HTTP 429)
    res_blocked = client.post(
        "/auth/login",
        data={"username": "admin@svsu.ac.in", "password": "WrongPassword!"},
    )
    assert res_blocked.status_code == 429
    assert "Retry-After" in res_blocked.headers
    assert int(res_blocked.headers["Retry-After"]) > 0


def test_must_change_password_workflow(client, db_session, base_setup):
    """Verify users with must_change_password=True are locked out until changing password."""
    # Create user with must_change_password=True
    staff_user = User(
        email="new.officer@svsu.ac.in",
        full_name="New Officer",
        password_hash=hash_password("TemporaryPass@10"),
        role=UserRole.dept_officer,
        department_id=base_setup["acad_dept"].id,
        is_active=True,
        must_change_password=True,
    )
    db_session.add(staff_user)
    db_session.commit()

    # Login returns must_change_password: true
    login_res = client.post(
        "/auth/login",
        data={"username": "new.officer@svsu.ac.in", "password": "TemporaryPass@10"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    assert login_res.json()["must_change_password"] is True

    headers = {"Authorization": f"Bearer {token}"}

    # Calling general protected endpoint is blocked (HTTP 403 PASSWORD_CHANGE_REQUIRED)
    queue_res = client.get("/department/queue", headers=headers)
    assert queue_res.status_code == 403
    assert queue_res.json()["detail"] == "PASSWORD_CHANGE_REQUIRED"

    # Calling /auth/me succeeds
    me_res = client.get("/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["must_change_password"] is True

    # Calling /auth/change-password with invalid current password fails
    bad_cp = client.post(
        "/auth/change-password",
        json={"current_password": "WrongPassword", "new_password": "NewSecurePassword@2026"},
        headers=headers,
    )
    assert bad_cp.status_code == 400

    # Calling /auth/change-password with same password fails
    same_cp = client.post(
        "/auth/change-password",
        json={"current_password": "TemporaryPass@10", "new_password": "TemporaryPass@10"},
        headers=headers,
    )
    assert same_cp.status_code == 400

    # Successful password change
    good_cp = client.post(
        "/auth/change-password",
        json={"current_password": "TemporaryPass@10", "new_password": "NewBrandSecurePass@2026"},
        headers=headers,
    )
    assert good_cp.status_code == 200
    assert good_cp.json()["detail"] == "Password changed successfully."

    # Now general protected endpoint succeeds
    queue_res2 = client.get("/department/queue", headers=headers)
    assert queue_res2.status_code == 200


def test_cancellation_and_reapplication(client, db_session, base_setup):
    """Verify student and staff cancellation rules and re-application after cancellation."""
    # Create student user
    student = User(
        email="rohan.verma@svsu.ac.in",
        full_name="Rohan Verma",
        password_hash=hash_password("StudentSecure@2026"),
        role=UserRole.student,
        roster_id=base_setup["roster"].id,
        is_active=True,
        must_change_password=False,
    )
    db_session.add(student)
    db_session.commit()

    student_token = create_access_token(student.id)
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # Student applies for clearance
    req = create_request(
        session=db_session,
        student_user=student,
        declared_is_hosteller=False,
    )
    req_id = req.id

    # Verify officers received outbox notification
    outbox_notifs = db_session.execute(
        select(EmailOutbox).where(EmailOutbox.kind == "request_submitted", EmailOutbox.related_request_id == req_id)
    ).scalars().all()
    assert len(outbox_notifs) >= 1

    # Student can cancel while all approvals are still PENDING
    cancel_res = client.post(
        f"/student/requests/{req_id}/cancel",
        json={"reason": "Need to update subject selections"},
        headers=student_headers,
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == ClearanceStatus.CANCELLED.value

    # Verify cancellation email queued
    cancel_email = db_session.execute(
        select(EmailOutbox).where(EmailOutbox.kind == "cancelled", EmailOutbox.related_request_id == req_id)
    ).scalars().first()
    assert cancel_email is not None

    # Cancelled request disappears from officer queue
    officer_token = create_access_token(base_setup["lib_officer"].id)
    officer_headers = {"Authorization": f"Bearer {officer_token}"}
    queue_res = client.get("/department/queue", headers=officer_headers)
    assert queue_res.status_code == 200
    items = queue_res.json()["items"]
    assert all(item["request_id"] != req_id for item in items)

    # Student can re-apply now that previous request is CANCELLED
    reapply_res = client.post(
        "/student/requests",
        json={"is_hosteller": False},
        headers=student_headers,
    )
    assert reapply_res.status_code in (200, 201)
    new_req_id = reapply_res.json()["id"]
    assert new_req_id != req_id
    assert reapply_res.json()["status"] == ClearanceStatus.SUBMITTED.value

    # Academic officer can cancel active clearance request with reason
    acad_officer_token = create_access_token(base_setup["acad_officer"].id)
    acad_headers = {"Authorization": f"Bearer {acad_officer_token}"}
    staff_cancel_res = client.post(
        f"/department/requests/{new_req_id}/cancel",
        json={"reason": "Student application retracted for correction"},
        headers=acad_headers,
    )
    assert staff_cancel_res.status_code == 200
    assert staff_cancel_res.json()["status"] == ClearanceStatus.CANCELLED.value


def test_send_reminders_deduplication(db_session, base_setup):
    """Verify daily reminder digests are sent and de-duplicated within 24 hours."""
    original_enabled = settings.REMINDERS_ENABLED
    original_days = settings.REMINDER_AFTER_DAYS
    try:
        settings.REMINDERS_ENABLED = True
        settings.REMINDER_AFTER_DAYS = 3

        # Create a student and request backdated > 3 days
        student = User(
            email="rohan.verma@svsu.ac.in",
            full_name="Rohan Verma",
            password_hash=hash_password("StudentSecure@2026"),
            role=UserRole.student,
            roster_id=base_setup["roster"].id,
            is_active=True,
            must_change_password=False,
        )
        db_session.add(student)
        db_session.commit()

        req = create_request(
            session=db_session,
            student_user=student,
            declared_is_hosteller=False,
        )

        # Backdate approvals
        four_days_ago = datetime.now(timezone.utc) - timedelta(days=4)
        for app in req.approvals:
            app.created_at = four_days_ago
        db_session.commit()

        # Run reminder sweep
        first_run_count = process_reminders(session=db_session)
        assert first_run_count >= 1

        # Run second reminder sweep immediately -> should be de-duplicated (0 new queued)
        second_run_count = process_reminders(session=db_session)
        assert second_run_count == 0
    finally:
        settings.REMINDERS_ENABLED = original_enabled
        settings.REMINDER_AFTER_DAYS = original_days


def test_create_first_admin_script(db_session):
    """Verify create_first_admin bootstraps admin account, enforces domain and password length."""
    # 1. Invalid domain
    res_bad_domain = create_first_admin("admin@gmail.com", "AdminSecure@2026", "Test Admin", session=db_session)
    assert res_bad_domain is False

    # 2. Too short password
    res_short_pw = create_first_admin("newadmin@svsu.ac.in", "Short@1", "Test Admin", session=db_session)
    assert res_short_pw is False

    # 3. Successful admin creation
    res_ok = create_first_admin("initial.admin@svsu.ac.in", "AdminSecurePassword@2026", "Initial Admin", session=db_session)
    assert res_ok is True

    admin_record = db_session.execute(
        select(User).where(User.email == "initial.admin@svsu.ac.in")
    ).scalar_one_or_none()
    assert admin_record is not None
    assert admin_record.role == UserRole.admin
    assert admin_record.must_change_password is False
