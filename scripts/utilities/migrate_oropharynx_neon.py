#!/usr/bin/env python3
"""
Migrate Oropharynx data to Neon PostgreSQL TNM Calculator Content Table
"""

import os
import json
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values

# Paths
project_root = Path(__file__).parent.parent.parent
calc_html_path = project_root / 'tnm_calculator' / 'calculators' / 'oropharynx_calc.html'

# Database connection
DATABASE_URL = "postgresql://neondb_owner:npg_DsKL8RFtw2zI@ep-frosty-sound-ahg70oqy-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"


def migrate():
    # Read calculator HTML
    if not calc_html_path.exists():
        print(f"ERROR: Calculator HTML not found: {calc_html_path}")
        return False

    calculator_html = calc_html_path.read_text(encoding='utf-8')
    print(f"Read calculator HTML: {len(calculator_html)} chars")

    # Connect to database
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        # Get algorithm discussion from case #34
        cur.execute('SELECT discussion FROM "case" WHERE id = 34')
        row = cur.fetchone()
        algorithm_html = row[0] if row else None
        print(f"Algorithm HTML from case #34: {len(algorithm_html) if algorithm_html else 0} chars")

        # Check if already exists
        cur.execute("SELECT id FROM tnm_calculator_content WHERE slug = 'oropharynx'")
        existing = cur.fetchone()
        if existing:
            print(f"Record already exists (ID: {existing[0]}), updating...")
            cur.execute("""
                UPDATE tnm_calculator_content
                SET calculator_html = %s,
                    algorithm_discussion_html = %s,
                    algorithm_case_id = 34,
                    updated_at = NOW()
                WHERE slug = 'oropharynx'
            """, (calculator_html, algorithm_html))
        else:
            # Insert new record
            special_features = json.dumps(['HPV+ Staging', 'HPV- Staging'])
            cur.execute("""
                INSERT INTO tnm_calculator_content
                (slug, cancer_name, body_section, calculator_html, algorithm_discussion_html,
                 staging_system, description, special_features, is_available,
                 generation_model, generated_at, algorithm_case_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW(), NOW())
                RETURNING id
            """, (
                'oropharynx',
                'Oropharynx',
                'Head and Neck',
                calculator_html,
                algorithm_html,
                'AJCC 9th Edition',
                'HPV+ and HPV- staging with detailed criteria',
                special_features,
                True,
                'manual/curated',
                34
            ))
            new_id = cur.fetchone()[0]
            print(f"Created new record ID: {new_id}")

        conn.commit()
        print("SUCCESS: Migration completed!")
        return True

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        return False

    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    print("=== Migrating Oropharynx to Neon TNM Calculator Content Table ===")
    print()
    migrate()
