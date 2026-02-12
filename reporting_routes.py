"""
Reporting & Algorithm Finder Routes

Flask blueprint for:
- Unified Algorithm Finder (search across existing cases + oncologic calculators + IF calculators)
- Case-based algorithmic approach: if a matching case exists, show its discussion;
  if not, generate via case_prelim_data, auto-create DRAFT case, email superadmin
- Non-oncologic reporting templates (Layer B: admin-curated trauma, grading, emergency)
- Admin management of reporting templates
"""

from flask import Blueprint, request, render_template, jsonify, url_for
from flask_login import login_required, current_user
from datetime import datetime
import json
import os
import re
import logging

from models import (
    db, Case, CaseStatus, Question, Answer, CaseApprovalQueue,
    ReportingTemplate, TNMCalculatorContent, ClinicalProtocol,
    IncidentalFindingCalculator, AJCCDiseaseSite, AJCCBodySection,
    User, AiPrelimCaseData, ReportingSession, PublishedReport,
)
from access_control import require_admin

logger = logging.getLogger(__name__)

reporting_bp = Blueprint('reporting', __name__)


# ==================== ALGORITHM FINDER (Unified Search) ====================

@reporting_bp.route('/algorithm-finder')
@login_required
def algorithm_finder():
    """Redirect to Smart Reporter — Algorithm Finder is now superseded."""
    from flask import redirect
    return redirect('/smart-reporter', code=302)


@reporting_bp.route('/api/algorithms/search')
@login_required
def unified_search():
    """
    Unified search across all algorithm types using pg_trgm.
    Returns results grouped by type: case, oncologic, incidental, reporting.
    Cases with published discussions are the PRIMARY source.
    """
    query = request.args.get('q', '').strip()
    filter_type = request.args.get('type', '')
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 50)

    if len(query) < 2:
        return jsonify({'results': [], 'query': query})

    results = []

    try:
        from sqlalchemy import text

        # Search existing PUBLISHED cases by diagnosis (PRIMARY source)
        if filter_type in ('', 'case'):
            case_sql = text("""
                SELECT c.id, c.case_number, c.diagnosis, c.status,
                       c.module, c.body_part,
                       GREATEST(
                           similarity(lower(c.diagnosis), lower(:query)),
                           similarity(
                               regexp_replace(lower(c.diagnosis), '^(right|left|bilateral|rt|lt|bilat)\\s+', ''),
                               lower(:query)
                           )
                       ) AS sim
                FROM "case" c
                WHERE c.status = 'published'
                  AND c.discussion IS NOT NULL
                  AND c.discussion != ''
                  AND (
                      similarity(lower(c.diagnosis), lower(:query)) > 0.1
                      OR c.diagnosis ILIKE :like_query
                  )
                ORDER BY sim DESC
                LIMIT :limit
            """)
            case_results = db.session.execute(case_sql, {
                'query': query, 'like_query': f'%{query}%', 'limit': limit
            }).fetchall()

            for r in case_results:
                bp_val = r.body_part.value if hasattr(r.body_part, 'value') else str(r.body_part) if r.body_part else None
                results.append({
                    'type': 'case',
                    'id': r.id,
                    'title': r.diagnosis,
                    'body_section': bp_val,
                    'description': f'Case {r.case_number}' if r.case_number else 'Published case',
                    'subtitle': 'Algorithmic Approach Available',
                    'url': f'/view-case/{r.id}',
                    'case_id': r.id,
                    'similarity': float(r.sim) if r.sim else 0,
                })

        # Search oncologic (TNM calculators)
        if filter_type in ('', 'oncologic'):
            onc_sql = text("""
                SELECT tc.id, tc.slug, tc.cancer_name, tc.body_section, tc.description,
                       tc.staging_system,
                       similarity(tc.cancer_name, :query) AS sim
                FROM tnm_calculator_content tc
                WHERE tc.is_available = TRUE
                  AND (
                      similarity(tc.cancer_name, :query) > 0.1
                      OR tc.cancer_name ILIKE :like_query
                  )
                ORDER BY sim DESC
                LIMIT :limit
            """)
            onc_results = db.session.execute(onc_sql, {
                'query': query, 'like_query': f'%{query}%', 'limit': limit
            }).fetchall()

            for r in onc_results:
                results.append({
                    'type': 'oncologic',
                    'id': r.id,
                    'slug': r.slug,
                    'title': r.cancer_name,
                    'body_section': r.body_section,
                    'description': r.description,
                    'subtitle': r.staging_system or 'AJCC 9th Edition',
                    'url': f'/tnm-calculator/{r.slug}',
                    'similarity': float(r.sim) if r.sim else 0,
                })

        # Search incidental findings calculators
        if filter_type in ('', 'incidental'):
            if_sql = text("""
                SELECT ifc.id, ifc.slug, ifc.finding_name, ifc.category, ifc.body_section,
                       ifc.description, ifc.guideline_source,
                       GREATEST(
                           similarity(ifc.finding_name, :query),
                           COALESCE(similarity(ifc.keywords, :query), 0)
                       ) AS sim
                FROM incidental_finding_calculator ifc
                WHERE ifc.is_available = TRUE
                  AND (
                      similarity(ifc.finding_name, :query) > 0.1
                      OR similarity(ifc.keywords, :query) > 0.1
                      OR ifc.finding_name ILIKE :like_query
                      OR ifc.keywords ILIKE :like_query
                  )
                ORDER BY sim DESC
                LIMIT :limit
            """)
            if_results = db.session.execute(if_sql, {
                'query': query, 'like_query': f'%{query}%', 'limit': limit
            }).fetchall()

            for r in if_results:
                results.append({
                    'type': 'incidental',
                    'id': r.id,
                    'slug': r.slug,
                    'title': r.finding_name,
                    'body_section': r.body_section,
                    'description': r.description,
                    'subtitle': r.guideline_source or r.category,
                    'url': f'/incidental-findings/{r.slug}',
                    'similarity': float(r.sim) if r.sim else 0,
                })

        # Search reporting templates (admin-curated + AI-generated cached)
        if filter_type in ('', 'reporting'):
            rt_sql = text("""
                SELECT rt.id, rt.slug, rt.title, rt.category, rt.body_section,
                       rt.description, rt.source_citation,
                       COALESCE(rt.is_ai_generated, FALSE) AS is_ai_generated,
                       GREATEST(
                           similarity(rt.title, :query),
                           COALESCE(similarity(rt.keywords, :query), 0)
                       ) AS sim
                FROM reporting_template rt
                WHERE rt.is_available = TRUE
                  AND (
                      similarity(rt.title, :query) > 0.1
                      OR similarity(rt.keywords, :query) > 0.1
                      OR rt.title ILIKE :like_query
                      OR rt.keywords ILIKE :like_query
                  )
                ORDER BY sim DESC
                LIMIT :limit
            """)
            rt_results = db.session.execute(rt_sql, {
                'query': query, 'like_query': f'%{query}%', 'limit': limit
            }).fetchall()

            for r in rt_results:
                results.append({
                    'type': 'reporting',
                    'id': r.id,
                    'slug': r.slug,
                    'title': r.title,
                    'body_section': r.body_section,
                    'description': r.description,
                    'subtitle': r.source_citation or r.category,
                    'url': f'/reporting-template/{r.slug}',
                    'similarity': float(r.sim) if r.sim else 0,
                    'is_ai_generated': bool(r.is_ai_generated),
                })

    except Exception as exc:
        logger.warning(f"pg_trgm unified search failed, falling back to ILIKE: {exc}")
        results = _fallback_search(query, filter_type, limit)

    # Sort all results by similarity descending
    results.sort(key=lambda r: r.get('similarity', 0), reverse=True)

    return jsonify({
        'results': results[:limit],
        'query': query,
        'total': len(results),
    })


