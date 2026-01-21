"""
Notes Integration Routes
========================
Notion and Anki integration for student note management.

Notion Routes:
- GET /notion/connect - Start OAuth flow
- GET /notion/callback - Handle OAuth callback
- GET /notion/disconnect - Remove connection
- GET /api/notion/status - Check connection status
- GET /api/notion/search - Search notes by query
- GET /api/notion/page/<page_id> - Fetch page content

Anki Routes:
- POST /api/anki/connect - Connect to AnkiConnect
- GET /api/anki/status - Check connection status
- GET /api/anki/decks - List available decks
- POST /api/anki/flashcard - Create a flashcard
"""

import os
import re
import json
import requests
from datetime import datetime
from flask import Blueprint, redirect, url_for, request, jsonify, session, current_app
from flask_login import login_required, current_user

from models import db

notes_bp = Blueprint('notes_integration', __name__, url_prefix='/notes')

# ==================== NOTION INTEGRATION ====================

# Notion API configuration
NOTION_CLIENT_ID = os.getenv('NOTION_CLIENT_ID')
NOTION_CLIENT_SECRET = os.getenv('NOTION_CLIENT_SECRET')
NOTION_REDIRECT_URI = os.getenv('NOTION_REDIRECT_URI', 'http://localhost:5000/notion/callback')
NOTION_AUTH_URL = 'https://api.notion.com/v1/oauth/authorize'
NOTION_TOKEN_URL = 'https://api.notion.com/v1/oauth/token'
NOTION_API_VERSION = '2022-06-28'

# Check if Notion SDK is available
try:
    from notion_client import Client as NotionClient
    NOTION_AVAILABLE = True
except ImportError:
    NOTION_AVAILABLE = False


def get_notion_client(access_token):
    """Create a Notion client with the given access token."""
    if not NOTION_AVAILABLE or not access_token:
        return None
    return NotionClient(auth=access_token)


def notion_blocks_to_text(blocks):
    """Convert Notion blocks to plain text."""
    text_parts = []
    
    for block in blocks:
        block_type = block.get('type')
        
        if block_type == 'paragraph':
            rich_text = block.get('paragraph', {}).get('rich_text', [])
            text_parts.append(''.join([t.get('plain_text', '') for t in rich_text]))
            
        elif block_type in ['heading_1', 'heading_2', 'heading_3']:
            rich_text = block.get(block_type, {}).get('rich_text', [])
            heading_text = ''.join([t.get('plain_text', '') for t in rich_text])
            prefix = '#' * int(block_type[-1])
            text_parts.append(f"\n{prefix} {heading_text}\n")
            
        elif block_type == 'bulleted_list_item':
            rich_text = block.get('bulleted_list_item', {}).get('rich_text', [])
            text_parts.append('• ' + ''.join([t.get('plain_text', '') for t in rich_text]))
            
        elif block_type == 'numbered_list_item':
            rich_text = block.get('numbered_list_item', {}).get('rich_text', [])
            text_parts.append('- ' + ''.join([t.get('plain_text', '') for t in rich_text]))
            
        elif block_type == 'to_do':
            rich_text = block.get('to_do', {}).get('rich_text', [])
            checked = block.get('to_do', {}).get('checked', False)
            checkbox = '☑' if checked else '☐'
            text_parts.append(f"{checkbox} " + ''.join([t.get('plain_text', '') for t in rich_text]))
            
        elif block_type == 'code':
            rich_text = block.get('code', {}).get('rich_text', [])
            language = block.get('code', {}).get('language', '')
            code_text = ''.join([t.get('plain_text', '') for t in rich_text])
            text_parts.append(f"\n```{language}\n{code_text}\n```\n")
            
        elif block_type == 'quote':
            rich_text = block.get('quote', {}).get('rich_text', [])
            text_parts.append('> ' + ''.join([t.get('plain_text', '') for t in rich_text]))
            
        elif block_type == 'divider':
            text_parts.append('\n---\n')
    
    return '\n'.join(text_parts)


