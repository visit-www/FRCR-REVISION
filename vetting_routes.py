"""
Vetting Tool Routes — Imaging request vetting workflow.

Blueprint: vetting_bp
Routes: main workflow, protocol library, admin management, API endpoints.
Shares RadIQ monthly rate limit quota.
"""

import json
import logging
from datetime import datetime
from re import sub as re_sub

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from models import (
    db, ImagingProtocol, VettingSession, VettingAlgorithm, log_ai_usage, UserRole,
)
from access_control import require_admin
from ai_vetting import (
    generate_vetting_analysis, generate_vetting_protocol,
    VettingAIError,
)

logger = logging.getLogger(__name__)

vetting_bp = Blueprint('vetting', __name__)


# ==================== HELPERS ====================

def _check_vetting_rate_limit():
    """Share RadIQ monthly quota for vetting AI calls."""
    from radiq_routes import _check_ai_rate_limit
    return _check_ai_rate_limit('radiq')


def _search_protocols(study_type, modality, user_id=None):
    """Search ImagingProtocol by title/keywords/shorthand/indications/modality.

    Returns personal matches first, then admin published.
    Searches the original query as-is (e.g. "CTPA") AND individual words.
    """
    results = []

    # Normalise search terms
    raw_query = study_type.replace('_', ' ').strip() if study_type else ''
    words = [w for w in raw_query.split() if len(w) >= 2]

    if not raw_query and not modality:
        return results

    def _build_filter(query_obj, model_cls):
        """Apply ILIKE filters across all searchable text columns."""
        if modality:
            query_obj = query_obj.filter(model_cls.modality.ilike(modality))

        text_filters = []

        # Match the full query string as-is (catches "CTPA", "MRI Brain", etc.)
        if raw_query:
            text_filters.append(model_cls.title.ilike(f'%{raw_query}%'))
            text_filters.append(model_cls.keywords.ilike(f'%{raw_query}%'))
            text_filters.append(model_cls.shorthand_text.ilike(f'%{raw_query}%'))
            text_filters.append(model_cls.indication_json.ilike(f'%{raw_query}%'))

        # Also match individual words (catches multi-word queries)
        for word in words[:5]:
            text_filters.append(model_cls.title.ilike(f'%{word}%'))
            text_filters.append(model_cls.keywords.ilike(f'%{word}%'))
            text_filters.append(model_cls.shorthand_text.ilike(f'%{word}%'))
            text_filters.append(model_cls.indication_json.ilike(f'%{word}%'))

        if text_filters:
            query_obj = query_obj.filter(db.or_(*text_filters))
        return query_obj

    # 1. Personal protocols (current user)
    if user_id:
        personal_q = ImagingProtocol.query.filter_by(origin='personal', user_id=user_id)
        personal_q = _build_filter(personal_q, ImagingProtocol)
        results.extend(personal_q.order_by(ImagingProtocol.is_emergency.desc()).limit(5).all())

    # 2. Admin published protocols
    admin_q = ImagingProtocol.query.filter_by(origin='admin', is_published=True)
    admin_q = _build_filter(admin_q, ImagingProtocol)
    admin_results = admin_q.order_by(ImagingProtocol.is_emergency.desc()).limit(10).all()

    # Deduplicate (personal takes priority)
    seen_ids = {p.id for p in results}
    for p in admin_results:
        if p.id not in seen_ids:
            results.append(p)

    return results[:10]


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
    return render_template('vetting.html')


@vetting_bp.route('/vetting/protocols')
@login_required
def vetting_protocols_page():
    """Protocol library browse page."""
    return render_template('vetting_protocols.html')


@vetting_bp.route('/vetting/admin/protocols')
@login_required
@require_admin
def vetting_admin_page():
    """Admin protocol management page."""
    return render_template('vetting_admin.html')


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
    """Call 1: Analyse clinical referral text."""
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

    try:
        result = generate_vetting_analysis(referral_text, modality_hint=modality_hint)
    except VettingAIError as e:
        logger.error("Vetting analysis failed: %s", e)
        log_ai_usage(current_user.id, 'vetting_analyse', provider='anthropic',
                     input_summary=referral_text[:500], status='error', error_message=str(e))
        return jsonify({'error': str(e)}), 500

    # Log successful AI usage
    log_ai_usage(current_user.id, 'vetting_analyse', provider='anthropic',
                 model=result.get('model', ''),
                 input_summary=referral_text[:500],
                 output_tokens=result.get('output_tokens'))

    # Search for matching protocols in library
    study_type = result.get('study_type', '')
    modality = result.get('modality', '')
    matched_protocols = _search_protocols(study_type, modality, user_id=current_user.id)

    # Search for matching clinical algorithms
    cleaned_text = result.get('cleaned_clinical_text', '')
    matched_algorithms = _search_algorithms(cleaned_text)

    return jsonify({
        'success': True,
        'analysis': result,
        'matched_protocols': [p.to_dict() for p in matched_protocols],
        'matched_algorithms': [a.to_dict() for a in matched_algorithms],
        'remaining_requests': remaining,
    })


