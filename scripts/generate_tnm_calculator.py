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

# Disease-specific defaults with comprehensive prompt guidance
# Each disease needs detailed notes specifying T4b/T4a criteria, mnemonics, and disease-specific features
DISEASE_DEFAULTS = {
    'oropharynx': {
        'features': ['HPV+ Staging', 'HPV- Staging', 'ENE Criteria'],
        'notes': '''CRITICAL OROPHARYNX-SPECIFIC REQUIREMENTS:

1. HPV STATUS SELECTOR: First input must be HPV status (Positive/Negative/Unknown)
   - HPV+ and HPV- have COMPLETELY DIFFERENT N staging systems
   - Show/hide relevant fields based on HPV status selection

2. T4b FEATURES (use checkboxes, any = T4b):
   - Prevertebral fascia invasion
   - Carotid artery encasement (>270 degrees)
   - Skull base invasion (clivus, pterygoid plates)
   - Mediastinal extension
   Mnemonic suggestion: "PACE" (Prevertebral, Artery, Cranium/skull base, Extension to mediastinum)

3. T4a FEATURES (use checkboxes, any = T4a):
   - Larynx invasion (epiglottis, arytenoids, cartilage)
   - Extrinsic tongue muscles (genioglossus, hyoglossus, styloglossus, palatoglossus)
   - Medial pterygoid muscle
   - Hard palate
   - Mandible
   Mnemonic suggestion: "HELP-M" (Hard palate, Extrinsic tongue, Larynx, Pterygoid medial, Mandible)

4. SIZE CUTOFFS:
   - T1: ≤2 cm
   - T2: >2 cm to ≤4 cm
   - T3: >4 cm OR lingual surface of epiglottis (HPV- only)

5. N STAGING - HPV-POSITIVE (simpler):
   - N0: No nodes
   - N1: Ipsilateral nodes, all ≤6 cm
   - N2: Bilateral or contralateral nodes, any >3cm but all <6 cm
   - N3: Any node >6 cm
   Note: ENE does NOT change imaging N stage for HPV+

6. N STAGING - HPV-NEGATIVE (complex):
   - N1: Single ipsilateral ≤3 cm, no ENE
   - N2a: Single ipsilateral >3 to 6 cm, no ENE
   - N2b: Multiple ipsilateral, all <6 cm, no ENE
   - N2c: Bilateral or contralateral, all <6 cm, no ENE
   - N3a: Any node with clinical ENE
   - N3b: Any node >6 cm

7. Inputs needed: tumor size (cm), largest node size (cm), ipsilateral node count, contralateral node count, ENE checkbox

8. PITFALLS to include:
   - Overcalling carotid encasement (≤270° is NOT T4b)
   - Confusing intrinsic vs extrinsic tongue muscles (only extrinsic = T4a)
   - Missing retropharyngeal nodes
   - Not confirming HPV status before staging''',
        'description': 'HPV+ and HPV- staging with detailed criteria'
    },
    'larynx': {
        'features': ['Subsites', 'Cartilage Invasion', 'Voice Preservation'],
        'notes': '''CRITICAL LARYNX-SPECIFIC REQUIREMENTS:

1. SUBSITE SELECTOR: First input should be subsite (Glottis/Supraglottis/Subglottis)
   - Different T staging criteria for each subsite
   - Show/hide relevant criteria based on subsite

2. T4b FEATURES (use checkboxes, any = T4b):
   - Prevertebral fascia invasion
   - Carotid artery encasement (>270 degrees)
   - Mediastinal structure involvement
   Mnemonic suggestion: "PACE" (Prevertebral, Artery encasement, Central mediastinal, Extensive soft tissue)

3. T4a FEATURES (use checkboxes, any = T4a):
   - Through OUTER cortex of thyroid cartilage (complete breakthrough)
   - Trachea invasion
   - Soft tissues of neck (beyond strap muscles)
   - Deep extrinsic tongue muscles
   - Strap muscles
   - Thyroid gland invasion
   - Esophagus invasion
   Mnemonic suggestion: "TESTS-ET" (Through cartilage, Esophagus, Soft tissues, Trachea, Strap muscles, Extrinsic Tongue, Thyroid)

4. T3 KEY CRITERIA (critical distinction from T2):
   - Vocal cord FIXATION (not just impaired mobility!)
   - Paraglottic space invasion
   - Inner cortex of thyroid cartilage ONLY (not through outer)
   - For Supraglottis: Pre-epiglottic space invasion

5. T2 vs T3 CRITICAL DISTINCTION:
   - T2 = Extension to adjacent subsites WITH normal OR impaired mobility
   - T3 = Vocal cord FIXATION (complete loss of movement)
   - IMPAIRED ≠ FIXED - This is a common pitfall

6. T1 GLOTTIC SUBCATEGORIES:
   - T1a: Limited to ONE vocal cord (may include anterior/posterior commissure with normal mobility)
   - T1b: Involves BOTH vocal cords

7. Size cutoffs for supraglottic/subglottic (not glottic):
   - T1: Limited to one subsite with normal mobility
   - T2: Extends to adjacent subsites with normal/impaired mobility
   - T3: Fixation or paraglottic space or inner cortex

8. CARTILAGE INVASION DECISION TREE:
   - Inner cortex erosion only = T3
   - Through outer cortex (complete breakthrough) = T4a
   - Include imaging tip: CT bone windows vs MRI for cartilage assessment

9. N STAGING (same as other head and neck):
   - Include size thresholds and laterality
   - ENE criteria

10. VOICE PRESERVATION notes in clinical implications:
    - T1-T2: Voice-preserving options (radiation, laser resection)
    - T3: Consider organ preservation protocols
    - T4: Likely requires total laryngectomy

11. PITFALLS to include:
    - Confusing impaired mobility with fixation (T2 vs T3)
    - Inner cortex vs outer cortex cartilage invasion (T3 vs T4a)
    - Missing paraglottic space invasion
    - Not specifying subsite''',
        'description': 'Glottic, supraglottic, and subglottic subsites with cartilage invasion criteria'
    },
    'breast': {
        'features': ['Prognostic Staging', 'Biomarkers', 'Oncotype DX'],
        'notes': '''CRITICAL BREAST-SPECIFIC REQUIREMENTS:

1. INCLUDE BOTH STAGING SYSTEMS:
   - Anatomic staging (T, N, M only)
   - Prognostic staging (requires biomarkers)

2. T STAGING BY SIZE (use number input):
   - Tis: Carcinoma in situ
   - T1mi: ≤1 mm
   - T1a: >1 mm to ≤5 mm
   - T1b: >5 mm to ≤10 mm
   - T1c: >10 mm to ≤20 mm
   - T2: >20 mm to ≤50 mm
   - T3: >50 mm

3. T4 FEATURES (use checkboxes):
   - T4a: Chest wall invasion (not pectoralis muscle alone)
   - T4b: Skin involvement (ulceration, satellite nodules, edema/peau d'orange)
   - T4c: Both T4a and T4b
   - T4d: Inflammatory breast cancer

4. N STAGING:
   - N1: 1-3 axillary nodes
   - N2: 4-9 axillary nodes OR internal mammary without axillary
   - N3: ≥10 axillary OR infraclavicular OR supraclavicular OR internal mammary with axillary

5. PROGNOSTIC STAGING requires:
   - Tumor grade (1-3) selector
   - ER status (Positive/Negative)
   - PR status (Positive/Negative)
   - HER2 status (Positive/Negative)
   Note: These change the final stage group!

6. Include note about Oncotype DX for ER+/HER2- tumors

7. IMAGING TIPS:
   - Chest wall = ribs and intercostal muscles (NOT pectoralis alone)
   - Peau d'orange vs inflammatory cancer
   - Axillary node morphology criteria''',
        'description': 'Anatomic and prognostic staging with biomarkers'
    },
    'lung': {
        'features': ['Size Cutoffs', 'Pleural Invasion', 'Separate Nodules'],
        'notes': '''CRITICAL LUNG (NSCLC)-SPECIFIC REQUIREMENTS:

1. T STAGING - SIZE IS CRITICAL (use number input):
   - T1a: ≤1 cm
   - T1b: >1 cm to ≤2 cm
   - T1c: >2 cm to ≤3 cm
   - T2a: >3 cm to ≤4 cm
   - T2b: >4 cm to ≤5 cm
   - T3: >5 cm to ≤7 cm
   - T4: >7 cm

2. T2 FEATURES (any of these, regardless of size up to 5cm):
   - Main bronchus involvement (regardless of distance from carina)
   - Visceral pleura invasion
   - Atelectasis/obstructive pneumonitis extending to hilum

3. T3 FEATURES (checkboxes):
   - Chest wall invasion (including superior sulcus)
   - Phrenic nerve involvement
   - Parietal pericardium invasion
   - Separate nodule in same lobe

4. T4 FEATURES (checkboxes):
   - Mediastinum invasion
   - Heart/great vessels invasion
   - Trachea/carina invasion
   - Recurrent laryngeal nerve
   - Esophagus
   - Vertebral body
   - Separate nodule in DIFFERENT ipsilateral lobe

5. N STAGING:
   - N1: Ipsilateral peribronchial and/or hilar nodes
   - N2: Ipsilateral mediastinal and/or subcarinal nodes
   - N3: Contralateral mediastinal/hilar, scalene, supraclavicular

6. M1 subcategories:
   - M1a: Separate tumor in contralateral lung, pleural nodules, malignant effusion
   - M1b: Single extrathoracic metastasis
   - M1c: Multiple extrathoracic metastases

7. IMAGING TIPS:
   - Visceral pleura invasion signs on CT
   - Chest wall invasion assessment
   - Mediastinal fat plane preservation

8. PITFALLS:
   - Not measuring longest dimension
   - Missing pleural invasion (look for pleural tag sign)
   - Confusing atelectasis with tumor''',
        'description': 'NSCLC staging with detailed size criteria'
    },
    'cervix-uteri': {
        'features': ['FIGO 2018', 'Nodal Staging', 'Parametrium'],
        'notes': '''CRITICAL CERVIX-SPECIFIC REQUIREMENTS:

1. USE FIGO 2018 STAGING (not pure AJCC):
   - Lymph node status is now incorporated
   - Imaging findings matter for staging

2. STAGE I: Confined to cervix
   - IA: Microscopic only (depth ≤5mm)
   - IB1: ≥5mm depth or ≥2cm, <2cm greatest dimension
   - IB2: ≥2cm to <4cm
   - IB3: ≥4cm

3. STAGE II: Beyond cervix, not to pelvic wall
   - IIA: Upper 2/3 vagina, no parametrium
   - IIB: Parametrial invasion

4. STAGE III: Extension to pelvic wall or lower vagina OR hydronephrosis OR nodes
   - IIIA: Lower 1/3 vagina
   - IIIB: Pelvic wall extension or hydronephrosis
   - IIIC1: Pelvic lymph node metastasis
   - IIIC2: Para-aortic lymph node metastasis

5. STAGE IV:
   - IVA: Bladder/rectal mucosa invasion
   - IVB: Distant metastasis

6. KEY INPUTS:
   - Tumor size (cm)
   - Parametrial invasion checkbox
   - Vaginal extension (upper 2/3 vs lower 1/3)
   - Pelvic sidewall extension checkbox
   - Hydronephrosis checkbox
   - Pelvic node involvement checkbox
   - Para-aortic node involvement checkbox
   - Bladder/rectal invasion checkbox

7. IMAGING TIPS:
   - Parametrial invasion assessment on MRI
   - Look for ureteral obstruction
   - T2W for tumor visualization''',
        'description': 'FIGO 2018 staging with nodal incorporation'
    },
    'prostate': {
        'features': ['PSA', 'Gleason Score', 'Grade Groups'],
        'notes': '''CRITICAL PROSTATE-SPECIFIC REQUIREMENTS:

1. T STAGING:
   - T1: Clinically inapparent (incidental)
   - T2a: ≤50% of one lobe
   - T2b: >50% of one lobe
   - T2c: Both lobes
   - T3a: Extraprostatic extension
   - T3b: Seminal vesicle invasion
   - T4: Bladder, rectum, pelvic wall, levator muscles

2. INCLUDE GRADE GROUP SELECTOR (ISUP):
   - Grade Group 1: Gleason ≤6
   - Grade Group 2: Gleason 3+4=7
   - Grade Group 3: Gleason 4+3=7
   - Grade Group 4: Gleason 8
   - Grade Group 5: Gleason 9-10

3. PSA LEVELS affect risk stratification:
   - <10 ng/mL
   - 10-20 ng/mL
   - >20 ng/mL

4. N STAGING:
   - N0: No regional nodes
   - N1: Regional node metastasis

5. IMAGING TIPS:
   - Extraprostatic extension on MRI
   - Seminal vesicle invasion signs
   - Bone scan for M staging''',
        'description': 'Prostate staging with Grade Groups'
    },
    'colon-and-rectum': {
        'features': ['Tumor Deposits', 'Circumferential Margin', 'MSI Status'],
        'notes': '''CRITICAL COLORECTAL-SPECIFIC REQUIREMENTS:

1. T STAGING:
   - Tis: Carcinoma in situ
   - T1: Submucosa invasion
   - T2: Muscularis propria invasion
   - T3: Through muscularis propria into pericolorectal tissues
   - T4a: Visceral peritoneum invasion
   - T4b: Adjacent organ/structure invasion

2. N STAGING (includes tumor deposits):
   - N1a: 1 regional node
   - N1b: 2-3 regional nodes
   - N1c: Tumor deposits WITHOUT nodal metastasis
   - N2a: 4-6 regional nodes
   - N2b: ≥7 regional nodes

3. TUMOR DEPOSITS DEFINITION:
   - Discrete tumor foci in pericolic/perirectal fat
   - No residual lymph node tissue
   - If identifiable node present = nodal metastasis

4. FOR RECTAL CANCER:
   - Circumferential resection margin (CRM) assessment
   - Distance from mesorectal fascia on MRI
   - Extramural vascular invasion (EMVI)

5. IMAGING TIPS:
   - T3 substaging by depth of invasion
   - Peritoneal reflection location
   - EMVI detection on MRI''',
        'description': 'Colorectal staging with tumor deposits criteria'
    },
    'kidney': {
        'features': ['Size', 'Renal Vein', 'IVC Thrombus'],
        'notes': '''CRITICAL RENAL CELL CARCINOMA-SPECIFIC REQUIREMENTS:

1. T STAGING BY SIZE:
   - T1a: ≤4 cm, limited to kidney
   - T1b: >4 cm to ≤7 cm, limited to kidney
   - T2a: >7 cm to ≤10 cm, limited to kidney
   - T2b: >10 cm, limited to kidney

2. T3 (VASCULAR/FAT INVASION):
   - T3a: Renal vein or perinephric fat (not beyond Gerota's fascia)
   - T3b: Tumor thrombus extending into IVC below diaphragm
   - T3c: Tumor thrombus extending into IVC above diaphragm or IVC wall invasion

3. T4 FEATURES:
   - Beyond Gerota's fascia
   - Adrenal gland involvement (direct extension)

4. IVC THROMBUS LEVELS:
   - Level 0: Renal vein only
   - Level I: IVC <2cm above renal vein
   - Level II: IVC below hepatic veins
   - Level III: IVC within hepatic veins (intrahepatic)
   - Level IV: IVC above diaphragm

5. N STAGING:
   - N0: No regional nodes
   - N1: Regional node metastasis

6. IMAGING TIPS:
   - Renal vein thrombus vs bland thrombus
   - IVC thrombus extent on coronal imaging
   - Gerota's fascia assessment''',
        'description': 'RCC staging with vascular invasion levels'
    },
    'melanoma': {
        'features': ['Breslow Depth', 'Ulceration', 'Mitotic Rate'],
        'notes': '''CRITICAL MELANOMA-SPECIFIC REQUIREMENTS:

1. T STAGING BY BRESLOW DEPTH:
   - T1: ≤1.0 mm
     - T1a: <0.8 mm without ulceration
     - T1b: <0.8 mm with ulceration OR 0.8-1.0 mm
   - T2: >1.0 to ≤2.0 mm
     - T2a: Without ulceration
     - T2b: With ulceration
   - T3: >2.0 to ≤4.0 mm
     - T3a/T3b: Based on ulceration
   - T4: >4.0 mm
     - T4a/T4b: Based on ulceration

2. INCLUDE ULCERATION CHECKBOX:
   - Ulceration upstages within each T category

3. N STAGING:
   - N1: 1 node
   - N2: 2-3 nodes OR in-transit/satellite metastases
   - N3: ≥4 nodes OR in-transit with nodal metastases

4. Satellite metastases: Within 2cm of primary
   In-transit metastases: >2cm from primary but before regional nodes

5. M STAGING:
   - M1a: Distant skin, soft tissue, or distant lymph nodes
   - M1b: Lung
   - M1c: Non-CNS visceral sites
   - M1d: CNS

6. Note about LDH elevation as prognostic factor''',
        'description': 'Melanoma staging with Breslow depth'
    },
    'thyroid': {
        'features': ['Age Factor', 'Histology Variants', 'Anaplastic'],
        'notes': '''CRITICAL THYROID-SPECIFIC REQUIREMENTS:

1. AGE-DEPENDENT STAGING (for differentiated thyroid cancer):
   - Age <55: Only Stage I and Stage II exist
     - Stage I: Any T, any N, M0
     - Stage II: Any T, any N, M1
   - Age ≥55: Full staging system applies

2. T STAGING:
   - T1: ≤2 cm, limited to thyroid
     - T1a: ≤1 cm
     - T1b: >1 cm to ≤2 cm
   - T2: >2 cm to ≤4 cm, limited to thyroid
   - T3a: >4 cm, limited to thyroid
   - T3b: Any size with gross extrathyroidal extension into strap muscles
   - T4a: Gross extension into subcutaneous soft tissues, larynx, trachea, esophagus, or recurrent laryngeal nerve
   - T4b: Gross extension into prevertebral fascia, encasing carotid artery, or mediastinal vessels

3. FOR ANAPLASTIC CARCINOMA:
   - All anaplastic = T4
   - T4a: Intrathyroidal
   - T4b: Gross extrathyroidal extension

4. INCLUDE:
   - Age input (critical!)
   - Histology selector (Differentiated vs Anaplastic)
   - Size input
   - Extrathyroidal extension checkboxes

5. N STAGING:
   - N1a: Level VI nodes (pretracheal, paratracheal, prelaryngeal)
   - N1b: Other cervical or retropharyngeal nodes

6. IMAGING TIPS:
   - Strap muscle invasion vs abutment
   - Tracheal invasion assessment
   - Central vs lateral neck nodes''',
        'description': 'Age-based staging with histology variants'
    },
}


