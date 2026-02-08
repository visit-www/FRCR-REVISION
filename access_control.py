"""
Permission and Access Control Utilities for Admin System
Provides decorators and helper functions for role-based access control
"""

from functools import wraps
from flask import abort, jsonify
from flask_login import current_user
from models import UserRole, SubscriptionStatus, PaymentStatus, CaseStatus


# ==================== ROLE-BASED DECORATORS ====================

def require_role(*roles):
    """
    Decorator to check if user has one of the required roles.
    Usage: @require_role(UserRole.ADMIN, UserRole.CONTENT_MANAGER)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)  # Unauthorized
            if current_user.role not in roles:
                abort(403)  # Forbidden
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_admin(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        
        # Ensure user role is fresh from database
        try:
            from models import db
            # Expire and refresh to get latest role
            db.session.expire(current_user)
            db.session.refresh(current_user)
        except Exception as e:
            print(f"[AUTH] Warning: Could not refresh user for admin check: {e}")
            pass  # Continue even if refresh fails
        
        # Check role - ensure it's a UserRole enum
        user_role = current_user.role
        
        # Debug logging (only for admin endpoints to reduce noise)
        from flask import request
        if request.path.startswith('/api/admin'):
            print(f"[AUTH] Admin check for {current_user.email}: role={user_role}, type={type(user_role).__name__}")
        
        # Handle string role (shouldn't happen but be defensive)
        if isinstance(user_role, str):
            try:
                user_role = UserRole(user_role.lower())
                # Update the user object with the enum
                current_user.role = user_role
                from models import db
                db.session.commit()
            except (ValueError, KeyError) as e:
                print(f"[AUTH] Error: User {current_user.email} has invalid role string '{user_role}': {e}")
                abort(403)
        
        # Compare with enum - direct comparison should work
        if not isinstance(user_role, UserRole):
            print(f"[AUTH] Error: User {current_user.email} role is not UserRole enum: {type(user_role).__name__}")
            abort(403)
        
        if user_role != UserRole.ADMIN:
            # Log for debugging
            print(f"[AUTH] Access denied: User {current_user.email} has role {user_role.value if hasattr(user_role, 'value') else user_role}, expected ADMIN")
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def require_content_manager(f):
    """Decorator to require content manager or admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if current_user.role not in [UserRole.CONTENT_MANAGER, UserRole.ADMIN]:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def require_student(f):
    """Decorator to require student or higher (any authenticated user)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        return f(*args, **kwargs)
    return decorated_function


# ==================== PERMISSION CHECK FUNCTIONS ====================

def is_admin(user=None):
    """Check if user is admin"""
    user = user or current_user
    return user.is_authenticated and user.role == UserRole.ADMIN


def is_content_manager(user=None):
    """Check if user is content manager or admin"""
    user = user or current_user
    return user.is_authenticated and user.role in [UserRole.CONTENT_MANAGER, UserRole.ADMIN]


def is_student(user=None):
    """Check if user is student"""
    user = user or current_user
    return user.is_authenticated and user.role == UserRole.STUDENT


def is_admin_or_content_manager(user=None):
    """Alias for is_content_manager"""
    return is_content_manager(user)


# ==================== CASE ACCESS CONTROL ====================

def has_case_view_access(case, user=None):
    """
    Check if user can view a case.
    Rules:
    - Admin/Content Manager: always have access to all cases
    - Students: can only view public cases (is_public=True)
    - Free users: limited to 2 cases per module
    """
    user = user or current_user
    
    if not user.is_authenticated:
        return False
    
    # Admin and Content Managers always have access
    if user.role in [UserRole.ADMIN, UserRole.CONTENT_MANAGER]:
        return True
    
    # Case creators can always view their own submissions
    if hasattr(case, 'created_by_user_id') and case.created_by_user_id and case.created_by_user_id == user.id:
        return True

    # Students: only public cases visible (use is_public field, not status)
    # The system uses is_public=True to mark cases visible to students
    if not case.is_public:
        return False
    
    # Check subscription limits for free users
    if user.subscription_status == SubscriptionStatus.FREE:
        from models import CaseViewLog, Case as CaseModel
        # Count cases viewed in this module by this user
        viewed_count = CaseViewLog.query.join(CaseModel).filter(
            CaseViewLog.user_id == user.id,
            CaseModel.module == case.module
        ).distinct(CaseModel.id).count()
        
        if viewed_count >= 2:  # Max 2 per module for free users
            return False
    
    return True


def has_case_edit_permission(case, user=None):
    """
    Check if user can edit a case.
    Rules:
    - Admin: can edit any case
    - Content Manager: can edit cases they created
    - Others: cannot edit
    """
    user = user or current_user
    
    if not user.is_authenticated:
        return False
    
    # Admin can edit any case
    if user.role == UserRole.ADMIN:
        return True
    
    # Content Manager can edit cases they created
    if user.role == UserRole.CONTENT_MANAGER:
        return case.created_by_user_id == user.id

    # Students can edit their own DRAFT cases (Suggest a Case feature)
    if user.role == UserRole.STUDENT:
        from models import CaseStatus
        return (case.created_by_user_id == user.id and case.status == CaseStatus.DRAFT)

    return False


def has_case_delete_permission(case, user=None):
    """
    Check if user can delete a case.
    Rules:
    - Admin: can delete any case
    - Content Manager: cannot delete (only admin)
    """
    user = user or current_user
    
    if not user.is_authenticated:
        return False
    
    # Only admin can delete
    return user.role == UserRole.ADMIN


def has_case_approval_permission(case, user=None):
    """
    Check if user can approve/review cases.
    Rules:
    - Admin: can approve/reject
    - Others: cannot
    """
    user = user or current_user
    
    if not user.is_authenticated:
        return False
    
    return user.role == UserRole.ADMIN


def has_case_visibility_permission(case, user=None):
    """
    Check if user can toggle case visibility (publish/hide).
    Rules:
    - Admin: can toggle any case
    - Content Manager: can toggle cases they created
    - Others: cannot toggle
    """
    user = user or current_user
    
    if not user.is_authenticated:
        return False
    
    # Admin can toggle any case
    if user.role == UserRole.ADMIN:
        return True
    
    # Content Manager can toggle cases they created
    if user.role == UserRole.CONTENT_MANAGER:
        return case.created_by_user_id == user.id
    
    return False


# ==================== CASE LIMIT HELPERS ====================

def get_cases_viewed_in_module(user, module):
    """Get count of distinct cases viewed by user in a module"""
    from models import CaseViewLog, Case as CaseModel
    
    if not user.is_authenticated:
        return 0
    
    return CaseViewLog.query.join(CaseModel).filter(
        CaseViewLog.user_id == user.id,
        CaseModel.module == module
    ).distinct(CaseModel.id).count()


def get_remaining_cases_for_module(user, module):
    """Get remaining cases user can view in free tier (2 - already viewed)"""
    if user.subscription_status != SubscriptionStatus.FREE:
        return -1  # Unlimited
    
    viewed = get_cases_viewed_in_module(user, module)
    return max(0, 2 - viewed)


def can_view_more_in_module(user, module):
    """Check if free user can view more cases in this module"""
    if user.subscription_status != SubscriptionStatus.FREE:
        return True
    
    viewed = get_cases_viewed_in_module(user, module)
    return viewed < 2


# ==================== USER MANAGEMENT PERMISSIONS ====================

def can_manage_users(user=None):
    """Check if user can manage other users"""
    user = user or current_user
    return user.is_authenticated and user.role == UserRole.ADMIN


def can_promote_user(user=None):
    """Check if user can promote others to higher roles"""
    user = user or current_user
    return user.is_authenticated and user.role == UserRole.ADMIN


def can_delete_user(user=None):
    """Check if user can delete other users"""
    user = user or current_user
    return user.is_authenticated and user.role == UserRole.ADMIN


def can_change_subscription(user=None):
    """Check if user can change subscription status"""
    user = user or current_user
    return user.is_authenticated and user.role == UserRole.ADMIN


# ==================== EXPORT & REPORTING ====================

def can_export_reports(user=None):
    """Check if user can export reports"""
    user = user or current_user
    return user.is_authenticated and user.role == UserRole.ADMIN


# ==================== AUDIT LOGGING ====================

def log_case_audit(case_id, user_id, action, changes=None, notes=None):
    """Create audit log entry for case action"""
    from models import db, CaseAuditLog
    
    audit = CaseAuditLog(
        case_id=case_id,
        user_id=user_id,
        action=action,
        changes=changes,
        notes=notes
    )
    db.session.add(audit)
    db.session.commit()
    return audit


def log_case_view(case_id, user_id, time_spent_seconds=None):
    """Log case view for analytics"""
    from models import db, CaseViewLog
    
    view = CaseViewLog(
        case_id=case_id,
        user_id=user_id,
        time_spent_seconds=time_spent_seconds
    )
    db.session.add(view)
    db.session.commit()
    return view


# ==================== USER DELETE HELPERS ====================

def delete_user_completely(target_user):
    """
    Permanently delete a user and clean up related data sensibly.
    
    DELETES (private user data):
    - CandidateNote (private notes)
    - TextHighlight (private highlights)  
    - RevisionSession (revision tracking)
    - RevisionHistory (revision history)
    - CaseViewLog (view analytics)
    - ForumMessageVote (user's votes)
    - ForumMessageFlag (user's flags - as flagger)
    
    PRESERVES (public/shared content):
    - ForumMessage (forum comments stay, but user_id set to NULL)
    - Forum message images (preserved with the message)
    - Profile picture URL (just a string, no cleanup needed)
    
    NULLIFIES (case-related references for admin/content managers):
    - Case.created_by_user_id -> NULL
    - Case.approved_by_user_id -> NULL
    - CaseAuditLog.user_id -> NULL (preserve audit trail)
    - CaseApprovalQueue.submitted_by_user_id -> NULL
    - ImportedCaseStaging.*_user_id -> NULL
    - AiDiagnosisCache.first_user_id -> NULL
    
    Returns dict with cleanup stats.
    """
    from models import (
        db, CandidateNote, TextHighlight, RevisionSession, RevisionHistory,
        CaseViewLog, ForumMessage, ForumMessageVote, ForumMessageFlag,
        Case, CaseAuditLog, CaseApprovalQueue, ImportedCaseStaging, AiDiagnosisCache
    )
    
    user_id = target_user.id
    stats = {
        'notes_deleted': 0,
        'highlights_deleted': 0,
        'revision_sessions_deleted': 0,
        'revision_history_deleted': 0,
        'view_logs_deleted': 0,
        'votes_deleted': 0,
        'flags_deleted': 0,
        'forum_messages_anonymized': 0,
        'cases_updated': 0,
        'audit_logs_updated': 0,
    }
    
    try:
        # ===== DELETE PRIVATE DATA =====
        
        # Delete candidate notes (private)
        stats['notes_deleted'] = CandidateNote.query.filter_by(user_id=user_id).delete()
        
        # Delete text highlights (private)
        stats['highlights_deleted'] = TextHighlight.query.filter_by(user_id=user_id).delete()
        
        # Delete revision sessions (private)
        stats['revision_sessions_deleted'] = RevisionSession.query.filter_by(user_id=user_id).delete()
        
        # Delete revision history (private)
        stats['revision_history_deleted'] = RevisionHistory.query.filter_by(user_id=user_id).delete()
        
        # Delete case view logs (analytics, not critical)
        stats['view_logs_deleted'] = CaseViewLog.query.filter_by(user_id=user_id).delete()
        
        # Delete forum votes (user's votes on messages)
        stats['votes_deleted'] = ForumMessageVote.query.filter_by(user_id=user_id).delete()
        
        # Delete forum flags (where user was the flagger)
        stats['flags_deleted'] = ForumMessageFlag.query.filter_by(user_id=user_id).delete()
        
        # ===== ANONYMIZE FORUM MESSAGES (preserve content, remove author link) =====
        stats['forum_messages_anonymized'] = ForumMessage.query.filter_by(user_id=user_id).update(
            {'user_id': None}, synchronize_session=False
        )
        
        # ===== NULLIFY CASE REFERENCES (preserve cases, remove author link) =====
        
        # Cases created by this user
        cases_created = Case.query.filter_by(created_by_user_id=user_id).update(
            {'created_by_user_id': None}, synchronize_session=False
        )
        
        # Cases approved by this user
        cases_approved = Case.query.filter_by(approved_by_user_id=user_id).update(
            {'approved_by_user_id': None}, synchronize_session=False
        )
        stats['cases_updated'] = cases_created + cases_approved
        
        # Audit logs (preserve trail, remove user link)
        stats['audit_logs_updated'] = CaseAuditLog.query.filter_by(user_id=user_id).update(
            {'user_id': None}, synchronize_session=False
        )
        
        # Approval queue
        CaseApprovalQueue.query.filter_by(submitted_by_user_id=user_id).update(
            {'submitted_by_user_id': None}, synchronize_session=False
        )
        
        # Imported case staging
        ImportedCaseStaging.query.filter_by(enriched_by_user_id=user_id).update(
            {'enriched_by_user_id': None}, synchronize_session=False
        )
        ImportedCaseStaging.query.filter_by(approved_by_user_id=user_id).update(
            {'approved_by_user_id': None}, synchronize_session=False
        )
        
        # AI diagnosis cache
        AiDiagnosisCache.query.filter_by(first_user_id=user_id).update(
            {'first_user_id': None}, synchronize_session=False
        )
        
        # Flag resolution references
        ForumMessageFlag.query.filter_by(resolved_by_user_id=user_id).update(
            {'resolved_by_user_id': None}, synchronize_session=False
        )
        
        # ===== DELETE THE USER =====
        db.session.delete(target_user)
        db.session.commit()
        
        return True, stats
        
    except Exception as e:
        db.session.rollback()
        return False, str(e)


def can_delete_user(target_user, deleting_user=None):
    """
    Check if user can delete another user.
    Only admins can delete users.
    """
    deleting_user = deleting_user or current_user
    
    if not deleting_user.is_authenticated or deleting_user.role != UserRole.ADMIN:
        return False, "Only admins can delete users"
    
    if deleting_user.id == target_user.id:
        return False, "Cannot delete your own account. Use another admin account."
    
    return True, None


# ==================== SUBSCRIPTION HELPERS ====================

def upgrade_to_paid(user, subscription_end_date=None):
    """Upgrade user to paid subscription"""
    from models import db
    from datetime import datetime
    
    user.subscription_status = SubscriptionStatus.PAID
    user.payment_status = PaymentStatus.ACTIVE
    user.subscription_start_date = datetime.utcnow()
    user.subscription_end_date = subscription_end_date
    db.session.commit()


def downgrade_to_free(user):
    """Downgrade user to free subscription"""
    from models import db
    from datetime import datetime
    
    user.subscription_status = SubscriptionStatus.FREE
    user.payment_status = PaymentStatus.CANCELED
    user.subscription_end_date = datetime.utcnow()
    db.session.commit()


def cancel_subscription(user):
    """Cancel user's subscription (downgrade to free)"""
    downgrade_to_free(user)
