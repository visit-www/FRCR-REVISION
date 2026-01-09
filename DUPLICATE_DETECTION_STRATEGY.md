# Import Duplicate Detection & Conflict Resolution Strategy

## Problem Statement

When admin imports a backup, some cases might:
1. **Already exist in staging** (from previous import)
2. **Already be in production** (promoted from previous import)
3. **Be partially enriched** (enrichment in progress)

Admin needs to decide: Skip, Update, or Force Import?

---

## Solution Architecture

### 1. Enhanced ImportedCaseStaging Model

Add to `models.py`:

```python
class ImportedCaseStaging(db.Model):
    """Temporary storage for cases being imported and enriched"""
    __tablename__ = 'imported_case_staging'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Raw data from import
    original_id = db.Column(db.Integer, nullable=True)
    case_number = db.Column(db.Integer, nullable=True)
    diagnosis = db.Column(db.Text, nullable=False)
    questions = db.Column(db.Text, nullable=False)
    answers = db.Column(db.Text, nullable=False)
    discussion = db.Column(db.Text, nullable=True)
    
    # Enriched metadata
    module = db.Column(db.Enum(FRCRModule), nullable=True, index=True)
    body_part = db.Column(db.Enum(BodyPart), nullable=True, index=True)
    age_group = db.Column(db.Enum(AgeGroup), nullable=True, index=True)
    is_public = db.Column(db.Boolean, default=False, index=True)
    
    # Status tracking
    enrichment_status = db.Column(db.String(20), default='pending', index=True)
    enriched_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    enriched_at = db.Column(db.DateTime, nullable=True)
    enrichment_notes = db.Column(db.Text, nullable=True)
    
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    approval_notes = db.Column(db.Text, nullable=True)
    
    # === NEW: Duplicate & Promotion Tracking ===
    promoted_to_case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=True, index=True)
    promoted_at = db.Column(db.DateTime, nullable=True)
    
    # Tracks previous versions if re-imported
    previous_staging_id = db.Column(db.Integer, db.ForeignKey('imported_case_staging.id'), nullable=True)
    is_replacement = db.Column(db.Boolean, default=False)  # TRUE if updating previous import
    
    # Import tracking
    import_batch_id = db.Column(db.String(50), nullable=False, index=True)
    source_system = db.Column(db.String(50), default='frcr_examiner')
    import_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    enriched_by = db.relationship('User', foreign_keys=[enriched_by_user_id])
    approved_by = db.relationship('User', foreign_keys=[approved_by_user_id])
    promoted_to_case = db.relationship('Case', foreign_keys=[promoted_to_case_id])
    previous_staging = db.relationship('ImportedCaseStaging', remote_side=[id], foreign_keys=[previous_staging_id])
    
    # Unique constraint: source_system + original_id per batch
    # But we allow multiple batches to have same original_id
    __table_args__ = (
        db.Index('idx_original_id_batch', 'source_system', 'original_id', 'import_batch_id'),
        db.Index('idx_promoted_case', 'promoted_to_case_id'),
    )
```

### 2. Duplicate Detection Service

Add to `services/import_service.py`:

