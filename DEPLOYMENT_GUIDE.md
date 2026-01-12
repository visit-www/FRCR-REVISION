# Vercel Deployment Guide

## Prerequisites

1. ✅ Git repository cleaned (sensitive files removed from history)
2. ✅ Vercel account (sign up at https://vercel.com)
3. ✅ Supabase account (for PostgreSQL database)

## Step 1: Push Cleaned History to GitHub

**⚠️ IMPORTANT**: The Git history has been cleaned locally but not pushed yet.

```bash
# Force push the cleaned history
git push origin --force --all
git push origin --force --tags
```

**Warning**: This will overwrite GitHub history. Make sure:
- You have push access
- Team members are notified to re-clone
- You have a backup (backup branch exists)

## Step 2: Create Supabase Database

1. Go to https://supabase.com and sign in
2. Create a new project (or use existing)
3. Go to **Settings** → **Database**
4. Copy the **Connection String** (use "Connection Pooling" → "Direct connection")
5. It should look like: `postgresql://postgres:[password]@[host]:5432/postgres`

## Step 3: Generate SECRET_KEY

Generate a strong random secret key:

```bash
# Using Python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Or using OpenSSL
openssl rand -base64 32
```

Save this key - you'll need it for Vercel environment variables.

## Step 4: Deploy to Vercel

### Option A: Via Vercel Dashboard (Recommended)

1. **Import Repository**
   - Go to https://vercel.com/dashboard
   - Click **Add New** → **Project**
   - Import your GitHub repository: `visit-www/FRCR-REVISION`

2. **Configure Project**
   - **Framework Preset**: Other
   - **Root Directory**: `./` (root)
   - **Build Command**: `pip install -r requirements.txt`
   - **Output Directory**: Leave empty
   - **Install Command**: Leave empty

3. **Set Environment Variables**
   Click **Environment Variables** and add:
   
   ```
   SECRET_KEY = [your-generated-secret-key]
   DATABASE_POSTGRES_URL_NON_POOLING = [your-supabase-connection-string]
   PYTHON_VERSION = 3.9
   ```
   
   **Important**: 
   - Use `DATABASE_POSTGRES_URL_NON_POOLING` (not `DATABASE_URL`)
   - Make sure the connection string uses `postgresql://` (not `postgres://`)
   - Remove any query parameters like `?pgbouncer=true` from the connection string

4. **Deploy**
   - Click **Deploy**
   - Wait for build to complete (2-5 minutes)
   - Your app will be live at `https://your-project.vercel.app`

### Option B: Via Vercel CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# Deploy
vercel

# Set environment variables
vercel env add SECRET_KEY
vercel env add DATABASE_POSTGRES_URL_NON_POOLING
vercel env add PYTHON_VERSION

# Deploy to production
vercel --prod
```

## Step 5: Initialize Database

After first deployment:

1. Visit your app: `https://your-project.vercel.app`
2. The app will automatically create database tables on first run
3. Register the first user (this user becomes admin)

## Step 6: Verify Deployment

1. ✅ App loads without errors
2. ✅ Can register/login
3. ✅ Database connection works
4. ✅ All routes accessible

## Troubleshooting

### Build Fails

- Check Vercel build logs
- Verify `requirements.txt` is correct
- Check Python version (should be 3.9)

### Database Connection Error

- Verify `DATABASE_POSTGRES_URL_NON_POOLING` is set correctly
- Check Supabase connection string format
- Ensure connection string uses `postgresql://` not `postgres://`
- Remove query parameters from connection string

### SECRET_KEY Error

- App will fail to start if `SECRET_KEY` is not set
- Generate a new key and add to Vercel environment variables
- Redeploy after adding

### 500 Errors

- Check Vercel function logs
- Verify all environment variables are set
- Check database connection
- Review application logs in Vercel dashboard

## Environment Variables Summary

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | ✅ Yes | Strong random key for session encryption |
| `DATABASE_POSTGRES_URL_NON_POOLING` | ✅ Yes | Supabase PostgreSQL connection string |
| `PYTHON_VERSION` | ⚠️ Recommended | Python version (3.9) |
| `DATABASE_URL` | ⚠️ Optional | Alternative database URL (fallback) |

## Post-Deployment

1. **Test all features**
   - User registration/login
   - Case management
   - Student features
   - Admin features

2. **Set up custom domain** (optional)
   - Go to Vercel project settings
   - Add your custom domain

3. **Monitor**
   - Check Vercel analytics
   - Monitor function execution times
   - Watch for errors in logs

## Support

- Vercel Docs: https://vercel.com/docs
- Supabase Docs: https://supabase.com/docs
- Flask Docs: https://flask.palletsprojects.com
