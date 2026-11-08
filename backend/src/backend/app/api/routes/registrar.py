"""Registrar & Accounts refund verification and processing routes."""
import csv
import io
import time
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import joinedload

from backend.app.api.deps import SessionDep, require_roles
from backend.app.core.crypto import decrypt_bank_account
from backend.app.models.user import User, UserRole
from backend.app.models.clearance import ClearanceRequest, ClearanceStatus, DepartmentApproval
from backend.app.models.refund import Refund, RefundStatus
from backend.app.models.roster import StudentRoster
from backend.app.models.audit import AuditLog
from backend.app.schemas.common import ErrorResponse, MessageResponse
from backend.app.schemas.workflow import DepartmentApprovalItem
from backend.app.schemas.registrar import (
    DepositLedgerRowReport,
    DepositLedgerUploadResponse,
    PaymentMode,
    RegistrarQueueResponse,
    RegistrarQueueItem,
    RegistrarQueueCounts,
    RegistrarRequestDetailResponse,
    RevealBankDetailsResponse,
    UpdateRosterDepositRequest,
    UpdateRosterDepositResponse,
    VerifyRefundRequest,
    VerifyRefundResponse,
    ReopenVerificationRequest,
    MarkRefundProcessedRequest,
    MarkRefundProcessedResponse,
    MarkRefundFailedRequest,
    ResolveStudentIssueRequest,
)
from backend.app.services.email import (
    notify_refund_verified,
    notify_refund_processed,
    notify_refund_failed,
)

router = APIRouter(prefix="/registrar", tags=["Registrar / Accounts"])
require_registrar = require_roles(UserRole.registrar_accounts)

def _payment_mode_str(val) -> str | None:
    if not val:
        return None
    return val.value if hasattr(val, "value") else str(val)


# Sliding window rate limiter for bank detail reveal: user_id -> list of float timestamps
_reveal_rate_limits: dict[int, list[float]] = {}


