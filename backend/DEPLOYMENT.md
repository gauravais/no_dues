# SVSU No-Dues Clearance System — Production Deployment & Operator Runbook

This guide covers production deployment prerequisites, environment variables, database setup, background workers, and operational security procedures for the No-Dues Clearance backend.

---

## 1. Production Environment Configuration

Create `/etc/nodues/production.env` (or a secure `.env` file with restrictive permissions, `chmod 600`):

```ini
# Application Mode
APP_ENV=production
DEBUG=false
ENABLE_DOCS=false

# Security & Tokens
SECRET_KEY=generate-a-strong-random-secret-key-at-least-32-chars
ACCESS_TOKEN_EXPIRE_MINUTES=120
ALLOWED_EMAIL_DOMAINS=svsu.ac.in

# Symmetric Encryption for Bank Account Numbers (Fernet 32-byte urlsafe base64)
# Generate with: uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=replace-with-securely-generated-fernet-key

# Google OAuth2 Authentication & Login Gate Flags
GOOGLE_CLIENT_ID=replace-with-google-client-id.apps.googleusercontent.com
GOOGLE_ALLOWED_DOMAINS=svsu.ac.in
AUTH_OTP_SIGNUP_ENABLED=false
AUTH_PASSWORD_LOGIN_FOR_STUDENTS=false

# Database Connection
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_USER=nodues_user
POSTGRES_PASSWORD=replace-with-secure-postgres-password
POSTGRES_DB=nodues_db

# CORS & Frontend URL (Must be HTTPS and contain NO localhost in production)
FRONTEND_BASE_URL=https://nodues.svsu.ac.in
CORS_ORIGINS=https://nodues.svsu.ac.in

# Real Email (SMTP Settings)
MAIL_CONSOLE_ONLY=false
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=nodues-noreply@svsu.ac.in
SMTP_PASSWORD=replace-with-smtp-app-password
SMTP_FROM=nodues-noreply@svsu.ac.in
SMTP_USE_TLS=true

# Pilot Email Restriction (Optional: leave empty to send to all university addresses)
# When set, real emails are sent ONLY to these addresses; others are marked SKIPPED in email_outbox.
EMAIL_ALLOWLIST=admin@svsu.ac.in,pilot.tester@svsu.ac.in

# Daily Automated Reminders
REMINDERS_ENABLED=true
REMINDER_AFTER_DAYS=3

# Development Overrides (Must be false in production)
DEV_RETURN_OTP=false
```

---

## 2. Production Startup Guards

When `APP_ENV=production`, the application strictly enforces:
- `ENABLE_DOCS=false` (Swagger and ReDoc are disabled to prevent API schema leakage).
- `CORS_ORIGINS` and `FRONTEND_BASE_URL` cannot contain `localhost` or `127.0.0.1`.
- `FRONTEND_BASE_URL` must start with `https://`.
- `MAIL_CONSOLE_ONLY=false`, with valid `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `SMTP_FROM`.
- In production, one-time passwords (OTPs) and user passwords are **never** printed to the console or logged.

If any check fails, FastAPI startup is halted with an informative error.

---

## 3. Database Migration & Initialization

Execute database migrations:

```bash
cd backend
uv run alembic upgrade head
```

Verify migration status:
```bash
uv run alembic current
```

---

## 4. Bootstrapping the First Administrator

Run the dedicated administrative bootstrap script:

```bash
# Option A: Interactive prompt (prompts for email, password via getpass, and name)
uv run python -m scripts.create_first_admin

# Option B: Headless with environment variables
FIRST_ADMIN_EMAIL=admin@svsu.ac.in FIRST_ADMIN_PASSWORD=InitialAdmin@Secure2026 uv run python -m scripts.create_first_admin
```

> **Rules enforced**:
> - Email domain must match `ALLOWED_EMAIL_DOMAINS` (`@svsu.ac.in`).
> - Password must be at least 10 characters.
> - Account is created with `must_change_password=False`.
> - Passwords are never echoed or written to log files.

---

## 5. Background Services & Cron Jobs

### A. Email Outbox Worker
The application uses the transactional **Outbox Pattern**: all notification emails and OTPs are inserted into `email_outbox` within the database transaction that triggers them.

Run the outbox processor as a managed daemon (e.g. systemd or supervisord):

```bash
uv run python -m scripts.send_emails --loop --interval 10
```

Systemd unit example (`/etc/systemd/system/nodues-email-worker.service`):
```ini
[Unit]
Description=NoDues Email Outbox Worker
After=network.target postgresql.service

[Service]
Type=simple
User=nodues
WorkingDirectory=/opt/nodues/backend
EnvironmentFile=/etc/nodues/production.env
ExecStart=/opt/nodues/backend/.venv/bin/python -m scripts.send_emails --loop --interval 10
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### B. Daily Digest & Reminder Cron
To notify department officers and students with stagnant requests (> `REMINDER_AFTER_DAYS`), configure a daily cron job:

