# FRCR Revision

A comprehensive exam preparation platform for FRCR (Fellowship of the Royal College of Radiologists) candidates. Practice with real cases, generate AI-powered content, explore TNM staging, and build confidence for exam success.

## 🌐 Live Application

**Production**: [https://frcr-revision.vercel.app](https://frcr-revision.vercel.app)

---

## ✨ Key Features

### 📚 Case Management
- Create and manage medical cases with diagnoses and discussions
- Attach multiple images via Cloudinary
- Rich text editor with TinyMCE
- Question & answer pairs for each case

### 🤖 AI-Powered Features
- **Case Generation**: Auto-generate preliminary case data from diagnoses
- **TNM Intelligence**: RAG-based AJCC TNM staging summaries
- **Reference Finder**: Search PubMed, Crossref, Radiopaedia

### 🏥 AJCC TNM Staging
- Complete AJCC 8th Edition staging data
- Interactive TNM viewers (student & admin)
- Intelligent staging summaries with images
- Quick reference tables

### 📝 Study Tools
- Personal notes and highlights on cases
- Anki flashcard integration
- PubMed article search
- TCIA imaging datasets

### 👥 User Management
- Role-based access (Admin, Content Manager, Student)
- Secure authentication with Flask-Login
- Profile management

### 💾 Backup System
- Complete JSON export/import
- AJCC data backup
- 24-hour backup reminders

---

## 🛠️ Technology Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Flask 2.3.3, Python 3.9+ |
| **Database** | PostgreSQL (Neon), SQLite (dev) |
| **ORM** | SQLAlchemy 2.0, Flask-Migrate |
| **AI** | Claude API (Anthropic) |
| **Frontend** | Bootstrap 5, TinyMCE, Vanilla JS |
| **Deployment** | Vercel Serverless |
| **Images** | Cloudinary |

---

## 📁 Project Structure

```
FRCR_REVISION/
├── app.py                 # Flask application
├── models.py              # Database models
├── ai_prelim.py           # AI case generation
├── ai_tnm.py              # TNM intelligence
├── ajcc_tnm/              # AJCC TNM module
├── templates/             # HTML templates
├── static/                # CSS, JS, images
├── docs/                  # Documentation
│   ├── STYLE_GUIDE.md     # Brand colors & styles
│   └── APP_STRUCTURE.md   # Full architecture
├── scripts/utilities/     # Maintenance scripts
└── migrations/            # Database migrations
```

See [docs/APP_STRUCTURE.md](docs/APP_STRUCTURE.md) for detailed architecture.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- pip

### Local Development

```bash
# Clone repository
git clone https://github.com/visit-www/FRCR-REVISION.git
cd FRCR-REVISION

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run application
flask run
```

Access at [http://localhost:5000](http://localhost:5000)

### Auto-Initialization

On first run, the app automatically:

1. **Seeds AJCC Data**: Creates 15 body sections and 23 common disease sites for TNM staging
2. **Creates Superadmin**: If no superadmin exists, creates one with a secure random password

```
============================================================
[ADMIN] SUPERADMIN ACCOUNT CREATED
============================================================
  Email:    lotusheart2016@gmail.com
  Password: [random-secure-password]
============================================================
  ⚠️  SAVE THIS PASSWORD NOW - IT WILL NOT BE SHOWN AGAIN!
  ⚠️  Change this password immediately after first login.
============================================================
```

**Important**: The superadmin password is only displayed once in the console. Save it immediately!

### Environment Variables

```bash
# Required for production
SECRET_KEY=your-secret-key
DATABASE_POSTGRES_URL_NON_POOLING=postgresql://...
CLAUDE_API_KEY=sk-ant-...
CLOUDINARY_URL=cloudinary://...

# Email (password recovery)
RESEND_API_KEY=re_xxxxxxxxx
```

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Session encryption key |
| `DATABASE_POSTGRES_URL_NON_POOLING` | Production | Neon PostgreSQL URL |
| `CLAUDE_API_KEY` | Yes | Anthropic Claude API key |
| `CLOUDINARY_URL` | Yes | Image upload service |
| `RESEND_API_KEY` | Yes | Email service (resend.com) |
| `EMAIL_FROM` | No | Sender email (default: onboarding@resend.dev) |
| `APP_URL` | No | App URL for email links |

---

## 🎨 Brand Colors

| Color | Hex | Usage |
|-------|-----|-------|
| Peachy Orange | `#e96304` | Primary actions |
| Soft Green | `#a8d5ba` | Success states |
| Teal Blue | `#5E899E` | Headers, neutral |
| Dark Text | `#2c3e50` | Primary text |

See [docs/STYLE_GUIDE.md](docs/STYLE_GUIDE.md) for complete style reference.

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [STYLE_GUIDE.md](docs/STYLE_GUIDE.md) | Brand colors, button styles, typography |
| [APP_STRUCTURE.md](docs/APP_STRUCTURE.md) | Architecture, modules, API endpoints |
| [AI_INTEGRATION_REFERENCE.md](docs/AI_INTEGRATION_REFERENCE.md) | Claude API integration |

---

## 🔧 Utility Scripts

Located in `scripts/utilities/`:

| Script | Purpose |
|--------|---------|
| `init_database.py` | Initialize database |
| `run_migration.py` | Run migrations |
| `check_users_in_db.py` | List users |
| `clear_all_notes.py` | Clear user notes |

---

## 🚀 Deployment

### Vercel

```bash
# Deploy to production
vercel --prod
```

Automatic deployments on push to `main` branch.

---

## 📄 License

Copyright © 2026. All rights reserved.

---

**Built with ❤️ for the medical education community**
