# FRCR EXAMINER - Quick Reference Card

## ⚡ Quick Start (30 seconds)
```bash
cd /Users/zen/myRepos/projects/FRCR_EXAMINER
./run.sh
# Open: http://localhost:5000
```

## 📁 Key Files

| File | Purpose |
|------|---------|
| `app.py` | Main Flask app (all routes & APIs) |
| `models.py` | Database models (4 tables) |
| `templates/` | HTML pages (5 templates) |
| `static/style.css` | Custom styling |
| `instance/frcr_examiner.db` | SQLite database |
| `requirements.txt` | Python dependencies |
| `run.sh` | Quick start script |

## 🎯 Main Workflow

### Prepare Exam
1. Exam Date + Time → Create Session
2. Packet ID (FORM001) → Create Packet (x4)
3. Case Details → Add Cases (3 per packet)
4. Candidate Names → Register Candidates (x4)

### Start Exam
1. Select Candidate
2. View Packet (auto-selected)
3. Browse Cases
4. View Case Details (grid format)

## 🔌 API Quick Reference

```
POST /api/exam/create          → exam_id, exam_time
POST /api/packet/create        → packet_id, packet_number
POST /api/case/create          → case_number, diagnosis, questions, answers
POST /api/candidate/create     → candidate_name, candidate_number

GET /api/candidates/<exam_id>
GET /api/packet/<packet_id>/cases
GET /api/case/<case_id>
```

## 🗄️ Database Tables

```
ExamSession
├─ id, exam_date, exam_time
├─ packets []
└─ candidates []

Packet
├─ id, exam_id, packet_number, packet_id
└─ cases []

Case
├─ id, packet_id, case_number
├─ diagnosis, questions, answers, discussion
└─ packet_id (FK)

Candidate
├─ id, exam_id, candidate_name
└─ candidate_number, packet_number
```

## 🚀 Commands

```bash
# Start application
./run.sh

# OR manual:
source venv/bin/activate
python app.py

# Load sample data
python load_sample_data.py

# Stop server
Ctrl+C

# Deactivate venv
deactivate

# Delete & recreate database
rm instance/frcr_examiner.db && python app.py
```

## 🌐 URLs

| URL | Description |
|-----|-------------|
| http://localhost:5000 | Home page (tabs) |
| http://localhost:5000/prepare-exam | Exam prep |
| http://localhost:5000/start-exam | Exam start |

## 📊 Data Structure

```
Exam Session (1)
├── Packet 1 (FORM001)
│   ├── Case 1: Diagnosis, Q&A, Discussion
│   ├── Case 2: Diagnosis, Q&A, Discussion
│   └── Case 3: Diagnosis, Q&A, Discussion
├── Packet 2 (FORM002) ... [similar]
├── Packet 3 (FORM003) ... [similar]
├── Packet 4 (FORM004) ... [similar]
└── Candidates (4)
    ├── Candidate A → Packet 1
    ├── Candidate B → Packet 2
    ├── Candidate C → Packet 3
    └── Candidate D → Packet 4
```

## 🔧 Configuration

**To change port:**
Edit `app.py` last line: `port=5001`

**To add more candidates:**
Edit `templates/index.html`: Add options 5, 6, 7...

**To disable debug mode:**
Edit `app.py` last line: `debug=False`

## 💡 Common Tasks

### Check Database
```bash
python -c "
from app import app
from models import ExamSession, Packet, Case, Candidate
with app.app_context():
    print(f'Exams: {ExamSession.query.count()}')
    print(f'Packets: {Packet.query.count()}')
    print(f'Cases: {Case.query.count()}')
    print(f'Candidates: {Candidate.query.count()}')
"
```

### Backup Database
```bash
cp instance/frcr_examiner.db instance/frcr_examiner_backup.db
```

### Clear Database
```bash
rm instance/frcr_examiner.db
python app.py  # Recreates empty DB
```

## 📱 Browser Support
- ✅ Chrome/Edge
- ✅ Firefox
- ✅ Safari
- ⚠️ IE11 (not tested)

## 🐛 Troubleshooting

| Error | Fix |
|-------|-----|
| Port in use | `lsof -i :5000` → kill PID |
| Import error | `pip install -r requirements.txt` |
| DB corrupted | `rm instance/frcr_examiner.db` |
| Venv broken | `deactivate && rm -rf venv` → recreate |

## 📚 Documentation

- **README.md** - User guide
- **SETUP.md** - Detailed setup & config
- **PROJECT_OVERVIEW.md** - Complete documentation
- This file - Quick reference

## ✨ Features at a Glance

✅ Flask backend with SQLAlchemy ORM
✅ Bootstrap 5 responsive UI
✅ SQLite local database
✅ 4 interconnected data models
✅ 5 HTML templates
✅ RESTful API endpoints
✅ Exam prep & exam execution workflows
✅ Dynamic form creation
✅ AJAX data loading
✅ Grid format case display

## 🎓 Tech Stack Summary

- **Backend**: Flask 2.3.3
- **Database**: SQLite3
- **ORM**: SQLAlchemy 2.0.21
- **Frontend**: Bootstrap 5.3
- **Scripting**: Vanilla JavaScript
- **Python**: 3.8+

---

**Need help?** Check README.md, SETUP.md, or PROJECT_OVERVIEW.md
