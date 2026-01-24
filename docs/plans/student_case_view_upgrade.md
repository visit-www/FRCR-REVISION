---
name: Student Case View Upgrade - Implementation & Execution Plan
overview: Comprehensive implementation plan for transforming the student case view into an integrated learning workspace, organized into 4 phases over 4 weeks with clear deliverables, code changes, and testing checkpoints.
todos:
  - id: phase1-layout
    content: "Phase 1.2: Implement CSS Grid layout for side-by-side Q&A + Notes (desktop 50/50, mobile stack)"
    status: completed
  - id: phase1-qa-preview
    content: "Phase 1.1: Replace Q&A dropdown with preview card list (renderStudentQAInteractive modification)"
    status: completed
  - id: phase1-forum-toggle
    content: "Phase 1.3: Add forum toggle button (hide by default, show/hide animation)"
    status: completed
  - id: phase2-floating-button
    content: "Phase 2.2: Add floating notes button (bottom-right, opens TinyMCE, appends to notes box)"
    status: pending
    dependencies:
      - phase1-layout
  - id: phase2-highlight-menu
    content: "Phase 2.3: Extend highlight menu with 'Add to Notes' option (all areas: Q&A/Discussion/Image/Forum)"
    status: pending
  - id: phase2-fragment-system
    content: "Phase 2.5: Implement note fragment system (unique IDs, superscript markers, fragment extraction/replacement)"
    status: pending
    dependencies:
      - phase2-highlight-menu
  - id: phase3-study-modes
    content: "Phase 3.1: Implement study modes (Flashcard/Review/Compare) with keyboard navigation"
    status: pending
    dependencies:
      - phase1-qa-preview
  - id: phase3-progress
    content: "Phase 3.2: Implement progress tracking (localStorage, status indicators, progress bar updates)"
    status: pending
    dependencies:
      - phase1-qa-preview
  - id: phase4-polish
    content: "Phase 4: Polish & integration (notes search, image links, keyboard shortcuts, mobile optimizations)"
    status: pending
    dependencies:
      - phase1-forum-toggle
      - phase2-fragment-system
      - phase3-study-modes
---

# Student Case View Upgrade - Implementation & Execution Plan

## Executive Summary

Transform the student case view from separate sections into an integrated learning workspace over 4 weeks. The plan includes side-by-side layouts, unified notes system, advanced Q&A features, and mobile optimizations—all while preserving existing functionality and SEO.

**Timeline:** 4 weeks (1 week per phase)

**Branch:** `feature/enhancing-student-case-view-v2`

**Risk Level:** Medium (significant UI changes, but no backend breaking changes)

---

## Current State Analysis

### What Already Exists

**Already Implemented:**

- `renderStudentQAInteractive()` function in `view_case.html` (line ~1804) - Q&A rendering for students
- `initStudentDiscussionChat()` function (line ~1307) - Client-side discussion forum
- `student-case-layout` CSS class (line ~1237) - Grid layout class application
- Highlight menu system (`highlightable-text` class, text selection handlers) - Lines ~2238-2405
- Notes section with auto-save (`candidateNoteText` textarea) - Lines ~235-252
- Basic Q&A dropdown interaction for students

**Needs Enhancement:**

