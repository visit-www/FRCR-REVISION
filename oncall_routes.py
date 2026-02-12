"""
On-Call Helper Routes

Flask blueprint for the On-Call Session Helper feature.
Provides clinical protocol search, AI-formatted answers, and admin protocol management.
"""

from flask import Blueprint, request, render_template, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import json
import os
import logging

from models import db, ClinicalProtocol, OnCallQueryLog
from access_control import require_admin

logger = logging.getLogger(__name__)

oncall_bp = Blueprint('oncall', __name__, url_prefix='/on-call-helper')


# ==================== PUBLIC ROUTES ====================

@oncall_bp.route('/')
@login_required
def oncall_helper():
    """Main on-call helper page with search interface."""
    return render_template('oncall_helper.html')


@oncall_bp.route('/api/search')
@login_required
def autocomplete_search():
    """Autocomplete search for protocols (lightweight)."""
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])

    from ai_oncall_helper import search_protocols_autocomplete
    results = search_protocols_autocomplete(query, limit=8)
    return jsonify(results)


@oncall_bp.route('/api/query', methods=['POST'])
@login_required
def submit_query():
    """Submit an on-call helper query and get AI-formatted response."""
    data = request.get_json()
    if not data or not data.get('query', '').strip():
        return jsonify({'error': 'Query text is required.'}), 400

    query_text = data['query'].strip()
    if len(query_text) > 1000:
        return jsonify({'error': 'Query too long (max 1000 characters).'}), 400

    try:
        from ai_oncall_helper import generate_oncall_response
        result = generate_oncall_response(
            query_text=query_text,
            user_id=current_user.id,
        )
        return jsonify(result)

    except Exception as exc:
        logger.error(f"On-call helper error for user {current_user.id}: {exc}")
        return jsonify({
            'error': str(exc),
            'answer_html': (
                '<div class="alert alert-danger">'
                '<i class="fas fa-exclamation-circle me-2"></i>'
                f'Error: {str(exc)}'
                '</div>'
            ),
        }), 500


@oncall_bp.route('/api/history')
@login_required
def query_history():
    """Get user's recent on-call query history."""
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 50)

    from ai_oncall_helper import get_query_history
    queries = get_query_history(current_user.id, limit=limit)

    return jsonify([
        {
            'id': q.id,
            'query_text': q.query_text,
            'response_source': q.response_source,
            'created_at': q.created_at.isoformat() if q.created_at else None,
        }
        for q in queries
    ])


@oncall_bp.route('/api/history/<int:log_id>')
@login_required
def get_query_detail(log_id):
    """Get a specific past query and its full response."""
    log_entry = OnCallQueryLog.query.get_or_404(log_id)

    # Users can only see their own queries
    if log_entry.user_id != current_user.id and not (
        hasattr(current_user, 'role') and current_user.role.value == 'admin'
    ):
        return jsonify({'error': 'Access denied.'}), 403

    return jsonify({
        'id': log_entry.id,
        'query_text': log_entry.query_text,
        'ai_response_text': log_entry.ai_response_text,
        'response_source': log_entry.response_source,
        'model_used': log_entry.model_used,
        'matched_protocol_ids': log_entry.get_matched_protocol_ids(),
        'created_at': log_entry.created_at.isoformat() if log_entry.created_at else None,
    })


# ==================== ADMIN: PROTOCOL MANAGEMENT ====================

@oncall_bp.route('/admin/protocols')
@require_admin
def admin_protocols():
    """Admin page for managing clinical protocols."""
    protocols = ClinicalProtocol.query.order_by(
        ClinicalProtocol.category,
        ClinicalProtocol.title
    ).all()

    categories = db.session.query(
        ClinicalProtocol.category
    ).distinct().order_by(ClinicalProtocol.category).all()
    categories = [c[0] for c in categories]

    return render_template('admin_protocols.html',
                           protocols=protocols,
                           categories=categories,
                           cloudinary_cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
                           cloudinary_upload_preset=os.environ.get('CLOUDINARY_UPLOAD_PRESET', ''))


@oncall_bp.route('/admin/protocols/api', methods=['GET'])
@require_admin
def list_protocols_api():
    """API: List all protocols with optional category filter."""
    category = request.args.get('category')
    query = ClinicalProtocol.query

    if category:
        query = query.filter_by(category=category)

    protocols = query.order_by(ClinicalProtocol.title).all()
    return jsonify([p.to_dict() for p in protocols])