def _fallback_search(query, filter_type, limit):
    """Fallback ILIKE search for SQLite compatibility."""
    results = []
    like = f'%{query}%'

    if filter_type in ('', 'case'):
        cases = Case.query.filter(
            Case.status == CaseStatus.PUBLISHED,
            Case.discussion.isnot(None),
            Case.discussion != '',
            Case.diagnosis.ilike(like),
        ).limit(limit).all()
        for c in cases:
            results.append({
                'type': 'case', 'id': c.id,
                'title': c.diagnosis,
                'body_section': c.body_part.value if c.body_part else None,
                'description': f'Case {c.case_number}' if c.case_number else 'Published case',
                'subtitle': 'Algorithmic Approach Available',
                'url': f'/view-case/{c.id}',
                'case_id': c.id,
                'similarity': 0.5,
            })

    if filter_type in ('', 'oncologic'):
        calcs = TNMCalculatorContent.query.filter(
            TNMCalculatorContent.is_available == True,
            TNMCalculatorContent.cancer_name.ilike(like),
        ).limit(limit).all()
        for c in calcs:
            results.append({
                'type': 'oncologic', 'id': c.id, 'slug': c.slug,
                'title': c.cancer_name, 'body_section': c.body_section,
                'description': c.description,
                'subtitle': c.staging_system or 'AJCC 9th Edition',
                'url': f'/tnm-calculator/{c.slug}',
                'similarity': 0.5,
            })

    if filter_type in ('', 'incidental'):
        ifs = IncidentalFindingCalculator.query.filter(
            IncidentalFindingCalculator.is_available == True,
            db.or_(
                IncidentalFindingCalculator.finding_name.ilike(like),
                IncidentalFindingCalculator.keywords.ilike(like),
            ),
        ).limit(limit).all()
        for f in ifs:
            results.append({
                'type': 'incidental', 'id': f.id, 'slug': f.slug,
                'title': f.finding_name, 'body_section': f.body_section,
                'description': f.description,
                'subtitle': f.guideline_source or f.category,
                'url': f'/incidental-findings/{f.slug}',
                'similarity': 0.5,
            })

    if filter_type in ('', 'reporting'):
        templates = ReportingTemplate.query.filter(
            ReportingTemplate.is_available == True,
            db.or_(
                ReportingTemplate.title.ilike(like),
                ReportingTemplate.keywords.ilike(like),
            ),
        ).limit(limit).all()
        for t in templates:
            results.append({
                'type': 'reporting', 'id': t.id, 'slug': t.slug,
                'title': t.title, 'body_section': t.body_section,
                'description': t.description,
                'subtitle': t.source_citation or t.category,
                'url': f'/reporting-template/{t.slug}',
                'similarity': 0.5,
            })

    return results


# ==================== CASE-BASED ALGORITHMIC APPROACH GENERATION ====================

