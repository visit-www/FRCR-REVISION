# Extractor Usage Guide

## IMPORTANT WARNING

**DO NOT MODIFY THE EXTRACTOR CODE WITHOUT CAREFUL CONSIDERATION**

The extraction service (`ajcc_tnm/services/extractor.py` and `auth_service.py`) was developed through extensive testing and debugging of the AJCC OAuth2 authentication flow. Changes to this code may break the entire extraction pipeline.

## Overview

The TNM Extractor fetches cancer staging data from the AJCC website API and parses it into structured JSON.

## Authentication

AJCC uses Okta-based OAuth2 authentication with JavaScript-heavy login forms. The module supports multiple authentication methods:

### 1. Automatic Authentication (Playwright)

Requires Playwright browser automation:

```bash
pip install playwright
playwright install chromium
```

Set credentials:
```bash
export AJCC_USERNAME=your_username
export AJCC_PASSWORD=your_password
```

### 2. Manual Cookie Authentication

For environments where Playwright isn't available:

1. Log in to AJCC website manually in your browser
2. Open DevTools > Application > Cookies
3. Copy the session cookies
4. Use the admin API to set cookies:

```python
# POST /api/admin/tnm/set-cookies
{
    "cookies": {
        "SESSION": "value",
        "JSESSIONID": "value"
    }
}
```

## Usage

### Basic Extraction

```python
from ajcc_tnm.services import TNMExtractor

extractor = TNMExtractor()

# Extract for a specific disease and year
data = extractor.extract_tnm_for_disease(
    section_slug='thorax',
    disease_slug='lung',
    year=2026
)

if data:
    print(f"Extracted {len(data.get('section_1_quick_reference_html', ''))} bytes of Section 1")
```

### Save to Database

```python
from models import AJCCDiseaseSite

disease_site = AJCCDiseaseSite.query.filter_by(slug='lung').first()

staging_data = extractor.save_to_database(
    staging_data_dict=data,
    disease_site=disease_site,
    year=2026,
    user_id=current_user.id
)
```

### Get Available Years

```python
years = extractor.get_available_years('thorax', 'lung')
# Returns: [2026, 2025, 2024]
```

## Data Structure

The extractor returns a dictionary with:

### JSON Fields (Primary Data)

```python
{
    'tnm_data_json': {...},           # T, N, M definitions + stage groups
    'cancers_staged_json': {...},     # Cancers staged list
    'cancers_not_staged_json': {...}, # Cancers not staged
    'summary_changes_json': {...},    # Changes from previous edition
    'primary_sites_json': {...},      # ICD-O codes
    'histopathologic_types_json': {...},
    'imaging_workup_json': {...},
    'staging_rules_json': {...},
    'common_scenarios_json': {...},
    'notes_json': {...}
}
```

### HTML Fields (Legacy)

```python
{
    'section_1_quick_reference_html': '<html>...',
    'section_2_cancers_staged_html': '<html>...',
    # ... sections 3-10
    'raw_html_content': '<html>...'   # Full page HTML
}
```

### Metadata

```python
{
    'year': 2026,
    'data_version': 2  # 1=HTML only, 2=JSON+HTML
}
```

## TNMDataCleaner

The `TNMDataCleaner` class parses HTML into structured JSON:

```python
from ajcc_tnm.services.extractor import TNMDataCleaner

# Parse TNM table HTML
tnm_json = TNMDataCleaner.parse_quick_reference_to_json(html)

# Result:
{
    'title': 'Lung Cancer',
    't_definitions': [
        {
            'subsite': 'Default',
            'categories': [
                {'category': 'TX', 'criteria': '...'},
                {'category': 'T1', 'criteria': '...'}
            ]
        }
    ],
    'n_definitions': {
        'clinical': [...],
        'pathological': [...]
    },
    'm_definitions': [...],
    'stage_groups': [
        {'T': 'T1', 'N': 'N0', 'M': 'M0', 'stage': 'IA'}
    ],
    'notes': [...]
}
```

## Debugging

Enable debug mode for verbose logging:

```bash
export AJCC_DEBUG=true
```

This will:
- Log detailed extraction steps
- Save raw API responses to files
- Show cookie information

## Common Issues

### Authentication Failure

1. Check credentials in environment variables
2. Try manual cookie authentication
3. Check if AJCC website structure changed

### Empty Content

Some diseases have content in child pages. The extractor automatically navigates to child pages if the main page has no content.

### Missing Sections

Not all diseases have all 10 sections. The extractor returns `None` for missing sections.

### Rate Limiting

Be respectful of AJCC servers. Don't extract too frequently. The extracted data is cached in the database.

## Best Practices

1. **Test with one disease first** before bulk extraction
2. **Check extracted data** before using in production
3. **Don't modify auth code** without understanding the OAuth flow
4. **Use the admin UI** for manual extraction when possible
5. **Back up your database** before large extraction runs
