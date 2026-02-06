#!/usr/bin/env python3
"""
One-time AI re-extraction of TNM data from raw AJCC HTML.

The regex-based parser frequently fails on DITA/XML junk in the raw HTML,
producing broken/missing T/N/M definitions. This script uses Claude to
cleanly extract structured TNM data from section_1_quick_reference_html.

Usage:
    python ajcc_tnm/scripts/ai_reextract_tnm.py              # Process all records
    python ajcc_tnm/scripts/ai_reextract_tnm.py --dry-run     # Preview without saving
    python ajcc_tnm/scripts/ai_reextract_tnm.py --id 5        # Process single record
    python ajcc_tnm/scripts/ai_reextract_tnm.py --id 5 --id 12  # Process specific records
"""

import os
import sys
import json
import re
import time
import argparse

# Add project root to path so we can import app/models
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, '.env'), override=True)
load_dotenv(os.path.join(project_root, '.env.local'), override=True)

import requests
from app import app, db

# Force Neon DB — this script must run against production, not local SQLite.
# app.py's load_dotenv(.env.local, override=True) sets USE_LOCAL_DB=1 which selects SQLite.
# We reconfigure the DB URI after import to point at Neon.
_neon_url = (
    os.getenv('DATABASE_POSTGRES_URL_NON_POOLING')
    or os.getenv('POSTGRES_URL_NON_POOLING')
    or os.getenv('DATABASE_URL')
    or os.getenv('POSTGRES_URL')
    or os.getenv('frcr_revision_db_POSTGRES_URL_NON_POOLING')
    or os.getenv('frcr_revision_db_DATABASE_URL')
)
if _neon_url:
    _neon_url = _neon_url.strip().replace('\n', '').replace('\r', '').replace('\\n', '')
    _neon_uri = _neon_url.replace('postgres://', 'postgresql://')
    app.config['SQLALCHEMY_DATABASE_URI'] = _neon_uri
    # Reinitialize the engine with the new URI
    with app.app_context():
        db.engine.dispose()
    print(f"[SCRIPT] Overrode DB → Neon: {_neon_uri[:60]}...")
else:
    print("[SCRIPT] WARNING: No Neon DATABASE_URL found in env — using whatever app.py configured")
    print("[SCRIPT] The script may be running against local SQLite!")
from models import AJCCStagingData


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_HTML_CHARS = 50000
REQUEST_TIMEOUT = 120  # seconds
DELAY_BETWEEN_REQUESTS = 5  # seconds — rate limit is 30K input tokens/min
MAX_RETRIES = 3
RETRY_BASE_DELAY = 60  # seconds — wait at least 1 min on rate limit


# ---------------------------------------------------------------------------
# HTML pre-cleaning (strip noise before sending to Claude)
# ---------------------------------------------------------------------------
def preclean_html(html: str) -> str:
    """Strip scripts, styles, and truncate to keep under token limits."""
    if not html:
        return ""
    # Remove <script> and <style> blocks
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML comments
    html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
    # Collapse excessive whitespace
    html = re.sub(r'\n{3,}', '\n\n', html)
    # Truncate if needed
    if len(html) > MAX_HTML_CHARS:
        html = html[:MAX_HTML_CHARS] + "\n<!-- TRUNCATED -->"
    return html.strip()


# ---------------------------------------------------------------------------
# Claude API call
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a medical data extraction specialist. You extract structured TNM staging data from messy AJCC HTML content.

You MUST return ONLY valid JSON — no markdown fences, no commentary, no explanation. Just the JSON object.

The HTML may contain DITA/XML artifacts, broken tags, metadata junk like [/concept/Tdefinition/...] or {""}) patterns. Ignore all that noise and extract the actual clinical content.

Rules:
- Extract ALL T, N, and M categories present in the HTML (TX, T0, Tis, T1, T1a, T1b, T2, T3, T4, T4a, T4b, etc.)
- For T definitions: group by subsite if the disease has subsite-specific definitions (e.g. supraglottis vs glottis for larynx). Use "Default" as the subsite name when there is only one group.
- For N definitions: separate clinical (cN) from pathological (pN) if both exist. If only one set exists, put it under "clinical" and leave "pathological" as an empty array.
- For M definitions: extract M0, M1, M1a, M1b, etc.
- For stage groups: extract all stage grouping rows (stage, T, N, M combinations). Use standard stage names (0, I, IA, IB, II, IIA, IIB, III, IIIA, IIIB, IV, IVA, IVB, IVC, etc.)
- Include any important notes (e.g. "p16+ oropharyngeal cancers use a separate staging system")
- Criteria text should be clean, readable English — no DITA artifacts
- If a section is not present in the HTML, use an empty array for that field"""


def build_user_prompt(html: str) -> str:
    return f"""Extract structured TNM staging data from this AJCC HTML content. Return ONLY the JSON object.

