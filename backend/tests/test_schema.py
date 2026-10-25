"""
Schema constraint tests for the NoDues Clearance System.

All DB tests run inside a transaction + savepoint that is rolled back after
each test function, so no permanent state is written.

Run from backend/:
    uv run pytest tests/ -v
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from backend.app.core.config import settings
from backend.app.models.university import (
    Faculty, Department, Programme,
    DepartmentKind, DepartmentApplicability,
)
from backend.app.models.roster import StudentRoster
from backend.app.models.user import User, UserRole
from backend.app.models.clearance import (
    ClearanceRequest, DepartmentApproval,
    ClearanceStatus, ApprovalStatus,
)
from backend.app.models.bank import mask_account_number


# ---------------------------------------------------------------------------
# Session fixture — each test gets a fresh savepoint, rolled back on teardown
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def db_engine():
    test_db_url = (
        f"postgresql+psycopg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/nodues_test"
    )
    return create_engine(test_db_url, echo=False)


@pytest.fixture(scope="function")
def session(db_engine):
    """Wrap every test in a savepoint; roll everything back at the end."""
    connection = db_engine.connect()
    outer_tx = connection.begin()

    Session = sessionmaker(bind=connection)
    sess = Session()
    sess.begin_nested()  # savepoint

    @event.listens_for(sess, "after_transaction_end")
    def restart_savepoint(session, transaction):
        # Keep re-creating the savepoint so the session stays usable after
        # an IntegrityError (which rolls back to the savepoint).
        if transaction.nested and not transaction._parent.nested:
            session.begin_nested()

    yield sess

    sess.close()
    outer_tx.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# Helpers: seed the minimum FK prerequisites each test may need
# ---------------------------------------------------------------------------

def _make_faculty_and_academic_dept(session):
    faculty = Faculty(name="Test Faculty TS", short_code="TFTS")
    session.add(faculty)
    session.flush()

    dept = Department(
        name="Test Academic Dept TS",
        kind=DepartmentKind.academic,
        applicability=DepartmentApplicability.OWN_ACADEMIC,
        faculty_id=faculty.id,
    )
    session.add(dept)
    session.flush()
    return faculty, dept


def _make_roster(session, dept_id):
    prog = Programme(name="Test Programme TS", academic_department_id=dept_id)
    session.add(prog)
    session.flush()

    roster = StudentRoster(
        registration_number="TS0001",
        name="Test Student",
        email="test.student.ts@example.edu",
        mobile="9999999999",
        address="1 Test Lane",
        programme_id=prog.id,
        is_hosteller=False,
    )
    session.add(roster)
    session.flush()
    return roster


def _make_clearance_request(session, roster_id):
    now = datetime.now(timezone.utc)
    req = ClearanceRequest(
        roster_id=roster_id,
        status=ClearanceStatus.SUBMITTED,
        submitted_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(req)
    session.flush()
    return req


# ---------------------------------------------------------------------------
# 1. Duplicate (request_id, department_id) approval must be rejected
# ---------------------------------------------------------------------------

def test_duplicate_approval_rejected(session):
    _, dept = _make_faculty_and_academic_dept(session)
    roster = _make_roster(session, dept.id)
    req = _make_clearance_request(session, roster.id)
    now = datetime.now(timezone.utc)

    a1 = DepartmentApproval(
        request_id=req.id,
        department_id=dept.id,
        status=ApprovalStatus.PENDING,
        resubmission_count=0,
        created_at=now,
        updated_at=now,
    )
    session.add(a1)
    session.flush()

    a2 = DepartmentApproval(
        request_id=req.id,
        department_id=dept.id,     # same (request, dept) → violates UNIQUE
        status=ApprovalStatus.PENDING,
        resubmission_count=0,
        created_at=now,
        updated_at=now,
    )
    session.add(a2)
    with pytest.raises(IntegrityError):
        session.flush()


# ---------------------------------------------------------------------------
# 2. Invalid status value must be rejected at the DB level
# ---------------------------------------------------------------------------

def test_invalid_approval_status_rejected(session):
    _, dept = _make_faculty_and_academic_dept(session)
    roster = _make_roster(session, dept.id)
    req = _make_clearance_request(session, roster.id)
    now = datetime.now(timezone.utc)

    with pytest.raises(Exception):   # psycopg raises DataError / LookupError for bad enum
        session.execute(
            text(
                "INSERT INTO department_approvals "
                "(request_id, department_id, status, resubmission_count, created_at, updated_at) "
                "VALUES (:rid, :did, 'INVALID_STATUS'::approval_status, 0, :now, :now)"
            ),
            {"rid": req.id, "did": dept.id, "now": now},
        )
        session.flush()


# ---------------------------------------------------------------------------
# 3. dept_officer without a department must be rejected
# ---------------------------------------------------------------------------

def test_dept_officer_without_department_rejected(session):
    now = datetime.now(timezone.utc)
    user = User(
        email="orphan.officer.ts@example.edu",
        password_hash="fakehash",
        role=UserRole.dept_officer,
        department_id=None,     # violates CHECK ck_user_dept_officer_hod_requires_dept
        roster_id=None,
        is_active=True,
        created_at=now,
    )
    session.add(user)
    with pytest.raises(IntegrityError):
        session.flush()


# ---------------------------------------------------------------------------
# 4. Academic department without faculty_id must be rejected
# ---------------------------------------------------------------------------

def test_academic_department_without_faculty_rejected(session):
    dept = Department(
        name="Bad Academic Dept TS",
        kind=DepartmentKind.academic,
        applicability=DepartmentApplicability.OWN_ACADEMIC,
        faculty_id=None,        # violates CHECK ck_department_kind_faculty_applicability
    )
    session.add(dept)
    with pytest.raises(IntegrityError):
        session.flush()


# ---------------------------------------------------------------------------
# 5. Service department with a faculty_id must be rejected
# ---------------------------------------------------------------------------

def test_service_department_with_faculty_rejected(session):
    faculty = Faculty(name="Extra Faculty TS", short_code="EFTS")
    session.add(faculty)
    session.flush()

    dept = Department(
        name="Bad Service Dept TS",
        kind=DepartmentKind.service,
        applicability=DepartmentApplicability.ALWAYS,
        faculty_id=faculty.id,  # violates CHECK — service depts must have faculty_id IS NULL
    )
    session.add(dept)
    with pytest.raises(IntegrityError):
        session.flush()


# ---------------------------------------------------------------------------
# 6. mask_account_number helper
# ---------------------------------------------------------------------------

def test_mask_account_number_basic():
    assert mask_account_number("123456781234") == "********1234"


def test_mask_account_number_exactly_four():
    """A 4-digit account number: zero mask chars, just the last 4."""
    assert mask_account_number("1234") == "1234"


def test_mask_account_number_short_raises():
    """Fewer than 4 digits must raise ValueError."""
    with pytest.raises(ValueError):
        mask_account_number("123")


def test_mask_account_number_various_lengths():
    assert mask_account_number("00001234") == "****1234"
    assert mask_account_number("9876543210") == "******3210"
