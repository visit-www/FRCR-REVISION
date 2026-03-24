# Load environment variables (must be first!)
# Order: .env -> .env.local (local overrides) -> .env.production (when ENV=production)
# .env.local overrides shell/vercel vars so USE_LOCAL_DB works for local runs
import os
from pathlib import Path
from dotenv import load_dotenv
_env_dir = Path(__file__).resolve().parent
load_dotenv(_env_dir / '.env', override=True)  # .env overrides shell (avoids stale R2_* etc)
load_dotenv(_env_dir / '.env.local', override=True)  # Local overrides (e.g. USE_LOCAL_DB=1)
if os.getenv('ENV') == 'production' or os.getenv('FLASK_ENV') == 'production':
    load_dotenv(_env_dir / '.env.production', override=True)

# Configure logging (before any module imports that use logging)
import logging
from urllib.parse import quote_plus as _quote_plus

# Structured JSON logging for production; human-readable for local dev
_is_production = os.getenv('VERCEL_ENV') == 'production'
if _is_production:
    class _JSONFormatter(logging.Formatter):
        def format(self, record):
            import json as _j
            return _j.dumps({
                'ts': self.formatTime(record),
                'level': record.levelname,
                'logger': record.name,
                'msg': record.getMessage(),
            })
    _handler = logging.StreamHandler()
    _handler.setFormatter(_JSONFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[_handler])
else:
    logging.basicConfig(
        level=logging.INFO if not os.getenv('FLASK_DEBUG') else logging.DEBUG,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    )
logger = logging.getLogger(__name__)

# ==================== SENTRY ERROR TRACKING ====================
_sentry_dsn = os.getenv('SENTRY_DSN')
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    def _sentry_before_send(event, hint):
        """Scrub PII from Sentry events before sending."""
        if 'request' in event:
            req = event['request']
            # Remove cookies and authorization headers
            if 'headers' in req:
                req['headers'] = {
                    k: v for k, v in req['headers'].items()
                    if k.lower() not in ('cookie', 'authorization', 'x-csrf-token')
                }
            # Remove request body data (may contain user reports)
            req.pop('data', None)
        # Remove user IP address
        if 'user' in event:
            event['user'].pop('ip_address', None)
        return event

    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[FlaskIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=float(os.getenv('SENTRY_TRACES_RATE', '0.1')),
        environment=os.getenv('VERCEL_ENV', 'development'),
        before_send=_sentry_before_send,
        send_default_pii=False,
    )
    logger.info('Sentry error tracking initialized')

# ==================== STUDENT CASE BROWSER ====================
# (Moved below app initialization)
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file, send_from_directory, flash
from models import UserRole
from flask_cors import CORS
from flask_login import LoginManager, login_required, current_user
from flask_migrate import Migrate
from models import db, User, Case, CaseImage, Question, Answer, BodyPart
from models import RevisionSession, RevisionHistory  # STUDENT REVISION: New models for balanced revision
from models import UserQAProgress  # STUDY MODE: SM-2 spaced repetition
from models import ForumMessage, ForumMessageVote, ForumMessageFlag  # Forum models
from models import ClinicalProtocol, OnCallQueryLog, IncidentalFindingCalculator  # Clinical tools
from models import RadiologyTemplate, ReportingAlgorithm  # New split tables (Feb 2026)
from models import ContentRequest  # User content requests (Feb 2026)
from models import RadiologyPearl  # Radiology pearls from teaching points
from models import case_algorithm_links, case_template_links, case_pearl_links, content_links  # Knowledge linking
from auth import auth_bp
from backup_routes import backup_bp
from admin_routes import admin_bp
from admin_enrichment_routes import enrichment_bp
from notes_integration_routes import notes_bp
from resources_routes import resources_bp
from reference_image_routes import reference_image_bp
# AJCC TNM Module - imports blueprints from the reusable module
from ajcc_tnm import get_blueprints, init_app as init_ajcc_tnm
admin_tnm_bp, tnm_bp = get_blueprints()
# TNM Calculator - standalone clinical-grade calculator module
from tnm_calculator.routes import tnm_calc_bp
from case_dicom_viewer import init_app as init_case_dicom, get_blueprint as get_case_dicom_bp
from oncall_routes import oncall_bp
from reporting_routes import reporting_bp
from radiology_tools import if_bp
from ai_prelim import AiPrelimError, generate_prelim_case_data
from datetime import datetime
from sqlalchemy.pool import NullPool
from io import BytesIO
import mimetypes
import json

# Cloudinary configuration for forum image uploads
import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    secure=True
)

app = Flask(__name__, 
    template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
    static_folder=os.path.join(os.path.dirname(__file__), 'static')
)

# Jinja filter: strip <style> and <script> tags from HTML content
# Prevents AI-generated or user-entered content from injecting global CSS/JS
import re as _re
@app.template_filter('strip_unsafe_tags')
def strip_unsafe_tags(html_content):
    if not html_content:
        return html_content
    html_content = _re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=_re.DOTALL | _re.IGNORECASE)
    html_content = _re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=_re.DOTALL | _re.IGNORECASE)
    return html_content

# CORS: restrict to production domain; allow all in local dev
if os.getenv('CORS_ORIGINS'):
    _cors_origins = [o.strip() for o in os.getenv('CORS_ORIGINS').split(',')]
elif os.getenv('VERCEL_ENV') == 'production':
    _cors_origins = ["https://www.radinsights.xyz", "https://radinsights.xyz"]
else:
    _cors_origins = ["*"]  # Local dev: allow all

CORS(app, resources={
    r"/api/*": {
        "origins": _cors_origins,
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Rate limiting — per-IP limits for abuse prevention
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["200 per minute"],
        storage_uri="memory://",
    )
    # Stricter limits for sensitive endpoints (applied via decorators in auth.py)
    app.config['LIMITER'] = limiter
    logger.info("Flask-Limiter enabled (200/min default)")
except ImportError:
    limiter = None
    logger.warning("flask-limiter not installed — rate limiting disabled")

# Ensure instance folder exists
instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
try:
    os.makedirs(instance_path, exist_ok=True)
except Exception as e:
    logger.warning(f"Could not create instance folder: {e}")
    instance_path = '/tmp'

# Configuration
# Set USE_LOCAL_DB=1 in .env.local to force SQLite for faster local startup
# Set USE_POOLED_DB=1 in .env.local to prefer Neon pooled URL (avoids "postgres message too large" with direct connection)
# Production (Vercel) uses PostgreSQL (Neon)
USE_LOCAL_DB = os.getenv('USE_LOCAL_DB', '').strip() in ('1', 'true', 'yes')
USE_POOLED_DB = os.getenv('USE_POOLED_DB', '').strip() in ('1', 'true', 'yes')
if USE_LOCAL_DB:
    DATABASE_URL = None
else:
    # Prefer pooled URL when USE_POOLED_DB=1 (fixes "postgres message too large" on local with Neon direct)
    if USE_POOLED_DB:
        DATABASE_URL = (
            os.getenv('DATABASE_URL')
            or os.getenv('POSTGRES_URL')
            or os.getenv('DATABASE_POSTGRES_URL')
            or os.getenv('DATABASE_POSTGRES_URL_NON_POOLING')
            or os.getenv('POSTGRES_URL_NON_POOLING')
            or os.getenv('frcr_revision_db_DATABASE_URL')
            or os.getenv('frcr_revision_db_POSTGRES_URL_NON_POOLING')
        )
    else:
        DATABASE_URL = (
            os.getenv('DATABASE_POSTGRES_URL_NON_POOLING')
            or os.getenv('POSTGRES_URL_NON_POOLING')
            or os.getenv('DATABASE_URL')
            or os.getenv('POSTGRES_URL')
            or os.getenv('DATABASE_POSTGRES_URL')
            or os.getenv('frcr_revision_db_POSTGRES_URL_NON_POOLING')
            or os.getenv('frcr_revision_db_DATABASE_URL')
        )

if DATABASE_URL:
    # Sanitize: strip embedded newlines and literal \n (common when loading from .env)
    DATABASE_URL = DATABASE_URL.strip().replace('\n', '').replace('\r', '').replace('\\n', '')
    # PostgreSQL on Vercel or external
    logger.info(f"Using PostgreSQL: {DATABASE_URL[:60]}...")
    # Handle both postgres:// and postgresql:// schemes
    db_uri = DATABASE_URL.replace('postgres://', 'postgresql://')
    
    # Remove unsupported query parameters (pgbouncer, supa, etc.) that cause psycopg2 errors
    # Some providers add query params not recognized by psycopg2
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
            # Sanitize values (strip newlines and literal \n from .env)
            params = {k: [v.strip().replace('\n', '').replace('\r', '').replace('\\n', '') for v in vals] for k, vals in params.items()}
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
    except Exception as e:
        pass  # URL parsing failed, use original db_uri
    
    # Enforce SSL for PostgreSQL connections (required for UK GDPR compliance)
    if 'sslmode' not in db_uri:
        separator = '&' if '?' in db_uri else '?'
        db_uri = db_uri + separator + 'sslmode=require'

    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri

    # For serverless environments (Vercel), disable connection pooling
    # Each function invocation should create and close its own connection
    if os.getenv('VERCEL'):
        logger.info("Serverless environment detected - using NullPool")
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'poolclass': NullPool,  # No connection pooling for serverless
            'pool_pre_ping': True,  # Verify connections before using
        }
else:
    # SQLite for local development
    logger.info(f"Using SQLite: {instance_path}/RadInsights_db.db")
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "RadInsights_db.db")}'
# SECURITY: SECRET_KEY hardening — no insecure defaults
_secret_key = os.getenv('SECRET_KEY')
if not _secret_key:
    if os.getenv('VERCEL') or os.getenv('VERCEL_ENV'):
        raise RuntimeError(
            "FATAL: SECRET_KEY environment variable is not set. "
            "This is required in production. Set it in Vercel environment variables."
        )
    else:
        # Local dev only: generate random ephemeral key (sessions won't persist across restarts)
        import secrets as _secrets
        _secret_key = _secrets.token_hex(32)
        print("[WARNING] SECRET_KEY not set — using random ephemeral key (local dev only)")
else:
    logger.info("SECRET_KEY is set")
app.config['SECRET_KEY'] = _secret_key
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# R2 stack upload: allow large multipart (1000+ images × ~1MB ≈ 1GB)
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_UPLOAD_MB', '1024')) * 1024 * 1024

# Only set SECURE in production (HTTPS). For localhost/HTTP, must be False or cookies won't be sent.
app_url = os.getenv('APP_URL', '') or os.getenv('VERCEL_URL', '')
is_local_http = 'localhost' in app_url or '127.0.0.1' in app_url or app_url.startswith('http://')
is_production = not is_local_http and (os.getenv('VERCEL_ENV') == 'production' or 'vercel.app' in app_url)

# Session cookie configuration (for regular sessions)
app.config['SESSION_COOKIE_SECURE'] = is_production  # HTTPS only in production; False for localhost
app.config['SESSION_COOKIE_HTTPONLY'] = True  # No JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
app.config['SESSION_COOKIE_NAME'] = 'frcr_session'  # Explicit name
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes session timeout

# Flask-Login "Remember Me" cookie configuration
# These settings control persistent login when user checks "Remember Me"
from datetime import timedelta
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=7)  # 7 days if "Remember Me" checked
app.config['REMEMBER_COOKIE_SECURE'] = is_production  # HTTPS only in production; False for localhost
app.config['REMEMBER_COOKIE_HTTPONLY'] = True  # No JavaScript access
app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
app.config['REMEMBER_COOKIE_NAME'] = 'frcr_remember'  # Explicit name

logger.info(f"SECURE={app.config['SESSION_COOKIE_SECURE']} (local_http={is_local_http}), REMEMBER_DAYS={app.config['REMEMBER_COOKIE_DURATION'].days}")

# Initialize database
db.init_app(app)

# Slow query logging — log queries taking > 1 second
import time as _time
from sqlalchemy import event as _sa_event

def _setup_slow_query_logging(app_instance):
    """Attach slow query listeners once engine is available."""
    engine = db.engine

    @_sa_event.listens_for(engine, "before_cursor_execute", named=True)
    def _before_cursor_execute(**kw):
        kw['context']._query_start_time = _time.monotonic()

    @_sa_event.listens_for(engine, "after_cursor_execute", named=True)
    def _after_cursor_execute(**kw):
        elapsed = _time.monotonic() - getattr(kw['context'], '_query_start_time', _time.monotonic())
        if elapsed > 1.0:
            _slow_logger = logging.getLogger('slow_query')
            _slow_logger.warning(f"Slow query ({elapsed:.2f}s): {kw['statement'][:200]}")

with app.app_context():
    try:
        _setup_slow_query_logging(app)
    except Exception as e:
        logger.warning(f"Slow query logging setup skipped: {e}")

# Initialize Flask-Migrate for Alembic migrations
migrate = Migrate(app, db)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to continue'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized():
    """Handle unauthorized access - return JSON for API/fetch, else redirect to login"""
    from flask import redirect, url_for, request
    # Return JSON for API requests (fetch, XHR, or Accept: application/json)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'Login required'}), 401
    if request.headers.get('Accept', '').lower().find('application/json') >= 0:
        return jsonify({'error': 'Login required'}), 401
    path = (request.path or '').strip()
    if path.startswith('/api/') or path.startswith('/case-dicom-viewer/api/'):
        return jsonify({'error': 'Login required'}), 401
    return redirect(url_for('auth.login'))


# ==================== INITIALIZATION HELPER FUNCTIONS ====================
# These functions MUST be defined before they are called in app.app_context()


def _ensure_superadmin_exists():
    """
    Ensure superadmin account exists. Creates one with a secure random password
    if it doesn't exist. The password is only shown once in the console/logs
    on first creation and should be changed immediately.
    
    SECURITY: Password is generated using cryptographically secure random bytes.
    It is NOT stored in code and is only displayed once at creation time.
    """
    import secrets
    import string
    from sqlalchemy import text
    
    SUPERADMIN_EMAIL = "lotusheart2016@gmail.com"
    
    # Clear any failed transactions from previous operations
    try:
        db.session.rollback()
    except Exception:
        pass
    
    # Use raw SQL to check if superadmin exists (avoids model column mismatch during migrations)
    try:
        result = db.session.execute(
            text('SELECT COUNT(*) FROM "user" WHERE email = :email'),
            {"email": SUPERADMIN_EMAIL}
        ).scalar()
        if result and result > 0:
            # Ensure the superadmin flag is set (for existing users before this feature)
            try:
                db.session.execute(
                    text('UPDATE "user" SET is_superadmin = true WHERE email = :email AND (is_superadmin IS NULL OR is_superadmin = false)'),
                    {"email": SUPERADMIN_EMAIL}
                )
                db.session.commit()
            except Exception:
                db.session.rollback()  # Clear failed transaction
            logger.info(f"Superadmin exists: {SUPERADMIN_EMAIL}")
            return
    except Exception as e:
        # Table doesn't exist yet or other error
        logger.warning(f"Check superadmin error (may be normal): {e}")
        db.session.rollback()
        return  # Don't try to create if we can't even check
    
    # Generate a cryptographically secure random password
    # 16 characters with uppercase, lowercase, digits, and special chars
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(16))
    
    try:
        # Create superadmin user with is_superadmin=True
        superadmin = User(
            email=SUPERADMIN_EMAIL,
            full_name="Super Admin",
            role=UserRole.ADMIN,
            is_superadmin=True,  # This is THE superadmin
            is_active=True,
            is_deleted=False
        )
        superadmin.set_password(password)
        
        db.session.add(superadmin)
        db.session.commit()
        
        # Log password ONCE - this is the only time it will be visible
        logger.info(
            "\n" + "=" * 60 +
            "\nSUPERADMIN ACCOUNT CREATED" +
            "\n" + "=" * 60 +
            f"\n  Email:    {SUPERADMIN_EMAIL}" +
            f"\n  Password: {password}" +
            f"\n  Role:     SUPERADMIN (highest privileges)" +
            "\n" + "=" * 60 +
            "\n  SAVE THIS PASSWORD NOW - IT WILL NOT BE SHOWN AGAIN!" +
            "\n  Change this password immediately after first login." +
            "\n" + "=" * 60
        )
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating superadmin: {e}")


