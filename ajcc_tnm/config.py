"""
AJCC TNM Module Configuration

Provides configurable settings for database, Cloudinary, and app integration.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List


@dataclass
class CloudinaryConfig:
    """Cloudinary configuration for image storage."""
    cloud_name: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    folder: str = "frcr_revision/AJCC_figures"
    
    @classmethod
    def from_env(cls):
        """Create config from environment variables."""
        return cls(
            cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
            api_key=os.getenv('CLOUDINARY_API_KEY'),
            api_secret=os.getenv('CLOUDINARY_API_SECRET'),
            folder=os.getenv('AJCC_CLOUDINARY_FOLDER', 'frcr_revision/AJCC_figures')
        )
    
    @property
    def is_configured(self) -> bool:
        """Check if Cloudinary is properly configured."""
        return all([self.cloud_name, self.api_key, self.api_secret])


@dataclass
class AJCCAuthConfig:
    """AJCC website authentication configuration."""
    username: Optional[str] = None
    password: Optional[str] = None
    cookies_file: str = ".ajcc_cookies.json"
    
    @classmethod
    def from_env(cls):
        """Create config from environment variables."""
        return cls(
            username=os.getenv('AJCC_USERNAME'),
            password=os.getenv('AJCC_PASSWORD'),
            cookies_file=os.getenv('AJCC_COOKIES_FILE', '.ajcc_cookies.json')
        )
    
    @property
    def is_configured(self) -> bool:
        """Check if AJCC auth is properly configured."""
        return bool(self.username and self.password)


@dataclass
class AJCCConfig:
    """
    Main configuration class for AJCC TNM module.
    
    Attributes:
        cloudinary: Cloudinary configuration for image storage
        auth: AJCC website authentication configuration
        default_year: Default diagnosis year to use
        supported_years: List of supported diagnosis years
        enable_html_legacy: Whether to store legacy HTML alongside JSON
        enable_image_download: Whether to download and store images to Cloudinary
        
        # Callbacks for host app integration
        get_db: Callback to get SQLAlchemy db instance
        get_user_model: Callback to get User model class
        get_frcr_module_enum: Callback to get FRCRModule enum (for mapping)
        get_body_part_enum: Callback to get BodyPart enum (for mapping)
        get_age_group_enum: Callback to get AgeGroup enum (for mapping)
        get_current_user_id: Callback to get current user ID
        require_admin: Decorator for admin-only routes
    """
    
    # Sub-configurations
    cloudinary: CloudinaryConfig = field(default_factory=CloudinaryConfig.from_env)
    auth: AJCCAuthConfig = field(default_factory=AJCCAuthConfig.from_env)
    
    # Data settings
    default_year: int = 2026
    supported_years: List[int] = field(default_factory=lambda: [2024, 2025, 2026])
    enable_html_legacy: bool = True
    enable_image_download: bool = True
    
    # Debug settings
    debug_mode: bool = field(default_factory=lambda: os.getenv('AJCC_DEBUG', '').lower() == 'true')
    
    # Callbacks for host app integration (set during init_app)
    get_db: Optional[Callable] = None
    get_user_model: Optional[Callable] = None
    get_frcr_module_enum: Optional[Callable] = None
    get_body_part_enum: Optional[Callable] = None
    get_age_group_enum: Optional[Callable] = None
    get_current_user_id: Optional[Callable] = None
    require_admin: Optional[Callable] = None
    
    def configure_for_flask_app(self, app):
        """
        Auto-configure callbacks for a standard Flask app structure.
        
        Args:
            app: Flask application instance
        """
        # Try to import from host app's models
        try:
            from models import db, User, FRCRModule, BodyPart, AgeGroup
            self.get_db = lambda: db
            self.get_user_model = lambda: User
            self.get_frcr_module_enum = lambda: FRCRModule
            self.get_body_part_enum = lambda: BodyPart
            self.get_age_group_enum = lambda: AgeGroup
        except ImportError:
            pass
        
        # Try to import access control
        try:
            from access_control import require_admin
            self.require_admin = require_admin
        except ImportError:
            pass
        
        # Try to get current user
        try:
            from flask_login import current_user
            self.get_current_user_id = lambda: current_user.id if current_user.is_authenticated else None
        except ImportError:
            pass
    
    @classmethod
    def from_env(cls):
        """Create a fully configured instance from environment variables."""
        return cls(
            cloudinary=CloudinaryConfig.from_env(),
            auth=AJCCAuthConfig.from_env(),
            default_year=int(os.getenv('AJCC_DEFAULT_YEAR', '2026')),
            enable_html_legacy=os.getenv('AJCC_ENABLE_HTML_LEGACY', 'true').lower() == 'true',
            enable_image_download=os.getenv('AJCC_ENABLE_IMAGE_DOWNLOAD', 'true').lower() == 'true',
            debug_mode=os.getenv('AJCC_DEBUG', '').lower() == 'true'
        )


# Staging time prefixes reference data
STAGING_TIME_PREFIXES = [
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


# Section information mapping
SECTION_INFO = {
    1: {'name': 'Staging Quick Reference', 'slug': 'quick-reference'},
    2: {'name': 'Cancers Staged Using This System', 'slug': 'cancers-staged'},
    3: {'name': 'Cancers NOT Staged by This System', 'slug': 'cancers-not-staged'},
    4: {'name': 'Summary of Changes', 'slug': 'summary-changes'},
    5: {'name': 'Identification of Primary Site', 'slug': 'primary-site'},
    6: {'name': 'Histopathologic Type', 'slug': 'histopathologic-type'},
    7: {'name': 'Clinical Staging and Workup', 'slug': 'clinical-staging-workup'},
    8: {'name': 'Staging Rules', 'slug': 'staging-rules'},
    9: {'name': 'Common Staging Scenarios', 'slug': 'common-scenarios'},
    10: {'name': 'Explanatory Notes', 'slug': 'explanatory-notes'}
}
