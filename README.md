# FRCR Examiner Tool

A professional examination management system designed for FRCR (Fellowship of the Royal College of Radiologists) viva exams. This application helps examiners prepare, organize, and conduct candidate examinations with medical images, case discussions, and Q&A pairs.

## 🚀 Quick Install (For End Users)

**Download the latest release for your operating system:**

[![Download for Windows](https://img.shields.io/badge/Download-Windows-blue?style=for-the-badge&logo=windows)](https://github.com/visit-www/Frcr-examiner/releases/latest)
[![Download for macOS](https://img.shields.io/badge/Download-macOS-lightgrey?style=for-the-badge&logo=apple)](https://github.com/visit-www/Frcr-examiner/releases/latest)

### Installation Steps

1. **Download** the appropriate package for your system
2. **Extract** the ZIP file
3. **Run the installer** (see guides below)
4. **Launch** the app from your desktop or applications folder

📖 **Detailed guides:** See [INSTALLATION_GUIDE.md](dist/INSTALLATION_GUIDE.md) or [QUICK_START.md](dist/QUICK_START.md)

---

## Features

### 📋 Core Functionality
- **Exam Session Management**: Create and manage multiple exam sessions with dates and times
- **Candidate Management**: Register candidates with unique identifiers and packet assignments
- **Case Management**: Organize medical cases with images, diagnoses, and discussion points
- **Q&A Pairs**: Add and manage question-answer pairs for each case
- **Image Handling**: Upload, manage, and attach medical images to cases
- **Exam Workflow**: Guide candidates through structured examination sessions

### 🎯 Key Features
- Intuitive web-based interface
- Responsive Bootstrap 5 design
- Session-based candidate organization
- Rich text editor for case discussions
- Image annotation and description capabilities
- Automatic database backups
- Admin dashboard for system management

## Technology Stack

- **Backend**: Flask (Python)
- **Database**: PostgreSQL (production) / SQLite (development)
- **Frontend**: Bootstrap 5, Vanilla JavaScript
- **ORM**: SQLAlchemy
- **Server**: WSGI-compatible (Railway/Gunicorn for production)

## Quick Start

### Prerequisites
- Python 3.7+
- PostgreSQL (production) or SQLite (development)
- pip (Python package manager)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/visit-www/Frcr-examiner.git
   cd Frcr-examiner
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure database**
   - Development: SQLite is configured by default
   - Production: Set `DATABASE_URL` environment variable

5. **Run the application**
   ```bash
   flask run
   ```
   Visit `http://localhost:5000` in your browser.

## Usage Guide

### Getting Started
1. **Navigate to Home**: Click "Home" in the navigation bar to access the dashboard
2. **Create Session**: Click "Manage Sessions" to create a new exam session
3. **Set Details**: Provide session name, exam date, and time
4. **Manage Session**: Click "Manage Session" button to organize that session

### Managing Sessions
From the Manage Session page, you can:
- **Add Packets**: Create exam packets containing medical cases
- **Add Cases**: Add medical cases to packets with images and descriptions
- **Add Candidates**: Register exam candidates for the session
- **Add Q&A Pairs**: Create question-answer pairs for discussion

### Taking an Exam
1. Navigate to **Exam** in the navigation bar
2. Select an exam session
3. Choose a candidate
4. View their packet and cases
5. Review images, diagnoses, and discussion points
6. Discuss and evaluate the candidate's responses

### Admin Functions
- Access **Admin** section for system management
- View and manage backups
- Monitor system status

## Project Structure

```
FRCR_EXAMINER/
├── app.py                    # Main Flask application
├── models.py                 # Database models
├── requirements.txt          # Python dependencies
├── templates/
│   ├── base.html            # Base template with navigation
│   ├── dashboard.html        # Home dashboard
│   ├── setup_sessions.html   # Session management
│   ├── manage_session.html   # Session detail management
│   ├── start_exam.html       # Exam start workflow
│   ├── view_case.html        # Case viewing and review
│   ├── edit_case.html        # Case editing interface
│   └── admin_dashboard.html  # Admin panel
├── static/
│   ├── style.css            # Application styles
│   └── edit-case-modal.js   # Case editing JavaScript
├── instance/                 # Instance-specific files (database)
└── backups/                  # Automatic database backups
```

## API Endpoints

### Session Management
- `GET /api/exam/sessions` - List all sessions
- `POST /api/exam/create` - Create new session
- `GET /api/session/{id}/packets` - Get packets in session

### Candidate Management
- `GET /api/candidates/{session_id}` - List candidates in session
- `POST /api/candidate/create` - Create new candidate
- `DELETE /api/candidate/{id}` - Delete candidate

### Case Management
- `GET /api/case/{id}` - Get case details
- `PUT /api/case/{id}` - Update case
- `GET /api/case/{id}/qa-pairs` - Get Q&A pairs for case
- `GET /api/case/{id}/images` - Get case images

### Image Management
- `POST /api/case-image/upload` - Upload image
- `DELETE /api/case-image/{id}` - Delete image
- `PUT /api/case-image/{id}` - Update image description

## Configuration

### Environment Variables
- `DATABASE_URL` - Database connection string (production)
- `FLASK_ENV` - Set to `development` or `production`
- `SECRET_KEY` - Flask secret key for sessions

### Database
- **Development**: SQLite (instance/frcr_examiner.db)
- **Production**: PostgreSQL via `DATABASE_URL`

## Backup & Recovery

The application includes automatic backup functionality:
- Backups are created every 24 hours
- Old backups are automatically cleaned up
- Manual backups can be initiated from Admin panel
- Stored in `backups/` directory

## Development

### Setting up for Development
```bash
# Install dev dependencies
pip install -r requirements.txt

# Run in debug mode
export FLASK_ENV=development
flask run
```

### Database Migrations
Models are defined in `models.py`. For schema changes:
1. Update model definitions
2. Restart Flask (will create new tables if needed)
3. For production, use migration tools

## Deployment

The application is designed for easy deployment on:
- **Railway**: Configure `DATABASE_URL` and deploy
- **Heroku**: Use Procfile configuration
- **Traditional VPS**: Use gunicorn with nginx reverse proxy

### Production Checklist
- [ ] Set `FLASK_ENV=production`
- [ ] Configure `DATABASE_URL` for PostgreSQL
- [ ] Set strong `SECRET_KEY`
- [ ] Enable HTTPS
- [ ] Set up automated backups
- [ ] Configure email notifications

## Troubleshooting

### Common Issues

**Port 5000 already in use**
```bash
# Use different port
flask run --port 5001
```

**Database connection errors**
- Verify DATABASE_URL format
- Check database credentials
- Ensure database server is running

**Image upload issues**
- Check file permissions on upload directory
- Verify image format is supported
- Check available disk space

## Contributing

1. Create a feature branch
2. Make your changes
3. Test thoroughly
4. Commit with clear messages
5. Push and create pull request

## License

This project is for educational and professional use in medical training environments.

## Support & Contact

For issues, suggestions, or support:
- Email: lotusheart2016@gmail.com
- Author: Dr Gaurav S.P Gupta, MBBS, MD, FRCR

## Changelog

### Version 1.0.0
- Initial release
- Complete session and candidate management
- Image upload and management
- Exam workflow
- Automatic backups
- Admin dashboard
- Responsive Bootstrap 5 UI
