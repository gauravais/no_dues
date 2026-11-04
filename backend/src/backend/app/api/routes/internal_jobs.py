"""Internal scheduled background job trigger endpoints."""
import secrets
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from backend.app.api.deps import SessionDep
from backend.app.core.config import settings
from backend.app.core.rate_limit import get_client_ip, check_rate_limit, record_attempt

# Dynamically inject backend directory and project root (two levels up from src) into sys.path
import sys
from pathlib import Path

_src_dir = Path(__file__).resolve().parents[4]
_backend_root = _src_dir.parent
_project_root = _backend_root.parent

for _path in (_backend_root, _project_root):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

from scripts.send_emails import process_pending_emails
from scripts.send_reminders import process_reminders

router = APIRouter(prefix="/internal/jobs", tags=["Internal Jobs"])


class EmailJobResponse(BaseModel):
    processed: int


class ReminderJobResponse(BaseModel):
    queued: int


def verify_job_key(
    request: Request,
    db: SessionDep,
    x_job_key: str | None = Header(None, alias="X-Job-Key"),
) -> None:
    """Enforces constant-time authentication via X-Job-Key header and rate limiting."""
    client_ip = get_client_ip(request)
    check_rate_limit(db, f"internal_job:{client_ip}", max_attempts=60)
    record_attempt(db, f"internal_job:{client_ip}", window_seconds=60)

    if not settings.JOB_SECRET or not settings.JOB_SECRET.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JOB_SECRET is not configured on the server",
        )

    if not x_job_key or not secrets.compare_digest(x_job_key.strip(), settings.JOB_SECRET.strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Job-Key",
        )


@router.post(
    "/send-emails",
    response_model=EmailJobResponse,
    include_in_schema=False,
    dependencies=[Depends(verify_job_key)],
)
def run_send_emails_job() -> EmailJobResponse:
    """Trigger a single batch of pending outbox emails."""
    count = process_pending_emails(batch_size=50)
    return EmailJobResponse(processed=count)


@router.post(
    "/send-reminders",
    response_model=ReminderJobResponse,
    include_in_schema=False,
    dependencies=[Depends(verify_job_key)],
)
def run_send_reminders_job(db: SessionDep) -> ReminderJobResponse:
    """Trigger a single sweep of reminder digests for pending clearance requests."""
    count = process_reminders(session=db)
    return ReminderJobResponse(queued=count)
