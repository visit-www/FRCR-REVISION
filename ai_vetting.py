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
    + _EVIDENCE_BLOCK
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
)

SHORTHAND_SYSTEM_PROMPT = (
    "You are a consultant radiologist. Extract a brief consultant-style shorthand "
    "from the given protocol — the format a consultant radiologist would write in the "
    "vetting box on a request card. 2-4 lines: study name, coverage, contrast, key phases. "
    "No preamble."
)


def generate_vetting_analysis(referral_text, modality_hint=None):
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

    user_prompt = (
        "Analyse this clinical referral and return a JSON object.\n\n"
        f"REFERRAL TEXT:\n{referral_text.strip()}\n"
        f"{hint_line}\n\n"
        "Return ONLY valid JSON with these fields:\n"
        "{\n"
        '  "cleaned_clinical_text": "cleaned version of the referral (fix formatting, '
        'expand abbreviations, preserve clinical meaning and original text)",\n'
        '  "study_type": "short study identifier e.g. CTPA, CT ABDOMEN PELVIS (CT AP), CT CAP, MRI BRAIN",\n'
        '  "study_name_special": "special study name e.g. 4D CT for parathyroid adenoma, Camp Bastion protocol",\n'
        '  "study_name_full": "full human-readable study name e.g. CT Pulmonary Angiography",\n'
        '  "modality": "CT or MRI or US or XR or NM or Fluoro",\n'
        '  "body_section": "one of: Thorax, Abdomen, Pelvis, Head and Neck, Brain, Spine, MSK, Cardiovascular, Breast, Multisystem (use Multisystem for e.g. CT CAP)",\n'
        '  "baseline_checks": {\n'
        '    "requires_egfr": true/false,\n'
        '    "egfr_threshold": 30 or 45 or null,\n'
        '    "pregnancy_check_required": true/false,\n'
        '    "allergy_check_required": true/false\n'
        '  },\n'
        '  "ai_flags": [\n'
        '    {"flag": "short description of missing/needed info", "reason": "why this matters"}\n'
        '  ]\n'
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
        max_tokens=800,
        temperature=0.2,
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
        '  }\n'
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
        max_tokens=1500,
        temperature=0.2,
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
