#!/usr/bin/env python3
"""
Inspect case_image_stack table columns using the same env as the app (e.g. .env.vercel).
Use this to verify the DB that Vercel uses has the expected schema.

Usage:
    vercel env pull .env.vercel --environment=production
    python scripts/utilities/inspect_case_image_stack.py
"""

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_env_vercel = _PROJECT_ROOT / '.env.vercel'
if _env_vercel.exists():
    print("[INFO] Loading .env.vercel")
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

os.environ.setdefault('FLASK_APP', 'app.py')


def main():
    from app import app
    from models import db
    from sqlalchemy import text

    with app.app_context():
        # Show which URL we're using (redacted)
        url = os.getenv('DATABASE_POSTGRES_URL_NON_POOLING') or os.getenv('POSTGRES_URL_NON_POOLING') or os.getenv('DATABASE_URL') or ''
        if url:
            print(f"[DB] URL prefix: {url[:50]}...")
        with db.engine.connect() as conn:
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
        print("\ncase_image_stack columns:")
        for name, dtype in rows:
            print(f"  - {name} ({dtype})")
        has_desc = any(name == 'description_html' for name, _ in rows)
        print(f"\ndescription_html present: {has_desc}")
        if not has_desc:
            print("Run: python scripts/utilities/run_sql_migration.py migrations/add_case_image_stack_description.sql")
            sys.exit(1)


if __name__ == '__main__':
    main()
