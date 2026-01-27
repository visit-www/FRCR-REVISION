"""
AI TNM Staging Intelligence Service

This module provides Claude API integration for generating intelligent TNM staging
summaries for oncological diagnoses. It is COMPLETELY SEPARATE from ai_prelim.py.

Design Philosophy:
- Single responsibility: TNM staging intelligence ONLY
- Expert onco-radiologist perspective for MDT/tumour boards
- Focus on imaging-relevant criteria and staging thresholds
- Never invent TNM definitions - always anchor to internal AJCC database
- Lazy-loaded: only called when user explicitly requests TNM analysis

Prompt Version: v1
Last Updated: January 2026
"""

import json
import os
import re
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any

import requests


class AiTnmError(Exception):
    """Raised when TNM intelligence generation fails."""
    pass


# ============================================================================
# ONCOLOGIC DETECTION (Deterministic, No AI)
# ============================================================================

ONCOLOGIC_KEYWORDS = [
    "cancer",
    "carcinoma",
    "tumor",
    "tumour",
    "malignancy",
    "malignant",
    "sarcoma",
    "lymphoma",
    "leukemia",
    "leukaemia",
    "melanoma",
    "adenocarcinoma",
    "squamous cell",
    "metastatic",
    "metastasis",
    "metastases",
    "neoplasm",
    "neoplastic",
    "blastoma",
    "myeloma",
]


# ============================================================================
# AJCC TNM VERSION MAPPING
# ============================================================================
# Maps disease slugs to their AJCC edition and the year that edition was released.
# Diseases not in this map default to AJCC 8th Edition.
# Source: AJCC Cancer Staging Manual version release documentation

AJCC_VERSION_9_DISEASES = {
    # Head and Neck
    "salivary-glands": 2026,                    # Major Salivary Glands
    "nasopharynx": 2025,                        # Nasopharynx
    "oropharynx-hpv-associated": 2026,          # HPV-mediated p16+ Oropharynx
    
    # Digestive System
    "appendix": 2023,                           # Appendix Carcinoma
    "anus": 2023,                               # Anus
    
    # Neuroendocrine Tumors
    "neuroendocrine-tumors-of-the-stomach": 2024,
    "neuroendocrine-tumors-of-the-duodenum-and-ampulla-of-vater": 2024,
    "neuroendocrine-tumors-of-the-jejunum-and-ileum": 2024,
    "neuroendocrine-tumors-of-the-appendix": 2024,
    "neuroendocrine-tumors-of-the-colon-and-rectum": 2024,
    "neuroendocrine-tumors-of-the-pancreas": 2024,
    
    # Thorax
    "thymus": 2025,                             # Thymus
    "lung": 2025,                               # Lung
    "diffuse-pleural-mesothelioma": 2025,       # Pleural Mesothelioma
    
    # Gynecological
    "vulva": 2024,                              # Vulva
    "cervix-uteri": 2021,                       # Cervix Uteri
    
    # CNS
    "brain-and-spinal-cord": 2023,              # Brain and Spinal Cord
}


def get_ajcc_version(disease_slug: str, diagnosis_year: int = None) -> tuple:
    """
    Get the correct AJCC edition for a disease.
    
    Args:
        disease_slug: The slug of the disease site
        diagnosis_year: The year of diagnosis (for future-proofing)
        
    Returns:
        Tuple of (edition_string, release_year) e.g., ("9th", 2025)
    """
    if disease_slug in AJCC_VERSION_9_DISEASES:
        release_year = AJCC_VERSION_9_DISEASES[disease_slug]
        return ("9th", release_year)
    
    # Default to 8th Edition (released 2017)
    return ("8th", 2017)


def format_tnm_version(disease_slug: str, year: int = None) -> str:
    """
    Format the full TNM version string for display.
    
    Args:
        disease_slug: The slug of the disease site
        year: Not used (kept for backward compatibility)
        
    Returns:
        Formatted string:
        - "AJCC 9th Edition (release_year)" for 9th Edition diseases
        - "AJCC 8th Edition" for 8th Edition diseases (no year shown)
    """
    edition, release_year = get_ajcc_version(disease_slug)
    
    if edition == "9th":
        # Show release year for 9th Edition
        return f"AJCC 9th Edition ({release_year})"
    else:
        # No year for 8th Edition
        return "AJCC 8th Edition"


def is_oncologic_diagnosis(diagnosis: str) -> bool:
    """
    Determine if a diagnosis requires TNM staging consideration.
    
    This is a deterministic, keyword-based check - no AI involved.
    Case-insensitive matching.
    
    Args:
        diagnosis: The diagnosis text
        
    Returns:
        True if oncologic keywords detected, False otherwise
    """
    if not diagnosis:
        return False
    
    diagnosis_lower = diagnosis.lower()
    return any(keyword in diagnosis_lower for keyword in ONCOLOGIC_KEYWORDS)


# ============================================================================
# ESSENTIAL TNM KEY CONCEPTS (IARC-sourced, No AI)
# ============================================================================

# Cache for essential TNM data (loaded once)
_ESSENTIAL_TNM_DATA = None

# Cancer type keywords for matching diagnoses to Essential TNM entries
ESSENTIAL_TNM_CANCER_KEYWORDS = {
    "breast": ["breast", "mammary"],
    "cervical": ["cervical", "cervix", "uterine cervix"],
    "oesophageal": ["oesophageal", "esophageal", "oesophagus", "esophagus"],
    "colorectal": ["colorectal", "colon", "rectal", "rectum", "colonic"],
    "liver": ["liver", "hepatocellular", "hcc", "hepatobiliary", "hepatic"],
    "ovarian": ["ovarian", "ovary", "fallopian"],
    "prostate": ["prostate", "prostatic"],
    "lymphoma": ["lymphoma", "hodgkin", "non-hodgkin"],
}


def _load_essential_tnm_data() -> list:
    """
    Load Essential TNM data from static JSON file.
    
    Returns cached data if already loaded.
    """
    global _ESSENTIAL_TNM_DATA
    
    if _ESSENTIAL_TNM_DATA is not None:
        return _ESSENTIAL_TNM_DATA
    
    try:
        import os
        json_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'static',
            'essential_tnm_data.json'
        )
        
        with open(json_path, 'r') as f:
            _ESSENTIAL_TNM_DATA = json.load(f)
        
        return _ESSENTIAL_TNM_DATA
    except Exception as e:
        print(f"[AI_TNM] Error loading essential TNM data: {e}")
        return []


