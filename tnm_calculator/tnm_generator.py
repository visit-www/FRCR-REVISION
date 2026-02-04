"""
TNM Calculator & Algorithm Generator Module

Uses Claude API to generate:
1. Interactive TNM calculator HTML (decision-tree based)
2. Algorithm discussion content for case documents

Generated content is saved to:
- Database: tnm_calculator_content table
- File: tnm_calculator/calculators/{slug}_calc.html
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import anthropic

logger = logging.getLogger(__name__)

# Calculator templates directory
CALCULATORS_DIR = Path(__file__).parent / 'calculators'


def get_claude_client():
    """Get Anthropic client instance."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
    return anthropic.Anthropic(api_key=api_key)


# ==================== PROMPTS ====================

CALCULATOR_HTML_PROMPT = """You are an expert radiologist and oncologist specializing in cancer staging.

Generate a COMPLETE, SELF-CONTAINED HTML file for an interactive TNM staging calculator for {cancer_name} cancer.

The calculator should follow this exact structure and style (based on the oropharynx calculator):

1. **Header Section**:
   - Gradient header with cancer name and AJCC edition
   - Brief intro text

2. **Step-by-Step Decision Tree**:
   - Each T category question presented as expandable cards
   - Start with worst case (T4b) then work down (T4a → T3 → T2 → T1 → Tis)
   - Use clinical mnemonics where helpful (e.g., "PACE" for pharynx T4b)
   - Include imaging tips and common pitfalls

3. **N Staging Section**:
   - Include both clinical (cN) and pathological (pN) when relevant
   - Special staging rules if applicable (e.g., HPV+ vs HPV-)

4. **M Staging Section**:
   - M0/M1 selection

5. **Stage Calculator**:
   - Real-time stage calculation based on selections
   - Stage group display with explanation

6. **Interactive Features**:
   - JavaScript for expanding/collapsing sections
   - Stage calculation logic
   - Reset functionality

Use these CSS variables for consistent styling:
```css
:root {{
    --brand-primary: #e96304;
    --brand-secondary: #ffc107;
    --brand-success: #a8d5ba;
    --brand-neutral: #5E899E;
    --brand-text-primary: #2c3e50;
    --brand-bg-offwhite: #fdfdfb;
}}
```

CRITICAL: Generate the COMPLETE HTML file including all CSS and JavaScript. Do not use placeholders.

Cancer: {cancer_name}
Body Section: {body_section}
Staging System: {staging_system}
{special_notes}

Generate the complete HTML now:"""


ALGORITHM_DISCUSSION_PROMPT = """You are an expert radiologist creating educational content for FRCR radiology trainees.

Generate a comprehensive ALGORITHM DISCUSSION for staging {cancer_name} cancer on imaging.

The content should include:

1. **Quick Reference Card** with:
   - Clinical mnemonics for T staging (e.g., T4b="PACE" for Perineural/skull base, Adjacent structures, Carotid encasement, Encases vessels)
   - Key imaging findings for each T category
   - Decision algorithm flowchart

2. **Step-by-Step Staging Algorithm** (7-8 steps):
   - Written in the order a radiologist should evaluate
   - Start with ruling out M1 disease
   - Then check T4b criteria first (unresectable)
   - Work through T4a, T3, T2, T1 systematically
   - Include specific imaging criteria

3. **N Staging Section**:
   - Nodal criteria for clinical vs pathological staging
   - Size thresholds and morphological features
   - ENE (extranodal extension) recognition

4. **Common Pitfalls**:
   - 3-5 specific mistakes to avoid
   - Imaging artifacts that mimic invasion
   - Underappreciated findings

5. **Imaging Tips**:
   - Optimal sequences/protocols
   - What to look for on each sequence
   - How to differentiate tumor from normal tissue

Format the content as rich HTML with:
- Styled cards with gradients
- Bullet points and numbered lists
- Color-coded sections (use brand colors: #e96304 orange, #5E899E teal, #a8d5ba green)
- Tables for staging comparison
- Bold key terms

Cancer: {cancer_name}
Body Section: {body_section}
Staging System: {staging_system}
{special_notes}

Generate the complete HTML discussion content now:"""


# ==================== GENERATION FUNCTIONS ====================

