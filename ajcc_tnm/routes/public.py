"""
Public Routes for AJCC TNM Staging System

Provides public-facing endpoints for browsing and viewing TNM staging data.
"""

from flask import Blueprint, request, render_template, jsonify, abort
from sqlalchemy import or_

# Import from main app's models (kept in main app for shared use)
from models import db, AJCCBodySection, AJCCDiseaseSite, AJCCDiagnosisYear, AJCCStagingData

tnm_bp = Blueprint('tnm', __name__, url_prefix='/tnm')

# Section names and slugs mapping
SECTION_INFO = {
    1: {'name': 'Staging Quick Reference', 'slug': 'quick-reference'},
    2: {'name': 'Cancers Staged Using This System', 'slug': 'cancers-staged'},
    3: {'name': 'Cancers NOT Staged by This System', 'slug': 'cancers-not-staged'},
    4: {'name': 'Summary of Changes', 'slug': 'summary-changes'},
    5: {'name': 'Identification of Primary Site', 'slug': 'primary-site'},
    6: {'name': 'Histopathologic Type', 'slug': 'histopathologic-type'},
    7: {'name': 'Clinical Staging and Workup', 'slug': 'clinical-staging-workup'},
    8: {'name': 'Staging Rules', 'slug': 'staging-rules'},
    9: {'name': 'Common Staging Scenarios', 'slug': 'common-scenarios'},
    10: {'name': 'Explanatory Notes', 'slug': 'explanatory-notes'}
}


def get_available_years_for_disease(disease_site_id):
    """Get list of available years for a disease."""
    staging_data = AJCCStagingData.query.filter_by(disease_site_id=disease_site_id).all()
    years = []
    for sd in staging_data:
        year = sd.diagnosis_year.year
        if year not in years:
            years.append(year)
    return sorted(years, reverse=True)  # Latest first


def get_staging_data_with_fallback(disease_site_id, requested_year=None):
    """
    Get staging data with year fallback logic.
    Defaults to 2026, falls back to latest available.
    """
    # Default to 2026
    if requested_year is None:
        requested_year = 2026
    
    # Get available years
    available_years = get_available_years_for_disease(disease_site_id)
    
    if not available_years:
        return None, None, None
    
    # Try requested year first
    year_to_use = requested_year
    if year_to_use not in available_years:
        # Fallback to latest available
        year_to_use = available_years[0]
    
    diagnosis_year = AJCCDiagnosisYear.query.filter_by(year=year_to_use).first()
    if not diagnosis_year:
        return None, None, None
    
    staging_data = AJCCStagingData.query.filter_by(
        disease_site_id=disease_site_id,
        diagnosis_year_id=diagnosis_year.id
    ).first()
    
    return staging_data, year_to_use, available_years


@tnm_bp.route('', methods=['GET'])
def browse():
    """Browse page - list all body sections."""
    sections = AJCCBodySection.query.order_by(
        AJCCBodySection.display_order,
        AJCCBodySection.section_name
    ).all()
    
    return render_template('tnm_browse.html', sections=sections)


@tnm_bp.route('/<section_slug>', methods=['GET'])
def section_page(section_slug):
    """List diseases in a section."""
    section = AJCCBodySection.query.filter_by(slug=section_slug).first_or_404()
    diseases = AJCCDiseaseSite.query.filter_by(
        body_section_id=section.id
    ).order_by(AJCCDiseaseSite.disease_name).all()
    
    return render_template('tnm_section.html', section=section, diseases=diseases)


