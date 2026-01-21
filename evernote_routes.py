"""
Evernote Integration Routes
===========================
OAuth authentication and API endpoints for Evernote note access.

Routes:
- GET /evernote/connect - Start OAuth flow
- GET /evernote/callback - Handle OAuth callback
- GET /evernote/disconnect - Remove Evernote connection
- GET /api/evernote/search - Search notes by query
- GET /api/evernote/note/<guid> - Fetch single note content
"""

import os
import re
from datetime import datetime
from flask import Blueprint, redirect, url_for, request, jsonify, session, current_app
from flask_login import login_required, current_user

# Evernote SDK imports
try:
    from evernote.api.client import EvernoteClient
    from evernote.edam.notestore import NoteStore
    from evernote.edam.error.ttypes import EDAMUserException, EDAMSystemException, EDAMNotFoundException
    EVERNOTE_AVAILABLE = True
except ImportError:
    EVERNOTE_AVAILABLE = False

from models import db

evernote_bp = Blueprint('evernote', __name__)


def get_evernote_client(access_token=None):
    """
    Create an Evernote client instance.
    Uses sandbox mode if EVERNOTE_SANDBOX env var is set to 'true'.
    """
    if not EVERNOTE_AVAILABLE:
        return None
    
    sandbox = os.getenv('EVERNOTE_SANDBOX', 'true').lower() == 'true'
    
    if access_token:
        return EvernoteClient(token=access_token, sandbox=sandbox)
    
    consumer_key = os.getenv('EVERNOTE_CONSUMER_KEY')
    consumer_secret = os.getenv('EVERNOTE_CONSUMER_SECRET')
    
    if not consumer_key or not consumer_secret:
        return None
    
    return EvernoteClient(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        sandbox=sandbox
    )


def enml_to_text(enml_content):
    """
    Convert Evernote ENML format to plain text.
    Strips XML tags and converts common ENML elements.
    """
    if not enml_content:
        return ""
    
    # Remove en-note wrapper
    text = re.sub(r'<\/?en-note[^>]*>', '', enml_content)
    
    # Convert line breaks
    text = re.sub(r'<br\s*\/?>', '\n', text)
    text = re.sub(r'<\/div>', '\n', text)
    text = re.sub(r'<\/p>', '\n\n', text)
    
    # Convert lists
    text = re.sub(r'<li[^>]*>', '• ', text)
    text = re.sub(r'<\/li>', '\n', text)
    
    # Remove en-media tags (images, attachments)
    text = re.sub(r'<en-media[^>]*\/?>', '[attachment]', text)
    
    # Remove all remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Decode HTML entities
    import html
    text = html.unescape(text)
    
    # Clean up whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    
    return text


# ==================== OAUTH ROUTES ====================

@evernote_bp.route('/connect')
@login_required
def connect():
    """
    Start Evernote OAuth flow.
    Redirects user to Evernote for authorization.
    """
    if not EVERNOTE_AVAILABLE:
        return jsonify({'error': 'Evernote SDK not installed'}), 500
    
    client = get_evernote_client()
    if not client:
        return jsonify({'error': 'Evernote not configured. Please set EVERNOTE_CONSUMER_KEY and EVERNOTE_CONSUMER_SECRET.'}), 500
    
    try:
        callback_url = url_for('evernote.callback', _external=True)
        request_token = client.get_request_token(callback_url)
        
        # Store request token in session for callback verification
        session['evernote_request_token'] = request_token
        
        # Redirect to Evernote authorization page
        authorize_url = client.get_authorize_url(request_token)
        return redirect(authorize_url)
    
    except Exception as e:
        current_app.logger.error(f"Evernote OAuth error: {str(e)}")
        return jsonify({'error': f'Failed to start Evernote authorization: {str(e)}'}), 500


@evernote_bp.route('/callback')
@login_required
def callback():
    """
    Handle Evernote OAuth callback.
    Exchanges temporary token for access token and stores it.
    """
    if not EVERNOTE_AVAILABLE:
        return redirect(url_for('dashboard') + '?evernote=error&msg=sdk_not_installed')
    
    oauth_verifier = request.args.get('oauth_verifier')
    request_token = session.get('evernote_request_token')
    
    if not oauth_verifier or not request_token:
        return redirect(url_for('dashboard') + '?evernote=error&msg=missing_token')
    
    try:
        client = get_evernote_client()
        access_token = client.get_access_token(
            request_token['oauth_token'],
            request_token['oauth_token_secret'],
            oauth_verifier
        )
        
        # Store access token in user record
        current_user.evernote_access_token = access_token
        current_user.evernote_connected_at = datetime.utcnow()
        db.session.commit()
        
        # Clean up session
        session.pop('evernote_request_token', None)
        
        return redirect(url_for('dashboard') + '?evernote=connected')
    
    except Exception as e:
        current_app.logger.error(f"Evernote callback error: {str(e)}")
        return redirect(url_for('dashboard') + '?evernote=error&msg=' + str(e))


