# Deployment Guide: Render & Neon (No-Dues Clearance System)

This guide details how to deploy the **No-Dues Clearance System** on **Render** (backend Docker web service + frontend static site) with a **Neon Serverless PostgreSQL** database.

---

## 1. Architecture Overview

- **Backend**: Render Free Docker Web Service (Singapore / Oregon / Frankfurt region). Spins down after 15 minutes of inactivity.
- **Frontend**: Render Static Site with global CDN, custom rewrite rules, and security headers (CSP, HSTS, X-Frame-Options).
- **Database**: Neon Serverless PostgreSQL with SSL (`sslmode=require`), connection retry with backoff for compute wake-up, and conservative pool limits (`pool_size=3`, `max_overflow=2`).
- **Transactional Email**: Brevo (Sendinblue) HTTPS API (bypasses outbound SMTP port blocks on Render).
- **Background Cron / Outbox Delivery**: GitHub Actions scheduled workflow (`.github/workflows/jobs.yml`) triggering authenticated internal endpoints (`/internal/jobs/send-emails` and `/internal/jobs/send-reminders`).

---

## 2. Secrets Generation

Generate high-entropy secrets on your local machine using Python:

```bash
# JWT Secret (minimum 32 characters)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Bank Encryption Key (minimum 32 characters)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Internal Job Secret (for GitHub Actions cron triggers)
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

> [!CAUTION]
> Never commit secrets or write production credentials into repository `.env` files. Provide them strictly through Render Dashboard Environment Variables or temporary session environment variables.

---

## 3. Database Setup (Neon PostgreSQL)

1. Sign up or log in at [Neon Console](https://console.neon.tech/).
2. Create a new project:
   - **Project Name**: `nodues-pilot`
   - **Postgres Version**: 16 (or 15+)
   - **Region**: Choose a region close to your Render deployment (e.g., `ap-southeast-1` Singapore or `us-east-2` Ohio).
3. In the Neon Dashboard, copy the connection string.
   - Choose **Pooled connection** or **Direct connection**. Neon provides a pooled URL (`-pooler` suffix in host) and a direct URL. Both work; the backend normalizes `postgres://` to `postgresql+psycopg://` and enforces `sslmode=require`.
   - Example connection string:
     ```text
     postgresql://nodues_user:secret_password@ep-cold-star-123456.ap-southeast-1.aws.neon.tech/nodues_db?sslmode=require
     ```

---

## 4. Deploying via Render Blueprint

