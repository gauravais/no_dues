"""Email outbox worker script.

Pulls PENDING items from email_outbox, attempts delivery (via console in dev or SMTP in prod),
and handles retry backoff up to 5 attempts. Never crashes on a single bad row and never logs
sensitive passwords or OTP bodies.
"""
import argparse
import logging
import sys
import time
from sqlalchemy import select

from backend.app.core.database import SessionLocal
from backend.app.models.email import EmailOutbox, OutboxStatus
from backend.app.services.email import deliver_outbox_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("send_emails")


def process_pending_emails(batch_size: int = 50) -> int:
    """Processes a batch of pending emails from the outbox table. Returns number processed."""
    session = SessionLocal()
    processed_count = 0
    try:
        items = session.execute(
            select(EmailOutbox)
            .where(
                EmailOutbox.status == OutboxStatus.PENDING,
                EmailOutbox.attempts < 5,
            )
            .order_by(EmailOutbox.id.asc())
            .limit(batch_size)
        ).scalars().all()

        if not items:
            return 0

        logger.info(f"Found {len(items)} pending email outbox items to process.")

        for item in items:
            try:
                success = deliver_outbox_email(session, item)
                processed_count += 1
                if success:
                    logger.info(f"Delivered email id={item.id} kind={item.kind} to={item.to_email} status={item.status}")
                else:
                    logger.warning(
                        f"Failed delivery attempt {item.attempts}/5 for email id={item.id} kind={item.kind}: {item.last_error}"
                    )
            except Exception as e:
                logger.error(f"Unexpected exception processing email id={item.id}: {e}")
                item.attempts += 1
                item.last_error = str(e)
                if item.attempts >= 5:
                    item.status = OutboxStatus.FAILED
                session.commit()
    finally:
        session.close()

    return processed_count


def main():
    parser = argparse.ArgumentParser(description="Process pending emails from outbox table.")
    parser.add_argument("--batch-size", type=int, default=50, help="Max emails to process in one batch")
    parser.add_argument("--loop", action="store_true", help="Run continuously in a polling loop")
    parser.add_argument("--interval", type=int, default=10, help="Polling interval in seconds when --loop is active")
    args = parser.parse_args()

    if not args.loop:
        count = process_pending_emails(args.batch_size)
        logger.info(f"Outbox sweep finished. Processed {count} emails.")
        sys.exit(0)

    logger.info(f"Starting continuous email outbox worker (interval: {args.interval}s)...")
    try:
        while True:
            process_pending_emails(args.batch_size)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Email worker stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
