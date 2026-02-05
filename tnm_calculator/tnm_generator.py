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

# Quality validation requirements
QUALITY_REQUIREMENTS = [
    ('calculator-form|form-section', 'Calculator form section'),
    ('reference-section', 'Reference section'),
    (r'type=["\']checkbox["\']', 'Checkbox inputs for T4 features'),
    (r'type=["\']number["\']', 'Number inputs for measurements'),
    ('mnemonic', 'Mnemonics'),
    ('tip-card|tip-box|tips-grid', 'Imaging tips'),
    ('pitfall', 'Common pitfalls'),
    ('systematic|step-number|step-item', 'Systematic approach'),
    ('resultReasoning|reasoning|Reasoning', 'Reasoning output'),
    ('clinical[- ]?implication|Clinical Implication', 'Clinical implications'),
]


def validate_calculator_quality(html_content: str) -> tuple:
    """
    Validate that generated calculator HTML meets quality criteria.

    Args:
        html_content: The generated HTML string

    Returns:
        Tuple of (passed: bool, issues: list of str)
    """
    import re
    issues = []

    # Check minimum length (~1500 lines, avg 80 chars = 120000 chars)
    if len(html_content) < 80000:
        issues.append(f"Content too short: {len(html_content):,} chars (expected 80,000+)")

    # Check for required elements
    for pattern, description in QUALITY_REQUIREMENTS:
        if not re.search(pattern, html_content, re.IGNORECASE):
            issues.append(f"Missing: {description}")

    # Count specific elements
    checkbox_count = len(re.findall(r'type=["\']checkbox["\']', html_content))
    if checkbox_count < 4:
        issues.append(f"Too few checkboxes: {checkbox_count} (expected 4+)")

    pitfall_count = len(re.findall(r'pitfall-number|pitfall-item|class="pitfall', html_content, re.IGNORECASE))
    if pitfall_count < 4:
        issues.append(f"Too few pitfalls: {pitfall_count} (expected 4+)")

    tip_count = len(re.findall(r'tip-card|tip-box|class="tip', html_content, re.IGNORECASE))
    if tip_count < 4:
        issues.append(f"Too few imaging tips: {tip_count} (expected 4+)")

    mnemonic_count = len(re.findall(r'mnemonic-box|mnemonic-letter|class="mnemonic', html_content, re.IGNORECASE))
    if mnemonic_count < 2:
        issues.append(f"Too few mnemonics: {mnemonic_count} (expected 2+)")

    passed = len(issues) == 0
    return passed, issues


def get_claude_client():
    """Get Anthropic client instance."""
    api_key = os.environ.get('CLAUDE_API_KEY')
    if not api_key:
        raise ValueError("CLAUDE_API_KEY environment variable is not set")
    return anthropic.Anthropic(api_key=api_key)


def get_claude_model():
    """Get Claude model name from env or use default (same as ai_tnm.py, ai_prelim.py)."""
    return os.environ.get('CLAUDE_MODEL', 'claude-sonnet-4-20250514')


# ==================== PROMPTS ====================

