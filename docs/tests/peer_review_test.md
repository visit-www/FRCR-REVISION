# RadInsight Peer Review Module — Test Plan

> Step-by-step manual testing guide. Test each section independently.
> Prerequisite: app running locally (`flask run` or `vercel dev`), logged in as admin.

---

## Part A: Anatomy Snippets (Primary Target)

### A1. Two-Step Search Flow
1. Go to Smart Reporter
2. In the Anatomy panel, type "circle of Willis" in the search box
3. **Expected:** Live typeahead dropdown appears with cached results (if any exist)
4. Press Enter or click Send
5. **If DB match exists:** Snippet loads immediately with "From verified database" source text
6. **If no DB match:** A prompt appears: "No cached anatomy snippet found for 'circle of Willis'" with a "Generate with RadInsight Intelligence" button and a Cancel button
7. Click "Generate with RadInsight Intelligence"
8. **Expected:** Loading spinner → snippet generates → displays with "RadInsight Intelligence reference" source text

### A2. Peer Review Badges on Anatomy Snippet
1. Generate a new anatomy snippet for "hepatic segments" (or any topic with measurements)
2. **Expected:** Snippet displays with:
   - Disclaimer banner at top: "AI-Generated Revision Aid — Verify critical measurements..."
   - Green tick badges next to PubMed-verified measurements (clickable → DOI link)
   - Amber warning badges next to unverified measurements (hover → tooltip: "This number came from the AI...")
   - Verification summary badges: "X verified" (green) + "Y unverified" (amber)
3. Click a green tick badge
4. **Expected:** Opens PubMed article in new tab (DOI or PubMed link)
5. Hover over an amber badge
6. **Expected:** Tooltip appears with caution message

### A3. Verified References Section
1. On the same anatomy snippet, scroll to the bottom
2. **Expected:** "Verified References" card with:
   - Radiopaedia article link (if article exists for this topic) — clickable, opens real article page (NOT a search page)
   - PubMed papers with: title (clickable DOI), author, journal, year
3. Click the Radiopaedia link
4. **Expected:** Opens `radiopaedia.org/articles/{slug}` — a real article page, not `/search?q=...`
5. Click a PubMed reference
6. **Expected:** Opens the actual paper via DOI or PubMed link

### A4. Flag Inaccuracy Button
1. On the anatomy snippet, find the "Flag Inaccuracy" button at the bottom
2. Click it
3. **Expected:** Modal appears with text area: "Help us improve accuracy..."
4. Type a description and click "Submit Flag"
5. **Expected:** Toast: "Thank you — flag submitted for review." Modal closes.
6. Check DB: `SELECT * FROM peer_review_flag ORDER BY created_at DESC LIMIT 1;`
7. **Expected:** Row exists with your user_id, content_type='anatomy_snippet', details matching your input

