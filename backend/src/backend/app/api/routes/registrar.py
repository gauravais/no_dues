"""Registrar & Accounts refund verification and processing routes."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from backend.app.api.deps import SessionDep, require_roles
from backend.app.models.user import User, UserRole
from backend.app.models.clearance import ClearanceRequest, ClearanceStatus
from backend.app.models.refund import Refund, RefundStatus
from backend.app.models.roster import StudentRoster
from backend.app.models.audit import AuditLog
from backend.app.schemas.common import ErrorResponse
from backend.app.schemas.registrar import (
    RegistrarQueueResponse,
    RegistrarQueueItem,
    VerifyRefundRequest,
    VerifyRefundResponse,
    MarkRefundProcessedRequest,
    MarkRefundProcessedResponse,
)

router = APIRouter(prefix="/registrar", tags=["Registrar / Accounts"])
require_registrar = require_roles(UserRole.registrar_accounts)


@router.get(
    "/queue",
    response_model=RegistrarQueueResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_registrar_queue",
    summary="Get Cleared or Refund-Verified Requests for Refund",
    description=(
        "Returns a paginated list of clearance requests in CLEARED or REFUND_VERIFIED status, "
        "allowing the university accounts branch to verify refunds and record disbursement payment references."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid status parameter. Must be CLEARED or REFUND_VERIFIED."},
        403: {"model": ErrorResponse, "description": "Forbidden for non-registrar roles"},
    },
)
def get_registrar_queue(
    db: SessionDep,
    current_user: User = Depends(require_registrar),
    queue_status: str = Query("CLEARED", alias="status", description="Filter by clearance status: CLEARED (default) or REFUND_VERIFIED"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> RegistrarQueueResponse:
    clean_status = queue_status.strip().upper()
    if clean_status not in ("CLEARED", "REFUND_VERIFIED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{queue_status}'. Allowed values are 'CLEARED' or 'REFUND_VERIFIED'.",
        )

    target_status = ClearanceStatus(clean_status)

    # Count total requests matching status
    total = db.scalar(
        select(func.count(ClearanceRequest.id))
        .where(ClearanceRequest.status == target_status)
    ) or 0

    # Fetch batch
    requests = db.execute(
        select(ClearanceRequest)
        .where(ClearanceRequest.status == target_status)
        .options(
            joinedload(ClearanceRequest.roster_entry)
            .joinedload(StudentRoster.programme),
            joinedload(ClearanceRequest.refund),
            joinedload(ClearanceRequest.certificate),
        )
        .order_by(ClearanceRequest.updated_at.asc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()

    items = []
    for req in requests:
        r = req.roster_entry
        prog_name = r.programme.name if (r and r.programme) else "N/A"
        dep_amt = req.refund.deposit_amount if req.refund else (r.security_deposit_amount if r else 0)
        cleared_date = req.certificate.issued_at if req.certificate else req.updated_at
        refund_st = req.refund.status.value if req.refund else "N/A"
        deductions = req.refund.deductions if req.refund else None
        final_amt = req.refund.final_amount if req.refund else None

        items.append(
            RegistrarQueueItem(
                request_id=req.id,
                student_name=r.name if r else "N/A",
                registration_number=r.registration_number if r else "N/A",
                programme=prog_name,
                deposit_amount=dep_amt,
                deductions=deductions,
                final_amount=final_amt,
                cleared_at=cleared_date,
                status=req.status.value,
                refund_status=refund_st,
            )
        )

    return RegistrarQueueResponse(total=total, items=items)


@router.post(
    "/requests/{request_id}/verify-refund",
    response_model=VerifyRefundResponse,
    status_code=status.HTTP_200_OK,
    operation_id="verify_student_refund",
    summary="Verify Refund Deductions and Approve",
    description=(
        "Applies any verified dues/deductions against the initial security deposit. Deductions must satisfy "
        "0 <= deductions <= deposit. Moves the refund status to VERIFIED and request status to REFUND_VERIFIED. "
        "Executes atomically with row locking and logs an audit trail."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Request not in CLEARED status or invalid deduction limits"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-registrar roles"},
        404: {"model": ErrorResponse, "description": "Clearance request or refund record not found"},
    },
)
def verify_refund(
    request_id: int,
    body: VerifyRefundRequest,
    db: SessionDep,
    current_user: User = Depends(require_registrar),
) -> VerifyRefundResponse:
    # 1. Concurrency lock on clearance request
    req = db.execute(
        select(ClearanceRequest)
        .where(ClearanceRequest.id == request_id)
        .with_for_update()
    ).scalars().first()

    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clearance request not found")

    if req.status != ClearanceStatus.CLEARED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Refund verification allowed only for requests in CLEARED status. Current: {req.status.value}",
        )

    # 2. Concurrency lock on refund record
    refund = db.execute(
        select(Refund)
        .where(Refund.request_id == req.id)
        .with_for_update()
    ).scalars().first()

    if not refund:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund record not found for this request")

    if body.deductions < 0 or body.deductions > refund.deposit_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Deductions must be between 0 and total deposit amount ({refund.deposit_amount}). Received: {body.deductions}",
        )

    now = datetime.now(timezone.utc)
    final_amt = refund.deposit_amount - body.deductions

    # 3. Update records
    refund.deductions = body.deductions
    refund.final_amount = final_amt
    refund.status = RefundStatus.VERIFIED
    refund.updated_at = now

    req.status = ClearanceStatus.REFUND_VERIFIED
    req.updated_at = now

    # 4. Audit Log
    audit = AuditLog(
        user_id=current_user.id,
        action="VERIFY_REFUND",
        entity_type="clearance_requests",
        entity_id=req.id,
        details={
            "deposit_amount": str(refund.deposit_amount),
            "deductions": str(body.deductions),
            "final_amount": str(final_amt),
            "remarks": body.remarks,
        },
        created_at=now,
    )
    db.add(audit)
    db.commit()

    return VerifyRefundResponse(
        request_id=req.id,
        deposit_amount=refund.deposit_amount,
        deductions=refund.deductions,
        final_amount=refund.final_amount,
        refund_status=refund.status.value,
        request_status=req.status.value,
        updated_at=refund.updated_at,
    )


@router.post(
    "/requests/{request_id}/mark-processed",
    response_model=MarkRefundProcessedResponse,
    status_code=status.HTTP_200_OK,
    operation_id="mark_refund_processed",
    summary="Mark Refund Disbursed / Processed",
    description=(
        "Records the bank payment reference (UTR/NEFT) once the refund amount is disbursed to the student's "
        "verified bank account. Requires the refund to have been VERIFIED previously."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Refund not in VERIFIED status yet"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-registrar roles"},
        404: {"model": ErrorResponse, "description": "Clearance request or refund record not found"},
    },
)
def mark_refund_processed(
    request_id: int,
    body: MarkRefundProcessedRequest,
    db: SessionDep,
    current_user: User = Depends(require_registrar),
) -> MarkRefundProcessedResponse:
    refund = db.execute(
        select(Refund)
        .where(Refund.request_id == request_id)
        .with_for_update()
    ).scalars().first()

    if not refund:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund record not found")

    if refund.status != RefundStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Refund must be in VERIFIED status before being marked as processed. Current status: {refund.status.value}",
        )

    now = datetime.now(timezone.utc)
    refund.status = RefundStatus.PROCESSED
    refund.updated_at = now

    audit = AuditLog(
        user_id=current_user.id,
        action="MARK_REFUND_PROCESSED",
        entity_type="clearance_requests",
        entity_id=request_id,
        details={"payment_reference": body.payment_reference.strip()},
        created_at=now,
    )
    db.add(audit)
    db.commit()

    return MarkRefundProcessedResponse(
        request_id=request_id,
        payment_reference=body.payment_reference.strip(),
        refund_status=refund.status.value,
        updated_at=refund.updated_at,
    )
