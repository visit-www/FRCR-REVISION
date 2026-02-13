"""
AI Smart Reporter Module (Revised)

Generates structured algorithm trees for interactive scan reading walkthrough,
provides unified AI assist for report editing, intent classification for routing,
anatomy references, and blank template generation.

CHANGELOG from original:
────────────────────────────────────────────────────────────────
1. DRY: Extracted shared API call boilerplate into _call_claude() helper
   - Eliminates ~150 lines of duplicated request/error-handling code
   - Single place to update headers, timeout logic, error messages

2. PROMPTS FIXED:
   - Fixed typos: "subspeciality" → "subspecialty", "whihc ocpy" → "which is copy",
     "Consistense" → "Consistency", missing period after "demographic factors in mind"
   - TREE_PROMPT: Added resource injection slot, improved sub-step branching rules,
     added explicit normal-variant handling, tightened report_text quality bar
   - UNIFIED_ASSIST: Better handling of empty reports (Gap 2 paste flow),
     added resource context injection (Gap 1), clarified PACS-ready output rules
   - QUICK_REVIEW: Added instruction to preserve section headings

3. PLAN ALIGNMENT — NEW FUNCTIONS:
   - classify_intent()         → Haiku-based intent router (Phase 3)
   - generate_anatomy_reference() → Anatomy panel content (Phase 5)
   - generate_blank_template()    → Structured empty template for abort flow (Gap 3)
   - format_resources_for_prompt() → Resource injection for Gap 1

4. COST OPTIMISATION:
   - generate_algorithm_tree: max_tokens 10000 → 6000 (trees rarely exceed 4k tokens)
   - classify_intent: Uses Haiku (~0.25$/M input) with max_tokens=500
   - generate_blank_template: Uses Haiku, max_tokens=1500
   - generate_anatomy_reference: Uses Haiku, max_tokens=1000
   - quick_review: Already Haiku ✓
   - unified_ai_assist: Stays on Sonnet (quality-critical) ✓
   - ask_claude_about_report: Marked as DEPRECATED, kept for backward compat

5. RESOURCE-AWARE GENERATION (Gap 1):
   - generate_algorithm_tree() now accepts optional `resources` dict
   - format_resources_for_prompt() converts URLs, DB refs, PDF text, TNM data
     into a structured prompt section injected before the JSON schema
   - If no resources provided, AI uses own knowledge (unchanged behaviour)

6. QUALITY IMPROVEMENTS:
   - Tree generation: Added rule for normal variants that mimic pathology
   - Tree generation: Added measurement thresholds where applicable
   - Unified assist: Better empty-report handling for paste-first workflow
   - Unified assist: Explicit instruction not to hallucinate image findings
   - JSON parsing: More robust fallback with detailed error logging
────────────────────────────────────────────────────────────────
"""

import json
import os
import re
import logging

import requests

logger = logging.getLogger(__name__)


class SmartReporterError(Exception):
    """Raised when Smart Reporter generation fails."""
    pass


# ==================== SHARED API HELPER ====================

