"""
Case DICOM Viewer - Flask Blueprint and API routes.

OAuth, folder parse, case stack CRUD.
"""

import logging
import re
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
from case_dicom_viewer.r2_service import is_configured as r2_is_configured, upload_object as r2_upload_object, upload_objects_parallel as r2_upload_objects_parallel, test_connection as r2_test_connection
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


@case_dicom_bp.route("/api/r2-test")
@login_required
def r2_test():
    """Test R2 credentials from within the running app (admin only)."""
    if not is_admin():
        return jsonify({"error": "Admin required"}), 403
    ok, msg = r2_test_connection()
    return jsonify({"ok": ok, "message": msg})


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


def _get_token_for_stack(stack) -> str | None:
    """
    Return an access token for fetching stack URLs.
    Tries session first, then stack's stored refresh token (server-side refresh).
    This allows all viewers (including students) to get fresh URLs.
    """
    token = _get_access_token()
    if token:
        return token
    # Fallback: use stack's stored refresh token for server-side refresh
    if not stack or not stack.onedrive_share_id:
        return None
    encrypted = getattr(stack, "onedrive_refresh_token_encrypted", None)
    if not encrypted:
        return None
    plain = decrypt_refresh_token(encrypted)
    if not plain:
        return None
    app_msal = _get_msal_app()
    if not app_msal:
        return None
    try:
        result = app_msal.acquire_token_by_refresh_token(
            refresh_token=plain,
            scopes=SCOPES,
        )
        if result and "access_token" in result:
            return result["access_token"]
    except Exception as e:
        logger.debug("[CaseDicomViewer] Server-side refresh from stored token failed: %s", e)
    return None


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
        # OneDrive/SharePoint/Graph + R2 (proxy R2 to avoid CORS/503 from service worker)
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
            "r2.cloudflarestorage.com",  # Cloudflare R2 presigned URLs
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


def _safe_stack_response(plans, has_stack=True, description_html=None, error_detail=None, stacks=None):
    """Return JSON response for stack API (same shape so frontend never breaks)."""
    out = {
        "plans": plans if plans is not None else {},
        "has_stack": bool(has_stack),
        "description_html": description_html,
    }
    if error_detail:
        out["error_detail"] = error_detail
    if stacks is not None:
        out["stacks"] = stacks
    return jsonify(out)


def _build_plans_from_stack(stack):
    """
    Build plans dict (plan name -> list of URLs) for a stack.
    For R2: r2_config_json has keys -> generate presigned URLs.
    For OneDrive: get_config() has URLs (or refresh from Graph).
    """
    from case_dicom_viewer.r2_service import generate_presigned_url
    if getattr(stack, "storage_backend", None) == "r2":
        r2_config = stack.get_r2_config()
        if not r2_config:
            return {}
        plans = {}
        for plan_name, keys in r2_config.items():
            if isinstance(keys, list):
                urls = []
                for k in keys:
                    url = generate_presigned_url(k)
                    if url:
                        urls.append(url)
                if urls:
                    plans[plan_name] = urls
        return plans
    # Legacy OneDrive: use config_json URLs
    return stack.get_config()


