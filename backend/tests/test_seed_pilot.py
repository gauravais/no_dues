"""
Tests for pilot seed script (seed_synthetic.py):
1. Seed creates no students (zero student roster/user records).
2. --remove-demo-students cleans only DEMO rows and dependents while preserving real student data.
3. --remove-demo-students and --reset refuse if real students exist unless --i-know-real-data-exists is passed.
4. --reset never deletes real roster rows.
5. --migrate-staff-domain renames staff and reports collisions.
6. Safety: production refusal when APP_ENV=production.
7. Safety: domain validation against ALLOWED_EMAIL_DOMAINS.
"""
import pytest
from sqlalchemy import select, func, not_

from backend.app.core.config import settings
from backend.app.models.university import Faculty, Department, Programme, DepartmentKind, DepartmentApplicability
from backend.app.models.roster import StudentRoster
from backend.app.models.user import User, UserRole
from backend.app.models.bank import BankDetail
from backend.app.models.clearance import ClearanceRequest, DepartmentApproval, ClearanceStatus, ApprovalStatus
from backend.app.models.certificate import Certificate
from backend.app.models.refund import Refund, RefundStatus
from backend.app.models.otp import SignupOTP
from backend.app.models.audit import AuditLog
from backend.app.core.security import hash_password

from scripts.seed_synthetic import (
    seed,
    remove_demo_students,
    migrate_staff_domain,
    reset_data,
    check_environment_and_domain,
    check_real_data_guard,
)


def test_seed_creates_zero_students(db_session, monkeypatch):
    """Seed must create university structure and staff accounts under staff_domain, but ZERO students."""
    monkeypatch.setattr(settings, "SEED_DEFAULT_PASSWORD", "TestSeedPass@123")
    monkeypatch.setattr(settings, "SEED_STAFF_EMAIL_DOMAIN", "svsu.ac.in")

    staff_emails = seed(db_session, staff_domain="svsu.ac.in")

    # 1. Verify zero student roster records
    student_roster_count = db_session.scalar(select(func.count(StudentRoster.id)))
    assert student_roster_count == 0

    # 2. Verify zero student user accounts
    student_users_count = db_session.scalar(
        select(func.count(User.id)).where(User.role == UserRole.student)
    )
    assert student_users_count == 0

    # 3. Verify zero bank details
    bank_count = db_session.scalar(select(func.count(BankDetail.id)))
    assert bank_count == 0

    # 4. Verify staff accounts were created with @svsu.ac.in
    assert len(staff_emails) > 0
    assert "admin@svsu.ac.in" in staff_emails
    assert "registrar.accounts@svsu.ac.in" in staff_emails
    assert "library.officer@svsu.ac.in" in staff_emails
    assert "officer.csit@svsu.ac.in" in staff_emails
    assert "hod.csit@svsu.ac.in" in staff_emails

    for email in staff_emails:
        assert email.endswith("@svsu.ac.in")


