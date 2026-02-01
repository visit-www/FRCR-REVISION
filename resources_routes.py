"""
Flask routes for PubMed, TCIA, and RadiologyAssistant integrations.

These routes provide exam-relevant resources for FRCR 2B candidates:
- PubMed: Latest guidelines and free full-text articles
- TCIA: Real DICOM imaging datasets for practice
- RadiologyAssistant: Smart search links to relevant articles
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from pathlib import Path
import json
from pubmed_service import search_pubmed, search_latest_guidelines, clear_pubmed_cache
from tcia_service import search_collections, get_collection_studies, get_study_series, search_by_diagnosis, clear_tcia_cache
import urllib.parse

resources_bp = Blueprint('resources', __name__, url_prefix='/resources')


@resources_bp.route('/api/anatomy-resources')
@login_required
def anatomy_resources():
    """Serve curated anatomy resources JSON (used by Anatomy tab in Notes)."""
    static_path = Path(current_app.static_folder or '') / 'anatomy_resources.json'
    try:
        with open(static_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        current_app.logger.error("anatomy_resources.json not found at %s", static_path)
        return jsonify({'error': 'Anatomy resources file not found', 'resources': [], 'body_part_keywords': {}}), 404
    except Exception as e:
        current_app.logger.error(f"Anatomy resources load error: {e}", exc_info=True)
        return jsonify({'error': str(e), 'resources': [], 'body_part_keywords': {}}), 500


@resources_bp.route('/api/pubmed/cache/clear', methods=['POST'])
@login_required
def pubmed_clear_cache():
    """Clear PubMed search cache. Use when results seem stale."""
    try:
        count = clear_pubmed_cache()
        return jsonify({'message': f'Cleared {count} cached PubMed results', 'count': count})
    except Exception as e:
        current_app.logger.error("PubMed cache clear error: %s", e, exc_info=True)
        return jsonify({'error': str(e), 'message': 'Failed to clear cache'}), 500


@resources_bp.route('/api/pubmed/search')
@login_required
def pubmed_search():
    """
    Search PubMed for articles related to a topic.
    
    Query params:
        - topic: Search topic (required)
        - max_results: Maximum results (default 20)
        - nocache: If "true", bypass cache and fetch fresh results
        - free_full_text: Filter for free full text (default true)
        - article_type: Comma-separated article types (optional)
    """
    topic = request.args.get('topic', '').strip()
    if not topic:
        return jsonify({'error': 'Topic parameter required', 'articles': []}), 400
    
    max_results = int(request.args.get('max_results', 20))
    nocache = request.args.get('nocache', 'false').lower() == 'true'
    free_full_text = request.args.get('free_full_text', 'true').lower() == 'true'
    
    article_types = []
    if request.args.get('article_type'):
        article_types = [at.strip() for at in request.args.get('article_type').split(',')]
    
    filters = {
        'free_full_text_only': False,  # Don't filter, just prioritize
        'article_type': article_types if article_types else None
    }
    
    try:
        articles = search_pubmed(topic, max_results=max_results, filters=filters, nocache=nocache)
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
    nocache = request.args.get('nocache', 'false').lower() == 'true'
    
    try:
        articles = search_latest_guidelines(topic, max_results=max_results, nocache=nocache)
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


@resources_bp.route('/api/tcia/cache/clear', methods=['POST'])
@login_required
def tcia_clear_cache():
    """Clear TCIA search cache. Use when results seem stale or after URL format changes."""
    try:
        count = clear_tcia_cache()
        return jsonify({'message': f'Cleared {count} cached items', 'count': count})
    except Exception as e:
        current_app.logger.error(f"TCIA cache clear error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@resources_bp.route('/api/tcia/search/debug')
@login_required
def tcia_search_debug():
    """Debug: return raw TCIA search result with URLs for troubleshooting."""
    diagnosis = request.args.get('diagnosis', 'lung cancer').strip() or 'lung cancer'
    try:
        from tcia_service import search_by_diagnosis
        result = search_by_diagnosis(diagnosis)
        # Sanitize for JSON: keep first result, first series with viewer URLs
        results = result.get('results', [])[:1]
        debug_data = []
        for r in results:
            series_list = r.get('series', [])[:2]
            debug_data.append({
                'collection': r.get('collection', {}).get('name'),
                'study': r.get('study', {}),
                'study_page_link': r.get('study_page_link'),
                'series_sample': [{
                    'series_instance_uid': s.get('series_instance_uid'),
                    'study_instance_uid': s.get('study_instance_uid'),
                    'viewer_link': s.get('viewer_link'),
                    'viewer_links': s.get('viewer_links'),
                } for s in series_list]
            })
        return jsonify({
            'diagnosis': diagnosis,
            'result_count': len(result.get('results', [])),
            'sample': debug_data,
            'warning': result.get('warning'),
        })
    except Exception as e:
        current_app.logger.exception("TCIA debug error")
        return jsonify({'error': str(e)}), 500


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


@resources_bp.route('/api/sciencedirect/apikey')
@login_required
def sciencedirect_apikey():
    """
    Get ScienceDirect API key for client-side use.
    API calls are made directly from the browser (CORS) as recommended by Elsevier.
    
    Returns:
        API key for authenticated users
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    from sciencedirect_service import get_api_key
    return jsonify({'api_key': get_api_key()})


