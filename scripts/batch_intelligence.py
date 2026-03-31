#!/usr/bin/env python3
"""
Batch Intelligence Processor
=============================
Backfills ContentIntelligence for admin content and processes pending UGI records
via Haiku. Follows batch_templates.py infrastructure pattern.

Keyword: RADINSIGHTS-CONTENT-BATCH-2026

Usage:
    PYTHONUNBUFFERED=1 python scripts/batch_intelligence.py list
    PYTHONUNBUFFERED=1 python scripts/batch_intelligence.py backfill [--type case|protocol|...]
    PYTHONUNBUFFERED=1 python scripts/batch_intelligence.py process-ugi [--limit 50]
"""

import argparse
import os
import sys
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env files (same order as app.py)
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


# Content type → (table, title_field, content_fields_sql, extra_where)
CONTENT_TYPE_MAP = {
    'case': {
        'table': '"case"',
        'title_field': 'diagnosis',
        'content_sql': "COALESCE(discussion, '')",
        'id_field': 'id',
        'body_section_field': "CAST(body_part AS TEXT)",
        'where': "status = 'PUBLISHED' AND discussion IS NOT NULL AND discussion != ''",
    },
    'protocol': {
        'table': 'clinical_protocol',
        'title_field': 'title',
        'content_sql': "COALESCE(content_html, '') || ' ' || COALESCE(keywords, '')",
        'id_field': 'id',
        'body_section_field': 'body_section',
        'where': "is_published = TRUE",
    },
    'reporting_algorithm': {
        'table': 'reporting_algorithm',
        'title_field': 'title',
        'content_sql': "COALESCE(description, '') || ' ' || COALESCE(keywords, '')",
        'id_field': 'id',
        'body_section_field': 'body_section',
        'where': "is_available = TRUE AND origin = 'admin'",
    },
    'radiology_template': {
        'table': 'radiology_template',
        'title_field': 'title',
        'content_sql': "COALESCE(description, '') || ' ' || LEFT(COALESCE(template_text, ''), 500)",
        'id_field': 'id',
        'body_section_field': 'body_section',
        'where': "is_available = TRUE",
    },
    'radiology_tool': {
        'table': 'incidental_finding_calculator',
        'title_field': 'finding_name',
        'content_sql': "COALESCE(description, '') || ' ' || COALESCE(keywords, '')",
        'id_field': 'id',
        'body_section_field': 'body_section',
        'where': "is_available = TRUE",
    },
    'radiology_pearl': {
        'table': 'radiology_pearl',
        'title_field': "LEFT(pearl_text, 100)",
        'content_sql': "COALESCE(pearl_text, '') || ' ' || COALESCE(tags, '')",
        'id_field': 'id',
        'body_section_field': 'body_section',
        'where': "is_verified = TRUE",
    },
    'anatomy_snippet': {
        'table': 'reporting_algorithm',
        'title_field': 'title',
        'content_sql': "COALESCE(description, '') || ' ' || COALESCE(keywords, '')",
        'id_field': 'id',
        'body_section_field': 'body_section',
        'where': "is_available = TRUE AND origin = 'anatomy_cache'",
    },
}


def get_neon_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(NEON_URL)
    Session = sessionmaker(bind=engine)
    return Session(), engine


def cmd_list(args):
    """Show content counts and intelligence coverage."""
    from sqlalchemy import text
    session, engine = get_neon_session()

    print(f"\n{'='*70}")
    print(f"  RadInsights Intelligence Status")
    print(f"{'='*70}")

    total_content = 0
    total_ci = 0

    for ctype, cfg in CONTENT_TYPE_MAP.items():
        count = session.execute(text(
            f"SELECT COUNT(*) FROM {cfg['table']} WHERE {cfg['where']}"
        )).scalar()
        ci_count = session.execute(text(
            "SELECT COUNT(*) FROM content_intelligence WHERE content_type = :t"
        ), {'t': ctype}).scalar()
        total_content += count
        total_ci += ci_count
        pct = f"{ci_count/count*100:.0f}%" if count > 0 else "N/A"
        print(f"  {ctype:25s}  {count:4d} items  |  {ci_count:4d} CI records  ({pct})")

    print(f"  {'─'*60}")
    print(f"  {'TOTAL':25s}  {total_content:4d} items  |  {total_ci:4d} CI records")

    # UGI stats
    for status in ('pending', 'processed', 'failed', 'discarded'):
        ugi_count = session.execute(text(
            "SELECT COUNT(*) FROM user_generated_intelligence WHERE processing_status = :s"
        ), {'s': status}).scalar()
        if ugi_count > 0:
            print(f"  UGI ({status:10s})  {ugi_count:4d} records")

    ugi_verified = session.execute(text(
        "SELECT COUNT(*) FROM user_generated_intelligence WHERE is_verified = TRUE"
    )).scalar()
    print(f"  UGI (verified)    {ugi_verified:4d} records")

    print(f"{'='*70}\n")
    session.close()