def get_essential_tnm_for_cancer(diagnosis: str) -> Optional[Dict]:
    """
    Get Essential TNM key concepts for a cancer diagnosis.
    
    Matches diagnosis text against known cancer types from IARC Essential TNM Guide.
    
    Args:
        diagnosis: Cancer diagnosis text
        
    Returns:
        Dict with:
            - cancer_type: Matched cancer type
            - title: Display title
            - key_points: List of key staging points
            - figure_id: ID for the flowchart figure
            - figure_description: Caption for the figure
            - cloudinary_url: Direct URL to the figure on Cloudinary
            - attribution: IARC attribution string
            - logo_figure_id: ID for IARC logo
            - logo_cloudinary_url: Direct URL to IARC logo on Cloudinary
        Or None if no match
    """
    if not diagnosis:
        return None
    
    diagnosis_lower = diagnosis.lower()
    data = _load_essential_tnm_data()
    
    if not data:
        return None
    
    # Find IARC logo (index 0)
    logo_entry = None
    for entry in data:
        if entry.get('figure_id') == 'essential_tnm_IACR_logo':
            logo_entry = entry
            break
    
    # Match diagnosis to cancer type
    for cancer_type, keywords in ESSENTIAL_TNM_CANCER_KEYWORDS.items():
        if any(keyword in diagnosis_lower for keyword in keywords):
            # Find matching entry in data
            for entry in data:
                if entry.get('cancer_type') == cancer_type and entry.get('key_points'):
                    return {
                        'cancer_type': cancer_type,
                        'title': entry.get('title', f'{cancer_type.title()} Cancer Essential TNM'),
                        'key_points': entry.get('key_points', []),
                        'figure_id': entry.get('figure_id'),
                        'figure_description': entry.get('figure_description', ''),
                        'cloudinary_url': entry.get('cloudinary_url'),
                        'attribution': entry.get('attribution', 'IARC Essential TNM Guide (CC BY-NC-ND 3.0 IGO)'),
                        'logo_figure_id': logo_entry.get('figure_id') if logo_entry else None,
                        'logo_cloudinary_url': logo_entry.get('cloudinary_url') if logo_entry else None,
                        'supplementary_table_id': entry.get('supplementary_table_id'),
                    }
    
    return None


def format_essential_tnm_markdown(essential_data: Dict) -> str:
    """
    Format Essential TNM key concepts as Markdown for injection into AI output.
    
    Uses Cloudinary URLs directly from essential_data.
    
    Args:
        essential_data: Dict from get_essential_tnm_for_cancer()
        
    Returns:
        Formatted Markdown string with key concepts, figure, and attribution
    """
    if not essential_data:
        return ""
    
    title = essential_data.get('title', 'Essential TNM Key Concepts')
    key_points = essential_data.get('key_points', [])
    figure_description = essential_data.get('figure_description', '')
    attribution = essential_data.get('attribution', 'IARC Essential TNM Guide')
    cloudinary_url = essential_data.get('cloudinary_url')
    logo_cloudinary_url = essential_data.get('logo_cloudinary_url')
    
    # Build Markdown
    lines = [
        "",
        "---",
        "",
        f"## 📋 {title}",
        "",
        "### Key Points for Staging",
        "",
    ]
    
    # Add numbered key points
    for i, point in enumerate(key_points, 1):
        lines.append(f"{i}. {point}")
    
    lines.append("")
    
    # Add figure with Cloudinary URL
    if cloudinary_url:
        lines.extend([
            f'<div style="margin: 1.5rem 0; text-align: center;">',
            f'    <img src="{cloudinary_url}" alt="{title}" style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">',
            f'    <p style="font-size: 0.85em; color: #666; margin-top: 0.5rem; font-style: italic;">{figure_description}</p>',
            f'</div>',
            "",
        ])
    
    # Add IARC attribution with logo
    lines.extend([
        "---",
        "",
        f'<div style="display: flex; align-items: center; gap: 12px; margin-top: 1rem;">',
    ])
    
    if logo_cloudinary_url:
        lines.append(f'    <img src="{logo_cloudinary_url}" alt="IARC Logo" style="height: 40px; width: auto;">')
    
    lines.extend([
        f'    <span style="font-size: 0.85em; color: #666; font-style: italic;">Source: {attribution}</span>',
        f'</div>',
        "",
    ])
    
    return "\n".join(lines)


# ============================================================================
# AJCC DATABASE MAPPING (Deterministic, No AI)
# ============================================================================

def _map_to_ajcc_site(
    diagnosis: str,
    module: str = None,
    body_part: str = None
) -> Optional[Dict]:
    """
    Map diagnosis to AJCC disease site using internal database.
    
    Uses AJCCDiseaseMapping table if populated, falls back to keyword matching.
    
    Args:
        diagnosis: Cancer diagnosis text
        module: FRCR module (optional)
        body_part: Body part hint (optional)
        
    Returns:
        Dict with keys:
            - disease_site_id
            - disease_name
            - section_name
            - section_slug
            - disease_slug
            - tnm_version
            - has_staging_data
        Or None if no match found
    """
    try:
        from flask import has_app_context
        if not has_app_context():
            return None
            
        from models import (
            AJCCDiseaseSite, AJCCBodySection, AJCCStagingData,
            AJCCDiseaseMapping, AJCCDiagnosisYear, FRCRModule, BodyPart
        )
        
        diagnosis_lower = diagnosis.lower().strip()
        
        # Strategy 1: Try to match via AJCCDiseaseMapping (if module/body_part provided)
        if module or body_part:
            query = AJCCDiseaseMapping.query
            
            if module:
                try:
                    frcr_module = FRCRModule(module) if isinstance(module, str) else module
                    query = query.filter_by(frcr_module=frcr_module)
                except (ValueError, KeyError):
                    pass
            
            if body_part:
                try:
                    body_part_enum = BodyPart(body_part) if isinstance(body_part, str) else body_part
                    query = query.filter_by(body_part=body_part_enum)
                except (ValueError, KeyError):
                    pass
            
            mappings = query.all()
            for mapping in mappings:
                disease_site = mapping.disease_site
                if disease_site:
                    disease_name_lower = disease_site.disease_name.lower()
                    # Check for keyword match
                    if any(word in diagnosis_lower for word in disease_name_lower.split()):
                        return _build_ajcc_result(disease_site)
        
        # Strategy 2: Direct disease site name matching
        disease_sites = AJCCDiseaseSite.query.all()
        best_match = None
        best_score = 0
        
        for disease_site in disease_sites:
            score = _calculate_match_score(diagnosis_lower, disease_site, body_part)
            if score > best_score:
                best_score = score
                best_match = disease_site
        
        if best_match and best_score >= 3:
            return _build_ajcc_result(best_match)
        
        return None
        
    except ImportError:
        return None
    except Exception as e:
        print(f"[AI_TNM] Error mapping to AJCC site: {e}")
        return None


