# Vetting Tool — End-to-End Test Plan

**Goal**: test every feature of the Vetting Tool workflow in a single session, with maximum coverage and minimum AI API calls. Each step is interactive — run it, and if it fails, **stop and tell me what went wrong**; I'll fix it before you move to the next step.

**Cost control**: the full run uses **5 AI calls total** (1 × Quick Clean + 3 × Analyse & Vet + 1 × Generate Protocol). Everything else is UI interaction, drawer toggles, filter changes, and button clicks — zero API cost.

**Setup once (not billed)**: login as an admin account; open `/vetting` in a browser. Keep this file open alongside.

---

## PART A — Static surfaces (zero API cost) — 5 min

These steps don't call any AI. Do them first to catch UI / routing / link issues before you burn any API credit.

### A1. Main nav + Quick Reference dropdown
1. Load any logged-in page (e.g. `/smart-reporter`).
2. Open the **Resources** dropdown. Confirm it shows exactly: Radiology Tools · Clinical Guidelines & Safety · TNM Calculators · Vetting Tool. **No Vetting Essentials, no Contrast Card here.**
3. Open the **Quick Ref** dropdown. Confirm it shows: Vetting Essentials · Contrast Card · Paediatric CT Protocols.
4. On mobile (narrow viewport or DevTools phone preview), open the offcanvas — confirm **both** collapsible sections (Resources + Quick Reference) are present and expand correctly.

**Expected**: all links navigate to the correct URL, no 404, no JS console errors.

### A2. Vetting Essentials card (public)
1. Navigate to `/vetting-essentials`.
2. Confirm breadcrumb: Home → Vetting Tool → Vetting Essentials.
3. Click through all 5 main tabs: **Phases · CECT Timing · Oral Contrast · Rectal Contrast · Liver Dual Supply**.
4. On the Oral Contrast tab, click both sub-tabs (**Adult** and **Paediatric**). Confirm the Paediatric table shows all 6 age bands (Newborn–6 mo through 12 y and above) and the NPO / mixing cards.
5. On the CECT Timing tab, change each of the 4 dropdowns (scanner, weight, rate, phase). Confirm the calculator output updates live (recommended volume, injection time, scan start time).

**Expected**: no broken layout, all tabs switch cleanly, calculator updates on every change.

### A3. Contrast Card (public)
1. Navigate to `/contrast-reaction-card`.
2. Confirm title shows as "**Contrast Card**" (not "Contrast Reaction Card").
3. Breadcrumb: Home → Quick Reference → Contrast Card.
4. Click through all 6 tabs: Premedication · Acute Reactions · Extravasation · Renal/CI-AKI · Special Populations · Paed Calculator.
5. On the **Paed Calculator** tab, click the small ℹ️ info icon next to the intro paragraph. Confirm the **"Dose rationales on which the calculator works"** info card opens with all 8 drug rows (Epinephrine IV/IM, Diphenhydramine, Saline bolus, Hydrocortisone, Prednisone, Atropine, EpiPen selector).
6. Enter weight `25` kg in the calculator input. Confirm all outputs populate instantly (epinephrine, fluids, diphenhydramine, etc.).
7. Close the info card with the × button.

**Expected**: all doses clamp correctly at maxima, info card toggles smoothly.

### A4. Paediatric CT Protocols reference (public)
1. Navigate to `/paediatric-ct-protocols`.
2. Breadcrumb: Home → Vetting Tool → Protocol Library → Paediatric CT Protocols.
3. Click **"Back to Protocol Library"** link — confirm it takes you to `/vetting/protocols`.
4. Return to `/paediatric-ct-protocols`.
5. Confirm the **Global dosing card** at top shows 2 cc/kg · 2 cc/s · Hand inject tiles.
6. Use the **Region filter** dropdown — select "Head & Neuro". Confirm only head/neuro cards show.
7. Use the **Contrast filter** dropdown — select "With contrast". Confirm cards filter correctly.
8. Type `append` in the search box. Confirm only the Appendicitis card shows.
9. Clear all filters — confirm all 13 cards return.

**Expected**: 13 protocols total across regions. Filter chaining works. Source citation at the foot reads "TRA Medical Imaging…".

### A5. Vetting Tool main page — drawers + nav
1. Navigate to `/vetting`.
2. Click the **"Protocol Library"** button at the top — confirm it opens `/vetting/protocols`.
3. Back on `/vetting`, click **"Contrast Card"** — confirm the offcanvas drawer slides out from the right and loads all 6 tabs.
4. Close it. Click **"Vetting Essentials"** — confirm the offcanvas drawer slides out with all 5 tabs including the Oral Contrast sub-tabs.
5. Close the drawer. Click the mic icon next to the referral textarea — confirm browser prompts for microphone (dictation support).

**Expected**: both drawers open, all content loads, no overlap.

