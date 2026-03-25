"""
Protocol Routes

Flask blueprint for clinical protocols (admin CRUD, user browse, AI generation)
and the On-Call Query Helper (protocol-backed AI search).

URL structure:
  /radiology-protocols           — user browse page (in app.py, uses PROTOCOL_CATEGORIES)
  /radiology-protocols/admin     — admin management page
  /radiology-protocols/admin/api — admin CRUD API
  /radiology-protocols/view/<id> — individual protocol view
  /on-call-helper                — on-call query search interface
  /on-call-helper/api/*          — on-call query API
"""

from flask import Blueprint, request, render_template, jsonify, redirect
from flask_login import login_required, current_user
from datetime import datetime
import json
import os
import logging

from models import db, ClinicalProtocol, OnCallQueryLog, ContentIntelligence
from access_control import require_admin

logger = logging.getLogger(__name__)

# Shared protocol category definitions — (slug, display_name, color, icon)
PROTOCOL_CATEGORIES = [
    ('acute_emergency', 'Acute & Emergency Imaging Pathways', '#dc3545', 'fa-ambulance'),
    ('diagnostic_algorithms', 'Diagnostic Imaging Algorithms', '#5E899E', 'fa-project-diagram'),
    ('interventional', 'Interventional Radiology Protocols', '#6b46c1', 'fa-syringe'),
    ('pre_procedural', 'Pre-Procedural Risk Assessment', '#e96304', 'fa-clipboard-check'),
    ('intra_procedural', 'Intra-Procedural Safety', '#d63384', 'fa-heartbeat'),
    ('post_procedural', 'Post-Procedural Care', '#198754', 'fa-notes-medical'),
    ('contrast_safety', 'Contrast Media Safety', '#0d6efd', 'fa-tint'),
    ('mri_safety', 'MRI Safety', '#6610f2', 'fa-magnet'),
    ('radiation_protection', 'Radiation Protection', '#fd7e14', 'fa-radiation'),
    ('special_populations', 'Special Populations', '#20c997', 'fa-baby'),
    ('medication_risk', 'Medication & Systemic Risk', '#ffc107', 'fa-pills'),
    ('adverse_events', 'Adverse Event Management', '#dc3545', 'fa-exclamation-triangle'),
]

# Quick lookup dicts
CATEGORY_MAP = {slug: {'name': name, 'color': color, 'icon': icon}
                for slug, name, color, icon in PROTOCOL_CATEGORIES}
CATEGORY_ORDER = [slug for slug, _, _, _ in PROTOCOL_CATEGORIES]

# No url_prefix — each route specifies its full path
protocol_bp = Blueprint('protocol', __name__)


# ==================== ON-CALL QUERY HELPER ====================

def _parse_display_source(source_citation):
    """Extract readable source text from source_citation (may be JSON or plain text)."""
    if not source_citation:
        return None
    s = source_citation.strip()
    if s.startswith('{'):
        try:
            data = json.loads(s)
            refs = data.get('references', [])
            names = [r.get('source', '') for r in refs if r.get('source', '').strip()]
            return '; '.join(names) if names else None
        except (json.JSONDecodeError, TypeError):
            return s
    return s


@protocol_bp.route('/on-call-helper')
@login_required
def oncall_helper():
    """Retired: redirect to protocol browse (protocols now in unified search)."""
    return redirect('/radiology-protocols', code=302)


@protocol_bp.route('/on-call-helper/api/search')
@login_required
def autocomplete_search():
    """Autocomplete search for protocols (lightweight). Kept for backward compat."""
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])

    from ai_protocol_helper import search_protocols_autocomplete
    results = search_protocols_autocomplete(query, limit=8)
    return jsonify(results)


# DEPRECATED (Mar 2026): AI query feature retired — protocols now searchable
# via unified search (/api/algorithms/search?type=protocol). Kept for audit trail.
# @protocol_bp.route('/on-call-helper/api/query', methods=['POST'])
# @login_required
# def submit_query():
#     """Submit an on-call helper query and get AI-formatted response."""
#     ...
@protocol_bp.route('/on-call-helper/api/query', methods=['POST'])
@login_required
def submit_query():
    """DEPRECATED: AI query retired. Returns message directing to unified search."""
    return jsonify({
        'error': 'The AI query feature has been retired. '
                 'Protocols are now searchable via the main search bar.',
        'deprecated': True,
    }), 410


