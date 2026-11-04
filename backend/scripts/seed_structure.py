"""
Production-safe seed script for university structure.

Seeds faculties, departments (academic and service), programmes, labs, and workshops.
Creates ZERO users, ZERO students, and ZERO credentials.
Safe to run in production, staging, and development.
Idempotent: running multiple times does not duplicate data.

Usage:
    uv run python -m scripts.seed_structure
    uv run python -m scripts.seed_structure --yes
"""

import argparse
import os
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv

# Ensure .env is loaded if present
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.app.core.config import settings
from backend.app.core.database import SessionLocal, engine
from backend.app.models.university import (
    Department,
    DepartmentApplicability,
    DepartmentKind,
    Faculty,
    Programme,
)

# ---------------------------------------------------------------------------
# UNIVERSITY STRUCTURE CONSTANTS
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

PROGRAMMES: dict[str, list[str]] = {
    "Skill Department of CS/IT": [
        "Master of Computer Application (MCA)",
        "Bachelor of Technology (B.Tech.) Computer Science & Engineering",
        "Bachelor of Technology (B.Tech.) Computer Engineering",
        "Bachelor in Computer Applications (BCA)",
        "Diploma in Computer (Generative AI/ Cyber Security)",
        "Diploma in Computer Science & Engineering",
    ],
    "Skill Department of Industry 4.0": [
        "Diploma in Industrial Electronics",
        "Bachelor of Vocation Robotics and Automation",
        "Master of Technology Robotics and Automation",
        "PG Diploma in Semiconductor Device Packaging",
    ],
    "Skill Department of Construction Management and Technology": [
        "Diploma of Vocation Draughtsmanship (Civil)",
        "Undergraduate Diploma in Interior Design",
        "Diploma in Civil Engineering",
    ],
    "Skill Department of Automotive Studies": [
        "Diploma of Vocation Mechanical Manufacturing",
        "Diploma in Mechanical Engineering",
        "Bachelor of Vocation Mechanical Manufacturing",
        "Bachelor of Technology Mechanical and Smart Manufacturing",
        "Bachelor of Vocation Mechatronics",
    ],
    "Skill Department of Green Technology": [
        "Bachelor of Vocation Solar Technology",
        "Bachelor of Vocation (Refrigeration and Air Conditioning)",
        "Bachelor of Technology Electrical Engineering",
    ],
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
ASSIGNED_ONLY_LABS = [f"Lab-{i}" for i in range(1, 10)]  # Lab-1 to Lab-9
ASSIGNED_ONLY_WORKSHOPS = [f"Workshop-{i}" for i in range(1, 4)]  # Workshop-1 to Workshop-3
ASSIGNED_ONLY_OTHERS = ["Others"]
SERVICE_DEPARTMENTS_ASSIGNED = (
    ASSIGNED_ONLY_LABS + ASSIGNED_ONLY_WORKSHOPS + ASSIGNED_ONLY_OTHERS
)


def upsert_returning_id(session, model, conflict_cols: list[str], values: dict) -> int:
    """PostgreSQL INSERT … ON CONFLICT DO UPDATE, then SELECT the row ID."""
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


def seed_structure(session) -> dict:
    """
    Idempotently seeds all university structure.
    Does NOT seed users, students, credentials, or audit logs.
    """
    print("Seeding university structure…")

    # 1. Faculty
    print("  - Faculty…")
    faculty_id = upsert_returning_id(
        session,
        Faculty,
        ["name"],
        {
            "name": FACULTY["name"],
            "short_code": FACULTY["short_code"],
        },
    )

    # 2. Academic departments
    print("  - Academic departments…")
    academic_dept_ids: dict[str, int] = {}
    for dept_name in ACADEMIC_DEPARTMENTS:
        dept_id = upsert_returning_id(
            session,
            Department,
            ["name"],
            {
                "name": dept_name,
                "kind": DepartmentKind.academic,
                "applicability": DepartmentApplicability.OWN_ACADEMIC,
                "faculty_id": faculty_id,
            },
        )
        academic_dept_ids[dept_name] = dept_id

    # 3. Programmes
    print("  - Programmes…")
    programme_ids: dict[str, int] = {}
    for dept_name, prog_list in PROGRAMMES.items():
        dept_id = academic_dept_ids[dept_name]
        for prog_name in prog_list:
            prog_id = upsert_returning_id(
                session,
                Programme,
                ["name"],
                {
                    "name": prog_name,
                    "academic_department_id": dept_id,
                },
            )
            programme_ids[prog_name] = prog_id

    # 4. Service departments — ALWAYS
    print("  - Service departments (ALWAYS)…")
    service_dept_ids: dict[str, int] = {}
    for dept_name in SERVICE_DEPARTMENTS_ALWAYS:
        dept_id = upsert_returning_id(
            session,
            Department,
            ["name"],
            {
                "name": dept_name,
                "kind": DepartmentKind.service,
                "applicability": DepartmentApplicability.ALWAYS,
                "faculty_id": None,
            },
        )
        service_dept_ids[dept_name] = dept_id

    # 5. Service departments — HOSTELLER_ONLY
    print("  - Service departments (HOSTELLER_ONLY)…")
    for dept_name in SERVICE_DEPARTMENTS_HOSTELLER:
        dept_id = upsert_returning_id(
            session,
            Department,
            ["name"],
            {
                "name": dept_name,
                "kind": DepartmentKind.service,
                "applicability": DepartmentApplicability.HOSTELLER_ONLY,
                "faculty_id": None,
            },
        )
        service_dept_ids[dept_name] = dept_id

    # 6. Service departments — ASSIGNED_ONLY (labs, workshops, others)
    print("  - Service departments (ASSIGNED_ONLY: labs / workshops / others)…")
    assigned_dept_ids: dict[str, int] = {}
    for dept_name in SERVICE_DEPARTMENTS_ASSIGNED:
        dept_id = upsert_returning_id(
            session,
            Department,
            ["name"],
            {
                "name": dept_name,
                "kind": DepartmentKind.service,
                "applicability": DepartmentApplicability.ASSIGNED_ONLY,
                "faculty_id": None,
            },
        )
        assigned_dept_ids[dept_name] = dept_id

    session.commit()
    print("Structure seeded successfully (0 users created).")

    return {
        "faculty_id": faculty_id,
        "academic_dept_ids": academic_dept_ids,
        "programme_ids": programme_ids,
        "service_dept_ids": service_dept_ids,
        "assigned_dept_ids": assigned_dept_ids,
    }


def get_db_host() -> str:
    """Extract and return only the database host name (never credentials, port, or database name)."""
    try:
        host = engine.url.host
        if host:
            return host.strip()
    except Exception:
        pass
    return "localhost"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed university structure (departments, programmes, labs). Production-safe; creates zero users."
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip interactive confirmation prompt.",
    )
    args = parser.parse_args()

    db_host = get_db_host()
    print(f"Database host: {db_host}")
    print(f"Environment:   {settings.APP_ENV}")

    if not args.yes:
        try:
            confirm = input(f"Type the database host '{db_host}' to confirm before writing: ").strip()
        except EOFError:
            confirm = ""
        if confirm != db_host:
            print("Host confirmation mismatch. Aborted.")
            sys.exit(1)

    with SessionLocal() as session:
        seed_structure(session)


if __name__ == "__main__":
    main()
