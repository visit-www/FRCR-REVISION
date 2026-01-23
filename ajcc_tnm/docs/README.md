# AJCC TNM Staging Module

A self-contained, reusable Python module for AJCC TNM cancer staging data extraction, storage, and display.

## Overview

This module provides:
- **Data Extraction**: Authenticated scraping of AJCC staging website API
- **Data Storage**: Structured database models for TNM staging data
- **Data Display**: Flask blueprints and templates for browsing/viewing staging data
- **Stage Calculator**: Programmatic lookup of stage groups from T, N, M values

## Quick Start

### Installation

```python
# In your Flask app
from ajcc_tnm import init_app, get_blueprints

# Initialize module
init_app(app)

# Register blueprints
admin_tnm_bp, tnm_bp = get_blueprints()
app.register_blueprint(admin_tnm_bp)
app.register_blueprint(tnm_bp)
```

### Configuration

Set environment variables:

```bash
# Required for extraction
AJCC_USERNAME=your_ajcc_username
AJCC_PASSWORD=your_ajcc_password

# Optional
AJCC_DEFAULT_YEAR=2026
AJCC_DEBUG=false
AJCC_ENABLE_HTML_LEGACY=true

# For image storage (optional)
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

## Module Structure

```
ajcc_tnm/
├── __init__.py           # Module entry point
├── config.py             # Configuration classes
├── models/               # Database models
├── services/             # Business logic
│   ├── extractor.py      # TNM data extraction
│   ├── auth_service.py   # AJCC authentication
│   └── mapping_service.py
├── routes/               # Flask blueprints
│   ├── admin.py          # Admin endpoints
│   └── public.py         # Public endpoints
├── templates/            # Jinja2 templates
├── data/                 # Reference data files
├── samples/              # Sample HTML for testing
├── tests/                # Test suite
└── docs/                 # Documentation
```

## Key Features

### 1. Authenticated Extraction

The module handles OAuth2 authentication with AJCC's Okta login system:

```python
from ajcc_tnm.services import TNMExtractor

extractor = TNMExtractor()
data = extractor.extract_tnm_for_disease('thorax', 'lung', 2026)
```

### 2. Structured Data Storage

Data is stored both as:
- **Clean JSON** (primary) - for programmatic access
- **Raw HTML** (legacy) - for display and reference

### 3. Stage Calculator

```python
from models import AJCCStagingData

staging = AJCCStagingData.query.filter_by(...).first()
stage = staging.get_stage_for_tnm('T2', 'N1', 'M0')
# Returns: 'IIB'
```

### 4. Flask Integration

```python
# Public routes at /tnm/...
/tnm                          # Browse body sections
/tnm/<section>                # List diseases in section
/tnm/<section>/<disease>      # View disease staging

# Admin routes at /api/admin/tnm/...
/api/admin/tnm/extract        # Trigger extraction
/api/admin/tnm/management     # Management UI
```

## Database Models

| Model | Description |
|-------|-------------|
| `AJCCBodySection` | Body regions (Thorax, Head/Neck, etc.) |
| `AJCCDiseaseSite` | Diseases within sections (Lung, Breast, etc.) |
| `AJCCDiagnosisYear` | Available years (2024, 2025, 2026) |
| `AJCCStagingData` | TNM staging data with JSON + HTML |
| `AJCCDiseaseMapping` | Links to app's module/body part enums |
| `AJCCStagingTimePrefix` | c, p, yc, yp, r, a prefixes |

## Documentation

- [Architecture](planning/ARCHITECTURE.md)
- [Database Schema](planning/DATABASE_SCHEMA.md)
- [Installation Guide](guides/INSTALLATION.md)
- [Configuration Options](guides/CONFIGURATION.md)
- [Extractor Usage](guides/EXTRACTOR_USAGE.md)
- [API Endpoints](api/ENDPOINTS.md)

## Version History

- **1.0.0** - Initial module extraction from FRCR Revision app