@protocol_bp.route('/on-call-helper/api/history')
@login_required
def query_history():
    """Get user's recent on-call query history."""
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 50)

    from ai_protocol_helper import get_query_history
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


@protocol_bp.route('/on-call-helper/api/history/<int:log_id>')
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


# ==================== USER-FACING BROWSE & SEARCH ====================

@protocol_bp.route('/radiology-protocols')
@login_required
def radiology_protocols_index():
    """User-facing browse page for clinical protocols."""
    protocols = ClinicalProtocol.query.filter_by(is_published=True).order_by(ClinicalProtocol.title).all()
    grouped = {}
    for p in protocols:
        # Parse display_source from JSON source_citation
        p.display_source = _parse_display_source(p.source_citation)
        cat = p.category or 'Other'
        grouped.setdefault(cat, []).append(p)
    return render_template('radiology_protocols_user.html',
                           grouped=grouped,
                           protocols=protocols,
                           protocol_categories=PROTOCOL_CATEGORIES,
                           category_map=CATEGORY_MAP)


@protocol_bp.route('/radiology-protocols/api/search')
@login_required
def radiology_protocols_search():
    """Search published clinical protocols."""
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    protocols = ClinicalProtocol.query.filter(
        ClinicalProtocol.is_published == True,
        db.or_(
            ClinicalProtocol.title.ilike(f'%{q}%'),
            ClinicalProtocol.keywords.ilike(f'%{q}%'),
        )
    ).order_by(ClinicalProtocol.title).limit(20).all()
    return jsonify([{
        'id': p.id, 'title': p.title, 'category': p.category,
        'url': f'/radiology-protocols/view/{p.id}'
    } for p in protocols])


# ==================== PROTOCOL VIEW ====================

@protocol_bp.route('/radiology-protocols/view/<int:protocol_id>')
@login_required
def view_protocol(protocol_id):
    """Individual protocol view page."""
    protocol = ClinicalProtocol.query.filter_by(
        id=protocol_id, is_published=True
    ).first_or_404()

    # Parse resources from source_citation (JSON format)
    resources = None
    if protocol.source_citation:
        try:
            resources = json.loads(protocol.source_citation)
            # Resolve linked cases
            if resources.get('linked_cases'):
                from models import Case
                case_ids = [c.get('id') for c in resources['linked_cases'] if c.get('id')]
                if case_ids:
                    cases = Case.query.filter(Case.id.in_(case_ids)).all()
                    resources['linked_cases'] = [
                        {'id': c.id, 'case_number': c.case_number, 'diagnosis': c.diagnosis or ''}
                        for c in cases
                    ]
            # Resolve linked TNM calculators
            if resources.get('linked_tnm'):
                from models import TNMCalculatorContent
                calc_ids = [t.get('id') for t in resources['linked_tnm'] if t.get('id')]
                slugs = [t.get('slug') for t in resources['linked_tnm'] if t.get('slug') and not t.get('id')]
                tnm_list = []
                if calc_ids:
                    tnms = TNMCalculatorContent.query.filter(TNMCalculatorContent.id.in_(calc_ids)).all()
                    tnm_list.extend([{'id': t.id, 'slug': t.slug, 'cancer_name': t.cancer_name} for t in tnms])
                if slugs:
                    tnms = TNMCalculatorContent.query.filter(TNMCalculatorContent.slug.in_(slugs)).all()
                    existing_ids = {t['id'] for t in tnm_list}
                    tnm_list.extend([{'id': t.id, 'slug': t.slug, 'cancer_name': t.cancer_name} for t in tnms if t.id not in existing_ids])
                resources['linked_tnm'] = tnm_list
            # Resolve linked algorithms
            if resources.get('linked_algorithms'):
                from models import ReportingAlgorithm
                algo_ids = [a.get('id') for a in resources['linked_algorithms'] if a.get('id')]
                if algo_ids:
                    algos = ReportingAlgorithm.query.filter(ReportingAlgorithm.id.in_(algo_ids)).all()
                    resources['linked_algorithms'] = [
                        {'id': a.id, 'title': a.title, 'slug': a.slug}
                        for a in algos
                    ]
            # Resolve linked templates
            if resources.get('linked_templates'):
                from models import RadiologyTemplate
                tmpl_ids = [t.get('id') for t in resources['linked_templates'] if t.get('id')]
                if tmpl_ids:
                    tmpls = RadiologyTemplate.query.filter(RadiologyTemplate.id.in_(tmpl_ids)).all()
                    resources['linked_templates'] = [
                        {'id': t.id, 'title': t.title, 'slug': t.slug}
                        for t in tmpls
                    ]
            # Resolve linked pearls
            if resources.get('linked_pearls'):
                from models import RadiologyPearl
                pearl_ids = [p.get('id') for p in resources['linked_pearls'] if p.get('id')]
                if pearl_ids:
                    pearls = RadiologyPearl.query.filter(RadiologyPearl.id.in_(pearl_ids)).all()
                    resources['linked_pearls'] = [
                        {'id': p.id, 'pearl_text': (p.pearl_text or '')[:120]}
                        for p in pearls
                    ]
        except (json.JSONDecodeError, TypeError):
            resources = None

    resources_json = json.dumps(resources) if resources else '{}'

    # Load AI cross-links
    ai_cross_links = []
    try:
        ci = ContentIntelligence.query.filter_by(
            content_type='protocol', content_id=protocol.id
        ).first()
        if ci and ci.cross_links_json:
            _links = json.loads(ci.cross_links_json)
            ai_cross_links = [l for l in _links if l.get('url')]
    except Exception:
        pass

    return render_template('protocol_view.html',
                           protocol=protocol,
                           resources=resources,
                           resources_json=resources_json,
                           category_map=CATEGORY_MAP,
                           ai_cross_links=ai_cross_links)