@reporting_bp.route('/api/algorithms/generate', methods=['POST'])
@login_required
def generate_algorithmic_approach():
    """
    Generate an algorithmic approach for a diagnosis that has no existing case.

    Flow:
    1. Receive diagnosis query from radiologist
    2. Create a new Case in DRAFT status with that diagnosis
    3. Call generate_prelim_case_data() (same as suggest-case) to generate discussion + Q&A
    4. Apply generated content to the case
    5. Add to CaseApprovalQueue and email superadmin
    6. Return the generated discussion HTML immediately to the radiologist

    This enriches the case library with every new query.
    """
    # DEPRECATED (Feb 2026): Use /api/smart-reporter/generate-tree instead.
    # Kept for backward compatibility — generates ReportingTemplate cache entries.
    logger.info(f"[DEPRECATED] /api/algorithms/generate called by user {current_user.id}. "
                "Consider using /api/smart-reporter/generate-tree instead.")

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    diagnosis = (data.get('diagnosis') or '').strip()
    if not diagnosis:
        return jsonify({'error': 'Diagnosis is required.'}), 400

    if len(diagnosis) > 500:
        return jsonify({'error': 'Diagnosis too long (max 500 characters).'}), 400

    # Optional metadata from the radiologist
    body_section = (data.get('body_section') or '').strip()
    notes = (data.get('notes') or '').strip()

    # Rate limit: max 10 algorithm-generated DRAFT cases per user
    draft_count = Case.query.filter_by(
        created_by_user_id=current_user.id,
        status=CaseStatus.DRAFT,
    ).count()
    if draft_count >= 10:
        return jsonify({
            'error': 'You have too many draft cases pending review. '
                     'Please wait for admin review before generating more.'
        }), 429

    # Step 1: Map body_section to BodyPart enum if provided
    body_part_enum = None
    module_enum = None
    if body_section:
        body_part_enum = _map_body_section_to_enum(body_section)
        module_enum = _map_body_section_to_module(body_section)

    # Step 2: Auto-generate case_number
    case_number = _generate_case_number(body_part_enum)

    # Step 3: Create DRAFT case
    try:
        case = Case(
            case_number=case_number,
            diagnosis=diagnosis,
            module=module_enum,
            body_part=body_part_enum,
            status=CaseStatus.DRAFT,
            is_public=False,
            created_by_user_id=current_user.id,
            contributor_name=current_user.full_name,
            contributor_notes=f"Auto-generated via Algorithm Finder. Query: {diagnosis}" + (
                f"\nBody section: {body_section}" if body_section else ""
            ) + (
                f"\nNotes: {notes}" if notes else ""
            ),
        )
        db.session.add(case)
        db.session.flush()  # Get case.id without committing yet
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to create draft case: {exc}")
        return jsonify({'error': f'Failed to create case: {exc}'}), 500

    # Step 4: Try new algorithmic reporter first, fallback to ai_prelim
    algorithmic_result = None
    used_new_reporter = False

    try:
        from ai_algorithmic_reporter import generate_algorithmic_report, AlgorithmicReporterError
        algorithmic_result = generate_algorithmic_report(
            diagnosis=diagnosis,
            body_section=body_section,
            notes=notes,
        )
        used_new_reporter = True
        logger.info(f"Algorithmic reporter succeeded for: {diagnosis}")
    except Exception as exc:
        logger.warning(f"Algorithmic reporter failed, falling back to ai_prelim: {exc}")

    if used_new_reporter and algorithmic_result:
        # New reporter path: use algorithmic_approach_html as discussion
        discussion_html = algorithmic_result.get('algorithmic_approach_html', '')
        case.discussion = discussion_html
        added_pairs = []  # New reporter doesn't generate Q&A pairs
        provider = algorithmic_result.get('provider', 'claude')
        model_name = algorithmic_result.get('model', '')

        # Save audit trail
        audit = AiPrelimCaseData(
            case_id=case.id,
            created_by_user_id=current_user.id,
            provider=provider,
            model_name=model_name,
            prompt_version='algorithmic_reporter_v1',
            request_payload=json.dumps({'diagnosis': diagnosis, 'body_section': body_section, 'notes': notes}),
            response_payload=json.dumps({
                'algorithmic_approach_html': discussion_html,
                'pacs_report': algorithmic_result.get('pacs_report', ''),
                'differential_diagnosis': algorithmic_result.get('differential_diagnosis', []),
                'recommendations': algorithmic_result.get('recommendations', []),
            }),
        )
        db.session.add(audit)

        # Cache as ReportingTemplate
        _create_reporting_template_from_algorithm(
            diagnosis=diagnosis,
            body_section=body_section,
            algorithmic_result=algorithmic_result,
            user_id=current_user.id,
        )

    else:
        # Fallback path: use ai_prelim (educational content)
        from ai_prelim import generate_prelim_case_data, AiPrelimError

        context = {
            'diagnosis': diagnosis,
            'module': module_enum.name if module_enum else '',
            'body_part': body_part_enum.name if body_part_enum else '',
            'notes': notes,
            'existing_summary': '',
            'sources': [
                'https://radiologyassistant.nl',
                'https://radiopaedia.org',
                'https://www.nice.org.uk',
            ],
        }

        try:
            result = generate_prelim_case_data(context, provider='claude')
        except AiPrelimError as exc:
            db.session.rollback()
            return jsonify({'error': f'AI generation failed: {exc}'}), 400
        except Exception as exc:
            db.session.rollback()
            logger.error(f"AI generation error: {exc}")
            return jsonify({'error': f'AI generation failed: {exc}'}), 500

        output = result.get('output', {})
        added_pairs = _apply_qa_pairs(case, output)
        discussion_html = _apply_discussion(case, output, result.get('provider', 'claude'), result.get('model', ''))
        provider = result.get('provider', 'claude')
        model_name = result.get('model', '')

        audit = AiPrelimCaseData(
            case_id=case.id,
            created_by_user_id=current_user.id,
            provider=provider,
            model_name=model_name,
            prompt_version=result.get('prompt_version', 'v1'),
            request_payload=json.dumps(context),
            response_payload=json.dumps(result),
        )
        db.session.add(audit)
        algorithmic_result = None

    # Step 7: Add to approval queue
    queue_entry = CaseApprovalQueue(
        case_id=case.id,
        submitted_by_user_id=current_user.id,
    )
    db.session.add(queue_entry)

    # Update status to PENDING_REVIEW so admin sees it
    case.status = CaseStatus.PENDING_REVIEW

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to save generated case: {exc}")
        return jsonify({'error': f'Failed to save: {exc}'}), 500

    # Step 8: Email superadmin (best effort — don't fail if email fails)
    try:
        from auth import send_case_review_notification
        send_case_review_notification(case, current_user)
    except Exception as exc:
        logger.warning(f"Email notification failed for algorithm case {case.id}: {exc}")

    # Step 9: Return the generated content immediately
    response_data = {
        'success': True,
        'case_id': case.id,
        'case_number': case.case_number,
        'diagnosis': diagnosis,
        'discussion_html': discussion_html or '',
        'qa_pairs': added_pairs if not used_new_reporter else [],
        'qa_count': len(added_pairs) if not used_new_reporter else 0,
        'warnings': (algorithmic_result or {}).get('warnings', []),
        'safety_checklist': [],
        'sources': (algorithmic_result or {}).get('sources', []),
        'provider': provider,
        'model': model_name,
        'message': 'Algorithmic approach generated. Case created and submitted for admin review.',
        'case_url': f'/view-case/{case.id}',
        'used_new_reporter': used_new_reporter,
    }

    # Enrich with new reporter data if available
    if used_new_reporter and algorithmic_result:
        response_data['pacs_report'] = algorithmic_result.get('pacs_report', '')
        response_data['differential_diagnosis'] = algorithmic_result.get('differential_diagnosis', [])
        response_data['recommendations'] = algorithmic_result.get('recommendations', [])
        response_data['key_findings_checklist'] = algorithmic_result.get('key_findings_checklist', [])
        response_data['pitfalls'] = algorithmic_result.get('pitfalls', [])

    return jsonify(response_data)


def _apply_qa_pairs(case, output):
    """Create Question/Answer records from AI output. Mirrors app.py _apply_qa_pairs_from_output."""
    next_q = 1
    next_a = 1
    added = []

    for pair in output.get('qa_pairs', []) or []:
        q_text = (pair.get('question') or '').strip()
        a_text = (pair.get('answer') or '').strip()
        if not q_text and not a_text:
            continue

        if q_text:
            q_text = f'<div data-ai-generated="true" class="ai-generated-wrapper">{q_text}</div>'
            db.session.add(Question(case_id=case.id, question_number=next_q, question_text=q_text))
            next_q += 1
        if a_text:
            a_text = f'<div data-ai-generated="true" class="ai-generated-wrapper">{a_text}</div>'
            db.session.add(Answer(case_id=case.id, answer_number=next_a, answer_text=a_text))
            next_a += 1
        added.append({'question': q_text, 'answer': a_text})
    return added


def _apply_discussion(case, output, provider, model_name):
    """Build discussion HTML and apply to case. Mirrors app.py _apply_discussion_from_output."""
    discussion = output.get('discussion', '')
    if not discussion:
        return ''

    # Build attribution footer
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    contributor_line = ''
    if current_user and current_user.full_name:
        contributor_line = f'with inputs from <strong>{current_user.full_name}</strong> '

    attribution = (
        f'<p style="font-size: 0.82em; color: #8b94a3; font-style: italic; margin: 4px 0 0 0;">'
        f'Generated {contributor_line}by RadInsights Intelligence on {timestamp}</p>'
    )

    footer = f'''<!-- Footer -->
<div style="background: #f3f4f6; padding: 12px 16px; border-top: 1px solid #e5e7eb; margin-top: 20px; border-radius: 0 0 8px 8px;">
    {attribution}
    <div style="display: flex; align-items: center; justify-content: flex-end; gap: 8px; margin-top: 6px;">
        <img style="width: 30px; height: 30px; object-fit: contain;" src="https://res.cloudinary.com/dx7b7chvn/image/upload/v1769503548/frcr-rev-logo-transp_o2hmrq.png" alt="RadiologyInsights Logo">
        <span style="font-size: 0.85em; color: #6b7280;">&copy; All rights reserved RadiologyInsights</span>
    </div>
</div>'''

    case.discussion = f"{discussion}{footer}"
    return discussion


