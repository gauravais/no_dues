"""
Seed script for the NoDues Clearance System.

Usage (from backend/ directory):
    uv run python -m scripts.seed_synthetic
    uv run python -m scripts.seed_synthetic --reset                  # Only in APP_ENV=development
    uv run python -m scripts.seed_synthetic --remove-demo-students   # Delete DEMO students and their records
    uv run python -m scripts.seed_synthetic --migrate-staff-domain   # Rename @example.edu staff to SEED_STAFF_EMAIL_DOMAIN

Idempotent: running seed twice does NOT create duplicates (upsert on natural keys).
Zero student records are created by default. Real pilots seed only university structure and staff accounts.
"""
import argparse
import sys
import os
from datetime import datetime, timezone

# Ensure .env is loaded before importing settings
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from sqlalchemy import select, delete, update, func, not_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.app.core.config import settings
from backend.app.core.database import SessionLocal, engine
from backend.app.models.university import (
    Faculty, Department, Programme,
    DepartmentKind, DepartmentApplicability,
)
from backend.app.models.lab_course import LabCourse
from backend.app.models.roster import StudentRoster, RosterAssignedDepartment
from backend.app.models.user import User, UserRole
from backend.app.models.bank import BankDetail
from backend.app.models.clearance import (
    ClearanceRequest, DepartmentApproval, request_lab_courses,
)
from backend.app.models.certificate import Certificate
from backend.app.models.refund import Refund
from backend.app.models.audit import AuditLog
from backend.app.models.otp import SignupOTP
from backend.app.core.security import normalize_email
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from scripts.seed_structure import (
    FACULTY,
    ACADEMIC_DEPARTMENTS,
    PROGRAMMES,
    SERVICE_DEPARTMENTS_ALWAYS,
    SERVICE_DEPARTMENTS_HOSTELLER,
    SERVICE_DEPARTMENTS_ASSIGNED,
    seed_structure,
)

# ---------------------------------------------------------------------------
# CONFIGURATION — university structure and departmental staffing
# ---------------------------------------------------------------------------

# Local parts for named service dept officers
SERVICE_OFFICER_LOCAL_PARTS: dict[str, str] = {
    "Library":                       "library.officer",
    "Computer Lab/Centre":           "complab.officer",
    "General/Transportation Branch": "transport.officer",
    "Dean Student Welfare":          "dsw.officer",
    "Sports":                        "sports.officer",
    "N.S.S.":                        "nss.officer",
    "R&S Branch":                    "rs.officer",
    "IIC":                           "iic.officer",
    "Account Section":               "accounts.officer",
    "Hostel (Boys/Girls)":           "hostel.officer",
}

# Short slugs for academic dept email generation
DEPT_SLUG: dict[str, str] = {
    "Skill Department of CS/IT":                                "csit",
    "Skill Department of Industry 4.0":                        "industry40",
    "Skill Department of Construction Management and Technology": "cmt",
    "Skill Department of Automotive Studies":                  "auto",
    "Skill Department of Green Technology":                    "greentech",
    "Skill Department of Plastic Technology":                  "plastic",
}


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def get_password_hasher() -> PasswordHash:
    return PasswordHash([Argon2Hasher()])


def hash_password(pw: str) -> str:
    ph = get_password_hasher()
    return ph.hash(pw)


def upsert_returning_id(session, model, conflict_cols: list[str], values: dict) -> int:
    """PostgreSQL INSERT … ON CONFLICT DO UPDATE, then SELECT the row."""
    update_dict = {k: v for k, v in values.items() if k not in conflict_cols}
    if update_dict:
        stmt = (
            pg_insert(model)
            .values(**values)
            .on_conflict_do_update(
                index_elements=conflict_cols,
                set_=update_dict,
            )
        )
    else:
        stmt = (
            pg_insert(model)
            .values(**values)
            .on_conflict_do_nothing(index_elements=conflict_cols)
        )
    session.execute(stmt)
    session.flush()

    filters = [getattr(model, col) == values[col] for col in conflict_cols]
    row = session.execute(select(model).where(*filters)).scalar_one()
    return row.id


ALLOWED_LOCAL_HOSTS = {"localhost", "127.0.0.1", "nodues_db", "db"}


