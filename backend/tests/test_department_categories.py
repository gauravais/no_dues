"""
Comprehensive test suite for Department Categories & Academic Structure:
1. Category model properties, computed category, and user-friendly labels.
2. Migration 0012 upgrade/downgrade roundtrip and conversion logic.
3. Student clearance request with lab_workshop_department_ids and other_department_ids.
4. Lab catalog direct_offices and active assigned_only_departments.
5. GET /departments/assigned-only and alias /departments/additional-facilities.
6. Public/authenticated GET /programmes endpoint.
7. Officer queue others_note scoping to additional facilities.
8. Lab courses CSV upload (dry_run, create_missing_offices, change reporting, officerless report).
9. Officer lab-workshops CRUD (/department/lab-workshops).
10. Admin department CRUD (/admin/departments, bulk-category, guards).
11. Admin academic structure CRUD (faculties, academic-departments, programmes, guards).
12. Officer roster programme_id modification guard.
13. Admin staff user PATCH /admin/users/{id} with unlink_google guard.
"""

import io
import os
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, inspect, text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import hash_password
from backend.app.core.crypto import encrypt_bank_account
from backend.app.models.university import (
    Department, Programme, Faculty, DepartmentKind, DepartmentApplicability,
)
from backend.app.models.user import User, UserRole, UserDepartment
from backend.app.models.roster import StudentRoster
from backend.app.models.bank import BankDetail
from backend.app.models.clearance import (
    ClearanceRequest, DepartmentApproval, ClearanceStatus, ApprovalStatus,
)
from backend.app.models.lab_course import LabCourse
from tests.conftest import make_auth_headers, TEST_DATABASE_URL


def _get_alembic_config():
    ini_path = "alembic.ini" if os.path.exists("alembic.ini") else "backend/alembic.ini"
    cfg = Config(ini_path)
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    if os.path.exists("backend/alembic") and not os.path.exists("alembic"):
        cfg.set_main_option("script_location", "backend/alembic")
    return cfg


def _get_or_create_admin(db: Session) -> User:
    admin = db.execute(select(User).where(User.role == UserRole.admin)).scalars().first()
    if not admin:
        admin = User(
            email="admin.cat@svsu.ac.in",
            full_name="Admin",
            password_hash=hash_password("adminpass123"),
            role=UserRole.admin,
            is_active=True,
        )
        db.add(admin)
        db.flush()
    return admin


def _get_or_create_academic_officer(db: Session) -> tuple[User, Department, Programme]:
    acad_dept = db.execute(
        select(Department).where(Department.kind == DepartmentKind.academic)
    ).scalars().first()
    if not acad_dept:
        faculty = db.execute(select(Faculty)).scalars().first()
        if not faculty:
            faculty = Faculty(name="Skill Faculty of Test", short_code="SFT")
            db.add(faculty)
            db.flush()
        acad_dept = Department(
            name="Skill Department of Test CS",
            kind=DepartmentKind.academic,
            applicability=DepartmentApplicability.OWN_ACADEMIC,
            faculty_id=faculty.id,
            is_active=True,
        )
        db.add(acad_dept)
        db.flush()

    prog = db.execute(
        select(Programme).where(Programme.academic_department_id == acad_dept.id)
    ).scalars().first()
    if not prog:
        prog = Programme(name="Test B.Tech CS", academic_department_id=acad_dept.id, is_active=True)
        db.add(prog)
        db.flush()

    officer = db.execute(
        select(User).where(User.role == UserRole.dept_officer, User.department_id == acad_dept.id)
    ).scalars().first()
    if not officer:
        officer = User(
            email=f"acad.officer.{acad_dept.id}@svsu.ac.in",
            full_name="Academic Officer",
            password_hash=hash_password("officerpass123"),
            role=UserRole.dept_officer,
            department_id=acad_dept.id,
            is_active=True,
        )
        db.add(officer)
        db.flush()
        db.add(UserDepartment(user_id=officer.id, department_id=acad_dept.id))
        db.flush()

    return officer, acad_dept, prog


