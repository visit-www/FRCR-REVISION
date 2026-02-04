#!/usr/bin/env python3
"""
Verify case_image_stack schema for R2 migration on both Neon (Vercel) and Local DB.

Requirements:
  - storage_backend (varchar/text)
  - r2_config_json (jsonb/text)
  - display_order (integer)
  - onedrive_share_id nullable
  - case_id non-unique (allows multiple stacks per case)

Usage:
  vercel env pull .env.vercel --environment=production
  python scripts/utilities/check_case_image_stack_schema.py
"""

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

REQUIRED_COLUMNS = {"storage_backend", "r2_config_json", "display_order"}
OPTIONAL_COLUMNS = {"description_html", "onedrive_refresh_token_encrypted"}


def check_neon():
    """Check Neon DB using .env.vercel."""
    _env = _PROJECT_ROOT / ".env.vercel"
    if not _env.exists():
        print("[NEON] SKIP - .env.vercel not found (run: vercel env pull .env.vercel)")
        return None
    with open(_env) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                v = v.strip().strip("'\"").replace("\n", "").replace("\r", "").replace("\\n", "")
                os.environ[k.strip()] = v
    for key in ("DATABASE_URL", "POSTGRES_URL", "DATABASE_POSTGRES_URL_NON_POOLING", "POSTGRES_URL_NON_POOLING"):
        v = os.environ.get(key)
        if v and ("\n" in v or v != v.strip()):
            os.environ[key] = v.strip().replace("\n", "").replace("\r", "")
    url = (
        os.getenv("DATABASE_POSTGRES_URL_NON_POOLING")
        or os.getenv("POSTGRES_URL_NON_POOLING")
        or os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
    )
    if not url:
        print("[NEON] SKIP - No DATABASE_URL in .env.vercel")
        return None
    url = url.strip().replace("\n", "").replace("\r", "").replace("postgres://", "postgresql://", 1)
    # Sanitize query params (sslmode=require\n causes errors)
    try:
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        parsed = urlparse(url)
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            params = {k: [x.strip().replace("\n", "").replace("\r", "") for x in vals] for k, vals in params.items()}
            url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(params, doseq=True), parsed.fragment))
    except Exception:
        pass

    from sqlalchemy import create_engine, text
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        # Columns
        r = conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'case_image_stack'
            ORDER BY ordinal_position
        """))
        cols = {row[0]: (row[1], row[2]) for row in r.fetchall()}

        # Indexes (check case_id is NOT unique)
        r = conn.execute(text("""
            SELECT indexname, indexdef FROM pg_indexes
            WHERE tablename = 'case_image_stack'
        """))
        indexes = r.fetchall()

        # Row count
        r = conn.execute(text("SELECT COUNT(*) FROM case_image_stack"))
        count = r.scalar()

    return {"cols": cols, "indexes": indexes, "count": count, "engine": "postgresql"}


def check_local():
    """Check local DB using app config (SQLite or Neon via .env/.env.local)."""
    _local = _PROJECT_ROOT / ".env.local"
    if _local.exists():
        with open(_local) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ[k.strip()] = v.strip().strip("'\"")
    os.environ.setdefault("FLASK_APP", "app.py")
    try:
        from app import app
        from models import db
        from sqlalchemy import text
    except Exception as e:
        print(f"[LOCAL] SKIP - Could not load app: {e}")
        return None

    with app.app_context():
        uri = str(db.engine.url)
        is_sqlite = "sqlite" in uri
        with db.engine.connect() as conn:
            if is_sqlite:
                r = conn.execute(text("PRAGMA table_info(case_image_stack)"))
                cols = {row[1]: ("TEXT" if "char" in str(row[2]).lower() or row[2] == "TEXT" else str(row[2]), "YES" if row[3] == 0 else "NO") for row in r.fetchall()}
                r = conn.execute(text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='case_image_stack'"))
                indexes = [(n[0], "") for n in r.fetchall()]
            else:
                r = conn.execute(text("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'case_image_stack'
                    ORDER BY ordinal_position
                """))
                cols = {row[0]: (row[1], row[2]) for row in r.fetchall()}
                r = conn.execute(text("""
                    SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'case_image_stack'
                """))
                indexes = r.fetchall()
            r = conn.execute(text("SELECT COUNT(*) FROM case_image_stack"))
            count = r.scalar()

    return {"cols": cols, "indexes": indexes, "count": count, "engine": "sqlite" if is_sqlite else "postgresql", "uri": uri[:60] + "..."}


def report(name: str, data: dict):
    if not data:
        return
    cols = data["cols"]
    indexes = data["indexes"]
    count = data["count"]
    engine = data.get("engine", "?")

    print(f"\n{'='*60}")
    print(f"  {name} ({engine})")
    if data.get("uri"):
        print(f"  URI: {data['uri']}")
    print(f"{'='*60}")

    if not cols:
        print("  [ERROR] Table case_image_stack not found or empty")
        return False

    missing = REQUIRED_COLUMNS - set(cols.keys())
    if missing:
        print(f"  [MISSING] Required columns: {missing}")
        print("  Run migrations: add_case_image_stack_r2_columns.sql, add_case_image_stack_multiple_per_case.sql")
    else:
        print(f"  [OK] Required columns: {', '.join(REQUIRED_COLUMNS)}")

    # case_id unique?
    case_id_unique = any("unique" in str(idx).lower() and "case_id" in str(idx).lower() for _, idx in indexes)
    if case_id_unique:
        print("  [WARN] case_id still has UNIQUE constraint - multiple stacks per case will fail")
        print("  Run: migrations/add_case_image_stack_multiple_per_case.sql")
    else:
        print("  [OK] case_id allows multiple rows (non-unique)")

    print(f"  Rows: {count}")
    return len(missing) == 0 and not case_id_unique


def main():
    print("Checking case_image_stack schema for R2 migration...")
    neon_ok = report("NEON (Vercel/Production)", check_neon())
    local_ok = report("LOCAL", check_local())
    print()
    if neon_ok and (local_ok is None or local_ok):
        print("[PASS] Neon DB is up to date.")
        if local_ok is None:
            print("       Local DB not checked (no app load).")
        elif local_ok:
            print("       Local DB is up to date.")
    else:
        print("[FAIL] One or more DBs need migrations. See above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