def generate_calculator_html(
    cancer_name: str,
    body_section: str,
    staging_system: str = "AJCC 9th Edition",
    special_notes: str = ""
) -> str:
    """
    Generate interactive TNM calculator HTML using Claude.

    Args:
        cancer_name: Display name (e.g., "Oropharynx", "Lung (NSCLC)")
        body_section: Body section (e.g., "Head and Neck", "Thorax")
        staging_system: Staging system used (default: AJCC 9th Edition)
        special_notes: Additional notes for generation (e.g., HPV variants)

    Returns:
        Complete HTML string for the calculator
    """
    client = get_claude_client()

    prompt = CALCULATOR_HTML_PROMPT.format(
        cancer_name=cancer_name,
        body_section=body_section,
        staging_system=staging_system,
        special_notes=f"Special considerations: {special_notes}" if special_notes else ""
    )

    logger.info(f"[TNM Generator] Generating calculator HTML for {cancer_name}")

    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=16000,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    html_content = response.content[0].text

    # Clean up if wrapped in markdown code blocks
    if html_content.startswith("```html"):
        html_content = html_content[7:]
    if html_content.startswith("```"):
        html_content = html_content[3:]
    if html_content.endswith("```"):
        html_content = html_content[:-3]

    return html_content.strip()


def generate_algorithm_discussion(
    cancer_name: str,
    body_section: str,
    staging_system: str = "AJCC 9th Edition",
    special_notes: str = ""
) -> str:
    """
    Generate algorithm discussion HTML for case document.

    Args:
        cancer_name: Display name
        body_section: Body section
        staging_system: Staging system
        special_notes: Additional notes

    Returns:
        HTML string for discussion content
    """
    client = get_claude_client()

    prompt = ALGORITHM_DISCUSSION_PROMPT.format(
        cancer_name=cancer_name,
        body_section=body_section,
        staging_system=staging_system,
        special_notes=f"Special considerations: {special_notes}" if special_notes else ""
    )

    logger.info(f"[TNM Generator] Generating algorithm discussion for {cancer_name}")

    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=12000,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    html_content = response.content[0].text

    # Clean up if wrapped in markdown code blocks
    if html_content.startswith("```html"):
        html_content = html_content[7:]
    if html_content.startswith("```"):
        html_content = html_content[3:]
    if html_content.endswith("```"):
        html_content = html_content[:-3]

    return html_content.strip()


def save_calculator_html_file(slug: str, html_content: str) -> Path:
    """
    Save calculator HTML to file in calculators directory.

    Args:
        slug: Calculator slug (e.g., 'oropharynx', 'lung')
        html_content: Complete HTML content

    Returns:
        Path to saved file
    """
    CALCULATORS_DIR.mkdir(parents=True, exist_ok=True)

    file_path = CALCULATORS_DIR / f"{slug}_calc.html"
    file_path.write_text(html_content, encoding='utf-8')

    logger.info(f"[TNM Generator] Saved calculator HTML to {file_path}")
    return file_path


