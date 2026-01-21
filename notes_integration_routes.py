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
- GET /api/notion/page/<page_id> - Fetch page content (JSON API)
- POST /api/notion/page/<page_id>/append - Append content to page
- GET /notion/view/<page_id> - Server-side rendered page view
- POST /notion/sync-to-notes/<page_id> - Import Notion content to local notes

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
from flask import Blueprint, redirect, url_for, request, jsonify, session, current_app, render_template
from flask_login import login_required, current_user

from models import db, CandidateNote

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


def fetch_blocks_recursive(client, block_id, depth=0, max_depth=5):
    """
    Recursively fetch all blocks and their children from a Notion page.
    
    Args:
        client: Notion API client
        block_id: ID of the block/page to fetch children for
        depth: Current recursion depth (for safety limits)
        max_depth: Maximum recursion depth to prevent infinite loops
    
    Returns:
        List of blocks with nested 'children' key for blocks that have children
    
    Note:
        - Handles pagination via next_cursor for pages with >100 blocks
        - Notion-hosted image URLs expire after ~1 hour (TODO: implement caching/re-hosting)
    """
    if depth > max_depth:
        return []
    
    all_blocks = []
    has_more = True
    start_cursor = None
    
    # Fetch all blocks at this level with pagination
    while has_more:
        try:
            if start_cursor:
                response = client.blocks.children.list(
                    block_id=block_id, 
                    start_cursor=start_cursor,
                    page_size=100
                )
            else:
                response = client.blocks.children.list(
                    block_id=block_id,
                    page_size=100
                )
            
            blocks = response.get('results', [])
            
            # For each block, recursively fetch children if has_children is True
            for block in blocks:
                if block.get('has_children', False):
                    block['children'] = fetch_blocks_recursive(
                        client, 
                        block.get('id'), 
                        depth=depth + 1, 
                        max_depth=max_depth
                    )
                all_blocks.append(block)
            
            has_more = response.get('has_more', False)
            start_cursor = response.get('next_cursor')
            
        except Exception as e:
            current_app.logger.error(f"Error fetching blocks at depth {depth}: {str(e)}")
            break
    
    return all_blocks


def rich_text_to_html(rich_text_array):
    """Convert Notion rich_text array to HTML with formatting."""
    if not rich_text_array:
        return ''
    
    html_parts = []
    for text_obj in rich_text_array:
        content = text_obj.get('plain_text', '')
        annotations = text_obj.get('annotations', {})
        href = text_obj.get('href')
        
        # Escape HTML
        import html
        content = html.escape(content)
        
        # Apply annotations
        if annotations.get('bold'):
            content = f'<strong>{content}</strong>'
        if annotations.get('italic'):
            content = f'<em>{content}</em>'
        if annotations.get('strikethrough'):
            content = f'<del>{content}</del>'
        if annotations.get('underline'):
            content = f'<u>{content}</u>'
        if annotations.get('code'):
            content = f'<code class="notion-inline-code">{content}</code>'
        
        # Color
        color = annotations.get('color', 'default')
        if color != 'default':
            if color.endswith('_background'):
                bg_color = color.replace('_background', '')
                content = f'<span class="notion-bg-{bg_color}">{content}</span>'
            else:
                content = f'<span class="notion-color-{color}">{content}</span>'
        
        # Link
        if href:
            content = f'<a href="{href}" target="_blank" rel="noopener" class="notion-link">{content}</a>'
        
        html_parts.append(content)
    
    return ''.join(html_parts)


