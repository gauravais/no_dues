"""Test configuration and shared fixtures for the NoDues test suite."""
import os

# If local .env was moved to secure storage outside repo, load it for test runner
_secure_env = os.path.expanduser(r"~\.nodues_secure\backend.env")
if not os.path.exists(".env") and os.path.exists(_secure_env):
    with open(_secure_env, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

import psycopg
from psycopg import sql
import pytest
from alembic.config import Config
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.core.config import settings, assert_local_test_database
from backend.app.core.security import hash_password, create_access_token
from backend.app.api.deps import get_db
from backend.app.main import app
from backend.app.models.university import (
    Faculty, Department, Programme,
    DepartmentKind, DepartmentApplicability,
)
from backend.app.models.roster import StudentRoster, RosterAssignedDepartment
from backend.app.models.lab_course import LabCourse
from backend.app.models.user import User, UserRole
from backend.app.models.bank import BankDetail
from backend.app.models.clearance import (
    ClearanceRequest, DepartmentApproval,
    ClearanceStatus, ApprovalStatus, request_lab_courses,
)
from backend.app.models.certificate import Certificate
from backend.app.models.refund import Refund
from backend.app.models.audit import AuditLog
from backend.app.models.otp import SignupOTP
from backend.app.models.email import EmailOutbox
from backend.app.models.rate_limit import AuthRateLimit

TEST_DB_NAME = "nodues_test"
TEST_DATABASE_URL = (
    f"postgresql+psycopg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{TEST_DB_NAME}"
)
# Guard: tests must refuse to run if their database host is not localhost, 127.0.0.1 or compose service name
assert_local_test_database(TEST_DATABASE_URL)
# Ensure test suites using example.edu fixtures pass alongside svsu.ac.in
if "example.edu" not in settings.allowed_email_domain_list:
    settings.ALLOWED_EMAIL_DOMAINS = f"{settings.ALLOWED_EMAIL_DOMAINS},example.edu"

# Ensure existing test suites with OTP and student password login pass
settings.AUTH_OTP_SIGNUP_ENABLED = True
settings.AUTH_PASSWORD_LOGIN_FOR_STUDENTS = True


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Ensure nodues_test database exists and is migrated to head."""
    # 1. Connect to postgres host and check/create nodues_test
    conn = psycopg.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        dbname="nodues_db",
        autocommit=True,
    )
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB_NAME,))
        if not cur.fetchone():
            cur.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(TEST_DB_NAME),
                    sql.Identifier(settings.POSTGRES_USER),
                )
            )
    conn.close()

    # 2. Run alembic upgrade head on nodues_test
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(alembic_cfg, "head")


@pytest.fixture(scope="session")
def test_engine():
    return create_engine(TEST_DATABASE_URL, poolclass=NullPool, echo=False)


@pytest.fixture(scope="session")
def TestingSessionLocal(test_engine):
    return sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="function")
def db_session(test_engine, TestingSessionLocal):
    """Provides a clean database session per test, resetting operational tables."""
    session = TestingSessionLocal()

    # Clean operational tables
    session.execute(delete(AuthRateLimit))
    session.execute(delete(EmailOutbox))
    session.execute(delete(AuditLog))
    session.execute(delete(Refund))
    session.execute(delete(Certificate))
    session.execute(delete(DepartmentApproval))
    session.execute(delete(request_lab_courses))
    session.execute(delete(ClearanceRequest))
    session.execute(delete(SignupOTP))
    session.execute(delete(BankDetail))
    session.execute(delete(RosterAssignedDepartment))
    session.execute(delete(User))
    session.execute(delete(StudentRoster))
    session.execute(delete(Programme))
    session.execute(delete(LabCourse))
    session.execute(delete(Department))
    session.execute(delete(Faculty))
    session.commit()

    # Seed core structure into nodues_test
    _seed_test_structure(session)

    yield session

    session.close()


def _seed_test_structure(session):
    """Seed minimal university structure into nodues_test for tests."""
    fac = Faculty(name="Skill Faculty of Engineering & Technology", short_code="SFET")
    session.add(fac)
    session.flush()

    # Academic Departments
    cs_dept = Department(
        name="Skill Department of CS/IT",
        kind=DepartmentKind.academic,
        applicability=DepartmentApplicability.OWN_ACADEMIC,
        faculty_id=fac.id,
    )
    auto_dept = Department(
        name="Skill Department of Automotive Studies",
        kind=DepartmentKind.academic,
        applicability=DepartmentApplicability.OWN_ACADEMIC,
        faculty_id=fac.id,
    )
    session.add_all([cs_dept, auto_dept])
    session.flush()

    # Programmes
    btech_ce = Programme(
        name="Bachelor of Technology (B.Tech.) Computer Engineering",
        academic_department_id=cs_dept.id,
    )
    btech_auto = Programme(
        name="Bachelor of Technology Mechanical and Smart Manufacturing",
        academic_department_id=auto_dept.id,
    )
    session.add_all([btech_ce, btech_auto])
    session.flush()

    # Service Departments: ALWAYS
    lib_dept = Department(
        name="Library",
        kind=DepartmentKind.service,
        applicability=DepartmentApplicability.ALWAYS,
        faculty_id=None,
    )
    sports_dept = Department(
        name="Sports",
        kind=DepartmentKind.service,
        applicability=DepartmentApplicability.ALWAYS,
        faculty_id=None,
    )
    session.add_all([lib_dept, sports_dept])

    # Service Departments: HOSTELLER_ONLY
    hostel_dept = Department(
        name="Hostel (Boys/Girls)",
        kind=DepartmentKind.service,
        applicability=DepartmentApplicability.HOSTELLER_ONLY,
        faculty_id=None,
    )
    session.add(hostel_dept)

    # Service Departments: ASSIGNED_ONLY
    lab1_dept = Department(
        name="Lab-1",
        kind=DepartmentKind.service,
        applicability=DepartmentApplicability.ASSIGNED_ONLY,
        faculty_id=None,
    )
    lab2_dept = Department(
        name="Lab-2",
        kind=DepartmentKind.service,
        applicability=DepartmentApplicability.ASSIGNED_ONLY,
        faculty_id=None,
    )
    session.add_all([lab1_dept, lab2_dept])
    session.flush()

    # Staff, HoD, Registrar & Admin Users
    pw = hash_password("TestPass@123")
    admin_user = User(
        email="admin@example.edu",
        full_name="System Administrator (Demo)",
        password_hash=pw,
        role=UserRole.admin,
        department_id=None,
        is_active=True,
    )
    reg_user = User(
        email="registrar.accounts@example.edu",
        full_name="Accounts Officer (Demo)",
        password_hash=pw,
        role=UserRole.registrar_accounts,
        department_id=None,
        is_active=True,
    )
    hod_cs = User(
        email="hod.csit@example.edu",
        full_name="Chairperson CS/IT (Demo)",
        password_hash=pw,
        role=UserRole.hod,
        department_id=cs_dept.id,
        is_active=True,
    )
    hod_auto = User(
        email="hod.auto@example.edu",
        full_name="Chairperson Automotive (Demo)",
        password_hash=pw,
        role=UserRole.hod,
        department_id=auto_dept.id,
        is_active=True,
    )
    officer_lib = User(
        email="library.officer@example.edu",
        full_name="Library Officer (Demo)",
        password_hash=pw,
        role=UserRole.dept_officer,
        department_id=lib_dept.id,
        is_active=True,
    )
    officer_sports = User(
        email="sports.officer@example.edu",
        full_name="Sports Officer (Demo)",
        password_hash=pw,
        role=UserRole.dept_officer,
        department_id=sports_dept.id,
        is_active=True,
    )
    officer_cs = User(
        email="officer.csit@example.edu",
        full_name="CS/IT Officer (Demo)",
        password_hash=pw,
        role=UserRole.dept_officer,
        department_id=cs_dept.id,
        is_active=True,
    )
    officer_lab1 = User(
        email="lab1.officer@example.edu",
        full_name="Lab-1 In-Charge (Demo)",
        password_hash=pw,
        role=UserRole.dept_officer,
        department_id=lab1_dept.id,
        is_active=True,
    )
    officer_lab2 = User(
        email="lab2.officer@example.edu",
        full_name="Lab-2 In-Charge (Demo)",
        password_hash=pw,
        role=UserRole.dept_officer,
        department_id=lab2_dept.id,
        is_active=True,
    )
    officer_hostel = User(
        email="hostel.officer@example.edu",
        full_name="Hostel Warden (Demo)",
        password_hash=pw,
        role=UserRole.dept_officer,
        department_id=hostel_dept.id,
        is_active=True,
    )
    officer_auto = User(
        email="officer.auto@example.edu",
        full_name="Automotive Officer (Demo)",
        password_hash=pw,
        role=UserRole.dept_officer,
        department_id=auto_dept.id,
        is_active=True,
    )
    session.add_all([
        admin_user, reg_user, hod_cs, hod_auto,
        officer_lib, officer_sports, officer_cs,
        officer_lab1, officer_lab2, officer_hostel, officer_auto,
    ])
    session.commit()


@pytest.fixture(scope="function")
def client(db_session):
    """TestClient that uses db_session on nodues_test."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_auth_headers(user_id: int) -> dict[str, str]:
    """Generate Bearer Authorization header for testing."""
    token = create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}
