"""
Public Routes

Flask blueprint for publicly accessible content previews.
These routes do NOT require authentication and are designed for SEO crawling
and social sharing.

URL structure:
  /case-library             — public case browse page
  /case-library/<int:id>    — public case preview page
"""

import json
import os
from flask import Blueprint, render_template

from models import db, Case, CaseImage, CaseStatus

# ── Load protocol reference JSON at import time (static data, read once) ──
_DATA_DIR = os.path.join(os.path.dirname(__file__), 'static', 'data')

def _load_json(filename):
    path = os.path.join(_DATA_DIR, filename)
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {}

CT_PROTOCOLS = _load_json('ct_protocols.json')
MRI_PROTOCOLS = _load_json('mri_protocols.json')
# OSCE guide data loaded per-request (admin can edit via static content editor)
_OSCE_GUIDE_JSON = os.path.join(_DATA_DIR, 'osce_guide.json')
_osce_cache = {'data': None, 'mtime': 0}

def _load_osce_guide():
    """Load osce_guide.json with file-mtime caching — refreshes when admin edits the file."""
    try:
        mt = os.path.getmtime(_OSCE_GUIDE_JSON)
    except OSError:
        return {}
    if _osce_cache['data'] is not None and mt == _osce_cache['mtime']:
        return _osce_cache['data']
    with open(_OSCE_GUIDE_JSON, 'r') as f:
        _osce_cache['data'] = json.load(f)
    _osce_cache['mtime'] = mt
    return _osce_cache['data']

public_bp = Blueprint('public', __name__)


@public_bp.route('/case-library')
def case_library():
    """Public case library browse page — published cases only."""
    cases = Case.query.filter_by(
        status=CaseStatus.PUBLISHED
    ).order_by(Case.created_at.desc()).all()

    # Attach first thumbnail to each case for card display
    for case in cases:
        first_img = CaseImage.query.filter_by(case_id=case.id).first()
        case._thumb = first_img.image_thumbnail_url if first_img and first_img.image_thumbnail_url else None

    return render_template('public_case_library.html', cases=cases)


@public_bp.route('/case-library/<int:case_id>')
def case_preview(case_id):
    """Public case preview — published cases only, gated content."""
    case = Case.query.filter_by(
        id=case_id, status=CaseStatus.PUBLISHED
    ).first_or_404()

    # Fetch images (limit to 3 for preview)
    images = CaseImage.query.filter_by(
        case_id=case.id
    ).limit(3).all()

    # Full discussion — educational content is free, AI features are paid
    discussion_html = case.discussion or ''

    # Questions for display
    question_count = len(case.question_items) if case.question_items else 0

    return render_template('public_case_preview.html',
                           case=case,
                           images=images,
                           discussion_html=discussion_html,
                           question_count=question_count)


@public_bp.route('/contrast-reaction-card')
def contrast_reaction_card():
    """Public contrast reaction card — ACR-aligned quick reference."""
    return render_template('contrast_reaction_card.html')


@public_bp.route('/vetting-essentials')
def vetting_essentials():
    """Public vetting essentials card — CT contrast phases, timing, oral/rectal, liver supply."""
    return render_template('vetting_essentials.html')


@public_bp.route('/paediatric-ct-protocols')
def paediatric_ct_protocols():
    """Public interactive paediatric CT protocol reference page."""
    return render_template('paediatric_ct_protocols.html')


@public_bp.route('/osce-radiology-guide')
def osce_radiology_guide():
    """Public OSCE radiology guide — interactive cases for 3rd year medical students."""
    from models import OsceCase, OsceCaseImage
    # Published cases from DB
    db_cases = OsceCase.query.filter_by(is_published=True)\
        .order_by(OsceCase.modality, OsceCase.sort_order, OsceCase.code).all()

    cases_json = []
    for c in db_cases:
        images = [{
            'url': img.image_url,
            'thumbnail': img.image_thumbnail_url,
            'description': img.image_description,
            'attribution': img.attribution,
            'source_url': img.source_url,
            'is_annotated': img.is_annotated or False,
            'paired_image_id': img.paired_image_id,
        } for img in c.images.order_by(OsceCaseImage.sort_order).all()]

        # Try to use structured osce_data JSON, fall back to content_html
        osce_data = c.get_osce_data()
        cases_json.append({
            'id': c.code,
            'db_id': c.id,
            'diagnosis': c.diagnosis,
            'modality': osce_data.get('modality', c.modality).lower().replace(' x-ray', '').replace('x-ray', '').replace(' ', '_'),
            'category': c.category,
            'difficulty': c.difficulty or 'Moderate',
            'views': osce_data.get('views', {}),
            'tags': osce_data.get('tags', {}),
            'osce': osce_data.get('osce', {}),
            'explanation': osce_data.get('explanation', {}),
            'teaching_points': osce_data.get('teaching_points', []),
            'images': images,
            'content_html': c.content_html or '',
            'linked_case_id': c.linked_case_id,
            'reference_links': c.get_reference_links(),
        })

    # Merge: DB cases override prototype cases, static data stays
    guide_data = dict(_load_osce_guide())
    if cases_json:
        guide_data['prototypeCases'] = cases_json
    # If no DB cases yet, keep the prototype cases from JSON for demo

    return render_template('osce_radiology_guide.html',
                           osce_data=guide_data)


@public_bp.route('/imaging-protocols-reference')
def imaging_protocols_reference():
    """Public imaging protocols reference — CT + MRI master protocol library."""
    # Build category → protocols map for CT (flat structure)
    ct_protocols = CT_PROTOCOLS.get('protocols', {})
    # Build category → protocols map for MRI (nested by category)
    mri_categories = {}
    for key, val in MRI_PROTOCOLS.items():
        if key == '_meta' or not isinstance(val, dict):
            continue
        mri_categories[key] = val

    return render_template('imaging_protocols_reference.html',
                           ct_protocols=ct_protocols,
                           mri_categories=mri_categories,
                           ct_meta=CT_PROTOCOLS.get('_meta', {}),
                           mri_meta=MRI_PROTOCOLS.get('_meta', {}))