@tnm_bp.route('/<section_slug>/<disease_slug>', methods=['GET'])
def disease_main_page(section_slug, disease_slug):
    """Main disease landing page with navigation sidebar."""
    section = AJCCBodySection.query.filter_by(slug=section_slug).first_or_404()
    disease_site = AJCCDiseaseSite.query.filter_by(
        body_section_id=section.id,
        slug=disease_slug
    ).first_or_404()
    
    year = request.args.get('year', type=int)
    view_mode = request.args.get('view', 'full')  # 'full' (enhanced) is now default, 'simple' for old
    from_case_id = request.args.get('from_case', type=int)  # For "Return to Case" button
    
    staging_data, year_used, available_years = get_staging_data_with_fallback(
        disease_site.id, year
    )
    
    # Use enhanced viewer by default, simple for legacy
    template = 'tnm_disease.html' if view_mode == 'simple' else 'ajcc_tnm_viewer.html'
    
    if not staging_data:
        # No data available
        return render_template(
            template,
            section=section,
            disease_site=disease_site,
            staging_data=None,
            year_used=None,
            available_years=available_years or [],
            section_info=SECTION_INFO,
            active_section=1,
            from_case_id=from_case_id
        )
    
    return render_template(
        template,
        section=section,
        disease_site=disease_site,
        staging_data=staging_data,
        year_used=year_used,
        available_years=available_years,
        section_info=SECTION_INFO,
        active_section=1,
        from_case_id=from_case_id
    )


@tnm_bp.route('/<section_slug>/<disease_slug>/viewer', methods=['GET'])
def disease_viewer_page(section_slug, disease_slug):
    """Full TNM viewer page with all sections, sidebar, and calculator."""
    section = AJCCBodySection.query.filter_by(slug=section_slug).first_or_404()
    disease_site = AJCCDiseaseSite.query.filter_by(
        body_section_id=section.id,
        slug=disease_slug
    ).first_or_404()
    
    year = request.args.get('year', type=int)
    from_case_id = request.args.get('from_case', type=int)  # For "Return to Case" button
    staging_data, year_used, available_years = get_staging_data_with_fallback(
        disease_site.id, year
    )
    
    return render_template(
        'ajcc_tnm_viewer.html',
        section=section,
        disease_site=disease_site,
        staging_data=staging_data,
        year_used=year_used,
        available_years=available_years or [],
        section_info=SECTION_INFO,
        active_section=1,
        from_case_id=from_case_id
    )


@tnm_bp.route('/check', methods=['GET'])
def check_tnm_data():
    """Check if TNM data exists for a diagnosis."""
    from flask import request
    from ..services.mapping_service import get_tnm_url_for_diagnosis
    
    diagnosis = request.args.get('diagnosis', '')
    if not diagnosis:
        return jsonify({'exists': False, 'url': None})
    
    # Get TNM URL
    url = get_tnm_url_for_diagnosis(diagnosis)
    
    return jsonify({
        'exists': url is not None,
        'url': url
    })


@tnm_bp.route('/<section_slug>/<disease_slug>/student', methods=['GET'])
def student_tnm_view(section_slug, disease_slug):
    """
    Student TNM view with case-specific features.
    
    Includes:
    - Return to Case button (if from_case_id provided)
    - Copy buttons for each section
    - Intelligent TNM data (if available)
    - Stage calculator
    """
    from models import IntelligentTNMData
    import re
    
    section = AJCCBodySection.query.filter_by(slug=section_slug).first_or_404()
    disease_site = AJCCDiseaseSite.query.filter_by(
        body_section_id=section.id,
        slug=disease_slug
    ).first_or_404()
    
    year = request.args.get('year', type=int)
    from_case_id = request.args.get('from_case', type=int)
    
    staging_data, year_used, available_years = get_staging_data_with_fallback(
        disease_site.id, year
    )
    
    # Get TNM definitions
    t_definitions = []
    n_definitions = {}
    m_definitions = []
    stage_groups = []
    explanatory_notes_html = None
    images = []
    
    if staging_data:
        t_definitions = staging_data.get_t_definitions()
        n_definitions = staging_data.get_n_definitions()
        m_definitions = staging_data.get_m_definitions()
        stage_groups = staging_data.get_stage_groups()
        explanatory_notes_html = staging_data.section_10_explanatory_notes_html
        
        # Extract images from HTML content
        for html in [staging_data.section_1_quick_reference_html, 
                     staging_data.section_7_clinical_staging_workup_html,
                     staging_data.section_10_explanatory_notes_html]:
            if html:
                img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html)
                for src in img_matches:
                    if src not in images:
                        images.append(src)
    
    # Get diagnosis year for intelligent data lookup
    diagnosis_year_id = None
    if staging_data:
        diagnosis_year_id = staging_data.diagnosis_year_id
    
    # Get intelligent TNM data if available
    intelligent_data = None
    try:
        intel_record = IntelligentTNMData.query.filter_by(
            disease_site_id=disease_site.id,
            diagnosis_year_id=diagnosis_year_id
        ).first()
        
        if intel_record:
            intelligent_data = intel_record.to_dict()
    except Exception as e:
        print(f"[TNM] Error loading intelligent data: {e}")
    
    # Build TNM version string
    tnm_version = f"AJCC 8th Edition ({year_used})" if year_used else "AJCC 8th Edition"
    
    return render_template(
        'student_tnm_view.html',
        section=section,
        disease=disease_site,
        staging_data=staging_data,
        t_definitions=t_definitions,
        n_definitions=n_definitions,
        m_definitions=m_definitions,
        stage_groups=stage_groups,
        explanatory_notes_html=explanatory_notes_html,
        images=images,
        intelligent_data=intelligent_data,
        tnm_version=tnm_version,
        year_used=year_used,
        available_years=available_years or [],
        from_case_id=from_case_id
    )


