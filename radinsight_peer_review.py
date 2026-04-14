"""
RadInsight Peer Review — Cross-Model Verification (CMV) module.

Post-processes AI-generated medical content to:
1. Send entire output to Gemini Flash for independent fact-checking
2. Persist verified claims in PeerReviewClaim DB table
3. Render inline verification badges (5 states)
4. Render content-level trust badge, references, disclaimers
5. Support admin override and manual reference attachment

Industry term: Cross-Model Verification (CMV) / LLM-as-Judge

Usage:
    from radinsight_peer_review import peer_review

    result = peer_review(ai_output_dict, topic="circle of Willis",
                         context="anatomy", body_section="Head and Neck",
                         modality="MRI")
"""

import re
import logging
import time
from datetime import datetime
from html import escape as html_escape
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Badge rendering — 5 states
# ---------------------------------------------------------------------------

_BADGE_CONFIG = {
    'agreed': {
        'css_class': 'cmv-badge-agreed',
        'icon': 'fa-check-circle',
        'color': '#198754',  # green
        'tooltip': 'Cross-Model Verified: An independent AI model agrees with this claim.',
    },
    'disputed': {
        'css_class': 'cmv-badge-disputed',
        'icon': 'fa-times-circle',
        'color': '#dc3545',  # red
        'tooltip': 'Disputed: An independent AI model disagrees with this claim. Check the correction.',
    },
    'uncertain': {
        'css_class': 'cmv-badge-uncertain',
        'icon': 'fa-question-circle',
        'color': '#ffc107',  # amber
        'tooltip': 'Uncertain: Could not be independently verified. Treat with caution.',
    },
    'admin_verified': {
        'css_class': 'cmv-badge-admin-verified',
        'icon': 'fa-shield-alt',
        'color': '#0d6efd',  # blue
        'tooltip': 'Manually verified by admin with reference.',
    },
    'dismissed': {
        'css_class': 'cmv-badge-dismissed',
        'icon': '',
        'color': '',
        'tooltip': '',
    },
    'pending': {
        'css_class': 'cmv-badge-uncertain',
        'icon': 'fa-hourglass-half',
        'color': '#6c757d',  # grey
        'tooltip': 'Verification pending.',
    },
}


def _esc(text) -> str:
    if not text:
        return ''
    return html_escape(str(text))


def render_verification_badge(claim: dict, is_admin: bool = False) -> str:
    """Render inline badge for a single claim.

    Args:
        claim: Dict with at minimum 'badge_state' key. For DB claims use .to_dict().
               For Gemini-direct claims, pass the processed dict.
        is_admin: If True, renders admin controls (edit/dismiss).
    """
    state = claim.get('badge_state', claim.get('gemini_verdict', 'uncertain'))
    if state == 'dismissed' and not is_admin:
        return ''

    cfg = _BADGE_CONFIG.get(state, _BADGE_CONFIG['uncertain'])

    # Build tooltip based on badge state
    reasoning = claim.get('gemini_reasoning', '')
    correction = claim.get('gemini_correction', '') or claim.get('correction', '')
    admin_notes = claim.get('admin_notes', '')
    ref_url = claim.get('admin_reference_url', '')
    ref_title = claim.get('admin_reference_title', '')
    confidence = claim.get('gemini_confidence', '') or claim.get('confidence', '')

    if state == 'admin_verified':
        tooltip = 'Admin verified.'
        if reasoning:
            tooltip += f' RadInsights CMV: {reasoning}'
        if ref_title:
            tooltip += f' | Ref: {ref_title}'
        if admin_notes:
            tooltip += f' | Notes: {admin_notes}'
        if ref_url:
            tooltip += ' | Click to view reference.'
    elif state == 'disputed':
        tooltip = admin_notes or ''
        if correction:
            tooltip += f'{" | " if tooltip else ""}Correction: {correction}'
        if ref_title:
            tooltip += f' | Ref: {ref_title}'
        if ref_url:
            tooltip += ' | Click to view.'
    elif state == 'dismissed':
        tooltip = 'Dismissed by admin.'
        if admin_notes:
            tooltip += f' {admin_notes}'
    else:
        # agreed or uncertain
        tooltip = cfg['tooltip']
        if reasoning:
            tooltip += f' {reasoning}'
        if admin_notes:
            tooltip += f' | Admin: {admin_notes}'

    claim_id = claim.get('id', '')

    # Use data-bs attributes for Bootstrap tooltip (richer, not truncated)
    tooltip_attrs = (
        f'data-bs-toggle="tooltip" data-bs-placement="top" data-bs-html="true" '
        f'data-bs-title="{_esc(tooltip)}"'
    )

    if state == 'admin_verified' and ref_url:
        badge_html = (
            f'<a href="{_esc(ref_url)}" target="_blank" rel="noopener noreferrer" '
            f'class="cmv-badge {cfg["css_class"]}" '
            f'{tooltip_attrs} data-claim-id="{claim_id}">'
            f'<i class="fas {cfg["icon"]}"></i>'
            f'</a>'
        )
    else:
        conf_attr = f' data-confidence="{_esc(confidence)}"' if confidence else ''
        badge_html = (
            f'<span class="cmv-badge {cfg["css_class"]}" '
            f'{tooltip_attrs} '
            f'data-claim-id="{claim_id}"{conf_attr}>'
            f'<i class="fas {cfg["icon"]}"></i>'
            f'</span>'
        )

    # Admin inline edit button (admin-only)
    if is_admin and claim_id:
        badge_html += (
            f' <button class="cmv-admin-edit btn btn-link btn-sm p-0" '
            f'data-claim-id="{claim_id}" '
            f'title="Edit verification">'
            f'<i class="fas fa-pen" style="font-size:0.6rem;"></i>'
            f'</button>'
        )

    return badge_html


