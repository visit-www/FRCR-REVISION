# FRCR EXAMINER - Setup and Run Guide

## Project Overview
FRCR Examiner is a Flask-based web application for managing FRCR (Fellowship of Royal College of Radiologists) exam preparation and recording exam results for candidates.

### Features
- **Prepare for Exam**: Create exam sessions, manage 4 packets (FORM IDs), add 3 cases per packet with questions, answers, and discussions
- **Start Exam**: Select candidate (1-4), view corresponding packet, navigate through cases, view case details in grid format
- **Responsive Design**: Bootstrap 5 UI, works on all screen sizes
- **SQLite Database**: Simple local database for data persistence

## Project Structure
```
FRCR_EXAMINER/
├── app.py                 # Main Flask application
├── models.py             # Database models
├── requirements.txt      # Python dependencies
├── templates/            # HTML templates
│   ├── base.html        # Base template with navbar
│   ├── index.html       # Home page with tabs
│   ├── start_exam.html  # Select candidate page
│   ├── view_packet.html # View cases in packet
│   └── view_case.html   # View individual case details
├── static/              # Static files
│   └── style.css        # Custom styles
└── instance/            # Instance folder (database stored here)
```

## Installation & Setup

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Step 1: Create Virtual Environment
```bash
cd /Users/zen/myRepos/projects/FRCR_EXAMINER
python3 -m venv venv
source venv/bin/activate
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Run the Application
```bash
python app.py
```

The application will start on `http://localhost:5000`

## Usage Guide

### 1. Prepare for Exam Tab
1. Enter **Exam Date** and **Exam Time**
2. Click **Create Exam Session**
3. Click **Add Packet** to create packets (1-4)
   - Enter Packet Number (1-4)
   - Enter Packet ID (e.g., FORM001, FORM002)
   - Click **Create Packet**
4. For each packet, click **Add Case** to add 3 cases:
   - Case Number (1-3)
   - Diagnosis (text)
   - Questions (text)
   - Answers (text)
   - Discussion/Comments (optional)
5. Click **Add Candidate** to register candidates (1-4):
   - Candidate Name
   - Candidate Number (1-4) - auto-maps to packet number

### 2. Start Exam Tab
1. Click **Start Exam Session**
2. Select a candidate from the list
3. Click **View Packet** to see cases in that candidate's packet
4. Click **View Case** to see full case details in grid format
5. Review case diagnosis, questions, answers, and discussion

## Database
- SQLite database is automatically created at: `instance/frcr_examiner.db`
- Database includes tables for:
  - ExamSession
  - Packet
  - Case
  - Candidate

## Stopping the Application
Press `Ctrl+C` in the terminal running the Flask app

## Deactivating Virtual Environment
```bash
deactivate
```

## Dependencies
- **Flask 2.3.3**: Web framework
- **Flask-SQLAlchemy 3.0.5**: ORM for database
- **SQLAlchemy 2.0.21**: Database toolkit
- **Bootstrap 5.3**: CSS framework (loaded via CDN)

## Notes
- The app runs in **debug mode** for development (auto-reload on code changes)
- Database file persists between sessions
- Each exam session can have multiple packets and candidates
- Candidate numbers 1-4 automatically map to packet numbers 1-4

## Troubleshooting
- If port 5000 is already in use, modify `app.py` line with `port=5000` to another port (e.g., 5001)
- If database issues occur, delete `instance/frcr_examiner.db` and restart the app
- Ensure virtual environment is activated before running the app

---
**Happy Exam Preparation!**
