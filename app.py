# Load environment variables from .env file (must be first!)
from dotenv import load_dotenv
load_dotenv()

# ==================== STUDENT CASE BROWSER ====================
# (Moved below app initialization)
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file, send_from_directory, flash
from models import UserRole
from flask_cors import CORS
from flask_login import LoginManager, login_required, current_user
from flask_migrate import Migrate
from models import db, User, Case, CaseImage, Question, Answer
from models import RevisionSession, RevisionHistory  # STUDENT REVISION: New models for balanced revision
from models import ForumMessage, ForumMessageVote, ForumMessageFlag  # Forum models
from auth import auth_bp
from backup_routes import backup_bp
from admin_routes import admin_bp
from admin_enrichment_routes import enrichment_bp
from notes_integration_routes import notes_bp
from resources_routes import resources_bp
# AJCC TNM Module - imports blueprints from the reusable module
from ajcc_tnm import get_blueprints, init_app as init_ajcc_tnm
admin_tnm_bp, tnm_bp = get_blueprints()
from ai_prelim import AiPrelimError, generate_prelim_case_data
from datetime import datetime
from sqlalchemy.pool import NullPool
import os
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
# Use PostgreSQL on production (Vercel/Neon), SQLite locally
# Production envs can be POSTGRES_URL(_NON_POOLING) or DATABASE_* variants
# Priority: Use non-pooling URL first for serverless environments
DATABASE_URL = (
    os.getenv('DATABASE_POSTGRES_URL_NON_POOLING')
    or os.getenv('POSTGRES_URL_NON_POOLING')
    or os.getenv('DATABASE_URL')
    or os.getenv('POSTGRES_URL')
    or os.getenv('DATABASE_POSTGRES_URL')
)

if DATABASE_URL:
    # PostgreSQL on Vercel or external
    print(f"[DB] Using PostgreSQL: {DATABASE_URL[:60]}...")
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
    
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    
    # For serverless environments (Vercel), disable connection pooling
    # Each function invocation should create and close its own connection
    if os.getenv('VERCEL'):
        print("[DB] Serverless environment detected - using NullPool")
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'poolclass': NullPool,  # No connection pooling for serverless
            'pool_pre_ping': True,  # Verify connections before using
        }
else:
    # SQLite for local development
    print(f"[DB] Using SQLite: {instance_path}/frcr_examiner.db")
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "frcr_examiner.db")}'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Session configuration
# Check if SECRET_KEY is set
if not os.getenv('SECRET_KEY'):
    print("[WARNING] SECRET_KEY not set! Using default insecure key")
else:
    print("[OK] SECRET_KEY is set")

# Only set SECURE in production (HTTPS)
is_production = os.getenv('VERCEL_ENV') == 'production' or 'vercel.app' in os.getenv('VERCEL_URL', '')

# Session cookie configuration (for regular sessions)
app.config['SESSION_COOKIE_SECURE'] = is_production  # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True  # No JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
app.config['SESSION_COOKIE_NAME'] = 'frcr_session'  # Explicit name
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes session timeout

# Flask-Login "Remember Me" cookie configuration
# These settings control persistent login when user checks "Remember Me"
from datetime import timedelta
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=7)  # 7 days if "Remember Me" checked
app.config['REMEMBER_COOKIE_SECURE'] = is_production  # HTTPS only in production
app.config['REMEMBER_COOKIE_HTTPONLY'] = True  # No JavaScript access
app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
app.config['REMEMBER_COOKIE_NAME'] = 'frcr_remember'  # Explicit name

