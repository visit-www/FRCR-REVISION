"""
Vetting Tool Routes — Imaging request vetting advisory workflow.

Blueprint: vetting_bp
Routes: main workflow, algorithm management, API endpoints.
Shares RadIQ monthly rate limit quota.

Protocol library removed Apr 2026 — AI analysis now handles study identification,
contrast detection, and safety checks directly from the referral text without
a stored protocol catalogue. See memory/protocol-library-removal.md for rationale.
"""

import json
import logging
from datetime import datetime
from re import sub as re_sub

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from models import (
    db, VettingSession, VettingAlgorithm, log_ai_usage, UserRole,
)
from access_control import require_admin
from ai_vetting import (
    generate_vetting_analysis,
    VettingAIError,
)

logger = logging.getLogger(__name__)

vetting_bp = Blueprint('vetting', __name__)


# ==================== HELPERS ====================

def _check_vetting_rate_limit():
    """Share RadIQ monthly quota for vetting AI calls."""
    from radiq_routes import _check_ai_rate_limit
    return _check_ai_rate_limit('radiq')


def _slugify(text):
    """Simple slug generator."""
    slug = text.lower().strip()
    slug = re_sub(r'[^\w\s-]', '', slug)
    slug = re_sub(r'[\s_]+', '-', slug)
    slug = re_sub(r'-+', '-', slug).strip('-')
    return slug[:200]


def _search_algorithms(text, body_section=None):
    """Search published VettingAlgorithms by clinical scenario, tags, keywords, entry criteria.

    Returns max 3 results, sorted by relevance (title match first).
    """
    if not text or not text.strip():
        return []

    query = VettingAlgorithm.query.filter_by(is_published=True)

    if body_section:
        query = query.filter(VettingAlgorithm.body_section.ilike(f'%{body_section}%'))

    raw = text.strip()
    words = [w for w in raw.split() if len(w) >= 2]

    text_filters = []

    # Full query match
    text_filters.append(VettingAlgorithm.clinical_scenario.ilike(f'%{raw}%'))
    text_filters.append(VettingAlgorithm.tags.ilike(f'%{raw}%'))
    text_filters.append(VettingAlgorithm.keywords.ilike(f'%{raw}%'))
    text_filters.append(VettingAlgorithm.entry_criteria_json.ilike(f'%{raw}%'))
    text_filters.append(VettingAlgorithm.title.ilike(f'%{raw}%'))

    # Individual word matches
    for word in words[:5]:
        text_filters.append(VettingAlgorithm.clinical_scenario.ilike(f'%{word}%'))
        text_filters.append(VettingAlgorithm.tags.ilike(f'%{word}%'))
        text_filters.append(VettingAlgorithm.keywords.ilike(f'%{word}%'))
        text_filters.append(VettingAlgorithm.entry_criteria_json.ilike(f'%{word}%'))

    query = query.filter(db.or_(*text_filters))

    return query.limit(3).all()


# ==================== PAGE ROUTES ====================

@vetting_bp.route('/vetting')
@login_required
def vetting_page():
    """Main vetting workflow page."""
    is_embed = request.args.get('embed') == '1'
    return render_template('vetting.html', is_embed=is_embed)


@vetting_bp.route('/vetting/admin/algorithms')
@login_required
@require_admin
def vetting_admin_algorithms_page():
    """Admin algorithm management page."""
    return render_template('vetting_admin_algorithms.html')


# ==================== API: VETTING WORKFLOW ====================

