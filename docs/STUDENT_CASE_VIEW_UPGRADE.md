# Student Case View Design Upgrade - Implementation Guide

> **Last Updated:** January 17, 2026  
> **Branch:** `feature/enhancing-student-case-view-v2`  
> **Base Branch:** `main` (stable-student-view-case-version)  
> **Status:** Planning → Implementation

---

## 📚 Related Documents

- **[AI Integration Reference](AI_INTEGRATION_REFERENCE.md)** - AI content generation and watermarking
- **[Full AI Prompt Documentation](FULL_AI_PROMPT.md)** - Complete AI prompt structure
- **[Anatomy Resources Feature Design](ANATOMY_RESOURCES_FEATURE.md)** - Anatomy resources feature

---

## 🎯 Project Overview

**Goal:** Transform the student case view from separate sections into an integrated, context-aware learning workspace that adapts to different study patterns.

**Core Principles:**
1. **Unified Notes System** - ONE notes box for all notes (context affects creation method, not storage)
2. **Progressive Disclosure** - Advanced features hidden until needed
3. **Spatial Efficiency** - Desktop side-by-side, mobile intelligent stacking
4. **Learning Flow** - Diagnosis → Explore (Q&A/Images) → Deep Dive (Discussion/Forum) → Synthesize (Notes)

---

## 🔒 Guiding Principle: Unified Notes System

**There is only ONE notes system and ONE notes box.**
- ❌ **Do NOT** create separate sections or tabs for "contextual notes" vs "global notes"
- ✅ All notes ultimately live in **one main Notes box**
- ✅ Context only affects **how** the note is created and **referenced**, not **where** it is stored
- ✅ Notes created from Question/Answer/Discussion/Forum/Image → all behave identically
- ✅ Notes created via floating button or text selection → all go to the same Notes box

### ✅ Revised Notes Workflow (Corrected + Improved)

**Architecture (Simplified):**

1️⃣ **Main Notes Box (Single Source of Truth)**
- There is **one persistent Notes box per case**
- This box contains **all notes**, regardless of how they were created:
  - Typed directly
  - Created from floating Notes button
  - Created from selected text in Question/Answer/Discussion/Forum/Image

2️⃣ **Floating Notes Button (Quick Capture)**
- Always visible floating button
- Click → opens TinyMCE text box
- Save → content **appended to main Notes box**

3️⃣ **Text Selection → Notes (Upgraded Highlight Menu)**
- **Scope:** Works in ALL areas: Question, Answer, Discussion, Image description, Forum messages
- Select text → existing highlight menu appears
- **Add "Add to Notes" option** (do NOT remove existing highlight options)
- Click "Add to Notes" → TinyMCE popup → Save → **appended to main Notes box**
- Superscript marker added near selected text (clickable reference to note)

**Important Rules (Do Not Break):**
- All notes live in **one Notes box**
- Contextual notes do **NOT** create new sections
- Superscript is only a **reference pointer**, not a separate note store
- Notes from Question/Answer/Discussion/Forum/Image → all behave identically

---

## 🚦 Implementation Phases

### **Phase 1: Foundation (Week 1)** ⚠️ START HERE

**Goal:** Working side-by-side layout with enhanced Q&A basics

#### 1.1 Enhanced Q&A Panel (Left Side)
- [ ] **Question Preview List**
  - Display all questions as preview cards (collapsed by default)
  - Status indicators: ✓ Reviewed, ⭐ Difficult, ⏸ Paused
  - Color coding: Gray (unreviewed), Green (reviewed), Orange (difficult)
  - **File:** `templates/view_case.html` - Modify `renderStudentQAInteractive()`
  
- [ ] **Expand/Collapse Per Question**
  - Click question card → expand to show full question + answer option
  - Smooth animation (CSS transitions)
  - **File:** `templates/view_case.html` - JavaScript toggle handlers

- [ ] **Reveal/Hide Answer**
  - "Reveal Answer" button per question
  - Answer shown with light green background (`rgba(168, 213, 186, 0.18)`)
  - "Hide Answer" to collapse
  - **File:** `templates/view_case.html` - Answer visibility toggle

- [ ] **Progress Indicator**
  - Top bar: `Progress: ████████░░ 5/8 (62%)`
  - Updates as questions are reviewed
  - **File:** `templates/view_case.html` - Progress calculation + display

