"""
Admin Routes for AJCC TNM Staging System

Provides endpoints for TNM data extraction, management, and editing.
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
import logging

# Import from main app's models (kept in main app for shared use)
from models import db, AJCCBodySection, AJCCDiseaseSite, AJCCDiagnosisYear, AJCCStagingData, AJCCDiseaseMapping

# Import from main app's access control
from access_control import require_admin

# Import from module's services
from ..services.extractor import TNMExtractor

admin_tnm_bp = Blueprint('admin_tnm', __name__, url_prefix='/api/admin/tnm')
logger = logging.getLogger(__name__)

# Section names mapping
SECTION_NAMES = {
    1: "Staging Quick Reference",
    2: "Cancers Staged Using This System",
    3: "Cancers NOT Staged by This System",
    4: "Summary of Changes",
    5: "Identification of Primary Site",
    6: "Histopathologic Type",
    7: "Clinical Staging and Workup",
    8: "Staging Rules",
    9: "Common Staging Scenarios",
    10: "Explanatory Notes"
}


@admin_tnm_bp.route('/sections', methods=['GET'])
@require_admin
def list_sections():
    """List all AJCC body sections."""
    try:
        sections = AJCCBodySection.query.order_by(AJCCBodySection.display_order, AJCCBodySection.section_name).all()
        return jsonify({
            'success': True,
            'sections': [{
                'id': s.id,
                'section_name': s.section_name,
                'slug': s.slug,
                'display_order': s.display_order
            } for s in sections]
        })
    except Exception as e:
        logger.error(f"Error listing sections: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_tnm_bp.route('/diseases', methods=['GET'])
@require_admin
def list_diseases():
    """List diseases for a section."""
    try:
        section_id = request.args.get('section_id', type=int)
        if not section_id:
            return jsonify({'success': False, 'error': 'section_id required'}), 400
        
        diseases = AJCCDiseaseSite.query.filter_by(body_section_id=section_id).order_by(AJCCDiseaseSite.disease_name).all()
        return jsonify({
            'success': True,
            'diseases': [{
                'id': d.id,
                'disease_name': d.disease_name,
                'slug': d.slug,
                'ajcc_url_path': d.ajcc_url_path,
                'body_section_id': d.body_section_id,
                # FRCR mapping fields
                'frcr_module': getattr(d, 'frcr_module', None),
                'frcr_body_part': getattr(d, 'frcr_body_part', None),
                'frcr_age_group': getattr(d, 'frcr_age_group', None),
            } for d in diseases]
        })
    except Exception as e:
        logger.error(f"Error listing diseases: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_tnm_bp.route('/staging-data', methods=['GET'])
@require_admin
def get_staging_data():
    """Get existing staging data for a disease/year."""
    try:
        disease_site_id = request.args.get('disease_site_id', type=int)
        year = request.args.get('year', 2026, type=int)
        
        if not disease_site_id:
            return jsonify({'success': False, 'error': 'disease_site_id required'}), 400
        
        diagnosis_year = AJCCDiagnosisYear.query.filter_by(year=year).first()
        if not diagnosis_year:
            return jsonify({'success': False, 'error': f'Year {year} not found'}), 404
        
        staging_data = AJCCStagingData.query.filter_by(
            disease_site_id=disease_site_id,
            diagnosis_year_id=diagnosis_year.id
        ).first()
        
        if not staging_data:
            return jsonify({
                'success': True,
                'exists': False,
                'data': None
            })
        
        disease_site = staging_data.disease_site
        return jsonify({
            'success': True,
            'exists': True,
            'data': {
                'id': staging_data.id,
                'disease_site_id': staging_data.disease_site_id,
                'disease_name': disease_site.disease_name,
                'year': year,
                'sections': {
                    'section_1': staging_data.section_1_quick_reference_html,
                    'section_2': staging_data.section_2_cancers_staged_html,
                    'section_3': staging_data.section_3_cancers_not_staged_html,
                    'section_4': staging_data.section_4_summary_changes_html,
                    'section_5': staging_data.section_5_primary_site_html,
                    'section_6': staging_data.section_6_histopathologic_type_html,
                    'section_7': staging_data.section_7_clinical_staging_workup_html,
                    'section_8': staging_data.section_8_staging_rules_html,
                    'section_9': staging_data.section_9_common_scenarios_html,
                    'section_10': staging_data.section_10_explanatory_notes_html,
                },
                'extracted_at': staging_data.extracted_at.isoformat() if staging_data.extracted_at else None,
                'last_updated_at': staging_data.last_updated_at.isoformat() if staging_data.last_updated_at else None
            }
        })
    except Exception as e:
        logger.error(f"Error getting staging data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_tnm_bp.route('/extract', methods=['POST'])
@require_admin
def extract_tnm():
    """Trigger TNM extraction for a specific disease/year combination."""
    try:
        # Check if AJCC credentials are set
        import os
        ajcc_username = os.getenv("AJCC_USERNAME")
        ajcc_password = os.getenv("AJCC_PASSWORD")
        
        if not ajcc_username or not ajcc_password:
            return jsonify({
                'success': False,
                'error': 'AJCC credentials not configured. Please set AJCC_USERNAME and AJCC_PASSWORD environment variables in your .env file.'
            }), 400
        
        data = request.get_json()
        disease_site_id = data.get('disease_site_id')
        diagnosis_year = data.get('diagnosis_year', 2026)
        section_slug = data.get('section_slug')
        disease_slug = data.get('disease_slug')
        
        if not all([disease_site_id, section_slug, disease_slug]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        # Get disease site
        disease_site = AJCCDiseaseSite.query.get(disease_site_id)
        if not disease_site:
            return jsonify({'success': False, 'error': 'Disease site not found'}), 404
        
        # Extract TNM data - pass api_path to support year-less entries
        extractor = TNMExtractor()
        api_path = disease_site.ajcc_url_path if hasattr(disease_site, 'ajcc_url_path') else None
        result = extractor.extract_tnm_for_disease(section_slug, disease_slug, diagnosis_year, api_path=api_path)
        
        if not result:
            return jsonify({
                'success': False,
                'error': 'Extraction failed - no data retrieved. This could be due to:\n'
                         '1. Authentication failure (check AJCC credentials)\n'
                         '2. No data available for this disease/year combination\n'
                         '3. AJCC website structure may have changed'
            }), 500
        
        # Save to database
        staging_data = extractor.save_to_database(result, disease_site, result.get('year', diagnosis_year), current_user.id)
        
        if not staging_data:
            return jsonify({
                'success': False,
                'error': 'Failed to save to database'
            }), 500
        
        return jsonify({
            'success': True,
            'message': 'TNM data extracted and saved successfully',
            'data': {
                'id': staging_data.id,
                'disease_site_id': staging_data.disease_site_id,
                'year': result.get('year'),
                'extracted_at': staging_data.extracted_at.isoformat() if staging_data.extracted_at else None
            }
        })
        
    except Exception as e:
        logger.error(f"Error extracting TNM: {e}")
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        # Provide more helpful error messages
        if 'AJCC_USERNAME' in error_msg or 'AJCC_PASSWORD' in error_msg:
            error_msg = 'AJCC credentials not configured. Please set AJCC_USERNAME and AJCC_PASSWORD in your .env file.'
        return jsonify({'success': False, 'error': error_msg}), 500


@admin_tnm_bp.route('/list', methods=['GET'])
@require_admin
def list_staging_data():
    """List all extracted TNM data with filters."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        section_id = request.args.get('section_id', type=int)
        year = request.args.get('year', type=int)
        
        per_page = min(per_page, 100)
        if page < 1:
            page = 1
        
        query = AJCCStagingData.query
        
        if section_id:
            query = query.join(AJCCDiseaseSite).filter(AJCCDiseaseSite.body_section_id == section_id)
        
        if year:
            query = query.join(AJCCDiagnosisYear).filter(AJCCDiagnosisYear.year == year)
        
        query = query.order_by(AJCCStagingData.extracted_at.desc())
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'data': [{
                'id': sd.id,
                'disease_site_id': sd.disease_site_id,
                'disease_name': sd.disease_site.disease_name,
                'disease_slug': sd.disease_site.slug,
                'section_name': sd.disease_site.body_section.section_name,
                'section_slug': sd.disease_site.body_section.slug,
                'year': sd.diagnosis_year.year,
                'is_curated': sd.is_curated,
                'curated_at': sd.curated_at.isoformat() if sd.curated_at else None,
                'extracted_at': sd.extracted_at.isoformat() if sd.extracted_at else None,
                'last_updated_at': sd.last_updated_at.isoformat() if sd.last_updated_at else None
            } for sd in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'page': page
        })
    except Exception as e:
        logger.error(f"Error listing staging data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_tnm_bp.route('/extraction-status', methods=['GET'])
@require_admin
def extraction_status():
    """Get extraction status for all disease sites - shows which need extraction."""
    try:
        year = request.args.get('year', 2026, type=int)
        
        # Get diagnosis year
        diagnosis_year = AJCCDiagnosisYear.query.filter_by(year=year).first()
        
        # Get all disease sites grouped by section
        sections = AJCCBodySection.query.order_by(AJCCBodySection.section_name).all()
        
        result = {
            'success': True,
            'year': year,
            'sections': [],
            'summary': {
                'total_sites': 0,
                'extracted': 0,
                'curated': 0,
                'pending': 0
            }
        }
        
        for section in sections:
            section_data = {
                'id': section.id,
                'name': section.section_name,
                'slug': section.slug,
                'diseases': [],
                'extracted_count': 0,
                'curated_count': 0,
                'total_count': 0
            }
            
            for disease in section.disease_sites:
                # Check if staging data exists for this disease + year
                staging_data = None
                if diagnosis_year:
                    staging_data = AJCCStagingData.query.filter_by(
                        disease_site_id=disease.id,
                        diagnosis_year_id=diagnosis_year.id
                    ).first()
                
                disease_info = {
                    'id': disease.id,
                    'name': disease.disease_name,
                    'slug': disease.slug,
                    'api_path': disease.ajcc_url_path,
                    'extracted': staging_data is not None,
                    'curated': staging_data.is_curated if staging_data else False,
                    'extracted_at': staging_data.extracted_at.isoformat() if staging_data and staging_data.extracted_at else None
                }
                
                section_data['diseases'].append(disease_info)
                section_data['total_count'] += 1
                result['summary']['total_sites'] += 1
                
                if staging_data:
                    section_data['extracted_count'] += 1
                    result['summary']['extracted'] += 1
                    if staging_data.is_curated:
                        section_data['curated_count'] += 1
                        result['summary']['curated'] += 1
                else:
                    result['summary']['pending'] += 1
            
            result['sections'].append(section_data)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting extraction status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_tnm_bp.route('/clean-data/<int:disease_site_id>/<int:year>', methods=['POST'])
@require_admin
def clean_staging_data(disease_site_id, year):
    """Clean DITA junk from existing staging data without re-extracting."""
    try:
        from ..services.extractor import TNMDataCleaner
        
        diagnosis_year = AJCCDiagnosisYear.query.filter_by(year=year).first()
        if not diagnosis_year:
            return jsonify({'success': False, 'error': f'Year {year} not found'}), 404
        
        staging_data = AJCCStagingData.query.filter_by(
            disease_site_id=disease_site_id,
            diagnosis_year_id=diagnosis_year.id
        ).first()
        
        if not staging_data:
            return jsonify({'success': False, 'error': 'Staging data not found'}), 404
        
        # Clean each HTML section
        sections_cleaned = 0
        for i in range(1, 11):
            section_attr = f'section_{i}_{"quick_reference" if i == 1 else ["cancers_staged", "cancers_not_staged", "summary_changes", "primary_site", "histopathologic_type", "clinical_staging_workup", "staging_rules", "common_scenarios", "explanatory_notes"][i-2] if i > 1 else ""}_html'
            
            # Map section numbers to actual attribute names
            attr_map = {
                1: 'section_1_quick_reference_html',
                2: 'section_2_cancers_staged_html',
                3: 'section_3_cancers_not_staged_html',
                4: 'section_4_summary_changes_html',
                5: 'section_5_primary_site_html',
                6: 'section_6_histopathologic_type_html',
                7: 'section_7_clinical_staging_workup_html',
                8: 'section_8_staging_rules_html',
                9: 'section_9_common_scenarios_html',
                10: 'section_10_explanatory_notes_html'
            }
            
            attr_name = attr_map.get(i)
            if attr_name and hasattr(staging_data, attr_name):
                html = getattr(staging_data, attr_name)
                if html:
                    cleaned_html = TNMDataCleaner.clean_html_section(html)
                    setattr(staging_data, attr_name, cleaned_html)
                    sections_cleaned += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Cleaned {sections_cleaned} sections for {staging_data.disease_site.disease_name}',
            'sections_cleaned': sections_cleaned
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error cleaning staging data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_tnm_bp.route('/edit/<int:disease_site_id>/<int:year>', methods=['GET'])
@require_admin
def get_all_sections_for_editing(disease_site_id, year):
    """Get all sections for a disease/year for editing."""
    try:
        diagnosis_year = AJCCDiagnosisYear.query.filter_by(year=year).first()
        if not diagnosis_year:
            return jsonify({'success': False, 'error': f'Year {year} not found'}), 404
        
        staging_data = AJCCStagingData.query.filter_by(
            disease_site_id=disease_site_id,
            diagnosis_year_id=diagnosis_year.id
        ).first()
        
        if not staging_data:
            return jsonify({'success': False, 'error': 'Staging data not found'}), 404
        
        disease_site = staging_data.disease_site
        sections = []
        
        for i in range(1, 11):
            html_content = staging_data.get_section_html(i)
            sections.append({
                'section_number': i,
                'section_name': SECTION_NAMES.get(i, f'Section {i}'),
                'html_content': html_content or ''
            })
        
        return jsonify({
            'success': True,
            'sections': sections,
            'disease_name': disease_site.disease_name,
            'year': year,
            'disease_site_id': disease_site_id
        })
    except Exception as e:
        logger.error(f"Error getting sections for editing: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_tnm_bp.route('/edit/<int:disease_site_id>/<int:year>/<int:section_number>', methods=['GET'])
@require_admin
def get_section_for_editing(disease_site_id, year, section_number):
    """Get a specific section for editing."""
    try:
        if section_number < 1 or section_number > 10:
            return jsonify({'success': False, 'error': 'Section number must be between 1 and 10'}), 400
        
        diagnosis_year = AJCCDiagnosisYear.query.filter_by(year=year).first()
        if not diagnosis_year:
            return jsonify({'success': False, 'error': f'Year {year} not found'}), 404
        
        staging_data = AJCCStagingData.query.filter_by(
            disease_site_id=disease_site_id,
            diagnosis_year_id=diagnosis_year.id
        ).first()
        
        if not staging_data:
            return jsonify({'success': False, 'error': 'Staging data not found'}), 404
        
        disease_site = staging_data.disease_site
        html_content = staging_data.get_section_html(section_number)
        
        return jsonify({
            'success': True,
            'section_number': section_number,
            'section_name': SECTION_NAMES.get(section_number, f'Section {section_number}'),
            'html_content': html_content or '',
            'disease_name': disease_site.disease_name,
            'year': year
        })
    except Exception as e:
        logger.error(f"Error getting section for editing: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_tnm_bp.route('/edit/<int:disease_site_id>/<int:year>/<int:section_number>', methods=['PUT'])
@require_admin
def update_section(disease_site_id, year, section_number):
    """Update a specific section's HTML content."""
    try:
        if section_number < 1 or section_number > 10:
            return jsonify({'success': False, 'error': 'Section number must be between 1 and 10'}), 400
        
        data = request.get_json()
        html_content = data.get('html_content', '')
        
        diagnosis_year = AJCCDiagnosisYear.query.filter_by(year=year).first()
        if not diagnosis_year:
            return jsonify({'success': False, 'error': f'Year {year} not found'}), 404
        
        staging_data = AJCCStagingData.query.filter_by(
            disease_site_id=disease_site_id,
            diagnosis_year_id=diagnosis_year.id
        ).first()
        
        if not staging_data:
            return jsonify({'success': False, 'error': 'Staging data not found'}), 404
        
        # Update the section
        staging_data.set_section_html(section_number, html_content)
        staging_data.last_updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Section updated successfully',
            'section_number': section_number,
            'section_name': SECTION_NAMES.get(section_number, f'Section {section_number}'),
            'last_updated_at': staging_data.last_updated_at.isoformat()
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating section: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_tnm_bp.route('/management', methods=['GET'])
@require_admin
def tnm_management_page():
    """Render admin TNM management page."""
    return render_template('admin_tnm_management.html')


@admin_tnm_bp.route('/set-cookies', methods=['POST'])
@require_admin
def set_manual_cookies():
    """Set manual AJCC session cookies (workaround for OAuth2 JS forms)."""
    try:
        from ..services.manual_auth_helper import set_manual_cookies, save_manual_cookies
        
        data = request.get_json()
        cookies = data.get('cookies', {})
        
        if not cookies:
            return jsonify({
                'success': False,
                'error': 'No cookies provided'
            }), 400
        
        # Set cookies
        success = set_manual_cookies(cookies)
        
        if success:
            # Save for persistence
            save_manual_cookies(cookies)
            return jsonify({
                'success': True,
                'message': 'Cookies set and verified successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Cookies set but verification failed. Check if cookies are valid.'
            }), 400
            
    except Exception as e:
        logger.error(f"Error setting manual cookies: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_tnm_bp.route('/auth-instructions', methods=['GET'])
@require_admin
def get_auth_instructions():
    """Get instructions for manual authentication."""
    from ..services.manual_auth_helper import get_cookie_instructions
    return jsonify({
        'success': True,
        'instructions': get_cookie_instructions()
    })


@admin_tnm_bp.route('/edit-page/<int:disease_site_id>/<int:year>', methods=['GET'])
@require_admin
def tnm_edit_page(disease_site_id, year):
    """Render admin TNM edit page - redirects to unified edit_tnm.html."""
    # Redirect to the curate page which now uses edit_tnm.html
    return redirect(url_for('admin_tnm.curate_tnm_page', disease_site_id=disease_site_id, year=year))


@admin_tnm_bp.route('/calculate-stage', methods=['GET'])
def calculate_stage():
    """
    Calculate prognostic stage for given T, N, M values.
    
    Query params:
        disease_site_id: Disease site ID
        year: Diagnosis year
        t: T stage value (e.g., "T1", "T2")
        n: N stage value (e.g., "N0", "N1")
        m: M stage value (e.g., "M0", "M1")
    
    Returns:
        JSON with stage result
    """
    try:
        disease_site_id = request.args.get('disease_site_id', type=int)
        year = request.args.get('year', 2026, type=int)
        t_stage = request.args.get('t', '')
        n_stage = request.args.get('n', '')
        m_stage = request.args.get('m', '')
        
        if not all([disease_site_id, t_stage, n_stage, m_stage]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters (disease_site_id, t, n, m)'
            }), 400
        
        diagnosis_year = AJCCDiagnosisYear.query.filter_by(year=year).first()
        if not diagnosis_year:
            return jsonify({
                'success': False,
                'error': f'Year {year} not found'
            }), 404
        
        staging_data = AJCCStagingData.query.filter_by(
            disease_site_id=disease_site_id,
            diagnosis_year_id=diagnosis_year.id
        ).first()
        
        if not staging_data:
            return jsonify({
                'success': False,
                'error': 'Staging data not found'
            }), 404
        
        # Calculate stage
        stage = staging_data.get_stage_for_tnm(t_stage, n_stage, m_stage)
        
        return jsonify({
            'success': True,
            'stage': stage,
            't': t_stage,
            'n': n_stage,
            'm': m_stage
        })
        
    except Exception as e:
        logger.error(f"Error calculating stage: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_tnm_bp.route('/delete/<int:disease_site_id>/<int:year>', methods=['DELETE'])
@require_admin
def delete_staging_data(disease_site_id, year):
    """
    Delete staging data for a disease/year combination.
    
    Args:
        disease_site_id: Disease site ID
        year: Diagnosis year
    
    Returns:
        JSON with success status
    """
    try:
        diagnosis_year = AJCCDiagnosisYear.query.filter_by(year=year).first()
        if not diagnosis_year:
            return jsonify({
                'success': False,
                'error': f'Year {year} not found'
            }), 404
        
        staging_data = AJCCStagingData.query.filter_by(
            disease_site_id=disease_site_id,
            diagnosis_year_id=diagnosis_year.id
        ).first()
        
        if not staging_data:
            return jsonify({
                'success': False,
                'error': 'Staging data not found'
            }), 404
        
        disease_name = staging_data.disease_site.disease_name if staging_data.disease_site else 'Unknown'
        
        db.session.delete(staging_data)
        db.session.commit()
        
        logger.info(f"Deleted staging data for {disease_name} ({year}) by user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': f'Successfully deleted staging data for {disease_name} ({year})'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting staging data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_tnm_bp.route('/disease-site/<int:disease_site_id>', methods=['GET'])
@require_admin
def get_disease_site(disease_site_id):
    """
    Get a disease site by ID with its FRCR settings.
    """
    try:
        disease_site = AJCCDiseaseSite.query.get(disease_site_id)
        if not disease_site:
            return jsonify({'success': False, 'error': 'Disease site not found'}), 404
        
        return jsonify({
            'success': True,
            'disease_site': {
                'id': disease_site.id,
                'disease_name': disease_site.disease_name,
                'slug': disease_site.slug,
                'section_name': disease_site.body_section.section_name if disease_site.body_section else None,
                'frcr_module': disease_site.frcr_module,
                'frcr_body_part': disease_site.frcr_body_part,
                'frcr_age_group': disease_site.frcr_age_group
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_tnm_bp.route('/disease-site/<int:disease_site_id>', methods=['PUT'])
@require_admin
def update_disease_site(disease_site_id):
    """
    Update disease site settings including FRCR mappings.
    """
    try:
        disease_site = AJCCDiseaseSite.query.get(disease_site_id)
        if not disease_site:
            return jsonify({'success': False, 'error': 'Disease site not found'}), 404
        
        data = request.get_json()
        
        # Update FRCR settings
        if 'frcr_module' in data:
            disease_site.frcr_module = data['frcr_module'] or None
        if 'frcr_body_part' in data:
            disease_site.frcr_body_part = data['frcr_body_part'] or None
        if 'frcr_age_group' in data:
            disease_site.frcr_age_group = data['frcr_age_group'] or None
        
        # Update basic info if provided
        if 'disease_name' in data and data['disease_name']:
            disease_site.disease_name = data['disease_name']
        
        db.session.commit()
        
        logger.info(f"Updated disease site {disease_site.disease_name} by user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': f'Successfully updated {disease_site.disease_name}'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating disease site: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# Authentication Endpoints
# ============================================================================

@admin_tnm_bp.route('/auth-status', methods=['GET'])
@require_admin
def check_auth_status():
    """
    Check current AJCC authentication status.
    Returns info about cookies, Playwright availability, and suggestions.
    """
    try:
        from ..services.auth_service import get_ajcc_session, AJCCAuthSession
        import os
        
        # Check if Playwright is available
        playwright_available = False
        try:
            from playwright.sync_api import sync_playwright
            playwright_available = True
        except ImportError:
            pass
        
        # Check if we have valid cookies
        auth_session = AJCCAuthSession()
        cookies = auth_session.get_session_cookies()
        
        has_cookies = len(cookies) > 0
        cookie_count = len(cookies)
        
        # Check if cookies are likely valid (have session-related cookies)
        session_cookie_names = ['session', 'okta', 'idx', 'JSESSIONID', 'facs']
        has_session_cookies = any(
            any(name.lower() in cookie.get('name', '').lower() for name in session_cookie_names)
            for cookie in cookies
        )
        
        # Try to verify authentication by making a test request
        authenticated = False
        expires = None
        method = 'unknown'
        
        if has_session_cookies:
            try:
                session = get_ajcc_session()
                # Make a lightweight test request
                test_url = "https://ajccstaging.org/api/versions"
                response = session.get(test_url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    # If we get valid version data, we're authenticated
                    if isinstance(data, list) and len(data) > 0:
                        authenticated = True
                        method = 'cookies'
            except Exception as e:
                logger.debug(f"Auth verification failed: {e}")
        
        result = {
            'authenticated': authenticated,
            'method': method,
            'cookie_count': cookie_count,
            'has_session_cookies': has_session_cookies,
            'playwright_available': playwright_available,
            'expires': expires
        }
        
        if not authenticated:
            if playwright_available:
                result['extension_hint'] = 'Click to authenticate with Playwright'
            else:
                result['extension_hint'] = 'Install browser extension or log in via extension'
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        return jsonify({
            'authenticated': False,
            'error': str(e),
            'playwright_available': False
        })


@admin_tnm_bp.route('/extension-cookies', methods=['POST', 'OPTIONS'])
def receive_extension_cookies():
    """
    Receive cookies from the browser extension.
    This endpoint does NOT require admin auth since it's called by the extension.
    It uses a simple timestamp-based validation.
    """
    # Handle CORS preflight request
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    try:
        from ..services.manual_auth_helper import set_manual_cookies, save_manual_cookies
        
        data = request.get_json()
        cookies_list = data.get('cookies', [])
        timestamp = data.get('timestamp')
        
        if not cookies_list:
            response = jsonify({
                'success': False,
                'error': 'No cookies provided'
            })
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response, 400
        
        # Validate timestamp is recent (within 5 minutes)
        if timestamp:
            import time
            current_time = int(time.time() * 1000)
            if abs(current_time - timestamp) > 300000:  # 5 minutes
                response = jsonify({
                    'success': False,
                    'error': 'Request timestamp too old'
                })
                response.headers['Access-Control-Allow-Origin'] = '*'
                return response, 400
        
        # Convert list format to dict format expected by set_manual_cookies
        cookies_dict = {}
        for cookie in cookies_list:
            if isinstance(cookie, dict) and 'name' in cookie and 'value' in cookie:
                cookies_dict[cookie['name']] = cookie['value']
        
        if not cookies_dict:
            response = jsonify({
                'success': False,
                'error': 'No valid cookies in request'
            })
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response, 400
        
        # Save cookies (always save, verification is optional)
        save_manual_cookies(cookies_dict)
        
        # Try to set and verify cookies (but don't fail if verification fails)
        verified = set_manual_cookies(cookies_dict)
        
        logger.info(f"Received {len(cookies_dict)} cookies from browser extension (verified: {verified})")
        
        response = jsonify({
            'success': True,
            'message': f'Saved {len(cookies_dict)} cookies',
            'cookie_count': len(cookies_dict),
            'verified': verified,
            'note': 'Cookies saved. Login to AJCC if not authenticated.' if not verified else None
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
            
    except Exception as e:
        logger.error(f"Error receiving extension cookies: {e}")
        response = jsonify({'success': False, 'error': str(e)})
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 500


@admin_tnm_bp.route('/playwright-auth', methods=['POST'])
@require_admin
def trigger_playwright_auth():
    """
    Trigger Playwright-based authentication.
    Opens a browser, logs in with credentials from .env, and captures cookies.
    """
    try:
        import os
        
        # Check if Playwright is available
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return jsonify({
                'success': False,
                'error': 'Playwright not installed. Run: pip install playwright && playwright install chromium'
            }), 400
        
        # Get credentials from environment
        username = os.getenv('AJCC_USERNAME', '')
        password = os.getenv('AJCC_PASSWORD', '')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'AJCC_USERNAME and AJCC_PASSWORD must be set in .env file'
            }), 400
        
        # Import auth service and trigger authentication
        from ..services.auth_service import AJCCAuthSession
        
        auth = AJCCAuthSession()
        success = auth.authenticate_with_playwright(username, password)
        
        if success:
            logger.info(f"Playwright authentication successful for {username}")
            return jsonify({
                'success': True,
                'message': 'Authentication successful'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Authentication failed. Check credentials.'
            }), 401
            
    except Exception as e:
        logger.error(f"Playwright authentication error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# TNM Data Curation Routes (Admin Only)
# ============================================================================

@admin_tnm_bp.route('/curate/<int:disease_site_id>/<int:year>', methods=['GET'])
@require_admin
def curate_tnm_page(disease_site_id, year):
    """
    Render the TNM curation page.
    Shows raw AJCC data and allows editing into Quick Reference + Explanatory Notes.
    """
    try:
        # Get disease site
        disease = AJCCDiseaseSite.query.get(disease_site_id)
        if not disease:
            return render_template('error.html', message='Disease site not found'), 404
        
        # Get the body section for this disease
        section = AJCCBodySection.query.get(disease.body_section_id) if disease.body_section_id else None
        
        # Get diagnosis year
        diagnosis_year = AJCCDiagnosisYear.query.filter_by(year=year).first()
        if not diagnosis_year:
            # Create the year if it doesn't exist
            diagnosis_year = AJCCDiagnosisYear(year=year)
            db.session.add(diagnosis_year)
            db.session.commit()
        
        # Get staging data
        staging_data = AJCCStagingData.query.filter_by(
            disease_site_id=disease_site_id,
            diagnosis_year_id=diagnosis_year.id
        ).first()
        
        # Get raw HTML combined for reference
        raw_html_combined = None
        curated_quick_reference = None
        curated_explanatory_notes = None
        
        if staging_data:
            raw_html_combined = staging_data.get_all_raw_html_combined()
            curated_quick_reference = staging_data.curated_quick_reference_html
            curated_explanatory_notes = staging_data.curated_explanatory_notes_html
        
        # Check if came from a case
        from_case_id = request.args.get('from_case_id', type=int)
        
        # Get available years for this disease
        available_years = []
        all_staging = AJCCStagingData.query.filter_by(disease_site_id=disease_site_id).all()
        for sd in all_staging:
            if sd.diagnosis_year and sd.diagnosis_year.year not in available_years:
                available_years.append(sd.diagnosis_year.year)
        available_years = sorted(available_years, reverse=True) if available_years else [year]
        
        # Get intelligent TNM data if available
        intelligent_data = None
        try:
            from models import IntelligentTNMData
            intel_record = IntelligentTNMData.query.filter_by(
                disease_site_id=disease_site_id,
                diagnosis_year_id=diagnosis_year.id
            ).first()
            if intel_record:
                intelligent_data = intel_record.to_dict()
        except Exception as e:
            logger.warning(f"Could not load intelligent data: {e}")
        
        return render_template(
            'edit_tnm.html',
            disease=disease,
            section=section,
            year=year,
            staging_data=staging_data,
            available_years=available_years,
            intelligent_data=intelligent_data,
            from_case_id=from_case_id
        )
        
    except Exception as e:
        logger.error(f"Error loading curation page: {e}")
        return render_template('error.html', message=str(e)), 500


@admin_tnm_bp.route('/curate/save', methods=['POST'])
@require_admin
def save_curated_tnm():
    """
    Save curated TNM data.
    Receives Quick Reference + Explanatory Notes and stores them.
    """
    try:
        data = request.get_json()
        
        disease_site_id = data.get('disease_site_id')
        year = data.get('year', 2024)  # Default to current edition
        quick_reference_html = data.get('quick_reference_html', '')
        explanatory_notes_html = data.get('explanatory_notes_html', '')
        
        if not disease_site_id:
            return jsonify({'success': False, 'error': 'Disease site ID required'}), 400
        
        # Get or create diagnosis year
        diagnosis_year = AJCCDiagnosisYear.query.filter_by(year=year).first()
        if not diagnosis_year:
            diagnosis_year = AJCCDiagnosisYear(year=year)
            db.session.add(diagnosis_year)
            db.session.flush()
        
        # Get or create staging data record
        staging_data = AJCCStagingData.query.filter_by(
            disease_site_id=disease_site_id,
            diagnosis_year_id=diagnosis_year.id
        ).first()
        
        if not staging_data:
            # Create a new staging data record for curation (without raw AJCC data)
            staging_data = AJCCStagingData(
                disease_site_id=disease_site_id,
                diagnosis_year_id=diagnosis_year.id,
                data_version=2
            )
            db.session.add(staging_data)
        
        # Set curated data
        staging_data.set_curated_data(
            quick_reference_html=quick_reference_html,
            explanatory_notes_html=explanatory_notes_html,
            user_id=current_user.id
        )
        
        db.session.commit()
        
        logger.info(f"Curated TNM data saved for disease_site_id={disease_site_id}, year={year} by user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Curated data saved successfully',
            'is_curated': True,
            'curated_at': staging_data.curated_at.isoformat() if staging_data.curated_at else None
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving curated TNM data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_tnm_bp.route('/curate/check/<int:disease_site_id>', methods=['GET'])
@require_admin
def check_curated_status(disease_site_id):
    """
    Check if a disease site has curated TNM data.
    Used by case editor to determine if TNM link can be created.
    """
    try:
        year = request.args.get('year', 2024, type=int)
        
        diagnosis_year = AJCCDiagnosisYear.query.filter_by(year=year).first()
        if not diagnosis_year:
            return jsonify({
                'success': True,
                'is_curated': False,
                'has_raw_data': False,
                'message': 'No TNM data exists for this disease site'
            })
        
        staging_data = AJCCStagingData.query.filter_by(
            disease_site_id=disease_site_id,
            diagnosis_year_id=diagnosis_year.id
        ).first()
        
        if not staging_data:
            return jsonify({
                'success': True,
                'is_curated': False,
                'has_raw_data': False,
                'message': 'No TNM data exists for this disease site'
            })
        
        # Check if has raw data
        has_raw_data = bool(staging_data.section_1_quick_reference_html or staging_data.raw_html_content)
        
        return jsonify({
            'success': True,
            'is_curated': staging_data.is_curated,
            'has_raw_data': has_raw_data,
            'curated_at': staging_data.curated_at.isoformat() if staging_data.curated_at else None,
            'message': 'Curated data available' if staging_data.is_curated else 'Data not yet curated'
        })
        
    except Exception as e:
        logger.error(f"Error checking curated status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
