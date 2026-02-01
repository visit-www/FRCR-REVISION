"""
TCIA (The Cancer Imaging Archive) Integration Service for FRCR-Revision

Purpose: Enable residents to practice real diagnostic interpretation using authentic DICOM datasets.
Provides metadata search and links to TCIA's native DICOM viewer.

Exam Relevance: Supports FRCR 2B candidates by providing:
- Real DICOM imaging datasets for practice
- Authentic pathology cases (not static images)
- Ability to scroll through CT/MRI stacks
- Practice identifying lesions in real datasets

Note: This service provides metadata and viewer links only.
Full DICOM downloads are deferred to reduce storage costs.
TCIA's native web viewer is used for image viewing.
"""

import os
import logging
import requests
from typing import List, Dict, Optional
from urllib.parse import urlencode
import json
import hashlib
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# TCIA/NBIA API base URL
TCIA_API_BASE = "https://services.cancerimagingarchive.net/nbia-api/services/v1"

# Cache configuration
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache', 'tcia')
CACHE_DURATION_HOURS = 168  # Cache for 1 week (metadata doesn't change often)
CACHE_VERSION = 2  # Bump when viewer URL format changes to invalidate old cache


def get_study_page_link(patient_id: str, collection: str) -> str:
    """NBIA search page - pre-fills Collection + PatientId (for browsing, not viewing)."""
    params = {'Collection': collection, 'PatientId': patient_id}
    return f"https://nbia.cancerimagingarchive.net/nbia-search/?{urlencode(params)}"


def get_study_viewer_links(study_instance_uid: str) -> Dict[str, str]:
    """Viewer URLs for entire study (all series). Use these for 'View Study' button."""
    # IDC: study UID in path, no series = entire study
    idc_url = f"https://viewer.imaging.datacommons.cancer.gov/viewer/{study_instance_uid}"
    # TCIA/NBIA viewer: studyInstanceUID only = entire study
    nbia_params = urlencode({'studyInstanceUID': study_instance_uid})
    nbia_url = f"https://www.cancerimagingarchive.net/viewer/?{nbia_params}"
    return {'idc': idc_url, 'nbia': nbia_url}


def get_viewer_links(study_instance_uid: str, series_uid: str) -> Dict[str, str]:
    """Generate viewer URLs with fallback options.
    IDC requires StudyInstanceUID in path; NBIA needs both in query params."""
    # IDC: study UID in path, series as ?seriesInstanceUID=...
    idc_base = f"https://viewer.imaging.datacommons.cancer.gov/viewer/{study_instance_uid}"
    idc_primary = f"{idc_base}?seriesInstanceUID={series_uid}" if series_uid else idc_base
    # OHIF v3: query params
    ohif_params = urlencode({
        'StudyInstanceUIDs': study_instance_uid,
        'SeriesInstanceUIDs': series_uid or ''
    })
    ohif_url = f"https://viewer.imaging.datacommons.cancer.gov/v3/viewer/?{ohif_params}" if series_uid else idc_base
    # NBIA: studyInstanceUID and seriesInstanceUID (camelCase)
    nbia_params = urlencode({
        'studyInstanceUID': study_instance_uid,
        'seriesInstanceUID': series_uid
    })
    nbia_url = f"https://www.cancerimagingarchive.net/viewer/?{nbia_params}"
    return {
        'primary': idc_primary,
        'fallback_nbia': nbia_url,
        'ohif': ohif_url,
    }


def ensure_cache_dir():
    """Create cache directory if it doesn't exist."""
    os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_key(endpoint: str, params: Dict) -> str:
    """Generate cache key from endpoint and parameters."""
    cache_data = f"{CACHE_VERSION}_{endpoint}_{json.dumps(params, sort_keys=True)}"
    return hashlib.md5(cache_data.encode()).hexdigest()


def clear_tcia_cache() -> int:
    """Remove all TCIA cache files. Returns count of files removed."""
    if not os.path.isdir(CACHE_DIR):
        return 0
    count = 0
    for f in os.listdir(CACHE_DIR):
        if f.endswith('.json'):
            try:
                os.remove(os.path.join(CACHE_DIR, f))
                count += 1
            except OSError:
                pass
    if count:
        logger.info("[TCIA] Cleared %d cache files", count)
    return count


def get_cached_result(cache_key: str) -> Optional[Dict]:
    """Retrieve cached result if still valid."""
    ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    if not os.path.exists(cache_file):
        return None
    
    try:
        with open(cache_file, 'r') as f:
            cached_data = json.load(f)
        
        # Check if cache is still valid
        cache_time = datetime.fromisoformat(cached_data.get('timestamp', ''))
        if datetime.now() - cache_time < timedelta(hours=CACHE_DURATION_HOURS):
            return cached_data.get('result')
    except Exception as e:
        logger.debug("[TCIA] Cache read error: %s", e)
    
    return None


def cache_result(cache_key: str, result: Dict):
    """Cache API results."""
    ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    try:
        with open(cache_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'result': result
            }, f)
    except Exception as e:
        logger.debug("[TCIA] Cache write error: %s", e)


