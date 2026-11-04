"""Registrar & Accounts refund verification and processing routes."""
import time
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from backend.app.api.deps import SessionDep, require_roles
from backend.app.core.crypto import decrypt_bank_account
from backend.app.models.user import User, UserRole
from backend.app.models.clearance import ClearanceRequest, ClearanceStatus, DepartmentApproval
from backend.app.models.refund import Refund, RefundStatus
from backend.app.models.roster import StudentRoster
from backend.app.models.audit import AuditLog
from backend.app.schemas.common import ErrorResponse
from backend.app.schemas.workflow import DepartmentApprovalItem
from backend.app.schemas.registrar import (
    RegistrarQueueResponse,
    RegistrarQueueItem,
    RegistrarRequestDetailResponse,
    RevealBankDetailsResponse,
    VerifyRefundRequest,
    VerifyRefundResponse,
    MarkRefundProcessedRequest,
    MarkRefundProcessedResponse,
)
from backend.app.services.email import notify_refund_verified, notify_refund_processed

router = APIRouter(prefix="/registrar", tags=["Registrar / Accounts"])
require_registrar = require_roles(UserRole.registrar_accounts)

# Sliding window rate limiter for bank detail reveal: user_id -> list of float timestamps
_reveal_rate_limits: dict[int, list[float]] = {}


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

    target_deposit = body.deposit_amount if body.deposit_amount is not None else refund.deposit_amount
    if target_deposit < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deposit amount cannot be negative.",
        )

    if body.deductions < 0 or body.deductions > target_deposit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Deductions must be between 0 and total deposit amount ({target_deposit}). Received: {body.deductions}",
        )

    clean_remarks = body.remarks.strip() if body.remarks else ""
    if not clean_remarks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Remarks are mandatory when verifying refund.",
        )

    now = datetime.now(timezone.utc)
    final_amt = target_deposit - body.deductions

    # 3. Update records
    refund.deposit_amount = target_deposit
    refund.deductions = body.deductions
    refund.final_amount = final_amt
    refund.remarks = clean_remarks
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
            "deductions": str(refund.deductions),
            "final_amount": str(final_amt),
            "remarks": clean_remarks,
        },
        created_at=now,
    )
    db.add(audit)
    notify_refund_verified(db, req, refund.final_amount or refund.deposit_amount)
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
    refund.payment_reference = body.payment_reference.strip()
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
    notify_refund_processed(db, refund.request, refund.payment_reference)
    db.commit()

    return MarkRefundProcessedResponse(
        request_id=request_id,
        payment_reference=body.payment_reference.strip(),
        refund_status=refund.status.value,
        updated_at=refund.updated_at,
    )


@router.get(
    "/requests/{request_id}",
    response_model=RegistrarRequestDetailResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_registrar_request_detail",
    summary="Get Clearance Request Details for Registrar",
    description=(
        "Returns full request details including student provenance (who uploaded/added to roster), "
        "masked bank account details, and refund status."
    ),
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-registrar roles"},
        404: {"model": ErrorResponse, "description": "Clearance request not found"},
    },
)
def get_registrar_request_detail(
    request_id: int,
    db: SessionDep,
    current_user: User = Depends(require_registrar),
) -> RegistrarRequestDetailResponse:
    req = db.execute(
        select(ClearanceRequest)
        .where(ClearanceRequest.id == request_id)
        .options(
            joinedload(ClearanceRequest.roster_entry).joinedload(StudentRoster.programme),
            joinedload(ClearanceRequest.roster_entry).joinedload(StudentRoster.created_by_user),
            joinedload(ClearanceRequest.roster_entry).joinedload(StudentRoster.bank_detail),
            joinedload(ClearanceRequest.refund),
            joinedload(ClearanceRequest.approvals).joinedload(DepartmentApproval.department),
            joinedload(ClearanceRequest.approvals).joinedload(DepartmentApproval.decided_by_user),
            joinedload(ClearanceRequest.approvals).joinedload(DepartmentApproval.added_by_user),
        )
    ).unique().scalar_one_or_none()

    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clearance request not found")

    r = req.roster_entry
    prog_name = r.programme.name if (r and r.programme) else "Unknown"
    bank = r.bank_detail if r else None

    # Fallback to roster security deposit if no refund record yet
    deposit_amt = req.refund.deposit_amount if req.refund else (r.security_deposit_amount if r else Decimal("0.00"))
    deductions = req.refund.deductions if req.refund else None
    final_amt = req.refund.final_amount if req.refund else None
    refund_st = req.refund.status.value if req.refund else "N/A"

    approval_items = [
        DepartmentApprovalItem(
            id=a.id,
            department_id=a.department_id,
            department_name=a.department.name if a.department else f"Department #{a.department_id}",
            department_kind=a.department.kind.value if a.department else "service",
            status=a.status,
            remarks=a.remarks,
            previous_remarks=a.previous_remarks,
            decided_at=a.decided_at,
            decided_by_name=a.decided_by_user.full_name or a.decided_by_user.email if a.decided_by_user else None,
            resubmission_count=a.resubmission_count,
            added_by_user_id=a.added_by_user_id,
            added_by_name=a.added_by_user.full_name or a.added_by_user.email if a.added_by_user else None,
            added_reason=a.added_reason,
        )
        for a in (req.approvals or [])
    ]

    creator_name = None
    if r and r.created_by_user:
        creator_name = r.created_by_user.full_name or r.created_by_user.email

    return RegistrarRequestDetailResponse(
        request_id=req.id,
        status=req.status.value,
        student_name=r.name if r else "Unknown",
        registration_number=r.registration_number if r else "Unknown",
        programme=prog_name,
        roster_source=r.source if r else None,
        roster_created_by_user_id=r.created_by_user_id if r else None,
        roster_created_by_name=creator_name,
        account_number_masked=bank.masked_account_number if bank else "N/A",
        ifsc_code=bank.ifsc_code if bank else "N/A",
        account_holder_name=bank.account_holder_name if bank else "N/A",
        bank_address=bank.bank_address if bank else "N/A",
        deposit_amount=deposit_amt,
        deductions=deductions,
        final_amount=final_amt,
        refund_status=refund_st,
        approvals=approval_items,
    )


