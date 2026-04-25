"""
Vetting Tool AI Module — Clinical referral analysis and advisory.

Single function:
1. generate_vetting_analysis() — parse referral, identify study, flag missing info

Protocol library removed Apr 2026 — AI analysis now handles study identification,
contrast detection, and safety checks directly without a stored protocol catalogue.

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

5. THYROID DISEASE:
   - Hyperthyroidism alone is NOT a contraindication to iodinated contrast and does NOT require premedication.
   - In acute thyroid storm, AVOID iodinated contrast (can potentiate thyrotoxicosis); steroid premedication is
     unlikely to help.
   - Before radioactive iodine therapy/imaging, observe a washout period after iodinated contrast: ~3-4 weeks for
     hyperthyroidism, ~6 weeks for hypothyroidism.
   - A single maternal dose of iodinated contrast in pregnancy has NO effect on neonatal thyroid function.
   - Iodinated contrast does NOT affect thyroid function tests in patients with normal thyroid function.

6. OBSOLETE / NON-RECOMMENDED PRACTICES (per ACR 2025):
    - N-acetylcysteine for CI-AKI prevention — NOT effective, NOT recommended.
    - Dose reduction of iodinated contrast in high-risk eGFR patients — NOT recommended (non-diagnostic scans).
    - Withholding metformin at eGFR >=30 — NOT required.
    - Prophylactic premedication for shellfish/seafood allergy — NOT indicated.
    - Topical iodine (povidone-iodine) allergy — NOT cross-reactive with iodinated contrast.
"""


# ── RCR Whole-Body CT Trauma Triage Block ────────────────────────────

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


# ── System Prompt ─────────────────────────────────────────────────────

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


# ── Quick Clean (lightweight) ────────────────────────────────────────

_QUICK_CLEAN_SYSTEM = (
    "You are a consultant radiologist. Clean up a clinical referral: "
    "fix typos, expand abbreviations, standardise formatting, identify the study. "
    "UK NHS context. British English. Return ONLY valid JSON."
)


def _quick_clean_analysis(referral_text, modality_hint=None):
    """Lightweight analysis — text cleanup + study identification only.

    Skips guideline blocks and evidence references
    to keep the prompt small and fast (~500 tokens vs ~8000).
    """
    hint_line = ""
    if modality_hint:
        hint_line = f"\nModality selected by referrer: {modality_hint}. Use this modality.\n"

    user_prompt = (
        "Clean this clinical referral and return JSON.\n\n"
        f"REFERRAL TEXT:\n{referral_text.strip()}\n{hint_line}\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        '  "cleaned_clinical_text": "cleaned version — one clinical fact per line, '
        'separated by \\n. Fix typos, expand abbreviations, preserve meaning.",\n'
        '  "study_type": "short study identifier e.g. CTPA, CT AP, MRI BRAIN",\n'
        '  "study_name_full": "full name e.g. CT Pulmonary Angiography",\n'
        '  "modality": "CT or MRI or US or XR or NM or Fluoro",\n'
        '  "body_section": "one of: Thorax, Abdomen, Pelvis, Head and Neck, Brain, Spine, MSK, Cardiovascular, Breast, Multisystem",\n'
        '  "contrast": "none or iv",\n'
        '  "is_paediatric": false,\n'
        '  "baseline_checks": {"requires_egfr": false, "pregnancy_check_required": false, "allergy_check_required": false, "metformin_check_required": false},\n'
        '  "ai_flags": []\n'
        "}\n"
    )

    text, model_used, tokens = call_claude(
        system_prompt=_QUICK_CLEAN_SYSTEM,
        user_prompt=user_prompt,
        max_tokens=800,
        temperature=0.1,
        timeout=20,
        error_class=VettingAIError,
        skip_preamble=True,
    )

    result = parse_json_response(text, error_class=VettingAIError)

    for field in ('cleaned_clinical_text', 'study_type', 'modality'):
        if not result.get(field):
            raise VettingAIError(f"AI response missing required field: {field}")

    result['model'] = model_used
    result['output_tokens'] = tokens

    logger.info("Quick clean complete: study=%s modality=%s tokens=%d",
                result.get('study_type'), result.get('modality'), tokens)

    return result


# ── Full Vetting Analysis ─────────────────────────────────────────────

def generate_vetting_analysis(referral_text, modality_hint=None, quick_clean=False):
    """
    Analyse a clinical referral — clean text, identify study, flag missing info.

    Args:
        referral_text: Raw clinical referral text from the request form
        modality_hint: Optional modality hint from the user (CT, MRI, US, XR)
        quick_clean: If True, use a lightweight prompt (text cleanup only)

    Returns:
        dict: {cleaned_clinical_text, study_type, study_name_full, modality,
               baseline_checks, ai_flags, model, output_tokens}

    Raises:
        VettingAIError on validation or API failure
    """
    if not referral_text or not referral_text.strip():
        raise VettingAIError("Referral text cannot be empty.")

    # ── Quick clean: lightweight prompt, no guideline blocks ──
    if quick_clean:
        return _quick_clean_analysis(referral_text, modality_hint)

    hint_line = ""
    if modality_hint:
        hint_line = (
            f"\nModality SELECTED by referrer: {modality_hint}. "
            "You MUST use this modality for study_type. "
            "If a different modality would be more appropriate, note this in ai_flags "
            "but still return the selected modality."
        )

    user_prompt = (
        "Analyse this clinical referral and return a JSON object.\n\n"
        f"REFERRAL TEXT:\n{referral_text.strip()}\n"
        f"{hint_line}\n"
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
        '  "contrast": "none or iv — whether this study requires IV contrast based on the clinical indication",\n'
        '  "is_paediatric": true/false (true if patient age < 16 years, or described as child/infant/neonate/paediatric/toddler; false if adult, unknown age, or not stated),\n'
        '  "baseline_checks": {\n'
        '    "requires_egfr": true/false,\n'
        '    "egfr_threshold": 30 or 45 or null,\n'
        '    "pregnancy_check_required": true/false,\n'
        '    "allergy_check_required": true/false,\n'
        '    "metformin_check_required": true/false (true if IV contrast AND patient on metformin or diabetic)\n'
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
        "GUIDELINES FOR ai_flags:\n"
        "- A flag is ONLY valid if the radiologist would need clarification BEFORE approving "
        "the imaging request.\n"
        "- MAXIMUM 3 flags. Each flag must represent ONE DISTINCT clinical decision gap. "
        "Do NOT split closely related missing details into separate flags.\n"
        "- Return [] if the referral contains sufficient information.\n"
        "- Include a flag ONLY if the missing information would directly affect: "
        "(a) imaging modality selection, (b) contrast/phase decisions, "
        "(c) anatomical coverage/extent, or (d) urgency/triage.\n"
        "- PRIORITISATION — select ONLY the highest-impact gaps in this order: "
        "1. Modality decisions, 2. Contrast/phase decisions, "
        "3. Coverage/extent decisions, 4. Urgency.\n"
        "- If more than 3 valid gaps exist, include the TOP 3 only.\n"
        "- Each flag must be specific, actionable, and non-overlapping.\n"
        "- DO NOT include: safety checks (eGFR, pregnancy, allergy, contrast reactions, "
        "medications) — handled separately; generic completeness statements; "
        "information already present; administrative/logistical details.\n"
        "- OUTPUT STYLE: concise statement with brief rationale.\n"
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
