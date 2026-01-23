"""
AJCC Manual Authentication Helper

Since Okta uses JavaScript-based login forms that are difficult to automate,
this module provides a way to manually authenticate and use session cookies.

Usage:
1. Log in to AJCC website manually in your browser
2. Copy session cookies from browser DevTools
3. Use set_manual_cookies() to set them
4. The session will be used for API calls
"""

import os
from typing import Optional, Dict
from .auth_service import AJCCAuthSession


def set_manual_cookies(cookies_dict: Dict[str, str]) -> bool:
    """
    Set manual session cookies for AJCC authentication.
    
    Args:
        cookies_dict: Dictionary of cookie name:value pairs
                     Example: {'session_id': 'abc123', 'auth_token': 'xyz789'}
    
    Returns:
        bool: True if cookies set successfully
    """
    try:
        import json
        
        # Convert to Playwright format for consistency
        playwright_cookies = []
        for name, value in cookies_dict.items():
            playwright_cookies.append({
                'name': name,
                'value': value,
                'domain': '.ajccstaging.org',
                'path': '/',
                'httpOnly': True,
                'secure': True,
                'sameSite': 'Lax'
            })
        
        # Save in Playwright format
        with open(MANUAL_COOKIES_FILE, 'w') as f:
            json.dump(playwright_cookies, f, indent=2)
        
        # Also test with requests session
        from .auth_service import AJCCAuthSession
        session = AJCCAuthSession()
        
        # Clear existing cookies
        session.session.cookies.clear()
        
        # Set new cookies
        for name, value in cookies_dict.items():
            session.session.cookies.set(name, value, domain='.ajccstaging.org')
        
        # Test the session
        test_url = "https://ajccstaging.org/api/content/thorax/lung/2026?locale=en&add-headers=true"
        response = session.session.get(test_url, timeout=10)
        
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get('content') and len(data.get('content', '')) > 0:
                    print("[AJCC_MANUAL_AUTH] ✓ Manual cookies verified - authentication successful")
                    return True
            except:
                pass
        
        print("[AJCC_MANUAL_AUTH] ⚠ Manual cookies set but verification failed")
        return False
        
    except Exception as e:
        print(f"[AJCC_MANUAL_AUTH] Error setting manual cookies: {e}")
        return False


def get_cookie_instructions() -> str:
    """
    Get instructions for extracting cookies from browser.
    
    Returns:
        str: Instructions text
    """
    return """
HOW TO GET AJCC SESSION COOKIES:

1. Open your browser and go to: https://ajccstaging.org
2. Log in manually with your credentials
3. Open Browser DevTools (F12 or Cmd+Option+I)
4. Go to Application/Storage tab → Cookies → https://ajccstaging.org
5. Copy the following cookies (if they exist):
   - session_id
   - JSESSIONID
   - auth_token
   - Any cookie with 'okta' in the name
   - Any cookie with 'facs' in the name

6. Use the admin panel to set these cookies, or call:
   set_manual_cookies({
       'cookie_name': 'cookie_value',
       ...
   })

ALTERNATIVE: Use browser extension to export cookies as JSON
"""


# Store manual cookies in environment or file for persistence
MANUAL_COOKIES_FILE = ".ajcc_cookies.json"


def save_manual_cookies(cookies_dict: Dict[str, str]) -> bool:
    """Save manual cookies to file for persistence."""
    try:
        import json
        with open(MANUAL_COOKIES_FILE, 'w') as f:
            json.dump(cookies_dict, f)
        print(f"[AJCC_MANUAL_AUTH] Cookies saved to {MANUAL_COOKIES_FILE}")
        return True
    except Exception as e:
        print(f"[AJCC_MANUAL_AUTH] Error saving cookies: {e}")
        return False


def load_manual_cookies() -> Optional[Dict[str, str]]:
    """Load manual cookies from file. Returns dict format for compatibility."""
    try:
        import json
        if os.path.exists(MANUAL_COOKIES_FILE):
            with open(MANUAL_COOKIES_FILE, 'r') as f:
                cookies = json.load(f)
            
            # Convert Playwright format to dict if needed
            if isinstance(cookies, list):
                # Playwright format - convert to dict
                cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                print(f"[AJCC_MANUAL_AUTH] Cookies loaded from {MANUAL_COOKIES_FILE} ({len(cookies_dict)} cookies)")
                return cookies_dict
            elif isinstance(cookies, dict):
                # Already in dict format
                print(f"[AJCC_MANUAL_AUTH] Cookies loaded from {MANUAL_COOKIES_FILE} ({len(cookies)} cookies)")
                return cookies
    except Exception as e:
        print(f"[AJCC_MANUAL_AUTH] Error loading cookies: {e}")
    return None
