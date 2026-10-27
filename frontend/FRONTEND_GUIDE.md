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
│   │   ├── department.js         # Department Queue & Decision submission
│   │   ├── hod.js                # HoD Queue, Request Detail, Decision submission
│   │   ├── registrar.js          # Cleared Queue, Verify Refund, Mark Processed
│   │   └── verify.js             # Public certificate check by UUID
│   ├── auth/                     # Authentication & Authorization
│   │   ├── AuthContext.jsx       # Global JWT, user profile, role helpers
│   │   └── ProtectedRoute.jsx    # Role-based route guard & redirect logic
│   ├── components/               # Custom and domain-specific UI components
│   │   ├── AppShell.jsx          # Responsive shell, wordmark, mobile Sheet
│   │   ├── DataTable.jsx         # TanStack Table + shadcn Table (sort, paginate, mobile cards)
│   │   ├── StatusBadge.jsx       # Icon + tint badges for Clearance & Approvals
│   │   ├── StepTimeline.jsx      # 4-stage visual clearance progress pipeline
│   │   ├── EmptyState.jsx        # Standard empty state card
│   │   └── ui/                   # Official shadcn/ui components (Radix primitives)
│   │       ├── alert-dialog.jsx
│   │       ├── alert.jsx
│   │       ├── badge.jsx
│   │       ├── button.jsx
│   │       ├── card.jsx
│   │       ├── dialog.jsx
│   │       ├── input.jsx
│   │       ├── label.jsx
│   │       ├── pagination.jsx
│   │       ├── progress.jsx
│   │       ├── select.jsx
│   │       ├── separator.jsx
│   │       ├── sheet.jsx
│   │       ├── skeleton.jsx
│   │       ├── sonner.jsx
│   │       ├── table.jsx
│   │       ├── tabs.jsx
│   │       ├── textarea.jsx
│   │       └── tooltip.jsx
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
│   │   │   └── StudentDashboard.jsx # Stat strip, bank details, live checklist, resubmit, PDF
│   │   ├── officer/
│   │   │   └── OfficerQueuePage.jsx # Department Officer Queue, status tabs, decision modal
│   │   ├── hod/
│   │   │   ├── HodQueuePage.jsx     # HoD Queue for academic department
│   │   │   └── HodRequestDetailPage.jsx # Full Dossier, sign-off matrix, approval/rejection
│   │   ├── registrar/
│   │   │   └── RegistrarRefundPage.jsx # Cleared queue, deduction calculator, payment ref
│   │   └── admin/
│   │       └── AdminDashboardPage.jsx # Master roster, CSV ingestion, staff provisioning
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

### B. Department Officer Interface (`/officer`)
- **Assigned Context**: Displays the authenticated officer's department (e.g. Library, Sports, Hostel) directly from `authApi.me()`.
- **Status Tabs**: Segregates records by `PENDING`, `APPROVED`, `REJECTED`, or `ALL`.
- **Decision Modal**:
  - Modal dialog with Approve vs Reject selection.
  - Strict validation: **remarks are strictly mandatory on rejection** (enforced with a 500-character counter).
  - Clear error handling for `409 Conflict` (already decided) and `404 Not Found` (unassigned department).
  - Strict no-optimistic-update pattern: cache invalidation via React Query `refetch()` upon confirmation.

### C. Chairperson / HoD Interface (`/hod` & `/hod/requests/:id`)
- **Department Scope**: Clarifies the academic department covered by the Chairperson (e.g. *Skill Department of CS/IT*).
- **Review Queue (`/hod`)**: Lists students in `HOD_REVIEW` status whose prior departmental clearances have all been approved.
- **Full Dossier View (`/hod/requests/:id`)**:
  - Student identity, course, and enrollment status (Hosteller vs Day Scholar).
  - Department Sign-off Matrix: Shows every applicable university department, category, status badge, remarks, previous rejection history, and decision dates.
  - Decision Panel: Approve (grants final clearance and issues digital certificate) or Reject (returns dossier to student with mandatory remarks).
  - Protected by `AlertDialog` confirmation modal.

### D. Registrar & Accounts Refund Interface (`/registrar`)
- **Queue**: Displays requests in `CLEARED` status awaiting security deposit reconciliation.
- **Live Deduction Calculator**: Form enforcing `0 <= deductions <= deposit_amount` with live net payout preview (`₹Deposit - ₹Deductions = ₹Net Payable`).
- **Chained Workflow Modal**: Immediately transitions from Step 1 (Verify Refund) to Step 2 (Record Payment Reference) upon verification, allowing seamless input of banking UTR/NEFT references.

---

## 6. Documented API Gaps & Specifications

1. **API Gap 1 (HoD Certificate Code Visibility)**:
   - *Issue*: When an HoD grants final approval via `POST /hod/requests/{id}/decision`, the backend creates the `Certificate` row with a UUID, but `HoDRequestDetailResponse` does not include `certificate_code` in its schema.
   - *Impact*: The HoD UI cannot display the certificate UUID code directly; only the student can retrieve it via `GET /student/requests/{id}/certificate.pdf` (which forbids non-student roles with HTTP 403).
   - *Recommendation*: Add `certificate_code: Optional[str] = None` to `HoDRequestDetailResponse`.

