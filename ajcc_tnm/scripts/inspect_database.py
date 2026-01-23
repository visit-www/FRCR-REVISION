#!/usr/bin/env python3
"""
Inspect TNM Database Content

Shows what TNM staging data has been stored in the database.
"""

from app import app
from models import (
    db, AJCCBodySection, AJCCDiseaseSite, AJCCDiagnosisYear, 
    AJCCStagingData, AJCCDiseaseMapping
)
from sqlalchemy import func

def print_section(title):
    """Print a section header."""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def truncate_html(html, max_length=100):
    """Truncate HTML content for display."""
    if not html:
        return "None"
    
    # Remove HTML tags for preview
    import re
    text = re.sub(r'<[^>]+>', '', html)
    text = ' '.join(text.split())  # Normalize whitespace
    
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text

def inspect_database():
    """Inspect and display TNM database content."""
    with app.app_context():
        print_section("TNM DATABASE INSPECTION")
        
        # 1. Body Sections
        print_section("1. AJCC Body Sections")
        body_sections = AJCCBodySection.query.order_by(AJCCBodySection.display_order).all()
        print(f"\nTotal: {len(body_sections)} body sections\n")
        
        if body_sections:
            for section in body_sections:
                disease_count = len(section.disease_sites)
                print(f"  [{section.id}] {section.section_name}")
                print(f"      Slug: {section.slug}")
                print(f"      Diseases: {disease_count}")
                print()
        else:
            print("  (No body sections found)")
        
        # 2. Disease Sites
        print_section("2. AJCC Disease Sites")
        disease_sites = AJCCDiseaseSite.query.order_by(AJCCDiseaseSite.body_section_id).all()
        print(f"\nTotal: {len(disease_sites)} disease sites\n")
        
        if disease_sites:
            current_section = None
            for disease in disease_sites:
                if disease.body_section_id != current_section:
                    current_section = disease.body_section_id
                    section = AJCCBodySection.query.get(disease.body_section_id)
                    print(f"\n  --- {section.section_name if section else 'Unknown'} ---")
                
                staging_count = len(disease.staging_data)
                print(f"  [{disease.id}] {disease.disease_name}")
                print(f"      Slug: {disease.slug}")
                print(f"      URL Path: {disease.ajcc_url_path}")
                print(f"      Staging Data: {staging_count} year(s)")
                print()
        else:
            print("  (No disease sites found)")
        
        # 3. Diagnosis Years
        print_section("3. AJCC Diagnosis Years")
        years = AJCCDiagnosisYear.query.order_by(AJCCDiagnosisYear.year.desc()).all()
        print(f"\nTotal: {len(years)} years configured\n")
        
        if years:
            for year in years:
                staging_count = len(year.staging_data)
                default_marker = " (DEFAULT)" if year.is_default else ""
                print(f"  [{year.id}] {year.year}{default_marker}")
                print(f"      Staging Data: {staging_count} disease(s)")
                print()
        else:
            print("  (No diagnosis years found)")
        
        # 4. Staging Data (The main content!)
        print_section("4. TNM STAGING DATA (Main Content)")
        staging_data = AJCCStagingData.query.join(AJCCDiseaseSite).join(AJCCDiagnosisYear).all()
        print(f"\nTotal: {len(staging_data)} staging data records\n")
        
        if staging_data:
            for data in staging_data:
                disease = AJCCDiseaseSite.query.get(data.disease_site_id)
                year = AJCCDiagnosisYear.query.get(data.diagnosis_year_id)
                
                print(f"\n  ┌─ [{data.id}] {disease.disease_name} ({year.year})")
                print(f"  │  Disease Site ID: {data.disease_site_id}")
                print(f"  │  Year ID: {data.diagnosis_year_id}")
                print(f"  │  Last Updated: {data.last_updated_at or 'Never'}")
                print(f"  │")
                
                # Show section content previews
                sections = [
                    ("Section 1 - Quick Reference", data.section_1_quick_reference_html),
                    ("Section 2 - Cancers Staged", data.section_2_cancers_staged_html),
                    ("Section 3 - Cancers Not Staged", data.section_3_cancers_not_staged_html),
                    ("Section 4 - Summary of Changes", data.section_4_summary_changes_html),
                    ("Section 5 - Primary Site", data.section_5_primary_site_html),
                    ("Section 6 - Histopathologic Type", data.section_6_histopathologic_type_html),
                    ("Section 7 - Clinical Staging", data.section_7_clinical_staging_workup_html),
                    ("Section 8 - Staging Rules", data.section_8_staging_rules_html),
                    ("Section 9 - Common Scenarios", data.section_9_common_scenarios_html),
                    ("Section 10 - Explanatory Notes", data.section_10_explanatory_notes_html),
                ]
                
                for section_name, section_content in sections:
                    has_content = section_content and len(section_content.strip()) > 0
                    status = "✓" if has_content else "✗"
                    length = len(section_content) if section_content else 0
                    
                    print(f"  │  {status} {section_name}: {length:,} chars")
                    
                    if has_content and length > 0:
                        preview = truncate_html(section_content, 80)
                        print(f"  │     Preview: {preview}")
                
                print(f"  └─")
        else:
            print("  (No staging data found)")
        
        # 5. Disease Mappings
        print_section("5. AJCC Disease Mappings (to FRCR Modules)")
        mappings = AJCCDiseaseMapping.query.all()
        print(f"\nTotal: {len(mappings)} mappings\n")
        
        if mappings:
            for mapping in mappings:
                disease = AJCCDiseaseSite.query.get(mapping.disease_site_id)
                print(f"  [{mapping.id}] {disease.disease_name if disease else 'Unknown'}")
                print(f"      FRCR Module: {mapping.frcr_module.value if mapping.frcr_module else 'Not mapped'}")
                print(f"      Body Part: {mapping.body_part.value if mapping.body_part else 'Not mapped'}")
                if mapping.notes:
                    print(f"      Notes: {mapping.notes}")
                print()
        else:
            print("  (No disease mappings found)")
        
        # Summary Statistics
        print_section("SUMMARY STATISTICS")
        
        total_sections = AJCCBodySection.query.count()
        total_diseases = AJCCDiseaseSite.query.count()
        total_years = AJCCDiagnosisYear.query.count()
        total_staging = AJCCStagingData.query.count()
        total_mappings = AJCCDiseaseMapping.query.count()
        
        # Count staging data with actual content
        staging_with_content = AJCCStagingData.query.filter(
            db.or_(
                AJCCStagingData.section_1_quick_reference_html.isnot(None),
                AJCCStagingData.section_2_cancers_staged_html.isnot(None),
                AJCCStagingData.section_3_cancers_not_staged_html.isnot(None),
                AJCCStagingData.section_4_summary_changes_html.isnot(None),
                AJCCStagingData.section_5_primary_site_html.isnot(None),
                AJCCStagingData.section_6_histopathologic_type_html.isnot(None),
                AJCCStagingData.section_7_clinical_staging_workup_html.isnot(None),
                AJCCStagingData.section_8_staging_rules_html.isnot(None),
                AJCCStagingData.section_9_common_scenarios_html.isnot(None),
                AJCCStagingData.section_10_explanatory_notes_html.isnot(None),
            )
        ).count()
        
        print(f"\n  Body Sections: {total_sections}")
        print(f"  Disease Sites: {total_diseases}")
        print(f"  Diagnosis Years: {total_years}")
        print(f"  Staging Data Records: {total_staging}")
        print(f"    └─ With Content: {staging_with_content}")
        print(f"    └─ Empty: {total_staging - staging_with_content}")
        print(f"  Disease Mappings: {total_mappings}")
        print()