def generate_and_save_tnm_content(
    db,
    slug: str,
    cancer_name: str,
    body_section: str,
    staging_system: str = "AJCC 9th Edition",
    special_features: list = None,
    description: str = "",
    special_notes: str = "",
    user_id: int = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Generate calculator and algorithm content, save to DB and file.

    Args:
        db: SQLAlchemy database instance
        slug: Unique identifier (e.g., 'oropharynx')
        cancer_name: Display name
        body_section: Body section
        staging_system: Staging system
        special_features: List of special features
        description: Short description
        special_notes: Notes for Claude
        user_id: Creating user ID

    Returns:
        Tuple of (success, message, result_data)
    """
    from models import TNMCalculatorContent

    try:
        # Check if already exists
        existing = TNMCalculatorContent.query.filter_by(slug=slug).first()
        if existing:
            return False, f"Calculator for '{slug}' already exists", {}

        # Generate calculator HTML
        logger.info(f"[TNM Generator] Starting generation for {cancer_name}")
        calculator_html = generate_calculator_html(
            cancer_name=cancer_name,
            body_section=body_section,
            staging_system=staging_system,
            special_notes=special_notes
        )

        # Generate algorithm discussion
        algorithm_html = generate_algorithm_discussion(
            cancer_name=cancer_name,
            body_section=body_section,
            staging_system=staging_system,
            special_notes=special_notes
        )

        # Save HTML file
        file_path = save_calculator_html_file(slug, calculator_html)

        # Create database record
        content = TNMCalculatorContent(
            slug=slug,
            cancer_name=cancer_name,
            body_section=body_section,
            calculator_html=calculator_html,
            algorithm_discussion_html=algorithm_html,
            staging_system=staging_system,
            description=description,
            is_available=True,
            generation_model="claude-3-5-sonnet-20241022",
            generated_at=datetime.utcnow(),
            created_by_user_id=user_id
        )

        if special_features:
            content.set_special_features(special_features)

        db.session.add(content)
        db.session.commit()

        logger.info(f"[TNM Generator] Successfully generated and saved {cancer_name} calculator")

        return True, f"Successfully generated {cancer_name} calculator", {
            'id': content.id,
            'slug': slug,
            'file_path': str(file_path),
            'calculator_html_length': len(calculator_html),
            'algorithm_html_length': len(algorithm_html)
        }

    except Exception as e:
        logger.error(f"[TNM Generator] Error generating {cancer_name}: {e}")
        db.session.rollback()
        return False, f"Error: {str(e)}", {}


def regenerate_calculator(
    db,
    slug: str,
    regenerate_calculator: bool = True,
    regenerate_algorithm: bool = True,
    special_notes: str = ""
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Regenerate content for existing calculator.

    Args:
        db: SQLAlchemy database instance
        slug: Calculator slug
        regenerate_calculator: Whether to regenerate calculator HTML
        regenerate_algorithm: Whether to regenerate algorithm HTML
        special_notes: Additional notes for generation

    Returns:
        Tuple of (success, message, result_data)
    """
    from models import TNMCalculatorContent

    try:
        content = TNMCalculatorContent.query.filter_by(slug=slug).first()
        if not content:
            return False, f"Calculator '{slug}' not found", {}

        if regenerate_calculator:
            calculator_html = generate_calculator_html(
                cancer_name=content.cancer_name,
                body_section=content.body_section,
                staging_system=content.staging_system,
                special_notes=special_notes
            )
            content.calculator_html = calculator_html
            save_calculator_html_file(slug, calculator_html)

        if regenerate_algorithm:
            algorithm_html = generate_algorithm_discussion(
                cancer_name=content.cancer_name,
                body_section=content.body_section,
                staging_system=content.staging_system,
                special_notes=special_notes
            )
            content.algorithm_discussion_html = algorithm_html

        content.generated_at = datetime.utcnow()
        db.session.commit()

        return True, f"Successfully regenerated {content.cancer_name}", {
            'id': content.id,
            'slug': slug
        }

    except Exception as e:
        logger.error(f"[TNM Generator] Error regenerating {slug}: {e}")
        db.session.rollback()
        return False, f"Error: {str(e)}", {}


def get_available_calculators() -> list:
    """Get list of available calculator slugs from V3_CALCULATORS in routes.py"""
    from .routes import V3_CALCULATORS

    calculators = []
    for section_id, section_data in V3_CALCULATORS.items():
        for calc in section_data['calculators']:
            calculators.append({
                'slug': calc['slug'],
                'name': calc['name'],
                'body_section': section_data['name'],
                'available': calc['available'],
                'staging_system': calc.get('staging_system', 'AJCC 9th Edition'),
                'special_features': calc.get('special_features', []),
                'description': calc.get('description', '')
            })

    return calculators


def insert_algorithm_to_case_discussion(
    db,
    case_id: int,
    calculator_slug: str
) -> Tuple[bool, str]:
    """
    Insert algorithm discussion HTML into a case's discussion field.

    Args:
        db: SQLAlchemy database instance
        case_id: Case ID to update
        calculator_slug: Calculator slug to get algorithm from

    Returns:
        Tuple of (success, message)
    """
    from models import Case, TNMCalculatorContent

    try:
        case = Case.query.get(case_id)
        if not case:
            return False, "Case not found"

        content = TNMCalculatorContent.query.filter_by(slug=calculator_slug).first()
        if not content:
            return False, f"Calculator '{calculator_slug}' not found"

        if not content.algorithm_discussion_html:
            return False, "Algorithm discussion content not available"

        # Append algorithm to existing discussion
        existing = case.discussion or ""
        separator = "\n\n<hr style='border-top: 2px solid #e96304; margin: 2rem 0;'>\n\n" if existing.strip() else ""

        algorithm_header = f"""
<div style="background: linear-gradient(135deg, #5E899E 0%, #4a7285 100%); color: white; padding: 15px 20px; border-radius: 8px 8px 0 0; margin-bottom: 0;">
    <h3 style="margin: 0; font-size: 1.25rem;">
        <i class="fas fa-sitemap" style="margin-right: 10px;"></i>{content.cancer_name} Staging Algorithm
    </h3>
    <small style="opacity: 0.9;">{content.staging_system}</small>
</div>
"""

        case.discussion = existing + separator + algorithm_header + content.algorithm_discussion_html
        case.calculator_slug = calculator_slug
        db.session.commit()

        return True, f"Algorithm inserted for {content.cancer_name}"

    except Exception as e:
        logger.error(f"[TNM Generator] Error inserting algorithm: {e}")
        db.session.rollback()
        return False, f"Error: {str(e)}"
