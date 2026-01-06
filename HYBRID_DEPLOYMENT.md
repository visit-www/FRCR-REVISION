# FRCR Examiner - Vercel + Local Storage Hybrid Deployment

Deploy to Vercel while keeping all data on your computer locally.

## Architecture

```
┌─────────────────────┐
│   Vercel (Cloud)    │
│   Web Interface     │
│  (HTML/JS/CSS)      │
└─────────────────────┘
           ↓ API Calls (CORS)
┌─────────────────────┐
│  Your Computer      │
│  Flask Backend      │  ← Runs locally
│  SQLite Database    │  ← Your data stays here
└─────────────────────┘
```

## How It Works

1. **Frontend:** Deployed to Vercel (accessible from anywhere)
2. **Backend:** Runs on your local computer
3. **Database:** Stored locally in SQLite
4. **Communication:** CORS-enabled API calls from Vercel to your local backend

## Setup

### Step 1: Run Local Flask Backend

```bash
# On your computer
cd Frcr-examiner
./start.sh  # macOS/Linux
# or
start.bat   # Windows
```

Server runs at: `http://localhost:5000`

### Step 2: Deploy to Vercel

```bash
vercel --prod
```

During setup:
- Project name: `frcr-examiner`
- Framework: `Python - Flask`

Your app will be at: `https://frcr-examiner.vercel.app`

### Step 3: Update Frontend API URL

The frontend needs to know where your Flask backend is:

**Option A: Access Locally (Same Network)**
- Frontend calls `http://localhost:5000`
- Works if accessing from same machine

**Option B: Access Remotely (Different Network)**
- Use ngrok to tunnel your local Flask to the internet:
  ```bash
  ngrok http 5000
  ```
- Copy the ngrok URL (e.g., `https://abc123.ngrok.io`)
- Update frontend to call that URL

**Option C: Use Environment Variable**
- Create `.env.local` in project root:
  ```
  REACT_APP_API_URL=http://localhost:5000
  ```

## Important Notes

### Your Local Flask Must Stay Running

The Vercel frontend needs your local backend running 24/7. If you close the terminal, the app won't work.

### Data Security

✅ **Secure:** All data stays on your computer (SQLite)
✅ **No cloud database:** Your exam data never goes to cloud servers
✅ **Only UI on Vercel:** Just the website interface is hosted

### Network Access

- **Local Network:** Access from any device on your home/office WiFi
- **Internet:** Use ngrok for remote access
- **Always:** Vercel frontend loads instantly from cloud

## Troubleshooting

### "Cannot connect to backend"
1. Check Flask is running: `http://localhost:5000` in browser
2. Check CORS is enabled in `app.py`
3. Use ngrok if accessing from outside network

### "CORS error"
- Flask CORS is already enabled
- Check browser console for exact error
- Verify API URLs match

### "Database not found"
- Flask automatically creates `instance/frcr_examiner.db`
- Check folder has write permissions
- Delete old database and restart Flask

## Deployment Commands

```bash
# First time
vercel --prod

# Update code
git push origin main
vercel --prod

# Check logs
vercel logs

# Local testing before deployment
vercel
```

## File Structure After Deployment

```
Local Computer:
  ├─ app.py             (Flask backend)
  ├─ models.py          (Database models)
  ├─ instance/          
  │  └─ frcr_examiner.db (YOUR DATA - STAYS LOCAL)
  ├─ templates/
  ├─ static/
  └─ backups/           (Auto-backups)

Vercel:
  ├─ HTML/CSS/JS (Static UI)
  ├─ API routing
  └─ Proxy to localhost:5000
```

## Backing Up Your Data

Since everything is local, just backup your `instance/frcr_examiner.db` file:

```bash
cp instance/frcr_examiner.db ~/Desktop/backup_$(date +%Y%m%d).db
```

Or use the auto-backup feature (every 24h in `backups/` folder).

## Reverting to Local Only

If you want to stop using Vercel and just run locally:

```bash
./start.sh  # or start.bat
# Access at http://localhost:5000
```

That's it!

---

**Summary:** Best of both worlds - professional cloud UI, local data storage!
