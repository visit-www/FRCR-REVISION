# ContentInteract Unification & My Study Notes — Test Plan

> **Created:** 2026-04-26
> **Status:** PENDING
> **Scope:** ContentInteract v3, all content area wiring, My Study Notes page
> **Cost notes:** Notes/highlights/forum API calls are DB-only (no AI cost). Forum image upload uses Cloudinary.

---

## PART A: ContentInteract Core (0 AI cost)

### A1. Side Panel Lifecycle

1. Navigate to `/osce-radiology-guide` (logged in)
2. Click "Notes & Discussion" button
3. **Expected:** Side panel opens on right (22% width), content shifts left
4. Click close (X) button
5. **Expected:** Panel closes, content returns to full width
6. Click toggle 5 times rapidly
7. **Expected:** No console errors, no duplicate panels, no event listener leaks

**Result:** ☐ PASS / ☐ FAIL

### A2. Notes Auto-Save

1. Open panel on OSCE guide
2. Type "Test note for OSCE guide" in textarea
3. Wait 2 seconds (auto-save debounce is 1.5s)
4. **Expected:** Status shows "Saved at HH:MM"
5. Close panel, reopen
6. **Expected:** Note text persists
7. Click "Clear" button, confirm
8. **Expected:** Note cleared, status shows "Cleared"
9. Reopen panel
10. **Expected:** Empty textarea

**Result:** ☐ PASS / ☐ FAIL

### A3. Linked Notes

1. On OSCE guide, select text in a case card body
2. **Expected:** Popup appears with "Highlight" and "Note" buttons
3. Click "Note"
4. **Expected:** Note popup appears with quoted selected text
5. Type "Important finding" and press Cmd+Enter
6. **Expected:** Panel opens, note saved, superscript marker (📝) appears in content

**Result:** ☐ PASS / ☐ FAIL

### A4. Highlights

1. Select text in OSCE content
2. Click "Highlight" in popup
3. **Expected:** Text highlighted in yellow
4. Reload page, open panel
5. **Expected:** Highlight persists (yellow background)
6. Click on highlight
7. **Expected:** Confirm dialog to remove
8. Confirm removal
9. **Expected:** Highlight removed

**Result:** ☐ PASS / ☐ FAIL

### A5. Forum — Basic

1. Open panel, scroll to Discussion section
2. Type "Hello forum" and click Post
3. **Expected:** Message appears with author name, timestamp, vote buttons
4. Click upvote on your message
5. **Expected:** Vote score updates, button shows active state
6. Click downvote
7. **Expected:** Upvote removed, downvote active, score updates

**Result:** ☐ PASS / ☐ FAIL

### A6. Forum — Image Upload

1. Click image icon (📷) next to Post button
2. Select an image file (< 2MB)
3. **Expected:** Preview thumbnail and filename appear
4. Click Post
5. **Expected:** Message posted with image thumbnail visible
6. Click thumbnail
7. **Expected:** Opens full-size image in new tab

**Result:** ☐ PASS / ☐ FAIL

### A7. Forum — Pin (Admin)

1. As admin, click pin (📌) button on a message
2. **Expected:** Message gets pinned badge, moves to top
3. Click pin again
4. **Expected:** Unpinned, returns to vote-sorted position

**Result:** ☐ PASS / ☐ FAIL (admin only)

### A8. Forum — Flag

1. As non-author, click flag (🚩) on someone else's message
2. Enter reason in prompt
3. **Expected:** "Message flagged" toast
4. Click flag again
5. **Expected:** "Already flagged" warning

**Result:** ☐ PASS / ☐ FAIL

### A9. Destroy/Reinit

1. On OSCE guide, open panel
2. Click "View Complete Case" to open focus view
3. **Expected:** Panel reinits with osce_case context
4. Type a note in focus view panel
5. **Expected:** Saves to `osce_case/{case_code}` (not `osce_guide/guide`)
6. Navigate to next case with arrow
7. **Expected:** Panel reloads with new case's notes (previous case notes not shown)
8. Close focus view
9. **Expected:** Panel reinits back to guide-level context

**Result:** ☐ PASS / ☐ FAIL

---

## PART B: Per-Content-Area Wiring (0 AI cost per test)

For each content area below, test:
1. Navigate to the page (logged in)
2. Verify notes toggle button is visible
3. Click toggle → panel opens
4. Type a note → auto-saves
5. Select text → highlight popup appears (where applicable)
6. Post a forum message

### B1. OSCE Focus View
- **URL:** `/osce-radiology-guide` → click "View Complete Case"
- **contentType:** `osce_case`
- **Highlights:** ☐ Skipped (dynamic innerHTML)

**Result:** ☐ PASS / ☐ FAIL

### B2. TNM Essentials
- **URL:** `/essential-tnm-concepts`
- **contentType:** `tnm_essentials`
- **contentKey:** `main`

**Result:** ☐ PASS / ☐ FAIL

### B3. TNM Disease View
- **URL:** `/tnm/thorax/lung` (any disease)
- **contentType:** `tnm_staging`
- **contentKey:** disease slug

**Result:** ☐ PASS / ☐ FAIL

### B4. Clinical Protocol
- **URL:** `/radiology-protocols/view/{id}` (any protocol)
- **contentType:** `protocol`

**Result:** ☐ PASS / ☐ FAIL

### B5. Contrast Card
- **URL:** `/contrast-reaction-card`
- **contentType:** `contrast_card`
- **contentKey:** `main`

**Result:** ☐ PASS / ☐ FAIL

### B6. Anatomy Snippet
- **URL:** `/anatomy-snippets/{slug}` (any snippet)
- **contentType:** `anatomy`

