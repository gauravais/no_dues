"""
Workflow Service: Encapsulates all approval and clearance business logic.
Contains NO FastAPI or Starlette imports so it can be tested in isolation.
"""
import uuid
from datetime import datetime, timezone
from typing import Sequence
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.app.models.university import (
    Department,
    DepartmentKind,
    Programme,
    DepartmentApplicability,
)
from backend.app.models.roster import StudentRoster, RosterAssignedDepartment
from backend.app.models.lab_course import LabCourse
from backend.app.models.user import User, UserRole, UserDepartment
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
    WorkflowForbiddenError,
)
from backend.app.services.email import (
    notify_officers_new_request,
    notify_student_rejection,
    notify_hod_all_approved,
    notify_student_hod_rejected,
    notify_hod_approved,
    notify_department_added,
    notify_request_cancelled,
)


def user_department_ids(user: User, session: Session | None = None) -> set[int]:
    """
    Returns the set of department IDs that the user belongs to.
    Computes the union of user_departments (via user.department_memberships or DB query)
    and users.department_id fallback.
    """
    dept_ids: set[int] = set()
    if user.department_id is not None:
        dept_ids.add(user.department_id)

    # Check loaded relationship if available
    try:
        memberships = getattr(user, "department_memberships", None)
        if memberships:
            for m in memberships:
                dept_ids.add(m.department_id)
    except Exception:
        pass

    if session is not None and user.id is not None:
        rows = session.execute(
            select(UserDepartment.department_id).where(UserDepartment.user_id == user.id)
        ).scalars().all()
        for did in rows:
            dept_ids.add(did)

    return dept_ids


def active_officers_for(session: Session, department_id: int) -> list[User]:
    """
    Returns list of active users with role dept_officer who have membership in this department
    (via user_departments or fallback users.department_id).
    """
    stmt = (
        select(User)
        .outerjoin(UserDepartment, UserDepartment.user_id == User.id)
        .where(
            User.role == UserRole.dept_officer,
            User.is_active == True,
            or_(
                User.department_id == department_id,
                UserDepartment.department_id == department_id,
            ),
        )
        .distinct()
    )
    return list(session.execute(stmt).scalars().all())


def active_hod_for(session: Session, academic_department_id: int) -> User | None:
    """
    Returns active user with role hod who has membership in this academic department
    (via user_departments or fallback users.department_id).
    """
    stmt = (
        select(User)
        .outerjoin(UserDepartment, UserDepartment.user_id == User.id)
        .where(
            User.role == UserRole.hod,
            User.is_active == True,
            or_(
                User.department_id == academic_department_id,
                UserDepartment.department_id == academic_department_id,
            ),
        )
        .distinct()
    )
    return session.execute(stmt).scalars().first()


def user_academic_department_ids(user: User, session: Session) -> set[int]:
    """
    Returns the subset of department IDs the user belongs to that have kind == DepartmentKind.academic.
    """
    all_dept_ids = user_department_ids(user, session)
    if not all_dept_ids:
        return set()
    academic_ids = session.execute(
        select(Department.id).where(
            Department.id.in_(all_dept_ids),
            Department.kind == DepartmentKind.academic,
        )
    ).scalars().all()
    return set(academic_ids)


def get_user_departments(user: User, session: Session) -> list[Department]:
    """
    Returns the Department models corresponding to all department memberships for the user.
    """
    dept_ids = user_department_ids(user, session)
    if not dept_ids:
        return []
    return list(
        session.execute(
            select(Department).where(Department.id.in_(dept_ids)).order_by(Department.name.asc())
        ).scalars().all()
    )



