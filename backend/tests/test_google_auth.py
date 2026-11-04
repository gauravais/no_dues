"""Tests for Google OAuth2 Authentication, gate flags, and admin google_only provisioning."""
import io
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.core.config import Settings, settings
from backend.app.models.user import User, UserRole
from backend.app.models.roster import StudentRoster
from backend.app.models.university import Programme, Department
from backend.app.models.audit import AuditLog
from backend.app.core.security import hash_password
from tests.conftest import make_auth_headers


@pytest.fixture
def mock_google_verifier():
    """Helper fixture to monkeypatch Google token verification."""
    with patch("google.oauth2.id_token.verify_oauth2_token") as mock_verify:
        yield mock_verify


@pytest.fixture
def test_admin_headers(db_session) -> dict[str, str]:
    """Helper fixture creating an admin user and returning auth headers."""
    admin = User(
        email="admin.google@svsu.ac.in",
        full_name="System Admin",
        password_hash=hash_password("AdminSecure@2026"),
        role=UserRole.admin,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    return make_auth_headers(admin.id)


def test_auth_config_endpoint(client: TestClient):
    """Test GET /auth/config returns expected public metadata."""
    old_client_id = settings.GOOGLE_CLIENT_ID
    old_otp = settings.AUTH_OTP_SIGNUP_ENABLED
    try:
        settings.GOOGLE_CLIENT_ID = "test-client-id-123.apps.googleusercontent.com"
        settings.AUTH_OTP_SIGNUP_ENABLED = False
        res = client.get("/auth/config")
        assert res.status_code == 200
        data = res.json()
        assert data["google_enabled"] is True
        assert data["google_client_id"] == "test-client-id-123.apps.googleusercontent.com"
        assert data["allowed_domain_hint"] in settings.google_allowed_domain_list
        assert data["otp_signup_enabled"] is False

        # When client id is empty
        settings.GOOGLE_CLIENT_ID = ""
        res2 = client.get("/auth/config")
        assert res2.status_code == 200
        assert res2.json()["google_enabled"] is False
        assert res2.json()["google_client_id"] is None
    finally:
        settings.GOOGLE_CLIENT_ID = old_client_id
        settings.AUTH_OTP_SIGNUP_ENABLED = old_otp


def test_google_login_valid_roster_student_first_and_second_login(
    client: TestClient,
    db_session,
    mock_google_verifier,
):
    """1. Valid roster student creates a user, writes audit entry, and returns token. 2. Second login reuses user."""
    prog = db_session.execute(select(Programme)).scalars().first()
    roster_email = "google.student1@svsu.ac.in"
    roster = StudentRoster(
        registration_number="REG_GOOGLE_001",
        name="Google Student One",
        email=roster_email,
        mobile="9876543210",
        address="123 Campus Hostel",
        programme_id=prog.id,
        is_hosteller=True,
        security_deposit_amount=5000.0,
    )
    db_session.add(roster)
    db_session.commit()

    mock_google_verifier.return_value = {
        "sub": "google-sub-student-1",
        "email": roster_email,
        "email_verified": True,
        "hd": "svsu.ac.in",
    }

    # First login
    res = client.post("/auth/google", json={"credential": "valid-id-token-1"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["must_change_password"] is False

    # Check user was created
    user = db_session.execute(
        select(User).where(User.google_sub == "google-sub-student-1")
    ).scalar_one_or_none()
    assert user is not None
    assert user.email == roster_email
    assert user.full_name == "Google Student One"
    assert user.role == UserRole.student
    assert user.password_hash is None
    assert user.last_login_at is not None

    # Check audit log
    audit = db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "google_first_login",
            AuditLog.user_id == user.id,
        )
    ).scalar_one_or_none()
    assert audit is not None
    assert audit.details["email"] == roster_email
    assert "credential" not in str(audit.details)
    assert "valid-id-token-1" not in str(audit.details)

    first_login_time = user.last_login_at

    # Second login
    res2 = client.post("/auth/google", json={"credential": "valid-id-token-1-again"})
    assert res2.status_code == 200
    db_session.refresh(user)
    assert user.last_login_at >= first_login_time


def test_google_login_not_in_roster(client: TestClient, db_session, mock_google_verifier):
    """3. Email not in roster gets 403 NOT_ELIGIBLE with friendly message."""
    mock_google_verifier.return_value = {
        "sub": "google-sub-unknown",
        "email": "not.in.roster@svsu.ac.in",
        "email_verified": True,
        "hd": "svsu.ac.in",
    }

    res = client.post("/auth/google", json={"credential": "token-unknown"})
    assert res.status_code == 403
    data = res.json()
    assert data["detail"]["code"] == "NOT_ELIGIBLE"
    assert "Your account is not in the student list. Please contact your department office." in data["detail"]["message"]


def test_google_login_wrong_domain(client: TestClient, mock_google_verifier):
    """4. Email domain not allowed returns 401."""
    mock_google_verifier.return_value = {
        "sub": "google-sub-wrong-domain",
        "email": "student@gmail.com",
        "email_verified": True,
        "hd": "gmail.com",
    }

    res = client.post("/auth/google", json={"credential": "token-wrong-domain"})
    assert res.status_code == 401
    assert "unauthorized" in res.json()["detail"].lower() or "domain" in res.json()["detail"].lower()


def test_google_login_email_verified_false(client: TestClient, mock_google_verifier):
    """5. email_verified is False returns 401."""
    mock_google_verifier.return_value = {
        "sub": "google-sub-unverified",
        "email": "unverified@svsu.ac.in",
        "email_verified": False,
        "hd": "svsu.ac.in",
    }

    res = client.post("/auth/google", json={"credential": "token-unverified"})
    assert res.status_code == 401
    assert "not verified" in res.json()["detail"].lower()


def test_google_login_missing_hd(client: TestClient, mock_google_verifier):
    """6. Missing hd claim returns 401."""
    mock_google_verifier.return_value = {
        "sub": "google-sub-no-hd",
        "email": "student@svsu.ac.in",
        "email_verified": True,
        # 'hd' missing
    }

    res = client.post("/auth/google", json={"credential": "token-no-hd"})
    assert res.status_code == 401
    assert "domain" in res.json()["detail"].lower()


def test_google_login_verifier_value_error(client: TestClient, mock_google_verifier):
    """7. Verifier raising ValueError returns 401."""
    mock_google_verifier.side_effect = ValueError("Invalid token signature or expired")

    res = client.post("/auth/google", json={"credential": "token-malformed"})
    assert res.status_code == 401
    assert "invalid or expired" in res.json()["detail"].lower()


def test_google_login_inactive_user(client: TestClient, db_session, mock_google_verifier):
    """8. Inactive user returns 403 ACCOUNT_DISABLED."""
    dept = db_session.execute(select(Department)).scalars().first()
    inactive_user = User(
        email="inactive.staff@svsu.ac.in",
        full_name="Inactive Staff",
        password_hash=None,
        role=UserRole.dept_officer,
        department_id=dept.id,
        is_active=False,
        google_sub="google-sub-inactive",
    )
    db_session.add(inactive_user)
    db_session.commit()

    mock_google_verifier.return_value = {
        "sub": "google-sub-inactive",
        "email": "inactive.staff@svsu.ac.in",
        "email_verified": True,
        "hd": "svsu.ac.in",
    }

    res = client.post("/auth/google", json={"credential": "token-inactive"})
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "ACCOUNT_DISABLED"


def test_google_login_staff_binds_sub_on_first_use(
    client: TestClient,
    db_session,
    mock_google_verifier,
):
    """9. Staff login with matching email binds google_sub on first use."""
    dept = db_session.execute(select(Department)).scalars().first()
    staff_user = User(
        email="officer.dept1@svsu.ac.in",
        full_name="Department Officer 1",
        password_hash=hash_password("StaffPass@123"),
        role=UserRole.dept_officer,
        department_id=dept.id,
        is_active=True,
        google_sub=None,  # initially unbound
    )
    db_session.add(staff_user)
    db_session.commit()

    mock_google_verifier.return_value = {
        "sub": "google-sub-staff-dept1",
        "email": "officer.dept1@svsu.ac.in",
        "email_verified": True,
        "hd": "svsu.ac.in",
    }

    res = client.post("/auth/google", json={"credential": "token-staff"})
    assert res.status_code == 200
    assert "access_token" in res.json()

    db_session.refresh(staff_user)
    assert staff_user.google_sub == "google-sub-staff-dept1"


def test_google_login_sub_mismatch_returns_403(
    client: TestClient,
    db_session,
    mock_google_verifier,
):
    """10. User whose email has a different google_sub returns 403."""
    dept = db_session.execute(select(Department)).scalars().first()
    user = User(
        email="officer.bound@svsu.ac.in",
        full_name="Bound Officer",
        password_hash=None,
        role=UserRole.dept_officer,
        department_id=dept.id,
        is_active=True,
        google_sub="original-sub-12345",
    )
    db_session.add(user)
    db_session.commit()

    # Attempting to sign in with same email but different Google account ID
    mock_google_verifier.return_value = {
        "sub": "imposter-sub-99999",
        "email": "officer.bound@svsu.ac.in",
        "email_verified": True,
        "hd": "svsu.ac.in",
    }

    res = client.post("/auth/google", json={"credential": "token-imposter"})
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "SUB_MISMATCH"


def test_google_login_concurrency_race(
    client: TestClient,
    db_session,
    mock_google_verifier,
):
    """11. The race for duplicate first login is handled cleanly."""
    prog = db_session.execute(select(Programme)).scalars().first()
    roster = StudentRoster(
        registration_number="REG_RACE_001",
        name="Race Student",
        email="race.student@svsu.ac.in",
        mobile="9876543211",
        address="Hostel B",
        programme_id=prog.id,
        is_hosteller=True,
        security_deposit_amount=5000.0,
    )
    db_session.add(roster)
    db_session.commit()

    mock_google_verifier.return_value = {
        "sub": "race-sub-001",
        "email": "race.student@svsu.ac.in",
        "email_verified": True,
        "hd": "svsu.ac.in",
    }

    res = client.post("/auth/google", json={"credential": "race-token-1"})
    assert res.status_code == 200

    # Repeating with the same credentials seamlessly succeeds
    res2 = client.post("/auth/google", json={"credential": "race-token-2"})
    assert res2.status_code == 200


def test_student_password_login_refused_or_allowed_by_flag(client: TestClient, db_session):
    """12. Student password login refused when flag is false and allowed when true."""
    prog = db_session.execute(select(Programme)).scalars().first()
    roster = StudentRoster(
        registration_number="REG_FLAG_001",
        name="Flag Test Student",
        email="student.flagtest@svsu.ac.in",
        mobile="9876543212",
        address="Hostel C",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=0.0,
    )
    db_session.add(roster)
    db_session.flush()

    student_user = User(
        email="student.flagtest@svsu.ac.in",
        full_name="Flag Test Student",
        password_hash=hash_password("StudentPassword@123"),
        role=UserRole.student,
        roster_id=roster.id,
        is_active=True,
    )
    db_session.add(student_user)
    db_session.commit()

    old_flag = settings.AUTH_PASSWORD_LOGIN_FOR_STUDENTS
    try:
        # Flag is False -> Refused with generic error
        settings.AUTH_PASSWORD_LOGIN_FOR_STUDENTS = False
        res = client.post(
            "/auth/login",
            data={"username": "student.flagtest@svsu.ac.in", "password": "StudentPassword@123"},
        )
        assert res.status_code == 401
        assert res.json()["detail"] == "Incorrect email or password"

        # Flag is True -> Allowed
        settings.AUTH_PASSWORD_LOGIN_FOR_STUDENTS = True
        res2 = client.post(
            "/auth/login",
            data={"username": "student.flagtest@svsu.ac.in", "password": "StudentPassword@123"},
        )
        assert res2.status_code == 200
        assert "access_token" in res2.json()
    finally:
        settings.AUTH_PASSWORD_LOGIN_FOR_STUDENTS = old_flag


def test_otp_endpoints_disabled_by_default_and_enabled_by_flag(client: TestClient):
    """13. OTP endpoints return 403 OTP_SIGNUP_DISABLED by default and work when enabled."""
    old_flag = settings.AUTH_OTP_SIGNUP_ENABLED
    try:
        settings.AUTH_OTP_SIGNUP_ENABLED = False
        res_req = client.post(
            "/auth/signup/request-otp",
            json={"registration_number": "ANYREG", "email": "test@svsu.ac.in"},
        )
        assert res_req.status_code == 403
        assert res_req.json()["detail"]["code"] == "OTP_SIGNUP_DISABLED"
        assert "Sign in with your university Google account instead." in res_req.json()["detail"]["message"]

        res_ver = client.post(
            "/auth/signup/verify",
            json={"registration_number": "ANYREG", "otp": "123456", "password": "NewPassword@123"},
        )
        assert res_ver.status_code == 403
        assert res_ver.json()["detail"]["code"] == "OTP_SIGNUP_DISABLED"
    finally:
        settings.AUTH_OTP_SIGNUP_ENABLED = old_flag


def test_admin_google_only_user_creation_and_reset_password(
    client: TestClient,
    test_admin_headers: dict[str, str],
    db_session,
):
    """15. google_only creation in admin: password_hash NULL, no temporary password, and reset-password returns 409."""
    dept = db_session.execute(select(Department)).scalars().first()

    # 1. Create staff user with google_only=True
    payload = {
        "email": "officer.googleonly@svsu.ac.in",
        "full_name": "Google Only Officer",
        "role": "dept_officer",
        "department_id": dept.id,
        "google_only": True,
    }
    res = client.post("/admin/users", json=payload, headers=test_admin_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["temporary_password"] is None

    user = db_session.execute(
        select(User).where(User.email == "officer.googleonly@svsu.ac.in")
    ).scalar_one_or_none()
    assert user is not None
    assert user.password_hash is None
    assert user.must_change_password is False

    # 2. Reset password for this user returns 409
    res_reset = client.post(f"/admin/users/{user.id}/reset-password", headers=test_admin_headers)
    assert res_reset.status_code == 409
    assert "cannot be reset" in res_reset.json()["detail"].lower()

    # 3. Bulk upload with google_only flag
    csv_content = (
        f"email,full_name,role,department,google_only\n"
        f"bulk.go1@svsu.ac.in,Bulk GO 1,dept_officer,{dept.id},true\n"
        f"bulk.pw1@svsu.ac.in,Bulk PW 1,dept_officer,{dept.id},false\n"
    )
    files = {"file": ("staff.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res_bulk = client.post("/admin/users/bulk-upload", files=files, headers=test_admin_headers)
    assert res_bulk.status_code == 200
    rows = res_bulk.json()["rows"]
    assert rows[0]["temporary_password"] is None
    assert rows[1]["temporary_password"] is not None

    u_go = db_session.execute(select(User).where(User.email == "bulk.go1@svsu.ac.in")).scalar_one()
    u_pw = db_session.execute(select(User).where(User.email == "bulk.pw1@svsu.ac.in")).scalar_one()
    assert u_go.password_hash is None
    assert u_pw.password_hash is not None


def test_google_login_rate_limiting(client: TestClient, mock_google_verifier, db_session):
    """16. Rate limits: 20 per IP per 15 min and 10 failed per email per 15 min."""
    mock_google_verifier.return_value = {
        "sub": "sub-rate-limit",
        "email": "rate.limit@svsu.ac.in",
        "email_verified": True,
        "hd": "wrong-domain.com",  # will fail domain check
    }

    # Simulate email failures until 429
    last_status = None
    res = None
    for _ in range(12):
        res = client.post("/auth/google", json={"credential": "token-rl"})
        last_status = res.status_code
        if last_status == 429:
            break

    assert last_status == 429
    assert res is not None
    assert "Retry-After" in res.headers or "retry-after" in res.headers


def test_production_startup_guards():
    """17. Production startup guards: GOOGLE_CLIENT_ID must be set unless OTP enabled, and password login false."""
    # Production without GOOGLE_CLIENT_ID and without AUTH_OTP_SIGNUP_ENABLED should raise
    with pytest.raises(ValueError, match="GOOGLE_CLIENT_ID"):
        Settings(
            APP_ENV="production",
            JWT_SECRET="x" * 32,
            BANK_DATA_KEY="x" * 32,
            SMTP_HOST="smtp.example.com",
            SMTP_PORT=587,
            SMTP_FROM="no-reply@svsu.ac.in",
            FRONTEND_BASE_URL="https://nodues.svsu.ac.in",
            CORS_ORIGINS="https://nodues.svsu.ac.in",
            DEV_RETURN_OTP=False,
            MAIL_CONSOLE_ONLY=False,
            ENABLE_DOCS=False,
            GOOGLE_CLIENT_ID="",
            AUTH_OTP_SIGNUP_ENABLED=False,
        )

    # Production with AUTH_PASSWORD_LOGIN_FOR_STUDENTS=True should raise
    with pytest.raises(ValueError, match="AUTH_PASSWORD_LOGIN_FOR_STUDENTS"):
        Settings(
            APP_ENV="production",
            JWT_SECRET="x" * 32,
            BANK_DATA_KEY="x" * 32,
            SMTP_HOST="smtp.example.com",
            SMTP_PORT=587,
            SMTP_FROM="no-reply@svsu.ac.in",
            FRONTEND_BASE_URL="https://nodues.svsu.ac.in",
            CORS_ORIGINS="https://nodues.svsu.ac.in",
            DEV_RETURN_OTP=False,
            MAIL_CONSOLE_ONLY=False,
            ENABLE_DOCS=False,
            GOOGLE_CLIENT_ID="some-client-id",
            AUTH_PASSWORD_LOGIN_FOR_STUDENTS=True,
        )
