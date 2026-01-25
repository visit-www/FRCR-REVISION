# AJCC Cancer Staging Manual 8th Edition - Ontology & Site Map

This document provides the complete mapping of anatomical sections and disease sites as defined in the AJCC Cancer Staging Manual 8th Edition, implemented in our application.

---

## Overview

| Metric | Count |
|--------|-------|
| **Total Sections** | 17 |
| **Total Disease Sites** | 72 |

---

## Complete Site Map

### 1. Head and Neck (10 sites)

| Disease Site | Slug | URL Path |
|--------------|------|----------|
| Lip | `lip` | head-and-neck/lip |
| Oral Cavity | `oral-cavity` | head-and-neck/oral-cavity |
| Oropharynx (HPV-Mediated) | `oropharynx-hpv` | head-and-neck/oropharynx-hpv |
| Oropharynx (Non-HPV) | `oropharynx` | head-and-neck/oropharynx |
| Nasopharynx | `nasopharynx` | head-and-neck/nasopharynx |
| Hypopharynx | `hypopharynx` | head-and-neck/hypopharynx |
| Larynx | `larynx` | head-and-neck/larynx |
| Nasal Cavity and Paranasal Sinuses | `nasal-cavity` | head-and-neck/nasal-cavity |
| Salivary Glands | `salivary-glands` | head-and-neck/salivary-glands |
| Unknown Primary of the Head and Neck | `unknown-primary-head-neck` | head-and-neck/unknown-primary |

**Clinical Notes:**
- HPV-mediated oropharyngeal carcinoma has a distinct staging system due to its better prognosis
- Unknown primary is staged when cervical lymph node metastasis is present without identifiable primary

---

### 2. Upper Gastrointestinal Tract (3 sites)

| Disease Site | Slug | URL Path |
|--------------|------|----------|
| Esophagus and Esophagogastric Junction | `esophagus` | upper-gastrointestinal-tract/esophagus |
| Stomach | `stomach` | upper-gastrointestinal-tract/stomach |
| Small Intestine | `small-intestine` | upper-gastrointestinal-tract/small-intestine |

**Clinical Notes:**
- Esophagogastric junction (Siewert) tumors are staged with esophageal system
- Small intestine includes duodenum, jejunum, and ileum (adenocarcinoma)

---

### 3. Lower Gastrointestinal Tract (4 sites)

| Disease Site | Slug | URL Path |
|--------------|------|----------|
| Appendix | `appendix` | lower-gastrointestinal-tract/appendix |
| Colon | `colon` | lower-gastrointestinal-tract/colon |
| Rectum | `rectum` | lower-gastrointestinal-tract/rectum |
| Anal Canal | `anal-canal` | lower-gastrointestinal-tract/anal-canal |

**Clinical Notes:**
- Appendix has separate staging for mucinous neoplasms vs. carcinoma
- Rectosigmoid junction tumors staged as rectal cancer

---

### 4. Hepatobiliary System (7 sites)

| Disease Site | Slug | URL Path |
|--------------|------|----------|
| Liver | `liver` | hepatobiliary-system/liver |
| Intrahepatic Bile Ducts | `intrahepatic-bile-ducts` | hepatobiliary-system/intrahepatic-bile-ducts |
| Perihilar Bile Ducts | `perihilar-bile-ducts` | hepatobiliary-system/perihilar-bile-ducts |
| Distal Bile Duct | `distal-bile-duct` | hepatobiliary-system/distal-bile-duct |
| Ampulla of Vater | `ampulla-of-vater` | hepatobiliary-system/ampulla-of-vater |
| Gallbladder | `gallbladder` | hepatobiliary-system/gallbladder |
| Pancreas | `pancreas` | hepatobiliary-system/pancreas |

**Clinical Notes:**
- Liver staging applies to hepatocellular carcinoma (HCC)
- Perihilar (Klatskin) tumors have distinct staging from intrahepatic cholangiocarcinoma
- Pancreas staging is for exocrine (ductal) adenocarcinoma

---

### 5. Neuroendocrine Tumors (6 sites)

| Disease Site | Slug | URL Path |
|--------------|------|----------|
| Neuroendocrine Tumors of the Stomach | `net-stomach` | neuroendocrine-tumors/stomach |
| Neuroendocrine Tumors of the Duodenum and Ampulla of Vater | `net-duodenum` | neuroendocrine-tumors/duodenum |
| Neuroendocrine Tumors of the Jejunum and Ileum | `net-jejunum-ileum` | neuroendocrine-tumors/jejunum-ileum |
| Neuroendocrine Tumors of the Appendix | `net-appendix` | neuroendocrine-tumors/appendix |
| Neuroendocrine Tumors of the Colon and Rectum | `net-colon-rectum` | neuroendocrine-tumors/colon-rectum |
| Neuroendocrine Tumors of the Pancreas | `net-pancreas` | neuroendocrine-tumors/pancreas |

**Clinical Notes:**
- Each site has organ-specific T staging based on tumor size and local invasion
- Well-differentiated NETs (G1-G2) and poorly differentiated NECs (G3) use same TNM
- Ki-67 index and mitotic rate determine grade