def _seed_ajcc_data_if_needed():
    """
    Auto-seed AJCC body sections and disease sites if the tables are empty.
    This ensures TNM functionality works on fresh deployments.
    """
    from models import AJCCBodySection, AJCCDiseaseSite
    from sqlalchemy import text
    
    # Clear any failed transactions
    try:
        db.session.rollback()
    except Exception:
        pass
    
    # Body sections - Complete AJCC 8th Edition
    BODY_SECTIONS = [
        ("Head and Neck", "head-and-neck"),
        ("Upper Gastrointestinal Tract", "upper-gastrointestinal-tract"),
        ("Lower Gastrointestinal Tract", "lower-gastrointestinal-tract"),
        ("Hepatobiliary System", "hepatobiliary-system"),
        ("Neuroendocrine Tumors", "neuroendocrine-tumors"),
        ("Thorax", "thorax"),
        ("Bone", "bone"),
        ("Soft Tissue Sarcoma", "soft-tissue-sarcoma"),
        ("Skin", "skin"),
        ("Breast", "breast"),
        ("Female Reproductive Organs", "female-reproductive-organs"),
        ("Male Genital Organs", "male-genital-organs"),
        ("Urinary Tract", "urinary-tract"),
        ("Ophthalmic Sites", "ophthalmic-sites"),
        ("Central Nervous System", "central-nervous-system"),
        ("Endocrine System", "endocrine-system"),
        ("Hematologic Malignancies", "hematologic-malignancies"),
    ]
    
    # Disease sites by section - AJCC Cancer Staging Manual 8th Edition
    # Slugs must match existing database entries to avoid duplicates
    DISEASE_SITES = {
        # Head and Neck (11 sites)
        "head-and-neck": [
            ("Staging Principles of Head and Neck Cancers", "staging-head-and-neck-cancers", "head-and-neck/staging-head-and-neck-cancers/introduction-and-overview-of-key-concepts"),
            ("Oral Cavity", "oral-cavity", "head-and-neck/oral-cavity"),
            ("Salivary Glands", "salivary-glands", "head-and-neck/salivary-glands"),
            ("Oropharynx (HPV-Associated)", "oropharynx-hpv-associated", "head-and-neck/oropharynx-hpv-associated"),
            ("Oropharynx (HPV-Independent) and Hypopharynx", "oropharynx-hpv-independent-and-hypopharynx", "head-and-neck/oropharynx-hpv-independent-and-hypopharynx"),
            ("Nasopharynx", "nasopharynx", "head-and-neck/nasopharynx"),
            ("Larynx", "larynx", "head-and-neck/larynx"),
            ("Nasal Cavity and Paranasal Sinuses", "nasal-cavity-and-paranasal-sinuses", "head-and-neck/nasal-cavity-and-paranasal-sinuses"),
            ("Mucosal Melanoma of the Head and Neck", "mucosal-melanoma-of-the-head-and-neck", "head-and-neck/mucosal-melanoma-of-the-head-and-neck"),
            ("Cutaneous Carcinoma of the Head and Neck", "cutaneous-carcinoma-of-the-head-and-neck", "head-and-neck/cutaneous-carcinoma-of-the-head-and-neck"),
            ("Cervical Lymph Nodes and Unknown Primary Tumors of the Head and Neck", "cervical-lymph-nodes-and-unknown-primary-tumors-of-the-head-and-neck", "head-and-neck/cervical-lymph-nodes-and-unknown-primary-tumors-of-the-head-and-neck"),
        ],
        # Upper Gastrointestinal Tract (3 sites)
        "upper-gastrointestinal-tract": [
            ("Esophagus and Esophagogastric Junction", "esophagus-and-esophagogastric-junction", "upper-gastrointestinal-tract/esophagus-and-esophagogastric-junction"),
            ("Stomach", "stomach", "upper-gastrointestinal-tract/stomach"),
            ("Small Intestine", "small-intestine", "upper-gastrointestinal-tract/small-intestine"),
        ],
        # Lower Gastrointestinal Tract (3 sites)
        "lower-gastrointestinal-tract": [
            ("Appendix", "appendix", "lower-gastrointestinal-tract/appendix"),
            ("Colon and Rectum", "colon-and-rectum", "lower-gastrointestinal-tract/colon-and-rectum"),
            ("Anus", "anus", "lower-gastrointestinal-tract/anus"),
        ],
        # Hepatobiliary System (7 sites)
        "hepatobiliary-system": [
            ("Liver", "liver", "hepatobiliary-system/liver"),
            ("Intrahepatic Bile Ducts", "intrahepatic-bile-ducts", "hepatobiliary-system/intrahepatic-bile-ducts"),
            ("Perihilar Bile Ducts", "perihilar-bile-ducts", "hepatobiliary-system/perihilar-bile-ducts"),
            ("Distal Bile Duct", "distal-bile-duct", "hepatobiliary-system/distal-bile-duct"),
            ("Ampulla of Vater", "ampulla-of-vater", "hepatobiliary-system/ampulla-of-vater"),
            ("Gallbladder", "gallbladder", "hepatobiliary-system/gallbladder"),
            ("Exocrine Pancreas", "exocrine-pancreas", "hepatobiliary-system/exocrine-pancreas"),
        ],
        # Neuroendocrine Tumors (6 sites)
        "neuroendocrine-tumors": [
            ("Neuroendocrine Tumors of the Stomach", "neuroendocrine-tumors-of-the-stomach", "neuroendocrine-tumors/neuroendocrine-tumors-of-the-stomach"),
            ("Neuroendocrine Tumors of the Duodenum and Ampulla of Vater", "neuroendocrine-tumors-of-the-duodenum-and-ampulla-of-vater", "neuroendocrine-tumors/neuroendocrine-tumors-of-the-duodenum-and-ampulla-of-vater"),
            ("Neuroendocrine Tumors of the Jejunum and Ileum", "neuroendocrine-tumors-of-the-jejunum-and-ileum", "neuroendocrine-tumors/neuroendocrine-tumors-of-the-jejunum-and-ileum"),
            ("Neuroendocrine Tumors of the Appendix", "neuroendocrine-tumors-of-the-appendix", "neuroendocrine-tumors/neuroendocrine-tumors-of-the-appendix"),
            ("Neuroendocrine Tumors of the Colon and Rectum", "neuroendocrine-tumors-of-the-colon-and-rectum", "neuroendocrine-tumors/neuroendocrine-tumors-of-the-colon-and-rectum"),
            ("Neuroendocrine Tumors of the Pancreas", "neuroendocrine-tumors-of-the-pancreas", "neuroendocrine-tumors/neuroendocrine-tumors-of-the-pancreas"),
        ],
        # Thorax (3 sites)
        "thorax": [
            ("Lung", "lung", "thorax/lung"),
            ("Diffuse Pleural Mesothelioma", "diffuse-pleural-mesothelioma", "thorax/diffuse-pleural-mesothelioma"),
            ("Thymus", "thymus", "thorax/thymus"),
        ],
        # Bone (1 site)
        "bone": [
            ("Bone", "bone", "bone/bone"),
        ],
        # Soft Tissue Sarcoma (7 sites)
        "soft-tissue-sarcoma": [
            ("Introduction to Soft Tissue Sarcoma", "introduction-to-soft-tissue-sarcoma", "soft-tissue-sarcoma/introduction-to-soft-tissue-sarcoma/introduction-to-soft-tissue-sarcoma"),
            ("Soft Tissue Sarcoma of the Head and Neck", "soft-tissue-sarcoma-of-the-head-and-neck", "soft-tissue-sarcoma/soft-tissue-sarcoma-of-the-head-and-neck"),
            ("Soft Tissue Sarcoma of the Trunk and Extremities", "soft-tissue-sarcoma-of-the-trunk-and-extremities", "soft-tissue-sarcoma/soft-tissue-sarcoma-of-the-trunk-and-extremities"),
            ("Soft Tissue Sarcoma of the Abdomen and Thoracic Visceral Organs", "soft-tissue-sarcoma-of-the-abdomen-and-thoracic-visceral-organs", "soft-tissue-sarcoma/soft-tissue-sarcoma-of-the-abdomen-and-thoracic-visceral-organs"),
            ("Soft Tissue Sarcoma of the Retroperitoneum", "soft-tissue-sarcoma-of-the-retroperitoneum", "soft-tissue-sarcoma/soft-tissue-sarcoma-of-the-retroperitoneum"),
            ("Soft Tissue Sarcoma - Unusual Histologies and Sites", "soft-tissue-sarcoma-unusual-histologies-and-sites", "soft-tissue-sarcoma/soft-tissue-sarcoma-unusual-histologies-and-sites"),
            ("Gastrointestinal Stromal Tumor", "gastrointestinal-stromal-tumor", "soft-tissue-sarcoma/gastrointestinal-stromal-tumor"),
        ],
        # Skin (2 sites)
        "skin": [
            ("Melanoma of the Skin", "melanoma-of-the-skin", "skin/melanoma-of-the-skin"),
            ("Merkel Cell Carcinoma", "merkel-cell-carcinoma", "skin/merkel-cell-carcinoma"),
        ],
        # Breast (1 site)
        "breast": [
            ("Breast", "breast", "breast/breast"),
        ],
        # Female Reproductive Organs (7 sites)
        "female-reproductive-organs": [
            ("Vulva", "vulva", "female-reproductive-organs/vulva"),
            ("Vagina", "vagina", "female-reproductive-organs/vagina"),
            ("Cervix Uteri", "cervix-uteri", "female-reproductive-organs/cervix-uteri"),
            ("Corpus Uteri: Carcinoma and Carcinosarcoma", "corpus-uteri-carcinoma-and-carcinosarcoma", "female-reproductive-organs/corpus-uteri-carcinoma-and-carcinosarcoma"),
            ("Corpus Uteri Sarcoma", "corpus-uteri-sarcoma", "female-reproductive-organs/corpus-uteri-sarcoma"),
            ("Ovary, Fallopian Tube, and Primary Peritoneal Carcinoma", "ovary-fallopian-tube-and-primary-peritoneal-carcinoma", "female-reproductive-organs/ovary-fallopian-tube-and-primary-peritoneal-carcinoma"),
            ("Gestational Trophoblastic Neoplasms", "gestational-trophoblastic-neoplasms", "female-reproductive-organs/gestational-trophoblastic-neoplasms"),
        ],
        # Male Genital Organs (3 sites)
        "male-genital-organs": [
            ("Penis", "penis", "male-genital-organs/penis"),
            ("Prostate", "prostate", "male-genital-organs/prostate"),
            ("Testis", "testis", "male-genital-organs/testis"),
        ],
        # Urinary Tract (4 sites)
        "urinary-tract": [
            ("Kidney", "kidney", "urinary-tract/kidney"),
            ("Renal Pelvis and Ureter", "renal-pelvis-and-ureter", "urinary-tract/renal-pelvis-and-ureter"),
            ("Urinary Bladder", "urinary-bladder", "urinary-tract/urinary-bladder"),
            ("Urethra", "urethra", "urinary-tract/urethra"),
        ],
        # Ophthalmic Sites (8 sites)
        "ophthalmic-sites": [
            ("Conjunctival Carcinoma", "conjunctival-carcinoma", "ophthalmic-sites/conjunctival-carcinoma"),
            ("Conjunctival Melanoma", "conjunctival-melanoma", "ophthalmic-sites/conjunctival-melanoma"),
            ("Eyelid Carcinoma", "eyelid-carcinoma", "ophthalmic-sites/eyelid-carcinoma"),
            ("Lacrimal Gland Carcinoma", "lacrimal-gland-carcinoma", "ophthalmic-sites/lacrimal-gland-carcinoma"),
            ("Ocular Adnexal Lymphoma", "ocular-adnexal-lymphoma", "ophthalmic-sites/ocular-adnexal-lymphoma"),
            ("Orbital Sarcoma", "orbital-sarcoma", "ophthalmic-sites/orbital-sarcoma"),
            ("Retinoblastoma", "retinoblastoma", "ophthalmic-sites/retinoblastoma"),
            ("Uveal Melanoma", "uveal-melanoma", "ophthalmic-sites/uveal-melanoma"),
        ],
        # Central Nervous System (1 site)
        "central-nervous-system": [
            ("Brain and Spinal Cord", "brain-and-spinal-cord", "central-nervous-system/brain-and-spinal-cord"),
        ],
        # Endocrine System (5 sites)
        "endocrine-system": [
            ("Thyroid: Differentiated and Anaplastic Carcinoma", "throid-differentiated-and-anaplastic-carcinoma", "endocrine-system/throid-differentiated-and-anaplastic-carcinoma"),
            ("Thyroid - Medullary", "thyroid-medullary", "endocrine-system/thyroid-medullary"),
            ("Parathyroid", "parathyroid", "endocrine-system/parathyroid"),
            ("Adrenal Cortical Carcinoma", "adrenal-cortical-carcinoma", "endocrine-system/adrenal-cortical-carcinoma"),
            ("Adrenal Neuroendocrine Tumors", "adrenal-neuroendocrine-tumors", "endocrine-system/adrenal-neuroendocrine-tumors"),
        ],
        # Hematologic Malignancies (6 sites)
        "hematologic-malignancies": [
            ("Introduction to Hematologic Malignancies", "introduction-to-hematologic-malignancies", "hematologic-malignancies/introduction-to-hematologic-malignancies/introduction-to-hematologic-malignancies"),
            ("Hodgkin and Non-Hodgkin Lymphomas", "hodgkin-and-non-hodgkin-lymphomas", "hematologic-malignancies/hodgkin-and-non-hodgkin-lymphomas"),
            ("Pediatric Hodgkin and Non-Hodgkin Lymphomas", "pediatric-hodgkin-and-non-hodgkin-lymphomas", "hematologic-malignancies/pediatric-hodgkin-and-non-hodgkin-lymphomas"),
            ("Primary Cutaneous Lymphomas", "primary-cutaneous-lymphomas", "hematologic-malignancies/primary-cutaneous-lymphomas"),
            ("Plasma Cell Myeloma and Plasma Cell Disorders", "plasma-cell-myeloma-and-plasma-cell-disorders", "hematologic-malignancies/plasma-cell-myeloma-and-plasma-cell-disorders"),
            ("Leukemia: Unspecified or Other Type", "leukemia", "hematologic-malignancies/leukemia"),
        ],
    }
    
    # Use raw SQL for count to avoid model column mismatch during migrations
    try:
        existing_sections = db.session.execute(text("SELECT COUNT(*) FROM ajcc_body_section")).scalar() or 0
        existing_sites = db.session.execute(text("SELECT COUNT(*) FROM ajcc_disease_site")).scalar() or 0
    except Exception as e:
        # Tables don't exist yet
        logger.warning(f"AJCC tables check error (may be normal): {e}")
        db.session.rollback()
        existing_sections = 0
        existing_sites = 0
    
    # Count expected disease sites
    expected_sites = sum(len(diseases) for diseases in DISEASE_SITES.values())
    
    # Check if we need to add missing entries or cleanup duplicates
    # Always run if counts don't match exactly (duplicates can inflate count)
    if existing_sections == len(BODY_SECTIONS) and existing_sites == expected_sites:
        logger.info(f"AJCC data complete: {existing_sections} sections, {existing_sites} sites")
        return
    
    logger.info(f"Syncing AJCC data (have {existing_sections}/{len(BODY_SECTIONS)} sections, {existing_sites}/{expected_sites} sites)...")
    
    try:
        # Seed body sections
        section_map = {}
        for name, slug in BODY_SECTIONS:
            existing = AJCCBodySection.query.filter_by(slug=slug).first()
            if not existing:
                section = AJCCBodySection(section_name=name, slug=slug)
                db.session.add(section)
                db.session.flush()
                section_map[slug] = section
            else:
                section_map[slug] = existing
        
        # Seed disease sites
        added_sites = 0
        for section_slug, diseases in DISEASE_SITES.items():
            section = section_map.get(section_slug)
            if not section:
                continue
            for disease_name, disease_slug, url_path in diseases:
                # Check by both slug and body_section_id to ensure correct parent
                existing = AJCCDiseaseSite.query.filter_by(
                    slug=disease_slug, 
                    body_section_id=section.id
                ).first()
                if not existing:
                    site = AJCCDiseaseSite(
                        disease_name=disease_name,
                        slug=disease_slug,
                        body_section_id=section.id,
                        ajcc_url_path=url_path
                    )
                    db.session.add(site)
                    added_sites += 1
        
        db.session.commit()
        
        # Cleanup: Remove disease sites with slugs not in the seed data
        # This handles cases where slug changed (e.g., "brain-spinal-cord" -> "brain")
        valid_slugs = set()
        for diseases in DISEASE_SITES.values():
            for _, slug, _ in diseases:
                valid_slugs.add(slug)
        
        # Find and remove orphaned/duplicate entries
        all_sites = AJCCDiseaseSite.query.all()
        removed_sites = 0
        for site in all_sites:
            if site.slug not in valid_slugs:
                # Check if this site has staging data - if so, skip
                if not site.staging_data:
                    db.session.delete(site)
                    removed_sites += 1
                    logger.info(f"Removed orphaned disease site: {site.disease_name} (slug: {site.slug})")
        
        if removed_sites > 0:
            db.session.commit()
        
        final_sections = AJCCBodySection.query.count()
        final_sites = AJCCDiseaseSite.query.count()
        if added_sites > 0 or removed_sites > 0:
            logger.info(f"AJCC updated: +{added_sites} added, -{removed_sites} removed. Total: {final_sections} sections, {final_sites} disease sites")
        else:
            logger.info(f"AJCC complete: {final_sections} sections, {final_sites} disease sites")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error seeding AJCC data: {e}")


def _migrate_reporting_templates_if_needed():
    """One-time migration: copy rows from legacy reporting_template to new tables.
    Idempotent — only runs if new tables are empty AND old table has data.
    Uses raw SQL so no ORM model is needed for the legacy table."""
    from sqlalchemy import text
    try:
        # Check if legacy table exists
        table_names = sa_inspect(db.engine).get_table_names()
        if 'reporting_template' not in table_names:
            return

        old_count = db.session.execute(text('SELECT COUNT(*) FROM reporting_template')).scalar()
        if old_count == 0:
            return

        rad_count = db.session.execute(text('SELECT COUNT(*) FROM radiology_template')).scalar()
        alg_count = db.session.execute(text('SELECT COUNT(*) FROM reporting_algorithm')).scalar()
        if rad_count > 0 or alg_count > 0:
            return  # Already migrated

        logger.info(f'Copying {old_count} rows from legacy reporting_template...')

        RADIOLOGY_CATEGORIES = {'radiology_template', 'personal_template'}
        rad_added = alg_added = 0

        rows = db.session.execute(text('SELECT * FROM reporting_template')).mappings().all()
        for old in rows:
            if old.get('category') in RADIOLOGY_CATEGORIES:
                origin = 'personal' if old['category'] == 'personal_template' else 'admin'
                new = RadiologyTemplate(
                    slug=old['slug'], title=old['title'], origin=origin,
                    body_section=old.get('body_section'), description=old.get('description'),
                    keywords=old.get('keywords'), template_text=old.get('pacs_report_text'),
                    source_citation=old.get('source_citation'), guideline_version=old.get('guideline_version'),
                    is_available=old.get('is_available', False),
                    is_ai_generated=old.get('is_ai_generated', False),
                    verified_by_user_id=old.get('verified_by_user_id'),
                    verified_at=old.get('verified_at'),
                    generation_prompt=old.get('generation_prompt'), generation_model=old.get('generation_model'),
                    generated_at=old.get('generated_at'), created_by_user_id=old.get('created_by_user_id'),
                    last_edit_note=old.get('last_edit_note'), legacy_id=old['id'],
                )
                if old.get('created_at'):
                    new.created_at = old['created_at']
                if old.get('updated_at'):
                    new.updated_at = old['updated_at']
                db.session.add(new)
                rad_added += 1
            else:
                cat = old.get('category', '')
                if cat in ('smart_reporter_cache', 'ai_generated'):
                    origin = 'user'
                elif cat == 'anatomy':
                    origin = 'anatomy_cache'
                else:
                    origin = 'admin'
                new = ReportingAlgorithm(
                    slug=old['slug'], title=old['title'], origin=origin,
                    category=cat, body_section=old.get('body_section'),
                    description=old.get('description'), keywords=old.get('keywords'),
                    template_html=old.get('template_html'), algorithm_html=old.get('algorithm_html'),
                    source_citation=old.get('source_citation'), guideline_version=old.get('guideline_version'),
                    is_available=old.get('is_available', False),
                    is_ai_generated=old.get('is_ai_generated', False),
                    verified_by_user_id=old.get('verified_by_user_id'),
                    verified_at=old.get('verified_at'),
                    generation_prompt=old.get('generation_prompt'), generation_model=old.get('generation_model'),
                    generated_at=old.get('generated_at'), created_by_user_id=old.get('created_by_user_id'),
                    last_edit_note=old.get('last_edit_note'), legacy_id=old['id'],
                )
                if old.get('created_at'):
                    new.created_at = old['created_at']
                if old.get('updated_at'):
                    new.updated_at = old['updated_at']
                db.session.add(new)
                alg_added += 1

        db.session.commit()
        logger.info(f'Migration done: {rad_added} → radiology_template, {alg_added} → reporting_algorithm')
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error migrating reporting_template: {e}')


# ==================== DATABASE INITIALIZATION ====================

