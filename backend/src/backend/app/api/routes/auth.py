"""Authentication endpoints: student signup with OTP, OAuth2 password login, profile, and password change."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from google.oauth2 import id_token
import google.auth.transport.requests

from backend.app.api.deps import SessionDep, CurrentUserAnyDep
from backend.app.core.config import settings
from backend.app.core.rate_limit import (
    get_client_ip,
    check_rate_limit,
    record_attempt,
    clear_rate_limit,
)
from backend.app.core.security import (
    hash_password,
    verify_password,
    generate_otp,
    hash_otp,
    verify_otp,
    create_access_token,
    normalize_email,
)
from backend.app.models.user import User, UserRole
from backend.app.models.roster import StudentRoster
from backend.app.models.otp import SignupOTP
from backend.app.models.audit import AuditLog
from backend.app.models.bank import mask_account_number
from backend.app.schemas.auth import (
    SignupOTPRequest,
    SignupOTPResponse,
    SignupVerifyRequest,
    ChangePasswordRequest,
    TokenResponse,
    GoogleAuthRequest,
    AuthConfigResponse,
    UserMeResponse,
    RosterSummary,
)
from backend.app.schemas.common import ErrorResponse, DepartmentBrief
from backend.app.services.email import send_otp_email, send_outbox_email_by_id
from backend.app.services.workflow import get_user_departments


router = APIRouter(prefix="/auth", tags=["Auth"])

GENERIC_OTP_MESSAGE = "If the details match our records, a code has been sent to your university email."


@router.get(
    "/config",
    response_model=AuthConfigResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_auth_config",
    summary="Get Authentication Configuration",
    description="Public configuration metadata for frontend authentication flows, including Google OAuth2 and OTP status.",
)
def get_auth_config() -> AuthConfigResponse:
    allowed_hint = settings.google_allowed_domain_list[0] if settings.google_allowed_domain_list else None
    return AuthConfigResponse(
        google_enabled=settings.google_enabled,
        google_client_id=settings.GOOGLE_CLIENT_ID if settings.google_enabled else None,
        allowed_domain_hint=allowed_hint,
        otp_signup_enabled=settings.AUTH_OTP_SIGNUP_ENABLED,
    )


@router.post(
    "/signup/request-otp",
    response_model=SignupOTPResponse,
    status_code=status.HTTP_200_OK,
    operation_id="request_signup_otp",
    summary="Request Student Signup OTP",
    description=(
        "Initiates student self-registration. Validates that the registration number exists "
        "in the student roster, the provided email matches the roster email, the domain is allowed, "
        "and that the student has not already created an account. Enforces rate limits and returns "
        "a generic message to prevent account enumeration."
    ),
    responses={
        429: {"model": ErrorResponse, "description": "Too many OTP requests"},
    },
)
def request_signup_otp(
    body: SignupOTPRequest,
    db: SessionDep,
    request: Request,
    background_tasks: BackgroundTasks,
) -> SignupOTPResponse:
    if not settings.AUTH_OTP_SIGNUP_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "OTP_SIGNUP_DISABLED",
                "message": "Sign in with your university Google account instead.",
            },
        )

    reg_num = body.registration_number.strip().upper()
    email_clean = normalize_email(body.email)
    client_ip = get_client_ip(request)

    # 1. Rate Limiting: max 3/email/hr, 3/reg#/hr, 5/IP/hr
    check_rate_limit(db, f"otp_req:email:{email_clean}", max_attempts=3)
    check_rate_limit(db, f"otp_req:reg:{reg_num}", max_attempts=3)
    check_rate_limit(db, f"otp_req:ip:{client_ip}", max_attempts=5)

    record_attempt(db, f"otp_req:email:{email_clean}", window_seconds=3600)
    record_attempt(db, f"otp_req:reg:{reg_num}", window_seconds=3600)
    record_attempt(db, f"otp_req:ip:{client_ip}", window_seconds=3600)

    # 2. Domain check
    domain = email_clean.split("@")[-1] if "@" in email_clean else ""
    if domain not in settings.allowed_email_domain_list:
        return SignupOTPResponse(detail=GENERIC_OTP_MESSAGE, dev_otp=None)

    # 3. Registration number in student_roster
    roster = db.execute(
        select(StudentRoster).where(func.upper(StudentRoster.registration_number) == reg_num)
    ).scalar_one_or_none()

    if not roster:
        return SignupOTPResponse(detail=GENERIC_OTP_MESSAGE, dev_otp=None)

    # 4. Email matches roster email
    if normalize_email(roster.email) != email_clean:
        return SignupOTPResponse(detail=GENERIC_OTP_MESSAGE, dev_otp=None)

    # 5. Check if user account already exists
    existing_user = db.execute(
        select(User).where(
            (func.lower(User.email) == email_clean) | (User.roster_id == roster.id)
        )
    ).scalar_one_or_none()

    if existing_user:
        return SignupOTPResponse(detail=GENERIC_OTP_MESSAGE, dev_otp=None)

    # 6. Generate 6-digit OTP, store hash with 10-minute expiry
    plain_otp = generate_otp(6)
    code_hash = hash_otp(plain_otp)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=10)

    otp_record = SignupOTP(
        email=email_clean,
        registration_number=roster.registration_number,
        code_hash=code_hash,
        expires_at=expires_at,
        attempts=0,
        consumed_at=None,
        created_at=now,
    )
    db.add(otp_record)

    # Queue in email_outbox inside same transaction
    outbox_item = send_otp_email(
        to_email=email_clean,
        otp_code=plain_otp,
        registration_number=roster.registration_number,
        session=db,
    )
    db.commit()

    # Immediate background delivery attempt
    background_tasks.add_task(send_outbox_email_by_id, outbox_item.id)

    dev_otp = plain_otp if (settings.APP_ENV == "development" and settings.DEV_RETURN_OTP) else None
    return SignupOTPResponse(detail=GENERIC_OTP_MESSAGE, dev_otp=dev_otp)


@router.post(
    "/signup/verify",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="verify_signup_otp",
    summary="Verify OTP and Create Student Account",
    description=(
        "Verifies the received OTP, enforces maximum 5 attempts, validates password length (min 10 chars), "
        "creates the User record with student role linked to the roster entry, and returns an access token."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid, expired verification code or password too short"},
        409: {"model": ErrorResponse, "description": "Account already created for this registration number"},
    },
)
def verify_signup_otp(body: SignupVerifyRequest, db: SessionDep) -> TokenResponse:
    if not settings.AUTH_OTP_SIGNUP_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "OTP_SIGNUP_DISABLED",
                "message": "Sign in with your university Google account instead.",
            },
        )

    reg_num = body.registration_number.strip().upper()
    now = datetime.now(timezone.utc)

    if len(body.password) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 10 characters long.",
        )

    # Find the latest unconsumed OTP for this registration number
    otp_record = db.execute(
        select(SignupOTP)
        .where(
            func.upper(SignupOTP.registration_number) == reg_num,
            SignupOTP.consumed_at.is_(None),
        )
        .order_by(SignupOTP.id.desc())
    ).scalars().first()

    if not otp_record or otp_record.expires_at < now or otp_record.attempts >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code. Please request a new code.",
        )

    # Verify code
    is_valid = verify_otp(body.otp.strip(), otp_record.code_hash)
    if not is_valid:
        otp_record.attempts += 1
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code. Please request a new code.",
        )

    # Roster lookup
    roster = db.execute(
        select(StudentRoster).where(func.upper(StudentRoster.registration_number) == reg_num)
    ).scalar_one_or_none()

    if not roster:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student roster record not found.",
        )

    roster_email_clean = normalize_email(roster.email)

    # Check for duplicate user
    existing_user = db.execute(
        select(User).where(
            (func.lower(User.email) == roster_email_clean) | (User.roster_id == roster.id)
        )
    ).scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already exists for this student. Please log in.",
        )

    # Mark OTP consumed
    otp_record.consumed_at = now

    # Create student User
    user = User(
        email=roster_email_clean,
        full_name=roster.name,
        password_hash=hash_password(body.password),
        role=UserRole.student,
        department_id=None,
        roster_id=roster.id,
        is_active=True,
        must_change_password=False,
        created_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        must_change_password=False,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    operation_id="login_access_token",
    summary="User Login (OAuth2 Password Grant)",
    description=(
        "Authenticates university students, department officers, HoDs, and administrators. "
        "Enforces persistent rate limiting of 5 failed attempts per 15 minutes per email and IP address. "
        "Returns a JWT Bearer access token and indicates if password change is required."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Incorrect email or password, or account inactive"},
        429: {"model": ErrorResponse, "description": "Too many failed login attempts"},
    },
)
def login_access_token(
    db: SessionDep,
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> TokenResponse:
    email_clean = normalize_email(form_data.username)
    client_ip = get_client_ip(request)

    email_key = f"login_fail:email:{email_clean}"
    ip_key = f"login_fail:ip:{client_ip}"

    # Check 15-minute lockout (max 5 failed logins)
    check_rate_limit(db, email_key, max_attempts=5)
    check_rate_limit(db, ip_key, max_attempts=5)

    user = db.execute(
        select(User).where(func.lower(User.email) == email_clean)
    ).scalar_one_or_none()

    if (
        not user
        or not user.password_hash
        or not verify_password(form_data.password, user.password_hash)
        or (user.role == UserRole.student and not settings.AUTH_PASSWORD_LOGIN_FOR_STUDENTS)
    ):
        record_attempt(db, email_key, window_seconds=15 * 60)
        record_attempt(db, ip_key, window_seconds=15 * 60)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Clear rate limit counter for this email upon successful authentication
    clear_rate_limit(db, email_key)

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        must_change_password=user.must_change_password,
    )


@router.post(
    "/google",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    operation_id="google_auth_login",
    summary="Google OAuth2 Single Sign-On",
    description=(
        "Authenticates university students, staff, and administrators via Google OAuth2 ID token credential. "
        "Verifies cryptographic signature, domain restriction, and student roster eligibility on first login. "
        "Enforces persistent rate limits on IP and failed attempts per email."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Invalid, expired, or unauthorized Google credential"},
        403: {"model": ErrorResponse, "description": "Account disabled, unregistered student, or sub mismatch"},
        429: {"model": ErrorResponse, "description": "Too many failed Google authentication attempts"},
    },
)
def google_auth_login(
    body: GoogleAuthRequest,
    db: SessionDep,
    request: Request,
) -> TokenResponse:
    client_ip = get_client_ip(request)
    ip_key = f"google_login:ip:{client_ip}"

    # Rate limiting: max 20 attempts per IP per 15 minutes
    check_rate_limit(db, ip_key, max_attempts=20)
    record_attempt(db, ip_key, window_seconds=15 * 60)

    # 1. Verify Google OAuth2 ID token
    try:
        req = google.auth.transport.requests.Request()
        payload = id_token.verify_oauth2_token(
            body.credential,
            req,
            settings.GOOGLE_CLIENT_ID or None,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Google authentication credential.",
        )

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential payload structure.",
        )

    # 2. Email verification flag
    if payload.get("email_verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account email is not verified.",
        )

    raw_email = payload.get("email")
    if not raw_email or not isinstance(raw_email, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google credential does not contain an email address.",
        )

    email_clean = normalize_email(raw_email)
    email_key = f"google_login_fail:email:{email_clean}"

    # Rate limiting: max 10 failed attempts per email per 15 minutes
    check_rate_limit(db, email_key, max_attempts=10)

    # 3. Domain and 'hd' claim verification
    email_domain = email_clean.split("@")[-1] if "@" in email_clean else ""
    hd_claim = str(payload.get("hd") or "").lower().strip()

    if not hd_claim or email_domain not in settings.google_allowed_domain_list or hd_claim != email_domain:
        record_attempt(db, email_key, window_seconds=15 * 60)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or unauthorized university Google email domain.",
        )

    sub = str(payload.get("sub") or "").strip()
    if not sub:
        record_attempt(db, email_key, window_seconds=15 * 60)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential identifier.",
        )

    # 4. User lookup: by google_sub first, then email
    user = db.execute(
        select(User).where(User.google_sub == sub)
    ).scalar_one_or_none()

    if not user:
        user = db.execute(
            select(User).where(func.lower(User.email) == email_clean)
        ).scalar_one_or_none()

        if user:
            if not user.google_sub:
                user.google_sub = sub
                db.flush()
            elif user.google_sub != sub:
                record_attempt(db, email_key, window_seconds=15 * 60)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"code": "SUB_MISMATCH", "message": "Google account ID does not match this user record."},
                )

    # 5. If user does not exist: query student_roster
    if not user:
        roster = db.execute(
            select(StudentRoster).where(func.lower(StudentRoster.email) == email_clean)
        ).scalar_one_or_none()

        if not roster:
            record_attempt(db, email_key, window_seconds=15 * 60)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "NOT_ELIGIBLE",
                    "message": "Your account is not in the student list. Please contact your department office.",
                },
            )

        existing_roster_user = db.execute(
            select(User).where(User.roster_id == roster.id)
        ).scalar_one_or_none()
        if existing_roster_user:
            record_attempt(db, email_key, window_seconds=15 * 60)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ACCOUNT_EXISTS", "message": "User account already exists for this student."},
            )

        now = datetime.now(timezone.utc)
        new_user = User(
            email=email_clean,
            full_name=roster.name,
            password_hash=None,
            role=UserRole.student,
            department_id=None,
            roster_id=roster.id,
            is_active=True,
            must_change_password=False,
            google_sub=sub,
            last_login_at=now,
            created_at=now,
        )
        db.add(new_user)
        try:
            db.flush()
            user = new_user
        except IntegrityError:
            db.rollback()
            # Concurrency race: another request just created this user; re-read
            user = db.execute(
                select(User).where(
                    (User.google_sub == sub) | (func.lower(User.email) == email_clean) | (User.roster_id == roster.id)
                )
            ).scalar_one_or_none()
            if not user:
                raise

        # Write audit log for first Google login
        audit = AuditLog(
            user_id=user.id,
            action="google_first_login",
            entity_type="User",
            entity_id=user.id,
            details={
                "email": email_clean,
                "registration_number": roster.registration_number,
            },
            created_at=now,
        )
        db.add(audit)
        db.commit()
        db.refresh(user)

    # 6. Check inactive user
    if not user.is_active:
        record_attempt(db, email_key, window_seconds=15 * 60)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCOUNT_DISABLED", "message": "User account is disabled."},
        )

    # 7. Success: update last_login_at, clear rate limit, issue token
    user.last_login_at = datetime.now(timezone.utc)
    clear_rate_limit(db, email_key)
    db.commit()

    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        must_change_password=False,
    )


@router.get(
    "/me",
    response_model=UserMeResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_my_profile",
    summary="Get Current User Profile",
    description=(
        "Returns profile details for the authenticated user. Accessible even if password change is required. "
        "If the user is a student, includes their academic roster summary and masked bank details."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Unauthenticated or invalid token"},
    },
)
def get_my_profile(
    current_user: CurrentUserAnyDep,
    db: SessionDep,
) -> UserMeResponse:
    dept_name = current_user.department.name if current_user.department else None

    depts = get_user_departments(current_user, db)
    dept_briefs = [
        DepartmentBrief(id=d.id, name=d.name, kind=d.kind.value)
        for d in depts
    ]

    roster_summary = None
    if current_user.role == UserRole.student and current_user.roster_entry:
        r = current_user.roster_entry
        prog_name = r.programme.name if r.programme else ""
        dept_title = r.programme.department.name if (r.programme and r.programme.department) else ""
        masked_acc = None
        if r.bank_detail and r.bank_detail.account_number:
            masked_acc = mask_account_number(r.bank_detail.account_number)

        roster_summary = RosterSummary(
            name=r.name,
            registration_number=r.registration_number,
            programme=prog_name,
            department=dept_title,
            is_hosteller=r.is_hosteller,
            security_deposit_amount=r.security_deposit_amount,
            masked_bank_account=masked_acc,
        )

    return UserMeResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        department_id=current_user.department_id,
        department_name=dept_name,
        departments=dept_briefs,
        must_change_password=current_user.must_change_password,
        roster=roster_summary,
    )



@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    operation_id="change_user_password",
    summary="Change User Password",
    description=(
        "Updates user password. Required when must_change_password flag is True (e.g. for initial admin-created accounts). "
        "Enforces current password verification, minimum 10 characters length, and disallows reusing the current password."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Incorrect current password or new password validation failure"},
        401: {"model": ErrorResponse, "description": "Unauthenticated"},
    },
)
def change_user_password(
    body: ChangePasswordRequest,
    db: SessionDep,
    current_user: CurrentUserAnyDep,
) -> dict:
    if not current_user.password_hash or not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password.",
        )

    if len(body.new_password) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 10 characters long.",
        )

    if body.new_password == body.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password.",
        )

    now = datetime.now(timezone.utc)
    current_user.password_hash = hash_password(body.new_password)
    current_user.must_change_password = False

    audit = AuditLog(
        user_id=current_user.id,
        action="PASSWORD_CHANGED",
        entity_type="User",
        entity_id=current_user.id,
        details={"email": current_user.email},
        created_at=now,
    )
    db.add(audit)
    db.commit()

    return {"detail": "Password changed successfully."}
