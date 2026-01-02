# FRCR EXAMINER - Complete Project Documentation

## 📋 Project Summary

**FRCR EXAMINER** is a comprehensive Flask-based web application designed to help examiners prepare for and conduct FRCR (Fellowship of Royal College of Radiologists) examinations. The tool streamlines the management of exam packets, cases, and candidate assessments.

## 🎯 Key Features

### 1. Prepare for Exam Tab
- **Exam Session Creation**: Enter exam date and time
- **Packet Management**: Create up to 4 packets with custom IDs (FORM001, FORM002, etc.)
- **Case Management**: Add up to 3 cases per packet with:
  - Case number
  - Diagnosis (detailed text)
  - Questions (exam questions)
  - Answers (model answers)
  - Discussion/Comments (clinical discussion)
- **Candidate Registration**: Register up to 4 candidates with auto-mapping to packets

### 2. Start Exam Tab
- **Candidate Selection**: Browse and select candidates
- **Packet Navigation**: View corresponding packet for selected candidate
- **Case Review**: Navigate through cases in grid format
- **Detailed View**: See full case information (diagnosis, questions, answers, discussion)

## 🗂️ Project Structure

```
FRCR_EXAMINER/
├── app.py                      # Flask application (318 lines)
├── models.py                   # Database models (65 lines)
├── requirements.txt            # Python dependencies
├── load_sample_data.py        # Sample data loader for testing
├── run.sh                      # Quick start script
├── README.md                   # User guide
├── SETUP.md                    # Setup instructions
├── .gitignore                  # Git ignore rules
│
├── templates/                  # HTML templates
│   ├── base.html              # Base layout with navbar
│   ├── index.html             # Home page (prepare + start tabs)
│   ├── start_exam.html        # Candidate selection
│   ├── view_packet.html       # Cases list
│   └── view_case.html         # Case details grid
│
├── static/                     # Static files
│   └── style.css              # Custom Bootstrap 5 styling
│
└── instance/                   # Instance folder (created at runtime)
    └── frcr_examiner.db       # SQLite database (auto-created)
```

## 🔧 Technology Stack

### Backend
- **Framework**: Flask 2.3.3
- **Database**: SQLite (via Flask-SQLAlchemy 3.0.5)
- **ORM**: SQLAlchemy 2.0.21
- **Python**: 3.8+

### Frontend
- **CSS Framework**: Bootstrap 5.3 (CDN)
- **JavaScript**: Vanilla JS (no frameworks)
- **Templating**: Jinja2 (Flask built-in)

### Tools
- **Package Manager**: pip
- **Virtual Environment**: venv
- **Database**: SQLite3

## 📊 Database Schema

### ExamSession Table
```
- id (Primary Key)
- exam_date (Date)
- exam_time (String)
- created_at (DateTime)
- packets (Relationship → Packet)
- candidates (Relationship → Candidate)
```

### Packet Table
```
- id (Primary Key)
- exam_id (Foreign Key → ExamSession)
- packet_number (Integer: 1-4)
- packet_id (String: FORM001-004)
- cases (Relationship → Case)
```

### Case Table
```
- id (Primary Key)
- packet_id (Foreign Key → Packet)
- case_number (Integer: 1-3)
- diagnosis (Text)
- questions (Text)
- answers (Text)
- discussion (Text, optional)
```

### Candidate Table
```
- id (Primary Key)
- exam_id (Foreign Key → ExamSession)
- candidate_name (String)
- candidate_number (Integer: 1-4)
- packet_number (Integer: 1-4, auto-mapped)
```

## 🚀 Getting Started

### Installation (3 steps)
```bash
# 1. Navigate to project
cd /Users/zen/myRepos/projects/FRCR_EXAMINER

# 2. Quick start with script (Mac)
./run.sh

# OR manual setup:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

### First Run
1. Open http://localhost:5000 in your browser
2. Go to "Prepare for Exam" tab
3. Enter exam date and time
4. Click "Create Exam Session"
5. Add packets (1-4) with custom IDs
6. Add cases (1-3 per packet) with details
7. Register candidates (1-4)

### Load Sample Data (Optional)
```bash
python load_sample_data.py
```
This creates demo data for testing without manual entry.

## 📡 API Endpoints

### Exam Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/exam/create` | POST | Create new exam session |
| `/api/packet/create` | POST | Create packet |
| `/api/case/create` | POST | Create case |
| `/api/candidate/create` | POST | Create candidate |

