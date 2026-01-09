# FRCR Revision: Complete Admin System Implementation Plan

**Updated**: January 9, 2026  
**Scope**: Role-based access control, subscription model, case approval workflow, user management  
**Estimated Duration**: 3-4 sprints (16-24 hours)  
**Complexity**: High (database schema changes, permission checks, new workflows)

---

## PART 1: DATABASE SCHEMA CHANGES

### 1.1 User Model - Add Role and Subscription Fields

```python
class UserRole(enum.Enum):
    """Three-tier role system"""
    STUDENT = "student"           # Default: View 2 cases/module if free, all if paid
    CONTENT_MANAGER = "content_manager"  # Create/edit cases, toggle visibility
    ADMIN = "admin"               # Full system control

class SubscriptionStatus(enum.Enum):
    """Subscription states"""
    FREE = "free"                 # Limited to 2 cases per module
    PAID = "paid"                 # Full access
    CANCELED = "canceled"         # Was paid, now canceled

class PaymentStatus(enum.Enum):
    """Payment tracking"""
    NO_SUBSCRIPTION = "no_subscription"  # Never subscribed
    ACTIVE = "active"             # Currently paid
    PAST_DUE = "past_due"         # Payment failed
    CANCELED = "canceled"         # Subscription ended

# User Model Changes:
class User(UserMixin, db.Model):
    # ... existing fields ...
    
    # === NEW FIELDS ===
    role = db.Column(db.Enum(UserRole), default=UserRole.STUDENT, nullable=False)
    subscription_status = db.Column(db.Enum(SubscriptionStatus), default=SubscriptionStatus.FREE)
    payment_status = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.NO_SUBSCRIPTION)
    subscription_start_date = db.Column(db.DateTime, nullable=True)
    subscription_end_date = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, default=False, index=True)  # Soft delete
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Audit tracking
    last_case_viewed = db.Column(db.DateTime, nullable=True)
    last_case_viewed_id = db.Column(db.Integer, nullable=True)
```

**Why these changes:**
- `role`: Enables role-based access control (STUDENT, CONTENT_MANAGER, ADMIN)
- `subscription_status + payment_status`: Track free vs paid users
- `is_deleted + deleted_at`: Soft delete option for admins
- `last_case_viewed`: Support randomization and coverage tracking

---

### 1.2 Case Model - Add Approval Workflow

```python
class CaseStatus(enum.Enum):
    """Case lifecycle states"""
    DRAFT = "draft"               # Created by content manager, not yet visible
    PENDING_REVIEW = "pending_review"  # Waiting for admin approval
    PUBLISHED = "published"       # Approved, visible to users (public)
    PRIVATE = "private"           # Hidden from users (admin only)
    ARCHIVED = "archived"         # Old cases, hidden from view

# Case Model Changes:
class Case(db.Model):
    # ... existing fields ...
    
    # === NEW FIELDS ===
    status = db.Column(db.Enum(CaseStatus), default=CaseStatus.DRAFT, index=True)
    is_public = db.Column(db.Boolean, default=False)  # Deprecated in favor of 'status'
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    created_by_user = db.relationship('User', foreign_keys=[created_by_user_id], backref='created_cases')
    approved_by_user = db.relationship('User', foreign_keys=[approved_by_user_id], backref='approved_cases')
    audit_logs = db.relationship('CaseAuditLog', backref='case', cascade='all, delete-orphan')
    view_stats = db.relationship('CaseViewLog', backref='case', cascade='all, delete-orphan')
```

**Why these changes:**
- `status`: Tracks case lifecycle (Draft → Pending Review → Published)
- `created_by_user_id + approved_by_user_id`: Audit trail
- `audit_logs + view_stats`: Track who created, edited, and who viewed

---

### 1.3 New Models: Activity Tracking