@tnm_bp.route('/<section_slug>/<disease_slug>/<section_slug_path>', methods=['GET'])
def section_page_route(section_slug, disease_slug, section_slug_path):
    """Route for individual section pages (1-10)."""
    # Map section slug to section number
    section_number = None
    for num, info in SECTION_INFO.items():
        if info['slug'] == section_slug_path:
            section_number = num
            break
    
    if not section_number:
        abort(404)
    
    section = AJCCBodySection.query.filter_by(slug=section_slug).first_or_404()
    disease_site = AJCCDiseaseSite.query.filter_by(
        body_section_id=section.id,
        slug=disease_slug
    ).first_or_404()
    
    year = request.args.get('year', type=int)
    staging_data, year_used, available_years = get_staging_data_with_fallback(
        disease_site.id, year
    )
    
    if not staging_data:
        abort(404, description="TNM data not available for this disease/year")
    
    # Get section HTML
    section_html = staging_data.get_section_html(section_number)
    
    # Determine template name
    template_map = {
        1: 'tnm_section_quick_reference.html',
        2: 'tnm_section_cancers_staged.html',
        3: 'tnm_section_cancers_not_staged.html',
        4: 'tnm_section_summary_changes.html',
        5: 'tnm_section_primary_site.html',
        6: 'tnm_section_histopathologic_type.html',
        7: 'tnm_section_clinical_staging_workup.html',
        8: 'tnm_section_staging_rules.html',
        9: 'tnm_section_common_scenarios.html',
        10: 'tnm_section_explanatory_notes.html'
    }
    
    template_name = template_map.get(section_number)
    if not template_name:
        abort(404)
    
    return render_template(
        template_name,
        section=section,
        disease_site=disease_site,
        staging_data=staging_data,
        section_number=section_number,
        section_name=SECTION_INFO[section_number]['name'],
        section_html=section_html,
        year_used=year_used,
        available_years=available_years,
        section_info=SECTION_INFO
    )


# ============================================================================
# API Endpoints for TNM Intelligence
# ============================================================================

