"""Bootstrap initial administrator account for No-Dues Clearance System.

Reads credentials from command-line arguments, environment variables, or interactive input.
Validates email domain, enforces minimum 10-character password length, sets must_change_password=False,
and never prints or logs passwords.
"""
import argparse
import getpass
import os
import sys

from backend.app.core.config import settings
from backend.app.core.database import SessionLocal, engine
from backend.app.core.security import hash_password, normalize_email
from backend.app.models.user import User, UserRole


def create_first_admin(
    email: str,
    password: str,
    full_name: str | None = None,
    session=None,
) -> bool:
    email_clean = normalize_email(email)

    domain = email_clean.split("@")[-1] if "@" in email_clean else ""
    if domain not in settings.allowed_email_domain_list:
        print(f"Error: Email domain '{domain}' is not in ALLOWED_EMAIL_DOMAINS: {settings.allowed_email_domain_list}")
        return False

    if len(password) < 10:
        print("Error: Password must be at least 10 characters long.")
        return False

    local_session = session or SessionLocal()
    try:
        existing = local_session.query(User).filter(User.email == email_clean).first()
        if existing:
            if existing.role == UserRole.admin:
                print(f"Administrator account '{email_clean}' already exists.")
                return True
            else:
                print(f"Error: User '{email_clean}' already exists with role '{existing.role.value}'.")
                return False

        admin_user = User(
            email=email_clean,
            full_name=full_name.strip() if full_name else "System Administrator",
            password_hash=hash_password(password),
            role=UserRole.admin,
            department_id=None,
            roster_id=None,
            is_active=True,
            must_change_password=False,
        )
        local_session.add(admin_user)
        local_session.commit()
        print(f"Successfully created initial administrator account: {email_clean}")
        return True
    finally:
        if session is None:
            local_session.close()


def main():
    parser = argparse.ArgumentParser(description="Bootstrap first administrator account.")
    parser.add_argument("--email", help="Administrator email address")
    parser.add_argument("--password", help="Administrator password (min 10 chars)")
    parser.add_argument("--name", help="Administrator full display name")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt (strictly refused)")
    args = parser.parse_args()

    if args.yes:
        print("ERROR: --yes is not permitted for create_first_admin; you must interactively confirm by typing the database host.", file=sys.stderr)
        sys.exit(1)

    db_host = engine.url.host or "localhost"
    print(f"Database host: {db_host}")
    try:
        confirm = input(f"Type the database host '{db_host}' to confirm before writing: ").strip()
    except EOFError:
        confirm = ""
    if confirm != db_host:
        print("Host confirmation mismatch. Aborted.")
        sys.exit(1)

    email = args.email or os.environ.get("FIRST_ADMIN_EMAIL")
    password = args.password or os.environ.get("FIRST_ADMIN_PASSWORD")
    name = args.name or os.environ.get("FIRST_ADMIN_NAME")

    if not email:
        email = input("Enter administrator email: ").strip()

    if not password:
        password = getpass.getpass("Enter administrator password (min 10 chars): ")

    if not name:
        name = input("Enter administrator full name (optional, press Enter for default): ").strip() or None

    success = create_first_admin(email, password, name)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
