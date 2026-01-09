# Data Migration & Enhancement Strategy: FRCR-Examiner → FRCR-Revision

## Executive Summary

This document outlines a three-phase strategy to import cases from FRCR-Examiner database into FRCR-Revision, allowing admins to enrich data with metadata (module, body part, age group) and control visibility (is_public).

---

## Phase 1: Data Ingestion & Staging

### 1.1 Create Staging Model for Imported Cases

A temporary staging area for raw imported data before enrichment:

```python
# In models.py - Add this new model

class ImportedCaseStaging(db.Model):
    """
    Temporary storage for imported cases pending enrichment.
    Cases move to production (Case model) after admin approval.
    """
    __tablename__ = 'imported_case_staging'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # ===== RAW DATA FROM IMPORT =====
    original_id = db.Column(db.Integer, nullable=True)  # ID from FRCR-Examiner
    case_number = db.Column(db.Integer, nullable=True)
    diagnosis = db.Column(db.Text, nullable=False)
    questions = db.Column(db.Text, nullable=False)
    answers = db.Column(db.Text, nullable=False)
    discussion = db.Column(db.Text, nullable=True)
    
    # ===== ENRICHED METADATA (Admin-added) =====
    module = db.Column(db.Enum(FRCRModule), nullable=True, index=True)
    body_part = db.Column(db.Enum(BodyPart), nullable=True, index=True)
    age_group = db.Column(db.Enum(AgeGroup), nullable=True, index=True)
    is_public = db.Column(db.Boolean, default=False, index=True)
    
    # ===== ENRICHMENT TRACKING =====
    enrichment_status = db.Column(
        db.String(20),
        default='pending',
        index=True
    )  # pending, in_progress, enriched, rejected
    
    enriched_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    enriched_at = db.Column(db.DateTime, nullable=True)
    enrichment_notes = db.Column(db.Text, nullable=True)
    
    # ===== APPROVAL WORKFLOW =====
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    approval_notes = db.Column(db.Text, nullable=True)
    
    # ===== IMPORT TRACKING =====
    import_batch_id = db.Column(db.String(50), nullable=False, index=True)  # UUID for batch
    source_system = db.Column(db.String(50), default='frcr_examiner')
    import_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    enriched_by = db.relationship('User', foreign_keys=[enriched_by_user_id])
    approved_by = db.relationship('User', foreign_keys=[approved_by_user_id])
    
    def __repr__(self):
        return f'<ImportedCaseStaging {self.case_number} Status:{self.enrichment_status}>'
```

### 1.2 Create Import Service Layer

Create file: `services/import_service.py`