```python
class DuplicateDetectionService:
    """Detects and handles duplicate cases during import"""
    
    @staticmethod
    def check_duplicates(backup_data, source_system='frcr_examiner'):
        """
        Analyze backup for duplicates against existing data
        
        Returns: {
            'total_cases': int,
            'duplicates': {
                'in_staging': [...],      # Already in ImportedCaseStaging
                'in_production': [...],   # Already promoted to Case
                'new_cases': [...]        # New to system
            },
            'conflicts': [...]  # Cases with conflicts
        }
        """
        duplicates_in_staging = []
        duplicates_in_production = []
        new_cases = []
        conflicts = []
        
        for case_data in backup_data.get('cases', []):
            original_id = case_data.get('id')
            diagnosis = case_data.get('diagnosis', '')
            
            # Check if in staging
            staging_case = ImportedCaseStaging.query.filter_by(
                source_system=source_system,
                original_id=original_id
            ).filter(
                ImportedCaseStaging.is_replacement == False
            ).first()
            
            if staging_case:
                duplicates_in_staging.append({
                    'original_id': original_id,
                    'staging_id': staging_case.id,
                    'diagnosis': diagnosis,
                    'import_batch_id': staging_case.import_batch_id,
                    'enrichment_status': staging_case.enrichment_status,
                    'imported_at': staging_case.import_timestamp.isoformat(),
                })
                continue
            
            # Check if already in production
            production_case = Case.query.join(
                ImportedCaseStaging
            ).filter(
                ImportedCaseStaging.source_system == source_system,
                ImportedCaseStaging.original_id == original_id,
                Case.id == ImportedCaseStaging.promoted_to_case_id
            ).first()
            
            if production_case:
                duplicates_in_production.append({
                    'original_id': original_id,
                    'case_id': production_case.id,
                    'diagnosis': diagnosis,
                    'module': production_case.module.value if production_case.module else None,
                    'promoted_at': (
                        ImportedCaseStaging.query.filter_by(
                            promoted_to_case_id=production_case.id
                        ).first().promoted_at.isoformat() if production_case else None
                    ),
                })
                continue
            
            # New case
            new_cases.append({
                'original_id': original_id,
                'case_number': case_data.get('case_number'),
                'diagnosis': diagnosis[:100],
            })
        
        return {
            'total_cases': len(backup_data.get('cases', [])),
            'new_cases': new_cases,
            'duplicates_in_staging': duplicates_in_staging,
            'duplicates_in_production': duplicates_in_production,
            'new_count': len(new_cases),
            'staging_count': len(duplicates_in_staging),
            'production_count': len(duplicates_in_production),
        }
    
    @staticmethod
    def get_duplicate_conflicts(original_id, source_system='frcr_examiner'):
        """Get all versions of a case (staging + production)"""
        staging = ImportedCaseStaging.query.filter_by(
            source_system=source_system,
            original_id=original_id,
            is_replacement=False
        ).all()
        
        production = Case.query.join(
            ImportedCaseStaging
        ).filter(
            ImportedCaseStaging.source_system == source_system,
            ImportedCaseStaging.original_id == original_id,
            Case.id == ImportedCaseStaging.promoted_to_case_id
        ).all()
        
        return {
            'staging_versions': [{
                'id': s.id,
                'batch_id': s.import_batch_id,
                'enrichment_status': s.enrichment_status,
                'imported_at': s.import_timestamp.isoformat(),
                'enriched_by': s.enriched_by.full_name if s.enriched_by else None,
            } for s in staging],
            'production_version': {
                'id': production[0].id if production else None,
                'module': production[0].module.value if production and production[0].module else None,
                'promoted_at': (
                    ImportedCaseStaging.query.filter_by(
                        promoted_to_case_id=production[0].id
                    ).first().promoted_at.isoformat() if production else None
                )
            } if production else None,
        }
```

### 3. Conflict Resolution Service

Add to `services/import_service.py`:

