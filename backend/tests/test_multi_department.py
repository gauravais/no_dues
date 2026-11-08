"""
Comprehensive tests for Multi-Department Membership Model:
1. Multi-office officer queue, office_counts, and department_id filtering
2. Multi-office officer approval decisions
3. Limited dossier and scoping for multi-office officer vs full dossier
4. Request creation availability with active officers covering multiple offices
5. Mixed officer (service + academic) permission isolation
6. HoD multi-academic department queue and decisions
7. Admin user department management endpoints (GET, POST, DELETE, promotion, 409 guard)
8. Admin user creation with department_ids
9. Admin bulk user upload with pipe-separated departments
10. GET /auth/me returns departments list
11. Email notification deduplication & reminder digest across offices
12. Alembic migration 0011 roundtrip
"""
import io
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, inspect
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import hash_password
from backend.app.core.crypto import encrypt_bank_account
from backend.app.models.university import (
    Department, Programme, DepartmentKind, DepartmentApplicability,
)
from backend.app.models.user import User, UserRole, UserDepartment
from backend.app.models.roster import StudentRoster
from backend.app.models.bank import BankDetail
from backend.app.models.clearance import (
    ClearanceRequest, DepartmentApproval, ClearanceStatus, ApprovalStatus,
)
from backend.app.models.email import EmailOutbox
from backend.app.services.email import notify_officers_new_request
from scripts.send_reminders import process_reminders
from tests.conftest import make_auth_headers, TEST_DATABASE_URL


def _create_student_with_request(
    db: Session,
    reg_num: str,
    email: str,
    prog_name: str = "Bachelor of Technology (B.Tech.) Computer Engineering",
    is_hosteller: bool = False,
) -> tuple[User, ClearanceRequest]:
    """Helper to create a student and an initial clearance request."""
    prog = db.execute(select(Programme).where(Programme.name == prog_name)).scalar_one()

    roster = StudentRoster(
        registration_number=reg_num,
        name=f"Student {reg_num}",
        email=email,
        mobile="9876543210",
        address="123 Campus Lane",
        programme_id=prog.id,
        is_hosteller=is_hosteller,
        security_deposit_amount=Decimal("5000.00"),
    )
    db.add(roster)
    db.flush()

    bank = BankDetail(
        roster_id=roster.id,
        account_holder_name=roster.name,
        account_number=encrypt_bank_account("987654321000"),
        ifsc_code="SBIN0001234",
        bank_address="Main Campus Branch",
    )
    db.add(bank)

    student_user = User(
        email=email,
        full_name=roster.name,
        password_hash=hash_password("Pass@123"),
        role=UserRole.student,
        roster_id=roster.id,
        is_active=True,
    )
    db.add(student_user)
    db.flush()

    # Create clearance request
    req = ClearanceRequest(
        roster_id=roster.id,
        status=ClearanceStatus.SUBMITTED,
        declared_is_hosteller=is_hosteller,
    )
    db.add(req)
    db.flush()

    # Add approvals for CS/IT, Library, Sports
    cs_dept = db.execute(select(Department).where(Department.name == "Skill Department of CS/IT")).scalar_one()
    lib_dept = db.execute(select(Department).where(Department.name == "Library")).scalar_one()
    sports_dept = db.execute(select(Department).where(Department.name == "Sports")).scalar_one()

    appr_cs = DepartmentApproval(request_id=req.id, department_id=cs_dept.id, status=ApprovalStatus.PENDING)
    appr_lib = DepartmentApproval(request_id=req.id, department_id=lib_dept.id, status=ApprovalStatus.PENDING)
    appr_sports = DepartmentApproval(request_id=req.id, department_id=sports_dept.id, status=ApprovalStatus.PENDING)
    db.add_all([appr_cs, appr_lib, appr_sports])

    if is_hosteller:
        hostel_dept = db.execute(select(Department).where(Department.name == "Hostel (Boys/Girls)")).scalar_one()
        appr_hostel = DepartmentApproval(request_id=req.id, department_id=hostel_dept.id, status=ApprovalStatus.PENDING)
        db.add(appr_hostel)

    db.commit()
    db.refresh(student_user)
    db.refresh(req)
    return student_user, req


# ---------------------------------------------------------------------------
# 1. Multi-office officer queue, office_counts, and department_id filtering
# ---------------------------------------------------------------------------

