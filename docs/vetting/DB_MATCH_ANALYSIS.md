# DB vs New Sources — Match Analysis

> **Purpose:** Audit existing `ImagingProtocol` admin entries against the three new sources (Swansea JSON, Radiology Assistant JSON, KOC Word files) so we can merge/add without creating duplicates.
>
> **Generated:** 2026-04-08
> **DB state:** 48 admin protocols (25 CT + 23 MRI), all published.

---

## Quality assessment of existing DB entries

I sampled 4 existing protocols (CTPA, CT KUB, CT Pancreas, MRI Prostate mp). Findings:

- **Shorthand:** present and reasonable (2–3 lines)
- **Detailed HTML:** **very thin** — just Parameter/Value pairs like `Contrast: Iodinated, Rate: 4, Timing: Bolus tracking`
- **Missing everywhere:**
  - Exact contrast **volume** (ml) — only flow rate present
  - Scan **delay** in seconds
  - Coverage ranges (e.g. "diaphragm to symphysis")
  - Patient **prep** (oral water, NBM, Buscopan)
  - Reconstructions (lung recons, MPR, bone)
  - Keywords are minimal (1–2 tags)
  - `special_notes` is empty on all 4 sampled

**Conclusion:** existing entries are **usable skeletons** but need enrichment. The Swansea and Radiology Assistant sources are substantially richer — especially for contrast dynamics and patient prep.

---

## Available sources

| Source | Count | Richness | Access | Status |
|---|---|---|---|---|
| **Existing DB admin protocols** | 48 (25 CT + 23 MRI) | Low (thin shell) | Neon prod | Live |
| **Swansea JSON** (plan doc) | 40 CT studies | **High** — UK-practice prep/contrast/phases | Already extracted | Ready |
| **Radiology Assistant JSON** (plan doc) | 16 abdominal CT | **High** — physiology-grounded timing | Already extracted | Ready |
| **KOC Word files** | 8 documents, ~1 MB | **Unknown** — to be parsed | Local OneDrive | Pending parse |
| **MRI enterography docx** × 2 | 2 | **High** — consultant + radiographer | Local OneDrive | Pending parse |
| **CT Perfusion brain docx** | 1 | Unknown | Local OneDrive | Pending parse |

### KOC Word files (pending parse)
```
Approved - 1 - adult cranium_modified gspg.docx       (194 KB)
Approved - 2 - adult neck_modified gspg.docx           (98 KB)
Approved - 3 - adult thorax_modifed gspg.docx         (114 KB)
Approved - 4 - adult abdomen_modified gspg.docx       (188 KB)
Approved - 5 - adult extremities_modified gspg.docx    (57 KB)
Approved - 6 - Pediatric.docx                         (306 KB)
Oncology-ARI-Aberdeen-CT protocols combined updates Feb 2022.doc  (31 KB)
Protocol Codes.docx                                    (23 KB)
Oral contrast preperations.docx                          —
CT-omnipauqe-dossage-protcols.pdf                         —
```

---

## Curated match matrix — DB ↔ Swansea

**Match tiers:**
- 🟢 **MERGE** — true match exists; enrich existing DB row with Swansea detail
- 🟡 **REVIEW** — plausible match, needs human check before merge
- ⚪ **ADD NEW** — no DB equivalent; import as new admin protocol
- 🔴 **DB-ONLY** — exists in DB but not in Swansea (keep as-is)

### CT — DB entries mapped to Swansea