---

### 6. Thorax (3 sites)

| Disease Site | Slug | URL Path |
|--------------|------|----------|
| Lung | `lung` | thorax/lung |
| Pleural Mesothelioma | `pleural-mesothelioma` | thorax/pleural-mesothelioma |
| Thymus | `thymus` | thorax/thymus |

**Clinical Notes:**
- Lung staging includes NSCLC, SCLC, and carcinoid tumors
- Mesothelioma has unique staging reflecting pleural spread patterns
- Thymic tumors include thymoma and thymic carcinoma

---

### 7. Bone (1 site)

| Disease Site | Slug | URL Path |
|--------------|------|----------|
| Bone | `bone` | bone/bone |

**Clinical Notes:**
- Applies to primary bone sarcomas (osteosarcoma, chondrosarcoma, Ewing sarcoma)
- T staging based on size (≤8 cm vs >8 cm) and skip metastases

---

### 8. Soft Tissue Sarcoma (5 sites)

| Disease Site | Slug | URL Path |
|--------------|------|----------|
| Soft Tissue Sarcoma of the Head and Neck | `soft-tissue-head-neck` | soft-tissue-sarcoma/head-neck |
| Soft Tissue Sarcoma of the Trunk and Extremities | `soft-tissue-trunk-extremities` | soft-tissue-sarcoma/trunk-extremities |
| Soft Tissue Sarcoma of the Abdomen and Thoracic Visceral Organs | `soft-tissue-abdomen-thorax` | soft-tissue-sarcoma/abdomen-thorax |
| Soft Tissue Sarcoma of the Retroperitoneum | `soft-tissue-retroperitoneum` | soft-tissue-sarcoma/retroperitoneum |
| Gastrointestinal Stromal Tumor | `gist` | soft-tissue-sarcoma/gist |

**Clinical Notes:**
- Site-specific staging reflects different prognostic implications
- GIST has separate staging based on mitotic rate and tumor location
- Grade (FNCLCC) is integral to staging

---

### 9. Skin (3 sites)

| Disease Site | Slug | URL Path |
|--------------|------|----------|
| Melanoma of the Skin | `melanoma` | skin/melanoma |
| Merkel Cell Carcinoma | `merkel-cell` | skin/merkel-cell |
| Cutaneous Squamous Cell Carcinoma | `cutaneous-scc` | skin/cutaneous-scc |

**Clinical Notes:**
- Melanoma staging based on Breslow thickness, ulceration, mitotic rate
- Cutaneous SCC of head and neck has specific high-risk features
- Merkel cell is rare neuroendocrine carcinoma with aggressive behavior

---

### 10. Breast (1 site)

| Disease Site | Slug | URL Path |
|--------------|------|----------|
| Breast | `breast` | breast/breast |

**Clinical Notes:**
- 8th Edition introduced prognostic staging incorporating biomarkers (ER, PR, HER2, grade)
- Anatomic staging still available for resource-limited settings

---

### 11. Female Reproductive Organs (7 sites)

| Disease Site | Slug | URL Path |
|--------------|------|----------|
| Vulva | `vulva` | female-reproductive-organs/vulva |
| Vagina | `vagina` | female-reproductive-organs/vagina |
| Cervix Uteri | `cervix` | female-reproductive-organs/cervix |
| Corpus Uteri Carcinoma and Carcinosarcoma | `corpus-uteri-carcinoma` | female-reproductive-organs/corpus-uteri-carcinoma |
| Corpus Uteri Sarcoma | `corpus-uteri-sarcoma` | female-reproductive-organs/corpus-uteri-sarcoma |
| Ovary, Fallopian Tube, and Primary Peritoneal Carcinoma | `ovary-fallopian-tube` | female-reproductive-organs/ovary |
| Gestational Trophoblastic Neoplasms | `gestational-trophoblastic` | female-reproductive-organs/gestational-trophoblastic |

**Clinical Notes:**
- Cervix staging is clinical (FIGO) and does not require pathologic confirmation
- Endometrial carcinoma and sarcoma have separate staging systems
- Ovarian/tubal/peritoneal carcinomas unified under single system

---

### 12. Male Genital Organs (3 sites)

| Disease Site | Slug | URL Path |
|--------------|------|----------|
| Penis | `penis` | male-genital-organs/penis |
| Prostate | `prostate` | male-genital-organs/prostate |
| Testis | `testis` | male-genital-organs/testis |

**Clinical Notes:**
- Prostate staging incorporates PSA and Gleason grade groups
- Testis staging includes serum tumor markers (AFP, hCG, LDH)

---

### 13. Urinary Tract (4 sites)

| Disease Site | Slug | URL Path |
|--------------|------|----------|
| Kidney | `kidney` | urinary-tract/kidney |
| Renal Pelvis and Ureter | `renal-pelvis-ureter` | urinary-tract/renal-pelvis-ureter |
| Urinary Bladder | `bladder` | urinary-tract/bladder |
| Urethra | `urethra` | urinary-tract/urethra |

