"""
Tests for deployment configurations, Neon resiliency guards, edge rate limiting,
email backends, internal job endpoints, host guards, and structure seeding.
"""

from unittest.mock import MagicMock, patch
import sys
import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import assert_local_test_database, settings
from backend.app.core.rate_limit import get_client_ip
from backend.app.models.email import EmailOutbox, OutboxStatus
from backend.app.models.university import Department, Faculty, Programme
from backend.app.models.user import User, UserRole
from backend.app.models.roster import StudentRoster
from backend.app.services.email import (
    BrevoEmailSender,
    deliver_outbox_email,
    get_email_sender,
)
from scripts.seed_structure import seed_structure, main as seed_structure_main
from scripts.create_first_admin import main as create_first_admin_main
from scripts.seed_synthetic import assert_local_database_host


# ---------------------------------------------------------------------------
# 1. Database Host Guards
# ---------------------------------------------------------------------------


def test_assert_local_test_database_allows_local_and_blocks_remote():
    """Verify test safety guard allows local test hosts and strictly refuses remote hosts like Neon."""
    # Allowed local hosts
    assert_local_test_database("postgresql+psycopg://user:pass@localhost:5432/nodues_test")
    assert_local_test_database("postgresql+psycopg://user:pass@127.0.0.1:5432/nodues_test")
    assert_local_test_database("postgresql+psycopg://user:pass@nodues_db:5432/nodues_test")

    # Disallowed remote hosts (e.g., Neon serverless)
    with pytest.raises(RuntimeError) as exc_info:
        assert_local_test_database(
            "postgresql+psycopg://user:pass@ep-shiny-star-123456.ap-southeast-1.aws.neon.tech/nodues_prod"
        )
    assert "SECURITY GUARD" in str(exc_info.value)
    assert "ep-shiny-star-123456.ap-southeast-1.aws.neon.tech" in str(exc_info.value)


def test_seed_synthetic_refuses_non_local_host():
    """Verify scripts/seed_synthetic.py strictly refuses non-local database hosts with no override."""
    # Allowed local hosts
    assert_local_database_host("localhost")
    assert_local_database_host("127.0.0.1")
    assert_local_database_host("nodues_db")
    assert_local_database_host("db")

    # Disallowed remote hosts
    remote_hosts = [
        "ep-cold-star-123456.ap-southeast-1.aws.neon.tech",
        "db.render.internal",
        "remote-postgres.edu",
        "192.0.2.1",
    ]
    for r_host in remote_hosts:
        with pytest.raises(RuntimeError) as exc_info:
            assert_local_database_host(r_host)
        assert "Refusing to run seed_synthetic against non-local database host" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 2. Host Typing Confirmation in seed_structure and create_first_admin
# ---------------------------------------------------------------------------


def test_seed_structure_host_confirmation(monkeypatch):
    """Verify seed_structure requires typing host name unless --yes is passed."""
    # Case A: --yes skips prompt
    monkeypatch.setattr(sys, "argv", ["seed_structure.py", "--yes"])
    with patch("scripts.seed_structure.seed_structure") as mock_seed:
        seed_structure_main()
        assert mock_seed.called

    # Case B: Interactive without --yes, typed host matches
    monkeypatch.setattr(sys, "argv", ["seed_structure.py"])
    monkeypatch.setattr("scripts.seed_structure.get_db_host", lambda: "localhost")
    monkeypatch.setattr("builtins.input", lambda prompt: "localhost")
    with patch("scripts.seed_structure.seed_structure") as mock_seed:
        seed_structure_main()
        assert mock_seed.called

    # Case C: Interactive without --yes, typed host mismatch -> aborts
    monkeypatch.setattr(sys, "argv", ["seed_structure.py"])
    monkeypatch.setattr("scripts.seed_structure.get_db_host", lambda: "localhost")
    monkeypatch.setattr("builtins.input", lambda prompt: "wrong-host")
    with patch("scripts.seed_structure.seed_structure") as mock_seed:
        with pytest.raises(SystemExit) as exc:
            seed_structure_main()
        assert exc.value.code == 1
        assert not mock_seed.called


