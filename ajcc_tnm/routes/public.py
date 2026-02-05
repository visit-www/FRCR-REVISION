"""
Public Routes for AJCC TNM Staging System

Provides public-facing endpoints for browsing and viewing TNM staging data.
"""

from flask import Blueprint, request, render_template, jsonify, abort
from flask_login import current_user
from sqlalchemy import or_

# Import from main app's models (kept in main app for shared use)
from models import db, AJCCBodySection, AJCCDiseaseSite, AJCCDiagnosisYear, AJCCStagingData
from ai_tnm import format_tnm_version

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


def strip_expired_ajcc_images(html_content):
    """
    Remove AJCC images with expired JWT tokens from HTML content.
    
    These images are hosted at ajcc.deploy.heretto.com and require JWT tokens
    that expire, causing 403 errors in the browser.
    
    Args:
        html_content: HTML string containing img tags
        
    Returns:
        HTML string with AJCC image tags removed
    """
    import re
    if not html_content:
        return html_content
    
    # Remove img tags with ajcc.deploy.heretto.com URLs
    # Matches: <img ... src="https://ajcc.deploy.heretto.com/..." ... />
    pattern = r'<img[^>]*src=["\'][^"\']*ajcc\.deploy\.heretto\.com[^"\']*["\'][^>]*/?\s*>'
    
    # Also remove figure elements that contain only the broken image
    # This cleans up empty figure containers
    cleaned = re.sub(pattern, '', html_content, flags=re.IGNORECASE)
    
    # Remove empty figure elements (figure with only whitespace/caption but no img)
    cleaned = re.sub(r'<figure[^>]*>\s*(<figcaption[^>]*>.*?</figcaption>)?\s*</figure>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    
    return cleaned


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
    ).order_by(AJCCDiseaseSite.display_order, AJCCDiseaseSite.disease_name).all()
    
    return render_template('tnm_section.html', section=section, diseases=diseases)