Required JSON schema:
{{
  "title": "string — disease/site name as it appears in the content",
  "t_definitions": [
    {{
      "subsite": "string — subsite name or 'Default'",
      "categories": [
        {{"category": "TX", "criteria": "Primary tumor cannot be assessed"}},
        {{"category": "T0", "criteria": "No evidence of primary tumor"}}
      ]
    }}
  ],
  "n_definitions": {{
    "clinical": [
      {{"category": "NX", "criteria": "Regional lymph nodes cannot be assessed"}},
      {{"category": "N0", "criteria": "No regional lymph node metastasis"}}
    ],
    "pathological": []
  }},
  "m_definitions": [
    {{"category": "M0", "criteria": "No distant metastasis"}},
    {{"category": "M1", "criteria": "Distant metastasis"}}
  ],
  "stage_groups": [
    {{"stage": "0", "T": "Tis", "N": "N0", "M": "M0"}},
    {{"stage": "I", "T": "T1", "N": "N0", "M": "M0"}}
  ],
  "notes": ["string — any important staging notes"]
}}

HTML content:
{html}"""


def call_claude(html: str, api_key: str) -> dict:
    """Send HTML to Claude and get structured TNM JSON back."""
    cleaned_html = preclean_html(html)
    if not cleaned_html:
        raise ValueError("HTML is empty after pre-cleaning")

    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 8000,
        "temperature": 0.1,
        "system": SYSTEM_PROMPT,  # Plain string — NOT array format
        "messages": [
            {"role": "user", "content": build_user_prompt(cleaned_html)}
        ],
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    response = None
    for attempt in range(1, MAX_RETRIES + 1):
        response = requests.post(
            CLAUDE_API_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 429 and attempt < MAX_RETRIES:
            wait = RETRY_BASE_DELAY * attempt
            print(f"        Rate limited (429), waiting {wait}s before retry {attempt + 1}/{MAX_RETRIES}...")
            time.sleep(wait)
            continue
        break

    if response.status_code >= 300:
        error_detail = response.text[:500] if response.text else "No details"
        raise RuntimeError(f"Claude API error (HTTP {response.status_code}): {error_detail}")

    data = response.json()
    content = data.get("content", [])
    if not content:
        raise RuntimeError("Claude returned empty content")

    text = content[0].get("text", "")

    # Strip markdown fences if present
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

    return json.loads(text)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_tnm_json(data: dict) -> list:
    """Validate extracted JSON. Returns list of warnings (empty = OK)."""
    warnings = []

    if not isinstance(data, dict):
        return ["Root is not a dict"]

    t_defs = data.get("t_definitions", [])
    if not isinstance(t_defs, list) or len(t_defs) == 0:
        warnings.append("No T definitions")
    else:
        for subsite in t_defs:
            cats = subsite.get("categories", [])
            if len(cats) == 0:
                warnings.append(f"T subsite '{subsite.get('subsite', '?')}' has no categories")

    n_defs = data.get("n_definitions", {})
    if not isinstance(n_defs, dict):
        warnings.append("n_definitions is not a dict")
    else:
        clinical = n_defs.get("clinical", [])
        if len(clinical) == 0:
            warnings.append("No clinical N definitions")

    m_defs = data.get("m_definitions", [])
    if not isinstance(m_defs, list) or len(m_defs) == 0:
        warnings.append("No M definitions")

    stage_groups = data.get("stage_groups", [])
    if not isinstance(stage_groups, list) or len(stage_groups) == 0:
        warnings.append("No stage groups")

    return warnings


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------
def count_existing(tnm_json_str: str) -> dict:
    """Count categories in existing tnm_data_json string."""
    if not tnm_json_str:
        return {"t": 0, "n_clin": 0, "n_path": 0, "m": 0, "stages": 0}
    try:
        data = json.loads(tnm_json_str)
    except (json.JSONDecodeError, TypeError):
        return {"t": 0, "n_clin": 0, "n_path": 0, "m": 0, "stages": 0}
    return count_data(data)


def count_data(data: dict) -> dict:
    """Count categories in a tnm data dict."""
    t_defs = data.get("t_definitions", [])
    if isinstance(t_defs, list):
        t_count = sum(len(s.get("categories", [])) for s in t_defs if isinstance(s, dict))
    else:
        t_count = 0

    n_defs = data.get("n_definitions", {})
    if isinstance(n_defs, dict):
        n_clin = len(n_defs.get("clinical", []))
        n_path = len(n_defs.get("pathological", []))
    elif isinstance(n_defs, list):
        n_clin = len(n_defs)
        n_path = 0
    else:
        n_clin = n_path = 0

    m_defs = data.get("m_definitions", [])
    m_count = len(m_defs) if isinstance(m_defs, list) else 0
    stage_groups = data.get("stage_groups", [])
    stage_count = len(stage_groups) if isinstance(stage_groups, list) else 0
    return {"t": t_count, "n_clin": n_clin, "n_path": n_path, "m": m_count, "stages": stage_count}


def fmt_counts(c: dict) -> str:
    return f"T:{c['t']} N(clin):{c['n_clin']} N(path):{c['n_path']} M:{c['m']} Stages:{c['stages']}"


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------
def has_good_data(tnm_json_str: str) -> bool:
    """Check if existing tnm_data_json has non-trivial data (likely already AI-extracted)."""
    if not tnm_json_str:
        return False
    try:
        data = json.loads(tnm_json_str)
    except (json.JSONDecodeError, TypeError):
        return False
    c = count_data(data)
    # Consider "good" if it has T defs AND (N or M) defs AND stage groups
    return c['t'] >= 3 and (c['n_clin'] >= 2 or c['n_path'] >= 2) and c['m'] >= 1 and c['stages'] >= 1


def process_record(record: AJCCStagingData, api_key: str, dry_run: bool = False,
                   skip_existing: bool = False) -> str:
    """
    Process a single record. Returns status string: 'success', 'skipped', or 'failed'.
    """
    disease_name = record.disease_site.disease_name if record.disease_site else f"ID:{record.id}"

    if not record.section_1_quick_reference_html:
        print(f"  SKIP  {disease_name} — no section_1 HTML")
        return "skipped"

    if skip_existing and has_good_data(record.tnm_data_json):
        print(f"  SKIP  [{record.id:3d}] {disease_name} — already has good data")
        return "skipped"

    html_len = len(record.section_1_quick_reference_html)
    old_counts = count_existing(record.tnm_data_json)

    print(f"  [{record.id:3d}] {disease_name} ({html_len:,} chars HTML)")
    print(f"        Old: {fmt_counts(old_counts)}")

    if dry_run:
        print(f"        DRY RUN — would send to Claude")
        return "success"

    try:
        extracted = call_claude(record.section_1_quick_reference_html, api_key)
    except json.JSONDecodeError as e:
        print(f"        FAIL — Claude returned invalid JSON: {e}")
        return "failed"
    except Exception as e:
        print(f"        FAIL — {e}")
        return "failed"

    # Validate
    warnings = validate_tnm_json(extracted)
    new_counts = count_data(extracted)
    print(f"        New: {fmt_counts(new_counts)}")

    if warnings:
        print(f"        Warnings: {'; '.join(warnings)}")

    # Save
    record.tnm_data_json = json.dumps(extracted, ensure_ascii=False)
    print(f"        OK")

    return "success"


def main():
    parser = argparse.ArgumentParser(description='AI re-extraction of TNM data from AJCC HTML')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview what would be done without calling Claude or saving')
    parser.add_argument('--id', type=int, action='append', dest='ids',
                        help='Process specific record ID(s) only. Can be repeated: --id 5 --id 12')
    parser.add_argument('--skip-existing', action='store_true',
                        help='Skip records that already have good TNM data (use for re-runs)')
    args = parser.parse_args()

    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key and not args.dry_run:
        print("ERROR: CLAUDE_API_KEY not set in environment")
        sys.exit(1)

    print("=" * 70)
    print("AI Re-extraction of TNM Data from AJCC HTML")
    print("=" * 70)
    if args.dry_run:
        print("MODE: DRY RUN (no API calls, no DB writes)")
    print(f"Model: {CLAUDE_MODEL}")
    print()

    with app.app_context():
        if args.ids:
            records = AJCCStagingData.query.filter(AJCCStagingData.id.in_(args.ids)).all()
            print(f"Processing {len(records)} specified record(s)")
        else:
            records = AJCCStagingData.query.all()
            print(f"Found {len(records)} total staging records")

        if not records:
            print("No records found.")
            return

        succeeded = 0
        failed = 0
        skipped = 0

        for i, record in enumerate(records):
            status = process_record(record, api_key, dry_run=args.dry_run,
                                    skip_existing=args.skip_existing)
            if status == "success":
                succeeded += 1
            elif status == "failed":
                failed += 1
            else:
                skipped += 1

            # Rate limiting (skip delay on dry run and last record)
            if not args.dry_run and i < len(records) - 1:
                time.sleep(DELAY_BETWEEN_REQUESTS)

        # Commit all changes at once
        if not args.dry_run and succeeded > 0:
            print(f"\nCommitting {succeeded} updated records to database...")
            db.session.commit()
            print("Committed.")

        print()
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"  Succeeded: {succeeded}")
        print(f"  Failed:    {failed}")
        print(f"  Skipped:   {skipped}")
        print(f"  Total:     {len(records)}")

        if args.dry_run:
            print("\nThis was a DRY RUN. Run without --dry-run to process.")


if __name__ == '__main__':
    main()
