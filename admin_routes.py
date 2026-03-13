"""
Admin Routes - User Management & Case Management API Endpoints
Provides CRUD operations for user management and case management with role-based access control
"""

from flask import Blueprint, request, jsonify, render_template_string, render_template
from flask_login import login_required, current_user
from models import db, User, UserRole, SubscriptionStatus, CaseAuditLog, Case
from access_control import require_admin, require_role, delete_user_completely, can_delete_user, upgrade_to_paid, downgrade_to_free
from datetime import datetime
from sqlalchemy import or_, and_
import logging
import os
import json
import markdown

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')
logger = logging.getLogger(__name__)


# ============================================================================
# USER LIST & DETAIL ENDPOINTS
# ============================================================================

@admin_bp.route('/users', methods=['GET'])
@require_admin
def list_users():
    """
    Get paginated list of users with optional filtering and search
    
    Query Parameters:
    - page: int (default 1)
    - per_page: int (default 20)
    - search: str (email or full_name)
    - role: str (student, content_manager, admin)
    - subscription: str (free, paid, canceled)
    - include_deleted: bool (default false)
    
    Returns: { users: [], total: int, pages: int }
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '', type=str)
        role_filter = request.args.get('role', '', type=str)
        subscription_filter = request.args.get('subscription', '', type=str)
        include_deleted = request.args.get('include_deleted', 'false', type=str).lower() == 'true'
        
        # Validate pagination
        per_page = min(per_page, 100)  # Max 100 per page
        if page < 1:
            page = 1
        
        # Build query
        query = User.query
        
        # Search by email or name
        if search:
            query = query.filter(or_(
                User.email.ilike(f'%{search}%'),
                User.full_name.ilike(f'%{search}%')
            ))
        
        # Filter by role
        if role_filter:
            try:
                # Convert string to UserRole enum
                role_enum = UserRole(role_filter)
                query = query.filter(User.role == role_enum)
            except ValueError:
                # Invalid role value, ignore filter
                pass
        
        # Filter by subscription
        if subscription_filter:
            try:
                # Convert string to SubscriptionStatus enum
                subscription_enum = SubscriptionStatus(subscription_filter)
                query = query.filter(User.subscription_status == subscription_enum)
            except ValueError:
                # Invalid subscription value, ignore filter
                pass
        
        # Paginate
        pagination = query.paginate(page=page, per_page=per_page)
        
        # Build response
        users_data = []
        for user in pagination.items:
            users_data.append({
                'id': user.id,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role.value if user.role else None,
                'is_superadmin': user.is_superadmin,
                'subscription_status': user.subscription_status.value if user.subscription_status else None,
                'payment_status': user.payment_status.value if user.payment_status else None,
                'is_active': user.is_active,
                'is_deleted': user.is_deleted,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'last_login': user.last_login.isoformat() if user.last_login else None
            })
        
        return jsonify({
            'users': users_data,
            'total': pagination.total,
            'pages': pagination.pages,
            'page': page,
            'per_page': per_page
        }), 200
    
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@require_admin
def get_user_detail(user_id):
    """
    Get detailed information about a specific user including stats
    
    Returns: User object with all fields + stats
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get stats
        from models import Case, CaseViewLog
        cases_created = Case.query.filter_by(created_by_user_id=user_id).count()
        cases_viewed = CaseViewLog.query.filter_by(user_id=user_id).count()
        
        return jsonify({
            'id': user.id,
            'email': user.email,
            'full_name': user.full_name,
            'role': user.role.value if user.role else None,
            'is_superadmin': user.is_superadmin,  # Special superadmin flag
            'subscription_status': user.subscription_status.value if user.subscription_status else None,
            'payment_status': user.payment_status.value if user.payment_status else None,
            'is_active': user.is_active,
            'is_admin': user.is_admin,  # Legacy field
            'is_deleted': user.is_deleted,
            'deleted_at': user.deleted_at.isoformat() if user.deleted_at else None,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'subscription_start_date': user.subscription_start_date.isoformat() if user.subscription_start_date else None,
            'subscription_end_date': user.subscription_end_date.isoformat() if user.subscription_end_date else None,
            'profile_picture': user.profile_picture,
            'recovery_token': user.recovery_token,
            'recovery_token_expires': user.recovery_token_expires.isoformat() if user.recovery_token_expires else None,
            'stats': {
                'cases_created': cases_created,
                'cases_viewed': cases_viewed
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting user detail: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# USER MODIFICATION ENDPOINTS
# ============================================================================

@admin_bp.route('/users/<int:user_id>/role', methods=['PUT'])
@require_admin
def update_user_role(user_id):
    """
    Change a user's role (STUDENT, CONTENT_MANAGER, ADMIN)
    
    Body: { "role": "content_manager", "approval_code": "ABCD1234" (optional) }
    
    Approval code required for non-superadmins when:
    - Promoting anyone to ADMIN
    - Promoting to CONTENT_MANAGER
    - Changing any ADMIN's role
    """
    from models import AdminApprovalCode
    from auth import send_admin_approval_email, generate_approval_code
    from datetime import timedelta
    
    try:
        # Get target user
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if trying to change own role
        if user.id == current_user.id:
            return jsonify({'error': 'Cannot change your own role'}), 400
        
        # Cannot change superadmin's role
        if user.is_superadmin:
            return jsonify({'error': 'Cannot change the superadmin role'}), 403
        
        # Get new role from request
        data = request.get_json()
        new_role = data.get('role', '').lower()
        approval_code = data.get('approval_code', '').strip().upper()
        
        # Validate role
        valid_roles = [r.value for r in UserRole]
        if new_role not in valid_roles:
            return jsonify({'error': f'Invalid role. Valid: {valid_roles}'}), 400
        
        old_role = user.role.value if user.role else 'student'
        new_role_enum = UserRole(new_role)
        
        # No change needed
        if old_role == new_role:
            return jsonify({'message': 'Role unchanged', 'user_id': user.id, 'role': new_role}), 200
        
        # Determine if approval is required
        requires_approval = False
        action_description = ""
        
        # Check if current user is superadmin
        is_superadmin = getattr(current_user, 'is_superadmin', False)
        
        if not is_superadmin:
            # Non-superadmin admins need approval for certain actions
            if new_role == 'admin':
                requires_approval = True
                action_description = f"promote {user.full_name} to Admin"
            elif new_role == 'content_manager' and old_role == 'student':
                requires_approval = True
                action_description = f"promote {user.full_name} to Content Manager"
            elif old_role == 'admin':
                requires_approval = True
                action_description = f"demote Admin {user.full_name} to {new_role.replace('_', ' ').title()}"
        
        if requires_approval:
            if approval_code:
                # Verify the approval code
                pending = AdminApprovalCode.query.filter_by(
                    code=approval_code,
                    requesting_admin_id=current_user.id,
                    target_user_id=user.id,
                    used=False
                ).first()
                
                if not pending or not pending.is_valid():
                    return jsonify({
                        'error': 'Invalid or expired approval code',
                        'requires_approval': True
                    }), 403
                
                # Mark code as used
                pending.mark_used()
                db.session.commit()
                
                # Proceed with role change (code verified)
                logger.info(f"Admin {current_user.email} used approval code to {action_description}")
            else:
                action_details = {'old_role': old_role, 'new_role': new_role}
                resend_requested = request.json.get('resend_code', False)
                
                # Check for existing pending approval for the same action
                # Use Python filtering for JSON field (works on both SQLite and PostgreSQL)
                pending_approvals = AdminApprovalCode.query.filter(
                    AdminApprovalCode.requesting_admin_id == current_user.id,
                    AdminApprovalCode.target_user_id == user.id,
                    AdminApprovalCode.used == False,
                    AdminApprovalCode.cancelled == False,
                    AdminApprovalCode.expires_at > datetime.utcnow()
                ).all()
                
                # Filter by action_details in Python (database-agnostic)
                existing_pending = next(
                    (p for p in pending_approvals 
                     if p.action_details and p.action_details.get('new_role') == new_role),
                    None
                )
                
                if existing_pending and not resend_requested:
                    # Pending approval already exists - don't send new code
                    time_remaining = existing_pending.expires_at - datetime.utcnow()
                    hours_remaining = int(time_remaining.total_seconds() // 3600)
                    minutes_remaining = int((time_remaining.total_seconds() % 3600) // 60)
                    
                    return jsonify({
                        'requires_approval': True,
                        'already_pending': True,
                        'message': f'A request for this action is already pending Super Admin approval.',
                        'status': 'already_pending',
                        'action': action_description,
                        'pending_id': existing_pending.id,
                        'expires_in': f'{hours_remaining}h {minutes_remaining}m',
                        'created_at': existing_pending.created_at.isoformat()
                    }), 202
                
                # If resend requested or no existing pending, generate new code
                if existing_pending and resend_requested:
                    # Cancel old code before generating new one
                    existing_pending.mark_cancelled(current_user.id)
                    logger.info(f"[AUDIT] Admin {current_user.email} requested resend - old code {existing_pending.code} cancelled")
                
                # Generate new approval code and send email
                code = generate_approval_code()
                
                # Send email to superadmin FIRST - action blocked if email fails
                email_result = send_admin_approval_email(
                    requesting_admin_email=current_user.email,
                    requesting_admin_name=current_user.full_name,
                    target_user_email=user.email,
                    target_user_name=user.full_name,
                    action=action_description,
                    code=code,
                    action_details=action_details
                )
                
                # BLOCK action if email delivery fails
                if not email_result.get('success'):
                    logger.error(f"[AUDIT] BLOCKED: Admin {current_user.email} tried to {action_description} - email failed: {email_result.get('error')}")
                    return jsonify({
                        'error': 'Unable to notify Super Admin. Action not completed.',
                        'detail': 'Email delivery failed. Please try again later or contact the Super Admin directly.',
                        'action_blocked': True
                    }), 503
                
                # Create pending approval record (only after email succeeds)
                pending_approval = AdminApprovalCode(
                    code=code,
                    requesting_admin_id=current_user.id,
                    target_user_id=user.id,
                    action=action_description,
                    action_details=action_details,
                    expires_at=datetime.utcnow() + timedelta(hours=24)
                )
                db.session.add(pending_approval)
                db.session.commit()
                
                # Audit log
                logger.info(f"[AUDIT] PENDING: Admin {current_user.email} requested to {action_description} - awaiting Super Admin approval (email_id: {email_result.get('email_id')})")
                
                return jsonify({
                    'requires_approval': True,
                    'message': 'This action requires Super Admin approval. An email notification has been sent.',
                    'status': 'pending_approval',
                    'action': action_description
                }), 202
        
        # Perform the role change
        user.role = new_role_enum
        db.session.commit()
        
        # Build response with warning for superadmin
        response = {
            'message': f'User role updated to {new_role}',
            'user_id': user.id,
            'old_role': old_role,
            'new_role': new_role
        }
        
        # Add warning for superadmin when promoting to privileged roles
        if is_superadmin and new_role in ['admin', 'content_manager']:
            warnings = {
                'admin': 'This user now has FULL admin access including user management, backup/restore, and TNM data management.',
                'content_manager': 'This user can now create and edit cases, but cannot manage users or access admin features.'
            }
            response['warning'] = warnings.get(new_role, '')
        
        logger.info(f"Admin {current_user.email} changed {user.email} role from {old_role} to {new_role}")
        
        return jsonify(response), 200
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating user role: {str(e)}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/users/<int:user_id>/subscription', methods=['PUT'])
@require_admin
def update_user_subscription(user_id):
    """
    Change a user's subscription status (FREE, PAID, CANCELED)
    
    Body: { "subscription_status": "paid" }
    """
    try:
        # Get target user
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get new subscription status
        data = request.get_json()
        new_status = data.get('subscription_status', '').lower()
        
        # Validate subscription status
        valid_statuses = [s.value for s in SubscriptionStatus]
        if new_status not in valid_statuses:
            return jsonify({'error': f'Invalid status. Valid: {valid_statuses}'}), 400
        
        # Update subscription
        old_status = user.subscription_status.value if user.subscription_status else None
        
        if new_status == 'paid':
            upgrade_to_paid(user)
        elif new_status == 'free':
            downgrade_to_free(user)
        elif new_status == 'canceled':
            downgrade_to_free(user)  # Same as downgrade
            user.subscription_status = SubscriptionStatus.CANCELED
        
        db.session.commit()
        
        # Log action
        logger.info(f"Admin {current_user.email} changed {user.email} subscription from {old_status} to {new_status}")
        
        return jsonify({
            'message': f'Subscription updated to {new_status}',
            'user_id': user.id,
            'old_status': old_status,
            'new_status': new_status
        }), 200
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating subscription: {str(e)}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['PUT'])
@require_admin
def toggle_user_active(user_id):
    """
    Toggle user is_active status
    
    Body: { "is_active": true }
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        is_active = data.get('is_active', user.is_active)
        
        old_status = user.is_active
        user.is_active = is_active
        db.session.commit()
        
        logger.info(f"Admin {current_user.email} set {user.email} active={is_active}")
        
        return jsonify({
            'message': f'User active status: {is_active}',
            'old_status': old_status,
            'new_status': is_active
        }), 200
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling user active: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# USER DELETION ENDPOINT
# ============================================================================

@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@require_admin
def delete_user(user_id):
    """
    Permanently delete a user and clean up related data.
    
    Query params:
    - approval_code: Required for non-superadmins deleting admins
    
    DELETES: Private data (notes, highlights, revision sessions, view logs, votes, flags)
    PRESERVES: Forum messages (anonymized), case data (author references nullified)
    
    Superadmin: Can delete anyone with a warning showing what will be deleted/preserved
    Admin: Can delete students/content managers freely, needs approval code for admins
    """
    from models import AdminApprovalCode
    from auth import send_admin_approval_email, generate_approval_code
    from datetime import timedelta
    
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Cannot delete self
        if user.id == current_user.id:
            return jsonify({'error': 'Cannot delete your own account'}), 400
        
        # Cannot delete the superadmin
        if user.is_superadmin:
            return jsonify({'error': 'Cannot delete the superadmin account'}), 403
        
        email = user.email
        user_role = user.role.value if hasattr(user.role, 'value') else str(user.role)
        is_superadmin = getattr(current_user, 'is_superadmin', False)
        
        # Get approval code from request
        approval_code = request.args.get('approval_code', '').strip().upper()
        
        # Determine if approval is required (Admin deleting Admin or Content Manager)
        requires_approval = False
        if not is_superadmin and user.role in [UserRole.ADMIN, UserRole.CONTENT_MANAGER]:
            requires_approval = True
        
        if requires_approval:
            role_display = 'Admin' if user.role == UserRole.ADMIN else 'Content Manager'
            action_description = f"delete {role_display} {user.full_name}"
            
            if approval_code:
                # Verify the approval code
                pending = AdminApprovalCode.query.filter_by(
                    code=approval_code,
                    requesting_admin_id=current_user.id,
                    target_user_id=user.id,
                    used=False
                ).first()
                
                if not pending or not pending.is_valid():
                    logger.warning(f"[AUDIT] REJECTED: Admin {current_user.email} provided invalid approval code for {action_description}")
                    return jsonify({
                        'error': 'Invalid or expired approval code',
                        'requires_approval': True
                    }), 403
                
                # Mark code as used
                pending.mark_used()
                db.session.commit()
                
                logger.info(f"[AUDIT] APPROVED: Admin {current_user.email} used approval code to {action_description}")
            else:
                action_details = {'target_role': user_role, 'action_type': 'deletion'}
                resend_requested = request.args.get('resend_code', 'false').lower() == 'true'
                
                # Check for existing pending approval for deletion of this user
                # Use Python filtering for JSON field (works on both SQLite and PostgreSQL)
                pending_approvals = AdminApprovalCode.query.filter(
                    AdminApprovalCode.requesting_admin_id == current_user.id,
                    AdminApprovalCode.target_user_id == user.id,
                    AdminApprovalCode.used == False,
                    AdminApprovalCode.cancelled == False,
                    AdminApprovalCode.expires_at > datetime.utcnow()
                ).all()
                
                # Filter by action_details in Python (database-agnostic)
                existing_pending = next(
                    (p for p in pending_approvals 
                     if p.action_details and p.action_details.get('action_type') == 'deletion'),
                    None
                )
                
                if existing_pending and not resend_requested:
                    # Pending approval already exists - don't send new code
                    time_remaining = existing_pending.expires_at - datetime.utcnow()
                    hours_remaining = int(time_remaining.total_seconds() // 3600)
                    minutes_remaining = int((time_remaining.total_seconds() % 3600) // 60)
                    
                    return jsonify({
                        'requires_approval': True,
                        'already_pending': True,
                        'message': f'A request to delete this {role_display} is already pending Super Admin approval.',
                        'status': 'already_pending',
                        'action': action_description,
                        'pending_id': existing_pending.id,
                        'expires_in': f'{hours_remaining}h {minutes_remaining}m',
                        'created_at': existing_pending.created_at.isoformat()
                    }), 202
                
                # If resend requested or no existing pending, generate new code
                if existing_pending and resend_requested:
                    # Cancel old code before generating new one
                    existing_pending.mark_cancelled(current_user.id)
                    logger.info(f"[AUDIT] Admin {current_user.email} requested resend - old code {existing_pending.code} cancelled")
                
                # Generate new approval code and send email FIRST
                code = generate_approval_code()
                
                # Send email to superadmin FIRST - action blocked if email fails
                email_result = send_admin_approval_email(
                    requesting_admin_email=current_user.email,
                    requesting_admin_name=current_user.full_name,
                    target_user_email=user.email,
                    target_user_name=user.full_name,
                    action=action_description,
                    code=code,
                    action_details=action_details
                )
                
                # BLOCK action if email delivery fails
                if not email_result.get('success'):
                    logger.error(f"[AUDIT] BLOCKED: Admin {current_user.email} tried to {action_description} - email failed: {email_result.get('error')}")
                    return jsonify({
                        'error': 'Unable to notify Super Admin. Action not completed.',
                        'detail': 'Email delivery failed. Please try again later or contact the Super Admin directly.',
                        'action_blocked': True
                    }), 503
                
                # Create pending approval record (only after email succeeds)
                pending_approval = AdminApprovalCode(
                    code=code,
                    requesting_admin_id=current_user.id,
                    target_user_id=user.id,
                    action=action_description,
                    action_details=action_details,
                    expires_at=datetime.utcnow() + timedelta(hours=24)
                )
                db.session.add(pending_approval)
                db.session.commit()
                
                # Audit log
                logger.info(f"[AUDIT] PENDING: Admin {current_user.email} requested to {action_description} - awaiting Super Admin approval (email_id: {email_result.get('email_id')})")
                
                return jsonify({
                    'requires_approval': True,
                    'message': f'Deleting a {role_display} requires Super Admin approval. An email notification has been sent.',
                    'status': 'pending_approval',
                    'action': action_description
                }), 202
        
        # Return a preview of what will be deleted/preserved (for ALL admins)
        if not request.args.get('confirmed'):
            # Get deletion preview stats
            from models import CandidateNote, TextHighlight, RevisionSession, ForumMessage, Case
            preview = {
                'will_delete': {
                    'notes': CandidateNote.query.filter_by(user_id=user.id).count(),
                    'highlights': TextHighlight.query.filter_by(user_id=user.id).count(),
                    'revision_sessions': RevisionSession.query.filter_by(user_id=user.id).count(),
                },
                'will_preserve': {
                    'forum_messages': ForumMessage.query.filter_by(user_id=user.id).count(),
                    'cases_created': Case.query.filter_by(created_by_user_id=user.id).count(),
                }
            }
            
            return jsonify({
                'requires_confirmation': True,
                'message': 'Please confirm deletion. Add ?confirmed=true to proceed.',
                'target_user': {
                    'email': email,
                    'name': user.full_name,
                    'role': user_role
                },
                'preview': preview,
                'warning': 'This action cannot be undone!'
            }), 200
        
        # Perform complete deletion with cleanup
        success, result = delete_user_completely(user)
        
        if not success:
            logger.error(f"Failed to delete user {email}: {result}")
            return jsonify({'error': f'Failed to delete user: {result}'}), 500
        
        stats = result
        logger.warning(
            f"Admin {current_user.email} DELETED user {email} (role: {user_role}). "
            f"Cleanup: {stats['notes_deleted']} notes, {stats['highlights_deleted']} highlights, "
            f"{stats['forum_messages_anonymized']} forum messages anonymized, "
            f"{stats['cases_updated']} case references updated"
        )
        
        return jsonify({
            'message': f'User permanently deleted: {email}',
            'user_id': user_id,
            'cleanup_stats': stats
        }), 200
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting user: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# STATISTICS & REPORTING
# ============================================================================

@admin_bp.route('/users/stats/overview', methods=['GET'])
@require_admin
def users_stats_overview():
    """
    Get overview statistics about users
    
    Returns: Total users, by role, by subscription, active/inactive counts
    """
    try:
        from models import Case, CaseViewLog
        
        total_users = User.query.count()
        active_users = User.query.filter(User.is_active == True).count()
        inactive_users = User.query.filter(User.is_active == False).count()
        
        # By role
        by_role = {}
        for role in UserRole:
            count = User.query.filter_by(role=role).count()
            by_role[role.value] = count
        
        # By subscription
        by_subscription = {}
        for status in SubscriptionStatus:
            count = User.query.filter_by(subscription_status=status).count()
            by_subscription[status.value] = count
        
        return jsonify({
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': inactive_users,
            'by_role': by_role,
            'by_subscription': by_subscription
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting user stats: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# CASE MANAGEMENT ENDPOINTS
# ============================================================================

@admin_bp.route('/cases', methods=['GET'])
@require_admin
def list_cases():
    """
    Get paginated list of cases with optional filtering and search
    
    Query Parameters:
    - page: int (default 1)
    - per_page: int (default 10)
    - search: str (diagnosis)
    - module: str (GENERAL_RADIOGRAPHY, FLUOROSCOPY, etc.)
    - body_part: str (CHEST, ABDOMEN, etc.)
    
    Returns: { success: bool, cases: [], total: int, pages: int }
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = request.args.get('search', '', type=str).strip()
        module_filter = request.args.get('module', '', type=str).strip()
        body_part_filter = request.args.get('body_part', '', type=str).strip()
        
        # Validate pagination
        per_page = min(per_page, 100)  # Max 100 per page
        if page < 1:
            page = 1
        
        # Build query
        query = Case.query
        
        # Search by diagnosis
        if search:
            query = query.filter(Case.diagnosis.ilike(f'%{search}%'))
        
        # Filter by module
        if module_filter:
            from models import FRCRModule
            try:
                module_enum = FRCRModule[module_filter]
                query = query.filter(Case.module == module_enum)
            except KeyError:
                pass
        
        # Filter by body_part
        if body_part_filter:
            from models import BodyPart
            try:
                body_part_enum = BodyPart[body_part_filter]
                query = query.filter(Case.body_part == body_part_enum)
            except KeyError:
                pass
        
        # Order by most recent
        query = query.order_by(Case.created_at.desc())
        
        # Paginate
        pagination = query.paginate(page=page, per_page=per_page)
        
        # Build response
        cases_data = []
        for case in pagination.items:
            # Get creator's name (prefer contributor_name from case, fallback to User.full_name)
            if case.contributor_name:
                creator_name = case.contributor_name
            else:
                creator = User.query.get(case.created_by_user_id) if case.created_by_user_id else None
                creator_name = creator.full_name if creator else 'Unknown'
            
            cases_data.append({
                'id': case.id,
                'diagnosis': case.diagnosis,
                'case_number': case.case_number,
                'module': case.module.name if case.module else None,
                'body_part': case.body_part.name if case.body_part else None,
                'is_public': case.is_public,
                'created_by_user_id': case.created_by_user_id,
                'created_by_name': creator_name,
                'created_at': case.created_at.isoformat() if case.created_at else None,
            })
        
        return jsonify({
            'success': True,
            'cases': cases_data,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        }), 200
        
    except Exception as e:
        logger.error(f"[ADMIN CASES] Error listing cases: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to list cases: {str(e)}'
        }), 500


@admin_bp.route('/cases/<int:case_id>', methods=['DELETE'])
@require_admin
def delete_case(case_id):
    """
    Delete a case (admin only)
    
    Args:
        case_id: int - Case ID to delete
    
    Returns: { success: bool, message: str }
    """
    try:
        case = Case.query.get(case_id)
        
        if not case:
            return jsonify({
                'success': False,
                'error': 'Case not found'
            }), 404
        
        # Delete associated questions and answers
        from models import Question, Answer
        Question.query.filter_by(case_id=case_id).delete()
        Answer.query.filter_by(case_id=case_id).delete()
        
        # Delete the case
        db.session.delete(case)
        db.session.commit()
        
        logger.info(f"[ADMIN] Case {case_id} deleted by user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Case deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ADMIN CASES] Error deleting case {case_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to delete case: {str(e)}'
        }), 500



# ============================================================================
# CASE PUBLIC/PRIVATE TOGGLE ENDPOINTS
# ============================================================================

@admin_bp.route('/cases/<int:case_id>/public', methods=['PATCH'])
@require_role(UserRole.ADMIN, UserRole.CONTENT_MANAGER)
def toggle_case_public(case_id):
    """
    Toggle the public/private status of a case robustly.
    Accepts: { is_public: true/false/"true"/"false" }
    Returns: { success: bool, is_public: bool }
    """
    data = request.get_json()
    is_public = data.get('is_public')

    # Robustly handle boolean and string values
    if isinstance(is_public, str):
        is_public = is_public.lower() == 'true'
    else:
        is_public = bool(is_public)

    case = Case.query.get(case_id)
    if not case:
        return jsonify({'success': False, 'error': 'Case not found'}), 404

    try:
        from models import CaseStatus, sync_case_visibility
        target_status = CaseStatus.PUBLISHED if is_public else CaseStatus.PRIVATE
        sync_case_visibility(case, status=target_status)
        db.session.commit()
        return jsonify({
            'success': True,
            'is_public': case.is_public,
            'status': case.status.name if case.status else 'DRAFT'
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error', 'details': str(e)}), 500


@admin_bp.route('/cases/<int:case_id>', methods=['GET'])
@require_role(UserRole.ADMIN, UserRole.CONTENT_MANAGER)
def get_case(case_id):
    """
    Get a single case by ID (for editing)
    Returns: { id, is_public, ... }
    Allows both admins and content managers to access case data for editing
    """
    case = Case.query.get(case_id)
    if not case:
        return jsonify({'success': False, 'error': 'Case not found'}), 404
    creator = None
    creator_name = 'Unknown'
    if case.contributor_name:
        creator_name = case.contributor_name
    elif case.created_by_user_id:
        creator = User.query.get(case.created_by_user_id)
        if creator:
            creator_name = creator.full_name
    return jsonify({
        'id': case.id,
        'diagnosis': case.diagnosis,
        'case_number': case.case_number,
        'discussion': case.discussion,
        'module': case.module.name if case.module else None,
        'body_part': case.body_part.name if case.body_part else None,
        'age_group': case.age_group.name if case.age_group else None,
        'calculator_slug': case.calculator_slug,
        'status': case.status.name if case.status else 'DRAFT',
        'is_public': case.is_public,
        'created_by_user_id': case.created_by_user_id,
        'created_by_name': creator_name,
        'contributor_name': case.contributor_name or '',
        'created_at': case.created_at.isoformat() if case.created_at else None,
        'contributor_notes': case.contributor_notes or '',
    }), 200

# ============================================================================
# APP DOCUMENTATION ENDPOINTS
# ============================================================================
# Docs in this list are visible and openable by any admin; others are superadmin-only.
ADMIN_ACCESSIBLE_DOCS = [
    'USER_ROLES_WORKFLOWS.md',
    'CUSTOM_CSS_CLASSES_REFERENCE.md',
    'AI_TOOLS_AND_COSTS.md',
    'content-creation-plan.md',
    'ai_smart_reporter_improved.py',
    'smart_reporter_plan_revised.pdf',
]


@admin_bp.route('/docs', methods=['GET'])
@require_admin
def list_docs():
    """
    List markdown documentation files in the docs/ folder.
    Superadmin: full recursive list. Other admins: only ADMIN_ACCESSIBLE_DOCS.
    Returns: { docs: [{ name, path, title, is_folder?, children? }] }
    """
    docs_dir = os.path.join(os.path.dirname(__file__), 'docs')
    
    if not current_user.is_superadmin:
        # Return flat list of admin-accessible docs only
        docs = []
        for name in sorted(ADMIN_ACCESSIBLE_DOCS):
            title = name.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ')
            docs.append({
                'name': name,
                'path': name,
                'title': title,
                'is_folder': False
            })
        return jsonify({'success': True, 'docs': docs})
    
    docs = []
    
    def scan_dir(directory, prefix=''):
        """Recursively scan directory for .md files"""
        items = []
        try:
            for item in sorted(os.listdir(directory)):
                item_path = os.path.join(directory, item)
                relative_path = os.path.join(prefix, item) if prefix else item
                
                if os.path.isdir(item_path):
                    # Recursively scan subdirectories
                    subitems = scan_dir(item_path, relative_path)
                    if subitems:
                        items.append({
                            'name': item,
                            'path': relative_path,
                            'is_folder': True,
                            'children': subitems
                        })
                elif item.endswith('.md'):
                    # Generate title from filename
                    title = item.replace('.md', '').replace('_', ' ').replace('-', ' ')
                    items.append({
                        'name': item,
                        'path': relative_path,
                        'title': title,
                        'is_folder': False
                    })
        except Exception as e:
            logger.error(f"Error scanning docs directory: {e}")
        return items
    
    docs = scan_dir(docs_dir)
    return jsonify({'success': True, 'docs': docs})


@admin_bp.route('/docs/<path:doc_path>', methods=['GET'])
@require_admin
def get_doc(doc_path):
    """
    Get a specific markdown document rendered as HTML
    Returns: { title, content_html, raw_content }
    Admins can access ADMIN_ACCESSIBLE_DOCS; superadmin can access all.
    """
    doc_filename = os.path.basename(doc_path)
    if not current_user.is_superadmin and doc_filename not in ADMIN_ACCESSIBLE_DOCS:
        return jsonify({'success': False, 'error': 'Access denied. Superadmin only.'}), 403
    
    docs_dir = os.path.join(os.path.dirname(__file__), 'docs')
    file_path = os.path.join(docs_dir, doc_path)
    
    # Security: Ensure path is within docs directory
    real_docs_dir = os.path.realpath(docs_dir)
    real_file_path = os.path.realpath(file_path)
    
    if not real_file_path.startswith(real_docs_dir):
        return jsonify({'success': False, 'error': 'Invalid path'}), 403
    
    if not os.path.exists(file_path):
        return jsonify({'success': False, 'error': 'Document not found'}), 404

    allowed_extensions = ('.md', '.py', '.pdf')
    if not any(file_path.endswith(ext) for ext in allowed_extensions):
        return jsonify({'success': False, 'error': 'Invalid file type'}), 400

    try:
        # Generate title from filename
        basename = os.path.basename(doc_path)
        title = basename.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ')

        # PDF: serve as binary download
        if file_path.endswith('.pdf'):
            from flask import send_file
            return send_file(file_path, mimetype='application/pdf', as_attachment=False, download_name=basename)

        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()

        if file_path.endswith('.py'):
            # Python files: render as syntax-highlighted code block
            import html as html_module
            escaped = html_module.escape(raw_content)
            content_html = f'<pre style="background:#f8f9fa;padding:15px;border-radius:8px;overflow-x:auto;font-size:0.85rem;line-height:1.5;"><code class="language-python">{escaped}</code></pre>'
        else:
            # Markdown files: convert to HTML with extensions
            md = markdown.Markdown(extensions=[
                'tables',
                'fenced_code',
                'codehilite',
                'toc',
                'nl2br'
            ])
            content_html = md.convert(raw_content)

        return jsonify({
            'success': True,
            'title': title,
            'path': doc_path,
            'content_html': content_html,
            'raw_content': raw_content,
            'file_type': basename.rsplit('.', 1)[-1],
        })
    except Exception as e:
        logger.error(f"Error reading doc {doc_path}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/docs/content', methods=['GET'])
@require_admin
def get_doc_content():
    """
    Get a specific markdown document rendered as HTML via query parameter.
    Used by Role Guide modal which is accessible to all admins.
    
    Query params:
        path: The document path (e.g., USER_ROLES_WORKFLOWS.md)
    
    Returns: { html, title }
    """
    doc_path = request.args.get('path', '')
    
    if not doc_path:
        return jsonify({'success': False, 'error': 'Path parameter required'}), 400
    
    doc_filename = os.path.basename(doc_path)
    if not current_user.is_superadmin and doc_filename not in ADMIN_ACCESSIBLE_DOCS:
        return jsonify({'success': False, 'error': 'Access denied. Superadmin only.'}), 403
    
    docs_dir = os.path.join(os.path.dirname(__file__), 'docs')
    file_path = os.path.join(docs_dir, doc_path)
    
    # Security: Ensure path is within docs directory
    real_docs_dir = os.path.realpath(docs_dir)
    real_file_path = os.path.realpath(file_path)
    
    if not real_file_path.startswith(real_docs_dir):
        return jsonify({'success': False, 'error': 'Invalid path'}), 403
    
    if not os.path.exists(file_path):
        return jsonify({'success': False, 'error': 'Document not found'}), 404

    allowed_extensions = ('.md', '.py', '.pdf')
    if not any(file_path.endswith(ext) for ext in allowed_extensions):
        return jsonify({'success': False, 'error': 'Invalid file type'}), 400

    try:
        basename = os.path.basename(doc_path)
        title = basename.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ')

        # PDF: return a link to the direct download endpoint
        if file_path.endswith('.pdf'):
            return jsonify({
                'success': True,
                'title': title,
                'html': f'<div class="text-center py-4"><p>This is a PDF document.</p><a href="/api/admin/docs/{doc_path}" class="btn btn-primary" target="_blank"><i class="fas fa-file-pdf me-2"></i>Open PDF</a></div>',
                'file_type': 'pdf',
            })

        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()

        if file_path.endswith('.py'):
            import html as html_module
            escaped = html_module.escape(raw_content)
            html_out = f'<pre style="background:#f8f9fa;padding:15px;border-radius:8px;overflow-x:auto;font-size:0.85rem;line-height:1.5;"><code class="language-python">{escaped}</code></pre>'
        else:
            md = markdown.Markdown(extensions=[
                'tables',
                'fenced_code',
                'codehilite',
                'toc',
                'nl2br'
            ])
            html_out = md.convert(raw_content)

        return jsonify({
            'success': True,
            'title': title,
            'html': html_out,
        })
    except Exception as e:
        logger.error(f"Error reading doc {doc_path}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# APPROVAL CODE MANAGEMENT (Superadmin Only)
# ============================================================================

@admin_bp.route('/approvals/pending', methods=['GET'])
@require_admin
def get_pending_approvals():
    """
    Get all pending approval requests (Superadmin only)
    Returns list of pending approvals that haven't been used, cancelled, or expired
    """
    from models import AdminApprovalCode
    
    # Only superadmin can view pending approvals
    is_superadmin = getattr(current_user, 'is_superadmin', False)
    if not is_superadmin:
        return jsonify({'error': 'Only Super Admin can view pending approvals'}), 403
    
    try:
        pending_approvals = AdminApprovalCode.query.filter(
            AdminApprovalCode.used == False,
            AdminApprovalCode.cancelled == False,
            AdminApprovalCode.expires_at > datetime.utcnow()
        ).order_by(AdminApprovalCode.created_at.desc()).all()
        
        result = []
        for approval in pending_approvals:
            time_remaining = approval.expires_at - datetime.utcnow()
            hours_remaining = int(time_remaining.total_seconds() // 3600)
            minutes_remaining = int((time_remaining.total_seconds() % 3600) // 60)
            
            result.append({
                'id': approval.id,
                'code': approval.code,  # Show code to superadmin
                'action': approval.action,
                'action_details': approval.action_details,
                'requesting_admin': {
                    'id': approval.requesting_admin.id,
                    'email': approval.requesting_admin.email,
                    'name': approval.requesting_admin.full_name
                },
                'target_user': {
                    'id': approval.target_user.id,
                    'email': approval.target_user.email,
                    'name': approval.target_user.full_name,
                    'role': approval.target_user.role.value if approval.target_user.role else None
                },
                'created_at': approval.created_at.isoformat(),
                'expires_at': approval.expires_at.isoformat(),
                'expires_in': f'{hours_remaining}h {minutes_remaining}m'
            })
        
        return jsonify({
            'success': True,
            'pending_count': len(result),
            'approvals': result
        })
    except Exception as e:
        logger.error(f"Error fetching pending approvals: {e}")
        return jsonify({'error': 'Failed to fetch pending approvals'}), 500


@admin_bp.route('/approvals/<int:approval_id>/cancel', methods=['POST'])
@require_admin
def cancel_approval(approval_id):
    """
    Cancel a pending approval request (Superadmin only)
    This invalidates the approval code, preventing the action from being completed
    """
    from models import AdminApprovalCode
    
    # Only superadmin can cancel approvals
    is_superadmin = getattr(current_user, 'is_superadmin', False)
    if not is_superadmin:
        return jsonify({'error': 'Only Super Admin can cancel approval requests'}), 403
    
    try:
        approval = AdminApprovalCode.query.get(approval_id)
        
        if not approval:
            return jsonify({'error': 'Approval request not found'}), 404
        
        if approval.used:
            return jsonify({'error': 'This approval code has already been used'}), 400
        
        if approval.cancelled:
            return jsonify({'error': 'This approval request was already cancelled'}), 400
        
        if not approval.is_valid():
            return jsonify({'error': 'This approval request has already expired'}), 400
        
        # Cancel the approval
        approval.mark_cancelled(current_user.id)
        db.session.commit()
        
        # Audit log
        logger.info(f"[AUDIT] CANCELLED: Super Admin {current_user.email} cancelled approval request {approval.code} for action: {approval.action}")
        
        return jsonify({
            'success': True,
            'message': f'Approval request cancelled successfully',
            'cancelled_action': approval.action,
            'requesting_admin': approval.requesting_admin.email
        })
    except Exception as e:
        logger.error(f"Error cancelling approval {approval_id}: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to cancel approval request'}), 500


@admin_bp.route('/approvals/history', methods=['GET'])
@require_admin
def get_approval_history():
    """
    Get approval history including used and cancelled requests (Superadmin only)
    Optional query params: limit (default 50), status ('used', 'cancelled', 'expired', 'all')
    """
    from models import AdminApprovalCode
    
    # Only superadmin can view approval history
    is_superadmin = getattr(current_user, 'is_superadmin', False)
    if not is_superadmin:
        return jsonify({'error': 'Only Super Admin can view approval history'}), 403
    
    try:
        limit = request.args.get('limit', 50, type=int)
        status_filter = request.args.get('status', 'all')
        
        query = AdminApprovalCode.query
        
        if status_filter == 'used':
            query = query.filter(AdminApprovalCode.used == True)
        elif status_filter == 'cancelled':
            query = query.filter(AdminApprovalCode.cancelled == True)
        elif status_filter == 'expired':
            query = query.filter(
                AdminApprovalCode.used == False,
                AdminApprovalCode.cancelled == False,
                AdminApprovalCode.expires_at <= datetime.utcnow()
            )
        # 'all' shows everything
        
        approvals = query.order_by(AdminApprovalCode.created_at.desc()).limit(limit).all()
        
        result = []
        for approval in approvals:
            # Determine status
            if approval.used:
                status = 'used'
            elif approval.cancelled:
                status = 'cancelled'
            elif datetime.utcnow() > approval.expires_at:
                status = 'expired'
            else:
                status = 'pending'
            
            result.append({
                'id': approval.id,
                'code': approval.code,
                'action': approval.action,
                'action_details': approval.action_details,
                'status': status,
                'requesting_admin': {
                    'id': approval.requesting_admin.id if approval.requesting_admin else None,
                    'email': approval.requesting_admin.email if approval.requesting_admin else 'Unknown',
                    'name': approval.requesting_admin.full_name if approval.requesting_admin else 'Unknown'
                },
                'target_user': {
                    'id': approval.target_user.id if approval.target_user else None,
                    'email': approval.target_user.email if approval.target_user else 'Deleted',
                    'name': approval.target_user.full_name if approval.target_user else 'Deleted'
                },
                'created_at': approval.created_at.isoformat(),
                'expires_at': approval.expires_at.isoformat(),
                'used_at': approval.used_at.isoformat() if approval.used_at else None,
                'cancelled_at': approval.cancelled_at.isoformat() if approval.cancelled_at else None,
                'cancelled_by': approval.cancelled_by.email if approval.cancelled_by else None
            })
        
        return jsonify({
            'success': True,
            'count': len(result),
            'filter': status_filter,
            'approvals': result
        })
    except Exception as e:
        logger.error(f"Error fetching approval history: {e}")
        return jsonify({'error': 'Failed to fetch approval history'}), 500


# ============================================================================
# CASE REFERENCES API
# ============================================================================

@admin_bp.route('/cases/<int:case_id>/references', methods=['GET'])
@require_role(UserRole.ADMIN, UserRole.CONTENT_MANAGER)
def get_case_references(case_id):
    """Get all references for a case"""
    from models import Case, CaseReference
    
    case = Case.query.get_or_404(case_id)
    references = CaseReference.query.filter_by(case_id=case_id).order_by(CaseReference.ref_number).all()
    
    return jsonify({
        'success': True,
        'case_id': case_id,
        'references': [ref.to_dict() for ref in references]
    })


@admin_bp.route('/cases/<int:case_id>/references', methods=['POST'])
@require_role(UserRole.ADMIN, UserRole.CONTENT_MANAGER)
def add_case_reference(case_id):
    """Add a reference to a case"""
    from models import Case, CaseReference, db
    
    case = Case.query.get_or_404(case_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    title = data.get('title', '').strip()
    url = data.get('url', '').strip()
    
    if not title:
        return jsonify({'success': False, 'error': 'Title is required'}), 400
    if not url:
        return jsonify({'success': False, 'error': 'URL is required'}), 400
    
    # Check if URL already exists for this case
    existing = CaseReference.query.filter_by(case_id=case_id, url=url).first()
    if existing:
        return jsonify({
            'success': True,
            'reference': existing.to_dict(),
            'is_duplicate': True,
            'message': f'Reference already exists as [{existing.ref_number}]'
        })
    
    # Get next ref_number
    max_ref = db.session.query(db.func.max(CaseReference.ref_number)).filter_by(case_id=case_id).scalar()
    next_ref_number = (max_ref or 0) + 1
    
    # Create new reference
    reference = CaseReference(
        case_id=case_id,
        ref_number=next_ref_number,
        title=title,
        url=url,
        journal=data.get('journal', '').strip() or None,
        year=data.get('year', '').strip() or None,
        is_inline=data.get('is_inline', False)
    )
    
    db.session.add(reference)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'reference': reference.to_dict(),
        'is_duplicate': False,
        'message': f'Reference [{next_ref_number}] added'
    })


@admin_bp.route('/cases/<int:case_id>/references/<int:ref_id>', methods=['DELETE'])
@require_role(UserRole.ADMIN, UserRole.CONTENT_MANAGER)
def delete_case_reference(case_id, ref_id):
    """Delete a reference from a case"""
    from models import CaseReference, db
    
    reference = CaseReference.query.filter_by(id=ref_id, case_id=case_id).first_or_404()
    ref_number = reference.ref_number
    
    db.session.delete(reference)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Reference [{ref_number}] deleted'
    })


@admin_bp.route('/cases/<int:case_id>/references', methods=['DELETE'])
@require_role(UserRole.ADMIN, UserRole.CONTENT_MANAGER)
def clear_case_references(case_id):
    """Clear all references for a case"""
    from models import Case, CaseReference, db
    
    case = Case.query.get_or_404(case_id)
    count = CaseReference.query.filter_by(case_id=case_id).delete()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'{count} references cleared'
    })


# ============================================================================
# TNM REFERENCES API (ADMIN)
# ============================================================================

@admin_bp.route('/tnm/<int:disease_site_id>/references', methods=['GET'])
@require_role(UserRole.ADMIN, UserRole.CONTENT_MANAGER)
def get_tnm_references(disease_site_id):
    """Get all references for a TNM disease site"""
    from models import AJCCDiseaseSite, TnmReference
    
    disease = AJCCDiseaseSite.query.get_or_404(disease_site_id)
    references = TnmReference.query.filter_by(disease_site_id=disease_site_id).order_by(TnmReference.ref_number).all()
    
    return jsonify({
        'success': True,
        'disease_site_id': disease_site_id,
        'references': [ref.to_dict() for ref in references]
    })


@admin_bp.route('/tnm/<int:disease_site_id>/references', methods=['POST'])
@require_role(UserRole.ADMIN, UserRole.CONTENT_MANAGER)
def add_tnm_reference(disease_site_id):
    """Add a reference to a TNM disease site"""
    from models import AJCCDiseaseSite, TnmReference, db
    
    disease = AJCCDiseaseSite.query.get_or_404(disease_site_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    title = data.get('title', '').strip()
    url = data.get('url', '').strip()
    
    if not title:
        return jsonify({'success': False, 'error': 'Title is required'}), 400
    if not url:
        return jsonify({'success': False, 'error': 'URL is required'}), 400
    
    # Check if URL already exists for this disease site
    existing = TnmReference.query.filter_by(disease_site_id=disease_site_id, url=url).first()
    if existing:
        return jsonify({
            'success': True,
            'reference': existing.to_dict(),
            'is_duplicate': True,
            'message': f'Reference already exists as [{existing.ref_number}]'
        })
    
    # Get next ref_number
    max_ref = db.session.query(db.func.max(TnmReference.ref_number)).filter_by(disease_site_id=disease_site_id).scalar()
    next_ref_number = (max_ref or 0) + 1
    
    # Create new reference
    reference = TnmReference(
        disease_site_id=disease_site_id,
        ref_number=next_ref_number,
        title=title,
        url=url,
        journal=data.get('journal', '').strip() or None,
        year=data.get('year', '').strip() or None,
        is_inline=data.get('is_inline', False)
    )
    
    db.session.add(reference)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'reference': reference.to_dict(),
        'is_duplicate': False,
        'message': f'Reference [{next_ref_number}] added'
    })


@admin_bp.route('/tnm/<int:disease_site_id>/references/<int:ref_id>', methods=['DELETE'])
@require_role(UserRole.ADMIN, UserRole.CONTENT_MANAGER)
def delete_tnm_reference(disease_site_id, ref_id):
    """Delete a reference from a TNM disease site"""
    from models import TnmReference, db
    
    reference = TnmReference.query.filter_by(id=ref_id, disease_site_id=disease_site_id).first_or_404()
    ref_number = reference.ref_number
    
    db.session.delete(reference)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Reference [{ref_number}] deleted'
    })


@admin_bp.route('/tnm/<int:disease_site_id>/references', methods=['DELETE'])
@require_role(UserRole.ADMIN, UserRole.CONTENT_MANAGER)
def clear_tnm_references(disease_site_id):
    """Clear all references for a TNM disease site"""
    from models import AJCCDiseaseSite, TnmReference, db
    
    disease = AJCCDiseaseSite.query.get_or_404(disease_site_id)
    count = TnmReference.query.filter_by(disease_site_id=disease_site_id).delete()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'{count} references cleared'
    })


