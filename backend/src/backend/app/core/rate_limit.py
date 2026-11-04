"""Database-backed rate limiting for authentication actions."""
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.models.rate_limit import AuthRateLimit


def get_client_ip(request: Request) -> str:
    """
    Extract the real client IP address.

    Configured via settings.TRUSTED_CLIENT_IP_HEADER:
    - Default empty (""): strictly uses the direct TCP socket address (request.client.host).
      No proxy headers are inspected. This is the secure default preventing header spoofing.
    - Configured (e.g. "True-Client-IP" on Render, "CF-Connecting-IP", or "X-Forwarded-For"):
      Reads the specified edge header. If the header contains a comma-separated list
      (such as standard X-Forwarded-For: client, proxy1, proxy2), extracts the first
      (leftmost / client) IP.
      If the header is missing or empty, securely falls back to request.client.host.
    """
    trusted_header = (getattr(settings, "TRUSTED_CLIENT_IP_HEADER", "") or "").strip()
    if trusted_header:
        val = request.headers.get(trusted_header.lower())
        if val:
            client_ip = val.split(",")[0].strip()
            if client_ip:
                return client_ip

    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"


def check_rate_limit(
    db: Session,
    key: str,
    max_attempts: int,
) -> None:
    """
    Check if the key has reached max_attempts within its current window.
    If exceeded, raises HTTP 429 Too Many Requests with a Retry-After header.
    """
    now = datetime.now(timezone.utc)
    record = db.query(AuthRateLimit).filter(AuthRateLimit.key == key).first()
    if record and record.reset_at > now:
        if record.count >= max_attempts:
            retry_after = max(1, int((record.reset_at - now).total_seconds()))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )


def record_attempt(
    db: Session,
    key: str,
    window_seconds: int,
) -> int:
    """
    Record an attempt against a key. If the existing window has expired or is new,
    starts a fresh window with count=1. Otherwise increments count.
    Returns the new count.
    """
    now = datetime.now(timezone.utc)
    record = db.query(AuthRateLimit).filter(AuthRateLimit.key == key).first()
    if not record or record.reset_at <= now:
        if not record:
            record = AuthRateLimit(
                key=key,
                count=1,
                reset_at=now + timedelta(seconds=window_seconds),
            )
            db.add(record)
        else:
            record.count = 1
            record.reset_at = now + timedelta(seconds=window_seconds)
    else:
        record.count += 1
    db.commit()
    return record.count


def clear_rate_limit(db: Session, key: str) -> None:
    """Remove rate limit counter for key (e.g. on successful login)."""
    record = db.query(AuthRateLimit).filter(AuthRateLimit.key == key).first()
    if record:
        db.delete(record)
        db.commit()