1. Push your repository to GitHub or GitLab.
2. In the [Render Dashboard](https://dashboard.render.com/):
   - Click **New +** -> **Blueprint**.
   - Select your repository.
   - Render will detect `render.yaml` at the root and create two services:
     - `nodues-backend` (Docker Web Service)
     - `nodues-frontend` (Static Site)
3. Fill in the required secret environment variables for `nodues-backend` in the Render UI:
   - `DATABASE_URL`: Your Neon PostgreSQL connection string.
   - `JWT_SECRET`: The generated JWT secret.
   - `BANK_DATA_KEY`: The generated bank encryption key.
   - `JOB_SECRET`: The generated internal job secret.
   - `EMAIL_BACKEND`: Set to `brevo` (or `disabled` during initial staging).
   - `BREVO_API_KEY`: Your Brevo API key (starts with `xkeysib-...`).
   - `EMAIL_FROM`: Verified sender address in Brevo (e.g., `nodues@svsu.ac.in` or `notifications@yourdomain.com`).
   - `GOOGLE_CLIENT_ID`: Your Google OAuth 2.0 Web Client ID.
   - `CORS_ORIGINS`: Temporary URL or future frontend URL (e.g., `https://nodues-frontend.onrender.com`).
   - `FRONTEND_BASE_URL`: `https://nodues-frontend.onrender.com`.
4. Apply Blueprint and wait for the backend to build and start.

---

## 5. Google OAuth 2.0 Configuration

In the [Google Cloud Console](https://console.cloud.google.com/apis/credentials):
1. Open your OAuth 2.0 Client ID (Web Application type).
2. **Authorized JavaScript origins**:
   - `https://nodues-frontend.onrender.com`
   - (Optional custom domain if mapped)
3. **Authorized redirect URIs**:
   - `https://nodues-frontend.onrender.com`
4. Save changes. Note: Google origin updates can take 5–10 minutes to propagate globally.

---

## 6. Frontend Build-Time Configuration

Render Static Sites bake environment variables into JavaScript assets during `npm run build`:
1. In Render Dashboard -> `nodues-frontend` -> **Environment**:
   - Set `VITE_API_BASE_URL` to `https://nodues-backend.onrender.com`.
2. Update the Content-Security-Policy header in `render.yaml` if using a custom domain:
   - Replace `REPLACE_WITH_BACKEND_ORIGIN` with `https://nodues-backend.onrender.com`.
3. Trigger a manual deploy of `nodues-frontend` to compile with the backend URL.

---

## 7. University Structure Seed (Production Safe)

Database tables are created automatically on container launch via `alembic upgrade head` in `docker-entrypoint.sh`.

To seed university faculties, departments, programmes, labs, and workshops into Neon without creating demo users:
Run the seed script from your laptop using a session-scoped environment variable:

```bash
# Windows PowerShell
$env:DATABASE_URL="postgresql://nodues_user:secret_password@ep-cold-star-123456.ap-southeast-1.aws.neon.tech/nodues_db?sslmode=require"
$env:APP_ENV="production"
uv run --project backend python -m scripts.seed_structure --yes
$env:DATABASE_URL=""
$env:APP_ENV=""

# Linux / macOS
DATABASE_URL="postgresql://nodues_user:secret_password@ep-cold-star-123456.ap-southeast-1.aws.neon.tech/nodues_db?sslmode=require" \
APP_ENV=production \
uv run --project backend python -m scripts.seed_structure --yes
```

> [!NOTE]
> `seed_structure.py` creates **zero users, zero students, and zero passwords**. It only inserts university departments, faculties, and programmes.

---

## 8. Creating the Initial System Administrator

To create your initial real administrator account:
1. Ensure the admin's email has the `@svsu.ac.in` domain.
2. Sign in via Google OAuth on the frontend. The system will create the initial account, or an admin can insert the first staff record with `role = 'admin'`.

---

## 9. Scheduled Background Jobs Setup (GitHub Actions)

Because Render free tier sleeps and has no persistent background daemon, automated outbox email delivery and overdue clearance reminders are dispatched via GitHub Actions:

1. In your GitHub repository: Go to **Settings** -> **Secrets and variables** -> **Actions**.
2. Add the following repository secrets:
   - `RENDER_BACKEND_URL`: `https://nodues-backend.onrender.com`
   - `JOB_SECRET`: The exact string configured in Render for `JOB_SECRET`.
3. In `.github/workflows/jobs.yml`, uncomment the cron schedules when ready:
   ```yaml
   schedule:
     - cron: "*/15 * * * *"  # Outbox email dispatch every 15 minutes
   ```
4. Test manually under GitHub Actions -> **Run workflow**.

---

## 10. Operational Considerations & Cold Starts

### Sleep & Suspension Behavior
- **Render Web Service**: Sleeps after 15 minutes of HTTP inactivity. The next incoming request takes 20–40 seconds to spin up the container.
- **Neon Serverless Postgres**: Compute suspends after 5 minutes of idle time. The application's `do_connect` hook includes retry logic with exponential backoff (retrying up to 3 times) to smoothly handle the 1–3 second Neon wake-up period.
- **Health Checks**: Render uses `GET /health/live` to check container liveliness. This endpoint returns `{"status":"ok"}` **without** querying the database, allowing Neon compute to sleep when no actual traffic is flowing. Do not point external uptime monitors at `GET /health` (which queries DB), as that would prevent Neon from ever suspending.

### Rate Limiting, Real IPs & Spoof Defense

#### 1. Choosing `TRUSTED_CLIENT_IP_HEADER`
- **Default (empty `""`)**: The application uses only the direct TCP socket connection address (`request.client.host`). All HTTP proxy headers (`X-Forwarded-For`, etc.) are ignored. This is the safest default for local development and direct container deployments.
- **On Render Production (`True-Client-IP`)**: Render web services run behind Cloudflare and Render ingress proxies. Cloudflare attaches `True-Client-IP` (and `CF-Connecting-IP`) representing the true external client IP. Downstream clients cannot spoof `True-Client-IP` because Cloudflare overwrites it at the edge. Therefore, in `render.yaml` and Render Dashboard, configure:
  ```env
  TRUSTED_CLIENT_IP_HEADER=True-Client-IP
  ```
- **AWS / Other Reverse Proxies**: If deployed behind an AWS ALB or Nginx proxy configured to strip incoming headers and append only verified IPs to `X-Forwarded-For`, configure `TRUSTED_CLIENT_IP_HEADER=X-Forwarded-For`.

#### 2. Live Spoof Test
To verify that attackers cannot bypass IP rate limits or spoof IPs by injecting arbitrary forwarded headers:

1. **Header Spoof Verification**:
   Send a request with a fake `X-Forwarded-For` header to the backend:
   ```bash
   curl -i -H "X-Forwarded-For: 198.51.100.99" https://nodues-backend.onrender.com/health/live
   ```
   Because `TRUSTED_CLIENT_IP_HEADER=True-Client-IP`, the backend reads strictly from `True-Client-IP` set by the edge proxy, completely disregarding `198.51.100.99`.

2. **Per-Identifier Lockout Independence Verification**:
   Even if an attacker uses botnets or proxy pools with diverse IP addresses, rate limiting operates on distinct keys:
   - `login_fail:email:{email}` (5 attempts per 15 min)
   - `otp_req:reg:{registration_number}` (3 attempts per hour)
   - `otp_req:email:{email}` (3 attempts per hour)
   - `otp_req:ip:{client_ip}` (5 attempts per hour)

   Attempts to brute-force a specific account or registration number are locked out independently of whether the IP rotates.

---

## 11. Backup & Disaster Recovery

### Manual Database Backup via `pg_dump`
Take periodic snapshots from your secure terminal:

```bash
# Export compressed binary dump
pg_dump "postgresql://nodues_user:secret_password@ep-cold-star-123456.ap-southeast-1.aws.neon.tech/nodues_db?sslmode=require" \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file="nodues_backup_$(date +%Y%m%d_%H%M%S).dump"
```

### Neon Point-in-Time Restore (PITR)
Neon automatically maintains continuous write-ahead logs (WAL). In the Neon Console, you can create a branch from any timestamp in the last 7 days to recover from accidental deletions or migration mistakes.

---

## 12. Rollback Procedure

If a deployed version causes errors:
1. In Render Dashboard -> `nodues-backend` -> **Deploys**.
2. Find the previous successful deployment and click **Rollback**.
3. If database schema was changed, run Alembic downgrade from your terminal targeting the database:
   ```bash
   DATABASE_URL="..." uv run --project backend alembic downgrade -1
   ```

---

## 13. Paid Upgrade Path

When moving from pilot to university-wide production:
1. **Render**: Upgrade `nodues-backend` from Free to **Starter** ($7/mo) or **Standard** ($25/mo). This prevents compute sleeping and eliminates cold-start latency.
2. **Neon**: Upgrade to Neon **Launch** ($19/mo) for higher compute allowances, 300 compute-hours, and 30-day point-in-time recovery.
3. **Brevo**: Upgrade if email volume exceeds 300 free emails/day.

---

## 14. Alternative AWS Migration Checklist

For on-premise or institutional AWS infrastructure:
- [ ] **Compute**: AWS ECS Fargate running the same Docker container (`backend/Dockerfile`).
- [ ] **Database**: Amazon Aurora Serverless v2 PostgreSQL or standard RDS PostgreSQL with Multi-AZ.
- [ ] **Static Assets**: Amazon CloudFront CDN + S3 bucket for the React frontend.
- [ ] **Secrets**: AWS Secrets Manager or Parameter Store (KMS encrypted).
- [ ] **Cron Jobs**: AWS EventBridge Scheduler invoking ECS tasks or API endpoints with signature.
- [ ] **Outbound Email**: Amazon SES with verified `@svsu.ac.in` domain identity.

---

## 15. Go-Live Checklist

- [ ] `APP_ENV=production` configured on backend.
- [ ] `ENABLE_DOCS=false` confirmed (OpenAPI docs disabled in production).
- [ ] `MAIL_CONSOLE_ONLY=false` confirmed.
- [ ] `DATABASE_URL` contains `sslmode=require`.
- [ ] `JWT_SECRET`, `BANK_DATA_KEY`, and `JOB_SECRET` are all unique and $\ge 32$ random characters.
- [ ] `CORS_ORIGINS` points strictly to the production frontend domain (no `localhost`).
- [ ] Google OAuth authorized JavaScript origins match the production URL.
- [ ] `seed_structure` executed once to populate departments and programmes.
- [ ] GitHub Actions job scheduled with verified secrets.
- [ ] End-to-end Google sign-in tested on frontend with an authorized `@svsu.ac.in` account.
