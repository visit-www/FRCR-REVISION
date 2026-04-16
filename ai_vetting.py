"""
Vetting Tool AI Module — Clinical referral analysis and protocol generation.

Three functions:
1. generate_vetting_analysis() — parse referral, identify study, flag missing info
2. generate_vetting_protocol() — generate shorthand + detailed protocol (when no library match)
3. extract_shorthand() — extract consultant-style shorthand from detailed protocol text

Uses shared ai_client.call_claude() for API calls.
Model: Sonnet (default) — fast structured output for classification tasks.
"""

import logging

from ai_client import call_claude, parse_json_response, AIClientError

logger = logging.getLogger(__name__)


class VettingAIError(AIClientError):
    """Vetting-specific AI error."""
    pass


# ── Evidence-Based Reference (ACR / ESR / RCR) ───────────────────────
# Distilled from: ACR Manual on Contrast Media (2025), ACR Appropriateness
# Criteria (4000+ scenarios), ESR iGuide (1600+ indications, PMC6419665).
# Embedded in system prompts to ground AI vetting in authoritative guidelines.

_EVIDENCE_BLOCK = (
    "\n\nEVIDENCE-BASED GUIDELINES (ACR Manual 2025):\n"
    "1. Renal Safety (eGFR):\n"
    "- Screening required if: history of renal disease, surgery, transplant, single kidney, "
    "diabetes with complications, or nephrotoxic drugs.\n"
    "- eGFR >= 30: IV iodinated contrast is safe. eGFR 30-44: prophylaxis (0.9% Saline) "
    "may be considered selectively. eGFR < 30: High risk; use hydration if essential or "
    "seek non-contrast alternatives (US, non-contrast MRI).\n"
    "- N-acetylcysteine is NOT effective for contrast-induced AKI prevention. Do NOT reduce "
    "contrast dose in high-risk patients — use standard dose or choose non-contrast alternative.\n"
    "- Emergency (Stroke, PE, Trauma, Dissection): DO NOT DELAY imaging for eGFR. If eGFR "
    "unknown, proceed if results change immediate management.\n"
    "- Metformin: No need to withhold if eGFR >= 30. Withhold for 48h only if eGFR < 30, "
    "AKI, or intra-arterial study.\n"
    "2. Allergy & Pregnancy:\n"
    "- Allergy: Prior reaction to same contrast class requires premedication (13h oral "
    "prednisone protocol or accelerated IV steroid/diphenhydramine).\n"
    "- Pregnancy: Iodinated contrast acceptable if warranted. Avoid Gadolinium (GBCA) "
    "unless benefit significantly outweighs fetal risk. Breastfeeding: No need to interrupt.\n"
    "3. Appropriateness:\n"
    "- Score: Usually Appropriate (7-9), May Be Appropriate (4-6), Usually Not (1-3).\n"
    "- Use ALARA: Prioritise non-ionising (US/XR) unless urgency dictates CT/MRI.\n\n"
    "VETTING OUTPUT RULES (MANDATORY):\n"
    "- Always classify as: APPROVED / APPROVED WITH CONDITIONS / NOT APPROPRIATE.\n"
    "- Explicitly state status for: eGFR (Adequate/Low/Unknown/N/A), Allergy (Known/Unknown/N/A), "
    "and Pregnancy (Confirmed/Unknown/N/A).\n"
    "- If safety data missing in non-emergencies, list as 'REQUIRED BEFORE PROCEEDING'.\n"
    "- For non-contrast studies, mark eGFR and Allergy as 'Not applicable'.\n"
    "- In emergencies, proceed and provide clinical justification for bypassing safety checks.\n"
)


# ── Reference Layer Block (UK authoritative sources) ─────────────────
# Anchors the AI to published guidelines so it does not drift onto
# obsolete US/training-data practice (e.g. oral contrast for appendicitis).
# Four-layer framework distilled from docs/vetting/GUIDELINE_LAYER_MAP.md.

