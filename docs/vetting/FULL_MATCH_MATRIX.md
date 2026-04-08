# Full Match Matrix — DB ↔ KOC ↔ Swansea ↔ Aberdeen

> **Purpose:** Final consolidated plan showing what every DB row becomes after the merge, and which new rows we import.
>
> **Generated:** 2026-04-08 (after dedupe)
> **Input DB:** 44 admin protocols (21 CT + 23 MRI)
> **Sources:**
> - **KOC**: 67 protocols (9 cranium + 7 thorax + 17 abdomen + 5 neck + 4 extremities + 25 paediatric)
> - **Swansea**: 40 CT protocols (`CT_PROTOCOLS_REFERENCE.md` Part A)
> - **Radiology Assistant**: 16 abdominal CT (`CT_PROTOCOLS_REFERENCE.md` Part B)
> - **Aberdeen**: 27 CT oncology protocols (`ABERDEEN_ONCOLOGY_CT.md`)
>
> **Merge strategy (confirmed by user):**
> 1. **KOC** = technical scanner layer (kVp/mAs/pitch/FOV/kernel/reconstructions) — **wins for scan parameters**
> 2. **Swansea** = UK clinical layer (contrast volume in ml, flow ml/s, oral prep volume, phase delays in seconds) — **wins for UK clinical values**
> 3. **Aberdeen** = clinical indication layer (which study + coverage + oral prep type) — **wins for oncology staging body coverage**
> 4. **Radiology Assistant** = physiology layer — populates knowledge dictionary, enriches timing explanations
> 5. **DB existing** = IDs are preserved; content is replaced where enrichment is available

---

## Legend

| Icon | Meaning |
|---|---|
| 🟢 **ENRICH** | Keep DB id; replace thin content with merged multi-source content |
| 🔵 **MERGE+DEDUPE** | (None remaining — dedupe already done in `dedupe_backup_20260408.json`) |
| ⚪ **ADD NEW** | Import as new row, `origin='admin'`, auto-publish |
| 🟣 **ADD PAED** | Import new paediatric row (UI color-code required) |
| 🔴 **KEEP** | Leave untouched — no richer source available |

---

## Section 1 — CT Existing rows (21) → enrichment plan

