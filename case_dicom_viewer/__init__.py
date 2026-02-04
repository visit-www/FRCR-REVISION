"""
Case DICOM Viewer Module

Standalone, exportable module for OneDrive-linked image stacks and DICOM-like
viewing with Cornerstone3D. Admin adds stacks in edit_case; students view in view_case.

Usage:
    from case_dicom_viewer import init_app, get_blueprint

    init_app(app)
    app.register_blueprint(get_blueprint())
"""

import os

__version__ = "0.1.0"

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_FOLDER = os.path.join(MODULE_DIR, "templates")
STATIC_FOLDER = os.path.join(MODULE_DIR, "static")


def init_app(app, db=None):
    """Initialize the Case DICOM Viewer module with a Flask application."""
    app.extensions["case_dicom_viewer"] = {"db": db}
    if TEMPLATE_FOLDER not in app.jinja_loader.searchpath:
        app.jinja_loader.searchpath.append(TEMPLATE_FOLDER)
    from .r2_service import is_configured
    if is_configured():
        print("[R2] Cloudflare R2 storage configured (bucket from .env)")
    else:
        print("[R2] R2 not configured - add R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME to .env")
    return None


def get_blueprint():
    """Get the Flask blueprint for Case DICOM Viewer routes."""
    from .routes import case_dicom_bp
    return case_dicom_bp
