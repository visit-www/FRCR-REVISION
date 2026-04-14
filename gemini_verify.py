"""
Gemini Cross-Model Verification (CMV) module.

Sends entire AI-generated content to Gemini Flash for independent
fact-checking of statistical claims, measurements, and medical facts.

Usage:
    from gemini_verify import verify_content

    result = verify_content(
        ai_text="The normal CBD diameter is up to 6mm...",
        body_section="Abdomen",
        modality="CT",
        topic="common bile duct",
    )
    # result['claims'] — list of {claim_text, claim_type, verdict, confidence, reasoning, correction}
    # result['summary'] — {agreed: N, disputed: N, uncertain: N, total: N}
    # result['raw_response'] — Gemini's raw text (for debugging)
"""

import os
import json
import time
import logging
import requests

logger = logging.getLogger(__name__)

GEMINI_MODELS = ['gemini-2.5-flash', 'gemini-2.5-flash-lite']  # Primary + lite fallback (separate rate limits)
GEMINI_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/models'


def _get_gemini_key():
    """Read API key at call time (not import time) so dotenv has loaded."""
    return os.environ.get('GEMINI_API_KEY', '')

# ---------------------------------------------------------------------------
# Prompt — the critical piece
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """You are a specialist radiology fact-checker performing Cross-Model Verification (CMV).

You will receive AI-generated radiology educational content along with context metadata (body section, imaging modality, clinical topic). Your job is to independently verify every statistical claim, measurement, prevalence rate, dose, threshold, grading criterion, and guideline reference in the content.

## RULES

1. **Find ALL verifiable claims** in the content — do not rely on any pre-extracted list. Scan the ENTIRE text thoroughly, including tables, lists, and nested content. Extract EVERY claim that contains a verifiable fact, specifically:
   - Normal measurement ranges
   - Abnormal thresholds and cut-off values — these are CRITICAL to verify
   - Diagnostic associations between a measurement and a specific pathology
   - Prevalence and incidence rates
   - Dose values and weight-based calculations
   - Grading and staging criteria
   - Guideline citations and recommendations
   - Sensitivity/specificity and comparative diagnostic accuracy claims
   - Clinical significance thresholds linking a value to a clinical outcome

   **IMPORTANT:** A single table row or paragraph may contain MULTIPLE verifiable claims. A normal range is one claim; an abnormal threshold with its associated pathology is a SEPARATE claim. Extract them individually.

2. **Context matters** — always consider:
   - Adult vs paediatric (assume adult unless stated otherwise)
   - Male vs female (note if measurement is sex-dependent)
   - Imaging modality (CT vs MRI vs US — normal ranges differ)
   - Measurement method/plane when relevant

3. **Tolerance for acceptable variation:**
   - Measurements: values within 15% of established ranges = AGREE
   - Prevalence: overlapping ranges = AGREE
   - Staging/grading criteria: STRICT matching required (wrong stage = DISAGREE)
   - Dose values: STRICT matching required (safety-critical)

4. **Verdicts:**
   - **AGREE** — the claim is accurate or within acceptable tolerance
   - **DISAGREE** — the claim is factually incorrect; provide the correct value
   - **UNCERTAIN** — you cannot confidently verify this claim (niche, ambiguous, or you lack knowledge). Do NOT guess. Say UNCERTAIN.

5. **Do NOT fabricate citations.** Do not cite specific papers, DOIs, or authors. You may reference general source types (textbooks, society guidelines) only if you are confident they exist.

6. **Classify each claim** as one of: measurement, epidemiology, criteria, dose, guideline, comparative

7. **Confidence level** for each verdict: HIGH, MEDIUM, or LOW

## OUTPUT FORMAT

Return ONLY a valid JSON array. No markdown, no code fences, no commentary outside the array.
If there are no verifiable claims, return an empty array: []

Each element:
{
  "claim_text": "the exact claim from the content",
  "claim_type": "measurement|epidemiology|criteria|dose|guideline|comparative",
  "verdict": "AGREE|DISAGREE|UNCERTAIN",
  "confidence": "HIGH|MEDIUM|LOW",
  "reasoning": "one sentence explaining your assessment",
  "correction": "correct value/fact (only if DISAGREE, otherwise null)"
}"""


