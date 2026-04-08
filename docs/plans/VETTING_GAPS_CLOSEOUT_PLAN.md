# Vetting Module — Gaps Closeout Plan

> **Status:** Planning — follow-up to the April 2026 Contrast Reaction Card + source-rebrand PR
> **Parent plan:** `/Users/zen/Downloads/radinights plans/Vetting Module Plan.docx`
> **Audit source:** Conversation audit (Apr 8, 2026) of plan vs. implementation

---

## Context

The original **Vetting Module Plan** was authored before any code existed. Over the past few months we have built 90% of it — scene-based UI, 124 imaging protocols, 20 vetting algorithms, 4-layer reference prompt (NICE/RCR/UKHSA/NHS Trusts), ACR Contrast Reaction Card, paediatric filter, Smart Reporter embed. An audit of the plan against the current codebase identified **11 outstanding items** split across three priority tiers.

This document captures those gaps, the rationale for tackling each, the exact files/routes to touch, and the verification plan.

**What is NOT in this plan:** the gaps that were either overtaken by better sources (e.g., Aberdeen oncology corpus replaced the planned "internal curated DB" concept) or rendered obsolete by later decisions. Those are noted in the "Deliberately deferred / obsoleted" section at the bottom.

---

## 🔴 Critical Gaps (5 items)

### C1. RadiQ vetting integration

**Plan intent:** "Can protocols be used in RadiQ? Yes — strongly recommended. RadiQ can answer protocol-related queries, suggest appropriate protocols, auto-insert protocol summaries in responses. This creates a shared protocol intelligence layer across modules."

**Current state:** `ai_radiq.py` and `radiq_routes.py` contain zero references to `ImagingProtocol`, `VettingAlgorithm`, or the vetting module. RadiQ's knowledge is siloed from the protocol library.

**Approach:**
1. Add a lightweight protocol-retrieval helper in `ai_radiq.py`:
   ```python
   def _retrieve_protocols_for_query(query: str, limit: int = 3) -> str:
       """Return a compact prompt snippet with top-matching protocols."""
       from models import ImagingProtocol
       # Reuse the existing vetting _search_protocols() to avoid duplication
       from vetting_routes import _search_protocols
       rows = _search_protocols(query, limit=limit, is_paediatric=None)
       if not rows: return ""
       lines = ["\n\nRELEVANT PROTOCOLS FROM VETTING LIBRARY:"]
       for p in rows:
           lines.append(f"- {p.title}: {p.shorthand_text or '(see detailed view)'}")
       return "\n".join(lines)
   ```
2. Inject the retrieved context into the RadiQ system prompt when the user's question mentions imaging/protocol keywords (`protocol`, `CT`, `MRI`, `contrast`, `phase`, `delay`, `timing`, etc.).
3. Add a "Related Protocols" footer on RadiQ responses that link to `/vetting/protocols?search=...`.

**Files:** `ai_radiq.py` (add helper + prompt injection), `radiq_routes.py` (optional: footer rendering), `templates/radiq.html` (optional: footer display).

**Verification:** Ask RadiQ "What's the contrast protocol for pancreatic cancer?" — it should quote the Swansea/Aberdeen protocol from the DB and link to `/vetting/protocols`.

---

### C2. CT GI Bleeding protocol

**Plan source:** Radiology Assistant — 3-phase (non-contrast, arterial 35s, PV 70s).

**Current state:** No such protocol exists in the DB (searched ILIKE '%bleed%' — zero results).

**Content:**
```json
{
  "title": "CT GI Bleed / GI Haemorrhage",
  "modality": "CT",
  "body_section": "Abdomen/Pelvis",
  "shorthand_text": "CT AP triphasic — non-con + arterial 35s + PV 70s. No oral.",
  "validation": { "requires_egfr": true, "egfr_threshold": 30 },
  "indications": ["Active GI bleed", "Melena", "Haematemesis",
                  "Obscure GI bleeding", "Post-endoscopy bleeding"],
  "detailed": [
    ["Preparation", "None. No oral contrast (masks active bleeding)."],
    ["Contrast", "100–150 ml @ 5 ml/s, 18G IV"],
    ["Phases", "Non-contrast → Arterial 35s → Portal venous 70s"],
    ["Coverage", "Diaphragm to symphysis"],
    ["Comments", "Active extravasation = contrast pooling on arterial that increases on PV"]
  ]
}
```

