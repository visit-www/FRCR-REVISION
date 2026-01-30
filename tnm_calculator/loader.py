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
        
        # Try loading from database as fallback
        definition = self._load_from_database(cancer_slug)
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
        
        # Prognostic stage groups (for breast cancer with biomarkers)
        prognostic_stage_groups = tnm.get("clinical_prognostic_stage_groups", [])
        slug = data.get("disease_name", "unknown").lower().replace(" ", "_")
        requires_biomarkers = len(prognostic_stage_groups) > 0 or "breast" in slug.lower()
        
        return CancerDefinition(
            name=data.get("disease_name", "Unknown"),
            slug=slug,
            version=str(data.get("diagnosis_year", "8")),
            subsites=subsites,
            t_definitions=t_definitions,
            n_definitions=n_definitions,
            m_definitions=m_definitions,
            stage_groups=stage_groups,
            notes=tnm.get("notes", []),
            prognostic_stage_groups=prognostic_stage_groups,
            requires_biomarkers=requires_biomarkers
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
        
        slug = disease.get("slug", "unknown")
        requires_biomarkers = "breast" in slug.lower()
        
        return CancerDefinition(
            name=disease.get("name", "Unknown"),
            slug=slug,
            version="8",
            subsites=[],
            t_definitions=t_definitions,
            n_definitions=n_definitions,
            m_definitions=m_definitions,
            stage_groups=stage_groups,
            notes=[],
            prognostic_stage_groups=[],
            requires_biomarkers=requires_biomarkers
        )
    
    def _load_from_database(self, cancer_slug: str) -> Optional[CancerDefinition]:
        """
        Load cancer definition from the database.
        
        Falls back to querying AJCCStagingData when JSON files don't have the data.
        """
        try:
            # Import here to avoid circular imports
            from models import AJCCStagingData, AJCCDiseaseSite
            from flask import current_app
            
            # Find disease site by slug
            disease = AJCCDiseaseSite.query.filter(
                AJCCDiseaseSite.slug == cancer_slug
            ).first()
            
            if not disease:
                # Try matching by name (case-insensitive)
                name_match = cancer_slug.replace("_", " ")
                disease = AJCCDiseaseSite.query.filter(
                    AJCCDiseaseSite.disease_name.ilike(f"%{name_match}%")
                ).first()
            
            if not disease:
                return None
            
            # Get staging data
            staging = AJCCStagingData.query.filter_by(disease_site_id=disease.id).first()
            if not staging or not staging.tnm_data_json:
                return None
            
            # Parse tnm_data_json
            tnm_data = json.loads(staging.tnm_data_json)
            
            # Build t_definitions
            t_definitions: Dict[str, List[Dict[str, str]]] = {}
            raw_t_defs = tnm_data.get("t_definitions", {})
            if isinstance(raw_t_defs, dict):
                for subsite, categories in raw_t_defs.items():
                    if isinstance(categories, list):
                        t_definitions[subsite] = categories
            elif isinstance(raw_t_defs, list):
                # Handle list format: [{subsite: "X", categories: [...]}]
                for item in raw_t_defs:
                    if isinstance(item, dict):
                        subsite = item.get("subsite", "default")
                        categories = item.get("categories", [])
                        t_definitions[subsite] = categories
            
            if not t_definitions:
                t_definitions["default"] = []
            
            # Build n_definitions
            n_definitions: Dict[str, List[Dict[str, str]]] = {}
            raw_n_defs = tnm_data.get("n_definitions", {})
            if isinstance(raw_n_defs, dict):
                if "clinical" in raw_n_defs:
                    n_definitions["clinical"] = raw_n_defs["clinical"]
                if "pathological" in raw_n_defs:
                    n_definitions["pathological"] = raw_n_defs["pathological"]
            elif isinstance(raw_n_defs, list):
                n_definitions["clinical"] = raw_n_defs
                n_definitions["pathological"] = raw_n_defs
            
            # M definitions
            m_definitions = tnm_data.get("m_definitions", [])
            if not m_definitions:
                m_definitions = [
                    {"category": "M0", "criteria": "No distant metastasis"},
                    {"category": "M1", "criteria": "Distant metastasis"}
                ]
            
            # Stage groups
            stage_groups = tnm_data.get("stage_groups", [])
            
            # Prognostic stage groups (for breast cancer with biomarkers)
            prognostic_stage_groups = tnm_data.get("clinical_prognostic_stage_groups", [])
            
            # Detect if cancer requires biomarkers (breast cancer)
            requires_biomarkers = len(prognostic_stage_groups) > 0 or disease.slug.lower() == "breast"
            
            # Get subsites
            subsites = list(t_definitions.keys())
            if subsites == ["default"]:
                subsites = []
            
            logger.info(f"[TNM Calculator] Loaded {disease.disease_name} from database "
                       f"({len(stage_groups)} stage groups, {len(prognostic_stage_groups)} prognostic groups)")
            
            return CancerDefinition(
                name=disease.disease_name,
                slug=disease.slug,
                version="8",  # Default to AJCC 8
                subsites=subsites,
                t_definitions=t_definitions,
                n_definitions=n_definitions,
                m_definitions=m_definitions,
                stage_groups=stage_groups,
                notes=tnm_data.get("notes", []),
                prognostic_stage_groups=prognostic_stage_groups,
                requires_biomarkers=requires_biomarkers
            )
            
        except Exception as e:
            logger.error(f"[TNM Calculator] Error loading from database: {e}")
            return None
    
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
        
        # If no cancers from ontology, try database first (has most complete data)
        if not cancers:
            cancers = self._get_cancers_from_database()
        
        # If still no cancers, check structured file as fallback
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
    
    def _get_cancers_from_database(self) -> List[Dict[str, str]]:
        """Get list of available cancers from database."""
        cancers = []
        try:
            from models import AJCCStagingData, AJCCDiseaseSite, AJCCBodySection
            
            # Get all diseases that have staging data with stage_groups OR clinical_prognostic_stage_groups
            staging_records = AJCCStagingData.query.all()
            
            for staging in staging_records:
                if not staging.tnm_data_json:
                    continue
                
                try:
                    tnm_data = json.loads(staging.tnm_data_json)
                    # Include cancers with either regular or prognostic stage groups
                    has_staging = tnm_data.get("stage_groups") or tnm_data.get("clinical_prognostic_stage_groups")
                    if not has_staging:
                        continue
                except:
                    continue
                
                disease = AJCCDiseaseSite.query.get(staging.disease_site_id)
                if not disease:
                    continue
                
                section = AJCCBodySection.query.get(disease.body_section_id) if disease.body_section_id else None
                
                cancers.append({
                    "name": disease.disease_name,
                    "slug": disease.slug,
                    "body_section": section.section_name if section else "Other"
                })
            
            logger.info(f"[TNM Calculator] Loaded {len(cancers)} cancers from database")
            
        except Exception as e:
            logger.error(f"[TNM Calculator] Error loading cancers from database: {e}")
        
        return cancers
    
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
