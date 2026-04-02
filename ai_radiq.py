"""
RadIQ AI Module — Consultant-level intelligence for radiologists.

Handles GP replies, complaint responses, incident reports, radiographer
requests, and general clinical queries.
Uses shared ai_client.call_claude() for API calls.

Architecture:
- radiographer/general: Model outputs JSON → format_json_to_html() converts
  to styled HTML. JSON forces structured reasoning (answer before title)
  and eliminates premature commitment bias.
- gp_reply/complaint/incident: Model outputs HTML directly. These categories
  have complex structured formats (Datix forms, formal letters) where the
  structure IS the content.

Model: Sonnet (default) — best balance of quality, speed, and cost for
structured clinical advisory.
"""

import re
import logging

from ai_client import call_claude, parse_json_response, AIClientError

logger = logging.getLogger(__name__)


class RadIQError(AIClientError):
    """RadIQ-specific AI error."""
    pass


RADIQ_CATEGORIES = {
    'gp_reply', 'complaint', 'incident',
    'radiographer', 'general',
}

# Categories where model outputs plain markdown (post-processed to HTML)
MARKDOWN_CATEGORIES = {'radiographer', 'general'}

# ── Category emoji map ────────────────────────────────────────────────
CATEGORY_EMOJI = {
    'gp_reply': '&#128233;',       # 📩
    'complaint': '&#128737;',      # 🛡
    'incident': '&#9888;',         # ⚠
    'radiographer': '&#128161;',   # 💡
    'general': '&#129504;',        # 🧠
}

# Python unicode for markdown post-processor
_CATEGORY_EMOJI_UNICODE = {
    'gp_reply': '\U0001f4e9',
    'complaint': '\U0001f6e1',
    'incident': '\U000026a0',
    'radiographer': '\U0001f4a1',
    'general': '\U0001f9e0',
}


# ── System Prompt ─────────────────────────────────────────────────────
# skip_preamble=True for all — ABC preamble's BREVITY instruction harms
# clinical Q&A accuracy by forcing oversimplification.

RADIQ_SYSTEM_PROMPT = (
    "You are RadIQ, an expert consultant radiologist working in the UK NHS. "
    "You provide authoritative, evidence-based clinical advice.\n\n"

    "ACCURACY IS YOUR TOP PRIORITY. Every clinical claim must be correct. "
    "If uncertain, say so — never present a guess as fact.\n\n"

    "RULES:\n"
    "- UK NHS context. British English.\n"
    "- Authoritative consultant tone. No generic AI language "
    "('Certainly!', 'Great question!', 'I'd be happy to help').\n"
    "- Do not include patient-identifiable information.\n"
    "- If imaging is not indicated, explain why.\n"
    "- If the query is ambiguous, state your assumptions.\n"
    "- For contrast agents or drugs: specify the exact agent, class "
    "(ionic/non-ionic), osmolality, and route. Distinguish between agents "
    "precisely — they are not interchangeable.\n"
    "- For named protocols (Fleischner, Bosniak, LI-RADS, PI-RADS, etc): "
    "give actual criteria and thresholds, not paraphrased summaries.\n"
    "- Prioritise: ACR Appropriateness Criteria, ACR Manual on Contrast "
    "Media, ESR iGuide, RCR iRefer.\n"
    "- If relevant RadInsights database content is provided, incorporate it.\n"
    "- If the query is not related to radiology, imaging, or clinical practice, "
    "return ONLY: {\"off_topic\": true} — nothing else.\n\n"

    "REFERENCES:\n"
    "- Cite real, specific publications: Organisation/Author, Title, Year.\n"
    "- NEVER fabricate references. If you cannot confidently recall the "
    "exact citation, omit it. Fewer real references are always better "
    "than fabricated ones.\n"
)


# ── Category-specific task instructions ───────────────────────────────

# Minimal HTML preamble for categories that output HTML directly.
# Much shorter than the old 30-line formatting section in the system prompt.
_HTML_FORMAT = (
    "OUTPUT: Valid HTML. Begin with <h5 class='radiq-title'>{emoji} Clean Title</h5>. "
    "Use <h5> for section headings. Do NOT use <mark> or highlights. "
    "References section: use <ul><li> for each reference (no URLs needed).\n\n"
)

