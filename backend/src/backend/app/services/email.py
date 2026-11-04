"""Email notification service using Outbox pattern for reliable, audited delivery."""
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal
import requests
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.models.email import EmailOutbox, OutboxStatus
from backend.app.models.user import User, UserRole
from backend.app.models.clearance import ClearanceRequest, DepartmentApproval
from backend.app.models.university import Department

logger = logging.getLogger("nodues.email")


def mask_reg_number(reg: str | None) -> str:
    """Mask student registration number for email notifications."""
    if not reg:
        return ""
    if len(reg) <= 4:
        return "****"
    return reg[:2] + "****" + reg[-2:]


def queue_email(
    session: Session,
    to_email: str,
    subject: str,
    body: str,
    kind: str,
    related_request_id: int | None = None,
) -> EmailOutbox:
    """Inserts an email into email_outbox within the caller's active database transaction."""
    email_clean = to_email.strip().lower()
    item = EmailOutbox(
        to_email=email_clean,
        subject=subject.strip(),
        body=body,
        kind=kind,
        related_request_id=related_request_id,
        status=OutboxStatus.PENDING,
        attempts=0,
        created_at=datetime.now(timezone.utc),
    )
    session.add(item)
    return item


# ---------------------------------------------------------------------------
# Provider Interface & Senders (Console, SMTP, Brevo, Resend, Disabled)
# ---------------------------------------------------------------------------

class BaseEmailSender(ABC):
    @abstractmethod
    def send(self, to_email: str, subject: str, body: str) -> None:
        """Send a single email message. Raises Exception on failure."""
        pass


class ConsoleEmailSender(BaseEmailSender):
    def send(self, to_email: str, subject: str, body: str) -> None:
        print(
            f"\n{'='*60}\n"
            f"[EMAIL CONSOLE]\n"
            f"To: {to_email}\n"
            f"Subject: {subject}\n\n"
            f"{body}\n"
            f"{'='*60}\n",
            flush=True,
        )


class SmtpEmailSender(BaseEmailSender):
    def send(self, to_email: str, subject: str, body: str) -> None:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.email_from_address
        msg["To"] = to_email
        msg.set_content(body)

        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
            if settings.SMTP_USE_TLS:
                server.starttls()

        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

        server.send_message(msg)
        server.quit()