_REFERENCE_LAYER_BLOCK = (
    "\n\nREFERENCE LAYERS (UK PRACTICE — cite the layer your recommendation follows):\n"
    "1. NICE (what/when to scan):\n"
    "   - NG143 (renal/ureteric stones — non-contrast CT KUB first-line)\n"
    "   - NG12 (suspected cancer 2WW pathway)\n"
    "   - NG158 / NG179 (VTE / pulmonary embolism — Wells → D-dimer → CTPA)\n"
    "   - NG232 (stroke and TIA — immediate NCCT then CTA)\n"
    "   - NG45 (major trauma assessment)\n"
    "   - CG176 (head injury — NICE head CT criteria)\n"
    "   - NG41 (headaches in >12s)\n"
    "   - NG127 (suspected sepsis)\n"
    "2. RCR iRefer 8th Ed (2017) — general appropriateness across 800+ scenarios.\n"
    "3. RCR Major Adult Trauma Guidance 2024 — WBCT triage criteria & trauma protocol.\n"
    "4. IR(ME)R 2017 (justification & optimisation) + UKHSA National DRL 2022 "
    "(CT DLP reference levels per study).\n"
    "5. ACR Manual on Contrast Media 2025 — contrast safety (eGFR, allergy, pregnancy, premed).\n\n"
    "REFERENCE LAYER RULES:\n"
    "- Cite the specific layer and document you follow for each recommendation "
    "(e.g. 'NICE NG143 — non-contrast CT KUB').\n"
    "- Where a UK NICE or RCR document directly answers the question, PREFER it over ACR.\n"
    "- For protocol parameters (contrast volume, phases, delays), follow the internal "
    "protocol library served by the calling code. If no library match, cite the physiology "
    "principle (e.g. 'PV 70 s per standard abdominal CT physiology').\n"
    "- Do NOT invent document numbers or editions. If unsure of the exact NICE guideline "
    "number, cite the generic source ('NICE stroke guidance') rather than guess.\n"
    "- Do NOT recommend OBSOLETE practices. Examples of obsolete practice the AI must AVOID:\n"
    "  * Oral contrast is NOT used for acute appendicitis in current UK practice (IV contrast only).\n"
    "  * Oral contrast is NOT routinely used for acute abdominal pain CT in the ED.\n"
    "  * N-acetylcysteine is NOT recommended for contrast-induced AKI prevention.\n"
    "  * Contrast dose reduction is NOT recommended for high-risk eGFR patients — use standard dose "
    "or choose a non-contrast alternative.\n"
    "  * Metformin withholding is NOT required if eGFR >= 30.\n"
)


# ── ACR Contrast Block — authoritative numeric reference ─────────────
# Distilled from ACR Manual on Contrast Media (2025 ed., Jan 2025, 122 pp).
# Source of truth: docs/vetting/ACR_CONTRAST_BLOCK_2025.md — when that file
# is updated, copy the block below verbatim. Same numbers are surfaced in
# templates/partials/_contrast_reaction_card.html so the vetting AI and the
# visible Contrast Reaction Card never drift apart.