@resources_bp.route('/api/sciencedirect/connect', methods=['POST'])
@login_required
def sciencedirect_connect():
    """
    Connect user to ScienceDirect (manual login).
    Opens login page for user to authenticate.
    After login, user should mark themselves as connected.
    - Admin: Connection valid for 1 year
    - Student: Connection valid for 3 months
    """
    from sciencedirect_service import get_student_connect_url
    from models import db
    from datetime import datetime, timedelta
    
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        connect_url = get_student_connect_url()
        
        # Mark as connected (user will login on ScienceDirect's site)
        # Note: Students must manually log in on ScienceDirect's website with their own credentials.
        # We mark them as "connected" so they don't have to click connect again, but they still
        # need to authenticate on ScienceDirect's site when searching.
        # For API access, students will need OAuth tokens (not yet implemented).
        current_user.sciencedirect_connected_at = datetime.utcnow()
        # Store a placeholder to indicate they've connected
        # TODO: When OAuth is implemented, store OAuth tokens instead of this placeholder
        current_user.sciencedirect_session_cookies = '{"connected": true}'  # Placeholder
        db.session.commit()
        
        # Calculate expiration based on user role
        is_admin = current_user.role.value == 'admin'
        if is_admin:
            expiration_days = 365  # 1 year for admin
            expiration_date = current_user.sciencedirect_connected_at + timedelta(days=expiration_days)
            message = f'Please complete login on ScienceDirect. Your connection will be valid for 1 year (until {expiration_date.strftime("%Y-%m-%d")}).'
        else:
            expiration_days = 90  # 3 months for student
            expiration_date = current_user.sciencedirect_connected_at + timedelta(days=expiration_days)
            message = f'Please complete login on ScienceDirect. Your connection will be valid for 3 months (until {expiration_date.strftime("%Y-%m-%d")}).'
        
        return jsonify({
            'connect_url': connect_url,
            'message': message,
            'connected': True,
            'expiration_date': expiration_date.isoformat(),
            'expiration_days': expiration_days,
            'is_admin': is_admin
        })
    except Exception as e:
        current_app.logger.error(f"ScienceDirect connect error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@resources_bp.route('/api/sciencedirect/status')
@login_required
def sciencedirect_status():
    """Check if user is connected to ScienceDirect and return expiration info."""
    from datetime import datetime, timedelta
    
    try:
        if not current_user.is_authenticated:
            return jsonify({'connected': False}), 401
        
        # Safely get role
        try:
            is_admin = current_user.role and current_user.role.value == 'admin'
        except (AttributeError, TypeError):
            is_admin = False
        
        # Safely get connection date
        connected_at = getattr(current_user, 'sciencedirect_connected_at', None)
        
        # Admin can use auto-login even without manual connection
        # But if they've manually connected, track expiration
        if is_admin:
            if not connected_at:
                # Admin with auto-login (no manual connection yet)
                return jsonify({
                    'connected': True,  # Admin can always use auto-login
                    'connected_at': None,
                    'is_admin': True,
                    'expired': False,
                    'expires_at': None,
                    'days_remaining': None,
                    'uses_auto_login': True
                })
            else:
                # Admin with manual connection - check expiration (1 year)
                expiration_days = 365
                expiration_date = connected_at + timedelta(days=expiration_days)
                now = datetime.utcnow()
                expired = expiration_date < now
                days_remaining = (expiration_date - now).days if not expired else 0
                connected = not expired
                
                return jsonify({
                    'connected': connected,
                    'connected_at': connected_at.isoformat() if connected_at else None,
                    'is_admin': True,
                    'expired': expired,
                    'expires_at': expiration_date.isoformat(),
                    'days_remaining': days_remaining,
                    'expiration_days': expiration_days,
                    'uses_auto_login': False
                })
        else:
            # Student - must have manual connection
            if not connected_at:
                return jsonify({
                    'connected': False,
                    'connected_at': None,
                    'is_admin': False,
                    'expired': False,
                    'expires_at': None,
                    'days_remaining': None
                })
            
            # Calculate expiration (3 months for student)
            expiration_days = 90
            expiration_date = connected_at + timedelta(days=expiration_days)
            now = datetime.utcnow()
            expired = expiration_date < now
            days_remaining = (expiration_date - now).days if not expired else 0
            
            # If expired, mark as not connected
            connected = not expired
            
            return jsonify({
                'connected': connected,
                'connected_at': connected_at.isoformat() if connected_at else None,
                'is_admin': False,
                'expired': expired,
                'expires_at': expiration_date.isoformat(),
                'days_remaining': days_remaining,
                'expiration_days': expiration_days
            })
    except Exception as e:
        current_app.logger.error(f'[SCIDIRECT] Status endpoint error: {str(e)}', exc_info=True)
        return jsonify({
            'connected': False,
            'error': 'Failed to check connection status'
        }), 500


@resources_bp.route('/api/sciencedirect/disconnect', methods=['POST'])
@login_required
def sciencedirect_disconnect():
    """Disconnect user from ScienceDirect."""
    from models import db
    
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        # Clear connection status (session cookies no longer used with API)
        current_user.sciencedirect_session_cookies = None
        current_user.sciencedirect_connected_at = None
        db.session.commit()
        
        return jsonify({'message': 'Disconnected from ScienceDirect', 'disconnected': True})
    except Exception as e:
        current_app.logger.error(f"ScienceDirect disconnect error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': str(e)}), 500




@resources_bp.route('/api/find-reference', methods=['POST'])
@login_required
def find_reference():
    """
    Find reference articles based on selected text.
    ADMIN ONLY - For use in case editor context menu.
    
    Searches across:
    - PubMed (medical/radiology journals)
    - Crossref (DOI lookup)
    - Specific radiology journals: Radiographics, AJR, RSNA, European Radiology, etc.
    
    Search strategy:
    1. Exact title match first
    2. If not found, search in article content
    3. Return precise match if found, or 1-3 close matches
    
    Request body:
        - query: Selected text to search for (required)
        - strict: Whether to do strict phrase search (default true)
    
    Returns:
        - exact_match: Single precise match if found
        - close_matches: 1-3 close matches if no exact match
        - message: Status message
    """
    from models import UserRole
    
    # Admin only
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    if current_user.role not in [UserRole.ADMIN, UserRole.CONTENT_MANAGER]:
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    query = data.get('query', '').strip()
    if not query:
        return jsonify({'error': 'Query text required'}), 400
    
    strict = data.get('strict', True)
    
    try:
        result = search_reference_articles(query, strict=strict)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Reference search error: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'message': 'Reference search failed. Please try again.'
        }), 500