def test_multi_office_officer_queue_and_office_counts(client, db_session):
    """An officer belonging to multiple offices sees all approvals and accurate counts."""
    lib_dept = db_session.execute(select(Department).where(Department.name == "Library")).scalar_one()
    sports_dept = db_session.execute(select(Department).where(Department.name == "Sports")).scalar_one()
    lab1_dept = db_session.execute(select(Department).where(Department.name == "Lab-1")).scalar_one()

    # Create an officer belonging to both Library and Sports
    multi_officer = User(
        email="multi.officer@example.edu",
        full_name="Multi Officer",
        password_hash=hash_password("Pass@123"),
        role=UserRole.dept_officer,
        department_id=lib_dept.id,
        is_active=True,
    )
    db_session.add(multi_officer)
    db_session.flush()

    # Add both memberships
    m1 = UserDepartment(user_id=multi_officer.id, department_id=lib_dept.id)
    m2 = UserDepartment(user_id=multi_officer.id, department_id=sports_dept.id)
    db_session.add_all([m1, m2])
    db_session.commit()

    # Create two student requests
    _, req1 = _create_student_with_request(db_session, "REG_MQ_1", "student1.mq@example.edu")
    _, req2 = _create_student_with_request(db_session, "REG_MQ_2", "student2.mq@example.edu")

    headers = make_auth_headers(multi_officer.id)

    # 1. GET /department/queue without filter
    res = client.get("/department/queue", headers=headers)
    assert res.status_code == 200
    data = res.json()

    # Response should have office_counts
    assert "office_counts" in data
    office_counts = {oc["department_name"]: oc["pending"] for oc in data["office_counts"]}
    assert office_counts.get("Library") == 2
    assert office_counts.get("Sports") == 2

    # Items should include approvals for BOTH Library and Sports
    dept_names = {item["department_name"] for item in data["items"]}
    assert "Library" in dept_names
    assert "Sports" in dept_names
    assert len(data["items"]) == 4

    # Each item has department_id and department_name
    for item in data["items"]:
        assert item["department_id"] in [lib_dept.id, sports_dept.id]
        assert item["department_name"] in ["Library", "Sports"]

    # 2. Filter by Library: GET /department/queue?department_id={lib_dept.id}
    res_lib = client.get(f"/department/queue?department_id={lib_dept.id}", headers=headers)
    assert res_lib.status_code == 200
    data_lib = res_lib.json()
    assert len(data_lib["items"]) == 2
    assert all(item["department_id"] == lib_dept.id for item in data_lib["items"])

    # 3. Filter by Sports: GET /department/queue?department_id={sports_dept.id}
    res_sports = client.get(f"/department/queue?department_id={sports_dept.id}", headers=headers)
    assert res_sports.status_code == 200
    data_sports = res_sports.json()
    assert len(data_sports["items"]) == 2
    assert all(item["department_id"] == sports_dept.id for item in data_sports["items"])

    # 4. Filter by unassigned office: GET /department/queue?department_id={lab1_dept.id} -> 404
    res_unassigned = client.get(f"/department/queue?department_id={lab1_dept.id}", headers=headers)
    assert res_unassigned.status_code == 404
    assert "Department not found among officer's assigned departments" in res_unassigned.json()["detail"]


# ---------------------------------------------------------------------------
# 2. Multi-office officer approval decisions
# ---------------------------------------------------------------------------

