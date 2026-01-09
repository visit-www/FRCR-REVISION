# Admin System: Architecture Overview

## Role Hierarchy & Capabilities Matrix

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          ROLE HIERARCHY                                 │
└─────────────────────────────────────────────────────────────────────────┘

    ADMIN (1-3 users)
    ├─ Full system control
    ├─ All Student capabilities
    ├─ User management
    ├─ Case approval
    ├─ Export reports
    ├─ Backup/restore
    └─ View audit logs
         ↑ can promote
         │
    CONTENT MANAGER (1-15+ users)
    ├─ Create/edit cases
    ├─ Toggle case visibility (publish/hide)
    ├─ All Student (PAID) capabilities
    └─ View audit logs of own cases
         ↑ can promote
         │
    STUDENT (many users)
    ├─ View published cases
    ├─ Create notes & highlights
    ├─ See performance report
    ├─ Upgrade to paid (2 → unlimited cases/module)
    └─ Downgrade subscription
```

---

## Subscription Model

```
┌──────────────────────────────────────────────────────────────────┐
│                     SUBSCRIPTION LOGIC                            │
└──────────────────────────────────────────────────────────────────┘

FREE MEMBER
├─ Max 2 cases per module
├─ Can create notes (but for free cases only)
├─ Can highlight (for free cases only)
├─ Can upgrade to paid anytime
└─ Sees upgrade prompts after 2nd case

PAID MEMBER
├─ Unlimited case access
├─ Full notes & highlight capability
├─ Can view performance analytics
├─ Can cancel anytime (→ soft downgrade)
└─ PaymentStatus: ACTIVE / PAST_DUE / CANCELED

ADMINS & CONTENT MANAGERS
├─ NO subscription restrictions (always full access)
├─ Never hit "2 case" limits
└─ Can manage other users' subscription status
```

---

## Case Lifecycle

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         CASE WORKFLOW                                     │
└──────────────────────────────────────────────────────────────────────────┘

Content Manager Creates Case
           ↓ (status = DRAFT)
    [Not visible to students]
           ↓
  Admin Reviews Case
           ↓
    ┌─────┴─────┐
    │           │
APPROVED    REJECTED
    │           │
    ↓           ↓
PUBLISHED    DRAFT + Notes
    ↓           ↓
Visible to   [Revision needed]
Students     [Back to CM]
    ↓
Content Manager can toggle:
PUBLISHED ↔ PRIVATE (hidden)
    ↓
Case remains in database
(can be re-published)
    
Final state: ARCHIVED
(Old cases, completely hidden)
```

---

## Database Schema Changes

```
┌─────────────────────────────────────────────────────────────────┐
│ USER Model Changes                                              │
├─────────────────────────────────────────────────────────────────┤
│ id                     (existing)                               │
│ email                  (existing)                               │
│ full_name              (existing)                               │
│ is_active              (existing)                               │
│ ────────────────────────────────────────────────────────────    │
│ + role                 NEW → "student", "content_manager", "admin" │
│ + subscription_status  NEW → "free", "paid", "canceled"        │
│ + payment_status       NEW → "no_subscription", "active", etc.  │
│ + subscription_start_date    (NEW)                             │
│ + subscription_end_date      (NEW)                             │
│ + is_deleted           NEW → soft delete flag                   │
│ + deleted_at           NEW → timestamp                          │
│ + deleted_by_user_id   NEW → who deleted this user             │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ CASE Model Changes                                               │
├──────────────────────────────────────────────────────────────────┤
│ id                     (existing)                                │
│ diagnosis              (existing)                                │
│ questions, answers     (existing)                                │
│ is_public              (existing, deprecated in favor of status) │
│ ─────────────────────────────────────────────────────────────    │
│ + status               NEW → "draft", "pending_review",         │
│                             "published", "private", "archived"  │
│ + created_by_user_id   NEW → who created this case             │
│ + approved_by_user_id  NEW → who approved this case            │
│ + approved_at          NEW → when was it approved              │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ NEW Models                                                       │
├──────────────────────────────────────────────────────────────────┤
│ CaseAuditLog                                                     │
│  ├─ Tracks: who created, edited, approved, deleted cases       │
│  └─ Used for audit trails & accountability                     │
│                                                                  │
│ CaseViewLog                                                      │
│  ├─ Tracks: which users viewed which cases when                │
│  └─ Used for analytics & randomization                         │
│                                                                  │
│ CaseApprovalQueue                                               │
│  ├─ Holds cases pending admin approval                         │
│  └─ Used for approval workflow                                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## Permission Matrix

```
┌────────────────────────────────────────────────────────────────────┐
│ Action                 │ Student │ Content Manager │ Admin         │
├────────────────────────────────────────────────────────────────────┤
│ View published cases   │ ✓ (limit) │ ✓            │ ✓             │
│ Create notes           │ ✓ (paid)  │ ✓            │ ✓             │
│ Create case            │ ✗         │ ✓ (→DRAFT)   │ ✓ (→DRAFT)    │
│ Edit own case          │ ✗         │ ✓            │ ✓ (any case)  │
│ Approve case           │ ✗         │ ✗            │ ✓             │
│ Publish/unpublish      │ ✗         │ ✓ (own)      │ ✓ (any)       │
│ Delete case            │ ✗         │ ✗            │ ✓             │
│ Manage users           │ ✗         │ ✗            │ ✓             │
│ Change user role       │ ✗         │ ✗            │ ✓             │
│ Change subscription    │ ✗ (self)  │ ✗            │ ✓             │
│ Export reports         │ ✗         │ ✗            │ ✓             │
│ View audit logs        │ ✗         │ ✓ (own)      │ ✓ (all)       │
│ Backup database        │ ✗         │ ✗            │ ✓             │
└────────────────────────────────────────────────────────────────────┘

