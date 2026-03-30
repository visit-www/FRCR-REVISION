# RadInsights Content Creation Roadmap

**Keyword:** `RADINSIGHTS-CONTENT-BATCH-2026`
**Created:** February 2026
**Purpose:** Comprehensive, prioritised plan for populating RadInsights with high-yield radiology content across all content types.

### Batch Generation Scripts

| Script | Content Type | Items | Usage |
|--------|-------------|-------|-------|
| `scripts/batch_templates.py` | Radiology Templates | 65 | `PYTHONUNBUFFERED=1 python scripts/batch_templates.py batch --phase 1` |
| `scripts/batch_algorithms.py` | Reporting Algorithms | 60 | `PYTHONUNBUFFERED=1 python scripts/batch_algorithms.py batch --phase 1` |
| `scripts/batch_tools.py` | Radiology Tools | 30 | `PYTHONUNBUFFERED=1 python scripts/batch_tools.py batch --phase 1` |
| `scripts/batch_protocols.py` | Clinical Protocols | 30 | `PYTHONUNBUFFERED=1 python scripts/batch_protocols.py batch --phase 1` |

All scripts support `list` (check status), `batch` (generate all), and `generate` (single item) subcommands. Use `--phase 1|2|3` to target specific phases.

---

## Current State (Neon DB — Feb 2026)

| Content Type | Count | Details |
|---|---|---|
| Cases | 36 published | CNS/HN **17**, GI 7, MSK 5, GU/Breast 4, Cardiothoracic 3, Paeds **0** |
| TNM Calculators | 39 | Complete AJCC 8th Edition coverage |
| Reporting Algorithms | 4 admin + 4 anatomy cache | Brachial Plexus, PE, 4D CT Parathyroid, Ca Cervix MRI |
| Radiology Templates | 1 admin + 5 personal | Admin: 4D CT Parathyroid. Personal templates are user-specific |
| Radiology Tools | 1 (Adrenal incidentaloma) | Major gap |
| Clinical Protocols | 0 | Empty |

**Key gaps:** Templates (1 admin), tools (1), and protocols (0) are virtually empty. Algorithms improving (4 admin) but need ~56 more for RADS family, trauma scales, grading systems. Cases strong in CNS/HN (17, well-covered) but **Paediatrics empty (0)**, Cardiothoracic weak (3), GU/Breast (4) needs expansion. TNM calculators complete.

> **SEO Note (March 31, 2026):** All content types are now publicly accessible to search engines. Public preview pages implemented for algorithms (full content), tools (full content), protocols (gated), templates (gated text), cases (`/case-library` with preview), knowledge hub, anatomy snippets, and pearls. Dynamic sitemap includes all public content. **Content generated via batch scripts will be immediately crawlable and indexable.** This makes content creation higher-impact — every new item directly improves SEO.

---

## Content Creation Phases

### PHASE 1: Foundation (Weeks 1-4)
**Goal:** Cover the 20% of content used 80% of the time. Daily-use reporting tools.

### PHASE 2: Core Expansion (Weeks 5-10)
**Goal:** Fill major subspecialty gaps. Weekly-use content and FRCR exam essentials.

### PHASE 3: Specialist Depth (Weeks 11-16)
**Goal:** Niche classifications, rare-but-tested cases, and specialist protocols.

### PHASE 4: Ongoing (Continuous)
**Goal:** User-requested content, emerging guidelines, annual updates.

---

## PHASE 1: Foundation (Weeks 1-4)

### 1A. Reporting Templates (20 templates) — Week 1-2

These are the highest-volume studies. Every teleradiologist reports these daily.

**Priority 1 — Emergency/On-Call (10 templates):**

| # | Template | Modality | Body Section |
|---|---|---|---|
| 1 | CT Head (acute, non-contrast) | CT | Brain |
| 2 | CTPA (pulmonary angiogram) | CTA | Thorax |
| 3 | CT Abdomen/Pelvis (acute abdomen) | CT | Abdomen |
| 4 | CT Cervical Spine (trauma) | CT | Spine |
| 5 | CT Whole Body (polytrauma) | CT | Multisystem |
| 6 | CT Aorta (dissection/aneurysm) | CTA | Cardiovascular |
| 7 | CT KUB (renal colic) | CT | Abdomen |
| 8 | CT Head (stroke — CTA Circle of Willis) | CTA | Brain |
| 9 | Chest X-ray (normal adult) | XR | Thorax |
| 10 | Chest X-ray (ITU/ICU) | XR | Thorax |

**Priority 2 — High-Volume Routine (10 templates):**

| # | Template | Modality | Body Section |
|---|---|---|---|
| 11 | MRI Lumbar Spine | MRI | Spine |
| 12 | MRI Brain (routine) | MRI | Brain |
| 13 | MRI Knee | MRI | Musculoskeletal |
| 14 | CT Chest (routine with contrast) | CT | Thorax |
| 15 | Ultrasound Abdomen (general) | US | Abdomen |
| 16 | CT Abdomen (triple phase liver) | CT | Abdomen |
| 17 | MRI Cervical Spine | MRI | Spine |
| 18 | CT Chest/Abdomen/Pelvis (oncology staging) | CT | Multisystem |
| 19 | CT Chest/Abdomen/Pelvis (oncology follow-up — RECIST) | CT | Multisystem |
| 20 | Ultrasound Renal | US | Abdomen |