| DB id | Current title | Action | Primary source | Secondary source | Notes |
|---|---|---|---|---|---|
| 1 | CT Brain Routine (Plain) | 🟢 ENRICH | KOC code 0 | Swansea Brain | Aberdeen: "Brain tumour primary → pre-contrast CT head" |
| 6 | CT Brain Trauma | 🟢 ENRICH | KOC code 2 (Brain FAST/Trauma) | — | Aberdeen: "Post brain tumour resection → pre+post" |
| 18 | CT Brain with Contrast | 🟢 ENRICH | KOC code 1 (Brain+Contrast) | Swansea Brain +C | Contrast 50 ml hand inject; Aberdeen: post-contrast if brain tumour metastases |
| 19 | CT Stroke Protocol (NCCT+CTA±CTP) | 🟢 ENRICH | KOC code 4 (Brain CTA COW) | NICE NG232 | KOC adds scan params; NICE names pathway |
| 7 | CT Paranasal Sinuses | 🟢 ENRICH | KOC code 6 (Sinuses) | Swansea Sinuses | 0.6 mm reformats, Bone+ and Soft kernels |
| 20 | CT Temporal Bone | 🟢 ENRICH | KOC code 8 (IAM) | Swansea Petrous | |
| 2 | CT Chest Routine | 🟢 ENRICH | KOC code 96 (Chest Routine plain) | — | |
| 8 | CT HRCT Chest | 🟢 ENRICH | KOC code 98 (HRCT) | Swansea HR Thorax | 1 mm slice, high resolution lung kernel |
| 9 | CT Pulmonary Angiography | 🟢 ENRICH | KOC code 103 (Pulmonary Angio) | Swansea Pulmonary Angio | Swansea adds 100 ml @ 4 ml/s |
| 10 | CT Carotid Angiography | 🟢 ENRICH | KOC code 51 (Carotid CTA) | Swansea Carotids | Omni 350 100 ml @ 4 ml/s; SureSubtraction technique |
| 33 | CT Aortic Angiography | 🟢 ENRICH | KOC code 102 (Chest CTA / Thoracic Aorta) + 158 (Abdominal Aorta CTA) | Swansea Dissection | Consider splitting into thoracic / abdominal variants |
| 23 | CT CAP (Staging) | 🟢 ENRICH | KOC code 100 (Chest/Abdomen/Pelvis Staging 2-phase) | Swansea Breast/Lymphoma/Melanoma | Aberdeen: generic template for multiple oncology staging |
| 3 | CT Abdomen Pelvis – Triphasic (Liver) | 🟢 ENRICH | KOC code 150 (Liver) | Aberdeen Liver HCC 4-phase | Upgrade to 4-phase with Iomeron-400 rationale |
| 24 | CT Abdomen Plain | 🔴 KEEP | (KOC code 144 matches) | — | Enrich params only |
| 25 | CT Abdomen Portal Venous Phase | 🟢 ENRICH | KOC code 145 (Abdomen Routine -C/+C) | Rad Assistant PV timing | 60-70 s venous |
| 26 | CT Liver Triphasic | 🟢 ENRICH | KOC code 150 (Liver) | Aberdeen HCC 4-phase (35/70/180) + Iomeron-400 | |
| 28 | CT Pancreas Protocol | 🟢 ENRICH | KOC code 152 (Pancreas) | Aberdeen Pancreas (40s arterial + water + chest) + Swansea water 500 ml | |
| 29 | CT Pancreatitis | 🔴 KEEP | (KOC code 152 also covers Acute Pancreatitis) | — | Aberdeen does not split |
| 30 | CT KUB | 🟢 ENRICH | KOC code 148 (KUB Prone) | Swansea KUB (1 L water 1 h, prone, low dose) | |
| 31 | CT Urogram | 🟢 ENRICH | KOC code 149 (CT Urography IVU) | Rad Assistant Kidney haematuria | Split-bolus 20/80 technique |
| 32 | CT Whole Body Trauma | 🟢 ENRICH | KOC code 154 (Abdominal Trauma) + 100 (WBCT scaffold) | RCR Major Trauma 2024 + `TRAUMA_WBCT_CRITERIA.md` | Arterial + delayed 180 s |

**CT existing count:** 21 rows → 19 ENRICH + 2 KEEP

---

## Section 2 — New CT rows from KOC

These KOC protocols have **no DB equivalent** — add as new:

| KOC code | Title | Body section | Paediatric | Source priority |
|---|---|---|---|---|
| 3 | Brain + Sinuses | Brain | — | KOC only |
| 4 | Brain CTA (Circle of Willis) | Brain | — | KOC + Swansea COW |
| 5 | Brain CTA + Brain | Brain | — | KOC only |
| 9 | Orbits | Head/Neck | — | KOC + Swansea Orbits |
| 10 | Facial Bones | Head/Neck | — | KOC only |
| 11 | Brain CTV (Venogram) | Brain | — | KOC + Swansea Cerebral Venogram |
| 49 | Cervical Spine | Spine | — | KOC only |
| 52 | Neck/Chest/Abdomen/Pelvis Non-Staging | Multisystem | — | KOC |
| 53 | Neck/Chest/Abdomen/Pelvis Staging 2-phase | Multisystem | — | KOC + Aberdeen Lymphoma (neck included) |
| 99 | Chest/Abdomen/Pelvis Non-Staging -C/+C | Multisystem | — | KOC |
| 104 | Thoracic Spine | Spine | — | KOC only |
| 146 | Abdomen & Pelvis Non-Staging 2-phase | Abdomen | — | KOC |
| 147 | Abdomen & Pelvis Staging 3-phase | Abdomen | — | KOC + Aberdeen CAP staging |
| 155 | Abdomen Ileus / SBO | Abdomen | — | KOC + Rad Assistant (no oral!) |
| 156 | Renal Injury + CT Cystogram | Abdomen | — | KOC + Rad Assistant Bladder rupture |
| 157 | Mesenteric CTA | Abdomen | — | KOC + Swansea Mesenteric |
| 158 | Abdominal Aorta CTA | Abdomen | — | KOC + Swansea Abdominal angio |
| 159 | Renal CTA | Abdomen | — | KOC + Swansea Renal angio |
| 192 | Lumbar Spine (CT) | Spine | — | KOC only |
| 194 | Sacrum / Coccyx | Spine | — | KOC only |
| 195 | Bony Pelvis | Pelvis | — | KOC only |
| 240 | Lower Extremities (Joints/Bone) | MSK | — | KOC only |
| 242 | Lower Extremities CTA (Peripheral Angio) | MSK | — | KOC + Swansea Peripheral lower limb |
| 288 | Upper Extremities (Joints/Bone) | MSK | — | KOC only |
| 290 | Upper Extremities CTA | MSK | — | KOC + Swansea Subclavian angio |

