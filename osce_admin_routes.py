"""
OSCE Guide Admin Routes

Admin CRUD for OSCE cases: list, create (AI), edit (TinyMCE), delete,
image upload (Cloudinary), link to Case, and static content editor
for quick reference / pattern index / exam technique.
"""

import json
import os
import re
import logging
from datetime import datetime

import cloudinary.uploader
from flask import Blueprint, request, jsonify, render_template
from flask_login import current_user

from models import db, OsceCase, OsceCaseImage, Case, CaseStatus
from access_control import require_admin

logger = logging.getLogger(__name__)

osce_admin_bp = Blueprint('osce_admin', __name__, url_prefix='/api/admin/osce')

_DATA_DIR = os.path.join(os.path.dirname(__file__), 'static', 'data')
_GUIDE_JSON_PATH = os.path.join(_DATA_DIR, 'osce_guide.json')



# =========================================================================
# ADMIN PAGE (HTML)
# =========================================================================

@osce_admin_bp.route('', methods=['GET'])
@require_admin
def osce_admin_page():
    """Admin page for managing OSCE cases + static content."""
    cases = OsceCase.query.order_by(OsceCase.modality, OsceCase.sort_order, OsceCase.code).all()
    # Published case list for "Dive Deeper" linking
    linkable_cases = Case.query.filter_by(status=CaseStatus.PUBLISHED).order_by(Case.diagnosis).all()
    return render_template('admin_osce.html', osce_cases=cases, linkable_cases=linkable_cases)


@osce_admin_bp.route('/edit/<int:case_id>', methods=['GET'])
@require_admin
def edit_osce_case_page(case_id):
    """Dedicated full-page editor for an OSCE case (TinyMCE needs visible DOM)."""
    case = OsceCase.query.get_or_404(case_id)
    linkable_cases = Case.query.filter_by(status=CaseStatus.PUBLISHED).order_by(Case.diagnosis).all()
    linked_ids = case.get_linked_case_ids()
    # Pre-format reference links for textarea
    refs = case.get_reference_links()
    ref_lines = '\n'.join(
        ' | '.join(filter(None, [r.get('url', ''), r.get('label', ''), r.get('source', '')]))
        for r in refs
    ) if refs else ''
    return render_template('admin_osce_edit.html',
                           osce_case=case,
                           linkable_cases=linkable_cases,
                           linked_case_ids=linked_ids,
                           ref_links_text=ref_lines)


# =========================================================================
# CASE CRUD (JSON API)
# =========================================================================

@osce_admin_bp.route('/cases', methods=['GET'])
@require_admin
def list_osce_cases():
    """List all OSCE cases."""
    cases = OsceCase.query.order_by(OsceCase.modality, OsceCase.sort_order).all()
    return jsonify([{
        'id': c.id, 'code': c.code, 'diagnosis': c.diagnosis,
        'modality': c.modality, 'category': c.category,
        'difficulty': c.difficulty, 'is_published': c.is_published,
        'linked_case_ids': c.get_linked_case_ids(),
        'image_count': c.images.count(),
    } for c in cases])


@osce_admin_bp.route('/cases', methods=['POST'])
@require_admin
def create_osce_case():
    """Create a new OSCE case (manually or from AI generation)."""

    data = request.get_json() or {}
    code = (data.get('code') or '').strip()
    diagnosis = (data.get('diagnosis') or '').strip()
    modality = (data.get('modality') or '').strip()
    category = (data.get('category') or '').strip()

    if not code or not modality or not category:
        return jsonify({'error': 'Code, modality, and category are required'}), 400
    if category.lower() != 'normal' and not diagnosis:
        return jsonify({'error': 'Diagnosis is required for pathological cases'}), 400

    # Check unique code
    if OsceCase.query.filter_by(code=code).first():
        return jsonify({'error': f'Code {code} already exists'}), 400

    case = OsceCase(
        code=code,
        diagnosis=diagnosis or f'Normal {modality}',
        modality=modality,
        category=category.lower(),
        difficulty=data.get('difficulty', 'Moderate'),
        osce_data=data.get('osce_data'),
        content_html=data.get('content_html'),
        linked_case_id=data.get('linked_case_ids', [None])[0] if data.get('linked_case_ids') else data.get('linked_case_id'),
        linked_case_ids=json.dumps(data.get('linked_case_ids', [])) if data.get('linked_case_ids') else None,
        reference_links=json.dumps(data.get('reference_links', [])),
        is_published=data.get('is_published', False),
        sort_order=data.get('sort_order', 0),
    )
    db.session.add(case)
    db.session.commit()

    return jsonify({'success': True, 'id': case.id, 'code': case.code}), 201


