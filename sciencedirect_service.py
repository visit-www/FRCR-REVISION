"""
ScienceDirect Integration Service for RadInsights

Purpose: Helper functions for ScienceDirect integration.
Uses client-side API calls (CORS) as recommended by Elsevier.

API Documentation: https://dev.elsevier.com/
Registered Portal: https://www.radinsights.xyz
API Key: Configured via SCIDIRECT_API_KEY environment variable
"""

import os
from urllib.parse import quote

# API Key from environment (for server-side use only - passed to frontend securely)
# SECURITY: No hardcoded fallback — key must be set via SCIDIRECT_API_KEY env var
SCIDIRECT_API_KEY = os.getenv('SCIDIRECT_API_KEY', '')

# ScienceDirect Website URLs
SCIDIRECT_BASE = "https://www.sciencedirect.com"
SCIDIRECT_SEARCH = f"{SCIDIRECT_BASE}/search/advanced"

# Elsevier API Configuration
ELSEVIER_API_BASE = "https://api.elsevier.com"
SCIDIRECT_API_ENDPOINT = f"{ELSEVIER_API_BASE}/content/search/sciencedirect"


def build_search_query(diagnosis: str, custom_query: str = None) -> str:
    """
    Build search query for ScienceDirect.
    
    Args:
        diagnosis: Diagnosis to search for
        custom_query: Optional custom search query (overrides auto-generated query)
    
    Returns:
        Search query string
    """
    if custom_query and custom_query.strip():
        return custom_query.strip()
    else:
        # Build advanced search query focused on radiology diagnosis.
        return f'{diagnosis} "radiological diagnosis"'


def build_search_url(query: str) -> str:
    """
    Build ScienceDirect website search URL.
    
    Args:
        query: Search query string
    
    Returns:
        URL to ScienceDirect search page
    """
    encoded_query = quote(query)
    return f"{SCIDIRECT_SEARCH}?qs={encoded_query}"


def get_api_key() -> str:
    """
    Get API key for client-side use.
    This should only be called from authenticated server endpoints.

    Returns:
        API key string, or empty string if not configured
    """
    if not SCIDIRECT_API_KEY:
        return ''
    return SCIDIRECT_API_KEY


def get_student_connect_url() -> str:
    """
    Get ScienceDirect login URL for student to connect.
    
    Returns:
        ScienceDirect login page URL
    """
    return f"{SCIDIRECT_BASE}/user/identity/login"