def show_specific_disease(disease_name, year):
    """Show detailed content for a specific disease and year."""
    with app.app_context():
        print_section(f"DETAILED VIEW: {disease_name} ({year})")
        
        # Find the disease
        disease = AJCCDiseaseSite.query.filter(
            AJCCDiseaseSite.disease_name.ilike(f"%{disease_name}%")
        ).first()
        
        if not disease:
            print(f"\n  ✗ Disease '{disease_name}' not found in database")
            return
        
        # Find the year
        year_obj = AJCCDiagnosisYear.query.filter_by(year=year).first()
        
        if not year_obj:
            print(f"\n  ✗ Year {year} not found in database")
            return
        
        # Find staging data
        staging = AJCCStagingData.query.filter_by(
            disease_site_id=disease.id,
            diagnosis_year_id=year_obj.id
        ).first()
        
        if not staging:
            print(f"\n  ✗ No staging data found for {disease.disease_name} ({year})")
            return
        
        print(f"\n  Disease: {disease.disease_name}")
        print(f"  URL Path: {disease.ajcc_url_path}")
        print(f"  Year: {year}")
        print(f"  Last Updated: {staging.last_updated_at or 'Never'}")
        print()
        
        # Show each section with full preview
        sections = [
            ("Section 1 - Quick Reference", staging.section_1_quick_reference_html),
            ("Section 2 - Cancers Staged", staging.section_2_cancers_staged_html),
            ("Section 3 - Cancers Not Staged", staging.section_3_cancers_not_staged_html),
            ("Section 4 - Summary of Changes", staging.section_4_summary_changes_html),
            ("Section 5 - Primary Site", staging.section_5_primary_site_html),
            ("Section 6 - Histopathologic Type", staging.section_6_histopathologic_type_html),
            ("Section 7 - Clinical Staging", staging.section_7_clinical_staging_workup_html),
            ("Section 8 - Staging Rules", staging.section_8_staging_rules_html),
            ("Section 9 - Common Scenarios", staging.section_9_common_scenarios_html),
            ("Section 10 - Explanatory Notes", staging.section_10_explanatory_notes_html),
        ]
        
        for section_name, section_content in sections:
            print(f"\n  {'─' * 75}")
            print(f"  {section_name}")
            print(f"  {'─' * 75}")
            
            if section_content and len(section_content.strip()) > 0:
                print(f"  Length: {len(section_content):,} characters")
                print(f"\n  Preview (first 500 chars):")
                print(f"  {'-' * 75}")
                preview = section_content[:500]
                print(f"  {preview}")
                if len(section_content) > 500:
                    print(f"  ... (+ {len(section_content) - 500:,} more characters)")
            else:
                print(f"  ✗ No content")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) == 3:
        # Show specific disease
        disease_name = sys.argv[1]
        year = int(sys.argv[2])
        show_specific_disease(disease_name, year)
    else:
        # Show overview
        inspect_database()
        
        print("\n" + "="*80)
        print("  To view detailed content for a specific disease:")
        print("  python inspect_tnm_database.py 'Larynx' 2026")
        print("="*80 + "\n")
