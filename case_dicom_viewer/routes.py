"""
Case DICOM Viewer - Flask Blueprint and API routes.

OAuth, folder parse, case stack CRUD.
"""

from flask import Blueprint, jsonify, request, redirect, url_for
from flask_login import login_required, current_user

from models import CaseImageStack
from access_control import has_case_view_access, has_case_edit_permission, is_admin

case_dicom_bp = Blueprint(
    "case_dicom_viewer",
    __name__,
    url_prefix="/case-dicom-viewer",
    template_folder="templates",
    static_folder="static",
    static_url_path="/case-dicom-viewer/static",
)


@case_dicom_bp.route("/oauth/authorize")
@login_required
def oauth_authorize():
    """Redirect to Microsoft login for OneDrive OAuth."""
    # TODO: Build authorization URL, redirect
    return jsonify({"error": "Not implemented yet"}), 501


@case_dicom_bp.route("/oauth/callback")
def oauth_callback():
    """Handle OAuth callback from Microsoft."""
    # TODO: Exchange code for tokens, store in session
    return jsonify({"error": "Not implemented yet"}), 501


@case_dicom_bp.route("/api/folder/parse", methods=["POST"])
@login_required
def folder_parse():
    """Parse OneDrive share link, return folder tree + image URLs."""
    data = request.get_json() or {}
    share_url = (data.get("share_url") or data.get("share_link") or "").strip()
    if not share_url:
        return jsonify({"error": "share_url required"}), 400
    # TODO: Call onedrive_service.parse_share_link, list_folder_contents
    return jsonify({"error": "Not implemented yet", "plans": []}), 501


@case_dicom_bp.route("/api/case/<int:case_id>/stack", methods=["GET"])
@login_required
def get_case_stack(case_id):
    """Return image stack config for case (student view)."""
    from models import Case
    case = Case.query.get(case_id)
    if not case or not has_case_view_access(case):
        return jsonify({"error": "Case not found or access denied"}), 404
    stack = CaseImageStack.query.filter_by(case_id=case_id).first()
    if not stack:
        return jsonify({"plans": {}, "has_stack": False})
    return jsonify({"plans": stack.get_config(), "has_stack": True})


@case_dicom_bp.route("/api/case/<int:case_id>/stack", methods=["POST"])
@login_required
def save_case_stack(case_id):
    """Save stack config (admin)."""
    from models import Case, db
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403
    case = Case.query.get(case_id)
    if not case or not has_case_edit_permission(case):
        return jsonify({"error": "Case not found or access denied"}), 404
    data = request.get_json() or {}
    config = data.get("config") or data.get("config_json") or data.get("plans") or {}
    share_id = (data.get("onedrive_share_id") or data.get("share_id") or "").strip()
    folder_path = (data.get("onedrive_folder_path") or data.get("folder_path") or "").strip() or None
    if not share_id:
        return jsonify({"error": "onedrive_share_id required"}), 400
    stack = CaseImageStack.query.filter_by(case_id=case_id).first()
    if stack:
        stack.onedrive_share_id = share_id
        stack.onedrive_folder_path = folder_path
        stack.set_config(config)
    else:
        stack = CaseImageStack(
            case_id=case_id,
            onedrive_share_id=share_id,
            onedrive_folder_path=folder_path,
            created_by_user_id=current_user.id if current_user.is_authenticated else None,
        )
        stack.set_config(config)
        db.session.add(stack)
    try:
        db.session.commit()
        return jsonify({"message": "Stack saved", "plans": stack.get_config()})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