#### 1.2 Notes Panel (Right Side - Basic)
- [ ] **Side-by-Side Layout**
  - Desktop (≥992px): Q&A (50%) + Notes (50%)
  - Mobile: Stack vertically (Q&A → Notes)
  - **File:** `templates/view_case.html` - CSS Grid layout
  - **File:** `static/style.css` - `.student-case-layout` grid styles

- [ ] **Global Notes Editor**
  - Existing textarea functionality (auto-save preserved)
  - Full-width when Q&A panel hidden (mobile)
  - **File:** `templates/view_case.html` - Notes section (minimal changes)

#### 1.3 Forum Toggle
- [ ] **Hide Forum by Default**
  - Forum panel initially hidden
  - **File:** `templates/view_case.html` - `initStudentDiscussionChat()` - Set `display: none` initially

- [ ] **Toggle Button**
  - Button: `[💬 Show Forum]` / `[💬 Hide Forum]`
  - Smooth show/hide animation
  - **File:** `templates/view_case.html` - Toggle button + handler
  - **File:** `static/style.css` - Animation styles

**Deliverable:** Working side-by-side layout with basic Q&A improvements

**Testing Checklist:**
- [ ] Desktop: Q&A and Notes side-by-side (50/50)
- [ ] Mobile: Q&A and Notes stack vertically
- [ ] All questions visible as preview cards
- [ ] Click question → expand/collapse works
- [ ] Click "Reveal Answer" → answer shown with green background
- [ ] Progress bar updates correctly
- [ ] Forum hidden by default
- [ ] Toggle button shows/hides forum

---

### **Phase 2: Unified Notes System (Week 2)**

**Goal:** Enhanced note-taking system with text selection → notes flow (works in ALL areas: Q&A, Discussion, Image descriptions, Forum)

#### 2.1 Notes Metadata System (Backend - Optional Enhancement)
- [ ] **Extend CandidateNote Model (Optional)**
  - Add optional metadata fields to track note source context:
    - `source_type` (nullable): `'qa'`, `'discussion'`, `'forum'`, `'image'`, or `null` (direct entry)
    - `source_context_id` (nullable): `'q1'`, `'disc_para_2'`, `'forum_msg_123'`, `'img_3'`, or `null`
    - `selected_text` (nullable): The original selected text (for reference)
  - **Note:** This is optional metadata only. All notes still live in the same `CandidateNote` table.
  - **File:** `models.py` - Extend `CandidateNote` model (optional migration)

- [ ] **API Endpoints (Optional Enhancement)**
  - `GET /api/case/<id>/note` - Get main note (existing endpoint)
  - `POST /api/case/<id>/note` - Save/append to main note (existing endpoint)
  - Metadata tracking happens client-side (localStorage or stored in note content itself)

#### 2.2 Floating Notes Button (Quick Capture)
- [ ] **Floating Button UI**
  - Always visible floating button (bottom-right corner, desktop)
  - Icon: `📝 Notes` or similar
  - **File:** `templates/view_case.html` - Add floating button HTML
  - **File:** `static/style.css` - Floating button styles

- [ ] **Quick Note Modal**
  - Click floating button → opens small TinyMCE text box
  - User can type notes freely (no context required)
  - "Save Note" button → appends content to main Notes box
  - Modal closes after save
  - **File:** `templates/view_case.html` - Modal HTML + JavaScript
  - **File:** Uses existing TinyMCE instance/config (do NOT introduce new editor)

#### 2.3 Upgraded Highlight Menu: "Add to Notes" Option
- [ ] **Extend Existing Highlight Menu**
  - **Scope:** Upgrade existing highlight/selection menu to work in ALL areas:
    - ✅ Question text
    - ✅ Answer text
    - ✅ Discussion paragraphs
    - ✅ Image descriptions
    - ✅ Forum messages (new)
  - **Important:** Do NOT remove existing highlight options — only extend
  - **File:** `templates/view_case.html` - Modify highlight menu JavaScript

- [ ] **Add "Add to Notes" Option**
  - When user selects text → existing highlight menu appears
  - Add new option: `"Add to Notes"` (keep existing highlight color options)
  - **File:** `templates/view_case.html` - Add menu option