def search_reference_articles(query: str, strict: bool = True) -> dict:
    """
    Search for reference articles across multiple sources.
    
    Strategy:
    1. Do strict exact phrase search first (in title, keywords)
    2. If no results, suggest query modifications
    3. Search PubMed, Crossref, then provide Radiopaedia/RadAssistant links
    """
    import requests
    import re
    
    # Preferred radiology journals for filtering
    RADIOLOGY_JOURNALS = [
        "Radiographics",
        "Radiology", 
        "American Journal of Roentgenology",
        "AJR Am J Roentgenol",
        "European Radiology",
        "British Journal of Radiology",
        "Indian Journal of Radiology and Imaging",
        "Clinical Radiology",
        "Insights into Imaging",
        "Acta Radiol",
        "J Comput Assist Tomogr",
        "Eur J Radiol",
    ]
    
    results = {
        'query': query,
        'exact_match': None,
        'close_matches': [],
        'sources_searched': [],
        'search_links': [],
        'suggestions': [],
        'allow_modify': False,
        'message': ''
    }
    
    # Clean and prepare query
    clean_query = query.strip()
    query_lower = clean_query.lower()
    
    # Generate search suggestions with PubMed spell check
    def generate_suggestions(original_query):
        suggestions = []
        words = original_query.split()
        
        # 1. Try PubMed's spell check API first (most accurate)
        pubmed_suggestion = get_pubmed_spelling_suggestion(original_query)
        if pubmed_suggestion and pubmed_suggestion.lower() != original_query.lower():
            suggestions.append({
                'query': pubmed_suggestion,
                'description': 'PubMed suggested'
            })
        
        # 2. Extract key medical terms
        key_terms = extract_key_medical_terms(original_query)
        if len(key_terms) < len(words) and len(key_terms) >= 2:
            suggestions.append({
                'query': ' '.join(key_terms),
                'description': 'Key terms only'
            })
        
        # 3. Common radiology spelling corrections (fallback)
        corrections = {
            'pictoral': 'pictorial',
            'assesment': 'assessment',
            'assessement': 'assessment',
            'laryngal': 'laryngeal',
            'larynegal': 'laryngeal',
            'metastisis': 'metastasis',
            'carcinoma': 'cancer',
            'tumour': 'tumor',
            'colour': 'color',
            'oesophagus': 'esophagus',
            'oesophageal': 'esophageal',
            'haemorrhage': 'hemorrhage',
            'haematoma': 'hematoma',
            'mri': 'MRI',
            'ct': 'CT',
            'pet': 'PET',
            'fdg': 'FDG',
            'suv': 'SUV',
            'hepatocelular': 'hepatocellular',
            'renal cell carcinom': 'renal cell carcinoma',
            'squamous cel': 'squamous cell',
            'adenocarcinom': 'adenocarcinoma',
            'lymphom': 'lymphoma',
            'melonoma': 'melanoma',
            'melanom': 'melanoma',
            'sarcom': 'sarcoma',
            'gliom': 'glioma',
            'glioblastom': 'glioblastoma',
            'meningiom': 'meningioma',
            'schwannom': 'schwannoma',
            'neuroblastom': 'neuroblastoma',
            'osteosarcom': 'osteosarcoma',
            'chondrosarcom': 'chondrosarcoma',
        }
        
        corrected_words = []
        has_correction = False
        for word in words:
            word_lower = word.lower()
            if word_lower in corrections:
                corrected_words.append(corrections[word_lower])
                has_correction = True
            else:
                corrected_words.append(word)
        
        if has_correction:
            corrected_query = ' '.join(corrected_words)
            # Only add if different from PubMed suggestion
            if not pubmed_suggestion or corrected_query.lower() != pubmed_suggestion.lower():
                suggestions.append({
                    'query': corrected_query,
                    'description': 'Spelling corrected'
                })
        
        # 4. Shorter phrase (first 3-4 key terms)
        if len(key_terms) > 4:
            suggestions.append({
                'query': ' '.join(key_terms[:4]),
                'description': 'Shorter phrase'
            })
        
        # 5. Main topic (last 3-4 key terms - often the disease name)
        if len(key_terms) > 4:
            suggestions.append({
                'query': ' '.join(key_terms[-3:]),
                'description': 'Main topic'
            })
        
        # Remove duplicates
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            q = s['query'].lower()
            if q not in seen and q != original_query.lower():
                seen.add(q)
                unique_suggestions.append(s)
        
        return unique_suggestions[:4]  # Max 4 suggestions
    
    all_articles = []
    sources_searched = []
    corrected_query = None
    
    # Check for spelling corrections first
    pubmed_suggestion = get_pubmed_spelling_suggestion(clean_query)
    if pubmed_suggestion and pubmed_suggestion.lower() != clean_query.lower():
        corrected_query = pubmed_suggestion
        print(f"[REFERENCE] PubMed suggested: '{clean_query}' -> '{corrected_query}'")
    
    # 1. STRICT SEARCH: PubMed (with original query)
    try:
        pubmed_results = search_pubmed_for_reference(clean_query, strict=True, journals=RADIOLOGY_JOURNALS)
        if pubmed_results:
            all_articles.extend(pubmed_results)
            sources_searched.append('PubMed')
    except Exception as e:
        print(f"[REFERENCE] PubMed error: {e}")
    
    # 2. If no results and we have a corrected query, try that
    if not all_articles and corrected_query:
        try:
            pubmed_results = search_pubmed_for_reference(corrected_query, strict=True, journals=RADIOLOGY_JOURNALS)
            if pubmed_results:
                all_articles.extend(pubmed_results)
                sources_searched.append('PubMed (corrected)')
                results['used_correction'] = corrected_query
        except Exception as e:
            print(f"[REFERENCE] PubMed corrected search error: {e}")
    
    # 3. STRICT SEARCH: Crossref
    if not all_articles:
        try:
            crossref_results = search_crossref_for_reference(clean_query, journals=RADIOLOGY_JOURNALS)
            if crossref_results:
                all_articles.extend(crossref_results)
                sources_searched.append('Crossref')
        except Exception as e:
            print(f"[REFERENCE] Crossref error: {e}")
    
    results['sources_searched'] = sources_searched
    
    # Add search links (Radiopaedia, Radiology Assistant)
    try:
        results['search_links'] = search_radiopaedia_for_reference(clean_query) + search_radiology_assistant_for_reference(clean_query)
    except Exception as e:
        print(f"[REFERENCE] Search links error: {e}")
    
    # Separate real articles from search links
    real_articles = [a for a in all_articles if not a.get('is_search_link')]
    
    if real_articles:
        # Check for exact title match
        for article in real_articles:
            title_lower = article.get('title', '').lower()
            # Exact match or query is substantial part of title
            if query_lower in title_lower or title_lower in query_lower:
                results['exact_match'] = article
                results['message'] = f"Exact match found via {article.get('source', 'unknown')}"
                return results
        
        # No exact match - return close matches
        seen_titles = set()
        unique_articles = []
        for article in real_articles:
            title_key = article.get('title', '').lower()[:50]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_articles.append(article)
        
        results['close_matches'] = unique_articles[:5]
        results['message'] = f"Found {len(results['close_matches'])} related article(s)"
    else:
        # NO RESULTS - Allow user to modify search
        results['allow_modify'] = True
        results['suggestions'] = generate_suggestions(clean_query)
        
        if results['suggestions']:
            results['message'] = 'No exact matches found. Try one of these searches or modify your query:'
        else:
            results['message'] = 'No matches found. Try using fewer words or different terms:'
    
    return results