_ACR_CONTRAST_BLOCK = """

ACR MANUAL ON CONTRAST MEDIA (2025 ed.) — AUTHORITATIVE REFERENCE FOR CONTRAST SAFETY:

1. CORTICOSTEROID PREMEDICATION (prior allergic-like reaction to same class of contrast):
   A. Elective 12-13 h ORAL (either regimen):
      - Prednisone 50 mg PO at 13 h, 7 h, and 1 h pre-contrast + diphenhydramine 50 mg PO/IM/IV at 1 h; OR
      - Methylprednisolone 32 mg PO at 12 h and 2 h pre-contrast (+/- diphenhydramine 50 mg).
      If unable to take PO: substitute hydrocortisone 200 mg IV for each oral prednisone dose.
   B. Accelerated IV (urgent, 4-5 h duration, in decreasing order of preference):
      1. Methylprednisolone Na succinate (Solu-Medrol) 40 mg IV OR hydrocortisone Na succinate (Solu-Cortef)
         200 mg IV immediately, then every 4 h until contrast + diphenhydramine 50 mg IV 1 h pre-contrast.
      2. Dexamethasone Na sulfate (Decadron) 7.5 mg IV immediately, then every 4 h + diphenhydramine 50 mg IV 1 h pre.
      3. Same drugs each 1 h pre-contrast — <4 h regimens have NO evidence of efficacy; only in true emergencies.
   C. Paediatric:
      - Elective: Prednisone 0.5-0.7 mg/kg PO (max 50 mg) at 13/7/1 h + diphenhydramine 1.25 mg/kg PO (max 50 mg) at 1 h.
      - Urgent/ED/NPO: Hydrocortisone 2 mg/kg IV (max 200 mg) at 5 h and 1 h + diphenhydramine 1 mg/kg IV (max 50 mg) at 1 h.
   Premedication is NOT indicated for shellfish/seafood allergy, topical iodine allergy, asthma alone, or prior
   reaction to a different class of contrast. Cross-reactivity iodinated<->gadolinium is NOT established.

2. POST-CONTRAST AKI (PC-AKI) / CI-AKI — IV iodinated contrast:
   - Single evidence-based threshold: eGFR 30 mL/min/1.73m^2. Above 30 -> IV iodinated contrast is NOT an independent
     nephrotoxic risk factor (level 1 evidence, Davenport/McDonald/Hinson 2013-2014 propensity-matched studies).
   - eGFR 30-44: borderline, not statistically significant risk; give contrast if clinically indicated at STANDARD dose.
   - eGFR <30 or AKI: weigh risks and benefits; prophylactic IV 0.9% saline (periprocedural volume expansion) may be
     considered. NOT an absolute contraindication.
   - PROPHYLAXIS: IV 0.9% saline only. Sodium bicarbonate is no better than saline. N-acetylcysteine is NOT recommended
     (no efficacy). Diuretics/mannitol NOT recommended. DO NOT reduce contrast dose to mitigate risk — it produces
     non-diagnostic scans without changing CI-AKI risk.
   - Screening eGFR only required if: CKD, remote AKI, dialysis, kidney surgery/ablation, albuminuria, or metformin use
     (+/- diabetes mellitus as optional risk factor). Routine patients without risk factors do NOT need baseline creatinine.

3. METFORMIN (ACR Categories):
   - Category I (eGFR >=30 and no AKI): NO need to discontinue metformin before or after IV iodinated contrast,
     NO need to re-check renal function afterwards.
   - Category II (eGFR <30, AKI, OR intra-arterial study with potential renal artery embolisation): STOP metformin at
     time of procedure, withhold 48 h, restart only after renal function rechecked and confirmed normal.
   - Gadolinium at standard MRI dose (0.1-0.3 mmol/kg): no metformin interruption needed.

4. GADOLINIUM-BASED CONTRAST AGENTS (GBCA) & NSF RISK:
   - Group I (greatest NSF risk — contraindicated in eGFR <30/AKI/dialysis):
     Gadodiamide (Omniscan), Gadopentetate (Magnevist), Gadoversetamide (OptiMARK).
   - Group II (few/no unconfounded NSF cases — safe at standard dose in CKD/AKI/dialysis; screening eGFR is OPTIONAL):
     Gadobenate (MultiHance), Gadobutrol (Gadavist/Gadovist), Gadoteric acid (Dotarem/Clariscan),
     Gadoteridol (ProHance), Gadopiclenol (Elucirem/Vueway), Gadoxetate disodium (Eovist/Primovist).
   - Group III: no agents currently classified.
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
   - 24G peripheral cannulae can be safely power-injected up to ~1.5 mL/s, <=150 psi.
   - Extravasation rate ~0.3-0.7% (similar to adults); most resolve without sequelae.
   - Contrast reaction treatment algorithms and drug doses (weight-based) are the same protocol as adults with
     paediatric weight adjustments.

7. ACUTE CONTRAST REACTIONS — key doses (ACR Tables 2025):
   - Hives/urticaria (mild-moderate): Diphenhydramine 1 mg/kg PO/IM/IV (max 50 mg), IV slowly over 1-2 min.
   - Bronchospasm (mild): Albuterol MDI 2 puffs x up to 3.
   - Bronchospasm (moderate/severe) OR laryngeal oedema OR anaphylactic shock — EPINEPHRINE is first-line:
     * IV: 0.1 mL/kg of 1:10,000 (0.1 mg/mL) = 0.01 mg/kg slow IV into running drip; max single 1.0 mL (0.1 mg);
           repeat every 5-15 min; max total 1 mg.
     * IM: 0.01 mL/kg of 1:1,000 (1.0 mg/mL) = 0.01 mg/kg; max single 0.30 mL (0.30 mg); repeat every 5-15 min;
           max total 1 mL (1 mg).
     * Auto-injector: EpiPen Jr 0.15 mg (<30 kg), EpiPen 0.30 mg (>=30 kg).
   - Hypotension: 0.9% saline 10-20 mL/kg IV bolus (max 500-1000 mL initial), legs elevated; epinephrine if refractory.
   - O2 6-10 L/min by mask in all moderate/severe reactions.
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
    - Withholding metformin at eGFR >=30 — NOT required.
    - Prophylactic premedication for shellfish/seafood allergy — NOT indicated.
    - Topical iodine (povidone-iodine) allergy — NOT cross-reactive with iodinated contrast.
    - Hyaluronidase for extravasation — NOT recommended.
    - Routine breast-milk pumping/discard after contrast — NOT required.
    - Volume thresholds (100-150 mL) as sole trigger for surgical extravasation review — NOT recommended.
"""