@router.get(
    "/queue",
    response_model=RegistrarQueueResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_registrar_queue",
    summary="Get Clearance Requests for Refund Queue",
    description=(
        "Returns a paginated list of clearance requests filtered by tab (TO_VERIFY, TO_PAY, PAID, FAILED, ALL), "
        "tab counts, and aggregate financial totals for accounts verification and disbursement."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid tab or status parameter"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-registrar roles"},
    },
)
def get_registrar_queue(
    db: SessionDep,
    current_user: User = Depends(require_registrar),
    tab: str | None = Query(None, description="Queue tab: TO_VERIFY, TO_PAY, PAID, FAILED, ALL"),
    queue_status: str | None = Query(None, alias="status", description="Legacy status filter: CLEARED or REFUND_VERIFIED"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> RegistrarQueueResponse:
    use_legacy_status = False
    legacy_status_val = None
    if tab is not None:
        clean_tab = tab.strip().upper()
        if clean_tab not in ("TO_VERIFY", "TO_PAY", "PAID", "FAILED", "ALL"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid tab '{tab}'. Allowed values are TO_VERIFY, TO_PAY, PAID, FAILED, ALL.",
            )
    elif queue_status is not None:
        clean_s = queue_status.strip().upper()
        if clean_s == "CLEARED":
            use_legacy_status = True
            legacy_status_val = ClearanceStatus.CLEARED
            clean_tab = "TO_VERIFY"
        elif clean_s == "REFUND_VERIFIED":
            use_legacy_status = True
            legacy_status_val = ClearanceStatus.REFUND_VERIFIED
            clean_tab = "TO_PAY"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status '{queue_status}'. Allowed values are 'CLEARED' or 'REFUND_VERIFIED'.",
            )
    else:
        clean_tab = "TO_VERIFY"

    # 1. Tab Counts
    count_to_verify = db.scalar(
        select(func.count(ClearanceRequest.id))
        .outerjoin(Refund, ClearanceRequest.id == Refund.request_id)
        .where(
            ClearanceRequest.status == ClearanceStatus.CLEARED,
            or_(Refund.id == None, Refund.status == RefundStatus.PENDING_VERIFICATION),
        )
    ) or 0

    count_to_pay = db.scalar(
        select(func.count(ClearanceRequest.id))
        .join(Refund, ClearanceRequest.id == Refund.request_id)
        .where(
            ClearanceRequest.status == ClearanceStatus.REFUND_VERIFIED,
            Refund.status == RefundStatus.VERIFIED,
        )
    ) or 0

    count_paid = db.scalar(
        select(func.count(ClearanceRequest.id))
        .join(Refund, ClearanceRequest.id == Refund.request_id)
        .where(
            ClearanceRequest.status == ClearanceStatus.REFUND_VERIFIED,
            Refund.status == RefundStatus.PROCESSED,
        )
    ) or 0

    count_failed = db.scalar(
        select(func.count(ClearanceRequest.id))
        .join(Refund, ClearanceRequest.id == Refund.request_id)
        .where(
            ClearanceRequest.status == ClearanceStatus.REFUND_VERIFIED,
            Refund.status == RefundStatus.PAYMENT_FAILED,
        )
    ) or 0

    count_all = db.scalar(
        select(func.count(ClearanceRequest.id))
        .where(
            ClearanceRequest.status.in_([ClearanceStatus.CLEARED, ClearanceStatus.REFUND_VERIFIED]),
        )
    ) or 0

    counts = RegistrarQueueCounts(
        TO_VERIFY=count_to_verify,
        TO_PAY=count_to_pay,
        PAID=count_paid,
        FAILED=count_failed,
        ALL=count_all,
    )

    # 2. Financial Totals
    total_to_pay = db.scalar(
        select(func.coalesce(func.sum(Refund.final_amount), Decimal("0.00")))
        .join(ClearanceRequest, ClearanceRequest.id == Refund.request_id)
        .where(
            ClearanceRequest.status == ClearanceStatus.REFUND_VERIFIED,
            Refund.status == RefundStatus.VERIFIED,
        )
    ) or Decimal("0.00")

    total_paid = db.scalar(
        select(func.coalesce(func.sum(Refund.final_amount), Decimal("0.00")))
        .join(ClearanceRequest, ClearanceRequest.id == Refund.request_id)
        .where(
            ClearanceRequest.status == ClearanceStatus.REFUND_VERIFIED,
            Refund.status == RefundStatus.PROCESSED,
        )
    ) or Decimal("0.00")

    # 3. Query items for selected tab
    base_query = (
        select(ClearanceRequest)
        .outerjoin(Refund, ClearanceRequest.id == Refund.request_id)
        .options(
            joinedload(ClearanceRequest.roster_entry).joinedload(StudentRoster.programme),
            joinedload(ClearanceRequest.refund),
            joinedload(ClearanceRequest.certificate),
        )
    )

    if use_legacy_status:
        tab_filter = (ClearanceRequest.status == legacy_status_val)
        total = db.scalar(select(func.count(ClearanceRequest.id)).where(tab_filter)) or 0
    elif clean_tab == "TO_VERIFY":
        tab_filter = and_(
            ClearanceRequest.status == ClearanceStatus.CLEARED,
            or_(Refund.id == None, Refund.status == RefundStatus.PENDING_VERIFICATION),
        )
        total = count_to_verify
    elif clean_tab == "TO_PAY":
        tab_filter = and_(
            ClearanceRequest.status == ClearanceStatus.REFUND_VERIFIED,
            Refund.status == RefundStatus.VERIFIED,
        )
        total = count_to_pay
    elif clean_tab == "PAID":
        tab_filter = and_(
            ClearanceRequest.status == ClearanceStatus.REFUND_VERIFIED,
            Refund.status == RefundStatus.PROCESSED,
        )
        total = count_paid
    elif clean_tab == "FAILED":
        tab_filter = and_(
            ClearanceRequest.status == ClearanceStatus.REFUND_VERIFIED,
            Refund.status == RefundStatus.PAYMENT_FAILED,
        )
        total = count_failed
    else:  # ALL
        tab_filter = ClearanceRequest.status.in_([ClearanceStatus.CLEARED, ClearanceStatus.REFUND_VERIFIED])
        total = count_all

    requests = db.execute(
        base_query.where(tab_filter)
        .order_by(ClearanceRequest.updated_at.asc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()

    items = []
    for req in requests:
        r = req.roster_entry
        prog_name = r.programme.name if (r and r.programme) else "N/A"
        dep_amt = req.refund.deposit_amount if req.refund else (r.security_deposit_amount if r else Decimal("0.00"))
        ledger_amt = r.security_deposit_amount if (r and r.security_deposit_amount and r.security_deposit_amount > 0) else None
        cleared_date = req.certificate.issued_at if req.certificate else req.updated_at
        refund_st = req.refund.status.value if req.refund else "N/A"
        deductions = req.refund.deductions if req.refund else None
        final_amt = req.refund.final_amount if req.refund else None
        issue_open = bool(req.refund and req.refund.student_issue_at and not req.refund.student_issue_resolved_at)

        items.append(
            RegistrarQueueItem(
                request_id=req.id,
                roster_id=req.roster_id,
                student_name=r.name if r else "N/A",
                registration_number=r.registration_number if r else "N/A",
                programme=prog_name,
                deposit_amount=dep_amt,
                ledger_deposit_amount=ledger_amt,
                deductions=deductions,
                final_amount=final_amt,
                cleared_date=cleared_date,
                status=req.status.value,
                refund_status=refund_st,
                student_issue_open=issue_open,
            )
        )

    return RegistrarQueueResponse(
        total=total,
        items=items,
        counts=counts,
        total_to_pay_amount=total_to_pay,
        total_paid_amount=total_paid,
    )


@router.post(
    "/requests/{request_id}/verify-refund",
    response_model=VerifyRefundResponse,
    status_code=status.HTTP_200_OK,
    operation_id="verify_student_refund",
    summary="Verify Refund Deductions and Approve",
    description=(
        "Applies verified dues/deductions against the initial security deposit. Deductions must satisfy "
        "0 <= deductions <= deposit. Moves refund status to VERIFIED and request status to REFUND_VERIFIED. "
        "Remarks become student-visible accounts_note (max 500 characters). Executes atomically with row locking."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid deduction limits or remarks"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-registrar roles"},
        404: {"model": ErrorResponse, "description": "Clearance request or refund record not found"},
        409: {"model": ErrorResponse, "description": "Request not in CLEARED status or refund not in PENDING_VERIFICATION"},
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
            status_code=status.HTTP_409_CONFLICT,
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

    if refund.status != RefundStatus.PENDING_VERIFICATION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Refund verification allowed only when refund status is PENDING_VERIFICATION. Current: {refund.status.value}",
        )

    target_deposit = (body.deposit_amount if body.deposit_amount is not None else refund.deposit_amount).quantize(Decimal("0.01"))
    if target_deposit < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deposit amount cannot be negative.",
        )

    deductions_amt = body.deductions.quantize(Decimal("0.01"))
    if deductions_amt < 0 or deductions_amt > target_deposit:
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
    if len(clean_remarks) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Remarks cannot exceed 500 characters.",
        )

    now = datetime.now(timezone.utc)
    final_amt = target_deposit - deductions_amt

    # 3. Update records
    refund.deposit_amount = target_deposit
    refund.deductions = deductions_amt
    refund.final_amount = final_amt
    refund.remarks = clean_remarks
    refund.accounts_note = clean_remarks
    refund.verified_at = now
    refund.verified_by_user_id = current_user.id
    refund.status = RefundStatus.VERIFIED
    refund.updated_at = now

    req.status = ClearanceStatus.REFUND_VERIFIED
    req.updated_at = now

    # 4. Audit Log
    audit_details = {
        "deposit_amount": f"{refund.deposit_amount:.2f}",
        "deductions": f"{refund.deductions:.2f}",
        "final_amount": f"{final_amt:.2f}",
        "remarks": clean_remarks,
    }
    roster_entry = db.scalar(select(StudentRoster).where(StudentRoster.id == req.roster_id)) if req.roster_id else None
    ledger_val = roster_entry.security_deposit_amount if roster_entry else None
    if ledger_val is not None and ledger_val > 0:
        audit_details["ledger_deposit_amount"] = f"{ledger_val:.2f}"
        if target_deposit != ledger_val:
            audit_details["deposit_differs_from_ledger"] = True
    elif ledger_val is not None and target_deposit != ledger_val:
        audit_details["ledger_deposit_amount"] = f"{ledger_val:.2f}"
        audit_details["deposit_differs_from_ledger"] = True

    audit = AuditLog(
        user_id=current_user.id,
        action="VERIFY_REFUND",
        entity_type="clearance_requests",
        entity_id=req.id,
        details=audit_details,
        created_at=now,
    )
    db.add(audit)
    notify_refund_verified(db, req, final_amt, clean_remarks)
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
    "/requests/{request_id}/reopen-verification",
    response_model=VerifyRefundResponse,
    status_code=status.HTTP_200_OK,
    operation_id="reopen_refund_verification",
    summary="Reopen Refund Verification to Correct Amounts",
    description=(
        "Reopens a verified refund back to PENDING_VERIFICATION and transitions request status from REFUND_VERIFIED "
        "back to CLEARED, allowing accounts staff to correct deductions or amounts. Reason is mandatory."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Missing or empty reason"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-registrar roles"},
        404: {"model": ErrorResponse, "description": "Clearance request or refund record not found"},
        409: {"model": ErrorResponse, "description": "Refund not in VERIFIED status or request not in REFUND_VERIFIED"},
    },
)
def reopen_refund_verification(
    request_id: int,
    body: ReopenVerificationRequest,
    db: SessionDep,
    current_user: User = Depends(require_registrar),
) -> VerifyRefundResponse:
    clean_reason = body.reason.strip() if body.reason else ""
    if not clean_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reason is mandatory to reopen verification.",
        )
    if len(clean_reason) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reason cannot exceed 500 characters.",
        )

    req = db.execute(
        select(ClearanceRequest).where(ClearanceRequest.id == request_id).with_for_update()
    ).scalars().first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clearance request not found")

    refund = db.execute(
        select(Refund).where(Refund.request_id == req.id).with_for_update()
    ).scalars().first()
    if not refund:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund record not found")

    if refund.status != RefundStatus.VERIFIED or req.status != ClearanceStatus.REFUND_VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Reopen verification allowed only when refund is VERIFIED and request is REFUND_VERIFIED (current refund: {refund.status.value}, request: {req.status.value}).",
        )

    now = datetime.now(timezone.utc)
    refund.status = RefundStatus.PENDING_VERIFICATION
    refund.updated_at = now
    req.status = ClearanceStatus.CLEARED
    req.updated_at = now

    audit = AuditLog(
        user_id=current_user.id,
        action="REOPEN_REFUND_VERIFICATION",
        entity_type="clearance_requests",
        entity_id=req.id,
        details={"reason": clean_reason},
        created_at=now,
    )
    db.add(audit)
    db.commit()

    return VerifyRefundResponse(
        request_id=req.id,
        deposit_amount=refund.deposit_amount,
        deductions=refund.deductions or Decimal("0.00"),
        final_amount=refund.final_amount or refund.deposit_amount,
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
        "Records the bank payment reference (6 to 40 letters/digits/hyphens), disbursement date (paid_on), "
        "and payment mode once the refund is disbursed. Only allowed when refund is VERIFIED. Closes open student issue if any."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid disbursement date or payment reference"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-registrar roles"},
        404: {"model": ErrorResponse, "description": "Clearance request or refund record not found"},
        409: {"model": ErrorResponse, "description": "Refund not in VERIFIED status"},
    },
)
def mark_refund_processed(
    request_id: int,
    body: MarkRefundProcessedRequest,
    db: SessionDep,
    current_user: User = Depends(require_registrar),
) -> MarkRefundProcessedResponse:
    req = db.execute(
        select(ClearanceRequest).where(ClearanceRequest.id == request_id).with_for_update()
    ).scalars().first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clearance request not found")

    refund = db.execute(
        select(Refund)
        .where(Refund.request_id == request_id)
        .with_for_update()
    ).scalars().first()

    if not refund:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund record not found")

    if refund.status != RefundStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Refund must be in VERIFIED status before being marked as processed. Current status: {refund.status.value}",
        )

    now = datetime.now(timezone.utc)
    today = now.date()

    if body.paid_on > today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Disbursement date cannot be in the future.",
        )

    if refund.verified_at and body.paid_on < refund.verified_at.date():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Disbursement date cannot be before the refund verification date.",
        )

    clean_ref = body.payment_reference.strip()
    refund.status = RefundStatus.PROCESSED
    refund.payment_reference = clean_ref
    refund.paid_on = body.paid_on
    refund.payment_mode = body.payment_mode.value if body.payment_mode else None
    refund.paid_at = now
    refund.paid_by_user_id = current_user.id
    refund.updated_at = now

    if refund.student_issue_at and not refund.student_issue_resolved_at:
        refund.student_issue_resolved_at = now

    audit = AuditLog(
        user_id=current_user.id,
        action="MARK_REFUND_PROCESSED",
        entity_type="clearance_requests",
        entity_id=request_id,
        details={
            "payment_reference": clean_ref,
            "paid_on": str(body.paid_on),
            "payment_mode": body.payment_mode.value if body.payment_mode else None,
        },
        created_at=now,
    )
    db.add(audit)
    notify_refund_processed(db, req, clean_ref, str(body.paid_on))
    db.commit()

    return MarkRefundProcessedResponse(
        request_id=request_id,
        payment_reference=clean_ref,
        refund_status=refund.status.value,
        paid_on=refund.paid_on,
        payment_mode=_payment_mode_str(refund.payment_mode),
        updated_at=refund.updated_at,
    )