```python
class CaseAuditLog(db.Model):
    """Audit trail for case creation, edits, approvals"""
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)  # 'created', 'edited', 'approved', 'rejected', 'deleted'
    changes = db.Column(db.JSON, nullable=True)  # What changed: {field: {old: value, new: value}}
    notes = db.Column(db.Text, nullable=True)  # Optional admin notes
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    user = db.relationship('User', backref='audit_logs')

class CaseViewLog(db.Model):
    """Track case views for student randomization and analytics"""
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    time_spent_seconds = db.Column(db.Integer, nullable=True)  # How long user spent on case
    
    __table_args__ = (
        db.Index('idx_user_case_view', 'user_id', 'case_id', 'viewed_at'),
    )
    
    user = db.relationship('User', backref='case_views')

class CaseApprovalQueue(db.Model):
    """Queue for cases pending admin approval"""
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False, unique=True)
    submitted_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    admin_notes = db.Column(db.Text, nullable=True)
    
    case = db.relationship('Case', backref='approval_queue')
    submitted_by_user = db.relationship('User', backref='submitted_cases')
```

**Why these models:**
- `CaseAuditLog`: Required for admins/content managers to track who did what
- `CaseViewLog`: Support randomization, see most-viewed cases for reports
- `CaseApprovalQueue`: Manage case approval workflow

---

## PART 2: ACCESS CONTROL DECORATORS & HELPERS

### 2.1 Permission Check Functions

```python
from functools import wraps
from flask import abort

def require_role(*roles):
    """Decorator to check user role"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def is_admin():
    """Check if user is admin"""
    return current_user.is_authenticated and current_user.role == UserRole.ADMIN

def is_content_manager():
    """Check if user is content manager or admin"""
    return current_user.is_authenticated and current_user.role in [UserRole.CONTENT_MANAGER, UserRole.ADMIN]

def is_student():
    """Check if user is student or higher"""
    return current_user.is_authenticated and current_user.role == UserRole.STUDENT

def has_case_access(case, user=None):
    """Check if user can view case based on subscription and case status"""
    user = user or current_user
    
    # Admin/Content Manager always have access
    if user.role in [UserRole.ADMIN, UserRole.CONTENT_MANAGER]:
        return True
    
    # Only published cases visible to students
    if case.status != CaseStatus.PUBLISHED:
        return False
    
    # Check subscription limits for free users
    if user.subscription_status == SubscriptionStatus.FREE:
        # Count cases viewed in this module
        viewed_count = CaseViewLog.query.join(Case).filter(
            CaseViewLog.user_id == user.id,
            Case.module == case.module
        ).count()
        if viewed_count >= 2:  # Max 2 per module for free users
            return False
    
    return True

def has_case_edit_permission(case, user=None):
    """Check if user can edit case"""
    user = user or current_user
    
    # Only admin or creator (if content manager) can edit
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.CONTENT_MANAGER and case.created_by_user_id == user.id:
        return True
    
    return False
```

---

## PART 3: IMPLEMENTATION PHASES

### PHASE 1: Database Schema & Core Infrastructure (Spike: 4 hours)

**Files to modify:**
1. `models.py` - Add new fields, enums, and models
2. Create migration: `migrations/versions/xxxx_add_role_subscription_fields.py`

**Work:**
- [ ] Add UserRole enum to User model
- [ ] Add SubscriptionStatus, PaymentStatus to User model
- [ ] Add soft delete fields (is_deleted, deleted_at, deleted_by_user_id)
- [ ] Add CaseStatus enum
- [ ] Add case workflow fields (status, created_by_user_id, approved_by_user_id, approved_at)
- [ ] Create CaseAuditLog, CaseViewLog, CaseApprovalQueue models
- [ ] Create Alembic migration
- [ ] Test: Migrate local database successfully

**Outcome:** Database ready for new features. All existing users get default role=STUDENT, subscription_status=FREE

---

### PHASE 2: User Management Backend & UI (Sprint: 6-8 hours)

**Priority: HIGHEST** (Blocks case approval workflow)

#### 2.1 Backend Endpoints

