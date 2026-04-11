"""
RadIQ Routes — Consultant-level AI assistant for radiologists.

Blueprint: radiq_bp
Routes: landing page, query submission, history CRUD.
"""

import logging
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from models import (
    db, RadIQQuery, RadIQFeedback, ClinicalProtocol, ReportingAlgorithm,
    IncidentalFindingCalculator, RadiologyPearl, ImagingProtocol,
    log_ai_usage, UserRole,
)
from ai_radiq import generate_radiq_response, RADIQ_CATEGORIES, RadIQError

logger = logging.getLogger(__name__)

radiq_bp = Blueprint('radiq', __name__)

TIER_LIMITS = {
    'free':      {'sr_monthly': 10,   'radiq_monthly': 5,   'trial_days': 7},
    'standard':  {'sr_monthly': 75,   'radiq_monthly': 20,  'trial_days': None},
    'elite':     {'sr_monthly': 300,  'radiq_monthly': 40,  'trial_days': None},
    'elite_pro': {'sr_monthly': 1500, 'radiq_monthly': 60,  'trial_days': None},
}


def _check_ai_rate_limit(usage_type='radiq'):
    """Tier-based monthly AI rate limit. Returns (ok, remaining, error_response)."""
    # Admin bypass
    if current_user.role == UserRole.ADMIN or getattr(current_user, 'is_superadmin', False):
        return True, 9999, None

    tier = getattr(current_user, 'subscription_tier', 'free') or 'free'
    limits = TIER_LIMITS.get(tier, TIER_LIMITS['free'])

    # Trial expiry check (free tier only, non-grandfathered)
    if tier == 'free' and current_user.trial_started_at is not None:
        trial_end = current_user.trial_started_at + timedelta(days=limits['trial_days'])
        if datetime.utcnow() > trial_end:
            return False, 0, (jsonify({
                'error': 'Your 7-day free trial has ended. Upgrade to continue using AI features.',
                'upgrade_required': True,
                'trial_expired': True,
            }), 429)

    # Monthly reset
    today = date.today()
    reset_date = current_user.usage_reset_date
    if reset_date is None or reset_date.month != today.month or reset_date.year != today.year:
        current_user.sr_usage_month = 0
        current_user.radiq_usage_month = 0
        current_user.usage_reset_date = today

    # Pick the right counter & limit
    if usage_type == 'radiq':
        used = current_user.radiq_usage_month or 0
        limit = limits['radiq_monthly']
    else:
        used = current_user.sr_usage_month or 0
        limit = limits['sr_monthly']

    if used >= limit:
        return False, 0, (jsonify({
            'error': f'You have used all {limit} {"RadIQ queries" if usage_type == "radiq" else "Smart Reporter actions"} '
                     f'for this month. Upgrade for more.',
            'upgrade_required': True,
            'trial_expired': False,
            'limit': limit,
            'tier': tier,
        }), 429)

    # Increment
    if usage_type == 'radiq':
        current_user.radiq_usage_month = used + 1
    else:
        current_user.sr_usage_month = used + 1

    # Legacy daily counter for analytics
    today_date = date.today()
    if current_user.ai_usage_date != today_date:
        current_user.ai_usage_date = today_date
        current_user.ai_usage_count = 0
    current_user.ai_usage_count = (current_user.ai_usage_count or 0) + 1

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    remaining = limit - (used + 1)
    return True, remaining, None


@radiq_bp.route('/api/radiq/ai-usage', methods=['GET'])
@login_required
def get_radiq_ai_usage():
    """Return tier-aware RadIQ usage info without incrementing counters."""
    tier = getattr(current_user, 'subscription_tier', 'free') or 'free'
    limits = TIER_LIMITS.get(tier, TIER_LIMITS['free'])

    # Monthly reset check
    today = date.today()
    reset_date = current_user.usage_reset_date
    if reset_date is None or reset_date.month != today.month or reset_date.year != today.year:
        radiq_used = 0
    else:
        radiq_used = current_user.radiq_usage_month or 0

    radiq_limit = limits['radiq_monthly']

    # Admin bypass
    if current_user.role == UserRole.ADMIN or getattr(current_user, 'is_superadmin', False):
        radiq_used = 0
        radiq_limit = 9999

    # Trial info
    trial_expired = False
    trial_days_left = None
    if tier == 'free' and current_user.trial_started_at is not None:
        trial_end = current_user.trial_started_at + timedelta(days=limits['trial_days'])
        now = datetime.utcnow()
        if now > trial_end:
            trial_expired = True
            trial_days_left = 0
        else:
            trial_days_left = (trial_end - now).days

    return jsonify({
        'remaining_requests': max(0, radiq_limit - radiq_used),
        'limit': radiq_limit,
        'tier': tier,
        'trial_expired': trial_expired,
        'trial_days_left': trial_days_left,
    })


