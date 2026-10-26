"""
Seed script for the NoDues Clearance System.

Usage (from backend/ directory):
    uv run python -m scripts.seed_synthetic
    uv run python -m scripts.seed_synthetic --reset   # Only in APP_ENV=development

Idempotent: running twice does NOT create duplicates (upsert on natural keys).
--reset: Wipes all seeded data in FK-safe order (development only).
"""
import argparse
import sys
import os
from datetime import datetime, timezone

# Ensure .env is loaded before importing settings
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.models.university import (
    Faculty, Department, Programme,
    DepartmentKind, DepartmentApplicability,
)
from backend.app.models.roster import StudentRoster, RosterAssignedDepartment
from backend.app.models.user import User, UserRole
from backend.app.models.bank import BankDetail
from backend.app.models.otp import SignupOTP
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

# ---------------------------------------------------------------------------
# CONFIGURATION — edit these lists/dicts to change seeded data
# ---------------------------------------------------------------------------

FACULTY = {
    "name": "Skill Faculty of Engineering & Technology",
    "short_code": "SFET",
}

# Academic departments (all under SFET faculty)
ACADEMIC_DEPARTMENTS = [
    "Skill Department of Automotive Studies",
    "Skill Department of Construction Management and Technology",
    "Skill Department of Green Technology",
    "Skill Department of CS/IT",
    "Skill Department of Industry 4.0",
    "Skill Department of Plastic Technology",
]

# Programmes mapped to departments.
# Status markers in comments:
#   [verified]  = confirmed on university website or admission notice
#   [INFERRED]  = not explicitly listed; mapping inferred by subject area
PROGRAMMES: dict[str, list[str]] = {
    # CS/IT [verified on the department page]
    "Skill Department of CS/IT": [
        "Master of Computer Application (MCA)",                         # [verified]
        "Bachelor of Technology (B.Tech.) Computer Science & Engineering",  # [verified]
        "Bachelor of Technology (B.Tech.) Computer Engineering",        # [verified]
        "Bachelor in Computer Applications (BCA)",                      # [verified]
        "Diploma in Computer (Generative AI/ Cyber Security)",          # [verified]
        "Diploma in Computer Science & Engineering",                    # [verified]
    ],
    # Industry 4.0 [verified via the university admission notice]
    "Skill Department of Industry 4.0": [
        "Diploma in Industrial Electronics",                            # [verified]
        "Bachelor of Vocation Robotics and Automation",                 # [verified]
        "Master of Technology Robotics and Automation",                 # [verified]
        "PG Diploma in Semiconductor Device Packaging",                 # [verified]
    ],
    # Construction Management and Technology
    "Skill Department of Construction Management and Technology": [
        "Diploma of Vocation Draughtsmanship (Civil)",                  # [verified]
        "Undergraduate Diploma in Interior Design",                     # [verified]
        "Diploma in Civil Engineering",                                 # [INFERRED]
    ],
    # Automotive Studies [INFERRED for all]
    "Skill Department of Automotive Studies": [
        "Diploma of Vocation Mechanical Manufacturing",                 # [INFERRED]
        "Diploma in Mechanical Engineering",                            # [INFERRED]
        "Bachelor of Vocation Mechanical Manufacturing",                # [INFERRED]
        "Bachelor of Technology Mechanical and Smart Manufacturing",    # [INFERRED]
        "Bachelor of Vocation Mechatronics",                           # [INFERRED]
    ],
    # Green Technology [INFERRED for all]
    "Skill Department of Green Technology": [
        "Bachelor of Vocation Solar Technology",                        # [INFERRED]
        "Bachelor of Vocation (Refrigeration and Air Conditioning)",    # [INFERRED]
        "Bachelor of Technology Electrical Engineering",                # [INFERRED]
    ],
    # Plastic Technology — no programmes listed (dept still gets officer + HoD)
    "Skill Department of Plastic Technology": [],
}

# Service departments — ALWAYS applicable
SERVICE_DEPARTMENTS_ALWAYS = [
    "Library",
    "Computer Lab/Centre",
    "General/Transportation Branch",
    "Dean Student Welfare",
    "Sports",
    "N.S.S.",
    "R&S Branch",
    "IIC",
    "Account Section",
]

# Service departments — HOSTELLER_ONLY
SERVICE_DEPARTMENTS_HOSTELLER = [
    "Hostel (Boys/Girls)",
]