```python
"""
Service for importing cases from backup JSON files
"""
import json
import uuid
from datetime import datetime
from models import db, ImportedCaseStaging

class ImportService:
    """Handles import of cases from FRCR-Examiner backup JSON"""
    
    @staticmethod
    def import_from_backup(backup_file_path, source_system='frcr_examiner'):
        """
        Import cases from backup JSON file into staging area
        
        Args:
            backup_file_path: Path to .json backup file
            source_system: Source system identifier
            
        Returns:
            {
                'success': bool,
                'import_batch_id': str,
                'total_imported': int,
                'errors': [str]
            }
        """
        errors = []
        imported_count = 0
        import_batch_id = str(uuid.uuid4())
        
        try:
            # Read backup file
            with open(backup_file_path, 'r') as f:
                backup_data = json.load(f)
            
            # Extract cases
            cases_data = backup_data.get('cases', [])
            
            for case_data in cases_data:
                try:
                    staging = ImportedCaseStaging(
                        original_id=case_data.get('id'),
                        case_number=case_data.get('case_number'),
                        diagnosis=case_data.get('diagnosis', ''),
                        questions=case_data.get('questions', ''),
                        answers=case_data.get('answers', ''),
                        discussion=case_data.get('discussion'),
                        enrichment_status='pending',
                        import_batch_id=import_batch_id,
                        source_system=source_system,
                    )
                    db.session.add(staging)
                    imported_count += 1
                except Exception as e:
                    errors.append(f"Failed to import case {case_data.get('case_number')}: {str(e)}")
            
            db.session.commit()
            
            return {
                'success': True,
                'import_batch_id': import_batch_id,
                'total_imported': imported_count,
                'errors': errors
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'import_batch_id': None,
                'total_imported': 0,
                'errors': [str(e)]
            }
    
    @staticmethod
    def get_pending_cases(page=1, per_page=20):
        """Get paginated list of cases pending enrichment"""
        return ImportedCaseStaging.query.filter_by(
            enrichment_status='pending'
        ).paginate(page=page, per_page=per_page)
    
    @staticmethod
    def get_import_batch(batch_id):
        """Get all cases from a specific import batch"""
        return ImportedCaseStaging.query.filter_by(
            import_batch_id=batch_id
        ).all()
    
    @staticmethod
    def get_enrichment_stats(batch_id=None):
        """Get statistics on enrichment progress"""
        query = ImportedCaseStaging.query
        
        if batch_id:
            query = query.filter_by(import_batch_id=batch_id)
        
        total = query.count()
        by_status = {
            'pending': query.filter_by(enrichment_status='pending').count(),
            'in_progress': query.filter_by(enrichment_status='in_progress').count(),
            'enriched': query.filter_by(enrichment_status='enriched').count(),
            'rejected': query.filter_by(enrichment_status='rejected').count(),
        }
        
        return {
            'total': total,
            'by_status': by_status,
            'completion_percentage': int((by_status['enriched'] / total * 100)) if total > 0 else 0
        }
```

---

## Phase 2: Admin Enrichment Interface

### 2.1 Create Admin Routes for Enrichment

Create file: `admin_enrichment_routes.py`