| DB ID | DB Title | Action | Swansea source | Notes |
|---|---|---|---|---|
| 1, 17 | CT Brain Routine (Plain) / CT Brain Plain | 🟢 MERGE + 🟡 **DEDUPE** | Brain | **Two DB entries are duplicates** — keep id=1, delete id=17, enrich with Swansea "Brain" |
| 6 | CT Brain Trauma | 🔴 DB-ONLY | — | Keep (Swansea has no trauma-specific brain) |
| 18 | CT Brain with Contrast | 🟢 MERGE | Brain (with contrast variant) | Swansea uses "50 ml hand inject if required" |
| 19 | CT Stroke Protocol | 🔴 DB-ONLY | — | Swansea has no dedicated stroke protocol — **keep existing** |
| 7 | CT Paranasal Sinuses | 🟢 MERGE | Sinuses | Swansea: 0.6 mm reformats, Bone+ & Soft |
| 20 | CT Temporal Bone | 🟢 MERGE | Petrous | Naming difference — same study |
| — | — | ⚪ ADD | Orbits | New |
| — | — | ⚪ ADD | Orbital cellulitis / mastoiditis | New |
| — | — | ⚪ ADD | Pituitary | New |
| — | — | ⚪ ADD | IAMs | New |
| 10 | CT Carotid Angiography | 🟢 MERGE | Carotids | Swansea: Omni 350 100 ml @ 4 ml/s |
| — | — | ⚪ ADD | Neck Oncology | New |
| — | — | ⚪ ADD | Neck Thyroid Multi Nodular Goitre | New |
| — | — | ⚪ ADD | 4D Neck (parathyroid) | New |
| — | — | ⚪ ADD | Neck infection | New |
| 2, 21 | CT Chest Routine / CT Chest Plain | 🟢 MERGE + 🟡 **DEDUPE** | — | **Two DB entries** — consolidate into one "CT Chest Plain" |
| 8, 22 | CT HRCT Chest / HRCT Chest | 🟢 MERGE + 🟡 **DEDUPE** | HR Thorax | **Two DB entries** — consolidate |
| 9 | CT Pulmonary Angiography | 🟢 MERGE | Pulmonary Angio | **Swansea adds volume (100 ml) + flow (4 ml/s)** — fills current gap |
| — | — | ⚪ ADD | Lung cancer (staging) | New |
| 23 | CT CAP (Staging) | 🟢 MERGE | Breast / Lymphoma / Melanoma (all = PV CAP) | Create generic + specialty variants |
| — | — | ⚪ ADD | Breast Cancer CT | New |
| — | — | ⚪ ADD | Lymphoma CT | New |
| — | — | ⚪ ADD | Melanoma CT | New |
| — | — | ⚪ ADD | Gynae cancer CT | New |
| 33 | CT Aortic Angiography | 🟢 MERGE | Dissection / Thoracic Angio | Swansea has two variants — consider splitting |
| — | — | ⚪ ADD | Circle of Willis | New |
| — | — | ⚪ ADD | Cerebral Venogram (CTV) | New |
| — | — | ⚪ ADD | Subclavian angio | New |
| — | — | ⚪ ADD | Abdominal / mesenteric angio | New |
| — | — | ⚪ ADD | Renal angio | New |
| — | — | ⚪ ADD | Peripheral lower-limb angio | New |
| 3 | CT Abdomen Pelvis – Triphasic (Liver) | 🟡 REVIEW | Liver HCC/Haemangioma | Likely same intent — merge with Swansea timing |
| 24 | CT Abdomen Plain | 🔴 DB-ONLY | — | Keep |
| 25 | CT Abdomen Portal Venous Phase | 🔴 DB-ONLY | — | Generic PV abdomen — keep |
| 26 | CT Liver Triphasic | 🟢 MERGE | Liver HCC/Haemangioma | Swansea adds prep |
| 27 | CT Liver Hemangioma Protocol | 🟢 MERGE | Liver HCC/Haemangioma | Likely duplicate of 26 — **REVIEW dedupe** |
| 28 | CT Pancreas Protocol | 🟢 MERGE | Pancreatic Cancer | Swansea adds 500 ml water prep + late arterial chest/liver |
| 29 | CT Pancreatitis | 🔴 DB-ONLY | — | Swansea has no pancreatitis — keep |
| — | — | ⚪ ADD | Oesophagus & Gastric | New (Swansea has detailed prep + Buscopan) |
| — | — | ⚪ ADD | Bowel & rectal cancer | New |
| — | — | ⚪ ADD | Other bowel pathology | New |
| 30 | CT KUB | 🟢 MERGE | KUB Calculus | Swansea: 1 L water 1 h, prone, low-dose + dual energy, full bladder |
| 31 | CT Urogram | 🟢 MERGE | — | Use Radiology Assistant "Kidney hematuria" protocol |
| — | — | ⚪ ADD | Renal mass | New |
| — | — | ⚪ ADD | Renal cyst characterisation | New |
| — | — | ⚪ ADD | TCC upper tract surveillance | New (split bolus 20/80) |
| — | — | ⚪ ADD | Bladder cancer | New |
| — | — | ⚪ ADD | Testicular cancer | New |
| — | — | ⚪ ADD | Prostate cancer CT | New |
| — | — | ⚪ ADD | Adrenal mass characterisation | New (Swansea has pre/60 s/15 min) |
| 32 | CT Whole Body Trauma | 🟢 MERGE | — | Use RCR Major Trauma 2024 for phases, keep DB id |

