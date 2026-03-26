"""
Incidental Finding Calculator Generator — Thin Wrapper

Delegates to clinical_tool_generator.py for actual generation.
Handles IF-specific database operations (create/update IncidentalFindingCalculator).
"""

import re
import logging
from collections import Counter
from datetime import datetime

from clinical_tool_generator import generate_clinical_tool, GeneratorError

logger = logging.getLogger(__name__)

# Minimum word length and stopwords for keyword extraction
_MIN_WORD_LEN = 4
_STOPWORDS = frozenset({
    # English stopwords
    'this', 'that', 'with', 'from', 'have', 'been', 'will', 'would', 'could',
    'should', 'their', 'there', 'they', 'them', 'then', 'than', 'these',
    'those', 'which', 'what', 'when', 'where', 'were', 'your', 'does', 'done',
    'each', 'more', 'most', 'much', 'such', 'very', 'into', 'over', 'also',
    'only', 'some', 'other', 'about', 'after', 'before', 'between', 'under',
    'above', 'below', 'both', 'same', 'based', 'using', 'used', 'make',
    'like', 'include', 'including', 'else', 'case',
    # HTML/CSS terms
    'style', 'class', 'table', 'thead', 'tbody', 'display', 'margin',
    'padding', 'border', 'color', 'background', 'font', 'width', 'height',
    'content', 'type', 'name', 'label', 'radio', 'checkbox', 'option',
    'title', 'section', 'header', 'body', 'html', 'head', 'solid',
    'hidden', 'overflow', 'white', 'none', 'auto', 'grid', 'flex',
    'margin-top', 'margin-bottom', 'font-size', 'font-weight',
    'border-radius', 'grid-template-columns', 'text-align',
    # JavaScript terms
    'script', 'function', 'return', 'document', 'element', 'event',
    'query', 'parse', 'float', 'number', 'string', 'true', 'false',
    'null', 'undefined', 'getelementbyid', 'queryselector', 'addeventlistener',
    'textcontent', 'classname', 'parsefloat', 'parseint', 'isnan', 'tofixed',
    'checked', 'foreach', 'indexof', 'length', 'prototype', 'tostring',
    # Form/UI terms
    'enter', 'value', 'click', 'button', 'select', 'check', 'input',
    'output', 'text', 'form', 'data', 'container', 'result', 'results',
    'status', 'method', 'placeholder', 'center', 'cursor', 'pointer',
    'repeat', 'auto-fill', 'max-width', 'media',
    # CSS variable/brand prefixes
    'brand-primary', 'brand-neutral', 'brand-border', 'brand-text-primary',
    'status-benign', 'status-indeterminate', 'status-suspicious',
})