# ---------------------------------------------------------------------------
# 1. Category Model & Properties
# ---------------------------------------------------------------------------

def test_department_category_properties():
    acad = Department(name="Dept A", kind=DepartmentKind.academic, applicability=DepartmentApplicability.OWN_ACADEMIC)
    assert acad.category == "ACADEMIC"
    assert acad.label == "Academic department"

    univ = Department(name="Library", kind=DepartmentKind.service, applicability=DepartmentApplicability.ALWAYS)
    assert univ.category == "UNIVERSITY_OFFICE"
    assert univ.label == "University office"

    hostel = Department(name="Hostel (Boys)", kind=DepartmentKind.service, applicability=DepartmentApplicability.HOSTELLER_ONLY)
    assert hostel.category == "HOSTEL"
    assert hostel.label == "Hostel"

    lab = Department(name="Robotics Lab", kind=DepartmentKind.service, applicability=DepartmentApplicability.LAB_WORKSHOP)
    assert lab.category == "LAB_WORKSHOP"
    assert lab.label == "Lab / Workshop"

    facility = Department(name="Others", kind=DepartmentKind.service, applicability=DepartmentApplicability.ASSIGNED_ONLY)
    assert facility.category == "ADDITIONAL_FACILITY"
    assert facility.label == "Additional facility"

    # Strict constraint: Never contain raw "service" or "assigned-only"
    for dept in [acad, univ, hostel, lab, facility]:
        assert "service" not in dept.label.lower()
        assert "assigned-only" not in dept.label.lower()


# ---------------------------------------------------------------------------
# 2. Migration 0012 Roundtrip
# ---------------------------------------------------------------------------

def test_migration_0012_roundtrip(test_engine):
    alembic_cfg = _get_alembic_config()

    # Downgrade to 0011
    command.downgrade(alembic_cfg, "0011_user_departments")
    insp_down = inspect(test_engine)
    dept_cols_down = [c["name"] for c in insp_down.get_columns("departments")]
    assert "is_active" not in dept_cols_down
    assert "created_by_user_id" not in dept_cols_down
    prog_cols_down = [c["name"] for c in insp_down.get_columns("programmes")]
    assert "is_active" not in prog_cols_down

    # Upgrade back to head (0012)
    command.upgrade(alembic_cfg, "head")
    insp_up = inspect(test_engine)
    dept_cols_up = [c["name"] for c in insp_up.get_columns("departments")]
    assert "is_active" in dept_cols_up
    assert "created_by_user_id" in dept_cols_up
    prog_cols_up = [c["name"] for c in insp_up.get_columns("programmes")]
    assert "is_active" in prog_cols_up


# ---------------------------------------------------------------------------
# 3. GET /departments, /assigned-only, and /additional-facilities
# ---------------------------------------------------------------------------

def test_department_listing_categories(client, db_session):
    admin = _get_or_create_admin(db_session)
    headers = make_auth_headers(admin.id)

    # GET /departments
    resp = client.get("/departments", headers=headers)
    assert resp.status_code == 200
    depts = resp.json()
    assert len(depts) > 0
    first = depts[0]
    assert "category" in first
    assert "label" in first
    assert "is_active" in first
    for d in depts:
        assert d["category"] in {"ACADEMIC", "UNIVERSITY_OFFICE", "HOSTEL", "LAB_WORKSHOP", "ADDITIONAL_FACILITY"}
        assert "service" not in d["label"].lower()
        assert "assigned-only" not in d["label"].lower()

    # GET /departments/assigned-only
    resp_ao = client.get("/departments/assigned-only", headers=headers)
    assert resp_ao.status_code == 200
    ao_depts = resp_ao.json()
    for d in ao_depts:
        assert d["category"] == "ADDITIONAL_FACILITY"

    # GET /departments/additional-facilities alias
    resp_alias = client.get("/departments/additional-facilities", headers=headers)
    assert resp_alias.status_code == 200
    assert resp_alias.json() == resp_ao.json()