def _map_body_section_to_enum(body_section):
    """Best-effort mapping from a body section string to BodyPart enum."""
    from models import BodyPart

    section_lower = body_section.lower()
    mappings = {
        'head': BodyPart.HEAD_NECK,
        'neck': BodyPart.HEAD_NECK,
        'brain': BodyPart.BRAIN_PITUITARY,
        'spine': BodyPart.SPINE,
        'thorax': BodyPart.LUNG_MEDIASTINUM,
        'chest': BodyPart.LUNG_MEDIASTINUM,
        'lung': BodyPart.LUNG_MEDIASTINUM,
        'cardiac': BodyPart.CARDIOVASCULAR,
        'heart': BodyPart.CARDIOVASCULAR,
        'vascular': BodyPart.CARDIOVASCULAR,
        'abdomen': BodyPart.GASTROINTESTINAL,
        'liver': BodyPart.HEPATOPANCREATICOBILIARY,
        'pancreas': BodyPart.HEPATOPANCREATICOBILIARY,
        'biliary': BodyPart.HEPATOPANCREATICOBILIARY,
        'renal': BodyPart.KUB,
        'kidney': BodyPart.KUB,
        'urinary': BodyPart.KUB,
        'adrenal': BodyPart.ADRENAL,
        'pelvis': BodyPart.GYNAECOLOGY,
        'breast': BodyPart.BREAST,
        'thyroid': BodyPart.THYROID_PARATHYROID,
        'msk': BodyPart.BONES,
        'musculoskeletal': BodyPart.BONES,
        'bone': BodyPart.BONES,
        'soft tissue': BodyPart.SOFT_TISSUE,
        'paediatric': BodyPart.MULTISYSTEM,
        'pediatric': BodyPart.MULTISYSTEM,
        'trauma': BodyPart.MULTISYSTEM,
    }

    for key, val in mappings.items():
        if key in section_lower:
            return val
    return None


def _map_body_section_to_module(body_section):
    """Best-effort mapping from a body section string to FRCRModule enum."""
    from models import FRCRModule

    section_lower = body_section.lower()
    mappings = {
        'head': FRCRModule.CNS_HEAD_NECK,
        'neck': FRCRModule.CNS_HEAD_NECK,
        'brain': FRCRModule.CNS_HEAD_NECK,
        'spine': FRCRModule.CNS_HEAD_NECK,
        'thorax': FRCRModule.CARDIOTHORACIC_VASCULAR,
        'chest': FRCRModule.CARDIOTHORACIC_VASCULAR,
        'lung': FRCRModule.CARDIOTHORACIC_VASCULAR,
        'cardiac': FRCRModule.CARDIOTHORACIC_VASCULAR,
        'heart': FRCRModule.CARDIOTHORACIC_VASCULAR,
        'vascular': FRCRModule.CARDIOTHORACIC_VASCULAR,
        'abdomen': FRCRModule.GASTROINTESTINAL,
        'liver': FRCRModule.GASTROINTESTINAL,
        'pancreas': FRCRModule.GASTROINTESTINAL,
        'biliary': FRCRModule.GASTROINTESTINAL,
        'gi': FRCRModule.GASTROINTESTINAL,
        'renal': FRCRModule.GENITOURINARY_BREAST,
        'kidney': FRCRModule.GENITOURINARY_BREAST,
        'urinary': FRCRModule.GENITOURINARY_BREAST,
        'adrenal': FRCRModule.GENITOURINARY_BREAST,
        'pelvis': FRCRModule.GENITOURINARY_BREAST,
        'breast': FRCRModule.GENITOURINARY_BREAST,
        'msk': FRCRModule.MUSCULOSKELETAL_TRAUMA,
        'musculoskeletal': FRCRModule.MUSCULOSKELETAL_TRAUMA,
        'bone': FRCRModule.MUSCULOSKELETAL_TRAUMA,
        'trauma': FRCRModule.MUSCULOSKELETAL_TRAUMA,
        'paediatric': FRCRModule.PAEDIATRIC,
        'pediatric': FRCRModule.PAEDIATRIC,
    }

    for key, val in mappings.items():
        if key in section_lower:
            return val
    return None


def _generate_case_number(body_part_enum):
    """Auto-generate a case number in the same format as suggest-case."""
    if body_part_enum:
        short_code = body_part_enum.name.replace('_', '').upper()[:6]
    else:
        short_code = 'ALGO'
    prefix = f"{short_code}-"

    existing = Case.query.filter(
        Case.case_number.ilike(f"{prefix}%")
    ).all()
    max_num = 0
    for c in existing:
        if c.case_number:
            match = re.search(r'-(\d+)$', c.case_number)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
    return f"{prefix}{max_num + 1:03d}"


def _create_reporting_template_from_algorithm(diagnosis, body_section, algorithmic_result, user_id):
    """
    Cache an AI-generated algorithm as a ReportingTemplate for instant future search hits.
    If a template with the same slug already exists, skip (no overwrite).
    """
    slug = re.sub(r'[^a-z0-9]+', '-', diagnosis.lower()).strip('-')
    if not slug:
        return None

    existing = ReportingTemplate.query.filter_by(slug=slug).first()
    if existing:
        logger.info(f"ReportingTemplate slug '{slug}' already exists, skipping cache creation.")
        return None

    # Build keywords from diagnosis + differentials
    keywords_parts = [diagnosis]
    for d in algorithmic_result.get('differential_diagnosis', []):
        if isinstance(d, dict) and d.get('diagnosis'):
            keywords_parts.append(d['diagnosis'])
    # Add suggested keywords from AI
    keywords_parts.extend(algorithmic_result.get('suggested_keywords', []))
    keywords = ', '.join(dict.fromkeys(keywords_parts))  # dedupe preserving order

    template = ReportingTemplate(
        slug=slug,
        title=diagnosis,
        category='ai_generated',
        body_section=body_section or None,
        description=f'AI-generated reporting algorithm for {diagnosis}',
        keywords=keywords,
        algorithm_html=algorithmic_result.get('algorithmic_approach_html', ''),
        pacs_report_text=algorithmic_result.get('pacs_report', ''),
        source_citation='AI-generated — verify against published guidelines',
        is_available=True,
        is_ai_generated=True,
        generation_model=algorithmic_result.get('model', ''),
        generated_at=datetime.utcnow(),
        created_by_user_id=user_id,
    )

    db.session.add(template)
    logger.info(f"Cached ReportingTemplate '{slug}' from algorithm generation.")
    return template


@reporting_bp.route('/api/algorithms/browse')
@login_required
def browse_algorithms():
    """Browse all available algorithms grouped by body section."""
    # Published cases with discussions
    cases = Case.query.filter(
        Case.status == CaseStatus.PUBLISHED,
        Case.discussion.isnot(None),
        Case.discussion != '',
    ).order_by(Case.body_part, Case.diagnosis).all()

    oncologic = TNMCalculatorContent.query.filter_by(
        is_available=True
    ).order_by(TNMCalculatorContent.body_section, TNMCalculatorContent.cancer_name).all()

    ifs = IncidentalFindingCalculator.query.filter_by(
        is_available=True
    ).order_by(IncidentalFindingCalculator.category, IncidentalFindingCalculator.finding_name).all()

    grouped = {}

    for c in cases:
        section = c.body_part.value if c.body_part else 'Other'
        grouped.setdefault(section, []).append({
            'type': 'case', 'id': c.id, 'title': c.diagnosis,
            'description': f'Case {c.case_number}' if c.case_number else '',
            'url': f'/view-case/{c.id}',
        })

    for c in oncologic:
        section = c.body_section or 'Other'
        grouped.setdefault(section, []).append({
            'type': 'oncologic', 'slug': c.slug, 'title': c.cancer_name,
            'description': c.description,
            'url': f'/tnm-calculator/{c.slug}',
        })

    for f in ifs:
        section = f.body_section or f.category or 'Other'
        grouped.setdefault(section, []).append({
            'type': 'incidental', 'slug': f.slug, 'title': f.finding_name,
            'description': f.description,
            'url': f'/incidental-findings/{f.slug}',
        })

    return jsonify(grouped)


