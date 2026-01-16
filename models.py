
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import enum

db = SQLAlchemy()

# ==================== CASE FLAG MODEL ====================
class CaseFlag(db.Model):
    """Student-specific case flagging"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'case_id', name='uq_user_case_flag'),)

    user = db.relationship('User', backref='case_flags', lazy=True)
    case = db.relationship('Case', backref='flags', lazy=True)

    def __repr__(self):
        return f'<CaseFlag user={self.user_id} case={self.case_id}>'

# ==================== ENUMS ====================

# User Role Enum
class UserRole(enum.Enum):
    """Three-tier role system for access control"""
    STUDENT = "student"              # Default: limited to 2 cases/module if free
    CONTENT_MANAGER = "content_manager"  # Can create/edit cases
    ADMIN = "admin"                  # Full system control

# Subscription Status Enum
class SubscriptionStatus(enum.Enum):
    """User subscription tier"""
    FREE = "free"                    # Limited to 2 cases per module
    PAID = "paid"                    # Unlimited access
    CANCELED = "canceled"            # Was paid, now canceled

# Payment Status Enum
class PaymentStatus(enum.Enum):
    """Payment tracking status"""
    NO_SUBSCRIPTION = "no_subscription"  # Never subscribed
    ACTIVE = "active"                # Currently paid
    PAST_DUE = "past_due"            # Payment failed
    CANCELED = "canceled"            # Subscription ended

# Case Status Enum
class CaseStatus(enum.Enum):
    """Case lifecycle states"""
    DRAFT = "draft"                  # Created but not ready for review
    PENDING_REVIEW = "pending_review"  # Waiting for admin approval
    PUBLISHED = "published"          # Approved and visible to users
    PRIVATE = "private"              # Hidden from students (admin only)
    REJECTED = "rejected"            # Rejected (e.g., duplicate) - recoverable
    ARCHIVED = "archived"            # Old cases, hidden from view

# FRCR Module Enum (FRCR-aligned modules)
class FRCRModule(enum.Enum):
    """FRCR examination modules"""
    CARDIOTHORACIC_VASCULAR = "Cardiothoracic and Vascular"
    MUSCULOSKELETAL_TRAUMA = "Musculoskeletal and Trauma"
    GASTROINTESTINAL = "Gastro-intestinal (incl. liver, biliary, pancreas, spleen)"
    GENITOURINARY_BREAST = "Genito-urinary, Adrenal, O&G and Breast"
    PAEDIATRIC = "Paediatric"
    CNS_HEAD_NECK = "CNS and Head & Neck (incl. spine, eyes, ENT, salivary, dental)"

# Body Part Enum (Comprehensive anatomical regions)
class BodyPart(enum.Enum):
    """Body parts for case categorization"""
    # Cardiovascular
    CARDIOVASCULAR = "Cardiovascular"
    
    # Lung and Thorax
    LUNG_MEDIASTINUM = "Lung and Mediastinum"
    CHEST_WALL = "Chest Wall"
    
    # Gastrointestinal
    GASTROINTESTINAL = "Gastrointestinal"
    HEPATOPANCREATICOBILIARY = "Hepatopancreaticobiliary"
    
    # Genitourinary and Endocrine
    ADRENAL = "Adrenal"
    THYROID_PARATHYROID = "Thyroid and Parathyroid"
    SPLEEN = "Spleen"
    KUB = "KUB"
    
    # Gynaecology and Breast
    GYNAECOLOGY = "Gynaecology"
    BREAST = "Breast"
    
    # Musculoskeletal
    UPPER_LIMB = "Upper Limb"
    LOWER_LIMB = "Lower Limb"
    BONES = "Bones"
    
    # CNS and Head & Neck
    BRAIN_PITUITARY = "Brain and Pituitary"
    SPINE = "Spine"
    HEAD_NECK = "Head and Neck"
    
    # Multi-system
    MULTISYSTEM = "Multisystem"

# Age Group Enum
class AgeGroup(enum.Enum):
    """Patient age category for cases"""
    ADULT = "Adult"
    PEDIATRIC = "Pediatric"

class User(UserMixin, db.Model):
    """Store user account information"""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.Text, nullable=False)  # Use Text instead of String for better compatibility
    full_name = db.Column(db.String(120), nullable=False)
    profile_picture = db.Column(db.Text, nullable=True)  # Base64 encoded image or URL
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)  # Admin flag for first user (DEPRECATED: use 'role' field)
    
    # === NEW FIELDS: ROLE-BASED ACCESS CONTROL ===
    role = db.Column(db.Enum(UserRole), default=UserRole.STUDENT, nullable=False, index=True)
    
    # === NEW FIELDS: SUBSCRIPTION & PAYMENT ===
    subscription_status = db.Column(db.Enum(SubscriptionStatus), default=SubscriptionStatus.FREE, nullable=False, index=True)
    payment_status = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.NO_SUBSCRIPTION, nullable=False)
    subscription_start_date = db.Column(db.DateTime, nullable=True)  # When user subscribed
    subscription_end_date = db.Column(db.DateTime, nullable=True)    # When subscription expires
    
    # === NEW FIELDS: SOFT DELETE ===
    is_deleted = db.Column(db.Boolean, default=False, index=True)  # Soft delete flag
    deleted_at = db.Column(db.DateTime, nullable=True)  # When was user deleted
    deleted_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Who deleted this user
    
    # === NEW FIELDS: AUDIT TRACKING ===
    last_case_viewed = db.Column(db.DateTime, nullable=True)  # When did user last view a case
    last_case_viewed_id = db.Column(db.Integer, nullable=True)  # Which case was viewed
    
    # Password recovery
    recovery_token = db.Column(db.String(255), unique=True, nullable=True)
    recovery_token_expires = db.Column(db.DateTime, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    # exam_sessions = db.relationship('ExamSession', backref='creator', lazy=True, cascade='all, delete-orphan')
    candidate_notes = db.relationship('CandidateNote', backref='author', lazy=True, cascade='all, delete-orphan')
    highlights = db.relationship('TextHighlight', backref='author', lazy=True, cascade='all, delete-orphan')
    created_cases = db.relationship('Case', foreign_keys='Case.created_by_user_id', backref='created_by', lazy=True)
    approved_cases = db.relationship('Case', foreign_keys='Case.approved_by_user_id', backref='approved_by', lazy=True)
    audit_logs = db.relationship('CaseAuditLog', backref='user', lazy=True, foreign_keys='CaseAuditLog.user_id')
    case_views = db.relationship('CaseViewLog', backref='user', lazy=True)
    
    # STUDENT REVISION: Track revision sessions
    revision_sessions = db.relationship('RevisionSession', backref='student', lazy=True, cascade='all, delete-orphan')
    revision_history = db.relationship('RevisionHistory', backref='student', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password against hash"""
        if not self.password_hash:
            print(f"[PASSWORD] WARNING: No password hash for user {self.email}")
            return False
        if not password:
            return False
        try:
            # Strip any whitespace from password_hash (in case of encoding issues)
            hash_to_check = self.password_hash.strip() if isinstance(self.password_hash, str) else self.password_hash
            return check_password_hash(hash_to_check, password)
        except Exception as e:
            print(f"[PASSWORD] ERROR checking password for {self.email}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    @property
    def is_admin_property(self):
        """Property: is_admin is True if role is ADMIN (for consistency)"""
        return self.role == UserRole.ADMIN
    
    def generate_recovery_token(self):
        """Generate unique token for password recovery"""
        token = secrets.token_urlsafe(32)
        self.recovery_token = token
        self.recovery_token_expires = datetime.utcnow() + timedelta(hours=24)
        return token
    
    def verify_recovery_token(self, token):
        """Verify recovery token is valid and not expired"""
        if not self.recovery_token or self.recovery_token != token:
            return False
        if self.recovery_token_expires < datetime.utcnow():
            return False
        return True
    
    def clear_recovery_token(self):
        """Clear recovery token after use"""
        self.recovery_token = None
        self.recovery_token_expires = None
    
    def __repr__(self):
        return f'<User {self.email}>'

class Case(db.Model):
    """Store case information"""
    id = db.Column(db.Integer, primary_key=True)
    # packet_id removed (legacy examiner workflow)
    case_number = db.Column(db.String(50), nullable=True)  # Auto-generated: BODYPART-001 format
    diagnosis = db.Column(db.Text, nullable=False)
    # Legacy questions/answers columns removed - data now stored in Question/Answer tables only
    discussion = db.Column(db.Text)  # Optional discussion/comments
    
    # === EXISTING FIELDS ===
    module = db.Column(db.Enum(FRCRModule), nullable=True, index=True)  # FRCR module categorization
    body_part = db.Column(db.Enum(BodyPart), nullable=True, index=True)  # Body part categorization
    age_group = db.Column(db.Enum(AgeGroup), nullable=True, index=True)  # Patient age category (Adult/Pediatric)
    is_public = db.Column(db.Boolean, default=False, index=True)  # DEPRECATED: use 'status' field instead
    
    # === NEW FIELDS: CASE WORKFLOW ===
    status = db.Column(db.Enum(CaseStatus), default=CaseStatus.DRAFT, nullable=False, index=True)  # Case lifecycle state
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Who created this case
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Who approved this case
    approved_at = db.Column(db.DateTime, nullable=True)  # When was it approved
    
    # === AI CONTENT VERIFICATION ===
    ai_content_verified = db.Column(db.Boolean, default=False, nullable=False, index=True)  # AI watermarks removed when True
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    images = db.relationship('CaseImage', backref='case', lazy=True, cascade='all, delete-orphan')
    question_items = db.relationship('Question', backref='case', lazy=True, cascade='all, delete-orphan')
    answer_items = db.relationship('Answer', backref='case', lazy=True, cascade='all, delete-orphan')
    candidate_notes = db.relationship('CandidateNote', backref='case', lazy=True, cascade='all, delete-orphan')
    highlights = db.relationship('TextHighlight', backref='case', lazy=True, cascade='all, delete-orphan')
    audit_logs = db.relationship('CaseAuditLog', backref='case', lazy=True, cascade='all, delete-orphan')
    view_logs = db.relationship('CaseViewLog', backref='case', lazy=True, cascade='all, delete-orphan')
    approval_queue = db.relationship('CaseApprovalQueue', backref='case', lazy=True, cascade='all, delete-orphan', uselist=False)
    
    def __repr__(self):
        return f'<Case {self.case_number} - {self.diagnosis}>'


def sync_case_visibility(case, status=None, is_public=None):
    """Keep status and is_public aligned with status as source of truth."""
    if status is not None:
        status_enum = None
        if isinstance(status, CaseStatus):
            status_enum = status
        elif isinstance(status, str):
            try:
                status_enum = CaseStatus[status]
            except KeyError:
                status_enum = None
        if status_enum:
            case.status = status_enum
            case.is_public = (status_enum == CaseStatus.PUBLISHED)
        return

    if is_public is not None:
        if isinstance(is_public, str):
            is_public = is_public.lower() == 'true'
        elif isinstance(is_public, int):
            is_public = is_public == 1
        else:
            is_public = bool(is_public)

        case.is_public = is_public
        if is_public and case.status != CaseStatus.PUBLISHED:
            case.status = CaseStatus.PUBLISHED
        elif not is_public and case.status == CaseStatus.PUBLISHED:
            case.status = CaseStatus.DRAFT


class Question(db.Model):
    """Store individual questions for a case"""
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False)
    question_number = db.Column(db.Integer, nullable=False)  # Order: 1, 2, 3...
    question_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Question {self.question_number} for Case {self.case_id}>'


