#!/usr/bin/env python3
"""
TNM Calculator Generator Script

Generates a TNM calculator locally and syncs to both:
- Local SQLite (for development)
- Neon PostgreSQL (for production)

Usage:
    python scripts/generate_tnm_calculator.py <slug> "<cancer_name>" "<body_section>" [--notes "special notes"]

Examples:
    python scripts/generate_tnm_calculator.py larynx "Larynx" "Head and Neck"
    python scripts/generate_tnm_calculator.py breast "Breast" "Breast" --notes "Include prognostic staging with biomarkers"
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(project_root / '.env')

# Neon connection string (production DB)
NEON_URL = "postgresql://neondb_owner:npg_DsKL8RFtw2zI@ep-frosty-sound-ahg70oqy-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"

# Disease-specific defaults (same as in edit_case.html)
DISEASE_DEFAULTS = {
    'oropharynx': {
        'features': ['HPV+ Staging', 'HPV- Staging', 'ENE Criteria'],
        'notes': 'Include both HPV-positive (p16+) and HPV-negative staging pathways. HPV+ has different N staging with better prognosis.',
        'description': 'HPV+ and HPV- staging with detailed criteria'
    },
    'larynx': {
        'features': ['Subsites', 'Cartilage Invasion', 'Voice Preservation'],
        'notes': 'Cover all subsites: Glottis, Supraglottis, Subglottis. Emphasize cartilage invasion criteria (T3 vs T4).',
        'description': 'Glottic, supraglottic, and subglottic subsites'
    },
    'breast': {
        'features': ['Prognostic Staging', 'Biomarkers', 'Oncotype DX'],
        'notes': 'Include BOTH anatomic staging AND prognostic staging. Prognostic staging requires Grade, ER, PR, HER2.',
        'description': 'Anatomic and prognostic staging with biomarkers'
    },
    'lung': {
        'features': ['Size Cutoffs', 'Pleural Invasion', 'Separate Nodules'],
        'notes': 'Emphasize T size cutoffs: ≤1cm, >1-2cm, >2-3cm, etc. Include visceral pleura invasion.',
        'description': 'NSCLC staging with detailed size criteria'
    },
    'cervix-uteri': {
        'features': ['FIGO 2018', 'Nodal Staging', 'Parametrium'],
        'notes': 'FIGO 2018 staging includes imaging and pathology. Lymph node status incorporated (IIIC1/IIIC2).',
        'description': 'FIGO 2018 staging with nodal incorporation'
    },
    'prostate': {
        'features': ['PSA', 'Gleason Score', 'Grade Groups'],
        'notes': 'Include PSA levels, Gleason score and ISUP Grade Groups (1-5). Extraprostatic extension criteria.',
        'description': 'Prostate staging with Grade Groups'
    },
    'colon-and-rectum': {
        'features': ['Tumor Deposits', 'Circumferential Margin', 'MSI Status'],
        'notes': 'Include tumor deposits concept. Emphasize circumferential resection margin for rectal cancer.',
        'description': 'Colorectal staging with tumor deposits criteria'
    },
    'kidney': {
        'features': ['Size', 'Renal Vein', 'IVC Thrombus'],
        'notes': 'Size cutoffs: ≤4cm (T1a), >4-7cm (T1b), etc. Renal vein and IVC thrombus levels.',
        'description': 'RCC staging with vascular invasion levels'
    },
    'melanoma': {
        'features': ['Breslow Depth', 'Ulceration', 'Mitotic Rate'],
        'notes': 'Include Breslow depth thresholds. Ulceration as adverse feature. Satellite/in-transit metastases.',
        'description': 'Melanoma staging with Breslow depth'
    },
    'thyroid': {
        'features': ['Age Factor', 'Histology Variants', 'Anaplastic'],
        'notes': 'Differentiated (papillary/follicular): age <55 has only Stage I/II. Anaplastic: all T4.',
        'description': 'Age-based staging with histology variants'
    },
}


def get_defaults(slug):
    """Get disease-specific defaults or generic ones."""
    if slug in DISEASE_DEFAULTS:
        return DISEASE_DEFAULTS[slug]
    return {
        'features': [],
        'notes': '',
        'description': f'{slug.replace("-", " ").title()} cancer staging'
    }


def generate_and_sync(slug, cancer_name, body_section, special_notes=None, special_features=None, description=None):
    """Generate calculator locally and sync to Neon."""

    defaults = get_defaults(slug)

    # Use provided values or defaults
    if not special_notes:
        special_notes = defaults['notes']
    if not special_features:
        special_features = defaults['features']
    if not description:
        description = defaults['description']

    print(f"\n{'='*60}")
    print(f"TNM Calculator Generator")
    print(f"{'='*60}")
    print(f"Slug: {slug}")
    print(f"Cancer: {cancer_name}")
    print(f"Body Section: {body_section}")
    print(f"Description: {description}")
    print(f"Features: {special_features}")
    print(f"Notes: {special_notes[:80]}..." if len(special_notes) > 80 else f"Notes: {special_notes}")
    print(f"{'='*60}\n")

    # Step 1: Generate locally
    print("[1/4] Generating calculator with Claude AI...")

    from app import app, db
    from tnm_calculator.tnm_generator import generate_calculator_html, generate_algorithm_discussion, save_calculator_html_file
    from models import TNMCalculatorContent

    with app.app_context():
        # Check if exists locally
        existing = TNMCalculatorContent.query.filter_by(slug=slug).first()
        if existing:
            print(f"  ⚠ Calculator '{slug}' already exists locally. Regenerating...")
            # Delete existing
            db.session.delete(existing)
            db.session.commit()

        # Generate HTML
        print("  Generating calculator HTML (this takes 30-60 seconds)...")
        calculator_html = generate_calculator_html(
            cancer_name=cancer_name,
            body_section=body_section,
            special_notes=special_notes
        )
        print(f"  ✓ Calculator HTML: {len(calculator_html):,} chars")

        # Generate algorithm discussion
        print("  Generating algorithm discussion...")
        algorithm_html = generate_algorithm_discussion(
            cancer_name=cancer_name,
            body_section=body_section,
            special_notes=special_notes
        )
        print(f"  ✓ Algorithm HTML: {len(algorithm_html):,} chars")

        # Save HTML file
        print("\n[2/4] Saving HTML file...")
        file_path = save_calculator_html_file(slug, calculator_html)
        print(f"  ✓ Saved to: {file_path}")

        # Save to local SQLite
        print("\n[3/4] Saving to local SQLite...")
        from tnm_calculator.tnm_generator import get_claude_model
        content = TNMCalculatorContent(
            slug=slug,
            cancer_name=cancer_name,
            body_section=body_section,
            calculator_html=calculator_html,
            algorithm_discussion_html=algorithm_html,
            staging_system='AJCC 9th Edition',
            description=description,
            special_features=str(special_features),
            is_available=True,
            generation_model=get_claude_model(),
            generated_at=datetime.utcnow()
        )
        db.session.add(content)
        db.session.commit()
        print(f"  ✓ Saved to local DB (id: {content.id})")

    # Step 4: Sync to Neon
    print("\n[4/4] Syncing to Neon (production DB)...")

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    import json

    engine = create_engine(NEON_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Check if exists in Neon
    result = session.execute(
        text("SELECT id FROM tnm_calculator_content WHERE slug = :slug"),
        {'slug': slug}
    )
    existing_row = result.fetchone()

    features_json = json.dumps(special_features) if special_features else '[]'

    if existing_row:
        # Update existing
        session.execute(text("""
            UPDATE tnm_calculator_content SET
                cancer_name = :cancer_name,
                body_section = :body_section,
                calculator_html = :calculator_html,
                algorithm_discussion_html = :algorithm_html,
                staging_system = 'AJCC 9th Edition',
                description = :description,
                special_features = :special_features,
                is_available = true,
                generation_model = :model,
                generated_at = NOW()
            WHERE slug = :slug
        """), {
            'slug': slug,
            'cancer_name': cancer_name,
            'body_section': body_section,
            'calculator_html': calculator_html,
            'algorithm_html': algorithm_html,
            'description': description,
            'special_features': features_json,
            'model': os.environ.get('CLAUDE_MODEL', 'claude-sonnet-4-20250514')
        })
        print(f"  ✓ Updated existing record in Neon")
    else:
        # Insert new
        session.execute(text("""
            INSERT INTO tnm_calculator_content
            (slug, cancer_name, body_section, calculator_html, algorithm_discussion_html,
             staging_system, description, special_features, is_available, generation_model, generated_at, created_at)
            VALUES (:slug, :cancer_name, :body_section, :calculator_html, :algorithm_html,
                    'AJCC 9th Edition', :description, :special_features, true, :model, NOW(), NOW())
        """), {
            'slug': slug,
            'cancer_name': cancer_name,
            'body_section': body_section,
            'calculator_html': calculator_html,
            'algorithm_html': algorithm_html,
            'description': description,
            'special_features': features_json,
            'model': os.environ.get('CLAUDE_MODEL', 'claude-sonnet-4-20250514')
        })
        print(f"  ✓ Inserted new record in Neon")

    session.commit()

    # Verify
    result = session.execute(
        text("SELECT slug, LENGTH(calculator_html) as html_len FROM tnm_calculator_content WHERE slug = :slug"),
        {'slug': slug}
    )
    row = result.fetchone()
    print(f"  ✓ Verified: {row[0]} has {row[1]:,} chars in Neon")

    print(f"\n{'='*60}")
    print(f"✅ SUCCESS! Calculator generated and synced.")
    print(f"{'='*60}")
    print(f"\nNext steps:")
    print(f"1. Commit the HTML file: git add tnm_calculator/calculators/{slug}_calc.html")
    print(f"2. Push to deploy: git push")
    print(f"3. Access at: /tnm-calculator/{slug}")
    print()


def main():
    parser = argparse.ArgumentParser(description='Generate TNM Calculator and sync to Neon')
    parser.add_argument('slug', help='URL slug (e.g., larynx, breast)')
    parser.add_argument('cancer_name', help='Display name (e.g., "Larynx", "Breast")')
    parser.add_argument('body_section', help='Body section (e.g., "Head and Neck", "Thorax")')
    parser.add_argument('--notes', '-n', help='Special notes for AI generation')
    parser.add_argument('--features', '-f', nargs='+', help='Special features (space-separated)')
    parser.add_argument('--description', '-d', help='Brief description')

    args = parser.parse_args()

    generate_and_sync(
        slug=args.slug,
        cancer_name=args.cancer_name,
        body_section=args.body_section,
        special_notes=args.notes,
        special_features=args.features,
        description=args.description
    )


if __name__ == '__main__':
    main()