print(f"[SESSION] SECURE={app.config['SESSION_COOKIE_SECURE']}, REMEMBER_DAYS={app.config['REMEMBER_COOKIE_DURATION'].days}")

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
    return User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized():
    """Handle unauthorized access - redirect to login"""
    from flask import redirect, url_for, request
    # If it's an AJAX request, return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'Login required'}), 401
    # Otherwise redirect to login
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
            print(f"[ADMIN] Superadmin exists: {SUPERADMIN_EMAIL}")
            return
    except Exception as e:
        # Table doesn't exist yet or other error
        print(f"[ADMIN] Check superadmin error (may be normal): {e}")
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
        
        # Print password ONCE - this is the only time it will be visible
        print("\n" + "=" * 60)
        print("[ADMIN] SUPERADMIN ACCOUNT CREATED")
        print("=" * 60)
        print(f"  Email:    {SUPERADMIN_EMAIL}")
        print(f"  Password: {password}")
        print(f"  Role:     SUPERADMIN (highest privileges)")
        print("=" * 60)
        print("  ⚠️  SAVE THIS PASSWORD NOW - IT WILL NOT BE SHOWN AGAIN!")
        print("  ⚠️  Change this password immediately after first login.")
        print("=" * 60 + "\n")
        
    except Exception as e:
        db.session.rollback()
        print(f"[ADMIN] Error creating superadmin: {e}")


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
    
    # Body sections
    BODY_SECTIONS = [
        ("Head and Neck", "head-and-neck"),
        ("Thorax", "thorax"),
        ("Lower Gastrointestinal Tract", "lower-gastrointestinal-tract"),
        ("Upper Gastrointestinal Tract", "upper-gastrointestinal-tract"),
        ("Hepatobiliary System", "hepatobiliary-system"),
        ("Breast", "breast"),
        ("Urinary System", "urinary-system"),
        ("Male Reproductive Organs", "male-reproductive-organs"),
        ("Female Reproductive Organs", "female-reproductive-organs"),
        ("Endocrine System", "endocrine-system"),
        ("Bone", "bone"),
        ("Soft Tissue Sarcoma", "soft-tissue-sarcoma"),
        ("Skin", "skin"),
        ("Neuroendocrine Tumors", "neuroendocrine-tumors"),
        ("Central Nervous System", "central-nervous-system"),
    ]
    
    # Disease sites by section
    DISEASE_SITES = {
        "head-and-neck": [
            ("Larynx", "larynx", "head-and-neck/larynx"),
            ("Oral Cavity", "oral-cavity", "head-and-neck/oral-cavity"),
            ("Oropharynx (HPV-Mediated)", "oropharynx-hpv-mediated", "head-and-neck/oropharynx-hpv-mediated"),
            ("Nasopharynx", "nasopharynx", "head-and-neck/nasopharynx"),
            ("Hypopharynx", "hypopharynx", "head-and-neck/hypopharynx"),
        ],
        "thorax": [("Lung", "lung", "thorax/lung")],
        "breast": [("Breast", "breast", "breast/breast")],
        "upper-gastrointestinal-tract": [
            ("Esophagus and Esophagogastric Junction", "esophagus", "upper-gastrointestinal-tract/esophagus"),
            ("Stomach", "stomach", "upper-gastrointestinal-tract/stomach"),
        ],
        "lower-gastrointestinal-tract": [("Colon and Rectum", "colon-and-rectum", "lower-gastrointestinal-tract/colon-and-rectum")],
        "hepatobiliary-system": [
            ("Liver", "liver", "hepatobiliary-system/liver"),
            ("Pancreas", "pancreas", "hepatobiliary-system/pancreas"),
        ],
        "urinary-system": [
            ("Kidney", "kidney", "urinary-system/kidney"),
            ("Urinary Bladder", "bladder", "urinary-system/bladder"),
        ],
        "male-reproductive-organs": [
            ("Prostate", "prostate", "male-reproductive-organs/prostate"),
            ("Testis", "testis", "male-reproductive-organs/testis"),
        ],
        "female-reproductive-organs": [
            ("Cervix Uteri", "cervix", "female-reproductive-organs/cervix"),
            ("Ovary", "ovary", "female-reproductive-organs/ovary"),
        ],
        "endocrine-system": [("Thyroid", "thyroid", "endocrine-system/thyroid")],
        "bone": [("Bone", "bone", "bone/bone")],
        "soft-tissue-sarcoma": [("Soft Tissue Sarcoma", "soft-tissue", "soft-tissue-sarcoma/soft-tissue")],
        "skin": [("Cutaneous Melanoma", "melanoma", "skin/melanoma")],
        "central-nervous-system": [("Brain and Spinal Cord", "brain", "central-nervous-system/brain")],
    }
    
    # Use raw SQL for count to avoid model column mismatch during migrations
    try:
        existing_sections = db.session.execute(text("SELECT COUNT(*) FROM ajcc_body_section")).scalar() or 0
        existing_sites = db.session.execute(text("SELECT COUNT(*) FROM ajcc_disease_site")).scalar() or 0
    except Exception as e:
        # Tables don't exist yet
        print(f"[SEED] AJCC tables check error (may be normal): {e}")
        db.session.rollback()
        existing_sections = 0
        existing_sites = 0
    
    # Count expected disease sites
    expected_sites = sum(len(diseases) for diseases in DISEASE_SITES.values())
    
    # Check if we need to add missing entries (incremental seeding)
    if existing_sections >= len(BODY_SECTIONS) and existing_sites >= expected_sites:
        print(f"[SEED] AJCC data complete: {existing_sections} sections, {existing_sites} sites")
        return
    
    print(f"[SEED] Adding missing AJCC data (have {existing_sections}/{len(BODY_SECTIONS)} sections, {existing_sites}/{expected_sites} sites)...")
    
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
        
        final_sections = AJCCBodySection.query.count()
        final_sites = AJCCDiseaseSite.query.count()
        if added_sites > 0:
            print(f"[SEED] Added {added_sites} new disease sites. Total: {final_sections} sections, {final_sites} disease sites")
        else:
            print(f"[SEED] Complete: {final_sections} sections, {final_sites} disease sites")
        
    except Exception as e:
        db.session.rollback()
        print(f"[SEED] Error seeding AJCC data: {e}")


