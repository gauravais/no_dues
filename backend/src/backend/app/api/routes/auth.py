"""Authentication endpoints: student signup with OTP, OAuth2 password login, and current user profile."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, func

from backend.app.api.deps import SessionDep, CurrentUserDep
from backend.app.core.config import settings
from backend.app.core.security import (
    hash_password,
    verify_password,
    generate_otp,
    hash_otp,
    verify_otp,
    create_access_token,
)
from backend.app.models.user import User, UserRole
from backend.app.models.roster import StudentRoster
from backend.app.models.otp import SignupOTP
from backend.app.models.bank import mask_account_number
from backend.app.schemas.auth import (
    SignupOTPRequest,
    SignupOTPResponse,
    SignupVerifyRequest,
    TokenResponse,
    UserMeResponse,
    RosterSummary,
)
from backend.app.schemas.common import ErrorResponse
from backend.app.services.email import send_otp_email

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/signup/request-otp",
    response_model=SignupOTPResponse,
    status_code=status.HTTP_200_OK,
    operation_id="request_signup_otp",
    summary="Request Student Signup OTP",
    description=(
        "Initiates student self-registration. Validates that the registration number exists "
        "in the student roster, the provided email matches the roster email, the domain is allowed, "
        "and that the student has not already created an account. Dispatches a 6-digit OTP."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid registration number, mismatched email, or disallowed domain"},
        409: {"model": ErrorResponse, "description": "User account already exists for this student"},
    },
)
def request_signup_otp(body: SignupOTPRequest, db: SessionDep) -> SignupOTPResponse:
    reg_num = body.registration_number.strip().upper()
    email_clean = str(body.email).strip().lower()

    # 1. Check email domain against ALLOWED_EMAIL_DOMAINS
    domain = email_clean.split("@")[-1] if "@" in email_clean else ""
    if domain not in settings.allowed_email_domain_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email domain '{domain}' is not allowed for registration.",
        )

    # 2. Check registration number in student_roster
    roster = db.execute(
        select(StudentRoster).where(func.upper(StudentRoster.registration_number) == reg_num)
    ).scalar_one_or_none()

    if not roster:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration number not found in university roster.",
        )

    # 3. Verify email matches roster email
    if roster.email.strip().lower() != email_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address does not match the official roster record for this registration number.",
        )

    # 4. Ensure no user account already exists
    existing_user = db.execute(
        select(User).where(
            (func.lower(User.email) == email_clean) | (User.roster_id == roster.id)
        )
    ).scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account has already been registered for this student. Please log in.",
        )

    # 5. Generate 6-digit OTP, store hash with 10-minute expiry
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
    db.commit()

    # Dispatch email
    send_otp_email(to_email=email_clean, otp_code=plain_otp, registration_number=roster.registration_number)

    dev_otp = plain_otp if (settings.APP_ENV == "development" and settings.DEV_RETURN_OTP) else None
    return SignupOTPResponse(
        detail="If the details match our records, an OTP has been dispatched to your email.",
        dev_otp=dev_otp,
    )


@router.post(
    "/signup/verify",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="verify_signup_otp",
    summary="Verify OTP and Create Student Account",
    description=(
        "Verifies the received OTP, enforces maximum 5 attempts, validates password length (min 8 chars), "
        "creates the User record with student role linked to the roster entry, and returns an access token."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid, expired, or exceeded attempts OTP, or password too short"},
        409: {"model": ErrorResponse, "description": "Account already created for this registration number"},
    },
)
def verify_signup_otp(body: SignupVerifyRequest, db: SessionDep) -> TokenResponse:
    reg_num = body.registration_number.strip().upper()
    now = datetime.now(timezone.utc)

    if len(body.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
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

    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active OTP request found. Please request a new OTP.",
        )

    if otp_record.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please request a new OTP.",
        )

    if otp_record.attempts >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum verification attempts (5) exceeded. Please request a new OTP.",
        )

    # Verify code
    is_valid = verify_otp(body.otp.strip(), otp_record.code_hash)
    if not is_valid:
        otp_record.attempts += 1
        db.commit()
        remaining = 5 - otp_record.attempts
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incorrect OTP. {remaining} attempt(s) remaining.",
        )

    # Roster lookup
    roster = db.execute(
        select(StudentRoster).where(func.upper(StudentRoster.registration_number) == reg_num)
    ).scalar_one()

    # Check for duplicate user
    existing_user = db.execute(
        select(User).where(
            (func.lower(User.email) == roster.email.lower()) | (User.roster_id == roster.id)
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
        email=roster.email.strip().lower(),
        password_hash=hash_password(body.password),
        role=UserRole.student,
        department_id=None,
        roster_id=roster.id,
        is_active=True,
        created_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, token_type="bearer")


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    operation_id="login_access_token",
    summary="User Login (OAuth2 Password Grant)",
    description=(
        "Authenticates university students, department officers, HoDs, and administrators. "
        "Accepts form data where username is the user's email address. Returns a JWT Bearer access token."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Incorrect email or password, or account inactive"},
    },
)
def login_access_token(
    db: SessionDep,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> TokenResponse:
    email_clean = form_data.username.strip().lower()

    user = db.execute(
        select(User).where(func.lower(User.email) == email_clean)
    ).scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.password_hash):
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

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, token_type="bearer")


@router.get(
    "/me",
    response_model=UserMeResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_my_profile",
    summary="Get Current User Profile",
    description=(
        "Returns profile details for the authenticated user. If the user is a student, "
        "includes their academic roster summary, deposit amount, and securely masked bank account number."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Unauthenticated or invalid token"},
    },
)
def get_my_profile(current_user: CurrentUserDep) -> UserMeResponse:
    dept_name = current_user.department.name if current_user.department else None

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
        role=current_user.role.value,
        department_id=current_user.department_id,
        department_name=dept_name,
        roster=roster_summary,
    )
