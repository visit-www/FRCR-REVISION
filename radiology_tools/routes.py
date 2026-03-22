"""
Radiology Tools Routes

Flask blueprint for radiology tools (incidental findings calculators etc.).
Provides finder UI, individual calculator views, and admin management.
URL prefix: /incidental-findings (kept for backward compatibility).
"""

from flask import Blueprint, request, render_template, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import os
import re
import logging

from models import db, IncidentalFindingCalculator
from access_control import require_admin
from clinical_tool_generator import extract_html_content

logger = logging.getLogger(__name__)

if_bp = Blueprint('radiology_tools', __name__, url_prefix='/incidental-findings')


# ==================== PUBLIC ROUTES ====================

@if_bp.route('/')
@login_required
def finder():
    """Main incidental findings finder page."""
    calculators = IncidentalFindingCalculator.query.filter_by(
        is_available=True
    ).order_by(
        IncidentalFindingCalculator.category,
        IncidentalFindingCalculator.finding_name
    ).all()

    # Group by category
    grouped = {}
    for calc in calculators:
        cat = calc.category or 'Other'
        grouped.setdefault(cat, []).append(calc)

    return render_template('radiology_tools_user.html',
                           calculators=calculators,
                           grouped=grouped)


@if_bp.route('/<slug>')
@login_required
def view_calculator(slug):
    """View a specific incidental finding calculator."""
    calculator = IncidentalFindingCalculator.query.filter_by(
        slug=slug, is_available=True
    ).first_or_404()

    # Extract calculator content for rendering (same pattern as TNM calculator)
    content = {'styles': '', 'body': ''}
    if calculator.calculator_html:
        content = extract_html_content(calculator.calculator_html)

    # Parse resources from guideline_source JSON (handles double-encoded strings)
    import json as _json
    resources = {'references': [], 'linked_cases': [], 'linked_tnm': [], 'pdfs': []}
    source_field = calculator.guideline_source
    if source_field:
        try:
            parsed = _json.loads(source_field)
            # Handle double-encoded JSON (JSON.stringify called twice on frontend)
            if isinstance(parsed, str):
                parsed = _json.loads(parsed)
            if isinstance(parsed, dict):
                resources = {
                    'references': parsed.get('references', []),
                    'linked_cases': parsed.get('linked_cases', []),
                    'linked_tnm': parsed.get('linked_tnm', []),
                    'pdfs': parsed.get('pdfs', []),
                }
            elif isinstance(parsed, list):
                resources['references'] = parsed
        except (_json.JSONDecodeError, TypeError):
            if source_field.strip() and not source_field.strip().startswith('{'):
                resources['references'] = [{'source': source_field.strip(), 'version': '', 'url': ''}]

    return render_template('radiology_tools_viewer.html',
                           calculator=calculator,
                           content=content,
                           resources=resources)


@if_bp.route('/api/search')
@login_required
def search_calculators():
    """Search incidental findings calculators."""
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])

    try:
        from sqlalchemy import text
        sql = text("""
            SELECT id, slug, finding_name, category, body_section, description,
                   guideline_source,
                   GREATEST(
                       similarity(finding_name, :query),
                       COALESCE(similarity(keywords, :query), 0)
                   ) AS sim
            FROM incidental_finding_calculator
            WHERE is_available = TRUE
              AND (
                  similarity(finding_name, :query) > 0.1
                  OR similarity(keywords, :query) > 0.1
                  OR finding_name ILIKE :like_query
                  OR keywords ILIKE :like_query
              )
            ORDER BY sim DESC
            LIMIT 10
        """)
        results = db.session.execute(sql, {
            'query': query,
            'like_query': f'%{query}%',
        }).fetchall()

        return jsonify([
            {
                'id': r.id, 'slug': r.slug, 'finding_name': r.finding_name,
                'category': r.category, 'body_section': r.body_section,
                'description': r.description, 'guideline_source': r.guideline_source,
                'url': f'/incidental-findings/{r.slug}',
            }
            for r in results
        ])

    except Exception:
        # Fallback for SQLite
        calcs = IncidentalFindingCalculator.query.filter(
            IncidentalFindingCalculator.is_available == True,
            db.or_(
                IncidentalFindingCalculator.finding_name.ilike(f'%{query}%'),
                IncidentalFindingCalculator.keywords.ilike(f'%{query}%'),
            ),
        ).limit(10).all()
        return jsonify([
            {
                'id': c.id, 'slug': c.slug, 'finding_name': c.finding_name,
                'category': c.category, 'body_section': c.body_section,
                'description': c.description, 'guideline_source': c.guideline_source,
                'url': f'/incidental-findings/{c.slug}',
            }
            for c in calcs
        ])


@if_bp.route('/embed/<slug>')
@login_required
def embed_calculator(slug):
    """Render a calculator in embed mode (for Smart Reporter Tool Panel)."""
    calculator = IncidentalFindingCalculator.query.filter_by(
        slug=slug, is_available=True
    ).first_or_404()

    if not calculator.calculator_html:
        return "Calculator content not available", 404

    return calculator.calculator_html


