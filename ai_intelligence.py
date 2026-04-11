"""
AI Intelligence Module

Haiku-powered processing for:
- ContentIntelligence: summaries, tags, cross-links for admin content
- UserGeneratedIntelligence: structured knowledge from Smart Reporter insights

Uses ai_client.call_claude() and parse_json_response() for API calls.
Model: claude-haiku-4-5-20251001 (~$0.0004/record)
"""

import json
import logging
from datetime import datetime

from ai_client import call_claude, parse_json_response, AIClientError

logger = logging.getLogger(__name__)

HAIKU_MODEL = 'claude-haiku-4-5-20251001'


# ==================== CONTENT INTELLIGENCE ====================

CI_SYSTEM_PROMPT = (
    "You are a radiology consultant creating structured metadata for a "
    "search and discovery system used by radiology trainees. "
    "Your output will power search results — be accurate and concise."
)

CI_USER_PROMPT = """Analyse this radiology content and produce structured metadata.

Content type: {content_type}
Title: {title}
Body section: {body_section}
Content:
{content_text}

Return a JSON object with:
{{
  "summary": "2-sentence summary (max 200 chars). Focus on what this content helps with.",
  "search_tags": "comma,separated,keywords (max 15 tags, include synonyms and abbreviations)",
  "cross_links": [
    {{"type": "content_type", "title_hint": "keyword to match related content", "relevance": "why linked"}}
  ]
}}

Rules:
- summary: Must be useful as a search result preview. Plain English, no jargon overload.
- search_tags: Include common abbreviations (e.g. PE for pulmonary embolism), related anatomy, modalities, and clinical scenarios.
- cross_links: Suggest 2-5 related content items using title keywords that could match other items in the database. Types: case, protocol, reporting_algorithm, radiology_template, radiology_tool, radiology_pearl, anatomy_snippet.

Return ONLY the JSON object, no markdown fences."""


def process_content_intelligence(content_type, content_id, title, body_section, content_text):
    """Process a content item into ContentIntelligence metadata via Haiku.

    Returns dict with keys: summary, search_tags, cross_links_json, processing_model, processing_tokens
    Raises AIClientError on failure.
    """
    truncated_text = (content_text or '')[:2000]

    prompt = CI_USER_PROMPT.format(
        content_type=content_type,
        title=title or 'Untitled',
        body_section=body_section or 'Unknown',
        content_text=truncated_text,
    )

    response_text, model_used, token_count = call_claude(
        system_prompt=CI_SYSTEM_PROMPT,
        user_prompt=prompt,
        model=HAIKU_MODEL,
        max_tokens=800,
        temperature=0.2,
        timeout=30,
    )

    result = parse_json_response(response_text)
    if not result or not result.get('summary'):
        raise AIClientError(f"Invalid CI response for {content_type}:{content_id}")

    cross_links = result.get('cross_links', [])

    return {
        'summary': result['summary'][:200],
        'search_tags': result.get('search_tags', ''),
        'cross_links_json': json.dumps(cross_links) if cross_links else None,
        'processing_model': model_used,
        'processing_tokens': token_count,
    }


def _build_url(ctype, match):
    """Build a frontend URL for a resolved cross-link match."""
    TYPE_URL_MAP = {
        'case': lambda m: f'/view-case/{m.id}',
        'protocol': lambda m: f'/radiology-protocols/view/{m.id}',
        'reporting_algorithm': lambda m: f'/reporting-template/{m.slug}',
        'radiology_template': lambda m: f'/radiology-template/view/{m.id}',
        'radiology_tool': lambda m: f'/incidental-findings/{m.slug}',
        'radiology_pearl': lambda m: '/radiology-pearls',
        'anatomy_snippet': lambda m: f'/anatomy-snippets/{m.slug}',
    }
    try:
        return TYPE_URL_MAP[ctype](match)
    except Exception:
        return None


def resolve_cross_links(cross_link_hints):
    """Resolve title_hint strings to actual content IDs via ILIKE search.

    Args:
        cross_link_hints: list of {type, title_hint, relevance}

    Returns:
        list of {type, id, title, url, relevance} with resolved IDs
    """
    if not cross_link_hints:
        return []

    from models import (
        db, Case, CaseStatus, ClinicalProtocol, ReportingAlgorithm,
        RadiologyTemplate, IncidentalFindingCalculator, RadiologyPearl,
    )

    resolved = []
    TYPE_MODEL_MAP = {
        'case': (Case, 'diagnosis', lambda c: c.id),
        'protocol': (ClinicalProtocol, 'title', lambda c: c.id),
        'reporting_algorithm': (ReportingAlgorithm, 'title', lambda c: c.id),
        'radiology_template': (RadiologyTemplate, 'title', lambda c: c.id),
        'radiology_tool': (IncidentalFindingCalculator, 'finding_name', lambda c: c.id),
        'radiology_pearl': (RadiologyPearl, 'pearl_text', lambda c: c.id),
        'anatomy_snippet': (ReportingAlgorithm, 'title', lambda c: c.id),
    }

    for hint in cross_link_hints:
        ctype = hint.get('type', '')
        title_hint = hint.get('title_hint', '')
        if not ctype or not title_hint or ctype not in TYPE_MODEL_MAP:
            continue

        model_cls, title_field, id_fn = TYPE_MODEL_MAP[ctype]
        try:
            field = getattr(model_cls, title_field)
            match = model_cls.query.filter(field.ilike(f'%{title_hint}%')).first()
            if match:
                url = _build_url(ctype, match)
                resolved.append({
                    'type': ctype,
                    'id': id_fn(match),
                    'title': getattr(match, title_field, '')[:100],
                    'url': url,
                    'relevance': hint.get('relevance', ''),
                })
        except Exception:
            continue

    return resolved