2. **API Gap 2 (Registrar Cleared Queue Omission)**:
   - *Issue*: `GET /registrar/queue` hardcodes `ClearanceRequest.status == ClearanceStatus.CLEARED` with no `status` filter query parameter. `POST /registrar/requests/{id}/verify-refund` immediately mutates the request status to `REFUND_VERIFIED`.
   - *Impact*: Once a request is verified, it disappears from `/registrar/queue`. If the registrar closes the modal or navigates away, the request cannot be retrieved to invoke `POST /registrar/requests/{id}/mark-processed`.
   - *Frontend Handling*: Implemented an immediate 2-step chained modal so the registrar can input the payment reference directly upon verification.
   - *Recommendation*: Add a `status` query parameter to `/registrar/queue` supporting `CLEARED` and `REFUND_VERIFIED` filters.

3. **API Gap 3 (Department Queue Search Parameter)**:
   - *Issue*: `GET /department/queue` only accepts `status`, `limit`, and `offset`. It does not support `search` or `query` parameters.
   - *Frontend Handling*: Provided client-side filtering on currently loaded page items with clear labeling.
   - *Recommendation*: Add `search: Optional[str] = Query(None)` to `/department/queue` to filter across student name and registration number.

4. **API Gap 4 (Department Officer Identity Excluded)**:
   - *Issue*: `DepartmentApprovalItem` exposes `decided_at`, `status`, and `remarks`, but omits `decided_by` or officer name.
   - *Frontend Handling*: Displayed "Department Officer" with a tooltip explaining that individual officer usernames are omitted by the backend contract.

5. **API Gap 5 (Missing GET /departments Endpoint)**:
   - *Issue*: The backend requires `department_id` when provisioning staff (`POST /admin/users`) and student lab assignments (`PUT /admin/roster/{id}/assigned-departments`), but exposes no `GET /departments` endpoint.
   - *Frontend Handling*: Hardcoded the 29 official SVSU departments (academic, service, and assignable labs/workshops) into `src/lib/departments.js` mirroring university seed data.
   - *Recommendation*: Expose `GET /departments` returning `list[DepartmentResponse]` with `id`, `name`, and `kind`.

6. **API Gap 6 (Missing GET /admin/users Directory Listing)**:
   - *Issue*: The backend provides `POST /admin/users`, `POST /admin/users/{id}/reset-password`, and `PATCH /admin/users/{id}/active`, but provides no endpoint to list or search existing user accounts.
   - *Frontend Handling*: The admin dashboard provides a session-provisioned staff directory and a direct User ID administration tool for resetting passwords and toggling active status.
   - *Recommendation*: Add `GET /admin/users` with pagination, role filtering, and email/name search.

---

## 7. Phase 3 Deliverables & System Administration Architecture

### A. Master Student Roster & CSV Ingestion (`/admin`)
- **Master Student Directory**: Paginated, server-filtered `DataTable` (`GET /admin/roster`) displaying registration numbers, names, emails, mobile, programmes, hosteller status, and security deposits.
- **Roster Profile Editor**: Dialog allowing administrators to update hosteller residency, security deposit amounts, addresses, and mobile numbers (`PATCH /admin/roster/{id}`).
- **Assigned Laboratories & Workshops**: Multi-select modal allowing assignment of specialized service departments (IDs 17–29: Lab-1 to Lab-9, Workshop-1 to Workshop-3, Others) via `PUT /admin/roster/{id}/assigned-departments`.
- **CSV Batch Ingestion**:
  - Drag-and-drop file ingestion zone with sample CSV template download.
  - Validates and parses 8 required column headers: `registration_number, name, email, mobile, address, programme, is_hosteller, security_deposit_amount`.
  - Ingests via `POST /admin/roster/upload` and renders a row-by-row execution report with status badges (`CREATED`, `UPDATED`, `REJECTED`) and detailed diagnostic messages.

### B. Staff Provisioning & Credential Security
- **Staff Provisioning Form**: Enables administrators to create accounts for `dept_officer`, `hod`, and `registrar_accounts`. Dynamically restricts department selection (HoDs are restricted strictly to academic departments).
- **One-Time Temporary Password Architecture**:
  - Temporary passwords returned by `POST /admin/users` and `POST /admin/users/{id}/reset-password` are displayed in a high-security modal with clipboard copy support.
  - The modal explicitly warns the administrator that credentials are displayed once and cannot be retrieved again.
  - Cleared from component memory immediately upon modal dismissal; never stored in localStorage, sessionStorage, or logs.
- **Direct User ID Administration**:
  - Allows instant temporary password resets for any user ID (`POST /admin/users/{id}/reset-password`).
  - Allows account activation or deactivation (`PATCH /admin/users/{id}/active`).
  - Enforces client-side and server-side self-deactivation protection preventing administrators from locking out their own accounts.

### C. Public Verification Portal (`/verify`, `/verify/:code`)
- Accessible publicly without authentication.
- Automatically captures the `:code` URL parameter from QR codes embedded in downloaded clearance certificates.
- Calls `GET /verify/{certificate_code}` and renders high-visibility validation results using text and icons (not color alone) to verify student identity, registration number, programme, department, and issue timestamp.

### D. System Polish & Resilience
- **Global Error Boundary (`ErrorBoundary.jsx`)**: Wraps application routes to catch unhandled JavaScript rendering exceptions and presents a clean recovery screen with "Reload Page" and "Return to Home".
- **Logout Confirmation Dialog**: `AlertDialog` in `AppShell` intercepts sign-out actions to prevent accidental session termination.
- **Dynamic Document Titles**: `useDocumentTitle` hook dynamically sets descriptive window titles (e.g. `Institutional Admin | SVSU No-Dues`).
- **Performance & Code-Splitting**: Lenis momentum scrolling and GSAP animation engines are dynamically imported (`import()`) exclusively on the public Landing route, maintaining small, fast bundles for all authenticated dashboard views.