### A5. Cached Snippet Click
1. Type "circle" in anatomy search
2. If typeahead shows a cached result, click it
3. **Expected:** Snippet loads directly (no "Generate?" prompt — it's a known cached item)

---

## Part B: Smart Reporter Follow-Up Q&A

### B1. Teaching Point Verification
1. In Smart Reporter, enter a report with findings (e.g. "3cm liver lesion, arterial enhancement, washout on portal venous phase")
2. Ask Claude to finalize
3. **Expected:** Insights panel shows teaching_point. Below insights, peer review section appears if teaching point contains verifiable numbers
4. Check for disclaimer + reference section below insights

### B2. Follow-Up Answer Verification
1. After finalization, ask a follow-up: "What is the Bosniak classification for cystic renal lesions?"
2. **Expected:** Answer contains factual claims with numbers. Peer review data returned in response.
3. Check browser DevTools Network tab → response JSON should include `peer_review` field with `verification_summary`

---

## Part C: SBA / Viva Actions

### C1. SBA Peer Review
1. Generate a report and finalize it
2. Click SBA action button
3. **Expected:** SBA questions generated. If explanations contain numerical claims:
   - Disclaimer banner appended after the SBA content
   - Verified References section appended
4. Check that references are real PubMed links (not fabricated)

### C2. Viva Peer Review
1. Click Viva action button on same report
2. **Expected:** Same as C1 — disclaimer + references appended if factual claims found

---

## Part D: RadIQ

### D1. RadIQ Answer Verification
1. Go to RadIQ
2. Ask: "What is the Fleischner Society guidelines for pulmonary nodule follow-up?"
3. **Expected:** Answer generated with numerical thresholds (e.g. "6mm", ">8mm")
4. Below the answer, disclaimer + verified references section should appear
5. Check response JSON in DevTools: `peer_review.verification_summary` should show claim counts

### D2. RadIQ Radiographer Category
1. Switch to Radiographer category
2. Ask: "What is the maximum contrast dose for a CT pulmonary angiogram?"
3. **Expected:** Answer with dose values. Peer review section appended.

---

## Part E: Vetting

### E1. Vetting Analysis Verification
1. Go to Vetting tool
2. Enter referral: "58M, known PE, on warfarin, new SOB, D-dimer elevated. ?recurrent PE"
3. **Expected:** Analysis returned with guideline_citation. Check response JSON in DevTools for `peer_review` field
4. **Expected:** `peer_review.verification_summary` shows whether guideline citation was verified

---

## Part F: Admin Content Generation

### F1. Admin Algorithm Generation
1. Go to Admin > Reporting Algorithms > Generate
2. Generate an algorithm for a topic with measurements
3. **Expected:** Response JSON includes `peer_review` field with verification summary
4. Admin can see which claims were verified before publishing

### F2. Admin Pearl Generation
1. Go to Admin > Generate Pearl
2. Generate a pearl for "hepatocellular carcinoma on MRI"
3. **Expected:** Response JSON includes `peer_review` field

---

## Part G: Admin Cost Tracking

### G1. Inline Cost Badge
1. As admin, use Smart Reporter and ask any question
2. **Expected:** Next to the model badge (Pro/Standard), a small monospace badge appears showing the API cost (e.g. `$0.0045`)
3. Non-admin users should NOT see this badge

### G2. Cost Dashboard
1. Go to Admin Dashboard > AI Costs tab
2. **Expected:** Opus model now appears in the "Cost by Model" chart (was missing before)
3. Verify totals make sense with the new Opus pricing ($15/$75 per M tokens)

---

## Part H: Prompt Guardrails

### H1. Anatomy Temperature 0
1. Generate the same anatomy topic twice (force_regenerate both times)
2. **Expected:** Outputs should be very similar (not identical due to API randomness, but close). Temperature 0 produces deterministic output.

### H2. Uncertainty Expression
1. Generate anatomy for a rare topic (e.g. "aberrant right subclavian artery")
2. **Expected:** Where the model is uncertain about prevalence, it should use hedge language: "approximately", "reported range varies", "up to"

### H3. LLM Self-Extracted Claims
1. Generate an anatomy snippet and check response in DevTools
2. **Expected:** The parsed JSON should include a `verifiable_claims` array with claims the model identified, each with `claim`, `type`, and `search_terms` fields

---

## Part I: Anatomy Snippet UX (#94-96)

### I1. Live Typeahead
1. Type slowly in anatomy search: "c...i...r...c...l...e"
2. **Expected:** After 2+ characters, suggestions appear within ~300ms. Results update as you type.

### I2. No-Match Confirm
1. Type a topic that definitely doesn't exist in DB (e.g. "xyzzy nonexistent anatomy")
2. Press Enter
3. **Expected:** Prompt appears: "No cached anatomy snippet found..." with Generate + Cancel buttons
4. Click Cancel
5. **Expected:** Prompt disappears, nothing generated

### I3. Collapse on New Snippet
1. Generate or load 2 anatomy snippets in sequence
2. **Expected:** Only the newest snippet is expanded. Older ones are collapsed with "(click to expand)" label

### I4. Persist Until Dismissed
1. Load an anatomy snippet
2. Switch to a different panel (e.g. load a tool)
3. Switch back to anatomy
4. **Expected:** Previous snippet is still visible (collapsed)
5. Only clears on: clicking × on a snippet, or New Report

---

## Regression Checks

- [ ] Smart Reporter report generation (no peer review) works unchanged
- [ ] MDT summary (no peer review) works unchanged
- [ ] Email actions (no peer review) work unchanged
- [ ] Non-admin users do NOT see cost badge
- [ ] App startup doesn't error (PeerReviewFlag table created by db.create_all)
- [ ] Anatomy snippet loads correctly for cached entries picked from typeahead