# ==================== USER GENERATED INTELLIGENCE ====================

UGI_SYSTEM_PROMPT = (
    "You are a radiology consultant and radiology teacher. "
    "Process these clinical insights as if you are writing notes from your daily "
    "case reporting for future reference. "
    "Discard case-specific information (patient age, specific measurements from one case). "
    "Keep only reusable, generalizable knowledge that would help a trainee."
)

UGI_USER_PROMPT = """Process these Smart Reporter insights into structured clinical knowledge.

Modality: {modality}
Body section: {body_section}
Exam type: {exam_type}

Teaching point:
{teaching_point}

Differentials discussed:
{differentials}

Return a JSON object:
{{
  "diagnosis": "Primary condition discussed (short name, max 100 chars)",
  "notes": ["Practical bullet 1 — what to look for or report", "Practical bullet 2"],
  "pitfalls": ["What to watch out for — common mistake or mimic"],
  "enriched_differentials": [
    {{"name": "Differential name", "distinguishing_features": "Key imaging clue in 1 sentence"}}
  ],
  "search_tags": "comma,separated,keywords (max 10 tags, include abbreviations)"
}}

Rules:
- notes: 2-5 bullets. Each must be actionable at the workstation. No textbook filler.
- pitfalls: 1-3 bullets. Focus on common reporting errors or diagnostic traps.
- enriched_differentials: Only include differentials where you can add a useful distinguishing feature. Max 5.
- search_tags: Include the diagnosis, body region, modality, and common search terms a trainee would use.

Return ONLY the JSON object, no markdown fences."""


def process_ugi(raw_teaching_point, raw_differentials, modality, body_section, exam_type):
    """Process raw teaching point + differentials into structured UGI via Haiku.

    Returns dict with keys: diagnosis, notes, pitfalls, enriched_differentials, search_tags,
                            processing_model, processing_tokens
    Raises AIClientError on failure.
    """
    differentials_text = ''
    if raw_differentials:
        if isinstance(raw_differentials, str):
            try:
                diffs = json.loads(raw_differentials)
            except (json.JSONDecodeError, TypeError):
                diffs = [raw_differentials]
        else:
            diffs = raw_differentials
        differentials_text = '\n'.join(f'- {d}' for d in diffs if d)

    prompt = UGI_USER_PROMPT.format(
        modality=modality or 'Unknown',
        body_section=body_section or 'Unknown',
        exam_type=exam_type or 'Unknown',
        teaching_point=raw_teaching_point,
        differentials=differentials_text or 'None provided',
    )

    response_text, model_used, token_count = call_claude(
        system_prompt=UGI_SYSTEM_PROMPT,
        user_prompt=prompt,
        model=HAIKU_MODEL,
        max_tokens=1000,
        temperature=0.2,
        timeout=30,
    )

    result = parse_json_response(response_text)
    if not result or not result.get('diagnosis'):
        raise AIClientError("Invalid UGI response — missing diagnosis")

    return {
        'diagnosis': result['diagnosis'][:300],
        'notes': json.dumps(result.get('notes', [])),
        'pitfalls': json.dumps(result.get('pitfalls', [])),
        'enriched_differentials': json.dumps(result.get('enriched_differentials', [])),
        'search_tags': result.get('search_tags', ''),
        'processing_model': model_used,
        'processing_tokens': token_count,
    }


def process_ugi_for_record(ugi_id):
    """Process a pending UGI record through Haiku, updating DB status.

    Returns True on success, False on failure.
    """
    from models import db, UserGeneratedIntelligence

    ugi = UserGeneratedIntelligence.query.get(ugi_id)
    if not ugi:
        logger.warning(f"UGI record {ugi_id} not found")
        return False

    if ugi.processing_status not in ('pending', 'failed'):
        logger.info(f"UGI record {ugi_id} already {ugi.processing_status}, skipping")
        return False

    try:
        result = process_ugi(
            raw_teaching_point=ugi.raw_teaching_point,
            raw_differentials=ugi.raw_differentials,
            modality=ugi.modality,
            body_section=ugi.body_section,
            exam_type=ugi.exam_type,
        )

        ugi.diagnosis = result['diagnosis']
        ugi.notes = result['notes']
        ugi.pitfalls = result['pitfalls']
        ugi.enriched_differentials = result['enriched_differentials']
        ugi.search_tags = result['search_tags']
        ugi.processing_model = result['processing_model']
        ugi.processing_tokens = result['processing_tokens']
        ugi.processed_at = datetime.utcnow()
        ugi.processing_status = 'processed'
        ugi.updated_at = datetime.utcnow()

        db.session.commit()
        logger.info(f"UGI record {ugi_id} processed successfully: {ugi.diagnosis}")

        # Track cost as admin overhead (admin triggers processing, not the user)
        try:
            from flask_login import current_user as _cu
            _admin_id = _cu.id if hasattr(_cu, 'id') and _cu.is_authenticated else 0
        except Exception:
            _admin_id = 0
        try:
            from ai_cost_tracker import track_ai_call
            track_ai_call(_admin_id, 'user_intelligence',
                          model=result.get('processing_model', ''),
                          output_tokens=result.get('processing_tokens'),
                          input_summary=f"UGI #{ugi_id}: {ugi.diagnosis[:100]}")
        except Exception:
            pass

        return True

    except Exception as exc:
        db.session.rollback()
        try:
            ugi.processing_status = 'failed'
            ugi.updated_at = datetime.utcnow()
            db.session.commit()
        except Exception:
            db.session.rollback()
        logger.error(f"UGI record {ugi_id} processing failed: {exc}")
        return False
