# FRCR Examiner

Medical exam management system for FRCR (Fundamental Recognition of Competence and Readiness) candidates.

## ⚡ Quick Start

### macOS/Linux
```bash
git clone https://github.com/visit-www/Frcr-examiner.git
cd Frcr-examiner
chmod +x start.sh
./start.sh
```
Opens at http://localhost:5000

### Windows
```bash
git clone https://github.com/visit-www/Frcr-examiner.git
cd Frcr-examiner
start.bat
```
Opens at http://localhost:5000

---

## Prerequisites
- **Python 3.9+** (download from https://www.python.org/downloads/)

That's it!

## Features

- 📋 Exam session management
- 👥 Candidate tracking
- 🏥 Medical case management with images
- 💬 Q&A pairs for each case
- 📊 Session analytics
- 💾 Automatic database backups (every 24h)

All data stored locally. Nothing goes to the cloud.

## Project Structure

```
├── app.py                 # Flask application
├── models.py              # Database models (SQLAlchemy)
├── run.py                 # Entry point
├── startup.sh             # Startup script
├── requirements.txt       # Python dependencies
├── templates/             # HTML templates
├── static/                # CSS, JavaScript, images
├── backup_manager.py      # Auto-backup system
├── backup_scheduler.py    # Backup scheduling
└── venv/                  # Virtual environment
```

## Dependencies

- Flask 2.3.3
- SQLAlchemy 2.0.45
- Flask-SQLAlchemy 3.0.5
- APScheduler 3.10.1

## Development

Create virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run in development mode:
```bash
python3 run.py
```

## Database

SQLite database stored in `instance/frcr_examiner.db`

Automatic backups created in `backups/` directory

## License

See LICENSE file for details

## Support

For issues and questions, visit the [GitHub repository](https://github.com/visit-www/Frcr-examiner)