```python
# routes/admin_users.py
@admin_bp.route('/users', methods=['GET'])
@require_role(UserRole.ADMIN)
def list_users():
    """List all users with filtering and pagination"""
    # Returns: { users: [...], total, page, pages }

@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@require_role(UserRole.ADMIN)
def get_user_detail(user_id):
    """Get user details + stats"""
    # Returns: user info, subscription status, cases reviewed, etc.

@admin_bp.route('/users/<int:user_id>/role', methods=['PUT'])
@require_role(UserRole.ADMIN)
def update_user_role(user_id):
    """Change user role: student → content_manager → admin"""
    # Audit log: who changed user role when

@admin_bp.route('/users/<int:user_id>/status', methods=['PUT'])
@require_role(UserRole.ADMIN)
def update_user_status(user_id):
    """Activate/deactivate user"""

@admin_bp.route('/users/<int:user_id>/subscription', methods=['PUT'])
@require_role(UserRole.ADMIN)
def update_subscription(user_id):
    """Update subscription and payment status"""

@admin_bp.route('/users/<int:user_id>/delete', methods=['PUT', 'DELETE'])
@require_role(UserRole.ADMIN)
def delete_user(user_id):
    """Delete user: soft delete (default) or permanent (with ?permanent=true)"""
```

#### 2.2 Frontend: User Management Tab

**admin_dashboard.html** - New section:
```html
<div id="user-management-tab" class="tab-pane">
    <!-- Search & Filter -->
    <input type="search" placeholder="Search users..." id="user-search">
    <select id="role-filter">
        <option>All Roles</option>
        <option value="student">Students</option>
        <option value="content_manager">Content Managers</option>
        <option value="admin">Admins</option>
    </select>
    
    <!-- User Table -->
    <table id="users-table">
        <thead>
            <tr>
                <th>Email</th>
                <th>Name</th>
                <th>Role</th>
                <th>Subscription</th>
                <th>Status</th>
                <th>Joined</th>
                <th>Last Login</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody id="users-body"></tbody>
    </table>
    
    <!-- User Detail Modal -->
    <div id="user-detail-modal" class="modal">
        <!-- User info, stats, actions -->
    </div>
</div>
```

**JS Functions:**
- `loadUsers()` - Fetch and render user list
- `openUserDetail(userId)` - Show detail modal
- `updateUserRole(userId, newRole)` - Promote/demote user
- `updateSubscription(userId, status)` - Change subscription status
- `deleteUser(userId)` - Show soft/permanent delete option

**Estimated Time:**
- Backend routes: 3 hours
- Frontend UI: 2 hours
- Testing: 1 hour
- **Total: 6 hours**

---

### PHASE 3: Case Approval Workflow (Sprint: 5-7 hours)

#### 3.1 Backend Endpoints

```python
# routes/admin_cases.py
@admin_bp.route('/case-queue', methods=['GET'])
@require_role(UserRole.ADMIN, UserRole.CONTENT_MANAGER)
def get_case_queue():
    """Get cases pending approval (DRAFT or PENDING_REVIEW)"""

@admin_bp.route('/cases/<int:case_id>/approve', methods=['POST'])
@require_role(UserRole.ADMIN)
def approve_case(case_id):
    """Approve case: PENDING_REVIEW → PUBLISHED"""
    # Log: admin approved case created by [creator]

@admin_bp.route('/cases/<int:case_id>/reject', methods=['POST'])
@require_role(UserRole.ADMIN)
def reject_case(case_id):
    """Reject case: PENDING_REVIEW → DRAFT with admin notes"""

@admin_bp.route('/cases/<int:case_id>/status', methods=['PUT'])
@require_role(UserRole.CONTENT_MANAGER)
def update_case_status(case_id):
    """Content manager: toggle public/hidden for their cases"""
    # Only content manager creator can do this

@cm_bp.route('/cases/create', methods=['POST'])
@require_role(UserRole.CONTENT_MANAGER, UserRole.ADMIN)
def create_case():
    """Create case as DRAFT, requires admin approval"""
    # Create case with status=DRAFT
    # Add to CaseApprovalQueue
    # Log: content manager created case
```

#### 3.2 Frontend: Case Queue Tab

