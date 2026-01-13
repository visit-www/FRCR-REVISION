
# ==================== STUDENT CASE BROWSER ====================
# (Moved below app initialization)
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file, flash
from models import UserRole
from flask_cors import CORS
from flask_login import LoginManager, login_required, current_user
from flask_migrate import Migrate
from models import db, User, Case, CaseImage, Question, Answer
from models import RevisionSession, RevisionHistory  # STUDENT REVISION: New models for balanced revision
from auth import auth_bp
from backup_routes import backup_bp
from admin_routes import admin_bp
from admin_enrichment_routes import enrichment_bp
from datetime import datetime
from sqlalchemy.pool import NullPool
import os
from io import BytesIO
import mimetypes

app = Flask(__name__, 
    template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
    static_folder=os.path.join(os.path.dirname(__file__), 'static')
)

# Enable CORS for Vercel frontend access
CORS(app, resources={
    r"/api/*": {
        "origins": ["*"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Ensure instance folder exists
instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
try:
    os.makedirs(instance_path, exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create instance folder: {e}")
    instance_path = '/tmp'

# Configuration
# Use PostgreSQL on production (Vercel), SQLite locally
# Vercel Supabase integration uses POSTGRES_URL_NON_POOLING for direct connection
# Priority: Use non-pooling URL first for serverless environments
DATABASE_URL = os.getenv('POSTGRES_URL_NON_POOLING') or os.getenv('DATABASE_POSTGRES_URL_NON_POOLING') or os.getenv('DATABASE_URL') or os.getenv('DATABASE_POSTGRES_URL') or os.getenv('POSTGRES_URL')

if DATABASE_URL:
    # PostgreSQL on Vercel or external
    print(f"[DB] Using PostgreSQL: {DATABASE_URL[:60]}...")
    # Handle both postgres:// and postgresql:// schemes
    db_uri = DATABASE_URL.replace('postgres://', 'postgresql://')
    
    # Remove unsupported query parameters (pgbouncer, supa, etc.) that cause psycopg2 errors
    # These are often added by Supabase but not recognized by psycopg2
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    
    try:
        parsed = urlparse(db_uri)
        if parsed.query:
            # Parse query parameters
            params = parse_qs(parsed.query, keep_blank_values=True)
            # Remove unsupported parameters
            unsupported_params = ['supa', 'pgbouncer', 'supabase']
            for param in unsupported_params:
                params.pop(param, None)
            
            # Rebuild query string
            new_query = urlencode(params, doseq=True) if params else ''
            # Rebuild URL
            db_uri = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment
            ))
            print(f"[DB] Cleaned query parameters from connection string")
    except Exception as e:
        print(f"[DB] Warning: Could not parse URL parameters: {e}")
    
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    
    # For serverless environments (Vercel), disable connection pooling
    # Each function invocation should create and close its own connection
    if os.getenv('VERCEL'):
        print("[DB] Serverless environment detected - using NullPool for PostgreSQL/Supabase")
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'poolclass': NullPool,  # No connection pooling for serverless
            'pool_pre_ping': True,  # Verify connections before using
            'connect_args': {
                'connect_timeout': 10,  # 10 second connection timeout
                'options': '-c statement_timeout=300000'  # 5 minute statement timeout for long imports
            }
        }
else:
    # SQLite for local development
    print(f"[DB] Using SQLite: {instance_path}/frcr_examiner.db")
    sqlite_path = os.path.join(instance_path, "frcr_examiner.db")
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sqlite_path}'
    # Configure SQLite for local development only
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'connect_args': {
            'timeout': 30,  # 30 second timeout for database operations
            'check_same_thread': False  # Allow multi-threaded access
        }
    }
# SECRET_KEY is required for production security
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    # In production, SECRET_KEY must be set via environment variable
    if os.getenv('VERCEL') or os.getenv('VERCEL_ENV') == 'production':
        raise ValueError("SECRET_KEY environment variable is required in production. Please set it in your deployment environment.")
    # For local development only, use a default (with warning)
    SECRET_KEY = 'dev-secret-key-change-in-production'
    print("[WARNING] SECRET_KEY not set! Using insecure default for local development only.")
    print("[WARNING] Set SECRET_KEY environment variable before deploying to production.")
else:
    print("[OK] SECRET_KEY is set from environment variable")

app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Only set SECURE in production (HTTPS)
is_production = os.getenv('VERCEL_ENV') == 'production' or 'vercel.app' in os.getenv('VERCEL_URL', '')
app.config['SESSION_COOKIE_SECURE'] = is_production  # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True  # No JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
app.config['SESSION_COOKIE_NAME'] = 'frcr_session'  # Explicit name
# Industry standard: 30 minutes session timeout (1800 seconds)
# Sessions will expire after 30 minutes of inactivity
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes
app.config['SESSION_COOKIE_MAX_AGE'] = 1800  # Cookie expires in 30 minutes

# For serverless (Vercel), don't set cookie domain to allow cross-subdomain cookies
# This ensures cookies work across *.vercel.app subdomains
# 
# IMPORTANT: We are NOT storing credentials in cookies!
# - Credentials (password hashes) are stored in the DATABASE only
# - The cookie only stores a SESSION IDENTIFIER (user_id) to track "who is logged in"
# - Flask-Login stores minimal data: just the user ID (e.g., {"user_id": 1})
# - On each request, the server reads the user_id from the cookie, then looks up the user in the database
# - This is necessary in serverless because we can't use in-memory session storage
if os.getenv('VERCEL'):
    app.config['SESSION_COOKIE_DOMAIN'] = None  # Use default (current domain)
    print("[SESSION] Serverless environment detected - using default cookie domain")

print(f"[SESSION] SECURE={app.config['SESSION_COOKIE_SECURE']}, HTTPONLY={app.config['SESSION_COOKIE_HTTPONLY']}, SAMESITE={app.config['SESSION_COOKIE_SAMESITE']}")

# Initialize database
db.init_app(app)

# Initialize Flask-Migrate for Alembic migrations
migrate = Migrate(app, db)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to continue'

@login_manager.user_loader
def load_user(user_id):
    """Load user from database by ID"""
    try:
        user = User.query.get(int(user_id))
        if user:
            # Ensure role is properly set
            # If user has is_admin flag but role is not ADMIN, fix it
            if user.is_admin:
                if not isinstance(user.role, UserRole) or user.role != UserRole.ADMIN:
                    print(f"[AUTH] Fixing user {user_id} ({user.email}) role: is_admin=True but role={user.role}, setting to ADMIN")
                    user.role = UserRole.ADMIN
                    db.session.commit()
            
            # Ensure role is a UserRole enum (not string)
            if isinstance(user.role, str):
                try:
                    user.role = UserRole(user.role.lower())
                    db.session.commit()
                    print(f"[AUTH] Converted user {user_id} role from string to enum: {user.role}")
                except (ValueError, KeyError) as e:
                    print(f"[AUTH] Error converting role for user {user_id}: {e}")
            
            # Debug log for admin users
            if isinstance(user.role, UserRole) and user.role == UserRole.ADMIN:
                print(f"[AUTH] Loaded admin user: {user.email} (ID: {user_id}, Role: {user.role.value})")
            
        return user
    except Exception as e:
        print(f"[AUTH] Error loading user {user_id}: {e}")
        import traceback
        traceback.print_exc()
        return None

@login_manager.unauthorized_handler
def unauthorized():
    """Handle unauthorized access - redirect to login"""
    print(f"[AUTH] Unauthorized access attempt. Redirecting to login.")
    from flask import redirect, url_for, request
    # If it's an AJAX request, return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'Login required'}), 401
    # Otherwise redirect to login
    return redirect(url_for('auth.login'))

# Activity tracking for session timeout
@app.before_request
def track_activity():
    """Track user activity to refresh session and detect inactivity"""
    from flask import session as flask_session
    from datetime import datetime, timedelta
    
    # Skip for static files, health checks, and auth endpoints
    if (request.endpoint in ['static', None] or 
        request.path.startswith('/static') or
        request.path.startswith('/auth/login') or
        request.path.startswith('/auth/register')):
        return
    
    # Only track activity for authenticated users
    if current_user.is_authenticated:
        try:
            # Check if session should expire
            last_activity_str = flask_session.get('last_activity')
            if last_activity_str:
                try:
                    last_activity = datetime.fromisoformat(last_activity_str)
                    time_since_activity = datetime.utcnow() - last_activity
                    
                    # If more than 30 minutes of inactivity, expire session
                    if time_since_activity > timedelta(seconds=1800):
                        from flask_login import logout_user
                        logout_user()
                        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            from flask import jsonify
                            return jsonify({'error': 'Session expired due to inactivity', 'expired': True}), 401
                        return redirect(url_for('auth.login'))
                except (ValueError, TypeError):
                    # Invalid timestamp, reset it
                    pass
            
            # Only update last activity if enough time has passed (avoid excessive updates)
            # This prevents showing expiry messages on every page refresh
            # We already have last_activity_str from above, reuse it
            should_update_activity = True
            
            if last_activity_str:
                try:
                    last_activity = datetime.fromisoformat(last_activity_str)
                    time_since_update = datetime.utcnow() - last_activity
                    # Only update if at least 1 minute has passed (reduces session writes)
                    # This prevents the expiry warning from showing on every page refresh
                    if time_since_update < timedelta(seconds=60):
                        should_update_activity = False
                except (ValueError, TypeError):
                    # Invalid timestamp, reset it
                    pass
            
            if should_update_activity:
                flask_session['last_activity'] = datetime.utcnow().isoformat()
                flask_session.permanent = True
            
            # Reload user from database to ensure role is up-to-date
            # This fixes the issue where role changes don't reflect until re-login
            # Only refresh periodically (every 5 minutes) to avoid excessive DB queries
            try:
                last_refresh_str = flask_session.get('user_refreshed_at')
                should_refresh_user = True
                
                if last_refresh_str:
                    try:
                        last_refresh = datetime.fromisoformat(last_refresh_str)
                        time_since_refresh = datetime.utcnow() - last_refresh
                        # Only refresh user every 5 minutes
                        if time_since_refresh < timedelta(seconds=300):
                            should_refresh_user = False
                    except (ValueError, TypeError):
                        pass
                
                if should_refresh_user:
                    # Expire the user object to force reload from database
                    db.session.expire(current_user)
                    # Refresh to get latest role
                    db.session.refresh(current_user)
                    # Mark when we refreshed
                    flask_session['user_refreshed_at'] = datetime.utcnow().isoformat()
                    
                    # Debug: Log role for admin endpoints
                    if request.path.startswith('/api/admin'):
                        print(f"[SESSION] User {current_user.email} role refreshed: {current_user.role} (type: {type(current_user.role).__name__})")
            except Exception as e:
                # User might have been deleted or session issue, ignore
                print(f"[SESSION] Warning: Could not refresh user: {e}")
                pass
                
        except Exception as e:
            # Don't break the request if activity tracking fails
            print(f"[SESSION] Error tracking activity: {e}")


# Ensure database tables exist before handling requests
# This is critical for serverless environments where tables might not be created on startup
@app.before_request
def ensure_tables_exist():
    """Ensure database tables exist before handling requests"""
    # Skip for static files and health checks
    if request.endpoint in ['static', None] or request.path.startswith('/static'):
        return
    
    try:
        # Check if tables exist using SQLAlchemy inspector
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'user' not in tables:
            print("[DB] User table missing - creating all tables...")
            try:
                db.create_all()
                # Verify tables were created
                inspector = inspect(db.engine)
                new_tables = inspector.get_table_names()
                print(f"[DB] Tables created successfully: {new_tables}")
            except Exception as create_error:
                print(f"[DB] ERROR creating tables: {create_error}")
                import traceback
                traceback.print_exc()
    except Exception as e:
        # Log but don't fail the request - let the route handle it
        print(f"[DB] Warning: Could not ensure tables exist: {e}")
        import traceback
        traceback.print_exc()

