# FRCR Revision - Application Structure

## Directory Tree

```
FRCR_REVISION/
├── api/
│   └── index.py                    # Vercel serverless entry point
│
├── ajcc_tnm/                       # AJCC TNM Staging Module
│   ├── __init__.py                 # Module initialization
│   ├── config.py                   # Module configuration
│   ├── data/                       # AJCC reference data (JSON)
│   ├── docs/                       # Module documentation
│   ├── models/                     # SQLAlchemy models
│   ├── routes/                     # Flask blueprints
│   │   ├── admin.py                # Admin TNM routes
│   │   └── public.py               # Public TNM routes
│   ├── samples/                    # Sample HTML sections
│   ├── scripts/                    # Module utilities
│   ├── services/                   # Business logic
│   └── templates/                  # Jinja2 templates
│
├── backups/                        # Backup storage
├── browser_extension/              # Chrome extension for AJCC
├── cache/                          # API response cache
│
├── docs/                           # Documentation
│   ├── APP_STRUCTURE.md            # This file
│   ├── STYLE_GUIDE.md              # Quick style reference
│   └── plans/                      # Feature planning docs
│
├── migrations/                     # Alembic migrations
│   └── versions/                   # Migration scripts
│
├── scripts/                        # Maintenance scripts
│   ├── seed_ajcc_diseases.py       # AJCC data seeder
│   └── utilities/                  # Utility scripts
│       ├── check_*.py              # Database inspection
│       ├── clear_*.py              # Data cleanup
│       ├── fix_*.py                # Schema fixes
│       └── init_database.py        # DB initialization
│
├── services/                       # Core services
│   └── __init__.py                 # Import service
│
├── static/                         # Static assets
│   ├── images/                     # App images & icons
│   ├── style.css                   # Main stylesheet
│   ├── config.js                   # Frontend config
│   ├── edit-case-modal.js          # Case editor JS
│   ├── session-manager.js          # Session handling
│   └── *.js                        # Other JS modules
│
├── templates/                      # HTML templates
│   ├── base.html                   # Base layout
│   ├── login.html                  # Auth pages
│   ├── dashboard.html              # Main dashboard
│   ├── edit_case.html              # Case editor
│   ├── view_case.html              # Case viewer
│   └── *.html                      # Other pages
│
├── app.py                          # Flask application factory
├── models.py                       # Core SQLAlchemy models
├── auth.py                         # Authentication routes
├── admin_routes.py                 # Admin dashboard routes
├── admin_enrichment_routes.py      # Case enrichment routes
├── backup_routes.py                # Backup/restore API
├── resources_routes.py             # PubMed/TCIA/Reference API
├── notes_integration_routes.py     # Notes & highlights
│
├── ai_prelim.py                    # AI case generation
├── ai_tnm.py                       # AI TNM intelligence
├── pubmed_service.py               # PubMed API service
├── tcia_service.py                 # TCIA API service
├── sciencedirect_service.py        # ScienceDirect service
├── browser_automation_service.py   # Playwright automation
│
├── requirements.txt                # Python dependencies
├── vercel.json                     # Vercel configuration
└── README.md                       # Project documentation
```

---

## Core Modules

### 1. Flask Application (`app.py`)
- Application factory pattern
- Blueprint registration
- Database configuration
- Error handlers

### 2. Models (`models.py`)
Core database models:
- `User` - Authentication & profiles
- `Case` - Medical case data
- `CaseImage` - Case images (Cloudinary)
- `Question` / `Answer` - Q&A pairs
- `ExamSession` / `Packet` - Exam organization
- `ImportedCaseStaging` - Case import workflow
- `UserNote` / `UserHighlight` - Student annotations

### 3. Authentication (`auth.py`)
- Login/logout routes
- Registration
- Password reset
- Session management

### 4. Admin Routes (`admin_routes.py`, `admin_enrichment_routes.py`)
- Dashboard
- User management
- Case enrichment workflow
- Content moderation

### 5. Backup System (`backup_routes.py`)
- JSON export/import
- AJCC data backup
- Automatic reminders

---

## AI Features

### Case Generation (`ai_prelim.py`)
- Detects oncologic diagnoses
- Generates preliminary case data
- Claude API integration

### TNM Intelligence (`ai_tnm.py`)
- RAG-based TNM staging
- AJCC data retrieval
- Intelligent summaries
- Figure injection

---

## API Endpoints Overview

| Module | Prefix | Description |
|--------|--------|-------------|
| Auth | `/auth/*` | Login, register, logout |
| Cases | `/api/case/*` | Case CRUD, Q&A |
| Backup | `/backup/*` | Export, import, restore |
| TNM | `/tnm/*` | TNM viewer, API |
| Resources | `/resources/*` | PubMed, TCIA, references |

---

## Database

### Production
- PostgreSQL via Neon
- Connection pooling disabled for serverless

### Development
- SQLite in `instance/` folder
- Migrations via Flask-Migrate

---

## Auto-Initialization

On startup, `app.py` automatically performs these initialization tasks:

### 1. AJCC Data Seeding (`_seed_ajcc_data_if_needed()`)

If AJCC tables are empty, seeds:
- **15 Body Sections**: Head and Neck, Thorax, Breast, etc.
- **23 Disease Sites**: Lung, Larynx, Breast, Colon, etc.

This ensures TNM functionality works on fresh deployments.

### 2. Superadmin Creation (`_ensure_superadmin_exists()`)

If no superadmin exists, creates one:
- **Email**: `lotusheart2016@gmail.com`
- **Password**: Cryptographically secure random (16 chars)
- **Role**: Admin

**Security Notes**:
- Password is generated using `secrets.choice()` (cryptographically secure)
- Password is only displayed ONCE in console at creation time
- Password is NOT stored in code or logs
- User should change password immediately after first login

---

## Deployment

### Vercel
- Serverless Python functions
- Entry point: `api/index.py`
- Config: `vercel.json`

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Session encryption (generate with `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `DATABASE_POSTGRES_URL_NON_POOLING` | Production | Neon PostgreSQL connection string |
| `CLAUDE_API_KEY` | Yes | Anthropic Claude API key for AI features |
| `CLOUDINARY_URL` | Yes | Cloudinary URL for image uploads |
| `RESEND_API_KEY` | Yes | Resend.com API key for password recovery emails |
| `EMAIL_FROM` | No | Sender email address (default: `onboarding@resend.dev`) |
| `APP_URL` | No | Application URL for email links (default: `https://frcr-examiner.vercel.app`) |

### Email Service

Password recovery emails are sent via [Resend](https://resend.com):
- **Free tier**: 100 emails/day, 3000/month
- **SDK**: `resend` Python package
- **Function**: `send_recovery_email()` in `auth.py`

To configure:
1. Sign up at [resend.com](https://resend.com)
2. Create an API key
3. Add `RESEND_API_KEY` to environment variables
4. (Optional) Verify your domain for custom sender address

---

## Development Commands

```bash
# Run locally
flask run

# Database migrations
flask db upgrade

# Create migration
flask db migrate -m "description"

# Deploy to Vercel
vercel --prod
```
