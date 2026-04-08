# Protocol Source Comparison — DB vs Swansea vs KOC

> **Purpose:** Head-to-head side-by-side comparison of the same protocol across all three sources to determine which source is most complete, richest, and most aligned with actual practice.
>
> **Generated:** 2026-04-08
> **Sample:** 5 common protocols (CT Brain Plain, CTPA, CT Chest Plain, CT KUB, CT Pancreas)

---

## TL;DR — Winner by category

| Aspect | DB | Swansea | KOC |
|---|:---:|:---:|:---:|
| Purpose / indications | ⚠️ Minimal | ❌ None | ✅ **Detailed** |
| Patient preparation | ❌ Absent | ✅ Present | ✅ **Detailed** |
| Coverage description | ⚠️ Brief | ✅ Present | ✅ **Precise** |
| Contrast volume (ml) | ❌ Absent | ✅ Present | ✅ **Present** |
| Flow rate (ml/s) | ⚠️ Some | ✅ Present | ✅ **Present** |
| Phase delays (s) | ⚠️ Some | ⚠️ Partial | ✅ **Full** |
| Scan parameters (kVp, mA, pitch) | ⚠️ kVp only | ❌ None | ✅ **Full** |
| Reconstruction details (planes, mm) | ❌ Absent | ✅ Brief | ✅ **Full** |
| Kernel / filter / algorithm | ❌ Absent | ❌ None | ✅ **Full** |
| UK-specific practice | ⚠️ Generic | ✅ **Best** | ⚠️ Middle East |
| Comments / clinical pearls | ❌ Absent | ✅ Brief | ✅ **Present** |
| **Overall richness (1-10)** | **2** | **6** | **9** |

**Verdict:**
- **KOC is overwhelmingly the richest source** (specific scan params, kernel, reconstructions, purpose, patient prep with mL of water).
- **Swansea is best for UK-specific practice patterns** (prep regimes like 500 ml water 1.5 h before, Omnipaque flavoured water, UK-named protocols like "PV CAP").
- **DB entries are minimal shells** — usable as placeholders but essentially useless for radiographer-level content.

---

## Protocol 1 — CT Brain Routine (Plain)

### 🟦 Existing DB (id=1)
```
SHORTHAND:
  CT Brain Plain
  Skull base to vertex
  Non-contrast study

DETAILED:
  Phase: Non-contrast | Timing: 0s | Coverage: Skull base to vertex
  kVp: 120 | mAs: auto | Slice: 3 mm | Interval: 2 mm
  Notes: Brain + bone reconstruction

PREP:      (none)
KEYWORDS:  brain, emergency, non-contrast, CT brain plain, head CT, CT head non contrast
```

### 🟩 Swansea
```
Study:        Brain
Prep:         None
Contrast:     50 ml hand inject if required
Parameters:   C1 to vertex
Comments:     5 mm axial reformats
```

### 🟥 KOC (richest)
```
Title:        Brain Routine – Plain

Purpose:      Evaluation of altered mental status, congenital anomalies,
              hydrocephalus, hemorrhages, tumors, strokes, headaches,
              infections (usually IV contrast required), seizures
              (contrast may be required), trauma, post-operative changes,
              calcifications.

Instructions: Cover the entire brain from foramen magnum to vertex,
              angled with OML (base of the skull).
Scanograms:   Dual, 120 kVp / 20 mA
Prep:         No preparation required.

Scan Details:
  Mode: W-Volume | Beam: 0.5 × 80 | Pitch: —
  kVp: 120 | mA: 280 | SureExp 3D: OFF | FOV: S

Procedure:
  Phase: Plain
  Coverage: Below base of skull to vertex
  Reconstructions: Ax 3×2, Cor 3×3 (only if SOL), Sag 3×3 (only if SOL)

Algorithm:
  Kernel: FC68 | Filter: OFF | Boost: OFF | OSR: Head

Comments:
  SOL implies tumors / masses / hematomas / abscesses.
  Display window (WW/WL): 80/40
```

**Comparison:**