# ---------------------------------------------------------------------------
# 4. GET /programmes
# ---------------------------------------------------------------------------

def test_get_programmes(client, db_session):
    admin = _get_or_create_admin(db_session)
    headers = make_auth_headers(admin.id)

    resp = client.get("/programmes", headers=headers)
    assert resp.status_code == 200
    progs = resp.json()
    assert len(progs) > 0
    p = progs[0]
    assert "id" in p
    assert "name" in p
    assert "academic_department_id" in p
    assert "academic_department_name" in p
    assert "faculty_name" in p


# ---------------------------------------------------------------------------
# 5. Student Request with lab_workshop_department_ids & other_department_ids
# ---------------------------------------------------------------------------

def test_student_request_lab_workshops_and_others(client, db_session):
    # Ensure active Lab/Workshop department with active officer
    lab_dept = Department(
        name="Advanced AI Lab",
        kind=DepartmentKind.service,
        applicability=DepartmentApplicability.LAB_WORKSHOP,
        is_active=True,
    )
    db_session.add(lab_dept)
    db_session.flush()

    lab_officer = User(
        email="ai.officer@svsu.ac.in",
        full_name="AI Lab Officer",
        password_hash=hash_password("pw12345678"),
        role=UserRole.dept_officer,
        department_id=lab_dept.id,
        is_active=True,
    )
    db_session.add(lab_officer)
    db_session.flush()
    db_session.add(UserDepartment(user_id=lab_officer.id, department_id=lab_dept.id))

    # Ensure active Additional Facility ("Others") with active officer
    others_dept = db_session.execute(
        select(Department).where(Department.name == "Others")
    ).scalar_one_or_none()
    if not others_dept:
        others_dept = Department(
            name="Others",
            kind=DepartmentKind.service,
            applicability=DepartmentApplicability.ASSIGNED_ONLY,
            is_active=True,
        )
        db_session.add(others_dept)
        db_session.flush()

    others_officer = db_session.execute(
        select(User).where(User.email == "others.officer@svsu.ac.in")
    ).scalar_one_or_none()
    if not others_officer:
        others_officer = User(
            email="others.officer@svsu.ac.in",
            full_name="Others Officer",
            password_hash=hash_password("pw12345678"),
            role=UserRole.dept_officer,
            department_id=others_dept.id,
            is_active=True,
        )
        db_session.add(others_officer)
        db_session.flush()
        db_session.add(UserDepartment(user_id=others_officer.id, department_id=others_dept.id))

    acad_officer, acad_dept, prog = _get_or_create_academic_officer(db_session)

    # Create Student
    roster = StudentRoster(
        registration_number="REG_CAT_01",
        name="Category Student",
        email="cat.student@svsu.ac.in",
        mobile="9876543210",
        address="Campus",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=Decimal("5000.00"),
    )
    db_session.add(roster)
    db_session.flush()

    student = User(
        email="cat.student@svsu.ac.in",
        full_name="Category Student",
        password_hash=hash_password("studentpass123"),
        role=UserRole.student,
        roster_id=roster.id,
        is_active=True,
    )
    db_session.add(student)
    db_session.flush()

    bank = BankDetail(
        roster_id=roster.id,
        _account_number=encrypt_bank_account("1234567890"),
        account_holder_name="Category Student",
        ifsc_code="SBIN0001234",
        bank_address="State Bank of India, Main Branch",
    )
    db_session.add(bank)
    db_session.commit()

    student_headers = make_auth_headers(student.id)

    # Check GET /student/lab-catalog returns direct_offices
    resp_cat = client.get("/student/lab-catalog", headers=student_headers)
    assert resp_cat.status_code == 200
    cat_data = resp_cat.json()
    assert "direct_offices" in cat_data
    assert any(o["id"] == lab_dept.id for o in cat_data["direct_offices"])
    assert any(o["id"] == others_dept.id for o in cat_data["assigned_only_departments"])

    # Apply clearance specifying lab_workshop_department_ids and other_department_ids
    payload = {
        "is_hosteller": False,
        "lab_course_ids": [],
        "lab_workshop_department_ids": [lab_dept.id],
        "other_department_ids": [others_dept.id],
        "others_note": "Utilized advanced robotics kit",
    }
    resp_apply = client.post("/student/requests", json=payload, headers=student_headers)
    assert resp_apply.status_code == 201
    req_data = resp_apply.json()

    approval_dept_ids = [a["department_id"] for a in req_data["approvals"]]
    assert lab_dept.id in approval_dept_ids
    assert others_dept.id in approval_dept_ids

    # Verify category and label in approvals response
    for a in req_data["approvals"]:
        if a["department_id"] == lab_dept.id:
            assert a["department_category"] == "LAB_WORKSHOP"
            assert a["department_label"] == "Lab / Workshop"
        elif a["department_id"] == others_dept.id:
            assert a["department_category"] == "ADDITIONAL_FACILITY"
            assert a["department_label"] == "Additional facility"