@router.post(
    "/requests/{request_id}/mark-failed",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    operation_id="mark_refund_failed",
    summary="Mark Refund Payment as Failed",
    description=(
        "Marks a verified or processed refund disbursement as failed (e.g. invalid bank account or RTGS bounce). "
        "Reason is mandatory. Retains previous payment reference in audit log. Closes open student issue if any."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Missing or empty failure reason"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-registrar roles"},
        404: {"model": ErrorResponse, "description": "Clearance request or refund record not found"},
        409: {"model": ErrorResponse, "description": "Refund not in VERIFIED or PROCESSED status"},
    },
)
def mark_refund_failed(
    request_id: int,
    body: MarkRefundFailedRequest,
    db: SessionDep,
    current_user: User = Depends(require_registrar),
) -> MessageResponse:
    clean_reason = body.reason.strip() if body.reason else ""
    if not clean_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failure reason is mandatory.",
        )
    if len(clean_reason) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failure reason cannot exceed 500 characters.",
        )

    req = db.execute(
        select(ClearanceRequest).where(ClearanceRequest.id == request_id).with_for_update()
    ).scalars().first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clearance request not found")

    refund = db.execute(
        select(Refund).where(Refund.request_id == req.id).with_for_update()
    ).scalars().first()
    if not refund:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund record not found")

    if refund.status not in (RefundStatus.VERIFIED, RefundStatus.PROCESSED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Refund payment can only be marked failed from VERIFIED or PROCESSED status. Current status: {refund.status.value}",
        )

    now = datetime.now(timezone.utc)
    previous_ref = refund.payment_reference
    refund.status = RefundStatus.PAYMENT_FAILED
    refund.failure_reason = clean_reason
    refund.failed_at = now
    refund.updated_at = now
    if refund.student_issue_at and not refund.student_issue_resolved_at:
        refund.student_issue_resolved_at = now

    audit = AuditLog(
        user_id=current_user.id,
        action="MARK_REFUND_FAILED",
        entity_type="clearance_requests",
        entity_id=req.id,
        details={
            "failure_reason": clean_reason,
            "previous_payment_reference": previous_ref,
        },
        created_at=now,
    )
    db.add(audit)
    notify_refund_failed(db, req, clean_reason)
    db.commit()

    return MessageResponse(detail=f"Refund payment marked as failed: {clean_reason}")


