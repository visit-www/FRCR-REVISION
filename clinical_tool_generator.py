"""
Clinical Tool Generator — Unified Pipeline

Generates interactive HTML clinical tools (incidental finding calculators,
reporting templates) and JSON walkthrough trees. Single entry point for
both admin and user-facing generation.

Shared utilities: resource formatting, quality validation, HTML extraction,
PDF text extraction, DB reference fetching.

Phase 1 of Unified Smart Reporter redesign.
"""

import json
import os
import re
import logging
from datetime import datetime

import requests

from ai_client import (
    call_claude as _call_claude_raw,
    strip_markdown_fences as _strip_markdown_fences,
)

logger = logging.getLogger(__name__)


class GeneratorError(Exception):
    """Raised when tool generation fails."""
    pass


# ==================== API HELPER (delegated to ai_client) ====================

def _call_claude(system_prompt, user_prompt, model=None, max_tokens=4000,
                 temperature=0.3, timeout=60):
    """Wrapper that raises GeneratorError instead of AIClientError."""
    return _call_claude_raw(system_prompt, user_prompt, model=model,
                            max_tokens=max_tokens, temperature=temperature,
                            timeout=timeout, error_class=GeneratorError)


# ==================== URL CONTENT FETCHING ====================

def fetch_url_content(url, max_chars=4000):
    """Fetch a URL and return plain text content for prompt injection.
    Returns extracted text or empty string on failure."""
    import requests
    import re as _re
    try:
        resp = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (RadInsights/1.0; +educational)',
        }, allow_redirects=True)
        resp.raise_for_status()
        content_type = resp.headers.get('Content-Type', '')
        # Only process text/html or text/plain
        if 'html' in content_type:
            html = resp.text[:200000]
            # Try BeautifulSoup if available
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                # Remove script/style
                for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                    tag.decompose()
                text = soup.get_text(separator='\n', strip=True)
            except ImportError:
                # Fallback: strip HTML tags with regex
                text = _re.sub(r'<[^>]+>', ' ', html)
                text = _re.sub(r'\s+', ' ', text).strip()
        elif 'text/plain' in content_type:
            text = resp.text
        else:
            print(f"[URL FETCH] Skipped {url}: unsupported content type {content_type}")
            return ''
        result = text[:max_chars].strip()
        print(f"[URL FETCH] OK {url} → {len(result)} chars")
        return result
    except Exception as exc:
        print(f"[URL FETCH] Failed {url}: {exc}")
        return ''


# ==================== RESOURCE FORMATTING (Gap 1) ====================