**Clinical Notes:**
- Kidney staging for renal cell carcinoma
- Upper tract urothelial carcinoma (renal pelvis/ureter) staged separately from bladder

---

### 14. Ophthalmic Sites (8 sites)

| Disease Site | Slug | URL Path |
|--------------|------|----------|
| Eyelid Carcinoma | `eyelid-carcinoma` | ophthalmic-sites/eyelid-carcinoma |
| Conjunctival Carcinoma | `conjunctival-carcinoma` | ophthalmic-sites/conjunctival-carcinoma |
| Conjunctival Melanoma | `conjunctival-melanoma` | ophthalmic-sites/conjunctival-melanoma |
| Uveal Melanoma | `uveal-melanoma` | ophthalmic-sites/uveal-melanoma |
| Retinoblastoma | `retinoblastoma` | ophthalmic-sites/retinoblastoma |
| Lacrimal Gland Carcinoma | `lacrimal-gland` | ophthalmic-sites/lacrimal-gland |
| Orbital Sarcoma | `orbital-sarcoma` | ophthalmic-sites/orbital-sarcoma |
| Ocular Adnexal Lymphoma | `ocular-adnexal-lymphoma` | ophthalmic-sites/ocular-adnexal-lymphoma |

**Clinical Notes:**
- Uveal melanoma (iris, ciliary body, choroid) has unique metastatic pattern (liver)
- Retinoblastoma uses International Retinoblastoma Staging System (IRSS)

---

### 15. Central Nervous System (1 site)

| Disease Site | Slug | URL Path |
|--------------|------|----------|
| Brain and Spinal Cord | `brain` | central-nervous-system/brain |

**Clinical Notes:**
- CNS tumors use WHO grading rather than traditional TNM
- Staging based on extent of resection and molecular markers
- Includes gliomas, meningiomas, and other primary CNS tumors

---

### 16. Endocrine System (4 sites)

| Disease Site | Slug | URL Path |
|--------------|------|----------|
| Thyroid - Differentiated and Anaplastic | `thyroid-differentiated` | endocrine-system/thyroid-differentiated |
| Thyroid - Medullary | `thyroid-medullary` | endocrine-system/thyroid-medullary |
| Parathyroid | `parathyroid` | endocrine-system/parathyroid |
| Adrenal Cortical Carcinoma | `adrenal-cortical` | endocrine-system/adrenal-cortical |

**Clinical Notes:**
- Differentiated thyroid (papillary, follicular) staging includes age (<55 vs ≥55)
- Medullary thyroid carcinoma has separate staging system
- Anaplastic thyroid carcinoma is always Stage IV

---

### 17. Hematologic Malignancies (2 sites)

| Disease Site | Slug | URL Path |
|--------------|------|----------|
| Hodgkin and Non-Hodgkin Lymphomas | `lymphomas` | hematologic-malignancies/lymphomas |
| Primary Cutaneous Lymphomas | `cutaneous-lymphomas` | hematologic-malignancies/cutaneous-lymphomas |

**Clinical Notes:**
- Uses Lugano classification (modified Ann Arbor) rather than TNM
- Cutaneous lymphomas (mycosis fungoides, Sézary syndrome) have specific staging

---

## Database Schema Reference

### Body Section Table (`ajcc_body_section`)

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `section_name` | String(100) | Display name (e.g., "Head and Neck") |
| `slug` | String(100) | URL-friendly identifier (e.g., "head-and-neck") |

### Disease Site Table (`ajcc_disease_site`)

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `disease_name` | String(200) | Display name |
| `slug` | String(100) | URL-friendly identifier |
| `body_section_id` | Integer | Foreign key to body section |
| `ajcc_url_path` | String(200) | Path for AJCC portal |
| `frcr_module` | Enum | Mapped FRCR exam module |
| `frcr_body_part` | Enum | Mapped body part category |
| `frcr_age_group` | Enum | Adult or Pediatric |

---

## FRCR Module Mapping

Disease sites can be mapped to FRCR 2B exam modules:

| FRCR Module | Example Disease Sites |
|-------------|----------------------|
| Cardiothoracic and Vascular | Lung, Pleural Mesothelioma, Thymus |
| Gastro-intestinal | Esophagus, Stomach, Colon, Liver, Pancreas |
| Genito-urinary, Adrenal, O&G and Breast | Kidney, Bladder, Prostate, Breast, Ovary |
| Musculoskeletal and Trauma | Bone, Soft Tissue Sarcomas |
| CNS and Head & Neck | Brain, Larynx, Oral Cavity, Thyroid |
| Paediatric | Retinoblastoma, select pediatric tumors |

---

## File Locations

- **Ontology JSON**: `ajcc_tnm/data/ajcc_frcr_full_ontology.json`
- **Seed Data**: `app.py` → `_seed_ajcc_data_if_needed()`
- **Models**: `ajcc_tnm/models/`

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-25 | 1.0 | Complete AJCC 8th Edition ontology with 72 disease sites |

---

*This document is auto-generated from the AJCC Cancer Staging Manual 8th Edition structure.*