### 1B. Reporting Algorithms (15 algorithms) — Week 1-2

The most commonly referenced classification and grading systems.

**RADS Family (5 algorithms):**

| # | Algorithm | Category | Body Section |
|---|---|---|---|
| 1 | BI-RADS (mammography/US/MRI assessment categories) | Scoring | Breast |
| 2 | LI-RADS (CT/MRI liver observation assessment) | Scoring | Abdomen |
| 3 | PI-RADS v2.1 (prostate mpMRI) | Scoring | Pelvis |
| 4 | TI-RADS (thyroid ultrasound) | Scoring | Head and Neck |
| 5 | Lung-RADS v2022 (lung screening CT) | Scoring | Thorax |

**Emergency/Trauma (5 algorithms):**

| # | Algorithm | Category | Body Section |
|---|---|---|---|
| 6 | Fleischner Society criteria (pulmonary nodules 2017) | Emergency | Thorax |
| 7 | ASPECTS (Alberta Stroke Programme Early CT Score) | Emergency | Brain |
| 8 | AAST Organ Injury Scale — Spleen (2018) | Trauma | Abdomen |
| 9 | AAST Organ Injury Scale — Liver (2018) | Trauma | Abdomen |
| 10 | AAST Organ Injury Scale — Kidney (2018) | Trauma | Abdomen |

**Routine/Classification (5 algorithms):**

| # | Algorithm | Category | Body Section |
|---|---|---|---|
| 11 | Bosniak Classification v2019 (renal cysts) | Routine | Abdomen |
| 12 | CT Severity Index / Balthazar (pancreatitis) | Scoring | Abdomen |
| 13 | Fazekas Scale (white matter disease) | Scoring | Brain |
| 14 | Scheltens MTA Score (medial temporal atrophy) | Scoring | Brain |
| 15 | RECIST 1.1 (tumour response assessment) | Oncology | Multisystem |

### 1C. Radiology Tools / Calculators (10 tools) — Week 2-3

**Incidental Findings — ACR White Paper Series:**

| # | Tool | Body Section | Source |
|---|---|---|---|
| 1 | Thyroid nodule (incidental on CT) | Head and Neck | ACR 2015 |
| 2 | Renal mass (incidental) | Abdomen | ACR 2017 |
| 3 | Liver lesion (incidental) | Abdomen | ACR 2017 |
| 4 | Pancreatic cyst (incidental) | Abdomen | ACR 2017 |
| 5 | Ovarian/adnexal mass (incidental) | Pelvis | ACR 2019 |
| 6 | Pulmonary nodule (Fleischner calculator) | Thorax | Fleischner 2017 |
| 7 | Pulmonary nodule (BTS, UK guidelines) | Thorax | BTS 2015 |

**Scoring Calculators:**

| # | Tool | Body Section | Notes |
|---|---|---|---|
| 8 | Wells Score — PE | Thorax | Pre-test probability for CTPA |
| 9 | Wells Score — DVT | Cardiovascular | Pre-test probability for DVT |
| 10 | NASCET Calculator (carotid stenosis %) | Cardiovascular | Percentage stenosis formula |

### 1D. Clinical Protocols (10 protocols) — Week 3-4

**Contrast Protocols (must-have for every department):**

| # | Protocol | Category |
|---|---|---|
| 1 | Acute contrast reaction management (anaphylaxis) | Emergency |
| 2 | Contrast in renal impairment (eGFR guidelines) | Safety |
| 3 | Metformin and iodinated contrast | Safety |
| 4 | MRI gadolinium in renal impairment (NSF risk) | Safety |
| 5 | Contrast premedication regimen (high-risk patients) | Safety |

**Emergency Imaging Pathways:**

| # | Protocol | Category |
|---|---|---|
| 6 | Acute stroke imaging pathway (< 4.5h and extended window) | Emergency |
| 7 | Whole-body CT polytrauma protocol | Emergency |
| 8 | Spinal clearance protocol (NEXUS/Canadian rules) | Emergency |
| 9 | MRI safety screening questionnaire (zones I-IV) | Safety |
| 10 | NAI skeletal survey protocol (RCR 2018) | Emergency |

---

## PHASE 2: Core Expansion (Weeks 5-10)

### 2A. Reporting Templates (+25 templates, total ~45) — Weeks 5-6

**Cross-Sectional Subspecialty:**