@router.post(
    "/requests/{request_id}/retry-payment",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    operation_id="retry_refund_payment",
    summary="Retry Failed Refund Payment",
    description="Transitions a refund in PAYMENT_FAILED status back to VERIFIED, enabling re-disbursement.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-registrar roles"},
        404: {"model": ErrorResponse, "description": "Clearance request or refund record not found"},
        409: {"model": ErrorResponse, "description": "Refund not in PAYMENT_FAILED status"},
    },
)
def retry_refund_payment(
    request_id: int,
    db: SessionDep,
    current_user: User = Depends(require_registrar),
) -> MessageResponse:
    req = db.execute(
        select(ClearanceRequest).where(ClearanceRequest.id == request_id).with_for_update()
    ).scalars().first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clearance request not found")

    refund = db.execute(
        select(Refund).where(Refund.request_id == req.id).with_for_update()
    ).scalars().first()
    if not refund:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund record not found")

    if refund.status != RefundStatus.PAYMENT_FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Payment retry is only allowed when refund is PAYMENT_FAILED. Current status: {refund.status.value}",
        )

    now = datetime.now(timezone.utc)
    refund.status = RefundStatus.VERIFIED
    refund.failure_reason = None
    refund.failed_at = None
    refund.updated_at = now
    if refund.student_issue_at and not refund.student_issue_resolved_at:
        refund.student_issue_resolved_at = now

    audit = AuditLog(
        user_id=current_user.id,
        action="RETRY_REFUND_PAYMENT",
        entity_type="clearance_requests",
        entity_id=req.id,
        details={"refund_id": refund.id},
        created_at=now,
    )
    db.add(audit)
    db.commit()

    return MessageResponse(detail="Refund status reset to VERIFIED for re-disbursement.")