**Files:** Add via admin `/vetting/admin/protocols` POST endpoint (or local helper script), then migration marker to idempotently insert on deploy.

---

### C3. CT Brain Dementia protocol

**Plan source:** Radiology Assistant — standard brain CT with coronal MTL reconstructions.

**Current state:** No dementia-specific brain protocol (ID 1 is "CT Brain Routine (Plain)" — general purpose).

**Content:**
```json
{
  "title": "CT Brain — Dementia Assessment",
  "modality": "CT",
  "body_section": "Brain",
  "shorthand_text": "Plain CT brain + coronal reformats through medial temporal lobes for hippocampal atrophy (Scheltens score).",
  "validation": { "requires_egfr": false, "allergy_check_required": false },
  "indications": ["Suspected dementia", "Cognitive decline",
                  "MMSE drop", "Alzheimer workup"],
  "detailed": [
    ["Preparation", "None"],
    ["Contrast", "None"],
    ["Phases", "Plain"],
    ["Coverage", "Vertex to C1"],
    ["Reformats", "Axial 5 mm + coronal 3 mm perpendicular to long axis of hippocampus"],
    ["Comments", "Assess medial temporal lobe atrophy (Scheltens 0–4). MRI preferred if available (NICE NG97)."]
  ]
}
```

---

### C4. CT Anastomosis Leak protocol

**Plan source:** Radiology Assistant — rectal contrast (50 ml in 750 ml water) + IV immediately after.

**Current state:** No anastomosis leak protocol exists.

**Content:**
```json
{
  "title": "CT Anastomosis Leak / Post-Op Bowel",
  "modality": "CT",
  "body_section": "Abdomen/Pelvis",
  "shorthand_text": "Rectal contrast 50ml in 750ml water + IV contrast immediately after. Non-con + PV 35s.",
  "validation": { "requires_egfr": true, "egfr_threshold": 30 },
  "indications": ["Post-operative fever", "Suspected anastomotic leak",
                  "Bowel surgery complications", "Raised inflammatory markers post-op"],
  "detailed": [
    ["Preparation", "Rectal tube — instill 50ml water-soluble contrast in 750ml water"],
    ["Contrast", "100 ml IV @ 3 ml/s immediately after rectal instillation"],
    ["Phases", "Non-contrast → Portal venous 35s"],
    ["Coverage", "Diaphragm to symphysis"],
    ["Comments", "Rectal contrast assesses integrity of bowel; IV assesses abscess/collection. Do NOT delay IV — inject during rectal phase."]
  ]
}
```

---

### C5. KOC Omnipaque Weight-Based Dose Calculator

**Plan source:** `/Users/zen/Library/CloudStorage/OneDrive-Personal/Workstation companions/Protocols/CT-Protocols-KOC/CT-omnipauqe-dossage-protcols.pdf`

**Current state:** Not ingested. Paediatric protocols (IDs 74-98) are weight-banded but reference generic contrast volumes, not Omnipaque-specific iodine dose tables.

**Approach:**
1. **Extract the PDF** into markdown (local only, not committed) using the same pattern as `docs/vetting/ACR_CONTRAST_BLOCK_2025.md`.
2. **Build a JS calculator** in the Contrast Reaction Card Tab 6 (paediatric calculator) — add "Iodine Dose" output alongside the existing Epi/Diphen/NS outputs.
3. **Store the concentration mapping** as a small JSON constant: Omnipaque 240/300/350 → mg iodine/ml.
4. **Inputs**: weight (kg) + concentration. **Outputs**: volume (ml), total iodine (mg I), total iodine per kg (mg I/kg).
5. **Reference table** in the card: adult 1.5 g I/kg for routine CAP, 2 g I/kg for CTA, etc.

**Files:** `templates/partials/_contrast_reaction_card.html` (Tab 6 extension), local ingestion of the PDF to docs.

---

## 🟡 Important Gaps (4 items)

### I1. Pregnancy "do-not-insert-unless-confirmed" UX wiring

**Plan intent:** "If not mentioned: do not insert into final text. Show subtle warning to user: 'Please confirm pregnancy status'. User options: Not pregnant / Pregnant (trigger warning, require rationale) / Not applicable (ignore)."

**Current state:** `vetting.html` has a 3-option dropdown (not_pregnant / possible / pregnant) but the Quick Clean text unconditionally inserts pregnancy status. The "rationale-required-on-confirmed-pregnancy" flow is missing.