with app.app_context():
    try:
        db.create_all()

        # Add columns that db.create_all() won't add to existing tables
        from sqlalchemy import text, inspect as sa_inspect
        insp = sa_inspect(db.engine)
        def _add_col_if_missing(table, column, col_sql):
            if table in insp.get_table_names():
                existing = [c['name'] for c in insp.get_columns(table)]
                if column not in existing:
                    with db.engine.connect() as conn:
                        conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {col_sql}'))
                        conn.commit()
                    logger.info(f'Added column {table}.{column}')

        # -- reporting_template (legacy — keep columns for migration) --
        _add_col_if_missing('reporting_template', 'pacs_report_text', 'pacs_report_text TEXT')
        _add_col_if_missing('reporting_template', 'is_ai_generated', 'is_ai_generated BOOLEAN DEFAULT false NOT NULL')
        _add_col_if_missing('reporting_template', 'verified_by_user_id', 'verified_by_user_id INTEGER')
        _add_col_if_missing('reporting_template', 'verified_at', 'verified_at TIMESTAMP')

        # -- Migrate legacy reporting_template → new tables --
        _migrate_reporting_templates_if_needed()

        # -- Widen String(500) columns to TEXT on both new tables --
        def _widen_col_to_text(table, column):
            """ALTER VARCHAR(500) → TEXT. Idempotent on PostgreSQL (safe to re-run)."""
            try:
                db.session.execute(db.text(
                    f'ALTER TABLE "{table}" ALTER COLUMN {column} TYPE TEXT'
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()
        for _tbl in ['radiology_template', 'reporting_algorithm']:
            for _col in ['description', 'source_citation', 'last_edit_note']:
                _widen_col_to_text(_tbl, _col)

        # -- clinical_protocol --
        _add_col_if_missing('clinical_protocol', 'body_section', 'body_section VARCHAR(100)')
        _add_col_if_missing('clinical_protocol', 'source_url', 'source_url VARCHAR(1000)')
        _add_col_if_missing('clinical_protocol', 'is_published', 'is_published BOOLEAN DEFAULT false NOT NULL')
        _add_col_if_missing('clinical_protocol', 'verified_by_user_id', 'verified_by_user_id INTEGER')
        _add_col_if_missing('clinical_protocol', 'verified_at', 'verified_at TIMESTAMP')
        _add_col_if_missing('clinical_protocol', 'created_by_user_id', 'created_by_user_id INTEGER')
        _add_col_if_missing('clinical_protocol', 'updated_at', 'updated_at TIMESTAMP')

        # -- incidental_finding_calculator --
        _add_col_if_missing('incidental_finding_calculator', 'body_section', 'body_section VARCHAR(100)')
        _add_col_if_missing('incidental_finding_calculator', 'category', 'category VARCHAR(100)')
        _add_col_if_missing('incidental_finding_calculator', 'description', 'description VARCHAR(500)')
        _add_col_if_missing('incidental_finding_calculator', 'algorithm_html', 'algorithm_html TEXT')
        _add_col_if_missing('incidental_finding_calculator', 'guideline_url', 'guideline_url VARCHAR(1000)')
        _add_col_if_missing('incidental_finding_calculator', 'verified_by_user_id', 'verified_by_user_id INTEGER')
        _add_col_if_missing('incidental_finding_calculator', 'verified_at', 'verified_at TIMESTAMP')
        _add_col_if_missing('incidental_finding_calculator', 'created_by_user_id', 'created_by_user_id INTEGER')
        _add_col_if_missing('incidental_finding_calculator', 'last_edit_note', 'last_edit_note VARCHAR(500)')

        # Widen guideline_source from VARCHAR(300) to TEXT (now stores JSON with references)
        try:
            with db.engine.connect() as conn:
                conn.execute(text(
                    'ALTER TABLE incidental_finding_calculator '
                    'ALTER COLUMN guideline_source TYPE TEXT'
                ))
                conn.commit()
        except Exception:
            pass  # already TEXT or table doesn't exist

        # -- reporting_algorithm: modality --
        _add_col_if_missing('reporting_algorithm', 'modality', 'modality VARCHAR(200)')

        # -- user: AI rate limiting --
        _add_col_if_missing('user', 'ai_usage_date', 'ai_usage_date DATE')
        _add_col_if_missing('user', 'ai_usage_count', 'ai_usage_count INTEGER DEFAULT 0')

        # -- user: Login rate limiting (brute force protection) --
        _add_col_if_missing('user', 'failed_login_count', 'failed_login_count INTEGER DEFAULT 0')
        _add_col_if_missing('user', 'failed_login_last', 'failed_login_last TIMESTAMP')
        _add_col_if_missing('user', 'locked_until', 'locked_until TIMESTAMP')

        # -- user: TOTP 2FA --
        _add_col_if_missing('user', 'totp_secret', 'totp_secret TEXT')
        _add_col_if_missing('user', 'totp_enabled', 'totp_enabled BOOLEAN DEFAULT false NOT NULL')

        # -- user: Widen token columns VARCHAR(255) → TEXT for encrypted storage --
        for _token_col in ['notion_access_token', 'anki_api_key']:
            _widen_col_to_text('user', _token_col)

        # -- reporting_session (legacy) --
        _add_col_if_missing('reporting_session', 'ask_claude_count', 'ask_claude_count INTEGER DEFAULT 0')
        _add_col_if_missing('reporting_session', 'updated_at', 'updated_at TIMESTAMP')

        # -- published_report (legacy) --
        _add_col_if_missing('published_report', 'algorithm_tree_json', 'algorithm_tree_json TEXT')

        # Auto-seed AJCC body sections and disease sites if not present
        _seed_ajcc_data_if_needed()
        
        # Ensure superadmin account exists
        _ensure_superadmin_exists()
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


# ============================================================================
# SECURITY HELPERS
# ============================================================================

import bleach as _bleach

# HTML sanitization for admin/AI-generated clinical content
_SANITIZE_ALLOWED_TAGS = list(_bleach.ALLOWED_TAGS) + [
    'div', 'span', 'p', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td', 'caption', 'colgroup', 'col',
    'ul', 'ol', 'li', 'dl', 'dt', 'dd',
    'img', 'figure', 'figcaption',
    'input', 'select', 'option', 'optgroup', 'label', 'button', 'form', 'textarea', 'fieldset', 'legend',
    'details', 'summary', 'section', 'article', 'nav', 'header', 'footer', 'aside', 'main',
    'hr', 'pre', 'code', 'sup', 'sub', 'mark', 'small', 'del', 'ins',
    'abbr', 'cite', 'dfn', 'kbd', 'samp', 'var', 'time', 'data',
    'svg', 'path', 'circle', 'rect', 'line', 'polyline', 'polygon', 'g', 'text', 'use', 'defs',
]

_SANITIZE_ALLOWED_ATTRS = {
    '*': ['class', 'id', 'style', 'role', 'aria-label', 'aria-hidden', 'aria-expanded',
          'aria-controls', 'aria-selected', 'aria-describedby', 'title', 'tabindex',
          'data-value', 'data-stage', 'data-type', 'data-target', 'data-toggle',
          'data-dismiss', 'data-parent', 'data-slide', 'data-slide-to', 'data-bs-toggle',
          'data-bs-target', 'data-bs-dismiss', 'data-bs-parent', 'data-category',
          'data-field', 'data-index', 'data-key', 'data-node', 'data-step',
          'onclick', 'onchange', 'oninput', 'onsubmit'],
    'a': ['href', 'target', 'rel', 'download'],
    'img': ['src', 'alt', 'width', 'height', 'loading'],
    'input': ['type', 'name', 'value', 'checked', 'placeholder', 'disabled', 'readonly',
              'min', 'max', 'step', 'required', 'pattern', 'autocomplete'],
    'select': ['name', 'disabled', 'required', 'multiple'],
    'option': ['value', 'selected', 'disabled'],
    'textarea': ['name', 'rows', 'cols', 'placeholder', 'disabled', 'readonly'],
    'button': ['type', 'disabled', 'name', 'value'],
    'form': ['action', 'method'],
    'td': ['colspan', 'rowspan'],
    'th': ['colspan', 'rowspan', 'scope'],
    'col': ['span'],
    'colgroup': ['span'],
    'label': ['for'],
    'time': ['datetime'],
    'svg': ['viewBox', 'xmlns', 'width', 'height', 'fill', 'stroke'],
    'path': ['d', 'fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin'],
    'circle': ['cx', 'cy', 'r', 'fill', 'stroke'],
    'rect': ['x', 'y', 'width', 'height', 'rx', 'ry', 'fill', 'stroke'],
    'line': ['x1', 'y1', 'x2', 'y2', 'stroke', 'stroke-width'],
}


def sanitize_clinical_html(html_content):
    """Sanitize admin/AI-generated clinical HTML, stripping script tags and event handlers.
    Allows a wide range of tags needed for interactive calculators and decision trees."""
    if not html_content:
        return html_content
    return _bleach.clean(
        html_content,
        tags=_SANITIZE_ALLOWED_TAGS,
        attributes=_SANITIZE_ALLOWED_ATTRS,
        strip=True,
    )


# EXIF stripping — remove GPS/device metadata from uploaded images (GDPR)
def _strip_exif(file_stream):
    """Strip EXIF metadata from image file stream. Returns cleaned BytesIO or original if not applicable."""
    try:
        from PIL import Image
        import io as _io
        file_stream.seek(0)
        img = Image.open(file_stream)
        if img.format not in ('JPEG', 'PNG', 'WEBP'):
            file_stream.seek(0)
            return file_stream
        # Re-save without EXIF
        clean = _io.BytesIO()
        img.save(clean, format=img.format, exif=b'')
        clean.seek(0)
        return clean
    except Exception:
        # If Pillow not installed or image can't be processed, pass through
        file_stream.seek(0)
        return file_stream


# Image magic byte validation (defense-in-depth alongside extension check + Cloudinary)
_IMAGE_MAGIC_BYTES = {
    b'\xff\xd8\xff': 'image/jpeg',
    b'\x89PNG': 'image/png',
    b'GIF87a': 'image/gif',
    b'GIF89a': 'image/gif',
}


def _validate_image_magic(file_stream, allowed_types=None):
    """Check file header matches claimed image type. Returns detected MIME type or None."""
    if allowed_types is None:
        allowed_types = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    header = file_stream.read(12)
    file_stream.seek(0)
    for magic, mime in _IMAGE_MAGIC_BYTES.items():
        if header.startswith(magic):
            return mime if mime in allowed_types else None
    # WebP: RIFF....WEBP
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return 'image/webp' if 'image/webp' in allowed_types else None
    return None


def _validate_return_url(url, default='/dashboard'):
    """Validate that a return URL is a safe local path (no open redirect)."""
    if not url:
        return default
    from urllib.parse import urlparse
    parsed = urlparse(url)
    # Reject absolute URLs with a scheme or netloc (external redirect)
    if parsed.scheme or parsed.netloc:
        return default
    # Reject protocol-relative URLs (//evil.com)
    if url.startswith('//'):
        return default
    # Must start with /
    if not url.startswith('/'):
        return default
    return url


# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(backup_bp)
app.register_blueprint(admin_bp)  # Sprint 2: Admin user management
app.register_blueprint(enrichment_bp)  # Data migration: Import, enrich, promote cases
app.register_blueprint(notes_bp)  # Notion + Anki integration for student notes
app.register_blueprint(resources_bp)  # PubMed, TCIA, RadiologyAssistant resources
app.register_blueprint(reference_image_bp)  # Reference image curation (CC-licensed CT/MRI, anatomy, concept)
# Initialize AJCC TNM module and register its blueprints
init_ajcc_tnm(app)
app.register_blueprint(admin_tnm_bp)  # AJCC TNM staging system - admin routes
app.register_blueprint(tnm_bp)  # AJCC TNM staging system - public routes
app.register_blueprint(tnm_calc_bp)  # TNM Calculator - standalone clinical-grade calculator
init_case_dicom(app)
app.register_blueprint(get_case_dicom_bp())  # Case DICOM Viewer - OneDrive image stacks
app.register_blueprint(oncall_bp)  # On-Call Session Helper - curated clinical protocols
app.register_blueprint(reporting_bp)  # Algorithm Finder + Non-oncologic reporting templates
app.register_blueprint(if_bp)  # Radiology Tools - guideline-based calculators (URL: /incidental-findings)

# Global PII guard — blocks patient-identifiable data in all POST/PUT JSON requests
from pii_guard import create_pii_middleware
create_pii_middleware(app)

# Apply stricter rate limits to sensitive auth endpoints
if limiter:
    limiter.limit("5 per hour")(app.view_functions.get('auth.register', lambda: None))
    limiter.limit("10 per minute")(app.view_functions.get('auth.login', lambda: None))
    limiter.limit("5 per hour")(app.view_functions.get('auth.forgot_password', lambda: None))

# Security headers — applied to every response
@app.after_request
def add_security_headers(response):
    """Add security headers to every response."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'  # Allow same-origin iframes (TNM calc embeds)
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if is_production:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    # Content Security Policy — allow self, Cloudinary (images), CDN (Bootstrap, Font Awesome)
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
        "img-src 'self' data: blob: https://res.cloudinary.com https://*.cloudinary.com https://upload.wikimedia.org https://*.wikimedia.org https://prod-images-static.radiopaedia.org; "
        "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
        "connect-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://res.cloudinary.com https://*.cloudinary.com https://fonts.googleapis.com https://fonts.gstatic.com; "
        "frame-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'"
    )
    return response


# ============================================================================
# CRON ENDPOINTS (Vercel Cron - 60s timeout even on Hobby plan)
# ============================================================================

@app.route('/api/cron/process-tnm-jobs', methods=['GET', 'POST'])
def process_tnm_generator_jobs():
    """
    Cron endpoint to process pending TNM generator jobs.
    Called by Vercel Cron every minute. Has 60s timeout (vs 10s for regular endpoints).

    Security: Vercel cron jobs include CRON_SECRET header.
    """
    import os
    from datetime import datetime
    from models import TNMGeneratorJob

    # Verify cron secret (Vercel sets this automatically)
    cron_secret = os.environ.get('CRON_SECRET')
    auth_header = request.headers.get('Authorization', '')

    if app.debug:
        # Allow in development without secret
        pass
    elif not cron_secret:
        # Production: CRON_SECRET must be configured
        logger.error("CRON_SECRET not configured — rejecting cron request")
        return jsonify({'error': 'Unauthorized'}), 401
    elif not auth_header.endswith(cron_secret):
        return jsonify({'error': 'Unauthorized'}), 401

    # Get oldest pending job
    job = TNMGeneratorJob.query.filter_by(status='pending').order_by(TNMGeneratorJob.created_at).first()

    if not job:
        return jsonify({'message': 'No pending jobs'}), 200

    try:
        # Mark as running
        job.status = 'running'
        job.started_at = datetime.utcnow()
        db.session.commit()

        logger.info(f"[TNM Cron] Processing job {job.job_id} for {job.slug}")

        # Generate the calculator
        from tnm_calculator.tnm_generator import generate_and_save_tnm_content
        import json

        special_features = []
        if job.special_features:
            try:
                special_features = json.loads(job.special_features)
            except:
                pass

        success, message, result_data = generate_and_save_tnm_content(
            db=db,
            slug=job.slug,
            cancer_name=job.cancer_name,
            body_section=job.body_section,
            staging_system=job.staging_system,
            special_features=special_features,
            description=job.description or '',
            special_notes=job.special_notes or '',
            user_id=job.created_by_user_id,
            overwrite=getattr(job, 'overwrite', False)  # Pass overwrite flag
        )

        if success:
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
            logger.info(f"[TNM Cron] Job {job.job_id} completed successfully")
        else:
            job.status = 'failed'
            job.error_message = message
            job.completed_at = datetime.utcnow()
            logger.error(f"[TNM Cron] Job {job.job_id} failed: {message}")

        db.session.commit()

        return jsonify({
            'job_id': job.job_id,
            'status': job.status,
            'message': message
        }), 200

    except Exception as e:
        logger.exception(f"[TNM Cron] Job {job.job_id} error: {e}")
        job.status = 'failed'
        job.error_message = str(e)
        job.completed_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'job_id': job.job_id,
            'status': 'failed',
            'error': str(e)
        }), 500


@app.route('/api/cron/data-retention-cleanup', methods=['GET', 'POST'])
def data_retention_cleanup():
    """
    Cron endpoint for GDPR data retention cleanup.
    Deletes expired recovery codes, approval codes, and stale TNM jobs.
    """
    from datetime import datetime, timedelta
    from models import AccountRecoveryCode, AdminApprovalCode, TNMGeneratorJob

    # Verify cron secret
    cron_secret = os.environ.get('CRON_SECRET')
    auth_header = request.headers.get('Authorization', '')
    if app.debug:
        pass
    elif not cron_secret:
        logger.error("CRON_SECRET not configured — rejecting cron request")
        return jsonify({'error': 'Unauthorized'}), 401
    elif not auth_header.endswith(cron_secret):
        return jsonify({'error': 'Unauthorized'}), 401

    now = datetime.utcnow()
    cleaned = {}

    try:
        # 1. Expired recovery codes (older than 7 days past expiry)
        cutoff_recovery = now - timedelta(days=7)
        expired_recovery = AccountRecoveryCode.query.filter(
            AccountRecoveryCode.expires_at < cutoff_recovery
        ).delete(synchronize_session=False)
        cleaned['expired_recovery_codes'] = expired_recovery

        # 2. Expired/used approval codes (older than 30 days past expiry)
        cutoff_approval = now - timedelta(days=30)
        expired_approvals = AdminApprovalCode.query.filter(
            AdminApprovalCode.expires_at < cutoff_approval
        ).delete(synchronize_session=False)
        cleaned['expired_approval_codes'] = expired_approvals

        # 3. Completed/failed TNM generator jobs older than 90 days
        cutoff_jobs = now - timedelta(days=90)
        old_jobs = TNMGeneratorJob.query.filter(
            TNMGeneratorJob.status.in_(['completed', 'failed']),
            TNMGeneratorJob.completed_at < cutoff_jobs
        ).delete(synchronize_session=False)
        cleaned['old_tnm_jobs'] = old_jobs

        db.session.commit()
        total = sum(cleaned.values())
        if total > 0:
            logger.info(f"[Data Retention] Cleaned {total} records: {cleaned}")
        return jsonify({'status': 'ok', 'cleaned': cleaned}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"[Data Retention] Cleanup error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/')
def index():
    """Smart dashboard - students see student dashboard, admins can access admin features"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('auth.login'))


@app.route('/privacy')
@app.route('/privacy-policy')
def privacy_policy():
    """Privacy Policy page - required for Notion OAuth and GDPR compliance"""
    return render_template('privacy_policy.html')


@app.route('/terms')
@app.route('/terms-of-use')
def terms_of_use():
    """Terms of Use page - required for legal compliance"""
    return render_template('terms_of_use.html')


@app.route('/about')
def about():
    """About page - app philosophy, design principles, and developer info"""
    return render_template('about.html')


@app.route('/essential-tnm-concepts')
def essential_tnm_concepts():
    """Essential TNM Concepts for Registrars - IARC guide embedded in iframe"""
    return render_template('essential_tnm_concepts.html')



@app.route('/cv')
def cv():
    """Curriculum Vitae page - black background, gold serif style"""
    return render_template('cv.html')


@app.route('/manifest.json')
def manifest():
    """Serve manifest.json with correct MIME type for PWA installation."""
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')


@app.route('/service-worker.js')
def service_worker():
    """Serve service-worker.js from root path for proper PWA scope."""
    response = send_from_directory('static', 'service-worker.js', mimetype='application/javascript')
    # Allow service worker to control pages at root scope
    response.headers['Service-Worker-Allowed'] = '/'
    return response


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


# ==================== SUGGEST A CASE: Student-powered case contribution ====================

@app.route('/suggest-case')
@login_required
def suggest_case():
    """Student-facing page for suggesting a new case."""
    return render_template('suggest_case.html')


def _normalize_diagnosis(text):
    """Normalize diagnosis text for similarity comparison: lowercase, strip laterality."""
    import re
    text = text.lower().strip()
    text = re.sub(r'^(right|left|bilateral|rt|lt|bilat)\s+', '', text)
    return text


def _find_similar_diagnoses(diagnosis_text, threshold=0.3, limit=5):
    """Find existing cases with similar diagnoses using pg_trgm similarity."""
    from sqlalchemy import text
    normalized = _normalize_diagnosis(diagnosis_text)
    if len(normalized) < 3:
        return []

    sql = text("""
        SELECT id, case_number, diagnosis, status,
               GREATEST(
                   similarity(lower(diagnosis), :normalized),
                   similarity(
                       regexp_replace(lower(diagnosis), '^(right|left|bilateral|rt|lt|bilat)\\s+', ''),
                       :normalized
                   )
               ) AS sim
        FROM "case"
        WHERE GREATEST(
                  similarity(lower(diagnosis), :normalized),
                  similarity(
                      regexp_replace(lower(diagnosis), '^(right|left|bilateral|rt|lt|bilat)\\s+', ''),
                      :normalized
                  )
              ) > :threshold
        ORDER BY sim DESC
        LIMIT :lim
    """)
    rows = db.session.execute(sql, {
        'normalized': normalized,
        'threshold': threshold,
        'lim': limit
    }).fetchall()

    results = []
    for r in rows:
        # Raw SQL returns status as string (PostgreSQL enum value)
        status_str = r.status.value if hasattr(r.status, 'value') else str(r.status)
        results.append({
            'id': r.id,
            'case_number': r.case_number,
            'diagnosis': r.diagnosis,
            'status': status_str,
            'similarity': round(float(r.sim), 3)
        })
    return results


@app.route('/api/diagnoses/similar')
@login_required
def get_similar_diagnoses():
    """Find existing cases with similar diagnoses (pg_trgm fuzzy matching)."""
    q = (request.args.get('q') or '').strip()
    if len(q) < 3:
        return jsonify([])

    try:
        threshold = float(request.args.get('threshold', 0.3))
    except (ValueError, TypeError):
        threshold = 0.3

    threshold = max(0.1, min(threshold, 0.9))

    try:
        results = _find_similar_diagnoses(q, threshold=threshold)
        return jsonify(results)
    except Exception as e:
        # pg_trgm extension may not be enabled
        logger.error(f"Similar diagnoses query failed: {e}")
        return jsonify([])


@app.route('/api/suggest-case/create', methods=['POST'])
@login_required
def create_suggested_case():
    """Create a case as a student suggestion (always DRAFT status)."""
    from models import FRCRModule, BodyPart, AgeGroup, CaseStatus
    import re

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    diagnosis = (data.get('diagnosis') or '').strip()
    if not diagnosis:
        return jsonify({'error': 'Diagnosis is required'}), 400
    if not data.get('module'):
        return jsonify({'error': 'Module is required'}), 400
    if not data.get('body_part'):
        return jsonify({'error': 'Body Part is required'}), 400

    # Duplicate check (soft guard): warn if similar published/reviewed case exists
    if not data.get('confirmed'):
        try:
            similar = _find_similar_diagnoses(diagnosis, threshold=0.5)
            # Only flag published or pending_review cases
            flagged = [s for s in similar if s['status'] in ('published', 'pending_review')]
            if flagged:
                return jsonify({
                    'needs_confirmation': True,
                    'similar_cases': flagged
                })
        except Exception:
            pass  # Don't block creation if similarity check fails

    try:
        module_enum = FRCRModule[data['module']]
    except KeyError:
        return jsonify({'error': 'Invalid module'}), 400
    try:
        body_part_enum = BodyPart[data['body_part']]
    except KeyError:
        return jsonify({'error': 'Invalid body part'}), 400

    age_group_enum = None
    if data.get('age_group'):
        try:
            age_group_enum = AgeGroup[data['age_group']]
        except KeyError:
            pass

    # Rate limit: max 5 DRAFT cases per student
    draft_count = Case.query.filter_by(
        created_by_user_id=current_user.id,
        status=CaseStatus.DRAFT
    ).count()
    if draft_count >= 5:
        return jsonify({'error': 'You have 5 draft cases. Please submit or delete existing drafts before creating more.'}), 429

    # Auto-generate case_number
    short_code = data['body_part'].replace('_', '').upper()[:6]
    prefix = f"{short_code}-"
    existing = Case.query.filter(
        Case.body_part == body_part_enum,
        Case.case_number.ilike(f"{prefix}%")
    ).all()
    max_num = 0
    for c in existing:
        if c.case_number:
            match = re.search(r'-(\d+)$', c.case_number)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
    case_number = f"{prefix}{max_num + 1:03d}"

    # Contributor name for attribution (falls back to user's full_name)
    contributor_name = (data.get('contributor_name') or '').strip() or current_user.full_name

    try:
        case = Case(
            case_number=case_number,
            diagnosis=diagnosis,
            module=module_enum,
            body_part=body_part_enum,
            age_group=age_group_enum,
            status=CaseStatus.DRAFT,
            is_public=False,
            created_by_user_id=current_user.id,
            contributor_name=contributor_name
        )
        db.session.add(case)
        db.session.commit()
        return jsonify({'success': True, 'case_id': case.id, 'case_number': case.case_number})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create case: {str(e)}'}), 500


@app.route('/api/case/<int:case_id>/contributor-notes', methods=['PUT'])
@login_required
def update_contributor_notes(case_id):
    """Save student Additional Insights for a case."""
    case = verify_case_ownership(case_id)
    if not case:
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json() or {}
    case.contributor_notes = (data.get('notes') or '').strip()
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/case/<int:case_id>/submit-for-review', methods=['POST'])
@login_required
def submit_case_for_review(case_id):
    """Submit a student-suggested case for admin review."""
    from models import CaseStatus, CaseApprovalQueue

    case = Case.query.get(case_id)
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    if case.created_by_user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    if case.status != CaseStatus.DRAFT:
        return jsonify({'error': 'Only draft cases can be submitted for review'}), 400

    case.status = CaseStatus.PENDING_REVIEW

    # Create approval queue entry (upsert — ignore if already exists)
    existing_entry = CaseApprovalQueue.query.filter_by(case_id=case.id).first()
    if not existing_entry:
        queue_entry = CaseApprovalQueue(
            case_id=case.id,
            submitted_by_user_id=current_user.id
        )
        db.session.add(queue_entry)

    db.session.commit()

    # Send email notification to admin (best effort)
    try:
        from auth import send_case_review_notification
        send_case_review_notification(case, current_user)
    except Exception as e:
        logger.warning(f"Email notification failed: {e}")

    return jsonify({'success': True, 'message': 'Case submitted for review. Thank you!'})


@app.route('/api/my-suggested-cases')
@login_required
def get_my_suggested_cases():
    """Get all cases created by the current user."""
    from models import CaseStatus
    cases = Case.query.filter_by(
        created_by_user_id=current_user.id
    ).order_by(Case.created_at.desc()).all()

    return jsonify([{
        'id': c.id,
        'diagnosis': c.diagnosis,
        'module': c.module.value if c.module else None,
        'status': c.status.value if c.status else 'draft',
        'created_at': c.created_at.isoformat() if c.created_at else None,
        'image_count': len(c.images) if c.images else 0,
    } for c in cases])


# ==================== STUDENT REVISION: BALANCED REVISION ====================
# This section implements the balanced revision feature for students
# CRITICAL: Does NOT interfere with examiner workflows

@app.route('/revision/start-balanced')
@login_required
def start_balanced_revision():
    """
    Start a new balanced revision session.
    Selects 6 random cases from each FRCR module (36 total cases).
    Prioritizes cases the user hasn't seen or has seen least recently.
    """
    from models import FRCRModule, Case, RevisionSession, RevisionHistory
    import json
    from sqlalchemy import func
    
    
    try:
        # Get all FRCR modules
        all_modules = list(FRCRModule)
        selected_case_ids = []
        
        # For each module, select 6 cases
        for module in all_modules:
            
            # Strategy: Get cases with LEFT JOIN to revision_history
            # Priority: unseen > least recently seen > random
            
            # Subquery: Get last_seen_at for each case for this user
            seen_subquery = db.session.query(
                RevisionHistory.case_id,
                func.max(RevisionHistory.last_seen_at).label('last_seen')
            ).filter(
                RevisionHistory.user_id == current_user.id
            ).group_by(RevisionHistory.case_id).subquery()
            
            # Main query: Get public cases for this module
            # LEFT JOIN with history to get seen status
            # Order by: NULL last_seen first (unseen), then oldest last_seen, then random
            cases = db.session.query(Case).filter(
                Case.is_public == True,
                Case.module == module
            ).outerjoin(
                seen_subquery,
                Case.id == seen_subquery.c.case_id
            ).order_by(
                seen_subquery.c.last_seen.asc().nullsfirst(),  # Unseen first
                func.random()  # Then random among same category
            ).limit(6).all()
            
            case_ids_for_module = [c.id for c in cases]
            selected_case_ids.extend(case_ids_for_module)
        
        # Check if we have enough cases
        if len(selected_case_ids) == 0:
            flash('Enough public cases not available for revision at presemt.', 'warning')
            return redirect(url_for('dashboard'))
        
        # Show warning if we have fewer than expected
        if len(selected_case_ids) < 36:
            flash(f'Started revision with {len(selected_case_ids)} available cases. Some modules need more cases for full coverage.', 'info')
        
        
        # Create new revision session
        revision_session = RevisionSession(
            user_id=current_user.id,
            case_ids='[]',  # Will be set below
            current_case_index=0
        )
        revision_session.set_case_ids_list(selected_case_ids)
        
        db.session.add(revision_session)
        db.session.commit()
        
        
        # Redirect to first case
        if selected_case_ids:
            first_case_id = selected_case_ids[0]
            flash(f'Started balanced revision session with {len(selected_case_ids)} cases!', 'success')
            return redirect(url_for('view_revision_case', session_id=revision_session.id, case_index=0))
        else:
            flash('No cases available for revision.', 'warning')
            return redirect(url_for('dashboard'))
    
    except Exception as e:
        db.session.rollback()
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


# ==================== RADIOLOGY PROTOCOLS (USER-FACING) ====================


@app.route('/radiology-protocols')
@login_required
def radiology_protocols_index():
    """User-facing browse page for clinical protocols."""
    protocols = ClinicalProtocol.query.filter_by(is_published=True).order_by(ClinicalProtocol.title).all()
    grouped = {}
    for p in protocols:
        cat = p.category or 'Other'
        grouped.setdefault(cat, []).append(p)
    return render_template('radiology_protocols_user.html', grouped=grouped, protocols=protocols)


@app.route('/radiology-protocols/api/search')
@login_required
def radiology_protocols_search():
    """Search published clinical protocols."""
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    protocols = ClinicalProtocol.query.filter(
        ClinicalProtocol.is_published == True,
        db.or_(
            ClinicalProtocol.title.ilike(f'%{q}%'),
            ClinicalProtocol.keywords.ilike(f'%{q}%'),
        )
    ).order_by(ClinicalProtocol.title).limit(20).all()
    return jsonify([{
        'id': p.id, 'title': p.title, 'category': p.category,
        'url': f'/on-call-helper/protocol/{p.id}'
    } for p in protocols])


# ==================== SPACED REPETITION STUDY SYSTEM ====================


@app.route('/study')
@login_required
def study_dashboard():
    """Study dashboard with stats and module breakdown."""
    from models import FRCRModule, Case, Question, CaseStatus
    from sqlalchemy import func, case as sql_case
    from datetime import date

    user_id = current_user.id
    today = date.today()

    # Overall stats
    total_progress = UserQAProgress.query.filter_by(user_id=user_id).count()

    due_today = UserQAProgress.query.filter(
        UserQAProgress.user_id == user_id,
        UserQAProgress.next_review_date <= today
    ).count()

    mastered = UserQAProgress.query.filter(
        UserQAProgress.user_id == user_id,
        UserQAProgress.repetition_number >= 5,
        UserQAProgress.interval_days >= 21
    ).count()

    learning = UserQAProgress.query.filter(
        UserQAProgress.user_id == user_id,
        UserQAProgress.repetition_number < 5
    ).count()

    total_correct = db.session.query(func.sum(UserQAProgress.times_correct)).filter(
        UserQAProgress.user_id == user_id
    ).scalar() or 0
    total_incorrect = db.session.query(func.sum(UserQAProgress.times_incorrect)).filter(
        UserQAProgress.user_id == user_id
    ).scalar() or 0
    total_attempts = total_correct + total_incorrect
    accuracy_percent = round((total_correct / total_attempts * 100), 1) if total_attempts > 0 else 0

    # Per-module breakdown
    module_stats = db.session.query(
        Case.module,
        func.count(UserQAProgress.id).label('total'),
        func.sum(sql_case((UserQAProgress.next_review_date <= today, 1), else_=0)).label('due'),
        func.sum(sql_case(
            ((UserQAProgress.repetition_number >= 5) & (UserQAProgress.interval_days >= 21), 1),
            else_=0
        )).label('mastered')
    ).join(Case, UserQAProgress.case_id == Case.id).filter(
        UserQAProgress.user_id == user_id
    ).group_by(Case.module).all()

    modules_data = []
    for module, total, due_count, mastered_count in module_stats:
        if module:
            modules_data.append({
                'module': module,
                'module_name': module.value,
                'total': total or 0,
                'due': due_count or 0,
                'mastered': mastered_count or 0,
                'progress_percent': round(((mastered_count or 0) / total * 100), 1) if total else 0
            })
    modules_data.sort(key=lambda x: list(FRCRModule).index(x['module']))

    # Total available Q&A pairs (published cases)
    total_qa = db.session.query(func.count(Question.id)).join(
        Case, Question.case_id == Case.id
    ).filter(Case.status == CaseStatus.PUBLISHED).scalar() or 0
    new_cards_available = max(0, total_qa - total_progress)

    # All modules with published Q&A pairs (for dropdown — works for new users too)
    available_modules = db.session.query(
        Case.module,
        func.count(Question.id).label('qa_count')
    ).join(
        Question, Question.case_id == Case.id
    ).filter(
        Case.status == CaseStatus.PUBLISHED,
        Case.module.isnot(None)
    ).group_by(Case.module).all()

    all_modules = []
    for module, qa_count in available_modules:
        # Find due count from modules_data if available
        md = next((m for m in modules_data if m['module'] == module), None)
        due_count = md['due'] if md else 0
        all_modules.append({
            'module': module,
            'module_name': module.value,
            'qa_count': qa_count,
            'due': due_count,
        })
    all_modules.sort(key=lambda x: list(FRCRModule).index(x['module']))

    return render_template('study.html',
                           due_today=due_today,
                           mastered=mastered,
                           learning=learning,
                           accuracy_percent=accuracy_percent,
                           total_progress=total_progress,
                           new_cards_available=new_cards_available,
                           modules_data=modules_data,
                           all_modules=all_modules)


@app.route('/study/session')
@login_required
def study_session():
    """Flashcard study session page."""
    from models import FRCRModule

    module_param = request.args.get('module')
    selected_module = None
    if module_param:
        try:
            selected_module = FRCRModule[module_param]
        except KeyError:
            flash('Invalid module selected', 'warning')
            return redirect(url_for('study_dashboard'))

    return render_template('study_session.html',
                           selected_module=selected_module,
                           modules=list(FRCRModule))


def _strip_html_tags(text):
    """Strip HTML tags from text, returning plain text content."""
    if not text:
        return text
    import re
    return re.sub(r'<[^>]+>', '', text).strip()


@app.route('/api/study/cards', methods=['GET'])
@login_required
def get_study_cards():
    """Get next batch of cards for study session (due first, then new)."""
    from models import Question, Answer, Case, FRCRModule, CaseStatus
    from sqlalchemy import func
    from datetime import date

    user_id = current_user.id
    today = date.today()
    module_param = request.args.get('module')
    limit = min(int(request.args.get('limit', 20)), 50)

    selected_module = None
    if module_param:
        try:
            selected_module = FRCRModule[module_param]
        except KeyError:
            return jsonify({'error': 'Invalid module'}), 400

    cards = []

    # 1) Due cards (most overdue first)
    due_query = db.session.query(
        Question.id.label('question_id'),
        Question.question_text,
        Question.case_id,
        Answer.answer_text,
        Case.diagnosis,
        Case.module,
        UserQAProgress.repetition_number,
        UserQAProgress.interval_days
    ).join(
        Answer, (Answer.case_id == Question.case_id) & (Answer.answer_number == Question.question_number)
    ).join(
        Case, Question.case_id == Case.id
    ).join(
        UserQAProgress, (UserQAProgress.question_id == Question.id) & (UserQAProgress.user_id == user_id)
    ).filter(
        Case.status == CaseStatus.PUBLISHED,
        UserQAProgress.next_review_date <= today
    )
    if selected_module:
        due_query = due_query.filter(Case.module == selected_module)
    due_query = due_query.order_by(UserQAProgress.next_review_date.asc())
    due_cards = due_query.limit(limit).all()

    for c in due_cards:
        cards.append({
            'question_id': c.question_id,
            'question_text': _strip_html_tags(c.question_text),
            'answer_text': _strip_html_tags(c.answer_text),
            'case_id': c.case_id,
            'diagnosis': c.diagnosis,
            'module': c.module.value if c.module else None,
            'is_new': False,
            'repetition_number': c.repetition_number,
            'interval_days': c.interval_days,
        })

    # 2) New cards (fill remaining)
    remaining = limit - len(cards)
    if remaining > 0:
        started_ids = db.session.query(UserQAProgress.question_id).filter(
            UserQAProgress.user_id == user_id
        ).subquery()

        new_query = db.session.query(
            Question.id.label('question_id'),
            Question.question_text,
            Question.case_id,
            Answer.answer_text,
            Case.diagnosis,
            Case.module,
        ).join(
            Answer, (Answer.case_id == Question.case_id) & (Answer.answer_number == Question.question_number)
        ).join(
            Case, Question.case_id == Case.id
        ).filter(
            Case.status == CaseStatus.PUBLISHED,
            Question.id.notin_(started_ids)
        )
        if selected_module:
            new_query = new_query.filter(Case.module == selected_module)
        new_query = new_query.order_by(func.random())
        new_cards = new_query.limit(remaining).all()

        for c in new_cards:
            cards.append({
                'question_id': c.question_id,
                'question_text': _strip_html_tags(c.question_text),
                'answer_text': _strip_html_tags(c.answer_text),
                'case_id': c.case_id,
                'diagnosis': c.diagnosis,
                'module': c.module.value if c.module else None,
                'is_new': True,
                'repetition_number': 0,
                'interval_days': 0,
            })

    return jsonify({
        'cards': cards,
        'total_returned': len(cards),
        'due_count': len([c for c in cards if not c['is_new']]),
        'new_count': len([c for c in cards if c['is_new']]),
    })


@app.route('/api/study/answer', methods=['POST'])
@login_required
def record_study_answer():
    """Record answer and update SM-2 schedule."""
    from models import Question
    from sm2_algorithm import update_progress_on_answer
    from datetime import date

    data = request.get_json()
    question_id = data.get('question_id')
    quality = data.get('quality')

    if not question_id or quality is None:
        return jsonify({'error': 'Missing required fields'}), 400
    if quality not in [0, 1, 2]:
        return jsonify({'error': 'Quality must be 0, 1, or 2'}), 400

    question = Question.query.get(question_id)
    if not question:
        return jsonify({'error': 'Question not found'}), 404

    progress = UserQAProgress.query.filter_by(
        user_id=current_user.id, question_id=question_id
    ).first()

    if not progress:
        progress = UserQAProgress(
            user_id=current_user.id,
            question_id=question_id,
            case_id=question.case_id,
            ease_factor=2.5,
            interval_days=0,
            repetition_number=0,
            next_review_date=date.today(),
            times_correct=0,
            times_incorrect=0,
        )
        db.session.add(progress)

    update_progress_on_answer(progress, quality)
    db.session.commit()

    today = date.today()
    due_remaining = UserQAProgress.query.filter(
        UserQAProgress.user_id == current_user.id,
        UserQAProgress.next_review_date <= today
    ).count()
    mastered_total = UserQAProgress.query.filter(
        UserQAProgress.user_id == current_user.id,
        UserQAProgress.repetition_number >= 5,
        UserQAProgress.interval_days >= 21
    ).count()

    return jsonify({
        'success': True,
        'next_review_date': progress.next_review_date.isoformat(),
        'interval_days': progress.interval_days,
        'repetition_number': progress.repetition_number,
        'stats': {'due_today': due_remaining, 'mastered': mastered_total},
    })


@app.route('/api/study/stats', methods=['GET'])
@login_required
def get_study_stats():
    """Get overall study statistics for current user."""
    from sqlalchemy import func
    from datetime import date

    user_id = current_user.id
    today = date.today()

    total_progress = UserQAProgress.query.filter_by(user_id=user_id).count()
    due_today = UserQAProgress.query.filter(
        UserQAProgress.user_id == user_id,
        UserQAProgress.next_review_date <= today
    ).count()
    mastered = UserQAProgress.query.filter(
        UserQAProgress.user_id == user_id,
        UserQAProgress.repetition_number >= 5,
        UserQAProgress.interval_days >= 21
    ).count()
    learning = UserQAProgress.query.filter(
        UserQAProgress.user_id == user_id,
        UserQAProgress.repetition_number < 5
    ).count()
    total_correct = db.session.query(func.sum(UserQAProgress.times_correct)).filter(
        UserQAProgress.user_id == user_id
    ).scalar() or 0
    total_incorrect = db.session.query(func.sum(UserQAProgress.times_incorrect)).filter(
        UserQAProgress.user_id == user_id
    ).scalar() or 0
    total_attempts = total_correct + total_incorrect
    accuracy_percent = round((total_correct / total_attempts * 100), 1) if total_attempts > 0 else 0

    return jsonify({
        'total_progress': total_progress,
        'due_today': due_today,
        'mastered': mastered,
        'learning': learning,
        'accuracy_percent': accuracy_percent,
    })


@app.route('/modules')
@login_required
def modules_view():
    """Display all FRCR modules"""
    from models import FRCRModule, Case, AgeGroup
    from sqlalchemy import or_

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
        if module == FRCRModule.PAEDIATRIC:
            case_count = Case.query.filter(
                Case.is_public == True,
                or_(Case.module == module, Case.age_group == AgeGroup.PEDIATRIC)
            ).count()
        else:
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
    """Show cases filtered by module"""
    from models import FRCRModule, BodyPart, Case, CandidateNote, AgeGroup
    from sqlalchemy import or_

    # Validate module
    try:
        module_enum = FRCRModule[module]
    except KeyError:
        return redirect(url_for('modules_view'))

    # Get filters from query params
    body_part_filter = request.args.get('body_part', '')
    search_query = request.args.get('q', '')

    # Build query — PAEDIATRIC module also includes cases with age_group=PEDIATRIC
    if module_enum == FRCRModule.PAEDIATRIC:
        query = Case.query.filter(
            Case.is_public == True,
            or_(Case.module == module_enum, Case.age_group == AgeGroup.PEDIATRIC)
        )
    else:
        query = Case.query.filter_by(module=module_enum, is_public=True)
    
    if body_part_filter:
        try:
            body_part_enum = BodyPart[body_part_filter]
            query = query.filter_by(body_part=body_part_enum)
        except KeyError:
            pass
    
    if search_query:
        query = query.filter(Case.diagnosis.ilike(f'%{search_query}%'))
    
    cases = query.order_by(Case.id).all()
    
    # Prepare case data
    cases_data = []
    for case in cases:
        # Check if user has notes
        has_notes = CandidateNote.query.filter_by(case_id=case.id, user_id=current_user.id).first() is not None
        
        cases_data.append({
            'id': case.id,
            'diagnosis': case.diagnosis,
            'module_display': case.module.value if case.module else 'N/A',
            'body_part_display': case.body_part.value if case.body_part else 'N/A',
            'image_count': len(case.images),
            'has_notes': has_notes,
            'is_public': case.is_public
        })
    
    # Get all body parts for filter
    body_parts = [{'value': bp.name, 'display_name': bp.value} for bp in BodyPart]
    
    return render_template('cases_list.html',
                         cases=cases_data,
                         module_filter=module_enum.value,
                         module_name=module_enum.name,  # Pass enum name for URL building
                         body_parts=body_parts,
                         body_part_selected=body_part_filter,
                         search_query=search_query,
                         list_source='module')


@app.route('/cases')
@login_required
def all_cases_view():
    if getattr(current_user, 'role', None) == UserRole.STUDENT:
        return redirect(url_for('student_cases_list'))
    from models import BodyPart, AgeGroup, FRCRModule, CaseStatus, CandidateNote, ImportedCaseStaging

    module_filter = request.args.get('module', '')
    body_part_filter = request.args.get('body_part', '')
    age_group_filter = request.args.get('age_group', '')
    status_filter = request.args.get('status', '')
    search_query = request.args.get('q', '')

    query = Case.query

    if module_filter:
        try:
            module_enum = FRCRModule[module_filter]
            query = query.filter_by(module=module_enum)
        except KeyError:
            module_filter = ''

    if body_part_filter:
        try:
            body_part_enum = BodyPart[body_part_filter]
            query = query.filter_by(body_part=body_part_enum)
        except KeyError:
            body_part_filter = ''

    if age_group_filter:
        try:
            age_group_enum = AgeGroup[age_group_filter]
            query = query.filter_by(age_group=age_group_enum)
        except KeyError:
            age_group_filter = ''

    if status_filter:
        try:
            status_enum = CaseStatus[status_filter]
            query = query.filter_by(status=status_enum)
        except KeyError:
            status_filter = ''

    if search_query:
        query = query.filter(Case.diagnosis.ilike(f'%{search_query}%'))

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 200)
    pagination = query.order_by(Case.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    cases = pagination.items

    cases_data = []
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

    body_parts = [{'value': bp.name, 'display_name': bp.value} for bp in BodyPart]
    age_groups = [{'value': ag.name, 'display_name': ag.value} for ag in AgeGroup]
    all_modules = [{'value': m.name, 'display_name': m.value} for m in FRCRModule]
    status_options = [{'value': s.name, 'display_name': s.value} for s in CaseStatus]
    pending_staging_count = ImportedCaseStaging.query.filter_by(enrichment_status='pending').count()

    return render_template('cases_list.html',
                           cases=cases_data,
                           module_filter=module_filter,
                           module_name=module_filter,  # In admin view, module_filter is already the enum name
                           module_selected=module_filter,
                           all_modules=all_modules,
                           body_parts=body_parts,
                           body_part_selected=body_part_filter,
                           age_groups=age_groups,
                           age_group_selected=age_group_filter,
                           status_options=status_options,
                           status_selected=status_filter,
                           pending_staging_count=pending_staging_count,
                           search_query=search_query,
                           list_source='admin',
                           pagination=pagination,
                           page=page,
                           per_page=per_page)


@app.route('/student-cases')
@login_required
def student_cases_list():
    from models import BodyPart, AgeGroup, FRCRModule, CandidateNote, CaseFlag, CaseStatus
    from sqlalchemy import or_

    module_filter = request.args.get('module', '')
    body_part_filter = request.args.get('body_part', '')
    age_group_filter = request.args.get('age_group', '')
    search_query = request.args.get('q', '')
    flagged_filter = request.args.get('flagged') == '1'

    query = Case.query.filter_by(status=CaseStatus.PUBLISHED)

    if module_filter:
        try:
            module_enum = FRCRModule[module_filter]
            if module_enum == FRCRModule.PAEDIATRIC:
                query = query.filter(
                    or_(Case.module == module_enum, Case.age_group == AgeGroup.PEDIATRIC)
                )
            else:
                query = query.filter_by(module=module_enum)
        except KeyError:
            module_filter = ''

    if body_part_filter:
        try:
            body_part_enum = BodyPart[body_part_filter]
            query = query.filter_by(body_part=body_part_enum)
        except KeyError:
            body_part_filter = ''

    if age_group_filter:
        try:
            age_group_enum = AgeGroup[age_group_filter]
            query = query.filter_by(age_group=age_group_enum)
        except KeyError:
            age_group_filter = ''

    if search_query:
        query = query.filter(Case.diagnosis.ilike(f'%{search_query}%'))

    if flagged_filter:
        query = query.join(CaseFlag).filter(CaseFlag.user_id == current_user.id)

    cases = query.order_by(Case.id.desc()).all()

    cases_data = []
    for case in cases:
        has_notes = CandidateNote.query.filter_by(case_id=case.id, user_id=current_user.id).first() is not None
        flagged = CaseFlag.query.filter_by(case_id=case.id, user_id=current_user.id).first() is not None
        cases_data.append({
            'id': case.id,
            'diagnosis': case.diagnosis,
            'module_display': case.module.value if case.module else 'N/A',
            'body_part_display': case.body_part.value if case.body_part else 'N/A',
            'age_group_display': case.age_group.value if case.age_group else 'N/A',
            'image_count': len(case.images),
            'has_notes': has_notes,
            'flagged': flagged,
            'is_public': case.is_public
        })

    body_parts = [{'value': bp.name, 'display_name': bp.value} for bp in BodyPart]
    age_groups = [{'value': ag.name, 'display_name': ag.value} for ag in AgeGroup]
    all_modules = [{'value': m.name, 'display_name': m.value} for m in FRCRModule]

    return render_template('student_cases_list.html',
                           cases=cases_data,
                           module_filter=module_filter,
                           module_name=module_filter,  # In student view, module_filter is already the enum name
                           module_selected=module_filter,
                           all_modules=all_modules,
                           body_parts=body_parts,
                           body_part_selected=body_part_filter,
                           age_groups=age_groups,
                           age_group_selected=age_group_filter,
                           search_query=search_query,
                           flagged_filter=flagged_filter,
                           list_source='student')


@app.route('/student/cases/<int:case_id>/flag', methods=['POST'])
@login_required
def flag_case(case_id):
    from models import CaseFlag, CaseStatus

    if getattr(current_user, 'role', None) != UserRole.STUDENT:
        return jsonify({'error': 'Only students can flag cases'}), 403

    case = Case.query.get(case_id)
    if not case or case.status != CaseStatus.PUBLISHED:
        return jsonify({'error': 'Case not found or not public'}), 404

    existing = CaseFlag.query.filter_by(user_id=current_user.id, case_id=case_id).first()
    if existing:
        return jsonify({'success': True, 'message': 'Case already flagged'}), 200

    flag = CaseFlag(user_id=current_user.id, case_id=case_id)
    db.session.add(flag)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/student/cases/<int:case_id>/unflag', methods=['POST'])
@login_required
def unflag_case(case_id):
    from models import CaseFlag

    if getattr(current_user, 'role', None) != UserRole.STUDENT:
        return jsonify({'error': 'Only students can unflag cases'}), 403

    flag = CaseFlag.query.filter_by(user_id=current_user.id, case_id=case_id).first()
    if not flag:
        return jsonify({'success': True, 'message': 'Case not flagged'}), 200

    db.session.delete(flag)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/profile')
@login_required
def student_profile():
    """Student profile page"""
    return render_template('profile.html')


@app.route('/admin')
@login_required
def admin_dashboard():
    """Admin dashboard - only accessible to admins"""
    if current_user.role != UserRole.ADMIN:
        return redirect(url_for('dashboard'))
    return render_template('admin_dashboard.html')


@app.route('/admin/staging-cases')
@login_required
def review_staging_cases():
    """Review and manage staging cases - ADMIN ONLY"""
    from models import ImportedCaseStaging
    
    if current_user.role != UserRole.ADMIN:
        return redirect(url_for('dashboard'))
    
    # Get status filter from query params
    status_filter = request.args.get('status', '')
    
    # Build query
    query = ImportedCaseStaging.query
    
    if status_filter == 'pending':
        query = query.filter(ImportedCaseStaging.enrichment_status == 'pending')
    elif status_filter == 'enriched':
        query = query.filter(ImportedCaseStaging.enrichment_status == 'enriched')
    elif status_filter == 'rejected':
        query = query.filter(ImportedCaseStaging.enrichment_status == 'rejected')
    
    # Get counts
    pending_count = ImportedCaseStaging.query.filter_by(enrichment_status='pending').count()
    enriched_count = ImportedCaseStaging.query.filter_by(enrichment_status='enriched').count()
    rejected_count = ImportedCaseStaging.query.filter_by(enrichment_status='rejected').count()
    
    # Get cases ordered by created_at desc
    cases = query.order_by(ImportedCaseStaging.created_at.desc()).all()
    
    return render_template('staging_cases_list.html',
                         cases=cases,
                         status_filter=status_filter,
                         pending_count=pending_count,
                         enriched_count=enriched_count,
                         rejected_count=rejected_count)


@app.route('/case-list')
@login_required
def case_list():
    """Case management page - list, create, edit, delete cases"""
    if current_user.role not in [UserRole.ADMIN, UserRole.CONTENT_MANAGER]:
        return redirect(url_for('dashboard'))
    return render_template('case_list.html')


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

    from models import AgeGroup, CaseStatus
    age_group_enum = None
    if data.get('age_group'):
        try:
            age_group_enum = AgeGroup[data['age_group']]
        except KeyError:
            pass

    status_enum = CaseStatus.DRAFT
    if data.get('status'):
        try:
            status_enum = CaseStatus[data['status']]
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
    
    # Create case (questions/answers are stored in separate tables now)
    try:
        # Add footer to discussion if it has content
        discussion = data.get('discussion', '')
        if discussion:
            footer = '''<!-- Footer -->
<div style="background: #f3f4f6; padding: 12px 16px; border-top: 1px solid #e5e7eb; margin-top: 20px; border-radius: 0 0 8px 8px;">
    <div style="display: flex; align-items: center; justify-content: flex-end; gap: 8px;">
        <img style="width: 30px; height: 30px; object-fit: contain;" src="https://res.cloudinary.com/dx7b7chvn/image/upload/v1769503548/frcr-rev-logo-transp_o2hmrq.png" alt="RadiologyInsights Logo">
        <span style="font-size: 0.85em; color: #6b7280;">&copy; All rights reserved RadiologyInsights</span>
    </div>
</div>'''
            discussion = f"{discussion}\n{footer}"
        
        case = Case(
            case_number=case_number,
            diagnosis=data['diagnosis'],
            discussion=discussion,
            module=module_enum,
            body_part=body_part_enum,
            age_group=age_group_enum,
            status=status_enum,
            calculator_slug=data.get('calculator_slug') or None,
            is_public=data.get('is_public', False),
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
                    question = Question(
                        case_id=case.id,
                        question_number=index,
                        question_text=question_text
                    )
                    db.session.add(question)
                
                # Create answer if it has content
                if answer_text:
                    answer = Answer(
                        case_id=case.id,
                        answer_number=index,
                        answer_text=answer_text
                    )
                    db.session.add(answer)
        
        db.session.commit()
        
        return jsonify({'success': True, 'id': case.id, 'case_id': case.id, 'message': 'Case created'})
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to create case: {str(e)}'}), 500


def get_module_enum_by_name_or_value(module_str):
    """Helper to find FRCRModule enum by name or display value"""
    from models import FRCRModule
    if not module_str:
        return None
    # Try by name first (e.g., "NEURORADIOLOGY")
    try:
        return FRCRModule[module_str]
    except KeyError:
        pass
    # Try by value (e.g., "Neuroradiology")
    for m in FRCRModule:
        if m.value == module_str:
            return m
    return None


def get_case_navigation_context(case_id, list_source, filters):
    """
    Compute previous and next case IDs based on the list source and filters.
    Uses same ordering as each list view for consistent navigation.
    Returns (prev_case_id, next_case_id, nav_params)
    """
    from models import FRCRModule, BodyPart, AgeGroup, CaseStatus, ImportedCaseStaging, CaseFlag
    
    prev_case_id = None
    next_case_id = None
    case_ids = []
    
    # Build nav_params to preserve context in links
    nav_params = {'list_source': list_source}
    nav_params.update(filters)
    
    try:
        if list_source == 'staging':
            # Staging cases don't link directly to view_case
            return None, None, nav_params
            
        elif list_source == 'student':
            # Student cases list - only published, ordered by id DESC (newest first)
            query = Case.query.filter_by(status=CaseStatus.PUBLISHED)
            
            module_enum = get_module_enum_by_name_or_value(filters.get('module'))
            if module_enum:
                query = query.filter_by(module=module_enum)
            
            if filters.get('body_part'):
                try:
                    bp_enum = BodyPart[filters['body_part']]
                    query = query.filter_by(body_part=bp_enum)
                except KeyError:
                    pass
            if filters.get('age_group'):
                try:
                    ag_enum = AgeGroup[filters['age_group']]
                    query = query.filter_by(age_group=ag_enum)
                except KeyError:
                    pass
            if filters.get('q'):
                query = query.filter(Case.diagnosis.ilike(f"%{filters['q']}%"))
            
            # Match student_cases_list ordering: Case.id.desc()
            case_ids = [c.id for c in query.order_by(Case.id.desc()).all()]
            
        elif list_source == 'admin':
            # Admin cases list - all cases, ordered by id DESC (newest first)
            query = Case.query
            
            module_enum = get_module_enum_by_name_or_value(filters.get('module'))
            if module_enum:
                query = query.filter_by(module=module_enum)
            
            if filters.get('body_part'):
                try:
                    bp_enum = BodyPart[filters['body_part']]
                    query = query.filter_by(body_part=bp_enum)
                except KeyError:
                    pass
            if filters.get('age_group'):
                try:
                    ag_enum = AgeGroup[filters['age_group']]
                    query = query.filter_by(age_group=ag_enum)
                except KeyError:
                    pass
            if filters.get('status'):
                try:
                    status_enum = CaseStatus[filters['status']]
                    query = query.filter_by(status=status_enum)
                except KeyError:
                    pass
            if filters.get('q'):
                query = query.filter(Case.diagnosis.ilike(f"%{filters['q']}%"))
            
            # Match all_cases_view ordering: Case.id.desc()
            case_ids = [c.id for c in query.order_by(Case.id.desc()).all()]
            
        elif list_source == 'module':
            # Module-specific list - public cases, ordered by id ASC
            module_enum = get_module_enum_by_name_or_value(filters.get('module'))
            if module_enum:
                query = Case.query.filter_by(module=module_enum, is_public=True)
                
                if filters.get('body_part'):
                    try:
                        bp_enum = BodyPart[filters['body_part']]
                        query = query.filter_by(body_part=bp_enum)
                    except KeyError:
                        pass
                if filters.get('q'):
                    query = query.filter(Case.diagnosis.ilike(f"%{filters['q']}%"))
                
                # Match cases_by_module ordering: Case.id (ascending)
                case_ids = [c.id for c in query.order_by(Case.id).all()]
        else:
            # Default: match user role's default list ordering
            is_student = getattr(current_user, 'role', None) == UserRole.STUDENT
            if is_student:
                case_ids = [c.id for c in Case.query.filter_by(status=CaseStatus.PUBLISHED).order_by(Case.id.desc()).all()]
            else:
                case_ids = [c.id for c in Case.query.order_by(Case.id.desc()).all()]
        
        # Find prev/next based on list order
        if case_id in case_ids:
            idx = case_ids.index(case_id)
            if idx > 0:
                prev_case_id = case_ids[idx - 1]
            if idx < len(case_ids) - 1:
                next_case_id = case_ids[idx + 1]
                
    except Exception as e:
        import traceback
        traceback.print_exc()
    
    return prev_case_id, next_case_id, nav_params


@app.route('/view-case/<int:case_id>')
@login_required
def view_case(case_id):
    """View a specific case with prev/next navigation based on list context"""
    from models import CandidateNote, CaseStatus
    
    case = Case.query.get(case_id)
    if not case:
        return redirect(url_for('dashboard'))

    # Access check: admin/content managers see all; students see public + own cases
    if not has_case_edit_permission(case) and not has_case_view_access(case):
        flash('You do not have access to this case.', 'warning')
        return redirect(url_for('dashboard'))

    # Get user's note for this case
    user_note = CandidateNote.query.filter_by(case_id=case_id, user_id=current_user.id).first()
    
    # Get navigation context from query params
    list_source = request.args.get('list_source', '')
    from_staging = request.args.get('from_staging', '') == 'true'
    
    # Collect filters from query params
    filters = {
        'module': request.args.get('module', ''),
        'body_part': request.args.get('body_part', ''),
        'age_group': request.args.get('age_group', ''),
        'status': request.args.get('status', ''),
        'q': request.args.get('q', ''),
    }
    
    # Compute prev/next
    prev_case_id, next_case_id, nav_params = get_case_navigation_context(case_id, list_source, filters)
    
    # Build query string for nav links
    nav_query_string = '&'.join(f"{k}={v}" for k, v in nav_params.items() if v)
    
    # TNM Staging: show calculator link in Notes tab when diagnosis is cancer and we can map to AJCC
    show_tnm_tab = False
    tnm_staging_url = None
    try:
        from ai_tnm import is_oncologic_diagnosis, _map_to_ajcc_site
        if (case.diagnosis and is_oncologic_diagnosis(case.diagnosis)):
            module_hint = case.module.value if case.module else None
            body_part_hint = case.body_part.value if case.body_part else None
            ajcc = _map_to_ajcc_site(case.diagnosis, module=module_hint, body_part=body_part_hint)
            if ajcc and ajcc.get('section_slug') and ajcc.get('disease_slug'):
                show_tnm_tab = True
                tnm_staging_url = f"/tnm/{ajcc['section_slug']}/{ajcc['disease_slug']}/view?year=2026&from_case={case_id}"
    except Exception:
        pass
    
    return render_template('view_case.html', 
                         case=case, 
                         user_note=user_note,
                         previous_case_id=prev_case_id,
                         next_case_id=next_case_id,
                         from_staging=from_staging,
                         nav_params=nav_params,
                         nav_query_string=nav_query_string,
                         show_tnm_tab=show_tnm_tab,
                         tnm_staging_url=tnm_staging_url)


# Body part groups for edit-case dropdown (group label -> enum names; must match models.BodyPart)
BODY_PART_GROUPS = [
    ("Cardiovascular", ["CARDIOVASCULAR"]),
    ("Lung and Thorax", ["LUNG_MEDIASTINUM", "CHEST_WALL"]),
    ("Gastrointestinal", ["UPPER_GASTROINTESTINAL", "LOWER_GASTROINTESTINAL", "GASTROINTESTINAL", "HEPATOPANCREATICOBILIARY"]),
    ("Genitourinary and Endocrine", ["ADRENAL", "MALE_GENITAL", "THYROID_PARATHYROID", "SPLEEN", "KUB"]),
    ("Gynaecology and Breast", ["GYNAECOLOGY", "BREAST"]),
    ("Musculoskeletal", ["UPPER_LIMB", "LOWER_LIMB", "BONES", "SOFT_TISSUE"]),
    ("CNS and Head & Neck", ["BRAIN_PITUITARY", "BRAIN_SPINE", "SPINE", "HEAD_NECK"]),
    ("Multi-system", ["MULTISYSTEM"]),
]


@app.route('/edit-case')
def edit_case():
    """Full-page edit interface for a case or staging case"""
    case_id = request.args.get('id', type=int)
    staging_id = request.args.get('staging_id', type=int)
    is_new = request.args.get('new', 'false').lower() == 'true'
    return_to = _validate_return_url(request.args.get('returnTo'))
    status_filter = request.args.get('status', '')
    
    case = None
    staging_case = None
    prev_staging_id = None
    next_staging_id = None
    
    if staging_id:
        # Load staging case for review/enrichment
        from models import ImportedCaseStaging
        staging_case = ImportedCaseStaging.query.get(staging_id)
        if not staging_case:
            return redirect(url_for('dashboard'))
        
        # Compute prev/next staging case IDs (same order as staging list: created_at desc)
        query = ImportedCaseStaging.query
        if status_filter:
            query = query.filter(ImportedCaseStaging.enrichment_status == status_filter)
        staging_ids = [s.id for s in query.order_by(ImportedCaseStaging.created_at.desc()).all()]
        
        if staging_id in staging_ids:
            idx = staging_ids.index(staging_id)
            if idx > 0:
                prev_staging_id = staging_ids[idx - 1]
            if idx < len(staging_ids) - 1:
                next_staging_id = staging_ids[idx + 1]
                
    elif case_id:
        # Load regular case for editing
        case = Case.query.get(case_id)
        if not case:
            return redirect(url_for('dashboard'))
    elif not is_new:
        # Neither staging_id, case_id, nor new - invalid request
        return redirect(url_for('dashboard'))
    
    # Build body part dropdown from enum so it stays in sync with models.BodyPart
    body_part_groups = []
    for label, names in BODY_PART_GROUPS:
        opts = []
        for n in names:
            try:
                b = BodyPart[n]
                opts.append((b.name, b.value))
            except KeyError:
                pass
        if opts:
            body_part_groups.append((label, opts))
    
    return render_template('edit_case.html', 
                         is_new=is_new,
                         return_to=return_to,
                         case=case,
                         staging_case=staging_case,
                         prev_staging_id=prev_staging_id,
                         next_staging_id=next_staging_id,
                         status_filter=status_filter,
                         body_part_groups=body_part_groups,
                         cloudinary_cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
                         cloudinary_upload_preset=os.environ.get('CLOUDINARY_UPLOAD_PRESET', ''))




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


@app.route('/api/case/<int:case_id>', methods=['DELETE'])
@login_required
def delete_case(case_id):
    """Delete a case and all related data"""
    # Verify user ownership
    case = verify_case_ownership(case_id)
    if not case:
        return jsonify({"error": "Unauthorized"}), 403
    
    try:
        # Clean up foreign key references that might prevent deletion
        
        # 1. Delete or update AiDiagnosisCache entries that reference this case as first_case_id
        from models import AiDiagnosisCache
        cache_entries = AiDiagnosisCache.query.filter_by(first_case_id=case_id).all()
        for cache_entry in cache_entries:
            db.session.delete(cache_entry)
        
        # 2. Update ImportedCaseStaging entries that reference this case as promoted_to_case_id
        from models import ImportedCaseStaging
        staging_entries = ImportedCaseStaging.query.filter_by(promoted_to_case_id=case_id).all()
        for staging_entry in staging_entries:
            staging_entry.promoted_to_case_id = None
            staging_entry.promoted_at = None
        
        # 3. Delete AiPrelimCaseData entries that reference this case
        from models import AiPrelimCaseData
        prelim_entries = AiPrelimCaseData.query.filter_by(case_id=case_id).all()
        for prelim_entry in prelim_entries:
            db.session.delete(prelim_entry)
        
        # 4. Delete CaseFlag entries that reference this case (NOT NULL constraint prevents cascade)
        from models import CaseFlag
        case_flags = CaseFlag.query.filter_by(case_id=case_id).all()
        for flag in case_flags:
            db.session.delete(flag)
        
        # 5. Clean up Cloudinary images from forum messages before cascade delete
        from models import ForumMessage
        forum_messages = ForumMessage.query.filter_by(case_id=case_id).all()
        for msg in forum_messages:
            if msg.image_public_id:
                try:
                    cloudinary.uploader.destroy(msg.image_public_id)
                except Exception as e:
                    logger.warning(f"Failed to delete Cloudinary image {msg.image_public_id}: {e}")
        
        # 6. Delete the case (cascade will handle: Questions, Answers, Images, Notes, Highlights, AuditLogs, ViewLogs, ApprovalQueue, ForumMessages)
        db.session.delete(case)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Case deleted successfully'})
    
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to delete case: {str(e)}'}), 500


@app.route('/api/case/<int:case_id>/image', methods=['POST'])
@login_required
def upload_case_image(case_id):
    """Upload an image for a case - stores in Cloudinary"""
    import re
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
    
    # Check file size (max 10MB)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > 10 * 1024 * 1024:  # 10MB
        return jsonify({'error': 'File size exceeds 10MB limit'}), 400
    
    # Check file type by extension
    allowed_types = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    file_type = mimetypes.guess_type(file.filename)[0]

    if file_type not in allowed_types:
        return jsonify({'error': 'Only image files (JPEG, PNG, GIF, WebP) are allowed'}), 400

    # Verify actual content matches claimed type (magic byte check)
    actual_type = _validate_image_magic(file, allowed_types)
    if not actual_type:
        return jsonify({'error': 'File content does not match an allowed image format'}), 400
    
    # Get description from form data
    description = request.form.get('description', '')
    
    try:
        # Strip EXIF metadata (GPS, device info) before upload
        file = _strip_exif(file)

        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file,
            folder='frcr_revision/frcr_cases',
            resource_type='image',
            transformation=[{'quality': 'auto', 'fetch_format': 'auto'}]
        )
        
        # Generate thumbnail URL
        thumbnail_url = cloudinary.CloudinaryImage(upload_result['public_id']).build_url(
            width=200, height=200, crop='fill', quality='auto'
        )
        
        case_image = CaseImage(
            case_id=case_id,
            image_url=upload_result['secure_url'],
            image_public_id=upload_result['public_id'],
            image_thumbnail_url=thumbnail_url,
            image_filename=re.sub(r'[^a-zA-Z0-9._-]', '_', os.path.basename(file.filename)) if file.filename else 'upload',
            image_type=file_type,
            image_description=description
        )
        
        db.session.add(case_image)
        db.session.commit()
        
        return jsonify({
            'image_id': case_image.id,
            'filename': case_image.image_filename,
            'image_url': case_image.image_url,
            'thumbnail_url': case_image.image_thumbnail_url,
            'message': 'Image uploaded successfully'
        })
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Upload error: {str(e)}'}), 500


@app.route('/api/case/<int:case_id>/image-url', methods=['POST'])
@login_required
def add_case_image_from_url(case_id):
    """Add a CaseImage from an external URL or from client-side Cloudinary upload.
    Used for Radiopaedia/CC-licensed URLs, or when frontend uploads directly to Cloudinary (avoids 413 on Vercel)."""
    case = verify_case_ownership(case_id)
    if not case:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json() or {}
    image_url = (data.get("image_url") or "").strip()
    if not image_url:
        return jsonify({"error": "image_url is required"}), 400

    thumbnail_url = (data.get("thumbnail_url") or "").strip() or image_url
    description = (data.get("description") or "").strip()
    filename = (data.get("filename") or "").strip()
    if not filename:
        # Extract filename from URL
        from urllib.parse import urlparse
        path = urlparse(image_url).path
        filename = path.split("/")[-1] or "external_image.jpg"

    # Optional: for client-side Cloudinary uploads we store public_id so delete can remove from Cloudinary
    image_public_id = (data.get("image_public_id") or "").strip() or None
    image_type = (data.get("image_type") or "").strip() or "image/jpeg"

    case_image = CaseImage(
        case_id=case_id,
        image_url=image_url,
        image_public_id=image_public_id,
        image_thumbnail_url=thumbnail_url,
        image_filename=filename,
        image_type=image_type,
        image_description=description,
    )
    db.session.add(case_image)
    try:
        db.session.commit()
        return jsonify({
            "image_id": case_image.id,
            "filename": case_image.image_filename,
            "image_url": case_image.image_url,
            "thumbnail_url": case_image.image_thumbnail_url,
            "message": "Image added successfully",
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route('/api/case/<int:case_id>/images')
@login_required
def get_case_images(case_id):
    """Get all images for a case - returns Cloudinary URLs or legacy fallback"""
    # Verify user ownership
    case = verify_case_ownership(case_id)
    if not case:
        return jsonify({"error": "Unauthorized"}), 403
    images = CaseImage.query.filter_by(case_id=case_id).order_by(CaseImage.created_at).all()
    return jsonify([{
        'id': img.id,
        'filename': img.image_filename,
        'description': img.image_description if img.image_description else '',
        'created_at': img.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        # Include Cloudinary URLs if available, else clients use /api/case-image/<id>
        'image_url': img.image_url,
        'thumbnail_url': img.image_thumbnail_url,
        'is_cloudinary': img.is_cloudinary
    } for img in images])


@app.route('/api/case-image/<int:image_id>')
@login_required
def get_case_image(image_id):
    """Retrieve a case image by ID - redirects to Cloudinary or serves legacy binary"""
    image = CaseImage.query.get(image_id)
    
    if not image:
        return jsonify({'error': 'Image not found'}), 404
    
    # If image is on Cloudinary, redirect to CDN
    if image.is_cloudinary and image.image_url:
        return redirect(image.image_url)
    
    # Legacy fallback: serve binary data from database
    if image.image_data:
        return send_file(
            BytesIO(image.image_data),
            mimetype=image.image_type,
            as_attachment=False,
            download_name=image.image_filename
        )
    
    return jsonify({'error': 'Image data not found'}), 404


@app.route('/api/case-image/<int:image_id>', methods=['DELETE'])
@login_required
def delete_case_image(image_id):
    """Delete a case image - cleans up Cloudinary if applicable"""
    # Verify user ownership of the case image
    image = CaseImage.query.get(image_id)
    if not image:
        return jsonify({"error": "Image not found"}), 404
    case = verify_case_ownership(image.case_id)
    if not case:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Delete from Cloudinary if applicable
    if image.image_public_id:
        try:
            cloudinary.uploader.destroy(image.image_public_id)
        except Exception as e:
            logger.warning(f"Failed to delete Cloudinary image {image.image_public_id}: {e}")
    
    db.session.delete(image)
    db.session.commit()
    
    return jsonify({'message': 'Image deleted successfully'})


@app.route('/api/case-image/<int:image_id>/description', methods=['GET', 'PUT'])
def image_description(image_id):
    """Get or update image description"""
    image = CaseImage.query.get(image_id)
    
    if not image:
        return jsonify({'error': 'Image not found'}), 404
    
    # Handle GET request
    if request.method == 'GET':
        return jsonify({
            'image_id': image.id,
            'description': image.image_description or ''
        })
    
    # Handle PUT request - update image description
    try:
        import bleach
        data = request.get_json()
        description = data.get('description', '')
        # Sanitize HTML for image description
        allowed_tags = list(bleach.sanitizer.ALLOWED_TAGS) + [
            'p', 'br', 'span', 'div', 'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'strong', 'em', 'u', 'b', 'i', 'a'
        ]
        allowed_attributes = {
            '*': ['style', 'class'],
            'a': ['href', 'title', 'target', 'rel'],
            'td': ['colspan', 'rowspan'],
            'th': ['colspan', 'rowspan']
        }
        cleaned = bleach.clean(
            description,
            tags=allowed_tags,
            attributes=allowed_attributes,
            strip=True
        )
        image.image_description = cleaned
        db.session.commit()
        return jsonify({
            'image_id': image.id,
            'description': image.image_description,
            'message': 'Description updated successfully'
        })
    except Exception as e:
        db.session.rollback()
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
        pair = {
            'number': i + 1,
            'question': {
                'id': questions[i].id,
                'text': questions[i].question_text
            } if i < len(questions) else {'id': None, 'text': ''},
            'answer': {
                'id': answers[i].id,
                'text': answers[i].answer_text
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
                    question = Question(
                        case_id=case_id,
                        question_number=index,
                        question_text=question_text
                    )
                    db.session.add(question)
                
                if answer_text:
                    answer = Answer(
                        case_id=case_id,
                        answer_number=index,
                        answer_text=answer_text
                    )
                    db.session.add(answer)
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'Updated {len(pairs)} Q&A pairs'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ==================== RELATED CASES API ====================

@app.route('/api/case/<int:case_id>/related', methods=['GET'])
@login_required
def get_related_cases(case_id):
    """Get all linked content for a case: cases, calculators, and references"""
    from models import related_cases as related_cases_table, case_calculator_links, case_reference_links, TNMCalculatorContent, CaseReference
    Case.query.get_or_404(case_id)

    items = []

    # 1) Case-to-case links
    rows = db.session.execute(
        db.select(
            related_cases_table.c.related_case_id,
            related_cases_table.c.relation_type
        ).where(related_cases_table.c.case_id == case_id)
    ).all()
    for row in rows:
        rc = Case.query.get(row.related_case_id)
        if rc:
            items.append({
                'id': rc.id,
                'link_type': 'case',
                'case_number': rc.case_number,
                'diagnosis': rc.diagnosis,
                'body_part': rc.body_part.value if rc.body_part else None,
                'calculator_slug': rc.calculator_slug,
                'relation_type': row.relation_type or 'related',
                'url': f'/view-case/{rc.id}'
            })

    # 2) Case-to-calculator links
    calc_rows = db.session.execute(
        db.select(case_calculator_links.c.calculator_id).where(
            case_calculator_links.c.case_id == case_id
        )
    ).all()
    for crow in calc_rows:
        calc = TNMCalculatorContent.query.get(crow.calculator_id)
        if calc:
            items.append({
                'id': calc.id,
                'link_type': 'calculator',
                'slug': calc.slug,
                'cancer_name': calc.cancer_name,
                'body_section': calc.body_section,
                'url': f'/tnm-calculator/{calc.slug}'
            })

    # 3) Case-to-reference links
    ref_rows = db.session.execute(
        db.select(case_reference_links.c.reference_id).where(
            case_reference_links.c.case_id == case_id
        )
    ).all()
    for rrow in ref_rows:
        ref = CaseReference.query.get(rrow.reference_id)
        if ref:
            items.append({
                'id': ref.id,
                'link_type': 'reference',
                'title': ref.title,
                'ref_url': ref.url,
                'journal': ref.journal,
                'year': ref.year,
                'source_case_number': None
            })
            # Try to get source case number for display
            source_case = Case.query.get(ref.case_id)
            if source_case:
                items[-1]['source_case_number'] = source_case.case_number

    # 4) Case-to-algorithm links
    algo_rows = db.session.execute(
        db.select(case_algorithm_links.c.algorithm_id).where(
            case_algorithm_links.c.case_id == case_id
        )
    ).all()
    for arow in algo_rows:
        algo = ReportingAlgorithm.query.get(arow.algorithm_id)
        if algo:
            items.append({
                'id': algo.id,
                'link_type': 'reporting_algorithm',
                'title': algo.title,
                'slug': algo.slug,
                'category': algo.category,
                'body_section': algo.body_section,
                'url': f'/reporting-template/{algo.slug}'
            })

    # 5) Case-to-template links
    tmpl_rows = db.session.execute(
        db.select(case_template_links.c.template_id).where(
            case_template_links.c.case_id == case_id
        )
    ).all()
    for trow in tmpl_rows:
        tmpl = RadiologyTemplate.query.get(trow.template_id)
        if tmpl:
            items.append({
                'id': tmpl.id,
                'link_type': 'radiology_template',
                'title': tmpl.title,
                'slug': tmpl.slug,
                'category': tmpl.category,
                'body_section': tmpl.body_section,
            })

    # 6) Case-to-pearl links
    pearl_rows = db.session.execute(
        db.select(case_pearl_links.c.pearl_id).where(
            case_pearl_links.c.case_id == case_id
        )
    ).all()
    for prow in pearl_rows:
        pearl = RadiologyPearl.query.get(prow.pearl_id)
        if pearl:
            items.append({
                'id': pearl.id,
                'link_type': 'pearl',
                'title': pearl.pearl_text[:120] + '...' if len(pearl.pearl_text or '') > 120 else pearl.pearl_text,
                'body_section': pearl.body_section,
                'is_verified': pearl.is_verified,
            })

    return jsonify(items)


@app.route('/api/pearl/<int:pearl_id>/linked-cases', methods=['GET'])
@login_required
def get_pearl_linked_cases(pearl_id):
    """Get all cases linked to a radiology pearl (reverse lookup)."""
    from models import case_pearl_links
    RadiologyPearl.query.get_or_404(pearl_id)

    rows = db.session.execute(
        db.select(case_pearl_links.c.case_id).where(
            case_pearl_links.c.pearl_id == pearl_id
        )
    ).all()

    cases = []
    for row in rows:
        c = Case.query.get(row.case_id)
        if c:
            cases.append({
                'id': c.id,
                'case_number': c.case_number,
                'diagnosis': c.diagnosis[:120] + '...' if len(c.diagnosis or '') > 120 else c.diagnosis,
                'body_part': c.body_part.value if c.body_part else None,
                'status': c.status.value if c.status else None,
                'url': f'/view-case/{c.id}',
            })
    return jsonify(cases)


@app.route('/api/algorithm/<int:algorithm_id>/linked-cases', methods=['GET'])
@login_required
def get_algorithm_linked_cases(algorithm_id):
    """Get all cases linked to a reporting algorithm / anatomy snippet (reverse lookup)."""
    from models import case_algorithm_links
    ReportingAlgorithm.query.get_or_404(algorithm_id)

    rows = db.session.execute(
        db.select(case_algorithm_links.c.case_id).where(
            case_algorithm_links.c.algorithm_id == algorithm_id
        )
    ).all()

    cases = []
    for row in rows:
        c = Case.query.get(row.case_id)
        if c:
            cases.append({
                'id': c.id,
                'case_number': c.case_number,
                'diagnosis': c.diagnosis[:120] + '...' if len(c.diagnosis or '') > 120 else c.diagnosis,
                'body_part': c.body_part.value if c.body_part else None,
                'status': c.status.value if c.status else None,
                'url': f'/view-case/{c.id}',
            })
    return jsonify(cases)


# ==================== UNIVERSAL CONTENT LINKING API ====================
_VALID_CONTENT_TYPES = ('case', 'pearl', 'algorithm')

def _resolve_content_item(ctype, cid):
    """Resolve a content type + id to a display dict, or None if not found."""
    if ctype == 'case':
        c = Case.query.get(cid)
        if not c:
            return None
        return {
            'link_type': 'case', 'id': c.id,
            'title': f'{c.case_number} — {(c.diagnosis or "")[:80]}',
            'subtitle': c.body_part.value if c.body_part else '',
            'icon': 'fa-file-medical', 'color': '#5E899E',
            'url': f'/view-case/{c.id}',
        }
    elif ctype == 'pearl':
        p = RadiologyPearl.query.get(cid)
        if not p:
            return None
        import re
        plain = re.sub(r'<[^>]+>', '', p.pearl_text or '')[:100]
        return {
            'link_type': 'pearl', 'id': p.id,
            'title': plain + ('...' if len(re.sub(r'<[^>]+>', '', p.pearl_text or '')) > 100 else ''),
            'subtitle': ' | '.join(filter(None, [p.body_section, p.modality])),
            'icon': 'fa-gem', 'color': '#6b46c1',
            'url': None,
        }
    elif ctype == 'algorithm':
        a = ReportingAlgorithm.query.get(cid)
        if not a:
            return None
        slug_prefix = 'anatomy-snippets' if a.origin == 'anatomy_cache' else 'reporting-algorithms'
        return {
            'link_type': 'algorithm', 'id': a.id,
            'title': a.title or '',
            'subtitle': ' | '.join(filter(None, [a.body_section, a.origin])),
            'icon': 'fa-bone', 'color': '#6f42c1',
            'url': f'/{slug_prefix}/{a.slug}' if a.slug else None,
        }
    return None


def _canonical_link(stype, sid, ttype, tid):
    """Return (source_type, source_id, target_type, target_id) in canonical order.
    Alphabetical by type; for same type, lower id first."""
    if stype > ttype or (stype == ttype and sid > tid):
        return ttype, tid, stype, sid
    return stype, sid, ttype, tid


@app.route('/api/content/<content_type>/<int:content_id>/links', methods=['GET'])
@login_required
def get_content_links(content_type, content_id):
    """Get all linked content for any item, merging legacy tables + content_links."""
    if content_type not in _VALID_CONTENT_TYPES:
        return jsonify({'error': 'Invalid content type'}), 400

    # Verify item exists
    if _resolve_content_item(content_type, content_id) is None:
        return jsonify({'error': 'Item not found'}), 404

    seen = set()  # (type, id) to deduplicate
    items = []

    def _add(ctype, cid):
        if (ctype, cid) in seen:
            return
        seen.add((ctype, cid))
        resolved = _resolve_content_item(ctype, cid)
        if resolved:
            items.append(resolved)

    # 1. Query content_links in both directions
    rows = db.session.execute(
        db.select(
            content_links.c.source_type, content_links.c.source_id,
            content_links.c.target_type, content_links.c.target_id
        ).where(
            db.or_(
                db.and_(content_links.c.source_type == content_type, content_links.c.source_id == content_id),
                db.and_(content_links.c.target_type == content_type, content_links.c.target_id == content_id),
            )
        )
    ).all()
    for row in rows:
        # Resolve the OTHER side of the link
        if row.source_type == content_type and row.source_id == content_id:
            _add(row.target_type, row.target_id)
        else:
            _add(row.source_type, row.source_id)

    # 2. Merge legacy case link tables
    if content_type == 'pearl':
        legacy_rows = db.session.execute(
            db.select(case_pearl_links.c.case_id).where(case_pearl_links.c.pearl_id == content_id)
        ).all()
        for r in legacy_rows:
            _add('case', r.case_id)
    elif content_type == 'algorithm':
        legacy_rows = db.session.execute(
            db.select(case_algorithm_links.c.case_id).where(case_algorithm_links.c.algorithm_id == content_id)
        ).all()
        for r in legacy_rows:
            _add('case', r.case_id)
    elif content_type == 'case':
        # Case → pearls
        pearl_rows = db.session.execute(
            db.select(case_pearl_links.c.pearl_id).where(case_pearl_links.c.case_id == content_id)
        ).all()
        for r in pearl_rows:
            _add('pearl', r.pearl_id)
        # Case → algorithms
        algo_rows = db.session.execute(
            db.select(case_algorithm_links.c.algorithm_id).where(case_algorithm_links.c.case_id == content_id)
        ).all()
        for r in algo_rows:
            _add('algorithm', r.algorithm_id)

    return jsonify(items)


@app.route('/api/content/<content_type>/<int:content_id>/links', methods=['POST'])
@login_required
def add_content_link(content_type, content_id):
    """Create a link between two content items. Auto cross-links via bidirectional query."""
    if content_type not in _VALID_CONTENT_TYPES:
        return jsonify({'error': 'Invalid content type'}), 400

    data = request.get_json()
    target_type = data.get('target_type', '').strip()
    target_id = data.get('target_id')

    if target_type not in _VALID_CONTENT_TYPES or not target_id:
        return jsonify({'error': 'target_type and target_id required'}), 400
    target_id = int(target_id)

    # Prevent self-links
    if content_type == target_type and content_id == target_id:
        return jsonify({'error': 'Cannot link an item to itself'}), 400

    # Verify both exist
    if _resolve_content_item(content_type, content_id) is None:
        return jsonify({'error': 'Source item not found'}), 404
    target_resolved = _resolve_content_item(target_type, target_id)
    if target_resolved is None:
        return jsonify({'error': 'Target item not found'}), 404

    # Route case links to legacy tables for backward compat
    case_side = None
    other_type = None
    other_id = None
    if content_type == 'case':
        case_side = content_id
        other_type, other_id = target_type, target_id
    elif target_type == 'case':
        case_side = target_id
        other_type, other_id = content_type, content_id

    if case_side is not None:
        if other_type == 'pearl':
            # Check duplicate in legacy table
            exists = db.session.execute(
                db.select(case_pearl_links.c.id).where(
                    case_pearl_links.c.case_id == case_side,
                    case_pearl_links.c.pearl_id == other_id,
                )
            ).first()
            if exists:
                return jsonify({'error': 'Already linked'}), 400
            db.session.execute(case_pearl_links.insert().values(
                case_id=case_side, pearl_id=other_id,
                created_by_user_id=current_user.id,
            ))
            db.session.commit()
            return jsonify(target_resolved)
        elif other_type == 'algorithm':
            exists = db.session.execute(
                db.select(case_algorithm_links.c.id).where(
                    case_algorithm_links.c.case_id == case_side,
                    case_algorithm_links.c.algorithm_id == other_id,
                )
            ).first()
            if exists:
                return jsonify({'error': 'Already linked'}), 400
            db.session.execute(case_algorithm_links.insert().values(
                case_id=case_side, algorithm_id=other_id,
                created_by_user_id=current_user.id,
            ))
            db.session.commit()
            return jsonify(target_resolved)

    # Non-case link → content_links table (canonical order)
    s_type, s_id, t_type, t_id = _canonical_link(content_type, content_id, target_type, target_id)

    exists = db.session.execute(
        db.select(content_links.c.id).where(
            content_links.c.source_type == s_type,
            content_links.c.source_id == s_id,
            content_links.c.target_type == t_type,
            content_links.c.target_id == t_id,
        )
    ).first()
    if exists:
        return jsonify({'error': 'Already linked'}), 400

    db.session.execute(content_links.insert().values(
        source_type=s_type, source_id=s_id,
        target_type=t_type, target_id=t_id,
        created_by_user_id=current_user.id,
    ))
    db.session.commit()
    return jsonify(target_resolved)


@app.route('/api/content/<content_type>/<int:content_id>/links', methods=['DELETE'])
@login_required
def delete_content_link(content_type, content_id):
    """Remove a link between two content items. Admin only."""
    from models import UserRole
    if current_user.role not in [UserRole.ADMIN, UserRole.CONTENT_MANAGER]:
        return jsonify({'error': 'Admin access required'}), 403

    if content_type not in _VALID_CONTENT_TYPES:
        return jsonify({'error': 'Invalid content type'}), 400

    data = request.get_json() or {}
    target_type = data.get('target_type') or request.args.get('target_type', '').strip()
    target_id = data.get('target_id') or request.args.get('target_id', type=int)

    if not target_type or not target_id:
        return jsonify({'error': 'target_type and target_id required'}), 400
    target_id = int(target_id)

    deleted = False

    # Try legacy tables first if case involved
    case_side = None
    other_type = None
    other_id = None
    if content_type == 'case':
        case_side = content_id
        other_type, other_id = target_type, target_id
    elif target_type == 'case':
        case_side = target_id
        other_type, other_id = content_type, content_id

    if case_side is not None:
        if other_type == 'pearl':
            db.session.execute(
                case_pearl_links.delete().where(
                    case_pearl_links.c.case_id == case_side,
                    case_pearl_links.c.pearl_id == other_id,
                )
            )
            deleted = True
        elif other_type == 'algorithm':
            db.session.execute(
                case_algorithm_links.delete().where(
                    case_algorithm_links.c.case_id == case_side,
                    case_algorithm_links.c.algorithm_id == other_id,
                )
            )
            deleted = True

    # Also try content_links (canonical order)
    s_type, s_id, t_type, t_id = _canonical_link(content_type, content_id, target_type, target_id)
    db.session.execute(
        content_links.delete().where(
            content_links.c.source_type == s_type,
            content_links.c.source_id == s_id,
            content_links.c.target_type == t_type,
            content_links.c.target_id == t_id,
        )
    )
    deleted = True

    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/content/search', methods=['GET'])
@login_required
def search_content_universal():
    """Unified search across all content types for the linking UI."""
    query = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'all').strip()
    exclude_type = request.args.get('exclude_type', '').strip()
    exclude_id = request.args.get('exclude_id', type=int)
    limit = request.args.get('limit', 15, type=int)

    if len(query) < 2:
        return jsonify([])

    results = []
    import re as _re

    def _search_cases(per_limit):
        cases = Case.query.filter(
            db.or_(Case.diagnosis.ilike(f'%{query}%'), Case.case_number.ilike(f'%{query}%'))
        ).limit(per_limit).all()
        for c in cases:
            if exclude_type == 'case' and exclude_id == c.id:
                continue
            results.append({
                'link_type': 'case', 'id': c.id,
                'title': f'{c.case_number} — {(c.diagnosis or "")[:80]}',
                'subtitle': c.body_part.value if c.body_part else '',
                'icon': 'fa-file-medical', 'color': '#5E899E',
                'badge': 'Case',
            })

    def _search_pearls(per_limit):
        pearls = RadiologyPearl.query.filter(
            db.or_(
                RadiologyPearl.pearl_text.ilike(f'%{query}%'),
                RadiologyPearl.tags.ilike(f'%{query}%'),
                RadiologyPearl.body_section.ilike(f'%{query}%'),
            )
        ).limit(per_limit).all()
        for p in pearls:
            if exclude_type == 'pearl' and exclude_id == p.id:
                continue
            plain = _re.sub(r'<[^>]+>', '', p.pearl_text or '')[:100]
            results.append({
                'link_type': 'pearl', 'id': p.id,
                'title': plain + ('...' if len(_re.sub(r'<[^>]+>', '', p.pearl_text or '')) > 100 else ''),
                'subtitle': ' | '.join(filter(None, [p.body_section, p.modality])),
                'icon': 'fa-gem', 'color': '#6b46c1',
                'badge': 'Pearl',
            })

    def _search_algorithms(per_limit):
        algos = ReportingAlgorithm.query.filter(
            ReportingAlgorithm.is_available == True,
            db.or_(
                ReportingAlgorithm.title.ilike(f'%{query}%'),
                ReportingAlgorithm.keywords.ilike(f'%{query}%'),
                ReportingAlgorithm.body_section.ilike(f'%{query}%'),
            )
        ).limit(per_limit).all()
        for a in algos:
            if exclude_type == 'algorithm' and exclude_id == a.id:
                continue
            is_anatomy = (a.category == 'anatomy')
            results.append({
                'link_type': 'algorithm', 'id': a.id,
                'title': a.title or '',
                'subtitle': ' | '.join(filter(None, [a.body_section, a.origin])),
                'icon': 'fa-bone' if is_anatomy else 'fa-sitemap',
                'color': '#0d6efd' if is_anatomy else '#5E899E',
                'badge': 'Anatomy' if is_anatomy else 'Algorithm',
            })

    if search_type == 'all':
        per_limit = min(limit, 5)
        _search_cases(per_limit)
        _search_pearls(per_limit)
        _search_algorithms(per_limit)
    elif search_type == 'case':
        _search_cases(limit)
    elif search_type == 'pearl':
        _search_pearls(limit)
    elif search_type == 'algorithm':
        _search_algorithms(limit)

    return jsonify(results[:limit])


@app.route('/api/case/<int:case_id>/related', methods=['POST'])
@login_required
def add_related_case(case_id):
    """Add a linked item (case, calculator, or reference) to a case - all authenticated users can add"""
    from models import related_cases, case_calculator_links, case_reference_links, TNMCalculatorContent, CaseReference

    case = Case.query.get_or_404(case_id)
    data = request.get_json()
    link_type = data.get('link_type', 'case')  # 'case', 'calculator', 'reference'

    if link_type == 'calculator':
        calculator_id = data.get('calculator_id')
        if not calculator_id:
            return jsonify({'error': 'calculator_id required'}), 400
        calc = TNMCalculatorContent.query.get(calculator_id)
        if not calc:
            return jsonify({'error': 'Calculator not found'}), 404
        existing = db.session.execute(
            db.select(case_calculator_links).where(
                case_calculator_links.c.case_id == case_id,
                case_calculator_links.c.calculator_id == calculator_id
            )
        ).first()
        if existing:
            return jsonify({'error': 'Calculator already linked'}), 400
        db.session.execute(case_calculator_links.insert().values(
            case_id=case_id, calculator_id=calculator_id, created_by_user_id=current_user.id
        ))
        db.session.commit()
        return jsonify({'success': True, 'message': 'Calculator linked', 'item': {
            'id': calc.id, 'link_type': 'calculator', 'slug': calc.slug,
            'cancer_name': calc.cancer_name, 'body_section': calc.body_section,
            'url': f'/tnm-calculator/{calc.slug}'
        }})

    elif link_type == 'reference':
        reference_id = data.get('reference_id')
        if not reference_id:
            return jsonify({'error': 'reference_id required'}), 400
        ref = CaseReference.query.get(reference_id)
        if not ref:
            return jsonify({'error': 'Reference not found'}), 404
        existing = db.session.execute(
            db.select(case_reference_links).where(
                case_reference_links.c.case_id == case_id,
                case_reference_links.c.reference_id == reference_id
            )
        ).first()
        if existing:
            return jsonify({'error': 'Reference already linked'}), 400
        db.session.execute(case_reference_links.insert().values(
            case_id=case_id, reference_id=reference_id, created_by_user_id=current_user.id
        ))
        db.session.commit()
        return jsonify({'success': True, 'message': 'Reference linked', 'item': {
            'id': ref.id, 'link_type': 'reference', 'title': ref.title,
            'ref_url': ref.url, 'journal': ref.journal, 'year': ref.year
        }})

    elif link_type == 'reporting_algorithm':
        algorithm_id = data.get('algorithm_id')
        if not algorithm_id:
            return jsonify({'error': 'algorithm_id required'}), 400
        algo = ReportingAlgorithm.query.get(algorithm_id)
        if not algo:
            return jsonify({'error': 'Algorithm not found'}), 404
        existing = db.session.execute(
            db.select(case_algorithm_links).where(
                case_algorithm_links.c.case_id == case_id,
                case_algorithm_links.c.algorithm_id == algorithm_id
            )
        ).first()
        if existing:
            return jsonify({'error': 'Algorithm already linked'}), 400
        db.session.execute(case_algorithm_links.insert().values(
            case_id=case_id, algorithm_id=algorithm_id, created_by_user_id=current_user.id
        ))
        db.session.commit()
        return jsonify({'success': True, 'message': 'Algorithm linked', 'item': {
            'id': algo.id, 'link_type': 'reporting_algorithm', 'title': algo.title,
            'slug': algo.slug, 'category': algo.category, 'body_section': algo.body_section,
            'url': f'/reporting-template/{algo.slug}'
        }})

    elif link_type == 'radiology_template':
        template_id = data.get('template_id')
        if not template_id:
            return jsonify({'error': 'template_id required'}), 400
        tmpl = RadiologyTemplate.query.get(template_id)
        if not tmpl:
            return jsonify({'error': 'Template not found'}), 404
        existing = db.session.execute(
            db.select(case_template_links).where(
                case_template_links.c.case_id == case_id,
                case_template_links.c.template_id == template_id
            )
        ).first()
        if existing:
            return jsonify({'error': 'Template already linked'}), 400
        db.session.execute(case_template_links.insert().values(
            case_id=case_id, template_id=template_id, created_by_user_id=current_user.id
        ))
        db.session.commit()
        return jsonify({'success': True, 'message': 'Template linked', 'item': {
            'id': tmpl.id, 'link_type': 'radiology_template', 'title': tmpl.title,
            'slug': tmpl.slug, 'category': tmpl.category, 'body_section': tmpl.body_section,
        }})

    elif link_type == 'pearl':
        pearl_id = data.get('pearl_id')
        if not pearl_id:
            return jsonify({'error': 'pearl_id required'}), 400
        pearl = RadiologyPearl.query.get(pearl_id)
        if not pearl:
            return jsonify({'error': 'Pearl not found'}), 404
        existing = db.session.execute(
            db.select(case_pearl_links).where(
                case_pearl_links.c.case_id == case_id,
                case_pearl_links.c.pearl_id == pearl_id
            )
        ).first()
        if existing:
            return jsonify({'error': 'Pearl already linked'}), 400
        db.session.execute(case_pearl_links.insert().values(
            case_id=case_id, pearl_id=pearl_id, created_by_user_id=current_user.id
        ))
        db.session.commit()
        return jsonify({'success': True, 'message': 'Pearl linked', 'item': {
            'id': pearl.id, 'link_type': 'pearl',
            'title': pearl.pearl_text[:120] + '...' if len(pearl.pearl_text or '') > 120 else pearl.pearl_text,
            'body_section': pearl.body_section,
        }})

    else:
        # Default: case-to-case link
        related_case_id = data.get('related_case_id')
        relation_type = data.get('relation_type', 'related')
        if not related_case_id:
            return jsonify({'error': 'related_case_id required'}), 400
        if related_case_id == case_id:
            return jsonify({'error': 'Cannot relate a case to itself'}), 400
        related_case = Case.query.get(related_case_id)
        if not related_case:
            return jsonify({'error': 'Related case not found'}), 404
        existing = db.session.execute(
            db.select(related_cases).where(
                related_cases.c.case_id == case_id,
                related_cases.c.related_case_id == related_case_id
            )
        ).first()
        if existing:
            return jsonify({'error': 'Cases are already related'}), 400
        db.session.execute(related_cases.insert().values(
            case_id=case_id, related_case_id=related_case_id, relation_type=relation_type
        ))
        db.session.commit()
        return jsonify({'success': True, 'message': 'Related case added', 'item': {
            'id': related_case.id, 'link_type': 'case', 'case_number': related_case.case_number,
            'diagnosis': related_case.diagnosis, 'relation_type': relation_type,
            'url': f'/view-case/{related_case.id}'
        }})


@app.route('/api/case/<int:case_id>/related/<int:linked_id>', methods=['DELETE'])
@login_required
def remove_related_case(case_id, linked_id):
    """Remove a linked item (case, calculator, or reference) from a case"""
    from models import related_cases, case_calculator_links, case_reference_links

    # Admin/Content Manager only
    if current_user.role not in [UserRole.ADMIN, UserRole.CONTENT_MANAGER]:
        return jsonify({'error': 'Unauthorized'}), 403

    link_type = request.args.get('link_type', 'case')

    if link_type == 'calculator':
        db.session.execute(
            case_calculator_links.delete().where(
                case_calculator_links.c.case_id == case_id,
                case_calculator_links.c.calculator_id == linked_id
            )
        )
    elif link_type == 'reference':
        db.session.execute(
            case_reference_links.delete().where(
                case_reference_links.c.case_id == case_id,
                case_reference_links.c.reference_id == linked_id
            )
        )
    elif link_type == 'reporting_algorithm':
        db.session.execute(
            case_algorithm_links.delete().where(
                case_algorithm_links.c.case_id == case_id,
                case_algorithm_links.c.algorithm_id == linked_id
            )
        )
    elif link_type == 'radiology_template':
        db.session.execute(
            case_template_links.delete().where(
                case_template_links.c.case_id == case_id,
                case_template_links.c.template_id == linked_id
            )
        )
    elif link_type == 'pearl':
        db.session.execute(
            case_pearl_links.delete().where(
                case_pearl_links.c.case_id == case_id,
                case_pearl_links.c.pearl_id == linked_id
            )
        )
    else:
        # Default: case-to-case
        db.session.execute(
            related_cases.delete().where(
                db.or_(
                    db.and_(
                        related_cases.c.case_id == case_id,
                        related_cases.c.related_case_id == linked_id
                    ),
                    db.and_(
                        related_cases.c.case_id == linked_id,
                        related_cases.c.related_case_id == case_id
                    )
                )
            )
        )

    db.session.commit()
    return jsonify({'success': True, 'message': 'Link removed'})


@app.route('/api/cases/search', methods=['GET'])
@login_required
def search_cases_for_linking():
    """Search content for the universal content linker.

    Accepts ?type= to branch search by content type.
    Default type=all searches ALL content types globally and returns
    mixed results with link_type badges for the frontend.
    """
    query = request.args.get('q', '').strip()
    exclude_id = request.args.get('exclude', type=int)
    limit = request.args.get('limit', 20, type=int)
    search_type = request.args.get('type', 'all').strip()

    if len(query) < 2:
        return jsonify([])

    # Per-type limit when searching globally (prevent one type dominating)
    per_type_limit = min(limit, 5) if search_type == 'all' else limit

    results = []

    # ── Cases ──
    if search_type in ('all', 'related', 'similar'):
        cases_query = Case.query.filter(
            db.or_(
                Case.diagnosis.ilike(f'%{query}%'),
                Case.case_number.ilike(f'%{query}%')
            )
        )
        if exclude_id:
            cases_query = cases_query.filter(Case.id != exclude_id)
        for c in cases_query.limit(per_type_limit).all():
            results.append({
                'id': c.id,
                'case_number': c.case_number,
                'diagnosis': c.diagnosis[:100] + '...' if len(c.diagnosis or '') > 100 else c.diagnosis,
                'body_part': c.body_part.value if c.body_part else None,
                'link_type': 'case',
            })

    # ── Staging Calculators (TNMCalculatorContent) ──
    if search_type in ('all', 'algorithm'):
        from models import TNMCalculatorContent
        for calc in TNMCalculatorContent.query.filter(
            db.or_(
                TNMCalculatorContent.cancer_name.ilike(f'%{query}%'),
                TNMCalculatorContent.slug.ilike(f'%{query}%'),
                TNMCalculatorContent.body_section.ilike(f'%{query}%'),
                TNMCalculatorContent.description.ilike(f'%{query}%'),
            )
        ).limit(per_type_limit).all():
            results.append({
                'id': calc.id,
                'slug': calc.slug,
                'cancer_name': calc.cancer_name,
                'body_section': calc.body_section,
                'url': f'/tnm-calculator/{calc.slug}',
                'link_type': 'calculator',
            })

    # ── References ──
    if search_type in ('all', 'reference'):
        from models import CaseReference
        seen_ids = set()
        for ref in CaseReference.query.filter(
            db.or_(
                CaseReference.title.ilike(f'%{query}%'),
                CaseReference.journal.ilike(f'%{query}%'),
            )
        ).limit(per_type_limit).all():
            if ref.id in seen_ids:
                continue
            seen_ids.add(ref.id)
            source_case = Case.query.get(ref.case_id)
            results.append({
                'id': ref.id,
                'title': ref.title[:120] + '...' if len(ref.title or '') > 120 else ref.title,
                'ref_url': ref.url,
                'journal': ref.journal,
                'year': ref.year,
                'source_case_number': source_case.case_number if source_case else None,
                'link_type': 'reference',
            })

    # ── Reporting Algorithms (non-anatomy) ──
    if search_type in ('all', 'reporting_algorithm'):
        algo_query = ReportingAlgorithm.query.filter(
            ReportingAlgorithm.is_available == True,
            db.or_(
                ReportingAlgorithm.title.ilike(f'%{query}%'),
                ReportingAlgorithm.keywords.ilike(f'%{query}%'),
                ReportingAlgorithm.body_section.ilike(f'%{query}%'),
            )
        )
        if search_type == 'all':
            algo_query = algo_query.filter(ReportingAlgorithm.category != 'anatomy')
        for a in algo_query.limit(per_type_limit).all():
            results.append({
                'id': a.id,
                'title': a.title,
                'slug': a.slug,
                'category': a.category,
                'body_section': a.body_section,
                'origin': a.origin,
                'link_type': 'reporting_algorithm',
            })

    # ── Anatomy Snippets (ReportingAlgorithm with category='anatomy') ──
    if search_type in ('all', 'anatomy_snippet'):
        for a in ReportingAlgorithm.query.filter(
            ReportingAlgorithm.is_available == True,
            ReportingAlgorithm.category == 'anatomy',
            db.or_(
                ReportingAlgorithm.title.ilike(f'%{query}%'),
                ReportingAlgorithm.keywords.ilike(f'%{query}%'),
                ReportingAlgorithm.body_section.ilike(f'%{query}%'),
            )
        ).limit(per_type_limit).all():
            results.append({
                'id': a.id,
                'title': a.title,
                'slug': a.slug,
                'category': 'anatomy',
                'body_section': a.body_section,
                'link_type': 'anatomy_snippet',
            })

    # ── Radiology Templates ──
    if search_type in ('all', 'radiology_template'):
        for t in RadiologyTemplate.query.filter(
            RadiologyTemplate.is_available == True,
            db.or_(
                RadiologyTemplate.title.ilike(f'%{query}%'),
                RadiologyTemplate.keywords.ilike(f'%{query}%'),
                RadiologyTemplate.body_section.ilike(f'%{query}%'),
            )
        ).limit(per_type_limit).all():
            results.append({
                'id': t.id,
                'title': t.title,
                'slug': t.slug,
                'category': t.category,
                'body_section': t.body_section,
                'link_type': 'radiology_template',
            })

    # ── Pearls ──
    if search_type in ('all', 'pearl'):
        for p in RadiologyPearl.query.filter(
            db.or_(
                RadiologyPearl.pearl_text.ilike(f'%{query}%'),
                RadiologyPearl.tags.ilike(f'%{query}%'),
                RadiologyPearl.body_section.ilike(f'%{query}%'),
            )
        ).limit(per_type_limit).all():
            results.append({
                'id': p.id,
                'title': p.pearl_text[:120] + '...' if len(p.pearl_text or '') > 120 else p.pearl_text,
                'body_section': p.body_section,
                'modality': p.modality,
                'is_verified': p.is_verified,
                'link_type': 'pearl',
            })

    return jsonify(results[:limit])


# ==================== CANDIDATE NOTES API ====================

@app.route('/api/case/<int:case_id>/note', methods=['GET'])
@login_required
def get_candidate_note(case_id):
    """Get user's note for a specific case"""
    from models import CandidateNote
    
    note = CandidateNote.query.filter_by(case_id=case_id, user_id=current_user.id).first()
    
    if not note:
        return jsonify({'note_text': ''}), 200
    
    return jsonify({
        'id': note.id,
        'note_text': note.note_text,
        'created_at': note.created_at.isoformat() if note.created_at else None,
        'updated_at': note.updated_at.isoformat() if note.updated_at else None
    })


# --- ADD POST HANDLER FOR CANDIDATE NOTES ---
@app.route('/api/case/<int:case_id>/note', methods=['POST'])
@login_required
def save_candidate_note(case_id):
    """Create or update user's note for a specific case"""
    from models import CandidateNote
    data = request.get_json()
    note_text = (data.get('note_text') or '').strip()
    if not note_text and note_text != '':
        return jsonify({'error': 'No note_text provided'}), 400
    note = CandidateNote.query.filter_by(case_id=case_id, user_id=current_user.id).first()
    if note:
        note.note_text = note_text
        note.updated_at = datetime.utcnow()
        action = 'updated'
    else:
        note = CandidateNote(case_id=case_id, user_id=current_user.id, note_text=note_text, created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        db.session.add(note)
        action = 'created'
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': f'Note {action}', 'note_text': note.note_text, 'updated_at': note.updated_at.isoformat() if note.updated_at else None})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


from access_control import has_case_edit_permission, has_case_view_access
from ai_prelim import AiPrelimError, generate_prelim_case_data

def verify_case_ownership(case_id):
    """
    Helper to check if the current user can access/edit the case.
    Admins and content managers: can edit all cases.
    Student contributors: can edit their own DRAFT cases.
    Other students: can only view published cases (GET only).
    Returns the case if allowed, else None.
    """
    from models import CaseStatus
    case = Case.query.get(case_id)
    if not case:
        return None
    # Admins and content managers can edit all cases
    if has_case_edit_permission(case):
        return case
    # Student contributors: can edit their own DRAFT cases (Suggest a Case)
    if (current_user.is_authenticated
            and case.created_by_user_id == current_user.id
            and case.status == CaseStatus.DRAFT):
        return case
    # Other students: only allow GET on viewable cases
    if has_case_view_access(case):
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
            'age_group': case.age_group.name if case.age_group else None,
            'calculator_slug': case.calculator_slug,
            'is_public': case.is_public,
            'status': case.status.name if case.status else 'DRAFT',
            'contributor_notes': case.contributor_notes or '',
            'contributor_name': case.contributor_name or '',
            'created_by_user_id': case.created_by_user_id,
        })

    # Handle PUT request (update case)
    if request.method == 'PUT':
        data = request.get_json()
        if data is None:
            return jsonify({'error': 'No data provided'}), 400
        # Update fields if present
        if 'diagnosis' in data:
            case.diagnosis = data['diagnosis']
        if 'discussion' in data:
            case.discussion = data['discussion']
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
        if 'calculator_slug' in data:
            case.calculator_slug = data['calculator_slug'] if data['calculator_slug'] else None
        if 'is_public' in data:
            val = data['is_public']
            if isinstance(val, bool):
                case.is_public = val
            elif isinstance(val, str):
                case.is_public = val.lower() == 'true'
            elif isinstance(val, int):
                case.is_public = val == 1
            else:
                case.is_public = False
        
        # Handle status update (with sync to is_public)
        if 'status' in data:
            from models import CaseStatus
            try:
                new_status = CaseStatus[data['status']] if data['status'] else CaseStatus.DRAFT
                case.status = new_status
                # Sync: PUBLISHED ↔ is_public (bidirectional)
                if new_status == CaseStatus.PUBLISHED:
                    case.is_public = True
                else:
                    case.is_public = False
            except (KeyError, ValueError):
                pass
        
        # Sync: If is_public is set, ensure status is PUBLISHED (bidirectional sync)
        if 'is_public' in data:
            if case.is_public and case.status != CaseStatus.PUBLISHED:
                case.status = CaseStatus.PUBLISHED
        
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
                    q = Question(case_id=case.id, question_number=index, question_text=question_text)
                    db.session.add(q)
                if answer_text:
                    a = Answer(case_id=case.id, answer_number=index, answer_text=answer_text)
                    db.session.add(a)
        try:
            db.session.commit()
            return jsonify({'success': True, 'message': 'Case updated'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500


def _escape_html(text):
    if text is None:
        return ''
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#039;'))


def _format_paragraph(text):
    if not text:
        return ''
    safe = _escape_html(text).replace('\n', '<br>')
    return f'<p>{safe}</p>'


def _sanitize_ai_html(html_content):
    """
    Sanitize AI-generated HTML, allowing only safe tags and our custom CSS classes.
    Strips <script>, onclick=, etc. while preserving styled content.
    """
    import bleach

    ALLOWED_TAGS = [
        'div', 'span', 'p', 'br', 'strong', 'em', 'b', 'i', 'u',
        'h3', 'h4', 'h5', 'ul', 'ol', 'li', 'table', 'thead', 'tbody',
        'tr', 'th', 'td', 'a', 'hr', 'sup', 'sub',
        'img', 'figure', 'figcaption', 'small',
    ]
    ALLOWED_ATTRS = {
        '*': ['class', 'style'],
        'a': ['href', 'target', 'rel'],
        'td': ['colspan', 'rowspan'],
        'th': ['colspan', 'rowspan'],
        'img': ['src', 'alt', 'loading', 'width', 'height'],
    }
    return bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        strip=True,
    )


def _is_html_discussion(text):
    """Detect if discussion content is HTML (new format) vs plain text (old cached data)."""
    if not text:
        return False
    return '<div' in text or '<table' in text or 'class=' in text


def _build_ai_discussion_html(output, provider, model_name):
    """
    Build HTML for AI-generated discussion content.

    Uses wrapper div with data-ai-generated="true" attribute for simple detection and removal.
    The wrapper provides visual distinction (orange background) and is removed when
    the case is saved and published, making the content appear as normal text.

    Handles both new HTML-formatted discussions (sanitized with bleach) and
    old plain-text discussions (escaped + newline conversion) for backward compat.
    """
    sections = []
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

    # Wrap entire AI-generated content in a single wrapper div with data attribute
    sections.append('<div data-ai-generated="true" class="ai-generated-wrapper">')

    # Discussion section
    discussion = (output or {}).get('discussion', '')
    if discussion:
        sections.append('<h4>Discussion</h4>')
        if _is_html_discussion(discussion):
            # New format: sanitize HTML, preserving our CSS classes
            sections.append(_sanitize_ai_html(discussion))
        else:
            # Old cached plain text: escape and convert newlines
            safe_discussion = _escape_html(discussion).replace('\n\n', '</p><p>').replace('\n', '<br>')
            sections.append(f'<p>{safe_discussion}</p>')

    # Safety checklist — styled as .pitfall callout box
    checklist = (output or {}).get('safety_checklist', []) or []
    if checklist:
        items = ''.join(f'<li>{_escape_html(item)}</li>' for item in checklist if item)
        if items:
            sections.append(
                '<div class="pitfall">'
                '<strong>Safety Checklist</strong>'
                f'<ul>{items}</ul>'
                '</div>'
            )

    # Sources/References — styled as .indent-block
    sources = (output or {}).get('sources', []) or []
    if sources:
        source_items = []
        for item in sources:
            title = _escape_html(item.get('title', 'Source'))
            url = item.get('url', '').strip()
            journal = _escape_html(item.get('journal', ''))
            raw_journal = (item.get('journal') or '').strip().lower()

            # Auto-resolve URL if not provided or if AI hallucinated one
            if not url or 'radiopaedia' in url:
                if 'radiopaedia' in raw_journal or 'radiopaedia' in url:
                    # Build Radiopaedia search URL from title (more reliable than AI-generated URLs)
                    search_q = _quote_plus(item.get('title', ''))
                    url = f'https://radiopaedia.org/search?q={search_q}&scope=articles'
                elif item.get('title'):
                    # Google Scholar search for journal articles
                    search_q = _quote_plus(item.get('title', ''))
                    url = f'https://scholar.google.com/scholar?q={search_q}'

            if url:
                safe_url = _escape_html(url)
                link_text = title
                if journal:
                    link_text += f' — <em>{journal}</em>'
                source_items.append(
                    f'<li>'
                    f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{link_text}</a>'
                    f'</li>'
                )
            else:
                source_items.append(f'<li>{title}{" — <em>" + journal + "</em>" if journal else ""}</li>')
        if source_items:
            sections.append(
                '<div class="indent-block">'
                '<strong>Sources &amp; References</strong>'
                f"<ul>{''.join(source_items)}</ul>"
                '</div>'
            )

    # Warnings — styled as .clinical-note callout
    warnings = (output or {}).get('warnings', []) or []
    if warnings:
        warning_text = '; '.join(_escape_html(w) for w in warnings if w)
        if warning_text:
            sections.append(
                f'<div class="clinical-note"><strong>Warnings:</strong> {warning_text}</div>'
            )

    # Close the wrapper div
    sections.append('</div>')

    return ''.join(sections)


# ==================== AI DIAGNOSIS CACHE HELPERS ====================

def check_ai_diagnosis_cache(diagnosis, provider, model_name):
    """
    Check if this diagnosis + model combination has been cached.
    Returns cache entry if exists, None otherwise.
    """
    from models import AiDiagnosisCache
    normalized_diagnosis = diagnosis.strip().lower()
    cache_entry = AiDiagnosisCache.query.filter_by(
        diagnosis=normalized_diagnosis,
        provider=provider,
        model_name=model_name
    ).first()
    return cache_entry


def get_all_models_for_diagnosis(diagnosis):
    """
    Get all models that have been used for this diagnosis.
    Returns list of dicts with provider and model_name.
    """
    from models import AiDiagnosisCache
    normalized_diagnosis = diagnosis.strip().lower()
    cache_entries = AiDiagnosisCache.query.filter_by(
        diagnosis=normalized_diagnosis
    ).all()
    return [
        {'provider': entry.provider, 'model_name': entry.model_name}
        for entry in cache_entries
    ]


def update_ai_diagnosis_cache(diagnosis, provider, model_name, case_id, user_id):
    """
    Update or create cache entry for this diagnosis + model combination.
    """
    from models import AiDiagnosisCache
    normalized_diagnosis = diagnosis.strip().lower()
    
    cache_entry = AiDiagnosisCache.query.filter_by(
        diagnosis=normalized_diagnosis,
        provider=provider,
        model_name=model_name
    ).first()
    
    if cache_entry:
        # Update existing entry
        cache_entry.query_count += 1
        cache_entry.last_queried_at = datetime.utcnow()
    else:
        # Create new entry
        cache_entry = AiDiagnosisCache(
            diagnosis=normalized_diagnosis,
            provider=provider,
            model_name=model_name,
            first_case_id=case_id,
            first_user_id=user_id,
            query_count=1,
            first_generated_at=datetime.utcnow(),
            last_queried_at=datetime.utcnow()
        )
        db.session.add(cache_entry)
    
    db.session.commit()
    return cache_entry


@app.route('/api/case/<int:case_id>/ai-prelim/check-cache', methods=['GET'])
@login_required
def check_ai_prelim_cache(case_id):
    """
    Check if AI generation for this diagnosis has been cached.
    Returns cache status and available models.
    """
    try:
        case = verify_case_ownership(case_id)
        if not case:
            return jsonify({'error': 'Unauthorized'}), 403
        
        if not case.diagnosis or not case.diagnosis.strip():
            return jsonify({
                'cached': False,
                'has_stored_data': False,
                'message': 'No diagnosis available'
            })

        # Support both model (new) and provider (legacy) parameters
        model_name = request.args.get('model', '').strip()

        # If model not specified, get default from environment (same as ai_prelim.py)
        if not model_name:
            import os
            model_name = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

        # Check for stored AI data (AiPrelimCaseData) for reload capability
        has_stored_data = False
        stored_data_info = None
        try:
            from models import AiPrelimCaseData
            stored = AiPrelimCaseData.query.filter_by(case_id=case_id).order_by(AiPrelimCaseData.created_at.desc()).first()
            if stored:
                has_stored_data = True
                stored_data_info = {
                    'provider': stored.provider,
                    'model_name': stored.model_name,
                    'generated_at': stored.created_at.isoformat() if stored.created_at else None,
                }
        except Exception:
            pass  # Table may not exist yet

        # Try to check cache, but handle case where table doesn't exist yet
        try:
            cache_entry = check_ai_diagnosis_cache(case.diagnosis, 'claude', model_name)
            all_models = get_all_models_for_diagnosis(case.diagnosis)
        except Exception as e:
            # Table might not exist yet (migration not run)
            # Return not cached so user can proceed
            return jsonify({
                'cached': False,
                'has_stored_data': has_stored_data,
                'stored_data_info': stored_data_info,
                'message': 'Cache check unavailable (migration may be pending)',
                'all_used_models': [],
                'requested_model': model_name,
            })

        return jsonify({
            'cached': cache_entry is not None,
            'has_stored_data': has_stored_data,
            'stored_data_info': stored_data_info,
            'cache_entry': {
                'provider': cache_entry.provider if cache_entry else None,
                'model_name': cache_entry.model_name if cache_entry else None,
                'first_generated_at': cache_entry.first_generated_at.isoformat() if cache_entry else None,
                'query_count': cache_entry.query_count if cache_entry else 0,
            } if cache_entry else None,
            'all_used_models': all_models,
            'requested_model': model_name,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Return not cached so user can proceed
        return jsonify({
            'cached': False,
            'has_stored_data': False,
            'error': str(e),
            'message': 'Cache check failed, proceeding anyway',
            'all_used_models': [],
        }), 200  # Return 200 so frontend doesn't treat it as error


def _apply_qa_pairs_from_output(case, output):
    """Create Question/Answer records from AI output qa_pairs. Returns list of added pairs."""
    existing_questions = Question.query.filter_by(case_id=case.id).count()
    existing_answers = Answer.query.filter_by(case_id=case.id).count()
    next_q_number = existing_questions + 1
    next_a_number = existing_answers + 1

    added_pairs = []
    for pair in output.get('qa_pairs', []) or []:
        question_text = (pair.get('question') or '').strip()
        answer_text = (pair.get('answer') or '').strip()
        if not question_text and not answer_text:
            continue

        # Wrap AI-generated Q&A in wrapper divs with data attribute
        if question_text:
            question_text = f'<div data-ai-generated="true" class="ai-generated-wrapper">{question_text}</div>'
        if answer_text:
            answer_text = f'<div data-ai-generated="true" class="ai-generated-wrapper">{answer_text}</div>'

        if question_text:
            q = Question(case_id=case.id, question_number=next_q_number, question_text=question_text)
            db.session.add(q)
            next_q_number += 1
        if answer_text:
            a = Answer(case_id=case.id, answer_number=next_a_number, answer_text=answer_text)
            db.session.add(a)
            next_a_number += 1
        added_pairs.append({'question': question_text, 'answer': answer_text})
    return added_pairs


def _apply_discussion_from_output(case, output, provider, model_name):
    """Build AI discussion HTML and append to case.discussion. Returns discussion_html string."""
    discussion_html = _build_ai_discussion_html(output, provider, model_name)
    if discussion_html:
        existing_discussion = case.discussion or ''
        separator = '\n' if existing_discussion else ''

        # Build attribution line — contributor name if case was user-submitted
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        contributor_line = ''
        if case.created_by_user_id:
            creator = User.query.get(case.created_by_user_id)
            if creator and creator.full_name:
                contributor_line = f'with inputs from <strong>{_escape_html(creator.full_name)}</strong> '
        attribution = (
            f'<p style="font-size: 0.82em; color: #8b94a3; font-style: italic; margin: 4px 0 0 0;">'
            f'Generated {contributor_line}by RadInsights Intelligence on {_escape_html(timestamp)}</p>'
        )

        footer = f'''<!-- Footer -->
<div style="background: #f3f4f6; padding: 12px 16px; border-top: 1px solid #e5e7eb; margin-top: 20px; border-radius: 0 0 8px 8px;">
    {attribution}
    <div style="display: flex; align-items: center; justify-content: flex-end; gap: 8px; margin-top: 6px;">
        <img style="width: 30px; height: 30px; object-fit: contain;" src="https://res.cloudinary.com/dx7b7chvn/image/upload/v1769503548/frcr-rev-logo-transp_o2hmrq.png" alt="RadiologyInsights Logo">
        <span style="font-size: 0.85em; color: #6b7280;">&copy; All rights reserved RadiologyInsights</span>
    </div>
</div>'''
        case.discussion = f"{existing_discussion}{separator}{discussion_html}{footer}"
    return discussion_html


@app.route('/api/case/<int:case_id>/ai-prelim', methods=['POST'])
@login_required
def generate_preliminary_case_data(case_id):
    case = verify_case_ownership(case_id)
    if not case:
        return jsonify({'error': 'Unauthorized'}), 403

    from access_control import has_case_edit_permission
    if not has_case_edit_permission(case):
        return jsonify({'error': 'Access denied'}), 403

    # Support both JSON and FormData (when PDFs are uploaded)
    if request.content_type and 'multipart/form-data' in request.content_type:
        data = request.form
    else:
        data = request.get_json() or {}

    # Support both model (new) and provider (legacy) parameters
    model = data.get('model', 'claude-sonnet-4-20250514')
    notes = (data.get('notes') or '').strip()
    force_regenerate = data.get('force_regenerate', False)
    if isinstance(force_regenerate, str):
        force_regenerate = force_regenerate.lower() not in ('false', '0', '')

    if not case.diagnosis or not case.diagnosis.strip():
        return jsonify({'error': 'Diagnosis is required'}), 400

    # Check cache (unless user explicitly chose to regenerate)
    if not force_regenerate:
        cache_entry = check_ai_diagnosis_cache(case.diagnosis, 'claude', model)
        if cache_entry:
            # Return cache warning - frontend will show dialog
            all_models = get_all_models_for_diagnosis(case.diagnosis)
            return jsonify({
                'error': 'CACHED',
                'message': f'This diagnosis has already been generated using {cache_entry.model_name}.',
                'cache_info': {
                    'provider': cache_entry.provider,
                    'model_name': cache_entry.model_name,
                    'first_generated_at': cache_entry.first_generated_at.isoformat(),
                    'query_count': cache_entry.query_count,
                },
                'all_used_models': all_models,
                'requested_model': model,
            }), 200  # 200 because this is expected behavior, not an error

    sources = [
        'https://radiologyassistant.nl',
        'https://radiopaedia.org',
        'https://www.nice.org.uk',
        'https://www.canstaging.org',
        'https://www.mdcalc.com',
    ]

    # Build additional context + extract reference images from optional user inputs
    instructions = (data.get('instructions') or '').strip()
    if request.content_type and 'multipart/form-data' in request.content_type:
        reference_urls = request.form.getlist('reference_url')
        pdf_files = request.files.getlist('pdf')
    else:
        reference_urls = data.get('reference_urls') or ([data['reference_url']] if data.get('reference_url') else [])
        pdf_files = []
    from reporting_routes import _build_generation_context
    additional_context, ref_images = _build_generation_context(instructions, reference_urls, pdf_files)

    context = {
        'diagnosis': case.diagnosis,
        'module': case.module.name if case.module else '',
        'body_part': case.body_part.name if case.body_part else '',
        'notes': notes,
        'existing_summary': case.discussion or '',
        'sources': sources,
        'additional_context': additional_context,
    }

    try:
        result = generate_prelim_case_data(context, provider='claude', model=model)
    except AiPrelimError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'error': f'RadInsights Intelligence generation failed: {exc}'}), 500

    output = result.get('output', {})

    # Fetch Radiopaedia images + combine with reference images from URL/PDF
    try:
        from ai_pearl_generator import fetch_radiopaedia_images, render_reference_images_html
        modality_str = case.module.name if case.module else ''
        rp_images = fetch_radiopaedia_images(case.diagnosis, modality=modality_str, max_images=3)
        all_images = rp_images + ref_images
        all_images = all_images[:5]
        if all_images:
            captions = output.get('image_captions', [])
            image_html = render_reference_images_html(all_images, captions)
            output['discussion'] = output.get('discussion', '') + image_html
    except Exception as img_exc:
        logger.warning("Failed to add images to case discussion: %s", img_exc)

    added_pairs = _apply_qa_pairs_from_output(case, output)
    discussion_html = _apply_discussion_from_output(case, output, result.get('provider', 'claude'), result.get('model', ''))

    from models import AiPrelimCaseData
    audit = AiPrelimCaseData(
        case_id=case.id,
        created_by_user_id=current_user.id,
        provider=result.get('provider', 'claude'),
        model_name=result.get('model', ''),
        prompt_version=result.get('prompt_version', 'v1'),
        request_payload=json.dumps(context),
        response_payload=json.dumps(result),
    )
    db.session.add(audit)

    # Update diagnosis cache
    try:
        update_ai_diagnosis_cache(
            diagnosis=case.diagnosis,
            provider=result.get('provider', 'claude'),
            model_name=result.get('model', model),
            case_id=case.id,
            user_id=current_user.id
        )
    except Exception as cache_exc:
        pass  # Log but don't fail the request if cache update fails

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return jsonify({'error': f'Failed to save AI data: {exc}'}), 500

    return jsonify({
        'success': True,
        'added_pairs': added_pairs,
        'pairs_count': len(added_pairs),
        'discussion_html': discussion_html,
        'discussion_appended': bool(discussion_html),
        'warnings': output.get('warnings', []),
        'provider': result.get('provider', 'claude'),
        'model': result.get('model', ''),
    })


@app.route('/api/case/<int:case_id>/ai-prelim/reload', methods=['POST'])
@login_required
def reload_preliminary_case_data(case_id):
    """Reload Q&A and discussion from stored AI response_payload without calling the AI again."""
    case = verify_case_ownership(case_id)
    if not case:
        return jsonify({'error': 'Unauthorized'}), 403

    from access_control import has_case_edit_permission
    if not has_case_edit_permission(case):
        return jsonify({'error': 'Access denied'}), 403

    from models import AiPrelimCaseData
    stored = AiPrelimCaseData.query.filter_by(case_id=case_id).order_by(AiPrelimCaseData.created_at.desc()).first()
    if not stored:
        return jsonify({'error': 'No stored AI data found for this case'}), 404

    try:
        result = json.loads(stored.response_payload)
    except (json.JSONDecodeError, TypeError):
        return jsonify({'error': 'Stored AI data is corrupt'}), 500

    output = result.get('output', {})

    # Delete existing Q&A for this case
    Question.query.filter_by(case_id=case.id).delete()
    Answer.query.filter_by(case_id=case.id).delete()
    # Clear discussion
    case.discussion = ''

    added_pairs = _apply_qa_pairs_from_output(case, output)
    discussion_html = _apply_discussion_from_output(case, output, stored.provider, stored.model_name)

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return jsonify({'error': f'Failed to reload AI data: {exc}'}), 500

    return jsonify({
        'success': True,
        'reloaded': True,
        'originally_generated_at': stored.created_at.isoformat() if stored.created_at else None,
        'added_pairs': added_pairs,
        'pairs_count': len(added_pairs),
        'discussion_html': discussion_html,
        'discussion_appended': bool(discussion_html),
        'provider': stored.provider,
        'model': stored.model_name,
    })


@app.route('/api/case/<int:case_id>/note', methods=['DELETE'])
@login_required
def delete_candidate_note(case_id):
    """Delete user's note for a case"""
    from models import CandidateNote
    
    note = CandidateNote.query.filter_by(case_id=case_id, user_id=current_user.id).first()
    
    if note:
        db.session.delete(note)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Note deleted'})
    
    return jsonify({'error': 'Note not found'}), 404


# ==================== CASE REFERENCES API (PUBLIC) ====================

@app.route('/api/case/<int:case_id>/references', methods=['GET'])
@login_required
def get_case_references_public(case_id):
    """Get all references for a case (for viewing)"""
    from models import Case, CaseReference
    
    case = Case.query.get_or_404(case_id)
    references = CaseReference.query.filter_by(case_id=case_id).order_by(CaseReference.ref_number).all()
    
    return jsonify({
        'success': True,
        'case_id': case_id,
        'references': [ref.to_dict() for ref in references]
    })


# ==================== TNM REFERENCES API (PUBLIC) ====================

@app.route('/api/tnm/<int:disease_site_id>/references', methods=['GET'])
@login_required
def get_tnm_references_public(disease_site_id):
    """Get all references for a TNM disease site (for viewing by students and admins)"""
    from models import AJCCDiseaseSite, TnmReference
    
    disease = AJCCDiseaseSite.query.get_or_404(disease_site_id)
    references = TnmReference.query.filter_by(disease_site_id=disease_site_id).order_by(TnmReference.ref_number).all()
    
    return jsonify({
        'success': True,
        'disease_site_id': disease_site_id,
        'references': [ref.to_dict() for ref in references]
    })


# ==================== TEXT HIGHLIGHTS API ====================

@app.route('/api/case/<int:case_id>/highlights', methods=['GET'])
@login_required
def get_highlights(case_id):
    """Get all highlights for a case by current user"""
    from models import TextHighlight
    
    highlights = TextHighlight.query.filter_by(case_id=case_id, user_id=current_user.id).all()
    
    return jsonify({
        'success': True,
        'highlights': [{
            'id': h.id,
            'text_content': h.text_content,
            'highlight_color': h.highlight_color,
            'field_name': h.field_name,
            'context_before': h.context_before,
            'context_after': h.context_after,
            'created_at': h.created_at.isoformat() if h.created_at else None
        } for h in highlights]
    })


@app.route('/api/case/<int:case_id>/highlight', methods=['POST'])
@login_required
def add_highlight(case_id):
    """Add a new text highlight"""
    from models import TextHighlight
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid or missing JSON data'}), 400
    
    text_content = data.get('text_content', '').strip()
    highlight_color = data.get('highlight_color', 'yellow')
    field_name = data.get('field_name', 'discussion')
    context_before = data.get('context_before', '')[:100] if data.get('context_before') else None
    context_after = data.get('context_after', '')[:100] if data.get('context_after') else None
    
    if not text_content:
        return jsonify({'error': 'Text content required'}), 400
    
    # Validate color
    valid_colors = ['yellow', 'green', 'pink', 'blue']
    if highlight_color not in valid_colors:
        return jsonify({'error': 'Invalid color'}), 400
    
    highlight = TextHighlight(
        case_id=case_id,
        user_id=current_user.id,
        text_content=text_content,
        highlight_color=highlight_color,
        field_name=field_name,
        context_before=context_before,
        context_after=context_after
    )
    
    db.session.add(highlight)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'highlight': {
            'id': highlight.id,
            'text_content': highlight.text_content,
            'highlight_color': highlight.highlight_color,
            'field_name': highlight.field_name,
            'context_before': highlight.context_before,
            'context_after': highlight.context_after
        }
    })


@app.route('/api/highlight/<int:highlight_id>', methods=['DELETE'])
@login_required
def delete_highlight(highlight_id):
    """Delete a highlight"""
    from models import TextHighlight
    
    highlight = TextHighlight.query.get(highlight_id)
    
    if not highlight:
        return jsonify({'error': 'Highlight not found'}), 404
    
    # Verify ownership
    if highlight.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    db.session.delete(highlight)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Highlight deleted'})


# ==================== FORUM API ====================

@app.route('/api/case/<int:case_id>/forum/messages', methods=['GET'])
@login_required
def get_forum_messages(case_id):
    """Get all forum messages for a case, sorted by votes (pinned first)"""
    from models import ForumMessage, ForumMessageVote
    
    # Get all non-deleted messages for this case
    messages = ForumMessage.query.filter_by(
        case_id=case_id, 
        is_deleted=False
    ).all()
    
    # Get current user's votes for these messages
    user_votes = {}
    if current_user.is_authenticated:
        votes = ForumMessageVote.query.filter(
            ForumMessageVote.message_id.in_([m.id for m in messages]),
            ForumMessageVote.user_id == current_user.id
        ).all()
        user_votes = {v.message_id: v.vote_value for v in votes}
    
    # Format response
    result = []
    for msg in messages:
        result.append({
            'id': msg.id,
            'content': msg.content,
            'vote_score': msg.vote_score,
            'is_pinned': msg.is_pinned,
            'user_vote': user_votes.get(msg.id, 0),
            'author_name': msg.author.get_display_name() if msg.author else 'User',
            'author_id': msg.user_id,
            'author_avatar': msg.author.profile_picture if msg.author and msg.author.profile_picture else None,
            'is_own': msg.user_id == current_user.id,
            'image_url': msg.image_url,
            'image_thumbnail_url': msg.image_thumbnail_url,
            'flag_count': msg.flag_count or 0,
            'created_at': msg.created_at.isoformat() if msg.created_at else None
        })
    
    # Sort: pinned first, then by vote_score desc, then by created_at desc (newest first as tiebreaker)
    # Using Python's stable sort: first sort by tiebreaker, then by primary keys
    result.sort(key=lambda x: x['created_at'] or '', reverse=True)  # Newest first (tiebreaker)
    result.sort(key=lambda x: (-int(x['is_pinned']), -x['vote_score']))  # Primary sort (stable)
    
    return jsonify({'success': True, 'messages': result})


@app.route('/api/case/<int:case_id>/forum/message', methods=['POST'])
@login_required
def post_forum_message(case_id):
    """Post a new forum message (with optional image)"""
    from models import ForumMessage
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid or missing JSON data'}), 400
    
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'error': 'Message content required'}), 400
    
    # Limit message length
    if len(content) > 5000:
        return jsonify({'error': 'Message too long (max 5000 characters)'}), 400
    
    # Optional image fields (from Cloudinary upload)
    image_url = data.get('image_url')
    image_public_id = data.get('image_public_id')
    image_thumbnail_url = data.get('image_thumbnail_url')
    
    message = ForumMessage(
        case_id=case_id,
        user_id=current_user.id,
        content=content,
        vote_score=0,
        is_pinned=False,
        image_url=image_url,
        image_public_id=image_public_id,
        image_thumbnail_url=image_thumbnail_url
    )
    
    db.session.add(message)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': {
            'id': message.id,
            'content': message.content,
            'vote_score': message.vote_score,
            'is_pinned': message.is_pinned,
            'user_vote': 0,
            'author_name': current_user.get_display_name(),
            'author_id': current_user.id,
            'author_avatar': current_user.profile_picture if current_user.profile_picture else None,
            'is_own': True,
            'image_url': message.image_url,
            'image_thumbnail_url': message.image_thumbnail_url,
            'created_at': message.created_at.isoformat()
        }
    })