```python
class ConflictResolutionService:
    """Handles admin decisions on duplicate imports"""
    
    # Resolution strategies
    SKIP = 'skip'                  # Don't import, leave existing
    REPLACE_STAGING = 'replace'    # Update staging version, re-enrich
    UPDATE_PRODUCTION = 'update'   # Update already-promoted case
    CREATE_NEW = 'create_new'      # Create as separate case (different case_number)
    FORCE_IMPORT = 'force_import'  # Import again despite duplicates
    
    @staticmethod
    def resolve_duplicate(original_id, new_case_data, resolution_strategy, user_id):
        """
        Handle duplicate based on admin's choice
        
        Args:
            original_id: ID from source system
            new_case_data: New case data from backup
            resolution_strategy: skip|replace|update|create_new|force_import
            user_id: Admin user ID making the decision
        
        Returns: {success, message, staging_id, action}
        """
        
        if resolution_strategy == ConflictResolutionService.SKIP:
            return {
                'success': True,
                'message': 'Case skipped',
                'action': 'skip',
            }
        
        elif resolution_strategy == ConflictResolutionService.REPLACE_STAGING:
            # Find existing staging case and mark as replaced
            existing = ImportedCaseStaging.query.filter_by(
                original_id=original_id,
                is_replacement=False
            ).order_by(ImportedCaseStaging.import_timestamp.desc()).first()
            
            if not existing:
                return {'success': False, 'message': 'No staging case found to replace'}
            
            # Create new version
            new_staging = ImportedCaseStaging(
                original_id=new_case_data['id'],
                case_number=new_case_data.get('case_number'),
                diagnosis=new_case_data.get('diagnosis', ''),
                questions=new_case_data.get('questions', ''),
                answers=new_case_data.get('answers', ''),
                discussion=new_case_data.get('discussion'),
                import_batch_id=existing.import_batch_id,  # Same batch
                previous_staging_id=existing.id,
                is_replacement=True,
                enrichment_status='pending',  # Reset to pending
                source_system='frcr_examiner',
            )
            
            db.session.add(new_staging)
            db.session.commit()
            
            return {
                'success': True,
                'message': f'Case replaced. Previous version (ID:{existing.id}) marked as superseded',
                'action': 'replaced',
                'staging_id': new_staging.id,
                'previous_staging_id': existing.id,
            }
        
        elif resolution_strategy == ConflictResolutionService.UPDATE_PRODUCTION:
            # Find production case and update it
            staging_with_production = ImportedCaseStaging.query.filter_by(
                original_id=original_id
            ).filter(ImportedCaseStaging.promoted_to_case_id != None).first()
            
            if not staging_with_production:
                return {'success': False, 'message': 'No production case found'}
            
            production_case = Case.query.get(staging_with_production.promoted_to_case_id)
            
            # Update production case with new data
            production_case.diagnosis = new_case_data.get('diagnosis', '')
            production_case.questions = new_case_data.get('questions', '')
            production_case.answers = new_case_data.get('answers', '')
            production_case.discussion = new_case_data.get('discussion')
            production_case.updated_at = datetime.utcnow()
            
            # Create audit log
            CaseAuditLog.query.create(
                case_id=production_case.id,
                user_id=user_id,
                action='updated_from_import',
                changes={
                    'diagnosis': {'old': production_case.diagnosis, 'new': new_case_data.get('diagnosis')},
                },
                notes=f'Case data updated from reimport of original_id {original_id}'
            )
            
            db.session.commit()
            
            return {
                'success': True,
                'message': f'Production case {production_case.id} updated',
                'action': 'updated',
                'case_id': production_case.id,
            }
        
        elif resolution_strategy == ConflictResolutionService.CREATE_NEW:
            # Create as completely new case (new case_number)
            new_staging = ImportedCaseStaging(
                original_id=new_case_data['id'],
                case_number=new_case_data.get('case_number'),
                diagnosis=new_case_data.get('diagnosis', ''),
                questions=new_case_data.get('questions', ''),
                answers=new_case_data.get('answers', ''),
                discussion=new_case_data.get('discussion'),
                enrichment_status='pending',
                source_system='frcr_examiner',
                import_batch_id=str(uuid.uuid4()),  # New batch
            )
            
            db.session.add(new_staging)
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Case imported as new duplicate (treated as separate case)',
                'action': 'created_new',
                'staging_id': new_staging.id,
            }
        
        elif resolution_strategy == ConflictResolutionService.FORCE_IMPORT:
            # Import regardless, create new staging record
            new_staging = ImportedCaseStaging(
                original_id=new_case_data['id'],
                case_number=new_case_data.get('case_number'),
                diagnosis=new_case_data.get('diagnosis', ''),
                questions=new_case_data.get('questions', ''),
                answers=new_case_data.get('answers', ''),
                discussion=new_case_data.get('discussion'),
                enrichment_status='pending',
                source_system='frcr_examiner',
                import_batch_id=str(uuid.uuid4()),
            )
            
            db.session.add(new_staging)
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Case force imported (duplicate of existing case)',
                'action': 'force_imported',
                'staging_id': new_staging.id,
            }
        
        return {
            'success': False,
            'message': 'Unknown resolution strategy',
        }
```

---

## 4. Enhanced Import API Endpoints

Add to `admin_enrichment_routes.py`:

```python
@enrichment_bp.route('/check-duplicates', methods=['POST'])
def check_duplicates():
    """
    Scan backup file for duplicates before importing
    Returns report of conflicts
    
    Body: multipart/form-data with 'backup_file'
    """
    if 'backup_file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['backup_file']
    if not file.filename.endswith('.json'):
        return jsonify({'error': 'Only JSON files'}), 400
    
    try:
        backup_data = json.loads(file.read().decode('utf-8'))
        
        from services.import_service import DuplicateDetectionService
        result = DuplicateDetectionService.check_duplicates(backup_data)
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@enrichment_bp.route('/conflicts/<int:original_id>', methods=['GET'])
def get_duplicate_conflicts(original_id):
    """Get all versions of a case (staging + production)"""
    from services.import_service import DuplicateDetectionService
    
    result = DuplicateDetectionService.get_duplicate_conflicts(original_id)
    return jsonify(result), 200

@enrichment_bp.route('/resolve-duplicate', methods=['POST'])
def resolve_duplicate():
    """
    Admin decides how to handle a duplicate
    
    Body: {
        original_id: int,
        new_case_data: {...},
        resolution_strategy: 'skip'|'replace'|'update'|'create_new'|'force_import'
    }
    """
    data = request.get_json()
    
    from services.import_service import ConflictResolutionService
    
    result = ConflictResolutionService.resolve_duplicate(
        original_id=data['original_id'],
        new_case_data=data.get('new_case_data'),
        resolution_strategy=data['resolution_strategy'],
        user_id=current_user.id
    )
    
    return jsonify(result), 200 if result['success'] else 400

@enrichment_bp.route('/import-with-conflicts', methods=['POST'])
def import_with_conflicts():
    """
    Import backup with admin-specified conflict resolution
    
    Body: {
        backup_file: File,
        conflicts: {
            original_id_1: 'skip',
            original_id_2: 'replace',
            ...
        }
    }
    """
    # First check duplicates
    file = request.files['backup_file']
    backup_data = json.loads(file.read().decode('utf-8'))
    
    from services.import_service import DuplicateDetectionService, ConflictResolutionService, ImportService
    
    # Get conflicts
    conflicts_report = DuplicateDetectionService.check_duplicates(backup_data)
    admin_decisions = request.form.get('conflicts', {})
    
    # Process each case based on admin's decision
    import_results = {
        'imported': 0,
        'skipped': 0,
        'updated': 0,
        'errors': []
    }
    
    for case_data in backup_data.get('cases', []):
        original_id = case_data['id']
        decision = admin_decisions.get(str(original_id), 'import')
        
        if decision == 'skip':
            import_results['skipped'] += 1
        elif decision in ['replace', 'update', 'create_new', 'force_import']:
            result = ConflictResolutionService.resolve_duplicate(
                original_id,
                case_data,
                decision,
                current_user.id
            )
            if result['success']:
                import_results['imported'] += 1
            else:
                import_results['errors'].append(result['message'])
        else:
            # Default: import as new
            staging = ImportedCaseStaging(...)
            db.session.add(staging)
            import_results['imported'] += 1
    
    db.session.commit()
    
    return jsonify(import_results), 200
```

---

## 5. Frontend: Duplicate Detection UI

### Workflow

```
User uploads backup.json
       ↓
[Check Duplicates button]
       ↓
API returns:
{
  total_cases: 150,
  new_cases: [{...}, ...],         // 120 new
  duplicates_in_staging: [...],     // 20 already in enrichment
  duplicates_in_production: [...]   // 10 already promoted
}
       ↓
UI shows summary:
┌─────────────────────────────────┐
│ 150 cases in backup             │
│                                 │
│ ✓ 120 NEW - Ready to import    │
│ ⊘ 20 in staging (enriching)    │
│ ✓ 10 already in production     │
│                                 │
│ [RESOLVE CONFLICTS]             │
│ [IMPORT NEW ONLY] [SKIP ALL]   │
└─────────────────────────────────┘
       ↓
Admin clicks case to see options:
┌─────────────────────────────────┐
│ Case #42: Pneumonia             │
│ In staging as of: Jan 9 12:30   │
│ Enrichment status: pending      │
│                                 │
│ What do you want to do?         │
│ ○ Skip (keep current)           │
│ ○ Replace (re-enrich)           │
│ ○ Force Import (create copy)    │
│                                 │
│ [APPLY]                         │
└─────────────────────────────────┘
```

### Vue Component Template

