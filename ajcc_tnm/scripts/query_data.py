#!/usr/bin/env python3
"""
Script to query and display AJCC TNM staging data from the database.
Run with: python query_ajcc_data.py
"""

import os
import sys
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import AJCCBodySection, AJCCDiseaseSite, AJCCDiagnosisYear, AJCCStagingData


def get_all_ajcc_data():
    """Get all AJCC data as a structured dictionary"""
    data = {
        'body_sections': [],
        'disease_sites': [],
        'diagnosis_years': [],
        'staging_data': []
    }
    
    with app.app_context():
        # Get body sections
        sections = AJCCBodySection.query.order_by(AJCCBodySection.display_order).all()
        for section in sections:
            data['body_sections'].append({
                'id': section.id,
                'section_name': section.section_name,
                'slug': section.slug,
                'display_order': section.display_order
            })
        
        # Get disease sites
        sites = AJCCDiseaseSite.query.all()
        for site in sites:
            data['disease_sites'].append({
                'id': site.id,
                'body_section_id': site.body_section_id,
                'disease_name': site.disease_name,
                'slug': site.slug,
                'ajcc_url_path': site.ajcc_url_path
            })
        
        # Get diagnosis years
        years = AJCCDiagnosisYear.query.order_by(AJCCDiagnosisYear.year).all()
        for year in years:
            data['diagnosis_years'].append({
                'id': year.id,
                'year': year.year,
                'is_default': year.is_default
            })
        
        # Get staging data with section content
        staging_records = AJCCStagingData.query.all()
        for record in staging_records:
            staging_entry = {
                'id': record.id,
                'disease_site_id': record.disease_site_id,
                'disease_name': record.disease_site.disease_name if record.disease_site else None,
                'diagnosis_year_id': record.diagnosis_year_id,
                'diagnosis_year': record.diagnosis_year.year if record.diagnosis_year else None,
                'extracted_at': record.extracted_at.isoformat() if record.extracted_at else None,
                'sections': {}
            }
            
            # Add all 10 sections
            section_names = [
                'quick_reference', 'cancers_staged', 'cancers_not_staged', 
                'summary_changes', 'primary_site', 'histopathologic_type',
                'clinical_staging_workup', 'staging_rules', 'common_scenarios',
                'explanatory_notes'
            ]
            
            for i, name in enumerate(section_names, 1):
                html_content = record.get_section_html(i)
                staging_entry['sections'][name] = {
                    'section_number': i,
                    'has_content': html_content is not None and len(html_content) > 0,
                    'content_length': len(html_content) if html_content else 0,
                    'html': html_content  # Include actual HTML content
                }
            
            data['staging_data'].append(staging_entry)
    
    return data


def print_summary():
    """Print a summary of AJCC data in the database"""
    with app.app_context():
        print("\n" + "="*60)
        print("AJCC TNM STAGING DATA SUMMARY")
        print("="*60)
        
        # Body sections
        sections = AJCCBodySection.query.order_by(AJCCBodySection.display_order).all()
        print(f"\n📂 Body Sections ({len(sections)} total):")
        for section in sections:
            disease_count = AJCCDiseaseSite.query.filter_by(body_section_id=section.id).count()
            print(f"   - {section.section_name} (slug: {section.slug}, diseases: {disease_count})")
        
        # Disease sites
        sites = AJCCDiseaseSite.query.all()
        print(f"\n🏥 Disease Sites ({len(sites)} total):")
        for site in sites[:10]:  # Show first 10
            print(f"   - [{site.id}] {site.disease_name} ({site.ajcc_url_path})")
        if len(sites) > 10:
            print(f"   ... and {len(sites) - 10} more")
        
        # Diagnosis years
        years = AJCCDiagnosisYear.query.order_by(AJCCDiagnosisYear.year).all()
        print(f"\n📅 Diagnosis Years ({len(years)} total):")
        for year in years:
            default = " (default)" if year.is_default else ""
            print(f"   - {year.year}{default}")
        
        # Staging data
        staging_count = AJCCStagingData.query.count()
        print(f"\n📊 Staging Data Records: {staging_count}")
        
        if staging_count > 0:
            staging_records = AJCCStagingData.query.limit(5).all()
            print("\n   Sample staging data:")
            for record in staging_records:
                disease_name = record.disease_site.disease_name if record.disease_site else "Unknown"
                year = record.diagnosis_year.year if record.diagnosis_year else "Unknown"
                version = getattr(record, 'data_version', 1)
                
                # Count non-empty sections
                non_empty_sections = sum(1 for i in range(1, 11) if record.get_section_html(i))
                
                # Check for JSON data
                has_json = record.tnm_data_json is not None
                
                print(f"   - {disease_name} ({year})")
                print(f"     Version: {version}, HTML sections: {non_empty_sections}/10, JSON: {'✓' if has_json else '✗'}")
                
                # Show JSON stats if available
                if has_json:
                    tnm = record.get_tnm_data()
                    if tnm:
                        t_count = len(tnm.get('t_definitions', []))
                        stage_count = len(tnm.get('stage_groups', []))
                        print(f"     TNM Data: {t_count} T subsites, {stage_count} stage groups")
        
        print("\n" + "="*60)


