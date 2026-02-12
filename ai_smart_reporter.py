"""
AI Smart Reporter Module

Generates structured algorithm trees for interactive scan reading walkthrough,
and provides lightweight "Ask Claude" for report editing assistance.

Separate from ai_algorithmic_reporter.py (which generates HTML + flat PACS text).
This module generates structured JSON with branching logic for client-side rendering.
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


# ==================== SYSTEM PROMPTS ====================

TREE_SYSTEM_PROMPT = (
    "You are a consultant radiologist with extensive daily PACS reporting experience. "
    "You generate structured algorithm decision trees for scan reading. "
    "Output valid JSON only. No markdown fences. No text outside the JSON object."
)

ASK_CLAUDE_SYSTEM_PROMPT = (
    "You are a consultant radiologist reviewing a trainee's draft PACS report. "
    "Answer their question concisely using standard radiology phrasing. "
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
1. Fix genuine spelling errors, including radiology-specific terms (e.g. "referral thyroid" should be "retrosternal thyroid", "heptaic" should be "hepatic").
2. Fix grammar errors.
3. Improve phrasing to match standard radiology conventions (e.g. "There is no evidence of" to "No evidence of", "The liver appears normal" to "The liver is unremarkable").
4. Do NOT assess clinical correctness. Do NOT add content. Do NOT change clinical meaning.
5. Each suggestion must quote the EXACT original text so the frontend can locate it.
6. Max 10 suggestions. Prioritise: spelling > grammar > phrasing.
7. If the report is already well-written, return an empty suggestions array and the original text as improved_report.

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
    "- Teach through the report — brief why when suggesting additions\n"
    "- NEVER add findings the trainee didn't describe — the images aren't available to you\n\n"
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

Return a JSON object with EXACTLY this structure:

{{
  "corrections": [
    {{
      "original": "exact phrase from the report",
      "suggested": "corrected/improved phrase",
      "reason": "Brief explanation (5-10 words)",
      "type": "terminology|gender_check|anatomy_check|consistency|phrasing"
    }}
  ],
  "answer": "Direct answer to the trainee's question. PACS-ready text where applicable. No preamble like 'Here is...' or 'I suggest...'. No markdown. Ready to paste into the report without editing.",
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
5. Max 8 corrections. Prioritise clinically significant errors over stylistic ones.
6. If the report has no issues, return an empty corrections array.

RULES FOR ANSWER:
1. Write as a consultant would dictate at a workstation. No hedging beyond standard conventions.
2. If the trainee asks for specific report text (e.g. "write the impression"), give complete PACS-ready sentences. Do NOT wrap in quotes or add labels.
3. Keep the answer under 250 words. Plain text only — no markdown, no HTML, no bullet lists.
4. If the trainee asks a knowledge question (e.g. "what's the differential?"), answer directly and concisely.

RULES FOR INSIGHTS:
1. Be specific and actionable, not generic platitudes.
2. differentials_to_consider: only list if genuinely relevant and not already covered in the report. Empty array if not applicable.
3. teaching_point: one actionable pearl, not a textbook paragraph. Relevant to this specific report.
4. If the report is excellent, say so — do not invent criticisms.
5. If the report is empty or too short for meaningful assessment, say so briefly in quality_assessment and skip the rest.

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
   For example, CT abdomen: start with the organ of interest based on the clinical question,
   then systematically cover remaining solid organs, bowel, vasculature, bones, soft tissues.
4. Each option's report_text must be a complete, standalone PACS-ready sentence.
   Write as a radiologist would in a formal report — no hedging beyond standard conventions.
5. Use next_step for conditional branching:
   - If a finding is abnormal, next_step should point to a sub-step that characterises it further.
   - If a finding is normal, next_step should skip ahead to the next organ (or null to continue sequentially).
   - If next_step is null, the engine advances to the next step in array order.
6. Include both normal and abnormal options for EVERY step. The normal option should always be first.
7. Each step should have 3-5 options (including one free-text option for unusual findings).
8. The last option in each step should be a free-text entry:
   {{"label": "Other (free text)", "report_text": "", "findings_flag": "abnormal", "is_free_text": true}}
9. lines_tubes_step should have 5-8 common options relevant to this modality and body region.
10. incidental_findings_step should have 4-6 common incidental findings for this body region.
11. report_template.indication must include the modality and clinical question.
12. report_template.technique should be specific to this modality (e.g., include contrast phase for CT).
13. Do NOT include pathophysiology, epidemiology, or teaching content.
14. findings_flag values: "normal", "abnormal", "equivocal", "incidental"

Output ONLY the JSON object. No markdown. No explanation."""


# ==================== MAIN GENERATOR ====================