def get_applicable_departments(
    session: Session,
    roster: StudentRoster,
    declared_is_hosteller: bool = False,
    declared_lab_courses: Sequence[LabCourse] | None = None,
    other_departments: Sequence[Department] | None = None,
) -> list[Department]:
    """
    Computes all applicable departments for a student from declarations:
    - ALWAYS: all departments with applicability ALWAYS
    - HOSTELLER_ONLY: if student's DECLARATION declared_is_hosteller == True
    - Assigned lab departments from declared_lab_courses (LabCourse.lab_department_id)
    - Optional other ASSIGNED_ONLY offices declared by student
    - Optional admin override: only departments mapped in roster_assigned_departments for this student
    - OWN_ACADEMIC: student's own academic department (via programme -> academic_department_id)
    """
    # 1. ALWAYS departments
    always_depts = session.execute(
        select(Department).where(Department.applicability == DepartmentApplicability.ALWAYS)
    ).scalars().all()

    # 2. HOSTELLER_ONLY departments (computed from declaration with roster fallback)
    hostel_depts: Sequence[Department] = []
    effective_is_hosteller = declared_is_hosteller if declared_is_hosteller is not None else roster.is_hosteller
    if effective_is_hosteller:
        hostel_depts = session.execute(
            select(Department).where(Department.applicability == DepartmentApplicability.HOSTELLER_ONLY)
        ).scalars().all()

    # 3. Lab departments from declared subjects
    lab_dept_ids = set()
    if declared_lab_courses:
        for lc in declared_lab_courses:
            lab_dept_ids.add(lc.lab_department_id)

    # Optional admin override mappings
    assigned_records = session.execute(
        select(RosterAssignedDepartment.department_id).where(RosterAssignedDepartment.roster_id == roster.id)
    ).scalars().all()
    for did in assigned_records:
        lab_dept_ids.add(did)

    assigned_depts: Sequence[Department] = []
    if lab_dept_ids:
        assigned_depts = session.execute(
            select(Department).where(Department.id.in_(lab_dept_ids))
        ).scalars().all()

    # 4. Student's OWN_ACADEMIC department
    prog = roster.programme
    if not prog:
        prog = session.get(Programme, roster.programme_id)
    
    academic_dept = session.get(Department, prog.academic_department_id)
    if not academic_dept:
        raise WorkflowNotFoundError(f"Academic department {prog.academic_department_id} not found.")

    # Combine unique departments by ID
    dept_map: dict[int, Department] = {}
    for d in list(always_depts) + list(hostel_depts) + list(assigned_depts) + list(other_departments or []) + [academic_dept]:
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


