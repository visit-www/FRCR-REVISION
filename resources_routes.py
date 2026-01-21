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
        'free_full_text': free_full_text,
        'article_type': article_types if article_types else None
    }
    
    try:
        articles = search_pubmed(topic, max_results=max_results, filters=filters)
        return jsonify({
            'articles': articles,
            'total': len(articles),
            'topic': topic
        })
    except Exception as e:
        current_app.logger.error(f"PubMed search error: {e}")
        return jsonify({'error': str(e), 'articles': []}), 500


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
        results = search_by_diagnosis(diagnosis, modality=modality)
        return jsonify({
            'results': results,
            'total': len(results),
            'diagnosis': diagnosis
        })
    except Exception as e:
        current_app.logger.error(f"TCIA search error: {e}")
        return jsonify({'error': str(e), 'results': []}), 500


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
