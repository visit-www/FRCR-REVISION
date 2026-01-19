# Notion Integration - Implementation Guide

> **Last Updated:** January 17, 2026  
> **Branch:** `feature/notion-integration`  
> **Base Branch:** `main` (after `feature/enhancing-student-case-view-v2` completion)  
> **Status:** Planning → Implementation

---

## 📚 Related Documents

- **[Student Case View Upgrade](STUDENT_CASE_VIEW_UPGRADE.md)** - Unified notes system with contextual fragments
- **[AI Integration Reference](AI_INTEGRATION_REFERENCE.md)** - AI content generation and watermarking

---

## 🎯 Project Overview

**Goal:** Integrate Notion API to enable users to search existing Notion notes by diagnosis, view them inline, and optionally sync app notes to Notion—while maintaining your app as the primary note-taking system.

**Core Principles:**
1. **Your App = Primary** - Notes are created and edited in your app first
2. **Notion = Optional Archive** - Sync to Notion is optional, not required
3. **Auto-Search by Diagnosis** - When user opens a case, automatically search Notion using diagnosis
4. **Manual Search** - Users can search Notion with custom queries
5. **One-Way Sync** - App → Notion (user chooses when to sync)
6. **Read-Only Viewing** - View Notion notes inline (read-only), open externally for editing

---

## 🔒 Guiding Principle: Dual-Layer Optional Integration

**Layer 1: Your App (Primary)**
- Primary note-taking system (`CandidateNote` in your database)
- Contextual fragments with superscript markers
- Unified Notes box
- Fast, local-first, always available

**Layer 2: Notion (Optional Archive & Search)**
- Optional sync/backup to Notion
- Search existing Notion notes (auto by diagnosis, manual by query)
- View Notion notes inline (read-only)
- Export capabilities
- Never required for core functionality

**Key Principles:**
1. **Your DB = Truth:** `CandidateNote` is the source of truth
2. **Notion = Optional Mirror:** Sync is one-way (app → Notion) and optional
3. **Never Block Core Features:** If Notion is unavailable, app still works
4. **Graceful Degradation:** Show warnings if Notion sync fails, but don't block note-taking

---

## 🚦 Implementation Phases

### **Phase 1: Foundation (Week 1-2)** ⚠️ START HERE

**Goal:** Optional Notion authentication and connection

#### 1.1 Notion Integration Setup
- [ ] **Create Notion Integration**
  - Register internal integration in Notion workspace (or public OAuth if users bring their own accounts)
  - Obtain Integration Token (stored in environment variable)
  - Configure permissions: `read`, `update`, `insert_content` (granular scopes)
  - **File:** Notion workspace settings (external setup)
  - **Documentation:** https://developers.notion.com/docs/create-a-notion-integration

- [ ] **Database Schema (Notion)**
  - Create `Notes` database in Notion workspace
  - Properties:
    - `Title` (title) - Note title
    - `CaseID` (number) - FRCR case ID
    - `Diagnosis` (rich_text) - Diagnosis text (for search)
    - `Content` (page content) - Note content (blocks)
    - `FragmentID` (text, optional) - For contextual fragments (`[note:abc123]`)
    - `CreatedAt` (date)
    - `UpdatedAt` (date)
    - `SyncedAt` (date) - Last sync timestamp
  - **Note:** Notion database schema configured manually in Notion workspace

- [ ] **Database Schema (Your App)**
  - `NotionConnection` model: `user_id`, `integration_token`, `database_id`, `connected_at`
  - `NotionSync` model: `candidate_note_id`, `notion_page_id`, `last_synced_at`
  - Migration: `XXXX_add_notion_integration.py`
  - **File:** `models.py`

#### 1.2 Notion Authentication Flow
- [ ] **OAuth Setup (Optional - if users connect their own Notion accounts)**
  - Notion OAuth 2.0 flow (if using public integration)
  - Store access tokens securely (encrypted in database)
  - **File:** `app.py` (OAuth routes), `services/notion_service.py` (new file)

- [ ] **Internal Integration (Recommended - single workspace)**
  - Use internal integration token (workspace-level)
  - No per-user authentication needed (all users share same workspace)
  - Store `NOTION_API_KEY` in environment variables
  - **File:** `.env`, `config.py`

#### 1.3 Settings UI
- [ ] **Connection Status UI**
  - "Connect Notion" button in user settings (if using OAuth)
  - "Disconnect Notion" option
  - Status indicator: "Connected ✓" or "Not connected"
  - Display connected database name
  - **Files:** `templates/profile.html` or new `templates/settings.html`