CATEGORY_PROMPTS = {
    'gp_reply': (
        _HTML_FORMAT +
        "TASK: Draft a formal reply letter to a GP referral or clinical query.\n"
        "STYLE: Professional letter format.\n\n"
        "SECTION STRUCTURE (use these exact <h5> headings in order):\n"
        "1. <h5>Indication</h5> — One-line restatement of the referral query.\n"
        "2. <h5>Draft Letter</h5> — Wrap in <div class='radiq-suggested-response'>. "
        "Write a complete, copy-ready reply letter:\n"
        "   - 'Dear Dr [Referring Clinician],' opening\n"
        "   - Acknowledgement of referral and clinical context\n"
        "   - Imaging findings summary with clinical significance\n"
        "   - Clear recommendation for follow-up, further imaging, or management\n"
        "   - Courteous sign-off: 'Yours sincerely, [Consultant Radiologist]'\n"
        "3. <h5>References</h5> — 2-4 guideline-level references.\n"
    ),
    'complaint': (
        _HTML_FORMAT +
        "TASK: Help draft a response to a patient or clinical complaint.\n"
        "STYLE: Empathetic, factual, non-adversarial. NHS duty of candour.\n\n"
        "SECTION STRUCTURE (use these exact <h5> headings in order):\n"
        "1. <h5>Summary of Complaint</h5> — Brief restatement of the complaint.\n"
        "2. <h5>Draft Response Letter</h5> — Wrap in <div class='radiq-suggested-response'>. "
        "Full draft complaint response:\n"
        "   - Acknowledge the concern with empathy\n"
        "   - Explain the radiological process clearly in lay terms where needed\n"
        "   - Address specific points raised factually and without defensiveness\n"
        "   - Professional, non-adversarial tone. Goal: rebuild trust while being honest.\n"
        "3. <h5>Lessons &amp; Actions</h5> — Actions taken or proposed to prevent recurrence.\n"
        "4. <h5>References</h5> — 2-4 guideline-level references.\n"
    ),
    'incident': (
        _HTML_FORMAT +
        "TASK: Generate a complete Datix-style radiology incident/adverse event report.\n"
        "STYLE: Structured, objective, non-judgmental, factual — suitable for electronic "
        "incident reporting systems (Datix, Riskman, Ulysses). Focus on learning and system "
        "improvement, never individual blame.\n\n"
        "PLACEHOLDERS: For any details the user has NOT provided, insert clearly marked "
        "placeholders in square brackets, e.g. [Patient Initials], [Hospital Number], "
        "[Date of Incident], [Cannula Size e.g. 20G]. NEVER invent patient details.\n\n"
        "SECTION STRUCTURE (use these exact <h5> headings in order):\n\n"
        "1. <h5>Incident Details</h5>\n"
        "   Present as a definition list (<dl>):\n"
        "   - <strong>Incident Type:</strong> Clinical Incident / Treatment\n"
        "   - <strong>Sub-Category:</strong> e.g. Extravasation, Missed Finding, "
        "Wrong Patient, Contrast Reaction, Equipment Failure\n"
        "   - <strong>Date of Incident:</strong> [Date of Incident]\n"
        "   - <strong>Time of Incident:</strong> [Time of Incident]\n"
        "   - <strong>Location:</strong> [Location]\n"
        "   - <strong>Severity of Harm:</strong> No Harm / Low / Moderate / Severe / Death\n"
        "   - <strong>Was the Patient Informed?</strong> [Yes/No]\n\n"
        "2. <h5>Incident Description</h5>\n"
        "   - <strong>Context:</strong> What procedure was being performed\n"
        "   - <strong>Incident:</strong> Factual, chronological account\n"
        "   - <strong>Observation:</strong> Clinical findings at the time\n\n"
        "3. <h5>Action Taken</h5>\n"
        "   - <strong>Immediate Action:</strong>\n"
        "   - <strong>Patient Management:</strong> Evidence-based interventions\n"
        "   - <strong>Escalation:</strong> Who was informed and when\n"
        "   - <strong>Follow-up:</strong> Observation period, outcome\n\n"
        "4. <h5>Documentation &amp; Reporting</h5>\n\n"
        "5. <h5>Root Cause / Contributing Factors</h5>\n"
        "   Checklist of systemic factors (☐ / ☑).\n\n"
        "6. <h5>Recommendations</h5> — Wrap in <div class='radiq-suggested-response'>.\n"
        "   Actionable steps to prevent recurrence.\n\n"
        "7. <h5>Key Elements Checklist</h5> — Audit validity items as ☐ items.\n\n"
        "8. <h5>References</h5> — 2-4 relevant guidelines (RCR, NPSA, NHS Improvement, ACR).\n"
    ),
    'radiographer': (
        "TASK: Answer this query.\n"
        "TONE: Practical, direct, conversational — like a quick corridor chat. "
        "Briefly explain WHY. Use 'you' and 'we' naturally.\n\n"
        "Return ONLY valid JSON with these fields IN THIS ORDER:\n"
        "{\n"
        '  "answer": "Your practical answer. Use plain text with '
        "paragraph breaks (\\\\n\\\\n). Be thorough on safety-critical points "
        "but keep the tone conversational.\",\n"
        '  "key_points": ["2-5 critical practical takeaways"],\n'
        '  "references": [\n'
        '    {"text": "Author/Org, Title, Year", "known_source": "acr_contrast_manual or rcr_irefer or acr_ac or null"}\n'
        "  ],\n"
        '  "title": "Clean professional title for the query"\n'
        "}\n\n"
        "IMPORTANT: Write the answer field FIRST, title field LAST.\n"
    ),
    'general': (
        "TASK: Answer this query.\n\n"
        "Return ONLY valid JSON with these fields IN THIS ORDER:\n"
        "{\n"
        '  "indication": "One-line restatement of the query",\n'
        '  "rationale": "Clinical rationale — high-yield explanation. Focus on WHY.",\n'
        '  "recommendation": "Clear, actionable guidance.",\n'
        '  "key_points": ["2-5 critical clinical points to highlight"],\n'
        '  "references": [\n'
        '    {"text": "Author/Org, Title, Year", "known_source": "acr_contrast_manual or rcr_irefer or acr_ac or null"}\n'
        "  ],\n"
        '  "title": "Clean professional title for the query"\n'
        "}\n\n"
        "IMPORTANT: Write fields in the order shown. Title LAST.\n"
    ),
}


