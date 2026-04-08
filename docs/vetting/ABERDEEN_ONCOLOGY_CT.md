# Aberdeen Royal Infirmary (ARI) — CT Oncology Protocols

> **Source:** NHS Grampian — Aberdeen Royal Infirmary
> **Document:** *Oncology-ARI-Aberdeen-CT protocols combined updates Feb 2022*
> **Scope:** Suspected malignancy and cancer follow-up CT protocols
> **Status:** UK teaching-hospital departmental guidance — high quality, clinically validated
> **Ingested:** 2026-04-08 (plain-text pasted by user)
>
> **Role in corpus:** Primary UK reference for **oncology staging/follow-up body coverage + contrast rules** (complements Swansea timing and KOC technical parameters).

---

## How this source is used

Aberdeen defines **which study to do and what coverage/contrast** for each oncology indication. It is **not a scanner parameter file** — it tells you *Brain tumour → pre+post contrast head* rather than specifying kVp/mAs.

Merge strategy: Aberdeen = **clinical indication layer**, KOC = **technical scanner layer**, Swansea = **UK clinical parameters layer**.

---

## 1. Neuro-oncology

| Indication | Protocol |
|---|---|
| **Brain tumours — primary** | Pre-contrast CT head; post-contrast if abnormal |
| **Brain tumours — metastatic** | Post-contrast CT head (if specifically requested) |
| **Post brain tumour resection (initial)** | Pre and post contrast CT head — to differentiate post-op haemorrhage from residual tumour |

---

## 2. Head & neck

| Indication | Protocol |
|---|---|
| **Head & neck SCC** | **Dual phase CT neck (arterial + venous) + CT chest** |

---

## 3. Thoracic malignancy

| Indication | Protocol |
|---|---|
| **Lung cancer** | CT high chest + abdomen + IV |
| **Mesothelioma / pleural disease + follow-up** | CT high chest + abdomen + IV |
| **Breast cancer** | CT high chest + abdomen + pelvis + IV. Post-contrast CT head only if specifically requested |

---

## 4. Upper GI

| Indication | Protocol |
|---|---|
| **Oesophageal cancer** | CT chest + abdomen + IV + **water** (oral) |
| **Stomach (gastric) cancer** | CT chest + abdomen + pelvis + IV + **water** (oral) |

---

## 5. Hepatobiliary

### Primary hepatic lesion

| Sub-scenario | Protocol |
|---|---|
| **Cirrhosis + suspected HCC / post-TACE** | **4-phase CT abdomen with Iomeron-400**: pre-contrast, arterial (35 s), venous (70 s), equilibrium (180 s). Include CT chest if requested or in primary liver malignancy |
| **Benign lesions suspected** (haemangioma, adenoma, FNH — HCC NOT suspected) | **MRI is first line**. If MRI unavailable → CT abdomen — arterial + venous + equilibrium phases |

### Hepatic metastases

| Scenario | Protocol |
|---|---|
| **Standard suspected mets** | CT chest + abdomen + pelvis + IV |
| **Hypervascular primaries** (thyroid, RCC, NET, melanoma, choriocarcinoma) | **Add arterial phase** CT abdomen |

---

## 6. Pancreatic & biliary

| Indication | Protocol |
|---|---|
| **Pancreatic cancer / cholangiocarcinoma — initial** | First: **ultrasound** to assess biliary obstruction. Then CT if pancreatic neoplasm suspected: **CT chest + pre-contrast + arterial (40 s) abdomen + venous phase abdomen & pelvis + water** (pre-contrast to look for stones) |
| **Pancreatic cancer — follow-up** | CT abdomen venous phase (to assess chemo response). If operable → arterial + venous phase |

---

## 7. Lower GI

| Indication | Protocol |
|---|---|
| **Colorectal cancer** | CT chest + abdomen + pelvis + IV |
| **Anal canal cancer** | CT chest + abdomen + pelvis + **groins** + IV |

---