Legend:
  ✓ = Can do
  ✓ (limit) = Can do with restrictions (e.g., 2 cases/module if free)
  ✓ (own) = Can do only on own content
  ✗ = Cannot do
```

---

## Admin Dashboard: New Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ADMIN DASHBOARD                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ [Overview] [Users] [Cases] [Approval] [Reports] [Backups] [Settings]  │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ OVERVIEW TAB                                                            │
│ ┌──────────────────────────────────────────────────────────────────┐   │
│ │ Quick Stats                                                      │   │
│ │ • Users: 45 total, 42 active, 3 admins, 8 content managers     │   │
│ │ • Cases: 120 total, 95 published, 15 draft, 10 private         │   │
│ │ • Subscriptions: 25 paid, 20 free                              │   │
│ │ • Backups: 5 available, 250MB storage, Last: 2 hours ago       │   │
│ └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ USERS TAB                                                               │
│ ┌──────────────────────────────────────────────────────────────────┐   │
│ │ [Search] [Filter by Role] [Add User]                            │   │
│ │                                                                  │   │
│ │ User List (searchable)                                          │   │
│ │ Email │ Name │ Role │ Subscription │ Status │ Joined │ Actions │   │
│ │ ────────────────────────────────────────────────────────────── │   │
│ │ john@  John   Student  PAID        Active  Jan 5    [View]     │   │
│ │ jane@  Jane   CM       (none)      Active  Jan 2    [Promote]  │   │
│ │ admin@ Admin  Admin    (none)      Active  Dec 1    [View]     │   │
│ │                                                                  │   │
│ └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│ User Detail Modal (on click)                                           │
│ ┌──────────────────────────────────────────────────────────────────┐   │
│ │ Email: john@example.com                                          │   │
│ │ Name: John Smith                                                 │   │
│ │ Role: Student → [Promote to Content Manager]                   │   │
│ │ Subscription: PAID (expires Dec 25, 2026)                       │   │
│ │ Status: Active → [Deactivate]                                   │   │
│ │ Cases Reviewed: 25                                              │   │
│ │ Notes Created: 50                                               │   │
│ │ Last Login: 2 hours ago                                         │   │
│ │ [Delete User] → (soft delete or permanent)                      │   │
│ └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ CASES TAB                                                               │
│ ┌──────────────────────────────────────────────────────────────────┐   │
│ │ [Create New Case] [Bulk Import CSV] [Import from FRCR Examiner] │   │
│ │ [Filter by Status] [Search]                                      │   │
│ │                                                                  │   │
│ │ All Cases (filterable)                                          │   │
│ │ Diagnosis │ Status │ Module │ Created By │ Approved │ Actions  │   │
│ │ ──────────────────────────────────────────────────────────────  │   │
│ │ Chest X-ray PUBLISHED Cardio Jane Admin (CM) [Edit] [Hide]      │   │
│ │ Brain MRI  DRAFT    CNS    John Admin     [Edit] [Approve]      │   │
│ │ Knee XR    PRIVATE  MSK    Jane Admin     [Edit] [Publish]      │   │
│ │                                                                  │   │
│ └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ APPROVAL QUEUE TAB                                                      │
│ ┌──────────────────────────────────────────────────────────────────┐   │
│ │ Pending Review: 3 cases                                          │   │
│ │                                                                  │   │
│ │ Case │ Created By │ Submitted │ Status │ Action                │   │
│ │ ───────────────────────────────────────────────────────────────  │   │
│ │ Chest John Admin (CM)  1 hr ago PENDING [Review] [Approve]      │   │
│ │ Brain Jane Admin (CM)  3 hrs ago PENDING [Review] [Approve]     │   │
│ │                                                                  │   │
│ │ Review Modal                                                    │   │
│ │ Case: [Case name and details]                                   │   │
│ │ Created by: [Creator name]                                      │   │
│ │ Admin Notes: [Textarea]                                         │   │
│ │ [Approve] [Reject & Send Back]                                  │   │
│ │                                                                  │   │
│ └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ REPORTS TAB                                                             │
│ ┌──────────────────────────────────────────────────────────────────┐   │
│ │ [Export Users Report (CSV)]                                      │   │
│ │ [Export Cases Report (CSV)]                                      │   │
│ │ [Export Analytics Report (CSV)]                                  │   │
│ │                                                                  │   │
│ │ Analytics Dashboard                                             │   │
│ │ • Most viewed modules: [Cardio: 450], [CNS: 320], ...          │   │
│ │ • Most reviewed cases: [Chest X-ray: 45], [Brain MRI: 38], ... │   │
│ │ • Content created by: [John Admin: 25 cases], [Jane: 18], ...   │   │
│ │ • User growth: [Chart]                                          │   │
│ │                                                                  │   │
│ └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ BACKUPS TAB (SIMPLIFIED)                                                │
│ ┌──────────────────────────────────────────────────────────────────┐   │
│ │ Quick Stats                                                      │   │
│ │ • Total Backups: 12                                             │   │
│ │ • Storage Used: 250 MB                                          │   │
│ │ • Last Backup: 2 hours ago                                      │   │
│ │                                                                  │   │
│ │ [Create Manual Backup]                                          │   │
│ │                                                                  │   │
│ │ Recent Backups                                                  │   │
│ │ Date │ Size │ Backup By │ Type │ Status │ Action               │   │
│ │ ────────────────────────────────────────────────────────────── │   │
│ │ Today Auto  System    Auto   ✓      [Download]                 │   │
│ │ Yesterday Manual (2hr ago) Manual ✓      [Download] [Restore]  │   │
│ │                                                                  │   │
│ └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ SETTINGS TAB (PLACEHOLDER)                                              │
│ ┌──────────────────────────────────────────────────────────────────┐   │
│ │ Coming Soon...                                                   │   │
│ │                                                                  │   │
│ │ • Payments & Subscription Management                            │   │
│ │ • Email Configuration                                           │   │
│ │ • System Settings                                               │   │
│ │                                                                  │   │
│ └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Timeline

```
SPRINT 1 (Week 1)
└─ Phase 1: Database Schema (4h)
   └─ Add role, subscription, soft delete fields
   └─ Outcome: Database ready