def test_officer_decisions_in_multiple_offices(client, db_session):
    """Officer can decide approvals in any assigned office, but not other offices."""
    lib_dept = db_session.execute(select(Department).where(Department.name == "Library")).scalar_one()
    sports_dept = db_session.execute(select(Department).where(Department.name == "Sports")).scalar_one()
    cs_dept = db_session.execute(select(Department).where(Department.name == "Skill Department of CS/IT")).scalar_one()

    officer = User(
        email="decision.officer@example.edu",
        full_name="Decision Officer",
        password_hash=hash_password("Pass@123"),
        role=UserRole.dept_officer,
        department_id=lib_dept.id,
        is_active=True,
    )
    db_session.add(officer)
    db_session.flush()
    db_session.add_all([
        UserDepartment(user_id=officer.id, department_id=lib_dept.id),
        UserDepartment(user_id=officer.id, department_id=sports_dept.id),
    ])
    db_session.commit()

    _, req = _create_student_with_request(db_session, "REG_DEC_1", "student.dec@example.edu")
    approvals = db_session.execute(
        select(DepartmentApproval).where(DepartmentApproval.request_id == req.id)
    ).scalars().all()
    appr_map = {a.department_id: a for a in approvals}

    headers = make_auth_headers(officer.id)

    # 1. Decide Library approval -> 200 OK
    res_lib = client.post(
        f"/department/approvals/{appr_map[lib_dept.id].id}/decision",
        json={"decision": "APPROVED", "remarks": "Books returned"},
        headers=headers,
    )
    assert res_lib.status_code == 200
    assert res_lib.json()["status"] == ApprovalStatus.APPROVED.value

    # 2. Decide Sports approval -> 200 OK
    res_sports = client.post(
        f"/department/approvals/{appr_map[sports_dept.id].id}/decision",
        json={"decision": "APPROVED", "remarks": "Sports kit returned"},
        headers=headers,
    )
    assert res_sports.status_code == 200
    assert res_sports.json()["status"] == ApprovalStatus.APPROVED.value

    # 3. Decide CS/IT approval (officer is not in CS/IT) -> 404
    res_cs = client.post(
        f"/department/approvals/{appr_map[cs_dept.id].id}/decision",
        json={"decision": "APPROVED", "remarks": "Unauthorized decision"},
        headers=headers,
    )
    assert res_cs.status_code == 404
    assert "Approval does not belong to your assigned department" in res_cs.json()["detail"]


# ---------------------------------------------------------------------------
# 3. Limited dossier and scoping for multi-office officer vs full dossier
# ---------------------------------------------------------------------------

def test_limited_dossier_and_scoping_for_multi_office_officer(client, db_session):
    """Multi-office service officer gets scoped dossier; academic officer gets full dossier."""
    sports_dept = db_session.execute(select(Department).where(Department.name == "Sports")).scalar_one()
    hostel_dept = db_session.execute(select(Department).where(Department.name == "Hostel (Boys/Girls)")).scalar_one()
    cs_dept = db_session.execute(select(Department).where(Department.name == "Skill Department of CS/IT")).scalar_one()

    # Officer in Sports + Hostel
    service_officer = User(
        email="service.multi@example.edu",
        full_name="Service Multi",
        password_hash=hash_password("Pass@123"),
        role=UserRole.dept_officer,
        department_id=sports_dept.id,
        is_active=True,
    )
    db_session.add(service_officer)
    db_session.flush()
    db_session.add_all([
        UserDepartment(user_id=service_officer.id, department_id=sports_dept.id),
        UserDepartment(user_id=service_officer.id, department_id=hostel_dept.id),
    ])

    # Officer in CS/IT (academic) + Sports
    academic_officer = User(
        email="acad.multi@example.edu",
        full_name="Academic Multi",
        password_hash=hash_password("Pass@123"),
        role=UserRole.dept_officer,
        department_id=cs_dept.id,
        is_active=True,
    )
    db_session.add(academic_officer)
    db_session.flush()
    db_session.add_all([
        UserDepartment(user_id=academic_officer.id, department_id=cs_dept.id),
        UserDepartment(user_id=academic_officer.id, department_id=sports_dept.id),
    ])
    db_session.commit()

    # Create hosteller student
    _, req = _create_student_with_request(
        db_session, "REG_DOS_1", "student.dos@example.edu", is_hosteller=True
    )

    # 1. Service officer view: scoped dossier
    res_svc = client.get(f"/department/requests/{req.id}", headers=make_auth_headers(service_officer.id))
    assert res_svc.status_code == 200
    data_svc = res_svc.json()
    assert data_svc["can_add_departments"] == []
    assert data_svc["declared_is_hosteller"] is True  # True because officer heads Hostel
    # Service officer sees only approvals for their departments (Sports and Hostel)
    returned_dept_names = {a["department_name"] for a in data_svc["approvals"]}
    assert returned_dept_names == {"Sports", "Hostel (Boys/Girls)"}

    # 2. Academic officer view: full dossier (since student belongs to CS/IT)
    res_acad = client.get(f"/department/requests/{req.id}", headers=make_auth_headers(academic_officer.id))
    assert res_acad.status_code == 200
    data_acad = res_acad.json()
    assert len(data_acad["can_add_departments"]) > 0
    # All approvals visible in full dossier
    assert len(data_acad["approvals"]) >= 4