# ==================== LANDING PAGE ====================

@radiq_bp.route('/radiq')
@login_required
def radiq_landing():
    """RadIQ landing page."""
    return render_template('radiq.html')


# ==================== QUERY SUBMISSION ====================

def _find_relevant_db_content(question, category):
    """Search DB for protocols, algorithms, and tools relevant to the user query.

    Returns:
        tuple: (prompt_context_str, list_of_link_dicts)
            - prompt_context_str: text to inject into AI prompt
            - link_dicts: [{'type': ..., 'title': ..., 'url': ..., 'icon': ..., 'color': ...}, ...]
    """
    import re
    prompt_parts = []
    links = []
    q = question.strip()
    if not q:
        return '', []

    try:
        # 1. Clinical Protocols
        protocols = ClinicalProtocol.query.filter_by(is_published=True).filter(
            db.or_(
                ClinicalProtocol.title.ilike(f'%{q[:80]}%'),
                ClinicalProtocol.keywords.ilike(f'%{q[:80]}%'),
            )
        ).limit(3).all()

        # If no match on full query, try individual keywords (3+ chars)
        if not protocols:
            words = [w for w in q.split() if len(w) >= 3]
            for word in words[:5]:
                found = ClinicalProtocol.query.filter_by(is_published=True).filter(
                    db.or_(
                        ClinicalProtocol.title.ilike(f'%{word}%'),
                        ClinicalProtocol.keywords.ilike(f'%{word}%'),
                    )
                ).limit(2).all()
                for p in found:
                    if p not in protocols:
                        protocols.append(p)
                if len(protocols) >= 3:
                    break

        for p in protocols[:3]:
            content_preview = ''
            if p.content_html:
                content_preview = re.sub(r'<[^>]+>', '', p.content_html)[:500]
            prompt_parts.append(
                f"[PROTOCOL] {p.title} (source: {p.source_citation or 'internal'})\n"
                f"{content_preview}"
            )
            links.append({
                'type': 'Protocol',
                'title': p.title,
                'url': f'/radiology-protocols/view/{p.id}',
                'icon': 'fa-clipboard-list',
                'color': '#e96304',
            })

        # 2. Reporting Algorithms
        algos = ReportingAlgorithm.query.filter_by(is_available=True).filter(
            db.or_(
                ReportingAlgorithm.title.ilike(f'%{q[:80]}%'),
                ReportingAlgorithm.keywords.ilike(f'%{q[:80]}%') if ReportingAlgorithm.keywords is not None else False,
            )
        ).limit(2).all()
        for a in algos:
            prompt_parts.append(
                f"[ALGORITHM] {a.title} — {a.category or ''} ({a.body_section or ''})\n"
                f"{(a.description or '')[:300]}"
            )
            links.append({
                'type': 'Algorithm',
                'title': a.title,
                'url': f'/reporting-template/{a.slug}' if a.slug else '#',
                'icon': 'fa-sitemap',
                'color': '#5E899E',
            })

        # 3. Radiology Tools (IF calculators)
        tools = IncidentalFindingCalculator.query.filter(
            db.or_(
                IncidentalFindingCalculator.title.ilike(f'%{q[:80]}%'),
                IncidentalFindingCalculator.finding_name.ilike(f'%{q[:80]}%'),
            )
        ).limit(2).all()

        # If no match on full query, try individual keywords
        if not tools:
            words = [w for w in q.split() if len(w) >= 3]
            for word in words[:5]:
                found = IncidentalFindingCalculator.query.filter(
                    db.or_(
                        IncidentalFindingCalculator.title.ilike(f'%{word}%'),
                        IncidentalFindingCalculator.finding_name.ilike(f'%{word}%'),
                    )
                ).limit(2).all()
                for t in found:
                    if t not in tools:
                        tools.append(t)
                if len(tools) >= 2:
                    break

        for t in tools[:2]:
            prompt_parts.append(
                f"[TOOL] {t.title} — {t.body_section or ''}"
            )
            links.append({
                'type': 'Tool',
                'title': t.title,
                'url': f'/incidental-findings/{t.slug}' if t.slug else '#',
                'icon': 'fa-tools',
                'color': '#198754',
            })

        # 4. Radiology Pearls (verified only)
        pearls = RadiologyPearl.query.filter_by(is_verified=True).filter(
            db.or_(
                RadiologyPearl.pearl_text.ilike(f'%{q[:80]}%'),
                RadiologyPearl.tags.ilike(f'%{q[:80]}%'),
            )
        ).limit(2).all()

        if not pearls:
            words = [w for w in q.split() if len(w) >= 3]
            for word in words[:5]:
                found = RadiologyPearl.query.filter_by(is_verified=True).filter(
                    db.or_(
                        RadiologyPearl.pearl_text.ilike(f'%{word}%'),
                        RadiologyPearl.tags.ilike(f'%{word}%'),
                    )
                ).limit(2).all()
                for p in found:
                    if p not in pearls:
                        pearls.append(p)
                if len(pearls) >= 2:
                    break

        for p in pearls[:2]:
            prompt_parts.append(
                f"[PEARL] {(p.pearl_text or '')[:300]}"
            )
            links.append({
                'type': 'Pearl',
                'title': (p.pearl_text or '')[:60] + ('...' if len(p.pearl_text or '') > 60 else ''),
                'url': '/radiology-pearls',
                'icon': 'fa-gem',
                'color': '#e96304',
            })

        # 5. Anatomy Snippets / Knowledge Hub (origin='anatomy_cache')
        snippets = ReportingAlgorithm.query.filter_by(
            is_available=True, origin='anatomy_cache'
        ).filter(
            ReportingAlgorithm.title.ilike(f'%{q[:80]}%')
        ).limit(2).all()

        if not snippets:
            words = [w for w in q.split() if len(w) >= 3]
            for word in words[:5]:
                found = ReportingAlgorithm.query.filter_by(
                    is_available=True, origin='anatomy_cache'
                ).filter(
                    ReportingAlgorithm.title.ilike(f'%{word}%')
                ).limit(2).all()
                for s in found:
                    if s not in snippets:
                        snippets.append(s)
                if len(snippets) >= 2:
                    break

        for s in snippets[:2]:
            prompt_parts.append(
                f"[ANATOMY] {s.title} — {(s.description or '')[:300]}"
            )
            links.append({
                'type': 'Anatomy',
                'title': s.title,
                'url': f'/anatomy-snippets/{s.slug}' if s.slug else '#',
                'icon': 'fa-brain',
                'color': '#6b46c1',
            })

        # 6. Imaging Protocols (vetting library) — gated on protocol-related keywords
        # to avoid injecting protocol context into unrelated clinical queries.
        q_lower = q.lower()
        _PROTOCOL_KEYWORDS = (
            'protocol', 'contrast', 'phase', 'delay', 'timing', 'dose',
            'kvp', 'mas', 'coverage', 'reconstruction', 'scanner', 'acquisition',
            'ctpa', 'kub', 'urogram', 'triphasic', 'angiography', 'bolus',
            'arterial', 'portal venous', 'equilibrium', 'paediatric contrast',
            'how to scan', 'how to image', 'imaging technique',
        )
        if any(kw in q_lower for kw in _PROTOCOL_KEYWORDS):
            img_protocols = ImagingProtocol.query.filter_by(
                origin='admin', is_published=True
            ).filter(
                db.or_(
                    ImagingProtocol.title.ilike(f'%{q[:80]}%'),
                    ImagingProtocol.keywords.ilike(f'%{q[:80]}%'),
                    ImagingProtocol.shorthand_text.ilike(f'%{q[:80]}%'),
                )
            ).limit(3).all()

            # Fallback to per-word matching if full-query match empty
            if not img_protocols:
                words = [w for w in q.split() if len(w) >= 3]
                for word in words[:5]:
                    found = ImagingProtocol.query.filter_by(
                        origin='admin', is_published=True
                    ).filter(
                        db.or_(
                            ImagingProtocol.title.ilike(f'%{word}%'),
                            ImagingProtocol.keywords.ilike(f'%{word}%'),
                            ImagingProtocol.shorthand_text.ilike(f'%{word}%'),
                        )
                    ).limit(2).all()
                    for p in found:
                        if p not in img_protocols:
                            img_protocols.append(p)
                    if len(img_protocols) >= 3:
                        break

            for p in img_protocols[:3]:
                prompt_parts.append(
                    f"[IMAGING PROTOCOL] {p.title} "
                    f"({p.modality}, {p.body_section or 'general'})\n"
                    f"Shorthand: {(p.shorthand_text or '')[:300]}\n"
                    f"Notes: {(p.special_notes or '')[:300]}"
                )
                links.append({
                    'type': 'Imaging Protocol',
                    'title': p.title,
                    'url': f'/vetting/protocols?search={p.slug}' if p.slug else '/vetting/protocols',
                    'icon': 'fa-notes-medical',
                    'color': '#5E899E',
                })

    except Exception as e:
        logger.warning(f"DB content lookup for RadIQ failed (non-fatal): {e}")

    if not prompt_parts:
        return '', []

    prompt_context = (
        "\n\nRELEVANT CONTENT FROM RADINSIGHTS DATABASE:\n"
        "The following resources exist in our database and may be relevant. "
        "Reference them in your response where appropriate, and mention they are "
        "available in RadInsights for the user to access.\n\n"
        + "\n\n".join(prompt_parts)
    )
    return prompt_context, links


