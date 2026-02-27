#!/usr/bin/env python3
"""
Batch Clinical Protocol Generator
===================================
Generates clinical protocols for the On-Call Helper and syncs to Neon production DB.
Modelled on generate_tnm_calculator.py batch infrastructure.

Keyword: RADINSIGHTS-CONTENT-BATCH-2026

Usage:
    PYTHONUNBUFFERED=1 python scripts/batch_protocols.py list
    PYTHONUNBUFFERED=1 python scripts/batch_protocols.py batch
    PYTHONUNBUFFERED=1 python scripts/batch_protocols.py batch --phase 1
    PYTHONUNBUFFERED=1 python scripts/batch_protocols.py generate "Acute Contrast Reaction Management" emergency
"""

import argparse
import os
import sys
import time
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

NEON_URL = os.getenv('DATABASE_URL') or os.getenv('NEON_URL') or \
    "postgresql://neondb_owner:npg_DsKL8RFtw2zI@ep-frosty-sound-ahg70oqy-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"

# (title, category, source_citation)
# Categories: emergency, routine, safety, contrast, criteria, staging, anatomy, dose
BATCH_LIST = [
    # === PHASE 1: Contrast + Emergency (10) ===
    ('Acute Contrast Reaction Management (Anaphylaxis)', 'emergency', 'ACR Manual on Contrast Media 2024'),
    ('Contrast in Renal Impairment (eGFR Guidelines)', 'safety', 'ACR/RCR/ESUR Guidelines'),
    ('Metformin and Iodinated Contrast', 'safety', 'ESUR/RCR Guidelines'),
    ('MRI Gadolinium in Renal Impairment (NSF Risk)', 'safety', 'ACR Group Classification'),
    ('Contrast Premedication Regimen (High-Risk Patients)', 'safety', 'ACR Manual on Contrast Media 2024'),
    ('Acute Stroke Imaging Pathway (< 4.5h and Extended Window)', 'emergency', 'RCR/AHA Guidelines'),
    ('Whole-Body CT Polytrauma Protocol', 'emergency', 'ESER Dual-Track Approach'),
    ('Spinal Clearance Protocol (NEXUS/Canadian Rules)', 'emergency', 'NEXUS/Canadian C-Spine Rules'),
    ('MRI Safety Screening Questionnaire (Zones I-IV)', 'safety', 'ACR MR Safety Manual 2024'),
    ('NAI Skeletal Survey Protocol', 'emergency', 'RCR 2018 Guidelines'),
    # === PHASE 2: Expanded (10) ===
    ('Contrast Extravasation Management', 'emergency', 'ACR Manual on Contrast Media'),
    ('Breastfeeding and Contrast', 'safety', 'ACR/ESUR Guidelines'),
    ('Thyroid and Iodinated Contrast', 'safety', 'Thyroid Storm Risk in Hyperthyroidism'),
    ('Mechanical Thrombectomy Imaging Criteria', 'emergency', 'AHA/ASA Guidelines'),
    ('TIA Imaging Pathway', 'emergency', 'NICE/RCR Guidelines'),
    ('NAI Head Imaging Algorithm', 'emergency', 'RCR 2018 Guidelines'),
    ('Paediatric CT Dose Optimisation', 'safety', 'Image Gently / ALARA'),
    ('Paediatric Sedation Protocol (MRI/CT)', 'safety', 'RCR/RCPCH Guidelines'),
    ('UTI Imaging Pathway (Paediatric, NICE)', 'routine', 'NICE CG54 Update'),
    ('Biopsy Pre-Procedure Checklist (RADPASS)', 'routine', 'SIR/BSIR Guidelines'),
    # === PHASE 3: Specialist (10) ===
    ('Anticoagulation Management (Pre-IR Procedure)', 'routine', 'SIR/BSIR Risk Stratification'),
    ('Drain Insertion Protocol', 'routine', 'Seldinger Technique / BSIR'),
    ('Post-Procedure Observation', 'routine', 'SIR Standards'),
    ('Nephrostomy Protocol', 'routine', 'BSIR Guidelines'),
    ('MRI Conditional Implant Checklist', 'safety', 'ACR MR Safety Manual'),
    ('MRI in Pregnancy', 'safety', 'ACR/RCR Guidelines'),
    ('Claustrophobia Management', 'routine', 'RCR Best Practice'),
    ('Intussusception Air Reduction Protocol', 'emergency', 'Paediatric Radiology Guidelines'),
    ('Cerebral Venous Thrombosis Imaging Pathway', 'emergency', 'AHA/ASA CVT Guidelines'),
    ('Contrast Allergy Referral Pathway', 'safety', 'Immunology Testing Pathway'),
]


