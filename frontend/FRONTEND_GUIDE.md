# Frontend Architecture & Developer Guide — SVSU No-Dues Clearance System

This guide outlines the frontend architecture, design system, component hierarchy, state management, and API integration rules for the **Shri Vishwakarma Skill University (SVSU) No-Dues Clearance System**.

---

## 1. Project Context & Clearance Workflow

The application replaces a multi-week paper-based clearance form with an automated digital workflow:
1. **Student Pre-requisite**: Student verifies official roster identity via 2-step OTP, registers an Indian bank account for security deposit refund, and initiates clearance.
2. **Parallel Department Reviews**: When submitted, the application dispatches reviews across all 10 applicable departments (Library, Sports, Hostel, Computer Centre, General Branch, DSW, NSS, R&S, IIC, Own Academic Department) concurrently.
3. **Selective Resubmission**: If any department officer flags dues and rejects with remarks, the request moves to `ACTION_NEEDED`. The student settles the issue and resubmits **only to that specific department**.
4. **Chairperson (HoD) Clearance**: Once all departments approve, the request moves to `HOD_REVIEW`. The Chairperson grants final clearance, issuing a tamper-proof certificate with an unguessable UUID code and QR code.
5. **Refund Reconciliation**: The Accounts & Registration section audits security deposit deductions, records the bank UTR/NEFT payment reference, and updates refund status to `PROCESSED`.

---

## 2. Design System: "Premium Minimalist White" + Restrained Brand Accent

- **Theme Palette**:
  - Background: Pure White (`#FFFFFF`, `hsl(0 0% 100%)`)
  - Foreground: Off-black (`#09090B`, `hsl(240 10% 3.9%)`)
  - Primary / Buttons: Solid Black (`#000000`, `hsl(0 0% 0%)`) with crisp white text (`#FFFFFF`)
  - Restrained Brand Accent: Deep Indigo / Cobalt (`hsl(221 83% 53%)` / `#2563EB`) for subtle highlights, interactive states, and key CTAs
  - Card & Surfaces: `#FFFFFF` with `#E5E7EB` borders (`border-border`)
  - Muted / Secondary: `#F4F4F5` (`hsl(240 4.8% 95.9%)`)
  - Destructive: `#EF4444` (`hsl(0 84.2% 60.2%)`)
  - Dark Mode: **Explicitly disabled** (no `.dark` classes).
- **Typography**:
  - Headings (`h1`–`h6`): **Syne** (`@fontsource/syne`, font weights 600, 700, 800)
  - Body & UI: **Inter** (`@fontsource/inter`, font weights 400, 500, 600, 700)
- **Type Scale**:
  - Display (Hero): `text-4xl sm:text-6xl lg:text-7xl` (`leading-[1.08]`)
  - Page Titles (`h1`): `text-2xl sm:text-3xl` font-extrabold
  - Section Headings (`h2`): `text-xl sm:text-2xl` font-bold
  - Card Titles (`h3`): `text-sm sm:text-base` font-bold
  - Body Copy: `text-xs sm:text-sm` leading-relaxed
  - Eyebrows & Badges: `text-[10px] sm:text-xs` font-semibold tracking-wider uppercase
- **Elevation Tiers**:
  - `shadow-2xs`: Subtle hairline boundary (`0 1px 2px rgba(0,0,0,0.03)`)
  - `shadow-xs`: Resting card elevation (`0 1px 2px 0 rgba(0,0,0,0.04)`)
  - `shadow-card`: Hover card elevation (`0 4px 12px rgba(0,0,0,0.06)`)
- **Spacing Scale & Rhythm**:
  - Desktop Section Padding: `py-20 md:py-24`
  - Mobile Section Padding: `py-12 md:py-14`
  - Container Max Width: `max-w-7xl` with `px-4 sm:px-6 lg:px-8`
- **Motion & Accessibility**:
  - Animations (GSAP line reveal, Lenis smooth scrolling) are **lazy-loaded strictly on the public Landing Page (`/`)**.
  - Respects `prefers-reduced-motion: reduce`: all transitions, animations, and marquee tickers collapse to zero duration when requested by the OS.
  - Mix-blend-mode magnetic cursor activates strictly on fine pointers (`@media (pointer: fine)`) and disables over text inputs, textareas, and buttons.

---

## 3. Directory Layout & Architecture

