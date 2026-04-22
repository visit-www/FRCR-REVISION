"""
AI OSCE Case Generator

Generates radiology OSCE cases for 3rd-year medical students.
Two prompt variants: pathological cases and normal studies.

Output: structured JSON for the OSCE guide page — editable in TinyMCE
when rendered to HTML.

Prompt Version: v7
Last Updated: April 2026
"""

import json
import os
from datetime import datetime

import requests

from ai_client import AIClientError


class AiOsceError(AIClientError):
    """Raised when OSCE case generation fails."""
    pass


# ============================================================================
# MODALITY-SPECIFIC APPROACHES (shared across prompts)
# ============================================================================

_MODALITY_APPROACHES = {
    "CXR": "ABCDE — Airway (trachea midline?), Breathing (lung fields, pleural space), Circulation (heart size/shape, mediastinum), Disability (bones, soft tissue), Everything else (review areas — apices, costophrenic angles, behind heart)",
    "AXR": "Gas pattern (SBO vs LBO vs normal), Free air (under diaphragm), Calcifications (renal, biliary, vascular), Solid organs (liver, spleen, kidneys), Bones (spine, pelvis)",
    "Knee X-ray": "Alignment (joint congruency, valgus/varus), Bones (cortical breaks, density), Cartilage/Joints (joint space, effusion), Soft tissues (swelling, fat pads, foreign bodies)",
    "Shoulder X-ray": "Alignment (glenohumeral, AC joint), Bones (humerus, clavicle, scapula — cortical breaks), Joints (joint space, AC separation), Soft tissues (calcification, swelling)",
    "Elbow X-ray": "Alignment (anterior humeral line, radiocapitellar line), Bones (cortical breaks in radial head, olecranon, coronoid, capitellum), Fat pads (anterior sail sign, posterior fat pad), Joints (joint space, carrying angle)",
    "Foot X-ray": "Alignment (Lisfranc joint — 2nd MT base aligns with middle cuneiform), Bones (cortical breaks — 5th MT base, calcaneus, navicular), Joints (tarsometatarsal congruency), Soft tissues (swelling pattern)",
    "CT Brain": "Blood (extra-axial collections — EDH biconvex, SDH crescent, SAH in sulci/cisterns; intraparenchymal), Brain (grey-white differentiation, mass effect, midline shift), CSF (ventricle size and symmetry, hydrocephalus), Bone (skull vault fractures, base of skull)",
}

# Standard views per modality
_MODALITY_VIEWS = {
    "CXR": "PA erect (standard — accurate heart size, sharp costophrenic angles, trachea midline assessment). AP supine/erect (sick patients — magnified heart, poor mediastinal assessment, effusions layer posteriorly). Lateral (retrosternal space, posterior costophrenic angles, vertebral body density).",
    "AXR": "AP supine (standard — gas pattern, calcifications, soft tissue outlines). Erect (air-fluid levels in obstruction, free air under diaphragm on erect CXR).",
    "Knee X-ray": "AP (joint space, alignment, valgus/varus). Lateral (effusion — suprapatellar pouch, tibial plateau depression, patella position). Skyline/sunrise (patellofemoral joint).",
    "Shoulder X-ray": "AP (glenohumeral alignment, fractures, AC joint). Axillary/Y-view (confirms anterior vs posterior dislocation — critical for posterior dislocations which are missed on AP alone).",
    "Elbow X-ray": "AP (carrying angle, joint space, radial head). Lateral (fat pads — anterior sail sign and posterior fat pad, anterior humeral line through middle third of capitellum).",
    "Foot X-ray": "AP/dorsoplantar (metatarsals, Lisfranc alignment — 2nd MT base with middle cuneiform). Oblique (5th metatarsal base — Jones fracture). Lateral (calcaneus — Bohler angle, plantar fascia).",
    "CT Brain": "Axial non-contrast (standard acute — blood appears hyperdense/white). Bone windows (skull fractures, mastoid air cells). Soft tissue windows (grey-white differentiation, ventricles). CTA (if vascular pathology suspected — stroke, aneurysm).",
}