# ==================== REPORTING TEMPLATE VIEWS ====================

@reporting_bp.route('/reporting-template/<slug>')
@login_required
def view_reporting_template(slug):
    """View a specific admin-curated reporting template."""
    template = ReportingTemplate.query.filter_by(slug=slug, is_available=True).first_or_404()

    content = {'styles': '', 'body': ''}
    if template.template_html:
        content = _extract_template_content(template.template_html)

    # For AI-generated templates, use algorithm_html as body if no template_html
    if not template.template_html and template.algorithm_html:
        content['body'] = template.algorithm_html

    # Parse resources from source_citation JSON
    resources = {'references': [], 'linked_cases': [], 'linked_tnm': [], 'pdfs': []}
    if template.source_citation:
        try:
            parsed = json.loads(template.source_citation)
            if isinstance(parsed, dict):
                resources = {
                    'references': parsed.get('references', []),
                    'linked_cases': parsed.get('linked_cases', []),
                    'linked_tnm': parsed.get('linked_tnm', []),
                    'pdfs': parsed.get('pdfs', []),
                }
            elif isinstance(parsed, list):
                resources['references'] = parsed
        except (json.JSONDecodeError, TypeError):
            if template.source_citation.strip():
                resources['references'] = [{'source': template.source_citation.strip(), 'version': '', 'url': ''}]

    return render_template('reporting_template_view.html',
                           template=template,
                           content=content,
                           resources=resources)


def _extract_template_content(html):
    """Extract style and body from self-contained HTML."""
    styles = ''
    body = html

    style_matches = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL)
    if style_matches:
        styles = '\n'.join(style_matches)

    body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL)
    if body_match:
        body = body_match.group(1)

    # Strip <style> blocks from body to prevent them overriding our layout CSS
    body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL)

    # Force single-column: replace multi-column grid patterns in extracted styles
    styles = re.sub(
        r'grid-template-columns\s*:\s*(?!1fr\s*[;\}])([^;}\n]+)',
        'grid-template-columns: 1fr',
        styles,
    )

    return {'styles': styles, 'body': body}


# ==================== ADMIN: REPORTING TEMPLATE MANAGEMENT ====================

@reporting_bp.route('/admin/reporting-templates')
@require_admin
def admin_reporting_templates():
    """Admin page for managing reporting templates."""
    templates = ReportingTemplate.query.order_by(
        ReportingTemplate.category, ReportingTemplate.title
    ).all()
    return render_template('admin_reporting_templates.html', templates=templates,
                           cloudinary_cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
                           cloudinary_upload_preset=os.environ.get('CLOUDINARY_UPLOAD_PRESET', ''))


@reporting_bp.route('/admin/reporting-templates/api', methods=['POST'])
@require_admin
def create_reporting_template():
    """API: Create a new reporting template."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    title = data.get('title', '').strip()
    category = data.get('category', '').strip()
    if not title or not category:
        return jsonify({'error': 'title and category are required.'}), 400

    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')

    existing = ReportingTemplate.query.filter_by(slug=slug).first()
    if existing:
        return jsonify({'error': f'Template with slug "{slug}" already exists.'}), 409

    template = ReportingTemplate(
        slug=slug,
        title=title,
        category=category,
        body_section=data.get('body_section', '').strip() or None,
        description=data.get('description', '').strip() or None,
        keywords=data.get('keywords', '').strip() or None,
        template_html=data.get('template_html', '').strip() or None,
        algorithm_html=data.get('algorithm_html', '').strip() or None,
        source_citation=data.get('source_citation', '').strip() or None,
        guideline_version=data.get('guideline_version', '').strip() or None,
        is_available=data.get('is_available', False),
        created_by_user_id=current_user.id,
    )

    db.session.add(template)
    db.session.commit()

    return jsonify(template.to_dict()), 201


@reporting_bp.route('/admin/reporting-templates/api/<int:template_id>', methods=['GET'])
@require_admin
def get_reporting_template(template_id):
    """API: Get a single reporting template."""
    template = ReportingTemplate.query.get_or_404(template_id)
    return jsonify(template.to_dict())


@reporting_bp.route('/admin/reporting-templates/api/<int:template_id>/verify', methods=['POST'])
@require_admin
def verify_reporting_template(template_id):
    """API: Verify and publish a reporting template."""
    template = ReportingTemplate.query.get_or_404(template_id)
    template.verified_by_user_id = current_user.id
    template.verified_at = datetime.utcnow()
    template.is_available = True
    db.session.commit()
    return jsonify({'success': True, 'message': f'Template "{template.title}" verified and published.'})


@reporting_bp.route('/admin/reporting-templates/api/<int:template_id>', methods=['PUT'])
@require_admin
def update_reporting_template(template_id):
    """API: Update a reporting template."""
    template = ReportingTemplate.query.get_or_404(template_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    for field in ['title', 'category', 'body_section', 'description', 'keywords',
                  'template_html', 'algorithm_html', 'source_citation', 'guideline_version',
                  'last_edit_note']:
        if field in data:
            setattr(template, field, data[field].strip() if isinstance(data[field], str) else data[field])

    if 'is_available' in data:
        template.is_available = bool(data['is_available'])

    template.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify(template.to_dict())


@reporting_bp.route('/admin/reporting-templates/api/<int:template_id>', methods=['DELETE'])
@require_admin
def delete_reporting_template(template_id):
    """API: Delete a reporting template."""
    template = ReportingTemplate.query.get_or_404(template_id)
    title = template.title
    db.session.delete(template)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Template "{title}" deleted.'})


@reporting_bp.route('/admin/reporting-templates/generate', methods=['POST'])
@require_admin
def generate_reporting_template():
    """API: Generate a reporting template using Claude (mirrors TNM generator pattern)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    title = data.get('title', '').strip()
    category = data.get('category', '').strip()
    if not title or not category:
        return jsonify({'error': 'title and category are required.'}), 400

    try:
        from reporting_template_generator import generate_reporting_template_html
        result = generate_reporting_template_html(
            title=title,
            category=category,
            body_section=data.get('body_section', ''),
            source_citation=data.get('source_citation', ''),
            additional_context=data.get('additional_context', ''),
            user_id=current_user.id,
        )
        return jsonify(result)

    except Exception as exc:
        logger.error(f"Reporting template generation failed: {exc}")
        return jsonify({'error': str(exc)}), 500


# ==================== SMART REPORTER ROUTES ====================