# ==================== ADMIN ROUTES ====================

@if_bp.route('/admin')
@require_admin
def admin_list():
    """Admin page for managing incidental finding calculators."""
    calculators = IncidentalFindingCalculator.query.order_by(
        IncidentalFindingCalculator.category,
        IncidentalFindingCalculator.finding_name
    ).all()
    return render_template('radiology_tools_admin.html', calculators=calculators,
                           cloudinary_cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
                           cloudinary_upload_preset=os.environ.get('CLOUDINARY_UPLOAD_PRESET', ''))


@if_bp.route('/admin/api', methods=['POST'])
@require_admin
def create_calculator():
    """API: Create a new incidental finding calculator."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    finding_name = data.get('finding_name', '').strip()
    if not finding_name:
        return jsonify({'error': 'finding_name is required.'}), 400

    slug = re.sub(r'[^a-z0-9]+', '-', finding_name.lower()).strip('-')

    existing = IncidentalFindingCalculator.query.filter_by(slug=slug).first()
    if existing:
        return jsonify({'error': f'Calculator with slug "{slug}" already exists.'}), 409

    from app import sanitize_clinical_html
    calculator = IncidentalFindingCalculator(
        slug=slug,
        finding_name=finding_name,
        body_section=data.get('body_section', '').strip() or None,
        category=data.get('category', '').strip() or None,
        description=data.get('description', '').strip() or None,
        keywords=data.get('keywords', '').strip() or None,
        calculator_html=sanitize_clinical_html(data.get('calculator_html', '').strip() or None),
        algorithm_html=sanitize_clinical_html(data.get('algorithm_html', '').strip() or None),
        guideline_source=data.get('guideline_source', '').strip() or None,
        guideline_version=data.get('guideline_version', '').strip() or None,
        guideline_url=data.get('guideline_url', '').strip() or None,
        is_available=data.get('is_available', False),
        created_by_user_id=current_user.id,
    )

    db.session.add(calculator)
    db.session.commit()

    return jsonify(calculator.to_dict()), 201


@if_bp.route('/admin/api/<int:calc_id>', methods=['GET'])
@require_admin
def get_calculator(calc_id):
    """API: Get a single incidental finding calculator."""
    calculator = IncidentalFindingCalculator.query.get_or_404(calc_id)
    return jsonify(calculator.to_dict())


@if_bp.route('/admin/api/<int:calc_id>', methods=['PUT'])
@require_admin
def update_calculator(calc_id):
    """API: Update an incidental finding calculator."""
    calculator = IncidentalFindingCalculator.query.get_or_404(calc_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    from app import sanitize_clinical_html
    _html_fields = {'calculator_html', 'algorithm_html'}
    for field in ['finding_name', 'body_section', 'category', 'description', 'keywords',
                  'calculator_html', 'algorithm_html', 'guideline_source', 'guideline_version',
                  'guideline_url', 'last_edit_note']:
        if field in data:
            val = data[field]
            val = val.strip() if isinstance(val, str) else val
            if field in _html_fields and isinstance(val, str):
                val = sanitize_clinical_html(val)
            setattr(calculator, field, val)

    if 'is_available' in data:
        calculator.is_available = bool(data['is_available'])

    calculator.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify(calculator.to_dict())


@if_bp.route('/admin/api/<int:calc_id>', methods=['DELETE'])
@require_admin
def delete_calculator(calc_id):
    """API: Delete an incidental finding calculator."""
    calculator = IncidentalFindingCalculator.query.get_or_404(calc_id)
    name = calculator.finding_name
    db.session.delete(calculator)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Calculator "{name}" deleted.'})


@if_bp.route('/admin/api/<int:calc_id>/verify', methods=['POST'])
@require_admin
def verify_calculator(calc_id):
    """API: Mark a calculator as verified by admin."""
    calculator = IncidentalFindingCalculator.query.get_or_404(calc_id)
    calculator.verified_by_user_id = current_user.id
    calculator.verified_at = datetime.utcnow()
    calculator.is_available = True
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Calculator "{calculator.finding_name}" verified and published.',
        'calculator': calculator.to_dict(),
    })


@if_bp.route('/admin/generate', methods=['POST'])
@require_admin
def generate_calculator():
    """API: Generate an incidental finding calculator using Claude."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    finding_name = data.get('finding_name', '').strip()
    if not finding_name:
        return jsonify({'error': 'finding_name is required.'}), 400

    try:
        from .generator import generate_if_calculator_html
        result = generate_if_calculator_html(
            finding_name=finding_name,
            guideline_source=data.get('guideline_source', ''),
            category=data.get('category', ''),
            body_section=data.get('body_section', ''),
            additional_context=data.get('additional_context', ''),
            user_id=current_user.id,
        )
        return jsonify(result)

    except Exception as exc:
        logger.error(f"IF calculator generation failed: {exc}")
        return jsonify({'error': str(exc)}), 500
