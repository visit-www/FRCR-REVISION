"""
Initialize AJCC Mappings Script

Populates AJCC body sections, disease sites, and mappings to app modules/body parts.
Run this script after database migration to initialize the AJCC data structure.
"""

import os
import sys
import json
import re

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, AJCCBodySection, AJCCDiseaseSite, AJCCDiagnosisYear, AJCCDiseaseMapping
from models import FRCRModule, BodyPart


def load_json_file(filepath):
    """Load JSON file."""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        full_path = os.path.join(project_root, filepath)
        with open(full_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {filepath} not found")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing {filepath}: {e}")
        return None


def load_text_file(filepath):
    """Load text file."""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        full_path = os.path.join(project_root, filepath)
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: {filepath} not found")
        return None


def slugify(text):
    """Convert text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


def create_mapping(disease_site, ajcc_section_name, disease_name):
    """
    Create mapping from AJCC disease to app FRCRModule and BodyPart.
    
    Returns list of (frcr_module, body_part) tuples.
    """
    mappings = []
    
    # Mapping rules based on AJCC section and disease
    section_lower = ajcc_section_name.lower()
    disease_lower = disease_name.lower()
    
    # Thorax -> Cardiothoracic and Vascular
    if 'thorax' in section_lower:
        if 'lung' in disease_lower:
            mappings.append((FRCRModule.CARDIOTHORACIC_VASCULAR, BodyPart.LUNG_MEDIASTINUM))
        elif 'pleural' in disease_lower or 'mesothelioma' in disease_lower:
            mappings.append((FRCRModule.CARDIOTHORACIC_VASCULAR, BodyPart.LUNG_MEDIASTINUM))
        elif 'thymus' in disease_lower:
            mappings.append((FRCRModule.CARDIOTHORACIC_VASCULAR, BodyPart.LUNG_MEDIASTINUM))
    
    # Head and Neck -> CNS and Head & Neck
    elif 'head' in section_lower and 'neck' in section_lower:
        mappings.append((FRCRModule.CNS_HEAD_NECK, BodyPart.HEAD_NECK))
    
    # Upper GI -> Gastro-intestinal
    elif 'upper' in section_lower and 'gastrointestinal' in section_lower:
        mappings.append((FRCRModule.GASTROINTESTINAL, BodyPart.GASTROINTESTINAL))
    
    # Lower GI -> Gastro-intestinal
    elif 'lower' in section_lower and 'gastrointestinal' in section_lower:
        mappings.append((FRCRModule.GASTROINTESTINAL, BodyPart.GASTROINTESTINAL))
    
    # Hepatobiliary -> Gastro-intestinal
    elif 'hepatobiliary' in section_lower:
        mappings.append((FRCRModule.GASTROINTESTINAL, BodyPart.HEPATOPANCREATICOBILIARY))
    
    # Breast -> Genito-urinary, Adrenal, O&G and Breast
    elif 'breast' in section_lower:
        mappings.append((FRCRModule.GENITOURINARY_BREAST, BodyPart.BREAST))
    
    # Female Reproductive -> Genito-urinary, Adrenal, O&G and Breast
    elif 'female' in section_lower and 'reproductive' in section_lower:
        mappings.append((FRCRModule.GENITOURINARY_BREAST, BodyPart.GYNAECOLOGY))
    
    # Male Genital -> Genito-urinary, Adrenal, O&G and Breast
    elif 'male' in section_lower and 'genital' in section_lower:
        mappings.append((FRCRModule.GENITOURINARY_BREAST, BodyPart.KUB))
    
    # Urinary Tract -> Genito-urinary, Adrenal, O&G and Breast
    elif 'urinary' in section_lower:
        mappings.append((FRCRModule.GENITOURINARY_BREAST, BodyPart.KUB))
    
    # Endocrine -> Genito-urinary, Adrenal, O&G and Breast (for adrenal) or CNS and Head & Neck (for thyroid)
    elif 'endocrine' in section_lower:
        if 'adrenal' in disease_lower:
            mappings.append((FRCRModule.GENITOURINARY_BREAST, BodyPart.ADRENAL))
        elif 'thyroid' in disease_lower or 'parathyroid' in disease_lower:
            mappings.append((FRCRModule.CNS_HEAD_NECK, BodyPart.THYROID_PARATHYROID))
    
    # Central Nervous System -> CNS and Head & Neck
    elif 'central' in section_lower and 'nervous' in section_lower:
        mappings.append((FRCRModule.CNS_HEAD_NECK, BodyPart.BRAIN_PITUITARY))
    
    # Bone -> Musculoskeletal and Trauma
    elif 'bone' in section_lower:
        mappings.append((FRCRModule.MUSCULOSKELETAL_TRAUMA, BodyPart.BONES))
    
    # Soft Tissue Sarcoma -> Musculoskeletal and Trauma
    elif 'soft tissue' in section_lower or 'sarcoma' in section_lower:
        mappings.append((FRCRModule.MUSCULOSKELETAL_TRAUMA, BodyPart.BONES))
    
    # Ophthalmic -> CNS and Head & Neck
    elif 'ophthalmic' in section_lower:
        mappings.append((FRCRModule.CNS_HEAD_NECK, BodyPart.HEAD_NECK))
    
    # Skin -> Could be multiple, default to Multisystem
    elif 'skin' in section_lower:
        mappings.append((FRCRModule.CNS_HEAD_NECK, BodyPart.HEAD_NECK))  # Often head/neck related
    
    # Neuroendocrine -> Gastro-intestinal (often GI-related)
    elif 'neuroendocrine' in section_lower:
        mappings.append((FRCRModule.GASTROINTESTINAL, BodyPart.GASTROINTESTINAL))
    
    # Hematologic -> Could be multiple, default to Multisystem
    elif 'hematologic' in section_lower:
        # No specific mapping - can be anywhere
        pass
    
    # If no mapping found, return empty list
    return mappings


def initialize_ajcc_mappings():
    """Initialize AJCC body sections, disease sites, and mappings."""
    
    with app.app_context():
        print("Starting AJCC mappings initialization...")
        
        # 1. Initialize diagnosis years
        print("\n1. Initializing diagnosis years...")
        years = [2024, 2025, 2026]
        for year in years:
            existing = AJCCDiagnosisYear.query.filter_by(year=year).first()
            if not existing:
                is_default = (year == 2026)
                diagnosis_year = AJCCDiagnosisYear(year=year, is_default=is_default)
                db.session.add(diagnosis_year)
                print(f"  Created diagnosis year: {year} (default: {is_default})")
            else:
                print(f"  Diagnosis year {year} already exists")
        db.session.commit()
        
        # 2. Load and create body sections from ajcc.json
        print("\n2. Loading body sections from ajcc.json...")
        ajcc_data = load_json_file('ajcc.json')
        if not ajcc_data:
            print("Error: Could not load ajcc.json")
            return
        
        section_order = 0
        for item in ajcc_data:
            if item.get('type') == 'body_system':
                section_name = item.get('display_name')
                slug = item.get('slug')
                
                if section_name and slug:
                    existing = AJCCBodySection.query.filter_by(slug=slug).first()
                    if not existing:
                        section = AJCCBodySection(
                            section_name=section_name,
                            slug=slug,
                            display_order=section_order
                        )
                        db.session.add(section)
                        print(f"  Created section: {section_name} ({slug})")
                    else:
                        print(f"  Section {section_name} already exists")
                    section_order += 1
        
        db.session.commit()
        
        # 3. Load and create disease sites from ajcc_frcr_full_ontology.json
        print("\n3. Loading disease sites from ajcc_frcr_full_ontology.json...")
        ontology_data = load_json_file('ajcc_frcr_full_ontology.json')
        if not ontology_data:
            print("Error: Could not load ajcc_frcr_full_ontology.json")
            return
        
        sections_data = ontology_data.get('sections', [])
        for section_data in sections_data:
            ajcc_section_name = section_data.get('ajcc_section')
            disease_sites = section_data.get('disease_sites', [])
            
            if not ajcc_section_name:
                continue
            
            # Find body section
            body_section = AJCCBodySection.query.filter_by(section_name=ajcc_section_name).first()
            if not body_section:
                print(f"  Warning: Body section '{ajcc_section_name}' not found, skipping")
                continue
            
            # Create disease sites
            for disease_name in disease_sites:
                disease_slug = slugify(disease_name)
                ajcc_url_path = f"{body_section.slug}/{disease_slug}"
                
                existing = AJCCDiseaseSite.query.filter_by(
                    body_section_id=body_section.id,
                    slug=disease_slug
                ).first()
                
                if not existing:
                    disease_site = AJCCDiseaseSite(
                        body_section_id=body_section.id,
                        disease_name=disease_name,
                        slug=disease_slug,
                        ajcc_url_path=ajcc_url_path
                    )
                    db.session.add(disease_site)
                    db.session.flush()  # Get ID
                    
                    print(f"  Created disease: {disease_name} ({disease_slug}) in {ajcc_section_name}")
                    
                    # 4. Create mappings to app modules/body parts
                    mappings = create_mapping(disease_site, ajcc_section_name, disease_name)
                    for frcr_module, body_part in mappings:
                        mapping = AJCCDiseaseMapping(
                            disease_site_id=disease_site.id,
                            frcr_module=frcr_module,
                            body_part=body_part
                        )
                        db.session.add(mapping)
                        print(f"    Mapped to: {frcr_module.value} / {body_part.value}")
                else:
                    print(f"  Disease {disease_name} already exists")
        
        db.session.commit()
        
        print("\n✓ AJCC mappings initialization completed!")
        print(f"  - Body sections: {AJCCBodySection.query.count()}")
        print(f"  - Disease sites: {AJCCDiseaseSite.query.count()}")
        print(f"  - Mappings: {AJCCDiseaseMapping.query.count()}")
        print(f"  - Diagnosis years: {AJCCDiagnosisYear.query.count()}")


if __name__ == '__main__':
    initialize_ajcc_mappings()
