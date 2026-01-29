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


def search_sciencedirect(diagnosis: str, oauth_token: Optional[str] = None, user_id: Optional[int] = None, user_role: Optional[str] = None, custom_query: Optional[str] = None) -> Dict:
    """
    Search ScienceDirect using official Elsevier API (uses API key for all users).
    
    Uses the official ScienceDirect Search API endpoint with API key authentication.
    All requests are made server-side to protect the API key.
    Supports OAuth bearer token for user-level entitlements when available.
    
    Args:
        diagnosis: Diagnosis to search for
        oauth_token: Optional OAuth bearer token for user-level access
        user_id: Optional user ID for logging purposes
        user_role: Optional user role for logging purposes
        custom_query: Optional custom search query (overrides auto-generated query)
    
    Returns:
        Dict with:
            - search_url: URL to view results on ScienceDirect website
            - api_results: API response data (if API call successful)
            - diagnosis: Original diagnosis
            - query: Search query used
            - logged_in: True if using API
    """
    # Use custom query if provided, otherwise build auto-generated query
    if custom_query and custom_query.strip():
        # Use custom query directly
        search_query = custom_query.strip()
    else:
        # Build advanced search query focused on radiology with specific imaging modalities
        search_query = f'"{diagnosis}" AND (radiology OR "medical imaging" OR CT OR "computed tomography" OR MRI OR "magnetic resonance" OR staging OR "tumor staging" OR "cancer staging")'
    
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
        # Note: Elsevier API may require domain/IP registration
        # 401 errors on localhost are expected if key is registered for radinsights.xyz
        # Log API key status (first 8 chars only for security)
        api_key_preview = SCIDIRECT_API_KEY[:8] + '...' if len(SCIDIRECT_API_KEY) > 8 else SCIDIRECT_API_KEY
        print(f"[SCIDIRECT] Making API request - Key: {api_key_preview}, Endpoint: {SCIDIRECT_API_ENDPOINT}, Query: {search_query[:100]}")
        print(f"[SCIDIRECT] Headers: {list(headers.keys())} (API key present: {'X-ELS-APIKey' in headers})")
        
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
            
            # Log successful API usage
            log_info = f"User ID: {user_id}, Role: {user_role}" if user_id else "Anonymous"
            print(f"[SCIDIRECT] API search successful - {log_info} - Query: '{search_query}' - Results: {total_results}")
            
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
            log_info = f"User ID: {user_id}, Role: {user_role}" if user_id else "Anonymous"
            error_response = response.text[:500] if response.text else 'No response body'
            
            # Special handling for 401 (Unauthorized)
            if response.status_code == 401:
                print(f"[SCIDIRECT] API 401 Unauthorized - {log_info} - Query: '{search_query}'")
                print(f"[SCIDIRECT] This usually means:")
                print(f"  1. API key is invalid or not properly configured")
                print(f"  2. API key is registered for a different domain/IP (localhost vs radinsights.xyz)")
                print(f"  3. API key requires additional authentication headers")
                print(f"  4. Response: {error_response[:200]}")
            else:
                print(f"[SCIDIRECT] API request failed: {response.status_code} - {log_info} - Query: '{search_query}' - Response: {error_response}")
            
            # Try to parse error message from response
            error_message = f'API request failed: {response.status_code}'
            if response.status_code == 401:
                error_message = 'API authentication failed (401). Please check API key configuration.'
            try:
                error_json = response.json()
                if 'service-error' in error_json:
                    error_detail = error_json.get('service-error', {}).get('error', {})
                    error_message = error_detail.get('message', error_message)
                elif 'message' in error_json:
                    error_message = error_json.get('message', error_message)
            except:
                pass
            
            encoded_query = quote(search_query)
            search_url = f"{SCIDIRECT_SEARCH}?qs={encoded_query}"
            
            return {
                'search_url': search_url,
                'diagnosis': diagnosis,
                'query': search_query,
                'logged_in': False,
                'api_success': False,
                'error': error_message,
                'error_code': response.status_code,
                'error_detail': error_response[:200] if len(error_response) > 200 else error_response
            }
            
    except Exception as e:
        log_info = f"User ID: {user_id}, Role: {user_role}" if user_id else "Anonymous"
        error_type = type(e).__name__
        print(f"[SCIDIRECT] API search error: {error_type}: {e} - {log_info} - Query: '{search_query}'")
        # Fallback to website search URL
        encoded_query = quote(search_query)
        search_url = f"{SCIDIRECT_SEARCH}?qs={encoded_query}"
        
        return {
            'search_url': search_url,
            'diagnosis': diagnosis,
            'query': search_query,
            'logged_in': False,
            'api_success': False,
            'error': f'{error_type}: {str(e)}',
            'error_detail': 'Check if API key has domain restrictions (localhost vs radinsights.xyz)'
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


def search_sciencedirect_student(user, diagnosis: str, oauth_token: Optional[str] = None, custom_query: Optional[str] = None) -> Dict:
    """
    Search ScienceDirect for students using API key (server-side).
    
    Students now use the same API key as admins (server-side only).
    All API calls are made from the server to protect the API key.
    OAuth tokens can be used when available for user-level entitlements.
    
    Args:
        user: User object (for logging and optional OAuth token)
        diagnosis: Diagnosis to search for
        oauth_token: Optional OAuth bearer token for user-level access
        custom_query: Optional custom search query (overrides auto-generated query)
    
    Returns:
        Dict with search_url, api_results, diagnosis, query, and status
    """
    # Use the main API search function (same as admin)
    # Pass user info for logging
    return search_sciencedirect(
        diagnosis=diagnosis,
        oauth_token=oauth_token or (getattr(user, 'sciencedirect_oauth_token', None) if hasattr(user, 'sciencedirect_oauth_token') else None),
        user_id=user.id if user else None,
        user_role=user.role.value if user and hasattr(user, 'role') else None,
        custom_query=custom_query
    )
