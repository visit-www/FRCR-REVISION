#!/usr/bin/env python3
"""
Add R2 columns to SQLite case_image_stack (for local dev with USE_LOCAL_DB=1).
Works with any SQLite version - skips columns that already exist.

Usage:
  python scripts/utilities/run_sqlite_r2_migration.py
"""

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load .env.local for USE_LOCAL_DB
_env_local = _PROJECT_ROOT / ".env.local"
if _env_local.exists():
    with open(_env_local) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ[k.strip()] = v.strip().strip("'\"")

os.environ.setdefault("FLASK_APP", "app.py")


def main():
    from app import app
    from models import db
    from sqlalchemy import text

    with app.app_context():
        uri = str(db.engine.url)
        if "sqlite" not in uri:
            print("[INFO] Not using SQLite - skip. (Use run_sql_migration_vercel_only.py for Neon.)")
            return
        with db.engine.connect() as conn:
            r = conn.execute(text("PRAGMA table_info(case_image_stack)"))
            rows = r.fetchall()
            existing = {row[1] for row in rows}
            cols_info = {row[1]: row[3] for row in rows}  # name -> notnull
        to_add = [
            ("storage_backend", "VARCHAR(20) DEFAULT 'onedrive'"),
            ("r2_config_json", "TEXT"),
            ("display_order", "INTEGER DEFAULT 0"),
            ("description_html", "TEXT"),
            ("study_label", "VARCHAR(200)"),
        ]
        added = 0
        for col, spec in to_add:
            if col in existing:
                print(f"  [SKIP] {col} exists")
                continue
            try:
                with db.engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE case_image_stack ADD COLUMN {col} {spec}"))
                print(f"  [OK] Added {col}")
                added += 1
            except Exception as e:
                print(f"  [ERROR] {col}: {e}")
                sys.exit(1)

        # SQLite: make onedrive_share_id nullable (required for R2-only stacks)
        # PRAGMA table_info: notnull=1 means NOT NULL
        if cols_info.get("onedrive_share_id") == 1:
            print("  [INFO] Recreating table to allow NULL for onedrive_share_id (R2 stacks)...")
            with db.engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE case_image_stack_new (
                        id INTEGER PRIMARY KEY,
                        case_id INTEGER NOT NULL REFERENCES "case"(id) ON DELETE CASCADE,
                        display_order INTEGER NOT NULL DEFAULT 0,
                        onedrive_share_id VARCHAR(500),
                        onedrive_folder_path VARCHAR(500),
                        config_json TEXT NOT NULL DEFAULT '{}',
                        storage_backend VARCHAR(20) DEFAULT 'onedrive',
                        r2_config_json TEXT,
                        onedrive_refresh_token_encrypted TEXT,
                        description_html TEXT,
                        created_by_user_id INTEGER REFERENCES "user"(id),
                        created_at TIMESTAMP
                    )
                """))
                conn.execute(text("""
                    INSERT INTO case_image_stack_new
                    (id, case_id, display_order, onedrive_share_id, onedrive_folder_path, config_json,
                     storage_backend, r2_config_json, onedrive_refresh_token_encrypted, description_html,
                     created_by_user_id, created_at)
                    SELECT id, case_id, COALESCE(display_order, 0), onedrive_share_id, onedrive_folder_path,
                           COALESCE(config_json, '{}'), COALESCE(storage_backend, 'onedrive'), r2_config_json,
                           onedrive_refresh_token_encrypted, description_html, created_by_user_id, created_at
                    FROM case_image_stack
                """))
                conn.execute(text("DROP TABLE case_image_stack"))
                conn.execute(text("ALTER TABLE case_image_stack_new RENAME TO case_image_stack"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_case_image_stack_case_id ON case_image_stack(case_id)"))
            print("  [OK] onedrive_share_id is now nullable")

        print(f"[OK] SQLite migration done. Added {added} column(s).")


if __name__ == "__main__":
    main()