def print_json_data():
    """Print the structured JSON data for all records"""
    with app.app_context():
        staging_records = AJCCStagingData.query.all()
        
        for record in staging_records:
            disease_name = record.disease_site.disease_name if record.disease_site else "Unknown"
            year = record.diagnosis_year.year if record.diagnosis_year else "Unknown"
            
            print(f"\n{'='*60}")
            print(f"JSON DATA: {disease_name} ({year})")
            print(f"{'='*60}")
            
            tnm = record.get_tnm_data()
            if tnm:
                print(f"\n📋 T Definitions ({len(tnm.get('t_definitions', []))} subsites):")
                for subsite in tnm.get('t_definitions', []):
                    print(f"   {subsite['subsite']}:")
                    for cat in subsite.get('categories', [])[:3]:
                        print(f"     - {cat['category']}: {cat['criteria'][:50]}...")
                    if len(subsite.get('categories', [])) > 3:
                        print(f"     ... and {len(subsite['categories']) - 3} more")
                
                n_def = tnm.get('n_definitions', {})
                print(f"\n📋 N Definitions:")
                print(f"   Clinical: {len(n_def.get('clinical', []))} categories")
                print(f"   Pathological: {len(n_def.get('pathological', []))} categories")
                
                print(f"\n📋 M Definitions ({len(tnm.get('m_definitions', []))} categories):")
                for cat in tnm.get('m_definitions', []):
                    print(f"   - {cat['category']}: {cat['criteria']}")
                
                print(f"\n📋 Stage Groups ({len(tnm.get('stage_groups', []))} combinations):")
                for sg in tnm.get('stage_groups', [])[:5]:
                    print(f"   - T={sg['T']}, N={sg['N']}, M={sg['M']} → Stage {sg['stage']}")
                if len(tnm.get('stage_groups', [])) > 5:
                    print(f"   ... and {len(tnm['stage_groups']) - 5} more")
                
                # Test stage lookup
                print(f"\n🔍 Stage Lookup Test:")
                test_cases = [
                    ('T1', 'N0', 'M0'),
                    ('T3', 'N1', 'M0'),
                    ('T4a', 'N2', 'M0'),
                    ('T2', 'N0', 'M1'),
                ]
                for t, n, m in test_cases:
                    stage = record.get_stage_for_tnm(t, n, m)
                    print(f"   {t} {n} {m} → Stage {stage or 'Not Found'}")


def export_to_json(filename='ajcc_data_export.json'):
    """Export all AJCC data to a JSON file"""
    data = get_all_ajcc_data()
    
    # Remove HTML content for cleaner JSON (optional)
    for staging in data['staging_data']:
        for section_name, section_data in staging['sections'].items():
            if section_data['html'] and len(section_data['html']) > 500:
                section_data['html_preview'] = section_data['html'][:500] + '...'
                # Keep full HTML in a separate field
                section_data['html_full'] = section_data['html']
            del section_data['html']
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Data exported to: {filename}")
    return filename


def get_staging_for_disease(disease_name_or_id, year=None):
    """Get staging data for a specific disease"""
    with app.app_context():
        query = AJCCStagingData.query
        
        if isinstance(disease_name_or_id, int):
            query = query.filter_by(disease_site_id=disease_name_or_id)
        else:
            query = query.join(AJCCDiseaseSite).filter(
                AJCCDiseaseSite.disease_name.ilike(f'%{disease_name_or_id}%')
            )
        
        if year:
            query = query.join(AJCCDiagnosisYear).filter(AJCCDiagnosisYear.year == year)
        
        results = query.all()
        
        if not results:
            print(f"No staging data found for: {disease_name_or_id}")
            return None
        
        for record in results:
            print(f"\n📋 Staging Data for: {record.disease_site.disease_name}")
            print(f"   Year: {record.diagnosis_year.year}")
            print(f"   Extracted: {record.extracted_at}")
            print("\n   Sections:")
            
            section_names = [
                'Quick Reference', 'Cancers Staged', 'Cancers Not Staged', 
                'Summary Changes', 'Primary Site', 'Histopathologic Type',
                'Clinical Staging Workup', 'Staging Rules', 'Common Scenarios',
                'Explanatory Notes'
            ]
            
            for i, name in enumerate(section_names, 1):
                html = record.get_section_html(i)
                if html:
                    print(f"   ✅ Section {i}: {name} ({len(html)} chars)")
                else:
                    print(f"   ❌ Section {i}: {name} (empty)")
        
        return results


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Query AJCC TNM Staging Data')
    parser.add_argument('--summary', action='store_true', help='Print summary of all data')
    parser.add_argument('--export', action='store_true', help='Export all data to JSON')
    parser.add_argument('--disease', type=str, help='Get staging for specific disease')
    parser.add_argument('--year', type=int, help='Filter by diagnosis year')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--show-json', action='store_true', help='Show structured JSON data')
    
    args = parser.parse_args()
    
    if args.export:
        export_to_json()
    elif args.disease:
        get_staging_for_disease(args.disease, args.year)
    elif args.json:
        data = get_all_ajcc_data()
        print(json.dumps(data, indent=2, default=str))
    elif args.show_json:
        print_json_data()
    else:
        # Default: print summary
        print_summary()
