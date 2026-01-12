# Database Backup & Import Workflow Documentation

## Overview

The FRCR-Revision app has **two separate import workflows** for different use cases:

1. **FRCR-Revision DB Import** - Direct import/restore of FRCR-Revision backups
2. **FRCR-Examiner DB Import** - Staging-based import from FRCR-Examiner app

---

## 1. FRCR-Revision DB Import Workflow

**Endpoint:** `/api/backup/restore`  
**Location:** Admin Dashboard → Database Management → Import Backup

### Workflow Steps:

1. **User selects backup file** (JSON format from FRCR-Revision)
2. **User must check two checkboxes:**
   - ☑️ **"Overwrite existing data"** (optional) - If checked, existing records will be updated
   - ☑️ **"I confirm I want to import"** (required) - Must be checked to proceed

3. **Import Process:**
   - **New records** → Always added (regardless of overwrite checkbox)
   - **Existing records** → Behavior depends on checkbox:
     - ✅ **Overwrite checked** → Existing records are **UPDATED** with backup data
     - ❌ **Overwrite unchecked** → Existing records are **SKIPPED** (not modified)

4. **Smart Field Handling:**
   - Unknown fields (not in FRCR-Revision DB schema) are **ignored**
   - Only valid fields are imported

5. **Staging for Incomplete Cases:**
   - Cases missing critical fields (module, body_part, age_group) are sent to **staging** for review
   - Admin can review and complete these cases later

### Overwrite Protection Confirmation:

✅ **CONFIRMED:** The database is **NOT overwritten** if the user has **NOT checked** "Overwrite existing data".

**Code Verification:**
```python
# Line 206-210: Checkboxes are read
overwrite_existing = request.form.get('overwrite_existing') == 'true'
confirm_overwrite = request.form.get('confirm_overwrite') == 'true'

# Line 240-264: Users - Only updates if overwrite_existing is True
if existing_user:
    if overwrite_existing:
        # Update existing user
        ...
    else:
        stats['users']['skipped'] += 1  # SKIPPED if not checked

# Line 315-380: Cases - Only updates if overwrite_existing is True
if existing_case:
    if overwrite_existing:
        # Update existing case
        ...
    else:
        stats['cases']['skipped'] += 1  # SKIPPED if not checked
```

---

## 2. FRCR-Examiner DB Import Workflow

**Endpoint:** `/api/admin/enrichment/import`  
**Location:** Admin Dashboard → Database Management → Import from FRCR-Examiner

### Workflow Steps:

1. **User selects FRCR-Examiner backup file** (JSON format)
2. **Click "Check for Duplicates"** button
   - System scans for duplicate cases
   - Shows report: New Cases, Staging Duplicates, Production Duplicates
3. **Click "Import Cases to Staging"** button
   - All cases are imported to **`ImportedCaseStaging`** table
   - **No direct production import** - all cases go through staging first
4. **Admin Review & Enrichment:**
   - Cases appear in staging area
   - Admin adds missing metadata (module, body_part, age_group)
   - Admin sets case status (Draft/Published)
5. **Promotion to Production:**
   - Admin reviews and approves cases
   - Cases are promoted to production `Case` table

### Key Differences from FRCR-Revision Import:

| Feature | FRCR-Revision Import | FRCR-Examiner Import |
|---------|---------------------|---------------------|
| **Destination** | Direct to production tables | Staging table first |
| **Overwrite Option** | Yes (with checkbox) | No (always creates new staging entries) |
| **Enrichment Required** | Only for incomplete cases | All cases require review |
| **Duplicate Handling** | Skip or overwrite | Always creates staging entry |
| **Use Case** | Restore FRCR-Revision backups | Import from different app (FRCR-Examiner) |

---

## Summary

### ✅ Overwrite Protection:

**FRCR-Revision Import:**
- ✅ **Safe:** Existing data is **NOT overwritten** unless "Overwrite existing data" checkbox is checked
- ✅ **New data:** Always added (doesn't require overwrite checkbox)
- ✅ **Existing data:** Only updated if checkbox is checked

**FRCR-Examiner Import:**
- ✅ **Always safe:** All imports go to staging first, never directly overwrite production
- ✅ **No overwrite option:** Not applicable (staging workflow)

### 🔄 Workflow Separation:

✅ **YES, the workflows are completely separate:**

1. **FRCR-Revision Import** (`/api/backup/restore`)
   - For restoring FRCR-Revision backups
   - Direct import with overwrite option
   - Handles all data types (users, cases, sessions, flags, etc.)

2. **FRCR-Examiner Import** (`/api/admin/enrichment/import`)
   - For importing from FRCR-Examiner app
   - Staging-based workflow
   - Only handles cases (goes through enrichment process)

---

## Recommendations

1. **For FRCR-Revision backups:** Use the "Import Backup" section
   - Check "Overwrite existing data" only if you want to update existing records
   - Leave unchecked to only add new records

2. **For FRCR-Examiner backups:** Use the "Import from FRCR-Examiner" section
   - Always goes through staging (safe)
   - Requires admin review before production

3. **Best Practice:** Always create a backup before importing, regardless of which workflow you use.
