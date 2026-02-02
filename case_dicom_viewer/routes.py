"""
Case DICOM Viewer - Flask Blueprint and API routes.

OAuth, folder parse, case stack CRUD.
"""

import logging
import secrets

import msal
from flask import Blueprint, Response, jsonify, request, redirect, session, url_for
from flask_login import login_required, current_user
import requests

from case_dicom_viewer.config import (
    get_client_id,
    get_client_secret,
    get_oauth_redirect_uri,
    SCOPES,
    AUTHORITY,
)
from models import CaseImageStack, CaseImageAnnotation
from access_control import has_case_view_access, has_case_edit_permission, is_admin, is_admin_or_content_manager
from case_dicom_viewer.token_utils import encrypt_refresh_token, decrypt_refresh_token

logger = logging.getLogger(__name__)

case_dicom_bp = Blueprint(
    "case_dicom_viewer",
    __name__,
    url_prefix="/case-dicom-viewer",
    template_folder="templates",
    static_folder="static",
    static_url_path="/case-dicom-viewer/static",
)


def _get_msal_app():
    """Build MSAL ConfidentialClientApplication."""
    client_id = get_client_id()
    client_secret = get_client_secret()
    if not client_id or not client_secret:
        return None
    return msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=AUTHORITY,
    )


@case_dicom_bp.route("/oauth/authorize")
@login_required
def oauth_authorize():
    """Redirect to Microsoft login for OneDrive OAuth."""
    app_msal = _get_msal_app()
    if not app_msal:
        return jsonify({"error": "OneDrive integration not configured (missing AZURE_CLIENT_ID or AZURE_CLIENT_SECRET)"}), 503

    state = secrets.token_urlsafe(32)
    session["onedrive_oauth_state"] = state
    session["onedrive_oauth_next"] = (
        request.args.get("next") or request.referrer or "/"
    ).strip() or "/"

    auth_url = app_msal.get_authorization_request_url(
        scopes=SCOPES,
        state=state,
        redirect_uri=get_oauth_redirect_uri(),
    )
    return redirect(auth_url)


@case_dicom_bp.route("/oauth/callback")
def oauth_callback():
    """Handle OAuth callback from Microsoft."""
    error = request.args.get("error")
    if error:
        desc = request.args.get("error_description", error)
        logger.warning("[CaseDicomViewer] OAuth error: %s", desc)
        next_url = session.pop("onedrive_oauth_next", "/")
        return redirect(f"{next_url}?onedrive_error={error}")

    state_in = request.args.get("state")
    state_stored = session.pop("onedrive_oauth_state", None)
    if not state_in or state_in != state_stored:
        logger.warning("[CaseDicomViewer] OAuth state mismatch")
        return redirect("/?onedrive_error=invalid_state")

    code = request.args.get("code")
    if not code:
        return redirect("/?onedrive_error=missing_code")

    app_msal = _get_msal_app()
    if not app_msal:
        return redirect("/?onedrive_error=config")

    result = app_msal.acquire_token_by_authorization_code(
        code=code,
        scopes=SCOPES,
        redirect_uri=get_oauth_redirect_uri(),
    )
    if "error" in result:
        logger.warning("[CaseDicomViewer] Token error: %s", result.get("error_description", result["error"]))
        next_url = session.pop("onedrive_oauth_next", "/")
        return redirect(f"{next_url}?onedrive_error=token_failed")

    session["onedrive_tokens"] = {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token"),
        "expires_in": result.get("expires_in"),
    }

    next_url = session.pop("onedrive_oauth_next", "/")
    sep = "&" if "?" in next_url else "?"
    return redirect(f"{next_url}{sep}onedrive_connected=1")


@case_dicom_bp.route("/api/status")
@login_required
def onedrive_status():
    """Return whether OneDrive is connected (has valid tokens)."""
    token = _get_access_token()
    return jsonify({"connected": bool(token)})


def _get_access_token():
    """Return valid access token, refreshing if needed. Returns None if not connected."""
    tokens = session.get("onedrive_tokens")
    if not tokens or not tokens.get("access_token"):
        return None
    app_msal = _get_msal_app()
    if not app_msal:
        return tokens.get("access_token")
    # Try refresh if we have refresh_token (MSAL will return cached if still valid)
    refresh_token = tokens.get("refresh_token")
    if refresh_token:
        result = app_msal.acquire_token_by_refresh_token(
            refresh_token=refresh_token,
            scopes=SCOPES,
        )
        if result and "access_token" in result:
            session["onedrive_tokens"] = {
                "access_token": result["access_token"],
                "refresh_token": result.get("refresh_token") or refresh_token,
                "expires_in": result.get("expires_in"),
            }
            return result["access_token"]
    return tokens.get("access_token")