#### 2.4 Text Selection → Notes Flow
- [ ] **Note Creation Modal**
  - Click "Add to Notes" → opens TinyMCE popup
  - Pre-populated with selected text (user can edit)
  - User types their note (can include selected text or add own commentary)
  - **File:** `templates/view_case.html` - Modal HTML + JavaScript

- [ ] **Save Note to Main Notes Box**
  - On clicking "Save":
    - Note content is **appended** to main Notes box
    - Small superscript marker is added near selected text in source
  - **File:** `templates/view_case.html` - Save handler + Notes box update

#### 2.5 Contextual Superscript Markers
- [ ] **Superscript Display**
  - After note is saved → add subtle superscript marker near selected text
  - Format: `<sup class="note-marker" data-note-id="...">📝</sup>` or similar
  - Visual: Subtle, doesn't break reading flow
  - **File:** `templates/view_case.html` - Superscript injection

- [ ] **Superscript Click Handler (Links to Specific Note Fragment)**
  - **Critical:** Superscript marker links to a **specific note fragment** within the unified Notes box, NOT the entire box
  - Click superscript → popup opens showing **ONLY that specific contextual note** (extracted from Notes box)
  - Popup is **editable** - user can edit just that note fragment
  - On save → updates **only that specific note section** in the Notes box (replaces the matched fragment)
  - **File:** `templates/view_case.html` - Click handler + popup modal + note extraction/replacement logic

- [ ] **Note Fragment Identification System**
  - Each note created from text selection gets a unique ID embedded in Notes box
  - Format in Notes box: `[note:abc123][from Q1] My specific note text...[/note:abc123]`
  - Superscript marker stores: `data-note-id="abc123"`
  - Click superscript → search Notes box for `[note:abc123]...[/note:abc123]` → extract **only the note content** (between tags) → show in popup
  - Edit in popup → replace **only the matched `[note:abc123]...[/note:abc123]` section** in Notes box → save
  - **File:** `templates/view_case.html` - Note ID generation, embedding, extraction, and targeted replacement logic

**Deliverable:** Unified notes system with text selection → notes flow

**Testing Checklist:**
- [ ] Floating Notes button → opens TinyMCE → saves to main Notes box
- [ ] Select text in Question → "Add to Notes" appears in menu → saves to main Notes box
- [ ] Select text in Answer → "Add to Notes" appears in menu → saves to main Notes box
- [ ] Select text in Discussion → "Add to Notes" appears in menu → saves to main Notes box
- [ ] Select text in Image description → "Add to Notes" appears in menu → saves to main Notes box
- [ ] Select text in Forum message → "Add to Notes" appears in menu → saves to main Notes box
- [ ] After saving → superscript marker appears near selected text
- [ ] Click superscript → popup shows note (editable)
- [ ] All notes appear in ONE unified Notes box
- [ ] No existing highlight behavior breaks
- [ ] Notes persist after page refresh

---

### **Phase 3: Advanced Q&A Features (Week 3)**

**Goal:** Advanced Q&A features with study modes and progress tracking

#### 3.1 Study Modes
- [ ] **Mode Selector**
  - Dropdown/buttons: Flashcard / Review / All / Compare
  - **File:** `templates/view_case.html` - Mode selector UI

- [ ] **Flashcard Mode**
  - Show one question at a time
  - Keyboard navigation: `N` (next), `P` (previous)
  - Full-screen view option
  - **File:** `templates/view_case.html` - Flashcard rendering function

- [ ] **Review Mode**
  - All questions visible, answers hidden
  - "Reveal All" / "Hide All" buttons
  - **File:** `templates/view_case.html` - Review mode rendering

- [ ] **Compare Mode**
  - Side-by-side Q&A view (if space permits)
  - **File:** `templates/view_case.html` - Compare mode rendering

#### 3.2 Progress Tracking (Frontend - localStorage initially)
- [ ] **Review Status Per Question**
  - Track reviewed/unreviewed/difficult status
  - Store in localStorage: `frcr_qa_progress_${caseId}_${userId}`
  - **File:** `templates/view_case.html` - Progress tracking functions

- [ ] **Mark as Reviewed/Difficult**
  - "✓ Mark Reviewed" button per question
  - "⭐ Mark Difficult" button per question
  - Updates localStorage + UI
  - **File:** `templates/view_case.html` - Status update handlers

- [ ] **Progress Bar Updates**
  - Progress bar updates as questions are reviewed
  - **File:** `templates/view_case.html` - Progress calculation

