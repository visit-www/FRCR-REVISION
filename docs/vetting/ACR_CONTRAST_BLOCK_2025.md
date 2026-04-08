# ACR Manual on Contrast Media (2025) — Distilled Reference Block

This is a compact distillation of the **ACR Manual on Contrast Media (2025 ed., Jan 2025, 122 pp)**.
Extracted via pdfplumber from the official ACR PDF.
All numeric values, drug doses, and category boundaries have been verified against the clean source text.

**Purpose**: single source of truth for both the **Contrast Reaction Card** UI partial
(`templates/partials/_contrast_reaction_card.html`) and the AI vetting evidence block
(`ai_vetting.py` → `_ACR_CONTRAST_BLOCK`). When the underlying ACR Manual is updated, change this file
first; everything else cites these numbers.

**Size target**: ~2.5–3 KB, optimised for token efficiency. Every line is directly sourceable.

---

```python
_ACR_CONTRAST_BLOCK = """
ACR MANUAL ON CONTRAST MEDIA (2025 ed.) — AUTHORITATIVE REFERENCE FOR CONTRAST SAFETY:

1. CORTICOSTEROID PREMEDICATION (prior allergic-like reaction to same class of contrast):
   A. Elective 12-13 h ORAL (either regimen):
      - Prednisone 50 mg PO at 13 h, 7 h, and 1 h pre-contrast + diphenhydramine 50 mg PO/IM/IV at 1 h; OR
      - Methylprednisolone 32 mg PO at 12 h and 2 h pre-contrast (± diphenhydramine 50 mg).
      If unable to take PO: substitute hydrocortisone 200 mg IV for each oral prednisone dose.
   B. Accelerated IV (urgent, 4-5 h duration, in decreasing order of preference):
      1. Methylprednisolone Na succinate (Solu-Medrol) 40 mg IV OR hydrocortisone Na succinate (Solu-Cortef)
         200 mg IV immediately, then every 4 h until contrast + diphenhydramine 50 mg IV 1 h pre-contrast.
      2. Dexamethasone Na sulfate (Decadron) 7.5 mg IV immediately, then every 4 h + diphenhydramine 50 mg IV 1 h pre.
      3. Same drugs each 1 h pre-contrast — <4 h regimens have NO evidence of efficacy; only in true emergencies.
   C. Paediatric (ACR Table A/B):
      - Elective: Prednisone 0.5-0.7 mg/kg PO (max 50 mg) at 13/7/1 h + diphenhydramine 1.25 mg/kg PO (max 50 mg) at 1 h.
      - Urgent/ED/NPO: Hydrocortisone 2 mg/kg IV (max 200 mg) at 5 h and 1 h + diphenhydramine 1 mg/kg IV (max 50 mg) at 1 h.
   Premedication is NOT indicated for shellfish/seafood allergy, topical iodine allergy, asthma alone, or prior
   reaction to a different class of contrast. Cross-reactivity iodinated<->gadolinium is NOT established.

2. POST-CONTRAST AKI (PC-AKI) / CI-AKI — IV iodinated contrast:
   - Single evidence-based threshold: eGFR 30 mL/min/1.73m². Above 30 → IV iodinated contrast is NOT an independent
     nephrotoxic risk factor (level 1 evidence, Davenport/McDonald/Hinson 2013-2014 propensity-matched studies).
   - eGFR 30-44: borderline, not statistically significant risk; give contrast if clinically indicated at STANDARD dose.
   - eGFR <30 or AKI: weigh risks and benefits; prophylactic IV 0.9% saline (periprocedural volume expansion) may be
     considered. NOT an absolute contraindication.
   - PROPHYLAXIS: IV 0.9% saline only. Sodium bicarbonate is no better than saline. N-acetylcysteine is NOT recommended
     (no efficacy). Diuretics/mannitol NOT recommended. DO NOT reduce contrast dose to mitigate risk — it produces
     non-diagnostic scans without changing CI-AKI risk.
   - Screening eGFR only required if: CKD, remote AKI, dialysis, kidney surgery/ablation, albuminuria, or metformin use
     (± diabetes mellitus as optional risk factor). Routine patients without risk factors do NOT need baseline creatinine.

3. METFORMIN (ACR Categories):
   - Category I (eGFR ≥30 and no AKI): NO need to discontinue metformin before or after IV iodinated contrast,
     NO need to re-check renal function afterwards.
   - Category II (eGFR <30, AKI, OR intra-arterial study with potential renal artery embolisation): STOP metformin at
     time of procedure, withhold 48 h, restart only after renal function rechecked and confirmed normal.
   - Gadolinium at standard MRI dose (0.1-0.3 mmol/kg): no metformin interruption needed.

4. GADOLINIUM-BASED CONTRAST AGENTS (GBCA) & NSF RISK:
   - Group I (greatest NSF risk — contraindicated in eGFR <30/AKI/dialysis):
     Gadodiamide (Omniscan), Gadopentetate (Magnevist), Gadoversetamide (OptiMARK).
   - Group II (few/no unconfounded NSF cases — safe at standard dose in CKD/AKI/dialysis; screening eGFR is OPTIONAL):
     Gadobenate (MultiHance), Gadobutrol (Gadavist/Gadovist), Gadoteric acid (Dotarem/Clariscan),
     Gadoteridol (ProHance), Gadopiclenol (Elucirem/Vueway)*, Gadoxetate disodium (Eovist/Primovist).
   - Group III: no agents currently classified (April 2024).
   - For Group II agents, ACR states renal function screening is OPTIONAL and contrast-enhanced MRI is NOT
     contraindicated at standard dose in eGFR <30, AKI, or on dialysis. Use lowest diagnostic dose.
   - In UK practice, Group II macrocyclic agents (Dotarem/Gadavist/ProHance) are standard; linear Group I agents are
     largely withdrawn (EMA 2017).

5. EXTRAVASATION (peripheral IV contrast):
   - Initial management: STOP injection, elevate affected limb above heart, apply cold OR warm compresses.
     No medical intervention (hyaluronidase, steroids, anticoagulants) has been shown effective. Hyaluronidase is NOT recommended.
   - Surgical consultation: based on CLINICAL SIGNS, not volume threshold. Obtain urgent surgical/plastics review if:
     severe pain, progressive swelling, decreased capillary refill, altered sensation, worsening active/passive range
     of motion, skin ulceration or blistering. Most common severe complication = compartment syndrome.
   - Volume thresholds (e.g. 100-150 mL) should NOT be used as a sole trigger for surgical consult.
   - Outpatients must be given written instructions to return for worsening pain, paraesthesia, reduced movement,
     or skin changes (severe injuries may develop hours later).

6. PAEDIATRIC IODINATED CONTRAST:
   - Typical dose: 1.5-2 mL/kg IV iodinated contrast (neonates/infants lower end).
   - 24G peripheral cannulae can be safely power-injected up to ~1.5 mL/s, ≤150 psi.
   - Extravasation rate ~0.3-0.7% (similar to adults); most resolve without sequelae.
   - Contrast reaction treatment algorithms and drug doses (weight-based) are the same protocol as adults with
     paediatric weight adjustments (see ACR Tables, Children chapter).

7. ACUTE CONTRAST REACTIONS — key doses (ACR Tables 2025):
   - Hives/urticaria (mild-moderate): Diphenhydramine 1 mg/kg PO/IM/IV (max 50 mg), IV slowly over 1-2 min.
   - Bronchospasm (mild): Albuterol MDI 2 puffs × up to 3.
   - Bronchospasm (moderate/severe) OR laryngeal oedema OR anaphylactic shock — EPINEPHRINE is first-line:
     * IV: 0.1 mL/kg of 1:10,000 (0.1 mg/mL) = 0.01 mg/kg slow IV into running drip; max single 1.0 mL (0.1 mg);
           repeat every 5-15 min; max total 1 mg.
     * IM: 0.01 mL/kg of 1:1,000 (1.0 mg/mL) = 0.01 mg/kg; max single 0.30 mL (0.30 mg); repeat every 5-15 min;
           max total 1 mL (1 mg).
     * Auto-injector: EpiPen Jr 0.15 mg (<30 kg), EpiPen 0.30 mg (≥30 kg).
   - Hypotension: 0.9% saline 10-20 mL/kg IV bolus (max 500-1000 mL initial), legs elevated; epinephrine if refractory.
   - O₂ 6-10 L/min by mask in all moderate/severe reactions.
   - Call emergency response team / 999 for all severe reactions.

8. BREAST-FEEDING AFTER IODINATED OR GBCA CONTRAST:
   - <0.01% of maternal IV iodinated contrast dose reaches breast milk; <1% of that is absorbed by the infant's gut.
   - <0.04% of maternal GBCA dose reaches breast milk; systemic infant dose <0.0004% of maternal dose.
   - Recommendation: BREAST-FEEDING CAN CONTINUE without interruption after maternal IV iodinated or GBCA contrast.
   - A 12-24 h pause is OPTIONAL at maternal preference only; there is no medical benefit beyond 24 h.
   - Routine neonatal thyroid function testing is NOT recommended after maternal iodinated contrast.

9. THYROID DISEASE:
   - Hyperthyroidism alone is NOT a contraindication to iodinated contrast and does NOT require premedication.
   - In acute thyroid storm, AVOID iodinated contrast (can potentiate thyrotoxicosis); steroid premedication is
     unlikely to help.
   - Before radioactive iodine therapy/imaging, observe a washout period after iodinated contrast: ~3-4 weeks for
     hyperthyroidism, ~6 weeks for hypothyroidism.
   - A single maternal dose of iodinated contrast in pregnancy has NO effect on neonatal thyroid function.
   - Iodinated contrast does NOT affect thyroid function tests in patients with normal thyroid function.

10. OBSOLETE / NON-RECOMMENDED PRACTICES (per ACR 2025):
    - N-acetylcysteine for CI-AKI prevention — NOT effective, NOT recommended.
    - Dose reduction of iodinated contrast in high-risk eGFR patients — NOT recommended (non-diagnostic scans).
    - Withholding metformin at eGFR ≥30 — NOT required.
    - Prophylactic premedication for shellfish/seafood allergy — NOT indicated.
    - Topical iodine (povidone-iodine) allergy — NOT cross-reactive with iodinated contrast.
    - Hyaluronidase for extravasation — NOT recommended.
    - Routine breast-milk pumping/discard after contrast — NOT required.
    - Volume thresholds (100-150 mL) as sole trigger for surgical extravasation review — NOT recommended.
"""
```

