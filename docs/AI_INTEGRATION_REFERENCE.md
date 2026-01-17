# AI Integration Reference Document

> **Last Updated:** January 17, 2026  
> **Branch:** `main`  
> **Stable Snapshot:** `v1.0-stable-ai-integration`

---

## 🚦 Session Progress (Pick Up Here)

### ✅ Completed (Jan 16, 2026)

1. **Prompt v2 implemented** in `ai_prelim.py`
   - Full detailed prompt matching reference document
   - JSON output with Q&A, discussion, safety checklist, teaching image, sources
   
2. **Orange background styling** for AI content
   - Q&A pairs and Discussion: Wrapped in `<div data-ai-generated="true" class="ai-generated-wrapper">`
   - Visual: Orange background (`rgba(233, 99, 4, 0.1)`) with red left border (`#e96304`)
   - On save (if published/public): Wrapper divs are stripped → content becomes normal

3. **Claude API working** (needs `CLAUDE_API_KEY` env var)
   - Model: `claude-sonnet-4-20250514` (configurable via `CLAUDE_MODEL`)

4. **✅ TESTED SUCCESSFULLY** (Jan 16, 2026)
   - Case: Extradural hematoma (#14)
   - Generated: 8 new Q&A pairs
   - Generated: Full discussion with imaging features, anatomy, herniation patterns
   - Generated: 8-point Clinico-Radiological Safety Focus checklist
   - Generated: Teaching image link (Radiopaedia)
   - Generated: 3 source references (Radiopaedia, Radiology Assistant, NICE)
   - Save verified: Orange styling stripped, content saved as permanent

### 🔜 Next Steps (Tomorrow)

1. **Test the current implementation**
   - Start Flask server
   - Open a case with diagnosis
   - Click "Create Preliminary Case Data"
   - Verify Q&A pairs appear with orange background
   - Verify discussion appended with orange styling
   - Save and verify styling is removed

2. **Consider alternative literature providers** (since no Consensus API yet):
   - Option B: PubMed E-utilities (free, PMID access)
   - Option C: Semantic Scholar API (free, good coverage)
   - Implementation stubs already in `ai_prelim.py`

3. **Future enhancements**:
   - Caching by diagnosis hash
   - Cost tracking
   - User quotas
   - Background job processing (for long API calls)

### ✅ NEW FEATURES (Jan 16-17, 2026 - After Stable Tag)

5. **AI Diagnosis Caching System**
   - Database model: `AiDiagnosisCache` (diagnosis + model, not user-based)
   - Cache check before generation with warning dialog
   - User choice: Regenerate or Cancel
   - Tracks query count and first generation timestamp

6. **AI Generation Cancel Button**
   - "Cancel Generation" button appears during active AI generation
   - Uses `AbortController` to cancel fetch requests
   - Automatically hides when generation completes or is cancelled
   - Stays in edit mode (does not navigate away)

7. **AI Generation Flash Messages**
   - Success message displayed after generation completes
   - Shows count of Q&A pairs generated
   - Indicates if discussion was appended
   - Auto-dismisses after 5 seconds

8. **Image Description Styling**
   - Links in image descriptions display as muted gray (`#6c757d`)
   - Credits, courtesy, and source information styled consistently
   - Maintains readability while distinguishing metadata

9. **Case Deletion Improvements**
   - Fixed foreign key constraint errors during case deletion
   - Explicit cleanup of related records: `CaseFlag`, `AiDiagnosisCache`, `ImportedCaseStaging`, `AiPrelimCaseData`
   - Robust error handling with rollback on failure

10. **Model Color Coding** (Documented for future)
   - Claude: Orange (current)
   - Consensus AI: Green (future)
   - Other models: TBD

### 📍 Key Files to Review

| File | Purpose |
|------|---------|
| `ai_prelim.py` | Claude API wrapper + v2 prompt |
| `app.py` (lines 1963-2130) | `/api/case/<id>/ai-prelim` route |
| `app.py` (lines 2070-2120) | Cache check endpoint `/api/case/<id>/ai-prelim/check-cache` |
| `models.py` | `AiDiagnosisCache` model (no `ai_content_verified` field - removed) |
| `static/edit-case-modal.js` | `createPrelimCaseData()`, `checkAiCacheAndPrompt()`, `stripAiGeneratedWrappers()`, `showAiGenerationFlash()`, `cancelAiGeneration()` |
| `static/style.css` (lines 4132-4298) | `.ai-generated-wrapper` (wrapper div strategy) |

---

## Table of Contents

1. [Current Implementation Status](#current-implementation-status)
2. [Goal: Literature-Driven Radiology Brain](#goal-literature-driven-radiology-brain)
3. [Recommended Architecture](#recommended-architecture)
4. [Cost Estimation](#cost-estimation)
5. [Files Involved](#files-involved)
6. [Next Steps](#next-steps)
7. [AI Prompt Reference](#ai-prompt-reference)

---

## Current Implementation Status

### ✅ What's Already Implemented

| Component | Status | Location |
|-----------|--------|----------|
| Claude API wrapper | ✅ Working (v2 prompt) | `ai_prelim.py` |
| Audit logging model | ✅ Schema ready | `models.py` (AiPrelimCaseData) |
| API route | ✅ Functional | `app.py` `/api/case/<id>/ai-prelim` |
| UI controls | ✅ Working | `edit_case.html` + `edit-case-modal.js` |
| Append-only behavior | ✅ Q&A + discussion | Route appends, never overwrites |
| Visual distinction | ✅ Orange background | Wrapper divs with `data-ai-generated="true"` and `.ai-generated-wrapper` class |
| Auto-normalize on save | ✅ Working | `stripAiGeneratedWrappers()` removes wrapper divs if published/public |
| Cancel generation | ✅ Working | `cancelAiGeneration()` with `AbortController` |
| Flash messages | ✅ Working | `showAiGenerationFlash()` shows generation summary |

### Current Flow

```
User clicks "Create Preliminary Case Data"
    │
    ▼
Client validates (diagnosis required, case saved)
    │
    ▼
POST /api/case/<id>/ai-prelim
    │
    ▼
Server builds detailed prompt (v2) from case context
    │
    ▼
Claude API generates JSON response
    │
    ▼
Server appends Q&A pairs + discussion + teaching image to case
(wrapped in <div data-ai-generated="true" class="ai-generated-wrapper">)
    │
    ▼
Audit record stored in ai_prelim_case_data table
    │
    ▼
User reviews AI content (shown with orange background + red left border)
    │
    ▼
Flash message shows: Q&A pairs count + discussion appended status
    │
    ▼
On Save (if published/public): Wrapper divs are stripped
(content converts to normal styling, same as existing content)
```

### ❌ Gaps vs. Full Vision

| Requirement | Current State | Gap |
|-------------|---------------|-----|
| **Literature retrieval** | ❌ None | No Consensus API integration (applied, awaiting access) |
| **Evidence anchoring** | ⚠️ Partial | Claude generates from training data, not live papers |
| **PMID citations** | ⚠️ Partial | Claude suggests PMIDs but not verified |
| **Multi-query pipeline** | ❌ None | Single prompt, awaiting Consensus for Query A-F |
| **Evidence filtering** | ❌ None | No paper selection logic |
| **Teaching image** | ✅ Working | Prompt requests + displays in discussion |
| **Safety checklist** | ✅ Working | Detailed prompt v2 generates safety items |
| **Visual distinction** | ✅ Done | Orange background wrapper divs for AI content, removed on publish/public |
| **Cost tracking** | ❌ None | No usage metering |
| **Caching** | ✅ Implemented | Diagnosis + model cache with warning dialog |
| **Cancel generation** | ✅ Implemented | AbortController-based cancellation with UI feedback |
| **Flash messages** | ✅ Implemented | Shows Q&A pairs count and discussion appended status |

---

## AI Diagnosis Caching & Watermark System

### Overview

The system now includes intelligent caching to prevent duplicate AI queries and watermark management based on case publication status.

### 1. AI Diagnosis Caching

**Database Model:** `AiDiagnosisCache`
- **Key:** `(diagnosis, provider, model_name)` - unique combination
- **Purpose:** Track which diagnosis+model combinations have been queried
- **Not user-based:** Same diagnosis+model is cached regardless of who queries it

**Workflow:**
1. User clicks "Create Preliminary Case Data"
2. Frontend checks cache via `GET /api/case/<id>/ai-prelim/check-cache`
3. If cached:
   - Show warning dialog: "This diagnosis has already been generated using {model}..."
   - User options:
     - **Regenerate** using same model (overwrites previous)
     - **Cancel** and choose different model
4. If not cached or user chooses regenerate:
   - Proceed with AI generation
   - Update cache after successful generation

**Cache Entry Fields:**
- `diagnosis` (normalized, lowercase)
- `provider` (e.g., 'claude')
- `model_name` (e.g., 'claude-sonnet-4-20250514')
- `first_case_id` - First case that generated this
- `first_user_id` - User who first generated
- `query_count` - How many times queried
- `first_generated_at` - Timestamp
- `last_queried_at` - Last query timestamp

### 2. AI Generation Cancel Button

**UI Control:** `aiCancelBtn` button in `edit_case.html`

**Functionality:**
- Appears automatically when AI generation starts
- Uses `AbortController` to cancel the active fetch request
- Hides automatically when generation completes or is cancelled
- Does not navigate away from edit mode (stays in place)
- Handler set dynamically in `createPrelimCaseData()` function

**Implementation:**
- Button ID: `aiCancelBtn`
- Styled as `btn-danger` (red)
- Display controlled via `style.display = 'inline-block'` / `'none'`
- Abort signal passed to `fetch()` request

### 3. AI Generation Flash Messages

**Function:** `showAiGenerationFlash()` in `edit-case-modal.js`

**Display:**
- Bootstrap alert/toast positioned top-right
- Shows after successful AI generation
- Displays:
  - Q&A pairs count: "Generated **X** Q&A pair(s)"
  - Discussion status: "Discussion was appended" or "not generated"
- Auto-dismisses after 5 seconds
- Container: `#aiFlashMessages` (fixed position)

### 4. Watermark Visibility Rules

| Case State | AI Watermarks Visible? |
|------------|------------------------|
| Draft / In-progress | ✅ Yes |
| Saved (not published) | ✅ Yes |
| Published / Public | ❌ No (removed on save) |

**Implementation:**
- Watermarks are wrapper divs: `<div data-ai-generated="true" class="ai-generated-wrapper">`
- Wrapper divs wrap both Q&A pairs and discussion sections
- On save, if case is `PUBLISHED` or `PUBLIC`, JavaScript strips wrapper divs via `stripAiGeneratedWrappers()`
- If not published, watermarks remain visible
- CSS: Orange background (`rgba(233, 99, 4, 0.1)`) with red left border (`#e96304`)

### 5. Model Color Coding

**Current:**
- **Claude:** Orange/Peachy Orange (`rgba(233, 99, 4, 0.1)`)

**Future Models (Documented):**
- **Consensus AI:** Green (`rgba(40, 167, 69, 0.1)`)
- **Other models:** TBD - each will have unique color

**Implementation:**
- Colors defined in `static/style.css` (`.ai-generated-wrapper`)
- Current: Single wrapper div strategy (simpler than per-element classes)
- Future: Model-specific wrapper classes can be added if needed

### 6. API Endpoints

**Cache Check:**
```
GET /api/case/<id>/ai-prelim/check-cache?provider=claude&model=...
Response: {
  "cached": true/false,
  "cache_entry": {...},
  "all_used_models": [...],
  "requested_provider": "...",
  "requested_model": "..."
}
```

**Generate (with cache bypass):**
```
POST /api/case/<id>/ai-prelim
Body: {
  "provider": "claude",
  "force_regenerate": true  // Bypass cache check
}
```

**Save Case (watermarks removed if published):**
```
PUT /api/case/<id>
Body: {
  ...case fields...,
  "status": "PUBLISHED"  // Watermarks removed on save if published/public
}
```

**Response includes generation summary:**
```
POST /api/case/<id>/ai-prelim
Response: {
  "success": true,
  "added_pairs": [...],
  "discussion_html": "...",
  "pairs_count": 8,
  "discussion_appended": true,
  ...
}
```

---

## Goal: Literature-Driven Radiology Brain

### Vision

Build an AI system that does what a consultant radiologist would do:

1. **Search the literature** → Extract what changes management → Summarise safely
2. **Avoid hallucinations** → Keep inside peer-reviewed medical evidence
3. **Generate FRCR-relevant content** → Q&A, discussion, safety notes, teaching images
4. **Generate FRCR-relevant knowledge** → Q&A, discussion, teaching images
4. **Full audit trail** → Every output traceable to source papers (PMID, journal)

### Consensus AI Retrieval + Synthesis Pipeline

#### PHASE 1 — Clinical Query Construction

When the button is clicked, build three structured Consensus queries from the case:

| Query | Purpose | Structure |
|-------|---------|-----------|
| **Query A** | Core diagnosis | `"{Diagnosis}" AND (CT OR MRI OR imaging OR radiology)` |
| **Query B** | Safety & complications | `"{Diagnosis}" AND (complications OR hemorrhage OR perforation OR rupture OR obstruction OR ischemia OR mortality)` |
| **Query C** | Management-changing imaging features | `"{Diagnosis}" AND ("imaging predictors" OR "CT findings" OR "MRI findings" OR "staging" OR "risk stratification" OR "treatment decision")` |
| **Query D** | Clinical adn radiological significant anatomical aspect | `"{Diagnosis}" AND ("Clinical anatomy" OR "Radiological anatomy"` |
| **Query E** | Pathological aspect that are radiological relevant | `"{Diagnosis}" AND ("Radiopathological correlation" OR "Pathological differentials based on imaging features" OR "Pathophysiology of the diagnosis" OR "Conceptual understanding of disease and how it occurs and its implication in imaging"` |
| **Query F** | Representative and descriptive images | `"{Diagnosis}" AND ("Line diagram to explain anatomical concepts relevant to radiology and its description" OR "Images to explain important diganostic features and how they appear in imaging"` |

These ensure retrieval of:
- Radiology papers
- Prognostic imaging papers
- Surgical / oncologic outcome papers

#### PHASE 2 — Evidence Filtering Rules

From Consensus results, **accept only** papers that satisfy ≥1 of:

✔ Imaging-based prognostic features  
✔ CT or MRI signs  
✔ Staging or grading  
✔ Complication predictors  
✔ Surgical or interventional decision rules  
✔ imaging based criterion

**Reject:**
- Pure pathology
- Molecular biology
- Animal studies
- Non-clinical reviews

#### PHASE 3 — Evidence Extraction

For each accepted paper, extract only:

| Field | Meaning |
|-------|---------|
| Imaging sign | What is seen |
| Modality | CT, MRI, etc |
| What it predicts | Bleeding, perforation, surgery, death, chemo, etc |
| Why it matters | Management change |
| Citation | PMID / Journal |

#### PHASE 4 — Evidence → Radiology Knowledge

Instruct the LLM:
- Use ONLY the extracted Consensus evidence
- Do not invent or generalize

Generate:
- **Viva questions** — "Which CT feature predicts X?"
- **Discussion** — What imaging changes outcomes
- **Safety logic** — Which features = unstable

#### PHASE 5 — Teaching Image

Query: `"{Diagnosis}" AND (figure OR CT image OR MRI image OR schematic)`

Extract:
- Source
- Caption
- Figure reference

---

## Recommended Architecture

### Option A: Consensus AI + Claude (Recommended)

```
┌──────────────────────────────────────────────────────────────────┐
│                        USER CLICKS BUTTON                        │
└──────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│ PHASE 1: Query Construction (Server-side)                        │
│ • Build 3 Consensus queries from diagnosis                       │
│ • Query A: Core diagnosis + imaging                              │
│ • Query B: Complications + safety                                │
│ • Query C: Management-changing findings                          |
| . Query D: Clinical adn radiological significant anatomical aspect|
| . Query E: Pathological aspect that are radiological relevant    |
| . Query F : Representative and descriptive images                |
└──────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│ PHASE 2: Evidence Retrieval (Consensus API)                      │
│ • Call Consensus API for each query                              │
│ • Receive: papers, abstracts, PMIDs, journal refs                │
│ • Cache results by diagnosis hash (24-48h TTL)                   │
└──────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│ PHASE 3: Evidence Filtering (Server-side rules)                  │
│ • Accept: imaging signs, CT/MRI findings, staging 
| . Accept FRCR exam related materia.               │
│ • Reject: pathology-only, animal studies, non-clinical           │
│ • Score relevance to radiology practice                          │
└──────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│ PHASE 4: LLM Synthesis (Claude)                                  │
│ • Input: ONLY filtered evidence atoms                            │
│ • Prompt: "Use ONLY these papers, do not invent"                 │
│ • Output: Q&A, discussion, safety checklist                      │
│ • Every claim must cite a PMID                                   │
└──────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│ PHASE 5: Store + Append                                          │
│ • Store evidence + LLM output in audit table                     │
│ • Append Q&A pairs to case                                       │
│ • Append discussion with clickable PMID links                    │
│ • Store teaching image reference if found                        │
└──────────────────────────────────────────────────────────────────┘
```

### Alternative Providers (If Consensus API Unavailable)

| Alternative | Pros | Cons | Implementation Status |
|-------------|------|------|----------------------|
| **Semantic Scholar API** | Free, good coverage | No built-in synthesis | Placeholder in `ai_prelim.py` |
| **PubMed E-utilities** | Free, PMID access | Requires more parsing | Placeholder in `ai_prelim.py` |
| **Perplexity API** | Good synthesis | Less citation control | Not started |
| **Claude with web search** | Integrated | Hallucination risk | Not recommended |

**Note:** PubMed and Semantic Scholar placeholders are in `ai_prelim.py` ready for implementation when Consensus API is unavailable.

---

## Cost Estimation

### Consensus AI Pricing
- Typically **$0.01–$0.05 per query** (API access varies)
- 3 queries per case = **$0.03–$0.15 per case**

### Claude API Pricing (claude-3-5-sonnet)
- Input: ~$3/1M tokens
- Output: ~$15/1M tokens
- Estimated per case: **$0.02–$0.08**

### Combined Estimate

| Volume | Consensus | Claude | Total/Month |
|--------|-----------|--------|-------------|
| 100 cases | $3–15 | $2–8 | **$5–25** |
| 1,000 cases | $30–150 | $20–80 | **$50–250** |
| 10,000 cases | $300–1,500 | $200–800 | **$500–2,500** |

### Cost Optimization Strategies

1. **Cache by diagnosis hash** — same diagnosis = skip re-query (24–48h TTL)
2. **Batch pre-generation** — run overnight for common diagnoses
3. **Tiered model** — use cheaper model for filtering, sonnet for synthesis
4. **User quota** — limit AI generations per user/day

---

## Files Involved

| File | Purpose |
|------|---------|
| `ai_prelim.py` | Claude API wrapper, prompt builder |
| `models.py` | `AiPrelimCaseData` audit model, `AiDiagnosisCache` model |
| `app.py` | `/api/case/<id>/ai-prelim` route, `/api/case/<id>/ai-prelim/check-cache` route |
| `templates/edit_case.html` | UI controls (dropdown + button, cancel button, flash container) |
| `static/edit-case-modal.js` | `createPrelimCaseData()`, `checkAiCacheAndPrompt()`, `stripAiGeneratedWrappers()`, `showAiGenerationFlash()`, `cancelAiGeneration()` |
| `static/style.css` | `.ai-generated-wrapper` styles, AI cache modal styling |
| `templates/view_case.html` | View mode watermark detection and styling |

### Database Tables

```sql
-- Existing (needs migration if not created)
CREATE TABLE ai_prelim_case_data (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES case(id),
    created_by_user_id INTEGER NOT NULL REFERENCES user(id),
    provider VARCHAR(50) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    prompt_version VARCHAR(20) DEFAULT 'v1',
    request_payload TEXT,
    response_payload TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Future: Evidence cache table
CREATE TABLE ai_evidence_cache (
    id SERIAL PRIMARY KEY,
    diagnosis_hash VARCHAR(64) UNIQUE,
    query_type VARCHAR(20),  -- 'core', 'safety', 'management'
    evidence_json TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);
```

---

## Next Steps

### Phase 1: Test & Validate (Immediate)

1. **Test current Claude implementation**
   - Ensure `CLAUDE_API_KEY` is set in environment
   - Open edit case → click "Create Preliminary Case Data"
   - Verify output quality and formatting

### Phase 2: Alternative Literature Providers (No Consensus API Yet)

Since Consensus API is not yet available, consider implementing:

| Provider | Status | Notes |
|----------|--------|-------|
| **PubMed E-utilities** | Not implemented | Free, PMID access, requires parsing |
| **Semantic Scholar API** | Not implemented | Free, good coverage, JSON responses |

Implementation stubs exist in `ai_prelim.py` (lines 409-430).

### Phase 3: Enhancements (Future)

1. **Caching** — Cache by diagnosis hash (24-48h TTL)
2. **Cost tracking** — Log token usage, estimate costs
3. **User quotas** — Limit AI generations per user/day
4. **Async processing** — Background jobs for long API calls
5. **Evidence anchoring** — When literature API available, cite PMIDs

---

## AI Prompt Reference

### Preliminary Case Data Generator — System Prompt

Use this prompt when calling the LLM to generate case content:

```
SYSTEM / INSTRUCTION PROMPT

You are a clinical radiology knowledge engine designed to help radiologists prepare, report, and teach from real clinical cases.
Your output must be clinically safe, FRCR-relevant, and radiology-focused.

You are given structured case data.
Your job is to generate high-yield preliminary case material that helps determine whether a candidate is safe to report independently.

═══════════════════════════════════════════════════════════════════
INPUT
═══════════════════════════════════════════════════════════════════

You will receive:
• Case diagnosis (may be empty)
• Modality (CT / MRI / X-ray / etc.)
• Body part
• Optional free-text notes
• Optional existing content (do not overwrite)

═══════════════════════════════════════════════════════════════════
STEP 1 — DIAGNOSIS HANDLING
═══════════════════════════════════════════════════════════════════

If Case Diagnosis is empty, ask:

"Please enter the working radiological diagnosis before I can generate preliminary case data."

Do NOT proceed until diagnosis is provided.

If diagnosis exists:
• Use it as the anchor concept
• Do not rephrase or replace it
• Do not invent a new diagnosis

═══════════════════════════════════════════════════════════════════
STEP 2 — CONTENT CREATION RULES
═══════════════════════════════════════════════════════════════════

You must:
• Append your output to existing case data
• Never overwrite or delete existing content
• Be concise but clinically powerful
• Prioritize safety, management-changing features, and anatomical danger points

This is NOT a textbook.
This is radiology survival knowledge.

═══════════════════════════════════════════════════════════════════
OUTPUT STRUCTURE
═══════════════════════════════════════════════════════════════════

Your output must contain four clearly separated sections in this exact order:

───────────────────────────────────────────────────────────────────
1) HIGH-YIELD QUESTION & ANSWER PAIRS
───────────────────────────────────────────────────────────────────

Create clinically realistic FRCR-style viva questions that test:
• Is this diagnosis life-threatening?
• What must not be missed?
• What changes management?
• What findings make this unsafe to ignore?
• What should be reported urgently?

Rules:
• Each question must be something a consultant would ask in real reporting
• Each answer must be short, precise, and clinically actionable
• Avoid trivia
• Prefer "what changes management" over rare facts

Format:
Q: …
A: …

───────────────────────────────────────────────────────────────────
2) DISCUSSION (RADIOLOGIST'S HIGH-YIELD NOTES)
───────────────────────────────────────────────────────────────────

Provide:
• Short paragraphs
• Bullet lists
• Tables (HTML or pipe table)
• One-liners

Focus on:
• Dangerous anatomy
• Spread patterns
• Complications
• Imaging signs
• What differentiates mild vs severe
• What differentiates stable vs unstable
• What must be mentioned in a report

If staging / grading / classification exists:
• Do NOT give full TNM or full scoring
• Instead give:
    • The 2–4 most important differentiating features
    • What changes management

───────────────────────────────────────────────────────────────────
3) CLINICO-RADIOLOGICAL SAFETY FOCUS
───────────────────────────────────────────────────────────────────

Explicitly state:
• What makes this diagnosis dangerous
• What imaging features mean urgent action
• What a junior must not miss
• What leads to legal or clinical harm if omitted

This section answers:

"Is the candidate safe to report this independently?"

───────────────────────────────────────────────────────────────────
4) TEACHING IMAGE WITH CREDITS
───────────────────────────────────────────────────────────────────

Provide ONE image that explains a key concept of this diagnosis:
• CT, MRI, or line diagram
• Something that explains anatomy, spread, or a classic sign

For the image provide:
• Image title
• Direct image link
• Short description
• What it teaches
• Source and credit
• Citation or site name

Example format:
Image: …
Link: …
Description: …
Teaching point: …
Source / Credit: …

Use medical sources such as:
• Radiopaedia
• Radiology Assistant
• AJR
• NEJM Image in Clinical Medicine
• Cancer staging atlases
• Or medical sources available to Consensus AI

═══════════════════════════════════════════════════════════════════
FORMATTING RULES
═══════════════════════════════════════════════════════════════════

You may use:
• Bold for danger
• Italics for concepts
• Tables
• Bullet lists
• Arrows (→)

Keep everything:
• Clinically relevant
• Radiology-focused
• Easy to retain

═══════════════════════════════════════════════════════════════════
QUALITY BAR
═══════════════════════════════════════════════════════════════════

Your output should feel like:

A senior radiologist writing high-yield exam notes + safety checklist 
for a trainee about to report this case alone.

If something is not relevant to reporting, do not include it.
```

### JSON Output Schema (For Programmatic Use)

When requesting JSON output, use this schema:

```json
{
  "qa_pairs": [
    {"question": "...", "answer": "..."}
  ],
  "discussion": "...",
  "safety_checklist": ["..."],
  "teaching_image": {
    "title": "...",
    "link": "...",
    "description": "...",
    "teaching_point": "...",
    "source": "..."
  },
  "sources": [
    {"title": "...", "url": "...", "pmid": "..."}
  ],
  "warnings": ["..."]
}
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CLAUDE_API_KEY` | Yes | — | Anthropic API key |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-20250514` | Model to use |
| `CONSENSUS_API_KEY` | Future | — | Consensus AI API key |
| `AI_CACHE_TTL_HOURS` | Future | `24` | Evidence cache TTL |
| `AI_MAX_REQUESTS_PER_DAY` | Future | `50` | User quota |

---

## References

- [Consensus AI](https://consensus.app) — Literature search
- [Anthropic Claude API](https://docs.anthropic.com) — LLM synthesis
- [Semantic Scholar API](https://api.semanticscholar.org) — Alternative literature search
- [PubMed E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/) — Free PMID access

---

*This document should be updated as the AI integration evolves.*