# ── RCR Whole-Body CT Trauma Triage Block ────────────────────────────
# Distilled from the Royal College of Radiologists' Major Adult Trauma
# Guidance (2024). Used only in ANALYSIS_SYSTEM_PROMPT (indication-level
# vetting) — NOT in the protocol prompt where scanner parameters live.
# Purpose: give the AI the exact triage thresholds so it does not
# paraphrase or miss specific vital-sign cut-offs when advising WBCT.

_WBCT_CRITERIA_BLOCK = """

RCR MAJOR ADULT TRAUMA GUIDANCE 2024 — WHOLE-BODY CT (WBCT) TRIAGE CRITERIA:

A whole-body CT (head + cervical spine + thoracoabdominal + pelvis, usually with IV
contrast from the arch to the pubic symphysis) is indicated in major adult trauma when
ONE OR MORE of the following criteria are met. Cite this reference explicitly when
recommending or vetting WBCT for polytrauma.

1. HIGH-RISK MECHANISM (any one):
   - Fall from height > 3 metres
   - Pedestrian or cyclist struck by motor vehicle
   - Ejection from a vehicle
   - Death of another occupant in the same vehicle
   - Prolonged entrapment or extrication
   - Road traffic collision with significant intrusion, rollover, or high speed

2. APPARENT SIGNIFICANT INJURY (any one):
   - Injury to more than one body region (polytrauma)
   - Suspected pelvic fracture
   - Suspected major chest injury (flail chest, multiple rib fractures, haemo/pneumothorax)
   - Suspected abdominal injury (seat-belt sign, abdominal distension, peritonism)
   - Suspected spinal-cord injury or unstable spinal fracture
   - Severe head injury (GCS <= 13 after initial resuscitation)
   - Open long-bone fracture or amputation proximal to wrist or ankle
   - Burn > 20% BSA with associated trauma

3. ABNORMAL PHYSIOLOGY AFTER INITIAL RESUSCITATION (any one):
   - GCS < 14
   - Systolic BP < 90 mmHg
   - Respiratory rate < 10 or > 29 per minute
   - SaO2 < 93% on air
   - Heart rate > 120 bpm with signs of shock

RULES FOR THE AI:
- If ANY single criterion from ANY category is present, WBCT is indicated per RCR 2024.
- Haemodynamically unstable patients who cannot tolerate CT should be managed by
  damage-control surgery or IR per trauma team discretion — CT is NOT a substitute
  for resuscitation.
- Paediatric trauma does NOT follow this criteria set — use the separate paediatric
  major trauma pathway (APLS + RCEM).
- When quoting a criterion, cite 'RCR Major Adult Trauma Guidance 2024'.
"""


# ── System Prompts ─────────────────────────────────────────────────────