**Deliverable:** Users can connect/disconnect Notion (or workspace admin configures integration)

**Testing Checklist:**
- [ ] Integration created in Notion workspace
- [ ] Database created with correct schema
- [ ] API token stored securely (environment variable)
- [ ] Connection status displays correctly
- [ ] Disconnect works

---

### **Phase 2: Search Integration (Week 3-4)**

**Goal:** Auto-search Notion notes by diagnosis, display results

#### 2.1 Notion Search Service
- [ ] **Notion API Client**
  - Python SDK: `notion-client` package (official Notion SDK for Python)
  - Initialize client: `notion = Client(auth=NOTION_API_KEY)`
  - Error handling (rate limits, network errors, auth failures)
  - **File:** `services/notion_service.py` (new file)
  ```python
  from notion_client import Client
  
  notion = Client(auth=os.getenv('NOTION_API_KEY'))
  
  def search_notion_database(query, database_id, max_results=10):
      # Query Notion database using filter
      results = notion.databases.query(
          database_id=database_id,
          filter={
              "property": "Diagnosis",
              "rich_text": {"contains": query}
          }
      )
      return results['results']
  ```

- [ ] **Search Function**
  - Search by diagnosis: Query `Diagnosis` property for case diagnosis text
  - Manual search: Query `Title` or `Content` for user-entered query
  - Return: Page ID, title, snippet, last updated timestamp
  - **File:** `services/notion_service.py`

- [ ] **Rate Limit Handling**
  - Notion API: ~3 requests/second per integration token
  - Implement request queue/batching
  - Cache search results (5-10 minutes TTL)
  - **File:** `services/notion_service.py` (rate limiting logic)

#### 2.2 Auto-Search on Case View
- [ ] **Auto-Search Trigger**
  - When case opens → check if Notion integration is configured
  - If configured → search Notion database using diagnosis text
  - Display results in sidebar/panel (hidden by default, toggle to show)
  - **File:** `templates/view_case.html` (new "Related Notion Notes" panel), `app.py` (search route)

- [ ] **Results Display**
  - Show: Page title, snippet (first 100 chars), last updated timestamp
  - "View Note" button → opens note viewer
  - "Open in Notion" button → external link to Notion page
  - **File:** `templates/view_case.html`

#### 2.3 Manual Search
- [ ] **Search Input Field**
  - Search input in Notion panel
  - Real-time search (debounced, 500ms delay)
  - Search across `Title` and `Content` properties
  - Display results with title, snippet, timestamp
  - **File:** `templates/view_case.html`, `app.py` (route `/api/notion/search`)

**Deliverable:** Users can search and view Notion notes from case view

**Testing Checklist:**
- [ ] Auto-search triggers when case opens
- [ ] Manual search works with custom queries
- [ ] Results display correctly (title, snippet, timestamp)
- [ ] Rate limits handled gracefully
- [ ] Cache prevents excessive API calls

---

### **Phase 3: Note Viewing (Week 5)**

**Goal:** View Notion notes inline (read-only)

#### 3.1 Note Fetch & Render
- [ ] **API Endpoint**
  - `GET /api/notion/page/<page_id>` - Fetch Notion page content
  - Use Notion SDK: `notion.pages.retrieve(page_id)` and `notion.blocks.children.list(block_id)`
  - Convert Notion blocks → HTML for rendering
  - **File:** `app.py` (note fetch route), `services/notion_service.py` (page retrieval + block-to-HTML conversion)

- [ ] **Block-to-HTML Converter**
  - Notion blocks (paragraph, heading, bullet_list, etc.) → HTML
  - Use `notion-client` helper functions or custom converter
  - Preserve formatting: bold, italic, links, lists
  - **File:** `services/notion_service.py` (conversion functions)

- [ ] **Note Viewer Modal**
  - Render fetched page content in modal or inline panel
  - Display: Title, content (converted HTML), last updated timestamp
  - "Refresh" button to reload content
  - **File:** `templates/view_case.html` (note viewer modal)

#### 3.2 External Link Option
- [ ] **Open in Notion Button**
  - "Open in Notion" button (links to Notion web/app)
  - Format: `https://www.notion.so/<page_id>` or `notion://www.notion.so/<page_id>`
  - Opens in user's Notion app or web browser
  - **File:** `templates/view_case.html`

**Deliverable:** Users can view Notion notes inline or open in Notion app

**Testing Checklist:**
- [ ] Fetching page content works
- [ ] Block-to-HTML conversion preserves formatting
- [ ] Note viewer modal displays correctly
- [ ] External link opens in Notion app/browser

