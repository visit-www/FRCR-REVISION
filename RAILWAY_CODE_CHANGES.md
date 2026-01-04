# Railway Deployment - Code Changes Required

## Quick Summary
You need to make 3 changes to your code for Railway deployment to work.

---

## CHANGE 1: Update `app.py`

**Find this section** in your `app.py` (around line 12-14):
```python
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "frcr_examiner.db")}'
```

**Replace with this:**
```python
# Use PostgreSQL on production (Railway), SQLite locally
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    # PostgreSQL on Railway
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL.replace('postgres://', 'postgresql://')
else:
    # SQLite for local development
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "frcr_examiner.db")}'
```

✅ This allows your app to work both locally (SQLite) and on Railway (PostgreSQL)

---

## CHANGE 2: Update `requirements.txt`

**Current:**
```
Flask==2.3.3
Flask-SQLAlchemy==3.0.5
SQLAlchemy==2.0.45
python-dotenv==1.0.0
Werkzeug==2.3.7
```

**Replace with:**
```
Flask==2.3.3
Flask-SQLAlchemy==3.0.5
SQLAlchemy==2.0.45
python-dotenv==1.0.0
Werkzeug==2.3.7
gunicorn==21.2.0
psycopg2-binary==2.9.9
```

✅ Added:
- `gunicorn`: Production web server for Railway
- `psycopg2-binary`: PostgreSQL driver

---

## CHANGE 3: Create `Procfile`

**Create new file** named `Procfile` (no .txt extension) in your root directory.

**Content:**
```
web: gunicorn app:app
```

✅ This tells Railway how to run your app

---

## HOW TO APPLY CHANGES

### In Terminal:
```bash
cd /Users/zen/myRepos/projects/FRCR_EXAMINER

# Make the changes above to the 3 files

# Commit and push
git add .
git commit -m "Configure app for Railway deployment"
git push origin main
```

### That's it!
Railway will automatically:
1. Detect your push
2. Create PostgreSQL database
3. Install dependencies
4. Deploy your app
5. Give you a live URL

---

## TESTING LOCALLY (Before pushing)

**Test that your app still works locally after changes:**

```bash
# Make sure you're in the project directory
cd /Users/zen/myRepos/projects/FRCR_EXAMINER

# Activate virtual environment
source venv/bin/activate

# Install new requirements
pip install -r requirements.txt

# Run the app (should still work with SQLite locally)
python app.py
```

✅ Should work exactly like before at `http://localhost:5000`

---

## FILE LOCATIONS

After changes, you should have:

```
FRCR_EXAMINER/
├── app.py ← MODIFIED (database config)
├── requirements.txt ← MODIFIED (added gunicorn, psycopg2)
├── Procfile ← NEW FILE (for Railway)
├── models.py
├── templates/
├── static/
└── instance/
```

---

## QUICK REFERENCE

| Change | File | What | Why |
|--------|------|------|-----|
| 1 | `app.py` | Use env DATABASE_URL or local SQLite | Works on Railway & locally |
| 2 | `requirements.txt` | Add gunicorn, psycopg2-binary | For production deployment |
| 3 | `Procfile` | `web: gunicorn app:app` | Tells Railway how to run app |

---

## IMPORTANT

✅ All changes are **backward compatible**
- Your app will still run locally with SQLite
- On Railway, it uses PostgreSQL
- No breaking changes
- Data format stays the same

---

## NEXT STEP

Once these 3 changes are made and pushed:
1. Go to Railway dashboard
2. Click "Deploy from GitHub repo"
3. Select your FRCR_Examiner repo
4. Railway handles the rest!

See **[RAILWAY_DEPLOYMENT_GUIDE.md](RAILWAY_DEPLOYMENT_GUIDE.md)** for complete step-by-step deployment instructions.