# ==================== STUDENT LINK/UNLINK API ====================

def _collect_protocol_linkable_items(resources):
    """Extract flat list of {type, id} dicts from protocol resource JSON."""
    items = []
    if not resources or not isinstance(resources, dict):
        return items
    _MAP = {
        'linked_cases': 'case',
        'linked_tnm': 'calculator',
        'linked_algorithms': 'algorithm',
        'linked_templates': 'template',
        'linked_pearls': 'pearl',
    }
    for key, ctype in _MAP.items():
        for entry in resources.get(key, []):
            item_id = entry.get('id')
            if not item_id and ctype == 'calculator':
                # Fallback: resolve slug to id
                slug = entry.get('slug')
                if slug:
                    from models import TNMCalculatorContent
                    calc = TNMCalculatorContent.query.filter_by(slug=slug).first()
                    if calc:
                        item_id = calc.id
            if item_id:
                items.append({'type': ctype, 'id': int(item_id)})
    return items


def _propagate_cross_links(items, user_id):
    """Create cross-links between all items co-linked on a protocol.
    Uses legacy case-* tables for case-involved pairs, content_links for the rest.
    Additive only — silently skips existing links."""
    from models import (case_algorithm_links, case_template_links,
                        case_pearl_links, case_calculator_links, content_links)

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a = items[i]
            b = items[j]
            if a['type'] == b['type'] and a['id'] == b['id']:
                continue  # same item

            case_side = None
            other_type = None
            other_id = None
            if a['type'] == 'case':
                case_side, other_type, other_id = a['id'], b['type'], b['id']
            elif b['type'] == 'case':
                case_side, other_type, other_id = b['id'], a['type'], a['id']

            try:
                if case_side is not None:
                    # Use legacy tables
                    if other_type == 'algorithm':
                        exists = db.session.execute(
                            db.select(case_algorithm_links.c.id).where(
                                case_algorithm_links.c.case_id == case_side,
                                case_algorithm_links.c.algorithm_id == other_id,
                            )
                        ).first()
                        if not exists:
                            db.session.execute(case_algorithm_links.insert().values(
                                case_id=case_side, algorithm_id=other_id,
                                created_by_user_id=user_id,
                            ))
                    elif other_type == 'template':
                        exists = db.session.execute(
                            db.select(case_template_links.c.id).where(
                                case_template_links.c.case_id == case_side,
                                case_template_links.c.template_id == other_id,
                            )
                        ).first()
                        if not exists:
                            db.session.execute(case_template_links.insert().values(
                                case_id=case_side, template_id=other_id,
                                created_by_user_id=user_id,
                            ))
                    elif other_type == 'pearl':
                        exists = db.session.execute(
                            db.select(case_pearl_links.c.id).where(
                                case_pearl_links.c.case_id == case_side,
                                case_pearl_links.c.pearl_id == other_id,
                            )
                        ).first()
                        if not exists:
                            db.session.execute(case_pearl_links.insert().values(
                                case_id=case_side, pearl_id=other_id,
                                created_by_user_id=user_id,
                            ))
                    elif other_type == 'calculator':
                        exists = db.session.execute(
                            db.select(case_calculator_links.c.id).where(
                                case_calculator_links.c.case_id == case_side,
                                case_calculator_links.c.calculator_id == other_id,
                            )
                        ).first()
                        if not exists:
                            db.session.execute(case_calculator_links.insert().values(
                                case_id=case_side, calculator_id=other_id,
                                created_by_user_id=user_id,
                            ))
                else:
                    # Non-case pair → content_links with canonical ordering
                    s_type, s_id = a['type'], a['id']
                    t_type, t_id = b['type'], b['id']
                    if s_type > t_type or (s_type == t_type and s_id > t_id):
                        s_type, s_id, t_type, t_id = t_type, t_id, s_type, s_id
                    exists = db.session.execute(
                        db.select(content_links.c.id).where(
                            content_links.c.source_type == s_type,
                            content_links.c.source_id == s_id,
                            content_links.c.target_type == t_type,
                            content_links.c.target_id == t_id,
                        )
                    ).first()
                    if not exists:
                        db.session.execute(content_links.insert().values(
                            source_type=s_type, source_id=s_id,
                            target_type=t_type, target_id=t_id,
                            created_by_user_id=user_id,
                        ))
            except Exception:
                logger.debug(f"Cross-link skip: {a} ↔ {b}", exc_info=True)
                continue

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.warning("Cross-link commit failed", exc_info=True)