@app.route('/api/forum/message/<int:message_id>/vote', methods=['POST'])
@login_required
def vote_forum_message(message_id):
    """Vote on a forum message (+1 upvote, -1 downvote, 0 remove vote)"""
    from models import ForumMessage, ForumMessageVote
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid or missing JSON data'}), 400
    
    vote_value = data.get('vote', 0)
    if vote_value not in [-1, 0, 1]:
        return jsonify({'error': 'Invalid vote value'}), 400
    
    message = ForumMessage.query.get(message_id)
    if not message or message.is_deleted:
        return jsonify({'error': 'Message not found'}), 404
    
    # Check for existing vote
    existing_vote = ForumMessageVote.query.filter_by(
        message_id=message_id,
        user_id=current_user.id
    ).first()
    
    old_vote_value = existing_vote.vote_value if existing_vote else 0
    
    if vote_value == 0:
        # Remove vote
        if existing_vote:
            message.vote_score -= existing_vote.vote_value
            db.session.delete(existing_vote)
    elif existing_vote:
        # Update existing vote
        message.vote_score -= existing_vote.vote_value
        message.vote_score += vote_value
        existing_vote.vote_value = vote_value
    else:
        # New vote
        new_vote = ForumMessageVote(
            message_id=message_id,
            user_id=current_user.id,
            vote_value=vote_value
        )
        db.session.add(new_vote)
        message.vote_score += vote_value
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'new_score': message.vote_score,
        'user_vote': vote_value
    })