@reporting_bp.route('/smart-reporter')
@login_required
def smart_reporter():
    """Landing page for Smart Reporter — sessions loaded dynamically via JS."""
    return render_template('smart_reporter.html')


@reporting_bp.route('/api/smart-reporter/generate-tree', methods=['POST'])
@login_required
def smart_reporter_generate_tree():
    """Generate an algorithm tree for interactive scan reading walkthrough."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    clinical_question = (data.get('clinical_question') or '').strip()
    if not clinical_question:
        return jsonify({'error': 'Clinical question is required.'}), 400
    if len(clinical_question) > 500:
        return jsonify({'error': 'Clinical question too long (max 500 characters).'}), 400

    modality = (data.get('modality') or '').strip()
    body_section = (data.get('body_section') or '').strip()

    # Rate limit: max 5 active sessions per user
    active_count = ReportingSession.query.filter(
        ReportingSession.user_id == current_user.id,
        ReportingSession.status.in_(['generating', 'walkthrough', 'editing']),
    ).count()
    if active_count >= 5:
        return jsonify({
            'error': 'You have too many active reporting sessions. '
                     'Please complete or close existing sessions before starting a new one.'
        }), 429

    # Create session in generating state
    session = ReportingSession(
        user_id=current_user.id,
        clinical_question=clinical_question,
        modality=modality or None,
        body_section=body_section or None,
        status='generating',
    )
    db.session.add(session)
    db.session.flush()

    # --- Cache lookup: check for existing ReportingTemplate with matching slug ---
    cache_slug = re.sub(r'[^a-z0-9]+', '-', clinical_question.lower()).strip('-')
    cached_template = None
    if cache_slug:
        cached_template = ReportingTemplate.query.filter_by(
            slug=cache_slug, is_available=True
        ).first()

    if cached_template and cached_template.algorithm_html:
        try:
            cached_tree = json.loads(cached_template.algorithm_html)
            if cached_tree and cached_tree.get('steps'):
                session.algorithm_tree_json = cached_template.algorithm_html
                session.status = 'walkthrough'
                session.provider = 'cache'
                session.model_name = cached_template.generation_model or 'cached'
                session.generation_tokens = 0
                db.session.commit()

                logger.info(f"Smart Reporter cache hit for slug '{cache_slug}'")
                return jsonify({
                    'success': True,
                    'session_id': session.id,
                    'algorithm_tree': cached_tree,
                    'cached': True,
                })
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Cache entry '{cache_slug}' has invalid algorithm_html, regenerating.")
            cached_template = None

    # --- Generate algorithm tree via AI ---
    try:
        from ai_smart_reporter import generate_algorithm_tree, SmartReporterError
        result = generate_algorithm_tree(
            clinical_question=clinical_question,
            modality=modality,
            body_section=body_section,
        )
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Smart Reporter tree generation failed: {exc}")
        return jsonify({'error': f'Algorithm generation failed: {exc}'}), 500

    # Store result in session
    tree_json = json.dumps({
        'steps': result.get('steps', []),
        'lines_tubes_step': result.get('lines_tubes_step', {}),
        'incidental_findings_step': result.get('incidental_findings_step', {}),
        'report_template': result.get('report_template', {}),
    })
    session.algorithm_tree_json = tree_json
    session.status = 'walkthrough'
    session.provider = result.get('provider', 'claude')
    session.model_name = result.get('model', '')
    session.generation_tokens = result.get('token_count', 0)

    # --- Cache write: store tree as ReportingTemplate for future reuse ---
    if cache_slug:
        existing_cache = ReportingTemplate.query.filter_by(slug=cache_slug).first()
        if not existing_cache:
            try:
                cache_entry = ReportingTemplate(
                    slug=cache_slug,
                    title=clinical_question,
                    category='smart_reporter_cache',
                    body_section=body_section or None,
                    description=f'Cached Smart Reporter algorithm for: {clinical_question}',
                    keywords=f'{clinical_question}, {modality or ""}, {body_section or ""}',
                    algorithm_html=tree_json,
                    is_available=True,
                    is_ai_generated=True,
                    generation_model=result.get('model', ''),
                    generated_at=datetime.utcnow(),
                    created_by_user_id=current_user.id,
                )
                db.session.add(cache_entry)
                logger.info(f"Cached Smart Reporter tree as ReportingTemplate '{cache_slug}'")
            except Exception as cache_exc:
                logger.warning(f"Failed to cache tree as ReportingTemplate: {cache_exc}")

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to save Smart Reporter session: {exc}")
        return jsonify({'error': 'Failed to save session.'}), 500

    return jsonify({
        'success': True,
        'session_id': session.id,
        'algorithm_tree': session.get_algorithm_tree(),
    })


@reporting_bp.route('/api/smart-reporter/session/<int:session_id>', methods=['GET'])
@login_required
def smart_reporter_get_session(session_id):
    """Get a Smart Reporter session for resume/reload."""
    session = ReportingSession.query.get_or_404(session_id)
    if session.user_id != current_user.id:
        return jsonify({'error': 'Access denied.'}), 403

    return jsonify({
        'id': session.id,
        'clinical_question': session.clinical_question,
        'modality': session.modality,
        'body_section': session.body_section,
        'algorithm_tree': session.get_algorithm_tree(),
        'walkthrough_answers': session.get_walkthrough_answers(),
        'report_text': session.report_text,
        'status': session.status,
        'ask_claude_count': session.ask_claude_count or 0,
        'created_at': session.created_at.isoformat() if session.created_at else None,
    })


@reporting_bp.route('/api/smart-reporter/session/<int:session_id>', methods=['PUT'])
@login_required
def smart_reporter_save_session(session_id):
    """Save walkthrough progress, report text, or status update."""
    session = ReportingSession.query.get_or_404(session_id)
    if session.user_id != current_user.id:
        return jsonify({'error': 'Access denied.'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    # Update walkthrough answers if provided
    if 'walkthrough_answers' in data:
        session.walkthrough_answers_json = json.dumps(data['walkthrough_answers'])

    # Update report text if provided
    if 'report_text' in data:
        session.report_text = data['report_text']

    # Update status if provided
    if 'status' in data and data['status'] in ('walkthrough', 'editing', 'completed'):
        session.status = data['status']
        if data['status'] == 'completed':
            session.completed_at = datetime.utcnow()

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to save Smart Reporter session {session_id}: {exc}")
        return jsonify({'error': 'Failed to save.'}), 500

    return jsonify({'success': True, 'status': session.status})


@reporting_bp.route('/api/smart-reporter/ask-claude', methods=['POST'])
@login_required
def smart_reporter_ask_claude():
    """Ask Claude a question about the current report (Scene 2)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    session_id = data.get('session_id')
    question = (data.get('question') or '').strip()
    current_report = (data.get('current_report') or '').strip()

    if not question:
        return jsonify({'error': 'Question is required.'}), 400
    if len(question) > 1000:
        return jsonify({'error': 'Question too long (max 1000 characters).'}), 400

    # Validate session if provided
    session = None
    if session_id:
        session = ReportingSession.query.get(session_id)
        if session and session.user_id != current_user.id:
            return jsonify({'error': 'Access denied.'}), 403
        if session and (session.ask_claude_count or 0) >= 20:
            return jsonify({
                'error': 'You have reached the maximum number of questions for this session (20). '
                         'Please use the remaining suggestions to finalize your report.'
            }), 429

    # Call Claude
    try:
        from ai_smart_reporter import ask_claude_about_report, SmartReporterError
        result = ask_claude_about_report(
            current_report=current_report,
            question=question,
        )
    except Exception as exc:
        logger.error(f"Smart Reporter ask-claude failed: {exc}")
        return jsonify({'error': f'Failed to get response: {exc}'}), 500

    # Increment counter
    if session:
        session.ask_claude_count = (session.ask_claude_count or 0) + 1
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    remaining = 20 - (session.ask_claude_count if session else 0)

    return jsonify({
        'success': True,
        'answer': result.get('answer', ''),
        'remaining_questions': max(0, remaining),
    })


