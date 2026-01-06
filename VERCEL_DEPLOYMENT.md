# Deployment to Vercel

## Quick Start

### 1. Login to Vercel
```bash
vercel login
```

### 2. Deploy
```bash
cd /Users/zen/myRepos/projects/FRCR_EXAMINER
vercel --prod
```

### 3. During Setup
- **Project name:** frcr-examiner
- **Framework:** Other
- **Root directory:** ./

## What Happens

✅ Flask app deployed to Vercel serverless
✅ Database stored in `/tmp` (ephemeral - resets on restart)
✅ App accessible at `https://frcr-examiner.vercel.app`

## Database Issue

**Important:** Vercel serverless functions use ephemeral storage. Database will reset after 24 hours.

### Solution: Use Vercel Postgres (Optional)

```bash
# Install Vercel Postgres
vercel postgres create
```

Then update `app.py`:
```python
# Use Vercel Postgres instead of SQLite
DATABASE_URL = os.getenv('POSTGRES_URL')
```

## Data Persistence Options

1. **Vercel Postgres** (recommended, free tier)
2. **External database** (PlanetScale MySQL, Supabase)
3. **Local SQLite with syncing** (keep local, upload backups)

## Commands

```bash
# Preview deployment
vercel

# Production deployment
vercel --prod

# Check logs
vercel logs

# Redeploy
vercel --prod --force
```

## Post-Deployment

1. Visit your deployed URL
2. Test all features
3. Download database backups regularly
4. Monitor logs in Vercel dashboard

---

**Your Vercel URL will be:** `https://frcr-examiner.vercel.app`