def generate_algorithm_tree(clinical_question, modality, body_section=''):
    """
    Generate a structured algorithm tree for interactive scan reading walkthrough.

    Args:
        clinical_question: The clinical question to answer (e.g. "Rule out acute pancreatitis")
        modality: Imaging modality (e.g. "CT", "MRI", "US")
        body_section: Anatomical region (optional)

    Returns:
        dict with: steps, lines_tubes_step, incidental_findings_step, report_template,
        model, token_count, provider
    """
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise SmartReporterError("RadInsight Intelligence API key not configured.")

    effective_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    user_prompt = TREE_PROMPT_TEMPLATE.format(
        clinical_question=clinical_question,
        modality=modality or 'Not specified',
        body_section=body_section or 'Infer from clinical question',
    )

    payload = {
        "model": effective_model,
        "max_tokens": 10000,
        "temperature": 0.3,
        "system": TREE_SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": user_prompt}
        ],
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
            timeout=150,
        )
    except requests.exceptions.Timeout:
        raise SmartReporterError("Algorithm tree generation timed out. Please try again.")
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

    text = content[0].get("text", "")
    if not text:
        raise SmartReporterError("No text in RadInsight Intelligence response.")

    parsed = _parse_tree_response(text)

    parsed['model'] = effective_model
    parsed['token_count'] = result.get("usage", {}).get("output_tokens", 0)
    parsed['provider'] = 'claude'

    return parsed


# ==================== ASK CLAUDE HELPER ====================

def ask_claude_about_report(current_report, question):
    """
    Lightweight Q&A for Scene 2 report editing.

    Args:
        current_report: The current plain-text PACS report
        question: The trainee's question

    Returns:
        dict with: answer, model, token_count
    """
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise SmartReporterError("RadInsight Intelligence API key not configured.")

    effective_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    user_message = f"""Here is the current draft PACS report:

---
{current_report}
---

Trainee's question: {question}"""

    payload = {
        "model": effective_model,
        "max_tokens": 1500,
        "temperature": 0.3,
        "system": ASK_CLAUDE_SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": user_message}
        ],
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
            timeout=30,
        )
    except requests.exceptions.Timeout:
        raise SmartReporterError("Request timed out. Please try again.")
    except requests.exceptions.RequestException as exc:
        raise SmartReporterError(f"Connection failed: {exc}")

    if response.status_code >= 300:
        detail = response.text[:500]
        raise SmartReporterError(f"Error (HTTP {response.status_code}): {detail}")

    result = response.json()
    content = result.get("content", [])
    if not content:
        raise SmartReporterError("Empty response.")

    answer = content[0].get("text", "").strip()

    return {
        'answer': answer,
        'model': effective_model,
        'token_count': result.get("usage", {}).get("output_tokens", 0),
    }


# ==================== REVIEW REPORT ====================

def review_report(report_text):
    """
    Review a report for spelling, grammar, phrasing, and structure.

    Args:
        report_text: The draft PACS report text

    Returns:
        dict with: improved_report, suggestions[], model, token_count
    """
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise SmartReporterError("RadInsight Intelligence API key not configured.")

    effective_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    user_prompt = REVIEW_REPORT_PROMPT.format(report_text=report_text)

    payload = {
        "model": effective_model,
        "max_tokens": 4000,
        "temperature": 0.2,
        "system": REVIEW_REPORT_SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": user_prompt}
        ],
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
            timeout=60,
        )
    except requests.exceptions.Timeout:
        raise SmartReporterError("Review timed out. Please try again.")
    except requests.exceptions.RequestException as exc:
        raise SmartReporterError(f"Connection failed: {exc}")

    if response.status_code >= 300:
        detail = response.text[:500]
        raise SmartReporterError(f"Error (HTTP {response.status_code}): {detail}")

    result = response.json()
    content = result.get("content", [])
    if not content:
        raise SmartReporterError("Empty response.")

    text = content[0].get("text", "").strip()
    if not text:
        raise SmartReporterError("No text in response.")

    parsed = _parse_review_response(text)
    parsed['model'] = effective_model
    parsed['token_count'] = result.get("usage", {}).get("output_tokens", 0)

    return parsed


# ==================== QUICK REVIEW (Layer 0) ====================

