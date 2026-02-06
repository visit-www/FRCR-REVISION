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


def extract_algorithm_from_calculator(calculator_html: str, cancer_name: str) -> str:
    """
    Extract algorithm discussion HTML from calculator HTML.

    The calculator already contains mnemonics, imaging tips, pitfalls, and
    systematic approach - we extract and reformat these sections with INLINE
    STYLES so they look good when inserted into case discussion fields.

    Args:
        calculator_html: Complete calculator HTML content
        cancer_name: Name of the cancer for header

    Returns:
        Formatted algorithm discussion HTML with inline styles
    """
    import re
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(calculator_html, 'html.parser')

    # Brand colors (inline - can't use CSS variables in discussion field)
    PRIMARY = '#5E899E'
    PRIMARY_DARK = '#4a7285'
    BG_OFFWHITE = '#f8f9fa'
    BORDER = '#e9ecef'
    DANGER = '#dc3545'

    # Card base style
    card_style = f"margin-bottom: 1.5rem; padding: 1.25rem; background: {BG_OFFWHITE}; border-radius: 10px; border: 1px solid {BORDER};"
    subtitle_style = f"font-size: 1.1rem; color: #2c3e50; margin-bottom: 1rem; font-weight: 600; border-bottom: 2px solid {PRIMARY}; padding-bottom: 0.5rem;"
    grid_style = "display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem;"

    sections_html = []

    # Extract and style mnemonics
    mnemonic_grid = soup.find('div', class_='mnemonic-grid')
    if mnemonic_grid:
        mnemonic_boxes = mnemonic_grid.find_all('div', class_='mnemonic-box')
        if mnemonic_boxes:
            boxes_html = []
            for box in mnemonic_boxes:
                h4 = box.find('h4')
                title = h4.get_text(strip=True) if h4 else 'Mnemonic'
                details = box.find_all('div', class_='mnemonic-detail')
                details_html = []
                for detail in details:
                    letter_el = detail.find('div', class_='mnemonic-letter')
                    letter = letter_el.get_text(strip=True) if letter_el else ''
                    # Get text after the letter
                    text = detail.get_text(strip=True).replace(letter, '', 1).strip()
                    details_html.append(f'''
                        <div style="display: flex; align-items: center; margin-bottom: 0.5rem; padding: 0.5rem; background: white; border-radius: 6px;">
                            <div style="width: 28px; height: 28px; background: {PRIMARY}; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; margin-right: 0.75rem; flex-shrink: 0; font-size: 0.9rem;">{letter}</div>
                            <span style="color: #2c3e50;">{text}</span>
                        </div>
                    ''')
                boxes_html.append(f'''
                    <div style="background: white; padding: 1rem; border-radius: 8px; border: 2px solid {PRIMARY};">
                        <h4 style="color: {PRIMARY}; margin: 0 0 0.75rem 0; font-size: 1rem; font-weight: 600;">{title}</h4>
                        {''.join(details_html)}
                    </div>
                ''')
            sections_html.append(f'''
                <div style="{card_style}">
                    <h4 style="{subtitle_style}"><i class="fas fa-brain" style="margin-right: 0.5rem; color: {PRIMARY};"></i>Memory Aids</h4>
                    <div style="{grid_style}">{''.join(boxes_html)}</div>
                </div>
            ''')

    # Extract and style imaging tips
    tips_grid = soup.find('div', class_='tips-grid')
    if tips_grid:
        tip_cards = tips_grid.find_all('div', class_='tip-card')
        if tip_cards:
            tips_html = []
            for card in tip_cards:
                h4 = card.find('h4')
                title = h4.get_text(strip=True) if h4 else 'Tip'
                # Get paragraph or tip-detail content
                detail = card.find('div', class_='tip-detail') or card.find('p')
                text = detail.get_text(strip=True) if detail else ''
                tips_html.append(f'''
                    <div style="background: white; padding: 1rem; border-radius: 8px; border: 1px solid {BORDER};">
                        <h4 style="color: {PRIMARY}; margin: 0 0 0.5rem 0; font-size: 0.95rem; font-weight: 600;">{title}</h4>
                        <p style="margin: 0; color: #495057; font-size: 0.9rem; line-height: 1.5;">{text}</p>
                    </div>
                ''')
            sections_html.append(f'''
                <div style="{card_style}">
                    <h4 style="{subtitle_style}"><i class="fas fa-lightbulb" style="margin-right: 0.5rem; color: {PRIMARY};"></i>Imaging Tips</h4>
                    <div style="{grid_style}">{''.join(tips_html)}</div>
                </div>
            ''')

    # Extract and style pitfalls
    pitfall_list = soup.find('div', class_='pitfall-list')
    if pitfall_list:
        pitfall_items = pitfall_list.find_all('div', class_='pitfall-item')
        if pitfall_items:
            pitfalls_html = []
            for i, item in enumerate(pitfall_items, 1):
                # Get text content, excluding the number
                number_el = item.find('div', class_='pitfall-number')
                text = item.get_text(strip=True)
                if number_el:
                    text = text.replace(number_el.get_text(strip=True), '', 1).strip()
                pitfalls_html.append(f'''
                    <div style="display: flex; align-items: flex-start; padding: 0.75rem; background: white; border-radius: 8px; border: 1px solid rgba(220, 53, 69, 0.2); margin-bottom: 0.5rem;">
                        <div style="width: 26px; height: 26px; background: {DANGER}; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; margin-right: 0.75rem; flex-shrink: 0; font-size: 0.85rem;">{i}</div>
                        <span style="color: #2c3e50; line-height: 1.5;">{text}</span>
                    </div>
                ''')
            sections_html.append(f'''
                <div style="{card_style} background: rgba(220, 53, 69, 0.03); border-color: rgba(220, 53, 69, 0.15);">
                    <h4 style="{subtitle_style} border-color: {DANGER};"><i class="fas fa-exclamation-triangle" style="margin-right: 0.5rem; color: {DANGER};"></i>Common Pitfalls</h4>
                    {''.join(pitfalls_html)}
                </div>
            ''')

    # Extract and style systematic approach
    systematic_steps = soup.find('div', class_='systematic-steps')
    if systematic_steps:
        step_items = systematic_steps.find_all('div', class_='step-item')
        if step_items:
            steps_html = []
            for i, item in enumerate(step_items, 1):
                h4 = item.find('h4')
                title = h4.get_text(strip=True) if h4 else f'Step {i}'
                # Get content after h4
                content_parts = []
                for child in item.children:
                    if child.name and child.name != 'h4':
                        content_parts.append(child.get_text(strip=True))
                text = ' '.join(content_parts)
                steps_html.append(f'''
                    <div style="display: flex; align-items: flex-start; padding: 0.75rem; background: white; border-radius: 8px; border: 1px solid {BORDER}; margin-bottom: 0.5rem;">
                        <div style="width: 26px; height: 26px; background: {PRIMARY}; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; margin-right: 0.75rem; flex-shrink: 0; font-size: 0.85rem;">{i}</div>
                        <div>
                            <strong style="color: {PRIMARY};">{title}</strong>
                            <p style="margin: 0.25rem 0 0 0; color: #495057; font-size: 0.9rem;">{text}</p>
                        </div>
                    </div>
                ''')
            sections_html.append(f'''
                <div style="{card_style}">
                    <h4 style="{subtitle_style}"><i class="fas fa-list-ol" style="margin-right: 0.5rem; color: {PRIMARY};"></i>Systematic Approach</h4>
                    {''.join(steps_html)}
                </div>
            ''')

    # Build the final HTML
    slug = cancer_name.lower().replace(' ', '-').replace('(', '').replace(')', '')

    if not sections_html:
        logger.warning(f"[TNM Generator] Could not extract algorithm sections from calculator for {cancer_name}")
        # Return a styled fallback
        return f'''
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 1rem 0;">
            <div style="background: linear-gradient(135deg, {PRIMARY} 0%, {PRIMARY_DARK} 100%); color: white; padding: 1rem 1.25rem; border-radius: 8px;">
                <h3 style="margin: 0; font-size: 1.1rem; font-weight: 600;">
                    <i class="fas fa-sitemap" style="margin-right: 0.5rem;"></i>{cancer_name} Staging Algorithm
                </h3>
                <p style="margin: 0.75rem 0 0 0; opacity: 0.9;">See the <a href="/tnm-calculator/{slug}" target="_blank" style="color: white; text-decoration: underline;">interactive TNM calculator</a> for detailed staging criteria, mnemonics, and imaging tips.</p>
            </div>
        </div>
        '''

    # Header + sections + footer link
    result = f'''
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 1rem 0;">
        <div style="background: linear-gradient(135deg, {PRIMARY} 0%, {PRIMARY_DARK} 100%); color: white; padding: 1rem 1.25rem; border-radius: 8px 8px 0 0;">
            <h3 style="margin: 0; font-size: 1.15rem; font-weight: 600;">
                <i class="fas fa-sitemap" style="margin-right: 0.5rem;"></i>{cancer_name} Staging Algorithm
            </h3>
        </div>
        <div style="background: white; border: 1px solid {BORDER}; border-top: none; border-radius: 0 0 8px 8px; padding: 1.25rem;">
            {''.join(sections_html)}
            <div style="text-align: center; padding-top: 0.5rem; border-top: 1px solid {BORDER}; margin-top: 0.5rem;">
                <a href="/tnm-calculator/{slug}" target="_blank" style="color: {PRIMARY}; text-decoration: none; font-weight: 500; font-size: 0.9rem;">
                    <i class="fas fa-calculator" style="margin-right: 0.5rem;"></i>Open Interactive Calculator
                </a>
            </div>
        </div>
    </div>
    '''

    logger.info(f"[TNM Generator] Extracted algorithm from calculator for {cancer_name} ({len(result):,} chars)")
    return result