def cmd_backfill(args):
    """Backfill ContentIntelligence for admin content via Haiku."""
    from sqlalchemy import text

    target_types = [args.type] if args.type else list(CONTENT_TYPE_MAP.keys())
    session, engine = get_neon_session()

    from app import app
    from ai_intelligence import process_content_intelligence

    total_processed = 0
    total_failed = 0

    for ctype in target_types:
        cfg = CONTENT_TYPE_MAP.get(ctype)
        if not cfg:
            print(f"  Unknown type: {ctype}")
            continue

        # Get existing CI content_ids for this type
        existing_ids = set()
        rows = session.execute(text(
            "SELECT content_id FROM content_intelligence WHERE content_type = :t"
        ), {'t': ctype}).fetchall()
        existing_ids = {r[0] for r in rows}

        # Fetch content items
        items = session.execute(text(f"""
            SELECT {cfg['id_field']} AS id,
                   {cfg['title_field']} AS title,
                   {cfg['body_section_field']} AS body_section,
                   {cfg['content_sql']} AS content_text
            FROM {cfg['table']}
            WHERE {cfg['where']}
            ORDER BY {cfg['id_field']}
        """)).fetchall()

        todo = [r for r in items if r.id not in existing_ids]
        if not todo:
            print(f"  {ctype}: all {len(items)} items already have CI records")
            continue

        print(f"\n  {ctype}: {len(todo)} items to process (of {len(items)} total)")

        for i, row in enumerate(todo, 1):
            print(f"    [{i}/{len(todo)}] {ctype}:{row.id} — {(row.title or 'Untitled')[:50]}...", end=' ')
            try:
                with app.app_context():
                    result = process_content_intelligence(
                        content_type=ctype,
                        content_id=row.id,
                        title=row.title or 'Untitled',
                        body_section=row.body_section or '',
                        content_text=row.content_text or '',
                    )

                session.execute(text("""
                    INSERT INTO content_intelligence
                    (content_type, content_id, summary, search_tags, cross_links_json,
                     processing_model, processing_tokens, processed_at, created_at, updated_at)
                    VALUES (:content_type, :content_id, :summary, :search_tags, :cross_links_json,
                            :processing_model, :processing_tokens, NOW(), NOW(), NOW())
                    ON CONFLICT (content_type, content_id) DO UPDATE SET
                        summary = EXCLUDED.summary, search_tags = EXCLUDED.search_tags,
                        cross_links_json = EXCLUDED.cross_links_json,
                        processing_model = EXCLUDED.processing_model,
                        processing_tokens = EXCLUDED.processing_tokens,
                        processed_at = NOW(), updated_at = NOW()
                """), {
                    'content_type': ctype,
                    'content_id': row.id,
                    'summary': result['summary'],
                    'search_tags': result['search_tags'],
                    'cross_links_json': result.get('cross_links_json'),
                    'processing_model': result['processing_model'],
                    'processing_tokens': result['processing_tokens'],
                })
                session.commit()
                print(f"OK ({result['processing_tokens']} tokens)")
                total_processed += 1
            except Exception as exc:
                session.rollback()
                print(f"FAILED: {exc}")
                total_failed += 1

            if i < len(todo):
                time.sleep(2)

    print(f"\n  Done: {total_processed} processed, {total_failed} failed")
    session.close()


def cmd_process_ugi(args):
    """Process pending UGI records through Haiku."""
    from sqlalchemy import text
    session, engine = get_neon_session()

    from app import app
    from ai_intelligence import process_ugi

    limit = args.limit or 50
    rows = session.execute(text("""
        SELECT id, raw_teaching_point, raw_differentials, modality, body_section, exam_type
        FROM user_generated_intelligence
        WHERE processing_status IN ('pending', 'failed')
        ORDER BY created_at ASC
        LIMIT :limit
    """), {'limit': limit}).fetchall()

    if not rows:
        print("  No pending UGI records to process.")
        session.close()
        return

    print(f"\n  Processing {len(rows)} pending UGI records...")
    processed = 0
    failed = 0

    for i, row in enumerate(rows, 1):
        print(f"  [{i}/{len(rows)}] UGI:{row.id} — {(row.raw_teaching_point or '')[:50]}...", end=' ')
        try:
            with app.app_context():
                result = process_ugi(
                    raw_teaching_point=row.raw_teaching_point,
                    raw_differentials=row.raw_differentials,
                    modality=row.modality,
                    body_section=row.body_section,
                    exam_type=row.exam_type,
                )

            session.execute(text("""
                UPDATE user_generated_intelligence SET
                    diagnosis = :diagnosis, notes = :notes, pitfalls = :pitfalls,
                    enriched_differentials = :enriched_differentials,
                    search_tags = :search_tags, processing_model = :processing_model,
                    processing_tokens = :processing_tokens, processed_at = NOW(),
                    processing_status = 'processed', updated_at = NOW()
                WHERE id = :id
            """), {
                'id': row.id,
                'diagnosis': result['diagnosis'],
                'notes': result['notes'],
                'pitfalls': result['pitfalls'],
                'enriched_differentials': result['enriched_differentials'],
                'search_tags': result['search_tags'],
                'processing_model': result['processing_model'],
                'processing_tokens': result['processing_tokens'],
            })
            session.commit()
            print(f"OK — {result['diagnosis'][:40]}")
            processed += 1
        except Exception as exc:
            session.rollback()
            try:
                session.execute(text("""
                    UPDATE user_generated_intelligence SET
                        processing_status = 'failed', updated_at = NOW()
                    WHERE id = :id
                """), {'id': row.id})
                session.commit()
            except Exception:
                session.rollback()
            print(f"FAILED: {exc}")
            failed += 1

        if i < len(rows):
            time.sleep(2)

    print(f"\n  Done: {processed} processed, {failed} failed")
    session.close()


