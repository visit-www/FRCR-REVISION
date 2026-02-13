"""
Reporting Template Generator — Thin Wrapper

Delegates to clinical_tool_generator.py for actual generation.
Handles RT-specific database operations (create/update ReportingTemplate).
"""

import re
import logging
from datetime import datetime

from clinical_tool_generator import generate_clinical_tool, GeneratorError

logger = logging.getLogger(__name__)


def generate_reporting_template_html(title, category, body_section='', source_citation='',
                                      additional_context='', user_id=None, model=None,
                                      overwrite=False, resources=None):
    """
    Generate a reporting template HTML page.

    Args:
        title: Template title (e.g., "AAST Splenic Injury Scale")
        category: Category (e.g., "trauma", "grading", "emergency")
        body_section: Body section (e.g., "Abdomen")
        source_citation: Source guideline citation (plain text or JSON)
        additional_context: Extra context for generation
        user_id: ID of requesting user
        model: Claude model to use
        overwrite: Whether to overwrite existing
        resources: Optional Gap 1 resources dict

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

    try:
        result = generate_clinical_tool(
            topic=title,
            mode='full_tool',
            context={
                'tool_type': 'rt',
                'category': category,
                'body_section': body_section,
                'source_citation': source_citation,
                'additional_context': additional_context,
            },
            resources=resources,
            model=model,
        )
    except GeneratorError as exc:
        return {'success': False, 'message': str(exc)}

    template_html = result['html']
    algorithm_html = result['algorithm_html']

    if existing and overwrite:
        existing.title = title
        existing.category = category
        existing.body_section = body_section or None
        existing.template_html = template_html
        existing.algorithm_html = algorithm_html
        existing.source_citation = source_citation or None
        existing.generation_prompt = result['prompt']
        existing.generation_model = result['model']
        existing.generated_at = datetime.utcnow()
        existing.is_available = False
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
            is_available=False,
            generation_prompt=result['prompt'],
            generation_model=result['model'],
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
        'validation_warnings': result['warnings'],
        'is_valid': result['is_valid'],
    }
