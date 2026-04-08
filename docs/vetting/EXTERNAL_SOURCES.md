# External Sources — Pending Ingestion

> **Purpose:** Track PDF / docx / URL sources referenced in the vetting plan that need to be parsed and ingested into the `ImagingProtocol` or `VettingAlgorithm` tables.

## Status legend

- ✅ Ingested (available in DB)
- 📄 Extracted to markdown reference (not yet in DB)
- ⏳ Pending access
- ❌ Not accessible

## 1 — Local files (OneDrive)

| Source | Scope | Path | Status |
|---|---|---|---|
| **Omnipaque dosage protocols** | CT contrast dosage tables | `/Users/zen/Library/CloudStorage/OneDrive-Personal/Workstation companions/Protocols/CT-Protocols-KOC/CT-omnipauqe-dossage-protcols.pdf` | ⏳ |
| **KOC CT protocols folder** | Full departmental CT protocol library | `/Users/zen/Library/CloudStorage/OneDrive-Personal/Workstation companions/Protocols/CT-Protocols-KOC/Proroctols` | ⏳ |
| **MRI enterography — clinical** | MR enterography protocol (consultant) | `/Users/zen/Library/CloudStorage/OneDrive-Personal/Workstation companions/Protocols/MRI enterography protocol.docx` | ⏳ |
| **MRI enterography — radiographer** | MR enterography protocol (radiographer) | `/Users/zen/Library/CloudStorage/OneDrive-Personal/Workstation companions/Protocols/MR enterography protocols_radiographers (1).docx` | ⏳ |

## 2 — URLs (web-fetchable)

| Source | Scope | URL | Status |
|---|---|---|---|
| **Radiology Assistant — CT contrast & protocols** | Phase physiology, oral/rectal contrast, abdominal pathology timing | https://radiologyassistant.nl/more/ct-protocols/ct-contrast-injection-and-protocols | 📄 Merged into `CT_PROTOCOLS_REFERENCE.md` Part B |
| **Split-bolus CT urography technique (AJR 2008)** | Split-bolus protocol for CT IVU | https://www.ajronline.org/doi/pdf/10.2214/AJR.07.2288 | ⏳ |
| **PE protocol in pregnancy (AJR 2011)** | Low-dose CTPA in pregnancy | https://www.ajronline.org/doi/pdf/10.2214/AJR.10.5385 | ⏳ |
| **RCR Major Adult Trauma Guidance 2024** | WBCT triage + trauma protocol + reporting templates | https://www.rcr.ac.uk/media/mbzdxefx/rcr-major-adult-trauma-guidance-2024.pdf | 📄 Triage extracted to `TRAUMA_WBCT_CRITERIA.md` |

## 3 — NICE / RCR guidelines (named, no full-text ingestion)

These are cited by **name + edition** in `ai_vetting.py` prompts via `GUIDELINE_LAYER_MAP.md` — no full-text ingestion required. The AI has training exposure to the documents; naming anchors its responses.

| Document | Used in |
|---|---|
| NICE NG143 (renal stones) | Protocol selection for haematuria/colic |
| NICE NG158/NG179 (PE) | CTPA pathway |
| NICE NG232 (stroke) | NCCT + CTA for stroke |
| NICE NG45 (major trauma) | Pre-WBCT triage |
| NICE CG176 (head injury) | Head CT criteria |
| RCR iRefer 8th Ed (2017) | General appropriateness |
| IR(ME)R 2017 | Justification & optimisation |
| UKHSA DRL 2022 | Dose reference levels |
| ACR Manual on Contrast Media 2025 | Contrast safety |

## Ingestion plan (future work)

Once these reference files are ready, create a batch script `scripts/import_vetting_protocols.py` that:

1. Reads structured JSON/YAML (converted from the PDF/docx files) and inserts rows into `ImagingProtocol` with `origin='admin'`.
2. Tags each imported protocol with its `source_citation` (e.g. "Swansea NHS Trust 2024", "KOC CT Protocols v2023", "Radiology Assistant CT-AP").
3. Populates `keywords`, `shorthand_text`, `detailed_protocol_html`, `body_section`, `modality`.
4. Runs in idempotent mode (skip if `title + source_citation` already present).

## Next action

Before running the batch import, user needs to confirm:
- [ ] Access to the OneDrive paths (may require sync-on-demand download)
- [ ] Which protocols to prioritise (KOC full folder vs Swansea subset)
- [ ] Any licensing constraints on NHS Trust protocols (some are internal-only)