def search_collections(
    cancer_type: Optional[str] = None,
    modality: Optional[str] = None,
    body_part: Optional[str] = None,
    max_results: int = 50
) -> List[Dict]:
    """
    Search TCIA collections by filters.
    
    Exam Relevance: Helps candidates find relevant imaging datasets for practice.
    
    Args:
        cancer_type: Filter by cancer type (e.g., "Non-small cell lung cancer")
        modality: Filter by imaging modality (e.g., "CT", "MRI", "PET")
        body_part: Filter by body part (e.g., "CHEST", "HEAD", "ABDOMEN")
        max_results: Maximum number of results
    
    Returns:
        List of collection dictionaries with metadata
    """
    params = {}
    if cancer_type:
        params['Collection'] = cancer_type
    if modality:
        params['Modality'] = modality
    if body_part:
        params['BodyPartExamined'] = body_part
    
    cache_key = get_cache_key('getCollectionValues', params)
    cached = get_cached_result(cache_key)
    if cached:
        return cached[:max_results]
    
    try:
        # Get all collections first
        url = f"{TCIA_API_BASE}/getCollectionValues"
        response = requests.get(url, timeout=15)
        
        if response.status_code != 200:
            return []
        
        # Parse simple format: [{"Collection":"name"}, ...]
        collections = response.json()
        logger.debug("[TCIA] Found %d collections", len(collections))
        
        if not isinstance(collections, list):
            logger.warning("[TCIA] Unexpected API format: %s", type(collections))
            return []
        
        # Filter collections
        filtered = []
        search_term = (cancer_type or '').lower()
        
        for item in collections:
            # Handle simple format: {"Collection":"name"}
            collection_name = item.get('Collection', '')
            if not collection_name:
                continue
            
            # Filter by search term if provided
            if search_term:
                # Simple keyword matching
                if search_term not in collection_name.lower():
                    continue
            
            # Return basic info (description/counts not in simple response)
            filtered.append({
                'collection_id': collection_name,
                'name': collection_name,
                'description': '',  # Not available in simple format
                'subject_count': 0,  # Not available in simple format
                'image_count': 0     # Not available in simple format
            })
            
            if len(filtered) >= max_results:
                break
        
        # Cache results
        cache_result(cache_key, filtered)
        
        return filtered[:max_results]
        
    except Exception as e:
        logger.error("[TCIA] Search error: %s", e, exc_info=True)
        return []


def get_collection_studies(collection_id: str, max_results: int = 20) -> List[Dict]:
    """
    Get patient studies for a specific collection.
    
    Exam Relevance: Allows candidates to browse available cases in a collection.
    
    Args:
        collection_id: TCIA collection ID
        max_results: Maximum number of studies to return
    
    Returns:
        List of study dictionaries with metadata
    """
    cache_key = get_cache_key('getPatientStudy', {'collection': collection_id})
    cached = get_cached_result(cache_key)
    if cached:
        return cached[:max_results]
    
    try:
        url = f"{TCIA_API_BASE}/getPatientStudy"
        params = {'Collection': collection_id}
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code != 200:
            return []
        
        studies = response.json()
        
        # Format studies
        formatted_studies = []
        for study in studies[:max_results]:
            formatted_studies.append({
                'patient_id': study.get('PatientId', ''),
                'study_instance_uid': study.get('StudyInstanceUID', ''),
                'study_date': study.get('StudyDate', ''),
                'study_description': study.get('StudyDescription', ''),
                'modality': study.get('Modality', ''),
                'series_count': study.get('SeriesCount', 0),
                'collection': collection_id
            })
        
        # Cache results
        cache_result(cache_key, formatted_studies)
        
        return formatted_studies
        
    except Exception as e:
        logger.error("[TCIA] Get studies error: %s", e)
        return []


def get_study_series(study_instance_uid: str) -> List[Dict]:
    """
    Get series for a specific study.
    
    Exam Relevance: Allows candidates to see available image series for a study.
    
    Args:
        study_instance_uid: Study Instance UID
    
    Returns:
        List of series dictionaries with metadata
    """
    cache_key = get_cache_key('getSeries', {'study': study_instance_uid})
    cached = get_cached_result(cache_key)
    if cached:
        return cached
    
    try:
        url = f"{TCIA_API_BASE}/getSeries"
        params = {'StudyInstanceUID': study_instance_uid}
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code != 200:
            return []
        
        series_list = response.json()
        
        # Format series with correct viewer URLs and fallbacks
        formatted_series = []
        for series in series_list:
            series_uid = series.get('SeriesInstanceUID', '')
            viewer_links = get_viewer_links(study_instance_uid, series_uid)
            
            formatted_series.append({
                'series_instance_uid': series_uid,
                'series_description': series.get('SeriesDescription', ''),
                'modality': series.get('Modality', ''),
                'body_part': series.get('BodyPartExamined', ''),
                'image_count': series.get('NumberOfSeriesRelatedInstances', 0),
                'viewer_link': viewer_links['primary'],
                'viewer_links': viewer_links,
                'study_instance_uid': study_instance_uid
            })
        
        # Cache results
        cache_result(cache_key, formatted_series)
        
        return formatted_series
        
    except Exception as e:
        logger.error("[TCIA] Get series error: %s", e)
        return []