@router.post(
    "/requests/{request_id}/reveal-bank-details",
    response_model=RevealBankDetailsResponse,
    status_code=status.HTTP_200_OK,
    operation_id="reveal_student_bank_details",
    summary="Audited Reveal of Full Bank Account Number",
    description=(
        "Returns plain, unmasked bank account details for a student whose clearance is CLEARED or REFUND_VERIFIED. "
        "Strictly restricted to registrar_accounts role, rate limited to 10 requests per minute per user, "
        "and logged in the audit trail without revealing the account number."
    ),
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-registrar roles"},
        404: {"model": ErrorResponse, "description": "Clearance request or bank details not found"},
        409: {"model": ErrorResponse, "description": "Request is not in CLEARED or REFUND_VERIFIED status"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded (10 calls/min)"},
    },
)
def reveal_student_bank_details(
    request_id: int,
    db: SessionDep,
    current_user: User = Depends(require_registrar),
) -> RevealBankDetailsResponse:
    # 1. Rate limiting: max 10 requests per minute per user
    now_ts = time.time()
    window_start = now_ts - 60.0
    timestamps = _reveal_rate_limits.get(current_user.id, [])
    timestamps = [t for t in timestamps if t > window_start]
    if len(timestamps) >= 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 10 bank account reveals per minute.",
        )
    timestamps.append(now_ts)
    _reveal_rate_limits[current_user.id] = timestamps

    # 2. Fetch clearance request
    req = db.execute(
        select(ClearanceRequest)
        .where(ClearanceRequest.id == request_id)
        .options(
            joinedload(ClearanceRequest.roster_entry).joinedload(StudentRoster.bank_detail),
        )
    ).unique().scalar_one_or_none()

    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clearance request not found")

    # 3. State guard: must be CLEARED or REFUND_VERIFIED
    if req.status not in (ClearanceStatus.CLEARED, ClearanceStatus.REFUND_VERIFIED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bank details cannot be revealed while request is in '{req.status.value}'. Must be CLEARED or REFUND_VERIFIED.",
        )

    bank = req.roster_entry.bank_detail if req.roster_entry else None
    if not bank:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank details not found for student")

    # 4. Decrypt bank account
    plain_account_number = decrypt_bank_account(bank.account_number)

    # 5. Audit Log (MUST NOT contain plain account number)
    now = datetime.now(timezone.utc)
    audit = AuditLog(
        user_id=current_user.id,
        action="BANK_DETAILS_REVEALED",
        entity_type="clearance_requests",
        entity_id=req.id,
        details={
            "request_id": req.id,
            "registration_number": req.roster_entry.registration_number if req.roster_entry else None,
            "revealed_by": current_user.email,
        },
        created_at=now,
    )
    db.add(audit)
    db.commit()

    return RevealBankDetailsResponse(
        account_holder_name=bank.account_holder_name,
        account_number=plain_account_number,
        ifsc_code=bank.ifsc_code,
        bank_address=bank.bank_address,
    )
