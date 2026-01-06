from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class ExamSession(db.Model):
    """Store exam session details"""
    id = db.Column(db.Integer, primary_key=True)
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
    packet_id = db.Column(db.Integer, db.ForeignKey('packet.id'), nullable=False)
    case_number = db.Column(db.Integer, nullable=False)  # 1-3 per packet
    diagnosis = db.Column(db.Text, nullable=False)
    questions = db.Column(db.Text, nullable=False)  # Can contain multiple questions
    answers = db.Column(db.Text, nullable=False)  # Can contain multiple answers
    discussion = db.Column(db.Text)  # Optional discussion/comments
    
    images = db.relationship('CaseImage', backref='case', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Case {self.case_number} - {self.diagnosis}>'


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