_MODALITY_MAP = {
    "CXR": "Chest X-ray",
    "AXR": "Abdominal X-ray",
    "Knee X-ray": "Knee X-ray",
    "Shoulder X-ray": "Shoulder X-ray",
    "Elbow X-ray": "Elbow X-ray",
    "Foot X-ray": "Foot X-ray",
    "CT Brain": "CT Brain",
}


# ============================================================================
# SYSTEM PROMPT
# ============================================================================

SYSTEM_PROMPT = """You are an expert radiology teacher sitting with a 3rd-year medical student at a lightbox.

Your job: teach them to READ images — pattern recognition, not memorisation. Explain what matters, skip what doesn't, never say the same thing twice.

You are creating a TEACHING CASE, not reporting on an actual image. Write as a guide — "check X, look for Y, normal is Z" — not as a mock report.

STUDENT LEVEL: basic anatomy, early clinical exposure, preparing for OSCE exams.

PRINCIPLES:
- Zero redundancy — if you said it in one section, do not repeat it in another
- Drop empty sections — set to null if a field adds nothing for this case
- Teach recognition — "when you see X, think Y" beats "the diagnosis is Y"
- Measurements matter — include thresholds (e.g., <3cm, <0.5 ratio)
- Plain text only — no HTML, no markdown

Output JSON only. No markdown fences."""


# ============================================================================
# PATHOLOGICAL CASE PROMPT
# ============================================================================

def _build_pathological_prompt(case_context):
    """Build prompt for a pathological OSCE case."""
    diagnosis = case_context.get("diagnosis", "").strip()
    modality = case_context.get("modality", "").strip()
    category = case_context.get("category", "").strip()
    tags = case_context.get("tags", "").strip()
    notes = case_context.get("notes", "").strip()

    additional_context = case_context.get("additional_context", "").strip()

    modality_label = _MODALITY_MAP.get(modality, modality)
    approach = _MODALITY_APPROACHES.get(modality, "Systematic review")
    views = _MODALITY_VIEWS.get(modality, "Standard views")

    context_block = ""
    if additional_context:
        context_block = f"""
=== ADDITIONAL CONTEXT ===
{additional_context}
=== END CONTEXT ===
Use the above to enrich your output. Also draw on broader medical knowledge.
"""

    return f"""Generate ONE radiology OSCE case.
{context_block}
====================================================================
INPUT
====================================================================

Diagnosis: {diagnosis}
Modality: {modality_label}
Category: {category}
Notes: {notes if notes else 'None'}

SYSTEMATIC APPROACH:
{approach}

STANDARD VIEWS:
{views}

====================================================================
OUTPUT (strict JSON)
====================================================================

{{
  "diagnosis": "{diagnosis}",
  "modality": "{modality}",
  "category": "{category}",
  "difficulty": "Easy or Moderate",

  "views": {{
    "obtained": "",
    "notes": ""
  }},

  "tags": {{
    "pattern": "",
    "tissue": ""
  }},

  "osce": {{
    "prompt": "",

    "expected_answer": {{
      "approach": "Numbered list. ONE sentence per item — state what to check and the criteria for normal vs abnormal, with thresholds. This is a TEACHING GUIDE, not a report — you are not reading an image. Do NOT include pitfalls (those go in teaching_points).",
      "key_finding": "Describe the expected abnormal appearance in simple visual language (not the diagnosis name). Then: this pattern suggests...",
      "diagnosis": "{diagnosis}",
      "urgency": "Clinical significance, emergency status, action needed."
    }},

    "model_script": "2-4 sentence OSCE script: identify view, state finding, give diagnosis, state urgency. Do not repeat the approach."
  }},

  "explanation": {{
    "mechanism": "Why the imaging looks like this. Set to null if approach already covers it."
  }},

  "teaching_points": ["Pitfalls, classic traps, differentials, examiner follow-ups — anything the student should WATCH OUT for. These must NOT duplicate the approach items."],

  "visual_hook": "One memorable sentence: the single visual pattern that makes this diagnosis click."
}}

====================================================================
QUALITY CHECK
====================================================================

- Approach = what you check + normal/abnormal + threshold (no pitfalls)
- Teaching points = pitfalls + traps + exam tips (no overlap with approach)
- Model script does not repeat approach
- No redundancy across sections"""