ANALYSIS_SYSTEM_PROMPT = (
    "You are a consultant radiologist vetting imaging requests in an NHS department. "
    "Your task is to analyse a clinical referral and extract structured information.\n\n"
    "RULES:\n"
    "- Understand the clinical context: what happened, the course of events, and what clinical question "
    "the referrer needs answered. If the course of events is unclear, do NOT assume or invent details. "
    "If the clinical context is ambiguous, flag it as an ai_flag item.\n"
    "- First identify the clinical question that needs addressing — derive this ONLY from the "
    "provided text, never from assumption.\n"
    "- Clean up the clinical text: fix typos, expand abbreviations (keep original meaning), "
    "standardise formatting. Do NOT alter clinical meaning.\n"
    "- Identify the most appropriate imaging study and modality to answer the clinical question "
    "inferred from the request.\n"
    "- If a specific imaging study has been explicitly mentioned in the clinical request:\n"
    "  - Critically analyse whether the requested study is reasonable based on current guidelines "
    "to answer the clinical question.\n"
    "  - If the explicitly requested study is optimum, accept it as the study to be performed.\n"
    "  - If the explicitly requested study is NOT optimum, suggest the best study that can answer "
    "the clinical question per current guidelines.\n"
    "  - Provide the rationale for accepting or overriding the imaging study requested in the referral.\n"
    "- Determine which baseline safety checks are needed based on the study type.\n"
    "- Flag 0-4 items of study-specific information that should be confirmed before proceeding.\n"
    "- UK NHS context. British English.\n"
    "- Be precise and concise.\n"
    "- FACTUAL ACCURACY: Do NOT fabricate dose thresholds, guideline criteria, "
    "or eGFR thresholds. If uncertain about a specific value, state the uncertainty. "
    "Only use values established in indexed medical literature or official guidelines.\n"
    + _EVIDENCE_BLOCK
    + _REFERENCE_LAYER_BLOCK
    + _ACR_CONTRAST_BLOCK
    + _WBCT_CRITERIA_BLOCK
)

PROTOCOL_SYSTEM_PROMPT = (
    "You are a consultant radiologist generating imaging protocols for an NHS department. "
    "Your task is to produce a complete imaging protocol for the specified study.\n\n"
    "RULES:\n"
    "- Shorthand: brief consultant vetting-box style (what goes on the request card). "
    "Include study name, coverage, contrast info, key phases. 2-4 lines max.\n"
    "Where studies have a special name, provide them in brackets along with the more generic "
    "name (e.g. 4D CT for parathyroid adenoma or Camp Bastion Protocol for trauma).\n"
    "- Detailed protocol: full technical specification as an HTML table. Include specific "
    "technical parameters (kVp, mAs, slice thickness, reconstruction kernels for CT; "
    "sequences, FOV, slice thickness for MRI) with a note 'Verify parameters for your department'.\n"
    "Include any medications to be given (e.g. Buscopan in gynaecological imaging) and their "
    "required safety checks.\n"
    "The detailed protocol should be in the format a radiographer would want as imaging protocol text.\n"
    "- Special notes: any important clinical considerations, e.g. timing, patient prep, "
    "contrast precautions. Only include if genuinely relevant.\n"
    "- Validation config: specify which safety checks the protocol requires. "
    "If any safety checks are needed, include them in the validation config.\n"
    "- UK NHS context. British English.\n"
    + _EVIDENCE_BLOCK
    + _REFERENCE_LAYER_BLOCK
    + _ACR_CONTRAST_BLOCK
)

SHORTHAND_SYSTEM_PROMPT = (
    "You are a consultant radiologist. Extract a brief consultant-style shorthand "
    "from the given protocol — the format a consultant radiologist would write in the "
    "vetting box on a request card. 2-4 lines: study name, coverage, contrast, key phases. "
    "No preamble."
)


