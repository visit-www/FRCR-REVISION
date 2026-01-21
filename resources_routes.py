"""
Flask routes for PubMed, TCIA, and RadiologyAssistant integrations.

These routes provide exam-relevant resources for FRCR 2B candidates:
- PubMed: Latest guidelines and free full-text articles
- TCIA: Real DICOM imaging datasets for practice
- RadiologyAssistant: Smart search links to relevant articles
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from pubmed_service import search_pubmed, search_latest_guidelines
from tcia_service import search_collections, get_collection_studies, get_study_series, search_by_diagnosis
import urllib.parse

resources_bp = Blueprint('resources', __name__, url_prefix='/resources')


@resources_bp.route('/api/pubmed/search')
@login_required
def pubmed_search():
    """
    Search PubMed for articles related to a topic.
    
    Query params:
        - topic: Search topic (required)
        - max_results: Maximum results (default 20)
        - free_full_text: Filter for free full text (default true)
        - article_type: Comma-separated article types (optional)
    """
    topic = request.args.get('topic', '').strip()
    if not topic:
        return jsonify({'error': 'Topic parameter required', 'articles': []}), 400
    
    max_results = int(request.args.get('max_results', 20))
    free_full_text = request.args.get('free_full_text', 'true').lower() == 'true'
    
    article_types = []
    if request.args.get('article_type'):
        article_types = [at.strip() for at in request.args.get('article_type').split(',')]
    
    filters = {
        'free_full_text_only': False,  # Don't filter, just prioritize
        'article_type': article_types if article_types else None
    }
    
    try:
        articles = search_pubmed(topic, max_results=max_results, filters=filters)
        current_app.logger.info(f"PubMed search for '{topic}': found {len(articles)} articles")
        return jsonify({
            'articles': articles,
            'total': len(articles),
            'topic': topic
        })
    except Exception as e:
        current_app.logger.error(f"PubMed search error: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'articles': [],
            'topic': topic,
            'message': 'PubMed search failed. Please try again or check your query.'
        }), 500


@resources_bp.route('/api/pubmed/guidelines')
@login_required
def pubmed_guidelines():
    """
    Search for latest guidelines and reviews on a topic.
    
    Query params:
        - topic: Search topic (required)
        - max_results: Maximum results (default 10)
    """
    topic = request.args.get('topic', '').strip()
    if not topic:
        return jsonify({'error': 'Topic parameter required', 'articles': []}), 400
    
    max_results = int(request.args.get('max_results', 10))
    
    try:
        articles = search_latest_guidelines(topic, max_results=max_results)
        return jsonify({
            'articles': articles,
            'total': len(articles),
            'topic': topic
        })
    except Exception as e:
        current_app.logger.error(f"PubMed guidelines search error: {e}")
        return jsonify({'error': str(e), 'articles': []}), 500


@resources_bp.route('/api/tcia/collections')
@login_required
def tcia_collections():
    """
    Search TCIA collections.
    
    Query params:
        - cancer_type: Filter by cancer type (optional)
        - modality: Filter by modality (optional)
        - body_part: Filter by body part (optional)
        - max_results: Maximum results (default 50)
    """
    cancer_type = request.args.get('cancer_type', '').strip() or None
    modality = request.args.get('modality', '').strip() or None
    body_part = request.args.get('body_part', '').strip() or None
    max_results = int(request.args.get('max_results', 50))
    
    try:
        collections = search_collections(
            cancer_type=cancer_type,
            modality=modality,
            body_part=body_part,
            max_results=max_results
        )
        return jsonify({
            'collections': collections,
            'total': len(collections)
        })
    except Exception as e:
        current_app.logger.error(f"TCIA collections search error: {e}")
        return jsonify({'error': str(e), 'collections': []}), 500


@resources_bp.route('/api/tcia/collections/<collection_id>/studies')
@login_required
def tcia_collection_studies(collection_id):
    """
    Get studies for a specific TCIA collection.
    
    Query params:
        - max_results: Maximum results (default 20)
    """
    max_results = int(request.args.get('max_results', 20))
    
    try:
        studies = get_collection_studies(collection_id, max_results=max_results)
        return jsonify({
            'studies': studies,
            'total': len(studies),
            'collection_id': collection_id
        })
    except Exception as e:
        current_app.logger.error(f"TCIA studies error: {e}")
        return jsonify({'error': str(e), 'studies': []}), 500


@resources_bp.route('/api/tcia/studies/<study_instance_uid>/series')
@login_required
def tcia_study_series(study_instance_uid):
    """
    Get series for a specific study.
    """
    try:
        series = get_study_series(study_instance_uid)
        return jsonify({
            'series': series,
            'total': len(series),
            'study_instance_uid': study_instance_uid
        })
    except Exception as e:
        current_app.logger.error(f"TCIA series error: {e}")
        return jsonify({'error': str(e), 'series': []}), 500


@resources_bp.route('/api/tcia/search')
@login_required
def tcia_search():
    """
    Search TCIA by diagnosis/keywords.
    
    Query params:
        - diagnosis: Diagnosis or keywords (required)
        - modality: Filter by modality (optional)
    """
    diagnosis = request.args.get('diagnosis', '').strip()
    if not diagnosis:
        return jsonify({'error': 'Diagnosis parameter required', 'results': []}), 400
    
    modality = request.args.get('modality', '').strip() or None
    
    try:
        search_result = search_by_diagnosis(diagnosis, modality=modality)
        results = search_result.get('results', [])
        current_app.logger.info(f"TCIA search for '{diagnosis}': found {len(results)} results (cancer-related: {search_result.get('is_cancer_related', False)})")
        return jsonify({
            'results': results,
            'total': len(results),
            'diagnosis': diagnosis,
            'is_cancer_related': search_result.get('is_cancer_related', False),
            'warning': search_result.get('warning')
        })
    except Exception as e:
        current_app.logger.error(f"TCIA search error: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'results': [],
            'diagnosis': diagnosis,
            'message': 'TCIA search failed. Please try again or check your query.'
        }), 500


@resources_bp.route('/api/radiology-assistant/search')
@login_required
def radiology_assistant_search():
    """
    Generate smart search link for RadiologyAssistant.
    
    Query params:
        - diagnosis: Diagnosis to search (required)
    
    Returns a search URL that can be used to find relevant articles.
    The URL uses RadiologyAssistant's search with the diagnosis.
    """
    diagnosis = request.args.get('diagnosis', '').strip()
    if not diagnosis:
        return jsonify({'error': 'Diagnosis parameter required'}), 400
    
    # Construct search URL for RadiologyAssistant
    # Format: https://radiologyassistant.nl/search?q={diagnosis} radiology assistant
    search_query = f"{diagnosis} radiology assistant"
    encoded_query = urllib.parse.quote(search_query)
    
    # Base URL for RadiologyAssistant search
    base_url = "https://radiologyassistant.nl"
    search_url = f"{base_url}/search?q={encoded_query}"
    
    # Note: To create deep links to specific sections, we would need to:
    # 1. Search the site and get article URLs
    # 2. Use browser automation or API to find diagnosis mentions
    # 3. Create fragment identifiers (#) for specific sections
    # 
    # For now, we provide the search URL and let users navigate
    # Future enhancement: Could use iframe or browser extension for deep linking
    
    return jsonify({
        'search_url': search_url,
        'diagnosis': diagnosis,
        'search_query': search_query,
        'instructions': 'Click to search RadiologyAssistant. Once on the article page, use browser search (Cmd/Ctrl+F) to find the diagnosis.'
    })


@resources_bp.route('/api/sciencedirect/search')
@login_required
def sciencedirect_search():
    """
    Search ScienceDirect with advanced search (radiology, imaging, diagnosis keywords).
    ADMIN ONLY - Auto-login is performed in the backend.
    
    Query params:
        - diagnosis: Diagnosis to search (required)
    
    Returns a search URL with advanced search parameters.
    """
    from access_control import require_admin
    from sciencedirect_service import search_sciencedirect
    
    # Check admin access
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    # Check if user is admin
    if current_user.role.value != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    
    diagnosis = request.args.get('diagnosis', '').strip()
    if not diagnosis:
        return jsonify({'error': 'Diagnosis parameter required'}), 400
    
    try:
        result = search_sciencedirect(diagnosis)
        current_app.logger.info(f"ScienceDirect search for '{diagnosis}': URL generated (logged in: {result.get('logged_in', False)})")
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"ScienceDirect search error: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'diagnosis': diagnosis,
            'message': 'ScienceDirect search failed. Please try again.'
        }), 500


@resources_bp.route('/api/sciencedirect/connect', methods=['POST'])
@login_required
def sciencedirect_connect():
    """
    Connect student to ScienceDirect (manual login).
    Opens login page for student to authenticate.
    After login, student should mark themselves as connected.
    """
    from sciencedirect_service import get_student_connect_url
    from models import db
    from datetime import datetime
    
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    # Only for students (admin uses auto-login)
    if current_user.role.value == 'admin':
        return jsonify({'error': 'Admins use auto-login. No connection needed.'}), 400
    
    try:
        connect_url = get_student_connect_url()
        
        # Mark as connected (student will login on ScienceDirect's site)
        # Note: We can't capture cookies directly, but we mark them as connected
        # so they don't have to click connect again
        current_user.sciencedirect_connected_at = datetime.utcnow()
        # Store a placeholder to indicate they've connected
        # In a full implementation, you'd capture actual cookies via browser extension or OAuth
        current_user.sciencedirect_session_cookies = '{"connected": true}'  # Placeholder
        db.session.commit()
        
        return jsonify({
            'connect_url': connect_url,
            'message': 'Please complete login on ScienceDirect. Your connection will be remembered.',
            'connected': True
        })
    except Exception as e:
        current_app.logger.error(f"ScienceDirect connect error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@resources_bp.route('/api/sciencedirect/status')
@login_required
def sciencedirect_status():
    """Check if student is connected to ScienceDirect."""
    if not current_user.is_authenticated:
        return jsonify({'connected': False}), 401
    
    # Admin always has access (auto-login)
    if current_user.role.value == 'admin':
        return jsonify({'connected': True, 'is_admin': True})
    
    # Check if student has connected
    connected = current_user.sciencedirect_connected_at is not None
    return jsonify({
        'connected': connected,
        'connected_at': current_user.sciencedirect_connected_at.isoformat() if current_user.sciencedirect_connected_at else None,
        'is_admin': False
    })


@resources_bp.route('/api/sciencedirect/disconnect', methods=['POST'])
@login_required
def sciencedirect_disconnect():
    """Disconnect student from ScienceDirect."""
    from models import db
    
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    # Only for students
    if current_user.role.value == 'admin':
        return jsonify({'error': 'Admins cannot disconnect (shared account)'}), 400
    
    try:
        current_user.sciencedirect_session_cookies = None
        current_user.sciencedirect_connected_at = None
        db.session.commit()
        
        return jsonify({'message': 'Disconnected from ScienceDirect'})
    except Exception as e:
        current_app.logger.error(f"ScienceDirect disconnect error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@resources_bp.route('/api/sciencedirect/search/student')
@login_required
def sciencedirect_search_student():
    """
    Search ScienceDirect for students (uses their saved session).
    
    Query params:
        - diagnosis: Diagnosis to search (required)
    """
    from sciencedirect_service import search_sciencedirect_student
    from models import db
    
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    # Admin should use the admin route
    if current_user.role.value == 'admin':
        return jsonify({'error': 'Use /api/sciencedirect/search for admin'}), 400
    
    # Check if connected
    if not current_user.sciencedirect_connected_at:
        return jsonify({
            'error': 'Not connected',
            'message': 'Please connect to ScienceDirect first',
            'requires_connection': True
        }), 400
    
    diagnosis = request.args.get('diagnosis', '').strip()
    if not diagnosis:
        return jsonify({'error': 'Diagnosis parameter required'}), 400
    
    try:
        result = search_sciencedirect_student(current_user, diagnosis)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"ScienceDirect student search error: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'diagnosis': diagnosis,
            'message': 'ScienceDirect search failed. Please try connecting again.'
        }), 500