# ── Known reference URLs (verified, never hallucinated) ───────────────
# Post-processor auto-links these. Model never sees URLs in its prompt.

_REFERENCE_URLS = {
    # ACR resources — match on organisation name, not topic keywords
    'acr appropriateness criteria': 'https://www.acr.org/Clinical-Resources/ACR-Appropriateness-Criteria',
    'acr manual on contrast media': 'https://www.acr.org/Clinical-Resources/Contrast-Manual',
    'acr contrast manual': 'https://www.acr.org/Clinical-Resources/Contrast-Manual',
    'acr ac portal': 'https://acsearch.acr.org/list',
    'acr manual on mr safety': 'https://www.acr.org/Clinical-Resources/Radiology-Safety/MR-Safety',
    'acr mr safety': 'https://www.acr.org/Clinical-Resources/Radiology-Safety/MR-Safety',
    # UK guidelines
    'rcr irefer': 'https://www.irefer.org.uk/',
    'irefer': 'https://www.irefer.org.uk/',
    'nice': 'https://www.nice.org.uk/guidance',
    'nhs improvement': 'https://www.england.nhs.uk/patient-safety/',
    'npsa': 'https://www.england.nhs.uk/patient-safety/',
    # Radiology resources
    'radiopaedia': 'https://radiopaedia.org/',
    'radiology assistant': 'https://radiologyassistant.nl/',
    'fleischner society': 'https://fleischner.org/',
    'esur guidelines': 'https://www.esur.org/esur-guidelines/',
    'esur contrast media': 'https://www.esur.org/esur-guidelines/',
    'shellock': 'http://www.mrisafety.com/',
    # NOTE: Classification names (Bosniak, LI-RADS, PI-RADS etc.) deliberately
    # excluded — they match topic keywords in paper titles, causing wrong links.
    # Those references fall through to Google Scholar instead.
}


# ── Post-processor: JSON → Styled HTML ────────────────────────────────
# Only used for MARKDOWN_CATEGORIES (radiographer, general).