# ==================== DATABASE INITIALIZATION ====================

with app.app_context():
    try:
        db.create_all()
        
        # Auto-seed AJCC body sections and disease sites if not present
        _seed_ajcc_data_if_needed()
        
        # Ensure superadmin account exists
        _ensure_superadmin_exists()
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise


# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(backup_bp)
app.register_blueprint(admin_bp)  # Sprint 2: Admin user management
app.register_blueprint(enrichment_bp)  # Data migration: Import, enrich, promote cases
app.register_blueprint(notes_bp)  # Notion + Anki integration for student notes
app.register_blueprint(resources_bp)  # PubMed, TCIA, RadiologyAssistant resources
# Initialize AJCC TNM module and register its blueprints
init_ajcc_tnm(app)
app.register_blueprint(admin_tnm_bp)  # AJCC TNM staging system - admin routes
app.register_blueprint(tnm_bp)  # AJCC TNM staging system - public routes


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


@app.route('/manifest.json')
def manifest():
    """Serve manifest.json with correct MIME type for PWA installation."""
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')


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
    """Show cases filtered by module"""
    from models import FRCRModule, BodyPart, Case, CandidateNote
    
    # Validate module
    try:
        module_enum = FRCRModule[module]
    except KeyError:
        return redirect(url_for('modules_view'))
    
    # Get filters from query params
    body_part_filter = request.args.get('body_part', '')
    search_query = request.args.get('q', '')
    
    # Build query
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

    cases = query.order_by(Case.id.desc()).all()

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
                           list_source='admin')


