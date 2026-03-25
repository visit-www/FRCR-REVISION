#!/usr/bin/env python3
"""
Resolve AI Cross-Link Hints
============================
Connects to Neon via app context, resolves title_hint strings in
ContentIntelligence.cross_links_json to actual content IDs + URLs.

Skips records that are already resolved (links contain 'id' key).

Usage:
    PYTHONUNBUFFERED=1 python scripts/resolve_cross_links.py
    PYTHONUNBUFFERED=1 python scripts/resolve_cross_links.py --dry-run
"""

import argparse
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


NEON_URL = (
    os.getenv('DATABASE_URL')
    or os.getenv('frcr_revision_db_DATABASE_URL')
    or "postgresql://neondb_owner:npg_DsKL8RFtw2zI@ep-frosty-sound-ahg70oqy-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"
)


def main():
    parser = argparse.ArgumentParser(description='Resolve cross-link hints to content IDs')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be resolved without writing')
    args = parser.parse_args()

    # Force Neon: monkey-patch load_dotenv BEFORE importing app.py
    # app.py calls load_dotenv(.env.local, override=True) at module level,
    # which would reset USE_LOCAL_DB=1. We prevent that by wrapping it.
    import dotenv
    _real_load = dotenv.load_dotenv
    def _neon_load(dotenv_path=None, override=False, **kw):
        result = _real_load(dotenv_path, override=override, **kw)
        # Always force Neon after any dotenv load
        os.environ['USE_LOCAL_DB'] = '0'
        os.environ['DATABASE_URL'] = NEON_URL
        return result
    dotenv.load_dotenv = _neon_load

    neon_uri = NEON_URL.replace('postgres://', 'postgresql://')
    os.environ['USE_LOCAL_DB'] = '0'
    os.environ['DATABASE_URL'] = NEON_URL
    print(f"Connecting to Neon: {neon_uri[:60]}...")

    from app import app
    from models import db, ContentIntelligence
    from ai_intelligence import resolve_cross_links

    # Restore original
    dotenv.load_dotenv = _real_load

    with app.app_context():
        records = ContentIntelligence.query.filter(
            ContentIntelligence.cross_links_json.isnot(None),
            ContentIntelligence.cross_links_json != '[]',
            ContentIntelligence.cross_links_json != '',
        ).all()

        print(f"Found {len(records)} ContentIntelligence records with cross_links_json")

        resolved_count = 0
        skipped_count = 0
        failed_count = 0

        for ci in records:
            try:
                hints = json.loads(ci.cross_links_json)
            except (json.JSONDecodeError, TypeError):
                failed_count += 1
                continue

            if not isinstance(hints, list) or not hints:
                skipped_count += 1
                continue

            # Skip already-resolved records (first link has 'id' key)
            if hints[0].get('id'):
                skipped_count += 1
                continue

            # Resolve hints to actual content
            resolved = resolve_cross_links(hints)

            label = f"  [{ci.content_type}:{ci.content_id}]"
            if not resolved:
                print(f"{label} — 0/{len(hints)} resolved")
                failed_count += 1
                continue

            print(f"{label} — {len(resolved)}/{len(hints)} resolved")
            for link in resolved:
                print(f"    -> {link['type']}: {link['title'][:60]} ({link.get('url', '?')})")

            if not args.dry_run:
                ci.cross_links_json = json.dumps(resolved)
                resolved_count += 1

        if not args.dry_run:
            db.session.commit()
            print(f"\nDone: {resolved_count} resolved, {skipped_count} skipped, {failed_count} failed")
        else:
            print(f"\n[DRY RUN] Would resolve: {resolved_count + len([r for r in records if True])}")
            print(f"Skipped (already resolved): {skipped_count}, Failed: {failed_count}")


if __name__ == '__main__':
    main()