└─ Phase 2: User Management (6h)
   └─ List users, promote/demote, manage subscription
   └─ Outcome: Admins can manage users

SPRINT 2 (Week 2)
└─ Phase 3: Case Approval (6-7h)
   └─ Draft → Review → Published workflow
   └─ Outcome: Content managers create cases, admins approve
└─ Phase 4: Case Creation (3-4h)
   └─ Add "Create Case" button to admin dashboard
   └─ Outcome: Admins can create cases directly
└─ Phase 5: Visibility Control (2-3h)
   └─ Toggle case public/hidden
   └─ Outcome: Content managers can manage case visibility

SPRINT 3 (Week 3)
└─ Phase 6: Subscription Limits (3-4h)
   └─ Enforce 2 cases/module for free users
   └─ Outcome: Free users see upgrade prompts
└─ Phase 7: Reports (4-5h)
   └─ Export user, case, analytics reports
   └─ Outcome: Admins can generate CSV reports
└─ Phase 9: Dashboard UI (3-4h)
   └─ Refactor dashboard with tabs
   └─ Outcome: Dashboard is organized and intuitive

SPRINT 4 (Week 4)
└─ Phase 8: Bulk Import (5-6h)
   └─ CSV upload + FRCR Examiner API import
   └─ Outcome: Admins can import cases in bulk
└─ Testing & Polish (2-3h)
   └─ End-to-end testing, bug fixes
   └─ Outcome: Production-ready

TOTAL TIME: ~37-42 hours
DURATION: 4 weeks
```

---

## Key Assumptions

✅ Current `/api/case/create` endpoint supports all needed fields  
✅ Case approval workflow should be required (DRAFT → APPROVED → PUBLISHED)  
✅ Free users limited to 2 cases per module (enforced on backend)  
✅ Soft delete is default (permanent delete requires explicit `?permanent=true`)  
✅ Content managers are trusted to create good cases (admins review before publish)  
✅ No existing user data needs role assignment (all default to STUDENT)  

---

## Questions to Clarify

1. Should content managers also be able to **edit cases created by other content managers**? (Currently: only their own)
2. Should **deleted users' cases be deleted too**, or preserved with `created_by=null`?
3. Should free users see the **number of cases remaining** in a module? (e.g., "1 of 2 remaining")
4. Should **admins be able to soft-delete their own account** or only delete others?
5. For **CSV import**, what format? (Recommend: diagnosis, module, body_part, questions, answers, discussion, as CSV)