### Data Retrieval
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/candidates/<exam_id>` | GET | List all candidates |
| `/api/packet/<packet_id>/cases` | GET | List cases in packet |
| `/api/case/<case_id>` | GET | Get case JSON data |

### Page Routes
| Route | Description |
|-------|-------------|
| `/` | Home page (main tab interface) |
| `/prepare-exam` | Exam preparation page |
| `/start-exam` | Candidate selection |
| `/view-packet/<id>` | Cases in packet |
| `/view-case/<id>` | Case details |

## 🎨 UI Components

### Navigation
- Dark blue navbar with "FRCR Examiner Tool" branding
- Quick access to home from any page

### Tabs
- **Prepare for Exam**: Forms for entering exam and case data
- **Start Exam**: Candidate selection and exam navigation

### Forms
- Responsive input fields with Bootstrap styling
- Real-time validation and feedback
- Clear section organization

### Case Display
- Grid format with labeled cells
- Read-only presentation for exam viewing
- Expandable text areas for long content
- Clean, professional layout

## 🔄 Workflow Examples

### Examiner Setup Workflow
```
1. Open app → Home Page
2. Click "Prepare for Exam" tab
3. Enter exam date & time → Create Session
4. Add Packet 1 (FORM001)
   ├─ Add Case 1: Diagnosis, Q&A, Discussion
   ├─ Add Case 2: Diagnosis, Q&A, Discussion
   └─ Add Case 3: Diagnosis, Q&A, Discussion
5. Repeat for Packets 2-4
6. Add Candidate A, B, C, D
7. Setup complete!
```

### Exam Execution Workflow
```
1. Open app → Home Page
2. Click "Start Exam Session"
3. Select Candidate A
4. View Packet 1 (auto-selected for Candidate A)
5. Review Case 1 (diagnosis, questions, answers, discussion)
6. Navigate to Case 2, Case 3
7. Move to next candidate
```

## 💾 Data Persistence

- **Database File**: `instance/frcr_examiner.db`
- **Auto-creation**: Database and tables created on first run
- **Data Retention**: All data persists between sessions
- **Backup**: Manual backup by copying `.db` file

## ⚙️ Configuration

### Default Settings
- **Host**: localhost (127.0.0.1)
- **Port**: 5000
- **Debug Mode**: Enabled (development)
- **Database**: SQLite (local)

### Customization
Edit `app.py` for:
- Port number: Line with `port=5000`
- Debug mode: Line with `debug=True`
- Host: Line with `host='localhost'`
- Secret key: Change `SECRET_KEY` value

## 🧪 Testing

### Manual Testing Checklist
- [ ] Create exam session
- [ ] Create packet with custom ID
- [ ] Create case with all fields
- [ ] Register candidates
- [ ] View candidates list
- [ ] Select candidate → view packet
- [ ] View individual cases
- [ ] Test responsive design (desktop/mobile)
- [ ] Verify data persistence (restart app)

### Using Sample Data
```bash
python load_sample_data.py
# Navigate to app and see pre-populated data
```

## 📱 Responsive Design

- **Desktop**: Full-width layout, side-by-side columns
- **Tablet**: Stacked layout, readable text
- **Mobile**: Single column, touch-friendly buttons
- **All Screens**: Bootstrap 5 responsive grid system

## 🔒 Security Notes

### Current Setup (Development)
- No authentication
- Suitable for local network only
- Debug mode enabled
- Basic secret key

### For Production
- Implement user authentication
- Change SECRET_KEY to random value
- Set debug=False
- Use environment variables
- Add HTTPS/SSL
- Database backup strategy

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Port 5000 in use | Change port in app.py, or kill process: `lsof -i :5000` |
| Database corrupted | Delete `instance/frcr_examiner.db`, restart app |
| Virtual env issues | Deactivate, delete venv/, recreate and reinstall |
| Import errors | Run `pip install --upgrade -r requirements.txt` |
| Page not loading | Check browser console (F12) for JavaScript errors |
| Data not saving | Check browser network tab (F12) for failed requests |

## 📚 Dependencies

```
Flask==2.3.3
Flask-SQLAlchemy==3.0.5
SQLAlchemy==2.0.21
python-dotenv==1.0.0
Werkzeug==2.3.7
Bootstrap 5.3 (CDN - no installation needed)
```

Install with: `pip install -r requirements.txt`

## 🎓 Educational Notes

This project demonstrates:
- **Full-stack web development**: Flask backend + Bootstrap frontend
- **Database design**: Relational model with 4 interconnected tables
- **RESTful API**: JSON endpoints for CRUD operations
- **Form handling**: Dynamic form creation and validation
- **Bootstrap responsive design**: Mobile-first approach
- **JavaScript AJAX**: Asynchronous data loading

## 📞 Support & Maintenance

### Regular Backups
```bash
cp instance/frcr_examiner.db backups/frcr_examiner_backup_$(date +%Y%m%d).db
```

### Database Statistics
```bash
python -c "
from app import app, db
from models import ExamSession, Packet, Case, Candidate
with app.app_context():
    print(f'Exams: {ExamSession.query.count()}')
    print(f'Packets: {Packet.query.count()}')
    print(f'Cases: {Case.query.count()}')
    print(f'Candidates: {Candidate.query.count()}')
"
```

### Update Dependencies
```bash
pip install --upgrade -r requirements.txt
```

## 📝 Version Info

- **Created**: January 2, 2026
- **Framework**: Flask 2.3.3
- **Python**: 3.8+
- **Database**: SQLite3
- **UI Framework**: Bootstrap 5.3

## 🎉 Ready to Use!

Your FRCR Examiner application is fully configured and ready to run. All files are in place, dependencies are specified, and sample data can be loaded for testing.

**Start the application with:**
```bash
./run.sh
```

**Happy Exam Preparation!** 🏥📋✅