@osce_admin_bp.route('/cases/<int:case_id>', methods=['GET'])
@require_admin
def get_osce_case(case_id):
    """Get a single OSCE case with all data."""

    case = OsceCase.query.get_or_404(case_id)
    images = [{
        'id': img.id,
        'image_url': img.image_url,
        'image_thumbnail_url': img.image_thumbnail_url,
        'image_description': img.image_description,
        'attribution': img.attribution,
        'source_url': img.source_url,
        'sort_order': img.sort_order,
        'is_annotated': img.is_annotated or False,
        'paired_image_id': img.paired_image_id,
    } for img in case.images.order_by(OsceCaseImage.sort_order).all()]

    return jsonify({
        'id': case.id, 'code': case.code, 'diagnosis': case.diagnosis,
        'modality': case.modality, 'category': case.category,
        'difficulty': case.difficulty,
        'osce_data': case.osce_data,
        'content_html': case.content_html,
        'linked_case_id': case.linked_case_id,
        'linked_case_ids': case.get_linked_case_ids(),
        'reference_links': case.get_reference_links(),
        'is_published': case.is_published,
        'sort_order': case.sort_order,
        'images': images,
    })


@osce_admin_bp.route('/cases/<int:case_id>', methods=['PUT'])
@require_admin
def update_osce_case(case_id):
    """Update an OSCE case — fields, content, links."""

    case = OsceCase.query.get_or_404(case_id)
    data = request.get_json() or {}

    if 'diagnosis' in data:
        case.diagnosis = data['diagnosis']
    if 'modality' in data:
        case.modality = data['modality']
    if 'category' in data:
        case.category = data['category'].lower()
    if 'difficulty' in data:
        case.difficulty = data['difficulty']
    if 'content_html' in data:
        case.content_html = data['content_html']
    if 'osce_data' in data:
        case.osce_data = data['osce_data']
    if 'linked_case_ids' in data:
        case.set_linked_case_ids(data['linked_case_ids'] or [])
    elif 'linked_case_id' in data:
        case.linked_case_id = data['linked_case_id'] or None
    if 'reference_links' in data:
        case.set_reference_links(data['reference_links'])
    if 'is_published' in data:
        case.is_published = bool(data['is_published'])
    if 'sort_order' in data:
        case.sort_order = int(data['sort_order'])

    case.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})


@osce_admin_bp.route('/cases/<int:case_id>', methods=['DELETE'])
@require_admin
def delete_osce_case(case_id):
    """Delete an OSCE case and its images."""

    case = OsceCase.query.get_or_404(case_id)

    # Delete Cloudinary images
    for img in case.images.all():
        if img.image_public_id:
            try:
                cloudinary.uploader.destroy(img.image_public_id)
            except Exception:
                pass

    db.session.delete(case)
    db.session.commit()
    return jsonify({'success': True})


# =========================================================================
# AI GENERATION (calls ai_osce.py, saves to case)
# =========================================================================

@osce_admin_bp.route('/cases/<int:case_id>/generate', methods=['POST'])
@require_admin
def generate_for_case(case_id):
    """Generate AI content for an existing OSCE case.
    Supports multipart/form-data for PDF uploads + reference URLs + instructions."""

    case = OsceCase.query.get_or_404(case_id)

    # Parse input (supports both JSON and multipart form data)
    if request.content_type and 'multipart/form-data' in request.content_type:
        instructions = (request.form.get('instructions') or '').strip()
        reference_urls = request.form.getlist('reference_url')
        pdf_files = request.files.getlist('pdf')
    else:
        data = request.get_json() or {}
        instructions = (data.get('instructions') or '').strip()
        reference_urls = data.get('reference_urls') or []
        pdf_files = []

    # Build additional context from references + PDFs + instructions
    from reporting_routes import _build_generation_context
    additional_context, _ = _build_generation_context(instructions, reference_urls, pdf_files)

    from ai_osce import AiOsceError, generate_osce_case, render_osce_html

    context = {
        'diagnosis': case.diagnosis,
        'modality': case.modality,
        'category': case.category,
        'additional_context': additional_context,
    }

    try:
        result = generate_osce_case(context)
    except AiOsceError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'error': f'Generation failed: {exc}'}), 500

    output = result.get('output', {})
    html = render_osce_html(output)

    case.osce_data = json.dumps(output)
    case.content_html = html
    case.updated_at = datetime.utcnow()

    # Track AI usage
    try:
        from ai_cost_tracker import track_ai_call
        _usage = result.get('usage', {})
        track_ai_call(current_user.id, 'generate_osce_case',
                      model=result.get('model', ''),
                      input_tokens=_usage.get('input_tokens', 0),
                      output_tokens=_usage.get('output_tokens', 0),
                      input_summary=f"osce: {case.code} {case.diagnosis}")
    except Exception:
        pass

    db.session.commit()

    return jsonify({
        'success': True,
        'content_html': html,
        'osce_data': output,
        'model': result.get('model', ''),
        'usage': result.get('usage', {}),
    })


# =========================================================================
# IMAGE MANAGEMENT
# =========================================================================

