"""Tests for deposit ledger template download, CSV upload (dry run & execute),
single-student PATCH, queue & detail exposure, and audit logging."""
import csv
import io
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.user import User, UserRole
from backend.app.models.roster import StudentRoster
from backend.app.models.clearance import ClearanceRequest, ClearanceStatus, ApprovalStatus
from backend.app.models.refund import Refund, RefundStatus
from backend.app.models.audit import AuditLog
from backend.app.models.university import Programme
from backend.app.models.bank import BankDetail
from backend.app.core.security import hash_password
from backend.app.services.workflow import create_request, decide_approval, hod_decide
from tests.conftest import make_auth_headers


def _get_or_create_registrar(db: Session) -> User:
    reg = db.execute(select(User).where(User.role == UserRole.registrar_accounts)).scalars().first()
    if not reg:
        pw = hash_password("Secret123!")
        reg = User(
            email="registrar.deposit@svsu.ac.in",
            password_hash=pw,
            role=UserRole.registrar_accounts,
            is_active=True,
            full_name="Accounts Officer",
        )
        db.add(reg)
        db.commit()
        db.refresh(reg)
    return reg


def _get_or_create_non_registrar_user(db: Session) -> User:
    user = db.execute(select(User).where(User.role == UserRole.admin)).scalars().first()
    if not user:
        pw = hash_password("Secret123!")
        user = User(
            email="admin.deposit.test@svsu.ac.in",
            password_hash=pw,
            role=UserRole.admin,
            is_active=True,
            full_name="Admin User",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _create_simple_roster_student(db: Session, reg_num: str, email: str, deposit: Decimal = Decimal("0.00")) -> StudentRoster:
    prog = db.execute(select(Programme)).scalars().first()
    roster = StudentRoster(
        registration_number=reg_num,
        name=f"Student {reg_num}",
        email=email,
        mobile="9876543210",
        address="Hostel 4, SVSU Campus",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=deposit,
    )
    db.add(roster)
    db.commit()
    db.refresh(roster)
    return roster


def _setup_cleared_student(db: Session, reg_num: str, email: str, deposit: Decimal = Decimal("5000.00")):
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
        security_deposit_amount=deposit,
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
    for app in req.approvals:
        officer = db.execute(select(User).where(User.department_id == app.department_id)).scalars().first()
        if not officer:
            officer = User(
                email=f"temp.officer.{app.department_id}@svsu.ac.in",
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
    return cleared_req, user, roster


def test_deposit_ledger_template_csv(client: TestClient, db_session: Session):
    registrar = _get_or_create_registrar(db_session)
    reg_headers = make_auth_headers(registrar.id)

    # 1. Non-registrar forbidden
    non_reg_user = _get_or_create_non_registrar_user(db_session)
    non_reg_headers = make_auth_headers(non_reg_user.id)
    res_unauth = client.get("/registrar/deposit-ledger/template.csv", headers=non_reg_headers)
    assert res_unauth.status_code == 403

    # 2. Registrar gets template
    res = client.get("/registrar/deposit-ledger/template.csv", headers=reg_headers)
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert 'attachment; filename="deposit_ledger_template.csv"' in res.headers["content-disposition"]

    # Validate CSV content
    reader = list(csv.reader(io.StringIO(res.text)))
    assert len(reader) >= 2
    assert [c.strip() for c in reader[0]] == ["registration_number", "deposit_amount"]
    assert reader[1][0].strip() == "2026SVSU0001"
    assert Decimal(reader[1][1].strip()) == Decimal("5000.00")


def test_deposit_ledger_upload_dry_run_and_persistence(client: TestClient, db_session: Session):
    registrar = _get_or_create_registrar(db_session)
    reg_headers = make_auth_headers(registrar.id)

    s1 = _create_simple_roster_student(db_session, "2026LEDG0001", "ledg1@svsu.ac.in", Decimal("0.00"))
    s2 = _create_simple_roster_student(db_session, "2026LEDG0002", "ledg2@svsu.ac.in", Decimal("1000.00"))

    csv_data = "registration_number,deposit_amount\n2026LEDG0001,5000.00\n2026LEDG0002,5000.00\n"

    # 1. Dry run upload
    res_dry = client.post(
        "/registrar/deposit-ledger/upload?dry_run=true",
        headers=reg_headers,
        files={"file": ("ledger.csv", csv_data, "text/csv")},
    )
    assert res_dry.status_code == 200
    data_dry = res_dry.json()
    assert data_dry["dry_run"] is True
    assert data_dry["total_rows"] == 2
    assert data_dry["updated_count"] == 2
    assert data_dry["rejected_count"] == 0

    # Ensure DB was not modified during dry-run
    db_session.expire_all()
    s1_db = db_session.scalar(select(StudentRoster).where(StudentRoster.id == s1.id))
    s2_db = db_session.scalar(select(StudentRoster).where(StudentRoster.id == s2.id))
    assert s1_db.security_deposit_amount == Decimal("0.00")
    assert s2_db.security_deposit_amount == Decimal("1000.00")

    # 2. Real upload
    res_real = client.post(
        "/registrar/deposit-ledger/upload?dry_run=false",
        headers=reg_headers,
        files={"file": ("ledger.csv", csv_data, "text/csv")},
    )
    assert res_real.status_code == 200
    data_real = res_real.json()
    assert data_real["dry_run"] is False
    assert data_real["updated_count"] == 2

    # Verify DB changes
    db_session.expire_all()
    s1_db = db_session.scalar(select(StudentRoster).where(StudentRoster.id == s1.id))
    s2_db = db_session.scalar(select(StudentRoster).where(StudentRoster.id == s2.id))
    assert s1_db.security_deposit_amount == Decimal("5000.00")
    assert s2_db.security_deposit_amount == Decimal("5000.00")
    assert s1_db.updated_by_user_id == registrar.id
    assert s2_db.updated_by_user_id == registrar.id

    # 3. Repeat upload: report unchanged
    res_repeat = client.post(
        "/registrar/deposit-ledger/upload?dry_run=false",
        headers=reg_headers,
        files={"file": ("ledger.csv", csv_data, "text/csv")},
    )
    assert res_repeat.status_code == 200
    data_repeat = res_repeat.json()
    assert data_repeat["updated_count"] == 0
    assert data_repeat["unchanged_count"] == 2
    assert data_repeat["rows"][0]["status"] == "unchanged"


def test_deposit_ledger_upload_rejections_and_validation(client: TestClient, db_session: Session):
    registrar = _get_or_create_registrar(db_session)
    reg_headers = make_auth_headers(registrar.id)

    # Student with verified refund
    cleared_req, _, verified_roster = _setup_cleared_student(db_session, "2026LEDGVERIF", "verif@svsu.ac.in", Decimal("4000.00"))
    verify_res = client.post(
        f"/registrar/requests/{cleared_req.id}/verify-refund",
        headers=reg_headers,
        json={"deposit_amount": 4000.00, "deductions": 500.00, "remarks": "Approved deductions"},
    )
    assert verify_res.status_code == 200

    # Test bad CSV header
    bad_header_csv = "student_id,amount\n123,5000\n"
    res_bad_head = client.post(
        "/registrar/deposit-ledger/upload",
        headers=reg_headers,
        files={"file": ("bad.csv", bad_header_csv, "text/csv")},
    )
    assert res_bad_head.status_code == 400
    assert "header" in res_bad_head.json()["detail"].lower()

    # Test various row rejection reasons
    test_csv = (
        "registration_number,deposit_amount\n"
        "UNKNOWN_STU,5000.00\n"
        "2026LEDGVERIF,6000.00\n"
        ",5000.00\n"
        "2026LEDG0001,-500.00\n"
        "2026LEDG0001,1000000000.00\n"
        "2026LEDG0001,5000.999\n"
        "2026LEDG0001,not_a_number\n"
    )
    res_rows = client.post(
        "/registrar/deposit-ledger/upload",
        headers=reg_headers,
        files={"file": ("test.csv", test_csv, "text/csv")},
    )
    assert res_rows.status_code == 200
    data = res_rows.json()
    assert data["rejected_count"] == 7
    reasons = [r["reason"] for r in data["rows"]]
    assert any("not found in roster" in (r or "") for r in reasons)
    assert any("already VERIFIED" in (r or "") for r in reasons)
    assert any("cannot be empty" in (r or "") for r in reasons)
    assert any("cannot be negative" in (r or "") for r in reasons)
    assert any("exceeds maximum" in (r or "") for r in reasons)
    assert any("2 decimal places" in (r or "") for r in reasons)
    assert any("valid decimal number" in (r or "") for r in reasons)


def test_patch_roster_deposit(client: TestClient, db_session: Session):
    registrar = _get_or_create_registrar(db_session)
    reg_headers = make_auth_headers(registrar.id)

    s = _create_simple_roster_student(db_session, "2026PATCH01", "patch01@svsu.ac.in", Decimal("3000.00"))

    # 1. 403 for non-registrar
    non_reg_user = _get_or_create_non_registrar_user(db_session)
    res_unauth = client.patch(f"/registrar/roster/{s.id}/deposit", headers=make_auth_headers(non_reg_user.id), json={"deposit_amount": 5500.00})
    assert res_unauth.status_code == 403

    # 2. 404 for unknown id
    res_404 = client.patch("/registrar/roster/999999/deposit", headers=reg_headers, json={"deposit_amount": 5500.00})
    assert res_404.status_code == 404

    # 3. 400 for bad precision
    res_bad = client.patch(f"/registrar/roster/{s.id}/deposit", headers=reg_headers, json={"deposit_amount": 5500.555})
    assert res_bad.status_code == 400

    # 4. Success update
    res_ok = client.patch(f"/registrar/roster/{s.id}/deposit", headers=reg_headers, json={"deposit_amount": 6500.00})
    assert res_ok.status_code == 200
    data_ok = res_ok.json()
    assert Decimal(str(data_ok["security_deposit_amount"])) == Decimal("6500.00")
    assert data_ok["registration_number"] == "2026PATCH01"

    # Verify DB & Audit Log
    db_session.expire_all()
    s_db = db_session.scalar(select(StudentRoster).where(StudentRoster.id == s.id))
    assert s_db.security_deposit_amount == Decimal("6500.00")
    assert s_db.updated_by_user_id == registrar.id

    audit = db_session.execute(
        select(AuditLog)
        .where(AuditLog.action == "UPDATE_ROSTER_DEPOSIT", AuditLog.entity_id == s.id)
    ).scalars().first()
    assert audit is not None
    assert audit.details["old_amount"] == "3000.00"
    assert audit.details["new_amount"] == "6500.00"

    # 5. 409 Conflict if student refund is verified
    cleared_req, _, verified_roster = _setup_cleared_student(db_session, "2026PATCHVERIF", "patchverif@svsu.ac.in", Decimal("4000.00"))
    client.post(
        f"/registrar/requests/{cleared_req.id}/verify-refund",
        headers=reg_headers,
        json={"deposit_amount": 4000.00, "deductions": 0.00, "remarks": "Zero deductions"},
    )
    res_conflict = client.patch(f"/registrar/roster/{verified_roster.id}/deposit", headers=reg_headers, json={"deposit_amount": 9000.00})
    assert res_conflict.status_code == 409
    assert "already VERIFIED" in res_conflict.json()["detail"]


def test_ledger_deposit_amount_in_queue_detail_and_audit(client: TestClient, db_session: Session):
    registrar = _get_or_create_registrar(db_session)
    reg_headers = make_auth_headers(registrar.id)

    # Student 1 with 7500 deposit
    req1, _, roster1 = _setup_cleared_student(db_session, "2026QUEUE1", "queue1@svsu.ac.in", Decimal("7500.00"))
    # Student 2 with 0 deposit
    req2, _, roster2 = _setup_cleared_student(db_session, "2026QUEUE2", "queue2@svsu.ac.in", Decimal("0.00"))

    # Check GET /registrar/queue
    res_q = client.get("/registrar/queue?tab=TO_VERIFY", headers=reg_headers)
    assert res_q.status_code == 200
    items = {item["request_id"]: item for item in res_q.json()["items"]}

    assert req1.id in items
    assert Decimal(str(items[req1.id]["ledger_deposit_amount"])) == Decimal("7500.00")

    assert req2.id in items
    assert items[req2.id]["ledger_deposit_amount"] is None

    # Check GET /registrar/requests/{id}
    res_det1 = client.get(f"/registrar/requests/{req1.id}", headers=reg_headers)
    assert res_det1.status_code == 200
    assert Decimal(str(res_det1.json()["ledger_deposit_amount"])) == Decimal("7500.00")

    res_det2 = client.get(f"/registrar/requests/{req2.id}", headers=reg_headers)
    assert res_det2.status_code == 200
    assert res_det2.json()["ledger_deposit_amount"] is None

    # Check verify-refund audit logging when deposit differs from ledger
    # req1 ledger deposit is 7500.00; registrar enters 7000.00
    res_ver = client.post(
        f"/registrar/requests/{req1.id}/verify-refund",
        headers=reg_headers,
        json={"deposit_amount": 7000.00, "deductions": 200.00, "remarks": "Deposit corrected against bank receipt"},
    )
    assert res_ver.status_code == 200

    db_session.expire_all()
    audit = db_session.execute(
        select(AuditLog)
        .where(AuditLog.action == "VERIFY_REFUND", AuditLog.entity_id == req1.id)
        .order_by(AuditLog.id.desc())
    ).scalars().first()
    assert audit is not None
    assert audit.details["deposit_amount"] == "7000.00"
    assert audit.details["ledger_deposit_amount"] == "7500.00"
    assert audit.details["deposit_differs_from_ledger"] is True
