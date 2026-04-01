# Vetting Tool — Imaging Protocol Workflow

> **Status**: Planned
> **Priority**: High
> **Keyword**: `RADINSIGHTS-VETTING-2026`
> **Created**: April 2026
> **Depends on**: Existing `ClinicalProtocol` model (NOT modified — separate system)

---

## 1. Overview

A structured vetting workflow that mirrors how consultant radiologists actually vet imaging requests. The user pastes a messy clinical referral, and the tool produces **three copy-paste ready outputs** for their hospital vetting system — plus a safety checklist layer.

**This is NOT RadIQ.** RadIQ is Q&A ("ask me anything"). The Vetting Tool is a structured pipeline:
`Clinical referral → Safety checks → Protocol selection → Copy-paste output`

**This is NOT the existing Clinical Guidelines & Safety section.** That contains reference guidelines (contrast safety, emergency pathways, procedures). The Vetting Tool produces actionable imaging protocols with technical scan parameters.

### Goals
- Copy-paste ready output for real hospital vetting systems (CRIS, Sectra, etc.)
- Safety-first: baseline checks + AI-flagged missing info
- Build a reusable imaging protocol library (admin-verified + personal)
- Save tokens: use library protocols when available, AI only when needed
- Train juniors: the safety checklist teaches what to check before approving

### Non-goals
- Not a CRIS replacement — no request rejection/approval workflow
- Not connected to any hospital system — output is text for copy-paste
- Does not replace clinical judgement — user is always the consultant

---

## 2. Workflow

```
┌─────────────────────────────────────────────────────────┐
│  STEP 1: INPUT                                          │
│  User pastes clinical referral text (messy, as received) │
│  + selects modality hint (optional: CT / MRI / US / XR)  │
└───────────────────────┬─────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 2: AI ANALYSIS  (single API call)                 │
│  → Cleans clinical text (formatting only, NO alteration) │
│  → Identifies study type (e.g. CTPA, MRI Brain + Gad)   │
│  → Determines which baseline checks apply                │
│  → Flags study-specific missing info                     │
└───────────────────────┬─────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 3: SAFETY CHECKLIST                               │
│  Tier 1 (baseline): eGFR, Pregnancy, Allergy  [N/A btn] │
│  Tier 2 (AI-flagged): Wells score?, CXR done?  [Skip]   │
│  User enters responses or skips — answers fold into      │
│  clinical details                                        │
└───────────────────────┬─────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 4: PROTOCOL SELECTION                             │
│  Priority: Personal library > Admin library > AI-gen     │
│  If library match found → populate from library          │
│  If no match → AI generates (flagged as AI-generated)    │
│  User can swap protocol from library at any time         │
└───────────────────────┬─────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 5: OUTPUT  (3 sections, each with copy + edit)    │
│                                                          │
│  ┌─ Clinical Details ──────────────────────────────┐    │
│  │ Cleaned history + safety checklist responses     │    │
│  │ [Copy] [Edit]                                    │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  ┌─ Vetting Protocol (shorthand) ──────────────────┐    │
│  │ CT CAP, PV phase. IV contrast.                   │    │
│  │ [Copy] [Edit]                                    │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  ┌─ Detailed Protocol (table) ─────────────────────┐    │
│  │ Phases | Contrast | Rate | Slice | Coverage      │    │
│  │ [Copy] [Edit]                                    │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  ┌─ Special Notes (optional) ──────────────────────┐    │
│  │ User-editable free text for edge cases           │    │
│  │ [Edit]                                           │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  [Save Protocol to My Library]  [Copy All to Clipboard]  │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Data Model

### 3.1 `ImagingProtocol` — Protocol Library

Completely separate from `ClinicalProtocol` (which stores guidelines/safety content). This stores actual scan protocols with technical parameters.

```python
class ImagingProtocol(db.Model):
    """
    Imaging protocol library for the Vetting Tool.
    Stores both admin-verified and user-personal protocols.
    NOT related to ClinicalProtocol (guidelines/safety).
    """
    __tablename__ = 'imaging_protocol'

    id = db.Column(db.Integer, primary_key=True)

    # Identity
    title = db.Column(db.String(300), nullable=False)          # e.g. "CTPA", "MRI Brain with Gadolinium"
    slug = db.Column(db.String(300), nullable=True, index=True) # url-safe, for admin protocols
    modality = db.Column(db.String(50), nullable=False)         # CT, MRI, US, XR, NM, Fluoro, PET-CT
    body_section = db.Column(db.String(100), nullable=True)     # Thorax, Abdomen, etc.
    keywords = db.Column(db.Text, nullable=True)                # comma-separated, for search

    # Protocol content — two tiers
    shorthand_text = db.Column(db.Text, nullable=True)          # consultant vetting-box style
    detailed_protocol_html = db.Column(db.Text, nullable=True)  # rich table/staged format
    special_notes = db.Column(db.Text, nullable=True)           # edge cases, prep instructions

    # Ownership
    origin = db.Column(db.String(20), nullable=False, default='admin')  # admin / personal
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # null for admin
    copied_from_id = db.Column(db.Integer, db.ForeignKey('imaging_protocol.id'), nullable=True)

    # Verification (admin protocols)
    is_published = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    verified_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='imaging_protocols')
    verified_by = db.relationship('User', foreign_keys=[verified_by_user_id])
    copied_from = db.relationship('ImagingProtocol', remote_side=[id])
