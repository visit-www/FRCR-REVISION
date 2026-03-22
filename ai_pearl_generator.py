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
    "You are a senior consultant radiologist writing a concise teaching pearl "
    "for radiology registrars and consultants. You produce ONLY valid JSON. "
    "No markdown fences, no explanation outside the JSON object.\n\n"
    "Your goal: a pearl a registrar can read in 2-3 minutes and walk away "
    "knowing what to look for, what to not miss, and what to tell the "
    "clinician. Brevity is a virtue — every sentence must earn its place.\n\n"
    "RULES:\n"
    "1. Every claim must be radiologically accurate. Do not fabricate.\n"
    "2. Use precise anatomical and radiological terminology. UK English.\n"
    "3. Be CONCISE — short punchy sentences, no filler, no preamble.\n"
    "4. search_pattern: practical PACS workstation steps. Include window/level "
    "settings and reformats only when they genuinely help.\n"
    "5. aunt_minnie: the pathognomonic or near-pathognomonic appearance — "
    "the one finding that clinches the diagnosis. If no true Aunt Minnie "
    "exists, describe the most characteristic constellation. Keep each "
    "field to one sentence.\n"
    "6. mimics: genuinely useful imaging discriminators — not 'clinical "
    "correlation.' One clear differentiator per mimic.\n"
    "7. critical_findings: urgent call-back criteria only.\n"
    "8. clinical_correlation: what the clinician needs in the report.\n"
    "9. workstation_tips: specific technical advice, not generic.\n"
    "10. image_guidance: describe how key findings appear on imaging so an "
    "admin can search for matching reference images. Include modality, "
    "sequence/phase, and the specific visual appearance (e.g. 'T2 hyperintense "
    "rim with central low signal on axial MRI' or 'hyperdense crescent on "
    "unenhanced CT').\n"
    "11. Counts: 3-4 search pattern steps, 2-3 mimics, 2-3 critical findings, "
    "3-4 report essentials, 2-3 workstation tips, 1-2 image descriptions.\n"
    "12. Tags: lowercase, specific, useful for search.\n\n"
    "Output ONLY the JSON object. No markdown. No explanation."
)

PEARL_USER_PROMPT = """\
Generate a concise radiology teaching pearl for:

TOPIC: {topic}
MODALITY: {modality}
BODY SECTION: {body_section}

Return a single JSON object with this exact schema:

{{
  "title": "Short title (e.g. 'HCC on MRI')",
  "search_pattern": {{
    "steps": [
      {{
        "step": 1,
        "action": "What to do at the workstation",
        "detail": "Specific technique or finding to assess",
        "key_finding": "What you are looking for"
      }}
    ],
    "summary_note": "One-sentence systematic approach"
  }},
  "aunt_minnie": {{
    "description": "The pathognomonic appearance (1 sentence)",
    "classic_presentation": "Brief clinical scenario (1 sentence)",
    "confidence_note": "Imaging-alone confidence (1 sentence)"
  }},
  "mimics": [
    {{
      "diagnosis": "Mimic name",
      "key_differentiator": "ONE imaging feature that distinguishes it",
      "pitfall": "Common trainee mistake"
    }}
  ],
  "critical_findings": [
    {{
      "finding": "The critical finding",
      "action": "What to do",
      "timeframe": "How quickly"
    }}
  ],
  "clinical_correlation": {{
    "clinical_question": "What is the referrer asking?",
    "report_essentials": ["Must-include items in the report"],
    "mdm_note": "What MDT needs from radiology (1 sentence)"
  }},
  "workstation_tips": [
    "Specific technical tip"
  ],
  "image_guidance": [
    {{
      "modality": "CT/MRI/US etc.",
      "sequence_or_phase": "e.g. arterial phase, T2 FLAIR, lung window",
      "appearance": "What the key finding looks like (e.g. 'hyperdense crescent on unenhanced CT')",
      "search_term": "Suggested image search term for finding a reference image"
    }}
  ],
  "image_captions": [
    "Brief clinical description of what a key reference image for this topic would show (1-2 sentences). Describe the specific imaging appearance, modality, and diagnostic significance. Provide 1-3 captions."
  ],
  "tags": ["lowercase", "search", "tags"]
}}

KEEP IT SHORT. 3-4 search steps, 2-3 mimics, 2-3 critical findings, 3-4 report essentials, 2-3 workstation tips, 1-2 image descriptions."""


# ── Generation function ──────────────────────────────────────────────

