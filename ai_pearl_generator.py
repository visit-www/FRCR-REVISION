"""
AI Pearl Generator Module

Generates richly-formatted radiology teaching pearls for admin curation.
Structured JSON output from Claude is rendered into Bootstrap 5 cards
with color-coded sections and Radiopaedia image integration.

Pattern: ai_client.py wrappers with module-specific PearlGeneratorError.
"""

import logging
import os

from ai_client import (
    call_claude as _call_claude_raw,
    parse_json_response as _parse_json_raw,
    AIClientError,
)

logger = logging.getLogger(__name__)


# ── Module-specific error ────────────────────────────────────────────

class PearlGeneratorError(AIClientError):
    """Raised when pearl generation fails."""
    pass


# ── API helpers (same pattern as ai_smart_reporter.py) ───────────────

def _call_claude(system_prompt, user_prompt, model=None, max_tokens=4000,
                 temperature=0.3, timeout=60):
    return _call_claude_raw(
        system_prompt, user_prompt, model=model,
        max_tokens=max_tokens, temperature=temperature,
        timeout=timeout, error_class=PearlGeneratorError,
    )


def _parse_json_response(text):
    return _parse_json_raw(text, error_class=PearlGeneratorError)


# ── Prompts ──────────────────────────────────────────────────────────

PEARL_SYSTEM_PROMPT = (
    "You are an expert radiology educator writing a comprehensive teaching "
    "pearl for FRCR exam trainees and radiology registrars. You produce ONLY "
    "valid JSON. No markdown fences, no explanation outside the JSON object.\n\n"
    "Your goal: create a pearl that a trainee can read in 3-5 minutes and walk "
    "away with a practical, memorable understanding of the diagnosis — what to "
    "look for on the workstation, what to not miss, and what to tell the "
    "clinician.\n\n"
    "RULES:\n"
    "1. Every claim must be radiologically accurate. Do not fabricate criteria "
    "or statistics.\n"
    "2. Use precise anatomical and radiological terminology.\n"
    "3. Use UK English spelling (e.g. tumour, centre, colour).\n"
    "4. Tables are preferred for structured comparison data (mimics, search "
    "patterns, grading).\n"
    "5. Keep each section focused and concise — avoid filler sentences.\n"
    "6. The search_pattern section must give a PRACTICAL step-by-step approach "
    "a registrar would follow at the PACS workstation. Include window/level "
    "settings, reformats, and specific things to click through.\n"
    "7. aunt_minnie should describe the pathognomonic or near-pathognomonic "
    "appearance — the one finding that clinches the diagnosis. If no true Aunt "
    "Minnie exists, describe the most characteristic constellation.\n"
    "8. mimics must give genuinely useful differentiators — not just 'clinical "
    "correlation.' Include at least one imaging discriminator per mimic.\n"
    "9. critical_findings should list findings that require immediate "
    "communication (urgent call-back criteria). If there are none specific to "
    "this diagnosis, list the general body-region critical findings.\n"
    "10. clinical_correlation should answer: what is the clinician actually "
    "asking when they request this scan, and what do they need in the report?\n"
    "11. workstation_tips should include specific technical advice: window "
    "settings, reconstruction algorithms, contrast timing, comparison "
    "techniques.\n"
    "12. Tags should be lowercase, specific, and useful for search (e.g. "
    "'liver', 'hepatocellular carcinoma', 'lirads', 'arterial enhancement').\n"
    "13. Provide 4-7 search pattern steps, 3-5 mimics, 2-4 critical findings, "
    "3-5 report essentials, and 3-5 workstation tips.\n\n"
    "Output ONLY the JSON object. No markdown. No explanation."
)

PEARL_USER_PROMPT = """\
Generate a radiology teaching pearl for:

TOPIC: {topic}
MODALITY: {modality}
BODY SECTION: {body_section}

Return a single JSON object with this exact schema:

{{
  "title": "Short display title (e.g. 'Hepatocellular Carcinoma on MRI')",
  "search_pattern": {{
    "steps": [
      {{
        "step": 1,
        "action": "What to do at the workstation",
        "detail": "Specific technique, window, or finding to assess",
        "key_finding": "What you are looking for at this step"
      }}
    ],
    "summary_note": "One-sentence summary of the systematic approach"
  }},
  "aunt_minnie": {{
    "description": "The pathognomonic or most characteristic appearance",
    "classic_presentation": "Brief clinical scenario where this is the spot diagnosis",
    "confidence_note": "How confident can you be with imaging alone?"
  }},
  "mimics": [
    {{
      "diagnosis": "Name of the mimic",
      "key_differentiator": "The ONE imaging feature that distinguishes it",
      "pitfall": "Common mistake trainees make with this mimic"
    }}
  ],
  "critical_findings": [
    {{
      "finding": "The critical finding",
      "action": "What to do (e.g. 'Urgent call to referrer')",
      "timeframe": "How quickly to act"
    }}
  ],
  "clinical_correlation": {{
    "clinical_question": "What is the referrer usually asking?",
    "report_essentials": ["List of things that MUST be in the report"],
    "mdm_note": "What the MDT/tumour board needs from radiology"
  }},
  "workstation_tips": [
    "Specific technical tip for reading this study"
  ],
  "tags": ["lowercase", "search", "tags"]
}}"""