def test_remove_demo_students_cleans_only_demo(db_session):
    """--remove-demo-students removes only DEMO roster rows and their dependents, leaving real data intact."""
    # Ensure a programme exists
    prog = db_session.scalars(select(Programme)).first()
    dept = db_session.scalars(select(Department).where(Department.kind == DepartmentKind.academic)).first()
    pw_hash = hash_password("SecretPass@123")

    # 1. Real student (registration does NOT start with DEMO)
    real_roster = StudentRoster(
        registration_number="REAL2026001",
        name="Real Pilot Student",
        email="real.student@svsu.ac.in",
        mobile="9811111111",
        address="Real Campus Address",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=5000.0,
    )
    db_session.add(real_roster)
    db_session.flush()

    real_user = User(
        email="real.student@svsu.ac.in",
        full_name="Real Pilot Student",
        password_hash=pw_hash,
        role=UserRole.student,
        roster_id=real_roster.id,
        is_active=True,
    )
    real_bank = BankDetail(
        roster_id=real_roster.id,
        account_holder_name="Real Pilot Student",
        account_number="123456789012",
        ifsc_code="SBIN0001234",
        bank_address="Real Campus Bank",
    )
    db_session.add_all([real_user, real_bank])
    db_session.flush()

    # 2. Demo student (registration starts with DEMO)
    demo_roster = StudentRoster(
        registration_number="DEMO2026999",
        name="Demo Cleanup Student",
        email="demo.cleanup@example.edu",
        mobile="9800000999",
        address="Demo Address",
        programme_id=prog.id,
        is_hosteller=True,
        security_deposit_amount=5000.0,
    )
    db_session.add(demo_roster)
    db_session.flush()

    demo_user = User(
        email="demo.cleanup@example.edu",
        full_name="Demo Cleanup Student",
        password_hash=pw_hash,
        role=UserRole.student,
        roster_id=demo_roster.id,
        is_active=True,
    )
    demo_bank = BankDetail(
        roster_id=demo_roster.id,
        account_holder_name="Demo Cleanup Student",
        account_number="987654321098",
        ifsc_code="DEMO0001234",
        bank_address="Demo Bank Address",
    )
    db_session.add_all([demo_user, demo_bank])
    db_session.flush()

    # Create request, approval, cert, refund, and signup OTP for demo student
    demo_req = ClearanceRequest(
        roster_id=demo_roster.id,
        status=ClearanceStatus.CLEARED,
        declared_is_hosteller=True,
    )
    db_session.add(demo_req)
    db_session.flush()

    demo_appr = DepartmentApproval(
        request_id=demo_req.id,
        department_id=dept.id,
        status=ApprovalStatus.APPROVED,
        remarks="Demo cleared",
    )
    demo_cert = Certificate(
        request_id=demo_req.id,
        certificate_code="DEMO-CERT-UUID-999",
        hod_user_id=real_user.id,
    )
    demo_refund = Refund(
        request_id=demo_req.id,
        deposit_amount=5000.0,
        deductions=0,
        final_amount=5000.0,
        status=RefundStatus.PENDING_VERIFICATION,
    )
    demo_otp = SignupOTP(
        email="demo.cleanup@example.edu",
        registration_number="DEMO2026999",
        code_hash="demo_hash",
        expires_at=demo_req.created_at,
    )
    demo_audit = AuditLog(
        user_id=demo_user.id,
        action="TEST_ACTION",
        entity_type="StudentRoster",
        entity_id=demo_roster.id,
    )
    db_session.add_all([demo_appr, demo_cert, demo_refund, demo_otp, demo_audit])
    db_session.commit()

    demo_req_id = demo_req.id
    demo_roster_id = demo_roster.id
    real_roster_id = real_roster.id

    # Run remove_demo_students with explicit real data override
    counts = remove_demo_students(db_session, yes=True, i_know_real_data_exists=True)

    # Verify counts
    assert counts["student_roster"] == 1
    assert counts["users"] == 1
    assert counts["bank_details"] == 1
    assert counts["clearance_requests"] == 1
    assert counts["department_approvals"] == 1
    assert counts["certificates"] == 1
    assert counts["refunds"] == 1
    assert counts["signup_otps"] == 1

    # Verify demo student records are gone
    assert db_session.scalar(select(StudentRoster).where(StudentRoster.registration_number == "DEMO2026999")) is None
    assert db_session.scalar(select(User).where(User.email == "demo.cleanup@example.edu")) is None
    assert db_session.scalar(select(ClearanceRequest).where(ClearanceRequest.id == demo_req_id)) is None

    # Verify real student records remain intact
    real_db_roster = db_session.scalar(select(StudentRoster).where(StudentRoster.registration_number == "REAL2026001"))
    assert real_db_roster is not None
    assert real_db_roster.email == "real.student@svsu.ac.in"

    real_db_user = db_session.scalar(select(User).where(User.email == "real.student@svsu.ac.in"))
    assert real_db_user is not None

    real_db_bank = db_session.scalar(select(BankDetail).where(BankDetail.roster_id == real_roster_id))
    assert real_db_bank is not None

    # Verify audit log row was preserved (not deleted), but user_id is now None
    audit_row = db_session.scalar(select(AuditLog).where(AuditLog.id == demo_audit.id))
    assert audit_row is not None
    assert audit_row.user_id is None


