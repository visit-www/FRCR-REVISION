# Vetting Module — Requirements

> Source: `Vetting Module Plan.docx` (Apr 2026)
> This is the functional specification for the vetting workflow, derived from the product plan.

## Working flow

1. **Input** — User adds clinical request/history (can be shorthand).
2. **Output** — System generates a structured vetting response.

## Core safety checks

### 1. eGFR check

```
IF contrast study:
    ├── eGFR provided?
    │       ├── YES → Is eGFR ≥ 30? (RCR current threshold)
    │       │         ├── YES → Pass
    │       │         └── NO  → Evaluate clinical indication
    │       │                   ├── Valid indication → Suggest proceeding with rationale
    │       │                   │                      User accept/decline
    │       │                   │                      ├── Accept → Insert rationale alongside eGFR
    │       │                   │                      └── Decline → Highlight eGFR in red
    │       │                   └── No indication → Block / flag
    │       └── NO  → Prompt user for eGFR
    └── Non-contrast → "eGFR not applicable"
```

**Threshold:** eGFR ≥ 30 (per current RCR guidance).

### 2. Allergy check

```
IF contrast study:
    ├── Allergy history provided?
    │       ├── YES → Record
    │       └── NO  → Prompt user to select one of:
    │                 ├── Not known
    │                 ├── No allergies
    │                 └── Contrast allergy present
    └── Non-contrast → "Allergy status not applicable"
```

### 3. Pregnancy check

```
IF pregnancy not mentioned:
    ├── Do NOT insert into final text
    └── Show subtle warning: "Please confirm pregnancy status"
         User options:
         ├── Not pregnant → Insert
         ├── Pregnant     → Warning → Require rationale to proceed
         │                           → If confirmed, insert rationale
         ├── Not applicable → Ignore
         └── (no selection) → Leave silent warning
```

## Investigation advisory

- Analyse the clinical request and suggest the most appropriate investigation.
- If multiple options are appropriate → present as **clickable choices**.
- On selection, auto-populate:
  - Investigation name
  - Coverage
  - Special instructions for radiographer

## Protocol access

### Two-layer protocol presentation

| Layer | Content | Audience |
|---|---|---|
| **Basic** | Study name, coverage, key instructions | Consultant vetting shorthand |
| **Detailed** | Slice thickness, kVp/mAs, flow rate, sequences, timing | Radiographer-level |

### User actions
- Select suggested investigation → view full protocol
- Copy Basic layer
- Copy Detailed layer
- Copy both together

## Protocol authoring

Users can create and save personal protocols with:
- Basic layer
- Detailed layer
- Title (protocol name)
- Keywords (for search)

## Protocol browser

- Display protocols as **card snippets**.
- On click → expand into full protocol view (structured table format).

## Protocol source strategy (Hybrid — recommended)

1. **Primary:** Internal curated database (`ImagingProtocol` admin-verified).
2. **Secondary:** Author-created protocols (`ImagingProtocol` origin=personal).
3. **Fallback:** AI generation from guideline-based templates (`ai_vetting.generate_vetting_protocol()`), grounded by named references in `GUIDELINE_LAYER_MAP.md`.

## RadiQ integration

Yes — **shared protocol intelligence layer**. RadiQ can:
- Answer protocol-related queries
- Suggest appropriate protocols
- Auto-insert protocol summaries in responses

## Module placement

- **Primary:** Standalone module (top navigation).
- **Embedded:**
  - Smart Reporter — pre-report vetting step
  - RadiQ — when user asks clinical appropriateness questions

## Key design principles

1. **Minimise user effort** — one-screen workflow.
2. **Ensure safety compliance** — eGFR/allergy/pregnancy never skipped.
3. **Provide actionable outputs** — copy-ready vetting text.
4. **Seamless integration** — share data with reporting + protocol systems.