def render_content_trust_badge(summary: dict, content_type: str = '', content_id: str = '') -> str:
    """Render the content-level CMV trust badge shown at top of content."""
    total = summary.get('total', 0)
    agreed = summary.get('agreed', 0)
    disputed = summary.get('disputed', 0)
    uncertain = summary.get('uncertain', 0)
    cmv_pending = summary.get('cmv_pending', False)

    # If CMV was skipped/failed, show pending badge
    if cmv_pending or (total == 0 and not summary.get('cmv_complete', False)):
        return (
            f'<div class="cmv-trust-badge cmv-trust-pending" '
            f'data-content-type="{_esc(content_type)}" data-content-id="{_esc(content_id)}">'
            f'<div class="cmv-trust-header">'
            f'<i class="fas fa-hourglass-half me-2"></i>'
            f'<strong>Pending Peer Review</strong>'
            f' <span class="badge bg-secondary">awaiting verification</span>'
            f'</div>'
            f'</div>'
        )

    if total == 0:
        return ''

    # Determine overall trust level
    if disputed > 0:
        trust_class = 'cmv-trust-caution'
        trust_icon = 'fa-exclamation-triangle'
        trust_label = 'Cross-Model Verified — Issues Found'
    elif uncertain > total * 0.5:
        trust_class = 'cmv-trust-partial'
        trust_icon = 'fa-shield-alt'
        trust_label = 'Cross-Model Verified — Partially'
    else:
        trust_class = 'cmv-trust-passed'
        trust_icon = 'fa-shield-alt'
        trust_label = 'Cross-Model Verified'

    stats_parts = []
    if agreed > 0:
        stats_parts.append(f'<span class="badge bg-success">{agreed} agreed</span>')
    if uncertain > 0:
        stats_parts.append(f'<span class="badge bg-warning text-dark">{uncertain} uncertain</span>')
    if disputed > 0:
        stats_parts.append(f'<span class="badge bg-danger">{disputed} disputed</span>')
    stats_html = ' '.join(stats_parts)

    return (
        f'<div class="cmv-trust-badge {trust_class}" '
        f'data-content-type="{_esc(content_type)}" data-content-id="{_esc(content_id)}">'
        f'<div class="cmv-trust-header">'
        f'<i class="fas {trust_icon} me-2"></i>'
        f'<strong>{trust_label}</strong>'
        f' {stats_html}'
        f' <button class="cmv-info-btn btn btn-link btn-sm p-0 ms-2" '
        f'data-bs-toggle="popover" data-bs-trigger="hover focus" '
        f'data-bs-html="true" data-bs-placement="bottom" '
        f'data-bs-content="'
        f'Each content generated by RadInsight Intelligence undergoes secondary '
        f'peer review through an independent AI model (Cross-Model Verification). '
        f'We also endeavour to verify as many claims as possible manually &mdash; '
        f'however you are advised to treat every piece of information as suggestive '
        f'and not prescriptive. Please verify claims from textbooks and reputed '
        f'peer-reviewed journals before using in routine practice.'
        f'">'
        f'<i class="fas fa-info-circle"></i> How this works'
        f'</button>'
        f'</div>'
        f'</div>'
    )