@radiq_bp.route('/api/radiq/query', methods=['POST'])
@login_required
def radiq_query():
    """Submit a query to RadIQ and save the response."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request.'}), 400

    question = (data.get('question') or '').strip()
    category = (data.get('category') or '').strip()

    if not question:
        return jsonify({'error': 'Please provide a question.'}), 400
    if category not in RADIQ_CATEGORIES:
        return jsonify({'error': f'Invalid category. Must be one of: {", ".join(sorted(RADIQ_CATEGORIES))}'}), 400

    # Rate limit
    ok, remaining, err = _check_ai_rate_limit()
    if not ok:
        return err

    # Look up relevant content in DB before calling AI
    db_context, db_links = _find_relevant_db_content(question, category)

    try:
        result = generate_radiq_response(question, category, db_context=db_context)
    except RadIQError as e:
        logger.error("RadIQ generation failed: %s", e)
        log_ai_usage(current_user.id, 'radiq_query', provider='anthropic',
                     input_summary=question[:500], status='error', error_message=str(e))
        return jsonify({'error': str(e)}), 500

    response_html = result['html']

    # Audit log for successful RadIQ generation
    from ai_cost_tracker import get_last_usage
    _usage = get_last_usage()
    log_ai_usage(current_user.id, 'radiq_query', provider='anthropic',
                 model=result.get('model', ''), input_summary=question[:500],
                 input_tokens=_usage.get('input_tokens'),
                 output_tokens=result.get('output_tokens'))

    # Save to DB
    query_record = RadIQQuery(
        user_id=current_user.id,
        category=category,
        question=question,
        response_text=response_html,
    )
    db.session.add(query_record)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to save RadIQ query: %s", e)
        return jsonify({
            'success': True,
            'response_html': response_html,
            'query_id': None,
            'remaining_requests': remaining,
            'db_links': db_links,
        })

    # --- RadInsight Peer Review ---
    peer_review_data = None
    try:
        from radinsight_peer_review import peer_review
        pr_result = peer_review(
            response_html,
            topic=question[:80],
            context='radiq',
            content_type='radiq_query',
            content_id=str(query_record.id),
        )
        peer_review_data = {
            'verification_summary': pr_result.get('verification_summary'),
            'references_html': pr_result.get('references_html', ''),
            'disclaimer_html': pr_result.get('disclaimer_html', ''),
        }
        if pr_result.get('verification_summary', {}).get('total', 0) > 0:
            response_html = (
                response_html
                + pr_result.get('disclaimer_html', '')
                + pr_result.get('references_html', '')
            )
    except Exception as exc:
        logger.debug("Peer review on RadIQ query failed: %s", exc)

    _riq_resp = {
        'success': True,
        'response_html': response_html,
        'query_id': query_record.id,
        'remaining_requests': remaining,
        'db_links': db_links,
        'peer_review': peer_review_data,
    }
    try:
        from ai_cost_tracker import admin_cost_response
        _c = admin_cost_response(current_user, result.get('model', ''), result)
        if _c is not None:
            _riq_resp['api_cost_usd'] = _c
    except Exception:
        pass
    return jsonify(_riq_resp)


# ==================== HISTORY ====================

@radiq_bp.route('/api/radiq/history')
@login_required
def radiq_history():
    """Get the current user's RadIQ query history (latest first, limit 50). Supports ?q= search."""
    search = (request.args.get('q') or '').strip()
    query = RadIQQuery.query.filter_by(user_id=current_user.id)

    if search:
        like_pattern = f'%{search}%'
        query = query.filter(db.or_(
            RadIQQuery.question.ilike(like_pattern),
            RadIQQuery.response_text.ilike(like_pattern),
        ))

    queries = query.order_by(RadIQQuery.created_at.desc()).limit(50).all()
    return jsonify({
        'queries': [q.to_dict() for q in queries],
    })