# ==================== STAGING NUANCES ====================

def load_staging_nuances():
    """Load disease-specific staging nuances from JSON file."""
    nuances_file = Path(__file__).parent / 'staging_nuances.json'
    if nuances_file.exists():
        with open(nuances_file, 'r') as f:
            return json.load(f)
    return {}


def get_disease_nuances(cancer_name: str, body_section: str) -> str:
    """Get disease-specific nuances for the given cancer type."""
    nuances = load_staging_nuances()

    # Map body sections to nuances keys
    section_map = {
        'head and neck': 'head_and_neck',
        'thorax': 'thorax',
        'breast': 'breast',
        'gastrointestinal': 'gastrointestinal',
        'hepatobiliary': 'gastrointestinal',
        'genitourinary': 'genitourinary',
        'gynecologic': 'gynecologic',
        'musculoskeletal': 'musculoskeletal',
        'skin': 'skin',
        'neuroendocrine': 'neuroendocrine',
        'hematologic': 'hematologic',
        'central nervous system': 'central_nervous_system',
        'bone': 'musculoskeletal',
        'soft tissue': 'musculoskeletal',
        'endocrine': 'head_and_neck',  # thyroid etc
    }

    # Map cancer names to nuances keys
    cancer_map = {
        'larynx': 'larynx',
        'oropharynx': 'oropharynx_hpv_positive',  # default to HPV+
        'oropharynx (hpv-associated)': 'oropharynx_hpv_positive',
        'oropharynx (hpv-independent)': 'oropharynx_hpv_negative',
        'hypopharynx': 'oropharynx_hpv_negative',
        'nasopharynx': 'nasopharynx',
        'oral cavity': 'oral_cavity',
        'nasal cavity': 'nasal_cavity_paranasal_sinuses',
        'paranasal sinuses': 'nasal_cavity_paranasal_sinuses',
        'salivary': 'salivary_glands',
        'thyroid': 'thyroid_differentiated',
        'lung': 'lung',
        'mesothelioma': 'pleural_mesothelioma',
        'thymus': 'thymus',
        'breast': 'breast',
        'esophagus': 'esophagus',
        'stomach': 'stomach',
        'colon': 'colon_rectum',
        'rectum': 'colon_rectum',
        'liver': 'liver_hcc',
        'pancreas': 'pancreas',
        'kidney': 'kidney',
        'bladder': 'bladder',
        'prostate': 'prostate',
        'testis': 'testis',
        'cervix': 'cervix',
        'ovary': 'ovary',
        'endometrium': 'endometrium',
        'melanoma': 'melanoma',
        'merkel': 'merkel_cell',
        'bone': 'bone_sarcoma',
        'sarcoma': 'soft_tissue_sarcoma',
    }

    # Find matching section
    section_key = None
    body_section_lower = body_section.lower()
    for key, value in section_map.items():
        if key in body_section_lower:
            section_key = value
            break

    # Find matching cancer
    cancer_key = None
    cancer_lower = cancer_name.lower()
    for key, value in cancer_map.items():
        if key in cancer_lower:
            cancer_key = value
            break

    # Build nuances text
    result_parts = []

    if section_key and section_key in nuances:
        section_nuances = nuances[section_key]
        if cancer_key and cancer_key in section_nuances:
            disease_nuances = section_nuances[cancer_key]
            result_parts.append(f"## DISEASE-SPECIFIC STAGING NUANCES FOR {cancer_name.upper()}\n")
            result_parts.append("Use these nuances to ensure accurate staging:\n")
            result_parts.append(json.dumps(disease_nuances, indent=2))

    if not result_parts:
        # Generic guidance
        result_parts.append(f"## NOTE: Ensure staging is specific to {cancer_name}\n")
        result_parts.append("If this cancer has subsites, staging should adapt to the specific subsite selected.")

    return '\n'.join(result_parts)


