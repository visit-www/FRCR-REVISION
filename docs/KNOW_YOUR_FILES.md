# Know Your Files

A quick reference guide to every file in the FRCR Revision application.

---

## Project Structure Tree

```
FRCR_REVISION/
│
├── 📄 Core Application
│   ├── app.py                     # Flask app factory & configuration
│   ├── models.py                  # SQLAlchemy database models
│   ├── auth.py                    # Authentication routes (login/register)
│   └── access_control.py          # Role-based permission decorators
│
├── 📄 Route Handlers
│   ├── admin_routes.py            # Admin dashboard & management
│   ├── admin_enrichment_routes.py # Case enrichment workflow
│   ├── backup_routes.py           # Backup/restore API
│   ├── resources_routes.py        # PubMed, TCIA, reference search
│   └── notes_integration_routes.py# Student notes & highlights
│
├── 🤖 AI Services
│   ├── ai_prelim.py               # AI case generation (Claude)
│   └── ai_tnm.py                  # TNM intelligence & RAG
│
├── 🔌 External Services
│   ├── pubmed_service.py          # PubMed API integration
│   ├── tcia_service.py            # TCIA imaging API
│   ├── sciencedirect_service.py   # ScienceDirect API
│   └── browser_automation_service.py # Playwright automation
│
├── 📁 ajcc_tnm/                   # AJCC TNM Staging Module
├── 📁 api/                        # Vercel serverless entry
├── 📁 templates/                  # HTML templates
├── 📁 static/                     # CSS, JS, images
├── 📁 scripts/                    # Maintenance utilities
├── 📁 migrations/                 # Database migrations
├── 📁 services/                   # Import service
└── 📁 docs/                       # Documentation
```

---

## Core Application Files

| File | Purpose |
|------|---------|
| `app.py` | Flask application factory, blueprint registration, DB config, error handlers |
| `models.py` | All SQLAlchemy models: User, Case, CaseImage, Question, Answer, ExamSession, Packet, Notes, Highlights, IntelligentTNMData |
| `auth.py` | Login, logout, register, password reset, session management |
| `access_control.py` | `@admin_required`, `@content_manager_required` decorators |

---

## Route Handlers

| File | Purpose |
|------|---------|
| `admin_routes.py` | Admin dashboard, user management, content moderation |
| `admin_enrichment_routes.py` | Case enrichment workflow, AI enhancement |
| `backup_routes.py` | JSON export/import, AJCC data backup |
| `resources_routes.py` | PubMed search, TCIA datasets, reference article finder |
| `notes_integration_routes.py` | Create/read/delete student notes & highlights |

---

## AI Services

| File | Purpose |
|------|---------|
| `ai_prelim.py` | Generate preliminary case data from diagnosis using Claude API |
| `ai_tnm.py` | RAG-based TNM staging intelligence, prompt engineering, figure injection |

---

## External Service Integrations

| File | Purpose |
|------|---------|
| `pubmed_service.py` | Search PubMed, fetch article metadata |
| `tcia_service.py` | Query TCIA for imaging datasets |
| `sciencedirect_service.py` | ScienceDirect article access |
| `browser_automation_service.py` | Playwright for web scraping (optional) |

---

## AJCC TNM Module (`ajcc_tnm/`)

### Models
| File | Purpose |
|------|---------|
| `models/__init__.py` | Model exports |
| `models/body_section.py` | `AJCCBodySection` - body regions (Head & Neck, etc.) |
| `models/disease_site.py` | `AJCCDiseaseSite` - specific cancers |
| `models/staging_data.py` | `AJCCStagingData` - TNM definitions, tables, notes |
| `models/diagnosis_year.py` | `DiagnosisYear` - year-specific staging |
| `models/disease_mapping.py` | `DiseaseMapping` - diagnosis → AJCC site mapping |
| `models/staging_time_prefix.py` | Clinical vs pathological staging |

### Routes
| File | Purpose |
|------|---------|
| `routes/public.py` | TNM browser, viewer, student view, API endpoints |
| `routes/admin.py` | Admin TNM management, data import, editing |

### Services
| File | Purpose |
|------|---------|
| `services/mapping_service.py` | Map diagnoses to AJCC sites |
| `services/auth_service.py` | AJCC site authentication |
| `services/extractor.py` | Extract data from AJCC HTML |
| `services/post_processor.py` | Clean & format extracted data |

### Templates
| File | Purpose |
|------|---------|
| `templates/ajcc_tnm_viewer.html` | Full TNM viewer with sidebar |
| `templates/student_tnm_view.html` | Student-focused TNM view |
| `templates/tnm_browse.html` | Browse all body sections |
| `templates/tnm_section.html` | Section listing page |
| `templates/tnm_disease.html` | Simple disease page |
| `templates/admin_tnm_*.html` | Admin editing interfaces |
| `templates/tnm_section_*.html` | Individual section templates |