**admin_dashboard.html** - New section:
```html
<div id="case-approval-tab" class="tab-pane">
    <!-- Approval Stats -->
    <div class="stats-cards">
        <div>Pending Review: <span id="pending-count">0</span></div>
        <div>Published: <span id="published-count">0</span></div>
        <div>Draft: <span id="draft-count">0</span></div>
    </div>
    
    <!-- Case Queue Table -->
    <table id="case-queue-table">
        <thead>
            <tr>
                <th>Diagnosis</th>
                <th>Status</th>
                <th>Created By</th>
                <th>Module</th>
                <th>Body Part</th>
                <th>Submitted</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody id="case-queue-body"></tbody>
    </table>
    
    <!-- Approve/Reject Modal -->
    <div id="case-review-modal" class="modal">
        <div>Case: <span id="review-case-name"></span></div>
        <div>Created by: <span id="review-case-creator"></span></div>
        <textarea id="admin-notes" placeholder="Review notes..."></textarea>
        <button onclick="approveCase()">Approve</button>
        <button onclick="rejectCase()">Reject</button>
    </div>
</div>
```

**Estimated Time:**
- Backend routes: 3 hours
- Frontend UI: 2 hours
- Testing: 1-2 hours
- **Total: 6-7 hours**

---

### PHASE 4: Case Creation with Table Support (Sprint: 3-4 hours)

**Leverage existing `/api/case/create` endpoint**

#### 4.1 Frontend Enhancement

Add button to admin dashboard:
```html
<button class="btn btn-primary" onclick="createNewCase()">
    <i class="fas fa-plus"></i> Create Case
</button>
```

This redirects to `/edit-case?new=true&admin=true`

#### 4.2 Edit Case Editor Enhancement

Modify `edit-case.html` to add table support:
```javascript
// Add to rich text editor toolbar
function insertTable() {
    const table = `<table style="width:100%; border-collapse:collapse;">
        <tr>
            <td style="border:1px solid #ccc; padding:8px">Cell 1</td>
            <td style="border:1px solid #ccc; padding:8px">Cell 2</td>
        </tr>
    </table>`;
    insertHTMLAtCursor(table);
}
```

#### 4.3 Case Creation Form Change

When case created by admin/content manager:
- Set `status = DRAFT` (not `is_public = True`)
- Add to `CaseApprovalQueue`
- Log: case created

**Estimated Time:**
- Backend: 0 hours (reuse existing)
- Frontend: 2 hours (add button, table support)
- Testing: 1-2 hours
- **Total: 3-4 hours**

---

### PHASE 5: Case Visibility Control (Sprint: 2-3 hours)

Content managers need to toggle case public/private after approval.

#### 5.1 Backend

```python
@cm_bp.route('/cases/<int:case_id>/toggle-visibility', methods=['PUT'])
@require_role(UserRole.CONTENT_MANAGER, UserRole.ADMIN)
def toggle_case_visibility(case_id):
    """Toggle case visibility: PUBLISHED ↔ PRIVATE"""
    # Only creator or admin can do this
    case.status = CaseStatus.PRIVATE if case.status == CaseStatus.PUBLISHED else CaseStatus.PUBLISHED
    # Log the change
```

#### 5.2 Frontend

Add toggle button in case view for content managers:
```html
{% if current_user.role in ['content_manager', 'admin'] %}
    <button class="btn btn-sm" id="visibility-toggle" onclick="toggleCaseVisibility()">
        <i class="fas fa-eye"></i> Toggle Visibility
    </button>
{% endif %}
```

**Estimated Time: 2-3 hours**

---

### PHASE 6: Subscription & Payment Restrictions (Sprint: 3-4 hours)

#### 6.1 Backend: Case View Filtering

```python
# In routes for case viewing
def check_case_access(case):
    if not has_case_access(case, current_user):
        abort(403)  # Forbidden: view limit exceeded or not published
    
    # Log view
    CaseViewLog.create(user_id=current_user.id, case_id=case.id)
```

#### 6.2 Frontend: View Limit Messages

If free user hits 2-case limit for module:
```html
<div class="alert alert-info">
    You've viewed 2 cases in this module (free limit).
    <a href="/subscribe">Upgrade to Paid</a> for unlimited access.
</div>
```

**Estimated Time: 3-4 hours**

---

### PHASE 7: Export Reports (Sprint: 4-5 hours)

Admins can export CSV with:
- Number of users, cases, most viewed cases, most viewed modules, content created

#### 7.1 Backend Routes

