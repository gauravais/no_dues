"""
FastAPI application entrypoint for Shri Vishwakarma Skill University (SVSU)
No-Dues Clearance & Security Deposit Refund System.
"""
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.routes import auth, student, department, hod, verify, registrar, admin
from backend.app.core.config import settings

APP_DESCRIPTION = """
### University No-Dues Clearance & Security Deposit Refund System
**Shri Vishwakarma Skill University (SVSU)**

This backend API replaces the manual paper-based clearance system with an automated digital workflow:
1. **Parallel Departmental Clearance**: When a student applies for No-Dues clearance, reviews are immediately dispatched in parallel to all applicable university departments:
   - **ALWAYS**: General service offices (Library, Sports, Account Section, NSS, Dean Student Welfare, etc.)
   - **HOSTELLER_ONLY**: Hostels (Boys/Girls) for residential students
   - **ASSIGNED_ONLY**: Specific laboratories and workshops assigned to the student
   - **OWN_ACADEMIC**: The student's own academic department office
2. **Selective Resubmission**: If any department rejects with remarks, the request enters `ACTION_NEEDED`. The student resolves the dues/issues and resubmits strictly to that specific department.
3. **Chairperson / HoD Final Clearance**: Once all departments have approved, the request moves to `HOD_REVIEW`. The Chairperson (HoD) grants final clearance, triggering issuance of an official Certificate with an unguessable UUID code (for verification).
4. **Post-Clearance Refund**: Verified records transition to Registration & Accounts (`registrar_accounts`) for refund reconciliation.

---
### Clearance Request Lifecycle Statuses
- `SUBMITTED`: Active clearance request dispatched to applicable departments; pending reviews.
- `ACTION_NEEDED`: One or more departments (or the HoD) rejected the request; student action is required.
- `HOD_REVIEW`: All applicable department clearances are approved; pending final review by the student's Academic Chairperson (HoD).
- `CLEARED`: HoD has approved; official clearance certificate generated.
- `REFUND_VERIFIED`: Accounts and Registration have verified the security deposit refund.

---
### System Roles & Access Matrix
- **`student`**: Self-registers via OTP; submits clearance application; tracks progress; resubmits to rejected departments or HoD.
- **`dept_officer`**: Assigned to a specific service or academic department office; approves or rejects student dues for that department with remarks.
- **`hod`**: Academic Chairperson of the student's department; performs final clearance review and issues certificates.
- **`registrar_accounts`**: University accounts section for post-clearance security deposit refund processing.
- **`admin`**: System management and roster administration.
"""

TAGS_METADATA = [
    {
        "name": "Auth",
        "description": "Student self-registration via official roster OTP, OAuth2 password login, and profile inspection.",
    },
    {
        "name": "Student",
        "description": "Student clearance lifecycle: application submission, live progress tracking, and resubmissions.",
    },
    {
        "name": "Department Officer",
        "description": "Review and decision workflow for departmental officers (Library, Hostel, Labs, Workshops, etc.).",
    },
    {
        "name": "HoD",
        "description": "Final review, clearance certification, and remarks by Academic Department Chairpersons (HoD).",
    },
    {
        "name": "Public Verification",
        "description": "Public certificate verification by UUID code or QR code link (no authentication required).",
    },
    {
        "name": "Registrar / Accounts",
        "description": "Post-clearance security deposit reconciliation, deductions, and payment reference recording.",
    },
    {
        "name": "Admin",
        "description": "Administrative roster CSV upload, student profile edits, staff user creation, and access management.",
    },
]

app = FastAPI(
    title="SVSU No-Dues Clearance API",
    version="1.0.0",
    description=APP_DESCRIPTION,
    openapi_tags=TAGS_METADATA,
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom validation exception handler to ensure {"detail": "..."} shape
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first_err = exc.errors()[0] if exc.errors() else {}
    msg = first_err.get("msg", "Invalid request parameter")
    field = ".".join(str(loc) for loc in first_err.get("loc", []))
    detail_msg = f"{field}: {msg}" if field else msg
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": detail_msg},
    )

# Include API Routers
app.include_router(auth.router)
app.include_router(student.router)
app.include_router(department.router)
app.include_router(hod.router)
app.include_router(verify.router)
app.include_router(registrar.router)
app.include_router(admin.router)


@app.get("/", tags=["Health"], include_in_schema=False)
def root():
    return {"message": "SVSU No-Dues Clearance System API is running", "docs": "/docs"}
