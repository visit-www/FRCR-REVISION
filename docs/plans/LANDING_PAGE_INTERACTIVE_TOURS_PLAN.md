# Landing Page Interactive Tours — Implementation Plan

> **Status:** Planned
> **Priority:** High
> **Keyword:** `RADINSIGHTS-TOURS-2026`

---

## Goal

Replace passive marketing with interactive, hands-on tours that let prospective users generate real outputs before signing up. Maximise signup conversion through positive marketing (headlines, CTAs, social proof) and improve SEO visibility through rich static content surrounding each tour.

## Key Selling Points (weave into all copy)

1. Saves time — faster reporting, vetting, MDT prep
2. Safety net — catches laterality errors, staging mismatches, missed nuances
3. No hallucinations — grounded in real clinical data, protocols, and guidelines
4. Real-time teaching �� every interaction is a learning opportunity
5. Concrete examples:
   - Report says "4 cm lung mass" but staging is T3N0M0 — catches discrepancy
   - Oropharyngeal cancer staged without HPV status consideration
   - Vetting catches missing contrast allergy history

---

## Phase 1 — Ship Fast (4 tours)

### Tour 1: Smart Reporter

**What the user does:**
- Picks a pre-loaded oncology case (e.g., lung cancer with staging complexity)
- Types a shorthand report in the draft box
- Clicks Finalise — sees structured report generated
- Adds impressions and recommendations
- Asks a clinical question — gets AI answer
- Searches for an anatomy snippet

**Implementation:**
- Pre-baked AI responses stored as JSON (no live Anthropic calls)
- Simulated typing effect for AI output to feel live
- Template/algorithm search works against real static data
- Guided overlay with numbered steps (1 of 6, 2 of 6, etc.)
- After step 6: CTA card — "Sign up to use this on your own cases"

### Tour 2: RadIQ

**What the user does:**
- Responds to a simulated complaint scenario
- Writes an incident report (contrast extravasation)
- Asks a protocol query (MRI brachial plexus)
- Retrieves an imaging protocol (polytrauma — Camp Bastion)

**Implementation:**
- 4 pre-baked scenario cards with realistic AI responses
- User picks a scenario → types input → sees pre-baked response
- Protocol retrieval pulls from real ImagingProtocol DB (read-only, no cost)
- After completing 2+ scenarios: CTA card

### Tour 3: Vetting

**What the user does:**
- Enters a sample vetting request (pre-filled example available)
- Selects Quick Clean
- Sees AI analysis with iRefer guideline citation and protocol match

**Implementation:**
- 2-3 pre-baked vetting scenarios (appendicitis, CTPA pregnancy, polytrauma)
- User selects one → sees realistic vetting output
- Highlights safety catches (pregnancy warnings, contrast allergy flags)
- CTA after analysis display

### Tour 4: MDT Preparation

**What the user does:**
- Views a pre-loaded case (e.g., breast cancer MDT)
- Clicks "Generate MDT Summary" — sees structured MDT output
- Reviews suggested discussion points, staging summary, management plan
- Sees how imaging findings are cross-referenced with history

**Implementation:**
- Single pre-baked MDT case with realistic AI output
- Show time saved: "This MDT prep took 45 seconds vs 15 minutes manually"
- Highlight smart nuance suggestions (e.g., "Consider MRI for margin assessment")
- CTA: "Prepare your next MDT in under a minute"

---

## Phase 1 — Shared Infrastructure

### Email Gate
- Require email capture before the first tour starts
- "Enter your email to try RadInsights free" — stores in `User` table as pre-registration or separate `TourLead` table
- After email: all 4 tours unlocked for that session (cookie-based)

### Data Capture Strategy (IMPLEMENTED)
- **Tour Capture tool** at `/api/admin/tour-capture` — admin form to record test step data
- During peer review / feature testing, admin captures each step:
  - Tour name (Smart Reporter, RadIQ, etc.)
  - Step number + label (e.g. "A1: Anatomy Search")
  - User input (what was typed/clicked)
  - Response JSON (pasted from browser Network tab)
  - Notes (PASS/FAIL, observations)
  - Screenshot URL (optional)
- Data saved to `tour_capture` DB table, filterable by tour
- Ctrl+Enter shortcut for fast capture during testing sessions
- This captured data becomes the **source material** for pre-baked tour responses

### Pre-baked Response System
- Tour data pulled from `tour_capture` DB table (captured during real testing sessions)
- Responses are real AI outputs from actual test cases — not fabricated
- Frontend renders them with simulated streaming effect (typewriter)
- Zero Anthropic API cost for anonymous visitors
- Clearly labelled as "Interactive Preview" — no deception, but feels live

### Guided Overlay Component
- Reusable JS component: `TourGuide.start({ steps: [...], onComplete: showCTA })`
- Numbered step indicators, highlight target element, next/back navigation
- Progress bar at top
- Skip button always visible (some users hate guided tours)

### CTA Strategy
- After each tour: "Sign up free — 10 Smart Reports + 5 RadIQ queries, no card required"
- Social proof bar: "Join 200+ radiology trainees" (update number dynamically)
- Mid-tour email capture if not already collected
- Return-to-landing button always visible

### SEO Layer
- Each tour section has a static `<section>` with:
  - H2 headline with target keyword (e.g., "AI Radiology Reporting Tool")
  - 2-3 paragraphs of descriptive text (crawlable)
  - Schema.org `SoftwareApplication` + `MedicalWebPage` markup
  - FAQ accordion with 3-4 questions per tour section
