"""
Incidental Finding Calculator Generator — Thin Wrapper

Delegates to clinical_tool_generator.py for actual generation.
Handles IF-specific database operations (create/update IncidentalFindingCalculator).
"""

import re
import logging
from datetime import datetime

from clinical_tool_generator import generate_clinical_tool, GeneratorError

logger = logging.getLogger(__name__)


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

    if existing and overwrite:
        existing.finding_name = finding_name
        existing.body_section = body_section or None
        existing.category = category or None
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
            keywords=f"{finding_name}, {category}, {guideline_source}, incidental",
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
