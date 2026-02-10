"""
AI Algorithmic Reporter Module

DEPRECATED (Feb 2026): Being phased out in favor of ai_smart_reporter.py.
Smart Reporter provides interactive walkthrough (Scene 1) and one-shot generation
(via "Generate Full Report Directly" which auto-selects normal findings).
Kept for backward compatibility with /api/algorithms/generate cache pipeline.

Generates step-by-step reporting algorithms that mirror how an experienced radiologist
reads and reports a scan. Produces a practical reporting guide with PACS report,
differentials, and recommendations — NOT educational material.

Separate from ai_prelim.py (which generates FRCR study material for the suggest-case flow).
"""

import json
import os
import re
import logging

import requests

logger = logging.getLogger(__name__)


class AlgorithmicReporterError(Exception):
    """Raised when algorithmic report generation fails."""
    pass


# ==================== SYSTEM PROMPT ====================

SYSTEM_PROMPT = (
    "You are a consultant radiologist with extensive daily PACS reporting experience. "
    "You generate step-by-step reporting algorithms and draft PACS reports. "
    "Output valid JSON only. No markdown. No text outside the JSON object."
)


# ==================== USER PROMPT TEMPLATE ====================

USER_PROMPT_TEMPLATE = """Your task is to generate a step-by-step reporting algorithm that mirrors how an
experienced radiologist actually reads and reports a scan in clinical practice.

This is NOT educational material. This is a practical reporting guide and report generator.

The output will be used:
- During active case reporting as a cognitive checklist
- To auto-generate a draft PACS report the radiologist will review and edit before signing

INPUTS:
<diagnosis>{diagnosis}</diagnosis>
<body_section>{body_section}</body_section>
<notes>{notes}</notes>

The diagnosis tells you what condition the algorithm covers. But the reporting walkthrough
must start from the clinical question (e.g., "headache, query SAH") and work systematically
toward confirming or excluding that diagnosis — mirroring how you would actually read the
scan before knowing the answer.

If diagnosis is vague or symptom-based, use it as the indication and generate a broader
systematic approach. If body_section is empty, infer from the diagnosis.

OUTPUT FORMAT (STRICT — valid JSON only, no markdown, no text outside JSON):
{{
  "algorithmic_approach_html": "",
  "differential_diagnosis": [],
  "recommendations": [],
  "pacs_report": "",
  "key_findings_checklist": [],
  "pitfalls": [],
  "sources": [],
  "warnings": [],
  "suggested_keywords": []
}}

FIELD SPECIFICATIONS:

1. algorithmic_approach_html (MOST IMPORTANT)
Step-by-step walkthrough of how to read and report the scan.

Every step must be a DECISION POINT that answers:
- What am I looking for?
- What does finding it mean?
- What does NOT finding it mean?

Do NOT include pathophysiology, epidemiology, or etiology unless it directly changes what
to look for on the scan.

BAD (educational fluff): "Extradural hematomas arise from middle meningeal artery rupture,
typically associated with temporal bone fractures. They occur in 1-3% of head injuries..."

GOOD (reporting algorithm): "Biconvex extra-axial collection? Check: Does it cross suture
lines? (No = extradural). Check temporal bone for fracture. Measure maximum thickness.
Assess midline shift."

Use ONLY these CSS classes (pre-defined in the app):
- <div class="diagnosis-box"> — protocol title/summary/final synthesis
- <div class="key-finding"> — green border: key imaging findings to look for
- <div class="differential-dx"> — purple border: differential considerations
- <div class="pitfall"> — red border: traps, must-not-miss, overcall/undercall risks
- <div class="clinical-note"> — teal border: clinical context, when to escalate
- <div class="staging-info"> — grey border: grading/staging if relevant
- <div class="image-finding"> — orange border: specific imaging features to check
- <span class="measurement"> — monospace for size thresholds and measurements
- <span class="anatomy-label"> — teal pill badge for anatomical structures
- <span class="important-text"> — bold red for critical/life-threatening flags
- <span class="highlight-red"> — red background highlight for red-flag items
- <div class="two-column"> — side-by-side layout (put two child divs inside)
- <table class="table table-sm table-bordered"> — for grading/comparison tables

Structure the algorithm as:
a. Start with indication and modality appropriateness
b. Stepwise systematic review of anatomy (in actual scan-reading order)
c. Key discriminating findings with conditional branching
d. Final diagnostic synthesis in a .diagnosis-box

Tone: Direct, practical, no teaching fluff. Use reporting-safe hedging language.
Do NOT use <html>, <head>, <body> tags, inline styles, markdown, or classes not listed above.

2. differential_diagnosis (ARRAY)
Each entry:
{{
  "diagnosis": "",
  "likelihood": "high | moderate | low",
  "rationale": "",
  "distinguishing_features": []
}}
- Only include differentials genuinely confusable on the imaging modality described
- Do NOT list rare diagnoses for academic completeness
- Distinguishing features must be imaging-based
- Order by likelihood (highest first)

3. recommendations (ARRAY)
Each entry:
{{
  "recommendation": "",
  "rationale": "",
  "urgency": "immediate | routine | elective"
}}
Include: additional imaging, clinical correlation, follow-up, urgent escalation.
Do NOT give treatment instructions unless imaging-related.

4. pacs_report (PLAIN TEXT — NOT HTML)
Draft framework the radiologist will review and edit before signing.
Must be realistic enough to use as a starting point.

Exact structure:
INDICATION:
[Clinical indication inferred from diagnosis and notes]

TECHNIQUE:
[Realistic and specific. E.g., "CT head without contrast. Axial 5mm sections with bone
and soft tissue algorithm. No prior available for comparison."]

FINDINGS:
[Structured by anatomical compartment. Describe expected findings for the diagnosis.
Use standard radiology phrasing with appropriate hedging.]

IMPRESSION:
[Most important first: life-threatening > clinically significant > incidental.
End with "Clinical correlation is recommended." as safety default.]

RECOMMENDATIONS:
[Aligned with the recommendations array. Optional if covered in impression.]

5. key_findings_checklist (ARRAY)
Things you must actively LOOK FOR on the scan before signing off — your mental to-do list.
E.g., "Assess lesion margins", "Look for adjacent fat stranding", "Measure maximum diameter",
"Check for vascular involvement", "Review bones on soft tissue window".
NOT a summary of the diagnosis.

6. pitfalls (ARRAY)
What can go WRONG in your interpretation: overcalls, mimics, technical limitations,
undercalling risks. Keep practical and experience-based.

7. sources (ARRAY)
Each entry:
{{
  "name": "Guideline or system name",
  "year": "Year or version",
  "relevance": "Brief note on why referenced"
}}
Only include actionable guidelines (grading systems, appropriateness criteria).

8. warnings (MANDATORY — always include at least one)
Always include: "This is an AI-generated reporting framework. All findings must be verified
against actual imaging before clinical use."
Add more if: diagnosis is probabilistic, imaging overlap exists, clinical correlation essential.

9. suggested_keywords (ARRAY)
8-12 concise search terms a radiologist would type. Include: diagnosis name, body region,
modality, key differentials, grading system names.

QUALITY CHECK — verify before responding:
- Would a consultant radiologist actually use this while reporting?
- Does the algorithm follow real scan-reading order?
- Is every step a decision point (not a teaching paragraph)?
- Is the PACS report copy-paste ready and realistic?
- Are differentials genuinely confusable on imaging?
- Have you included at least one warning?
If not, revise before outputting."""


