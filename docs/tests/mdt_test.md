# MDT Suite — End-to-End Test Plan

**Goal**: test every feature of the MDT Suite with maximum coverage and minimum AI spend. Each step is interactive — run it, and if it fails **stop and tell me**; I'll fix before the next step.

**Cost control**: full run uses **2 AI calls** (both for AI pre-MDT summary generation, both Sonnet — cheap). Everything else is UI / DB / clipboard work, zero API cost.

**Setup**:
1. Branch `mdt-module` deployed (preview or merged to main)
2. Logged in as any user
3. Open `/mdt` in a browser
4. Keep this file open alongside

---

## PART A — Static surfaces (zero API cost) — 5 min

### A1. Navigation
1. Open Resources dropdown → confirm "MDT Suite" entry visible
2. Click → lands on `/mdt`
3. Confirm breadcrumb: Home → MDT Suite
4. Mobile: open hamburger → Resources collapse → "MDT Suite" entry visible

### A2. Landing page
On `/mdt`:
1. Quick start row visible: Date · Meeting name · MDT type · Open / + buttons
2. Today's date pre-filled
3. Recent meetings card: empty state ("No meetings in the next 2 weeks") if first use
4. Diagnosis search box on the right
5. Privacy banner at the bottom

### A3. Create your first meeting
1. Type "Tuesday Lung MDT" in name → no autocomplete (first time)
2. Pick date 5 days from now
3. Select "Lung" type
4. Click **+** button → confirm prompt → created → navigates to `/mdt/meetings/<id>`

**Expected**: redirects to meeting browser page.

### A4. Meeting browser
1. Confirm header shows meeting name + date + type badge + "0 cases" count
2. Empty state: "No cases yet. Click 'Add case' to start."
3. PDF and HTML export buttons present (top-right)
4. Add case button (orange) present

### A5. Add 3 cases via the modal
Click **Add case** three times:

**Case 1:**
- Reference: `L-2026-04-001`
- Diagnosis: `Adenocarcinoma right upper lobe`
- Clinical history: `67M ex-smoker, 6/52 weight loss, raised ALP`

**Case 2:**
- Reference: `L-2026-04-002`
- Diagnosis: `Mesothelioma right pleura`
- Clinical history: `72M asbestos exposure, dyspnoea`

**Case 3:** (test PII Guard)
- Reference: `1234567890` ← deliberately a 10-digit number
- Diagnosis: `Test`

**Expected**:
- Cases 1 & 2 save and appear in the table
- Case 3 is **rejected with an error** about NHS-number-shaped reference (PII Guard)
- After case 3 fails, change reference to `L-003` and try again — should succeed

Refresh the page → all 3 cases persist in the table.

### A6. Open a case detail
1. Click case 1's diagnosis or edit button
2. Confirm 5 sections present: Identity · Pre-meeting context · AI summary · Meeting outcome · Linked case
3. Confirm reference is shown as password (•••••••) with eye toggle
4. Click eye → reveals reference
5. Status btn-group shows Pending selected
6. "Saved Xs ago" indicator at the top

### A7. Auto-save
1. Type into the **Imaging findings** textarea: `4 cm spiculated RUL mass with mediastinal nodes`
2. Wait ~1.5 seconds → indicator flashes "Saving…" then "Saved at HH:MM:SS"
3. Refresh the page → text persists
4. Type into **Histology / biopsy**: `CNB: adenocarcinoma, EGFR ex19del`
5. Wait → save indicator updates
6. Click status radio "Discussed" → instant save (no debounce)
7. Refresh → status remains Discussed

### A8. PII Guard on textareas
PII Guard relies on **labelled** patterns — a bare "John Smith" or "42 Acacia" is too false-positive-prone in clinical text and is intentionally not flagged. Use the labelled forms to test:

1. In **Clinical history**, type:
   `Name: John Smith, DOB: 15/03/1958, NHS 123 456 7890, address: 42 Acacia Avenue, postcode SW1A 1AA`
2. Within ~250 ms, PII Guard should highlight:
   - **Name: John Smith** (labelled name)
   - **DOB 15/03/1958** (date pattern)
   - **NHS 123 456 7890** (NHS number with Mod-11 checksum)
   - **address: 42 Acacia Avenue** (labelled address)
   - **SW1A 1AA** (UK postcode)
3. Red shield badge should appear in the **Case identity** card header
4. The auto-save indicator should show: *"Save blocked — resolve flagged PII above (Redact / Remove / Dismiss)"*
5. Click the red shield → bulk dropdown → **Redact All** → all PII replaced with `[REDACTED]`
6. Within ~1 second the auto-save indicator should change to "Saved Xs ago" automatically (no need to type anything else — the watchdog re-fires the save)

