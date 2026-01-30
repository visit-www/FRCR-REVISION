"""
TNM Calculator Stage Resolver

Resolves the final stage group from T, N, M categories using staging tables.
Implements the clinical logic for TNM staging.
"""

import re
import logging
from typing import Optional, List, Tuple, Dict, Any

from .models import CancerDefinition, StagingType

logger = logging.getLogger(__name__)


class StageResolver:
    """
    Resolves stage groups from T, N, M categories.
    
    Implements the clinical staging logic:
    1. Apply M overrides (M1 → highest stage, typically Stage IV)
    2. Match T and N against stage group table
    3. Handle special cases (Any T, Any N, etc.)
    """
    
    # Stage hierarchy for comparison (lower index = earlier stage)
    STAGE_HIERARCHY = [
        "0", "I", "IA", "IA1", "IA2", "IA3", "IB", "IB1", "IB2",
        "II", "IIA", "IIA1", "IIA2", "IIB", "IIC",
        "III", "IIIA", "IIIB", "IIIC", "IIIC1", "IIIC2", "IIID",
        "IV", "IVA", "IVA1", "IVA2", "IVB", "IVC"
    ]
    
    # Color mapping for stages
    STAGE_COLORS = {
        "0": "#28a745",      # Green - early
        "I": "#28a745",      # Green
        "IA": "#28a745",
        "IA1": "#28a745",
        "IA2": "#28a745",
        "IA3": "#28a745",
        "IB": "#28a745",
        "IB1": "#28a745",
        "IB2": "#28a745",
        "II": "#ffc107",     # Yellow/Orange - intermediate
        "IIA": "#ffc107",
        "IIA1": "#ffc107",
        "IIA2": "#ffc107",
        "IIB": "#ffc107",
        "IIC": "#ffc107",
        "III": "#fd7e14",    # Orange - advanced
        "IIIA": "#fd7e14",
        "IIIB": "#fd7e14",
        "IIIC": "#fd7e14",
        "IIIC1": "#fd7e14",
        "IIIC2": "#fd7e14",
        "IIID": "#fd7e14",
        "IV": "#dc3545",     # Red - metastatic
        "IVA": "#dc3545",
        "IVA1": "#dc3545",
        "IVA2": "#dc3545",
        "IVB": "#dc3545",
        "IVC": "#dc3545"
    }
    
    def __init__(self, definition: CancerDefinition):
        """
        Initialize the resolver with a cancer definition.
        
        Args:
            definition: The cancer definition containing staging rules
        """
        self.definition = definition
    
    def resolve(
        self,
        t_category: str,
        n_category: str,
        m_category: str
    ) -> Tuple[str, bool, str]:
        """
        Resolve the stage group from T, N, M categories.
        
        Args:
            t_category: The T category (e.g., "T2", "T3")
            n_category: The N category (e.g., "N0", "N1")
            m_category: The M category (e.g., "M0", "M1")
            
        Returns:
            Tuple of (stage_group, is_metastatic, stage_color)
        """
        # Normalize categories
        t_cat = self._normalize_category(t_category)
        n_cat = self._normalize_category(n_category)
        m_cat = self._normalize_category(m_category)
        
        # Check for M1 override first
        if m_cat.startswith("M1"):
            stage = self._find_m1_stage()
            return (f"Stage {stage}", True, self.STAGE_COLORS.get(stage, "#dc3545"))
        
        # Find matching stage group
        stage = self._match_stage_group(t_cat, n_cat, m_cat)
        
        if stage:
            is_metastatic = stage.startswith("IV")
            return (f"Stage {stage}", is_metastatic, self.STAGE_COLORS.get(stage, "#5E899E"))
        
        # If no match found, return unknown
        logger.warning(f"[TNM Calculator] No stage match found for {t_cat}{n_cat}{m_cat}")
        return ("Unknown Stage", False, "#6c757d")
    
    def _normalize_category(self, category: str) -> str:
        """Normalize a T/N/M category for matching."""
        if not category:
            return ""
        
        # Remove leading/trailing whitespace
        cat = category.strip().upper()
        
        # Handle common variations
        cat = cat.replace("IS", "is")  # Tis
        
        return cat
    
    def _find_m1_stage(self) -> str:
        """Find the stage for M1 (typically the highest stage)."""
        # Look for M1 in stage groups
        for group in self.definition.stage_groups:
            m_value = group.get("M", "").upper()
            if "M1" in m_value:
                return group.get("stage", "IV")
        
        # Default to IVC for M1 if no specific rule
        # Check what stage variants exist
        stages = [g.get("stage", "") for g in self.definition.stage_groups]
        
        # Find the highest stage
        for stage in ["IVC", "IVB", "IVA", "IV"]:
            if stage in stages:
                return stage
        
        return "IV"
    
    def _match_stage_group(self, t_cat: str, n_cat: str, m_cat: str) -> Optional[str]:
        """
        Match against the stage group table.
        
        Handles patterns like "T1, T2, T3" and "Any T".
        """
        best_match: Optional[str] = None
        
        for group in self.definition.stage_groups:
            t_pattern = group.get("T", "").upper()
            n_pattern = group.get("N", "").upper()
            m_pattern = group.get("M", "").upper()
            stage = group.get("stage", "")
            
            # Check if M matches
            if not self._matches_pattern(m_cat, m_pattern):
                continue
            
            # Check if T matches
            if not self._matches_pattern(t_cat, t_pattern):
                continue
            
            # Check if N matches
            if not self._matches_pattern(n_cat, n_pattern):
                continue
            
            # Found a match
            best_match = stage
            
            # If exact match (not "Any" patterns), prefer it
            if "ANY" not in t_pattern and "ANY" not in n_pattern:
                return stage
        
        return best_match
    
    def _matches_pattern(self, value: str, pattern: str) -> bool:
        """
        Check if a value matches a pattern from the stage table.
        
        Patterns can be:
        - Single value: "T1", "N0", "M0"
        - Multiple values: "T1, T2, T3" or "N0, N1"
        - Wildcards: "Any T", "Any N"
        - Subcategories match parent: "T1a" matches "T1"
        """
        if not pattern:
            return True
        
        pattern = pattern.upper().strip()
        value = value.upper().strip()
        
        # Handle "Any" pattern
        if "ANY" in pattern:
            return True
        
        # Split multiple patterns
        patterns = [p.strip() for p in pattern.replace(",", " ").split()]
        
        for p in patterns:
            if self._value_matches_single_pattern(value, p):
                return True
        
        return False
    
    def _value_matches_single_pattern(self, value: str, pattern: str) -> bool:
        """Check if a value matches a single pattern."""
        # Exact match
        if value == pattern:
            return True
        
        # Handle range patterns like "T3-T4" or "M1a-M1b"
        if '-' in pattern:
            parts = pattern.split('-')
            if len(parts) == 2:
                start, end = parts[0].strip(), parts[1].strip()
                # Exact match with start or end
                if value == start or value == end:
                    return True
                # Value is subcategory of start or end (e.g., T3a matches T3-T4)
                # Extra chars must not start with digit
                if value.startswith(start) and len(value) > len(start):
                    extra = value[len(start):]
                    if not extra[0].isdigit():
                        return True
                if value.startswith(end) and len(value) > len(end):
                    extra = value[len(end):]
                    if not extra[0].isdigit():
                        return True
                # Pattern part starts with value (e.g., M1 matches M1a-M1b)
                if start.startswith(value) and len(start) > len(value):
                    extra = start[len(value):]
                    if not extra[0].isdigit():
                        return True
                if end.startswith(value) and len(end) > len(value):
                    extra = end[len(value):]
                    if not extra[0].isdigit():
                        return True
        
        # Subcategory match (T1a matches T1)
        if value.startswith(pattern) and len(value) > len(pattern):
            extra = value[len(pattern):]
            if not extra[0].isdigit():
                return True
        
        # Parent category match (T1 matches T1a, T1b, etc.)
        if pattern.startswith(value) and len(pattern) > len(value):
            extra = pattern[len(value):]
            if not extra[0].isdigit():
                return True
        
        return False
    
    def get_stage_color(self, stage: str) -> str:
        """Get the color for a stage."""
        # Remove "Stage " prefix if present
        stage_clean = stage.replace("Stage ", "").strip()
        return self.STAGE_COLORS.get(stage_clean, "#5E899E")
    
    def resolve_prognostic(
        self,
        t_category: str,
        n_category: str,
        m_category: str,
        grade: str,
        her2_status: str,
        er_status: str,
        pr_status: str
    ) -> Tuple[str, bool, str, str]:
        """
        Resolve the prognostic stage group using biomarkers (for breast cancer).
        
        Args:
            t_category: The T category
            n_category: The N category
            m_category: The M category
            grade: Tumor grade (G1, G2, G3)
            her2_status: HER2 status (Positive, Negative)
            er_status: ER status (Positive, Negative)
            pr_status: PR status (Positive, Negative)
            
        Returns:
            Tuple of (stage_group, is_metastatic, stage_color, explanation)
        """
        # Normalize categories
        t_cat = self._normalize_category(t_category)
        n_cat = self._normalize_category(n_category)
        m_cat = self._normalize_category(m_category)
        
        # Normalize biomarkers
        grade_norm = grade.upper() if grade else ""
        her2_norm = her2_status.capitalize() if her2_status else ""
        er_norm = er_status.capitalize() if er_status else ""
        pr_norm = pr_status.capitalize() if pr_status else ""
        
        # Check for M1 override first - always Stage IV
        if m_cat.startswith("M1"):
            explanation = "M1 (distant metastasis) automatically classifies as Stage IV regardless of biomarkers."
            return ("Stage IV", True, self.STAGE_COLORS.get("IV", "#dc3545"), explanation)
        
        # Match against prognostic stage groups
        if not hasattr(self.definition, 'prognostic_stage_groups') or not self.definition.prognostic_stage_groups:
            # Fall back to anatomic staging
            stage, is_meta, color = self.resolve(t_category, n_category, m_category)
            explanation = "Prognostic staging data not available. Using anatomic staging."
            return (stage, is_meta, color, explanation)
        
        # Find matching prognostic stage
        for group in self.definition.prognostic_stage_groups:
            if self._matches_prognostic_pattern(
                t_cat, n_cat, m_cat,
                grade_norm, her2_norm, er_norm, pr_norm,
                group
            ):
                stage = group.get("stage", "")
                is_metastatic = stage.startswith("IV")
                color = self.STAGE_COLORS.get(stage, "#5E899E")
                
                # Build explanation
                explanation = self._build_prognostic_explanation(
                    t_cat, n_cat, m_cat,
                    grade_norm, her2_norm, er_norm, pr_norm,
                    stage
                )
                
                return (f"Stage {stage}", is_metastatic, color, explanation)
        
        # No exact match found - try to find closest match
        logger.warning(f"[TNM Calculator] No prognostic stage match for "
                      f"{t_cat}{n_cat}{m_cat} G:{grade_norm} HER2:{her2_norm} ER:{er_norm} PR:{pr_norm}")
        
        # Fall back to anatomic staging with warning
        stage, is_meta, color = self.resolve(t_category, n_category, m_category)
        explanation = (f"No exact prognostic stage match found for this biomarker combination. "
                      f"Using anatomic stage ({stage}) as fallback.")
        return (stage, is_meta, color, explanation)
    
    def _matches_prognostic_pattern(
        self,
        t_cat: str, n_cat: str, m_cat: str,
        grade: str, her2: str, er: str, pr: str,
        group: Dict[str, str]
    ) -> bool:
        """Check if T/N/M and biomarkers match a prognostic stage group pattern."""
        # Get patterns from group
        tnm_pattern = group.get("tnm", "").upper()
        grade_pattern = group.get("grade", "").upper()
        her2_pattern = group.get("her2", "").capitalize()
        er_pattern = group.get("er", "").capitalize()
        pr_pattern = group.get("pr", "").capitalize()
        
        # Match TNM pattern (can be comma-separated like "T1 N0 M0, T0 N1mi M0")
        if not self._matches_tnm_combo(t_cat, n_cat, m_cat, tnm_pattern):
            return False
        
        # Match grade (handle "Any", "G1-G2", etc.)
        if not self._matches_biomarker_pattern(grade, grade_pattern):
            return False
        
        # Match HER2
        if not self._matches_biomarker_pattern(her2, her2_pattern):
            return False
        
        # Match ER
        if not self._matches_biomarker_pattern(er, er_pattern):
            return False
        
        # Match PR
        if not self._matches_biomarker_pattern(pr, pr_pattern):
            return False
        
        return True
    
    def _matches_tnm_combo(self, t_cat: str, n_cat: str, m_cat: str, pattern: str) -> bool:
        """Match T/N/M against a TNM pattern like 'T1 N0 M0, T0 N1MI M0'."""
        if not pattern or "ANY" in pattern.upper():
            return True
        
        # Split by comma for multiple TNM combos
        combos = [c.strip() for c in pattern.split(",")]
        
        for combo in combos:
            # Parse T, N, M from combo (e.g., "T1 N0 M0" or "T2N1M0")
            parts = combo.replace(" ", "").upper()
            
            # Extract T, N, M using regex
            t_match = re.search(r'(T[0-9A-Z]+)', parts)
            n_match = re.search(r'(N[0-9A-Z]+)', parts)
            m_match = re.search(r'(M[0-9A-Z]+)', parts)
            
            t_pattern = t_match.group(1) if t_match else ""
            n_pattern = n_match.group(1) if n_match else ""
            m_pattern_str = m_match.group(1) if m_match else ""
            
            # Check if current values match this combo
            t_matches = self._matches_pattern(t_cat, t_pattern) if t_pattern else True
            n_matches = self._matches_pattern(n_cat, n_pattern) if n_pattern else True
            m_matches = self._matches_pattern(m_cat, m_pattern_str) if m_pattern_str else True
            
            if t_matches and n_matches and m_matches:
                return True
        
        return False
    
    def _matches_biomarker_pattern(self, value: str, pattern: str) -> bool:
        """Match a biomarker value against a pattern."""
        if not pattern or pattern.upper() == "ANY":
            return True
        
        value_upper = value.upper() if value else ""
        pattern_upper = pattern.upper()
        
        # Handle "Positive" / "Negative" matching to "+" / "-"
        if value_upper == "POSITIVE" and pattern_upper in ["POSITIVE", "+"]:
            return True
        if value_upper == "NEGATIVE" and pattern_upper in ["NEGATIVE", "-"]:
            return True
        
        # Handle grade ranges like "G1-G2"
        if "-" in pattern_upper and value_upper:
            parts = pattern_upper.split("-")
            if len(parts) == 2:
                if value_upper == parts[0] or value_upper == parts[1]:
                    return True
                # Check if value is between (e.g., G2 in G1-G3)
                if value_upper.startswith("G") and parts[0].startswith("G") and parts[1].startswith("G"):
                    try:
                        v = int(value_upper[1:])
                        low = int(parts[0][1:])
                        high = int(parts[1][1:])
                        if low <= v <= high:
                            return True
                    except ValueError:
                        pass
        
        # Exact match
        return value_upper == pattern_upper
    
    def _build_prognostic_explanation(
        self,
        t_cat: str, n_cat: str, m_cat: str,
        grade: str, her2: str, er: str, pr: str,
        stage: str
    ) -> str:
        """Build a human-readable explanation for prognostic staging."""
        # Determine biology profile
        biology_desc = []
        if er == "Positive" or er == "POSITIVE":
            biology_desc.append("ER+")
        else:
            biology_desc.append("ER-")
        
        if pr == "Positive" or pr == "POSITIVE":
            biology_desc.append("PR+")
        else:
            biology_desc.append("PR-")
        
        if her2 == "Positive" or her2 == "POSITIVE":
            biology_desc.append("HER2+")
        else:
            biology_desc.append("HER2-")
        
        biology_str = "/".join(biology_desc)
        
        # Determine if favorable or unfavorable
        favorable_factors = []
        unfavorable_factors = []
        
        if er.upper() == "POSITIVE" or pr.upper() == "POSITIVE":
            favorable_factors.append("hormone receptor positive")
        if her2.upper() == "POSITIVE":
            favorable_factors.append("HER2 positive (targeted therapy available)")
        if grade in ["G1", "g1"]:
            favorable_factors.append("low grade (G1)")
        
        if er.upper() == "NEGATIVE" and pr.upper() == "NEGATIVE" and her2.upper() == "NEGATIVE":
            unfavorable_factors.append("triple negative")
        if grade in ["G3", "g3"]:
            unfavorable_factors.append("high grade (G3)")
        
        # Build explanation
        explanation = f"Clinical Prognostic Stage {stage} based on {t_cat}{n_cat}{m_cat} with {grade} and {biology_str}. "
        
        if favorable_factors:
            explanation += f"Favorable factors: {', '.join(favorable_factors)}. "
        if unfavorable_factors:
            explanation += f"Unfavorable factors: {', '.join(unfavorable_factors)}. "
        
        return explanation.strip()
    
    def compare_stages(self, stage1: str, stage2: str) -> int:
        """
        Compare two stages.
        
        Returns:
            -1 if stage1 < stage2
            0 if stage1 == stage2
            1 if stage1 > stage2
        """
        # Clean stage strings
        s1 = stage1.replace("Stage ", "").strip().upper()
        s2 = stage2.replace("Stage ", "").strip().upper()
        
        try:
            idx1 = self.STAGE_HIERARCHY.index(s1) if s1 in self.STAGE_HIERARCHY else 99
            idx2 = self.STAGE_HIERARCHY.index(s2) if s2 in self.STAGE_HIERARCHY else 99
            
            if idx1 < idx2:
                return -1
            elif idx1 > idx2:
                return 1
            else:
                return 0
        except ValueError:
            return 0