def format_json_to_html(data, category='general'):
    """
    Convert model's JSON output to styled HTML for the RadIQ frontend.

    For 'radiographer': title + answer + key_points + references
    For 'general': title + indication + rationale + recommendation + key_points + references
    """
    if not data or not isinstance(data, dict):
        return ''

    emoji = _CATEGORY_EMOJI_UNICODE.get(category, '')
    parts = []

    # Title
    title = data.get('title', 'Response')
    parts.append(
        f"<h5 class='radiq-title'>{emoji} {_esc(title)}</h5>" if emoji
        else f"<h5 class='radiq-title'>{_esc(title)}</h5>"
    )

    key_points = data.get('key_points', [])

    if category == 'general':
        if data.get('indication'):
            parts.append("<h5>Indication</h5>")
            parts.append(f"<p>{_esc(data['indication'])}</p>")
        if data.get('rationale'):
            parts.append("<h5>Clinical Rationale</h5>")
            parts.append(_text_to_html(data['rationale']))
        if data.get('recommendation'):
            parts.append("<h5>Recommendation</h5>")
            parts.append("<div class='radiq-suggested-response'>")
            parts.append(_text_to_html(data['recommendation']))
            parts.append("</div>")
    else:
        if data.get('answer'):
            parts.append("<h5>Answer</h5>")
            parts.append("<div class='radiq-suggested-response'>")
            parts.append(_text_to_html(data['answer']))
            parts.append("</div>")

    # Key points — teal left-border card
    if key_points:
        parts.append("<div class='radiq-key-points-card'>")
        parts.append("<h5>Key Points</h5>")
        parts.append("<ul>")
        for kp in key_points:
            parts.append(f"<li>{_esc(kp)}</li>")
        parts.append("</ul>")
        parts.append("</div>")

    # References
    refs = data.get('references', [])
    if refs:
        parts.append(f"<h5>References</h5>")
        parts.append("<ul>")
        for ref in refs:
            if isinstance(ref, dict):
                ref_text = _esc(ref.get('text', ''))
                source = ref.get('known_source', '') or ''
                url = _SOURCE_TO_URL.get(source)
                if url:
                    parts.append(
                        f"<li><a href='{url}' target='_blank' "
                        f"rel='noopener noreferrer'>{ref_text}</a></li>"
                    )
                else:
                    # Try keyword matching as fallback
                    linked = _linkify_reference(ref_text)
                    parts.append(f"<li>{linked}</li>")
            else:
                linked = _linkify_reference(_esc(str(ref)))
                parts.append(f"<li>{linked}</li>")
        parts.append("</ul>")

    return '\n'.join(parts)


# ── Source key → URL mapping ──────────────────────────────────────────
_SOURCE_TO_URL = {
    'acr_contrast_manual': 'https://www.acr.org/Clinical-Resources/Contrast-Manual',
    'acr_contrast': 'https://www.acr.org/Clinical-Resources/Contrast-Manual',
    'acr_ac': 'https://www.acr.org/Clinical-Resources/ACR-Appropriateness-Criteria',
    'acr_appropriateness': 'https://www.acr.org/Clinical-Resources/ACR-Appropriateness-Criteria',
    'rcr_irefer': 'https://www.irefer.org.uk/',
    'irefer': 'https://www.irefer.org.uk/',
    'nice': 'https://www.nice.org.uk/guidance',
    'radiopaedia': 'https://radiopaedia.org/',
    'fleischner': 'https://fleischner.org/',
    'esur': 'https://www.esur.org/esur-guidelines/',
    'nhs_improvement': 'https://www.england.nhs.uk/patient-safety/',
}


def _linkify_reference(text):
    """Auto-link known sources by keyword, fall back to Google Scholar search."""
    text_lower = text.lower()
    for keyword, url in _REFERENCE_URLS.items():
        if keyword in text_lower:
            return (
                f"<a href='{url}' target='_blank' "
                f"rel='noopener noreferrer'>{text}</a>"
            )
    # Fallback: Google Scholar search with quoted title for exact match
    from urllib.parse import quote_plus
    scholar_url = f"https://scholar.google.com/scholar?q=%22{quote_plus(text)}%22"
    return (
        f"<a href='{scholar_url}' target='_blank' "
        f"rel='noopener noreferrer'>{text}</a>"
    )


def _linkify_html_references(html):
    """Auto-link plain-text references in HTML output (gp_reply, complaint, incident).

    Finds <li> items that don't already contain <a> tags and applies
    the same keyword → known URL / Google Scholar fallback logic.
    """
    def _replace_li(match):
        inner = match.group(1)
        if '<a ' in inner:
            return match.group(0)  # already linked
        linked = _linkify_reference(inner)
        return f'<li>{linked}</li>'

    return re.sub(r'<li>((?:(?!</li>).)+)</li>', _replace_li, html)


