#!/usr/bin/env python3
"""
Add study_label to case_image_stack and stack_id to case_image_annotation (SQLite).
For local dev with USE_LOCAL_DB=1.

Usage:
  python scripts/utilities/run_sqlite_study_annotation_migration.py
"""

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

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
            print("[INFO] Not using SQLite - skip.")
            return

        with db.engine.connect() as conn:
            # case_image_stack: study_label
            r = conn.execute(text("PRAGMA table_info(case_image_stack)"))
            cols = {row[1] for row in r.fetchall()}
            if "study_label" not in cols:
                with db.engine.begin() as c:
                    c.execute(text("ALTER TABLE case_image_stack ADD COLUMN study_label VARCHAR(200)"))
                print("  [OK] Added study_label to case_image_stack")
            else:
                print("  [SKIP] study_label exists")

            # case_image_annotation: stack_id
            r = conn.execute(text("PRAGMA table_info(case_image_annotation)"))
            cols = {row[1] for row in r.fetchall()}
            if "stack_id" not in cols:
                with db.engine.begin() as c:
                    c.execute(text("ALTER TABLE case_image_annotation ADD COLUMN stack_id INTEGER REFERENCES case_image_stack(id) ON DELETE CASCADE"))
                print("  [OK] Added stack_id to case_image_annotation")
            else:
                print("  [SKIP] stack_id exists")

            # Make case_id nullable in case_image_annotation (for per-study annotations)
            r = conn.execute(text("PRAGMA table_info(case_image_annotation)"))
            info = {row[1]: row[3] for row in r.fetchall()}
            if info.get("case_id") == 1:  # NOT NULL
                print("  [INFO] case_id in case_image_annotation is NOT NULL; SQLite cannot ALTER. Keep as-is for now.")
                # SQLite cannot change nullability without recreating table - skip for backward compat
            else:
                print("  [SKIP] case_id already nullable or column missing")

        print("[OK] SQLite study/annotation migration done.")


if __name__ == "__main__":
    main()