def render_disclaimer_html(summary: dict) -> str:
    """Render the peer review disclaimer banner."""
    total = summary.get('total', 0)
    agreed = summary.get('agreed', summary.get('verified', 0))
    disputed = summary.get('disputed', 0)
    uncertain = summary.get('uncertain', summary.get('unverified', 0))
    cmv_pending = summary.get('cmv_pending', False)

    if cmv_pending or (total == 0 and not summary.get('cmv_complete', False)):
        return (
            '<div class="peer-review-disclaimer cmv-disclaimer mt-2 mb-2" style="border-left-color:#6c757d;">'
            '<i class="fas fa-hourglass-half me-1" style="color:#6c757d;"></i>'
            '<strong>AI-Generated Revision Aid</strong> &mdash; '
            'Peer review pending. Verify all claims against your textbook before clinical use.'
            ' <span class="badge bg-secondary ms-1">pending verification</span>'
            '</div>'
        )

    badges = ''
    if total > 0:
        if agreed > 0:
            badges += f' <span class="badge bg-success ms-1">{agreed} agreed</span>'
        if uncertain > 0:
            badges += f' <span class="badge bg-warning text-dark ms-1">{uncertain} uncertain</span>'
        if disputed > 0:
            badges += f' <span class="badge bg-danger ms-1">{disputed} disputed</span>'

    return (
        '<div class="peer-review-disclaimer cmv-disclaimer mt-2 mb-2">'
        '<i class="fas fa-shield-alt me-1"></i>'
        '<strong>AI-Generated Revision Aid</strong> &mdash; '
        'Cross-model verified. Confirm critical measurements against your textbook.'
        f'{badges}'
        '</div>'
    )


def render_references_html(
    claims: list[dict],
    radiopaedia_url: Optional[str] = None,
    topic: str = '',
) -> str:
    """Render verified references section from admin-attached references."""
    # Collect admin-attached references
    refs = []
    for c in claims:
        url = c.get('admin_reference_url', '')
        title = c.get('admin_reference_title', '')
        if url:
            refs.append({'url': url, 'title': title or url})

    if not refs and not radiopaedia_url:
        return ''

    parts = [
        '<div class="peer-review-references cmv-references mt-3">',
        '<div class="card border">',
        '<div class="card-header bg-light py-2">',
        '<i class="fas fa-book-medical me-2 text-muted"></i>',
        '<strong class="text-muted">Verified References</strong>',
        '</div>',
        '<div class="card-body p-3">',
        '<ul class="list-unstyled mb-0">',
    ]

    if radiopaedia_url:
        parts.append(
            f'<li class="mb-2">'
            f'<i class="fas fa-globe me-1 text-info"></i>'
            f'<a href="{_esc(radiopaedia_url)}" target="_blank" rel="noopener noreferrer">'
            f'{_esc(topic.title())} &mdash; Radiopaedia.org</a>'
            f' <span class="badge bg-info text-white" style="font-size:0.6rem;">Radiopaedia</span>'
            f'</li>'
        )

    seen_urls = set()
    for ref in refs:
        if ref['url'] in seen_urls:
            continue
        seen_urls.add(ref['url'])
        source_badge = ''
        if 'pubmed' in ref['url'].lower() or 'doi.org' in ref['url'].lower():
            source_badge = ' <span class="badge bg-success" style="font-size:0.6rem;">PubMed</span>'
        elif 'radiopaedia' in ref['url'].lower():
            source_badge = ' <span class="badge bg-info text-white" style="font-size:0.6rem;">Radiopaedia</span>'
        parts.append(
            f'<li class="mb-2">'
            f'<i class="fas fa-file-medical me-1 text-success"></i>'
            f'<a href="{_esc(ref["url"])}" target="_blank" rel="noopener noreferrer">'
            f'{_esc(ref["title"])}</a>{source_badge}'
            f'</li>'
        )

    parts.extend(['</ul>', '</div>', '</div>', '</div>'])
    return '\n'.join(parts)


