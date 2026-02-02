#!/usr/bin/env python3
"""
Run a standalone SQL migration file against Neon/PostgreSQL using Vercel env.

Usage:
    vercel env pull .env.vercel --environment=production
    source venv/bin/activate
    python scripts/utilities/run_sql_migration.py migrations/add_case_image_stack_description.sql

Or with DATABASE_URL already set:
    python scripts/utilities/run_sql_migration.py migrations/add_case_image_stack_description.sql
"""

import os
import sys
from pathlib import Path

# Project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load .env.vercel if present (same as run_migration.py)
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
    if len(sys.argv) < 2:
        print("Usage: python run_sql_migration.py <path-to.sql>")
        print("Example: python run_sql_migration.py migrations/add_case_image_stack_description.sql")
        sys.exit(1)
    sql_path = Path(sys.argv[1])
    if not sql_path.is_absolute():
        sql_path = _PROJECT_ROOT / sql_path
    if not sql_path.exists():
        print(f"[ERROR] File not found: {sql_path}")
        sys.exit(1)
    sql = sql_path.read_text().strip()
    if not sql:
        print("[WARN] SQL file is empty")
        sys.exit(0)

    from app import app
    from models import db
    from sqlalchemy import text

    with app.app_context():
        try:
            with db.engine.connect() as conn:
                for stmt in sql.split(';'):
                    stmt = stmt.strip()
                    if stmt and not stmt.startswith('--'):
                        conn.execute(text(stmt))
                        conn.commit()
            print(f"[OK] Ran {sql_path.name}")
        except Exception as e:
            print(f"[ERROR] {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()