class Answer(db.Model):
    """Store individual answers for a case"""
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False)
    answer_number = db.Column(db.Integer, nullable=False)  # Order: 1, 2, 3...
    answer_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Answer {self.answer_number} for Case {self.case_id}>'


class CaseImage(db.Model):
    """Store images for a case"""
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False)
    image_data = db.Column(db.LargeBinary, nullable=False)  # Binary image data
    image_filename = db.Column(db.String(255), nullable=False)
    image_type = db.Column(db.String(50), nullable=False)  # e.g., 'image/png', 'image/jpeg'
    image_description = db.Column(db.Text, default='')  # Optional image description
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<CaseImage {self.image_filename} for Case {self.case_id}>'





class CandidateNote(db.Model):
    """Store student/candidate notes for cases"""
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    note_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Composite index for efficient lookups
    __table_args__ = (
        db.Index('idx_case_user', 'case_id', 'user_id'),
    )
    
    def __repr__(self):
        return f'<CandidateNote Case:{self.case_id} User:{self.user_id}>'


class TextHighlight(db.Model):
    """Store text highlights for search and personalization"""
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    text_content = db.Column(db.Text, nullable=False)  # The highlighted text
    highlight_color = db.Column(db.String(20), nullable=False)  # yellow, green, pink, blue
    field_name = db.Column(db.String(50), nullable=False)  # question, answer, discussion, notes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Composite index for efficient lookups
    __table_args__ = (
        db.Index('idx_case_user_highlight', 'case_id', 'user_id'),
        db.Index('idx_text_search', 'text_content'),  # For keyword search
    )
    
    def __repr__(self):
        return f'<TextHighlight Case:{self.case_id} User:{self.user_id} Color:{self.highlight_color}>'