def render_flag_button_html(content_type: str = '', content_id: str = '') -> str:
    """Render the 'Flag Inaccuracy' button (uses global flag modal)."""
    return (
        f'<button class="btn btn-sm btn-outline-danger peer-review-flag mt-2" '
        f'onclick="openGlobalFlagModal({{contentType:\'{_esc(content_type)}\','
        f'contentId:\'{_esc(content_id)}\'}})">'
        f'<i class="fas fa-flag me-1"></i>Flag Inaccuracy'
        f'</button>'
    )


# ---------------------------------------------------------------------------
# Radiopaedia article verification (kept — simple HEAD check)
# ---------------------------------------------------------------------------
_radiopaedia_cache: dict[str, Optional[str]] = {}


def verify_radiopaedia_article(topic: str) -> Optional[str]:
    """Check if a Radiopaedia article exists. Returns verified URL or None."""
    import requests as req

    slug = re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')
    url = f"https://radiopaedia.org/articles/{slug}"

    if url in _radiopaedia_cache:
        return _radiopaedia_cache[url]

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
        }
        r = req.head(url, headers=headers, timeout=5, allow_redirects=True)
        if r.status_code == 200:
            final_url = r.url if r.url else url
            _radiopaedia_cache[url] = final_url
            return final_url
    except Exception as exc:
        logger.debug("Radiopaedia HEAD check failed for '%s': %s", url, exc)

    _radiopaedia_cache[url] = None
    return None


# ---------------------------------------------------------------------------
# DB persistence — store/retrieve claims
# ---------------------------------------------------------------------------

def _persist_claims(claims: list[dict], content_type: str, content_id: str,
                    body_section: str = '', modality: str = '', topic: str = '',
                    model: str = '') -> list:
    """Save Gemini-verified claims to PeerReviewClaim table.

    Returns list of PeerReviewClaim ORM objects (or dicts if DB unavailable).
    """
    try:
        from models import db, PeerReviewClaim
    except ImportError:
        logger.warning("Cannot import PeerReviewClaim model — returning raw claims")
        return claims

    db_claims = []
    try:
        # Delete ALL old claims for this content (re-verification = clean slate)
        PeerReviewClaim.query.filter_by(
            content_type=content_type,
            content_id=content_id or None,
        ).delete()

        for c in claims:
            prc = PeerReviewClaim(
                content_type=content_type,
                content_id=content_id or None,
                claim_text=c.get('claim_text', ''),
                claim_type=c.get('claim_type', 'unknown'),
                gemini_verdict=c.get('verdict', 'uncertain'),
                gemini_confidence=c.get('confidence', 'medium'),
                gemini_reasoning=c.get('reasoning', ''),
                gemini_correction=c.get('correction'),
                gemini_model=model,
                context_body_section=body_section,
                context_modality=modality,
                context_topic=topic,
            )
            db.session.add(prc)
            db_claims.append(prc)

        db.session.commit()
        logger.info("Persisted %d CMV claims for %s/%s", len(db_claims), content_type, content_id)

    except Exception as exc:
        logger.error("Failed to persist CMV claims: %s", exc)
        db.session.rollback()
        # Return raw dicts as fallback
        return claims

    return db_claims


