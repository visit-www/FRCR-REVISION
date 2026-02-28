#!/usr/bin/env python3
"""
Batch Reporting Algorithm Generator
====================================
Generates interactive reporting algorithm decision trees and syncs to Neon production DB.
Modelled on generate_tnm_calculator.py batch infrastructure.

Keyword: RADINSIGHTS-CONTENT-BATCH-2026

Usage:
    PYTHONUNBUFFERED=1 python scripts/batch_algorithms.py list
    PYTHONUNBUFFERED=1 python scripts/batch_algorithms.py batch
    PYTHONUNBUFFERED=1 python scripts/batch_algorithms.py batch --phase 1
    PYTHONUNBUFFERED=1 python scripts/batch_algorithms.py generate bi-rads "BI-RADS Assessment Categories" scoring Breast
"""

import argparse
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

NEON_URL = os.getenv('DATABASE_URL') or os.getenv('NEON_URL') or \
    "postgresql://neondb_owner:npg_DsKL8RFtw2zI@ep-frosty-sound-ahg70oqy-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"

# (slug, title, category, body_section, source_citation)
# Categories: emergency, routine, oncology, trauma, grading, scoring
BATCH_LIST = [
    # === PHASE 1: RADS Family (5) ===
    ('bi-rads', 'BI-RADS Assessment Categories', 'scoring', 'Breast', 'ACR BI-RADS 5th Edition'),
    ('li-rads', 'LI-RADS (Liver Imaging)', 'scoring', 'Abdomen', 'ACR LI-RADS v2018'),
    ('pi-rads', 'PI-RADS v2.1 (Prostate MRI)', 'scoring', 'Pelvis', 'PI-RADS v2.1 2019'),
    ('ti-rads', 'ACR TI-RADS (Thyroid Ultrasound)', 'scoring', 'Head and Neck', 'ACR TI-RADS 2017'),
    ('lung-rads', 'Lung-RADS v2022 (Lung Screening CT)', 'scoring', 'Thorax', 'ACR Lung-RADS v2022'),
    # === PHASE 1: Emergency/Trauma (5) ===
    ('fleischner-criteria', 'Fleischner Society Criteria (Pulmonary Nodules 2017)', 'emergency', 'Thorax', 'Fleischner Society 2017'),
    ('aspects-score', 'ASPECTS (Alberta Stroke Programme Early CT Score)', 'emergency', 'Brain', 'ASPECTS 2000'),
    ('aast-spleen', 'AAST Organ Injury Scale - Spleen (2018)', 'trauma', 'Abdomen', 'AAST 2018 Revision'),
    ('aast-liver', 'AAST Organ Injury Scale - Liver (2018)', 'trauma', 'Abdomen', 'AAST 2018 Revision'),
    ('aast-kidney', 'AAST Organ Injury Scale - Kidney (2018)', 'trauma', 'Abdomen', 'AAST 2018 Revision'),
    # === PHASE 1: Routine/Classification (5) ===
    ('bosniak-classification', 'Bosniak Classification v2019 (Renal Cysts)', 'routine', 'Abdomen', 'Bosniak Classification v2019'),
    ('ct-severity-index-pancreatitis', 'CT Severity Index / Balthazar (Pancreatitis)', 'scoring', 'Abdomen', 'Balthazar CT Severity Index'),
    ('fazekas-scale', 'Fazekas Scale (White Matter Disease)', 'scoring', 'Brain', 'Fazekas Scale 1987'),
    ('scheltens-mta-score', 'Scheltens MTA Score (Medial Temporal Atrophy)', 'scoring', 'Brain', 'Scheltens MTA Scale'),
    ('recist-1-1', 'RECIST 1.1 (Tumour Response Assessment)', 'oncology', 'Multisystem', 'RECIST 1.1 2009'),
    # === PHASE 2: RADS Completion (3) ===
    ('o-rads', 'O-RADS (Ovarian/Adnexal)', 'scoring', 'Pelvis', 'ACR O-RADS US v2022, MRI 2020'),
    ('cad-rads', 'CAD-RADS 2.0 (Coronary CTA)', 'scoring', 'Cardiovascular', 'CAD-RADS 2.0 2022'),
    ('c-rads', 'C-RADS (CT Colonography)', 'scoring', 'Abdomen', 'ACR C-RADS 2005'),
    # === PHASE 2: Neuro/Brain (6) ===
    ('fisher-scale', 'Fisher Scale / Modified Fisher (SAH)', 'emergency', 'Brain', 'Fisher Scale 1980'),
    ('marshall-ct-classification', 'Marshall CT Classification (TBI)', 'emergency', 'Brain', 'Marshall CT Classification 1991'),
    ('gca-scale', 'GCA Scale (Global Cortical Atrophy, Pasquier)', 'scoring', 'Brain', 'Pasquier GCA Scale'),
    ('koedam-pa-score', 'Koedam Posterior Atrophy Score', 'scoring', 'Brain', 'Koedam PA Score 2011'),
    ('evans-index', 'Evans Index (Hydrocephalus)', 'routine', 'Brain', 'Evans Index'),
    ('spetzler-martin', 'Spetzler-Martin AVM Grading', 'grading', 'Brain', 'Spetzler-Martin 1986'),
    # === PHASE 2: Abdominal (3) ===
    ('modified-atlanta-pancreatitis', 'Modified Atlanta Classification (Pancreatitis)', 'emergency', 'Abdomen', 'Revised Atlanta Classification 2012'),
    ('couinaud-liver-segments', 'Couinaud Liver Segment Anatomy', 'routine', 'Abdomen', 'Couinaud Classification'),
    ('sfu-hydronephrosis', 'SFU Hydronephrosis Grading', 'routine', 'Abdomen', 'Society of Fetal Urology'),
    # === PHASE 2: Trauma (5) ===
    ('aast-pancreas', 'AAST Organ Injury Scale - Pancreas', 'trauma', 'Abdomen', 'AAST OIS'),
    ('aast-bowel-mesentery', 'AAST Organ Injury Scale - Bowel/Mesentery', 'trauma', 'Abdomen', 'AAST OIS'),
    ('aast-bladder', 'AAST Organ Injury Scale - Bladder', 'trauma', 'Pelvis', 'AAST OIS'),
    ('young-burgess-pelvic', 'Young-Burgess Classification (Pelvic Fractures)', 'trauma', 'Pelvis', 'Young-Burgess 1986'),
    ('tlics', 'TLICS (Thoracolumbar Injury Classification)', 'trauma', 'Spine', 'TLICS Score'),
    # === PHASE 2: MSK/Orthopaedic (8) ===
    ('salter-harris', 'Salter-Harris Classification (Physeal Fractures)', 'grading', 'Musculoskeletal', 'Salter-Harris 1963'),
    ('garden-classification', 'Garden Classification (Femoral Neck Fractures)', 'grading', 'Musculoskeletal', 'Garden 1961'),
    ('weber-ankle', 'Weber Classification (Ankle Fractures)', 'grading', 'Musculoskeletal', 'Weber/Danis-Weber'),
    ('neer-proximal-humerus', 'Neer Classification (Proximal Humerus)', 'grading', 'Musculoskeletal', 'Neer 1970'),
    ('schatzker-tibial-plateau', 'Schatzker Classification (Tibial Plateau)', 'grading', 'Musculoskeletal', 'Schatzker 1979'),
    ('mason-radial-head', 'Mason Classification (Radial Head)', 'grading', 'Musculoskeletal', 'Mason 1954'),
    ('kellgren-lawrence', 'Kellgren-Lawrence (Osteoarthritis Grading)', 'grading', 'Musculoskeletal', 'Kellgren-Lawrence 1957'),
    ('modic-changes', 'Modic Changes (Endplate Degeneration)', 'grading', 'Spine', 'Modic 1988'),
    # === PHASE 3: Oncology (5) ===
    ('deauville-criteria', 'Deauville Criteria (Lymphoma PET-CT)', 'oncology', 'Multisystem', 'Deauville 5-Point Scale'),
    ('irecist', 'iRECIST (Immunotherapy Response)', 'oncology', 'Multisystem', 'iRECIST 2017'),
    ('mrecist', 'mRECIST (HCC Response)', 'oncology', 'Abdomen', 'mRECIST 2010'),
    ('rano-criteria', 'RANO Criteria (Brain Tumour Response)', 'oncology', 'Brain', 'RANO 2010'),
    ('lugano-classification', 'Lugano Classification (Lymphoma Staging)', 'oncology', 'Multisystem', 'Lugano 2014'),
    # === PHASE 3: Neuro (3) ===
    ('hunt-hess', 'Hunt and Hess Scale (SAH)', 'grading', 'Brain', 'Hunt and Hess 1968'),
    ('wfns-sah', 'WFNS Scale (SAH)', 'grading', 'Brain', 'WFNS 1988'),
    ('rotterdam-ct-score', 'Rotterdam CT Score (TBI)', 'emergency', 'Brain', 'Rotterdam 2005'),
    # === PHASE 3: Vascular (3) ===
    ('stanford-dissection', 'Stanford Classification (Aortic Dissection)', 'emergency', 'Cardiovascular', 'Stanford Classification'),
    ('debakey-dissection', 'DeBakey Classification (Aortic Dissection)', 'emergency', 'Cardiovascular', 'DeBakey Classification'),
    ('lake-louise-myocarditis', 'Lake Louise Criteria (Myocarditis CMR)', 'routine', 'Cardiovascular', 'Lake Louise Criteria 2018'),
    # === PHASE 3: MSK continued (6) ===
    ('rockwood-acj', 'Rockwood Classification (ACJ Injuries)', 'grading', 'Musculoskeletal', 'Rockwood 1984'),
    ('sanders-calcaneal', 'Sanders Classification (Calcaneal CT)', 'grading', 'Musculoskeletal', 'Sanders 1993'),
    ('pfirrmann-disc', 'Pfirrmann Grading (Disc Degeneration MRI)', 'grading', 'Spine', 'Pfirrmann 2001'),
    ('hawkins-talar-neck', 'Hawkins Classification (Talar Neck Fractures)', 'grading', 'Musculoskeletal', 'Hawkins 1970'),
    ('gustilo-anderson', 'Gustilo-Anderson (Open Fractures)', 'grading', 'Musculoskeletal', 'Gustilo-Anderson 1976'),
    ('cobb-angle', 'Cobb Angle Measurement (Scoliosis)', 'scoring', 'Spine', 'Cobb Method'),
    # === PHASE 3: Breast/GU (3) ===
    ('bi-rads-density', 'BI-RADS Breast Density (a-d)', 'scoring', 'Breast', 'ACR BI-RADS 5th Edition'),
    ('parks-fistula', 'Parks Classification (Perianal Fistula)', 'routine', 'Pelvis', 'Parks Classification 1976'),
    ('figo-staging', 'FIGO Staging (Cervical/Endometrial/Ovarian)', 'oncology', 'Pelvis', 'FIGO 2018'),
    # === PHASE 3: Hepatic Scoring (moved from tools) (2) ===
    ('child-pugh', 'Child-Pugh Score (Liver Cirrhosis)', 'scoring', 'Abdomen', 'Child-Pugh Classification'),
    ('meld-score', 'MELD Score (Liver Disease Severity)', 'scoring', 'Abdomen', 'MELD Score'),
]