def extract_key_medical_terms(query: str) -> list:
    """Extract key medical/radiology terms from query, removing filler words."""
    # Common filler words to remove
    filler_words = {
        'the', 'a', 'an', 'of', 'in', 'for', 'and', 'or', 'with', 'on', 'to', 
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
        'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
        'must', 'shall', 'can', 'need', 'dare', 'ought', 'used', 'this', 'that',
        'these', 'those', 'am', 'it', 'its', 'by', 'from', 'as', 'at', 'which',
        'what', 'when', 'where', 'who', 'whom', 'how', 'why', 'all', 'each',
        'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
        'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
        'but', 'if', 'then', 'because', 'while', 'although', 'though', 'after',
        'before', 'during', 'between', 'through', 'about', 'against', 'into',
        'used', 'using', 'use', 'increasingly', 'detection', 'assessment',
    }
    
    words = query.lower().split()
    key_terms = [w for w in words if w not in filler_words and len(w) > 2]
    return key_terms


def get_pubmed_spelling_suggestion(query: str) -> str:
    """Use PubMed's spell check API to get spelling suggestions."""
    import requests
    
    try:
        response = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/espell.fcgi",
            params={
                'db': 'pubmed',
                'term': query,
            },
            timeout=5
        )
        
        if response.status_code == 200:
            # Parse XML response for corrected query
            import re
            corrected_match = re.search(r'<CorrectedQuery>([^<]+)</CorrectedQuery>', response.text)
            if corrected_match:
                return corrected_match.group(1)
    except Exception as e:
        print(f"[REFERENCE] Spell check error: {e}")
    
    return None


