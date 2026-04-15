"""
Admin Routes for AJCC TNM Staging System

Provides endpoints for TNM data extraction, management, and editing.
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
import json
import logging

# Import from main app's models (kept in main app for shared use)
from models import db, AJCCBodySection, AJCCDiseaseSite, AJCCDiagnosisYear, AJCCStagingData, AJCCDiseaseMapping, IntelligentTNMData

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
        
        diseases = AJCCDiseaseSite.query.filter_by(body_section_id=section_id).order_by(AJCCDiseaseSite.display_order, AJCCDiseaseSite.disease_name).all()
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
        
        # Update the HTML section
        staging_data.set_section_html(section_number, html_content)
        staging_data.last_updated_at = datetime.utcnow()

        # For sections 2 and 3, also update the JSON columns that the view template reads from.
        # The view_tnm template reads cancers_staged/not_staged from JSON columns, not HTML columns.
        if section_number in (2, 3) and html_content:
            import re
            # Parse <li> items from HTML into a list
            li_items = re.findall(r'<li[^>]*>(.*?)</li>', html_content, re.DOTALL | re.IGNORECASE)
            if li_items:
                # Strip HTML tags from each item to get clean text
                items = [re.sub(r'<[^>]+>', '', item).strip() for item in li_items if item.strip()]
            else:
                # No list items found — store the whole text as a single item
                plain_text = re.sub(r'<[^>]+>', '', html_content).strip()
                items = [plain_text] if plain_text else []

            if section_number == 2:
                staging_data.cancers_staged_json = json.dumps(items)
            else:
                staging_data.cancers_not_staged_json = json.dumps(items)

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

# ============================================================================
# AJCC Data Audit Routes
# ============================================================================

@admin_tnm_bp.route('/audit', methods=['GET'])
@require_admin
def audit_page():
    """Render the AJCC data audit dashboard."""
    return render_template('admin_tnm_audit.html')


@admin_tnm_bp.route('/audit/data', methods=['GET'])
@require_admin
def audit_data():
    """
    Algorithmic audit of ALL AJCC staging data.
    Runs free checks: missing data, definition counts, cross-contamination.
    Returns JSON sorted by issue count (most problems first).
    """
    import re

    try:
        # Get all disease sites with staging data
        all_diseases = AJCCDiseaseSite.query.order_by(AJCCDiseaseSite.disease_name).all()

        # Build set of all disease names for cross-contamination check
        disease_names = {}
        for d in all_diseases:
            # Store lowercase name and id for lookup
            disease_names[d.id] = d.disease_name.lower()

        # False-positive phrases: anatomical terms that contain disease names
        # but don't indicate cross-contamination
        false_positive_patterns = {
            'cervix': ['cervical lymph', 'cervical node', 'cervical chain',
                       'cervical spine', 'cervical vertebr', 'cervical cord',
                       'cervical myelopathy', 'cervical fascia', 'cervical level'],
            'thyroid': ['thyroid cartilage', 'thyroid notch', 'thyroid shield',
                        'thyrohyoid', 'thyroarytenoid'],
            'oral': ['oral commissure', 'oral mucosa', 'oral cavity'],
            'bone': ['bone marrow', 'bone scan'],
        }

        results = []

        for disease in all_diseases:
            section = disease.body_section

            # Find staging data for this disease (any year)
            staging_records = AJCCStagingData.query.filter_by(
                disease_site_id=disease.id
            ).all()

            if not staging_records:
                # Disease with no staging data at all
                results.append({
                    'disease_site_id': disease.id,
                    'disease_name': disease.disease_name,
                    'disease_slug': disease.slug,
                    'section_name': section.section_name if section else 'Unknown',
                    'section_slug': section.slug if section else '',
                    'has_data': False,
                    'is_curated': False,
                    't_count': 0,
                    'n_count': 0,
                    'm_count': 0,
                    'stage_groups_count': 0,
                    'has_qr': False,
                    'has_notes': False,
                    'qr_length': 0,
                    'notes_length': 0,
                    'issues': ['No staging data extracted'],
                    'issue_count': 1,
                    'year': None,
                    'contamination': [],
                })
                continue

            for staging in staging_records:
                year_obj = staging.diagnosis_year
                year = year_obj.year if year_obj else None
                issues = []
                contamination = []

                # Check 1: Has JSON data
                has_json = staging.tnm_data_json is not None
                if not has_json:
                    issues.append('Missing tnm_data_json')

                # Check 2-5: Definition counts
                t_defs = staging.get_t_definitions()
                n_defs = staging.get_n_definitions()
                m_defs = staging.get_m_definitions()
                stage_groups = staging.get_stage_groups()

                t_count = len(t_defs) if isinstance(t_defs, list) else 0
                # Handle subsite-organized T definitions
                if t_defs and isinstance(t_defs, list) and len(t_defs) > 0:
                    if isinstance(t_defs[0], dict) and 'categories' in t_defs[0]:
                        t_count = sum(len(t.get('categories', [])) for t in t_defs if isinstance(t, dict))

                if isinstance(n_defs, dict):
                    n_count = sum(len(v) for v in n_defs.values() if isinstance(v, list))
                elif isinstance(n_defs, list):
                    n_count = len(n_defs)
                else:
                    n_count = 0

                m_count = len(m_defs) if isinstance(m_defs, list) else 0
                sg_count = len(stage_groups) if isinstance(stage_groups, list) else 0

                if t_count == 0:
                    issues.append('No T definitions')
                if n_count == 0:
                    issues.append('No N definitions')
                if m_count == 0:
                    issues.append('No M definitions')
                if sg_count == 0:
                    issues.append('No stage groups')

                # Check 6-7: HTML sections
                qr_html = staging.section_1_quick_reference_html or ''
                notes_html = staging.section_10_explanatory_notes_html or ''
                has_qr = len(qr_html.strip()) > 0
                has_notes = len(notes_html.strip()) > 0

                if not has_qr:
                    issues.append('Missing quick reference HTML')
                if not has_notes:
                    issues.append('Missing explanatory notes HTML')

                # Check 8: Cross-contamination
                search_text = re.sub(r'<[^>]+>', ' ', qr_html + ' ' + notes_html).lower()
                current_name = disease.disease_name.lower()

                for other_id, other_name in disease_names.items():
                    if other_id == disease.id:
                        continue
                    # Skip very short names (< 4 chars) to avoid false positives
                    if len(other_name) < 4:
                        continue
                    # Skip if other name is a substring of current name
                    if other_name in current_name or current_name in other_name:
                        continue

                    if other_name in search_text:
                        # Check false positives
                        is_false_positive = False
                        for fp_key, fp_phrases in false_positive_patterns.items():
                            if fp_key in other_name:
                                # Check if ALL occurrences are within false positive phrases
                                remaining = search_text
                                for phrase in fp_phrases:
                                    remaining = remaining.replace(phrase, '')
                                if other_name not in remaining:
                                    is_false_positive = True
                                    break

                        if not is_false_positive:
                            contamination.append(other_name)

                if contamination:
                    issues.append(f'Possible cross-contamination: {", ".join(contamination[:3])}')

                results.append({
                    'disease_site_id': disease.id,
                    'disease_name': disease.disease_name,
                    'disease_slug': disease.slug,
                    'section_name': section.section_name if section else 'Unknown',
                    'section_slug': section.slug if section else '',
                    'has_data': True,
                    'is_curated': staging.is_curated,
                    't_count': t_count,
                    'n_count': n_count,
                    'm_count': m_count,
                    'stage_groups_count': sg_count,
                    'has_qr': has_qr,
                    'has_notes': has_notes,
                    'qr_length': len(qr_html),
                    'notes_length': len(notes_html),
                    'issues': issues,
                    'issue_count': len(issues),
                    'year': year,
                    'contamination': contamination,
                })

        # Sort by issue count (most problems first)
        results.sort(key=lambda x: (-x['issue_count'], x['disease_name']))

        # Build summary
        total = len(results)
        with_issues = sum(1 for r in results if r['issue_count'] > 0)
        missing_data = sum(1 for r in results if not r['has_data'])
        curated = sum(1 for r in results if r['is_curated'])

        return jsonify({
            'success': True,
            'summary': {
                'total': total,
                'with_issues': with_issues,
                'missing_data': missing_data,
                'curated': curated,
            },
            'results': results,
        })

    except Exception as e:
        logger.error(f"Error running audit: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_tnm_bp.route('/audit/ai-review', methods=['POST'])
@require_admin
def audit_ai_review():
    """
    Manual AI review of a single disease's AJCC data.
    Sends T/N/M definitions + quick reference + explanatory notes to Claude
    for medical accuracy validation. Cost ~$0.01 per call.
    """
    import os
    import requests as http_requests

    try:
        data = request.get_json()
        disease_site_id = data.get('disease_site_id')
        year = data.get('year', 2026)

        if not disease_site_id:
            return jsonify({'success': False, 'error': 'disease_site_id required'}), 400

        disease = AJCCDiseaseSite.query.get(disease_site_id)
        if not disease:
            return jsonify({'success': False, 'error': 'Disease site not found'}), 404

        diagnosis_year = AJCCDiagnosisYear.query.filter_by(year=year).first()
        if not diagnosis_year:
            return jsonify({'success': False, 'error': f'Year {year} not found'}), 404

        staging = AJCCStagingData.query.filter_by(
            disease_site_id=disease_site_id,
            diagnosis_year_id=diagnosis_year.id
        ).first()

        if not staging:
            return jsonify({'success': False, 'error': 'No staging data found'}), 404

        # Build review content
        import re
        t_defs = staging.get_t_definitions()
        n_defs = staging.get_n_definitions()
        m_defs = staging.get_m_definitions()
        stage_groups = staging.get_stage_groups()
        qr_html = staging.section_1_quick_reference_html or ''
        notes_html = staging.section_10_explanatory_notes_html or ''

        # Strip HTML for review
        qr_text = re.sub(r'<[^>]+>', ' ', qr_html)
        qr_text = re.sub(r'\s+', ' ', qr_text).strip()[:4000]
        notes_text = re.sub(r'<[^>]+>', ' ', notes_html)
        notes_text = re.sub(r'\s+', ' ', notes_text).strip()[:4000]

        review_prompt = f"""Review these AJCC staging definitions for {disease.disease_name} ({disease.body_section.section_name if disease.body_section else 'Unknown'}).