def get_all_candidate_sites(
    diagnosis: str,
    module: str = None,
    body_part: str = None,
    min_score: int = 1
) -> List[Dict]:
    """
    Get ALL candidate cancer sites from a diagnosis string.
    
    Unlike _map_to_ajcc_site which returns the best match,
    this returns ALL potential matches with their scores.
    
    Args:
        diagnosis: Cancer diagnosis text
        module: FRCR module (optional)
        body_part: Body part hint (optional)
        min_score: Minimum score to include (default 1)
        
    Returns:
        List of dicts with keys:
            - disease_site_id
            - disease_name
            - section_name
            - section_slug
            - disease_slug
            - tnm_link
            - has_staging_data
            - score
            - is_recommended (True for highest score)
    """
    try:
        from flask import has_app_context
        if not has_app_context():
            return []
            
        from models import AJCCDiseaseSite
        
        diagnosis_lower = diagnosis.lower().strip()
        
        # Get all disease sites with scores
        candidates = []
        disease_sites = AJCCDiseaseSite.query.all()
        
        for disease_site in disease_sites:
            score = _calculate_match_score(diagnosis_lower, disease_site, body_part)
            if score >= min_score:
                result = _build_ajcc_result(disease_site)
                if result:
                    result['score'] = score
                    candidates.append(result)
        
        # Sort by score (highest first)
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Mark the top one as recommended
        if candidates:
            candidates[0]['is_recommended'] = True
            for c in candidates[1:]:
                c['is_recommended'] = False
        
        return candidates
        
    except ImportError:
        return []
    except Exception as e:
        print(f"[AI_TNM] Error getting candidate sites: {e}")
        return []


def _calculate_match_score(diagnosis_lower: str, disease_site, body_part: str = None) -> int:
    """
    Calculate match score between diagnosis and disease site.
    
    Uses improved matching with:
    - Primary cancer phrase detection (highest priority)
    - Anatomical exclusion patterns (prevents false matches)
    - Contextual keyword matching
    """
    score = 0
    disease_name_lower = disease_site.disease_name.lower()
    section_name = disease_site.body_section.section_name.lower() if disease_site.body_section else ""
    
    # =========================================================================
    # ANATOMICAL EXCLUSION PATTERNS
    # =========================================================================
    # These phrases contain organ keywords but refer to anatomy, not the organ's cancer
    # Format: { "organ": ["phrases that should NOT match this organ's cancer"] }
    # =========================================================================
    # ORGAN KEYWORD MAPPINGS (defined first for use in exclusion checking)
    # =========================================================================
    organ_mappings = {
        "lung": ["lung", "pulmonary", "bronchial", "bronchogenic"],
        "breast": ["breast", "mammary"],
        "liver": ["liver", "hepatic", "hepatocellular", "hcc"],
        "colon": ["colon", "colonic", "colorectal", "rectal", "rectum"],
        "stomach": ["stomach", "gastric"],
        "esophagus": ["esophagus", "esophageal", "oesophagus", "oesophageal"],
        "pancreas": ["pancreas", "pancreatic"],
        "kidney": ["kidney", "renal", "rcc"],
        "bladder": ["bladder", "vesical", "urothelial"],
        "prostate": ["prostate", "prostatic"],
        "thyroid": ["thyroid"],
        "larynx": ["larynx", "laryngeal", "glottic", "supraglottic", "subglottic"],
        "oral": ["oral", "tongue", "floor of mouth", "buccal"],
        "oropharynx": ["oropharynx", "oropharyngeal", "tonsil", "base of tongue"],
        "nasopharynx": ["nasopharynx", "nasopharyngeal"],
        "hypopharynx": ["hypopharynx", "hypopharyngeal", "pyriform"],
        "brain": ["brain", "cerebral", "intracranial", "glioma", "glioblastoma"],
        "cervix": ["cervix", "cervical"],
        "ovary": ["ovary", "ovarian"],
        "endometrium": ["endometrium", "endometrial", "uterus", "uterine"],
        "testis": ["testis", "testicular"],
        "bone": ["bone", "osteosarcoma", "skeletal"],
        "soft tissue": ["soft tissue", "sarcoma"],
    }
    
    anatomical_exclusions = {
        "thyroid": [
            "thyroid cartilage",      # Laryngeal anatomy
            "thyroid cartilage invasion",
            "thyroid cartilage involvement",
            "thyroid cartilage destruction",
            "thyroid notch",
            "thyroid shield",         # Radiation protection
        ],
        "cervix": [
            "cervical spine",         # Spine anatomy
            "cervical vertebra",
            "cervical vertebrae",
            "cervical lymph node",    # Lymph node location
            "cervical lymphadenopathy",
            "cervical node",
            "cervical chain",
            "cervical cord",          # Spinal cord
            "cervical myelopathy",
        ],
        # Metastasis exclusions - these are metastasis TO organ, not primary cancer
        "lung": [
            "lung metastasis",
            "lung metastases",
            "lung mets",
            "pulmonary metastasis",
            "pulmonary metastases",
            "pulmonary mets",
        ],
        "liver": [
            "liver metastasis",
            "liver metastases",
            "liver mets",
            "hepatic metastasis",
            "hepatic metastases",
            "hepatic mets",
        ],
        "bone": [
            "bone metastasis",
            "bone metastases",
            "bone mets",
            "osseous metastasis",
            "osseous metastases",
            "skeletal metastasis",
            "skeletal metastases",
        ],
        "brain": [
            "brain metastasis",
            "brain metastases",
            "brain mets",
            "cerebral metastasis",
            "cerebral metastases",
            "intracranial metastasis",
            "intracranial metastases",
        ],
        "adrenal": [
            "adrenal metastasis",
            "adrenal metastases",
            "adrenal mets",
        ],
    }
    
    # Check if this organ match should be excluded due to anatomical context
    def should_exclude_organ(organ: str, diagnosis: str) -> bool:
        """Check if organ keyword appears only in anatomical/exclusion context."""
        exclusions = anatomical_exclusions.get(organ, [])
        for exclusion_phrase in exclusions:
            if exclusion_phrase in diagnosis:
                # Found exclusion phrase - check if this is the ONLY occurrence
                # Remove the exclusion phrase and see if organ keyword still exists
                remaining = diagnosis.replace(exclusion_phrase, "")
                organ_keywords = organ_mappings.get(organ, [organ])
                if not any(kw in remaining for kw in organ_keywords):
                    return True  # Organ only appears in exclusion context
        return False
    
    # =========================================================================
    # PRIMARY CANCER PHRASE DETECTION (Highest Priority)
    # =========================================================================
    # Patterns like "X cancer", "X carcinoma", "X tumor" at start of diagnosis
    # should receive highest weight
    
    # Adjective to noun mappings for organs (diagnosis often uses adjective form)
    adjective_mappings = {
        "larynx": ["laryngeal", "larynx"],
        "lung": ["pulmonary", "lung", "bronchogenic"],
        "liver": ["hepatic", "liver", "hepatocellular"],
        "kidney": ["renal", "kidney"],
        "bladder": ["vesical", "bladder", "urothelial"],
        "stomach": ["gastric", "stomach"],
        "esophagus": ["esophageal", "oesophageal", "esophagus", "oesophagus"],
        "colon": ["colonic", "colorectal", "colon", "rectal"],
        "pancreas": ["pancreatic", "pancreas"],
        "thyroid": ["thyroid"],
        "breast": ["mammary", "breast"],
        "ovary": ["ovarian", "ovary"],
        "prostate": ["prostatic", "prostate"],
        "cervix": ["cervical", "cervix"],  # Note: cervical also means spine
        "brain": ["cerebral", "brain", "intracranial"],
        "bone": ["osseous", "bone", "skeletal"],
        "oral": ["oral", "tongue", "buccal"],
        "oropharynx": ["oropharyngeal", "oropharynx", "tonsillar"],
        "nasopharynx": ["nasopharyngeal", "nasopharynx"],
        "hypopharynx": ["hypopharyngeal", "hypopharynx", "pyriform"],
        "testis": ["testicular", "testis"],
        "endometrium": ["endometrial", "endometrium", "uterine"],
    }
    
    # Get all possible name forms for this disease
    disease_forms = [disease_name_lower]
    for organ, forms in adjective_mappings.items():
        if organ in disease_name_lower:
            disease_forms.extend(forms)
    
    # Build primary cancer patterns for all forms
    primary_cancer_patterns = []
    cancer_suffixes = ["cancer", "carcinoma", "tumor", "tumour", "malignancy", 
                       "adenocarcinoma", "squamous cell", "scc", "neoplasm"]
    
    for form in disease_forms:
        for suffix in cancer_suffixes:
            primary_cancer_patterns.append(f"{form} {suffix}")
    
    # Check for primary cancer phrase at the beginning (first 50 chars)
    diagnosis_start = diagnosis_lower[:50] if len(diagnosis_lower) > 50 else diagnosis_lower
    for pattern in primary_cancer_patterns:
        if pattern in diagnosis_start:
            score += 20  # High score for primary cancer match at start
            break
    
    # Also check anywhere in diagnosis (but lower score)
    if score < 20:  # Only if not already matched at start
        for pattern in primary_cancer_patterns:
            if pattern in diagnosis_lower:
                score += 12
                break
    
    # =========================================================================
    # EXACT DISEASE NAME MATCH
    # =========================================================================
    if disease_name_lower in diagnosis_lower:
        score += 10
    elif diagnosis_lower in disease_name_lower:
        score += 8
    
    # =========================================================================
    # WORD-LEVEL MATCHING
    # =========================================================================
    disease_words = [w for w in disease_name_lower.split() if len(w) > 3]
    for word in disease_words:
        if word in diagnosis_lower:
            score += 2
    
    # =========================================================================
    # BODY PART HINT BONUS
    # =========================================================================
    if body_part:
        body_part_lower = body_part.lower()
        if body_part_lower in section_name or section_name in body_part_lower:
            score += 3
    
    # =========================================================================
    # ORGAN KEYWORD MATCHING (with exclusion checking)
    # =========================================================================
    for organ, keywords in organ_mappings.items():
        if organ in disease_name_lower:
            # Check if this organ should be excluded due to anatomical context
            if should_exclude_organ(organ, diagnosis_lower):
                continue  # Skip this organ - it's only in anatomical context
            
            if any(kw in diagnosis_lower for kw in keywords):
                score += 5
    
    return score