# ============================================================================
# NORMAL CASE PROMPT
# ============================================================================

def _build_normal_prompt(case_context):
    """Build prompt for a normal study OSCE case."""
    modality = case_context.get("modality", "").strip()
    notes = case_context.get("notes", "").strip()
    additional_context = case_context.get("additional_context", "").strip()

    modality_label = _MODALITY_MAP.get(modality, modality)
    approach = _MODALITY_APPROACHES.get(modality, "Systematic review")
    views = _MODALITY_VIEWS.get(modality, "Standard views")

    context_block = ""
    if additional_context:
        context_block = f"""
=== ADDITIONAL CONTEXT ===
{additional_context}
=== END CONTEXT ===
Use the above to enrich your output.
"""

    return f"""Generate ONE NORMAL radiology OSCE case.
{context_block}
====================================================================
INPUT
====================================================================

Modality: {modality_label}
Notes: {notes if notes else 'None'}

SYSTEMATIC APPROACH:
{approach}

STANDARD VIEWS:
{views}

====================================================================
OUTPUT (strict JSON)
====================================================================

{{
  "diagnosis": "Normal {modality_label}",
  "modality": "{modality}",
  "category": "Normal",
  "difficulty": "Easy",

  "views": {{
    "obtained": "",
    "notes": ""
  }},

  "tags": {{
    "pattern": "normal",
    "tissue": "all structures"
  }},

  "osce": {{
    "prompt": "",

    "expected_answer": {{
      "approach": "Numbered list. ONE sentence per item — state what to check and the normal value/threshold. This is a TEACHING GUIDE, not a report — you are not reading an image. Do NOT include pitfalls (those go in teaching_points).",
      "key_finding": "No abnormality detected",
      "diagnosis": "Normal {modality_label}",
      "urgency": "No urgent findings"
    }},

    "model_script": "3-5 sentence OSCE script: identify view, confirm normality concisely, conclude with summary. Do not repeat the approach."
  }},

  "explanation": {{
    "common_pitfalls": "Set to null — pitfalls now go in teaching_points."
  }},

  "teaching_points": ["Pitfalls, normal variants that mimic pathology, OSCE traps, examiner follow-ups. These must NOT duplicate the approach items."],

  "visual_hook": "One memorable sentence about what makes a normal study convincingly normal."
}}

====================================================================
QUALITY CHECK
====================================================================

- Approach = what you check + normal value (no pitfalls, no essays)
- Teaching points = pitfalls + traps + exam tips (no overlap with approach)
- Model script does not repeat approach
- No redundancy across sections"""


# ============================================================================
# API CALL
# ============================================================================

