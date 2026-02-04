"""
TNM Calculator Flask Routes

API endpoints and page routes for the TNM Calculator.
Supports both v2 (API-based) and v3 (HTML calculator) approaches.
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
import logging
import os
from pathlib import Path

from .engine import TNMCalculator
from .models import TNMInput, StagingType

logger = logging.getLogger(__name__)

# Create blueprint - using main app templates folder for v3 templates
tnm_calc_bp = Blueprint(
    'tnm_calculator',
    __name__,
    template_folder='../templates',  # Use main app templates
    url_prefix='/tnm-calculator'
)

# Global calculator instance
_calculator = None


def get_calculator() -> TNMCalculator:
    """Get or create the calculator instance."""
    global _calculator
    if _calculator is None:
        _calculator = TNMCalculator()
    return _calculator


# ==================== V3 CALCULATOR DEFINITIONS ====================

# Define available calculators with metadata
V3_CALCULATORS = {
    'head_and_neck': {
        'name': 'Head and Neck',
        'icon': 'fas fa-head-side',
        'calculators': [
            {
                'name': 'Oropharynx',
                'slug': 'oropharynx',
                'description': 'HPV+ and HPV- staging with detailed criteria',
                'special_features': ['HPV+ Staging', 'HPV- Staging'],
                'staging_system': 'AJCC 9th Edition',
                'available': True
            },
            {
                'name': 'Larynx',
                'slug': 'larynx',
                'description': 'Glottic, supraglottic, and subglottic subsites',
                'special_features': ['Subsites'],
                'staging_system': 'AJCC 9th Edition',
                'available': False
            },
            {
                'name': 'Oral Cavity',
                'slug': 'oral_cavity',
                'description': 'Lip, tongue, floor of mouth, buccal mucosa',
                'special_features': ['Depth of Invasion'],
                'staging_system': 'AJCC 9th Edition',
                'available': False
            },
            {
                'name': 'Nasopharynx',
                'slug': 'nasopharynx',
                'description': 'EBV-associated staging',
                'special_features': ['EBV Status'],
                'staging_system': 'AJCC 9th Edition',
                'available': False
            },
            {
                'name': 'Hypopharynx',
                'slug': 'hypopharynx',
                'description': 'Pyriform sinus, posterior pharyngeal wall',
                'special_features': [],
                'staging_system': 'AJCC 9th Edition',
                'available': False
            },
            {
                'name': 'Thyroid',
                'slug': 'thyroid',
                'description': 'Differentiated, medullary, and anaplastic',
                'special_features': ['Age Factor', 'Histology'],
                'staging_system': 'AJCC 9th Edition',
                'available': False
            },
        ]
    },
    'thorax': {
        'name': 'Thorax',
        'icon': 'fas fa-lungs',
        'calculators': [
            {
                'name': 'Lung (NSCLC)',
                'slug': 'lung',
                'description': 'Non-small cell lung cancer staging',
                'special_features': ['SCLC Option'],
                'staging_system': 'AJCC 9th Edition',
                'available': False
            },
            {
                'name': 'Esophagus',
                'slug': 'esophagus',
                'description': 'SCC and adenocarcinoma staging',
                'special_features': ['Histology', 'Location'],
                'staging_system': 'AJCC 9th Edition',
                'available': False
            },
        ]
    },
    'breast': {
        'name': 'Breast',
        'icon': 'fas fa-ribbon',
        'calculators': [
            {
                'name': 'Breast Cancer',
                'slug': 'breast',
                'description': 'Anatomic and prognostic staging with biomarkers',
                'special_features': ['ER/PR', 'HER2', 'Grade', 'Prognostic'],
                'staging_system': 'AJCC 9th Edition',
                'available': False
            },
        ]
    },
    'gynecological': {
        'name': 'Gynecological',
        'icon': 'fas fa-venus',
        'calculators': [
            {
                'name': 'Cervix',
                'slug': 'cervix',
                'description': 'FIGO 2018 staging for cervical cancer',
                'special_features': ['Imaging-based'],
                'staging_system': 'FIGO 2018',
                'available': False
            },
            {
                'name': 'Endometrium',
                'slug': 'endometrium',
                'description': 'FIGO 2023 staging for endometrial cancer',
                'special_features': ['Molecular'],
                'staging_system': 'FIGO 2023',
                'available': False
            },
            {
                'name': 'Ovary',
                'slug': 'ovary',
                'description': 'FIGO staging for ovarian cancer',
                'special_features': [],
                'staging_system': 'FIGO 2014',
                'available': False
            },
        ]
    },
}


def get_v3_sections():
    """Get calculator sections for index page."""
    sections = []
    for section_id, section_data in V3_CALCULATORS.items():
        sections.append({
            'name': section_data['name'],
            'icon': section_data['icon'],
            'calculators': section_data['calculators']
        })
    return sections


def calculator_exists(disease: str) -> bool:
    """Check if a calculator HTML file exists."""
    calc_dir = Path(__file__).parent / 'calculators'
    calc_file = calc_dir / f'{disease}_calc.html'
    return calc_file.exists()


# ==================== V3 PAGE ROUTES ====================

@tnm_calc_bp.route('/')
def index():
    """Render the TNM Calculator v3 index page."""
    sections = get_v3_sections()
    return render_template(
        'tnm_calculator_v3/index.html',
        sections=sections
    )


@tnm_calc_bp.route('/v2')
def calculator_page_v2():
    """Render the legacy v2 TNM Calculator page (API-based)."""
    calculator = get_calculator()
    cancers = calculator.get_available_cancers()

    return render_template(
        'tnm_calculator.html',
        cancers=cancers
    )


@tnm_calc_bp.route('/<disease>')
def calculator(disease: str):
    """Render a disease-specific v3 calculator."""
    # Check if calculator exists
    if not calculator_exists(disease):
        logger.warning(f"[TNM Calculator] Calculator not found: {disease}")
        return redirect(url_for('tnm_calculator.index'))

    # Find calculator metadata
    calc_meta = None
    for section in V3_CALCULATORS.values():
        for calc in section['calculators']:
            if calc['slug'] == disease:
                calc_meta = calc
                break
        if calc_meta:
            break

    disease_name = calc_meta['name'] if calc_meta else disease.replace('_', ' ').title()

    # Read and render the calculator HTML
    calc_dir = Path(__file__).parent / 'calculators'
    calc_file = calc_dir / f'{disease}_calc.html'

    try:
        with open(calc_file, 'r', encoding='utf-8') as f:
            calculator_html = f.read()

        return render_template(
            'tnm_calculator_v3/calculator_wrapper.html',
            disease_name=disease_name,
            calculator_html=calculator_html,
            embed_mode=False
        )
    except Exception as e:
        logger.error(f"[TNM Calculator] Error loading calculator {disease}: {e}")
        return redirect(url_for('tnm_calculator.index'))


@tnm_calc_bp.route('/embed/<disease>')
def embed(disease: str):
    """Render a calculator in embed mode (for case discussion)."""
    if not calculator_exists(disease):
        return "Calculator not found", 404

    calc_dir = Path(__file__).parent / 'calculators'
    calc_file = calc_dir / f'{disease}_calc.html'

    try:
        with open(calc_file, 'r', encoding='utf-8') as f:
            calculator_html = f.read()

        return render_template(
            'tnm_calculator_v3/calculator_wrapper.html',
            disease_name=disease.replace('_', ' ').title(),
            calculator_html=calculator_html,
            embed_mode=True
        )
    except Exception as e:
        logger.error(f"[TNM Calculator] Error loading embed calculator {disease}: {e}")
        return "Calculator error", 500


# ==================== API ROUTES ====================

@tnm_calc_bp.route('/api/calculate', methods=['POST'])
def calculate():
    """
    Calculate TNM stage from input.
    
    Request body:
    {
        "cancer_type": "larynx",
        "t_category": "T2",
        "n_category": "N1",
        "m_category": "M0",
        "staging_type": "clinical",  // optional
        "subsite": "Glottis",        // optional
        "version": "8",              // optional
        // Biomarkers for breast cancer prognostic staging (optional)
        "grade": "G2",               // G1, G2, G3
        "her2_status": "Positive",   // Positive, Negative
        "er_status": "Positive",     // Positive, Negative
        "pr_status": "Negative"      // Positive, Negative
    }
    
    Response:
    {
        "success": true,
        "tnm_classification": "T2N1M0",
        "stage_group": "Stage III",
        "t_explanation": "...",
        "n_explanation": "...",
        "m_explanation": "...",
        "stage_explanation": "...",
        "disclaimer": "...",
        "uses_prognostic_staging": false,
        "grade": null,
        "her2_status": null,
        "er_status": null,
        "pr_status": null
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        # Validate required fields
        required = ["cancer_type", "t_category", "n_category", "m_category"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({
                "success": False,
                "error": f"Missing required fields: {', '.join(missing)}"
            }), 400
        
        # Parse staging type
        staging_type_str = data.get("staging_type", "clinical")
        try:
            staging_type = StagingType(staging_type_str)
        except ValueError:
            staging_type = StagingType.CLINICAL
        
        # Create input
        input = TNMInput(
            cancer_type=data["cancer_type"],
            t_category=data["t_category"],
            n_category=data["n_category"],
            m_category=data["m_category"],
            staging_type=staging_type,
            subsite=data.get("subsite"),
            version=data.get("version", "8"),
            # Biomarkers for prognostic staging (breast cancer)
            grade=data.get("grade"),
            her2_status=data.get("her2_status"),
            er_status=data.get("er_status"),
            pr_status=data.get("pr_status")
        )
        
        # Calculate
        calculator = get_calculator()
        result = calculator.calculate(input)
        
        logger.info(f"[TNM Calculator API] {input.cancer_type}: "
                   f"{result.tnm_classification} → {result.stage_group}")
        
        return jsonify(result.to_dict())
        
    except Exception as e:
        logger.error(f"[TNM Calculator API] Error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@tnm_calc_bp.route('/api/cancers')
def list_cancers():
    """
    Get list of available cancer types.
    
    Response:
    {
        "cancers": [
            {"name": "Larynx", "slug": "larynx", "body_section": "Head and Neck"},
            ...
        ]
    }
    """
    calculator = get_calculator()
    cancers = calculator.get_available_cancers()
    
    return jsonify({"cancers": cancers})


@tnm_calc_bp.route('/api/cancer/<cancer_type>')
def get_cancer_info(cancer_type: str):
    """
    Get detailed information about a cancer type.
    
    Response:
    {
        "name": "Larynx",
        "slug": "larynx",
        "subsites": ["Glottis", "Supraglottis", "Subglottis"],
        "t_categories": {...},
        "n_categories": {...},
        "m_categories": [...],
        "stage_groups": [...],
        "notes": [...]
    }
    """
    calculator = get_calculator()
    info = calculator.get_cancer_info(cancer_type)
    
    if not info:
        return jsonify({
            "success": False,
            "error": f"Cancer type '{cancer_type}' not found"
        }), 404
    
    return jsonify({"success": True, **info})


@tnm_calc_bp.route('/api/categories/<cancer_type>')
def get_categories(cancer_type: str):
    """
    Get available T, N, M categories for a cancer type.
    
    Query params:
    - subsite: Optional subsite for T categories
    - staging_type: 'clinical' or 'pathological'
    
    Response:
    {
        "t_categories": ["TX", "T0", "Tis", "T1", ...],
        "n_categories": ["NX", "N0", "N1", ...],
        "m_categories": ["M0", "M1"],
        "subsites": ["Glottis", "Supraglottis", ...]
    }
    """
    subsite = request.args.get('subsite')
    staging_type_str = request.args.get('staging_type', 'clinical')
    
    try:
        staging_type = StagingType(staging_type_str)
    except ValueError:
        staging_type = StagingType.CLINICAL
    
    calculator = get_calculator()
    info = calculator.get_cancer_info(cancer_type)
    
    if not info:
        return jsonify({
            "success": False,
            "error": f"Cancer type '{cancer_type}' not found"
        }), 404
    
    # Get T categories for the specified subsite
    t_categories = []
    if subsite and subsite in info["t_categories"]:
        t_categories = info["t_categories"][subsite]
    elif info["subsites"]:
        # Use first subsite as default
        first_subsite = info["subsites"][0]
        t_categories = info["t_categories"].get(first_subsite, [])
    else:
        t_categories = info["t_categories"].get("default", [])
    
    # Get N categories
    n_key = "pathological" if staging_type == StagingType.PATHOLOGICAL else "clinical"
    n_categories = info["n_categories"].get(n_key, [])
    
    return jsonify({
        "success": True,
        "t_categories": t_categories,
        "n_categories": n_categories,
        "m_categories": info["m_categories"],
        "subsites": info["subsites"]
    })


# ==================== REGISTRATION ====================

def register_routes(app):
    """Register the TNM Calculator blueprint with the Flask app."""
    app.register_blueprint(tnm_calc_bp)
    logger.info("[TNM Calculator] Routes registered")
