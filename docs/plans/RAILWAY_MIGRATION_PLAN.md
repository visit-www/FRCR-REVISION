# Railway Migration Plan

**Status:** Planning
**Current Host:** Vercel (Hobby Plan)
**Target Host:** Railway
**Domain:** www.radinsights.xyz (Namecheap)

---

## Why Migrate?

| Issue | Vercel Hobby | Railway |
|-------|-------------|---------|
| Function timeout | 10 seconds | No limit (persistent service) |
| Cron jobs | Daily only | Any frequency |
| Cold starts | Yes (serverless) | No (persistent) |
| Cost | Free | $5/month credit (free tier) |

---

## Pre-Migration Checklist

- [ ] Railway account created
- [ ] Railway CLI installed
- [ ] Backup current Vercel deployment
- [ ] Export all environment variables from Vercel
- [ ] Document current DNS settings in Namecheap

---

## Phase 1: Railway Setup (5 minutes)

### 1.1 Install Railway CLI
```bash
npm install -g @railway/cli
# or
brew install railway
```

### 1.2 Login and Initialize
```bash
railway login
cd /path/to/FRCR_REVISION
railway init
# Select "Empty Project" or connect to GitHub repo
```

### 1.3 Create Project Files

**Procfile** (create in project root):
```
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

**runtime.txt** (create in project root):
```
python-3.12.0
```

**railway.json** (create in project root):
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "gunicorn app:app --bind 0.0.0.0:$PORT",
    "healthcheckPath": "/",
    "healthcheckTimeout": 30,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

---

## Phase 2: Environment Variables

### 2.1 Export from Vercel
```bash
# List all Vercel env vars
vercel env ls

# Pull to local file (for reference)
vercel env pull .env.vercel-backup
```

### 2.2 Required Environment Variables

Copy these to Railway Dashboard → Project → Variables:

#### Core Application
| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `APP_URL` | Public URL | `https://www.radinsights.xyz` |
| `PORT` | Railway sets automatically | (don't set manually) |

#### Database (Neon PostgreSQL - NO CHANGE)
| Variable | Description | Source |
|----------|-------------|--------|
| `DATABASE_URL` | Neon pooled connection | Copy from Vercel or Neon Dashboard |

**Note:** Neon works with any host. Just copy the connection string.

#### Claude AI
| Variable | Description | Source |
|----------|-------------|--------|
| `CLAUDE_API_KEY` | Anthropic API key | https://console.anthropic.com/ |
| `CLAUDE_MODEL` | Model to use | `claude-sonnet-4-20250514` |

#### Cloudflare R2 Storage (NO CHANGE)
| Variable | Description | Source |
|----------|-------------|--------|
| `R2_ACCOUNT_ID` | Cloudflare account ID | Cloudflare Dashboard |
| `R2_ACCESS_KEY_ID` | R2 API key ID | Cloudflare R2 > API Tokens |
| `R2_SECRET_ACCESS_KEY` | R2 API secret | Cloudflare R2 > API Tokens |
| `R2_BUCKET_NAME` | Bucket name | e.g., `frcr-case-images` |
| `R2_JURISDICTION` | Optional, if EU bucket | `eu` or omit |
| `R2_UPLOAD_WORKERS` | Parallel uploads | `20` |
| `MAX_UPLOAD_MB` | Upload size limit | `1024` |

**Note:** R2 works with any host. Just copy the credentials.

#### OneDrive / Azure (Case Images)
| Variable | Description | Source |
|----------|-------------|--------|
| `AZURE_CLIENT_ID` | Azure App client ID | Azure Portal > App Registrations |
| `AZURE_CLIENT_SECRET` | Azure App secret | Azure Portal > App Registrations |
| `ONEDRIVE_CLIENT_ID` | Same as AZURE_CLIENT_ID | (legacy alias) |
| `ONEDRIVE_CLIENT_SECRET` | Same as AZURE_CLIENT_SECRET | (legacy alias) |

**Action Required:** Update Azure App redirect URIs:
1. Go to Azure Portal → App Registrations → Your App
2. Add new redirect URI: `https://www.radinsights.xyz/auth/onedrive/callback`
3. Keep old Vercel URI until migration complete

#### Resend Email
| Variable | Description | Source |
|----------|-------------|--------|
| `RESEND_API_KEY` | Resend API key | https://resend.com/api-keys |
| `EMAIL_FROM` | Sender email | `noreply@radinsights.xyz` |
| `SUPERADMIN_EMAIL` | Admin notifications | Your email |

**Note:** Resend works with any host. Domain verification stays the same.

#### Cloudinary (Forum Images)
| Variable | Description | Source |
|----------|-------------|--------|
| `CLOUDINARY_CLOUD_NAME` | Cloud name | Cloudinary Dashboard |
| `CLOUDINARY_API_KEY` | API key | Cloudinary Dashboard |
| `CLOUDINARY_API_SECRET` | API secret | Cloudinary Dashboard |

**Note:** Cloudinary works with any host. No changes needed.

#### Image Search (Optional)
| Variable | Description |
|----------|-------------|
| `GOOGLE_SEARCH_API_KEY` | Google Custom Search |
| `GOOGLE_SEARCH_ENGINE_ID` | Google CSE ID |
| `BING_IMAGE_SEARCH_KEY` | Azure Bing Search |
| `REFERENCE_IMAGE_SEARCH_PROVIDERS` | `commons,openi` |

### 2.3 Railway CLI Method (Alternative)
```bash
# Set variables via CLI
railway variables set SECRET_KEY="your-secret-key"
railway variables set DATABASE_URL="postgresql://..."
railway variables set CLAUDE_API_KEY="sk-ant-..."
# ... etc
```

---

## Phase 3: Cron Jobs Setup

### 3.1 Railway Cron Configuration

Railway has built-in cron support. Add to `railway.json`:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "gunicorn app:app --bind 0.0.0.0:$PORT"
  },
  "crons": [
    {
      "schedule": "* * * * *",
      "command": "curl -X POST http://localhost:$PORT/api/cron/process-tnm-jobs"
    }
  ]
}
```

### 3.2 Alternative: Separate Cron Service

If the above doesn't work, create a second Railway service:

**cron-worker/Procfile:**
```
worker: python cron_worker.py
```

**cron_worker.py:**
```python
import schedule
import time
import requests
import os

