"""
TNM Calculator Engine

The main calculation engine that coordinates all components:
- Input validation
- Rule loading
- Stage resolution
- Explanation generation

This is the primary interface for using the TNM Calculator.
"""

import logging
from typing import Optional, List, Dict, Any

from .models import (
    TNMInput, TNMResult, ValidationError, 
    CancerDefinition, StagingType
)
from .loader import RuleLoader, get_loader
from .resolver import StageResolver
from .explainer import Explainer

logger = logging.getLogger(__name__)


class TNMCalculator:
    """
    Clinical-grade TNM Staging Calculator.
    
    A deterministic, rule-based calculator that:
    - Accepts structured inputs (T/N/M descriptors)
    - Applies cancer-specific TNM rules from JSON
    - Outputs TNM classification, stage group, and explanations
    
    Example usage:
        calculator = TNMCalculator()
        
        input = TNMInput(
            cancer_type="larynx",
            t_category="T2",
            n_category="N1",
            m_category="M0"
        )
        
        result = calculator.calculate(input)
        print(result.stage_group)  # "Stage III"
        print(result.stage_explanation)
    """
    
    # Standard clinical disclaimer
    DISCLAIMER = (
        "Decision-support only. Final staging responsibility remains with "
        "the treating clinician. This calculator is for educational purposes "
        "and should not replace clinical judgment."
    )
    
    def __init__(self, loader: Optional[RuleLoader] = None):
        """
        Initialize the TNM Calculator.
        
        Args:
            loader: Optional custom rule loader. Uses default if not provided.
        """
        self.loader = loader or get_loader()
        logger.info("[TNM Calculator] Engine initialized")
    
    def calculate(self, input: TNMInput) -> TNMResult:
        """
        Calculate TNM stage from structured input.
        
        Flow:
        1. Validate inputs
        2. Load cancer-specific rules
        3. Apply M overrides (M1 → Stage IV)
        4. Resolve T category
        5. Resolve N category
        6. Match stage group
        7. Generate explanation
        
        Args:
            input: TNMInput with cancer type and T/N/M categories
            
        Returns:
            TNMResult with stage group and explanations
        """
        logger.info(f"[TNM Calculator] Calculating stage for {input.cancer_type}: "
                   f"{input.t_category}{input.n_category}{input.m_category}")
        
        # Step 1: Load cancer definition
        definition = self.loader.load_cancer_definition(input.cancer_type)
        if not definition:
            return TNMResult.error(
                f"Cancer type '{input.cancer_type}' not found in staging database",
                cancer_type=input.cancer_type,
                version=input.version
            )
        
        # Step 2: Validate inputs
        validation_errors = self._validate_input(input, definition)
        if any(e.severity == "error" for e in validation_errors):
            return self._create_error_result(input, definition, validation_errors)
        
        # Step 3: Create resolver and explainer
        resolver = StageResolver(definition)
        explainer = Explainer(definition)
        
        # Step 4: Resolve stage
        stage_group, is_metastatic, stage_color = resolver.resolve(
            input.t_category,
            input.n_category,
            input.m_category
        )
        
        # Step 5: Generate explanations
        t_explanation = explainer.explain_t(input.t_category, input.subsite)
        n_explanation = explainer.explain_n(input.n_category, input.staging_type)
        m_explanation = explainer.explain_m(input.m_category)
        stage_explanation = explainer.explain_stage(
            stage_group,
            input.t_category,
            input.n_category,
            input.m_category,
            input.subsite,
            input.staging_type
        )
        
        # Step 6: Build result
        tnm_classification = f"{input.t_category}{input.n_category}{input.m_category}"
        
        result = TNMResult(
            success=True,
            tnm_classification=tnm_classification,
            stage_group=stage_group,
            t_category=input.t_category,
            n_category=input.n_category,
            m_category=input.m_category,
            t_explanation=t_explanation,
            n_explanation=n_explanation,
            m_explanation=m_explanation,
            stage_explanation=stage_explanation,
            disclaimer=self.DISCLAIMER,
            cancer_type=definition.name,
            version=definition.version,
            validation_errors=validation_errors,
            staging_type=input.staging_type,
            subsite=input.subsite,
            stage_color=stage_color,
            is_metastatic=is_metastatic,
            available_t_categories=definition.get_t_categories(input.subsite),
            available_n_categories=definition.get_n_categories(input.staging_type),
            available_m_categories=definition.get_m_categories()
        )
        
        logger.info(f"[TNM Calculator] Result: {tnm_classification} → {stage_group}")
        
        return result
    
    def _validate_input(
        self,
        input: TNMInput,
        definition: CancerDefinition
    ) -> List[ValidationError]:
        """
        Validate the input against the cancer definition.
        
        Checks:
        - T category is valid for this cancer type
        - N category is valid
        - M category is valid
        - Subsite is valid (if applicable)
        """
        errors: List[ValidationError] = []
        
        # Get valid categories
        valid_t = definition.get_t_categories(input.subsite)
        valid_n = definition.get_n_categories(input.staging_type)
        valid_m = definition.get_m_categories()
        
        # Validate T category
        if not self._is_valid_category(input.t_category, valid_t):
            errors.append(ValidationError(
                field="t_category",
                message=f"'{input.t_category}' is not a valid T category for {definition.name}. "
                       f"Valid options: {', '.join(valid_t[:10])}{'...' if len(valid_t) > 10 else ''}",
                severity="warning"  # Warning, not error - we'll still try to stage
            ))
        
        # Validate N category
        if not self._is_valid_category(input.n_category, valid_n):
            errors.append(ValidationError(
                field="n_category",
                message=f"'{input.n_category}' is not a valid N category for {definition.name}. "
                       f"Valid options: {', '.join(valid_n[:10])}{'...' if len(valid_n) > 10 else ''}",
                severity="warning"
            ))
        
        # Validate M category
        if not self._is_valid_category(input.m_category, valid_m):
            errors.append(ValidationError(
                field="m_category",
                message=f"'{input.m_category}' is not a valid M category. "
                       f"Valid options: {', '.join(valid_m)}",
                severity="warning"
            ))
        
        # Validate subsite if applicable
        if definition.subsites and input.subsite:
            if input.subsite not in definition.subsites:
                errors.append(ValidationError(
                    field="subsite",
                    message=f"'{input.subsite}' is not a valid subsite for {definition.name}. "
                           f"Valid options: {', '.join(definition.subsites)}",
                    severity="warning"
                ))
        
        return errors
    
    def _is_valid_category(self, category: str, valid_list: List[str]) -> bool:
        """Check if a category is in the valid list (case-insensitive)."""
        if not category or not valid_list:
            return True  # Allow empty validation
        
        cat_upper = category.upper()
        valid_upper = [v.upper() for v in valid_list]
        
        # Exact match
        if cat_upper in valid_upper:
            return True
        
        # Subcategory match (T1a is valid if T1 is in list)
        for valid in valid_upper:
            if cat_upper.startswith(valid):
                return True
        
        return False
    
    def _create_error_result(
        self,
        input: TNMInput,
        definition: CancerDefinition,
        errors: List[ValidationError]
    ) -> TNMResult:
        """Create an error result with validation errors."""
        return TNMResult(
            success=False,
            tnm_classification="",
            stage_group="",
            t_category=input.t_category,
            n_category=input.n_category,
            m_category=input.m_category,
            t_explanation="",
            n_explanation="",
            m_explanation="",
            stage_explanation="",
            disclaimer=self.DISCLAIMER,
            cancer_type=definition.name,
            version=definition.version,
            validation_errors=errors,
            staging_type=input.staging_type,
            subsite=input.subsite,
            available_t_categories=definition.get_t_categories(input.subsite),
            available_n_categories=definition.get_n_categories(input.staging_type),
            available_m_categories=definition.get_m_categories()
        )
    
    def get_cancer_info(self, cancer_type: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a cancer type for UI rendering.
        
        Returns:
            Dict with cancer name, subsites, available categories, etc.
        """
        definition = self.loader.load_cancer_definition(cancer_type)
        if not definition:
            return None
        
        return {
            "name": definition.name,
            "slug": definition.slug,
            "version": definition.version,
            "subsites": definition.subsites,
            "has_subsites": len(definition.subsites) > 0,
            "t_categories": {
                subsite: definition.get_t_categories(subsite)
                for subsite in (definition.subsites or ["default"])
            },
            "n_categories": {
                "clinical": definition.get_n_categories(StagingType.CLINICAL),
                "pathological": definition.get_n_categories(StagingType.PATHOLOGICAL)
            },
            "m_categories": definition.get_m_categories(),
            "stage_groups": definition.stage_groups,
            "notes": definition.notes
        }
    
    def get_available_cancers(self) -> List[Dict[str, str]]:
        """
        Get list of all available cancer types.
        
        Returns:
            List of dicts with 'name', 'slug', and 'body_section' keys
        """
        return self.loader.get_available_cancers()


# Convenience function for quick calculations
def calculate_stage(
    cancer_type: str,
    t_category: str,
    n_category: str,
    m_category: str,
    staging_type: str = "clinical",
    subsite: Optional[str] = None,
    version: str = "8"
) -> TNMResult:
    """
    Quick function to calculate TNM stage.
    
    Example:
        result = calculate_stage(
            cancer_type="larynx",
            t_category="T2",
            n_category="N1",
            m_category="M0"
        )
        print(result.stage_group)  # "Stage III"
    """
    calculator = TNMCalculator()
    
    input = TNMInput(
        cancer_type=cancer_type,
        t_category=t_category,
        n_category=n_category,
        m_category=m_category,
        staging_type=StagingType(staging_type),
        subsite=subsite,
        version=version
    )
    
    return calculator.calculate(input)
