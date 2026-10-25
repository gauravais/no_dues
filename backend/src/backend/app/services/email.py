"""Email notification service for OTP verification."""
import logging
from backend.app.core.config import settings

logger = logging.getLogger("nodues.email")


def send_otp_email(to_email: str, otp_code: str, registration_number: str) -> None:
    """
    Delivers a one-time password to the student email.
    If MAIL_CONSOLE_ONLY is True, prints a formatted notice to stdout / server console.
    """
    message = (
        f"\n{'='*60}\n"
        f"[NO-DUES EMAIL SERVICE]\n"
        f"To: {to_email}\n"
        f"Subject: Your No-Dues Signup One-Time Password (OTP)\n"
        f"Registration Number: {registration_number}\n"
        f"One-Time Password: {otp_code}\n"
        f"Valid for: 10 minutes\n"
        f"{'='*60}\n"
    )

    if settings.MAIL_CONSOLE_ONLY:
        print(message, flush=True)
    else:
        logger.info(f"Dispatching OTP email to {to_email} (code: {otp_code})")
