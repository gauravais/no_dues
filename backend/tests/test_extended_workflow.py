"""
Tests for extended functionality:
- Student bank details CRUD, validation, and masking
- Blocking clearance application without bank details
- Official Certificate PDF generation & QR verification link
- Public verification endpoint privacy & valid/invalid responses
- Registrar / Accounts refund verification, deduction limits, and processed marking
- Admin Roster CSV upload with created/updated/rejected reports
- Admin user provisioning (temporary passwords, HoD department constraints, self-deactivation guard)
- Strict role-based access control (403 guards) across all new endpoints
"""
import io
from decimal import Decimal
from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from backend.app.models.user import User, UserRole
from backend.app.models.roster import StudentRoster, RosterAssignedDepartment
from backend.app.models.university import Department, Programme, DepartmentKind
from backend.app.models.clearance import ClearanceRequest, ClearanceStatus, ApprovalStatus
from backend.app.models.bank import BankDetail
from backend.app.models.refund import Refund, RefundStatus
from backend.app.models.certificate import Certificate
from backend.app.core.security import hash_password
from backend.app.services.workflow import (
    create_request,
    decide_approval,
    hod_decide,
)
from tests.conftest import make_auth_headers


def _create_test_student(
    db: Session,
    reg_num: str = "DEMO9001",
    email: str = "student9001@example.edu",
    is_hosteller: bool = False,
    assigned_dept_ids: list[int] | None = None,
    deposit: float = 5000.0,
) -> tuple[User, StudentRoster]:
    prog = db.execute(select(Programme)).scalars().first()
    now = datetime.now(timezone.utc)

    roster = StudentRoster(
        registration_number=reg_num,
        name="Test Student",
        email=email,
        mobile="9800009001",
        address="100 Test St",
        programme_id=prog.id,
        is_hosteller=is_hosteller,
        security_deposit_amount=deposit,
    )
    db.add(roster)
    db.flush()

    if assigned_dept_ids:
        for did in assigned_dept_ids:
            db.add(RosterAssignedDepartment(roster_id=roster.id, department_id=did))

    db.add(
        BankDetail(
            roster_id=roster.id,
            account_holder_name="Test Student",
            account_number="123456780001",
            ifsc_code="DEMO0009001",
            bank_address="Demo Bank, Main",
        )
    )

    user = User(
        email=email,
        full_name="Test Student",
        password_hash=hash_password("StudentPass@123"),
        role=UserRole.student,
        department_id=None,
        roster_id=roster.id,
        is_active=True,
        created_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, roster


# ---------------------------------------------------------------------------
# Test 13: Bank details validation, masking, and update
# ---------------------------------------------------------------------------
def test_13_bank_details_validation_and_masking(client: TestClient, db_session: Session):
    db = db_session
    student, _ = _create_test_student(db, reg_num="DEMO9013", email="student13@example.edu")
    headers = make_auth_headers(student.id)

    # 1. GET bank details -> masked
    res = client.get("/student/bank-details", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["account_number_masked"].startswith("********")
    assert data["account_number_masked"].endswith("0001")
    assert "account_number" not in data  # Never leak full number!

    # 2. PUT with valid new account number & IFSC
    update_payload = {
        "account_number": "987654321098",
        "ifsc_code": "HDFC0001234",
        "account_holder_name": "Aarav Sharma",
        "bank_address": "HDFC Bank, Sector 15 Branch, Gurugram",
    }
    put_res = client.put("/student/bank-details", json=update_payload, headers=headers)
    assert put_res.status_code == 200, put_res.text
    put_data = put_res.json()
    assert put_data["account_number_masked"] == "********1098"
    assert put_data["ifsc_code"] == "HDFC0001234"
    assert "987654321098" not in put_res.text  # Full number not echoed

    # Verify DB has stored full account number
    bank_in_db = db.execute(
        select(BankDetail).where(BankDetail.roster_id == student.roster_id)
    ).scalar_one()
    assert bank_in_db.account_number == "987654321098"

    # 3. PUT with invalid IFSC -> 422
    bad_ifsc_res = client.put(
        "/student/bank-details",
        json={**update_payload, "ifsc_code": "INVALID_IFSC"},
        headers=headers,
    )
    assert bad_ifsc_res.status_code == 422

    # 4. PUT with non-digit or short account number -> 422
    bad_acc_res = client.put(
        "/student/bank-details",
        json={**update_payload, "account_number": "12345"},  # Too short (min 9)
        headers=headers,
    )
    assert bad_acc_res.status_code == 422


# ---------------------------------------------------------------------------
# Test 14: Applying for clearance without bank details is refused (400)
# ---------------------------------------------------------------------------
def test_14_applying_without_bank_details_refused(client: TestClient, db_session: Session):
    db = db_session
    prog = db.execute(select(Programme)).scalars().first()
    now = datetime.now(timezone.utc)

    # Create a fresh student without bank details
    roster_no_bank = StudentRoster(
        registration_number="DEMO9999",
        name="No Bank Student",
        email="nobank@example.edu",
        mobile="9800009999",
        address="999 No Bank Road",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=5000.0,
    )
    db.add(roster_no_bank)
    db.flush()

    user_no_bank = User(
        email="nobank@example.edu",
        full_name="No Bank Student",
        password_hash="fakehash",
        role=UserRole.student,
        roster_id=roster_no_bank.id,
        is_active=True,
        created_at=now,
    )
    db.add(user_no_bank)
    db.commit()

    headers = make_auth_headers(user_no_bank.id)
    res = client.post("/student/requests", headers=headers)
    assert res.status_code == 400
    assert "Bank details must be provided" in res.json()["detail"]


# ---------------------------------------------------------------------------
# Test 15: Certificate PDF generation, ownership, and QR verification
# ---------------------------------------------------------------------------
def test_15_certificate_pdf_and_public_verification(client: TestClient, db_session: Session):
    db = db_session
    # Setup cleared request for student
    student, _ = _create_test_student(db, reg_num="DEMO9015", email="student15@example.edu")
    student_headers = make_auth_headers(student.id)

    # Create request
    req = create_request(db, student)

    # Attempting to download certificate while SUBMITTED -> 400
    pre_res = client.get(f"/student/requests/{req.id}/certificate.pdf", headers=student_headers)
    assert pre_res.status_code == 400
    assert "Certificate is available only for CLEARED" in pre_res.json()["detail"]

    # Approve all approvals
    for app in req.approvals:
        officer = db.execute(select(User).where(User.department_id == app.department_id)).scalars().first()
        if not officer:
            officer = User(
                email=f"temp.officer.{app.department_id}@example.edu",
                password_hash=hash_password("pw"),
                role=UserRole.dept_officer,
                department_id=app.department_id,
                is_active=True,
            )
            db.add(officer)
            db.flush()
        decide_approval(db, officer, app.id, ApprovalStatus.APPROVED, remarks=None)

    # Chairperson approves -> CLEARED
    hod_user = db.execute(select(User).where(User.role == UserRole.hod, User.department_id == req.roster_entry.programme.academic_department_id)).scalars().first()
    cleared_req = hod_decide(db, hod_user, req.id, ApprovalStatus.APPROVED, remarks=None)
    assert cleared_req.status == ClearanceStatus.CLEARED

    # 1. Student downloads own certificate PDF
    pdf_res = client.get(f"/student/requests/{req.id}/certificate.pdf", headers=student_headers)
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF")  # Valid PDF header

    # 2. Another student cannot download this certificate -> 403
    other_student, _ = _create_test_student(db, reg_num="DEMO9016", email="student16@example.edu")
    other_headers = make_auth_headers(other_student.id)
    forbidden_res = client.get(f"/student/requests/{req.id}/certificate.pdf", headers=other_headers)
    assert forbidden_res.status_code == 403

    # 3. Public Verification endpoint (No login required)
    cert_code = cleared_req.certificate.certificate_code
    verify_res = client.get(f"/verify/{cert_code}")
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["valid"] is True
    assert v_data["issued_at"] is not None
    assert v_data["masked_registration_number"].endswith("9015")
    assert v_data["programme"] != ""
    assert v_data["department"] != ""
    # Verify strict data privacy: NO bank, email, mobile, or student name exposed!
    assert "email" not in v_data
    assert "mobile" not in v_data
    assert "bank" not in v_data
    assert "account" not in v_data
    assert "student_name" not in v_data

    # 4. Unknown certificate code verification
    unknown_res = client.get("/verify/00000000-0000-0000-0000-000000000000")
    assert unknown_res.status_code == 200
    assert unknown_res.json() == {"valid": False, "issued_at": None, "masked_registration_number": None, "programme": None, "department": None}


# ---------------------------------------------------------------------------
# Test 16: Registrar refund queue, deduction limits, and processed marking
# ---------------------------------------------------------------------------
def test_16_registrar_refund_verification_and_limits(client: TestClient, db_session: Session):
    db = db_session
    reg_user = db.execute(select(User).where(User.role == UserRole.registrar_accounts)).scalars().first()
    reg_headers = make_auth_headers(reg_user.id)

    # Create and clear a clearance request
    student, _ = _create_test_student(db, reg_num="DEMO9017", email="student17@example.edu", deposit=5000.0)
    req = create_request(db, student)
    for app in req.approvals:
        officer = db.execute(select(User).where(User.department_id == app.department_id)).scalars().first()
        if not officer:
            officer = User(
                email=f"temp.officer.{app.department_id}@example.edu",
                password_hash=hash_password("pw"),
                role=UserRole.dept_officer,
                department_id=app.department_id,
                is_active=True,
            )
            db.add(officer)
            db.flush()
        decide_approval(db, officer, app.id, ApprovalStatus.APPROVED, remarks=None)
    hod_user = db.execute(select(User).where(User.role == UserRole.hod, User.department_id == req.roster_entry.programme.academic_department_id)).scalars().first()
    cleared_req = hod_decide(db, hod_user, req.id, ApprovalStatus.APPROVED, remarks=None)
    assert cleared_req.status == ClearanceStatus.CLEARED
    deposit = cleared_req.refund.deposit_amount

    # 1. GET /registrar/queue
    q_res = client.get("/registrar/queue", headers=reg_headers)
    assert q_res.status_code == 200
    q_data = q_res.json()
    assert q_data["total"] >= 1
    assert any(item["request_id"] == cleared_req.id for item in q_data["items"])

    # 2. Attempt deductions > deposit -> 400
    excessive_res = client.post(
        f"/registrar/requests/{cleared_req.id}/verify-refund",
        json={"deductions": float(deposit + 500), "remarks": "Excessive deduction"},
        headers=reg_headers,
    )
    assert excessive_res.status_code == 400
    assert "Deductions must be between 0 and total deposit amount" in excessive_res.json()["detail"]

    # 3. Attempt negative deductions -> 422
    negative_res = client.post(
        f"/registrar/requests/{cleared_req.id}/verify-refund",
        json={"deductions": -50.0, "remarks": "Negative deduction"},
        headers=reg_headers,
    )
    assert negative_res.status_code == 422

    # 4. Verify refund successfully with deductions = 200
    deduction_val = 200.0
    verify_res = client.post(
        f"/registrar/requests/{cleared_req.id}/verify-refund",
        json={"deductions": deduction_val, "remarks": "Hostel electricity dues"},
        headers=reg_headers,
    )
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["refund_status"] == "VERIFIED"
    assert v_data["request_status"] == "REFUND_VERIFIED"
    assert Decimal(str(v_data["final_amount"])) == deposit - Decimal(str(deduction_val))

    # 5. Attempt to verify again -> 400 (not in CLEARED status anymore)
    repeat_verify_res = client.post(
        f"/registrar/requests/{cleared_req.id}/verify-refund",
        json={"deductions": 0, "remarks": "Repeat"},
        headers=reg_headers,
    )
    assert repeat_verify_res.status_code == 400

    # 6. Mark processed
    proc_res = client.post(
        f"/registrar/requests/{cleared_req.id}/mark-processed",
        json={"payment_reference": "NEFT-SVSU-2026-9901"},
        headers=reg_headers,
    )
    assert proc_res.status_code == 200
    assert proc_res.json()["refund_status"] == "PROCESSED"
    assert proc_res.json()["payment_reference"] == "NEFT-SVSU-2026-9901"


# ---------------------------------------------------------------------------
# Test 17: Admin Roster CSV Upload (Good, Bad, Update)
# ---------------------------------------------------------------------------
def test_17_admin_roster_csv_upload(client: TestClient, db_session: Session):
    db = db_session
    admin = db.execute(select(User).where(User.role == UserRole.admin)).scalars().first()
    admin_headers = make_auth_headers(admin.id)

    # Pre-create student to test update flow
    _create_test_student(db, reg_num="DEMO2026002", email="priya.sharma@example.edu")

    csv_data = """registration_number,name,email,mobile,address,programme,is_hosteller,security_deposit_amount
CSV2026001,New Student One,newstudent1@example.edu,9811111111,10 New Colony,Bachelor of Technology (B.Tech.) Computer Engineering,true,5000.00
CSV2026002,Bad Prog Student,badprog@example.edu,9811111112,11 New Colony,Unknown Nonexistent Programme,false,5000.00
CSV2026003,Negative Deposit,negdep@example.edu,9811111113,12 New Colony,Bachelor of Technology (B.Tech.) Computer Engineering,false,-100.00
DEMO2026002,Priya Sharma Updated,priya.sharma@example.edu,9800000002,Updated Address 123,Bachelor of Technology (B.Tech.) Computer Engineering,true,7000.00
"""
    files = {"file": ("roster.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    upload_res = client.post("/admin/roster/upload", files=files, headers=admin_headers)
    assert upload_res.status_code == 200, upload_res.text

    report = upload_res.json()
    assert report["total_rows"] == 4
    assert report["created_count"] == 1  # CSV2026001
    assert report["updated_count"] == 1  # DEMO2026002
    assert report["rejected_count"] == 2  # CSV2026002 (bad prog) and CSV2026003 (neg deposit)

    # Verify updated row in DB
    updated_roster = db.execute(
        select(StudentRoster).where(StudentRoster.registration_number == "DEMO2026002")
    ).scalar_one()
    assert updated_roster.address == "Updated Address 123"
    assert updated_roster.security_deposit_amount == Decimal("7000.00")


# ---------------------------------------------------------------------------
# Test 18: Admin Roster Patch & Assigned Departments
# ---------------------------------------------------------------------------
def test_18_admin_roster_patch_and_assigned_departments(client: TestClient, db_session: Session):
    db = db_session
    admin = db.execute(select(User).where(User.role == UserRole.admin)).scalars().first()
    admin_headers = make_auth_headers(admin.id)

    _, roster = _create_test_student(db, reg_num="DEMO2026003", email="rohan.verma@example.edu")

    # 1. PATCH deposit and hosteller status
    patch_res = client.patch(
        f"/admin/roster/{roster.id}",
        json={"is_hosteller": False, "security_deposit_amount": 6500.00},
        headers=admin_headers,
    )
    assert patch_res.status_code == 200
    p_data = patch_res.json()
    assert p_data["is_hosteller"] is False
    assert Decimal(str(p_data["security_deposit_amount"])) == Decimal("6500.00")

    # 2. PUT assigned departments
    lab_depts = db.execute(
        select(Department).where(Department.applicability.in_(["ASSIGNED_ONLY", "LAB_WORKSHOP"]))
    ).scalars().all()
    assigned_ids = [lab_depts[0].id, lab_depts[1].id]

    put_depts_res = client.put(
        f"/admin/roster/{roster.id}/assigned-departments",
        json={"department_ids": assigned_ids},
        headers=admin_headers,
    )
    assert put_depts_res.status_code == 200
    assert set(put_depts_res.json()["assigned_department_ids"]) == set(assigned_ids)


# ---------------------------------------------------------------------------
# Test 19: Admin user provisioning, rules, password reset, and self-deactivation guard
# ---------------------------------------------------------------------------
def test_19_admin_user_provisioning_and_guards(client: TestClient, db_session: Session):
    db = db_session
    admin = db.execute(select(User).where(User.role == UserRole.admin)).scalars().first()
    admin_headers = make_auth_headers(admin.id)

    academic_dept = db.execute(
        select(Department).where(Department.kind == DepartmentKind.academic)
    ).scalars().first()
    service_dept = db.execute(
        select(Department).where(Department.kind == DepartmentKind.service)
    ).scalars().first()

    # 1. Dept officer without department -> 400
    res1 = client.post(
        "/admin/users",
        json={"email": "new.officer@example.edu", "full_name": "Test Officer", "role": "dept_officer", "department_id": None},
        headers=admin_headers,
    )
    assert res1.status_code == 400
    assert "Department ID is mandatory" in res1.json()["detail"]

    # 2. HoD assigned to service department -> 400
    res2 = client.post(
        "/admin/users",
        json={"email": "new.hod@example.edu", "full_name": "Test HoD", "role": "hod", "department_id": service_dept.id},
        headers=admin_headers,
    )
    assert res2.status_code == 400
    assert "academic department" in res2.json()["detail"]

    # 3. Valid HoD creation -> succeeds and returns temporary password
    res3 = client.post(
        "/admin/users",
        json={"email": "valid.hod@example.edu", "full_name": "Dr. Valid HoD", "role": "hod", "department_id": academic_dept.id},
        headers=admin_headers,
    )
    assert res3.status_code == 201
    created_user_data = res3.json()
    temp_pw = created_user_data["temporary_password"]
    assert temp_pw is not None
    assert len(temp_pw) >= 12
    created_user_id = created_user_data["id"]

    # 4. Admin resets user password -> returns new temporary password
    reset_res = client.post(f"/admin/users/{created_user_id}/reset-password", headers=admin_headers)
    assert reset_res.status_code == 200
    new_temp_pw = reset_res.json()["temporary_password"]
    assert new_temp_pw is not None
    assert new_temp_pw != temp_pw

    # 5. Admin cannot deactivate themselves -> 400
    self_deact_res = client.patch(f"/admin/users/{admin.id}/active", json={"is_active": False}, headers=admin_headers)
    assert self_deact_res.status_code == 400
    assert "Admin cannot deactivate their own account" in self_deact_res.json()["detail"]

    # 6. Admin can deactivate another user -> 200
    deact_res = client.patch(f"/admin/users/{created_user_id}/active", json={"is_active": False}, headers=admin_headers)
    assert deact_res.status_code == 200
    assert deact_res.json()["is_active"] is False


# ---------------------------------------------------------------------------
# Test 20: Role guards (403 Forbidden) on all new endpoints
# ---------------------------------------------------------------------------
def test_20_role_guards_on_new_endpoints(client: TestClient, db_session: Session):
    db = db_session
    student, _ = _create_test_student(db, reg_num="DEMO9020", email="student20@example.edu")
    officer = db.execute(select(User).where(User.role == UserRole.dept_officer)).scalars().first()
    student_headers = make_auth_headers(student.id)
    officer_headers = make_auth_headers(officer.id)

    # Student calling registrar or admin endpoints -> 403
    assert client.get("/registrar/queue", headers=student_headers).status_code == 403
    assert client.post("/registrar/requests/1/verify-refund", json={"deductions": 0}, headers=student_headers).status_code == 403
    assert client.get("/admin/roster", headers=student_headers).status_code == 403
    assert client.post("/admin/users", json={}, headers=student_headers).status_code == 403

    # Officer calling registrar or admin endpoints -> 403
    assert client.get("/registrar/queue", headers=officer_headers).status_code == 403
    assert client.get("/admin/roster", headers=officer_headers).status_code == 403
    assert client.get("/student/bank-details", headers=officer_headers).status_code == 403
