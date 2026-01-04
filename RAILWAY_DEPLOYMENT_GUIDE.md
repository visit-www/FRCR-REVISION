# Railway Deployment - Complete Step-by-Step Guide

## Prerequisites
✅ GitHub account with FRCR_Examiner repo  
✅ Railway account linked to GitHub  
✅ App tested and working locally  

---

## 🚀 STEP-BY-STEP DEPLOYMENT

### **STEP 1: Go to Railway Dashboard**
1. Open [railway.app](https://railway.app)
2. Click **"Dashboard"** (top right)
3. Sign in with GitHub if not already

---

### **STEP 2: Create New Project**
1. Click **"New Project"** (big blue button)
2. Select **"Deploy from GitHub repo"**
3. Choose your GitHub account if prompted

---

### **STEP 3: Select Your Repository**
1. Search for **"FRCR_Examiner"** in the search box
2. Click on **"visit-www/Frcr-examiner"** to select it
3. Choose **"main"** branch (or your branch)
4. Click **"Deploy"**

*Railway is now analyzing your repo... this takes 30-60 seconds*

---

### **STEP 4: Wait for Initial Detection**
You'll see a loading screen. Railway is:
- Detecting Python project
- Reading requirements.txt
- Setting up environment

**This is normal - let it complete!**

---

### **STEP 5: Add PostgreSQL Database**
1. Once deployment shows, look for **"Add Service"** or **"+ New"** button
2. Click it
3. Select **"Database"** → **"PostgreSQL"**
4. Click **"Create"**

Railway will automatically:
- Create free PostgreSQL database
- Generate connection string
- Add to environment variables

---

### **STEP 6: Configure Environment Variables**
Railway should auto-detect and set:
- `DATABASE_URL` (PostgreSQL connection)
- `PORT` (5000)

To verify or add variables:
1. Click on your **"web"** service
2. Go to **"Variables"** tab
3. You should see `DATABASE_URL` already set

**Add these if needed:**
```
FLASK_ENV=production
FLASK_APP=app.py
```

---

### **STEP 7: Update Your Code for Production** (IMPORTANT)

Modify `app.py` to use PostgreSQL in production:

Find this line in your `app.py`:
```python
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "frcr_examiner.db")}'
```

Replace it with:
```python
# Use PostgreSQL on production, SQLite locally
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    # PostgreSQL on Railway
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL.replace('postgres://', 'postgresql://')
else:
    # SQLite locally
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "frcr_examiner.db")}'
```

---

### **STEP 8: Update requirements.txt**

Add PostgreSQL driver. Open `requirements.txt` and add:
```
Flask==2.3.3
Flask-SQLAlchemy==3.0.5
SQLAlchemy==2.0.45
python-dotenv==1.0.0
Werkzeug==2.3.7
gunicorn==21.2.0
psycopg2-binary==2.9.9
```

---

### **STEP 9: Create Procfile** (If not exists)

Create file named `Procfile` (no extension) in root directory with:
```
web: gunicorn app:app
```

---

### **STEP 10: Commit and Push Changes**

```bash
cd /Users/zen/myRepos/projects/FRCR_EXAMINER

# Add all changes
git add .

# Commit
git commit -m "Prepare for Railway deployment with PostgreSQL support"

# Push to GitHub
git push origin main
```

Railway will automatically detect the push and **redeploy** your app!

---

### **STEP 11: Wait for Deployment**

On Railway dashboard:
1. You'll see deployment building
2. Watch the logs scroll by
3. Wait for **"✓ Deployment Successful"** message

**Takes 2-5 minutes**

---

### **STEP 12: Get Your Live URL**

1. On Railway dashboard, click your **"web"** service
2. Look for **"Domain"** section
3. You'll see something like: `https://frcr-examiner.railway.app`

Copy this URL - this is your live app!

---

### **STEP 13: Test Your App**

1. Open your Railway URL in browser
2. Test these features:
   - Create exam session
   - Add packets
   - Add cases
   - View cases
   - Manage sessions

✅ If everything works, you're done!

---

## ✅ TROUBLESHOOTING

### **Issue: Deployment fails during build**

**Solution:**
1. Check Railway logs for errors
2. Verify `requirements.txt` is correct
3. Verify `Procfile` exists
4. Push fixes and Railway will redeploy

---

### **Issue: "Application failed to start" error**

**Possible causes:**
```
1. Missing gunicorn in requirements.txt
   → Add: gunicorn==21.2.0

2. Procfile has wrong syntax
   → Should be: web: gunicorn app:app

3. DATABASE_URL not set
   → Check Variables tab in Railway
   → Should show DATABASE_URL automatically
```

---

### **Issue: Database connection error**

**Solution:**
1. Check that PostgreSQL database was created
2. In Railway, click **"PostgreSQL"** service
3. Verify it shows **"Deployed"**
4. Check `app.py` has correct database logic

---

### **Issue: Can't see PostgreSQL database in Railway**

**Solution:**
1. Click **"New"** button
2. Select **"Database"**
3. Choose **"PostgreSQL"**
4. Click **"Create"**

Railway will automatically add connection variables.

---

## 🔍 VERIFICATION CHECKLIST

- [ ] Repository pushed to GitHub (main branch)
- [ ] `requirements.txt` has gunicorn and psycopg2-binary
- [ ] `Procfile` exists with: `web: gunicorn app:app`
- [ ] `app.py` checks for `DATABASE_URL` environment variable
- [ ] PostgreSQL database created in Railway
- [ ] Deployment shows "✓ Deployed Successfully"
- [ ] Live URL is accessible
- [ ] App features work (create session, add cases, etc.)

---

## 📊 WHAT YOU GET

| Feature | Status |
|---------|--------|
| Web hosting | ✅ FREE |
| PostgreSQL database | ✅ FREE |
| Auto-deploys on git push | ✅ YES |
| HTTPS/SSL | ✅ INCLUDED |
| Storage | ✅ 100GB+ |
| Monthly usage | ✅ FREE |

---

## 🎯 SHARING WITH COLLEAGUES

Once deployment is successful:

1. Get your Railway URL (e.g., `https://frcr-examiner.railway.app`)
2. Share with colleagues: **Just send them the URL!**
3. They can access the app directly in their browser
4. All data is stored in the shared PostgreSQL database
5. No installation needed for colleagues - just a web browser!

---

## 📝 NEXT STEPS AFTER DEPLOYMENT

1. **Test thoroughly** with live URL
2. **Create test data** in production
3. **Share URL** with colleagues
4. **Monitor logs** if issues occur
5. **Push updates** to GitHub - Railway auto-redeploys

---

## 🚨 IMPORTANT NOTES

### Auto-redeployment
- Every time you push to GitHub, Railway automatically redeploys
- Takes 2-5 minutes
- No manual steps needed
- Database data persists

### Monitoring
- Click **"Logs"** tab to see app errors
- Click **"Metrics"** to see usage
- Both free in Railway

### Scaling (not needed for your app)
- Railway auto-scales if needed
- Free tier is very generous
- You won't hit limits with FRCR Examiner

---

## 💾 DATABASE MANAGEMENT

Railway PostgreSQL includes:
- Free 100GB storage (more than enough)
- Automatic backups
- Secure connection
- No maintenance needed

To view database contents:
1. Click **"PostgreSQL"** service in Railway
2. Go to **"Data"** tab
3. You can view/manage tables

---

## 🔐 SECURITY

- ✅ HTTPS enabled automatically
- ✅ Database connections encrypted
- ✅ Environment variables protected
- ✅ No secrets in code
- ✅ All data encrypted at rest

---

## 📞 HELP LINKS

- Railway Docs: https://docs.railway.app
- Flask Deployment: https://docs.railway.app/guides/flask
- PostgreSQL: https://docs.railway.app/databases/postgresql
- Common Issues: https://docs.railway.app/troubleshoot

---

## 🎉 SUCCESS INDICATORS

Once complete, you should have:
1. ✅ Live URL (https://something.railway.app)
2. ✅ App accessible in browser
3. ✅ All features working
4. ✅ Data persisting in PostgreSQL
5. ✅ Can share URL with colleagues
6. ✅ $0 cost

---

**That's it! Your app is now live and free! 🚀**

Any issues? Check the troubleshooting section or Railway logs.