def generate_and_sync(slug, title, category, body_section, source_citation=''):
    """Generate a reporting algorithm via Claude API and save to Neon."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    print(f"\n{'='*60}")
    print(f"Reporting Algorithm Generator")
    print(f"{'='*60}")
    print(f"Slug: {slug}")
    print(f"Title: {title}")
    print(f"Category: {category}")
    print(f"Body Section: {body_section}")
    print(f"Source: {source_citation}")
    print(f"{'='*60}\n")

    print("[1/2] Generating algorithm with RadInsight Intelligence...")
    print("  Calling Claude API (this takes 60-120 seconds)...")

    from app import app
    from clinical_tool_generator import generate_clinical_tool

    with app.app_context():
        result = generate_clinical_tool(
            topic=title,
            mode='full_tool',
            context={
                'tool_type': 'reporting_algorithm',
                'category': category,
                'body_section': body_section,
                'source_citation': source_citation,
            },
        )

    template_html = result.get('html', '')
    algorithm_html = result.get('algorithm_html', '')
    model = result.get('model', 'unknown')
    token_count = result.get('token_count', 0)

    if not template_html or len(template_html) < 500:
        raise ValueError(f"Generated HTML too short ({len(template_html)} chars)")

    print(f"  Template HTML: {len(template_html):,} chars")
    print(f"  Algorithm HTML: {len(algorithm_html):,} chars")
    print(f"  Model: {model}, Tokens: {token_count}")

    print("\n[2/2] Syncing to Neon (production DB)...")

    engine = create_engine(NEON_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    existing = session.execute(
        text("SELECT id FROM reporting_algorithm WHERE slug = :slug"),
        {'slug': slug}
    ).fetchone()

    params = {
        'slug': slug,
        'title': title,
        'template_html': template_html,
        'algorithm_html': algorithm_html,
        'category': category,
        'body_section': body_section,
        'source_citation': source_citation,
        'origin': 'admin',
        'is_ai_generated': True,
        'is_available': True,
        'generation_model': model,
    }

    if existing:
        session.execute(text("""
            UPDATE reporting_algorithm SET
                title = :title, template_html = :template_html,
                algorithm_html = :algorithm_html, category = :category,
                body_section = :body_section, source_citation = :source_citation,
                origin = :origin, is_ai_generated = :is_ai_generated,
                is_available = :is_available, generation_model = :generation_model,
                generated_at = NOW()
            WHERE slug = :slug
        """), params)
        print(f"  Updated existing record in Neon")
    else:
        session.execute(text("""
            INSERT INTO reporting_algorithm
            (slug, title, template_html, algorithm_html, category, body_section,
             source_citation, origin, is_ai_generated, is_available, generation_model,
             generated_at, created_at, updated_at)
            VALUES (:slug, :title, :template_html, :algorithm_html, :category, :body_section,
                    :source_citation, :origin, :is_ai_generated, :is_available, :generation_model,
                    NOW(), NOW(), NOW())
        """), params)
        print(f"  Inserted new record in Neon")

    session.commit()
    session.close()
    print(f"\n  SUCCESS - reporting algorithm: {slug}")


def batch_generate(skip_existing=True, only_slugs=None, phase=None):
    """Generate all algorithms in BATCH_LIST sequentially."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    existing_slugs = set()
    if skip_existing:
        engine = create_engine(NEON_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        rows = session.execute(text("SELECT slug FROM reporting_algorithm WHERE origin = 'admin'")).fetchall()
        existing_slugs = {r[0] for r in rows}
        session.close()

    phase_ranges = {1: (0, 15), 2: (15, 40), 3: (40, 62)}

    todo = []
    for i, (slug, title, category, body_section, source) in enumerate(BATCH_LIST):
        if phase and phase in phase_ranges:
            start, end = phase_ranges[phase]
            if i < start or i >= end:
                continue
        if only_slugs and slug not in only_slugs:
            continue
        if slug in existing_slugs:
            print(f"  SKIP {slug} (already exists)")
            continue
        todo.append((slug, title, category, body_section, source))

    if not todo:
        print("\nNothing to generate - all algorithms already exist.")
        return

    print(f"\n{'='*60}")
    print(f"BATCH Reporting Algorithm Generation")
    print(f"{'='*60}")
    print(f"Total to generate: {len(todo)}")
    print(f"Estimated cost: ~${len(todo) * 0.24:.2f}")
    print(f"Estimated time: ~{len(todo) * 1}-{len(todo) * 2} minutes")
    print(f"{'='*60}")
    for i, (slug, title, category, body_section, _) in enumerate(todo, 1):
        print(f"  {i:2d}. {slug:35s} | {title:45s} | {category:10s} | {body_section}")
    print(f"{'='*60}\n")

    results = {'success': [], 'failed': []}
    start_time = time.time()

    for i, (slug, title, category, body_section, source) in enumerate(todo, 1):
        print(f"\n[{i}/{len(todo)}] Generating: {title} ({slug})")
        print(f"{'-'*50}")
        t0 = time.time()
        success = False
        for attempt in range(3):
            try:
                if attempt > 0:
                    wait = 60 * attempt
                    print(f"  Retry {attempt}/2 — waiting {wait}s for rate limit...")
                    time.sleep(wait)
                generate_and_sync(slug, title, category, body_section, source)
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
    """Show all algorithms and whether they exist in Neon."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(NEON_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    rows = session.execute(text(
        "SELECT slug, LENGTH(template_html) as len FROM reporting_algorithm WHERE origin = 'admin'"
    )).fetchall()
    existing = {r[0]: r[1] for r in rows}
    session.close()

    phases = {0: 'Phase 1 (RADS + Emergency + Routine)', 15: 'Phase 2 (Neuro + Trauma + MSK)', 40: 'Phase 3 (Oncology + Specialist)'}
    print(f"\n{'Slug':35s} | {'Title':45s} | {'Category':10s} | {'Section':15s} | Status")
    print(f"{'-'*150}")

    pending_count = 0
    for i, (slug, title, category, body_section, _) in enumerate(BATCH_LIST):
        if i in phases:
            print(f"\n  --- {phases[i]} ---")
        if slug in existing:
            status = f"EXISTS ({existing[slug]:,} chars)"
        else:
            status = "PENDING"
            pending_count += 1
        print(f"{slug:35s} | {title:45s} | {category:10s} | {body_section:15s} | {status}")

    print(f"\nTotal: {len(BATCH_LIST)} | Existing: {len(BATCH_LIST) - pending_count} | Pending: {pending_count}")
    print(f"Estimated cost for pending: ~${pending_count * 0.24:.2f}\n")


def main():
    parser = argparse.ArgumentParser(description='Batch Reporting Algorithm Generator')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    single = subparsers.add_parser('generate', help='Generate a single algorithm')
    single.add_argument('slug', help='URL slug')
    single.add_argument('title', help='Algorithm title')
    single.add_argument('category', help='Category (emergency, routine, oncology, trauma, grading, scoring)')
    single.add_argument('body_section', help='Body section')
    single.add_argument('--source', '-s', default='', help='Source citation')

    batch = subparsers.add_parser('batch', help='Batch generate all algorithms')
    batch.add_argument('--include-existing', action='store_true', help='Regenerate existing')
    batch.add_argument('--only', nargs='+', help='Only specific slugs')
    batch.add_argument('--phase', type=int, choices=[1, 2, 3], help='Only generate specific phase')

    subparsers.add_parser('list', help='List all algorithms and their status')

    args = parser.parse_args()

    if args.command == 'generate':
        generate_and_sync(args.slug, args.title, args.category, args.body_section, getattr(args, 'source', ''))
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
