# Data Migration Implementation - Quick Start Guide

## 📋 Summary

You want to migrate cases from FRCR-Examiner to FRCR-Revision with admin enrichment. This document gives you the step-by-step implementation path.

---

## 🎯 Key Features

| Feature | Purpose |
|---------|---------|
| **ImportedCaseStaging** | Temporary holding area for raw imported data |
| **Enrichment Workflow** | Admins add Module, BodyPart, AgeGroup, is_public |
| **Approval Gate** | QA review before data enters production |
| **Promotion Service** | Move approved cases to main Case table |
| **Batch Tracking** | Group imports by import_batch_id |

---

## 🚀 Quick Implementation Path

### Step 1: Update Models (15 min)

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
    
    # Import tracking
    import_batch_id = db.Column(db.String(50), nullable=False, index=True)
    source_system = db.Column(db.String(50), default='frcr_examiner')
    import_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    enriched_by = db.relationship('User', foreign_keys=[enriched_by_user_id])
    approved_by = db.relationship('User', foreign_keys=[approved_by_user_id])
```

Run migration:
```bash
cd /Users/zen/myRepos/projects/FRCR_REVISION
alembic revision --autogenerate -m "add_imported_case_staging_model"
alembic upgrade head
```

---

### Step 2: Create Import Service (20 min)

Create `services/import_service.py`:

```python
"""Service layer for data import and promotion"""
import json
import uuid
from datetime import datetime
from models import db, ImportedCaseStaging, Case, CaseStatus, FRCRModule, BodyPart, AgeGroup

class ImportService:
    @staticmethod
    def import_from_backup(backup_file_path, source_system='frcr_examiner'):
        """Import cases from JSON backup into staging"""
        import_batch_id = str(uuid.uuid4())
        imported_count = 0
        errors = []
        
        try:
            with open(backup_file_path, 'r') as f:
                backup_data = json.load(f)
            
            for case_data in backup_data.get('cases', []):
                try:
                    staging = ImportedCaseStaging(
                        original_id=case_data.get('id'),
                        case_number=case_data.get('case_number'),
                        diagnosis=case_data.get('diagnosis', ''),
                        questions=case_data.get('questions', ''),
                        answers=case_data.get('answers', ''),
                        discussion=case_data.get('discussion'),
                        import_batch_id=import_batch_id,
                        source_system=source_system,
                    )
                    db.session.add(staging)
                    imported_count += 1
                except Exception as e:
                    errors.append(f"Case {case_data.get('case_number')}: {str(e)}")
            
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
        """Get cases pending enrichment"""
        return ImportedCaseStaging.query.filter_by(
            enrichment_status='pending'
        ).paginate(page=page, per_page=per_page)
    
    @staticmethod
    def get_enrichment_stats(batch_id=None):
        """Get completion stats"""
        query = ImportedCaseStaging.query
        if batch_id:
            query = query.filter_by(import_batch_id=batch_id)
        
        total = query.count()
        return {
            'total': total,
            'by_status': {
                'pending': query.filter_by(enrichment_status='pending').count(),
                'enriched': query.filter_by(enrichment_status='enriched').count(),
                'rejected': query.filter_by(enrichment_status='rejected').count(),
            }
        }

