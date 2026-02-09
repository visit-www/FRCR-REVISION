"""
Reporting Template Generator

Generates interactive non-oncologic reporting templates (Layer B)
using Claude, mirroring tnm_calculator/tnm_generator.py patterns.

Covers: trauma scoring (AAST), grading systems (LI-RADS, PI-RADS),
emergency templates (CT head, CTPA, polytrauma), etc.
"""

import json
import os
import re
import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


# ==================== PROMPT TEMPLATE ====================

REPORTING_TEMPLATE_PROMPT = """You are an expert radiology consultant creating an interactive reporting decision tree.

TEMPLATE TITLE: {title}
CATEGORY: {category}
BODY SECTION: {body_section}
SOURCE GUIDELINE: {source_citation}

{additional_context}

Create a COMPLETE, self-contained HTML page (with inline CSS and JavaScript) that implements
an interactive reporting decision tree for this clinical scenario.

REQUIREMENTS:

1. CLINICAL ACCURACY
   - Base all content on published guidelines and established radiology practice
   - Include specific grading criteria, classification systems, or scoring scales
   - Include management implications for each grade/score/finding
   - Follow the "WORST FIRST" reporting principle (most critical findings first)

2. INTERACTIVE DECISION TREE
   - Checkboxes for present/absent findings
   - Radio buttons for mutually exclusive categories
   - Number inputs for measurements (with appropriate units)
   - Dropdown selects for categorical choices
   - Conditional show/hide for branching logic
   - Auto-calculate grade/score/category as user inputs findings

3. STRUCTURED REPORT GENERATION
   The key differentiator: the template should generate a structured radiology report.

   Include these sections in the generated report:
   - INDICATION: (pre-filled based on template type)
   - TECHNIQUE: (standard protocol for this study type)
   - FINDINGS: (compiled from checked/entered findings, organised by system)
   - IMPRESSION: (numbered key findings, most critical first)

   Include a "Generate Report" button that compiles all inputs into the report.
   Include a "Copy Report" button for clipboard.

4. REFERENCE SECTION
   - Classification/grading table for quick reference
   - Key measurement thresholds
   - Common pitfalls (4+)
   - When to escalate / call for help
   - Relevant cross-references

5. STYLING
   - Use CSS variables for consistent theming:
     --brand-primary: #e96304;
     --brand-neutral: #5E899E;
     --brand-bg-offwhite: #fdfdfb;
     --brand-border: #c5cad1;
     --brand-text-primary: #2c3e50;
   - Single-column vertical layout
   - Responsive design
   - Professional medical appearance
   - Colour-coded severity (green → yellow → red)

6. JAVASCRIPT
   - All logic inline (no external dependencies)
   - Auto-calculate on input change
   - Report generation from inputs
   - Copy-to-clipboard functionality
   - Print-friendly output

7. DISCLAIMER
   - Include at top: "Clinical Decision Support Tool — verify against current guidelines and institutional protocols before clinical use"
   - Include source citation

OUTPUT:
Return ONLY the complete HTML document. No markdown code fences. No explanatory text.
Start with <!DOCTYPE html> and end with </html>.

The template should be comprehensive enough that a radiologist can use it during reporting
to systematically document findings and generate a structured report.
Minimum 1500 lines of well-structured HTML/CSS/JS.
"""


# ==================== GENERATOR ====================