def _build_ajcc_result(disease_site) -> Dict:
    """Build standardized AJCC result dictionary."""
    from models import AJCCStagingData, AJCCDiagnosisYear
    
    section = disease_site.body_section
    
    # Check if staging data exists
    staging_data = AJCCStagingData.query.filter_by(
        disease_site_id=disease_site.id
    ).first()
    
    # Get latest diagnosis year
    year = None
    if staging_data:
        year_obj = AJCCDiagnosisYear.query.get(staging_data.diagnosis_year_id)
        year = year_obj.year if year_obj else None
    
    section_slug = section.slug if section else ""
    disease_slug = disease_site.slug or ""
    
    # Build TNM link with leading / for absolute path
    # Use /view suffix for unified TNM view (role-aware)
    tnm_link = None
    if section_slug and disease_slug:
        tnm_link = f"/tnm/{section_slug}/{disease_slug}/view"
        if year:
            tnm_link += f"?year={year}"
    
    # Check if data is curated (for student visibility)
    is_curated = staging_data.is_curated if staging_data else False
    
    return {
        "disease_site_id": disease_site.id,
        "disease_name": disease_site.disease_name,
        "section_name": section.section_name if section else None,
        "section_slug": section_slug,
        "disease_slug": disease_slug,
        "tnm_link": tnm_link,
        "tnm_version": format_tnm_version(disease_slug, year),
        "has_staging_data": staging_data is not None,
        "is_curated": is_curated,
        "staging_data_id": staging_data.id if staging_data else None,
    }


def _get_staging_data(disease_site_id: int) -> Optional[Dict]:
    """
    Retrieve complete staging data from database for Claude input.
    
    Returns structured data including:
    - Quick reference TNM tables
    - Explanatory notes
    - Staging rules
    - Images (with URLs)
    """
    try:
        from models import AJCCStagingData, AJCCDiagnosisYear
        import re
        
        staging = AJCCStagingData.query.filter_by(
            disease_site_id=disease_site_id
        ).first()
        
        if not staging:
            return None
        
        # Get year info
        year_obj = AJCCDiagnosisYear.query.get(staging.diagnosis_year_id)
        year = year_obj.year if year_obj else None
        
        # Extract images from HTML content
        images = []
        html_sections = [
            staging.section_1_quick_reference_html,
            staging.section_7_clinical_staging_workup_html,
            staging.section_10_explanatory_notes_html,
        ]
        
        for html in html_sections:
            if html:
                # Find all img tags
                img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', html, re.IGNORECASE)
                for src in img_matches:
                    if src not in images:
                        images.append(src)
        
        return {
            "diagnosis_year": year,
            "tnm_data": staging.get_tnm_data(),
            "t_definitions": staging.get_t_definitions(),
            "n_definitions": staging.get_n_definitions(),
            "m_definitions": staging.get_m_definitions(),
            "stage_groups": staging.get_stage_groups(),
            "quick_reference_html": staging.section_1_quick_reference_html,
            "explanatory_notes_html": staging.section_10_explanatory_notes_html,
            "clinical_staging_workup_html": staging.section_7_clinical_staging_workup_html,
            "staging_rules_html": staging.section_8_staging_rules_html,
            "notes_json": staging.get_json_section('notes') if hasattr(staging, 'get_json_section') else None,
            "imaging_workup_json": staging.get_json_section('imaging_workup') if hasattr(staging, 'get_json_section') else None,
            "images": images,
        }
        
    except Exception as e:
        print(f"[AI_TNM] Error retrieving staging data: {e}")
        return None