def _is_cancer_related(diagnosis: str) -> bool:
    """
    Check if diagnosis is cancer-related.
    TCIA is cancer-focused, so non-cancer searches will be irrelevant.
    """
    diagnosis_lower = diagnosis.lower()
    
    # Cancer-related keywords
    cancer_keywords = [
        'cancer', 'carcinoma', 'tumor', 'tumour', 'neoplasm', 'malignancy', 'malignant',
        'lymphoma', 'sarcoma', 'adenocarcinoma', 'squamous', 'metastasis', 'metastatic',
        'oncology', 'oncological', 'lesion', 'mass', 'nodule'
    ]
    
    return any(keyword in diagnosis_lower for keyword in cancer_keywords)


def _score_collection_relevance(collection_name: str, diagnosis: str) -> int:
    """
    Score collection relevance to diagnosis (higher = more relevant).
    Returns 0 if not relevant.
    """
    collection_lower = collection_name.lower()
    diagnosis_lower = diagnosis.lower()
    
    # Extract meaningful keywords (length > 3)
    diagnosis_keywords = [word for word in diagnosis_lower.split() if len(word) > 3]
    
    if not diagnosis_keywords:
        return 0
    
    score = 0
    
    # Exact match gets highest score
    if diagnosis_lower in collection_lower:
        score += 100
    
    # Keyword matches
    for keyword in diagnosis_keywords:
        if keyword in collection_lower:
            score += 10
    
    # Cancer-related terms boost score
    cancer_terms = ['cancer', 'carcinoma', 'tumor', 'tumour', 'neoplasm']
    for term in cancer_terms:
        if term in collection_lower and term in diagnosis_lower:
            score += 20
    
    return score


def search_by_diagnosis(diagnosis: str, modality: Optional[str] = None) -> Dict:
    """
    Search TCIA collections by diagnosis/keywords.
    IMPROVED: Better relevance scoring, cancer-focused filtering, and warnings.
    
    Exam Relevance: Helps candidates find relevant cases for specific diagnoses.
    
    Args:
        diagnosis: Diagnosis or keywords to search
        modality: Optional modality filter (CT, MRI, PET)
    
    Returns:
        Dict with:
            - results: List of relevant collections and studies
            - is_cancer_related: Whether diagnosis appears cancer-related
            - warning: Optional warning message
    """
    # Check if diagnosis is cancer-related
    is_cancer = _is_cancer_related(diagnosis)
    
    # Get all collections first
    all_collections = search_collections(max_results=200)
    
    # Score and rank collections by relevance
    scored_collections = []
    for collection in all_collections:
        score = _score_collection_relevance(collection['name'], diagnosis)
        if score > 0:  # Only include collections with some relevance
            scored_collections.append((score, collection))
    
    # Sort by relevance score (highest first)
    scored_collections.sort(key=lambda x: x[0], reverse=True)
    
    # Get top relevant collections (limit to top 3 for better relevance)
    relevant_collections = [col for _, col in scored_collections[:3]]
    
    # Warning message if not cancer-related or no matches
    warning = None
    if not is_cancer:
        warning = "TCIA focuses on cancer imaging. Your search may return limited or irrelevant results for non-cancer diagnoses."
    elif not relevant_collections:
        warning = f"No relevant cancer imaging collections found for '{diagnosis}'. TCIA may not have datasets for this specific diagnosis."
    
    # If no relevant matches, return empty with warning (don't return random collections)
    if not relevant_collections:
        return {
            'results': [],
            'is_cancer_related': is_cancer,
            'warning': warning
        }
    
    # Get studies for relevant collections
    results = []
    for collection in relevant_collections:
        collection_id = collection['collection_id']
        try:
            studies = get_collection_studies(collection_id, max_results=3)
            
            for study in studies:
                series_list = get_study_series(study['study_instance_uid'])
                patient_id = study.get('patient_id', '')
                study_page_link = get_study_page_link(patient_id, collection_id)
                
                # Add study_page_link to each series for frontend
                for s in series_list[:5]:  # Top 5 series per study
                    s['study_page_link'] = study_page_link
                
                collection_page_link = f"https://www.cancerimagingarchive.net/collection/{collection_id}/"
                study_viewer_links = get_study_viewer_links(study['study_instance_uid'])
                
                results.append({
                    'collection': collection,
                    'collection_page_link': collection_page_link,
                    'study': study,
                    'study_page_link': study_page_link,
                    'study_viewer_links': study_viewer_links,
                    'series': series_list[:5]
                })
        except Exception as e:
            logger.warning("[TCIA] Error getting studies for %s: %s", collection_id, e)
            continue
    
    logger.info("[TCIA] search_by_diagnosis: %d results for '%s' (cancer-related: %s)", len(results), diagnosis, is_cancer)
    
    return {
        'results': results,
        'is_cancer_related': is_cancer,
        'warning': warning
    }