@app.route('/api/forum/message/<int:message_id>/pin', methods=['POST'])
@login_required
def toggle_pin_forum_message(message_id):
    """Toggle pin status of a forum message (admin only)"""
    from models import ForumMessage, UserRole
    
    # Check admin permission
    if current_user.role != UserRole.ADMIN:
        return jsonify({'error': 'Admin access required'}), 403
    
    message = ForumMessage.query.get(message_id)
    if not message or message.is_deleted:
        return jsonify({'error': 'Message not found'}), 404
    
    message.is_pinned = not message.is_pinned
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_pinned': message.is_pinned
    })


@app.route('/api/forum/message/<int:message_id>', methods=['DELETE'])
@login_required
def delete_forum_message(message_id):
    """Delete (soft) a forum message - own messages or admin"""
    from models import ForumMessage, UserRole
    
    message = ForumMessage.query.get(message_id)
    if not message:
        return jsonify({'error': 'Message not found'}), 404
    
    # Check permission: own message or admin
    is_admin = current_user.role == UserRole.ADMIN
    if message.user_id != current_user.id and not is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Delete Cloudinary image if present
    if message.image_public_id:
        try:
            cloudinary.uploader.destroy(message.image_public_id)
        except Exception as e:
            # Log but don't fail the delete operation
            logger.warning(f"Failed to delete Cloudinary image {message.image_public_id}: {e}")
    
    message.is_deleted = True
    message.image_url = None
    message.image_thumbnail_url = None
    message.image_public_id = None
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Message deleted'})