@case_dicom_bp.route("/api/folder/parse", methods=["POST"])
@login_required
def folder_parse():
    """Parse OneDrive share link, return folder tree + image URLs."""
    token = _get_access_token()
    if not token:
        return jsonify({"error": "Connect OneDrive first", "code": "not_connected"}), 401

    data = request.get_json() or {}
    share_url = (data.get("share_url") or data.get("share_link") or "").strip()
    if not share_url:
        return jsonify({"error": "share_url required"}), 400

    from case_dicom_viewer.onedrive_service import parse_share_link_and_list

    result = parse_share_link_and_list(token, share_url)
    if "error" in result and result["error"]:
        return jsonify({"error": result["error"], "plans": result.get("plans", {})}), 400
    return jsonify({
        "items": result.get("items", []),
        "plans": result.get("plans", {}),
        "encoded_share_id": result.get("encoded_share_id"),
    })


def _is_allowed_proxy_url(url: str) -> bool:
    """Allow only HTTPS; OneDrive/SharePoint/Graph download hosts to reduce SSRF risk."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not url.startswith("https://"):
        return False
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        if not host:
            return False
        # OneDrive/SharePoint/Graph download and redirect hosts (downloadUrl can point to these)
        allowed = (
            "sharepoint.com",
            "1drv.ms",
            "1drv.com",
            "onedrive.com",
            "live.com",
            "microsoft.com",
            "microsoftpersonalcontent.com",
            "office.com",
            "officecdn-df.microsoft.com",
            "df.office.net",
        )
        return any(a in host for a in allowed)
    except Exception:
        return False


@case_dicom_bp.route("/api/image", methods=["GET"])
@login_required
def proxy_image():
    """
    Proxy image from OneDrive (or allowed HTTPS) to avoid CORS and expiry.
    GET /case-dicom-viewer/api/image?url=<encoded_url>
    """
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "url required"}), 400
    if not _is_allowed_proxy_url(url):
        try:
            from urllib.parse import urlparse
            host = (urlparse(url.strip()).netloc or "").lower()
            logger.warning("[CaseDicomViewer] proxy_image rejected host: %s", host or "(empty)")
        except Exception:
            pass
        return jsonify({"error": "URL not allowed for proxy"}), 403
    try:
        r = requests.get(url, timeout=30, stream=True)
        r.raise_for_status()
        headers = {}
        ct = r.headers.get("Content-Type")
        if ct:
            headers["Content-Type"] = ct
        return Response(r.iter_content(chunk_size=8192), status=r.status_code, headers=headers)
    except requests.RequestException as e:
        logger.warning("[CaseDicomViewer] proxy_image failed: %s", e)
        return jsonify({"error": "Failed to fetch image"}), 502


def _safe_stack_response(plans, has_stack=True, description_html=None, error_detail=None):
    """Return JSON response for stack API (same shape so frontend never breaks)."""
    out = {
        "plans": plans if plans is not None else {},
        "has_stack": bool(has_stack),
        "description_html": description_html,
    }
    if error_detail:
        out["error_detail"] = error_detail
    return jsonify(out)


@case_dicom_bp.route("/api/case/<int:case_id>/stack", methods=["GET"])
@login_required
def get_case_stack(case_id):
    """Return image stack config for case. Refreshes URLs from Graph when viewer has OneDrive tokens."""
    from models import Case
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        case = Case.query.get(case_id)
        if not case or not has_case_view_access(case):
            return jsonify({"error": "Case not found or access denied"}), 404
        try:
            stack = CaseImageStack.query.filter_by(case_id=case_id).first()
        except (OperationalError, ProgrammingError) as e:
            logger.warning(
                "[CaseDicomViewer] Stack query failed (run migration add_case_image_stack_description.sql?): %s",
                e,
            )
            return _safe_stack_response(
                {}, has_stack=False,
                error_detail="Database schema may be out of date. Run migration add_case_image_stack_description.sql",
            )
        if not stack:
            return _safe_stack_response({}, has_stack=False)
        try:
            plans = stack.get_config()
        except Exception as e:
            logger.warning("[CaseDicomViewer] get_config failed: %s", e)
            return _safe_stack_response(
                {}, has_stack=False,
                error_detail="Failed to load stack config: " + str(e)[:200],
            )
        token = _get_access_token()
        if token and stack.onedrive_share_id:
            try:
                from case_dicom_viewer.onedrive_service import list_folder_contents
                fresh = list_folder_contents(token, stack.onedrive_share_id)
                if fresh.get("plans"):
                    plans = fresh["plans"]
                    logger.info("[CaseDicomViewer] Refreshed stack URLs from Graph for case %s", case_id)
            except Exception as e:
                logger.debug("[CaseDicomViewer] Could not refresh stack from Graph (using stored): %s", e)
        try:
            description_html = getattr(stack, "description_html", None) or None
        except Exception:
            description_html = None
        return _safe_stack_response(plans, has_stack=True, description_html=description_html)
    except Exception as e:
        logger.exception("[CaseDicomViewer] get_case_stack failed for case_id=%s: %s", case_id, e)
        return _safe_stack_response(
            {}, has_stack=False,
            error_detail="Server error loading stack: " + str(e)[:200],
        )


@case_dicom_bp.route("/api/case/<int:case_id>/stack", methods=["POST"])
@login_required
def save_case_stack(case_id):
    """Save stack config (admin). Always returns JSON (never HTML) on error."""
    from models import Case, db
    from sqlalchemy.exc import OperationalError, ProgrammingError

    def _rollback():
        try:
            db.session.rollback()
        except Exception:
            pass

    try:
        if not is_admin():
            return jsonify({"error": "Admin access required"}), 403
        case = Case.query.get(case_id)
        if not case or not has_case_edit_permission(case):
            return jsonify({"error": "Case not found or access denied"}), 404
        data = request.get_json() or {}
        config = data.get("config") or data.get("config_json") or data.get("plans") or {}
        share_id = (data.get("onedrive_share_id") or data.get("share_id") or "").strip()
        folder_path = (data.get("onedrive_folder_path") or data.get("folder_path") or "").strip() or None
        description_html = data.get("description_html")
        stack = CaseImageStack.query.filter_by(case_id=case_id).first()
        if stack:
            if share_id:
                stack.onedrive_share_id = share_id
                stack.onedrive_folder_path = folder_path
                stack.set_config(config)
            if description_html is not None:
                try:
                    stack.description_html = description_html if description_html else None
                except Exception:
                    stack.description_html = None
        else:
            if not share_id:
                return jsonify({"error": "onedrive_share_id required"}), 400
            stack = CaseImageStack(
                case_id=case_id,
                onedrive_share_id=share_id,
                onedrive_folder_path=folder_path,
                created_by_user_id=current_user.id if current_user.is_authenticated else None,
            )
            try:
                stack.description_html = description_html if description_html else None
            except Exception:
                pass
            stack.set_config(config)
            db.session.add(stack)
        db.session.commit()
        return jsonify({
            "message": "Stack saved",
            "plans": stack.get_config(),
            "description_html": getattr(stack, "description_html", None),
        })
    except (OperationalError, ProgrammingError) as e:
        _rollback()
        err_msg = str(e)
        if "description_html" in err_msg or "column" in err_msg.lower():
            logger.warning("[CaseDicomViewer] Save stack failed (run migration add_case_image_stack_description.sql?): %s", e)
            return jsonify({
                "error": "Database schema may be out of date. Run migration: add_case_image_stack_description.sql",
            }), 500
        return jsonify({"error": err_msg[:500]}), 500
    except Exception as e:
        _rollback()
        logger.exception("[CaseDicomViewer] save_case_stack failed for case_id=%s: %s", case_id, e)
        return jsonify({"error": str(e)[:500]}), 500


@case_dicom_bp.route("/api/case/<int:case_id>/stack/description", methods=["PATCH", "PUT"])
@login_required
def update_case_stack_description(case_id):
    """Update only the rich-text description for the image stack (admin/content manager). Always returns JSON on error."""
    from models import Case, db
    try:
        if not is_admin_or_content_manager():
            return jsonify({"error": "Admin or content manager access required"}), 403
        case = Case.query.get(case_id)
        if not case or not has_case_edit_permission(case):
            return jsonify({"error": "Case not found or access denied"}), 404
        stack = CaseImageStack.query.filter_by(case_id=case_id).first()
        if not stack:
            return jsonify({"error": "No image stack linked to this case"}), 404
        data = request.get_json() or {}
        description_html = data.get("description_html")
        if description_html is None:
            return jsonify({"error": "description_html required"}), 400
        stack.description_html = description_html if description_html else None
        db.session.commit()
        return jsonify({
            "message": "Description saved",
            "description_html": getattr(stack, "description_html", None),
        })
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.exception("[CaseDicomViewer] update_case_stack_description failed for case_id=%s: %s", case_id, e)
        return jsonify({"error": str(e)[:500]}), 500


@case_dicom_bp.route("/api/case/<int:case_id>/stack", methods=["DELETE"])
@login_required
def delete_case_stack(case_id):
    """Remove image stack link for case (admin)."""
    from models import Case, db
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403
    case = Case.query.get(case_id)
    if not case or not has_case_edit_permission(case):
        return jsonify({"error": "Case not found or access denied"}), 404
    stack = CaseImageStack.query.filter_by(case_id=case_id).first()
    if not stack:
        return jsonify({"message": "No image stack linked", "has_stack": False})
    try:
        db.session.delete(stack)
        db.session.commit()
        return jsonify({"message": "Image stack removed", "has_stack": False})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ==================== ANNOTATIONS API ====================

@case_dicom_bp.route("/api/case/<int:case_id>/annotations", methods=["GET"])
@login_required
def get_case_annotations(case_id):
    """Return annotations for a case's image stack."""
    from models import Case, CaseImageAnnotation
    case = Case.query.get(case_id)
    if not case or not has_case_view_access(case):
        return jsonify({"error": "Case not found or access denied"}), 404
    
    annotation = CaseImageAnnotation.query.filter_by(case_id=case_id).first()
    if not annotation:
        return jsonify({"annotations": {}, "has_annotations": False})
    
    return jsonify({
        "annotations": annotation.get_annotations(),
        "has_annotations": True,
        "updated_at": annotation.updated_at.isoformat() if annotation.updated_at else None,
    })