def generate_osce_case(case_context):
    """
    Generate an OSCE case using the Anthropic Messages API.

    Args:
        case_context: dict with keys:
            - diagnosis (required for pathological; ignored for normal)
            - modality (required) — one of: CXR, AXR, Knee X-ray,
              Shoulder X-ray, Elbow X-ray, Foot X-ray, CT Brain
            - category (required) — Emergency, Spotter, Common, or Normal
            - tags (optional) — comma-separated tag string
            - notes (optional) — additional context
            - model (optional) — Claude model override

    Returns:
        dict with keys:
            - provider, model, prompt_version, generated_at
            - output (parsed JSON)
            - raw_response
            - usage (input_tokens, output_tokens)

    Raises:
        AiOsceError: If generation fails
    """
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise AiOsceError("CLAUDE_API_KEY is not configured.")

    category = (case_context.get("category") or "").strip()
    modality = (case_context.get("modality") or "").strip()

    if not modality:
        raise AiOsceError("Modality is required for OSCE case generation.")

    if modality not in _MODALITY_APPROACHES:
        raise AiOsceError(
            f"Unsupported modality: {modality}. "
            f"Supported: {', '.join(_MODALITY_APPROACHES.keys())}"
        )

    # Select prompt variant
    if category.lower() == "normal":
        user_prompt = _build_normal_prompt(case_context)
    else:
        diagnosis = (case_context.get("diagnosis") or "").strip()
        if not diagnosis:
            raise AiOsceError("Diagnosis is required for pathological OSCE cases.")
        user_prompt = _build_pathological_prompt(case_context)

    # Prepend shared ABC preamble
    from ai_client import ABC_PREAMBLE
    effective_system = ABC_PREAMBLE + SYSTEM_PROMPT

    model = case_context.get("model") or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

    payload = {
        "model": model,
        "max_tokens": 6000,
        "temperature": 0.3,
        "system": effective_system,
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
            data=json.dumps(payload),
            timeout=120,
        )
    except requests.exceptions.Timeout:
        raise AiOsceError("OSCE generation request timed out. Please try again.")
    except requests.exceptions.RequestException as exc:
        raise AiOsceError(f"Failed to connect to AI service: {exc}")

    if response.status_code >= 300:
        error_detail = response.text[:500] if response.text else "No details"
        raise AiOsceError(
            f"AI service error (HTTP {response.status_code}): {error_detail}"
        )

    data = response.json()
    usage = data.get("usage", {})
    content = data.get("content", [])
    if not content:
        raise AiOsceError("AI response missing content block.")

    text = content[0].get("text", "").strip()
    if not text:
        raise AiOsceError("AI response was empty.")

    # Clean up markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # Parse JSON
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        import re
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
            except json.JSONDecodeError:
                raise AiOsceError(
                    f"Response was not valid JSON: {exc}. Preview: {text[:200]}..."
                ) from exc
        else:
            raise AiOsceError(
                f"Response was not valid JSON: {exc}. Preview: {text[:200]}..."
            ) from exc

    # Validate and set defaults
    parsed.setdefault("diagnosis", case_context.get("diagnosis", ""))
    parsed.setdefault("modality", modality)
    parsed.setdefault("category", category)
    parsed.setdefault("difficulty", "Moderate")
    parsed.setdefault("views", {})
    parsed.setdefault("tags", {})
    parsed.setdefault("osce", {})
    parsed["osce"].setdefault("prompt", "")
    parsed["osce"].setdefault("expected_answer", {})
    parsed["osce"].setdefault("model_script", "")
    parsed.setdefault("explanation", {})
    parsed.setdefault("teaching_points", [])

    # Validate teaching_points is a list of strings
    if isinstance(parsed.get("teaching_points"), list):
        parsed["teaching_points"] = [
            item.strip() for item in parsed["teaching_points"]
            if isinstance(item, str) and item.strip()
        ]

    return {
        "provider": "claude",
        "model": model,
        "prompt_version": "osce-v7",
        "generated_at": datetime.utcnow().isoformat(),
        "output": parsed,
        "raw_response": text,
        "usage": {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        },
    }


# ============================================================================
# HTML RENDERER — converts OSCE JSON to TinyMCE-editable HTML
# ============================================================================

