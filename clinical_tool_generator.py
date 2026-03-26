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
    AIClientError,
)

logger = logging.getLogger(__name__)


class GeneratorError(AIClientError):
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


# ==================== CLOUDINARY IMAGE UPLOAD ====================

def upload_to_cloudinary(image_data, filename='reference_image',
                         folder='frcr_revision/ai_references'):
    """Upload image bytes to Cloudinary.

    Args:
        image_data: bytes or file-like object
        filename: public_id stem (Cloudinary will add extension)
        folder: Cloudinary folder path

    Returns:
        dict with url, public_id, width, height — or None on failure
    """
    try:
        import cloudinary.uploader
        result = cloudinary.uploader.upload(
            image_data,
            folder=folder,
            resource_type='image',
            transformation=[{'quality': 'auto', 'fetch_format': 'auto'}],
        )
        return {
            'url': result['secure_url'],
            'public_id': result['public_id'],
            'width': result.get('width', 0),
            'height': result.get('height', 0),
        }
    except Exception as exc:
        logger.warning("Cloudinary upload failed for %s: %s", filename, exc)
        return None


# ==================== URL IMAGE EXTRACTION ====================

# Patterns that indicate non-content images (logos, icons, tracking pixels, etc.)
_NON_CONTENT_PATTERNS = re.compile(
    r'(logo|icon|avatar|gravatar|tracking|pixel|badge|button|banner|sprite|favicon'
    r'|widget|ad[_-]|advert|\.gif$|1x1|spacer|arrow|nav[_-]|menu[_-])',
    re.IGNORECASE,
)


def fetch_url_images(url, max_images=5):
    """Extract content images from a URL, upload to Cloudinary.

    Returns list of dicts with keys:
        url, title, case_url, source_domain, license, author
    """
    import hashlib
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("BeautifulSoup not available — cannot extract URL images")
        return []

    try:
        resp = requests.get(url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (RadInsights/1.0; +educational)',
        }, allow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("fetch_url_images: request failed for %s: %s", url, exc)
        return []

    content_type = resp.headers.get('Content-Type', '')
    if 'html' not in content_type:
        return []

    soup = BeautifulSoup(resp.text[:300000], 'html.parser')

    # Remove navigation/footer to focus on content
    for tag in soup(['nav', 'footer', 'header', 'aside']):
        tag.decompose()

    # Collect candidate images — prefer <figure> images, then <article>, then <main>/<body>
    candidates = []
    seen_srcs = set()

    # Priority 1: images inside <figure> tags (usually the main content images)
    for fig in soup.find_all('figure'):
        img = fig.find('img')
        if not img:
            continue
        src = img.get('src', '') or img.get('data-src', '')
        if not src or src in seen_srcs:
            continue
        seen_srcs.add(src)
        figcap = fig.find('figcaption')
        caption_text = figcap.get_text(strip=True) if figcap else ''
        candidates.append({
            'src': src,
            'alt': img.get('alt', ''),
            'caption': caption_text,
            'priority': 0,
        })

    # Priority 2: images inside <article> or main content area
    content_area = soup.find('article') or soup.find('main') or soup.find('body')
    if content_area:
        for img in content_area.find_all('img'):
            src = img.get('src', '') or img.get('data-src', '')
            if not src or src in seen_srcs:
                continue
            seen_srcs.add(src)
            candidates.append({
                'src': src,
                'alt': img.get('alt', ''),
                'caption': '',
                'priority': 1,
            })

    # Filter out non-content images
    from urllib.parse import urljoin
    filtered = []
    for c in candidates:
        src = c['src']
        if _NON_CONTENT_PATTERNS.search(src):
            continue
        # Make absolute URL
        c['src'] = urljoin(url, src)
        filtered.append(c)

    # Sort by priority (figure images first)
    filtered.sort(key=lambda x: x['priority'])

    # Download, check size, upload to Cloudinary
    from urllib.parse import urlparse
    source_domain = urlparse(url).netloc
    results = []

    for c in filtered[:max_images * 2]:  # fetch extra in case some fail
        if len(results) >= max_images:
            break
        try:
            img_resp = requests.get(c['src'], timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (RadInsights/1.0; +educational)',
            })
            img_resp.raise_for_status()
            img_bytes = img_resp.content
            # Skip small images (< 10KB likely icons/thumbnails)
            if len(img_bytes) < 10000:
                continue
            # Upload to Cloudinary
            img_hash = hashlib.md5(img_bytes).hexdigest()[:10]
            cloud = upload_to_cloudinary(
                img_bytes,
                filename=f"url_ref_{img_hash}",
                folder='frcr_revision/ai_references',
            )
            if cloud:
                results.append({
                    'url': cloud['url'],
                    'title': c['alt'] or c['caption'] or 'Reference Image',
                    'case_url': url,
                    'source_domain': source_domain,
                    'license': 'See source',
                    'author': None,
                })
        except Exception as exc:
            logger.debug("fetch_url_images: skip image %s: %s", c['src'][:80], exc)
            continue

    logger.info("fetch_url_images: extracted %d images from %s", len(results), url)
    return results


# ==================== PDF IMAGE EXTRACTION ====================

