# FRCR Examiner

A comprehensive web application for managing FRCR (Fellowship of the Royal College of Radiologists) examination sessions, medical cases, and candidate assessments.

## 🌐 Production Deployment

**Live Application**: [https://frcr-examiner.vercel.app](https://frcr-examiner.vercel.app)

## ✨ Features

### Exam Management
- Create and manage multiple examination sessions
- Organize cases into packets for structured delivery
- Track exam dates, times, and session metadata

### Case Management  
- Add detailed medical cases with diagnoses and discussions
- Attach multiple images to each case with descriptions
- Create question-and-answer pairs for each case
- Rich text support in discussions (HTML, links, formatting)
- Responsive grey-themed Q&A table layout (desktop/mobile optimized)

### Candidate Tracking
- Register candidates with unique identifiers
- Assign packet numbers to candidates
- View candidate-specific case packets

### User Authentication
- Secure registration and login system
- User data isolation (each user sees only their own data)
- Admin dashboard for first registered user
- Profile management and password recovery

### Backup & Restore
- Download complete database backups as JSON
- Upload and restore from previous backups
- 24-hour automatic backup reminders
- Admin-only access for data management

### Image Viewer
- Full-screen image viewer with modal display
- Keyboard navigation (←/→ arrow keys)
- Click-based navigation controls
- Image counter and descriptions
- Supports multiple images per case

## 🛠️ Technology Stack

- **Backend**: Flask 2.3.3, Python 3.9+
- **Database**: PostgreSQL (Supabase) for production, SQLite for local development
- **ORM**: SQLAlchemy 2.0.45, Flask-SQLAlchemy 3.0.5
- **Authentication**: Flask-Login 0.6.2, Werkzeug password hashing
- **Frontend**: Bootstrap 5, vanilla JavaScript
- **Deployment**: Vercel serverless functions
- **Session Management**: Flask sessions with secure cookies

## 📦 Project Structure

```
├── api/
│   └── index.py              # Vercel serverless entry point
├── app.py                     # Main Flask application
├── auth.py                    # Authentication routes and logic
├── backup_routes.py          # Backup/restore API endpoints
├── models.py                  # SQLAlchemy database models
├── requirements.txt           # Python dependencies
├── vercel.json               # Vercel deployment configuration
├── static/
│   ├── config.js             # API configuration
│   ├── style.css              # Custom styles
│   ├── edit-case-modal.js    # Case editing functionality
│   └── images/               # Application images
├── templates/                 # HTML templates (Jinja2)
└── instance/                  # Local SQLite database (dev only)
```

## 🚀 Local Development

### Prerequisites
- Python 3.9 or higher
- pip (Python package installer)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/visit-www/Frcr-examiner.git
   cd Frcr-examiner
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables** (optional for local development)
   ```bash
   # .env.local
   DATABASE_URL=postgresql://...  # Optional: use PostgreSQL instead of SQLite
   SECRET_KEY=your-secret-key     # Optional: defaults to dev key
   ```

5. **Run the application**
   ```bash
   python3 app.py
   ```

6. **Access the application**
   - Open browser to [http://localhost:5000](http://localhost:5000)
   - Register a new account (first user becomes admin)

## 🌍 Production Deployment

### Vercel Deployment

1. **Push to GitHub**
   ```bash
   git push origin main
   ```

2. **Connect to Vercel**
   - Import your GitHub repository in Vercel dashboard
   - Configure environment variables:
     - `DATABASE_URL`: PostgreSQL connection string (Supabase recommended)
     - `SECRET_KEY`: Strong random key for session encryption
     - `PYTHON_VERSION`: 3.9

3. **Deploy**
   - Vercel automatically deploys on every push to main branch
   - Access your app at `https://your-project.vercel.app`

### Database Setup (Production)

The application uses Supabase PostgreSQL for production:

1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Get your PostgreSQL connection string
3. Add to Vercel environment variables as `DATABASE_URL`
4. Database tables are created automatically on first run

## 🔐 Authentication & Security

- Passwords hashed with Werkzeug's generate_password_hash
- Session-based authentication with Flask-Login
- CSRF protection on all forms
- User data isolation (queries filtered by `user_id`)
- Admin role assigned to first registered user
- Secure password requirements enforced client-side

## 💾 Backup System

### Creating Backups
1. Log in as admin (first registered user)
2. Navigate to Admin Dashboard
3. Click "Download Backup" to save complete database as JSON
4. Store backup file securely

### Restoring Backups
1. Log in as admin
2. Navigate to Backup Manager
3. Upload previously downloaded JSON backup file
4. Confirm overwrite (destructive operation)
5. Database is restored from backup

**Note**: Backups are recommended every 24 hours. The system sends browser notifications as reminders.

## 📚 Database Schema

### Core Models
- **User**: Email, password hash, full name, admin status
- **ExamSession**: Date, time, session name, user relationship
- **Packet**: Packet number/ID, belongs to exam session
- **Case**: Case number, diagnosis, questions, answers, discussion
- **Candidate**: Name, number, assigned packet
- **CaseImage**: Binary image data, filename, type, description
- **Question**: Question text, number, case relationship
- **Answer**: Answer text, number, case relationship

### Relationships
- User → ExamSessions (one-to-many)
- ExamSession → Packets (one-to-many)
- Packet → Cases (one-to-many)  
- ExamSession → Candidates (one-to-many)
- Case → CaseImages (one-to-many)
- Case → Questions (one-to-many)
- Case → Answers (one-to-many)

## 🤝 Contributing

This is a production application. For bug reports or feature requests, please open an issue on GitHub.

## 📄 License

Copyright © 2026. All rights reserved.

## 🆘 Support

For technical support or questions:
- Open an issue on GitHub
- Email: support@example.com

## 🔄 Version History

### v1.2.0 (Current)
- Image viewer with keyboard navigation
- Visual navigation controls for images
- Grey-themed Q&A responsive layouts
- HTML support in discussion fields
- Auto-linkify URLs in discussions
- Production-ready codebase cleanup

### v1.1.0  
- User authentication system
- Multi-user data isolation
- Admin dashboard
- Profile management

### v1.0.0
- Initial release
- Exam session management
- Case and candidate tracking
- Backup/restore system

---

**Built with ❤️ for the medical education community**