@reporting_bp.route('/api/smart-reporter/review-report', methods=['POST'])
@login_required
def smart_reporter_review_report():
    """Review a report for spelling, grammar, phrasing, and structure."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    report_text = (data.get('report_text') or '').strip()
    session_id = data.get('session_id')

    if not report_text:
        return jsonify({'error': 'Report text is required.'}), 400
    if len(report_text) > 10000:
        return jsonify({'error': 'Report text too long (max 10000 characters).'}), 400

    # Rate limit via session if provided
    session = None
    if session_id:
        session = ReportingSession.query.get(session_id)
        if session and session.user_id != current_user.id:
            return jsonify({'error': 'Access denied.'}), 403
        if session and (session.ask_claude_count or 0) >= 20:
            return jsonify({
                'error': 'You have reached the maximum number of AI requests for this session (20).'
            }), 429

    try:
        from ai_smart_reporter import review_report, SmartReporterError
        result = review_report(report_text=report_text)
    except Exception as exc:
        logger.error(f"Smart Reporter review failed: {exc}")
        return jsonify({'error': f'Review failed: {exc}'}), 500

    # Increment counter
    if session:
        session.ask_claude_count = (session.ask_claude_count or 0) + 1
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    remaining = 20 - (session.ask_claude_count if session else 0)

    return jsonify({
        'success': True,
        'improved_report': result.get('improved_report', ''),
        'suggestions': result.get('suggestions', []),
        'remaining_questions': max(0, remaining),
    })


@reporting_bp.route('/api/smart-reporter/create-session', methods=['POST'])
@login_required
def smart_reporter_create_session():
    """Create a blank session for Scene 2 direct entry (no algorithm tree)."""
    data = request.get_json() or {}

    clinical_question = (data.get('clinical_question') or 'Report editing session').strip()[:500]

    # Rate limit: max 5 active sessions per user
    active_count = ReportingSession.query.filter(
        ReportingSession.user_id == current_user.id,
        ReportingSession.status.in_(['generating', 'walkthrough', 'editing']),
    ).count()
    if active_count >= 5:
        return jsonify({
            'error': 'You have too many active sessions. '
                     'Please complete or close existing sessions before starting a new one.'
        }), 429

    session = ReportingSession(
        user_id=current_user.id,
        clinical_question=clinical_question,
        status='editing',
    )
    db.session.add(session)

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to create Smart Reporter session: {exc}")
        return jsonify({'error': 'Failed to create session.'}), 500

    return jsonify({
        'success': True,
        'session_id': session.id,
    })


@reporting_bp.route('/api/smart-reporter/sessions', methods=['GET'])
@login_required
def smart_reporter_list_sessions():
    """List the current user's Smart Reporter sessions with search + pagination."""
    search = request.args.get('q', '').strip()
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 50)  # Cap at 50

    query = ReportingSession.query.filter_by(user_id=current_user.id)

    if search:
        query = query.filter(
            ReportingSession.clinical_question.ilike(f'%{search}%')
        )

    total = query.count()
    sessions = query.order_by(
        ReportingSession.created_at.desc()
    ).offset(offset).limit(limit).all()

    return jsonify({
        'sessions': [s.to_summary_dict() for s in sessions],
        'total': total,
        'offset': offset,
        'has_more': (offset + limit) < total,
    })


@reporting_bp.route('/api/smart-reporter/session/<int:session_id>', methods=['DELETE'])
@login_required
def smart_reporter_delete_session(session_id):
    """Delete a Smart Reporter session."""
    session = ReportingSession.query.get_or_404(session_id)
    if session.user_id != current_user.id:
        return jsonify({'error': 'Access denied.'}), 403

    try:
        db.session.delete(session)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to delete Smart Reporter session {session_id}: {exc}")
        return jsonify({'error': 'Failed to delete session.'}), 500

    return jsonify({'success': True})


@reporting_bp.route('/api/smart-reporter/session/<int:session_id>/publish', methods=['POST'])
@login_required
def smart_reporter_publish_session(session_id):
    """Publish a session to the community library."""
    session = ReportingSession.query.get_or_404(session_id)
    if session.user_id != current_user.id:
        return jsonify({'error': 'Access denied.'}), 403

    if not session.report_text or not session.report_text.strip():
        return jsonify({'error': 'Cannot publish an empty report. Add content first.'}), 400

    # Check if already published
    existing = PublishedReport.query.filter_by(
        session_id=session_id, user_id=current_user.id
    ).first()
    if existing:
        return jsonify({'error': 'This session has already been published.'}), 409

    # Determine contributor name
    contributor_name = (
        current_user.public_display_name
        or current_user.full_name
        or 'Anonymous'
    )

    published = PublishedReport(
        session_id=session.id,
        user_id=current_user.id,
        clinical_question=session.clinical_question,
        modality=session.modality,
        body_section=session.body_section,
        report_text=session.report_text,
        algorithm_tree_json=session.algorithm_tree_json,
        contributor_name=contributor_name,
    )
    db.session.add(published)

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to publish session {session_id}: {exc}")
        return jsonify({'error': 'Failed to publish.'}), 500

    return jsonify({
        'success': True,
        'published_id': published.id,
        'message': f'Report published to community library as "{contributor_name}".',
    })


@reporting_bp.route('/api/smart-reporter/community', methods=['GET'])
@login_required
def smart_reporter_community_library():
    """List published reports from all users (community library)."""
    search = request.args.get('q', '').strip()
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 50)

    query = PublishedReport.query

    if search:
        query = query.filter(
            db.or_(
                PublishedReport.clinical_question.ilike(f'%{search}%'),
                PublishedReport.modality.ilike(f'%{search}%'),
                PublishedReport.body_section.ilike(f'%{search}%'),
                PublishedReport.contributor_name.ilike(f'%{search}%'),
            )
        )

    total = query.count()
    reports = query.order_by(
        PublishedReport.published_at.desc()
    ).offset(offset).limit(limit).all()

    return jsonify({
        'reports': [r.to_summary_dict() for r in reports],
        'total': total,
        'offset': offset,
        'has_more': (offset + limit) < total,
    })


