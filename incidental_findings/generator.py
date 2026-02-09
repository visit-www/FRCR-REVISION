"""
Incidental Finding Calculator Generator

Generates interactive HTML calculators for incidental findings management
based on published guidelines (Fleischner, ACR, Bosniak, TI-RADS, etc.).

Mirrors tnm_calculator/tnm_generator.py patterns:
- Claude API for HTML generation
- Self-contained HTML with inline CSS/JS
- Quality validation
- Database storage
"""

import json
import os
import re
import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


# ==================== PROMPT TEMPLATE ====================

IF_CALCULATOR_PROMPT = """You are an expert radiology consultant creating an interactive incidental finding calculator.

FINDING: {finding_name}
GUIDELINE SOURCE: {guideline_source}
CATEGORY: {category}
BODY SECTION: {body_section}

{additional_context}

Create a COMPLETE, self-contained HTML page (with inline CSS and JavaScript) that implements
an interactive decision tree for managing this incidental finding based on published guidelines.

REQUIREMENTS:

1. CLINICAL ACCURACY
   - Base all recommendations STRICTLY on the published guideline cited
   - Include specific size thresholds, categories, and follow-up intervals
   - Include risk stratification where applicable
   - Include when to refer to specialist / when no follow-up needed

2. INTERACTIVE FORM
   - Checkboxes and radio buttons for clinical features
   - Number inputs for measurements (size in mm/cm)
   - Dropdown selects for categorical inputs (e.g., risk status, modality)
   - Auto-calculate recommendation when inputs change
   - Show/hide conditional inputs based on selections (branching logic)

3. RESULT DISPLAY
   - Clear category/grade/recommendation output
   - Follow-up recommendation with specific timing
   - Management implications
   - REPORT LANGUAGE: Generate copy-paste radiology report text for the finding
   - Include "Copy Report Language" button

4. REFERENCE SECTION
   - Full guideline citation
   - Key algorithm summary table
   - Common pitfalls (4+)
   - Important caveats and exceptions

5. STYLING
   - Use CSS variables for consistent theming:
     --brand-primary: #e96304;
     --brand-neutral: #5E899E;
     --brand-bg-offwhite: #fdfdfb;
     --brand-border: #c5cad1;
     --brand-text-primary: #2c3e50;
   - Single-column vertical layout (for iframe embedding)
   - Responsive design
   - Professional medical appearance
   - Clear visual hierarchy

6. JAVASCRIPT
   - All logic inline (no external dependencies)
   - Auto-calculate on input change
   - Report language generation based on inputs
   - Copy-to-clipboard functionality
   - Print-friendly output

7. CLINICAL DISCLAIMER
   - Include at top: "Clinical Decision Support Tool — verify against current guidelines before clinical use"
   - Include guideline citation and version

OUTPUT:
Return ONLY the complete HTML document. No markdown code fences. No explanatory text.
Start with <!DOCTYPE html> and end with </html>.

The calculator should be comprehensive enough that a radiologist can use it during reporting
to determine the correct management recommendation and generate appropriate report language.
Minimum 1500 lines of well-structured HTML/CSS/JS.
"""


# ==================== GENERATOR ====================

