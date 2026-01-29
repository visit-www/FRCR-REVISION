"""
TNM Calculator Rule Loader

Loads TNM staging rules from JSON data files.
Supports the existing AJCC data format used in the application.
"""

import json
import os
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from .models import CancerDefinition, StagingType

logger = logging.getLogger(__name__)


class RuleLoader:
    """
    Loads TNM staging rules from JSON data files.
    
    Supports loading from:
    - ajcc_tnm_structured.json (single disease structured data)
    - ajcc_data_export.json (multiple diseases)
    - ajcc_frcr_full_ontology.json (full ontology with all diseases)
    """
    
    # Cache for loaded definitions
    _cache: Dict[str, CancerDefinition] = {}
    _all_cancers_loaded: bool = False
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize the rule loader.
        
        Args:
            data_dir: Path to the data directory. Defaults to ajcc_tnm/data/
        """
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            # Default to ajcc_tnm/data relative to this file's location
            module_dir = Path(__file__).parent.parent
            self.data_dir = module_dir / "ajcc_tnm" / "data"
        
        logger.info(f"[TNM Calculator] Rule loader initialized with data_dir: {self.data_dir}")
    
    def load_cancer_definition(self, cancer_type: str) -> Optional[CancerDefinition]:
        """
        Load the definition for a specific cancer type.
        
        Args:
            cancer_type: The cancer type slug (e.g., "larynx", "breast")
            
        Returns:
            CancerDefinition if found, None otherwise
        """
        cancer_slug = cancer_type.lower().replace(" ", "_")
        
        # Check cache first
        if cancer_slug in self._cache:
            return self._cache[cancer_slug]
        
        # Try loading from structured data file
        definition = self._load_from_structured_file(cancer_slug)
        if definition:
            self._cache[cancer_slug] = definition
            return definition
        
        # Try loading from full ontology
        definition = self._load_from_ontology(cancer_slug)
        if definition:
            self._cache[cancer_slug] = definition
            return definition
        
        logger.warning(f"[TNM Calculator] No definition found for cancer type: {cancer_type}")
        return None
    
    def _load_from_structured_file(self, cancer_slug: str) -> Optional[CancerDefinition]:
        """Load from ajcc_tnm_structured.json or similar structured file."""
        structured_file = self.data_dir / "ajcc_tnm_structured.json"
        
        if not structured_file.exists():
            return None
        
        try:
            with open(structured_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check if this file contains the requested cancer type
            disease_name = data.get("disease_name", "").lower().replace(" ", "_")
            if disease_name == cancer_slug or cancer_slug in disease_name:
                return self._parse_structured_data(data)
            
        except Exception as e:
            logger.error(f"[TNM Calculator] Error loading structured file: {e}")
        
        return None
    
    def _load_from_ontology(self, cancer_slug: str) -> Optional[CancerDefinition]:
        """Load from ajcc_frcr_full_ontology.json."""
        ontology_file = self.data_dir / "ajcc_frcr_full_ontology.json"
        
        if not ontology_file.exists():
            return None
        
        try:
            with open(ontology_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Search for the cancer type in the ontology
            for section in data.get("body_sections", []):
                for disease in section.get("diseases", []):
                    disease_slug = disease.get("slug", "").lower()
                    disease_name = disease.get("name", "").lower().replace(" ", "_")
                    
                    if cancer_slug in [disease_slug, disease_name]:
                        return self._parse_ontology_disease(disease)
            
        except Exception as e:
            logger.error(f"[TNM Calculator] Error loading ontology file: {e}")
        
        return None
    
    def _parse_structured_data(self, data: Dict[str, Any]) -> CancerDefinition:
        """Parse structured data format (from ajcc_tnm_structured.json)."""
        tnm = data.get("tnm_staging", {})
        
        # Parse T definitions - may have subsites
        t_definitions: Dict[str, List[Dict[str, str]]] = {}
        raw_t_defs = tnm.get("t_definitions", [])
        
        if isinstance(raw_t_defs, list):
            for item in raw_t_defs:
                if isinstance(item, dict) and "subsite" in item:
                    subsite = item["subsite"]
                    categories = item.get("categories", [])
                    t_definitions[subsite] = categories
                elif isinstance(item, dict) and "category" in item:
                    # Flat list format
                    if "default" not in t_definitions:
                        t_definitions["default"] = []
                    t_definitions["default"].append(item)
        
        # If no subsites, use "default"
        if not t_definitions:
            t_definitions["default"] = []
        
        # Parse N definitions - may have clinical/pathological
        n_definitions: Dict[str, List[Dict[str, str]]] = {}
        raw_n_defs = tnm.get("n_definitions", {})
        
        if isinstance(raw_n_defs, dict):
            if "clinical" in raw_n_defs:
                n_definitions["clinical"] = raw_n_defs["clinical"]
            if "pathological" in raw_n_defs:
                n_definitions["pathological"] = raw_n_defs["pathological"]
        elif isinstance(raw_n_defs, list):
            n_definitions["clinical"] = raw_n_defs
            n_definitions["pathological"] = raw_n_defs
        
        # Parse M definitions
        m_definitions = tnm.get("m_definitions", [])
        if not m_definitions:
            m_definitions = [
                {"category": "M0", "criteria": "No distant metastasis"},
                {"category": "M1", "criteria": "Distant metastasis"}
            ]
        
        # Parse stage groups
        stage_groups = tnm.get("stage_groups", [])
        
        # Get subsites list
        subsites = list(t_definitions.keys())
        if subsites == ["default"]:
            subsites = []
        
        return CancerDefinition(
            name=data.get("disease_name", "Unknown"),
            slug=data.get("disease_name", "unknown").lower().replace(" ", "_"),
            version=str(data.get("diagnosis_year", "8")),
            subsites=subsites,
            t_definitions=t_definitions,
            n_definitions=n_definitions,
            m_definitions=m_definitions,
            stage_groups=stage_groups,
            notes=tnm.get("notes", [])
        )
    
    def _parse_ontology_disease(self, disease: Dict[str, Any]) -> CancerDefinition:
        """Parse disease from ontology format."""
        # This is a simplified parser - the full ontology has more complex structure
        staging = disease.get("staging", {})
        
        t_definitions: Dict[str, List[Dict[str, str]]] = {"default": []}
        n_definitions: Dict[str, List[Dict[str, str]]] = {
            "clinical": [],
            "pathological": []
        }
        m_definitions: List[Dict[str, str]] = []
        stage_groups: List[Dict[str, str]] = []
        
        # Parse T categories
        for t_cat in staging.get("t_categories", []):
            t_definitions["default"].append({
                "category": t_cat.get("code", ""),
                "criteria": t_cat.get("description", "")
            })
        
        # Parse N categories
        for n_cat in staging.get("n_categories", []):
            n_definitions["clinical"].append({
                "category": n_cat.get("code", ""),
                "criteria": n_cat.get("description", "")
            })
            n_definitions["pathological"].append({
                "category": n_cat.get("code", ""),
                "criteria": n_cat.get("description", "")
            })
        
        # Parse M categories
        for m_cat in staging.get("m_categories", []):
            m_definitions.append({
                "category": m_cat.get("code", ""),
                "criteria": m_cat.get("description", "")
            })
        
        # Default M if not specified
        if not m_definitions:
            m_definitions = [
                {"category": "M0", "criteria": "No distant metastasis"},
                {"category": "M1", "criteria": "Distant metastasis"}
            ]
        
        # Parse stage groups
        for sg in staging.get("stage_groups", []):
            stage_groups.append({
                "T": sg.get("t", ""),
                "N": sg.get("n", ""),
                "M": sg.get("m", ""),
                "stage": sg.get("stage", "")
            })
        
        return CancerDefinition(
            name=disease.get("name", "Unknown"),
            slug=disease.get("slug", "unknown"),
            version="8",
            subsites=[],
            t_definitions=t_definitions,
            n_definitions=n_definitions,
            m_definitions=m_definitions,
            stage_groups=stage_groups,
            notes=[]
        )
    
    def get_available_cancers(self) -> List[Dict[str, str]]:
        """
        Get a list of all available cancer types.
        
        Returns:
            List of dicts with 'name' and 'slug' keys
        """
        cancers = []
        
        # Try loading from ontology file
        ontology_file = self.data_dir / "ajcc_frcr_full_ontology.json"
        if ontology_file.exists():
            try:
                with open(ontology_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for section in data.get("body_sections", []):
                    for disease in section.get("diseases", []):
                        cancers.append({
                            "name": disease.get("name", "Unknown"),
                            "slug": disease.get("slug", "unknown"),
                            "body_section": section.get("name", "Other")
                        })
            except Exception as e:
                logger.error(f"[TNM Calculator] Error loading cancer list: {e}")
        
        # If no ontology, check for structured file
        if not cancers:
            structured_file = self.data_dir / "ajcc_tnm_structured.json"
            if structured_file.exists():
                try:
                    with open(structured_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    cancers.append({
                        "name": data.get("disease_name", "Unknown"),
                        "slug": data.get("disease_name", "unknown").lower().replace(" ", "_"),
                        "body_section": "Unknown"
                    })
                except Exception as e:
                    logger.error(f"[TNM Calculator] Error loading structured file: {e}")
        
        return sorted(cancers, key=lambda x: x["name"])
    
    def clear_cache(self):
        """Clear the definition cache."""
        self._cache.clear()
        self._all_cancers_loaded = False


# Global instance for convenience
_default_loader: Optional[RuleLoader] = None


def get_loader() -> RuleLoader:
    """Get the default rule loader instance."""
    global _default_loader
    if _default_loader is None:
        _default_loader = RuleLoader()
    return _default_loader