@case_dicom_bp.route("/api/case/<int:case_id>/annotations", methods=["POST"])
@login_required
def save_case_annotations(case_id):
    """Save annotations for a case's image stack (admin/content manager only)."""
    from models import Case, CaseImageAnnotation, db
    if not is_admin_or_content_manager():
        return jsonify({"error": "Admin or content manager access required"}), 403
    
    case = Case.query.get(case_id)
    if not case or not has_case_edit_permission(case):
        return jsonify({"error": "Case not found or access denied"}), 404
    
    data = request.get_json() or {}
    annotations = data.get("annotations", {})
    
    annotation = CaseImageAnnotation.query.filter_by(case_id=case_id).first()
    if annotation:
        annotation.set_annotations(annotations)
    else:
        annotation = CaseImageAnnotation(
            case_id=case_id,
            created_by_user_id=current_user.id if current_user.is_authenticated else None,
        )
        annotation.set_annotations(annotations)
        db.session.add(annotation)
    
    try:
        db.session.commit()
        logger.info("[CaseDicomViewer] Saved annotations for case %s by user %s", case_id, current_user.id)
        return jsonify({
            "message": "Annotations saved",
            "has_annotations": True,
            "updated_at": annotation.updated_at.isoformat() if annotation.updated_at else None,
        })
    except Exception as e:
        db.session.rollback()
        logger.error("[CaseDicomViewer] Failed to save annotations: %s", e)
        return jsonify({"error": str(e)}), 500


@case_dicom_bp.route("/api/case/<int:case_id>/annotations", methods=["DELETE"])
@login_required
def delete_case_annotations(case_id):
    """Delete all annotations for a case (admin only)."""
    from models import Case, CaseImageAnnotation, db
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403
    
    case = Case.query.get(case_id)
    if not case or not has_case_edit_permission(case):
        return jsonify({"error": "Case not found or access denied"}), 404
    
    annotation = CaseImageAnnotation.query.filter_by(case_id=case_id).first()
    if not annotation:
        return jsonify({"message": "No annotations found", "has_annotations": False})
    
    try:
        db.session.delete(annotation)
        db.session.commit()
        logger.info("[CaseDicomViewer] Deleted annotations for case %s by user %s", case_id, current_user.id)
        return jsonify({"message": "Annotations deleted", "has_annotations": False})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500