#### 3.3 Filter and Search (Optional - Phase 3.5)
- [ ] **Filter Dropdown**
  - Filter: All / Unreviewed / Difficult / Reviewed
  - **File:** `templates/view_case.html` - Filter UI + logic

- [ ] **Search Within Questions/Answers**
  - Search box to filter questions by text
  - **File:** `templates/view_case.html` - Search functionality

**Deliverable:** Advanced Q&A with study modes

**Testing Checklist:**
- [ ] Switch to Flashcard mode → shows one question at a time
- [ ] Keyboard `N`/`P` → navigates questions
- [ ] Mark question as reviewed → progress bar updates
- [ ] Mark question as difficult → shows orange indicator
- [ ] Filter by "Unreviewed" → shows only unreviewed questions

---

### **Phase 4: Polish and Integration (Week 4)**

**Goal:** Polished, fully integrated learning workspace

#### 4.1 Notes Panel Enhancements (Unified Notes Box)
- [ ] **Search Within Notes**
  - Search box in Notes panel
  - Search within the unified Notes box content
  - **File:** `templates/view_case.html` - Search UI (client-side search)

- [ ] **Optional: Note Source Labels**
  - Notes can optionally show source context (e.g., `[from Q1]`, `[from Discussion]`)
  - Visual labels help users understand note origins (optional enhancement)
  - **File:** `templates/view_case.html` - Note rendering with context labels

- [ ] **Notes Box Rich Text Support**
  - Existing Notes box already supports auto-save
  - Ensure TinyMCE (if used) works seamlessly with unified notes
  - **File:** `templates/view_case.html` - Existing notes editor (no changes needed)

#### 4.2 Image Integration
- [ ] **Clickable Image References in Q&A**
  - Text: `[See Image 1]` → click opens image modal
  - **File:** `templates/view_case.html` - Link handler

- [ ] **Clickable Image References in Discussion**
  - Same as above
  - **File:** `templates/view_case.html` - Link handler

- [ ] **Image Description Notes**
  - Text selection in image descriptions → "Add to Notes" works (Phase 2.4)

#### 4.3 Keyboard Shortcuts
- [ ] **Global Shortcuts**
  - `N` / `→`: Next question (Flashcard mode)
  - `P` / `←`: Previous question (Flashcard mode)
  - `Space`: Reveal/Hide answer
  - `D`: Mark difficult
  - `R`: Mark reviewed
  - `T`: Toggle notes panel (mobile)
  - `F`: Toggle forum (mobile)
  - **File:** `templates/view_case.html` - Keyboard event listeners

#### 4.4 Mobile Optimizations
- [ ] **Collapsible Notes Panel**
  - "📝 Notes" button on mobile → expand/collapse panel
  - **File:** `templates/view_case.html` - Mobile toggle

- [ ] **Swipe Gestures for Q&A**
  - Swipe right on question → reveal answer
  - **File:** `templates/view_case.html` - Touch event handlers (optional)

- [ ] **Bottom Sheet for Forum**
  - Forum opens as bottom sheet on mobile
  - **File:** `templates/view_case.html` - Mobile forum UI

- [ ] **Full-Screen Flashcard Mode**
  - Flashcard mode uses full screen on mobile
  - **File:** `templates/view_case.html` - Full-screen CSS

**Deliverable:** Polished, integrated learning workspace

**Testing Checklist:**
- [ ] Search notes → filters correctly
- [ ] Pin note → appears at top
- [ ] Click `[See Image 1]` → opens image modal
- [ ] Keyboard shortcuts work
- [ ] Mobile: Notes panel collapses/expands
- [ ] Mobile: Forum opens as bottom sheet

---

## 📁 Files to Modify

### **Backend Files**
- `models.py` - Optionally extend `CandidateNote` with metadata fields (optional - Phase 2.1)
- `app.py` - Use existing `/api/case/<id>/note` endpoint (no new endpoints needed)

### **Frontend Files**
- `templates/view_case.html` - Main implementation (JavaScript + HTML)
- `static/style.css` - CSS for new layouts and components

### **Documentation Files**
- `docs/STUDENT_CASE_VIEW_UPGRADE.md` - This file (implementation tracking)

---

## 🔧 Technical Implementation Details

### **Data Structure: Unified Notes System**