```

### 3.2 `VettingSession` — User's Vetting History

```python
class VettingSession(db.Model):
    """Records each vetting workflow the user completes."""
    __tablename__ = 'vetting_session'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Input
    raw_clinical_text = db.Column(db.Text, nullable=False)
    modality_hint = db.Column(db.String(50), nullable=True)   # user's optional hint

    # AI analysis output
    cleaned_clinical_text = db.Column(db.Text, nullable=True)
    study_type = db.Column(db.String(200), nullable=True)      # e.g. "CTPA", "MRI Brain + Gad"

    # Safety checklist (JSON)
    # Format: {"egfr": {"value": "72", "skipped": false},
    #          "pregnancy": {"value": "N/A - male", "skipped": false},
    #          "allergy": {"value": "None known", "skipped": false},
    #          "ai_flags": [{"label": "Wells score?", "value": "6", "skipped": false}]}
    safety_checks_json = db.Column(db.Text, nullable=True)

    # Protocol source
    protocol_source = db.Column(db.String(20), nullable=True)  # personal / admin / ai_generated
    protocol_id = db.Column(db.Integer, db.ForeignKey('imaging_protocol.id'), nullable=True)

    # Final output (user may have edited)
    final_clinical_details = db.Column(db.Text, nullable=True)
    final_shorthand = db.Column(db.Text, nullable=True)
    final_detailed_html = db.Column(db.Text, nullable=True)
    final_special_notes = db.Column(db.Text, nullable=True)

    # AI metadata
    ai_model = db.Column(db.String(50), nullable=True)
    ai_tokens_used = db.Column(db.Integer, nullable=True)

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = db.relationship('User', backref=db.backref('vetting_sessions', lazy='dynamic'))
    protocol = db.relationship('ImagingProtocol')
```

---

## 4. AI Prompts

### 4.1 Prompt Architecture

Two API calls per vetting session (not three — keeps cost down):

| Call | Purpose | When | Max tokens |
|------|---------|------|------------|
| **Call 1**: Clinical Analysis | Clean text + identify study + flag missing info | Always | ~800 |
| **Call 2**: Protocol Generation | Generate shorthand + detailed protocol | Only if no library match | ~1500 |

If a library protocol matches → skip Call 2 entirely (zero tokens for protocol).

### 4.2 Call 1: Clinical Analysis Prompt

**System prompt:**

```
You are a consultant radiologist vetting imaging requests in an NHS radiology
department. Your task is to analyse a clinical referral and prepare it for
vetting.

OUTPUT FORMAT: Respond with valid JSON only. No markdown, no explanation.

JSON SCHEMA:
{
  "cleaned_clinical_text": "...",
  "study_type": "...",
  "study_name_full": "...",
  "modality": "CT|MRI|US|XR|NM|Fluoro|PET-CT",
  "baseline_checks": {
    "egfr_needed": true/false,
    "pregnancy_check_needed": true/false,
    "allergy_check_needed": true/false
  },
  "ai_flags": [
    {"label": "...", "reason": "..."}
  ]
}

RULES:
1. CLEANED CLINICAL TEXT: Fix spelling, grammar, and formatting ONLY.
   Do NOT add, remove, or reinterpret ANY clinical information.
   Do NOT expand abbreviations that are standard (SOB, ?PE, Hx, Dx, Ix).
   Do NOT add information that was not in the original text.
   Preserve the clinical meaning EXACTLY.

