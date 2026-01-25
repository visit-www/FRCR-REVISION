# FRCR Revision - User Roles & Workflows

## Quick Reference

| Role | Access Level | Can Manage Users | Can Manage Cases | Needs Approval |
|------|--------------|------------------|------------------|----------------|
| **Super Admin** | Full | ✅ All actions | ✅ Full | Never |
| **Admin** | High | ⚠️ With limits | ✅ Full | For sensitive actions |
| **Content Manager** | Medium | ❌ No | ✅ Create/Edit | N/A |
| **Student** | Basic | ❌ No | ❌ View only | N/A |

---

## 1. Role Definitions

### 🔴 Super Admin
The highest authority in the system. Only ONE superadmin exists.

**Capabilities:**
- All Admin capabilities
- Promote/demote ANY user without approval
- Delete ANY user (except self)
- Cancel pending approval requests
- View approval history
- Cannot be demoted or deleted by anyone

**Email:** `lotusheart2016@gmail.com`

---

### 🟠 Admin
Full system administrators with some restrictions.

**Capabilities:**
- Manage users (view, edit roles, subscriptions)
- Manage all cases
- Access backup/restore
- Moderate forum content
- Manage AJCC TNM data

**Restrictions (Requires Super Admin Approval):**
- Promoting any user to Admin
- Demoting another Admin
- Deleting another Admin or Content Manager

**Cannot:**
- Change their own role
- Delete themselves
- Modify Super Admin account

---

### 🔵 Content Manager
Content creators with case management focus.

**Capabilities:**
- Create new cases
- Edit existing cases
- Add questions/answers
- Upload images
- View dashboard analytics

**Restrictions:**
- Cannot access user management
- Cannot access backup/restore
- Cannot change user roles

---

### 🟢 Student
End users learning from the platform.

**Capabilities:**
- View cases (limited if FREE subscription)
- Create notes and highlights
- Participate in forum discussions
- Save study progress
- Delete own account (soft delete)

**Subscription Tiers:**
| Tier | Cases per Module | Features |
|------|-----------------|----------|
| FREE | 2 cases | Basic access |
| PAID | Unlimited | Full access |

---

## 2. Admin Approval Workflow

### When Approval is Required

An Admin needs Super Admin approval for:
1. **Promoting to Admin** - Any user → Admin
2. **Demoting Admin** - Admin → any lower role
3. **Deleting Admin** - Removing an Admin account
4. **Deleting Content Manager** - Removing a Content Manager

### Approval Flow

```
Admin requests sensitive action
         ↓
System checks for existing pending request
         ↓
┌─ Request exists ───────────────────┐    ┌─ No existing request ──────────────┐
│ Show "Already Pending" modal       │    │ Generate 8-char approval code      │
│ Options:                           │    │ Email sent to Super Admin          │
│   - Enter existing code            │    │ Show "Enter Code" modal            │
│   - Resend code (cancels old)      │    │                                    │
└────────────────────────────────────┘    └────────────────────────────────────┘
         ↓
Admin enters approval code
         ↓
┌─ Code valid ───────────────────────┐    ┌─ Code invalid/expired ─────────────┐
│ Action completed                   │    │ Show error message                 │
│ Code marked as used                │    │ Admin can retry or resend          │
└────────────────────────────────────┘    └────────────────────────────────────┘
```

### Super Admin Controls

Super Admin can:
- **View pending approvals**: `GET /api/admin/approvals/pending`
- **Cancel a request**: `POST /api/admin/approvals/{id}/cancel`
- **View history**: `GET /api/admin/approvals/history`

When Super Admin cancels a request:
- Approval code becomes invalid
- Admin cannot complete the action
- New request must be submitted

### Approval Code Details

| Property | Value |
|----------|-------|
| Format | 8 uppercase alphanumeric characters |
| Validity | 24 hours from generation |
| Usage | Single use only |
| Linked to | Specific action + requesting admin + target user |

---

## 3. Student Account Self-Service

### Account Deletion (Soft Delete)

Students can delete their own accounts:

**Location:** Profile → Account Settings → Delete My Account

**What happens:**
1. Account is **soft deleted** (marked as deleted, not removed)
2. User is logged out immediately
3. All subscriptions are **permanently lost**
4. Data is retained for **31 days** for recovery

**Data Retention:**
| Retained | NOT Retained |
|----------|--------------|
| Profile data | Active subscriptions |
| Notes & highlights | Subscription benefits |
| Case history | Promotional pricing |
| Forum posts (remain visible) | |

