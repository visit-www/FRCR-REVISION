"""
AJCC Staging Service

This module provides functions to map cancer diagnoses to AJCC staging sections
and generate URLs to AJCC disease staging pages.

For use in:
- AI prompt enhancement (optional AJCC URL reference in discussion)
- Future admin route for dedicated TNM retrieval
- Linking to TNM pages from case discussions

Note: This service will be extended later for a separate admin route focused
on TNM classification extraction.
"""

import json
import os
from typing import Optional, Dict, List
from urllib.parse import quote
from flask import url_for


# AJCC Configuration
AJCC_BASE_URL = "https://ajccstaging.org"
AJCC_ONTOLOGY_FILE = "ajcc_frcr_full_ontology.json"
AJCC_JSON_FILE = "ajcc.json"
AJCC_BODY_PART_FILE = "ajcc-body-part.txt"

# AJCC Login Credentials (for future admin route)
# These must be set as environment variables - no hardcoded defaults for security
AJCC_USERNAME = os.getenv("AJCC_USERNAME")
AJCC_PASSWORD = os.getenv("AJCC_PASSWORD")


def _load_json_file(filepath: str) -> Dict:
    """Load JSON file from workspace root."""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(script_dir, filepath)
        with open(full_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[AJCC] Warning: {filepath} not found")
        return {}
    except json.JSONDecodeError as e:
        print(f"[AJCC] Error parsing {filepath}: {e}")
        return {}


def _load_text_file(filepath: str) -> List[str]:
    """Load text file from workspace root."""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(script_dir, filepath)
        with open(full_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        print(f"[AJCC] Warning: {filepath} not found")
        return []


def load_ajcc_ontology() -> Dict:
    """
    Load AJCC body part and disease mapping from ajcc_frcr_full_ontology.json.
    
    Returns:
        Dict with structure: {
            "sections": [
                {
                    "ajcc_section": "Thorax",
                    "disease_sites": ["Lung", "Pleural Mesothelioma", "Thymus"]
                },
                ...
            ]
        }
    """
    return _load_json_file(AJCC_ONTOLOGY_FILE)


def load_ajcc_url_mappings() -> List[Dict]:
    """
    Load AJCC URL slug mappings from ajcc.json.
    
    Returns:
        List of dicts with structure: [
            {
                "slug": "thorax",
                "display_name": "Thorax",
                "url": "https://ajccstaging.org/en/thorax",
                "type": "body_system"
            },
            ...
        ]
    """
    return _load_json_file(AJCC_JSON_FILE)


def _normalize_text(text: str) -> str:
    """Normalize text for matching (lowercase, remove special chars)."""
    return text.lower().strip()


def _match_diagnosis_to_section(diagnosis: str, body_part: str = None) -> Optional[Dict]:
    """
    Match diagnosis to AJCC section and disease site.
    
    Args:
        diagnosis: Cancer diagnosis string
        body_part: Optional body part hint from case data
        
    Returns:
        Dict with keys: ajcc_section, disease_site, or None if no match
    """
    if "cancer" not in diagnosis.lower():
        return None
    
    ontology = load_ajcc_ontology()
    if not ontology or "sections" not in ontology:
        return None
    
    diagnosis_lower = _normalize_text(diagnosis)
    body_part_lower = _normalize_text(body_part) if body_part else ""
    
    # Try to match diagnosis keywords to disease sites
    best_match = None
    best_score = 0
    
    for section in ontology.get("sections", []):
        ajcc_section = section.get("ajcc_section", "")
        disease_sites = section.get("disease_sites", [])
        
        for disease_site in disease_sites:
            disease_lower = _normalize_text(disease_site)
            
            # Score based on keyword matches
            score = 0
            
            # Exact match gets highest score
            if disease_lower in diagnosis_lower or diagnosis_lower in disease_lower:
                score += 10
            
            # Partial word matches
            disease_words = disease_lower.split()
            for word in disease_words:
                if len(word) > 3 and word in diagnosis_lower:
                    score += 2
            
            # Body part hint bonus
            if body_part_lower and body_part_lower in ajcc_section.lower():
                score += 3
            
            # Common cancer type matches
            cancer_types = {
                "lung": ["lung", "pulmonary", "bronchial"],
                "breast": ["breast", "mammary"],
                "liver": ["liver", "hepatic", "hepatocellular"],
                "colon": ["colon", "colonic", "colorectal"],
                "rectum": ["rectum", "rectal"],
                "stomach": ["stomach", "gastric"],
                "esophagus": ["esophagus", "esophageal", "oesophagus"],
                "pancreas": ["pancreas", "pancreatic"],
                "kidney": ["kidney", "renal"],
                "bladder": ["bladder", "vesical"],
                "prostate": ["prostate", "prostatic"],
                "thyroid": ["thyroid"],
                "brain": ["brain", "cerebral", "intracranial"],
                "head": ["head", "neck", "oral", "oropharynx", "larynx"],
            }
            
            for key, keywords in cancer_types.items():
                if key in disease_lower:
                    if any(kw in diagnosis_lower for kw in keywords):
                        score += 5
            
            if score > best_score:
                best_score = score
                best_match = {
                    "ajcc_section": ajcc_section,
                    "disease_site": disease_site,
                    "score": score
                }
    
    if best_match and best_score >= 3:  # Minimum threshold
        return {
            "ajcc_section": best_match["ajcc_section"],
            "disease_site": best_match["disease_site"]
        }
    
    return None


def _section_name_to_slug(section_name: str) -> Optional[str]:
    """
    Convert AJCC section name to URL slug.
    
    Args:
        section_name: e.g., "Head and Neck"
        
    Returns:
        URL slug: e.g., "head-and-neck"
    """
    url_mappings = load_ajcc_url_mappings()
    if not isinstance(url_mappings, list):
        return None
    
    section_lower = _normalize_text(section_name)
    
    for mapping in url_mappings:
        if isinstance(mapping, dict):
            display_name = _normalize_text(mapping.get("display_name", ""))
            if display_name == section_lower:
                slug = mapping.get("slug", "")
                if slug and mapping.get("type") == "body_system":
                    return slug
    
    # Fallback: convert section name to slug manually
    slug = section_name.lower().replace(" ", "-")
    return slug


def _disease_site_to_slug(disease_site: str) -> str:
    """
    Convert disease site name to URL slug.
    
    Args:
        disease_site: e.g., "Lung"
        
    Returns:
        URL slug: e.g., "lung"
    """
    # Simple conversion: lowercase, replace spaces with hyphens
    slug = disease_site.lower().replace(" ", "-")
    # Remove special characters
    slug = "".join(c if c.isalnum() or c == "-" else "" for c in slug)
    return slug


def map_diagnosis_to_ajcc(diagnosis: str, body_part: str = None) -> Optional[Dict]:
    """
    Map cancer diagnosis to AJCC section and disease site.
    
    Only returns result if diagnosis contains 'cancer' keyword.
    
    Args:
        diagnosis: Cancer diagnosis string (e.g., "Lung cancer", "Breast carcinoma")
        body_part: Optional body part hint from case data
        
    Returns:
        Dict with keys:
            - ajcc_section: str (e.g., "Thorax")
            - disease_site: str (e.g., "Lung")
            - url: str (AJCC disease staging page URL)
            - slug: str (section slug for URL)
        Or None if diagnosis doesn't contain "cancer" or no match found
    """
    if "cancer" not in diagnosis.lower():
        return None
    
    match = _match_diagnosis_to_section(diagnosis, body_part)
    if not match:
        return None
    
    ajcc_section = match["ajcc_section"]
    disease_site = match["disease_site"]
    
    section_slug = _section_name_to_slug(ajcc_section)
    disease_slug = _disease_site_to_slug(disease_site)
    
    if not section_slug:
        return None
    
    # Generate URL
    # Format: https://ajccstaging.org/en/{section-slug}/{disease-slug}
    url = f"{AJCC_BASE_URL}/en/{section_slug}/{disease_slug}"
    
    return {
        "ajcc_section": ajcc_section,
        "disease_site": disease_site,
        "url": url,
        "slug": section_slug
    }


def generate_ajcc_disease_url(ajcc_section: str, disease_site: str) -> str:
    """
    Generate direct URL to AJCC disease staging page.
    
    Args:
        ajcc_section: AJCC section name (e.g., "Thorax")
        disease_site: Disease site name (e.g., "Lung")
        
    Returns:
        URL string: https://ajccstaging.org/en/{section-slug}/{disease-slug}
    """
    section_slug = _section_name_to_slug(ajcc_section)
    disease_slug = _disease_site_to_slug(disease_site)
    
    if not section_slug:
        # Fallback to manual conversion
        section_slug = ajcc_section.lower().replace(" ", "-")
    
    return f"{AJCC_BASE_URL}/en/{section_slug}/{disease_slug}"


# ============================================================================
# FUTURE: Session Management and TNM Extraction (for admin route)
# ============================================================================

def get_ajcc_session():
    """
    Get logged-in AJCC session (with caching).
    
    This will be implemented for the future admin route.
    For now, returns None as we're not doing active session management.
    
    Returns:
        requests.Session or None
    """
    # TODO: Implement session management with login
    # - Login to AJCC using credentials
    # - Cache session cookies
    # - Return session object
    return None


def extract_tnm_from_page(url: str) -> Optional[Dict]:
    """
    Extract TNM staging information from AJCC page.
    
    This will be implemented for the future admin route.
    
    Args:
        url: AJCC disease staging page URL
        
    Returns:
        Dict with keys:
            - t_stages: List of T stage definitions
            - n_stages: List of N stage definitions
            - m_stages: List of M stage definitions
            - stage_groupings: List of stage groupings
        Or None if extraction fails
    """
    # TODO: Implement page parsing with BeautifulSoup
    # - Navigate to disease page
    # - Extract T, N, M definitions
    # - Extract stage groupings
    # - Return structured data
    return None


# ============================================================================
# TNM PAGE LINKING (for case discussions)
# ============================================================================

def get_tnm_url_for_diagnosis(diagnosis: str, app_context=None) -> Optional[str]:
    """
    Get TNM page URL for a cancer diagnosis if TNM data exists.
    
    Args:
        diagnosis: Cancer diagnosis text (e.g., "Lung cancer", "Breast carcinoma")
        app_context: Flask app context (optional, for database queries)
        
    Returns:
        URL to TNM page (e.g., "/tnm/thorax/lung") or None if not found
    """
    if not diagnosis or 'cancer' not in diagnosis.lower():
        return None
    
    # Try to import models only if app context is available
    try:
        from models import AJCCDiseaseSite, AJCCStagingData, AJCCDiagnosisYear, db
        
        if app_context is None:
            # Try to get current app context
            from flask import has_app_context, current_app
            if not has_app_context():
                return None
            app_context = current_app.app_context()
        
        with app_context:
            # Search for matching disease site
            diagnosis_lower = diagnosis.lower()
            
            # Try to find disease site by name matching
            disease_sites = AJCCDiseaseSite.query.all()
            for disease_site in disease_sites:
                disease_name_lower = disease_site.disease_name.lower()
                
                # Check if diagnosis contains disease name or vice versa
                if disease_name_lower in diagnosis_lower or diagnosis_lower in disease_name_lower:
                    # Check if TNM data exists for this disease
                    staging_data = AJCCStagingData.query.filter_by(
                        disease_site_id=disease_site.id
                    ).first()
                    
                    if staging_data:
                        # Get section slug
                        section = disease_site.body_section
                        if section:
                            return f"/tnm/{section.slug}/{disease_site.slug}"
            
            return None
    except ImportError:
        # Models not available, return None
        return None
    except Exception as e:
        print(f"[AJCC] Error getting TNM URL: {e}")
        return None


def check_tnm_data_exists(diagnosis: str, app_context=None) -> bool:
    """
    Check if TNM data exists for a diagnosis.
    
    Args:
        diagnosis: Cancer diagnosis text
        app_context: Flask app context (optional)
        
    Returns:
        True if TNM data exists, False otherwise
    """
    url = get_tnm_url_for_diagnosis(diagnosis, app_context)
    return url is not None