def _load_claims_from_db(content_type: str, content_id: str) -> list[dict]:
    """Load persisted claims from DB. Returns list of dicts."""
    try:
        from models import PeerReviewClaim
        rows = PeerReviewClaim.query.filter_by(
            content_type=content_type,
            content_id=content_id or None,
        ).order_by(PeerReviewClaim.id).all()
        return [r.to_dict() for r in rows]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# HTML injection — inject inline badges into rendered content
# ---------------------------------------------------------------------------

def _inject_badges_into_html(html: str, claims: list[dict], is_admin: bool = False) -> str:
    """Inject CMV badges into rendered HTML near matching claim text.

    Tracks positions where badges have been injected to prevent duplicates
    when multiple claims reference the same number.
    """
    # Track character positions where badges have been injected
    badged_positions = set()

    for claim in claims:
        if claim.get('badge_state') == 'dismissed' and not is_admin:
            continue

        badge = render_verification_badge(claim, is_admin=is_admin)
        claim_text = claim.get('claim_text', '')
        if not claim_text or not badge:
            continue

        escaped_text = _esc(claim_text)

        # Try 1: exact match of claim text in HTML
        idx = html.find(escaped_text)
        if idx != -1 and idx not in badged_positions:
            # Check no badge already adjacent
            after = html[idx + len(escaped_text):idx + len(escaped_text) + 30]
            if 'cmv-badge' not in after:
                html = html[:idx + len(escaped_text)] + ' ' + badge + html[idx + len(escaped_text):]
                badged_positions.add(idx)
                continue

        # Try 2: match key numbers from the claim
        numbers = re.findall(
            r'\d+(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?%?(?:\s*(?:mm|cm|mL|mg|Gy|HU|mGy|mSv))?',
            claim_text
        )
        injected = False
        for num in numbers:
            escaped_num = _esc(num)
            pattern = r'(>[^<]*?)(' + re.escape(escaped_num) + r')([^<]*?<)'
            for match in re.finditer(pattern, html):
                pos = match.start()
                # Skip if a badge was already injected near this position
                if any(abs(pos - bp) < 50 for bp in badged_positions):
                    continue
                # Skip if badge already exists right after this match
                after_match = html[match.end():match.end() + 30]
                if 'cmv-badge' in after_match:
                    continue
                replacement = match.group(1) + match.group(2) + ' ' + badge + match.group(3)
                html = html[:match.start()] + replacement + html[match.end():]
                badged_positions.add(pos)
                injected = True
                break
            if injected:
                break
        if injected:
            continue

        # Try 3: first 40 chars (skip if already badged nearby)
        short = _esc(claim_text[:40].strip())
        if short:
            idx = html.find(short)
            if idx != -1 and not any(abs(idx - bp) < 50 for bp in badged_positions):
                after = html[idx + len(short):idx + len(short) + 30]
                if 'cmv-badge' not in after:
                    html = html[:idx + len(short)] + ' ' + badge + html[idx + len(short):]
                    badged_positions.add(idx)

    return html


# ---------------------------------------------------------------------------
# Main public API — drop-in replacement
# ---------------------------------------------------------------------------

