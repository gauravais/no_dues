"""Comprehensive tests for the complete refund loop: state transitions, validations,
auditing, student issues, queue tabs, CSV export, and migration 0013 roundtrip."""
import io
import csv
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from alembic.config import Config
from alembic import command

from backend.app.models.user import User, UserRole
from backend.app.models.roster import StudentRoster
from backend.app.models.clearance import ClearanceRequest, ClearanceStatus, ApprovalStatus
from backend.app.models.refund import Refund, RefundStatus, PaymentMode
from backend.app.models.audit import AuditLog
from backend.app.models.university import Programme, Department
from backend.app.models.bank import BankDetail
from backend.app.core.security import hash_password
from backend.app.services.workflow import create_request, decide_approval, hod_decide
from tests.conftest import make_auth_headers, TEST_DATABASE_URL


def _setup_cleared_student(db: Session, reg_num: str = "REF001", email: str = "ref001@example.edu"):
    prog = db.execute(select(Programme)).scalars().first()
    pw = hash_password("Secret123!")
    roster = StudentRoster(
        registration_number=reg_num,
        name=f"Student {reg_num}",
        email=email,
        mobile="9800000099",
        address="10 Campus Road",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=Decimal("5000.00"),
    )
    db.add(roster)
    db.flush()

    db.add(
        BankDetail(
            roster_id=roster.id,
            account_holder_name=f"Student {reg_num}",
            account_number="123456789012",
            ifsc_code="DEMO0009001",
            bank_address="Demo Bank, Main",
        )
    )
    db.flush()

    user = User(
        email=email,
        password_hash=pw,
        role=UserRole.student,
        roster_id=roster.id,
        is_active=True,
    )
    db.add(user)
    db.flush()

    req = create_request(db, user)
    # Approve all approvals
    for app in req.approvals:
        officer = db.execute(select(User).where(User.department_id == app.department_id)).scalars().first()
        if not officer:
            officer = User(
                email=f"temp.officer.{app.department_id}@example.edu",
                password_hash=pw,
                role=UserRole.dept_officer,
                department_id=app.department_id,
                is_active=True,
            )
            db.add(officer)
            db.flush()
        decide_approval(db, officer, app.id, ApprovalStatus.APPROVED, remarks=None)

    hod = db.execute(select(User).where(User.role == UserRole.hod, User.department_id == prog.academic_department_id)).scalars().first()
    cleared_req = hod_decide(db, hod, req.id, ApprovalStatus.APPROVED, remarks=None)
    db.commit()
    return user, cleared_req


def test_refund_state_transitions_happy_path(client: TestClient, db_session: Session):
    """CLEARED -> VERIFIED -> PROCESSED with accounts_note, paid_on, payment_mode."""
    student, req = _setup_cleared_student(db_session, "HP001", "hp001@example.edu")
    reg_user = db_session.execute(select(User).where(User.role == UserRole.registrar_accounts)).scalars().first()
    reg_headers = make_auth_headers(reg_user.id)
    student_headers = make_auth_headers(student.id)

    # 1. Initially student sees None amounts
    cur = client.get("/student/requests/current", headers=student_headers).json()
    assert cur["refund_status"] is None
    assert cur["deposit_amount"] is None
    assert cur["deductions"] is None
    assert cur["final_amount"] is None

    # 2. Verify refund
    ver_res = client.post(
        f"/registrar/requests/{req.id}/verify-refund",
        json={"deductions": 200.0, "remarks": "Hostel electricity dues deducted"},
        headers=reg_headers,
    )
    assert ver_res.status_code == 200
    assert ver_res.json()["refund_status"] == "VERIFIED"
    assert ver_res.json()["request_status"] == "REFUND_VERIFIED"

    # Verify student view now shows verified amounts
    cur = client.get("/student/requests/current", headers=student_headers).json()
    assert cur["refund_status"] == "VERIFIED"
    assert float(cur["deposit_amount"]) == 5000.00
    assert float(cur["deductions"]) == 200.00
    assert float(cur["final_amount"]) == 4800.00
    assert cur["accounts_note"] == "Hostel electricity dues deducted"
    assert cur["payment_reference"] is None

    # 3. Mark Processed
    today = datetime.now(timezone.utc).date()
    proc_res = client.post(
        f"/registrar/requests/{req.id}/mark-processed",
        json={
            "payment_reference": "NEFT-SVSU-20261108-01",
            "paid_on": str(today),
            "payment_mode": "NEFT",
        },
        headers=reg_headers,
    )
    assert proc_res.status_code == 200
    p_data = proc_res.json()
    assert p_data["refund_status"] == "PROCESSED"
    assert p_data["payment_reference"] == "NEFT-SVSU-20261108-01"
    assert p_data["paid_on"] == str(today)
    assert p_data["payment_mode"] == "NEFT"

    # Verify student view shows payment reference and paid_on
    cur = client.get("/student/requests/current", headers=student_headers).json()
    assert cur["refund_status"] == "PROCESSED"
    assert cur["payment_reference"] == "NEFT-SVSU-20261108-01"
    assert cur["paid_on"] == str(today)
    assert cur["payment_mode"] == "NEFT"