# ============================================================================
# CLAUDE PROMPTS (TNM Intelligence Engine - Locked System Prompt)
# ============================================================================

TNM_SYSTEM_PROMPT = """You are an expert oncologic radiologist specializing in TNM staging,
MDT decision-making, and radiology education.

Your role is to transform provided AJCC TNM staging data into
clinically actionable radiology intelligence.

AUTHORITATIVE SOURCE RULE:
• AJCC data provided to you is the single source of truth
  for TNM definitions, cutoffs, and staging rules.
• You must NOT invent, alter, or contradict staging criteria.

ALLOWED REASONING:
You MAY use general, non-proprietary radiology knowledge to:
• Explain how AJCC definitions are applied on imaging
• Clarify measurement techniques and imaging landmarks
• Highlight common imaging pitfalls and limitations
• Translate explanatory notes into high-yield clinical pearls
• Frame MDT / tumour board discussion points

FORBIDDEN ACTIONS:
• Do NOT reproduce AJCC tables verbatim unless explicitly supplied
• Do NOT introduce staging rules not present in the provided data
• Do NOT cite proprietary or paywalled sources as references
• Do NOT speculate beyond evidence-based radiology knowledge

REFERENCE STYLE (DESCRIPTIVE ONLY):
• Suggest relevant educational resources using DESCRIPTIVE format only
• NEVER include DOIs, PMIDs, URLs, or page numbers
• You can search for all repudated and peer reviewed journals which provide open access to FULL text BUT use  this exact format :
  - "Radiographics: [Article Topic]"
  - "Radiopaedia: [Topic]"
  - "AJR: [Topic]"
  - "European Radiology: [Topic]"
• Users will search for these references themselves using our reference finder tool
• Keep reference suggestions brief - just source and topic

TONE & STYLE:
• Senior consultant radiologist teaching a fellow
• Precise, structured, and clinically focused
• Bullet points only, no narrative paragraphs
• No filler, no repetition

OUTPUT FORMAT:
• Structured Markdown with numbered section headers
• Use #### for section headings WITH numbers: #### 1. Title, #### 2. Title, etc.
• Required sections (in this order):
  1. Critical Stage-Changing Findings (with **T-stage**, **N-stage**, **M-stage** subsections)
  2. Practical Application on Imaging
  3. High-Yield Explanatory Note Pearls
  4. Tumour Board / MDT Discussion Points
  5. Reporting Reminders
• Use bullet points (- ) for all content under each section
• Use **bold** for emphasis on critical findings
• Group stage-changing findings by T, N, M separately"""