| # | Template | Modality | Body Section |
|---|---|---|---|
| 21 | CT Sinuses | CT | Head and Neck |
| 22 | CT Neck with contrast (staging) | CT | Head and Neck |
| 23 | Ultrasound Thyroid | US | Head and Neck |
| 24 | Ultrasound Neck lumps | US | Head and Neck |
| 25 | MRI Brain (epilepsy protocol) | MRI | Brain |
| 26 | MRI Brain (dementia/memory clinic) | MRI | Brain |
| 27 | MRI Brain (pituitary protocol) | MRI | Brain |
| 28 | CT Thoracic/Lumbar Spine (trauma) | CT | Spine |
| 29 | MRI Whole Spine (metastatic survey) | MRI | Spine |
| 30 | CT Chest (HRCT — ILD) | CT | Thorax |
| 31 | CT Abdomen (pancreatic protocol) | CT | Abdomen |
| 32 | CT Abdomen (small bowel obstruction) | CT | Abdomen |
| 33 | MRI Liver (hepatocyte-specific / Primovist) | MRI | Abdomen |
| 34 | MRI MRCP | MRI | Abdomen |
| 35 | MRI Small Bowel (Crohn's / MR enterography) | MRI | Abdomen |
| 36 | Ultrasound Hepatobiliary | US | Abdomen |
| 37 | CT Pelvis (trauma) | CT | Pelvis |
| 38 | MRI Pelvis (rectal cancer staging) | MRI | Pelvis |
| 39 | MRI Prostate (mpMRI — PI-RADS) | MRI | Pelvis |
| 40 | Ultrasound Pelvis (gynaecological) | US | Pelvis |
| 41 | MRI Shoulder | MRI | Musculoskeletal |
| 42 | Ultrasound DVT (lower limb venous) | US | Cardiovascular |
| 43 | Ultrasound Carotid Doppler | US | Cardiovascular |
| 44 | Mammography (screening — BI-RADS) | XR | Breast |
| 45 | Mammography (diagnostic/symptomatic) | XR | Breast |

### 2B. Reporting Algorithms (+25 algorithms, total ~40) — Weeks 5-7

**RADS Completion:**

| # | Algorithm | Category | Body Section |
|---|---|---|---|
| 16 | O-RADS (ovarian US and MRI) | Scoring | Pelvis |
| 17 | CAD-RADS 2.0 (coronary CTA) | Scoring | Cardiovascular |
| 18 | C-RADS (CT colonography) | Scoring | Abdomen |

**Neuro/Brain:**

| # | Algorithm | Category | Body Section |
|---|---|---|---|
| 19 | Fisher Scale / Modified Fisher (SAH) | Emergency | Brain |
| 20 | Marshall CT Classification (TBI) | Emergency | Brain |
| 21 | GCA Scale (global cortical atrophy, Pasquier) | Scoring | Brain |
| 22 | Koedam Posterior Atrophy Score | Scoring | Brain |
| 23 | Evans Index (hydrocephalus) | Routine | Brain |
| 24 | Spetzler-Martin (AVM grading) | Grading | Brain |

**Abdominal:**

| # | Algorithm | Category | Body Section |
|---|---|---|---|
| 25 | Modified Atlanta Classification (pancreatitis) | Emergency | Abdomen |
| 26 | Couinaud Liver Segment Anatomy | Routine | Abdomen |
| 27 | SFU Hydronephrosis Grading | Routine | Abdomen |

**Trauma:**

| # | Algorithm | Category | Body Section |
|---|---|---|---|
| 28 | AAST Organ Injury Scale — Pancreas | Trauma | Abdomen |
| 29 | AAST Organ Injury Scale — Bowel/Mesentery | Trauma | Abdomen |
| 30 | AAST Organ Injury Scale — Bladder | Trauma | Pelvis |
| 31 | Young-Burgess Classification (pelvic fractures) | Trauma | Pelvis |
| 32 | TLICS (thoracolumbar injury classification) | Trauma | Spine |

**MSK/Orthopaedic:**

| # | Algorithm | Category | Body Section |
|---|---|---|---|
| 33 | Salter-Harris Classification (physeal fractures) | Grading | Musculoskeletal |
| 34 | Garden Classification (femoral neck fractures) | Grading | Musculoskeletal |
| 35 | Weber Classification (ankle fractures) | Grading | Musculoskeletal |
| 36 | Neer Classification (proximal humerus) | Grading | Musculoskeletal |
| 37 | Schatzker Classification (tibial plateau) | Grading | Musculoskeletal |
| 38 | Mason Classification (radial head) | Grading | Musculoskeletal |
| 39 | Kellgren-Lawrence (osteoarthritis grading) | Grading | Musculoskeletal |
| 40 | Modic Changes (endplate degeneration) | Grading | Spine |

### 2C. Radiology Tools (+10 tools, total ~20) — Weeks 7-8

| # | Tool | Body Section | Notes |
|---|---|---|---|
| 11 | Splenic lesion (incidental) | Abdomen | ACR White Paper |
| 12 | Gallbladder polyp management | Abdomen | European guidelines |
| 13 | Mediastinal lymph node (incidental) | Thorax | ACR 2020 |
| 14 | TI-RADS Point Calculator | Head and Neck | ACR 5-feature scoring |
| 15 | PI-RADS Zone-Based Calculator | Pelvis | DWI/T2W/DCE scoring |
| 16 | LI-RADS Feature Calculator | Abdomen | Major + ancillary features |
| 17 | Bosniak Feature Calculator | Abdomen | v2019 criteria |
| 18 | CT Severity Index Calculator (pancreatitis) | Abdomen | Balthazar + necrosis |
| 19 | RECIST 1.1 Calculator | Multisystem | Target lesion sum, % change |
| 20 | Aorta Diameter Reference Values | Cardiovascular | Age/sex-adjusted normals |

### 2D. Clinical Protocols (+10 protocols, total ~20) — Weeks 8-9

| # | Protocol | Category |
|---|---|---|
| 11 | Contrast extravasation management | Emergency |
| 12 | Breastfeeding and contrast | Safety |
| 13 | Thyroid and iodinated contrast | Safety |
| 14 | Mechanical thrombectomy imaging criteria | Emergency |
| 15 | TIA imaging pathway | Emergency |
| 16 | NAI head imaging algorithm | Emergency |
| 17 | Paediatric CT dose optimisation | Safety |
| 18 | Paediatric sedation protocol (MRI/CT) | Safety |
| 19 | UTI imaging pathway (paediatric, NICE) | Routine |
| 20 | Biopsy pre-procedure checklist (RADPASS) | Routine |

### 2E. Cases (+30 cases, total ~66) — Weeks 5-10

**Priority: Fill empty modules and FRCR high-yield gaps.**

**Paediatric (0 cases currently — critical gap, need 8):**

| # | Case | Priority |
|---|---|---|
| 1 | Intussusception (target sign on US) | Tier 1 |
| 2 | Pyloric stenosis (US measurements) | Tier 1 |
| 3 | Wilms tumour (nephroblastoma) | Tier 1 |
| 4 | Posterior fossa tumour (medulloblastoma) | Tier 1 |
| 5 | NAI (corner fractures, bucket-handle) | Tier 1 |
| 6 | Necrotising enterocolitis (NEC) | Tier 1 |
| 7 | Developmental dysplasia of hip (DDH) | Tier 2 |
| 8 | Congenital diaphragmatic hernia | Tier 2 |

**Cardiothoracic (3 cases currently — need 7 more):**

| # | Case | Priority |
|---|---|---|
| 9 | Aortic dissection (Type A) | Tier 1 |
| 10 | Interstitial lung disease (UIP pattern) | Tier 1 |
| 11 | Lung cancer staging (central mass with nodes) | Tier 1 |
| 12 | Anterior mediastinal mass (thymoma) | Tier 1 |
| 13 | Bronchiectasis (CF pattern) | Tier 2 |
| 14 | Thoracic aortic aneurysm | Tier 2 |
| 15 | Pulmonary sequestration | Tier 2 |

**GU/Breast (4 cases currently — need 5 more):**

| # | Case | Priority |
|---|---|---|
| 16 | Renal cell carcinoma | Tier 1 |
| 17 | Ovarian dermoid cyst | Tier 1 |
| 18 | Testicular tumour with retroperitoneal nodes | Tier 1 |
| 19 | Prostate cancer (PI-RADS 5 lesion) | Tier 1 |
| 20 | Ectopic pregnancy | Tier 1 |

**MSK (5 cases currently — need 5 more):**

| # | Case | Priority |
|---|---|---|
| 21 | Osteosarcoma | Tier 1 |
| 22 | Meniscal tear (MRI knee) | Tier 1 |
| 23 | Rotator cuff tear (MRI shoulder) | Tier 1 |
| 24 | Septic arthritis / osteomyelitis | Tier 1 |
| 25 | Perthes disease / SUFE (paediatric hip) | Tier 1 |

**GI (7 cases currently — need 5 more):**

| # | Case | Priority |
|---|---|---|
| 26 | Small bowel obstruction (with transition point) | Tier 1 |
| 27 | Acute necrotising pancreatitis | Tier 1 |
| 28 | HCC (LI-RADS 5 in cirrhotic liver) | Tier 1 |
| 29 | Crohn's disease (MR enterography) | Tier 1 |
| 30 | Sigmoid volvulus (coffee bean sign) | Tier 1 |

---

## PHASE 3: Specialist Depth (Weeks 11-16)

### 3A. Reporting Templates (+20 templates, total ~65)

| # | Template | Modality | Body Section |
|---|---|---|---|
| 46 | CT Temporal Bones | CT | Head and Neck |
| 47 | MRI IAMs (internal auditory meati) | MRI | Head and Neck |
| 48 | MRI Orbits | MRI | Head and Neck |
| 49 | CT Venogram (cerebral) | CTV | Brain |
| 50 | MRI Brain (tumour surveillance — RANO) | MRI | Brain |
| 51 | MRI Spine (infection/discitis) | MRI | Spine |
| 52 | LDCT Lung Screening (Lung-RADS) | CT | Thorax |
| 53 | CT Mesenteric Angiogram | CTA | Abdomen |
| 54 | MRI Pancreas (cystic lesions/IPMN) | MRI | Abdomen |
| 55 | CT Colonography | CT | Abdomen |
| 56 | MRI Pelvis (cervical cancer staging) | MRI | Pelvis |
| 57 | MRI Pelvis (anal cancer) | MRI | Pelvis |
| 58 | MRI Fistula (perianal — Parks) | MRI | Pelvis |
| 59 | MRI Hip | MRI | Musculoskeletal |
| 60 | MRI Soft Tissue Mass | MRI | Musculoskeletal |
| 61 | DEXA Scan | DXA | Musculoskeletal |
| 62 | CT Coronary Angiogram (CAD-RADS) | CTA | Cardiovascular |
| 63 | Cardiac MRI (routine) | MRI | Cardiovascular |
| 64 | MRI Breast | MRI | Breast |
| 65 | PET-CT Report (Deauville) | PET/CT | Multisystem |

### 3B. Reporting Algorithms (+20 algorithms, total ~60)

**Oncology:**

| # | Algorithm | Category | Body Section |
|---|---|---|---|
| 41 | Deauville Criteria (lymphoma PET-CT) | Oncology | Multisystem |
| 42 | iRECIST (immunotherapy response) | Oncology | Multisystem |
| 43 | mRECIST (HCC response) | Oncology | Abdomen |
| 44 | RANO Criteria (brain tumour response) | Oncology | Brain |
| 45 | Lugano Classification (lymphoma staging) | Oncology | Multisystem |

**Neuro:**

| # | Algorithm | Category | Body Section |
|---|---|---|---|
| 46 | Hunt and Hess Scale (SAH) | Grading | Brain |
| 47 | WFNS Scale (SAH) | Grading | Brain |
| 48 | Rotterdam CT Score (TBI) | Emergency | Brain |

**Vascular:**

| # | Algorithm | Category | Body Section |
|---|---|---|---|
| 49 | Stanford Classification (aortic dissection) | Emergency | Cardiovascular |
| 50 | DeBakey Classification (aortic dissection) | Emergency | Cardiovascular |
| 51 | Lake Louise Criteria (myocarditis CMR) | Routine | Cardiovascular |

**MSK (continued):**

| # | Algorithm | Category | Body Section |
|---|---|---|---|
| 52 | Rockwood Classification (ACJ injuries) | Grading | Musculoskeletal |
| 53 | Sanders Classification (calcaneal CT) | Grading | Musculoskeletal |
| 54 | Pfirrmann Grading (disc degeneration MRI) | Grading | Spine |
| 55 | Hawkins Classification (talar neck fractures) | Grading | Musculoskeletal |
| 56 | Gustilo-Anderson (open fractures) | Grading | Musculoskeletal |
| 57 | Cobb Angle Measurement (scoliosis) | Scoring | Spine |

**Breast:**

| # | Algorithm | Category | Body Section |
|---|---|---|---|
| 58 | BI-RADS Breast Density (a-d) | Scoring | Breast |

**GU:**

| # | Algorithm | Category | Body Section |
|---|---|---|---|
| 59 | Parks Classification (perianal fistula) | Routine | Pelvis |
| 60 | FIGO Staging (cervical/endometrial/ovarian) | Oncology | Pelvis |

### 3C. Radiology Tools (+10 tools, total ~30)

| # | Tool | Body Section |
|---|---|---|
| 21 | O-RADS Calculator (ovarian US) | Pelvis |
| 22 | CAD-RADS Calculator | Cardiovascular |
| 23 | Deauville Score Calculator | Multisystem |
| 24 | Child-Pugh Score Calculator | Abdomen |
| 25 | MELD Score Calculator | Abdomen |
| 26 | CT Radiation Dose Calculator (DLP to mSv) | Multisystem |
| 27 | Lymph Node Size Reference (by station) | Multisystem |
| 28 | CBD Diameter Reference | Abdomen |
| 29 | Ovarian Volume Calculator | Pelvis |
| 30 | Thyroid Volume Calculator | Head and Neck |

### 3D. Clinical Protocols (+10 protocols, total ~30)

| # | Protocol | Category |
|---|---|---|
| 21 | Anticoagulation management (pre-IR procedure) | Routine |
| 22 | Drain insertion protocol | Routine |
| 23 | Post-procedure observation | Routine |
| 24 | Nephrostomy protocol | Routine |
| 25 | MRI conditional implant checklist | Safety |
| 26 | MRI in pregnancy | Safety |
| 27 | Claustrophobia management | Routine |
| 28 | Intussusception air reduction protocol | Emergency |
| 29 | Cerebral venous thrombosis imaging pathway | Emergency |
| 30 | Contrast allergy referral pathway | Safety |

### 3E. Cases (+20 cases, total ~86)

**Tier 2 and rare-but-classic FRCR cases:**

| # | Case | Module | Priority |
|---|---|---|---|
| 31 | Paget's disease | MSK | Tier 2 |
| 32 | Chondrocalcinosis / CPPD | MSK | Tier 2 |
| 33 | Stress fracture (metatarsal) | MSK | Tier 2 |
| 34 | Avascular necrosis (femoral head) | MSK | Tier 2 |
| 35 | Sarcoidosis (bilateral hilar LAD + lung) | Cardiothoracic | Tier 2 |
| 36 | Empyema | Cardiothoracic | Tier 2 |
| 37 | Oesophageal carcinoma | GI | Tier 2 |
| 38 | Cholangiocarcinoma | GI | Tier 2 |
| 39 | Budd-Chiari syndrome | GI | Tier 2 |
| 40 | Mesenteric ischaemia | GI | Tier 2 |
| 41 | Bladder cancer staging | GU | Tier 2 |
| 42 | Endometriosis (MRI) | GU | Tier 2 |
| 43 | MS (Barkhof/McDonald criteria) | CNS/HN | Tier 2 |
| 44 | Cerebral abscess | CNS/HN | Tier 2 |
| 45 | Cholesteatoma | CNS/HN | Tier 2 |
| 46 | Spinal cord tumour (ependymoma) | CNS/HN | Tier 2 |
| 47 | Neuroblastoma | Paeds | Tier 2 |
| 48 | Tuberous sclerosis (phakomatosis) | Paeds | Tier 2 |
| 49 | NF1 (phakomatosis) | Paeds | Tier 2 |
| 50 | Lymphoma staging (Hodgkin's) | Multisystem | Tier 2 |

---

## PHASE 4: Continuous Growth

### 4A. Tier 3 — Rare-but-Classic Exam Cases (Ongoing)

These appear less frequently but are considered "classic" FRCR long cases:

- Pheochromocytoma (bilateral = MEN2)
- Kartagener syndrome (situs inversus + bronchiectasis)
- Pulmonary alveolar proteinosis (crazy paving)
- Rendu-Osler-Weber (pulmonary AVMs)
- Erdheim-Chester disease
- Langerhans cell histiocytosis
- Castleman disease
- Scimitar syndrome
- Meigs syndrome
- VHL syndrome

### 4B. Niche Algorithms (Ongoing)

| Algorithm | Category | Body Section |
|---|---|---|
| NI-RADS (head and neck post-treatment) | Scoring | Head and Neck |
| Barrow Grading (carotid-cavernous fistula) | Grading | Brain |
| Choi Criteria (GIST response) | Oncology | Abdomen |
| IPMN Management (Fukuoka/Kyoto) | Routine | Abdomen |
| AO/OTA Universal Fracture Classification | Grading | Musculoskeletal |
| Lauge-Hansen (ankle mechanism) | Grading | Musculoskeletal |
| Denis Classification (spinal fractures) | Trauma | Spine |
| Fontaine Classification (PVD) | Grading | Cardiovascular |
| Agatston Score (coronary calcium) | Scoring | Cardiovascular |

### 4C. Annual Updates

- AJCC staging updates (when 9th Edition releases)
- ACR White Paper updates (incidental findings)
- RADS system version updates (BI-RADS, PI-RADS, etc.)
- RCR guideline updates (UK-specific)
- Fleischner updates (pulmonary nodule management)

### 4D. User-Requested Content

Monitor the `ContentRequest` table for patterns. Prioritise requests that:
1. Come from multiple users
2. Align with common reporting scenarios
3. Fill gaps in existing body section coverage

---

## Content Creation Summary

### Total Content Targets by Phase

| Content Type | Current (Neon) | Phase 1 | Phase 2 | Phase 3 | Total Target |
|---|---|---|---|---|---|
| Reporting Templates | 1 admin (+5 personal) | +20 (21) | +25 (46) | +20 (66) | ~66 |
| Reporting Algorithms | 4 admin (+4 anatomy) | +15 (19) | +25 (44) | +20 (64) | ~64 |
| Radiology Tools | 1 | +10 (11) | +10 (21) | +10 (31) | ~31 |
| Clinical Protocols | 0 | +10 (10) | +10 (20) | +10 (30) | ~30 |
| Cases | 36 | — | +30 (66) | +20 (86) | ~86 |
| TNM Calculators | 39 | — | — | — | 39 (complete) |
| **TOTAL** | **81 admin** | **+55** | **+100** | **+80** | **~316** |

> **Note:** Existing admin algorithms (Brachial Plexus, PE, 4D CT Parathyroid, Ca Cervix) and the admin template (4D CT Parathyroid) are NOT duplicated in the batch lists — they are additional to the 65 + 60 planned items. Personal templates (5) are user-specific and not visible to all users.

### Content by Body Section (Target Distribution)

| Body Section | Templates | Algorithms | Tools | Protocols | Cases |
|---|---|---|---|---|---|
| Brain | 7 | 10 | 1 | 3 | 10 |
| Head and Neck | 6 | 3 | 3 | 0 | 8 |
| Spine | 5 | 4 | 0 | 1 | 5 |
| Thorax | 7 | 3 | 4 | 2 | 10 |
| Abdomen | 12 | 10 | 8 | 2 | 12 |
| Pelvis | 6 | 6 | 3 | 1 | 8 |
| Musculoskeletal | 7 | 12 | 0 | 0 | 10 |
| Cardiovascular | 5 | 5 | 3 | 0 | 5 |
| Breast | 4 | 2 | 1 | 0 | 4 |
| Multisystem | 4 | 5 | 3 | 3 | 8 |
| Cross-cutting | — | — | 4 | 18 | — |

### Generation Method

All content types can be AI-generated through existing admin interfaces:

| Content Type | Admin URL | Generator |
|---|---|---|
| Reporting Templates | `/admin/radiology-templates` | `ai_smart_reporter.py` |
| Reporting Algorithms | `/admin/reporting-algorithms` | `reporting_template_generator.py` |
| Radiology Tools | `/incidental-findings/admin` | `clinical_tool_generator.py` |
| Clinical Protocols | `/on-call-helper/admin/protocols` | `ai_oncall_helper.py` |
| Cases | `/admin` (main dashboard) | `ai_prelim.py` |

**Workflow for each item:**
1. Generate via admin AI tool (provide title, body section, source citation, guideline URL)
2. Review generated content for clinical accuracy
3. Edit if needed (HTML editor available for algorithms/tools)
4. Verify and publish

**Tip:** Use `PYTHONUNBUFFERED=1` for batch generation scripts. Provide guideline URLs in the source citation field — the generator will fetch and incorporate the content.

---

## Prioritisation Principles

1. **High-volume studies first** — CT head, CTPA, CT abdomen, CXR are reported hundreds of times daily across any teleradiology service
2. **Emergency/on-call next** — Contrast reactions, stroke pathways, and trauma protocols are safety-critical
3. **FRCR exam alignment** — Content that doubles as exam prep AND reporting support gets highest priority
4. **UK guidelines where applicable** — BTS (not just Fleischner) for pulmonary nodules, NICE for paediatric UTI, RCR for NAI
5. **Classification systems that are actually used** — Salter-Harris, Garden, Weber, Bosniak are used daily; Lauge-Hansen and AO/OTA are specialist
6. **Fill empty modules first** — Paediatrics has 0 cases; every other gap is less critical

---

## Cost Estimates

### API Pricing (Claude Sonnet 4, Feb 2026)

| Metric | Standard | Batch API (50% off) |
|---|---|---|
| Input tokens | $3.00 / million | $1.50 / million |
| Output tokens | $15.00 / million | $7.50 / million |

> 1 token ~ 4 characters ~ 0.75 words.

### Cost Per Content Item

| Content Type | Generator | Model | Input Tokens | Output Tokens | Cost (Standard) | Cost (Batch) |
|---|---|---|---|---|---|---|
| Reporting Template | `ai_smart_reporter.py` | Sonnet | ~2,500 | ~5,000 | **$0.08** | **$0.04** |
| Reporting Algorithm | `reporting_template_generator.py` | Sonnet | ~4,500 | ~15,000 | **$0.24** | **$0.12** |
| Radiology Tool (IF Calc) | `clinical_tool_generator.py` | Sonnet | ~5,000 | ~15,000 | **$0.24** | **$0.12** |
| Clinical Protocol | `ai_oncall_helper.py` | Sonnet | ~2,500 | ~3,000 | **$0.05** | **$0.03** |
| Case (Prelim + Discussion) | `ai_prelim.py` | Sonnet | ~3,500 | ~4,500 | **$0.08** | **$0.04** |
| Case (TNM Intelligence) | `ai_tnm.py` | Sonnet | ~4,500 | ~3,000 | **$0.06** | **$0.03** |

> Reporting templates are plain-text PACS reports (shorter output). Algorithms and tools are full interactive HTML (longer output, higher cost).

### Phase Cost Breakdown

#### Phase 1: Foundation (~$10.80 standard / ~$5.40 batch)

| Content | Quantity | Unit Cost | Standard Total | Batch Total |
|---|---|---|---|---|
| Reporting Templates | 20 | $0.08 | $1.60 | $0.80 |
| Reporting Algorithms | 15 | $0.24 | $3.60 | $1.80 |
| Radiology Tools | 10 | $0.24 | $2.40 | $1.20 |
| Clinical Protocols | 10 | $0.05 | $0.50 | $0.30 |
| Cases | 0 | — | $0.00 | $0.00 |
| **Phase 1 Total** | **55 items** | | **$8.10** | **$4.10** |

> Plus ~30% regeneration allowance for items needing a second attempt = **~$10.50 standard / ~$5.30 batch**

#### Phase 2: Core Expansion (~$17.30 standard / ~$8.70 batch)

| Content | Quantity | Unit Cost | Standard Total | Batch Total |
|---|---|---|---|---|
| Reporting Templates | 25 | $0.08 | $2.00 | $1.00 |
| Reporting Algorithms | 25 | $0.24 | $6.00 | $3.00 |
| Radiology Tools | 10 | $0.24 | $2.40 | $1.20 |
| Clinical Protocols | 10 | $0.05 | $0.50 | $0.30 |
| Cases (prelim) | 30 | $0.08 | $2.40 | $1.20 |
| Cases (TNM intel, ~40% oncologic) | 12 | $0.06 | $0.72 | $0.36 |
| **Phase 2 Total** | **112 items** | | **$14.02** | **$7.06** |

> With regeneration allowance: **~$18.20 standard / ~$9.20 batch**

#### Phase 3: Specialist Depth (~$14.50 standard / ~$7.30 batch)

| Content | Quantity | Unit Cost | Standard Total | Batch Total |
|---|---|---|---|---|
| Reporting Templates | 20 | $0.08 | $1.60 | $0.80 |
| Reporting Algorithms | 20 | $0.24 | $4.80 | $2.40 |
| Radiology Tools | 10 | $0.24 | $2.40 | $1.20 |
| Clinical Protocols | 10 | $0.05 | $0.50 | $0.30 |
| Cases (prelim) | 20 | $0.08 | $1.60 | $0.80 |
| Cases (TNM intel) | 8 | $0.06 | $0.48 | $0.24 |
| **Phase 3 Total** | **88 items** | | **$11.38** | **$5.74** |

> With regeneration allowance: **~$14.80 standard / ~$7.50 batch**

### Total Content Build Cost

| | Standard API | Batch API (50% off) |
|---|---|---|
| Phase 1 (55 items) | $10.50 | $5.30 |
| Phase 2 (112 items) | $18.20 | $9.20 |
| Phase 3 (88 items) | $14.80 | $7.50 |
| **All Phases (255 items)** | **$43.50** | **$22.00** |

> These are AI generation costs only. Admin review time is the real bottleneck, not cost.

---

## Batch Generation — Method and Cost Savings

### What Is Batch Generation?

Instead of generating content one item at a time through the admin web interface (click Generate, wait 30-120s, review, repeat), batch generation runs a Python script locally that generates multiple items in sequence, writing directly to the Neon production database.

### Existing Batch Infrastructure

The TNM calculator batch script (`scripts/generate_tnm_calculator.py`) already demonstrates this pattern. It generated all 39 TNM calculators in a single run:

```
PYTHONUNBUFFERED=1 python scripts/generate_tnm_calculator.py batch
```

**How it works:**
1. Script defines a `BATCH_LIST` — an array of items to generate (title, body section, source citation)
2. Loops through the list sequentially
3. For each item: calls the AI generator function → validates output → writes to Neon DB
4. 2-second pause between API calls (rate limit courtesy)
5. Skips items that already exist (`skip_existing=True`)
6. Logs success/failure with timing per item
7. If one item fails, continues to the next (no batch abort)

**Timing:** Each item takes 30-120 seconds depending on output complexity:
- Clinical protocols: ~30s (shorter output, 3,000 tokens)
- Reporting templates: ~45s (moderate output, 5,000 tokens)
- Reporting algorithms: ~90s (long HTML output, 15,000 tokens)
- Radiology tools: ~90s (long HTML output, 15,000 tokens)

### New Batch Scripts Needed

To batch-generate the content in this roadmap, we need 4 new scripts modelled on the TNM batch script:

| Script | Content Type | Generator Function | Items |
|---|---|---|---|
| `scripts/batch_templates.py` | Radiology Templates | `generate_radiology_template()` | 65 |
| `scripts/batch_algorithms.py` | Reporting Algorithms | `generate_reporting_template_html()` | 60 |
| `scripts/batch_tools.py` | Radiology Tools (IF Calcs) | `generate_clinical_tool()` | 30 |
| `scripts/batch_protocols.py` | Clinical Protocols | `generate_protocol_content()` | 30 |

Cases require images and clinical context, so they cannot be fully batch-generated — the AI generates the discussion/Q&A, but the admin must provide diagnosis, modality, module, and images. Cases are best created one at a time through the admin interface.

### Does Batch Reduce Cost?

**Short answer: Yes, potentially 50% savings via Anthropic's Batch API.**

#### Method 1: Sequential Script (Current TNM Approach)
- Calls the standard Messages API (`/v1/messages`) in a loop
- Each call is a standard API request at full price
- **Cost: Standard pricing ($3/$15 per MTok)**
- **Advantage:** Results available immediately, can review as you go
- **Timing:** ~2 hours for 60 algorithms (90s each + 2s pause)

#### Method 2: Anthropic Batch API
- Submits all requests as a single batch via `/v1/messages/batches`
- Anthropic processes them asynchronously (results within 24 hours)
- **Cost: 50% off ($1.50/$7.50 per MTok)**
- **Advantage:** Half the cost
- **Disadvantage:** Results not immediate — wait up to 24 hours, then bulk review
- **Best for:** Large content runs where you don't need results instantly

#### Method 3: Admin Web Interface (One at a Time)
- Click Generate in the admin page, wait, review, verify, repeat
- Same standard API pricing as Method 1
- **Cost: Standard pricing**
- **Advantage:** Review each item as it's generated
- **Disadvantage:** Slowest method, requires active admin attention for every item
- **Timing:** ~3-5 minutes per item (including review) = 5+ hours for 60 algorithms

### Cost Comparison for Full Roadmap (255 items)

| Method | API Cost | Time Investment | Admin Effort |
|---|---|---|---|
| Web interface (one at a time) | $43.50 | ~20 hours of clicking | High — constant attention |
| Sequential batch script | $43.50 | ~6 hours runtime, review after | Medium — review in bulk |
| Anthropic Batch API | **$22.00** | ~24h wait, then review | Medium — review in bulk |
| **Hybrid (Batch API + script)** | **$22.00** | ~24h wait, then review | **Recommended** |

### Recommended Approach: Hybrid Batch

1. **Write batch scripts** with BATCH_LIST arrays for each content type (one-time effort)
2. **Submit via Anthropic Batch API** for 50% cost savings
3. **Poll for results** — script checks batch status, downloads completed items
4. **Write to Neon DB** — script inserts/updates completed items
5. **Admin reviews in bulk** — use existing admin pages to verify and publish

**Phase 1 example workflow:**
```
# 1. Submit batch (all 55 items)
PYTHONUNBUFFERED=1 python scripts/batch_all.py submit --phase 1

# 2. Wait for completion (check periodically)
python scripts/batch_all.py status

# 3. Download results and write to DB
python scripts/batch_all.py sync

# 4. Review and verify in admin UI
# → /admin/radiology-templates (20 templates)
# → /admin/reporting-algorithms (15 algorithms)
# → /incidental-findings/admin (10 tools)
# → /on-call-helper/admin/protocols (10 protocols)
```

### Batch API Integration

The Anthropic Batch API uses a different endpoint:

```python
# Submit batch
POST https://api.anthropic.com/v1/messages/batches
{
  "requests": [
    {
      "custom_id": "template-ct-head-acute",
      "params": {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 8000,
        "system": "...",
        "messages": [{"role": "user", "content": "..."}]
      }
    },
    # ... more items
  ]
}

# Poll status
GET https://api.anthropic.com/v1/messages/batches/{batch_id}

# Download results when complete
GET https://api.anthropic.com/v1/messages/batches/{batch_id}/results
```

**Key constraints:**
- Max 10,000 requests per batch
- Results available within 24 hours (often faster)
- Same quality as standard API — no quality tradeoff
- Uses existing API key — no additional setup

### Summary: Why Batch Generation Matters

| Benefit | Impact |
|---|---|
| **50% cost savings** | $43.50 → $22.00 for full roadmap |
| **Consistent quality** | Same BATCH_LIST ensures every item gets the same prompt structure |
| **Repeatable** | Re-run for guideline updates, new editions |
| **Skips existing** | Idempotent — safe to re-run without duplicates |
| **Decoupled from admin UI** | No Vercel timeout limits (local script, not serverless) |
| **Bulk review** | Admin reviews 20 templates in one sitting instead of one every 5 minutes |

> **Bottom line:** The entire content roadmap (255 items across 4 content types) costs ~$22 with batch generation. Admin review time is the real constraint, not API cost.