def process_tnm_jobs():
    try:
        url = os.environ.get('APP_URL', 'http://localhost:5000')
        requests.post(f"{url}/api/cron/process-tnm-jobs", timeout=120)
    except Exception as e:
        print(f"Cron error: {e}")

schedule.every(1).minutes.do(process_tnm_jobs)

while True:
    schedule.run_pending()
    time.sleep(30)
```

---

## Phase 4: Code Changes

### 4.1 Remove Vercel-Specific Code

**Delete these files (optional, can keep for reference):**
- `api/index.py` - Vercel serverless wrapper
- `vercel.json` - Vercel config

**Or keep them** - they won't affect Railway deployment.

### 4.2 Update app.py (Optional)

Remove Vercel-specific environment checks if desired:
```python
# These can stay - they're harmless on Railway:
# os.getenv('VERCEL')
# os.getenv('VERCEL_ENV')
# os.getenv('VERCEL_URL')
```

### 4.3 Add gunicorn to requirements.txt

Check if already present:
```bash
grep gunicorn requirements.txt
```

If not, add:
```
gunicorn>=21.0.0
```

---

## Phase 5: Deploy to Railway

### 5.1 Initial Deployment
```bash
cd /path/to/FRCR_REVISION
railway up
```

### 5.2 Check Logs
```bash
railway logs
```

### 5.3 Get Temporary URL
Railway provides a temporary URL like `your-app.up.railway.app`. Test everything here first.

---

## Phase 6: Domain Migration (Namecheap)

### 6.1 Get Railway Domain Settings

1. Railway Dashboard → Project → Settings → Domains
2. Add custom domain: `www.radinsights.xyz`
3. Railway will show required DNS records

### 6.2 Update Namecheap DNS

1. Login to Namecheap → Domain List → radinsights.xyz → Manage
2. Go to Advanced DNS tab
3. Update/Add records:

| Type | Host | Value | TTL |
|------|------|-------|-----|
| CNAME | www | `your-project.up.railway.app` | Automatic |
| A | @ | Railway IP (if provided) | Automatic |

**Or use Railway's recommended method:**
| Type | Host | Value |
|------|------|-------|
| CNAME | www | `cname.railway.app` |

4. Wait for DNS propagation (5-30 minutes)

### 6.3 SSL Certificate

Railway automatically provisions SSL via Let's Encrypt. No action needed.

### 6.4 Verify Domain
```bash
# Check DNS propagation
dig www.radinsights.xyz CNAME