# ==================== NOTION OAUTH ROUTES ====================

def get_return_url():
    """Get the URL to return to after OAuth flow."""
    # Check session for stored case ID
    case_id = session.pop('notion_return_case_id', None)
    if case_id:
        return url_for('view_case', case_id=case_id)
    
    # Check referrer header
    referrer = request.referrer
    if referrer and '/case/' in referrer:
        return referrer
    
    # Default to dashboard
    return url_for('dashboard')


@notes_bp.route('/notion/connect')
@login_required
def notion_connect():
    """Start Notion OAuth flow."""
    if not NOTION_CLIENT_ID:
        return jsonify({'error': 'Notion not configured. Please set NOTION_CLIENT_ID.'}), 500
    
    # Store the case ID if provided (from query param or referrer)
    case_id = request.args.get('case_id')
    if not case_id and request.referrer:
        # Try to extract case ID from referrer URL
        import re
        match = re.search(r'/case/(\d+)', request.referrer)
        if match:
            case_id = match.group(1)
    
    if case_id:
        session['notion_return_case_id'] = case_id
    
    # Build OAuth URL
    auth_url = (
        f"{NOTION_AUTH_URL}"
        f"?client_id={NOTION_CLIENT_ID}"
        f"&response_type=code"
        f"&owner=user"
        f"&redirect_uri={NOTION_REDIRECT_URI}"
    )
    
    return redirect(auth_url)


@notes_bp.route('/notion/callback')
@login_required
def notion_callback():
    """Handle Notion OAuth callback."""
    code = request.args.get('code')
    error = request.args.get('error')
    
    return_url = get_return_url()
    
    if error:
        return redirect(return_url + f'?notion=error&msg={error}')
    
    if not code:
        return redirect(return_url + '?notion=error&msg=no_code')
    
    try:
        # Exchange code for access token
        import base64
        credentials = base64.b64encode(
            f"{NOTION_CLIENT_ID}:{NOTION_CLIENT_SECRET}".encode()
        ).decode()
        
        response = requests.post(
            NOTION_TOKEN_URL,
            headers={
                'Authorization': f'Basic {credentials}',
                'Content-Type': 'application/json',
                'Notion-Version': NOTION_API_VERSION
            },
            json={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': NOTION_REDIRECT_URI
            }
        )
        
        if response.status_code != 200:
            return redirect(return_url + f'?notion=error&msg=token_error')
        
        data = response.json()
        
        # Store tokens
        current_user.notion_access_token = data.get('access_token')
        current_user.notion_workspace_id = data.get('workspace_id')
        current_user.notion_connected_at = datetime.utcnow()
        db.session.commit()
        
        return redirect(return_url + '?notion=connected')
    
    except Exception as e:
        current_app.logger.error(f"Notion OAuth error: {str(e)}")
        return redirect(return_url + f'?notion=error&msg={str(e)}')


@notes_bp.route('/notion/disconnect')
@login_required
def notion_disconnect():
    """Disconnect Notion account."""
    current_user.notion_access_token = None
    current_user.notion_workspace_id = None
    current_user.notion_connected_at = None
    db.session.commit()
    
    # Get return URL from referrer or default to dashboard
    referrer = request.referrer
    if referrer and '/case/' in referrer:
        return redirect(referrer + '?notion=disconnected')
    
    return redirect(url_for('dashboard') + '?notion=disconnected')


# ==================== NOTION API ROUTES ====================

@notes_bp.route('/api/notion/status')
@login_required
def notion_status():
    """Check Notion connection status."""
    return jsonify({
        'connected': current_user.notion_access_token is not None,
        'workspace_id': current_user.notion_workspace_id,
        'connected_at': current_user.notion_connected_at.isoformat() if current_user.notion_connected_at else None,
        'sdk_available': NOTION_AVAILABLE
    })


