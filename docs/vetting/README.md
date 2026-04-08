# Vetting Module — Reference Material

> **Purpose:** ground-truth reference content for the Vetting Module AI and protocol library.
> Derived from `Vetting Module Plan.docx` (Apr 2026) and external curated sources.
>
> **Scope:** this folder contains **reference material only** (what the AI should know, what protocols exist).
> For **architecture / implementation plan**, see `docs/plans/VETTING_TOOL_PLAN.md`.

## Files in this folder

| File | Purpose | Used by |
|---|---|---|
| `REQUIREMENTS.md` | Workflow spec, core safety checks (eGFR / allergy / pregnancy), UX principles | Product + frontend + `vetting_routes.py` |
| `CT_PROTOCOLS_REFERENCE.md` | Merged CT protocol library (Swansea NHS Trust + Radiology Assistant) | Seed data for `ImagingProtocol` admin table |
| `GUIDELINE_LAYER_MAP.md` | Which guideline layer answers which question (NICE / RCR / UKHSA / NHS Trusts) | `ai_vetting.py` prompt references |
| `TRAUMA_WBCT_CRITERIA.md` | Whole-body CT trauma triage criteria (RCR Major Adult Trauma 2024) | Seed data for `VettingAlgorithm` |
| `EXTERNAL_SOURCES.md` | URLs + local PDF paths pending ingestion | Future batch import scripts |

## How this reference material is used

```
┌──────────────────────────────────────────────────────────────────┐
│  User submits referral → ai_vetting.generate_vetting_analysis()  │
└──────────────────────────┬───────────────────────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          ▼                                 ▼
   _search_protocols()              _search_algorithms()
   (ImagingProtocol table)          (VettingAlgorithm table)
          │                                 │
   seeded from                       seeded from
   CT_PROTOCOLS_REFERENCE.md         TRAUMA_WBCT_CRITERIA.md
   + EXTERNAL_SOURCES.md (PDFs)      + NICE pathways
          │                                 │
          └────────────────┬────────────────┘
                           ▼
              Library match found?
                     ┌─────┴─────┐
                    YES           NO
                     │             │
              Use library    generate_vetting_protocol()
                             (AI fallback — grounded by
                              GUIDELINE_LAYER_MAP.md refs)
```

## Key architectural decisions (from the plan doc)

1. **Hybrid sourcing** — internal curated DB is primary, guideline-based AI templates are fallback.
2. **RadiQ integration** — shared protocol intelligence layer across modules.
3. **Placement** — standalone module + contextually embedded in Smart Reporter and RadiQ.
4. **Two-layer protocols** — Basic layer (consultant shorthand) + Detailed layer (radiographer technical).

## Status

- Created: 2026-04-08
- Source document: `/Users/zen/Downloads/radinights plans/Vetting Module Plan.docx`
- Pending ingestion: PDFs in `EXTERNAL_SOURCES.md`
