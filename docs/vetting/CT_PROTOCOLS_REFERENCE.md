# CT Protocols Reference — Ground Truth Library

> **Purpose:** Canonical CT protocol reference for seeding the `ImagingProtocol` admin table and grounding AI fallback generation.
>
> **Sources:**
> 1. **Swansea NHS Trust CT protocols** (UK department workflow) — primary reference for UK practice.
> 2. **Radiology Assistant — CT contrast injection & protocols** (https://radiologyassistant.nl/more/ct-protocols/ct-contrast-injection-and-protocols) — phase physiology, abdominal pathology timing.
>
> **How to use:** these tables are normalised from the plan doc's JSON blocks and can be imported directly into `ImagingProtocol` via a batch script (pending).

---

## Part A — Swansea NHS Trust CT protocols (UK)

### Head and neck

| Study | Prep | Contrast | Parameters | Comments |
|---|---|---|---|---|
| **Brain** | None | 50 ml hand inject if required | C1 to vertex | 5 mm axial reformats |
| **Sinuses** | None | 50 ml hand inject if required | Frontal to maxillary sinuses | 0.6 mm reformats Cor + Sag. Bone+ and Soft |
| **Orbits** | None | 50 ml hand inject if required | Cover orbits | 0.6 mm reformats Cor + Sag. Bone+ and Soft |
| **Orbital cellulitis / mastoiditis complications** | None | 100 ml at 3 ml/s | 50 s delay | 0.6 mm reformats Cor + Sag. Bone+ and Soft |
| **Pituitary** | None | 50 ml @ 3 ml/s then 45 ml @ 1 ml/s | 60 s delay | 0.6 mm reformats Cor + Sag. Bone+ and Soft |
| **IAMs** | None | 50 ml hand inject if required | Helical head pre, helical IAMs post | 0.6 mm reformats Cor + Sag. Bone+ and Soft |
| **Petrous** | None | None | Helical | 0.6 mm reformats Cor + Sag. Bone+ and Soft |
| **Neck oncology** | None | 100 ml @ 1 ml/s | 100 s delay, supraorbital margin to lung apices | 3 mm axial + Sag/Cor reformats. Bone reformats. Arms by side. Quiet respiration |
| **Neck thyroid MNG** | None | None | Hyoid to carina | 3 mm reformats. Arms by side. Quiet respiration |
| **4D neck (parathyroid)** | None | 100 ml | Pre, 25 s & 85 s. Skull base to T4 | 3 mm reformats. Arms by side. Quiet respiration |
| **Neck infection** | None | 100 ml @ 3 ml/s | Skull base to T4, 50 s delay | 3 mm reformats. Arms by side. Quiet respiration |

### Thorax

| Study | Prep | Contrast | Parameters | Comments |
|---|---|---|---|---|
| **Lung cancer** | None | 100 ml @ 3 ml/s | PV 70 s delay chest/liver | Lung recons |
| **HR thorax (HRCT)** | None | None | Inspiration supine (+ inspiration prone if requested), carina to lung bases | — |

### Abdomen / pelvis oncology

| Study | Prep | Contrast | Parameters | Comments |
|---|---|---|---|---|
| **Breast cancer** | 500 ml water 1.5 h before | 100 ml @ 3 ml/s | PV CAP 70 s delay, include supraclavicular fossa | Lung recons |
| **Oesophagus & gastric, neuroendocrine** | 1 L water 30 min before + 1 glass immediately before; NBM 6 h | 100 ml @ 3 ml/s + Buscopan + water load | PV CAP | Lung recons |
| **Pancreatic cancer** | 500 ml water 1.5 h before + 2 glasses immediately before | 100 ml @ 3 ml/s | Late arterial chest/liver, PV abdo/pelvis | Lung recons |
| **Bowel & rectal cancer** | 500 ml water 1.5 h before | 100 ml @ 3 ml/s | PV CAP | Lung recons |
| **Other bowel pathology** | 500 ml water 1.5 h before | 100 ml @ 3 ml/s | PV AP | — |
| **Renal mass** | 500 ml water 1.5 h before | 100 ml @ 3 ml/s | PV CAP | Lung recons |
| **Renal cyst characterisation** | 500 ml water 1.5 h before | 100 ml @ 3 ml/s | Pre renal area then PV AP | — |
| **TCC upper tract surveillance** | 500 ml water 1.5 h before + 1 glass immediately before | 100–120 ml @ 3 ml/s | Split bolus 20/80 or 20/100, 12 min delay abdo/pelvis | — |
| **Bladder cancer** | 500 ml water 1.5 h before | 100 ml @ 3 ml/s | PV CAP | Lung recons |
| **Testicular cancer** | 500 ml water 1.5 h before | 100 ml @ 3 ml/s | PV CAP | — |
| **Prostate cancer** | 500 ml water 1.5 h | 100 ml @ 3 ml/s | PV CAP | Lung recons |
| **KUB calculus (stone)** | 1 L water 1 h before | None | Prone, low-dose + dual energy if calculus seen | Full bladder |
| **Adrenal mass characterisation** | None | 100 ml @ 3 ml/s | Pre, 60 s, 15 min delay | Just adrenal area |
| **Liver HCC / haemangioma** | — | 100 ml @ 3 ml/s | Arterial liver then PV AP | — |
| **Lymphoma** | 500 ml water 1.5 h before | 100 ml @ 3 ml/s | PV CAP | Lung recons |
| **Melanoma** | 1st visit: Omnipaque 25 ml in 500 ml water × 2 (2 h, 1 h before); water only on follow-up | 100 ml @ 3 ml/s | PV CAP | Lung recons |
| **Gynae cancer** | Omnipaque 25 ml in 500 ml water × 2 (2 h, 1 h before) | 100 ml @ 3 ml/s | PV CAP | Lung recons |

### Vascular (CTA)

| Study | Prep | Contrast | Parameters | Comments |
|---|---|---|---|---|
| **Circle of Willis** | None | Omni 350, 50 ml @ 4 ml/s + 50 ml saline chase | Whole head arterial | MPR |
| **Cerebral venogram (CTV)** | None | Omni 300, 100 ml @ 3 ml/s | Whole head, 50 s delay | MPR |
| **Carotids** | None | Omni 350, 100 ml @ 4 ml/s | Arterial, aortic arch to skull base | MPR |
| **Subclavian angio** | None | Omni 350, 100 ml @ 4 ml/s | Hyoid to below elbow of affected side | Cannula in **non-affected** side |
| **Thoracic angio** | None | Omni 350, 100 ml @ 4 ml/s | Apices to lung bases | Lung reformats |
| **Abdominal / mesenteric angio** | None | Omni 350, 100 ml @ 4 ml/s | Diaphragms to acetabular | — |
| **Renal angio** | None | Omni 350, 100 ml @ 4 ml/s | Diaphragms to iliac crests | — |
| **Aortic dissection** | None | Omni 350, 100 ml @ 4 ml/s | Pre thorax, arterial CAP from C6 to symphysis | — |
| **Peripheral lower-limb angio** | None | Omni 350, 100 ml @ 4 ml/s | Diaphragm to toes | — |
| **Pulmonary angio (CTPA)** | None | Omni 350, 100 ml @ 4 ml/s | Top of arch to base of heart (unless specified) | — |

---

## Part B — Radiology Assistant abdominal CT protocols (phase physiology)

> Source: https://radiologyassistant.nl/more/ct-protocols/ct-contrast-injection-and-protocols
> These are international/physiology-grounded protocols useful for AI-fallback generation.

### Liver

| Indication | Contrast | Phases | Notes |
|---|---|---|---|
| **Liver lesion characterisation** | 150 cc, 5 cc/s, 18 G IV | Arterial 35 s, PV 70 s, Delayed 600 s | Whole abdomen can be scanned during 1st or 2nd scan |
| **Liver metastases (hypovascular)** | 150 cc, 5 cc/s, 18 G IV | PV 70 s | Standard for colorectal/hypovascular mets |

### Pancreas

| Indication | Contrast | Phases | Notes |
|---|---|---|---|
| **Pancreatic carcinoma / pancreatitis** | 150 cc, 5 cc/s, 18 G IV | Arterial 35 s (abdomen), PV 70 s (upper abdomen) | Optional non-contrast upper abdomen for calcifications |

### GI bleed / vascular

| Indication | Contrast | Phases | Notes |
|---|---|---|---|
| **GI bleeding (CT angio)** | Standard | Non-contrast, arterial 35 s, PV 70 s | Triple-phase abdomen |
| **Acute aneurysm / dissection (abdomen)** | Standard | Non-contrast (low dose), arterial 35 s | No PV phase needed |

### Bowel

| Indication | Contrast | Phases | Notes |
|---|---|---|---|
| **Ileus / obstruction** | 150 cc, 5 cc/s, 18 G IV | PV 35 s, diaphragm to symphysis | **No oral contrast.** Optional repeat at 70 s |
| **Anastomotic leak** | 50 cc rectal in 750 ml water + IV | Non-contrast + PV 35 s | Inject IV contrast **immediately after** rectal contrast |

### Adrenal

| Indication | Contrast | Phases | Notes |
|---|---|---|---|
| **Adrenal lesion characterisation** | 100 cc @ 3 cc/s | Non-contrast upper abdomen → if <10 HU **STOP** → otherwise contrast 50 s + delayed 15 min (900 s) | Washout calculation |

### Trauma

| Indication | Contrast | Phases | Notes |
|---|---|---|---|
| **Blunt abdominal trauma** | 150 cc, 5 cc/s | Arterial 35 s, delayed 180 s | Long delay for urinary system filling |
| **Penetrating injury** | Same as blunt | Same + **rectal contrast** for suspected bowel perforation | — |
| **Bladder rupture** | Same as blunt | Same + repeat lower abdomen after bladder contrast instillation | — |

### Urology

| Indication | Contrast | Phases | Notes |
|---|---|---|---|
| **Haematuria / urothelial carcinoma (CT urography)** | 50 cc @ 3 cc/s + 100 cc @ 3 cc/s | Non-contrast, injection, delayed excretory 600 s, post-contrast 90 s | **Prep:** drink 1 L water 30 min before |

### Chest

| Indication | Contrast | Phases | Notes |
|---|---|---|---|
| **Pulmonary emboli (CTPA)** | 80–100 cc @ 5 cc/s | **Bolus tracking** (no fixed delay), ROI right atrium or pulmonary trunk | Start 5 cm below diaphragm. Scan direction depends on scanner speed. Patient breathing instructions critical |
| **Lung carcinoma** | Standard | Chest + upper abdomen 35 s, upper abdomen delayed 70 s | — |

### Aorta

| Indication | Contrast | Phases | Notes |
|---|---|---|---|
| **Thoracic aortic dissection** | Standard | Chest non-contrast, mid-neck to symphysis arterial 5 s | — |

### Brain

| Indication | Prep | Notes |
|---|---|---|
| **Dementia (CT)** | Standard brain CT | Include coronal reconstructions for medial temporal lobe atrophy |

---

## Key physiology references (from Radiology Assistant article)

### Phases of contrast enhancement (to embed as a dictionary entry)

| Phase | Timing (abdomen) | Use |
|---|---|---|
| Non-contrast | — | Calcification, haemorrhage, calculus, baseline HU |
| Early arterial | 15–20 s | Pure arterial mapping |
| Late arterial (peak aortic) | 35 s | HCC, hypervascular lesions, CT angiography |
| Portal venous | 70 s | Parenchymal assessment (liver, pancreas), metastases |
| Delayed/equilibrium | 180 s+ | Fibrotic tissue, cholangiocarcinoma, washout |
| Excretory | 600 s+ | Urothelial assessment, CT urography |

### CECT timing interaction (to embed as a brief explainer)

Four interacting variables determine CECT timing:
1. **Scanner speed** (rotation time, pitch, detectors) — faster scanner needs tighter bolus
2. **Contrast rate** (cc/s) — higher rate → sharper peak, earlier arterial
3. **Contrast volume** (cc) — larger volume → prolonged plateau
4. **Scan delay / acquisition start** — bolus-tracked or fixed

### Oral contrast — role table

| Type | When to use | When **NOT** to use |
|---|---|---|
| **Positive (dilute iodinated / barium)** | Anastomotic leak evaluation, select bowel studies | Routine appendicitis (IV only), ileus, trauma, vascular |
| **Neutral (water / dilute PEG)** | Oncology staging (melanoma, gynae), CT enterography | — |
| **None** | Appendicitis, ileus, trauma, vascular, routine oncology FU | — |

### Rectal contrast — when to use

- Suspected colonic / rectal anastomotic leak
- Penetrating abdominal trauma with suspected bowel perforation
- Bladder rupture assessment (instilled, not rectal)

### Liver dual blood supply — lesion characterisation table

| Phase | Liver parenchyma | Hepatic artery | Portal vein | Best for |
|---|---|---|---|---|
| Early arterial (15–20 s) | Low | Peak | Minimal | Pure arterial mapping |
| Late arterial (35 s) | Low-mid | Peak | Early filling | **HCC**, hypervascular mets (NET, RCC) |
| Portal venous (70 s) | Peak | Declining | Peak | Hypovascular mets, parenchymal lesions |
| Delayed (180 s+) | Washout | Washout | Equilibrium | Haemangioma fill-in, cholangiocarcinoma, HCC washout |

---

## Sources pending ingestion (see `EXTERNAL_SOURCES.md`)

- Omnipaque dosage protocols PDF (KOC)
- Full KOC CT protocols folder
- MRI enterography protocols (2 docx files)
- Split bolus urography technique (AJR 2008)
- PE protocol in pregnancy (AJR 2011)
- RCR Major Adult Trauma Guidance 2024 PDF
