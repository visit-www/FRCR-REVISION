"""
AJCC TNM Staging Module

A self-contained, reusable module for AJCC TNM cancer staging data extraction,
storage, and display. Can be integrated into any Flask application.

Usage:
    from ajcc_tnm import init_app, get_blueprints
    
    # Initialize with Flask app
    init_app(app)
    
    # Register blueprints
    admin_bp, public_bp = get_blueprints()
    app.register_blueprint(admin_bp)
    app.register_blueprint(public_bp)
"""

import os

__version__ = "1.0.0"
__author__ = "FRCR Revision Team"

# Module paths
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_FOLDER = os.path.join(MODULE_DIR, 'templates')
DATA_FOLDER = os.path.join(MODULE_DIR, 'data')
SAMPLES_FOLDER = os.path.join(MODULE_DIR, 'samples')


def init_app(app, db=None, config=None):
    """
    Initialize the AJCC TNM module with a Flask application.
    
    Args:
        app: Flask application instance
        db: SQLAlchemy database instance (optional, uses app's db if not provided)
        config: AJCCConfig instance (optional, uses defaults if not provided)
    
    Returns:
        None
    """
    from .config import AJCCConfig
    
    # Use provided config or create default
    if config is None:
        config = AJCCConfig()
    
    # Store config in app
    app.extensions['ajcc_tnm'] = {
        'config': config,
        'db': db
    }
    
    # Add template folder to Jinja search path
    if TEMPLATE_FOLDER not in app.jinja_loader.searchpath:
        app.jinja_loader.searchpath.append(TEMPLATE_FOLDER)
    
    return None


def get_blueprints():
    """
    Get the Flask blueprints for AJCC TNM routes.
    
    Returns:
        tuple: (admin_blueprint, public_blueprint)
    """
    from .routes import admin_tnm_bp, tnm_bp
    return admin_tnm_bp, tnm_bp


def get_config(app):
    """
    Get the AJCC config from the Flask app.
    
    Args:
        app: Flask application instance
        
    Returns:
        AJCCConfig instance
    """
    ext = app.extensions.get('ajcc_tnm', {})
    return ext.get('config')


# Convenience exports for common imports
from .config import AJCCConfig

# Models will be exported after they're moved
# from .models import (
#     AJCCBodySection, AJCCDiseaseSite, AJCCDiagnosisYear,
#     AJCCStagingData, AJCCDiseaseMapping, AJCCStagingTimePrefix
# )
