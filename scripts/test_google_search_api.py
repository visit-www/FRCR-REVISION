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
    "rights": "cc_publicdomain,cc_attribute,cc_sharealike",
}
# Try without rights first to see if CSE works at all
params_no_rights = {**params}
del params_no_rights["rights"]

print("Test 1: With CC rights filter")
r = requests.get(url, params=params, timeout=10)
data = r.json()
if "error" in data:
    print(f"  ERROR: {data['error'].get('message', data['error'])}")
    print(f"  Code: {data['error'].get('code')}")
else:
    items = data.get("items", [])
    print(f"  Status: {r.status_code}, Items: {len(items)}")
    for i, it in enumerate(items[:2], 1):
        print(f"  [{i}] {it.get('link', '')[:60]}...")

print()
print("Test 2: Without rights filter (to check if CSE works)")
r2 = requests.get(url, params=params_no_rights, timeout=10)
data2 = r2.json()
if "error" in data2:
    print(f"  ERROR: {data2['error'].get('message', data2['error'])}")
else:
    items2 = data2.get("items", [])
    print(f"  Status: {r2.status_code}, Items: {len(items2)}")
    if items2:
        print("  CSE works. If Test 1 had 0 items, the CC rights filter may be too strict.")
    else:
        print("  No items. Check: CSE has Image search ON and searches the entire web.")
