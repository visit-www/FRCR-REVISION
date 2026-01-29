# ClinicalKey Integration - Implementation Plan

> **Priority:** 2 (Easy Win)  
> **Complexity:** Medium  
> **Estimated Effort:** 3-5 days  
> **Status:** Planned

## Executive Summary

Implement ClinicalKey integration following the existing ScienceDirect pattern. ClinicalKey provides access to medical textbooks and radiology resources. Admin users get auto-login capability, while students must manually log in with 3-month validity tracking.

---

## CRITICAL: App Style and Branding Guidelines

**All UI implementations MUST follow existing app design patterns:**

### Color Palette
- Primary Blue: `#5E899E` (used for anatomy, notes, headers)
- Success Green: `#28a745` (used for connected states, relevant badges)
- Warning Orange: `#ffc107` (used for expired states)
- ClinicalKey Blue: `#0066cc` (Elsevier brand color - use for ClinicalKey icon only)

### UI Component Patterns
- Follow existing tab structure in `view_case.html` sidebar
- Use Bootstrap 5 classes consistently (`btn`, `alert`, `badge`, `card`)
- Match existing icon usage (FontAwesome 5)
- Follow existing spacing patterns (`mb-3`, `p-3`, `gap-2`)

### Connection Status Pattern (Copy from ScienceDirect)
- Badge in tab header showing connection state
- Alert box showing expiration countdown
- Connect/Disconnect button styling
- Same color coding for states (green=connected, yellow=expired, gray=not connected)

---

## Access Credentials

| Environment | URL | Username | Password |
|-------------|-----|----------|----------|
| Web/Browser | https://clinicalpub.com/account/ | gaurav0133@gmail.com | abc123@ |
| App | N/A | garuav0133@gmail.com | FreedomPass@2024 |

**Note:** Store credentials in environment variables, never in code.

---

## Database Schema Changes

Add to User model in `models.py`:

```python
# ClinicalKey Integration (following ScienceDirect pattern)
clinicalkey_connected_at = db.Column(db.DateTime, nullable=True)
clinicalkey_session_data = db.Column(db.Text, nullable=True)
```

---

## Backend Implementation

### New Service File: `clinicalkey_service.py`

```python
CLINICALKEY_LOGIN_URL = "https://clinicalpub.com/account/"
CLINICALKEY_SEARCH_URL = "https://www.clinicalkey.com/#!/search"

def build_search_query(diagnosis, module=None, body_part=None, custom_query=None):
    if custom_query and custom_query.strip():
        return custom_query.strip()
    parts = [diagnosis]
    if module: parts.append(module)
    if body_part: parts.append(body_part)
    return f'{" ".join(parts)} radiology imaging'

def build_search_url(query):
    params = {'query': query, 'facet': 'contenttype:Radiology', 'searchType': 'default'}
    return f"{CLINICALKEY_SEARCH_URL}?{urlencode(params)}"
```

### API Routes

- `GET /api/clinicalkey/status` - Check connection status
- `POST /api/clinicalkey/connect` - Mark as connected
- `POST /api/clinicalkey/disconnect` - Clear connection
- `GET /api/clinicalkey/search-url` - Generate search URL

---

## Files to Modify/Create

### New Files
- `clinicalkey_service.py`

### Modified Files
- `models.py` - Add ClinicalKey columns
- `resources_routes.py` - Add API routes
- `templates/edit_case.html` - Admin UI
- `templates/view_case.html` - Student UI

### Migrations
- `migrations/versions/xxx_add_clinicalkey_columns.py`

---

## Success Criteria

- ClinicalKey search works for admin with auto-login
- ClinicalKey search works for students with manual login
- Login expiration displayed correctly (1 year admin, 3 months student)
- UI matches existing ScienceDirect styling exactly
- No regressions in existing functionality

---

## Todos

- [ ] Add ClinicalKey columns to User model and create migration
- [ ] Create clinicalkey_service.py with search query builder
- [ ] Add ClinicalKey API routes to resources_routes.py
- [ ] Add ClinicalKey section to edit_case.html (match existing card styling)
- [ ] Add ClinicalKey tab to view_case.html (copy ScienceDirect tab pattern)
- [ ] Test ClinicalKey integration with various case types
