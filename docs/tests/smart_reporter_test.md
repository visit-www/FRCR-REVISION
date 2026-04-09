# Smart Reporter — End-to-End Test Plan

**Goal**: exercise every feature of the Smart Reporter in a single session, with minimum AI API calls and maximum regression coverage. Interactive — run each step, and if it fails, **stop and tell me**; I'll fix before the next step.

**Cost control**: the full run uses **6 AI calls total** (1 × anatomy snippet + 1 × finalize Opus + 1 × regenerate Opus + 1 × MDT Sonnet + 1 × SBA Sonnet + 1 × follow-up Sonnet). All other steps are local UI + DB + dictation.

**Setup once (not billed)**: login, open `/smart-reporter`, keep this file alongside.

---

## PART A — Static surfaces + state (zero API cost) — 5 min

### A1. Landing scene
1. Open `/smart-reporter`. Confirm you land on the main editor view, not a walkthrough.
2. Confirm the input textarea is present with placeholder text.
3. Confirm the **Review & Finalize** button (green) is visible.
4. Confirm the **Ask RadInsights Intelligence** input box is present.
5. Confirm the model badge ("Pro" or "Standard") is hidden initially.

**Expected**: clean landing, no stale state, all buttons in default position.

### A2. Blank-state guidance
1. Confirm the blank-state guide appears when the editor is empty.
2. Type 10 characters — guide disappears and action buttons enable.
3. Delete all text — guide reappears, action buttons disable (less than 20 chars).

**Expected**: length gate (20 chars) works both ways.

### A3. Autosave
1. Type a short draft (~200 chars): `CT chest: basilar crepitations, raised D-dimer, wells 4.`
2. Wait 3 seconds (debounce).
3. Reload the page.
4. Confirm the draft is restored from sessionStorage.

**Expected**: autosave fires ~2 s after stop typing, restores on reload.

### A4. Anatomy snippet panel — DB search (0 API)
1. Click the Anatomy Snippet search input (right panel).
2. Type `iams` (2+ chars).
3. Confirm typeahead dropdown appears with cached matches (e.g. "Internal Auditory Meati" from DB).
4. **Click** any dropdown result.
5. Confirm the anatomy panel opens with **actual content** (not "No anatomy content available" — that was the earlier bug).
6. Click the × on the anatomy card — confirm it closes.

**Expected**: clickable dropdown, content loads, close works. **If you see "No anatomy content available", tell me immediately — that means the cached-content fix regressed.**

### A5. Session output persistence (0 API)
1. Generate an anatomy snippet (from A4), leave it open.
2. Generate a **second** anatomy snippet (different topic — e.g. "circle of willis").
3. Confirm:
   - The new snippet appears **expanded at the top**
   - The old snippet is **collapsed** (not deleted, just collapsed) below it
   - Click the collapsed old snippet — it expands
4. Click × on one card — confirm only that card is removed, the other stays.