def peer_review(
    ai_output: dict | str,
    topic: str = '',
    context: str = 'anatomy',
    content_type: str = '',
    content_id: str = '',
    skip_pubmed: bool = False,  # kept for backward compat, now means skip_verification
    body_section: str = '',
    modality: str = '',
    is_admin: bool = False,
) -> dict:
    """Run RadInsight Cross-Model Verification on AI-generated content.

    This is the main entry point — same signature as before (with new optional params).
    Internally uses Gemini Flash instead of PubMed for verification.

    Args:
        ai_output: Structured dict or raw text/HTML from AI.
        topic: Medical topic (e.g., "circle of Willis").
        context: One of 'anatomy', 'radiq', 'vetting', 'teaching', 'sba', 'viva', 'admin'.
        content_type: For DB persistence (e.g., 'anatomy_snippet', 'radiq_query').
        content_id: DB id of the content being verified.
        skip_pubmed: If True, skip Gemini verification (backward compat).
        body_section: Anatomical region for Gemini context.
        modality: Imaging modality for Gemini context.
        is_admin: If True, render admin edit controls on badges.

    Returns:
        dict with keys: claims, references_html, disclaimer_html, flag_button_html,
        verification_summary, radiopaedia_url, content_trust_badge_html,
        annotated_html, elapsed_ms
    """
    start_time = time.time()

    # --- 1. Run Gemini Cross-Model Verification ---
    claims_data = []
    gemini_model = None
    cmv_failed = False  # Track if CMV was attempted but failed

    if not skip_pubmed:
        try:
            from gemini_verify import verify_content
            gemini_result = verify_content(
                ai_output=ai_output,
                body_section=body_section,
                modality=modality,
                topic=topic,
            )
            claims_data = gemini_result.get('claims', [])
            gemini_model = gemini_result.get('model', '')

            if gemini_result.get('error'):
                logger.warning("Gemini CMV error: %s", gemini_result['error'])
                cmv_failed = True

        except Exception as exc:
            logger.error("Gemini CMV failed: %s", exc)
            cmv_failed = True

    # --- 2. Persist claims to DB ---
    if claims_data and content_type:
        db_claims = _persist_claims(
            claims_data, content_type, content_id,
            body_section=body_section, modality=modality,
            topic=topic, model=gemini_model or '',
        )
        # Convert to dicts for rendering
        if db_claims and hasattr(db_claims[0], 'to_dict'):
            claims_dicts = [c.to_dict() for c in db_claims]
        else:
            # Fallback: add badge_state to raw Gemini claims
            claims_dicts = []
            for c in claims_data:
                verdict = c.get('verdict', 'uncertain')
                badge_map = {'agree': 'agreed', 'disagree': 'disputed', 'uncertain': 'uncertain'}
                c['badge_state'] = badge_map.get(verdict, 'uncertain')
                claims_dicts.append(c)
    else:
        claims_dicts = []
        for c in claims_data:
            verdict = c.get('verdict', 'uncertain')
            badge_map = {'agree': 'agreed', 'disagree': 'disputed', 'uncertain': 'uncertain'}
            c['badge_state'] = badge_map.get(verdict, 'uncertain')
            claims_dicts.append(c)

    # --- 3. Verify Radiopaedia article ---
    radiopaedia_url = None
    if topic:
        radiopaedia_url = verify_radiopaedia_article(topic)

    # --- 4. Build summary ---
    agreed = sum(1 for c in claims_dicts if c.get('badge_state') == 'agreed' or c.get('badge_state') == 'admin_verified')
    disputed = sum(1 for c in claims_dicts if c.get('badge_state') == 'disputed')
    uncertain = sum(1 for c in claims_dicts if c.get('badge_state') == 'uncertain')
    cmv_complete = len(claims_dicts) > 0 and not cmv_failed
    summary = {
        'agreed': agreed,
        'disputed': disputed,
        'uncertain': uncertain,
        'total': len(claims_dicts),
        'cmv_pending': cmv_failed or (len(claims_dicts) == 0 and not skip_pubmed),
        'cmv_complete': cmv_complete,
        # Backward compat keys
        'verified': agreed,
        'unverified': uncertain + disputed,
    }

    # --- 5. Render HTML ---
    disclaimer_html = render_disclaimer_html(summary)
    references_html = render_references_html(claims_dicts, radiopaedia_url, topic)
    flag_html = render_flag_button_html(content_type, content_id)
    trust_badge_html = render_content_trust_badge(summary, content_type, content_id)

    # --- 6. If input was HTML/string, annotate with inline badges ---
    annotated_html = None
    if isinstance(ai_output, str) and claims_dicts:
        annotated_html = _inject_badges_into_html(ai_output, claims_dicts, is_admin=is_admin)

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "CMV peer review for '%s' (%s): %d claims — %d agreed, %d disputed, %d uncertain, %dms",
        topic, context, len(claims_dicts), agreed, disputed, uncertain, elapsed_ms,
    )

    return {
        'claims': claims_dicts,
        'references_html': references_html,
        'disclaimer_html': disclaimer_html,
        'flag_button_html': flag_html,
        'content_trust_badge_html': trust_badge_html,
        'verification_summary': summary,
        'radiopaedia_url': radiopaedia_url,
        'pubmed_articles': [],  # backward compat
        'annotated_html': annotated_html,
        'elapsed_ms': elapsed_ms,
    }