| Field | DB | Swansea | KOC |
|---|:---:|:---:|:---:|
| Purpose / indications | — | — | ✅ 10 indications listed |
| Coverage language | Skull base to vertex | C1 to vertex | **Foramen magnum to vertex, OML-angled** |
| kVp | 120 | — | 120 |
| mA | auto | — | **280 (specific)** |
| Beam / pitch | — | — | **0.5 × 80, W-Volume** |
| Recon thickness | 3 mm | 5 mm | **Ax 3×2, Cor/Sag 3×3 if SOL** |
| Kernel | — | — | **FC68** |
| Display WW/WL | — | — | **80/40** |

**Winner: KOC by a wide margin.** Swansea adds nothing that KOC doesn't already have more precisely. DB is unusable for radiographer-level content.

---

## Protocol 2 — CT Pulmonary Angiography (CTPA)

### 🟦 Existing DB (id=9)
```
SHORTHAND:
  CTPA
  Pulmonary arteries
  IV contrast arterial phase

DETAILED:
  Contrast Type: Iodinated | Rate: 4 ml/s | Timing: Bolus tracking
  (nothing else — no volume, no coverage, no params)

KEYWORDS:  vascular, emergency
```

### 🟩 Swansea
```
Study:        Pulmonary Angio (CTPA)
Prep:         None
Contrast:     Omni 350, 100 ml @ 4 ml/s
Parameters:   Top of aortic arch to base of heart (unless specified by radiologist)
Comments:     —
```

### 🟥 KOC
```
Title:        Pulmonary Angio (CTA)

Purpose:      Evaluate pulmonary embolism (PE). Emergency scan — triage
              patient for top priority.
Instructions: Cover entire thorax.

Prep:         Train patient on breath holding.
              Contrast media preparation required.
              18G cannula (preferred on Rt side).

Scan Details:
  Mode: Helical | Beam: 0.5 × 80 | Pitch: HP Detail
  kVp: 120 | mA: Reference | SureExp 3D: Hi Quality | FOV: L

Contrast:
  Volume: 50 cc | Rate: 5.0 cc/s | Delay: SureStart (bolus tracking)

Procedure:
  Phase: Chest CTA
  Coverage: Above lung apices to below diaphragm
  Reconstructions: Ax 1×1 (CTA) / 3×3 (lung), Cor 2×2 CTA, Sag 2×2 CTA

Algorithm:
  Chest CTA: Kernel FC08, Filter AIDR 3D STND, OSR On
  Lung: Kernel FC52

Comments:
  MIP coronal, MIP sagittal, and MIP obliques required.
```

**Comparison:**

| Field | DB | Swansea | KOC |
|---|:---:|:---:|:---:|
| Contrast volume | ❌ | **100 ml** | 50 cc |
| Flow rate | 4 ml/s | 4 ml/s | **5.0 cc/s** |
| Coverage | — | Arch to heart base | **Apices to diaphragm (wider)** |
| Delay / timing | Bolus tracking | (implicit) | **SureStart named** |
| Scanner params | — | — | **Full (kVp/beam/pitch)** |
| Reconstructions | — | — | **Ax 1×1 CTA + 3×3 lung** |
| Kernel | — | — | **FC08 CTA + FC52 lung** |
| Post-processing | — | — | **MIP cor/sag/oblique required** |
| Cannula spec | — | — | **18G right side** |
| Breath-hold coaching | — | — | ✅ |

**Conflict point:** Swansea says 100 ml, KOC says 50 cc. **Swansea (100 ml) is more aligned with UK practice** (standard UK CTPA volume is 60–100 ml at 4–5 ml/s). KOC's 50 cc is on the low side for UK adult practice.

**Winner: KOC for technical depth + MIP post-processing, but Swansea overrides on contrast volume for UK practice.** Best result = **merge KOC scaffold with Swansea volume**.

---

## Protocol 3 — CT Chest Routine (Plain)

### 🟦 Existing DB (id=2)
```
SHORTHAND:
  CT Chest
  Lung apices to mid kidneys
  Optional contrast

DETAILED:
  Phase: Pre-contrast | Timing: 0s | Coverage: Chest | kVp: 120 | Slice: 2 mm
  Phase: Post-contrast | Timing: 50s | Coverage: Chest | kVp: 120 | Slice: 2 mm

KEYWORDS:  chest, contrast, routine, CT chest, thorax CT
```