def assert_local_database_host(host: str | None = None) -> None:
    """Refuse to run if database host is not local (localhost, 127.0.0.1, or local compose service name).

    This check applies to ALL operations (--reset, --remove-demo-students, --migrate-staff-domain, seed)
    regardless of APP_ENV. There is no override flag.
    """
    if host is None:
        try:
            host = engine.url.host
        except Exception:
            host = settings.POSTGRES_HOST

    host_clean = (host or "").strip().lower()
    if host_clean not in ALLOWED_LOCAL_HOSTS:
        print(
            f"ERROR: Refusing to run seed_synthetic against non-local database host '{host_clean}'. "
            f"Synthetic data operations are strictly permitted only on local hosts ({', '.join(sorted(ALLOWED_LOCAL_HOSTS))}), regardless of APP_ENV. "
            "There is no override flag.",
            file=sys.stderr,
        )
        raise RuntimeError(
            f"Refusing to run seed_synthetic against non-local database host '{host_clean}'"
        )


def check_environment_and_domain(staff_domain: str) -> None:
    """Verify safety requirements: refuse in production, validate staff domain against ALLOWED_EMAIL_DOMAINS."""
    if settings.APP_ENV == "production":
        print(
            "ERROR: Refusing to seed synthetic data in production. "
            "Create staff users through the admin API /admin/users or bulk upload.",
            file=sys.stderr,
        )
        sys.exit(1)

    if staff_domain not in settings.allowed_email_domain_list:
        print(
            f"ERROR: SEED_STAFF_EMAIL_DOMAIN '{staff_domain}' is not listed in ALLOWED_EMAIL_DOMAINS "
            f"({', '.join(settings.allowed_email_domain_list)}).",
            file=sys.stderr,
        )
        sys.exit(1)


