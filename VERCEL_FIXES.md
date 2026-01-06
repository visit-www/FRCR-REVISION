# Vercel Deployment Issues - Diagnosis & Fixes

## Problems Found

### 1. **Missing Serverless Function Entry Point**
   - **Issue**: No `/api/index.py` file to handle serverless requests
   - **Impact**: Vercel couldn't route requests to Flask app
   - **Fix**: Created `api/index.py` that exports the Flask app

### 2. **Incorrect vercel.json Configuration**
   - **Issue**: Configuration was trying to build a static site instead of a Python app
   - **Previous config**:
     ```json
     "buildCommand": "mkdir -p public && cp -r templates/* public/..."
     "outputDirectory": "public"
     ```
   - **Problem**: This doesn't run Flask, just copies HTML files
   - **Fix**: Updated to:
     ```json
     "buildCommand": "pip install -r requirements.txt"
     "runtime": "python@3.11"
     "functions": { "api/index.py": { "maxDuration": 30 } }
     "routes": [
       { "src": "/.*", "dest": "/api/index.py" }
     ]
     ```

### 3. **Wrong Environment Variable**
   - **Issue**: `FLASK_BACKEND_URL` was hardcoded to `localhost:5000`
   - **Problem**: This URL doesn't exist in production
   - **Fix**: Removed this variable; Flask uses relative URLs instead

### 4. **Missing .vercelignore Entries**
   - **Issue**: Large unnecessary directories were being uploaded
   - **Problem**: Slower builds, potential conflicts
   - **Fix**: Added entries to exclude: `node_modules/`, `dist/`, `build/`, `Frcr-examiner/`, `electron/`, etc.

## Files Modified

### 1. **vercel.json** ✅
   - Updated to properly configure Python runtime
   - Added serverless function routes
   - Corrected build command

### 2. **api/index.py** ✅ (NEW)
   - Created serverless entry point
   - Imports Flask app from root
   - Vercel routes all requests through this

### 3. **.vercelignore** ✅
   - Added unnecessary files and directories
   - Reduces build size and time

### 4. **VERCEL_DEPLOYMENT.md** ✅
   - Rewrote with correct Flask-specific instructions
   - Added troubleshooting guide
   - Documented data persistence options

## What Happens Now

1. **Build**: `pip install -r requirements.txt`
2. **Runtime**: Python 3.11 serverless functions
3. **Request Flow**: All requests → `api/index.py` → Flask app
4. **Database**: SQLite in `/tmp` (ephemeral, 24-hour reset)
5. **Static Files**: Served from filesystem, cached by CDN

## Next Steps to Deploy

```bash
# 1. Verify local Flask app works
python app.py

# 2. Update requirements.txt with all dependencies
pip freeze > requirements.txt

# 3. Test with Vercel locally (optional)
npm install -g vercel
vercel dev

# 4. Deploy to production
git add .
git commit -m "Fix Vercel Flask deployment configuration"
git push origin main
vercel --prod
```

## Known Limitations

⚠️ **Database Persistence**: SQLite resets every 24 hours
- Recommended: Use PostgreSQL instead
- Setup: `vercel postgres create` or use external database

## Verification

After deployment, verify with:
```bash
# Check if API is responding
curl https://frcr-examiner.vercel.app/api/exam/sessions

# View logs
vercel logs frcr-examiner
```

---

**Status**: ✅ Configuration Fixed
**Ready to Deploy**: Yes
**Date**: January 7, 2026