def format_resources_for_prompt(resources):
    """
    Convert resources into a structured prompt section.

    Accepts two formats:
    1. Admin JSON string (from guideline_source/source_citation fields):
       '{"references": [...], "linked_cases": [...], "linked_tnm": [...], "pdfs": [...]}'
    2. Gap 1 dict with keys: urls, db_refs, pdf_texts, tnm_refs

    Returns:
        str: Formatted prompt section, or empty string if no resources
    """
    if not resources:
        return ''

    # Handle JSON string from admin fields
    if isinstance(resources, str):
        resources = resources.strip()
        if not resources:
            return ''
        try:
            parsed = json.loads(resources)
        except (json.JSONDecodeError, TypeError):
            # Plain text reference — return as-is
            return f"REFERENCE: {resources}"
        if isinstance(parsed, str):
            return f"REFERENCE: {parsed}"
        if not isinstance(parsed, dict):
            return ''
        resources = parsed

    if not isinstance(resources, dict):
        return ''

    sections = []

    # Admin-format references (with URL content fetching)
    refs = resources.get('references', [])
    if refs:
        ref_lines = []
        for i, ref in enumerate(refs, 1):
            if isinstance(ref, dict):
                line = f"  {i}. {ref.get('source', 'Unknown')}"
                if ref.get('version'):
                    line += f" ({ref['version']})"
                if ref.get('url'):
                    line += f" — {ref['url']}"
                    fetched = fetch_url_content(ref['url'])
                    if fetched:
                        line += f"\n     Content:\n     {fetched[:4000]}"
                ref_lines.append(line)
            elif isinstance(ref, str):
                ref_lines.append(f"  {i}. {ref}")
        if ref_lines:
            sections.append("REFERENCES:\n" + "\n".join(ref_lines))

    # Gap 1: Reference URLs (fetch content)
    urls = resources.get('urls', [])
    if urls:
        url_parts = []
        for u in urls:
            if not u:
                continue
            fetched = fetch_url_content(u)
            if fetched:
                url_parts.append(f"  - {u}\n    Content:\n    {fetched[:4000]}")
            else:
                url_parts.append(f"  - {u}")
        if url_parts:
            sections.append("REFERENCE ARTICLES:\n" + "\n".join(url_parts))

    # Admin-format linked cases
    cases = resources.get('linked_cases', [])
    if cases:
        case_lines = []
        for c in cases:
            if isinstance(c, dict):
                case_lines.append(f"  - Case {c.get('case_number', '')}: {c.get('diagnosis', '')}")
        if case_lines:
            sections.append("LINKED CASES:\n" + "\n".join(case_lines))

    # Gap 1: DB references (pre-fetched content)
    db_refs = resources.get('db_refs', [])
    if db_refs:
        type_labels = {
            'if': 'Incidental Findings Calculator',
            'rt': 'Reporting Template',
            'protocol': 'Clinical Protocol',
            'tnm': 'TNM Staging System',
        }
        ref_parts = []
        for ref in db_refs:
            if not isinstance(ref, dict):
                continue
            label = type_labels.get(ref.get('type', ''), ref.get('type', 'Reference'))
            content = ref.get('content', '')
            slug = ref.get('slug', '')
            if content:
                ref_parts.append(f"  [{label}: {slug}]\n  {content[:3000]}")
        if ref_parts:
            sections.append("DATABASE CONTENT:\n" + "\n\n".join(ref_parts))

    # Admin + Gap 1: TNM references
    tnm = resources.get('linked_tnm', [])
    if tnm:
        tnm_lines = []
        for t in tnm:
            if isinstance(t, dict):
                tnm_lines.append(f"  - {t.get('cancer_name', t.get('slug', ''))}")
        if tnm_lines:
            sections.append("LINKED TNM CALCULATORS:\n" + "\n".join(tnm_lines))

    tnm_refs = resources.get('tnm_refs', [])
    if tnm_refs:
        tnm_parts = []
        for ref in tnm_refs:
            if isinstance(ref, dict) and ref.get('content'):
                tnm_parts.append(f"  [{ref.get('system', 'TNM')}]\n  {ref['content'][:2000]}")
        if tnm_parts:
            sections.append("TNM STAGING DATA:\n" + "\n\n".join(tnm_parts))

    # Admin PDFs (count only) + Gap 1 PDF texts
    pdfs = resources.get('pdfs', [])
    if pdfs:
        sections.append(f"REFERENCE PDFs: {len(pdfs)} PDF document(s) provided")

    pdf_texts = resources.get('pdf_texts', [])
    if pdf_texts:
        pdf_parts = []
        for pdf in pdf_texts:
            if isinstance(pdf, dict) and pdf.get('text'):
                fname = pdf.get('filename', 'uploaded document')
                pdf_parts.append(f"  [PDF: {fname}]\n  {pdf['text'][:4000]}")
        if pdf_parts:
            sections.append("UPLOADED DOCUMENTS:\n" + "\n\n".join(pdf_parts))

    if not sections:
        return ''

    return (
        "\n\n=== REFERENCE MATERIALS ===\n"
        "Use the following references to ground your output in evidence. "
        "Where references conflict with general knowledge, prefer the references.\n\n"
        + "\n\n".join(sections)
        + "\n=== END REFERENCES ===\n"
    )


# ==================== PDF TEXT EXTRACTION (Gap 1) ====================

def extract_pdf_text(file_path):
    """
    Extract text from a PDF file for prompt injection.

    Returns:
        str: Extracted text, or empty string on failure
    """
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages[:20]:  # Limit to 20 pages
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n\n".join(text_parts)
    except ImportError:
        pass

    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(file_path)
        text_parts = []
        for page in reader.pages[:20]:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n\n".join(text_parts)
    except ImportError:
        logger.warning("Neither pdfplumber nor PyPDF2 available for PDF extraction.")
        return ''
    except Exception as exc:
        logger.error(f"PDF extraction error: {exc}")
        return ''


