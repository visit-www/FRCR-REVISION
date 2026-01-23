# AJCC Authentication Issue & Solution

## Problem Identified

From the server logs, we can see:

1. **Okta uses JavaScript-based login forms** (React/Angular SPA)
   - No traditional HTML `<form>` tags
   - Cannot be automated with simple HTTP POST requests
   - Requires browser JavaScript execution

2. **API returns empty content without authentication**
   - Status: 200 OK
   - But: `Response data keys: []` (empty response)
   - This indicates the session is not authenticated

## Solution Implemented

### Option 1: Manual Cookie Input (Recommended for Now)

Since automated OAuth2 with JavaScript forms is complex, we've added a **manual cookie input** feature:

1. **How it works:**
   - Admin logs into AJCC website manually in browser
   - Extracts session cookies from browser DevTools
   - Pastes cookies into admin panel
   - System uses these cookies for API calls

2. **Steps to use:**
   - Go to `/api/admin/tnm/management`
   - Click "Show Instructions" in the Authentication Setup section
   - Follow the instructions to get cookies from browser
   - Paste cookies in JSON format
   - Click "Set Manual Cookies"
   - Cookies are saved and verified

3. **Cookie format:**
   ```json
   {
     "session_id": "abc123...",
     "JSESSIONID": "xyz789...",
     "okta_session": "..."
   }
   ```

### Option 2: Future - Browser Automation

For a fully automated solution, we could use:
- **Selenium** or **Playwright** for browser automation
- This would require additional dependencies
- More complex but fully automated

## Current Status

✅ **Manual cookie input implemented**
- Admin panel has cookie input section
- Cookies are saved to `.ajcc_cookies.json` (gitignored)
- Cookies are loaded automatically on server start
- Session verification on first use

⚠️ **Automated OAuth2 still needs work**
- Improved OAuth URL extraction (checks JavaScript)
- Better form detection
- But JavaScript forms still can't be automated easily

## Next Steps

1. **Immediate:** Use manual cookie input to test extraction
2. **Short-term:** Consider Selenium/Playwright for full automation
3. **Long-term:** Check if AJCC provides API tokens or alternative auth

## Testing Manual Authentication

1. Open browser and go to: https://ajccstaging.org
2. Log in manually
3. Open DevTools (F12) → Application → Cookies → ajccstaging.org
4. Copy relevant cookies (session, okta, facs-related)
5. Go to admin panel → TNM Management
6. Paste cookies in JSON format
7. Click "Set Manual Cookies"
8. Try extraction again

## Files Modified

- `ajcc_auth_service.py` - Improved OAuth URL extraction, manual cookie loading
- `ajcc_manual_auth_helper.py` - New module for manual cookie management
- `admin_tnm_routes.py` - Added `/set-cookies` endpoint
- `admin_tnm_management.html` - Added cookie input UI
- `.gitignore` - Added `.ajcc_cookies.json`
