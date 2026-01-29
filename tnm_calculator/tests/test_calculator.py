"""
TNM Calculator Tests

Tests for the TNM Calculator module using known staging cases.
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tnm_calculator import TNMCalculator, TNMInput, TNMResult, StagingType


class TestTNMCalculator:
    """Test suite for the TNM Calculator."""
    
    @pytest.fixture
    def calculator(self):
        """Create a calculator instance for tests."""
        return TNMCalculator()
    
    # ==================== LARYNX STAGING TESTS ====================
    
    def test_larynx_stage_0(self, calculator):
        """Test Larynx Tis N0 M0 = Stage 0"""
        input = TNMInput(
            cancer_type="larynx",
            t_category="Tis",
            n_category="N0",
            m_category="M0"
        )
        result = calculator.calculate(input)
        
        assert result.success is True
        assert result.stage_group == "Stage 0"
        assert result.is_metastatic is False
    
    def test_larynx_stage_i(self, calculator):
        """Test Larynx T1 N0 M0 = Stage I"""
        input = TNMInput(
            cancer_type="larynx",
            t_category="T1",
            n_category="N0",
            m_category="M0"
        )
        result = calculator.calculate(input)
        
        assert result.success is True
        assert result.stage_group == "Stage I"
        assert result.is_metastatic is False
    
    def test_larynx_stage_ii(self, calculator):
        """Test Larynx T2 N0 M0 = Stage II"""
        input = TNMInput(
            cancer_type="larynx",
            t_category="T2",
            n_category="N0",
            m_category="M0"
        )
        result = calculator.calculate(input)
        
        assert result.success is True
        assert result.stage_group == "Stage II"
        assert result.is_metastatic is False
    
    def test_larynx_stage_iii_t3n0(self, calculator):
        """Test Larynx T3 N0 M0 = Stage III"""
        input = TNMInput(
            cancer_type="larynx",
            t_category="T3",
            n_category="N0",
            m_category="M0"
        )
        result = calculator.calculate(input)
        
        assert result.success is True
        assert result.stage_group == "Stage III"
        assert result.is_metastatic is False
    
    def test_larynx_stage_iii_t2n1(self, calculator):
        """Test Larynx T2 N1 M0 = Stage III"""
        input = TNMInput(
            cancer_type="larynx",
            t_category="T2",
            n_category="N1",
            m_category="M0"
        )
        result = calculator.calculate(input)
        
        assert result.success is True
        assert result.stage_group == "Stage III"
        assert result.is_metastatic is False
    
    def test_larynx_stage_iva_t4a(self, calculator):
        """Test Larynx T4a N0 M0 = Stage IVA"""
        input = TNMInput(
            cancer_type="larynx",
            t_category="T4a",
            n_category="N0",
            m_category="M0"
        )
        result = calculator.calculate(input)
        
        assert result.success is True
        assert result.stage_group == "Stage IVA"
        assert result.is_metastatic is False
    
    def test_larynx_stage_ivb_n3(self, calculator):
        """Test Larynx Any T N3 M0 = Stage IVB"""
        input = TNMInput(
            cancer_type="larynx",
            t_category="T2",
            n_category="N3",
            m_category="M0"
        )
        result = calculator.calculate(input)
        
        assert result.success is True
        assert result.stage_group == "Stage IVB"
        assert result.is_metastatic is False
    
    def test_larynx_stage_ivc_m1(self, calculator):
        """Test Larynx Any T Any N M1 = Stage IVC (metastatic)"""
        input = TNMInput(
            cancer_type="larynx",
            t_category="T1",
            n_category="N0",
            m_category="M1"
        )
        result = calculator.calculate(input)
        
        assert result.success is True
        assert result.stage_group == "Stage IVC"
        assert result.is_metastatic is True
        assert result.stage_color == "#dc3545"  # Red for metastatic
    
    # ==================== M1 OVERRIDE TESTS ====================
    
    def test_m1_override_always_stage_iv(self, calculator):
        """Test that M1 always results in Stage IV regardless of T and N"""
        test_cases = [
            ("T1", "N0"),
            ("T2", "N1"),
            ("T3", "N2"),
            ("T4a", "N3"),
        ]
        
        for t_cat, n_cat in test_cases:
            input = TNMInput(
                cancer_type="larynx",
                t_category=t_cat,
                n_category=n_cat,
                m_category="M1"
            )
            result = calculator.calculate(input)
            
            assert result.success is True
            assert "IV" in result.stage_group, f"Expected Stage IV for {t_cat}{n_cat}M1"
            assert result.is_metastatic is True
    
    # ==================== EXPLANATION TESTS ====================
    
    def test_result_has_explanations(self, calculator):
        """Test that result includes all required explanations"""
        input = TNMInput(
            cancer_type="larynx",
            t_category="T2",
            n_category="N1",
            m_category="M0"
        )
        result = calculator.calculate(input)
        
        assert result.success is True
        assert len(result.t_explanation) > 0
        assert len(result.n_explanation) > 0
        assert len(result.m_explanation) > 0
        assert len(result.stage_explanation) > 0
        assert len(result.disclaimer) > 0
    
    def test_disclaimer_present(self, calculator):
        """Test that clinical disclaimer is always present"""
        input = TNMInput(
            cancer_type="larynx",
            t_category="T1",
            n_category="N0",
            m_category="M0"
        )
        result = calculator.calculate(input)
        
        assert "clinical" in result.disclaimer.lower()
        assert "decision" in result.disclaimer.lower()
    
    # ==================== VALIDATION TESTS ====================
    
    def test_invalid_cancer_type(self, calculator):
        """Test error handling for invalid cancer type"""
        input = TNMInput(
            cancer_type="invalid_cancer_type",
            t_category="T1",
            n_category="N0",
            m_category="M0"
        )
        result = calculator.calculate(input)
        
        assert result.success is False
        assert len(result.validation_errors) > 0
    
    # ==================== SERIALIZATION TESTS ====================
    
    def test_result_to_dict(self, calculator):
        """Test that result can be serialized to dict"""
        input = TNMInput(
            cancer_type="larynx",
            t_category="T2",
            n_category="N1",
            m_category="M0"
        )
        result = calculator.calculate(input)
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert "success" in result_dict
        assert "stage_group" in result_dict
        assert "tnm_classification" in result_dict
        assert "t_explanation" in result_dict
        assert "disclaimer" in result_dict
    
    def test_input_from_dict(self):
        """Test creating input from dict"""
        data = {
            "cancer_type": "larynx",
            "t_category": "T2",
            "n_category": "N1",
            "m_category": "M0",
            "staging_type": "clinical"
        }
        
        input = TNMInput.from_dict(data)
        
        assert input.cancer_type == "larynx"
        assert input.t_category == "T2"
        assert input.staging_type == StagingType.CLINICAL


# ==================== STANDALONE TEST RUNNER ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