def test_create_first_admin_host_confirmation(monkeypatch, db_session):
    """Verify create_first_admin strictly refuses --yes and requires typing host name."""
    from backend.app.core.database import engine
    actual_host = engine.url.host or "localhost"

    # Case A: --yes is strictly refused
    monkeypatch.setattr(sys, "argv", ["create_first_admin.py", "--yes"])
    with pytest.raises(SystemExit) as exc:
        create_first_admin_main()
    assert exc.value.code == 1

    # Case B: Interactive confirmation mismatch -> aborts with code 1
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "create_first_admin.py",
            "--email", "admin.new@svsu.ac.in",
            "--password", "StrongPass@1234",
            "--name", "System Admin",
        ],
    )
    monkeypatch.setattr("builtins.input", lambda prompt: "different_and_wrong_host")
    with pytest.raises(SystemExit) as exc:
        create_first_admin_main()
    assert exc.value.code == 1

    # Case C: Interactive confirmation matching host -> proceeds
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "create_first_admin.py",
            "--email", "admin.new@example.edu",
            "--password", "StrongPass@1234",
            "--name", "System Admin",
        ],
    )
    monkeypatch.setattr("builtins.input", lambda prompt: actual_host)
    with pytest.raises(SystemExit) as exc:
        create_first_admin_main()
    assert exc.value.code == 0
    from backend.app.core.database import SessionLocal
    with SessionLocal() as check_session:
        created = check_session.query(User).filter(User.email == "admin.new@example.edu").first()
        assert created is not None
        assert created.role == UserRole.admin


# ---------------------------------------------------------------------------
# 3. Health Endpoints
# ---------------------------------------------------------------------------


def test_health_live_endpoint(client: TestClient):
    """Verify /health/live returns 200 OK without requiring a database query."""
    resp = client.get("/health/live")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "environment" in data


# ---------------------------------------------------------------------------
# 4. Client IP & Configurable Header Spoof Defense
# ---------------------------------------------------------------------------


def test_client_ip_configurable_header_defense():
    """Verify get_client_ip adheres to TRUSTED_CLIENT_IP_HEADER setting."""
    req = MagicMock()
    req.headers = {
        "x-forwarded-for": "198.51.100.99, 10.0.0.1",
        "true-client-ip": "203.0.113.5",
    }
    req.client.host = "127.0.0.1"

    # Default: TRUSTED_CLIENT_IP_HEADER empty -> uses direct socket address only
    with patch.object(settings, "TRUSTED_CLIENT_IP_HEADER", ""):
        assert get_client_ip(req) == "127.0.0.1"

    # Configured: TRUSTED_CLIENT_IP_HEADER="True-Client-IP" -> reads True-Client-IP
    with patch.object(settings, "TRUSTED_CLIENT_IP_HEADER", "True-Client-IP"):
        assert get_client_ip(req) == "203.0.113.5"

    # Configured: TRUSTED_CLIENT_IP_HEADER="X-Forwarded-For" -> extracts leftmost client IP
    with patch.object(settings, "TRUSTED_CLIENT_IP_HEADER", "X-Forwarded-For"):
        assert get_client_ip(req) == "198.51.100.99"

    # Configured header missing -> securely falls back to socket host
    req_no_header = MagicMock()
    req_no_header.headers = {}
    req_no_header.client.host = "10.0.0.5"
    with patch.object(settings, "TRUSTED_CLIENT_IP_HEADER", "True-Client-IP"):
        assert get_client_ip(req_no_header) == "10.0.0.5"


# ---------------------------------------------------------------------------
# 5. Rate Limiting Independence of Client IP
# ---------------------------------------------------------------------------