def generate_if_calculator_html(finding_name, guideline_source='', category='',
                                 body_section='', additional_context='', user_id=None,
                                 model=None, overwrite=False):
    """
    Generate an incidental finding calculator HTML page using Claude.

    Args:
        finding_name: Name of the incidental finding (e.g., "Pulmonary Nodule")
        guideline_source: Published guideline (e.g., "Fleischner Society 2017")
        category: Finding category (e.g., "pulmonary")
        body_section: Body section (e.g., "Thorax")
        additional_context: Extra context for generation
        user_id: ID of requesting user
        model: Claude model to use
        overwrite: Whether to overwrite existing calculator

    Returns:
        dict with success, message, and metadata
    """
    from models import db, IncidentalFindingCalculator

    slug = re.sub(r'[^a-z0-9]+', '-', finding_name.lower()).strip('-')

    # Check for existing
    existing = IncidentalFindingCalculator.query.filter_by(slug=slug).first()
    if existing and not overwrite:
        return {
            'success': False,
            'message': f'Calculator for "{finding_name}" already exists. Use overwrite=true to replace.',
            'slug': slug,
        }

    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        return {'success': False, 'message': 'CLAUDE_API_KEY not configured.'}

    effective_model = model or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    # Build prompt
    prompt = IF_CALCULATOR_PROMPT.format(
        finding_name=finding_name,
        guideline_source=guideline_source or 'Use the most widely accepted published guideline',
        category=category or 'incidental',
        body_section=body_section or 'Not specified',
        additional_context=additional_context or '',
    )

    payload = {
        "model": effective_model,
        "max_tokens": 20000,
        "temperature": 0.3,
        "system": "You are an experienced radiology consultant creating clinical decision support tools. Generate complete, self-contained HTML pages with accurate clinical content based on published guidelines. All CSS and JavaScript must be inline.",
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json=payload,
            timeout=240,
        )
    except requests.exceptions.Timeout:
        return {'success': False, 'message': 'Generation timed out. Please try again.'}
    except requests.exceptions.RequestException as exc:
        return {'success': False, 'message': f'API connection error: {exc}'}

    if response.status_code >= 300:
        return {'success': False, 'message': f'API error (HTTP {response.status_code}): {response.text[:500]}'}

    result = response.json()
    content = result.get("content", [])
    if not content:
        return {'success': False, 'message': 'Empty response from API.'}

    calculator_html = content[0].get("text", "")

    # Strip markdown code fences if present
    if calculator_html.strip().startswith("```"):
        lines = calculator_html.strip().split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        calculator_html = "\n".join(lines)

    # Validate minimum quality
    is_valid, warnings = _validate_quality(calculator_html)

    # Extract algorithm summary for the algorithm_html field
    algorithm_html = _extract_algorithm_summary(calculator_html, finding_name)

    # Save to database
    if existing and overwrite:
        existing.finding_name = finding_name
        existing.body_section = body_section or None
        existing.category = category or None
        existing.calculator_html = calculator_html
        existing.algorithm_html = algorithm_html
        existing.guideline_source = guideline_source or None
        existing.generation_prompt = prompt[:2000]
        existing.generation_model = effective_model
        existing.generated_at = datetime.utcnow()
        existing.is_available = False  # Needs admin review
        existing.updated_at = datetime.utcnow()
        db.session.commit()
        calc_id = existing.id
    else:
        calculator = IncidentalFindingCalculator(
            slug=slug,
            finding_name=finding_name,
            body_section=body_section or None,
            category=category or None,
            keywords=f"{finding_name}, {category}, {guideline_source}, incidental",
            calculator_html=calculator_html,
            algorithm_html=algorithm_html,
            guideline_source=guideline_source or None,
            is_available=False,  # Needs admin review before publishing
            generation_prompt=prompt[:2000],
            generation_model=effective_model,
            generated_at=datetime.utcnow(),
            created_by_user_id=user_id,
        )
        db.session.add(calculator)
        db.session.commit()
        calc_id = calculator.id

    return {
        'success': True,
        'message': f'Calculator for "{finding_name}" generated. Awaiting admin review.',
        'slug': slug,
        'id': calc_id,
        'html_length': len(calculator_html),
        'validation_warnings': warnings,
        'is_valid': is_valid,
    }


def _validate_quality(html):
    """Validate generated calculator HTML meets minimum quality."""
    warnings = []

    if len(html) < 5000:
        warnings.append(f'HTML too short ({len(html)} chars, expected 5000+)')

    checks = [
        (r'type=["\']checkbox["\']|type=["\']radio["\']', 'Interactive inputs (checkbox/radio)'),
        (r'type=["\']number["\']', 'Number inputs for measurements'),
        (r'copy|clipboard', 'Copy functionality'),
        (r'recommendation|follow-up|follow up', 'Follow-up recommendations'),
        (r'report|impression', 'Report language section'),
    ]

    for pattern, description in checks:
        if not re.search(pattern, html, re.IGNORECASE):
            warnings.append(f'Missing: {description}')

    is_valid = len(warnings) <= 2
    return is_valid, warnings


def _extract_algorithm_summary(html, finding_name):
    """Extract a portable algorithm summary from the calculator HTML."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # If BeautifulSoup not available, return a simple wrapper
        return f'<div class="if-algorithm"><h4>{finding_name} — Incidental Finding Management</h4><p>See interactive calculator for full decision tree.</p></div>'

    soup = BeautifulSoup(html, 'html.parser')

    PRIMARY = '#5E899E'
    BG_OFFWHITE = '#f8f9fa'
    BORDER = '#e9ecef'

    sections = []

    # Look for reference/summary sections
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        text = heading.get_text(strip=True).lower()
        if any(kw in text for kw in ['reference', 'summary', 'algorithm', 'guideline', 'classification', 'criteria']):
            # Get the content following this heading
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                content_parts.append(str(sibling))
            if content_parts:
                sections.append({
                    'title': heading.get_text(strip=True),
                    'content': '\n'.join(content_parts[:5]),  # Limit to 5 elements
                })

    if not sections:
        return f'<div class="if-algorithm"><h4>{finding_name}</h4><p>See interactive calculator for full decision tree.</p></div>'

    # Build portable HTML
    parts = [
        f'<div style="margin: 1rem 0; padding: 1rem; background: {BG_OFFWHITE}; border-radius: 10px; border: 1px solid {BORDER};">',
        f'<h4 style="color: {PRIMARY}; margin-bottom: 1rem;">{finding_name} — Quick Reference</h4>',
    ]

    for section in sections[:4]:
        parts.append(f'<h6 style="color: #2c3e50; border-bottom: 2px solid {PRIMARY}; padding-bottom: 0.3rem; margin-top: 1rem;">{section["title"]}</h6>')
        parts.append(section['content'])

    parts.append('</div>')
    return '\n'.join(parts)