# ==================== AUDIT & TRACKING MODELS ====================

class CaseAuditLog(db.Model):
    """Audit trail for case creation, edits, approvals"""
    __tablename__ = 'case_audit_log'
    
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)  # 'created', 'edited', 'approved', 'rejected', 'deleted'
    changes = db.Column(db.JSON, nullable=True)  # What changed: {field: {old: value, new: value}}
    notes = db.Column(db.Text, nullable=True)  # Optional admin notes
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<CaseAuditLog Case:{self.case_id} User:{self.user_id} Action:{self.action}>'


class CaseViewLog(db.Model):
    """Track case views for student randomization and analytics"""
    __tablename__ = 'case_view_log'
    
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    time_spent_seconds = db.Column(db.Integer, nullable=True)  # How long user spent on case
    
    __table_args__ = (
        db.Index('idx_user_case_view', 'user_id', 'case_id', 'viewed_at'),
    )
    
    def __repr__(self):
        return f'<CaseViewLog Case:{self.case_id} User:{self.user_id} Viewed:{self.viewed_at}>'


class CaseApprovalQueue(db.Model):
    """Queue for cases pending admin approval"""
    __tablename__ = 'case_approval_queue'
    
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, unique=True, index=True)
    submitted_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    admin_notes = db.Column(db.Text, nullable=True)
    
    submitted_by_user = db.relationship('User', backref='submitted_cases')
    
    def __repr__(self):
        return f'<CaseApprovalQueue Case:{self.case_id} Submitted:{self.submitted_at}>'