@router.post(
    "/requests/{request_id}/resolve-issue",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    operation_id="resolve_student_refund_issue",
    summary="Resolve Student Refund Issue",
    description="Closes an open student issue on a refund by setting student_issue_resolved_at to current timestamp.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden for non-registrar roles"},
        404: {"model": ErrorResponse, "description": "Clearance request or refund record not found"},
        409: {"model": ErrorResponse, "description": "No open student issue to resolve"},
    },
)
def resolve_student_issue(
    request_id: int,
    db: SessionDep,
    body: ResolveStudentIssueRequest | None = None,
    current_user: User = Depends(require_registrar),
) -> MessageResponse:
    req = db.execute(
        select(ClearanceRequest).where(ClearanceRequest.id == request_id).with_for_update()
    ).scalars().first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clearance request not found")

    refund = db.execute(
        select(Refund).where(Refund.request_id == req.id).with_for_update()
    ).scalars().first()
    if not refund:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund record not found")

    if not refund.student_issue_at or refund.student_issue_resolved_at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No open student issue found on this refund record.",
        )

    now = datetime.now(timezone.utc)
    refund.student_issue_resolved_at = now
    refund.updated_at = now

    clean_note = body.note.strip() if (body and body.note) else None

    audit = AuditLog(
        user_id=current_user.id,
        action="RESOLVE_STUDENT_ISSUE",
        entity_type="clearance_requests",
        entity_id=req.id,
        details={"resolution_note": clean_note},
        created_at=now,
    )
    db.add(audit)
    db.commit()

    return MessageResponse(detail="Student refund issue resolved successfully.")