def get_opus_example_excerpt() -> str:
    """Get excerpt from Opus-generated calculator as quality reference."""
    example_file = Path(__file__).parent / 'calculators' / 'larynx-opus_calc.html'
    if not example_file.exists():
        return ""

    # Read the file and extract key sections
    with open(example_file, 'r') as f:
        content = f.read()

    # Extract the calculateTStage function as an example of good subsite-specific logic
    import re
    match = re.search(r'(function calculateTStage\(\).*?^        \})', content, re.MULTILINE | re.DOTALL)
    if match:
        excerpt = match.group(1)
        return f"""
## REFERENCE: EXAMPLE OF HIGH-QUALITY SUBSITE-SPECIFIC STAGING LOGIC

The following is an example of excellent staging logic that adapts to subsites.
Your calculator should follow this pattern of subsite-aware staging:

```javascript
{excerpt[:3000]}...
```

KEY QUALITIES TO EMULATE:
1. Separate staging logic for each subsite (supraglottic, glottic, subglottic)
2. T1a/T1b distinctions where medically appropriate
3. Clear reasoning returned with each stage determination
4. Modular function structure (calculateTStage, calculateNStage, etc.)
"""
    return ""


# ==================== PROMPTS ====================

CALCULATOR_HTML_PROMPT = """You are an experienced oncology radiologist creating a practical TNM staging calculator. Your role is to guide radiology registrars through staging scans as they encounter them in daily clinical practice - think of yourself as a senior consultant helping a registrar report a staging scan step-by-step. This should also serve FRCR exam preparation.

{disease_nuances}

{opus_example}

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

## CRITICAL LAYOUT REQUIREMENT

The page MUST use a **SINGLE-COLUMN VERTICAL LAYOUT** (not side-by-side grid). This is required for iframe embedding compatibility.

Structure the page as:
1. Header (centered)
2. Calculator Form (full width, stacked vertically)
3. Results Card (full width, below calculator)
4. Reference Section (full width, below results)

**DO NOT use side-by-side layouts** like `grid-template-columns: 1fr 1fr` for the main content.
Use `display: flex; flex-direction: column;` for the main content wrapper.

## QUALITY CRITERIA CHECKLIST
Your output MUST satisfy ALL of these:

- [ ] **VERTICAL LAYOUT** - Single column, no side-by-side sections (critical for iframe)
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
    special_notes: str = "",
    model: str = None
) -> str:
    """
    Generate interactive TNM calculator HTML using Claude.

    Args:
        cancer_name: Display name (e.g., "Oropharynx", "Lung (NSCLC)")
        body_section: Body section (e.g., "Head and Neck", "Thorax")
        staging_system: Staging system used (default: AJCC 9th Edition)
        special_notes: Additional notes for generation (e.g., HPV variants)
        model: Claude model to use (defaults to env CLAUDE_MODEL or sonnet)

    Returns:
        Complete HTML string for the calculator
    """
    client = get_claude_client()

    # Get disease-specific nuances and Opus example for enhanced quality
    disease_nuances = get_disease_nuances(cancer_name, body_section)
    opus_example = get_opus_example_excerpt()

    prompt = CALCULATOR_HTML_PROMPT.format(
        cancer_name=cancer_name,
        body_section=body_section,
        staging_system=staging_system,
        special_notes=f"Special considerations: {special_notes}" if special_notes else "",
        disease_nuances=disease_nuances,
        opus_example=opus_example
    )

    logger.info(f"[TNM Generator] Generating calculator HTML for {cancer_name}")

    # Use provided model or fall back to environment/default
    if model is None:
        model = get_claude_model()
    max_retries = 3
    retry_delay = 10  # seconds

    for attempt in range(max_retries):
        try:
            # Opus requires streaming for long operations (SDK requirement for >10min potential)
            if 'opus' in model.lower():
                logger.info(f"[TNM Generator] Using streaming for Opus model (attempt {attempt + 1})")
                html_content = ""
                with client.messages.stream(
                    model=model,
                    max_tokens=20000,
                    temperature=0.3,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                ) as stream:
                    for text in stream.text_stream:
                        html_content += text
            else:
                response = client.messages.create(
                    model=model,
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
            break  # Success, exit retry loop
        except Exception as e:
            if 'overloaded' in str(e).lower() and attempt < max_retries - 1:
                import time
                logger.warning(f"[TNM Generator] API overloaded, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                raise

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
    overwrite: bool = False,
    model: str = None
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
        model: Claude model to use (defaults to env CLAUDE_MODEL or sonnet)

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

        # Use provided model or fall back to environment/default
        effective_model = model if model else get_claude_model()
        logger.info(f"[TNM Generator] Starting generation for {cancer_name} with model {effective_model}")

        # Generate calculator HTML
        calculator_html = generate_calculator_html(
            cancer_name=cancer_name,
            body_section=body_section,
            staging_system=staging_system,
            special_notes=special_notes,
            model=effective_model
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

        # Extract algorithm discussion from calculator HTML (no second API call!)
        # The calculator already contains mnemonics, tips, pitfalls, systematic approach
        algorithm_html = extract_algorithm_from_calculator(calculator_html, cancer_name)
        logger.info(f"[TNM Generator] Algorithm extracted from calculator (no additional API call)")

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
            generation_model=effective_model,
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
        # Note: algorithm_discussion_html already includes styled header, so we just wrap it
        algorithm_wrapper = f"""
<!-- TNM-ALGORITHM-START:{calculator_slug} -->
<div class="tnm-algorithm-container" data-algorithm-slug="{calculator_slug}" data-algorithm-version="{content.id}" data-editable="true">
{content.algorithm_discussion_html}
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