@oncall_bp.route('/admin/protocols/api', methods=['POST'])
@require_admin
def create_protocol():
    """API: Create a new clinical protocol."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    required_fields = ['title', 'category', 'keywords', 'source_citation']
    for field in required_fields:
        if not data.get(field, '').strip():
            return jsonify({'error': f'{field} is required.'}), 400

    protocol = ClinicalProtocol(
        title=data['title'].strip(),
        category=data['category'].strip(),
        keywords=data['keywords'].strip(),
        content_structured=json.dumps(data.get('content_structured')) if data.get('content_structured') else None,
        content_html=data.get('content_html', '').strip() or None,
        source_citation=data['source_citation'].strip(),
        guideline_version=data.get('guideline_version', '').strip() or None,
        source_url=data.get('source_url', '').strip() or None,
        is_published=data.get('is_published', False),
        created_by_user_id=current_user.id,
    )

    db.session.add(protocol)
    db.session.commit()

    return jsonify(protocol.to_dict()), 201


@oncall_bp.route('/admin/protocols/api/<int:protocol_id>', methods=['GET'])
@require_admin
def get_protocol(protocol_id):
    """API: Get a single protocol."""
    protocol = ClinicalProtocol.query.get_or_404(protocol_id)
    return jsonify(protocol.to_dict())


@oncall_bp.route('/admin/protocols/api/<int:protocol_id>', methods=['PUT'])
@require_admin
def update_protocol(protocol_id):
    """API: Update a clinical protocol."""
    protocol = ClinicalProtocol.query.get_or_404(protocol_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    if 'title' in data:
        protocol.title = data['title'].strip()
    if 'category' in data:
        protocol.category = data['category'].strip()
    if 'keywords' in data:
        protocol.keywords = data['keywords'].strip()
    if 'content_structured' in data:
        protocol.content_structured = json.dumps(data['content_structured']) if data['content_structured'] else None
    if 'content_html' in data:
        protocol.content_html = data['content_html'].strip() or None
    if 'source_citation' in data:
        protocol.source_citation = data['source_citation'].strip()
    if 'guideline_version' in data:
        protocol.guideline_version = data['guideline_version'].strip() or None
    if 'source_url' in data:
        protocol.source_url = data['source_url'].strip() or None
    if 'is_published' in data:
        protocol.is_published = bool(data['is_published'])

    protocol.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify(protocol.to_dict())


@oncall_bp.route('/admin/protocols/api/<int:protocol_id>', methods=['DELETE'])
@require_admin
def delete_protocol(protocol_id):
    """API: Delete a clinical protocol."""
    protocol = ClinicalProtocol.query.get_or_404(protocol_id)
    db.session.delete(protocol)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Protocol "{protocol.title}" deleted.'})


@oncall_bp.route('/admin/protocols/api/<int:protocol_id>/verify', methods=['POST'])
@require_admin
def verify_protocol(protocol_id):
    """API: Mark a protocol as verified by the current admin."""
    protocol = ClinicalProtocol.query.get_or_404(protocol_id)
    protocol.verified_by_user_id = current_user.id
    protocol.verified_at = datetime.utcnow()
    protocol.is_published = True
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Protocol "{protocol.title}" verified and published.',
        'protocol': protocol.to_dict(),
    })


@oncall_bp.route('/admin/protocols/generate', methods=['POST'])
@require_admin
def generate_protocol():
    """API: Generate a clinical protocol using AI, save as draft for admin review."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    title = (data.get('title') or '').strip()
    category = (data.get('category') or '').strip()
    if not title or not category:
        return jsonify({'error': 'Title and category are required.'}), 400

    source_citation = (data.get('source_citation') or '').strip()
    additional_context = (data.get('additional_context') or '').strip()

    try:
        from ai_oncall_helper import generate_protocol_content
        result = generate_protocol_content(
            title=title,
            category=category,
            source_citation=source_citation,
            additional_context=additional_context,
        )
    except Exception as exc:
        logger.error(f"Protocol AI generation failed: {exc}")
        return jsonify({'error': str(exc)}), 500

    # Create protocol as DRAFT (is_published=False) — admin must review
    keywords = ', '.join(result.get('suggested_keywords', []))
    protocol = ClinicalProtocol(
        title=title,
        category=category,
        keywords=keywords or title,
        content_html=result.get('content_html') or None,
        content_structured=json.dumps(result.get('content_structured')) if result.get('content_structured') else None,
        source_citation=source_citation or 'AI-generated — verify against published guideline',
        guideline_version=result.get('guideline_version') or None,
        is_published=False,
        created_by_user_id=current_user.id,
    )

    db.session.add(protocol)
    db.session.commit()

    return jsonify({
        'success': True,
        'protocol': protocol.to_dict(),
        'warnings': result.get('warnings', []),
        'message': f'Protocol "{title}" generated as draft. Review content and publish when verified.',
    })


@oncall_bp.route('/admin/protocols/api/<int:protocol_id>/unpublish', methods=['POST'])
@require_admin
def unpublish_protocol(protocol_id):
    """API: Unpublish a protocol (keep in DB but hide from search)."""
    protocol = ClinicalProtocol.query.get_or_404(protocol_id)
    protocol.is_published = False
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Protocol "{protocol.title}" unpublished.',
    })