@radiq_bp.route('/api/radiq/history/<int:query_id>')
@login_required
def radiq_history_detail(query_id):
    """Get a single saved query."""
    q = RadIQQuery.query.filter_by(id=query_id, user_id=current_user.id).first()
    if not q:
        return jsonify({'error': 'Query not found.'}), 404
    return jsonify(q.to_dict())


@radiq_bp.route('/api/radiq/history/<int:query_id>', methods=['DELETE'])
@login_required
def radiq_history_delete(query_id):
    """Delete a saved query."""
    q = RadIQQuery.query.filter_by(id=query_id, user_id=current_user.id).first()
    if not q:
        return jsonify({'error': 'Query not found.'}), 404
    db.session.delete(q)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to delete RadIQ query %d: %s", query_id, e)
        return jsonify({'error': 'Failed to delete query.'}), 500
    return jsonify({'success': True})


# ==================== FEEDBACK ====================

ALLOWED_FEEDBACK_REASONS = {'incorrect', 'outdated', 'missing_info', 'inappropriate', 'other'}


@radiq_bp.route('/api/radiq/feedback', methods=['POST'])
@login_required
def radiq_feedback():
    """Flag a RadIQ response as incorrect/unhelpful."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request.'}), 400

    query_id = data.get('query_id')
    reason = (data.get('reason') or '').strip()
    details = (data.get('details') or '').strip() or None

    if not query_id or not reason:
        return jsonify({'error': 'query_id and reason are required.'}), 400
    if reason not in ALLOWED_FEEDBACK_REASONS:
        return jsonify({'error': f'Invalid reason. Must be one of: {", ".join(sorted(ALLOWED_FEEDBACK_REASONS))}'}), 400

    # Verify query belongs to current user
    query_record = RadIQQuery.query.filter_by(id=query_id, user_id=current_user.id).first()
    if not query_record:
        return jsonify({'error': 'Query not found.'}), 404

    # Check for duplicate
    existing = RadIQFeedback.query.filter_by(query_id=query_id, user_id=current_user.id).first()
    if existing:
        return jsonify({'error': 'You have already flagged this response.'}), 409

    feedback = RadIQFeedback(
        query_id=query_id,
        user_id=current_user.id,
        reason=reason,
        details=details,
    )
    db.session.add(feedback)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to save RadIQ feedback: %s", e)
        return jsonify({'error': 'Failed to save feedback.'}), 500

    logger.info("RadIQ feedback submitted: query_id=%d reason=%s user=%d", query_id, reason, current_user.id)
    return jsonify({'success': True})