def notion_blocks_to_html(blocks, depth=0):
    """
    Recursively convert Notion blocks to styled HTML.
    
    Args:
        blocks: List of Notion block objects (may include nested 'children' key)
        depth: Current recursion depth for indentation tracking
    
    Returns:
        HTML string representation of all blocks
    
    Supports:
        - paragraph, heading_1/2/3, bulleted/numbered lists
        - to_do, toggle (with nested children), code, quote, callout
        - image (file and external URLs), bookmark, embed, video
        - column_list and column (rendered as flex layout)
        - Nested children via recursion
    
    Note:
        Notion-hosted image URLs expire after ~1 hour.
        TODO: Implement image caching/re-hosting for production use.
    """
    import html as html_module
    
    html_parts = []
    list_stack = []  # Track open lists
    
    def close_lists():
        """Close any open list tags."""
        nonlocal list_stack
        result = ''
        while list_stack:
            list_type = list_stack.pop()
            result += f'</{list_type}>'
        return result
    
    for block in blocks:
        block_type = block.get('type')
        block_id = block.get('id', '')
        children = block.get('children', [])
        
        # Handle list items specially - with nested children support
        if block_type == 'bulleted_list_item':
            if not list_stack or list_stack[-1] != 'ul':
                html_parts.append(close_lists())
                html_parts.append('<ul class="notion-bulleted-list">')
                list_stack.append('ul')
            rich_text = block.get('bulleted_list_item', {}).get('rich_text', [])
            content = rich_text_to_html(rich_text)
            # Handle nested children (sub-lists, paragraphs, etc.)
            if children:
                nested_html = notion_blocks_to_html(children, depth=depth + 1)
                html_parts.append(f'<li>{content}<div class="notion-nested">{nested_html}</div></li>')
            else:
                html_parts.append(f'<li>{content}</li>')
            continue
            
        elif block_type == 'numbered_list_item':
            if not list_stack or list_stack[-1] != 'ol':
                html_parts.append(close_lists())
                html_parts.append('<ol class="notion-numbered-list">')
                list_stack.append('ol')
            rich_text = block.get('numbered_list_item', {}).get('rich_text', [])
            content = rich_text_to_html(rich_text)
            # Handle nested children
            if children:
                nested_html = notion_blocks_to_html(children, depth=depth + 1)
                html_parts.append(f'<li>{content}<div class="notion-nested">{nested_html}</div></li>')
            else:
                html_parts.append(f'<li>{content}</li>')
            continue
        
        # Close any open lists for non-list items
        html_parts.append(close_lists())
        
        if block_type == 'paragraph':
            rich_text = block.get('paragraph', {}).get('rich_text', [])
            content = rich_text_to_html(rich_text)
            if content:
                html_parts.append(f'<p class="notion-paragraph">{content}</p>')
            else:
                html_parts.append('<p class="notion-paragraph notion-empty">&nbsp;</p>')
            # Handle nested children in paragraph
            if children:
                html_parts.append(f'<div class="notion-nested">{notion_blocks_to_html(children, depth=depth + 1)}</div>')
                
        elif block_type == 'heading_1':
            rich_text = block.get('heading_1', {}).get('rich_text', [])
            is_toggleable = block.get('heading_1', {}).get('is_toggleable', False)
            heading_html = rich_text_to_html(rich_text)
            if is_toggleable and children:
                nested_html = notion_blocks_to_html(children, depth=depth + 1)
                html_parts.append(f'<details class="notion-toggle-heading"><summary><h1 class="notion-heading-1">{heading_html}</h1></summary><div class="notion-toggle-content">{nested_html}</div></details>')
            else:
                html_parts.append(f'<h1 class="notion-heading-1">{heading_html}</h1>')
            
        elif block_type == 'heading_2':
            rich_text = block.get('heading_2', {}).get('rich_text', [])
            is_toggleable = block.get('heading_2', {}).get('is_toggleable', False)
            heading_html = rich_text_to_html(rich_text)
            if is_toggleable and children:
                nested_html = notion_blocks_to_html(children, depth=depth + 1)
                html_parts.append(f'<details class="notion-toggle-heading"><summary><h2 class="notion-heading-2">{heading_html}</h2></summary><div class="notion-toggle-content">{nested_html}</div></details>')
            else:
                html_parts.append(f'<h2 class="notion-heading-2">{heading_html}</h2>')
            
        elif block_type == 'heading_3':
            rich_text = block.get('heading_3', {}).get('rich_text', [])
            is_toggleable = block.get('heading_3', {}).get('is_toggleable', False)
            heading_html = rich_text_to_html(rich_text)
            if is_toggleable and children:
                nested_html = notion_blocks_to_html(children, depth=depth + 1)
                html_parts.append(f'<details class="notion-toggle-heading"><summary><h3 class="notion-heading-3">{heading_html}</h3></summary><div class="notion-toggle-content">{nested_html}</div></details>')
            else:
                html_parts.append(f'<h3 class="notion-heading-3">{heading_html}</h3>')
            
        elif block_type == 'to_do':
            rich_text = block.get('to_do', {}).get('rich_text', [])
            checked = block.get('to_do', {}).get('checked', False)
            checked_class = 'checked' if checked else ''
            checkbox = '☑' if checked else '☐'
            content = f'<div class="notion-to-do {checked_class}"><span class="notion-checkbox">{checkbox}</span> {rich_text_to_html(rich_text)}</div>'
            html_parts.append(content)
            # Handle nested children in to_do
            if children:
                html_parts.append(f'<div class="notion-nested notion-todo-nested">{notion_blocks_to_html(children, depth=depth + 1)}</div>')
            
        elif block_type == 'toggle':
            rich_text = block.get('toggle', {}).get('rich_text', [])
            toggle_content = rich_text_to_html(rich_text)
            # Toggle blocks should have children content
            nested_html = notion_blocks_to_html(children, depth=depth + 1) if children else ''
            html_parts.append(f'<details class="notion-toggle"><summary>{toggle_content}</summary><div class="notion-toggle-content">{nested_html}</div></details>')
            
        elif block_type == 'code':
            rich_text = block.get('code', {}).get('rich_text', [])
            language = block.get('code', {}).get('language', 'plain text')
            code_text = ''.join([t.get('plain_text', '') for t in rich_text])
            code_text = html_module.escape(code_text)
            html_parts.append(f'<div class="notion-code-block"><div class="notion-code-language">{language}</div><pre><code>{code_text}</code></pre></div>')
            
        elif block_type == 'quote':
            rich_text = block.get('quote', {}).get('rich_text', [])
            quote_content = rich_text_to_html(rich_text)
            # Handle nested children in quote
            if children:
                nested_html = notion_blocks_to_html(children, depth=depth + 1)
                html_parts.append(f'<blockquote class="notion-quote">{quote_content}<div class="notion-quote-nested">{nested_html}</div></blockquote>')
            else:
                html_parts.append(f'<blockquote class="notion-quote">{quote_content}</blockquote>')
            
        elif block_type == 'callout':
            rich_text = block.get('callout', {}).get('rich_text', [])
            icon = block.get('callout', {}).get('icon', {})
            emoji = icon.get('emoji', '💡') if icon.get('type') == 'emoji' else '💡'
            callout_content = rich_text_to_html(rich_text)
            # Handle nested children in callout
            if children:
                nested_html = notion_blocks_to_html(children, depth=depth + 1)
                html_parts.append(f'<div class="notion-callout"><span class="notion-callout-icon">{emoji}</span><div class="notion-callout-content">{callout_content}<div class="notion-callout-nested">{nested_html}</div></div></div>')
            else:
                html_parts.append(f'<div class="notion-callout"><span class="notion-callout-icon">{emoji}</span><div class="notion-callout-content">{callout_content}</div></div>')
            
        elif block_type == 'divider':
            html_parts.append('<hr class="notion-divider">')
            
        elif block_type == 'image':
            image_data = block.get('image', {})
            image_type = image_data.get('type', '')
            caption = image_data.get('caption', [])
            
            # Get image URL
            # NOTE: Notion-hosted (file type) URLs expire after ~1 hour
            # TODO: Implement image caching/re-hosting for production
            image_url = ''
            if image_type == 'external':
                image_url = image_data.get('external', {}).get('url', '')
            elif image_type == 'file':
                image_url = image_data.get('file', {}).get('url', '')
            
            if image_url:
                caption_html = rich_text_to_html(caption) if caption else ''
                # Escape the URL for safety
                safe_url = html_module.escape(image_url)
                html_parts.append(f'''
                    <figure class="notion-image">
                        <img src="{safe_url}" alt="{caption_html}" loading="lazy">
                        {f'<figcaption>{caption_html}</figcaption>' if caption_html else ''}
                    </figure>
                ''')
                
        elif block_type == 'bookmark':
            url = block.get('bookmark', {}).get('url', '')
            caption = block.get('bookmark', {}).get('caption', [])
            caption_html = rich_text_to_html(caption) if caption else html_module.escape(url)
            safe_url = html_module.escape(url)
            html_parts.append(f'<a href="{safe_url}" target="_blank" rel="noopener" class="notion-bookmark">{caption_html}</a>')
            
        elif block_type == 'embed':
            url = block.get('embed', {}).get('url', '')
            safe_url = html_module.escape(url)
            html_parts.append(f'<div class="notion-embed"><a href="{safe_url}" target="_blank" rel="noopener">🔗 Embedded content: {safe_url}</a></div>')
            
        elif block_type == 'video':
            video_data = block.get('video', {})
            video_type = video_data.get('type', '')
            video_url = ''
            if video_type == 'external':
                video_url = video_data.get('external', {}).get('url', '')
            elif video_type == 'file':
                video_url = video_data.get('file', {}).get('url', '')
            if video_url:
                safe_url = html_module.escape(video_url)
                html_parts.append(f'<div class="notion-video"><a href="{safe_url}" target="_blank" rel="noopener">🎬 Video: {safe_url}</a></div>')
                
        elif block_type == 'table':
            # Tables are complex - render placeholder but acknowledge children exist
            html_parts.append('<div class="notion-table-placeholder">📊 Table (view in Notion for full formatting)</div>')
            
        elif block_type == 'column_list':
            # Render column_list as a flex container with its column children
            columns_html = []
            for col_block in children:
                if col_block.get('type') == 'column':
                    col_children = col_block.get('children', [])
                    col_content = notion_blocks_to_html(col_children, depth=depth + 1) if col_children else ''
                    columns_html.append(f'<div class="notion-column">{col_content}</div>')
            if columns_html:
                html_parts.append(f'<div class="notion-column-list">{" ".join(columns_html)}</div>')
            
        elif block_type == 'column':
            # Columns are handled by column_list parent; if standalone, render children
            if children:
                html_parts.append(f'<div class="notion-column">{notion_blocks_to_html(children, depth=depth + 1)}</div>')
                
        elif block_type == 'synced_block':
            # Synced blocks contain synced content as children
            if children:
                html_parts.append(f'<div class="notion-synced-block">{notion_blocks_to_html(children, depth=depth + 1)}</div>')
                
        elif block_type == 'child_page':
            # Child page reference
            title = block.get('child_page', {}).get('title', 'Untitled')
            html_parts.append(f'<div class="notion-child-page">📄 <span class="notion-child-page-title">{html_module.escape(title)}</span></div>')
            
        elif block_type == 'child_database':
            # Child database reference
            title = block.get('child_database', {}).get('title', 'Untitled Database')
            html_parts.append(f'<div class="notion-child-database">🗃️ <span class="notion-child-database-title">{html_module.escape(title)}</span></div>')
    
    # Close any remaining open lists
    html_parts.append(close_lists())
    
    return '\n'.join(html_parts)


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
    """Search Notion pages by query.
    
    Query params:
    - q: search query (required)
    - limit: max results (default 10, max 50)
    - strict: if 'true', filter results to only pages containing the exact phrase in title
    """
    if not current_user.notion_access_token:
        return jsonify({'error': 'Notion not connected', 'pages': [], 'connected': False}), 200
    
    query = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 10)), 50)
    strict_mode = request.args.get('strict', 'false').lower() == 'true'
    
    if not query:
        return jsonify({'error': 'No search query provided', 'pages': []}), 400
    
    try:
        client = get_notion_client(current_user.notion_access_token)
        if not client:
            return jsonify({'error': 'Notion SDK not available', 'pages': []}), 200
        
        # For strict mode, fetch more results to filter from
        fetch_limit = limit * 5 if strict_mode else limit
        
        # Search pages
        results = client.search(
            query=query,
            filter={'property': 'object', 'value': 'page'},
            page_size=min(fetch_limit, 50)
        )
        
        pages = []
        query_lower = query.lower()
        
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
            
            # For strict mode, only include pages where title contains the exact phrase
            if strict_mode:
                if query_lower not in title.lower():
                    continue
            
            pages.append({
                'id': page.get('id'),
                'title': title,
                'url': page.get('url'),
                'created_time': page.get('created_time'),
                'last_edited_time': page.get('last_edited_time'),
                'icon': page.get('icon', {}).get('emoji') if page.get('icon') else None
            })
            
            # Stop once we have enough results
            if len(pages) >= limit:
                break
        
        return jsonify({
            'pages': pages,
            'total': len(pages),
            'query': query,
            'strict': strict_mode,
            'connected': True
        })
    
    except Exception as e:
        current_app.logger.error(f"Notion search error: {str(e)}")
        return jsonify({'error': str(e), 'pages': []}), 200


