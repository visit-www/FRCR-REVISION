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
- 💾 **NEW! Web-based backup system** with download & restore
- ⏰ **NEW! Automatic 24-hour backup reminders**
- 🔄 **NEW! One-click database restore**

All data stored locally or in your database. You control your backups.

## 🆕 Backup System (v1.0)

The app now includes a comprehensive web-based backup and restore system:

- **Download Backups**: One-click download of your entire database as JSON
- **Auto Reminders**: Get notified every 24 hours to backup your data
- **Easy Restore**: Upload any backup file to restore your database
- **Local Management**: Python script to manage your downloaded backups (keep last 5)

📖 **Full documentation**: See [BACKUP_SYSTEM.md](BACKUP_SYSTEM.md) for complete guide

**Quick Access**: Admin → Web Backup Manager

## Project Structure

```
├── app.py                     # Flask application
├── models.py                  # Database models (SQLAlchemy)
├── backup_routes.py           # NEW! Web backup API endpoints
├── manage_local_backups.py    # NEW! Local backup manager script
├── run.py                     # Entry point
├── startup.sh                 # Startup script
├── requirements.txt           # Python dependencies
├── templates/                 # HTML templates
│   └── backup_manager.html    # NEW! Backup manager page
├── static/                    # CSS, JavaScript, images
│   └── backup-reminder.js     # NEW! Backup reminder system
├── backup_manager.py          # Legacy auto-backup system
├── backup_scheduler.py        # Legacy backup scheduling
└── venv/                      # Virtual environment
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

- **Local**: SQLite database stored in `instance/frcr_examiner.db`
- **Production**: PostgreSQL via Supabase (Vercel deployment)
- **Backups**: Web-based JSON backups (download to your computer)
- **Legacy Backups**: Old SQLite backups in `backups/` directory

### Managing Backups

**Web Interface** (Recommended):
1. Go to Admin → Web Backup Manager
2. Click "Download Backup Now"
3. Store safely on your computer

**Command Line** (Optional):
```bash
# Manage your downloaded backups
python manage_local_backups.py ~/Downloads

# Keep only last 5 backups
python manage_local_backups.py ~/Downloads cleanup

# Verify a backup file
python manage_local_backups.py ~/Downloads/backup.json verify
```

See [BACKUP_SYSTEM.md](BACKUP_SYSTEM.md) for complete documentation.

## License

See LICENSE file for details

## Support

For issues and questions, visit the [GitHub repository](https://github.com/visit-www/Frcr-examiner)