def test_reopen_verification_and_reverify(client: TestClient, db_session: Session):
    """VERIFIED -> PENDING_VERIFICATION (via reopen) -> VERIFIED with updated deductions."""
    student, req = _setup_cleared_student(db_session, "REOPEN001", "reopen001@example.edu")
    reg_user = db_session.execute(select(User).where(User.role == UserRole.registrar_accounts)).scalars().first()
    reg_headers = make_auth_headers(reg_user.id)

    # 1. Verify
    client.post(
        f"/registrar/requests/{req.id}/verify-refund",
        json={"deductions": 500.0, "remarks": "Incorrect deduction initial"},
        headers=reg_headers,
    )

    # 2. Reopen without reason -> 422
    reopen_fail = client.post(
        f"/registrar/requests/{req.id}/reopen-verification",
        json={},
        headers=reg_headers,
    )
    assert reopen_fail.status_code == 422

    # 3. Reopen successfully
    reopen_ok = client.post(
        f"/registrar/requests/{req.id}/reopen-verification",
        json={"reason": "Accounts team corrected deductions"},
        headers=reg_headers,
    )
    assert reopen_ok.status_code == 200
    assert reopen_ok.json()["refund_status"] == "PENDING_VERIFICATION"
    assert reopen_ok.json()["request_status"] == "CLEARED"

    # 4. Re-verify with correct deductions
    rev_res = client.post(
        f"/registrar/requests/{req.id}/verify-refund",
        json={"deductions": 100.0, "remarks": "Corrected deduction Rs. 100"},
        headers=reg_headers,
    )
    assert rev_res.status_code == 200
    assert float(rev_res.json()["deductions"]) == 100.0
    assert float(rev_res.json()["final_amount"]) == 4900.0


def test_failed_disbursement_retry_and_processed(client: TestClient, db_session: Session):
    """VERIFIED -> PAYMENT_FAILED -> VERIFIED (retry) -> PROCESSED."""
    student, req = _setup_cleared_student(db_session, "FAIL001", "fail001@example.edu")
    reg_user = db_session.execute(select(User).where(User.role == UserRole.registrar_accounts)).scalars().first()
    reg_headers = make_auth_headers(reg_user.id)
    student_headers = make_auth_headers(student.id)

    # Verify
    client.post(
        f"/registrar/requests/{req.id}/verify-refund",
        json={"deductions": 0, "remarks": "Full refund verified"},
        headers=reg_headers,
    )

    # Mark Failed from VERIFIED
    fail_res = client.post(
        f"/registrar/requests/{req.id}/mark-failed",
        json={"reason": "Beneficiary account inactive"},
        headers=reg_headers,
    )
    assert fail_res.status_code == 200

    # Student sees failure reason
    cur = client.get("/student/requests/current", headers=student_headers).json()
    assert cur["refund_status"] == "PAYMENT_FAILED"
    assert cur["failure_reason"] == "Beneficiary account inactive"

    # Retry payment
    retry_res = client.post(
        f"/registrar/requests/{req.id}/retry-payment",
        headers=reg_headers,
    )
    assert retry_res.status_code == 200

    # Refund status is back to VERIFIED
    cur = client.get("/student/requests/current", headers=student_headers).json()
    assert cur["refund_status"] == "VERIFIED"
    assert cur["failure_reason"] is None

    # Now mark processed
    today = datetime.now(timezone.utc).date()
    proc_res = client.post(
        f"/registrar/requests/{req.id}/mark-processed",
        json={"payment_reference": "IMPS-RETRIED-001", "paid_on": str(today), "payment_mode": "IMPS"},
        headers=reg_headers,
    )
    assert proc_res.status_code == 200
    assert proc_res.json()["refund_status"] == "PROCESSED"


