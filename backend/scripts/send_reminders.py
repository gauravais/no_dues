"""Daily reminder digest script.

Identifies clearance requests pending review or student action for longer than REMINDER_AFTER_DAYS,
and queues at most 1 digest email per recipient per 24 hours.
"""
import logging
import sys
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, or_

from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.models.email import EmailOutbox
from backend.app.models.user import User, UserRole, UserDepartment
from backend.app.models.clearance import (
    ClearanceRequest,
    DepartmentApproval,
    ClearanceStatus,
    ApprovalStatus,
)
from backend.app.models.university import Programme, Department
from backend.app.models.roster import StudentRoster
from backend.app.services.email import queue_email


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("send_reminders")


def was_reminder_sent_recently(session, to_email: str, kind: str) -> bool:
    """Checks whether a reminder of the specified kind was queued or sent to the email within the last 24 hours."""
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    existing = session.execute(
        select(EmailOutbox.id).where(
            func.lower(EmailOutbox.to_email) == to_email.strip().lower(),
            EmailOutbox.kind == kind,
            EmailOutbox.created_at >= since,
        )
    ).first()
    return existing is not None


def process_reminders(session=None) -> int:
    """Queues reminder digests for eligible officers, HoDs, and students. Returns total queued."""
    if not settings.REMINDERS_ENABLED:
        logger.info("Reminders are disabled (REMINDERS_ENABLED=False). Exiting.")
        return 0

    local_session = session or SessionLocal()
    queued_count = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.REMINDER_AFTER_DAYS)

    try:
        # Pre-fetch department names
        dept_name_map = {
            d.id: d.name
            for d in local_session.execute(select(Department)).scalars().all()
        }

        # 1. Department Officers: pending approvals older than cutoff, grouped per person
        dept_approvals = local_session.execute(
            select(
                DepartmentApproval.department_id,
                func.count(DepartmentApproval.id).label("pending_count"),
            )
            .join(ClearanceRequest, ClearanceRequest.id == DepartmentApproval.request_id)
            .where(
                DepartmentApproval.status == ApprovalStatus.PENDING,
                ClearanceRequest.status != ClearanceStatus.CANCELLED,
                DepartmentApproval.created_at <= cutoff,
            )
            .group_by(DepartmentApproval.department_id)
        ).all()

        officer_digests: dict[int, dict] = {}
        for dept_id, pending_count in dept_approvals:
            officers = local_session.execute(
                select(User)
                .outerjoin(UserDepartment, UserDepartment.user_id == User.id)
                .where(
                    User.role == UserRole.dept_officer,
                    User.is_active == True,
                    or_(
                        User.department_id == dept_id,
                        UserDepartment.department_id == dept_id,
                    ),
                )
                .distinct()
            ).scalars().all()

            dept_name = dept_name_map.get(dept_id, f"Department #{dept_id}")
            for officer in officers:
                if officer.id not in officer_digests:
                    officer_digests[officer.id] = {"user": officer, "offices": {}, "total": 0}
                officer_digests[officer.id]["offices"][dept_name] = pending_count
                officer_digests[officer.id]["total"] += pending_count

        for o_info in officer_digests.values():
            officer = o_info["user"]
            total_pending = o_info["total"]
            if not was_reminder_sent_recently(local_session, officer.email, "digest_reminder"):
                offices_lines = "\n".join(f"- {name}: {cnt} pending" for name, cnt in sorted(o_info["offices"].items()))
                queue_email(
                    session=local_session,
                    to_email=officer.email,
                    subject="SVSU No-Dues Clearance: Daily Pending Digest",
                    body=(
                        f"Dear Officer,\n\n"
                        f"You have {total_pending} clearance request(s) awaiting review across your assigned office(s) "
                        f"for more than {settings.REMINDER_AFTER_DAYS} day(s):\n\n"
                        f"{offices_lines}\n\n"
                        f"Please review the pending queue:\n"
                        f"{settings.FRONTEND_BASE_URL}/department/queue\n\n"
                        f"Regards,\nSVSU No-Dues Clearance Team"
                    ),
                    kind="digest_reminder",
                )
                queued_count += 1
                logger.info(f"Queued digest reminder for officer {officer.email} ({total_pending} pending across {len(o_info['offices'])} offices)")

        # 2. HoDs: requests in HOD_REVIEW older than cutoff, grouped per person
        hod_requests = local_session.execute(
            select(
                Programme.academic_department_id,
                func.count(ClearanceRequest.id).label("pending_count"),
            )
            .join(StudentRoster, StudentRoster.id == ClearanceRequest.roster_id)
            .join(Programme, Programme.id == StudentRoster.programme_id)
            .where(
                ClearanceRequest.status == ClearanceStatus.HOD_REVIEW,
                ClearanceRequest.updated_at <= cutoff,
            )
            .group_by(Programme.academic_department_id)
        ).all()

        hod_digests: dict[int, dict] = {}
        for acad_dept_id, pending_count in hod_requests:
            hods = local_session.execute(
                select(User)
                .outerjoin(UserDepartment, UserDepartment.user_id == User.id)
                .where(
                    User.role == UserRole.hod,
                    User.is_active == True,
                    or_(
                        User.department_id == acad_dept_id,
                        UserDepartment.department_id == acad_dept_id,
                    ),
                )
                .distinct()
            ).scalars().all()

            dept_name = dept_name_map.get(acad_dept_id, f"Department #{acad_dept_id}")
            for hod in hods:
                if hod.id not in hod_digests:
                    hod_digests[hod.id] = {"user": hod, "offices": {}, "total": 0}
                hod_digests[hod.id]["offices"][dept_name] = pending_count
                hod_digests[hod.id]["total"] += pending_count

        for h_info in hod_digests.values():
            hod = h_info["user"]
            total_pending = h_info["total"]
            if not was_reminder_sent_recently(local_session, hod.email, "digest_reminder"):
                offices_lines = "\n".join(f"- {name}: {cnt} pending" for name, cnt in sorted(h_info["offices"].items()))
                queue_email(
                    session=local_session,
                    to_email=hod.email,
                    subject="SVSU No-Dues Clearance: Daily Pending HoD Review Digest",
                    body=(
                        f"Dear Head of Department,\n\n"
                        f"You have {total_pending} clearance request(s) awaiting your final HoD review "
                        f"for more than {settings.REMINDER_AFTER_DAYS} day(s):\n\n"
                        f"{offices_lines}\n\n"
                        f"Please review the pending queue:\n"
                        f"{settings.FRONTEND_BASE_URL}/hod/queue\n\n"
                        f"Regards,\nSVSU No-Dues Clearance Team"
                    ),
                    kind="digest_reminder",
                )
                queued_count += 1
                logger.info(f"Queued digest reminder for HoD {hod.email} ({total_pending} pending across {len(h_info['offices'])} departments)")


        # 3. Students: requests in ACTION_NEEDED older than cutoff
        student_rejections = local_session.execute(
            select(ClearanceRequest)
            .where(
                ClearanceRequest.status == ClearanceStatus.ACTION_NEEDED,
                ClearanceRequest.updated_at <= cutoff,
            )
        ).scalars().all()

        for req in student_rejections:
            student_email = req.roster_entry.email if req.roster_entry else None
            if student_email and not was_reminder_sent_recently(local_session, student_email, "rejection_reminder"):
                queue_email(
                    session=local_session,
                    to_email=student_email,
                    subject="SVSU No-Dues Clearance: Action Required on Your Request",
                    body=(
                        f"Dear Student,\n\n"
                        f"Your clearance request requires your attention and has had rejections pending "
                        f"for more than {settings.REMINDER_AFTER_DAYS} day(s).\n\n"
                        f"Please review the rejection remarks and resubmit your request:\n"
                        f"{settings.FRONTEND_BASE_URL}/student\n\n"
                        f"Regards,\nSVSU No-Dues Clearance Team"
                    ),
                    kind="rejection_reminder",
                    related_request_id=req.id,
                )
                queued_count += 1
                logger.info(f"Queued rejection reminder for student {student_email}")

        local_session.commit()
    finally:
        if session is None:
            local_session.close()

    return queued_count


def main():
    logger.info("Starting reminder check sweep...")
    count = process_reminders()
    logger.info(f"Reminder sweep completed. Total new reminders queued: {count}")
    sys.exit(0)


if __name__ == "__main__":
    main()
