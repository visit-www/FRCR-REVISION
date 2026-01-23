"""
AJCC TNM Models

Database models for AJCC TNM staging data storage.

These models are designed to be used with Flask-SQLAlchemy and require
the main app's db instance and enums (FRCRModule, BodyPart) to be available.
"""

# Note: Models are still defined in main models.py for now to avoid
# breaking the existing migration history and table relationships.
# This module re-exports them for convenience.

try:
    from models import (
        AJCCBodySection,
        AJCCDiseaseSite,
        AJCCDiagnosisYear,
        AJCCStagingData,
        AJCCDiseaseMapping
    )
    
    # Also export the new staging time prefix model
    # This will be added to main models.py or created separately
    try:
        from models import AJCCStagingTimePrefix
    except ImportError:
        # Not yet added to main models
        from .staging_time_prefix import AJCCStagingTimePrefix
    
    __all__ = [
        'AJCCBodySection',
        'AJCCDiseaseSite',
        'AJCCDiagnosisYear',
        'AJCCStagingData',
        'AJCCDiseaseMapping',
        'AJCCStagingTimePrefix'
    ]
except ImportError:
    # Models not yet available - they'll be moved later
    __all__ = []
    
    # Try to import from local files as fallback
    try:
        from .body_section import AJCCBodySection
        from .disease_site import AJCCDiseaseSite
        from .diagnosis_year import AJCCDiagnosisYear
        from .staging_data import AJCCStagingData
        from .disease_mapping import AJCCDiseaseMapping
        from .staging_time_prefix import AJCCStagingTimePrefix
        
        __all__ = [
            'AJCCBodySection',
            'AJCCDiseaseSite',
            'AJCCDiagnosisYear',
            'AJCCStagingData',
            'AJCCDiseaseMapping',
            'AJCCStagingTimePrefix'
        ]
    except ImportError:
        pass
