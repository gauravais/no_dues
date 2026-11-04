"""Comprehensive tests for audit & hardening pass:
- Declarations on clearance requests (hostel, lab courses, notes).
- Mid-clearance subject declarations dropping HOD_REVIEW to SUBMITTED.
- Academic officer and HoD adding departments to active requests with guards & audit.
- Lab officer queue showing declared subjects.
- HoD & Academic officer detail views with declarations, added-by info, and can_add_departments.
- Bank details required on application.
- Registrar verify-refund requiring deposit, deductions, remarks, overriding draft deposit.
- Lab catalog scoping including university-wide (academic_department_id is null) courses.
- Roster provenance (source, created_by_user_id) visible to registrar, hidden from students.
- Bank account encryption at rest with Fernet.
- Audited registrar reveal endpoint with state guard, 403, 409, 429 rate limit, and clean audit trail.
"""
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.core.security import hash_password
from backend.app.core.crypto import decrypt_bank_account
from backend.app.models.user import User, UserRole
from backend.app.models.roster import StudentRoster
from backend.app.models.university import Department, Programme, DepartmentApplicability, DepartmentKind
from backend.app.models.lab_course import LabCourse
from backend.app.models.bank import BankDetail
from backend.app.models.clearance import (
    ClearanceRequest,
    DepartmentApproval,
    ClearanceStatus,
    ApprovalStatus,
)
from backend.app.models.refund import Refund, RefundStatus
from backend.app.models.audit import AuditLog
from backend.app.services.workflow import (
    create_request,
    decide_approval,
    hod_decide,
    add_office_to_request,
    student_declare_lab_courses,
)
from tests.conftest import make_auth_headers