# ==================== STUDENT REVISION MODELS ====================
# These models support the balanced revision feature for students
# CRITICAL: Do NOT mix with examiner ExamSession/Packet/Candidate models

class RevisionSession(db.Model):
    """
    Tracks a student's balanced revision session.
    Each session contains 6 cases from each FRCR module (36 total).
    """
    __tablename__ = 'revision_session'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Session metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)  # NULL if in progress
    
    # Store selected case IDs as JSON array (locked once created)
    # Format: [case_id1, case_id2, ...]
    case_ids = db.Column(db.Text, nullable=False)  # JSON array of integers
    
    # Track progress through the session
    current_case_index = db.Column(db.Integer, default=0)  # 0-based index into case_ids
    
    # Statistics
    total_cases = db.Column(db.Integer, default=36)  # 6 per module × 6 modules
    
    def __repr__(self):
        return f'<RevisionSession {self.id} User:{self.user_id} Progress:{self.current_case_index}/{self.total_cases}>'
    
    def get_case_ids_list(self):
        """Parse JSON case_ids into Python list"""
        import json
        return json.loads(self.case_ids) if self.case_ids else []
    
    def set_case_ids_list(self, case_list):
        """Convert Python list to JSON and store"""
        import json
        self.case_ids = json.dumps(case_list)
        self.total_cases = len(case_list)


class RevisionHistory(db.Model):
    """
    Tracks which cases each user has seen during revision.
    Purpose: Prevent repetition and enable smart case selection.
    """
    __tablename__ = 'revision_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)
    
    # Module reference (denormalized for faster queries)
    module = db.Column(db.Enum(FRCRModule), nullable=False, index=True)
    
    # Tracking timestamps
    first_seen_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    times_seen = db.Column(db.Integer, default=1)  # Increment on each view
    
    # Optional: Link to specific revision session
    revision_session_id = db.Column(db.Integer, db.ForeignKey('revision_session.id'), nullable=True)
    
    # Composite indexes for efficient queries
    __table_args__ = (
        # Ensure one history record per user-case pair
        db.UniqueConstraint('user_id', 'case_id', name='unique_user_case'),
        # Fast lookup: "which cases has this user seen in this module?"
        db.Index('idx_user_module_lastseen', 'user_id', 'module', 'last_seen_at'),
    )
    
    def __repr__(self):
        return f'<RevisionHistory User:{self.user_id} Case:{self.case_id} Module:{self.module.value} Seen:{self.times_seen}x>'


# ==================== DATA IMPORT & ENRICHMENT MODELS ====================
# These models support importing cases from external sources (e.g., FRCR-Examiner)
# and enriching them with metadata before promoting to production

