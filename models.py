from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import enum

db = SQLAlchemy()

# FRCR Module Enum
class FRCRModule(enum.Enum):
    """FRCR examination modules"""
    CARDIOTHORACIC_VASCULAR = "Cardiothoracic and Vascular"
    MUSCULOSKELETAL_TRAUMA = "Musculoskeletal and Trauma"
    GASTROINTESTINAL = "Gastro-intestinal (liver, biliary, pancreas, spleen)"
    GENITOURINARY_BREAST = "Genito-urinary, Adrenal, Obstetrics & Gynaecology, and Breast"
    PAEDIATRIC = "Paediatric"
    CNS_HEAD_NECK = "Central Nervous System and Head & Neck"

# Body Part Enum
class BodyPart(enum.Enum):
    """Body parts for case categorization"""
    # CNS and Head & Neck
    BRAIN = "Brain"
    SPINE = "Spine"
    HEAD_NECK = "Head & Neck"
    
    # Cardiothoracic and Vascular
    THORAX = "Thorax"
    CARDIOVASCULAR = "Cardiovascular"
    CHEST_WALL = "Chest wall"
    
    # Musculoskeletal
    UPPER_LIMB = "Upper limb"
    LOWER_LIMB = "Lower limb"
    
    # Gastrointestinal
    ABDOMEN_BOWEL = "Abdomen and bowel"
    LIVER = "Liver"
    GALLBLADDER = "Gallbladder"
    BILIARY_TREE = "Biliary tree"
    PANCREAS = "Pancreas"
    SPLEEN = "Spleen"
    
    # Genitourinary and Breast
    URINARY_SYSTEM = "Urinary system"
    REPRODUCTIVE_SYSTEM = "Reproductive system"
    BREAST = "Breast"
    
    # Paediatric (system-wide)
    PAEDIATRIC_GENERAL = "Paediatric - General"
    PAEDIATRIC_SKELETON = "Paediatric - Growing skeleton"
    PAEDIATRIC_CHEST = "Paediatric - Neonatal chest"
    PAEDIATRIC_CONGENITAL = "Paediatric - Congenital anomalies"

class User(UserMixin, db.Model):
    """Store user account information"""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.Text, nullable=False)  # Use Text instead of String for better compatibility
    full_name = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)  # Admin flag for first user
    
    # Password recovery
    recovery_token = db.Column(db.String(255), unique=True, nullable=True)
    recovery_token_expires = db.Column(db.DateTime, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    exam_sessions = db.relationship('ExamSession', backref='creator', lazy=True, cascade='all, delete-orphan')
    candidate_notes = db.relationship('CandidateNote', backref='author', lazy=True, cascade='all, delete-orphan')
    highlights = db.relationship('TextHighlight', backref='author', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password against hash"""
        return check_password_hash(self.password_hash, password)
    
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


class ExamSession(db.Model):
    """Store exam session details"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exam_date = db.Column(db.Date, nullable=False)
    exam_time = db.Column(db.String(10), nullable=False)
    session_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    packets = db.relationship('Packet', backref='exam', lazy=True, cascade='all, delete-orphan')
    candidates = db.relationship('Candidate', backref='exam', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ExamSession {self.session_name}>'


class Packet(db.Model):
    """Store packet information"""
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam_session.id'), nullable=False)
    packet_number = db.Column(db.Integer, nullable=False)  # 1-4
    packet_id = db.Column(db.String(50), nullable=False)  # e.g., FORM001, FORM002
    
    cases = db.relationship('Case', backref='packet', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Packet {self.packet_id}>'


class Case(db.Model):
    """Store case information"""
    id = db.Column(db.Integer, primary_key=True)
    packet_id = db.Column(db.Integer, db.ForeignKey('packet.id'), nullable=True)  # Nullable for standalone cases
    case_number = db.Column(db.Integer, nullable=True)  # Legacy field - nullable for non-packet cases
    diagnosis = db.Column(db.Text, nullable=False)
    questions = db.Column(db.Text, nullable=False)  # Legacy - for backward compatibility
    answers = db.Column(db.Text, nullable=False)  # Legacy - for backward compatibility
    discussion = db.Column(db.Text)  # Optional discussion/comments
    
    # New fields for FRCR Revision
    module = db.Column(db.Enum(FRCRModule), nullable=True, index=True)  # FRCR module categorization
    body_part = db.Column(db.Enum(BodyPart), nullable=True, index=True)  # Body part categorization
    is_public = db.Column(db.Boolean, default=False, index=True)  # Admin approval for visibility to students
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Track who created the case
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    images = db.relationship('CaseImage', backref='case', lazy=True, cascade='all, delete-orphan')
    question_items = db.relationship('Question', backref='case', lazy=True, cascade='all, delete-orphan')
    answer_items = db.relationship('Answer', backref='case', lazy=True, cascade='all, delete-orphan')
    candidate_notes = db.relationship('CandidateNote', backref='case', lazy=True, cascade='all, delete-orphan')
    highlights = db.relationship('TextHighlight', backref='case', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Case {self.case_number} - {self.diagnosis}>'


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


class Candidate(db.Model):
    """Store candidate information"""
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam_session.id'), nullable=False)
    candidate_name = db.Column(db.String(120), nullable=False)
    candidate_number = db.Column(db.Integer, nullable=False)  # 1-4
    packet_number = db.Column(db.Integer, nullable=False)  # Maps to packet 1-4
    
    def __repr__(self):
        return f'<Candidate {self.candidate_name} ({self.candidate_number})>'


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
