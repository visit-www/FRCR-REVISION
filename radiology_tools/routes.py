"""
Radiology Tools Routes

Flask blueprint for radiology tools (incidental findings calculators etc.).
Provides finder UI, individual calculator views, and admin management.
URL prefix: /incidental-findings (kept for backward compatibility).
"""

from flask import Blueprint, request, render_template, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import json
import os
import re
import logging

from models import db, IncidentalFindingCalculator, ContentIntelligence
from access_control import require_admin
from clinical_tool_generator import extract_html_content

logger = logging.getLogger(__name__)

if_bp = Blueprint('radiology_tools', __name__, url_prefix='/incidental-findings')


# ==================== PUBLIC ROUTES ====================

# New canonical categories: (slug, display_name, accent_color, pastel_color, icon)
TOOL_CATEGORIES = [
    ('management_guidelines', 'Management Guidelines', '#1b6ec2', '#e1edfb', 'fa-book-medical'),
    ('calculators',           'Calculators',           '#e96304', '#fdeee4', 'fa-calculator'),
    ('classifications',       'Classifications',       '#7c3aed', '#ece4f6', 'fa-layer-group'),
    ('decision_tools',        'Decision Tools',        '#198754', '#e2f2e8', 'fa-project-diagram'),
]

# Map old DB categories → new category slugs
_CAT_MAP = {
    # Old standard categories
    'Guidelines': 'management_guidelines',
    'Classification': 'classifications',
    'Calculator': 'calculators',
    'Scoring': 'calculators',
    # New canonical slugs (identity)
    'management_guidelines': 'management_guidelines',
    'calculators': 'calculators',
    'classifications': 'classifications',
    'decision_tools': 'decision_tools',
    # Organ-based categories from batch_tools → management_guidelines
    'thyroid': 'management_guidelines',
    'renal': 'management_guidelines',
    'hepatic': 'management_guidelines',
    'pancreatic': 'management_guidelines',
    'ovarian': 'management_guidelines',
    'pulmonary': 'management_guidelines',
    'splenic': 'management_guidelines',
    'hepatobiliary': 'management_guidelines',
    'mediastinal': 'management_guidelines',
    # Scoring / calculators / reference
    'scoring': 'calculators',
    'vascular': 'calculators',
    'dose': 'calculators',
    'reference': 'calculators',
}

# Build metadata dict for template convenience
_CAT_META = {slug: {'name': name, 'color': color, 'pastel': pastel, 'icon': icon}
             for slug, name, color, pastel, icon in TOOL_CATEGORIES}


@if_bp.route('/')
def finder():
    """Main radiology tools browse page (public)."""
    calculators = IncidentalFindingCalculator.query.filter_by(
        is_available=True
    ).order_by(
        IncidentalFindingCalculator.finding_name
    ).all()

    # Group by new canonical category
    grouped = {}
    for calc in calculators:
        cat = _CAT_MAP.get(calc.category or '', 'management_guidelines')
        grouped.setdefault(cat, []).append(calc)

    return render_template('radiology_tools_user.html',
                           calculators=calculators,
                           grouped=grouped,
                           tool_categories=TOOL_CATEGORIES,
                           cat_meta=_CAT_META)


@if_bp.route('/<slug>')
def view_calculator(slug):
    """View a specific incidental finding calculator (public)."""
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

    # Load AI cross-links
    ai_cross_links = []
    try:
        ci = ContentIntelligence.query.filter_by(
            content_type='radiology_tool', content_id=calculator.id
        ).first()
        if ci and ci.cross_links_json:
            _links = _json.loads(ci.cross_links_json)
            ai_cross_links = [l for l in _links if l.get('url')]
    except Exception:
        pass

    return render_template('radiology_tools_viewer.html',
                           calculator=calculator,
                           content=content,
                           resources=resources,
                           ai_cross_links=ai_cross_links)


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
                'mapped_category': _CAT_MAP.get(r.category or '', 'management_guidelines'),
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
                'mapped_category': _CAT_MAP.get(c.category or '', 'management_guidelines'),
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

