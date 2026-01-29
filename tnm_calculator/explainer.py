"""
TNM Calculator Explanation Generator

Generates human-readable explanations for TNM staging results.
Critical for clinical usability and transparency.
"""

from typing import Optional, List, Dict, Any
from .models import CancerDefinition, StagingType, TNMInput


class Explainer:
    """
    Generates human-readable explanations for TNM staging.
    
    Every staging result must include:
    - Why this T was assigned
    - Why this N was assigned
    - Why this final stage applies
    """
    
    def __init__(self, definition: CancerDefinition):
        """
        Initialize the explainer with a cancer definition.
        
        Args:
            definition: The cancer definition containing criteria text
        """
        self.definition = definition
    
    def explain_t(
        self,
        t_category: str,
        subsite: Optional[str] = None
    ) -> str:
        """
        Generate explanation for T category.
        
        Args:
            t_category: The T category (e.g., "T2")
            subsite: Optional subsite for subsite-specific criteria
            
        Returns:
            Human-readable explanation
        """
        criteria = self.definition.get_t_criteria(t_category, subsite)
        
        if criteria:
            return f"{t_category}: {criteria}"
        
        # Default explanations for common categories
        default_explanations = {
            "TX": "TX: Primary tumor cannot be assessed",
            "T0": "T0: No evidence of primary tumor",
            "Tis": "Tis: Carcinoma in situ",
            "T1": "T1: Tumor confined to the primary site",
            "T2": "T2: Tumor with local extension",
            "T3": "T3: Tumor with significant local extension",
            "T4": "T4: Tumor with extensive local invasion",
            "T4a": "T4a: Moderately advanced local disease",
            "T4b": "T4b: Very advanced local disease"
        }
        
        # Try to match with subcategories
        t_upper = t_category.upper()
        for key, explanation in default_explanations.items():
            if t_upper.startswith(key):
                return explanation
        
        return f"{t_category}: Primary tumor classification"
    
    def explain_n(
        self,
        n_category: str,
        staging_type: StagingType = StagingType.CLINICAL
    ) -> str:
        """
        Generate explanation for N category.
        
        Args:
            n_category: The N category (e.g., "N1")
            staging_type: Clinical or pathological staging
            
        Returns:
            Human-readable explanation
        """
        criteria = self.definition.get_n_criteria(n_category, staging_type)
        
        if criteria:
            return f"{n_category}: {criteria}"
        
        # Default explanations
        default_explanations = {
            "NX": "NX: Regional lymph nodes cannot be assessed",
            "N0": "N0: No regional lymph node metastasis",
            "N1": "N1: Limited regional lymph node involvement",
            "N2": "N2: Moderate regional lymph node involvement",
            "N2a": "N2a: Metastasis in single ipsilateral lymph node(s)",
            "N2b": "N2b: Metastasis in multiple ipsilateral lymph nodes",
            "N2c": "N2c: Metastasis in bilateral or contralateral lymph nodes",
            "N3": "N3: Extensive regional lymph node involvement",
            "N3a": "N3a: Metastasis in lymph node(s) >6 cm without ENE",
            "N3b": "N3b: Metastasis with extranodal extension (ENE)"
        }
        
        n_upper = n_category.upper()
        for key, explanation in default_explanations.items():
            if n_upper == key or n_upper.startswith(key):
                return explanation
        
        return f"{n_category}: Regional lymph node classification"
    
    def explain_m(self, m_category: str) -> str:
        """
        Generate explanation for M category.
        
        Args:
            m_category: The M category (e.g., "M0", "M1")
            
        Returns:
            Human-readable explanation
        """
        criteria = self.definition.get_m_criteria(m_category)
        
        if criteria:
            return f"{m_category}: {criteria}"
        
        # Default explanations
        m_upper = m_category.upper()
        if m_upper.startswith("M0"):
            return "M0: No distant metastasis"
        elif m_upper.startswith("M1"):
            return "M1: Distant metastasis present"
        elif m_upper == "MX":
            return "MX: Distant metastasis cannot be assessed"
        
        return f"{m_category}: Distant metastasis classification"
    
    def explain_stage(
        self,
        stage: str,
        t_category: str,
        n_category: str,
        m_category: str,
        subsite: Optional[str] = None,
        staging_type: Optional[StagingType] = None
    ) -> str:
        """
        Generate comprehensive explanation for the final stage.
        
        Args:
            stage: The final stage group (e.g., "Stage IIIA")
            t_category: The T category
            n_category: The N category
            m_category: The M category
            subsite: Optional subsite
            staging_type: Clinical or pathological staging type
            
        Returns:
            Human-readable explanation of why this stage was assigned
        """
        tnm = f"{t_category}{n_category}{m_category}"
        cancer_name = self.definition.name
        version = self.definition.version
        
        # Build explanation parts
        parts = []
        
        # Stage assignment
        parts.append(f"{stage} assigned for {cancer_name}")
        
        # TNM classification
        parts.append(f"TNM Classification: {tnm}")
        
        # M1 override explanation
        if m_category.upper().startswith("M1"):
            parts.append("Note: Presence of distant metastasis (M1) results in Stage IV designation regardless of T or N status")
        
        # T explanation
        t_criteria = self.definition.get_t_criteria(t_category, subsite)
        if t_criteria:
            parts.append(f"T: {t_criteria}")
        
        # N explanation - use the correct staging type
        n_criteria = self.definition.get_n_criteria(n_category, staging_type or StagingType.CLINICAL)
        if n_criteria:
            parts.append(f"N: {n_criteria}")
        
        # M explanation
        m_criteria = self.definition.get_m_criteria(m_category)
        if m_criteria:
            parts.append(f"M: {m_criteria}")
        
        # Version reference
        parts.append(f"Based on AJCC {version}th Edition staging criteria")
        
        return " | ".join(parts)
    
    def generate_summary(
        self,
        stage: str,
        t_category: str,
        n_category: str,
        m_category: str,
        is_metastatic: bool = False
    ) -> str:
        """
        Generate a brief clinical summary.
        
        Example: "Stage IIIB because the tumour invades the chest wall (T4), 
        ipsilateral supraclavicular nodes are involved (N3), and no distant 
        metastasis is present (M0)."
        """
        cancer_name = self.definition.name
        
        # Get short descriptions
        t_desc = self._get_short_t_description(t_category)
        n_desc = self._get_short_n_description(n_category)
        m_desc = self._get_short_m_description(m_category)
        
        if is_metastatic:
            return (
                f"{stage} for {cancer_name.lower()} cancer because "
                f"{m_desc}, indicating advanced disease regardless of "
                f"local tumor extent ({t_category}) or nodal status ({n_category})."
            )
        
        return (
            f"{stage} for {cancer_name.lower()} cancer because "
            f"{t_desc} ({t_category}), {n_desc} ({n_category}), "
            f"and {m_desc} ({m_category})."
        )
    
    def _get_short_t_description(self, t_category: str) -> str:
        """Get a short description for T category."""
        t_upper = t_category.upper()
        
        descriptions = {
            "TX": "the primary tumor cannot be assessed",
            "T0": "there is no evidence of primary tumor",
            "TIS": "carcinoma in situ is present",
            "T1": "the tumor is confined to the primary site",
            "T1A": "the tumor is very small and localized",
            "T1B": "the tumor is small and localized",
            "T2": "the tumor has limited local extension",
            "T3": "the tumor has moderate local extension",
            "T4": "the tumor has extensive local invasion",
            "T4A": "the tumor shows moderately advanced local invasion",
            "T4B": "the tumor shows very advanced local invasion"
        }
        
        # Try exact match first
        if t_upper in descriptions:
            return descriptions[t_upper]
        
        # Try prefix match
        for key in sorted(descriptions.keys(), key=len, reverse=True):
            if t_upper.startswith(key):
                return descriptions[key]
        
        return f"the tumor is classified as {t_category}"
    
    def _get_short_n_description(self, n_category: str) -> str:
        """Get a short description for N category."""
        n_upper = n_category.upper()
        
        descriptions = {
            "NX": "regional lymph nodes cannot be assessed",
            "N0": "no regional lymph node involvement is present",
            "N1": "limited regional lymph node metastasis is present",
            "N2": "moderate regional lymph node metastasis is present",
            "N2A": "single ipsilateral node involvement is present",
            "N2B": "multiple ipsilateral nodes are involved",
            "N2C": "bilateral or contralateral nodes are involved",
            "N3": "extensive regional lymph node metastasis is present",
            "N3A": "large lymph node metastasis is present",
            "N3B": "lymph node metastasis with extranodal extension is present"
        }
        
        if n_upper in descriptions:
            return descriptions[n_upper]
        
        for key in sorted(descriptions.keys(), key=len, reverse=True):
            if n_upper.startswith(key):
                return descriptions[key]
        
        return f"nodes are classified as {n_category}"
    
    def _get_short_m_description(self, m_category: str) -> str:
        """Get a short description for M category."""
        m_upper = m_category.upper()
        
        if m_upper.startswith("M0"):
            return "no distant metastasis is present"
        elif m_upper.startswith("M1"):
            return "distant metastasis is present"
        elif m_upper == "MX":
            return "distant metastasis cannot be assessed"
        
        return f"metastasis is classified as {m_category}"