# ============================================================================
# R2 BUCKET MANAGEMENT (Admin only)
# ============================================================================

@admin_bp.route('/r2/list', methods=['GET'])
@require_admin
def r2_list_objects():
    """List objects and folders in R2 bucket. Query: prefix, delimiter, max_keys, continuation_token."""
    try:
        from case_dicom_viewer.r2_service import list_objects as r2_list, is_configured
        if not is_configured():
            return jsonify({'error': 'R2 not configured'}), 503
        prefix = request.args.get('prefix', '')
        delimiter = request.args.get('delimiter', '/')
        max_keys = min(int(request.args.get('max_keys', 1000)), 1000)
        token = request.args.get('continuation_token') or None
        result = r2_list(prefix=prefix, delimiter=delimiter, max_keys=max_keys, continuation_token=token)
        return jsonify(result), 200
    except Exception as e:
        logger.exception("R2 list error: %s", e)
        return jsonify({'error': str(e)[:500]}), 500


@admin_bp.route('/r2/delete', methods=['POST'])
@require_admin
def r2_delete_objects():
    """
    Delete objects from R2. Body: { "prefix": "cases/123/abc/" } OR { "keys": ["key1", "key2"] }.
    Use prefix to delete a folder and all contents.
    """
    try:
        from case_dicom_viewer.r2_service import delete_prefix, delete_objects, is_configured
        if not is_configured():
            return jsonify({'error': 'R2 not configured'}), 503
        data = request.get_json() or {}
        prefix = data.get('prefix')
        keys = data.get('keys', [])
        delete_all = data.get('delete_all', False)

        if delete_all:
            deleted_count, errors = delete_prefix("")
            return jsonify({
                'deleted': deleted_count,
                'errors': errors[:20],
                'message': f'Deleted {deleted_count} object(s). Bucket emptied.'
            }), 200
        if prefix is not None:
            deleted_count, errors = delete_prefix(prefix)
            msg = f'Deleted {deleted_count} object(s)' + (f' under {prefix}' if prefix else '. Bucket emptied.')
            return jsonify({'deleted': deleted_count, 'errors': errors[:20], 'message': msg}), 200
        elif keys:
            deleted, errors = delete_objects(keys)
            return jsonify({
                'deleted': deleted,
                'deleted_keys': deleted,
                'errors': errors[:20],
                'message': f'Deleted {len(deleted)} object(s)'
            }), 200
        else:
            return jsonify({'error': 'Provide prefix or keys in JSON body'}), 400
    except Exception as e:
        logger.exception("R2 delete error: %s", e)
        return jsonify({'error': str(e)[:500]}), 500