def _build_tnm_user_prompt(ajcc_match: Dict, staging_data: Dict) -> str:
    """Build user prompt with staging data for Claude.
    
    Uses the 6-section task template for TNM Intelligence:
    1. Practical Application of TNM on Imaging
    2. Critical Stage-Changing Imaging Findings
    3. High-Yield Pearls from Explanatory Notes
    4. MDT / Tumour Board Discussion Points
    5. Figures & Diagrams
    6. References
    
    Handles complex AJCC data structures:
    - T definitions can be flat or organized by subsite (e.g., Glottis, Supraglottis)
    - N definitions can be dict with clinical/pathological or flat list
    - Uses 'criteria' or 'definition' keys interchangeably
    """
    import re
    
    disease_name = ajcc_match.get('disease_name', 'Unknown')
    section_name = ajcc_match.get('section_name', 'Unknown')
    tnm_version = ajcc_match.get('tnm_version', 'AJCC 8th Edition')
    
    # Format T definitions (handles both flat and subsite-organized structures)
    t_defs = staging_data.get("t_definitions", [])
    t_section = ""
    if t_defs:
        t_section = "T STAGE DEFINITIONS:\n"
        for t in t_defs:
            if isinstance(t, dict):
                # Check if this is subsite-organized (e.g., Larynx with Glottis/Supraglottis)
                if 'subsite' in t and 'categories' in t:
                    subsite = t.get('subsite', 'Unknown')
                    t_section += f"\n  [{subsite}]:\n"
                    for cat in t.get('categories', []):
                        if isinstance(cat, dict):
                            category = cat.get('category', 'T?')
                            criteria = cat.get('criteria', cat.get('definition', ''))
                            t_section += f"    {category}: {criteria}\n"
                elif 'category' in t:
                    definition = t.get('definition', t.get('criteria', ''))
                    t_section += f"  {t.get('category', 'T?')}: {definition}\n"
            else:
                t_section += f"  {t}\n"
    
    # Format N definitions (handles dict with clinical/pathological or flat list)
    n_defs = staging_data.get("n_definitions", {})
    n_section = ""
    if n_defs:
        n_section = "N STAGE DEFINITIONS:\n"
        if isinstance(n_defs, dict):
            clinical = n_defs.get("clinical", [])
            pathological = n_defs.get("pathological", [])
            if clinical:
                n_section += "  Clinical (cN):\n"
                for n in clinical:
                    if isinstance(n, dict):
                        definition = n.get('definition', n.get('criteria', ''))
                        n_section += f"    {n.get('category', 'N?')}: {definition}\n"
            if pathological:
                n_section += "  Pathological (pN):\n"
                for n in pathological:
                    if isinstance(n, dict):
                        definition = n.get('definition', n.get('criteria', ''))
                        n_section += f"    {n.get('category', 'N?')}: {definition}\n"
        elif isinstance(n_defs, list):
            for n in n_defs:
                if isinstance(n, dict):
                    definition = n.get('definition', n.get('criteria', ''))
                    n_section += f"  {n.get('category', 'N?')}: {definition}\n"
    
    # Format M definitions
    m_defs = staging_data.get("m_definitions", [])
    m_section = ""
    if m_defs:
        m_section = "M STAGE DEFINITIONS:\n"
        for m in m_defs:
            if isinstance(m, dict):
                definition = m.get('definition', m.get('criteria', ''))
                m_section += f"  {m.get('category', 'M?')}: {definition}\n"
            else:
                m_section += f"  {m}\n"
    
    # Format stage groups (compact)
    stage_groups = staging_data.get("stage_groups", [])
    sg_section = ""
    if stage_groups:
        sg_section = "STAGE GROUPINGS:\n"
        for sg in stage_groups[:12]:
            if isinstance(sg, dict):
                sg_section += f"  Stage {sg.get('stage', '?')}: T{sg.get('T', '?')} N{sg.get('N', '?')} M{sg.get('M', '?')}\n"
    
    # Extract images from explanatory notes HTML
    explanatory_notes_html = staging_data.get("explanatory_notes_html", "") or ""
    images = []
    if explanatory_notes_html:
        img_matches = re.findall(r'<img[^>]+src="([^"]+)"', explanatory_notes_html)
        images = img_matches[:8]
    
    explicit_images = staging_data.get("images", [])
    if explicit_images:
        images = list(set(images + explicit_images))[:8]
    
    figures_section = ""
    if images:
        figures_section = "AJCC FIGURES AVAILABLE (use placeholders to include them):\n"
        for i, img_url in enumerate(images, 1):
            figures_section += f"  [FIGURE_{i}] - {img_url}\n"
        figures_section += "\nIMPORTANT: Include these figures in Section 5 using [FIGURE_1], [FIGURE_2], etc."
    
    # Clean HTML from explanatory notes - THIS IS HIGHEST PRIORITY
    explanatory_text = explanatory_notes_html
    if explanatory_text:
        explanatory_text = re.sub(r'<[^>]+>', ' ', explanatory_text)
        explanatory_text = re.sub(r'\s+', ' ', explanatory_text).strip()
        # Allow more text since this is the highest priority source
        if len(explanatory_text) > 8000:
            explanatory_text = explanatory_text[:8000] + "... [truncated]"
    
    prompt = f"""Primary cancer site: {disease_name}
Body Section: {section_name}
Edition: {tnm_version}

You are provided with AJCC TNM staging data for this site,
including definitions, explanatory notes, and figures.

Using ONLY the provided AJCC data as the staging authority,
and applying radiology knowledge appropriately,
perform the following tasks:

═══════════════════════════════════════════════════════════════════
AJCC STAGING DATA (Retrieval Priority Order Applied)
═══════════════════════════════════════════════════════════════════

>>> EXPLANATORY NOTES (HIGHEST PRIORITY - analyze carefully) <<<

{explanatory_text if explanatory_text else '[No explanatory notes available]'}

>>> T, N, M DEFINITIONS <<<

{t_section}
{n_section}
{m_section}
{sg_section}

>>> FIGURES & DIAGRAMS <<<

{figures_section if figures_section else '[No figures available]'}

═══════════════════════════════════════════════════════════════════
YOUR TASK: Generate TNM Imaging Intelligence
═══════════════════════════════════════════════════════════════════

1) PRACTICAL APPLICATION OF TNM ON IMAGING
Explain how T, N, and M categories are assessed on imaging.

Focus on:
• Imaging landmarks relevant to this site
• Measurement rules important for staging
• Modality strengths and weaknesses (CT vs MRI)
• Imaging surrogates for clinical findings (e.g. fixation)

---

2) CRITICAL STAGE-CHANGING IMAGING FINDINGS
List findings that, if present, will:
• Upstage T category
• Upstage N category
• Change M category
• Alter surgical approach or management

Only include high-impact, exam- and MDT-relevant findings.

Group clearly by T, N, and M with specific stage transitions (e.g., T2 → T3).

---

3) HIGH-YIELD PEARLS FROM EXPLANATORY NOTES
Extract the most clinically relevant information from
the AJCC explanatory notes and convert them into
concise, memorable radiology pearls.

These pearls should:
• Prevent common staging errors
• Highlight subtle but critical nuances
• Be easy to recall during reporting or MDT

---

4) MDT / TUMOUR BOARD DISCUSSION POINTS
List points a radiologist should explicitly mention
or be prepared to defend in tumour board discussion.

Focus on:
• Resectability
• High-risk features
• Imaging limitations
• Areas of uncertainty affecting staging

---

5) FIGURES & DIAGRAMS
For each AJCC figure provided above, include it using the placeholder format:

[FIGURE_1]
Brief description of what Figure 1 illustrates and how it helps TNM interpretation.

[FIGURE_2]
Brief description of what Figure 2 illustrates and how it helps TNM interpretation.

IMPORTANT: Use exact placeholders [FIGURE_1], [FIGURE_2], etc. - these will be replaced with actual images.

---

6) SUGGESTED READING (DESCRIPTIVE ONLY)
List 2-4 relevant educational resources for further reading.

FORMAT RULES - MUST FOLLOW:
• Use ONLY descriptive format: "Source: Topic"
• NEVER include DOIs, PMIDs, URLs, links, or page numbers
• Examples of CORRECT format:
  - "Radiographics: Imaging of Laryngeal Cancer"
  - "Radiopaedia: Laryngeal carcinoma TNM staging"  
  - "AJR: Head and neck cancer staging pictorial review"
  - "European Radiology: Laryngeal cartilage invasion assessment"
• The user will use the reference finder tool to locate these articles

Preferred sources to suggest:
• Radiographics, AJR, Radiology (RSNA journals)
• NICE guidelines
• Radiopaedia, Radiology Assistant
• European Radiology, British Journal of Radiology
• Indian Journal of Radiology and Imaging
• Society guidelines (ACR, ESUR, NCCN)


═══════════════════════════════════════════════════════════════════
FORMAT RULES
═══════════════════════════════════════════════════════════════════

Output as structured Markdown with these exact headers:

### TNM Imaging Intelligence – {disease_name}

#### 1. Practical Application on Imaging
- ...

#### 2. Critical Stage-Changing Findings
**T-stage**
- T2 → T3: ...
- T3 → T4a: ...
**N-stage**
- ...
**M-stage**
- ...

#### 3. High-Yield Explanatory Note Pearls
- ...

#### 4. Tumour Board / MDT Discussion Points
- ...

#### 5. AJCC Figures & Diagrams

[FIGURE_1]
Description of what this figure shows...

[FIGURE_2]
Description of what this figure shows...

#### 6. Suggested Reading
- Radiographics: [Topic]
- AJR: [Topic]

🔴 REPORTING REMINDER
State any critical imaging limitation relevant to staging this cancer.

💡 TIP: Use the "Find Reference" feature to locate full articles.

═══════════════════════════════════════════════════════════════════

OUTPUT ONLY THE MARKDOWN. No JSON. No code fences around the entire output.
Start directly with "### TNM Imaging Intelligence"."""

    return prompt


# ============================================================================
# CLAUDE API CALL
# ============================================================================