```python
@admin_bp.route('/reports/users', methods=['GET'])
@require_role(UserRole.ADMIN)
def export_users_report():
    """Export users CSV"""

@admin_bp.route('/reports/cases', methods=['GET'])
@require_role(UserRole.ADMIN)
def export_cases_report():
    """Export cases CSV"""

@admin_bp.route('/reports/analytics', methods=['GET'])
@require_role(UserRole.ADMIN)
def export_analytics_report():
    """Export analytics CSV: most viewed, most reviewed"""
```

#### 7.2 Frontend

Add Reports tab to admin dashboard:
```html
<div id="reports-tab" class="tab-pane">
    <button onclick="exportUsersReport()">Export Users</button>
    <button onclick="exportCasesReport()">Export Cases</button>
    <button onclick="exportAnalyticsReport()">Export Analytics</button>
</div>
```

**Estimated Time: 4-5 hours**

---

### PHASE 8: Bulk Import (Sprint: 5-6 hours)

Support CSV upload or API import from FRCR Examiner app.

#### 8.1 CSV Import

```python
@admin_bp.route('/import/cases', methods=['POST'])
@require_role(UserRole.ADMIN, UserRole.CONTENT_MANAGER)
def import_cases_csv():
    """Upload CSV of cases
    CSV format: diagnosis, module, body_part, questions, answers, discussion
    """
```

#### 8.2 API Import from FRCR Examiner

```python
@admin_bp.route('/import/frcr-examiner', methods=['POST'])
@require_role(UserRole.ADMIN)
def import_from_examiner():
    """Pull cases from FRCR Examiner app API"""
    # Query: examiner_app_url + /api/cases
    # Transform: examiner case format → revision case format
```

**Estimated Time: 5-6 hours**

---

### PHASE 9: Admin Dashboard UI Refactor (Sprint: 3-4 hours)

#### 9.1 Simplify Backup Manager

Collapse backup section from 5 cards → 1 card with:
- Quick stats (total backups, storage, last backup)
- "Create Manual Backup" button
- "View Backup History" link (optional)

Remove:
- Detailed database tables
- Activity log
- Backup restore UI (if not needed)

#### 9.2 Add Navigation Tabs

```html
<ul class="nav nav-tabs">
    <li><a href="#overview-tab" data-toggle="tab">Overview</a></li>
    <li><a href="#user-management-tab" data-toggle="tab">Users</a></li>
    <li><a href="#case-management-tab" data-toggle="tab">Cases</a></li>
    <li><a href="#case-approval-tab" data-toggle="tab">Approval Queue</a></li>
    <li><a href="#reports-tab" data-toggle="tab">Reports</a></li>
    <li><a href="#backups-tab" data-toggle="tab">Backups</a></li>
    <li><a href="#settings-tab" data-toggle="tab">Settings</a></li>
</ul>
```

**Estimated Time: 3-4 hours**

---

## PART 4: SUMMARY TABLE

| Phase | Feature | Backend Hours | Frontend Hours | Total | Dependencies |
|-------|---------|---------------|----------------|-------|--------------|
| 1 | Database Schema | 4 | 0 | 4 | None |
| 2 | User Management | 3 | 2 | 5-6 | Phase 1 |
| 3 | Case Approval | 3 | 2 | 5-7 | Phase 1, 2 |
| 4 | Case Creation | 0 | 2 | 2-3 | Phase 1 |
| 5 | Visibility Control | 1 | 1 | 2-3 | Phase 3 |
| 6 | Subscription Limits | 2 | 1 | 3-4 | Phase 1 |
| 7 | Reports | 3 | 1 | 4-5 | Phase 2, 3 |
| 8 | Bulk Import | 4 | 1 | 5-6 | Phase 1, 3 |
| 9 | Dashboard UI | 0 | 3-4 | 3-4 | All phases |
| **TOTAL** | **All** | **23-26** | **14-16** | **37-42 hours** | Sequential |

---

## PART 5: RECOMMENDED SPRINT PLAN

### Sprint 1: Foundation (Week 1)
- Phase 1: Database schema changes (4 hours)
- Phase 2: User management (6 hours)
- **Total: 10 hours → ~2 days work**

**Outcome**: Admins can manage users, promote/demote roles, change subscription status

---

