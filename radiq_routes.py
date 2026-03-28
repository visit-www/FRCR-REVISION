"""
RadIQ Routes — Consultant-level AI assistant for radiologists.

Blueprint: radiq_bp
Routes: landing page, query submission, history CRUD.
"""

import logging
from datetime import date

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from models import db, RadIQQuery
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

    try:
        response_html = generate_radiq_response(question, category)
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
    """Get the current user's RadIQ query history (latest first, limit 50)."""
    queries = RadIQQuery.query.filter_by(user_id=current_user.id)\
        .order_by(RadIQQuery.created_at.desc())\
        .limit(50)\
        .all()
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
