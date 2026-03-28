"""
RadIQ AI Module — Consultant-level intelligence for radiologists.

Handles GP replies, complaint responses, incident reports, radiographer
requests, imaging protocol advice, and general clinical queries.
Uses shared ai_client.call_claude() for API calls.
"""

import logging

from ai_client import call_claude, AIClientError

logger = logging.getLogger(__name__)


class RadIQError(AIClientError):
    """RadIQ-specific AI error."""
    pass


RADIQ_CATEGORIES = {
    'gp_reply', 'complaint', 'incident',
    'radiographer', 'imaging_protocol', 'general',
}

RADIQ_SYSTEM_PROMPT = (
    "You are RadIQ, an expert UK consultant radiologist assistant embedded in "
    "the RadInsights platform. You help radiologists with real-world clinical "
    "and professional queries.\n\n"
    "OUTPUT FORMAT — always use this HTML structure:\n"
    "<h5>Summary</h5>\n<p>One-paragraph executive summary.</p>\n"
    "<h5>Key Points</h5>\n<ul><li>Bullet points of the most important considerations.</li></ul>\n"
    "<h5>Suggested Response</h5>\n<div class='radiq-suggested-response'>The draft text the radiologist can adapt.</div>\n"
    "<h5>Clinical Justification</h5>\n<p>Evidence-based reasoning supporting the advice.</p>\n"
    "<h5>References & Guidelines</h5>\n<ul><li>Cite relevant RCR, NICE, ACR, or other guidelines where applicable.</li></ul>\n\n"
    "PRINCIPLES:\n"
    "- Be professional, defensible, and concise.\n"
    "- UK NHS context by default (but note if advice differs internationally).\n"
    "- Never fabricate guideline references — cite real ones or say 'based on general consensus'.\n"
    "- Use appropriate medical terminology but remain clear.\n"
    "- If the query is ambiguous, state your assumptions clearly.\n"
    "- All output must be valid HTML (no markdown).\n"
)

CATEGORY_PROMPTS = {
    'gp_reply': (
        "TASK: Draft a formal reply letter to a GP referral or query.\n"
        "STYLE: Professional letter format. Start with 'Dear Dr [Referring Clinician],'.\n"
        "Include: acknowledgement of referral, imaging findings summary, "
        "clinical significance, recommended follow-up or further imaging, "
        "and a courteous sign-off with 'Yours sincerely, [Consultant Radiologist]'.\n"
        "The suggested response section should contain the full draft letter.\n"
    ),
    'complaint': (
        "TASK: Help draft a response to a patient or clinical complaint.\n"
        "STYLE: Empathetic, factual, and structured. Acknowledge the concern, "
        "explain the radiological process clearly, address specific points raised, "
        "and outline any actions taken or proposed.\n"
        "Follow the NHS duty of candour principles where applicable.\n"
        "The suggested response should be a draft complaint response letter.\n"
    ),
    'incident': (
        "TASK: Help structure a radiology incident/adverse event report.\n"
        "STYLE: Datix-style structured incident report.\n"
        "Include: incident description, patient impact assessment, "
        "contributing factors, immediate actions taken, root cause analysis, "
        "lessons learned, and recommendations to prevent recurrence.\n"
        "Use objective, non-judgmental language throughout.\n"
    ),
    'radiographer': (
        "TASK: Respond to a radiographer's clinical or protocol query.\n"
        "STYLE: Collegial, technically precise, and educational.\n"
        "Provide clinical justification for imaging decisions, protocol "
        "modifications, or technique guidance. Reference IR(ME)R regulations "
        "where relevant. Explain the clinical reasoning so the radiographer "
        "understands the 'why' behind the guidance.\n"
    ),
    'imaging_protocol': (
        "TASK: Provide imaging protocol advice.\n"
        "STYLE: Structured technical guidance.\n"
        "Cover: modality choice and justification, contrast administration "
        "(type, volume, rate, timing), specific sequences or phases, "
        "patient preparation, radiation dose considerations (ALARA), "
        "and any contraindications or precautions.\n"
        "Reference relevant RCR iRefer guidelines where applicable.\n"
    ),
    'general': (
        "TASK: Provide balanced clinical advisory on a radiology question.\n"
        "STYLE: Evidence-based, balanced, and practical.\n"
        "Consider the question from multiple angles, provide the most "
        "defensible position, and note any areas of controversy or "
        "variation in practice.\n"
    ),
}


def generate_radiq_response(question, category):
    """
    Generate a RadIQ AI response.

    Args:
        question: The user's clinical query text
        category: One of RADIQ_CATEGORIES

    Returns:
        str: HTML-formatted response

    Raises:
        RadIQError on validation or API failure
    """
    if category not in RADIQ_CATEGORIES:
        raise RadIQError(f"Invalid category: {category}")

    if not question or not question.strip():
        raise RadIQError("Question cannot be empty.")

    category_instruction = CATEGORY_PROMPTS.get(category, CATEGORY_PROMPTS['general'])

    user_prompt = (
        f"{category_instruction}\n"
        f"QUERY:\n{question.strip()}\n\n"
        "Respond using the HTML format described in your system prompt."
    )

    text, model_used, tokens = call_claude(
        system_prompt=RADIQ_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=3000,
        temperature=0.3,
        timeout=60,
        error_class=RadIQError,
    )

    logger.info("RadIQ response generated: category=%s model=%s tokens=%d",
                category, model_used, tokens)

    return text
