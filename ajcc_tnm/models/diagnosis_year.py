"""
AJCCDiagnosisYear Model

AJCC diagnosis years (2024, 2025, 2026)
"""

from datetime import datetime
from models import db


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
