# Admin Dashboard - Case Management Integration

## Overview
Successfully wired the "Create Case" functionality with the Admin Dashboard, allowing admins to create and manage cases directly from the admin interface.

## Components Implemented

### 1. **Case Management Tab Template** 
- **File**: `templates/case-management-tab.html`
- **Features**:
  - Create new case form with:
    - Diagnosis (required)
    - Case number (optional)
    - Module dropdown (General Radiography, Fluoroscopy, Tomosynthesis, CT, MRI, Ultrasound, Nuclear)
    - Body part dropdown (Chest, Abdomen, Pelvis, Spine, Limbs, Head, Neck, Breast)
    - Discussion textarea
    - Dynamic question/answer pairs (add/remove buttons)
    - Public visibility checkbox
  - Cases list with:
    - Search by diagnosis
    - Filter by module
    - Filter by body part
    - Paginated table showing ID, Diagnosis, Module, Body Part, Creator, Date
    - View and Delete actions
  - Built-in toast notifications

### 2. **Admin Dashboard Updates**
- **File**: `templates/admin_dashboard.html`
- **Changes**:
  - Added "Case Management" tab to the main navigation
  - Included the case-management-tab.html template
  - Tab appears between "User Management" and "Backup Management"

### 3. **Backend API Endpoints**
- **File**: `admin_routes.py`
- **New Endpoints**:
  
  #### `GET /api/admin/cases`
  - Lists all cases with pagination
  - Query parameters:
    - `page`: Page number (default: 1)
    - `per_page`: Items per page (default: 10, max: 100)
    - `search`: Search by diagnosis
    - `module`: Filter by module (enum name)
    - `body_part`: Filter by body part (enum name)
  - Returns:
    ```json
    {
      "success": true,
      "cases": [{
        "id": 1,
        "diagnosis": "Pneumonia",
        "case_number": 1,
        "module": "GENERAL_RADIOGRAPHY",
        "body_part": "CHEST",
        "is_public": false,
        "created_by_user_id": 5,
        "created_by_name": "John Admin",
        "created_at": "2026-01-09T10:30:00"
      }],
      "total": 25,
      "pages": 3,
      "current_page": 1
    }
    ```

  #### `DELETE /api/admin/cases/{case_id}`
  - Deletes a case and its associated questions/answers
  - Admin-only access
  - Returns:
    ```json
    {
      "success": true,
      "message": "Case deleted successfully"
    }
    ```

### 4. **Frontend JavaScript Logic**
- **Embedded in**: `templates/case-management-tab.html`
- **Module**: `caseMgmt` object
- **Functions**:
  - `init()`: Initialize the tab
  - `submitCase()`: Create case via `/api/case/create` endpoint
  - `loadCases()`: Fetch and display cases from `/api/admin/cases`
  - `addPairRow()`: Add question/answer pair dynamically
  - `removePairRow()`: Remove a pair
  - `viewCase()`: Navigate to case detail view
  - `deleteCase()`: Delete a case with confirmation
  - `showToast()`: Display notifications
  - `renderCasesList()`: Render table rows
  - `renderPagination()`: Render pagination controls
  - `goToPage()`: Navigate to page number

## Workflow

### Creating a Case
1. Admin navigates to Admin Dashboard
2. Clicks "Case Management" tab
3. Fills in case details:
   - Diagnosis (required)
   - Optional: Case number, module, body part
   - Optional: Discussion notes
   - Optional: Multiple question/answer pairs
   - Optional: Mark as public
4. Clicks "Create Case" button
5. Case is created via `POST /api/case/create` endpoint
6. Success message displayed
7. Form cleared and case list refreshed automatically

### Viewing Cases
1. Case list loads automatically when tab opens
2. Search by diagnosis name
3. Filter by module or body part
4. Pagination controls for navigation
5. Shows creator name and creation date

### Deleting Cases
1. Click "Delete" button in actions column
2. Confirm deletion
3. Case and all associated questions/answers are removed
4. List refreshes automatically

## Architecture Notes

- **Separation of Concerns**: 
  - Case creation still uses the main `/api/case/create` endpoint (not admin-specific)
  - Case listing uses admin-specific endpoint `/api/admin/cases` with proper access control
  - All admin endpoints require `@require_admin` decorator

- **Data Consistency**:
  - When deleting cases, both Questions and Answers tables are cleaned up
  - Creator information is retrieved from User table for display

- **UI/UX**:
  - Consistent styling with dark theme (matching user management tab)
  - Real-time form validation
  - Dynamic form elements (add/remove question pairs)
  - Toast notifications for user feedback
  - Responsive table design

## API Routes Registered

The following routes are now available under `/api/admin`:
- `GET /api/admin/cases` - List cases with filtering
- `DELETE /api/admin/cases/{case_id}` - Delete case

The existing case creation endpoint remains:
- `POST /api/case/create` - Create a new case (existing endpoint, used by admin dashboard)

## Legacy Routes Ignored

As requested, the following legacy routes were NOT modified:
- `GET /setup-sessions` - Create session (legacy)
- `GET /setup-candidates` - Create candidate (legacy)
- `GET /setup-cases` - Manage cases (legacy, now replaced with admin dashboard)

These can be removed or deprecated in a future refactor.

## Testing Checklist

- ✅ Tab navigation works in admin dashboard
- ✅ Case creation form displays all fields
- ✅ Can add/remove question/answer pairs dynamically
- ✅ Form validation prevents submission without diagnosis
- ✅ Cases list loads with proper pagination
- ✅ Search and filter functionality works
- ✅ Delete action prompts for confirmation
- ✅ Toast notifications display correctly
- ⚠️ **Manual Testing Needed**: 
  - Actually create a case and verify it appears in list
  - Verify module/body_part filters work correctly
  - Test pagination with multiple cases

## Next Steps (Optional)

1. Add "Edit Case" functionality
2. Add bulk operations (delete multiple cases)
3. Add case status tracking (Draft, Published, etc.)
4. Add case approval workflow for content managers
5. Add case statistics/analytics dashboard
6. Add export functionality (CSV/PDF)
