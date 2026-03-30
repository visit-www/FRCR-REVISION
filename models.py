
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.types import TypeDecorator, Text as SAText
import secrets
import enum
import json
import logging

_models_logger = logging.getLogger(__name__)

db = SQLAlchemy()


class EncryptedText(TypeDecorator):
    """Transparently encrypts on write and decrypts on read using Fernet (AES).
    Falls back to plaintext for legacy unencrypted data (backward compatible)."""
    impl = SAText
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and isinstance(value, str) and value.strip():
            try:
                from case_dicom_viewer.token_utils import encrypt_refresh_token
                encrypted = encrypt_refresh_token(value)
                return encrypted if encrypted else value
            except Exception:
                return value
        return value

    def process_result_value(self, value, dialect):
        if value is not None and isinstance(value, str) and value.strip():
            try:
                from case_dicom_viewer.token_utils import decrypt_refresh_token
                decrypted = decrypt_refresh_token(value)
                return decrypted if decrypted else value  # Plaintext fallback for legacy data
            except Exception:
                return value
        return value

# ==================== CASE FLAG MODEL ====================
class CaseFlag(db.Model):
    """Student-specific case flagging"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'case_id', name='uq_user_case_flag'),)

    user = db.relationship('User', backref='user_case_flags', lazy=True)
    # case relationship defined on Case model with cascade delete

    def __repr__(self):
        return f'<CaseFlag user={self.user_id} case={self.case_id}>'

# ==================== RELATED CASES ASSOCIATION TABLE ====================
# Many-to-many self-referential relationship for linking related cases
related_cases = db.Table('related_cases',
    db.Column('case_id', db.Integer, db.ForeignKey('case.id', ondelete='CASCADE'), primary_key=True),
    db.Column('related_case_id', db.Integer, db.ForeignKey('case.id', ondelete='CASCADE'), primary_key=True),
    db.Column('relation_type', db.String(50), default='related'),  # 'algorithm', 'similar', 'reference'
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)

# ==================== CASE-CALCULATOR LINK TABLE ====================
case_calculator_links = db.Table('case_calculator_links',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('case_id', db.Integer, db.ForeignKey('case.id', ondelete='CASCADE'), nullable=False),
    db.Column('calculator_id', db.Integer, db.ForeignKey('tnm_calculator_content.id', ondelete='CASCADE'), nullable=False),
    db.Column('created_by_user_id', db.Integer, db.ForeignKey('user.id'), nullable=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow),
    db.UniqueConstraint('case_id', 'calculator_id')
)

# ==================== CASE-REFERENCE LINK TABLE ====================
case_reference_links = db.Table('case_reference_links',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('case_id', db.Integer, db.ForeignKey('case.id', ondelete='CASCADE'), nullable=False),
    db.Column('reference_id', db.Integer, db.ForeignKey('case_reference.id', ondelete='CASCADE'), nullable=False),
    db.Column('created_by_user_id', db.Integer, db.ForeignKey('user.id'), nullable=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow),
    db.UniqueConstraint('case_id', 'reference_id')
)

# ==================== CASE-ALGORITHM LINK TABLE ====================
case_algorithm_links = db.Table('case_algorithm_links',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('case_id', db.Integer, db.ForeignKey('case.id', ondelete='CASCADE'), nullable=False),
    db.Column('algorithm_id', db.Integer, db.ForeignKey('reporting_algorithm.id', ondelete='CASCADE'), nullable=False),
    db.Column('created_by_user_id', db.Integer, db.ForeignKey('user.id'), nullable=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow),
    db.UniqueConstraint('case_id', 'algorithm_id')
)

# ==================== CASE-TEMPLATE LINK TABLE ====================
case_template_links = db.Table('case_template_links',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('case_id', db.Integer, db.ForeignKey('case.id', ondelete='CASCADE'), nullable=False),
    db.Column('template_id', db.Integer, db.ForeignKey('radiology_template.id', ondelete='CASCADE'), nullable=False),
    db.Column('created_by_user_id', db.Integer, db.ForeignKey('user.id'), nullable=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow),
    db.UniqueConstraint('case_id', 'template_id')
)

# ==================== CASE-PEARL LINK TABLE ====================
case_pearl_links = db.Table('case_pearl_links',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('case_id', db.Integer, db.ForeignKey('case.id', ondelete='CASCADE'), nullable=False),
    db.Column('pearl_id', db.Integer, db.ForeignKey('radiology_pearl.id', ondelete='CASCADE'), nullable=False),
    db.Column('created_by_user_id', db.Integer, db.ForeignKey('user.id'), nullable=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow),
    db.UniqueConstraint('case_id', 'pearl_id')
)

# ==================== UNIVERSAL CONTENT LINK TABLE ====================
# Generic many-to-many for linking any content type to any other content type.
# Stored in canonical order (source_type <= target_type alphabetically) to
# prevent duplicates. Queried from both directions for automatic cross-linking.
content_links = db.Table('content_links',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('source_type', db.String(50), nullable=False),   # 'algorithm', 'case', 'pearl'
    db.Column('source_id', db.Integer, nullable=False),
    db.Column('target_type', db.String(50), nullable=False),
    db.Column('target_id', db.Integer, nullable=False),
    db.Column('created_by_user_id', db.Integer, db.ForeignKey('user.id'), nullable=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow),
    db.UniqueConstraint('source_type', 'source_id', 'target_type', 'target_id', name='uq_content_link')
)

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
    UPPER_GASTROINTESTINAL = "Upper gastrointestinal"
    LOWER_GASTROINTESTINAL = "Lower gastrointestinal"
    GASTROINTESTINAL = "Gastrointestinal"
    HEPATOPANCREATICOBILIARY = "Hepatopancreaticobiliary"
    
    # Genitourinary and Endocrine
    ADRENAL = "Adrenal"
    MALE_GENITAL = "Male genital"
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
    SOFT_TISSUE = "Soft tissue"
    
    # CNS and Head & Neck
    BRAIN_PITUITARY = "Brain and Pituitary"
    BRAIN_SPINE = "Brain and Spinal Cord"
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
    profile_picture = db.Column(db.Text, nullable=True)  # Cloudinary URL (legacy: base64)
    profile_picture_public_id = db.Column(db.String(255), nullable=True)  # For Cloudinary deletion
    public_display_name = db.Column(db.String(30), nullable=True)  # User-controlled forum display name
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)  # Admin flag for first user (DEPRECATED: use 'role' field)
    
    # === NEW FIELDS: ROLE-BASED ACCESS CONTROL ===
    role = db.Column(db.Enum(UserRole), default=UserRole.STUDENT, nullable=False, index=True)
    is_superadmin = db.Column(db.Boolean, default=False, index=True)  # Only one superadmin (lotusheart2016@gmail.com)
    
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
    
    # === NOTION INTEGRATION ===
    notion_access_token = db.Column(EncryptedText(), nullable=True)  # OAuth access token (encrypted at rest)
    notion_workspace_id = db.Column(db.String(100), nullable=True)  # Connected workspace ID
    notion_connected_at = db.Column(db.DateTime, nullable=True)  # When Notion was connected
    
    # === ANKI INTEGRATION ===
    anki_api_key = db.Column(EncryptedText(), nullable=True)  # AnkiWeb API key (encrypted at rest)
    anki_deck_name = db.Column(db.String(100), nullable=True, default='RadInsights')  # Default deck name
    anki_connected_at = db.Column(db.DateTime, nullable=True)  # When Anki was connected
    
    # === SCIENCE DIRECT INTEGRATION (Student) ===
    sciencedirect_session_cookies = db.Column(EncryptedText(), nullable=True)  # Serialized session cookies (encrypted at rest)
    sciencedirect_connected_at = db.Column(db.DateTime, nullable=True)  # When ScienceDirect was connected
    
    # === AI USAGE RATE LIMITING ===
    ai_usage_date = db.Column(db.Date, nullable=True)  # Date of last AI usage
    ai_usage_count = db.Column(db.Integer, default=0)   # Number of AI requests today

    # === SUBSCRIPTION TIER & MONTHLY AI USAGE ===
    subscription_tier = db.Column(db.String(20), default='free')   # 'free', 'standard', 'elite'
    trial_started_at = db.Column(db.DateTime, nullable=True)       # NULL = grandfathered (no trial expiry)
    sr_usage_month = db.Column(db.Integer, default=0)              # Smart Reporter actions this month
    radiq_usage_month = db.Column(db.Integer, default=0)           # RadIQ queries this month
    usage_reset_date = db.Column(db.Date, nullable=True)           # 1st of current billing month

    # === LOGIN RATE LIMITING (brute force protection) ===
    failed_login_count = db.Column(db.Integer, default=0)
    failed_login_last = db.Column(db.DateTime, nullable=True)
    locked_until = db.Column(db.DateTime, nullable=True)

    # === 2FA TOTP (admin only) ===
    totp_secret = db.Column(EncryptedText(), nullable=True)  # Base32 TOTP secret (encrypted at rest)
    totp_enabled = db.Column(db.Boolean, default=False)       # Whether 2FA is active
    totp_backup_codes = db.Column(EncryptedText(), nullable=True)  # JSON list of hashed backup codes
    totp_grace_period_until = db.Column(db.DateTime, nullable=True)  # Admins get 7-day grace to set up 2FA

    # === GOOGLE OAUTH ===
    google_id = db.Column(db.String(255), nullable=True, unique=True)  # Google OAuth user ID

    # === STRIPE ===
    stripe_customer_id = db.Column(db.String(255), nullable=True, unique=True, index=True)

    # === PENDING PLAN CHANGE (scheduled downgrades) ===
    pending_subscription_tier = db.Column(db.String(20), nullable=True)       # 'standard', 'free', or None
    pending_change_effective_date = db.Column(db.DateTime, nullable=True)     # When change takes effect

    # Password recovery
    recovery_token = db.Column(db.String(255), unique=True, nullable=True)
    recovery_token_expires = db.Column(db.DateTime, nullable=True)

    # === ONBOARDING ===
    has_seen_tour = db.Column(db.Boolean, default=False)

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
            return False
        if not password:
            return False
        try:
            # Strip any whitespace from password_hash (in case of encoding issues)
            hash_to_check = self.password_hash.strip() if isinstance(self.password_hash, str) else self.password_hash
            return check_password_hash(hash_to_check, password)
        except Exception as e:
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
        if not self.recovery_token_expires or self.recovery_token_expires < datetime.utcnow():
            return False
        return True
    
    def clear_recovery_token(self):
        """Clear recovery token after use"""
        self.recovery_token = None
        self.recovery_token_expires = None
    
    @property
    def username(self):
        """Extract username from email (before @)"""
        if self.email:
            return self.email.split('@')[0]
        return None
    
    def get_display_name(self):
        """
        Get the user's display name for forum/public contexts.
        Resolution priority:
        1. public_display_name (if set)
        2. username (from email)
        3. full_name
        4. "User" (final fallback)
        
        NEVER returns subscription status like "Free user" or "Paid user"
        """
        if self.public_display_name and self.public_display_name.strip():
            return self.public_display_name.strip()
        if self.username:
            return self.username
        if self.full_name and self.full_name.strip():
            return self.full_name.strip()
        return "User"
    
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
    # REMOVED: ai_content_verified field - watermarks are now removed based on publish/public status only

    # === CALCULATOR INTEGRATION ===
    calculator_slug = db.Column(db.String(50), nullable=True)  # e.g., 'oropharynx', 'lung', None

    # === CONTRIBUTOR (Suggest a Case) ===
    contributor_name = db.Column(db.String(120), nullable=True)  # Attribution name for student-submitted cases
    contributor_notes = db.Column(db.Text, nullable=True)  # Student "Additional Insights" free text

    # === RELATED CASES ===
    # Self-referential many-to-many for linking related cases (e.g., algorithm → specific cases)
    related_cases_list = db.relationship(
        'Case',
        secondary='related_cases',
        primaryjoin='Case.id == related_cases.c.case_id',
        secondaryjoin='Case.id == related_cases.c.related_case_id',
        backref=db.backref('referenced_by', lazy='dynamic'),
        lazy='dynamic'
    )

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
    # Forum messages - cascade delete when case is deleted (user messages preserved when user deleted)
    forum_messages_rel = db.relationship('ForumMessage', backref='case_ref', lazy=True, cascade='all, delete-orphan')
    # Case flags - cascade delete when case is deleted
    case_flags = db.relationship('CaseFlag', backref='case_ref', lazy=True, cascade='all, delete-orphan')
    # Revision history - cascade delete when case is deleted
    revision_history_rel = db.relationship('RevisionHistory', backref='case_ref', lazy=True, cascade='all, delete-orphan')
    
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


class CaseReference(db.Model):
    """Store references for a case - proper database model for better integrity and queryability"""
    __tablename__ = 'case_reference'
    
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)
    
    # Reference data
    ref_number = db.Column(db.Integer, nullable=False)  # The [1], [2], etc. display number
    title = db.Column(db.Text, nullable=False)
    url = db.Column(db.Text, nullable=False)
    journal = db.Column(db.String(500), nullable=True)
    year = db.Column(db.String(10), nullable=True)
    
    # Whether this reference has an inline citation (superscript) in the discussion
    # False = added via search/manual (reference list only)
    # True = added via context menu (has [N] superscript in text)
    is_inline = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship back to Case
    case = db.relationship('Case', backref=db.backref('references', lazy=True, cascade='all, delete-orphan'))
    
    # Unique constraint: one ref_number per case
    __table_args__ = (
        db.UniqueConstraint('case_id', 'ref_number', name='uq_case_ref_number'),
        db.UniqueConstraint('case_id', 'url', name='uq_case_ref_url'),
    )
    
    def __repr__(self):
        return f'<CaseReference [{self.ref_number}] for Case {self.case_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'case_id': self.case_id,
            'ref_number': self.ref_number,
            'title': self.title,
            'url': self.url,
            'journal': self.journal,
            'year': self.year,
            'is_inline': self.is_inline,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class TnmReference(db.Model):
    """Store references for TNM disease sites - mirrors CaseReference structure"""
    __tablename__ = 'tnm_reference'
    
    id = db.Column(db.Integer, primary_key=True)
    disease_site_id = db.Column(db.Integer, db.ForeignKey('ajcc_disease_site.id'), nullable=False, index=True)
    
    # Reference data
    ref_number = db.Column(db.Integer, nullable=False)  # The [1], [2], etc. display number
    title = db.Column(db.Text, nullable=False)
    url = db.Column(db.Text, nullable=False)
    journal = db.Column(db.String(500), nullable=True)
    year = db.Column(db.String(10), nullable=True)
    
    # Whether this reference has an inline citation (superscript) in the content
    # False = added via search/manual (reference list only, hidden superscript)
    # True = added via context menu (has visible [N] superscript in text)
    is_inline = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship back to AJCCDiseaseSite
    disease_site = db.relationship('AJCCDiseaseSite', backref=db.backref('references', lazy=True, cascade='all, delete-orphan'))
    
    # Unique constraint: one ref_number per disease site, one URL per disease site
    __table_args__ = (
        db.UniqueConstraint('disease_site_id', 'ref_number', name='uq_tnm_ref_number'),
        db.UniqueConstraint('disease_site_id', 'url', name='uq_tnm_ref_url'),
    )
    
    def __repr__(self):
        return f'<TnmReference [{self.ref_number}] for DiseaseSite {self.disease_site_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'disease_site_id': self.disease_site_id,
            'ref_number': self.ref_number,
            'title': self.title,
            'url': self.url,
            'journal': self.journal,
            'year': self.year,
            'is_inline': self.is_inline,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class CaseImage(db.Model):
    """Store images for a case - using Cloudinary for storage"""
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False)
    
    # Legacy binary field - kept for backward compatibility during migration
    image_data = db.Column(db.LargeBinary, nullable=True)  # Deprecated: will be removed
    
    # Cloudinary storage fields (preferred)
    image_url = db.Column(db.String(500), nullable=True)  # Full Cloudinary URL
    image_public_id = db.Column(db.String(255), nullable=True)  # For Cloudinary deletion
    image_thumbnail_url = db.Column(db.String(500), nullable=True)  # Auto-generated thumbnail
    
    image_filename = db.Column(db.String(255), nullable=False)
    image_type = db.Column(db.String(50), nullable=False)  # e.g., 'image/png', 'image/jpeg'
    image_description = db.Column(db.Text, default='')  # Optional image description
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<CaseImage {self.image_filename} for Case {self.case_id}>'
    
    @property
    def is_cloudinary(self):
        """Check if image is stored in Cloudinary"""
        return self.image_url is not None


class CaseReferenceImage(db.Model):
    """Admin-curated reference images for cases (CT/MRI, anatomy diagrams, concept diagrams).
    All images MUST be Creative Commons or public domain. Stored for display in Anatomy tab."""
    __tablename__ = 'case_reference_image'
    
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)
    
    source_url = db.Column(db.String(1000), nullable=False)
    source_domain = db.Column(db.String(255), nullable=False)
    thumbnail_url = db.Column(db.String(500), nullable=True)
    # image_type: 'ct_mri' | 'anatomy_diagram' | 'concept_diagram'
    image_type = db.Column(db.String(50), nullable=False, default='ct_mri')
    modality = db.Column(db.String(50), nullable=True)  # CT, MRI, etc. (for imaging type)
    
    ai_description = db.Column(db.Text, nullable=True)
    ai_relevance_score = db.Column(db.Float, nullable=True)
    admin_note = db.Column(db.Text, nullable=True)
    display_order = db.Column(db.Integer, default=0)
    added_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # REQUIRED: License must be Creative Commons or public domain
    license = db.Column(db.String(100), nullable=False, default='CC BY 4.0')
    attribution = db.Column(db.String(500), nullable=False)
    
    case = db.relationship('Case', backref=db.backref('reference_images', lazy=True, cascade='all, delete-orphan'))
    added_by = db.relationship('User', backref='added_reference_images')
    
    def to_dict(self):
        return {
            'id': self.id,
            'case_id': self.case_id,
            'source_url': self.source_url,
            'source_domain': self.source_domain,
            'thumbnail_url': self.thumbnail_url,
            'image_type': self.image_type,
            'modality': self.modality,
            'ai_description': self.ai_description,
            'admin_note': self.admin_note,
            'display_order': self.display_order,
            'license': self.license,
            'attribution': self.attribution,
        }


class CaseImageStack(db.Model):
    """Image stack (Study in UI) for a case. R2 or legacy OneDrive. Series (axial, sagittal, etc.) with image URLs/keys. Multiple studies per case allowed."""
    __tablename__ = 'case_image_stack'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)
    study_label = db.Column(db.String(200), nullable=True)  # Admin-defined label (e.g. "CT temporal bone"); required for new R2 stacks
    display_order = db.Column(db.Integer, default=0, nullable=False)
    onedrive_share_id = db.Column(db.String(500), nullable=True)  # nullable for R2-only stacks
    onedrive_folder_path = db.Column(db.String(500), nullable=True)
    config_json = db.Column(db.Text, nullable=False)  # JSON: { "axial": [url1, url2], "sagittal": [...] }
    storage_backend = db.Column(db.String(20), default="onedrive", nullable=True)  # 'onedrive' | 'r2'
    r2_config_json = db.Column(db.Text, nullable=True)  # JSON: { "axial": ["key1", "key2"], ... }
    # Encrypted refresh token for server-side URL refresh (all viewers get fresh URLs)
    onedrive_refresh_token_encrypted = db.Column(db.Text, nullable=True)
    # Rich-text case description (TinyMCE HTML) for image stack
    description_html = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    case = db.relationship('Case', backref=db.backref('image_stacks', lazy=True, order_by='CaseImageStack.display_order', cascade='all, delete-orphan'))
    created_by = db.relationship('User', backref='created_image_stacks')

    def get_config(self):
        import json
        if self.config_json:
            try:
                return json.loads(self.config_json)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_config(self, config: dict):
        import json
        self.config_json = json.dumps(config, ensure_ascii=False) if config else "{}"

    def get_r2_config(self) -> dict:
        """Return R2 object keys per plan: { 'axial': ['key1', 'key2'], ... }."""
        import json
        val = self.r2_config_json
        if val:
            if isinstance(val, dict):
                return val  # jsonb column auto-deserialized by psycopg2
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_r2_config(self, config: dict):
        import json
        self.r2_config_json = json.dumps(config, ensure_ascii=False) if config else None


class CaseImageAnnotation(db.Model):
    """Annotations for a study (admin-created arrows, text, measurements). One record per study (stack_id). Legacy: case_id for backward compat."""
    __tablename__ = 'case_image_annotation'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=True, index=True)  # Legacy; prefer stack_id
    stack_id = db.Column(db.Integer, db.ForeignKey('case_image_stack.id'), nullable=True, unique=True, index=True)  # Per-study annotations
    annotations_json = db.Column(db.Text, nullable=False, default='{}')  # { seriesName: { imageIndex: [annotations] } }
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    case = db.relationship('Case', backref=db.backref('image_annotations', lazy=True, uselist=True, cascade='all, delete-orphan'))
    stack = db.relationship('CaseImageStack', backref=db.backref('image_annotations', uselist=False, lazy=True, cascade='all, delete-orphan'))
    created_by = db.relationship('User', backref='created_image_annotations')

    def get_annotations(self):
        import json
        val = self.annotations_json
        if val:
            if isinstance(val, dict):
                return val  # Already deserialized (jsonb column)
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_annotations(self, annotations: dict):
        import json
        self.annotations_json = json.dumps(annotations, ensure_ascii=False) if annotations else "{}"


class CandidateNote(db.Model):
    """Store student/candidate notes for cases and TNM disease sites"""
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=True, index=True)  # nullable for TNM notes
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    note_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Optional: TNM disease site association (for TNM view notes)
    tnm_disease_id = db.Column(db.Integer, db.ForeignKey('ajcc_disease_site.id'), nullable=True, index=True)
    
    # Relationships
    tnm_disease = db.relationship('AJCCDiseaseSite', backref=db.backref('student_notes', lazy=True))
    
    # Composite index for efficient lookups
    __table_args__ = (
        db.Index('idx_case_user', 'case_id', 'user_id'),
        db.Index('idx_tnm_user', 'tnm_disease_id', 'user_id'),
    )
    
    def __repr__(self):
        return f'<CandidateNote Case:{self.case_id} User:{self.user_id}>'


class TextHighlight(db.Model):
    """Store text highlights for search and personalization"""
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=True, index=True)  # nullable for TNM highlights
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    text_content = db.Column(db.Text, nullable=False)  # The highlighted text
    highlight_color = db.Column(db.String(20), nullable=False, default='yellow')  # yellow, green, pink, blue
    field_name = db.Column(db.String(50), nullable=False)  # question, answer, discussion, notes, tnm_quick_ref, etc.
    # Context for reliable repositioning on page reload
    context_before = db.Column(db.String(100), nullable=True)  # 50 chars before the highlight
    context_after = db.Column(db.String(100), nullable=True)  # 50 chars after the highlight
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Optional: TNM disease site association (for TNM view highlights)
    tnm_disease_id = db.Column(db.Integer, db.ForeignKey('ajcc_disease_site.id'), nullable=True, index=True)
    
    # Relationships
    tnm_disease = db.relationship('AJCCDiseaseSite', backref=db.backref('student_highlights', lazy=True))
    
    # Composite index for efficient lookups
    __table_args__ = (
        db.Index('idx_case_user_highlight', 'case_id', 'user_id'),
        db.Index('idx_text_search', 'text_content'),  # For keyword search
        db.Index('idx_tnm_user_highlight', 'tnm_disease_id', 'user_id'),
    )
    
    def __repr__(self):
        return f'<TextHighlight Case:{self.case_id} User:{self.user_id} Color:{self.highlight_color}>'


# ==================== TNM CALCULATOR CONTENT MODEL ====================

class TNMCalculatorContent(db.Model):
    """
    Stores AI-generated TNM calculator HTML and algorithm content.
    Each record represents a calculator for a specific cancer type.
    The HTML is also saved as a file in tnm_calculator/calculators/
    """
    __tablename__ = 'tnm_calculator_content'

    id = db.Column(db.Integer, primary_key=True)

    # Cancer identification
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)  # e.g. 'oropharynx', 'lung'
    cancer_name = db.Column(db.String(200), nullable=False)  # Display name: 'Oropharynx', 'Lung (NSCLC)'
    body_section = db.Column(db.String(100), nullable=False)  # e.g. 'Head and Neck', 'Thorax'

    # Generated content
    calculator_html = db.Column(db.Text, nullable=True)  # The full calculator HTML for decision tree UI
    algorithm_discussion_html = db.Column(db.Text, nullable=True)  # Algorithm content for case discussion
    staging_system = db.Column(db.String(50), default='AJCC 9th Edition')  # e.g. 'AJCC 9th Edition', 'FIGO 2023'

    # Metadata
    special_features = db.Column(db.Text, nullable=True)  # JSON array: ['HPV+ Staging', 'HPV- Staging']
    description = db.Column(db.String(500), nullable=True)  # Short description
    is_available = db.Column(db.Boolean, default=False, nullable=False)  # Whether calculator is ready for use

    # AI generation tracking
    generation_prompt = db.Column(db.Text, nullable=True)  # The prompt used to generate this content
    generation_model = db.Column(db.String(100), nullable=True)  # e.g. 'claude-3-opus-20240229'
    generated_at = db.Column(db.DateTime, nullable=True)  # When AI generation completed

    # Associated case (if linked to an algorithm case document)
    algorithm_case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=True, index=True)

    # Editing
    last_edit_note = db.Column(db.String(500), nullable=True)  # What was changed in last manual edit

    # Audit
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    algorithm_case = db.relationship('Case', backref=db.backref('tnm_calculator_content', uselist=False, lazy=True))
    created_by = db.relationship('User', backref='created_tnm_calculators')

    def get_special_features(self):
        """Return special features as list"""
        import json
        if self.special_features:
            try:
                return json.loads(self.special_features)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_special_features(self, features: list):
        """Set special features from list"""
        import json
        self.special_features = json.dumps(features, ensure_ascii=False) if features else None

    def to_dict(self):
        """Return model as dictionary for API responses"""
        return {
            'id': self.id,
            'slug': self.slug,
            'cancer_name': self.cancer_name,
            'body_section': self.body_section,
            'staging_system': self.staging_system,
            'description': self.description,
            'special_features': self.get_special_features(),
            'is_available': self.is_available,
            'algorithm_case_id': self.algorithm_case_id,
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<TNMCalculatorContent {self.slug} ({self.cancer_name})>'


class TNMGeneratorJob(db.Model):
    """
    Job queue for TNM calculator generation.
    Allows async generation with cron processing (works around Vercel 10s timeout).
    """
    __tablename__ = 'tnm_generator_job'

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(36), unique=True, nullable=False, index=True)  # UUID

    # Job parameters
    slug = db.Column(db.String(100), nullable=False)
    cancer_name = db.Column(db.String(200), nullable=False)
    body_section = db.Column(db.String(100), nullable=False)
    staging_system = db.Column(db.String(50), default='AJCC 9th Edition')
    description = db.Column(db.String(500), nullable=True)
    special_features = db.Column(db.Text, nullable=True)  # JSON array
    special_notes = db.Column(db.Text, nullable=True)
    overwrite = db.Column(db.Boolean, default=False)  # Overwrite existing calculator

    # Status: pending, running, completed, failed
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    error_message = db.Column(db.Text, nullable=True)

    # Timing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    # User who requested
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_by = db.relationship('User', backref='tnm_generator_jobs')

    def to_dict(self):
        return {
            'job_id': self.job_id,
            'slug': self.slug,
            'cancer_name': self.cancer_name,
            'status': self.status,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

    def __repr__(self):
        return f'<TNMGeneratorJob {self.job_id} ({self.slug}): {self.status}>'


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


# ==================== SPACED REPETITION STUDY SYSTEM ====================
# SM-2 algorithm implementation for Q&A pair mastery tracking

class UserQAProgress(db.Model):
    """SM-2 spaced repetition progress per user per question."""
    __tablename__ = 'user_qa_progress'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False, index=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)  # Denormalized for module queries

    # SM-2 parameters
    ease_factor = db.Column(db.Float, default=2.5, nullable=False)
    interval_days = db.Column(db.Integer, default=0, nullable=False)
    repetition_number = db.Column(db.Integer, default=0, nullable=False)
    next_review_date = db.Column(db.Date, nullable=False, index=True)
    last_reviewed_at = db.Column(db.DateTime, nullable=True)

    # Stats
    times_correct = db.Column(db.Integer, default=0, nullable=False)
    times_incorrect = db.Column(db.Integer, default=0, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'question_id', name='uq_user_question_progress'),
        db.Index('idx_user_qa_due', 'user_id', 'next_review_date'),
    )

    user = db.relationship('User', backref='qa_progress', lazy=True)
    question = db.relationship('Question', backref='user_progress', lazy=True)
    case = db.relationship('Case', backref='qa_progress', lazy=True)

    def __repr__(self):
        return f'<UserQAProgress user={self.user_id} q={self.question_id} interval={self.interval_days}d>'


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


# ==================== FORUM DISCUSSION MODELS ====================
# These models support the case-specific discussion forum for students

class ForumMessage(db.Model):
    """
    Stores forum messages for case discussions and TNM disease site discussions.
    Messages are shared across all users for a given case or TNM disease.
    """
    __tablename__ = 'forum_message'
    
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=True, index=True)  # nullable for TNM forums
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Optional: TNM disease site association (for TNM view forum)
    tnm_disease_id = db.Column(db.Integer, db.ForeignKey('ajcc_disease_site.id'), nullable=True, index=True)
    
    # Message content (HTML supported)
    content = db.Column(db.Text, nullable=False)
    
    # Voting - net score (upvotes - downvotes)
    vote_score = db.Column(db.Integer, default=0, nullable=False, index=True)
    
    # Admin can pin important messages
    is_pinned = db.Column(db.Boolean, default=False, index=True)
    
    # Soft delete (hide rather than remove)
    is_deleted = db.Column(db.Boolean, default=False, index=True)
    
    # Flag count (cached for performance)
    flag_count = db.Column(db.Integer, default=0, index=True)
    
    # Cloudinary image fields (URLs only - no binary data!)
    image_url = db.Column(db.String(500), nullable=True)  # Full Cloudinary URL
    image_public_id = db.Column(db.String(255), nullable=True)  # For deletion
    image_thumbnail_url = db.Column(db.String(500), nullable=True)  # Auto-generated thumbnail
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    author = db.relationship('User', backref='forum_messages', lazy=True)
    # case relationship defined on Case model with cascade delete
    votes = db.relationship('ForumMessageVote', backref='message', lazy=True, cascade='all, delete-orphan')
    flags = db.relationship('ForumMessageFlag', backref='message', lazy=True, cascade='all, delete-orphan')
    tnm_disease = db.relationship('AJCCDiseaseSite', backref=db.backref('forum_messages', lazy=True))
    
    __table_args__ = (
        db.Index('idx_forum_case_votes', 'case_id', 'vote_score'),
        db.Index('idx_forum_case_pinned', 'case_id', 'is_pinned'),
        db.Index('idx_forum_tnm_disease', 'tnm_disease_id'),
        db.Index('idx_forum_flagged', 'flag_count'),
    )
    
    def __repr__(self):
        return f'<ForumMessage {self.id} Case:{self.case_id} User:{self.user_id} Score:{self.vote_score}>'


class ForumMessageVote(db.Model):
    """
    Tracks individual user votes on forum messages.
    Ensures each user can only vote once per message.
    """
    __tablename__ = 'forum_message_vote'
    
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('forum_message.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    # +1 for upvote, -1 for downvote
    vote_value = db.Column(db.Integer, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Each user can only vote once per message
    __table_args__ = (
        db.UniqueConstraint('message_id', 'user_id', name='uq_message_user_vote'),
    )
    
    def __repr__(self):
        return f'<ForumMessageVote Msg:{self.message_id} User:{self.user_id} Vote:{self.vote_value}>'


class ForumMessageFlag(db.Model):
    """
    User flags on forum messages for moderation.
    Users can flag inappropriate, spam, or incorrect messages.
    """
    __tablename__ = 'forum_message_flag'
    
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('forum_message.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Flag reason: spam, inappropriate, incorrect, other
    reason = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text, nullable=True)  # Optional additional details
    
    # Resolution tracking
    is_resolved = db.Column(db.Boolean, default=False, index=True)
    resolved_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    flagger = db.relationship('User', foreign_keys=[user_id], backref='flagged_messages')
    resolver = db.relationship('User', foreign_keys=[resolved_by_user_id])
    
    # Each user can only flag a message once
    __table_args__ = (
        db.UniqueConstraint('message_id', 'user_id', name='uq_message_user_flag'),
        db.Index('idx_unresolved_flags', 'is_resolved', 'created_at'),
    )
    
    def __repr__(self):
        return f'<ForumMessageFlag Msg:{self.message_id} User:{self.user_id} Reason:{self.reason}>'


# ==================== ADMIN APPROVAL SYSTEM ====================

class AdminApprovalCode(db.Model):
    """
    Stores approval codes for sensitive admin actions.
    When a non-superadmin tries to perform restricted actions (like promoting to admin
    or deleting another admin), a code is generated and emailed to the superadmin.
    The requesting admin must enter this code to complete the action.
    """
    __tablename__ = 'admin_approval_code'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(8), unique=True, nullable=False, index=True)  # Random 8-char code
    
    # Who is requesting the action
    requesting_admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Who is the target of the action
    target_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    # What action is being requested
    # Values: 'promote_to_admin', 'promote_to_content_manager', 'demote_admin', 'delete_admin'
    action = db.Column(db.String(50), nullable=False)
    
    # Additional context (e.g., new role value)
    action_details = db.Column(db.JSON, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)  # 24 hour expiry by default
    
    # Status
    used = db.Column(db.Boolean, default=False, index=True)
    used_at = db.Column(db.DateTime, nullable=True)
    cancelled = db.Column(db.Boolean, default=False, index=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    cancelled_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Relationships
    requesting_admin = db.relationship('User', foreign_keys=[requesting_admin_id], backref='requested_approvals')
    target_user = db.relationship('User', foreign_keys=[target_user_id], backref='approval_targets')
    cancelled_by = db.relationship('User', foreign_keys=[cancelled_by_user_id])
    
    def is_valid(self):
        """Check if code is still valid (not used, not expired, not cancelled)"""
        if self.used:
            return False
        if self.cancelled:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        return True
    
    def is_pending(self):
        """Check if this approval is still pending (not used, not cancelled, not expired)"""
        return self.is_valid()
    
    def mark_used(self):
        """Mark the code as used"""
        self.used = True
        self.used_at = datetime.utcnow()
    
    def mark_cancelled(self, cancelled_by_id):
        """Mark the code as cancelled by superadmin"""
        self.cancelled = True
        self.cancelled_at = datetime.utcnow()
        self.cancelled_by_user_id = cancelled_by_id
    
    def __repr__(self):
        status = 'CANCELLED' if self.cancelled else ('USED' if self.used else ('VALID' if self.is_valid() else 'EXPIRED'))
        return f'<AdminApprovalCode {self.code} Action:{self.action} Status:{status}>'


class AccountRecoveryCode(db.Model):
    """
    Stores recovery codes for soft-deleted student accounts.
    Students can recover their accounts within 31 days using a code sent via email.
    """
    __tablename__ = 'account_recovery_code'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(8), unique=True, nullable=False, index=True)  # 8-char code
    
    # User requesting recovery
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Request metadata for security logging
    request_ip = db.Column(db.String(50), nullable=True)
    request_user_agent = db.Column(db.String(500), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)  # 15 minutes by default
    
    # Status
    used = db.Column(db.Boolean, default=False, index=True)
    used_at = db.Column(db.DateTime, nullable=True)
    
    # Rate limiting - track attempts
    attempts = db.Column(db.Integer, default=0)
    last_attempt_at = db.Column(db.DateTime, nullable=True)
    
    # Relationship
    user = db.relationship('User', backref='recovery_codes')
    
    def is_valid(self):
        """Check if code is still valid (not used, not expired)"""
        if self.used:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        return True
    
    def mark_used(self):
        """Mark the code as used"""
        self.used = True
        self.used_at = datetime.utcnow()
    
    def record_attempt(self):
        """Record a verification attempt"""
        self.attempts += 1
        self.last_attempt_at = datetime.utcnow()
    
    def __repr__(self):
        return f'<AccountRecoveryCode {self.code} User:{self.user_id} Valid:{self.is_valid()}>'


# ==================== AJCC TNM STAGING MODELS ====================

class AJCCBodySection(db.Model):
    """AJCC body sections (e.g., Thorax, Head and Neck, etc.)"""
    id = db.Column(db.Integer, primary_key=True)
    section_name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(100), nullable=False, unique=True, index=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    disease_sites = db.relationship('AJCCDiseaseSite', backref='body_section', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<AJCCBodySection {self.section_name}>'


class AJCCDiseaseSite(db.Model):
    """AJCC disease sites within body sections (e.g., Lung, Breast, etc.)"""
    id = db.Column(db.Integer, primary_key=True)
    body_section_id = db.Column(db.Integer, db.ForeignKey('ajcc_body_section.id'), nullable=False, index=True)
    disease_name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), nullable=False, index=True)
    ajcc_url_path = db.Column(db.String(300), nullable=False)  # e.g., "thorax/lung"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Display ordering within section
    display_order = db.Column(db.Integer, default=0)  # Lower numbers appear first
    
    # FRCR App Integration - maps AJCC sites to app's module/body_part/age_group
    frcr_module = db.Column(db.String(100), nullable=True)  # e.g., "CNS and Head & Neck (incl. spine, eyes, ENT, salivary, dental)"
    frcr_body_part = db.Column(db.String(100), nullable=True)  # e.g., "Brain and Pituitary", "HEAD_NECK"
    frcr_age_group = db.Column(db.String(100), nullable=True)  # e.g., "Adult", "Pediatric"
    
    # Relationships
    mappings = db.relationship('AJCCDiseaseMapping', backref='disease_site', lazy=True, cascade='all, delete-orphan')
    staging_data = db.relationship('AJCCStagingData', backref='disease_site', lazy=True, cascade='all, delete-orphan')
    
    # Unique constraint: same disease name can exist in different sections
    __table_args__ = (
        db.UniqueConstraint('body_section_id', 'slug', name='uq_body_section_disease_slug'),
        db.Index('idx_disease_slug', 'slug'),
    )
    
    def __repr__(self):
        return f'<AJCCDiseaseSite {self.disease_name}>'


class AJCCDiagnosisYear(db.Model):
    """AJCC diagnosis years (2024, 2025, 2026)"""
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, unique=True)
    is_default = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    staging_data = db.relationship('AJCCStagingData', backref='diagnosis_year', lazy=True)
    
    def __repr__(self):
        return f'<AJCCDiagnosisYear {self.year}>'


class AJCCDiseaseMapping(db.Model):
    """Maps AJCC disease sites to app FRCRModule and BodyPart"""
    id = db.Column(db.Integer, primary_key=True)
    disease_site_id = db.Column(db.Integer, db.ForeignKey('ajcc_disease_site.id'), nullable=False, index=True)
    frcr_module = db.Column(db.Enum(FRCRModule), nullable=True, index=True)
    body_part = db.Column(db.Enum(BodyPart), nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes for efficient querying
    __table_args__ = (
        db.Index('idx_disease_frcr_module', 'disease_site_id', 'frcr_module'),
        db.Index('idx_disease_body_part', 'disease_site_id', 'body_part'),
    )
    
    def __repr__(self):
        return f'<AJCCDiseaseMapping Disease:{self.disease_site_id} Module:{self.frcr_module} BodyPart:{self.body_part}>'


class AJCCStagingData(db.Model):
    """Stores TNM staging data with structured JSON and optional HTML sections"""
    id = db.Column(db.Integer, primary_key=True)
    disease_site_id = db.Column(db.Integer, db.ForeignKey('ajcc_disease_site.id'), nullable=False, index=True)
    diagnosis_year_id = db.Column(db.Integer, db.ForeignKey('ajcc_diagnosis_year.id'), nullable=False, index=True)
    
    # ============================================
    # PRIMARY DATA: Structured JSON (preferred)
    # ============================================
    
    # Core TNM staging data as clean JSON
    tnm_data_json = db.Column(db.Text, nullable=True)  # Main TNM staging: T, N, M definitions + stage groups
    
    # Additional structured sections as JSON
    cancers_staged_json = db.Column(db.Text, nullable=True)  # List of cancers staged by this system
    cancers_not_staged_json = db.Column(db.Text, nullable=True)  # List of cancers NOT staged
    summary_changes_json = db.Column(db.Text, nullable=True)  # Summary of changes from previous edition
    primary_sites_json = db.Column(db.Text, nullable=True)  # ICD-O codes and primary site descriptions
    histopathologic_types_json = db.Column(db.Text, nullable=True)  # Histopathologic type information
    imaging_workup_json = db.Column(db.Text, nullable=True)  # Clinical staging/imaging workup data
    staging_rules_json = db.Column(db.Text, nullable=True)  # Staging rules and criteria
    common_scenarios_json = db.Column(db.Text, nullable=True)  # Common staging scenarios/examples
    notes_json = db.Column(db.Text, nullable=True)  # Explanatory notes, figures references
    
    # ============================================
    # LEGACY: HTML sections (for backward compatibility)
    # ============================================
    section_1_quick_reference_html = db.Column(db.Text, nullable=True)
    section_2_cancers_staged_html = db.Column(db.Text, nullable=True)
    section_3_cancers_not_staged_html = db.Column(db.Text, nullable=True)
    section_4_summary_changes_html = db.Column(db.Text, nullable=True)
    section_5_primary_site_html = db.Column(db.Text, nullable=True)
    section_6_histopathologic_type_html = db.Column(db.Text, nullable=True)
    section_7_clinical_staging_workup_html = db.Column(db.Text, nullable=True)
    section_8_staging_rules_html = db.Column(db.Text, nullable=True)
    section_9_common_scenarios_html = db.Column(db.Text, nullable=True)
    section_10_explanatory_notes_html = db.Column(db.Text, nullable=True)
    
    # Metadata
    raw_html_content = db.Column(db.Text, nullable=True)  # Store original full page HTML for reference
    extracted_at = db.Column(db.DateTime, default=datetime.utcnow)
    extracted_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    last_updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    data_version = db.Column(db.Integer, default=2)  # 1=HTML only, 2=JSON+HTML
    
    # ============================================
    # CURATED DATA: Admin-edited content for student viewing
    # ============================================
    # Original AJCC data is preserved above; curated versions are shown to students
    
    # Quick Reference: TNM tables + core staging definitions (largely unchanged from AJCC)
    curated_quick_reference_html = db.Column(db.Text, nullable=True)
    
    # Explanatory Notes: Admin-curated content with interpretations, clarifications, high-yield points
    curated_explanatory_notes_html = db.Column(db.Text, nullable=True)
    
    # Curation status
    is_curated = db.Column(db.Boolean, default=False, index=True)  # True when admin has curated this data
    curated_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    curated_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    extracted_by = db.relationship('User', foreign_keys=[extracted_by_user_id], backref='extracted_tnm_data')
    curated_by = db.relationship('User', foreign_keys=[curated_by_user_id], backref='curated_tnm_data')
    
    # Unique constraint: one staging data record per disease/year combination
    __table_args__ = (
        db.UniqueConstraint('disease_site_id', 'diagnosis_year_id', name='uq_disease_year_staging'),
        db.Index('idx_disease_year', 'disease_site_id', 'diagnosis_year_id'),
    )
    
    def __repr__(self):
        return f'<AJCCStagingData Disease:{self.disease_site_id} Year:{self.diagnosis_year_id}>'
    
    # ============================================
    # JSON Data Access Methods
    # ============================================
    
    def get_tnm_data(self):
        """Get parsed TNM staging data as dict"""
        import json
        if self.tnm_data_json:
            try:
                return json.loads(self.tnm_data_json)
            except:
                return None
        return None
    
    def set_tnm_data(self, data):
        """Set TNM staging data from dict"""
        import json
        self.tnm_data_json = json.dumps(data, ensure_ascii=False) if data else None
    
    def get_t_definitions(self):
        """Get T stage definitions"""
        tnm = self.get_tnm_data()
        return tnm.get('t_definitions', []) if tnm else []
    
    def get_n_definitions(self):
        """Get N stage definitions (clinical and pathological). Normalizes list format to dict."""
        tnm = self.get_tnm_data()
        raw = tnm.get('n_definitions', {}) if tnm else {}
        if isinstance(raw, list):
            return {'clinical': raw, 'pathological': []}
        if isinstance(raw, dict) and ('clinical' in raw or 'pathological' in raw):
            return {
                'clinical': raw.get('clinical', []),
                'pathological': raw.get('pathological', []),
            }
        return {'clinical': [], 'pathological': []}
    
    def get_m_definitions(self):
        """Get M stage definitions"""
        tnm = self.get_tnm_data()
        return tnm.get('m_definitions', []) if tnm else []
    
    def get_stage_groups(self):
        """Get prognostic stage group combinations"""
        tnm = self.get_tnm_data()
        return tnm.get('stage_groups', []) if tnm else []
    
    def get_stage_for_tnm(self, t_stage, n_stage, m_stage):
        """
        Look up the prognostic stage for given T, N, M values.
        
        Args:
            t_stage: T stage value (e.g., "T1", "T2", "T3")
            n_stage: N stage value (e.g., "N0", "N1", "N2")
            m_stage: M stage value (e.g., "M0", "M1")
            
        Returns:
            Stage group string (e.g., "I", "II", "IVA") or None if not found
        """
        stage_groups = self.get_stage_groups()
        
        for sg in stage_groups:
            t_match = self._matches_tnm_pattern(t_stage, sg.get('T', ''))
            n_match = self._matches_tnm_pattern(n_stage, sg.get('N', ''))
            m_match = self._matches_tnm_pattern(m_stage, sg.get('M', ''))
            
            if t_match and n_match and m_match:
                return sg.get('stage')
        
        return None
    
    def _matches_tnm_pattern(self, value, pattern):
        """Check if a TNM value matches a pattern (e.g., "T1" matches "T1, T2, T3" or "Any T")"""
        if not pattern or not value:
            return False
        
        pattern = pattern.strip()
        value = value.strip().upper()
        
        # Handle "Any X" patterns
        if pattern.lower().startswith('any'):
            return True
        
        # Split on comma first, then handle each option
        options = [opt.strip().upper() for opt in pattern.split(',')]
        
        for opt in options:
            # Handle range patterns like "T3-T4" or "T2a-T2b" or "T1mi-T1a" or "M1a-M1b"
            if '-' in opt:
                parts = opt.split('-')
                if len(parts) == 2:
                    start, end = parts[0].strip(), parts[1].strip()
                    # Exact match with start or end
                    if value == start or value == end:
                        return True
                    # Value is subcategory of start or end (e.g., T3a matches T3-T4)
                    # But NOT T10 matching T1 - extra chars must not start with digit
                    if value.startswith(start) and len(value) > len(start):
                        extra = value[len(start):]
                        if not extra[0].isdigit():
                            return True
                    if value.startswith(end) and len(value) > len(end):
                        extra = value[len(end):]
                        if not extra[0].isdigit():
                            return True
                    # Pattern part starts with value (e.g., M1 matches M1a-M1b)
                    # Validate the pattern's extra chars too
                    if start.startswith(value) and len(start) > len(value):
                        extra = start[len(value):]
                        if not extra[0].isdigit():
                            return True
                    if end.startswith(value) and len(end) > len(value):
                        extra = end[len(value):]
                        if not extra[0].isdigit():
                            return True
            elif value == opt:
                return True
            # Handle subcategory matching (e.g., "T1a" matches "T1")
            # Extra chars must not start with a digit (T10 should NOT match T1)
            elif value.startswith(opt) and len(value) > len(opt):
                extra = value[len(opt):]
                if not extra[0].isdigit():
                    return True
            # Handle parent category matching (e.g., "M1" matches "M1a", "M1b")
            elif opt.startswith(value) and len(opt) > len(value):
                extra = opt[len(value):]
                if not extra[0].isdigit():
                    return True
        
        return False
    
    def get_json_section(self, section_name):
        """Get a JSON section by name"""
        import json
        section_map = {
            'tnm': self.tnm_data_json,
            'cancers_staged': self.cancers_staged_json,
            'cancers_not_staged': self.cancers_not_staged_json,
            'summary_changes': self.summary_changes_json,
            'primary_sites': self.primary_sites_json,
            'histopathologic_types': self.histopathologic_types_json,
            'imaging_workup': self.imaging_workup_json,
            'staging_rules': self.staging_rules_json,
            'common_scenarios': self.common_scenarios_json,
            'notes': self.notes_json,
        }
        json_str = section_map.get(section_name)
        if json_str:
            try:
                return json.loads(json_str)
            except:
                return None
        return None
    
    def set_json_section(self, section_name, data):
        """Set a JSON section by name"""
        import json
        section_map = {
            'tnm': 'tnm_data_json',
            'cancers_staged': 'cancers_staged_json',
            'cancers_not_staged': 'cancers_not_staged_json',
            'summary_changes': 'summary_changes_json',
            'primary_sites': 'primary_sites_json',
            'histopathologic_types': 'histopathologic_types_json',
            'imaging_workup': 'imaging_workup_json',
            'staging_rules': 'staging_rules_json',
            'common_scenarios': 'common_scenarios_json',
            'notes': 'notes_json',
        }
        field_name = section_map.get(section_name)
        if field_name:
            json_str = json.dumps(data, ensure_ascii=False) if data else None
            setattr(self, field_name, json_str)
    
    def to_full_json(self):
        """Export all data as a complete JSON structure"""
        import json
        result = {
            'id': self.id,
            'disease_site_id': self.disease_site_id,
            'disease_name': self.disease_site.disease_name if self.disease_site else None,
            'diagnosis_year': self.diagnosis_year.year if self.diagnosis_year else None,
            'extracted_at': self.extracted_at.isoformat() if self.extracted_at else None,
            'data_version': self.data_version,
            'tnm_staging': self.get_tnm_data(),
            'sections': {
                'cancers_staged': self.get_json_section('cancers_staged'),
                'cancers_not_staged': self.get_json_section('cancers_not_staged'),
                'summary_changes': self.get_json_section('summary_changes'),
                'primary_sites': self.get_json_section('primary_sites'),
                'histopathologic_types': self.get_json_section('histopathologic_types'),
                'imaging_workup': self.get_json_section('imaging_workup'),
                'staging_rules': self.get_json_section('staging_rules'),
                'common_scenarios': self.get_json_section('common_scenarios'),
                'notes': self.get_json_section('notes'),
            }
        }
        return result
    
    # ============================================
    # Legacy HTML Methods (backward compatibility)
    # ============================================
    
    def get_section_html(self, section_number):
        """Get HTML content for a specific section (1-10) - LEGACY"""
        section_map = {
            1: self.section_1_quick_reference_html,
            2: self.section_2_cancers_staged_html,
            3: self.section_3_cancers_not_staged_html,
            4: self.section_4_summary_changes_html,
            5: self.section_5_primary_site_html,
            6: self.section_6_histopathologic_type_html,
            7: self.section_7_clinical_staging_workup_html,
            8: self.section_8_staging_rules_html,
            9: self.section_9_common_scenarios_html,
            10: self.section_10_explanatory_notes_html,
        }
        return section_map.get(section_number)
    
    def set_section_html(self, section_number, html_content):
        """Set HTML content for a specific section (1-10) - LEGACY"""
        section_map = {
            1: 'section_1_quick_reference_html',
            2: 'section_2_cancers_staged_html',
            3: 'section_3_cancers_not_staged_html',
            4: 'section_4_summary_changes_html',
            5: 'section_5_primary_site_html',
            6: 'section_6_histopathologic_type_html',
            7: 'section_7_clinical_staging_workup_html',
            8: 'section_8_staging_rules_html',
            9: 'section_9_common_scenarios_html',
            10: 'section_10_explanatory_notes_html',
        }
        field_name = section_map.get(section_number)
        if field_name:
            setattr(self, field_name, html_content)
    
    # ============================================
    # Curated Data Methods
    # ============================================
    
    def get_all_raw_html_combined(self):
        """Get all raw AJCC HTML sections combined into a single HTML string for curation editing."""
        sections = []
        section_names = {
            1: "Quick Reference",
            2: "Cancers Staged",
            3: "Cancers Not Staged", 
            4: "Summary of Changes",
            5: "Primary Site",
            6: "Histopathologic Type",
            7: "Clinical Staging Workup",
            8: "Staging Rules",
            9: "Common Scenarios",
            10: "Explanatory Notes"
        }
        
        for i in range(1, 11):
            html = self.get_section_html(i)
            if html:
                sections.append(f'<div class="ajcc-section" data-section="{i}">')
                sections.append(f'<h2 class="section-title">{section_names.get(i, f"Section {i}")}</h2>')
                sections.append(html)
                sections.append('</div>')
                sections.append('<hr class="section-divider">')
        
        return '\n'.join(sections)
    
    def set_curated_data(self, quick_reference_html, explanatory_notes_html, user_id=None):
        """Set curated data and mark as curated."""
        from datetime import datetime
        self.curated_quick_reference_html = quick_reference_html
        self.curated_explanatory_notes_html = explanatory_notes_html
        self.is_curated = True
        self.curated_at = datetime.utcnow()
        if user_id:
            self.curated_by_user_id = user_id
    
    def get_student_view_data(self):
        """
        Get data for student viewing.
        Returns curated data if available, otherwise returns None (students shouldn't see uncurated).
        """
        if not self.is_curated:
            return None
        
        return {
            'quick_reference_html': self.curated_quick_reference_html,
            'explanatory_notes_html': self.curated_explanatory_notes_html,
            'curated_at': self.curated_at,
            'is_curated': True
        }


class AJCCStagingTimePrefix(db.Model):
    """
    Standard reference table for staging time prefixes.
    
    Prefixes indicate the timing and method of staging:
    - c: Clinical staging
    - p: Pathological staging
    - yc: Post-therapy clinical staging
    - yp: Post-therapy pathological staging
    - r: Recurrence staging
    - a: Autopsy staging
    """
    id = db.Column(db.Integer, primary_key=True)
    prefix = db.Column(db.String(5), nullable=False, unique=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AJCCStagingTimePrefix {self.prefix}: {self.name}>'
    
    @classmethod
    def seed_defaults(cls):
        """Seed the default staging time prefixes."""
        defaults = [
            {'prefix': 'c', 'name': 'Clinical', 'description': 'Clinical staging based on physical examination, imaging, endoscopy, biopsy, and surgical exploration', 'display_order': 1},
            {'prefix': 'p', 'name': 'Pathological', 'description': 'Pathological staging based on surgical resection specimen', 'display_order': 2},
            {'prefix': 'yc', 'name': 'Post-therapy Clinical', 'description': 'Clinical staging performed after neoadjuvant therapy', 'display_order': 3},
            {'prefix': 'yp', 'name': 'Post-therapy Pathological', 'description': 'Pathological staging performed after neoadjuvant therapy', 'display_order': 4},
            {'prefix': 'r', 'name': 'Recurrence', 'description': 'Staging at time of recurrence', 'display_order': 5},
            {'prefix': 'a', 'name': 'Autopsy', 'description': 'Staging determined at autopsy', 'display_order': 6}
        ]
        
        for prefix_data in defaults:
            existing = cls.query.filter_by(prefix=prefix_data['prefix']).first()
            if not existing:
                prefix = cls(**prefix_data)
                db.session.add(prefix)
        
        db.session.commit()


class IntelligentTNMData(db.Model):
    """
    Stores AI-generated, human-verified TNM intelligence data.
    
    This table stores the intelligent summaries, radiologist key points,
    upstaging triggers, and MDT decision points generated by ai_tnm.py
    after they have been reviewed and verified by an admin.
    
    Key principle: AI generates, human verifies, then stored for reuse.
    """
    __tablename__ = 'intelligent_tnm_data'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Link to AJCC disease site
    disease_site_id = db.Column(db.Integer, db.ForeignKey('ajcc_disease_site.id'), nullable=False, index=True)
    diagnosis_year_id = db.Column(db.Integer, db.ForeignKey('ajcc_diagnosis_year.id'), nullable=True, index=True)
    
    # TNM Memory Aid - Easy-to-remember staging summaries
    tnm_memory_aid_t = db.Column(db.Text, nullable=True)  # T-stage radiologist summary
    tnm_memory_aid_n = db.Column(db.Text, nullable=True)  # N-stage radiologist summary
    tnm_memory_aid_m = db.Column(db.Text, nullable=True)  # M-stage radiologist summary
    
    # Radiologist Key Points - JSON array of strings
    radiologist_key_points_json = db.Column(db.Text, nullable=True)
    
    # Upstaging Triggers - JSON array of strings (MDT-critical)
    upstaging_triggers_json = db.Column(db.Text, nullable=True)
    
    # MDT Critical Findings - JSON array of strings
    mdt_critical_findings_json = db.Column(db.Text, nullable=True)
    
    # Copy-Friendly Report Templates - JSON object
    copy_blocks_json = db.Column(db.Text, nullable=True)
    
    # Imaging Checklist - JSON array of strings
    imaging_checklist_json = db.Column(db.Text, nullable=True)
    
    # Reference Images - JSON array of objects with url, description, staging_relevance
    reference_images_json = db.Column(db.Text, nullable=True)
    
    # Warnings/Caveats - JSON array of strings
    warnings_json = db.Column(db.Text, nullable=True)
    
    # Essential TNM Concepts - JSON object with cancer-specific IARC content
    # Contains: cancer_type, figure_url, key_concepts, attribution
    # Only available for 7 cancers: breast, colorectal, ovarian, cervical, prostate, lymphoma, liver
    essential_tnm_json = db.Column(db.Text, nullable=True)
    
    # Verification metadata
    verified_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    source_case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=True)  # Which case triggered generation
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Version tracking
    version = db.Column(db.Integer, default=1)  # Increment when updated
    
    # Relationships
    disease_site = db.relationship('AJCCDiseaseSite', backref=db.backref('intelligent_data', lazy=True))
    diagnosis_year = db.relationship('AJCCDiagnosisYear', backref=db.backref('intelligent_data', lazy=True))
    verified_by = db.relationship('User', foreign_keys=[verified_by_user_id], backref='verified_tnm_intelligence')
    source_case = db.relationship('Case', foreign_keys=[source_case_id], backref='tnm_intelligence_generated')
    
    # DESIGN: One intelligence record per disease site (not per disease/year)
    # The diagnosis_year_id is kept for tracking but not for uniqueness.
    __table_args__ = (
        db.UniqueConstraint('disease_site_id', name='uq_disease_site_intelligence'),
        db.Index('idx_disease_intelligence', 'disease_site_id'),
    )
    
    def __repr__(self):
        return f'<IntelligentTNMData Disease:{self.disease_site_id} Year:{self.diagnosis_year_id}>'
    
    # ============================================
    # JSON Field Accessors
    # ============================================
    
    def get_radiologist_key_points(self):
        """Get radiologist key points as list."""
        import json
        if self.radiologist_key_points_json:
            try:
                return json.loads(self.radiologist_key_points_json)
            except:
                return []
        return []
    
    def set_radiologist_key_points(self, points: list):
        """Set radiologist key points from list."""
        import json
        self.radiologist_key_points_json = json.dumps(points, ensure_ascii=False) if points else None
    
    def get_upstaging_triggers(self):
        """Get upstaging triggers as list."""
        import json
        if self.upstaging_triggers_json:
            try:
                return json.loads(self.upstaging_triggers_json)
            except:
                return []
        return []
    
    def set_upstaging_triggers(self, triggers: list):
        """Set upstaging triggers from list."""
        import json
        self.upstaging_triggers_json = json.dumps(triggers, ensure_ascii=False) if triggers else None
    
    def get_mdt_critical_findings(self):
        """Get MDT critical findings as list."""
        import json
        if self.mdt_critical_findings_json:
            try:
                return json.loads(self.mdt_critical_findings_json)
            except:
                return []
        return []
    
    def set_mdt_critical_findings(self, findings: list):
        """Set MDT critical findings from list."""
        import json
        self.mdt_critical_findings_json = json.dumps(findings, ensure_ascii=False) if findings else None
    
    def get_copy_blocks(self):
        """Get copy blocks as dict."""
        import json
        if self.copy_blocks_json:
            try:
                return json.loads(self.copy_blocks_json)
            except:
                return {}
        return {}
    
    def set_copy_blocks(self, blocks: dict):
        """Set copy blocks from dict."""
        import json
        self.copy_blocks_json = json.dumps(blocks, ensure_ascii=False) if blocks else None
    
    def get_imaging_checklist(self):
        """Get imaging checklist as list."""
        import json
        if self.imaging_checklist_json:
            try:
                return json.loads(self.imaging_checklist_json)
            except:
                return []
        return []
    
    def set_imaging_checklist(self, checklist: list):
        """Set imaging checklist from list."""
        import json
        self.imaging_checklist_json = json.dumps(checklist, ensure_ascii=False) if checklist else None
    
    def get_reference_images(self):
        """Get reference images as list of dicts."""
        import json
        if self.reference_images_json:
            try:
                return json.loads(self.reference_images_json)
            except:
                return []
        return []
    
    def set_reference_images(self, images: list):
        """Set reference images from list of dicts."""
        import json
        self.reference_images_json = json.dumps(images, ensure_ascii=False) if images else None
    
    def get_warnings(self):
        """Get warnings as list."""
        import json
        if self.warnings_json:
            try:
                return json.loads(self.warnings_json)
            except:
                return []
        return []
    
    def set_warnings(self, warnings: list):
        """Set warnings from list."""
        import json
        self.warnings_json = json.dumps(warnings, ensure_ascii=False) if warnings else None
    
    def get_essential_tnm(self):
        """Get essential TNM data as dict."""
        import json
        if self.essential_tnm_json:
            try:
                return json.loads(self.essential_tnm_json)
            except:
                return None
        return None
    
    def set_essential_tnm(self, essential_data: dict):
        """Set essential TNM data from dict."""
        import json
        self.essential_tnm_json = json.dumps(essential_data, ensure_ascii=False) if essential_data else None
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'disease_site_id': self.disease_site_id,
            'diagnosis_year_id': self.diagnosis_year_id,
            'tnm_memory_aid': {
                'T': self.tnm_memory_aid_t,
                'N': self.tnm_memory_aid_n,
                'M': self.tnm_memory_aid_m,
            },
            'radiologist_key_points': self.get_radiologist_key_points(),
            'upstaging_triggers': self.get_upstaging_triggers(),
            'mdt_critical_findings': self.get_mdt_critical_findings(),
            'copy_blocks': self.get_copy_blocks(),
            'imaging_checklist': self.get_imaging_checklist(),
            'reference_images': self.get_reference_images(),
            'warnings': self.get_warnings(),
            'essential_tnm': self.get_essential_tnm(),
            'verified_by_user_id': self.verified_by_user_id,
            'source_case_id': self.source_case_id,
            'version': self.version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_ai_output(cls, ai_output: dict, disease_site_id: int, diagnosis_year_id: int = None,
                       verified_by_user_id: int = None, source_case_id: int = None):
        """
        Create IntelligentTNMData from AI output.
        
        Args:
            ai_output: Output from ai_tnm.generate_tnm_intelligence()
            disease_site_id: AJCC disease site ID
            diagnosis_year_id: Optional diagnosis year ID
            verified_by_user_id: User who verified the data
            source_case_id: Case that triggered generation
            
        Returns:
            IntelligentTNMData instance (not yet committed)
        """
        import json
        
        instance = cls(
            disease_site_id=disease_site_id,
            diagnosis_year_id=diagnosis_year_id,
            verified_by_user_id=verified_by_user_id,
            source_case_id=source_case_id,
        )
        
        # Extract TNM memory aid
        memory_aid = ai_output.get('tnm_memory_aid', {})
        instance.tnm_memory_aid_t = memory_aid.get('T')
        instance.tnm_memory_aid_n = memory_aid.get('N')
        instance.tnm_memory_aid_m = memory_aid.get('M')
        
        # Set JSON fields
        instance.set_radiologist_key_points(ai_output.get('radiologist_key_points', []))
        instance.set_upstaging_triggers(ai_output.get('upstaging_triggers', []))
        instance.set_mdt_critical_findings(ai_output.get('mdt_critical_findings', []))
        instance.set_copy_blocks(ai_output.get('copy_blocks', {}))
        instance.set_imaging_checklist(ai_output.get('imaging_checklist', []))
        instance.set_reference_images(ai_output.get('reference_images', []))
        instance.set_warnings(ai_output.get('warnings', []))
        instance.set_essential_tnm(ai_output.get('essential_tnm'))
        
        return instance


# ==================== ANATOMY FIGURE MODEL ====================

class AnatomyFigure(db.Model):
    """
    CC-licensed anatomy and staging figures for AI injection.
    
    Sources:
    - OpenStax Anatomy & Physiology 2e (CC BY 4.0)
    - IARC Essential TNM Guide (CC BY-NC-ND 3.0 IGO)
    - Radiopaedia diagrams (CC-NC-BY-SA 3.0)
    - Open Anatomy Project (Open Source)
    """
    __tablename__ = 'anatomy_figure'
    
    id = db.Column(db.Integer, primary_key=True)
    figure_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    
    # Classification
    source = db.Column(db.String(50), nullable=False, index=True)  # 'openstax', 'iarc', 'radiopaedia', 'open_anatomy'
    body_region = db.Column(db.String(100), index=True)  # 'thorax', 'head-neck', 'abdomen', 'msk'
    figure_type = db.Column(db.String(50))  # 'anatomy', 'staging', 'flowchart', 'cross-section'
    keywords = db.Column(db.JSON)  # ['lung', 'bronchi', 'respiratory']
    modality = db.Column(db.String(50))  # 'diagram', 'ct', 'mri', 'xray'
    
    # For TNM-specific figures (IARC)
    cancer_type = db.Column(db.String(100), index=True)  # 'lung', 'breast', etc.
    staging_category = db.Column(db.String(20))  # 'T', 'N', 'M', 'general', 'flowchart'
    
    # Image URLs
    original_url = db.Column(db.String(500))
    cloudinary_url = db.Column(db.String(500))
    cloudinary_public_id = db.Column(db.String(300))
    thumbnail_url = db.Column(db.String(500))
    
    # Attribution (IMPORTANT for CC compliance)
    license = db.Column(db.String(100), default='CC BY 4.0')
    attribution = db.Column(db.String(300), nullable=False)
    
    # Metadata
    chapter = db.Column(db.Integer)  # For OpenStax chapter reference
    page_number = db.Column(db.Integer)  # For IARC PDF page reference
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<AnatomyFigure {self.figure_id}: {self.title[:50]}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'figure_id': self.figure_id,
            'title': self.title,
            'description': self.description,
            'source': self.source,
            'body_region': self.body_region,
            'figure_type': self.figure_type,
            'keywords': self.keywords,
            'cancer_type': self.cancer_type,
            'staging_category': self.staging_category,
            'cloudinary_url': self.cloudinary_url,
            'thumbnail_url': self.thumbnail_url,
            'attribution': self.attribution,
            'license': self.license
        }
    
    def get_html(self, size='medium'):
        """Generate HTML for embedding in discussions."""
        sizes = {
            'small': 'max-width: 200px;',
            'medium': 'max-width: 400px;',
            'large': 'max-width: 600px;',
            'full': 'max-width: 100%;'
        }
        style = sizes.get(size, sizes['medium'])
        
        return f'''
<figure class="anatomy-figure" style="margin: 1rem 0; text-align: center;">
    <img src="{self.cloudinary_url}" alt="{self.title}" 
         style="{style} border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
    <figcaption style="font-size: 0.85em; color: #666; margin-top: 0.5rem; font-style: italic;">
        {self.title} – {self.attribution}
    </figcaption>
</figure>
'''
    
    @classmethod
    def find_by_keywords(cls, keywords: list, source: str = None, body_region: str = None, limit: int = 5):
        """Find figures matching keywords."""
        query = cls.query.filter(cls.is_active == True)
        
        if source:
            query = query.filter(cls.source == source)
        if body_region:
            query = query.filter(cls.body_region == body_region)
        
        # Score by keyword match (simple approach)
        all_figures = query.all()
        scored = []
        
        for fig in all_figures:
            fig_keywords = set(fig.keywords or [])
            search_keywords = set(k.lower() for k in keywords)
            overlap = len(fig_keywords & search_keywords)
            if overlap > 0:
                scored.append((overlap, fig))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        
        return [fig for score, fig in scored[:limit]]
    
    @classmethod
    def find_for_tnm(cls, cancer_type: str, staging_category: str = None):
        """Find IARC TNM figures for a specific cancer type."""
        query = cls.query.filter(
            cls.is_active == True,
            cls.source == 'iarc',
            cls.cancer_type == cancer_type.lower()
        )
        
        if staging_category:
            query = query.filter(cls.staging_category == staging_category.upper())
        
        return query.all()
    
    @classmethod
    def find_for_anatomy(cls, body_region: str, modality: str = None):
        """Find anatomy figures for a body region."""
        query = cls.query.filter(
            cls.is_active == True,
            cls.source.in_(['openstax', 'open_anatomy', 'radiopaedia']),
            cls.body_region == body_region.lower()
        )
        
        if modality:
            query = query.filter(cls.modality == modality.lower())
        
        return query.all()


# ==================== TNM IMAGE MODEL ====================

class TNMImage(db.Model):
    """
    Images uploaded for TNM disease sites.
    
    Stores images uploaded by admins for specific TNM disease sites,
    linked to Cloudinary for CDN delivery.
    """
    __tablename__ = 'tnm_image'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Link to AJCC disease site (required)
    disease_site_id = db.Column(db.Integer, db.ForeignKey('ajcc_disease_site.id'), nullable=False, index=True)
    
    # Optional: link to specific diagnosis year
    diagnosis_year_id = db.Column(db.Integer, db.ForeignKey('ajcc_diagnosis_year.id'), nullable=True, index=True)
    
    # Image metadata
    title = db.Column(db.String(300), nullable=True)
    description = db.Column(db.Text, nullable=True)  # Rich text (HTML) for detailed captions
    alt_text = db.Column(db.Text, nullable=True)  # Can be long for accessibility
    
    # Cloudinary storage
    cloudinary_url = db.Column(db.String(500), nullable=False)
    cloudinary_public_id = db.Column(db.String(300), nullable=False)
    
    # Image dimensions (useful for responsive layouts)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    
    # Classification
    image_type = db.Column(db.String(50), default='reference')  # 'reference', 'diagram', 'staging', 'anatomy'
    
    # Tracking
    uploaded_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    disease_site = db.relationship('AJCCDiseaseSite', backref=db.backref('images', lazy='dynamic'))
    diagnosis_year = db.relationship('AJCCDiagnosisYear', backref=db.backref('tnm_images', lazy='dynamic'))
    uploaded_by = db.relationship('User', backref=db.backref('uploaded_tnm_images', lazy='dynamic'))
    
    # Index for efficient queries
    __table_args__ = (
        db.Index('idx_tnm_image_disease', 'disease_site_id', 'is_active'),
    )
    
    def __repr__(self):
        return f'<TNMImage {self.id}: {self.title or "Untitled"} for disease {self.disease_site_id}>'
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'disease_site_id': self.disease_site_id,
            'diagnosis_year_id': self.diagnosis_year_id,
            'title': self.title,
            'description': self.description,
            'alt_text': self.alt_text,
            'url': self.cloudinary_url,
            'cloudinary_public_id': self.cloudinary_public_id,
            'width': self.width,
            'height': self.height,
            'image_type': self.image_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'uploaded_by_user_id': self.uploaded_by_user_id
        }
    
    def get_html(self, size='medium'):
        """Generate HTML for embedding in content."""
        sizes = {
            'small': 'max-width: 200px;',
            'medium': 'max-width: 400px;',
            'large': 'max-width: 600px;',
            'full': 'max-width: 100%;'
        }
        style = sizes.get(size, sizes['medium'])
        alt = self.alt_text or self.title or 'TNM Figure'
        
        return f'<img src="{self.cloudinary_url}" alt="{alt}" style="{style} height: auto; border-radius: 8px;">'
    
    @classmethod
    def get_for_disease(cls, disease_site_id: int, active_only: bool = True):
        """Get all images for a disease site."""
        query = cls.query.filter_by(disease_site_id=disease_site_id)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(cls.created_at.desc()).all()
    
    @classmethod
    def delete_from_cloudinary(cls, image_id: int) -> bool:
        """Delete image from Cloudinary and database."""
        import cloudinary
        import cloudinary.uploader
        
        image = cls.query.get(image_id)
        if not image:
            return False
        
        try:
            # Delete from Cloudinary
            if image.cloudinary_public_id:
                cloudinary.uploader.destroy(image.cloudinary_public_id)
            
            # Delete from database
            db.session.delete(image)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting TNM image {image_id}: {e}")
            return False


# ==================== CLINICAL PROTOCOL (On-Call Helper Knowledge Base) ====================

class ProtocolCategory(enum.Enum):
    """Categories for clinical protocols"""
    CONTRAST = "contrast"
    SCORING = "scoring"
    STAGING = "staging"
    CRITERIA = "criteria"
    EMERGENCY = "emergency"
    ANATOMY = "anatomy"
    DOSE = "dose"
    SAFETY = "safety"


class ClinicalProtocol(db.Model):
    """
    Curated clinical protocol knowledge base for on-call helper.
    Each protocol is a verified, citable reference entry.
    Claude formats these for the user — it does NOT source them.
    """
    __tablename__ = 'clinical_protocol'

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    keywords = db.Column(db.Text, nullable=False)  # comma-separated, for pg_trgm search
    content_structured = db.Column(db.Text, nullable=True)  # JSONB-style structured data
    content_html = db.Column(db.Text, nullable=True)  # rich formatted reference content
    source_citation = db.Column(db.Text, nullable=False)
    guideline_version = db.Column(db.String(100), nullable=True)
    source_url = db.Column(db.String(1000), nullable=True)
    body_section = db.Column(db.String(100), nullable=True)
    is_published = db.Column(db.Boolean, default=False, nullable=False, index=True)
    verified_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    verified_by = db.relationship('User', foreign_keys=[verified_by_user_id], backref='verified_protocols', lazy=True)
    created_by = db.relationship('User', foreign_keys=[created_by_user_id], backref='created_protocols', lazy=True)

    def get_content_structured(self):
        if self.content_structured:
            try:
                return json.loads(self.content_structured)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    def set_content_structured(self, data):
        self.content_structured = json.dumps(data) if data else None

    def to_dict(self):
        return {
            'id': self.id,
            'category': self.category,
            'title': self.title,
            'keywords': self.keywords,
            'content_structured': self.get_content_structured(),
            'content_html': self.content_html,
            'source_citation': self.source_citation,
            'guideline_version': self.guideline_version,
            'source_url': self.source_url,
            'body_section': self.body_section,
            'is_published': self.is_published,
            'verified_by_user_id': self.verified_by_user_id,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<ClinicalProtocol {self.id}: {self.title}>'


class OnCallQueryLog(db.Model):
    """
    Audit trail for on-call helper queries — medicolegal requirement.
    Every query and AI response is logged with user, timestamp, and matched protocols.
    """
    __tablename__ = 'oncall_query_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    query_text = db.Column(db.Text, nullable=False)
    matched_protocol_ids = db.Column(db.Text, nullable=True)  # JSON array of protocol IDs
    ai_response_text = db.Column(db.Text, nullable=True)
    model_used = db.Column(db.String(100), nullable=True)
    token_count = db.Column(db.Integer, nullable=True)
    response_source = db.Column(db.String(50), default='protocol')  # 'protocol', 'no_match', 'cached'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship('User', backref='oncall_queries', lazy=True)

    def get_matched_protocol_ids(self):
        if self.matched_protocol_ids:
            try:
                return json.loads(self.matched_protocol_ids)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_matched_protocol_ids(self, ids):
        self.matched_protocol_ids = json.dumps(ids) if ids else None

    def __repr__(self):
        return f'<OnCallQueryLog {self.id}: user={self.user_id} at {self.created_at}>'


# ==================== RADIOLOGY TEMPLATE (plain-text PACS reports) ====================

class RadiologyTemplate(db.Model):
    """
    Plain-text PACS report templates for copy-to-clipboard workflow.
    Origin: 'admin' (admin-curated) or 'personal' (user-created via Smart Reporter).
    """
    __tablename__ = 'radiology_template'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    origin = db.Column(db.String(30), nullable=False, default='admin', index=True)
    category = db.Column(db.String(100), nullable=True, index=True)
    body_section = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    keywords = db.Column(db.Text, nullable=True)
    template_text = db.Column(db.Text, nullable=True)
    source_citation = db.Column(db.Text, nullable=True)
    guideline_version = db.Column(db.String(100), nullable=True)
    is_available = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_ai_generated = db.Column(db.Boolean, default=False, nullable=False)
    verified_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    generation_prompt = db.Column(db.Text, nullable=True)
    generation_model = db.Column(db.String(100), nullable=True)
    generated_at = db.Column(db.DateTime, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    last_edit_note = db.Column(db.Text, nullable=True)
    legacy_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    verified_by = db.relationship('User', foreign_keys=[verified_by_user_id], backref='verified_radiology_templates', lazy=True)
    created_by = db.relationship('User', foreign_keys=[created_by_user_id], backref='created_radiology_templates', lazy=True)

    def to_dict(self):
        return {
            'id': self.id, 'slug': self.slug, 'title': self.title,
            'origin': self.origin, 'category': self.category,
            'body_section': self.body_section, 'description': self.description,
            'keywords': self.keywords, 'template_text': self.template_text,
            'source_citation': self.source_citation, 'guideline_version': self.guideline_version,
            'is_available': self.is_available, 'is_ai_generated': self.is_ai_generated,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'generation_model': self.generation_model,
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<RadiologyTemplate {self.slug}: {self.title}>'


# ==================== REPORTING ALGORITHM (interactive decision trees) ====================

class ReportingAlgorithm(db.Model):
    """
    Interactive decision tree algorithms for structured radiological reporting.
    Origin: 'admin' (curated by admin), 'user' (generated by user via Smart Reporter), 'anatomy_cache'.
    """
    __tablename__ = 'reporting_algorithm'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    origin = db.Column(db.String(30), nullable=False, default='admin', index=True)
    category = db.Column(db.String(100), nullable=False, index=True)
    body_section = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    keywords = db.Column(db.Text, nullable=True)
    template_html = db.Column(db.Text, nullable=True)
    algorithm_html = db.Column(db.Text, nullable=True)
    source_citation = db.Column(db.Text, nullable=True)
    guideline_version = db.Column(db.String(100), nullable=True)
    is_available = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_ai_generated = db.Column(db.Boolean, default=False, nullable=False)
    verified_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    generation_prompt = db.Column(db.Text, nullable=True)
    generation_model = db.Column(db.String(100), nullable=True)
    generated_at = db.Column(db.DateTime, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    modality = db.Column(db.String(200), nullable=True)
    last_edit_note = db.Column(db.Text, nullable=True)
    legacy_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    verified_by = db.relationship('User', foreign_keys=[verified_by_user_id], backref='verified_reporting_algorithms', lazy=True)
    created_by = db.relationship('User', foreign_keys=[created_by_user_id], backref='created_reporting_algorithms', lazy=True)

    def to_dict(self, include_html=False):
        d = {
            'id': self.id, 'slug': self.slug, 'title': self.title,
            'origin': self.origin, 'category': self.category,
            'body_section': self.body_section, 'modality': self.modality,
            'description': self.description,
            'keywords': self.keywords, 'source_citation': self.source_citation,
            'guideline_version': self.guideline_version,
            'is_available': self.is_available, 'is_ai_generated': self.is_ai_generated,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'generation_model': self.generation_model,
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_html:
            d['template_html'] = self.template_html
            d['algorithm_html'] = self.algorithm_html
        return d

    def __repr__(self):
        return f'<ReportingAlgorithm {self.slug}: {self.title}>'


# ==================== SMART REPORTER SESSION ====================
# DEPRECATED: Scheduled for removal. No active code references these models.
# Kept only to avoid dropping database tables unexpectedly.

class ReportingSession(db.Model):
    """
    DEPRECATED — No longer used by Smart Reporter (redesign Feb 2026).
    Tracks a radiologist's Smart Reporter session from algorithm walkthrough to final report.
    Each session stores the full algorithm tree JSON, user answers, and assembled report.
    """
    __tablename__ = 'reporting_session'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # What was queried
    clinical_question = db.Column(db.String(500), nullable=False)
    modality = db.Column(db.String(100), nullable=True)
    body_section = db.Column(db.String(100), nullable=True)

    # AI-generated algorithm tree (full JSON from Claude)
    algorithm_tree_json = db.Column(db.Text, nullable=True)

    # User's walkthrough answers: [{step_id, selected_options: [...], report_text}]
    walkthrough_answers_json = db.Column(db.Text, nullable=True)

    # Final assembled report (plain text, HL7-aligned sections)
    report_text = db.Column(db.Text, nullable=True)

    # Session status: generating, walkthrough, editing, completed
    status = db.Column(db.String(30), nullable=False, default='generating', index=True)

    # AI audit trail
    provider = db.Column(db.String(50), nullable=True)
    model_name = db.Column(db.String(100), nullable=True)
    generation_tokens = db.Column(db.Integer, nullable=True)
    ask_claude_count = db.Column(db.Integer, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='reporting_sessions', lazy=True)

    __table_args__ = (
        db.Index('idx_reporting_session_user_status', 'user_id', 'status'),
    )

    def get_algorithm_tree(self):
        if self.algorithm_tree_json:
            try:
                return json.loads(self.algorithm_tree_json)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    def get_walkthrough_answers(self):
        if self.walkthrough_answers_json:
            try:
                return json.loads(self.walkthrough_answers_json)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def to_summary_dict(self):
        return {
            'id': self.id,
            'clinical_question': self.clinical_question,
            'modality': self.modality,
            'body_section': self.body_section,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }

    def __repr__(self):
        return f'<ReportingSession {self.id} user={self.user_id} status={self.status}>'


# ==================== PUBLISHED REPORT (COMMUNITY LIBRARY) ====================

class PublishedReport(db.Model):
    """
    DEPRECATED — No longer used by Smart Reporter (redesign Feb 2026).
    Snapshot of a reporting session submitted for community publication.
    Independent of the original session — deleting the session does not remove the publication.
    """
    __tablename__ = 'published_report'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, nullable=True)  # Reference only, no FK constraint
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Report content (snapshot at publish time)
    clinical_question = db.Column(db.String(500), nullable=False)
    modality = db.Column(db.String(100), nullable=True)
    body_section = db.Column(db.String(100), nullable=True)
    report_text = db.Column(db.Text, nullable=False)
    algorithm_tree_json = db.Column(db.Text, nullable=True)

    # Attribution
    contributor_name = db.Column(db.String(120), nullable=False)

    # Timestamps
    published_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = db.relationship('User', backref='published_reports', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'clinical_question': self.clinical_question,
            'modality': self.modality,
            'body_section': self.body_section,
            'report_text': self.report_text,
            'contributor_name': self.contributor_name,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'has_algorithm': bool(self.algorithm_tree_json),
        }

    def to_summary_dict(self):
        return {
            'id': self.id,
            'clinical_question': self.clinical_question,
            'modality': self.modality,
            'body_section': self.body_section,
            'contributor_name': self.contributor_name,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'has_algorithm': bool(self.algorithm_tree_json),
        }

    def __repr__(self):
        return f'<PublishedReport {self.id} by={self.contributor_name}>'


# ==================== CONTENT REQUEST ====================

class ContentRequest(db.Model):
    """User-submitted requests for new templates, algorithms, or resources."""
    __tablename__ = 'content_request'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    request_type = db.Column(db.String(50), nullable=False)  # template, algorithm, resource
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    body_section = db.Column(db.String(100))
    status = db.Column(db.String(30), default='pending')  # pending, completed, declined
    admin_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('content_requests', lazy='dynamic'))

    def __repr__(self):
        return f'<ContentRequest {self.id} type={self.request_type} status={self.status}>'


# ==================== RADIOLOGY PEARLS ====================

class RadiologyPearl(db.Model):
    """Clinical teaching pearls captured from Smart Reporter AI insights."""
    __tablename__ = 'radiology_pearl'

    id = db.Column(db.Integer, primary_key=True)
    content_hash = db.Column(db.String(64), unique=True, nullable=False)  # SHA-256 dedup
    pearl_text = db.Column(db.Text, nullable=False)
    body_section = db.Column(db.String(100))
    modality = db.Column(db.String(100))
    tags = db.Column(db.Text)  # comma-separated keywords
    source_report_context = db.Column(db.Text)  # original report snippet for context
    is_verified = db.Column(db.Boolean, default=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    verified_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    verified_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = db.relationship('User', foreign_keys=[created_by_user_id])
    verified_by = db.relationship('User', foreign_keys=[verified_by_user_id])

    def __repr__(self):
        return f'<RadiologyPearl {self.id} verified={self.is_verified}>'


# ==================== LEARNING QUESTIONS (SBA / VIVA) ====================

class LearningQuestion(db.Model):
    """SBA and Viva questions silently captured from Smart Reporter report actions."""
    __tablename__ = 'learning_question'

    id = db.Column(db.Integer, primary_key=True)
    question_type = db.Column(db.String(20), nullable=False, index=True)  # 'sba' or 'viva'
    body_section = db.Column(db.String(100), index=True)
    modality = db.Column(db.String(100))
    module = db.Column(db.String(100), index=True)  # FRCR module (auto-inferred from body_section)
    title = db.Column(db.String(300))
    html_content = db.Column(db.Text, nullable=False)
    source_report_context = db.Column(db.Text)  # first 200 chars of source report
    content_hash = db.Column(db.String(64), unique=True, nullable=False)  # SHA-256 dedup
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    created_by = db.relationship('User', foreign_keys=[created_by_user_id])

    def __repr__(self):
        return f'<LearningQuestion {self.id} type={self.question_type} section={self.body_section}>'


class LearningQuestionProgress(db.Model):
    """Tracks user self-assessment on SBA and Viva questions."""
    __tablename__ = 'learning_question_progress'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    learning_question_id = db.Column(db.Integer, db.ForeignKey('learning_question.id'), nullable=False, index=True)
    score = db.Column(db.Integer, default=0)        # SBA: 0-3 correct; Viva: 1-3 confidence
    best_score = db.Column(db.Integer, default=0)
    times_attempted = db.Column(db.Integer, default=0)
    last_attempted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'learning_question_id', name='uq_user_learning_question'),
    )

    user = db.relationship('User', foreign_keys=[user_id])
    learning_question = db.relationship('LearningQuestion', foreign_keys=[learning_question_id])

    def __repr__(self):
        return f'<LearningQuestionProgress user={self.user_id} q={self.learning_question_id} score={self.score}>'


class LearningQuestionReference(db.Model):
    """URL references attached to learning questions (journal articles, guidelines, etc.)."""
    __tablename__ = 'learning_question_reference'

    id = db.Column(db.Integer, primary_key=True)
    learning_question_id = db.Column(db.Integer, db.ForeignKey('learning_question.id'), nullable=False, index=True)
    ref_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.Text, nullable=False)
    url = db.Column(db.Text, nullable=False)
    journal = db.Column(db.String(500))
    year = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    question = db.relationship('LearningQuestion', backref=db.backref('references', cascade='all, delete-orphan'))

    __table_args__ = (
        db.UniqueConstraint('learning_question_id', 'ref_number', name='uq_lq_ref_number'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'learning_question_id': self.learning_question_id,
            'ref_number': self.ref_number,
            'title': self.title,
            'url': self.url,
            'journal': self.journal,
            'year': self.year,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ==================== CONTENT INTELLIGENCE ====================

class ContentIntelligence(db.Model):
    """AI-processed metadata for admin content (summaries, tags, cross-links)."""
    __tablename__ = 'content_intelligence'

    id = db.Column(db.Integer, primary_key=True)
    content_type = db.Column(db.String(50), nullable=False, index=True)  # case, protocol, reporting_algorithm, radiology_template, radiology_tool, radiology_pearl, anatomy_snippet
    content_id = db.Column(db.Integer, nullable=False, index=True)
    summary = db.Column(db.Text, nullable=False)  # 2-line AI summary for search results
    search_tags = db.Column(db.Text)  # comma-separated keywords
    cross_links_json = db.Column(db.Text)  # JSON: [{type, id, title, relevance}]
    processing_model = db.Column(db.String(100))
    processing_tokens = db.Column(db.Integer)
    processed_at = db.Column(db.DateTime)
    is_verified = db.Column(db.Boolean, default=False)
    verified_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    verified_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('content_type', 'content_id', name='uq_content_intelligence'),
    )

    verified_by = db.relationship('User', foreign_keys=[verified_by_user_id])

    def get_cross_links(self):
        if not self.cross_links_json:
            return []
        try:
            return json.loads(self.cross_links_json)
        except (json.JSONDecodeError, TypeError):
            return []

    def to_dict(self):
        return {
            'id': self.id,
            'content_type': self.content_type,
            'content_id': self.content_id,
            'summary': self.summary,
            'search_tags': self.search_tags,
            'cross_links': self.get_cross_links(),
            'processing_model': self.processing_model,
            'processing_tokens': self.processing_tokens,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<ContentIntelligence {self.content_type}:{self.content_id} verified={self.is_verified}>'


class UserGeneratedIntelligence(db.Model):
    """Structured clinical knowledge silently captured from Smart Reporter insights."""
    __tablename__ = 'user_generated_intelligence'

    id = db.Column(db.Integer, primary_key=True)
    content_hash = db.Column(db.String(64), unique=True, nullable=False)  # SHA-256 dedup

    # Source metadata (from Smart Reporter session)
    modality = db.Column(db.String(100))
    exam_type = db.Column(db.String(200))  # e.g. "CT Abdomen Pelvis"
    body_section = db.Column(db.String(100))
    clinical_question = db.Column(db.Text)

    # Raw inputs (saved verbatim from AI assist)
    raw_teaching_point = db.Column(db.Text, nullable=False)
    raw_differentials = db.Column(db.Text)  # JSON array

    # Haiku-processed structured fields
    diagnosis = db.Column(db.String(300))
    notes = db.Column(db.Text)  # JSON array of practical knowledge bullets
    pitfalls = db.Column(db.Text)  # JSON array of pitfall bullets
    enriched_differentials = db.Column(db.Text)  # JSON: [{name, distinguishing_features}]
    search_tags = db.Column(db.Text)  # comma-separated

    # Processing
    processing_model = db.Column(db.String(100))
    processing_tokens = db.Column(db.Integer)
    processed_at = db.Column(db.DateTime)  # null if pending
    processing_status = db.Column(db.String(20), default='pending')  # pending/processed/failed/discarded

    # Verification
    is_verified = db.Column(db.Boolean, default=False)
    verified_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    verified_at = db.Column(db.DateTime)

    # Provenance
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = db.relationship('User', foreign_keys=[created_by_user_id])
    verified_by = db.relationship('User', foreign_keys=[verified_by_user_id])

    def get_notes(self):
        if not self.notes:
            return []
        try:
            return json.loads(self.notes)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_pitfalls(self):
        if not self.pitfalls:
            return []
        try:
            return json.loads(self.pitfalls)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_enriched_differentials(self):
        if not self.enriched_differentials:
            return []
        try:
            return json.loads(self.enriched_differentials)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_raw_differentials(self):
        if not self.raw_differentials:
            return []
        try:
            return json.loads(self.raw_differentials)
        except (json.JSONDecodeError, TypeError):
            return []

    def to_dict(self):
        return {
            'id': self.id,
            'diagnosis': self.diagnosis,
            'modality': self.modality,
            'exam_type': self.exam_type,
            'body_section': self.body_section,
            'clinical_question': self.clinical_question,
            'raw_teaching_point': self.raw_teaching_point,
            'raw_differentials': self.get_raw_differentials(),
            'notes': self.get_notes(),
            'pitfalls': self.get_pitfalls(),
            'enriched_differentials': self.get_enriched_differentials(),
            'search_tags': self.search_tags,
            'processing_status': self.processing_status,
            'processing_model': self.processing_model,
            'is_verified': self.is_verified,
            'created_by_user_id': self.created_by_user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<UserGeneratedIntelligence {self.id} status={self.processing_status} verified={self.is_verified}>'


# ==================== AI AUDIT LOG ====================

class AIAuditLog(db.Model):
    """Audit trail for all AI generation requests (compliance + cost tracking)."""
    __tablename__ = 'ai_audit_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False)  # e.g. 'generate_tree', 'review_report', 'ask_claude'
    provider = db.Column(db.String(50), nullable=True)   # e.g. 'anthropic'
    model = db.Column(db.String(100), nullable=True)      # e.g. 'claude-sonnet-4-20250514'
    input_tokens = db.Column(db.Integer, nullable=True)
    output_tokens = db.Column(db.Integer, nullable=True)
    input_summary = db.Column(db.String(500), nullable=True)  # Truncated input for context
    status = db.Column(db.String(20), default='success')       # 'success', 'error', 'rate_limited'
    error_message = db.Column(db.Text, nullable=True)
    duration_ms = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref='ai_audit_logs', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'provider': self.provider,
            'model': self.model,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'input_summary': self.input_summary,
            'status': self.status,
            'error_message': self.error_message,
            'duration_ms': self.duration_ms,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


def log_ai_usage(user_id, action, provider=None, model=None,
                 input_tokens=None, output_tokens=None,
                 input_summary=None, status='success', error_message=None, duration_ms=None):
    """Log an AI generation request. Wrapped in try/except — audit logging never breaks main flow."""
    try:
        log = AIAuditLog(
            user_id=user_id, action=action, provider=provider, model=model,
            input_tokens=input_tokens, output_tokens=output_tokens,
            input_summary=input_summary[:500] if input_summary else None,
            status=status, error_message=error_message, duration_ms=duration_ms,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()


# ==================== INCIDENTAL FINDING CALCULATOR ====================

class IncidentalFindingCalculator(db.Model):
    """
    Interactive calculators for incidental findings management.
    Deterministic decision trees based on published guidelines (Fleischner, ACR, etc.).
    Mirrors TNMCalculatorContent pattern.
    """
    __tablename__ = 'incidental_finding_calculator'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    finding_name = db.Column(db.String(300), nullable=False)
    body_section = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(100), nullable=True)  # pulmonary, adrenal, renal, liver, thyroid, etc.
    description = db.Column(db.String(500), nullable=True)
    keywords = db.Column(db.Text, nullable=True)  # for pg_trgm search
    calculator_html = db.Column(db.Text, nullable=True)  # interactive decision tree HTML
    algorithm_html = db.Column(db.Text, nullable=True)  # extracted algorithm/reference
    guideline_source = db.Column(db.Text, nullable=True)  # JSON with references, linked_cases, etc.
    guideline_version = db.Column(db.String(100), nullable=True)
    guideline_url = db.Column(db.String(1000), nullable=True)
    is_available = db.Column(db.Boolean, default=False, nullable=False, index=True)
    generation_prompt = db.Column(db.Text, nullable=True)
    generation_model = db.Column(db.String(100), nullable=True)
    generated_at = db.Column(db.DateTime, nullable=True)
    verified_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    last_edit_note = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    verified_by = db.relationship('User', foreign_keys=[verified_by_user_id], backref='verified_if_calculators', lazy=True)
    created_by = db.relationship('User', foreign_keys=[created_by_user_id], backref='created_if_calculators', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'slug': self.slug,
            'finding_name': self.finding_name,
            'body_section': self.body_section,
            'category': self.category,
            'description': self.description,
            'keywords': self.keywords,
            'guideline_source': self.guideline_source,
            'guideline_version': self.guideline_version,
            'guideline_url': self.guideline_url,
            'is_available': self.is_available,
            'generation_model': self.generation_model,
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<IncidentalFindingCalculator {self.slug}: {self.finding_name}>'


# ==================== SNIPPET REFERENCE / DOCUMENT / IMAGE ====================

class SnippetReference(db.Model):
    """URL references attached to anatomy snippets (journal articles, guidelines, etc.)."""
    __tablename__ = 'snippet_reference'

    id = db.Column(db.Integer, primary_key=True)
    algorithm_id = db.Column(db.Integer, db.ForeignKey('reporting_algorithm.id'), nullable=False, index=True)
    ref_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.Text, nullable=False)
    url = db.Column(db.Text, nullable=False)
    journal = db.Column(db.String(500))
    year = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    algorithm = db.relationship('ReportingAlgorithm', backref=db.backref('references', cascade='all, delete-orphan'))

    __table_args__ = (
        db.UniqueConstraint('algorithm_id', 'ref_number', name='uq_snippet_ref_number'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'algorithm_id': self.algorithm_id,
            'ref_number': self.ref_number,
            'title': self.title,
            'url': self.url,
            'journal': self.journal,
            'year': self.year,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SnippetDocument(db.Model):
    """PDF/document uploads attached to anatomy snippets via Cloudinary."""
    __tablename__ = 'snippet_document'

    id = db.Column(db.Integer, primary_key=True)
    algorithm_id = db.Column(db.Integer, db.ForeignKey('reporting_algorithm.id'), nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    cloudinary_url = db.Column(db.String(500), nullable=False)
    cloudinary_public_id = db.Column(db.String(255))
    file_type = db.Column(db.String(50), default='pdf')
    file_size_kb = db.Column(db.Integer)
    uploaded_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    algorithm = db.relationship('ReportingAlgorithm', backref=db.backref('documents', cascade='all, delete-orphan'))
    uploaded_by = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'algorithm_id': self.algorithm_id,
            'title': self.title,
            'cloudinary_url': self.cloudinary_url,
            'file_type': self.file_type,
            'file_size_kb': self.file_size_kb,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SnippetImage(db.Model):
    """Images with attribution attached to anatomy snippets (Radiopaedia, CC, manual)."""
    __tablename__ = 'snippet_image'

    id = db.Column(db.Integer, primary_key=True)
    algorithm_id = db.Column(db.Integer, db.ForeignKey('reporting_algorithm.id'), nullable=False, index=True)
    source_url = db.Column(db.String(1000), nullable=False)
    source_domain = db.Column(db.String(255), nullable=False)
    thumbnail_url = db.Column(db.String(500))
    image_type = db.Column(db.String(50), default='ct_mri')
    modality = db.Column(db.String(50))
    description = db.Column(db.Text)
    display_order = db.Column(db.Integer, default=0)
    license = db.Column(db.String(100), nullable=False, default='CC BY-NC-SA 3.0')
    attribution = db.Column(db.String(500), nullable=False)
    added_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    algorithm = db.relationship('ReportingAlgorithm', backref=db.backref('snippet_images', cascade='all, delete-orphan'))
    added_by = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'algorithm_id': self.algorithm_id,
            'source_url': self.source_url,
            'source_domain': self.source_domain,
            'thumbnail_url': self.thumbnail_url,
            'image_type': self.image_type,
            'modality': self.modality,
            'description': self.description,
            'display_order': self.display_order,
            'license': self.license,
            'attribution': self.attribution,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ==================== RADIQ QUERY MODEL ====================

class RadIQQuery(db.Model):
    """Saved RadIQ queries — consultant-level AI advisory for radiologists."""
    __tablename__ = 'radiq_query'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False)  # gp_reply, complaint, incident, radiographer, imaging_protocol, general
    question = db.Column(db.Text, nullable=False)
    response_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('radiq_queries', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'category': self.category,
            'question': self.question,
            'response_text': self.response_text,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<RadIQQuery {self.id} cat={self.category} user={self.user_id}>'


class PiiOverrideLog(db.Model):
    """Audit trail for PII guard actions — overrides, dismissals, batch dismissals."""
    __tablename__ = 'pii_override_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    action = db.Column(db.String(20), nullable=False, default='override')  # override | dismiss | batch_dismiss
    flagged_types = db.Column(db.Text, nullable=False)  # comma-separated PII types
    flagged_count = db.Column(db.Integer, nullable=False, default=0)
    target_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('pii_overrides', lazy='dynamic'))

    def __repr__(self):
        return f'<PiiOverrideLog {self.id} user={self.user_id} types={self.flagged_types}>'


# ==================== RATE LIMIT ENTRY ====================
class RateLimitEntry(db.Model):
    """DB-backed rate limiting — persists across serverless cold starts."""
    __tablename__ = 'rate_limit_entry'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), nullable=False)       # IP address or user identifier
    endpoint = db.Column(db.String(255), nullable=False)   # e.g. 'auth.register'
    hit_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.Index('ix_rate_limit_key_endpoint_hit', 'key', 'endpoint', 'hit_at'),
    )

    def __repr__(self):
        return f'<RateLimitEntry {self.key} {self.endpoint} {self.hit_at}>'


# ==================== ERASURE LOG ====================
class ErasureLog(db.Model):
    """GDPR erasure audit trail — records what was deleted and when."""
    __tablename__ = 'erasure_log'

    id = db.Column(db.Integer, primary_key=True)
    erasure_type = db.Column(db.String(50), nullable=False)  # 'user_request', 'auto_purge', 'admin_action'
    initiated_by_user_id = db.Column(db.Integer, nullable=True)  # NULL for auto-purge
    target_user_email_hash = db.Column(db.String(64), nullable=False)  # SHA-256 for auditability without PII
    records_deleted = db.Column(db.Text, nullable=True)  # JSON summary of deleted record counts
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<ErasureLog {self.id} type={self.erasure_type}>'


# ==================== ADMIN ACTION LOG ====================
class AdminActionLog(db.Model):
    """Persistent audit trail for admin actions."""
    __tablename__ = 'admin_action_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False)     # e.g. 'role_change', 'delete_user', 'verify_algorithm'
    target_type = db.Column(db.String(50), nullable=True)   # e.g. 'user', 'case', 'reporting_algorithm'
    target_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)             # JSON with action-specific metadata
    ip_address = db.Column(db.String(45), nullable=True)    # IPv4 or IPv6
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship('User', backref=db.backref('admin_actions', lazy='dynamic'))

    def __repr__(self):
        return f'<AdminActionLog {self.id} action={self.action}>'


def log_admin_action(user_id, action, target_type=None, target_id=None, details=None, ip_address=None):
    """Log an admin action. Never raises — failures are logged and swallowed."""
    try:
        details_json = json.dumps(details) if details and not isinstance(details, str) else details
        entry = AdminActionLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details_json,
            ip_address=ip_address
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        _models_logger.error(f"Failed to log admin action: {e}")