2. STUDY TYPE: Identify the most appropriate imaging study.
   Use standard names: "CTPA", "CT CAP", "MRI Brain", "US Abdomen", etc.
   If the referral is ambiguous, pick the most likely study and flag it
   in ai_flags with: "Study type inferred — please confirm".

3. BASELINE CHECKS:
   - egfr_needed: true if ANY contrast agent is involved (IV or oral CT,
     gadolinium MRI). false for non-contrast studies.
   - pregnancy_check_needed: true if ionising radiation OR gadolinium.
     false for US, non-contrast MRI.
   - allergy_check_needed: true if ANY contrast agent. false otherwise.

4. AI FLAGS: Flag ONLY genuinely missing information that a consultant
   would ask about before vetting THIS SPECIFIC study. Do NOT flag
   generic things. Be specific and clinically relevant.
   Maximum 4 flags. Common examples by study type:
```

> **DOCTOR INPUT NEEDED HERE**: I need your help to define the study-specific flags table. For each major study type, what are the 2-4 things a consultant actually checks beyond baseline? Draft below — please review and correct:

```
   CTPA: Wells score, CXR result, D-dimer value
   CT CAP (oncology): Primary tumour known?, Previous imaging for comparison?
   CT Abdomen acute: Inflammatory markers (CRP/WCC)?
   MRI Brain: Specific clinical question? (e.g., ?MS, ?tumour, ?pituitary)
   MRI Spine: Level of symptoms? Red flags (cauda equina)?
   US Abdomen: Relevant blood tests (LFTs, amylase)?
   CT Renal colic: Urine dip result?
```

```
   Do NOT flag information already present in the referral text.
   Do NOT flag things that don't change the protocol or vetting decision.
```

### 4.3 Call 2: Protocol Generation Prompt

**Only called when no library protocol matches the study type.**

**System prompt:**

```
You are a consultant radiologist writing an imaging protocol for a vetting
system. You write TWO versions:

1. SHORTHAND: What you would type in the vetting box for radiographers.
   This is terse, informed-audience shorthand. Examples:
   - "CT CAP, PV phase. IV contrast."
   - "CTPA. Standard. No delayed."
   - "MRI brain + Gad. Standard sequences + DWI."
   - "CT head non-con."
   - "MRI liver with Primovist. Arterial, PV, 20min HBP."
   Only mention coverage/phases/sequences when NON-STANDARD.
   Radiographers know standard protocols — don't state the obvious.

2. DETAILED PROTOCOL: A structured HTML table with full technical parameters
   that a radiographer can reference if needed.

OUTPUT FORMAT: Respond with valid JSON only.

JSON SCHEMA:
{
  "shorthand": "...",
  "detailed_protocol_html": "...",
  "special_notes": "..." or null
}

SHORTHAND RULES:
- Write exactly as a consultant would type in a CRIS/Sectra vetting box
- Assume an informed radiographer audience
- Include: study name, contrast (if applicable), phases (names only,
  not timing — unless unusual timing e.g. "20min hepatobiliary phase")
- Include coverage ONLY if non-standard (e.g. "vertex to symphysis"
  instead of normal CAP coverage)
- Do NOT include technical parameters (kVp, mAs, slice thickness) —
  that's for the detailed table
- Maximum 2-3 lines

DETAILED PROTOCOL RULES:
- Output valid HTML using <table> with proper <thead> and <tbody>
- Use CSS class "vetting-protocol-table" on the <table> element
- For SIMPLE protocols (single-phase CT, standard MRI), use a single table:
  Columns: Parameter | Value
  Rows: Coverage, kVp, mAs/ref, Slice thickness, Recon kernel,
        Contrast agent, Volume, Rate, Delay, Phases, Reformats

- For COMPLEX protocols (multi-phase CT, multi-sequence MRI, MR Enterography),
  use a STAGED format:
```

> **DOCTOR INPUT NEEDED HERE**: I need your guidance on the staged format for complex protocols. My proposed format below — please validate the clinical ordering and completeness:

```
  <h6 class="vetting-stage-heading">Stage 1: Patient Preparation</h6>
  <table class="vetting-protocol-table">...</table>

  <h6 class="vetting-stage-heading">Stage 2: Pre-contrast Sequences</h6>
  <table class="vetting-protocol-table">
    Columns: Sequence | Plane | Coverage | Slice | Notes
  </table>

  <h6 class="vetting-stage-heading">Stage 3: Contrast Administration</h6>
  <table class="vetting-protocol-table">
    Columns: Parameter | Value
    (Agent, Volume, Rate, Timing)
  </table>

  <h6 class="vetting-stage-heading">Stage 4: Post-contrast Sequences</h6>
  <table class="vetting-protocol-table">
    Columns: Sequence | Timing | Plane | Coverage | Notes
  </table>

- For CT multi-phase:
  Columns: Phase | Delay (s) | Coverage | Slice (mm) | Recon | Notes

- SPECIAL NOTES: Include ONLY when clinically relevant:
  patient prep (fasting, oral contrast, Buscopan), contraindications,
  weight-based dosing notes, scanner-specific caveats.
  If nothing special → return null.

- Use <mark class="vetting-highlight"> for critical safety points
  (e.g. max contrast dose, mandatory prep steps). Maximum 2 highlights.
```

### 4.4 Shorthand Extraction Prompt (for batch generation)

Used when admin creates detailed protocols from PDF and needs shorthand auto-extracted:

```
You are a consultant radiologist. Given a detailed imaging protocol below,
write the shorthand version — what you would type in a CRIS vetting box.

Rules:
- Terse, informed-audience shorthand (radiographers know standard protocols)
- Study name + contrast + phases (names only, not timing unless unusual)
- Coverage only if non-standard
- Maximum 2-3 lines
- Do NOT include technical parameters

DETAILED PROTOCOL:
{detailed_protocol_text}

Respond with the shorthand text only. No JSON, no explanation.
```

### 4.5 Prompt Quality Flags

Areas where AI output must be validated — **never trust blindly**:

| Risk | Mitigation |
|------|------------|
| AI invents contrast doses | Detailed protocol flagged as "AI-generated — verify doses for your department" when not from library |
| AI misidentifies study type | User can override study type before protocol generation |
| AI cleans clinical text too aggressively | Prompt strictly says formatting-only; UI shows original alongside cleaned version for comparison |
| AI flags irrelevant checks | Maximum 4 flags; user can skip any |
| AI halluccinates protocol parameters | Library protocols preferred over AI-generated; admin protocols are verified |

---

## 5. Safety Checklist Design

### 5.1 Tier 1: Baseline Checks (hardcoded, not AI-generated)

These are determined by the AI's `baseline_checks` output (which fields apply), but the items themselves are from a fixed list. No token cost for the checklist itself.

```
┌──────────────────────────────────────────────────────────────┐
│  ⚕ Pre-vetting Safety Checks                                │
│                                                              │
│  eGFR / Renal function   [____________] [N/A]                │
│  Pregnancy status         [____________] [N/A]                │
│  Contrast allergy history [____________] [N/A]                │
│                                                              │
│  ⚠ AI suggests checking:                                     │
│  Wells score?             [____________] [Skip]               │
│  CXR result?              [____________] [Skip]               │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 How responses fold into output

When the user enters a value (e.g., eGFR: "72"), it gets appended to the cleaned clinical details:

```
Clinical Details:
65-year-old female presenting with acute onset shortness of breath and
pleuritic chest pain. D-dimer elevated at 1.2 mg/L. On warfarin for AF.
History of DVT 2019.

Pre-vetting checks:
- eGFR: 72 (adequate for IV contrast)
- Pregnancy: Post-menopausal
- Allergy: No known contrast allergy
- Wells score: 6 (PE likely)
- CXR: Reported as normal
```

This makes the final clinical details output **complete** — ready to paste into a vetting system with full documentation.

### 5.3 When baseline checks are hidden

| Modality/Study | eGFR | Pregnancy | Allergy |
|----------------|------|-----------|---------|
| CT with contrast | Show | Show | Show |
| CT non-contrast | Hide | Show | Hide |
| MRI with gadolinium | Show | Show | Show |
| MRI non-contrast | Hide | Show (relative) | Hide |
| Ultrasound | Hide | Hide | Hide |
| X-ray | Hide | Show | Hide |
| Fluoroscopy with contrast | Show | Show | Show |
| Nuclear medicine | Hide | Show | Hide |

---

## 6. Protocol Library

### 6.1 Access Points

**Primary** — from the Vetting Tool page itself:

```
/vetting                   → Vetting workflow (main page)
/vetting/protocols         → Protocol library (browse + manage)
```

The library page has two views:

| Tab | Shows | Actions |
|-----|-------|---------|
| **All Protocols** | Admin (verified, published) + user's personal, admin first | Search, filter by modality/body section |
| **My Protocols** | User's personal only | Edit (TinyMCE inline), delete |

**Admin protocols** show a "Copy to My Library" button. This creates a personal copy the user can customise. The admin original stays untouched.

**During vetting workflow** — a protocol picker dropdown/search appears at Step 4:
- Searches by study name, modality, keywords
- Shows source badge: `[Admin ✓]` or `[Personal]` or `[AI Generated ⚠]`
- Personal matches shown first (user has customised for their department)

### 6.2 Personal Protocol Saving

When user clicks "Save Protocol to My Library" from a vetting session:
- Saves: title (study type), shorthand, detailed HTML, special notes, modality, body_section
- `origin = 'personal'`, `user_id = current_user.id`
- If saved from an admin protocol: `copied_from_id` set for traceability
- User can edit shorthand and detailed protocol independently via TinyMCE inline

### 6.3 Admin Protocol Library

**Route**: `/vetting/admin/protocols` (admin-only)

**Admin creates protocols via**:
1. **Manual entry** — TinyMCE rich editor for detailed protocol, text field for shorthand
2. **AI batch generation** — upload PDF protocol manual, script extracts and structures
3. **AI single generation** — enter study name, AI generates detailed + shorthand as draft

All admin protocols start as **draft** (`is_published=False`). Admin must verify and publish.

Verification sets: `is_verified=True`, `verified_by_user_id`, `verified_at`, `is_published=True`.

---

## 7. Admin Batch Generation from PDF

### 7.1 Script: `scripts/generate_imaging_protocols.py`

Similar pattern to existing `scripts/generate_tnm_calculator.py`:

1. Parse PDF protocol manual (user provides)
2. For each protocol found:
   - Extract study name, modality, body section
   - Extract or AI-generate detailed protocol HTML (staged format for complex, single table for simple)
   - AI-generate shorthand from detailed protocol (Call: shorthand extraction prompt)
   - Create `ImagingProtocol` record with `origin='admin'`, `is_published=False`
3. Admin reviews in `/vetting/admin/protocols`, edits, verifies, publishes

### 7.2 PDF parsing approach

> **DOCTOR INPUT NEEDED**: Please provide the PDF protocol manual when ready. The parsing strategy depends on the PDF format:
> - If well-structured (consistent headings, tables): regex/tabula extraction + AI cleanup
> - If loosely structured (running text): AI does full extraction and structuring
> - Either way: every protocol starts as DRAFT for manual review

---

## 8. UI Design

### 8.1 Page: `/vetting` — Main Vetting Workflow

**Design philosophy**: Clinical workflow, not a form. Progressive disclosure — sections appear as the workflow advances. Follows app brand style (teal/orange, `.card-brand`, no generic Bootstrap).