### A6. Protocol Library (user-facing)
1. Navigate to `/vetting/protocols`.
2. Confirm the **Paediatric CT Protocols** banner (orange gradient, child icon) appears prominently above the tabs.
3. Click the banner — confirm it navigates in the **same tab** (not new tab) to `/paediatric-ct-protocols`.
4. Back to `/vetting/protocols`. Click through both tabs: **All Protocols** and **My Protocols**.
5. Change the **Modality** filter to `CT`. Confirm list updates.
6. Type a search term (e.g. `liver`) — confirm client-side filter works.
7. Click any protocol card to open the detail modal. Confirm the HTML renders cleanly.

**Expected**: banner visible + clickable, filters work, detail modal shows styled HTML (table-based, orange highlight).

### A7. Admin protocol management
1. Navigate to `/vetting/admin/protocols` (admin-only).
2. Confirm the **Paediatric CT Protocols** banner is also at the top here (same as A6).
3. Confirm the filter bar has **4 filters**: Modality · Source · Status · Search.
4. Use the **Source** filter — try `Swansea` (should show 35), `Claude Opus` (should show 33), `mrimaster` (should show 24).
5. Use the **Status** filter — `Verified` (should show 172), `To be verified` (should show 57).
6. Combine: Modality = CT + Source = Claude Opus + Status = To be verified → should show 33.
7. Click a protocol's Edit button — confirm modal opens with all fields pre-filled.
8. Close without saving.

**Expected**: filters combine correctly, counts match the JSON master file. No data loss on modal close.

**→ STOP AT THIS POINT if anything in Part A failed. Fix first, then resume.**

---

## PART B — AI-backed vetting workflow (5 API calls) — 10 min

Now the AI-billed tests. Each case is chosen to exercise a specific feature — do not repeat calls unnecessarily.

### B1. Quick Clean — safety checks only (1 API call, Haiku/fast)
**Input** (paste into `/vetting` textarea):
```
45F, headache for 3 weeks, worse in mornings. PMH: breast Ca 2019, nil else. On tamoxifen. Eiblled on 2 occasions ?mets. No focal neuro. GCS 15. Ref: Dr Jones GP.
```
Modality hint: **MRI**

Click **Quick Clean** (not Analyse & Vet).

**Expected**:
- Spinner shows → result card appears
- Cleaned referral text appears (typo "Eiblled" corrected to something sensible, "ref" converted to full name)
- Safety checks populated (eGFR not applicable for MRI, allergy, pregnancy status asked, renal status)
- Body section: Brain
- No protocol list populated (Quick Clean skips protocol matching)
- PII guard does NOT flag anything (Dr Jones is a referrer, not a patient identifier — if it flags, note it for me)

**If the cleaned text is wrong or safety checks miss key items, tell me which.**

### B2. Full Analyse & Vet — appendicitis (1 API call) — tests the vetting fix from earlier
**Input**:
```
65-year-old male presented with abdominal pain. Initially central but then progressed to right iliac fossa. One episode of vomiting. Low-grade fever. White blood cell count 14, C-reactive protein 34.
```
Modality hint: **CT**

Click **Analyse & Vet** (full pipeline).

**Expected**:
- AI cites iRefer for suspected appendicitis
- **Protocol Match section finds a library protocol** (earlier this was broken — the 54 matched prod CT protocols include CT Abdomen/Pelvis variants, the fix should match now)
- Suggested protocol: CT Abdomen + Pelvis with IV contrast
- Safety: eGFR required, allergy check
- AI recommendation cites NICE or iRefer

**If "No library protocol matched" appears — tell me immediately, that's a regression of the earlier fix.**

### B3. Full Analyse & Vet — CTPA pregnancy (1 API call) — tests safety guard + pregnancy protocol
**Input**:
```
28F, 26/40 pregnant, sudden onset pleuritic chest pain, SOB, tachycardia HR 112. D-dimer raised (6.8, age-adjusted), Wells 4.5. ?PE. No leg symptoms.
```
Modality hint: **CT**

Click **Analyse & Vet**.

**Expected**:
- Pregnancy confirmation prompt appears **before** inserting recommendation (this was one of the PR3 fixes)
- After confirmation, recommendation includes: CTPA pregnancy protocol, foetal dose considerations, NICE NG158
- Protocol Match: should find "CT Pulmonary Angiography — Pregnancy" (PR2 N1 protocol, tagged `_origin: radinsights`)
- Safety: eGFR check, pregnancy confirmation explicit
- Rationale textarea for pregnancy should be visible

**If pregnancy confirmation does not prompt before insert, or CTPA pregnancy protocol not matched, tell me.**

### B4. Generate Protocol (no library match scenario) (1 API call)
**Input** (deliberately obscure to force AI generation):
```
35M, suspected pre-sacral teratoma on US, needs pre-operative CT with fistula tracking.
```
Modality hint: **CT**