**Result:** ☐ PASS / ☐ FAIL

### B7. Radiology Pearls
- **URL:** `/radiology-pearls`
- **contentType:** `pearl`
- **contentKey:** `browse`

**Result:** ☐ PASS / ☐ FAIL

### B8. Vetting Essentials
- **URL:** `/vetting-essentials`
- **contentType:** `vetting`
- **contentKey:** `main`

**Result:** ☐ PASS / ☐ FAIL

---

## PART C: Case View Bridge (0 AI cost)

### C1. Case Notes — Dual Write

1. Navigate to `/view-case/{id}` (any case)
2. Type a note in the notes tab
3. Save
4. **Expected:** Note saved with both `case_id` AND `content_type='case', content_key='{id}'`
5. Navigate to `/my-notes`
6. **Expected:** Note appears in "Cases" notebook

**Result:** ☐ PASS / ☐ FAIL

### C2. Case Forum — Dual Write

1. Post a forum message on a case
2. **Expected:** Message stored with `content_type='case', content_key='{id}'`
3. Vote on a message
4. **Expected:** Vote works as before

**Result:** ☐ PASS / ☐ FAIL

### C3. Case Highlights — Dual Write

1. Highlight text in case discussion
2. **Expected:** Highlight stored with `content_type='case'`
3. Reload page
4. **Expected:** Highlight persists

**Result:** ☐ PASS / ☐ FAIL

### C4. Anki/Notion Tabs

1. Verify Anki and Notion tabs still appear in case notes section
2. **Expected:** No regression from dual-write changes

**Result:** ☐ PASS / ☐ FAIL

---

## PART D: My Study Notes Page (0 AI cost)

### D1. Empty State

1. Navigate to `/my-notes` as a user with no notes
2. **Expected:** Empty state with guidance text, sidebar shows "No notebooks yet"

**Result:** ☐ PASS / ☐ FAIL

### D2. Notes Display

1. Create notes on 3+ content types (case, OSCE, protocol)
2. Navigate to `/my-notes`
3. **Expected:** All notes visible in list, correct type badges and colours
4. Sidebar shows notebooks with counts

**Result:** ☐ PASS / ☐ FAIL

### D3. Notebook Filter

1. Click a notebook in sidebar (e.g., "Cases")
2. **Expected:** List filters to only case notes
3. Click "All Notes"
4. **Expected:** All notes shown again

**Result:** ☐ PASS / ☐ FAIL

### D4. Search

1. Type a keyword that appears in one note's text
2. **Expected:** List filters instantly (client-side, no server round-trip lag)
3. Clear search
4. **Expected:** All notes shown

**Result:** ☐ PASS / ☐ FAIL

### D5. Star Toggle

1. Click star button on a note in detail pane
2. **Expected:** Star fills in, note shows star icon in list
3. Click "Starred" in sidebar
4. **Expected:** Only starred notes shown

**Result:** ☐ PASS / ☐ FAIL

### D6. Tag Management

1. In detail pane, type a tag and press Enter
2. **Expected:** Tag added, appears in detail pane and sidebar
3. Click X on tag in detail pane
4. **Expected:** Tag removed
5. Click tag in sidebar
6. **Expected:** List filters to notes with that tag

**Result:** ☐ PASS / ☐ FAIL

### D7. Inline Edit

1. Select a note in list
2. Edit the text in detail pane
3. Wait 2 seconds
4. **Expected:** "Saved" status appears
5. Reload page
6. **Expected:** Edit persists

**Result:** ☐ PASS / ☐ FAIL

### D8. Delete Note

1. Click delete button in detail pane
2. Confirm
3. **Expected:** Note removed from list, detail pane shows placeholder

**Result:** ☐ PASS / ☐ FAIL

### D9. Source Navigation

1. Click source link in detail pane header
2. **Expected:** Navigates to original content page (case, protocol, etc.)

**Result:** ☐ PASS / ☐ FAIL

### D10. Sort

1. Change sort to "A-Z"
2. **Expected:** Notes sorted alphabetically by source title
3. Change to "Starred first"
4. **Expected:** Starred notes at top

**Result:** ☐ PASS / ☐ FAIL

### D11. Responsive / Mobile

1. Resize browser to < 993px
2. **Expected:** Sidebar hidden, hamburger menu visible
3. Click hamburger
4. **Expected:** Sidebar slides in as overlay
5. List and detail stack vertically

**Result:** ☐ PASS / ☐ FAIL

### D12. Navbar Button

1. Check desktop navbar (after search box)
2. **Expected:** "Notes" link with book-open icon visible
3. Click it
4. **Expected:** Navigates to `/my-notes`

**Result:** ☐ PASS / ☐ FAIL

---

## PART E: Cross-Content Retrieval

### E1. Multi-Source Notes in My Notes

1. Create a note on: a case, an OSCE case (via focus view), a protocol, and TNM essentials
2. Navigate to `/my-notes`
3. **Expected:** All 4 notes appear, each with correct notebook badge and colour
4. Click each notebook in sidebar
5. **Expected:** Correct filtering

**Result:** ☐ PASS / ☐ FAIL

### E2. Tags Across Content Types

1. Add tag "revision" to a case note and an OSCE note
2. Click "revision" tag in sidebar
3. **Expected:** Both notes shown regardless of content type

**Result:** ☐ PASS / ☐ FAIL

---

## Progress Summary

| Part | Tests | Pass | Fail | Skip |
|------|-------|------|------|------|
| A — Core | 9 | | | |
| B — Content Areas | 8 | | | |
| C — Case Bridge | 4 | | | |
| D — My Study Notes | 12 | | | |
| E — Cross-Content | 2 | | | |
| **Total** | **35** | | | |