@case_dicom_bp.route("/api/case/<int:case_id>/stack", methods=["GET"])
@login_required
def get_case_stack(case_id):
    """Return image stack config for case. Supports stack_id param for specific stack. R2 stacks get presigned URLs."""
    from models import Case
    from sqlalchemy.exc import OperationalError, ProgrammingError

    stack_id = request.args.get("stack_id", type=int)
    try:
        case = Case.query.get(case_id)
        if not case or not has_case_view_access(case):
            return jsonify({"error": "Case not found or access denied"}), 404
        try:
            stacks = CaseImageStack.query.filter_by(case_id=case_id).order_by(CaseImageStack.display_order, CaseImageStack.id).all()
        except (OperationalError, ProgrammingError) as e:
            logger.warning(
                "[CaseDicomViewer] Stack query failed (run migration?): %s",
                e,
            )
            return _safe_stack_response(
                {}, has_stack=False,
                error_detail="Database schema may be out of date. Run migrations add_case_image_stack_*.",
            )
        if not stacks:
            return _safe_stack_response({}, has_stack=False, stacks=[])

        # Resolve which stack to return (for plans/description)
        stack = None
        if stack_id:
            stack = next((s for s in stacks if s.id == stack_id), None)
        if not stack:
            stack = stacks[0]

        try:
            plans = _build_plans_from_stack(stack)
        except Exception as e:
            logger.warning("[CaseDicomViewer] build plans failed: %s", e)
            plans = {}
        # OneDrive: refresh URLs from Graph if available
        if getattr(stack, "storage_backend", None) != "r2" and stack.onedrive_share_id:
            token = _get_token_for_stack(stack)
            if token:
                try:
                    from case_dicom_viewer.onedrive_service import list_folder_contents
                    fresh = list_folder_contents(token, stack.onedrive_share_id)
                    if fresh.get("plans"):
                        plans = fresh["plans"]
                        logger.info("[CaseDicomViewer] Refreshed stack URLs from Graph for case %s", case_id)
                except Exception as e:
                    logger.debug("[CaseDicomViewer] Could not refresh stack from Graph: %s", e)

        description_html = getattr(stack, "description_html", None) or None

        # Build stacks list for multi-stack UI (id, display_order, study_label, plans = series names)
        def _plan_names(s):
            cfg = s.get_r2_config() if getattr(s, "storage_backend", None) == "r2" else s.get_config()
            return list((cfg or {}).keys()) if isinstance(cfg, dict) else []
        stacks_out = [
            {
                "id": s.id,
                "display_order": getattr(s, "display_order", 0),
                "study_label": getattr(s, "study_label", None) or f"Study {s.id}",
                "plans": _plan_names(s),
            }
            for s in stacks
        ]
        return _safe_stack_response(
            plans, has_stack=True, description_html=description_html,
            stacks=stacks_out,
        )
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
                # Store refresh token for server-side URL refresh (all viewers get fresh URLs)
                tokens = session.get("onedrive_tokens")
                if tokens and tokens.get("refresh_token"):
                    encrypted = encrypt_refresh_token(tokens["refresh_token"])
                    if encrypted:
                        stack.onedrive_refresh_token_encrypted = encrypted
                        logger.debug("[CaseDicomViewer] Stored refresh token for server-side URL refresh")
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
            # Store refresh token for server-side URL refresh (all viewers get fresh URLs)
            tokens = session.get("onedrive_tokens")
            if tokens and tokens.get("refresh_token"):
                encrypted = encrypt_refresh_token(tokens["refresh_token"])
                if encrypted:
                    stack.onedrive_refresh_token_encrypted = encrypted
                    logger.debug("[CaseDicomViewer] Stored refresh token for server-side URL refresh")
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
    """Update the rich-text description for a study. Admins, content managers, and student creators of DRAFT cases."""
    from models import Case, CaseStatus, db
    try:
        case = Case.query.get(case_id)
        if not case:
            return jsonify({"error": "Case not found"}), 404
        # Allow admin/content managers, or student creator of their own DRAFT case
        if not is_admin_or_content_manager():
            if not (current_user.is_authenticated
                    and case.created_by_user_id == current_user.id
                    and case.status == CaseStatus.DRAFT):
                return jsonify({"error": "Access denied"}), 403
        data = request.get_json() or {}
        stack_id = data.get("stack_id") or request.args.get("stack_id", type=int)
        if stack_id:
            stack = CaseImageStack.query.filter_by(case_id=case_id, id=stack_id).first()
        else:
            stack = CaseImageStack.query.filter_by(case_id=case_id).order_by(CaseImageStack.display_order, CaseImageStack.id).first()
        if not stack:
            return jsonify({"error": "No image stack linked to this case"}), 404
        description_html = data.get("description_html")
        if description_html is None:
            return jsonify({"error": "description_html required"}), 400
        stack.description_html = description_html if description_html else None
        db.session.commit()
        logger.info("[CaseDicomViewer] Description saved for case_id=%s stack_id=%s len=%s",
                     case_id, stack.id, len(description_html) if description_html else 0)
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
    """Remove image stack for case (admin). Use stack_id to delete a specific stack, or omit to delete first."""
    from models import Case, db
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403
    case = Case.query.get(case_id)
    if not case or not has_case_edit_permission(case):
        return jsonify({"error": "Case not found or access denied"}), 404
    stack_id = request.args.get("stack_id", type=int)
    if stack_id:
        stack = CaseImageStack.query.filter_by(case_id=case_id, id=stack_id).first()
    else:
        stack = CaseImageStack.query.filter_by(case_id=case_id).order_by(CaseImageStack.display_order, CaseImageStack.id).first()
    if not stack:
        remaining = CaseImageStack.query.filter_by(case_id=case_id).count()
        return jsonify({"message": "No image stack found", "has_stack": remaining > 0, "stacks_remaining": remaining})
    try:
        db.session.delete(stack)
        db.session.commit()
        remaining = CaseImageStack.query.filter_by(case_id=case_id).count()
        return jsonify({
            "message": "Study unlinked. To free storage, use Admin Dashboard → R2 Bucket Manager.",
            "has_stack": remaining > 0,
            "stacks_remaining": remaining,
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@case_dicom_bp.route("/api/case/<int:case_id>/stack/series", methods=["DELETE"])
@login_required
def remove_series_from_stack(case_id):
    """Remove a series from a study (DB only; R2 objects not deleted). If study becomes empty, delete study row."""
    from models import Case, db
    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403
    case = Case.query.get(case_id)
    if not case or not has_case_edit_permission(case):
        return jsonify({"error": "Case not found or access denied"}), 404
    stack_id = request.args.get("stack_id", type=int)
    series_name = (request.args.get("series") or request.args.get("series_name") or "").strip()
    if not stack_id or not series_name:
        return jsonify({"error": "stack_id and series (series name) required"}), 400
    stack = CaseImageStack.query.filter_by(case_id=case_id, id=stack_id).first()
    if not stack:
        return jsonify({"error": "Study not found"}), 404
    r2_config = dict(stack.get_r2_config())
    if series_name not in r2_config:
        return jsonify({"error": "Series not found in study", "series": series_name}), 404
    del r2_config[series_name]
    stack.set_r2_config(r2_config)
    if not r2_config:
        db.session.delete(stack)
    db.session.commit()
    remaining = CaseImageStack.query.filter_by(case_id=case_id).count()
    return jsonify({
        "message": "Series removed. To free storage, use Admin Dashboard → R2 Bucket Manager." if r2_config else "Study removed (was empty). To free storage, use Admin Dashboard → R2 Bucket Manager.",
        "study_deleted": not r2_config,
        "has_stack": remaining > 0,
        "stacks_remaining": remaining,
    })


# Allowed series names: letters, numbers, spaces, underscore, hyphen (e.g. T1 axial, axial contrast)
_SERIES_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9 _-]*$")


def _natural_sort_key(filename):
    """Sort key for natural ordering (slice_1, slice_2, ..., slice_10)."""
    parts = re.split(r"(\d+)", str(filename or ""))
    return [int(p) if p.isdigit() else p.lower() for p in parts if p]


def _allowed_series_name(name):
    n = (name or "").strip()
    return n and _SERIES_NAME_RE.match(n) and len(n) <= 50


def _slug(s: str, max_len: int = 50) -> str:
    """Sanitize string for R2 path: lowercase, replace spaces/special with underscore."""
    if not s:
        return ""
    s = re.sub(r"[^\w\s-]", "", str(s))
    s = re.sub(r"[\s_]+", "_", s).strip("_").lower()
    return s[:max_len] if s else ""


@case_dicom_bp.route("/api/case/<int:case_id>/stack/upload", methods=["POST"])
@login_required
def upload_case_stack_to_r2(case_id):
    """
    Direct upload of image files to R2. Creates new Study (CaseImageStack) or adds series to existing.
    Form: study_label (required for new study), stack_id (optional, add to existing study).
    Multipart form: one field per series (e.g. axial_contrast, sagittal) with multiple files.
    R2 path: cases/{case_id}_{case_slug}/studies/{study_id}_{study_slug}/series/{series_slug}/{index}.{ext}
    """
    from models import Case, CaseStatus, db

    try:
        if not r2_is_configured():
            return jsonify({"error": "R2 storage not configured. Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME in .env"}), 503

        case = Case.query.get(case_id)
        if not case:
            return jsonify({"error": "Case not found"}), 404
        # Allow admins, content managers, and student creators of DRAFT cases
        if not is_admin():
            if not (current_user.is_authenticated
                    and case.created_by_user_id == current_user.id
                    and case.status == CaseStatus.DRAFT):
                return jsonify({"error": "Admin access required"}), 403
        if not has_case_edit_permission(case):
            return jsonify({"error": "Access denied"}), 403

        study_label = (request.form.get("study_label") or "").strip()
        stack_id = request.form.get("stack_id", type=int)
        stack = None
        if stack_id:
            stack = CaseImageStack.query.filter_by(case_id=case_id, id=stack_id).first()
            if not stack:
                return jsonify({"error": "Study not found for this case"}), 404
            study_label = study_label or getattr(stack, "study_label", None) or "Study"
        elif not study_label:
            return jsonify({"error": "study_label required for new study"}), 400

        # Collect files by series from request.files
        plan_files = {}
        for key in request.files:
            if not _allowed_series_name(key):
                continue
            files = request.files.getlist(key)
            valid = [f for f in files if f and getattr(f, "filename", None)]
            if valid:
                plan_files[key] = sorted(valid, key=lambda f: _natural_sort_key(getattr(f, "filename", "") or ""))

        if not plan_files:
            return jsonify({"error": "No valid files. Add at least one series (e.g. T1 axial, axial contrast, sagittal) with one or more image files."}), 400

        case_slug = _slug(getattr(case, "case_number", None) or getattr(case, "diagnosis", "") or str(case_id))
        if not case_slug:
            case_slug = str(case_id)

        if stack:
            # Add series to existing study
            study_id = stack.id
            study_slug = _slug(getattr(stack, "study_label", None) or str(stack.id))
            if not study_slug:
                study_slug = str(stack.id)
            r2_config = dict(stack.get_r2_config())
        else:
            # New study: create row first to get id
            max_order = db.session.query(db.func.max(CaseImageStack.display_order)).filter_by(case_id=case_id).scalar()
            display_order = (max_order if max_order is not None else -1) + 1
            stack = CaseImageStack(
                case_id=case_id,
                study_label=study_label,
                storage_backend="r2",
                display_order=display_order,
                config_json="{}",
                created_by_user_id=current_user.id if current_user.is_authenticated else None,
            )
            db.session.add(stack)
            db.session.flush()  # get stack.id
            study_id = stack.id
            study_slug = _slug(study_label) or str(study_id)
            r2_config = {}

        base_prefix = f"cases/{case_id}_{case_slug}/studies/{study_id}_{study_slug}/series"

        # Process files in batches to limit peak memory usage
        UPLOAD_BATCH_SIZE = 50
        plan_key_lists = {}
        successful_keys = set()
        failed_keys = []
        for plan_name, files in plan_files.items():
            series_slug = plan_name.replace(" ", "_")
            # Determine starting index: if appending to existing series, offset by existing count
            existing_keys = r2_config.get(plan_name, [])
            start_idx = len(existing_keys) if isinstance(existing_keys, list) else 0
            plan_keys = []
            for batch_start in range(0, len(files), UPLOAD_BATCH_SIZE):
                batch = files[batch_start:batch_start + UPLOAD_BATCH_SIZE]
                batch_items = []
                for j, f in enumerate(batch):
                    idx = start_idx + batch_start + j
                    fn = getattr(f, "filename", None) or f"image_{idx}"
                    ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else "jpg"
                    if ext not in ("jpg", "jpeg", "png", "gif", "bmp", "webp", "tiff", "tif"):
                        ext = "jpg"
                    key = f"{base_prefix}/{series_slug}/{idx:04d}.{ext}"
                    content_type = f"image/{ext}" if ext in ("jpeg", "jpg", "png", "gif", "bmp", "webp", "tiff", "tif") else "application/octet-stream"
                    try:
                        body = f.read()
                    except Exception as e:
                        logger.warning("[CaseDicomViewer] Failed to read file %s: %s", fn, e)
                        continue
                    batch_items.append((key, body, content_type))
                    plan_keys.append(key)
                # Upload this batch then release memory
                if batch_items:
                    ok, fail = r2_upload_objects_parallel(batch_items)
                    successful_keys.update(ok)
                    failed_keys.extend(fail)
            plan_key_lists[plan_name] = plan_keys

        if failed_keys:
            for k in failed_keys:
                logger.warning("[CaseDicomViewer] R2 upload failed for %s", k)

        added_any = False
        for plan_name, plan_keys in plan_key_lists.items():
            keys = [k for k in plan_keys if k in successful_keys]
            if keys:
                # Merge with existing keys for this series (supports chunked uploads)
                existing = r2_config.get(plan_name, [])
                if isinstance(existing, list) and existing:
                    r2_config[plan_name] = existing + keys
                else:
                    r2_config[plan_name] = keys
                added_any = True

        if not added_any:
            db.session.rollback()
            return jsonify({
                "error": "All uploads failed. If you see Access Denied: ensure R2 API token has 'Object Read & Write', is scoped to this bucket, and bucket name matches R2_BUCKET_NAME. See case_dicom_viewer/docs/R2_SETUP.md"
            }), 500

        stack.set_r2_config(r2_config)
        db.session.commit()
        return jsonify({
            "message": "Study uploaded" if not stack_id else "Series added to study",
            "stack_id": stack.id,
            "study_label": getattr(stack, "study_label", None),
            "plans": list(r2_config.keys()),
        })
    except Exception as e:
        db.session.rollback()
        # ClientDisconnected = browser closed connection (often timeout on large uploads)
        err_class = type(e).__name__
        if err_class == "ClientDisconnected" or "ClientDisconnected" in str(type(e)):
            return jsonify({
                "error": "Upload timed out or connection closed. For 500+ images, try uploading one series at a time, or fewer files per upload."
            }), 408
        logger.exception("[CaseDicomViewer] Upload error: %s", e)
        err_msg = str(e)[:500] if str(e) else "Unknown error"
        return jsonify({"error": err_msg}), 500


# ==================== ANNOTATIONS API ====================

def _get_annotation_for_stack(case_id: int, stack_id: int | None):
    """Return annotation record for stack_id (per-study) or legacy case_id."""
    from models import CaseImageAnnotation, CaseImageStack
    if stack_id:
        ann = CaseImageAnnotation.query.filter_by(stack_id=stack_id).first()
        if ann:
            return ann
        stack = CaseImageStack.query.filter_by(case_id=case_id, id=stack_id).first()
        if not stack:
            return None
    # Fallback: legacy case-level annotation (first one)
    return CaseImageAnnotation.query.filter_by(case_id=case_id).first()


@case_dicom_bp.route("/api/case/<int:case_id>/annotations", methods=["GET"])
@login_required
def get_case_annotations(case_id):
    """Return annotations for a study. Use stack_id query param for per-study annotations."""
    from models import Case, CaseImageAnnotation, CaseImageStack
    case = Case.query.get(case_id)
    if not case or not has_case_view_access(case):
        return jsonify({"error": "Case not found or access denied"}), 404
    stack_id = request.args.get("stack_id", type=int)
    annotation = _get_annotation_for_stack(case_id, stack_id)
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
    """Save annotations for a study (admin/content manager). Use stack_id in JSON for per-study."""
    from models import Case, CaseImageAnnotation, CaseImageStack, db
    if not is_admin_or_content_manager():
        return jsonify({"error": "Admin or content manager access required"}), 403
    case = Case.query.get(case_id)
    if not case or not has_case_edit_permission(case):
        return jsonify({"error": "Case not found or access denied"}), 404
    data = request.get_json() or {}
    annotations = data.get("annotations", {})
    stack_id = None
    sid = data.get("stack_id")
    if sid is not None:
        try:
            stack_id = int(sid)
        except (TypeError, ValueError):
            pass
    if stack_id is None:
        stack_id = request.args.get("stack_id", type=int)

    if stack_id:
        stack = CaseImageStack.query.filter_by(case_id=case_id, id=stack_id).first()
        if not stack:
            return jsonify({"error": "Study not found for this case"}), 404

    annotation = _get_annotation_for_stack(case_id, stack_id)
    if annotation:
        annotation.set_annotations(annotations)
    else:
        annotation = CaseImageAnnotation(
            case_id=case_id,
            stack_id=stack_id,
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