### 🟩 Swansea
```
Study:        HR Thorax (HRCT)   [Swansea has no "routine" chest plain]
Prep:         None
Contrast:     None
Parameters:   Inspiration supine (+ inspiration prone if requested),
              carina to lung bases
Comments:     —
```
*Swansea does not have a generic "CT Chest Plain" — it has "HR Thorax" (HRCT) and "Lung cancer" (PV staging).*

### 🟥 KOC
```
Title:        Chest Routine (plain)

Purpose:      Trauma, pneumonia, pleural effusion, pneumothorax,
              chest wall disease, post-operative assessment.
Prep:         Train patient on breath holding.

Scan Details:
  Mode: Helical | Beam: 0.5 × 80 | Pitch: HP Detail
  kVp: 120 | mA: Reference | FOV: L

Procedure:
  Phase: Plain
  Coverage: Above lung apices to below diaphragm
  Reconstructions:
    Ax 2×2 (mediastinum) (lung), 1×10 (HRCT)
    Cor 3×3 (lung)
    Sag 3×3 (lung)

Algorithm:
  Mediastinum: Kernel FC08**
  Lung: Kernel FC52
  HRCT: Kernel FC56
```

**Comparison:**

| Field | DB | Swansea | KOC |
|---|:---:|:---:|:---:|
| Coverage | Apices to mid-kidneys (non-standard) | Carina to bases (HRCT only) | **Apices to diaphragm** |
| Has separate HRCT recon | ❌ | HRCT only | ✅ **Integrated 1×10 HRCT on same scan** |
| Mediastinum kernel | ❌ | — | **FC08** |
| Lung kernel | ❌ | — | **FC52** |
| HRCT kernel | ❌ | — | **FC56** |
| Plain + contrast workflow | Both in one entry | Separate Swansea protocols | Separate KOC protocols |

**Conflict:** DB has a dubious "mid-kidneys" coverage range. KOC's "apices to diaphragm" is the standard. Swansea's "carina to bases" only applies to HRCT.

**Winner: KOC.** The integration of mediastinum/lung/HRCT kernels on a single scan is more modern than Swansea's split approach.

---

## Protocol 4 — CT KUB (Stone Protocol)

### 🟦 Existing DB (id=30)
```
SHORTHAND:
  CT KUB
  Kidneys to bladder
  Non-contrast

DETAILED:
  Phase: Plain | Notes: Stone protocol

KEYWORDS:  renal, stone
```
*(This is the thinnest existing entry — essentially a title with no technical content.)*

### 🟩 Swansea
```
Study:        KUB Calculus
Prep:         1 L water 1 h before scan
Contrast:     None
Parameters:   Prone, low-dose + dual energy if calculus seen
Comments:     Full bladder
```

### 🟥 KOC
```
Title:        KUB (Prone Position)

Purpose:      Abdomen pain — renal colic.
Prep:         Bladder should be at least partially full (NOT too full).
              For renal colic: scan prone.

Scan Details:
  Mode: Helical | Beam: 0.5 × 80 | Pitch: HP Standard
  kVp: 120 | mA: Reference | FOV: L

Procedure:
  Phase: Plain
  Coverage: Above diaphragm to below ischium
  Reconstructions:
    Ax 2×2 (abdomen)
    Cor 3×3 (abdomen)
    Sag 3×3 (abdomen)

Algorithm:
  Abdomen: Kernel FC08, Filter AIDR 3D STND, OSR On

Comments:
  Protocol is configured for prone positioning.
```

**Comparison:**

| Field | DB | Swansea | KOC |
|---|:---:|:---:|:---:|
| Prep (water timing/volume) | ❌ | **1 L water 1 h before** | "partially full bladder" (no volume) |
| Position (prone) | ❌ | ✅ | ✅ |
| Low-dose technique | ❌ | ✅ mentioned | ❌ not stated |
| Dual-energy if stone seen | ❌ | ✅ | ❌ |
| Coverage | Kidneys to bladder | — | **Diaphragm to ischium** |
| Kernel / filter | ❌ | ❌ | ✅ FC08 + AIDR |
| Reconstructions | ❌ | ❌ | ✅ Ax/Cor/Sag |

**KEY FINDING:** This is the **only protocol where Swansea beats KOC on clinical content** — Swansea explicitly mentions **low-dose + dual-energy** (modern UK practice) and the **1 L water 1 h before** prep regime. KOC lacks both.

