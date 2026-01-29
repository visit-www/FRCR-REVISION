"""
TNM Calculator Module - Standalone Clinical-Grade TNM Staging Calculator

A deterministic, rule-based TNM staging calculator that:
- Is informative, interactive, and easy to use
- Is clinically safe and explainable
- Does NOT rely on AI or probabilistic logic
- Can be embedded into other apps as a reusable module

This is decision support, not autonomous decision-making.
"""

from .engine import TNMCalculator
from .models import TNMInput, TNMResult, StagingType

__version__ = "1.0.0"
__all__ = ["TNMCalculator", "TNMInput", "TNMResult", "StagingType"]
