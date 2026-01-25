#!/usr/bin/env python3
"""
Sync AJCC staging data from local backup to Neon PostgreSQL database.
Bypasses Vercel's upload limit by connecting directly to Neon.
"""

import json
import psycopg2
from psycopg2.extras import execute_values
import os

# Neon connection string
NEON_URL = "postgresql://neondb_owner:npg_DsKL8RFtw2zI@ep-frosty-sound-ahg70oqy-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"

# Backup file path
BACKUP_FILE = "/Users/zen/Downloads/frcr_revision_backup_20260126_012331.json"

def sync_staging_data():
    """Sync ajcc_staging_data to Neon"""
    
    print(f"Loading backup from {BACKUP_FILE}...")
    with open(BACKUP_FILE, 'r') as f:
        data = json.load(f)
    
    staging_data = data.get('ajcc_staging_data', [])
    print(f"Found {len(staging_data)} staging data entries to sync")
    
    print("Connecting to Neon...")
    conn = psycopg2.connect(NEON_URL)
    cur = conn.cursor()
    
    # First, clear existing staging data (optional - comment out to merge instead)
    # print("Clearing existing staging data...")
    # cur.execute("DELETE FROM ajcc_staging_data")
    
    success_count = 0
    error_count = 0
    
    for i, item in enumerate(staging_data):
        try:
            # Upsert each record
            cur.execute("""
                INSERT INTO ajcc_staging_data (
                    disease_site_id, diagnosis_year_id, extracted_at, extracted_by_user_id,
                    last_updated_at, data_version, tnm_data_json, cancers_staged_json,
                    cancers_not_staged_json, summary_changes_json, primary_sites_json,
                    histopathologic_types_json, imaging_workup_json, staging_rules_json,
                    common_scenarios_json, notes_json, section_1_quick_reference_html,
                    section_2_cancers_staged_html, section_3_cancers_not_staged_html,
                    section_4_summary_changes_html, section_5_primary_site_html,
                    section_6_histopathologic_type_html, section_7_clinical_staging_workup_html,
                    section_8_staging_rules_html, section_9_common_scenarios_html,
                    section_10_explanatory_notes_html, raw_html_content
                ) VALUES (
                    %(disease_site_id)s, %(diagnosis_year_id)s, %(extracted_at)s, %(extracted_by_user_id)s,
                    %(last_updated_at)s, %(data_version)s, %(tnm_data_json)s, %(cancers_staged_json)s,
                    %(cancers_not_staged_json)s, %(summary_changes_json)s, %(primary_sites_json)s,
                    %(histopathologic_types_json)s, %(imaging_workup_json)s, %(staging_rules_json)s,
                    %(common_scenarios_json)s, %(notes_json)s, %(section_1_quick_reference_html)s,
                    %(section_2_cancers_staged_html)s, %(section_3_cancers_not_staged_html)s,
                    %(section_4_summary_changes_html)s, %(section_5_primary_site_html)s,
                    %(section_6_histopathologic_type_html)s, %(section_7_clinical_staging_workup_html)s,
                    %(section_8_staging_rules_html)s, %(section_9_common_scenarios_html)s,
                    %(section_10_explanatory_notes_html)s, %(raw_html_content)s
                )
                ON CONFLICT (disease_site_id, diagnosis_year_id) DO UPDATE SET
                    extracted_at = EXCLUDED.extracted_at,
                    last_updated_at = EXCLUDED.last_updated_at,
                    data_version = EXCLUDED.data_version,
                    tnm_data_json = EXCLUDED.tnm_data_json,
                    cancers_staged_json = EXCLUDED.cancers_staged_json,
                    cancers_not_staged_json = EXCLUDED.cancers_not_staged_json,
                    summary_changes_json = EXCLUDED.summary_changes_json,
                    primary_sites_json = EXCLUDED.primary_sites_json,
                    histopathologic_types_json = EXCLUDED.histopathologic_types_json,
                    imaging_workup_json = EXCLUDED.imaging_workup_json,
                    staging_rules_json = EXCLUDED.staging_rules_json,
                    common_scenarios_json = EXCLUDED.common_scenarios_json,
                    notes_json = EXCLUDED.notes_json,
                    section_1_quick_reference_html = EXCLUDED.section_1_quick_reference_html,
                    section_2_cancers_staged_html = EXCLUDED.section_2_cancers_staged_html,
                    section_3_cancers_not_staged_html = EXCLUDED.section_3_cancers_not_staged_html,
                    section_4_summary_changes_html = EXCLUDED.section_4_summary_changes_html,
                    section_5_primary_site_html = EXCLUDED.section_5_primary_site_html,
                    section_6_histopathologic_type_html = EXCLUDED.section_6_histopathologic_type_html,
                    section_7_clinical_staging_workup_html = EXCLUDED.section_7_clinical_staging_workup_html,
                    section_8_staging_rules_html = EXCLUDED.section_8_staging_rules_html,
                    section_9_common_scenarios_html = EXCLUDED.section_9_common_scenarios_html,
                    section_10_explanatory_notes_html = EXCLUDED.section_10_explanatory_notes_html,
                    raw_html_content = EXCLUDED.raw_html_content
            """, {
                'disease_site_id': item['disease_site_id'],
                'diagnosis_year_id': item['diagnosis_year_id'],
                'extracted_at': item.get('extracted_at'),
                'extracted_by_user_id': item.get('extracted_by_user_id'),
                'last_updated_at': item.get('last_updated_at'),
                'data_version': item.get('data_version', 1),
                'tnm_data_json': item.get('tnm_data_json'),
                'cancers_staged_json': item.get('cancers_staged_json'),
                'cancers_not_staged_json': item.get('cancers_not_staged_json'),
                'summary_changes_json': item.get('summary_changes_json'),
                'primary_sites_json': item.get('primary_sites_json'),
                'histopathologic_types_json': item.get('histopathologic_types_json'),
                'imaging_workup_json': item.get('imaging_workup_json'),
                'staging_rules_json': item.get('staging_rules_json'),
                'common_scenarios_json': item.get('common_scenarios_json'),
                'notes_json': item.get('notes_json'),
                'section_1_quick_reference_html': item.get('section_1_quick_reference_html'),
                'section_2_cancers_staged_html': item.get('section_2_cancers_staged_html'),
                'section_3_cancers_not_staged_html': item.get('section_3_cancers_not_staged_html'),
                'section_4_summary_changes_html': item.get('section_4_summary_changes_html'),
                'section_5_primary_site_html': item.get('section_5_primary_site_html'),
                'section_6_histopathologic_type_html': item.get('section_6_histopathologic_type_html'),
                'section_7_clinical_staging_workup_html': item.get('section_7_clinical_staging_workup_html'),
                'section_8_staging_rules_html': item.get('section_8_staging_rules_html'),
                'section_9_common_scenarios_html': item.get('section_9_common_scenarios_html'),
                'section_10_explanatory_notes_html': item.get('section_10_explanatory_notes_html'),
                'raw_html_content': item.get('raw_html_content'),
            })
            success_count += 1
            print(f"  [{i+1}/{len(staging_data)}] Synced disease_site_id={item['disease_site_id']}")
            
        except Exception as e:
            error_count += 1
            print(f"  [{i+1}/{len(staging_data)}] ERROR: {e}")
    
    conn.commit()
    
    # Verify count
    cur.execute("SELECT COUNT(*) FROM ajcc_staging_data")
    total = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    print()
    print("=" * 50)
    print(f"Sync complete!")
    print(f"  Success: {success_count}")
    print(f"  Errors: {error_count}")
    print(f"  Total in Neon: {total}")
    print("=" * 50)

if __name__ == "__main__":
    sync_staging_data()
