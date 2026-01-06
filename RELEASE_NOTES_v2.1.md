# FRCR Examiner v2.1 - Getting Started

## Download

Get the latest release: **[FRCR-Examiner-v2.1-Source.zip](https://github.com/visit-www/Frcr-examiner/releases/tag/v2.1.0)**

## Installation

### Prerequisites
- **Python 3.9+** (download from https://www.python.org/downloads/)
  - Windows users: Make sure to check **"Add Python to PATH"** during installation

### Setup (Pick One)

#### Option 1: Automated Installer (Easiest)

**macOS/Linux:**
```bash
# Extract the ZIP, then:
bash install_and_run.sh
```

**Windows:**
```cmd
# Extract the ZIP, then double-click:
install_and_run.bat
```

#### Option 2: Manual Setup

```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
# macOS/Linux:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

## What Happens Next

1. ✅ Virtual environment is created
2. ✅ All dependencies are installed
3. ✅ Database is initialized
4. ✅ Flask server starts
5. ✅ Browser opens to **http://localhost:5000**

## Features

- 📋 Exam session management
- 👥 Candidate tracking
- 🏥 Medical case management with images
- 💬 Q&A pairs for each case
- 📊 Session analytics
- 💾 Automatic database backups

## Documentation

- [Full Installation Guide](INSTALLATION.md) - Detailed setup instructions
- [README.md](README.md) - Complete project information

## Troubleshooting

**"Python is not found"**
- Install Python from https://www.python.org/downloads/
- Windows: Check "Add Python to PATH" during installation

**"Permission denied" (macOS)**
```bash
chmod +x install_and_run.sh
bash install_and_run.sh
```

**Port already in use**
Edit `app.py` line 82 and change port 5000 to another number

**Issues?** Report them on [GitHub Issues](https://github.com/visit-www/Frcr-examiner/issues)

---

**Questions?** See the full [INSTALLATION.md](INSTALLATION.md) guide in the extracted folder.
