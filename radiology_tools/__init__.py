"""
Radiology Tools Module

Interactive calculators for radiology tools (incidental findings, clinical
decision aids) based on published guidelines (Fleischner, ACR, Bosniak,
TI-RADS, etc.).

Deterministic decision trees — no AI needed at runtime.
Same architecture as TNM calculators.

NOTE: The URL prefix remains /incidental-findings for backward compatibility.
The Flask blueprint is registered as 'radiology_tools'. Data keys like
'incidental_findings_step' in algorithm trees are unchanged to avoid
breaking existing cached data.
"""

from .routes import if_bp

__all__ = ['if_bp']
