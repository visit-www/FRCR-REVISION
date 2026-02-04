#!/usr/bin/env python3
"""
Test R2 connection and diagnose Unauthorized/AccessDenied errors.

Run from project root with venv active:
  python scripts/utilities/test_r2_connection.py

Loads .env and .env.local the same way app.py does, then tries head_bucket.
"""

import os
import sys
from pathlib import Path

# Load env like app.py
_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_root))

from dotenv import load_dotenv
load_dotenv(_root / ".env")
load_dotenv(_root / ".env.local", override=True)


def _get(key: str) -> str | None:
    v = os.environ.get(key)
    if v is None:
        return None
    return v.strip().replace("\n", "").replace("\r", "").replace("\\n", "") or None


def main():
    print("=== R2 Connection Test ===\n")

    account_id = _get("R2_ACCOUNT_ID")
    access_key = _get("R2_ACCESS_KEY_ID")
    secret_key = _get("R2_SECRET_ACCESS_KEY")
    bucket = _get("R2_BUCKET_NAME")
    jurisdiction = (_get("R2_JURISDICTION") or "").lower().strip()

    print("Environment (loaded from .env then .env.local):")
    print(f"  R2_ACCOUNT_ID:     {repr(account_id)[:50]}... (len={len(account_id) if account_id else 0})")
    print(f"  R2_ACCESS_KEY_ID:  {repr(access_key)[:30]}... (len={len(access_key) if access_key else 0})")
    print(f"  R2_SECRET_ACCESS_KEY: {'***' if secret_key else 'MISSING'} (len={len(secret_key) if secret_key else 0})")
    print(f"  R2_BUCKET_NAME:    {repr(bucket)}")
    print(f"  R2_JURISDICTION:   {repr(jurisdiction) or '(default/US)'}")
    print()

    if not all([account_id, access_key, secret_key, bucket]):
        print("ERROR: Missing R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, or R2_BUCKET_NAME")
        return 1

    if len(account_id) != 32 or not all(c in "0123456789abcdef" for c in account_id.lower()):
        print("WARN: R2_ACCOUNT_ID should be 32 hex chars. Check Cloudflare R2 Overview for Account ID.")

    # Build endpoint (jurisdiction-specific if needed)
    if jurisdiction == "eu":
        endpoint = f"https://{account_id}.eu.r2.cloudflarestorage.com"
        print("Using EU jurisdiction endpoint (R2_JURISDICTION=eu)")
    elif jurisdiction == "fedramp":
        endpoint = f"https://{account_id}.fedramp.r2.cloudflarestorage.com"
        print("Using FedRAMP jurisdiction endpoint")
    else:
        endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
        print("Using default (US) endpoint")
    print(f"Endpoint: {endpoint}\n")

    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        print("ERROR: boto3 not installed. Run: pip install boto3")
        return 1

    config = Config(signature_version="s3v4", region_name="auto")
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=config,
    )

    print("Testing head_bucket...")
    try:
        client.head_bucket(Bucket=bucket)
        print("SUCCESS: head_bucket succeeded. R2 credentials and bucket are valid.")
        return 0
    except Exception as e:
        err = str(e)
        code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
        print(f"FAILED: {e}\n")

        if "Unauthorized" in err or code == "Unauthorized":
            print("Diagnosis: Unauthorized = invalid credentials or wrong endpoint.")
            print("  - If bucket is in EU jurisdiction: add R2_JURISDICTION=eu to .env")
            print("  - Recreate R2 API token (R2 > Manage R2 API Tokens) and copy Access Key ID + Secret Access Key")
            print("  - Ensure no extra spaces/newlines in .env values")
            print("  - Account ID must match the account where the bucket was created")
        elif "AccessDenied" in err or code == "AccessDenied":
            print("Diagnosis: AccessDenied = credentials valid but insufficient permissions.")
            print("  - Token must have 'Object Read & Write' permission")
            print("  - If scoped to specific buckets, ensure your bucket is included")
        elif "404" in err or "Not Found" in err:
            print("Diagnosis: Bucket not found.")
            print("  - R2_BUCKET_NAME must match exactly (case-sensitive)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