# Type mapping from frontend link_type → resource JSON key
_LINK_TYPE_TO_KEY = {
    'case': 'linked_cases',
    'calculator': 'linked_tnm',
    'reporting_algorithm': 'linked_algorithms',
    'radiology_template': 'linked_templates',
    'pearl': 'linked_pearls',
}


@protocol_bp.route('/radiology-protocols/view/<int:protocol_id>/link', methods=['POST'])
@login_required
def add_protocol_link(protocol_id):
    """Student/user: link content to a protocol."""
    protocol = ClinicalProtocol.query.filter_by(
        id=protocol_id, is_published=True
    ).first_or_404()

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    link_type = (data.get('link_type') or '').strip()
    item = data.get('item')
    if link_type not in _LINK_TYPE_TO_KEY or not item or not item.get('id'):
        return jsonify({'error': 'link_type and item with id required'}), 400

    # Parse existing resources
    try:
        resources = json.loads(protocol.source_citation) if protocol.source_citation else {}
    except (json.JSONDecodeError, TypeError):
        resources = {}

    key = _LINK_TYPE_TO_KEY[link_type]
    if key not in resources:
        resources[key] = []

    item_id = item['id']
    # Check for duplicates
    existing_ids = set()
    for entry in resources[key]:
        eid = entry.get('id') or entry.get('slug')
        if eid:
            existing_ids.add(str(eid))
    if str(item_id) in existing_ids:
        return jsonify({'error': 'Already linked'}), 400

    resources[key].append(item)
    protocol.source_citation = json.dumps(resources)
    protocol.updated_at = datetime.utcnow()
    db.session.commit()

    # Propagate cross-links if ≥2 items total
    all_items = _collect_protocol_linkable_items(resources)
    if len(all_items) >= 2:
        _propagate_cross_links(all_items, current_user.id)

    return jsonify({'success': True})