def peer_review_anatomy(
    parsed_json: dict,
    rendered_html: str,
    topic: str = '',
    content_id: str = '',
    body_section: str = '',
    modality: str = '',
    is_admin: bool = False,
) -> dict:
    """Convenience wrapper for anatomy snippets.

    Returns the same dict as peer_review() plus 'content_html' which is
    the original rendered HTML with injected badges + trust badge + disclaimer.
    """
    pr = peer_review(
        parsed_json,
        topic=topic,
        context='anatomy',
        content_type='anatomy_snippet',
        content_id=content_id,
        body_section=body_section,
        modality=modality,
        is_admin=is_admin,
    )

    # Don't bake badges into HTML — they are rendered client-side from DB claims
    # Just keep the content as-is; trust badge + inline badges loaded via JS
    rendered_html = rendered_html + pr['flag_button_html']

    pr['content_html'] = rendered_html
    return pr


# ---------------------------------------------------------------------------
# Stale badge handling: strip automated badges on content edit
# ---------------------------------------------------------------------------

def strip_automated_badges(html: str) -> str:
    """Remove all automated CMV/peer review elements from HTML.

    Strips: inline badges (all states), disclaimer, trust badge,
    references section, and flag button. Preserves manual-verified badges.
    Uses a DOM-aware approach to handle nested divs correctly.
    """
    if not html:
        return html

    # Remove inline badges (no nesting issues — these are spans/anchors)
    html = re.sub(r'<a[^>]*class="[^"]*cmv-badge[^"]*"[^>]*>.*?</a>', '', html, flags=re.DOTALL)
    html = re.sub(r'<span[^>]*class="[^"]*cmv-badge[^"]*"[^>]*>.*?</span>', '', html, flags=re.DOTALL)
    html = re.sub(r'<button[^>]*class="[^"]*cmv-admin-edit[^"]*"[^>]*>.*?</button>', '', html, flags=re.DOTALL)
    html = re.sub(r'<a[^>]*class="peer-review-badge[^"]*"[^>]*>.*?</a>', '', html, flags=re.DOTALL)
    html = re.sub(r'<span[^>]*class="peer-review-badge[^"]*"[^>]*>.*?</span>', '', html, flags=re.DOTALL)
    html = re.sub(r'<button[^>]*class="[^"]*peer-review-flag[^"]*"[^>]*>.*?</button>', '', html, flags=re.DOTALL)

    # Remove nested div structures (trust badge, disclaimer, references)
    # Use a helper that counts div nesting to find the correct closing tag
    for pattern in [
        r'<div[^>]*class="[^"]*cmv-trust-badge[^"]*"[^>]*>',
        r'<div[^>]*class="[^"]*cmv-trust-pending[^"]*"[^>]*>',
        r'<div[^>]*class="[^"]*(?:peer-review-disclaimer|cmv-disclaimer)[^"]*"[^>]*>',
        r'<div[^>]*class="[^"]*(?:peer-review-references|cmv-references)[^"]*"[^>]*>',
    ]:
        match = re.search(pattern, html)
        if match:
            start = match.start()
            # Find the matching closing </div> by counting nesting
            depth = 0
            pos = start
            end = None
            while pos < len(html):
                div_open = html.find('<div', pos)
                div_close = html.find('</div>', pos)
                if div_close == -1:
                    break
                if div_open != -1 and div_open < div_close:
                    depth += 1
                    pos = div_open + 4
                else:
                    depth -= 1
                    if depth == 0:
                        end = div_close + 6  # len('</div>')
                        break
                    pos = div_close + 6
            if end:
                html = html[:start] + html[end:]

    # Clean up orphan closing divs and whitespace
    # Balance divs: remove leading orphan </div> tags
    while html.lstrip().startswith('</div>'):
        html = re.sub(r'^\s*</div>\s*', '', html, count=1)

    html = re.sub(r'\n\s*\n\s*\n', '\n\n', html)
    return html.strip()