# ==================== DB REFERENCE FETCHING (Gap 1) ====================

def fetch_db_references(db_refs):
    """
    Load existing DB content by type and slug for prompt injection.

    Args:
        db_refs: list of {'type': 'if'|'rt'|'protocol'|'tnm', 'slug': str}

    Returns:
        list of {'type', 'slug', 'content'} with content filled in
    """
    if not db_refs:
        return []

    results = []
    for ref in db_refs:
        if not isinstance(ref, dict):
            continue
        ref_type = ref.get('type', '')
        slug = ref.get('slug', '')
        if not ref_type or not slug:
            continue

        content = ''
        try:
            if ref_type == 'if':
                from models import IncidentalFindingCalculator
                calc = IncidentalFindingCalculator.query.filter_by(slug=slug).first()
                if calc and calc.algorithm_html:
                    content = _html_to_text(calc.algorithm_html)
            elif ref_type == 'rt':
                from models import ReportingAlgorithm
                tmpl = ReportingAlgorithm.query.filter_by(slug=slug).first()
                if tmpl and tmpl.algorithm_html:
                    content = _html_to_text(tmpl.algorithm_html)
            elif ref_type == 'protocol':
                from models import ClinicalProtocol
                proto = ClinicalProtocol.query.filter_by(id=int(slug) if slug.isdigit() else 0).first()
                if not proto:
                    proto = ClinicalProtocol.query.filter(
                        ClinicalProtocol.title.ilike(f'%{slug}%')
                    ).first()
                if proto and proto.content_html:
                    content = _html_to_text(proto.content_html)[:3000]
            elif ref_type == 'tnm':
                from models import TNMCalculatorContent
                tnm = TNMCalculatorContent.query.filter_by(slug=slug).first()
                if tnm and tnm.calculator_html:
                    content = _html_to_text(tnm.calculator_html)[:2000]
        except Exception as exc:
            logger.warning(f"Error fetching DB ref {ref_type}/{slug}: {exc}")

        if content:
            results.append({'type': ref_type, 'slug': slug, 'content': content})

    return results


def fetch_tnm_data(tnm_slugs):
    """
    Load TNM staging data for prompt context.

    Args:
        tnm_slugs: list of TNM calculator slugs

    Returns:
        list of {'system', 'content'} dicts
    """
    if not tnm_slugs:
        return []

    results = []
    try:
        from models import TNMCalculatorContent
        for slug in tnm_slugs:
            tnm = TNMCalculatorContent.query.filter_by(slug=slug).first()
            if tnm and tnm.calculator_html:
                content = _html_to_text(tnm.calculator_html)[:2000]
                results.append({
                    'system': tnm.cancer_name or slug,
                    'content': content,
                })
    except Exception as exc:
        logger.warning(f"Error fetching TNM data: {exc}")

    return results


