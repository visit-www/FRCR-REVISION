# Clinical Tools Architecture

Backend and frontend flow documentation for the three AI-powered clinical tools:
**On-Call Helper**, **Algorithm Finder**, and **Incidental Findings Helper**.

---

## Table of Contents

1. [Overview](#overview)
2. [Database Models](#database-models)
3. [Feature 1: On-Call Helper](#feature-1-on-call-helper)
4. [Feature 2: Algorithm Finder](#feature-2-algorithm-finder)
5. [Feature 3: Incidental Findings Helper](#feature-3-incidental-findings-helper)
6. [TNM Calculator Generation Script](#tnm-calculator-generation-script)
7. [Cross-Cutting Concerns](#cross-cutting-concerns)
8. [File Reference](#file-reference)
9. [API Endpoint Reference](#api-endpoint-reference)

---

## Overview

### Architecture Pattern

All three features follow the same hybrid pattern already used by the TNM staging browser:

```
Authoritative data lives in the database (curated by admins)
        ↓
User searches via pg_trgm fuzzy matching
        ↓
Matched data injected as context into Claude API call (where AI is needed)
        ↓
Claude FORMATS the data — it does NOT SOURCE it
        ↓
Response displayed with mandatory source citation + disclaimer
        ↓
Every interaction logged for audit trail
```

### Blueprints Registered in `app.py`

| Blueprint | Variable | URL Prefix | File |
|-----------|----------|------------|------|
| On-Call Helper | `oncall_bp` | `/on-call-helper` | `oncall_routes.py` |
| Algorithm Finder / Reporting | `reporting_bp` | (none — root level) | `reporting_routes.py` |
| Incidental Findings | `if_bp` | `/incidental-findings` | `incidental_findings/routes.py` |

All three are imported and registered in `app.py`:

```python
from oncall_routes import oncall_bp
from reporting_routes import reporting_bp
from incidental_findings import if_bp

app.register_blueprint(oncall_bp)
app.register_blueprint(reporting_bp)
app.register_blueprint(if_bp)
```

---

## Database Models

All models are defined in `models.py`. Migration SQL is in `migrations/add_clinical_tools_tables.sql`.

### ClinicalProtocol

Stores curated clinical protocols for the On-Call Helper knowledge base.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | SERIAL PK | |
| `category` | VARCHAR(50) | CONTRAST, SCORING, STAGING, CRITERIA, EMERGENCY, ANATOMY, DOSE, SAFETY |
| `title` | VARCHAR(300) | Protocol title (pg_trgm indexed) |
| `keywords` | TEXT | Search keywords (pg_trgm indexed) |
| `content_structured` | TEXT (JSON) | Structured data (grades, criteria, values) |
| `content_html` | TEXT | Rich formatted reference content |
| `source_citation` | VARCHAR(500) | e.g. "AAST 2018 Revised Organ Injury Scale" |
| `guideline_version` | VARCHAR(100) | e.g. "2018 Revision" |
| `source_url` | VARCHAR(1000) | Link to original guideline |
| `is_published` | BOOLEAN | Only published protocols appear in search |
| `verified_by_user_id` | FK → user | Admin who verified the protocol |
| `verified_at` | TIMESTAMP | When it was verified |
| `created_by_user_id` | FK → user | Admin who created it |

### OnCallQueryLog

Audit trail for every On-Call Helper query (medicolegal requirement).

| Column | Type | Purpose |
|--------|------|---------|
| `id` | SERIAL PK | |
| `user_id` | FK → user | Who queried |
| `query_text` | TEXT | The clinical question |
| `matched_protocol_ids` | TEXT (JSON) | Which protocols were matched |
| `ai_response_text` | TEXT | The full AI-formatted response |
| `model_used` | VARCHAR(100) | e.g. "claude-sonnet-4-20250514" |
| `token_count` | INTEGER | Tokens used |
| `response_source` | VARCHAR(50) | "protocol" or "no_match" |

### ReportingTemplate

Admin-curated non-oncologic reporting decision trees (trauma, grading, emergency).

| Column | Type | Purpose |
|--------|------|---------|
| `id` | SERIAL PK | |
| `slug` | VARCHAR(200) UNIQUE | URL slug |
| `title` | VARCHAR(300) | Template title (pg_trgm indexed) |
| `category` | VARCHAR(100) | trauma, grading, emergency, scoring |
| `body_section` | VARCHAR(100) | e.g. "Abdomen" |
| `keywords` | TEXT | Search keywords (pg_trgm indexed) |
| `template_html` | TEXT | Self-contained interactive HTML |
| `algorithm_html` | TEXT | Extracted algorithm summary |
| `source_citation` | VARCHAR(500) | Guideline source |
| `is_available` | BOOLEAN | Whether visible to users |
| `generation_model` | VARCHAR(100) | Which Claude model generated it |

### IncidentalFindingCalculator

Interactive calculators for incidental finding management guidelines.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | SERIAL PK | |
| `slug` | VARCHAR(200) UNIQUE | URL slug |
| `finding_name` | VARCHAR(300) | e.g. "Pulmonary Nodule" (pg_trgm indexed) |
| `category` | VARCHAR(100) | e.g. "pulmonary", "renal", "adrenal" |
| `keywords` | TEXT | Search keywords (pg_trgm indexed) |
| `calculator_html` | TEXT | Self-contained interactive HTML |
| `algorithm_html` | TEXT | Extracted algorithm summary |
| `guideline_source` | VARCHAR(300) | e.g. "Fleischner Society 2017" |
| `guideline_version` | VARCHAR(100) | |
| `is_available` | BOOLEAN | Whether visible to users |
| `verified_by_user_id` | FK → user | Admin who verified against guideline |

---

## Feature 1: On-Call Helper

### Purpose

A curated clinical protocol knowledge base where Claude **formats** but does **not source** answers. Every response traces back to an admin-verified protocol.

### Backend Flow

**Files:** `ai_oncall_helper.py`, `oncall_routes.py`

#### Search/Autocomplete Flow

```
GET /on-call-helper/api/search?q=renal+trauma
        ↓
search_protocols_autocomplete(query_text, limit=8)
        ↓
SQL: SELECT id, title, category, keywords
     FROM clinical_protocol
     WHERE is_published = TRUE
       AND (similarity(keywords, :query) > 0.15
            OR similarity(title, :query) > 0.15
            OR title ILIKE :like_query)
     ORDER BY GREATEST(similarity(keywords, :query), similarity(title, :query)) DESC
        ↓
Returns: [{id, title, category, keywords, similarity}]
```

#### Query Submission Flow

```
POST /on-call-helper/api/query
Body: {"query": "What is the AAST renal trauma grading?"}
        ↓
ai_oncall_helper.generate_oncall_response(query_text, user_id)
        ↓
Step 1: search_protocols(query_text, limit=5)
   - pg_trgm search against ClinicalProtocol table
   - Falls back to ILIKE if pg_trgm fails (SQLite dev)
        ↓
Step 2: If NO matching protocols found:
   → Return: "No verified protocol found for this query"
   → Log to OnCallQueryLog with response_source='no_match'
   → DOES NOT generate from Claude training data
        ↓
Step 3: If protocols found:
   → _build_protocol_context(protocols)
   → Builds delimited text blocks from each protocol's content
        ↓
Step 4: Call Claude API
   URL: https://api.anthropic.com/v1/messages
   Model: claude-sonnet-4-20250514 (configurable via CLAUDE_MODEL env var)
   Temperature: 0.2 (low — consistent answers)
   Max tokens: 4000
   System prompt: SYSTEM_PROMPT + protocol context blocks
   User message: The clinical query
        ↓
Step 5: Parse JSON response
   Expected fields: answer_html, summary, citations[], confidence, flags[]
   Fallback: regex extraction if JSON parse fails
        ↓
Step 6: Log to OnCallQueryLog
   - user_id, query_text, matched_protocol_ids, ai_response_text
   - model_used, token_count, response_source='protocol'
        ↓
Step 7: Return response to frontend
```

#### Admin Protocol Management

```
GET  /on-call-helper/admin/protocols         → Admin list page
GET  /on-call-helper/admin/protocols/api      → List all protocols (JSON)
POST /on-call-helper/admin/protocols/api      → Create protocol
GET  /on-call-helper/admin/protocols/api/:id  → Get single protocol
PUT  /on-call-helper/admin/protocols/api/:id  → Update protocol
DELETE /on-call-helper/admin/protocols/api/:id → Delete protocol
POST /on-call-helper/admin/protocols/api/:id/verify    → Verify & publish
POST /on-call-helper/admin/protocols/api/:id/unpublish → Unpublish
```

All admin routes require `@require_admin` decorator.

### Frontend Flow

**Template:** `templates/oncall_helper.html`

```
User lands on /on-call-helper
        ↓
Clinical disclaimer banner displayed at top (always visible)
        ↓
User types in search bar
        ↓
Debounced (300ms) autocomplete → GET /on-call-helper/api/search?q=...
        ↓
Dropdown shows matching protocol titles
        ↓
User submits query (Enter or click Submit)
        ↓
POST /on-call-helper/api/query → Loading spinner shown
        ↓
Response displayed in card:
  - answer_html (the formatted clinical answer)
  - Confidence badge (high/medium/low with color)
  - Citations list with guideline names and versions
  - Matched protocols listed
  - Any flags (e.g. "AI-supplemented — verify independently")
        ↓
History sidebar loads from GET /on-call-helper/api/history
  - Shows recent queries with timestamps
  - Click to reload a previous answer
```

### Medicolegal Safeguards

1. Every response includes source citation, guideline version, verification date
2. Persistent disclaimer banner on every page
3. Full audit log (OnCallQueryLog) — every query and response stored
4. Admin-only content curation with verify gate
5. If no matching protocol: refuses to generate from Claude training data
6. If Claude supplements beyond context: response flagged

---

## Feature 2: Algorithm Finder

### Purpose

Unified search across **all** algorithmic content in the platform:
- Published cases with discussion (PRIMARY source)
- TNM calculators (oncologic algorithms)
- Incidental findings calculators
- Admin-curated reporting templates

If no match exists, the radiologist can generate a new algorithmic approach which simultaneously creates a DRAFT case that enriches the case library.

### Backend Flow

**Files:** `reporting_routes.py`, `reporting_template_generator.py`

#### Unified Search Flow

```
GET /api/algorithms/search?q=splenic+injury&type=
        ↓
Searches 4 tables in parallel using pg_trgm:
        ↓
1. Cases (PRIMARY):
   SELECT c.id, c.diagnosis, similarity(...)
   FROM "case" c
   WHERE c.status = 'published'
     AND c.discussion IS NOT NULL
     AND (similarity(...) > 0.1 OR c.diagnosis ILIKE ...)

2. TNM Calculators:
   SELECT tc.id, tc.slug, tc.cancer_name, similarity(...)
   FROM tnm_calculator_content tc
   WHERE tc.is_available = TRUE AND (similarity(...) > 0.1 OR ...)

3. Incidental Findings:
   SELECT ifc.id, ifc.slug, ifc.finding_name, similarity(...)
   FROM incidental_finding_calculator ifc
   WHERE ifc.is_available = TRUE AND (similarity(...) > 0.1 OR ...)

4. Reporting Templates:
   SELECT rt.id, rt.slug, rt.title, similarity(...)
   FROM reporting_template rt
   WHERE rt.is_available = TRUE AND (similarity(...) > 0.1 OR ...)
        ↓
All results merged, sorted by similarity DESC
        ↓
Each result includes: type, id, title, body_section, description, url, similarity
```

The `type` query parameter can filter to a single source: `case`, `oncologic`, `incidental`, or `reporting`.

#### Case-Based Generation Flow (The Key Feature)

This is the flow when a radiologist searches for something that has no existing match.

```
POST /api/algorithms/generate
Body: {
  "diagnosis": "AAST Grade III Splenic Injury",
  "body_section": "Abdomen",
  "notes": "Post-trauma CT findings"
}
        ↓
Step 1: Rate limit check
   - Max 10 DRAFT cases per user
   - Returns 429 if exceeded
        ↓
Step 2: Map body_section → BodyPart enum + FRCRModule enum
   - _map_body_section_to_enum("Abdomen") → BodyPart.GASTROINTESTINAL
   - _map_body_section_to_module("Abdomen") → FRCRModule.GASTROINTESTINAL
        ↓
Step 3: Auto-generate case_number
   - _generate_case_number(BodyPart.GASTROINTESTINAL)
   - Format: "GASTRO-001", "GASTRO-002", etc.
   - Finds max existing number with that prefix
        ↓
Step 4: Create Case in DRAFT status
   - case_number, diagnosis, module, body_part
   - status = CaseStatus.DRAFT
   - created_by_user_id = current_user.id
   - contributor_name = current_user.full_name
   - contributor_notes = "Auto-generated via Algorithm Finder..."
   - db.session.flush() to get case.id
        ↓
Step 5: Call generate_prelim_case_data() from ai_prelim.py
   - Same pipeline used by the suggest-case feature
   - Context includes: diagnosis, module, body_part, notes, sources
   - Sources: radiologyassistant.nl, radiopaedia.org, nice.org.uk
   - Claude generates: discussion HTML, Q&A pairs, warnings, safety checklist
        ↓
Step 6: Apply Q&A pairs to case
   - _apply_qa_pairs(case, output)
   - Creates Question and Answer records in DB
   - Each wrapped in <div data-ai-generated="true">
        ↓
Step 7: Apply discussion to case
   - _apply_discussion(case, output, provider, model)
   - Appends attribution footer with contributor name + timestamp
   - Sets case.discussion = discussion + footer
        ↓
Step 8: Save audit trail
   - AiPrelimCaseData record (same as suggest-case)
   - Contains: case_id, provider, model, prompt, response
        ↓
Step 9: Add to CaseApprovalQueue
   - case_id, submitted_by_user_id
   - Update case status: DRAFT → PENDING_REVIEW
        ↓
Step 10: Commit to database
        ↓
Step 11: Email superadmin (best effort)
   - send_case_review_notification(case, current_user)
   - Uses Resend API (same as suggest-case)
   - Includes case details and query metadata
        ↓
Step 12: Return response immediately
   {
     success: true,
     case_id, case_number, diagnosis,
     discussion_html,      ← shown to radiologist immediately
     qa_pairs, qa_count,
     warnings, safety_checklist, sources,
     provider, model,
     case_url: "/view-case/{id}"
   }
```

**Key insight:** Every "generate" action enriches the case library. Once a superadmin reviews and publishes the case, future searches for the same diagnosis will find it directly as a "case" type result — no generation needed.

#### Browse Flow

```
GET /api/algorithms/browse
        ↓
Loads all published cases (with discussion), available TNM calculators,
and available IF calculators
        ↓
Groups them by body section
        ↓
Returns: { "Head and Neck": [...], "Abdomen": [...], ... }
```

#### Admin Reporting Template Management

```
GET  /admin/reporting-templates              → Admin list page
POST /admin/reporting-templates/api          → Create template
PUT  /admin/reporting-templates/api/:id      → Update template
DELETE /admin/reporting-templates/api/:id     → Delete template
POST /admin/reporting-templates/generate     → Generate via Claude
GET  /reporting-template/:slug               → View template
```

The "Generate" endpoint uses `reporting_template_generator.py`:
- Calls Claude API with a comprehensive prompt for interactive decision tree HTML
- Max tokens: 20,000, temperature: 0.3, timeout: 240s
- Validates quality (checkboxes, inputs, copy functionality, recommendations)
- Saves to `ReportingTemplate` table with `is_available = False` (admin must publish)

### Frontend Flow

**Template:** `templates/algorithm_finder.html`

```
User lands on /algorithm-finder
        ↓
Stats row shows: X cases, Y TNM calculators, Z IF calculators
        ↓
Search bar with type filter chips: All | Cases | TNM Calculators | Incidental Findings
        ↓
User types diagnosis → debounced search → GET /api/algorithms/search?q=...
        ↓
Results displayed with type-specific icons:
  - 📋 Case (green) → links to /view-case/{id}
  - 🧬 TNM Calculator (purple) → links to /tnm-calculator/{slug}
  - 🔍 Incidental Finding (blue) → links to /incidental-findings/{slug}
  - 📄 Reporting Template (orange) → links to /reporting-template/{slug}
        ↓
Below search results: "Generate Algorithmic Approach" section (always visible)
  - Diagnosis input (pre-filled from search)
  - Body section dropdown
  - Additional notes textarea
  - "Generate" button
        ↓
User clicks Generate → POST /api/algorithms/generate
        ↓
Loading spinner ("Generating algorithmic approach...")
        ↓
On success, shows generated content:
  - Discussion HTML (the algorithmic approach)
  - Warnings and safety checklist
  - Q&A pairs
  - "View Full Case" link → /view-case/{id}
  - Notice: "Case created and submitted for admin review"
```

---

## Feature 3: Incidental Findings Helper

### Purpose

Deterministic decision trees based on published guidelines (Fleischner, ACR, Bosniak, TI-RADS, etc.). No AI at runtime — pure interactive calculator logic. Same architecture as TNM calculators.

### Backend Flow

**Files:** `incidental_findings/routes.py`, `incidental_findings/generator.py`

#### Public Routes

```
GET /incidental-findings/
   → Loads all available calculators, groups by category
   → Renders finder.html with search + browse-by-category

GET /incidental-findings/:slug
   → Loads calculator by slug
   → Extracts styles and body from self-contained HTML
   → Renders calculator.html wrapper (same pattern as TNM calculator)

GET /incidental-findings/api/search?q=pulmonary+nodule
   → pg_trgm search against finding_name and keywords
   → Falls back to ILIKE for SQLite
   → Returns: [{id, slug, finding_name, category, body_section, description, similarity}]
```

#### Admin Routes

```
GET  /incidental-findings/admin              → Admin list page
POST /incidental-findings/admin/api          → Create calculator manually
PUT  /incidental-findings/admin/api/:id      → Update calculator
DELETE /incidental-findings/admin/api/:id     → Delete calculator
POST /incidental-findings/admin/api/:id/verify → Verify against guideline & publish
POST /incidental-findings/admin/generate     → Generate via Claude
```

#### Generation Flow (Admin Only)

```
POST /incidental-findings/admin/generate
Body: {
  "finding_name": "Pulmonary Nodule",
  "category": "pulmonary",
  "body_section": "Thorax",
  "guideline_source": "Fleischner Society 2017",
  "additional_context": "Include solid and ground-glass categories"
}
        ↓
incidental_findings/generator.py → generate_if_calculator_html()
        ↓
Step 1: Create slug from finding_name (e.g. "pulmonary-nodule")
Step 2: Call Claude API
   - Model: claude-sonnet-4-20250514
   - Max tokens: 20,000
   - Temperature: 0.3
   - Timeout: 240 seconds
   - Prompt: IF_CALCULATOR_PROMPT (comprehensive prompt for interactive forms)
        ↓
Step 3: Validate quality
   - Must have checkboxes, number inputs
   - Must have copy-to-clipboard functionality
   - Must have recommendations section
   - Must have report language generation
        ↓
Step 4: Extract algorithm summary (BeautifulSoup)
   - Looks for reference/summary sections
   - Creates standalone algorithm_html
        ↓
Step 5: Save to IncidentalFindingCalculator table
   - is_available = False (admin must verify against published guideline)
   - Stores generation_prompt and generation_model for reproducibility
        ↓
Return: {success, message, slug, calculator_id}
```

### Frontend Flow

**Templates:** `templates/incidental_findings/finder.html`, `templates/incidental_findings/calculator.html`

#### Finder Page

```
User lands on /incidental-findings
        ↓
Clinical disclaimer banner at top
        ↓
Search bar → debounced search → GET /incidental-findings/api/search?q=...
        ↓
Results shown with finding name, category, guideline source
        ↓
Below search: Browse by category
   - Pulmonary, Renal, Adrenal, Hepatic, Thyroid, etc.
   - Each category shows available calculators as cards
        ↓
Click calculator → /incidental-findings/{slug}
```

#### Calculator Page

```
User on /incidental-findings/pulmonary-nodule
        ↓
Guideline citation banner: "Based on: Fleischner Society 2017"
        ↓
Interactive form (self-contained HTML):
  - Checkboxes: solid vs ground-glass, single vs multiple
  - Number inputs: size in mm
  - Radio buttons: risk factors (high vs low risk)
  - Dropdowns: patient characteristics
        ↓
User fills in findings → JavaScript evaluates decision tree
        ↓
Result shown:
  - Category/grade (e.g. "Fleischner Category 4B")
  - Recommendation (e.g. "CT at 3 months, consider PET-CT")
  - Report language (copy-paste ready):
    "8mm solid pulmonary nodule in the right upper lobe.
     Recommend CT chest in 3 months per Fleischner 2017 guidelines."
  - Copy-to-clipboard button
        ↓
Clinical disclaimer footer
```

---

## TNM Calculator Generation Script

### `scripts/generate_tnm_calculator.py`

This script generates TNM staging calculators and syncs them to both local SQLite and Neon PostgreSQL. It is **separate from the case system**.

### What It Does

```
python scripts/generate_tnm_calculator.py larynx "Larynx" "Head and Neck"
        ↓
Step 1: Generate calculator HTML via Claude API
   - Uses tnm_calculator/tnm_generator.py → generate_calculator_html()
   - Includes disease-specific notes from DISEASE_DEFAULTS dict
   - Claude generates self-contained HTML with interactive forms, mnemonics,
     imaging tips, pitfalls, systematic approach
        ↓
Step 2: Extract algorithm from calculator
   - extract_algorithm_from_calculator(calculator_html, cancer_name)
   - Pulls out the step-by-step reading approach, pitfalls, tips
        ↓
Step 3: Save HTML file
   - tnm_calculator/calculators/{slug}_calc.html
        ↓
Step 4: Save to local SQLite
   - TNMCalculatorContent record
        ↓
Step 5: Sync to Neon PostgreSQL
   - Direct SQL INSERT/UPDATE using SQLAlchemy + connection string
```

### What It Does NOT Do

- Does **not** create `Case` records
- Does **not** create algorithmic discussions attached to cases
- Does **not** trigger the CaseApprovalQueue or email notifications
- Does **not** generate Q&A pairs or AiPrelimCaseData records

### How TNM Calculators Appear in Algorithm Finder

TNM calculators stored in `tnm_calculator_content` are searchable via the Algorithm Finder (`GET /api/algorithms/search?type=oncologic`). They appear as separate "oncologic" type results linking to `/tnm-calculator/{slug}`, completely independent from the case table.

### DISEASE_DEFAULTS

The script includes hand-crafted disease-specific generation notes for 10 cancers:

| Slug | Cancer | Key Features |
|------|--------|-------------|
| `oropharynx` | Oropharyngeal | HPV+/HPV- staging, PACE mnemonic |
| `larynx` | Larynx | 3 subsites, cartilage invasion tree |
| `breast` | Breast | Anatomic + prognostic staging, biomarkers |
| `lung` | Lung (NSCLC) | Detailed size cutoffs |
| `cervix-uteri` | Cervix | FIGO 2018 staging |
| `prostate` | Prostate | Grade groups, PSA levels |
| `colon-and-rectum` | Colorectal | Tumor deposits, CRM |
| `kidney` | Kidney (RCC) | IVC thrombus levels |
| `melanoma` | Melanoma | Breslow depth, ulceration |
| `thyroid` | Thyroid | Age-dependent, anaplastic |

For the remaining ~68 AJCC disease sites without hand-crafted defaults, the script generates with generic AJCC staging data context. Each generation should be reviewed by an admin before publishing.

---

## Cross-Cutting Concerns

### pg_trgm Search

All three features use PostgreSQL's `pg_trgm` extension for fuzzy text matching:

```sql
-- Similarity score (0.0 to 1.0)
similarity(column, 'search term') > 0.1

-- GIN index for performance
CREATE INDEX idx_..._trgm ON table USING GIN (column gin_trgm_ops);
```

Every pg_trgm query has an ILIKE fallback for local SQLite development.

### Claude API Integration

All AI features use the same pattern from `ai_prelim.py`:

| Parameter | Value |
|-----------|-------|
| API URL | `https://api.anthropic.com/v1/messages` |
| API Version | `2023-06-01` |
| Model | `claude-sonnet-4-20250514` (configurable via `CLAUDE_MODEL`) |
| Temperature | 0.2 (On-Call), 0.3 (generators) |
| Timeout | 90s (On-Call), 240s (generators) |
| Auth | `CLAUDE_API_KEY` env var |

### Authentication

| Route Type | Decorator |
|------------|-----------|
| Public (user-facing) | `@login_required` (flask_login) |
| Admin (management) | `@require_admin` (access_control.py) |

### Disclaimer

All three features display a clinical disclaimer:

> **Clinical Decision Support Tool.** This tool is for educational and reference purposes. Always verify against current guidelines and institutional protocols before clinical use.

### Rate Limiting

- Algorithm generation: max 10 DRAFT cases per user (checked before generation)
- On-Call queries: no hard limit, but every query logged for monitoring

### Audit Trail

| Feature | Audit Table | What's Logged |
|---------|-------------|---------------|
| On-Call Helper | `oncall_query_log` | query, matched protocols, response, model, tokens |
| Algorithm Finder | `ai_prelim_case_data` | case_id, prompt, response, provider, model |
| Incidental Findings | (none at runtime) | Deterministic — no AI at runtime |

---

## File Reference

### New Files Created

| File | Purpose |
|------|---------|
| `ai_oncall_helper.py` | On-Call Helper AI module — protocol search, Claude formatting, audit logging |
| `oncall_routes.py` | On-Call Helper Flask blueprint — 13 routes (public + admin) |
| `reporting_routes.py` | Algorithm Finder + Reporting Templates blueprint — 10 routes |
| `reporting_template_generator.py` | Claude-powered reporting template generator |
| `incidental_findings/__init__.py` | IF module init, exports `if_bp` |
| `incidental_findings/routes.py` | IF Flask blueprint — 9 routes (public + admin) |
| `incidental_findings/generator.py` | Claude-powered IF calculator generator |
| `migrations/add_clinical_tools_tables.sql` | Migration for 4 new tables + 16 indexes |
| `templates/oncall_helper.html` | On-Call Helper search + response UI |
| `templates/admin_protocols.html` | Admin protocol CRUD management page |
| `templates/algorithm_finder.html` | Unified algorithm search/browse + generate UI |
| `templates/admin_reporting_templates.html` | Admin reporting template management page |
| `templates/reporting_template_view.html` | Reporting template calculator wrapper |
| `templates/incidental_findings/finder.html` | IF search + browse by category |
| `templates/incidental_findings/calculator.html` | IF calculator wrapper |
| `templates/incidental_findings/admin.html` | IF admin management page |

### Modified Files

| File | Changes |
|------|---------|
| `models.py` | Added 4 models: `ClinicalProtocol`, `OnCallQueryLog`, `ReportingTemplate`, `IncidentalFindingCalculator` + `ProtocolCategory` enum |
| `app.py` | Added imports + registered 3 new blueprints |
| `templates/student_dashboard.html` | Added 3 new dashboard cards: Algorithm Finder, On-Call Helper, Incidental Findings |

---

## API Endpoint Reference

### On-Call Helper

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/on-call-helper/` | login | Main page |
| GET | `/on-call-helper/api/search?q=` | login | Autocomplete |
| POST | `/on-call-helper/api/query` | login | Submit query |
| GET | `/on-call-helper/api/history` | login | Query history |
| GET | `/on-call-helper/api/history/:id` | login | Query detail |
| GET | `/on-call-helper/admin/protocols` | admin | Admin page |
| GET | `/on-call-helper/admin/protocols/api` | admin | List protocols |
| POST | `/on-call-helper/admin/protocols/api` | admin | Create protocol |
| GET | `/on-call-helper/admin/protocols/api/:id` | admin | Get protocol |
| PUT | `/on-call-helper/admin/protocols/api/:id` | admin | Update protocol |
| DELETE | `/on-call-helper/admin/protocols/api/:id` | admin | Delete protocol |
| POST | `/on-call-helper/admin/protocols/api/:id/verify` | admin | Verify & publish |
| POST | `/on-call-helper/admin/protocols/api/:id/unpublish` | admin | Unpublish |

### Algorithm Finder / Reporting

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/algorithm-finder` | login | Main page |
| GET | `/api/algorithms/search?q=&type=` | login | Unified search |
| POST | `/api/algorithms/generate` | login | Generate approach (creates DRAFT case) |
| GET | `/api/algorithms/browse` | login | Browse by body section |
| GET | `/reporting-template/:slug` | login | View template |
| GET | `/admin/reporting-templates` | admin | Admin page |
| POST | `/admin/reporting-templates/api` | admin | Create template |
| PUT | `/admin/reporting-templates/api/:id` | admin | Update template |
| DELETE | `/admin/reporting-templates/api/:id` | admin | Delete template |
| POST | `/admin/reporting-templates/generate` | admin | Generate via Claude |

### Incidental Findings

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/incidental-findings/` | login | Finder page |
| GET | `/incidental-findings/:slug` | login | Calculator view |
| GET | `/incidental-findings/api/search?q=` | login | Search calculators |
| GET | `/incidental-findings/admin` | admin | Admin page |
| POST | `/incidental-findings/admin/api` | admin | Create calculator |
| PUT | `/incidental-findings/admin/api/:id` | admin | Update calculator |
| DELETE | `/incidental-findings/admin/api/:id` | admin | Delete calculator |
| POST | `/incidental-findings/admin/api/:id/verify` | admin | Verify & publish |
| POST | `/incidental-findings/admin/generate` | admin | Generate via Claude |
