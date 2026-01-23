# AJCC Authentication Flow

This document describes the correct login flow for AJCC Staging Online.

## Complete Authentication Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     AJCC AUTHENTICATION FLOW                         │
└─────────────────────────────────────────────────────────────────────┘

STEP 1: FACS Portal (Optional Entry Point)
┌─────────────────────────────────────────────────────────────────────┐
│ https://www.facs.org/quality-programs/cancer-programs/             │
│ american-joint-committee-on-cancer/ajcc-staging-online/             │
│                                                                       │
│ Page Content:                                                         │
│ • Information about AJCC Staging Online subscription                 │
│ • Link: "access your AJCC Staging Online subscription"               │
│   → Links to https://ajccstaging.org/en                             │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
STEP 2: AJCC Home Page
┌─────────────────────────────────────────────────────────────────────┐
│ https://ajccstaging.org/en                                           │
│                                                                       │
│ Page Content:                                                         │
│ • Main landing page with body systems (if authenticated)             │
│ • "Login" button in top right corner                                 │
│                                                                       │
│ ACTION: Click "Login" button                                         │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
STEP 3: AJCC Login Page
┌─────────────────────────────────────────────────────────────────────┐
│ https://ajccstaging.org/en/login                                     │
│                                                                       │
│ Page Content:                                                         │
│ • Login options page                                                  │
│ • "Okta" button/link                                                  │
│   → Links to Okta OAuth URL                                          │
│                                                                       │
│ ACTION: Click "Okta" button                                          │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
STEP 4: Okta Authentication Page
┌─────────────────────────────────────────────────────────────────────┐
│ https://login.facs.org/oauth2/v1/authorize?                         │
│   redirect_uri=https://ajccstaging.org/auth/okta                    │
│   &client_id=0oabuyb8n6zbTGYaw697                                   │
│   &response_type=code                                                 │
│   &scope=openid%20email%20profile                                    │
│   &state=/                                                            │
│                                                                       │
│ Page Content:                                                         │
│ • Okta login form                                                     │
│ • Username/email field                                                │
│ • Password field                                                      │
│ • Submit button                                                       │
│                                                                       │
│ ACTION: Fill username, password, and click submit                    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
STEP 5: OAuth Redirect & Callback
┌─────────────────────────────────────────────────────────────────────┐
│ https://ajccstaging.org/auth/okta?code=...                          │
│                                                                       │
│ Process:                                                              │
│ • Okta validates credentials                                          │
│ • Generates authorization code                                        │
│ • Redirects back to AJCC with code                                   │
│ • AJCC exchanges code for tokens                                     │
│ • Sets authentication cookies                                         │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
STEP 6: Authenticated AJCC Home
┌─────────────────────────────────────────────────────────────────────┐
│ https://ajccstaging.org/en                                           │
│                                                                       │
│ Page Content:                                                         │
│ • Full access to all 17 body systems                                 │
│ • Thorax, Head and Neck, Digestive System, etc.                     │
│ • User is now authenticated                                           │
│                                                                       │
│ Cookies Set:                                                          │
│ • Session cookies from ajccstaging.org                               │
│ • Authentication tokens                                               │
└─────────────────────────────────────────────────────────────────────┘
```

## Implementation in Code

### Browser Automation Flow

```python
# Step 1: Start at FACS portal (optional)
browser.navigate("https://www.facs.org/.../ajcc-staging-online/")

# Step 2: Navigate to AJCC home
browser.navigate("https://ajccstaging.org/en")

# Step 3: Click Login button
browser.click('a:has-text("Login")')

# Step 4: Click Okta button on login page
browser.click('a[href*="login.facs.org"]')

# Step 5: Fill and submit Okta form
browser.fill(username_field, username)
browser.fill(password_field, password)
browser.click(submit_button)

# Step 6: Wait for OAuth redirect
browser.wait_for_load_state("load")

# Step 7: Extract cookies
cookies = browser.get_cookies()
```

## Important Notes

### Bot Detection
The AJCC website has bot detection that may redirect to `/upgrade_browser` if:
- Browser fingerprint looks suspicious
- User agent is outdated
- JavaScript automation markers are detected

**Solution**: Use stealth browser settings (see `browser_automation_service.py`)

### OAuth Flow Timing
The OAuth redirect flow involves multiple navigations:
1. Okta validates credentials (2-3 seconds)
2. Generates authorization code (1 second)
3. Redirects to AJCC callback URL (1-2 seconds)
4. AJCC processes callback (2-3 seconds)
5. Final redirect to home page (1 second)

**Total time**: 7-12 seconds after clicking submit

**Solution**: Use appropriate wait times and load state checks

### Cookie Persistence
Authenticated cookies are valid for the session duration. Cookies include:
- Session ID
- Authentication tokens
- CSRF tokens

**Solution**: Save cookies to `.ajcc_cookies.json` and reuse for subsequent requests

## Testing the Flow

### Manual Test (Browser)
1. Open browser
2. Go to https://ajccstaging.org/en
3. Click "Login" (top right)
4. Click "Okta"
5. Enter credentials
6. Should see body systems after login

### Automated Test (Script)
```bash
python test_auth_quick.py
```

## Common Issues

### Issue: Redirected to `/upgrade_browser`
**Cause**: Bot detection triggered
**Solution**: 
- Use stealth browser settings
- Add proper user agent
- Hide automation markers

### Issue: "Execution context destroyed"
**Cause**: Trying to access page properties during navigation
**Solution**: 
- Wait for load state to complete
- Wrap page property accesses in try-except

### Issue: Cannot find login form
**Cause**: Not following the correct navigation flow
**Solution**: 
- Go through AJCC home → Login page → Okta
- Don't navigate directly to Okta URL

### Issue: Timeout on Okta page
**Cause**: Network latency or slow OAuth processing
**Solution**: 
- Increase timeout to 45 seconds
- Use "domcontentloaded" instead of "networkidle"

## API Endpoints

After authentication, you can access protected API endpoints:

```
GET https://ajccstaging.org/api/content/{section}/{disease}/{year}
    ?locale=en&add-headers=true

Example:
GET https://ajccstaging.org/api/content/head-and-neck/hypopharynx/2026
    ?locale=en&add-headers=true

Response: JSON with TNM staging data
```

## Session Management

### Session Lifetime
- Cookies valid for duration of session
- Typically 4-8 hours
- No specific expiry time in cookie

### Session Validation
Check if session is still valid:
```python
response = session.get(
    "https://ajccstaging.org/api/content/thorax/lung/2026",
    params={"locale": "en", "add-headers": "true"}
)

if response.status_code == 200 and response.json().get('content'):
    # Session is valid
else:
    # Need to re-authenticate
```

### Re-authentication
The system automatically re-authenticates if:
- Session expired (401 response)
- Cookies invalid
- More than 5 minutes since last validation check