def _call_claude_tnm(system_prompt: str, user_prompt: str) -> str:
    """
    Make Claude API call for TNM intelligence.
    
    Returns Markdown content directly (not JSON).
    Uses lower temperature for more deterministic output.
    """
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise AiTnmError("CLAUDE_API_KEY is not configured.")
    
    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    
    payload = {
        "model": model,
        "max_tokens": 4000,  # Increased for longer Markdown output
        "temperature": 0.3,  # Slightly higher for better writing quality
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_prompt}
        ],
    }
    
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json=payload,
            timeout=90,  # Increased timeout for longer responses
        )
    except requests.exceptions.Timeout:
        raise AiTnmError("Claude API request timed out.")
    except requests.exceptions.RequestException as exc:
        raise AiTnmError(f"Failed to connect to Claude API: {exc}")
    
    if response.status_code >= 300:
        error_detail = response.text[:500] if response.text else "No details"
        raise AiTnmError(f"Claude API error (HTTP {response.status_code}): {error_detail}")
    
    data = response.json()
    content = data.get("content", [])
    if not content:
        raise AiTnmError("Claude response missing content block")
    
    text = content[0].get("text", "").strip()
    if not text:
        raise AiTnmError("Claude response was empty")
    
    # Clean up - remove any code fence wrapper if Claude added it
    if text.startswith("```markdown"):
        text = text[11:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    elif text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    
    # Validate that we got proper Markdown output
    if not text.startswith("###") and not text.startswith("# "):
        # Try to find the start of the expected output
        start_idx = text.find("### TNM Imaging Intelligence")
        if start_idx != -1:
            text = text[start_idx:]
        else:
            print(f"[AI_TNM] Warning: Response doesn't start with expected header")
            print(f"[AI_TNM] First 500 chars: {text[:500]}")
    
    return text


# ============================================================================
# MARKDOWN PARSING - Extract structured data from AI output
# ============================================================================

def _parse_tnm_markdown(markdown_content: str) -> Dict:
    """
    Parse TNM Intelligence Markdown to extract structured fields for database storage.
    
    Args:
        markdown_content: Markdown text from Claude AI
        
    Returns:
        Dict with structured fields:
        - tnm_memory_aid: {T, N, M} stage summaries
        - radiologist_key_points: List of key findings
        - upstaging_triggers: T-stage/N-stage/M-stage triggers
        - mdt_critical_findings: MDT discussion points
        - copy_blocks: Report templates
        - imaging_checklist: Imaging review items
        - warnings: Reporting reminders
    """
    import re
    
    result = {
        'tnm_memory_aid': {'T': None, 'N': None, 'M': None},
        'radiologist_key_points': [],
        'upstaging_triggers': [],
        'mdt_critical_findings': [],
        'copy_blocks': {},
        'imaging_checklist': [],
        'reference_images': [],
        'warnings': []
    }
    
    if not markdown_content:
        return result
    
    # Extract sections using regex
    sections = {}
    current_section = None
    current_content = []
    
    for line in markdown_content.split('\n'):
        # Check for section headers - support both:
        #   #### 1. Title (numbered)
        #   #### Title (non-numbered)
        section_match = re.match(r'^####\s*(?:\d+\.)?\s*(.+)', line)
        if section_match:
            # Save previous section
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = section_match.group(1).strip().lower()
            current_content = []
        else:
            current_content.append(line)
    
    # Save last section
    if current_section:
        sections[current_section] = '\n'.join(current_content).strip()
    
    # Parse Critical Stage-Changing Findings for tnm_memory_aid and upstaging_triggers
    stage_findings = sections.get('critical stage-changing findings', '')
    if stage_findings:
        # Extract T-stage info
        t_match = re.search(r'\*\*T-stage\*\*(.+?)(?=\*\*[NM]-stage\*\*|$)', stage_findings, re.DOTALL)
        if t_match:
            t_lines = [l.strip('- ').strip() for l in t_match.group(1).strip().split('\n') if l.strip().startswith('-')]
            result['tnm_memory_aid']['T'] = '; '.join(t_lines[:3]) if t_lines else None
            result['upstaging_triggers'].extend([f"T: {l}" for l in t_lines])
        
        # Extract N-stage info
        n_match = re.search(r'\*\*N-stage\*\*(.+?)(?=\*\*M-stage\*\*|$)', stage_findings, re.DOTALL)
        if n_match:
            n_lines = [l.strip('- ').strip() for l in n_match.group(1).strip().split('\n') if l.strip().startswith('-')]
            result['tnm_memory_aid']['N'] = '; '.join(n_lines[:3]) if n_lines else None
            result['upstaging_triggers'].extend([f"N: {l}" for l in n_lines])
        
        # Extract M-stage info
        m_match = re.search(r'\*\*M-stage\*\*(.+?)$', stage_findings, re.DOTALL)
        if m_match:
            m_lines = [l.strip('- ').strip() for l in m_match.group(1).strip().split('\n') if l.strip().startswith('-')]
            result['tnm_memory_aid']['M'] = '; '.join(m_lines[:3]) if m_lines else None
            result['upstaging_triggers'].extend([f"M: {l}" for l in m_lines])
    
    # Parse Practical Application on Imaging -> radiologist_key_points
    practical = sections.get('practical application on imaging', '')
    if practical:
        result['radiologist_key_points'] = [
            l.strip('- ').strip() 
            for l in practical.split('\n') 
            if l.strip().startswith('-') and len(l.strip()) > 5
        ][:10]  # Limit to 10 points
    
    # Parse High-Yield Explanatory Note Pearls -> imaging_checklist
    pearls = sections.get('high-yield explanatory note pearls', '')
    if pearls:
        result['imaging_checklist'] = [
            l.strip('- ').strip() 
            for l in pearls.split('\n') 
            if l.strip().startswith('-') and len(l.strip()) > 5
        ][:10]
    
    # Parse MDT Discussion Points -> mdt_critical_findings
    mdt = sections.get('tumour board / mdt discussion points', '')
    if mdt:
        result['mdt_critical_findings'] = [
            l.strip('- ').strip() 
            for l in mdt.split('\n') 
            if l.strip().startswith('-') and len(l.strip()) > 5
        ][:10]
    
    # Parse Reporting Reminder -> warnings
    reminder_match = re.search(r'🔴\s*REPORTING REMINDER\s*\n(.+?)(?=\n\n|💡|$)', markdown_content, re.DOTALL)
    if reminder_match:
        result['warnings'] = [reminder_match.group(1).strip()]
    
    return result


# ============================================================================
# FIGURE INJECTION
# ============================================================================

def _inject_figures_into_markdown(markdown_content: str, images: List[str]) -> str:
    """
    Replace figure placeholders [FIGURE_N] with actual image HTML.
    
    Args:
        markdown_content: Markdown text with [FIGURE_1], [FIGURE_2] placeholders
        images: List of image URLs
        
    Returns:
        Markdown with placeholders replaced by <img> tags
    """
    if not images:
        # No images available - remove placeholders or replace with note
        import re
        markdown_content = re.sub(
            r'\[FIGURE_\d+\]',
            '*[Figure not available]*',
            markdown_content
        )
        return markdown_content
    
    # Replace each placeholder with actual image
    for i, img_url in enumerate(images, 1):
        placeholder = f"[FIGURE_{i}]"
        
        # Create responsive image HTML with styling
        img_html = f'''
<div style="margin: 1rem 0; text-align: center;">
    <img src="{img_url}" alt="AJCC Figure {i}" style="max-width: 100%; height: auto; border: 1px solid #c5cad1; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
    <p style="font-size: 0.85em; color: #5a6270; margin-top: 0.5rem;"><strong>Figure {i}</strong></p>
</div>
'''
        markdown_content = markdown_content.replace(placeholder, img_html)
    
    # Remove any remaining unmatched placeholders (if Claude used more than available)
    import re
    markdown_content = re.sub(
        r'\[FIGURE_\d+\]',
        '*[Additional figure not available]*',
        markdown_content
    )
    
    return markdown_content


# ============================================================================
# MAIN PUBLIC API
# ============================================================================

def generate_tnm_intelligence(
    *,
    diagnosis: str,
    module: str = None,
    body_part: str = None,
    from_case_id: int = None,
    provider: str = "claude"
) -> Dict:
    """
    Generate TNM staging intelligence for oncologic diagnoses.
    
    This is the main entry point for TNM AI analysis.
    
    Args:
        diagnosis: Cancer diagnosis text (required)
        module: FRCR module (optional, improves matching)
        body_part: Body part hint (optional, improves matching)
        from_case_id: Source case ID for back navigation
        provider: AI provider (currently only "claude")
        
    Returns:
        Dict with keys:
            - ajcc_match: AJCC disease site mapping
            - tnm_link: Internal URL to TNM page
            - tnm_memory_aid: Easy-to-remember T/N/M summaries
            - radiologist_key_points: List of must-report items
            - upstaging_triggers: Findings that increase stage
            - mdt_critical_findings: MDT decision points
            - copy_blocks: Copy-friendly report templates
            - reference_images: Staging-relevant images
            - imaging_checklist: Systematic imaging review list
            - warnings: Any caveats or uncertainties
            - generated_at: Timestamp
            - provider: AI provider used
            
    Raises:
        AiTnmError: If generation fails
    """
    if provider != "claude":
        raise AiTnmError(f"Unsupported provider: {provider}")
    
    # Check if oncologic diagnosis
    if not is_oncologic_diagnosis(diagnosis):
        raise AiTnmError(
            "This diagnosis does not appear to require TNM staging. "
            "TNM intelligence is only available for oncologic diagnoses."
        )
    
    # Map to AJCC site
    ajcc_match = _map_to_ajcc_site(diagnosis, module, body_part)
    if not ajcc_match:
        raise AiTnmError(
            f"Could not map '{diagnosis}' to an AJCC disease site. "
            "Please check the diagnosis or add manual AJCC mapping."
        )
    
    # Get staging data from database
    staging_data = _get_staging_data(ajcc_match["disease_site_id"])
    if not staging_data:
        raise AiTnmError(
            f"No TNM staging data found for {ajcc_match['disease_name']}. "
            "Please extract staging data from AJCC first."
        )
    
    # Build prompts
    user_prompt = _build_tnm_user_prompt(ajcc_match, staging_data)
    
    # Call Claude - returns Markdown directly
    markdown_content = _call_claude_tnm(TNM_SYSTEM_PROMPT, user_prompt)
    
    # Parse Markdown to extract structured fields for database storage
    parsed_data = _parse_tnm_markdown(markdown_content)
    
    # Get images from staging data and inject them into markdown
    images = staging_data.get("images", [])
    markdown_content = _inject_figures_into_markdown(markdown_content, images)
    
    # Get Essential TNM Key Concepts (IARC-sourced) for applicable cancers
    essential_tnm_data = get_essential_tnm_for_cancer(diagnosis)
    if essential_tnm_data:
        # Append Essential TNM key concepts to the AI-generated content
        essential_markdown = format_essential_tnm_markdown(essential_tnm_data)
        markdown_content = markdown_content + essential_markdown
    
    # Build internal link (single link for both views)
    section_slug = ajcc_match.get("section_slug", "")
    disease_slug = ajcc_match.get("disease_slug", "")
    tnm_version = ajcc_match.get("tnm_version", "AJCC 8th Edition")
    
    # Extract year from tnm_version if present (e.g., "AJCC 8th Edition (2026)")
    import re
    year_match = re.search(r'\((\d{4})\)', tnm_version)
    year = year_match.group(1) if year_match else "2026"
    
    # Build TNM link with year parameter - use /view suffix for unified TNM view
    tnm_link = f"/tnm/{section_slug}/{disease_slug}/view?year={year}"
    if from_case_id is not None:
        tnm_link += f"&from_case={from_case_id}"
    
    # Return Markdown content with metadata AND structured fields for auto-save
    result = {
        "ajcc_match": ajcc_match,
        "tnm_link": tnm_link,
        "tnm_intelligence_markdown": markdown_content,
        "images": images,  # Include images for frontend if needed
        "generated_at": datetime.utcnow().isoformat(),
        "provider": provider,
        # Structured fields parsed from Markdown (for intelligent_tnm_data table)
        "tnm_memory_aid": parsed_data.get("tnm_memory_aid"),
        "radiologist_key_points": parsed_data.get("radiologist_key_points", []),
        "upstaging_triggers": parsed_data.get("upstaging_triggers", []),
        "mdt_critical_findings": parsed_data.get("mdt_critical_findings", []),
        "copy_blocks": parsed_data.get("copy_blocks", {}),
        "imaging_checklist": parsed_data.get("imaging_checklist", []),
        "reference_images": parsed_data.get("reference_images", []),
        "warnings": parsed_data.get("warnings", []),
        "source_case_id": from_case_id,
        "disease_name": ajcc_match.get("disease_name", "Unknown"),
        "tnm_version": tnm_version,
        # Essential TNM key concepts (IARC-sourced, for applicable cancers)
        "essential_tnm": essential_tnm_data,
    }
    
    return result


# ============================================================================
# INTEGRATION HELPERS
# ============================================================================

def should_show_tnm_button(diagnosis: str) -> bool:
    """
    Check if TNM intelligence button should be shown for this diagnosis.
    
    Simple wrapper around is_oncologic_diagnosis for view integration.
    """
    return is_oncologic_diagnosis(diagnosis)