```
frontend/
├── docs/
│   └── screens/                  # Viewport audit screenshots (1280px, 768px, 375px)
├── src/
│   ├── api/                      # Strongly typed REST client modules
│   │   ├── auth.js               # Login, Me, OTP request & verify
│   │   ├── student.js            # Bank details, Request lifecycle, Resubmits, PDF blob
│   │   ├── department.js         # Queue, Decision, Roster, Lab Catalog, Dossier, Add Office
│   │   ├── hod.js                # HoD Queue, Request Detail, Decision, Add Office
│   │   ├── registrar.js          # Queue, Detail, Verify Refund, Mark Processed, Audited Reveal
│   │   └── verify.js             # Public certificate check by UUID
│   ├── auth/                     # Authentication & Authorization
│   │   ├── AuthContext.jsx       # Global JWT, user profile, role helpers
│   │   └── ProtectedRoute.jsx    # Role-based route guard & redirect logic
│   ├── components/               # Custom and domain-specific UI components
│   │   ├── AppShell.jsx          # Responsive shell, wordmark, mobile Sheet, academic role nav
│   │   ├── DataTable.jsx         # TanStack Table + shadcn Table (sort, paginate, mobile cards)
│   │   ├── CsvUpload.jsx         # Drag-and-drop CSV uploader, size check, template download, report
│   │   ├── StatusBadge.jsx       # Icon + tint badges for Clearance & Approvals
│   │   ├── StepTimeline.jsx      # 4-stage visual clearance progress pipeline
│   │   ├── EmptyState.jsx        # Standard empty state card
│   │   └── ui/                   # Official shadcn/ui components (Radix primitives)
│   ├── lib/
│   │   ├── axios.js              # Axios instance, Bearer injector, 401/403 interceptors
│   │   └── utils.js              # cn class-name utility
│   ├── pages/                    # Route page views
│   │   ├── public/
│   │   │   ├── LandingPage.jsx   # In-code product visual, hero reveal, marquee
│   │   │   ├── LoginPage.jsx     # 2-column layout + collapsible demo email chips
│   │   │   ├── SignupPage.jsx    # 2-step OTP verification & account creation
│   │   │   ├── VerifyPage.jsx    # Public QR verification view
│   │   │   ├── NotFoundPage.jsx  # 404 handler
│   │   │   └── ForbiddenPage.jsx # 403 authorization handler
│   │   ├── student/
│   │   │   ├── StudentDashboard.jsx # Stat strip, bank details, live checklist, "Add More" panel, resubmit, PDF
│   │   │   └── StudentApplyPage.jsx # 5-step accessible clearance declaration wizard
│   │   ├── officer/
│   │   │   ├── OfficerQueuePage.jsx         # Department Officer Queue, status tabs, decision modal
│   │   │   ├── OfficerRosterPage.jsx        # Academic officer student roster list & CSV ingestion
│   │   │   ├── OfficerLabCatalogPage.jsx    # Academic officer lab subjects catalog & CSV ingestion
│   │   │   └── OfficerRequestDetailPage.jsx # Academic clearance dossier & add office dialog
│   │   ├── hod/
│   │   │   ├── HodQueuePage.jsx             # HoD Queue for academic department
│   │   │   └── HodRequestDetailPage.jsx     # Full Dossier, sign-off matrix, approval/rejection, add office
│   │   ├── registrar/
│   │   │   ├── RegistrarRefundPage.jsx       # Cleared queue, deduction calculator, payment ref
│   │   │   └── RegistrarRequestDetailPage.jsx # Financial audit, roster provenance, 30s bank reveal
│   │   └── admin/
│   │       ├── AdminOfficesPage.jsx       # Department staffing dashboard & staffing gaps
│   │       ├── AdminUsersPage.jsx         # User directory, provisioning, bulk upload, passwords
│   │       ├── AdminRosterPage.jsx        # Master roster fallback & CSV ingestion
│   │       └── AdminLabCoursesPage.jsx    # Master lab courses catalog & CSV ingestion
│   ├── App.jsx                   # React Router, ErrorBoundary & TanStack Query root provider
│   ├── index.css                 # Minimalist white theme tokens & animations
│   └── main.jsx                  # Entrypoint with Syne & Inter font imports
```

---

## 4. Quality & Accessibility Verification

- **Contrast**: Text elements meet WCAG AA contrast ratio standards (foreground `#09090b` on `#ffffff` is 19.3:1).
- **Keyboard Navigation**: All interactive controls (buttons, inputs, links, dialog triggers) exhibit clear, high-contrast `:focus-visible` rings with offset.
- **Responsiveness**: Audited and confirmed without horizontal scroll across `375px`, `768px`, `1280px`, and `1536px`.
- **Motion Restraint**: Animations are subtle (150–250ms), utilize hardware-accelerated transforms/opacity, and honor `prefers-reduced-motion`.

---

## 5. Phase 2 Role Interfaces & Shared Components

