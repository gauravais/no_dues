# SVSU No-Dues Clearance & Refund System (Frontend)

An institutional digital clearance and security deposit refund portal built for **Shri Vishwakarma Skill University (SVSU)**. This React application digitizes the traditional paper-based no-dues workflow, replacing physical stamp-collecting with parallel departmental reviews, verifiable cryptographic certificates, and automated registrar reconciliation.

---

## 1. Quick Start & Execution

### Prerequisites
- Node.js (v18+ or v20+)
- npm (v9+)
- SVSU FastAPI Backend running (default: `http://localhost:8000`)

### Execution Order: Run Backend First
1. **Start Backend Services**: Ensure Docker PostgreSQL, Alembic migrations, and the FastAPI backend are running on `http://localhost:8000` (refer to `backend/README.md`).
2. **Install & Run Frontend**:
```bash
# Navigate to frontend folder
cd frontend

# Install dependencies
npm install

# Start development server with Hot Module Replacement (HMR)
npm run dev

# Run production build (Vite with leak and wording checks)
npm run build

# Run ESLint validation
npm run lint

# Validate frontend-backend API contract against OpenAPI
npm run check:contract

# Run leak detection (example.edu, DEMO2026, dev_otp)
npm run check:leaks

# Run wording check (demo, FastAPI, Tailwind, shadcn, React 19, synthetic)
npm run check:wording

# Preview production build locally
npm run preview
```

---

## 2. Environment Configuration

Create a `.env` or `.env.local` file inside the `frontend/` directory to configure the backend API target:

| Variable | Description | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Base URL of the FastAPI backend service | `http://localhost:8000` |

If unset, Axios defaults automatically to `http://localhost:8000`.

---

## 3. Staff Accounts (Role-Based Testing)

The following seeded staff accounts are generated for testing each administrative role. In compliance with security hygiene, default passwords are never published in public documentation; in development environments, they are derived from the `SEED_DEFAULT_PASSWORD` environment variable.

| Role | Institutional Email | Assigned Department / Notes |
|---|---|---|
| **System Administrator** | `admin@svsu.ac.in` | Full administrative & provisioning rights |
| **Registrar / Accounts** | `registrar.accounts@svsu.ac.in` | University Registrar & Finance Section (R&S Branch) |
| **Chairperson (HoD) CS/IT** | `hod.csit@svsu.ac.in` | Chairperson, Skill Dept of CS/IT |
| **Academic Officer (CS/IT)** | `officer.csit@svsu.ac.in` | Skill Dept of CS/IT (Academic Officer) |
| **Department Officer (Library)** | `library.officer@svsu.ac.in` | Central Library |
| **Department Officer (Hostel)** | `hostel.officer@svsu.ac.in` | Hostel Office (Boys/Girls) |
| **Department Officer (Sports)** | `sports.officer@svsu.ac.in` | Sports & Gymnasium Section |
| **Department Officer (Accounts)** | `accounts.officer@svsu.ac.in` | University Accounts Section |

> **Development Quick-Fill Chips**: In local development (`import.meta.env.DEV`), the `/login` page displays "Quick sign-in (development only)" chips for the staff roles above. Chips pre-fill emails only (never passwords) and are completely excluded from production builds. Build-time leak verification (`npm run check:leaks`) and wording validation (`npm run check:wording`) ensure no forbidden patterns or stack mentions are bundled into `dist/`.

---

## 4. Who Does What: Roles & Responsibility Matrix

Responsibility is clearly distributed across six distinct university actors to prevent administrative bottlenecks:

| Actor | Primary Duties | Scope of Authority | Data Visibility & Privacy Limits |
|---|---|---|---|
| **Administrator** (`admin`) | 1. Monitors department staffing health (`missing_officer`, `missing_hod`).<br/>2. Provisions dealing officers and HoDs.<br/>3. Resets staff passwords.<br/>4. Manages global roster and lab fallbacks. | University-wide administration; main page at `/admin/offices`. | Cannot reveal unmasked bank numbers. Password hashes are never accessible. Temporary passwords appear strictly once in transient dialogs. |
| **Academic Department** (`dept_officer` academic) | 1. Maintains student roster for **own** department programmes.<br/>2. Maintains lab subject catalog for **own** programmes.<br/>3. Reviews academic department clearance.<br/>4. Adds dealing offices mid-clearance with justification. | Limited strictly to programmes and students belonging to their academic department. | Never sees student bank account details or financial audit ledgers. |
| **Service Offices** (`dept_officer` service) | 1. Reviews clearance tasks for their domain (Library, Sports, Hostel, Lab-1, etc.).<br/>2. Approves or rejects with mandatory remarks.<br/>3. Lab officers inspect matching student declared subjects. | Limited to their assigned branch / laboratory. | Forbidden from modifying rosters or catalogs. No access to student bank details. |
| **Student** (`student`) | 1. Sets/updates encrypted refund bank details.<br/>2. Declares hostel residency, lab subjects, and special notes.<br/>3. Tracks parallel reviews and resubmits to rejected offices.<br/>4. Downloads signed PDF certificate upon HoD clearance. | Limited strictly to own clearance application and profile. | Bank details masked (`********1234`). Never sees administrative audit logs or roster provenance. |
| **Chairperson (HoD)** (`hod`) | 1. Conducts final review once all departmental approvals are secured.<br/>2. Approves clearance (issuing digital certificate) or rejects with remarks.<br/>3. Adds dealing offices with mandatory justification. | Restricted strictly to students enrolled in their academic department programmes. | No access to student bank account details. |
| **Registrar / Accounts** (`registrar_accounts`) | 1. Audits cleared applications awaiting caution money refund.<br/>2. Inspects roster provenance.<br/>3. Verifies deposit amount, records deductions, and marks disbursed.<br/>4. Executes audited 30-second reveal of bank account. | University-wide financial reconciliation and disbursement. | Full roster provenance visible. Audited bank detail reveals are rate-limited (max 10/min) and logged immutably. |

---

## 5. Features by Role

### 1. Student Portal (`/student` & `/student/apply`)
- **Pre-Clearance Bank Registration**: Validates Indian bank account and IFSC code (`PUT /student/bank-details`), encrypted at rest with Fernet AES-128-CBC + HMAC-SHA256.
- **5-Step Application Wizard**:
  - Step 1: Bank verification.
  - Step 2: Hostel residency declaration (`is_hosteller`).
  - Step 3: Dynamic departmental lab course selection.
  - Step 4: Supplemental assigned-only offices and freeform notes.
  - Step 5: Unified review and submission confirmation (`POST /student/requests`).
- **Parallel Clearance Checklist**: Live status badges (`PENDING`, `APPROVED`, `REJECTED`), previous rejection history callouts, and resubmission counters.
- **Targeted Resubmission**: Resubmit strictly to the rejected department without resetting other approvals (`POST /student/requests/{id}/departments/{d_id}/resubmit`).
- **Mid-Clearance Expansion**: Add supplemental lab subjects (`POST /student/requests/{id}/lab-courses`) or assigned offices.
- **Certificate Download**: Generates official PDF clearance certificate on demand with an embedded QR code and verification URL (`GET /student/requests/{id}/certificate.pdf`).

### 2. Department Officer Interface (`/officer`)
- **Queue & Status Tabs**: Segregates clearance items by `PENDING`, `APPROVED`, `REJECTED`, and `ALL`.
- **Search & Dossier Inspection**: Server-side search filtering across student name and registration number with links to full dossiers (`/officer/requests/:id`).
- **Declared Subjects Display**: Lab officers inspect declared course code and title chips corresponding to their lab office.
- **Decision Modal**: Approve or reject with live `x/500` character counter; remarks are strictly mandatory upon rejection. Plain text notice clarifies valid approval remarks.
- **Academic Officer Suite**:
  - **Student Roster (`/officer/roster`)**: Programme-scoped student roster management, single student creation, profile editing (with 409 account conflict notice), and CSV batch upload with template download.
  - **Lab Catalog (`/officer/lab-catalog`)**: Laboratory subjects catalog mapped to service departments, create course dialog, active toggle, and CSV upload with template.
  - **Clearance Dossier & Add Office (`/officer/requests/:id`)**: Comprehensive student dossier view and post-submission office dispatch modal (`POST /department/requests/{id}/add-department`).