def _html_to_text(html):
    """Simple HTML to text conversion for prompt injection."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    except ImportError:
        # Fallback: strip tags with regex
        return re.sub(r'<[^>]+>', ' ', html).strip()


# ==================== HTML CONTENT EXTRACTION ====================

def extract_html_content(html):
    """
    Extract style and body from self-contained HTML for app integration.
    Used by IF, RT, and protocol view routes.

    Returns:
        dict: {'styles': str, 'body': str}
    """
    styles = ''
    body = html

    style_matches = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL)
    if style_matches:
        styles = '\n'.join(style_matches)

    body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL)
    if body_match:
        body = body_match.group(1)

    # Strip <style> blocks from body to prevent them overriding layout CSS
    body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL)

    # Force single-column: replace multi-column grid patterns
    styles = re.sub(
        r'grid-template-columns\s*:\s*(?!1fr\s*[;\}])([^;}\n]+)',
        'grid-template-columns: 1fr',
        styles,
    )

    # Force left-align
    styles = re.sub(
        r'text-align\s*:\s*center',
        'text-align: left',
        styles,
    )

    return {'styles': styles, 'body': body}


# ==================== QUALITY VALIDATION ====================

def validate_quality(html, tool_type='if'):
    """
    Validate generated HTML meets minimum quality standards.

    Args:
        html: Generated HTML string
        tool_type: 'if' for incidental findings, 'rt' for reporting template

    Returns:
        tuple: (is_valid: bool, warnings: list[str])
    """
    warnings = []

    if len(html) < 5000:
        warnings.append(f'HTML too short ({len(html)} chars, expected 5000+)')

    common_checks = [
        (r'type=["\']checkbox["\']|type=["\']radio["\']', 'Interactive inputs'),
        (r'copy|clipboard', 'Copy functionality'),
    ]

    if_checks = [
        (r'type=["\']number["\']', 'Number inputs for measurements'),
        (r'recommendation|follow-up|follow up', 'Follow-up recommendations'),
        (r'report|impression', 'Report language section'),
    ]

    rt_checks = [
        (r'finding|impression|report', 'Report generation'),
        (r'grade|score|category|classification', 'Grading/classification'),
    ]

    checks = common_checks + (if_checks if tool_type == 'if' else rt_checks)

    for pattern, description in checks:
        if not re.search(pattern, html, re.IGNORECASE):
            warnings.append(f'Missing: {description}')

    is_valid = len(warnings) <= 2
    return is_valid, warnings


# ==================== ALGORITHM SUMMARY EXTRACTION ====================

def extract_algorithm_summary(html, title, tool_type='if'):
    """
    Extract a portable algorithm summary from generated HTML.

    Args:
        html: Full calculator/template HTML
        title: Display title for the tool
        tool_type: 'if' or 'rt'

    Returns:
        str: Portable HTML summary snippet
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        css_class = 'if-algorithm' if tool_type == 'if' else 'reporting-algorithm'
        return f'<div class="{css_class}"><h4>{title}</h4><p>See interactive tool for full decision tree.</p></div>'

    soup = BeautifulSoup(html, 'html.parser')

    PRIMARY = '#5E899E'
    BG_OFFWHITE = '#f8f9fa'
    BORDER = '#e9ecef'

    # Keywords differ slightly by tool type
    if tool_type == 'if':
        keywords = ['reference', 'summary', 'algorithm', 'guideline', 'classification', 'criteria']
    else:
        keywords = ['reference', 'classification', 'grading', 'criteria', 'scale', 'scoring']

    sections = []
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        text = heading.get_text(strip=True).lower()
        if any(kw in text for kw in keywords):
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
        css_class = 'if-algorithm' if tool_type == 'if' else 'reporting-algorithm'
        return f'<div class="{css_class}"><h4>{title}</h4><p>See interactive tool for full decision tree.</p></div>'

    parts = [
        f'<div style="margin: 1rem 0; padding: 1rem; background: {BG_OFFWHITE}; border-radius: 10px; border: 1px solid {BORDER};">',
        f'<h4 style="color: {PRIMARY}; margin-bottom: 1rem;">{title} — Quick Reference</h4>',
    ]

    for section in sections[:4]:
        parts.append(
            f'<h6 style="color: #2c3e50; border-bottom: 2px solid {PRIMARY}; '
            f'padding-bottom: 0.3rem; margin-top: 1rem;">{section["title"]}</h6>'
        )
        parts.append(section['content'])

    parts.append('</div>')
    return '\n'.join(parts)


# ==================== PROMPTS ====================

IF_SYSTEM_PROMPT = (
    "You are an experienced radiology consultant creating clinical decision support tools. "
    "Generate complete, self-contained HTML pages with accurate clinical content based on "
    "published guidelines. All CSS and JavaScript must be inline."
)

RT_SYSTEM_PROMPT = (
    "You are an experienced radiology consultant creating clinical reporting tools. "
    "Generate complete, self-contained HTML pages with accurate clinical content. "
    "All CSS and JavaScript must be inline. Focus on practical, reporting-oriented "
    "decision trees that generate structured radiology reports."
)

IF_CALCULATOR_PROMPT = """You are an expert radiology consultant creating an interactive incidental finding calculator.

FINDING: {topic}
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
   - Include at top: "Clinical Decision Support Tool -- verify against current guidelines before clinical use"
   - Include guideline citation and version

OUTPUT:
Return ONLY the complete HTML document. No markdown code fences. No explanatory text.
Start with <!DOCTYPE html> and end with </html>.

The calculator should be comprehensive enough that a radiologist can use it during reporting
to determine the correct management recommendation and generate appropriate report language.
Minimum 1500 lines of well-structured HTML/CSS/JS.
"""