### A. Shared DataTable (`src/components/DataTable.jsx`)
- Built on TanStack Table (`@tanstack/react-table`) and shadcn Table (`table.jsx`).
- **Sortable Columns**: Interactive column headers with ascending, descending, and unsorted indicators (`ArrowUpDown`, `ArrowUp`, `ArrowDown`).
- **Pagination**: Supports both client-driven and server-driven (`manualPagination`) modes, with record count, current page index, total pages, and navigation buttons.
- **Skeleton Rows**: Smooth animated skeleton rows rendered during in-flight network requests.
- **Empty State**: Integrated `EmptyState` component displaying customized icons, titles, and contextual guidance.
- **Mobile Card View**: Fluid responsive breakpoint (`md`) swapping the table view for an accessible stacked card layout with optional `renderMobileCard` customization.
- **Status Filter Tabs**: Integrated `Tabs` component for status filtering (`PENDING`, `APPROVED`, `REJECTED`, `ALL`).

### B. Shared CsvUpload (`src/components/CsvUpload.jsx`)
- Reusable drag-and-drop CSV ingestion component adhering to the "Premium Minimalist White" system.
- **Client-Side Validation**: Restricts input to `.csv` mime types and enforces a strict 2 MB maximum file size limit with accessible inline error alerts.
- **Template Download**: Dedicated "Download template" action retrieving authenticated `.csv` templates via Axios with `responseType: 'blob'`.
- **Detailed Execution Report**: Renders metrics for `total_rows`, `created_count`, `updated_count`, and `rejected_count`, alongside an interactive table of rejected rows detailing row numbers and validation failure reasons.

### C. Dynamic Academic Navigation (`src/components/AppShell.jsx`)
- Uses `GET /departments` and `authApi.me()` to determine if a logged-in `dept_officer` belongs to an `academic` department (`kind === 'academic'`).
- Conditionally presents the **Student Roster** (`/officer/roster`) and **Lab Catalog** (`/officer/lab-catalog`) navigation links exclusively to academic officers.

### D. Department Officer Interfaces
- **Queue Interface (`/officer`)**:
  - Displays assigned department context and status tabs (`PENDING`, `APPROVED`, `REJECTED`, `ALL`).
  - Server-side search over student name and registration number.
  - Rows display `declared_is_hosteller` (scoped to Hostel office), declared subject chips matching the officer's lab, `others_note` (for unlinked assigned offices), and a direct link to the clearance dossier.
  - Decision Modal with Approve/Reject choices, live 500-character counter, mandatory remarks on rejection, and plain text notice explaining approvals with remarks (e.g. *"student did not use this lab"*).
  - Handles `409 Conflict` and `404 Not Found` without optimistic updates.
- **Academic Student Roster (`/officer/roster`)**:
  - Exclusively available to academic department officers for managing students in their department's programmes.
  - Server-filtered, paginated student roster with search.
  - "Add Student" modal and "Edit Student" modal. Clear explanation when email edits are rejected with `HTTP 409 Conflict` because an active user account already exists.
  - Integrated `CsvUpload` utilizing `GET /department/roster/template.csv` and `POST /department/roster/upload`.
- **Academic Lab Catalog (`/officer/lab-catalog`)**:
  - Catalog of laboratory subjects belonging to the officer's academic department.
  - Search and active/inactive status filters.
  - Create Subject modal allowing mapping to `ASSIGNED_ONLY` service departments.
  - Inline active toggle (`PATCH /department/lab-courses/{id}` with `{ is_active }`).
  - Integrated `CsvUpload` utilizing `GET /department/lab-courses/template.csv` and `POST /department/lab-courses/upload`.
- **Dossier & Add Office (`/officer/requests/:id`)**:
  - Accessible to all department officers whose office is on the request.
  - **Academic Officer (Full Dossier)**: Displays full parallel review matrix, student academic profile, hostel residency status, declared lab courses, others note, and "Add Office" modal (`POST /department/requests/{id}/add-department`).
  - **Service / Non-Academic Officer (Limited Dossier)**: Displays student identity, academic department, own declared lab subjects, hostel declaration (if hostel office), others note (if applicable), and their own department's approval line. Unrelated officers receive `404 Not Found`.

### E. Chairperson / HoD Interface (`/hod` & `/hod/requests/:id`)
- **Review Queue (`/hod`)**: Lists students in `HOD_REVIEW` status whose prior departmental clearances have all been approved.
- **Full Dossier View (`/hod/requests/:id`)**:
  - Student identity, course, and enrollment status (Hosteller vs Day Scholar).
  - Approvals matrix showing status, remarks, decision timestamps, `added_by_name`, and `added_reason`.
  - Declared lab subjects, hostel status, and others note.
  - "Add Office" modal allowing HoD to dispatch a request to additional departments (`POST /hod/requests/{id}/add-department`).
  - Decision Panel: Approve or Reject (returns dossier to student with mandatory remarks).
  - Prominent display and clipboard copy of `certificate_code` upon approval.

