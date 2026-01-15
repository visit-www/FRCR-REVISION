
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
from ai_prelim import AiPrelimError, generate_prelim_case_data
from datetime import datetime
from sqlalchemy.pool import NullPool
import os
from io import BytesIO
import mimetypes
import json

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
# Vercel/Supabase envs can be POSTGRES_URL(_NON_POOLING) or DATABASE_* variants
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
app.config['SESSION_COOKIE_SECURE'] = is_production  # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True  # No JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
app.config['SESSION_COOKIE_NAME'] = 'frcr_session'  # Explicit name
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours

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
    return User.query.get(int(user_id))

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


# ==================== HELPER FUNCTIONS ====================



with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(backup_bp)
app.register_blueprint(admin_bp)  # Sprint 2: Admin user management
app.register_blueprint(enrichment_bp)  # Data migration: Import, enrich, promote cases


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
    Selects 6 random cases from each FRCR module (36 total cases).
    Prioritizes cases the user hasn't seen or has seen least recently.
    """
    from models import FRCRModule, Case, RevisionSession, RevisionHistory
    import json
    from sqlalchemy import func
    
    print(f"[REVISION] User {current_user.id} starting balanced revision session")
    
    try:
        # Get all FRCR modules
        all_modules = list(FRCRModule)
        selected_case_ids = []
        
        # For each module, select 6 cases
        for module in all_modules:
            print(f"[REVISION] Selecting cases for module: {module.value}")
            
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
            
            print(f"[REVISION] Selected {len(case_ids_for_module)} cases from {module.value}: {case_ids_for_module}")
            
            # Handle insufficient cases in module
            if len(cases) < 6:
                print(f"[REVISION] WARNING: Only {len(cases)} cases available in {module.value} (need 6)")
        
        # Check if we have enough cases
        if len(selected_case_ids) == 0:
            flash('Enough public cases not available for revision at presemt.', 'warning')
            return redirect(url_for('dashboard'))
        
        # Show warning if we have fewer than expected
        if len(selected_case_ids) < 36:
            flash(f'Started revision with {len(selected_case_ids)} available cases. Some modules need more cases for full coverage.', 'info')
        
        print(f"[REVISION] Total selected cases: {len(selected_case_ids)}")
        
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
                         body_parts=body_parts,
                         body_part_selected=body_part_filter,
                         search_query=search_query)


@app.route('/cases')
@login_required
def all_cases_view():
    if getattr(current_user, 'role', None) == UserRole.STUDENT:
        return redirect(url_for('student_cases_list'))
    # ...existing admin case list logic...


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
    """Case management page - list, create, edit, delete cases"""
    if not current_user.is_admin:
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
    
    # Convert lists to JSON strings for TEXT fields (legacy support)
    try:
        case = Case(
            packet_id=data.get('packet_id'),  # Nullable for standalone cases
            case_number=case_number,
            diagnosis=data['diagnosis'],
            questions=json.dumps(questions or []),
            answers=json.dumps(answers or []),
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
    print(f"[DEBUG] case.discussion for case_id={case_id}: {repr(case.discussion)}")
    return render_template('view_case.html', 
                         case=case, 
                         user_note=user_note)


@app.route('/edit-case')
def edit_case():
    """Full-page edit interface for a case"""
    case_id = request.args.get('id', type=int)
    is_new = request.args.get('new', 'false').lower() == 'true'
    return_to = request.args.get('returnTo', url_for('dashboard'))
    if not is_new and not case_id:
        return redirect(url_for('dashboard'))
    case = Case.query.get(case_id) if case_id else None
    if not is_new and not case:
        return redirect(url_for('dashboard'))
    return render_template('edit_case.html', 
                         is_new=is_new,
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


@app.route('/api/case/<int:case_id>', methods=['DELETE'])
@login_required
def delete_case(case_id):
    """Delete a case"""
    # Verify user ownership
    case = verify_case_ownership(case_id)
    if not case:
        return jsonify({"error": "Unauthorized"}), 403
    
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    
    db.session.delete(case)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Case deleted successfully'})


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
    
    image_data = file.read()
    
    # Get description from form data
    description = request.form.get('description', '')
    
    try:
        case_image = CaseImage(
            case_id=case_id,
            image_data=image_data,
            image_filename=file.filename,
            image_type=file_type,
            image_description=description
        )
        
        db.session.add(case_image)
        db.session.commit()
        
        return jsonify({
            'image_id': case_image.id,
            'filename': case_image.image_filename,
            'message': 'Image uploaded successfully'
        })
    except Exception as e:
        db.session.rollback()
        print(f"[IMAGE] Error uploading image: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Database error: {str(e)}'}), 500


@app.route('/api/case/<int:case_id>/images')
@login_required
def get_case_images(case_id):
    """Get all images for a case"""
    # Verify user ownership
    case = verify_case_ownership(case_id)
    if not case:
        return jsonify({"error": "Unauthorized"}), 403
    images = CaseImage.query.filter_by(case_id=case_id).order_by(CaseImage.created_at).all()
    return jsonify([{
        'id': img.id,
        'filename': img.image_filename,
        'description': img.image_description if img.image_description else '',
        'created_at': img.created_at.strftime('%Y-%m-%d %H:%M:%S')
    } for img in images])


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


@app.route('/api/case-image/<int:image_id>/description', methods=['PUT'])
def update_image_description(image_id):
    """Update image description"""
    try:
        image = CaseImage.query.get(image_id)
        
        if not image:
            return jsonify({'error': 'Image not found'}), 404
        
        import bleach
        data = request.get_json()
        description = data.get('description', '')
        # Sanitize HTML for image description
        allowed_tags = bleach.sanitizer.ALLOWED_TAGS + [
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
        print(f"[ERROR] Update image description failed: {str(e)}")
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
            print(f"[DEBUG] Case {case.id} saved successfully.")
            return jsonify({'success': True, 'message': 'Case updated'})
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Failed to update case: {e}")
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
    sections = []
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    header = (
        '<hr>'
        '<h3>AI Preliminary Case Data</h3>'
        f'<p><em>Generated by { _escape_html(provider) } ({ _escape_html(model_name) })'
        f' on { _escape_html(timestamp) }.</em></p>'
    )
    sections.append(header)

    discussion = (output or {}).get('discussion', '')
    if discussion:
        sections.append('<h4>Discussion</h4>')
        sections.append(_format_paragraph(discussion))

    checklist = (output or {}).get('safety_checklist', []) or []
    if checklist:
        sections.append('<h4>Clinico-Radiological Safety Focus</h4>')
        items = ''.join(f'<li>{_escape_html(item)}</li>' for item in checklist if item)
        if items:
            sections.append(f'<ul>{items}</ul>')

    teaching = (output or {}).get('teaching_image', {}) or {}
    if teaching:
        title = _escape_html(teaching.get('title', ''))
        link = _escape_html(teaching.get('link', ''))
        description = _escape_html(teaching.get('description', ''))
        teaching_point = _escape_html(teaching.get('teaching_point', ''))
        source = _escape_html(teaching.get('source', ''))
        sections.append('<h4>Teaching Image</h4>')
        if title:
            sections.append(f'<p><strong>Image:</strong> {title}</p>')
        if link:
            sections.append(
                f'<p><strong>Link:</strong> <a href="{link}" target="_blank" '
                f'rel="noopener noreferrer">{link}</a></p>'
            )
        if description:
            sections.append(f'<p><strong>Description:</strong> {description}</p>')
        if teaching_point:
            sections.append(f'<p><strong>Teaching point:</strong> {teaching_point}</p>')
        if source:
            sections.append(f'<p><strong>Source:</strong> {source}</p>')

    sources = (output or {}).get('sources', []) or []
    if sources:
        sections.append('<h4>Sources</h4>')
        source_items = []
        for item in sources:
            title = _escape_html(item.get('title', 'Source'))
            url = _escape_html(item.get('url', ''))
            if url:
                source_items.append(
                    f'<li><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></li>'
                )
            else:
                source_items.append(f'<li>{title}</li>')
        if source_items:
            sections.append(f"<ul>{''.join(source_items)}</ul>")

    warnings = (output or {}).get('warnings', []) or []
    if warnings:
        warning_text = '; '.join(_escape_html(w) for w in warnings if w)
        if warning_text:
            sections.append(f'<p><strong>Warnings:</strong> {warning_text}</p>')

    return ''.join(sections)


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

    if not case.diagnosis or not case.diagnosis.strip():
        return jsonify({'error': 'Diagnosis is required'}), 400

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

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return jsonify({'error': f'Failed to save AI data: {exc}'}), 500

    return jsonify({
        'success': True,
        'added_pairs': added_pairs,
        'discussion_html': discussion_html,
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
    """Add a new text highlight"""
    from models import TextHighlight
    
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
        print(f"[ADMIN] Migration error: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    if sys.platform == 'darwin':
        show_macos_gatekeeper_popup()
    port = find_free_port(5000, 20)
    print(f"Starting server on http://127.0.0.1:{port}")
    app.run(debug=True, host='127.0.0.1', port=port)
