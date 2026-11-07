"""FastAPI request dependencies: database sessions, user authentication, and role authorization."""
from typing import Generator, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal
from backend.app.core.security import decode_access_token
from backend.app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    description="Provide access token as: Bearer <token>",
)


def get_db() -> Generator[Session, None, None]:
    """Provide a transactional SQLAlchemy session per request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(oauth2_scheme)]


def get_current_user_any(
    db: SessionDep,
    token: TokenDep,
) -> User:
    """
    Decodes the JWT Bearer token and ALWAYS reloads the live user record from the database.
    Verifies that the user exists and is active, without checking must_change_password.
    Used for endpoints accessible when password change is required (/auth/me, /auth/change-password).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception

    sub = payload.get("sub")
    if not sub:
        raise credentials_exception

    try:
        user_id = int(sub)
    except (ValueError, TypeError):
        raise credentials_exception

    user = db.get(User, user_id)
    if not user:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


CurrentUserAnyDep = Annotated[User, Depends(get_current_user_any)]


def get_current_user(
    current_user: CurrentUserAnyDep,
) -> User:
    """
    Ensures active user does not have must_change_password set.
    If must_change_password is True, raises 403 Forbidden with PASSWORD_CHANGE_REQUIRED.
    """
    if current_user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PASSWORD_CHANGE_REQUIRED",
        )
    return current_user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed_roles: UserRole):
    """
    Dependency factory to enforce role-based access control (RBAC).
    Returns a 403 Forbidden exception if the user does not possess one of the allowed roles.
    """
    def role_checker(current_user: CurrentUserDep) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation forbidden: required role in {[r.value for r in allowed_roles]}, your role is {current_user.role.value}",
            )
        return current_user

    return role_checker


def require_academic_officer(
    current_user: CurrentUserDep,
    db: SessionDep,
) -> User:
    """
    Enforces that the user is a dept_officer belonging to an academic department.
    Returns 403 Forbidden for service department officers or other roles.
    """
    if current_user.role != UserRole.dept_officer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation forbidden: required role is dept_officer, your role is {current_user.role.value}",
        )
    from backend.app.services.workflow import user_academic_department_ids
    acad_dept_ids = user_academic_department_ids(current_user, db)
    if not acad_dept_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation forbidden: roster and lab catalog management is restricted to academic department officers",
        )
    return current_user