def _build_user_prompt(ai_text: str, body_section: str = '', modality: str = '', topic: str = '') -> str:
    """Build the user prompt with content + context metadata."""
    context_parts = []
    if body_section:
        context_parts.append(f"Body section: {body_section}")
    if modality:
        context_parts.append(f"Imaging modality: {modality}")
    if topic:
        context_parts.append(f"Clinical topic: {topic}")

    context_block = '\n'.join(context_parts) if context_parts else 'No additional context provided.'

    return f"""## Context
{context_block}

## AI-Generated Content to Verify
{ai_text}"""


def _parse_gemini_response(text: str) -> list[dict]:
    """Parse Gemini's JSON response, handling common formatting issues."""
    text = text.strip()

    # Strip markdown code fences if present
    if text.startswith('```'):
        lines = text.split('\n')
        # Remove first and last lines (``` markers)
        lines = [l for l in lines if not l.strip().startswith('```')]
        text = '\n'.join(lines).strip()

    if not text:
        return []

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and 'claims' in parsed:
            return parsed['claims']
        return []
    except json.JSONDecodeError:
        # Try to extract JSON array from the text
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        logger.warning("Failed to parse Gemini CMV response: %s", text[:200])
        return []


def _extract_text_from_ai_output(ai_output) -> str:
    """Extract readable text from various AI output formats.

    For structured anatomy dicts, produces labelled sections so Gemini
    can understand the context of each claim (e.g., which structure a
    measurement belongs to).
    """
    if isinstance(ai_output, str):
        import re
        if '<' in ai_output and '>' in ai_output:
            html = ai_output
            # Preserve table structure: add separators for rows and cells
            html = re.sub(r'</tr>', '\n', html)
            html = re.sub(r'</td>', ' | ', html)
            html = re.sub(r'</th>', ' | ', html)
            # Preserve line breaks
            html = re.sub(r'<br\s*/?>', '\n', html)
            html = re.sub(r'</li>', '\n', html)
            html = re.sub(r'</p>', '\n', html)
            html = re.sub(r'</h[1-6]>', '\n', html)
            # Strip remaining tags
            plain = re.sub(r'<[^>]+>', ' ', html)
            # Clean up whitespace but preserve newlines
            plain = re.sub(r'[ \t]+', ' ', plain)
            plain = re.sub(r'\n\s*\n', '\n', plain)
            return plain.strip()
        return ai_output

    if isinstance(ai_output, dict):
        text_parts = []

        # Title and overview
        title = ai_output.get('title', '')
        if title:
            text_parts.append(f"Title: {title}")
        overview = ai_output.get('overview', '')
        if overview:
            text_parts.append(f"Overview: {overview}")

        # Common top-level text fields (non-anatomy)
        for key in ['answer', 'teaching_point', 'guideline_citation',
                     'pearl_text', 'report_text', 'full_report', 'html']:
            val = ai_output.get(key, '')
            if isinstance(val, str) and val.strip():
                text_parts.append(val)

        # Key points list
        kp = ai_output.get('key_points', [])
        if isinstance(kp, list):
            text_parts.extend(str(item) for item in kp if item)

        # Insights dict (Smart Reporter)
        insights = ai_output.get('insights', {})
        if isinstance(insights, dict):
            for k, v in insights.items():
                if isinstance(v, str) and v.strip() and k != 'verifiable_claims':
                    text_parts.append(v)

        # --- Anatomy structured fields (with labels for context) ---

        # Key structures
        structures = ai_output.get('key_structures', [])
        if structures and isinstance(structures, list):
            text_parts.append("\n## Key Structures")
            for s in structures:
                if not isinstance(s, dict):
                    continue
                name = s.get('name', 'Unknown')
                parts = [f"Structure: {name}"]
                for k in ('imaging_landmark', 'relationships', 'reporting_relevance'):
                    v = s.get(k, '')
                    if v:
                        parts.append(f"  {k.replace('_', ' ').title()}: {v}")
                text_parts.append('\n'.join(parts))

        # Normal variants
        variants = ai_output.get('normal_variants', [])
        if variants and isinstance(variants, list):
            text_parts.append("\n## Normal Variants")
            for v in variants:
                if not isinstance(v, dict):
                    continue
                name = v.get('variant', v.get('name', 'Unknown'))
                parts = [f"Variant: {name}"]
                for k in ('prevalence', 'why_it_exists', 'imaging_pitfall'):
                    val = v.get(k, '')
                    if val:
                        parts.append(f"  {k.replace('_', ' ').title()}: {val}")
                text_parts.append('\n'.join(parts))

        # Measurements
        measurements = ai_output.get('measurements', [])
        if measurements and isinstance(measurements, list):
            text_parts.append("\n## Measurements")
            for m in measurements:
                if not isinstance(m, dict):
                    continue
                what = m.get('what', 'Unknown')
                normal = m.get('normal', '')
                threshold = m.get('abnormal_threshold', '')
                text_parts.append(
                    f"Measurement: {what}\n"
                    f"  Normal: {normal}\n"
                    f"  Abnormal threshold: {threshold}"
                )

        # Diagnostic appearances
        appearances = ai_output.get('diagnostic_appearances', [])
        if appearances and isinstance(appearances, list):
            text_parts.append("\n## Diagnostic Appearances")
            for a in appearances:
                if not isinstance(a, dict):
                    continue
                finding = a.get('finding', 'Unknown')
                parts = [f"Finding: {finding}"]
                for k in ('modality', 'significance'):
                    val = a.get(k, '')
                    if val:
                        parts.append(f"  {k.title()}: {val}")
                text_parts.append('\n'.join(parts))

        # Pathology at this site
        pathologies = ai_output.get('pathology_at_this_site', [])
        if pathologies and isinstance(pathologies, list):
            text_parts.append("\n## Pathology at This Site")
            for p in pathologies:
                if not isinstance(p, dict):
                    continue
                name = p.get('pathology', 'Unknown')
                parts = [f"Pathology: {name}"]
                for k in ('key_finding', 'clinical_question'):
                    val = p.get(k, '')
                    if val:
                        parts.append(f"  {k.replace('_', ' ').title()}: {val}")
                text_parts.append('\n'.join(parts))

        if text_parts:
            return '\n'.join(text_parts)

    return str(ai_output)[:3000]