def _fix_letter_formatting(html):
    """Convert bare newlines inside radiq-suggested-response divs to <br> tags.

    The model outputs letters with plain newlines. CSS white-space:pre-line
    displays them, but copy-paste loses them. Converting to <br> ensures
    formatting survives in Word/Docs/email.
    """
    def _convert(match):
        content = match.group(1)
        content = content.replace('\n\n', '<br><br>')
        content = content.replace('\n', '<br>')
        return f"<div class='radiq-suggested-response'>{content}</div>"

    return re.sub(
        r"<div class='radiq-suggested-response'>(.*?)</div>",
        _convert, html, flags=re.DOTALL,
    )


def _esc(text):
    """Escape HTML entities in text."""
    return (text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _text_to_html(text):
    """Convert plain text with paragraph breaks to HTML paragraphs."""
    if not text:
        return ''

    paragraphs = re.split(r'\n\n+', text.strip())
    parts = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        lines = para.split('\n')
        if all(l.strip().startswith(('- ', '* ')) for l in lines if l.strip()):
            parts.append('<ul>')
            for line in lines:
                item = line.strip().lstrip('-* ').strip()
                parts.append(f'<li>{_esc(item)}</li>')
            parts.append('</ul>')
        elif all(re.match(r'^\d+\.', l.strip()) for l in lines if l.strip()):
            parts.append('<ul>')
            for line in lines:
                item = re.sub(r'^\d+\.\s*', '', line.strip())
                parts.append(f'<li>{_esc(item)}</li>')
            parts.append('</ul>')
        else:
            parts.append(f'<p>{_esc(para.replace(chr(10), " "))}</p>')

    return '\n'.join(parts)


# ── Main generation function ──────────────────────────────────────────

def generate_radiq_response(question, category, db_context=''):
    """
    Generate a RadIQ AI response.

    Args:
        question: The user's clinical query text
        category: One of RADIQ_CATEGORIES
        db_context: Optional string of relevant DB content to include in prompt

    Returns:
        dict: {html, model, output_tokens}

    Raises:
        RadIQError on validation or API failure
    """
    if category not in RADIQ_CATEGORIES:
        raise RadIQError(f"Invalid category: {category}")

    if not question or not question.strip():
        raise RadIQError("Question cannot be empty.")

    # Build category prompt — HTML categories get emoji inserted into format preamble
    category_instruction = CATEGORY_PROMPTS.get(category, CATEGORY_PROMPTS['general'])
    if category not in MARKDOWN_CATEGORIES:
        emoji = CATEGORY_EMOJI.get(category, '')
        category_instruction = category_instruction.replace('{emoji}', emoji)

    user_prompt = (
        f"{category_instruction}\n"
        f"QUERY:\n{question.strip()}\n"
    )

    if db_context:
        user_prompt += (
            f"\nRELEVANT RADINSIGHTS CONTENT:\n{db_context}\n"
        )

    text, model_used, tokens = call_claude(
        system_prompt=RADIQ_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=3000,
        temperature=0.15,
        timeout=60,
        error_class=RadIQError,
        skip_preamble=True,
    )

    # Check for off-topic short-circuit (any category)
    if '"off_topic"' in text and 'true' in text:
        html = ("<p><strong>This query is outside the scope of RadIQ.</strong> "
                "Please ask radiology, imaging, or clinical practice related questions.</p>")
        logger.info("RadIQ off-topic query detected, category=%s", category)
        return {'html': html, 'model': model_used, 'output_tokens': tokens}

    # JSON categories: parse structured output → styled HTML
    # HTML categories: return model output as-is
    if category in MARKDOWN_CATEGORIES:
        try:
            data = parse_json_response(text, error_class=RadIQError)
            html = format_json_to_html(data, category=category)
        except (RadIQError, Exception) as exc:
            logger.warning("JSON parse failed for RadIQ %s, using raw text: %s",
                           category, exc)
            html = f"<div class='radiq-suggested-response'>{_esc(text)}</div>"
    else:
        html = _linkify_html_references(text)
        html = _fix_letter_formatting(html)

    logger.info("RadIQ response generated: category=%s model=%s tokens=%d",
                category, model_used, tokens)

    return {
        'html': html,
        'model': model_used,
        'output_tokens': tokens,
    }