REPORTING_TEMPLATE_PROMPT = """You are an expert radiology consultant creating an interactive reporting decision tree.

TEMPLATE TITLE: {topic}
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
   - Colour-coded severity (green > yellow > red)

6. JAVASCRIPT
   - All logic inline (no external dependencies)
   - Auto-calculate on input change
   - Report generation from inputs
   - Copy-to-clipboard functionality
   - Print-friendly output

7. DISCLAIMER
   - Include at top: "Clinical Decision Support Tool -- verify against current guidelines and institutional protocols before clinical use"
   - Include source citation

OUTPUT:
Return ONLY the complete HTML document. No markdown code fences. No explanatory text.
Start with <!DOCTYPE html> and end with </html>.

The template should be comprehensive enough that a radiologist can use it during reporting
to systematically document findings and generate a structured report.
Minimum 1500 lines of well-structured HTML/CSS/JS.
"""


# ==================== MAIN GENERATOR ====================

def generate_clinical_tool(topic, mode='full_tool', context=None, resources=None, model=None):
    """
    Unified generator for clinical tools.

    Args:
        topic: Tool title/finding name (e.g. "Pulmonary Nodule", "AAST Splenic Injury")
        mode: 'full_tool' for interactive HTML (IF/RT generators)
        context: dict with tool_type, category, body_section, guideline_source/source_citation,
                 additional_context
        resources: dict with urls, db_refs, pdf_texts, tnm_refs (Gap 1)
        model: Override Claude model

    Returns:
        dict with: html, algorithm_html, is_valid, warnings, model, token_count
    """
    if context is None:
        context = {}

    tool_type = context.get('tool_type', 'rt')
    category = context.get('category', '')
    body_section = context.get('body_section', '')
    additional_context = context.get('additional_context', '')

    # Build resource section from both admin resources and Gap 1 resources
    resource_text = ''
    if resources:
        resource_text = format_resources_for_prompt(resources)

    if tool_type == 'if':
        guideline_source = context.get('guideline_source', '')
        # Format admin guideline_source if it's JSON
        if guideline_source and not resource_text:
            resource_text = format_resources_for_prompt(guideline_source)
        elif guideline_source and not resource_text.strip():
            resource_text = format_resources_for_prompt(guideline_source)

        # Combine additional_context with resource text
        combined_context = additional_context
        if resource_text:
            combined_context = (additional_context + "\n\n" + resource_text).strip()

        user_prompt = IF_CALCULATOR_PROMPT.format(
            topic=topic,
            guideline_source=guideline_source if not resource_text else 'See references below',
            category=category or 'incidental',
            body_section=body_section or 'Not specified',
            additional_context=combined_context,
        )
        system_prompt = IF_SYSTEM_PROMPT
    else:
        source_citation = context.get('source_citation', '')
        if source_citation and not resource_text:
            resource_text = format_resources_for_prompt(source_citation)

        combined_context = additional_context
        if resource_text:
            combined_context = (additional_context + "\n\n" + resource_text).strip()

        user_prompt = REPORTING_TEMPLATE_PROMPT.format(
            topic=topic,
            category=category or 'reporting',
            body_section=body_section or 'Not specified',
            source_citation=source_citation if not resource_text else 'See references below',
            additional_context=combined_context,
        )
        system_prompt = RT_SYSTEM_PROMPT

    effective_model = model or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    text, used_model, token_count = _call_claude(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=effective_model,
        max_tokens=20000,
        temperature=0.3,
        timeout=240,
    )

    html = _strip_markdown_fences(text)
    is_valid, warnings = validate_quality(html, tool_type)
    algorithm_html = extract_algorithm_summary(html, topic, tool_type)

    return {
        'html': html,
        'algorithm_html': algorithm_html,
        'is_valid': is_valid,
        'warnings': warnings,
        'model': used_model,
        'token_count': token_count,
        'prompt': user_prompt[:2000],
    }