def create_request(
    session: Session,
    student_user: User,
    declared_is_hosteller: bool | None = None,
    declared_lab_course_ids: list[int] | None = None,
    other_department_ids: list[int] | None = None,
    others_note: str | None = None,
) -> ClearanceRequest:
    """
    Creates a clearance request for the student from their declarations.
    Refuses if student already has a request whose status is not REFUND_VERIFIED (409 Conflict).
    Creates:
    - 1 clearance_requests (SUBMITTED) with declared_is_hosteller, others_note, declared_lab_courses
    - 1 department_approvals per applicable department (PENDING)
    - 1 refunds row (PENDING_VERIFICATION)
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
            ClearanceRequest.status.not_in([ClearanceStatus.REFUND_VERIFIED, ClearanceStatus.CANCELLED]),
        )
    ).scalars().first()

    if existing_active:
        raise WorkflowConflictError("Student already has an active clearance request.")

    # Validate active HoD for academic department
    prog = roster.programme
    if not prog:
        prog = session.get(Programme, roster.programme_id)
    if not prog:
        raise WorkflowNotFoundError(f"Programme {roster.programme_id} not found.")

    academic_dept = session.get(Department, prog.academic_department_id)
    if not academic_dept:
        raise WorkflowNotFoundError(f"Academic department {prog.academic_department_id} not found.")

    active_hod = active_hod_for(session, academic_dept.id)
    if not active_hod:
        raise WorkflowConflictError(
            f"Academic department '{academic_dept.name}' has no active Head of Department (HoD). Cannot submit clearance request."
        )

    declared_courses = []
    if declared_lab_course_ids:
        declared_courses = session.execute(
            select(LabCourse).where(
                LabCourse.id.in_(declared_lab_course_ids),
                LabCourse.is_active == True,
            )
        ).scalars().all()

    # Validate other ASSIGNED_ONLY offices
    other_depts = []
    if other_department_ids:
        for did in other_department_ids:
            d = session.get(Department, did)
            if not d:
                raise WorkflowNotFoundError(f"Department ID {did} not found.")

            # 1. only ASSIGNED_ONLY offices
            if d.applicability != DepartmentApplicability.ASSIGNED_ONLY:
                raise WorkflowBadRequestError(
                    f"Department '{d.name}' cannot be declared as an other office. Only ASSIGNED_ONLY departments are allowed."
                )

            # 2. not linked to a lab subject
            linked_course = session.execute(
                select(LabCourse.id).where(LabCourse.lab_department_id == d.id)
            ).first()
            if linked_course:
                raise WorkflowBadRequestError(
                    f"Department '{d.name}' is linked to a lab subject and must be declared through lab subjects, not as an other office."
                )

            # 3. each with an active officer
            active_officers = active_officers_for(session, d.id)
            if not active_officers:
                raise WorkflowConflictError(
                    f"Department '{d.name}' has no active dealing officer. Cannot submit clearance request."
                )

            other_depts.append(d)

    applicable_depts = get_applicable_departments(
        session,
        roster,
        declared_is_hosteller=declared_is_hosteller,
        declared_lab_courses=declared_courses,
        other_departments=other_depts,
    )

    # Validate that every applicable department has at least one active officer
    for dept in applicable_depts:
        active_officers = active_officers_for(session, dept.id)
        if not active_officers:
            raise WorkflowConflictError(
                f"Department '{dept.name}' has no active dealing officer. Cannot submit clearance request."
            )


    now = datetime.now(timezone.utc)
    effective_is_hosteller = declared_is_hosteller if declared_is_hosteller is not None else roster.is_hosteller

    request = ClearanceRequest(
        roster_id=roster.id,
        status=ClearanceStatus.SUBMITTED,
        declared_is_hosteller=effective_is_hosteller,
        others_note=others_note.strip() if others_note else None,
        submitted_at=now,
        created_at=now,
        updated_at=now,
    )
    request.declared_lab_courses.extend(declared_courses)
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

    # Create refund record (provisional deposit; verified by registrar from university records)
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
            "declared_is_hosteller": declared_is_hosteller,
            "declared_subjects_count": len(declared_courses),
            "others_note": request.others_note,
        },
    )

    session.flush()
    notify_officers_new_request(session, request)

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
    if approval.department_id not in user_department_ids(officer_user, session):
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

    if decision == ApprovalStatus.REJECTED:
        notify_student_rejection(session, req, approval.department.name, approval.remarks or "")
    elif req.status == ClearanceStatus.HOD_REVIEW and old_request_status != ClearanceStatus.HOD_REVIEW.value:
        notify_hod_all_approved(session, req)

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
    if not prog or prog.academic_department_id not in user_academic_department_ids(hod_user, session):
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
        notify_hod_approved(session, req)
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
        notify_student_hod_rejected(session, req, cleaned_remarks)
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


def add_department_to_request(
    session: Session,
    request_id: int,
    department_id: int,
    acting_user: User,
) -> DepartmentApproval:
    """
    Adds an ASSIGNED_ONLY or applicable department to an active clearance request.
    Verifies:
    1. Request exists and belongs to the student (or acting user has permission).
    2. Request is active (not CLEARED or REFUND_VERIFIED).
    3. Target department exists.
    4. Target department is not already in the clearance request (409 Conflict).
    5. Target department has at least one active dealing officer (409 Conflict).
    Creates:
    - DepartmentApproval (PENDING)
    - RosterAssignedDepartment if not present
    Recomputes request status and records audit log.
    """
    req = session.execute(
        select(ClearanceRequest)
        .where(ClearanceRequest.id == request_id)
        .with_for_update()
    ).scalar_one_or_none()

    if not req:
        raise WorkflowNotFoundError(f"Clearance request {request_id} not found.")

    # If student, verify request ownership
    if acting_user.role == UserRole.student and req.roster_id != acting_user.roster_id:
        raise WorkflowNotFoundError("Clearance request not found.")

    if req.status in (ClearanceStatus.CLEARED, ClearanceStatus.REFUND_VERIFIED):
        raise WorkflowConflictError("Cannot add department to a finalized clearance request.")

    dept = session.get(Department, department_id)
    if not dept:
        raise WorkflowNotFoundError(f"Department {department_id} not found.")

    # Check if department is already part of the request
    existing_approval = session.execute(
        select(DepartmentApproval).where(
            DepartmentApproval.request_id == req.id,
            DepartmentApproval.department_id == dept.id,
        )
    ).scalar_one_or_none()
    if existing_approval:
        raise WorkflowConflictError(f"Department '{dept.name}' is already part of this clearance request.")

    # Active officer check
    active_officers = active_officers_for(session, dept.id)
    if not active_officers:
        raise WorkflowConflictError(
            f"Department '{dept.name}' has no active dealing officer. Cannot add to clearance request."
        )


    now = datetime.now(timezone.utc)
    approval = DepartmentApproval(
        request_id=req.id,
        department_id=dept.id,
        status=ApprovalStatus.PENDING,
        resubmission_count=0,
        created_at=now,
        updated_at=now,
    )
    session.add(approval)

    # Ensure mapped in roster_assigned_departments
    assigned_exists = session.execute(
        select(RosterAssignedDepartment).where(
            RosterAssignedDepartment.roster_id == req.roster_id,
            RosterAssignedDepartment.department_id == dept.id,
        )
    ).scalar_one_or_none()
    if not assigned_exists:
        session.add(
            RosterAssignedDepartment(
                roster_id=req.roster_id,
                department_id=dept.id,
            )
        )

    session.flush()
    session.refresh(req)
    req.status = recompute_request_status(req)

    _record_audit(
        session=session,
        user_id=acting_user.id,
        action="DEPARTMENT_ADDED_TO_REQUEST",
        entity_type="DepartmentApproval",
        entity_id=approval.id,
        details={
            "request_id": req.id,
            "department_id": dept.id,
            "department_name": dept.name,
            "new_status": req.status.value,
        },
    )

    notify_department_added(session, req, dept, "Added by academic officer")

    session.commit()
    session.refresh(approval)
    return approval


def add_office_to_request(
    session: Session,
    request_id: int,
    department_id: int,
    acting_user: User,
    reason: str,
) -> DepartmentApproval:
    """
    Academic department officer or HoD adds an office to a clearance request.
    Validations:
    - reason must be non-empty (400 WorkflowBadRequestError)
    - request must exist and student must belong to acting_user's academic department (404 WorkflowNotFoundError)
    - request status must NOT be CLEARED or REFUND_VERIFIED (409 WorkflowConflictError)
    - target department must exist (404 WorkflowNotFoundError)
    - department must NOT already be part of the request approvals (409 WorkflowConflictError)
    - target department must have at least one active officer (409 WorkflowConflictError)
    Records:
    - DepartmentApproval with added_by_user_id and added_reason
    - Audit log
    - Recomputes request status (e.g. HOD_REVIEW -> SUBMITTED)
    """
    clean_reason = reason.strip() if reason else ""
    if not clean_reason:
        raise WorkflowBadRequestError("Reason is mandatory when adding an office to a clearance request.")

    req = session.execute(
        select(ClearanceRequest)
        .where(ClearanceRequest.id == request_id)
        .with_for_update()
    ).scalar_one_or_none()

    if not req:
        raise WorkflowNotFoundError(f"Clearance request {request_id} not found.")

    # Scoped strictly to acting user's academic department
    student_acad_dept_id = (
        req.roster_entry.programme.academic_department_id
        if (req.roster_entry and req.roster_entry.programme)
        else None
    )
    if student_acad_dept_id not in user_academic_department_ids(acting_user, session):
        raise WorkflowNotFoundError("Clearance request not found in your academic department.")


    if req.status in (ClearanceStatus.CLEARED, ClearanceStatus.REFUND_VERIFIED):
        raise WorkflowConflictError("Cannot add department to a finalized clearance request.")

    dept = session.get(Department, department_id)
    if not dept:
        raise WorkflowNotFoundError(f"Department {department_id} not found.")

    # Check duplicate
    existing_approval = session.execute(
        select(DepartmentApproval).where(
            DepartmentApproval.request_id == req.id,
            DepartmentApproval.department_id == dept.id,
        )
    ).scalar_one_or_none()
    if existing_approval:
        raise WorkflowConflictError(f"Department '{dept.name}' is already part of this clearance request.")

    # Active officer check
    active_officers = active_officers_for(session, dept.id)
    if not active_officers:
        raise WorkflowConflictError(
            f"Department '{dept.name}' has no active dealing officer. Cannot add to clearance request."
        )


    now = datetime.now(timezone.utc)
    approval = DepartmentApproval(
        request_id=req.id,
        department_id=dept.id,
        status=ApprovalStatus.PENDING,
        added_by_user_id=acting_user.id,
        added_reason=clean_reason,
        resubmission_count=0,
        created_at=now,
        updated_at=now,
    )
    session.add(approval)

    session.flush()
    session.refresh(req)
    req.status = recompute_request_status(req)

    _record_audit(
        session=session,
        user_id=acting_user.id,
        action="OFFICE_ADDED_BY_STAFF",
        entity_type="DepartmentApproval",
        entity_id=approval.id,
        details={
            "request_id": req.id,
            "department_id": dept.id,
            "department_name": dept.name,
            "reason": clean_reason,
            "new_status": req.status.value,
        },
    )

    notify_department_added(session, req, dept, clean_reason)

    session.commit()
    session.refresh(approval)
    return approval


def student_declare_lab_courses(
    session: Session,
    student_user: User,
    request_id: int,
    lab_course_ids: list[int],
) -> ClearanceRequest:
    """
    Student declares more lab subjects while the request is not CLEARED/REFUND_VERIFIED.
    Adds new subjects to declared_lab_courses; for any new lab department, adds a PENDING approval.
    Recomputes request status (HOD_REVIEW drops back to SUBMITTED).
    """
    req = session.execute(
        select(ClearanceRequest)
        .where(ClearanceRequest.id == request_id)
        .with_for_update()
    ).scalar_one_or_none()

    if not req or req.roster_id != student_user.roster_id:
        raise WorkflowNotFoundError("Clearance request not found.")

    if req.status in (ClearanceStatus.CLEARED, ClearanceStatus.REFUND_VERIFIED):
        raise WorkflowConflictError("Cannot declare subjects for a finalized clearance request.")

    if not lab_course_ids:
        return req

    courses = session.execute(
        select(LabCourse).where(LabCourse.id.in_(lab_course_ids), LabCourse.is_active == True)
    ).scalars().all()

    existing_course_ids = {c.id for c in req.declared_lab_courses}
    existing_dept_ids = {a.department_id for a in req.approvals}
    new_depts_added = []
    now = datetime.now(timezone.utc)

    for c in courses:
        if c.id not in existing_course_ids:
            req.declared_lab_courses.append(c)
            existing_course_ids.add(c.id)

        if c.lab_department_id not in existing_dept_ids:
            lab_dept = session.get(Department, c.lab_department_id)
            active_officers = active_officers_for(session, c.lab_department_id)
            if not active_officers:
                dept_name = lab_dept.name if lab_dept else f"#{c.lab_department_id}"
                raise WorkflowConflictError(
                    f"Department '{dept_name}' has no active dealing officer. Cannot add to clearance request."
                )


            approval = DepartmentApproval(
                request_id=req.id,
                department_id=c.lab_department_id,
                status=ApprovalStatus.PENDING,
                resubmission_count=0,
                created_at=now,
                updated_at=now,
            )
            session.add(approval)
            existing_dept_ids.add(c.lab_department_id)
            new_depts_added.append(c.lab_department_id)

    session.flush()
    session.refresh(req)
    req.status = recompute_request_status(req)

    _record_audit(
        session=session,
        user_id=student_user.id,
        action="STUDENT_DECLARED_LAB_COURSES",
        entity_type="ClearanceRequest",
        entity_id=req.id,
        details={
            "declared_lab_course_ids": lab_course_ids,
            "new_departments_added": new_depts_added,
            "new_status": req.status.value,
        },
    )

    session.commit()
    session.refresh(req)
    return req


def student_cancel_request(
    session: Session,
    request_id: int,
    student_user: User,
    reason: str | None = None,
) -> ClearanceRequest:
    """
    Student cancels their clearance request.
    Permitted ONLY when all departmental approvals are still in PENDING status.
    Forbidden if any approval was approved/rejected or request reached HOD_REVIEW / CLEARED.
    """
    req = session.execute(
        select(ClearanceRequest)
        .where(ClearanceRequest.id == request_id)
        .with_for_update()
    ).scalar_one_or_none()

    if not req:
        raise WorkflowNotFoundError(f"Clearance request {request_id} not found.")

    if req.roster_id != student_user.roster_id:
        raise WorkflowForbiddenError("You can only cancel your own clearance request.")

    if req.status in (ClearanceStatus.CLEARED, ClearanceStatus.REFUND_VERIFIED, ClearanceStatus.CANCELLED):
        raise WorkflowBadRequestError("Cannot cancel a completed, verified, or already cancelled request.")

    # Check that all approvals are still PENDING
    any_non_pending = any(a.status != ApprovalStatus.PENDING for a in req.approvals)
    if any_non_pending or req.status != ClearanceStatus.SUBMITTED:
        raise WorkflowBadRequestError("Student can cancel only when all approvals are still PENDING.")

    req.status = ClearanceStatus.CANCELLED
    now = datetime.now(timezone.utc)
    req.updated_at = now

    cancel_reason = reason.strip() if reason else "Cancelled by student"
    _record_audit(
        session=session,
        user_id=student_user.id,
        action="CANCELLED_BY_STUDENT",
        entity_type="ClearanceRequest",
        entity_id=req.id,
        details={"reason": cancel_reason},
    )

    notify_request_cancelled(session, req, cancel_reason)

    session.commit()
    session.refresh(req)
    return req


def staff_cancel_request(
    session: Session,
    request_id: int,
    staff_user: User,
    reason: str,
) -> ClearanceRequest:
    """
    Department officer or administrator cancels a clearance request.
    Rules:
    - Reason is mandatory (WorkflowBadRequestError)
    - Forbidden if status is CLEARED, REFUND_VERIFIED, or CANCELLED (WorkflowBadRequestError)
    - If acting user is dept_officer:
      Must belong to academic department matching student's enrolled programme (WorkflowForbiddenError)
    - If acting user is admin: allowed
    - Records audit entry and queues notification email to student.
    """
    clean_reason = reason.strip() if reason else ""
    if not clean_reason:
        raise WorkflowBadRequestError("Cancellation reason is mandatory.")

    req = session.execute(
        select(ClearanceRequest)
        .where(ClearanceRequest.id == request_id)
        .with_for_update()
    ).scalar_one_or_none()

    if not req:
        raise WorkflowNotFoundError(f"Clearance request {request_id} not found.")

    if req.status in (ClearanceStatus.CLEARED, ClearanceStatus.REFUND_VERIFIED, ClearanceStatus.CANCELLED):
        raise WorkflowBadRequestError("Cannot cancel a cleared, verified, or already cancelled request.")

    # Check role permissions
    if staff_user.role == UserRole.dept_officer:
        # Academic officer can cancel only own students
        student_acad_id = (
            req.roster_entry.programme.academic_department_id
            if (req.roster_entry and req.roster_entry.programme)
            else None
        )
        officer_acad_ids = user_academic_department_ids(staff_user, session)
        if not student_acad_id or student_acad_id not in officer_acad_ids:
            raise WorkflowForbiddenError("Academic officers can only cancel clearance requests of their own students.")

    elif staff_user.role != UserRole.admin:
        raise WorkflowForbiddenError("Only academic department officers or administrators can cancel clearance requests.")

    req.status = ClearanceStatus.CANCELLED
    now = datetime.now(timezone.utc)
    req.updated_at = now

    _record_audit(
        session=session,
        user_id=staff_user.id,
        action="CANCELLED_BY_STAFF",
        entity_type="ClearanceRequest",
        entity_id=req.id,
        details={"reason": clean_reason, "cancelled_by_role": staff_user.role.value},
    )

    notify_request_cancelled(session, req, clean_reason)

    session.commit()
    session.refresh(req)
    return req

