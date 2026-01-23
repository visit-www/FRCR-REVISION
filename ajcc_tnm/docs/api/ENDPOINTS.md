# API Endpoints

## Public Routes (`/tnm`)

### Browse Body Sections

```
GET /tnm
```

Returns the main browse page listing all body sections.

**Response**: HTML page

### List Diseases in Section

```
GET /tnm/<section_slug>
```

Lists all diseases within a body section.

**Parameters**:
- `section_slug`: Body section URL slug (e.g., "thorax")

**Response**: HTML page

### View Disease Staging

```
GET /tnm/<section_slug>/<disease_slug>
```

Main disease page with navigation sidebar.

**Parameters**:
- `section_slug`: Body section URL slug
- `disease_slug`: Disease URL slug (e.g., "lung")

**Query Parameters**:
- `year`: (optional) Diagnosis year, defaults to 2026

**Response**: HTML page

### View Section Details

```
GET /tnm/<section_slug>/<disease_slug>/<section_slug_path>
```

View specific section (1-10) for a disease.

**Parameters**:
- `section_slug`: Body section URL slug
- `disease_slug`: Disease URL slug
- `section_slug_path`: Section slug (e.g., "quick-reference")

**Query Parameters**:
- `year`: (optional) Diagnosis year

**Response**: HTML page

### Check TNM Data

```
GET /tnm/check?diagnosis=<diagnosis>
```

Check if TNM data exists for a diagnosis.

**Query Parameters**:
- `diagnosis`: Cancer diagnosis text

**Response**:
```json
{
    "exists": true,
    "url": "/tnm/thorax/lung"
}
```

## Admin Routes (`/api/admin/tnm`)

All admin routes require authentication and admin role.

### List Body Sections

```
GET /api/admin/tnm/sections
```

**Response**:
```json
{
    "success": true,
    "sections": [
        {
            "id": 1,
            "section_name": "Thorax",
            "slug": "thorax",
            "display_order": 1
        }
    ]
}
```

### List Diseases

```
GET /api/admin/tnm/diseases?section_id=<id>
```

**Query Parameters**:
- `section_id`: Body section ID (required)

**Response**:
```json
{
    "success": true,
    "diseases": [
        {
            "id": 1,
            "disease_name": "Lung",
            "slug": "lung",
            "ajcc_url_path": "thorax/lung",
            "body_section_id": 1
        }
    ]
}
```

### Get Staging Data

```
GET /api/admin/tnm/staging-data?disease_site_id=<id>&year=<year>
```

**Query Parameters**:
- `disease_site_id`: Disease site ID (required)
- `year`: Diagnosis year (default: 2026)

**Response**:
```json
{
    "success": true,
    "exists": true,
    "data": {
        "id": 1,
        "disease_site_id": 1,
        "disease_name": "Lung",
        "year": 2026,
        "sections": {
            "section_1": "<html>...</html>",
            "section_2": "<html>...</html>"
        },
        "extracted_at": "2024-01-01T12:00:00",
        "last_updated_at": "2024-01-01T12:00:00"
    }
}
```

### Extract TNM Data

```
POST /api/admin/tnm/extract
```

Trigger TNM extraction for a disease.

**Request Body**:
```json
{
    "disease_site_id": 1,
    "section_slug": "thorax",
    "disease_slug": "lung",
    "diagnosis_year": 2026
}
```

**Response**:
```json
{
    "success": true,
    "message": "TNM data extracted and saved successfully",
    "data": {
        "id": 1,
        "disease_site_id": 1,
        "year": 2026,
        "extracted_at": "2024-01-01T12:00:00"
    }
}
```

### List All Staging Data

```
GET /api/admin/tnm/list?page=<page>&per_page=<per_page>&section_id=<id>&year=<year>
```

**Query Parameters**:
- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 20, max: 100)
- `section_id`: Filter by section (optional)
- `year`: Filter by year (optional)

**Response**:
```json
{
    "success": true,
    "data": [...],
    "total": 50,
    "pages": 3,
    "page": 1
}
```

### Get Sections for Editing

```
GET /api/admin/tnm/edit/<disease_site_id>/<year>
```

**Response**:
```json
{
    "success": true,
    "sections": [
        {
            "section_number": 1,
            "section_name": "Staging Quick Reference",
            "html_content": "<html>...</html>"
        }
    ],
    "disease_name": "Lung",
    "year": 2026,
    "disease_site_id": 1
}
```

### Update Section

```
PUT /api/admin/tnm/edit/<disease_site_id>/<year>/<section_number>
```

**Request Body**:
```json
{
    "html_content": "<html>Updated content</html>"
}
```

**Response**:
```json
{
    "success": true,
    "message": "Section updated successfully",
    "section_number": 1,
    "section_name": "Staging Quick Reference",
    "last_updated_at": "2024-01-01T12:00:00"
}
```

### Set Manual Cookies

```
POST /api/admin/tnm/set-cookies
```

Set manual session cookies for authentication.

**Request Body**:
```json
{
    "cookies": {
        "session_id": "abc123",
        "auth_token": "xyz789"
    }
}
```

### Get Auth Instructions

```
GET /api/admin/tnm/auth-instructions
```

Get instructions for manual authentication.

### Management Page

```
GET /api/admin/tnm/management
```

Returns the admin management HTML page.

### Edit Page

```
GET /api/admin/tnm/edit-page/<disease_site_id>/<year>
```

Returns the admin edit HTML page for a specific disease/year.

## Error Responses

All endpoints return consistent error responses:

```json
{
    "success": false,
    "error": "Error message description"
}
```

HTTP status codes:
- `400` - Bad request (missing parameters)
- `401` - Unauthorized
- `403` - Forbidden (not admin)
- `404` - Not found
- `500` - Server error