@vetting_bp.route('/api/vetting/analyse', methods=['POST'])
@login_required
def vetting_analyse():
    """Analyse clinical referral text — clean, identify study, safety checks."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request.'}), 400

    referral_text = (data.get('referral_text') or '').strip()
    modality_hint = (data.get('modality_hint') or '').strip() or None

    if not referral_text:
        return jsonify({'error': 'Please provide the clinical referral text.'}), 400

    if len(referral_text) > 5000:
        return jsonify({'error': 'Referral text too long (max 5000 characters).'}), 400

    # Rate limit (shares RadIQ quota)
    ok, remaining, err = _check_vetting_rate_limit()
    if not ok:
        return err

    quick_clean = data.get('quick_clean', False)

    try:
        result = generate_vetting_analysis(referral_text, modality_hint=modality_hint,
                                           quick_clean=quick_clean)
    except VettingAIError as e:
        logger.error("Vetting analysis failed: %s", e)
        log_ai_usage(current_user.id, 'vetting_analyse', provider='anthropic',
                     input_summary=referral_text[:500], status='error', error_message=str(e))
        return jsonify({'error': str(e)}), 500

    # Log successful AI usage
    from ai_cost_tracker import get_last_usage
    _usage = get_last_usage()
    log_ai_usage(current_user.id, 'vetting_analyse', provider='anthropic',
                 model=result.get('model', ''),
                 input_summary=referral_text[:500],
                 input_tokens=_usage.get('input_tokens'),
                 output_tokens=result.get('output_tokens'))

    # Search for matching clinical algorithms (skip in quick clean mode)
    matched_algorithms = []
    if not quick_clean:
        cleaned_text = result.get('cleaned_clinical_text', '')
        body_section = result.get('body_section') or None
        matched_algorithms = _search_algorithms(cleaned_text, body_section=body_section)

    # --- RadInsight Peer Review on vetting analysis ---
    peer_review_data = None
    try:
        from radinsight_peer_review import peer_review
        pr_input = {}
        if result.get('guideline_citation'):
            pr_input['guideline_citation'] = result['guideline_citation']
        ai_flags = result.get('ai_flags', [])
        if ai_flags:
            pr_input['key_points'] = [f.get('flag', '') + ' ' + f.get('reason', '') for f in ai_flags if isinstance(f, dict)]
        if pr_input:
            pr_result = peer_review(
                pr_input,
                topic=result.get('study_type', ''),
                context='vetting',
                content_type='vetting_analysis',
            )
            peer_review_data = {
                'verification_summary': pr_result.get('verification_summary'),
                'references_html': pr_result.get('references_html', ''),
                'disclaimer_html': pr_result.get('disclaimer_html', ''),
                'content_trust_badge_html': pr_result.get('content_trust_badge_html', ''),
            }
    except Exception as exc:
        logger.debug("Peer review on vetting analysis failed: %s", exc)

    _va_resp = {
        'success': True,
        'analysis': result,
        'matched_algorithms': [a.to_dict() for a in matched_algorithms],
        'remaining_requests': remaining,
        'peer_review': peer_review_data,
    }
    try:
        from ai_cost_tracker import admin_cost_response
        _c = admin_cost_response(current_user, result.get('model', ''), result)
        if _c is not None:
            _va_resp['api_cost_usd'] = _c
    except Exception:
        pass
    return jsonify(_va_resp)


@vetting_bp.route('/api/vetting/save-session', methods=['POST'])
@login_required
def vetting_save_session():
    """Save a completed vetting session."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request.'}), 400

    session = VettingSession(
        user_id=current_user.id,
        raw_clinical_text=data.get('raw_clinical_text', ''),
        modality_hint=data.get('modality_hint'),
        cleaned_clinical_text=data.get('cleaned_clinical_text'),
        study_type=data.get('study_type'),
        safety_checks_json=json.dumps(data.get('safety_checks')) if data.get('safety_checks') else None,
        protocol_source=data.get('protocol_source'),
        protocol_id=data.get('protocol_id'),
        final_clinical_details=data.get('final_clinical_details'),
        final_shorthand=data.get('final_shorthand'),
        final_detailed_html=data.get('final_detailed_html'),
        final_special_notes=data.get('final_special_notes'),
        ai_model=data.get('ai_model'),
        ai_tokens_used=data.get('ai_tokens_used'),
    )
    db.session.add(session)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to save vetting session: %s", e)
        return jsonify({'error': 'Failed to save session.'}), 500

    return jsonify({'success': True, 'session_id': session.id})


# ==================== API: ADMIN ALGORITHM MANAGEMENT ====================

@vetting_bp.route('/api/vetting/admin/algorithms', methods=['GET'])
@login_required
@require_admin
def admin_list_algorithms():
    """List all admin algorithms (published and unpublished)."""
    algorithms = VettingAlgorithm.query.filter_by(origin='admin').order_by(
        VettingAlgorithm.body_section, VettingAlgorithm.title
    ).all()
    return jsonify({'algorithms': [a.to_dict() for a in algorithms]})