**New CT from KOC:** 25 protocols

---

## Section 3 — New Paediatric CT rows from KOC 🟣

**All paediatric rows require UI color coding** (frontend task — add `is_paediatric` flag to `ImagingProtocol` model).

| KOC code | Title | Age/weight band | Body section |
|---|---|---|---|
| 432 | Brain baby (0-2 years) volume | 0-2 y | Brain |
| 433 | Brain baby (3-5 years) volume | 3-5 y | Brain |
| 434 | Brain baby (6-12 years) volume | 6-12 y | Brain |
| 435 | Pediatric sinuses volume | — | Head/Neck |
| 436 | IAM Child volume | — | Head/Neck |
| 480 | Neck Child < 15 kg | < 15 kg | Head/Neck |
| 481 | Neck Child 16-30 kg | 16-30 kg | Head/Neck |
| 482 | Neck Child 31-45 kg | 31-45 kg | Head/Neck |
| 483 | Neck Child 46-60 kg | 46-60 kg | Head/Neck |
| 484 | Neck Child 61+ kg | 61+ kg | Head/Neck |
| 528 | Chest baby < 15 kg | < 15 kg | Chest |
| 529 | Chest Child 16-30 kg | 16-30 kg | Chest |
| 530 | Chest Child 31-45 kg | 31-45 kg | Chest |
| 531 | Chest Child 46-60 kg | 46-60 kg | Chest |
| 532 | Chest Child 60+ kg | 60+ kg | Chest |
| 576 | Abdomen Baby < 15 kg | < 15 kg | Abdomen |
| 577 | Abdomen Child 16-30 kg | 16-30 kg | Abdomen |
| 578 | Abdomen Child 31-45 kg | 31-45 kg | Abdomen |
| 579 | Abdomen Child 46-60 kg | 46-60 kg | Abdomen |
| 580 | Abdomen Child 61+ kg | 61+ kg | Abdomen |
| 672 | Extremity < 15 kg | < 15 kg | MSK |
| 673 | Extremity 15-35 kg | 15-35 kg | MSK |
| 674 | Extremity 35-45 kg | 35-45 kg | MSK |
| 675 | Extremity 46-60 kg | 46-60 kg | MSK |
| 676 | Extremity 60+ kg | 60+ kg | MSK |

**New Paediatric CT:** 25 protocols

---

## Section 4 — New CT rows from Aberdeen Oncology

These are **clinical indication protocols** (body coverage + contrast rules). They reference the underlying KOC technical protocol where appropriate:

| # | Indication | KOC base | Notes |
|---|---|---|---|
| 1 | HN SCC dual phase | KOC 48 Soft Tissue Neck | Dual phase arterial + venous + chest |
| 2 | Lung Cancer staging | KOC 99 (CAP) | High chest + abdomen (no pelvis unless bone Sx) |
| 3 | Mesothelioma | KOC 99 | Same as lung Ca staging |
| 4 | Breast Cancer staging | KOC 100 (CAP staging) | High chest + abdomen + pelvis |
| 5 | Oesophageal Cancer | KOC 100 | Chest + abdomen + **water** oral |
| 6 | Gastric Cancer | KOC 100 | Chest + CAP + **water** oral |
| 7 | Hepatic Mets (standard) | KOC 147 (Abdomen staging 3-phase) | CAP + IV, arterial if hypervascular primary |
| 8 | Pancreas Follow-up | KOC 152 | Venous only (or arterial + venous if operable) |
| 9 | Colorectal Cancer | KOC 100 | CAP + IV |
| 10 | Anal Canal Cancer | KOC 100 | CAP + **groins** + IV |
| 11 | Renal Malignancy | KOC 150 (Liver triphasic) adapted | Triple-phase renal + chest |
| 12 | Upper Urothelial (haematuria) | KOC 149 | Painful → KUB + CT urogram; painless → CT urogram |
| 13 | Bladder Cancer | KOC 149 | **Split-dose IV urogram** + water |
| 14 | Prostate Cancer | KOC 147 | Abdomen + pelvis + IV + water |
| 15 | Testicular Cancer | KOC 100 | CAP + IV |
| 16 | Adrenal Washout | KOC 151 (3-phase adrenal) | Pre → if ≥10 HU → 1 min + 15 min |
| 17 | Adrenocortical Cancer | KOC 151 | Pre + 65 s chest |
| 18 | Ovarian Cancer | KOC 100 | CAP + IV |
| 19 | Cervical Cancer (MRI fallback) | KOC 147 | Abdomen + pelvis + IV |
| 20 | Endometrial Cancer (G3) | KOC 100 | CAP + IV |
| 21 | Vulval/Vaginal Cancer | KOC 147 | Abdomen + pelvis + IV |
| 22 | Sarcoma Staging | KOC 100 | CAP + IV |
| 23 | Lymphoma Staging | KOC 53 (Neck + CAP) | **Includes neck** — important distinction |
| 24 | Melanoma Staging | KOC 99 | Chest + abdomen; head/neck/pelvis optional |
| 25 | CUP (Carcinoma Unknown Primary) | KOC 100 | CAP + IV |