@tnm_bp.route('/<section_slug>/<disease_slug>', methods=['GET'])
def disease_main_page(section_slug, disease_slug):
    """
    Main disease landing page.
    - Admins: Can choose between raw AJCC data (ajcc_tnm_viewer.html) or curated view (view_tnm.html)
    - Students/Others: Redirected to curated view (view_tnm.html)
    """
    from flask import redirect, url_for
    
    section = AJCCBodySection.query.filter_by(slug=section_slug).first_or_404()
    disease_site = AJCCDiseaseSite.query.filter_by(
        body_section_id=section.id,
        slug=disease_slug
    ).first_or_404()
    
    year = request.args.get('year', type=int)
    view_mode = request.args.get('view', default='curated')  # 'raw' for AJCC viewer, 'curated' for view_tnm
    from_case_id = request.args.get('from_case', type=int)
    
    # Check if user is admin
    is_admin = False
    try:
        if current_user.is_authenticated and hasattr(current_user, 'role') and current_user.role:
            role_value = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
            is_admin = role_value in ['admin', 'superadmin', 'content_manager']
    except Exception:
        is_admin = False
    
    # Non-admins always go to curated view
    if not is_admin:
        return redirect(url_for('tnm.tnm_view', section_slug=section_slug, disease_slug=disease_slug, 
                                year=year, from_case=from_case_id))
    
    # Admins: Check view_mode parameter
    if view_mode == 'curated':
        return redirect(url_for('tnm.tnm_view', section_slug=section_slug, disease_slug=disease_slug,
                                year=year, from_case=from_case_id))
    
    # Admin viewing raw AJCC data
    staging_data, year_used, available_years = get_staging_data_with_fallback(
        disease_site.id, year
    )
    
    template = 'ajcc_tnm_viewer.html'
    
    if not staging_data:
        return render_template(
            template,
            section=section,
            disease_site=disease_site,
            staging_data=None,
            year_used=None,
            available_years=available_years or [],
            section_info=SECTION_INFO,
            active_section=1,
            from_case_id=from_case_id,
            is_admin=is_admin
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
        from_case_id=from_case_id,
        is_admin=is_admin
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


@tnm_bp.route('/<section_slug>/<disease_slug>/view', methods=['GET'])
@tnm_bp.route('/<section_slug>/<disease_slug>/student', methods=['GET'])  # Backward compatibility
def tnm_view(section_slug, disease_slug):
    """
    Unified TNM view for both students and admins.
    
    Shows role-appropriate UI:
    - Students: Notes, highlights, study tools
    - Admins: Edit buttons, management links
    
    Features:
    - Return to Case button (if from_case_id provided)
    - Intelligent TNM data (if available)
    - Role-based UI rendering
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
    
    # Check if user is admin (admins can see raw data, students only see curated)
    is_admin = False
    try:
        if current_user.is_authenticated and hasattr(current_user, 'role') and current_user.role:
            role_value = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
            is_admin = role_value in ['admin', 'superadmin', 'content_manager']
    except Exception as e:
        print(f"[TNM] Error checking admin status: {e}")
        is_admin = False
    
    # Get TNM definitions
    t_definitions = []
    n_definitions = {}
    m_definitions = []
    stage_groups = []
    clinical_prognostic_stage_groups = []
    explanatory_notes_html = None
    quick_reference_html = None
    curated_quick_reference = None  # Admin's additional notes for quick reference
    images = []
    is_curated = False
    cancers_staged = []
    cancers_not_staged = []
    
    if staging_data:
        # Check if curated data exists
        is_curated = staging_data.is_curated
        
        # Get curated quick reference notes (admin's additional comments) - always show if exists
        curated_quick_reference = staging_data.curated_quick_reference_html
        
        # Show curated content if available, otherwise show raw extracted data
        # Both admins and students can see content, but students get a warning if not curated
        if is_curated:
            # Use curated content (preferred)
            quick_reference_html = staging_data.curated_quick_reference_html
            explanatory_notes_html = staging_data.curated_explanatory_notes_html
        else:
            # Show raw extracted data with warning
            # This allows students to access content immediately while curation is in progress
            quick_reference_html = staging_data.section_1_quick_reference_html
            explanatory_notes_html = staging_data.section_10_explanatory_notes_html
        
        # Strip expired AJCC images to prevent 403 console errors
        explanatory_notes_html = strip_expired_ajcc_images(explanatory_notes_html)
        
        # Always try to get structured TNM definitions (from JSON)
        t_definitions = staging_data.get_t_definitions()
        n_definitions = staging_data.get_n_definitions()
        m_definitions = staging_data.get_m_definitions()
        stage_groups = staging_data.get_stage_groups()
        
        # Get clinical prognostic stage groups (for cancers like Breast that use biomarkers)
        # This is stored inside tnm_data_json, not as a separate field
        if staging_data.tnm_data_json:
            import json
            tnm_data = staging_data.tnm_data_json
            if isinstance(tnm_data, str):
                tnm_data = json.loads(tnm_data)
            clinical_prognostic_stage_groups = tnm_data.get('clinical_prognostic_stage_groups', [])
        
        # Get cancers staged and not staged (handle nested JSON structure)
        cancers_staged_data = staging_data.get_json_section('cancers_staged') or {}
        cancers_not_staged_data = staging_data.get_json_section('cancers_not_staged') or {}
        
        # Extract cancer list from various JSON formats
        cancers_staged = []
        if isinstance(cancers_staged_data, dict):
            # Handle {"cancers": [...], "text": "..."} format
            if cancers_staged_data.get('cancers'):
                cancers_staged = cancers_staged_data['cancers']
            elif cancers_staged_data.get('text'):
                # Parse text if cancers array is empty
                cancers_staged = [cancers_staged_data['text']]
        elif isinstance(cancers_staged_data, list):
            cancers_staged = cancers_staged_data
        
        cancers_not_staged = []
        if isinstance(cancers_not_staged_data, dict):
            # Handle {"exclusions": [{cancer_type: ..., staged_according_to: ...}]} format
            if cancers_not_staged_data.get('exclusions'):
                cancers_not_staged = [
                    f"{exc.get('cancer_type', '')} → {exc.get('staged_according_to', '')}"
                    for exc in cancers_not_staged_data['exclusions']
                    if isinstance(exc, dict)
                ]
            elif cancers_not_staged_data.get('text'):
                cancers_not_staged = [cancers_not_staged_data['text']]
        elif isinstance(cancers_not_staged_data, list):
            cancers_not_staged = cancers_not_staged_data
        
        # Extract images from curated content if available, else from raw
        source_html = quick_reference_html or explanatory_notes_html
        if is_admin and not is_curated:
            source_html = staging_data.section_1_quick_reference_html or staging_data.section_10_explanatory_notes_html
        
        if source_html:
            img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', source_html)
            for src in img_matches:
                if src not in images:
                    images.append(src)
    
    # Get diagnosis year for intelligent data lookup
    diagnosis_year_id = None
    diagnosis_year = None
    if staging_data:
        diagnosis_year_id = staging_data.diagnosis_year_id
        diagnosis_year = staging_data.diagnosis_year
    
    # Get intelligent TNM data if available
    # Query by disease_site_id only - one record per disease site regardless of year
    intelligent_data = None
    try:
        intel_record = IntelligentTNMData.query.filter_by(
            disease_site_id=disease_site.id
        ).first()
        
        if intel_record:
            intelligent_data = intel_record.to_dict()
            print(f"[TNM] Loaded intelligent data for disease {disease_site.id}, year {diagnosis_year_id}")
    except Exception as e:
        print(f"[TNM] Error loading intelligent data: {e}")
    
    # Build TNM version string using the AJCC_VERSION_9_DISEASES dictionary
    # Returns "AJCC 9th Edition (year)" for 9th Edition cancers, "AJCC 8th Edition" for others
    try:
        tnm_version = format_tnm_version(disease_slug)
    except Exception as e:
        print(f"[TNM] Error formatting TNM version: {e}")
        tnm_version = "AJCC Staging"
    
    # Get current date for footer
    from datetime import datetime
    current_date = datetime.utcnow()
    
    # Get user's TNM note for students (pre-load for auto-save textarea)
    user_tnm_note = None
    try:
        if current_user.is_authenticated:
            from models import CandidateNote
            user_tnm_note = CandidateNote.query.filter_by(
                tnm_disease_id=disease_site.id,
                user_id=current_user.id
            ).first()
    except Exception as e:
        print(f"[TNM] Error loading user note: {e}")
    
    try:
        return render_template(
            'view_tnm.html',
            section=section,
            disease=disease_site,
            staging_data=staging_data,
            t_definitions=t_definitions,
            n_definitions=n_definitions,
            m_definitions=m_definitions,
            stage_groups=stage_groups,
            clinical_prognostic_stage_groups=clinical_prognostic_stage_groups,
            cancers_staged=cancers_staged,
            cancers_not_staged=cancers_not_staged,
            quick_reference_html=quick_reference_html,
            curated_quick_reference=curated_quick_reference,
            explanatory_notes_html=explanatory_notes_html,
            images=images,
            intelligent_data=intelligent_data,
            tnm_version=tnm_version,
            year_used=year_used,
            available_years=available_years or [],
            from_case_id=from_case_id,
            is_curated=is_curated,
            is_admin=is_admin,
            current_date=current_date,
            diagnosis_year=diagnosis_year,
            user_tnm_note=user_tnm_note
        )
    except Exception as e:
        import traceback
        print(f"[TNM] Error rendering view_tnm template: {e}")
        traceback.print_exc()
        # Return a simple error page instead of blank
        from flask import abort
        abort(500, description=f"Template rendering error: {str(e)}")


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
    model = data.get('model', 'claude-sonnet-4-20250514')  # Default to Sonnet for cost efficiency

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
            provider="claude",
            model=model
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
    
    Returns:
    {
        "is_oncologic": true/false,
        "has_staging_data": true/false,
        "disease_name": "Lung",
        "can_generate": true/false
    }
    """
    diagnosis = request.args.get('diagnosis', '').strip()
    if not diagnosis:
        return jsonify({'is_oncologic': False})
    
    module = request.args.get('module', '').strip() or None
    body_part = request.args.get('body_part', '').strip() or None
    
    try:
        from ai_tnm import is_oncologic_diagnosis, _map_to_ajcc_site
        
        is_oncologic = is_oncologic_diagnosis(diagnosis)
        
        if not is_oncologic:
            return jsonify({
                'is_oncologic': False,
                'has_staging_data': False,
                'can_generate': False
            })
        
        ajcc_match = _map_to_ajcc_site(diagnosis, module, body_part)
        
        if ajcc_match:
            return jsonify({
                'is_oncologic': True,
                'has_staging_data': ajcc_match.get('has_staging_data', False),
                'disease_name': ajcc_match.get('disease_name'),
                'can_generate': ajcc_match.get('has_staging_data', False)
            })
        else:
            return jsonify({
                'is_oncologic': True,
                'has_staging_data': False,
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
    Check if intelligent TNM data already exists for a disease site.
    
    Query params:
    - disease_site_id: Disease site ID (required) - TNM intelligence is stored per disease site
    - case_id: Case ID (optional) - for backward compatibility
    
    Returns existing intelligent data if found.
    """
    from models import IntelligentTNMData, Case
    
    disease_site_id = request.args.get('disease_site_id', type=int)
    case_id = request.args.get('case_id', type=int)
    
    # disease_site_id is required for lookup
    if not disease_site_id:
        return jsonify({'exists': False, 'message': 'No disease_site_id provided'})
    
    try:
        # Optionally verify case exists (for backward compatibility)
        if case_id:
            case = Case.query.get(case_id)
            if not case:
                print(f"[TNM] Warning: case_id={case_id} not found, continuing with disease_site_id lookup")
        
        # Look for intelligent data by disease_site_id
        # TNM intelligence is stored once per disease site, not per case
        intel_data = IntelligentTNMData.query.filter_by(
            disease_site_id=disease_site_id
        ).first()
        
        if intel_data:
            print(f"[TNM] Found existing intelligence for disease_site_id={disease_site_id}, ID={intel_data.id}, version={intel_data.version}")
            return jsonify({
                'exists': True,
                'data': intel_data.to_dict(),
                'generated_at': intel_data.created_at.isoformat() if intel_data.created_at else None,
                'disease_site_id': intel_data.disease_site_id,
                'version': intel_data.version
            })
        else:
            print(f"[TNM] No existing intelligence found for disease_site_id={disease_site_id}")
            return jsonify({'exists': False})
            
    except Exception as e:
        print(f"[TNM] Error checking existing intelligence: {e}")
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


@tnm_bp.route('/api/images/<int:disease_site_id>', methods=['GET'])
def get_tnm_images_public(disease_site_id):
    """
    Get all images for a disease site (public read access).
    This endpoint is accessible to all authenticated users for viewing.
    """
    from models import TNMImage
    
    try:
        images = TNMImage.get_for_disease(disease_site_id)
        return jsonify({
            'success': True,
            'images': [img.to_dict() for img in images]
        })
    except Exception as e:
        print(f"[TNM] Error fetching images: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


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
        # Check if record already exists for this disease site
        # IMPORTANT: Query by disease_site_id ONLY to ensure we update existing records
        # regardless of diagnosis_year_id. This prevents duplicate records when
        # diagnosis_year_id is not passed from frontend (which is common).
        # We store one intelligence record per disease site.
        existing = IntelligentTNMData.query.filter_by(
            disease_site_id=disease_site_id
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
            existing.set_essential_tnm(tnm_intelligence.get('essential_tnm'))
            existing.verified_by_user_id = current_user.id
            existing.version += 1
            # Update diagnosis_year_id if provided (useful for tracking)
            if diagnosis_year_id:
                existing.diagnosis_year_id = diagnosis_year_id
            # Update source_case_id if provided
            if source_case_id:
                existing.source_case_id = source_case_id
            
            db.session.commit()
            
            print(f"[TNM Intelligence] Updated existing record ID={existing.id} for disease_site_id={disease_site_id}, version={existing.version}")
            
            return jsonify({
                'success': True,
                'message': 'TNM intelligence updated',
                'id': existing.id,
                'version': existing.version
            })
        else:
            # Create new record (first time for this disease site)
            print(f"[TNM Intelligence] Creating new record for disease_site_id={disease_site_id}")
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


@tnm_bp.route('/api/save-staging-data', methods=['POST'])
def save_staging_data_api():
    """
    Save editable staging data (stage groups, explanatory notes) from student view.
    
    Admin-only endpoint for inline editing.
    
    Request body:
    {
        "disease_site_id": 123,
        "year": 2026,
        "section": "stage_groups" | "explanatory_notes" | "cancers_staged" | "cancers_not_staged",
        "data": [...] or "html content"
    }
    """
    from flask_login import current_user
    from models import UserRole
    from datetime import datetime
    import json
    
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
    year = data.get('year', 2026)
    section = data.get('section')
    section_data = data.get('data')
    
    if not disease_site_id or not section:
        return jsonify({'error': 'disease_site_id and section are required'}), 400
    
    try:
        # Find the staging data record
        staging = AJCCStagingData.query.filter_by(
            disease_site_id=disease_site_id
        ).first()
        
        if not staging:
            return jsonify({'error': 'Staging data not found'}), 404
        
        if section == 'stage_groups':
            # Update stage_groups within tnm_data_json
            tnm_data = staging.get_tnm_data() or {}
            tnm_data['stage_groups'] = section_data
            staging.tnm_data_json = json.dumps(tnm_data)
            
        elif section == 'explanatory_notes':
            # Update curated explanatory notes
            staging.curated_explanatory_notes_html = section_data
            staging.is_curated = True
            staging.curated_at = datetime.utcnow()
            staging.curated_by_user_id = current_user.id
            
        elif section == 'cancers_staged':
            # Update cancers staged JSON
            staging.cancers_staged_json = json.dumps(section_data) if isinstance(section_data, list) else section_data
            
        elif section == 'cancers_not_staged':
            # Update cancers not staged JSON
            staging.cancers_not_staged_json = json.dumps(section_data) if isinstance(section_data, list) else section_data
            
        else:
            return jsonify({'error': f'Unknown section: {section}'}), 400
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{section} updated successfully',
            'section': section
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== TNM STUDENT TOOLS API ====================

@tnm_bp.route('/api/<int:disease_id>/note', methods=['GET', 'POST', 'DELETE'])
def tnm_note_api(disease_id):
    """
    Handle TNM disease-specific notes for students.
    GET: Retrieve user's notes for this TNM disease
    POST: Save/update notes
    DELETE: Delete notes
    """
    from flask_login import current_user
    from models import CandidateNote, UserRole
    
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    # Only students can use notes
    if current_user.role not in [UserRole.STUDENT, UserRole.ADMIN]:
        return jsonify({'error': 'Notes are for students only'}), 403
    
    if request.method == 'GET':
        note = CandidateNote.query.filter_by(
            tnm_disease_id=disease_id,
            user_id=current_user.id
        ).first()
        
        return jsonify({
            'success': True,
            'note_text': note.note_text if note else '',
            'updated_at': note.updated_at.isoformat() if note else None
        })
    
    elif request.method == 'POST':
        data = request.get_json()
        note_text = data.get('note_text', '').strip()
        
        existing = CandidateNote.query.filter_by(
            tnm_disease_id=disease_id,
            user_id=current_user.id
        ).first()
        
        # If note is empty, delete existing record instead of saving empty
        if not note_text:
            if existing:
                db.session.delete(existing)
                db.session.commit()
                return jsonify({'success': True, 'message': 'Note deleted (was empty)'})
            else:
                # Don't create empty record
                return jsonify({'success': True, 'message': 'No note to save (empty)'})
        
        if existing:
            existing.note_text = note_text
        else:
            new_note = CandidateNote(
                tnm_disease_id=disease_id,
                user_id=current_user.id,
                note_text=note_text
            )
            db.session.add(new_note)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Note saved'})
    
    elif request.method == 'DELETE':
        CandidateNote.query.filter_by(
            tnm_disease_id=disease_id,
            user_id=current_user.id
        ).delete()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Note deleted'})


@tnm_bp.route('/api/<int:disease_id>/highlights', methods=['GET'])
def tnm_highlights_get(disease_id):
    """Get all highlights for a TNM disease for the current user."""
    from flask_login import current_user
    from models import TextHighlight, UserRole
    
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    highlights = TextHighlight.query.filter_by(
        tnm_disease_id=disease_id,
        user_id=current_user.id
    ).all()
    
    return jsonify({
        'success': True,
        'highlights': [{
            'id': h.id,
            'text_content': h.text_content,
            'highlight_color': h.highlight_color,
            'field_name': h.field_name,
            'context_before': h.context_before,
            'context_after': h.context_after
        } for h in highlights]
    })


@tnm_bp.route('/api/<int:disease_id>/highlight', methods=['POST'])
def tnm_highlight_create(disease_id):
    """Create a new highlight for a TNM disease."""
    from flask_login import current_user
    from models import TextHighlight, UserRole
    
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    data = request.get_json()
    
    highlight = TextHighlight(
        tnm_disease_id=disease_id,
        user_id=current_user.id,
        text_content=data.get('text_content', ''),
        highlight_color=data.get('highlight_color', 'yellow'),
        field_name=data.get('field_name', 'tnm_content'),
        context_before=data.get('context_before', ''),
        context_after=data.get('context_after', '')
    )
    
    db.session.add(highlight)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'highlight_id': highlight.id,
        'message': 'Highlight created'
    })


@tnm_bp.route('/api/highlight/<int:highlight_id>', methods=['DELETE'])
def tnm_highlight_delete(highlight_id):
    """Delete a highlight."""
    from flask_login import current_user
    from models import TextHighlight
    
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    highlight = TextHighlight.query.get(highlight_id)
    if not highlight:
        return jsonify({'error': 'Highlight not found'}), 404
    
    if highlight.user_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    
    db.session.delete(highlight)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Highlight deleted'})


@tnm_bp.route('/api/<int:disease_id>/forum/messages', methods=['GET'])
def tnm_forum_messages(disease_id):
    """Get all forum messages for a TNM disease."""
    from flask_login import current_user
    from models import ForumMessage, ForumMessageVote, UserRole
    
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    messages = ForumMessage.query.filter_by(
        tnm_disease_id=disease_id,
        is_deleted=False
    ).order_by(
        ForumMessage.is_pinned.desc(),
        ForumMessage.vote_score.desc(),
        ForumMessage.created_at.desc()
    ).all()
    
    # Get user's votes for these messages
    msg_ids = [m.id for m in messages]
    user_votes = {v.message_id: v.vote_value for v in ForumMessageVote.query.filter(
        ForumMessageVote.message_id.in_(msg_ids),
        ForumMessageVote.user_id == current_user.id
    ).all()} if msg_ids else {}
    
    return jsonify({
        'success': True,
        'messages': [{
            'id': m.id,
            'content': m.content,
            'author_display_name': m.author.display_name or 'Anonymous',
            'vote_score': m.vote_score,
            'is_pinned': m.is_pinned,
            'user_vote': user_votes.get(m.id, 0),
            'is_own': m.user_id == current_user.id,
            'image_url': m.image_url,
            'image_thumbnail_url': m.image_thumbnail_url,
            'created_at': m.created_at.isoformat(),
            'flag_count': m.flag_count
        } for m in messages]
    })


@tnm_bp.route('/api/<int:disease_id>/forum/message', methods=['POST'])
def tnm_forum_message_create(disease_id):
    """Create a new forum message for a TNM disease."""
    from flask_login import current_user
    from models import ForumMessage, UserRole
    
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    data = request.get_json()
    content = data.get('content', '').strip()
    
    if not content:
        return jsonify({'error': 'Message content required'}), 400
    
    message = ForumMessage(
        tnm_disease_id=disease_id,
        user_id=current_user.id,
        content=content,
        image_url=data.get('image_url'),
        image_public_id=data.get('image_public_id'),
        image_thumbnail_url=data.get('image_thumbnail_url')
    )
    
    db.session.add(message)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message_id': message.id,
        'message': 'Posted successfully'
    })