"""
AJCCStagingTimePrefix Model

Standard reference table for staging time prefixes (c, p, yc, yp, r, a).
"""

from datetime import datetime
from models import db


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
    def seed_defaults(cls, db_session):
        """
        Seed the default staging time prefixes.
        
        Args:
            db_session: SQLAlchemy database session
        """
        defaults = [
            {
                'prefix': 'c',
                'name': 'Clinical',
                'description': 'Clinical staging based on physical examination, imaging, endoscopy, biopsy, and surgical exploration',
                'display_order': 1
            },
            {
                'prefix': 'p',
                'name': 'Pathological',
                'description': 'Pathological staging based on surgical resection specimen',
                'display_order': 2
            },
            {
                'prefix': 'yc',
                'name': 'Post-therapy Clinical',
                'description': 'Clinical staging performed after neoadjuvant therapy',
                'display_order': 3
            },
            {
                'prefix': 'yp',
                'name': 'Post-therapy Pathological',
                'description': 'Pathological staging performed after neoadjuvant therapy',
                'display_order': 4
            },
            {
                'prefix': 'r',
                'name': 'Recurrence',
                'description': 'Staging at time of recurrence',
                'display_order': 5
            },
            {
                'prefix': 'a',
                'name': 'Autopsy',
                'description': 'Staging determined at autopsy',
                'display_order': 6
            }
        ]
        
        for prefix_data in defaults:
            existing = cls.query.filter_by(prefix=prefix_data['prefix']).first()
            if not existing:
                prefix = cls(**prefix_data)
                db_session.add(prefix)
        
        db_session.commit()
