# FRCR Open-Web AI Reference (v1)

Purpose: Map existing FRCR modules to open-web sources for staging,
classifications, gradings, and calculators. This document is intended to
support both FRCR-Revision and future WSCompanion AI features.

Scope: Open-web sources only. No restricted or paywalled ingestion.

## Approved Open-Web Sources

- Radiology Assistant: https://radiologyassistant.nl
- Radiopaedia: https://radiopaedia.org
- NICE: https://www.nice.org.uk
- CanStaging (TNM): https://www.canstaging.org
- MDCalc: https://www.mdcalc.com

## Guiding Principles (Open-Web Only)

- Link-based referencing by default; no paywalled ingestion.
- No hallucinations: disease-specific claims should be grounded in retrieved
  open-web sources. If evidence is not retrieved, output must be limited to
  general reporting safety principles.
- Store source URLs in metadata even if citations are not shown to end users.

## Open-Web Mapping by Source (Link-Based)

Focus: Common exam-encountered cancer staging, classifications, gradings, and
calculators. Use these sources as link-based references for RAG grounding.

### CanStaging (TNM)

Common TNM staging references (high-yield FRCR 2B):

- Lung cancer TNM
- Breast cancer TNM
- Colorectal cancer TNM
- Head and neck cancer TNM
- Prostate cancer TNM
- Renal cancer TNM
- Bladder cancer TNM
- Cervical cancer TNM
- Endometrial cancer TNM

### Radiopaedia

Classifications and grading systems (imaging-centric summaries):

- LI-RADS
- BI-RADS
- PI-RADS
- VI-RADS (bladder)
- O-RADS (ovarian)
- Bosniak classification (renal cysts)
- ASPECTS (stroke)
- Modified Fisher grade (SAH)
- AO Spine
- TLICS
- Common fracture classifications (Garden, Pauwels, Schatzker)
- CT grading of acute pancreatitis (Atlanta-based summaries)
- Lung nodule guidelines (Fleischner / BTS summaries)

### NICE

Imaging-relevant referral and management guidance:

- Suspected cancer referral criteria (NG12)
- Head injury imaging indications
- Stroke and TIA pathways
- Suspected PE / DVT pathways
- Sepsis and acute abdomen imaging triage (as applicable)

### MDCalc

High-yield calculators that influence imaging urgency:

- Wells score (PE/DVT)
- PERC rule
- CURB-65 (pneumonia severity)
- BISAP (acute pancreatitis severity)
- GCS (neuro trauma context)
- CHA2DS2-VASc (stroke risk context)

## FRCR Module Mapping

### Cardiothoracic and Vascular

Focus: Common cancer staging, imaging classifications, and calculators.

- Cancer staging (TNM)
  - Lung cancer TNM (CanStaging)
- Classifications and gradings (Radiopaedia / Radiology Assistant)
  - Solitary pulmonary nodule guidelines (Fleischner/BTS summaries)
  - Aortic syndromes (acute aortic syndrome overview)
  - Pulmonary embolism imaging features (RV strain, clot burden patterns)
- Calculators (MDCalc)
  - Wells score (PE/DVT)
  - PERC rule
  - CURB-65 (pneumonia severity)

### Musculoskeletal and Trauma

- Cancer staging (TNM)
  - Bone and soft tissue sarcoma staging (CanStaging)
- Classifications and gradings (Radiopaedia / Radiology Assistant)
  - AO Spine
  - TLICS
  - Fracture classifications (e.g., Garden, Pauwels, Schatzker)
- Calculators (MDCalc)
  - None mandatory; optional trauma scores if clinically needed

### Gastro-intestinal (incl. liver, biliary, pancreas, spleen)

- Cancer staging (TNM)
  - Colorectal, pancreatic, liver, gastric TNM (CanStaging)
- Classifications and gradings (Radiopaedia / Radiology Assistant)
  - LI-RADS
  - CT grading of acute pancreatitis (Atlanta-based summaries)
- Calculators (MDCalc)
  - BISAP (acute pancreatitis severity)

### Genito-urinary, Adrenal, O&G and Breast

- Cancer staging (TNM)
  - Breast, renal, prostate, bladder, cervical, endometrial TNM (CanStaging)
- Classifications and gradings (Radiopaedia / Radiology Assistant)
  - BI-RADS
  - PI-RADS
  - VI-RADS
  - O-RADS (ovarian)
  - Bosniak classification (renal cysts)
- Calculators (MDCalc)
  - None mandatory; add if clinically required (e.g., stone risk tools)

### Paediatric

- Cancer staging (TNM)
  - Use CanStaging where applicable to pediatric tumors (confirm indication)
- Classifications and gradings (Radiopaedia / Radiology Assistant)
  - Pediatric imaging topic summaries where available
- Calculators (MDCalc)
  - None mandatory; use only if clinically relevant and open-web

### CNS and Head & Neck (incl. spine, eyes, ENT, salivary, dental)

- Cancer staging (TNM)
  - Head & neck TNM (CanStaging)
  - Brain tumors are not TNM-based; use classification systems instead
- Classifications and gradings (Radiopaedia / Radiology Assistant)
  - ASPECTS (stroke)
  - Modified Fisher grade (SAH)
  - WHO CNS tumor classification (high-level summaries)