def calculate_relevance_score(query: str, title: str) -> float:
    """Calculate how relevant an article title is to the query."""
    query_terms = set(extract_key_medical_terms(query))
    title_terms = set(extract_key_medical_terms(title))
    
    if not query_terms:
        return 0.0
    
    # Count matching terms
    matches = query_terms.intersection(title_terms)
    
    # Score based on percentage of query terms found in title
    score = len(matches) / len(query_terms)
    
    # Bonus for exact phrase match
    if query.lower() in title.lower():
        score += 0.5
    
    # Bonus for longer matches
    if len(matches) >= 3:
        score += 0.2
    
    return min(score, 1.0)


def search_pubmed_for_reference(query: str, strict: bool = True, journals: list = None, max_results: int = 5) -> list:
    """
    Search PubMed for reference articles with intelligent multi-stage search.
    
    Strategy:
    1. Try exact phrase in title
    2. Try key terms in title
    3. Try key terms in title/abstract
    4. Filter results by relevance score
    """
    import requests
    
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    # Extract key terms for better matching
    key_terms = extract_key_medical_terms(query)
    key_terms_query = ' '.join(key_terms) if key_terms else query
    
    def do_search(search_query: str) -> list:
        """Execute a PubMed search and return article IDs."""
        try:
            # Add radiology journal filter for better results
            if journals:
                journal_filter = " OR ".join([f'"{j}"[Journal]' for j in journals[:5]])
                full_query = f"({search_query}) AND ({journal_filter})"
            else:
                full_query = search_query
            
            response = requests.get(
                f"{base_url}/esearch.fcgi",
                params={
                    'db': 'pubmed',
                    'term': full_query,
                    'retmax': max_results * 2,  # Get more to filter later
                    'retmode': 'json',
                    'sort': 'relevance'
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('esearchresult', {}).get('idlist', [])
        except Exception as e:
            print(f"[REFERENCE] PubMed search error: {e}")
        return []
    
    # Multi-stage search strategy
    id_list = []
    
    if strict:
        # Stage 1: Exact phrase in title
        id_list = do_search(f'"{query}"[Title]')
        
        # Stage 2: Key terms in title (all terms required)
        if not id_list and key_terms:
            title_query = ' AND '.join([f'{term}[Title]' for term in key_terms[:5]])
            id_list = do_search(title_query)
        
        # Stage 3: Key terms in title (any term)
        if not id_list and key_terms:
            title_query = ' OR '.join([f'{term}[Title]' for term in key_terms[:5]])
            id_list = do_search(title_query)
    else:
        # Broad search: key terms in title/abstract
        if key_terms:
            abstract_query = ' AND '.join([f'{term}[Title/Abstract]' for term in key_terms[:4]])
            id_list = do_search(abstract_query)
    
    if not id_list:
        return []
    
    # Fetch article details
    try:
        fetch_response = requests.get(
            f"{base_url}/esummary.fcgi",
            params={
                'db': 'pubmed',
                'id': ','.join(id_list[:max_results * 2]),
                'retmode': 'json'
            },
            timeout=10
        )
        
        if fetch_response.status_code != 200:
            return []
        
        fetch_data = fetch_response.json()
        articles = []
        
        for pmid in id_list:
            article_data = fetch_data.get('result', {}).get(pmid, {})
            if article_data:
                title = article_data.get('title', '')
                
                # Calculate relevance score
                relevance = calculate_relevance_score(query, title)
                
                # Only include articles with reasonable relevance (> 0.2)
                if relevance >= 0.2 or len(id_list) <= 3:
                    articles.append({
                        'title': title,
                        'authors': [a.get('name', '') for a in article_data.get('authors', [])[:3]],
                        'journal': article_data.get('source', ''),
                        'year': article_data.get('pubdate', '')[:4] if article_data.get('pubdate') else '',
                        'pmid': pmid,
                        'pubmed_link': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        'doi': article_data.get('elocationid', '').replace('doi: ', '') if 'doi' in article_data.get('elocationid', '').lower() else None,
                        'source': 'PubMed',
                        'relevance': relevance
                    })
        
        # Sort by relevance and return top results
        articles.sort(key=lambda x: x.get('relevance', 0), reverse=True)
        return articles[:max_results]
        
    except Exception as e:
        print(f"[REFERENCE] PubMed fetch error: {e}")
        return []


def search_crossref_for_reference(query: str, journals: list = None, max_results: int = 5) -> list:
    """Search Crossref for reference articles."""
    import requests
    
    try:
        params = {
            'query.title': query,
            'rows': max_results,
            'sort': 'relevance'
        }
        
        # Add journal filter
        if journals:
            params['query.container-title'] = ' OR '.join(journals[:3])
        
        response = requests.get(
            "https://api.crossref.org/works",
            params=params,
            headers={'User-Agent': 'RadInsights/1.0 (mailto:admin@radinsights.com)'},
            timeout=10
        )
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        items = data.get('message', {}).get('items', [])
        
        articles = []
        for item in items:
            title = item.get('title', [''])[0] if item.get('title') else ''
            authors = [f"{a.get('family', '')}, {a.get('given', '')}" for a in item.get('author', [])[:3]]
            
            articles.append({
                'title': title,
                'authors': authors,
                'journal': item.get('container-title', [''])[0] if item.get('container-title') else '',
                'year': str(item.get('published-print', {}).get('date-parts', [['']])[0][0]) if item.get('published-print') else '',
                'doi': item.get('DOI', ''),
                'doi_link': f"https://doi.org/{item.get('DOI', '')}" if item.get('DOI') else None,
                'source': 'Crossref'
            })
        
        return articles
        
    except Exception as e:
        print(f"[REFERENCE] Crossref search error: {e}")
        return []


def search_radiopaedia_for_reference(query: str, max_results: int = 3) -> list:
    """
    Search Radiopaedia for reference articles.
    Uses their search endpoint. Returns search link as fallback.
    """
    import requests
    import urllib.parse
    
    # Always return a search link for Radiopaedia (they don't have a public API for article search)
    # The user can click to search manually
    return [{
        'title': f'Search Radiopaedia',
        'authors': [],
        'journal': 'Radiopaedia',
        'year': '',
        'link': f'https://radiopaedia.org/search?q={urllib.parse.quote(query)}&scope=articles',
        'source': 'Radiopaedia',
        'is_search_link': True
    }]


def search_radiology_assistant_for_reference(query: str) -> list:
    """
    Generate Radiology Assistant search link.
    Radiology Assistant doesn't have a public API, so we provide a search link.
    """
    import urllib.parse
    
    # Build search URL for Radiology Assistant
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://radiologyassistant.nl/search?q={encoded_query}"
    
    return [{
        'title': f'Search Radiology Assistant for: {query}',
        'authors': [],
        'journal': 'Radiology Assistant',
        'year': '',
        'link': search_url,
        'source': 'Radiology Assistant',
        'is_search_link': True
    }]
