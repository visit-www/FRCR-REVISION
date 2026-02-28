#!/usr/bin/env python3
"""
Batch Radiology Template Generator
===================================
Generates PACS-ready radiology report templates and syncs to Neon production DB.
Modelled on generate_tnm_calculator.py batch infrastructure.

Keyword: RADINSIGHTS-CONTENT-BATCH-2026

Usage:
    PYTHONUNBUFFERED=1 python scripts/batch_templates.py list
    PYTHONUNBUFFERED=1 python scripts/batch_templates.py batch
    PYTHONUNBUFFERED=1 python scripts/batch_templates.py generate ct-head-acute "CT Head (acute, non-contrast)" CT Brain
"""

import argparse
import os
import sys
import time
import re
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

NEON_URL = os.getenv('DATABASE_URL') or os.getenv('NEON_URL') or \
    "postgresql://neondb_owner:npg_DsKL8RFtw2zI@ep-frosty-sound-ahg70oqy-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"

# (slug, title, modality, body_section)
BATCH_LIST = [
    # === PHASE 1: Emergency / On-Call (10) ===
    ('ct-head-acute', 'CT Head (acute, non-contrast)', 'CT', 'Brain'),
    ('ctpa-pulmonary-angiogram', 'CTPA (Pulmonary Angiogram)', 'CTA', 'Thorax'),
    ('ct-abdomen-pelvis-acute', 'CT Abdomen/Pelvis (acute abdomen)', 'CT', 'Abdomen'),
    ('ct-cervical-spine-trauma', 'CT Cervical Spine (trauma)', 'CT', 'Spine'),
    ('ct-whole-body-polytrauma', 'CT Whole Body (polytrauma)', 'CT', 'Multisystem'),
    ('ct-aorta-dissection', 'CT Aorta (dissection/aneurysm)', 'CTA', 'Cardiovascular'),
    ('ct-kub-renal-colic', 'CT KUB (renal colic)', 'CT', 'Abdomen'),
    ('ct-head-stroke-cta', 'CT Head Stroke (CTA Circle of Willis)', 'CTA', 'Brain'),
    ('chest-xray-normal-adult', 'Chest X-ray (normal adult)', 'XR', 'Thorax'),
    ('chest-xray-itu', 'Chest X-ray (ITU/ICU)', 'XR', 'Thorax'),
    # === PHASE 1: High-Volume Routine (10) ===
    ('mri-lumbar-spine', 'MRI Lumbar Spine', 'MRI', 'Spine'),
    ('mri-brain-routine', 'MRI Brain (routine)', 'MRI', 'Brain'),
    ('mri-knee', 'MRI Knee', 'MRI', 'Musculoskeletal'),
    ('ct-chest-routine', 'CT Chest (routine with contrast)', 'CT', 'Thorax'),
    ('us-abdomen-general', 'Ultrasound Abdomen (general)', 'US', 'Abdomen'),
    ('ct-abdomen-triple-phase-liver', 'CT Abdomen (triple phase liver)', 'CT', 'Abdomen'),
    ('mri-cervical-spine', 'MRI Cervical Spine', 'MRI', 'Spine'),
    ('ct-cap-oncology-staging', 'CT Chest/Abdomen/Pelvis (oncology staging)', 'CT', 'Multisystem'),
    ('ct-cap-oncology-followup', 'CT Chest/Abdomen/Pelvis (oncology follow-up RECIST)', 'CT', 'Multisystem'),
    ('us-renal', 'Ultrasound Renal', 'US', 'Abdomen'),
    # === PHASE 2: Subspecialty (25) ===
    ('ct-sinuses', 'CT Sinuses', 'CT', 'Head and Neck'),
    ('ct-neck-staging', 'CT Neck with contrast (staging)', 'CT', 'Head and Neck'),
    ('us-thyroid', 'Ultrasound Thyroid', 'US', 'Head and Neck'),
    ('us-neck-lumps', 'Ultrasound Neck lumps', 'US', 'Head and Neck'),
    ('mri-brain-epilepsy', 'MRI Brain (epilepsy protocol)', 'MRI', 'Brain'),
    ('mri-brain-dementia', 'MRI Brain (dementia/memory clinic)', 'MRI', 'Brain'),
    ('mri-brain-pituitary', 'MRI Brain (pituitary protocol)', 'MRI', 'Brain'),
    ('ct-thoracolumbar-spine-trauma', 'CT Thoracic/Lumbar Spine (trauma)', 'CT', 'Spine'),
    ('mri-whole-spine-metastatic', 'MRI Whole Spine (metastatic survey)', 'MRI', 'Spine'),
    ('ct-chest-hrct', 'CT Chest (HRCT - ILD)', 'CT', 'Thorax'),
    ('ct-abdomen-pancreatic', 'CT Abdomen (pancreatic protocol)', 'CT', 'Abdomen'),
    ('ct-abdomen-sbo', 'CT Abdomen (small bowel obstruction)', 'CT', 'Abdomen'),
    ('mri-liver-primovist', 'MRI Liver (hepatocyte-specific / Primovist)', 'MRI', 'Abdomen'),
    ('mri-mrcp', 'MRI MRCP', 'MRI', 'Abdomen'),
    ('mri-small-bowel-crohns', 'MRI Small Bowel (Crohn\'s / MR enterography)', 'MRI', 'Abdomen'),
    ('us-hepatobiliary', 'Ultrasound Hepatobiliary', 'US', 'Abdomen'),
    ('ct-pelvis-trauma', 'CT Pelvis (trauma)', 'CT', 'Pelvis'),
    ('mri-pelvis-rectal-staging', 'MRI Pelvis (rectal cancer staging)', 'MRI', 'Pelvis'),
    ('mri-prostate-pirads', 'MRI Prostate (mpMRI - PI-RADS)', 'MRI', 'Pelvis'),
    ('us-pelvis-gynae', 'Ultrasound Pelvis (gynaecological)', 'US', 'Pelvis'),
    ('mri-shoulder', 'MRI Shoulder', 'MRI', 'Musculoskeletal'),
    ('us-dvt-lower-limb', 'Ultrasound DVT (lower limb venous)', 'US', 'Cardiovascular'),
    ('us-carotid-doppler', 'Ultrasound Carotid Doppler', 'US', 'Cardiovascular'),
    ('mammography-screening', 'Mammography (screening - BI-RADS)', 'XR', 'Breast'),
    ('mammography-diagnostic', 'Mammography (diagnostic/symptomatic)', 'XR', 'Breast'),
    # === PHASE 3: Specialist (20) ===
    ('ct-temporal-bones', 'CT Temporal Bones', 'CT', 'Head and Neck'),
    ('mri-iams', 'MRI Internal Auditory Meati (IAMs)', 'MRI', 'Head and Neck'),
    ('mri-orbits', 'MRI Orbits', 'MRI', 'Head and Neck'),
    ('ct-venogram-cerebral', 'CT Venogram (cerebral)', 'CTV', 'Brain'),
    ('mri-brain-tumour-rano', 'MRI Brain (tumour surveillance - RANO)', 'MRI', 'Brain'),
    ('mri-spine-infection', 'MRI Spine (infection/discitis)', 'MRI', 'Spine'),
    ('ldct-lung-screening', 'LDCT Lung Screening (Lung-RADS)', 'CT', 'Thorax'),
    ('ct-mesenteric-angiogram', 'CT Mesenteric Angiogram', 'CTA', 'Abdomen'),
    ('mri-pancreas-cystic', 'MRI Pancreas (cystic lesions/IPMN)', 'MRI', 'Abdomen'),
    ('ct-colonography', 'CT Colonography', 'CT', 'Abdomen'),
    ('mri-pelvis-cervical-staging', 'MRI Pelvis (cervical cancer staging)', 'MRI', 'Pelvis'),
    ('mri-pelvis-anal-cancer', 'MRI Pelvis (anal cancer)', 'MRI', 'Pelvis'),
    ('mri-fistula-perianal', 'MRI Fistula (perianal - Parks)', 'MRI', 'Pelvis'),
    ('mri-hip', 'MRI Hip', 'MRI', 'Musculoskeletal'),
    ('mri-soft-tissue-mass', 'MRI Soft Tissue Mass', 'MRI', 'Musculoskeletal'),
    ('dexa-scan', 'DEXA Scan', 'DXA', 'Musculoskeletal'),
    ('ct-coronary-angiogram', 'CT Coronary Angiogram (CAD-RADS)', 'CTA', 'Cardiovascular'),
    ('cardiac-mri-routine', 'Cardiac MRI (routine)', 'MRI', 'Cardiovascular'),
    ('mri-breast', 'MRI Breast', 'MRI', 'Breast'),
    ('pet-ct-report', 'PET-CT Report (Deauville)', 'PET/CT', 'Multisystem'),
]