def verify_content(
    ai_output,
    body_section: str = '',
    modality: str = '',
    topic: str = '',
    timeout: int = 30,
) -> dict:
    """Send AI content to Gemini Flash for cross-model verification.

    Args:
        ai_output: The AI-generated content (str, HTML, or structured dict).
        body_section: Anatomical region (e.g., "Abdomen", "Head and Neck").
        modality: Imaging modality (e.g., "CT", "MRI", "US").
        topic: Clinical topic for context (e.g., "common bile duct").
        timeout: Request timeout in seconds.

    Returns:
        dict with keys: claims, summary, raw_response, elapsed_ms, model, error
    """
    start_time = time.time()

    api_key = _get_gemini_key()
    if not api_key:
        logger.warning("GEMINI_API_KEY not set — skipping cross-model verification")
        return {
            'claims': [],
            'summary': {'agreed': 0, 'disputed': 0, 'uncertain': 0, 'total': 0},
            'raw_response': '',
            'elapsed_ms': 0,
            'model': None,
            'error': 'GEMINI_API_KEY not configured',
        }

    # Extract text from whatever format the AI output is in
    ai_text = _extract_text_from_ai_output(ai_output)
    if not ai_text or len(ai_text.strip()) < 20:
        return {
            'claims': [],
            'summary': {'agreed': 0, 'disputed': 0, 'uncertain': 0, 'total': 0},
            'raw_response': '',
            'elapsed_ms': 0,
            'model': GEMINI_MODELS[0],
            'error': None,
        }

    # Truncate very long content to stay within free tier limits
    # Gemini 2.5 Flash supports 1M tokens; 15K chars is ~4K tokens — well within limits
    if len(ai_text) > 30000:
        ai_text = ai_text[:30000] + '\n[...content truncated for verification]'

    user_prompt = _build_user_prompt(ai_text, body_section, modality, topic)

    payload = {
        'contents': [
            {
                'role': 'user',
                'parts': [{'text': user_prompt}],
            }
        ],
        'systemInstruction': {
            'parts': [{'text': _SYSTEM_PROMPT}]
        },
        'generationConfig': {
            'temperature': 0.1,  # Low temperature for factual accuracy
            'maxOutputTokens': 8192,
            'responseMimeType': 'application/json',
        },
    }

    # Try each model in order (2.5 Flash first, fallback to 2.0 Flash)
    claims = []
    raw_text = ''
    used_model = GEMINI_MODELS[0]
    last_error = None

    for model_name in GEMINI_MODELS:
        url = f'{GEMINI_BASE_URL}/{model_name}:generateContent?key={api_key}'
        try:
            resp = requests.post(
                url,
                json=payload,
                timeout=timeout,
                headers={'Content-Type': 'application/json'},
            )
            if resp.status_code in (503, 429):
                wait = 5 if resp.status_code == 429 else 1
                logger.warning("Gemini %s returned %d — waiting %ds then trying fallback",
                               model_name, resp.status_code, wait)
                last_error = f'{model_name}: {resp.status_code}'
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()

            raw_text = ''
            candidates = data.get('candidates', [])
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                for part in parts:
                    if 'text' in part:
                        raw_text += part['text']

            claims = _parse_gemini_response(raw_text)
            used_model = model_name

            for claim in claims:
                claim['verdict'] = (claim.get('verdict') or 'uncertain').lower()
                claim['confidence'] = (claim.get('confidence') or 'medium').lower()
                claim['claim_type'] = (claim.get('claim_type') or 'unknown').lower()
                if claim['verdict'] not in ('agree', 'disagree', 'uncertain'):
                    claim['verdict'] = 'uncertain'

            last_error = None
            break  # Success — don't try next model

        except requests.exceptions.Timeout:
            logger.warning("Gemini %s timed out after %ds — trying fallback", model_name, timeout)
            last_error = f'{model_name}: timeout'
            continue
        except requests.exceptions.RequestException as exc:
            logger.warning("Gemini %s failed: %s — trying fallback", model_name, exc)
            last_error = str(exc)
            continue

    if last_error and not claims:
        logger.error("All Gemini models failed: %s", last_error)
        return {
            'claims': [],
            'summary': {'agreed': 0, 'disputed': 0, 'uncertain': 0, 'total': 0},
            'raw_response': '',
            'elapsed_ms': int((time.time() - start_time) * 1000),
            'model': used_model,
            'error': last_error,
        }

    elapsed_ms = int((time.time() - start_time) * 1000)

    # Build summary
    agreed = sum(1 for c in claims if c.get('verdict') == 'agree')
    disputed = sum(1 for c in claims if c.get('verdict') == 'disagree')
    uncertain = sum(1 for c in claims if c.get('verdict') == 'uncertain')

    summary = {
        'agreed': agreed,
        'disputed': disputed,
        'uncertain': uncertain,
        'total': len(claims),
    }

    logger.info(
        "Gemini CMV for '%s' (%s/%s): %d claims — %d agreed, %d disputed, %d uncertain, %dms",
        topic, body_section, modality, len(claims), agreed, disputed, uncertain, elapsed_ms,
    )

    return {
        'claims': claims,
        'summary': summary,
        'raw_response': raw_text,
        'elapsed_ms': elapsed_ms,
        'model': used_model,
        'error': None,
    }
