# AJCC TNM Module Architecture

## Overview

The AJCC TNM module is designed as a self-contained, reusable package that can be integrated into any Flask application.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Host Flask App                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   models.py │  │    app.py   │  │    Other Blueprints     │  │
│  │  (db, User, │  │             │  │                         │  │
│  │   Enums)    │  │             │  │                         │  │
│  └──────┬──────┘  └──────┬──────┘  └─────────────────────────┘  │
│         │                │                                       │
│         │    ┌───────────┴───────────┐                          │
│         │    │    init_ajcc_tnm(app) │                          │
│         │    │  register_blueprint() │                          │
│         │    └───────────┬───────────┘                          │
│         │                │                                       │
│  ┌──────┴────────────────┴──────────────────────────────────┐   │
│  │                      ajcc_tnm/                            │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │   │
│  │  │  models/ │  │ services/│  │  routes/ │  │templates/│  │   │
│  │  │          │  │          │  │          │  │          │  │   │
│  │  │BodySect  │  │Extractor │  │ admin.py │  │tnm_*.html│  │   │
│  │  │DiseaseSt │  │AuthServ  │  │public.py │  │          │  │   │
│  │  │DiagYear  │  │Mapping   │  │          │  │          │  │   │
│  │  │StagingDt │  │          │  │          │  │          │  │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Extraction Flow

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Admin UI   │ ──▶  │   Extractor  │ ──▶  │  AJCC API    │
│  /management │      │   Service    │      │ (External)   │
└──────────────┘      └──────┬───────┘      └──────────────┘
                             │
                             ▼
                      ┌──────────────┐
                      │ TNMDataClean │
                      │    (Parse)   │
                      └──────┬───────┘
                             │
                             ▼
                      ┌──────────────┐
                      │   Database   │
                      │ (JSON + HTML)│
                      └──────────────┘
```

### Display Flow

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│    Browser   │ ──▶  │   Routes     │ ──▶  │   Models     │
│   /tnm/...   │      │  (public.py) │      │ StagingData  │
└──────────────┘      └──────┬───────┘      └──────────────┘
                             │
                             ▼
                      ┌──────────────┐
                      │   Template   │
                      │ tnm_*.html   │
                      └──────────────┘
```

## Key Design Decisions

### 1. Dual Storage (JSON + HTML)

- **Primary**: Clean JSON for programmatic access
- **Legacy**: Raw HTML for display and debugging
- **Rationale**: Allows gradual migration while preserving original data

### 2. Model Location

Models remain in the host app's `models.py` to:
- Share the same `db` instance
- Avoid migration conflicts
- Allow foreign keys to host models (User)

The module re-exports them for convenience.

### 3. Template Folder

Templates are in `ajcc_tnm/templates/` and added to Jinja's search path during `init_app()`.

### 4. Configuration

Uses dataclasses with callbacks for host app integration:
- `get_db()` - Get SQLAlchemy db instance
- `get_current_user_id()` - Get current user
- `require_admin` - Admin decorator

## Component Responsibilities

### Models

| Model | Responsibility |
|-------|----------------|
| `AJCCBodySection` | Body region hierarchy |
| `AJCCDiseaseSite` | Disease within sections |
| `AJCCDiagnosisYear` | Year selection |
| `AJCCStagingData` | TNM data storage + accessors |
| `AJCCDiseaseMapping` | App integration mapping |
| `AJCCStagingTimePrefix` | Reference data |

### Services

| Service | Responsibility |
|---------|----------------|
| `extractor.py` | Fetch and parse AJCC data |
| `auth_service.py` | OAuth2 authentication |
| `manual_auth_helper.py` | Cookie-based auth fallback |
| `mapping_service.py` | Diagnosis to URL mapping |

### Routes

| Blueprint | Prefix | Purpose |
|-----------|--------|---------|
| `tnm_bp` | `/tnm` | Public browsing |
| `admin_tnm_bp` | `/api/admin/tnm` | Admin management |

## Extension Points

### Adding New Features

1. **New Templates**: Add to `ajcc_tnm/templates/`
2. **New Routes**: Add to `routes/public.py` or `routes/admin.py`
3. **New Services**: Add to `services/` directory
4. **New Models**: Add to host `models.py` (for migrations)

### Integrating with Host App

The module uses callbacks for integration:

```python
config = AJCCConfig()
config.get_frcr_module_enum = lambda: MyModuleEnum
config.get_body_part_enum = lambda: MyBodyPartEnum
init_ajcc_tnm(app, config=config)
```