**Winner: MERGE Swansea + KOC.**
- Swansea contributes: prep (1 L water, 1 h), low-dose + dual-energy language
- KOC contributes: coverage (diaphragm to ischium), kernel (FC08), reconstructions
- DB: delete the thin shell, replace entirely

---

## Protocol 5 — CT Pancreas (Acute Pancreatitis / Pancreatic Mass)

### 🟦 Existing DB (id=28)
```
SHORTHAND:
  Pancreas CT
  Pancreas
  Pancreatic + portal phase

DETAILED:
  Phase: Pancreatic phase | Timing: 40s
  Phase: Portal phase     | Timing: 70s

KEYWORDS:  pancreas, oncology
```

### 🟩 Swansea
```
Study:        Pancreatic Cancer
Prep:         500 ml water 1.5 h before + 2 glasses water immediately before
Contrast:     100 ml @ 3 ml/s
Parameters:   Late arterial chest/liver, PV abdo/pelvis
Comments:     Lung recons
```

### 🟥 KOC
```
Title:        Pancreas (Acute Pancreatitis / Pancreatic Mass)

Purpose:      Evaluation of pancreatic pathology.
Instructions: Cover entire abdomen, diaphragm to pubic symphysis.

Prep:         Contrast required, 18G cannula.
              500 mL – 1 L water over 30 min (skip if not tolerated).

Scan Details:
  Mode: GG-Hel (gated helical) | Beam: 0.5 × 80 | Pitch: HP Standard
  kVp: 120 | mA: Reference | FOV: L

Contrast:
  Volume: 100 cc | Rate: 4.0 cc/s | Delay: 35 s

Procedure:
  Phase 1 (Plain):           Diaphragm to iliac crest | Ax 2×2
  Phase 2 (Pancreatic 35 s): Diaphragm to iliac crest | Ax 2×2 + Cor 3×3
  Phase 3 (Portal venous 65 s): Diaphragm to iliac crest | Ax 2×2 + Cor 3×3 + Sag 3×3

Algorithm:
  Abdomen: Kernel FC08, Filter AIDR 3D STND
```

**Comparison:**

| Field | DB | Swansea | KOC |
|---|:---:|:---:|:---:|
| Pancreatic phase delay | **40 s** | — | **35 s** |
| Portal phase delay | **70 s** | — | **65 s** |
| Contrast volume | ❌ | **100 ml** | **100 cc** |
| Flow rate | ❌ | **3 ml/s** | **4 cc/s** |
| Oral prep (volume + timing) | ❌ | 500 ml @ 1.5 h | **500 mL–1 L over 30 min** |
| Coverage | ❌ | — | **Diaphragm to iliac crest** |
| Includes non-contrast phase | ❌ | ❌ | ✅ |
| Includes chest/liver late arterial | ❌ | ✅ | ❌ |
| Lung recons | ❌ | ✅ | ❌ |
| Scanner params | ❌ | ❌ | ✅ |

**Conflicts:**
1. **Flow rate:** Swansea 3 ml/s vs KOC 4 cc/s. **KOC is correct for modern pancreas protocol** — 4–5 ml/s is needed for the pancreatic arterial phase at 35 s.
2. **Delays:** DB has 40/70s, KOC has 35/65s. **KOC is more aligned with modern practice** (35 s = late arterial/pancreatic, 65 s = portal venous on modern scanners).
3. **Chest/liver coverage:** Swansea includes it, KOC does not. For **staging** pancreatic cancer, chest/liver inclusion is standard (UK practice) — so Swansea adds clinical coverage depth here.
4. **Lung recons:** Only Swansea mentions this.

**Winner: MERGE KOC (technical core) + Swansea (staging extension).**
- KOC contributes: all scan params, 35/65 s timing (modern), 4 cc/s rate, oral prep protocol, coverage, kernel
- Swansea contributes: chest/liver coverage for staging, lung reconstructions
- Result: the best pancreas protocol any of the three could produce alone.

---

## Overall patterns observed