class BrevoEmailSender(BaseEmailSender):
    """Sends transactional email via Brevo HTTPS REST API (https://api.brevo.com/v3/smtp/email)."""

    def send(self, to_email: str, subject: str, body: str) -> None:
        if not settings.BREVO_API_KEY:
            raise RuntimeError("BREVO_API_KEY is not configured")

        sender_email = settings.email_from_address
        payload = {
            "sender": {"email": sender_email},
            "to": [{"email": to_email}],
            "subject": subject,
            "textContent": body,
        }
        headers = {
            "api-key": settings.BREVO_API_KEY.strip(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload,
            headers=headers,
            timeout=10,
        )
        if response.status_code not in (200, 201, 202):
            raise RuntimeError(f"Brevo API error HTTP {response.status_code}: {response.text}")


class ResendEmailSender(BaseEmailSender):
    """Sends transactional email via Resend HTTPS REST API (https://api.resend.com/emails)."""

    def send(self, to_email: str, subject: str, body: str) -> None:
        if not settings.RESEND_API_KEY:
            raise RuntimeError("RESEND_API_KEY is not configured")

        sender_email = settings.email_from_address
        payload = {
            "from": sender_email,
            "to": [to_email],
            "subject": subject,
            "text": body,
        }
        headers = {
            "Authorization": f"Bearer {settings.RESEND_API_KEY.strip()}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            "https://api.resend.com/emails",
            json=payload,
            headers=headers,
            timeout=10,
        )
        if response.status_code not in (200, 201, 202):
            raise RuntimeError(f"Resend API error HTTP {response.status_code}: {response.text}")


class DisabledEmailSender(BaseEmailSender):
    def send(self, to_email: str, subject: str, body: str) -> None:
        raise RuntimeError("email disabled")


def get_email_sender() -> BaseEmailSender:
    """Factory returning the configured provider sender based on EMAIL_BACKEND."""
    backend = settings.email_backend
    if backend == "console":
        return ConsoleEmailSender()
    elif backend == "smtp":
        return SmtpEmailSender()
    elif backend == "brevo":
        return BrevoEmailSender()
    elif backend == "resend":
        return ResendEmailSender()
    return DisabledEmailSender()


def deliver_outbox_email(session: Session, item: EmailOutbox) -> bool:
    """
    Attempts delivery of a single outbox item according to application settings:
    - Checks EMAIL_ALLOWLIST: if not allowed, marks SKIPPED with explanatory note.
    - If EMAIL_BACKEND=disabled: marks SKIPPED with note 'email disabled'.
    - Otherwise: delegates to configured sender (console, smtp, brevo, resend).
    - On failure: increments attempts up to 5, marks FAILED if attempts >= 5.
    """
    to_email_lower = item.to_email.strip().lower()

    # 1. Check EMAIL_ALLOWLIST
    if settings.email_allowlist_set:
        if to_email_lower not in settings.email_allowlist_set:
            item.status = OutboxStatus.SKIPPED
            item.last_error = "Recipient not in EMAIL_ALLOWLIST"
            item.sent_at = datetime.now(timezone.utc)
            session.commit()
            return True

    # 2. Disabled backend mode (Render default)
    if settings.email_backend == "disabled":
        item.status = OutboxStatus.SKIPPED
        item.last_error = "email disabled"
        item.sent_at = datetime.now(timezone.utc)
        session.commit()
        return True

    # 3. Deliver via configured provider
    try:
        sender = get_email_sender()
        sender.send(to_email=item.to_email, subject=item.subject, body=item.body)
        item.status = OutboxStatus.SENT
        item.sent_at = datetime.now(timezone.utc)
        item.last_error = None
        session.commit()
        return True
    except Exception as exc:
        item.attempts += 1
        item.last_error = str(exc)
        if item.attempts >= 5:
            item.status = OutboxStatus.FAILED
        else:
            item.status = OutboxStatus.PENDING
        session.commit()
        logger.warning(
            f"Failed to deliver outbox email id={item.id} via backend={settings.email_backend} (attempt {item.attempts}/5): {exc}"
        )
        return False


def send_outbox_email_by_id(outbox_id: int) -> None:
    """Background worker helper to deliver an outbox item by its database ID."""
    session = SessionLocal()
    try:
        item = session.get(EmailOutbox, outbox_id)
        if item and item.status == OutboxStatus.PENDING:
            deliver_outbox_email(session, item)
    except Exception as e:
        logger.error(f"Error in background email delivery for outbox id={outbox_id}: {e}")
    finally:
        session.close()


def send_otp_email(
    to_email: str,
    otp_code: str,
    registration_number: str,
    session: Session | None = None,
) -> EmailOutbox:
    """Queues a student signup OTP email in the database outbox."""
    subject = "SVSU No-Dues Clearance: Your Sign-Up Verification Code"
    body = (
        f"Dear Student,\n\n"
        f"Your one-time verification code for No-Dues Clearance registration is: {otp_code}\n\n"
        f"This code is valid for 10 minutes.\n"
        f"If you did not initiate this request, please disregard this email.\n\n"
        f"Regards,\n"
        f"SVSU No-Dues Clearance Team"
    )

    if session is not None:
        return queue_email(
            session=session,
            to_email=to_email,
            subject=subject,
            body=body,
            kind="signup_otp",
        )
    else:
        local_db = SessionLocal()
        try:
            item = queue_email(
                session=local_db,
                to_email=to_email,
                subject=subject,
                body=body,
                kind="signup_otp",
            )
            local_db.commit()
            local_db.refresh(item)
            return item
        finally:
            local_db.close()


def notify_officers_new_request(session: Session, request: ClearanceRequest) -> None:
    """Queues 1 email per active officer of each department on the new clearance request."""
    subject = "SVSU No-Dues Clearance: New Request Awaiting Review"
    url = f"{settings.FRONTEND_BASE_URL}/department/queue"
    body = (
        f"A new student no-dues clearance request has been submitted and is awaiting your department's review.\n\n"
        f"Please log in to review the pending queue:\n{url}\n\n"
        f"Regards,\nSVSU No-Dues Clearance Team"
    )

    dept_ids = [
        row[0]
        for row in session.execute(
            select(DepartmentApproval.department_id).where(DepartmentApproval.request_id == request.id)
        ).all()
    ]
    if not dept_ids and request.approvals:
        dept_ids = [a.department_id for a in request.approvals]
    if not dept_ids:
        return

    officers = session.execute(
        select(User).where(
            User.role == UserRole.dept_officer,
            User.department_id.in_(dept_ids),
            User.is_active == True,
        )
    ).scalars().all()

    for officer in officers:
        queue_email(
            session=session,
            to_email=officer.email,
            subject=subject,
            body=body,
            kind="request_submitted",
            related_request_id=request.id,
        )


def notify_student_rejection(
    session: Session,
    request: ClearanceRequest,
    department_name: str,
    remarks: str,
) -> None:
    """Queues rejection notice to student with mandatory department remarks."""
    student_email = request.roster_entry.email if request.roster_entry else None
    if not student_email:
        return

    subject = f"SVSU No-Dues Clearance: Action Required ({department_name})"
    url = f"{settings.FRONTEND_BASE_URL}/student"
    body = (
        f"Your no-dues clearance request was rejected by {department_name}.\n\n"
        f"Department Remarks:\n{remarks}\n\n"
        f"Please resolve the dues and resubmit your clearance request:\n{url}\n\n"
        f"Regards,\nSVSU No-Dues Clearance Team"
    )
    queue_email(
        session=session,
        to_email=student_email,
        subject=subject,
        body=body,
        kind="rejection",
        related_request_id=request.id,
    )


def notify_hod_all_approved(session: Session, request: ClearanceRequest) -> None:
    """Queues email to academic HoD when all departmental approvals have been completed."""
    academic_dept_id = None
    if request.roster_entry and request.roster_entry.programme:
        academic_dept_id = request.roster_entry.programme.academic_department_id

    if not academic_dept_id:
        return

    hod = session.execute(
        select(User).where(
            User.role == UserRole.hod,
            User.department_id == academic_dept_id,
            User.is_active == True,
        )
    ).scalars().first()

    if not hod:
        return

    subject = "SVSU No-Dues Clearance: Request Ready for HoD Review"
    url = f"{settings.FRONTEND_BASE_URL}/hod/queue"
    body = (
        f"All department clearances have been approved for a student in your academic department.\n\n"
        f"Please review the request and render the final departmental clearance decision:\n{url}\n\n"
        f"Regards,\nSVSU No-Dues Clearance Team"
    )
    queue_email(
        session=session,
        to_email=hod.email,
        subject=subject,
        body=body,
        kind="hod_review",
        related_request_id=request.id,
    )


def notify_student_hod_rejected(
    session: Session,
    request: ClearanceRequest,
    remarks: str,
) -> None:
    """Queues HoD rejection notification to student with remarks."""
    student_email = request.roster_entry.email if request.roster_entry else None
    if not student_email:
        return

    subject = "SVSU No-Dues Clearance: HoD Decision"
    url = f"{settings.FRONTEND_BASE_URL}/student"
    body = (
        f"Your no-dues clearance request was rejected by your Head of Department.\n\n"
        f"HoD Remarks:\n{remarks}\n\n"
        f"Please review the remarks and update your submission:\n{url}\n\n"
        f"Regards,\nSVSU No-Dues Clearance Team"
    )
    queue_email(
        session=session,
        to_email=student_email,
        subject=subject,
        body=body,
        kind="hod_rejected",
        related_request_id=request.id,
    )


def notify_hod_approved(session: Session, request: ClearanceRequest) -> None:
    """Queues approval notification to student and notification to Registrar Accounts."""
    student_email = request.roster_entry.email if request.roster_entry else None
    if student_email:
        url = f"{settings.FRONTEND_BASE_URL}/student"
        queue_email(
            session=session,
            to_email=student_email,
            subject="SVSU No-Dues Clearance: Approved by Head of Department",
            body=(
                f"Your no-dues clearance request has received Head of Department approval and has been "
                f"forwarded to Registrar Accounts for caution money refund verification.\n\n"
                f"Track your clearance status:\n{url}\n\n"
                f"Regards,\nSVSU No-Dues Clearance Team"
            ),
            kind="hod_approved_student",
            related_request_id=request.id,
        )

    # Notify Registrar Accounts officers
    reg_officers = session.execute(
        select(User).where(
            User.role == UserRole.registrar_accounts,
            User.is_active == True,
        )
    ).scalars().all()

    reg_url = f"{settings.FRONTEND_BASE_URL}/registrar"
    for ro in reg_officers:
        queue_email(
            session=session,
            to_email=ro.email,
            subject="SVSU No-Dues Clearance: New Clearance Ready for Refund Verification",
            body=(
                f"A clearance request has received HoD approval and is ready for security deposit "
                f"refund verification.\n\n"
                f"Please review the registrar queue:\n{reg_url}\n\n"
                f"Regards,\nSVSU No-Dues Clearance Team"
            ),
            kind="hod_approved_registrar",
            related_request_id=request.id,
        )


def notify_refund_verified(
    session: Session,
    request: ClearanceRequest,
    amount: Decimal | str,
) -> None:
    """Queues refund verification notice to student."""
    student_email = request.roster_entry.email if request.roster_entry else None
    if not student_email:
        return

    url = f"{settings.FRONTEND_BASE_URL}/student"
    queue_email(
        session=session,
        to_email=student_email,
        subject="SVSU No-Dues Clearance: Caution Money Refund Verified",
        body=(
            f"Your caution money refund of Rs. {amount} has been verified by Registrar Accounts.\n\n"
            f"View your clearance status and certificate:\n{url}\n\n"
            f"Regards,\nSVSU No-Dues Clearance Team"
        ),
        kind="refund_verified",
        related_request_id=request.id,
    )


def notify_refund_processed(
    session: Session,
    request: ClearanceRequest,
    payment_reference: str,
) -> None:
    """Queues refund payment processed notice to student."""
    student_email = request.roster_entry.email if request.roster_entry else None
    if not student_email:
        return

    url = f"{settings.FRONTEND_BASE_URL}/student"
    queue_email(
        session=session,
        to_email=student_email,
        subject="SVSU No-Dues Clearance: Refund Payment Processed",
        body=(
            f"Your caution money refund has been processed with payment transaction reference: {payment_reference}.\n\n"
            f"View your clearance record:\n{url}\n\n"
            f"Regards,\nSVSU No-Dues Clearance Team"
        ),
        kind="refund_processed",
        related_request_id=request.id,
    )


def notify_department_added(
    session: Session,
    request: ClearanceRequest,
    department: Department,
    reason: str,
) -> None:
    """Queues notification to officers of the added department and notice to student."""
    # Notify officers of added office
    officers = session.execute(
        select(User).where(
            User.role == UserRole.dept_officer,
            User.department_id == department.id,
            User.is_active == True,
        )
    ).scalars().all()

    dept_url = f"{settings.FRONTEND_BASE_URL}/department/queue"
    for officer in officers:
        queue_email(
            session=session,
            to_email=officer.email,
            subject="SVSU No-Dues Clearance: Department Added to Request",
            body=(
                f"Your department '{department.name}' was added to an active clearance request.\n\n"
                f"Please review the pending queue:\n{dept_url}\n\n"
                f"Regards,\nSVSU No-Dues Clearance Team"
            ),
            kind="department_added_officer",
            related_request_id=request.id,
        )

    # Notify student
    student_email = request.roster_entry.email if request.roster_entry else None
    if student_email:
        student_url = f"{settings.FRONTEND_BASE_URL}/student"
        queue_email(
            session=session,
            to_email=student_email,
            subject=f"SVSU No-Dues Clearance: Office Added ({department.name})",
            body=(
                f"The office '{department.name}' was added to your clearance request.\n"
                f"Reason: {reason}\n\n"
                f"Track your clearance status:\n{student_url}\n\n"
                f"Regards,\nSVSU No-Dues Clearance Team"
            ),
            kind="department_added_student",
            related_request_id=request.id,
        )


def notify_request_cancelled(
    session: Session,
    request: ClearanceRequest,
    reason: str,
) -> None:
    """Queues cancellation notice to student."""
    student_email = request.roster_entry.email if request.roster_entry else None
    if not student_email:
        return

    student_url = f"{settings.FRONTEND_BASE_URL}/student"
    queue_email(
        session=session,
        to_email=student_email,
        subject="SVSU No-Dues Clearance: Request Cancelled",
        body=(
            f"Your no-dues clearance request has been cancelled.\n"
            f"Reason: {reason}\n\n"
            f"You may submit a new request if needed:\n{student_url}\n\n"
            f"Regards,\nSVSU No-Dues Clearance Team"
        ),
        kind="cancelled",
        related_request_id=request.id,
    )