### F. Registrar & Accounts Refund Interface (`/registrar` & `/registrar/requests/:id`)
- **Queue (`/registrar`)**:
  - Tabs for `CLEARED` (awaiting refund verification) and `REFUND_VERIFIED` (awaiting payment processing).
  - Displays student name, registration number, deposit amount, deductions, and final payout amount.
  - Direct "Inspect" link to the full refund inspection page.
- **Refund Inspection & Audit Page (`/registrar/requests/:id`)**:
  - Student identity, programme, and clearance timeline.
  - **Roster Provenance Panel**: Renders `roster_source` and `roster_created_by_name` exclusively on this page with the advisory notice: *"Check that the roster entry was created by the student's own department"*.
  - **Audited Bank Details Reveal**:
    - Masked account display by default (`••••••••1234`).
    - Dedicated "Reveal full details" trigger prompting an `AlertDialog` warning: *"This action is recorded in the audit log"*.
    - Mutation configured with `gcTime: 0`; holds decrypted account numbers in transient memory only.
    - 30-second countdown auto-hide timer and manual "Hide" button.
    - Handles rate-limiting (`HTTP 429 Too Many Requests`).
  - **Verify Refund Action**: Form enforcing `0 <= deductions <= deposit_amount` with live calculation of net payable amount and confirmation modal.
  - **Mark Processed Action**: Modal for recording the bank UTR/NEFT payment reference (`POST /registrar/requests/{id}/mark-processed`).

### G. Student Clearance & 5-Step Application Wizard (`/student/apply` & `/student`)
- **Declaration-Driven Clearance**:
  - Clearance departments are declared by the student: hostel residency, lab/workshop courses from the departmental catalog, and additional assigned-only offices.
- **5-Step Application Wizard (`/student/apply`)**:
  - **Step 1 (Bank Details)**: Validates Indian bank account, IFSC code, beneficiary name, and branch address (`PUT /student/bank-details`).
  - **Step 2 (Residence Status)**: Radio cards for Hosteller vs Day Scholar (`is_hosteller`).
  - **Step 3 (Labs & Workshops)**: Dynamically fetches student's academic lab catalog (`GET /student/lab-catalog`). Features live search filter, course details, and removable summary chips.
  - **Step 4 (Other Offices & Notes)**: Fetches assigned-only departments (`GET /departments/assigned-only`) and provides an optional note textarea.
  - **Step 5 (Review & Submission)**: Unified declaration summary card. Requires explicit confirmation checkbox before invoking `POST /student/requests`.
- **Student Dashboard Enhancements (`/student`)**:
  - Clearance cards displaying status, remarks, rejection history, declared subjects, and `added_reason` banners.
  - Targeted resubmission for rejected departments.
  - "Add More" panel for supplemental assigned offices (`POST /student/requests/{id}/departments`) and lab subjects (`POST /student/requests/{id}/lab-courses`).
  - Digital Certificate download (`GET /student/requests/{id}/certificate.pdf`).

---

## 6. Resolved Backend Capabilities & API Contract Compliance

All previously identified backend capability gaps have been completely resolved and verified against the live backend contract:

1. **Queue Item Hostel & Special Declaration Scoping (`GET /department/queue`)**:
   - `DepartmentQueueItem` provides `declared_is_hosteller` (scoped as a boolean strictly for the Hostel office, and `null` for other offices).
   - `others_note` is returned for dealing offices that are on the request but unlinked to any specific lab course.
   - Frontend renders badges for hostel residency status and notes on both desktop table rows and mobile card layouts.

2. **Cross-Department Dossier Access (`GET /department/requests/{id}`)**:
   - All department officers whose office is on an active clearance request can view the clearance dossier.
   - Student's academic department officer receives the full dossier (complete approval matrix and candidate offices to add).
   - Non-academic officers receive a limited dossier (student details, academic department, own declared lab subjects, hostel declaration if hostel office, others note if applicable, and their own approval record). Officers from unrelated departments receive `404 Not Found`.

3. **Student Security Deposit Refund Visibility (`GET /student/requests/current`)**:
   - Returns complete refund financial status: `refund_status`, `deposit_amount`, `deductions`, `final_amount`, and transaction `payment_reference` (UTR/NEFT) once disbursed.
   - Frontend dashboard renders a dedicated "Security Deposit Refund Summary" card when financial data is present.

4. **Dynamic Other Offices Validation (`POST /student/requests`)**:
   - Supports `other_department_ids` (and alias `other_office_ids`), validating offices are `ASSIGNED_ONLY`, unlinked to lab courses in the catalog, and have an active officer.

5. **Mid-Clearance Lab Course Declaration (`POST /student/requests/{id}/lab-courses`)**:
   - Fully registered on the student router and confirmed in `/openapi.json`. Automatically rolls request status back to `SUBMITTED` if currently in `HOD_REVIEW`.