```
┌─────────────────────────────────────────────────────────────┐
│  🏥 Vetting Tool                              [My Protocols] │
│  ─────────────────────────────────────────────────────────── │
│                                                              │
│  ┌─ card-brand ────────────────────────────────────────────┐ │
│  │ card-brand-header: Paste Clinical Referral              │ │
│  │                                                         │ │
│  │  [textarea — clinical referral text]                    │ │
│  │                                                         │ │
│  │  Modality hint (optional): [CT] [MRI] [US] [XR] [Other]│ │
│  │                                                         │ │
│  │  [btn-brand-primary: Analyse & Vet]                     │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ── appears after AI analysis ──────────────────────────────│
│                                                              │
│  ┌─ Safety Checks card (teal accent) ─────────────────────┐ │
│  │  Tier 1: eGFR [___] [N/A]  Pregnancy [___] [N/A]  ... │ │
│  │  Tier 2: ⚠ Wells score? [___] [Skip]                   │ │
│  │                                                         │ │
│  │  [btn-brand-neutral: Continue with Protocol]            │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ── appears after safety checks ────────────────────────────│
│                                                              │
│  ┌─ Protocol Source banner ────────────────────────────────┐ │
│  │  ✓ Matched: "CTPA" from Admin Library                   │ │
│  │  [Change Protocol ▾] — dropdown/search to swap          │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─ Output Section 1: Clinical Details ───────────────────┐ │
│  │  [Copy 📋] [Edit ✏️]                                    │ │
│  │  Cleaned clinical history + safety check responses      │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─ Output Section 2: Vetting Protocol (shorthand) ───────┐ │
│  │  [Copy 📋] [Edit ✏️]                                    │ │
│  │  CT CAP, PV phase. IV contrast.                         │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─ Output Section 3: Detailed Protocol ──────────────────┐ │
│  │  [Copy 📋] [Edit ✏️]                                    │ │
│  │  [Rich HTML table / staged format]                      │ │
│  │  Source: Admin Library ✓  |  AI Generated ⚠ Verify      │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─ Output Section 4: Special Notes (optional) ───────────┐ │
│  │  [Edit ✏️]                                               │ │
│  │  User-editable free text                                │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  [btn-brand-primary: Copy All to Clipboard]                  │
│  [btn-brand-neutral: Save Protocol to My Library]            │
│  [btn-outline: New Vetting]                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 TinyMCE Inline Editing

Each output section has an "Edit" button. On click:
- Section becomes editable via TinyMCE inline (same pattern as existing template editing)
- "Save" and "Cancel" buttons appear
- For detailed protocol: TinyMCE with table plugin enabled (edit cells, add/remove rows)
- Edits are local to the session — only persisted when user clicks "Save Protocol to My Library"

### 8.3 Copy to Clipboard

Each section has its own copy button (copies that section only).
"Copy All" copies all three sections concatenated with clear dividers:

```
--- CLINICAL DETAILS ---
[cleaned text + safety checks]

--- PROTOCOL ---
[shorthand]

--- DETAILED PROTOCOL ---
[table as plain text / formatted]

--- NOTES ---
[special notes if any]
```

**Implementation note**: For the detailed table, copy as plain-text formatted table (not HTML). Use a `tableToText()` utility that converts `<table>` to aligned plain text.

### 8.4 Protocol Source Badge

Visual indicator on the protocol output:

| Source | Badge | Colour |
|--------|-------|--------|
| Admin library (verified) | `✓ Admin Protocol` | Green (--brand-success) |
| Personal library | `Personal Protocol` | Teal (--brand-neutral) |
| AI-generated | `⚠ AI Generated — Verify parameters` | Orange (--brand-primary) |

### 8.5 CSS Classes (new)

Follow existing `.card-brand` pattern. No inline colours.

```css
/* Vetting tool cards */
.vetting-input-card { }          /* extends .card-brand */
.vetting-safety-card { }         /* teal left-border accent */
.vetting-output-section { }      /* output card with copy/edit buttons */
.vetting-output-header { }       /* section header with action buttons */

/* Protocol tables */
.vetting-protocol-table { }      /* styled <table> for detailed protocol */
.vetting-protocol-table th { }   /* header cells */
.vetting-protocol-table td { }   /* data cells */
.vetting-stage-heading { }       /* h6 for complex protocol stages */
.vetting-highlight { }           /* <mark> for critical safety points */

/* Safety checklist */
.vetting-safety-row { }          /* each check item row */
.vetting-safety-input { }        /* text input for check response */
.vetting-safety-skip { }         /* N/A / Skip button */
.vetting-safety-tier2 { }        /* AI-flagged items (visually distinct) */

/* Protocol source badges */
.vetting-source-admin { }        /* green */
.vetting-source-personal { }     /* teal */
.vetting-source-ai { }           /* orange with warning icon */

