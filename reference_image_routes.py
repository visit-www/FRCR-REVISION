"""
Reference Image Curation Routes

Admin-side search and curation of CC-licensed reference images for cases.
Images: CT/MRI, anatomy diagrams, concept diagrams.
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from access_control import require_admin, has_case_edit_permission, has_case_view_access
from models import db, Case, CaseReferenceImage
from google_search_service import search_reference_images, build_manual_search_url
from google_search_service import IMAGE_TYPE_CT_MRI, IMAGE_TYPE_ANATOMY_DIAGRAM, IMAGE_TYPE_CONCEPT_DIAGRAM

reference_image_bp = Blueprint("reference_images", __name__, url_prefix="/api/reference-images")


def _get_case_for_edit(case_id):
    """Return case if current user can edit it, else None."""
    case = Case.query.get(case_id)
    if not case:
        return None
    if has_case_edit_permission(case):
        return case
    return None


def _get_case_for_view(case_id):
    """Return case if current user can view it, else None."""
    case = Case.query.get(case_id)
    if not case:
        return None
    if has_case_edit_permission(case) or has_case_view_access(case):
        return case
    return None


@reference_image_bp.route("/search", methods=["GET"])
@login_required
@require_admin
def search():
    """
    Search for CC-licensed reference images.
    Query params: diagnosis (required), body_part, modality, image_type
    """
    diagnosis = request.args.get("diagnosis", "").strip()
    if not diagnosis:
        return jsonify({"error": "diagnosis is required", "results": []}), 400

    body_part = request.args.get("body_part", "").strip()
    modality = request.args.get("modality", "").strip()  # CT, MRI, or empty
    image_type = request.args.get("image_type", "").strip()
    max_per_type = min(int(request.args.get("max_per_type", 5)), 10)

    image_types = None
    if image_type in (IMAGE_TYPE_CT_MRI, IMAGE_TYPE_ANATOMY_DIAGRAM, IMAGE_TYPE_CONCEPT_DIAGRAM):
        image_types = [image_type]

    try:
        results = search_reference_images(
            diagnosis=diagnosis,
            body_part=body_part,
            modality=modality,
            image_types=image_types,
            max_per_type=max_per_type,
        )
        # Add placeholder attribution (Google CSE filters for CC; actual attribution from source)
        for r in results:
            r.setdefault("attribution", f"Source: {r.get('displayLink', r.get('source_domain', 'unknown'))}")
            r.setdefault("license", "CC (filtered by search)")
        if not results:
            manual_url = build_manual_search_url(
                diagnosis=diagnosis,
                body_part=body_part,
                modality=modality,
                image_type=image_type if image_type else None,
            )
            return jsonify({
                "results": [],
                "diagnosis": diagnosis,
                "hint": "API responded but returned 0 images. Ensure your Programmable Search Engine has Image search ON and is set to search the entire web.",
                "manual_search_url": manual_url,
            })
        return jsonify({"results": results, "diagnosis": diagnosis})
    except Exception as e:
        # Fallback: direct Google Images URL with same parameters (CC filter)
        manual_url = build_manual_search_url(
            diagnosis=diagnosis,
            body_part=body_part,
            modality=modality,
            image_type=image_type if image_type else None,
        )
        return jsonify({
            "error": str(e),
            "results": [],
            "manual_search_url": manual_url,
        })


@reference_image_bp.route("/case/<int:case_id>", methods=["GET"])
@login_required
def get_case_reference_images(case_id):
    """Get curated reference images for a case (students and admins)."""
    case = _get_case_for_view(case_id)
    if not case:
        return jsonify({"error": "Case not found or access denied"}), 404

    images = (
        CaseReferenceImage.query.filter_by(case_id=case_id)
        .order_by(CaseReferenceImage.display_order, CaseReferenceImage.image_type, CaseReferenceImage.id)
        .all()
    )
    return jsonify([img.to_dict() for img in images])


@reference_image_bp.route("/case/<int:case_id>", methods=["POST"])
@login_required
@require_admin
def add_case_reference_image(case_id):
    """
    Add a reference image to a case.
    Body: { source_url, source_domain, thumbnail_url, image_type, modality?, license, attribution, ai_description?, admin_note? }
    """
    case = _get_case_for_edit(case_id)
    if not case:
        return jsonify({"error": "Case not found or access denied"}), 404

    data = request.get_json() or {}
    source_url = (data.get("source_url") or data.get("link") or "").strip()
    license_val = (data.get("license") or "CC BY 4.0").strip()
    attribution = (data.get("attribution") or "").strip()

    if not source_url:
        return jsonify({"error": "source_url is required"}), 400
    if not attribution:
        return jsonify({"error": "attribution is required for CC compliance"}), 400

    # Reject if license not CC/public domain
    license_upper = license_val.upper()
    if "CC" not in license_upper and "PUBLIC DOMAIN" not in license_upper and "CC0" not in license_upper:
        return jsonify({"error": "Only Creative Commons or public domain images are allowed"}), 400

    source_domain = (data.get("source_domain") or "").strip()
    if not source_domain:
        from urllib.parse import urlparse
        try:
            parsed = urlparse(source_url)
            source_domain = parsed.netloc or "unknown"
            if source_domain.startswith("www."):
                source_domain = source_domain[4:]
        except Exception:
            source_domain = "unknown"

    image_type = (data.get("image_type") or IMAGE_TYPE_CT_MRI).strip()
    if image_type not in (IMAGE_TYPE_CT_MRI, IMAGE_TYPE_ANATOMY_DIAGRAM, IMAGE_TYPE_CONCEPT_DIAGRAM):
        image_type = IMAGE_TYPE_CT_MRI

    ref_img = CaseReferenceImage(
        case_id=case_id,
        source_url=source_url[:1000],
        source_domain=source_domain[:255],
        thumbnail_url=(data.get("thumbnail_url") or "").strip()[:500] or None,
        image_type=image_type,
        modality=(data.get("modality") or "").strip()[:50] or None,
        ai_description=(data.get("ai_description") or "").strip() or None,
        ai_relevance_score=data.get("ai_relevance_score"),
        admin_note=(data.get("admin_note") or "").strip() or None,
        license=license_val[:100],
        attribution=attribution[:500],
        added_by_user_id=current_user.id,
    )
    db.session.add(ref_img)
    try:
        db.session.commit()
        return jsonify(ref_img.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@reference_image_bp.route("/case/<int:case_id>/<int:image_id>", methods=["DELETE"])
@login_required
@require_admin
def delete_case_reference_image(case_id, image_id):
    """Remove a reference image from a case."""
    case = _get_case_for_edit(case_id)
    if not case:
        return jsonify({"error": "Case not found or access denied"}), 404

    ref_img = CaseReferenceImage.query.filter_by(id=image_id, case_id=case_id).first()
    if not ref_img:
        return jsonify({"error": "Reference image not found"}), 404

    db.session.delete(ref_img)
    try:
        db.session.commit()
        return jsonify({"message": "Deleted"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@reference_image_bp.route("/case/<int:case_id>/reorder", methods=["PUT"])
@login_required
@require_admin
def reorder_case_reference_images(case_id):
    """Update display_order for reference images. Body: { order: [id1, id2, ...] }"""
    case = _get_case_for_edit(case_id)
    if not case:
        return jsonify({"error": "Case not found or access denied"}), 404

    data = request.get_json() or {}
    order = data.get("order", [])
    if not isinstance(order, list):
        return jsonify({"error": "order must be a list of image ids"}), 400

    for idx, img_id in enumerate(order):
        ref_img = CaseReferenceImage.query.filter_by(id=img_id, case_id=case_id).first()
        if ref_img:
            ref_img.display_order = idx
    try:
        db.session.commit()
        return jsonify({"message": "Reordered"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