def cmd_backfill_learning_tags(args):
    """Backfill search_tags for LearningQuestion records via Haiku."""
    import re
    from sqlalchemy import text

    session, engine = get_neon_session()
    limit = args.limit or 500

    rows = session.execute(text("""
        SELECT id, title, tags, description, body_section, modality,
               source_report_context, html_content
        FROM learning_question
        WHERE search_tags IS NULL OR search_tags = ''
        ORDER BY id
        LIMIT :limit
    """), {'limit': limit}).fetchall()

    if not rows:
        print("  All learning questions already have search_tags.")
        session.close()
        return

    print(f"\n  Backfilling search_tags for {len(rows)} learning questions...")

    from ai_client import call_claude

    processed = 0
    failed = 0

    for i, row in enumerate(rows, 1):
        print(f"  [{i}/{len(rows)}] LQ:{row.id} — {(row.title or 'Untitled')[:50]}...", end=' ')

        # Strip HTML from content for the prompt
        plain_content = re.sub(r'<[^>]+>', ' ', (row.html_content or '')[:2000])
        plain_content = re.sub(r'\s+', ' ', plain_content).strip()[:800]

        prompt_text = (
            f"Title: {row.title or 'N/A'}\n"
            f"Body section: {row.body_section or 'N/A'}\n"
            f"Modality: {row.modality or 'N/A'}\n"
            f"Tags: {row.tags or 'N/A'}\n"
            f"Description: {row.description or 'N/A'}\n"
            f"Report context: {row.source_report_context or 'N/A'}\n"
            f"Content excerpt: {plain_content}\n"
        )

        try:
            response_text, model_used, tokens = call_claude(
                system_prompt=(
                    "Generate concise search tags for this radiology learning question. "
                    "Return ONLY a comma-separated list of 10-15 tags. Include:\n"
                    "- The primary diagnosis/condition (full name AND common abbreviations)\n"
                    "- Key imaging findings mentioned\n"
                    "- Relevant anatomy\n"
                    "- Related differential diagnoses\n"
                    "- Modality terms (e.g. CT, MRI, X-ray)\n"
                    "Example: pulmonary embolism, PE, filling defect, pulmonary artery, "
                    "CT pulmonary angiogram, CTPA, DVT, Hampton hump, Westermark sign\n"
                    "Return ONLY the comma-separated tags, nothing else."
                ),
                user_prompt=prompt_text,
                model='claude-haiku-4-5-20251001',
                max_tokens=300,
                temperature=0.2,
                skip_preamble=True,
            )

            search_tags = response_text.strip()
            if len(search_tags) > 1000:
                search_tags = search_tags[:1000]

            session.execute(text("""
                UPDATE learning_question
                SET search_tags = :search_tags
                WHERE id = :id
            """), {'search_tags': search_tags, 'id': row.id})
            session.commit()
            print(f"OK — {search_tags[:60]}...")
            processed += 1

        except Exception as exc:
            session.rollback()
            print(f"FAILED: {exc}")
            failed += 1

        if i < len(rows):
            time.sleep(1)

    print(f"\n  Done: {processed} processed, {failed} failed")
    session.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RadInsights Intelligence Batch Processor')
    subparsers = parser.add_subparsers(dest='command', help='Sub-command')

    # list
    subparsers.add_parser('list', help='Show content counts and intelligence coverage')

    # backfill
    backfill_parser = subparsers.add_parser('backfill', help='Backfill ContentIntelligence via Haiku')
    backfill_parser.add_argument('--type', choices=list(CONTENT_TYPE_MAP.keys()),
                                help='Process only this content type')

    # process-ugi
    ugi_parser = subparsers.add_parser('process-ugi', help='Process pending UGI records via Haiku')
    ugi_parser.add_argument('--limit', type=int, default=50, help='Max records to process')

    # backfill-learning-tags
    lt_parser = subparsers.add_parser('backfill-learning-tags',
                                      help='Backfill search_tags for learning questions via Haiku')
    lt_parser.add_argument('--limit', type=int, default=500, help='Max records to process')

    args = parser.parse_args()

    if args.command == 'list':
        cmd_list(args)
    elif args.command == 'backfill':
        cmd_backfill(args)
    elif args.command == 'process-ugi':
        cmd_process_ugi(args)
    elif args.command == 'backfill-learning-tags':
        cmd_backfill_learning_tags(args)
    else:
        parser.print_help()
