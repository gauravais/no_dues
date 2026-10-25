"""
Comprehensive test suite for NoDues Backend:
- Workflow engine and business rules
- Authentication, OTP verification, and JWT security
- Role-based access control (RBAC)
- Multi-threaded concurrency and state locking
- API responses and security (no password hash / unmasked bank account leaks)
"""
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import hash_password, hash_otp, create_access_token
from backend.app.models.university import Department, Programme, Faculty
from backend.app.models.roster import StudentRoster, RosterAssignedDepartment
from backend.app.models.user import User, UserRole
from backend.app.models.bank import BankDetail
from backend.app.models.clearance import (
    ClearanceRequest,
    DepartmentApproval,
    ClearanceStatus,
    ApprovalStatus,
)
from backend.app.models.certificate import Certificate
from backend.app.models.otp import SignupOTP
from backend.app.services.exceptions import (
    WorkflowConflictError,
    WorkflowBadRequestError,
    WorkflowNotFoundError,
)
from backend.app.services.workflow import (
    create_request,
    decide_approval,
    resubmit_department,
    hod_decide,
    student_resubmit_to_hod,
    get_applicable_departments,
)
from tests.conftest import make_auth_headers


# ---------------------------------------------------------------------------
# Helpers for setting up test student users & rosters
# ---------------------------------------------------------------------------

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

    # Add bank details
    db.add(
        BankDetail(
            roster_id=roster.id,
            account_holder_name="Test Student",
            account_number="123456789012",
            ifsc_code="DEMO0009001",
            bank_address="Demo Bank, Main",
        )
    )

    user = User(
        email=email,
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
# TEST 1: create_request creates approvals exactly for applicable departments
# (hosteller vs day scholar, and student with assigned labs)
# ---------------------------------------------------------------------------

def test_1_create_request_applicable_departments(db_session: Session):
    # Get available departments
    lib = db_session.execute(select(Department).where(Department.name == "Library")).scalar_one()
    sports = db_session.execute(select(Department).where(Department.name == "Sports")).scalar_one()
    hostel = db_session.execute(select(Department).where(Department.name == "Hostel (Boys/Girls)")).scalar_one()
    lab1 = db_session.execute(select(Department).where(Department.name == "Lab-1")).scalar_one()
    cs_dept = db_session.execute(select(Department).where(Department.name == "Skill Department of CS/IT")).scalar_one()

    # Case A: Day scholar without assigned labs
    user_day, roster_day = _create_test_student(db_session, "DEMO9001", "dayscholar@example.edu", is_hosteller=False)
    req_day = create_request(db_session, user_day)
    day_dept_ids = {a.department_id for a in req_day.approvals}
    # Should have Library, Sports (ALWAYS), and CS/IT (OWN_ACADEMIC), but NOT Hostel or Lab-1
    assert lib.id in day_dept_ids
    assert sports.id in day_dept_ids
    assert cs_dept.id in day_dept_ids
    assert hostel.id not in day_dept_ids
    assert lab1.id not in day_dept_ids

    # Case B: Hosteller with assigned Lab-1
    user_hostel, roster_hostel = _create_test_student(
        db_session, "DEMO9002", "hosteller@example.edu", is_hosteller=True, assigned_dept_ids=[lab1.id]
    )
    req_hostel = create_request(db_session, user_hostel)
    hostel_dept_ids = {a.department_id for a in req_hostel.approvals}
    assert lib.id in hostel_dept_ids
    assert sports.id in hostel_dept_ids
    assert cs_dept.id in hostel_dept_ids
    assert hostel.id in hostel_dept_ids
    assert lab1.id in hostel_dept_ids


# ---------------------------------------------------------------------------
# TEST 2: A second open request is refused (409 Conflict)
# ---------------------------------------------------------------------------

def test_2_second_open_request_refused(db_session: Session):
    user, _ = _create_test_student(db_session, "DEMO9003", "student9003@example.edu")
    req = create_request(db_session, user)
    assert req.status == ClearanceStatus.SUBMITTED

    # Second open request must raise WorkflowConflictError
    with pytest.raises(WorkflowConflictError, match="already has an active clearance request"):
        create_request(db_session, user)


# ---------------------------------------------------------------------------
# TEST 3: All approvals APPROVED -> HOD_REVIEW
# ---------------------------------------------------------------------------

def test_3_all_approvals_approved_transitions_to_hod_review(db_session: Session):
    user, _ = _create_test_student(db_session, "DEMO9004", "student9004@example.edu")
    req = create_request(db_session, user)

    # Approve each department approval
    for approval in req.approvals:
        # Fetch or mock officer for approval.department_id
        officer = db_session.execute(
            select(User).where(User.department_id == approval.department_id, User.role == UserRole.dept_officer)
        ).scalar_one_or_none()
        if not officer:
            officer = User(
                email=f"temp.officer.{approval.department_id}@example.edu",
                password_hash="pwd",
                role=UserRole.dept_officer,
                department_id=approval.department_id,
                is_active=True,
            )
            db_session.add(officer)
            db_session.commit()

        decide_approval(db_session, officer, approval.id, ApprovalStatus.APPROVED, "Clear")

    db_session.refresh(req)
    assert req.status == ClearanceStatus.HOD_REVIEW


# ---------------------------------------------------------------------------
# TEST 4: Rejection without remarks fails; rejection -> ACTION_NEEDED
# ---------------------------------------------------------------------------

def test_4_rejection_requires_remarks_and_sets_action_needed(db_session: Session):
    user, _ = _create_test_student(db_session, "DEMO9005", "student9005@example.edu")
    req = create_request(db_session, user)
    approval = req.approvals[0]

    officer = db_session.execute(
        select(User).where(User.department_id == approval.department_id, User.role == UserRole.dept_officer)
    ).scalar_one()

    # Rejection without remarks -> WorkflowBadRequestError
    with pytest.raises(WorkflowBadRequestError, match="Remarks are mandatory"):
        decide_approval(db_session, officer, approval.id, ApprovalStatus.REJECTED, "   ")

    # Rejection with remarks -> success, sets ACTION_NEEDED
    decide_approval(db_session, officer, approval.id, ApprovalStatus.REJECTED, "Book damaged: Rs 200 due")
    db_session.refresh(req)
    assert req.status == ClearanceStatus.ACTION_NEEDED
    assert approval.status == ApprovalStatus.REJECTED
    assert approval.remarks == "Book damaged: Rs 200 due"


# ---------------------------------------------------------------------------
# TEST 5: Resubmitting only rejected department -> PENDING; after approval -> HOD_REVIEW
# ---------------------------------------------------------------------------

def test_5_resubmit_rejected_department(db_session: Session):
    user, _ = _create_test_student(db_session, "DEMO9006", "student9006@example.edu")
    req = create_request(db_session, user)

    # Approve all except the first one
    rejected_app = req.approvals[0]
    for app in req.approvals[1:]:
        officer = db_session.execute(
            select(User).where(User.department_id == app.department_id, User.role == UserRole.dept_officer)
        ).scalar_one_or_none()
        if not officer:
            officer = User(
                email=f"temp.{app.department_id}@example.edu",
                password_hash="pwd",
                role=UserRole.dept_officer,
                department_id=app.department_id,
                is_active=True,
            )
            db_session.add(officer)
            db_session.commit()
        decide_approval(db_session, officer, app.id, ApprovalStatus.APPROVED, "Clear")

    # Reject the first one
    rej_officer = db_session.execute(
        select(User).where(User.department_id == rejected_app.department_id, User.role == UserRole.dept_officer)
    ).scalar_one()
    decide_approval(db_session, rej_officer, rejected_app.id, ApprovalStatus.REJECTED, "Pending fine")

    db_session.refresh(req)
    assert req.status == ClearanceStatus.ACTION_NEEDED

    # Student resubmits ONLY the rejected department
    resubmit_department(db_session, user, req.id, rejected_app.department_id)
    db_session.refresh(rejected_app)
    db_session.refresh(req)

    assert rejected_app.status == ApprovalStatus.PENDING
    assert rejected_app.resubmission_count == 1
    # Other approvals still APPROVED
    for a in req.approvals:
        if a.id != rejected_app.id:
            assert a.status == ApprovalStatus.APPROVED

    # Now approve the resubmitted department -> request moves to HOD_REVIEW
    decide_approval(db_session, rej_officer, rejected_app.id, ApprovalStatus.APPROVED, "Fine cleared")
    db_session.refresh(req)
    assert req.status == ClearanceStatus.HOD_REVIEW


# ---------------------------------------------------------------------------
# TEST 6: An officer cannot decide an approval of another department (404)
# ---------------------------------------------------------------------------

def test_6_officer_cannot_decide_other_department_approval(db_session: Session):
    user, _ = _create_test_student(db_session, "DEMO9007", "student9007@example.edu")
    req = create_request(db_session, user)

    # Find library approval and sports officer
    lib_approval = next(a for a in req.approvals if a.department.name == "Library")
    sports_officer = db_session.execute(
        select(User).where(User.email == "sports.officer@example.edu")
    ).scalar_one()

    # Sports officer deciding Library approval -> WorkflowNotFoundError
    with pytest.raises(WorkflowNotFoundError, match="does not belong to your assigned department"):
        decide_approval(db_session, sports_officer, lib_approval.id, ApprovalStatus.APPROVED, "OK")


# ---------------------------------------------------------------------------
# TEST 7: HoD cannot decide before HOD_REVIEW (409), HoD of other department cannot decide (404)
# ---------------------------------------------------------------------------

def test_7_hod_premature_or_unauthorized_decision(db_session: Session):
    user, _ = _create_test_student(db_session, "DEMO9008", "student9008@example.edu")
    req = create_request(db_session, user)

    hod_cs = db_session.execute(select(User).where(User.email == "hod.csit@example.edu")).scalar_one()
    hod_auto = db_session.execute(select(User).where(User.email == "hod.auto@example.edu")).scalar_one()

    # Premature decision while SUBMITTED -> WorkflowConflictError (409)
    assert req.status == ClearanceStatus.SUBMITTED
    with pytest.raises(WorkflowConflictError, match="expected HOD_REVIEW"):
        hod_decide(db_session, hod_cs, req.id, ApprovalStatus.APPROVED, None)

    # Move to HOD_REVIEW by approving all
    for a in req.approvals:
        officer = db_session.execute(
            select(User).where(User.department_id == a.department_id, User.role == UserRole.dept_officer)
        ).scalar_one_or_none()
        if not officer:
            officer = User(
                email=f"off.{a.department_id}@example.edu",
                password_hash="pwd",
                role=UserRole.dept_officer,
                department_id=a.department_id,
                is_active=True,
            )
            db_session.add(officer)
            db_session.commit()
        decide_approval(db_session, officer, a.id, ApprovalStatus.APPROVED, "OK")

    db_session.refresh(req)
    assert req.status == ClearanceStatus.HOD_REVIEW

    # HoD of Automotive trying to decide CS/IT student request -> WorkflowNotFoundError (404)
    with pytest.raises(WorkflowNotFoundError, match="does not belong to your academic department"):
        hod_decide(db_session, hod_auto, req.id, ApprovalStatus.APPROVED, "Wrong HoD")


# ---------------------------------------------------------------------------
# TEST 8: HoD APPROVE -> CLEARED and exactly one certificate row
# ---------------------------------------------------------------------------

def test_8_hod_approve_generates_certificate(db_session: Session):
    user, _ = _create_test_student(db_session, "DEMO9009", "student9009@example.edu")
    req = create_request(db_session, user)

    # Approve all department approvals
    for a in req.approvals:
        officer = db_session.execute(
            select(User).where(User.department_id == a.department_id, User.role == UserRole.dept_officer)
        ).scalar_one_or_none()
        if not officer:
            officer = User(
                email=f"off2.{a.department_id}@example.edu",
                password_hash="pwd",
                role=UserRole.dept_officer,
                department_id=a.department_id,
                is_active=True,
            )
            db_session.add(officer)
            db_session.commit()
        decide_approval(db_session, officer, a.id, ApprovalStatus.APPROVED, "OK")

    hod_cs = db_session.execute(select(User).where(User.email == "hod.csit@example.edu")).scalar_one()
    hod_decide(db_session, hod_cs, req.id, ApprovalStatus.APPROVED, "Excellent progress")

    db_session.refresh(req)
    assert req.status == ClearanceStatus.CLEARED
    assert req.hod_user_id == hod_cs.id
    assert req.hod_decided_at is not None

    # Verify exactly one certificate exists
    certs = db_session.execute(
        select(Certificate).where(Certificate.request_id == req.id)
    ).scalars().all()
    assert len(certs) == 1
    assert len(certs[0].certificate_code) == 36  # UUID length


# ---------------------------------------------------------------------------
# TEST 9: HoD REJECT -> ACTION_NEEDED; student resubmit-to-hod -> HOD_REVIEW
# ---------------------------------------------------------------------------

def test_9_hod_reject_and_resubmit_to_hod(db_session: Session):
    user, _ = _create_test_student(db_session, "DEMO9010", "student9010@example.edu")
    req = create_request(db_session, user)

    for a in req.approvals:
        officer = db_session.execute(
            select(User).where(User.department_id == a.department_id, User.role == UserRole.dept_officer)
        ).scalar_one_or_none()
        if not officer:
            officer = User(
                email=f"off3.{a.department_id}@example.edu",
                password_hash="pwd",
                role=UserRole.dept_officer,
                department_id=a.department_id,
                is_active=True,
            )
            db_session.add(officer)
            db_session.commit()
        decide_approval(db_session, officer, a.id, ApprovalStatus.APPROVED, "OK")

    hod_cs = db_session.execute(select(User).where(User.email == "hod.csit@example.edu")).scalar_one()

    # HoD rejects with mandatory remarks
    hod_decide(db_session, hod_cs, req.id, ApprovalStatus.REJECTED, "Submit project report copy to HoD office")
    db_session.refresh(req)
    assert req.status == ClearanceStatus.ACTION_NEEDED
    assert req.hod_remarks == "Submit project report copy to HoD office"

    # Student resubmits to HoD
    student_resubmit_to_hod(db_session, user, req.id)
    db_session.refresh(req)
    assert req.status == ClearanceStatus.HOD_REVIEW
    assert req.hod_remarks is None


# ---------------------------------------------------------------------------
# TEST 10: Concurrency - two threads decide the last two approvals simultaneously
# ---------------------------------------------------------------------------

def test_10_concurrency_last_two_approvals(test_engine, TestingSessionLocal):
    # Set up request in its own transaction
    setup_session = TestingSessionLocal()
    user, _ = _create_test_student(setup_session, "DEMO9011", "student9011@example.edu")
    req = create_request(setup_session, user)

    # Approve all except the last two
    other_approvals = req.approvals[:-2]
    last_two_approvals = req.approvals[-2:]

    for a in other_approvals:
        officer = setup_session.execute(
            select(User).where(User.department_id == a.department_id, User.role == UserRole.dept_officer)
        ).scalar_one_or_none()
        if not officer:
            officer = User(
                email=f"off_conc.{a.department_id}@example.edu",
                password_hash="pwd",
                role=UserRole.dept_officer,
                department_id=a.department_id,
                is_active=True,
            )
            setup_session.add(officer)
            setup_session.commit()
        decide_approval(setup_session, officer, a.id, ApprovalStatus.APPROVED, "OK")

    app1_id, dept1_id = last_two_approvals[0].id, last_two_approvals[0].department_id
    app2_id, dept2_id = last_two_approvals[1].id, last_two_approvals[1].department_id
    req_id = req.id
    setup_session.close()

    def worker(approval_id, dept_id):
        sess = TestingSessionLocal()
        officer = sess.execute(
            select(User).where(User.department_id == dept_id, User.role == UserRole.dept_officer)
        ).scalar_one_or_none()
        if not officer:
            officer = User(
                email=f"worker_off_{dept_id}@example.edu",
                password_hash="pwd",
                role=UserRole.dept_officer,
                department_id=dept_id,
                is_active=True,
            )
            sess.add(officer)
            sess.commit()
        decide_approval(sess, officer, approval_id, ApprovalStatus.APPROVED, "Concurrent OK")
        sess.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(worker, app1_id, dept1_id)
        f2 = executor.submit(worker, app2_id, dept2_id)
        f1.result()
        f2.result()

    verify_session = TestingSessionLocal()
    final_req = verify_session.get(ClearanceRequest, req_id)
    assert final_req.status == ClearanceStatus.HOD_REVIEW
    verify_session.close()


# ---------------------------------------------------------------------------
# TEST 11: Sign-up: success, wrong OTP, expired OTP, 5-attempt limit, unknown reg, wrong email, duplicate
# ---------------------------------------------------------------------------

def test_11_signup_full_flow_and_validations(client, db_session: Session):
    prog = db_session.execute(select(Programme)).scalars().first()

    # 1. Setup roster row without user
    roster = StudentRoster(
        registration_number="DEMO8888",
        name="Candidate Student",
        email="candidate.student@example.edu",
        mobile="9800008888",
        address="888 Candidate Way",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=5000.0,
    )
    db_session.add(roster)
    db_session.commit()

    # Unknown registration number -> 400
    res_unk = client.post("/auth/signup/request-otp", json={"registration_number": "UNKNOWN99", "email": "any@example.edu"})
    assert res_unk.status_code == 400

    # Wrong email for registration number -> 400
    res_wrong_email = client.post("/auth/signup/request-otp", json={"registration_number": "DEMO8888", "email": "wrong@example.edu"})
    assert res_wrong_email.status_code == 400

    # Disallowed email domain -> 400
    res_disallowed = client.post("/auth/signup/request-otp", json={"registration_number": "DEMO8888", "email": "candidate@gmail.com"})
    assert res_disallowed.status_code == 400

    # Request OTP successfully
    res_otp = client.post("/auth/signup/request-otp", json={"registration_number": "DEMO8888", "email": "candidate.student@example.edu"})
    assert res_otp.status_code == 200

    # Check OTP in database
    otp_record = db_session.execute(
        select(SignupOTP).where(SignupOTP.registration_number == "DEMO8888")
    ).scalar_one()

    # Wrong OTP -> 400
    res_wrong_otp = client.post("/auth/signup/verify", json={"registration_number": "DEMO8888", "otp": "000000", "password": "NewPassword@123"})
    assert res_wrong_otp.status_code == 400
    assert "attempt(s) remaining" in res_wrong_otp.json()["detail"]

    # Test 5-attempt limit: submit wrong OTP 4 more times (total 5)
    for _ in range(4):
        client.post("/auth/signup/verify", json={"registration_number": "DEMO8888", "otp": "000000", "password": "NewPassword@123"})

    res_exceeded = client.post("/auth/signup/verify", json={"registration_number": "DEMO8888", "otp": "000000", "password": "NewPassword@123"})
    assert res_exceeded.status_code == 400
    assert "exceeded" in res_exceeded.json()["detail"]

    # Test expired OTP
    now = datetime.now(timezone.utc)
    expired_otp = SignupOTP(
        email="candidate.student@example.edu",
        registration_number="DEMO8888",
        code_hash=hash_otp("112233"),
        expires_at=now - timedelta(minutes=1),
        attempts=0,
        consumed_at=None,
        created_at=now - timedelta(minutes=15),
    )
    db_session.add(expired_otp)
    db_session.commit()

    res_expired = client.post("/auth/signup/verify", json={"registration_number": "DEMO8888", "otp": "112233", "password": "NewPassword@123"})
    assert res_expired.status_code == 400
    assert "expired" in res_expired.json()["detail"]

    # Valid OTP -> Success
    valid_otp = SignupOTP(
        email="candidate.student@example.edu",
        registration_number="DEMO8888",
        code_hash=hash_otp("998877"),
        expires_at=now + timedelta(minutes=10),
        attempts=0,
        consumed_at=None,
        created_at=now,
    )
    db_session.add(valid_otp)
    db_session.commit()

    res_verify = client.post("/auth/signup/verify", json={"registration_number": "DEMO8888", "otp": "998877", "password": "NewPassword@123"})
    assert res_verify.status_code == 201
    assert "access_token" in res_verify.json()

    # Duplicate sign-up -> request-otp returns 409
    res_dup = client.post("/auth/signup/request-otp", json={"registration_number": "DEMO8888", "email": "candidate.student@example.edu"})
    assert res_dup.status_code == 409


# ---------------------------------------------------------------------------
# TEST 12: Role guards (student calling /department/* or /hod/* gets 403)
# and no response contains password_hash or full account number
# ---------------------------------------------------------------------------

def test_12_role_guards_and_data_privacy(client, db_session: Session):
    user, _ = _create_test_student(db_session, "DEMO9012", "student9012@example.edu")
    headers = make_auth_headers(user.id)

    # Student trying to call department queue -> 403
    res_dept = client.get("/department/queue", headers=headers)
    assert res_dept.status_code == 403

    # Student trying to call HoD queue -> 403
    res_hod = client.get("/hod/queue", headers=headers)
    assert res_hod.status_code == 403

    # Check /auth/me profile
    res_me = client.get("/auth/me", headers=headers)
    assert res_me.status_code == 200
    data = res_me.json()
    response_text = res_me.text

    # Verify no password_hash in response
    assert "password_hash" not in response_text
    assert "argon2" not in response_text

    # Verify full account number 123456789012 is NOT in response
    assert "123456789012" not in response_text
    # Verify account number is masked with last 4 digits
    assert data["roster"]["masked_bank_account"] == "********9012"