**Alternative test for Dismiss flow**:
1. Type: `Name: Jane Doe`
2. Wait for shield + highlight
3. Click the highlight → popover → tick the confirmation checkbox → **Dismiss** button
4. Auto-save indicator should change from "Save blocked" to "Saved Xs ago" within 1 second

**Expected**: PII Guard catches all 5 patterns, blocks the PUT until resolved, and auto-retries the save once the user resolves the matches.

### A8b. Bare names / addresses are intentionally NOT flagged
1. In **Clinical history**, type: `Patient is John Smith from 42 Acacia Avenue`
2. PII Guard does **not** highlight (no labelled prefix) — this is the expected behaviour to avoid breaking real clinical text like "John Cunningham mass" or "Acacia thorn injury"
3. The text saves normally

This is by design. If you need stricter scanning, set `data-pii-guard-tier="HIGH"` (already done on the MDT form) — but the regex is the same; the tier only affects how the matches are presented.

**→ STOP if anything in Part A failed.**

---

## PART B — AI summary generation (2 API calls — Sonnet) — 3 min

### B1. Generate pre-MDT summary for Case 1
On case 1 detail page:
1. Confirm all 5 context fields are populated (history, imaging, histology, etc.)
2. Click **Generate / Regenerate** button under "AI pre-MDT summary"
3. Expected:
   - Spinner ~3-5 s
   - Summary appears in the textarea
   - 2-3 lines of plain text
   - Mentions key elements (age, sex, stage if inferable, EGFR, proposed next step)
   - Save indicator updates after the API call
4. Click **Generate / Regenerate** again → new summary (slight variation OK)

**Expected**: 1 Sonnet call per click, both cost ~$0.001.

### B2. Edit the AI summary manually
1. Click into the summary textarea
2. Append: ` ECOG 1.`
3. Wait → auto-saves
4. Refresh → edit persisted

### B3. Negative test — sparse case
Open case 3 (the one with just `Test` diagnosis, no context):
1. Click Generate
2. Expected: error message "At least one of clinical_history, imaging_findings, histology_biopsy, lab_values, or additional_notes is required."
3. Confirm no API call burned (no spinner persists)

---

## PART C — Search + listing (zero API) — 3 min

### C1. Diagnosis search from landing page
1. Go to `/mdt`
2. Type `adeno` in the search box
3. Expected: live results dropdown shows Case 1 with status badge
4. Click result → opens case detail directly (`/mdt/cases/<id>`)

### C2. Diagnosis search from `/mdt/cases/search`
1. Navigate to `/mdt/cases/search`
2. Type `mesoth` → Case 2 appears
3. Type `right` → Cases 1 + 2 both appear (substring match)
4. Type a misspelling like `mesotheliom` → on prod (Postgres pg_trgm) it should still match

### C3. Meetings list
1. Navigate to `/mdt/meetings`
2. Confirm your meeting appears with case count (3) and pending count
3. Test filters:
   - Set MDT type = `Lung` → filters correctly
   - Set MDT type = `Breast` → no results
   - Set name search = `lung` → matches
   - Set date range to today only → no results (your meeting is in the future)
   - Set date range = today + 30 days → matches

### C4. Empty state
1. Set every filter to something nonsensical
2. Confirm "No meetings match these filters." message

---

## PART D — Export (zero API) — 5 min

### D1. HTML export
On the meeting browser:
1. Click **HTML** button → file downloads as `mdt_Tuesday_Lung_MDT_<date>.html`
2. Open the downloaded file in a browser
3. Confirm:
   - All 3 cases visible in 2-column layout
   - Case data on the left, editable consensus on the right
   - Status chips coloured per case
   - Toolbar at top with Copy / Print buttons
   - Privacy banner present

### D2. Edit + persist locally
1. In the HTML file (browser), type into Case 1's "MDT consensus" textarea: `Stage IIIA NSCLC. For thoracic surgery.`
2. Type into Action plan: `Refer Mr X · PET-CT staging`
3. Change status dropdown to "Discussed"
4. **Reload the file** in the browser
5. Expected: edits **persist** (localStorage)

### D3. Copy to clipboard
1. Click "Copy all consensus to clipboard" button
2. Expected: alert "Copied 3 cases. Paste into RadInsights MDT Suite → Bulk Import."
3. Open a text editor and paste — confirm valid JSON with `meeting_id` + `entries` array