**New CT from Aberdeen:** 25 protocols (Aberdeen's other 2 — HCC 4-phase and Pancreas primary — enrich existing IDs 26 and 28)

---

## Section 5 — New CT rows from Swansea (not covered by KOC/Aberdeen)

| Swansea protocol | Justification for new row |
|---|---|
| Pituitary | Not in KOC detail docs |
| IAMs (as standalone) | Handled by KOC paediatric IAM but no adult row |
| Neck Oncology (non-cancer workup) | Different from HN SCC staging |
| Neck Thyroid MNG | Thyroid-specific |
| 4D Neck (parathyroid) | Parathyroid-specific |
| Neck infection | Emergency presentation |

**New CT from Swansea (extras):** 6 protocols

---

## Section 6 — MRI (unchanged)

All 23 MRI DB rows stay as-is for now. **No new MRI sources parsed yet**. Pending:
- MR enterography docx × 2 (clinical + radiographer)
- CT Perfusion brain docx
- Any MRI content in KOC docs (none found in adult — may exist in paediatric which we parsed)

---

## Final counts

| Segment | Count |
|---|---|
| **Existing CT rows kept & enriched** | 21 |
| **New CT from KOC** | 25 |
| **New Paediatric CT from KOC** 🟣 | 25 |
| **New CT from Aberdeen Oncology** | 25 |
| **New CT from Swansea extras** | 6 |
| **Existing MRI rows (unchanged)** | 23 |
| **TOTAL after merge** | **125** |

**Delta from current DB:** 44 → **125** (+81 net new rows, all CT)

---

## Conflict resolution rules (consolidated)

When multiple sources disagree on a field, the hierarchy is:

| Field | Winner | Why |
|---|---|---|
| **Scanner parameters** (kVp, mAs, pitch, FOV, kernel, reconstructions) | **KOC** | Most complete technical detail |
| **Contrast volume (ml), flow rate (ml/s), brand** | **Swansea** > Aberdeen > KOC | UK NHS values |
| **Phase timing (seconds)** | **Radiology Assistant** > Aberdeen > Swansea | Physiology-grounded |
| **Oral prep type & volume** | **Aberdeen** > Swansea | Aberdeen most explicit |
| **Body coverage for oncology** | **Aberdeen** | Staging-specific |
| **Emergency triage criteria** | **RCR guidelines** (WBCT 2024, NICE head injury) | Authoritative |
| **Paediatric weight banding** | **KOC paediatric** (exclusive source) | Only source with bands |

---

## Paediatric UI requirement

User instruction: *"In UI front end give these protocol card a color code"*

Required changes to support paediatric protocols in UI:

1. **DB:** add `is_paediatric BOOLEAN DEFAULT FALSE` column to `imaging_protocol` (needs migration).
2. **Model:** add field in `models.py` `ImagingProtocol`.
3. **Admin form:** add tickbox "Paediatric protocol".
4. **Card template:** conditional class `.protocol-card-paed` applying:
   - border-left: 4px solid `--brand-success` (#a8d5ba) or a new colour
   - small pill badge "Paediatric"
   - weight band tag shown prominently
5. **Filter:** add Adult / Paediatric filter tab on `/radiology-protocols` browse page.
6. **Vetting AI prompt:** add note "use paediatric protocol if patient < 16 y" — reference weight-banded protocols.

---

## Status — NOT YET EXECUTED

> **Update (2026-04-08):** The merge plan below has been fully designed but **has NOT yet been applied** to Neon production. Earlier drafts of this file claimed "Upsert completed successfully" — that was aspirational and is now corrected.
>
> **Current DB state:** 44 admin protocols (21 CT + 23 MRI) — unchanged from baseline.
>
> **Target state after import:** 125 rows (44 original, of which 19 enriched, + 81 new — 25 adult CT from KOC, 25 paediatric CT from KOC, 25 Aberdeen oncology, 6 Swansea extras).

### Pending work

1. **Schema migration** — commit `is_paediatric` column in `models.py` and the `_add_col_if_missing` entry in `app.py`. Deploy to Vercel so Neon gets the new column.
2. **Build merge-import script** — `scripts/import_vetting_merge.py`:
   - Parses the structured protocol data from this folder (CT_PROTOCOLS_REFERENCE.md, ABERDEEN_ONCOLOGY_CT.md, the KOC extracts)
   - Applies the conflict-resolution hierarchy (KOC scanner params → Swansea UK clinical → Aberdeen oncology coverage → Radiology Assistant physiology)
   - ENRICH existing DB ids (21 CT rows)
   - INSERT new rows (25 KOC adult + 25 KOC paediatric + 25 Aberdeen + 6 Swansea extras)
   - Idempotent + dry-run mode
3. **Execute the import** against Neon, verify counts (44 → 125).
4. **Frontend display** — admin filter + paediatric badge already coded in `vetting_routes.py` + `vetting_admin.html` (paired with the pending schema migration).

### Unrelated but related work also completed in earlier sessions

- **AI vetting prompt upgrades** — added `_REFERENCE_LAYER_BLOCK` to both analysis & protocol system prompts (NICE NG143/NG12/NG158/NG179/NG232/NG45/CG176/NG41/NG127, RCR iRefer 8th Ed, RCR Major Adult Trauma Guidance 2024, IR(ME)R 2017 + UKHSA DRL 2022, ACR Manual 2025). Temperature lowered 0.2 → 0.1 on both calls. New `guideline_citation` JSON output field on both routes. Frontend displays citation in Scene 2.
- **AI paediatric detection** — `_search_protocols()` accepts `is_paediatric` kwarg (pending migration); analyse endpoint passes `True` when AI is confident the patient is paediatric.
- **ACR Contrast Block 2025** — added to `ai_vetting.py` as `_ACR_CONTRAST_BLOCK` and appended to both system prompts (see `ACR_CONTRAST_BLOCK_2025.md` in this folder).

### Still not scoped in this plan

1. **MRI corpus** — parse MR enterography + CT perfusion brain docx from OneDrive
2. **Knowledge dictionary** — ingest Omnipaque dosage PDF + Oral contrast prep docx into `_EVIDENCE_BLOCK`
