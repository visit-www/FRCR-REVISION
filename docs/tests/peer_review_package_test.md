# RadInsight Peer Review Package — Test Plan

> Step-by-step test plan for the `radinsight_peer_review.py` standalone package.
> Tests cover: claim extraction, PubMed verification, Radiopaedia HEAD checks,
> badge rendering, disclaimer banners, flag inaccuracy, and integration points.
>
> **Prerequisites:** App running locally or on Vercel, logged in as admin.
> Run tests in order — each section builds on the previous one.

---

## Part 1: Claim Extraction

### 1.1 LLM Self-Extraction (verifiable_claims field)
1. Generate a NEW anatomy snippet (force_regenerate if cached): topic = "circle of Willis"
2. Open browser DevTools → Network tab → find the `/api/smart-reporter/anatomy` POST response
3. **Expected:** Response JSON should contain the AI-generated anatomy data. Check if the raw Claude response (before parsing) includes a `verifiable_claims` array
4. If present: each claim should have `claim`, `type`, and `search_terms` fields
5. **Expected types:** prevalence, measurement, threshold

### 1.2 Regex Fallback
1. Generate an anatomy snippet for a simple topic: "femoral triangle"
2. Check the response — if `verifiable_claims` is empty or missing, the module falls back to regex
3. **Expected:** Measurements in `measurements.normal` and `measurements.abnormal_threshold` fields should still be detected and badged
4. **Verify:** Look for green/amber badges next to numerical values in the rendered snippet

### 1.3 Merged Claims (LLM + Regex)
1. Generate a snippet with many measurements: "aortic root dimensions"
2. **Expected:** Both LLM-extracted claims AND regex-found claims should appear
3. No duplicate badges for the same number
4. The total claim count (in the disclaimer banner) should be >= the count of measurements in the snippet

### 1.4 No Claims (Text Without Numbers)
1. Generate a snippet for a topic with few numbers: "MRI safety zones"
2. **Expected:** Disclaimer banner still appears but may show "0 verified, 0 unverified" or no badges at all
3. **Verify:** No JavaScript errors in console

---

## Part 2: PubMed Verification

### 2.1 Verified Claim (Green Badge)
1. Generate snippet for "circle of Willis" or "hepatic segments"
2. Look for green tick badges (<i class="fas fa-check-circle text-success">)
3. Click a green badge
4. **Expected:** Opens PubMed article or DOI link in new tab — must be a REAL article page

### 2.2 Unverified Claim (Amber Badge)
1. In the same snippet, look for amber warning badges (<i class="fas fa-exclamation-triangle text-warning">)
2. Hover over an amber badge
3. **Expected:** Tooltip appears: "This number came from the AI. We couldn't find a paper to back it. Treat with caution."
4. **Verify:** Tooltip uses Bootstrap tooltip (data-bs-toggle="tooltip"), not native title

### 2.3 PubMed Search Failure
1. Generate snippet for a very niche topic: "aberrant right subclavian artery imaging pitfalls"
2. **Expected:** Most claims should be amber (PubMed unlikely to have exact matches)
3. **Verify:** App doesn't error — graceful degradation to "unverified"

### 2.4 Caching
1. Generate the same snippet twice (same topic, within 24 hours)
2. **Expected:** Second request should be faster (cache hit in `cache/peer_review/`)
3. Check: `ls cache/peer_review/` — should contain JSON files

---

## Part 3: Radiopaedia Article Verification

### 3.1 Valid Article URL
1. Generate snippet for "circle of Willis"
2. In the "Verified References" section, look for a Radiopaedia link
3. **Expected:** Link goes to `https://radiopaedia.org/articles/circle-of-willis` (or similar real article page)
4. Click the link — should open a real Radiopaedia article, NOT a search page

### 3.2 No Article (Fallback)
1. Generate snippet for a very specific topic: "quadrilateral space syndrome"
2. **Expected:** If Radiopaedia doesn't have an article, no Radiopaedia link is shown (not a search page fallback)
3. **Verify:** Only PubMed references appear in the references section (if any)

### 3.3 Redirected Article
1. Generate snippet for "CoW" or a topic where Radiopaedia redirects the slug
2. **Expected:** The HEAD check follows redirects and uses the final URL
3. Link should still be clickable and valid

---

## Part 4: HTML Rendering

### 4.1 Disclaimer Banner
1. Generate any anatomy snippet
2. **Expected:** A teal-bordered banner at the TOP of the snippet:
   - Shield icon + "AI-Generated Revision Aid"
   - "Verify critical measurements against your textbook before clinical use."
   - Green badge: "X verified" (if any claims verified)
   - Amber badge: "Y unverified" (if any claims unverified)

### 4.2 Inline Badges in Anatomy Tables
1. In the generated snippet, check the Measurements table
2. **Expected:** Each measurement value (e.g., "< 40 mm", "3-5 cm") has a green or amber badge inline, right after the text
3. Check Normal Variants table — prevalence values should also have badges

### 4.3 Verified References Section
1. Scroll to the bottom of the snippet
2. **Expected:** "Verified References" card with:
   - Radiopaedia article link (globe icon, blue "Radiopaedia" badge)
   - PubMed articles (green file icon, "PubMed" badge)
   - Each PubMed entry: title (clickable), author, journal (italic), year

