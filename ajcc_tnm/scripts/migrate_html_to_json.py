#!/usr/bin/env python3
"""
Migrate existing AJCC HTML data to structured JSON format.

This script:
1. Reads existing HTML content from AJCCStagingData records
2. Parses HTML into clean structured JSON
3. Updates the records with JSON data
4. Sets data_version to 2

Usage:
    python migrate_ajcc_html_to_json.py [--dry-run]
"""

import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import AJCCStagingData
from ajcc_tnm_extractor import TNMDataCleaner


def migrate_record(staging: AJCCStagingData, dry_run: bool = False) -> bool:
    """
    Migrate a single AJCCStagingData record from HTML to JSON.
    
    Returns True if migration was successful.
    """
    disease_name = staging.disease_site.disease_name if staging.disease_site else f"ID:{staging.id}"
    year = staging.diagnosis_year.year if staging.diagnosis_year else "Unknown"
    
    print(f"\n{'='*60}")
    print(f"Migrating: {disease_name} ({year})")
    print(f"{'='*60}")
    
    changes_made = False
    
    # Parse Quick Reference HTML to TNM JSON
    if staging.section_1_quick_reference_html:
        print(f"  Parsing Quick Reference HTML ({len(staging.section_1_quick_reference_html)} chars)...")
        try:
            tnm_data = TNMDataCleaner.parse_quick_reference_to_json(staging.section_1_quick_reference_html)
            
            t_count = len(tnm_data.get('t_definitions', []))
            n_clinical = len(tnm_data.get('n_definitions', {}).get('clinical', []))
            n_path = len(tnm_data.get('n_definitions', {}).get('pathological', []))
            m_count = len(tnm_data.get('m_definitions', []))
            stage_count = len(tnm_data.get('stage_groups', []))
            
            print(f"  ✓ Parsed TNM data:")
            print(f"    - T definitions: {t_count} subsites")
            print(f"    - N definitions: {n_clinical} clinical, {n_path} pathological")
            print(f"    - M definitions: {m_count} categories")
            print(f"    - Stage groups: {stage_count} combinations")
            
            if not dry_run:
                staging.tnm_data_json = json.dumps(tnm_data, ensure_ascii=False)
            changes_made = True
            
        except Exception as e:
            print(f"  ✗ Error parsing Quick Reference: {e}")
    
    # Parse Cancers Staged
    if staging.section_2_cancers_staged_html:
        print(f"  Parsing Cancers Staged HTML...")
        try:
            data = TNMDataCleaner.parse_cancers_staged_to_json(staging.section_2_cancers_staged_html)
            if not dry_run:
                staging.cancers_staged_json = json.dumps(data, ensure_ascii=False)
            print(f"  ✓ Parsed Cancers Staged")
            changes_made = True
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    # Parse Cancers Not Staged
    if staging.section_3_cancers_not_staged_html:
        print(f"  Parsing Cancers Not Staged HTML...")
        try:
            data = TNMDataCleaner.parse_cancers_not_staged_to_json(staging.section_3_cancers_not_staged_html)
            exclusions = len(data.get('exclusions', []))
            if not dry_run:
                staging.cancers_not_staged_json = json.dumps(data, ensure_ascii=False)
            print(f"  ✓ Parsed Cancers Not Staged ({exclusions} exclusions)")
            changes_made = True
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    # Parse Summary of Changes
    if staging.section_4_summary_changes_html:
        print(f"  Parsing Summary of Changes HTML...")
        try:
            data = TNMDataCleaner.parse_summary_changes_to_json(staging.section_4_summary_changes_html)
            changes_count = len(data.get('changes', []))
            if not dry_run:
                staging.summary_changes_json = json.dumps(data, ensure_ascii=False)
            print(f"  ✓ Parsed Summary of Changes ({changes_count} changes)")
            changes_made = True
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    # Parse Primary Site
    if staging.section_5_primary_site_html:
        print(f"  Parsing Primary Site HTML...")
        try:
            data = TNMDataCleaner.parse_primary_site_to_json(staging.section_5_primary_site_html)
            sites_count = len(data.get('sites', []))
            if not dry_run:
                staging.primary_sites_json = json.dumps(data, ensure_ascii=False)
            print(f"  ✓ Parsed Primary Site ({sites_count} ICD-O codes)")
            changes_made = True
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    # Parse Histopathologic Type
    if staging.section_6_histopathologic_type_html:
        print(f"  Parsing Histopathologic Type HTML...")
        try:
            data = TNMDataCleaner.parse_histopathologic_type_to_json(staging.section_6_histopathologic_type_html)
            if not dry_run:
                staging.histopathologic_types_json = json.dumps(data, ensure_ascii=False)
            print(f"  ✓ Parsed Histopathologic Type")
            changes_made = True
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    # Parse Staging Rules
    if staging.section_8_staging_rules_html:
        print(f"  Parsing Staging Rules HTML...")
        try:
            data = TNMDataCleaner.parse_staging_rules_to_json(staging.section_8_staging_rules_html)
            rules_count = len(data.get('rules', []))
            if not dry_run:
                staging.staging_rules_json = json.dumps(data, ensure_ascii=False)
            print(f"  ✓ Parsed Staging Rules ({rules_count} rules)")
            changes_made = True
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    # Update data version
    if changes_made and not dry_run:
        staging.data_version = 2
        print(f"\n  ✓ Updated data_version to 2")
    
    return changes_made


def main():
    parser = argparse.ArgumentParser(description='Migrate AJCC HTML data to JSON')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be done without making changes')
    args = parser.parse_args()
    
    if args.dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No changes will be made")
        print("=" * 60)
    
    with app.app_context():
        # Get all staging records
        records = AJCCStagingData.query.all()
        print(f"\nFound {len(records)} staging records to migrate")
        
        if not records:
            print("No records to migrate.")
            return
        
        migrated = 0
        failed = 0
        
        for record in records:
            try:
                if migrate_record(record, dry_run=args.dry_run):
                    migrated += 1
            except Exception as e:
                print(f"  ✗ Failed to migrate record {record.id}: {e}")
                failed += 1
        
        if not args.dry_run and migrated > 0:
            print(f"\n{'='*60}")
            print("Committing changes to database...")
            db.session.commit()
            print("✓ Changes committed")
        
        print(f"\n{'='*60}")
        print("MIGRATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total records: {len(records)}")
        print(f"Migrated: {migrated}")
        print(f"Failed: {failed}")
        
        if args.dry_run:
            print("\nThis was a DRY RUN. Run without --dry-run to apply changes.")


if __name__ == '__main__':
    main()