CALCULATOR_HTML_PROMPT = """You are an expert radiologist and oncologist creating an educational TNM staging calculator for FRCR radiology trainees preparing for their exams.

Generate a COMPLETE, SELF-CONTAINED HTML file with TWO MAIN SECTIONS for {cancer_name} cancer staging.

## CRITICAL ARCHITECTURE REQUIREMENTS

The HTML must have EXACTLY this two-part structure:

### SECTION A: INTERACTIVE CALCULATOR (Form-Based)

The calculator uses FORM INPUTS to AUTOMATICALLY determine staging. Users input their imaging findings; the system calculates T, N, M stages.

Required elements:

1. **Disease-Specific Parameters** (if applicable)
   - Example: Subsite selector for larynx, HPV status for oropharynx

2. **T-Stage via Checkboxes** (hierarchical - check worst first):
   - T4b features group: If ANY checkbox checked = automatic T4b
   - T4a features group: If ANY checkbox checked = automatic T4a
   - Size/extent input for T1-T3 determination

3. **N-Stage via Inputs**:
   - Largest node size (cm) - number input with step="0.1"
   - Node distribution counters (ipsilateral count, contralateral count)
   - ENE (extranodal extension) checkbox

4. **M-Stage via Radio**:
   - Yes/No for distant metastases

5. **Calculate Button + Results Display**:
   - Shows T stage, N stage, M stage, Overall Stage
   - CRITICAL: Must include REASONING explaining WHY each stage was assigned
   - Include CLINICAL IMPLICATIONS section

### SECTION B: COMPREHENSIVE REFERENCE GUIDE

A separate scrollable section BELOW the calculator containing:

1. **Mnemonics Section** (create 2 memorable ones):
   - T4b mnemonic (e.g., "PACE" = Prevertebral, Artery encasement, Cranium, Extension)
   - T4a mnemonic (e.g., "HELP" for specific criteria)

2. **Size-Based T Staging Table** showing cutoffs

3. **N Staging Table** (if variants exist, show comparison)

4. **6+ Imaging Tips** in card format with:
   - Title
   - Description
   - Tip detail

5. **6+ Common Pitfalls** numbered with:
   - Pitfall title
   - Explanation of why it's wrong and how to avoid

6. **8-Step Systematic Reading Approach**

## EXAMPLE HTML STRUCTURES TO FOLLOW

### Calculator Form Pattern:
```html
<div class="calculator-form">
    <div class="form-section">
        <h3 class="section-title">T Stage: Primary Tumor</h3>

        <!-- T4b Features -->
        <div class="form-group">
            <label class="form-label">
                <strong>T4b Features (Unresectable):</strong>
                <span class="help-text">If ANY present = Automatic T4b</span>
            </label>
            <div class="checkbox-group">
                <label class="checkbox-option">
                    <input type="checkbox" id="t4b_feature1" onchange="updateCalculator()">
                    <span>Feature description here</span>
                </label>
                <!-- More checkboxes -->
            </div>
        </div>

        <!-- Tumor Size -->
        <div class="form-group">
            <label class="form-label">
                <strong>Tumor Size (maximum dimension):</strong>
                <span class="help-text">Measure on any plane</span>
            </label>
            <div class="input-with-unit">
                <input type="number" id="tumorSize" step="0.1" min="0" placeholder="e.g., 3.5" onchange="updateCalculator()">
                <span class="unit">cm</span>
            </div>
        </div>
    </div>
</div>
```

### Results Display Pattern:
```html
<div class="result-card" id="finalResult">
    <h2>Final Staging Result</h2>
    <div class="result-grid">
        <div class="result-item">
            <strong>T Stage</strong>
            <div class="result-value" id="resultT">-</div>
        </div>
        <div class="result-item">
            <strong>N Stage</strong>
            <div class="result-value" id="resultN">-</div>
        </div>
        <div class="result-item">
            <strong>M Stage</strong>
            <div class="result-value" id="resultM">-</div>
        </div>
    </div>
    <h3>Overall Stage: <span id="resultStage">-</span></h3>
    <div id="resultReasoning">
        <!-- JavaScript populates: T Stage (T2): Reason why... N Stage (N1): Reason why... -->
    </div>
</div>
```

### Reference Section Pattern:
```html
<div class="reference-section">
    <!-- Mnemonics -->
    <div class="reference-card">
        <h3 class="reference-subtitle">Mnemonics to Remember</h3>
        <div class="mnemonic-grid">
            <div class="mnemonic-box">
                <h4>T4b - "MNEMONIC"</h4>
                <div class="mnemonic-detail">
                    <div class="mnemonic-letter">M</div>
                    <div>What M stands for</div>
                </div>
                <!-- More letters -->
            </div>
        </div>
    </div>

    <!-- Imaging Tips -->
    <div class="reference-card">
        <h3 class="reference-subtitle">Key Imaging Tips</h3>
        <div class="tips-grid">
            <div class="tip-card">
                <h4>Tip Title</h4>
                <p>Description of the tip</p>
                <div class="tip-detail">Additional details...</div>
            </div>
            <!-- 5+ more tip cards -->
        </div>
    </div>

    <!-- Common Pitfalls -->
    <div class="reference-card pitfall-card">
        <h3 class="reference-subtitle">Common Pitfalls to Avoid</h3>
        <div class="pitfall-list">
            <div class="pitfall-item">
                <div class="pitfall-number">1</div>
                <div>
                    <strong>Pitfall title</strong>
                    <p>Why this is wrong and how to avoid it</p>
                </div>
            </div>
            <!-- 5+ more pitfalls -->
        </div>
    </div>

    <!-- Systematic Approach -->
    <div class="reference-card">
        <h3 class="reference-subtitle">Systematic Reading Approach</h3>
        <div class="systematic-steps">
            <div class="step-item">
                <div class="step-number">1</div>
                <div>
                    <strong>Step title</strong>
                    <p>What to do in this step</p>
                </div>
            </div>
            <!-- 7 more steps -->
        </div>
    </div>
</div>
```

## CSS VARIABLES (Use Consistently)
```css
:root {{
    --brand-primary: #e96304;
    --brand-secondary: #ffc107;
    --brand-success: #a8d5ba;
    --brand-neutral: #5E899E;
    --brand-text-primary: #2c3e50;
    --brand-text-secondary: #5a6270;
    --brand-text-light: #8b94a3;
    --brand-bg-white: #ffffff;
    --brand-bg-offwhite: #fdfdfb;
    --brand-border: #c5cad1;
}}
```

## QUALITY CRITERIA CHECKLIST
Your output MUST satisfy ALL of these:

- [ ] Form-based calculator with checkboxes for T4b/T4a features
- [ ] Number inputs for tumor size and node measurements
- [ ] Automatic stage calculation (user inputs findings, system determines T/N)
- [ ] Results include detailed REASONING for each stage
- [ ] Clinical implications section in results
- [ ] Separate Reference Section (not mixed with calculator)
- [ ] At least 2 mnemonics for staging criteria
- [ ] Size cutoff reference table
- [ ] At least 6 imaging tips in card format
- [ ] At least 6 numbered common pitfalls with explanations
- [ ] 8-step systematic reading approach
- [ ] Reset functionality
- [ ] Calculate button
- [ ] Mobile-responsive design
- [ ] Complete CSS included (no external stylesheets)
- [ ] Complete JavaScript included (no external scripts)
- [ ] HTML file should be 1500+ lines to ensure comprehensive coverage

## CANCER-SPECIFIC INFORMATION

Cancer: {cancer_name}
Body Section: {body_section}
Staging System: {staging_system}
{special_notes}

## OUTPUT

Generate the COMPLETE HTML file now. Do not use placeholders. Include ALL CSS and JavaScript inline.
The file must be comprehensive (1500+ lines) with form-based calculator AND reference section."""


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
        model=get_claude_model(),
        max_tokens=20000,
        temperature=0.3,
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
        model=get_claude_model(),
        max_tokens=15000,
        temperature=0.3,
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
    user_id: int = None,
    overwrite: bool = False
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
        overwrite: If True, overwrite existing calculator

    Returns:
        Tuple of (success, message, result_data)
    """
    from models import TNMCalculatorContent

    try:
        # Check if already exists
        existing = TNMCalculatorContent.query.filter_by(slug=slug).first()
        if existing and not overwrite:
            return False, f"Calculator for '{slug}' already exists. Use overwrite option to replace.", {}

        # If overwrite is True and existing record found, delete it first
        if existing and overwrite:
            logger.info(f"[TNM Generator] Overwriting existing calculator for {slug}")
            db.session.delete(existing)
            db.session.commit()

        # Generate calculator HTML
        logger.info(f"[TNM Generator] Starting generation for {cancer_name}")
        calculator_html = generate_calculator_html(
            cancer_name=cancer_name,
            body_section=body_section,
            staging_system=staging_system,
            special_notes=special_notes
        )

        # Validate quality
        passed, issues = validate_calculator_quality(calculator_html)
        if not passed:
            logger.warning(f"[TNM Generator] Quality validation issues for {cancer_name}:")
            for issue in issues:
                logger.warning(f"  - {issue}")
            # Continue anyway but log warnings - could add flag to fail on validation issues
        else:
            logger.info(f"[TNM Generator] Quality validation passed for {cancer_name}")

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
            generation_model=get_claude_model(),
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
    Wraps in identifiable container for later extraction/sync.

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

        # Wrap algorithm in identifiable container for extraction/sync
        algorithm_wrapper = f"""
