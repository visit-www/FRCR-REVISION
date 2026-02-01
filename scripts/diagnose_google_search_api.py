#!/usr/bin/env python3
"""
Diagnose Google Custom Search API - test different request variations.
Run from project root: python scripts/diagnose_google_search_api.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[1] / ".env.local", override=True)

import requests

api_key = os.environ.get("GOOGLE_SEARCH_API_KEY") or os.environ.get("GOOGLE_CSE_API_KEY")
cx = os.environ.get("GOOGLE_SEARCH_ENGINE_ID") or os.environ.get("GOOGLE_CSE_ID")

if not api_key or not cx:
    print("ERROR: GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID required in .env")
    sys.exit(1)

# Canonical endpoint per Google docs (cse.list)
BASE_URL = "https://customsearch.googleapis.com/customsearch/v1"
# Site-restricted variant (if your PSE is site-restricted):
# BASE_URL_SITERESTRICT = "https://www.googleapis.com/customsearch/v1/siterestrict"
URLS = [BASE_URL]

def test_request(base_url, params, label):
    """Make request and print result."""
    full_url = base_url + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    # Mask key in output
    safe_url = full_url.replace(api_key, "KEY_MASKED")
    print(f"\n--- {label} ---")
    print(f"URL: {safe_url[:120]}...")
    try:
        r = requests.get(base_url, params=params, timeout=10)
        data = r.json()
        if "error" in data:
            err = data["error"]
            print(f"RESULT: 403/ERROR - {err.get('message', err)}")
            print(f"  Code: {err.get('code')}, Status: {r.status_code}")
            return False
        items = data.get("items", [])
        print(f"RESULT: OK - {len(items)} items, Status: {r.status_code}")
        return True
    except Exception as e:
        print(f"RESULT: Exception - {e}")
        return False

# Minimal required params only (key, cx, q)
minimal = {"key": api_key, "cx": cx, "q": "brain CT"}

# Our current params
current = {
    "key": api_key,
    "cx": cx,
    "q": "brain CT imaging",
    "searchType": "image",
    "num": 3,
    "rights": "cc_publicdomain,cc_attribute,cc_sharealike",
    "safe": "off",
}

print("=" * 60)
print("Google Custom Search API Diagnostic")
print("=" * 60)
print(f"API key: ...{api_key[-4:]}, cx: ...{cx[-4:]}")

for base_url in URLS:
    test_request(base_url, minimal, f"Minimal params @ {base_url.split('/')[2]}")
    test_request(base_url, current, f"Full params (with rights,safe) @ {base_url.split('/')[2]}")

# Try without rights - in case rights causes issue
no_rights = {**current}
del no_rights["rights"]
test_request(URLS[0], no_rights, "Without 'rights' param")

# Try without safe
no_safe = {**current}
del no_safe["safe"]
test_request(URLS[0], no_safe, "Without 'safe' param")

print("\n" + "=" * 60)
print("If all fail with 403: project/API access issue (not request params)")
print("=" * 60)
