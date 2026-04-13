# Peer Review v2 — Manual Verification + Global Flag System

> **Status:** Planned
> **Priority:** High
> **Depends on:** Current peer review module (radinsight_peer_review.py)

---

## Goal

Upgrade peer review from a fully automated system to a **hybrid** model:
1. Automated first-pass (existing) → suggests claims and badges
2. **Admin manual verification** → select text, verify via PubMed, add custom verification labels
3. **Global flag system** → any user can flag inaccuracies from any content type, with structured data going to admin dashboard

---

## Part 1: Admin Manual Verification (Select & Verify)

### UX Flow
1. Admin selects text anywhere in the app (anatomy snippet, Smart Reporter output, RadIQ answer, vetting analysis, case discussion, etc.)
2. A popup appears (reusing the case view `showSimpleSelectionMenu` pattern) with:
   - **Verify with PubMed** — searches PubMed for the selected text
   - **Flag Inaccuracy** — opens global flag modal (Part 2)
3. If "Verify with PubMed":
   - PubMed search results appear in a small panel/modal
   - Admin picks the relevant paper(s)
   - Admin can **edit the verification label** (custom text):
     - Default: the selected text (e.g., "stapes 0.5 mm")
     - Custom: admin rewrites to "normal stapes footplate thickness range" for clarity
   - Submit → verified badge injected inline with DOI link
   - Badge tagged as `manual-verified` (distinct from automated `peer-review-badge`)

### Manual Badge Behavior
- `manual-verified` badges **survive content edits** (not stripped on re-save)
- Automated `peer-review-badge` badges **get stripped on edit** (re-run on next load)
- Manual badges stored in a separate `ManualVerification` table (not embedded in HTML):
  ```
  ManualVerification:
    id, content_type, content_id, selected_text, custom_label,
    pubmed_doi, pubmed_title, pubmed_authors, pubmed_year,
    verified_by_user_id, created_at
  ```
- On render: merge automated + manual badges (manual takes precedence)

### Selection Popup Component (Global)
- Reusable JS: `initSelectionVerify(containerSelector)` — attaches to any content area
- Detects text selection → shows floating popup with Verify + Flag buttons
- Admin-only: Verify button hidden for non-admin users
- All users: Flag button always visible
- Style: matches app design (teal border, brand-neutral accent, rounded, subtle shadow)
- Existing case view selection menu migrated to use this shared component

---

## Part 2: Global Flag System

### Current State
- `PeerReviewFlag` model exists with: user_id, content_type, content_id, section, details, claim_text, is_resolved
- Flag button only appears on anatomy snippets (inside `peer_review_flag_button_html`)
- Modal is basic Bootstrap — doesn't match app design
- No dropdown for content type — user types freeform

### Redesigned Flag Modal
- **Matches app design:** uses `.app-content-modal` style (teal header), brand colors
- **Structured input:**
  - Content type dropdown (auto-detected where possible):
    - Anatomy Snippet, Smart Reporter Report, Smart Reporter Q&A, RadIQ Answer, Vetting Analysis, Case Discussion, SBA Question, Viva Question, Reporting Algorithm, Radiology Template, Protocol, Radiology Pearl, TNM Calculator, Incidental Finding Tool
  - Error type dropdown:
    - Incorrect measurement/number, Wrong anatomical term, Outdated guideline, Missing information, Formatting issue, Other
  - Selected text (auto-filled from selection if available)
  - Description (freeform — "What's wrong and what should it say?")
  - Severity: Low / Medium / High (radio buttons)
- **Accessible globally:** flag button in the selection popup + standalone flag button in page footer/nav for content without selection

### Admin Dashboard — Flags Tab
- New tab in admin dashboard: **Content Flags**
- Table view: date, user, content type, error type, severity, selected text, status
- Filter by: content type, error type, severity, resolved/unresolved
- Click to expand: full details, link to the flagged content
- Actions: Resolve (with notes), Dismiss, Edit Content (opens the content in editor)
- Badge count in nav: "3 unresolved flags" (like RadIQ Flags)

---

## Part 3: Stale Badge Handling on Edit

### When Content is Edited (TinyMCE save, API update):
1. Strip all automated `peer-review-badge` spans from HTML
2. Preserve all `manual-verified` badges
3. Set `peer_review_stale = True` on the record (or clear a hash)
4. Next load: on-demand peer review re-runs for automated badges
5. Manual badges render from `ManualVerification` table (always fresh)

### Implementation:
- `_strip_automated_badges(html)` utility in `radinsight_peer_review.py`
- Called in the Smart Reporter anatomy save path and any TinyMCE save endpoint
- Manual badges stored in DB table, not in HTML — so they're never lost

---

## Files to Create/Modify

| File | Action | Status |
|------|--------|--------|
| `models.py` — `ManualVerification` | New model for admin-verified claims | TODO |
| `models.py` — `PeerReviewFlag` | Add error_type, severity columns | TODO |
| `radinsight_peer_review.py` | Add `_strip_automated_badges()`, manual badge merge | TODO |
| `static/js/selection-verify.js` | New — global selection popup (Verify + Flag) | TODO |
| `static/css/selection-verify.css` | New — popup + flag modal styles | TODO |
| `templates/partials/_flag_modal.html` | New — redesigned global flag modal | TODO |
| `templates/partials/_verify_panel.html` | New — PubMed search results panel | TODO |
| `admin_routes.py` | Add flags dashboard tab + resolution endpoints | TODO |
| `templates/admin_dashboard.html` | Add Content Flags tab | TODO |
| `reporting_routes.py` | Wire selection-verify into anatomy save path | TODO |
| `templates/smart_reporter.html` | Init selection-verify on output areas | TODO |
| `templates/view_case.html` | Migrate to shared selection component | TODO |
| `pubmed_service.py` | Add endpoint for frontend PubMed search | TODO |

---

## Content Types (for flag dropdown + ManualVerification)

| Value | Display Name |
|-------|-------------|
| anatomy_snippet | Anatomy Snippet |
| smart_reporter_report | Smart Reporter Report |
| smart_reporter_qa | Smart Reporter Q&A |
| radiq_answer | RadIQ Answer |
| vetting_analysis | Vetting Analysis |
| case_discussion | Case Discussion |
| sba_question | SBA Question |
| viva_question | Viva Question |
| reporting_algorithm | Reporting Algorithm |
| radiology_template | Radiology Template |
| imaging_protocol | Imaging Protocol |
| radiology_pearl | Radiology Pearl |
| tnm_calculator | TNM Calculator |
| incidental_finding_tool | Incidental Finding Tool |

---

## Error Types (for flag dropdown)

| Value | Display Name |
|-------|-------------|
| incorrect_number | Incorrect measurement or number |
| wrong_anatomy | Wrong anatomical term |
| outdated_guideline | Outdated guideline or reference |
| missing_info | Missing important information |
| formatting | Formatting or display issue |
| hallucination | AI hallucination / fabricated claim |
| other | Other |

---

## Priority Order

1. **Global flag modal** (Part 2) — highest user impact, any user can report issues
2. **Admin flags dashboard** (Part 2) — admin needs to see and act on flags
3. **Stale badge handling** (Part 3) — prevent stale verification badges
4. **Admin manual verification** (Part 1) — powerful but admin-only, can come later