def quick_review(report_text):
    """
    Lightweight proofreading: spelling, grammar, phrasing only.
    Uses Haiku for cost efficiency. No clinical assessment.

    Returns:
        dict with: improved_report, suggestions[], model, token_count
    """
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise SmartReporterError("RadInsight Intelligence API key not configured.")

    effective_model = os.getenv("CLAUDE_QUICK_MODEL", "claude-haiku-4-5-20251001")

    user_prompt = QUICK_REVIEW_PROMPT.format(report_text=report_text)

    payload = {
        "model": effective_model,
        "max_tokens": 2000,
        "temperature": 0.2,
        "system": QUICK_REVIEW_SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": user_prompt}
        ],
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
            timeout=20,
        )
    except requests.exceptions.Timeout:
        raise SmartReporterError("Quick review timed out. Please try again.")
    except requests.exceptions.RequestException as exc:
        raise SmartReporterError(f"Connection failed: {exc}")

    if response.status_code >= 300:
        detail = response.text[:500]
        raise SmartReporterError(f"Error (HTTP {response.status_code}): {detail}")

    result = response.json()
    content = result.get("content", [])
    if not content:
        raise SmartReporterError("Empty response.")

    text = content[0].get("text", "").strip()
    if not text:
        raise SmartReporterError("No text in response.")

    parsed = _parse_review_response(text)
    parsed['model'] = effective_model
    parsed['token_count'] = result.get("usage", {}).get("output_tokens", 0)

    return parsed


# ==================== UNIFIED AI ASSIST (Layers 1+2+3) ====================

def unified_ai_assist(report_text, question, clinical_question='', modality='', body_section='', external_context=None):
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

    Returns:
        dict with: corrections[], answer, insights{}, model, token_count
    """
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise SmartReporterError("RadInsight Intelligence API key not configured.")

    effective_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

    user_prompt = UNIFIED_ASSIST_PROMPT.format(
        report_text=report_text or '(empty report)',
        question=question,
        clinical_question=clinical_question or 'Not specified',
        modality=modality or 'Not specified',
        body_section=body_section or 'Not specified',
    )

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
            user_prompt += (
                f"\n\nADDITIONAL CONTEXT: The user is reporting on a case related to "
                f"{label}: \"{ctx_title}\". Factor this into your corrections, answer, and insights."
            )

    payload = {
        "model": effective_model,
        "max_tokens": 4000,
        "temperature": 0.3,
        "system": UNIFIED_ASSIST_SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": user_prompt}
        ],
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
            timeout=45,
        )
    except requests.exceptions.Timeout:
        raise SmartReporterError("AI assist timed out. Please try again.")
    except requests.exceptions.RequestException as exc:
        raise SmartReporterError(f"Connection failed: {exc}")

    if response.status_code >= 300:
        detail = response.text[:500]
        raise SmartReporterError(f"Error (HTTP {response.status_code}): {detail}")

    result = response.json()
    content_blocks = result.get("content", [])
    if not content_blocks:
        raise SmartReporterError("Empty response.")

    text = content_blocks[0].get("text", "").strip()
    if not text:
        raise SmartReporterError("No text in response.")

    parsed = _parse_assist_response(text, question)
    parsed['model'] = effective_model
    parsed['token_count'] = result.get("usage", {}).get("output_tokens", 0)

    return parsed


def _parse_assist_response(text, original_question):
    """Parse unified AI assist JSON response with graceful fallbacks."""
    # Strip markdown code fences
    if text.strip().startswith("```"):
        lines = text.strip().split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                # Graceful fallback: return the raw text as the answer
                return {
                    'corrections': [],
                    'answer': text,
                    'insights': {},
                }
        else:
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
    # Strip markdown code fences
    if text.strip().startswith("```"):
        lines = text.strip().split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                raise SmartReporterError("Failed to parse review response as JSON.")
        else:
            raise SmartReporterError("Review response was not valid JSON.")

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
    # Strip markdown code fences
    if text.strip().startswith("```"):
        lines = text.strip().split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                raise SmartReporterError("Failed to parse algorithm tree response as JSON.")
        else:
            raise SmartReporterError("Algorithm tree response was not valid JSON.")

    # Validate required top-level keys
    parsed.setdefault('steps', [])
    parsed.setdefault('lines_tubes_step', {
        'id': 'lines_tubes',
        'organ': 'Lines and devices',
        'question': 'Are there any lines, tubes, or surgical devices?',
        'options': [
            {'label': 'No lines or tubes', 'report_text': 'No lines, tubes, or surgical devices are identified.', 'findings_flag': 'normal'},
        ],
        'allow_multiple': True,
    })
    parsed.setdefault('incidental_findings_step', {
        'id': 'incidentals',
        'organ': 'Incidental findings',
        'question': 'Any incidental findings to note?',
        'options': [
            {'label': 'No incidental findings', 'report_text': '', 'findings_flag': 'normal'},
            {'label': 'Other (free text)', 'report_text': '', 'findings_flag': 'incidental', 'is_free_text': True},
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
