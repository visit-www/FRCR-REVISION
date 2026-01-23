"""
AJCC TNM Routes

Flask blueprints for AJCC TNM public and admin endpoints.
"""

from .admin import admin_tnm_bp
from .public import tnm_bp

__all__ = ['admin_tnm_bp', 'tnm_bp']