@notes_bp.route('/api/notion/page/<page_id>')
@login_required
def notion_get_page(page_id):
    """Fetch content of a Notion page with recursive block fetching and HTML rendering."""
    if not current_user.notion_access_token:
        return jsonify({'error': 'Notion not connected', 'connected': False}), 401
    
    try:
        client = get_notion_client(current_user.notion_access_token)
        if not client:
            return jsonify({'error': 'Notion SDK not available'}), 500
        
        # Get page metadata
        page = client.pages.retrieve(page_id=page_id)
        
        # Recursively fetch all blocks including nested children
        all_blocks = fetch_blocks_recursive(client, page_id)
        
        # Convert blocks to HTML (recursive function handles nested blocks)
        content_html = notion_blocks_to_html(all_blocks)
        
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
        
        # Get cover image if exists
        cover_url = None
        cover = page.get('cover')
        if cover:
            if cover.get('type') == 'external':
                cover_url = cover.get('external', {}).get('url')
            elif cover.get('type') == 'file':
                cover_url = cover.get('file', {}).get('url')
        
        # Get icon
        icon = None
        icon_data = page.get('icon')
        if icon_data:
            if icon_data.get('type') == 'emoji':
                icon = icon_data.get('emoji')
            elif icon_data.get('type') == 'external':
                icon = icon_data.get('external', {}).get('url')
        
        return jsonify({
            'id': page_id,
            'title': title,
            'url': page.get('url'),
            'content_html': content_html,
            'cover_url': cover_url,
            'icon': icon,
            'created_time': page.get('created_time'),
            'last_edited_time': page.get('last_edited_time'),
            'connected': True
        })
    
    except Exception as e:
        current_app.logger.error(f"Notion page fetch error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@notes_bp.route('/notion/view/<page_id>')
@login_required
def notion_view_page(page_id):
    """
    Server-side render a Notion page with full HTML output.
    
    This route renders a complete HTML page using Jinja2, suitable for
    full-page viewing of Notion content within the app.
    
    Args:
        page_id: Notion page ID to render
    
    Returns:
        Rendered HTML template with Notion content
    """
    if not current_user.notion_access_token:
        return redirect(url_for('notes_integration.notion_connect'))
    
    try:
        client = get_notion_client(current_user.notion_access_token)
        if not client:
            return render_template('notion_page.html', 
                                   error='Notion SDK not available',
                                   page=None,
                                   content_html='')
        
        # Get page metadata
        page = client.pages.retrieve(page_id=page_id)
        
        # Recursively fetch all blocks including nested children
        all_blocks = fetch_blocks_recursive(client, page_id)
        
        # Convert blocks to HTML
        content_html = notion_blocks_to_html(all_blocks)
        
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
        
        # Get cover image if exists
        cover_url = None
        cover = page.get('cover')
        if cover:
            if cover.get('type') == 'external':
                cover_url = cover.get('external', {}).get('url')
            elif cover.get('type') == 'file':
                cover_url = cover.get('file', {}).get('url')
        
        # Get icon
        icon = None
        icon_data = page.get('icon')
        if icon_data:
            if icon_data.get('type') == 'emoji':
                icon = icon_data.get('emoji')
            elif icon_data.get('type') == 'external':
                icon = icon_data.get('external', {}).get('url')
        
        # Build page data object
        page_data = {
            'id': page_id,
            'title': title,
            'url': page.get('url'),
            'cover_url': cover_url,
            'icon': icon,
            'created_time': page.get('created_time'),
            'last_edited_time': page.get('last_edited_time')
        }
        
        return render_template('notion_page.html',
                               page=page_data,
                               content_html=content_html,
                               error=None)
    
    except Exception as e:
        current_app.logger.error(f"Notion page view error: {str(e)}")
        return render_template('notion_page.html',
                               error=str(e),
                               page=None,
                               content_html='')


@notes_bp.route('/api/notion/page/<page_id>/append', methods=['POST'])
@login_required
def notion_append_to_page(page_id):
    """Append content to a Notion page."""
    if not current_user.notion_access_token:
        return jsonify({'error': 'Notion not connected', 'connected': False}), 401
    
    try:
        data = request.get_json()
        content = data.get('content', '')
        
        if not content:
            return jsonify({'error': 'No content provided'}), 400
        
        client = get_notion_client(current_user.notion_access_token)
        if not client:
            return jsonify({'error': 'Notion SDK not available'}), 500
        
        # Create blocks to append
        # Split content by newlines and create paragraph blocks
        lines = content.strip().split('\n')
        children = []
        
        for line in lines:
            if line.strip():
                children.append({
                    'object': 'block',
                    'type': 'paragraph',
                    'paragraph': {
                        'rich_text': [{
                            'type': 'text',
                            'text': {'content': line}
                        }]
                    }
                })
        
        if not children:
            return jsonify({'error': 'No valid content to append'}), 400
        
        # Add a divider before the new content
        children.insert(0, {
            'object': 'block',
            'type': 'divider',
            'divider': {}
        })
        
        # Add a timestamp header
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        children.insert(1, {
            'object': 'block',
            'type': 'paragraph',
            'paragraph': {
                'rich_text': [{
                    'type': 'text',
                    'text': {'content': f'📝 Added from FRCR-Revision on {timestamp}'},
                    'annotations': {'italic': True, 'color': 'gray'}
                }]
            }
        })
        
        # Append blocks to the page
        result = client.blocks.children.append(
            block_id=page_id,
            children=children
        )
        
        return jsonify({
            'success': True,
            'message': 'Content added to Notion page',
            'blocks_added': len(children)
        })
    
    except Exception as e:
        current_app.logger.error(f"Notion append error: {str(e)}")
        return jsonify({'error': str(e)}), 500


def extract_text_from_blocks(blocks, depth=0):
    """
    Extract plain text from Notion blocks recursively.
    
    Used for syncing Notion content to local notes storage.
    Preserves some formatting with markdown-like syntax.
    
    Args:
        blocks: List of Notion blocks (may include nested 'children')
        depth: Current recursion depth for indentation
    
    Returns:
        Plain text string representation of all blocks
    """
    text_parts = []
    indent = '  ' * depth
    
    for block in blocks:
        block_type = block.get('type')
        children = block.get('children', [])
        
        # Extract rich_text content helper
        def get_text(rich_text_array):
            return ''.join([t.get('plain_text', '') for t in rich_text_array])
        
        if block_type == 'paragraph':
            text = get_text(block.get('paragraph', {}).get('rich_text', []))
            if text:
                text_parts.append(f"{indent}{text}")
                
        elif block_type in ['heading_1', 'heading_2', 'heading_3']:
            text = get_text(block.get(block_type, {}).get('rich_text', []))
            prefix = '#' * int(block_type[-1])
            text_parts.append(f"\n{indent}{prefix} {text}\n")
            
        elif block_type == 'bulleted_list_item':
            text = get_text(block.get('bulleted_list_item', {}).get('rich_text', []))
            text_parts.append(f"{indent}• {text}")
            
        elif block_type == 'numbered_list_item':
            text = get_text(block.get('numbered_list_item', {}).get('rich_text', []))
            text_parts.append(f"{indent}- {text}")
            
        elif block_type == 'to_do':
            text = get_text(block.get('to_do', {}).get('rich_text', []))
            checked = block.get('to_do', {}).get('checked', False)
            checkbox = '☑' if checked else '☐'
            text_parts.append(f"{indent}{checkbox} {text}")
            
        elif block_type == 'toggle':
            text = get_text(block.get('toggle', {}).get('rich_text', []))
            text_parts.append(f"{indent}▸ {text}")
            
        elif block_type == 'code':
            text = get_text(block.get('code', {}).get('rich_text', []))
            language = block.get('code', {}).get('language', '')
            text_parts.append(f"\n{indent}```{language}\n{indent}{text}\n{indent}```\n")
            
        elif block_type == 'quote':
            text = get_text(block.get('quote', {}).get('rich_text', []))
            text_parts.append(f"{indent}> {text}")
            
        elif block_type == 'callout':
            text = get_text(block.get('callout', {}).get('rich_text', []))
            icon = block.get('callout', {}).get('icon', {})
            emoji = icon.get('emoji', '💡') if icon.get('type') == 'emoji' else '💡'
            text_parts.append(f"{indent}{emoji} {text}")
            
        elif block_type == 'divider':
            text_parts.append(f"\n{indent}---\n")
            
        elif block_type == 'image':
            caption = get_text(block.get('image', {}).get('caption', []))
            text_parts.append(f"{indent}[Image: {caption if caption else 'No caption'}]")
            
        elif block_type == 'bookmark':
            url = block.get('bookmark', {}).get('url', '')
            text_parts.append(f"{indent}[Bookmark: {url}]")
            
        elif block_type == 'child_page':
            title = block.get('child_page', {}).get('title', 'Untitled')
            text_parts.append(f"{indent}📄 {title}")
            
        elif block_type == 'column_list':
            # Process columns sequentially
            for col in children:
                if col.get('type') == 'column':
                    col_children = col.get('children', [])
                    if col_children:
                        text_parts.append(extract_text_from_blocks(col_children, depth))
            children = []  # Already processed
        
        # Process nested children
        if children:
            nested_text = extract_text_from_blocks(children, depth + 1)
            if nested_text:
                text_parts.append(nested_text)
    
    return '\n'.join(filter(None, text_parts))


@notes_bp.route('/notion/sync-to-notes/<page_id>', methods=['POST'])
@login_required
def notion_sync_to_notes(page_id):
    """
    Import Notion page content into local CandidateNote for a specific case.
    
    This allows students to copy Notion content into their case-specific notes
    for offline access and integration with the app's note-taking features.
    
    Request JSON:
        - case_id: Required. The case ID to associate the notes with.
        - mode: Optional. 'append' (default) or 'replace'
    
    Returns:
        JSON with success status and note details
    """
    if not current_user.notion_access_token:
        return jsonify({'error': 'Notion not connected', 'connected': False}), 401
    
    try:
        data = request.get_json() or {}
        case_id = data.get('case_id')
        mode = data.get('mode', 'append')  # 'append' or 'replace'
        
        if not case_id:
            return jsonify({'error': 'case_id is required'}), 400
        
        client = get_notion_client(current_user.notion_access_token)
        if not client:
            return jsonify({'error': 'Notion SDK not available'}), 500
        
        # Get page metadata for title
        page = client.pages.retrieve(page_id=page_id)
        
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
        
        # Recursively fetch all blocks
        all_blocks = fetch_blocks_recursive(client, page_id)
        
        # Extract plain text content
        content_text = extract_text_from_blocks(all_blocks)
        
        if not content_text.strip():
            return jsonify({'error': 'No text content found in Notion page'}), 400
        
        # Build the note content with header
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        header = f"[From Notion: {title} - Synced {timestamp}]\n"
        new_content = header + content_text
        
        # Get or create the user's note for this case
        note = CandidateNote.query.filter_by(
            case_id=case_id,
            user_id=current_user.id
        ).first()
        
        if note:
            if mode == 'replace':
                note.note_text = new_content
            else:  # append
                separator = '\n\n---\n\n' if note.note_text.strip() else ''
                note.note_text = note.note_text + separator + new_content
            note.updated_at = datetime.utcnow()
        else:
            note = CandidateNote(
                case_id=case_id,
                user_id=current_user.id,
                note_text=new_content
            )
            db.session.add(note)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Notion content synced to notes ({mode})',
            'note_id': note.id,
            'case_id': case_id,
            'page_title': title,
            'content_length': len(content_text)
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Notion sync-to-notes error: {str(e)}")
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
    """Create a flashcard in Anki.
    
    Request JSON:
        - front: Front side text (required)
        - back: Back side text (required)
        - deck: Deck name (optional, uses user's default)
        - tags: List of tags (optional)
        - allow_duplicate: Boolean, allow duplicate cards (default: True)
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    front = data.get('front', '').strip()
    back = data.get('back', '').strip()
    deck_name = data.get('deck', current_user.anki_deck_name or 'FRCR Revision')
    tags = data.get('tags', ['FRCR', 'Radiology'])
    allow_duplicate = data.get('allow_duplicate', True)
    
    if not front or not back:
        return jsonify({'error': 'Front and back content required'}), 400
    
    # Ensure deck exists
    anki_request('createDeck', deck=deck_name)
    
    # Check for duplicates if not allowing them
    if not allow_duplicate:
        # Search for existing note with same front and back
        query = f'Front:"{front}" Back:"{back}"'
        existing_notes, find_error = anki_request('findNotes', query=query)
        
        if find_error:
            current_app.logger.warning(f"Error checking for duplicates: {find_error}")
        elif existing_notes and len(existing_notes) > 0:
            return jsonify({
                'success': False,
                'error': 'A card with this content already exists',
                'duplicate': True,
                'existing_note_ids': existing_notes
            }), 200
    
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
                'allowDuplicate': allow_duplicate
            }
        }
    )
    
    if error:
        # Check if it's a duplicate error and provide better message
        if 'duplicate' in error.lower() or 'cannot create note' in error.lower():
            return jsonify({
                'success': False,
                'error': 'A card with this content already exists. Set allow_duplicate=true to create anyway.',
                'duplicate': True
            }), 200
        return jsonify({'success': False, 'error': error}), 200
    
    return jsonify({
        'success': True,
        'note_id': result,
        'deck': deck_name
    })


@notes_bp.route('/api/anki/flashcard/bulk', methods=['POST'])
@login_required
def anki_create_bulk_flashcards():
    """Create multiple flashcards from Q&A pairs.
    
    Request JSON:
        - cards: List of {front, back} objects (required)
        - deck: Deck name (optional)
        - tags: List of tags (optional)
        - allow_duplicate: Boolean, allow duplicate cards (default: True)
    """
    data = request.get_json()
    
    if not data or 'cards' not in data:
        return jsonify({'error': 'No cards provided'}), 400
    
    cards = data.get('cards', [])
    deck_name = data.get('deck', current_user.anki_deck_name or 'FRCR Revision')
    tags = data.get('tags', ['FRCR', 'Radiology'])
    allow_duplicate = data.get('allow_duplicate', True)
    
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
                    'allowDuplicate': allow_duplicate
                }
            })
    
    if not notes:
        return jsonify({'error': 'No valid cards to create'}), 400
    
    result, error = anki_request('addNotes', notes=notes)
    
    if error:
        return jsonify({'success': False, 'error': error}), 200
    
    # Count successful additions (non-null results)
    # AnkiConnect returns None for duplicates when allowDuplicate=False
    created = sum(1 for r in result if r is not None) if result else 0
    skipped = len(notes) - created
    
    response = {
        'success': True,
        'created': created,
        'total': len(notes),
        'deck': deck_name
    }
    
    if skipped > 0:
        response['skipped'] = skipped
        response['message'] = f'Created {created} cards, {skipped} skipped (duplicates)'
    
    return jsonify(response)


@notes_bp.route('/api/anki/search')
@login_required
def anki_search():
    """Search Anki flashcards by query.
    
    Query params:
        - q: Search query (required)
        - deck: Filter by deck name (optional)
        - limit: Max results (default 50, max 100)
    """
    query = request.args.get('q', '').strip()
    deck_filter = request.args.get('deck', '')
    limit = min(int(request.args.get('limit', 50)), 100)
    
    if not query:
        return jsonify({'error': 'Search query required', 'cards': []}), 400
    
    # Build Anki search query
    # Anki uses a special query syntax: https://docs.ankiweb.net/searching.html
    anki_query = query
    
    # If deck filter specified, add it to query
    if deck_filter:
        anki_query = f'deck:"{deck_filter}" {anki_query}'
    
    # Find notes matching the query
    note_ids, error = anki_request('findNotes', query=anki_query)
    
    if error:
        return jsonify({'error': error, 'cards': []}), 200
    
    if not note_ids:
        return jsonify({
            'cards': [],
            'total': 0,
            'query': query
        })
    
    # Limit results
    note_ids = note_ids[:limit]
    
    # Get note details
    notes_info, info_error = anki_request('notesInfo', notes=note_ids)
    
    if info_error:
        return jsonify({'error': info_error, 'cards': []}), 200
    
    # Format cards for response
    cards = []
    for note in notes_info or []:
        fields = note.get('fields', {})
        front = fields.get('Front', {}).get('value', '')
        back = fields.get('Back', {}).get('value', '')
        
        cards.append({
            'note_id': note.get('noteId'),
            'front': front,
            'back': back,
            'deck': note.get('deckName', ''),
            'tags': note.get('tags', []),
            'created': note.get('fields', {}).get('Front', {}).get('value', ''),
            'modified': note.get('mod', 0)  # Unix timestamp
        })
    
    return jsonify({
        'cards': cards,
        'total': len(cards),
        'query': query
    })


@notes_bp.route('/api/anki/note/<int:note_id>')
@login_required
def anki_get_note(note_id):
    """Get details of a specific Anki note."""
    notes_info, error = anki_request('notesInfo', notes=[note_id])
    
    if error:
        return jsonify({'error': error}), 200
    
    if not notes_info or len(notes_info) == 0:
        return jsonify({'error': 'Note not found'}), 404
    
    note = notes_info[0]
    fields = note.get('fields', {})
    front = fields.get('Front', {}).get('value', '')
    back = fields.get('Back', {}).get('value', '')
    
    return jsonify({
        'note_id': note.get('noteId'),
        'front': front,
        'back': back,
        'deck': note.get('deckName', ''),
        'tags': note.get('tags', []),
        'model': note.get('modelName', ''),
        'created': note.get('fields', {}).get('Front', {}).get('value', ''),
        'modified': note.get('mod', 0)
    })


def register_notes_blueprint(app):
    """Register notes integration blueprint with the Flask app."""
    app.register_blueprint(notes_bp)
