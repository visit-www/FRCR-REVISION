"""
ScienceDirect Integration Service for FRCR-Revision

Purpose: Enable residents to search ScienceDirect for radiology-related articles.
Uses advanced search with radiology, imaging, and diagnosis keywords.

Note: Auto-login is performed in the backend for all users using shared credentials.
"""

import os
import requests
from typing import Dict, Optional
from urllib.parse import quote, urlencode

# ScienceDirect credentials (shared for all users)
SCIDIRECT_USERNAME = os.getenv('SCIDIRECT_USERNAME', 'lotusheart2016@gmail.com')
SCIDIRECT_PASSWORD = os.getenv('SCIDIRECT_PASSWORD', 'Shine@2025')

# ScienceDirect URLs
SCIDIRECT_BASE = "https://www.sciencedirect.com"
SCIDIRECT_LOGIN = f"{SCIDIRECT_BASE}/user/identity/login"
SCIDIRECT_SEARCH = f"{SCIDIRECT_BASE}/search/advanced"


class ScienceDirectSession:
    """Manages ScienceDirect session with auto-login."""
    
    def __init__(self):
        self.session = requests.Session()
        self.logged_in = False
        self._login()
    
    def _login(self):
        """Perform auto-login to ScienceDirect."""
        try:
            # First, get the login page to get CSRF token and cookies
            login_page = self.session.get(SCIDIRECT_LOGIN, timeout=10)
            
            if login_page.status_code != 200:
                print(f"[SCIDIRECT] Failed to load login page: {login_page.status_code}")
                return False
            
            # Extract CSRF token if present (ScienceDirect may use different auth methods)
            # Try to find CSRF token in the page
            import re
            csrf_match = re.search(r'name=["\']_token["\']\s+value=["\']([^"\']+)["\']', login_page.text)
            csrf_token = csrf_match.group(1) if csrf_match else None
            
            # Prepare login data
            login_data = {
                'email': SCIDIRECT_USERNAME,
                'password': SCIDIRECT_PASSWORD
            }
            
            if csrf_token:
                login_data['_token'] = csrf_token
            
            # Attempt login
            login_response = self.session.post(
                SCIDIRECT_LOGIN,
                data=login_data,
                headers={
                    'Referer': SCIDIRECT_LOGIN,
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
                allow_redirects=True,
                timeout=10
            )
            
            # Check if login was successful (redirect to dashboard or account page)
            if login_response.status_code == 200 or login_response.status_code == 302:
                # Check if we're logged in by looking for user indicators
                if 'logout' in login_response.text.lower() or 'account' in login_response.url.lower():
                    self.logged_in = True
                    print("[SCIDIRECT] Login successful")
                    # Save session for future use
                    _save_session(self)
                    return True
                else:
                    # Try alternative: check cookies
                    if 'sdcore' in self.session.cookies or 'sdid' in self.session.cookies:
                        self.logged_in = True
                        print("[SCIDIRECT] Login successful (cookie-based)")
                        # Save session for future use
                        _save_session(self)
                        return True
            
            print(f"[SCIDIRECT] Login may have failed: {login_response.status_code}")
            # Even if login check fails, continue - some sites allow search without full login
            
        except Exception as e:
            print(f"[SCIDIRECT] Login error: {e}")
            # Continue anyway - search might work without full login
        
        return False
    
    def search(self, diagnosis: str) -> Dict:
        """
        Search ScienceDirect with advanced search parameters.
        
        Uses advanced search entry point with keywords: radiology, imaging, diagnosis
        
        Args:
            diagnosis: Diagnosis to search for
        
        Returns:
            Dict with search_url and diagnosis
        """
        # Build advanced search query
        # Format: diagnosis AND (radiology OR imaging OR diagnosis)
        # This ensures results are radiology-focused
        search_query = f"{diagnosis} AND (radiology OR imaging OR diagnosis)"
        
        # ScienceDirect advanced search entry point
        # The advanced search form uses specific parameter names
        # We'll construct a URL that pre-fills the advanced search form
        
        # Encode the query for URL
        encoded_query = quote(search_query)
        
        # Construct advanced search URL
        # ScienceDirect advanced search entry: https://www.sciencedirect.com/search/advanced
        # We'll use the query parameter to pre-fill the search
        search_url = f"{SCIDIRECT_SEARCH}?qs={encoded_query}"
        
        # Alternative: Use the standard search with advanced query syntax
        # This might work better for programmatic access
        # search_url = f"{SCIDIRECT_BASE}/search?qs={encoded_query}&show=100&sortBy=relevance"
        
        return {
            'search_url': search_url,
            'diagnosis': diagnosis,
            'query': search_query,
            'logged_in': self.logged_in
        }


# Global session instance (reused for all requests)
# Session is persisted to maintain login state
_session = None
_session_file = os.path.join(os.path.dirname(__file__), 'cache', 'sciencedirect_session.pkl')


def _save_session(session):
    """Save session cookies to file for persistence."""
    try:
        import pickle
        os.makedirs(os.path.dirname(_session_file), exist_ok=True)
        with open(_session_file, 'wb') as f:
            pickle.dump(dict(session.session.cookies), f)
    except Exception as e:
        print(f"[SCIDIRECT] Could not save session: {e}")


def _load_session(session):
    """Load session cookies from file."""
    try:
        import pickle
        if os.path.exists(_session_file):
            with open(_session_file, 'rb') as f:
                cookies = pickle.load(f)
                session.session.cookies.update(cookies)
                print("[SCIDIRECT] Loaded saved session cookies")
                return True
    except Exception as e:
        print(f"[SCIDIRECT] Could not load session: {e}")
    return False


def get_session() -> ScienceDirectSession:
    """Get or create ScienceDirect session with persistence."""
    global _session
    if _session is None:
        _session = ScienceDirectSession()
        # Try to load saved session
        if _load_session(_session):
            # Verify session is still valid by checking if we're logged in
            # If not, re-login will happen automatically
            pass
        # Save session after login
        if _session.logged_in:
            _save_session(_session)
    else:
        # If session exists, try to load saved cookies to refresh
        _load_session(_session)
    
    return _session


def search_sciencedirect(diagnosis: str) -> Dict:
    """
    Search ScienceDirect for articles related to diagnosis (ADMIN - uses shared session).
    
    Exam Relevance: Provides access to peer-reviewed radiology articles
    from ScienceDirect's extensive database.
    
    Args:
        diagnosis: Diagnosis to search for
    
    Returns:
        Dict with search_url, diagnosis, query, and logged_in status
    """
    session = get_session()
    return session.search(diagnosis)


def get_student_connect_url() -> str:
    """
    Get ScienceDirect login URL for student to connect.
    Returns the login page URL where student can authenticate.
    """
    return SCIDIRECT_LOGIN


def search_sciencedirect_student(user, diagnosis: str) -> Dict:
    """
    Search ScienceDirect for student.
    
    Note: Since we can't capture cookies from ScienceDirect directly due to browser security,
    we generate the search URL. Students will need to be logged in on ScienceDirect's site
    in their browser to access full-text articles. The connection status is tracked so they
    don't have to click "connect" again.
    
    Args:
        user: User object (connection status checked)
        diagnosis: Diagnosis to search for
    
    Returns:
        Dict with search_url, diagnosis, query, and logged_in status
    """
    # Build search query
    search_query = f"{diagnosis} AND (radiology OR imaging OR diagnosis)"
    encoded_query = quote(search_query)
    search_url = f"{SCIDIRECT_SEARCH}?qs={encoded_query}"
    
    # Check if user has connected (even though we can't use their cookies directly)
    logged_in = user.sciencedirect_connected_at is not None
    
    return {
        'search_url': search_url,
        'diagnosis': diagnosis,
        'query': search_query,
        'logged_in': logged_in,
        'note': 'You can search and view results. For full-text access, make sure you are logged in on ScienceDirect in your browser.'
    }
