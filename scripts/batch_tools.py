#!/usr/bin/env python3
"""
Batch Radiology Tools (Incidental Findings Calculator) Generator
=================================================================
Generates interactive clinical decision tools and syncs to Neon production DB.
Modelled on generate_tnm_calculator.py batch infrastructure.

Keyword: RADINSIGHTS-CONTENT-BATCH-2026

Usage:
    PYTHONUNBUFFERED=1 python scripts/batch_tools.py list
    PYTHONUNBUFFERED=1 python scripts/batch_tools.py batch
    PYTHONUNBUFFERED=1 python scripts/batch_tools.py batch --phase 1
    PYTHONUNBUFFERED=1 python scripts/batch_tools.py generate thyroid-nodule-incidental "Thyroid Nodule (Incidental on CT)" "Head and Neck" thyroid
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

NEON_URL = os.getenv('DATABASE_URL') or os.getenv('NEON_URL') or \
    "postgresql://neondb_owner:npg_DsKL8RFtw2zI@ep-frosty-sound-ahg70oqy-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"

# (slug, finding_name, body_section, category, guideline_source)
BATCH_LIST = [
    # === PHASE 1: ACR White Papers + Scoring (10) ===
    ('thyroid-nodule-incidental', 'Thyroid Nodule (Incidental on CT)', 'Head and Neck', 'thyroid', 'ACR White Paper 2015'),
    ('renal-mass-incidental', 'Renal Mass (Incidental)', 'Abdomen', 'renal', 'ACR White Paper 2017'),
    ('liver-lesion-incidental', 'Liver Lesion (Incidental)', 'Abdomen', 'hepatic', 'ACR White Paper 2017'),
    ('pancreatic-cyst-incidental', 'Pancreatic Cyst (Incidental)', 'Abdomen', 'pancreatic', 'ACR White Paper 2017'),
    ('ovarian-adnexal-incidental', 'Ovarian/Adnexal Mass (Incidental)', 'Pelvis', 'ovarian', 'ACR White Paper 2019'),
    ('pulmonary-nodule-fleischner', 'Pulmonary Nodule (Fleischner Calculator)', 'Thorax', 'pulmonary', 'Fleischner Society 2017'),
    ('pulmonary-nodule-bts', 'Pulmonary Nodule (BTS UK Guidelines)', 'Thorax', 'pulmonary', 'British Thoracic Society 2015'),
    ('wells-score-pe', 'Wells Score - Pulmonary Embolism', 'Thorax', 'scoring', 'Wells PE Score'),
    ('wells-score-dvt', 'Wells Score - DVT', 'Cardiovascular', 'scoring', 'Wells DVT Score'),
    ('nascet-calculator', 'NASCET Calculator (Carotid Stenosis %)', 'Cardiovascular', 'vascular', 'NASCET Method'),
    # === PHASE 2: Expanded IF + Scoring (10) ===
    ('splenic-lesion-incidental', 'Splenic Lesion (Incidental)', 'Abdomen', 'splenic', 'ACR White Paper'),
    ('gallbladder-polyp', 'Gallbladder Polyp Management', 'Abdomen', 'hepatobiliary', 'European Guidelines'),
    ('mediastinal-lymph-node', 'Mediastinal Lymph Node (Incidental)', 'Thorax', 'mediastinal', 'ACR White Paper 2020'),
    ('ti-rads-calculator', 'ACR TI-RADS Point Calculator', 'Head and Neck', 'thyroid', 'ACR TI-RADS 2017'),
    ('pirads-calculator', 'PI-RADS Zone-Based Calculator', 'Pelvis', 'prostate', 'PI-RADS v2.1'),
    ('lirads-calculator', 'LI-RADS Feature Calculator', 'Abdomen', 'hepatic', 'ACR LI-RADS v2018'),
    ('bosniak-calculator', 'Bosniak Feature Calculator (v2019)', 'Abdomen', 'renal', 'Bosniak v2019'),
    ('ct-severity-index-calc', 'CT Severity Index Calculator (Pancreatitis)', 'Abdomen', 'pancreatic', 'Balthazar CTSI'),
    ('recist-calculator', 'RECIST 1.1 Calculator', 'Multisystem', 'oncology', 'RECIST 1.1 2009'),
    ('aorta-diameter-reference', 'Aorta Diameter Reference Values', 'Cardiovascular', 'vascular', 'Age/Sex-Adjusted Normals'),
    # === PHASE 3: Specialist (10) ===
    ('o-rads-calculator', 'O-RADS Calculator (Ovarian US)', 'Pelvis', 'ovarian', 'ACR O-RADS US v2022'),
    ('cad-rads-calculator', 'CAD-RADS Calculator', 'Cardiovascular', 'cardiac', 'CAD-RADS 2.0 2022'),
    ('deauville-calculator', 'Deauville Score Calculator', 'Multisystem', 'oncology', 'Deauville 5-Point Scale'),
    ('child-pugh-calculator', 'Child-Pugh Score Calculator', 'Abdomen', 'hepatic', 'Child-Pugh Classification'),
    ('meld-calculator', 'MELD Score Calculator', 'Abdomen', 'hepatic', 'MELD Score'),
    ('ct-dose-calculator', 'CT Radiation Dose Calculator (DLP to mSv)', 'Multisystem', 'dose', 'ICRP/NRPB Conversion Factors'),
    ('lymph-node-size-reference', 'Lymph Node Size Reference (by Station)', 'Multisystem', 'reference', 'Short Axis Thresholds'),
    ('cbd-diameter-reference', 'CBD Diameter Reference', 'Abdomen', 'hepatobiliary', 'Age-Adjusted CBD Normals'),
    ('ovarian-volume-calculator', 'Ovarian Volume Calculator', 'Pelvis', 'ovarian', 'Ellipsoid Formula'),
    ('thyroid-volume-calculator', 'Thyroid Volume Calculator', 'Head and Neck', 'thyroid', 'Ellipsoid Per Lobe'),
]


def generate_and_sync(slug, finding_name, body_section, category, guideline_source=''):
    """Generate a radiology tool via Claude API and save to Neon."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    print(f"\n{'='*60}")
    print(f"Radiology Tool Generator")
    print(f"{'='*60}")
    print(f"Slug: {slug}")
    print(f"Finding: {finding_name}")
    print(f"Body Section: {body_section}")
    print(f"Category: {category}")
    print(f"Guideline: {guideline_source}")
    print(f"{'='*60}\n")

    print("[1/2] Generating tool with RadInsight Intelligence...")
    print("  Calling Claude API (this takes 60-120 seconds)...")

    from app import app
    from clinical_tool_generator import generate_clinical_tool

    with app.app_context():
        result = generate_clinical_tool(
            topic=finding_name,
            mode='full_tool',
            context={
                'tool_type': 'incidental_finding',
                'category': category,
                'body_section': body_section,
                'guideline_source': guideline_source,
            },
        )

    calculator_html = result.get('html', '')
    algorithm_html = result.get('algorithm_html', '')
    model = result.get('model', 'unknown')
    token_count = result.get('token_count', 0)

    if not calculator_html or len(calculator_html) < 500:
        raise ValueError(f"Generated HTML too short ({len(calculator_html)} chars)")

    print(f"  Calculator HTML: {len(calculator_html):,} chars")
    print(f"  Algorithm HTML: {len(algorithm_html):,} chars")
    print(f"  Model: {model}, Tokens: {token_count}")

    print("\n[2/2] Syncing to Neon (production DB)...")

    engine = create_engine(NEON_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    existing = session.execute(
        text("SELECT id FROM incidental_finding_calculator WHERE slug = :slug"),
        {'slug': slug}
    ).fetchone()

    params = {
        'slug': slug,
        'finding_name': finding_name,
        'calculator_html': calculator_html,
        'algorithm_html': algorithm_html,
        'body_section': body_section,
        'category': category,
        'guideline_source': guideline_source,
        'is_available': True,
        'generation_model': model,
    }

    if existing:
        session.execute(text("""
            UPDATE incidental_finding_calculator SET
                finding_name = :finding_name, calculator_html = :calculator_html,
                algorithm_html = :algorithm_html, body_section = :body_section,
                category = :category, guideline_source = :guideline_source,
                is_available = :is_available, generation_model = :generation_model,
                generated_at = NOW()
            WHERE slug = :slug
        """), params)
        print(f"  Updated existing record in Neon")
    else:
        session.execute(text("""
            INSERT INTO incidental_finding_calculator
            (slug, finding_name, calculator_html, algorithm_html, body_section, category,
             guideline_source, is_available, generation_model, generated_at, created_at)
            VALUES (:slug, :finding_name, :calculator_html, :algorithm_html, :body_section, :category,
                    :guideline_source, :is_available, :generation_model, NOW(), NOW())
        """), params)
        print(f"  Inserted new record in Neon")

    session.commit()
    session.close()
    print(f"\n  SUCCESS - radiology tool: {slug}")


def batch_generate(skip_existing=True, only_slugs=None, phase=None):
    """Generate all tools in BATCH_LIST sequentially."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    existing_slugs = set()
    if skip_existing:
        engine = create_engine(NEON_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        rows = session.execute(text("SELECT slug FROM incidental_finding_calculator")).fetchall()
        existing_slugs = {r[0] for r in rows}
        session.close()

    phase_ranges = {1: (0, 10), 2: (10, 20), 3: (20, 30)}

    todo = []
    for i, (slug, name, body, cat, guide) in enumerate(BATCH_LIST):
        if phase and phase in phase_ranges:
            start, end = phase_ranges[phase]
            if i < start or i >= end:
                continue
        if only_slugs and slug not in only_slugs:
            continue
        if slug in existing_slugs:
            print(f"  SKIP {slug} (already exists)")
            continue
        todo.append((slug, name, body, cat, guide))

    if not todo:
        print("\nNothing to generate - all tools already exist.")
        return

    print(f"\n{'='*60}")
    print(f"BATCH Radiology Tool Generation")
    print(f"{'='*60}")
    print(f"Total to generate: {len(todo)}")
    print(f"Estimated cost: ~${len(todo) * 0.24:.2f}")
    print(f"Estimated time: ~{len(todo) * 1}-{len(todo) * 2} minutes")
    print(f"{'='*60}")
    for i, (slug, name, body, cat, _) in enumerate(todo, 1):
        print(f"  {i:2d}. {slug:35s} | {name:40s} | {cat:15s} | {body}")
    print(f"{'='*60}\n")

    results = {'success': [], 'failed': []}
    start_time = time.time()

    for i, (slug, name, body, cat, guide) in enumerate(todo, 1):
        print(f"\n[{i}/{len(todo)}] Generating: {name} ({slug})")
        print(f"{'-'*50}")
        t0 = time.time()
        success = False
        for attempt in range(3):
            try:
                if attempt > 0:
                    wait = 60 * attempt
                    print(f"  Retry {attempt}/2 — waiting {wait}s for rate limit...")
                    time.sleep(wait)
                generate_and_sync(slug, name, body, cat, guide)
                elapsed = time.time() - t0
                results['success'].append((slug, elapsed))
                print(f"  Completed in {elapsed:.0f}s")
                success = True
                break
            except Exception as e:
                if '429' in str(e) or 'rate_limit' in str(e):
                    print(f"  Rate limited (attempt {attempt+1}/3)")
                    continue
                elapsed = time.time() - t0
                results['failed'].append((slug, str(e)))
                print(f"  FAILED after {elapsed:.0f}s: {e}")
                break
        if not success and slug not in [s for s, _ in results['failed']]:
            results['failed'].append((slug, 'Rate limit exceeded after 3 retries'))

        if i < len(todo):
            time.sleep(5)

    total_time = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"BATCH GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"Total time: {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"Success: {len(results['success'])}")
    print(f"Failed:  {len(results['failed'])}")

    if results['success']:
        print(f"\nSuccessful:")
        for slug, elapsed in results['success']:
            print(f"  {slug:35s} ({elapsed:.0f}s)")
    if results['failed']:
        print(f"\nFailed:")
        for slug, error in results['failed']:
            print(f"  {slug:35s} - {error[:80]}")
    print()


def list_status():
    """Show all tools and whether they exist in Neon."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(NEON_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    rows = session.execute(text(
        "SELECT slug, LENGTH(calculator_html) as len FROM incidental_finding_calculator"
    )).fetchall()
    existing = {r[0]: r[1] for r in rows}
    session.close()

    phases = {0: 'Phase 1 (ACR White Papers + Scoring)', 10: 'Phase 2 (Expanded IF + Scoring)', 20: 'Phase 3 (Specialist)'}
    print(f"\n{'Slug':35s} | {'Finding':40s} | {'Category':15s} | {'Section':15s} | Status")
    print(f"{'-'*145}")

    pending_count = 0
    for i, (slug, name, body, cat, _) in enumerate(BATCH_LIST):
        if i in phases:
            print(f"\n  --- {phases[i]} ---")
        if slug in existing:
            status = f"EXISTS ({existing[slug]:,} chars)"
        else:
            status = "PENDING"
            pending_count += 1
        print(f"{slug:35s} | {name:40s} | {cat:15s} | {body:15s} | {status}")

    print(f"\nTotal: {len(BATCH_LIST)} | Existing: {len(BATCH_LIST) - pending_count} | Pending: {pending_count}")
    print(f"Estimated cost for pending: ~${pending_count * 0.24:.2f}\n")


def main():
    parser = argparse.ArgumentParser(description='Batch Radiology Tool Generator')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    single = subparsers.add_parser('generate', help='Generate a single tool')
    single.add_argument('slug', help='URL slug')
    single.add_argument('finding_name', help='Finding/tool name')
    single.add_argument('body_section', help='Body section')
    single.add_argument('category', help='Category')
    single.add_argument('--guideline', '-g', default='', help='Guideline source')

    batch = subparsers.add_parser('batch', help='Batch generate all tools')
    batch.add_argument('--include-existing', action='store_true', help='Regenerate existing')
    batch.add_argument('--only', nargs='+', help='Only specific slugs')
    batch.add_argument('--phase', type=int, choices=[1, 2, 3], help='Only generate specific phase')

    subparsers.add_parser('list', help='List all tools and their status')

    args = parser.parse_args()

    if args.command == 'generate':
        generate_and_sync(args.slug, args.finding_name, args.body_section, args.category, getattr(args, 'guideline', ''))
    elif args.command == 'batch':
        batch_generate(
            skip_existing=not args.include_existing,
            only_slugs=set(args.only) if args.only else None,
            phase=args.phase,
        )
    elif args.command == 'list':
        list_status()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