@tnm_bp.route('/api/generate', methods=['POST'])
def generate_tnm_intelligence_api():
    """
    API endpoint to generate TNM intelligence using Claude.
    
    Request body:
    {
        "diagnosis": "Lung cancer",
        "original_diagnosis": "Laryngeal cancer with lung metastasis",  // optional
        "module": "Chest",  // optional
        "body_part": "Lung",  // optional
        "case_id": 123,  // optional
        "primary_site_override": "Larynx"  // optional - user-selected primary site
    }
    
    Returns generated TNM intelligence data.
    Admin authentication required.
    """
    from flask_login import current_user, login_required
    from models import UserRole
    
    # Check authentication
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    # Check admin/content manager role
    if current_user.role not in [UserRole.ADMIN, UserRole.CONTENT_MANAGER]:
        return jsonify({'error': 'Admin or Content Manager role required'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    diagnosis = data.get('diagnosis', '').strip()
    original_diagnosis = data.get('original_diagnosis', '').strip() or diagnosis
    primary_site_override = data.get('primary_site_override', '').strip() or None
    
    if not diagnosis:
        return jsonify({'error': 'Diagnosis is required'}), 400
    
    module = data.get('module', '').strip() or None
    body_part = data.get('body_part', '').strip() or None
    case_id = data.get('case_id')
    
    try:
        from ai_tnm import generate_tnm_intelligence, _map_to_ajcc_site
        
        # If user specified a primary site, use that for lookup
        effective_diagnosis = diagnosis
        if primary_site_override:
            # Use the override for AJCC matching
            effective_diagnosis = f"{primary_site_override} cancer"
        
        result = generate_tnm_intelligence(
            diagnosis=effective_diagnosis,
            module=module,
            body_part=body_part,
            from_case_id=case_id,
            provider="claude"
        )
        
        # Store original diagnosis in result for reference
        if original_diagnosis != effective_diagnosis:
            result['original_diagnosis'] = original_diagnosis
        
        # Also include the raw staging tables data from Quick Reference
        staging_tables = {}
        ajcc_match = result.get('ajcc_match', {})
        disease_site_id = ajcc_match.get('disease_site_id')
        
        if disease_site_id:
            # Get staging data for this disease
            staging_data, year_used, available_years = get_staging_data_with_fallback(disease_site_id)
            if staging_data:
                # Extract images from explanatory notes
                import re
                explanatory_html = staging_data.section_10_explanatory_notes_html or ""
                images = []
                if explanatory_html:
                    img_matches = re.findall(r'<img[^>]+src="([^"]+)"', explanatory_html)
                    images = img_matches[:10]  # Limit to 10 images
                
                staging_tables = {
                    't_definitions': staging_data.get_t_definitions() or [],
                    'n_definitions': staging_data.get_n_definitions() or {},
                    'm_definitions': staging_data.get_m_definitions() or [],
                    'stage_groups': staging_data.get_stage_groups() or [],
                    'quick_reference_html': staging_data.section_1_quick_reference_html,
                    'explanatory_notes_html': explanatory_html,
                    'images': images,
                    'year_used': year_used,
                    'available_years': available_years or []
                }
        
        result['staging_tables'] = staging_tables
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@tnm_bp.route('/api/check', methods=['GET'])
def check_tnm_available_api():
    """
    Check if TNM intelligence is available for a diagnosis.
    
    Query params:
    - diagnosis: Cancer diagnosis text
    - module: FRCR module (optional)
    - body_part: Body part (optional)
    - case_id: Case ID for link generation (optional)
    
    Returns:
    {
        "is_oncologic": true/false,
        "has_staging_data": true/false,
        "tnm_link": "/tnm/...",
        "disease_name": "Lung",
        "can_generate": true/false
    }
    """
    diagnosis = request.args.get('diagnosis', '').strip()
    if not diagnosis:
        return jsonify({'is_oncologic': False})
    
    module = request.args.get('module', '').strip() or None
    body_part = request.args.get('body_part', '').strip() or None
    case_id = request.args.get('case_id', type=int)
    
    try:
        from ai_tnm import is_oncologic_diagnosis, get_tnm_reference_only
        
        is_oncologic = is_oncologic_diagnosis(diagnosis)
        
        if not is_oncologic:
            return jsonify({
                'is_oncologic': False,
                'has_staging_data': False,
                'tnm_link': None,
                'can_generate': False
            })
        
        ref = get_tnm_reference_only(
            diagnosis=diagnosis,
            module=module,
            body_part=body_part,
            from_case_id=case_id
        )
        
        if ref:
            return jsonify({
                'is_oncologic': True,
                'has_staging_data': ref.get('has_staging_data', False),
                'tnm_link': ref.get('tnm_link'),
                'disease_name': ref['ajcc_match'].get('disease_name'),
                'can_generate': ref.get('has_staging_data', False)
            })
        else:
            return jsonify({
                'is_oncologic': True,
                'has_staging_data': False,
                'tnm_link': None,
                'disease_name': None,
                'can_generate': False,
                'message': 'TNM data not yet available for this cancer type'
            })
            
    except Exception as e:
        return jsonify({
            'is_oncologic': True,
            'error': str(e)
        }), 500


@tnm_bp.route('/api/check-candidates', methods=['GET'])
def check_tnm_candidates_api():
    """
    Get ALL possible cancer site candidates from a diagnosis.
    
    This allows the user to choose the correct primary site
    instead of relying on automatic matching.
    
    Query params:
    - diagnosis: Cancer diagnosis text
    - module: FRCR module (optional)
    - body_part: Body part (optional)
    
    Returns:
    {
        "is_oncologic": true/false,
        "candidates": [
            {
                "disease_site_id": 1,
                "disease_name": "Larynx",
                "section_name": "Head and Neck",
                "tnm_link": "/tnm/head-and-neck/larynx/student",
                "has_staging_data": true,
                "score": 25,
                "is_recommended": true
            },
            ...
        ]
    }
    """
    diagnosis = request.args.get('diagnosis', '').strip()
    if not diagnosis:
        return jsonify({'is_oncologic': False, 'candidates': []})
    
    module = request.args.get('module', '').strip() or None
    body_part = request.args.get('body_part', '').strip() or None
    
    try:
        from ai_tnm import is_oncologic_diagnosis, get_all_candidate_sites
        
        is_oncologic = is_oncologic_diagnosis(diagnosis)
        
        if not is_oncologic:
            return jsonify({
                'is_oncologic': False,
                'candidates': []
            })
        
        candidates = get_all_candidate_sites(
            diagnosis=diagnosis,
            module=module,
            body_part=body_part,
            min_score=1  # Include all with any match
        )
        
        # Filter to only include those with staging data, but keep others for "Other" option
        # Actually, let's return all and let JS filter
        return jsonify({
            'is_oncologic': True,
            'candidates': candidates
        })
            
    except Exception as e:
        return jsonify({
            'is_oncologic': True,
            'candidates': [],
            'error': str(e)
        }), 500


@tnm_bp.route('/api/check-existing-intelligence', methods=['GET'])
def check_existing_intelligence_api():
    """
    Check if intelligent TNM data already exists for a case.
    
    Query params:
    - case_id: Case ID to check
    - disease_site_id: Disease site ID (optional, for more specific check)
    
    Returns existing intelligent data if found.
    """
    from models import IntelligentTNMData, Case
    
    case_id = request.args.get('case_id', type=int)
    disease_site_id = request.args.get('disease_site_id', type=int)
    
    if not case_id:
        return jsonify({'exists': False, 'message': 'No case_id provided'})
    
    try:
        # Check if case has stored intelligent TNM data
        case = Case.query.get(case_id)
        if not case:
            return jsonify({'exists': False, 'message': 'Case not found'})
        
        # Look for intelligent data associated with this case's disease site
        if disease_site_id:
            intel_data = IntelligentTNMData.query.filter_by(
                disease_site_id=disease_site_id
            ).first()
        else:
            # Try to find any intelligent data that might be relevant
            intel_data = None
        
        if intel_data:
            return jsonify({
                'exists': True,
                'data': intel_data.to_dict(),
                'generated_at': intel_data.created_at.isoformat() if intel_data.created_at else None,
                'disease_site_id': intel_data.disease_site_id
            })
        else:
            return jsonify({'exists': False})
            
    except Exception as e:
        return jsonify({'exists': False, 'error': str(e)})


@tnm_bp.route('/api/disease-sites', methods=['GET'])
def get_ajcc_disease_sites_api():
    """
    Get list of all known AJCC disease sites.
    Used for validation when user enters custom primary site.
    """
    try:
        disease_sites = AJCCDiseaseSite.query.order_by(AJCCDiseaseSite.disease_name).all()
        sites = [ds.disease_name for ds in disease_sites]
        return jsonify({
            'success': True,
            'sites': sites,
            'count': len(sites)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'sites': []
        }), 500


@tnm_bp.route('/api/save-intelligence', methods=['POST'])
def save_tnm_intelligence_api():
    """
    Save verified TNM intelligence to database.
    
    Called when admin verifies and saves case data.
    Stores the AI-generated TNM intelligence for reuse.
    
    Request body:
    {
        "disease_site_id": 123,
        "diagnosis_year_id": 1,  // optional
        "source_case_id": 456,  // optional
        "tnm_intelligence": { ... AI output ... }
    }
    """
    from flask_login import current_user
    from models import UserRole, IntelligentTNMData
    
    # Check authentication
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    # Check admin/content manager role
    if current_user.role not in [UserRole.ADMIN, UserRole.CONTENT_MANAGER]:
        return jsonify({'error': 'Admin or Content Manager role required'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    disease_site_id = data.get('disease_site_id')
    if not disease_site_id:
        return jsonify({'error': 'disease_site_id is required'}), 400
    
    # Support both nested format (from case editor) and flat format (from student view editor)
    tnm_intelligence = data.get('tnm_intelligence')
    if not tnm_intelligence:
        # Flat format - convert to nested format
        tnm_intelligence = {
            'tnm_memory_aid': data.get('tnm_memory_aid', {}),
            'radiologist_key_points': data.get('radiologist_key_points', []),
            'upstaging_triggers': data.get('upstaging_triggers', []),
            'mdt_critical_findings': data.get('mdt_critical_findings', []),
            'copy_blocks': data.get('copy_blocks', {}),
            'imaging_checklist': data.get('imaging_checklist', []),
            'reference_images': data.get('reference_images', []),
            'warnings': data.get('warnings', [])
        }
    
    # Validate that we have some data
    if not any([tnm_intelligence.get('tnm_memory_aid'), 
                tnm_intelligence.get('radiologist_key_points'),
                tnm_intelligence.get('upstaging_triggers')]):
        return jsonify({'error': 'No intelligence data provided'}), 400
    
    diagnosis_year_id = data.get('diagnosis_year_id')
    source_case_id = data.get('source_case_id')
    
    try:
        # Check if record already exists
        existing = IntelligentTNMData.query.filter_by(
            disease_site_id=disease_site_id,
            diagnosis_year_id=diagnosis_year_id
        ).first()
        
        if existing:
            # Update existing record
            existing.tnm_memory_aid_t = tnm_intelligence.get('tnm_memory_aid', {}).get('T')
            existing.tnm_memory_aid_n = tnm_intelligence.get('tnm_memory_aid', {}).get('N')
            existing.tnm_memory_aid_m = tnm_intelligence.get('tnm_memory_aid', {}).get('M')
            existing.set_radiologist_key_points(tnm_intelligence.get('radiologist_key_points', []))
            existing.set_upstaging_triggers(tnm_intelligence.get('upstaging_triggers', []))
            existing.set_mdt_critical_findings(tnm_intelligence.get('mdt_critical_findings', []))
            existing.set_copy_blocks(tnm_intelligence.get('copy_blocks', {}))
            existing.set_imaging_checklist(tnm_intelligence.get('imaging_checklist', []))
            existing.set_reference_images(tnm_intelligence.get('reference_images', []))
            existing.set_warnings(tnm_intelligence.get('warnings', []))
            existing.verified_by_user_id = current_user.id
            existing.version += 1
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'TNM intelligence updated',
                'id': existing.id,
                'version': existing.version
            })
        else:
            # Create new record
            intel_data = IntelligentTNMData.from_ai_output(
                ai_output=tnm_intelligence,
                disease_site_id=disease_site_id,
                diagnosis_year_id=diagnosis_year_id,
                verified_by_user_id=current_user.id,
                source_case_id=source_case_id
            )
            
            db.session.add(intel_data)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'TNM intelligence saved',
                'id': intel_data.id,
                'version': 1
            })
            
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