6. **System Health Check & Security Guardrails (`GET /health`)**:
   - Database probe endpoint (`SELECT 1`) returning `200 OK` or `503 Service Unavailable`.
   - Production startup validation enforces secret length, disabling console mail, disabling dev OTPs, and Fernet encryption key configuration.

---

## 7. Institutional Administration & Verification Architecture

### A. Offices & Staffing Health Dashboard (`/admin/offices`)
- **Primary Admin Screen**: Serves as the landing hub for system administrators.
- **Department Staffing Health**: Table rendering every university department, categorization (`academic` vs `service`), active officers, and HoD assignment.
- **Staffing Gap Badges**: High-visibility warning badges (`Needs Officer`, `Needs HoD`) flagging unstaffed offices that would block student clearance workflows.
- **Summary KPI Strip**: Live counters for total offices, academic faculties, service branches, and total offices needing staff.
- **Direct Assignment Actions**: Table row shortcuts to provision a dedicated officer or HoD directly for that department.

### B. Staff & User Directory (`/admin/users`)
- **User Directory**: Searchable, role-filtered, department-filtered, and active-status-filtered paginated `DataTable` (`GET /admin/users`).
- **Staff Provisioning Form**: Enables administrators to create accounts for `dept_officer`, `hod`, `registrar_accounts`, and `admin`. Dynamically restricts Chairperson (HoD) provisioning strictly to academic departments.
- **Bulk Staff CSV Upload**:
  - Ingestion modal with sample template download (`email, full_name, role, department`).
  - Row-by-row diagnostic report (`total_rows`, `created_count`, `rejected_count`).
  - Secure credential table with individual copy actions and a one-time "Download credentials CSV" option.
- **One-Time Temporary Password Security**:
  - Temporary passwords returned by user creation, bulk upload, or password resets are held strictly in component memory and displayed in a high-security dialog.
  - Cleared immediately upon dialog dismissal; never persisted in localStorage, sessionStorage, URLs, or console logs.
- **Credential Administration**:
  - Instant temporary password reset for any user (`POST /admin/users/{id}/reset-password`).
  - Account activation and deactivation toggle (`PATCH /admin/users/{id}/active`) with confirmation dialogs and self-deactivation protection.

### C. Master Roster & Lab Course Fallbacks (`/admin/roster` & `/admin/lab-courses`)
- **Global Student Roster (`/admin/roster`)**: Searchable roster directory, contact profile editing (mobile & address), and CSV upload. Note: residency and security deposit columns are hidden from this view with an advisory notice, as residency is declared directly by students when applying and deposit amounts are verified by Accounts during refund processing.
- **Global Lab Course Catalog (`/admin/lab-courses`)**: Comprehensive lab course directory across all academic faculties, course creation modal (mapping to `ASSIGNED_ONLY` service departments), metadata editor, and active status toggle.

### D. Public Certificate Verification (`/verify`, `/verify/:code`)
- **Zero-Authentication Verification**: Publicly accessible page for employers and third parties to verify certificate validity.
- **QR Code Target**: Resolves directly when scanning the QR code embedded in student clearance certificates (`/verify/:code`).
- **Privacy-Preserving Verification**: Displays certificate validity using icons and text (not color alone), rendering issue timestamp, masked student roll number, programme, and academic department (never reveals student names, emails, phones, or bank details).

### E. System Polish, Performance & Accessibility
- **Bundle Splitting & Lazy Engines**: Lenis momentum scrolling and GSAP animation engines are dynamically imported (`import()`) exclusively on the public Landing route (`/`). Authenticated dashboard views remain lightweight and calm.
- **Sub-300ms Transitions**: Micro-interactions and dialog transitions run with hardware-accelerated transforms and collapse to 0ms when `prefers-reduced-motion` is active.
- **Accessibility & Contrast**: High-contrast `:focus-visible` rings, ARIA landmark semantics, Radix UI dialog focus trapping, and WCAG AA contrast compliance.
- **Session Lifecycle**: 401 response interceptor in `axios.js` automatically purges expired tokens and smoothly routes back to `/login` with an informational toast.
- **Global Error Boundary (`ErrorBoundary.jsx`)**: Catches unhandled JavaScript rendering exceptions and presents a clean recovery screen with "Reload Page" and "Return to Home".

---

## 8. Seeded Demo Accounts Reference

All seeded demo accounts in the development database are created via `backend/scripts/seed_synthetic.py`. Default passwords are never published in public documentation; in development environments, they are derived from the `SEED_DEFAULT_PASSWORD` environment variable in `backend/.env`.

**Pilot Invariant — Zero Demo Students**: To maintain real data integrity for production and pilot deployments, zero demo students are seeded into the system. Student roster entries must be ingested by academic departments or administrators.

