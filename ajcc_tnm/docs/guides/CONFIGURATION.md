# Configuration Guide

## Overview

The AJCC TNM module uses a configuration system that can be customized via:
1. Environment variables
2. Python configuration objects
3. Callbacks for host app integration

## Configuration Class

```python
from ajcc_tnm.config import AJCCConfig, CloudinaryConfig, AJCCAuthConfig

config = AJCCConfig(
    cloudinary=CloudinaryConfig(...),
    auth=AJCCAuthConfig(...),
    default_year=2026,
    enable_html_legacy=True,
    enable_image_download=True,
    debug_mode=False
)
```

## Environment Variables

### Required for Extraction

| Variable | Description | Default |
|----------|-------------|---------|
| `AJCC_USERNAME` | AJCC website username | None |
| `AJCC_PASSWORD` | AJCC website password | None |

### Optional Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `AJCC_DEFAULT_YEAR` | Default diagnosis year | 2026 |
| `AJCC_DEBUG` | Enable debug mode | false |
| `AJCC_ENABLE_HTML_LEGACY` | Store HTML alongside JSON | true |
| `AJCC_ENABLE_IMAGE_DOWNLOAD` | Download images to Cloudinary | true |
| `AJCC_COOKIES_FILE` | Path to cookies file | .ajcc_cookies.json |

### Cloudinary (for Image Storage)

| Variable | Description | Default |
|----------|-------------|---------|
| `CLOUDINARY_CLOUD_NAME` | Cloudinary cloud name | None |
| `CLOUDINARY_API_KEY` | Cloudinary API key | None |
| `CLOUDINARY_API_SECRET` | Cloudinary API secret | None |
| `AJCC_CLOUDINARY_FOLDER` | Folder for AJCC images | ajcc_tnm/images |

## Python Configuration

### Basic Usage

```python
from ajcc_tnm import init_app
from ajcc_tnm.config import AJCCConfig

config = AJCCConfig.from_env()  # Load from environment
init_app(app, config=config)
```

### Custom Configuration

```python
from ajcc_tnm.config import AJCCConfig, CloudinaryConfig, AJCCAuthConfig

config = AJCCConfig(
    cloudinary=CloudinaryConfig(
        cloud_name='my_cloud',
        api_key='xxx',
        api_secret='xxx',
        folder='my_app/ajcc_images'
    ),
    auth=AJCCAuthConfig(
        username='myuser',
        password='mypass'
    ),
    default_year=2026,
    supported_years=[2024, 2025, 2026],
    enable_html_legacy=True,
    enable_image_download=True,
    debug_mode=False
)

init_app(app, config=config)
```

## Host App Integration

### Callbacks

The module uses callbacks to integrate with the host app:

```python
config = AJCCConfig()

# Database access
config.get_db = lambda: db

# User model access
config.get_user_model = lambda: User

# App enums for mapping
config.get_frcr_module_enum = lambda: FRCRModule
config.get_body_part_enum = lambda: BodyPart
config.get_age_group_enum = lambda: AgeGroup

# Current user ID
config.get_current_user_id = lambda: current_user.id if current_user.is_authenticated else None

# Admin decorator
config.require_admin = require_admin
```

### Auto-Configuration

For standard Flask apps, use auto-configuration:

```python
config = AJCCConfig()
config.configure_for_flask_app(app)
init_app(app, config=config)
```

This automatically sets up callbacks based on common conventions.

## Section Configuration

The module defines 10 standard sections:

```python
from ajcc_tnm.config import SECTION_INFO

# SECTION_INFO = {
#     1: {'name': 'Staging Quick Reference', 'slug': 'quick-reference'},
#     2: {'name': 'Cancers Staged Using This System', 'slug': 'cancers-staged'},
#     3: {'name': 'Cancers NOT Staged by This System', 'slug': 'cancers-not-staged'},
#     4: {'name': 'Summary of Changes', 'slug': 'summary-changes'},
#     5: {'name': 'Identification of Primary Site', 'slug': 'primary-site'},
#     6: {'name': 'Histopathologic Type', 'slug': 'histopathologic-type'},
#     7: {'name': 'Clinical Staging and Workup', 'slug': 'clinical-staging-workup'},
#     8: {'name': 'Staging Rules', 'slug': 'staging-rules'},
#     9: {'name': 'Common Staging Scenarios', 'slug': 'common-scenarios'},
#     10: {'name': 'Explanatory Notes', 'slug': 'explanatory-notes'}
# }
```

## Staging Time Prefixes

Standard prefixes are defined in config:

```python
from ajcc_tnm.config import STAGING_TIME_PREFIXES

# [
#     {'prefix': 'c', 'name': 'Clinical', 'description': '...'},
#     {'prefix': 'p', 'name': 'Pathological', 'description': '...'},
#     {'prefix': 'yc', 'name': 'Post-therapy Clinical', 'description': '...'},
#     {'prefix': 'yp', 'name': 'Post-therapy Pathological', 'description': '...'},
#     {'prefix': 'r', 'name': 'Recurrence', 'description': '...'},
#     {'prefix': 'a', 'name': 'Autopsy', 'description': '...'}
# ]
```

## Debug Mode

Enable debug mode for verbose logging:

```bash
export AJCC_DEBUG=true
```

Or in Python:

```python
config = AJCCConfig(debug_mode=True)
```

Debug mode:
- Saves raw API responses to files
- Logs detailed extraction steps
- Shows cookie information