# ── Generation function ──────────────────────────────────────────────

def generate_pearl(topic, modality='', body_section=''):
    """
    Generate a structured radiology teaching pearl via Claude.

    Returns:
        dict with keys: pearl_data, pearl_html, title, tags, model, token_count
    Raises:
        PearlGeneratorError on failure
    """
    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    user_prompt = PEARL_USER_PROMPT.format(
        topic=topic,
        modality=modality or 'Any/All',
        body_section=body_section or 'Not specified',
    )

    text, model_used, token_count = _call_claude(
        system_prompt=PEARL_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        max_tokens=4000,
        temperature=0.3,
        timeout=90,
    )

    pearl_data = _parse_json_response(text)

    required = ['title', 'search_pattern', 'aunt_minnie', 'mimics',
                'critical_findings', 'clinical_correlation']
    missing = [k for k in required if k not in pearl_data]
    if missing:
        raise PearlGeneratorError(f"AI response missing keys: {missing}")

    pearl_html = render_pearl_html(pearl_data)

    return {
        'pearl_data': pearl_data,
        'pearl_html': pearl_html,
        'title': pearl_data.get('title', topic),
        'tags': ','.join(pearl_data.get('tags', [])),
        'model': model_used,
        'token_count': token_count,
    }


# ── Radiopaedia image helper ────────────────────────────────────────

def fetch_radiopaedia_image(topic, modality=''):
    """Fetch a single best Radiopaedia image for the pearl. Returns dict or None."""
    try:
        from radiopaedia_search_service import search_radiopaedia_images
        results = search_radiopaedia_images(
            diagnosis=topic,
            modality=modality,
            max_per_type=3,
        )
        if results:
            return results[0]
    except Exception as exc:
        logger.warning("Radiopaedia image fetch failed for '%s': %s", topic, exc)
    return None


# ── HTML renderer ────────────────────────────────────────────────────

def _esc(text):
    """HTML-escape a string."""
    if not text:
        return ''
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def _card_open(bs_color, icon, title):
    """Open a Bootstrap card with colored left border and header."""
    return (
        f'<div class="card mb-3 border-start border-4 border-{bs_color}">'
        f'<div class="card-header bg-{bs_color} bg-opacity-10 py-2">'
        f'<i class="fas {icon} me-2 text-{bs_color}"></i>'
        f'<strong class="text-{bs_color}">{title}</strong>'
        f'</div>'
        f'<div class="card-body py-2">'
    )


def _card_open_custom(color, icon, title):
    """Open a card with a custom hex colour (for brand-neutral teal)."""
    return (
        f'<div class="card mb-3" style="border-left: 4px solid {color};">'
        f'<div class="card-header py-2" style="background: {color}15;">'
        f'<i class="fas {icon} me-2" style="color: {color};"></i>'
        f'<strong style="color: {color};">{title}</strong>'
        f'</div>'
        f'<div class="card-body py-2">'
    )


def _card_close():
    return '</div></div>'