@notes_bp.route('/api/notion/search')
@login_required
def notion_search():
    """Search Notion pages by query."""
    if not current_user.notion_access_token:
        return jsonify({'error': 'Notion not connected', 'pages': [], 'connected': False}), 200
    
    query = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 10)), 50)
    
    if not query:
        return jsonify({'error': 'No search query provided', 'pages': []}), 400
    
    try:
        client = get_notion_client(current_user.notion_access_token)
        if not client:
            return jsonify({'error': 'Notion SDK not available', 'pages': []}), 200
        
        # Search pages
        results = client.search(
            query=query,
            filter={'property': 'object', 'value': 'page'},
            page_size=limit
        )
        
        pages = []
        for page in results.get('results', []):
            # Extract title from properties
            title = 'Untitled'
            props = page.get('properties', {})
            
            # Try common title property names
            for prop_name in ['title', 'Title', 'Name', 'name']:
                if prop_name in props:
                    title_prop = props[prop_name]
                    if title_prop.get('type') == 'title':
                        title_parts = title_prop.get('title', [])
                        if title_parts:
                            title = ''.join([t.get('plain_text', '') for t in title_parts])
                        break
            
            pages.append({
                'id': page.get('id'),
                'title': title,
                'url': page.get('url'),
                'created_time': page.get('created_time'),
                'last_edited_time': page.get('last_edited_time'),
                'icon': page.get('icon', {}).get('emoji') if page.get('icon') else None
            })
        
        return jsonify({
            'pages': pages,
            'total': len(pages),
            'query': query,
            'connected': True
        })
    
    except Exception as e:
        current_app.logger.error(f"Notion search error: {str(e)}")
        return jsonify({'error': str(e), 'pages': []}), 200


@notes_bp.route('/api/notion/page/<page_id>')
@login_required
def notion_get_page(page_id):
    """Fetch content of a Notion page."""
    if not current_user.notion_access_token:
        return jsonify({'error': 'Notion not connected', 'connected': False}), 401
    
    try:
        client = get_notion_client(current_user.notion_access_token)
        if not client:
            return jsonify({'error': 'Notion SDK not available'}), 500
        
        # Get page metadata
        page = client.pages.retrieve(page_id=page_id)
        
        # Get page content (blocks)
        blocks = client.blocks.children.list(block_id=page_id)
        
        # Convert blocks to text
        content_text = notion_blocks_to_text(blocks.get('results', []))
        
        # Extract title
        title = 'Untitled'
        props = page.get('properties', {})
        for prop_name in ['title', 'Title', 'Name', 'name']:
            if prop_name in props:
                title_prop = props[prop_name]
                if title_prop.get('type') == 'title':
                    title_parts = title_prop.get('title', [])
                    if title_parts:
                        title = ''.join([t.get('plain_text', '') for t in title_parts])
                    break
        
        return jsonify({
            'id': page_id,
            'title': title,
            'url': page.get('url'),
            'content_text': content_text,
            'created_time': page.get('created_time'),
            'last_edited_time': page.get('last_edited_time'),
            'connected': True
        })
    
    except Exception as e:
        current_app.logger.error(f"Notion page fetch error: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ==================== ANKI INTEGRATION ====================

# AnkiConnect configuration (local Anki desktop app)
ANKICONNECT_URL = os.getenv('ANKICONNECT_URL', 'http://localhost:8765')


def anki_request(action, **params):
    """Make a request to AnkiConnect."""
    payload = {
        'action': action,
        'version': 6,
        'params': params
    }
    
    try:
        response = requests.post(ANKICONNECT_URL, json=payload, timeout=5)
        result = response.json()
        
        if result.get('error'):
            return None, result['error']
        
        return result.get('result'), None
    except requests.exceptions.ConnectionError:
        return None, 'AnkiConnect not running. Please ensure Anki is open with AnkiConnect installed.'
    except Exception as e:
        return None, str(e)


@notes_bp.route('/api/anki/status')
@login_required
def anki_status():
    """Check AnkiConnect connection status."""
    result, error = anki_request('version')
    
    return jsonify({
        'connected': result is not None,
        'version': result if result else None,
        'error': error,
        'deck_name': current_user.anki_deck_name or 'FRCR Revision'
    })


@notes_bp.route('/api/anki/connect', methods=['POST'])
@login_required
def anki_connect():
    """Test and save AnkiConnect connection."""
    data = request.get_json() or {}
    deck_name = data.get('deck_name', 'FRCR Revision')
    
    # Test connection
    result, error = anki_request('version')
    
    if error:
        return jsonify({'success': False, 'error': error}), 200
    
    # Create deck if it doesn't exist
    anki_request('createDeck', deck=deck_name)
    
    # Save settings
    current_user.anki_deck_name = deck_name
    current_user.anki_connected_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'version': result,
        'deck_name': deck_name
    })


