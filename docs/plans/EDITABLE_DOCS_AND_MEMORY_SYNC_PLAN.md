# Editable Admin Docs + Claude Memory Sync — Implementation Plan

> **Status:** Planned — resume in next session
> **Priority:** Medium
> **Estimated effort:** 1 session

---

## Context

Admin needs to edit documentation (marketing, business model, SEO, AI docs) from the frontend without deploying code. Changes should be trackable and syncable to Claude's memory so the coding agent stays aware of the current state.

## Architecture

### 1. Database Models

```python
class AdminDocument(db.Model):
    """Editable admin documents stored in DB (not filesystem)."""
    __tablename__ = 'admin_document'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(100), unique=True, nullable=False)  # e.g. 'marketing-launch-kit'
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50))  # marketing, finance, seo, technical, qa
    content_html = db.Column(db.Text)  # TinyMCE HTML content
    last_edited_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

class ClaudeMemoryUpdate(db.Model):
    """Pending memory updates for Claude coding agent."""
    __tablename__ = 'claude_memory_update'

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50))  # project, feedback, user, reference
    summary = db.Column(db.String(500))  # One-line description
    details = db.Column(db.Text)  # Full content for memory file
    source_doc_slug = db.Column(db.String(100))  # Which doc triggered this
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_synced = db.Column(db.Boolean, default=False)
    synced_at = db.Column(db.DateTime)
```

### 2. API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/admin/documents` | GET | List all documents |
| `/api/admin/documents/<slug>` | GET | Get document content |
| `/api/admin/documents/<slug>` | PUT | Save TinyMCE edits |
| `/api/admin/documents/seed` | POST | One-time: migrate markdown files to DB |
| `/api/admin/claude-memory-sync` | GET | Get unsynced memory updates (for Claude) |
| `/api/admin/claude-memory-sync/mark-synced` | POST | Mark all as synced |
| `/api/admin/claude-memory-sync` | POST | Create a new memory update (from "Sync to Dev Notes" button) |

### 3. Frontend

**Document Editor Page:** `/api/admin/documents/<slug>/edit`
- TinyMCE editor (same integration as MDT case detail)
- Auto-save on blur (debounced)
- "Sync to Dev Notes" button → opens modal:
  - Category dropdown (project, feedback, reference)
  - Summary text field (one line)
  - Details auto-populated from document diff or manual entry
  - Submit → POST to `/api/admin/claude-memory-sync`

**Docs Hub Update:** Add "Edit" buttons on each document card

### 4. Initial Migration

Seed the DB with existing markdown docs:
- `docs/MARKETING_LAUNCH_KIT.md` → slug: `marketing-launch-kit`
- `docs/BUSINESS_FINANCE_MODEL.md` → slug: `business-finance-model`
- `docs/SEO_AUDIT_APRIL_2026.md` → slug: `seo-audit`
- `docs/tests/peer_review_test.md` → slug: `peer-review-test`
- `docs/tests/peer_review_package_test.md` → slug: `peer-review-package-test`

### 5. Claude Memory Sync Flow

```
Admin edits doc → clicks "Sync to Dev Notes"
    ↓
Modal: enters summary + category
    ↓
POST /api/admin/claude-memory-sync
    ↓
Saved to claude_memory_update (is_synced=false)
    ↓
Next Claude session: user says "update memory"
    ↓
Claude asks user to curl /api/admin/claude-memory-sync
    ↓
Claude reads unsynced entries, updates memory files
    ↓
User runs POST /mark-synced
```

### 6. CLAUDE.md Integration

Already created — contains "Memory Sync Protocol" section that instructs Claude to check the sync endpoint when user says "update memory."

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `models.py` | Add AdminDocument + ClaudeMemoryUpdate models |
| `admin_routes.py` | Add document CRUD + memory sync endpoints |
| `templates/admin_doc_editor.html` | New — TinyMCE document editor |
| `templates/admin_docs_hub.html` | Update — add edit buttons, link to DB docs |
| `CLAUDE.md` | Already created |

## Verification
1. Edit a document in the frontend → verify saves to DB
2. Click "Sync to Dev Notes" → verify creates ClaudeMemoryUpdate row
3. GET /api/admin/claude-memory-sync → verify returns unsynced entries
4. POST /mark-synced → verify entries marked as synced
5. Verify TinyMCE works with existing CSS/Bootstrap styling