- Calculators (MDCalc)
  - CHA2DS2-VASc (stroke risk context)
  - GCS (if needed for neuro trauma context)

## Notes for AI/RAG Usage

- All disease-specific claims should be grounded in retrieved open-web
  sources. If not retrieved, output should be limited to general reporting
  safety principles.
- Store source URLs in metadata even if citations are not shown to end users.
- Use CanStaging for TNM where possible and treat it as the authoritative
  reference.

## Diagnosis to Radiology Assistant Mapping (Initial Allowed Source)

This section maps common diagnoses to the closest Radiology Assistant topic.
If no clear match exists, mark as coverage gap for later supplementation.

### Neuro / Head and Neck

- Acute ischemic stroke -> Imaging in Acute Stroke
- Intracerebral hemorrhage -> Traumatic / Non-traumatic Intracranial Hemorrhage
- Subarachnoid hemorrhage -> Intracranial Hemorrhage (general)
- Cerebral venous sinus thrombosis -> Cerebral Venous Sinus Thrombosis
- Multiple sclerosis -> Multiple Sclerosis 2.0
- High-grade glioma -> Systematic Approach to Brain Tumors
- Meningioma -> Systematic Approach to Brain Tumors
- Pituitary macroadenoma -> Sella Turcica and Parasellar Region
- Temporal bone cholesteatoma -> Temporal Bone Pathology
- Acute mastoiditis -> Temporal Bone Pathology
- Peritonsillar abscess -> Infrahyoid Neck (gap if not explicit)
- Deep neck space infection -> Infrahyoid Neck (anatomy and pathology)
- Cervical lymphadenopathy -> Cervical Lymph Node Map
- Thyroid nodule -> TI-RADS

### Chest / Cardio-thoracic

- Pulmonary embolism -> Pulmonary Hypertension and Thromboembolic Disease
- Pneumonia -> Chest X-Ray - Lung Disease / HRCT patterns
- Pulmonary edema -> Chest X-Ray - Heart Failure
- Pneumothorax -> Chest X-Ray - Basic Interpretation
- Lung cancer -> TNM classification 9th edition
- Solitary pulmonary nodule -> Solitary Pulmonary Nodule / Fleischner 2017
- Tuberculosis -> Imaging findings in TB
- Pleural effusion / empyema -> Chest X-Ray - Basic Interpretation
- Aortic dissection -> Acute Aortic Syndrome
- Aortic aneurysm rupture -> Aortic Aneurysm Rupture

### Abdomen / GI

- Acute appendicitis -> Appendicitis and Mimics / Appendicitis - US findings
- Small bowel obstruction -> Closed Loop Obstruction
- Closed-loop obstruction -> Closed Loop Obstruction
- Bowel ischemia -> Bowel Ischemia
- Acute cholecystitis -> Gallbladder obstruction / Gallbladder wall thickening
- Acute pancreatitis -> Acute Pancreatitis
- Diverticulitis -> CT pattern of Bowel wall thickening (partial)
- Acute colitis -> CT pattern of Bowel wall thickening
- Perforated viscus -> Acute Abdomen approach (partial)
- Abdominal abscess -> Acute Abdomen approach (partial)

### Hepatobiliary / Pancreas

- Hepatocellular carcinoma -> Common Liver Tumors / LI-RADS
- Liver metastases -> Common Liver Tumors
- Hepatic hemangioma -> Characterisation of liver masses
- Biliary obstruction / cholangitis -> Biliary duct pathology
- Pancreatic adenocarcinoma -> Pancreatic Cancer - CT staging 2.0
- Pancreatic cystic neoplasm -> Pancreatic cystic lesions

### GU / Renal / Adrenal

- Renal cell carcinoma -> Solid Renal Masses
- Renal trauma -> CT in Abdominal Trauma
- Acute pyelonephritis -> Coverage gap
- Obstructing ureteric stone -> Coverage gap
- Hydronephrosis -> Coverage gap
- Adrenal adenoma vs metastasis -> Characterization of Adrenal lesions
- Testicular torsion -> Coverage gap
- Epididymo-orchitis -> Coverage gap

### MSK / Spine

- Neck of femur fracture -> Hip imaging topics (partial)
- Occult hip fracture -> Hip imaging topics (partial)
- Vertebral compression fracture -> Thoracolumbar injury / AO Spine
- Spinal metastases -> Coverage gap
- Discitis / osteomyelitis -> Coverage gap
- Septic arthritis -> Coverage gap
- Osteomyelitis -> Coverage gap
- Rotator cuff tear -> Shoulder Rotator cuff injury
- Meniscal tear -> Meniscal pathology

### Breast / Gyn

- Breast cancer -> BI-RADS / Breast cancer topics
- Fibroadenoma -> BI-RADS (partial)
- Ovarian torsion -> Acute Abdomen in Gynaecology - Ultrasound
- Ovarian cyst (simple/complex) -> Roadmap to evaluate ovarian cysts
- Ectopic pregnancy -> Transvaginal Ultrasound (partial)
- Endometrial carcinoma -> Endometrial Cancer - MR staging
- Cervical cancer -> Cervical Cancer - MR staging