# ==================== SAFE HTML RENDERING ====================
def convert_pipe_table_to_html(text):
    """
    Convert pipe-separated text to HTML table.
    
    Example:
    Header 1 | Header 2 | Header 3
    Row 1 Col 1 | Row 1 Col 2 | Row 1 Col 3
    
    Returns HTML table or original text if no pipe table detected.
    """
    if not text or '|' not in text:
        return text
    
    lines = text.strip().split('\n')
    if len(lines) < 2:
        return text
    
    # Check if first line looks like a header (contains |)
    first_line = lines[0].strip()
    if '|' not in first_line:
        return text
    
    # Parse header row
    headers = [cell.strip() for cell in first_line.split('|')]
    if len(headers) < 2:
        return text
    
    # Build table HTML
    table_html = '<table><thead><tr>'
    for header in headers:
        table_html += f'<th>{header}</th>'
    table_html += '</tr></thead><tbody>'
    
    # Parse data rows
    for line in lines[1:]:
        line = line.strip()
        if not line:  # Skip empty lines
            continue
        if '|' not in line:
            continue  # Skip lines without pipes
        
        cells = [cell.strip() for cell in line.split('|')]
        # Pad or trim to match header count
        while len(cells) < len(headers):
            cells.append('')
        cells = cells[:len(headers)]
        
        table_html += '<tr>'
        for cell in cells:
            table_html += f'<td>{cell}</td>'
        table_html += '</tr>'
    
    table_html += '</tbody></table>'
    return table_html

