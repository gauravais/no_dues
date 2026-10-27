"""
Workflow Service: Encapsulates all approval and clearance business logic.
Contains NO FastAPI or Starlette imports so it can be tested in isolation.
"""
import uuid
from datetime import datetime, timezone
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.app.models.university import (
    Department,
    Programme,
    DepartmentApplicability,
)
from backend.app.models.roster import StudentRoster, RosterAssignedDepartment
from backend.app.models.user import User
from backend.app.models.clearance import (
    ClearanceRequest,
    DepartmentApproval,
    ClearanceStatus,
    ApprovalStatus,
)
from backend.app.models.certificate import Certificate
from backend.app.models.refund import Refund, RefundStatus
from backend.app.models.audit import AuditLog
from backend.app.services.exceptions import (
    WorkflowNotFoundError,
    WorkflowConflictError,
    WorkflowBadRequestError,
)


def get_applicable_departments(session: Session, roster: StudentRoster) -> list[Department]:
    """
    Computes all applicable departments for a student:
    - ALWAYS: all departments with applicability ALWAYS
    - HOSTELLER_ONLY: if student roster is_hosteller == True
    - ASSIGNED_ONLY: only departments mapped in roster_assigned_departments for this student
    - OWN_ACADEMIC: student's own academic department (via programme -> academic_department_id)
    """
    # 1. ALWAYS departments
    always_depts = session.execute(
        select(Department).where(Department.applicability == DepartmentApplicability.ALWAYS)
    ).scalars().all()

    # 2. HOSTELLER_ONLY departments
    hostel_depts: Sequence[Department] = []
    if roster.is_hosteller:
        hostel_depts = session.execute(
            select(Department).where(Department.applicability == DepartmentApplicability.HOSTELLER_ONLY)
        ).scalars().all()

    # 3. ASSIGNED_ONLY departments
    assigned_depts = session.execute(
        select(Department)
        .join(RosterAssignedDepartment, RosterAssignedDepartment.department_id == Department.id)
        .where(
            RosterAssignedDepartment.roster_id == roster.id,
            Department.applicability == DepartmentApplicability.ASSIGNED_ONLY,
        )
    ).scalars().all()

    # 4. Student's OWN_ACADEMIC department
    # Load programme if not already populated
    prog = roster.programme
    if not prog:
        from backend.app.models.university import Programme
        prog = session.get(Programme, roster.programme_id)
    
    academic_dept = session.get(Department, prog.academic_department_id)
    if not academic_dept:
        raise WorkflowNotFoundError(f"Academic department {prog.academic_department_id} not found.")

    # Combine unique departments by ID
    dept_map: dict[int, Department] = {}
    for d in list(always_depts) + list(hostel_depts) + list(assigned_depts) + [academic_dept]:
        dept_map[d.id] = d

    return sorted(list(dept_map.values()), key=lambda x: x.id)


def recompute_request_status(request: ClearanceRequest) -> ClearanceStatus:
    """
    Recomputes clearance request status strictly in this order:
    1. if status is CLEARED or REFUND_VERIFIED: no change
    2. any approval REJECTED -> ACTION_NEEDED
    3. elif request.hod_remarks is not null (an unresolved HoD rejection) -> stay ACTION_NEEDED
    4. elif all approvals APPROVED -> HOD_REVIEW
    5. else -> SUBMITTED
    """
    if request.status in (ClearanceStatus.CLEARED, ClearanceStatus.REFUND_VERIFIED):
        return request.status

    approvals = request.approvals

    # 2. Any approval REJECTED -> ACTION_NEEDED
    if any(a.status == ApprovalStatus.REJECTED for a in approvals):
        return ClearanceStatus.ACTION_NEEDED

    # 3. Elif unresolved HoD rejection -> ACTION_NEEDED
    if request.hod_remarks is not None:
        return ClearanceStatus.ACTION_NEEDED

    # 4. Elif all approvals APPROVED -> HOD_REVIEW
    if approvals and all(a.status == ApprovalStatus.APPROVED for a in approvals):
        return ClearanceStatus.HOD_REVIEW

    # 5. Else -> SUBMITTED
    return ClearanceStatus.SUBMITTED


def _record_audit(
    session: Session,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    details: dict | None,
) -> None:
    """Helper to record an immutable audit_log record."""
    audit = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        created_at=datetime.now(timezone.utc),
    )
    session.add(audit)


