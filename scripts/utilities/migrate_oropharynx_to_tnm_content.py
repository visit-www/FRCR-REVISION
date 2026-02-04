#!/usr/bin/env python3
"""
Migrate Oropharynx Algorithm Case (#34) to TNM Calculator Content Table

This script:
1. Reads the existing oropharynx calculator HTML file
2. Reads the algorithm case (#34) discussion from the database
3. Creates a TNMCalculatorContent record with both
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment
from dotenv import load_dotenv
load_dotenv(project_root / '.env')

# Import app (this initializes everything)
import app as flask_app
from models import db, Case, TNMCalculatorContent


def migrate_oropharynx():
    """Migrate oropharynx data to TNMCalculatorContent table."""

    # Read existing calculator HTML
    calc_html_path = project_root / 'tnm_calculator' / 'calculators' / 'oropharynx_calc.html'
    if not calc_html_path.exists():
        print(f"ERROR: Calculator HTML not found: {calc_html_path}")
        return False

    calculator_html = calc_html_path.read_text(encoding='utf-8')
    print(f"Read calculator HTML: {len(calculator_html)} chars")

    with flask_app.app.app_context():
        # Check if already exists
        existing = TNMCalculatorContent.query.filter_by(slug='oropharynx').first()
        if existing:
            print(f"WARNING: Oropharynx calculator already exists in database (ID: {existing.id})")
            update = input("Update existing record? (y/n): ").strip().lower()
            if update != 'y':
                print("Aborted.")
                return False

            # Update existing
            existing.calculator_html = calculator_html
            existing.updated_at = datetime.utcnow()
            db.session.commit()
            print(f"Updated existing record ID: {existing.id}")
            return True

        # Get algorithm discussion from case #34
        case = Case.query.get(34)
        algorithm_html = None
        if case:
            algorithm_html = case.discussion
            print(f"Found case #34: {case.diagnosis}")
            print(f"Algorithm HTML: {len(algorithm_html) if algorithm_html else 0} chars")
        else:
            print("WARNING: Case #34 not found - algorithm_html will be empty")

        # Create new TNMCalculatorContent record
        content = TNMCalculatorContent(
            slug='oropharynx',
            cancer_name='Oropharynx',
            body_section='Head and Neck',
            calculator_html=calculator_html,
            algorithm_discussion_html=algorithm_html,
            staging_system='AJCC 9th Edition',
            description='HPV+ and HPV- staging with detailed criteria',
            is_available=True,
            generation_model='manual/curated',
            generated_at=datetime.utcnow(),
            algorithm_case_id=34 if case else None,
            created_at=datetime.utcnow()
        )
        content.set_special_features(['HPV+ Staging', 'HPV- Staging'])

        db.session.add(content)
        db.session.commit()

        print(f"Created TNMCalculatorContent record ID: {content.id}")
        print(f"  Slug: {content.slug}")
        print(f"  Cancer Name: {content.cancer_name}")
        print(f"  Calculator HTML: {len(content.calculator_html) if content.calculator_html else 0} chars")
        print(f"  Algorithm HTML: {len(content.algorithm_discussion_html) if content.algorithm_discussion_html else 0} chars")
        print(f"  Linked Case ID: {content.algorithm_case_id}")

        return True


if __name__ == '__main__':
    print("=== Migrating Oropharynx to TNM Calculator Content Table ===")
    print()

    success = migrate_oropharynx()

    if success:
        print()
        print("SUCCESS: Migration completed!")
    else:
        print()
        print("FAILED: Migration did not complete")
        sys.exit(1)