# Complete list of FRCR-relevant cancers for batch generation
# (slug, cancer_name, body_section)
BATCH_LIST = [
    # --- Head and Neck ---
    ('oropharynx', 'Oropharynx', 'Head and Neck'),
    ('larynx', 'Larynx', 'Head and Neck'),
    ('thyroid', 'Thyroid', 'Head and Neck'),
    ('nasopharynx', 'Nasopharynx', 'Head and Neck'),
    ('hypopharynx', 'Hypopharynx', 'Head and Neck'),
    ('oral-cavity', 'Oral Cavity', 'Head and Neck'),
    ('salivary-glands', 'Salivary Glands', 'Head and Neck'),
    # --- Thorax ---
    ('lung', 'Lung (NSCLC)', 'Thorax'),
    ('esophagus', 'Esophagus', 'Thorax'),
    ('mesothelioma', 'Pleural Mesothelioma', 'Thorax'),
    # --- Breast ---
    ('breast', 'Breast', 'Breast'),
    # --- Gastrointestinal ---
    ('colon-and-rectum', 'Colon and Rectum', 'Abdomen'),
    ('stomach', 'Stomach (Gastric)', 'Abdomen'),
    ('pancreas', 'Pancreas', 'Abdomen'),
    ('liver', 'Hepatocellular Carcinoma', 'Abdomen'),
    ('cholangiocarcinoma', 'Intrahepatic Cholangiocarcinoma', 'Abdomen'),
    ('gallbladder', 'Gallbladder', 'Abdomen'),
    # --- Genitourinary ---
    ('kidney', 'Kidney (Renal Cell Carcinoma)', 'Abdomen'),
    ('bladder', 'Urinary Bladder', 'Pelvis'),
    ('prostate', 'Prostate', 'Pelvis'),
    ('testis', 'Testis', 'Pelvis'),
    # --- Gynaecological ---
    ('cervix-uteri', 'Cervix Uteri', 'Pelvis'),
    ('endometrium', 'Endometrium (Corpus Uteri)', 'Pelvis'),
    ('ovary', 'Ovary / Fallopian Tube / Peritoneum', 'Pelvis'),
    # --- Skin / Soft Tissue ---
    ('melanoma', 'Cutaneous Melanoma', 'Skin'),
    ('soft-tissue-sarcoma', 'Soft Tissue Sarcoma', 'Musculoskeletal'),
    # --- Bone ---
    ('bone', 'Primary Bone Tumours', 'Musculoskeletal'),
    # --- CNS ---
    ('brain', 'Brain and Spinal Cord Tumours', 'Neuro'),
]


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
    """Generate calculator via Claude API and save to Neon (production DB) + local HTML file."""

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    import json

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
    notes_preview = special_notes[:80] + '...' if len(special_notes) > 80 else special_notes
    print(f"Notes: {notes_preview}")
    print(f"{'='*60}\n")

    # Step 1: Generate HTML via Claude API (needs app context for AJCC data lookup)
    print("[1/3] Generating calculator with RadInsight Intelligence...")
    print("  Calling Claude API (this takes 30-90 seconds)...")

    from app import app
    from tnm_calculator.tnm_generator import generate_calculator_html, extract_algorithm_from_calculator, save_calculator_html_file, get_claude_model

    with app.app_context():
        calculator_html = generate_calculator_html(
            cancer_name=cancer_name,
            body_section=body_section,
            special_notes=special_notes
        )
    print(f"  Calculator HTML: {len(calculator_html):,} chars")

    # Extract algorithm summary (no API call — parses existing HTML)
    algorithm_html = extract_algorithm_from_calculator(calculator_html, cancer_name)
    print(f"  Algorithm HTML: {len(algorithm_html):,} chars")

    # Step 2: Save HTML file locally
    print("\n[2/3] Saving HTML file...")
    file_path = save_calculator_html_file(slug, calculator_html)
    print(f"  Saved to: {file_path}")

    # Step 3: Upsert into Neon (production DB)
    print("\n[3/3] Syncing to Neon (production DB)...")

    engine = create_engine(NEON_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    result = session.execute(
        text("SELECT id FROM tnm_calculator_content WHERE slug = :slug"),
        {'slug': slug}
    )
    existing_row = result.fetchone()

    features_json = json.dumps(special_features) if special_features else '[]'
    model = get_claude_model()

    params = {
        'slug': slug,
        'cancer_name': cancer_name,
        'body_section': body_section,
        'calculator_html': calculator_html,
        'algorithm_html': algorithm_html,
        'description': description,
        'special_features': features_json,
        'model': model,
    }

    if existing_row:
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
        """), params)
        print(f"  Updated existing record in Neon")
    else:
        session.execute(text("""
            INSERT INTO tnm_calculator_content
            (slug, cancer_name, body_section, calculator_html, algorithm_discussion_html,
             staging_system, description, special_features, is_available, generation_model, generated_at, created_at)
            VALUES (:slug, :cancer_name, :body_section, :calculator_html, :algorithm_html,
                    'AJCC 9th Edition', :description, :special_features, true, :model, NOW(), NOW())
        """), params)
        print(f"  Inserted new record in Neon")

    session.commit()

    # Verify
    result = session.execute(
        text("SELECT slug, LENGTH(calculator_html) as html_len FROM tnm_calculator_content WHERE slug = :slug"),
        {'slug': slug}
    )
    row = result.fetchone()
    print(f"  Verified: {row[0]} has {row[1]:,} chars in Neon")
    session.close()

    print(f"\n  SUCCESS — /tnm-calculator/{slug}")


def batch_generate(skip_existing=True, only_slugs=None):
    """Generate all calculators in BATCH_LIST sequentially.

    Args:
        skip_existing: If True, skip slugs that already exist in Neon.
        only_slugs: If provided, only generate these slugs (subset of BATCH_LIST).
    """
    import time
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    # Check existing in Neon
    existing_slugs = set()
    if skip_existing:
        engine = create_engine(NEON_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        rows = session.execute(text("SELECT slug FROM tnm_calculator_content")).fetchall()
        existing_slugs = {r[0] for r in rows}
        session.close()

    # Filter batch list
    todo = []
    for slug, cancer_name, body_section in BATCH_LIST:
        if only_slugs and slug not in only_slugs:
            continue
        if slug in existing_slugs:
            print(f"  SKIP {slug} (already exists in Neon)")
            continue
        todo.append((slug, cancer_name, body_section))

    if not todo:
        print("\nNothing to generate — all calculators already exist.")
        return

    print(f"\n{'='*60}")
    print(f"BATCH TNM Calculator Generation")
    print(f"{'='*60}")
    print(f"Total to generate: {len(todo)}")
    print(f"Estimated cost: ~${len(todo) * 0.24:.2f}")
    print(f"Estimated time: ~{len(todo) * 1}-{len(todo) * 2} minutes")
    print(f"{'='*60}")
    for i, (slug, name, section) in enumerate(todo, 1):
        has_notes = slug in DISEASE_DEFAULTS
        print(f"  {i:2d}. {slug:30s} | {name:35s} | {section:20s} | {'+ notes' if has_notes else 'generic'}")
    print(f"{'='*60}\n")

    results = {'success': [], 'failed': []}
    start_time = time.time()

    for i, (slug, cancer_name, body_section) in enumerate(todo, 1):
        print(f"\n[{i}/{len(todo)}] Generating: {cancer_name} ({slug})")
        print(f"{'-'*50}")
        t0 = time.time()
        try:
            generate_and_sync(slug, cancer_name, body_section)
            elapsed = time.time() - t0
            results['success'].append((slug, elapsed))
            print(f"  Completed in {elapsed:.0f}s")
        except Exception as e:
            elapsed = time.time() - t0
            results['failed'].append((slug, str(e)))
            print(f"  FAILED after {elapsed:.0f}s: {e}")

        # Brief pause between API calls to be respectful
        if i < len(todo):
            time.sleep(2)

    # Summary
    total_time = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"BATCH GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"Total time: {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"Success: {len(results['success'])}")
    print(f"Failed:  {len(results['failed'])}")

    if results['success']:
        print(f"\nSuccessful:")
        for slug, elapsed in results['success']:
            print(f"  {slug:30s} ({elapsed:.0f}s)")

    if results['failed']:
        print(f"\nFailed:")
        for slug, error in results['failed']:
            print(f"  {slug:30s} — {error[:80]}")

    print(f"\nNext steps:")
    print(f"1. git add tnm_calculator/calculators/")
    print(f"2. git commit -m 'Add batch-generated TNM calculators'")
    print(f"3. git push && vercel --prod")
    print()


def main():
    parser = argparse.ArgumentParser(description='Generate TNM Calculator and sync to Neon')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Single generation
    single = subparsers.add_parser('generate', help='Generate a single calculator')
    single.add_argument('slug', help='URL slug (e.g., larynx, breast)')
    single.add_argument('cancer_name', help='Display name (e.g., "Larynx", "Breast")')
    single.add_argument('body_section', help='Body section (e.g., "Head and Neck", "Thorax")')
    single.add_argument('--notes', '-n', help='Special notes for AI generation')
    single.add_argument('--features', '-f', nargs='+', help='Special features (space-separated)')
    single.add_argument('--description', '-d', help='Brief description')

    # Batch generation
    batch = subparsers.add_parser('batch', help='Batch generate all calculators')
    batch.add_argument('--include-existing', action='store_true',
                       help='Regenerate even if calculator already exists in Neon')
    batch.add_argument('--only', nargs='+', help='Only generate specific slugs (space-separated)')

    # List available
    subparsers.add_parser('list', help='List all cancers in batch list and their status')

    args = parser.parse_args()

    if args.command == 'generate':
        generate_and_sync(
            slug=args.slug,
            cancer_name=args.cancer_name,
            body_section=args.body_section,
            special_notes=args.notes,
            special_features=args.features,
            description=args.description
        )
    elif args.command == 'batch':
        batch_generate(
            skip_existing=not args.include_existing,
            only_slugs=set(args.only) if args.only else None,
        )
    elif args.command == 'list':
        list_status()
    else:
        parser.print_help()


def list_status():
    """Show all cancers and whether they exist in Neon."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(NEON_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    rows = session.execute(text(
        "SELECT slug, LENGTH(calculator_html) as html_len FROM tnm_calculator_content"
    )).fetchall()
    existing = {r[0]: r[1] for r in rows}
    session.close()

    print(f"\n{'Slug':30s} | {'Cancer':35s} | {'Section':20s} | {'Status':15s} | Notes")
    print(f"{'-'*130}")
    for slug, cancer_name, body_section in BATCH_LIST:
        has_notes = slug in DISEASE_DEFAULTS
        if slug in existing:
            status = f"EXISTS ({existing[slug]:,} chars)"
        else:
            status = "PENDING"
        notes_flag = '+ detailed notes' if has_notes else ''
        print(f"{slug:30s} | {cancer_name:35s} | {body_section:20s} | {status:15s} | {notes_flag}")

    # Show extras in DB not in BATCH_LIST
    batch_slugs = {s for s, _, _ in BATCH_LIST}
    extras = [s for s in existing if s not in batch_slugs]
    if extras:
        print(f"\nExtra calculators in DB (not in batch list):")
        for s in sorted(extras):
            print(f"  {s:30s} ({existing[s]:,} chars)")
    print()


if __name__ == '__main__':
    main()