@notes_bp.route('/api/anki/disconnect', methods=['POST'])
@login_required
def anki_disconnect():
    """Clear Anki connection settings."""
    current_user.anki_deck_name = None
    current_user.anki_connected_at = None
    db.session.commit()
    
    return jsonify({'success': True})


@notes_bp.route('/api/anki/decks')
@login_required
def anki_decks():
    """List available Anki decks."""
    result, error = anki_request('deckNames')
    
    if error:
        return jsonify({'decks': [], 'error': error}), 200
    
    return jsonify({
        'decks': result or [],
        'current_deck': current_user.anki_deck_name
    })


@notes_bp.route('/api/anki/flashcard', methods=['POST'])
@login_required
def anki_create_flashcard():
    """Create a flashcard in Anki."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    front = data.get('front', '').strip()
    back = data.get('back', '').strip()
    deck_name = data.get('deck', current_user.anki_deck_name or 'FRCR Revision')
    tags = data.get('tags', ['FRCR', 'Radiology'])
    
    if not front or not back:
        return jsonify({'error': 'Front and back content required'}), 400
    
    # Ensure deck exists
    anki_request('createDeck', deck=deck_name)
    
    # Create the note
    result, error = anki_request(
        'addNote',
        note={
            'deckName': deck_name,
            'modelName': 'Basic',
            'fields': {
                'Front': front,
                'Back': back
            },
            'tags': tags,
            'options': {
                'allowDuplicate': False
            }
        }
    )
    
    if error:
        return jsonify({'success': False, 'error': error}), 200
    
    return jsonify({
        'success': True,
        'note_id': result,
        'deck': deck_name
    })


@notes_bp.route('/api/anki/flashcard/bulk', methods=['POST'])
@login_required
def anki_create_bulk_flashcards():
    """Create multiple flashcards from Q&A pairs."""
    data = request.get_json()
    
    if not data or 'cards' not in data:
        return jsonify({'error': 'No cards provided'}), 400
    
    cards = data.get('cards', [])
    deck_name = data.get('deck', current_user.anki_deck_name or 'FRCR Revision')
    tags = data.get('tags', ['FRCR', 'Radiology'])
    
    if not cards:
        return jsonify({'error': 'Empty cards list'}), 400
    
    # Ensure deck exists
    anki_request('createDeck', deck=deck_name)
    
    # Create notes in bulk
    notes = []
    for card in cards:
        front = card.get('front', '').strip()
        back = card.get('back', '').strip()
        
        if front and back:
            notes.append({
                'deckName': deck_name,
                'modelName': 'Basic',
                'fields': {
                    'Front': front,
                    'Back': back
                },
                'tags': tags,
                'options': {
                    'allowDuplicate': False
                }
            })
    
    if not notes:
        return jsonify({'error': 'No valid cards to create'}), 400
    
    result, error = anki_request('addNotes', notes=notes)
    
    if error:
        return jsonify({'success': False, 'error': error}), 200
    
    # Count successful additions (non-null results)
    created = sum(1 for r in result if r is not None) if result else 0
    
    return jsonify({
        'success': True,
        'created': created,
        'total': len(notes),
        'deck': deck_name
    })


def register_notes_blueprint(app):
    """Register notes integration blueprint with the Flask app."""
    app.register_blueprint(notes_bp)