- Tour interactions are progressive enhancement on top of the static content

### Mobile Strategy
- AI tours (Smart Reporter, MDT): desktop-only with "Best experienced on desktop" message on mobile, show static screenshots + CTA
- RadIQ & Vetting: simplified mobile layout (single-column, no TinyMCE)
- Non-AI tours: most already work on mobile (calculators, tools, knowledge hub) — just add guided overlay

---

## Phase 1B — Non-AI Tours (Live, Real Data, Zero Cost)

These features are already built, serve real data from the DB, and cost nothing to run. They should ship alongside the AI tours — no reason to defer. Users interact with the real product, not pre-baked data.

### Tour 5: TNM Calculator
- User selects a cancer type (e.g., lung, breast, colorectal)
- Inputs T, N, M values via the real calculator UI
- Sees real-time staging output, prognostic group, and FRCR-relevant notes
- **Live interaction** — uses the existing `/tnm-calculator/{slug}` route
- Guided overlay highlights each input step

### Tour 6: Radiology Tools (Incidental Findings)
- User picks a tool (e.g., pancreatic cyst, adrenal nodule, thyroid nodule)
- Inputs findings via the real interactive form
- Gets structured management recommendation
- **Live interaction** — uses existing `/incidental-findings/{slug}` routes
- Highlight: "These tools follow ACR, Bosniak, and society guidelines"

### Tour 7: Cases
- User browses the case library (real cases, already public)
- Opens one case (e.g., facial nerve schwannoma)
- Navigates image stacks, reads discussion, sees teaching points
- **Live interaction** — uses existing `/case-library/{id}` route
- Highlight: "120+ curated radiology cases with FRCR-level discussion"

### Tour 8: Oncology / TNM Intelligence
- User browses TNM case listing page
- Opens one oncology case (e.g., breast cancer)
- Explores TNM intelligence panel within the case
- **Live interaction** — existing case view with TNM data
- Highlight: "Every oncology case linked to staging, guidelines, and differentials"

### Tour 9: Knowledge Hub
- User browses the knowledge hub
- Explores one Pearl (e.g., thyroid eye disease)
- Opens one Anatomy Snippet (e.g., inner ear anatomy)
- **Live interaction** — existing `/knowledge-hub`, `/radiology-pearls`, `/anatomy-snippets/{slug}` routes
- All content already public and SEO-indexed

### Tour 10: Protocols & Safety
- User browses the protocol library
- Opens a protocol (e.g., biopsy safety checklist, CT polytrauma)
- Views the contrast reaction card
- **Live interaction** — existing `/radiology-protocols/view/{id}` and `/contrast-reaction-card` routes
- Highlight: "130+ imaging protocols from UK NHS trusts and international guidelines"

### Tour 11: Practice (SBA/Viva/Q&A)
- User sees 3 sample Q&A items (pre-loaded, static)
- Tries 1 SBA question and 1 Viva question
- **Pre-baked** for the AI-generated questions, but formatted identically to real output
- Highlight: "Questions generated during real clinical cases — not textbook regurgitation"
- Emphasise dual value: daily work + exam prep

---

## Phase 2 — Optimise Based on Data

Phase 2 is not about adding tours — all tours ship in Phase 1. Phase 2 is about:

| Action | Trigger |
|--------|---------|
| A/B test tour order on landing page | After 500+ visitors |
| Replace pre-baked AI responses with live (rate-limited) for high-converting tours | If conversion > 5% on a tour |
| Add video walkthrough alternative for users who skip guided tours | If skip rate > 40% |
| Personalise tour recommendations based on user's stated role (trainee vs consultant) | After email gate captures role |
| Add "Share this tour" social buttons on highest-converting tours | After identifying top 3 |

---

## Files to Create/Modify

| File | Action | Status |
|------|--------|--------|
| `models.py` — `TourCapture` | DB table for captured test data | DONE |
| `admin_routes.py` — tour-capture endpoints | Save/list/delete/filter captures | DONE |
| `templates/admin_tour_capture.html` | Admin capture form | DONE |
| `templates/landing_tours.html` | New — landing page with tour sections | TODO |
| `static/js/tour-guide.js` | New — reusable guided overlay component | TODO |
| `static/css/tour.css` | New — tour-specific styles | TODO |
| `app.py` or `public_routes.py` | Route for landing page | TODO |
| `models.py` — `TourLead` | Email capture model | TODO |
| `templates/partials/_tour_cta.html` | New — reusable CTA partial | TODO |
| `templates/partials/_schema_medical.html` | Update — add SoftwareApplication schema | TODO |

---

## Metrics to Track

- Email capture rate (visitors → email entered)
- Tour completion rate (started → finished all steps)
- Tour-to-signup rate (completed tour → registered)
- Which tour has highest conversion (informs Phase 2 priority)
- Bounce rate on landing page vs current

---

## Cost & Risk

| Risk | Mitigation |
|------|-----------|
| Bot abuse on email capture | Honeypot field + rate limit by IP |
| Users expect live AI in tours | Label as "Interactive Preview" — set expectation |
| Pre-baked responses feel stale | Use realistic, varied examples; rotate periodically |
| Scope creep — over-polishing before launch | Ship all 11 tours with minimal guided overlay, iterate after data |
| Mobile UX poor for complex AI tours | Desktop-first for SR/MDT; simplified mobile for RadIQ/Vetting; non-AI tours already mobile-friendly |
| Non-AI tours feel less impressive than AI tours | Position them as "tools you'll use every day" — practical value, not flash |