def test_login_rate_limit_per_email_independent_of_ip(client: TestClient):
    """Verify per-email login lockout triggers after 5 failed attempts even if IP address rotates."""
    target_email = "admin@example.edu"

    with patch.object(settings, "TRUSTED_CLIENT_IP_HEADER", "True-Client-IP"):
        # 5 failed login attempts from 5 different client IPs
        for i in range(1, 6):
            resp = client.post(
                "/auth/login",
                data={"username": target_email, "password": "WrongPassword!"},
                headers={"True-Client-IP": f"198.51.100.{i}"},
            )
            assert resp.status_code == 401

        # 6th attempt from a brand-new 6th IP: per-email rate limit locks out account
        resp_6th = client.post(
            "/auth/login",
            data={"username": target_email, "password": "WrongPassword!"},
            headers={"True-Client-IP": "198.51.100.99"},
        )
        assert resp_6th.status_code == 429
        assert "Too many attempts" in resp_6th.json()["detail"]
        assert "Retry-After" in resp_6th.headers


def test_signup_otp_rate_limit_per_reg_num_independent_of_ip(client: TestClient, db_session):
    """Verify per-registration-number signup OTP lockout triggers after 3 attempts even if IP rotates."""
    prog = db_session.query(Programme).first()
    assert prog is not None

    # Add eligible student in roster
    roster_entry = StudentRoster(
        registration_number="REG2026RATE01",
        name="Test Rate Student",
        email="ratestudent@example.edu",
        mobile="9876543210",
        address="Campus",
        programme_id=prog.id,
        is_hosteller=False,
    )
    db_session.add(roster_entry)
    db_session.commit()

    with patch.object(settings, "AUTH_OTP_SIGNUP_ENABLED", True):
        with patch.object(settings, "TRUSTED_CLIENT_IP_HEADER", "True-Client-IP"):
            # 3 OTP requests from 3 different client IPs
            for i in range(1, 4):
                resp = client.post(
                    "/auth/signup/request-otp",
                    json={
                        "registration_number": "REG2026RATE01",
                        "email": "ratestudent@example.edu",
                    },
                    headers={"True-Client-IP": f"203.0.113.{i}"},
                )
                assert resp.status_code == 200

            # 4th request from a brand-new 4th IP: per-registration-number limit locks out
            resp_4th = client.post(
                "/auth/signup/request-otp",
                json={
                    "registration_number": "REG2026RATE01",
                    "email": "ratestudent@example.edu",
                },
                headers={"True-Client-IP": "203.0.113.88"},
            )
            assert resp_4th.status_code == 429
            assert "Too many attempts" in resp_4th.json()["detail"]
            assert "Retry-After" in resp_4th.headers


# ---------------------------------------------------------------------------
# 6. Email Backends & Outbox Delivery
# ---------------------------------------------------------------------------


def test_email_backend_disabled_mode(db_session):
    """When EMAIL_BACKEND=disabled, outbox delivery marks item SKIPPED with 'email disabled'."""
    outbox = EmailOutbox(
        to_email="test.student@svsu.ac.in",
        subject="Test Disabled",
        body="Body text",
        kind="test",
        status=OutboxStatus.PENDING,
    )
    db_session.add(outbox)
    db_session.commit()

    with patch.object(settings, "EMAIL_BACKEND", "disabled"):
        res = deliver_outbox_email(db_session, outbox)
        assert res is True
        assert outbox.status == OutboxStatus.SKIPPED
        assert outbox.last_error == "email disabled"


def test_email_allowlist_enforcement(db_session):
    """When EMAIL_ALLOWLIST is set, non-allowlisted recipients are SKIPPED."""
    outbox = EmailOutbox(
        to_email="nonallowlisted@svsu.ac.in",
        subject="Test Allowlist",
        body="Body text",
        kind="test",
        status=OutboxStatus.PENDING,
    )
    db_session.add(outbox)
    db_session.commit()

    with patch.object(settings, "EMAIL_ALLOWLIST", "vip@svsu.ac.in"):
        res = deliver_outbox_email(db_session, outbox)
        assert res is True
        assert outbox.status == OutboxStatus.SKIPPED
        assert "EMAIL_ALLOWLIST" in outbox.last_error


