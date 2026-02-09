"""
Incidental Findings Module

Interactive calculators for incidental findings management based on
published guidelines (Fleischner, ACR, Bosniak, TI-RADS, etc.).

Deterministic decision trees — no AI needed at runtime.
Same architecture as TNM calculators.
"""

from .routes import if_bp

__all__ = ['if_bp']