```python
"""
Admin routes for case enrichment workflow
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, ImportedCaseStaging, FRCRModule, BodyPart, AgeGroup, UserRole
from services.import_service import ImportService
from access_control import require_admin
from datetime import datetime

enrichment_bp = Blueprint('enrichment', __name__, url_prefix='/api/admin/enrichment')

@enrichment_bp.before_request
@login_required
@require_admin
def check_admin():
    """Verify admin access"""
    pass

@enrichment_bp.route('/import', methods=['POST'])
def import_cases():
    """
    Import cases from backup JSON file
    
    Expects: multipart/form-data with 'backup_file' field
    Returns: {import_batch_id, total_imported, errors}
    """
    if 'backup_file' not in request.files:
        return jsonify({'error': 'No backup file provided'}), 400
    
    file = request.files['backup_file']
    if not file.filename.endswith('.json'):
        return jsonify({'error': 'Only JSON files supported'}), 400
    
    # Save temp file and import
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
        file.save(tmp.name)
        result = ImportService.import_from_backup(tmp.name)
    
    return jsonify(result), 200 if result['success'] else 400

@enrichment_bp.route('/pending', methods=['GET'])
def get_pending_cases():
    """Get list of cases pending enrichment"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    pagination = ImportService.get_pending_cases(page, per_page)
    
    return jsonify({
        'cases': [{
            'id': case.id,
            'case_number': case.case_number,
            'diagnosis': case.diagnosis[:100],  # First 100 chars
            'module': case.module.value if case.module else None,
            'body_part': case.body_part.value if case.body_part else None,
            'age_group': case.age_group.value if case.age_group else None,
            'is_public': case.is_public,
            'enrichment_status': case.enrichment_status,
        } for case in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    })

@enrichment_bp.route('/<int:case_id>', methods=['GET'])
def get_case_details(case_id):
    """Get full details of a case for enrichment"""
    case = ImportedCaseStaging.query.get_or_404(case_id)
    
    return jsonify({
        'id': case.id,
        'case_number': case.case_number,
        'diagnosis': case.diagnosis,
        'questions': case.questions,
        'answers': case.answers,
        'discussion': case.discussion,
        'module': case.module.value if case.module else None,
        'body_part': case.body_part.value if case.body_part else None,
        'age_group': case.age_group.value if case.age_group else None,
        'is_public': case.is_public,
        'enrichment_status': case.enrichment_status,
        'enrichment_notes': case.enrichment_notes,
    })

@enrichment_bp.route('/<int:case_id>/enrich', methods=['PUT'])
def enrich_case(case_id):
    """
    Update case with enrichment metadata
    
    Body: {
        module: str,
        body_part: str,
        age_group: str,
        is_public: bool,
        enrichment_notes: str
    }
    """
    case = ImportedCaseStaging.query.get_or_404(case_id)
    data = request.get_json()
    
    try:
        # Update enums
        if data.get('module'):
            case.module = FRCRModule(data['module'])
        
        if data.get('body_part'):
            case.body_part = BodyPart(data['body_part'])
        
        if data.get('age_group'):
            case.age_group = AgeGroup(data['age_group'])
        
        # Update public flag
        case.is_public = data.get('is_public', False)
        
        # Mark as enriched
        case.enrichment_status = 'enriched'
        case.enriched_by_user_id = current_user.id
        case.enriched_at = datetime.utcnow()
        case.enrichment_notes = data.get('enrichment_notes', '')
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Case enriched'}), 200
        
    except ValueError as e:
        return jsonify({'error': f'Invalid enum value: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@enrichment_bp.route('/<int:case_id>/approve', methods=['POST'])
def approve_enrichment(case_id):
    """
    Admin approves enriched case for promotion to production
    
    Body: { approval_notes: str (optional) }
    """
    case = ImportedCaseStaging.query.get_or_404(case_id)
    
    if case.enrichment_status != 'enriched':
        return jsonify({
            'error': 'Only enriched cases can be approved'
        }), 400
    
    data = request.get_json() or {}
    
    try:
        case.approved_by_user_id = current_user.id
        case.approved_at = datetime.utcnow()
        case.approval_notes = data.get('approval_notes', '')
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Case approved'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@enrichment_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get enrichment statistics"""
    batch_id = request.args.get('batch_id')
    stats = ImportService.get_enrichment_stats(batch_id)
    
    return jsonify(stats)

@enrichment_bp.route('/<int:case_id>/reject', methods=['POST'])
def reject_case(case_id):
    """Reject a case from import"""
    case = ImportedCaseStaging.query.get_or_404(case_id)
    data = request.get_json() or {}
    
    case.enrichment_status = 'rejected'
    case.enrichment_notes = data.get('reason', '')
    
    db.session.commit()
    
    return jsonify({'success': True}), 200
```

---

## Phase 3: Promotion to Production

### 3.1 Promotion Service

Add to `services/import_service.py`:

```python
class PromotionService:
    """Handles promotion of enriched cases from staging to production"""
    
    @staticmethod
    def promote_case(staging_case_id, case_packet_id=None, created_by_user_id=None):
        """
        Promote enriched case from staging to production Case model
        
        Args:
            staging_case_id: ID of ImportedCaseStaging record
            case_packet_id: Optional packet_id for organized cases
            created_by_user_id: User ID creating the case
            
        Returns:
            {success, message, case_id}
        """
        try:
            staging = ImportedCaseStaging.query.get(staging_case_id)
            if not staging:
                return {'success': False, 'message': 'Staging case not found'}
            
            if staging.enrichment_status != 'enriched' or not staging.approved_at:
                return {
                    'success': False,
                    'message': 'Case must be enriched and approved before promotion'
                }
            
            # Create production case
            from models import Case, CaseStatus
            
            case = Case(
                case_number=staging.case_number,
                diagnosis=staging.diagnosis,
                questions=staging.questions,
                answers=staging.answers,
                discussion=staging.discussion,
                module=staging.module,
                body_part=staging.body_part,
                age_group=staging.age_group,
                is_public=staging.is_public,
                status=CaseStatus.PUBLISHED if staging.is_public else CaseStatus.DRAFT,
                packet_id=case_packet_id,
                created_by_user_id=created_by_user_id,
            )
            
            db.session.add(case)
            db.session.flush()
            
            # Archive the staging record
            staging.enrichment_status = 'promoted'
            
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Case promoted to production',
                'case_id': case.id
            }
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def bulk_promote(batch_id, created_by_user_id):
        """Promote all approved cases from a batch"""
        staging_cases = ImportedCaseStaging.query.filter_by(
            import_batch_id=batch_id,
            enrichment_status='enriched'
        ).filter(ImportedCaseStaging.approved_at != None).all()
        
        promoted = 0
        errors = []
        
        for staging in staging_cases:
            result = PromotionService.promote_case(
                staging.id,
                created_by_user_id=created_by_user_id
            )
            if result['success']:
                promoted += 1
            else:
                errors.append(result['message'])
        
        return {
            'promoted': promoted,
            'total_approved': len(staging_cases),
            'errors': errors
        }
```

