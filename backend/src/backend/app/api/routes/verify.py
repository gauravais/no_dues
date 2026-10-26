"""Public certificate verification endpoint (No authentication required)."""
from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from backend.app.api.deps import SessionDep
from backend.app.models.certificate import Certificate
from backend.app.models.clearance import ClearanceRequest
from backend.app.models.roster import StudentRoster
from backend.app.models.bank import mask_account_number
from backend.app.schemas.verify import PublicVerificationResponse

router = APIRouter(prefix="/verify", tags=["Public Verification"])


@router.get(
    "/{certificate_code}",
    response_model=PublicVerificationResponse,
    status_code=status.HTTP_200_OK,
    operation_id="verify_certificate_public",
    summary="Verify Certificate Authenticity (Public)",
    description=(
        "Public endpoint to verify a student's No-Dues clearance certificate using the unique UUID code "
        "or scanned QR code. Returns basic academic details and issue timestamp. Protects privacy by strictly "
        "masking the registration number and never exposing student names, phone numbers, emails, or financial details."
    ),
)
def verify_certificate(
    certificate_code: str,
    db: SessionDep,
) -> PublicVerificationResponse:
    cert = db.execute(
        select(Certificate)
        .where(Certificate.certificate_code == certificate_code)
        .options(
            joinedload(Certificate.request)
            .joinedload(ClearanceRequest.roster_entry)
            .joinedload(StudentRoster.programme)
        )
    ).scalars().first()

    if not cert or not cert.request or not cert.request.roster_entry:
        return PublicVerificationResponse(valid=False)

    roster = cert.request.roster_entry
    prog = roster.programme
    dept_name = prog.department.name if (prog and prog.department) else "N/A"
    prog_name = prog.name if prog else "N/A"

    try:
        masked_reg = mask_account_number(roster.registration_number)
    except ValueError:
        masked_reg = "****" + roster.registration_number[-4:] if len(roster.registration_number) >= 4 else "****"

    return PublicVerificationResponse(
        valid=True,
        issued_at=cert.issued_at,
        masked_registration_number=masked_reg,
        programme=prog_name,
        department=dept_name,
    )