# ---------------------------------------------------------------------------
# 6. Officer Queue others_note Scoping
# ---------------------------------------------------------------------------

def test_officer_queue_others_note_scoping(client, db_session):
    # Setup lab_dept and others_dept
    lab_dept = Department(
        name="Scope Lab",
        kind=DepartmentKind.service,
        applicability=DepartmentApplicability.LAB_WORKSHOP,
        is_active=True,
    )
    others_dept = Department(
        name="Scope Facility",
        kind=DepartmentKind.service,
        applicability=DepartmentApplicability.ASSIGNED_ONLY,
        is_active=True,
    )
    db_session.add_all([lab_dept, others_dept])
    db_session.flush()

    lab_officer = User(
        email="scope.lab.officer@svsu.ac.in",
        full_name="Scope Lab Officer",
        password_hash=hash_password("pw12345678"),
        role=UserRole.dept_officer,
        department_id=lab_dept.id,
        is_active=True,
    )
    others_officer = User(
        email="scope.others.officer@svsu.ac.in",
        full_name="Scope Others Officer",
        password_hash=hash_password("pw12345678"),
        role=UserRole.dept_officer,
        department_id=others_dept.id,
        is_active=True,
    )
    db_session.add_all([lab_officer, others_officer])
    db_session.flush()
    db_session.add(UserDepartment(user_id=lab_officer.id, department_id=lab_dept.id))
    db_session.add(UserDepartment(user_id=others_officer.id, department_id=others_dept.id))

    acad_officer, acad_dept, prog = _get_or_create_academic_officer(db_session)

    roster = StudentRoster(
        registration_number="REG_SCOPE_01",
        name="Scope Student",
        email="scope.student@svsu.ac.in",
        mobile="9876543210",
        address="Campus",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=Decimal("5000.00"),
    )
    db_session.add(roster)
    db_session.flush()

    student = User(
        email="scope.student@svsu.ac.in",
        full_name="Scope Student",
        password_hash=hash_password("studentpass123"),
        role=UserRole.student,
        roster_id=roster.id,
        is_active=True,
    )
    db_session.add(student)
    db_session.flush()

    bank = BankDetail(
        roster_id=roster.id,
        _account_number=encrypt_bank_account("1234567890"),
        account_holder_name="Scope Student",
        ifsc_code="SBIN0001234",
        bank_address="Main Branch",
    )
    db_session.add(bank)
    db_session.commit()

    student_headers = make_auth_headers(student.id)
    payload = {
        "is_hosteller": False,
        "lab_course_ids": [],
        "lab_workshop_department_ids": [lab_dept.id],
        "other_department_ids": [others_dept.id],
        "others_note": "Special gear requested",
    }
    resp = client.post("/student/requests", json=payload, headers=student_headers)
    assert resp.status_code == 201

    # Others officer queue SHOULD see others_note
    others_headers = make_auth_headers(others_officer.id)
    resp_others = client.get("/department/queue", headers=others_headers)
    assert resp_others.status_code == 200
    items = resp_others.json()["items"]
    target_item = next((i for i in items if i["registration_number"] == "REG_SCOPE_01"), None)
    assert target_item is not None
    assert target_item["others_note"] == "Special gear requested"

    # Lab officer queue should NOT see others_note
    lab_headers = make_auth_headers(lab_officer.id)
    resp_lab = client.get("/department/queue", headers=lab_headers)
    assert resp_lab.status_code == 200
    lab_items = resp_lab.json()["items"]
    target_lab_item = next((i for i in lab_items if i["registration_number"] == "REG_SCOPE_01"), None)
    assert target_lab_item is not None
    assert target_lab_item["others_note"] is None