@vetting_bp.route('/api/vetting/generate-protocol', methods=['POST'])
@login_required
def vetting_generate_protocol():
    """Call 2: Generate protocol when no library match selected."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request.'}), 400

    study_type = (data.get('study_type') or '').strip()
    modality = (data.get('modality') or '').strip()
    clinical_context = (data.get('clinical_context') or '').strip() or None
    algorithm_context = (data.get('algorithm_context') or '').strip() or None

    if not study_type:
        return jsonify({'error': 'Study type is required.'}), 400

    # Rate limit
    ok, remaining, err = _check_vetting_rate_limit()
    if not ok:
        return err

    try:
        result = generate_vetting_protocol(study_type, modality, clinical_context=clinical_context,
                                           algorithm_context=algorithm_context)
    except VettingAIError as e:
        logger.error("Vetting protocol generation failed: %s", e)
        log_ai_usage(current_user.id, 'vetting_protocol', provider='anthropic',
                     input_summary=f"{study_type} ({modality})", status='error', error_message=str(e))
        return jsonify({'error': str(e)}), 500

    log_ai_usage(current_user.id, 'vetting_protocol', provider='anthropic',
                 model=result.get('model', ''),
                 input_summary=f"{study_type} ({modality})",
                 output_tokens=result.get('output_tokens'))

    return jsonify({
        'success': True,
        'protocol': result,
        'remaining_requests': remaining,
    })


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


@vetting_bp.route('/api/vetting/protocols/search')
@login_required
def vetting_search_protocols():
    """Search protocols by query string."""
    q = (request.args.get('q') or '').strip()
    modality = (request.args.get('modality') or '').strip() or None

    if not q and not modality:
        return jsonify({'protocols': []})

    results = _search_protocols(q, modality, user_id=current_user.id)
    return jsonify({'protocols': [p.to_dict() for p in results]})


# ==================== API: PROTOCOL LIBRARY (USER) ====================

@vetting_bp.route('/api/vetting/protocols', methods=['GET'])
@login_required
def list_protocols():
    """List personal + admin published protocols."""
    modality_filter = request.args.get('modality', '').strip()
    body_section_filter = request.args.get('body_section', '').strip()

    # Personal protocols
    personal_q = ImagingProtocol.query.filter_by(origin='personal', user_id=current_user.id)
    # Admin published protocols
    admin_q = ImagingProtocol.query.filter_by(origin='admin', is_published=True)

    if modality_filter:
        personal_q = personal_q.filter(ImagingProtocol.modality.ilike(modality_filter))
        admin_q = admin_q.filter(ImagingProtocol.modality.ilike(modality_filter))
    if body_section_filter:
        personal_q = personal_q.filter(ImagingProtocol.body_section.ilike(f'%{body_section_filter}%'))
        admin_q = admin_q.filter(ImagingProtocol.body_section.ilike(f'%{body_section_filter}%'))

    personal = personal_q.order_by(ImagingProtocol.title).all()
    admin = admin_q.order_by(ImagingProtocol.title).all()

    return jsonify({
        'personal': [p.to_dict() for p in personal],
        'admin': [p.to_dict() for p in admin],
    })


@vetting_bp.route('/api/vetting/protocols', methods=['POST'])
@login_required
def create_personal_protocol():
    """Save a protocol to personal library."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request.'}), 400

    title = (data.get('title') or '').strip()
    modality = (data.get('modality') or '').strip()
    if not title or not modality:
        return jsonify({'error': 'Title and modality are required.'}), 400

    protocol = ImagingProtocol(
        title=title,
        slug=_slugify(title),
        modality=modality,
        body_section=data.get('body_section', '').strip() or None,
        keywords=data.get('keywords', '').strip() or None,
        shorthand_text=data.get('shorthand_text', '').strip() or None,
        detailed_protocol_html=data.get('detailed_protocol_html', '').strip() or None,
        special_notes=data.get('special_notes', '').strip() or None,
        indication_json=json.dumps(data['indication_json']) if data.get('indication_json') else None,
        validation_json=json.dumps(data['validation_json']) if data.get('validation_json') else None,
        origin='personal',
        user_id=current_user.id,
        copied_from_id=data.get('copied_from_id'),
        is_published=False,
        is_emergency=data.get('is_emergency', False),
    )
    db.session.add(protocol)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to create personal protocol: %s", e)
        return jsonify({'error': 'Failed to save protocol.'}), 500

    return jsonify({'success': True, 'protocol': protocol.to_dict()})