**Expected**: stacked history behaviour (this was the #95/#96 fix).

### A6. Report action buttons — disabled until content
1. Confirm MDT / SBA / Viva / Email Colleague / Email Patient buttons are disabled with no report draft.
2. Type a minimal report: `CT chest: no acute findings. No PE. No pneumonia.`
3. Confirm the buttons now enable.

### A7. View mode toggle
1. Click the view mode toggle (split / stack layout).
2. Confirm layout switches.
3. Reload page — confirm the view mode is persisted.

**Expected**: state persisted in localStorage.

### A8. Model badge (visual only, 0 API)
1. Confirm the badge is hidden initially.
2. (Skip — badge only appears after an AI call.)

**→ STOP if anything in Part A failed. Fix first.**

---

## PART B — Anatomy snippet (1 API call — Sonnet) — 3 min

### B1. Generate anatomy snippet (new topic not in DB)
1. In the Anatomy Snippet search, type `retroperitoneal compartments`.
2. Typeahead should say "No cached match — will generate with RadInsights Intelligence".
3. Click the search arrow button to generate.
4. Confirm:
   - Spinner shows
   - After ~3–5 s, the snippet appears in the anatomy panel
   - Source label reads "RadInsight Intelligence reference" (NOT "From verified database")
   - Content is medically sensible (anterior pararenal, perirenal, posterior pararenal spaces)
5. Go to `/knowledge-hub/anatomy-snippets` (or wherever the anatomy browse is) — confirm the new snippet was auto-saved to the DB for future cache hits.

**Expected**: one API call, content cached for reuse, subsequent lookups are DB-hits (free).

---

## PART C — Finalize workflow (2 API calls — Opus) — 8 min

### C1. First finalize (1 Opus call)
**Input draft** (paste into the editor):
```
CT chest + abdomen + pelvis, 65M, no prior.

Clinical: raised ALP, wt loss.

Findings:
- Large hypodense lesion 4cm right lobe of liver, ill-defined.
- Smaller 1.5cm lesion left lobe.
- No lymphadenopathy.
- Lungs clear.
- Normal bowel.

Impression: liver lesions.
```

1. Click **Review & Finalize**.
2. Confirm:
   - Spinner appears
   - Model badge switches to "Pro" (green) — indicating Opus was used
   - Response populates the PACS output box
   - Indication / Technique / Comparison / Findings / Impression / Recommendation sections are all filled
   - Suggestions / corrections appear in the "Changes Made" section
   - The finalize button transforms into an orange **Regenerate** button
3. Confirm PACS output is editable.

**Expected**: Opus call, full structured report output, button transforms.

### C2. Regenerate (1 Opus call)
1. With the Regenerate button showing, click it.
2. Confirm dialog: "Are you sure you want to regenerate?"
3. Click OK.
4. Confirm:
   - Input has orange glow
   - Go + Cancel buttons replace Send
5. Type a regeneration instruction: `make it more concise and add differentials`
6. Click **Go**.
7. Confirm:
   - "Regenerating..." spinner
   - New PACS output appears
   - Prefix "Rewrite and finalize the full report with the following changes:" was added (visible in network request if you want to inspect)
8. Confirm the model badge still reads "Pro".

**Expected**: regen uses Opus, prefix is injected to bypass the "already finalized" guard.

### C3. Advisory follow-up after finalize (1 Sonnet call — **already counted in C4**)
*(skip if you want, this is a freebie as part of C4.)*

---

## PART D — Report actions (2 API calls — Sonnet) — 5 min

### D1. MDT summary (1 Sonnet call)
1. With a finalized report still in the editor, click **MDT**.
2. Confirm:
   - Confirmation dialog if a prior MDT exists (skip if first time)
   - Model badge shows "Standard" (Sonnet, not Opus, per the routing rule)
   - MDT card appears stacked at top with header "MDT Summary"
   - Content includes: case summary, imaging findings, recommendation, next steps
3. Click the header — confirm it collapses.
4. Click it again — confirm it expands.
5. Click **Copy** button — confirm clipboard toast.

### D2. SBA generation (1 Sonnet call)
1. Click **SBA**.
2. Confirm:
   - New card appears stacked above the MDT card
   - Old MDT card collapses automatically
   - SBA content includes stem + 5 options + rationale
   - "Saved! Access this anytime from SBA Practice" footer appears
3. Confirm the MDT card is still present below (not deleted) and can be expanded.

**Expected**: SBA and Viva always stack (never replace). MDT / email actions replace on re-generation (with confirmation). Sonnet used for all report actions.

### D3. Viva (skip — same mechanism as SBA) (0 API)

### D4. Dismiss stack (0 API)
1. Click × on one card — confirm only that card closes.
2. Confirm the other card stays visible.

---

## PART E — Follow-up questions + report refresh (1 Sonnet call) — 3 min

### E1. Advisory follow-up (1 Sonnet call)
1. After finalizing + generating MDT/SBA, type into the Ask Claude input:
   ```
   what is the differential for a hypoattenuating liver lesion with rim enhancement?
   ```
2. Click Ask.
3. Confirm:
   - **Sonnet** (Standard badge), not Opus — because this is an advisory follow-up after finalization
   - Answer appears in the answer section
   - Answer section does NOT replace the finalized PACS output
   - Markdown rendering works (bullet lists, bold, code)
4. Confirm `state.aiAssistReportText` is NOT set back (no stale preview box reappears).

**Expected**: advisory follow-up uses Sonnet, finalized report text is preserved.

### E2. Full-report guard (0 API — UI-only)
1. Try to click "Ask Claude" with a prompt like: `rewrite this whole report as a different specialty`.
2. Confirm the front-end blocks the full_report response (this guard was the fix for not re-triggering Opus path after finalization).

---

## PART F — Dictation + Safari-specific (0 API — browser Web Speech) — 3 min

### F1. Chrome/Edge dictation
1. Click mic on the editor input.
2. Grant permission.
3. Say: `chest clear no consolidation stop new line impression colon normal study`
4. Confirm:
   - "stop" inserts `.` (period)
   - "new line" inserts a newline
   - "colon" inserts `:`
5. Say: `scratch that`
6. Confirm the last inserted phrase is removed.

### F2. Safari test (if you have a Mac — otherwise skip)
1. Open the page in Safari.
2. Dictate a short phrase: `hello world`
3. Confirm text is inserted **once** (not twice — this was the earlier bug).
4. Say `stop` — confirm period inserted, NOT literal "stop".

**Expected**: Safari fixes hold.

---

## PART G — Cleanup

1. Click **New Report** button.
2. Confirm:
   - Editor clears
   - State resets (no anatomy history, no action cards, no badges)
   - Regenerate button reverts to green Review & Finalize
   - Insights panel clears

---

## API call budget

| Part | Calls | Model |
|---|---|---|
| B1 | 1 | Sonnet (anatomy) |
| C1 | 1 | Opus (finalize) |
| C2 | 1 | Opus (regenerate) |
| D1 | 1 | Sonnet (MDT) |
| D2 | 1 | Sonnet (SBA) |
| E1 | 1 | Sonnet (follow-up) |
| **Total** | **6** | Mixed |

Everything else is free (UI state, dictation, DB lookups, autosave, drawer toggles, filter changes, view modes, collapse/expand).

---

## PART H — Report back format

When you're done, reply with a summary in this shape:

```
Part A: PASS / FAIL (notes)
Part B: PASS / FAIL (notes)
Part C1: PASS / FAIL (notes)
Part C2: PASS / FAIL (notes)
Part D1: PASS / FAIL (notes)
Part D2: PASS / FAIL (notes)
Part E: PASS / FAIL (notes)
Part F: PASS / FAIL (notes)

Issues found:
1. ...
2. ...

API calls actually consumed: X
```

I'll pick up from the first failure, fix it, and we'll continue.

---

## Appendix — what's specifically being tested

| Part | Feature | Fix commit / file |
|---|---|---|
| A4 | Anatomy DB content render | `0dbc0b3` — cached hit returns content_html |
| A5 | Anatomy history stack + collapse | `0dbc0b3` — #95/#96 |
| C1/C2 | Opus routing + Regenerate button | `smart_reporter.html` regen mode |
| D1 | MDT Sonnet routing | `ai_smart_reporter.py` model routing |
| D2 | SBA stack (never replace) | `smart_reporter.html` action rules |
| E1 | Advisory follow-up preserves finalized text | frontend guard |
| F | Dictation "stop" / "new line" + Safari dedup | `0dbc0b3` — speech-to-text.js |

Every test corresponds to a real fix in the recent commit history. Pass = regression held; fail = localised to a specific commit and I can re-patch immediately.