**Approach:**
1. When pregnancy dropdown is empty → Quick Clean does NOT write a pregnancy line (currently writes "Pregnancy: unknown").
2. When user picks "Pregnant" → open a small inline rationale input, require text before `Continue`.
3. When "Not applicable" (via N/A skip button) → insert nothing.
4. Only insert "Not pregnant" or "Pregnant [rationale]" when explicitly chosen.

**Files:** `templates/vetting.html` — `updateQuickCleanOutput()` JS function + pregnancy row.

---

### I2. RCR WBCT criteria verbatim in AI prompt

**Plan source:** RCR Major Adult Trauma Guidance 2024 — the exact triage table (Mechanism / Apparent Injury / Vital Signs, 3 categories, 1 positive → WBCT).

**Current state:** `_REFERENCE_LAYER_BLOCK` references the document by name but does not embed the triage table verbatim. The AI may paraphrase or miss specific thresholds (GCS <14, SBP <90, RR <10 or >29, SaO2 <93%).

**Approach:** Add `_WBCT_CRITERIA_BLOCK` to `ai_vetting.py` — ~30 lines, verbatim from the RCR 2024 guidance already in the conversation. Include it only in `ANALYSIS_SYSTEM_PROMPT` (not the protocol prompt) since it's about indication-level vetting, not scanner parameters.

**Files:** `ai_vetting.py` lines ~100 (before `_ACR_CONTRAST_BLOCK`).

---

### I3. RCR Primary/Secondary Survey Report Template

**Plan source:** RCR Major Adult Trauma Guidance 2024 PDF — pulls the primary + secondary survey reporting template.

**Current state:** No such template exists in `radiology_template` table.

**Approach:**
1. Extract the 2-template structure from the RCR PDF (user-supplied locally, not committed).
2. Insert as two `RadiologyTemplate` rows with `origin='admin'`, linked via Smart Reporter's template picker.
3. Add a `keywords` entry so it surfaces on "WBCT" / "polytrauma" / "major trauma" queries.

**Files:** Admin creation via `/admin/radiology-templates` or idempotent migration block.

---

### I4. CT Liver 4-phase (dedicated HCC protocol)

**Plan source:** Aberdeen — 4-phase (pre, arterial 35s, venous 70s, equilibrium 180s) with Iomeron-400.

**Current state:** ID 26 "CT Liver Triphasic" is 3-phase only. The 4-phase variant with Iomeron-400 is specifically required for HCC/post-TACE per Aberdeen.

**Approach:** Either (a) upgrade ID 26 to 4-phase, or (b) create a new row "CT Liver 4-Phase (HCC / Post-TACE)" and leave ID 26 as the generic "Liver Triphasic" for metastases. **Recommend (b)** — two distinct clinical scenarios.

**Files:** Migration block in `app.py` OR single admin POST.

---

## 🟢 Nice-to-have Gaps (3 items)

### N1. PE in Pregnancy variant

**Plan source:** https://www.ajronline.org/doi/pdf/10.2214/AJR.10.5385

**Current state:** Standard CTPA (ID 9) exists; no pregnancy-specific variant with the low-dose / shielding / bismuth guidance from the AJR paper.

**Approach:** Create new protocol "CT Pulmonary Angiography — Pregnancy" with reduced kVp, shielding, amniocentesis dose note, and a reference to NICE NG158 VTE in pregnancy. Cite AJR DOI in `special_notes`.

---

### N2. Swansea gaps — IAMS (CT), Subclavian angio, Renal Cyst Characterisation

Three protocols present in the Swansea JSON but not yet in Neon:

- **CT IAMs** (50ml hand inject if required, helical head pre + helical IAMs post)
- **CT Subclavian angio** (Omni 350 100ml @ 4ml/s, hyoid to below elbow of affected side, cannula in NON-affected side)
- **CT Renal Cyst Characterisation** (Pre renal area then PV AP)

Small, well-defined — can be batched into one migration block.

---

### N3. Split-bolus urography + pregnancy PE AJR citations

**Plan source:** https://www.ajronline.org/doi/pdf/10.2214/AJR.07.2288 (split-bolus urography)

**Current state:** ID 111 (Bladder Cancer Split-Bolus Urogram) exists but `special_notes` does not cite the AJR paper. ID 9 CTPA has no pregnancy AJR citation.

