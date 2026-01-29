"""
TNM Calculator Data Models

Defines the input and output data structures for the TNM Calculator.
All models are designed to be JSON-serializable for API usage.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class StagingType(str, Enum):
    """Type of staging being performed."""
    CLINICAL = "clinical"      # cTNM - based on clinical/imaging findings
    PATHOLOGICAL = "pathological"  # pTNM - based on pathology after surgery
    POST_THERAPY = "post_therapy"  # ypTNM - after neoadjuvant therapy


@dataclass
class TNMInput:
    """
    Input data for TNM staging calculation.
    
    Attributes:
        cancer_type: The type of cancer (e.g., "larynx", "breast", "lung")
        t_category: The T category (e.g., "T1", "T2", "T3", "T4a")
        n_category: The N category (e.g., "N0", "N1", "N2", "N3")
        m_category: The M category (e.g., "M0", "M1")
        staging_type: Clinical, pathological, or post-therapy staging
        subsite: Optional subsite for cancers with subsite-specific T definitions
        version: AJCC version (default: "8")
    """
    cancer_type: str
    t_category: str
    n_category: str
    m_category: str
    staging_type: StagingType = StagingType.CLINICAL
    subsite: Optional[str] = None
    version: str = "8"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "cancer_type": self.cancer_type,
            "t_category": self.t_category,
            "n_category": self.n_category,
            "m_category": self.m_category,
            "staging_type": self.staging_type.value,
            "subsite": self.subsite,
            "version": self.version
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TNMInput":
        """Create from dictionary."""
        staging_type = data.get("staging_type", "clinical")
        if isinstance(staging_type, str):
            staging_type = StagingType(staging_type)
        
        return cls(
            cancer_type=data["cancer_type"],
            t_category=data["t_category"],
            n_category=data["n_category"],
            m_category=data["m_category"],
            staging_type=staging_type,
            subsite=data.get("subsite"),
            version=data.get("version", "8")
        )


@dataclass
class ValidationError:
    """Represents a validation error in TNM input."""
    field: str
    message: str
    severity: str = "error"  # "error" or "warning"


@dataclass
class TNMResult:
    """
    Result of TNM staging calculation.
    
    Attributes:
        success: Whether the calculation was successful
        tnm_classification: The full TNM classification (e.g., "T2N1M0")
        stage_group: The final stage group (e.g., "Stage IIIA")
        t_category: The validated/normalized T category
        n_category: The validated/normalized N category
        m_category: The validated/normalized M category
        t_explanation: Human-readable explanation for T category
        n_explanation: Human-readable explanation for N category
        m_explanation: Human-readable explanation for M category
        stage_explanation: Human-readable explanation for final stage
        disclaimer: Clinical safety disclaimer
        validation_errors: List of validation errors if any
        cancer_type: The cancer type used
        version: AJCC version used
        calculated_at: Timestamp of calculation
    """
    success: bool
    tnm_classification: str
    stage_group: str
    t_category: str
    n_category: str
    m_category: str
    t_explanation: str
    n_explanation: str
    m_explanation: str
    stage_explanation: str
    disclaimer: str
    cancer_type: str
    version: str
    validation_errors: List[ValidationError] = field(default_factory=list)
    staging_type: StagingType = StagingType.CLINICAL
    subsite: Optional[str] = None
    calculated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # Additional metadata
    stage_color: str = ""  # For UI display
    is_metastatic: bool = False
    available_t_categories: List[str] = field(default_factory=list)
    available_n_categories: List[str] = field(default_factory=list)
    available_m_categories: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "tnm_classification": self.tnm_classification,
            "stage_group": self.stage_group,
            "t_category": self.t_category,
            "n_category": self.n_category,
            "m_category": self.m_category,
            "t_explanation": self.t_explanation,
            "n_explanation": self.n_explanation,
            "m_explanation": self.m_explanation,
            "stage_explanation": self.stage_explanation,
            "disclaimer": self.disclaimer,
            "cancer_type": self.cancer_type,
            "version": self.version,
            "validation_errors": [
                {"field": e.field, "message": e.message, "severity": e.severity}
                for e in self.validation_errors
            ],
            "staging_type": self.staging_type.value,
            "subsite": self.subsite,
            "calculated_at": self.calculated_at,
            "stage_color": self.stage_color,
            "is_metastatic": self.is_metastatic,
            "available_t_categories": self.available_t_categories,
            "available_n_categories": self.available_n_categories,
            "available_m_categories": self.available_m_categories
        }
    
    @staticmethod
    def error(message: str, cancer_type: str = "", version: str = "8") -> "TNMResult":
        """Create an error result."""
        return TNMResult(
            success=False,
            tnm_classification="",
            stage_group="",
            t_category="",
            n_category="",
            m_category="",
            t_explanation="",
            n_explanation="",
            m_explanation="",
            stage_explanation="",
            disclaimer=TNMResult.get_disclaimer(),
            cancer_type=cancer_type,
            version=version,
            validation_errors=[ValidationError(field="general", message=message)]
        )
    
    @staticmethod
    def get_disclaimer() -> str:
        """Return the standard clinical disclaimer."""
        return (
            "Decision-support only. Final staging responsibility remains with "
            "the treating clinician. This calculator is for educational purposes "
            "and should not replace clinical judgment."
        )


@dataclass
class CancerDefinition:
    """
    Definition of a cancer type with its TNM staging rules.
    
    Loaded from JSON data files.
    """
    name: str
    slug: str
    version: str
    subsites: List[str]
    t_definitions: Dict[str, List[Dict[str, str]]]  # subsite -> categories
    n_definitions: Dict[str, List[Dict[str, str]]]  # clinical/pathological -> categories
    m_definitions: List[Dict[str, str]]
    stage_groups: List[Dict[str, str]]
    notes: List[str] = field(default_factory=list)
    
    def get_t_categories(self, subsite: Optional[str] = None) -> List[str]:
        """Get available T categories for a subsite."""
        if subsite and subsite in self.t_definitions:
            return [cat["category"] for cat in self.t_definitions[subsite]]
        # Return first subsite's categories if no specific subsite
        if self.t_definitions:
            first_subsite = list(self.t_definitions.keys())[0]
            return [cat["category"] for cat in self.t_definitions[first_subsite]]
        return []
    
    def get_n_categories(self, staging_type: StagingType = StagingType.CLINICAL) -> List[str]:
        """Get available N categories."""
        key = "pathological" if staging_type == StagingType.PATHOLOGICAL else "clinical"
        if key in self.n_definitions:
            return [cat["category"] for cat in self.n_definitions[key]]
        # Fallback to any available
        for cats in self.n_definitions.values():
            return [cat["category"] for cat in cats]
        return []
    
    def get_m_categories(self) -> List[str]:
        """Get available M categories."""
        return [cat["category"] for cat in self.m_definitions]
    
    def get_t_criteria(self, t_category: str, subsite: Optional[str] = None) -> Optional[str]:
        """Get the criteria text for a T category."""
        subsites_to_check = [subsite] if subsite else list(self.t_definitions.keys())
        for ss in subsites_to_check:
            if ss in self.t_definitions:
                for cat in self.t_definitions[ss]:
                    if cat["category"] == t_category:
                        return cat.get("criteria", "")
        return None
    
    def get_n_criteria(self, n_category: str, staging_type: StagingType = StagingType.CLINICAL) -> Optional[str]:
        """Get the criteria text for an N category."""
        key = "pathological" if staging_type == StagingType.PATHOLOGICAL else "clinical"
        if key in self.n_definitions:
            for cat in self.n_definitions[key]:
                if cat["category"] == n_category:
                    return cat.get("criteria", "")
        return None
    
    def get_m_criteria(self, m_category: str) -> Optional[str]:
        """Get the criteria text for an M category."""
        for cat in self.m_definitions:
            if cat["category"] == m_category:
                return cat.get("criteria", "")
        return None
