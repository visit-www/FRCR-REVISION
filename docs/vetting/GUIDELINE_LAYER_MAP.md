# Guideline Layer Map — UK Authoritative Sources

> **Purpose:** named guideline references to embed in `ai_vetting.py` system prompts so the AI anchors to authoritative published sources (not training-data drift).
>
> **Principle:** each layer answers a different class of question. The AI should cite **which layer and which document** its recommendation comes from.

## The four-layer UK framework

| Layer | Role | Example questions it answers |
|---|---|---|
| **NICE** | When & what to scan | "Should I CT or MRI this patient?" — CT vs MRI decision, appropriateness of investigation |
| **RCR** | Standards & governance | "What are the rules for this scenario?" — Trauma imaging, iRefer, major incident, paediatric radiation |
| **UKHSA / IR(ME)R** | Safety & dose | "What DRL applies? Is this justified?" — Dose reference levels, justification, optimisation |
| **NHS Trusts (e.g. Swansea)** | Actual protocols | "What contrast volume and phases?" — Contrast, phases, timing, radiographer parameters |

## Named references to cite in AI prompts

### NICE (what to scan)

| Document | Scope | Use case |
|---|---|---|
| **NICE NG143** | Renal and ureteric stones: assessment and management | First-line CT KUB (non-contrast, low-dose) |
| **NICE NG12** | Suspected cancer: recognition and referral | When imaging is indicated on the 2WW pathway |
| **NICE NG41** | Headaches in >12s | When to image headache |
| **NICE NG232** | Stroke and TIA | Immediate NCCT then CTA for suspected stroke |
| **NICE NG158** | Venous thromboembolism | Wells → D-dimer → CTPA pathway |
| **NICE NG179** | Pulmonary embolism (ACCP adaptation) | PE workup |
| **NICE NG45** | Major trauma: assessment and management | Pre-WBCT triage |
| **NICE CG176** | Head injury | NICE head CT criteria |
| **NICE NG127** | Suspected sepsis | Imaging escalation |

### RCR (standards & governance)

| Document | Scope | Use case |
|---|---|---|
| **RCR iRefer 8th Ed (2017)** | Making the best use of clinical radiology | General appropriateness — 800+ scenarios |
| **RCR Major Adult Trauma Guidance 2024** | WBCT triage, trauma imaging protocol | See `TRAUMA_WBCT_CRITERIA.md` |
| **RCR Standards for Radiology Reporting** | Report structure & urgency | Reporting turnaround SLAs |
| **RCR Paediatric Radiation Guidance** | ALARA in children | Paediatric dose thresholds |

### UKHSA / IR(ME)R (safety & dose)

| Document | Scope | Use case |
|---|---|---|
| **IR(ME)R 2017 (Ionising Radiation Medical Exposure Regulations)** | Justification, authorisation, optimisation | Legal framework for every ionising exposure |
| **UKHSA National Diagnostic Reference Levels (DRLs) 2022** | CT DLP reference levels per study | Benchmark dose appropriateness |
| **ACR Manual on Contrast Media 2025** | Contrast safety (eGFR, allergy, pregnancy, premed) | See `_EVIDENCE_BLOCK` in `ai_vetting.py` |

### NHS Trusts (actual protocols)

| Source | Scope | File / location |
|---|---|---|
| **Swansea NHS Trust CT protocols** | Full departmental CT protocol library | See `CT_PROTOCOLS_REFERENCE.md` Part A |
| **KOC CT protocols (Kent & Canterbury)** | Multi-study CT protocols including Omnipaque dosage | `EXTERNAL_SOURCES.md` pending ingestion |
| **Local MRI enterography protocols** | Clinical + radiographer layers | `EXTERNAL_SOURCES.md` pending ingestion |

## How to embed in `ai_vetting.py`

Add a **`_REFERENCE_LAYER_BLOCK`** to both `ANALYSIS_SYSTEM_PROMPT` and `PROTOCOL_SYSTEM_PROMPT`:

```
REFERENCE LAYERS (UK PRACTICE — cite the layer your recommendation follows):

1. NICE (what/when to scan):
   - NG143 (renal stones), NG12 (cancer 2WW), NG158/NG179 (PE),
     NG232 (stroke), NG45 (major trauma), CG176 (head injury).

2. RCR iRefer 8th Ed (general appropriateness — 800+ scenarios).
3. RCR Major Adult Trauma Guidance 2024 (WBCT triage, trauma protocol).
4. IR(ME)R 2017 (justification & optimisation) + UKHSA DRL 2022 (dose benchmarks).
5. ACR Manual on Contrast Media 2025 (contrast safety — eGFR, allergy, pregnancy).

RULES:
- Cite the specific layer + document you follow for each recommendation.
- If a UK NICE or RCR document directly answers the question, prefer it over ACR.
- For protocol parameters (contrast volume, phases, delays) — follow the internal
  library (Swansea / KOC) served by the calling code. If no library match, cite the
  physiology principle (e.g. "PV 70s per standard abdominal CT physiology").
- Do NOT invent document numbers or editions. If unsure of the exact NICE guideline
  number, cite the generic source ("NICE stroke guidance") rather than guess.
- Do NOT recommend obsolete practices. Example: oral contrast is NOT used for
  acute appendicitis in current UK practice (IV contrast only).
```

## Prompt citation output field

Add a new optional field to `generate_vetting_analysis()` and `generate_vetting_protocol()` JSON output:

```json
{
  "guideline_citation": "NICE NG143 (renal stones) — non-contrast CT KUB first-line",
  ...
}
```

This gives you an audit trail for every AI recommendation.

## Notes

- The model **does** have training exposure to these UK documents. Naming the exact document + year/edition is usually enough to anchor it. Where the model hallucinates document numbers, we catch it at review time via the `guideline_citation` field.
- This is preferable to hand-crafted few-shot lists because: (a) maintenance is a single line change vs updating examples, (b) coverage is implicit across the whole guideline, (c) no brittleness to phrasing variation.
- For protocol parameters we still rely on the internal library (Swansea / KOC) — the AI only cites physiology/principle when no library match is found.