def _slugify(title):
    """Generate a URL-safe slug from title."""
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug[:80]


def generate_and_sync(title, category, source_citation=''):
    """Generate a clinical protocol via Claude API and save to Neon."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    print(f"\n{'='*60}")
    print(f"Clinical Protocol Generator")
    print(f"{'='*60}")
    print(f"Title: {title}")
    print(f"Category: {category}")
    print(f"Source: {source_citation}")
    print(f"{'='*60}\n")

    print("[1/2] Generating protocol with RadInsight Intelligence...")
    print("  Calling Claude API (this takes 30-60 seconds)...")

    from app import app
    from ai_oncall_helper import generate_protocol_content

    with app.app_context():
        result = generate_protocol_content(
            title=title,
            category=category,
            source_citation=source_citation,
        )

    content_html = result.get('content_html', '')
    content_structured = result.get('content_structured', '')
    keywords = result.get('suggested_keywords', '')
    guideline_version = result.get('guideline_version', '')

    if not content_html or len(content_html) < 100:
        raise ValueError(f"Generated content too short ({len(content_html)} chars)")

    print(f"  Content HTML: {len(content_html):,} chars")
    print(f"  Keywords: {keywords[:80]}...")
    print(f"  Guideline version: {guideline_version}")

    print("\n[2/2] Syncing to Neon (production DB)...")

    engine = create_engine(NEON_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Check by title (protocols don't have slugs)
    existing = session.execute(
        text("SELECT id FROM clinical_protocol WHERE title = :title"),
        {'title': title}
    ).fetchone()

    import json
    structured_str = json.dumps(content_structured) if isinstance(content_structured, (dict, list)) else str(content_structured or '')

    params = {
        'title': title,
        'category': category,
        'content_html': content_html,
        'content_structured': structured_str,
        'keywords': keywords if isinstance(keywords, str) else ', '.join(keywords) if keywords else '',
        'source_citation': source_citation,
        'guideline_version': guideline_version,
        'is_published': True,
    }

    if existing:
        session.execute(text("""
            UPDATE clinical_protocol SET
                category = :category, content_html = :content_html,
                content_structured = :content_structured, keywords = :keywords,
                source_citation = :source_citation, guideline_version = :guideline_version,
                is_published = :is_published
            WHERE title = :title
        """), params)
        print(f"  Updated existing record in Neon")
    else:
        session.execute(text("""
            INSERT INTO clinical_protocol
            (title, category, content_html, content_structured, keywords,
             source_citation, guideline_version, is_published, created_at)
            VALUES (:title, :category, :content_html, :content_structured, :keywords,
                    :source_citation, :guideline_version, :is_published, NOW())
        """), params)
        print(f"  Inserted new record in Neon")

    session.commit()
    session.close()
    print(f"\n  SUCCESS - clinical protocol: {title}")


def batch_generate(skip_existing=True, only_indices=None, phase=None):
    """Generate all protocols in BATCH_LIST sequentially."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    existing_titles = set()
    if skip_existing:
        engine = create_engine(NEON_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        rows = session.execute(text("SELECT title FROM clinical_protocol")).fetchall()
        existing_titles = {r[0] for r in rows}
        session.close()

    phase_ranges = {1: (0, 10), 2: (10, 20), 3: (20, 30)}

    todo = []
    for i, (title, category, source) in enumerate(BATCH_LIST):
        if phase and phase in phase_ranges:
            start, end = phase_ranges[phase]
            if i < start or i >= end:
                continue
        if only_indices and i not in only_indices:
            continue
        if title in existing_titles:
            print(f"  SKIP {title[:50]} (already exists)")
            continue
        todo.append((title, category, source))

    if not todo:
        print("\nNothing to generate - all protocols already exist.")
        return

    print(f"\n{'='*60}")
    print(f"BATCH Clinical Protocol Generation")
    print(f"{'='*60}")
    print(f"Total to generate: {len(todo)}")
    print(f"Estimated cost: ~${len(todo) * 0.05:.2f}")
    print(f"Estimated time: ~{len(todo) * 0.5:.0f}-{len(todo) * 1:.0f} minutes")
    print(f"{'='*60}")
    for i, (title, category, _) in enumerate(todo, 1):
        print(f"  {i:2d}. {title:55s} | {category}")
    print(f"{'='*60}\n")

    results = {'success': [], 'failed': []}
    start_time = time.time()

    for i, (title, category, source) in enumerate(todo, 1):
        print(f"\n[{i}/{len(todo)}] Generating: {title}")
        print(f"{'-'*50}")
        t0 = time.time()
        try:
            generate_and_sync(title, category, source)
            elapsed = time.time() - t0
            results['success'].append((title, elapsed))
            print(f"  Completed in {elapsed:.0f}s")
        except Exception as e:
            elapsed = time.time() - t0
            results['failed'].append((title, str(e)))
            print(f"  FAILED after {elapsed:.0f}s: {e}")

        if i < len(todo):
            time.sleep(2)

    total_time = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"BATCH GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"Total time: {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"Success: {len(results['success'])}")
    print(f"Failed:  {len(results['failed'])}")

    if results['success']:
        print(f"\nSuccessful:")
        for title, elapsed in results['success']:
            print(f"  {title:55s} ({elapsed:.0f}s)")
    if results['failed']:
        print(f"\nFailed:")
        for title, error in results['failed']:
            print(f"  {title:55s} - {error[:80]}")
    print()


def list_status():
    """Show all protocols and whether they exist in Neon."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(NEON_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    rows = session.execute(text(
        "SELECT title, LENGTH(content_html) as len FROM clinical_protocol"
    )).fetchall()
    existing = {r[0]: r[1] for r in rows}
    session.close()

    phases = {0: 'Phase 1 (Contrast + Emergency)', 10: 'Phase 2 (Expanded)', 20: 'Phase 3 (Specialist)'}
    print(f"\n{'Title':55s} | {'Category':12s} | Status")
    print(f"{'-'*110}")

    pending_count = 0
    for i, (title, category, _) in enumerate(BATCH_LIST):
        if i in phases:
            print(f"\n  --- {phases[i]} ---")
        if title in existing:
            status = f"EXISTS ({existing[title]:,} chars)"
        else:
            status = "PENDING"
            pending_count += 1
        print(f"{title:55s} | {category:12s} | {status}")

    print(f"\nTotal: {len(BATCH_LIST)} | Existing: {len(BATCH_LIST) - pending_count} | Pending: {pending_count}")
    print(f"Estimated cost for pending: ~${pending_count * 0.05:.2f}\n")


def main():
    parser = argparse.ArgumentParser(description='Batch Clinical Protocol Generator')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    single = subparsers.add_parser('generate', help='Generate a single protocol')
    single.add_argument('title', help='Protocol title')
    single.add_argument('category', help='Category (emergency, routine, safety, contrast, etc.)')
    single.add_argument('--source', '-s', default='', help='Source citation')

    batch = subparsers.add_parser('batch', help='Batch generate all protocols')
    batch.add_argument('--include-existing', action='store_true', help='Regenerate existing')
    batch.add_argument('--phase', type=int, choices=[1, 2, 3], help='Only generate specific phase')

    subparsers.add_parser('list', help='List all protocols and their status')

    args = parser.parse_args()

    if args.command == 'generate':
        generate_and_sync(args.title, args.category, getattr(args, 'source', ''))
    elif args.command == 'batch':
        batch_generate(
            skip_existing=not args.include_existing,
            phase=args.phase,
        )
    elif args.command == 'list':
        list_status()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