@app.route('/api/forum/message/<int:message_id>/flag', methods=['POST'])
@login_required
def flag_forum_message(message_id):
    """Flag a forum message for moderation"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid or missing JSON data'}), 400
    
    reason = data.get('reason', '').strip()
    if not reason or reason not in ['spam', 'inappropriate', 'incorrect', 'other']:
        return jsonify({'error': 'Invalid flag reason'}), 400
    
    details = data.get('details', '').strip()[:500]  # Limit to 500 chars
    
    message = ForumMessage.query.get(message_id)
    if not message or message.is_deleted:
        return jsonify({'error': 'Message not found'}), 404
    
    # Can't flag your own message
    if message.user_id == current_user.id:
        return jsonify({'error': 'Cannot flag your own message'}), 400
    
    # Check if already flagged by this user
    existing_flag = ForumMessageFlag.query.filter_by(
        message_id=message_id,
        user_id=current_user.id
    ).first()
    
    if existing_flag:
        return jsonify({'error': 'You have already flagged this message'}), 400
    
    # Create flag
    flag = ForumMessageFlag(
        message_id=message_id,
        user_id=current_user.id,
        reason=reason,
        details=details if details else None
    )
    db.session.add(flag)
    
    # Update flag count on message
    message.flag_count = (message.flag_count or 0) + 1
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Message flagged for review',
        'flag_count': message.flag_count
    })


@app.route('/api/forum/upload-image', methods=['POST'])
@login_required
def upload_forum_image():
    """Upload an image to Cloudinary for forum messages"""
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    file = request.files['image']
    
    if not file or not file.filename:
        return jsonify({'error': 'No image selected'}), 400
    
    # Validate file type (content-type header)
    allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
    if file.content_type not in allowed_types:
        return jsonify({'error': 'Invalid image type. Allowed: jpg, png, gif, webp'}), 400

    # Validate magic bytes (defense-in-depth — content-type is spoofable)
    detected_mime = _validate_image_magic(file)
    if not detected_mime:
        return jsonify({'error': 'File content does not match an allowed image format'}), 400

    # Check file size (read into memory to check, max 2MB)
    file_data = file.read()
    if len(file_data) > 2 * 1024 * 1024:
        return jsonify({'error': 'Image too large (max 2MB)'}), 400

    # Strip EXIF metadata (GPS, device info) before upload
    import io as _io
    file_data = _strip_exif(_io.BytesIO(file_data)).read()

    # Check if Cloudinary is configured
    if not os.environ.get('CLOUDINARY_CLOUD_NAME'):
        return jsonify({'error': 'Image upload not configured'}), 500

    try:
        # Upload to Cloudinary with auto-thumbnail
        result = cloudinary.uploader.upload(
            file_data,
            folder='frcr_revision/frcr_forum',
            transformation=[{'width': 800, 'crop': 'limit'}],  # Limit size
            eager=[{'width': 80, 'height': 80, 'crop': 'fill'}]  # Generate thumbnail
        )
        
        thumbnail_url = result.get('eager', [{}])[0].get('secure_url', result['secure_url'])
        
        return jsonify({
            'success': True,
            'image_url': result['secure_url'],
            'thumbnail_url': thumbnail_url,
            'public_id': result['public_id']
        })
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500


# ==================== ADMIN FORUM MANAGEMENT ENDPOINTS ====================

@app.route('/api/admin/forum/messages', methods=['GET'])
@login_required
def admin_get_forum_messages():
    """Get all forum messages with filters (admin only)"""
    if current_user.role != UserRole.ADMIN:
        return jsonify({'error': 'Admin access required'}), 403
    
    # Query parameters
    case_id = request.args.get('case_id', type=int)
    flagged_only = request.args.get('flagged_only', 'false').lower() == 'true'
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = ForumMessage.query.filter_by(is_deleted=False)
    
    if case_id:
        query = query.filter_by(case_id=case_id)
    
    if flagged_only:
        query = query.filter(ForumMessage.flag_count > 0)
    
    # Order by flag count desc, then created_at desc
    query = query.order_by(ForumMessage.flag_count.desc(), ForumMessage.created_at.desc())
    
    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    messages = pagination.items
    
    result = []
    for msg in messages:
        # Get case info
        case = Case.query.get(msg.case_id)
        case_number = case.case_number if case else 'Unknown'
        
        # Get author info
        author = User.query.get(msg.user_id)
        author_name = author.get_display_name() if author else 'Unknown'
        
        # Get flags for this message
        flags = ForumMessageFlag.query.filter_by(message_id=msg.id, is_resolved=False).all()
        flag_details = [{
            'id': f.id,
            'reason': f.reason,
            'details': f.details,
            'created_at': f.created_at.isoformat(),
            'flagger_name': User.query.get(f.user_id).get_display_name() if User.query.get(f.user_id) else 'Unknown'
        } for f in flags]
        
        result.append({
            'id': msg.id,
            'case_id': msg.case_id,
            'case_number': case_number,
            'content': msg.content[:200] + '...' if len(msg.content) > 200 else msg.content,
            'full_content': msg.content,
            'author_id': msg.user_id,
            'author_name': author_name,
            'vote_score': msg.vote_score,
            'is_pinned': msg.is_pinned,
            'flag_count': msg.flag_count or 0,
            'flags': flag_details,
            'image_url': msg.image_url,
            'image_thumbnail_url': msg.image_thumbnail_url,
            'created_at': msg.created_at.isoformat()
        })
    
    # Get total flagged messages count (for badge display regardless of current filter)
    total_flagged = ForumMessage.query.filter(
        ForumMessage.is_deleted == False,
        ForumMessage.flag_count > 0
    ).count()
    
    return jsonify({
        'success': True,
        'messages': result,
        'total': pagination.total,
        'total_flagged': total_flagged,
        'pages': pagination.pages,
        'current_page': page
    })


@app.route('/api/admin/forum/flagged', methods=['GET'])
@login_required
def admin_get_flagged_messages():
    """Get only flagged forum messages (admin only)"""
    if current_user.role != UserRole.ADMIN:
        return jsonify({'error': 'Admin access required'}), 403
    
    # Get messages with unresolved flags
    messages = ForumMessage.query.filter(
        ForumMessage.is_deleted == False,
        ForumMessage.flag_count > 0
    ).order_by(ForumMessage.flag_count.desc(), ForumMessage.created_at.desc()).all()
    
    result = []
    for msg in messages:
        case = Case.query.get(msg.case_id)
        author = User.query.get(msg.user_id)
        
        flags = ForumMessageFlag.query.filter_by(message_id=msg.id, is_resolved=False).all()
        flag_details = [{
            'id': f.id,
            'reason': f.reason,
            'details': f.details,
            'created_at': f.created_at.isoformat()
        } for f in flags]
        
        result.append({
            'id': msg.id,
            'case_id': msg.case_id,
            'case_number': case.case_number if case else 'Unknown',
            'content': msg.content,
            'author_name': author.get_display_name() if author else 'Unknown',
            'vote_score': msg.vote_score,
            'is_pinned': msg.is_pinned,
            'flag_count': msg.flag_count or 0,
            'flags': flag_details,
            'created_at': msg.created_at.isoformat()
        })
    
    return jsonify({
        'success': True,
        'messages': result,
        'total': len(result),
        'total_flagged': len(result)  # Same as total for this endpoint
    })


@app.route('/api/admin/forum/flag/<int:flag_id>/resolve', methods=['POST'])
@login_required
def admin_resolve_flag(flag_id):
    """Resolve (dismiss) a flag on a forum message (admin only)"""
    if current_user.role != UserRole.ADMIN:
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.get_json() or {}
    resolution_notes = data.get('notes', '').strip()[:500]
    
    flag = ForumMessageFlag.query.get(flag_id)
    if not flag:
        return jsonify({'error': 'Flag not found'}), 404
    
    # Get current unresolved count BEFORE marking as resolved (to avoid off-by-one error)
    message = ForumMessage.query.get(flag.message_id)
    current_unresolved = ForumMessageFlag.query.filter_by(
        message_id=flag.message_id,
        is_resolved=False
    ).count() if message else 0
    
    flag.is_resolved = True
    flag.resolved_by_user_id = current_user.id
    flag.resolved_at = datetime.utcnow()
    flag.resolution_notes = resolution_notes if resolution_notes else None
    
    # Update flag count on message (subtract 1 since we just resolved this flag)
    if message:
        message.flag_count = max(0, current_unresolved - 1)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Flag resolved',
        'remaining_flags': message.flag_count if message else 0
    })


@app.route('/api/admin/forum/message/<int:message_id>/resolve-all-flags', methods=['POST'])
@login_required
def admin_resolve_all_flags(message_id):
    """Resolve all flags on a forum message (admin only)"""
    if current_user.role != UserRole.ADMIN:
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.get_json() or {}
    resolution_notes = data.get('notes', '').strip()[:500]
    
    message = ForumMessage.query.get(message_id)
    if not message:
        return jsonify({'error': 'Message not found'}), 404
    
    # Resolve all unresolved flags
    flags = ForumMessageFlag.query.filter_by(message_id=message_id, is_resolved=False).all()
    for flag in flags:
        flag.is_resolved = True
        flag.resolved_by_user_id = current_user.id
        flag.resolved_at = datetime.utcnow()
        flag.resolution_notes = resolution_notes if resolution_notes else None
    
    message.flag_count = 0
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Resolved {len(flags)} flag(s)',
        'resolved_count': len(flags)
    })


# ==================== ADMIN ENDPOINTS ====================

@app.route('/api/admin/migrate-db', methods=['POST'])
def migrate_db():
    """Create database tables if they don't exist"""
    try:
        logger.info("Running database migration...")
        db.create_all()
        logger.info("Database migration complete")
        return jsonify({'success': True, 'message': 'Database tables created'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring and uptime checks."""
    health = {'status': 'ok', 'app': 'RadInsights'}
    try:
        db.session.execute(db.text('SELECT 1'))
        health['database'] = 'ok'
    except Exception as e:
        health['status'] = 'degraded'
        health['database'] = 'error'
        logger.error(f"Health check DB error: {e}")
    return jsonify(health), 200 if health['status'] == 'ok' else 503


@app.route('/robots.txt', methods=['GET'])
def robots_txt():
    """Serve robots.txt to prevent search engines crawling admin/API routes."""
    content = """User-agent: *
Allow: /
Disallow: /api/
Disallow: /auth/
Disallow: /admin/
Disallow: /on-call-helper/admin/
Disallow: /incidental-findings/admin/
Disallow: /api/admin/
Disallow: /api/backup/
Disallow: /health

Sitemap: https://radinsights.co.uk/sitemap.xml
"""
    return content, 200, {'Content-Type': 'text/plain'}


@app.route('/sitemap.xml', methods=['GET'])
def sitemap_xml():
    """Generate sitemap.xml for search engines."""
    pages = [
        ('/', '1.0', 'monthly'),
        ('/smart-reporter', '0.9', 'weekly'),
        ('/radiology-protocols', '0.8', 'weekly'),
        ('/reporting-algorithms', '0.8', 'weekly'),
        ('/reporting-templates', '0.8', 'weekly'),
        ('/radiology-tools', '0.8', 'weekly'),
        ('/on-call-helper', '0.7', 'monthly'),
        ('/privacy-policy', '0.3', 'yearly'),
        ('/terms-of-use', '0.3', 'yearly'),
    ]

    # Add public TNM calculator pages
    try:
        from models import TNMCalculator
        calcs = TNMCalculator.query.filter_by(is_available=True).all()
        for c in calcs:
            pages.append((f'/tnm-calculator/{c.slug}', '0.7', 'monthly'))
    except Exception:
        pass

    base_url = 'https://radinsights.co.uk'
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for path, priority, freq in pages:
        xml += f'  <url>\n    <loc>{base_url}{path}</loc>\n'
        xml += f'    <priority>{priority}</priority>\n'
        xml += f'    <changefreq>{freq}</changefreq>\n  </url>\n'
    xml += '</urlset>'
    return xml, 200, {'Content-Type': 'application/xml'}


@app.errorhandler(404)
def page_not_found(e):
    """Branded 404 error page."""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    return render_template('errors/404.html'), 404


@app.errorhandler(403)
def access_denied(e):
    """Branded 403 error page."""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Access denied'}), 403
    return render_template('errors/403.html'), 403


@app.errorhandler(500)
def internal_server_error(e):
    """Branded 500 error page."""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('errors/500.html'), 500


@app.errorhandler(413)
def request_entity_too_large(e):
    """Return JSON for 413 so upload UI can show a helpful message."""
    return jsonify({
        'error': 'Upload too large. Limit is {}MB. Try fewer images per series or upload in batches.'.format(
            app.config.get('MAX_CONTENT_LENGTH', 0) // (1024 * 1024)
        )
    }), 413


if __name__ == '__main__':
    if sys.platform == 'darwin':
        show_macos_gatekeeper_popup()
    port = find_free_port(5000, 20)
    logger.info(f"Starting server on http://127.0.0.1:{port}")
    app.run(debug=True, host='127.0.0.1', port=port)