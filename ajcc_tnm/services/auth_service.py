"""
AJCC Authentication Service

Handles OAuth2 authentication with AJCC website via Okta.
Uses browser automation (Playwright) for JavaScript-based login forms.
Manages session cookies and authentication state.
"""

import os
import requests
from typing import Optional
from urllib.parse import urlparse, parse_qs, urlencode
import time
try:
    from browser_automation_service import BrowserAutomationService
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("[AJCC_AUTH] Warning: Playwright not available. Install with: pip install playwright && playwright install chromium")


class AJCCAuthSession:
    """Manages authenticated session with AJCC website."""
    
    def __init__(self):
        self.session = requests.Session()
        self.username = os.getenv("AJCC_USERNAME")
        self.password = os.getenv("AJCC_PASSWORD")
        self.base_url = "https://ajccstaging.org"
        self.login_url = "https://login.facs.org/oauth2/v1/authorize"
        self.authenticated = False
        self.last_auth_check = None
        self.auth_check_interval = 300  # Check every 5 minutes
        
        # Try to load saved cookies if available
        self._load_saved_cookies()
    
    def _load_saved_cookies(self):
        """Load saved cookies from file if available."""
        try:
            import json
            cookie_file = ".ajcc_cookies.json"
            if os.path.exists(cookie_file):
                with open(cookie_file, 'r') as f:
                    cookies = json.load(f)
                
                # Handle both formats: dict (manual) or list (Playwright)
                cookies_loaded = 0
                if isinstance(cookies, dict):
                    # Manual cookie format
                    for name, value in cookies.items():
                        self.session.cookies.set(name, value, domain='.ajccstaging.org')
                        cookies_loaded += 1
                elif isinstance(cookies, list):
                    # Playwright cookie format
                    for cookie in cookies:
                        try:
                            # Properly format domain
                            domain = cookie.get('domain', '')
                            if not domain:
                                domain = '.ajccstaging.org'
                            if domain and not domain.startswith('.'):
                                domain = '.' + domain
                            
                            self.session.cookies.set(
                                name=cookie['name'],
                                value=cookie['value'],
                                domain=domain,
                                path=cookie.get('path', '/'),
                                secure=cookie.get('secure', False),
                                expires=cookie.get('expires')
                            )
                            cookies_loaded += 1
                        except Exception as e:
                            print(f"[AJCC_AUTH] Warning: Could not load cookie {cookie.get('name', 'unknown')}: {e}")
                            continue
                
                print(f"[AJCC_AUTH] Loaded {cookies_loaded} cookies from file")
                # Don't mark as authenticated yet - will verify on first use
        except Exception as e:
            print(f"[AJCC_AUTH] Could not load saved cookies: {e}")
        
    def authenticate_ajcc(self) -> bool:
        """
        Perform OAuth2 login to AJCC website using browser automation.
        
        Returns:
            bool: True if authentication successful, False otherwise
        """
        if not self.username or not self.password:
            print("[AJCC_AUTH] Error: AJCC_USERNAME and AJCC_PASSWORD must be set in environment")
            return False
        
        if not PLAYWRIGHT_AVAILABLE:
            print("[AJCC_AUTH] Error: Playwright not installed")
            print("[AJCC_AUTH] Install with: pip install playwright && playwright install chromium")
            return False
        
        try:
            print("[AJCC_AUTH] Starting browser-based authentication...")
            
            # Use browser automation for JavaScript-based login
            with BrowserAutomationService(headless=True, browser_type="chromium") as browser:
                # Step 1: Navigate to FACS AJCC portal page first (proper entry point)
                # This is the correct flow: FACS portal -> AJCC site -> Login -> Okta
                facs_ajcc_url = "https://www.facs.org/quality-programs/cancer-programs/american-joint-committee-on-cancer/ajcc-staging-online/"
                print(f"[AJCC_AUTH] Step 1: Starting at FACS portal...")
                
                try:
                    browser.navigate(facs_ajcc_url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(2)
                    print(f"[AJCC_AUTH] Loaded FACS portal page")
                except Exception as e:
                    print(f"[AJCC_AUTH] Note: FACS portal navigation issue: {e}")
                    print(f"[AJCC_AUTH] Continuing with direct AJCC navigation...")
                
                # Step 2: Navigate to AJCC staging site
                ajcc_home_url = f"{self.base_url}/en"
                print(f"[AJCC_AUTH] Step 2: Navigating to AJCC home...")
                browser.navigate(ajcc_home_url, wait_until="domcontentloaded", timeout=20000)
                time.sleep(2)
                
                # Check if we were redirected to upgrade_browser (bot detection)
                current_url = browser.get_current_url()
                if 'upgrade_browser' in current_url:
                    print("[AJCC_AUTH] Warning: Redirected to upgrade_browser page - retrying...")
                    time.sleep(3)
                    browser.navigate(ajcc_home_url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(2)
                    current_url = browser.get_current_url()
                    
                    if 'upgrade_browser' in current_url:
                        print("[AJCC_AUTH] Still blocked. Browser may need additional anti-detection measures.")
                        # Continue anyway, the login flow might still work
                
                # Step 3: Look for and click the Login button on AJCC home page (top right)
                print("[AJCC_AUTH] Step 3: Looking for Login button on AJCC home...")
                time.sleep(1)
                
                try:
                    # Look for login button/link on the AJCC home page
                    login_selectors = [
                        'a:has-text("Login")',
                        'button:has-text("Login")',
                        'a:has-text("Sign In")',
                        'a[href*="/login"]',
                        'a[href*="/en/login"]',
                        '[class*="login"]',
                        '[id*="login"]',
                    ]
                    
                    login_clicked = False
                    for selector in login_selectors:
                        try:
                            if browser.page.locator(selector).count() > 0:
                                print(f"[AJCC_AUTH] Found login element: {selector}")
                                browser.page.locator(selector).first.click()
                                time.sleep(2)  # Wait for navigation
                                login_clicked = True
                                print(f"[AJCC_AUTH] Clicked login button")
                                break
                        except Exception as e:
                            continue
                    
                    if not login_clicked:
                        # Try direct navigation to login page
                        print("[AJCC_AUTH] No login button found, navigating directly to login page...")
                        login_page_url = f"{self.base_url}/en/login"
                        browser.navigate(login_page_url, wait_until="domcontentloaded", timeout=20000)
                        time.sleep(2)
                        print("[AJCC_AUTH] Navigated to login page")
                
                except Exception as e:
                    print(f"[AJCC_AUTH] Error clicking login: {e}")
                    # Fallback to direct navigation
                    login_page_url = f"{self.base_url}/en/login"
                    browser.navigate(login_page_url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(2)
                
                # Step 4: Now on login page, click the Okta button
                print("[AJCC_AUTH] Step 4: Looking for Okta button on login page...")
                time.sleep(1)
                
                try:
                    # Look for Okta login button/link
                    okta_selectors = [
                        'a:has-text("Okta")',
                        'button:has-text("Okta")',
                        'a:has-text("Sign In with Okta")',
                        'a[href*="login.facs.org"]',
                        'a[href*="okta"]',
                        'button:has-text("Sign In")',
                        'a:has-text("Sign In")',
                    ]
                    
                    okta_clicked = False
                    for selector in okta_selectors:
                        try:
                            if browser.page.locator(selector).count() > 0:
                                print(f"[AJCC_AUTH] Found Okta button: {selector}")
                                browser.page.locator(selector).first.click()
                                time.sleep(3)  # Wait for Okta to load
                                okta_clicked = True
                                print(f"[AJCC_AUTH] Clicked Okta button")
                                break
                        except:
                            continue
                    
                    if not okta_clicked:
                        # If no Okta button found, try direct navigation
                        print("[AJCC_AUTH] No Okta button found, navigating directly to Okta...")
                        okta_url = "https://login.facs.org/oauth2/v1/authorize?redirect_uri=https://ajccstaging.org/auth/okta&client_id=0oabuyb8n6zbTGYaw697&response_type=code&scope=openid%20email%20profile&state=/"
                        browser.navigate(okta_url, wait_until="domcontentloaded", timeout=45000)
                        time.sleep(3)
                        print("[AJCC_AUTH] Navigated directly to Okta")
                    
                except Exception as e:
                    print(f"[AJCC_AUTH] Error finding Okta button: {e}")
                    # Try direct Okta URL
                    print("[AJCC_AUTH] Retrying with direct Okta URL...")
                    okta_url = "https://login.facs.org/oauth2/v1/authorize?redirect_uri=https://ajccstaging.org/auth/okta&client_id=0oabuyb8n6zbTGYaw697&response_type=code&scope=openid%20email%20profile&state=/"
                    browser.navigate(okta_url, wait_until="domcontentloaded", timeout=45000)
                    time.sleep(3)
                
                # Step 5: Wait for Okta login form and fill credentials
                print("[AJCC_AUTH] Step 5: Waiting for Okta login form...")
                print(f"[AJCC_AUTH] Current URL: {browser.get_current_url()}")
                
                try:
                    # Wait for username/email field with more patience
                    username_selectors = [
                        'input[name="username"]',
                        'input[name="email"]',
                        'input[type="email"]',
                        'input[type="text"]',
                        'input[id*="username"]',
                        'input[id*="email"]',
                        'input[autocomplete="username"]',
                        '#okta-signin-username',
                        '#input0',
                    ]
                    
                    username_found = False
                    username_selector = None
                    
                    # Try each selector with shorter timeout
                    for selector in username_selectors:
                        try:
                            if browser.page.locator(selector).count() > 0:
                                username_found = True
                                username_selector = selector
                                print(f"[AJCC_AUTH] Found username field: {selector}")
                                break
                        except:
                            continue
                    
                    # If not found immediately, wait a bit and retry
                    if not username_found:
                        print("[AJCC_AUTH] No username field found immediately, waiting 5 seconds...")
                        time.sleep(5)
                        
                        for selector in username_selectors:
                            try:
                                if browser.page.locator(selector).count() > 0:
                                    username_found = True
                                    username_selector = selector
                                    print(f"[AJCC_AUTH] Found username field after wait: {selector}")
                                    break
                            except:
                                continue
                    
                    if not username_found:
                        print("[AJCC_AUTH] Error: Could not find username field")
                        print(f"[AJCC_AUTH] Page title: {browser.page.title()}")
                        # Take a screenshot for debugging
                        try:
                            browser.take_screenshot("debug_no_login_form.png")
                            print("[AJCC_AUTH] Screenshot saved to debug_no_login_form.png")
                        except:
                            pass
                        return False
                    
                    # Fill login form
                    print("[AJCC_AUTH] Filling login form...")
                    
                    # Fill username field using the found selector
                    try:
                        field = browser.page.locator(username_selector).first
                        field.click()  # Focus the field first
                        time.sleep(0.5)
                        field.fill(self.username)
                        print(f"[AJCC_AUTH] ✓ Filled username: {self.username}")
                        time.sleep(0.5)
                    except Exception as e:
                        print(f"[AJCC_AUTH] Error filling username: {e}")
                        return False
                    
                    # Find and fill password field
                    password_selectors = [
                        'input[name="password"]',
                        'input[type="password"]',
                        'input[id*="password"]',
                        'input[autocomplete="current-password"]',
                        '#okta-signin-password',
                        '#input1',
                    ]
                    
                    password_found = False
                    for selector in password_selectors:
                        try:
                            if browser.page.locator(selector).count() > 0:
                                field = browser.page.locator(selector).first
                                field.click()  # Focus the field first
                                time.sleep(0.5)
                                field.fill(self.password)
                                print(f"[AJCC_AUTH] ✓ Filled password field")
                                password_found = True
                                time.sleep(0.5)
                                break
                        except Exception as e:
                            print(f"[AJCC_AUTH] Could not fill password with {selector}: {e}")
                            continue
                    
                    if not password_found:
                        print("[AJCC_AUTH] Error: Could not find or fill password field")
                        return False
                    
                    # Submit form
                    print("[AJCC_AUTH] Submitting login form...")
                    submit_selectors = [
                        'button[type="submit"]',
                        'input[type="submit"]',
                        'button:has-text("Sign In")',
                        'button:has-text("Log In")',
                        'button:has-text("Submit")',
                        '#okta-signin-submit',
                        'input[value="Sign In"]',
                    ]
                    
                    submitted = False
                    for selector in submit_selectors:
                        try:
                            if browser.page.locator(selector).count() > 0:
                                print(f"[AJCC_AUTH] Found submit button: {selector}")
                                # Click and wait for navigation
                                browser.page.locator(selector).first.click()
                                print(f"[AJCC_AUTH] Clicked submit button")
                                # Wait for navigation or response
                                try:
                                    browser.page.wait_for_load_state("networkidle", timeout=30000)
                                except:
                                    pass  # Page might have already navigated
                                submitted = True
                                break
                        except Exception as e:
                            print(f"[AJCC_AUTH] Could not click {selector}: {e}")
                            continue
                    
                    if not submitted:
                        # Try pressing Enter on password field
                        print("[AJCC_AUTH] No submit button found, trying Enter key...")
                        try:
                            browser.page.locator('input[type="password"]').first.press('Enter')
                            browser.page.wait_for_load_state("networkidle", timeout=30000)
                            print("[AJCC_AUTH] Submitted form with Enter key")
                        except Exception as e:
                            print(f"[AJCC_AUTH] Error submitting with Enter: {e}")
                            return False
                    
                    # Wait for redirect to AJCC
                    print("[AJCC_AUTH] Waiting for authentication to complete...")
                    time.sleep(3)
                    
                    # Wait for navigation to complete (OAuth redirect)
                    try:
                        browser.page.wait_for_load_state("load", timeout=15000)
                        print("[AJCC_AUTH] Page loaded after authentication")
                    except Exception as e:
                        print(f"[AJCC_AUTH] Timeout waiting for page load (may be ok): {e}")
                    
                    time.sleep(2)  # Additional time for any redirects
                    
                    # Check if we're on AJCC site
                    try:
                        current_url = browser.get_current_url()
                        print(f"[AJCC_AUTH] Current URL after submit: {current_url}")
                        
                        # Try to get page title, but don't fail if navigation is still happening
                        try:
                            page_title = browser.page.title()
                            print(f"[AJCC_AUTH] Page title: {page_title}")
                        except:
                            print("[AJCC_AUTH] (Page still navigating, title unavailable)")
                        
                        # Check where we landed
                        if 'ajccstaging.org' in current_url and 'login' not in current_url.lower():
                            print("[AJCC_AUTH] ✓ Successfully redirected to AJCC site")
                        elif 'okta' in current_url or 'login.facs.org' in current_url:
                            # May need to handle MFA or additional steps
                            print("[AJCC_AUTH] Still on authentication page - may need additional steps")
                            print(f"[AJCC_AUTH] Checking for MFA prompt or errors...")
                            
                            # Wait a bit more for any MFA prompts or redirects
                            time.sleep(5)
                            try:
                                current_url = browser.get_current_url()
                                print(f"[AJCC_AUTH] URL after additional wait: {current_url}")
                                
                                if 'ajccstaging.org' not in current_url:
                                    print("[AJCC_AUTH] Warning: Authentication may have failed or requires manual intervention (MFA)")
                                    # Take screenshot for debugging
                                    try:
                                        browser.take_screenshot("debug_auth_stuck.png")
                                        print("[AJCC_AUTH] Screenshot saved to debug_auth_stuck.png")
                                    except:
                                        pass
                            except Exception as e:
                                print(f"[AJCC_AUTH] Error checking URL: {e}")
                    except Exception as e:
                        print(f"[AJCC_AUTH] Error getting page info: {e}")
                    
                    # Step 6: Extract cookies and set in requests session
                    print("[AJCC_AUTH] Step 6: Extracting cookies...")
                    cookies = browser.get_cookies()
                    
                    # Convert Playwright cookies to requests cookies
                    # Need to properly handle domain formatting for requests library
                    cookies_set = 0
                    for cookie in cookies:
                        try:
                            # Get cookie domain and ensure it's properly formatted
                            domain = cookie.get('domain', '')
                            if not domain:
                                domain = '.ajccstaging.org'
                            
                            # requests library needs domains to start with '.' for domain cookies
                            if domain and not domain.startswith('.'):
                                domain = '.' + domain
                            
                            # Set cookie with all available attributes
                            self.session.cookies.set(
                                name=cookie['name'],
                                value=cookie['value'],
                                domain=domain,
                                path=cookie.get('path', '/'),
                                secure=cookie.get('secure', False),
                                expires=cookie.get('expires')
                            )
                            cookies_set += 1
                        except Exception as e:
                            print(f"[AJCC_AUTH] Warning: Could not set cookie {cookie.get('name', 'unknown')}: {e}")
                            continue
                    
                    print(f"[AJCC_AUTH] Extracted {len(cookies)} cookies, set {cookies_set} in session")
                    
                    # Log a few important cookies for debugging
                    ajcc_cookies = [c['name'] for c in cookies if 'ajcc' in c.get('domain', '').lower() or 'facs' in c.get('domain', '').lower()]
                    if ajcc_cookies:
                        print(f"[AJCC_AUTH] AJCC/FACS cookies: {ajcc_cookies[:5]}")
                    
                    # Save cookies for future use
                    try:
                        browser.save_cookies_to_file(".ajcc_cookies.json")
                    except:
                        pass
                    
                except Exception as e:
                    print(f"[AJCC_AUTH] Error during login: {e}")
                    import traceback
                    traceback.print_exc()
                    return False
                
                # Step 7: Verify authentication
                print("[AJCC_AUTH] Step 7: Verifying authentication...")
                test_url = f"{self.base_url}/api/content/thorax/lung/2026?locale=en&add-headers=true"
                test_response = self.session.get(test_url, timeout=30)
                print(f"[AJCC_AUTH] Test response: {test_response.status_code}")
                
                if test_response.status_code == 200:
                    try:
                        data = test_response.json()
                        
                        # Check if response has the expected structure of authenticated API response
                        # Even if content is empty, if we get metadata fields, we're authenticated
                        expected_fields = ['title', 'metadata', 'versions', 'breadcrumbs']
                        has_metadata = any(field in data for field in expected_fields)
                        
                        # Also check if content exists (even if empty)
                        has_content_field = 'content' in data
                        
                        if has_metadata or has_content_field:
                            self.authenticated = True
                            self.last_auth_check = time.time()
                            
                            content_length = len(data.get('content', ''))
                            if content_length > 0:
                                print(f"[AJCC_AUTH] ✓ Authentication successful (content length: {content_length})")
                            else:
                                print(f"[AJCC_AUTH] ✓ Authentication successful (authenticated API access confirmed)")
                                print(f"[AJCC_AUTH]   Note: Content field empty for test URL, but API structure is valid")
                            return True
                        else:
                            print(f"[AJCC_AUTH] Response missing expected fields")
                            print(f"[AJCC_AUTH] Available keys: {list(data.keys())[:10]}")
                    except Exception as e:
                        print(f"[AJCC_AUTH] Failed to parse test response: {e}")
                elif test_response.status_code == 401:
                    print("[AJCC_AUTH] ✗ Authentication failed: Unauthorized (401)")
                    return False
                elif test_response.status_code == 403:
                    print("[AJCC_AUTH] ✗ Authentication failed: Forbidden (403)")
                    return False
                
                print("[AJCC_AUTH] ✗ Authentication verification failed")
                return False
                
        except ImportError:
            print("[AJCC_AUTH] Error: Playwright not installed")
            print("[AJCC_AUTH] Install with: pip install playwright && playwright install chromium")
            return False
        except Exception as e:
            print(f"[AJCC_AUTH] Error during authentication: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _extract_oauth_url(self, html_content: str) -> Optional[str]:
        """Extract OAuth2 authorization URL from login page HTML."""
        try:
            from bs4 import BeautifulSoup
            import re
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for Okta login link in anchor tags
            okta_link = soup.find('a', href=lambda x: x and 'login.facs.org' in x)
            if okta_link:
                href = okta_link.get('href')
                if href.startswith('http'):
                    return href
                else:
                    return f"{self.base_url}{href}"
            
            # Look for OAuth URL in JavaScript/scripts
            scripts = soup.find_all('script')
            for script in scripts:
                script_text = script.string or ''
                # Look for OAuth authorize URL patterns
                oauth_pattern = r'https://login\.facs\.org/oauth2/[^"\']+'
                matches = re.findall(oauth_pattern, script_text)
                if matches:
                    return matches[0]
            
            # Look for redirect in meta tags
            meta_refresh = soup.find('meta', attrs={'http-equiv': 'refresh'})
            if meta_refresh:
                content = meta_refresh.get('content', '')
                if 'url=' in content:
                    url = content.split('url=')[1]
                    return url.strip()
            
            # Look for window.location redirects in scripts
            for script in scripts:
                script_text = script.string or ''
                if 'window.location' in script_text or 'location.href' in script_text:
                    # Try to extract URL
                    url_pattern = r'["\'](https?://[^"\']+)["\']'
                    matches = re.findall(url_pattern, script_text)
                    for match in matches:
                        if 'login.facs.org' in match or 'oauth' in match.lower():
                            return match
            
            return None
        except Exception as e:
            print(f"[AJCC_AUTH] Error extracting OAuth URL: {e}")
            return None
    
    def _submit_login(self, html_content: str, current_url: str) -> bool:
        """Submit login credentials to Okta login form."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find login form
            form = soup.find('form')
            if not form:
                print("[AJCC_AUTH] Error: Could not find login form in HTML")
                print("[AJCC_AUTH] This may indicate the page structure has changed")
                # Try to find form by ID or class
                form = soup.find('form', id=lambda x: x and 'login' in x.lower())
                if not form:
                    form = soup.find('form', class_=lambda x: x and 'login' in str(x).lower())
            
            if not form:
                print("[AJCC_AUTH] No login form found - authentication may require manual browser login")
                return False
            
            # Get form action URL
            action = form.get('action', '')
            if not action:
                # Try method="post" forms without action (submit to same URL)
                action = current_url
            
            if not action.startswith('http'):
                # Relative URL - construct absolute
                parsed = urlparse(current_url)
                if action.startswith('/'):
                    action = f"{parsed.scheme}://{parsed.netloc}{action}"
                else:
                    action = f"{parsed.scheme}://{parsed.netloc}/{action}"
            
            print(f"[AJCC_AUTH] Form action: {action}")
            
            # Prepare form data
            form_data = {}
            for input_tag in form.find_all(['input', 'select']):
                name = input_tag.get('name')
                input_type = input_tag.get('type', '').lower()
                input_id = input_tag.get('id', '').lower()
                
                if name:
                    if input_type == 'hidden':
                        form_data[name] = input_tag.get('value', '')
                    elif name.lower() in ['username', 'email', 'user', 'login'] or 'username' in input_id or 'email' in input_id:
                        form_data[name] = self.username
                        print(f"[AJCC_AUTH] Found username field: {name}")
                    elif name.lower() in ['password', 'pass', 'pwd'] or 'password' in input_id:
                        form_data[name] = self.password
                        print(f"[AJCC_AUTH] Found password field: {name}")
            
            if not form_data:
                print("[AJCC_AUTH] Warning: No form fields found")
            
            # Submit form
            print(f"[AJCC_AUTH] Submitting form with {len(form_data)} fields...")
            response = self.session.post(action, data=form_data, allow_redirects=True, timeout=30)
            print(f"[AJCC_AUTH] Login response: {response.status_code}, URL: {response.url}")
            
            response.raise_for_status()
            
            # Check if we're redirected to AJCC (success) or still on login page (failure)
            if 'ajccstaging.org' in response.url and 'login' not in response.url.lower():
                print("[AJCC_AUTH] ✓ Redirected to AJCC site (likely success)")
                return True
            elif response.status_code in [200, 302]:
                # Check if we're still on a login page
                if 'login' in response.url.lower() or 'okta' in response.url.lower():
                    print("[AJCC_AUTH] Still on login page - authentication may have failed")
                    return False
                return True
            
            return False
            
        except Exception as e:
            print(f"[AJCC_AUTH] Error submitting login: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_authenticated_session(self) -> requests.Session:
        """
        Get authenticated session. Re-authenticates if needed.
        
        Returns:
            requests.Session: Authenticated session object
        """
        # Check if we need to re-authenticate
        if not self.authenticated:
            self.authenticate_ajcc()
        elif self.last_auth_check:
            # Check periodically if session is still valid
            elapsed = time.time() - self.last_auth_check
            if elapsed > self.auth_check_interval:
                if not self.is_session_valid():
                    self.authenticate_ajcc()
        
        return self.session
    
    def is_session_valid(self) -> bool:
        """
        Check if current session is still valid.
        
        Returns:
            bool: True if session is valid, False otherwise
        """
        try:
            # Test with a protected endpoint
            test_url = f"{self.base_url}/api/content/thorax/lung/2026?locale=en&add-headers=true"
            response = self.session.get(test_url, timeout=10)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('content') and len(data.get('content', '')) > 0:
                        self.last_auth_check = time.time()
                        return True
                except:
                    pass
            
            return False
        except Exception as e:
            print(f"[AJCC_AUTH] Error checking session validity: {e}")
            return False
    
    def get_session_cookies(self) -> list:
        """
        Get all cookies from the current session.
        
        Returns:
            list: List of cookie dicts with name, value, domain, etc.
        """
        cookies = []
        for cookie in self.session.cookies:
            cookies.append({
                'name': cookie.name,
                'value': cookie.value,
                'domain': cookie.domain,
                'path': cookie.path,
                'secure': cookie.secure,
                'expires': cookie.expires
            })
        return cookies
    
    def authenticate_with_playwright(self, username: str = None, password: str = None) -> bool:
        """
        Authenticate using Playwright browser automation.
        
        Args:
            username: AJCC/FACS username (optional, uses env var if not provided)
            password: AJCC/FACS password (optional, uses env var if not provided)
        
        Returns:
            bool: True if authentication successful
        """
        # Use provided credentials or fall back to environment variables
        if username:
            self.username = username
        if password:
            self.password = password
        
        if not self.username or not self.password:
            print("[AJCC_AUTH] Error: Username and password required")
            return False
        
        # Call the existing authenticate method
        return self.authenticate_ajcc()


# Global session instance
_global_session = None


def get_ajcc_session() -> requests.Session:
    """
    Get or create authenticated AJCC session.
    
    Returns:
        requests.Session: Authenticated session
    """
    global _global_session
    
    if _global_session is None:
        _global_session = AJCCAuthSession()
    
    return _global_session.get_authenticated_session()


def authenticate_ajcc() -> bool:
    """
    Perform AJCC authentication.
    
    Returns:
        bool: True if successful
    """
    global _global_session
    
    if _global_session is None:
        _global_session = AJCCAuthSession()
    
    return _global_session.authenticate_ajcc()