## 8. Genitourinary — kidney & urothelium

| Indication | Protocol |
|---|---|
| **Renal indeterminate lesion** | **Triple phase CT renal** — pre + 30 s + 100 s |
| **Renal malignancy** | Triple phase CT renal (pre + 30 s + 100 s) + CT chest; add pelvis if local symptoms (e.g. bone pain) |
| **Ureter / upper urothelial tumour — painful haematuria** | CT KUB + CT urogram + water |
| **Ureter / upper urothelial tumour — painless haematuria** | CT urogram + water |
| **Bladder tumour — staging & follow-up** | CT urogram (**split-dose IV contrast**) + water; add CT chest if requested |

---

## 9. Male pelvis

| Indication | Protocol |
|---|---|
| **Prostate (staging & follow-up)** | CT abdomen + pelvis + IV + water; add CT chest if requested |
| **Testicular tumour — staging & follow-up** | CT chest + abdomen + pelvis + IV. On follow-up, **pelvis may be omitted** if inguinal orchidectomy |

---

## 10. Adrenal

| Indication | Protocol |
|---|---|
| **Adrenal nodule assessment** | **Pre-contrast CT abdomen + review**. If homogeneous and **< 10 HU → STOP**. If non-homogeneous or ≥ 10 HU → add IV contrast, image at **1 min and 15 min** (washout study) |
| **Adrenocortical carcinoma** | Pre-contrast CT abdomen + CT chest (65 s) |

---

## 11. Gynaecological malignancy

| Indication | Protocol |
|---|---|
| **Ovarian tumour (staging & follow-up)** | CT chest + abdomen + pelvis + IV |
| **Cervical cancer** | CT **only if unable to have MRI** — CT abdomen + pelvis + IV |
| **Endometrial cancer** | CT **if Grade 3** — CT chest + abdomen + pelvis + IV |
| **Vulval / vaginal cancer** | CT **only if unable to have MRI** — CT abdomen + pelvis + IV |

---

## 12. Other

| Indication | Protocol |
|---|---|
| **Bone & soft-tissue sarcoma** | CT chest + abdomen + pelvis + IV |
| **Lymphoma** | CT **neck** + chest + abdomen + pelvis + IV |
| **Melanoma** | CT chest + abdomen + IV. Add CT head / neck / pelvis if requested |
| **Carcinoma of unknown primary (CUP)** | CT chest + abdomen + pelvis + IV |

---

## Protocol themes extracted

| Theme | Aberdeen rule |
|---|---|
| **Oral prep** | Oesophageal / gastric / pancreatic / bladder / urothelial / prostate → **water** (no barium, no positive oral) |
| **MRI-first indications** | Cervix, vulva, vagina, endometrium (unless Grade 3), benign liver lesions |
| **Bone/pelvis add-on** | Renal Ca with bone pain, melanoma if requested, breast if requested |
| **Arterial-phase add-on** | Hypervascular mets (thyroid, RCC, NET, melanoma, choriocarcinoma) |
| **Washout study** | Adrenal nodule ≥ 10 HU — 1 min + 15 min timed delays |
| **Split-bolus** | Bladder cancer CT urogram (split-dose IV) |
| **Dual-phase neck** | HN SCC (arterial + venous) |
| **Contrast agent** | Liver HCC/TACE uses **Iomeron-400** (high-concentration), standard elsewhere |

---

## Mapping to DB / merge plan