def test_invalid_state_transitions_return_409(client: TestClient, db_session: Session):
    """Every invalid state transition must return 409 Conflict."""
    student, req = _setup_cleared_student(db_session, "INV001", "inv001@example.edu")
    reg_user = db_session.execute(select(User).where(User.role == UserRole.registrar_accounts)).scalars().first()
    reg_headers = make_auth_headers(reg_user.id)

    # Current: CLEARED, PENDING_VERIFICATION
    # Cannot reopen when PENDING_VERIFICATION -> 409
    res = client.post(f"/registrar/requests/{req.id}/reopen-verification", json={"reason": "test"}, headers=reg_headers)
    assert res.status_code == 409

    # Cannot mark processed when PENDING_VERIFICATION -> 409
    res = client.post(f"/registrar/requests/{req.id}/mark-processed", json={"payment_reference": "REF12345"}, headers=reg_headers)
    assert res.status_code == 409

    # Cannot mark failed when PENDING_VERIFICATION -> 409
    res = client.post(f"/registrar/requests/{req.id}/mark-failed", json={"reason": "test"}, headers=reg_headers)
    assert res.status_code == 409

    # Cannot retry payment when PENDING_VERIFICATION -> 409
    res = client.post(f"/registrar/requests/{req.id}/retry-payment", headers=reg_headers)
    assert res.status_code == 409

    # Now verify
    client.post(f"/registrar/requests/{req.id}/verify-refund", json={"deductions": 0, "remarks": "ok"}, headers=reg_headers)

    # Cannot retry payment when VERIFIED -> 409
    res = client.post(f"/registrar/requests/{req.id}/retry-payment", headers=reg_headers)
    assert res.status_code == 409

    # Cannot verify again when already VERIFIED -> 409
    res = client.post(f"/registrar/requests/{req.id}/verify-refund", json={"deductions": 0, "remarks": "ok"}, headers=reg_headers)
    assert res.status_code == 409


def test_date_and_payment_reference_validations(client: TestClient, db_session: Session):
    """Validation of paid_on dates and payment_reference regex."""
    student, req = _setup_cleared_student(db_session, "VAL001", "val001@example.edu")
    reg_user = db_session.execute(select(User).where(User.role == UserRole.registrar_accounts)).scalars().first()
    reg_headers = make_auth_headers(reg_user.id)

    # Verify
    client.post(f"/registrar/requests/{req.id}/verify-refund", json={"deductions": 0, "remarks": "ok"}, headers=reg_headers)

    # 1. Future paid_on -> 400
    future_date = (datetime.now(timezone.utc) + timedelta(days=2)).date()
    res = client.post(
        f"/registrar/requests/{req.id}/mark-processed",
        json={"payment_reference": "VALID-REF-123", "paid_on": str(future_date)},
        headers=reg_headers,
    )
    assert res.status_code == 400
    assert "future" in res.json()["detail"].lower()

    # 2. paid_on before verified_at date -> 400
    past_date = (datetime.now(timezone.utc) - timedelta(days=5)).date()
    res = client.post(
        f"/registrar/requests/{req.id}/mark-processed",
        json={"payment_reference": "VALID-REF-123", "paid_on": str(past_date)},
        headers=reg_headers,
    )
    assert res.status_code == 400
    assert "before" in res.json()["detail"].lower()

    # 3. Invalid reference pattern (contains invalid chars like spaces or special symbols) -> 422
    res = client.post(
        f"/registrar/requests/{req.id}/mark-processed",
        json={"payment_reference": "INVALID REF!#$"},
        headers=reg_headers,
    )
    assert res.status_code == 422

    # 4. Too short reference (< 6 chars) -> 422
    res = client.post(
        f"/registrar/requests/{req.id}/mark-processed",
        json={"payment_reference": "12345"},
        headers=reg_headers,
    )
    assert res.status_code == 422