### D4. PDF export
1. Back on the meeting browser, click **PDF** button
2. Expected on dev/local: file downloads (will be HTML extension if WeasyPrint not installed — that's the fallback)
3. Expected on prod with WeasyPrint: actual PDF, landscape A4

### D5. Print to PDF (HTML fallback)
If PDF export gave you HTML:
1. Open the HTML file
2. Use browser **Print** (Cmd/Ctrl+P)
3. Choose "Save as PDF"
4. Confirm landscape works, all cases visible, consensus boxes empty (or filled if you edited)

---

## PART E — Bulk paste-back (zero API) — 4 min

### E1. Open bulk import page
1. From the case detail page, click "Bulk import consensus from offline notes" link at the bottom
2. OR navigate to `/mdt/meetings/<id>/bulk-import` directly
3. Confirm breadcrumb chain
4. Paste textarea + Preview/Commit buttons present

### E2. Preview diff
1. Paste the JSON you copied in D3
2. Click **Preview diff**
3. Expected:
   - Diff table appears
   - Each case row shows: reference + diagnosis · old consensus · new consensus · old → new status
   - Yellow highlight on rows with actual changes
   - "Commit changes" button enables

### E3. Commit
1. Click **Commit changes**
2. Confirm dialog → OK
3. Expected:
   - Toast: "Updated 3 case(s)"
   - Auto-redirects to meeting browser after 2s
   - Cases now show updated status (Discussed) in the table

### E4. Verify
1. Open Case 1 detail
2. Confirm:
   - mdt_consensus field has the imported text
   - action_plan has the imported text
   - Status is Discussed

### E5. Bad data
1. Go back to bulk import
2. Paste: `{"entries": [{"case_id": 99999, "mdt_consensus": "test"}]}`
3. Click Preview diff
4. Expected: "1 skipped" warning

---

## PART F — Linking (zero API) — 2 min

### F1. Link a case
1. Open Case 1 detail
2. Scroll to the **Linked previous case** section
3. Click **Link to a case**
4. Modal opens, type `mesoth` in the search
5. Click Case 2 result
6. Toast: "Linked"
7. Page reloads, link section now shows the linked case

### F2. Unlink
1. Click **Unlink** button
2. Confirm → toast: "Unlinked"
3. Page reloads, link section back to empty state

---

## PART G — Smart Reporter integration (1 API call — already counted in B) — 3 min

### G1. Generate an MDT card from a real report
1. Navigate to `/smart-reporter`
2. Paste a short report draft, e.g.:
   ```
   CT chest abdomen pelvis. 67M known smoker. Findings: 4 cm spiculated RUL mass with mediastinal lymphadenopathy. No distant metastases. Liver, adrenals, bones clear.
   Impression: probable lung cancer with mediastinal nodal disease.
   ```
3. Click **Review & Finalize** (1 Opus call — but that's a Smart Reporter test, not MDT)
4. Click **MDT** action button (1 Sonnet call)
5. MDT card appears stacked

### G2. Save to MDT Suite
1. On the MDT action card, click **Save to MDT Suite** button
2. Modal opens
3. Confirm pre-fills:
   - Date = today
   - Diagnosis = parsed from card content (or empty)
   - History = clinical question (if any)
   - Findings = current PACS output
   - Summary = the AI MDT card text
4. Type meeting name: "Tuesday Lung MDT" → autocomplete picks up the existing meeting from earlier tests
5. Click **Save case**
6. Expected: toast "Saved to MDT Suite. Open meeting →"
7. Click "Open meeting" → navigates to the meeting browser
8. Confirm the new case is in the table

---

## PART H — Cross-user isolation (zero API) — 1 min

If you have a second user account:
1. Log in as User B
2. Try to navigate to `/mdt/meetings/<id>` where `<id>` is User A's meeting
3. Expected: **404** (not 403 — to avoid information leak)
4. Try `/api/mdt/meetings/<id>` → 404
5. Try `/api/mdt/cases/<id>` → 404
6. Try the bulk import endpoint → 404

**Expected**: complete isolation. User B never sees User A's data, even via direct URL.

---

## API budget summary

| Part | Calls | Cumulative |
|---|---|---|
| A | 0 | 0 |
| B | 2 (both Sonnet) | 2 |
| C | 0 | 2 |
| D | 0 | 2 |
| E | 0 | 2 |
| F | 0 | 2 |
| G | 1 Sonnet (MDT card) + 1 Opus (Finalize, optional) | 3-4 |
| H | 0 | 3-4 |

**Total: 3-4 AI calls.** ~$0.005-$0.01 in real spend.

---

## Sign-off

Reply with:
```
Part A: PASS / FAIL (notes)
Part B: PASS / FAIL
Part C: PASS / FAIL
Part D: PASS / FAIL
Part E: PASS / FAIL
Part F: PASS / FAIL
Part G: PASS / FAIL
Part H: PASS / FAIL

Issues: ...
```

Pass ≥ 7/8 parts → ready to merge to main and deploy.
Anything failing → I fix in place, you re-run that part.
