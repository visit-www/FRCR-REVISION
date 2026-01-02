# FRCR EXAMINER - Configuration Guide

## Quick Start (macOS)

### Option 1: Using the Run Script (Easiest)
```bash
cd /Users/zen/myRepos/projects/FRCR_EXAMINER
./run.sh
```
The script will:
- Create a virtual environment (if not exists)
- Install dependencies
- Start the Flask server

### Option 2: Manual Setup
```bash
cd /Users/zen/myRepos/projects/FRCR_EXAMINER

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

## Accessing the Application
- **URL**: http://localhost:5000
- **Port**: 5000 (can be changed in app.py if needed)

## Project Architecture

### Frontend (Templates)
- **base.html**: Navigation bar and layout template
- **index.html**: Home page with "Prepare for Exam" and "Start Exam" tabs
- **start_exam.html**: Candidate selection page
- **view_packet.html**: Cases list for selected candidate
- **view_case.html**: Detailed case information in grid format

### Backend (Flask)
- **app.py**: Main Flask application with all routes and API endpoints
- **models.py**: SQLAlchemy database models
- **requirements.txt**: Python package dependencies

### Database Models
1. **ExamSession**
   - Stores exam date and time
   - Links to multiple packets and candidates

2. **Packet**
   - Packet number (1-4)
   - Packet ID (FORM001, FORM002, etc.)
   - Contains 1-3 cases

3. **Case**
   - Case number (1-3 per packet)
   - Diagnosis, Questions, Answers, Discussion
   - Linked to a packet

4. **Candidate**
   - Candidate name and number (1-4)
   - Packet number (auto-mapped: candidate 1 → packet 1, etc.)

## Database Location
- **File**: `/Users/zen/myRepos/projects/FRCR_EXAMINER/instance/frcr_examiner.db`
- **Type**: SQLite3
- **Auto-created**: Yes (on first run)

## API Endpoints

### Exam Management
- `POST /api/exam/create` - Create new exam session
- `POST /api/packet/create` - Create packet
- `POST /api/case/create` - Create case
- `POST /api/candidate/create` - Create candidate

### Data Retrieval
- `GET /api/candidates/<exam_id>` - Get all candidates for exam
- `GET /api/packet/<packet_id>/cases` - Get cases in packet
- `GET /api/case/<case_id>` - Get case details as JSON

### Page Routes
- `GET /` - Home page
- `GET /prepare-exam` - Prepare exam page
- `GET /start-exam` - Select candidate page
- `GET /select-candidate` - Candidate selection
- `GET /view-packet/<candidate_id>` - View packet cases
- `GET /view-case/<case_id>` - View case details

## Customization

### Change Port
Edit **app.py** (last line):
```python
if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5001)  # Change 5000 to 5001
```

### Add More Candidates
Modify the candidate selection in **templates/index.html**:
```html
<option value="5">5</option>
<option value="6">6</option>
```
Also update the HTML for `candidateNumber` select options.

### Change Colors
Edit **static/style.css** to modify color scheme:
```css
:root {
    --primary-color: #0d6efd;
    --success-color: #198754;
    --danger-color: #dc3545;
}
```

### Disable Debug Mode (Production)
Edit **app.py** last line:
```python
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
```

## Virtual Environment Management

### Activate
```bash
source venv/bin/activate
```

### Deactivate
```bash
deactivate
```

### List Installed Packages
```bash
pip list
```

### Upgrade Package
```bash
pip install --upgrade Flask
```

## Troubleshooting

### Port Already in Use
```bash
lsof -i :5000  # Find what's using port 5000
kill -9 <PID>   # Kill the process
```

### Database Issues
```bash
rm -f instance/frcr_examiner.db  # Delete database
python app.py                     # Restart to recreate
```

### Import Errors
```bash
pip install --upgrade -r requirements.txt
```

### Virtual Environment Not Working
```bash
deactivate
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Browser Compatibility
- Chrome/Edge: ✅ Full support
- Firefox: ✅ Full support
- Safari: ✅ Full support
- IE11: ⚠️ Not tested (Bootstrap 5 requires modern browsers)

## Performance Notes
- SQLite is suitable for small to medium datasets
- Database is stored locally (no cloud sync)
- All data is persistent between sessions
- App supports concurrent browser sessions

## Security Notes (Development)
- `SECRET_KEY` should be changed for production
- Debug mode is enabled (disable in production)
- Database contains exam data - backup regularly
- No authentication implemented (for local use)

## Backup Data
```bash
cp instance/frcr_examiner.db instance/frcr_examiner_backup.db
```

## Stop Server
Press `Ctrl+C` in the terminal running the Flask app

---
For more information, see README.md