```bash
# Crontab entry: run every morning at 08:30 IST (03:00 UTC)
0 3 * * * cd /opt/nodues/backend && /opt/nodues/backend/.venv/bin/python -m scripts.send_reminders >> /var/log/nodues-reminders.log 2>&1
```

---

## 6. Security Features Overview

| Security Feature | Specification |
|---|---|
| **Failed Login Rate Limit** | Max 5 failed attempts per 15 minutes per email and IP address. Persisted in PostgreSQL table `auth_rate_limits`. Returns HTTP 429 with `Retry-After`. |
| **Signup OTP Rate Limit** | Max 3 requests / email / hour; max 3 requests / registration number / hour; max 5 requests / IP / hour. Returns generic success response whether student exists or not to prevent user enumeration. |
| **Forced Password Change** | Admin-created staff accounts and reset accounts have `must_change_password=True`. Users are locked out from all endpoints except `/auth/me` and `POST /auth/change-password` (HTTP 403 `PASSWORD_CHANGE_REQUIRED`). |
| **Student Password Length** | Enforced minimum 10 characters on registration and password change. |
| **Bank Account Reveal** | Masked everywhere (`********1234`). Only Registrar Accounts role can access plain bank details via `POST /registrar/requests/{id}/reveal-bank-details`, strictly rate limited (10 calls/min) and audit-logged without storing decrypted numbers in logs. |
| **Clearance Cancellation** | Student can cancel their own clearance request only while all department approvals remain `PENDING`. Academic officers and admins can cancel active requests with a mandatory reason, audit trail, and email notification to student. |

---

## 7. Google Cloud Setup (OAuth 2.0 Single Sign-On)

University students, staff, and administrators authenticate securely via Google OAuth2 ID tokens issued by Google Identity Services (GIS).

### A. Create a Google Cloud Project
1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Click the project dropdown at the top and select **New Project**.
3. Name the project (e.g. `SVSU No-Dues Clearance`) and select your university organization (`svsu.ac.in`).

### B. Configure OAuth Consent Screen
1. Navigate to **APIs & Services** > **OAuth consent screen**.
2. **User Type**:
   - **Internal** (*Recommended for university pilot & production*): Available strictly to Google Workspace accounts within `svsu.ac.in`. No app verification is required, and any active university student or staff account can immediately log in without test-user restrictions.
   - **External**: Required only if testing with outside personal `@gmail.com` accounts. In "Testing" mode, it is capped at a strict maximum of 100 manually added test users. Moving to production requires domain verification and Google app review.
3. Fill in required application details:
   - App name: `SVSU No-Dues System`
   - User support email: `it.support@svsu.ac.in`
   - Developer contact email: `admin@svsu.ac.in`
4. **Scopes**: Add standard non-sensitive scopes: `openid`, `.../auth/userinfo.email`, and `.../auth/userinfo.profile`.

### C. Create Web OAuth Client ID
1. Navigate to **APIs & Services** > **Credentials**.
2. Click **Create Credentials** > **OAuth client ID**.
3. Select Application type: **Web application**.
4. Name: `No-Dues Web Client`.
5. **Authorized JavaScript origins**:
   - Production URL: `https://nodues.svsu.ac.in`
   - Local development: `http://localhost` and `http://localhost:5173`
   - > [!IMPORTANT]
     > Google OAuth **strictly requires HTTPS** for all production origins (only `localhost` can be HTTP). **Raw IP addresses (e.g. `http://192.168.1.5` or `http://10.0.0.1`) and wildcard subdomains are prohibited** by Google.
6. Click **Create**. Copy the generated **Client ID** (e.g. `474883945999-...apps.googleusercontent.com`).

### D. Client Secret Not Needed
For modern frontend Single Sign-On via Google Identity Services (`google.accounts.id`), **no Client Secret is needed or stored**. The Client ID is a public identifier. The frontend sends the cryptographically signed JWT ID token to the backend, which verifies the signature against Google's public JWK certificates.

### E. Configuration & Deployment
1. Set the Client ID in `backend/.env`:
   ```ini
   GOOGLE_CLIENT_ID=474883945999-7ffjj1nlpnomlu3ad2adj9jh99jmf085.apps.googleusercontent.com
   GOOGLE_ALLOWED_DOMAINS=svsu.ac.in
   AUTH_OTP_SIGNUP_ENABLED=false
   AUTH_PASSWORD_LOGIN_FOR_STUDENTS=false
   ```
2. The frontend dynamically fetches the configuration via `GET /auth/config`.

### F. Propagation Timing
- When creating a new OAuth client or modifying **Authorized JavaScript origins**, Google's global edge caches typically take **5 minutes up to a few hours** to propagate changes worldwide. If login displays an `origin_mismatch` error immediately after creation, wait a few minutes before retesting.
