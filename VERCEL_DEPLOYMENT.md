# Deployment to Vercel

## Overview

This application is a Flask-based web app with a SQLite database. Vercel deployment uses Python serverless functions to run the Flask app.

## Prerequisites

- Vercel account (free tier is fine)
- GitHub repository synced with your local code
- Vercel CLI (optional but recommended)

## Installation

### Option 1: Using Vercel CLI (Recommended)

```bash
# Install Vercel CLI globally
npm install -g vercel

# Login to Vercel
vercel login

# Deploy from project directory
cd /Users/zen/myRepos/projects/FRCR_EXAMINER
vercel --prod
```

### Option 2: GitHub Integration (Automatic)

1. Push your code to GitHub
2. Go to [vercel.com](https://vercel.com)
3. Click "New Project"
4. Select your GitHub repository
5. Vercel automatically detects Python and deploys

## Configuration Files

✅ **vercel.json** - Main configuration file
- Specifies Python 3.11 runtime
- Routes all requests through Flask (`api/index.py`)
- Sets environment variables

✅ **api/index.py** - Serverless function entry point
- Imports and exposes the Flask app
- Vercel calls this function for all HTTP requests

✅ **.vercelignore** - Files to exclude from deployment
- Removes unnecessary files to speed up builds

## How It Works

1. **Build Phase**
   - Vercel installs dependencies from `requirements.txt`
   - Creates a Python 3.11 serverless environment

2. **Request Handling**
   - All HTTP requests → `api/index.py`
   - Flask app processes requests normally
   - Routes through your existing `/api/*` endpoints

3. **Database**
   - SQLite stored in `/tmp` (ephemeral storage)
   - **Important**: Database resets every 24 hours
   - See "Data Persistence" section below

## Deployment Steps

### First-Time Setup

```bash
# 1. Ensure all dependencies are in requirements.txt
pip freeze > requirements.txt

# 2. Commit changes
git add .
git commit -m "Add Vercel configuration for Flask deployment"
git push

# 3. Deploy
vercel --prod
```

### Subsequent Deployments

```bash
# Simply push to GitHub (if using GitHub integration)
git push

# OR use Vercel CLI
vercel --prod
```

## Post-Deployment Testing

1. Visit your deployment URL: `https://frcr-examiner.vercel.app`
2. Test API endpoints:
   ```bash
   curl https://frcr-examiner.vercel.app/api/exam/sessions
   ```
3. Check logs in Vercel dashboard
4. Monitor for errors

## Data Persistence Options

### ⚠️ Problem: Vercel Ephemeral Storage

SQLite files are lost after:
- Function invocation timeout (>30 seconds)
- Server restart
- 24 hours of inactivity

### Solution 1: Use PostgreSQL (Recommended)

```bash
# Add a Postgres database to your Vercel project
vercel postgres create
```

Then update `app.py`:
```python
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    # Use PostgreSQL in production
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL.replace('postgres://', 'postgresql://')
else:
    # SQLite for local development
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{instance_path}/frcr_examiner.db'
```

**Cost**: Free tier available (50 MB)

### Solution 2: External Database Services

- **Supabase** (PostgreSQL) - free tier
- **PlanetScale** (MySQL) - free tier
- **Railway** (any database) - $5/month minimum

### Solution 3: Accept Ephemeral Storage

If data loss is acceptable:
- Database resets every 24 hours
- Useful for testing/demo purposes
- Users must re-populate data on deployment

## Environment Variables

Set in Vercel Dashboard or via CLI:

```bash
# Interactive setup
vercel env add DATABASE_URL

# Or edit in Dashboard: Settings → Environment Variables
```

Common variables:
- `DATABASE_URL` - External database connection string
- `FLASK_ENV` - Set to "production"

## Monitoring & Debugging

### View Logs
```bash
vercel logs [your-project-name]
```

### Check Build Logs
- Vercel Dashboard → Deployments → Click deployment → Build Logs

### Common Issues

**Issue**: "No module named 'app'"
- **Fix**: Ensure `app.py` is in the root directory

**Issue**: "Database locked"
- **Fix**: Use external PostgreSQL database instead of SQLite

**Issue**: "Function timeout"
- **Fix**: Increase timeout in `vercel.json` (max 30s for hobby plan)

## Rollback

```bash
# Revert to previous deployment
vercel rollback
```

## Domain Configuration

1. Go to Vercel Dashboard
2. Select your project
3. Settings → Domains
4. Add custom domain (requires DNS configuration)

## Performance Optimization

1. **Cold Start**: First request takes ~2-3 seconds (normal)
2. **Caching**: Static files cached in CDN
3. **Database**: Use connection pooling for external database

## Security Checklist

- [ ] Change `SECRET_KEY` in `app.py`
- [ ] Set environment variables securely (not in code)
- [ ] Use HTTPS only (automatic with Vercel)
- [ ] Enable CORS only for trusted origins
- [ ] Use external database in production

## Troubleshooting

### Deployment Fails
```bash
# Check for syntax errors locally
python app.py

# Verify requirements.txt
cat requirements.txt

# Test Flask app
vercel dev
```

### 502 Bad Gateway
- Check Vercel logs: `vercel logs`
- Verify Flask app starts without errors
- Check for timeout issues in your code

### Routes Not Working
- Ensure Flask routes exist
- Check CORS configuration
- Verify headers are correct

## Commands Reference

```bash
# View all deployments
vercel list

# Inspect a deployment
vercel inspect [url]

# Set environment variables
vercel env add [NAME]

# Remove environment variable
vercel env remove [NAME]

# Force redeploy
vercel --prod --force

# Preview deployment (test before production)
vercel

# View project settings
vercel project info
```

## Your Deployment URL

After deployment, your app will be available at:
```
https://frcr-examiner.vercel.app
```

Monitor the deployment in the Vercel Dashboard!

---

**Last Updated**: January 2026
**Framework**: Flask 2.3.3
**Runtime**: Python 3.11