def preserve_text_structure(text):
    """
    Preserve line breaks, bullets, and indentation in plain text.
    Converts plain text formatting to HTML before sanitization.
    
    Handles:
    - Newlines (\n) → <br>
    - Double newlines (\n\n) → paragraph breaks
    - Bullet points (•, -, *) → HTML list items
    - Indentation → preserved with &nbsp; or <br>
    """
    if not text:
        return ''
    
    # Check if text already contains HTML tags
    if '<' in text and '>' in text:
        import re
        # Check for complex HTML structures (tables, divs, etc.) that should be preserved as-is
        has_complex_html = (
            re.search(r'<table[^>]*>', text, re.IGNORECASE) or 
            re.search(r'<thead[^>]*>', text, re.IGNORECASE) or
            re.search(r'<tbody[^>]*>', text, re.IGNORECASE) or
            re.search(r'<div[^>]*>', text, re.IGNORECASE) or
            re.search(r'<span[^>]*>', text, re.IGNORECASE)
        )
        
        # Check if content already has structure tags (p, ul, li, br) - means it's already formatted
        has_structure_tags = (
            re.search(r'<p[^>]*>', text, re.IGNORECASE) or
            re.search(r'<ul[^>]*>', text, re.IGNORECASE) or
            re.search(r'<ol[^>]*>', text, re.IGNORECASE) or
            re.search(r'<li[^>]*>', text, re.IGNORECASE) or
            re.search(r'<br\s*/?>', text, re.IGNORECASE)
        )
        
        # If it has complex HTML (tables) OR already has structure tags, return as-is
        # This preserves HTML tables and already-formatted content from TinyMCE
        if has_complex_html or has_structure_tags:
            return text
        
        # Has simple HTML tags (like <b>, <i>, <mark>) but no structure - process to add structure
        # Convert <p> tags to newlines (preserve content)
        text = re.sub(r'<p[^>]*>', '\n', text)
        text = re.sub(r'</p>', '\n', text)
        # Convert <br> and <br/> to newlines
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        # Convert <li> items to bullet format for processing
        text = re.sub(r'<li[^>]*>', '• ', text)
        text = re.sub(r'</li>', '\n', text)
        # Remove other HTML tags but preserve their text content
        # Formatting tags (mark, hr, b, i, u, strong, em) will be preserved by bleach sanitizer
        text = re.sub(r'<[^>]+>', '', text)
        # Decode HTML entities
        import html
        text = html.unescape(text)
        # Now process as plain text (fall through to plain text processing below)
    
    # Plain text processing
    # First, normalize tabs to spaces (4 spaces per tab)
    text = text.replace('\t', '    ')
    lines = text.split('\n')
    processed_lines = []
    in_list = False
    
    for i, line in enumerate(lines):
        # Calculate indentation (spaces at start)
        original_indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        
        if not stripped:
            # Empty line - close list if open, then add break
            if in_list:
                processed_lines.append('</ul>')
                in_list = False
            processed_lines.append('<br>')
            continue
        
        # Detect bullet points (•, -, *, or numbered ONLY if indented or part of a list)
        is_bullet = False
        bullet_text = stripped
        
        # Check for bullet characters (•, *, -)
        if stripped.startswith('•') or stripped.startswith('*') or (stripped.startswith('-') and len(stripped) > 1 and stripped[1] != '-'):
            is_bullet = True
            bullet_text = stripped[1:].strip()
        # Check for numbered bullets (1., 2., etc.) - ONLY if indented (part of a sub-list)
        # Numbered items at start of line (no indent) are section headers, not bullets
        elif original_indent > 0 and len(stripped) > 2:
            # Check if it's a numbered list item (digit followed by . or ) and space)
            if stripped[0].isdigit():
                # Check for pattern like "1. " or "1) "
                match_pos = -1
                if len(stripped) > 2 and stripped[1] in ['.', ')']:
                    if len(stripped) > 3 and stripped[2] == ' ':
                        # Pattern: "1. text" or "1) text"
                        is_bullet = True
                        bullet_text = stripped[3:].strip()
                    elif len(stripped) == 3:
                        # Pattern: "1. " (just number and punctuation)
                        is_bullet = True
                        bullet_text = ''
        
        # Handle bullet points - collect into lists
        if is_bullet:
            if not in_list:
                processed_lines.append('<ul>')
                in_list = True
            # Add list item with preserved indentation
            # For nested bullets, preserve some indentation
            indent_spaces = ''
            if original_indent > 0:
                # Convert indent to non-breaking spaces (approximate: 2 spaces = 1 &nbsp;)
                indent_count = min(original_indent // 2, 10)
                indent_spaces = '&nbsp;' * indent_count
            processed_lines.append(f'<li>{indent_spaces}{bullet_text}</li>')
        else:
            # Not a bullet point
            if in_list:
                processed_lines.append('</ul>')
                in_list = False
            
            # Regular text line - always create a new paragraph (don't merge)
            # Preserve indentation if present
            indent_spaces = ''
            if original_indent > 0:
                indent_count = min(original_indent, 20)
                indent_spaces = '&nbsp;' * indent_count
            
            processed_lines.append(f'<p>{indent_spaces}{stripped}</p>')
    
    # Close any open list
    if in_list:
        processed_lines.append('</ul>')
    
    result = ''.join(processed_lines)
    
    # Clean up: convert double breaks to paragraph breaks
    result = result.replace('</p><br><p>', '</p><p>')
    result = result.replace('<br><br>', '</p><p>')
    
    return result

def sanitize_html_for_saving(html_content):
    """
    Sanitize HTML content for safe saving to database.
    Handles both HTML from TinyMCE and plain text.
    
    For HTML content: Sanitizes safely while preserving structure
    For plain text: Saves as-is (no conversion to HTML) - formatting preserved via CSS
    
    This is used when SAVING content (from TinyMCE editor or form inputs).
    """
    if not html_content:
        return ''
    
    import bleach
    import re
    
    # Step 1: Convert pipe tables to HTML (if any)
    html_content = convert_pipe_table_to_html(html_content)
    
    # Step 2: Check if content is already HTML (from TinyMCE) or plain text
    # First, decode any HTML entities that might have been escaped
    import html as html_module
    # If content looks like it might be escaped HTML (has &lt; or &gt;), decode it
    if '&lt;' in html_content or '&gt;' in html_content:
        # Try to decode HTML entities
        html_content = html_module.unescape(html_content)
    
    has_html_tags = '<' in html_content and '>' in html_content
    
    if has_html_tags:
        # Content is HTML (from TinyMCE) - sanitize it safely
        # Convert ALLOWED_TAGS to list if it's a frozenset (newer bleach versions)
        base_tags = list(bleach.sanitizer.ALLOWED_TAGS) if isinstance(bleach.sanitizer.ALLOWED_TAGS, frozenset) else bleach.sanitizer.ALLOWED_TAGS
        
        # Allowed tags for rich text formatting (unified across all fields)
        allowed_tags = base_tags + [
            'p', 'br', 'hr',  # Paragraphs, line breaks, horizontal rules
            'b', 'strong', 'i', 'em', 'u', 'mark',  # Text formatting
            'ul', 'ol', 'li',  # Lists
            'sup', 'sub',  # Superscript/subscript
            'blockquote',  # Quotes
            'h1', 'h2', 'h3', 'h4',  # Headings
            'table', 'thead', 'tbody', 'tr', 'th', 'td',  # Tables
            'span', 'div',  # Containers
            'img', 'a'  # Media and links
        ]
        
        # Allowed attributes
        allowed_attributes = {
            '*': ['class'],  # All elements can have class
            'img': ['src', 'alt', 'title', 'width', 'height'],
            'a': ['href', 'title', 'target'],
            'table': ['border', 'cellpadding', 'cellspacing', 'style', 'width', 'class'],
            'thead': ['style', 'class'],
            'tbody': ['style', 'class'],
            'tr': ['style', 'class'],
            'th': ['colspan', 'rowspan', 'style', 'class'],
            'td': ['colspan', 'rowspan', 'style', 'class']
        }
        
        # Allowed URL protocols
        allowed_protocols = ['http', 'https', 'data']
        
        # Sanitize HTML
        cleaned = bleach.clean(
            html_content,
            tags=allowed_tags,
            attributes=allowed_attributes,
            protocols=allowed_protocols,
            strip=True
        )
        
        return cleaned
    else:
        # Plain text - save as-is (no conversion to HTML)
        # Formatting (line breaks, bullets, indentation) will be preserved via CSS
        # Just escape any potential XSS characters
        import html
        # Escape HTML entities to prevent XSS, but keep the text structure intact
        return html.escape(html_content)


def sanitize_html_for_display(html_content):
    """
    Sanitize HTML content for safe display.
    Content is already saved in database with structure preserved.
    This just ensures it's safe to render (prevents XSS).
    
    This is used when DISPLAYING content (from database).
    """
    if not html_content:
        return ''
    
    import bleach
    
    # Convert ALLOWED_TAGS to list if it's a frozenset (newer bleach versions)
    base_tags = list(bleach.sanitizer.ALLOWED_TAGS) if isinstance(bleach.sanitizer.ALLOWED_TAGS, frozenset) else bleach.sanitizer.ALLOWED_TAGS
    
    # Allowed tags for rich text formatting (unified across all fields)
    allowed_tags = base_tags + [
        'p', 'br', 'hr',  # Paragraphs, line breaks, horizontal rules
        'b', 'strong', 'i', 'em', 'u', 'mark',  # Text formatting
        'ul', 'ol', 'li',  # Lists
        'sup', 'sub',  # Superscript/subscript
        'blockquote',  # Quotes
        'h1', 'h2', 'h3', 'h4',  # Headings
        'table', 'thead', 'tbody', 'tr', 'th', 'td',  # Tables
        'span', 'div',  # Containers
        'img', 'a'  # Media and links
    ]
    
    # Allowed attributes
    allowed_attributes = {
        '*': ['class'],  # All elements can have class
        'img': ['src', 'alt', 'title', 'width', 'height'],
        'a': ['href', 'title', 'target'],
        'td': ['colspan', 'rowspan'],
        'th': ['colspan', 'rowspan']
    }
    
    # Allowed URL protocols
    allowed_protocols = ['http', 'https', 'data']
    
    # Sanitize HTML (content is already formatted, just ensure safety)
    cleaned = bleach.clean(
        html_content,
        tags=allowed_tags,
        attributes=allowed_attributes,
        protocols=allowed_protocols,
        strip=True
    )
    
    return cleaned

@app.template_filter('safe_html')
def safe_html_filter(html_content):
    """
    Jinja2 filter for safe HTML rendering.
    Usage: {{ case.discussion|safe_html }}
    """
    from markupsafe import Markup
    sanitized = sanitize_html_for_display(html_content)
    return Markup(sanitized)  # Mark as safe so Jinja2 doesn't escape it


# ==================== HELPER FUNCTIONS ====================



# Initialize database tables on startup
# In serverless (Vercel), this runs on cold start
# If tables don't exist, they'll be created on first request via lazy initialization
with app.app_context():
    try:
        # Check if user table exists by trying to query it
        try:
            User.query.limit(1).count()
            print("[DB] Database tables already exist")
        except Exception as query_error:
            # Tables don't exist, create them
            print("[DB] Tables not found, creating database schema...")
            db.create_all()
            print("[DB] Database schema created successfully")
    except Exception as e:
        print(f"[DB] Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        # Don't raise - allow app to start and create tables on first request
        print("[DB] Will attempt to create tables on first database operation")

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(backup_bp)
app.register_blueprint(admin_bp)  # Sprint 2: Admin user management
app.register_blueprint(enrichment_bp)  # Data migration: Import, enrich, promote cases

# Handle favicon requests to prevent 404 errors
@app.route('/favicon.ico', endpoint='favicon_ico')
@app.route('/favicon.png', endpoint='favicon_png')
def favicon():
    """Handle favicon requests - return existing icon or 204 No Content"""
    try:
        # Try to return the existing icon using the static folder path
        icon_path = os.path.join(app.static_folder, 'images', 'icon-192x192.png')
        if os.path.exists(icon_path):
            return send_file(icon_path, mimetype='image/png')
        else:
            # If icon doesn't exist, return 204 No Content (standard for missing favicons)
            return '', 204
    except Exception as e:
        # Log error but return 204 to prevent 404 spam
        print(f"[FAVICON] Error serving favicon: {e}")
        return '', 204

# Handle favicon requests to prevent 404 errors
@app.route('/favicon.ico')
@app.route('/favicon.png')
def favicon():
    """Handle favicon requests - return existing icon or 204 No Content"""
    try:
        # Try to return the existing icon
        return send_file('static/images/icon-192x192.png', mimetype='image/png')
    except Exception:
        # If icon doesn't exist, return 204 No Content (standard for missing favicons)
        return '', 204


@app.route('/')
def index():
    """Smart dashboard - students see student dashboard, admins can access admin features"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('auth.login'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard for students"""
    from models import CandidateNote, TextHighlight, Case
    
    # Get user statistics
    notes_count = CandidateNote.query.filter_by(user_id=current_user.id).count()
    highlights_count = TextHighlight.query.filter_by(user_id=current_user.id).count()
    
    # Count of cases with notes (reviewed cases)
    reviewed_count = db.session.query(CandidateNote.case_id).filter_by(user_id=current_user.id).distinct().count()
    
    # Total public cases
    case_count = Case.query.filter_by(is_public=True).count()
    
    return render_template('student_dashboard.html',
                         notes_count=notes_count,
                         highlights_count=highlights_count,
                         reviewed_count=reviewed_count,
                         case_count=case_count)


# ==================== STUDENT REVISION: BALANCED REVISION ====================
# This section implements the balanced revision feature for students
# CRITICAL: Does NOT interfere with examiner workflows

@app.route('/revision/start-balanced')
@login_required
def start_balanced_revision():
    """
    Start a new balanced revision session.
    Selects cases from each FRCR module (at least 1 per module required).
    Prioritizes cases the user hasn't seen or has seen least recently.
    Ensures new cases are selected each time when multiple cases are available.
    """
    from models import FRCRModule, Case, RevisionSession, RevisionHistory
    import json
    from sqlalchemy import func
    
    print(f"[REVISION] User {current_user.id} starting balanced revision session")
    
    try:
        # Get all FRCR modules
        all_modules = list(FRCRModule)
        
        # STEP 1: Check if at least one case is available in EACH module
        module_case_counts = {}
        modules_without_cases = []
        
        for module in all_modules:
            case_count = Case.query.filter_by(
                module=module,
                is_public=True
            ).count()
            module_case_counts[module] = case_count
            
            if case_count == 0:
                modules_without_cases.append(module.value)
            
            print(f"[REVISION] Module {module.value}: {case_count} cases available")
        
        # If any module has 0 cases, show error and return
        if modules_without_cases:
            module_list = ", ".join(modules_without_cases)
            flash(f'Cannot start balanced revision: No cases available in {len(modules_without_cases)} module(s): {module_list}. Please try again later as we are addung new cases continuiously.', 'warning')
            return redirect(url_for('dashboard'))
        
        # STEP 2: Get cases from recent sessions to exclude (ensure new cases each time)
        # Get case IDs from user's recent sessions (last 5 sessions)
        recent_sessions = RevisionSession.query.filter_by(
            user_id=current_user.id
        ).order_by(RevisionSession.created_at.desc()).limit(5).all()
        
        recently_used_case_ids = set()
        for session in recent_sessions:
            recently_used_case_ids.update(session.get_case_ids_list())
        
        print(f"[REVISION] Excluding {len(recently_used_case_ids)} cases from recent sessions")
        
        # STEP 3: Select cases from each module
        selected_case_ids = []
        module_selection_info = []  # Track info for user feedback
        
        for module in all_modules:
            print(f"[REVISION] Selecting cases for module: {module.value}")
            
            # Subquery: Get last_seen_at for each case for this user
            seen_subquery = db.session.query(
                RevisionHistory.case_id,
                func.max(RevisionHistory.last_seen_at).label('last_seen')
            ).filter(
                RevisionHistory.user_id == current_user.id
            ).group_by(RevisionHistory.case_id).subquery()
            
            # Main query: Get public cases for this module
            # Exclude recently used cases to ensure variety
            # Priority: unseen > least recently seen > random
            query = db.session.query(Case).filter(
                Case.is_public == True,
                Case.module == module
            )
            
            # Exclude recently used cases if there are enough alternatives
            total_available = Case.query.filter_by(
                module=module,
                is_public=True
            ).count()
            
            # Only exclude recent cases if we have more than 1 case available
            if total_available > 1 and recently_used_case_ids:
                query = query.filter(~Case.id.in_(recently_used_case_ids))
            
            # Order by: NULL last_seen first (unseen), then oldest last_seen, then random
            cases = query.outerjoin(
                seen_subquery,
                Case.id == seen_subquery.c.case_id
            ).order_by(
                seen_subquery.c.last_seen.asc().nullsfirst(),  # Unseen first
                func.random()  # Then random among same category
            ).limit(6).all()
            
            case_ids_for_module = [c.id for c in cases]
            selected_case_ids.extend(case_ids_for_module)
            
            # Calculate remaining cases for this module
            remaining_in_module = total_available - len(case_ids_for_module)
            
            module_selection_info.append({
                'module': module.value,
                'selected': len(case_ids_for_module),
                'remaining': remaining_in_module,
                'total': total_available
            })
            
            print(f"[REVISION] Selected {len(case_ids_for_module)} cases from {module.value}: {case_ids_for_module}")
            print(f"[REVISION] Remaining cases in {module.value}: {remaining_in_module} out of {total_available} total")
        
        # STEP 4: Create session and provide feedback
        if len(selected_case_ids) == 0:
            flash('No cases available for revision.', 'warning')
            return redirect(url_for('dashboard'))
        
        # Create new revision session
        revision_session = RevisionSession(
            user_id=current_user.id,
            case_ids='[]',  # Will be set below
            current_case_index=0
        )
        revision_session.set_case_ids_list(selected_case_ids)
        
        db.session.add(revision_session)
        db.session.commit()
        
        print(f"[REVISION] Created session {revision_session.id} with {len(selected_case_ids)} cases")
        
        # STEP 5: Create informative success message with remaining cases info
        total_remaining = sum(info['remaining'] for info in module_selection_info)
        total_available_all = sum(info['total'] for info in module_selection_info)
        
        # Build detailed message
        message_parts = [
            f'Started balanced revision with {len(selected_case_ids)} cases!',
            f'Remaining cases for future revisions: {total_remaining} out of {total_available_all} total cases.'
        ]
        
        flash(' '.join(message_parts), 'success')
        
        # Redirect to first case
        return redirect(url_for("view_revision_case", session_id=revision_session.id, case_index=0))
    
    except Exception as e:
        db.session.rollback()
        print(f"[REVISION] Error starting session: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Error starting revision session: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))


@app.route('/revision/session/<int:session_id>/case/<int:case_index>')
@login_required
def view_revision_case(session_id, case_index):
    """
    View a case within a revision session.
    Tracks case viewing in revision history.
    """
    from models import RevisionSession, RevisionHistory, Case, FRCRModule
    
    # Get the revision session
    revision_session = RevisionSession.query.filter_by(
        id=session_id,
        user_id=current_user.id  # Security: ensure user owns this session
    ).first()
    
    if not revision_session:
        flash('Revision session not found or access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Get case IDs from session
    case_ids = revision_session.get_case_ids_list()
    
    # Validate case_index
    if case_index < 0 or case_index >= len(case_ids):
        flash('Invalid case index.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Get the case
    case_id = case_ids[case_index]
    case = Case.query.get(case_id)
    
    if not case:
        flash('Case not found.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Update revision session progress
    revision_session.current_case_index = case_index
    
    # Track in revision history (create or update)
    history = RevisionHistory.query.filter_by(
        user_id=current_user.id,
        case_id=case_id
    ).first()
    
    if history:
        # Update existing history
        history.last_seen_at = datetime.utcnow()
        history.times_seen += 1
    else:
        # Create new history entry
        history = RevisionHistory(
            user_id=current_user.id,
            case_id=case_id,
            module=case.module,
            revision_session_id=session_id,
            times_seen=1
        )
        db.session.add(history)
    
    db.session.commit()
    
    print(f"[REVISION] User {current_user.id} viewing case {case_id} (index {case_index}/{len(case_ids)-1}) in session {session_id}")
    
    # Calculate navigation info
    has_previous = case_index > 0
    has_next = case_index < len(case_ids) - 1
    progress_percent = int((case_index + 1) / len(case_ids) * 100)
    
    # Prepare navigation URLs
    previous_url = url_for('view_revision_case', session_id=session_id, case_index=case_index-1) if has_previous else None
    next_url = url_for('view_revision_case', session_id=session_id, case_index=case_index+1) if has_next else None
    
    # Reuse existing view_case template with additional context
    return render_template('view_case.html',
                         case=case,
                         # Revision session context
                         revision_mode=True,
                         revision_session_id=session_id,
                         case_index=case_index,
                         total_cases=len(case_ids),
                         progress_percent=progress_percent,
                         has_previous=has_previous,
                         has_next=has_next,
                         previous_url=previous_url,
                         next_url=next_url)


@app.route('/modules')
@login_required
def modules_view():
    """Display all FRCR modules"""
    from models import FRCRModule, Case
    
    # Prepare module data with case counts
    modules_data = []
    module_icons = {
        'CARDIOTHORACIC_VASCULAR': 'fas fa-heart',
        'MUSCULOSKELETAL_TRAUMA': 'fas fa-bone',
        'GASTROINTESTINAL': 'fas fa-stomach',
        'GENITOURINARY_BREAST': 'fas fa-venus',
        'PAEDIATRIC': 'fas fa-baby',
        'CNS_HEAD_NECK': 'fas fa-brain'
    }
    
    module_descriptions = {
        'CARDIOTHORACIC_VASCULAR': 'Heart, lungs, chest, and vascular imaging',
        'MUSCULOSKELETAL_TRAUMA': 'Bones, joints, and trauma imaging',
        'GASTROINTESTINAL': 'Abdominal organs, liver, biliary, pancreas',
        'GENITOURINARY_BREAST': 'Urinary, reproductive, and breast imaging',
        'PAEDIATRIC': 'Neonatal and paediatric cases',
        'CNS_HEAD_NECK': 'Brain, spine, and head & neck imaging'
    }
    
    for module in FRCRModule:
        case_count = Case.query.filter_by(module=module, is_public=True).count()
        modules_data.append({
            'value': module.name,
            'display_name': module.value,
            'icon': module_icons.get(module.name, 'fas fa-folder'),
            'description': module_descriptions.get(module.name, ''),
            'case_count': case_count
        })
    
    return render_template('modules_view.html', modules=modules_data)


@app.route('/modules/<module>')
@login_required
def cases_by_module(module):
    """Show cases filtered by module - different templates for students vs admins"""
    from models import FRCRModule, BodyPart, AgeGroup, Case, CandidateNote, CaseFlag
    
    # Validate module
    try:
        module_enum = FRCRModule[module]
    except KeyError:
        return redirect(url_for('modules_view'))
    
    # Get filters from query params
    body_part_filter = request.args.get('body_part', '')
    age_group_filter = request.args.get('age_group', '')
    search_query = request.args.get('q', '')
    
    # Check if user is a student - use student template
    is_student = (hasattr(current_user, 'role') and current_user.role == UserRole.STUDENT)
    
    if is_student:
        # Students: only public cases, use student template
        query = Case.query.filter_by(module=module_enum, is_public=True)
    else:
        # Admins/Content Managers: all cases
        query = Case.query.filter_by(module=module_enum)
    
    if body_part_filter:
        try:
            body_part_enum = BodyPart[body_part_filter]
            query = query.filter_by(body_part=body_part_enum)
        except KeyError:
            pass
    
    if age_group_filter:
        try:
            age_group_enum = AgeGroup[age_group_filter]
            query = query.filter_by(age_group=age_group_enum)
        except KeyError:
            pass
    
    if search_query:
        query = query.filter(Case.diagnosis.ilike(f'%{search_query}%'))
    
    cases = query.order_by(Case.id).all()
    
    # Prepare case data
    cases_data = []
    if is_student:
        # Get all flagged case IDs for this user
        flagged_case_ids = set(
            flag.case_id for flag in CaseFlag.query.filter_by(user_id=current_user.id).all()
        )
        
        # Prepare case data for student template - match admin template structure
    for case in cases:
            cases_data.append({
                'id': case.id,
                'diagnosis': case.diagnosis,
                'module_display': case.module.value if case.module else 'N/A',
                'body_part_display': case.body_part.value if case.body_part else 'N/A',
                'age_group_display': case.age_group.value if case.age_group else 'N/A',
                'image_count': len(case.images),
                'date': case.created_at.strftime('%Y-%m-%d') if case.created_at else 'N/A',
                'flagged': case.id in flagged_case_ids,
                'is_public': True
            })
    else:
        # Admins/Content Managers: prepare case data for admin template
        for case in cases:
            has_notes = CandidateNote.query.filter_by(case_id=case.id, user_id=current_user.id).first() is not None
            cases_data.append({
                'id': case.id,
                'diagnosis': case.diagnosis,
                'module_display': case.module.value if case.module else 'N/A',
                'body_part_display': case.body_part.value if case.body_part else 'N/A',
                'age_group_display': case.age_group.value if case.age_group else 'N/A',
                'image_count': len(case.images),
                'has_notes': has_notes,
                'is_public': case.is_public
            })
    
    # Get all body parts and age groups for filters
    body_parts = [{'value': bp.name, 'display_name': bp.value} for bp in BodyPart]
    age_groups = [{'value': ag.name, 'display_name': ag.value} for ag in AgeGroup]
    all_modules = [{'value': m.name, 'display_name': m.value} for m in FRCRModule]
    
    if is_student:
        return render_template('student_cases_list.html',
                             cases=cases_data,
                             module_filter=module_enum.value,
                             body_parts=body_parts,
                             body_part_selected=body_part_filter,
                             age_groups=age_groups,
                             age_group_selected=age_group_filter,
                             all_modules=all_modules,
                             search_query=search_query)
    else:
        return render_template('cases_list.html',
                         cases=cases_data,
                         module_filter=module_enum.value,
                         body_parts=body_parts,
                         body_part_selected=body_part_filter,
                             age_groups=age_groups,
                             age_group_selected=age_group_filter,
                             all_modules=all_modules,
                         search_query=search_query)


@app.route('/cases')
@login_required
def all_cases_view():
    """Case list view - different templates for students vs admins"""
    from models import FRCRModule, BodyPart, AgeGroup, Case, CandidateNote
    
    # For students: redirect to student route
    is_student = (hasattr(current_user, 'role') and current_user.role == UserRole.STUDENT)
    if is_student:
        return redirect(url_for('student_cases_list'))
    
    # For admins: show full case management with all cases
    # Get filters from query params
    module_filter = request.args.get('module', '')
    body_part_filter = request.args.get('body_part', '')
    age_group_filter = request.args.get('age_group', '')
    search_query = request.args.get('q', '')
    
    # Build query - admins see ALL cases (public and private)
    query = Case.query
    
    if module_filter:
        try:
            module_enum = FRCRModule[module_filter]
            query = query.filter_by(module=module_enum)
        except KeyError:
            pass
    
    if body_part_filter:
        try:
            body_part_enum = BodyPart[body_part_filter]
            query = query.filter_by(body_part=body_part_enum)
        except KeyError:
            pass
    
    if age_group_filter:
        try:
            age_group_enum = AgeGroup[age_group_filter]
            query = query.filter_by(age_group=age_group_enum)
        except KeyError:
            pass
    
    if search_query:
        query = query.filter(Case.diagnosis.ilike(f'%{search_query}%'))
    
    cases = query.order_by(Case.id).all()
    
    # Prepare case data for admin template
    cases_data = []
    for case in cases:
        # Check if user has notes (for admin's reference)
        has_notes = CandidateNote.query.filter_by(case_id=case.id, user_id=current_user.id).first() is not None
        
        cases_data.append({
            'id': case.id,
            'diagnosis': case.diagnosis,
            'module_display': case.module.value if case.module else 'N/A',
            'body_part_display': case.body_part.value if case.body_part else 'N/A',
            'age_group_display': case.age_group.value if case.age_group else 'N/A',
            'image_count': len(case.images),
            'has_notes': has_notes,
            'is_public': case.is_public
        })
    
    # Get all modules, body parts, and age groups for filters
    all_modules = [{'value': m.name, 'display_name': m.value} for m in FRCRModule]
    body_parts = [{'value': bp.name, 'display_name': bp.value} for bp in BodyPart]
    age_groups = [{'value': ag.name, 'display_name': ag.value} for ag in AgeGroup]
    
    # Get count of pending staging cases for badge
    from models import ImportedCaseStaging
    pending_staging_count = ImportedCaseStaging.query.filter_by(enrichment_status='pending').count()
    
    return render_template('cases_list.html',
                         cases=cases_data,
                         module_filter=None,  # No module filter at top level
                         body_parts=body_parts,
                         body_part_selected=body_part_filter,
                         module_selected=module_filter,
                         all_modules=all_modules,
                         age_groups=age_groups,
                         age_group_selected=age_group_filter,
                         search_query=search_query,
                         pending_staging_count=pending_staging_count)


@app.route('/student/cases')
@login_required
def student_cases_list():
    """Student case list - shows only public cases, no admin controls"""
    from models import FRCRModule, BodyPart, AgeGroup, Case, CaseFlag
    
    # Ensure only students can access this route
    is_student = (hasattr(current_user, 'role') and current_user.role == UserRole.STUDENT)
    if not is_student:
        return redirect(url_for('all_cases_view'))
    
    # Get filters from query params
    module_filter = request.args.get('module', '')
    body_part_filter = request.args.get('body_part', '')
    age_group_filter = request.args.get('age_group', '')
    flagged_only = request.args.get('flagged', '').lower() == 'true'
    search_query = request.args.get('q', '')
    
    # Build query - students see ONLY public cases
    query = Case.query.filter_by(is_public=True)
    
    if module_filter:
        try:
            module_enum = FRCRModule[module_filter]
            query = query.filter_by(module=module_enum)
        except KeyError:
            pass
    
    if body_part_filter:
        try:
            body_part_enum = BodyPart[body_part_filter]
            query = query.filter_by(body_part=body_part_enum)
        except KeyError:
            pass
    
    if age_group_filter:
        try:
            age_group_enum = AgeGroup[age_group_filter]
            query = query.filter_by(age_group=age_group_enum)
        except KeyError:
            pass
    
    if search_query:
        query = query.filter(Case.diagnosis.ilike(f'%{search_query}%'))
    
    # Get all flagged case IDs for this user
    flagged_case_ids = set(
        flag.case_id for flag in CaseFlag.query.filter_by(user_id=current_user.id).all()
    )
    
    # Filter to only flagged cases if requested
    if flagged_only:
        if flagged_case_ids:
            query = query.filter(Case.id.in_(flagged_case_ids))
            cases = query.order_by(Case.id).all()
        else:
            # No flagged cases, return empty result
            cases = []
    else:
        cases = query.order_by(Case.id).all()
    
    # Prepare case data for student template - match admin template structure
    cases_data = []
    for case in cases:
        cases_data.append({
            'id': case.id,
            'diagnosis': case.diagnosis,
            'module_display': case.module.value if case.module else 'N/A',
            'body_part_display': case.body_part.value if case.body_part else 'N/A',
            'age_group_display': case.age_group.value if case.age_group else 'N/A',
            'image_count': len(case.images),
            'date': case.created_at.strftime('%Y-%m-%d') if case.created_at else 'N/A',
            'flagged': case.id in flagged_case_ids,
            'is_public': True  # Students only see public cases
        })
    
    # Get all modules, body parts, and age groups for filters
    all_modules = [{'value': m.name, 'display_name': m.value} for m in FRCRModule]
    body_parts = [{'value': bp.name, 'display_name': bp.value} for bp in BodyPart]
    age_groups = [{'value': ag.name, 'display_name': ag.value} for ag in AgeGroup]
    
    return render_template('student_cases_list.html',
                         cases=cases_data,
                         body_parts=body_parts,
                         body_part_selected=body_part_filter,
                         module_selected=module_filter,
                         all_modules=all_modules,
                         age_groups=age_groups,
                         age_group_selected=age_group_filter,
                         flagged_filter=flagged_only,
                         search_query=search_query)


@app.route('/student/cases/<int:case_id>/flag', methods=['POST'])
@login_required
def flag_case(case_id):
    """Flag a case for the current student - STUDENTS ONLY"""
    from models import Case, CaseFlag
    
    # Only students can flag cases
    is_student = (hasattr(current_user, 'role') and current_user.role == UserRole.STUDENT)
    if not is_student:
        return jsonify({'success': False, 'error': 'Access denied. Flagging is for students only.'}), 403
    
    # Verify case exists and is public
    case = Case.query.get(case_id)
    if not case:
        return jsonify({'success': False, 'error': 'Case not found'}), 404
    
    if not case.is_public:
        return jsonify({'success': False, 'error': 'Cannot flag private cases'}), 403
    
    # Check if already flagged
    existing_flag = CaseFlag.query.filter_by(
        user_id=current_user.id,
        case_id=case_id
    ).first()
    
    if existing_flag:
        return jsonify({'success': True, 'message': 'Case already flagged'}), 200
    
    # Create flag
    flag = CaseFlag(
        user_id=current_user.id,
        case_id=case_id
    )
    db.session.add(flag)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Case flagged'}), 200


@app.route('/student/cases/<int:case_id>/unflag', methods=['POST'])
@login_required
def unflag_case(case_id):
    """Unflag a case for the current student - STUDENTS ONLY"""
    from models import CaseFlag
    
    # Only students can unflag cases
    is_student = (hasattr(current_user, 'role') and current_user.role == UserRole.STUDENT)
    if not is_student:
        return jsonify({'success': False, 'error': 'Access denied. Flagging is for students only.'}), 403
    
    # Find and delete flag
    flag = CaseFlag.query.filter_by(
        user_id=current_user.id,
        case_id=case_id
    ).first()
    
    if not flag:
        return jsonify({'success': True, 'message': 'Case not flagged'}), 200
    
    db.session.delete(flag)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Case unflagged'}), 200


@app.route('/profile')
@login_required
def student_profile():
    """Student profile page"""
    return render_template('profile.html')


@app.route('/admin')
@login_required
def admin_dashboard():
    """Admin dashboard - only accessible to admins"""
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    return render_template('admin_dashboard.html')


@app.route('/case-list')
@login_required
def case_list():
    """Case management page - list, create, edit, delete cases - ADMIN ONLY"""
    # Check if user is admin or content manager
    is_admin_or_cm = (hasattr(current_user, 'role') and 
                      current_user.role in [UserRole.ADMIN, UserRole.CONTENT_MANAGER])
    
    if not is_admin_or_cm:
        # Students should be redirected to student case list
        if hasattr(current_user, 'role') and current_user.role == UserRole.STUDENT:
            return redirect(url_for('student_cases_list'))
        return redirect(url_for('dashboard'))
    
    # Redirect to /cases which has the proper admin case list
    return redirect(url_for('all_cases_view'))


# ==================== SETUP WORKFLOW (ADMIN ONLY) ====================

# REMOVED: Session management not needed for student revision app
# @app.route('/setup/sessions')
# @login_required
# def setup_sessions():
#     """Manage exam sessions - ADMIN ONLY (Legacy from examiner app)"""
#     if not current_user.is_admin:
#         return redirect(url_for('dashboard'))
#     return render_template('setup_sessions.html')


# REMOVED: Case management now handled in admin dashboard
# @app.route('/setup/cases')
# @login_required
# def setup_cases():
#     """Case bank management - ADMIN ONLY"""
#     if not current_user.is_admin:
#         return redirect(url_for('dashboard'))
#     return render_template('setup_cases.html')


# REMOVED: Not needed for student app
# @app.route('/setup/candidates')
# @login_required
# def setup_candidates():
#     """Candidate management"""
#     return render_template('setup_candidates.html')


# ==================== EXAM WORKFLOW (REMOVED FOR STUDENT APP) ====================

# REMOVED: Exam session/candidate/packet management not needed
# @app.route('/exam/start')
# @login_required
# def exam_start():
#     """Start exam - select candidate"""
#     return render_template('exam_start.html')

# @app.route('/prepare-exam')
# @login_required
# def prepare_exam():
#     """Deprecated - redirects to new setup"""
#     return redirect(url_for('setup_sessions'))

# @app.route('/api/exam/sessions')
# @login_required
# def get_exam_sessions():
#     """Get all exam sessions"""
#     sessions = ExamSession.query.filter_by(user_id=current_user.id).order_by(ExamSession.created_at.desc()).all()
#     return jsonify([{
#         'id': s.id,
#         'session_name': s.session_name,
#         'exam_date': s.exam_date.strftime('%Y-%m-%d'),
#         'exam_time': s.exam_time,
#         'created_at': s.created_at.strftime('%Y-%m-%d %H:%M:%S')
#     } for s in sessions])

# @app.route('/api/exam/create', methods=['POST'])
# @login_required
# def create_exam():
#     """Create a new exam session"""
#     data = request.get_json()
#     
#     exam_date = datetime.strptime(data['exam_date'], '%Y-%m-%d').date()
#     exam_time = data['exam_time']
#     
#     # Format session name: "05 Jan 2026 1:30 PM Exam Session"
#     date_str = exam_date.strftime('%d %b %Y')
#     
#     # Convert 24-hour time to 12-hour format with AM/PM
#     time_obj = datetime.strptime(exam_time, '%H:%M').time()
#     time_str = time_obj.strftime('%I:%M %p')
#     
#     session_name = f"{date_str} {time_str} Exam Session"
#     
#     exam = ExamSession(
#         user_id=current_user.id,
#         exam_date=exam_date,
#         exam_time=exam_time,
#         session_name=session_name
#     )
#     db.session.add(exam)
#     db.session.commit()
#     
#     return jsonify({
#         'exam_id': exam.id,
#         'session_name': session_name,
#         'message': f'Exam session "{session_name}" created'
#     })

# @app.route('/api/packet/create', methods=['POST'])
# @login_required
# def create_packet():
#     """Create a new packet"""
#     data = request.get_json()
#     
#     packet = Packet(
#         exam_id=data['exam_id'],
#         packet_number=data['packet_number'],
#         packet_id=data['packet_id']
#     )
#     db.session.add(packet)
#     db.session.commit()
#     
#     return jsonify({'packet_id': packet.id, 'message': 'Packet created'})


@app.route('/api/case/next-number', methods=['GET'])
@login_required
def get_next_case_number():
    """Get the next auto-generated case number for a body part"""
    from models import BodyPart
    import re
    
    body_part = request.args.get('body_part', '')
    
    if not body_part:
        return jsonify({'success': False, 'error': 'Body part is required'}), 400
    
    try:
        # Validate body part
        body_part_enum = BodyPart[body_part]
        
        # Create a short code from the body part name (e.g., LUNG_MEDIASTINUM -> LUNGMED)
        # Use first part of name, max 6 chars for readability
        short_code = body_part.replace('_', '').upper()[:6]
        
        # Find the highest existing case number for this body part pattern
        # Pattern: SHORTCODE-XXX
        prefix = f"{short_code}-"
        
        # Query cases with this body part and extract the highest number
        cases_with_pattern = Case.query.filter(
            Case.body_part == body_part_enum,
            Case.case_number.ilike(f"{prefix}%")
        ).all()
        
        max_num = 0
        for case in cases_with_pattern:
            if case.case_number:
                # Extract number from pattern like "CHEST-001"
                match = re.search(r'-(\d+)$', case.case_number)
                if match:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
        
        # Generate next number
        next_num = max_num + 1
        case_number = f"{prefix}{next_num:03d}"
        
        return jsonify({
            'success': True,
            'case_number': case_number,
            'body_part': body_part_enum.value
        })
        
    except KeyError:
        return jsonify({'success': False, 'error': f'Invalid body part: {body_part}'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/case/create', methods=['POST'])
@login_required
def create_case():
    """Create a new case"""
    import json
    import re
    from models import FRCRModule, BodyPart
    
    data = request.get_json()
    
    # Validate required fields
    if not data.get('diagnosis'):
        return jsonify({'error': 'Diagnosis is required'}), 400
    if not data.get('module'):
        return jsonify({'error': 'Module is required'}), 400
    if not data.get('body_part'):
        return jsonify({'error': 'Body Part is required'}), 400
    
    # Extract questions and answers from pairs
    questions = []
    answers = []
    pairs = []
    
    if 'pairs' in data:
        pairs = data['pairs']
        for pair in pairs:
            if pair.get('question_text'):
                questions.append({'question_text': pair['question_text']})
            if pair.get('answer_text'):
                answers.append({'answer_text': pair['answer_text']})
    
    # If questions/answers are provided directly (for backwards compatibility)
    if 'questions' in data:
        questions = data['questions']
    if 'answers' in data:
        answers = data['answers']
    
    # Parse module and body_part enums
    module_enum = None
    if data.get('module'):
        try:
            module_enum = FRCRModule[data['module']]
        except KeyError:
            pass
    
    body_part_enum = None
    if data.get('body_part'):
        try:
            body_part_enum = BodyPart[data['body_part']]
        except KeyError:
            pass
    
    # Auto-generate case_number if not provided and body_part is set
    case_number = data.get('case_number')
    if not case_number and body_part_enum:
        # Generate case number: SHORTCODE-XXX
        short_code = data['body_part'].replace('_', '').upper()[:6]
        prefix = f"{short_code}-"
        
        # Find highest existing number for this body part
        cases_with_pattern = Case.query.filter(
            Case.body_part == body_part_enum,
            Case.case_number.ilike(f"{prefix}%")
        ).all()
        
        max_num = 0
        for c in cases_with_pattern:
            if c.case_number:
                match = re.search(r'-(\d+)$', c.case_number)
                if match:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
        
        case_number = f"{prefix}{max_num + 1:03d}"
    
    # Parse status (default to DRAFT)
    from models import CaseStatus, AgeGroup
    status_enum = CaseStatus.DRAFT
    if data.get('status'):
        try:
            status_enum = CaseStatus[data['status']]
        except (KeyError, AttributeError):
            pass
    
    # Parse age_group if provided
    age_group_enum = None
    if data.get('age_group'):
        try:
            age_group_enum = AgeGroup[data['age_group']]
        except (KeyError, AttributeError):
            pass
    
    # Create case - NO LONGER storing Q&A in legacy JSON fields
    # All Q&A data is stored in Question and Answer tables only
    # Note: packet_id was removed from Case model (legacy examiner workflow)
    try:
        case = Case(
            case_number=case_number,
            diagnosis=sanitize_html_for_saving(data.get('diagnosis', '')),
            discussion=sanitize_html_for_saving(data.get('discussion', '')),
            module=module_enum,
            body_part=body_part_enum,
            age_group=age_group_enum,
            status=status_enum,
            is_public=data.get('is_public', False),  # Legacy field, status takes precedence
            created_by_user_id=current_user.id
        )
        db.session.add(case)
        db.session.flush()  # Get the case ID
        
        # Create Question and Answer entries in their respective tables
        if pairs:
            for index, pair in enumerate(pairs, start=1):
                question_text = (pair.get('question_text') or '').strip()
                answer_text = (pair.get('answer_text') or '').strip()
                
                # Create question if it has content
                if question_text:
                    # Sanitize question text for safe saving
                    question = Question(
                        case_id=case.id,
                        question_number=index,
                        question_text=sanitize_html_for_saving(question_text)
                    )
                    db.session.add(question)
                
                # Create answer if it has content
                if answer_text:
                    # Sanitize answer text for safe saving (handles HTML from TinyMCE + plain text)
                    answer = Answer(
                        case_id=case.id,
                        answer_number=index,
                        answer_text=sanitize_html_for_saving(answer_text)
                    )
                    db.session.add(answer)
        
        db.session.commit()
        
        return jsonify({'success': True, 'id': case.id, 'case_id': case.id, 'message': 'Case created'})
    except Exception as e:
        db.session.rollback()
        print(f"[CASE] Error creating case: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to create case: {str(e)}'}), 500


@app.route('/view-case/<int:case_id>')
@login_required
def view_case(case_id):
    """View a specific case"""
    from models import CandidateNote
    case = Case.query.get(case_id)
    if not case:
        return redirect(url_for('dashboard'))
    # Get user's note for this case
    user_note = CandidateNote.query.filter_by(case_id=case_id, user_id=current_user.id).first()
    
    # Check if user came from staging cases
    from_staging = request.args.get('from_staging', 'false').lower() == 'true'
    
    print(f"[DEBUG] case.discussion for case_id={case_id}: {repr(case.discussion)}")
    return render_template('view_case.html', 
                         case=case, 
                         user_note=user_note,
                         from_staging=from_staging)


@app.route('/admin/staging-cases')
@login_required
def review_staging_cases():
    """List staging cases for review and enrichment"""
    from models import ImportedCaseStaging
    from access_control import has_case_edit_permission
    
    if not has_case_edit_permission(None, current_user):
        flash('Admin access required to review staging cases', 'danger')
        return redirect(url_for('dashboard'))
    
    # Get filter parameters
    status_filter = request.args.get('status', 'pending')  # pending, enriched, rejected
    batch_id = request.args.get('batch_id', '')
    
    # Build query
    query = ImportedCaseStaging.query
    
    if status_filter == 'pending':
        query = query.filter(ImportedCaseStaging.enrichment_status == 'pending')
    elif status_filter == 'enriched':
        query = query.filter(ImportedCaseStaging.enrichment_status == 'enriched')
    elif status_filter == 'rejected':
        query = query.filter(ImportedCaseStaging.enrichment_status == 'rejected')
    
    if batch_id:
        query = query.filter(ImportedCaseStaging.import_batch_id == batch_id)
    
    # Order by most recent first
    staging_cases = query.order_by(ImportedCaseStaging.created_at.desc()).all()
    
    # Get counts for all statuses
    pending_count = ImportedCaseStaging.query.filter_by(enrichment_status='pending').count()
    enriched_count = ImportedCaseStaging.query.filter_by(enrichment_status='enriched').count()
    rejected_count = ImportedCaseStaging.query.filter_by(enrichment_status='rejected').count()
    
    # Prepare data for template
    cases_data = []
    for staging in staging_cases:
        missing_fields = []
        if not staging.module:
            missing_fields.append('Module')
        if not staging.body_part:
            missing_fields.append('Body Part')
        if not staging.age_group:
            missing_fields.append('Age Group')
        
        cases_data.append({
            'id': staging.id,
            'case_number': staging.case_number or 'N/A',
            'diagnosis': staging.diagnosis or 'N/A',
            'module': staging.module.value if staging.module else None,
            'body_part': staging.body_part.value if staging.body_part else None,
            'age_group': staging.age_group.value if staging.age_group else None,
            'status': staging.enrichment_status,
            'missing_fields': missing_fields,
            'created_at': staging.created_at.strftime('%Y-%m-%d %H:%M:%S') if staging.created_at else 'N/A',
            'import_batch_id': staging.import_batch_id,
        })
    
    return render_template('staging_cases_list.html',
                         cases=cases_data,
                         status_filter=status_filter,
                         batch_id=batch_id,
                         pending_count=pending_count,
                         enriched_count=enriched_count,
                         rejected_count=rejected_count)


@app.route('/edit-case')
@login_required
def edit_case():
    """Full-page edit interface for a case or staging case"""
    case_id = request.args.get('id', type=int)
    staging_id = request.args.get('staging_id', type=int)
    is_new = request.args.get('new', 'false').lower() == 'true'
    return_to = request.args.get('returnTo', url_for('dashboard'))
    
    # Check permissions for editing cases (admins and content managers only)
    from access_control import has_case_edit_permission
    
    # For new cases, check if user has permission to create
    if is_new:
        if not has_case_edit_permission(None, current_user):
            flash('You do not have permission to create cases', 'danger')
            return redirect(url_for('dashboard'))
    
    # For existing cases, check permissions
    if case_id and not is_new:
        case = Case.query.get(case_id)
        if case and not has_case_edit_permission(case, current_user):
            flash('You do not have permission to edit this case', 'danger')
            return redirect(url_for('view_case', case_id=case_id))
    
    # Handle staging case review
    if staging_id:
        from models import ImportedCaseStaging
        from access_control import has_case_edit_permission
        
        if not has_case_edit_permission(None, current_user):
            flash('Admin access required to review staging cases', 'danger')
            return redirect(url_for('dashboard'))
        
        staging = ImportedCaseStaging.query.get(staging_id)
        if not staging:
            flash('Staging case not found', 'danger')
            return redirect(url_for('dashboard'))
        
        # Check for missing critical fields
        missing_fields = []
        if not staging.module:
            missing_fields.append('module')
        if not staging.body_part:
            missing_fields.append('body_part')
        if not staging.age_group:
            missing_fields.append('age_group')
        
        return render_template('edit_case.html', 
                             is_new=False,
                             is_staging=True,
                             staging=staging,
                             missing_fields=missing_fields,
                             return_to=return_to)
    
    # Handle regular case editing
    if not is_new and not case_id:
        return redirect(url_for('dashboard'))
    case = Case.query.get(case_id) if case_id else None
    if not is_new and not case:
        return redirect(url_for('dashboard'))
    return render_template('edit_case.html', 
                         is_new=is_new,
                         is_staging=False,
                         return_to=return_to,
                         case=case)




# REMOVED: Session management routes (examiner-specific)
# @app.route('/manage-session/<int:session_id>')
# def manage_session(session_id):
#     """Manage exam session - edit packets and candidates"""
#     exam = ExamSession.query.get(session_id)
#     
#     if not exam:
#         return redirect(url_for('index'))
#     
#     session['current_exam_id'] = session_id
#     return render_template('manage_session.html', session=exam)


# @app.route('/api/session/<int:session_id>/packets')
# def get_session_packets(session_id):
#     """Get all packets for a session"""
#     packets = Packet.query.filter_by(exam_id=session_id).all()
#     return jsonify([{
#         'id': p.id,
#         'packet_number': p.packet_number,
#         'packet_id': p.packet_id
#     } for p in packets])


# REMOVED: Packet management routes (examiner-specific)
# @app.route('/api/packet/<int:packet_id>', methods=['DELETE'])
# @login_required
# def delete_packet(packet_id):
#     """Delete a packet and all its cases"""
#     # Verify user ownership
#     obj = verify_packet_ownership(delete_id)
#     if not obj:
#         return jsonify({"error": "Unauthorized"}), 403
#     
#     """Delete a packet and all its cases"""
#     packet = Packet.query.get(packet_id)
#     
#     if not packet:
#         return jsonify({'error': 'Packet not found'}), 404
#     
#     # Delete all cases in this packet
#     Case.query.filter_by(packet_id=packet_id).delete()
#     
#     db.session.delete(packet)
#     db.session.commit()
#     
#     return jsonify({'message': 'Packet deleted successfully'})


# @app.route('/api/packet/<int:packet_id>', methods=['PUT'])
# @login_required
# def update_packet(packet_id):
#     """Update a packet"""
#     # Verify user ownership
#     obj = verify_packet_ownership(delete_id)
#     if not obj:
#         return jsonify({"error": "Unauthorized"}), 403
#     
#     """Update a packet"""
#     packet = Packet.query.get(packet_id)
#     
#     if not packet:
#         return jsonify({'error': 'Packet not found'}), 404
#     
#     data = request.get_json()
#     
#     if 'packet_number' in data:
#         packet.packet_number = data['packet_number']
#     if 'packet_id' in data:
#         packet.packet_id = data['packet_id']
#     
#     db.session.commit()
#     
#     return jsonify({'message': 'Packet updated successfully'})


@app.route('/api/case/<int:case_id>/reject', methods=['POST'])
@login_required
def reject_case(case_id):
    """Reject a case (mark as rejected instead of deleting)"""
    try:
        from models import CaseStatus
        from access_control import has_case_edit_permission
        
        # Check if user has permission
        case = Case.query.get(case_id)
        if not case:
            return jsonify({
                'success': False,
                'error': 'Case not found'
            }), 404
        
        # Check if user has edit permission (admin or content manager)
        if not has_case_edit_permission(case, current_user):
            return jsonify({
                'success': False,
                'error': 'Unauthorized - Admin or Content Manager access required'
            }), 403
        
        # Set status to REJECTED instead of deleting
        case.status = CaseStatus.REJECTED
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Case rejected successfully. It can be recovered later.'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"[REJECT] Error rejecting case {case_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to reject case: {str(e)}'
        }), 500


@app.route('/api/case/<int:case_id>', methods=['DELETE'])
@login_required
def delete_case(case_id):
    """Delete a case"""
    try:
        # Check if user has permission to delete
        case = Case.query.get(case_id)
    if not case:
            return jsonify({
                'success': False,
                'error': 'Case not found'
            }), 404
        
        # Check if user has delete permission (admin or content manager)
        if not has_case_delete_permission(case):
            return jsonify({
                'success': False,
                'error': 'Unauthorized - Admin or Content Manager access required'
            }), 403
        
        # Delete associated questions and answers
        Question.query.filter_by(case_id=case_id).delete()
        Answer.query.filter_by(case_id=case_id).delete()
        
        # Delete associated images
        CaseImage.query.filter_by(case_id=case_id).delete()
        
        # Delete the case
    db.session.delete(case)
    db.session.commit()
    
        return jsonify({
            'success': True,
            'message': 'Case deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"[DELETE] Error deleting case {case_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to delete case: {str(e)}'
        }), 500


@app.route('/api/case/<int:case_id>/image', methods=['POST'])
@login_required
def upload_case_image(case_id):
    """Upload an image for a case"""
    # Verify user ownership
    case = verify_case_ownership(case_id)
    if not case:
        return jsonify({"error": "Unauthorized"}), 403
    
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400
    
    file = request.files['image']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check file size (max 4MB for Vercel compatibility, 10MB for local)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    # Vercel has a 4.5MB request body limit, so we limit to 4MB to be safe
    max_size = 4 * 1024 * 1024 if os.getenv('VERCEL') else 10 * 1024 * 1024
    if file_size > max_size:
        size_mb = max_size / (1024 * 1024)
        return jsonify({'error': f'File size exceeds {size_mb}MB limit. Vercel has a 4.5MB request body limit.'}), 400
    
    # Check file type
    allowed_types = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    file_type = mimetypes.guess_type(file.filename)[0]
    
    if file_type not in allowed_types:
        return jsonify({'error': 'Only image files (JPEG, PNG, GIF, WebP) are allowed'}), 400
    
    # Read image data - ensure it's bytes for PostgreSQL BYTEA
    # Reset file pointer to beginning (in case it was read before)
    file.seek(0)
    image_data = file.read()
    
    if not image_data:
        return jsonify({'error': 'Image file is empty'}), 400
    
    if not isinstance(image_data, bytes):
        image_data = bytes(image_data)
    
    print(f"[IMAGE] Image data size: {len(image_data)} bytes, filename: {file.filename}")
    
    # Get description from form data
    description = request.form.get('description', '') or ''
    
    # Ensure filename is a string and not None
    filename = file.filename or 'image.jpg'
    if not isinstance(filename, str):
        filename = str(filename)
    
    # Ensure file_type is a string
    if not file_type or not isinstance(file_type, str):
        file_type = 'image/jpeg'  # Default fallback
    
    try:
        # Explicitly set created_at to avoid any datetime parsing issues with PostgreSQL
        from datetime import datetime
        
        # Create the image object with explicit types
        case_image = CaseImage(
            case_id=case_id,
            image_data=image_data,
            image_filename=filename,
            image_type=file_type,
            image_description=description,
            created_at=datetime.utcnow()  # Explicitly set to avoid default issues with PostgreSQL
        )
        
        db.session.add(case_image)
        db.session.flush()  # Flush to get the ID without committing
        
        # Verify the image was added correctly
        image_id = case_image.id
        
        db.session.commit()
        
        return jsonify({
            'image_id': image_id,
            'filename': case_image.image_filename,
            'message': 'Image uploaded successfully'
        })
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        error_type = type(e).__name__
        print(f"[IMAGE] Error uploading image: {error_type}: {error_msg}")
        import traceback
        traceback.print_exc()
        
        # Return detailed error for debugging (in production, you might want to sanitize this)
        # Include error type and message for better debugging
        error_response = {
            'error': f'Failed to upload image: {error_msg}',
            'error_type': error_type,
            'details': error_msg
        }
        
        # Check for specific PostgreSQL errors
        if 'pattern' in error_msg.lower() or 'string did not match' in error_msg.lower():
            error_response['error'] = 'Database schema error. The image table may be missing required columns.'
            error_response['details'] = 'Pattern matching error - check database schema'
        elif 'column' in error_msg.lower() and 'does not exist' in error_msg.lower():
            error_response['error'] = 'Database schema error. Missing required columns in image table.'
            error_response['details'] = error_msg
        elif 'null value' in error_msg.lower() or 'not null' in error_msg.lower():
            error_response['error'] = 'Database constraint error. Required fields are missing.'
            error_response['details'] = error_msg
        elif 'timeout' in error_msg.lower() or 'connection' in error_msg.lower():
            error_response['error'] = 'Database connection error. Please try again.'
            error_response['details'] = error_msg
        
        return jsonify(error_response), 500


@app.route('/api/case/<int:case_id>/images')
@login_required
def get_case_images(case_id):
    """Get all images for a case"""
    # Verify user ownership
    case = verify_case_ownership(case_id)
    if not case:
        return jsonify({"error": "Unauthorized"}), 403
    images = CaseImage.query.filter_by(case_id=case_id).order_by(CaseImage.created_at).all()
    result = []
    for img in images:
        try:
            # Handle created_at safely for PostgreSQL
            created_at_str = None
            if img.created_at:
                if isinstance(img.created_at, str):
                    # Already a string, try to parse and reformat
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(img.created_at.replace('Z', '+00:00'))
                        created_at_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except (ValueError, AttributeError):
                        created_at_str = str(img.created_at)
                else:
                    # It's a datetime object
                    created_at_str = img.created_at.strftime('%Y-%m-%d %H:%M:%S')
        except (AttributeError, ValueError, TypeError) as e:
            print(f"[IMAGE] Warning: Could not format created_at for image {img.id}: {e}")
            created_at_str = 'N/A'
        
        result.append({
        'id': img.id,
        'filename': img.image_filename,
        'description': img.image_description if img.image_description else '',
            'created_at': created_at_str
        })
    return jsonify(result)


@app.route('/api/case-image/<int:image_id>')
@login_required
def get_case_image(image_id):
    """Retrieve a case image by ID"""
    image = CaseImage.query.get(image_id)
    
    if not image:
        return jsonify({'error': 'Image not found'}), 404
    
    return send_file(
        BytesIO(image.image_data),
        mimetype=image.image_type,
        as_attachment=False,
        download_name=image.image_filename
    )


@app.route('/api/case-image/<int:image_id>', methods=['DELETE'])
@login_required
def delete_case_image(image_id):
    """Delete a case image"""
    # Verify user ownership of the case image
    image = CaseImage.query.get(image_id)
    if not image:
        return jsonify({"error": "Unauthorized"}), 403
    case = verify_case_ownership(image.case_id)
    if not case:
        return jsonify({"error": "Unauthorized"}), 403
    
    """Delete a case image"""
    image = CaseImage.query.get(image_id)
    
    if not image:
        return jsonify({'error': 'Image not found'}), 404
    
    db.session.delete(image)
    db.session.commit()
    
    return jsonify({'message': 'Image deleted successfully'})


@app.route('/api/case-image/<int:image_id>/description', methods=['GET', 'PUT'])
@login_required
def image_description(image_id):
    """Get or update image description"""
    try:
        image = CaseImage.query.get(image_id)
        
        if not image:
            return jsonify({'error': 'Image not found'}), 404
        
        # Verify user has permission to edit the case this image belongs to
        case = verify_case_ownership(image.case_id)
        if not case:
            return jsonify({"error": "Unauthorized"}), 403
        
        # Handle GET request - return current description
        if request.method == 'GET':
            return jsonify({
                'image_id': image.id,
                'description': image.image_description or ''
            })
        
        # Handle PUT request - update description
        data = request.get_json()
        description = data.get('description', '')
        # Sanitize HTML for image description for safe saving (handles HTML + plain text)
        image.image_description = sanitize_html_for_saving(description) if description else ''
        db.session.commit()
        return jsonify({
            'image_id': image.id,
            'description': image.image_description,
            'message': 'Description updated successfully'
        })
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Image description operation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to update description: {str(e)}'}), 500




# REMOVED: Candidate management routes (examiner-specific)
# @app.route('/api/candidate/<int:candidate_id>', methods=['PUT'])
# @login_required
# def update_candidate(candidate_id):
#     """Update a candidate"""
#     # Verify user ownership
#     obj = verify_candidate_ownership(update_id)
#     if not obj:
#         return jsonify({"error": "Unauthorized"}), 403
#     
#     """Update a candidate"""
#     candidate = Candidate.query.get(candidate_id)
#     
#     if not candidate:
#         return jsonify({'error': 'Candidate not found'}), 404
#     
#     data = request.get_json()
#     
#     if 'candidate_name' in data:
#         candidate.candidate_name = data['candidate_name']
#     if 'candidate_number' in data:
#         candidate.candidate_number = data['candidate_number']
#     
#     db.session.commit()
#     
#     return jsonify({'message': 'Candidate updated successfully'})


# @app.route('/api/candidate/<int:candidate_id>', methods=['DELETE'])
# @login_required
# def delete_candidate(candidate_id):
#     """Delete a candidate"""
#     # Verify user ownership
#     obj = verify_candidate_ownership(update_id)
#     if not obj:
#         return jsonify({"error": "Unauthorized"}), 403
#     
#     """Delete a candidate"""
#     candidate = Candidate.query.get(candidate_id)
#     
#     if not candidate:
#         return jsonify({'error': 'Candidate not found'}), 404
#     
#     db.session.delete(candidate)
#     db.session.commit()
#     
#     return jsonify({'message': 'Candidate deleted successfully'})


# ==================== UTILITY FUNCTIONS ====================

import socket

def find_free_port(start_port=5000, max_tries=20):
    port = start_port
    for _ in range(max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                port += 1
    raise RuntimeError("No free port found.")


import sys

def show_macos_gatekeeper_popup():
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        message = (
            "macOS Security Notice:\n\n"
            "If you see a message like:\n"
            "'FRCR_Examiner.app cannot be opened because it is from an unidentified developer.'\n\n"
            "This is normal for apps not downloaded from the App Store.\n\n"
            "How to open the app:\n"
            "1. Open Finder and locate FRCR_Examiner.app (in Applications or Downloads)\n"
            "2. Right-click (or Control-click) the app and select Open\n"
            "3. In the dialog, click Open again\n"
            "4. If you still can't open it, go to System Settings → Privacy & Security,\n"
            "   scroll to Security, click 'Allow Anyway', then try again.\n\n"
            "This only needs to be done the first time."
        )
        messagebox.showinfo("FRCR Examiner - macOS Info", message)
        root.destroy()
    except Exception:
        pass


# ==================== Question & Answer Management Endpoints ====================

@app.route('/api/case/<int:case_id>/questions', methods=['GET'])
@login_required
def get_case_questions(case_id):
    """Get all questions for a case"""
    # Verify user ownership
    case = verify_case_ownership(case_id)
    if not case:
        return jsonify({"error": "Unauthorized"}), 403
    
    questions = Question.query.filter_by(case_id=case_id).order_by(Question.question_number).all()
    return jsonify([{
        'id': q.id,
        'number': q.question_number,
        'text': q.question_text
    } for q in questions])


@app.route('/api/case/<int:case_id>/answers', methods=['GET'])
@login_required
def get_case_answers(case_id):
    """Get all answers for a case"""
    # Verify user ownership
    case = verify_case_ownership(case_id)
    if not case:
        return jsonify({"error": "Unauthorized"}), 403
    
    answers = Answer.query.filter_by(case_id=case_id).order_by(Answer.answer_number).all()
    return jsonify([{
        'id': a.id,
        'number': a.answer_number,
        'text': a.answer_text
    } for a in answers])


@app.route('/api/question/<int:question_id>', methods=['PUT'])
def update_question(question_id):
    """Update a single question's text"""
    question = Question.query.get(question_id)
    if not question:
        return jsonify({'error': 'Question not found'}), 404
    
    data = request.get_json()
    question.question_text = data.get('text', '').strip()
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Question updated'})


@app.route('/api/answer/<int:answer_id>', methods=['PUT'])
def update_answer(answer_id):
    """Update a single answer's text"""
    answer = Answer.query.get(answer_id)
    if not answer:
        return jsonify({'error': 'Answer not found'}), 404
    
    data = request.get_json()
    answer.answer_text = data.get('text', '').strip()
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Answer updated'})


@app.route('/api/case/<int:case_id>/qa-pairs', methods=['GET'])
@login_required
def get_case_qa_pairs(case_id):
    """Get Q&A pairs for a case"""
    # Verify user ownership
    case = verify_case_ownership(case_id)
    if not case:
        return jsonify({"error": "Unauthorized"}), 403
    
    questions = Question.query.filter_by(case_id=case_id).order_by(Question.question_number).all()
    answers = Answer.query.filter_by(case_id=case_id).order_by(Answer.answer_number).all()
    
    pairs = []
    max_pairs = max(len(questions), len(answers))
    
    for i in range(max_pairs):
        # Process question and answer text through safe_html filter to preserve structure
        question_text = questions[i].question_text if i < len(questions) else ''
        answer_text = answers[i].answer_text if i < len(answers) else ''
        
        # Apply structure preservation and sanitization
        question_text_processed = sanitize_html_for_display(question_text) if question_text else ''
        answer_text_processed = sanitize_html_for_display(answer_text) if answer_text else ''
        
        pair = {
            'number': i + 1,
            'question': {
                'id': questions[i].id,
                'text': question_text_processed
            } if i < len(questions) else {'id': None, 'text': ''},
            'answer': {
                'id': answers[i].id,
                'text': answer_text_processed
            } if i < len(answers) else {'id': None, 'text': ''}
        }
        pairs.append(pair)
    
    return jsonify(pairs)


# ==================== SIMPLIFIED Q&A ENDPOINTS ====================

@app.route('/api/case/<int:case_id>/qa-pairs', methods=['PUT'])
@login_required
def update_case_qa_pairs(case_id):
    """Simplified endpoint to update all Q&A pairs for a case in one request"""
    # Verify user ownership
    case = verify_case_ownership(case_id)
    if not case:
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.get_json()
    pairs = data.get('pairs', [])
    
    if not isinstance(pairs, list):
        return jsonify({'error': 'pairs must be an array'}), 400
    
    try:
        # Delete all existing Q&A pairs
        Question.query.filter_by(case_id=case_id).delete()
        Answer.query.filter_by(case_id=case_id).delete()
        
        # Create new pairs
        for index, pair in enumerate(pairs, start=1):
            question_text = (pair.get('question_text') or '').strip()
            answer_text = (pair.get('answer_text') or '').strip()
            
            # Only create if at least one has content
            if question_text or answer_text:
                if question_text:
                    # Sanitize question text for safe saving
                    question = Question(
                        case_id=case_id,
                        question_number=index,
                        question_text=sanitize_html_for_saving(question_text)
                    )
                    db.session.add(question)
                
                if answer_text:
                    # Sanitize answer text for safe saving (handles HTML from TinyMCE + plain text)
                    answer = Answer(
                        case_id=case_id,
                        answer_number=index,
                        answer_text=sanitize_html_for_saving(answer_text)
                    )
                    db.session.add(answer)
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'Updated {len(pairs)} Q&A pairs'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ==================== CANDIDATE NOTES API ====================

@app.route('/api/case/<int:case_id>/note', methods=['GET'])
@login_required
def get_candidate_note(case_id):
    """Get user's note for a specific case - STUDENTS ONLY"""
    from models import CandidateNote
    
    # Only students can access notes
    is_student = (hasattr(current_user, 'role') and current_user.role == UserRole.STUDENT)
    if not is_student:
        return jsonify({'error': 'Access denied. Notes are for students only.'}), 403
    
    note = CandidateNote.query.filter_by(case_id=case_id, user_id=current_user.id).first()
    
    if not note:
        return jsonify({'note_text': ''}), 200
    
    return jsonify({
        'id': note.id,
        'note_text': note.note_text,
        'created_at': note.created_at.isoformat() if note.created_at else None,
        'updated_at': note.updated_at.isoformat() if note.updated_at else None
    })


@app.route('/api/case/<int:case_id>/note', methods=['POST'])
@login_required
def save_candidate_note(case_id):
    """Create or update user's note for a specific case - STUDENTS ONLY"""
    from models import CandidateNote, Case
    
    # Only students can create/edit notes
    is_student = (hasattr(current_user, 'role') and current_user.role == UserRole.STUDENT)
    if not is_student:
        return jsonify({'error': 'Access denied. Notes are for students only.'}), 403
    
    # Verify case exists and is public
    case = Case.query.get(case_id)
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    if not case.is_public:
        return jsonify({'error': 'Cannot add notes to private cases'}), 403
    
    data = request.get_json()
    note_text = (data.get('note_text') or '').strip()
    
    # Check for existing note - use filter_by to prevent duplicates
    note = CandidateNote.query.filter_by(case_id=case_id, user_id=current_user.id).first()
    
    if note:
        # Update existing note only if text has changed
        if note.note_text != note_text:
        note.note_text = note_text
        note.updated_at = datetime.utcnow()
        action = 'updated'
    else:
            # No change, return existing note
            return jsonify({
                'success': True, 
                'message': 'Note unchanged', 
                'note_text': note.note_text, 
                'updated_at': note.updated_at.isoformat() if note.updated_at else None
            }), 200
    else:
        # Check if there are any other notes with same content (duplicate prevention)
        existing_duplicate = CandidateNote.query.filter_by(
            case_id=case_id,
            user_id=current_user.id,
            note_text=note_text
        ).first()
        
        if existing_duplicate:
            # Return existing duplicate instead of creating new one
            return jsonify({
                'success': True,
                'message': 'Note already exists',
                'note_text': existing_duplicate.note_text,
                'updated_at': existing_duplicate.updated_at.isoformat() if existing_duplicate.updated_at else None
            }), 200
        
        note = CandidateNote(case_id=case_id, user_id=current_user.id, note_text=note_text, created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        db.session.add(note)
        action = 'created'
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': f'Note {action}', 'note_text': note.note_text, 'updated_at': note.updated_at.isoformat() if note.updated_at else None})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


from access_control import has_case_edit_permission, has_case_view_access, has_case_delete_permission

def verify_case_ownership(case_id):
    """
    Helper to check if the current user can access/edit the case.
    Admins and content managers: can edit all cases.
    Students: can only view published cases, never edit.
    Returns the case if allowed, else None.
    """
    case = Case.query.get(case_id)
    if not case:
        return None
    # Admins and content managers can edit all cases
    if has_case_edit_permission(case):
        return case
    # Students: only allow view if published, never edit
    if has_case_view_access(case):
        # Only allow GET requests for students
        if request.method == 'GET':
            return case
        else:
            return None
    return None

@app.route('/api/case/<int:case_id>', methods=['GET', 'PUT'])
@login_required
def get_case(case_id):
    """Get case details as JSON or update case"""
    # Verify ownership
    case = verify_case_ownership(case_id)
    if not case:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Handle GET request
    if request.method == 'GET':
        return jsonify({
            'id': case.id,
            'case_number': case.case_number,
            'diagnosis': case.diagnosis,
            'questions': [{'question_text': q.question_text, 'id': q.id} for q in case.question_items],
            'answers': [{'answer_text': a.answer_text, 'id': a.id} for a in case.answer_items],
            'discussion': case.discussion,
            'module': case.module.name if case.module else None,
            'body_part': case.body_part.name if case.body_part else None,
            'status': case.status.name if case.status else 'DRAFT',
            'is_public': case.is_public
        })

    # Handle PUT request (update case)
    if request.method == 'PUT':
        data = request.get_json()
        print(f"[DEBUG] Incoming PUT data: {data}")
        if data is None:
            return jsonify({'error': 'No data provided'}), 400
        # Update fields if present
        if 'diagnosis' in data:
            # Sanitize diagnosis for safe saving (handles HTML + plain text)
            diagnosis_content = data.get('diagnosis', '')
            case.diagnosis = sanitize_html_for_saving(diagnosis_content) if diagnosis_content else ''
        if 'discussion' in data:
            # Sanitize discussion content for safe saving (handles HTML + plain text)
            discussion_content = data.get('discussion', '')
            case.discussion = sanitize_html_for_saving(discussion_content) if discussion_content else ''
        if 'module' in data:
            from models import FRCRModule
            try:
                case.module = FRCRModule[data['module']] if data['module'] else None
            except Exception:
                pass
        if 'body_part' in data:
            from models import BodyPart
            try:
                case.body_part = BodyPart[data['body_part']] if data['body_part'] else None
            except Exception:
                pass
        if 'age_group' in data:
            from models import AgeGroup
            try:
                case.age_group = AgeGroup[data['age_group']] if data['age_group'] else None
            except Exception:
                pass
        if 'status' in data:
            from models import CaseStatus
            try:
                case.status = CaseStatus[data['status']] if data['status'] else CaseStatus.DRAFT
                # Automatically sync is_public based on status: PUBLISHED = True, all others = False
                case.is_public = (case.status == CaseStatus.PUBLISHED)
            except (KeyError, AttributeError):
                pass
        elif 'is_public' in data:
            # Legacy support: if only is_public is provided (without status), sync status
            val = data['is_public']
            if isinstance(val, bool):
                case.is_public = val
            elif isinstance(val, str):
                case.is_public = val.lower() == 'true'
            elif isinstance(val, int):
                case.is_public = val == 1
            else:
                case.is_public = False
            # Sync status with is_public if status not explicitly set
            from models import CaseStatus
            if case.is_public:
                case.status = CaseStatus.PUBLISHED
            else:
                # Only change to DRAFT if current status is PUBLISHED (preserve other statuses)
                if case.status == CaseStatus.PUBLISHED:
                    case.status = CaseStatus.DRAFT
        # Optionally update Q&A pairs if present
        if 'pairs' in data:
            # Remove old Q&A
            from models import Question, Answer
            Question.query.filter_by(case_id=case.id).delete()
            Answer.query.filter_by(case_id=case.id).delete()
            for index, pair in enumerate(data['pairs'], start=1):
                question_text = (pair.get('question_text') or '').strip()
                answer_text = (pair.get('answer_text') or '').strip()
                if question_text:
                    # Sanitize question text for safe saving
                    q = Question(case_id=case.id, question_number=index, question_text=sanitize_html_for_saving(question_text))
                    db.session.add(q)
                if answer_text:
                    # Sanitize answer text for safe saving (handles HTML from TinyMCE + plain text)
                    a = Answer(case_id=case.id, answer_number=index, answer_text=sanitize_html_for_saving(answer_text))
                    db.session.add(a)
        try:
            db.session.commit()
            print(f"[DEBUG] Case {case.id} saved successfully.")
            return jsonify({'success': True, 'message': 'Case updated'})
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Failed to update case: {e}")
            return jsonify({'error': str(e)}), 500


@app.route('/api/case/<int:case_id>/note', methods=['DELETE'])
@login_required
def delete_candidate_note(case_id):
    """Delete user's note for a case - STUDENTS ONLY"""
    from models import CandidateNote
    
    # Only students can delete notes
    is_student = (hasattr(current_user, 'role') and current_user.role == UserRole.STUDENT)
    if not is_student:
        return jsonify({'error': 'Access denied. Notes are for students only.'}), 403
    
    note = CandidateNote.query.filter_by(case_id=case_id, user_id=current_user.id).first()
    
    if note:
        db.session.delete(note)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Note deleted'})
    
    return jsonify({'error': 'Note not found'}), 404


# ==================== TEXT HIGHLIGHTS API ====================

@app.route('/api/case/<int:case_id>/highlights', methods=['GET'])
@login_required
def get_highlights(case_id):
    """Get all highlights for a case by current user - STUDENTS ONLY"""
    from models import TextHighlight
    
    # Only students can access highlights
    is_student = (hasattr(current_user, 'role') and current_user.role == UserRole.STUDENT)
    if not is_student:
        return jsonify({'highlights': []}), 200  # Return empty for admins (they shouldn't see highlights)
    
    highlights = TextHighlight.query.filter_by(case_id=case_id, user_id=current_user.id).all()
    
    return jsonify({
        'highlights': [{
            'id': h.id,
            'text_content': h.text_content,
            'highlight_color': h.highlight_color,
            'field_name': h.field_name,
            'created_at': h.created_at.isoformat() if h.created_at else None
        } for h in highlights]
    })


@app.route('/api/case/<int:case_id>/highlight', methods=['POST'])
@login_required
def add_highlight(case_id):
    """Add a new text highlight - STUDENTS ONLY"""
    from models import TextHighlight, Case
    
    # Only students can create highlights
    is_student = (hasattr(current_user, 'role') and current_user.role == UserRole.STUDENT)
    if not is_student:
        return jsonify({'error': 'Access denied. Highlights are for students only.'}), 403
    
    # Verify case exists and is public
    case = Case.query.get(case_id)
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    if not case.is_public:
        return jsonify({'error': 'Cannot highlight private cases'}), 403
    
    data = request.get_json()
    text_content = data.get('text_content', '').strip()
    highlight_color = data.get('highlight_color', 'yellow')
    field_name = data.get('field_name', 'discussion')
    
    if not text_content:
        return jsonify({'error': 'Text content required'}), 400
    
    # Validate color
    valid_colors = ['yellow', 'green', 'pink', 'blue']
    if highlight_color not in valid_colors:
        return jsonify({'error': 'Invalid color'}), 400
    
    # Check for existing duplicate highlight (same case, user, text, color, and field)
    existing_highlight = TextHighlight.query.filter_by(
        case_id=case_id,
        user_id=current_user.id,
        text_content=text_content,
        highlight_color=highlight_color,
        field_name=field_name
    ).first()
    
    if existing_highlight:
        # Return existing highlight instead of creating duplicate
        return jsonify({
            'success': True,
            'highlight': {
                'id': existing_highlight.id,
                'text_content': existing_highlight.text_content,
                'highlight_color': existing_highlight.highlight_color,
                'field_name': existing_highlight.field_name
            },
            'message': 'Highlight already exists'
        }), 200
    
    highlight = TextHighlight(
        case_id=case_id,
        user_id=current_user.id,
        text_content=text_content,
        highlight_color=highlight_color,
        field_name=field_name
    )
    
    db.session.add(highlight)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'highlight': {
            'id': highlight.id,
            'text_content': highlight.text_content,
            'highlight_color': highlight.highlight_color,
            'field_name': highlight.field_name
        }
    })


@app.route('/api/highlight/<int:highlight_id>', methods=['DELETE'])
@login_required
def delete_highlight(highlight_id):
    """Delete a highlight - STUDENTS ONLY"""
    from models import TextHighlight
    
    # Only students can delete highlights
    is_student = (hasattr(current_user, 'role') and current_user.role == UserRole.STUDENT)
    if not is_student:
        return jsonify({'error': 'Access denied. Highlights are for students only.'}), 403
    
    highlight = TextHighlight.query.get(highlight_id)
    
    if not highlight:
        return jsonify({'error': 'Highlight not found'}), 404
    
    # Verify ownership - students can only delete their own highlights
    if highlight.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    db.session.delete(highlight)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Highlight deleted'})


# ==================== ADMIN ENDPOINTS ====================

@app.route('/api/admin/migrate-db', methods=['POST'])
@login_required
def migrate_db():
    """Create database tables if they don't exist - Admin only"""
    # Check both is_admin flag and role for compatibility
    is_admin = (hasattr(current_user, 'is_admin') and current_user.is_admin) or \
               (hasattr(current_user, 'role') and current_user.role == UserRole.ADMIN)
    if not is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    try:
        print("[ADMIN] Running database migration...")
        db.create_all()
        
        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        print(f"[ADMIN] Database migration complete. Tables: {', '.join(tables)}")
        return jsonify({
            'success': True, 
            'message': 'Database tables created',
            'tables_created': tables,
            'table_count': len(tables)
        }), 200
    except Exception as e:
        print(f"[ADMIN] Migration error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Migration failed: {str(e)}'}), 500

@app.route('/api/admin/check-db', methods=['GET'])
def check_db():
    """Check database connection and table status - Public endpoint for diagnostics"""
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        # Check if user table exists and has data
        user_count = 0
        if 'user' in tables:
            try:
                user_count = User.query.count()
            except Exception:
                pass
        
        return jsonify({
            'success': True,
            'database_connected': True,
            'tables': tables,
            'table_count': len(tables),
            'user_table_exists': 'user' in tables,
            'user_count': user_count,
            'message': 'Database is accessible' if 'user' in tables else 'Database connected but tables missing'
        }), 200
    except Exception as e:
        print(f"[DB] Check error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'database_connected': False,
            'error': str(e)
        }), 500
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    if sys.platform == 'darwin':
        show_macos_gatekeeper_popup()
    port = find_free_port(5000, 20)
    print(f"Starting server on http://127.0.0.1:{port}")
    app.run(debug=True, host='127.0.0.1', port=port)