def generate_pearl(topic, modality='', body_section='', additional_context=''):
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
    if additional_context:
        user_prompt += (
            f"\n\n=== ADDITIONAL CONTEXT PROVIDED BY ADMIN ===\n"
            f"{additional_context}\n"
            f"=== END CONTEXT ===\n\n"
            f"Use the above as preferred references to enrich and ground your output. "
            f"Cite specific details from these sources where relevant, but also draw on "
            f"your broader medical knowledge — do not limit your response exclusively to "
            f"these references."
        )

    text, model_used, token_count = _call_claude(
        system_prompt=PEARL_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        max_tokens=3000,
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


# ── Radiopaedia image helpers ──────────────────────────────────────

def fetch_radiopaedia_images(topic, modality='', max_images=3):
    """Fetch multiple Radiopaedia images with author attribution.

    Returns list of normalised image dicts:
        [{url, title, case_url, license, author, source_domain}]
    """
    try:
        from radiopaedia_search_service import (
            search_radiopaedia_images, scrape_case_author,
        )
        raw = search_radiopaedia_images(
            diagnosis=topic,
            modality=modality,
            max_per_type=max_images,
        )
        results = []
        for r in raw[:max_images]:
            author = None
            try:
                author = scrape_case_author(r.get('case_url', ''))
            except Exception:
                pass
            results.append({
                'url': r.get('thumbnail_link') or r.get('link', ''),
                'title': r.get('title', 'Radiopaedia Case'),
                'case_url': r.get('case_url', ''),
                'license': r.get('license', 'CC BY-NC-SA 3.0'),
                'author': author,
                'source_domain': 'radiopaedia.org',
            })
        return results
    except Exception as exc:
        logger.warning("Radiopaedia image fetch failed for '%s': %s", topic, exc)
    return []


def fetch_radiopaedia_image(topic, modality=''):
    """Fetch single image (backward compat). Returns dict or None."""
    results = fetch_radiopaedia_images(topic, modality, max_images=1)
    return results[0] if results else None


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


def render_reference_images_html(images, captions=None):
    """Render a list of reference images into a Bootstrap card with attribution.

    Args:
        images: list of dicts with keys: url, title, case_url, license, author, source_domain
        captions: optional list of AI-generated captions (paired by index)

    Returns:
        HTML string (empty string if no images)
    """
    if not images:
        return ''
    captions = captions or []

    parts = [
        '<div class="card mt-3 border">',
        '<div class="card-header bg-light py-2">',
        '<i class="fas fa-images me-2 text-muted"></i>',
        '<strong class="text-muted">Reference Images</strong>',
        '</div>',
        '<div class="card-body p-3">',
        '<div class="row g-3">',
    ]

    for i, img in enumerate(images[:5]):
        img_url = _esc(img.get('url', ''))
        title = _esc(img.get('title', 'Reference Image'))
        case_url = _esc(img.get('case_url', ''))
        license_text = _esc(img.get('license', ''))
        author = _esc(img.get('author', ''))
        source = _esc(img.get('source_domain', ''))
        caption = _esc(captions[i]) if i < len(captions) else ''

        # Single image gets full width, multiple get 2-column
        col_class = 'col-12' if len(images) == 1 else 'col-12 col-md-6'

        parts.append(f'<div class="{col_class}">')
        parts.append('<div class="text-center">')

        # Image with optional link
        if case_url:
            parts.append(
                f'<a href="{case_url}" target="_blank" rel="noopener noreferrer">'
                f'<img src="{img_url}" alt="{title}" '
                f'class="img-fluid rounded" style="max-height: 280px;" loading="lazy">'
                f'</a>'
            )
        else:
            parts.append(
                f'<img src="{img_url}" alt="{title}" '
                f'class="img-fluid rounded" style="max-height: 280px;" loading="lazy">'
            )

        # AI-generated caption
        if caption:
            parts.append(
                f'<p class="mt-1 mb-0 small text-muted fst-italic">{caption}</p>'
            )

        # Attribution line
        attr_parts = []
        if case_url and title:
            attr_parts.append(
                f'<a href="{case_url}" target="_blank" rel="noopener noreferrer">{title}</a>'
            )
        elif title:
            attr_parts.append(title)
        if author:
            attr_parts.append(author)
        if source:
            attr_parts.append(source)
        if license_text:
            attr_parts.append(license_text)
        if attr_parts:
            parts.append(
                f'<p class="mt-1 mb-0 small text-muted">'
                + ' &mdash; '.join(attr_parts)
                + '</p>'
            )

        parts.append('</div></div>')

    parts.append('</div></div></div>')
    return '\n'.join(parts)


def render_pearl_html(pearl_data, radiopaedia_image=None, reference_images=None):
    """
    Render structured pearl JSON into Bootstrap 5 HTML cards.

    Args:
        pearl_data: Parsed JSON dict from Claude
        radiopaedia_image: DEPRECATED — single image dict (backward compat)
        reference_images: List of normalised image dicts for multi-image rendering

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

    # ── 7. Image Guidance (Info) ──
    img_guide = pearl_data.get('image_guidance', [])
    if img_guide:
        parts.append(_card_open('info', 'fa-camera', 'Image Guidance'))
        parts.append(
            '<div class="table-responsive"><table class="table table-sm table-bordered mb-0">'
            '<thead><tr><th>Modality</th><th>Sequence / Phase</th>'
            '<th>Appearance</th><th>Search Term</th></tr></thead><tbody>'
        )
        for ig in img_guide:
            parts.append(
                f'<tr><td>{_esc(ig.get("modality", ""))}</td>'
                f'<td>{_esc(ig.get("sequence_or_phase", ""))}</td>'
                f'<td>{_esc(ig.get("appearance", ""))}</td>'
                f'<td><em>{_esc(ig.get("search_term", ""))}</em></td></tr>'
            )
        parts.append('</tbody></table></div>')
        parts.append(_card_close())

    # ── 8. Reference Images (multi-image or legacy single) ──
    captions = pearl_data.get('image_captions', [])
    if reference_images:
        parts.append(render_reference_images_html(reference_images, captions))
    elif radiopaedia_image:
        # Backward compat: convert legacy single image dict to list format
        legacy = {
            'url': radiopaedia_image.get('thumbnail_link') or radiopaedia_image.get('link', ''),
            'title': radiopaedia_image.get('title', 'Radiopaedia Case'),
            'case_url': radiopaedia_image.get('case_url', ''),
            'license': radiopaedia_image.get('license', 'CC BY-NC-SA 3.0'),
            'author': radiopaedia_image.get('author'),
            'source_domain': 'radiopaedia.org',
        }
        parts.append(render_reference_images_html([legacy], captions))

    return '\n'.join(parts)