@router.get(
    "/requests/{request_id}",
    response_model=RegistrarRequestDetailResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_registrar_request_detail",
    summary="Get Clearance Request Details for Registrar",
    description=(
        "Returns full request details including student provenance (who uploaded/added to roster), "
        "masked bank account details, and full refund timeline."
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
            joinedload(ClearanceRequest.refund).joinedload(Refund.verified_by_user),
            joinedload(ClearanceRequest.refund).joinedload(Refund.paid_by_user),
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

    ref = req.refund
    deposit_amt = ref.deposit_amount if ref else (r.security_deposit_amount if r else Decimal("0.00"))
    deductions = ref.deductions if ref else None
    final_amt = ref.final_amount if ref else None
    refund_st = ref.status.value if ref else "N/A"

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

    verified_by_name = None
    if ref and ref.verified_by_user:
        verified_by_name = ref.verified_by_user.full_name or ref.verified_by_user.email

    paid_by_name = None
    if ref and ref.paid_by_user:
        paid_by_name = ref.paid_by_user.full_name or ref.paid_by_user.email

    ledger_amt = r.security_deposit_amount if (r and r.security_deposit_amount and r.security_deposit_amount > 0) else None

    return RegistrarRequestDetailResponse(
        request_id=req.id,
        roster_id=req.roster_id,
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
        ledger_deposit_amount=ledger_amt,
        deductions=deductions,
        final_amount=final_amt,
        refund_status=refund_st,
        approvals=approval_items,
        # Complete timeline fields
        verified_at=ref.verified_at if ref else None,
        verified_by_name=verified_by_name,
        accounts_note=ref.accounts_note if ref else None,
        paid_at=ref.paid_at if ref else None,
        paid_by_name=paid_by_name,
        paid_on=ref.paid_on if ref else None,
        payment_mode=_payment_mode_str(ref.payment_mode) if ref else None,
        payment_reference=ref.payment_reference if ref else None,
        failure_reason=ref.failure_reason if ref else None,
        failed_at=ref.failed_at if ref else None,
        student_confirmed_at=ref.student_confirmed_at if ref else None,
        student_issue_note=ref.student_issue_note if ref else None,
        student_issue_at=ref.student_issue_at if ref else None,
        student_issue_resolved_at=ref.student_issue_resolved_at if ref else None,
    )


@router.get(
    "/refunds/export.csv",
    status_code=status.HTTP_200_OK,
    operation_id="export_refunds_csv",
    summary="Export Refunds to CSV",
    description=(
        "Exports a CSV table of refunds filtered by queue tab (TO_VERIFY, TO_PAY, PAID, FAILED, ALL). "
        "Strictly includes only masked bank account numbers (e.g. '********1234') and never plain accounts. "
        "Logs an audit entry and requires registrar_accounts role."
    ),
    responses={
        200: {"content": {"text/csv": {}}, "description": "CSV export file"},
        400: {"model": ErrorResponse, "description": "Invalid tab filter"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-registrar roles"},
    },
)
def export_refunds_csv(
    db: SessionDep,
    current_user: User = Depends(require_registrar),
    tab: str = Query("ALL", description="Filter tab: TO_VERIFY, TO_PAY, PAID, FAILED, ALL"),
) -> Response:
    clean_tab = tab.strip().upper()
    if clean_tab not in ("TO_VERIFY", "TO_PAY", "PAID", "FAILED", "ALL"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tab '{tab}'. Allowed values are TO_VERIFY, TO_PAY, PAID, FAILED, ALL.",
        )

    base_query = (
        select(ClearanceRequest)
        .join(Refund, ClearanceRequest.id == Refund.request_id)
        .options(
            joinedload(ClearanceRequest.roster_entry).joinedload(StudentRoster.programme),
            joinedload(ClearanceRequest.roster_entry).joinedload(StudentRoster.bank_detail),
            joinedload(ClearanceRequest.refund),
        )
    )

    if clean_tab == "TO_VERIFY":
        tab_filter = and_(
            ClearanceRequest.status == ClearanceStatus.CLEARED,
            Refund.status == RefundStatus.PENDING_VERIFICATION,
        )
    elif clean_tab == "TO_PAY":
        tab_filter = and_(
            ClearanceRequest.status == ClearanceStatus.REFUND_VERIFIED,
            Refund.status == RefundStatus.VERIFIED,
        )
    elif clean_tab == "PAID":
        tab_filter = and_(
            ClearanceRequest.status == ClearanceStatus.REFUND_VERIFIED,
            Refund.status == RefundStatus.PROCESSED,
        )
    elif clean_tab == "FAILED":
        tab_filter = and_(
            ClearanceRequest.status == ClearanceStatus.REFUND_VERIFIED,
            Refund.status == RefundStatus.PAYMENT_FAILED,
        )
    else:  # ALL
        tab_filter = ClearanceRequest.status.in_([ClearanceStatus.CLEARED, ClearanceStatus.REFUND_VERIFIED])

    requests = db.execute(base_query.where(tab_filter).order_by(ClearanceRequest.id.asc())).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "registration_number",
        "student_name",
        "programme",
        "deposit_amount",
        "deductions",
        "final_amount",
        "refund_status",
        "payment_reference",
        "paid_on",
        "payment_mode",
        "account_number_masked",
    ])

    for req in requests:
        r = req.roster_entry
        b = r.bank_detail if r else None
        ref = req.refund
        prog_name = r.programme.name if (r and r.programme) else "N/A"
        masked_acc = b.masked_account_number if b else "N/A"

        writer.writerow([
            r.registration_number if r else "N/A",
            r.name if r else "N/A",
            prog_name,
            str(ref.deposit_amount) if ref else "0.00",
            str(ref.deductions) if (ref and ref.deductions is not None) else "",
            str(ref.final_amount) if (ref and ref.final_amount is not None) else "",
            ref.status.value if ref else "N/A",
            ref.payment_reference or "" if ref else "",
            str(ref.paid_on) if (ref and ref.paid_on) else "",
            _payment_mode_str(ref.payment_mode) or "" if ref else "",
            masked_acc,
        ])

    csv_data = output.getvalue()

    now = datetime.now(timezone.utc)
    audit = AuditLog(
        user_id=current_user.id,
        action="EXPORT_REFUNDS_CSV",
        entity_type="refunds",
        entity_id=None,
        details={"tab": clean_tab, "count": len(requests)},
        created_at=now,
    )
    db.add(audit)
    db.commit()

    now_str = now.strftime("%Y%m%d_%H%M%S")
    filename = f"refunds_export_{clean_tab.lower()}_{now_str}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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


# ----------------------------------------------------------------------
# Deposit Ledger Endpoints
# ----------------------------------------------------------------------

@router.get(
    "/deposit-ledger/template.csv",
    status_code=status.HTTP_200_OK,
    operation_id="get_deposit_ledger_template",
    summary="Download Deposit Ledger CSV Template",
    description="Downloads a CSV template formatted for security deposit ledger upload with sample data.",
    responses={
        200: {"content": {"text/csv": {}}, "description": "Deposit ledger CSV template"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-registrar roles"},
    },
)
def get_deposit_ledger_template(
    current_user: User = Depends(require_registrar),
) -> Response:
    content = "registration_number,deposit_amount\r\n2026SVSU0001,5000.00\r\n"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="deposit_ledger_template.csv"'},
    )


@router.post(
    "/deposit-ledger/upload",
    response_model=DepositLedgerUploadResponse,
    status_code=status.HTTP_200_OK,
    operation_id="upload_deposit_ledger_csv",
    summary="Bulk Upload Security Deposit Ledger from CSV",
    description=(
        "Uploads a CSV to set or update student_roster.security_deposit_amount (the ledger value) for students "
        "whose refund has not yet been verified or processed. Supports dry-run simulation."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid CSV file or format"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-registrar roles"},
    },
)
async def upload_deposit_ledger_csv(
    db: SessionDep,
    file: UploadFile = File(..., description="CSV file with registration_number and deposit_amount"),
    dry_run: bool = Query(False, description="Simulate upload without persisting changes"),
    current_user: User = Depends(require_registrar),
) -> DepositLedgerUploadResponse:
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to decode CSV file as text")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded CSV file is empty or missing header row")

    fieldnames_map = {f.strip().lower(): f for f in reader.fieldnames if f}
    if "registration_number" not in fieldnames_map or "deposit_amount" not in fieldnames_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV header must contain 'registration_number' and 'deposit_amount' columns",
        )

    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV file contains no data rows")

    row_reports: list[DepositLedgerRowReport] = []
    updated_count = 0
    unchanged_count = 0
    rejected_count = 0

    for idx, row in enumerate(rows, start=1):
        reg_num = (row.get(fieldnames_map["registration_number"]) or "").strip()
        dep_str = (row.get(fieldnames_map["deposit_amount"]) or "").strip()

        if not reg_num:
            row_reports.append(DepositLedgerRowReport(
                row_number=idx,
                registration_number="UNKNOWN",
                status="rejected",
                reason="Registration number cannot be empty",
            ))
            rejected_count += 1
            continue

        try:
            parsed_amt = Decimal(dep_str)
        except Exception:
            row_reports.append(DepositLedgerRowReport(
                row_number=idx,
                registration_number=reg_num,
                status="rejected",
                reason=f"Invalid deposit amount '{dep_str}'. Must be a valid decimal number.",
            ))
            rejected_count += 1
            continue

        if parsed_amt < Decimal("0.00"):
            row_reports.append(DepositLedgerRowReport(
                row_number=idx,
                registration_number=reg_num,
                status="rejected",
                reason="Deposit amount cannot be negative",
            ))
            rejected_count += 1
            continue

        if parsed_amt > Decimal("99999999.99"):
            row_reports.append(DepositLedgerRowReport(
                row_number=idx,
                registration_number=reg_num,
                status="rejected",
                reason="Deposit amount exceeds maximum limit of 99,999,999.99",
            ))
            rejected_count += 1
            continue

        if parsed_amt.as_tuple().exponent < -2:
            row_reports.append(DepositLedgerRowReport(
                row_number=idx,
                registration_number=reg_num,
                status="rejected",
                reason="Deposit amount cannot have more than 2 decimal places",
            ))
            rejected_count += 1
            continue

        student = db.scalar(select(StudentRoster).where(StudentRoster.registration_number == reg_num))
        if not student:
            row_reports.append(DepositLedgerRowReport(
                row_number=idx,
                registration_number=reg_num,
                status="rejected",
                reason="Student registration number not found in roster",
            ))
            rejected_count += 1
            continue

        verified_refund = db.scalar(
            select(Refund)
            .join(ClearanceRequest, Refund.request_id == ClearanceRequest.id)
            .where(
                ClearanceRequest.roster_id == student.id,
                Refund.status.in_([RefundStatus.VERIFIED, RefundStatus.PROCESSED]),
            )
        )
        if verified_refund:
            row_reports.append(DepositLedgerRowReport(
                row_number=idx,
                registration_number=reg_num,
                status="rejected",
                old_amount=student.security_deposit_amount,
                reason=f"Cannot update deposit ledger: student refund is already {verified_refund.status.value}",
            ))
            rejected_count += 1
            continue

        old_val = student.security_deposit_amount or Decimal("0.00")
        if old_val == parsed_amt:
            row_reports.append(DepositLedgerRowReport(
                row_number=idx,
                registration_number=reg_num,
                status="unchanged",
                old_amount=old_val,
                new_amount=parsed_amt,
                reason="Deposit amount matches existing ledger value",
            ))
            unchanged_count += 1
        else:
            row_reports.append(DepositLedgerRowReport(
                row_number=idx,
                registration_number=reg_num,
                status="updated",
                old_amount=old_val,
                new_amount=parsed_amt,
            ))
            updated_count += 1
            if not dry_run:
                student.security_deposit_amount = parsed_amt
                student.updated_by_user_id = current_user.id

    now = datetime.now(timezone.utc)
    audit = AuditLog(
        user_id=current_user.id,
        action="DEPOSIT_LEDGER_UPLOAD",
        entity_type="deposit_ledger",
        entity_id=None,
        details={
            "dry_run": dry_run,
            "filename": file.filename,
            "total_rows": len(rows),
            "updated_count": updated_count,
            "unchanged_count": unchanged_count,
            "rejected_count": rejected_count,
        },
        created_at=now,
    )
    db.add(audit)
    if not dry_run:
        db.commit()

    return DepositLedgerUploadResponse(
        dry_run=dry_run,
        total_rows=len(rows),
        updated_count=updated_count,
        unchanged_count=unchanged_count,
        rejected_count=rejected_count,
        rows=row_reports,
    )