@vetting_bp.route('/api/vetting/admin/algorithms', methods=['POST'])
@login_required
@require_admin
def admin_create_algorithm():
    """Create an admin algorithm."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request.'}), 400

    title = (data.get('title') or '').strip()
    algorithm_key = (data.get('algorithm_key') or '').strip()
    clinical_scenario = (data.get('clinical_scenario') or '').strip()

    if not title or not algorithm_key or not clinical_scenario:
        return jsonify({'error': 'Title, algorithm key, and clinical scenario are required.'}), 400

    # Check uniqueness
    existing = VettingAlgorithm.query.filter_by(algorithm_key=algorithm_key).first()
    if existing:
        return jsonify({'error': f'Algorithm key "{algorithm_key}" already exists.'}), 409

    # Parse entry_criteria from newline-separated text to JSON array
    entry_criteria_raw = (data.get('entry_criteria') or '').strip()
    entry_criteria = [line.strip() for line in entry_criteria_raw.split('\n') if line.strip()] if entry_criteria_raw else []

    algorithm = VettingAlgorithm(
        algorithm_key=algorithm_key,
        title=title,
        slug=_slugify(title),
        body_section=data.get('body_section', '').strip() or None,
        clinical_scenario=clinical_scenario,
        entry_criteria_json=json.dumps(entry_criteria) if entry_criteria else None,
        steps_json=data.get('steps_json', '[]').strip() or '[]',
        safety_json=data.get('safety_json', '').strip() or None,
        tags=data.get('tags', '').strip() or None,
        keywords=data.get('keywords', '').strip() or None,
        origin='admin',
        is_published=False,
    )
    db.session.add(algorithm)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to create admin algorithm: %s", e)
        return jsonify({'error': 'Failed to create algorithm.'}), 500

    return jsonify({'success': True, 'algorithm': algorithm.to_dict()})


@vetting_bp.route('/api/vetting/admin/algorithms/<int:alg_id>', methods=['PUT'])
@login_required
@require_admin
def admin_update_algorithm(alg_id):
    """Update an admin algorithm."""
    algorithm = VettingAlgorithm.query.get(alg_id)
    if not algorithm or algorithm.origin != 'admin':
        return jsonify({'error': 'Admin algorithm not found.'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request.'}), 400

    if 'title' in data:
        algorithm.title = data['title'].strip()
        algorithm.slug = _slugify(algorithm.title)
    if 'algorithm_key' in data:
        new_key = data['algorithm_key'].strip()
        if new_key != algorithm.algorithm_key:
            existing = VettingAlgorithm.query.filter_by(algorithm_key=new_key).first()
            if existing:
                return jsonify({'error': f'Algorithm key "{new_key}" already exists.'}), 409
            algorithm.algorithm_key = new_key
    if 'body_section' in data:
        algorithm.body_section = data['body_section'].strip() or None
    if 'clinical_scenario' in data:
        algorithm.clinical_scenario = data['clinical_scenario'].strip()
    if 'entry_criteria' in data:
        raw = (data['entry_criteria'] or '').strip()
        criteria = [line.strip() for line in raw.split('\n') if line.strip()] if raw else []
        algorithm.entry_criteria_json = json.dumps(criteria) if criteria else None
    if 'steps_json' in data:
        algorithm.steps_json = data['steps_json'].strip() or '[]'
    if 'safety_json' in data:
        algorithm.safety_json = data['safety_json'].strip() or None
    if 'tags' in data:
        algorithm.tags = data['tags'].strip() or None
    if 'keywords' in data:
        algorithm.keywords = data['keywords'].strip() or None

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to update admin algorithm %d: %s", alg_id, e)
        return jsonify({'error': 'Failed to update algorithm.'}), 500

    return jsonify({'success': True, 'algorithm': algorithm.to_dict()})


@vetting_bp.route('/api/vetting/admin/algorithms/<int:alg_id>/verify', methods=['POST'])
@login_required
@require_admin
def admin_verify_algorithm(alg_id):
    """Verify and publish an admin algorithm."""
    algorithm = VettingAlgorithm.query.get(alg_id)
    if not algorithm or algorithm.origin != 'admin':
        return jsonify({'error': 'Admin algorithm not found.'}), 404

    algorithm.is_verified = True
    algorithm.is_published = True
    algorithm.verified_by_user_id = current_user.id
    algorithm.verified_at = datetime.utcnow()

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to verify algorithm %d: %s", alg_id, e)
        return jsonify({'error': 'Failed to verify algorithm.'}), 500

    return jsonify({'success': True, 'algorithm': algorithm.to_dict()})


@vetting_bp.route('/api/vetting/admin/algorithms/<int:alg_id>', methods=['DELETE'])
@login_required
@require_admin
def admin_delete_algorithm(alg_id):
    """Delete an admin algorithm."""
    algorithm = VettingAlgorithm.query.get(alg_id)
    if not algorithm or algorithm.origin != 'admin':
        return jsonify({'error': 'Admin algorithm not found.'}), 404

    db.session.delete(algorithm)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to delete admin algorithm %d: %s", alg_id, e)
        return jsonify({'error': 'Failed to delete algorithm.'}), 500

    return jsonify({'success': True})
