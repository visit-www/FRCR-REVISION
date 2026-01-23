# Installation Guide

## Prerequisites

- Python 3.8+
- Flask application with Flask-SQLAlchemy
- Required packages (in requirements.txt):
  - `flask`
  - `flask-sqlalchemy`
  - `flask-login`
  - `beautifulsoup4`
  - `requests`
  - `playwright` (optional, for browser automation)

## Installation Steps

### 1. Copy Module to Your Project

```bash
# Copy the ajcc_tnm directory to your project
cp -r ajcc_tnm /path/to/your/project/
```

### 2. Add Models to Your models.py

Copy the AJCC models from this module to your main `models.py`:

```python
# At the end of your models.py, add:

# ==================== AJCC TNM STAGING MODELS ====================

class AJCCBodySection(db.Model):
    # ... (copy from ajcc_tnm/models/body_section.py)

class AJCCDiseaseSite(db.Model):
    # ... (copy from ajcc_tnm/models/disease_site.py)

class AJCCDiagnosisYear(db.Model):
    # ... (copy from ajcc_tnm/models/diagnosis_year.py)

class AJCCStagingData(db.Model):
    # ... (copy from ajcc_tnm/models/staging_data.py)

class AJCCDiseaseMapping(db.Model):
    # ... (copy from ajcc_tnm/models/disease_mapping.py)

class AJCCStagingTimePrefix(db.Model):
    # ... (copy from ajcc_tnm/models/staging_time_prefix.py)
```

### 3. Run Database Migrations

```bash
# Create migration
flask db migrate -m "Add AJCC TNM models"

# Apply migration
flask db upgrade
```

### 4. Initialize in Your App

```python
# In app.py
from ajcc_tnm import init_app as init_ajcc_tnm, get_blueprints

# After creating your Flask app
app = Flask(__name__)
# ... your app configuration ...

# Initialize AJCC TNM module
init_ajcc_tnm(app)

# Register blueprints
admin_tnm_bp, tnm_bp = get_blueprints()
app.register_blueprint(admin_tnm_bp)
app.register_blueprint(tnm_bp)
```

### 5. Set Environment Variables

```bash
# .env file
AJCC_USERNAME=your_ajcc_username
AJCC_PASSWORD=your_ajcc_password
AJCC_DEFAULT_YEAR=2026

# Optional: For image storage
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

### 6. Seed Initial Data

```bash
# In Flask shell
flask shell

>>> from models import AJCCStagingTimePrefix, db
>>> AJCCStagingTimePrefix.seed_defaults()
>>> print("Staging time prefixes seeded!")
```

### 7. Initialize Body Sections and Diseases

Run the initialization script:

```bash
python -m ajcc_tnm.scripts.initialize_mappings
```

Or manually:

```python
from models import db, AJCCBodySection, AJCCDiseaseSite

# Add body sections
thorax = AJCCBodySection(section_name="Thorax", slug="thorax", display_order=1)
db.session.add(thorax)

# Add diseases
lung = AJCCDiseaseSite(
    body_section_id=thorax.id,
    disease_name="Lung",
    slug="lung",
    ajcc_url_path="thorax/lung"
)
db.session.add(lung)
db.session.commit()
```

## Verification

### Check Routes

```bash
flask routes | grep tnm
```

Expected output:
```
tnm.browse                      GET     /tnm
tnm.disease_main_page           GET     /tnm/<section_slug>/<disease_slug>
admin_tnm.extract_tnm           POST    /api/admin/tnm/extract
...
```

### Test Import

```python
python -c "from ajcc_tnm import get_blueprints; print('Success!')"
```

### Access UI

- Browse: `http://localhost:5000/tnm`
- Admin: `http://localhost:5000/api/admin/tnm/management`

## Troubleshooting

### Import Errors

If you get import errors, ensure:
1. `ajcc_tnm` directory is in your Python path
2. All `__init__.py` files exist
3. Main `models.py` has AJCC models

### Template Not Found

Ensure templates are registered:

```python
# Check if templates folder is in search path
print(app.jinja_loader.searchpath)
# Should include: .../ajcc_tnm/templates
```

### Database Errors

Run migrations:

```bash
flask db upgrade
```

Check tables exist:

```sql
SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'ajcc%';
```
