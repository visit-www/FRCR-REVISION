# Algorithmic Report Template — Flow Audit, Gap Analysis & Redesign Spec

> **Date:** February 2026
> **Purpose:** Reference document for building the Smart Reporter feature.
> **Perspective:** Radiology trainee using this tool for daily PACS reporting.

---

## Table of Contents

1. [Current State Audit](#1-current-state-audit)
2. [Identified Gaps](#2-identified-gaps)
3. [Proposed Redesign — "Smart Reporter"](#3-proposed-redesign--smart-reporter)
4. [Scene 1: Help Me Report From Beginning](#4-scene-1-help-me-report-from-beginning)
5. [Scene 2: I Know the Diagnosis — Finalize Report](#5-scene-2-i-know-the-diagnosis--finalize-report)
6. [Scene 3: Quick Reference / Specific Help](#6-scene-3-quick-reference--specific-help)
7. [Output Specification](#7-output-specification)
8. [Safety & Compliance](#8-safety--compliance)
9. [Data Model Changes](#9-data-model-changes)
10. [Technical Architecture Decisions](#10-technical-architecture-decisions)
11. [Implementation Priority](#11-implementation-priority)
12. [Key Files Reference](#12-key-files-reference)

---

## 1. Current State Audit

### Architecture

The feature lives under `/algorithm-finder` with two **disconnected** subsystems:

| Layer | Purpose | Generator | Trigger |
|-------|---------|-----------|---------|
| **Layer A — Algorithmic Reporter** | Static step-by-step algorithm + draft PACS report | `ai_algorithmic_reporter.py` | Public — Algorithm Finder search |
| **Layer B — Reporting Template** | Interactive decision-tree HTML (checkboxes, scores) | `reporting_template_generator.py` | Admin-only — `/admin/reporting-templates/generate` |

**Core problem:** A trainee gets Layer A (static read-only algorithm) but never Layer B (interactive template). The two systems don't talk.

### Current User Journey

```
Trainee opens /algorithm-finder
        │
        ▼
Types diagnosis → pg_trgm search across Cases, TNM Calcs, IF Calcs, Templates
        │
        ├── Match → clickable result cards
        │
        └── No match → "Generate" card appears
                │ (optional: body section + notes)
                ▼
            POST /api/algorithms/generate
                │
                ├── Create DRAFT Case
                ├── Try ai_algorithmic_reporter (primary)
                │     └── fallback → ai_prelim (educational)
                ├── Cache as ReportingTemplate (is_available=False)
                ├── Add to CaseApprovalQueue + email admin
                └── Return read-only content:
                      • Discussion HTML (algorithm)
                      • Draft PACS report (copy btn)
                      • Differentials, recommendations
                      • Checklist, pitfalls, warnings
```

### Backend Logic

| | Primary: `ai_algorithmic_reporter.py` | Fallback: `ai_prelim.py` |
|---|---|---|
| Persona | Consultant radiologist, PACS reporting | Educational teacher |
| Tokens | 8,000 / 120s | 6,000 / 90s |
| Outputs | algorithm HTML, PACS report, differentials, recommendations, checklist, pitfalls | Discussion HTML, Q&A pairs, safety checklist |
| PACS report | Yes (structured) | No |
| Interactive | No | No |

---

## 2. Identified Gaps

| # | Gap | Severity | Status |
|---|-----|----------|--------|
| 1 | **No interactivity** — report is static skeleton, no finding selection | Critical | Addressed in redesign |
| 2 | **Two disconnected layers** — Layer A (public) and Layer B (admin) never merge | Critical | Addressed in redesign |
| 3 | **No modality awareness** — CT vs MRI vs US need different approaches | High | Addressed in redesign |
| 4 | **No findings-first workflow** — tool is diagnosis-first only | High | Addressed in redesign (Scene 1 Option 2) |
| 5 | **Silent fallback** — ai_prelim used without user knowing | High | Addressed in redesign |
| 6 | **Cached template invisible** — is_available=False even after case approval | High | Addressed in redesign |
| 7 | **Generic report** — not tailored to the trainee's actual findings | High | Addressed in redesign |
| 8 | **No edit/refine** — content is read-only, no iteration | Medium | Addressed in redesign (Scene 2) |
| 9 | **No history/favourites** — no quick re-access | Medium | Addressed in redesign |
| 10 | **Opaque rate limit** — 10-draft cap with no visibility | Low | Addressed in redesign |
| 11 | **No PII protection** — user could paste patient details | Medium | Addressed in redesign |
| 12 | **No PACS-ready output** — hidden formatting chars break paste | Medium | Addressed in redesign |

---

## 3. Proposed Redesign — "Smart Reporter"

### Entry Point

Trainee clicks **"Smart Reporter"** (renamed from Algorithm Finder). They see three paths:

```
┌─────────────────────────────────────────────────────────┐
│                    SMART REPORTER                         │
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Scene 1    │  │   Scene 2    │  │   Scene 3    │   │
│  │  Help me     │  │ I know the   │  │ Quick        │   │
│  │  report from │  │ diagnosis —  │  │ reference    │   │
│  │  beginning   │  │ finalize     │  │              │   │
│  │              │  │ the report   │  │              │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
│                                                           │
│  [Search existing cases & algorithms...]                  │
│  [My Recent Reports]                                      │
└─────────────────────────────────────────────────────────┘
```

The existing search bar remains — DB-first for all queries. The three scenes handle **new** reporting workflows.

---

## 4. Scene 1: Help Me Report From Beginning

### Purpose
Guide a trainee through systematic scan reading, step by step, as a consultant would.

### Flow Diagram

```
Scene 1 Entry
    │
    ├── Option A: "I have a clinical question"
    │       │
    │       ▼
    │   User types: "Rule out acute pancreatitis"
    │       │
    │       ▼
    │   Select modality: [CT] [MRI] [US] [XR] [Other]
    │       │
    │       ▼
    │   ──── PROCEED TO ALGORITHMIC PATHWAY ────
    │
    └── Option B: "I have clinical details, help me infer"
            │
            ▼
        User types: "Pain upper abdomen radiating to back"
            │
            ▼
        Claude API call #1: Infer differential list
            │
            ├── Claude confident → returns differential list immediately
            │
            └── Claude needs clarity → asks ONE focused follow-up question
                (e.g. "Is there history of gallstones or alcohol use?")
                User can answer OR skip
                    │
                    ▼
                Claude returns differential list (MAX 2 rounds total)
            │
            ▼
        Differential presented in priority columns:
        ┌───────────────────────────────────────────────┐
        │  🔴 RED — Most likely / surgically urgent      │
        │     ☐ Acute pancreatitis                       │
        │     ☐ Perforated viscus                        │
        │                                                │
        │  🟠 ORANGE — Important considerations          │
        │     ☐ Cholecystitis / choledocholithiasis       │
        │     ☐ Mesenteric ischaemia                     │
        │                                                │
        │  🟡 YELLOW — Less likely but check             │
        │     ☐ Peptic ulcer disease                     │
        │     ☐ Aortic pathology                         │
        └───────────────────────────────────────────────┘
        User selects one or more → these become the clinical questions
            │
            ▼
        Select modality: [CT] [MRI] [US] [XR] [Other]
            │
            ▼
        ──── PROCEED TO ALGORITHMIC PATHWAY ────
```

### The Algorithmic Pathway (Interactive Q&A)

This is the core of the feature. Claude presents the scan reading as an interactive walkthrough.

```
ALGORITHMIC PATHWAY
(Claude has: clinical question(s), modality, optional notes)
    │
    ▼
Claude generates full algorithm skeleton in ONE API call:
  - Ordered sequence of anatomical checkpoints
  - For each checkpoint: question + pre-selected answer options
  - Branching logic (if finding X → ask Y)
    │
    ▼
Presented to trainee step-by-step:

┌─────────────────────────────────────────────────┐
│  Step 1: PANCREAS                                │
│                                                   │
│  How does the pancreas appear?                    │
│                                                   │
│  ○ Normal size and enhancement                    │
│  ○ Bulky and oedematous, loss of lobulation       │
│  ○ Atrophic with calcifications                   │
│  ○ Focal mass lesion identified                   │
│  ○ [Free text...]                                 │
│                                                   │
│  [Next ▶]              [Skip to report ▶▶]       │
└─────────────────────────────────────────────────┘

User selects → answer feeds into the PACS report being built
    │
    ▼
┌─────────────────────────────────────────────────┐
│  Step 2: PERIPANCREATIC FAT                      │
│  (shown because pancreas abnormal in Step 1)     │
│                                                   │
│  Peripancreatic changes:                          │
│                                                   │
│  ☐ Fat stranding present                          │
│  ☐ Fluid collections identified                   │
│  ☐ Peripancreatic vascular involvement            │
│  ☐ No peripancreatic abnormality                  │
│  ○ [Free text...]                                 │
│                                                   │
│  [◀ Back]  [Next ▶]   [Skip to report ▶▶]       │
└─────────────────────────────────────────────────┘

    ... continues through all relevant anatomy ...
    ... includes lines/tubes check ...
    ... includes incidental findings sweep ...
    │
    ▼
At any point: [Skip to report ▶▶] → exits to Scene 2
with all answers gathered so far feeding the report.
```

### Key Design Decisions for the Algorithmic Pathway

1. **One upfront API call** generates the full decision tree with all branches and options. This avoids 3-10s latency per step. Follow-up Claude calls only when user picks "free text."
2. **Branching is conditional:** If pancreas is normal, skip peripancreatic detail steps. The branch logic is embedded in the generated JSON structure.
3. **Every selection maps to report language:** "Bulky and oedematous" → auto-inserts "The pancreas is bulky and oedematous with loss of normal lobulation" into the Findings section.
4. **Lines/tubes and incidental findings** are always included at the end regardless of diagnosis — mirrors real practice.
5. **Checklist items** (from `key_findings_checklist`) become interactive checkboxes the trainee ticks off as they go.

---

## 5. Scene 2: I Know the Diagnosis — Finalize Report

### Purpose
Structure and polish a report when the trainee already knows what they're looking at. Also serves as the exit point from Scene 1.

### Flow

```
Scene 2 Entry
(reached directly OR after Scene 1 walkthrough)
    │
    ▼
If coming from Scene 1:
  - Report auto-populated from walkthrough answers
  - Structured into: INDICATION | TECHNIQUE | COMPARISON | FINDINGS | IMPRESSION | RECOMMENDATION

If entered directly:
  - User types/pastes their draft report or key findings
  - Claude structures it into the standard sections
    │
    ▼
LIVE REPORT EDITOR
┌─────────────────────────────────────────────────────┐
│  INDICATION:                                         │
│  [CT abdomen and pelvis with IV contrast.            │
│   Clinical question: Rule out acute pancreatitis.]   │
│                                                       │
│  TECHNIQUE:                                           │
│  [CT abdomen pelvis, portal venous phase, IV         │
│   contrast 100ml Omnipaque 350.]                     │
│                                                       │
│  COMPARISON:                                          │
│  [No prior imaging available.]                        │
│                                                       │
│  FINDINGS:                                            │
│  [The pancreas is bulky and oedematous...            │
│   Peripancreatic fat stranding is present...          │
│   No drainable fluid collections identified...]       │
│                                                       │
│  IMPRESSION:                                          │
│  [Findings in keeping with acute pancreatitis,        │
│   modified CT severity index 4/10...]                 │
│                                                       │
│  RECOMMENDATION:                                      │
│  [Clinical correlation advised. Consider repeat       │
│   imaging if clinical deterioration.]                 │
├─────────────────────────────────────────────────────┤
│  💬 Ask Claude:                                       │
│  ┌─────────────────────────────────────────────┐     │
│  │ "Help me write the impression"              │     │
│  │ "Check spelling and grammar"                │     │
│  │ "Add recommendations for follow-up"         │     │
│  │ "What CT severity index should I use?"      │     │
│  └─────────────────────────────────────────────┘     │
│                                                       │
│  Claude: "Based on your findings, the modified        │
│  CT severity index is 4 (pancreatic inflammation      │
│  with peripancreatic fat stranding, no necrosis)..."  │
│                                                       │
│  [Insert into report] [Dismiss]                       │
├─────────────────────────────────────────────────────┤
│  [📋 Copy Report]  [💾 Save]  [🔄 Reset]             │
└─────────────────────────────────────────────────────┘
```

### Specific Help Functions in Scene 2

The "Ask Claude" box accepts free-text. Common use cases:
- "Help me write the impression" → Claude drafts impression from findings
- "Help me write recommendations" → Claude suggests follow-up
- "Check spelling and grammar and organise" → Claude returns cleaned version
- "What is the modified CT severity index?" → Quick reference answer
- "Is there anything I missed?" → Claude reviews report for completeness

For each response, Claude asks: **"Insert into report?"** — user confirms or dismisses.

---

## 6. Scene 3: Quick Reference / Specific Help

### Purpose
Quick-access clinical reference without building a full report. Gateway to existing DB tools.

### Flow

```
Scene 3 Entry
    │
    ▼
User selects question type:
┌──────────────────────────────────────────┐
│  What kind of help do you need?           │
│                                            │
│  ○ Guidelines (e.g. "Bosniak 3 cyst")     │
│  ○ Staging (e.g. "T3 rectal cancer")      │
│  ○ Grading (e.g. "AAST liver injury")     │
│  ○ Scoring / Calculators (e.g. "Wells")   │
│  ○ Oncology TNM Staging                    │
│  ○ Conceptual Understanding               │
└──────────────────────────────────────────┘
    │
    ▼
User types question briefly (e.g. "Wells score")
    │
    ▼
Backend: DB search FIRST
    ├── Match in ClinicalProtocol → show verified protocol card
    ├── Match in TNMCalculatorContent → link to existing calculator
    ├── Match in IncidentalFindingCalculator → link to existing calculator
    ├── Match in Cases → link to existing case
    │
    └── No DB match → Claude generates response
         • Table format with rationale and clinical importance
         • Mandatory source citation
         • Flagged as "AI-generated — verify independently"
    │
    ▼
Response shown as clickable card:
  - If DB match: link to full tool (calculator, case, protocol)
  - If AI-generated: inline answer with [Save as Protocol Draft] option
```

### Conceptual Understanding Sub-type

For comparative questions like "DIPNECH versus pulmonary metastasis":
- Claude provides a focused comparison table
- Columns: Feature | DIPNECH | Pulmonary Metastasis
- Rows focus on imaging differentiation by the relevant modality
- Clear, concise, no educational fluff — only what helps distinguish on the scan

---

## 7. Output Specification

### Three Linked Outputs

Every completed Smart Reporter session produces up to three outputs:

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  1. ALGORITHM     │────▶│  2. FINAL REPORT │────▶│  3. CASE REF     │
│                    │     │                    │     │                    │
│  Reusable for     │     │  Saved + linked    │     │  Draft if new     │
│  similar queries   │     │  to algorithm      │     │  Link if exists   │
│                    │     │  and diagnosis     │     │  in DB             │
│  Cached in         │     │  User's personal   │     │  Triggers admin   │
│  ReportingTemplate │     │  report history     │     │  review if new    │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

| Output | Storage | Reuse | Visibility |
|--------|---------|-------|------------|
| **Algorithm** | `ReportingTemplate` table | Shown to future users searching same diagnosis | Draft until admin approves |
| **Final Report** | New `ReportingSession` table | User's personal history | Private to user |
| **Case Reference** | `Case` table (draft) | Published after admin review | Only generated if user opts in |

### Report Format Requirements

1. **HL7-aligned sections:** INDICATION, CLINICAL QUESTION, TECHNIQUE, COMPARISON, FINDINGS, IMPRESSION, RECOMMENDATION
2. **Plain text only** — no hidden formatting, no HTML tags, no rich text markers
3. **Clean for PACS** — copy-paste directly into any PACS/RIS without manual cleanup
4. **No PII** — see Safety section below

### Case Reference Trigger

The case reference (educational case with discussion, Q&A) is **NOT** generated automatically. It is triggered only when:
1. The report reaches a final diagnosis (Scene 1 walkthrough completed or Scene 2 impression written)
2. User is asked: "Would you like to create a case reference guide for this diagnosis?"
3. User clicks yes OR enters a custom diagnosis term
4. DB is searched first — if a published case already exists, the user is shown a link instead
5. If no match → `ai_prelim.py` generates a draft case → saved → admin notified
6. Duplicate detection uses pg_trgm similarity to avoid near-duplicate cases

---

## 8. Safety & Compliance

### PII Protection

**Rule:** No patient-identifiable information may be sent to Claude.

Detection strategy (client-side, before API call):
- Regex patterns: NHS numbers (`\d{3}\s?\d{3}\s?\d{4}`), DOB formats, MRN patterns
- Keyword detection: "patient name", "Dr.", "hospital", common name patterns, postcodes
- If detected → block submission, show: *"Patient-identifiable information detected. Please remove before proceeding. We cannot process personal data."*
- The input field should have a placeholder reminder: *"Do not enter patient names, dates of birth, or hospital numbers"*

### Clinical Disclaimers

Persistent at all stages:
> **Clinical Decision Support Tool** — AI-generated content requires clinical verification. Do not use as the sole basis for clinical decisions. Verify against current guidelines and institutional protocols.

### Audit Trail

Every session logged:
- User ID, timestamps, all inputs and outputs
- Which algorithm was used, which answers were selected
- Final report text
- Whether case reference was generated

---

## 9. Data Model Changes

### New: `ReportingSession`

Tracks a user's complete Smart Reporter session.

```
reporting_session
├── id (PK)
├── user_id (FK → user)
├── session_type: 'scene1' | 'scene2' | 'scene3'
├── clinical_question (TEXT)
├── modality (VARCHAR) — CT, MRI, US, XR, etc.
├── selected_differentials (JSON) — from Scene 1 Option B
├── algorithm_data (JSON) — full algorithm tree + user's answers
├── report_text (TEXT) — final plain-text report
├── report_sections (JSON) — structured {indication, technique, ...}
├── linked_algorithm_id (FK → reporting_template, nullable)
├── linked_case_id (FK → case, nullable)
├── ai_model_used (VARCHAR)
├── total_tokens (INTEGER)
├── created_at (TIMESTAMP)
├── updated_at (TIMESTAMP)
└── is_complete (BOOLEAN)
```

### Modified: `ReportingTemplate`

Add fields for the interactive algorithm tree:
```
+ algorithm_tree_json (TEXT) — structured decision tree for interactive walkthrough
+ modality (VARCHAR) — CT, MRI, US, XR, etc.
+ usage_count (INTEGER DEFAULT 0) — how many times reused
```

---

## 10. Technical Architecture Decisions

### Multi-turn Conversation State

Scenes 1 and 2 are multi-turn. Options:

| Approach | Pros | Cons | **Decision** |
|----------|------|------|-------------|
| Server-side session | Clean, resumable | Adds DB state complexity | |
| Client-side state | Stateless server, simpler | Prompt grows with each turn | |
| **Hybrid** | Best of both | Moderate complexity | **Chosen** |

**Hybrid approach:**
- Scene 1 algorithmic pathway: **one upfront API call** generates the full decision tree. Client-side JS handles step-by-step display. No further API calls unless user picks "free text."
- Scene 2 ask-Claude: Each question is a **new API call** with the current report text as context. No conversation history needed — the report IS the context.
- Scene 1 Option B (infer differential): Max **2 API calls**. First should resolve 90% of cases.

### Algorithm Tree JSON Structure

The upfront API call for the algorithmic pathway returns structured JSON:

```json
{
  "steps": [
    {
      "id": "step_1",
      "organ": "Pancreas",
      "question": "How does the pancreas appear?",
      "options": [
        {
          "label": "Normal size and enhancement",
          "report_text": "The pancreas is normal in size and enhancement.",
          "next_step": "step_5",
          "findings_flag": "normal"
        },
        {
          "label": "Bulky and oedematous",
          "report_text": "The pancreas is bulky and oedematous with loss of normal lobulation.",
          "next_step": "step_2",
          "findings_flag": "abnormal"
        },
        {
          "label": "Free text",
          "report_text": null,
          "next_step": "step_2",
          "findings_flag": "custom"
        }
      ],
      "allow_multiple": false
    },
    {
      "id": "step_2",
      "organ": "Peripancreatic fat",
      "condition": "step_1.findings_flag == 'abnormal'",
      "question": "Peripancreatic changes:",
      "options": [...],
      "allow_multiple": true
    }
  ],
  "lines_tubes_step": { ... },
  "incidental_findings_step": { ... },
  "report_template": {
    "indication": "CT abdomen and pelvis with IV contrast.\nClinical question: {clinical_question}",
    "technique": "CT abdomen pelvis, portal venous phase.",
    "comparison": "No prior imaging available.",
    "findings": "{auto_populated_from_answers}",
    "impression": "{auto_generated_from_findings}",
    "recommendation": "{auto_generated}"
  }
}
```

### API Call Budget Per Session

| Action | API Calls | Estimated Tokens |
|--------|-----------|-----------------|
| Scene 1 Opt A: Enter question + generate algorithm | 1 | ~8,000 |
| Scene 1 Opt B: Infer differential | 1-2 | ~2,000-4,000 |
| Scene 1: Generate algorithm tree | 1 | ~10,000 |
| Scene 1: Free text answer (occasional) | 0-2 | ~500 each |
| Scene 2: Ask Claude (per question) | 1 each | ~1,000-2,000 each |
| Scene 2: Generate impression from findings | 1 | ~1,500 |
| Case reference generation | 1 | ~6,000 |
| **Typical full session** | **3-5 calls** | **~15,000-25,000** |

---

## 11. Implementation Priority

### Phase 1 — Foundation (MVP)

Build the core interactive reporting loop. This alone makes the tool useful.

1. **New landing page** — 3-scene entry point, search bar, recent reports
2. **Scene 2 (finalize report)** — Simplest to build. Report editor with "Ask Claude" chat. This works standalone.
3. **Scene 1 Option A (clinical question → modality → algorithm)** — Single API call generates algorithm tree JSON. Client-side JS renders step-by-step. Answers auto-populate report.
4. **Report output** — Plain text, HL7-aligned sections, copy-to-clipboard, clean for PACS
5. **ReportingSession model** — Save user's reports for history

### Phase 2 — Intelligence

6. **Scene 1 Option B (infer from clinical details)** — Differential inference with colour-coded priority
7. **Scene 3 (quick reference)** — Gateway to existing DB tools + AI fallback
8. **PII detection** — Client-side regex blocking
9. **Case reference trigger** — Post-report opt-in case generation with duplicate detection
10. **Fix caching visibility** — Auto-link template availability to case approval

### Phase 3 — Polish

11. **User history dashboard** — "My recent reports" with search and re-open
12. **Algorithm reuse** — When a cached algorithm tree exists for the same diagnosis+modality, serve it instantly
13. **Scene 3 conceptual understanding** — Comparison tables, differential imaging features
14. **Report refinement chat** — Multi-turn Scene 2 "Ask Claude" with insert/dismiss UX

---

## 12. Key Files Reference

### Current Files (to be modified or replaced)

| File | Lines | Role |
|------|-------|------|
| `reporting_routes.py` | 1-964 | All routes — will be heavily modified |
| `ai_algorithmic_reporter.py` | 1-364 | Primary AI generator — prompt will change for tree JSON output |
| `ai_prelim.py` | — | Fallback / case reference generator — kept for case reference only |
| `reporting_template_generator.py` | 1-311 | Layer B — may be merged into main generator |
| `models.py` | 2538-2590 | `ReportingTemplate` — add fields; new `ReportingSession` model |
| `templates/algorithm_finder.html` | 1-637 | Will be replaced with new Smart Reporter UI |
| `templates/reporting_template_view.html` | 1-155 | May be kept for viewing cached algorithms |
| `templates/admin_reporting_templates.html` | 1-197 | Admin management — minor updates |

### New Files (to be created)

| File | Purpose |
|------|---------|
| `templates/smart_reporter.html` | Main 3-scene landing page |
| `templates/smart_reporter_walkthrough.html` | Scene 1 interactive algorithm UI |
| `templates/smart_reporter_editor.html` | Scene 2 report editor with Ask Claude |
| `templates/smart_reporter_reference.html` | Scene 3 quick reference UI |
| `ai_smart_reporter.py` | New unified AI generator (replaces separate generators) |
| `smart_reporter_routes.py` | New blueprint (or refactored `reporting_routes.py`) |

---

*This document should be read alongside `docs/CLINICAL_TOOLS_ARCHITECTURE.md` for the broader clinical tools context.*
*Previous version of this audit (current-state only) is superseded by this combined document.*