@protocol_bp.route('/radiology-protocols/view/<int:protocol_id>/link', methods=['DELETE'])
@login_required
def remove_protocol_link(protocol_id):
    """Student/user: unlink content from a protocol."""
    protocol = ClinicalProtocol.query.filter_by(
        id=protocol_id, is_published=True
    ).first_or_404()

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    link_type = (data.get('link_type') or '').strip()
    item_id = data.get('item_id')
    if link_type not in _LINK_TYPE_TO_KEY or not item_id:
        return jsonify({'error': 'link_type and item_id required'}), 400

    try:
        resources = json.loads(protocol.source_citation) if protocol.source_citation else {}
    except (json.JSONDecodeError, TypeError):
        resources = {}

    key = _LINK_TYPE_TO_KEY[link_type]
    if key in resources:
        resources[key] = [
            entry for entry in resources[key]
            if str(entry.get('id', '')) != str(item_id) and str(entry.get('slug', '')) != str(item_id)
        ]

    protocol.source_citation = json.dumps(resources)
    protocol.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True})


# ==================== ADMIN: PROTOCOL MANAGEMENT ====================

@protocol_bp.route('/radiology-protocols/admin')
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
                           protocol_categories=PROTOCOL_CATEGORIES,
                           category_map=CATEGORY_MAP,
                           cloudinary_cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
                           cloudinary_upload_preset=os.environ.get('CLOUDINARY_UPLOAD_PRESET', ''))


@protocol_bp.route('/radiology-protocols/admin/api', methods=['GET'])
@require_admin
def list_protocols_api():
    """API: List all protocols with optional category filter."""
    category = request.args.get('category')
    query = ClinicalProtocol.query

    if category:
        query = query.filter_by(category=category)

    protocols = query.order_by(ClinicalProtocol.title).all()
    return jsonify([p.to_dict() for p in protocols])


@protocol_bp.route('/radiology-protocols/admin/api', methods=['POST'])
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

    from app import sanitize_clinical_html
    protocol = ClinicalProtocol(
        title=data['title'].strip(),
        category=data['category'].strip(),
        keywords=data['keywords'].strip(),
        content_structured=json.dumps(data.get('content_structured')) if data.get('content_structured') else None,
        content_html=sanitize_clinical_html(data.get('content_html', '').strip() or None),
        source_citation=data['source_citation'].strip(),
        guideline_version=data.get('guideline_version', '').strip() or None,
        source_url=data.get('source_url', '').strip() or None,
        body_section=data.get('body_section', '').strip() or None,
        is_published=data.get('is_published', False),
        created_by_user_id=current_user.id,
    )

    db.session.add(protocol)
    db.session.commit()

    return jsonify(protocol.to_dict()), 201


@protocol_bp.route('/radiology-protocols/admin/api/<int:protocol_id>', methods=['GET'])
@require_admin
def get_protocol(protocol_id):
    """API: Get a single protocol."""
    protocol = ClinicalProtocol.query.get_or_404(protocol_id)
    return jsonify(protocol.to_dict())


@protocol_bp.route('/radiology-protocols/admin/api/<int:protocol_id>', methods=['PUT'])
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
        from app import sanitize_clinical_html
        protocol.content_html = sanitize_clinical_html(data['content_html'].strip() or None)
    if 'source_citation' in data:
        protocol.source_citation = data['source_citation'].strip()
    if 'guideline_version' in data:
        protocol.guideline_version = data['guideline_version'].strip() or None
    if 'source_url' in data:
        protocol.source_url = data['source_url'].strip() or None
    if 'body_section' in data:
        protocol.body_section = data['body_section'].strip() or None
    if 'is_published' in data:
        protocol.is_published = bool(data['is_published'])

    protocol.updated_at = datetime.utcnow()
    db.session.commit()

    # Propagate cross-links for any linked content
    try:
        res = json.loads(protocol.source_citation) if protocol.source_citation else {}
        all_items = _collect_protocol_linkable_items(res)
        if len(all_items) >= 2:
            _propagate_cross_links(all_items, current_user.id)
    except Exception:
        logger.debug("Cross-link propagation skipped on admin save", exc_info=True)

    return jsonify(protocol.to_dict())