# ---------------------------------------------------------------------------
# 7. Officer Lab/Workshop CRUD (/department/lab-workshops)
# ---------------------------------------------------------------------------

def test_officer_lab_workshops_crud(client, db_session):
    acad_officer, acad_dept, prog = _get_or_create_academic_officer(db_session)
    headers = make_auth_headers(acad_officer.id)

    # 1. Create a new lab/workshop
    resp = client.post("/department/lab-workshops", json={"name": "Cybernetics Workshop"}, headers=headers)
    assert resp.status_code == 201
    created = resp.json()
    dept_id = created["id"]
    assert created["name"] == "Cybernetics Workshop"
    assert created["category"] == "LAB_WORKSHOP"
    assert created["editable"] is True
    assert created["created_by_me"] is True

    # Check department ownership
    dept_db = db_session.get(Department, dept_id)
    assert dept_db.created_by_user_id == acad_officer.id

    # 2. List lab workshops
    resp_list = client.get("/department/lab-workshops", headers=headers)
    assert resp_list.status_code == 200
    items = resp_list.json()
    item = next((x for x in items if x["id"] == dept_id), None)
    assert item is not None
    assert item["editable"] is True

    # 3. Patch lab workshop
    resp_patch = client.patch(f"/department/lab-workshops/{dept_id}", json={"name": "Cybernetics & AI Lab"}, headers=headers)
    assert resp_patch.status_code == 200
    assert resp_patch.json()["name"] == "Cybernetics & AI Lab"

    # 4. Another officer cannot edit it
    other_officer = User(
        email="other.officer.edit@svsu.ac.in",
        full_name="Other Officer",
        password_hash=hash_password("pw12345678"),
        role=UserRole.dept_officer,
        department_id=acad_dept.id,
        is_active=True,
    )
    db_session.add(other_officer)
    db_session.commit()

    resp_forbidden = client.patch(
        f"/department/lab-workshops/{dept_id}",
        json={"name": "Hacked Lab"},
        headers=make_auth_headers(other_officer.id),
    )
    assert resp_forbidden.status_code == 403


# ---------------------------------------------------------------------------
# 8. Lab Courses CSV Upload (dry_run, create_missing_offices, change reporting)
# ---------------------------------------------------------------------------