---

### **Phase 4: Sync to Notion (Week 6-7)**

**Goal:** Sync notes FROM app → Notion (user choice)

#### 4.1 Sync UI
- [ ] **Sync Toggle in Notes Panel**
  - "Sync to Notion" toggle in Notes panel header
  - Options: "New note" OR "Existing note" (select from search results)
  - Per-case sync preference (store in `NotionSync` table)
  - "Sync Now" button for manual sync
  - **File:** `templates/view_case.html` (sync toggle UI)

- [ ] **Sync Status Indicator**
  - Status: "Synced to Notion ✓" or "Not synced"
  - Show last sync timestamp
  - Display sync errors if any
  - **File:** `templates/view_case.html`

#### 4.2 Note Sync Logic
- [ ] **Convert App Note → Notion Page**
  - Convert `CandidateNote.note_text` → Notion page structure
  - Handle contextual fragments: Each `[note:abc123]...[/note:abc123]` fragment → Notion block with fragment ID
  - Create page: `notion.pages.create(parent={"database_id": database_id}, properties={...})`
  - Add content blocks: `notion.blocks.children.append(block_id, children=[...])`
  - **File:** `services/notion_service.py` (sync functions)

- [ ] **Fragment Mapping Strategy**
  - **Option A (Recommended):** All fragments in one Notion page, each fragment as a toggle/divider block
  - **Option B:** Each fragment becomes its own Notion page (more granular, but may hit limits)
  - Store mapping: `NotionSync.candidate_note_id` → `NotionSync.notion_page_id`
  - **File:** `services/notion_service.py`

- [ ] **Update Existing Notion Page**
  - If note already synced → update existing Notion page
  - Clear existing blocks, append new blocks (or use patch to update specific blocks)
  - Update `last_synced_at` timestamp
  - **File:** `services/notion_service.py` (update logic)

#### 4.3 Sync Metadata Tracking
- [ ] **Track Sync Status**
  - Store `NotionSync` records: `candidate_note_id`, `notion_page_id`, `last_synced_at`
  - On note update → check if synced → update Notion if enabled
  - Handle deleted notes (cleanup `NotionSync` records)
  - **File:** `models.py` (NotionSync model), `app.py` (sync route `/api/case/<id>/note/sync-notion`)

**Deliverable:** Users can sync notes to Notion (create new or update existing)

**Testing Checklist:**
- [ ] Creating new Notion page from app note works
- [ ] Updating existing Notion page works
- [ ] Fragment mapping preserved (Option A or B)
- [ ] Sync metadata tracked correctly
- [ ] Manual sync button works

---

### **Phase 5: Polish & Edge Cases (Week 8)**

**Goal:** Handle errors, rate limits, offline scenarios

#### 5.1 Error Handling
- [ ] **Rate Limit Errors (429)**
  - Queue sync requests, retry after delay
  - Show user message: "Sync queued, will retry shortly"
  - **File:** `services/notion_service.py` (error handling), `templates/view_case.html` (error messages)

- [ ] **Auth Failures**
  - Token expired → prompt re-authentication (if using OAuth)
  - Integration not found → show "Notion integration not configured"
  - **File:** `app.py` (error handling)

- [ ] **Network Errors**
  - Notion API unavailable → show warning, allow retry
  - Timeout handling → retry with exponential backoff
  - **File:** `services/notion_service.py`

#### 5.2 Caching
- [ ] **Search Results Cache**
  - Cache search results (5-10 minutes TTL)
  - Cache page content for faster viewing
  - Invalidate cache on manual refresh
  - **File:** `services/notion_service.py` (cache layer using Flask-Caching or in-memory dict)