def test_guard_refuses_when_real_students_exist(db_session):
    """Destructive operations (--reset, --remove-demo-students) refuse if real students exist without override."""
    prog = db_session.scalars(select(Programme)).first()
    real_roster = StudentRoster(
        registration_number="REAL2026002",
        name="Real Guard Student",
        email="real.guard@svsu.ac.in",
        mobile="9822222222",
        address="Real Campus Address",
        programme_id=prog.id,
        is_hosteller=False,
    )
    db_session.add(real_roster)
    db_session.commit()

    # Calling check_real_data_guard without flag must exit
    with pytest.raises(SystemExit) as exc:
        check_real_data_guard(db_session, i_know_real_data_exists=False)
    assert exc.value.code == 1

    # Calling with flag succeeds
    check_real_data_guard(db_session, i_know_real_data_exists=True)


def test_reset_never_deletes_real_roster_rows(db_session):
    """--reset must NEVER delete real student roster rows, even with override flag."""
    prog = db_session.scalars(select(Programme)).first()
    pw_hash = hash_password("SecretPass@123")

    real_roster = StudentRoster(
        registration_number="REAL2026003",
        name="Real Reset Student",
        email="real.reset@svsu.ac.in",
        mobile="9833333333",
        address="Real Campus Address",
        programme_id=prog.id,
        is_hosteller=False,
    )
    demo_roster = StudentRoster(
        registration_number="DEMO2026001",
        name="Demo Reset Student",
        email="demo.reset@example.edu",
        mobile="9800000001",
        address="Demo Address",
        programme_id=prog.id,
        is_hosteller=False,
    )
    db_session.add_all([real_roster, demo_roster])
    db_session.commit()

    # Run reset_data with override
    reset_data(db_session, i_know_real_data_exists=True)

    # Real student roster row MUST still exist
    real_after = db_session.scalar(select(StudentRoster).where(StudentRoster.registration_number == "REAL2026003"))
    assert real_after is not None

    # Demo student roster row MUST be gone
    demo_after = db_session.scalar(select(StudentRoster).where(StudentRoster.registration_number == "DEMO2026001"))
    assert demo_after is None


def test_migrate_staff_domain_renames_and_handles_collisions(db_session):
    """--migrate-staff-domain renames @example.edu staff to SEED_STAFF_EMAIL_DOMAIN and reports collisions."""
    dept = db_session.scalars(select(Department).where(Department.kind == DepartmentKind.academic)).first()
    pw_hash = hash_password("SecretPass@123")

    # Use existing seeded staff user (library.officer@example.edu) plus a colliding user
    staff_colliding = User(
        email="colliding.officer@example.edu",
        full_name="Colliding Officer",
        password_hash=pw_hash,
        role=UserRole.dept_officer,
        department_id=dept.id,
        is_active=True,
    )
    # Existing user with target email
    existing_target = User(
        email="colliding.officer@svsu.ac.in",
        full_name="Existing Target User",
        password_hash=pw_hash,
        role=UserRole.dept_officer,
        department_id=dept.id,
        is_active=True,
    )
    db_session.add_all([staff_colliding, existing_target])
    db_session.commit()

    renamed, collisions = migrate_staff_domain(db_session, staff_domain="svsu.ac.in")

    assert "library.officer@svsu.ac.in" in renamed
    assert ("colliding.officer@example.edu", "colliding.officer@svsu.ac.in") in collisions

    # Check database state
    user_lib = db_session.scalar(select(User).where(User.email == "library.officer@svsu.ac.in"))
    assert user_lib is not None

    user2 = db_session.scalar(select(User).where(User.id == staff_colliding.id))
    assert user2.email == "colliding.officer@example.edu"  # Unchanged due to collision


def test_production_refusal(monkeypatch):
    """Script refuses to run synthetic seed in production."""
    monkeypatch.setattr(settings, "APP_ENV", "production")

    with pytest.raises(SystemExit) as exc:
        check_environment_and_domain("svsu.ac.in")
    assert exc.value.code == 1


def test_domain_validation_against_allowed_email_domains(monkeypatch):
    """Script validates SEED_STAFF_EMAIL_DOMAIN against ALLOWED_EMAIL_DOMAINS."""
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "ALLOWED_EMAIL_DOMAINS", "svsu.ac.in")

    # Allowed domain succeeds
    check_environment_and_domain("svsu.ac.in")

    # Disallowed domain exits with code 1
    with pytest.raises(SystemExit) as exc:
        check_environment_and_domain("unauthorized-domain.com")
    assert exc.value.code == 1