@osce_admin_bp.route('/cases/<int:case_id>/images', methods=['POST'])
@require_admin
def upload_osce_image(case_id):
    """Upload image(s) for an OSCE case via Cloudinary."""

    case = OsceCase.query.get_or_404(case_id)

    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    file = request.files['image']
    if not file or not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    description = (request.form.get('description') or '').strip()
    attribution = (request.form.get('attribution') or '').strip()
    source_url = (request.form.get('source_url') or '').strip()
    is_annotated = request.form.get('is_annotated', '').lower() in ('true', '1', 'on')
    paired_image_id = request.form.get('paired_image_id', '').strip()
    paired_image_id = int(paired_image_id) if paired_image_id else None

    try:
        # Strip EXIF for privacy
        from app import _strip_exif
        file = _strip_exif(file)

        upload_result = cloudinary.uploader.upload(
            file,
            folder='frcr_revision/osce_cases',
            resource_type='image',
            transformation=[{'quality': 'auto', 'fetch_format': 'auto'}]
        )

        thumbnail_url = cloudinary.CloudinaryImage(upload_result['public_id']).build_url(
            width=300, height=200, crop='fill', quality='auto'
        )

        img = OsceCaseImage(
            osce_case_id=case.id,
            image_url=upload_result['secure_url'],
            image_public_id=upload_result['public_id'],
            image_thumbnail_url=thumbnail_url,
            image_description=description,
            attribution=attribution,
            source_url=source_url or None,
            is_annotated=is_annotated,
            paired_image_id=paired_image_id,
            sort_order=case.images.count(),
        )
        db.session.add(img)
        db.session.commit()

        return jsonify({
            'success': True,
            'image': {
                'id': img.id,
                'image_url': img.image_url,
                'image_thumbnail_url': img.image_thumbnail_url,
                'image_description': img.image_description,
                'attribution': img.attribution,
            }
        })
    except Exception as exc:
        return jsonify({'error': f'Upload failed: {exc}'}), 500


@osce_admin_bp.route('/images/<int:image_id>', methods=['PUT'])
@require_admin
def update_osce_image(image_id):
    """Update image metadata (description, attribution)."""

    img = OsceCaseImage.query.get_or_404(image_id)
    data = request.get_json() or {}

    if 'image_description' in data:
        img.image_description = data['image_description']
    if 'attribution' in data:
        img.attribution = data['attribution']
    if 'source_url' in data:
        img.source_url = data['source_url']
    if 'sort_order' in data:
        img.sort_order = int(data['sort_order'])
    if 'is_annotated' in data:
        img.is_annotated = bool(data['is_annotated'])
    if 'paired_image_id' in data:
        img.paired_image_id = data['paired_image_id'] or None

    db.session.commit()
    return jsonify({'success': True})


@osce_admin_bp.route('/images/<int:image_id>', methods=['DELETE'])
@require_admin
def delete_osce_image(image_id):
    """Delete an OSCE case image."""

    img = OsceCaseImage.query.get_or_404(image_id)

    if img.image_public_id:
        try:
            cloudinary.uploader.destroy(img.image_public_id)
        except Exception:
            pass

    db.session.delete(img)
    db.session.commit()
    return jsonify({'success': True})


# =========================================================================
# STATIC CONTENT EDITOR (quick reference, pattern index, exam technique)
# =========================================================================

def _load_guide_json():
    """Load the osce_guide.json static data."""
    if os.path.exists(_GUIDE_JSON_PATH):
        with open(_GUIDE_JSON_PATH, 'r') as f:
            return json.load(f)
    return {}


def _save_guide_json(data):
    """Save osce_guide.json atomically."""
    tmp = _GUIDE_JSON_PATH + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, _GUIDE_JSON_PATH)


@osce_admin_bp.route('/static-content', methods=['GET'])
@require_admin
def get_static_content():
    """Get the static content sections (quick reference, patterns, technique)."""

    data = _load_guide_json()
    return jsonify({
        'quickReference': data.get('quickReference', {}),
        'patternIndex': data.get('patternIndex', {}),
        'examTechnique': data.get('examTechnique', {}),
        'modalities': data.get('modalities', {}),
    })


@osce_admin_bp.route('/static-content/<section>', methods=['PUT'])
@require_admin
def update_static_section(section):
    """Update a specific static content section."""


    allowed = ['quickReference', 'patternIndex', 'examTechnique', 'modalities']
    if section not in allowed:
        return jsonify({'error': f'Invalid section. Allowed: {", ".join(allowed)}'}), 400

    data = _load_guide_json()
    new_content = request.get_json()
    if new_content is None:
        return jsonify({'error': 'No content provided'}), 400

    data[section] = new_content
    data.setdefault('_meta', {})['lastUpdated'] = datetime.utcnow().strftime('%Y-%m-%d')

    _save_guide_json(data)
    return jsonify({'success': True, 'section': section})