# ==================== MAIN GENERATOR ====================

def generate_algorithmic_report(diagnosis, body_section='', notes=''):
    """
    Generate a reporting algorithm with PACS report using Claude API.

    Args:
        diagnosis: Suspected or confirmed diagnosis
        body_section: Anatomical region (optional)
        notes: Clinical context (optional)

    Returns:
        dict with: algorithmic_approach_html, differential_diagnosis, recommendations,
        pacs_report, key_findings_checklist, pitfalls, sources, warnings,
        suggested_keywords, model, token_count
    """
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise AlgorithmicReporterError("RadInsight Intelligence API key not configured.")

    effective_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    user_prompt = USER_PROMPT_TEMPLATE.format(
        diagnosis=diagnosis,
        body_section=body_section or 'Not specified — infer from diagnosis',
        notes=notes or 'None',
    )

    payload = {
        "model": effective_model,
        "max_tokens": 8000,
        "temperature": 0.3,
        "system": SYSTEM_PROMPT,
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
            timeout=120,
        )
    except requests.exceptions.Timeout:
        raise AlgorithmicReporterError("Algorithmic report generation timed out. Please try again.")
    except requests.exceptions.RequestException as exc:
        raise AlgorithmicReporterError(f"Failed to connect to RadInsight Intelligence: {exc}")

    if response.status_code >= 300:
        detail = response.text[:500]
        raise AlgorithmicReporterError(
            f"RadInsight Intelligence error (HTTP {response.status_code}): {detail}"
        )

    result = response.json()
    content = result.get("content", [])
    if not content:
        raise AlgorithmicReporterError("Empty response from RadInsight Intelligence.")

    text = content[0].get("text", "")
    if not text:
        raise AlgorithmicReporterError("No text in RadInsight Intelligence response.")

    # Parse JSON response
    parsed = _parse_algorithmic_response(text)

    parsed['model'] = effective_model
    parsed['token_count'] = result.get("usage", {}).get("output_tokens", 0)
    parsed['provider'] = 'claude'

    return parsed