def test_brevo_email_sender_success_and_error():
    """Verify Brevo HTTPS POST payload structure, success, and error handling."""
    sender = BrevoEmailSender()

    with patch.object(settings, "BREVO_API_KEY", "xkeysib-test-123"):
        with patch.object(settings, "EMAIL_FROM", "noreply@svsu.ac.in"):
            with patch("requests.post") as mock_post:
                # 1. Success response (201 Created)
                mock_post.return_value.status_code = 201
                sender.send(
                    to_email="recipient@svsu.ac.in",
                    subject="Brevo Test",
                    body="Hello Brevo",
                )
                assert mock_post.called
                url, kwargs = mock_post.call_args
                assert url[0] == "https://api.brevo.com/v3/smtp/email"
                assert kwargs["headers"]["api-key"] == "xkeysib-test-123"
                assert kwargs["json"]["to"] == [{"email": "recipient@svsu.ac.in"}]
                assert kwargs["json"]["sender"]["email"] == "noreply@svsu.ac.in"

                # 2. Failure response (401 Unauthorized)
                mock_post.return_value.status_code = 401
                mock_post.return_value.text = "Invalid API key"
                with pytest.raises(RuntimeError) as exc_err:
                    sender.send(
                        to_email="recipient@svsu.ac.in",
                        subject="Brevo Test",
                        body="Hello Brevo",
                    )
                assert "HTTP 401" in str(exc_err.value)


# ---------------------------------------------------------------------------
# 7. Internal Scheduled Job Endpoints
# ---------------------------------------------------------------------------


def test_internal_jobs_authentication(client: TestClient):
    """Verify /internal/jobs/* endpoints enforce JOB_SECRET and X-Job-Key."""
    # Case 1: Server has JOB_SECRET unset -> 503 Service Unavailable
    with patch.object(settings, "JOB_SECRET", ""):
        resp = client.post(
            "/internal/jobs/send-emails",
            headers={"X-Job-Key": "some-key"},
        )
        assert resp.status_code == 503
        assert "not configured" in resp.json()["detail"]

    # Case 2: Server has JOB_SECRET set, request provides incorrect key -> 401 Unauthorized
    with patch.object(settings, "JOB_SECRET", "super-secret-job-token"):
        resp = client.post(
            "/internal/jobs/send-emails",
            headers={"X-Job-Key": "wrong-key"},
        )
        assert resp.status_code == 401
        assert "Invalid or missing" in resp.json()["detail"]

        # Case 3: Correct key -> 200 OK with processed count
        with patch("backend.app.api.routes.internal_jobs.process_pending_emails", return_value=0):
            resp = client.post(
                "/internal/jobs/send-emails",
                headers={"X-Job-Key": "super-secret-job-token"},
            )
            assert resp.status_code == 200
            assert resp.json() == {"processed": 0}

        # Case 4: Correct key for send-reminders -> 200 OK with queued count
        with patch("backend.app.api.routes.internal_jobs.process_reminders", return_value=0):
            resp = client.post(
                "/internal/jobs/send-reminders",
                headers={"X-Job-Key": "super-secret-job-token"},
            )
            assert resp.status_code == 200
            assert resp.json() == {"queued": 0}


# ---------------------------------------------------------------------------
# 8. Production-Safe Structure Seed
# ---------------------------------------------------------------------------


def test_seed_structure_idempotent_and_zero_users(db_session):
    """Verify seed_structure creates faculties, departments, and programmes with 0 new users."""
    initial_user_count = db_session.query(User).count()

    # Run seed_structure
    res1 = seed_structure(db_session)
    assert res1["faculty_id"] is not None
    assert len(res1["academic_dept_ids"]) == 6
    assert len(res1["service_dept_ids"]) == 10  # 9 ALWAYS + 1 HOSTELLER
    assert len(res1["assigned_dept_ids"]) == 1  # 1 others (additional facility)

    # Verify zero users created
    user_count = db_session.query(User).count()
    assert user_count == initial_user_count

    dept_count_after_first = db_session.query(Department).count()

    # Verify idempotency: running again succeeds without creating duplicates
    res2 = seed_structure(db_session)
    assert res2["faculty_id"] == res1["faculty_id"]
    assert db_session.query(Faculty).count() == 1
    assert db_session.query(Department).count() == dept_count_after_first
    assert db_session.query(User).count() == initial_user_count