@evernote_bp.route('/disconnect')
@login_required
def disconnect():
    """
    Disconnect Evernote account.
    Removes stored access token.
    """
    current_user.evernote_access_token = None
    current_user.evernote_connected_at = None
    db.session.commit()
    
    return redirect(url_for('dashboard') + '?evernote=disconnected')


@evernote_bp.route('/status')
@login_required
def status():
    """
    Check Evernote connection status.
    Returns whether user has connected their Evernote account.
    """
    return jsonify({
        'connected': current_user.evernote_access_token is not None,
        'connected_at': current_user.evernote_connected_at.isoformat() if current_user.evernote_connected_at else None,
        'sdk_available': EVERNOTE_AVAILABLE
    })


# ==================== API ROUTES ====================

@evernote_bp.route('/api/search')
@login_required
def search_notes():
    """
    Search user's Evernote notes.
    Query params:
    - q: Search query (diagnosis text)
    - limit: Max results (default 10)
    """
    if not EVERNOTE_AVAILABLE:
        return jsonify({'error': 'Evernote SDK not installed', 'notes': []}), 200
    
    if not current_user.evernote_access_token:
        return jsonify({'error': 'Evernote not connected', 'notes': [], 'connected': False}), 200
    
    query = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 10)), 50)  # Max 50 results
    
    if not query:
        return jsonify({'error': 'No search query provided', 'notes': []}), 400
    
    try:
        client = get_evernote_client(current_user.evernote_access_token)
        note_store = client.get_note_store()
        
        # Build search filter
        note_filter = NoteStore.NoteFilter()
        note_filter.words = query  # Search in title and content
        
        # Specify what metadata to return
        result_spec = NoteStore.NotesMetadataResultSpec()
        result_spec.includeTitle = True
        result_spec.includeUpdated = True
        result_spec.includeCreated = True
        result_spec.includeContentLength = True
        
        # Execute search
        notes_metadata = note_store.findNotesMetadata(note_filter, 0, limit, result_spec)
        
        notes = []
        for note in notes_metadata.notes:
            notes.append({
                'guid': note.guid,
                'title': note.title,
                'created': note.created,
                'updated': note.updated,
                'content_length': note.contentLength
            })
        
        return jsonify({
            'notes': notes,
            'total_notes': notes_metadata.totalNotes,
            'query': query,
            'connected': True
        })
    
    except EDAMUserException as e:
        current_app.logger.error(f"Evernote user error: {e.errorCode}")
        if e.errorCode == 9:  # AUTH_EXPIRED
            # Clear invalid token
            current_user.evernote_access_token = None
            current_user.evernote_connected_at = None
            db.session.commit()
            return jsonify({'error': 'Evernote session expired. Please reconnect.', 'notes': [], 'connected': False}), 200
        return jsonify({'error': f'Evernote error: {e.parameter}', 'notes': []}), 200
    
    except EDAMSystemException as e:
        current_app.logger.error(f"Evernote system error: {e.errorCode}")
        return jsonify({'error': 'Evernote service temporarily unavailable', 'notes': []}), 200
    
    except Exception as e:
        current_app.logger.error(f"Evernote search error: {str(e)}")
        return jsonify({'error': f'Search failed: {str(e)}', 'notes': []}), 200


@evernote_bp.route('/api/note/<guid>')
@login_required
def get_note(guid):
    """
    Fetch content of a specific Evernote note.
    Returns both ENML and plain text versions.
    """
    if not EVERNOTE_AVAILABLE:
        return jsonify({'error': 'Evernote SDK not installed'}), 500
    
    if not current_user.evernote_access_token:
        return jsonify({'error': 'Evernote not connected', 'connected': False}), 401
    
    try:
        client = get_evernote_client(current_user.evernote_access_token)
        note_store = client.get_note_store()
        
        # Fetch note with content
        note = note_store.getNote(guid, True, False, False, False)
        
        # Convert ENML to plain text
        plain_text = enml_to_text(note.content)
        
        return jsonify({
            'guid': note.guid,
            'title': note.title,
            'content_enml': note.content,
            'content_text': plain_text,
            'created': note.created,
            'updated': note.updated,
            'connected': True
        })
    
    except EDAMNotFoundException:
        return jsonify({'error': 'Note not found'}), 404
    
    except EDAMUserException as e:
        if e.errorCode == 9:  # AUTH_EXPIRED
            current_user.evernote_access_token = None
            current_user.evernote_connected_at = None
            db.session.commit()
            return jsonify({'error': 'Evernote session expired', 'connected': False}), 401
        return jsonify({'error': f'Evernote error: {e.parameter}'}), 400
    
    except Exception as e:
        current_app.logger.error(f"Evernote fetch note error: {str(e)}")
        return jsonify({'error': f'Failed to fetch note: {str(e)}'}), 500


def register_evernote_blueprint(app):
    """Register Evernote blueprint with the Flask app."""
    app.register_blueprint(evernote_bp, url_prefix='/evernote')