```vue
<template>
  <div class="import-manager">
    <!-- Step 1: Check Duplicates -->
    <div v-if="step === 'check'" class="card">
      <div class="card-header">Check for Duplicates</div>
      <div class="card-body">
        <input type="file" @change="selectFile" accept=".json">
        <button @click="checkDuplicates()" :disabled="!selectedFile">
          🔍 Check Duplicates
        </button>
      </div>
    </div>

    <!-- Step 2: Review Duplicates -->
    <div v-if="step === 'review'" class="card">
      <div class="card-header">Import Analysis</div>
      <div class="card-body">
        <div class="alert alert-info">
          📊 {{ report.total_cases }} total cases in backup
        </div>

        <!-- New Cases -->
        <div class="mb-4">
          <h5>✓ {{ report.new_count }} New Cases (Ready to Import)</h5>
          <div class="list-group" style="max-height: 200px; overflow-y: auto;">
            <div class="list-group-item" v-for="c in report.new_cases" :key="c.original_id">
              <small>{{ c.diagnosis }}</small>
            </div>
          </div>
        </div>

        <!-- Duplicates in Staging -->
        <div class="mb-4" v-if="report.duplicates_in_staging.length > 0">
          <h5>⊘ {{ report.staging_count }} In Staging (Needs Decision)</h5>
          <table class="table table-sm">
            <thead>
              <tr>
                <th>Diagnosis</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in report.duplicates_in_staging" :key="c.original_id">
                <td>{{ c.diagnosis }}</td>
                <td>
                  <span class="badge bg-warning">{{ c.enrichment_status }}</span>
                </td>
                <td>
                  <button @click="resolveConflict(c.original_id)" class="btn btn-sm btn-primary">
                    Resolve
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Duplicates in Production -->
        <div class="mb-4" v-if="report.duplicates_in_production.length > 0">
          <h5>✓ {{ report.production_count }} Already in Production</h5>
          <div class="alert alert-success">
            These cases are already live. Choose to skip or update.
          </div>
          <table class="table table-sm">
            <thead>
              <tr>
                <th>Diagnosis</th>
                <th>Module</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in report.duplicates_in_production" :key="c.original_id">
                <td>{{ c.diagnosis }}</td>
                <td>{{ c.module }}</td>
                <td>
                  <button @click="resolveConflict(c.original_id)" class="btn btn-sm btn-primary">
                    Decide
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="mt-4">
          <button @click="importWithResolutions()" class="btn btn-success">
            ✓ Import ({{ report.new_count }} new + resolved conflicts)
          </button>
          <button @click="step = 'check'" class="btn btn-secondary">
            ← Back
          </button>
        </div>
      </div>
    </div>

    <!-- Step 3: Resolve Individual Conflict -->
    <div v-if="step === 'resolve'" class="card">
      <div class="card-header">Resolve Duplicate: Case #{{ conflictCase.original_id }}</div>
      <div class="card-body">
        <p><strong>Diagnosis:</strong> {{ conflictCase.diagnosis }}</p>
        
        <div class="mb-4" v-if="conflictVersions.staging_versions.length > 0">
          <h6>📋 In Staging:</h6>
          <ul>
            <li v-for="s in conflictVersions.staging_versions" :key="s.id">
              Status: {{ s.enrichment_status }}, Imported: {{ s.imported_at }}
            </li>
          </ul>
        </div>

        <div class="mb-4" v-if="conflictVersions.production_version">
          <h6>✓ In Production:</h6>
          <p>Case #{{ conflictVersions.production_version.id }}, Module: {{ conflictVersions.production_version.module }}</p>
        </div>

        <div class="mb-4">
          <h6>What do you want to do?</h6>
          <div class="form-check">
            <input class="form-check-input" type="radio" v-model="resolution" value="skip">
            <label class="form-check-label">
              🚫 Skip - Don't import, keep existing
            </label>
          </div>
          <div class="form-check">
            <input class="form-check-input" type="radio" v-model="resolution" value="replace">
            <label class="form-check-label">
              🔄 Replace - Update staging version, re-enrich
            </label>
          </div>
          <div class="form-check">
            <input class="form-check-input" type="radio" v-model="resolution" value="update">
            <label class="form-check-label">
              ✏️ Update - Modify the production case
            </label>
          </div>
          <div class="form-check">
            <input class="form-check-input" type="radio" v-model="resolution" value="create_new">
            <label class="form-check-label">
              ➕ New - Import as separate case anyway
            </label>
          </div>
          <div class="form-check">
            <input class="form-check-input" type="radio" v-model="resolution" value="force_import">
            <label class="form-check-label">
              ⚡ Force - Import despite duplicates (expert only)
            </label>
          </div>
        </div>

        <button @click="saveResolution()" class="btn btn-primary">Apply Decision</button>
        <button @click="step = 'review'" class="btn btn-secondary">← Back</button>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      step: 'check',
      selectedFile: null,
      report: null,
      conflictCase: null,
      conflictVersions: null,
      resolution: null,
      resolutions: {}  // Track all admin decisions
    }
  },
  methods: {
    selectFile(event) {
      this.selectedFile = event.target.files[0];
    },
    async checkDuplicates() {
      const formData = new FormData();
      formData.append('backup_file', this.selectedFile);
      
      const response = await fetch('/api/admin/enrichment/check-duplicates', {
        method: 'POST',
        body: formData
      });
      
      this.report = await response.json();
      this.step = 'review';
    },
    async resolveConflict(originalId) {
      const response = await fetch(`/api/admin/enrichment/conflicts/${originalId}`);
      this.conflictVersions = await response.json();
      
      this.conflictCase = this.report.duplicates_in_staging.find(c => c.original_id === originalId) ||
                         this.report.duplicates_in_production.find(c => c.original_id === originalId);
      
      this.resolution = 'skip';  // Default
      this.step = 'resolve';
    },
    saveResolution() {
      this.resolutions[this.conflictCase.original_id] = this.resolution;
      this.step = 'review';
    },
    async importWithResolutions() {
      const formData = new FormData();
      formData.append('backup_file', this.selectedFile);
      formData.append('conflicts', JSON.stringify(this.resolutions));
      
      const response = await fetch('/api/admin/enrichment/import-with-conflicts', {
        method: 'POST',
        body: formData
      });
      
      const result = await response.json();
      alert(`✓ Imported: ${result.imported}, Skipped: ${result.skipped}`);
      
      this.step = 'check';
      this.selectedFile = null;
      this.report = null;
    }
  }
}
</script>
```

