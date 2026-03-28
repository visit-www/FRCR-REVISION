"""
RadIQ Routes — Consultant-level AI assistant for radiologists.

Blueprint: radiq_bp
Routes: landing page, query submission, history CRUD.
"""

import logging
from datetime import date

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from models import (
    db, RadIQQuery, ClinicalProtocol, ReportingAlgorithm,
    IncidentalFindingCalculator,
)
from ai_radiq import generate_radiq_response, RADIQ_CATEGORIES, RadIQError

logger = logging.getLogger(__name__)

radiq_bp = Blueprint('radiq', __name__)

AI_DAILY_LIMIT = 50


def _check_ai_rate_limit():
    """Check and increment per-user daily AI usage. Returns (ok, remaining, error_response)."""
    today = date.today()
    if current_user.ai_usage_date != today:
        current_user.ai_usage_date = today
        current_user.ai_usage_count = 0
    if (current_user.ai_usage_count or 0) >= AI_DAILY_LIMIT:
        return False, 0, (jsonify({
            'error': f'You have reached the daily limit of {AI_DAILY_LIMIT} AI requests. '
                     'Please try again tomorrow.'
        }), 429)
    current_user.ai_usage_count = (current_user.ai_usage_count or 0) + 1
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    remaining = AI_DAILY_LIMIT - current_user.ai_usage_count
    return True, remaining, None


# ==================== LANDING PAGE ====================

@radiq_bp.route('/radiq')
@login_required
def radiq_landing():
    """RadIQ landing page."""
    return render_template('radiq.html')


# ==================== QUERY SUBMISSION ====================

def _find_relevant_db_content(question, category):
    """Search DB for protocols, algorithms, and tools relevant to the user query."""
    results = []
    q = question.strip()
    if not q:
        return ''

    try:
        # 1. Clinical Protocols — most relevant for protocol/radiographer/general queries
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
                import re
                content_preview = re.sub(r'<[^>]+>', '', p.content_html)[:500]
            results.append(
                f"[PROTOCOL] {p.title} (source: {p.source_citation or 'internal'})\n"
                f"{content_preview}"
            )

        # 2. Reporting Algorithms — useful for structured guidance
        algos = ReportingAlgorithm.query.filter_by(is_available=True).filter(
            db.or_(
                ReportingAlgorithm.title.ilike(f'%{q[:80]}%'),
                ReportingAlgorithm.keywords.ilike(f'%{q[:80]}%') if ReportingAlgorithm.keywords is not None else False,
            )
        ).limit(2).all()
        for a in algos:
            results.append(
                f"[ALGORITHM] {a.title} — {a.category or ''} ({a.body_section or ''})\n"
                f"{(a.description or '')[:300]}"
            )

        # 3. Radiology Tools (IF calculators) — for specific clinical tools
        tools = IncidentalFindingCalculator.query.filter(
            IncidentalFindingCalculator.title.ilike(f'%{q[:80]}%')
        ).limit(2).all()
        for t in tools:
            results.append(
                f"[TOOL] {t.title} — {t.body_section or ''}"
            )

    except Exception as e:
        logger.warning(f"DB content lookup for RadIQ failed (non-fatal): {e}")

    if not results:
        return ''

    return (
        "\n\nRELEVANT CONTENT FROM RADINSIGHTS DATABASE:\n"
        "The following resources exist in our database and may be relevant. "
        "Reference them in your response where appropriate, and mention they are "
        "available in RadInsights for the user to access.\n\n"
        + "\n\n".join(results)
    )


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
    db_context = _find_relevant_db_content(question, category)

    try:
        response_html = generate_radiq_response(question, category, db_context=db_context)
    except RadIQError as e:
        logger.error("RadIQ generation failed: %s", e)
        return jsonify({'error': str(e)}), 500

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
        # Still return the response even if save fails
        return jsonify({
            'success': True,
            'response_html': response_html,
            'query_id': None,
            'remaining_requests': remaining,
        })

    return jsonify({
        'success': True,
        'response_html': response_html,
        'query_id': query_record.id,
        'remaining_requests': remaining,
    })


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