### KOC strengths
- **Scanner parameters** (mode, beam, pitch, kVp, mA, FOV) — present on every protocol, absent from Swansea and DB.
- **Kernels and reconstruction algorithms** (FC08, FC52, FC56, FC68, AIDR) — unique to KOC.
- **Reconstruction planes and slice thickness per plane** (Ax, Cor, Sag + mm) — unique to KOC.
- **Clinical purpose statements** — 5–10 indications per protocol.
- **Patient-specific instructions** (breath-hold coaching, cannula gauge + side, positioning).
- **Scanogram settings** specified separately (120 kVp / 20–50 mA).

### Swansea strengths
- **UK oral prep regimes** (500 ml water 1.5 h before, 2 glasses immediately before, Omnipaque-flavoured water for melanoma/gynae).
- **NBM requirements** (oesophagus 6 h NBM).
- **UK-specific named protocols** ("PV CAP", "lung recons", "bowel and rectal cancer").
- **Buscopan requirements** (oesophagus, gynae).
- **Multi-region studies for staging** (Swansea "Pancreatic Cancer" includes chest/liver late arterial + abdomen PV).
- **Low-dose + dual-energy technique** for stone protocol.
- **TCC split-bolus technique** (20/80 with 12 min delay).

### KOC weaknesses
- Uses **Middle-Eastern / Aberdeen practice** — some contrast volumes are lower than UK standard (e.g. CTPA 50 cc vs UK 100 ml).
- Missing UK-specific oral prep regimes.
- Missing staging extensions (single-region focus).

### Swansea weaknesses
- **No scanner parameters** at all (kVp/mA/pitch absent).
- **No reconstruction specifications** beyond "lung recons / MPR / bone".
- **No kernels or filters**.
- **No purpose / indications listed**.
- **No patient positioning / cannula specs**.

### DB weaknesses
- Essentially **empty placeholders** — titles are OK, detailed content is insufficient for any downstream use.
- Some protocols have obvious duplicates.
- Some have non-standard coverage ("mid-kidneys" for chest).

---

## Recommended import strategy (based on this comparison)

### Strategy: **KOC scaffold + Swansea UK overlay**

1. **Parse all 8 KOC Word files first** — they give us the richest technical scaffold (parameters, kernels, reconstructions, purpose, prep). This becomes the new canonical `detailed_protocol_html` content.

2. **Cross-reference against Swansea** — where Swansea has UK-specific content not in KOC:
   - Prep regimes (oral water, NBM, Buscopan, flavoured contrast)
   - Staging extensions (chest/liver add-ons)
   - UK-named protocols (PV CAP, low-dose + dual-energy KUB, split-bolus TCC)
   - Modern UK contrast volumes (override KOC where KOC is too low)

3. **Where KOC and Swansea conflict on clinical values** (contrast volume, timing), the rule is:
   - **Prefer Swansea** for UK-facing practice values
   - **Prefer KOC** for technical scanner parameters
   - Document the choice in a `source_citation` field per protocol

4. **Merge into existing DB rows where title matches** (preserving IDs). Add new rows for what's missing. Delete the 4 duplicates already identified.

5. **Add Radiology Assistant physiology content** as a separate knowledge-dictionary block (not a protocol entry) — this becomes reference material inside `ai_vetting.py` for the AI fallback path.

### Suggested import order

| Step | Action | Why this order |
|---|---|---|
| 1 | Delete duplicates (ids 17, 21, 22, 27) | Pure cleanup, no risk |
| 2 | Parse remaining 5 KOC files (neck, extremities, paediatric, Aberdeen oncology, protocol codes) | Complete the KOC corpus first |
| 3 | Produce **full** match matrix (48 DB vs ~70 KOC) | Know exactly what's new before importing |
| 4 | Build merged content per protocol using KOC + Swansea rules | Apply the strategy above |
| 5 | Write batch upsert script targeting DB | Idempotent, re-runnable |
| 6 | Run dry-run → review → commit | Auto-publish on commit per user decision |
| 7 | Seed `_EVIDENCE_BLOCK` knowledge dictionary from Radiology Assistant physiology + Omnipaque dosage + Oral contrast prep docs | Separate from protocol import |

### What I need from you before step 2

- Confirm: **parse all remaining 5 KOC files next**? (cranium, thorax, abdomen already done — 34 protocols identified, awaiting neck + extremities + paediatric + Aberdeen + protocol codes)
- Or: **start with the dedupe step 1 now** and parse remaining KOC in parallel?
