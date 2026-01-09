# Admin Dashboard Restructuring Strategy

## Executive Summary
Transform the admin dashboard from a backup-focused interface into a comprehensive admin control center. Simplify backup management, add critical admin features (case creation, user management), and establish a scalable foundation for future admin capabilities.

---

## CURRENT STATE ANALYSIS

### Admin Dashboard Today
- **Primary Focus**: Database backup/restore (70% of UI)
- **Backup Features**: Statistics, manual creation, history log, auto-backup notifications
- **User Management**: None (admins can't manage users)
- **Case Management**: Edit/delete only (via view-case.html when is_admin=true)
- **Scalability**: Not positioned for additional admin features

### Case Creation Today
- **Existing Route**: `POST /api/case/create` (Flask backend)
- **UI Access**: Via `edit-case.html` full-page editor
- **Launch Points**: manage_session.html OR edit-case.html with ?new=true
- **Capabilities**: 
  - Q&A pairs (text-only)
  - Images with descriptions
  - Module & body part categorization
  - Discussion text field
- **Limitation**: No table support in answers/discussion
- **Current Users**: Not directly accessible to admins (designed for exam setup)

### User Model
- Fields: `id`, `email`, `password_hash`, `full_name`, `is_admin`, `is_active`, `created_at`, `last_login`
- **Missing**: Subscription tier, payment status, role granularity
- **Current Access Control**: Binary (is_admin=true/false)

---

## PROPOSED ADMIN DASHBOARD ARCHITECTURE

### New Dashboard Structure
```
Admin Dashboard (/)
├── Dashboard Overview (Quick Stats)
│   ├── Users: total, active, admins
│   ├── Cases: total, public, private
│   └── Backups: count, storage used
│
├── User Management
│   ├── List all users
│   ├── View user details + stats
│   ├── Change user status (active/inactive)
│   ├── Upgrade to admin / Remove admin
│   └── Delete user (with cascade handling)
│
├── Case Management
│   ├── Create case (with table support in answers/discussion)
│   ├── List all cases (filterable)
│   ├── Edit case
│   ├── Delete case
│   └── Manage case visibility (public/private)
│
├── Database Backups (Simplified)
│   ├── Quick stats (simplified from current)
│   ├── Create manual backup
│   └── Download/restore backup
│
├── Settings (Placeholder)
│   └── Future: Payments & Subscriptions (stub)
└── External Data Import (Placeholder)
    └── Pull cases from FRCR Examiner app (deferred)
```

---

## IMPLEMENTATION STRATEGY

### Phase 1: Simplify Backup Manager (Foundation)
**Why**: Clear cluttered admin dashboard, reduce cognitive load

**Changes**:
1. Collapse current 5-section backup dashboard into 1-2 cards
   - Keep: Quick stats card (total backups, storage, last backup)
   - Keep: Single "Create Manual Backup" button
   - Remove: Detailed database summary, activity log, table listing
   - Remove: Backup restore table (move to modal/separate page if needed)

2. Rationale:
   - Auto-backup handles 95% of backup needs
   - Admin rarely needs to manually restore
   - Detailed backup logs can be in separate "Backup History" modal
   - Frees 70% of dashboard space for new admin functions

**Estimated Impact**: ~200 lines removed from admin_dashboard.html, UI becomes 40% cleaner

---

### Phase 2: User Management (Critical)
**Why**: Foundation for role-based access control, enables admin to onboard users

**Features**:
1. **User List** (Searchable, paginated)
   - Email, Full Name, Status (Active/Inactive), Admin?, Joined Date, Last Login
   - Quick action buttons: View Details, Toggle Admin, Deactivate

2. **User Detail View**
   - Profile: Email, Name, Join date, Last login
   - Activity: Cases reviewed, notes created, highlights added
   - Actions: Change admin status, activate/deactivate, delete
   - Confirmation dialogs for destructive actions

3. **Backend Requirements**:
   - `GET /api/admin/users` - List users (paginated, filterable)
   - `GET /api/admin/users/<id>` - User detail + stats
   - `PUT /api/admin/users/<id>` - Update status/admin flag
   - `DELETE /api/admin/users/<id>` - Delete user (with cascade)
   - All require `@login_required` + `check_admin()` verification

**Database Model Changes**: NONE (existing fields sufficient)

**Estimated Impact**: 
- Backend: 200 lines (4 routes)
- Frontend: 400 lines (list view + detail modal)
- Total: ~600 lines new code

---

### Phase 3: Admin Case Creation (High Value)
**Why**: Enables admins to populate case library without exam setup workflow

**Key Enhancement**: Add table support in answers & discussion
- **Problem**: Current case editor only supports plain text
- **Solution**: Use existing HTML editor + add table button (copy from edit-case.html)
- **Implementation**: Minimal—reuse existing rich text handling, extend to tables

**Features**:
1. **Case Creation Form** (Separate from edit-case modal)
   - Diagnosis (required)
   - Module selection (dropdown)
   - Body Part selection (dropdown)
   - Q&A Pairs (with table support)
   - Discussion section (with table support)
   - Images upload
   - Public/Private toggle

2. **UI Location**: New "Create Case" button in admin dashboard
   - Opens modal OR full-page editor (reuse edit-case.html)
   - On save, redirects back to admin dashboard with success toast

3. **Table Implementation**:
   - Add `<table>` button to rich text editors in answers & discussion
   - Insert pre-formatted HTML table template
   - Users can edit via WYSIWYG or raw HTML

4. **Backend Changes**:
   - Existing route `/api/case/create` already supports all features
   - NO code changes needed—just add frontend UI in admin dashboard
   - Leverage: `edit-case.html` already has full rich text handling

**Estimated Impact**:
- Backend: 0 lines (use existing route)
- Frontend: 300 lines (button + modal trigger)
- Total: ~300 lines

---

### Phase 4: Dashboard Overview Section (Quick Wins)
**Why**: Admin sees system health at a glance

**Widgets**:
1. **User Metrics**
   - Total users | Active users | Admins
   - Trend arrow (↑ increase, → stable, ↓ decrease)

2. **Case Metrics**
   - Total cases | Public cases | Private cases
   - Last created: [case name] [date]

3. **System Health**
   - Database size | Backups available | Last backup [time]
   - One-click "Create Backup" button

**Backend**: Extend `/api/admin/dashboard-stats`
- Returns: User count, case count, backup stats, revision stats

**Estimated Impact**: 200 lines (HTML + 1 API route)

---

### Phase 5: Placeholder Sections (For Future)
**Why**: Signal to users that more features are coming, structure for scaling

**Add to Dashboard**:
1. **Payments & Subscriptions** (Placeholder)
   - Single card: "Coming Soon - Manage subscription status and billing"
   - No functionality yet

2. **Pull Cases from FRCR Examiner** (Placeholder)
   - Single card: "Coming Soon - Import cases from examiner app"
   - No functionality yet

---

## ARCHITECTURE BENEFITS

### 1. Clean Separation of Concerns
```
Student Dashboard (dashboard.html)
  ├── Revision features (balanced revision, modules, cases)
  ├── My statistics (notes, highlights)
  └── Public case library

Admin Dashboard (admin_dashboard.html)
  ├── User management
  ├── Case management
  ├── System health
  ├── Backups (simplified)
  └── Settings & future features
```

### 2. Scalability
- Easy to add new admin sections (e.g., Reports, Analytics, Payments)
- Tab/card-based layout supports unlimited features
- Each section is independent (no layout conflicts)

### 3. User Experience
- Admins can perform all tasks without leaving admin dashboard
- No need to navigate to case editor, user list elsewhere
- Consistent color scheme (admin dashboard styling already done)

### 4. Access Control
- All routes protected by `check_admin()` function
- Template uses `{% if current_user.is_admin %}`
- No leakage of admin features to students

---

## DATA FLOW DIAGRAM

### Case Creation (Admin)
```
Admin Dashboard (admin_dashboard.html)
  → Click "Create Case" button
  → Opens modal OR redirects to edit-case.html with ?new=true&admin=true
  → Form submission → POST /api/case/create
  → Response → Redirect to admin dashboard with success toast
```

### User Management (Admin)
```
Admin Dashboard (admin_dashboard.html)
  → Click "User Management" tab
  → GET /api/admin/users → Render user list
  → Click user row → GET /api/admin/users/<id> → Show detail modal
  → Click "Make Admin" → PUT /api/admin/users/<id> → Success toast
```

---

## MIGRATION PATH

### Step 1: Simplify Backups (Lowest Risk)
- Remove bulk of admin_dashboard.html content
- Keep core backup functionality
- Estimated: 30 minutes, 0 functional risk

### Step 2: Add User Management (Medium Complexity)
- Add new routes to Flask app
- Build user list + modal components
- Estimated: 2 hours, medium complexity

### Step 3: Add Case Creation (Reuse Existing Code)
- Add "Create Case" button to admin dashboard
- Leverage existing edit-case.html and /api/case/create
- Estimated: 45 minutes, low risk

### Step 4: Dashboard Stats (Quick Win)
- Add overview cards with metrics
- Estimated: 30 minutes

### Step 5: Placeholder Sections
- Add stubbed cards for future features
- Estimated: 15 minutes

**Total Estimated Time**: 4-5 hours (mostly frontend)
**Production Risk**: Low (all changes additive, existing features untouched)

---

## SUGGESTED ADDITIONAL ADMIN FEATURES

### Short Term (Next Phase)
1. **Case Visibility Control**
   - Toggle cases between public/private
   - Bulk publish/unpublish
   - Rationale: Currently all cases are public once created

2. **Activity Audit Log**
   - Who created what case, when
   - Who accessed cases, when
   - Backup history
   - Rationale: Important for medical education compliance

3. **Export Reports**
   - User activity report (CSV)
   - Case library inventory
   - Revision statistics
   - Rationale: Admins may need metrics for stakeholders

### Medium Term (Future Phases)
1. **Role-Based Access Control**
   - Currently: Admin (all) vs Student (view only)
   - Future: Content Manager, Instructor, Student roles
   - Rationale: Supports scaling to multi-tenant institutions

2. **Case Approval Workflow**
   - Cases start as "draft"
   - Admin review before public
   - Comments/feedback on cases
   - Rationale: Quality control for case library

3. **Bulk Import**
   - Upload CSV of cases
   - Import from FRCR Examiner app (API)
   - Rationale: Speed up case library creation

4. **Student Progress Analytics**
   - Dashboard: Completion rates, module progress
   - Per-student: Detailed revision history
   - Rationale: Track learning effectiveness

---

## DESIGN DECISIONS & RATIONALE

| Decision | Why |
|----------|-----|
| **Simplify backups** | Backup is automatic; detailed management rarely needed |
| **Keep edit-case.html for case creation** | Reuse working code, consistent UX, faster implementation |
| **Add table support to answers/discussion** | Matches FRCR Examiner app capability, improves case quality |
| **Binary admin role (for now)** | Sufficient for MVP; future phases add granular roles |
| **User list + modal detail** | Better UX than separate page, consistent with case management |
| **Dashboard overview cards** | Quick health check, matches modern admin dashboards |
| **Placeholder sections** | Shows product roadmap, guides future development |

---

## ASSUMPTIONS & CONSTRAINTS

### Assumptions
1. ✅ Existing `/api/case/create` supports all case creation needs
2. ✅ `is_admin` field in User model is sufficient (no role enum needed)
3. ✅ Users will be managed by admin (no self-signup to admin)
4. ✅ Backup manager can be simplified without feature loss

### Constraints
1. **Time**: Admin dashboard should be built in 1 sprint (~4 hours)
2. **Data**: No sensitive user data exported (passwords excluded from backup)
3. **Access**: All admin features require is_admin=true
4. **Backwards Compatibility**: Case creation should work from both admin dashboard AND existing edit-case.html paths

---

## RISK ANALYSIS

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| User deletion cascades incorrectly | Low | High | Test thoroughly, add confirmation dialogs |
| Admin access bypass | Low | Critical | Code review all @login_required + check_admin() |
| Case creation breaks existing workflow | Low | Medium | Test both admin dashboard + edit-case.html paths |
| Backup functionality breaks | Low | High | Keep backup routes isolated, test separately |

---

## SUCCESS CRITERIA

✅ Admins can create cases with table support in answers/discussion
✅ Admins can manage users (list, view, promote, deactivate, delete)
✅ Admin dashboard is visually organized with clear sections
✅ Backup manager is simplified (70% less content)
✅ All changes are backward compatible
✅ No security vulnerabilities introduced
✅ Placeholder sections set up for future features

---

## NEXT STEPS

**IF APPROVED**:
1. Review this strategy document for feedback
2. Identify any changes to proposed approach
3. Proceed with phased implementation (Phase 1-5)
4. Test each phase before moving to next

**Questions for clarification**:
1. Should case creation be a modal or full-page redirect to edit-case.html?
2. Should user deletion be permanent or soft-delete (archive)?
3. Should we add role field (Admin, Content Manager, Instructor) now or in future?
4. Any other admin features to add in this sprint?

