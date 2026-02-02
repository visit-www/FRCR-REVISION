#!/usr/bin/env python3
"""
Run a SQL migration against the Vercel/Neon DB only.
Does NOT import the Flask app, so .env.local never overrides .env.vercel.
Use this when run_sql_migration.py seems to run against a different DB.

Usage:
    vercel env pull .env.vercel --environment=production
    python scripts/utilities/run_sql_migration_vercel_only.py migrations/add_case_image_stack_description.sql
"""

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load ONLY .env.vercel - do not import app (which loads .env / .env.local and overrides)
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

# Same precedence as app.py so we hit the same DB Vercel uses
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
# Sanitize query params (strip newlines in values, e.g. sslmode=require\n)
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
    if len(sys.argv) < 2:
        print("Usage: python run_sql_migration_vercel_only.py <path-to.sql>")
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

    from sqlalchemy import create_engine, text

    def _strip_comments(stmt):
        lines = []
        for line in stmt.split('\n'):
            line = line.strip()
            if line and not line.startswith('--'):
                lines.append(line)
        return ' '.join(lines).strip()

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            for stmt in sql.split(';'):
                stmt = _strip_comments(stmt.strip())
                if stmt:
                    conn.execute(text(stmt))
        print(f"[OK] Ran {sql_path.name}")
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