---

## 6. Summary: Duplicate Detection Features

| Feature | How It Works |
|---------|--------------|
| **Pre-Import Check** | Scan backup before importing to show conflicts |
| **Staging Duplicates** | Find if case already in enrichment stage |
| **Production Duplicates** | Find if case already promoted |
| **Skip** | Don't import, keep existing |
| **Replace** | Delete old staging version, create new (re-enrich) |
| **Update** | Modify the production case directly |
| **Create New** | Import as separate case anyway (allows duplicates) |
| **Force Import** | Override all checks, import anyway |
| **Audit Trail** | Track which admin made which decision |

---

## 7. Database Schema Updates

Migration:

```bash
alembic revision --autogenerate -m "add_duplicate_tracking_to_imported_case_staging"
```

New columns:
- `promoted_to_case_id` → FK to Case table
- `promoted_at` → DateTime
- `previous_staging_id` → FK to self (previous version)
- `is_replacement` → Boolean (TRUE if updating previous import)
- Index on `(source_system, original_id, import_batch_id)`

---

## 8. Benefits

✅ **No Accidental Duplicates**: Admin sees all conflicts before importing
✅ **Smart Decisions**: 5 resolution strategies for different scenarios
✅ **Data Integrity**: Track which staging → which production case
✅ **Audit Trail**: All admin decisions recorded
✅ **Flexible**: Can replace enrichment, update live data, or skip entirely
✅ **Safe**: Always show admin what will happen before it happens

---

## Questions This Answers

> "Will admin be able to check if a case has been imported before?"

✅ **YES** - Upload file, hit "Check Duplicates", get full report

> "If yes, then choose whether to import it again or not?"

✅ **YES** - 5 resolution strategies:
- **Skip** - Don't import
- **Replace** - Re-import & re-enrich
- **Update** - Modify live case
- **New** - Import as duplicate anyway
- **Force** - Override all checks
