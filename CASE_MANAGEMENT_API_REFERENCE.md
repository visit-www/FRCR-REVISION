# Admin Dashboard Case Management - API Reference

## Endpoints

### 1. Create Case
**Endpoint**: `POST /api/case/create`
**Authentication**: Required (any authenticated user, but intended for admins)
**Access**: Created case is tied to current user

**Request Body**:
```json
{
  "diagnosis": "Pneumonia with complications",
  "case_number": 1,
  "module": "GENERAL_RADIOGRAPHY",
  "body_part": "CHEST",
  "discussion": "This case demonstrates...",
  "is_public": true,
  "pairs": [
    {
      "question_text": "What is the primary finding?",
      "answer_text": "Right lower lobe consolidation"
    },
    {
      "question_text": "What organism is likely responsible?",
      "answer_text": "Streptococcus pneumoniae"
    }
  ]
}
```

**Response (Success)**:
```json
{
  "success": true,
  "id": 42,
  "case_id": 42,
  "message": "Case created"
}
```

**Response (Error)**:
```json
{
  "error": "Failed to create case: [error message]"
}
```

---

### 2. List Cases (Admin)
**Endpoint**: `GET /api/admin/cases`
**Authentication**: Required (admin only)
**Access**: Lists all cases with pagination and filtering

**Query Parameters**:
| Parameter | Type | Default | Example |
|-----------|------|---------|---------|
| `page` | integer | 1 | `?page=1` |
| `per_page` | integer | 10 | `?per_page=20` |
| `search` | string | "" | `?search=pneumonia` |
| `module` | string | "" | `?module=GENERAL_RADIOGRAPHY` |
| `body_part` | string | "" | `?body_part=CHEST` |

**Available Module Values**:
- `GENERAL_RADIOGRAPHY`
- `FLUOROSCOPY`
- `TOMOSYNTHESIS`
- `CT`
- `MRI`
- `ULTRASOUND`
- `NUCLEAR`

**Available Body Part Values**:
- `CHEST`
- `ABDOMEN`
- `PELVIS`
- `SPINE`
- `LIMBS`
- `HEAD`
- `NECK`
- `BREAST`

**Example Request**:
```
GET /api/admin/cases?page=1&per_page=10&search=pneumonia&module=GENERAL_RADIOGRAPHY&body_part=CHEST
```

**Response (Success)**:
```json
{
  "success": true,
  "cases": [
    {
      "id": 42,
      "diagnosis": "Pneumonia with complications",
      "case_number": 1,
      "module": "GENERAL_RADIOGRAPHY",
      "body_part": "CHEST",
      "is_public": true,
      "created_by_user_id": 5,
      "created_by_name": "Dr. John Smith",
      "created_at": "2026-01-09T10:30:00"
    },
    {
      "id": 41,
      "diagnosis": "Tuberculosis",
      "case_number": 2,
      "module": "GENERAL_RADIOGRAPHY",
      "body_part": "CHEST",
      "is_public": false,
      "created_by_user_id": 5,
      "created_by_name": "Dr. John Smith",
      "created_at": "2026-01-08T14:15:00"
    }
  ],
  "total": 25,
  "pages": 3,
  "current_page": 1
}
```

**Response (Error)**:
```json
{
  "success": false,
  "error": "Failed to list cases: [error message]"
}
```

---

### 3. Delete Case (Admin)
**Endpoint**: `DELETE /api/admin/cases/{case_id}`
**Authentication**: Required (admin only)
**Access**: Deletes specified case and all associated questions/answers

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `case_id` | integer | ID of case to delete |

**Example Request**:
```
DELETE /api/admin/cases/42
```

**Response (Success)**:
```json
{
  "success": true,
  "message": "Case deleted successfully"
}
```

**Response (Case Not Found)**:
```json
{
  "success": false,
  "error": "Case not found"
}
```

**Response (Error)**:
```json
{
  "success": false,
  "error": "Failed to delete case: [error message]"
}
```

---

## JavaScript API (Frontend)