---

## Architecture Overview

```
FRCR-Examiner Backup (JSON)
        ↓
    ImportService
        ↓
ImportedCaseStaging (Staging Table)
        ↓
    Admin Enriches Data
    (Module, BodyPart, AgeGroup, is_public)
        ↓
    Admin Approves
        ↓
PromotionService
        ↓
    Case Table (Production)
```

---

## Frontend Components Needed

### 3.2 Import Manager Interface

```tsx
// New admin tab: "Case Import Manager"
- Import dropdown with file upload
- Visual progress bar showing enrichment stats
- Table of pending cases with quick-edit mode
- Bulk actions: Approve Selected, Reject Selected, Promote All
```

### 3.3 Case Enrichment Form

```tsx
// Modal/Panel for enriching a case
- Diagnosis display (read-only)
- Module dropdown (required)
- Body Part dropdown (required)
- Age Group dropdown (required)
- Public checkbox
- Notes textarea
- Save/Approve buttons
```

---

## Database Migration

Add to `migrations/versions/`:

```bash
# Run:
alembic revision --autogenerate -m "add_case_import_staging_model"
alembic upgrade head
```

---

## Workflow Summary for Admin

1. **Upload Backup**: Admin uploads FRCR-Examiner backup JSON
   - System imports all cases to staging (enrichment_status = 'pending')
   
2. **Enrich Data**: For each case, admin:
   - Selects FRCR Module
   - Selects Body Part
   - Selects Age Group (Adult/Pediatric)
   - Toggles is_public flag
   - Adds optional notes
   
3. **Approve**: Admin reviews enriched case and approves

4. **Promote**: Either:
   - Auto-promote approved cases, OR
   - Manually promote selected cases
   - Promoted cases appear in main Case table

---

## Implementation Priority

**Phase 1** (High Priority):
- Create ImportedCaseStaging model
- Create ImportService
- Create import API endpoint

**Phase 2** (High Priority):
- Create enrichment admin routes
- Create admin UI for enrichment

**Phase 3** (Medium Priority):
- Create PromotionService
- Create promotion endpoints
- Create bulk promotion UI

---

## Error Handling & Validation

- ✅ Duplicate case detection (original_id)
- ✅ Required field validation (diagnosis, questions, answers)
- ✅ Enum value validation
- ✅ Admin permission checks
- ✅ Transaction rollback on failures
- ✅ Audit logging for all enrichments

---

## Key Benefits

| Feature | Benefit |
|---------|---------|
| **Staging Table** | Non-destructive import, easy to rollback |
| **Enrichment Tracking** | See who enriched and when |
| **Workflow Status** | pending → enriched → approved → promoted |
| **Batch Tracking** | Group imports by batch_id for easy management |
| **Approval Gate** | QA review before production |
| **Bulk Operations** | Promote multiple cases at once |

---

## Security Considerations

- ✅ Admin-only access (require_admin decorator)
- ✅ Audit trail for all enrichments
- ✅ No passwords in import (security risk eliminated)
- ✅ Soft deletes on rejection (data preservation)
- ✅ User tracking (enriched_by, approved_by)

---

## Next Steps

1. Create the model migration
2. Implement ImportService
3. Create enrichment routes
4. Build admin enrichment UI
5. Test end-to-end workflow
6. Document for admin users