def test_lab_courses_csv_upload_advanced(client, db_session):
    acad_officer, acad_dept, prog = _get_or_create_academic_officer(db_session)
    headers = make_auth_headers(acad_officer.id)

    # Ensure an active Lab/Workshop office exists
    existing_lab = Department(
        name="Existing Cyber Lab",
        kind=DepartmentKind.service,
        applicability=DepartmentApplicability.LAB_WORKSHOP,
        is_active=True,
    )
    db_session.add(existing_lab)
    db_session.commit()

    csv_content = (
        "code,name,lab_office,specialization\n"
        f"CYBER-101,Network Security Lab,{existing_lab.name},Cyber\n"
        "AUTO-101,Engine Dyno Lab,New Testing Bay,Automotive\n"
    )

    # Dry run with missing office -> should report offices_to_create
    files = {"file": ("courses.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    resp_dry = client.post("/department/lab-courses/upload?dry_run=true", files=files, headers=headers)
    assert resp_dry.status_code == 200
    dry_data = resp_dry.json()
    assert dry_data["dry_run"] is True
    assert "New Testing Bay" in dry_data["offices_to_create"]
    assert db_session.execute(select(LabCourse).where(LabCourse.code == "AUTO-101")).scalar_one_or_none() is None

    # Upload with create_missing_offices=true
    files2 = {"file": ("courses.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    resp_real = client.post("/department/lab-courses/upload?create_missing_offices=true", files=files2, headers=headers)
    assert resp_real.status_code == 200
    real_data = resp_real.json()
    assert real_data["dry_run"] is False
    assert real_data["created_count"] == 2
    assert "New Testing Bay" in real_data["offices_without_officers"]

    # Re-upload with office change
    alt_lab = Department(
        name="Alternative Cyber Lab",
        kind=DepartmentKind.service,
        applicability=DepartmentApplicability.LAB_WORKSHOP,
        is_active=True,
    )
    db_session.add(alt_lab)
    db_session.commit()

    csv_changed = (
        "code,name,lab_office,specialization\n"
        f"CYBER-101,Network Security Lab,{alt_lab.name},Cyber\n"
    )
    files3 = {"file": ("courses.csv", io.BytesIO(csv_changed.encode("utf-8")), "text/csv")}
    resp_change = client.post("/department/lab-courses/upload", files=files3, headers=headers)
    assert resp_change.status_code == 200
    change_data = resp_change.json()
    assert change_data["updated_count"] == 1
    assert any("changed from" in r["status"] for r in change_data["rows"])


# ---------------------------------------------------------------------------
# 9. Admin Department CRUD & Category Guards
# ---------------------------------------------------------------------------

def test_admin_departments_crud_and_guards(client, db_session):
    admin = _get_or_create_admin(db_session)
    headers = make_auth_headers(admin.id)

    # 1. GET /admin/departments
    resp = client.get("/admin/departments", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) > 0
    dept_entry = data["items"][0]
    assert "open_approvals_count" in dept_entry
    assert "subject_count" in dept_entry
    assert "officer_count" in dept_entry

    # 2. POST /admin/departments
    create_payload = {
        "name": "Robotics & Automation Lab Unique",
        "category": "LAB_WORKSHOP",
        "faculty_id": None,
    }
    resp_create = client.post("/admin/departments", json=create_payload, headers=headers)
    assert resp_create.status_code == 201
    created_dept = resp_create.json()
    dept_id = created_dept["id"]
    assert created_dept["category"] == "LAB_WORKSHOP"

    # 3. PATCH /admin/departments/{id}
    patch_payload = {
        "name": "Robotics Lab Core Unique",
        "category": "ADDITIONAL_FACILITY",
    }
    resp_patch = client.patch(f"/admin/departments/{dept_id}", json=patch_payload, headers=headers)
    assert resp_patch.status_code == 200
    assert resp_patch.json()["name"] == "Robotics Lab Core Unique"
    assert resp_patch.json()["category"] == "ADDITIONAL_FACILITY"

    # 4. Bulk Category Update
    bulk_payload = {
        "department_ids": [dept_id],
        "category": "LAB_WORKSHOP",
    }
    resp_bulk = client.post("/admin/departments/bulk-category", json=bulk_payload, headers=headers)
    assert resp_bulk.status_code == 200
    assert resp_bulk.json()["updated_count"] == 1

    # 5. Guard: Deactivating department with open clearance request fails with 409
    # Create request and approval
    acad_officer, acad_dept, prog = _get_or_create_academic_officer(db_session)
    roster = StudentRoster(
        registration_number="REG_DEACT_01",
        name="Deact Student",
        email="deact.student@svsu.ac.in",
        mobile="9876543210",
        address="Campus",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=Decimal("5000.00"),
    )
    db_session.add(roster)
    db_session.flush()

    open_req = ClearanceRequest(
        roster_id=roster.id,
        status=ClearanceStatus.SUBMITTED,
    )
    db_session.add(open_req)
    db_session.flush()

    app = DepartmentApproval(
        request_id=open_req.id,
        department_id=dept_id,
        status=ApprovalStatus.PENDING,
    )
    db_session.add(app)
    db_session.commit()

    resp_deact = client.patch(f"/admin/departments/{dept_id}", json={"is_active": False}, headers=headers)
    assert resp_deact.status_code == 409
    assert "open approvals on active clearance requests" in resp_deact.json()["detail"]

    # Clean up test approval and request
    db_session.delete(app)
    db_session.delete(open_req)
    db_session.delete(roster)
    db_session.commit()

    # 6. DELETE /admin/departments/{id}
    resp_del = client.delete(f"/admin/departments/{dept_id}", headers=headers)
    assert resp_del.status_code == 200
    assert "successfully deleted" in resp_del.json()["detail"]


# ---------------------------------------------------------------------------
# 10. Admin Academic Structure CRUD (Faculties, Depts, Programmes)
# ---------------------------------------------------------------------------

def test_admin_academic_structure_crud(client, db_session):
    admin = _get_or_create_admin(db_session)
    headers = make_auth_headers(admin.id)

    # 1. Faculty
    resp_f = client.post("/admin/faculties", json={"name": "Faculty of Sciences", "short_code": "FOS"}, headers=headers)
    assert resp_f.status_code == 201
    faculty_id = resp_f.json()["id"]

    resp_f_list = client.get("/admin/faculties", headers=headers)
    assert resp_f_list.status_code == 200
    assert any(f["id"] == faculty_id for f in resp_f_list.json())

    # 2. Academic Department
    resp_ad = client.post("/admin/academic-departments", json={"name": "Dept of Applied Physics", "faculty_id": faculty_id}, headers=headers)
    assert resp_ad.status_code == 201
    acad_dept_id = resp_ad.json()["id"]

    resp_ad_list = client.get("/admin/academic-departments", headers=headers)
    assert resp_ad_list.status_code == 200
    assert any(d["id"] == acad_dept_id for d in resp_ad_list.json())

    # 3. Programme
    resp_prog = client.post("/admin/programmes", json={"name": "B.Sc. Applied Physics", "academic_department_id": acad_dept_id}, headers=headers)
    assert resp_prog.status_code == 201
    prog_id = resp_prog.json()["id"]

    resp_p_list = client.get("/admin/programmes", headers=headers)
    assert resp_p_list.status_code == 200
    assert any(p["id"] == prog_id for p in resp_p_list.json())


# ---------------------------------------------------------------------------
# 11. Staff User PATCH /admin/users/{id}
# ---------------------------------------------------------------------------

def test_admin_patch_staff_user(client, db_session):
    admin = _get_or_create_admin(db_session)
    headers = make_auth_headers(admin.id)

    acad_dept = db_session.execute(
        select(Department).where(Department.name == "Skill Department of CS/IT")
    ).scalar_one()

    # Create staff user with google_sub and valid department
    staff = User(
        email="staff.patch@svsu.ac.in",
        full_name="Staff Patch Old",
        password_hash=None,
        google_sub="google_sub_12345",
        role=UserRole.dept_officer,
        department_id=acad_dept.id,
        is_active=True,
    )
    db_session.add(staff)
    db_session.commit()

    # Changing email without unlink_google should fail with 409
    resp_fail = client.patch(
        f"/admin/users/{staff.id}",
        json={"email": "staff.patch.new@svsu.ac.in"},
        headers=headers,
    )
    assert resp_fail.status_code == 409
    assert "unlink_google=true" in resp_fail.json()["detail"]

    # Changing email with unlink_google=true succeeds
    resp_ok = client.patch(
        f"/admin/users/{staff.id}",
        json={"email": "staff.patch.new@svsu.ac.in", "full_name": "Staff Patch New", "unlink_google": True},
        headers=headers,
    )
    assert resp_ok.status_code == 200
    updated = resp_ok.json()
    assert updated["email"] == "staff.patch.new@svsu.ac.in"
    assert updated["full_name"] == "Staff Patch New"

    db_session.refresh(staff)
    assert staff.google_sub is None


# ---------------------------------------------------------------------------
# 12. Officer Roster Programme Modification Guard
# ---------------------------------------------------------------------------

def test_officer_roster_programme_modification_guard(client, db_session):
    acad_officer, acad_dept, prog1 = _get_or_create_academic_officer(db_session)
    headers = make_auth_headers(acad_officer.id)

    # Create second programme in same academic department
    prog2 = Programme(name="B.Tech CS Special Track", academic_department_id=acad_dept.id, is_active=True)
    db_session.add(prog2)

    # Create third programme in another academic department
    other_acad = Department(
        name="Other Acad Dept",
        kind=DepartmentKind.academic,
        applicability=DepartmentApplicability.OWN_ACADEMIC,
        faculty_id=acad_dept.faculty_id,
        is_active=True,
    )
    db_session.add(other_acad)
    db_session.flush()
    prog_other = Programme(name="Other Engineering Track", academic_department_id=other_acad.id, is_active=True)
    db_session.add(prog_other)
    db_session.flush()

    # Create student on prog1
    roster = StudentRoster(
        registration_number="REG_PROG_CHANGE",
        name="Prog Change Student",
        email="prog.change@svsu.ac.in",
        mobile="9876543210",
        address="Campus",
        programme_id=prog1.id,
        is_hosteller=False,
        security_deposit_amount=Decimal("5000.00"),
    )
    db_session.add(roster)
    db_session.commit()

    # 1. Update programme_id to prog2 (same academic department, no open request) -> 200
    resp_ok = client.patch(f"/department/roster/{roster.id}", json={"programme_id": prog2.id}, headers=headers)
    assert resp_ok.status_code == 200
    assert resp_ok.json()["programme_id"] == prog2.id

    # 2. Update programme_id to prog_other (different academic department) -> 403 Forbidden
    resp_other = client.patch(f"/department/roster/{roster.id}", json={"programme_id": prog_other.id}, headers=headers)
    assert resp_other.status_code == 403

    # 3. Open request created -> change programme_id should fail with 409
    req = ClearanceRequest(roster_id=roster.id, status=ClearanceStatus.SUBMITTED)
    db_session.add(req)
    db_session.commit()

    resp_conflict = client.patch(f"/department/roster/{roster.id}", json={"programme_id": prog1.id}, headers=headers)
    assert resp_conflict.status_code == 409
    assert "open clearance request" in resp_conflict.json()["detail"]


# ---------------------------------------------------------------------------
# 13. Role Permissions Guards for New Endpoints
# ---------------------------------------------------------------------------

def test_role_permissions_guards(client, db_session):
    acad_officer, acad_dept, prog = _get_or_create_academic_officer(db_session)
    officer_headers = make_auth_headers(acad_officer.id)

    # Department officer forbidden from Admin endpoints
    resp_admin = client.get("/admin/departments", headers=officer_headers)
    assert resp_admin.status_code == 403

    resp_fac = client.post("/admin/faculties", json={"name": "Hacked", "short_code": "H"}, headers=officer_headers)
    assert resp_fac.status_code == 403

    # Service officer forbidden from academic roster & lab-workshops endpoints
    service_dept = db_session.execute(
        select(Department).where(Department.kind == DepartmentKind.service)
    ).scalars().first()
    service_officer = User(
        email="service.guard.test@svsu.ac.in",
        full_name="Service Officer",
        password_hash=hash_password("pw12345678"),
        role=UserRole.dept_officer,
        department_id=service_dept.id,
        is_active=True,
    )
    db_session.add(service_officer)
    db_session.commit()

    serv_headers = make_auth_headers(service_officer.id)
    resp_serv = client.get("/department/lab-workshops", headers=serv_headers)
    assert resp_serv.status_code == 403