### Sprint 2: Case Workflow (Week 2)
- Phase 3: Case approval workflow (6-7 hours)
- Phase 4: Case creation with tables (3-4 hours)
- Phase 5: Visibility control (2-3 hours)
- **Total: 11-14 hours → ~2-3 days work**

**Outcome**: Content managers create cases (DRAFT), admins approve (PUBLISHED), admins/content managers toggle visibility

---

### Sprint 3: Features & UX (Week 3)
- Phase 6: Subscription limits (3-4 hours)
- Phase 7: Reports (4-5 hours)
- Phase 9: Dashboard UI refactor (3-4 hours)
- **Total: 10-13 hours → ~2-3 days work**

**Outcome**: Free users limited to 2 cases/module, admins can export reports, dashboard cleaned up

---

### Sprint 4: Import & Polish (Week 4)
- Phase 8: Bulk import (5-6 hours)
- Testing & bug fixes (2-3 hours)
- **Total: 7-9 hours → ~1-2 days work**

**Outcome**: Admins can import cases from CSV or FRCR Examiner app API

---

## PART 6: CRITICAL IMPLEMENTATION NOTES

### 6.1 Backward Compatibility

**Problem**: Existing cases have `is_public=true` but no `status` field

**Solution**: Migration script
```python
# In migration
for case in Case.query.all():
    case.status = CaseStatus.PUBLISHED if case.is_public else CaseStatus.PRIVATE
db.session.commit()
```

---

### 6.2 Access Control Pattern

Apply this pattern everywhere:

```python
@app.route('/api/case/<int:case_id>', methods=['GET'])
@login_required
def get_case(case_id):
    case = Case.query.get_or_404(case_id)
    
    # Check access
    if not has_case_access(case, current_user):
        abort(403)
    
    # Proceed
    return jsonify(case_to_dict(case))
```

---

### 6.3 Audit Logging Pattern

Create log entry for every admin action:

```python
def log_audit(case_id, user_id, action, changes=None, notes=None):
    log = CaseAuditLog(
        case_id=case_id,
        user_id=user_id,
        action=action,
        changes=changes,
        notes=notes
    )
    db.session.add(log)
    db.session.commit()
```

---

### 6.4 Soft Delete Implementation

When user soft-deleted:
1. Set `is_deleted=true`, `deleted_at=now()`, `deleted_by_user_id=admin_id`
2. Exclude from user lists/queries: `.filter_by(is_deleted=False)`
3. Permanently delete if admin chooses `?permanent=true` (requires confirmation)

---

## PART 7: TESTING CHECKLIST

### Unit Tests
- [ ] UserRole enum works correctly
- [ ] `has_case_access()` correctly applies subscription limits
- [ ] `has_case_edit_permission()` checks content manager ownership
- [ ] Soft delete marks user but keeps data
- [ ] Migration runs without errors

### Integration Tests
- [ ] Admin can create user, promote to content manager, then to admin
- [ ] Content manager can create case (DRAFT), admin approves (PUBLISHED)
- [ ] Free user can view 2 cases/module, 3rd shows limit message
- [ ] Paid user can view unlimited cases
- [ ] Case audit log tracks all changes
- [ ] Reports export correct data

### End-to-End Tests
- [ ] Admin dashboard loads all tabs
- [ ] User management: list → detail → promote → delete works
- [ ] Case approval: draft → review → approve → published
- [ ] Bulk import: CSV upload creates cases as DRAFT

---

## PART 8: RISK MITIGATION

| Risk | Probability | Mitigation |
|------|------------|-----------|
| Migration fails on existing data | Medium | Test migration on copy of production DB first |
| Soft delete breaks existing queries | High | Add `.filter_by(is_deleted=False)` everywhere |
| Permission checks missed | High | Use `@require_role()` decorator consistently |
| Case view limits too restrictive | Low | Make limit configurable in settings |
| Import duplicates cases | Medium | Add UUID to cases, check for duplicates on import |

---

## NEXT STEPS

1. **Review this plan** - Any changes needed?
2. **Approve Sprint 1** - Start with database schema + user management
3. **Begin Phase 1** - Update models.py with new fields
4. **Create migration** - Alembic migration for new schema
5. **Implement Phase 2** - User management endpoints + UI

Should I proceed with Sprint 1 implementation?

