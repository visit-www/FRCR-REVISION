"""
Public Routes

Flask blueprint for publicly accessible content previews.
These routes do NOT require authentication and are designed for SEO crawling
and social sharing.

URL structure:
  /case-library             — public case browse page
  /case-library/<int:id>    — public case preview page
"""

from flask import Blueprint, render_template
from models import db, Case, CaseImage, CaseStatus

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

    # Truncate discussion server-side for security
    discussion_teaser = ''
    if case.discussion:
        discussion_teaser = case.discussion[:150]

    # Count questions for gated display
    question_count = len(case.question_items) if case.question_items else 0

    return render_template('public_case_preview.html',
                           case=case,
                           images=images,
                           discussion_teaser=discussion_teaser,
                           question_count=question_count)


@public_bp.route('/contrast-reaction-card')
def contrast_reaction_card():
    """Public contrast reaction card — ACR-aligned quick reference."""
    return render_template('contrast_reaction_card.html')