def test_student_confirm_and_issue_reporting(client: TestClient, db_session: Session):
    """Student confirmation and issue reporting lifecycle."""
    student, req = _setup_cleared_student(db_session, "CONF001", "conf001@example.edu")
    reg_user = db_session.execute(select(User).where(User.role == UserRole.registrar_accounts)).scalars().first()
    reg_headers = make_auth_headers(reg_user.id)
    student_headers = make_auth_headers(student.id)

    # 1. Cannot confirm receipt when PENDING_VERIFICATION -> 409
    res = client.post(f"/student/requests/{req.id}/refund/confirm", json={"received": True}, headers=student_headers)
    assert res.status_code == 409

    # 2. Verify and Mark Processed
    client.post(f"/registrar/requests/{req.id}/verify-refund", json={"deductions": 0, "remarks": "ok"}, headers=reg_headers)
    client.post(f"/registrar/requests/{req.id}/mark-processed", json={"payment_reference": "REFUND-TX-001"}, headers=reg_headers)

    # 3. Report issue with empty note -> 400
    res = client.post(f"/student/requests/{req.id}/refund/confirm", json={"received": False, "note": "   "}, headers=student_headers)
    assert res.status_code == 400

    # 4. Report issue with note -> sets issue fields
    res = client.post(f"/student/requests/{req.id}/refund/confirm", json={"received": False, "note": "Funds not credited after 5 days"}, headers=student_headers)
    assert res.status_code == 200
    assert res.json()["student_issue_note"] == "Funds not credited after 5 days"
    assert res.json()["student_issue_at"] is not None

    # Registrar queue shows student_issue_open == True
    q_res = client.get("/registrar/queue?tab=PAID", headers=reg_headers).json()
    item = next(it for it in q_res["items"] if it["request_id"] == req.id)
    assert item["student_issue_open"] is True

    # 5. Registrar resolves issue
    res_issue = client.post(
        f"/registrar/requests/{req.id}/resolve-issue",
        json={"note": "UTR confirmed with bank manager"},
        headers=reg_headers,
    )
    assert res_issue.status_code == 200

    # Now student_issue_open is False
    q_res = client.get("/registrar/queue?tab=PAID", headers=reg_headers).json()
    item = next(it for it in q_res["items"] if it["request_id"] == req.id)
    assert item["student_issue_open"] is False

    # 6. Student confirms receipt
    res_conf = client.post(f"/student/requests/{req.id}/refund/confirm", json={"received": True}, headers=student_headers)
    assert res_conf.status_code == 200
    assert res_conf.json()["student_confirmed_at"] is not None


def test_bank_details_modification_locked_after_processed(client: TestClient, db_session: Session):
    """PUT /student/bank-details returns 409 once any refund is PROCESSED."""
    student, req = _setup_cleared_student(db_session, "BANKMOD001", "bankmod001@example.edu")
    reg_user = db_session.execute(select(User).where(User.role == UserRole.registrar_accounts)).scalars().first()
    reg_headers = make_auth_headers(reg_user.id)
    student_headers = make_auth_headers(student.id)

    # 1. Update bank details before PROCESSED -> succeeds & writes audit
    update_res = client.put(
        "/student/bank-details",
        json={
            "account_number": "11223344556677",
            "ifsc_code": "SBIN0001234",
            "account_holder_name": "Student BankMod",
            "bank_address": "SBI Campus Branch",
        },
        headers=student_headers,
    )
    assert update_res.status_code == 200

    # Verify audit log (never stores plain account number)
    audit = db_session.execute(
        select(AuditLog)
        .where(AuditLog.user_id == student.id, AuditLog.action == "UPDATE_BANK_DETAILS")
        .order_by(AuditLog.id.desc())
    ).scalars().first()
    assert audit is not None
    assert "11223344556677" not in str(audit.details)
    assert audit.details["account_number_masked"] == "**********6677"

    # 2. Complete clearance and verify/process refund
    client.post(f"/registrar/requests/{req.id}/verify-refund", json={"deductions": 0, "remarks": "ok"}, headers=reg_headers)
    client.post(f"/registrar/requests/{req.id}/mark-processed", json={"payment_reference": "DISBURSED-001"}, headers=reg_headers)

    # 3. Attempt to update bank details after PROCESSED -> 409 Conflict
    locked_res = client.put(
        "/student/bank-details",
        json={
            "account_number": "99887766554433",
            "ifsc_code": "SBIN0001234",
            "account_holder_name": "Student BankMod",
            "bank_address": "SBI Campus Branch",
        },
        headers=student_headers,
    )
    assert locked_res.status_code == 409
    assert "after refund has been processed" in locked_res.json()["detail"].lower()