def _guideline_display(raw):
    """Extract human-readable guideline text from raw guideline_source (may be JSON)."""
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            refs = obj.get('references') or []
            sources = [r.get('source') or r.get('url', '') for r in refs if isinstance(r, dict)]
            sources = [s for s in sources if s]
            return ', '.join(sources) if sources else None
    except (json.JSONDecodeError, TypeError):
        pass
    return raw


@if_bp.route('/admin')
@require_admin
def admin_list():
    """Admin page for managing incidental finding calculators."""
    calculators = IncidentalFindingCalculator.query.order_by(
        IncidentalFindingCalculator.category,
        IncidentalFindingCalculator.finding_name
    ).all()
    for c in calculators:
        c._guideline_display = _guideline_display(c.guideline_source)
    return render_template('radiology_tools_admin.html', calculators=calculators,
                           cloudinary_cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
                           cloudinary_upload_preset=os.environ.get('CLOUDINARY_UPLOAD_PRESET', ''))


@if_bp.route('/admin/edit/<int:calc_id>')
@require_admin
def edit_tool(calc_id):
    """Full-page editor for a radiology tool."""
    calculator = IncidentalFindingCalculator.query.get_or_404(calc_id)
    return render_template('edit_radiology_tool.html',
                           calculator=calculator,
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

    calculator = IncidentalFindingCalculator(
        slug=slug,
        finding_name=finding_name,
        body_section=data.get('body_section', '').strip() or None,
        category=data.get('category', '').strip() or None,
        description=data.get('description', '').strip() or None,
        keywords=data.get('keywords', '').strip() or None,
        calculator_html=data.get('calculator_html', '').strip() or None,
        algorithm_html=data.get('algorithm_html', '').strip() or None,
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

    for field in ['finding_name', 'body_section', 'category', 'description', 'keywords',
                  'calculator_html', 'algorithm_html', 'guideline_source', 'guideline_version',
                  'guideline_url', 'last_edit_note']:
        if field in data:
            val = data[field]
            val = val.strip() if isinstance(val, str) else val
            setattr(calculator, field, val)

    if 'is_available' in data:
        calculator.is_available = bool(data['is_available'])

    # Auto-refresh keywords from HTML content if calculator_html was updated
    if 'calculator_html' in data and data['calculator_html']:
        from radiology_tools.generator import _extract_keywords_from_html
        calculator.keywords = _extract_keywords_from_html(
            data['calculator_html'],
            finding_name=calculator.finding_name,
            category=calculator.category or '',
            guideline_source=calculator.guideline_source or '',
        )

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

    # Parse guideline_source JSON into resources dict for URL/PDF fetching
    resources = None
    guideline_source = data.get('guideline_source', '')
    if guideline_source:
        try:
            resources = json.loads(guideline_source) if isinstance(guideline_source, str) else guideline_source
        except (json.JSONDecodeError, TypeError):
            pass

    try:
        from .generator import generate_if_calculator_html
        result = generate_if_calculator_html(
            finding_name=finding_name,
            guideline_source=guideline_source,
            category=data.get('category', ''),
            body_section=data.get('body_section', ''),
            additional_context=data.get('additional_context', ''),
            user_id=current_user.id,
            overwrite=data.get('overwrite', False),
            resources=resources,
        )

        # Track AI usage
        try:
            from ai_cost_tracker import track_ai_call
            track_ai_call(current_user.id, 'generate_if_calculator',
                          model=result.get('model', ''),
                          output_tokens=result.get('token_count'),
                          input_summary=f"if_calc: {finding_name[:200]}")
        except Exception:
            pass

        return jsonify(result)

    except Exception as exc:
        logger.error(f"IF calculator generation failed: {exc}")
        return jsonify({'error': str(exc)}), 500
