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
