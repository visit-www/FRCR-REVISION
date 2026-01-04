# 🚀 Railway Deployment - Quick Start (5 Minutes)

## Before You Start
✅ You have Railway + GitHub connected  
✅ Your FRCR_Examiner code is on GitHub  

---

## THE 3 QUICK CHANGES

### 1️⃣ Edit `app.py` (Around line 12-14)

**BEFORE:**
```python
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "frcr_examiner.db")}'
```

**AFTER:**
```python
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL.replace('postgres://', 'postgresql://')
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "frcr_examiner.db")}'
```

---

### 2️⃣ Edit `requirements.txt`

Add these 2 lines at the end:
```
gunicorn==21.2.0
psycopg2-binary==2.9.9
```

---

### 3️⃣ Create `Procfile` file

Create new file in root directory with this one line:
```
web: gunicorn app:app
```

---

## DEPLOY (3 STEPS)

### Step 1: Commit & Push
```bash
cd /Users/zen/myRepos/projects/FRCR_EXAMINER
git add .
git commit -m "Railway deployment setup"
git push origin main
```

### Step 2: Go to Railway
Open https://railway.app/dashboard

### Step 3: Deploy
1. Click **"New Project"**
2. Select **"Deploy from GitHub repo"**
3. Choose **"Frcr-examiner"**
4. Click **"Deploy"**
5. Wait 2-5 minutes

---

## 🎉 DONE!

Railway will automatically:
- ✅ Detect Python/Flask app
- ✅ Create free PostgreSQL database
- ✅ Deploy your app
- ✅ Give you a live URL

---

## GET YOUR URL

In Railway dashboard:
1. Click on **"web"** service
2. Look for **"Domain"**
3. Copy the URL (like: `https://frcr-examiner.railway.app`)
4. Share with colleagues!

---

## VERIFY IT WORKS

Open your Railway URL and test:
- [ ] Create exam session
- [ ] Add packets & cases
- [ ] View sessions
- [ ] Manage content

✅ All working? You're live!

---

## COST

**FREE** 🎉
- No hosting charges
- No database charges
- No hidden fees

---

## 📚 NEED HELP?

- Full details: See `RAILWAY_DEPLOYMENT_GUIDE.md`
- Code changes: See `RAILWAY_CODE_CHANGES.md`
- Database options: See `FREE_DATABASE_OPTIONS.md`

---

**That's it! Your app is now on the web! 🌐**