def render_osce_html(osce_data):
    """
    Convert OSCE case JSON into editable HTML for TinyMCE storage.

    The HTML uses semantic class names (osce-section, osce-*) so the
    OSCE guide page can parse and render it, while remaining fully
    editable in TinyMCE for admin tweaks.

    Args:
        osce_data: dict — the parsed OSCE case JSON (the "output" field)

    Returns:
        str — HTML string
    """
    if not osce_data or not isinstance(osce_data, dict):
        return ""

    def _esc(val):
        """Escape HTML entities."""
        if not val:
            return ""
        return (str(val)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))

    parts = []

    # -- Header --
    diagnosis = _esc(osce_data.get("diagnosis", ""))
    category = _esc(osce_data.get("category", ""))
    difficulty = _esc(osce_data.get("difficulty", ""))
    modality = _esc(osce_data.get("modality", ""))

    parts.append(
        f'<div class="osce-section" data-section="header">'
        f'<h3>{diagnosis}</h3>'
        f'<p><strong>Modality:</strong> {modality} &nbsp;|&nbsp; '
        f'<strong>Category:</strong> {category} &nbsp;|&nbsp; '
        f'<strong>Difficulty:</strong> {difficulty}</p>'
        f'</div>'
    )

    # -- Views --
    views = osce_data.get("views", {})
    if views and isinstance(views, dict):
        parts.append('<div class="osce-section" data-section="views">')
        parts.append('<h4>Radiographic Views</h4>')
        for field in ("obtained", "notes", "why_this_view", "additional_views"):
            val = views.get(field)
            if val:
                label = field.replace("_", " ").title()
                parts.append(f'<p><strong>{_esc(label)}:</strong> {_esc(val)}</p>')
        parts.append('</div>')

    # -- Tags --
    tags = osce_data.get("tags", {})
    if tags and isinstance(tags, dict):
        tag_parts = []
        for key in ("pattern", "tissue", "mechanism"):
            val = tags.get(key)
            if val:
                tag_parts.append(f'<span class="osce-tag">{_esc(key)}: {_esc(val)}</span>')
        if tag_parts:
            parts.append(
                f'<div class="osce-section" data-section="tags">'
                f'<p>{" &nbsp; ".join(tag_parts)}</p>'
                f'</div>'
            )

    # -- OSCE Station --
    osce = osce_data.get("osce", {})
    if osce:
        parts.append('<div class="osce-section" data-section="osce">')
        parts.append('<h4>OSCE Station</h4>')

        prompt = osce.get("prompt")
        if prompt:
            parts.append(f'<p><strong>Examiner prompt:</strong> <em>{_esc(prompt)}</em></p>')

        answer = osce.get("expected_answer", {})
        if answer:
            parts.append('<h5>Expected Answer</h5>')
            for field in ("approach", "key_finding", "diagnosis", "urgency"):
                val = answer.get(field)
                if val:
                    label = field.replace("_", " ").title()
                    parts.append(f'<p><strong>{_esc(label)}:</strong> {_esc(val)}</p>')

        script = osce.get("model_script")
        if script:
            parts.append(
                f'<div class="osce-model-script">'
                f'<h5>Model Answer Script</h5>'
                f'<blockquote>{_esc(script)}</blockquote>'
                f'</div>'
            )
        parts.append('</div>')

    # -- Explanation --
    explanation = osce_data.get("explanation", {})
    if explanation:
        has_content = any(explanation.get(k) for k in explanation)
        if has_content:
            parts.append('<div class="osce-section" data-section="explanation">')
            parts.append('<h4>Explanation</h4>')
            for field in ("pattern_recognition", "mechanism", "why_it_matters",
                          "systematic_check", "normal_landmarks", "common_pitfalls",
                          "confirm_normal_checklist"):
                val = explanation.get(field)
                if val:
                    label = field.replace("_", " ").title()
                    parts.append(f'<p><strong>{_esc(label)}:</strong> {_esc(val)}</p>')
            parts.append('</div>')

    # -- Visual Hook --
    hook = osce_data.get("visual_hook")
    if hook:
        parts.append(
            f'<div class="osce-section" data-section="visual_hook">'
            f'<h4>Visual Hook</h4>'
            f'<p><em>{_esc(hook)}</em></p>'
            f'</div>'
        )

    # -- Teaching Points --
    points = osce_data.get("teaching_points", [])
    if points:
        parts.append('<div class="osce-section" data-section="teaching_points">')
        parts.append('<h4>Teaching Points</h4>')
        parts.append('<ul>')
        for pt in points:
            if isinstance(pt, str) and pt.strip():
                parts.append(f'<li>{_esc(pt.strip())}</li>')
        parts.append('</ul>')
        parts.append('</div>')

    return "\n".join(parts)