### 4.4 Flag Inaccuracy Button
1. At the bottom of the snippet, find "Flag Inaccuracy" button (red outline)
2. Click it
3. **Expected:** Modal opens with:
   - Title: "Flag Inaccuracy"
   - Text area: "Help us improve accuracy. Describe what you believe is incorrect."
   - Cancel + Submit Flag buttons
4. Type a description, click Submit Flag
5. **Expected:** Toast: "Thank you — flag submitted for review." Modal closes.

---

## Part 5: Integration — Smart Reporter

### 5.1 Teaching Point Verification
1. Enter a report with findings, finalize it
2. Check the Insights section for teaching_point
3. **Expected:** If teaching point contains numbers, peer review data appears below insights
4. Check response JSON in DevTools: `peer_review.verification_summary` should have claim counts

### 5.2 Follow-Up Answer Verification
1. After finalization, ask: "What is the Bosniak classification system?"
2. **Expected:** Answer may contain numerical thresholds. Peer review section renders if claims found.

### 5.3 SBA Action
1. Click SBA action button
2. **Expected:** SBA HTML generated. If explanations contain numbers:
   - Disclaimer appended after SBA content
   - Verified References section appended
3. Click a reference link — must open real PubMed/DOI page

### 5.4 Viva Action
1. Click Viva action button
2. **Expected:** Same as 5.3 — disclaimer + references appended if numerical claims exist

---

## Part 6: Integration — RadIQ

### 6.1 General Query
1. Go to RadIQ, ask: "What are the Fleischner Society guidelines for pulmonary nodule follow-up?"
2. **Expected:** Response contains thresholds (6mm, 8mm, etc.)
3. Disclaimer + references appended below the answer
4. Check DevTools: `peer_review.verification_summary` in response JSON

### 6.2 Radiographer Query
1. Switch to Radiographer category, ask: "What is the maximum IV contrast dose for CT?"
2. **Expected:** Response with dose values. Peer review section present.

---

## Part 7: Integration — Vetting

### 7.1 Full Analysis (Not Quick Clean)
1. Go to Vetting, enter referral text: "58M, chest pain, troponin negative, D-dimer elevated. ?PE"
2. Click Analyse (not Quick Clean)
3. **Expected:** Analysis result with guideline_citation
4. Check DevTools response: `peer_review` field present with verification_summary

### 7.2 Quick Clean
1. Click Quick Clean with any referral text
2. **Expected:** Quick Clean DOES call the AI (it analyses the referral). Cost badge should appear on the result heading.
3. Peer review data may be minimal (cleaned text has few verifiable claims)

---

## Part 8: Integration — Admin Content Generation

### 8.1 Pearl Generation
1. Admin > Generate Pearl for "hepatocellular carcinoma on MRI"
2. Check response JSON in DevTools
3. **Expected:** `peer_review` field with verification_summary

### 8.2 Algorithm Generation
1. Admin > Reporting Algorithms > Generate for any topic
2. Check response JSON
3. **Expected:** `peer_review` field present

---

## Part 9: Flag Inaccuracy Backend

### 9.1 Flag Submission
1. Click Flag Inaccuracy on any snippet/response
2. Submit with details
3. **Expected:** `POST /api/peer-review/flag` returns `{"success": true, "flag_id": N}`

### 9.2 Database Verification
1. Check DB: `SELECT * FROM peer_review_flag ORDER BY created_at DESC LIMIT 5;`
2. **Expected:** Row with your user_id, content_type, details text

### 9.3 Empty Details Rejected
1. Click Flag Inaccuracy, leave text area empty, click Submit
2. **Expected:** Toast: "Please describe the inaccuracy." — no submission

---

## Part 10: Cost Tracking

### 10.1 Peer Review Doesn't Add AI Cost
1. Peer review uses PubMed (free) and Radiopaedia HEAD checks (free) — no Anthropic API calls
2. **Expected:** No additional entries in AIAuditLog for peer review itself
3. The only tracked cost is the original AI generation call

### 10.2 Admin Cost Badge Shows
1. As admin, generate any anatomy snippet
2. **Expected:** Cost badge (e.g., `$0.0150`) appears next to model badge
3. This cost is for the Claude API call, not the peer review post-processing

---

## Part 11: Edge Cases

### 11.1 Empty AI Response
1. If Claude returns empty content (rare), peer review should not crash
2. **Expected:** Snippet shows with disclaimer but no badges (graceful fallback)

### 11.2 PubMed Service Down
1. If PubMed API is unreachable, all claims should default to "unverified"
2. **Expected:** No crash — amber badges everywhere, references section may be empty

### 11.3 Radiopaedia HEAD Timeout
1. If radiopaedia.org is slow/down, HEAD check should timeout after 5s
2. **Expected:** No Radiopaedia link shown, PubMed references still work

### 11.4 Very Large Snippet
1. Generate snippet for a broad topic: "abdominal anatomy comprehensive"
2. **Expected:** Multiple claims extracted and verified. No timeout on the peer review post-processing.
3. **Performance:** Total peer review overhead should be < 1 second (PubMed calls run in parallel)

---

## Regression Checks

- [ ] Smart Reporter report generation (no peer review) works unchanged
- [ ] MDT summary (no peer review) works unchanged
- [ ] Email actions (no peer review) work unchanged
- [ ] Non-admin users do NOT see cost badge
- [ ] Anatomy snippet from DB cache loads without peer review (only fresh generation triggers it)
- [ ] App startup doesn't error (PeerReviewFlag table auto-created)
- [ ] Base.html tooltip init function exists only for admin users
