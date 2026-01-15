# AI Integration Reference Document

> **Last Updated:** January 2026  
> **Branch:** `feature/ai-integration`  
> **Stable Snapshot:** `v1.0-stable`

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
| Claude API wrapper | ✅ Working | `ai_prelim.py` |
| Audit logging model | ✅ Schema ready | `models.py` (AiPrelimCaseData) |
| API route | ✅ Functional | `app.py` `/api/case/<id>/ai-prelim` |
| UI controls | ✅ Basic | `edit_case.html` + `edit-case-modal.js` |
| Append-only behavior | ✅ Q&A + discussion | Route appends, never overwrites |

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
Server builds prompt from case context
    │
    ▼
Claude API generates JSON response
    │
    ▼
Server appends Q&A pairs + discussion to case
    │
    ▼
Audit record stored in ai_prelim_case_data table
```

### ❌ Gaps vs. Full Vision

| Requirement | Current State | Gap |
|-------------|---------------|-----|
| **Literature retrieval** | ❌ None | No Consensus API integration |
| **Evidence anchoring** | ⚠️ Partial | Claude generates from training data, not live papers |
| **PMID citations** | ❌ None | No real references, just URL sources |
| **Multi-query pipeline** | ❌ None | Single prompt, no Query A/B/C |
| **Evidence filtering** | ❌ None | No paper selection logic |
| **Teaching image** | ⚠️ Schema only | Prompt asks for it, but no real image retrieval |
| **Safety checklist** | ⚠️ Schema only | Generated but not verified |
| **Cost tracking** | ❌ None | No usage metering |
| **Caching** | ❌ None | Every click = new API call |

---

## Goal: Literature-Driven Radiology Brain

### Vision

Build an AI system that does what a consultant radiologist would do:

1. **Search the literature** → Extract what changes management → Summarise safely
2. **Avoid hallucinations** → Keep inside peer-reviewed medical evidence
3. **Generate FRCR-relevant content** → Q&A, discussion, safety notes, teaching images
4. **Full audit trail** → Every output traceable to source papers (PMID, journal)

### Consensus AI Retrieval + Synthesis Pipeline

#### PHASE 1 — Clinical Query Construction

When the button is clicked, build three structured Consensus queries from the case:

| Query | Purpose | Structure |
|-------|---------|-----------|
| **Query A** | Core diagnosis | `"{Diagnosis}" AND (CT OR MRI OR imaging OR radiology)` |
| **Query B** | Safety & complications | `"{Diagnosis}" AND (complications OR hemorrhage OR perforation OR rupture OR obstruction OR ischemia OR mortality)` |
| **Query C** | Management-changing imaging | `"{Diagnosis}" AND ("imaging predictors" OR "CT findings" OR "MRI findings" OR "staging" OR "risk stratification" OR "treatment decision")` |

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
│ • Query C: Management-changing findings                          │
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
│ • Accept: imaging signs, CT/MRI findings, staging                │
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

| Alternative | Pros | Cons |
|-------------|------|------|
| **Semantic Scholar API** | Free, good coverage | No built-in synthesis |
| **PubMed E-utilities** | Free, PMID access | Requires more parsing |
| **Perplexity API** | Good synthesis | Less citation control |
| **Claude with web search** | Integrated | Hallucination risk |

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
| `models.py` | `AiPrelimCaseData` audit model |
| `app.py` | `/api/case/<id>/ai-prelim` route |
| `templates/edit_case.html` | UI controls (dropdown + button) |
| `static/edit-case-modal.js` | `createPrelimCaseData()` client function |

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

### Immediate Questions to Answer

1. **Do you have Consensus AI API access?** (Their API is invite-only/enterprise)
2. **Is async OK?** (Background job = better UX for 10-30s operations)
3. **Cost ceiling?** (Should we build in hard limits?)
4. **Teaching image priority?** (Real image retrieval is complex — defer or implement?)

### Implementation Order (When Ready)

1. Create `consensus_client.py` with query builder
2. Add evidence filtering rules
3. Modify `ai_prelim.py` to accept evidence as input
4. Update prompt to enforce "cite only provided PMIDs"
5. Add caching layer (Redis or DB table)
6. Add background job processing (Celery/RQ)
7. Add cost tracking and user quotas

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
| `CLAUDE_MODEL` | No | `claude-3-5-sonnet-20240620` | Model to use |
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