@router.patch(
    "/roster/{id}/deposit",
    response_model=UpdateRosterDepositResponse,
    status_code=status.HTTP_200_OK,
    operation_id="update_roster_student_deposit",
    summary="Update Single Student Security Deposit Ledger Amount",
    description="Updates the security deposit ledger amount for a student in the roster whose refund is not yet verified or processed.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid deposit amount"},
        403: {"model": ErrorResponse, "description": "Forbidden for non-registrar roles"},
        404: {"model": ErrorResponse, "description": "Student roster entry not found"},
        409: {"model": ErrorResponse, "description": "Student refund is already verified or processed"},
    },
)
def update_roster_student_deposit(
    id: int,
    body: UpdateRosterDepositRequest,
    db: SessionDep,
    current_user: User = Depends(require_registrar),
) -> UpdateRosterDepositResponse:
    student = db.scalar(select(StudentRoster).where(StudentRoster.id == id))
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student roster entry with id {id} not found.",
        )

    if body.deposit_amount.as_tuple().exponent < -2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deposit amount cannot have more than 2 decimal places.",
        )

    verified_refund = db.scalar(
        select(Refund)
        .join(ClearanceRequest, Refund.request_id == ClearanceRequest.id)
        .where(
            ClearanceRequest.roster_id == student.id,
            Refund.status.in_([RefundStatus.VERIFIED, RefundStatus.PROCESSED]),
        )
    )
    if verified_refund:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot update deposit ledger: student refund is already {verified_refund.status.value}.",
        )

    old_amount = student.security_deposit_amount
    new_deposit = body.deposit_amount.quantize(Decimal("0.01"))
    student.security_deposit_amount = new_deposit
    student.updated_by_user_id = current_user.id

    now = datetime.now(timezone.utc)
    audit = AuditLog(
        user_id=current_user.id,
        action="UPDATE_ROSTER_DEPOSIT",
        entity_type="student_roster",
        entity_id=student.id,
        details={
            "registration_number": student.registration_number,
            "old_amount": f"{old_amount:.2f}" if old_amount is not None else None,
            "new_amount": f"{new_deposit:.2f}",
        },
        created_at=now,
    )
    db.add(audit)
    db.commit()

    return UpdateRosterDepositResponse(
        id=student.id,
        registration_number=student.registration_number,
        name=student.name,
        security_deposit_amount=student.security_deposit_amount,
        message="Deposit ledger amount updated successfully.",
    )