def generate_and_sync(slug, title, modality, body_section):
    """Generate a radiology template via Claude API and save to Neon."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    print(f"\n{'='*60}")
    print(f"Radiology Template Generator")
    print(f"{'='*60}")
    print(f"Slug: {slug}")
    print(f"Title: {title}")
    print(f"Modality: {modality}")
    print(f"Body Section: {body_section}")
    print(f"{'='*60}\n")

    # Generate via Claude API
    print("[1/2] Generating template with RadInsight Intelligence...")
    print("  Calling Claude API (this takes 30-60 seconds)...")

    from app import app
    from ai_smart_reporter import generate_radiology_template

    with app.app_context():
        result = generate_radiology_template(
            clinical_scenario=title,
            modality=modality,
            body_section=body_section,
        )

    template_text = result.get('template_text', '')
    model = result.get('model', 'unknown')
    token_count = result.get('token_count', 0)

    if not template_text or len(template_text) < 100:
        raise ValueError(f"Generated template too short ({len(template_text)} chars)")

    print(f"  Template text: {len(template_text):,} chars")
    print(f"  Model: {model}, Tokens: {token_count}")

    # Upsert into Neon
    print("\n[2/2] Syncing to Neon (production DB)...")

    engine = create_engine(NEON_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    existing = session.execute(
        text("SELECT id FROM radiology_template WHERE slug = :slug"),
        {'slug': slug}
    ).fetchone()

    params = {
        'slug': slug,
        'title': title,
        'template_text': template_text,
        'body_section': body_section,
        'origin': 'admin',
        'is_ai_generated': True,
        'is_available': True,
        'generation_model': model,
    }

    if existing:
        session.execute(text("""
            UPDATE radiology_template SET
                title = :title, template_text = :template_text,
                body_section = :body_section, origin = :origin,
                is_ai_generated = :is_ai_generated, is_available = :is_available,
                generation_model = :generation_model, generated_at = NOW()
            WHERE slug = :slug
        """), params)
        print(f"  Updated existing record in Neon")
    else:
        session.execute(text("""
            INSERT INTO radiology_template
            (slug, title, template_text, body_section, origin,
             is_ai_generated, is_available, generation_model, generated_at, created_at, updated_at)
            VALUES (:slug, :title, :template_text, :body_section, :origin,
                    :is_ai_generated, :is_available, :generation_model, NOW(), NOW(), NOW())
        """), params)
        print(f"  Inserted new record in Neon")

    session.commit()
    session.close()
    print(f"\n  SUCCESS - radiology template: {slug}")


def batch_generate(skip_existing=True, only_slugs=None, phase=None):
    """Generate all templates in BATCH_LIST sequentially."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    existing_slugs = set()
    if skip_existing:
        engine = create_engine(NEON_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        rows = session.execute(text("SELECT slug FROM radiology_template WHERE origin = 'admin'")).fetchall()
        existing_slugs = {r[0] for r in rows}
        session.close()

    # Phase filtering
    phase_ranges = {1: (0, 20), 2: (20, 45), 3: (45, 65)}

    todo = []
    for i, (slug, title, modality, body_section) in enumerate(BATCH_LIST):
        if phase and phase in phase_ranges:
            start, end = phase_ranges[phase]
            if i < start or i >= end:
                continue
        if only_slugs and slug not in only_slugs:
            continue
        if slug in existing_slugs:
            print(f"  SKIP {slug} (already exists)")
            continue
        todo.append((slug, title, modality, body_section))

    if not todo:
        print("\nNothing to generate - all templates already exist.")
        return

    print(f"\n{'='*60}")
    print(f"BATCH Radiology Template Generation")
    print(f"{'='*60}")
    print(f"Total to generate: {len(todo)}")
    print(f"Estimated cost: ~${len(todo) * 0.08:.2f}")
    print(f"Estimated time: ~{len(todo) * 0.5:.0f}-{len(todo) * 1:.0f} minutes")
    print(f"{'='*60}")
    for i, (slug, title, modality, body_section) in enumerate(todo, 1):
        print(f"  {i:2d}. {slug:35s} | {title:45s} | {modality:5s} | {body_section}")
    print(f"{'='*60}\n")

    results = {'success': [], 'failed': []}
    start_time = time.time()

    for i, (slug, title, modality, body_section) in enumerate(todo, 1):
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
                generate_and_sync(slug, title, modality, body_section)
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
    """Show all templates and whether they exist in Neon."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(NEON_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    rows = session.execute(text(
        "SELECT slug, LENGTH(template_text) as len FROM radiology_template WHERE origin = 'admin'"
    )).fetchall()
    existing = {r[0]: r[1] for r in rows}
    session.close()

    phases = {0: 'Phase 1', 20: 'Phase 2', 45: 'Phase 3'}
    print(f"\n{'Slug':35s} | {'Title':45s} | {'Modality':5s} | {'Section':15s} | Status")
    print(f"{'-'*140}")

    pending_count = 0
    for i, (slug, title, modality, body_section) in enumerate(BATCH_LIST):
        if i in phases:
            print(f"\n  --- {phases[i]} ---")
        if slug in existing:
            status = f"EXISTS ({existing[slug]:,} chars)"
        else:
            status = "PENDING"
            pending_count += 1
        print(f"{slug:35s} | {title:45s} | {modality:5s} | {body_section:15s} | {status}")

    print(f"\nTotal: {len(BATCH_LIST)} | Existing: {len(BATCH_LIST) - pending_count} | Pending: {pending_count}")
    print(f"Estimated cost for pending: ~${pending_count * 0.08:.2f}\n")


def main():
    parser = argparse.ArgumentParser(description='Batch Radiology Template Generator')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    single = subparsers.add_parser('generate', help='Generate a single template')
    single.add_argument('slug', help='URL slug')
    single.add_argument('title', help='Template title')
    single.add_argument('modality', help='Imaging modality (CT, MRI, US, XR, etc.)')
    single.add_argument('body_section', help='Body section')

    batch = subparsers.add_parser('batch', help='Batch generate all templates')
    batch.add_argument('--include-existing', action='store_true', help='Regenerate existing')
    batch.add_argument('--only', nargs='+', help='Only specific slugs')
    batch.add_argument('--phase', type=int, choices=[1, 2, 3], help='Only generate specific phase')

    subparsers.add_parser('list', help='List all templates and their status')

    args = parser.parse_args()

    if args.command == 'generate':
        generate_and_sync(args.slug, args.title, args.modality, args.body_section)
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