def create_request(session: Session, student_user: User) -> ClearanceRequest:
    """
    Creates a clearance request for the student.
    Refuses if student already has a request whose status is not REFUND_VERIFIED (409 Conflict).
    Creates:
    - 1 clearance_requests (SUBMITTED)
    - 1 department_approvals per applicable department (PENDING)
    - 1 refunds row (PENDING_VERIFICATION, deposit from roster, deductions 0, final = deposit)
    """
    if not student_user.roster_id:
        raise WorkflowBadRequestError("Student user has no linked roster profile.")

    # 1. Lock the student's roster row (FOR UPDATE) to serialize request creation per student
    roster = session.execute(
        select(StudentRoster)
        .where(StudentRoster.id == student_user.roster_id)
        .with_for_update()
    ).scalar_one_or_none()

    if not roster:
        raise WorkflowNotFoundError("Student roster entry not found.")

    if not roster.bank_detail:
        raise WorkflowBadRequestError("Bank details must be provided before applying for clearance.")

    # Check existing active requests
    existing_active = session.execute(
        select(ClearanceRequest).where(
            ClearanceRequest.roster_id == roster.id,
            ClearanceRequest.status != ClearanceStatus.REFUND_VERIFIED,
        )
    ).scalars().first()

    if existing_active:
        raise WorkflowConflictError("Student already has an active clearance request.")

    applicable_depts = get_applicable_departments(session, roster)
    now = datetime.now(timezone.utc)

    request = ClearanceRequest(
        roster_id=roster.id,
        status=ClearanceStatus.SUBMITTED,
        submitted_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(request)
    session.flush()

    # Create approvals
    for dept in applicable_depts:
        approval = DepartmentApproval(
            request_id=request.id,
            department_id=dept.id,
            status=ApprovalStatus.PENDING,
            resubmission_count=0,
            created_at=now,
            updated_at=now,
        )
        session.add(approval)

    # Create refund record
    deposit = roster.security_deposit_amount or 0
    refund = Refund(
        request_id=request.id,
        deposit_amount=deposit,
        deductions=0,
        final_amount=deposit,
        status=RefundStatus.PENDING_VERIFICATION,
        updated_at=now,
    )
    session.add(refund)

    _record_audit(
        session=session,
        user_id=student_user.id,
        action="REQUEST_CREATED",
        entity_type="ClearanceRequest",
        entity_id=request.id,
        details={
            "initial_status": request.status.value,
            "department_count": len(applicable_depts),
            "deposit_amount": str(deposit),
        },
    )

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise WorkflowConflictError("Student already has an active clearance request.")

    session.refresh(request)
    return request


def decide_approval(
    session: Session,
    officer_user: User,
    approval_id: int,
    decision: ApprovalStatus,
    remarks: str | None,
) -> DepartmentApproval:
    """
    Officer decides a pending department approval.
    - Prevents stale-read race conditions by:
        1. Finding the approval's request_id.
        2. Locking the clearance_requests row with SELECT ... FOR UPDATE.
        3. Reloading the approval with populate_existing=True.
        4. Validating ownership (404), PENDING status (409), and rejection remarks (400).
    - Recomputes request status and records audit log.
    """
    # 1. Find the approval's request_id
    req_id = session.execute(
        select(DepartmentApproval.request_id).where(DepartmentApproval.id == approval_id)
    ).scalar_one_or_none()

    if not req_id:
        raise WorkflowNotFoundError(f"Department approval {approval_id} not found.")

    # 2. Lock that clearance_requests row with SELECT ... FOR UPDATE
    req = session.execute(
        select(ClearanceRequest)
        .where(ClearanceRequest.id == req_id)
        .with_for_update()
    ).scalar_one_or_none()

    if not req:
        raise WorkflowNotFoundError(f"Clearance request {req_id} not found.")

    # 3. RELOAD the approval with populate_existing=True
    approval = session.execute(
        select(DepartmentApproval)
        .where(DepartmentApproval.id == approval_id)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()

    if not approval:
        raise WorkflowNotFoundError(f"Department approval {approval_id} not found.")

    # 4. Check ownership (404)
    if approval.department_id != officer_user.department_id:
        raise WorkflowNotFoundError("Approval does not belong to your assigned department.")

    # 5. Check PENDING status (409)
    if approval.status != ApprovalStatus.PENDING:
        raise WorkflowConflictError("Approval is not pending decision.")

    # 6. Validate remarks on rejection (400)
    cleaned_remarks = remarks.strip() if remarks else ""
    if decision == ApprovalStatus.REJECTED and not cleaned_remarks:
        raise WorkflowBadRequestError("Remarks are mandatory when rejecting an approval.")

    old_request_status = req.status.value
    now = datetime.now(timezone.utc)

    # 7. Update approval
    approval.status = decision
    approval.remarks = cleaned_remarks if decision == ApprovalStatus.REJECTED else (remarks.strip() if remarks else None)
    approval.decided_by = officer_user.id
    approval.decided_at = now
    approval.updated_at = now

    # 8. Recompute request status
    session.flush()
    session.refresh(req)
    req.status = recompute_request_status(req)
    req.updated_at = now

    _record_audit(
        session=session,
        user_id=officer_user.id,
        action="APPROVAL_DECIDED",
        entity_type="DepartmentApproval",
        entity_id=approval.id,
        details={
            "decision": decision.value,
            "remarks": approval.remarks,
            "old_request_status": old_request_status,
            "new_request_status": req.status.value,
        },
    )

    session.commit()
    session.refresh(approval)
    return approval


def resubmit_department(
    session: Session,
    student_user: User,
    request_id: int,
    department_id: int,
) -> DepartmentApproval:
    """
    Student resubmits only to a specific rejected department.
    - Request must belong to student (otherwise 404).
    - Approval must be REJECTED (otherwise 409).
    - Sets approval to PENDING, preserves old remarks in previous_remarks, clears remarks,
      increments resubmission_count, clears decided_by/decided_at.
    - Keeps old remarks in audit log.
    - Recomputes request status.
    """
    req = session.execute(
        select(ClearanceRequest)
        .where(ClearanceRequest.id == request_id)
        .with_for_update()
    ).scalar_one_or_none()

    if not req or req.roster_id != student_user.roster_id:
        raise WorkflowNotFoundError("Clearance request not found.")

    approval = session.execute(
        select(DepartmentApproval).where(
            DepartmentApproval.request_id == request_id,
            DepartmentApproval.department_id == department_id,
        )
    ).scalar_one_or_none()

    if not approval:
        raise WorkflowNotFoundError("Department approval not found for this request.")

    if approval.status != ApprovalStatus.REJECTED:
        raise WorkflowConflictError("Only rejected department approvals can be resubmitted.")

    now = datetime.now(timezone.utc)
    old_remarks = approval.remarks
    old_req_status = req.status.value

    # Reset approval: preserve previous rejection reason, clear current decision remarks
    approval.status = ApprovalStatus.PENDING
    approval.previous_remarks = old_remarks
    approval.remarks = None
    approval.resubmission_count += 1
    approval.decided_by = None
    approval.decided_at = None
    approval.updated_at = now

    # Recompute request status
    session.flush()
    session.refresh(req)
    req.status = recompute_request_status(req)
    req.updated_at = now

    _record_audit(
        session=session,
        user_id=student_user.id,
        action="DEPARTMENT_RESUBMITTED",
        entity_type="DepartmentApproval",
        entity_id=approval.id,
        details={
            "department_id": department_id,
            "old_remarks": old_remarks,
            "previous_remarks": old_remarks,
            "resubmission_count": approval.resubmission_count,
            "old_request_status": old_req_status,
            "new_request_status": req.status.value,
        },
    )

    session.commit()
    session.refresh(approval)
    return approval


def hod_decide(
    session: Session,
    hod_user: User,
    request_id: int,
    decision: ApprovalStatus,
    remarks: str | None,
) -> ClearanceRequest:
    """
    HoD final decision on a request.
    - Check request belongs to HoD's academic department (404) BEFORE checking status (409).
    - Status check raises generic "Request is not awaiting HoD review." (409).
    - APPROVED:
        * status = CLEARED
        * set hod_user_id and hod_decided_at
        * create exactly one Certificate (code = UUID)
        * clear hod_remarks
    - REJECTED:
        * remarks mandatory (otherwise 400)
        * status = ACTION_NEEDED
        * set hod_remarks, hod_user_id, hod_decided_at
    """
    req = session.execute(
        select(ClearanceRequest)
        .where(ClearanceRequest.id == request_id)
        .with_for_update()
    ).scalar_one_or_none()

    if not req:
        raise WorkflowNotFoundError("Clearance request not found.")

    # 1. Check student academic department FIRST (404)
    roster = session.get(StudentRoster, req.roster_id)
    if not roster or not roster.programme_id:
        raise WorkflowNotFoundError("Student roster entry not found.")

    prog = session.get(Programme, roster.programme_id)
    if not prog or prog.academic_department_id != hod_user.department_id:
        raise WorkflowNotFoundError("Clearance request does not belong to your academic department.")

    # 2. Check status with generic message (409)
    if req.status != ClearanceStatus.HOD_REVIEW:
        raise WorkflowConflictError("Request is not awaiting HoD review.")

    cleaned_remarks = remarks.strip() if remarks else ""
    now = datetime.now(timezone.utc)

    if decision == ApprovalStatus.APPROVED:
        req.status = ClearanceStatus.CLEARED
        req.hod_user_id = hod_user.id
        req.hod_decided_at = now
        req.hod_remarks = None
        req.updated_at = now

        # Create Certificate
        cert = Certificate(
            request_id=req.id,
            certificate_code=str(uuid.uuid4()),
            issued_at=now,
            hod_user_id=hod_user.id,
        )
        session.add(cert)

        _record_audit(
            session=session,
            user_id=hod_user.id,
            action="HOD_APPROVED",
            entity_type="ClearanceRequest",
            entity_id=req.id,
            details={
                "status": ClearanceStatus.CLEARED.value,
                "certificate_code": cert.certificate_code,
            },
        )
    elif decision == ApprovalStatus.REJECTED:
        if not cleaned_remarks:
            raise WorkflowBadRequestError("Remarks are mandatory when rejecting a clearance request.")

        req.status = ClearanceStatus.ACTION_NEEDED
        req.hod_remarks = cleaned_remarks
        req.hod_user_id = hod_user.id
        req.hod_decided_at = now
        req.updated_at = now

        _record_audit(
            session=session,
            user_id=hod_user.id,
            action="HOD_REJECTED",
            entity_type="ClearanceRequest",
            entity_id=req.id,
            details={
                "status": ClearanceStatus.ACTION_NEEDED.value,
                "hod_remarks": cleaned_remarks,
            },
        )
    else:
        raise WorkflowBadRequestError("Decision must be APPROVED or REJECTED.")

    session.commit()
    session.refresh(req)
    return req


def student_resubmit_to_hod(
    session: Session,
    student_user: User,
    request_id: int,
) -> ClearanceRequest:
    """
    Student resubmits to HoD after addressing HoD rejection remarks.
    - Only allowed when request status is ACTION_NEEDED.
    - No approval is REJECTED.
    - hod_remarks is NOT null.
    - Clears hod_remarks (copies it to audit log) and sets status = HOD_REVIEW.
    """
    req = session.execute(
        select(ClearanceRequest)
        .where(ClearanceRequest.id == request_id)
        .with_for_update()
    ).scalar_one_or_none()

    if not req or req.roster_id != student_user.roster_id:
        raise WorkflowNotFoundError("Clearance request not found.")

    if req.status != ClearanceStatus.ACTION_NEEDED:
        raise WorkflowConflictError("Request is not in ACTION_NEEDED status.")

    if req.hod_remarks is None:
        raise WorkflowConflictError("No pending HoD remarks to resubmit for.")

    # Verify no department approval is currently REJECTED
    if any(a.status == ApprovalStatus.REJECTED for a in req.approvals):
        raise WorkflowConflictError("Cannot resubmit to HoD while department approvals are still rejected.")

    now = datetime.now(timezone.utc)
    old_hod_remarks = req.hod_remarks
    req.hod_remarks = None
    req.status = ClearanceStatus.HOD_REVIEW
    req.updated_at = now

    _record_audit(
        session=session,
        user_id=student_user.id,
        action="RESUBMIT_TO_HOD",
        entity_type="ClearanceRequest",
        entity_id=req.id,
        details={
            "previous_hod_remarks": old_hod_remarks,
            "status": ClearanceStatus.HOD_REVIEW.value,
        },
    )

    session.commit()
    session.refresh(req)
    return req