**Approach:** Append the DOI + "Chow et al., AJR 2008; 191:1293" to the `special_notes` of ID 111, and pregnancy CTPA (N1 above).

---

## Deliberately deferred / obsoleted

These plan items will **not** be implemented as originally specified:

| Plan item | Reason |
|---|---|
| KOC scanner parameter protocols folder (docx files) | Superseded by Swansea + Aberdeen corpus, which give equivalent UK-standard coverage with better legal posture (departmental SOPs vs. institutional docx). |
| MR enterography second source doc | ID 43 covers the core protocol; two source docs would duplicate without clinical gain. |
| NICE direct scraping | Addressed separately in `scripts/nice_cache.py` (local reference only) + the Hybrid Path C plan from the April 8 conversation. |

---

## Priority order for implementation

The 12 items break naturally into **3 PRs**:

### PR 1 — Critical content (C2, C3, C4, I4, N2)
Add 5–6 new imaging protocols via a single idempotent migration block in `app.py`. Low risk, high clinical value. **No new UI work.** Can ship same day as planned.

### PR 2 — Prompt + template enrichment (I2, I3, N1, N3)
1. Add `_WBCT_CRITERIA_BLOCK` to `ai_vetting.py`
2. Create 2 RCR trauma templates
3. Add pregnancy-CTPA protocol
4. Backfill source citations on split-bolus protocols

### PR 3 — RadiQ + UX wiring (C1, I1, C5)
1. RadiQ protocol retrieval helper + prompt injection
2. Pregnancy "do-not-insert-unless-confirmed" UX
3. KOC Omnipaque paediatric calculator extension (largest piece — ~200 lines HTML/JS in the contrast card Tab 6)

**Total estimated scope:** ~12 files across 3 PRs.

---

## Verification plan (per PR)

### PR 1 verification
- `SELECT COUNT(*) FROM imaging_protocol WHERE title LIKE 'CT GI Bleed%'` → 1
- Same for Brain Dementia, Anastomosis Leak, Liver 4-phase, IAMs, Subclavian, Renal Cyst
- Visit `/vetting/protocols?search=GI bleed` → row appears
- Vet a test referral "active PR bleeding" → AI matches the new GI bleed protocol

### PR 2 verification
- Ask vetting "72M RTC 50mph GCS 13 SBP 85" → AI cites specific WBCT criteria verbatim (GCS <14 ✓, SBP <90 ✓)
- Smart Reporter template picker shows "RCR Primary Survey Trauma" and "RCR Secondary Survey Trauma"
- Vet "28F 32/40 SOB chest pain D-dimer raised" → suggests pregnancy-specific CTPA variant

### PR 3 verification
- Ask RadiQ "what's the contrast protocol for pancreatic cancer?" → quotes Swansea protocol, links to `/vetting/protocols?search=pancreas`
- In vetting, leave pregnancy empty → Quick Clean omits pregnancy line
- In vetting, select "Pregnant" → rationale input appears, Continue is blocked until filled
- In Contrast Card Tab 6, enter weight 25 kg + Omnipaque 350 → correct iodine dose displayed

---

## Risks / Gotchas

1. **Neon write timing** — After the April 8 audit we know Neon currently has 124 admin protocols with mystery provenance on IDs 50-129. Adding new rows is safe (next available ID) but **do not UPDATE** any existing row without checking its current state first.
2. **PII Guard** in the admin protocol editor — new protocol text must be free of case-identifying content to avoid false positives at save time.
3. **Migration block ordering** — the source-rebrand migration (committed today) uses sentinel `<!-- src:radinsight-v1 -->`. New protocols added in PR 1 must include that sentinel from the start so the rebrand migration skips them cleanly.
4. **RadiQ prompt size** — injecting protocol context on every RadiQ call will inflate token usage. Limit retrieval to top 3 matches, gate on keyword match, and log usage to spot runaway cases.

---

## Success criteria

Plan is considered closed when:
- All 5 🔴 items merged and deployed
- Audit re-run against plan returns **0 critical gaps**
- `SELECT COUNT(*) FROM imaging_protocol WHERE origin='admin'` ≥ 130
- RadiQ answers at least one protocol-specific query with a DB-sourced reference
- `docs/COMPREHENSIVE_TODO.md` updated with the 3 PRs marked done
