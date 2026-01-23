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
            active_section=1
        )
    
    return render_template(
        template,
        section=section,
        disease_site=disease_site,
        staging_data=staging_data,
        year_used=year_used,
        available_years=available_years,
        section_info=SECTION_INFO,
        active_section=1
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
        active_section=1
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