<!-- TNM-ALGORITHM-START:{calculator_slug} -->
<div class="tnm-algorithm-container" data-algorithm-slug="{calculator_slug}" data-algorithm-version="{content.id}">
<div style="background: linear-gradient(135deg, #5E899E 0%, #4a7285 100%); color: white; padding: 15px 20px; border-radius: 8px 8px 0 0; margin-bottom: 0;">
    <h3 style="margin: 0; font-size: 1.25rem;">
        <i class="fas fa-sitemap" style="margin-right: 10px;"></i>{content.cancer_name} Staging Algorithm
    </h3>
    <small style="opacity: 0.9;">{content.staging_system}</small>
</div>
<div class="tnm-algorithm-content" data-editable="true">
{content.algorithm_discussion_html}
</div>
</div>
<!-- TNM-ALGORITHM-END:{calculator_slug} -->
"""

        case.discussion = existing + separator + algorithm_wrapper
        case.calculator_slug = calculator_slug
        db.session.commit()

        return True, f"Algorithm inserted for {content.cancer_name}"

    except Exception as e:
        logger.error(f"[TNM Generator] Error inserting algorithm: {e}")
        db.session.rollback()
        return False, f"Error: {str(e)}"


def extract_algorithm_from_discussion(discussion_html: str, calculator_slug: str) -> Optional[str]:
    """
    Extract algorithm content from case discussion HTML.

    Args:
        discussion_html: Full discussion HTML
        calculator_slug: Slug of algorithm to extract

    Returns:
        Extracted algorithm HTML or None if not found
    """
    import re

    # Pattern to match algorithm container
    pattern = rf'<!-- TNM-ALGORITHM-START:{re.escape(calculator_slug)} -->.*?<div class="tnm-algorithm-content"[^>]*>(.*?)</div>\s*</div>\s*<!-- TNM-ALGORITHM-END:{re.escape(calculator_slug)} -->'

    match = re.search(pattern, discussion_html, re.DOTALL)
    if match:
        return match.group(1).strip()

    return None


def update_algorithm_template_from_case(
    db,
    case_id: int,
    calculator_slug: str
) -> Tuple[bool, str]:
    """
    Update algorithm template from edited case discussion.
    Extracts algorithm content and saves to TNMCalculatorContent.

    Args:
        db: SQLAlchemy database instance
        case_id: Case ID containing edited algorithm
        calculator_slug: Calculator slug to update

    Returns:
        Tuple of (success, message)
    """
    from models import Case, TNMCalculatorContent

    try:
        case = Case.query.get(case_id)
        if not case:
            return False, "Case not found"

        if not case.discussion:
            return False, "Case has no discussion content"

        content = TNMCalculatorContent.query.filter_by(slug=calculator_slug).first()
        if not content:
            return False, f"Calculator '{calculator_slug}' not found"

        # Extract algorithm from discussion
        extracted = extract_algorithm_from_discussion(case.discussion, calculator_slug)
        if not extracted:
            return False, f"Could not find algorithm for '{calculator_slug}' in discussion"

        # Update template
        old_length = len(content.algorithm_discussion_html or '')
        content.algorithm_discussion_html = extracted
        content.updated_at = datetime.utcnow()
        db.session.commit()

        logger.info(f"[TNM Generator] Updated algorithm template '{calculator_slug}' from case {case_id}: {old_length} -> {len(extracted)} chars")

        return True, f"Algorithm template updated ({len(extracted)} chars)"

    except Exception as e:
        logger.error(f"[TNM Generator] Error updating algorithm template: {e}")
        db.session.rollback()
        return False, f"Error: {str(e)}"
