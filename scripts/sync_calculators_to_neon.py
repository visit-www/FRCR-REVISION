#!/usr/bin/env python3
"""
Sync TNM calculator HTML files to Neon PostgreSQL database.
Updates the calculator_html field in tnm_calculator_content table.
"""

import psycopg2
import os
from pathlib import Path

# Neon connection string
NEON_URL = "postgresql://neondb_owner:npg_DsKL8RFtw2zI@ep-frosty-sound-ahg70oqy-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"

# Calculator files directory
CALC_DIR = Path(__file__).parent.parent / 'tnm_calculator' / 'calculators'

def sync_calculators():
    """Sync all calculator HTML files to Neon database"""

    print("Connecting to Neon...")
    conn = psycopg2.connect(NEON_URL)
    cur = conn.cursor()

    # Get list of calculator files
    calc_files = list(CALC_DIR.glob('*_calc.html'))
    print(f"Found {len(calc_files)} calculator files")

    success_count = 0
    error_count = 0

    for calc_file in calc_files:
        slug = calc_file.stem.replace('_calc', '')

        try:
            # Read the HTML file
            with open(calc_file, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # Update the database record
            cur.execute("""
                UPDATE tnm_calculator_content
                SET calculator_html = %s, updated_at = NOW()
                WHERE slug = %s
            """, (html_content, slug))

            if cur.rowcount > 0:
                success_count += 1
                print(f"  Updated: {slug}")
            else:
                print(f"  No DB record found for: {slug}")

        except Exception as e:
            error_count += 1
            print(f"  ERROR syncing {slug}: {e}")

    conn.commit()

    # Show current calculator records
    cur.execute("SELECT slug, cancer_name, LENGTH(calculator_html) as html_len FROM tnm_calculator_content ORDER BY slug")
    records = cur.fetchall()

    print("\n" + "=" * 60)
    print("Current calculator records in Neon:")
    for slug, name, html_len in records:
        print(f"  {slug}: {name} ({html_len or 0} chars)")

    cur.close()
    conn.close()

    print("\n" + "=" * 60)
    print(f"Sync complete!")
    print(f"  Updated: {success_count}")
    print(f"  Errors: {error_count}")
    print("=" * 60)

if __name__ == "__main__":
    sync_calculators()