| Role | Demo Email Address | User Full Name / Scope |
|---|---|---|
| **System Administrator** | `admin@svsu.ac.in` | System Administrator (Demo) |
| **Registrar / Accounts** | `registrar.accounts@svsu.ac.in` | Accounts Officer (Demo) / R&S Branch |
| **Chairperson (HoD) CS/IT** | `hod.csit@svsu.ac.in` | Chairperson Skill Department of CS/IT (Demo) |
| **Academic Officer (CS/IT)** | `officer.csit@svsu.ac.in` | Skill Department of CS/IT Officer (Demo) |
| **Department Officer (Library)** | `library.officer@svsu.ac.in` | Library Officer (Demo) / Central Library |
| **Department Officer (Hostel)** | `hostel.officer@svsu.ac.in` | Hostel (Boys/Girls) Officer (Demo) |
| **Department Officer (Sports)** | `sports.officer@svsu.ac.in` | Sports Officer (Demo) / Sports Section |
| **Department Officer (Accounts)** | `accounts.officer@svsu.ac.in` | Account Section Officer (Demo) |

> **Development Quick-Fill Chips & Leak Prevention**:
> - Quick-fill chips on the `/login` page are rendered exclusively in development mode (`import.meta.env.DEV`). They pre-fill staff emails only and never auto-populate passwords.
> - The production build (`npm run build`) automatically executes `npm run check:leaks` (`frontend/scripts/check_leaks.mjs`), which scans all compiled assets in `dist/` and aborts if forbidden patterns (`example.edu`, `DEMO2026`, or `dev_otp`) are detected.

---

## 9. Security, Cancellation & Pilot Hardening

### A. Forced & Voluntary Password Change (`/change-password`)
- **Forced Password Change Enforcement**:
  - Accounts provisioned by an administrator or reset via temporary password carry `must_change_password: true` in `/auth/me` and the login response.
  - While this flag is active, `ProtectedRoute` and the Axios 403 interceptor (`detail === 'PASSWORD_CHANGE_REQUIRED'`) redirect navigation to `/change-password` and block access to any other route.
  - Nav links in `AppShell` are hidden while keeping "Sign Out" completely accessible.
  - Form requires current password, new password ($\ge$ 10 characters, different from current), and confirm password match, with a real-time reactive checklist and show/hide toggles.
- **Voluntary Password Change**:
  - Accessible to all authenticated roles via the user profile dropdown menu in `AppShell`.
  - On successful update, calls `refreshProfile()` to sync state and redirects to the role's default view.

### B. Sign-Up, Rate Limits & Anti-Enumeration
- **Enumeration Resistance**:
  - `POST /auth/signup/request-otp` always responds with a generic dispatch message (`"If the details match our records, a code has been sent to your university email."`).
  - The frontend always advances to Step 2 (Verification code entry) and displays this message to prevent account enumeration.
  - Dev OTP hints are strictly guarded by `import.meta.env.DEV`.
- **Rate Limit Resilience (HTTP 429)**:
  - Both Login and Sign-Up inspect `Retry-After` response headers, display a user-friendly notice in minutes, and disable submit actions during the active cooldown period.
  - A dedicated "Resend code" button features an active countdown timer (60s).
- **Password Strength**:
  - Student registration requires a minimum 10-character password.

### C. Clearance Request Cancellation (`CANCELLED` Lifecycle)
- **Status Integration**: `CANCELLED` is integrated into `StatusBadge`, `StepTimeline`, dashboards, and queues.
- **Student Cancellation**:
  - Displayed on the student dashboard only when **all** departmental reviews are in `PENDING` status.
  - Requires a mandatory cancellation reason (`POST /student/requests/{id}/cancel`).
  - Once cancelled, an informative banner is displayed alongside an "Apply Again" button routing to `/student/apply`.
- **Academic Officer Cancellation**:
  - Available in `/officer/requests/:id` exclusively for academic department officers.
  - Hidden when the request is `CLEARED`, `REFUND_VERIFIED`, or `CANCELLED`.
  - Requires a mandatory audit reason (`POST /department/requests/{id}/cancel`).
- **Administrative Emergency Cancellation**:
  - Administrators can cancel an active clearance request by specifying its ID and an audit reason via `POST /admin/requests/{id}/cancel`.
- **API Gap Note**:
  - *Admin Request Search Gap*: The backend provides `POST /admin/requests/{id}/cancel` for request cancellation by ID, but lacks a search or listing endpoint (`GET /admin/requests?search=...`) to look up clearance requests by student roll number or name. The frontend currently surfaces an ID-based cancellation card on `/admin/offices`.