### Account Recovery

If a student tries to log in during the 31-day recovery period:

**Flow:**
1. Login attempt shows "Account Deactivated" screen
2. User clicks "Recover My Account"
3. Recovery code sent to email (8 chars, 15 min validity)
4. User enters code
5. User must set NEW password (old password cannot be reused)
6. Account restored with all data (except subscriptions)

**Security:**
- Recovery codes are single-use
- Rate-limited to prevent abuse
- IP and user-agent logged for auditing
- All previous sessions invalidated on recovery

### Permanent Deletion

After 31 days:
- Account is permanently deleted
- All personal data removed
- Forum posts remain (anonymized as "Deleted User")
- Email can be reused for new registration

---

## 4. Admin Dashboard Features

### User Management Tab
- View all users with search/filter
- Click user to view/edit details
- Change roles (with approval workflow)
- Change subscriptions
- Delete users (with confirmation/approval)

### Case Management Tab
- Link to `/cases` for full case list
- Create, edit, delete cases
- Manage questions and answers

### Forum Tab
- View flagged content
- Moderate discussions
- Remove inappropriate content

### Database Management Tab
- Export/import backups (Admin only, not Content Manager)
- View database status
- Manual backup triggers

### TNM Management Tab
- Link to AJCC TNM management
- Configure disease site mappings
- Fetch staging data from AJCC

### App Documents Tab
- View application documentation
- Quick reference for developers/admins

---

## 5. Role Change Matrix

| Actor | Target | To Student | To CM | To Admin | Delete |
|-------|--------|------------|-------|----------|--------|
| **Super Admin** | Student | ✅ | ✅ | ✅ | ✅ |
| **Super Admin** | Content Manager | ✅ | ✅ | ✅ | ✅ |
| **Super Admin** | Admin | ✅ | ✅ | ✅ | ✅ |
| **Super Admin** | Super Admin | ❌ | ❌ | ❌ | ❌ |
| **Admin** | Student | ✅ | ✅ | ⚠️ Approval | ✅ |
| **Admin** | Content Manager | ✅ | ✅ | ⚠️ Approval | ⚠️ Approval |
| **Admin** | Admin | ⚠️ Approval | ⚠️ Approval | N/A | ⚠️ Approval |
| **Admin** | Super Admin | ❌ | ❌ | ❌ | ❌ |
| **Admin** | Self | ❌ | ❌ | ❌ | ❌ |

**Legend:**
- ✅ Allowed without approval
- ⚠️ Requires Super Admin approval code
- ❌ Not allowed

---

## 6. Audit Logging

All sensitive actions are logged with:
- Timestamp
- Actor (who performed the action)
- Target (who was affected)
- Action type
- Approval status (if applicable)
- IP address (for recovery attempts)

Log format:
```
[AUDIT] PENDING: Admin user@example.com requested to promote Student John Doe to Admin
[AUDIT] APPROVED: Admin user@example.com used approval code to promote Student John Doe to Admin
[AUDIT] CANCELLED: Super Admin cancelled approval request for action: promote to Admin
```

---

## 7. Security Guardrails

### Non-Negotiable Rules

1. **Super Admin Protection**
   - Cannot be demoted
   - Cannot be deleted
   - Role cannot be changed

2. **Self-Protection**
   - Users cannot change their own role
   - Users cannot delete themselves (except Student soft-delete)

3. **Email Delivery Requirement**
   - If approval email fails to send, action is **blocked**
   - Error message shown to admin
   - No action proceeds without email confirmation

4. **Single-Use Codes**
   - Each approval code can only be used once
   - Resending a code invalidates the previous one
   - Super Admin can cancel pending codes

---

## 8. Quick API Reference

### User Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/users` | GET | List all users |
| `/api/admin/users/{id}` | GET | Get user details |
| `/api/admin/users/{id}/role` | PUT | Change user role |
| `/api/admin/users/{id}` | DELETE | Delete user |

### Approval Management (Super Admin Only)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/approvals/pending` | GET | List pending approvals |
| `/api/admin/approvals/{id}/cancel` | POST | Cancel a pending approval |
| `/api/admin/approvals/history` | GET | View approval history |

### Account Self-Service (Students)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/account/soft-delete` | POST | Delete own account |
| `/auth/account/request-recovery` | POST | Request recovery code |
| `/auth/account/verify-recovery` | POST | Verify recovery code |
| `/auth/account/complete-recovery` | POST | Set new password |

---

*Last updated: January 2026*
