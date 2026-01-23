"""
AJCCBodySection Model

AJCC body sections (e.g., Thorax, Head and Neck, etc.)
"""

from datetime import datetime
from models import db


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