def _call_claude(system_prompt, user_prompt, model=None, max_tokens=4000,
                 temperature=0.3, timeout=60):
    """
    Shared helper for all Claude API calls.
    Eliminates duplicated request/error-handling boilerplate.

    Args:
        system_prompt: System message string
        user_prompt: User message string
        model: Override model (defaults to CLAUDE_MODEL env var)
        max_tokens: Max response tokens
        temperature: Sampling temperature
        timeout: Request timeout in seconds

    Returns:
        tuple: (response_text: str, model_used: str, token_count: int)

    Raises:
        SmartReporterError on any failure
    """
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise SmartReporterError("RadInsight Intelligence API key not configured.")

    effective_model = model or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    payload = {
        "model": effective_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json=payload,
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        raise SmartReporterError("Request timed out. Please try again.")
    except requests.exceptions.RequestException as exc:
        raise SmartReporterError(f"Failed to connect to RadInsight Intelligence: {exc}")

    if response.status_code >= 300:
        detail = response.text[:500]
        raise SmartReporterError(
            f"RadInsight Intelligence error (HTTP {response.status_code}): {detail}"
        )

    result = response.json()
    content = result.get("content", [])
    if not content:
        raise SmartReporterError("Empty response from RadInsight Intelligence.")

    text = content[0].get("text", "").strip()
    if not text:
        raise SmartReporterError("No text in RadInsight Intelligence response.")

    token_count = result.get("usage", {}).get("output_tokens", 0)
    return text, effective_model, token_count


def _parse_json_response(text):
    """
    Shared JSON parser with markdown fence stripping and regex fallback.

    Returns parsed dict or raises SmartReporterError.
    """
    cleaned = text.strip()

    # Strip markdown code fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: find the outermost JSON object
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                logger.warning("JSON fallback parse also failed. Raw text: %s", cleaned[:500])
                raise SmartReporterError("Failed to parse AI response as JSON.")
        raise SmartReporterError("AI response was not valid JSON.")


# ==================== RESOURCE FORMATTING (Gap 1) ====================

def format_resources_for_prompt(resources):
    """
    Convert user-supplied resources into a structured prompt section.

    Args:
        resources: dict with optional keys:
            - urls: list of reference article URLs
            - db_refs: list of {type: 'if'|'rt'|'protocol'|'tnm', slug: str, content: str}
            - pdf_texts: list of {filename: str, text: str}
            - tnm_refs: list of {system: str, content: str}

    Returns:
        str: Formatted prompt section, or empty string if no resources
    """
    if not resources or not isinstance(resources, dict):
        return ""

    sections = []

    # Reference URLs (fetch content)
    urls = resources.get('urls', [])
    if urls:
        from clinical_tool_generator import fetch_url_content
        url_parts = []
        for u in urls:
            if not u:
                continue
            fetched = fetch_url_content(u)
            if fetched:
                url_parts.append(f"  - {u}\n    Content:\n    {fetched[:4000]}")
            else:
                url_parts.append(f"  - {u}")
        if url_parts:
            sections.append("REFERENCE ARTICLES (use these as evidence sources):\n" + "\n".join(url_parts))

    # Database references (pre-fetched content from IF calcs, templates, protocols)
    db_refs = resources.get('db_refs', [])
    if db_refs:
        ref_parts = []
        type_labels = {
            'if': 'Incidental Findings Calculator',
            'rt': 'Reporting Template',
            'protocol': 'Clinical Protocol',
            'tnm': 'TNM Staging System',
        }
        for ref in db_refs:
            if not isinstance(ref, dict):
                continue
            label = type_labels.get(ref.get('type', ''), ref.get('type', 'Reference'))
            content = ref.get('content', '')
            slug = ref.get('slug', '')
            if content:
                ref_parts.append(f"  [{label}: {slug}]\n  {content[:3000]}")
        if ref_parts:
            sections.append(
                "EXISTING DATABASE CONTENT (incorporate into your output):\n"
                + "\n\n".join(ref_parts)
            )

    # TNM staging data
    tnm_refs = resources.get('tnm_refs', [])
    if tnm_refs:
        tnm_parts = []
        for ref in tnm_refs:
            if isinstance(ref, dict) and ref.get('content'):
                tnm_parts.append(f"  [{ref.get('system', 'TNM')}]\n  {ref['content'][:2000]}")
        if tnm_parts:
            sections.append(
                "TNM STAGING DATA (use for staging-related steps):\n"
                + "\n\n".join(tnm_parts)
            )

    # Uploaded PDF text
    pdf_texts = resources.get('pdf_texts', [])
    if pdf_texts:
        pdf_parts = []
        for pdf in pdf_texts:
            if isinstance(pdf, dict) and pdf.get('text'):
                fname = pdf.get('filename', 'uploaded document')
                # Truncate long PDFs to stay within token budget
                pdf_parts.append(f"  [PDF: {fname}]\n  {pdf['text'][:4000]}")
        if pdf_parts:
            sections.append(
                "UPLOADED REFERENCE DOCUMENTS (use as evidence):\n"
                + "\n\n".join(pdf_parts)
            )

    if not sections:
        return ""

    return (
        "\n\n═══ REFERENCE MATERIALS PROVIDED ═══\n"
        "Use the following references to ground your output in evidence. "
        "Where references conflict with general knowledge, prefer the references. "
        "If references are incomplete for certain steps, supplement with your own knowledge.\n\n"
        + "\n\n".join(sections)
        + "\n═══ END REFERENCES ═══\n\n"
    )


# ==================== SYSTEM PROMPTS ====================

TREE_SYSTEM_PROMPT = (
    "You are a consultant radiologist with extensive daily subspecialty radiology reporting experience. "
    "You generate structured algorithm decision trees for systematic scan reading. "
    "Your trees reflect real-world reading order, not textbook chapter order. "
    "Output valid JSON only. No markdown fences. No text outside the JSON object."
)

ASK_CLAUDE_SYSTEM_PROMPT = (
    "You are a consultant radiologist reviewing a trainee's draft radiology report. "
    "Answer their question concisely using standard radiology phrasing. "
    "While responding, keep the entire report findings, clinical context, and patient demographic factors in mind. "
    "If suggesting report text, make it ready to paste directly into a PACS report. "
    "Keep answers under 200 words. Plain text only — no markdown or HTML."
)

REVIEW_REPORT_SYSTEM_PROMPT = (
    "You are a consultant radiologist reviewing a trainee's draft PACS report. "
    "You check for spelling, grammar, radiology phrasing conventions, and structural completeness. "
    "Output valid JSON only. No markdown fences. No text outside the JSON object."
)

# ---- Quick Check (Layer 0): Lightweight proofreading only ----

QUICK_REVIEW_SYSTEM_PROMPT = (
    "You are a medical text proofreader specialising in radiology PACS reports. "
    "Fix spelling (including radiology-specific terms), grammar, and phrasing. "
    "Do NOT assess clinical content, do NOT add findings, do NOT change meaning. "
    "Output valid JSON only. No markdown fences. No text outside the JSON object."
)

QUICK_REVIEW_PROMPT = """Proofread this PACS report for spelling, grammar, and phrasing only.

DRAFT REPORT:
---
{report_text}
---

Return a JSON object with this EXACT structure:

{{
  "improved_report": "Full corrected report text with all suggestions applied.",
  "suggestions": [
    {{
      "original": "exact original phrase from the report",
      "suggested": "corrected phrase",
      "reason": "Brief explanation (5-10 words)",
      "type": "spelling|grammar|phrasing"
    }}
  ]
}}

RULES:
1. Fix genuine spelling errors, including radiology-specific terms (e.g. "referral thyroid" → "retrosternal thyroid", "heptaic" → "hepatic").
2. Fix grammar errors.
3. Improve phrasing to match standard radiology conventions (e.g. "There is no evidence of" → "No evidence of", "The liver appears normal" → "The liver is unremarkable").
4. Preserve all section headings (INDICATION, TECHNIQUE, FINDINGS, IMPRESSION, etc.) exactly as they appear.
5. Do NOT assess clinical correctness. Do NOT add content. Do NOT change clinical meaning.
6. Each suggestion must quote the EXACT original text so the frontend can locate it.
7. Max 10 suggestions. Prioritise: spelling > grammar > phrasing.
8. If the report is already well-written, return an empty suggestions array and the original text as improved_report.

Output ONLY the JSON object. No markdown. No explanation."""

# ---- Unified AI Assist (Layers 1+2+3): Corrections + Answer + Insights ----

UNIFIED_ASSIST_SYSTEM_PROMPT = (
    "You are an expert subspecialty consultant radiologist mentoring a trainee at "
    "the PACS workstation. You review their draft report, answer their question, "
    "and provide clinical quality assessment.\n\n"
    "Your persona:\n"
    "- Correct without condescension — just fix it, don't lecture\n"
    "- Give actionable report text ready to paste into PACS\n"
    "- Flag clinically important gaps the referring clinician would notice\n"
    "- Teach through the report — brief rationale when suggesting additions\n"
    "- NEVER add findings the trainee didn't describe — the images aren't available to you\n"
    "- NEVER fabricate or hallucinate imaging findings\n\n"
    "Output valid JSON only. No markdown fences. No text outside the JSON object."
)

UNIFIED_ASSIST_PROMPT = """You are reviewing a trainee's draft PACS report and answering their question.

CLINICAL CONTEXT:
- Clinical question: {clinical_question}
- Modality: {modality}
- Body section: {body_section}

DRAFT REPORT:
---
{report_text}
---

TRAINEE'S QUESTION: {question}
{resource_section}
Return a JSON object with EXACTLY this structure:

{{
  "corrections": [
    {{
      "original": "exact phrase from the report",
      "suggested": "corrected/improved phrase",
      "reason": "Brief explanation (5-10 words)",
      "type": "terminology|gender_check|anatomy_check|consistency|phrasing|sidedness"
    }}
  ],
  "answer": "Direct answer to the trainee's question. PACS-ready text where applicable. No preamble, no commentary on the report beyond what was asked. Copy-paste ready.",
  "insights": {{
    "clinical_question_coverage": "Does the report adequately address the referring clinician's question? 1-2 sentences.",
    "quality_assessment": "Would a subspecialist consultant be satisfied with this report? What would they want added or changed? 1-2 sentences.",
    "differentials_to_consider": ["Differential 1 to consider", "Differential 2"],
    "recommendation_check": "Are the recommendations appropriate and complete? 1 sentence.",
    "teaching_point": "One brief clinical pearl relevant to this report. 1-2 sentences."
  }}
}}

RULES FOR CORRECTIONS:
1. Focus on radiology-specific terminology (e.g. "hepatic hemangioma" not "liver hemangioma", "retrosternal" not "referral").
2. Cross-check gender/anatomy: if clinical context mentions female patient, flag prostate references; if male, flag uterine references.
3. Check section consistency: impression must not mention findings absent from the FINDINGS section, and vice versa.
4. Each correction must quote EXACT original text so the frontend can locate it.
5. Consistency in sidedness: e.g. if clinical details say "right sided pain abdomen" but report says "left iliac fossa diverticulitis", flag this sidedness inconsistency.
6. Max 8 corrections. Prioritise clinically significant errors over stylistic ones.
7. If the report has no issues, return an empty corrections array.
8. If the report is empty or very short, return empty corrections and note this in quality_assessment.

RULES FOR ANSWER:
1. Write as a consultant would dictate at a workstation. No hedging beyond standard conventions.
2. If the trainee asks for specific report text (e.g. "write the impression"), give complete PACS-ready sentences. Do NOT wrap in quotes or add labels.
3. Keep the answer under 250 words. Plain text only — no markdown, no HTML, no bullet lists.
4. If the trainee asks a knowledge question (e.g. "what's the differential?"), answer directly and concisely.
5. Do NOT add commentary about the report quality or your reasoning — only answer the question asked.

RULES FOR INSIGHTS:
1. Be specific and actionable, not generic platitudes.
2. differentials_to_consider: only list if genuinely relevant and not already covered in the report. Empty array if not applicable.
3. teaching_point: one actionable pearl, not a textbook paragraph. Relevant to this specific report.
4. If the report is excellent, say so — do not invent criticisms.
5. If the report is empty or too short for meaningful assessment, say so briefly in quality_assessment and leave other insight fields minimal.

Output ONLY the JSON object. No markdown. No explanation."""

REVIEW_REPORT_PROMPT = """Review this draft PACS report for spelling, grammar, radiology phrasing, and structure.

DRAFT REPORT:
---
{report_text}
---

Return a JSON object with this EXACT structure:

{{
  "improved_report": "The full corrected report text with all suggestions applied. Preserve the user's section headings (INDICATION, TECHNIQUE, etc.) exactly as they appear. If the report has no headings, add appropriate ones.",
  "suggestions": [
    {{
      "original": "the exact original phrase from the report",
      "suggested": "the corrected/improved phrase",
      "reason": "Brief explanation (5-10 words)",
      "type": "spelling|grammar|phrasing|structure|completeness"
    }}
  ]
}}

RULES:
1. Fix genuine spelling and grammar errors.
2. Improve phrasing to match standard radiology reporting conventions (e.g. "There is no evidence of" → "No evidence of", "The liver appears normal" → "The liver is unremarkable").
3. Suggest structural improvements if sections are missing or out of standard order.
4. Do NOT change clinical meaning. Do NOT add findings the user did not describe.
5. Do NOT remove any content the user wrote — only rephrase for clarity and convention.
6. If the report is already well-written, return an empty suggestions array and the original text as improved_report.
7. Each suggestion must quote the EXACT original text so the frontend can locate it.
8. Limit to the most impactful 15 suggestions maximum. Prioritise: spelling > grammar > phrasing > structure.
9. For completeness type: suggest if standard sections (INDICATION, TECHNIQUE, COMPARISON, FINDINGS, IMPRESSION) are missing.

Output ONLY the JSON object. No markdown. No explanation."""


# ==================== TREE GENERATION PROMPT ====================

TREE_PROMPT_TEMPLATE = """You are generating a structured algorithm tree that guides a radiology trainee
through reading a {modality} scan step by step.

CLINICAL QUESTION: {clinical_question}
MODALITY: {modality}
BODY SECTION: {body_section}
{resource_section}
The algorithm tree is a JSON object with this EXACT structure:

{{
  "steps": [
    {{
      "id": "step_1",
      "organ": "Organ or anatomical structure being assessed",
      "question": "What are you looking for at this step?",
      "options": [
        {{
          "label": "Short description of finding (what user clicks)",
          "report_text": "Complete sentence for the PACS report if this option is selected.",
          "next_step": "step_2",
          "findings_flag": "normal"
        }}
      ],
      "allow_multiple": false
    }}
  ],
  "lines_tubes_step": {{
    "id": "lines_tubes",
    "organ": "Lines and devices",
    "question": "Are there any lines, tubes, or surgical devices?",
    "options": [
      {{
        "label": "No lines or tubes",
        "report_text": "No lines, tubes, or surgical devices are identified.",
        "findings_flag": "normal"
      }},
      {{
        "label": "Endotracheal tube",
        "report_text": "An endotracheal tube is present with the tip projected approximately 3 cm above the carina.",
        "findings_flag": "normal"
      }}
    ],
    "allow_multiple": true
  }},
  "incidental_findings_step": {{
    "id": "incidentals",
    "organ": "Incidental findings",
    "question": "Any incidental findings to note?",
    "options": [
      {{
        "label": "No incidental findings",
        "report_text": "",
        "findings_flag": "normal"
      }},
      {{
        "label": "Simple renal cyst",
        "report_text": "Incidental note is made of a simple renal cyst.",
        "findings_flag": "incidental"
      }},
      {{
        "label": "Other (free text)",
        "report_text": "",
        "findings_flag": "incidental",
        "is_free_text": true
      }}
    ],
    "allow_multiple": true
  }},
  "report_template": {{
    "indication": "Clinical indication text derived from the question",
    "technique": "Specific technique description for this modality and body region",
    "comparison": "No prior available for comparison.",
    "impression_normal": "Summary impression if all findings are normal",
    "impression_abnormal": "Summary impression template referencing the key abnormal findings",
    "recommendation": "Standard follow-up recommendation if applicable"
  }}
}}

RULES:
1. Generate 8-15 steps covering the systematic scan reading order for this modality and clinical question.
2. Every step must assess ONE anatomical structure or compartment.
3. Steps must follow the actual order a radiologist reads the scan (not textbook order).
   For example, CT abdomen with clinical question about appendicitis:
   start with the appendix (target organ), then systematically cover remaining bowel,
   solid organs, vasculature, peritoneum, bones, soft tissues.
4. Each option's report_text must be a complete, standalone PACS-ready sentence.
   Write as a radiologist would in a formal report — use standard conventions.
   Include specific measurements or thresholds where applicable
   (e.g. "aortic diameter measures X cm" rather than just "aortic dilatation").
5. Use next_step for conditional branching:
   - If a finding is abnormal, next_step should point to a sub-step that characterises it further
     (e.g. abnormal liver → sub-step asking about number, segment, enhancement pattern).
   - If a finding is normal, next_step should be null (engine advances sequentially).
   - Sub-steps for characterisation should eventually rejoin the main sequence via next_step.
6. Include both normal and abnormal options for EVERY step. The normal option should always be first.
7. For normal options, include common normal variants that mimic pathology where relevant
   (e.g. "Prominent peri-portal cuffing — likely normal variant" for liver, or
   "Prominent hilar lymph nodes, within normal limits" for chest).
8. Each step should have 3-6 options (including one free-text option for unusual findings).
9. The last option in each step should be a free-text entry:
   {{"label": "Other (free text)", "report_text": "", "findings_flag": "abnormal", "is_free_text": true}}
10. lines_tubes_step should have 5-8 common options relevant to this modality and body region.
11. incidental_findings_step should have 4-6 common incidental findings for this body region.
12. report_template.indication must include the modality and clinical question.
13. report_template.technique should be specific to this modality (e.g., include contrast phase for CT,
    sequences for MRI, probe frequency for US).
14. Do NOT include pathophysiology, epidemiology, or teaching content in report_text.
15. findings_flag values: "normal", "abnormal", "equivocal", "incidental"

Output ONLY the JSON object. No markdown. No explanation."""


# ==================== INTENT CLASSIFIER (Phase 3) ====================

CLASSIFY_INTENT_SYSTEM_PROMPT = (
    "You classify radiology workstation queries into intent categories. "
    "Output valid JSON only. No markdown. No text outside the JSON object."
)

CLASSIFY_INTENT_PROMPT = """Classify this radiology user query into an intent category.

USER QUERY: {user_input}

Return a JSON object:
{{
  "intent": "walkthrough|report_help|tool_request|reference|protocol|anatomy|paste_report",
  "canonical_topic": "lowercase-hyphenated-slug",
  "display_title": "Human Readable Title",
  "modality": "CT|MRI|US|XR|NM|PET-CT|Fluoroscopy|null",
  "body_section": "Head|Neck|Chest|Abdomen|Pelvis|MSK|Spine|Vascular|Whole Body|null",
  "category": "emergency|oncology|vascular|msk|neuro|general|paediatric|null"
}}

INTENT DEFINITIONS:
- walkthrough: User wants step-by-step guidance reading a scan (e.g. "CT abdomen pancreatitis", "MRI brain headache", "rule out PE")
- report_help: User wants help with an existing report (e.g. "check my report", "write the impression", "fix spelling")
- tool_request: User wants a specific scoring/classification tool (e.g. "Li-RADS", "Bosniak classification", "PI-RADS scoring")
- reference: User wants reference material about a topic (e.g. "Fleischner criteria", "adrenal washout protocol")
- protocol: User wants imaging protocol information (e.g. "CT angiography protocol", "MRI liver protocol")
- anatomy: User wants anatomical reference (e.g. "Circle of Willis anatomy", "brachial plexus")
- paste_report: User indicates they have a report to paste (e.g. "I have a report", "paste my report", "review my report")

CANONICAL TOPIC:
- Normalise to the underlying clinical entity, not the user's exact words
- "Pain in RIF" → "right-iliac-fossa-pain"
- "Rule out PE" → "pulmonary-embolism"
- "CT abdomen, known pancreatic mass" → "pancreatic-mass-staging"
- "CT abdomen" (no clinical context) → "ct-abdomen-systematic"
- "Li-RADS scoring" → "li-rads"

Output ONLY the JSON object."""


def classify_intent(user_input):
    """
    Classify user input into an intent category for routing.
    Uses Haiku for speed and cost efficiency (~200ms, minimal cost).

    Args:
        user_input: Raw text from the Smart Reporter search bar

    Returns:
        dict with: intent, canonical_topic, display_title, modality, body_section, category
    """
    haiku_model = os.getenv("CLAUDE_QUICK_MODEL", "claude-haiku-4-5-20251001")

    prompt = CLASSIFY_INTENT_PROMPT.format(user_input=user_input)

    text, model, tokens = _call_claude(
        system_prompt=CLASSIFY_INTENT_SYSTEM_PROMPT,
        user_prompt=prompt,
        model=haiku_model,
        max_tokens=500,
        temperature=0.1,
        timeout=10,
    )

    parsed = _parse_json_response(text)

    # Ensure all expected keys exist with defaults
    parsed.setdefault('intent', 'walkthrough')
    parsed.setdefault('canonical_topic', '')
    parsed.setdefault('display_title', user_input)
    parsed.setdefault('modality', None)
    parsed.setdefault('body_section', None)
    parsed.setdefault('category', None)

    # Validate intent is one of the allowed values
    valid_intents = {'walkthrough', 'report_help', 'tool_request', 'reference',
                     'protocol', 'anatomy', 'paste_report'}
    if parsed['intent'] not in valid_intents:
        parsed['intent'] = 'walkthrough'

    parsed['model'] = model
    parsed['token_count'] = tokens

    return parsed


# ==================== ANATOMY REFERENCE (Phase 5) ====================

ANATOMY_SYSTEM_PROMPT = (
    "You are a radiology anatomy reference. Provide diagnostically relevant anatomy, "
    "not full textbook anatomy. Focus on what radiologists need at the workstation. "
    "Output valid HTML. No markdown. Use <h4>, <p>, <ul>, <li> tags only."
)

ANATOMY_PROMPT = """Provide a concise radiology-focused anatomy reference for: {topic}

Structure your response as HTML with these sections:
1. <h4>Key Structures</h4> — List the main anatomical components with imaging landmarks
2. <h4>Imaging Appearance</h4> — Normal appearance on common modalities (CT, MRI, US as applicable)
3. <h4>Normal Variants</h4> — Variants that mimic pathology (critical for avoiding false positives)
4. <h4>Key Measurements</h4> — Normal measurement ranges relevant to reporting

Keep it under 250 words total. Focus on practical reporting utility.
Use HTML tags: <h4>, <p>, <ul>, <li>, <strong>. No markdown."""


def generate_anatomy_reference(topic):
    """
    Generate a concise anatomy reference for the editor Anatomy Panel.
    Uses Haiku for speed. DB lookup should be attempted first (in routes).

    Args:
        topic: Anatomical topic (e.g. "Circle of Willis", "brachial plexus")

    Returns:
        dict with: title, content_html, source ('ai'), model, token_count
    """
    haiku_model = os.getenv("CLAUDE_QUICK_MODEL", "claude-haiku-4-5-20251001")

    prompt = ANATOMY_PROMPT.format(topic=topic)

    text, model, tokens = _call_claude(
        system_prompt=ANATOMY_SYSTEM_PROMPT,
        user_prompt=prompt,
        model=haiku_model,
        max_tokens=1000,
        temperature=0.2,
        timeout=15,
    )

    return {
        'title': topic.title(),
        'content_html': text,
        'source': 'ai',
        'model': model,
        'token_count': tokens,
    }


# ==================== BLANK TEMPLATE (Gap 3) ====================

BLANK_TEMPLATE_SYSTEM_PROMPT = (
    "You generate structured but empty radiology reporting templates. "
    "The template has section headings and placeholder guidance but NO findings. "
    "The radiologist will fill in their own findings. "
    "Output plain text only. No markdown. No HTML."
)

BLANK_TEMPLATE_PROMPT = """Generate a blank structured PACS reporting template for:

MODALITY: {modality}
BODY SECTION: {body_section}
CLINICAL QUESTION: {clinical_question}

Output a template with these sections:
INDICATION:
(Pre-fill with the modality and clinical question)

TECHNIQUE:
(Pre-fill with standard technique for this modality and body region)

COMPARISON:
No prior available for comparison.

FINDINGS:
(List the organ/structure subheadings a radiologist should systematically assess,
each followed by an empty line for the radiologist to fill in. Order them in standard
reading order for this modality/region. Include 6-10 subheadings.)

IMPRESSION:
(Leave empty — radiologist will write after completing findings)

Output the template as plain text. Each section heading on its own line followed by a colon.
Subheadings under FINDINGS should be indented or numbered."""


def generate_blank_template(modality='', body_section='', clinical_question=''):
    """
    Generate a structured blank reporting template for the abort-walkthrough flow (Gap 3).
    Uses Haiku for speed (~3-5s).

    Args:
        modality: e.g. "CT", "MRI"
        body_section: e.g. "Abdomen", "Brain"
        clinical_question: e.g. "Rule out appendicitis"

    Returns:
        dict with: template_text, model, token_count
    """
    haiku_model = os.getenv("CLAUDE_QUICK_MODEL", "claude-haiku-4-5-20251001")

    prompt = BLANK_TEMPLATE_PROMPT.format(
        modality=modality or 'Not specified',
        body_section=body_section or 'Not specified',
        clinical_question=clinical_question or 'Not specified',
    )

    text, model, tokens = _call_claude(
        system_prompt=BLANK_TEMPLATE_SYSTEM_PROMPT,
        user_prompt=prompt,
        model=haiku_model,
        max_tokens=1500,
        temperature=0.2,
        timeout=15,
    )

    return {
        'template_text': text,
        'model': model,
        'token_count': tokens,
    }


# ==================== RADIOLOGY TEMPLATE GENERATOR ====================

RADIOLOGY_TEMPLATE_SYSTEM_PROMPT = (
    "You are an expert consultant radiologist writing structured PACS report templates. "
    "You produce clinically accurate, scenario-specific radiology report templates that are "
    "ready for copy-paste into a PACS reporting system. Templates must follow standard "
    "radiology reporting conventions with appropriate normal findings boilerplate and "
    "key positive/negative findings relevant to the clinical scenario. "
    "Output plain text only. No markdown formatting. No HTML tags."
)

RADIOLOGY_TEMPLATE_PROMPT = """Generate a structured radiology report template for the following clinical scenario:

CLINICAL SCENARIO: {clinical_scenario}
MODALITY: {modality}
BODY SECTION: {body_section}

{resources_section}

Output the template with EXACTLY these section headings (each on its own line, followed by a colon):

STUDY:
(Full study title, e.g. "CT Abdomen and Pelvis with IV Contrast")

INDICATION:
(Pre-fill with the clinical context for this scenario. Be specific but concise.)

COMPARISON:
No prior available for comparison.

TECHNIQUE:
(Standard technique for this modality/region. Keep concise — 2-3 lines max. Include key parameters like contrast, sequences, or views.)

FINDINGS:
(Systematic organ-by-organ or structure-by-structure assessment in standard reading order for this modality/region. For each structure:
- Include normal boilerplate text as default
- For structures relevant to the clinical scenario, include both normal and abnormal descriptors that a radiologist might select/edit
- Use standard radiology terminology and measurements where appropriate
- Include 8-12 subheadings appropriate to the body region
- Each subheading should be on its own line followed by a colon, then the finding text on the next line)

IMPRESSION:
(Numbered impression points. Include 2-4 key findings relevant to this clinical scenario. Use standard impression language.)

RECOMMENDATIONS:
(Follow-up recommendations if clinically appropriate for this scenario. If none needed, write "Clinical correlation recommended.")

RULES:
- Use standard radiology abbreviations where appropriate
- Include measurement placeholders where relevant (e.g. "[x.x cm]")
- Write findings in present tense, third person
- Be specific to the clinical scenario — this is NOT a blank template
- If reference materials are provided, incorporate their guidance into findings and recommendations"""


def generate_radiology_template(clinical_scenario, modality='', body_section='', resources=None):
    """
    Generate a clinical-scenario-specific radiology report template.
    Unlike generate_blank_template() which produces empty scaffolding,
    this produces a filled template with standard normal findings and
    key positive/negative findings relevant to the clinical scenario.

    Uses Sonnet for quality. Accepts resources (URLs, PDFs, DB refs).

    Args:
        clinical_scenario: e.g. "CT Abdomen — Acute Pancreatitis"
        modality: e.g. "CT", "MRI", "US"
        body_section: e.g. "Abdomen", "Brain"
        resources: Optional dict with urls, db_refs, pdf_texts, tnm_refs

    Returns:
        dict with: template_text, model, token_count
    """
    # Format resources for prompt injection if provided
    resources_section = ''
    if resources:
        try:
            from clinical_tool_generator import format_resources_for_prompt
            resources_section = format_resources_for_prompt(resources)
        except ImportError:
            logger.warning("clinical_tool_generator not available for resource formatting")

    prompt = RADIOLOGY_TEMPLATE_PROMPT.format(
        clinical_scenario=clinical_scenario or 'Not specified',
        modality=modality or 'Not specified',
        body_section=body_section or 'Not specified',
        resources_section=resources_section,
    )

    sonnet_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

    text, model, tokens = _call_claude(
        system_prompt=RADIOLOGY_TEMPLATE_SYSTEM_PROMPT,
        user_prompt=prompt,
        model=sonnet_model,
        max_tokens=3000,
        temperature=0.3,
        timeout=60,
    )

    return {
        'template_text': text,
        'model': model,
        'token_count': tokens,
    }


# ==================== MAIN GENERATOR ====================

def generate_algorithm_tree(clinical_question, modality, body_section='', resources=None):
    """
    Generate a structured algorithm tree for interactive scan reading walkthrough.

    Args:
        clinical_question: The clinical question (e.g. "Rule out acute pancreatitis")
        modality: Imaging modality (e.g. "CT", "MRI", "US")
        body_section: Anatomical region (optional)
        resources: Optional dict with urls, db_refs, pdf_texts, tnm_refs (Gap 1)

    Returns:
        dict with: steps, lines_tubes_step, incidental_findings_step, report_template,
        model, token_count, provider
    """
    resource_section = format_resources_for_prompt(resources)

    user_prompt = TREE_PROMPT_TEMPLATE.format(
        clinical_question=clinical_question,
        modality=modality or 'Not specified',
        body_section=body_section or 'Infer from clinical question',
        resource_section=resource_section,
    )

    text, model, tokens = _call_claude(
        system_prompt=TREE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=6000,
        temperature=0.3,
        timeout=150,
    )

    parsed = _parse_tree_response(text)
    parsed['model'] = model
    parsed['token_count'] = tokens
    parsed['provider'] = 'claude'

    return parsed


# ==================== ASK CLAUDE HELPER (DEPRECATED) ====================

def ask_claude_about_report(current_report, question):
    """
    DEPRECATED: Use unified_ai_assist() instead.
    Kept for backward compatibility with existing routes.

    Lightweight Q&A for Scene 2 report editing.
    """
    logger.warning("ask_claude_about_report() is deprecated. Use unified_ai_assist() instead.")

    user_message = f"""Here is the current draft PACS report:

---
{current_report}
---

Trainee's question: {question}"""

    text, model, tokens = _call_claude(
        system_prompt=ASK_CLAUDE_SYSTEM_PROMPT,
        user_prompt=user_message,
        max_tokens=1500,
        temperature=0.3,
        timeout=30,
    )

    return {
        'answer': text,
        'model': model,
        'token_count': tokens,
    }


# ==================== REVIEW REPORT ====================

def review_report(report_text):
    """
    Review a report for spelling, grammar, phrasing, and structure.

    Returns:
        dict with: improved_report, suggestions[], model, token_count
    """
    user_prompt = REVIEW_REPORT_PROMPT.format(report_text=report_text)

    text, model, tokens = _call_claude(
        system_prompt=REVIEW_REPORT_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=4000,
        temperature=0.2,
        timeout=60,
    )

    parsed = _parse_review_response(text)
    parsed['model'] = model
    parsed['token_count'] = tokens

    return parsed


# ==================== QUICK REVIEW (Layer 0) ====================

def quick_review(report_text):
    """
    Lightweight proofreading: spelling, grammar, phrasing only.
    Uses Haiku for cost efficiency. No clinical assessment.

    Returns:
        dict with: improved_report, suggestions[], model, token_count
    """
    haiku_model = os.getenv("CLAUDE_QUICK_MODEL", "claude-haiku-4-5-20251001")

    user_prompt = QUICK_REVIEW_PROMPT.format(report_text=report_text)

    text, model, tokens = _call_claude(
        system_prompt=QUICK_REVIEW_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=haiku_model,
        max_tokens=2000,
        temperature=0.2,
        timeout=20,
    )

    parsed = _parse_review_response(text)
    parsed['model'] = model
    parsed['token_count'] = tokens

    return parsed


# ==================== UNIFIED AI ASSIST (Layers 1+2+3) ====================

def unified_ai_assist(report_text, question, clinical_question='', modality='',
                      body_section='', external_context=None, resources=None):
    """
    Unified AI assistant: corrections + direct answer + clinical insights.
    Single API call returns all three layers.

    Args:
        report_text: The current draft PACS report
        question: The trainee's question
        clinical_question: The clinical indication (from session)
        modality: Imaging modality (from session)
        body_section: Anatomical region (from session)
        external_context: Optional dict with {type, title, slug, id} from "Use in Report" buttons
        resources: Optional dict with urls, db_refs, pdf_texts, tnm_refs (Gap 1)

    Returns:
        dict with: corrections[], answer, insights{}, model, token_count
    """
    # Build resource section from explicit resources AND external context
    resource_section = format_resources_for_prompt(resources)

    # Append external context if user arrived from another tool
    if external_context and isinstance(external_context, dict):
        ctx_type = external_context.get('type', '')
        ctx_title = external_context.get('title', '')
        if ctx_type and ctx_title:
            context_labels = {
                'if': 'Incidental Findings calculator',
                'tnm': 'TNM Staging calculator',
                'template': 'Reporting Template',
                'protocol': 'Clinical Protocol',
            }
            label = context_labels.get(ctx_type, ctx_type)
            resource_section += (
                f"\nADDITIONAL CONTEXT: The user is reporting on a case related to "
                f"{label}: \"{ctx_title}\". Factor this into your corrections, answer, and insights.\n"
            )

    user_prompt = UNIFIED_ASSIST_PROMPT.format(
        report_text=report_text or '(empty report — user may be starting fresh or about to paste their report)',
        question=question,
        clinical_question=clinical_question or 'Not specified',
        modality=modality or 'Not specified',
        body_section=body_section or 'Not specified',
        resource_section=resource_section,
    )

    effective_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

    text, model, tokens = _call_claude(
        system_prompt=UNIFIED_ASSIST_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=effective_model,
        max_tokens=4000,
        temperature=0.3,
        timeout=45,
    )

    parsed = _parse_assist_response(text, question)
    parsed['model'] = model
    parsed['token_count'] = tokens

    return parsed


# ==================== RESPONSE PARSERS ====================

def _parse_assist_response(text, original_question):
    """Parse unified AI assist JSON response with graceful fallbacks."""
    try:
        parsed = _parse_json_response(text)
    except SmartReporterError:
        # Graceful fallback: return the raw text as the answer
        logger.warning("AI assist response was not valid JSON; returning raw text as answer.")
        return {
            'corrections': [],
            'answer': text,
            'insights': {},
        }

    # Extract and validate corrections
    corrections = []
    for c in parsed.get('corrections', []):
        if not isinstance(c, dict):
            continue
        c.setdefault('original', '')
        c.setdefault('suggested', '')
        c.setdefault('reason', '')
        c.setdefault('type', 'phrasing')
        if c['original'] and c['suggested'] and c['original'] != c['suggested']:
            corrections.append(c)

    # Extract answer
    answer = parsed.get('answer', '').strip()

    # Extract insights with defaults
    raw_insights = parsed.get('insights', {})
    if not isinstance(raw_insights, dict):
        raw_insights = {}

    insights = {
        'clinical_question_coverage': raw_insights.get('clinical_question_coverage', ''),
        'quality_assessment': raw_insights.get('quality_assessment', ''),
        'differentials_to_consider': raw_insights.get('differentials_to_consider', []),
        'recommendation_check': raw_insights.get('recommendation_check', ''),
        'teaching_point': raw_insights.get('teaching_point', ''),
    }

    # Ensure differentials is a list
    if not isinstance(insights['differentials_to_consider'], list):
        insights['differentials_to_consider'] = []

    return {
        'corrections': corrections,
        'answer': answer,
        'insights': insights,
    }


def _parse_review_response(text):
    """Parse review report JSON response."""
    parsed = _parse_json_response(text)

    parsed.setdefault('improved_report', '')
    parsed.setdefault('suggestions', [])

    # Validate suggestions
    valid_suggestions = []
    for s in parsed['suggestions']:
        if not isinstance(s, dict):
            continue
        s.setdefault('original', '')
        s.setdefault('suggested', '')
        s.setdefault('reason', '')
        s.setdefault('type', 'phrasing')
        if s['original'] and s['suggested'] and s['original'] != s['suggested']:
            valid_suggestions.append(s)
    parsed['suggestions'] = valid_suggestions

    return parsed


# ==================== TREE RESPONSE PARSER ====================

def _parse_tree_response(text):
    """Parse algorithm tree JSON response with validation and fallbacks."""
    parsed = _parse_json_response(text)

    # Validate required top-level keys
    parsed.setdefault('steps', [])
    parsed.setdefault('lines_tubes_step', {
        'id': 'lines_tubes',
        'organ': 'Lines and devices',
        'question': 'Are there any lines, tubes, or surgical devices?',
        'options': [
            {'label': 'No lines or tubes',
             'report_text': 'No lines, tubes, or surgical devices are identified.',
             'findings_flag': 'normal'},
        ],
        'allow_multiple': True,
    })
    parsed.setdefault('incidental_findings_step', {
        'id': 'incidentals',
        'organ': 'Incidental findings',
        'question': 'Any incidental findings to note?',
        'options': [
            {'label': 'No incidental findings', 'report_text': '',
             'findings_flag': 'normal'},
            {'label': 'Other (free text)', 'report_text': '',
             'findings_flag': 'incidental', 'is_free_text': True},
        ],
        'allow_multiple': True,
    })
    parsed.setdefault('report_template', {})

    # Validate report_template has all HL7 sections
    rt = parsed['report_template']
    rt.setdefault('indication', '')
    rt.setdefault('technique', '')
    rt.setdefault('comparison', 'No prior available for comparison.')
    rt.setdefault('impression_normal', 'No acute abnormality identified.')
    rt.setdefault('impression_abnormal', '')
    rt.setdefault('recommendation', '')

    # Validate each step
    valid_step_ids = {s.get('id') for s in parsed['steps'] if isinstance(s, dict)}
    valid_step_ids.add('lines_tubes')
    valid_step_ids.add('incidentals')

    validated_steps = []
    for step in parsed['steps']:
        if not isinstance(step, dict):
            continue
        step.setdefault('id', f'step_{len(validated_steps) + 1}')
        step.setdefault('organ', '')
        step.setdefault('question', '')
        step.setdefault('options', [])
        step.setdefault('allow_multiple', False)

        # Validate options
        valid_options = []
        for opt in step.get('options', []):
            if not isinstance(opt, dict):
                continue
            opt.setdefault('label', '')
            opt.setdefault('report_text', '')
            opt.setdefault('findings_flag', 'normal')
            # Validate next_step reference — set to null if invalid
            ns = opt.get('next_step')
            if ns and ns not in valid_step_ids:
                opt['next_step'] = None
            elif ns is None:
                opt.setdefault('next_step', None)
            valid_options.append(opt)
        step['options'] = valid_options
        validated_steps.append(step)

    parsed['steps'] = validated_steps

    # Validate lines_tubes_step and incidental_findings_step options
    for special_key in ['lines_tubes_step', 'incidental_findings_step']:
        special = parsed[special_key]
        if isinstance(special, dict):
            special.setdefault('allow_multiple', True)
            valid_opts = []
            for opt in special.get('options', []):
                if isinstance(opt, dict):
                    opt.setdefault('label', '')
                    opt.setdefault('report_text', '')
                    opt.setdefault('findings_flag', 'normal')
                    valid_opts.append(opt)
            special['options'] = valid_opts

    if not parsed['steps']:
        raise SmartReporterError("Algorithm tree has no steps. Generation may have failed.")

    return parsed