def extract_pdf_images(file_path, max_images=5):
    """Extract images from a PDF using PyMuPDF, upload to Cloudinary.

    Returns list of dicts with keys:
        url, title, case_url, source_domain, license, author
    Gracefully returns [] if PyMuPDF is not installed.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.info("PyMuPDF not installed — skipping PDF image extraction")
        return []

    import hashlib

    try:
        doc = fitz.open(file_path)
    except Exception as exc:
        logger.warning("extract_pdf_images: cannot open %s: %s", file_path, exc)
        return []

    results = []
    for page_num in range(min(len(doc), 30)):  # Limit to 30 pages
        if len(results) >= max_images:
            break
        page = doc[page_num]
        for img_index, img_info in enumerate(page.get_images()):
            if len(results) >= max_images:
                break
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                img_bytes = base_image['image']
                # Skip tiny images (icons, decorations)
                if len(img_bytes) < 5000:
                    continue
                img_hash = hashlib.md5(img_bytes).hexdigest()[:10]
                cloud = upload_to_cloudinary(
                    img_bytes,
                    filename=f"pdf_p{page_num + 1}_i{img_index}_{img_hash}",
                    folder='frcr_revision/ai_pdf_images',
                )
                if cloud:
                    results.append({
                        'url': cloud['url'],
                        'title': f'PDF Figure (page {page_num + 1})',
                        'case_url': '',
                        'source_domain': 'Uploaded PDF',
                        'license': 'See source document',
                        'author': None,
                    })
            except Exception as exc:
                logger.debug("extract_pdf_images: skip xref %d: %s", xref, exc)
                continue

    doc.close()
    logger.info("extract_pdf_images: extracted %d images from %s", len(results), file_path)
    return results


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
        (r'reportOutput|report-output|generateReportBtn|Generate\s+Report', '"Generate Report" button or output'),
    ]

    rt_checks = [
        (r'finding|impression|report', 'Report generation'),
        (r'grade|score|category|classification', 'Grading/classification'),
        (r'Generate\s+Report|generateReport|generate.*report', '"Generate Report" button'),
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
   - REPORT LANGUAGE: Generate copy-paste radiology report text for the finding.
     The report text MUST read as a consultant radiologist's dictation — flowing prose,
     NOT a raw list of checkbox labels or bullet points.
     For example, instead of "Adrenal nodule: 2.1cm, lipid-rich" generate:
     "There is a 2.1 cm left adrenal nodule demonstrating macroscopic fat on unenhanced CT
     (HU < 10), consistent with a lipid-rich adenoma. No follow-up required."
   - Place the generated report text in a <textarea id="reportOutput"> element
   - Include a "Copy Report Language" button that copies from this textarea
   - Include a clearly visible "Generate Report" button (use id="generateReportBtn")
     that compiles all checked/entered inputs into the report text

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

8. CODE CORRECTNESS (CRITICAL)
   - Every HTML attribute MUST be properly closed (e.g., <label for="fieldId">Text</label>)
   - JavaScript variable names MUST be consistent throughout (e.g., if you declare reportText, never misspell it as reporText or reportext)
   - All text strings MUST be complete — never truncate words mid-spelling
   - Test every function name reference: if you define generateReport(), every onclick must use that exact name
   - All HTML tags must be properly opened AND closed (e.g., <em>text</em>, not >text</em>)
   - All comments must be complete (e.g., "// Calculate recommendation", not "//lculate recommendation")
   - All external links with target="_blank" MUST include rel="noopener" (e.g., <a href="..." target="_blank" rel="noopener">)

OUTPUT:
Return ONLY the complete HTML document. No markdown code fences. No explanatory text.
Start with <!DOCTYPE html> and end with </html>.

The calculator should be comprehensive enough that a radiologist can use it during reporting
to determine the correct management recommendation and generate appropriate report language.
Prioritise correctness and completeness over length.
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
   - FINDINGS: (compiled from checked/entered findings, organised by system into flowing prose paragraphs — NOT a raw list of checkbox labels)
   - IMPRESSION: (numbered key findings, most critical first)

   CRITICAL: You MUST include a clearly visible "Generate Report" button (use id="generateReportBtn")
   that compiles all checked/entered inputs into a natural-language radiology report.
   Place the generated report text in a <textarea id="reportOutput"> element.
   The generated report text MUST read as a consultant radiologist's dictation — flowing prose
   grouped by anatomical system, NOT a bullet list or a raw dump of the checked items.
   For example, instead of copying "Liver: normal" verbatim, generate:
   "The liver is normal in size and attenuation with no focal lesion identified."
   Include a "Copy Report" button that copies from the reportOutput textarea.

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

8. CODE CORRECTNESS (CRITICAL)
   - Every HTML attribute MUST be properly closed (e.g., <label for="fieldId">Text</label>)
   - JavaScript variable names MUST be consistent throughout (e.g., if you declare reportText, never misspell it as reporText or reportext)
   - All text strings MUST be complete — never truncate words mid-spelling
   - Test every function name reference: if you define generateReport(), every onclick must use that exact name
   - All HTML tags must be properly opened AND closed (e.g., <em>text</em>, not >text</em>)
   - All comments must be complete (e.g., "// Calculate recommendation", not "//lculate recommendation")
   - All external links with target="_blank" MUST include rel="noopener" (e.g., <a href="..." target="_blank" rel="noopener">)

OUTPUT:
Return ONLY the complete HTML document. No markdown code fences. No explanatory text.
Start with <!DOCTYPE html> and end with </html>.

The template should be comprehensive enough that a radiologist can use it during reporting
to systematically document findings and generate a structured report.
Prioritise correctness and completeness over length.
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

    # Detect truncated output (hit max_tokens before completing HTML)
    if not html.rstrip().endswith('</html>'):
        logger.warning("Generated HTML appears truncated (does not end with </html>). "
                       "Output tokens: %d / max: %d", token_count, 20000)
        # Try to salvage by closing the document
        html = html.rstrip() + '\n</script>\n</body>\n</html>'

    is_valid, warnings = validate_quality(html, tool_type)
    if token_count >= 19500:
        warnings.append(f'Output may be truncated ({token_count} tokens used, near 20000 limit)')

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