class ImportedCaseStaging(db.Model):
    """
    Temporary storage for cases being imported and enriched.
    Cases move to production (Case model) after admin approval.
    Supports duplicate detection and conflict resolution.
    """
    __tablename__ = 'imported_case_staging'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # ===== RAW DATA FROM IMPORT =====
    original_id = db.Column(db.Integer, nullable=True, index=True)  # ID from source system
    case_number = db.Column(db.Integer, nullable=True)
    diagnosis = db.Column(db.Text, nullable=False)
    questions = db.Column(db.Text, nullable=False)  # DEPRECATED: Legacy field - kept for import compatibility only. Will be migrated to Question table on promotion.
    answers = db.Column(db.Text, nullable=False)  # DEPRECATED: Legacy field - kept for import compatibility only. Will be migrated to Answer table on promotion.
    discussion = db.Column(db.Text, nullable=True)
    
    # ===== ENRICHED METADATA (Admin-added) =====
    module = db.Column(db.Enum(FRCRModule), nullable=True, index=True)
    body_part = db.Column(db.Enum(BodyPart), nullable=True, index=True)
    age_group = db.Column(db.Enum(AgeGroup), nullable=True, index=True)
    is_public = db.Column(db.Boolean, default=False, index=True)
    
    # ===== ENRICHMENT TRACKING =====
    enrichment_status = db.Column(
        db.String(20),
        default='pending',
        index=True
    )  # pending, in_progress, enriched, rejected, promoted
    
    enriched_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    enriched_at = db.Column(db.DateTime, nullable=True)
    enrichment_notes = db.Column(db.Text, nullable=True)
    
    # ===== APPROVAL WORKFLOW =====
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    approval_notes = db.Column(db.Text, nullable=True)
    
    # ===== DUPLICATE & PROMOTION TRACKING =====
    promoted_to_case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=True, index=True)
    promoted_at = db.Column(db.DateTime, nullable=True)
    
    # Tracks previous versions if re-imported
    previous_staging_id = db.Column(db.Integer, db.ForeignKey('imported_case_staging.id'), nullable=True)
    is_replacement = db.Column(db.Boolean, default=False)  # TRUE if updating previous import
    
    # ===== IMPORT TRACKING =====
    import_batch_id = db.Column(db.String(50), nullable=False, index=True)  # UUID for batch
    source_system = db.Column(db.String(50), default='frcr_examiner', index=True)
    import_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    enriched_by = db.relationship('User', foreign_keys=[enriched_by_user_id])
    approved_by = db.relationship('User', foreign_keys=[approved_by_user_id])
    promoted_to_case = db.relationship('Case', foreign_keys=[promoted_to_case_id])
    previous_staging = db.relationship('ImportedCaseStaging', remote_side=[id], foreign_keys=[previous_staging_id])
    
    # Indexes for efficient duplicate detection
    __table_args__ = (
        db.Index('idx_original_id_batch', 'source_system', 'original_id', 'import_batch_id'),
        db.Index('idx_promoted_case', 'promoted_to_case_id'),
        db.Index('idx_enrichment_status', 'enrichment_status'),
    )
    
    def __repr__(self):
        return f'<ImportedCaseStaging {self.case_number} Status:{self.enrichment_status}>'


class AiPrelimCaseData(db.Model):
    """
    Stores AI-generated preliminary case data and audit metadata.
    """
    __tablename__ = 'ai_prelim_case_data'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    provider = db.Column(db.String(50), nullable=False)
    model_name = db.Column(db.String(100), nullable=False)
    prompt_version = db.Column(db.String(20), nullable=False, default='v1')

    request_payload = db.Column(db.Text, nullable=True)
    response_payload = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    case = db.relationship('Case', foreign_keys=[case_id])
    created_by = db.relationship('User', foreign_keys=[created_by_user_id])

    def __repr__(self):
        return f'<AiPrelimCaseData Case:{self.case_id} Provider:{self.provider}>'


class AiDiagnosisCache(db.Model):
    """
    Caches AI-generated content by diagnosis + model combination.
    This is diagnosis-based (not user-based) to prevent duplicate queries.
    """
    __tablename__ = 'ai_diagnosis_cache'

    id = db.Column(db.Integer, primary_key=True)
    diagnosis = db.Column(db.String(500), nullable=False, index=True)
    provider = db.Column(db.String(50), nullable=False)  # e.g., 'claude', 'consensus'
    model_name = db.Column(db.String(100), nullable=False)  # e.g., 'claude-sonnet-4-20250514'
    
    # Store reference to the case that first generated this content
    first_case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)
    first_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Timestamp of first generation
    first_generated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Count how many times this diagnosis+model has been queried
    query_count = db.Column(db.Integer, default=1, nullable=False)
    
    # Last time this was queried (for potential cache expiration)
    last_queried_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        db.UniqueConstraint('diagnosis', 'provider', 'model_name', name='uq_diagnosis_provider_model'),
    )

    case = db.relationship('Case', foreign_keys=[first_case_id])
    user = db.relationship('User', foreign_keys=[first_user_id])

    def __repr__(self):
        return f'<AiDiagnosisCache Diagnosis:{self.diagnosis[:30]}... Model:{self.model_name}>'