def generate_vetting_analysis(referral_text, modality_hint=None, protocol_titles=None):
    """
    Analyse a clinical referral — clean text, identify study, flag missing info.

    Args:
        referral_text: Raw clinical referral text from the request form
        modality_hint: Optional modality hint from the user (CT, MRI, US, XR)

    Returns:
        dict: {cleaned_clinical_text, study_type, study_name_full, modality,
               baseline_checks, ai_flags, model, output_tokens}

    Raises:
        VettingAIError on validation or API failure
    """
    if not referral_text or not referral_text.strip():
        raise VettingAIError("Referral text cannot be empty.")

    hint_line = f"\nModality hint from referrer: {modality_hint}" if modality_hint else ""

    # Build protocol catalogue line if titles provided
    protocol_line = ""
    if protocol_titles:
        protocol_line = (
            "\nAVAILABLE PROTOCOL LIBRARY (slug → title):\n"
            + "\n".join(f"  {slug}: {title}" for slug, title in protocol_titles)
            + "\n"
        )

    user_prompt = (
        "Analyse this clinical referral and return a JSON object.\n\n"
        f"REFERRAL TEXT:\n{referral_text.strip()}\n"
        f"{hint_line}\n"
        f"{protocol_line}\n"
        "Return ONLY valid JSON with these fields:\n"
        "{\n"
        '  "cleaned_clinical_text": "cleaned version of the referral (fix formatting, '
        'expand abbreviations, preserve clinical meaning and original text). '
        'Format as separate short lines — one clinical fact/finding per line, '
        'separated by a single newline character \\n. Do NOT return one long paragraph. '
        'Example: \\"58M, known COPD\\n3/7 pleuritic chest pain\\nSOB, HR 110, SpO2 92% RA\\nWells 4.5, D-dimer positive\\n?PE\\"",\n'
        '  "study_type": "short study identifier e.g. CTPA, CT ABDOMEN PELVIS (CT AP), CT CAP, MRI BRAIN",\n'
        '  "study_name_special": "special study name e.g. 4D CT for parathyroid adenoma, Camp Bastion protocol",\n'
        '  "study_name_full": "full human-readable study name e.g. CT Pulmonary Angiography",\n'
        '  "modality": "CT or MRI or US or XR or NM or Fluoro",\n'
        '  "body_section": "one of: Thorax, Abdomen, Pelvis, Head and Neck, Brain, Spine, MSK, Cardiovascular, Breast, Multisystem (use Multisystem for e.g. CT CAP)",\n'
        '  "matched_protocol_slug": "slug of the BEST matching protocol from the AVAILABLE PROTOCOL LIBRARY above. Pick the most specific match for this clinical scenario. null if no library provided or no good match.",\n'
        '  "is_paediatric": true/false (true if patient age < 16 years, or described as child/infant/neonate/paediatric/toddler; false if adult, unknown age, or not stated),\n'
        '  "baseline_checks": {\n'
        '    "requires_egfr": true/false,\n'
        '    "egfr_threshold": 30 or 45 or null,\n'
        '    "pregnancy_check_required": true/false,\n'
        '    "allergy_check_required": true/false\n'
        '  },\n'
        '  "ai_flags": [\n'
        '    {"flag": "short description of missing/needed info", "reason": "why this matters"}\n'
        '  ],\n'
        '  "guideline_citation": "specific UK guideline layer and document anchoring '
        'this recommendation, e.g. NICE NG143 — non-contrast CT KUB first-line, or '
        'RCR iRefer 8th Ed — CTPA if Wells >4 + positive D-dimer. Use null only if '
        'no named guideline applies.",\n'
        '  "verifiable_claims": [\n'
        '    {"claim": "The specific factual assertion (e.g. eGFR threshold, dose limit, guideline criterion)", '
        '"type": "threshold|guideline|dose|measurement", '
        '"search_terms": "PubMed search terms to verify this claim"}\n'
        "  ]\n"
        "}\n\n"
        "GUIDELINES FOR ai_flags (0-4 items only):\n"
        "- Flag genuinely important missing clinical information for the specific study.\n"
        "- Examples: Wells score for ?PE, GCS/onset time for stroke, tumour markers for staging.\n"
        "- Do NOT flag generic items like 'clinical history' if already provided.\n"
        "- Do NOT flag items that are administrative (e.g. patient weight unless contrast-relevant).\n"
    )

    text, model_used, tokens = call_claude(
        system_prompt=ANALYSIS_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=1500,
        temperature=0.1,
        timeout=30,
        error_class=VettingAIError,
        skip_preamble=True,
    )

    result = parse_json_response(text, error_class=VettingAIError)

    # Validate required fields
    for field in ('cleaned_clinical_text', 'study_type', 'modality'):
        if not result.get(field):
            raise VettingAIError(f"AI response missing required field: {field}")

    result['model'] = model_used
    result['output_tokens'] = tokens

    logger.info("Vetting analysis complete: study=%s modality=%s model=%s tokens=%d",
                result.get('study_type'), result.get('modality'), model_used, tokens)

    return result