- Q&A preview list (currently dropdown-based)
- Side-by-side layout CSS (class exists but needs grid implementation)
- Forum toggle button (forum exists but always visible)
- Floating notes button (doesn't exist)
- "Add to Notes" in highlight menu (highlight menu exists but no notes option)
- Superscript markers and fragment system (doesn't exist)
- Progress tracking (doesn't exist)
- Study modes (doesn't exist)

---

## Phase-by-Phase Implementation

### Phase 1: Foundation (Week 1) - Layout & Basic Q&A

**Goal:** Working side-by-side layout with enhanced Q&A basics

**Key Changes:**

#### 1.1 Enhanced Q&A Panel (Left Side)

**File:** `templates/view_case.html`

- **Current:** `renderStudentQAInteractive()` renders Q&A with dropdown selection
- **Change:** Replace dropdown with preview card list
  - Modify `renderStudentQAInteractive()` function (starts ~line 1804)
  - Add question preview cards (collapsed by default)
  - Add status indicators (✓ Reviewed, ⭐ Difficult)
  - Add expand/collapse animation
  - Add "Reveal Answer" button per question
  - Add progress indicator bar at top

**File:** `static/style.css`

- Add `.qa-student-preview-card` styles
- Add `.qa-progress-bar` styles
- Add status indicator colors (gray/green/orange)
- Add expand/collapse transitions

#### 1.2 Notes Panel (Right Side)

**File:** `templates/view_case.html`

- **Current:** Notes section exists (line ~226) but stacks vertically
- **Change:** Apply grid layout for side-by-side
  - Ensure `student-case-layout` class is applied (already done at line 1237)
  - Verify notes section has correct class/ID

**File:** `static/style.css`

- **Current:** `.student-case-layout` CSS exists (check lines ~506-538)
- **Change:** Implement CSS Grid for desktop (50/50 split)
  - Grid columns: `1fr 1fr` for Q&A + Notes
  - Grid rows: Diagnosis (full), Q&A+Notes (row 2), Discussion (row 3), Images (row 4)
  - Mobile: Stack vertically (remove grid on <992px)

#### 1.3 Forum Toggle

**File:** `templates/view_case.html`

- **Current:** `initStudentDiscussionChat()` creates forum (line ~1307)
- **Change:** 
  - Set `#discussionChatPanel` to `display: none` initially
  - Add toggle button above discussion section
  - Toggle handler: show/hide panel with animation

**File:** `static/style.css`

- Add forum toggle button styles
- Add show/hide animation (slideDown/slideUp)

**Dependencies:** None (Phase 1 is foundation)

**Estimated Effort:** 16-20 hours

**Testing Checklist:**

- [ ] Desktop: Q&A and Notes side-by-side (50/50)
- [ ] Mobile: Q&A and Notes stack vertically
- [ ] Question preview cards display correctly
- [ ] Click question → expand/collapse works
- [ ] "Reveal Answer" shows answer with green background
- [ ] Progress bar updates correctly
- [ ] Forum hidden by default
- [ ] Toggle button shows/hides forum

---

### Phase 2: Unified Notes System (Week 2)

**Goal:** Enhanced note-taking with text selection → notes flow

**Key Changes:**

#### 2.1 Floating Notes Button

**File:** `templates/view_case.html`

- Add floating button HTML (bottom-right corner)
- Add click handler → open TinyMCE modal
- On save → append content to `#candidateNoteText` textarea
- Call existing `/api/case/<id>/note` endpoint

**File:** `static/style.css`

- Add `.floating-notes-button` styles (fixed position, bottom-right)
- Add TinyMCE modal styles

**Dependencies:** Existing TinyMCE instance/config (reuse, don't create new)

#### 2.2 Upgrade Highlight Menu: "Add to Notes"

**File:** `templates/view_case.html`

- **Current:** `showHighlightActionMenu()` function (find around line ~2405)
- **Change:** 
  - Add "Add to Notes" option to menu
  - Click handler → open TinyMCE popup
  - Pre-populate with selected text
  - On save → append to notes box with `[note:abc123]...[/note:abc123]` tags
  - Generate unique ID for each note fragment

**Dependencies:** Highlight menu system (already exists)

#### 2.3 Superscript Markers & Fragment System

**File:** `templates/view_case.html`

- After saving note from selection → inject superscript marker near selected text
- Format: `<sup class="note-marker" data-note-id="abc123">📝</sup>`
- Store marker metadata in localStorage: `note_markers_case_${caseId}_user_${userId}`
- Click handler on superscript → extract fragment from notes box → show in popup
- Popup editable → replace only matched `[note:abc123]...[/note:abc123]` section

**File:** `static/style.css`

- Add `.note-marker` styles (subtle, clickable)
- Add note fragment popup modal styles

**Critical Implementation:**

- Note fragment format: `[note:abc123][from Q1] User note text...[/note:abc123]`
- localStorage structure: `{ note_id: "abc123", source_type: "qa", source_context_id: "q1", ... }`
- Fragment extraction: Regex to find `[note:abc123](.*?)[/note:abc123]` in notes box
- Fragment replacement: Replace matched section only, preserve other content

**Dependencies:** Phase 2.2 (highlight menu upgrade)

**Estimated Effort:** 24-30 hours (most complex phase)

**Testing Checklist:**

- [ ] Floating Notes button opens TinyMCE → saves to main Notes box
- [ ] Select text in Question → "Add to Notes" appears → saves correctly
- [ ] Same for Answer/Discussion/Image/Forum
- [ ] Superscript marker appears after save
- [ ] Click superscript → popup shows only that fragment (editable)
- [ ] Edit in popup → only that fragment updates in Notes box
- [ ] All notes appear in ONE unified Notes box
- [ ] Notes persist after page refresh

---

### Phase 3: Advanced Q&A Features (Week 3)

**Goal:** Study modes and progress tracking

**Key Changes:**

#### 3.1 Study Modes

**File:** `templates/view_case.html`

- Add mode selector UI (Flashcard / Review / All / Compare)
- Modify `renderStudentQAInteractive()` to accept mode parameter
- Flashcard mode: Show one question at a time, keyboard `N`/`P`
- Review mode: All questions visible, answers hidden, "Reveal All" button
- Compare mode: Side-by-side Q&A view

**File:** `static/style.css`

- Add study mode selector styles
- Add flashcard mode full-screen styles
- Add compare mode side-by-side styles

#### 3.2 Progress Tracking

**File:** `templates/view_case.html`

- Store progress in localStorage: `frcr_qa_progress_${caseId}_${userId}`
- Structure: `{ reviewed: [1,2,3], difficult: [3], last_reviewed: "..." }`
- "Mark Reviewed" / "Mark Difficult" buttons per question
- Update progress bar calculation based on localStorage

**File:** `static/style.css`

- Add status indicator styles (✓/⭐ buttons)

**Dependencies:** Phase 1.1 (Q&A preview list)

**Estimated Effort:** 16-20 hours

**Testing Checklist:**

- [ ] Switch to Flashcard mode → shows one question at a time
- [ ] Keyboard `N`/`P` navigates questions
- [ ] Mark question as reviewed → progress bar updates
- [ ] Mark question as difficult → shows orange indicator
- [ ] Progress persists after page refresh

---

### Phase 4: Polish & Integration (Week 4)

**Goal:** Final polish and mobile optimizations

**Key Changes:**

#### 4.1 Notes Panel Enhancements

**File:** `templates/view_case.html`

- Add search box in Notes panel (client-side search)
- Optional: Note source labels (`[from Q1]`, `[from Discussion]`)

#### 4.2 Image Integration

**File:** `templates/view_case.html`

- Make `[See Image 1]` references clickable (open image modal)
- Text selection in image descriptions → "Add to Notes" works (Phase 2.2)

#### 4.3 Keyboard Shortcuts

**File:** `templates/view_case.html`

- Add global keyboard event listeners
- Shortcuts: `N`/`→` (next), `P`/`←` (previous), `Space` (reveal), `D` (difficult), `R` (reviewed), `T` (toggle notes), `F` (toggle forum)

#### 4.4 Mobile Optimizations

**File:** `templates/view_case.html`

- Collapsible Notes panel on mobile (toggle button)
- Forum bottom sheet on mobile (CSS transform)
- Full-screen flashcard mode on mobile

**File:** `static/style.css`

- Mobile-specific styles for collapsible panels
- Bottom sheet animation
- Full-screen flashcard styles

**Dependencies:** All previous phases

**Estimated Effort:** 16-20 hours

**Testing Checklist:**

- [ ] Search notes works correctly
- [ ] Image references clickable
- [ ] Keyboard shortcuts work
- [ ] Mobile: Notes panel collapses/expands
- [ ] Mobile: Forum opens as bottom sheet
- [ ] Mobile: Flashcard mode full-screen

---

## Critical Implementation Details

### Note Fragment System (Phase 2)

**Data Flow:**

```
User selects text → "Add to Notes" → TinyMCE popup → Save
  ↓
Generate unique ID (e.g., "abc123")
  ↓
Append to Notes box: `[note:abc123][from Q1] User note...[/note:abc123]`
  ↓
Store marker metadata in localStorage
  ↓
Inject superscript: <sup data-note-id="abc123">📝</sup>
  ↓
On click → Extract fragment via regex → Show in popup → Edit → Replace fragment
```

**Implementation Functions:**

```javascript
// Generate unique ID
function generateNoteId() {
  return 'note_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// Extract fragment from notes box
function extractNoteFragment(noteId, notesText) {
  const regex = new RegExp(`\\[note:${noteId}\\](.*?)\\[/note:${noteId}\\]`, 's');
  const match = notesText.match(regex);
  return match ? match[1].replace(/^\[from [^\]]+\]/, '').trim() : null;
}

// Replace fragment in notes box
function replaceNoteFragment(noteId, newContent, notesText) {
  const regex = new RegExp(`(\\[note:${noteId}\\]\\[from [^\\]]+\\])(.*?)(\\[/note:${noteId}\\])`, 's');
  return notesText.replace(regex, `$1${newContent}$3`);
}
```

### CSS Grid Layout (Phase 1.2)

**Desktop Grid:**

```css
@media (min-width: 992px) {
  .case-details.student-case-layout {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.25rem;
  }
  .case-details.student-case-layout .diagnosis-section { grid-column: 1 / -1; grid-row: 1; }
  .case-details.student-case-layout .qa-section { grid-column: 1 / 2; grid-row: 2; }
  .case-details.student-case-layout .notes-section { grid-column: 2 / 3; grid-row: 2; }
  .case-details.student-case-layout .discussion-section { grid-column: 1 / -1; grid-row: 3; }
  .case-details.student-case-layout .images-section { grid-column: 1 / -1; grid-row: 4; }
}
```

**Mobile Stack:**

```css
@media (max-width: 991px) {
  .case-details.student-case-layout {
    display: block; /* Remove grid */
  }
}
```

---

## Files to Modify

### Primary Files

1. **`templates/view_case.html`** - Main implementation (~3000 lines)

   - Phase 1: Lines ~1804-2000 (Q&A rendering), ~1307-1500 (forum toggle)
   - Phase 2: Lines ~2238-2500 (highlight menu), new floating button, superscript handlers
   - Phase 3: Lines ~1804-2000 (study modes), progress tracking
   - Phase 4: Lines ~235-252 (notes enhancements), keyboard shortcuts, mobile handlers

2. **`static/style.css`** - Styling (~4300 lines)

   - Phase 1: Lines ~506-538 (grid layout), new Q&A/forum styles
   - Phase 2: New floating button, superscript marker, note popup styles
   - Phase 3: Study mode styles, progress indicators
   - Phase 4: Mobile optimizations, keyboard shortcut hints

### Secondary Files (Optional)

3. **`models.py`** - Phase 2.1 (optional metadata fields for `CandidateNote`)
4. **`app.py`** - No changes needed (existing `/api/case/<id>/note` endpoint sufficient)

---

## Risk Mitigation

### High-Risk Areas

1. **Note Fragment System (Phase 2.3)**

   - **Risk:** Complex regex parsing, edge cases (nested tags, malformed fragments)
   - **Mitigation:** 
     - Test with various note formats
     - Escape special characters in note content
     - Fallback: If fragment not found, show full notes box

2. **CSS Grid Layout (Phase 1.2)**

   - **Risk:** Breaks existing layout for non-students or other views
   - **Mitigation:**
     - Only apply `student-case-layout` class when `isStudent === true` (already done)
     - Test with different screen sizes
     - Verify DOM order preserved (SEO requirement)

3. **Highlight Menu Extension (Phase 2.2)**

   - **Risk:** Breaks existing highlight functionality
   - **Mitigation:**
     - Extend, don't replace existing menu
     - Test highlight colors still work
     - Isolate "Add to Notes" as separate option

### Medium-Risk Areas

4. **localStorage Dependencies (Phase 2, 3)**

   - **Risk:** localStorage unavailable (private mode) or cleared
   - **Mitigation:**
     - Graceful degradation (show full notes box if markers not found)
     - Sync critical data to backend (optional future enhancement)

5. **Mobile Performance (Phase 4)**

   - **Risk:** Heavy JavaScript on mobile devices
   - **Mitigation:**
     - Progressive enhancement (features degrade gracefully)
     - Lazy load non-critical features
     - Test on real devices

---

## Testing Strategy

### Unit Testing (Per Phase)

**Phase 1:**

- CSS Grid renders correctly (desktop/mobile)
- Q&A preview cards display and expand
- Forum toggle works

**Phase 2:**

- Note fragment generation (unique IDs)
- Fragment extraction (regex parsing)
- Fragment replacement (preserve other content)
- Superscript marker injection and click handlers

**Phase 3:**

- Study mode switching
- Progress tracking (localStorage)
- Progress bar calculation

**Phase 4:**

- Keyboard shortcuts (don't conflict with browser shortcuts)
- Mobile responsive behavior
- Search functionality

### Integration Testing

- Full user flow: Select text → Add to Notes → View superscript → Edit fragment
- Cross-phase: Q&A progress → Study modes → Notes integration
- Browser compatibility: Chrome, Firefox, Safari, Edge
- Mobile devices: iOS Safari, Android Chrome

### Regression Testing

- Existing highlight colors still work
- Non-student views unchanged
- SEO DOM order preserved
- Existing notes auto-save still works
- Image modal still works
- Discussion forum still works (client-side)

---

## Success Criteria

**Phase 1 Complete When:**

- Desktop layout: Q&A and Notes side-by-side (50/50)
- Mobile layout: Sections stack vertically
- Q&A preview list works (no dropdown)
- Forum hidden by default with toggle

**Phase 2 Complete When:**

- Floating notes button works
- "Add to Notes" in highlight menu works (all areas)
- Superscript markers appear and are clickable
- Fragment editing works (isolated updates)

**Phase 3 Complete When:**

- Study modes work (Flashcard/Review/Compare)
- Progress tracking works (localStorage)
- Progress bar updates correctly

**Phase 4 Complete When:**

- All keyboard shortcuts work
- Mobile optimizations complete
- Search functionality works
- No regressions in existing features

**Overall Success When:**

- All 4 phases complete
- All testing checklists passed
- No breaking changes to existing functionality
- SEO DOM order preserved
- Accessibility maintained (keyboard navigation, screen readers)

---

## Timeline & Milestones

**Week 1 (Phase 1):** Foundation

- Day 1-2: CSS Grid layout + Q&A preview list
- Day 3-4: Forum toggle + progress indicator
- Day 5: Testing + fixes

**Week 2 (Phase 2):** Unified Notes System

- Day 1-2: Floating notes button
- Day 3-4: Highlight menu upgrade + superscript markers
- Day 5: Fragment system implementation + testing

**Week 3 (Phase 3):** Advanced Q&A

- Day 1-2: Study modes (Flashcard/Review/Compare)
- Day 3-4: Progress tracking + status indicators
- Day 5: Testing + fixes

**Week 4 (Phase 4):** Polish

- Day 1-2: Notes enhancements + image integration
- Day 3-4: Keyboard shortcuts + mobile optimizations
- Day 5: Final testing + documentation

---

## Next Steps

1. **Pre-Implementation:**

   - [ ] Complete pre-implementation checklist (git status, branch creation, backup)
   - [ ] Review existing code structure (confirm line numbers for key functions)
   - [ ] Set up testing environment (local dev + staging)

2. **Begin Phase 1:**

   - [ ] Start with CSS Grid layout (lowest risk, foundation for everything)
   - [ ] Test layout on desktop and mobile
   - [ ] Proceed to Q&A preview list

3. **Track Progress:**

   - [ ] Update `STUDENT_CASE_VIEW_UPGRADE.md` checkboxes as tasks complete
   - [ ] Document deviations from plan
   - [ ] Note any blocking issues

---

**Implementation Status:** Ready to begin Phase 1

**Risk Assessment:** Medium (significant UI changes, but well-scoped and non-breaking)

**Estimated Total Effort:** 72-90 hours (4 weeks @ 18-22 hours/week)