---

## Sections covered

1. Premedication (adult oral, adult IV accelerated, paediatric)
2. PC-AKI / CI-AKI eGFR thresholds and prophylaxis
3. Metformin Category I/II rules
4. GBCA Group I/II/III classification and NSF risk
5. Extravasation management and surgical consult criteria
6. Paediatric iodinated dosing
7. Acute reaction treatment (epinephrine, diphenhydramine, albuterol, fluids)
8. Breast-feeding recommendations
9. Thyroid disease (hyperthyroidism, storm, RAI washout, neonatal)
10. Explicit list of obsolete practices

## Where this is used

- **`templates/partials/_contrast_reaction_card.html`** — Contrast Reaction Card UI (6 tabs)
  surfaced in the vetting drawer, on `/contrast-reaction-card`, and as the body of clinical
  protocols #1 (Adult) and #11 (Paediatric).
- **`ai_vetting.py`** — appended to `_EVIDENCE_BLOCK` in both `ANALYSIS_SYSTEM_PROMPT` and
  `PROTOCOL_SYSTEM_PROMPT` so the vetting AI cites the same numbers as the visible card.

## Source provenance

- Primary: `ACR-Manual-on-Contrast-Media.pdf` (Jan 2025 edition, 122 pages).
- Thyroid section verified at `acr_manual_clean.txt` lines 240-253 (full cleaned manual,
  not committed to repo — re-extract from PDF if needed).