| Aberdeen protocol | DB action | Target ID / new slug |
|---|---|---|
| Brain primary / metastatic | 🟢 ENRICH | id=1 CT Brain + id=18 CT Brain with Contrast |
| HN SCC dual phase | ⚪ ADD | `ct-neck-hn-scc` |
| Lung Ca staging | ⚪ ADD | `ct-lung-cancer` |
| Mesothelioma | ⚪ ADD | `ct-mesothelioma` |
| Breast Ca staging | ⚪ ADD | `ct-breast-cancer` |
| Oesophageal + water | ⚪ ADD | `ct-oesophageal-cancer` |
| Gastric + water | ⚪ ADD | `ct-gastric-cancer` |
| HCC 4-phase (Iomeron-400) | 🟢 MERGE | id=26 CT Liver Triphasic (upgrade to 4-phase + specify Iomeron-400) |
| Hepatic mets (+arterial for hypervascular) | 🟢 ENRICH | id=23 CT CAP Staging (note) |
| Pancreas + water | 🟢 ENRICH | id=28 CT Pancreas Protocol (add water prep from Aberdeen) |
| Pancreas follow-up | ⚪ ADD | `ct-pancreas-followup` |
| Colorectal Ca | ⚪ ADD | `ct-colorectal-cancer` |
| Anal canal + groins | ⚪ ADD | `ct-anal-canal-cancer` |
| Renal indeterminate triphasic | 🟢 ENRICH | id=31 CT Urogram (add as variant) |
| Renal malignancy triphasic + chest | ⚪ ADD | `ct-renal-cancer` |
| Upper urothelial (painful/painless) | ⚪ ADD | `ct-upper-urothelial-haematuria` |
| Bladder Ca split-bolus | ⚪ ADD | `ct-bladder-cancer` |
| Prostate staging | ⚪ ADD | `ct-prostate-cancer` |
| Testicular staging | ⚪ ADD | `ct-testicular-cancer` |
| Adrenal washout | ⚪ ADD | `ct-adrenal-washout` |
| Adrenocortical Ca | ⚪ ADD | `ct-adrenocortical-cancer` |
| Ovarian staging | ⚪ ADD | `ct-ovarian-cancer` |
| Cervix (MRI-first fallback) | ⚪ ADD | `ct-cervical-cancer` |
| Endometrial G3 | ⚪ ADD | `ct-endometrial-cancer` |
| Vulval/vaginal | ⚪ ADD | `ct-vulval-vaginal-cancer` |
| Sarcoma | ⚪ ADD | `ct-sarcoma-staging` |
| Lymphoma (neck included!) | ⚪ ADD | `ct-lymphoma-staging` |
| Melanoma | ⚪ ADD | `ct-melanoma-staging` |
| CUP | ⚪ ADD | `ct-cup` |

**Total new oncology protocols from Aberdeen:** 25 new + 4 enriched

---

## Conflict resolution with Swansea

Where Aberdeen and Swansea both cover the same cancer:

| Protocol | Aberdeen says | Swansea says | Resolution |
|---|---|---|---|
| **Breast Ca** | CT high chest + A/P + IV | Breast = PV CAP | Merge — Aberdeen specifies "high chest" (apex to bases), Swansea gives PV timing. Use Aberdeen coverage + Swansea phase/timing. |
| **Lymphoma** | **Neck** + chest + abd + pelvis + IV | CAP only | **Aberdeen wins** — neck inclusion is clinically important. |
| **Melanoma** | Chest + abdomen + IV (pelvis optional) | CAP | **Aberdeen wins** — allows pelvis-sparing for lower-energy melanoma staging. |
| **Pancreas** | CT chest + pre + 40 s arterial + venous A/P + water | Water prep + late arterial chest/liver | Combine — Aberdeen timing (40 s arterial), Swansea water volume, both include chest. |
| **Liver HCC** | 4-phase (pre/35/70/180) + **Iomeron-400** | Liver HCC/Haemangioma (timing from Rad Assist) | Merge — Aberdeen contrast agent brand, Rad Assist physiology timings. |

---

## Oral contrast doctrine (from Aberdeen)

Aberdeen is explicit: **oral contrast is water** (negative contrast) for staging. **No positive oral** (iodinated or barium) for:
- Oesophageal / gastric / pancreatic / bladder / urothelial / prostate staging

This aligns with **current UK practice** (RCR/BSUGi) — another data point supporting the prompt guidance that **oral contrast for appendicitis is obsolete**.