# ==================== RESPONSE PARSER ====================

def _parse_algorithmic_response(text):
    """Parse algorithmic reporter JSON response with fallback."""
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
                raise AlgorithmicReporterError(
                    "Failed to parse algorithmic report response as JSON."
                )
        else:
            raise AlgorithmicReporterError(
                "Algorithmic report response was not valid JSON."
            )

    # Validate and set defaults for all required fields
    parsed.setdefault('algorithmic_approach_html', '')
    parsed.setdefault('differential_diagnosis', [])
    parsed.setdefault('recommendations', [])
    parsed.setdefault('pacs_report', '')
    parsed.setdefault('key_findings_checklist', [])
    parsed.setdefault('pitfalls', [])
    parsed.setdefault('sources', [])
    parsed.setdefault('warnings', [
        'This is an AI-generated reporting framework. All findings must be verified against actual imaging before clinical use.'
    ])
    parsed.setdefault('suggested_keywords', [])

    # Validate differential_diagnosis structure
    valid_diffs = []
    for d in parsed.get('differential_diagnosis', []):
        if isinstance(d, dict) and d.get('diagnosis'):
            valid_diffs.append({
                'diagnosis': d.get('diagnosis', ''),
                'likelihood': d.get('likelihood', 'moderate'),
                'rationale': d.get('rationale', ''),
                'distinguishing_features': d.get('distinguishing_features', []),
            })
    parsed['differential_diagnosis'] = valid_diffs

    # Validate recommendations structure
    valid_recs = []
    for r in parsed.get('recommendations', []):
        if isinstance(r, dict) and r.get('recommendation'):
            valid_recs.append({
                'recommendation': r.get('recommendation', ''),
                'rationale': r.get('rationale', ''),
                'urgency': r.get('urgency', 'routine'),
            })
    parsed['recommendations'] = valid_recs

    # Validate sources structure
    valid_sources = []
    for s in parsed.get('sources', []):
        if isinstance(s, dict) and s.get('name'):
            valid_sources.append({
                'name': s.get('name', ''),
                'year': s.get('year', ''),
                'relevance': s.get('relevance', ''),
            })
        elif isinstance(s, str):
            valid_sources.append({'name': s, 'year': '', 'relevance': ''})
    parsed['sources'] = valid_sources

    # Ensure lists are lists of strings where expected
    for field in ['key_findings_checklist', 'pitfalls', 'warnings', 'suggested_keywords']:
        if not isinstance(parsed[field], list):
            parsed[field] = []
        parsed[field] = [str(item) for item in parsed[field] if item]

    return parsed
