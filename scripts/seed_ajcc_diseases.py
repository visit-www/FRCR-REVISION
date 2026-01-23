#!/usr/bin/env python3
"""
Seed AJCC Disease Sites

This script populates the AJCCDiseaseSite table with all diseases
organized by body section, matching the AJCC Cancer Staging Manual structure.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import AJCCBodySection, AJCCDiseaseSite


def slugify(text):
    """Convert text to URL-friendly slug."""
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text


# Define all sections and their diseases
# Format: {section_slug: [(disease_name, disease_slug, ajcc_url_path), ...]}
SECTIONS_AND_DISEASES = {
    "head-and-neck": [
        ("Oral Cavity", "oral-cavity", "head-and-neck/oral-cavity"),
        ("Oropharynx (HPV-Mediated)", "oropharynx-hpv-mediated", "head-and-neck/oropharynx-hpv-mediated"),
        ("Oropharynx (p16-Negative)", "oropharynx-p16-negative", "head-and-neck/oropharynx-p16-negative"),
        ("Hypopharynx", "hypopharynx", "head-and-neck/hypopharynx"),
        ("Nasopharynx", "nasopharynx", "head-and-neck/nasopharynx"),
        ("Larynx", "larynx", "head-and-neck/larynx"),
        ("Nasal Cavity and Paranasal Sinuses", "nasal-cavity-and-paranasal-sinuses", "head-and-neck/nasal-cavity-and-paranasal-sinuses"),
        ("Salivary Glands", "salivary-glands", "head-and-neck/salivary-glands"),
        ("Mucosal Melanoma of the Head and Neck", "mucosal-melanoma-of-the-head-and-neck", "head-and-neck/mucosal-melanoma-of-the-head-and-neck"),
        ("Cutaneous Carcinoma of the Head and Neck", "cutaneous-carcinoma-of-the-head-and-neck", "head-and-neck/cutaneous-carcinoma-of-the-head-and-neck"),
    ],
    
    "lower-gastrointestinal-tract": [
        ("Colon and Rectum", "colon-and-rectum", "lower-gastrointestinal-tract/colon-and-rectum"),
        ("Anal Canal", "anal-canal", "lower-gastrointestinal-tract/anal-canal"),
        ("Appendix", "appendix", "lower-gastrointestinal-tract/appendix"),
    ],
    
    "hepatobiliary-system": [
        ("Liver", "liver", "hepatobiliary-system/liver"),
        ("Intrahepatic Bile Ducts", "intrahepatic-bile-ducts", "hepatobiliary-system/intrahepatic-bile-ducts"),
        ("Perihilar Bile Ducts", "perihilar-bile-ducts", "hepatobiliary-system/perihilar-bile-ducts"),
        ("Distal Bile Duct", "distal-bile-duct", "hepatobiliary-system/distal-bile-duct"),
        ("Gallbladder", "gallbladder", "hepatobiliary-system/gallbladder"),
        ("Exocrine Pancreas", "exocrine-pancreas", "hepatobiliary-system/exocrine-pancreas"),
        ("Ampulla of Vater", "ampulla-of-vater", "hepatobiliary-system/ampulla-of-vater"),
    ],
    
    "neuroendocrine-tumors": [
        ("Neuroendocrine Tumors of the Stomach", "neuroendocrine-tumors-of-the-stomach", "neuroendocrine-tumors/neuroendocrine-tumors-of-the-stomach"),
        ("Neuroendocrine Tumors of the Duodenum and Ampulla of Vater", "neuroendocrine-tumors-of-the-duodenum-and-ampulla-of-vater", "neuroendocrine-tumors/neuroendocrine-tumors-of-the-duodenum-and-ampulla-of-vater"),
        ("Neuroendocrine Tumors of the Jejunum and Ileum", "neuroendocrine-tumors-of-the-jejunum-and-ileum", "neuroendocrine-tumors/neuroendocrine-tumors-of-the-jejunum-and-ileum"),
        ("Neuroendocrine Tumors of the Appendix", "neuroendocrine-tumors-of-the-appendix", "neuroendocrine-tumors/neuroendocrine-tumors-of-the-appendix"),
        ("Neuroendocrine Tumors of the Colon and Rectum", "neuroendocrine-tumors-of-the-colon-and-rectum", "neuroendocrine-tumors/neuroendocrine-tumors-of-the-colon-and-rectum"),
        ("Neuroendocrine Tumors of the Pancreas", "neuroendocrine-tumors-of-the-pancreas", "neuroendocrine-tumors/neuroendocrine-tumors-of-the-pancreas"),
    ],
    
    "soft-tissue-sarcoma": [
        ("Gastrointestinal Stromal Tumor", "gastrointestinal-stromal-tumor", "soft-tissue-sarcoma/gastrointestinal-stromal-tumor"),
        ("Soft Tissue Sarcoma of the Abdomen and Thoracic Visceral Organs", "soft-tissue-sarcoma-of-the-abdomen-and-thoracic-visceral-organs", "soft-tissue-sarcoma/soft-tissue-sarcoma-of-the-abdomen-and-thoracic-visceral-organs"),
        ("Soft Tissue Sarcoma of the Head and Neck", "soft-tissue-sarcoma-of-the-head-and-neck", "soft-tissue-sarcoma/soft-tissue-sarcoma-of-the-head-and-neck"),
        ("Soft Tissue Sarcoma of the Retroperitoneum", "soft-tissue-sarcoma-of-the-retroperitoneum", "soft-tissue-sarcoma/soft-tissue-sarcoma-of-the-retroperitoneum"),
        ("Soft Tissue Sarcoma of the Trunk and Extremities", "soft-tissue-sarcoma-of-the-trunk-and-extremities", "soft-tissue-sarcoma/soft-tissue-sarcoma-of-the-trunk-and-extremities"),
        ("Soft Tissue Sarcoma of Unusual Histologies and Sites", "soft-tissue-sarcoma-of-unusual-histologies-and-sites", "soft-tissue-sarcoma/soft-tissue-sarcoma-of-unusual-histologies-and-sites"),
    ],
    
    "female-reproductive-organs": [
        ("Cervix Uteri", "cervix-uteri", "female-reproductive-organs/cervix-uteri"),
        ("Corpus Uteri Carcinoma and Carcinosarcoma", "corpus-uteri-carcinoma-and-carcinosarcoma", "female-reproductive-organs/corpus-uteri-carcinoma-and-carcinosarcoma"),
        ("Corpus Uteri Sarcoma", "corpus-uteri-sarcoma", "female-reproductive-organs/corpus-uteri-sarcoma"),
        ("Gestational Trophoblastic Neoplasms", "gestational-trophoblastic-neoplasms", "female-reproductive-organs/gestational-trophoblastic-neoplasms"),
        ("Ovary, Fallopian Tube, and Primary Peritoneal Carcinoma", "ovary-fallopian-tube-and-primary-peritoneal-carcinoma", "female-reproductive-organs/ovary-fallopian-tube-and-primary-peritoneal-carcinoma"),
        ("Vagina", "vagina", "female-reproductive-organs/vagina"),
        ("Vulva", "vulva", "female-reproductive-organs/vulva"),
    ],
    
    "endocrine-system": [
        ("Adrenal Cortical Carcinoma", "adrenal-cortical-carcinoma", "endocrine-system/adrenal-cortical-carcinoma"),
        ("Adrenal Neuroendocrine Tumors", "adrenal-neuroendocrine-tumors", "endocrine-system/adrenal-neuroendocrine-tumors"),
        ("Parathyroid", "parathyroid", "endocrine-system/parathyroid"),
        ("Thyroid - Differentiated and Anaplastic Carcinoma", "thyroid-differentiated-and-anaplastic-carcinoma", "endocrine-system/thyroid-differentiated-and-anaplastic-carcinoma"),
        ("Thyroid - Medullary Carcinoma", "thyroid-medullary-carcinoma", "endocrine-system/thyroid-medullary-carcinoma"),
    ],
    
    "hematologic-malignancies": [
        ("Hodgkin and Non-Hodgkin Lymphoma", "hodgkin-and-non-hodgkin-lymphoma", "hematologic-malignancies/hodgkin-and-non-hodgkin-lymphoma"),
        ("Pediatric Hodgkin and Non-Hodgkin Lymphoma", "pediatric-hodgkin-and-non-hodgkin-lymphoma", "hematologic-malignancies/pediatric-hodgkin-and-non-hodgkin-lymphoma"),
        ("Primary Cutaneous Lymphoma", "primary-cutaneous-lymphoma", "hematologic-malignancies/primary-cutaneous-lymphoma"),
        ("Plasma Cell Myeloma and Plasma Cell Disorders", "plasma-cell-myeloma-and-plasma-cell-disorders", "hematologic-malignancies/plasma-cell-myeloma-and-plasma-cell-disorders"),
        ("Leukemia", "leukemia", "hematologic-malignancies/leukemia"),
    ],
}


def seed_diseases():
    """Seed the disease sites for each section."""
    
    with app.app_context():
        stats = {'added': 0, 'updated': 0, 'deleted': 0, 'unchanged': 0}
        
        for section_slug, diseases in SECTIONS_AND_DISEASES.items():
            # Get the body section
            section = AJCCBodySection.query.filter_by(slug=section_slug).first()
            if not section:
                print(f"Warning: Section '{section_slug}' not found, skipping...")
                continue
            
            print(f"\n=== {section.section_name} ===")
            
            # Get existing diseases for this section
            existing_diseases = {d.slug: d for d in AJCCDiseaseSite.query.filter_by(body_section_id=section.id).all()}
            new_slugs = {d[1] for d in diseases}
            
            # Delete diseases not in the new list
            for slug, disease in existing_diseases.items():
                if slug not in new_slugs:
                    print(f"  - Deleting: {disease.disease_name}")
                    db.session.delete(disease)
                    stats['deleted'] += 1
            
            # Add or update diseases
            for disease_name, disease_slug, ajcc_url_path in diseases:
                if disease_slug in existing_diseases:
                    # Update existing
                    disease = existing_diseases[disease_slug]
                    if disease.disease_name != disease_name or disease.ajcc_url_path != ajcc_url_path:
                        disease.disease_name = disease_name
                        disease.ajcc_url_path = ajcc_url_path
                        print(f"  ~ Updated: {disease_name}")
                        stats['updated'] += 1
                    else:
                        stats['unchanged'] += 1
                else:
                    # Add new
                    new_disease = AJCCDiseaseSite(
                        body_section_id=section.id,
                        disease_name=disease_name,
                        slug=disease_slug,
                        ajcc_url_path=ajcc_url_path
                    )
                    db.session.add(new_disease)
                    print(f"  + Added: {disease_name}")
                    stats['added'] += 1
        
        # Commit changes
        db.session.commit()
        
        print(f"\n=== Summary ===")
        print(f"  Added: {stats['added']}")
        print(f"  Updated: {stats['updated']}")
        print(f"  Deleted: {stats['deleted']}")
        print(f"  Unchanged: {stats['unchanged']}")
        print("\nDone!")


if __name__ == "__main__":
    seed_diseases()
