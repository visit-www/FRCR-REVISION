"""
AJCCDiseaseMapping Model

Maps AJCC disease sites to app FRCRModule and BodyPart
"""

from datetime import datetime
from models import db, FRCRModule, BodyPart


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