### CT — summary counts
- **MERGE** (enrich existing): **11** protocols
- **DEDUPE** (consolidate two DB rows → one): **3** pairs (Brain Plain, Chest Plain, HRCT Chest)
- **REVIEW** (plausible but ambiguous): **2** (Triphasic liver duplicates)
- **ADD NEW** from Swansea: **28** protocols
- **DB-ONLY** (keep as-is): **5** protocols (CT Brain Trauma, CT Stroke, CT Abdomen Plain, CT Abdomen PV, CT Pancreatitis)

---

## Curated match matrix — DB ↔ Radiology Assistant

The Radiology Assistant content is mostly **physiology & timing** that should **enrich** existing DB protocols rather than become standalone entries.

| Rad Assist item | Action | Target DB entry |
|---|---|---|
| Liver — Lesion characterization | 🟢 ENRICH | id=26 CT Liver Triphasic (add 35/70/600 s timings) |
| Liver — Metastases (PV only) | 🟢 ENRICH | id=25 CT Abdomen Portal Venous |
| Pancreas — Ca / Pancreatitis | 🟢 ENRICH | id=28 CT Pancreas + id=29 CT Pancreatitis |
| GI bleeding (triple phase) | ⚪ **ADD NEW** | "CT Abdomen Triple Phase (GI bleed)" |
| Acute Aneurysm / Dissection (abdominal) | 🟢 ENRICH | id=33 CT Aortic Angiography (add abdominal variant) |
| Abdomen ileus (no oral!) | ⚪ **ADD NEW** | "CT Abdomen Ileus/Obstruction" |
| Adrenals — characterisation | 🟡 Handled by Swansea "Adrenal Mass" — use Rad Assist for STOP-rule detail |
| Abdomen Trauma — Blunt | 🟢 ENRICH | id=32 CT Whole Body Trauma (add arterial+delayed 180 s) |
| Abdomen Trauma — Penetrating | 🟢 ENRICH | id=32 (note re rectal contrast) |
| Abdomen Trauma — Bladder rupture | 🟢 ENRICH | id=32 (note re repeat post-instillation) |
| Abdomen Anastomotic leak | ⚪ **ADD NEW** | "CT Abdomen Anastomotic Leak" (rectal contrast + IV) |
| Kidney — Haematuria / urothelial | 🟢 ENRICH | id=31 CT Urogram (Rad Assist has full technique) |
| Pulmonary emboli | 🟢 ENRICH | id=9 CT Pulmonary Angiography (add bolus tracking detail) |
| Lung carcinoma | Handled by Swansea "Lung cancer" — skip |
| Aorta Dissection | Handled by Swansea "Dissection" — skip |
| Brain — Dementia (coronal recons) | 🟢 ENRICH | id=18 CT Brain with Contrast OR add new "CT Brain Dementia" |