class PromotionService:
    @staticmethod
    def promote_case(staging_case_id, created_by_user_id=None):
        """Promote staging case to production"""
        try:
            staging = ImportedCaseStaging.query.get(staging_case_id)
            if not staging or not staging.approved_at:
                return {'success': False, 'message': 'Case not approved'}
            
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
                created_by_user_id=created_by_user_id,
            )
            
            db.session.add(case)
            db.session.flush()
            
            db.session.commit()
            return {
                'success': True,
                'case_id': case.id
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def bulk_promote(batch_id, created_by_user_id):
        """Promote all approved cases in batch"""
        staging_cases = ImportedCaseStaging.query.filter_by(
            import_batch_id=batch_id
        ).filter(ImportedCaseStaging.approved_at != None).all()
        
        promoted = 0
        for staging in staging_cases:
            result = PromotionService.promote_case(staging.id, created_by_user_id)
            if result['success']:
                promoted += 1
        
        return {'promoted': promoted, 'total': len(staging_cases)}
```

---

### Step 3: Create Admin Routes (25 min)

Create `admin_enrichment_routes.py`:

```python
"""Admin routes for case enrichment and import"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, ImportedCaseStaging, FRCRModule, BodyPart, AgeGroup
from services.import_service import ImportService, PromotionService
from access_control import require_admin
from datetime import datetime
import tempfile
import os

enrichment_bp = Blueprint('enrichment', __name__, url_prefix='/api/admin/enrichment')

@enrichment_bp.before_request
@login_required
@require_admin
def check_admin():
    pass

@enrichment_bp.route('/import', methods=['POST'])
def import_cases():
    """Upload and import backup JSON file"""
    if 'backup_file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['backup_file']
    if not file.filename.endswith('.json'):
        return jsonify({'error': 'Only JSON files'}), 400
    
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
        file.save(tmp.name)
        result = ImportService.import_from_backup(tmp.name)
        os.unlink(tmp.name)
    
    return jsonify(result), 200 if result['success'] else 400

@enrichment_bp.route('/pending', methods=['GET'])
def get_pending_cases():
    """Get cases pending enrichment"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    pagination = ImportService.get_pending_cases(page, per_page)
    
    return jsonify({
        'cases': [{
            'id': c.id,
            'case_number': c.case_number,
            'diagnosis': c.diagnosis[:100],
            'module': c.module.value if c.module else None,
            'body_part': c.body_part.value if c.body_part else None,
            'age_group': c.age_group.value if c.age_group else None,
        } for c in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
    })

@enrichment_bp.route('/<int:case_id>', methods=['GET'])
def get_case_details(case_id):
    """Get full case details"""
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
    })