T DEFINITIONS: {json.dumps(t_defs, indent=1)[:3000] if t_defs else 'NONE'}

N DEFINITIONS: {json.dumps(n_defs, indent=1)[:3000] if n_defs else 'NONE'}

M DEFINITIONS: {json.dumps(m_defs, indent=1)[:2000] if m_defs else 'NONE'}

STAGE GROUPS: {json.dumps(stage_groups, indent=1)[:2000] if stage_groups else 'NONE'}

QUICK REFERENCE TEXT: {qr_text[:3000] if qr_text else 'NONE'}

EXPLANATORY NOTES TEXT: {notes_text[:3000] if notes_text else 'NONE'}

Check for:
1. Wrong disease data (data that belongs to a different cancer type)
2. Incorrect staging criteria (wrong T/N/M cutoffs or definitions)
3. Missing categories (e.g. T1 exists but T2 is missing)
4. Inconsistencies between definitions and stage groups
5. Any text that clearly references a different anatomical site

Return your analysis as JSON with this exact structure:
{{
  "issues_found": [
    {{"severity": "high|medium|low", "category": "wrong_disease|incorrect_criteria|missing_category|inconsistency|other", "description": "..."}}
  ],
  "overall_assessment": "clean|minor_issues|major_issues",
  "confidence": "high|medium|low",
  "summary": "Brief 1-2 sentence summary"
}}"""

        api_key = os.getenv("CLAUDE_API_KEY")
        if not api_key:
            return jsonify({'success': False, 'error': 'CLAUDE_API_KEY not configured'}), 500

        model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

        response = http_requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": model,
                "max_tokens": 2000,
                "temperature": 0.1,
                "system": "You are a medical data auditor specializing in AJCC TNM staging. Return ONLY valid JSON.",
                "messages": [{"role": "user", "content": review_prompt}],
            },
            timeout=60,
        )

        if response.status_code >= 300:
            return jsonify({'success': False, 'error': f'RadInsights Intelligence error: {response.status_code}'}), 500

        ai_text = response.json()["content"][0]["text"].strip()

        # Try to parse JSON from response
        # Handle markdown code blocks
        if ai_text.startswith("```"):
            ai_text = ai_text.split("\n", 1)[1] if "\n" in ai_text else ai_text[3:]
            if ai_text.endswith("```"):
                ai_text = ai_text[:-3]
            ai_text = ai_text.strip()

        try:
            review_result = json.loads(ai_text)
        except json.JSONDecodeError:
            review_result = {
                "issues_found": [],
                "overall_assessment": "unknown",
                "confidence": "low",
                "summary": ai_text[:500],
            }

        return jsonify({
            'success': True,
            'review': review_result,
            'disease_name': disease.disease_name,
        })

    except Exception as e:
        logger.error(f"Error in AI review: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


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
        
        # Get TNM version info for display
        try:
            from ai_tnm import format_tnm_version, get_ajcc_version
            tnm_version = format_tnm_version(disease.slug)
            edition_info = get_ajcc_version(disease.slug)
            is_tnm9 = edition_info[0] == "9th"
        except Exception as e:
            logger.warning(f"Could not get TNM version: {e}")
            tnm_version = "AJCC Staging"
            is_tnm9 = False
        
        return render_template(
            'edit_tnm.html',
            disease=disease,
            section=section,
            year=year,
            staging_data=staging_data,
            available_years=available_years,
            intelligent_data=intelligent_data,
            from_case_id=from_case_id,
            tnm_version=tnm_version,
            is_tnm9=is_tnm9
        )
        
    except Exception as e:
        logger.error(f"Error loading curation page: {e}")
        return render_template('error.html', message=str(e)), 500


@admin_tnm_bp.route('/curate/save', methods=['POST'])
@require_admin
def save_curated_tnm():
    """
    Save curated TNM data.
    Receives Quick Reference + Explanatory Notes + TNM Intelligence + Essential TNM and stores them.
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
        
        # ============================================
        # Save TNM Intelligence Data
        # ============================================
        tnm_memory_aid_t = data.get('tnm_memory_aid_t')
        tnm_memory_aid_n = data.get('tnm_memory_aid_n')
        tnm_memory_aid_m = data.get('tnm_memory_aid_m')
        radiologist_key_points_html = data.get('radiologist_key_points_html')
        upstaging_triggers_html = data.get('upstaging_triggers_html')
        essential_tnm_data = data.get('essential_tnm')
        
        # Check if any intelligent data was provided
        has_intelligent_data = any([
            tnm_memory_aid_t, tnm_memory_aid_n, tnm_memory_aid_m,
            radiologist_key_points_html, upstaging_triggers_html,
            essential_tnm_data
        ])
        
        if has_intelligent_data:
            # Get or create intelligent TNM data record
            # NOTE: Query by disease_site_id only - one record per disease site
            # (unique constraint is on disease_site_id, not disease_site_id + diagnosis_year_id)
            intelligent_data = IntelligentTNMData.query.filter_by(
                disease_site_id=disease_site_id
            ).first()
            
            if not intelligent_data:
                intelligent_data = IntelligentTNMData(
                    disease_site_id=disease_site_id,
                    diagnosis_year_id=diagnosis_year.id,
                    verified_by_user_id=current_user.id
                )
                db.session.add(intelligent_data)
            else:
                # Update diagnosis_year_id if provided (for tracking purposes)
                if diagnosis_year and diagnosis_year.id:
                    intelligent_data.diagnosis_year_id = diagnosis_year.id
            
            # Update memory aids
            if tnm_memory_aid_t is not None:
                intelligent_data.tnm_memory_aid_t = tnm_memory_aid_t
            if tnm_memory_aid_n is not None:
                intelligent_data.tnm_memory_aid_n = tnm_memory_aid_n
            if tnm_memory_aid_m is not None:
                intelligent_data.tnm_memory_aid_m = tnm_memory_aid_m
            
            # Parse HTML lists into arrays for key points and triggers
            if radiologist_key_points_html:
                key_points = _extract_list_items_from_html(radiologist_key_points_html)
                intelligent_data.set_radiologist_key_points(key_points)
            
            if upstaging_triggers_html:
                triggers = _extract_list_items_from_html(upstaging_triggers_html)
                intelligent_data.set_upstaging_triggers(triggers)
            
            # Save Essential TNM data
            if essential_tnm_data:
                # Process key_concepts_html into array
                key_concepts = []
                if essential_tnm_data.get('key_concepts_html'):
                    key_concepts = _extract_list_items_from_html(essential_tnm_data['key_concepts_html'])
                
                essential_tnm_obj = {
                    'figure_url': essential_tnm_data.get('figure_url', ''),
                    'title': essential_tnm_data.get('title', ''),
                    'key_concepts': key_concepts,
                    'supplementary_table': essential_tnm_data.get('supplementary_table', ''),
                    'attribution': essential_tnm_data.get('attribution', 'IARC Essential TNM Guide (CC BY-NC-ND 3.0 IGO)')
                }
                intelligent_data.set_essential_tnm(essential_tnm_obj)
            
            # Update version and timestamps
            intelligent_data.version = (intelligent_data.version or 0) + 1
            intelligent_data.verified_by_user_id = current_user.id
        
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
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def _extract_list_items_from_html(html_content):
    """
    Extract text from <li> elements in HTML content.
    Returns a list of strings.
    """
    import re
    if not html_content:
        return []
    
    # Match <li>...</li> content, handling nested tags
    li_pattern = r'<li[^>]*>(.*?)</li>'
    matches = re.findall(li_pattern, html_content, re.DOTALL | re.IGNORECASE)
    
    # Clean each item - remove HTML tags
    items = []
    for match in matches:
        # Remove HTML tags but keep text
        clean_text = re.sub(r'<[^>]+>', '', match)
        clean_text = clean_text.strip()
        if clean_text:
            items.append(clean_text)
    
    # If no list items found, treat entire content as single item (stripped of HTML)
    if not items and html_content.strip():
        clean_text = re.sub(r'<[^>]+>', '', html_content).strip()
        if clean_text:
            items = [clean_text]
    
    return items