# Service departments — ASSIGNED_ONLY (labs, workshops, others)
ASSIGNED_ONLY_LABS = [f"Lab-{i}" for i in range(1, 10)]        # Lab-1 to Lab-9
ASSIGNED_ONLY_WORKSHOPS = [f"Workshop-{i}" for i in range(1, 4)]  # Workshop-1 to Workshop-3
ASSIGNED_ONLY_OTHERS = ["Others"]
SERVICE_DEPARTMENTS_ASSIGNED = ASSIGNED_ONLY_LABS + ASSIGNED_ONLY_WORKSHOPS + ASSIGNED_ONLY_OTHERS

# Explicit email map for named service dept officers
SERVICE_OFFICER_EMAIL_MAP: dict[str, str] = {
    "Library":                       "library.officer@example.edu",
    "Computer Lab/Centre":           "complab.officer@example.edu",
    "General/Transportation Branch": "transport.officer@example.edu",
    "Dean Student Welfare":          "dsw.officer@example.edu",
    "Sports":                        "sports.officer@example.edu",
    "N.S.S.":                        "nss.officer@example.edu",
    "R&S Branch":                    "rs.officer@example.edu",
    "IIC":                           "iic.officer@example.edu",
    "Account Section":               "accounts.officer@example.edu",
    "Hostel (Boys/Girls)":           "hostel.officer@example.edu",
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
# Synthetic students — ALL data is FAKE (no real names, emails, or numbers)
# Covers: 3 hostellers (DEMO001-003), 2 day scholars (DEMO004-005)
#         3 different academic departments (CS/IT, Industry 4.0, Green/CMT)
#         Lab/workshop assignments for DEMO001, DEMO002, DEMO003
# ---------------------------------------------------------------------------
STUDENTS = [
    {
        "registration_number": "DEMO2026001",
        "name": "Arjun Mehta",                      # FAKE
        "email": "arjun.mehta@example.edu",
        "mobile": "9800000001",
        "address": "12, Fake Street, Demo City, 110001",
        "programme": "Bachelor of Technology (B.Tech.) Computer Engineering",
        "is_hosteller": True,
        "security_deposit_amount": 5000.00,
        "assigned_labs": ["Lab-2", "Lab-5"],
        "bank": {
            "account_holder_name": "Arjun Mehta",
            "account_number": "110200000001",
            "ifsc_code": "DEMO0000001",
            "bank_address": "Demo Bank, Main Branch, Demo City",
        },
    },
    {
        "registration_number": "DEMO2026002",
        "name": "Priya Sharma",                     # FAKE
        "email": "priya.sharma@example.edu",
        "mobile": "9800000002",
        "address": "34, Sample Nagar, Demo City, 110002",
        "programme": "Master of Computer Application (MCA)",
        "is_hosteller": True,
        "security_deposit_amount": 10000.00,
        "assigned_labs": ["Lab-3"],
        "bank": {
            "account_holder_name": "Priya Sharma",
            "account_number": "220300000002",
            "ifsc_code": "DEMO0000002",
            "bank_address": "Demo Bank, West Branch, Demo City",
        },
    },
    {
        "registration_number": "DEMO2026003",
        "name": "Rohan Verma",                      # FAKE
        "email": "rohan.verma@example.edu",
        "mobile": "9800000003",
        "address": "56, Test Colony, Demo City, 110003",
        "programme": "Bachelor of Vocation Robotics and Automation",
        "is_hosteller": True,
        "security_deposit_amount": 6000.00,
        "assigned_labs": ["Workshop-1"],
        "bank": {
            "account_holder_name": "Rohan Verma",
            "account_number": "330400000003",
            "ifsc_code": "DEMO0000003",
            "bank_address": "Demo Bank, East Branch, Demo City",
        },
    },
    {
        "registration_number": "DEMO2026004",
        "name": "Sneha Patel",                      # FAKE
        "email": "sneha.patel@example.edu",
        "mobile": "9800000004",
        "address": "78, Mock Road, Demo City, 110004",
        "programme": "Bachelor of Vocation Solar Technology",
        "is_hosteller": False,
        "security_deposit_amount": 3000.00,
        "assigned_labs": [],
        "bank": {
            "account_holder_name": "Sneha Patel",
            "account_number": "440500000004",
            "ifsc_code": "DEMO0000004",
            "bank_address": "Demo Bank, North Branch, Demo City",
        },
    },
    {
        "registration_number": "DEMO2026005",
        "name": "Vikram Singh",                     # FAKE
        "email": "vikram.singh@example.edu",
        "mobile": "9800000005",
        "address": "90, Placeholder Avenue, Demo City, 110005",
        "programme": "Diploma in Civil Engineering",
        "is_hosteller": False,
        "security_deposit_amount": 2500.00,
        "assigned_labs": [],
        "bank": {
            "account_holder_name": "Vikram Singh",
            "account_number": "550600000005",
            "ifsc_code": "DEMO0000005",
            "bank_address": "Demo Bank, South Branch, Demo City",
        },
    },
]

# 3 extra roster rows WITHOUT user accounts (so sign-up can be tested)
UNREGISTERED_STUDENTS = [
    {
        "registration_number": "DEMO2026006",
        "name": "Aman Gupta",                      # FAKE
        "email": "aman.gupta@example.edu",
        "mobile": "9800000006",
        "address": "101, Test Road, Demo City, 110006",
        "programme": "Bachelor of Technology (B.Tech.) Computer Science & Engineering",
        "is_hosteller": False,
        "security_deposit_amount": 5000.00,
        "assigned_labs": [],
        "bank": {
            "account_holder_name": "Aman Gupta",
            "account_number": "660700000006",
            "ifsc_code": "DEMO0000006",
            "bank_address": "Demo Bank, Central Branch, Demo City",
        },
    },
    {
        "registration_number": "DEMO2026007",
        "name": "Kavita Rao",                      # FAKE
        "email": "kavita.rao@example.edu",
        "mobile": "9800000007",
        "address": "102, Sample Avenue, Demo City, 110007",
        "programme": "Bachelor of Vocation Robotics and Automation",
        "is_hosteller": True,
        "security_deposit_amount": 7500.00,
        "assigned_labs": ["Lab-1"],
        "bank": {
            "account_holder_name": "Kavita Rao",
            "account_number": "770800000007",
            "ifsc_code": "DEMO0000007",
            "bank_address": "Demo Bank, City Branch, Demo City",
        },
    },
    {
        "registration_number": "DEMO2026008",
        "name": "Deepak Joshi",                     # FAKE
        "email": "deepak.joshi@example.edu",
        "mobile": "9800000008",
        "address": "103, Mock Colony, Demo City, 110008",
        "programme": "Diploma of Vocation Draughtsmanship (Civil)",
        "is_hosteller": False,
        "security_deposit_amount": 3500.00,
        "assigned_labs": [],
        "bank": {
            "account_holder_name": "Deepak Joshi",
            "account_number": "880900000008",
            "ifsc_code": "DEMO0000008",
            "bank_address": "Demo Bank, South Extension, Demo City",
        },
    },
]


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def get_password_hasher() -> PasswordHash:
    return PasswordHash([Argon2Hasher()])


def hash_password(pw: str) -> str:
    ph = get_password_hasher()
    return ph.hash(pw)


def upsert_returning_id(session, model, conflict_cols: list[str], values: dict) -> int:
    """PostgreSQL INSERT … ON CONFLICT DO UPDATE, then SELECT the row.

    Idempotent on the natural key(s) listed in conflict_cols.
    """
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


# ---------------------------------------------------------------------------
# RESET (development only)
# ---------------------------------------------------------------------------

def reset_data(session) -> None:
    if settings.APP_ENV != "development":
        print("ERROR: --reset is only allowed when APP_ENV=development", file=sys.stderr)
        sys.exit(1)
    print("Resetting seeded data (development only)…")
    # FK-safe order: deepest dependents first
    session.execute(delete(SignupOTP))
    session.execute(delete(BankDetail))
    session.execute(delete(RosterAssignedDepartment))
    session.execute(delete(User))
    session.execute(delete(StudentRoster))
    session.execute(delete(Programme))
    session.execute(delete(Department))
    session.execute(delete(Faculty))
    session.commit()
    print("Reset complete.")


# ---------------------------------------------------------------------------
# SEED
# ---------------------------------------------------------------------------

def seed(session) -> None:
    password = settings.SEED_DEFAULT_PASSWORD
    if not password:
        print("ERROR: SEED_DEFAULT_PASSWORD not set in environment", file=sys.stderr)
        sys.exit(1)

    pw_hash = hash_password(password)
    now = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # 1. Faculty
    # ------------------------------------------------------------------
    print("Seeding faculty…")
    faculty_id = upsert_returning_id(session, Faculty, ["name"], {
        "name": FACULTY["name"],
        "short_code": FACULTY["short_code"],
    })

    # ------------------------------------------------------------------
    # 2. Academic departments
    # ------------------------------------------------------------------
    print("Seeding academic departments…")
    academic_dept_ids: dict[str, int] = {}
    for dept_name in ACADEMIC_DEPARTMENTS:
        dept_id = upsert_returning_id(session, Department, ["name"], {
            "name": dept_name,
            "kind": DepartmentKind.academic,
            "applicability": DepartmentApplicability.OWN_ACADEMIC,
            "faculty_id": faculty_id,
        })
        academic_dept_ids[dept_name] = dept_id

    # ------------------------------------------------------------------
    # 3. Programmes
    # ------------------------------------------------------------------
    print("Seeding programmes…")
    programme_ids: dict[str, int] = {}
    for dept_name, prog_list in PROGRAMMES.items():
        dept_id = academic_dept_ids[dept_name]
        for prog_name in prog_list:
            prog_id = upsert_returning_id(session, Programme, ["name"], {
                "name": prog_name,
                "academic_department_id": dept_id,
            })
            programme_ids[prog_name] = prog_id

    # ------------------------------------------------------------------
    # 4. Service departments — ALWAYS
    # ------------------------------------------------------------------
    print("Seeding service departments (ALWAYS)…")
    service_dept_ids: dict[str, int] = {}
    for dept_name in SERVICE_DEPARTMENTS_ALWAYS:
        dept_id = upsert_returning_id(session, Department, ["name"], {
            "name": dept_name,
            "kind": DepartmentKind.service,
            "applicability": DepartmentApplicability.ALWAYS,
            "faculty_id": None,
        })
        service_dept_ids[dept_name] = dept_id

    # ------------------------------------------------------------------
    # 5. Service departments — HOSTELLER_ONLY
    # ------------------------------------------------------------------
    print("Seeding service departments (HOSTELLER_ONLY)…")
    for dept_name in SERVICE_DEPARTMENTS_HOSTELLER:
        dept_id = upsert_returning_id(session, Department, ["name"], {
            "name": dept_name,
            "kind": DepartmentKind.service,
            "applicability": DepartmentApplicability.HOSTELLER_ONLY,
            "faculty_id": None,
        })
        service_dept_ids[dept_name] = dept_id

    # ------------------------------------------------------------------
    # 6. Service departments — ASSIGNED_ONLY (labs, workshops, others)
    # ------------------------------------------------------------------
    print("Seeding service departments (ASSIGNED_ONLY: labs / workshops / others)…")
    assigned_dept_ids: dict[str, int] = {}
    for dept_name in SERVICE_DEPARTMENTS_ASSIGNED:
        dept_id = upsert_returning_id(session, Department, ["name"], {
            "name": dept_name,
            "kind": DepartmentKind.service,
            "applicability": DepartmentApplicability.ASSIGNED_ONLY,
            "faculty_id": None,
        })
        assigned_dept_ids[dept_name] = dept_id

    session.commit()

    # ------------------------------------------------------------------
    # 7. Users
    # ------------------------------------------------------------------
    print("Seeding users…")

    # Admin (no department)
    upsert_returning_id(session, User, ["email"], {
        "email": "admin@example.edu",
        "full_name": "System Administrator (Demo)",
        "password_hash": pw_hash,
        "role": UserRole.admin,
        "department_id": None,
        "roster_id": None,
        "is_active": True,
        "created_at": now,
    })

    # Registrar/Accounts — attached to R&S Branch
    rs_branch_id = service_dept_ids["R&S Branch"]
    upsert_returning_id(session, User, ["email"], {
        "email": "registrar.accounts@example.edu",
        "full_name": "Accounts Officer (Demo)",
        "password_hash": pw_hash,
        "role": UserRole.registrar_accounts,
        "department_id": rs_branch_id,
        "roster_id": None,
        "is_active": True,
        "created_at": now,
    })

    # Service dept officers for named departments (library, hostel, etc.)
    for dept_name, officer_email in SERVICE_OFFICER_EMAIL_MAP.items():
        dept_id = service_dept_ids.get(dept_name)
        if dept_id is None:
            print(f"  WARN: service dept '{dept_name}' not found, skipping", file=sys.stderr)
            continue
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

    # Service dept officers for ASSIGNED_ONLY labs/workshops/others (generated in loop)
    for dept_name, dept_id in assigned_dept_ids.items():
        slug = (
            dept_name.lower()
            .replace("/", "")
            .replace("-", "")
            .replace(" ", "")
            .replace(".", "")
        )
        email = f"{slug}.officer@example.edu"
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

    # Academic dept officers + HoDs (one each per department)
    for dept_name, dept_id in academic_dept_ids.items():
        slug = DEPT_SLUG[dept_name]
        upsert_returning_id(session, User, ["email"], {
            "email": f"officer.{slug}@example.edu",
            "full_name": f"{dept_name} Officer (Demo)",
            "password_hash": pw_hash,
            "role": UserRole.dept_officer,
            "department_id": dept_id,
            "roster_id": None,
            "is_active": True,
            "created_at": now,
        })
        upsert_returning_id(session, User, ["email"], {
            "email": f"hod.{slug}@example.edu",
            "full_name": f"Chairperson {dept_name} (Demo)",
            "password_hash": pw_hash,
            "role": UserRole.hod,
            "department_id": dept_id,
            "roster_id": None,
            "is_active": True,
            "created_at": now,
        })

    session.commit()

    # ------------------------------------------------------------------
    # 8. Students: roster row + student user + bank details + assigned labs
    # ------------------------------------------------------------------
    print("Seeding students…")
    for s in STUDENTS:
        prog_id = programme_ids.get(s["programme"])
        if prog_id is None:
            print(
                f"  WARN: programme '{s['programme']}' not found, skipping student",
                file=sys.stderr,
            )
            continue

        # Roster
        roster_id = upsert_returning_id(session, StudentRoster, ["registration_number"], {
            "registration_number": s["registration_number"],
            "name": s["name"],
            "email": s["email"],
            "mobile": s["mobile"],
            "address": s["address"],
            "programme_id": prog_id,
            "is_hosteller": s["is_hosteller"],
            "security_deposit_amount": s.get("security_deposit_amount", 0.0),
        })

        # Bank details (upsert on roster_id)
        if s.get("bank"):
            b = s["bank"]
            upsert_returning_id(session, BankDetail, ["roster_id"], {
                "roster_id": roster_id,
                "account_holder_name": b["account_holder_name"],
                "account_number": b["account_number"],
                "ifsc_code": b["ifsc_code"],
                "bank_address": b["bank_address"],
            })

        # Student user (email same as roster email — unique on users table)
        upsert_returning_id(session, User, ["email"], {
            "email": s["email"],
            "full_name": s["name"],
            "password_hash": pw_hash,
            "role": UserRole.student,
            "department_id": None,
            "roster_id": roster_id,
            "is_active": True,
            "created_at": now,
        })

        # Assigned labs / workshops
        for lab_name in s.get("assigned_labs", []):
            dept_id = assigned_dept_ids.get(lab_name)
            if dept_id is None:
                print(f"  WARN: assigned dept '{lab_name}' not found, skipping", file=sys.stderr)
                continue
            stmt = (
                pg_insert(RosterAssignedDepartment)
                .values(roster_id=roster_id, department_id=dept_id)
                .on_conflict_do_nothing(index_elements=["roster_id", "department_id"])
            )
            session.execute(stmt)

    print("Seeding unregistered students (roster only, no user account)…")
    for s in UNREGISTERED_STUDENTS:
        prog_id = programme_ids.get(s["programme"])
        if prog_id is None:
            print(
                f"  WARN: programme '{s['programme']}' not found, skipping student",
                file=sys.stderr,
            )
            continue

        roster_id = upsert_returning_id(session, StudentRoster, ["registration_number"], {
            "registration_number": s["registration_number"],
            "name": s["name"],
            "email": s["email"],
            "mobile": s["mobile"],
            "address": s["address"],
            "programme_id": prog_id,
            "is_hosteller": s["is_hosteller"],
            "security_deposit_amount": s.get("security_deposit_amount", 0.0),
        })

        if s.get("bank"):
            b = s["bank"]
            upsert_returning_id(session, BankDetail, ["roster_id"], {
                "roster_id": roster_id,
                "account_holder_name": b["account_holder_name"],
                "account_number": b["account_number"],
                "ifsc_code": b["ifsc_code"],
                "bank_address": b["bank_address"],
            })

        for lab_name in s.get("assigned_labs", []):
            dept_id = assigned_dept_ids.get(lab_name)
            if dept_id is None:
                continue
            stmt = (
                pg_insert(RosterAssignedDepartment)
                .values(roster_id=roster_id, department_id=dept_id)
                .on_conflict_do_nothing(index_elements=["roster_id", "department_id"])
            )
            session.execute(stmt)

    session.commit()
    print("Seed complete.")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic data for NoDues system")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe all seeded data before re-seeding (only allowed in APP_ENV=development)",
    )
    args = parser.parse_args()

    with SessionLocal() as session:
        if args.reset:
            reset_data(session)
        seed(session)


if __name__ == "__main__":
    main()