@reporting_bp.route('/api/smart-reporter/community/<int:report_id>', methods=['GET'])
@login_required
def smart_reporter_get_published_report(report_id):
    """Get a single published report (full content) for loading into editor."""
    report = PublishedReport.query.get_or_404(report_id)
    return jsonify(report.to_dict())


@reporting_bp.route('/api/smart-reporter/admin-templates', methods=['GET'])
@login_required
def smart_reporter_admin_templates():
    """List verified (admin-curated) ReportingTemplate entries for the Smart Reporter landing page."""
    search = request.args.get('q', '').strip()
    offset = request.args.get('offset', 0, type=int)
    limit = min(request.args.get('limit', 20, type=int), 50)

    query = ReportingTemplate.query.filter(
        ReportingTemplate.is_available == True,
        ReportingTemplate.verified_at.isnot(None),
    )

    if search:
        query = query.filter(
            db.or_(
                ReportingTemplate.title.ilike(f'%{search}%'),
                ReportingTemplate.keywords.ilike(f'%{search}%'),
                ReportingTemplate.body_section.ilike(f'%{search}%'),
            )
        )

    total = query.count()
    templates = query.order_by(ReportingTemplate.updated_at.desc()).offset(offset).limit(limit).all()

    return jsonify({
        'templates': [{
            'id': t.id,
            'slug': t.slug,
            'title': t.title,
            'category': t.category,
            'body_section': t.body_section,
            'description': t.description,
            'has_algorithm': bool(t.algorithm_html),
            'has_pacs_report': bool(t.pacs_report_text),
            'verified_at': t.verified_at.isoformat() if t.verified_at else None,
            'created_at': t.created_at.isoformat() if t.created_at else None,
        } for t in templates],
        'total': total,
        'offset': offset,
        'has_more': (offset + limit) < total,
    })


@reporting_bp.route('/api/smart-reporter/admin-templates/<int:template_id>', methods=['GET'])
@login_required
def smart_reporter_get_admin_template(template_id):
    """Get a single admin template (full content) for loading into editor."""
    template = ReportingTemplate.query.get_or_404(template_id)
    if not template.is_available or not template.verified_at:
        return jsonify({'error': 'Template not available.'}), 404

    result = template.to_dict()
    result['algorithm_html'] = template.algorithm_html
    result['template_html'] = template.template_html
    result['has_algorithm'] = bool(template.algorithm_html)
    result['has_pacs_report'] = bool(template.pacs_report_text)
    return jsonify(result)


@reporting_bp.route('/api/smart-reporter/relevant-content', methods=['GET'])
@login_required
def smart_reporter_relevant_content():
    """Search across DB for content relevant to the current report context.

    Searches: Cases, TNM calculators, IF calculators, Reporting templates, Clinical protocols.
    Returns top results per category as clickable cards.
    """
    q = request.args.get('q', '').strip()
    body_section = request.args.get('body_section', '').strip()

    if not q and not body_section:
        return jsonify({'results': []})

    results = []
    search_terms = [t for t in q.lower().split() if len(t) > 2]

    # --- Cases (published, matching diagnosis or body_part) ---
    try:
        case_query = Case.query.filter(Case.status == CaseStatus.PUBLISHED)
        if q:
            case_query = case_query.filter(
                db.or_(
                    Case.diagnosis.ilike(f'%{q}%'),
                    Case.body_part.ilike(f'%{q}%'),
                )
            )
        elif body_section:
            case_query = case_query.filter(Case.body_part.ilike(f'%{body_section}%'))

        cases = case_query.order_by(Case.diagnosis).limit(4).all()
        for c in cases:
            results.append({
                'type': 'case',
                'icon': 'fa-book-medical',
                'color': '#e96304',
                'title': c.diagnosis or 'Case',
                'subtitle': c.body_part or '',
                'url': f'/view-case/{c.id}',
            })
    except Exception:
        pass

    # --- TNM Calculators (available, matching cancer name or body section) ---
    try:
        tnm_query = TNMCalculatorContent.query.filter_by(is_available=True)
        if q:
            tnm_query = tnm_query.filter(
                db.or_(
                    TNMCalculatorContent.cancer_name.ilike(f'%{q}%'),
                    TNMCalculatorContent.body_section.ilike(f'%{q}%'),
                )
            )
        elif body_section:
            tnm_query = tnm_query.filter(TNMCalculatorContent.body_section.ilike(f'%{body_section}%'))

        tnms = tnm_query.limit(4).all()
        for t in tnms:
            results.append({
                'type': 'tnm',
                'icon': 'fa-dna',
                'color': '#6b46c1',
                'title': f'TNM: {t.cancer_name}',
                'subtitle': t.body_section or '',
                'url': f'/tnm-calculator/{t.slug}',
            })
    except Exception:
        pass

    # --- Incidental Findings Calculators ---
    try:
        if_query = IncidentalFindingCalculator.query.filter_by(is_available=True)
        if q:
            if_query = if_query.filter(
                db.or_(
                    IncidentalFindingCalculator.finding_name.ilike(f'%{q}%'),
                    IncidentalFindingCalculator.keywords.ilike(f'%{q}%'),
                )
            )
        elif body_section:
            if_query = if_query.filter(IncidentalFindingCalculator.body_section.ilike(f'%{body_section}%'))

        ifs = if_query.limit(4).all()
        for f in ifs:
            results.append({
                'type': 'incidental',
                'icon': 'fa-search-plus',
                'color': '#5E899E',
                'title': f.finding_name,
                'subtitle': f.guideline_source or f.body_section or '',
                'url': f'/incidental-findings/{f.slug}',
            })
    except Exception:
        pass

    # --- Reporting Templates ---
    try:
        rt_query = ReportingTemplate.query.filter_by(is_available=True)
        if q:
            rt_query = rt_query.filter(
                db.or_(
                    ReportingTemplate.title.ilike(f'%{q}%'),
                    ReportingTemplate.keywords.ilike(f'%{q}%'),
                )
            )
        elif body_section:
            rt_query = rt_query.filter(ReportingTemplate.body_section.ilike(f'%{body_section}%'))

        rts = rt_query.limit(3).all()
        for t in rts:
            results.append({
                'type': 'template',
                'icon': 'fa-clipboard-list',
                'color': '#a8d5ba',
                'title': t.title,
                'subtitle': t.category or t.body_section or '',
                'url': f'/reporting-template/{t.slug}',
            })
    except Exception:
        pass

    # --- Clinical Protocols ---
    try:
        cp_query = ClinicalProtocol.query.filter_by(is_published=True)
        if q:
            cp_query = cp_query.filter(
                db.or_(
                    ClinicalProtocol.title.ilike(f'%{q}%'),
                    ClinicalProtocol.keywords.ilike(f'%{q}%'),
                )
            )
        # Protocols don't have body_section, skip if only body_section provided

        if q:  # Only search protocols when there's a text query
            cps = cp_query.limit(3).all()
            for p in cps:
                results.append({
                    'type': 'protocol',
                    'icon': 'fa-headset',
                    'color': '#198754',
                    'title': p.title,
                    'subtitle': p.category or '',
                    'url': f'/on-call-helper',  # Protocols don't have individual pages
                })
    except Exception:
        pass

    return jsonify({'results': results[:15]})