### D. Public Help & Guide (`/help`)
- A public static guide explaining the 5-step digital clearance lifecycle, deposit refund policies, and QR code certificate verification.
- Displays technical support contact info from `VITE_SUPPORT_EMAIL` when configured in `.env` (hidden when unset).
- Emphasizes the university security reminder: *"You never need to share your account credentials or verification codes with anyone."*

---

## 10. Google Authentication (OAuth2 SSO) & Content-Security-Policy (CSP)

### A. Authentication Architecture & Flow
1. **Startup Configuration (`GET /auth/config`)**:
   - Loaded once at startup using TanStack Query (`useAuthConfig` hook with `staleTime: Infinity`).
   - Retrieves `google_enabled`, `google_client_id`, `allowed_domain_hint`, and `otp_signup_enabled`.
2. **Lazy-Loaded Google Identity Services (GIS)**:
   - When `google_enabled` is true and `google_client_id` is present, the GIS client script (`https://accounts.google.com/gsi/client`) is lazy-loaded strictly on the `/login` page.
   - Initialized with `client_id` and renders an official "Continue with Google" button with the subtext: `Use your university account (@<allowed_domain_hint>)`.
   - Credentials returned in the callback are sent directly to `POST /auth/google { credential }`. The raw token is **never stored locally** in browser storage or cookies.
   - On successful response, tokens are persisted in `localStorage` via `AuthContext`, followed by `/auth/me` profile fetching and automatic role-based redirect.
3. **Staff & Admin Email/Password Section**:
   - Rendered below the Google button as a collapsed `<details>` section: *"Staff and admin: sign in with email and password"*.
   - If Google sign-in is disabled, missing a client ID, or blocked by a browser privacy extension, this section automatically expands.
   - Development quick-fill chips (`import.meta.env.DEV` only) pre-fill the staff email and automatically open the password section.

### B. Error Handling & Edge States
- **`NOT_ELIGIBLE` (HTTP 403)**:
  - Triggered when a student's Google email does not exist on the approved academic roster.
  - Displays a clean amber alert panel: *"Your account is not in the student list. Please contact your department office."*
- **`ACCOUNT_DISABLED` (HTTP 403)**:
  - Triggered when a user account has been deactivated by an administrator.
  - Displays a rose alert panel: *"Your account has been deactivated. Please contact your department office or administrator."*
- **`SUB_MISMATCH` (HTTP 403)**:
  - Triggered if an existing user attempts to log in with a different Google account ID.
  - Displays: *"Google account ID mismatch. Please sign in with the university Google account originally linked to your record."*
- **Rate Limit (HTTP 429)**:
  - Reads the `Retry-After` header in seconds and formats it in minutes.
  - Temporarily pauses sign-in with an active countdown timer.
- **Script Failure / Privacy Blocker**:
  - If GIS fails to load or is blocked by browser tracking protection, displays: *"Google sign-in could not load. Staff can use email and password; students, please try another browser or disable tracking protection for this site."*
  - Automatically opens the staff email and password form.
- **Missing Client ID**:
  - The Google button is completely hidden and the login card defaults cleanly to the standard password form.

### C. Student Sign-Up Redirection (`/signup`)
- When `otp_signup_enabled` is `false`, any navigation to `/signup` immediately redirects to `/login` with an informational banner: *"Students now sign in with their university Google account. No separate sign-up is needed."*
- When `otp_signup_enabled` is `true`, the traditional 2-step OTP registration flow remains active.

### D. Administrator User Provisioning (`/admin/users`)
- **Single User Provisioning**:
  - Includes a "Google sign-in only (no password)" toggle.
  - When enabled, `google_only: true` is sent to `POST /admin/users`. The user is created without a password, and the one-time temporary password modal is suppressed with a toast notification: *"This user signs in with Google."*
- **Bulk Staff Provisioning**:
  - Supports an optional `google_only` (true/false) column in the uploaded CSV.
  - Provides a toggle to force all uploaded accounts to Google sign-in only.
  - The downloadable CSV template is updated to include the `google_only` column.

### E. Content-Security-Policy (CSP) Sources for Production
When deploying behind a reverse proxy (e.g., NGINX, Cloudflare, Caddy), configure the following CSP directives to allow Google Identity Services and the backend API:

```http
Content-Security-Policy:
  default-src 'self';
  script-src 'self' https://accounts.google.com/gsi/client;
  frame-src 'self' https://accounts.google.com/gsi/;
  connect-src 'self' https://accounts.google.com/gsi/ https://api.nodues.svsu.ac.in;
  style-src 'self' 'unsafe-inline' https://accounts.google.com/gsi/style;
  font-src 'self' data:;
  img-src 'self' data: https://accounts.google.com/;
```

---

## 10. Cold-Start Resilience & Wording Governance