---

## API / Serverless

| File | Purpose |
|------|---------|
| `api/index.py` | Vercel serverless entry point, imports Flask app |

---

## Templates (`templates/`)

### Authentication
| File | Purpose |
|------|---------|
| `login.html` | Login page |
| `register.html` | Registration page |
| `forgot_password.html` | Password reset request |
| `reset_password.html` | Password reset form |
| `profile.html` | User profile management |

### Dashboard & Navigation
| File | Purpose |
|------|---------|
| `base.html` | Base layout with navbar, footer |
| `dashboard.html` | Main user dashboard |
| `student_dashboard.html` | Student-specific dashboard |
| `admin_dashboard.html` | Admin control panel |

### Case Management
| File | Purpose |
|------|---------|
| `edit_case.html` | Case editor with TinyMCE, TNM button |
| `view_case.html` | Student case viewer with notes/highlights |
| `cases_list.html` | List of cases |
| `student_cases_list.html` | Student case browser |
| `staging_cases_list.html` | Staging workflow list |

### Session Management
| File | Purpose |
|------|---------|
| `setup_sessions.html` | Create/edit exam sessions |
| `manage_session.html` | Manage session details |
| `setup_cases.html` | Add cases to session |
| `modules_view.html` | Module browser |

### Admin
| File | Purpose |
|------|---------|
| `backup_manager.html` | Backup/restore interface |
| `user-management-tab.html` | User management partial |

### Static Pages
| File | Purpose |
|------|---------|
| `about.html` | About page |
| `privacy_policy.html` | Privacy policy |
| `terms_of_use.html` | Terms of use |
| `notion_page.html` | Notion integration |

---

## Static Files (`static/`)

| File | Purpose |
|------|---------|
| `style.css` | Main application stylesheet |
| `config.js` | Frontend configuration |
| `edit-case-modal.js` | Case editing functionality |
| `session-manager.js` | Session handling |
| `backup-reminder.js` | 24-hour backup reminders |
| `user-management.js` | Admin user management |
| `pwa-register.js` | PWA registration |
| `service-worker.js` | Offline support |
| `tinymce.min.js` | TinyMCE rich text editor |

---

## Scripts (`scripts/`)

### Main Scripts
| File | Purpose |
|------|---------|
| `seed_ajcc_diseases.py` | Seed AJCC disease data |

### Utilities (`scripts/utilities/`)
| File | Purpose |
|------|---------|
| `init_database.py` | Initialize database tables |
| `run_migration.py` | Run database migrations |
| `check_users_in_db.py` | List all users |
| `check_user_role.py` | Check user roles |
| `check_notes_highlights.py` | Inspect notes/highlights |
| `clear_all_notes.py` | Clear all user notes |
| `delete_all_staging_cases.py` | Delete staging cases |
| `fix_user_schema.py` | Fix user table schema |
| `fix_sciencedirect_schema_vercel.py` | Fix ScienceDirect fields |
| `crawl_structure_only.py` | Crawl AJCC structure |
| `extract_site_structure.py` | Extract site hierarchy |

---

## Migrations (`migrations/`)

| File | Purpose |
|------|---------|
| `env.py` | Alembic configuration |
| `versions/*.py` | Individual migration scripts |

---

## Services (`services/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Import service for case data |

---

## Browser Extension (`browser_extension/`)

| File | Purpose |
|------|---------|
| `popup.html` | Extension popup UI |
| `popup.js` | Popup logic |
| `background.js` | Background service worker |

---

## Configuration Files

| File | Purpose |
|------|---------|
| `requirements.txt` | Python dependencies |
| `vercel.json` | Vercel deployment config |
| `.gitignore` | Git ignore rules |
| `README.md` | Project documentation |

---

## Quick Lookup by Function

### "I want to add a new API endpoint"
→ Create route in `admin_routes.py`, `resources_routes.py`, or `ajcc_tnm/routes/`

### "I want to modify the database schema"
→ Edit `models.py` → Run `flask db migrate` → `flask db upgrade`

### "I want to change AI behavior"
→ Edit prompts in `ai_prelim.py` or `ai_tnm.py`

### "I want to add a new page"
→ Create template in `templates/` → Add route in relevant `*_routes.py`

### "I want to change styles"
→ Edit `static/style.css` or use inline styles per `docs/STYLE_GUIDE.md`

### "I want to add TNM data"
→ Use admin TNM management or `ajcc_tnm/routes/admin.py`