@protocol_bp.route('/radiology-protocols/admin/api/<int:protocol_id>', methods=['DELETE'])
@require_admin
def delete_protocol(protocol_id):
    """API: Delete a clinical protocol."""
    protocol = ClinicalProtocol.query.get_or_404(protocol_id)
    db.session.delete(protocol)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Protocol "{protocol.title}" deleted.'})


@protocol_bp.route('/radiology-protocols/admin/api/<int:protocol_id>/verify', methods=['POST'])
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


@protocol_bp.route('/radiology-protocols/admin/generate', methods=['POST'])
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
    body_section = (data.get('body_section') or '').strip()
    additional_context = (data.get('additional_context') or '').strip()

    try:
        from ai_protocol_helper import generate_protocol_content
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
    from app import sanitize_clinical_html
    keywords = ', '.join(result.get('suggested_keywords', []))
    protocol = ClinicalProtocol(
        title=title,
        category=category,
        keywords=keywords or title,
        content_html=sanitize_clinical_html(result.get('content_html') or None),
        content_structured=json.dumps(result.get('content_structured')) if result.get('content_structured') else None,
        source_citation=source_citation or 'AI-generated — verify against published guideline',
        guideline_version=result.get('guideline_version') or None,
        body_section=body_section or None,
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


@protocol_bp.route('/radiology-protocols/admin/edit/<int:protocol_id>')
@require_admin
def edit_protocol(protocol_id):
    """Full-page protocol editor (TinyMCE + preview, matching snippet/pearl editor)."""
    protocol = ClinicalProtocol.query.get_or_404(protocol_id)
    return render_template('edit_protocol.html',
                           protocol=protocol,
                           protocol_categories=PROTOCOL_CATEGORIES,
                           category_map=CATEGORY_MAP,
                           cloudinary_cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
                           cloudinary_upload_preset=os.environ.get('CLOUDINARY_UPLOAD_PRESET', ''))


@protocol_bp.route('/radiology-protocols/admin/api/<int:protocol_id>/regenerate', methods=['POST'])
@require_admin
def regenerate_protocol(protocol_id):
    """API: Regenerate protocol content using AI with existing metadata + optional extra context."""
    protocol = ClinicalProtocol.query.get_or_404(protocol_id)
    data = request.get_json() or {}
    additional_context = (data.get('additional_context') or '').strip()
    # Use resources from regenerate panel if provided, else fall back to protocol's stored resources
    source_citation = (data.get('source_citation') or '').strip() or protocol.source_citation or ''

    try:
        from ai_protocol_helper import generate_protocol_content
        result = generate_protocol_content(
            title=protocol.title,
            category=protocol.category or '',
            source_citation=source_citation,
            additional_context=additional_context,
        )
    except Exception as exc:
        logger.error(f"Protocol regeneration failed for {protocol_id}: {exc}")
        return jsonify({'error': str(exc)}), 500

    from app import sanitize_clinical_html
    protocol.content_html = sanitize_clinical_html(result.get('content_html') or None)
    if result.get('content_structured'):
        protocol.content_structured = json.dumps(result['content_structured'])
    if result.get('suggested_keywords'):
        protocol.keywords = ', '.join(result['suggested_keywords'])
    protocol.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'success': True,
        'content_html': protocol.content_html,
        'keywords': protocol.keywords,
        'message': f'Protocol "{protocol.title}" regenerated.',
    })


@protocol_bp.route('/radiology-protocols/admin/api/<int:protocol_id>/unpublish', methods=['POST'])
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


# ==================== LEGACY REDIRECTS ====================

@protocol_bp.route('/on-call-helper/admin/protocols')
@login_required
def _redirect_admin_protocols():
    return redirect('/radiology-protocols/admin', code=301)


@protocol_bp.route('/on-call-helper/protocol/<int:protocol_id>')
@login_required
def _redirect_view_protocol(protocol_id):
    return redirect(f'/radiology-protocols/view/{protocol_id}', code=301)