### A. Free-Tier Cloud Hosting Cold-Start Handling
- **Extended Request Timeout**: Axios timeout is configured to **90 seconds** (`90000ms`) across all client requests to comfortably accommodate initial container boot times on free-tier hosting (e.g. Render, Railway).
- **Non-Blocking Wake-up Banner**: If any API request exceeds **4 seconds** before receiving a response, a non-blocking banner appears at the top of the viewport:
  > *"The server is waking up. This can take up to a minute the first time."*
  - Uses `pointer-events-none` so user interaction is never interrupted.
  - Automatically unmounts / clears once slow in-flight requests resolve.
- **GET Request Auto-Retry**: Idempotent `GET` requests are automatically retried **once** upon network errors or gateway status codes (`HTTP 502`, `HTTP 503`, `HTTP 504`).
- **Strict No-Retry on Mutations**: `POST`, `PUT`, `PATCH`, and `DELETE` requests are **never retried automatically**, avoiding duplicate clearance actions, submissions, or transactions.

### B. Wording Governance & Build-Time Audits
- **Zero Tech-Stack Mentions in User UI**: Mentions of frameworks (FastAPI, React 19, Tailwind CSS, shadcn/ui, Vite, PostgreSQL, etc.) are strictly prohibited across all user-facing text, page titles, meta tags, and tooltips.
- **Standardized University Footer**: All public and authenticated layouts render the clean copyright:
  > *"© 2026 Shri Vishwakarma Skill University"*
- **Automated Verification in `npm run build`**:
  1. `npm run check:leaks`: Rejects bundles in `dist/` containing forbidden development identifiers (`example.edu`, `DEMO2026`, `dev_otp`).
  2. `npm run check:wording`: Scans all files in `src/` and `index.html` for forbidden terms (`demo`, `FastAPI`, `Tailwind`, `shadcn`, `React 19`, `synthetic`), allowing exemptions only when explicitly annotated with `wording-ok`.
  3. `npm run check:contract`: Verifies 100% frontend API client alignment against the OpenAPI contract.

---

## 11. Multi-Office Membership Architecture

The frontend fully supports the additive multi-department membership model where a single staff account (one email, one identity) can be assigned to multiple university offices or academic teaching departments:

### A. Authentication & Shell Integration (`AppShell.jsx`)
- **Profile Memberships**: `user.departments` provides an array of `{ id, name, kind }` representing all assigned university facilities.
- **Office Chips in User Menu**: User dropdown and mobile sheet render badges for all assigned offices.
- **Academic Role Guarding**: Roster and Lab Catalog navigation links are displayed **strictly if $\ge 1$ membership is `academic`**. Pure service officers (e.g. Library and Sports only) never see roster or catalog links.

### B. Officer Queue (`/officer`)
- **Office Selector**: When an officer belongs to $>1$ office, an office selector pill bar appears with "All my offices" (displaying total pending dues across all offices from `office_counts`) alongside individual office buttons with their specific pending counts.
- **Office Column**: An "Office" column is dynamically included in the desktop table and mobile card view.
- **Decision Modal**: Prominently highlights `"Deciding for: <Office Name>"` to prevent decision confusion.
- **Single Office Fidelity**: When the officer belongs to exactly one office, the interface preserves the standard single-department view.

### C. Student Dossier Detail (`/officer/requests/:id`)
- **Independent Per-Office Sections**: When several of the officer's assigned offices appear on a student's clearance application, the page renders a distinct card/section for each office.
- **Office-Specific Context**: Each section independently surfaces the office status badge, relevant declared laboratory subjects, hostel residency declaration, student notes, and prior remarks.
- **Independent Decision Controls**: Separate Approve and Reject actions are provided for each office, recording decisions independently via `departmentApi.submitDecision`.

### D. Roster & Lab Catalog Scope Filtering
- When an officer belongs to multiple academic departments, both `/officer/roster` and `/officer/lab-catalog` provide an academic department selector narrowing the query scope by passing `department_id` to the API.

### E. Chairperson (HoD) Review Queue (`/hod`)
- When an HoD chairs multiple academic departments, the queue provides a department filter dropdown and displays a "Department" column in the table and mobile cards.

### F. Administrator Management (`/admin/users` & `/admin/offices`)
- **Multi-Select Provisioning**: User creation form features multi-select checkboxes for departments (enforcing $\ge 1$ office for officers and strictly academic departments for HoDs).
- **Directory Chips**: The staff directory table renders badges for each department assigned to a user.
- **Offices Management Panel**: Administrators can view, add, and remove assigned offices per user. The last remaining department is protected from removal, instructing administrators to deactivate the user account instead.
- **Bulk CSV Ingestion**: Downloadable template and parser support the `departments` column with pipe separation (e.g., `Library|Sports`).
- **Staffing Dashboard (`/admin/offices`)**: Shows subtle badges next to staff names indicating other university offices they represent.