All JavaScript functionality is contained in the `caseMgmt` object within `case-management-tab.html`.

### Main Functions

#### `caseMgmt.submitCase()`
Creates a new case based on form values

**Usage**:
```javascript
// Called automatically on form submission
// Gathers data from form fields and POSTs to /api/case/create
```

#### `caseMgmt.loadCases()`
Fetches and displays cases with current filters

**Usage**:
```javascript
caseMgmt.loadCases();
// Refreshes case list based on current page, search, and filters
```

#### `caseMgmt.addPairRow()`
Dynamically adds a question/answer pair row to the form

**Usage**:
```javascript
caseMgmt.addPairRow();
// Adds new input fields for Q&A pair
```

#### `caseMgmt.removePairRow(buttonElement)`
Removes a question/answer pair

**Usage**:
```javascript
// Called by inline onclick handler
caseMgmt.removePairRow(this);
```

#### `caseMgmt.deleteCase(caseId)`
Deletes a case after confirmation

**Usage**:
```javascript
caseMgmt.deleteCase(42);
// Prompts user, then DELETEs to /api/admin/cases/42
```

#### `caseMgmt.viewCase(caseId)`
Navigates to case detail view

**Usage**:
```javascript
caseMgmt.viewCase(42);
// Redirects to /view-case/42
```

#### `caseMgmt.showToast(message, type)`
Displays a notification toast

**Usage**:
```javascript
caseMgmt.showToast('Case created!', 'success');
caseMgmt.showToast('Error occurred', 'error');
caseMgmt.showToast('Processing...', 'info');
```

---

## Error Codes

| Code | Scenario |
|------|----------|
| 200 | Success |
| 400 | Bad request (invalid parameters) |
| 403 | Access denied (not admin) |
| 404 | Case not found (for delete) |
| 500 | Server error |

---

## Form Fields

### Create Case Form

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `caseDiagnosis` | text | Yes | Main diagnosis text |
| `caseNumber` | number | No | Optional case number |
| `caseModule` | select | No | Enum value |
| `caseBodyPart` | select | No | Enum value |
| `caseDiscussion` | textarea | No | Discussion/clinical notes |
| `caseIsPublic` | checkbox | No | Visibility flag |
| `.pair-question` | textarea | No | Question text (dynamic) |
| `.pair-answer` | textarea | No | Answer text (dynamic) |

---

## Search & Filter Example

**Search for pneumonia cases**:
```
GET /api/admin/cases?search=pneumonia
```

**Get chest CT cases only**:
```
GET /api/admin/cases?module=CT&body_part=CHEST
```

**Get page 2 of results**:
```
GET /api/admin/cases?page=2&per_page=10
```

**Complex query**:
```
GET /api/admin/cases?page=1&per_page=20&search=pneumonia&module=GENERAL_RADIOGRAPHY&body_part=CHEST
```

---

## HTML Structure

The complete case management UI is in `templates/case-management-tab.html`:

```html
<div id="caseManagementTab">
  <!-- Create Case Section -->
  <form id="createCaseForm">
    <!-- Form fields -->
    <div id="questionAnswerPairs">
      <!-- Dynamic Q&A pair rows added here -->
    </div>
  </form>
  
  <!-- Cases List Section -->
  <div>
    <!-- Search & Filter controls -->
    <table id="casesList">
      <!-- Case rows populated here -->
    </table>
    <nav id="casesPagination">
      <!-- Pagination controls -->
    </nav>
  </div>
</div>
```

---

## Integration with Admin Dashboard

The case management tab is included in `admin_dashboard.html`:

```html
<button id="cases-tab" data-bs-target="#cases-content">
  <i class="fas fa-flask"></i> Case Management
</button>

<div id="cases-content" role="tabpanel">
  {% include 'case-management-tab.html' %}
</div>
```

When an admin clicks the "Case Management" tab:
1. The case-management-tab.html is rendered
2. `caseMgmt.init()` is called
3. Initial case list is loaded
4. User can create cases or manage existing ones