@app.route('/student-cases')
@login_required
def student_cases_list():
    from models import BodyPart, AgeGroup, FRCRModule, CandidateNote, CaseFlag, CaseStatus

    module_filter = request.args.get('module', '')
    body_part_filter = request.args.get('body_part', '')
    age_group_filter = request.args.get('age_group', '')
    search_query = request.args.get('q', '')
    flagged_filter = request.args.get('flagged') == '1'

    query = Case.query.filter_by(status=CaseStatus.PUBLISHED)

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
        case = Case(
            case_number=case_number,
            diagnosis=data['diagnosis'],
            discussion=data.get('discussion', ''),
            module=module_enum,
            body_part=body_part_enum,
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
    
    
    return render_template('view_case.html', 
                         case=case, 
                         user_note=user_note,
                         previous_case_id=prev_case_id,
                         next_case_id=next_case_id,
                         from_staging=from_staging,
                         nav_params=nav_params,
                         nav_query_string=nav_query_string)


@app.route('/edit-case')
def edit_case():
    """Full-page edit interface for a case or staging case"""
    case_id = request.args.get('id', type=int)
    staging_id = request.args.get('staging_id', type=int)
    is_new = request.args.get('new', 'false').lower() == 'true'
    return_to = request.args.get('returnTo', url_for('dashboard'))
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
    
    return render_template('edit_case.html', 
                         is_new=is_new,
                         return_to=return_to,
                         case=case,
                         staging_case=staging_case,
                         prev_staging_id=prev_staging_id,
                         next_staging_id=next_staging_id,
                         status_filter=status_filter)




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
                    print(f"Warning: Failed to delete Cloudinary image {msg.image_public_id}: {e}")
        
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
    
    # Check file type
    allowed_types = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    file_type = mimetypes.guess_type(file.filename)[0]
    
    if file_type not in allowed_types:
        return jsonify({'error': 'Only image files (JPEG, PNG, GIF, WebP) are allowed'}), 400
    
    # Get description from form data
    description = request.form.get('description', '')
    
    try:
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file,
            folder='frcr_cases',
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
            image_filename=file.filename,
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
            print(f"Warning: Failed to delete Cloudinary image {image.image_public_id}: {e}")
    
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
            'is_public': case.is_public,
            'status': case.status.name if case.status else 'DRAFT'
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


def _build_ai_discussion_html(output, provider, model_name):
    """
    Build HTML for AI-generated discussion content.
    
    Uses wrapper div with data-ai-generated="true" attribute for simple detection and removal.
    The wrapper provides visual distinction (orange background) and is removed when 
    the case is saved and published, making the content appear as normal text.
    """
    sections = []
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    
    # Wrap entire AI-generated content in a single wrapper div with data attribute
    sections.append('<div data-ai-generated="true" class="ai-generated-wrapper">')
    
    # Header with AI attribution
    header = (
        '<hr style="border-top: 2px solid #dc3545; margin: 0.5rem 0;">'
        '<h3>AI Preliminary Case Data</h3>'
        f'<p><em>Generated by { _escape_html(provider) } ({ _escape_html(model_name) })'
        f' on { _escape_html(timestamp) }.</em></p>'
    )
    sections.append(header)

    # Discussion section
    discussion = (output or {}).get('discussion', '')
    if discussion:
        sections.append('<h4>Discussion</h4>')
        # Format discussion with better paragraph handling
        safe_discussion = _escape_html(discussion).replace('\n\n', '</p><p>').replace('\n', '<br>')
        sections.append(f'<p>{safe_discussion}</p>')

    # Safety checklist
    checklist = (output or {}).get('safety_checklist', []) or []
    if checklist:
        sections.append('<h4>Clinico-Radiological Safety Focus</h4>')
        items = ''.join(f'<li>{_escape_html(item)}</li>' for item in checklist if item)
        if items:
            sections.append(f'<ul>{items}</ul>')

    # Teaching image
    teaching = (output or {}).get('teaching_image', {}) or {}
    if teaching and any(teaching.values()):
        title = _escape_html(teaching.get('title', ''))
        link = teaching.get('link', '')  # Don't escape yet - need for href
        description = _escape_html(teaching.get('description', ''))
        teaching_point = _escape_html(teaching.get('teaching_point', ''))
        source = _escape_html(teaching.get('source', ''))
        
        sections.append('<h4>Teaching Image</h4>')
        if title:
            sections.append(f'<p><strong>Image:</strong> {title}</p>')
        if link:
            safe_link = _escape_html(link)
            sections.append(
                f'<p><strong>Link:</strong> '
                f'<a href="{safe_link}" target="_blank" rel="noopener noreferrer">{safe_link}</a></p>'
            )
        if description:
            sections.append(f'<p><strong>Description:</strong> {description}</p>')
        if teaching_point:
            sections.append(f'<p><strong>Teaching point:</strong> {teaching_point}</p>')
        if source:
            sections.append(f'<p><strong>Source:</strong> {source}</p>')

    # Sources/References
    sources = (output or {}).get('sources', []) or []
    if sources:
        sections.append('<h4>Sources</h4>')
        source_items = []
        for item in sources:
            title = _escape_html(item.get('title', 'Source'))
            url = item.get('url', '')
            pmid = item.get('pmid', '')
            
            if url:
                safe_url = _escape_html(url)
                link_text = title
                if pmid:
                    link_text += f' (PMID: {_escape_html(pmid)})'
                source_items.append(
                    f'<li>'
                    f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{link_text}</a>'
                    f'</li>'
                )
            elif pmid:
                # Link to PubMed if we have PMID but no URL
                pubmed_url = f'https://pubmed.ncbi.nlm.nih.gov/{_escape_html(pmid)}/'
                source_items.append(
                    f'<li>'
                    f'<a href="{pubmed_url}" target="_blank" rel="noopener noreferrer">'
                    f'{title} (PMID: {_escape_html(pmid)})</a>'
                    f'</li>'
                )
            else:
                source_items.append(f'<li>{title}</li>')
        if source_items:
            sections.append(f"<ul>{''.join(source_items)}</ul>")

    # Warnings
    warnings = (output or {}).get('warnings', []) or []
    if warnings:
        warning_text = '; '.join(_escape_html(w) for w in warnings if w)
        if warning_text:
            sections.append(f'<p><strong>⚠️ Warnings:</strong> {warning_text}</p>')
    
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
                'message': 'No diagnosis available'
            })
        
        provider = request.args.get('provider', 'claude').strip()
        model_name = request.args.get('model', '').strip()
        
        # If model not specified, get default from environment (same as ai_prelim.py)
        if not model_name:
            import os
            if provider == 'claude':
                model_name = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
            else:
                model_name = ''  # Unknown provider
        
        # Try to check cache, but handle case where table doesn't exist yet
        try:
            cache_entry = check_ai_diagnosis_cache(case.diagnosis, provider, model_name)
            all_models = get_all_models_for_diagnosis(case.diagnosis)
        except Exception as e:
            # Table might not exist yet (migration not run)
            # Return not cached so user can proceed
            return jsonify({
                'cached': False,
                'message': 'Cache check unavailable (migration may be pending)',
                'all_used_models': [],
                'requested_provider': provider,
                'requested_model': model_name,
            })
        
        return jsonify({
            'cached': cache_entry is not None,
            'cache_entry': {
                'provider': cache_entry.provider if cache_entry else None,
                'model_name': cache_entry.model_name if cache_entry else None,
                'first_generated_at': cache_entry.first_generated_at.isoformat() if cache_entry else None,
                'query_count': cache_entry.query_count if cache_entry else 0,
            } if cache_entry else None,
            'all_used_models': all_models,
            'requested_provider': provider,
            'requested_model': model_name,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Return not cached so user can proceed
        return jsonify({
            'cached': False,
            'error': str(e),
            'message': 'Cache check failed, proceeding anyway',
            'all_used_models': [],
        }), 200  # Return 200 so frontend doesn't treat it as error


@app.route('/api/case/<int:case_id>/ai-prelim', methods=['POST'])
@login_required
def generate_preliminary_case_data(case_id):
    case = verify_case_ownership(case_id)
    if not case:
        return jsonify({'error': 'Unauthorized'}), 403

    from access_control import has_case_edit_permission
    if not has_case_edit_permission(case):
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json() or {}
    provider = (data.get('provider') or 'claude').strip()
    notes = (data.get('notes') or '').strip()
    force_regenerate = data.get('force_regenerate', False)  # User confirmed to regenerate

    if not case.diagnosis or not case.diagnosis.strip():
        return jsonify({'error': 'Diagnosis is required'}), 400
    
    # Get model name (will be determined by ai_prelim, but we need it for cache check)
    import os
    model_name = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514") if provider == 'claude' else ''
    
    # Check cache (unless user explicitly chose to regenerate)
    if not force_regenerate:
        cache_entry = check_ai_diagnosis_cache(case.diagnosis, provider, model_name)
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
                'requested_provider': provider,
                'requested_model': model_name,
            }), 200  # 200 because this is expected behavior, not an error

    sources = [
        'https://radiologyassistant.nl',
        'https://radiopaedia.org',
        'https://www.nice.org.uk',
        'https://www.canstaging.org',
        'https://www.mdcalc.com',
    ]

    context = {
        'diagnosis': case.diagnosis,
        'module': case.module.name if case.module else '',
        'body_part': case.body_part.name if case.body_part else '',
        'notes': notes,
        'existing_summary': case.discussion or '',
        'sources': sources,
    }

    try:
        result = generate_prelim_case_data(context, provider=provider)
    except AiPrelimError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'error': f'AI generation failed: {exc}'}), 500

    output = result.get('output', {})

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

    discussion_html = _build_ai_discussion_html(output, result.get('provider', provider), result.get('model', ''))
    if discussion_html:
        existing_discussion = case.discussion or ''
        separator = '\n' if existing_discussion else ''
        case.discussion = f"{existing_discussion}{separator}{discussion_html}"

    from models import AiPrelimCaseData
    audit = AiPrelimCaseData(
        case_id=case.id,
        created_by_user_id=current_user.id,
        provider=result.get('provider', provider),
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
            provider=result.get('provider', provider),
            model_name=result.get('model', model_name),
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
        'provider': result.get('provider', provider),
        'model': result.get('model', ''),
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
            print(f"Warning: Failed to delete Cloudinary image {message.image_public_id}: {e}")
    
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
    
    # Validate file type
    allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
    if file.content_type not in allowed_types:
        return jsonify({'error': 'Invalid image type. Allowed: jpg, png, gif, webp'}), 400
    
    # Check file size (read into memory to check, max 2MB)
    file_data = file.read()
    if len(file_data) > 2 * 1024 * 1024:
        return jsonify({'error': 'Image too large (max 2MB)'}), 400
    
    # Check if Cloudinary is configured
    if not os.environ.get('CLOUDINARY_CLOUD_NAME'):
        return jsonify({'error': 'Image upload not configured'}), 500
    
    try:
        # Upload to Cloudinary with auto-thumbnail
        result = cloudinary.uploader.upload(
            file_data,
            folder='frcr_forum',
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
        print("[ADMIN] Running database migration...")
        db.create_all()
        print("[ADMIN] Database migration complete")
        return jsonify({'success': True, 'message': 'Database tables created'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    if sys.platform == 'darwin':
        show_macos_gatekeeper_popup()
    port = find_free_port(5000, 20)
    print(f"Starting server on http://127.0.0.1:{port}")
    app.run(debug=True, host='127.0.0.1', port=port)