### Rad Assistant — summary counts
- **ENRICH** existing: **11** protocols
- **ADD NEW**: **3** protocols (CT GI bleed, CT Ileus, CT Anastomotic leak)

---

## Duplicates within existing DB (to consolidate)

The DB has **3 pairs of obvious duplicates** from earlier imports:

| ID(s) | Title | Action |
|---|---|---|
| 1, 17 | CT Brain Routine (Plain) / CT Brain Plain | Keep id=1 (earlier), soft-delete id=17 |
| 2, 21 | CT Chest Routine / CT Chest Plain | Keep id=2 (earlier), soft-delete id=21 |
| 8, 22 | CT HRCT Chest / HRCT Chest | Keep id=8, soft-delete id=22 |
| 26, 27 | CT Liver Triphasic / CT Liver Hemangioma Protocol | **Review** — may be intentionally separate (haemangioma needs 3-min delayed). If separate, clarify titles. |

Dedupe saves **3–4 rows**.

---

## MRI — no comparison yet

The plan doc does NOT provide MRI protocol content (only the MR enterography references pending from OneDrive). The 23 existing MRI entries should stay as-is until we parse:
- `MRI enterography protocol.docx`
- `MR enterography protocols_radiographers (1).docx`
- Any MRI content in the KOC cranium/thorax/abdomen/extremities docs

**Likely gaps to check once KOC is parsed:**
- Dedicated MRI cardiac protocol (stress/viability)
- MRI rectum (staging)
- MRI prostate biopsy planning variants
- MRI small bowel vs enterography variants
- MRI perfusion

---

## Final counts — what the import script needs to do

| Action | CT | MRI | Total |
|---|---|---|---|
| MERGE existing DB rows with richer Swansea/RA content | 11 | TBD (after KOC parse) | 11+ |
| ENRICH existing DB rows with Rad Assistant physiology | 11 | 0 | 11 |
| DEDUPE (consolidate duplicate pairs) | 3 pairs (-3 rows) | 0 | -3 rows |
| ADD NEW from Swansea | 28 | — | 28 |
| ADD NEW from Radiology Assistant | 3 | — | 3 |
| **Net DB change** | **+28** | **0 (pending KOC)** | **+28** |

After this pass the DB will have:
- **Before:** 48 admin protocols
- **After:** ~73 admin protocols (45 retained + 28 new), all with substantially richer detailed content

After KOC parse (separate step), we expect another 30–50 additions, bringing total to ~100–120.

---

## Recommended import order

1. **Step 1 — Dedupe** (3 pairs, no new content). Low risk, pure cleanup.
2. **Step 2 — Enrich 22 existing rows** (11 Swansea merges + 11 Rad Assistant). Keep all IDs stable.
3. **Step 3 — Add 31 new rows** (28 Swansea + 3 Rad Assistant). Use `origin='admin'`, `is_published=False` first, then verify in admin UI before publishing.
4. **Step 4 — Parse KOC Word files** (separate session). Produces another match matrix MRI-heavy.
5. **Step 5 — Parse MRI enterography** + CT perfusion docx.
6. **Step 6 — Parse Oral contrast & Omnipaque dosage** as a **knowledge dictionary** (not protocols — these become part of the `_EVIDENCE_BLOCK` in `ai_vetting.py`).

---

## Questions for you before we proceed

1. **Delete vs soft-delete** the 3 duplicate rows — do you want a hard delete, or mark them `is_published=False` with a note?
2. **id=26 vs id=27** (Liver Triphasic vs Liver Hemangioma) — intentional split for the delayed phase, or accidental duplicate?
3. **Publish strategy for new rows** — auto-publish after merge, or hold as unpublished for you to verify in the admin UI first?
4. **KOC parse priority** — should we parse the KOC Word files **before** doing the Swansea import, to avoid re-importing the same studies twice if KOC already has them in better UK format?