@vetting_bp.route('/api/vetting/protocols/<int:protocol_id>', methods=['PUT'])
@login_required
def update_personal_protocol(protocol_id):
    """Update a personal protocol (verify ownership)."""
    protocol = ImagingProtocol.query.get(protocol_id)
    if not protocol:
        return jsonify({'error': 'Protocol not found.'}), 404
    if protocol.origin != 'personal' or protocol.user_id != current_user.id:
        return jsonify({'error': 'You can only edit your own protocols.'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request.'}), 400

    if 'title' in data:
        protocol.title = data['title'].strip()
        protocol.slug = _slugify(protocol.title)
    if 'modality' in data:
        protocol.modality = data['modality'].strip()
    if 'body_section' in data:
        protocol.body_section = data['body_section'].strip() or None
    if 'keywords' in data:
        protocol.keywords = data['keywords'].strip() or None
    if 'shorthand_text' in data:
        protocol.shorthand_text = data['shorthand_text'].strip() or None
    if 'detailed_protocol_html' in data:
        protocol.detailed_protocol_html = data['detailed_protocol_html'].strip() or None
    if 'special_notes' in data:
        protocol.special_notes = data['special_notes'].strip() or None
    if 'indication_json' in data:
        protocol.indication_json = json.dumps(data['indication_json']) if data['indication_json'] else None
    if 'validation_json' in data:
        protocol.validation_json = json.dumps(data['validation_json']) if data['validation_json'] else None
    if 'is_emergency' in data:
        protocol.is_emergency = bool(data['is_emergency'])

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to update protocol %d: %s", protocol_id, e)
        return jsonify({'error': 'Failed to update protocol.'}), 500

    return jsonify({'success': True, 'protocol': protocol.to_dict()})


@vetting_bp.route('/api/vetting/protocols/<int:protocol_id>', methods=['DELETE'])
@login_required
def delete_personal_protocol(protocol_id):
    """Delete a personal protocol (verify ownership)."""
    protocol = ImagingProtocol.query.get(protocol_id)
    if not protocol:
        return jsonify({'error': 'Protocol not found.'}), 404
    if protocol.origin != 'personal' or protocol.user_id != current_user.id:
        return jsonify({'error': 'You can only delete your own protocols.'}), 403

    db.session.delete(protocol)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to delete protocol %d: %s", protocol_id, e)
        return jsonify({'error': 'Failed to delete protocol.'}), 500

    return jsonify({'success': True})


@vetting_bp.route('/api/vetting/protocols/<int:protocol_id>/copy', methods=['POST'])
@login_required
def copy_protocol_to_personal(protocol_id):
    """Copy an admin protocol to the user's personal library."""
    source = ImagingProtocol.query.get(protocol_id)
    if not source:
        return jsonify({'error': 'Protocol not found.'}), 404
    if source.origin != 'admin' or not source.is_published:
        return jsonify({'error': 'Can only copy published admin protocols.'}), 403

    # Prevent duplicate copies
    existing = ImagingProtocol.query.filter_by(
        user_id=current_user.id, origin='personal', copied_from_id=source.id
    ).first()
    if existing:
        return jsonify({'error': 'This protocol is already in your library.'}), 409

    copy = ImagingProtocol(
        title=source.title,
        slug=_slugify(source.title),
        modality=source.modality,
        body_section=source.body_section,
        keywords=source.keywords,
        shorthand_text=source.shorthand_text,
        detailed_protocol_html=source.detailed_protocol_html,
        special_notes=source.special_notes,
        indication_json=source.indication_json,
        validation_json=source.validation_json,
        search_config_json=source.search_config_json,
        origin='personal',
        user_id=current_user.id,
        copied_from_id=source.id,
        is_published=False,
        is_emergency=source.is_emergency,
    )
    db.session.add(copy)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to copy protocol %d: %s", protocol_id, e)
        return jsonify({'error': 'Failed to copy protocol.'}), 500

    return jsonify({'success': True, 'protocol': copy.to_dict()})


# ==================== API: ADMIN PROTOCOL MANAGEMENT ====================

@vetting_bp.route('/api/vetting/admin/protocols', methods=['GET'])
@login_required
@require_admin
def admin_list_protocols():
    """List all admin protocols (published and unpublished)."""
    protocols = ImagingProtocol.query.filter_by(origin='admin').order_by(
        ImagingProtocol.modality, ImagingProtocol.title
    ).all()
    return jsonify({'protocols': [p.to_dict() for p in protocols]})


@vetting_bp.route('/api/vetting/admin/protocols', methods=['POST'])
@login_required
@require_admin
def admin_create_protocol():
    """Create an admin protocol."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request.'}), 400

    title = (data.get('title') or '').strip()
    modality = (data.get('modality') or '').strip()
    if not title or not modality:
        return jsonify({'error': 'Title and modality are required.'}), 400

    protocol = ImagingProtocol(
        title=title,
        slug=_slugify(title),
        modality=modality,
        body_section=data.get('body_section', '').strip() or None,
        keywords=data.get('keywords', '').strip() or None,
        shorthand_text=data.get('shorthand_text', '').strip() or None,
        detailed_protocol_html=data.get('detailed_protocol_html', '').strip() or None,
        special_notes=data.get('special_notes', '').strip() or None,
        indication_json=json.dumps(data['indication_json']) if data.get('indication_json') else None,
        validation_json=json.dumps(data['validation_json']) if data.get('validation_json') else None,
        search_config_json=json.dumps(data['search_config_json']) if data.get('search_config_json') else None,
        origin='admin',
        is_published=False,
        is_emergency=data.get('is_emergency', False),
    )
    db.session.add(protocol)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to create admin protocol: %s", e)
        return jsonify({'error': 'Failed to create protocol.'}), 500

    return jsonify({'success': True, 'protocol': protocol.to_dict()})


@vetting_bp.route('/api/vetting/admin/protocols/<int:protocol_id>', methods=['PUT'])
@login_required
@require_admin
def admin_update_protocol(protocol_id):
    """Update an admin protocol."""
    protocol = ImagingProtocol.query.get(protocol_id)
    if not protocol or protocol.origin != 'admin':
        return jsonify({'error': 'Admin protocol not found.'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request.'}), 400

    if 'title' in data:
        protocol.title = data['title'].strip()
        protocol.slug = _slugify(protocol.title)
    if 'modality' in data:
        protocol.modality = data['modality'].strip()
    if 'body_section' in data:
        protocol.body_section = data['body_section'].strip() or None
    if 'keywords' in data:
        protocol.keywords = data['keywords'].strip() or None
    if 'shorthand_text' in data:
        protocol.shorthand_text = data['shorthand_text'].strip() or None
    if 'detailed_protocol_html' in data:
        protocol.detailed_protocol_html = data['detailed_protocol_html'].strip() or None
    if 'special_notes' in data:
        protocol.special_notes = data['special_notes'].strip() or None
    if 'indication_json' in data:
        protocol.indication_json = json.dumps(data['indication_json']) if data['indication_json'] else None
    if 'validation_json' in data:
        protocol.validation_json = json.dumps(data['validation_json']) if data['validation_json'] else None
    if 'search_config_json' in data:
        protocol.search_config_json = json.dumps(data['search_config_json']) if data['search_config_json'] else None
    if 'is_emergency' in data:
        protocol.is_emergency = bool(data['is_emergency'])

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to update admin protocol %d: %s", protocol_id, e)
        return jsonify({'error': 'Failed to update protocol.'}), 500

    return jsonify({'success': True, 'protocol': protocol.to_dict()})


@vetting_bp.route('/api/vetting/admin/protocols/<int:protocol_id>/verify', methods=['POST'])
@login_required
@require_admin
def admin_verify_protocol(protocol_id):
    """Verify and publish an admin protocol."""
    protocol = ImagingProtocol.query.get(protocol_id)
    if not protocol or protocol.origin != 'admin':
        return jsonify({'error': 'Admin protocol not found.'}), 404

    protocol.is_verified = True
    protocol.is_published = True
    protocol.verified_by_user_id = current_user.id
    protocol.verified_at = datetime.utcnow()

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to verify protocol %d: %s", protocol_id, e)
        return jsonify({'error': 'Failed to verify protocol.'}), 500

    return jsonify({'success': True, 'protocol': protocol.to_dict()})


@vetting_bp.route('/api/vetting/admin/protocols/<int:protocol_id>', methods=['DELETE'])
@login_required
@require_admin
def admin_delete_protocol(protocol_id):
    """Delete an admin protocol."""
    protocol = ImagingProtocol.query.get(protocol_id)
    if not protocol or protocol.origin != 'admin':
        return jsonify({'error': 'Admin protocol not found.'}), 404

    db.session.delete(protocol)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to delete admin protocol %d: %s", protocol_id, e)
        return jsonify({'error': 'Failed to delete protocol.'}), 500

    return jsonify({'success': True})


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
