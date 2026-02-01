#!/usr/bin/env python3
"""
Test Google Custom Search API for reference images.
Run from project root: python scripts/test_google_search_api.py
"""
import os
import sys

# Load .env
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[1] / ".env.local", override=True)

api_key = os.environ.get("GOOGLE_SEARCH_API_KEY") or os.environ.get("GOOGLE_CSE_API_KEY")
cx = os.environ.get("GOOGLE_SEARCH_ENGINE_ID") or os.environ.get("GOOGLE_CSE_ID")

print("Config check:")
print(f"  GOOGLE_SEARCH_API_KEY: {'***' + (api_key[-4:] if api_key else '') + ' (set)' if api_key else 'NOT SET'}")
print(f"  GOOGLE_SEARCH_ENGINE_ID: {'***' + (cx[-4:] if cx else '') + ' (set)' if cx else 'NOT SET'}")
print()

if not api_key or not cx:
    print("Add both vars to .env and try again.")
    sys.exit(1)

import requests

url = "https://www.googleapis.com/customsearch/v1"
params = {
    "key": api_key,
    "cx": cx,
    "q": "brain CT imaging",
    "searchType": "image",
    "num": 3,
}
params_with_rights = {**params, "rights": "cc_publicdomain,cc_attribute,cc_sharealike"}

print("Test 1: Basic search (no CC filter)")
r = requests.get(url, params=params, timeout=10)
data = r.json()
if "error" in data:
    err = data["error"]
    code = err.get("code", "")
    msg = err.get("message", str(err))
    print(f"  ERROR: {msg}")
    print(f"  Code: {code}")
    if code == 403 or "access" in msg.lower():
        print()
        print("=" * 60)
        print("403 FIX CHECKLIST (Custom Search JSON API):")
        print("=" * 60)
        print("1. Enable API: console.cloud.google.com -> APIs & Services ->")
        print("   Library -> search 'Custom Search API' -> ENABLE")
        print()
        print("2. Billing: APIs & Services -> Billing. Link a billing account.")
        print("   (Required even for free tier. Free: 100 queries/day)")
        print()
        print("3. Same project: Ensure API key and Custom Search API are in")
        print("   the SAME Google Cloud project.")
        print()
        print("4. API key restrictions: Credentials -> your key -> if 'Restrict key',")
        print("   ensure 'Custom Search API' is in the allowed APIs list.")
        print("   Or temporarily use 'Don't restrict key' to test.")
        print()
        print("5. Wait: After enabling billing/API, wait 5-15 min for propagation.")
        print("=" * 60)
    sys.exit(1)
else:
    items = data.get("items", [])
    print(f"  OK - Status: {r.status_code}, Items: {len(items)}")
    for i, it in enumerate(items[:2], 1):
        print(f"  [{i}] {it.get('link', '')[:60]}...")

print()
print("Test 2: With CC rights filter")
r2 = requests.get(url, params=params_with_rights, timeout=10)
data2 = r2.json()
if "error" in data2:
    print(f"  ERROR: {data2['error'].get('message', data2['error'])}")
else:
    items2 = data2.get("items", [])
    print(f"  OK - Items: {len(items2)}")
    if items2:
        print("  All tests passed.")
    else:
        print("  CSE works but 0 CC results. Try different query or relax filter.")