```javascript
// Main Notes Box (Backend - CandidateNote model)
// Each contextual note is embedded with unique ID tags
{
  "id": 1,
  "user_id": 5,
  "case_id": 14,
  "note_text": "Main case notes...\n\n[note:abc123][from Q1] My specific note on question 1...[/note:abc123]\n\n[note:def456][from Discussion] Key point from discussion paragraph 2...[/note:def456]\n\nDirect entry note (no ID tags)...",
  "created_at": "2026-01-17T10:00:00Z",
  "updated_at": "2026-01-17T10:05:00Z"
}

// Superscript Marker Metadata (localStorage - client-side only)
// Links superscript markers to note IDs in the Notes box
{
  "note_markers_case_14_user_5": [
    {
      "note_id": "abc123",  // Links to [note:abc123]...[/note:abc123] in Notes box
      "source_type": "qa",
      "source_context_id": "q1",
      "selected_text": "classic CT appearance",
      "position_in_source": "start:100, end:120", // Character position in source text (Q&A/Discussion/etc.)
      "created_at": "2026-01-17T10:00:00Z"
    },
    {
      "note_id": "def456",  // Links to [note:def456]...[/note:def456] in Notes box
      "source_type": "discussion",
      "source_context_id": "disc_para_2",
      "selected_text": "imaging features",
      "position_in_source": "start:250, end:270",
      "created_at": "2026-01-17T10:05:00Z"
    }
  ]
}
```

**Critical Implementation Details:**

1. **Note Fragment Embedding:**
   - When note is created from text selection → generate unique ID (e.g., `abc123`)
   - Append to Notes box as: `[note:abc123][from Q1] User's note text...[/note:abc123]`
   - Store marker metadata in localStorage with `note_id: "abc123"`

2. **Superscript Marker:**
   - Format: `<sup class="note-marker" data-note-id="abc123">📝</sup>`
   - Click handler: Extract `data-note-id` → search Notes box for `[note:abc123]...[/note:abc123]` → extract content between tags → show in popup

3. **Popup Display:**
   - Shows **ONLY the note fragment** (content between `[note:abc123]` and `[/note:abc123]`)
   - Does NOT show entire Notes box
   - User can edit this specific note fragment

4. **Save After Edit:**
   - Replace **only the matched `[note:abc123]...[/note:abc123]` section** in Notes box
   - Preserve all other notes and content
   - Update `CandidateNote.note_text` via existing API endpoint

