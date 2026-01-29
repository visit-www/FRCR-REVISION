"""
ScienceDirect Integration Service for FRCR-Revision

Purpose: Enable residents to search ScienceDirect for radiology-related articles.
Uses official Elsevier ScienceDirect API with API key authentication.

API Documentation: https://dev.elsevier.com/
Registered Portal: https://www.radinsights.xyz
API Key: Configured via SCIDIRECT_API_KEY environment variable
"""

import os
import requests
from typing import Dict, Optional
from urllib.parse import quote, urlencode

# Elsevier API Configuration
ELSEVIER_API_BASE = "https://api.elsevier.com"
SCIDIRECT_API_ENDPOINT = f"{ELSEVIER_API_BASE}/content/search/sciencedirect"

# API Key from environment (fallback to provided key)
SCIDIRECT_API_KEY = os.getenv('SCIDIRECT_API_KEY', 'ebd7f645469e104b6326952959e1cde6')

# ScienceDirect Website URLs (for student manual login)
SCIDIRECT_BASE = "https://www.sciencedirect.com"
SCIDIRECT_LOGIN = f"{SCIDIRECT_BASE}/user/identity/login"
SCIDIRECT_SEARCH = f"{SCIDIRECT_BASE}/search/advanced"


def search_sciencedirect(diagnosis: str, oauth_token: Optional[str] = None) -> Dict:
    """
    Search ScienceDirect using official Elsevier API (ADMIN - uses API key).
    
    Uses the official ScienceDirect Search API endpoint with API key authentication.
    Supports OAuth bearer token for user-level entitlements when available.
    
    Args:
        diagnosis: Diagnosis to search for
        oauth_token: Optional OAuth bearer token for user-level access
    
    Returns:
        Dict with:
            - search_url: URL to view results on ScienceDirect website
            - api_results: API response data (if API call successful)
            - diagnosis: Original diagnosis
            - query: Search query used
            - logged_in: True if using API (always True for admin)
    """
    # Build advanced search query focused on radiology
    # Format: diagnosis AND (radiology OR imaging OR diagnosis)
    search_query = f"{diagnosis} AND (radiology OR imaging OR diagnosis)"
    
    # Prepare API request
    headers = {
        'X-ELS-APIKey': SCIDIRECT_API_KEY,
        'Accept': 'application/json'
    }
    
    # Add OAuth bearer token if provided (for user-level entitlements)
    if oauth_token:
        headers['Authorization'] = f'Bearer {oauth_token}'
    
    # API parameters
    params = {
        'query': search_query,
        'count': 25,  # Number of results
        'sort': 'relevance'  # Sort by relevance
    }
    
    try:
        # Make API request
        response = requests.get(
            SCIDIRECT_API_ENDPOINT,
            headers=headers,
            params=params,
            timeout=15
        )
        
        # Check response
        if response.status_code == 200:
            api_data = response.json()
            
            # Extract results from API response
            # API response structure: {'search-results': {'entry': [...], 'opensearch:totalResults': ...}}
            search_results = api_data.get('search-results', {})
            entries = search_results.get('entry', [])
            total_results = search_results.get('opensearch:totalResults', '0')
            
            # Build search URL for ScienceDirect website (for viewing full results)
            encoded_query = quote(search_query)
            search_url = f"{SCIDIRECT_SEARCH}?qs={encoded_query}"
            
            return {
                'search_url': search_url,
                'api_results': {
                    'articles': entries,
                    'total_results': total_results,
                    'query': search_query
                },
                'diagnosis': diagnosis,
                'query': search_query,
                'logged_in': True,  # API access means authenticated
                'api_success': True
            }
        else:
            # API request failed, fallback to website search URL
            print(f"[SCIDIRECT] API request failed: {response.status_code} - {response.text}")
            encoded_query = quote(search_query)
            search_url = f"{SCIDIRECT_SEARCH}?qs={encoded_query}"
            
            return {
                'search_url': search_url,
                'diagnosis': diagnosis,
                'query': search_query,
                'logged_in': False,
                'api_success': False,
                'error': f'API request failed: {response.status_code}'
            }
            
    except Exception as e:
        print(f"[SCIDIRECT] API search error: {e}")
        # Fallback to website search URL
        encoded_query = quote(search_query)
        search_url = f"{SCIDIRECT_SEARCH}?qs={encoded_query}"
        
        return {
            'search_url': search_url,
            'diagnosis': diagnosis,
            'query': search_query,
            'logged_in': False,
            'api_success': False,
            'error': str(e)
        }


def get_student_connect_url() -> str:
    """
    Get ScienceDirect login URL for student to connect.
    
    Students must manually log in on ScienceDirect's website with their own credentials.
    This returns the login page URL where they can authenticate.
    
    Returns:
        ScienceDirect login page URL
    """
    return SCIDIRECT_LOGIN


def search_sciencedirect_student(user, diagnosis: str) -> Dict:
    """
    Search ScienceDirect for student (manual login required).
    
    IMPORTANT: Students must use their own ScienceDirect credentials.
    This function generates a search URL that opens in a new window where
    the student must log in with their own credentials if not already logged in.
    
    Note: We cannot capture cookies from ScienceDirect due to browser security.
    Students must manually log in on ScienceDirect's website with their own account.
    The connection status is tracked so they don't have to click "connect" again,
    but they still need to authenticate on ScienceDirect's site.
    
    Args:
        user: User object (connection status checked)
        diagnosis: Diagnosis to search for
    
    Returns:
        Dict with search_url, diagnosis, query, and connection status
    """
    # Build search query
    search_query = f"{diagnosis} AND (radiology OR imaging OR diagnosis)"
    encoded_query = quote(search_query)
    
    # Construct search URL for ScienceDirect website
    search_url = f"{SCIDIRECT_SEARCH}?qs={encoded_query}"
    
    # Check if user has connected (they've clicked connect, but still need to log in on ScienceDirect)
    connected = user.sciencedirect_connected_at is not None
    
    return {
        'search_url': search_url,
        'login_url': SCIDIRECT_LOGIN,
        'diagnosis': diagnosis,
        'query': search_query,
        'logged_in': False,  # Always False for students - they must log in on ScienceDirect
        'connected': connected,  # Whether they've clicked "connect" in our app
        'requires_manual_login': True
    }
