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
    RadiologyTemplate, ReportingAlgorithm,
    TNMCalculatorContent, ClinicalProtocol,
    IncidentalFindingCalculator, AJCCDiseaseSite, AJCCBodySection,
    User, AiPrelimCaseData, ReportingSession, PublishedReport,
)
from access_control import require_admin
from clinical_tool_generator import extract_html_content

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
                SELECT ra.id, ra.slug, ra.title, ra.category, ra.body_section,
                       ra.description, ra.source_citation,
                       COALESCE(ra.is_ai_generated, FALSE) AS is_ai_generated,
                       GREATEST(
                           similarity(ra.title, :query),
                           COALESCE(similarity(ra.keywords, :query), 0)
                       ) AS sim
                FROM reporting_algorithm ra
                WHERE ra.is_available = TRUE
                  AND (
                      similarity(ra.title, :query) > 0.1
                      OR similarity(ra.keywords, :query) > 0.1
                      OR ra.title ILIKE :like_query
                      OR ra.keywords ILIKE :like_query
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
        templates = ReportingAlgorithm.query.filter(
            ReportingAlgorithm.is_available == True,
            db.or_(
                ReportingAlgorithm.title.ilike(like),
                ReportingAlgorithm.keywords.ilike(like),
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
    # Kept for backward compatibility — generates ReportingAlgorithm cache entries.
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

        # Cache as ReportingAlgorithm
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
    Cache an AI-generated algorithm as a ReportingAlgorithm for instant future search hits.
    If an entry with the same slug already exists, skip (no overwrite).
    """
    slug = re.sub(r'[^a-z0-9]+', '-', diagnosis.lower()).strip('-')
    if not slug:
        return None

    existing = ReportingAlgorithm.query.filter_by(slug=slug).first()
    if existing:
        logger.info(f"ReportingAlgorithm slug '{slug}' already exists, skipping cache creation.")
        return None

    # Build keywords from diagnosis + differentials
    keywords_parts = [diagnosis]
    for d in algorithmic_result.get('differential_diagnosis', []):
        if isinstance(d, dict) and d.get('diagnosis'):
            keywords_parts.append(d['diagnosis'])
    # Add suggested keywords from AI
    keywords_parts.extend(algorithmic_result.get('suggested_keywords', []))
    keywords = ', '.join(dict.fromkeys(keywords_parts))  # dedupe preserving order

    entry = ReportingAlgorithm(
        slug=slug,
        title=diagnosis,
        origin='ai_generated',
        category='ai_generated',
        body_section=body_section or None,
        description=f'AI-generated reporting algorithm for {diagnosis}',
        keywords=keywords,
        algorithm_html=algorithmic_result.get('algorithmic_approach_html', ''),
        source_citation='AI-generated — verify against published guidelines',
        is_available=True,
        is_ai_generated=True,
        generation_model=algorithmic_result.get('model', ''),
        generated_at=datetime.utcnow(),
        created_by_user_id=user_id,
    )

    db.session.add(entry)
    logger.info(f"Cached ReportingAlgorithm '{slug}' from algorithm generation.")
    return entry


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
    template = ReportingAlgorithm.query.filter_by(slug=slug, is_available=True).first_or_404()

    content = {'styles': '', 'body': ''}
    if template.template_html:
        content = extract_html_content(template.template_html)

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


@reporting_bp.route('/reporting-template/embed/<slug>')
@login_required
def embed_reporting_template(slug):
    """Render a reporting template in embed mode (for Smart Reporter Tool Panel)."""
    template = ReportingAlgorithm.query.filter_by(slug=slug, is_available=True).first_or_404()

    if template.template_html:
        return template.template_html
    elif template.algorithm_html:
        return template.algorithm_html
    else:
        return "Template content not available", 404


# ==================== USER: REPORTING ALGORITHMS BROWSE ====================

@reporting_bp.route('/reporting-algorithms')
@login_required
def browse_reporting_algorithms():
    """User-facing browse page for reporting algorithms (interactive decision trees)."""
    templates = ReportingAlgorithm.query.filter_by(
        is_available=True
    ).order_by(
        ReportingAlgorithm.category, ReportingAlgorithm.title
    ).all()

    grouped = {}
    for t in templates:
        cat = t.category or 'Other'
        if cat == 'smart_reporter_cache':
            continue  # Skip cached entries, show only curated
        grouped.setdefault(cat, []).append(t)

    return render_template('reporting_algorithms_browse.html', grouped=grouped)


# ==================== USER: RADIOLOGY TEMPLATES BROWSE ====================

@reporting_bp.route('/reporting-templates')
@login_required
def browse_reporting_templates():
    """User-facing browse page for radiology templates (plain-text PACS reports)."""
    radiology_templates = RadiologyTemplate.query.filter_by(
        is_available=True
    ).order_by(RadiologyTemplate.title).all()

    return render_template('reporting_templates_browse.html',
                           radiology_templates=radiology_templates)


@reporting_bp.route('/radiology-template/text/<int:template_id>')
@login_required
def get_radiology_template_text(template_id):
    """User-facing endpoint to fetch radiology template text for preview/copy."""
    t = RadiologyTemplate.query.get_or_404(template_id)
    if not t.is_available or t.origin not in ('admin', 'personal'):
        return jsonify({'error': 'Template not available'}), 404
    return jsonify({
        'title': t.title,
        'pacs_report_text': t.template_text or '',
    })


# ==================== ADMIN: REPORTING ALGORITHM MANAGEMENT ====================

@reporting_bp.route('/admin/reporting-algorithms')
@require_admin
def admin_reporting_algorithms():
    """Admin page for managing reporting algorithms (interactive decision trees)."""
    templates = ReportingAlgorithm.query.order_by(
        ReportingAlgorithm.category, ReportingAlgorithm.title
    ).all()
    return render_template('admin_reporting_algorithms.html', templates=templates,
                           cloudinary_cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
                           cloudinary_upload_preset=os.environ.get('CLOUDINARY_UPLOAD_PRESET', ''))


@reporting_bp.route('/admin/reporting-algorithms/api', methods=['POST'])
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

    existing = ReportingAlgorithm.query.filter_by(slug=slug).first()
    if existing:
        return jsonify({'error': f'Template with slug "{slug}" already exists.'}), 409

    template = ReportingAlgorithm(
        slug=slug,
        title=title,
        origin='admin',
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


@reporting_bp.route('/admin/reporting-algorithms/api/<int:template_id>', methods=['GET'])
@require_admin
def get_reporting_template(template_id):
    """API: Get a single reporting template."""
    template = ReportingAlgorithm.query.get_or_404(template_id)
    return jsonify(template.to_dict())


@reporting_bp.route('/admin/reporting-algorithms/api/<int:template_id>/verify', methods=['POST'])
@require_admin
def verify_reporting_template(template_id):
    """API: Verify and publish a reporting template."""
    template = ReportingAlgorithm.query.get_or_404(template_id)
    template.verified_by_user_id = current_user.id
    template.verified_at = datetime.utcnow()
    template.is_available = True
    db.session.commit()
    return jsonify({'success': True, 'message': f'Template "{template.title}" verified and published.'})


@reporting_bp.route('/admin/reporting-algorithms/api/<int:template_id>', methods=['PUT'])
@require_admin
def update_reporting_template(template_id):
    """API: Update a reporting template."""
    template = ReportingAlgorithm.query.get_or_404(template_id)
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


@reporting_bp.route('/admin/reporting-algorithms/api/<int:template_id>', methods=['DELETE'])
@require_admin
def delete_reporting_template(template_id):
    """API: Delete a reporting template."""
    template = ReportingAlgorithm.query.get_or_404(template_id)
    title = template.title
    db.session.delete(template)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Template "{title}" deleted.'})


@reporting_bp.route('/admin/reporting-algorithms/generate', methods=['POST'])
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


# ==================== RADIOLOGY TEMPLATES (ADMIN) ====================


@reporting_bp.route('/admin/radiology-templates')
@require_admin
def admin_radiology_templates():
    """Admin page for managing plain-text radiology report templates."""
    templates = RadiologyTemplate.query.order_by(
        RadiologyTemplate.created_at.desc()
    ).all()
    return render_template('admin_radiology_templates.html', templates=templates,
                           cloudinary_cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
                           cloudinary_upload_preset=os.environ.get('CLOUDINARY_UPLOAD_PRESET', ''))


@reporting_bp.route('/admin/radiology-templates/generate', methods=['POST'])
@require_admin
def generate_radiology_template_route():
    """Generate a radiology report template via AI from clinical scenario."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    clinical_scenario = (data.get('clinical_scenario') or '').strip()
    if not clinical_scenario:
        return jsonify({'error': 'clinical_scenario is required.'}), 400

    modality = (data.get('modality') or '').strip()
    body_section = (data.get('body_section') or '').strip()

    # Extract resources if provided
    resources = None
    source_citation = data.get('source_citation', '')
    if source_citation:
        try:
            from clinical_tool_generator import format_resources_for_prompt
            resources = {'raw_citation': source_citation}
        except ImportError:
            pass

    try:
        from ai_smart_reporter import generate_radiology_template
        result = generate_radiology_template(
            clinical_scenario=clinical_scenario,
            modality=modality,
            body_section=body_section,
            resources=resources,
        )
    except Exception as exc:
        logger.error(f"Radiology template generation failed: {exc}")
        return jsonify({'error': str(exc)}), 500

    # Save to DB
    slug = re.sub(r'[^a-z0-9]+', '-', clinical_scenario.lower()).strip('-')
    # Handle slug collisions
    base_slug = slug
    counter = 1
    while RadiologyTemplate.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    template = RadiologyTemplate(
        slug=slug,
        title=clinical_scenario,
        origin='admin',
        category=None,
        body_section=body_section,
        description=f"{modality} — {clinical_scenario}" if modality else clinical_scenario,
        template_text=result['template_text'],
        is_available=False,
        is_ai_generated=True,
        generation_model=result.get('model', ''),
        generation_prompt=clinical_scenario,
        generated_at=datetime.utcnow(),
        created_by_user_id=current_user.id,
    )
    db.session.add(template)
    db.session.commit()

    return jsonify({
        'success': True,
        'id': template.id,
        'slug': slug,
        'message': f'Template "{clinical_scenario}" generated successfully.',
    })


@reporting_bp.route('/admin/radiology-templates/api/<int:template_id>', methods=['GET'])
@require_admin
def get_radiology_template(template_id):
    """Fetch a single radiology template for editing."""
    t = RadiologyTemplate.query.get_or_404(template_id)
    return jsonify({
        'id': t.id,
        'title': t.title,
        'slug': t.slug,
        'category': t.category,
        'body_section': t.body_section or '',
        'description': t.description or '',
        'keywords': t.keywords or '',
        'pacs_report_text': t.template_text or '',
        'is_available': t.is_available,
        'is_ai_generated': t.is_ai_generated,
        'verified_at': t.verified_at.isoformat() if t.verified_at else None,
        'created_at': t.created_at.isoformat() if t.created_at else None,
    })


@reporting_bp.route('/admin/radiology-templates/api/<int:template_id>', methods=['PUT'])
@require_admin
def update_radiology_template(template_id):
    """Update a radiology template's text and metadata."""
    t = RadiologyTemplate.query.get_or_404(template_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    if 'title' in data:
        t.title = data['title'].strip()
    if 'body_section' in data:
        t.body_section = data['body_section'].strip()
    if 'keywords' in data:
        t.keywords = data['keywords'].strip()
    if 'description' in data:
        t.description = data['description'].strip()
    if 'pacs_report_text' in data:
        t.template_text = data['pacs_report_text']
    if 'is_available' in data:
        t.is_available = bool(data['is_available'])
    if 'last_edit_note' in data:
        t.last_edit_note = data['last_edit_note'].strip()

    t.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True, 'message': 'Template updated.'})


@reporting_bp.route('/admin/radiology-templates/api/<int:template_id>/verify', methods=['POST'])
@require_admin
def verify_radiology_template(template_id):
    """Verify and publish a radiology template."""
    t = RadiologyTemplate.query.get_or_404(template_id)
    t.verified_by_user_id = current_user.id
    t.verified_at = datetime.utcnow()
    t.is_available = True
    db.session.commit()
    return jsonify({'success': True, 'message': f'Template "{t.title}" verified and published.'})


@reporting_bp.route('/admin/radiology-templates/api/<int:template_id>', methods=['DELETE'])
@require_admin
def delete_radiology_template(template_id):
    """Delete a radiology template."""
    t = RadiologyTemplate.query.get_or_404(template_id)
    title = t.title
    db.session.delete(t)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Template "{title}" deleted.'})


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

    # --- Cache lookup: check for existing ReportingAlgorithm with matching slug ---
    cache_slug = re.sub(r'[^a-z0-9]+', '-', clinical_question.lower()).strip('-')
    cached_template = None
    if cache_slug:
        cached_template = ReportingAlgorithm.query.filter_by(
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

    # --- Cache write: store tree as ReportingAlgorithm for future reuse ---
    if cache_slug:
        existing_cache = ReportingAlgorithm.query.filter_by(slug=cache_slug).first()
        if not existing_cache:
            try:
                cache_entry = ReportingAlgorithm(
                    slug=cache_slug,
                    title=clinical_question,
                    origin='smart_reporter_cache',
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
                logger.info(f"Cached Smart Reporter tree as ReportingAlgorithm '{cache_slug}'")
            except Exception as cache_exc:
                logger.warning(f"Failed to cache tree as ReportingAlgorithm: {cache_exc}")

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


@reporting_bp.route('/api/smart-reporter/quick-review', methods=['POST'])
@login_required
def smart_reporter_quick_review():
    """Quick Check: lightweight spelling/grammar/phrasing review using Haiku."""
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
        from ai_smart_reporter import quick_review, SmartReporterError
        result = quick_review(report_text=report_text)
    except Exception as exc:
        logger.error(f"Smart Reporter quick review failed: {exc}")
        return jsonify({'error': f'Quick review failed: {exc}'}), 500

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


@reporting_bp.route('/api/smart-reporter/ai-assist', methods=['POST'])
@login_required
def smart_reporter_ai_assist():
    """Unified AI assistant: corrections + answer + insights in one call."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    question = (data.get('question') or '').strip()
    report_text = (data.get('report_text') or '').strip()
    session_id = data.get('session_id')

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
                'error': 'You have reached the maximum number of AI requests for this session (20).'
            }), 429

    # Pull clinical context from session as fallback
    clinical_question = (data.get('clinical_question') or
                         (session.clinical_question if session else '') or '')
    modality = (data.get('modality') or
                (session.modality if session else '') or '')
    body_section = (data.get('body_section') or
                    (session.body_section if session else '') or '')

    # External context from "Use in Report" buttons
    external_context = data.get('external_context')

    try:
        from ai_smart_reporter import unified_ai_assist, SmartReporterError
        result = unified_ai_assist(
            report_text=report_text,
            question=question,
            clinical_question=clinical_question,
            modality=modality,
            body_section=body_section,
            external_context=external_context,
        )
    except Exception as exc:
        logger.error(f"Smart Reporter AI assist failed: {exc}")
        return jsonify({'error': f'AI assist failed: {exc}'}), 500

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
        'corrections': result.get('corrections', []),
        'answer': result.get('answer', ''),
        'insights': result.get('insights', {}),
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


@reporting_bp.route('/api/smart-reporter/route-intent', methods=['POST'])
@login_required
def smart_reporter_route_intent():
    """Classify user input into an intent category for Smart Reporter routing."""
    data = request.get_json() or {}
    user_input = (data.get('query') or '').strip()
    if not user_input:
        return jsonify({'error': 'Query is required.'}), 400

    try:
        from ai_smart_reporter import classify_intent, SmartReporterError
        result = classify_intent(user_input)
    except Exception as exc:
        logger.error(f"Smart Reporter intent classification failed: {exc}")
        # Fallback: default to walkthrough intent
        result = {
            'intent': 'walkthrough',
            'canonical_topic': '',
            'display_title': user_input,
            'modality': None,
            'body_section': None,
            'category': None,
        }

    # Check cache for walkthrough intent
    cached_tree = None
    if result.get('intent') == 'walkthrough' and result.get('canonical_topic'):
        slug = result['canonical_topic']
        # Check admin-verified templates first, then unverified, then user cache
        cached = ReportingAlgorithm.query.filter(
            ReportingAlgorithm.slug == slug,
            ReportingAlgorithm.is_available == True,
        ).order_by(
            ReportingAlgorithm.verified_at.desc().nullslast(),
        ).first()
        if cached and cached.algorithm_html:
            cached_tree = {
                'source': 'cache',
                'template_id': cached.id,
                'title': cached.title,
                'verified': cached.verified_at is not None,
            }

    return jsonify({
        'success': True,
        'intent': result.get('intent', 'walkthrough'),
        'canonical_topic': result.get('canonical_topic', ''),
        'display_title': result.get('display_title', user_input),
        'modality': result.get('modality'),
        'body_section': result.get('body_section'),
        'category': result.get('category'),
        'cached_tree': cached_tree,
    })


@reporting_bp.route('/api/smart-reporter/blank-template', methods=['POST'])
@login_required
def smart_reporter_blank_template():
    """Generate a blank structured reporting template (Gap 3 abort flow)."""
    data = request.get_json() or {}

    modality = (data.get('modality') or '').strip()
    body_section = (data.get('body_section') or '').strip()
    clinical_question = (data.get('clinical_question') or '').strip()

    if not modality and not body_section and not clinical_question:
        return jsonify({'error': 'At least one of modality, body_section, or clinical_question is required.'}), 400

    try:
        from ai_smart_reporter import generate_blank_template, SmartReporterError
        result = generate_blank_template(
            modality=modality,
            body_section=body_section,
            clinical_question=clinical_question,
        )
    except Exception as exc:
        logger.error(f"Smart Reporter blank template generation failed: {exc}")
        return jsonify({'error': f'Template generation failed: {exc}'}), 500

    return jsonify({
        'success': True,
        'template_text': result.get('template_text', ''),
        'model': result.get('model', ''),
        'token_count': result.get('token_count', 0),
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


## ==================== PERSONAL TEMPLATES (Phase 4, Gap 4) ====================

@reporting_bp.route('/api/smart-reporter/personal-templates', methods=['GET'])
@login_required
def smart_reporter_list_personal_templates():
    """List the current user's personal templates."""
    search = request.args.get('q', '').strip()
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 50)

    query = RadiologyTemplate.query.filter_by(
        origin='personal',
        created_by_user_id=current_user.id,
    )

    if search:
        query = query.filter(
            db.or_(
                RadiologyTemplate.title.ilike(f'%{search}%'),
                RadiologyTemplate.body_section.ilike(f'%{search}%'),
                RadiologyTemplate.keywords.ilike(f'%{search}%'),
            )
        )

    total = query.count()
    templates = query.order_by(
        RadiologyTemplate.updated_at.desc()
    ).offset(offset).limit(limit).all()

    return jsonify({
        'templates': [{
            'id': t.id,
            'title': t.title,
            'slug': t.slug,
            'body_section': t.body_section,
            'description': t.description,
            'updated_at': t.updated_at.isoformat() if t.updated_at else None,
            'has_content': bool(t.template_text),
        } for t in templates],
        'total': total,
        'offset': offset,
        'has_more': (offset + limit) < total,
    })


@reporting_bp.route('/api/smart-reporter/personal-templates', methods=['POST'])
@login_required
def smart_reporter_create_personal_template():
    """Save a report as a personal template (Gap 4)."""
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    report_text = (data.get('report_text') or '').strip()

    if not title:
        return jsonify({'error': 'Template title is required.'}), 400
    if not report_text:
        return jsonify({'error': 'Report text is required.'}), 400

    # Rate limit: max 50 personal templates per user
    count = RadiologyTemplate.query.filter_by(
        origin='personal',
        created_by_user_id=current_user.id,
    ).count()
    if count >= 50:
        return jsonify({
            'error': 'You have reached the maximum of 50 personal templates. '
                     'Please delete some before creating new ones.'
        }), 429

    # Generate unique slug: pt-{user_id}-{normalized-title}
    import re as _re
    base_slug = _re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    slug = f'pt-{current_user.id}-{base_slug}'

    # Handle slug collision (shouldn't happen often with user prefix)
    existing = RadiologyTemplate.query.filter_by(slug=slug).first()
    if existing:
        # If same user owns it, update instead
        if existing.created_by_user_id == current_user.id and existing.origin == 'personal':
            existing.title = title
            existing.template_text = report_text
            existing.body_section = (data.get('body_section') or '').strip() or None
            existing.description = (data.get('description') or '').strip() or None
            existing.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({
                'success': True,
                'template_id': existing.id,
                'message': f'Template "{title}" updated.',
            })
        # Different owner — append counter
        counter = 1
        while RadiologyTemplate.query.filter_by(slug=f'{slug}-{counter}').first():
            counter += 1
        slug = f'{slug}-{counter}'

    template = RadiologyTemplate(
        slug=slug,
        title=title,
        origin='personal',
        body_section=(data.get('body_section') or '').strip() or None,
        description=(data.get('description') or '').strip() or None,
        template_text=report_text,
        is_available=True,
        created_by_user_id=current_user.id,
    )
    db.session.add(template)

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to save personal template: {exc}")
        return jsonify({'error': 'Failed to save template.'}), 500

    return jsonify({
        'success': True,
        'template_id': template.id,
        'message': f'Template "{title}" saved.',
    }), 201


@reporting_bp.route('/api/smart-reporter/personal-templates/<int:template_id>', methods=['GET'])
@login_required
def smart_reporter_get_personal_template(template_id):
    """Get a personal template's content."""
    template = RadiologyTemplate.query.get_or_404(template_id)
    if template.created_by_user_id != current_user.id or template.origin != 'personal':
        return jsonify({'error': 'Access denied.'}), 403

    return jsonify({
        'id': template.id,
        'title': template.title,
        'slug': template.slug,
        'body_section': template.body_section,
        'description': template.description,
        'pacs_report_text': template.template_text or '',
        'updated_at': template.updated_at.isoformat() if template.updated_at else None,
    })


@reporting_bp.route('/api/smart-reporter/personal-templates/<int:template_id>', methods=['PUT'])
@login_required
def smart_reporter_update_personal_template(template_id):
    """Update a personal template (rename, change content)."""
    template = RadiologyTemplate.query.get_or_404(template_id)
    if template.created_by_user_id != current_user.id or template.origin != 'personal':
        return jsonify({'error': 'Access denied.'}), 403

    data = request.get_json() or {}

    if 'title' in data:
        title = (data['title'] or '').strip()
        if title:
            template.title = title
    if 'report_text' in data:
        template.template_text = (data['report_text'] or '').strip()
    if 'body_section' in data:
        template.body_section = (data['body_section'] or '').strip() or None
    if 'description' in data:
        template.description = (data['description'] or '').strip() or None

    template.updated_at = datetime.utcnow()

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to update personal template {template_id}: {exc}")
        return jsonify({'error': 'Failed to update template.'}), 500

    return jsonify({'success': True, 'message': f'Template "{template.title}" updated.'})


@reporting_bp.route('/api/smart-reporter/personal-templates/<int:template_id>', methods=['DELETE'])
@login_required
def smart_reporter_delete_personal_template(template_id):
    """Delete a personal template."""
    template = RadiologyTemplate.query.get_or_404(template_id)
    if template.created_by_user_id != current_user.id or template.origin != 'personal':
        return jsonify({'error': 'Access denied.'}), 403

    title = template.title
    try:
        db.session.delete(template)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to delete personal template {template_id}: {exc}")
        return jsonify({'error': 'Failed to delete template.'}), 500

    return jsonify({'success': True, 'message': f'Template "{title}" deleted.'})


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
    """List verified (admin-curated) templates for the Smart Reporter landing page.

    Merges results from RadiologyTemplate (plain-text PACS reports) and
    ReportingAlgorithm (interactive decision trees).
    """
    search = request.args.get('q', '').strip()
    offset = request.args.get('offset', 0, type=int)
    limit = min(request.args.get('limit', 20, type=int), 50)

    # --- RadiologyTemplate (admin, verified) ---
    rt_query = RadiologyTemplate.query.filter(
        RadiologyTemplate.is_available == True,
        RadiologyTemplate.verified_at.isnot(None),
        RadiologyTemplate.origin == 'admin',
    )
    if search:
        rt_query = rt_query.filter(
            db.or_(
                RadiologyTemplate.title.ilike(f'%{search}%'),
                RadiologyTemplate.keywords.ilike(f'%{search}%'),
                RadiologyTemplate.body_section.ilike(f'%{search}%'),
            )
        )

    # --- ReportingAlgorithm (verified) ---
    ra_query = ReportingAlgorithm.query.filter(
        ReportingAlgorithm.is_available == True,
        ReportingAlgorithm.verified_at.isnot(None),
    )
    if search:
        ra_query = ra_query.filter(
            db.or_(
                ReportingAlgorithm.title.ilike(f'%{search}%'),
                ReportingAlgorithm.keywords.ilike(f'%{search}%'),
                ReportingAlgorithm.body_section.ilike(f'%{search}%'),
            )
        )

    rt_results = rt_query.all()
    ra_results = ra_query.all()

    combined = []
    for t in rt_results:
        combined.append({
            'id': t.id,
            'slug': t.slug,
            'title': t.title,
            'category': t.category,
            'body_section': t.body_section,
            'description': t.description,
            'source_table': 'radiology_template',
            'has_algorithm': False,
            'has_pacs_report': bool(t.template_text),
            'verified_at': t.verified_at.isoformat() if t.verified_at else None,
            'created_at': t.created_at.isoformat() if t.created_at else None,
        })
    for t in ra_results:
        combined.append({
            'id': t.id,
            'slug': t.slug,
            'title': t.title,
            'category': t.category,
            'body_section': t.body_section,
            'description': t.description,
            'source_table': 'reporting_algorithm',
            'has_algorithm': bool(t.algorithm_html),
            'has_pacs_report': False,
            'verified_at': t.verified_at.isoformat() if t.verified_at else None,
            'created_at': t.created_at.isoformat() if t.created_at else None,
        })

    # Sort by verified_at descending
    combined.sort(key=lambda x: x.get('verified_at') or '', reverse=True)

    total = len(combined)
    page = combined[offset:offset + limit]

    return jsonify({
        'templates': page,
        'total': total,
        'offset': offset,
        'has_more': (offset + limit) < total,
    })


@reporting_bp.route('/api/smart-reporter/admin-templates/<int:template_id>', methods=['GET'])
@login_required
def smart_reporter_get_admin_template(template_id):
    """Get a single admin template (full content) for loading into editor.

    Checks both RadiologyTemplate and ReportingAlgorithm tables.
    The source_table query param indicates which table to look in.
    """
    source_table = request.args.get('source_table', 'reporting_algorithm')

    if source_table == 'radiology_template':
        template = RadiologyTemplate.query.get_or_404(template_id)
        if not template.is_available or not template.verified_at:
            return jsonify({'error': 'Template not available.'}), 404
        result = template.to_dict()
        result['pacs_report_text'] = template.template_text or ''
        result['has_pacs_report'] = bool(template.template_text)
        result['has_algorithm'] = False
        result['source_table'] = 'radiology_template'
        return jsonify(result)

    # Default: ReportingAlgorithm
    template = ReportingAlgorithm.query.get_or_404(template_id)
    if not template.is_available or not template.verified_at:
        return jsonify({'error': 'Template not available.'}), 404

    result = template.to_dict()
    result['algorithm_html'] = template.algorithm_html
    result['template_html'] = template.template_html
    result['has_algorithm'] = bool(template.algorithm_html)
    result['has_pacs_report'] = False
    result['source_table'] = 'reporting_algorithm'
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

    # --- Reporting Algorithms ---
    try:
        rt_query = ReportingAlgorithm.query.filter_by(is_available=True)
        if q:
            rt_query = rt_query.filter(
                db.or_(
                    ReportingAlgorithm.title.ilike(f'%{q}%'),
                    ReportingAlgorithm.keywords.ilike(f'%{q}%'),
                )
            )
        elif body_section:
            rt_query = rt_query.filter(ReportingAlgorithm.body_section.ilike(f'%{body_section}%'))

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
        elif body_section:
            cp_query = cp_query.filter(ClinicalProtocol.body_section.ilike(f'%{body_section}%'))

        cps = cp_query.limit(3).all()
        for p in cps:
            results.append({
                'type': 'protocol',
                'icon': 'fa-headset',
                'color': '#198754',
                'title': p.title,
                'subtitle': p.category or '',
                'url': f'/on-call-helper/protocol/{p.id}',
            })
    except Exception:
        pass

    return jsonify({'results': results[:15]})


@reporting_bp.route('/api/smart-reporter/anatomy', methods=['POST'])
@login_required
def smart_reporter_anatomy():
    """Generate or retrieve anatomy reference content for the Anatomy Panel."""
    data = request.get_json() or {}
    topic = (data.get('topic') or '').strip()
    if not topic:
        return jsonify({'error': 'Anatomy topic is required.'}), 400

    # DB-first: check for cached anatomy content
    cached = ReportingAlgorithm.query.filter(
        ReportingAlgorithm.category == 'anatomy',
        ReportingAlgorithm.is_available == True,
        db.or_(
            ReportingAlgorithm.title.ilike(f'%{topic}%'),
            ReportingAlgorithm.keywords.ilike(f'%{topic}%'),
        ),
    ).first()

    if cached and cached.template_html:
        return jsonify({
            'success': True,
            'title': cached.title,
            'content_html': cached.template_html,
            'source': 'database',
        })

    # AI fallback: generate anatomy reference
    try:
        from ai_smart_reporter import generate_anatomy_reference, SmartReporterError
        result = generate_anatomy_reference(topic)
    except Exception as exc:
        logger.error(f"Anatomy reference generation failed: {exc}")
        return jsonify({'error': f'Failed to generate anatomy reference: {exc}'}), 500

    return jsonify({
        'success': True,
        'title': result.get('title', topic.title()),
        'content_html': result.get('content_html', ''),
        'source': result.get('source', 'ai'),
        'model': result.get('model', ''),
        'token_count': result.get('token_count', 0),
    })
