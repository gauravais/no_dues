"""
Hardening tests for workflow engine:
1. Concurrency race on decide_approval (20 repetitions):
   Two threads decide the SAME approval at the exact same moment (one Approve, one Reject).
   Exactly one succeeds and the other gets 409 (WorkflowConflictError), and the stored decision matches the winner.
2. Concurrency race on create_request:
   Two threads call create_request for the same student at the same moment.
   Exactly one succeeds, the other gets 409, and exactly one request and one set of approvals exist in the database.
3. HoD security & authorization:
   HoD of another department gets 404 (WorkflowNotFoundError) both for a HOD_REVIEW request and for a SUBMITTED request,
   never revealing clearance status to unauthorized HoDs.
4. Previous rejection reason:
   API returns previous_remarks separately from decision remarks to students after resubmission,
   and previous remarks are preserved in the audit log.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from backend.app.core.security import hash_password
from backend.app.models.user import User, UserRole
from backend.app.models.roster import StudentRoster
from backend.app.models.university import Department, Programme, DepartmentKind
from backend.app.models.clearance import (
    ClearanceRequest,
    DepartmentApproval,
    ClearanceStatus,
    ApprovalStatus,
)
from backend.app.models.bank import BankDetail
from backend.app.models.audit import AuditLog
from backend.app.services.exceptions import (
    WorkflowConflictError,
    WorkflowNotFoundError,
)
from backend.app.services.workflow import (
    create_request,
    decide_approval,
    hod_decide,
)
from tests.conftest import make_auth_headers


def _setup_student_with_bank(
    db: Session,
    reg_num: str,
    email: str,
    dept_name: str = "Skill Department of CS/IT",
) -> User:
    """Helper to provision a student with linked roster and bank details."""
    dept = db.execute(select(Department).where(Department.name == dept_name)).scalar_one()
    prog = db.execute(select(Programme).where(Programme.academic_department_id == dept.id)).scalars().first()
    now = datetime.now(timezone.utc)

    roster = StudentRoster(
        registration_number=reg_num,
        name=f"Student {reg_num}",
        email=email,
        mobile="9800000000",
        address="123 Test Campus Road",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=5000.0,
    )
    db.add(roster)
    db.flush()

    db.add(
        BankDetail(
            roster_id=roster.id,
            account_holder_name=f"Student {reg_num}",
            account_number="123456789012",
            ifsc_code="SBIN0001234",
            bank_address="SBI Main Campus Branch",
        )
    )

    user = User(
        email=email,
        full_name=f"Student {reg_num}",
        password_hash=hash_password("Pass@12345"),
        role=UserRole.student,
        department_id=None,
        roster_id=roster.id,
        is_active=True,
        created_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# TEST: decide_approval race condition (20 repetitions)
# ---------------------------------------------------------------------------
def test_decide_approval_concurrency_race(test_engine, TestingSessionLocal):
    """
    Two threads decide the SAME approval at the exact same moment:
    Thread A: Approve
    Thread B: Reject
    In every run, exactly one must succeed and the other must get 409 (WorkflowConflictError).
    The stored decision in DB must match the winning thread.
    Repeated 20 times to verify stability.
    """
    NUM_ROUNDS = 20

    for i in range(NUM_ROUNDS):
        setup_session = TestingSessionLocal()
        reg_num = f"RACE_APP_{i:03d}"
        email = f"race_app_{i:03d}@example.edu"
        student_user = _setup_student_with_bank(setup_session, reg_num, email)

        req = create_request(setup_session, student_user)
        target_app = req.approvals[0]
        approval_id = target_app.id
        dept_id = target_app.department_id

        # Find or create officer for this department
        officer = setup_session.execute(
            select(User).where(User.department_id == dept_id, User.role == UserRole.dept_officer)
        ).scalars().first()
        if not officer:
            officer = User(
                email=f"race_off_{dept_id}_{i}@example.edu",
                full_name="Race Officer",
                password_hash=hash_password("pw"),
                role=UserRole.dept_officer,
                department_id=dept_id,
                is_active=True,
            )
            setup_session.add(officer)
            setup_session.commit()

        officer_id = officer.id
        setup_session.close()

        # Worker tasks
        def worker_approve():
            sess = TestingSessionLocal()
            off = sess.get(User, officer_id)
            try:
                decide_approval(sess, off, approval_id, ApprovalStatus.APPROVED, "Approved by Thread A")
                return ("SUCCESS", ApprovalStatus.APPROVED, "Approved by Thread A")
            except WorkflowConflictError as e:
                return ("CONFLICT_409", None, str(e))
            finally:
                sess.close()

        def worker_reject():
            sess = TestingSessionLocal()
            off = sess.get(User, officer_id)
            try:
                decide_approval(sess, off, approval_id, ApprovalStatus.REJECTED, "Rejected by Thread B")
                return ("SUCCESS", ApprovalStatus.REJECTED, "Rejected by Thread B")
            except WorkflowConflictError as e:
                return ("CONFLICT_409", None, str(e))
            finally:
                sess.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(worker_approve)
            f2 = executor.submit(worker_reject)
            r1 = f1.result()
            r2 = f2.result()

        results = [r1, r2]
        statuses = [r[0] for r in results]

        # Exactly one must succeed and one must get 409
        assert statuses.count("SUCCESS") == 1, f"Round {i}: Expected exactly 1 SUCCESS, got {statuses}"
        assert statuses.count("CONFLICT_409") == 1, f"Round {i}: Expected exactly 1 CONFLICT_409, got {statuses}"

        winner = next(r for r in results if r[0] == "SUCCESS")
        winning_decision = winner[1]
        winning_remarks = winner[2]

        # Check DB record matches the winner
        verify_sess = TestingSessionLocal()
        final_app = verify_sess.get(DepartmentApproval, approval_id)
        assert final_app.status == winning_decision, f"Round {i}: Stored status {final_app.status} does not match winner {winning_decision}"
        assert final_app.remarks == winning_remarks, f"Round {i}: Stored remarks {final_app.remarks} does not match winner {winning_remarks}"
        verify_sess.close()


# ---------------------------------------------------------------------------
# TEST: create_request race condition
# ---------------------------------------------------------------------------
def test_create_request_concurrency_race(test_engine, TestingSessionLocal):
    """
    Two threads call create_request for the same student at the exact same moment.
    Row-level lock on student_roster + partial unique index on clearance_requests ensures:
    - Exactly one succeeds.
    - Exactly one gets 409 (WorkflowConflictError).
    - Exactly one ClearanceRequest and one set of approvals exist in the database.
    """
    setup_session = TestingSessionLocal()
    student_user = _setup_student_with_bank(setup_session, "RACE_REQ_001", "race_req_001@example.edu")
    student_user_id = student_user.id
    roster_id = student_user.roster_id
    setup_session.close()

    def worker_create():
        sess = TestingSessionLocal()
        u = sess.get(User, student_user_id)
        try:
            req = create_request(sess, u)
            return ("SUCCESS", req.id)
        except WorkflowConflictError as e:
            return ("CONFLICT_409", str(e))
        finally:
            sess.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(worker_create)
        f2 = executor.submit(worker_create)
        r1 = f1.result()
        r2 = f2.result()

    results = [r1, r2]
    outcomes = [r[0] for r in results]

    assert outcomes.count("SUCCESS") == 1, f"Expected 1 SUCCESS, got {outcomes}"
    assert outcomes.count("CONFLICT_409") == 1, f"Expected 1 CONFLICT_409, got {outcomes}"
    assert "Student already has an active clearance request." in next(r[1] for r in results if r[0] == "CONFLICT_409")

    # Verify database integrity: exactly one request and one set of approvals
    verify_sess = TestingSessionLocal()
    requests = verify_sess.execute(
        select(ClearanceRequest).where(ClearanceRequest.roster_id == roster_id)
    ).scalars().all()
    assert len(requests) == 1

    approvals = verify_sess.execute(
        select(DepartmentApproval).where(DepartmentApproval.request_id == requests[0].id)
    ).scalars().all()
    assert len(approvals) > 0  # Expected set of approvals exists
    verify_sess.close()


# ---------------------------------------------------------------------------
# TEST: HoD 404 vs 409 department guard
# ---------------------------------------------------------------------------
def test_hod_decide_unauthorized_department_404_on_submitted_and_hod_review(TestingSessionLocal):
    """
    HoD of another department gets 404 (WorkflowNotFoundError) both for a HOD_REVIEW request
    and for a SUBMITTED request, preventing state leakage across academic faculties.
    """
    sess = TestingSessionLocal()
    # Student in CS/IT
    student_user = _setup_student_with_bank(
        sess, "HOD_SEC_001", "hod_sec_001@example.edu", dept_name="Skill Department of CS/IT"
    )
    req = create_request(sess, student_user)
    assert req.status == ClearanceStatus.SUBMITTED

    # HoD of CS/IT (correct) and HoD of Automotive (unauthorized)
    hod_cs = sess.execute(select(User).where(User.email == "hod.csit@example.edu")).scalar_one()
    hod_auto = sess.execute(select(User).where(User.email == "hod.auto@example.edu")).scalar_one()

    # 1. On SUBMITTED request:
    # Unauthorized HoD gets 404 (never learns the request is in SUBMITTED status)
    with pytest.raises(WorkflowNotFoundError, match="does not belong to your academic department"):
        hod_decide(sess, hod_auto, req.id, ApprovalStatus.APPROVED, None)

    # Authorized HoD on SUBMITTED request gets 409 with generic message
    with pytest.raises(WorkflowConflictError, match="Request is not awaiting HoD review"):
        hod_decide(sess, hod_cs, req.id, ApprovalStatus.APPROVED, None)

    # 2. Advance request to HOD_REVIEW
    for a in req.approvals:
        off = sess.execute(
            select(User).where(User.department_id == a.department_id, User.role == UserRole.dept_officer)
        ).scalars().first()
        if not off:
            off = User(
                email=f"off_sec_{a.department_id}@example.edu",
                password_hash=hash_password("pw"),
                role=UserRole.dept_officer,
                department_id=a.department_id,
                is_active=True,
            )
            sess.add(off)
            sess.commit()
        decide_approval(sess, off, a.id, ApprovalStatus.APPROVED, "OK")

    sess.refresh(req)
    assert req.status == ClearanceStatus.HOD_REVIEW

    # On HOD_REVIEW request:
    # Unauthorized HoD STILL gets 404
    with pytest.raises(WorkflowNotFoundError, match="does not belong to your academic department"):
        hod_decide(sess, hod_auto, req.id, ApprovalStatus.APPROVED, None)

    # Authorized HoD succeeds and clears the request
    cleared = hod_decide(sess, hod_cs, req.id, ApprovalStatus.APPROVED, "Approved final")
    assert cleared.status == ClearanceStatus.CLEARED
    sess.close()


# ---------------------------------------------------------------------------
# TEST: Previous rejection remarks exposed in API & preserved in audit log
# ---------------------------------------------------------------------------
def test_previous_rejection_reason_exposed_to_student(client: TestClient, db_session: Session):
    """
    Verifies that when a department rejects and student resubmits:
    - Department approval status becomes PENDING.
    - remarks is cleared to None (avoiding confusion).
    - previous_remarks holds the old rejection reason.
    - AuditLog preserves both old_remarks and previous_remarks.
    """
    db = db_session
    student_user = _setup_student_with_bank(db, "REMARK_001", "remark_001@example.edu")
    student_headers = make_auth_headers(student_user.id)

    # Apply
    apply_res = client.post("/student/requests", headers=student_headers)
    assert apply_res.status_code == 201
    req_id = apply_res.json()["id"]

    # Retrieve library approval
    req_obj = db.get(ClearanceRequest, req_id)
    lib_dept = db.execute(select(Department).where(Department.name == "Library")).scalar_one()
    lib_app = next(a for a in req_obj.approvals if a.department_id == lib_dept.id)

    # Department officer rejects Library approval
    lib_officer = db.execute(
        select(User).where(User.department_id == lib_dept.id, User.role == UserRole.dept_officer)
    ).scalar_one()
    officer_headers = make_auth_headers(lib_officer.id)

    rejection_reason = "Library book damaged: Rs. 250 fine due."
    rej_res = client.post(
        f"/department/approvals/{lib_app.id}/decision",
        json={"decision": "REJECTED", "remarks": rejection_reason},
        headers=officer_headers,
    )
    assert rej_res.status_code == 200

    # Student views current status before resubmission
    cur_res1 = client.get("/student/requests/current", headers=student_headers)
    assert cur_res1.status_code == 200
    app_data1 = next(a for a in cur_res1.json()["approvals"] if a["id"] == lib_app.id)
    assert app_data1["status"] == "REJECTED"
    assert app_data1["remarks"] == rejection_reason
    assert app_data1["previous_remarks"] is None

    # Student resubmits only to Library department
    resubmit_res = client.post(
        f"/student/requests/{req_id}/departments/{lib_dept.id}/resubmit",
        headers=student_headers,
    )
    assert resubmit_res.status_code == 200
    resub_data = resubmit_res.json()
    assert resub_data["status"] == "PENDING"
    assert resub_data["remarks"] is None  # Current remarks cleared!
    assert resub_data["previous_remarks"] == rejection_reason  # Preserved as previous rejection reason!
    assert resub_data["resubmission_count"] == 1

    # Student views current status after resubmission
    cur_res2 = client.get("/student/requests/current", headers=student_headers)
    assert cur_res2.status_code == 200
    app_data2 = next(a for a in cur_res2.json()["approvals"] if a["id"] == lib_app.id)
    assert app_data2["status"] == "PENDING"
    assert app_data2["remarks"] is None
    assert app_data2["previous_remarks"] == rejection_reason

    # Verify AuditLog has recorded previous remarks
    audit_entry = db.execute(
        select(AuditLog).where(
            AuditLog.entity_id == lib_app.id,
            AuditLog.action == "DEPARTMENT_RESUBMITTED",
        )
    ).scalar_one()
    assert audit_entry.details["previous_remarks"] == rejection_reason
    assert audit_entry.details["old_remarks"] == rejection_reason