#### 5.3 User Guidance
- [ ] **Free Tier Information**
  - Notion free tier: Unlimited pages (no note limits like Evernote)
  - No explicit warnings needed (unlike Evernote's 50-note limit)
  - **File:** `templates/view_case.html` (info tooltips, if needed)

**Deliverable:** Robust error handling and user guidance

**Testing Checklist:**
- [ ] Rate limit errors handled gracefully
- [ ] Auth failures prompt re-authentication
- [ ] Network errors show warnings
- [ ] Cache reduces API calls
- [ ] User guidance is clear

---

## 📁 Files to Modify

### **Backend Files**
- `models.py` - Add `NotionConnection` and `NotionSync` models
- `app.py` - Add API routes for Notion integration
- `migrations/versions/XXXX_add_notion_integration.py` - Database migration
- `services/notion_service.py` - New file (Notion API client)

### **Frontend Files**
- `templates/view_case.html` - Notion panel, search UI, note viewer modal
- `templates/profile.html` or `templates/settings.html` - Notion connection UI
- `static/style.css` - Styles for Notion panel and modals

### **Configuration Files**
- `.env` - Store `NOTION_API_KEY` environment variable
- `requirements.txt` - Add `notion-client` package

### **Documentation Files**
- `docs/NOTION_INTEGRATION_PLAN.md` - This file (implementation tracking)

---

## 🔧 Technical Implementation Details

### **Data Structure: Notion Integration**

```javascript
// Backend - NotionConnection model
{
  "id": 1,
  "user_id": 5,
  "integration_token": "secret_xxxxx",  // Encrypted, or workspace-level token in env
  "database_id": "a1b2c3d4e5f6",  // Notion database ID
  "connected_at": "2026-01-17T10:00:00Z"
}

// Backend - NotionSync model
{
  "id": 1,
  "candidate_note_id": 14,
  "notion_page_id": "a1b2c3d4e5f6",
  "last_synced_at": "2026-01-17T10:00:00Z"
}

// Notion Database - Notes
{
  "page_id": "a1b2c3d4e5f6",
  "properties": {
    "Title": "Case #14: Glioblastoma Notes",
    "CaseID": 14,
    "Diagnosis": "Glioblastoma",
    "FragmentID": null,  // Or "abc123" for contextual fragments
    "CreatedAt": "2026-01-17T10:00:00Z",
    "UpdatedAt": "2026-01-17T10:05:00Z"
  },
  "content": [
    // Notion blocks: paragraphs, headings, lists, etc.
  ]
}
```

### **API Routes**

```
GET  /api/notion/connect          # OAuth callback (if using OAuth)
POST /api/notion/disconnect       # Disconnect account
GET  /api/notion/search?q=...     # Search notes (auto by diagnosis or manual)
GET  /api/notion/page/<page_id>   # Fetch page content
POST /api/case/<id>/note/sync-notion  # Sync note to Notion
```

### **Notion Service Module**

```
services/notion_service.py
- initialize_client()     # Setup Notion client
- search_database(query, database_id)  # Search by diagnosis or custom query
- get_page(page_id)       # Fetch page content
- blocks_to_html(blocks)  # Convert Notion blocks to HTML
- create_page(title, content, database_id)  # Create new page
- update_page(page_id, content)  # Update existing page
- handle_rate_limit()     # Retry logic
```

---

## 🎨 UX Recommendations

### **Notion Panel Design**

**Location:** Right sidebar in case view (hidden by default, toggle button: `[💬 Show Notion Notes]`)

**Layout:**
```
┌─────────────────────────────────┐
│ 💬 Related Notion Notes         │
│ [Toggle: Show/Hide]              │
├─────────────────────────────────┤
│ 🔍 Search Notion: [________]    │
├─────────────────────────────────┤
│ Auto-search: "Glioblastoma"     │
│                                 │
│ 1. Case #14 Notes (2 days ago)  │
│    Snippet of content...        │
│    [View] [Open in Notion]      │
│                                 │
│ 2. Glioblastoma Study Notes     │
│    ...                          │
└─────────────────────────────────┘
```

**Integration with Notes Panel:**
- Sync toggle appears in Notes panel header
- Status: "Synced to Notion ✓" or "Not synced"
- "Sync Now" button for manual sync
- Last sync timestamp displayed

---

## 🐛 Known Issues & Considerations

### **Technical Considerations**

1. **Rate Limits** - Notion API: ~3 requests/second per integration token
   - Solution: Cache search results; batch sync operations; queue sync requests

2. **Fragment Mapping Complexity**
   - Risk: Contextual fragments (`[note:abc123]`) don't map directly to Notion blocks
   - Solution: Store fragments as blocks with metadata, or all fragments in one page with separators

3. **Notion Database Access**
   - Risk: Integration must have access to database, or pages show "Untitled"
   - Solution: Ensure integration is granted access to `Notes` database in Notion workspace

4. **Block-to-HTML Conversion**
   - Risk: Notion blocks have complex structure (nested blocks, rich text, embeds)
   - Solution: Use official Notion SDK helpers or custom converter for basic blocks only

### **Business Considerations**

1. **Workspace vs Individual Accounts**
   - Option A: Single workspace (internal integration) - simpler, all users share same database
   - Option B: User-owned accounts (OAuth) - more complex, requires per-user authentication
   - **Recommendation:** Start with Option A (single workspace), migrate to Option B if needed

2. **Free Tier**
   - Notion free tier: Unlimited pages, unlimited blocks (no note limits)
   - No explicit warnings needed (unlike Evernote's 50-note limit)
   - Still respect rate limits (3 req/sec)

---

## 📊 Success Metrics

Track these metrics post-launch:

- **Integration Usage:**
  - Number of users with Notion connected
  - Search queries per session (auto + manual)
  - Notes synced to Notion (per user)

- **Search Effectiveness:**
  - Auto-search results found per case
  - Manual search usage rate
  - Click-through rate (search result → view note)

- **Sync Adoption:**
  - Percentage of notes synced to Notion
  - Sync frequency (on save vs manual)
  - Sync success rate (errors vs successful)

- **User Satisfaction:**
  - Feedback on Notion panel UX
  - Requests for additional Notion features
  - Issues/errors reported

---

## 🔄 Iteration Plan

### **Sprint 1 (Week 1-2): Phase 1**
- Deliverable: Notion integration setup and authentication
- Demo: Connection status in settings
- Feedback: Refine setup flow

### **Sprint 2 (Week 3-4): Phase 2**
- Deliverable: Search integration (auto + manual)
- Demo: Search Notion notes from case view
- Feedback: Refine search UX

### **Sprint 3 (Week 5): Phase 3**
- Deliverable: Note viewing (inline + external link)
- Demo: View Notion notes in app
- Feedback: Refine viewer UI

### **Sprint 4 (Week 6-7): Phase 4**
- Deliverable: Sync notes to Notion
- Demo: Sync app notes to Notion
- Feedback: Refine sync workflow

### **Sprint 5 (Week 8): Phase 5**
- Deliverable: Error handling and polish
- Demo: Full integration with error handling
- Feedback: Final polish

---

## 📝 Notes for Implementation

### **Design Decisions**

1. **Notion vs Evernote:** Notion chosen for better free tier (unlimited pages), modern API, growing adoption among students
2. **Single Workspace vs OAuth:** Start with single workspace (simpler), migrate to OAuth if users need individual accounts
3. **Fragment Mapping:** Store all fragments in one Notion page with block separators (simpler than one page per fragment)
4. **Sync Frequency:** Manual sync only (user clicks "Sync Now") - avoids rate limit issues, gives user control

### **Accessibility Considerations**

- Notion panel keyboard accessible (toggle with Enter/Space)
- Note viewer modal accessible (ARIA labels, focus management)
- External links clearly labeled ("Open in Notion")
- Error messages accessible (screen reader friendly)

### **Performance Considerations**

- Cache search results (5-10 min TTL) to reduce API calls
- Batch block fetches (load all blocks for a page in one call)
- Debounce manual search (500ms delay)
- Lazy load Notion panel (load content only when panel opened)

---

## 🚀 Next Steps

1. **Complete Prerequisites**
   - Student case view enhancements completed (Phase 1-4)
   - Unified notes system with contextual fragments implemented
   - Stable base to build upon

2. **Setup Notion Workspace**
   - Create Notion workspace (or use existing)
   - Create `Notes` database with schema (properties listed above)
   - Create internal integration in Notion
   - Obtain Integration Token

3. **Begin Phase 1**
   - Install `notion-client` package: `pip install notion-client`
   - Create `services/notion_service.py`
   - Implement connection status UI

4. **Update This Document**
   - Check off completed tasks as you go
   - Document any deviations from plan
   - Add implementation notes

---

## ✅ Pre-Implementation Checklist

Before starting Phase 1:

- [ ] **Student Case View Complete**
  - Phase 1-4 of `STUDENT_CASE_VIEW_UPGRADE.md` completed
  - Unified notes system working
  - Stable base established

- [ ] **Notion Workspace Setup**
  - Notion workspace created or existing workspace identified
  - `Notes` database created with schema
  - Internal integration created in Notion
  - Integration Token obtained and stored securely

- [ ] **Environment Configuration**
  - `NOTION_API_KEY` added to `.env` file
  - `NOTION_DATABASE_ID` added to `.env` file (or config)
  - Environment variables documented in `VERCEL_ENV_SETUP.md`

- [ ] **Create Feature Branch**
  ```bash
  git checkout main
  git pull origin main
  git checkout -b feature/notion-integration
  git push -u origin feature/notion-integration
  ```

- [ ] **Install Dependencies**
  ```bash
  pip install notion-client
  # Add to requirements.txt: notion-client>=2.2.0
  ```

---

**Implementation Status:** 🟡 **Ready to Begin (after student view work)**

**Last Updated:** January 17, 2026  
**Next Review:** After Phase 1 completion