def test_registrar_queue_tabs_counts_and_export_csv(client: TestClient, db_session: Session):
    """Queue tabs filtering, counts, financial totals, and CSV export."""
    student, req = _setup_cleared_student(db_session, "TAB001", "tab001@example.edu")
    reg_user = db_session.execute(select(User).where(User.role == UserRole.registrar_accounts)).scalars().first()
    reg_headers = make_auth_headers(reg_user.id)
    student_headers = make_auth_headers(student.id)

    # 1. In TO_VERIFY
    q1 = client.get("/registrar/queue?tab=TO_VERIFY", headers=reg_headers).json()
    assert any(it["request_id"] == req.id for it in q1["items"])
    assert q1["counts"]["TO_VERIFY"] >= 1

    # 2. Move to TO_PAY
    client.post(f"/registrar/requests/{req.id}/verify-refund", json={"deductions": 300.0, "remarks": "Lab fine Rs. 300"}, headers=reg_headers)
    q2 = client.get("/registrar/queue?tab=TO_PAY", headers=reg_headers).json()
    assert any(it["request_id"] == req.id for it in q2["items"])
    assert q2["counts"]["TO_PAY"] >= 1
    assert Decimal(str(q2["total_to_pay_amount"])) >= Decimal("4700.00")

    # 3. Move to PAID
    client.post(f"/registrar/requests/{req.id}/mark-processed", json={"payment_reference": "TXN-PAID-001"}, headers=reg_headers)
    q3 = client.get("/registrar/queue?tab=PAID", headers=reg_headers).json()
    assert any(it["request_id"] == req.id for it in q3["items"])
    assert q3["counts"]["PAID"] >= 1
    assert Decimal(str(q3["total_paid_amount"])) >= Decimal("4700.00")

    # 4. CSV Export - Registrar role only
    csv_res = client.get("/registrar/refunds/export.csv?tab=PAID", headers=reg_headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    reader = csv.reader(io.StringIO(csv_res.text))
    rows = list(reader)
    header = rows[0]
    assert header == [
        "registration_number", "student_name", "programme", "deposit_amount",
        "deductions", "final_amount", "refund_status", "payment_reference",
        "paid_on", "payment_mode", "account_number_masked",
    ]
    # Check that plain accounts are never exposed in CSV
    assert not any("123456789" in row[-1] for row in rows[1:])

    # Student cannot export CSV -> 403
    forbidden_res = client.get("/registrar/refunds/export.csv?tab=PAID", headers=student_headers)
    assert forbidden_res.status_code == 403


def test_non_cancelled_single_request_constraint(client: TestClient, db_session: Session):
    """Student with REFUND_VERIFIED request cannot reapply; student with CANCELLED request can."""
    student, req = _setup_cleared_student(db_session, "UNQ001", "unq001@example.edu")
    reg_user = db_session.execute(select(User).where(User.role == UserRole.registrar_accounts)).scalars().first()
    reg_headers = make_auth_headers(reg_user.id)
    student_headers = make_auth_headers(student.id)

    # Move request to REFUND_VERIFIED
    client.post(f"/registrar/requests/{req.id}/verify-refund", json={"deductions": 0, "remarks": "Verified"}, headers=reg_headers)

    # Student attempts to apply again -> 409 Conflict
    reapply_res = client.post("/student/requests", json={"is_hosteller": False}, headers=student_headers)
    assert reapply_res.status_code == 409
    assert "Only one non-cancelled clearance request is permitted per student." in reapply_res.json()["detail"]


def test_migration_0013_roundtrip():
    """Verify upgrade -> downgrade -> upgrade for migration 0013_complete_refund_loop."""
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)

    # Downgrade to 0012
    command.downgrade(alembic_cfg, "0012_department_categories")

    # Upgrade to head (0013)
    command.upgrade(alembic_cfg, "head")

    # Downgrade again to test reversibility
    command.downgrade(alembic_cfg, "0012_department_categories")

    # Upgrade back to head
    command.upgrade(alembic_cfg, "head")
