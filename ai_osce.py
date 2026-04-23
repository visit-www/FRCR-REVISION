"""
AI OSCE Case Generator

Generates radiology OSCE cases for 3rd-year medical students.
Two prompt variants: pathological cases and normal studies.

Output: structured JSON for the OSCE guide page — editable in TinyMCE
when rendered to HTML.

Prompt Version: v9 (reset to v1 quality + selective improvements)
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

# Standard views per modality — what students must identify and why
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
# SYSTEM PROMPT (v1 base + teacher mindset + no-redundancy principle)
# ============================================================================

SYSTEM_PROMPT = """You are an expert clinical radiology educator designing OSCE training cases for 3rd-year medical students.

Think like a teacher sitting with a student at a lightbox — explain what matters, skip what doesn't, and never say the same thing twice.

TEACHING STYLE:
- Write as if explaining what to LOOK FOR and WHY, not listing what you found. "Look along both renal outlines for small dense opacities" not "no calcifications seen."
- Explain the reasoning: WHY you check gas pattern first (because obstruction and perforation are the emergencies), WHERE to look (not just what the structure is called), and WHAT normal looks like so abnormal jumps out.
- Measurements should be taught in context: "small bowel should be under 3 cm — if you see a loop wider than that, think obstruction" not just "small bowel less than 3 cm."

EDUCATIONAL GOALS:
- Teach pattern recognition (what do I see?)
- Teach mechanism (why does it look like this?)
- Reinforce systematic approach (how to read the image)
- Train OSCE-style verbal responses (concise, structured, examiner-ready)
- Prioritise clinically important and exam-relevant diagnoses

STUDENT LEVEL:
- 3rd-year medical student
- Basic anatomy knowledge
- Early clinical exposure
- Preparing for OSCE exams

CONSTRAINTS:
- Do NOT include rare or specialist-only diagnoses
- Do NOT include excessive detail beyond student level
- Do NOT assume advanced radiology knowledge
- Ensure findings are CLASSIC and recognisable
- Use simple visual language for findings (describe what is SEEN, not the diagnosis)
- Never repeat the same information across sections — if you said it once, do not say it again
- If a section adds nothing for this specific case, set it to null
- Plain text only — NO HTML, NO markdown formatting

Output JSON only. No markdown fences. No explanations outside the JSON structure."""


# ============================================================================
# PATHOLOGICAL CASE PROMPT (v1 structure + visual_hook + views.notes)
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
    approach = _MODALITY_APPROACHES.get(modality, "Systematic review of all visible structures")
    views = _MODALITY_VIEWS.get(modality, "Standard views for this modality")

    context_block = ""
    if additional_context:
        context_block = f"""
=== ADDITIONAL CONTEXT PROVIDED BY ADMIN ===
{additional_context}
=== END CONTEXT ===

Use the above as preferred references to enrich and ground your output.
Cite specific details from these sources where relevant, but also draw on
your broader medical knowledge.
"""

    return f"""Generate ONE high-quality radiology OSCE case.
{context_block}
IMPORTANT -- VIEW IDENTIFICATION:
The student MUST identify the radiographic view as the FIRST thing they say.
Standard views for {modality_label}:
{views}

INPUT
====================================================================

Diagnosis: {diagnosis}
Modality: {modality_label}
Category: {category} (Emergency = life-threatening, Spotter = classic recognisable finding, Common = frequently seen)
Tags: {tags if tags else 'Not specified'}
Notes: {notes if notes else 'None'}

SYSTEMATIC APPROACH FOR THIS MODALITY:
{approach}

====================================================================
OUTPUT STRUCTURE (strict JSON)
====================================================================

Return valid JSON with this exact structure:

{{
  "diagnosis": "{diagnosis}",
  "modality": "{modality}",
  "category": "{category}",
  "difficulty": "Easy or Moderate (choose based on how recognisable the findings are)",

  "views": {{
    "obtained": "Which view(s) this case image would be (e.g., 'PA erect chest radiograph')",
    "notes": "One line per view. Format:\\nPA erect — standard view, accurate heart size, sharp costophrenic angles\\nAP — used for sick patients, magnifies heart\\nLateral — retrosternal space, posterior angles"
  }},

  "tags": {{
    "pattern": "visual pattern category (e.g., air, fluid, blood, bone disruption, soft tissue, calcification)",
    "tissue": "affected tissue/structure (e.g., pleural, parenchymal, cortical, intra-axial)"
  }},

  "osce": {{
    "prompt": "The examiner's instruction (e.g., 'Please interpret this chest X-ray')",

    "expected_answer": {{
      "approach": "START by identifying the view: 'This is a [view] [modality].' Then demonstrate the systematic approach. Put each step on its own line, starting with the category name. Use the {modality} approach: {approach}. Example format:\\nAirway — trachea is midline, no deviation...\\nBreathing — lung fields are clear bilaterally...\\nCirculation — heart size normal, cardiothoracic ratio under 0.5...",
      "key_finding": "Describe what is SEEN on the image in simple visual language. Do not name the diagnosis here -- describe the appearance (e.g., 'visible line in right hemithorax with absent lung markings beyond it', NOT 'pneumothorax')",
      "diagnosis": "The diagnosis with laterality/specifics as appropriate",
      "urgency": "Clinical urgency statement -- is this an emergency? What action is needed?"
    }},

    "model_script": "A 2-4 sentence OSCE-ready verbal response. Must sound like a student speaking to an examiner. Structure: 1) identify the view, 2) state the key finding, 3) give the diagnosis, 4) state urgency/management if relevant."
  }},

  "explanation": {{
    "pattern_recognition": "Link the visual pattern to the diagnosis: 'If you see X -> think Y -> because Z'. Make this memorable and concise.",
    "mechanism": "Explain WHY the imaging looks like this. Keep simple but conceptually correct. A 3rd-year student should understand this.",
    "why_it_matters": "Clinical significance -- why must a student know this? Focus on patient safety and exam relevance. Set to null if urgency already covers this."
  }},

  "teaching_points": [
    "3-5 high-yield, memorable teaching points",
    "Include classic signs, named signs, measurement thresholds where relevant",
    "Include common examiner follow-up questions with brief answers",
    "Include key differentials if relevant (1-2 main mimics)",
    "Do NOT repeat information already covered in approach or explanation"
  ],

  "visual_hook": "One memorable sentence: the single visual pattern that makes this diagnosis click. Something a student remembers at 2am on call."
}}

====================================================================
QUALITY RULES
====================================================================

1. APPROACH must use the modality-specific systematic method listed above
2. KEY FINDING must describe what is SEEN, not the diagnosis name
3. MODEL SCRIPT must sound like a student speaking, not a textbook
4. MECHANISM must be simple enough for a 3rd-year to understand
5. TEACHING POINTS must be memorable and exam-focused
6. No section should repeat information from another section
7. All text must be plain text -- NO HTML, NO markdown
8. Diagnosis must be the anchor -- do not rephrase or replace it"""


# ============================================================================
# NORMAL CASE PROMPT (v1 structure + visual_hook + views.notes)
# ============================================================================

def _build_normal_prompt(case_context):
    """Build prompt for a normal study OSCE case."""
    modality = case_context.get("modality", "").strip()
    notes = case_context.get("notes", "").strip()
    additional_context = case_context.get("additional_context", "").strip()

    modality_label = _MODALITY_MAP.get(modality, modality)
    approach = _MODALITY_APPROACHES.get(modality, "Systematic review of all visible structures")
    views = _MODALITY_VIEWS.get(modality, "Standard views for this modality")

    context_block = ""
    if additional_context:
        context_block = f"""
=== ADDITIONAL CONTEXT PROVIDED BY ADMIN ===
{additional_context}
=== END CONTEXT ===

Use the above as preferred references to enrich and ground your output.
"""

    return f"""Generate ONE high-quality NORMAL radiology OSCE case for a 3rd-year medical student.

The purpose of a normal case is to teach the systematic approach and help students recognise what NORMAL looks like -- so they can spot abnormal.

IMPORTANT -- VIEW IDENTIFICATION:
The student MUST identify the radiographic view as the FIRST thing they say.
Standard views for {modality_label}:
{views}

INPUT
====================================================================

Modality: {modality_label}
Category: Normal
Notes: {notes if notes else 'None'}

SYSTEMATIC APPROACH FOR THIS MODALITY:
{approach}

====================================================================
OUTPUT STRUCTURE (strict JSON)
====================================================================

Return valid JSON with this exact structure:

{{
  "diagnosis": "Normal {modality_label}",
  "modality": "{modality}",
  "category": "Normal",
  "difficulty": "Easy",

  "views": {{
    "obtained": "Which standard view(s) are shown (e.g., 'PA erect chest radiograph')",
    "notes": "One line per view. Format:\\nAP supine — standard, shows gas pattern and organ outlines\\nErect — air-fluid levels, free subdiaphragmatic gas\\nLateral decubitus — alternative when patient cannot stand"
  }},

  "tags": {{
    "pattern": "normal",
    "tissue": "all structures"
  }},

  "osce": {{
    "prompt": "Please interpret this {modality_label.lower()}",

    "expected_answer": {{
      "approach": "START by identifying the view: 'This is a [view] [modality].' Then walk through the COMPLETE systematic approach, checking EVERY step and confirming each is normal. Put each step on its own line, starting with the category name. Use: {approach}. Example format:\\nGas pattern — bowel gas scattered and non-distended, small bowel under 3 cm...\\nFree air — no subdiaphragmatic gas...\\nCalcifications — trace renal outlines for calculi...",
      "key_finding": "No acute abnormality identified. All structures appear normal.",
      "diagnosis": "Normal {modality_label}",
      "urgency": "No urgent findings. Correlate clinically."
    }},

    "model_script": "A 3-5 sentence OSCE-ready presentation of a normal study. Walk through the systematic approach, confirming each element is normal. Conclude with 'In summary, this is a normal {modality_label.lower()} with no acute abnormality.' This should demonstrate to the examiner that you have a thorough, systematic method."
  }},

  "explanation": {{
    "normal_landmarks": "One structure per line. Format: Structure name — normal value/threshold. Example:\\nSmall bowel diameter — less than 3 cm\\nLarge bowel diameter — less than 6 cm (caecum less than 9 cm)\\nPsoas shadows — bilateral, symmetric, visible from T12 to iliac fossa",
    "common_pitfalls": "List 3-5 things that look abnormal on a normal {modality_label.lower()} but are actually normal variants or artefacts. Include: what it looks like, what it mimics, and how to tell it is normal. These are common OSCE traps."
  }},

  "teaching_points": [
    "3-5 teaching points about reading normal studies",
    "Include 'always check' review areas that are commonly missed",
    "Include normal variants that trap students in OSCEs",
    "Include the examiner's likely follow-up: 'What would make you worried on this image?'",
    "Do NOT repeat information already covered in approach or explanation"
  ],

  "visual_hook": "One memorable sentence about what makes a normal study convincingly normal -- what pattern of normality should the student recognise."
}}

====================================================================
QUALITY RULES
====================================================================

1. The systematic approach walkthrough is the CORE of this case
2. Common pitfalls/normal variants must be specific to {modality_label}
3. Model script must demonstrate a thorough, methodical approach
4. No section should repeat information from another section
5. All text must be plain text -- NO HTML, NO markdown
6. Focus on what students commonly miss or mistake for pathology"""


# ============================================================================
# API CALL
# ============================================================================

def generate_osce_case(case_context):
    """
    Generate an OSCE case using the Anthropic Messages API.

    Args:
        case_context: dict with keys:
            - diagnosis (required for pathological; ignored for normal)
            - modality (required) -- one of: CXR, AXR, Knee X-ray,
              Shoulder X-ray, Elbow X-ray, Foot X-ray, CT Brain
            - category (required) -- Emergency, Spotter, Common, or Normal
            - tags (optional) -- comma-separated tag string
            - notes (optional) -- additional context
            - model (optional) -- Claude model override

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
        "prompt_version": "osce-v9",
        "generated_at": datetime.utcnow().isoformat(),
        "output": parsed,
        "raw_response": text,
        "usage": {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        },
    }


# ============================================================================
# HTML RENDERER -- converts OSCE JSON to TinyMCE-editable HTML
# ============================================================================

def render_osce_html(osce_data):
    """
    Convert OSCE case JSON into editable HTML for TinyMCE storage.

    The HTML uses semantic class names (osce-section, osce-*) so the
    OSCE guide page can parse and render it, while remaining fully
    editable in TinyMCE for admin tweaks.

    Args:
        osce_data: dict -- the parsed OSCE case JSON (the "output" field)

    Returns:
        str -- HTML string
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