@admin_tnm_bp.route('/curate/upload-image', methods=['POST'])
@require_admin
def upload_tnm_image():
    """
    Upload an image to Cloudinary for TNM content.
    Images are stored in frcr_revision/tnm_cases folder.
    Creates a database record linking the image to the disease.
    """
    import os
    from models import TNMImage
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    disease_site_id = request.form.get('disease_site_id')
    if not disease_site_id:
        return jsonify({'success': False, 'error': 'Disease site ID required'}), 400
    
    try:
        disease_site_id = int(disease_site_id)
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid disease site ID'}), 400
    
    # Optional fields
    title = request.form.get('title', file.filename)
    description = request.form.get('description', '')
    image_type = request.form.get('image_type', 'reference')
    
    # Validate file type
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in allowed_extensions:
        return jsonify({'success': False, 'error': f'Invalid file type. Allowed: {", ".join(allowed_extensions)}'}), 400
    
    # Check file size (max 10MB)
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Seek back to start
    if size > 10 * 1024 * 1024:
        return jsonify({'success': False, 'error': 'File too large. Max 10MB'}), 400
    
    # Check Cloudinary configuration
    if not os.environ.get('CLOUDINARY_CLOUD_NAME'):
        return jsonify({'success': False, 'error': 'Image upload not configured'}), 500
    
    try:
        import cloudinary
        import cloudinary.uploader
        import uuid
        
        # Generate a unique public ID
        unique_id = str(uuid.uuid4())[:8]
        filename_base = file.filename.rsplit('.', 1)[0] if '.' in file.filename else file.filename
        # Sanitize filename for URL
        filename_base = ''.join(c if c.isalnum() or c in '-_' else '_' for c in filename_base)
        public_id = f"frcr_revision/tnm_cases/disease_{disease_site_id}/{filename_base}_{unique_id}"
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            file,
            public_id=public_id,
            folder=None,  # Public ID includes the folder path
            resource_type='image',
            tags=['tnm', 'frcr-revision', f'disease_{disease_site_id}']
        )
        
        # Create database record
        tnm_image = TNMImage(
            disease_site_id=disease_site_id,
            title=title,
            description=description,
            alt_text=title,
            cloudinary_url=result.get('secure_url'),
            cloudinary_public_id=result.get('public_id'),
            width=result.get('width'),
            height=result.get('height'),
            image_type=image_type,
            uploaded_by_user_id=current_user.id if current_user.is_authenticated else None
        )
        db.session.add(tnm_image)
        db.session.commit()
        
        logger.info(f"TNM image uploaded: id={tnm_image.id}, disease={disease_site_id}, by user {current_user.id}")
        
        return jsonify({
            'success': True,
            'image': tnm_image.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error uploading TNM image: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_tnm_bp.route('/curate/images/<int:disease_site_id>', methods=['GET'])
@require_admin
def get_tnm_images(disease_site_id):
    """
    Get all images for a disease site.
    """
    from models import TNMImage
    
    try:
        images = TNMImage.get_for_disease(disease_site_id)
        return jsonify({
            'success': True,
            'images': [img.to_dict() for img in images]
        })
    except Exception as e:
        logger.error(f"Error fetching TNM images: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_tnm_bp.route('/curate/images/<int:image_id>', methods=['DELETE'])
@require_admin
def delete_tnm_image(image_id):
    """
    Delete a TNM image from Cloudinary and database.
    """
    from models import TNMImage
    
    try:
        image = TNMImage.query.get(image_id)
        if not image:
            return jsonify({'success': False, 'error': 'Image not found'}), 404
        
        success = TNMImage.delete_from_cloudinary(image_id)
        if success:
            logger.info(f"TNM image deleted: id={image_id} by user {current_user.id}")
            return jsonify({'success': True, 'message': 'Image deleted'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete image'}), 500
            
    except Exception as e:
        logger.error(f"Error deleting TNM image: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_tnm_bp.route('/curate/images/<int:image_id>/description', methods=['PATCH'])
@require_admin
def update_tnm_image_description(image_id):
    """
    Update the description of a TNM image.
    """
    from models import TNMImage
    
    try:
        image = TNMImage.query.get(image_id)
        if not image:
            return jsonify({'success': False, 'error': 'Image not found'}), 404
        
        data = request.get_json()
        if data is None:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        
        new_description = data.get('description', '')
        image.description = new_description
        image.alt_text = new_description  # Also update alt text
        db.session.commit()
        
        logger.info(f"TNM image description updated: id={image_id} by user {current_user.id}")
        return jsonify({
            'success': True, 
            'message': 'Description updated',
            'image': image.to_dict()
        })
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating TNM image description: {e}")
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