**Important:** 
- All notes live in ONE `CandidateNote.note_text` field
- Each contextual note is a **fragment** within that field, tagged with unique ID
- Superscript markers link to specific fragments, not the entire box
- Direct notes (from floating button) have no ID tags (they're just plain text)

### **Progress Tracking Structure**

```javascript
// localStorage structure
{
  "qa_progress_case_14_user_5": {
    "reviewed": [1, 2, 3],
    "difficult": [3],
    "last_reviewed": "2026-01-17T10:00:00Z"
  }
}
```

### **CSS Grid Layout (Desktop)**

```css
/* Desktop: Q&A (50%) + Notes (50%) */
@media (min-width: 992px) {
  .case-details.student-case-layout {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.25rem;
  }

  .case-details.student-case-layout .diagnosis-section {
    grid-column: 1 / -1;
    grid-row: 1;
  }

  .case-details.student-case-layout .qa-section {
    grid-column: 1 / 2;
    grid-row: 2;
  }

  .case-details.student-case-layout .notes-section {
    grid-column: 2 / 3;
    grid-row: 2;
  }

  .case-details.student-case-layout .discussion-section {
    grid-column: 1 / -1;
    grid-row: 3;
  }

  .case-details.student-case-layout .images-section {
    grid-column: 1 / -1;
    grid-row: 4;
  }
}
```

---

## ✅ Pre-Implementation Checklist

Before starting Phase 1:

- [ ] **Git Status Check**
  - Current branch: `main`
  - All changes committed
  - Tag created: `stable-student-view-case-version`

- [ ] **Create Feature Branch**
  ```bash
  git checkout main
  git pull origin main
  git checkout -b feature/enhancing-student-case-view-v2
  git push -u origin feature/enhancing-student-case-view-v2
  ```

- [ ] **Backup Current State**
  - Ensure `templates/view_case.html` is backed up
  - Current implementation documented

---

## 🐛 Known Issues & Considerations

### **Issues from Current Implementation**
1. **Q&A Dropdown Interaction** - Current dropdown-based system may feel clunky. **Solution:** Phase 1.1 replaces with preview list.
2. **Notes Isolation** - Notes are separate from Q&A. **Solution:** Phase 1.2 creates side-by-side layout.
3. **Forum Always Visible** - Forum takes up space even when not used. **Solution:** Phase 1.3 hides by default with toggle.

### **Technical Considerations**
1. **localStorage vs Backend** - Progress tracking uses localStorage initially (Phase 3). Can migrate to backend later.
2. **Unified Notes Storage** - All notes live in ONE `CandidateNote.note_text` field. Superscript markers stored client-side (localStorage) for reference only.
3. **Mobile Performance** - Full feature set on mobile may be heavy. Consider progressive enhancement (Phase 4.4).
4. **Existing Highlight Menu** - Do NOT remove existing highlight functionality. Only extend with "Add to Notes" option.
5. **TinyMCE Reuse** - Use existing TinyMCE instance/config. Do NOT introduce new editor.

---

## 📊 Success Metrics

Track these metrics post-launch:

- **Engagement:**
  - Time spent on case view page
  - Number of questions reviewed per session
  - Average questions per case

- **Learning:**
  - Review frequency (difficult questions revisited)
  - Completion rate (questions reviewed / total questions)

- **Notes:**
  - Notes created per case (via floating button + text selection)
  - Notes per source type (Q&A / Discussion / Forum / Image / Direct) ratio

- **Forum:**
  - Forum messages posted
  - Forum usage after toggle (before/after toggle clicks)

- **Usability:**
  - Task completion time (review all questions)
  - User feedback (surveys/interviews)

---

## 🔄 Iteration Plan

### **Sprint 1 (Week 1): Phase 1**
- Deliverable: Side-by-side layout + basic Q&A improvements
- Demo: Stakeholder review
- Feedback: Incorporate into Phase 2

### **Sprint 2 (Week 2): Phase 2**
- Deliverable: Unified notes system with text selection → notes flow
- Demo: Student user testing (5-10 users)
- Feedback: Refine note-taking UX and superscript markers

### **Sprint 3 (Week 3): Phase 3**
- Deliverable: Advanced Q&A features
- Demo: Study mode testing
- Feedback: Refine study modes

### **Sprint 4 (Week 4): Phase 4**
- Deliverable: Polished workspace
- Demo: Full feature testing
- Feedback: Final polish

---

## 📝 Notes for Implementation

### **Design Decisions**
1. **Side-by-Side Q&A + Notes:** Reduces cognitive load, allows simultaneous review and note-taking.
2. **Unified Notes System:** ONE notes box for all notes. Context affects creation method (floating button vs. text selection), not storage location.
3. **Forum Hidden by Default:** Progressive disclosure reduces initial cognitive load.
4. **Multiple Study Modes:** Supports different learning styles (focused vs. comprehensive review).
5. **Text Selection → Notes:** Extends existing highlight menu with "Add to Notes" option (does NOT replace existing highlight functionality).
6. **Superscript Markers:** Visual references back to notes in main box (not separate note storage).

### **Accessibility Considerations**
- Keyboard navigation support (Phase 4.3)
- Screen reader compatibility (ARIA labels)
- High contrast mode support
- Mobile touch targets ≥44px

### **Performance Considerations**
- Superscript markers stored client-side (localStorage) for fast access
- Debounce search/filter (avoid excessive rendering)
- Virtual scrolling for long question lists (future optimization)
- Main Notes box uses existing auto-save mechanism (no performance impact)

---

## 🚀 Next Steps

1. **Complete Pre-Implementation Checklist**
   - Commit current state to `main`
   - Tag `main` as `stable-student-view-case-version`
   - Create feature branch: `feature/enhancing-student-case-view-v2`

2. **Begin Phase 1.1**
   - Start with Question Preview List
   - Test expand/collapse interaction
   - Iterate based on feedback

3. **Update This Document**
   - Check off completed tasks as you go
   - Document any deviations from plan
   - Add implementation notes

---

**Implementation Status:** 🟡 **Ready to Begin**

**Last Updated:** January 17, 2026  
**Next Review:** After Phase 1 completion