def check_real_data_guard(session, i_know_real_data_exists: bool) -> None:
    """Refuse destructive operations if real (non-DEMO) student roster rows exist without explicit override."""
    real_student_count = session.scalar(
        select(func.count(StudentRoster.id)).where(
            not_(StudentRoster.registration_number.startswith("DEMO"))
        )
    ) or 0
    if real_student_count > 0 and not i_know_real_data_exists:
        print(
            f"ERROR: Found {real_student_count} real (non-DEMO) student roster row(s) in database. "
            "Refusing --reset / --remove-demo-students unless --i-know-real-data-exists is explicitly passed.",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLEANUP DEMO STUDENTS
# ---------------------------------------------------------------------------

def remove_demo_students(session, yes: bool = False, i_know_real_data_exists: bool = False) -> dict[str, int]:
    """Delete ONLY roster rows whose registration_number starts with 'DEMO' and dependent records.

    Audit log entries are preserved without deletion (user_id is unlinked if linked to demo user).
    """
    assert_local_database_host()

    if settings.APP_ENV not in ("development", "test"):
        print("ERROR: --remove-demo-students is only allowed when APP_ENV=development", file=sys.stderr)
        sys.exit(1)

    check_real_data_guard(session, i_know_real_data_exists)

    if not yes:
        try:
            confirm = input("Are you sure you want to delete all DEMO students and their records? [y/N]: ")
        except EOFError:
            confirm = "n"
        if confirm.strip().lower() not in ("y", "yes"):
            print("Aborted.")
            return {}

    print("Cleaning up DEMO students and dependent records…")

    demo_roster_rows = session.scalars(
        select(StudentRoster).where(StudentRoster.registration_number.startswith("DEMO"))
    ).all()
    demo_roster_ids = [r.id for r in demo_roster_rows]

    demo_user_ids = []
    if demo_roster_ids:
        demo_user_ids = session.scalars(
            select(User.id).where(User.roster_id.in_(demo_roster_ids))
        ).all()

    other_demo_student_user_ids = session.scalars(
        select(User.id).where(
            User.role == UserRole.student,
            User.email.ilike("%demo%"),
            User.id.not_in(demo_user_ids) if demo_user_ids else True,
        )
    ).all()
    all_demo_user_ids = list(set(demo_user_ids + other_demo_student_user_ids))

    demo_request_ids = []
    if demo_roster_ids:
        demo_request_ids = session.scalars(
            select(ClearanceRequest.id).where(ClearanceRequest.roster_id.in_(demo_roster_ids))
        ).all()

    counts: dict[str, int] = {}

    # 1. certificates
    if demo_request_ids:
        res = session.execute(delete(Certificate).where(Certificate.request_id.in_(demo_request_ids)))
        counts["certificates"] = res.rowcount or 0
    else:
        counts["certificates"] = 0

    # 2. refunds
    if demo_request_ids:
        res = session.execute(delete(Refund).where(Refund.request_id.in_(demo_request_ids)))
        counts["refunds"] = res.rowcount or 0
    else:
        counts["refunds"] = 0

    # 3. request_lab_courses
    if demo_request_ids:
        res = session.execute(delete(request_lab_courses).where(request_lab_courses.c.request_id.in_(demo_request_ids)))
        counts["request_lab_courses"] = res.rowcount or 0
    else:
        counts["request_lab_courses"] = 0

    # 4. department_approvals
    if demo_request_ids:
        res = session.execute(delete(DepartmentApproval).where(DepartmentApproval.request_id.in_(demo_request_ids)))
        counts["department_approvals"] = res.rowcount or 0
    else:
        counts["department_approvals"] = 0

    # 5. clearance_requests
    if demo_request_ids:
        res = session.execute(delete(ClearanceRequest).where(ClearanceRequest.id.in_(demo_request_ids)))
        counts["clearance_requests"] = res.rowcount or 0
    else:
        counts["clearance_requests"] = 0

    # 6. bank_details
    if demo_roster_ids:
        res = session.execute(delete(BankDetail).where(BankDetail.roster_id.in_(demo_roster_ids)))
        counts["bank_details"] = res.rowcount or 0
    else:
        counts["bank_details"] = 0

    # 7. signup_otps (by registration_number prefix DEMO)
    res = session.execute(delete(SignupOTP).where(SignupOTP.registration_number.startswith("DEMO")))
    counts["signup_otps"] = res.rowcount or 0

    # 8. audit_log — DO NOT DELETE rows; unlink user_id to prevent FK violation
    if all_demo_user_ids:
        session.execute(
            update(AuditLog).where(AuditLog.user_id.in_(all_demo_user_ids)).values(user_id=None)
        )

    # 9. roster_assigned_departments
    if demo_roster_ids:
        res = session.execute(delete(RosterAssignedDepartment).where(RosterAssignedDepartment.roster_id.in_(demo_roster_ids)))
        counts["roster_assigned_departments"] = res.rowcount or 0
    else:
        counts["roster_assigned_departments"] = 0

    # 10. users (demo students)
    if all_demo_user_ids:
        res = session.execute(delete(User).where(User.id.in_(all_demo_user_ids)))
        counts["users"] = res.rowcount or 0
    else:
        counts["users"] = 0

    # 11. student_roster (only DEMO rows)
    if demo_roster_ids:
        res = session.execute(delete(StudentRoster).where(StudentRoster.id.in_(demo_roster_ids)))
        counts["student_roster"] = res.rowcount or 0
    else:
        counts["student_roster"] = 0

    session.commit()

    print("Deleted rows per table:")
    for tbl, cnt in counts.items():
        print(f"  - {tbl}: {cnt}")

    return counts


# ---------------------------------------------------------------------------
# MIGRATE STAFF DOMAIN
# ---------------------------------------------------------------------------

def migrate_staff_domain(session, staff_domain: str) -> tuple[list[str], list[tuple[str, str]]]:
    """Update existing staff users whose email is @example.edu to SEED_STAFF_EMAIL_DOMAIN."""
    assert_local_database_host()
    print(f"Migrating existing staff accounts from @example.edu to @{staff_domain}…")
    staff_users = session.scalars(
        select(User).where(
            User.role != UserRole.student,
            User.email.endswith("@example.edu"),
        ).order_by(User.id)
    ).all()

    renamed_emails: list[str] = []
    collisions: list[tuple[str, str]] = []

    for user in staff_users:
        local_part = user.email.split("@")[0]
        new_email = normalize_email(f"{local_part}@{staff_domain}")
        collision = session.scalar(
            select(User).where(User.email == new_email, User.id != user.id)
        )
        if collision:
            print(f"  COLLISION: cannot rename '{user.email}' -> '{new_email}': account already exists. Skipping.")
            collisions.append((user.email, new_email))
        else:
            old_email = user.email
            user.email = new_email
            renamed_emails.append(new_email)
            print(f"  Renamed: {old_email} -> {new_email}")

    session.commit()
    print(f"Migration complete: {len(renamed_emails)} account(s) renamed, {len(collisions)} collision(s) skipped.")
    return renamed_emails, collisions


# ---------------------------------------------------------------------------
# RESET (development only)
# ---------------------------------------------------------------------------

def reset_data(session, i_know_real_data_exists: bool = False) -> None:
    """Wipe seeded structure and demo data before re-seeding (only in APP_ENV=development).

    A reset NEVER deletes real student roster rows.
    """
    assert_local_database_host()
    if settings.APP_ENV not in ("development", "test"):
        print("ERROR: --reset is only allowed when APP_ENV=development", file=sys.stderr)
        sys.exit(1)

    check_real_data_guard(session, i_know_real_data_exists)

    print("Resetting seeded data (development only)…")
    # Clean up demo students first
    remove_demo_students(session, yes=True, i_know_real_data_exists=i_know_real_data_exists)

    real_student_count = session.scalar(
        select(func.count(StudentRoster.id)).where(
            not_(StudentRoster.registration_number.startswith("DEMO"))
        )
    ) or 0

    # Delete staff users
    session.execute(delete(User).where(User.role != UserRole.student))

    # A reset must NEVER delete real roster rows.
    # If no real roster rows exist, also wipe programmes, departments, faculties.
    if real_student_count == 0:
        session.execute(delete(Programme))
        session.execute(delete(Department))
        session.execute(delete(Faculty))
    else:
        print("Real student roster rows present; preserving programmes, departments, and faculties.")

    session.commit()
    print("Reset complete.")


# ---------------------------------------------------------------------------
# SEED (pilot structure and staff only — ZERO students)
# ---------------------------------------------------------------------------

def seed(session, staff_domain: str) -> list[str]:
    assert_local_database_host()
    password = settings.SEED_DEFAULT_PASSWORD
    if not password:
        print("ERROR: SEED_DEFAULT_PASSWORD not set in environment", file=sys.stderr)
        sys.exit(1)

    pw_hash = hash_password(password)
    now = datetime.now(timezone.utc)
    staff_emails_created: list[str] = []

    # 1-6. University Structure (Faculty, Departments, Programmes)
    struct_ids = seed_structure(session)
    faculty_id = struct_ids["faculty_id"]
    academic_dept_ids = struct_ids["academic_dept_ids"]
    programme_ids = struct_ids["programme_ids"]
    service_dept_ids = struct_ids["service_dept_ids"]
    assigned_dept_ids = struct_ids["assigned_dept_ids"]

    # 7. Staff Users (Seeded under staff_domain)
    print(f"Seeding staff users with domain @{staff_domain}…")

    # Admin (no department)
    admin_email = normalize_email(f"admin@{staff_domain}")
    upsert_returning_id(session, User, ["email"], {
        "email": admin_email,
        "full_name": "System Administrator (Demo)",
        "password_hash": pw_hash,
        "role": UserRole.admin,
        "department_id": None,
        "roster_id": None,
        "is_active": True,
        "created_at": now,
    })
    staff_emails_created.append(admin_email)

    # Registrar/Accounts — attached to R&S Branch
    rs_branch_id = service_dept_ids["R&S Branch"]
    reg_email = normalize_email(f"registrar.accounts@{staff_domain}")
    upsert_returning_id(session, User, ["email"], {
        "email": reg_email,
        "full_name": "Accounts Officer (Demo)",
        "password_hash": pw_hash,
        "role": UserRole.registrar_accounts,
        "department_id": rs_branch_id,
        "roster_id": None,
        "is_active": True,
        "created_at": now,
    })
    staff_emails_created.append(reg_email)

    # Service dept officers for named departments
    for dept_name, local_part in SERVICE_OFFICER_LOCAL_PARTS.items():
        dept_id = service_dept_ids.get(dept_name)
        if dept_id is None:
            print(f"  WARN: service dept '{dept_name}' not found, skipping", file=sys.stderr)
            continue
        email = normalize_email(f"{local_part}@{staff_domain}")
        upsert_returning_id(session, User, ["email"], {
            "email": email,
            "full_name": f"{dept_name} Officer (Demo)",
            "password_hash": pw_hash,
            "role": UserRole.dept_officer,
            "department_id": dept_id,
            "roster_id": None,
            "is_active": True,
            "created_at": now,
        })
        staff_emails_created.append(email)

    # Service dept officers for ASSIGNED_ONLY labs/workshops/others
    for dept_name, dept_id in assigned_dept_ids.items():
        slug = (
            dept_name.lower()
            .replace("/", "")
            .replace("-", "")
            .replace(" ", "")
            .replace(".", "")
        )
        email = normalize_email(f"{slug}.officer@{staff_domain}")
        upsert_returning_id(session, User, ["email"], {
            "email": email,
            "full_name": f"{dept_name} In-Charge (Demo)",
            "password_hash": pw_hash,
            "role": UserRole.dept_officer,
            "department_id": dept_id,
            "roster_id": None,
            "is_active": True,
            "created_at": now,
        })
        staff_emails_created.append(email)

    # Academic dept officers + HoDs (one each per department)
    for dept_name, dept_id in academic_dept_ids.items():
        slug = DEPT_SLUG[dept_name]
        officer_email = normalize_email(f"officer.{slug}@{staff_domain}")
        hod_email = normalize_email(f"hod.{slug}@{staff_domain}")

        upsert_returning_id(session, User, ["email"], {
            "email": officer_email,
            "full_name": f"{dept_name} Officer (Demo)",
            "password_hash": pw_hash,
            "role": UserRole.dept_officer,
            "department_id": dept_id,
            "roster_id": None,
            "is_active": True,
            "created_at": now,
        })
        staff_emails_created.append(officer_email)

        upsert_returning_id(session, User, ["email"], {
            "email": hod_email,
            "full_name": f"Chairperson {dept_name} (Demo)",
            "password_hash": pw_hash,
            "role": UserRole.hod,
            "department_id": dept_id,
            "roster_id": None,
            "is_active": True,
            "created_at": now,
        })
        staff_emails_created.append(hod_email)

    session.commit()
    print("Seed complete. (Zero student records created).")
    return staff_emails_created


# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------

def print_summary(session, staff_emails: list[str]) -> None:
    models_to_count = [
        ("faculties", Faculty),
        ("departments", Department),
        ("programmes", Programme),
        ("lab_courses", LabCourse),
        ("student_roster", StudentRoster),
        ("roster_assigned_departments", RosterAssignedDepartment),
        ("users", User),
        ("bank_details", BankDetail),
        ("clearance_requests", ClearanceRequest),
        ("department_approvals", DepartmentApproval),
        ("certificates", Certificate),
        ("refunds", Refund),
        ("signup_otps", SignupOTP),
        ("audit_log", AuditLog),
    ]

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("Database Table Row Counts:")
    for name, model in models_to_count:
        cnt = session.scalar(select(func.count()).select_from(model)) or 0
        print(f"  - {name}: {cnt}")

    if staff_emails:
        print("\nStaff Accounts (created or renamed):")
        for email in sorted(set(staff_emails)):
            print(f"  - {email}")

    print("\nReminder: Replace demo staff with real staff before enabling real email or letting real students apply.")
    print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    try:
        assert_local_database_host()
    except RuntimeError:
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Seed synthetic data for NoDues system")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe seeded structure and demo data before re-seeding (only in APP_ENV=development)",
    )
    parser.add_argument(
        "--remove-demo-students",
        action="store_true",
        help="Delete all DEMO students, roster rows, and dependent records (only in APP_ENV=development)",
    )
    parser.add_argument(
        "--migrate-staff-domain",
        action="store_true",
        help="Migrate existing staff users with @example.edu to SEED_STAFF_EMAIL_DOMAIN",
    )
    parser.add_argument(
        "--i-know-real-data-exists",
        action="store_true",
        help="Explicit confirmation required to reset or remove demo students if real students exist",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip interactive confirmation for --remove-demo-students",
    )
    args = parser.parse_args()

    staff_domain = os.environ.get(
        "SEED_STAFF_EMAIL_DOMAIN", getattr(settings, "SEED_STAFF_EMAIL_DOMAIN", "svsu.ac.in")
    ).strip().lower()

    check_environment_and_domain(staff_domain)

    with SessionLocal() as session:
        staff_emails: list[str] = []

        if args.reset:
            reset_data(session, i_know_real_data_exists=args.i_know_real_data_exists)

        if args.remove_demo_students:
            remove_demo_students(session, yes=args.yes, i_know_real_data_exists=args.i_know_real_data_exists)

        if args.migrate_staff_domain:
            renamed, _ = migrate_staff_domain(session, staff_domain=staff_domain)
            staff_emails.extend(renamed)

        should_run_seed = args.reset or (not args.remove_demo_students and not args.migrate_staff_domain)
        if should_run_seed:
            created_staff = seed(session, staff_domain=staff_domain)
            staff_emails.extend(created_staff)

        print_summary(session, staff_emails)


if __name__ == "__main__":
    main()
