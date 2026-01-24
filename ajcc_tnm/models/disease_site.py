"""
AJCCDiseaseSite Model

AJCC disease sites within body sections (e.g., Lung, Breast, etc.)
"""

from datetime import datetime
from models import db


class AJCCDiseaseSite(db.Model):
    """AJCC disease sites within body sections (e.g., Lung, Breast, etc.)"""
    id = db.Column(db.Integer, primary_key=True)
    body_section_id = db.Column(db.Integer, db.ForeignKey('ajcc_body_section.id'), nullable=False, index=True)
    disease_name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), nullable=False, index=True)
    ajcc_url_path = db.Column(db.String(300), nullable=False)  # e.g., "thorax/lung"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # FRCR App Integration - maps AJCC sites to app's module/body_part/age_group
    frcr_module = db.Column(db.String(50), nullable=True)  # e.g., "FRCR_2A", "FRCR_2B"
    frcr_body_part = db.Column(db.String(50), nullable=True)  # e.g., "CHEST", "HEAD_NECK"
    frcr_age_group = db.Column(db.String(50), nullable=True)  # e.g., "ADULT", "PAEDIATRIC"
    
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
