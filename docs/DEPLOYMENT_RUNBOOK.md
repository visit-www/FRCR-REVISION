# RadInsights Deployment Runbook

Operational reference for deploying, monitoring, and maintaining the RadInsights Flask application on Vercel with Neon PostgreSQL.

---

## Table of Contents

1. [Environment Variables](#1-environment-variables)
2. [Deployment (Vercel)](#2-deployment-vercel)
3. [Database (Neon PostgreSQL)](#3-database-neon-postgresql)
4. [Monitoring](#4-monitoring)
5. [Cron Jobs](#5-cron-jobs)
6. [Backup and Restore](#6-backup-and-restore)
7. [Disaster Recovery](#7-disaster-recovery)
8. [Rollback Procedure](#8-rollback-procedure)
9. [Common Issues](#9-common-issues)

---

## 1. Environment Variables

All variables are set in Vercel Project Settings > Environment Variables. Local development uses `.env` and `.env.local` files (loaded via `python-dotenv`).

### Required (Production will fail without these)

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Flask session signing key. App raises `RuntimeError` on Vercel if missing. Use a random 64-char hex string (`python -c "import secrets; print(secrets.token_hex(32))"`) |
| `DATABASE_URL` or `DATABASE_POSTGRES_URL_NON_POOLING` | Neon PostgreSQL connection string. Multiple fallback env names are checked (see below). Must be a `postgresql://` URL |
| `CLAUDE_API_KEY` | Anthropic API key for all AI features (case generation, Smart Reporter, TNM calculators, protocol generation) |
| `CRON_SECRET` | Vercel Cron authentication secret. Set in Vercel dashboard; Vercel injects it as the `Authorization` header for cron requests |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary cloud name for image uploads (cases, forum, profile pictures) |
| `CLOUDINARY_API_KEY` | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Cloudinary API secret |

### Database URL Resolution Order

The app checks these environment variables in order (non-pooled preferred by default):

```
DATABASE_POSTGRES_URL_NON_POOLING
POSTGRES_URL_NON_POOLING
DATABASE_URL
POSTGRES_URL
DATABASE_POSTGRES_URL
frcr_revision_db_DATABASE_URL
frcr_revision_db_POSTGRES_URL_NON_POOLING
```

Set `USE_POOLED_DB=1` to reverse priority (pooled URL first). Set `USE_LOCAL_DB=1` to force local SQLite.

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_MODEL` | `claude-sonnet-4-20250514` | Override the default Claude model for AI generators |
| `CLAUDE_QUICK_MODEL` | `claude-haiku-4-5-20251001` | Override the fast/cheap model used for Smart Reporter ask/review |
| `RESEND_API_KEY` | (none) | Resend email service key. Required for account recovery emails and admin notifications |
| `EMAIL_FROM` | `RadInsights <contact@radinsights.xyz>` | From address for transactional emails |
| `SUPERADMIN_EMAIL` | (none) | Email for admin notification routing (new user reviews, case submissions). Used in `auth.py` |
| `APP_URL` | (none) | Canonical app URL (e.g. `https://www.radinsights.xyz`). Falls back to `VERCEL_URL` |
| `CORS_ORIGINS` | Auto-detected | Comma-separated allowed origins. Defaults to `radinsights.xyz` in production, `*` in dev |
| `CLOUDINARY_UPLOAD_PRESET` | (none) | Unsigned upload preset for client-side uploads |
| `MAX_UPLOAD_MB` | `1024` | Maximum upload size in MB |
| `NOTION_CLIENT_ID` | (none) | Notion OAuth app client ID (for Notion integration) |
| `NOTION_CLIENT_SECRET` | (none) | Notion OAuth app secret |
| `NOTION_REDIRECT_URI` | `http://localhost:5000/notion/callback` | Notion OAuth callback URL |
| `R2_ACCOUNT_ID` | (none) | Cloudflare R2 account ID (for DICOM image stacks) |
| `R2_ACCESS_KEY_ID` | (none) | R2 API token access key |
| `R2_SECRET_ACCESS_KEY` | (none) | R2 API token secret key |
| `R2_BUCKET_NAME` | (none) | R2 bucket name |
| `R2_JURISDICTION` | (default/US) | Set to `eu` for EU jurisdiction R2 endpoint |
| `R2_UPLOAD_WORKERS` | `20` | Thread pool size for parallel R2 uploads |
| `AZURE_CLIENT_ID` | (none) | Azure app registration ID (OneDrive DICOM viewer integration) |
| `AZURE_CLIENT_SECRET` | (none) | Azure app registration secret |
| `FLASK_DEBUG` | (none) | Set to enable debug logging level |
| `FLASK_ENV` | (none) | Set to `production` to load `.env.production` |
| `NEON_URL` | (none) | Direct Neon URL used by batch scripts (falls back to `DATABASE_URL`) |

### Vercel-Injected Variables (do not set manually)

| Variable | Description |
|----------|-------------|
| `VERCEL` | Set to `1` when running on Vercel. Triggers NullPool for serverless |
| `VERCEL_ENV` | `production`, `preview`, or `development` |
| `VERCEL_URL` | Auto-assigned deployment URL |

---

## 2. Deployment (Vercel)

### Architecture

```
vercel.json
  builds:
    api/index.py  -> @vercel/python (maxDuration: 300s, maxLambdaSize: 50mb)
    static/**     -> @vercel/static  (CDN, Cache-Control: 86400s)
  rewrites:
    /static/*  -> static files
    /*         -> api/index.py (Flask WSGI app)
```

The entry point is `api/index.py`, which imports the Flask `app` from `app.py`.

### How to Deploy

1. **Push to main branch** -- Vercel auto-deploys from the connected Git repository.

2. **Manual deploy** (from local):
   ```bash
   vercel --prod
   ```

3. **Preview deploy** (for testing before production):
   ```bash
   vercel
   ```
   Or push to a non-main branch; Vercel creates a preview URL.

### Post-Deploy Verification Checklist

1. **Health check**: `curl https://radinsights.co.uk/health`
   - Expected: `{"status": "ok", "app": "RadInsights", "database": "ok"}`
   - If `database: "error"` -- check Neon connection string.

2. **Login**: Navigate to the app and verify login works (session cookies require correct `SECRET_KEY`).

3. **Static assets**: Open browser DevTools Network tab; confirm CSS/JS load from CDN with cache headers.

4. **Cron jobs**: Check Vercel dashboard > Cron Jobs tab to confirm schedules are active.

5. **AI features**: Try generating content in Smart Reporter or On-Call Helper (requires `CLAUDE_API_KEY`).

### Security Headers (set in vercel.json)

All responses include: `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `X-XSS-Protection: 1; mode=block`, `Strict-Transport-Security: max-age=31536000`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`.

Dynamic routes also set `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`.

---

## 3. Database (Neon PostgreSQL)

### Connection Setup

- Production uses Neon PostgreSQL with SSL required (`sslmode=require` appended automatically).
- Serverless mode: `NullPool` (no connection pooling) when `VERCEL` env is set.
- Local dev: SQLite at `instance/RadInsights_db.db` when `USE_LOCAL_DB=1`.

### Auto-Migration Block

On every app startup (inside `with app.app_context()`), the following runs:

1. **`db.create_all()`** -- Creates any NEW tables. Does NOT add columns to existing tables.

2. **`_add_col_if_missing(table, column, col_sql)`** -- Inspects each table and runs `ALTER TABLE ADD COLUMN` for any missing columns. This is idempotent and runs on every cold start.

3. **`_widen_col_to_text(table, column)`** -- Widens `VARCHAR(500)` columns to `TEXT` on both `radiology_template` and `reporting_algorithm` tables.

4. **`_migrate_reporting_templates_if_needed()`** -- One-time migration from legacy `reporting_template` table to the new `radiology_template` + `reporting_algorithm` split.

5. **`_seed_ajcc_data_if_needed()`** -- Seeds AJCC body sections and disease sites if tables are empty.

6. **`_ensure_superadmin_exists()`** -- Creates superadmin account if it does not exist (password shown once in logs).

### Adding a New Column to an Existing Table

**Every time** you add a column to an existing model in `models.py`, you MUST also:

1. Add the column definition in `models.py`.
2. Add a corresponding `_add_col_if_missing()` call in the `app.py` initialization block.

Example:
```python
# In models.py
class MyModel(db.Model):
    new_field = db.Column(db.Text, nullable=True)

# In app.py (inside the with app.app_context() block)
_add_col_if_missing('my_model', 'new_field', 'new_field TEXT')
```

For boolean columns, use: `'new_flag BOOLEAN DEFAULT false NOT NULL'`

### Manual Migration via Admin Endpoint

```bash
curl -X POST https://radinsights.co.uk/api/admin/migrate-db
```

This calls `db.create_all()` which creates any new tables (but does not add columns to existing ones).

### Direct Neon Access

For batch operations or manual queries:

```bash
# Using psql
psql "postgresql://neondb_owner:<password>@<host>/neondb?sslmode=require"

# Batch scripts use NEON_URL env var
PYTHONUNBUFFERED=1 python scripts/batch_templates.py batch --phase 1
```

---

## 4. Monitoring

### Health Check Endpoint

```
GET /health
```

Response:
```json
{"status": "ok", "app": "RadInsights", "database": "ok"}
```

Returns HTTP 200 when healthy, HTTP 503 when degraded (database unreachable). Set up an external uptime monitor (e.g., UptimeRobot, Betterstack) to poll this endpoint every 1-5 minutes.

### Structured Logging

In production (`VERCEL_ENV=production`), all logs are emitted as JSON:

```json
{"ts": "2026-03-14 10:00:00", "level": "INFO", "logger": "app", "msg": "..."}
```

View logs in the Vercel dashboard under Deployments > Functions > Logs, or via:

```bash
vercel logs --follow
```

### Slow Query Detection

Queries taking longer than 1 second are logged at WARNING level by the `slow_query` logger:

```
WARNING: Slow query (2.34s): SELECT * FROM case WHERE ...
```

Monitor for these in Vercel logs. Consider adding database indexes if patterns emerge.

### PII Guard

The PII middleware (`pii_guard.py`) blocks patient-identifiable data in POST/PUT JSON requests. Returns HTTP 422 with `pii_blocked: true` if PII is detected. Client-side guard in `static/pii-guard.js` intercepts fetch calls.

### Rate Limiting

- Default: 200 requests/minute per IP (Flask-Limiter, in-memory storage).
- AI endpoints: 50 requests/day per user (tracked via `ai_usage_date` + `ai_usage_count` on User model).
- Login: Brute-force protection via `failed_login_count` / `locked_until` on User model.

---

## 5. Cron Jobs

### Configured Crons (in vercel.json)

| Endpoint | Schedule | Purpose |
|----------|----------|---------|
| `/api/cron/process-tnm-jobs` | `0 0 * * *` (daily at midnight UTC) | Process pending TNM calculator generation jobs |

### Available but Not Scheduled

| Endpoint | Purpose |
|----------|---------|
| `/api/cron/data-retention-cleanup` | GDPR cleanup: deletes expired recovery codes (7d), approval codes (30d), stale TNM jobs (90d) |

To add this to the schedule, update `vercel.json`:

```json
{
  "crons": [
    {
      "path": "/api/cron/process-tnm-jobs",
      "schedule": "0 0 * * *"
    },
    {
      "path": "/api/cron/data-retention-cleanup",
      "schedule": "0 3 * * 0"
    }
  ]
}
```

### Cron Authentication

All cron endpoints require `CRON_SECRET`:

- Vercel automatically sends `Authorization: Bearer <CRON_SECRET>` for configured cron jobs.
- The endpoints check `request.headers.get('Authorization', '').endswith(cron_secret)`.
- In debug mode (`app.debug=True`), authentication is skipped.
- If `CRON_SECRET` is not set in production, all cron requests return 401.

### Manual Trigger

```bash
# Trigger locally (debug mode skips auth)
curl http://localhost:5000/api/cron/process-tnm-jobs

# Trigger on production (requires CRON_SECRET)
curl -H "Authorization: Bearer YOUR_CRON_SECRET" \
  https://radinsights.co.uk/api/cron/data-retention-cleanup
```

---

## 6. Backup and Restore

All backup routes are under `/api/backup/` and require admin authentication (role = ADMIN; Content Managers do not have access).

### Export

**Plain JSON backup:**

```
GET /api/backup/download
```

Downloads a JSON file containing all database tables. Filename format: `radinsights_backup_YYYYMMDD_HHMMSS.json`.

**Encrypted backup (AES-256 Fernet):**

```
GET /api/backup/download?encrypted=true
```

- Encryption key is derived from `SECRET_KEY` via SHA-256.
- Returns a ZIP file containing `backup.enc` + `README.txt`.
- Important: If you rotate `SECRET_KEY`, you lose the ability to decrypt old encrypted backups.

**Backup status:**

```
GET /api/backup/status
```

Returns backup status and last backup time.

### Import / Restore

```
POST /api/backup/restore
Content-Type: multipart/form-data
Body: backup_file=<file.json or file.json.gz>
```

- Accepts `.json` or `.json.gz` files.
- Gzip compression supported for large backups (>4MB) to stay under Vercel's 4.5MB body limit.
- Smart merge: maps user IDs, handles both new and legacy table formats.
- Backward compatible: imports old `reporting_templates` key and maps to the new `radiology_templates` + `reporting_algorithms` split.

### Backup Contents

The export includes: users (with hashed passwords, excluding tokens), cases, images, questions, answers, forum data, AJCC TNM staging data, revision sessions/history, spaced repetition progress, clinical protocols, radiology templates, reporting algorithms, incidental finding calculators, TNM calculator content, case DICOM stacks, audit logs, and all association tables.

### Recommended Backup Schedule

1. Download a backup before any major deployment or database migration.
2. Weekly automated backup via admin UI or scripted `curl`.
3. Store encrypted backups in a separate location from the production database.

---

## 7. Disaster Recovery

### Database Unreachable (Neon)

1. Check Neon dashboard (https://console.neon.tech) for service status.
2. Verify the connection string in Vercel environment variables has not changed.
3. Check `/health` endpoint -- if `database: "error"`, the issue is confirmed.
4. If Neon is down: wait for recovery. The app will return 503 on health checks but static pages may still load.
5. If connection string changed (e.g., branch rename): update `DATABASE_URL` in Vercel env vars and redeploy.

### Broken Deployment

1. Roll back immediately via Vercel dashboard or CLI (see [Rollback Procedure](#8-rollback-procedure)).
2. Check Vercel deployment logs for build or runtime errors.
3. Common causes: missing environment variable, syntax error in Python, dependency version conflict.

### User Lockout (Forgot Password / Account Locked)

1. If `RESEND_API_KEY` is configured: user can use the "Forgot Password" flow.
2. If email is not working: admin can reset via direct database access:
   ```sql
   -- Unlock a locked account
   UPDATE "user" SET locked_until = NULL, failed_login_count = 0
   WHERE email = 'user@example.com';
   ```
3. Superadmin account: auto-created on startup with a random password logged to console. If lost, delete the user row and redeploy (a new password will be generated and logged).

### Admin Account Recovery

The superadmin account is auto-created by `_ensure_superadmin_exists()` on every cold start. If the password is lost:

```sql
-- Option 1: Delete and let auto-creation regenerate with new password
DELETE FROM "user" WHERE email = 'lotusheart2016@gmail.com';
-- Then redeploy or restart. Check logs for the new password.

-- Option 2: Manually set a new password hash
-- Generate with: python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('NewPassword123!'))"
UPDATE "user" SET password_hash = '<generated_hash>'
WHERE email = 'lotusheart2016@gmail.com';
```

### Full Data Restore

1. Obtain the most recent backup file (JSON or encrypted ZIP).
2. If encrypted: you need the `SECRET_KEY` that was active when the backup was created.
3. Log in as admin, navigate to the backup admin page.
4. Upload the backup file via the restore endpoint.
5. Verify data integrity: spot-check cases, user accounts, templates, and algorithms.

### Neon Database Branch Reset

If the database is corrupted beyond repair:

1. Create a new Neon branch from a known-good point-in-time (Neon supports branching with time travel).
2. Update the connection string in Vercel environment variables.
3. Redeploy. The auto-migration block will run `db.create_all()` and column migrations.
4. If no branch is available, restore from the latest backup file.

---

## 8. Rollback Procedure

### Via Vercel Dashboard

1. Go to Vercel Project > Deployments.
2. Find the last known-good deployment.
3. Click the three-dot menu > "Promote to Production".

### Via Vercel CLI

```bash
# List recent deployments
vercel ls

# Roll back to the previous production deployment
vercel rollback

# Roll back to a specific deployment URL
vercel rollback <deployment-url>
```

### Important Notes

- Rollback only affects the application code. Database schema changes (columns added by `_add_col_if_missing`) are NOT rolled back.
- If a rollback is needed because of a bad database migration, you may need to manually `ALTER TABLE DROP COLUMN` in Neon.
- Environment variable changes are independent of deployments. If you changed an env var and need to revert, do so in Vercel Project Settings before rolling back.

---

## 9. Common Issues

### `maxDuration` Must Be in `builds[].config`, Not `functions`

**Wrong** (causes deployment failures):
```json
{
  "builds": [...],
  "functions": { "api/index.py": { "maxDuration": 300 } }
}
```

**Correct:**
```json
{
  "builds": [{
    "src": "api/index.py",
    "use": "@vercel/python",
    "config": { "maxDuration": 300 }
  }]
}
```

Never mix `functions` and `builds` in `vercel.json`.

### Anthropic API System Prompt Must Be a Plain String

**Wrong** (causes 500 errors):
```python
"system": [{"type": "text", "text": "..."}]
```

**Correct:**
```python
"system": "Your system prompt here"
```

All AI generators use `requests.post` directly to the Anthropic Messages API (not the SDK).

### `db.create_all()` Does Not Add Columns to Existing Tables

This is a SQLAlchemy limitation. `db.create_all()` only creates NEW tables. To add a column to an existing table, you must use the `_add_col_if_missing()` helper in `app.py`. See [Adding a New Column](#adding-a-new-column-to-an-existing-table).

### `dict.get()` Evaluates Defaults Eagerly

```python
# WRONG: raises NameError if undefined_var is not defined
result.get('key', undefined_var)

# CORRECT: use a literal fallback
result.get('key', '')
```

### Session Cookies Not Working After Deploy

- Verify `SECRET_KEY` has not changed between deployments. A different key invalidates all existing sessions.
- `SESSION_COOKIE_SECURE` is automatically `True` in production. If testing over HTTP, cookies will not be sent.

### Large Backup Restore Fails (Vercel 4.5MB Body Limit)

The restore endpoint supports gzip-compressed uploads. The admin UI compresses files >4MB automatically. For manual `curl` uploads:

```bash
gzip backup.json
curl -X POST -F "backup_file=@backup.json.gz" -F "compressed=true" \
  https://radinsights.co.uk/api/backup/restore
```

### Batch Script Output Not Appearing

Python buffers stdout when writing to non-TTY (e.g., piped to a file). Always prefix batch scripts with:

```bash
PYTHONUNBUFFERED=1 python scripts/batch_templates.py batch --phase 1
```

### Neon "Postgres Message Too Large" Error

When connecting locally to Neon's direct (non-pooled) URL with large queries, set `USE_POOLED_DB=1` in `.env.local` to prefer the pooled connection URL.

### Cold Start Timeouts

Vercel serverless functions have a cold start. The `maxDuration: 300` (5 minutes) is set, but the default for non-Pro plans is lower. AI generation endpoints may need the full 300s. Ensure the Vercel plan supports the configured `maxDuration`.

### Static Files Not Updating After Deploy

Static files are served with `Cache-Control: public, max-age=86400, s-maxage=604800` (1 day browser cache, 7 day CDN cache). After deploying updated static files:

- CDN cache clears automatically on new Vercel deployments.
- Browser cache: users may need to hard-refresh or wait up to 24 hours.
- For critical CSS/JS changes, consider cache-busting by appending a version query parameter.
