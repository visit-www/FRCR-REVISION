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
import requests
from typing import List, Dict, Optional
import json
import hashlib
from datetime import datetime, timedelta

# TCIA/NBIA API base URL
TCIA_API_BASE = "https://services.cancerimagingarchive.net/nbia-api/services/v1"

# Cache configuration
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache', 'tcia')
CACHE_DURATION_HOURS = 168  # Cache for 1 week (metadata doesn't change often)


def ensure_cache_dir():
    """Create cache directory if it doesn't exist."""
    os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_key(endpoint: str, params: Dict) -> str:
    """Generate cache key from endpoint and parameters."""
    cache_data = f"{endpoint}_{json.dumps(params, sort_keys=True)}"
    return hashlib.md5(cache_data.encode()).hexdigest()


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
        print(f"TCIA cache read error: {e}")
    
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
        print(f"TCIA cache write error: {e}")


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
        
        collections = response.json()
        
        # Filter collections
        filtered = []
        for collection in collections:
            name = collection.get('Collection', '').lower()
            description = collection.get('Description', '').lower()
            
            # Apply filters
            if cancer_type and cancer_type.lower() not in name and cancer_type.lower() not in description:
                continue
            
            # Note: Modality and body part filtering would require additional API calls
            # For now, return all collections and let frontend filter
            
            filtered.append({
                'collection_id': collection.get('Collection'),
                'name': collection.get('Collection'),
                'description': collection.get('Description'),
                'subject_count': collection.get('SubjectCount', 0),
                'image_count': collection.get('ImageCount', 0)
            })
        
        # Cache results
        cache_result(cache_key, filtered)
        
        return filtered[:max_results]
        
    except Exception as e:
        print(f"TCIA search error: {e}")
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
        print(f"TCIA get studies error: {e}")
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
        
        # Format series
        formatted_series = []
        for series in series_list:
            series_uid = series.get('SeriesInstanceUID', '')
            
            # Generate TCIA viewer link
            viewer_link = f"https://www.cancerimagingarchive.net/viewer/?studyInstanceUID={study_instance_uid}&seriesInstanceUID={series_uid}"
            
            formatted_series.append({
                'series_instance_uid': series_uid,
                'series_description': series.get('SeriesDescription', ''),
                'modality': series.get('Modality', ''),
                'body_part': series.get('BodyPartExamined', ''),
                'image_count': series.get('NumberOfSeriesRelatedInstances', 0),
                'viewer_link': viewer_link,
                'study_instance_uid': study_instance_uid
            })
        
        # Cache results
        cache_result(cache_key, formatted_series)
        
        return formatted_series
        
    except Exception as e:
        print(f"TCIA get series error: {e}")
        return []


def search_by_diagnosis(diagnosis: str, modality: Optional[str] = None) -> List[Dict]:
    """
    Search TCIA collections by diagnosis/keywords.
    
    Exam Relevance: Helps candidates find relevant cases for specific diagnoses.
    
    Args:
        diagnosis: Diagnosis or keywords to search
        modality: Optional modality filter (CT, MRI, PET)
    
    Returns:
        List of relevant collections and studies
    """
    # Search collections by keywords
    collections = search_collections(cancer_type=diagnosis, modality=modality)
    
    results = []
    for collection in collections[:5]:  # Limit to top 5 collections
        collection_id = collection['collection_id']
        studies = get_collection_studies(collection_id, max_results=5)
        
        for study in studies:
            series_list = get_study_series(study['study_instance_uid'])
            
            results.append({
                'collection': collection,
                'study': study,
                'series': series_list[:3]  # Top 3 series per study
            })
    
    return results
