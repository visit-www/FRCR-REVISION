# FRCR Examiner - Simple Installation Guide

## 🚀 Quick Start (No Compilation Needed!)

FRCR Examiner now uses a **simple, cross-platform launcher** that handles everything automatically. No PyInstaller or build tools required.

### macOS Installation

1. **Download** the release ZIP and extract it
2. **Open Terminal** and navigate to the folder:
   ```bash
   cd /path/to/FRCR-Examiner
   ```
3. **Run the installer**:
   ```bash
   bash install_and_run.sh
   ```

That's it! The script will:
- ✅ Check if Python 3 is installed
- ✅ Create a virtual environment
- ✅ Install all dependencies automatically
- ✅ Set up the database
- ✅ Launch the web app
- ✅ Open your browser to http://localhost:5000

### Windows Installation

1. **Download** the release ZIP and extract it
2. **Open Command Prompt** (or PowerShell) and navigate to the folder:
   ```cmd
   cd C:\path\to\FRCR-Examiner
   ```
3. **Double-click** `install_and_run.bat` OR run:
   ```cmd
   install_and_run.bat
   ```

The script handles everything else automatically!

---

## 📋 Requirements

- **Python 3.9+** (free download: https://www.python.org/downloads/)
  - **Windows only**: Make sure to check "Add Python to PATH" during installation!

That's the ONLY requirement. Everything else is handled automatically.

---

## ⚙️ Manual Setup (If You Prefer)

If you want to run it manually:

```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

Then open http://localhost:5000 in your browser.

---

## 🆘 Troubleshooting

### "Python is not found"
- **macOS**: Install from https://www.python.org/downloads/
- **Windows**: Install Python and check "Add Python to PATH" during setup

### "Permission denied" (macOS only)
```bash
chmod +x install_and_run.sh
bash install_and_run.sh
```

### Port already in use
The app uses port 5000. If that's in use, edit `app.py` and change:
```python
app.run(host='127.0.0.1', port=5000)  # Change 5000 to another number
```

### Database issues
Delete `frcr_examiner.db` and run the installer again—it will recreate it.

---

## 📦 What's Included

```
FRCR-Examiner/
├── app.py                 # Main Flask application
├── models.py              # Database models
├── requirements.txt       # Python dependencies
├── install_and_run.sh     # macOS/Linux launcher
├── install_and_run.bat    # Windows launcher
├── templates/             # HTML templates
├── static/                # CSS, JavaScript, images
└── frcr_examiner.db       # Database (created on first run)
```

---

## 🔄 Running It Again

After the first setup, you can just run the installer script again—it skips already-completed steps.

---

**Questions?** Open an issue on [GitHub](https://github.com/visit-www/Frcr-examiner)