def render_pearl_html(pearl_data, radiopaedia_image=None):
    """
    Render structured pearl JSON into Bootstrap 5 HTML cards.

    Args:
        pearl_data: Parsed JSON dict from Claude
        radiopaedia_image: Optional dict from search_radiopaedia_images()

    Returns:
        HTML string
    """
    parts = []

    # Title
    title = _esc(pearl_data.get('title', ''))
    parts.append(f'<h3 class="pearl-gen-title mb-3">{title}</h3>')

    # ── 1. Search Pattern (Blue / primary) ──
    sp = pearl_data.get('search_pattern', {})
    if sp:
        parts.append(_card_open('primary', 'fa-search', 'Readout Search Pattern'))
        steps = sp.get('steps', [])
        if steps:
            parts.append(
                '<table class="table table-sm table-bordered mb-2">'
                '<thead><tr>'
                '<th style="width:50px;">Step</th>'
                '<th>Action</th>'
                '<th>Detail</th>'
                '<th>Key Finding</th>'
                '</tr></thead><tbody>'
            )
            for s in steps:
                parts.append(
                    f'<tr>'
                    f'<td class="text-center fw-bold">{_esc(str(s.get("step", "")))}</td>'
                    f'<td>{_esc(s.get("action", ""))}</td>'
                    f'<td>{_esc(s.get("detail", ""))}</td>'
                    f'<td><strong>{_esc(s.get("key_finding", ""))}</strong></td>'
                    f'</tr>'
                )
            parts.append('</tbody></table>')
        note = sp.get('summary_note', '')
        if note:
            parts.append(
                f'<p class="text-muted fst-italic mb-0">'
                f'<small>{_esc(note)}</small></p>'
            )
        parts.append(_card_close())

    # ── 2. Aunt Minnie (Green / success) ──
    am = pearl_data.get('aunt_minnie', {})
    if am:
        parts.append(_card_open('success', 'fa-bullseye', 'Aunt Minnie'))
        desc = am.get('description', '')
        if desc:
            parts.append(
                f'<p><strong>Classic Appearance:</strong> {_esc(desc)}</p>'
            )
        pres = am.get('classic_presentation', '')
        if pres:
            parts.append(
                f'<p><strong>Classic Presentation:</strong> {_esc(pres)}</p>'
            )
        conf = am.get('confidence_note', '')
        if conf:
            parts.append(
                f'<p class="text-muted fst-italic mb-0">'
                f'<small>{_esc(conf)}</small></p>'
            )
        parts.append(_card_close())

    # ── 3. Mimics & Pitfalls (Amber / warning) ──
    mimics = pearl_data.get('mimics', [])
    if mimics:
        parts.append(
            _card_open('warning', 'fa-exclamation-triangle', 'Mimics &amp; Pitfalls')
        )
        parts.append(
            '<table class="table table-sm table-bordered mb-0">'
            '<thead><tr>'
            '<th>Mimic</th>'
            '<th>Key Differentiator</th>'
            '<th>Pitfall</th>'
            '</tr></thead><tbody>'
        )
        for m in mimics:
            parts.append(
                f'<tr>'
                f'<td><strong>{_esc(m.get("diagnosis", ""))}</strong></td>'
                f'<td>{_esc(m.get("key_differentiator", ""))}</td>'
                f'<td class="text-danger">{_esc(m.get("pitfall", ""))}</td>'
                f'</tr>'
            )
        parts.append('</tbody></table>')
        parts.append(_card_close())

    # ── 4. Critical Findings (Red / danger) ──
    crits = pearl_data.get('critical_findings', [])
    if crits:
        parts.append(_card_open('danger', 'fa-bolt', 'Critical Findings'))
        parts.append(
            '<table class="table table-sm table-bordered mb-0">'
            '<thead><tr>'
            '<th>Finding</th>'
            '<th>Action Required</th>'
            '<th>Timeframe</th>'
            '</tr></thead><tbody>'
        )
        for c in crits:
            parts.append(
                f'<tr>'
                f'<td><strong>{_esc(c.get("finding", ""))}</strong></td>'
                f'<td>{_esc(c.get("action", ""))}</td>'
                f'<td>{_esc(c.get("timeframe", ""))}</td>'
                f'</tr>'
            )
        parts.append('</tbody></table>')
        parts.append(_card_close())

    # ── 5. Clinical Correlation (Teal / brand-neutral) ──
    cc = pearl_data.get('clinical_correlation', {})
    if cc:
        parts.append(
            _card_open_custom('#5E899E', 'fa-stethoscope', 'Clinical Correlation')
        )
        cq = cc.get('clinical_question', '')
        if cq:
            parts.append(
                f'<p><strong>Clinical Question:</strong> {_esc(cq)}</p>'
            )
        essentials = cc.get('report_essentials', [])
        if essentials:
            parts.append(
                '<p class="mb-1"><strong>Report Must Include:</strong></p>'
                '<ul class="mb-2">'
            )
            for e in essentials:
                parts.append(f'<li>{_esc(e)}</li>')
            parts.append('</ul>')
        mdm = cc.get('mdm_note', '')
        if mdm:
            parts.append(
                f'<p class="mb-0"><strong>MDT Note:</strong> {_esc(mdm)}</p>'
            )
        parts.append(_card_close())

    # ── 6. Workstation Summary (Dark) ──
    tips = pearl_data.get('workstation_tips', [])
    if tips:
        parts.append(_card_open('dark', 'fa-desktop', 'Workstation Summary'))
        parts.append('<ul class="mb-0">')
        for t in tips:
            parts.append(f'<li>{_esc(t)}</li>')
        parts.append('</ul>')
        parts.append(_card_close())

    # ── 7. Radiopaedia Image (optional) ──
    if radiopaedia_image:
        img_url = _esc(radiopaedia_image.get('link', ''))
        thumb_url = _esc(radiopaedia_image.get('thumbnail_link', '') or img_url)
        case_title = _esc(radiopaedia_image.get('title', 'Radiopaedia Case'))
        case_url = _esc(radiopaedia_image.get('case_url', ''))
        license_text = _esc(radiopaedia_image.get('license', 'CC BY-NC-SA 3.0'))

        parts.append(
            '<div class="card mt-3 border">'
            '<div class="card-body text-center p-3">'
            f'<a href="{case_url}" target="_blank" rel="noopener noreferrer">'
            f'<img src="{thumb_url}" alt="{case_title}" '
            f'class="img-fluid rounded" style="max-height: 300px;" loading="lazy">'
            f'</a>'
            f'<p class="mt-2 mb-0 small text-muted">'
            f'<a href="{case_url}" target="_blank" rel="noopener noreferrer">'
            f'{case_title}</a>'
            f' &mdash; Radiopaedia.org &mdash; {license_text}'
            f'</p>'
            '</div></div>'
        )

    return '\n'.join(parts)