### 3. Chairperson / HoD Queue & Dossier (`/hod` & `/hod/requests/:id`)
- **Academic Review Queue**: Reviews clearance dossiers once all parallel department sign-offs have been approved.
- **Sign-off Matrix**: Full departmental audit breakdown with status badges, remarks, previous rejection history, and decision timestamps.
- **Post-Submission Dispatch**: Ability to add extra dealing offices with mandatory justification (`POST /hod/requests/{id}/add-department`).
- **Final Decision & Issuance**: Grants final approval issuing an immutable UUID certificate code, or rejects dossier back to student with remarks.

### 4. Registrar & Accounts Workspace (`/registrar` & `/registrar/requests/:id`)
- **Reconciliation Queue**: Filter requests by `CLEARED` (awaiting verification) and `REFUND_VERIFIED` (awaiting payment reference).
- **Roster Provenance Panel**: Inspects student enrollment origin (`roster_source`, `roster_created_by_name`) with the advisory notice: *"Check that the roster entry was created by the student's own department"*.
- **Audited Bank Details Reveal**: Security modal with confirmation notice (*"This action is recorded in the audit log"*), transient memory display, 30-second countdown auto-hide timer, manual hide action, and 429 rate limit protection.
- **Verify Refund**: Form enforcing `0 <= deductions <= deposit_amount` with live breakdown calculation.
- **Mark Processed**: Records bank UTR / NEFT disbursement payment reference.

### 5. Institutional Administration (`/admin`)
- **Offices & Staffing Dashboard (`/admin/offices`)**:
  - Master table of all academic and service departments with active officers and HoDs.
  - Staffing gap badges (`Needs Officer`, `Needs HoD`) and summary metrics.
  - Quick action buttons to directly assign officers or HoDs to understaffed offices.
- **Staff & User Directory (`/admin/users`)**:
  - Filterable by search query, role, department, and active status.
  - Single user creation with department validation (Chairperson / HoD role is strictly restricted to academic departments).
  - Bulk staff CSV upload with template download, row-by-row report, and one-time credentials export.
  - On-demand password reset and account activate/deactivate toggle (with self-deactivation protection).
  - One-time temporary password modal that wipes credentials from memory upon dismissal.
- **Master Student Roster (`/admin/roster`)**: Fallback student directory search, profile editor, and CSV batch ingestion.
- **Master Lab Catalog (`/admin/lab-courses`)**: Global laboratory course directory, creation modal, edit modal, and CSV ingestion.

### 6. Public Certificate Verification (`/verify`, `/verify/:code`)
- **Zero-Authentication Verification**: Publicly accessible page for employers and third parties.
- **QR Code Resolution**: Resolves automatically when scanning the QR code on clearance certificates.
- **Privacy-Preserving Verification**: Validates certificate authenticity using icons and text, rendering issue date, masked registration number, student programme, and department (never reveals student names, emails, phones, or bank details).

---

## 6. Directory Structure

