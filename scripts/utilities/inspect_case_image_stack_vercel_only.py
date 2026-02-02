#!/usr/bin/env python3
"""
Inspect case_image_stack columns using ONLY .env.vercel (no app import).
Use this to verify the Vercel/Neon DB schema.

Usage:
    vercel env pull .env.vercel --environment=production
    python scripts/utilities/inspect_case_image_stack_vercel_only.py
"""

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_env_vercel = _PROJECT_ROOT / '.env.vercel'
if not _env_vercel.exists():
    print("[ERROR] .env.vercel not found. Run: vercel env pull .env.vercel --environment=production")
    sys.exit(1)
print("[INFO] Loading .env.vercel only (no app import)")
with open(_env_vercel, 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, _, value = line.partition('=')
            key, value = key.strip(), value.strip().strip('"\' \n\r\t')
            os.environ[key] = value
for k in ('DATABASE_URL', 'POSTGRES_URL', 'POSTGRES_URL_NON_POOLING', 'DATABASE_POSTGRES_URL_NON_POOLING'):
    v = os.environ.get(k)
    if v and ('\n' in v or v != v.strip()):
        os.environ[k] = v.strip()

DATABASE_URL = (
    os.getenv('DATABASE_POSTGRES_URL_NON_POOLING')
    or os.getenv('POSTGRES_URL_NON_POOLING')
    or os.getenv('DATABASE_URL')
    or os.getenv('POSTGRES_URL')
)
if not DATABASE_URL:
    print("[ERROR] No DATABASE_URL in .env.vercel")
    sys.exit(1)
DATABASE_URL = DATABASE_URL.strip().replace('\n', '').replace('\r', '').replace('\\n', '')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
try:
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    parsed = urlparse(DATABASE_URL)
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        params = {k: [v.strip().replace('\n', '').replace('\r', '') for v in vals] for k, vals in params.items()}
        new_query = urlencode(params, doseq=True) if params else ''
        DATABASE_URL = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
except Exception:
    pass
print(f"[DB] Connecting to: {DATABASE_URL[:55]}...")

def main():
    from sqlalchemy import create_engine, text
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'case_image_stack'
            ORDER BY ordinal_position
        """))
        rows = r.fetchall()
    if not rows:
        print("[WARN] Table case_image_stack not found or has no columns.")
        sys.exit(1)
    print("\ncase_image_stack columns (Vercel/Neon DB):")
    for name, dtype in rows:
        print(f"  - {name} ({dtype})")
    has_desc = any(name == 'description_html' for name, _ in rows)
    print(f"\ndescription_html present: {has_desc}")
    sys.exit(0 if has_desc else 1)


if __name__ == '__main__':
    main()