/* Library */
.vetting-protocol-card { }       /* protocol card in library browse */
```

---

## 9. API Endpoints

### 9.1 Vetting Workflow

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| POST | `/api/vetting/analyse` | Call 1: Clinical analysis + flags | `@login_required` |
| POST | `/api/vetting/generate-protocol` | Call 2: Protocol generation (if no library match) | `@login_required` |
| POST | `/api/vetting/save-session` | Save completed vetting session | `@login_required` |

### 9.2 Protocol Library (User)

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| GET | `/api/vetting/protocols` | List user's personal + admin published protocols | `@login_required` |
| GET | `/api/vetting/protocols/search?q=` | Search protocols by name/keyword/modality | `@login_required` |
| POST | `/api/vetting/protocols` | Save protocol to personal library | `@login_required` |
| PUT | `/api/vetting/protocols/<id>` | Update personal protocol | `@login_required` |
| DELETE | `/api/vetting/protocols/<id>` | Delete personal protocol | `@login_required` |
| POST | `/api/vetting/protocols/<id>/copy` | Copy admin protocol to personal library | `@login_required` |

### 9.3 Admin Protocol Management

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| GET | `/vetting/admin/protocols` | Admin protocol management page | `@require_admin` |
| POST | `/api/vetting/admin/protocols` | Create admin protocol | `@require_admin` |
| PUT | `/api/vetting/admin/protocols/<id>` | Update admin protocol | `@require_admin` |
| POST | `/api/vetting/admin/protocols/<id>/verify` | Verify & publish | `@require_admin` |
| DELETE | `/api/vetting/admin/protocols/<id>` | Delete admin protocol | `@require_admin` |
| POST | `/api/vetting/admin/generate` | AI-generate single protocol (draft) | `@require_admin` |
| POST | `/api/vetting/admin/batch-generate` | Batch generate from input | `@require_admin` |

---

## 10. Navigation & Routing

### 10.1 Routes

| Route | Template | Purpose |
|-------|----------|---------|
| `/vetting` | `templates/vetting.html` | Main vetting workflow page |
| `/vetting/protocols` | `templates/vetting_protocols.html` | User protocol library |
| `/vetting/admin/protocols` | `templates/vetting_admin.html` | Admin protocol management |

### 10.2 Nav Placement

**Desktop**: Add to Resources dropdown (after Clinical Guidelines & Safety):
```html
<li><a href="/vetting"><i class="fas fa-check-double me-2" style="color: #5E899E;"></i>Vetting Tool</a></li>
```

**Mobile**: Add to Resources collapse section (same position).

**Admin sidebar**: Add "Imaging Protocols" link to admin panel (alongside existing admin pages).

### 10.3 Existing Pages — DO NOT MODIFY

These existing systems are completely separate and must NOT be touched:

| System | Model | Route prefix | Purpose |
|--------|-------|-------------|---------|
| Clinical Guidelines & Safety | `ClinicalProtocol` | `/radiology-protocols` | Safety guidelines, not scan protocols |
| Smart Reporter | various | `/smart-reporter` | Report generation, separate workflow |
| RadIQ | `RadIQQuery` | `/radiq` | Q&A, not structured vetting |
| Reporting Algorithms | `ReportingAlgorithm` | `/reporting-algorithms` | Decision trees |
| Radiology Templates | `RadiologyTemplate` | `/reporting-templates` | PACS report templates |

---

## 11. Files to Create

| File | Purpose |
|------|---------|
| `vetting_routes.py` | Blueprint for all vetting routes + API endpoints |
| `ai_vetting.py` | AI prompts + generation functions (analyse, protocol gen, shorthand extraction) |
| `templates/vetting.html` | Main vetting workflow page |
| `templates/vetting_protocols.html` | User protocol library |
| `templates/vetting_admin.html` | Admin protocol management |
| `scripts/generate_imaging_protocols.py` | Batch generation script |

## 12. Files to Modify

| File | Change |
|------|--------|
| `models.py` | Add `ImagingProtocol` + `VettingSession` models |
| `app.py` | Register vetting blueprint, add migration block |
| `templates/base.html` | Add "Vetting Tool" to Resources dropdown (desktop + mobile) |
| `templates/pricing.html` | Add vetting tool to feature lists (if applicable to tier) |
| `static/css/` or inline | Add `.vetting-*` CSS classes |

---

## 13. Implementation Phases

### Phase 1: Core Vetting Workflow
- Models: `ImagingProtocol`, `VettingSession`
- AI: Clinical analysis prompt (Call 1) + Protocol generation prompt (Call 2)
- UI: Input → Safety checks → Output (3 sections) → Copy
- TinyMCE inline editing on output sections
- No library yet — all protocols AI-generated

### Phase 2: Protocol Library
- Admin protocol creation (manual + AI single-generate)
- User personal library (save from sessions)
- Protocol matching during vetting (personal > admin > AI)
- "Copy to My Library" for admin protocols
- Library browse/search page

### Phase 3: Admin Batch Generation
- PDF parsing script
- Shorthand extraction prompt
- Bulk import → draft → verify → publish workflow

### Phase 4: Polish & Integration
- Vetting session history (user can review past vettings)
- Protocol usage analytics (which protocols most used)
- Sitemap + SEO (if vetting becomes public preview)
- Landing/pricing page updates

---

## 14. Cost Estimate

### Token cost per vetting session

| Scenario | Call 1 | Call 2 | Total |
|----------|--------|--------|-------|
| Library match exists | ~800 tokens | 0 (skipped) | ~800 tokens |
| No library match (AI generates) | ~800 tokens | ~1500 tokens | ~2300 tokens |

At Sonnet pricing (~$3/$15 per 1M input/output tokens):
- With library: ~$0.005 per vetting
- Without library: ~$0.015 per vetting

### Development effort

| Phase | Estimate |
|-------|----------|
| Phase 1: Core workflow | Medium-High (new blueprint, 2 prompts, full UI) |
| Phase 2: Library | Medium (CRUD, search, TinyMCE, library matching) |
| Phase 3: Batch generation | Medium (PDF parsing, script, admin UI) |
| Phase 4: Polish | Low-Medium |

---

## 15. Guardrails

1. **AI-generated protocols are always flagged** — orange badge, "Verify parameters for your department". Library protocols show green/teal badge.
2. **Clinical text is NEVER altered in meaning** — only formatting. Original text preserved in `raw_clinical_text` for audit.
3. **Safety checklist cannot be skipped entirely** — the checklist is always shown. Individual items can be skipped, but the section is always visible.
4. **Protocol parameters are institution-specific** — detailed protocols should include a note: "Parameters shown are general guidance. Verify against your department's local protocols."
5. **No PII in AI calls** — the PII guard (`pii_guard.py`) middleware applies to vetting API endpoints too.
6. **Personal protocols are private** — never visible to other users. Admin protocols are shared.
7. **Rate limiting** — same tier-based limits as RadIQ (free: X/month, premium: Y/month).

---

## 16. Open Questions for Doctor Review

These are areas where clinical expertise is needed before implementation:

### Q1: Study-specific AI flags
The draft flags in Section 4.2 need clinical validation. For each major study type:
- What 2-4 things does a consultant actually check beyond eGFR/pregnancy/allergy?
- Are there any study types where eGFR/pregnancy/allergy are NOT the right baseline?

### Q2: Complex protocol staging
The staged format (Section 4.3) for protocols like MR Enterography:
- Is the Stage 1→2→3→4 ordering correct for all complex protocols?
- Are there protocols that need a different stage structure?
- What other complex protocols should we plan for? (e.g., cardiac MRI, CT coronary angiogram, dynamic pituitary MRI)

### Q3: Shorthand conventions
The shorthand style in the prompt (Section 4.3):
- Do the example shorthands match how you'd actually write them?
- Are there common abbreviations I'm missing or getting wrong?
- Is "PV phase" vs "portal venous" vs "PVP" — which do consultants actually write?

### Q4: Detailed protocol parameters
For AI-generated protocols (no library match):
- Should the AI attempt to give specific numbers (kVp, mAs, slice thickness)?
- Or should these always be placeholders like "[per local protocol]"?
- Argument for numbers: gives trainees a reference. Argument against: varies by scanner.

### Q5: PDF protocol manual format
- When you provide the PDF, what format is it in? (tables, running text, diagrams?)
- Is it one department's protocols or a published reference?
- This determines the batch parsing approach.

---

## 17. Relationship to Other Systems

```
┌──────────────────────────────────────────────────────┐
│                    RadInsights App                     │
│                                                       │
│  Smart Reporter ──── Report writing workflow           │
│       │                                               │
│       │ (no direct link)                              │
│       │                                               │
│  RadIQ ────────── Q&A clinical advisory               │
│       │               │                               │
│       │               │ (radiographer query            │
│       │               │  may overlap — that's OK,      │
│       │               │  RadIQ = quick Q&A,            │
│       │               │  Vetting = structured output)  │
│       │               │                               │
│  Vetting Tool ─── Structured vetting workflow         │
│       │               │                               │
│       │         ImagingProtocol library                │
│       │         (admin + personal)                     │
│       │                                               │
│  Clinical Guidelines ── Safety reference (read-only)  │
│  (ClinicalProtocol)     Not scan protocols            │
│                                                       │
└──────────────────────────────────────────────────────┘
```

The Vetting Tool is a standalone workflow. It does not share session state with Smart Reporter or RadIQ. A user might use RadIQ to ask "What's the Fleischner criteria?" and separately use the Vetting Tool to vet a CT chest request — these are independent actions.
