"""
Comprehensive tests for Academic Department Delegation, Lab Catalog, Admin Offices,
Active Officer Hardening, and Student Declarations.
"""
import io
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.security import hash_password
from backend.app.models.university import (
    Department,
    Programme,
    DepartmentKind,
    DepartmentApplicability,
)
from backend.app.models.user import User, UserRole, UserDepartment
from backend.app.models.roster import StudentRoster, RosterAssignedDepartment
from backend.app.models.lab_course import LabCourse
from backend.app.models.bank import BankDetail
from backend.app.models.clearance import ClearanceRequest, DepartmentApproval, ClearanceStatus, ApprovalStatus
from backend.app.models.audit import AuditLog
from tests.conftest import make_auth_headers


def _setup_student_with_bank(db: Session, reg_num: str, email: str, prog_name: str = "Bachelor of Technology (B.Tech.) Computer Engineering"):
    prog = db.execute(select(Programme).where(Programme.name == prog_name)).scalars().first()
    roster = StudentRoster(
        registration_number=reg_num,
        name=f"Student {reg_num}",
        email=email,
        mobile="9876543210",
        address="Hostel Campus",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=5000.0,
    )
    db.add(roster)
    db.flush()

    bank = BankDetail(
        roster_id=roster.id,
        account_holder_name=roster.name,
        account_number="123456789012",
        ifsc_code="DEMO0001234",
        bank_address="Main Campus Branch",
    )
    db.add(bank)

    user = User(
        email=email,
        full_name=roster.name,
        password_hash=hash_password("Pass@123"),
        role=UserRole.student,
        roster_id=roster.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(roster)
    return user, roster


def test_service_officer_forbidden_on_academic_routes(client, db_session):
    """Service department officers (e.g. Library) must get 403 on academic roster and lab catalog routes."""
    lib_officer = db_session.execute(
        select(User).where(User.email == "library.officer@example.edu")
    ).scalar_one()
    headers = make_auth_headers(lib_officer.id)

    # 1. Roster list
    resp = client.get("/department/roster", headers=headers)
    assert resp.status_code == 403
    assert "restricted to academic department officers" in resp.json()["detail"]

    # 2. Roster add
    resp = client.post(
        "/department/roster",
        headers=headers,
        json={
            "registration_number": "2026CS999",
            "name": "Test",
            "email": "test999@example.edu",
            "mobile": "9876543210",
            "programme_id": 1,
        },
    )
    assert resp.status_code == 403

    # 3. Roster upload
    csv_file = io.BytesIO(b"registration_number,name,email,mobile,programme\r\n")
    resp = client.post(
        "/department/roster/upload",
        headers=headers,
        files={"file": ("test.csv", csv_file, "text/csv")},
    )
    assert resp.status_code == 403

    # 4. Lab courses list
    resp = client.get("/department/lab-courses", headers=headers)
    assert resp.status_code == 403

    # 5. Lab courses add
    resp = client.post(
        "/department/lab-courses",
        headers=headers,
        json={"code": "LAB101", "name": "Test Lab", "lab_department_id": 4},
    )
    assert resp.status_code == 403


def test_academic_officer_roster_upload(client, db_session):
    """Academic officer uploads CSV: own programmes created/updated, foreign rejected, foreign rows unmodifiable."""
    cs_officer = db_session.execute(
        select(User).where(User.email == "officer.csit@example.edu")
    ).scalar_one()
    headers = make_auth_headers(cs_officer.id)

    # Pre-seed a student belonging to Automotive department
    auto_prog = db_session.execute(
        select(Programme).where(Programme.name == "Bachelor of Technology Mechanical and Smart Manufacturing")
    ).scalar_one()
    auto_student = StudentRoster(
        registration_number="2026AUTO001",
        name="Auto Student",
        email="auto.student001@example.edu",
        mobile="9876543211",
        address="Auto Block",
        programme_id=auto_prog.id,
    )
    db_session.add(auto_student)
    db_session.commit()

    # Pre-seed an existing CS student to verify update
    cs_prog = db_session.execute(
        select(Programme).where(Programme.name == "Bachelor of Technology (B.Tech.) Computer Engineering")
    ).scalar_one()
    cs_student = StudentRoster(
        registration_number="2026CS001",
        name="Old CS Name",
        email="cs001@example.edu",
        mobile="9876543212",
        address="CS Block",
        programme_id=cs_prog.id,
    )
    db_session.add(cs_student)
    db_session.commit()

    csv_data = (
        "registration_number,name,email,mobile,address,programme,is_hosteller,security_deposit_amount\r\n"
        # 1. Valid new student in CS programme -> created
        "2026CS002,New CS Student,cs002@example.edu,9876543213,Hostel A,Bachelor of Technology (B.Tech.) Computer Engineering,true,5000\r\n"
        # 2. Existing CS student -> updated
        "2026CS001,Updated CS Name,cs001@example.edu,9876543212,CS Block 2,Bachelor of Technology (B.Tech.) Computer Engineering,false,5000\r\n"
        # 3. New student for Automotive programme -> rejected (foreign department)
        "2026AUTO002,Foreign Auto,auto002@example.edu,9876543214,Block B,Bachelor of Technology Mechanical and Smart Manufacturing,false,5000\r\n"
        # 4. Attempt to modify existing Automotive student -> rejected (foreign row unmodifiable)
        "2026AUTO001,Hacked Auto,auto.student001@example.edu,9876543211,New Addr,Bachelor of Technology (B.Tech.) Computer Engineering,false,5000\r\n"
        # 5. Invalid email format -> rejected
        "2026CS003,Bad Email,not-an-email,9876543215,Block C,Bachelor of Technology (B.Tech.) Computer Engineering,false,5000\r\n"
    )

    resp = client.post(
        "/department/roster/upload",
        headers=headers,
        files={"file": ("roster.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_rows"] == 5
    assert data["created_count"] == 1
    assert data["updated_count"] == 1
    assert data["rejected_count"] == 3

    # Verify audit log was written
    audit = db_session.execute(
        select(AuditLog).where(AuditLog.action == "ACADEMIC_ROSTER_UPLOADED")
    ).scalar_one_or_none()
    assert audit is not None
    assert audit.details["created"] == 1


def test_academic_officer_roster_crud_and_email_conflict(client, db_session):
    """Roster CRUD scoped to academic department; changing email when user exists returns 409 Conflict."""
    cs_officer = db_session.execute(
        select(User).where(User.email == "officer.csit@example.edu")
    ).scalar_one()
    headers = make_auth_headers(cs_officer.id)

    cs_prog = db_session.execute(
        select(Programme).where(Programme.name == "Bachelor of Technology (B.Tech.) Computer Engineering")
    ).scalar_one()

    # 1. Create single student
    resp = client.post(
        "/department/roster",
        headers=headers,
        json={
            "registration_number": "2026CS050",
            "name": "Priya Sharma",
            "email": "priya.cs050@example.edu",
            "mobile": "9811223344",
            "address": "Gurugram",
            "programme_id": cs_prog.id,
            "is_hosteller": True,
            "security_deposit_amount": 6000.0,
        },
    )
    assert resp.status_code == 201
    created_id = resp.json()["id"]

    # 2. List department roster
    resp = client.get("/department/roster?search=Priya", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["registration_number"] == "2026CS050"

    # 3. Patch before user account exists (can change email)
    resp = client.patch(
        f"/department/roster/{created_id}",
        headers=headers,
        json={"email": "priya.updated@example.edu", "name": "Priya S."},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "priya.updated@example.edu"
    assert resp.json()["name"] == "Priya S."

    # 4. Now create a User account linked to this roster row
    student_user = User(
        email="priya.updated@example.edu",
        full_name="Priya S.",
        password_hash=hash_password("Pass@123"),
        role=UserRole.student,
        roster_id=created_id,
        is_active=True,
    )
    db_session.add(student_user)
    db_session.commit()

    # 5. Patching email NOW must be refused with 409 Conflict
    resp = client.patch(
        f"/department/roster/{created_id}",
        headers=headers,
        json={"email": "priya.conflict@example.edu"},
    )
    assert resp.status_code == 409
    assert "student already has an active user account" in resp.json()["detail"].lower()

    # 6. Patching name works and syncs user.full_name
    resp = client.patch(
        f"/department/roster/{created_id}",
        headers=headers,
        json={"name": "Priya Sharma Final"},
    )
    assert resp.status_code == 200
    db_session.refresh(student_user)
    assert student_user.full_name == "Priya Sharma Final"


def test_academic_lab_catalog_scoping_and_upload(client, db_session):
    """Academic officer lab catalog CRUD, template download, and upload validation."""
    cs_officer = db_session.execute(
        select(User).where(User.email == "officer.csit@example.edu")
    ).scalar_one()
    headers = make_auth_headers(cs_officer.id)

    # 1. Download template
    resp = client.get("/department/lab-courses/template.csv", headers=headers)
    assert resp.status_code == 200
    assert "code,name,lab_office,specialization" in resp.text

    # 2. Add single lab course
    lab1_dept = db_session.execute(
        select(Department).where(Department.name == "Lab-1")
    ).scalar_one()

    resp = client.post(
        "/department/lab-courses",
        headers=headers,
        json={
            "code": "CSE-L101",
            "name": "Data Structures Lab",
            "lab_department_id": lab1_dept.id,
            "specialization": "Core",
        },
    )
    assert resp.status_code == 201
    course_id = resp.json()["id"]

    # 3. Reject non-ASSIGNED_ONLY department (Library is ALWAYS)
    lib_dept = db_session.execute(
        select(Department).where(Department.name == "Library")
    ).scalar_one()
    resp = client.post(
        "/department/lab-courses",
        headers=headers,
        json={
            "code": "CSE-L102",
            "name": "Invalid Lab",
            "lab_department_id": lib_dept.id,
        },
    )
    assert resp.status_code == 400
    assert "LAB_WORKSHOP" in resp.json()["detail"] or "Lab / Workshop" in resp.json()["detail"]

    # 4. Upload CSV
    csv_data = (
        "code,name,lab_office,specialization\r\n"
        "CSE-L103,Web Technologies Lab,Lab-1,Full Stack\r\n"
        "CSE-L104,Operating Systems Lab,NonExistentOffice,Systems\r\n"
    )
    resp = client.post(
        "/department/lab-courses/upload",
        headers=headers,
        files={"file": ("labs.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created_count"] == 1
    assert data["rejected_count"] == 1

    # 5. List courses (only CS courses)
    resp = client.get("/department/lab-courses", headers=headers)
    assert resp.status_code == 200
    codes = [c["code"] for c in resp.json()["items"]]
    assert "CSE-L101" in codes
    assert "CSE-L103" in codes

    # 6. Patch course
    resp = client.patch(
        f"/department/lab-courses/{course_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_admin_offices_and_user_directory_filters(client, db_session):
    """Admin office staffing status (missing_officer, missing_hod) and user filters."""
    admin_user = db_session.execute(
        select(User).where(User.email == "admin@example.edu")
    ).scalar_one()
    headers = make_auth_headers(admin_user.id)

    # 1. Offices list
    resp = client.get("/admin/offices", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 0

    cs_office = next(o for o in data["items"] if o["name"] == "Skill Department of CS/IT")
    assert cs_office["missing_officer"] is False
    assert cs_office["missing_hod"] is False
    assert len(cs_office["active_officers"]) >= 1

    # 2. Users directory filters
    resp = client.get("/admin/users?role=dept_officer&is_active=true", headers=headers)
    assert resp.status_code == 200
    users = resp.json()
    assert all(u["role"] == "dept_officer" and u["is_active"] is True for u in users)

    # Filter by department_id
    lib_dept = db_session.execute(select(Department).where(Department.name == "Library")).scalar_one()
    resp = client.get(f"/admin/users?department_id={lib_dept.id}", headers=headers)
    assert resp.status_code == 200
    assert all(u["department_id"] == lib_dept.id for u in resp.json())


def test_admin_users_bulk_upload(client, db_session):
    """Admin bulk provisions staff users; temporary passwords returned in response only."""
    admin_user = db_session.execute(
        select(User).where(User.email == "admin@example.edu")
    ).scalar_one()
    headers = make_auth_headers(admin_user.id)

    csv_data = (
        "email,full_name,role,department\r\n"
        # 1. Valid officer
        "new.officer1@example.edu,Officer One,dept_officer,Lab-1\r\n"
        # 2. Valid HoD
        "new.hod1@example.edu,HoD One,hod,Skill Department of CS/IT\r\n"
        # 3. Invalid role
        "bad.role@example.edu,Bad User,student,Library\r\n"
        # 4. HoD in non-academic department
        "bad.hod@example.edu,Bad HoD,hod,Library\r\n"
    )

    resp = client.post(
        "/admin/users/bulk-upload",
        headers=headers,
        files={"file": ("staff.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created_count"] == 2
    assert data["rejected_count"] == 2

    # Verify temporary password is in response
    created_rows = [r for r in data["rows"] if r["status"] == "created"]
    assert len(created_rows) == 2
    assert created_rows[0]["temporary_password"] is not None

    # Verify audit log does not leak password
    audit = db_session.execute(
        select(AuditLog).where(AuditLog.action == "CREATE_USER_BULK")
    ).scalars().first()
    assert audit is not None
    assert "password" not in str(audit.details)


def test_create_request_active_officer_and_hod_guards(client, db_session):
    """create_request fails with 409 if any applicable department has no active officer or no active HoD."""
    student_user, _ = _setup_student_with_bank(db_session, "2026TEST01", "student.test01@example.edu")
    headers = make_auth_headers(student_user.id)

    # 1. Deactivate Library officer
    lib_officer = db_session.execute(
        select(User).where(User.email == "library.officer@example.edu")
    ).scalar_one()
    lib_officer.is_active = False
    db_session.commit()

    resp = client.post("/student/requests", headers=headers)
    assert resp.status_code == 409
    assert "Library" in resp.json()["detail"]
    assert "has no active dealing officer" in resp.json()["detail"]

    # Reactivate Library officer
    lib_officer.is_active = True
    db_session.commit()

    # 2. Deactivate CS HoD
    cs_hod = db_session.execute(
        select(User).where(User.email == "hod.csit@example.edu")
    ).scalar_one()
    cs_hod.is_active = False
    db_session.commit()

    resp = client.post("/student/requests", headers=headers)
    assert resp.status_code == 409
    assert "has no active Head of Department (HoD)" in resp.json()["detail"]

    # Reactivate HoD -> submission succeeds!
    cs_hod.is_active = True
    db_session.commit()

    resp = client.post("/student/requests", headers=headers)
    assert resp.status_code == 201
    assert resp.json()["status"] == "SUBMITTED"


def test_multiple_officers_same_department_concurrency(client, db_session):
    """When multiple officers belong to the same department, either can decide; second attempt gets 409."""
    student_user, _ = _setup_student_with_bank(db_session, "2026TEST02", "student.test02@example.edu")
    req_headers = make_auth_headers(student_user.id)

    # Apply for clearance
    resp = client.post("/student/requests", headers=req_headers)
    assert resp.status_code == 201
    req_id = resp.json()["id"]

    # Find Library approval ID
    lib_dept = db_session.execute(select(Department).where(Department.name == "Library")).scalar_one()
    lib_approval = db_session.execute(
        select(DepartmentApproval).where(
            DepartmentApproval.request_id == req_id,
            DepartmentApproval.department_id == lib_dept.id,
        )
    ).scalar_one()

    # Create a second officer for Library
    officer2 = User(
        email="library.officer2@example.edu",
        full_name="Second Library Officer",
        password_hash=hash_password("Pass@123"),
        role=UserRole.dept_officer,
        department_id=lib_dept.id,
        is_active=True,
    )
    db_session.add(officer2)
    db_session.commit()

    officer1 = db_session.execute(select(User).where(User.email == "library.officer@example.edu")).scalar_one()

    # Officer 1 approves
    headers1 = make_auth_headers(officer1.id)
    resp1 = client.post(
        f"/department/approvals/{lib_approval.id}/decision",
        headers=headers1,
        json={"decision": "APPROVED", "remarks": "Approved by Officer 1"},
    )
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "APPROVED"

    # Officer 2 attempts to decide the same approval -> 409 Conflict!
    headers2 = make_auth_headers(officer2.id)
    resp2 = client.post(
        f"/department/approvals/{lib_approval.id}/decision",
        headers=headers2,
        json={"decision": "REJECTED", "remarks": "Conflicting decision"},
    )
    assert resp2.status_code == 409
    assert "Approval is not pending decision" in resp2.json()["detail"]


def test_student_catalog_and_add_department(client, db_session):
    """Student catalogs and dynamic department addition to clearance request."""
    student_user, _ = _setup_student_with_bank(db_session, "2026TEST03", "student.test03@example.edu")
    headers = make_auth_headers(student_user.id)

    # 1. GET /student/lab-catalog
    resp = client.get("/student/lab-catalog", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "lab_courses" in data
    assert "assigned_only_departments" in data

    # 2. GET /departments/assigned-only
    resp = client.get("/departments/assigned-only", headers=headers)
    assert resp.status_code == 200
    assigned_depts = resp.json()
    assert any(d["name"] == "Others" for d in assigned_depts)
    assert any(d["name"] == "Lab-1" for d in data.get("direct_offices", []))

    # 3. Apply for clearance
    resp = client.post("/student/requests", headers=headers)
    assert resp.status_code == 201
    req_id = resp.json()["id"]

    # 4. Add Lab-1 to request
    lab1_dept = db_session.execute(select(Department).where(Department.name == "Lab-1")).scalar_one()
    resp = client.post(
        f"/student/requests/{req_id}/departments",
        headers=headers,
        json={"department_id": lab1_dept.id},
    )
    assert resp.status_code == 201
    assert resp.json()["department_id"] == lab1_dept.id
    assert resp.json()["status"] == "PENDING"

    # 5. Adding again -> 409 Conflict
    resp = client.post(
        f"/student/requests/{req_id}/departments",
        headers=headers,
        json={"department_id": lab1_dept.id},
    )
    assert resp.status_code == 409
    assert "already part of this clearance request" in resp.json()["detail"]


def test_student_lab_catalog_has_active_officer_flag(client, db_session: Session):
    """
    Verifies that GET /student/lab-catalog returns has_active_officer (bool) on all
    direct_offices and assigned_only_departments, accurately reflecting whether
    an active dealing officer is assigned to that office.
    """
    student_user, _ = _setup_student_with_bank(db_session, "2026TEST_ACT", "student.active_flag@example.edu")
    headers = make_auth_headers(student_user.id)

    # 1. Create an unstaffed lab/workshop department
    unstaffed_lab = Department(
        name="Robotics Workshop Unstaffed",
        kind=DepartmentKind.service,
        applicability=DepartmentApplicability.LAB_WORKSHOP,
        description="Autonomous Systems Workshop",
        is_active=True,
    )
    db_session.add(unstaffed_lab)

    # 2. Create an unstaffed additional facility
    unstaffed_facility = Department(
        name="Innovation Incubation Facility Unstaffed",
        kind=DepartmentKind.service,
        applicability=DepartmentApplicability.ASSIGNED_ONLY,
        description="Center for Incubation",
        is_active=True,
    )
    db_session.add(unstaffed_facility)
    db_session.commit()
    db_session.refresh(unstaffed_lab)
    db_session.refresh(unstaffed_facility)

    # 3. GET /student/lab-catalog
    resp = client.get("/student/lab-catalog", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Verify all direct_offices have has_active_officer as bool
    assert len(data["direct_offices"]) > 0
    for d in data["direct_offices"]:
        assert "has_active_officer" in d
        assert isinstance(d["has_active_officer"], bool)

    # Verify all assigned_only_departments have has_active_officer as bool
    assert len(data["assigned_only_departments"]) > 0
    for d in data["assigned_only_departments"]:
        assert "has_active_officer" in d
        assert isinstance(d["has_active_officer"], bool)

    # Verify unstaffed lab has has_active_officer == False
    matched_lab = next((d for d in data["direct_offices"] if d["id"] == unstaffed_lab.id), None)
    assert matched_lab is not None
    assert matched_lab["has_active_officer"] is False

    # Verify unstaffed facility has has_active_officer == False
    matched_facility = next((d for d in data["assigned_only_departments"] if d["id"] == unstaffed_facility.id), None)
    assert matched_facility is not None
    assert matched_facility["has_active_officer"] is False

    # 4. Now create an active officer and assign to the unstaffed lab
    officer = User(
        email="robotics.officer@svsu.ac.in",
        full_name="Robotics Lab In-charge",
        role=UserRole.dept_officer,
        department_id=unstaffed_lab.id,
        is_active=True,
    )
    db_session.add(officer)
    db_session.commit()
    db_session.refresh(officer)

    # Assign membership
    membership = UserDepartment(user_id=officer.id, department_id=unstaffed_lab.id)
    db_session.add(membership)
    db_session.commit()

    # 5. GET /student/lab-catalog again
    resp2 = client.get("/student/lab-catalog", headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()

    matched_lab2 = next((d for d in data2["direct_offices"] if d["id"] == unstaffed_lab.id), None)
    assert matched_lab2 is not None
    assert matched_lab2["has_active_officer"] is True

    # 6. Deactivate officer -> has_active_officer should become False
    officer.is_active = False
    db_session.commit()

    resp3 = client.get("/student/lab-catalog", headers=headers)
    assert resp3.status_code == 200
    data3 = resp3.json()
    matched_lab3 = next((d for d in data3["direct_offices"] if d["id"] == unstaffed_lab.id), None)
    assert matched_lab3 is not None
    assert matched_lab3["has_active_officer"] is False