def generate_reporting_template_html(title, category, body_section='', source_citation='',
                                      additional_context='', user_id=None, model=None,
                                      overwrite=False):
    """
    Generate a reporting template HTML page using Claude.

    Args:
        title: Template title (e.g., "AAST Splenic Injury Scale")
        category: Category (e.g., "trauma", "grading", "emergency")
        body_section: Body section (e.g., "Abdomen")
        source_citation: Source guideline citation
        additional_context: Extra context for generation
        user_id: ID of requesting user
        model: Claude model to use
        overwrite: Whether to overwrite existing

    Returns:
        dict with success, message, and metadata
    """
    from models import db, ReportingTemplate

    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')

    existing = ReportingTemplate.query.filter_by(slug=slug).first()
    if existing and not overwrite:
        return {
            'success': False,
            'message': f'Template "{title}" already exists. Use overwrite=true to replace.',
            'slug': slug,
        }

    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        return {'success': False, 'message': 'CLAUDE_API_KEY not configured.'}

    effective_model = model or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    prompt = REPORTING_TEMPLATE_PROMPT.format(
        title=title,
        category=category or 'reporting',
        body_section=body_section or 'Not specified',
        source_citation=source_citation or 'Use established radiology guidelines',
        additional_context=additional_context or '',
    )

    payload = {
        "model": effective_model,
        "max_tokens": 20000,
        "temperature": 0.3,
        "system": "You are an experienced radiology consultant creating clinical reporting tools. Generate complete, self-contained HTML pages with accurate clinical content. All CSS and JavaScript must be inline. Focus on practical, reporting-oriented decision trees that generate structured radiology reports.",
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

    template_html = content[0].get("text", "")

    # Strip markdown code fences
    if template_html.strip().startswith("```"):
        lines = template_html.strip().split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        template_html = "\n".join(lines)

    # Validate
    is_valid, warnings = _validate_quality(template_html)

    # Extract algorithm summary
    algorithm_html = _extract_algorithm(template_html, title)

    # Save to database
    if existing and overwrite:
        existing.title = title
        existing.category = category
        existing.body_section = body_section or None
        existing.template_html = template_html
        existing.algorithm_html = algorithm_html
        existing.source_citation = source_citation or None
        existing.generation_prompt = prompt[:2000]
        existing.generation_model = effective_model
        existing.generated_at = datetime.utcnow()
        existing.is_available = False  # Needs admin review
        existing.updated_at = datetime.utcnow()
        db.session.commit()
        template_id = existing.id
    else:
        template = ReportingTemplate(
            slug=slug,
            title=title,
            category=category,
            body_section=body_section or None,
            keywords=f"{title}, {category}, {body_section}, reporting",
            template_html=template_html,
            algorithm_html=algorithm_html,
            source_citation=source_citation or None,
            is_available=False,  # Needs admin review
            generation_prompt=prompt[:2000],
            generation_model=effective_model,
            generated_at=datetime.utcnow(),
            created_by_user_id=user_id,
        )
        db.session.add(template)
        db.session.commit()
        template_id = template.id

    return {
        'success': True,
        'message': f'Template "{title}" generated. Awaiting admin review.',
        'slug': slug,
        'id': template_id,
        'html_length': len(template_html),
        'validation_warnings': warnings,
        'is_valid': is_valid,
    }


def _validate_quality(html):
    """Validate generated template HTML meets minimum quality."""
    warnings = []

    if len(html) < 5000:
        warnings.append(f'HTML too short ({len(html)} chars, expected 5000+)')

    checks = [
        (r'type=["\']checkbox["\']|type=["\']radio["\']', 'Interactive inputs'),
        (r'copy|clipboard', 'Copy functionality'),
        (r'finding|impression|report', 'Report generation'),
        (r'grade|score|category|classification', 'Grading/classification'),
    ]

    for pattern, description in checks:
        if not re.search(pattern, html, re.IGNORECASE):
            warnings.append(f'Missing: {description}')

    is_valid = len(warnings) <= 2
    return is_valid, warnings


def _extract_algorithm(html, title):
    """Extract a portable algorithm summary from the template HTML."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return f'<div class="reporting-algorithm"><h4>{title}</h4><p>See interactive template for full decision tree.</p></div>'

    soup = BeautifulSoup(html, 'html.parser')

    PRIMARY = '#5E899E'
    BG_OFFWHITE = '#f8f9fa'
    BORDER = '#e9ecef'

    sections = []

    for heading in soup.find_all(['h2', 'h3', 'h4']):
        text = heading.get_text(strip=True).lower()
        if any(kw in text for kw in ['reference', 'classification', 'grading', 'criteria', 'scale', 'scoring']):
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                content_parts.append(str(sibling))
            if content_parts:
                sections.append({
                    'title': heading.get_text(strip=True),
                    'content': '\n'.join(content_parts[:5]),
                })

    if not sections:
        return f'<div class="reporting-algorithm"><h4>{title}</h4><p>See interactive template for full decision tree.</p></div>'

    parts = [
        f'<div style="margin: 1rem 0; padding: 1rem; background: {BG_OFFWHITE}; border-radius: 10px; border: 1px solid {BORDER};">',
        f'<h4 style="color: {PRIMARY}; margin-bottom: 1rem;">{title} — Quick Reference</h4>',
    ]

    for section in sections[:4]:
        parts.append(f'<h6 style="color: #2c3e50; border-bottom: 2px solid {PRIMARY}; padding-bottom: 0.3rem; margin-top: 1rem;">{section["title"]}</h6>')
        parts.append(section['content'])

    parts.append('</div>')
    return '\n'.join(parts)