# Check HTTPS
curl -I https://www.radinsights.xyz
```

---

## Phase 7: Service Integrations Update

### 7.1 Azure App Registration (OneDrive)

1. Azure Portal → App Registrations → Your App
2. Authentication → Add redirect URI:
   - `https://www.radinsights.xyz/auth/onedrive/callback`
   - `https://www.radinsights.xyz/case-dicom/auth/callback`
3. Remove old Vercel URIs after migration verified

### 7.2 Resend Domain Verification

No changes needed - domain `radinsights.xyz` is already verified.

### 7.3 Cloudflare R2 CORS (if needed)

If you encounter CORS issues with R2:

1. Cloudflare Dashboard → R2 → Your Bucket → Settings → CORS
2. Add/Update allowed origins:
```json
[
  {
    "AllowedOrigins": ["https://www.radinsights.xyz"],
    "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3600
  }
]
```

---

## Phase 8: Testing Checklist

### 8.1 Core Functionality
- [ ] Homepage loads
- [ ] User login works
- [ ] Session persists (cookies working)
- [ ] Database queries work (Neon connection)

### 8.2 Case Management
- [ ] View case works
- [ ] Edit case works
- [ ] Image stack viewer loads images (R2)
- [ ] OneDrive image loading works

### 8.3 TNM Features
- [ ] TNM Calculator pages load
- [ ] TNM Generator queues jobs
- [ ] Cron processes jobs (check after 1-2 minutes)
- [ ] Calculator generation completes

### 8.4 Email
- [ ] Password reset email sends
- [ ] Admin approval emails send

### 8.5 Forum
- [ ] Forum loads
- [ ] Image upload works (Cloudinary)

---

## Phase 9: Cutover

### 9.1 Final Steps
1. Verify all tests pass on Railway
2. Update DNS to point to Railway (if not already)
3. Wait for DNS propagation
4. Monitor logs for errors

### 9.2 Rollback Plan

If issues occur:
1. Revert DNS in Namecheap to Vercel
2. Vercel deployment is still running (no changes made)
3. Debug Railway deployment
4. Retry cutover

### 9.3 Cleanup (After Stable)

1. Remove old Vercel redirect URIs from Azure
2. Optionally delete Vercel project
3. Update any documentation referencing Vercel

---

## Cost Comparison

| Service | Vercel Hobby | Railway Free |
|---------|-------------|--------------|
| Compute | Limited (serverless) | $5 credit/month |
| Functions | 10s timeout | No limit |
| Cron | Daily only | Any frequency |
| Bandwidth | 100GB | Included in credit |
| Database | External (Neon) | External (Neon) |
| Storage | External (R2) | External (R2) |

**Estimated Railway Usage:** Well under $5/month for current traffic.

---

## Files to Create Summary

| File | Content |
|------|---------|
| `Procfile` | `web: gunicorn app:app --bind 0.0.0.0:$PORT` |
| `runtime.txt` | `python-3.12.0` |
| `railway.json` | Build & deploy config + cron |

---

## Quick Reference Commands

```bash
# Deploy
railway up

# View logs
railway logs

# Open dashboard
railway open

# Set environment variable
railway variables set KEY=value

# List services
railway status

# Connect to shell
railway shell
```

---

## Timeline Estimate

| Phase | Duration |
|-------|----------|
| Railway setup | 5 minutes |
| Environment variables | 10 minutes |
| Code changes | 5 minutes |
| Initial deploy | 5 minutes |
| DNS migration | 5-30 minutes (propagation) |
| Testing | 15 minutes |
| **Total** | **~1 hour** |

---

## Support Resources

- Railway Docs: https://docs.railway.app/
- Railway Discord: https://discord.gg/railway
- Neon Docs: https://neon.tech/docs
- Cloudflare R2 Docs: https://developers.cloudflare.com/r2/

---

*Last Updated: February 2026*