def _setup_student_with_bank(
    db: Session,
    reg_num: str = "DEMO9901",
    email: str = "student9901@example.edu",
    is_hosteller: bool = False,
    deposit: float = 5000.0,
) -> tuple[User, StudentRoster]:
    prog = db.execute(select(Programme)).scalars().first()
    now = datetime.now(timezone.utc)

    roster = StudentRoster(
        registration_number=reg_num,
        name="Hardening Student",
        email=email,
        mobile="9800009901",
        address="100 Hardening Ave",
        programme_id=prog.id,
        is_hosteller=is_hosteller,
        security_deposit_amount=deposit,
        source="department_upload",
    )
    db.add(roster)
    db.flush()

    db.add(
        BankDetail(
            roster_id=roster.id,
            account_holder_name="Hardening Student",
            account_number="123456789901",
            ifsc_code="DEMO0009901",
            bank_address="Hardening Branch, Palwal",
        )
    )

    user = User(
        email=email,
        full_name="Hardening Student",
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
    db.refresh(roster)
    return user, roster


# ---------------------------------------------------------------------------
# 1. Declarations stored on request; hostel computed from declaration
# ---------------------------------------------------------------------------
def test_declarations_stored_on_request_and_hostel_computation(db_session: Session):
    db = db_session
    # Roster has is_hosteller = False, but student declares is_hosteller = True
    user, roster = _setup_student_with_bank(db, "DECL001", "decl001@example.edu", is_hosteller=False)

    # Setup lab course
    lab_dept = db.execute(select(Department).where(Department.name == "Lab-1")).scalar_one()
    course = LabCourse(
        code="CS-L101",
        name="Data Structures Lab",
        academic_department_id=roster.programme.academic_department_id,
        lab_department_id=lab_dept.id,
        is_active=True,
    )
    db.add(course)
    db.commit()

    req = create_request(
        session=db,
        student_user=user,
        declared_is_hosteller=True,
        declared_lab_course_ids=[course.id],
        others_note="Leaving campus room early",
    )

    assert req.declared_is_hosteller is True
    assert roster.is_hosteller is False  # Roster is NOT mutated!
    assert req.others_note == "Leaving campus room early"
    assert len(req.declared_lab_courses) == 1
    assert req.declared_lab_courses[0].code == "CS-L101"

    # Approvals must include Hostel and Lab-1
    dept_ids = {a.department_id for a in req.approvals}
    hostel_dept = db.execute(select(Department).where(Department.name == "Hostel (Boys/Girls)")).scalar_one()
    assert hostel_dept.id in dept_ids
    assert lab_dept.id in dept_ids


# ---------------------------------------------------------------------------
# 2. Student declares more lab subjects mid-clearance
# ---------------------------------------------------------------------------
def test_student_declares_more_lab_subjects_drops_hod_review(db_session: Session):
    db = db_session
    user, roster = _setup_student_with_bank(db, "DECL002", "decl002@example.edu", is_hosteller=False)

    # Lab 1 and Lab 2 courses
    lab1_dept = db.execute(select(Department).where(Department.name == "Lab-1")).scalar_one()
    lab2_dept = db.execute(select(Department).where(Department.name == "Lab-2")).scalar_one()

    c1 = LabCourse(code="L1", name="Lab 1 Course", lab_department_id=lab1_dept.id, is_active=True)
    c2 = LabCourse(code="L2", name="Lab 2 Course", lab_department_id=lab2_dept.id, is_active=True)
    db.add_all([c1, c2])
    db.commit()

    req = create_request(db, user, declared_is_hosteller=False, declared_lab_course_ids=[c1.id])
    assert any(a.department_id == lab1_dept.id for a in req.approvals)
    assert not any(a.department_id == lab2_dept.id for a in req.approvals)

    # Approve all existing approvals so request reaches HOD_REVIEW
    for app in req.approvals:
        officer = db.execute(select(User).where(User.department_id == app.department_id)).scalars().first()
        decide_approval(db, officer, app.id, ApprovalStatus.APPROVED, remarks=None)

    db.refresh(req)
    assert req.status == ClearanceStatus.HOD_REVIEW

    # Student declares course c2 mid-clearance
    updated_req = student_declare_lab_courses(db, user, req.id, [c1.id, c2.id])
    assert updated_req.status == ClearanceStatus.SUBMITTED  # Dropped back to SUBMITTED!
    assert any(a.department_id == lab2_dept.id for a in updated_req.approvals)


# ---------------------------------------------------------------------------
# 3. Academic officer and HoD adding an office: guards and effects
# ---------------------------------------------------------------------------
def test_academic_officer_and_hod_add_department_guards(client: TestClient, db_session: Session):
    db = db_session
    user, roster = _setup_student_with_bank(db, "ADDOFF01", "addoff01@example.edu", is_hosteller=False)
    req = create_request(db, user, declared_is_hosteller=False)

    acad_officer = db.execute(
        select(User).where(User.role == UserRole.dept_officer, User.department_id == roster.programme.academic_department_id)
    ).scalars().first()
    hod_user = db.execute(
        select(User).where(User.role == UserRole.hod, User.department_id == roster.programme.academic_department_id)
    ).scalars().first()
    foreign_officer = db.execute(
        select(User).where(User.role == UserRole.dept_officer, User.department_id != roster.programme.academic_department_id)
    ).scalars().first()

    acad_headers = make_auth_headers(acad_officer.id)
    hod_headers = make_auth_headers(hod_user.id)
    foreign_headers = make_auth_headers(foreign_officer.id)

    target_dept = db.execute(select(Department).where(Department.name == "Lab-1")).scalar_one()

    # Reason missing -> 422/400
    res_bad = client.post(
        f"/department/requests/{req.id}/add-department",
        json={"department_id": target_dept.id, "reason": ""},
        headers=acad_headers,
    )
    assert res_bad.status_code in (400, 422)

    # Foreign academic officer -> 404
    res_foreign = client.post(
        f"/department/requests/{req.id}/add-department",
        json={"department_id": target_dept.id, "reason": "Testing dues"},
        headers=foreign_headers,
    )
    assert res_foreign.status_code in (403, 404)

    # Success path for academic officer
    res_ok = client.post(
        f"/department/requests/{req.id}/add-department",
        json={"department_id": target_dept.id, "reason": "Unreturned equipment in Lab 1"},
        headers=acad_headers,
    )
    assert res_ok.status_code == 200, res_ok.text
    data_ok = res_ok.json()
    assert data_ok["department_id"] == target_dept.id
    assert data_ok["added_by_user_id"] == acad_officer.id
    assert data_ok["added_reason"] == "Unreturned equipment in Lab 1"
    assert data_ok["status"] == "PENDING"

    # Adding already added office -> 409
    res_dup = client.post(
        f"/department/requests/{req.id}/add-department",
        json={"department_id": target_dept.id, "reason": "Duplicate addition"},
        headers=acad_headers,
    )
    assert res_dup.status_code == 409

    # HoD adds another office (Lab-2)
    target_dept2 = db.execute(select(Department).where(Department.name == "Lab-2")).scalar_one()
    res_hod = client.post(
        f"/hod/requests/{req.id}/add-department",
        json={"department_id": target_dept2.id, "reason": "Robotics workshop component fee"},
        headers=hod_headers,
    )
    assert res_hod.status_code == 200, res_hod.text
    data_hod = res_hod.json()
    assert data_hod["department_id"] == target_dept2.id
    assert data_hod["added_by_user_id"] == hod_user.id
    assert data_hod["added_reason"] == "Robotics workshop component fee"

    # Verify audit log entries
    audits = db.execute(
        select(AuditLog).where(AuditLog.action == "OFFICE_ADDED_BY_STAFF", AuditLog.entity_id.in_([data_ok["id"], data_hod["id"]]))
    ).scalars().all()
    assert len(audits) == 2


# ---------------------------------------------------------------------------
# 4. Lab officer queue shows declared subjects matching that lab
# ---------------------------------------------------------------------------
def test_lab_officer_queue_shows_matching_declared_subjects(client: TestClient, db_session: Session):
    db = db_session
    user, roster = _setup_student_with_bank(db, "QUEUE01", "queue01@example.edu", is_hosteller=False)

    lab1_dept = db.execute(select(Department).where(Department.name == "Lab-1")).scalar_one()
    c1 = LabCourse(code="L101", name="Embedded Systems Lab", lab_department_id=lab1_dept.id, is_active=True)
    db.add(c1)
    db.commit()

    create_request(db, user, declared_is_hosteller=False, declared_lab_course_ids=[c1.id])

    lab1_officer = db.execute(
        select(User).where(User.role == UserRole.dept_officer, User.department_id == lab1_dept.id)
    ).scalars().first()
    headers = make_auth_headers(lab1_officer.id)

    res = client.get("/department/queue", headers=headers)
    assert res.status_code == 200
    items = res.json()["items"]
    target_item = next((i for i in items if i["registration_number"] == "QUEUE01"), None)
    assert target_item is not None
    assert any("Embedded Systems Lab" in s for s in target_item["declared_subjects"])


# ---------------------------------------------------------------------------
# 5. Detail views for Academic Officer and HoD
# ---------------------------------------------------------------------------
def test_academic_and_hod_detail_views(client: TestClient, db_session: Session):
    db = db_session
    user, roster = _setup_student_with_bank(db, "DETAIL01", "detail01@example.edu", is_hosteller=True)

    lab1_dept = db.execute(select(Department).where(Department.name == "Lab-1")).scalar_one()
    c1 = LabCourse(code="VLSI", name="VLSI Design Lab", lab_department_id=lab1_dept.id, is_active=True)
    db.add(c1)
    db.commit()

    req = create_request(
        db,
        user,
        declared_is_hosteller=True,
        declared_lab_course_ids=[c1.id],
        others_note="Graduating batch 2026",
    )

    acad_officer = db.execute(
        select(User).where(User.role == UserRole.dept_officer, User.department_id == roster.programme.academic_department_id)
    ).scalars().first()
    hod_user = db.execute(
        select(User).where(User.role == UserRole.hod, User.department_id == roster.programme.academic_department_id)
    ).scalars().first()

    # Academic officer detail view
    res_acad = client.get(f"/department/requests/{req.id}", headers=make_auth_headers(acad_officer.id))
    assert res_acad.status_code == 200, res_acad.text
    d_acad = res_acad.json()
    assert d_acad["declared_is_hosteller"] is True
    assert d_acad["others_note"] == "Graduating batch 2026"
    assert any("VLSI Design Lab" in s for s in d_acad["declared_subjects"])
    assert len(d_acad["can_add_departments"]) > 0

    # HoD detail view
    res_hod = client.get(f"/hod/requests/{req.id}", headers=make_auth_headers(hod_user.id))
    assert res_hod.status_code == 200, res_hod.text
    d_hod = res_hod.json()
    assert d_hod["declared_is_hosteller"] is True
    assert d_hod["others_note"] == "Graduating batch 2026"
    assert any("VLSI Design Lab" in s for s in d_hod["declared_subjects"])
    assert len(d_hod["can_add_departments"]) > 0


# ---------------------------------------------------------------------------
# 6. Registrar verify-refund: overrides deposit and sets deductions & remarks
# ---------------------------------------------------------------------------
def test_registrar_verify_refund_overrides_deposit(client: TestClient, db_session: Session):
    db = db_session
    user, roster = _setup_student_with_bank(db, "REFUND01", "refund01@example.edu", deposit=5000.0)
    req = create_request(db, user, declared_is_hosteller=False)

    # Approve all approvals to reach CLEARED
    for app in req.approvals:
        officer = db.execute(select(User).where(User.department_id == app.department_id)).scalars().first()
        decide_approval(db, officer, app.id, ApprovalStatus.APPROVED, remarks=None)
    hod_user = db.execute(
        select(User).where(User.role == UserRole.hod, User.department_id == req.roster_entry.programme.academic_department_id)
    ).scalars().first()
    cleared_req = hod_decide(db, hod_user, req.id, ApprovalStatus.APPROVED, remarks=None)
    assert cleared_req.status == ClearanceStatus.CLEARED

    reg_user = db.execute(select(User).where(User.role == UserRole.registrar_accounts)).scalars().first()
    reg_headers = make_auth_headers(reg_user.id)

    # Verify refund with verified deposit = 6000.00 and deductions = 500.00
    res_verify = client.post(
        f"/registrar/requests/{cleared_req.id}/verify-refund",
        json={
            "deposit_amount": 6000.0,
            "deductions": 500.0,
            "remarks": "Official university deposit ledger checked. Deducted Rs. 500 library late fee.",
        },
        headers=reg_headers,
    )
    assert res_verify.status_code == 200, res_verify.text
    data = res_verify.json()
    assert float(data["deposit_amount"]) == 6000.0
    assert float(data["deductions"]) == 500.0
    assert float(data["final_amount"]) == 5500.0
    assert data["request_status"] == "REFUND_VERIFIED"

    # Check refund record in DB
    refund = db.execute(select(Refund).where(Refund.request_id == cleared_req.id)).scalar_one()
    assert refund.deposit_amount == Decimal("6000.00")
    assert refund.deductions == Decimal("500.00")
    assert refund.final_amount == Decimal("5500.00")

    audit = db.execute(
        select(AuditLog).where(AuditLog.action == "VERIFY_REFUND", AuditLog.entity_id == cleared_req.id)
    ).scalar_one()
    assert audit.details["remarks"] == "Official university deposit ledger checked. Deducted Rs. 500 library late fee."


# ---------------------------------------------------------------------------
# 7. Lab catalog scoping includes university-wide subjects
# ---------------------------------------------------------------------------
def test_lab_catalog_scoping_includes_university_wide(client: TestClient, db_session: Session):
    db = db_session
    user, roster = _setup_student_with_bank(db, "CATALOG01", "catalog01@example.edu")
    lab1_dept = db.execute(select(Department).where(Department.name == "Lab-1")).scalar_one()

    # Subject with academic_department_id = NULL (university-wide open elective)
    univ_course = LabCourse(
        code="UNIV-L01",
        name="Central IoT Lab",
        academic_department_id=None,
        lab_department_id=lab1_dept.id,
        is_active=True,
    )
    db.add(univ_course)
    db.commit()

    res = client.get("/student/lab-catalog", headers=make_auth_headers(user.id))
    assert res.status_code == 200
    courses = res.json()["lab_courses"]
    assert any(c["code"] == "UNIV-L01" for c in courses)


# ---------------------------------------------------------------------------
# 8. Roster provenance visible to registrar, hidden from students
# ---------------------------------------------------------------------------
def test_roster_provenance_visibility(client: TestClient, db_session: Session):
    db = db_session
    user, roster = _setup_student_with_bank(db, "PROV001", "prov001@example.edu")
    req = create_request(db, user, declared_is_hosteller=False)

    reg_user = db.execute(select(User).where(User.role == UserRole.registrar_accounts)).scalars().first()

    # Registrar view shows roster_source
    res_reg = client.get(f"/registrar/requests/{req.id}", headers=make_auth_headers(reg_user.id))
    assert res_reg.status_code == 200, res_reg.text
    data_reg = res_reg.json()
    assert data_reg["roster_source"] == "department_upload"

    # Student clearance view does NOT leak roster provenance or creator
    res_student = client.get("/student/requests/current", headers=make_auth_headers(user.id))
    assert res_student.status_code == 200
    data_stud = res_student.json()
    assert "roster_source" not in data_stud
    assert "roster_created_by_user_id" not in data_stud


# ---------------------------------------------------------------------------
# 9. Bank account encryption at rest with Fernet
# ---------------------------------------------------------------------------
def test_bank_account_encrypted_at_rest(db_session: Session):
    db = db_session
    user, roster = _setup_student_with_bank(db, "CRYPTO01", "crypto01@example.edu")

    # Raw SQL query directly on the table
    raw_acc = db.execute(
        text("SELECT account_number FROM bank_details WHERE roster_id = :rid"),
        {"rid": roster.id},
    ).scalar()

    # Must be encrypted ciphertext, NOT plaintext!
    assert raw_acc != "123456789901"
    assert raw_acc.startswith("gAAAAA")

    # Decrypt roundtrip must yield original
    plain = decrypt_bank_account(raw_acc)
    assert plain == "123456789901"


# ---------------------------------------------------------------------------
# 10. Audited Registrar Reveal Endpoint: state guards, rate limit, audit trail
# ---------------------------------------------------------------------------
def test_registrar_reveal_bank_details(client: TestClient, db_session: Session):
    db = db_session
    user, roster = _setup_student_with_bank(db, "REVEAL01", "reveal01@example.edu")
    req = create_request(db, user, declared_is_hosteller=False)

    reg_user = db.execute(select(User).where(User.role == UserRole.registrar_accounts)).scalars().first()
    reg_headers = make_auth_headers(reg_user.id)
    student_headers = make_auth_headers(user.id)

    # 1. 403 for non-registrar
    res_403 = client.post(f"/registrar/requests/{req.id}/reveal-bank-details", headers=student_headers)
    assert res_403.status_code == 403

    # 2. 409 while request is SUBMITTED
    res_409 = client.post(f"/registrar/requests/{req.id}/reveal-bank-details", headers=reg_headers)
    assert res_409.status_code == 409

    # Approve and clear request
    for app in req.approvals:
        officer = db.execute(select(User).where(User.department_id == app.department_id)).scalars().first()
        decide_approval(db, officer, app.id, ApprovalStatus.APPROVED, remarks=None)
    hod_user = db.execute(
        select(User).where(User.role == UserRole.hod, User.department_id == req.roster_entry.programme.academic_department_id)
    ).scalars().first()
    hod_decide(db, hod_user, req.id, ApprovalStatus.APPROVED, remarks=None)

    # 3. 200 for registrar once CLEARED
    res_200 = client.post(f"/registrar/requests/{req.id}/reveal-bank-details", headers=reg_headers)
    assert res_200.status_code == 200, res_200.text
    revealed = res_200.json()
    assert revealed["account_number"] == "123456789901"
    assert revealed["account_holder_name"] == "Hardening Student"
    assert revealed["ifsc_code"] == "DEMO0009901"

    # 4. Check audit log (MUST NOT contain account number)
    audit = db.execute(
        select(AuditLog).where(AuditLog.action == "BANK_DETAILS_REVEALED", AuditLog.entity_id == req.id)
    ).scalar_one()
    assert "123456789901" not in str(audit.details)

    # 5. Rate limit: 10 calls per minute limit
    # We already made 1 call (res_200), let's make 9 more to hit 10, then the 11th should be 429
    for _ in range(9):
        client.post(f"/registrar/requests/{req.id}/reveal-bank-details", headers=reg_headers)

    res_429 = client.post(f"/registrar/requests/{req.id}/reveal-bank-details", headers=reg_headers)
    assert res_429.status_code == 429
    assert "Rate limit exceeded" in res_429.json()["detail"]


# ---------------------------------------------------------------------------
# 11. Student applying without bank details is rejected
# ---------------------------------------------------------------------------
def test_applying_without_bank_details_refused(client: TestClient, db_session: Session):
    db = db_session
    prog = db.execute(select(Programme)).scalars().first()
    now = datetime.now(timezone.utc)

    roster = StudentRoster(
        registration_number="NOBANK01",
        name="No Bank Student",
        email="nobank01@example.edu",
        mobile="9800008888",
        address="No Bank Address",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=5000.0,
    )
    db.add(roster)
    db.flush()

    user = User(
        email="nobank01@example.edu",
        full_name="No Bank Student",
        password_hash=hash_password("StudentPass@123"),
        role=UserRole.student,
        department_id=None,
        roster_id=roster.id,
        is_active=True,
        created_at=now,
    )
    db.add(user)
    db.commit()

    # Calling create_request without bank details -> WorkflowBadRequestError
    with pytest.raises(Exception) as exc_info:
        create_request(db, user)
    assert "Bank details must be provided" in str(exc_info.value)