def generate_vetting_protocol(study_type, modality, clinical_context=None, algorithm_context=None):
    """
    Generate an imaging protocol when no library match exists.

    Args:
        study_type: Study identifier from analysis step (e.g. CTPA)
        modality: CT, MRI, US, XR, etc.
        clinical_context: Optional clinical context for tailoring the protocol
        algorithm_context: Optional algorithm pathway text from VettingAlgorithm.to_ai_context()

    Returns:
        dict: {shorthand, detailed_protocol_html, special_notes, validation,
               model, output_tokens}

    Raises:
        VettingAIError on validation or API failure
    """
    if not study_type:
        raise VettingAIError("Study type is required.")

    context_line = f"\nClinical context: {clinical_context}" if clinical_context else ""
    algorithm_line = ""
    if algorithm_context:
        algorithm_line = (
            f"\n\nCLINICAL ALGORITHM (guideline-based pathway):\n"
            f"{algorithm_context}\n"
            f"Follow this pathway to guide protocol recommendation."
        )

    user_prompt = (
        f"Generate a complete imaging protocol for: {study_type} ({modality})\n"
        f"{context_line}{algorithm_line}\n\n"
        "Return ONLY valid JSON with these fields:\n"
        "{\n"
        '  "shorthand": "Consultant vetting-box shorthand (2-4 lines).\\n'
        'Example for CTPA: CTPA\\nChest — diaphragm to apices\\nIV contrast, PA phase\\nBolus tracking aorta",\n'
        '  "detailed_protocol_html": "<table class=\'table table-sm vetting-protocol-table\'>'
        '<thead><tr><th>Parameter</th><th>Value</th></tr></thead><tbody>...</tbody></table>'
        '<p class=\'text-muted small mt-2\'><em>Verify parameters for your department.</em></p>",\n'
        '  "special_notes": "Any important clinical notes (patient prep, timing, contrast precautions). '
        'null if none relevant.",\n'
        '  "validation": {\n'
        '    "requires_egfr": true/false,\n'
        '    "egfr_threshold": 30 or 45 or null,\n'
        '    "pregnancy_check_required": true/false,\n'
        '    "allergy_check_required": true/false\n'
        '  },\n'
        '  "guideline_citation": "specific UK guideline layer and document anchoring '
        'this protocol, e.g. NICE NG143 — non-contrast CT KUB first-line, or '
        'Swansea NHS Trust CT protocol library — standard triphasic liver. Use null '
        'only if no named guideline applies."\n'
        "}\n\n"
        "SHORTHAND STYLE EXAMPLES:\n"
        "CT Head: CT Brain / Non-contrast / Skull base to vertex\n"
        "CT CAP: CT Chest Abdomen Pelvis / IV contrast / Portal venous phase / "
        "Thoracic inlet to symphysis pubis\n"
        "MRI Brain: MRI Brain / Axial T1, T2, FLAIR, DWI / Sag T1 / +Gd if indicated\n\n"
        "DETAILED PROTOCOL: Use an HTML table with Parameter and Value columns. "
        "Include modality-specific technical parameters.\n"
        "For CT: kVp, mAs/dose modulation, slice thickness, reconstruction kernel, "
        "contrast volume, injection rate, scan delay/phases, coverage.\n"
        "For MRI: sequences (with plane), FOV, slice thickness, contrast agent, "
        "special prep.\n"
    )

    text, model_used, tokens = call_claude(
        system_prompt=PROTOCOL_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=2500,
        temperature=0.1,
        timeout=45,
        error_class=VettingAIError,
        skip_preamble=True,
    )

    result = parse_json_response(text, error_class=VettingAIError)

    if not result.get('shorthand'):
        raise VettingAIError("AI response missing protocol shorthand.")

    result['model'] = model_used
    result['output_tokens'] = tokens

    logger.info("Vetting protocol generated: study=%s modality=%s tokens=%d",
                study_type, modality, tokens)

    return result


def extract_shorthand(detailed_protocol_text):
    """
    Extract consultant-style shorthand from detailed protocol text.
    Used during batch import of protocols.

    Args:
        detailed_protocol_text: Full protocol text (plain text or HTML)

    Returns:
        str: Shorthand text (2-4 lines)

    Raises:
        VettingAIError on failure
    """
    if not detailed_protocol_text or not detailed_protocol_text.strip():
        raise VettingAIError("Protocol text cannot be empty.")

    user_prompt = (
        "Extract a consultant-style vetting shorthand from this protocol.\n"
        "Return ONLY the shorthand text (2-4 lines, no JSON, no explanation).\n\n"
        f"PROTOCOL:\n{detailed_protocol_text.strip()}\n"
    )

    text, model_used, tokens = call_claude(
        system_prompt=SHORTHAND_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=200,
        temperature=0.1,
        timeout=20,
        error_class=VettingAIError,
        skip_preamble=True,
    )

    logger.info("Shorthand extracted: model=%s tokens=%d", model_used, tokens)
    return text.strip()