```
frontend/
├── docs/                   # Viewport audits and screenshots
├── public/                 # Static assets, SVG favicons, icons
├── src/
│   ├── api/                # Modular Axios REST client services
│   │   ├── admin.js        # Offices, users, bulk staff, roster & lab catalog
│   │   ├── auth.js         # Login, Google SSO, config, OTP, user profile
│   │   ├── department.js   # Queue, decisions, roster, lab catalog, dossier
│   │   ├── hod.js          # HoD queue, dossier, decisions, add office
│   │   ├── registrar.js    # Refund queue, verification, disbursement, bank reveal
│   │   ├── student.js      # Declarations, bank details, resubmit, certificate
│   │   └── verify.js       # Public certificate verification
│   ├── auth/               # Authentication contexts & route guards
│   │   ├── AuthContext.jsx # Global JWT auth state, role helpers, logout
│   │   └── ProtectedRoute.jsx # Role-based route guard & redirect logic
│   ├── components/         # Reusable UI components & patterns
│   │   ├── ui/             # Radix UI primitives styled with Tailwind CSS
│   │   ├── AppShell.jsx    # Responsive shell, wordmark, academic role nav
│   │   ├── CsvUpload.jsx   # Drag-and-drop CSV uploader, size check, report
│   │   ├── DataTable.jsx   # TanStack Table v9 wrapper with search & pagination
│   │   ├── EmptyState.jsx  # Consistent empty state presentation
│   │   ├── ErrorBoundary.jsx # Global React error boundary with diagnostic display
│   │   ├── StatusBadge.jsx # Color-coded status pills with Lucide icons
│   │   └── StepTimeline.jsx # Visual multi-step clearance progress indicator
│   ├── hooks/              # Custom React hooks
│   │   ├── useAuthConfig.js    # TanStack Query hook loading /auth/config once at startup
│   │   └── useDocumentTitle.js # View-specific document title updater
│   ├── lib/                # Shared utilities and configurations
│   │   ├── axios.js        # Axios instance with 401 session-expired interceptor
│   │   └── utils.js        # Class name merge utilities (clsx + twMerge)
│   ├── pages/              # View layer organized by user role
│   │   ├── admin/          # Admin offices, users directory, roster & lab fallbacks
│   │   │   ├── AdminOfficesPage.jsx
│   │   │   ├── AdminUsersPage.jsx
│   │   │   ├── AdminRosterPage.jsx
│   │   │   └── AdminLabCoursesPage.jsx
│   │   ├── hod/            # HoD queue and audit detail review
│   │   │   ├── HodQueuePage.jsx
│   │   │   └── HodRequestDetailPage.jsx
│   │   ├── officer/        # Department clearance queue, roster & lab catalog
│   │   │   ├── OfficerQueuePage.jsx
│   │   │   ├── OfficerRosterPage.jsx
│   │   │   ├── OfficerLabCatalogPage.jsx
│   │   │   └── OfficerRequestDetailPage.jsx
│   │   ├── public/         # Landing, Login, Signup, Verify, Help, ChangePassword, 404, 403
│   │   │   ├── LandingPage.jsx
│   │   │   ├── LoginPage.jsx
│   │   │   ├── SignupPage.jsx
│   │   │   ├── VerifyPage.jsx
│   │   │   ├── HelpPage.jsx
│   │   │   ├── ChangePasswordPage.jsx
│   │   │   ├── NotFoundPage.jsx
│   │   │   └── ForbiddenPage.jsx
│   │   ├── registrar/      # Refund reconciliation & audited bank reveal
│   │   │   ├── RegistrarRefundPage.jsx
│   │   │   └── RegistrarRequestDetailPage.jsx
│   │   └── student/        # Student dashboard, timeline, bank modal
│   │       ├── StudentDashboard.jsx
│   │       └── StudentApplyPage.jsx
│   ├── App.jsx             # Router, Suspense fallbacks, QueryClient provider
│   ├── main.jsx            # Application bootstrap with typography styles
│   └── index.css           # Tailwind base styles and Minimalist White tokens
├── jsconfig.json           # Path alias configuration (@ -> ./src)
├── tailwind.config.js      # Custom theme colors, typography, borders
├── vite.config.js          # Vite configuration with React and path resolution
└── package.json            # Dependencies and scripts
```

---

## 7. Design System & Polish

- **Theme**: "Premium Minimalist White" — crisp pure white backgrounds (`#FFFFFF`), subtle zinc borders (`#E4E4E7`), high-contrast typography (`#09090B`), and restrained brand cobalt accents (`#2563EB`).
- **Typography**: Syne for headings (`font-heading`) and Inter for body text (`font-sans`).
- **Page Transitions**: Snappy transitions under 300 ms (`transition-colors duration-150 / duration-200`).
- **Motion Restraint**: Lenis smooth scrolling and GSAP animations are **dynamically imported** exclusively on the public Landing route (`/`). All dashboards remain lightweight and calm. Respects `prefers-reduced-motion: reduce`.
- **Accessibility & Focus**: High-contrast `:focus-visible` rings on all interactive inputs and buttons, ARIA landmark semantics, Radix UI focus-trapping dialogs, and WCAG AA contrast compliance.
- **Session Lifecycle**: 401 response interceptor in `axios.js` automatically purges expired tokens and smoothly routes back to `/login` with an informational toast.

---

## 8. Screenshots & Visual Verification

> **Synthetic Data Requirement**: All screenshots and walkthrough captures must be generated strictly using synthetic seed accounts (`@example.edu` or unseeded demo students). Never capture or publish production student records or unmasked financial details.

Screenshots and viewport responsive audits across desktop (`1280px`), tablet (`768px`), and mobile (`375px`) are archived under `frontend/docs/screens/`.
