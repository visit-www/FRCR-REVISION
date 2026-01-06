# FRCR Examiner - Local Server Setup

A simple medical exam management system that runs on your computer.

## Installation & Running

### macOS/Linux

1. **Clone the repository**
```bash
git clone https://github.com/visit-www/Frcr-examiner.git
cd Frcr-examiner
```

2. **Run the start script**
```bash
chmod +x start.sh
./start.sh
```

3. **Open in browser**
Visit: **http://localhost:5000**

That's it! Server automatically:
- Creates Python environment
- Installs dependencies
- Creates local database
- Starts the application

---

### Windows

1. **Clone the repository**
```bash
git clone https://github.com/visit-www/Frcr-examiner.git
cd Frcr-examiner
```

2. **Double-click** `start.bat`

3. **Open in browser**
Visit: **http://localhost:5000**

---

## Features

- 📋 Exam session management
- 👥 Candidate tracking
- 🏥 Medical case management with images
- 💬 Q&A pairs for each case
- 📊 Session analytics
- 💾 Automatic database backups

---

## Database

- **Type:** SQLite (local file)
- **Location:** `instance/frcr_examiner.db`
- **Backups:** `backups/` folder (automatic)

All data stays on your computer. Nothing is sent to the cloud.

---

## Manual Setup (If You Prefer)

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

---

## Troubleshooting

### "Python not found"
- Install Python 3.9+ from https://www.python.org/downloads/
- Windows: Check "Add Python to PATH" during installation

### "Port 5000 already in use"
- Close other applications using port 5000
- Or edit `app.py` line 82: change `port=5000` to another number

### "Permission denied" (macOS)
```bash
chmod +x start.sh
./start.sh
```

### Database errors
- Delete `instance/frcr_examiner.db`
- Run start script again (will recreate fresh database)

---

## Stopping the Server

Press **Ctrl+C** in the terminal where the server is running.

---

## Updating

To get the latest version:
```bash
git pull origin main
```

Then run `start.sh` (or `start.bat`) again.

---

## Data Backups

Backups are created automatically every 24 hours in `backups/` folder.

To manually backup:
```bash
# Copy the database file
cp instance/frcr_examiner.db ~/Desktop/frcr_backup.db
```

---

## Support

- GitHub: https://github.com/visit-www/Frcr-examiner
- Issues: https://github.com/visit-www/Frcr-examiner/issues

---

**Simple. Local. Secure. All your data stays on your computer.**