@enrichment_bp.route('/<int:case_id>/enrich', methods=['PUT'])
def enrich_case(case_id):
    """Save enrichment metadata"""
    case = ImportedCaseStaging.query.get_or_404(case_id)
    data = request.get_json()
    
    try:
        if data.get('module'):
            case.module = FRCRModule(data['module'])
        if data.get('body_part'):
            case.body_part = BodyPart(data['body_part'])
        if data.get('age_group'):
            case.age_group = AgeGroup(data['age_group'])
        
        case.is_public = data.get('is_public', False)
        case.enrichment_status = 'enriched'
        case.enriched_by_user_id = current_user.id
        case.enriched_at = datetime.utcnow()
        case.enrichment_notes = data.get('enrichment_notes', '')
        
        db.session.commit()
        return jsonify({'success': True}), 200
    except ValueError as e:
        return jsonify({'error': f'Invalid value: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@enrichment_bp.route('/<int:case_id>/approve', methods=['POST'])
def approve_case(case_id):
    """Approve enriched case"""
    case = ImportedCaseStaging.query.get_or_404(case_id)
    
    if case.enrichment_status != 'enriched':
        return jsonify({'error': 'Case must be enriched first'}), 400
    
    data = request.get_json() or {}
    case.approved_by_user_id = current_user.id
    case.approved_at = datetime.utcnow()
    case.approval_notes = data.get('approval_notes', '')
    
    db.session.commit()
    return jsonify({'success': True}), 200

@enrichment_bp.route('/<int:case_id>/promote', methods=['POST'])
def promote_case(case_id):
    """Promote case to production"""
    result = PromotionService.promote_case(case_id, current_user.id)
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400

@enrichment_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get enrichment statistics"""
    batch_id = request.args.get('batch_id')
    stats = ImportService.get_enrichment_stats(batch_id)
    return jsonify(stats), 200
```

Add to `app.py`:

```python
from admin_enrichment_routes import enrichment_bp
app.register_blueprint(enrichment_bp)
```

---

### Step 4: Test with cURL (10 min)

```bash
# 1. Import backup
curl -X POST -F "backup_file=@/Users/zen/Downloads/frcr_examiner_backup_20260109_115350.json" \
  http://localhost:5000/api/admin/enrichment/import

# Response:
# {
#   "import_batch_id": "abc123...",
#   "total_imported": 100,
#   "success": true,
#   "errors": []
# }

# 2. Get pending cases
curl http://localhost:5000/api/admin/enrichment/pending?page=1&per_page=5

# 3. Get one case
curl http://localhost:5000/api/admin/enrichment/1

# 4. Enrich a case
curl -X PUT -H "Content-Type: application/json" \
  -d '{
    "module": "Cardiothoracic and Vascular",
    "body_part": "Cardiovascular",
    "age_group": "Adult",
    "is_public": true,
    "enrichment_notes": "Good teaching case"
  }' \
  http://localhost:5000/api/admin/enrichment/1/enrich

# 5. Approve case
curl -X POST -H "Content-Type: application/json" \
  -d '{"approval_notes": "Ready for production"}' \
  http://localhost:5000/api/admin/enrichment/1/approve

# 6. Promote to production
curl -X POST http://localhost:5000/api/admin/enrichment/1/promote

# 7. Check stats
curl http://localhost:5000/api/admin/enrichment/stats?batch_id=abc123...
```

---

### Step 5: Create Admin UI Components (40 min)

This is where the admin dashboard lives. For quick testing, create a simple HTML form in a new admin template.

Create `templates/import_manager.html`:

```html
{% extends "base.html" %}

{% block content %}
<div class="container py-4">
    <h2>📊 Import & Enrichment Manager</h2>
    
    <!-- Import Section -->
    <div class="card mb-4">
        <div class="card-header bg-primary text-white">
            <h5 class="mb-0">📥 Import Backup</h5>
        </div>
        <div class="card-body">
            <form id="importForm">
                <div class="mb-3">
                    <label for="backupFile" class="form-label">Select Backup JSON File</label>
                    <input class="form-control" type="file" id="backupFile" accept=".json">
                </div>
                <button type="button" class="btn btn-primary" onclick="importBackup()">
                    <i class="fas fa-upload"></i> Import
                </button>
            </form>
            <div id="importStatus" class="mt-3" style="display:none;">
                <p id="importMessage"></p>
                <div class="progress" style="display:none;" id="importProgress">
                    <div class="progress-bar" id="importBar" role="progressbar" style="width: 0%;"></div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Stats Section -->
    <div class="card mb-4">
        <div class="card-header bg-info text-white">
            <h5 class="mb-0">📈 Enrichment Progress</h5>
        </div>
        <div class="card-body" id="statsContainer">
            <p>Loading...</p>
        </div>
    </div>
    
    <!-- Pending Cases Section -->
    <div class="card">
        <div class="card-header bg-warning text-dark">
            <h5 class="mb-0">📋 Pending Enrichment</h5>
        </div>
        <div class="card-body">
            <div id="pendingCasesContainer">
                <p>Loading...</p>
            </div>
        </div>
    </div>
</div>

<script>
function importBackup() {
    const fileInput = document.getElementById('backupFile');
    const formData = new FormData();
    formData.append('backup_file', fileInput.files[0]);
    
    fetch('/api/admin/enrichment/import', {
        method: 'POST',
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            alert(`✓ Imported ${data.total_imported} cases\nBatch ID: ${data.import_batch_id}`);
            loadStats();
            loadPendingCases();
        } else {
            alert(`✗ Import failed: ${data.errors[0]}`);
        }
    });
}

function loadStats() {
    fetch('/api/admin/enrichment/stats')
        .then(r => r.json())
        .then(data => {
            const html = `
                <p>Total: ${data.total}</p>
                <p>✓ Enriched: ${data.by_status.enriched}</p>
                <p>⧗ Pending: ${data.by_status.pending}</p>
                <p>⨯ Rejected: ${data.by_status.rejected}</p>
                <div class="progress">
                    <div class="progress-bar" style="width: ${(data.by_status.enriched/data.total*100)}%;">
                        ${Math.round(data.by_status.enriched/data.total*100)}%
                    </div>
                </div>
            `;
            document.getElementById('statsContainer').innerHTML = html;
        });
}

function loadPendingCases() {
    fetch('/api/admin/enrichment/pending?per_page=10')
        .then(r => r.json())
        .then(data => {
            let html = '<table class="table"><thead><tr><th>#</th><th>Diagnosis</th><th>Module</th><th>Action</th></tr></thead><tbody>';
            
            for (const c of data.cases) {
                html += `
                    <tr>
                        <td>${c.case_number}</td>
                        <td>${c.diagnosis.substring(0, 50)}...</td>
                        <td>${c.module || 'Not set'}</td>
                        <td><button class="btn btn-sm btn-primary" onclick="enrichCase(${c.id})">Enrich</button></td>
                    </tr>
                `;
            }
            
            html += '</tbody></table>';
            document.getElementById('pendingCasesContainer').innerHTML = html;
        });
}

function enrichCase(caseId) {
    // Simplified: show alert with case ID
    // In production, open a modal with form
    alert(`Would open enrichment form for case ${caseId}`);
}

// Load on page load
window.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadPendingCases();
});
</script>
{% endblock %}
```

Add route in `app.py`:

```python
@app.route('/admin/import-manager')
@login_required
def import_manager():
    if not current_user.is_admin:
        return redirect('/login')
    return render_template('import_manager.html')
```

---

## 🔄 Complete Workflow

```
1. Admin logs in → /admin/import-manager
2. Admin uploads: frcr_examiner_backup_20260109_115350.json
   ↓
3. API imports → ImportedCaseStaging (100 cases, status='pending')
   ↓
4. Dashboard shows: "100 cases pending enrichment"
   ↓
5. Admin clicks case → Opens enrichment form
   - Selects Module: "Cardiothoracic and Vascular"
   - Selects Body: "Cardiovascular"
   - Selects Age: "Adult"
   - Toggles Public: ON
   - Clicks SAVE
   ↓
6. Case status → 'enriched', enriched_at = now, enriched_by = admin
   ↓
7. Admin reviews → Clicks APPROVE
   ↓
8. Case status → approved_at = now, approved_by = admin
   ↓
9. Admin clicks PROMOTE or bulk promote all
   ↓
10. PromotionService creates Case record in production
    ↓
11. Case now available for students!
    ✓ Shows in revision
    ✓ Searchable by module
    ✓ Filterable by body part
```

---

## ✅ Validation Checklist

- [ ] Model migration runs without errors
- [ ] Import service successfully reads backup JSON
- [ ] 100+ cases imported to staging table
- [ ] All enum values (FRCRModule, BodyPart, AgeGroup) work
- [ ] Enrichment endpoint updates all fields
- [ ] Approval endpoint sets approved_at and approved_by
- [ ] Promotion creates Case in production table
- [ ] Promoted cases appear with correct module/body_part/age_group
- [ ] Admin UI displays pending cases
- [ ] Stats show completion percentage

---

## 🎓 Example Data Flow

```
Input: Case from frcr_examiner_backup.json
{
  "id": 1,
  "case_number": 1,
  "diagnosis": "Right lower lobe pneumonia",
  "questions": "What is the diagnosis?",
  "answers": "Bacterial pneumonia",
  "discussion": "Note the consolidation..."
}

↓ ImportService.import_from_backup()

ImportedCaseStaging record created:
{
  "id": 42,
  "original_id": 1,
  "case_number": 1,
  "diagnosis": "Right lower lobe pneumonia",
  "module": NULL,
  "body_part": NULL,
  "age_group": NULL,
  "is_public": FALSE,
  "enrichment_status": "pending"
}

↓ Admin enriches via PUT /api/admin/enrichment/42/enrich

{
  "id": 42,
  "original_id": 1,
  "case_number": 1,
  "diagnosis": "Right lower lobe pneumonia",
  "module": "Cardiothoracic and Vascular",  ← ADDED
  "body_part": "Lung and Mediastinum",      ← ADDED
  "age_group": "Adult",                     ← ADDED
  "is_public": TRUE,                        ← ADDED
  "enrichment_status": "enriched",
  "enriched_by_user_id": 1,
  "enriched_at": "2026-01-09T12:30:00"
}

↓ Admin approves via POST /api/admin/enrichment/42/approve

Status: enriched → approved_at set

↓ PromotionService.promote_case(42)

Case table (NEW record):
{
  "id": 105,
  "case_number": 1,
  "diagnosis": "Right lower lobe pneumonia",
  "module": "Cardiothoracic and Vascular",
  "body_part": "Lung and Mediastinum",
  "age_group": "Adult",
  "is_public": TRUE,
  "status": "PUBLISHED",
  "created_by_user_id": 1,
  "created_at": "2026-01-09T12:40:00"
}

✓ Case now visible to students!
```

---

## 🚨 Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Import fails with JSON error | Validate backup file format matches spec |
| Enrichment endpoint 404 | Ensure blueprint registered in app.py |
| FRCRModule enum error | Use exact enum value from models.py |
| Cases not appearing in Case table | Verify promotion ran successfully |
| Migration conflicts | Delete alembic versions folder, regenerate |

---

## 📊 Testing Script

Save as `test_import_flow.sh`:

```bash
#!/bin/bash

echo "🧪 Testing Import Workflow"

BACKUP_FILE="$1"
BASE_URL="http://localhost:5000"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: ./test_import_flow.sh <backup_file.json>"
    exit 1
fi

echo "1️⃣  Importing backup..."
IMPORT_RESPONSE=$(curl -s -X POST \
  -F "backup_file=@$BACKUP_FILE" \
  $BASE_URL/api/admin/enrichment/import)

BATCH_ID=$(echo $IMPORT_RESPONSE | grep -o '"import_batch_id":"[^"]*' | cut -d'"' -f4)
echo "✓ Imported with batch ID: $BATCH_ID"

echo ""
echo "2️⃣  Getting pending cases..."
curl -s $BASE_URL/api/admin/enrichment/pending?per_page=5 | python -m json.tool

echo ""
echo "3️⃣  Getting stats..."
curl -s "$BASE_URL/api/admin/enrichment/stats?batch_id=$BATCH_ID" | python -m json.tool

echo ""
echo "✅ Test complete!"
```

Run:
```bash
chmod +x test_import_flow.sh
./test_import_flow.sh /Users/zen/Downloads/frcr_examiner_backup_20260109_115350.json
```

---

## 🎯 Next Steps

1. **Implement Phase 1** (Models & Services)
   - Add ImportedCaseStaging to models.py
   - Create migration
   - Create import_service.py

2. **Implement Phase 2** (Backend API)
   - Create admin_enrichment_routes.py
   - Register blueprint
   - Test with cURL

3. **Implement Phase 3** (Frontend)
   - Create import_manager.html template
   - Build enrichment form component
   - Add to admin dashboard

4. **Test End-to-End**
   - Import real backup
   - Enrich 5 test cases
   - Approve and promote
   - Verify in revision

---

## 💡 Pro Tips

✅ Start with small test batch (5-10 cases) before full import
✅ Always approve before promoting to catch errors
✅ Use `import_batch_id` to group related imports
✅ Set `is_public=false` for draft cases
✅ Add detailed `enrichment_notes` for audit trail
✅ Test API endpoints with Postman first, then build UI

Good luck! 🚀
