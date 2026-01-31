#!/usr/bin/env python3
"""Check production DB for case images still stored as binary (not in Cloudinary)."""
import os
from pathlib import Path

# Load production env (Vercel-pulled)
env_file = Path(__file__).resolve().parent.parent / ".env.vercel"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                v = v.strip().strip('"').strip("'").replace("\\n", "").strip()
                if k and v:
                    os.environ[k] = v

db_url = (
    os.environ.get("frcr_revision_db_POSTGRES_URL")
    or os.environ.get("POSTGRES_URL")
    or os.environ.get("DATABASE_URL")
)
if not db_url:
    print("ERROR: No database URL found in .env.vercel")
    exit(1)

# Strip trailing \n if present
db_url = db_url.replace("\\n", "").strip()

import sqlalchemy
from sqlalchemy import text

engine = sqlalchemy.create_engine(db_url)

with engine.connect() as conn:
    # Count images with binary data (stored in DB, not Cloudinary)
    r = conn.execute(
        text("""
            SELECT ci.id, ci.case_id, ci.image_filename,
                   c.case_number, c.diagnosis,
                   CASE WHEN ci.image_url IS NOT NULL THEN 'Cloudinary' ELSE 'DB' END as storage
            FROM case_image ci
            JOIN "case" c ON c.id = ci.case_id
            WHERE ci.image_data IS NOT NULL
               OR (ci.image_url IS NULL AND ci.image_data IS NULL)
            ORDER BY ci.case_id, ci.id
        """)
    )
    rows = r.fetchall()

    # Also get total counts
    r2 = conn.execute(
        text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE image_url IS NOT NULL) as cloudinary,
                COUNT(*) FILTER (WHERE image_data IS NOT NULL) as db_binary,
                COUNT(*) FILTER (WHERE image_url IS NULL AND image_data IS NULL) as empty
            FROM case_image
        """)
    )
    total, cloudinary, db_binary, empty = r2.fetchone()

print("=== Case Image Storage Report (Production/Vercel DB) ===\n")
print(f"Total images:      {total}")
print(f"In Cloudinary:     {cloudinary}")
print(f"Still in DB:       {db_binary} (image_data present)")
print(f"Empty (broken):    {empty} (no url, no data)\n")

if rows:
    print("Images NOT in Cloudinary (need migration):\n")
    for r in rows:
        print(f"  id={r[0]} case_id={r[1]} case#{r[3]} | {r[2]} | diagnosis: {str(r[4])[:50]}... | {r[5]}")
    print(f"\n>>> {len(rows)} image(s) need to be migrated to Cloudinary")
else:
    print(">>> All images are in Cloudinary. None stored in DB.")
