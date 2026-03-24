#!/usr/bin/env python3
"""
Backfill keywords/description on original content tables from ContentIntelligence.
Runs directly on Neon. Only fills NULL or empty fields — never overwrites existing data.

Usage:
    PYTHONUNBUFFERED=1 python scripts/backfill_keywords.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from dotenv import load_dotenv
_env_dir = Path(__file__).resolve().parent.parent
load_dotenv(_env_dir / '.env', override=True)
load_dotenv(_env_dir / '.env.local', override=True)

NEON_URL = (
    os.getenv('DATABASE_URL')
    or os.getenv('NEON_URL')
    or os.getenv('POSTGRES_URL')
    or os.getenv('frcr_revision_db_DATABASE_URL')
    or os.getenv('frcr_revision_db_POSTGRES_URL')
    or os.getenv('frcr_revision_db_POSTGRES_URL_NON_POOLING')
)

if not NEON_URL:
    print("ERROR: No database URL found in environment")
    sys.exit(1)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

engine = create_engine(NEON_URL)
Session = sessionmaker(bind=engine)
session = Session()

# Each entry: (ci_content_type, target_table, description_col, keywords_col)
BACKFILL_MAP = [
    {
        'ci_type': 'protocol',
        'table': 'clinical_protocol',
        'desc_col': None,        # no description column
        'kw_col': 'keywords',
    },
    {
        'ci_type': 'reporting_algorithm',
        'table': 'reporting_algorithm',
        'desc_col': 'description',
        'kw_col': 'keywords',
    },
    {
        'ci_type': 'anatomy_snippet',
        'table': 'reporting_algorithm',
        'desc_col': 'description',
        'kw_col': 'keywords',
    },
    {
        'ci_type': 'radiology_template',
        'table': 'radiology_template',
        'desc_col': 'description',
        'kw_col': 'keywords',
    },
    {
        'ci_type': 'radiology_tool',
        'table': 'incidental_finding_calculator',
        'desc_col': 'description',
        'kw_col': 'keywords',
    },
    {
        'ci_type': 'radiology_pearl',
        'table': 'radiology_pearl',
        'desc_col': None,        # no description column
        'kw_col': 'tags',        # uses 'tags' instead of 'keywords'
    },
]

print(f"\n{'='*60}")
print(f"  Backfill keywords/description from ContentIntelligence")
print(f"{'='*60}\n")

total_desc = 0
total_kw = 0

for cfg in BACKFILL_MAP:
    ci_type = cfg['ci_type']
    table = cfg['table']
    desc_col = cfg['desc_col']
    kw_col = cfg['kw_col']

    # Fetch CI records for this type
    rows = session.execute(text("""
        SELECT content_id, summary, search_tags
        FROM content_intelligence
        WHERE content_type = :ct
    """), {'ct': ci_type}).fetchall()

    if not rows:
        print(f"  {ci_type}: no CI records — skip")
        continue

    desc_updated = 0
    kw_updated = 0

    for r in rows:
        content_id = r.content_id
        summary = (r.summary or '').strip()
        tags = (r.search_tags or '').strip()

        # Update description if column exists and current value is empty
        if desc_col and summary:
            result = session.execute(text(f"""
                UPDATE {table}
                SET {desc_col} = :summary
                WHERE id = :id
                  AND ({desc_col} IS NULL OR TRIM({desc_col}) = '')
            """), {'summary': summary, 'id': content_id})
            if result.rowcount > 0:
                desc_updated += 1

        # Update keywords/tags if current value is empty
        if kw_col and tags:
            result = session.execute(text(f"""
                UPDATE {table}
                SET {kw_col} = :tags
                WHERE id = :id
                  AND ({kw_col} IS NULL OR TRIM({kw_col}) = '')
            """), {'tags': tags, 'id': content_id})
            if result.rowcount > 0:
                kw_updated += 1

        # Also APPEND CI tags to existing keywords (merge, no duplicates)
        if kw_col and tags:
            existing = session.execute(text(f"""
                SELECT {kw_col} FROM {table} WHERE id = :id
            """), {'id': content_id}).scalar()

            if existing and existing.strip():
                # Merge: add new tags that aren't already present
                existing_set = {t.strip().lower() for t in existing.split(',') if t.strip()}
                new_tags = [t.strip() for t in tags.split(',') if t.strip() and t.strip().lower() not in existing_set]
                if new_tags:
                    merged = existing.rstrip(',').strip() + ', ' + ', '.join(new_tags)
                    session.execute(text(f"""
                        UPDATE {table} SET {kw_col} = :merged WHERE id = :id
                    """), {'merged': merged, 'id': content_id})
                    kw_updated += 1

    session.commit()

    total_desc += desc_updated
    total_kw += kw_updated
    print(f"  {ci_type} ({table}):")
    if desc_col:
        print(f"    description: {desc_updated} filled (of {len(rows)} CI records)")
    print(f"    {kw_col}: {kw_updated} updated/merged (of {len(rows)} CI records)")

print(f"\n  {'─'*50}")
print(f"  TOTAL: {total_desc} descriptions filled, {total_kw} keywords merged")
print(f"{'='*60}\n")

session.close()
