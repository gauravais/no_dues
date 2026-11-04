"""Security utilities: password hashing, OTP generation/hashing, and JWT encoding/decoding."""
import secrets
import string
from datetime import datetime, timezone, timedelta
from typing import Any
import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from backend.app.core.config import settings

# Initialize Argon2 password hasher
password_hasher = PasswordHash([Argon2Hasher()])


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2."""
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """Verify a plaintext password against an Argon2 hash."""
    if not hashed_password or not plain_password:
        return False
    return password_hasher.verify(plain_password, hashed_password)


def generate_otp(length: int = 6) -> str:
    """Generate a cryptographically secure numeric OTP."""
    digits = string.digits
    return "".join(secrets.choice(digits) for _ in range(length))


def hash_otp(otp: str) -> str:
    """Hash an OTP code using Argon2 before database persistence."""
    return password_hasher.hash(otp)


def verify_otp(plain_otp: str, hashed_otp: str) -> bool:
    """Verify an input OTP against its stored Argon2 hash."""
    return password_hasher.verify(plain_otp, hashed_otp)


def create_access_token(subject: str | int, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token carrying the user id in 'sub'."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT access token, returning payload dict or None if invalid/expired."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except (jwt.PyJWTError, ValueError):
        return None


def normalize_email(value: str | None) -> str:
    """Normalize email address by stripping whitespace and lowercasing."""
    if not value:
        return ""
    return str(value).strip().lower()