def _extract_keywords_from_html(html, finding_name='', category='',
                                 guideline_source='', max_keywords=80):
    """Extract clinically relevant search terms from generated HTML content.

    Strips tags, extracts meaningful words and bigrams, deduplicates,
    and returns a comma-separated keyword string for pg_trgm search.
    """
    # Strip HTML tags to get plain text
    text = re.sub(r'<[^>]+>', ' ', html)
    # Decode common HTML entities
    for entity, char in [('&gt;', '>'), ('&lt;', '<'), ('&amp;', '&'),
                         ('&ge;', '>='), ('&le;', '<='), ('&bull;', ''),
                         ('&minus;', '-'), ('&darr;', '')]:
        text = text.replace(entity, char)
    # Remove CSS/JS artifacts
    text = re.sub(r'[{}();:=\[\]\'\"\\]', ' ', text)
    text = re.sub(r'\b\d+(\.\d+)?(px|em|rem|%|fr|ms|vh|vw)\b', ' ', text)
    text = re.sub(r'#[0-9a-fA-F]{3,8}\b', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # Tokenise
    words = re.findall(r'[a-zA-Z][a-zA-Z0-9-]{3,}', text.lower())
    words = [w for w in words if w not in _STOPWORDS and len(w) >= _MIN_WORD_LEN]

    # Count frequency — higher frequency = more relevant
    freq = Counter(words)

    # Build bigrams from the original text for clinical phrases
    text_lower = text.lower()
    bigrams = re.findall(
        r'\b([a-z][a-z-]{2,})\s+([a-z][a-z-]{2,})\b', text_lower
    )
    _bigram_noise = frozenset({
        'var', 'else', 'solid', 'getelementbyid', 'classname', 'textcontent',
        'parsefloat', 'checked', 'reporttext', 'statusclass', 'followup',
    })
    bigram_freq = Counter(
        f"{a} {b}" for a, b in bigrams
        if a not in _STOPWORDS and b not in _STOPWORDS
        and a not in _bigram_noise and b not in _bigram_noise
        and len(a) >= 3 and len(b) >= 3
    )

    # Merge: take top single words + top bigrams
    top_words = [w for w, _ in freq.most_common(max_keywords)]
    top_bigrams = [bg for bg, c in bigram_freq.most_common(30) if c >= 2]

    # Start with explicit metadata
    parts = [finding_name]
    if category:
        parts.append(category)
    if guideline_source and not guideline_source.startswith('{'):
        parts.append(guideline_source)
    parts.append('incidental')

    # Add bigrams first (more specific), then singles
    seen = set()
    for term in top_bigrams + top_words:
        if term not in seen:
            seen.add(term)
            parts.append(term)
        if len(parts) >= max_keywords:
            break

    return ', '.join(parts)


def generate_if_calculator_html(finding_name, guideline_source='', category='',
                                 body_section='', additional_context='', user_id=None,
                                 model=None, overwrite=False, resources=None):
    """
    Generate an incidental finding calculator HTML page.

    Args:
        finding_name: Name of the incidental finding (e.g., "Pulmonary Nodule")
        guideline_source: Published guideline citation (plain text or JSON)
        category: Finding category (e.g., "pulmonary")
        body_section: Body section (e.g., "Thorax")
        additional_context: Extra context for generation
        user_id: ID of requesting user
        model: Claude model to use
        overwrite: Whether to overwrite existing calculator
        resources: Optional Gap 1 resources dict

    Returns:
        dict with success, message, and metadata
    """
    from models import db, IncidentalFindingCalculator

    slug = re.sub(r'[^a-z0-9]+', '-', finding_name.lower()).strip('-')

    existing = IncidentalFindingCalculator.query.filter_by(slug=slug).first()
    if existing and not overwrite:
        return {
            'success': False,
            'message': f'Radiology tool for "{finding_name}" already exists. Use overwrite=true to replace.',
            'slug': slug,
        }

    try:
        result = generate_clinical_tool(
            topic=finding_name,
            mode='full_tool',
            context={
                'tool_type': 'if',
                'category': category,
                'body_section': body_section,
                'guideline_source': guideline_source,
                'additional_context': additional_context,
            },
            resources=resources,
            model=model,
        )
    except GeneratorError as exc:
        return {'success': False, 'message': str(exc)}

    calculator_html = result['html']
    algorithm_html = result['algorithm_html']

    # Extract search keywords from generated content
    keywords = _extract_keywords_from_html(
        calculator_html,
        finding_name=finding_name,
        category=category,
        guideline_source=guideline_source,
    )

    if existing and overwrite:
        existing.finding_name = finding_name
        existing.body_section = body_section or None
        existing.category = category or None
        existing.keywords = keywords
        existing.calculator_html = calculator_html
        existing.algorithm_html = algorithm_html
        existing.guideline_source = guideline_source or None
        existing.generation_prompt = result['prompt']
        existing.generation_model = result['model']
        existing.generated_at = datetime.utcnow()
        existing.is_available = False
        existing.verified_at = None
        existing.verified_by_user_id = None
        existing.updated_at = datetime.utcnow()
        db.session.commit()
        calc_id = existing.id
    else:
        calculator = IncidentalFindingCalculator(
            slug=slug,
            finding_name=finding_name,
            body_section=body_section or None,
            category=category or None,
            keywords=keywords,
            calculator_html=calculator_html,
            algorithm_html=algorithm_html,
            guideline_source=guideline_source or None,
            is_available=False,
            generation_prompt=result['prompt'],
            generation_model=result['model'],
            generated_at=datetime.utcnow(),
            created_by_user_id=user_id,
        )
        db.session.add(calculator)
        db.session.commit()
        calc_id = calculator.id

    return {
        'success': True,
        'message': f'Radiology tool for "{finding_name}" generated. Awaiting admin review.',
        'slug': slug,
        'id': calc_id,
        'html_length': len(calculator_html),
        'validation_warnings': result['warnings'],
        'is_valid': result['is_valid'],
    }