Click **Analyse & Vet**.

**Expected**:
- Likely "No exact library protocol matched" (pre-sacral teratoma is unusual)
- A **"Generate Protocol with AI"** button appears
- Click it → AI generates a bespoke protocol with phases, contrast dose, coverage
- AI cites physiological principle and notes "verify against local policy"

**If the generate button doesn't appear or the generated protocol is nonsensical, tell me.**

### B5. Save + edit personal protocol (0 API calls — pure DB)
1. From the B4 result, click "Save to my protocols" (if that button exists) OR go to `/vetting/protocols`, click any admin protocol, and click "Copy to my library".
2. Go to the **My Protocols** tab.
3. Confirm your copied protocol is there with origin = `personal`.
4. Click Edit, change one field (e.g. the shorthand), save.
5. Reload the page — confirm the edit persisted.
6. Delete the personal protocol.

**Expected**: CRUD works cleanly on personal protocols. The admin master protocols are untouched.

### B6. Vetting history (0 API calls)
1. Navigate to `/vetting/history` (if the route exists).
2. Confirm the 4 vetting sessions from B1–B4 are listed with timestamps.
3. Open one — confirm the full session data is retrievable.

**Expected**: all 4 sessions saved. If only 3, something truncated — tell me.

---

## PART C — Regression + edge cases (0–2 API calls) — 5 min

### C1. PII guard (0 API calls — client-side engine)
Paste this into the vetting textarea:
```
Mr John Smith, NHS 123 456 7890, DOB 15/03/1958, lives at 42 Acacia Avenue. Has presented with...
```

**Expected**:
- PII Guard highlights: John Smith (name), NHS number, DOB, address
- Red shield badge in card header appears
- API buttons (Analyse / Quick Clean) are greyed out until PII resolved
- Bulk "Redact all" or "Remove all" dropdown works

Resolve all PII via Redact. Confirm buttons re-enable.

### C2. Dictation (0 API calls — browser Web Speech)
1. Click the mic button next to the referral textarea.
2. Grant permission.
3. Say: "thirty two year old female with acute right iliac fossa pain stop new line white cell count twelve"
4. Observe:
   - "stop" should insert a full stop (not literally type "stop")
   - "new line" should insert a newline
   - On Safari, text should NOT be inserted twice (the double-insert fix)

**Expected**: transcribed text is clean, commands are recognised.

### C3. Rate limit visibility (0 API calls — UI check)
1. Check the usage counter on `/vetting` — confirm it shows remaining AI calls for the month.
2. After Part B, the counter should have decreased by ~5.

**Expected**: counter decrements visibly after each AI call.

### C4. CORS / preflight (0 API calls)
Open DevTools Network tab, click **Analyse & Vet** once more on any small input. Confirm no CORS errors, no 4xx / 5xx other than intentional rate limits.

---

## PART D — Cleanup + sign-off

1. Delete any test personal protocols you created in B5.
2. Delete test vetting sessions in B1–B4 if you want a clean history.
3. Report back to me with a **PASS / FAIL summary per section** and any issues found.

**Total API calls consumed**: up to **5** (B1 × Haiku + B2 × Sonnet + B3 × Sonnet + B4 × Sonnet protocol generation + 1 buffer).

**Estimated cost**: roughly 5 × average Sonnet request ≈ minimal spend.

---

## Appendix — what's specifically being tested

| Part | Feature | File(s) tested |
|---|---|---|
| A1 | Main nav split | `templates/base.html` |
| A2 | Vetting Essentials card + sub-tabs | `_vetting_essentials.html` |
| A3 | Contrast Card + info card | `_contrast_reaction_card.html` |
| A4 | Paed CT reference page | `paediatric_ct_protocols.html` |
| A5 | Vetting drawers | `vetting.html` |
| A6 | User protocol library + banner | `vetting_protocols.html` |
| A7 | Admin filters (source / status / modality) | `vetting_admin.html` + `vetting_routes.py` |
| B1 | Quick Clean — Haiku pathway | `ai_vetting.py` |
| B2 | `_search_protocols` fix for appendicitis | `vetting_routes.py` |
| B3 | Pregnancy confirmation guard + CTPA pregnancy protocol | PR2 N1 + PR3 |
| B4 | Fallback AI protocol generation | `vetting_routes.py generate_protocol` |
| B5 | Personal protocol CRUD | `vetting_routes.py` |
| B6 | Session history persistence | `VettingSession` model |
| C1 | PII Guard v2 | `pii-guard.js` |
| C2 | Safari dictation fixes | `speech-to-text.js` |
| C3 | Rate limit counter | `_check_ai_rate_limit` |

Every tick here corresponds to something we've actually changed in the last few sessions. If any step fails, the regression is localisable.