# ============================================================================
# AJCC DATA ENDPOINT (for TNM Generator auto-fill)
# ============================================================================

@admin_bp.route('/tnm/ajcc-data', methods=['GET'])
@require_admin
def get_ajcc_data():
    """
    Get AJCC staging data for TNM Generator auto-fill.

    Returns:
    - sections: List of body sections with disease sites
    - staging_data: Complete T/N/M definitions for diseases with data (currently Larynx)
    """
    try:
        base_path = os.path.join(os.path.dirname(__file__), 'ajcc_tnm', 'data')

        # Load ontology (sections and disease sites)
        ontology_path = os.path.join(base_path, 'ajcc_frcr_full_ontology.json')
        with open(ontology_path, 'r') as f:
            ontology = json.load(f)

        # Load structured TNM data (currently only Larynx has complete data)
        structured_path = os.path.join(base_path, 'ajcc_tnm_structured.json')
        staging_data = {}
        try:
            with open(structured_path, 'r') as f:
                larynx_data = json.load(f)
                # Create slug from disease name
                slug = larynx_data['disease_name'].lower().replace(' ', '-').replace('(', '').replace(')', '')
                staging_data[slug] = larynx_data
        except Exception as e:
            logger.warning(f"Could not load structured TNM data: {e}")

        # Build response with sections and diseases
        sections = []
        for section in ontology.get('sections', []):
            section_name = section.get('ajcc_section', '')
            diseases = []
            for disease in section.get('disease_sites', []):
                # Generate slug from disease name
                slug = disease.lower().replace(' ', '-').replace('(', '').replace(')', '').replace(',', '')
                diseases.append({
                    'name': disease,
                    'slug': slug,
                    'has_staging_data': slug in staging_data
                })
            sections.append({
                'name': section_name,
                'slug': section_name.lower().replace(' ', '-'),
                'diseases': diseases
            })

        return jsonify({
            'success': True,
            'source': ontology.get('source', 'AJCC Cancer Staging Manual'),
            'sections': sections,
            'staging_data': staging_data
        }), 200

    except FileNotFoundError as e:
        logger.error(f"AJCC data file not found: {e}")
        return jsonify({'success': False, 'error': 'AJCC data files not found'}), 500
    except Exception as e:
        logger.exception(f"Error loading AJCC data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# TNM CALCULATOR GENERATOR ENDPOINTS
# ============================================================================

@admin_bp.route('/tnm/generate', methods=['POST'])
@require_admin
def generate_tnm_calculator():
    """
    Generate TNM calculator and algorithm content using AI.

    Body:
    {
        "slug": "lung",
        "cancer_name": "Lung (NSCLC)",
        "body_section": "Thorax",
        "staging_system": "AJCC 9th Edition",  // optional
        "special_features": ["SCLC Option"],   // optional
        "description": "Non-small cell lung cancer staging",  // optional
        "special_notes": ""  // optional, notes for AI generation
    }

    Returns: { success: bool, message: str, data: {...} }
    """
    try:
        from tnm_calculator.tnm_generator import generate_and_save_tnm_content

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        required = ['slug', 'cancer_name', 'body_section']
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing)}'
            }), 400

        # Get model parameter (default to Sonnet for cost efficiency)
        model = data.get('model', 'claude-sonnet-4-20250514')

        success, message, result_data = generate_and_save_tnm_content(
            db=db,
            slug=data['slug'],
            cancer_name=data['cancer_name'],
            body_section=data['body_section'],
            staging_system=data.get('staging_system', 'AJCC 9th Edition'),
            special_features=data.get('special_features', []),
            description=data.get('description', ''),
            special_notes=data.get('special_notes', ''),
            user_id=current_user.id,
            overwrite=data.get('overwrite', False),
            model=model
        )

        if success:
            # Auto-link calculator to case if case_id provided
            case_id = data.get('case_id')
            if case_id:
                try:
                    from models import Case
                    case = Case.query.get(case_id)
                    if case:
                        case.calculator_slug = data['slug']
                        db.session.commit()
                        logger.info(f"Auto-linked calculator '{data['slug']}' to case {case_id}")
                        result_data['case_linked'] = True
                except Exception as link_error:
                    logger.warning(f"Failed to auto-link calculator to case: {link_error}")
                    result_data['case_linked'] = False

            return jsonify({'success': True, 'message': message, 'data': result_data}), 200
        else:
            return jsonify({'success': False, 'error': message}), 400

    except Exception as e:
        logger.exception(f"TNM Generator error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/tnm/regenerate/<slug>', methods=['POST'])
@require_admin
def regenerate_tnm_calculator(slug):
    """
    Regenerate content for existing TNM calculator.

    Body:
    {
        "regenerate_calculator": true,  // optional, default true
        "regenerate_algorithm": true,   // optional, default true
        "special_notes": ""             // optional
    }
    """
    try:
        from tnm_calculator.tnm_generator import regenerate_calculator

        data = request.get_json() or {}

        success, message, result_data = regenerate_calculator(
            db=db,
            slug=slug,
            regenerate_calculator=data.get('regenerate_calculator', True),
            regenerate_algorithm=data.get('regenerate_algorithm', True),
            special_notes=data.get('special_notes', '')
        )

        if success:
            return jsonify({'success': True, 'message': message, 'data': result_data}), 200
        else:
            return jsonify({'success': False, 'error': message}), 404

    except Exception as e:
        logger.exception(f"TNM Regenerate error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/tnm/list', methods=['GET'])
@require_admin
def list_tnm_calculators():
    """
    List all TNM calculators in database.

    Returns: { calculators: [...] }
    """
    try:
        from models import TNMCalculatorContent

        calculators = TNMCalculatorContent.query.order_by(TNMCalculatorContent.body_section, TNMCalculatorContent.cancer_name).all()

        return jsonify({
            'success': True,
            'calculators': [c.to_dict() for c in calculators]
        }), 200

    except Exception as e:
        logger.exception(f"TNM List error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# TNM GENERATOR JOB QUEUE (for Vercel Hobby - avoids 10s timeout)
# ============================================================================

@admin_bp.route('/tnm/queue', methods=['POST'])
@require_admin
def queue_tnm_generation():
    """
    Queue a TNM calculator generation job.
    Returns immediately with job_id for polling.
    Job is processed by cron endpoint (60s timeout).

    Body: same as /tnm/generate
    Returns: { success: true, job_id: "uuid", message: "Job queued" }
    """
    import uuid
    from models import TNMGeneratorJob
    import json

    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        required = ['slug', 'cancer_name', 'body_section']
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing)}'
            }), 400

        overwrite = data.get('overwrite', False)

        # Check if job already pending for this slug (unless overwrite mode)
        if not overwrite:
            existing = TNMGeneratorJob.query.filter_by(
                slug=data['slug'],
                status='pending'
            ).first()
            if existing:
                return jsonify({
                    'success': True,
                    'job_id': existing.job_id,
                    'message': 'Job already queued',
                    'status': 'pending'
                }), 200

        # Create job
        job = TNMGeneratorJob(
            job_id=str(uuid.uuid4()),
            slug=data['slug'],
            cancer_name=data['cancer_name'],
            body_section=data['body_section'],
            staging_system=data.get('staging_system', 'AJCC 9th Edition'),
            description=data.get('description', ''),
            special_features=json.dumps(data.get('special_features', [])),
            special_notes=data.get('special_notes', ''),
            overwrite=overwrite,
            created_by_user_id=current_user.id
        )
        db.session.add(job)
        db.session.commit()

        logger.info(f"[TNM Queue] Job queued: {job.job_id} for {job.slug}")

        return jsonify({
            'success': True,
            'job_id': job.job_id,
            'message': 'Job queued for processing',
            'status': 'pending'
        }), 202

    except Exception as e:
        logger.exception(f"TNM Queue error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/tnm/status/<job_id>', methods=['GET'])
@require_admin
def get_tnm_job_status(job_id):
    """
    Check status of a queued generation job.

    Returns: { success: true, job: {...} }
    """
    from models import TNMGeneratorJob

    try:
        job = TNMGeneratorJob.query.filter_by(job_id=job_id).first()
        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404

        return jsonify({
            'success': True,
            'job': job.to_dict()
        }), 200

    except Exception as e:
        logger.exception(f"TNM Status error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/tnm/update-template/<int:case_id>', methods=['POST'])
@require_admin
def update_algorithm_template(case_id):
    """
    Update algorithm template from edited case discussion.
    Extracts algorithm content and saves back to TNMCalculatorContent.

    Body:
    {
        "calculator_slug": "larynx"  // optional, uses case.calculator_slug if not provided
    }

    Returns: { success: true, message: "..." }
    """
    from tnm_calculator.tnm_generator import update_algorithm_template_from_case
    from models import Case

    try:
        data = request.get_json() or {}
        calculator_slug = data.get('calculator_slug')

        # Get slug from case if not provided
        if not calculator_slug:
            case = Case.query.get(case_id)
            if not case:
                return jsonify({'success': False, 'error': 'Case not found'}), 404
            calculator_slug = case.calculator_slug
            if not calculator_slug:
                return jsonify({'success': False, 'error': 'No calculator_slug on case'}), 400

        success, message = update_algorithm_template_from_case(
            db=db,
            case_id=case_id,
            calculator_slug=calculator_slug
        )

        if success:
            return jsonify({'success': True, 'message': message}), 200
        else:
            return jsonify({'success': False, 'error': message}), 400

    except Exception as e:
        logger.exception(f"Update algorithm template error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/tnm/available', methods=['GET'])
@require_admin
def list_available_cancers():
    """
    List available cancer types from V3_CALCULATORS config.

    Returns: { cancers: [...] }
    """
    try:
        from tnm_calculator.tnm_generator import get_available_calculators

        calculators = get_available_calculators()

        return jsonify({
            'success': True,
            'cancers': calculators
        }), 200

    except Exception as e:
        logger.exception(f"TNM Available error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/tnm/insert-algorithm/<int:case_id>', methods=['POST'])
@require_admin
def insert_algorithm_to_case(case_id):
    """
    Insert algorithm discussion into a case's discussion field.

    Body:
    {
        "calculator_slug": "oropharynx"
    }
    """
    try:
        from tnm_calculator.tnm_generator import insert_algorithm_to_case_discussion

        data = request.get_json()
        if not data or not data.get('calculator_slug'):
            return jsonify({'success': False, 'error': 'calculator_slug is required'}), 400

        success, message = insert_algorithm_to_case_discussion(
            db=db,
            case_id=case_id,
            calculator_slug=data['calculator_slug']
        )

        if success:
            return jsonify({'success': True, 'message': message}), 200
        else:
            return jsonify({'success': False, 'error': message}), 400

    except Exception as e:
        logger.exception(f"TNM Insert Algorithm error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/tnm/<slug>', methods=['GET'])
@require_admin
def get_tnm_calculator(slug):
    """
    Get TNM calculator content by slug.
    """
    try:
        from models import TNMCalculatorContent

        content = TNMCalculatorContent.query.filter_by(slug=slug).first()
        if not content:
            return jsonify({'success': False, 'error': 'Calculator not found'}), 404

        return jsonify({
            'success': True,
            'calculator': content.to_dict(),
            'calculator_html': content.calculator_html,
            'algorithm_html': content.algorithm_discussion_html
        }), 200

    except Exception as e:
        logger.exception(f"TNM Get error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/tnm/<slug>', methods=['PATCH'])
@require_admin
def update_tnm_calculator(slug):
    """
    Update TNM calculator HTML content (for manual edits).
    Also re-extracts algorithm discussion from the updated HTML.
    """
    try:
        from models import TNMCalculatorContent
        from tnm_calculator.tnm_generator import extract_algorithm_from_calculator

        content = TNMCalculatorContent.query.filter_by(slug=slug).first()
        if not content:
            return jsonify({'success': False, 'error': 'Calculator not found'}), 404

        data = request.get_json()
        if not data or 'calculator_html' not in data:
            return jsonify({'success': False, 'error': 'calculator_html is required'}), 400

        content.calculator_html = data['calculator_html']

        if data.get('edit_note'):
            content.last_edit_note = data['edit_note'][:500]

        # Re-extract algorithm from updated HTML
        try:
            algorithm_html = extract_algorithm_from_calculator(
                data['calculator_html'], content.cancer_name
            )
            content.algorithm_discussion_html = algorithm_html
        except Exception as alg_err:
            logger.warning(f"Algorithm re-extraction failed for {slug}: {alg_err}")

        db.session.commit()
        logger.info(f"Admin {current_user.email} edited TNM calculator: {slug}")

        return jsonify({
            'success': True,
            'message': f'Calculator {slug} updated',
            'updated_at': content.updated_at.isoformat() if content.updated_at else None
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"TNM Update error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/tnm-editor/<slug>')
@require_admin
def tnm_calculator_editor(slug):
    """
    Admin page: Monaco Editor + live preview for editing calculator HTML.
    """
    from models import TNMCalculatorContent

    content = TNMCalculatorContent.query.filter_by(slug=slug).first()
    if not content:
        return f"Calculator '{slug}' not found", 404

    return render_template(
        'admin_tnm_editor.html',
        slug=slug,
        cancer_name=content.cancer_name,
        calculator_html=content.calculator_html or '',
        last_edit_note=content.last_edit_note or '',
        updated_at=content.updated_at.isoformat() if content.updated_at else ''
    )


@admin_bp.route('/tnm/<slug>', methods=['DELETE'])
@require_admin
def delete_tnm_calculator(slug):
    """
    Delete TNM calculator from database (keeps HTML file).
    """
    try:
        from models import TNMCalculatorContent

        content = TNMCalculatorContent.query.filter_by(slug=slug).first()
        if not content:
            return jsonify({'success': False, 'error': 'Calculator not found'}), 404

        db.session.delete(content)
        db.session.commit()

        logger.info(f"Admin {current_user.email} deleted TNM calculator: {slug}")

        return jsonify({
            'success': True,
            'message': f'Calculator {slug} deleted from database'
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"TNM Delete error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# SENTRY MONITORING (Admin only)
# ============================================================================

@admin_bp.route('/sentry/stats', methods=['GET'])
@require_admin
def sentry_stats():
    """Proxy endpoint for Sentry API. Returns aggregated error stats."""
    import requests as http_requests

    auth_token = os.getenv('SENTRY_AUTH_TOKEN')
    org = os.getenv('SENTRY_ORG')
    project = os.getenv('SENTRY_PROJECT')

    if not all([auth_token, org, project]):
        return jsonify({
            'configured': False,
            'error': 'Sentry API not configured. Set SENTRY_AUTH_TOKEN, SENTRY_ORG, SENTRY_PROJECT.',
        }), 200

    headers = {'Authorization': f'Bearer {auth_token}'}
    base_url = 'https://sentry.io/api/0'
    period = request.args.get('period', '24h')

    result = {
        'configured': True,
        'period': period,
        'unresolved_count': 0,
        'recent_issues': [],
        'stats': [],
        'sentry_url': f'https://{org}.sentry.io/projects/{project}/',
        'errors': [],
    }

    try:
        # 1. Unresolved issues (most recent 10)
        issues_resp = http_requests.get(
            f'{base_url}/projects/{org}/{project}/issues/',
            headers=headers,
            params={'query': 'is:unresolved', 'sort': 'date', 'limit': 10, 'statsPeriod': period},
            timeout=10,
        )
        if issues_resp.status_code == 200:
            issues = issues_resp.json()
            result['unresolved_count'] = int(issues_resp.headers.get('X-Hits', len(issues)))
            result['recent_issues'] = [{
                'id': issue['id'],
                'title': issue['title'],
                'culprit': issue.get('culprit', ''),
                'count': int(issue.get('count', 0)),
                'first_seen': issue.get('firstSeen'),
                'last_seen': issue.get('lastSeen'),
                'level': issue.get('level', 'error'),
                'permalink': issue.get('permalink', ''),
            } for issue in issues]
        else:
            result['errors'].append(f'Issues API: {issues_resp.status_code}')

        # 2. Event stats (hourly/daily counts)
        stats_resp = http_requests.get(
            f'{base_url}/projects/{org}/{project}/stats/',
            headers=headers,
            params={'stat': 'received', 'resolution': '1h' if period == '24h' else '1d'},
            timeout=10,
        )
        if stats_resp.status_code == 200:
            result['stats'] = stats_resp.json()
        else:
            result['errors'].append(f'Stats API: {stats_resp.status_code}')

    except http_requests.exceptions.Timeout:
        result['errors'].append('Sentry API timeout')
    except http_requests.exceptions.ConnectionError:
        result['errors'].append('Could not connect to Sentry API')
    except Exception as e:
        logger.exception("Sentry stats error: %s", e)
        result['errors'].append(str(e)[:200])

    return jsonify(result), 200


# ============================================================================
# CONTENT MODERATION ENDPOINTS
# ============================================================================

@admin_bp.route('/moderation/counts', methods=['GET'])
@require_admin
def moderation_counts():
    """Get counts for pending content requests and user algorithm drafts."""
    from models import ContentRequest, ReportingAlgorithm
    pending_requests = ContentRequest.query.filter_by(status='pending').count()
    user_drafts = ReportingAlgorithm.query.filter_by(origin='user', is_available=False).count()
    return jsonify({
        'pending_requests': pending_requests,
        'user_drafts': user_drafts,
        'total': pending_requests + user_drafts,
    }), 200


@admin_bp.route('/moderation/user-drafts', methods=['GET'])
@require_admin
def list_user_drafts():
    """List user-generated algorithm drafts awaiting review."""
    from models import ReportingAlgorithm
    drafts = ReportingAlgorithm.query.filter_by(
        origin='user', is_available=False
    ).order_by(ReportingAlgorithm.created_at.desc()).limit(100).all()
    results = []
    for d in drafts:
        creator = User.query.get(d.created_by_user_id) if d.created_by_user_id else None
        results.append({
            'id': d.id,
            'title': d.title,
            'slug': d.slug,
            'category': d.category,
            'body_section': d.body_section,
            'username': creator.full_name if creator else 'Unknown',
            'created_at': d.created_at.isoformat() if d.created_at else None,
        })
    return jsonify({'drafts': results, 'count': len(results)}), 200


@admin_bp.route('/moderation/user-drafts/<int:draft_id>/publish', methods=['POST'])
@require_admin
def publish_user_draft(draft_id):
    """Publish a user-generated algorithm draft (make it available to all users)."""
    from models import ReportingAlgorithm
    draft = ReportingAlgorithm.query.get_or_404(draft_id)
    if draft.origin != 'user':
        return jsonify({'error': 'Only user-generated drafts can be published here'}), 400
    draft.is_available = True
    draft.verified_by_user_id = current_user.id
    draft.verified_at = datetime.utcnow()
    db.session.commit()
    logger.info(f'Admin {current_user.email} published user draft algorithm #{draft_id}')
    return jsonify({'success': True, 'message': f'Algorithm "{draft.title}" published'}), 200


@admin_bp.route('/moderation/user-drafts/<int:draft_id>', methods=['DELETE'])
@require_admin
def delete_user_draft(draft_id):
    """Delete a user-generated algorithm draft."""
    from models import ReportingAlgorithm
    draft = ReportingAlgorithm.query.get_or_404(draft_id)
    if draft.origin != 'user':
        return jsonify({'error': 'Only user-generated drafts can be deleted here'}), 400
    title = draft.title
    db.session.delete(draft)
    db.session.commit()
    logger.info(f'Admin {current_user.email} deleted user draft algorithm #{draft_id}')
    return jsonify({'success': True, 'message': f'Draft "{title}" deleted'}), 200


# ============================================================================
# 2FA SETUP ENDPOINTS
# ============================================================================

@admin_bp.route('/2fa/setup', methods=['POST'])
@require_admin
def setup_2fa():
    """Generate a new TOTP secret and QR code for 2FA setup."""
    import pyotp
    import qrcode
    import io
    import base64

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=current_user.email,
        issuer_name='RadInsights'
    )

    # Generate QR code as base64 PNG
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    return jsonify({
        'secret': secret,
        'qr_code': f'data:image/png;base64,{qr_base64}',
    }), 200


@admin_bp.route('/2fa/enable', methods=['POST'])
@require_admin
def enable_2fa():
    """Verify a TOTP code and enable 2FA for the admin account."""
    import pyotp

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    secret = data.get('secret', '').strip()
    code = str(data.get('code', '')).strip()

    if not secret or not code or len(code) != 6 or not code.isdigit():
        return jsonify({'error': 'Please enter the 6-digit code from your authenticator app'}), 400

    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        return jsonify({'error': 'Invalid code. Please check your authenticator app and try again.'}), 400

    current_user.totp_secret = secret
    current_user.totp_enabled = True
    db.session.commit()

    logger.info(f'2FA enabled for admin user {current_user.email}')
    return jsonify({'success': True, 'message': '2FA has been enabled'}), 200


@admin_bp.route('/2fa/disable', methods=['POST'])
@require_admin
def disable_2fa():
    """Disable 2FA — requires a valid TOTP code for security."""
    import pyotp

    if not current_user.totp_enabled or not current_user.totp_secret:
        return jsonify({'error': '2FA is not enabled'}), 400

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    code = str(data.get('code', '')).strip()
    if not code or len(code) != 6 or not code.isdigit():
        return jsonify({'error': 'Please enter your current 6-digit code'}), 400

    totp = pyotp.TOTP(current_user.totp_secret)
    if not totp.verify(code, valid_window=1):
        return jsonify({'error': 'Invalid code. 2FA was not disabled.'}), 400

    current_user.totp_secret = None
    current_user.totp_enabled = False
    db.session.commit()

    logger.info(f'2FA disabled for admin user {current_user.email}')
    return jsonify({'success': True, 'message': '2FA has been disabled'}), 200


@admin_bp.route('/2fa/status', methods=['GET'])
@require_admin
def get_2fa_status():
    """Get current 2FA status for the logged-in admin."""
    return jsonify({
        'enabled': bool(current_user.totp_enabled),
    }), 200


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@admin_bp.errorhandler(403)
def forbidden(e):
    return jsonify({'error': 'Access denied. Admin role required.'}), 403


@admin_bp.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404