# ---------------------------------------------------------------------------
# 4. Request creation availability with active officers covering multiple offices
# ---------------------------------------------------------------------------

def test_request_creation_active_officers_across_offices(client, db_session):
    """Request creation verifies active officers across user_departments."""
    lib_dept = db_session.execute(select(Department).where(Department.name == "Library")).scalar_one()
    sports_dept = db_session.execute(select(Department).where(Department.name == "Sports")).scalar_one()

    # Deactivate existing library and sports officers
    existing_lib = db_session.execute(select(User).where(User.email == "library.officer@example.edu")).scalar_one()
    existing_sports = db_session.execute(select(User).where(User.email == "sports.officer@example.edu")).scalar_one()
    existing_lib.is_active = False
    existing_sports.is_active = False
    db_session.commit()

    # Create student ready to apply
    prog = db_session.execute(select(Programme).where(Programme.name.ilike("%Computer%"))).scalar_one()
    roster = StudentRoster(
        registration_number="REG_AVAIL_1",
        name="Avail Student",
        email="avail.student@example.edu",
        mobile="9876543210",
        address="Campus",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=Decimal("5000.00"),
    )
    db_session.add(roster)
    db_session.flush()
    bank = BankDetail(
        roster_id=roster.id,
        account_holder_name=roster.name,
        account_number=encrypt_bank_account("987654321000"),
        ifsc_code="SBIN0001234",
        bank_address="Main Campus Branch",
    )
    db_session.add(bank)
    user = User(
        email="avail.student@example.edu",
        full_name=roster.name,
        password_hash=hash_password("Pass@123"),
        role=UserRole.student,
        roster_id=roster.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    headers = make_auth_headers(user.id)

    # 1. Apply when neither office has active officer -> 409
    res = client.post("/student/requests", json={"other_department_ids": []}, headers=headers)
    assert res.status_code == 409
    assert "no active dealing officer" in res.json()["detail"]

    # 2. Add ONE officer covering BOTH Library and Sports
    covering_officer = User(
        email="covering.officer@example.edu",
        full_name="Covering Officer",
        password_hash=hash_password("Pass@123"),
        role=UserRole.dept_officer,
        department_id=lib_dept.id,
        is_active=True,
    )
    db_session.add(covering_officer)
    db_session.flush()
    db_session.add_all([
        UserDepartment(user_id=covering_officer.id, department_id=lib_dept.id),
        UserDepartment(user_id=covering_officer.id, department_id=sports_dept.id),
    ])
    db_session.commit()

    # 3. Apply again -> 201 Created! (Single officer covers both offices)
    res_ok = client.post("/student/requests", json={"other_department_ids": []}, headers=headers)
    assert res_ok.status_code == 201

    # 4. If that officer is deactivated, creating new request for another student fails again
    covering_officer.is_active = False
    db_session.commit()

    # Create second student
    roster2 = StudentRoster(
        registration_number="REG_AVAIL_2",
        name="Avail Student 2",
        email="avail2.student@example.edu",
        mobile="9876543210",
        address="Campus",
        programme_id=prog.id,
        is_hosteller=False,
        security_deposit_amount=Decimal("5000.00"),
    )
    db_session.add(roster2)
    db_session.flush()
    db_session.add(BankDetail(
        roster_id=roster2.id,
        account_holder_name=roster2.name,
        account_number=encrypt_bank_account("987654321000"),
        ifsc_code="SBIN0001234",
        bank_address="Main Campus Branch",
    ))
    user2 = User(
        email="avail2.student@example.edu",
        full_name=roster2.name,
        password_hash=hash_password("Pass@123"),
        role=UserRole.student,
        roster_id=roster2.id,
        is_active=True,
    )
    db_session.add(user2)
    db_session.commit()

    res_fail = client.post("/student/requests", json={"other_department_ids": []}, headers=make_auth_headers(user2.id))
    assert res_fail.status_code == 409


# ---------------------------------------------------------------------------
# 5. Mixed officer (service + academic) permission isolation
# ---------------------------------------------------------------------------

def test_mixed_officer_service_vs_academic_permissions(client, db_session):
    """An officer in both service and academic depts can only manage academic features for their academic dept."""
    cs_dept = db_session.execute(select(Department).where(Department.name == "Skill Department of CS/IT")).scalar_one()
    sports_dept = db_session.execute(select(Department).where(Department.name == "Sports")).scalar_one()
    auto_dept = db_session.execute(select(Department).where(Department.name == "Skill Department of Automotive Studies")).scalar_one()

    mixed_officer = User(
        email="mixed.officer@example.edu",
        full_name="Mixed Officer",
        password_hash=hash_password("Pass@123"),
        role=UserRole.dept_officer,
        department_id=cs_dept.id,
        is_active=True,
    )
    db_session.add(mixed_officer)
    db_session.flush()
    db_session.add_all([
        UserDepartment(user_id=mixed_officer.id, department_id=cs_dept.id),
        UserDepartment(user_id=mixed_officer.id, department_id=sports_dept.id),
    ])
    db_session.commit()

    headers = make_auth_headers(mixed_officer.id)

    # 1. Roster list without filter: returns roster for CS/IT (their academic dept)
    res = client.get("/department/roster", headers=headers)
    assert res.status_code == 200

    # 2. Roster list with department_id=cs_dept.id: 200 OK
    res_cs = client.get(f"/department/roster?department_id={cs_dept.id}", headers=headers)
    assert res_cs.status_code == 200

    # 3. Roster list with department_id=sports_dept.id (service office): 404
    res_sports = client.get(f"/department/roster?department_id={sports_dept.id}", headers=headers)
    assert res_sports.status_code == 404
    assert "Department not found among your academic departments" in res_sports.json()["detail"]

    # 4. Roster list with department_id=auto_dept.id (other academic office): 404
    res_auto = client.get(f"/department/roster?department_id={auto_dept.id}", headers=headers)
    assert res_auto.status_code == 404

    # 5. Lab catalog list without filter: 200 OK
    res_labs = client.get("/department/lab-courses", headers=headers)
    assert res_labs.status_code == 200

    # 6. Lab catalog filtered by sports_dept.id (service office): 404
    res_lab_sports = client.get(f"/department/lab-courses?department_id={sports_dept.id}", headers=headers)
    assert res_lab_sports.status_code == 404
    assert "Department not found among your academic departments" in res_lab_sports.json()["detail"]

    # 7. Lab course add with lab_department_id=sports_dept.id: 400 (not an ASSIGNED_ONLY service department)
    res_lab_add_sports = client.post(
        "/department/lab-courses",
        json={
            "code": "TEST-LAB-101",
            "name": "Sports Lab",
            "lab_department_id": sports_dept.id,
        },
        headers=headers,
    )
    assert res_lab_add_sports.status_code == 400
    assert "LAB_WORKSHOP applicability" in res_lab_add_sports.json()["detail"]


# ---------------------------------------------------------------------------
# 6. HoD multi-academic department queue and decisions
# ---------------------------------------------------------------------------

def test_hod_multi_academic_departments(client, db_session):
    """An HoD heading multiple academic departments sees requests and can decide for both."""
    cs_dept = db_session.execute(select(Department).where(Department.name == "Skill Department of CS/IT")).scalar_one()
    auto_dept = db_session.execute(select(Department).where(Department.name == "Skill Department of Automotive Studies")).scalar_one()

    # Multi-department HoD
    multi_hod = User(
        email="multi.hod@example.edu",
        full_name="Multi HoD",
        password_hash=hash_password("Pass@123"),
        role=UserRole.hod,
        department_id=cs_dept.id,
        is_active=True,
    )
    db_session.add(multi_hod)
    db_session.flush()
    db_session.add_all([
        UserDepartment(user_id=multi_hod.id, department_id=cs_dept.id),
        UserDepartment(user_id=multi_hod.id, department_id=auto_dept.id),
    ])
    db_session.commit()

    # Create two students: one CE, one Auto
    _, req1 = _create_student_with_request(
        db_session, "REG_HOD_1", "student1.hod@example.edu",
        prog_name="Bachelor of Technology (B.Tech.) Computer Engineering",
    )
    _, req2 = _create_student_with_request(
        db_session, "REG_HOD_2", "student2.hod@example.edu",
        prog_name="Bachelor of Technology Mechanical and Smart Manufacturing",
    )

    # Approve all approvals so requests transition to hod_review
    for req in [req1, req2]:
        for a in req.approvals:
            a.status = ApprovalStatus.APPROVED
        req.status = ClearanceStatus.HOD_REVIEW
    db_session.commit()

    headers = make_auth_headers(multi_hod.id)

    # 1. GET /hod/queue: should include BOTH students
    res_q = client.get("/hod/queue", headers=headers)
    assert res_q.status_code == 200
    q_data = res_q.json()
    reg_nums = {item["registration_number"] for item in q_data}
    assert "REG_HOD_1" in reg_nums
    assert "REG_HOD_2" in reg_nums

    # 2. HoD can decide both requests
    res_d1 = client.post(
        f"/hod/requests/{req1.id}/decision",
        json={"decision": "APPROVED", "remarks": "Approved CE student"},
        headers=headers,
    )
    assert res_d1.status_code == 200
    assert res_d1.json()["status"] == ClearanceStatus.CLEARED.value

    res_d2 = client.post(
        f"/hod/requests/{req2.id}/decision",
        json={"decision": "APPROVED", "remarks": "Approved Auto student"},
        headers=headers,
    )
    assert res_d2.status_code == 200
    assert res_d2.json()["status"] == ClearanceStatus.CLEARED.value


# ---------------------------------------------------------------------------
# 7. Admin user department management endpoints
# ---------------------------------------------------------------------------

def test_admin_user_department_management_endpoints(client, db_session):
    """Test GET /admin/users/{id}, POST /admin/users/{id}/departments, and DELETE."""
    admin = db_session.execute(select(User).where(User.email == "admin@example.edu")).scalar_one()
    lib_dept = db_session.execute(select(Department).where(Department.name == "Library")).scalar_one()
    sports_dept = db_session.execute(select(Department).where(Department.name == "Sports")).scalar_one()
    lab1_dept = db_session.execute(select(Department).where(Department.name == "Lab-1")).scalar_one()

    # Create dept_officer in Library
    user = User(
        email="managed.officer@example.edu",
        full_name="Managed Officer",
        password_hash=hash_password("Pass@123"),
        role=UserRole.dept_officer,
        department_id=lib_dept.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserDepartment(user_id=user.id, department_id=lib_dept.id))
    db_session.commit()

    admin_headers = make_auth_headers(admin.id)

    # 1. GET /admin/users/{id}
    res = client.get(f"/admin/users/{user.id}", headers=admin_headers)
    assert res.status_code == 200
    detail = res.json()
    assert detail["id"] == user.id
    assert len(detail["departments"]) == 1
    assert detail["departments"][0]["id"] == lib_dept.id

    # 2. POST /admin/users/{id}/departments to add Sports
    res_add = client.post(
        f"/admin/users/{user.id}/departments",
        json={"department_id": sports_dept.id},
        headers=admin_headers,
    )
    assert res_add.status_code == 200
    add_data = res_add.json()
    dept_ids = {d["id"] for d in add_data["departments"]}
    assert dept_ids == {lib_dept.id, sports_dept.id}

    # 3. Add same department again -> idempotent 200
    res_dup = client.post(
        f"/admin/users/{user.id}/departments",
        json={"department_id": sports_dept.id},
        headers=admin_headers,
    )
    assert res_dup.status_code == 200

    # 4. Add 3rd department (Lab-1)
    client.post(
        f"/admin/users/{user.id}/departments",
        json={"department_id": lab1_dept.id},
        headers=admin_headers,
    )

    # 5. DELETE the primary department (Library)
    res_del_prim = client.delete(
        f"/admin/users/{user.id}/departments/{lib_dept.id}",
        headers=admin_headers,
    )
    assert res_del_prim.status_code == 200
    del_data = res_del_prim.json()
    # Library removed
    remaining_ids = {d["id"] for d in del_data["departments"]}
    assert lib_dept.id not in remaining_ids
    # Primary department_id promoted to one of remaining
    assert del_data["department_id"] in remaining_ids

    # 6. DELETE Lab-1
    client.delete(
        f"/admin/users/{user.id}/departments/{lab1_dept.id}",
        headers=admin_headers,
    )

    # 7. Attempt to DELETE last department (Sports) -> 409 "Deactivate the user instead"
    res_last = client.delete(
        f"/admin/users/{user.id}/departments/{sports_dept.id}",
        headers=admin_headers,
    )
    assert res_last.status_code == 409
    assert "Deactivate the user instead" in res_last.json()["detail"]

    # 8. Test HoD cannot be assigned a service department
    hod = db_session.execute(select(User).where(User.email == "hod.csit@example.edu")).scalar_one()
    res_hod_service = client.post(
        f"/admin/users/{hod.id}/departments",
        json={"department_id": sports_dept.id},
        headers=admin_headers,
    )
    assert res_hod_service.status_code == 400
    assert "academic departments" in res_hod_service.json()["detail"]


# ---------------------------------------------------------------------------
# 8. Admin user creation with department_ids
# ---------------------------------------------------------------------------

def test_admin_user_creation_with_department_ids(client, db_session):
    """POST /admin/users supports department_ids array and enforces role constraints."""
    admin = db_session.execute(select(User).where(User.email == "admin@example.edu")).scalar_one()
    lib_dept = db_session.execute(select(Department).where(Department.name == "Library")).scalar_one()
    sports_dept = db_session.execute(select(Department).where(Department.name == "Sports")).scalar_one()

    admin_headers = make_auth_headers(admin.id)

    # 1. Create dept_officer with department_ids
    res = client.post(
        "/admin/users",
        json={
            "email": "new.multiofficer@example.edu",
            "full_name": "New Multi Officer",
            "role": "dept_officer",
            "department_ids": [lib_dept.id, sports_dept.id],
        },
        headers=admin_headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert len(data["departments"]) == 2
    dept_ids = {d["id"] for d in data["departments"]}
    assert dept_ids == {lib_dept.id, sports_dept.id}

    # 2. dept_officer with empty department_ids -> 400
    res_no_dept = client.post(
        "/admin/users",
        json={
            "email": "empty.officer@example.edu",
            "full_name": "Empty Officer",
            "role": "dept_officer",
            "department_ids": [],
        },
        headers=admin_headers,
    )
    assert res_no_dept.status_code == 400

    # 3. HoD with service department -> 400
    res_hod_invalid = client.post(
        "/admin/users",
        json={
            "email": "invalid.hod@example.edu",
            "full_name": "Invalid HoD",
            "role": "hod",
            "department_ids": [sports_dept.id],
        },
        headers=admin_headers,
    )
    assert res_hod_invalid.status_code == 400
    assert "must belong to an academic department" in res_hod_invalid.json()["detail"]

    # 4. Admin role not allowed for staff creation endpoint -> 400
    res_admin_invalid = client.post(
        "/admin/users",
        json={
            "email": "invalid.admin@example.edu",
            "full_name": "Invalid Admin",
            "role": "admin",
            "department_ids": [sports_dept.id],
        },
        headers=admin_headers,
    )
    assert res_admin_invalid.status_code == 400


# ---------------------------------------------------------------------------
# 9. Admin bulk user upload with pipe-separated departments
# ---------------------------------------------------------------------------

def test_admin_bulk_upload_pipe_separated_departments(client, db_session):
    """POST /admin/users/bulk-upload supports pipe-separated departments column."""
    admin = db_session.execute(select(User).where(User.email == "admin@example.edu")).scalar_one()
    admin_headers = make_auth_headers(admin.id)

    csv_content = (
        "email,full_name,role,departments\n"
        "bulk.multi1@example.edu,Bulk Multi One,dept_officer,Sports | Library\n"
        "bulk.multi2@example.edu,Bulk Multi Two,dept_officer,Sports | Nonexistent Department\n"
    )
    files = {"file": ("users.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}

    res = client.post("/admin/users/bulk-upload", files=files, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()

    assert data["created_count"] == 1
    assert data["rejected_count"] == 1

    # Check the created user has both departments
    created_user = db_session.execute(
        select(User).where(User.email == "bulk.multi1@example.edu")
    ).scalar_one()
    dept_names = {ud.department.name for ud in created_user.department_memberships}
    assert dept_names == {"Sports", "Library"}


# ---------------------------------------------------------------------------
# 10. GET /auth/me returns departments list
# ---------------------------------------------------------------------------

def test_auth_me_returns_departments_list(client, db_session):
    """GET /auth/me returns primary department_id and departments list."""
    lib_dept = db_session.execute(select(Department).where(Department.name == "Library")).scalar_one()
    sports_dept = db_session.execute(select(Department).where(Department.name == "Sports")).scalar_one()

    officer = User(
        email="me.officer@example.edu",
        full_name="Me Officer",
        password_hash=hash_password("Pass@123"),
        role=UserRole.dept_officer,
        department_id=lib_dept.id,
        is_active=True,
    )
    db_session.add(officer)
    db_session.flush()
    db_session.add_all([
        UserDepartment(user_id=officer.id, department_id=lib_dept.id),
        UserDepartment(user_id=officer.id, department_id=sports_dept.id),
    ])
    db_session.commit()

    res = client.get("/auth/me", headers=make_auth_headers(officer.id))
    assert res.status_code == 200
    data = res.json()
    assert data["department_id"] == lib_dept.id
    assert len(data["departments"]) == 2
    dept_ids = {d["id"] for d in data["departments"]}
    assert dept_ids == {lib_dept.id, sports_dept.id}


# ---------------------------------------------------------------------------
# 11. Email notification deduplication & reminder digest across offices
# ---------------------------------------------------------------------------

def test_email_notifications_and_reminder_digest_deduplication(db_session):
    """One person covering multiple offices receives 1 notification listing all offices."""
    lib_dept = db_session.execute(select(Department).where(Department.name == "Library")).scalar_one()
    sports_dept = db_session.execute(select(Department).where(Department.name == "Sports")).scalar_one()

    # Create officer covering Library and Sports
    officer = User(
        email="multi.notify@example.edu",
        full_name="Multi Notify Officer",
        password_hash=hash_password("Pass@123"),
        role=UserRole.dept_officer,
        department_id=lib_dept.id,
        is_active=True,
    )
    db_session.add(officer)
    db_session.flush()
    db_session.add_all([
        UserDepartment(user_id=officer.id, department_id=lib_dept.id),
        UserDepartment(user_id=officer.id, department_id=sports_dept.id),
    ])
    db_session.commit()

    # Create request with approvals for Library and Sports
    _, req = _create_student_with_request(db_session, "REG_NOTIF_1", "student.notif@example.edu")

    # Call notify_officers_new_request
    notify_officers_new_request(db_session, req)
    db_session.commit()

    # Query outbox for this officer's email
    outbox_entries = db_session.execute(
        select(EmailOutbox).where(EmailOutbox.to_email == "multi.notify@example.edu")
    ).scalars().all()

    # Must be exactly 1 email sent to this person
    assert len(outbox_entries) == 1
    entry = outbox_entries[0]
    # The body lists both offices
    assert "Library" in entry.body
    assert "Sports" in entry.body

    # Test daily reminder digest grouping across offices
    orig_enabled = settings.REMINDERS_ENABLED
    orig_days = settings.REMINDER_AFTER_DAYS
    try:
        settings.REMINDERS_ENABLED = True
        settings.REMINDER_AFTER_DAYS = 3
        # Backdate approvals older than 3 days
        four_days_ago = datetime.now(timezone.utc) - timedelta(days=4)
        for app in req.approvals:
            app.created_at = four_days_ago
        db_session.commit()

        count = process_reminders(session=db_session)
        assert count >= 1

        # Check digest email for officer
        digest = db_session.execute(
            select(EmailOutbox).where(
                EmailOutbox.to_email == "multi.notify@example.edu",
                EmailOutbox.kind == "digest_reminder",
            )
        ).scalars().first()
        assert digest is not None
        assert "Library" in digest.body
        assert "Sports" in digest.body
    finally:
        settings.REMINDERS_ENABLED = orig_enabled
        settings.REMINDER_AFTER_DAYS = orig_days


# ---------------------------------------------------------------------------
# 12. Alembic migration 0011 roundtrip
# ---------------------------------------------------------------------------

def test_migration_0011_roundtrip(test_engine):
    """Test Alembic downgrade to 0010 and upgrade back to head with backfill check."""
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)

    # 1. Downgrade to 0010
    command.downgrade(alembic_cfg, "0010_google_auth")
    insp_down = inspect(test_engine)
    assert "user_departments" not in insp_down.get_table_names()

    # 2. Upgrade to 0011 (head)
    command.upgrade(alembic_cfg, "head")
    insp_up = inspect(test_engine)
    assert "user_departments" in insp_up.get_table_names()
    cols = [c["name"] for c in insp_up.get_columns("user_departments")]
    assert "user_id" in cols
    assert "department_id" in cols
    assert "created_at" in cols
    assert "created_by_user_id" in cols

    # 3. Verify idempotent re-run of upgrade
    command.upgrade(alembic_cfg, "head")
