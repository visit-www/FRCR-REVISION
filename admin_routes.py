"""
Admin Routes - User Management & Case Management API Endpoints
Provides CRUD operations for user management and case management with role-based access control
"""

from flask import Blueprint, request, jsonify, render_template_string, render_template
from flask_login import login_required, current_user
from models import db, User, UserRole, SubscriptionStatus, CaseAuditLog, Case, AdminActionLog, log_admin_action
from access_control import require_admin, require_role, delete_user_completely, can_delete_user, upgrade_to_paid, downgrade_to_free
from datetime import datetime, timedelta
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
                'subscription_tier': getattr(user, 'subscription_tier', 'free') or 'free',
                'sr_usage_month': user.sr_usage_month or 0,
                'radiq_usage_month': user.radiq_usage_month or 0,
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
            'subscription_tier': getattr(user, 'subscription_tier', 'free') or 'free',
            'sr_usage_month': user.sr_usage_month or 0,
            'radiq_usage_month': user.radiq_usage_month or 0,
            'trial_started_at': user.trial_started_at.isoformat() if user.trial_started_at else None,
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
        # Set 7-day 2FA grace period when promoting to admin
        if new_role == 'admin' and not user.totp_enabled:
            user.totp_grace_period_until = datetime.utcnow() + timedelta(days=7)
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
        log_admin_action(current_user.id, 'role_change', 'user', user.id,
                         {'old_role': old_role, 'new_role': new_role, 'target_email': user.email},
                         request.headers.get('X-Forwarded-For', request.remote_addr))

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
        log_admin_action(current_user.id, 'subscription_change', 'user', user.id,
                         {'old_status': old_status, 'new_status': new_status, 'target_email': user.email},
                         request.headers.get('X-Forwarded-For', request.remote_addr))

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


@admin_bp.route('/users/<int:user_id>/plan', methods=['PUT'])
@require_admin
def update_user_plan(user_id):
    """Change a user's subscription tier (free, standard, elite, elite_pro)."""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json()
        new_tier = data.get('subscription_tier', '').lower()
        valid_tiers = ['free', 'standard', 'elite', 'elite_pro', 'canceled']
        if new_tier not in valid_tiers:
            return jsonify({'error': f'Invalid tier. Valid: {valid_tiers}'}), 400

        old_tier = getattr(user, 'subscription_tier', 'free') or 'free'
        user.subscription_tier = new_tier
        db.session.commit()

        logger.info("Admin %s changed %s plan from %s to %s",
                     current_user.email, user.email, old_tier, new_tier)
        log_admin_action(current_user.id, 'plan_change', 'user', user.id,
                         {'old_tier': old_tier, 'new_tier': new_tier,
                          'target_email': user.email},
                         request.headers.get('X-Forwarded-For', request.remote_addr))

        return jsonify({
            'message': f'Plan updated from {old_tier} to {new_tier}',
            'old_tier': old_tier, 'new_tier': new_tier,
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.error("Error updating plan: %s", e)
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
        log_admin_action(current_user.id, 'toggle_active', 'user', user.id,
                         {'old_active': old_status, 'new_active': is_active, 'target_email': user.email},
                         request.headers.get('X-Forwarded-For', request.remote_addr))

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
# RESET USER AI QUOTA
# ============================================================================

@admin_bp.route('/users/<int:user_id>/reset-quota', methods=['POST'])
@require_admin
def reset_user_quota(user_id):
    """Reset a user's monthly AI usage counters (SR + RadIQ)."""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        old_sr = user.sr_usage_month or 0
        old_radiq = user.radiq_usage_month or 0
        user.sr_usage_month = 0
        user.radiq_usage_month = 0
        db.session.commit()

        logger.info("Admin %s reset quota for %s (sr=%d→0, radiq=%d→0)",
                     current_user.email, user.email, old_sr, old_radiq)
        log_admin_action(current_user.id, 'reset_quota', 'user', user.id,
                         {'old_sr': old_sr, 'old_radiq': old_radiq,
                          'target_email': user.email},
                         request.headers.get('X-Forwarded-For', request.remote_addr))

        return jsonify({
            'message': f'Quota reset for {user.email}',
            'old_sr': old_sr, 'old_radiq': old_radiq,
            'new_sr': 0, 'new_radiq': 0,
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.error("Error resetting quota: %s", e)
        return jsonify({'error': str(e)}), 500


# ============================================================================
# ADMIN PASSWORD RESET (send reset link to user)
# ============================================================================

@admin_bp.route('/users/<int:user_id>/send-password-reset', methods=['POST'])
@require_admin
def admin_send_password_reset(user_id):
    """Send a password reset email to the user (admin-initiated)."""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        if not user.email:
            return jsonify({'error': 'User has no email address'}), 400

        # Generate token and send email (same flow as forgot-password)
        token = user.generate_recovery_token()
        db.session.commit()

        from auth import send_recovery_email
        email_sent = send_recovery_email(user.email, token)

        logger.info("Admin %s sent password reset to %s (sent=%s)",
                     current_user.email, user.email, email_sent)
        log_admin_action(current_user.id, 'send_password_reset', 'user', user.id,
                         {'target_email': user.email, 'email_sent': email_sent},
                         request.headers.get('X-Forwarded-For', request.remote_addr))

        if email_sent:
            return jsonify({'message': f'Password reset email sent to {user.email}'}), 200
        else:
            return jsonify({'error': 'Failed to send email. Check email configuration.'}), 500
    except Exception as e:
        db.session.rollback()
        logger.error("Error sending password reset: %s", e)
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
        log_admin_action(current_user.id, 'delete_user', 'user', user_id,
                         {'target_email': email, 'target_role': user_role, 'cleanup_stats': stats},
                         request.headers.get('X-Forwarded-For', request.remote_addr))

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
        log_admin_action(current_user.id, 'delete_case', 'case', case_id,
                         {'case_title': getattr(case, 'title', None)},
                         request.headers.get('X-Forwarded-For', request.remote_addr))

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
        model = data.get('model', 'claude-sonnet-4-6')

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


@admin_bp.route('/moderation/user-drafts/<int:draft_id>/preview', methods=['GET'])
@require_admin
def preview_user_draft(draft_id):
    """Get full HTML preview of a user-generated algorithm draft."""
    from models import ReportingAlgorithm
    draft = ReportingAlgorithm.query.get_or_404(draft_id)
    creator = User.query.get(draft.created_by_user_id) if draft.created_by_user_id else None
    return jsonify({
        'id': draft.id,
        'title': draft.title,
        'category': draft.category,
        'body_section': draft.body_section,
        'description': draft.description,
        'algorithm_html': draft.algorithm_html or '',
        'template_html': draft.template_html or '',
        'username': creator.full_name if creator else 'Unknown',
        'created_at': draft.created_at.isoformat() if draft.created_at else None,
    }), 200


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
    if not totp.verify(code, valid_window=2):
        return jsonify({'error': 'Invalid code. Please check your authenticator app and try again.'}), 400

    import secrets as secrets_mod
    import hashlib

    current_user.totp_secret = secret
    current_user.totp_enabled = True

    # Generate 8 backup codes
    plaintext_codes = [secrets_mod.token_hex(4) for _ in range(8)]
    hashed_codes = [hashlib.sha256(c.encode()).hexdigest() for c in plaintext_codes]
    current_user.totp_backup_codes = json.dumps(hashed_codes)

    db.session.commit()

    logger.info(f'2FA enabled for admin user {current_user.email}')
    return jsonify({
        'success': True,
        'message': '2FA has been enabled',
        'backup_codes': plaintext_codes
    }), 200


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
    if not totp.verify(code, valid_window=2):
        return jsonify({'error': 'Invalid code. 2FA was not disabled.'}), 400

    current_user.totp_secret = None
    current_user.totp_enabled = False
    current_user.totp_backup_codes = None
    db.session.commit()

    logger.info(f'2FA disabled for admin user {current_user.email}')
    return jsonify({'success': True, 'message': '2FA has been disabled'}), 200


@admin_bp.route('/2fa/status', methods=['GET'])
@require_admin
def get_2fa_status():
    """Get current 2FA status for the logged-in admin."""
    has_backup = False
    if current_user.totp_backup_codes:
        try:
            codes = json.loads(current_user.totp_backup_codes)
            has_backup = len(codes) > 0
        except (json.JSONDecodeError, TypeError):
            pass
    return jsonify({
        'enabled': bool(current_user.totp_enabled),
        'has_backup_codes': has_backup,
    }), 200


@admin_bp.route('/2fa/regenerate-backup-codes', methods=['POST'])
@require_admin
def regenerate_backup_codes():
    """Regenerate backup codes — requires a valid TOTP code."""
    import pyotp
    import secrets as secrets_mod
    import hashlib

    if not current_user.totp_enabled or not current_user.totp_secret:
        return jsonify({'error': '2FA is not enabled'}), 400

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    code = str(data.get('code', '')).strip()
    if not code or len(code) != 6 or not code.isdigit():
        return jsonify({'error': 'Please enter your current 6-digit code'}), 400

    totp = pyotp.TOTP(current_user.totp_secret)
    if not totp.verify(code, valid_window=2):
        return jsonify({'error': 'Invalid code'}), 400

    plaintext_codes = [secrets_mod.token_hex(4) for _ in range(8)]
    hashed_codes = [hashlib.sha256(c.encode()).hexdigest() for c in plaintext_codes]
    current_user.totp_backup_codes = json.dumps(hashed_codes)
    db.session.commit()

    logger.info(f'Backup codes regenerated for admin user {current_user.email}')
    return jsonify({
        'success': True,
        'backup_codes': plaintext_codes
    }), 200


# ============================================================================
# AI COST TRACKER
# ============================================================================

# Cost calculation — delegated to standalone ai_cost_tracker module
from ai_cost_tracker import calc_cost as _calc_cost, MODEL_COSTS, DEFAULT_MODEL_COST


@admin_bp.route('/ai-costs', methods=['GET'])
@require_admin
def ai_costs():
    """
    Aggregate AI usage costs from AIAuditLog.

    Query params:
        days  — lookback period (default 30)
        user_id — optional single-user filter
    """
    from models import AIAuditLog
    from sqlalchemy import func

    days = request.args.get('days', 30, type=int)
    days = min(max(days, 1), 365)
    user_id_filter = request.args.get('user_id', type=int)

    cutoff = datetime.utcnow() - timedelta(days=days)

    try:
        base_q = AIAuditLog.query.filter(AIAuditLog.created_at >= cutoff)
        if user_id_filter:
            base_q = base_q.filter(AIAuditLog.user_id == user_id_filter)

        rows = base_q.all()

        # ── Summary ──
        total_requests = len(rows)
        total_cost = sum(_calc_cost(r.model, r.input_tokens, r.output_tokens) for r in rows)
        avg_cost = round(total_cost / total_requests, 6) if total_requests else 0

        date_from = cutoff.strftime('%Y-%m-%d')
        date_to = datetime.utcnow().strftime('%Y-%m-%d')

        # ── By user ──
        user_map = {}
        for r in rows:
            uid = r.user_id or 0
            if uid not in user_map:
                user_map[uid] = {'input_tokens': 0, 'output_tokens': 0, 'requests': 0}
            user_map[uid]['input_tokens'] += r.input_tokens or 0
            user_map[uid]['output_tokens'] += r.output_tokens or 0
            user_map[uid]['requests'] += 1

        # Batch-fetch usernames
        user_ids = [uid for uid in user_map if uid]
        users_by_id = {}
        if user_ids:
            for u in User.query.filter(User.id.in_(user_ids)).all():
                users_by_id[u.id] = u

        # Pre-calculate per-user costs using actual model data
        user_costs = {}
        for r in rows:
            uid = r.user_id or 0
            user_costs[uid] = user_costs.get(uid, 0) + _calc_cost(r.model, r.input_tokens, r.output_tokens)

        by_user = []
        for uid, data in user_map.items():
            u = users_by_id.get(uid)
            by_user.append({
                'user_id': uid,
                'username': u.full_name if u else ('System' if uid == 0 else 'Unknown'),
                'email': u.email if u else '',
                'requests': data['requests'],
                'input_tokens': data['input_tokens'],
                'output_tokens': data['output_tokens'],
                'cost_usd': round(user_costs.get(uid, 0), 4),
            })
        by_user.sort(key=lambda x: -x['cost_usd'])

        # ── By action ──
        action_map = {}
        for r in rows:
            act = r.action or 'unknown'
            if act not in action_map:
                action_map[act] = {'requests': 0, 'cost': 0}
            action_map[act]['requests'] += 1
            action_map[act]['cost'] += _calc_cost(r.model, r.input_tokens, r.output_tokens)
        by_action = [
            {'action': act, 'requests': d['requests'], 'cost_usd': round(d['cost'], 4)}
            for act, d in sorted(action_map.items(), key=lambda x: -x[1]['cost'])
        ]

        # ── By day ──
        day_map = {}
        for r in rows:
            day_key = r.created_at.strftime('%Y-%m-%d') if r.created_at else 'unknown'
            if day_key not in day_map:
                day_map[day_key] = {'requests': 0, 'cost': 0}
            day_map[day_key]['requests'] += 1
            day_map[day_key]['cost'] += _calc_cost(r.model, r.input_tokens, r.output_tokens)
        by_day = [
            {'date': d, 'requests': v['requests'], 'cost_usd': round(v['cost'], 4)}
            for d, v in sorted(day_map.items())
        ]

        # ── By model ──
        model_map = {}
        for r in rows:
            m = r.model or 'unknown'
            if m not in model_map:
                model_map[m] = {'requests': 0, 'cost': 0, 'input_tokens': 0, 'output_tokens': 0}
            model_map[m]['requests'] += 1
            model_map[m]['input_tokens'] += r.input_tokens or 0
            model_map[m]['output_tokens'] += r.output_tokens or 0
            model_map[m]['cost'] += _calc_cost(r.model, r.input_tokens, r.output_tokens)
        by_model = [
            {'model': m, 'requests': d['requests'], 'cost_usd': round(d['cost'], 4),
             'input_tokens': d['input_tokens'], 'output_tokens': d['output_tokens']}
            for m, d in sorted(model_map.items(), key=lambda x: -x[1]['cost'])
        ]

        # ── By category: admin generation vs user interaction ──
        # Actions that are admin/content generation (one-time setup cost)
        _ADMIN_ACTIONS = {
            'generate_algorithm', 'generate_radiology_template', 'generate_anatomy',
            'generate_pearl', 'generate_tnm', 'generate_protocol', 'regenerate_protocol',
            'generate_if_calculator', 'generate_case_data', 'generate_tree',
            'cost_tracking_reset_v1',
        }
        # Actions that are user interaction (per-user recurring cost)
        _USER_ACTIONS = {
            'ai_assist', 'ask_claude', 'review_report', 'quick_review',
            'radiq_query', 'vetting_analyse', 'vetting_protocol',
            'generate_mdt_summary',
        }
        # report_action_* are user interactions
        admin_cost = 0.0
        admin_requests = 0
        user_cost = 0.0
        user_requests = 0
        action_cost = 0.0
        action_requests = 0
        for r in rows:
            c = _calc_cost(r.model, r.input_tokens, r.output_tokens)
            act = r.action or ''
            if act in _ADMIN_ACTIONS:
                admin_cost += c
                admin_requests += 1
            elif act in _USER_ACTIONS or act.startswith('report_action_'):
                user_cost += c
                user_requests += 1
            else:
                # Uncategorised — count as user
                user_cost += c
                user_requests += 1

        # ── By model family (simplified: Opus / Sonnet / Haiku) ──
        family_map = {'opus': {'requests': 0, 'cost': 0.0},
                      'sonnet': {'requests': 0, 'cost': 0.0},
                      'haiku': {'requests': 0, 'cost': 0.0},
                      'other': {'requests': 0, 'cost': 0.0}}
        for r in rows:
            c = _calc_cost(r.model, r.input_tokens, r.output_tokens)
            m = (r.model or '').lower()
            if 'opus' in m:
                family_map['opus']['requests'] += 1
                family_map['opus']['cost'] += c
            elif 'haiku' in m:
                family_map['haiku']['requests'] += 1
                family_map['haiku']['cost'] += c
            elif 'sonnet' in m or m:
                family_map['sonnet']['requests'] += 1
                family_map['sonnet']['cost'] += c
            else:
                family_map['other']['requests'] += 1
                family_map['other']['cost'] += c
        by_family = [
            {'family': f, 'requests': d['requests'], 'cost_usd': round(d['cost'], 4)}
            for f, d in family_map.items() if d['requests'] > 0
        ]

        return jsonify({
            'summary': {
                'total_requests': total_requests,
                'total_cost_usd': round(total_cost, 4),
                'avg_cost_per_request': round(avg_cost, 6),
                'date_range': {'from': date_from, 'to': date_to},
            },
            'by_category': {
                'admin_generation': {
                    'requests': admin_requests,
                    'cost_usd': round(admin_cost, 4),
                    'description': 'One-time content creation (algorithms, templates, protocols, TNM, cases)',
                },
                'user_interaction': {
                    'requests': user_requests,
                    'cost_usd': round(user_cost, 4),
                    'description': 'Per-user recurring (reports, Q&A, reviews, vetting, RadIQ, SBA/Viva)',
                },
            },
            'by_user': by_user,
            'by_action': by_action,
            'by_day': by_day,
            'by_model': by_model,
            'by_family': by_family,
        }), 200

    except Exception as e:
        logger.error(f"Error fetching AI costs: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# RADINSIGHT AI DOCUMENTATION
# ============================================================================

@admin_bp.route('/ai-documentation')
@require_admin
def ai_documentation():
    """Admin page: AI documentation — serves from DB if available, falls back to template."""
    from models import AdminDocument
    doc = AdminDocument.query.filter_by(slug='ai-documentation').first()
    if doc:
        return render_template('admin_doc_view.html', doc=doc)
    from ai_cost_tracker import MODEL_COSTS
    return render_template('admin_ai_documentation.html', model_costs=MODEL_COSTS)


@admin_bp.route('/marketing')
@require_admin
def admin_marketing():
    """Admin page: marketing — serves from DB if available, falls back to template."""
    from models import AdminDocument
    doc = AdminDocument.query.filter_by(slug='marketing').first()
    if doc:
        return render_template('admin_doc_view.html', doc=doc)
    return render_template('admin_marketing.html')


@admin_bp.route('/docs-hub')
@require_admin
def admin_docs_hub():
    """Admin page: documentation hub — links to all admin docs."""
    from models import AdminDocument, ClaudeMemoryUpdate
    db_docs = AdminDocument.query.filter(AdminDocument.category != '_system').order_by(AdminDocument.category, AdminDocument.title).all()
    pending_sync = ClaudeMemoryUpdate.query.filter_by(is_synced=False).count()
    return render_template('admin_docs_hub.html', db_docs=db_docs, pending_sync=pending_sync)


@admin_bp.route('/seo-audit')
@require_admin
def admin_seo_audit():
    """Admin page: SEO audit — serves from DB if available, falls back to template."""
    from models import AdminDocument
    doc = AdminDocument.query.filter_by(slug='seo-audit').first()
    if doc:
        return render_template('admin_doc_view.html', doc=doc)
    return render_template('admin_seo_audit.html')


@admin_bp.route('/reset-ai-costs', methods=['POST'])
@require_admin
def reset_ai_costs():
    """One-time: delete ALL AIAuditLog rows to start fresh. Admin only."""
    from models import AIAuditLog
    try:
        count = AIAuditLog.query.delete(synchronize_session=False)
        db.session.commit()
        logger.info("Admin %s reset AI costs: deleted %d rows", current_user.email, count)
        return jsonify({'success': True, 'deleted': count, 'message': f'Deleted {count} audit log rows. Dashboard is now fresh.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# ADMIN AUDIT LOG
# ============================================================================

@admin_bp.route('/audit-log', methods=['GET'])
@require_admin
def get_audit_log():
    """Paginated admin audit log with optional filtering."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 200)
        action_filter = request.args.get('action')
        user_filter = request.args.get('user_id', type=int)

        query = AdminActionLog.query.order_by(AdminActionLog.created_at.desc())
        if action_filter:
            query = query.filter(AdminActionLog.action == action_filter)
        if user_filter:
            query = query.filter(AdminActionLog.user_id == user_filter)

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        entries = []
        for e in pagination.items:
            admin_user = User.query.get(e.user_id) if e.user_id else None
            entries.append({
                'id': e.id,
                'user_id': e.user_id,
                'admin_email': admin_user.email if admin_user else 'System',
                'action': e.action,
                'target_type': e.target_type,
                'target_id': e.target_id,
                'details': json.loads(e.details) if e.details else None,
                'ip_address': e.ip_address,
                'created_at': e.created_at.isoformat() if e.created_at else None,
            })

        return jsonify({
            'entries': entries,
            'page': pagination.page,
            'pages': pagination.pages,
            'total': pagination.total,
        }), 200

    except Exception as e:
        logger.error(f"Error fetching audit log: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# RADIQ FLAGGED RESPONSES
# ============================================================================

@admin_bp.route('/radiq/flagged', methods=['GET'])
@require_admin
def list_radiq_flagged():
    """List unresolved flagged RadIQ responses."""
    from models import RadIQFeedback, RadIQQuery
    feedbacks = (
        db.session.query(RadIQFeedback)
        .join(RadIQQuery, RadIQFeedback.query_id == RadIQQuery.id)
        .filter(RadIQFeedback.is_resolved == False)
        .order_by(RadIQFeedback.created_at.desc())
        .limit(100)
        .all()
    )
    results = []
    for f in feedbacks:
        q = f.query
        flagger = User.query.get(f.user_id)
        results.append({
            'id': f.id,
            'query_id': f.query_id,
            'category': q.category if q else '',
            'question': (q.question[:200] + '...') if q and len(q.question) > 200 else (q.question if q else ''),
            'response_excerpt': (q.response_text[:300] + '...') if q and q.response_text and len(q.response_text) > 300 else (q.response_text if q else ''),
            'full_response': q.response_text if q else '',
            'reason': f.reason,
            'details': f.details,
            'flagger_email': flagger.email if flagger else 'Unknown',
            'created_at': f.created_at.isoformat() if f.created_at else None,
        })
    return jsonify({'flagged': results, 'count': len(results)}), 200


@admin_bp.route('/radiq/feedback/<int:feedback_id>/resolve', methods=['POST'])
@require_admin
def resolve_radiq_feedback(feedback_id):
    """Resolve a flagged RadIQ response."""
    from models import RadIQFeedback
    feedback = db.session.query(RadIQFeedback).get(feedback_id)
    if not feedback:
        return jsonify({'error': 'Feedback not found.'}), 404
    if feedback.is_resolved:
        return jsonify({'error': 'Already resolved.'}), 400

    data = request.get_json() or {}
    feedback.is_resolved = True
    feedback.resolved_by_user_id = current_user.id
    feedback.resolved_at = datetime.utcnow()
    feedback.resolution_notes = (data.get('notes') or '').strip() or None

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to resolve RadIQ feedback %d: %s", feedback_id, e)
        return jsonify({'error': 'Failed to resolve.'}), 500

    logger.info("Admin %s resolved RadIQ feedback #%d", current_user.email, feedback_id)
    return jsonify({'success': True}), 200


@admin_bp.route('/radiq/flagged/count', methods=['GET'])
@require_admin
def radiq_flagged_count():
    """Return count of unresolved RadIQ flags."""
    from models import RadIQFeedback
    # RadIQFeedback has a 'query' relationship that shadows Model.query
    count = db.session.query(RadIQFeedback).filter_by(is_resolved=False).count()
    return jsonify({'count': count}), 200


# ============================================================================
# EDITABLE ADMIN DOCUMENTS
# ============================================================================

@admin_bp.route('/documents', methods=['GET'])
@require_admin
def list_documents():
    """List all editable admin documents."""
    from models import AdminDocument
    docs = AdminDocument.query.order_by(AdminDocument.category, AdminDocument.title).all()
    return jsonify({'documents': [d.to_dict() for d in docs]})


@admin_bp.route('/documents/<slug>', methods=['GET'])
@require_admin
def get_document(slug):
    """Get a single document by slug."""
    from models import AdminDocument
    doc = AdminDocument.query.filter_by(slug=slug).first()
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    return jsonify(doc.to_dict())


@admin_bp.route('/documents/<slug>', methods=['PUT'])
@require_admin
def save_document(slug):
    """Save TinyMCE edits to a document."""
    from models import AdminDocument
    doc = AdminDocument.query.filter_by(slug=slug).first()
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    data = request.get_json(silent=True) or {}
    if 'content_html' in data:
        doc.content_html = data['content_html']
    if 'title' in data:
        doc.title = data['title']
    if 'category' in data:
        doc.category = data['category']
    doc.last_edited_by = current_user.id

    try:
        # Auto-create memory sync entry on every save
        from models import ClaudeMemoryUpdate
        sync = ClaudeMemoryUpdate(
            category='project',
            summary=f'Document updated: {doc.title}',
            details=f'Admin edited "{doc.title}" ({slug}) — category: {doc.category}',
            source_doc_slug=slug,
            created_by=current_user.id,
        )
        db.session.add(sync)
        db.session.commit()
        log_admin_action(current_user.id, 'document_edit', details=f'Edited document: {slug}')
        return jsonify({'success': True, 'document': doc.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/documents', methods=['POST'])
@require_admin
def create_document():
    """Create a new admin document."""
    from models import AdminDocument
    data = request.get_json(silent=True) or {}
    slug = data.get('slug', '').strip()
    title = data.get('title', '').strip()
    if not slug or not title:
        return jsonify({'error': 'slug and title are required'}), 400

    if AdminDocument.query.filter_by(slug=slug).first():
        return jsonify({'error': f'Document with slug "{slug}" already exists'}), 409

    doc = AdminDocument(
        slug=slug,
        title=title,
        category=data.get('category', 'general'),
        content_html=data.get('content_html', ''),
        last_edited_by=current_user.id,
    )
    db.session.add(doc)
    try:
        db.session.commit()
        log_admin_action(current_user.id, 'document_create', details=f'Created document: {slug}')
        return jsonify({'success': True, 'document': doc.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/documents/<slug>', methods=['DELETE'])
@require_admin
def delete_document(slug):
    """Delete a document and auto-sync the deletion to Claude memory."""
    from models import AdminDocument, ClaudeMemoryUpdate
    doc = AdminDocument.query.filter_by(slug=slug).first()
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    title = doc.title
    category = doc.category
    sync = ClaudeMemoryUpdate(
        category='project',
        summary=f'Document deleted: {title}',
        details=f'Admin deleted "{title}" ({slug}) — was in category: {category}',
        source_doc_slug=slug,
        created_by=current_user.id,
    )
    db.session.add(sync)
    db.session.delete(doc)
    try:
        db.session.commit()
        log_admin_action(current_user.id, 'document_delete', details=f'Deleted document: {slug}')
        return jsonify({'success': True, 'deleted': slug})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/documents/<slug>/edit', methods=['GET'])
@require_admin
def edit_document_page(slug):
    """Render the TinyMCE editor page for a document."""
    from models import AdminDocument
    doc = AdminDocument.query.filter_by(slug=slug).first()
    if not doc:
        return "Document not found", 404
    return render_template('admin_doc_editor.html', doc=doc)


@admin_bp.route('/documents/<slug>/view', methods=['GET'])
@require_admin
def view_document_page(slug):
    """Render a read-only view of a DB-stored document."""
    from models import AdminDocument
    doc = AdminDocument.query.filter_by(slug=slug).first()
    if not doc:
        return "Document not found", 404
    return render_template('admin_doc_view.html', doc=doc)


# ============================================================================
# TOUR CAPTURE
# ============================================================================

@admin_bp.route('/tour-capture', methods=['GET'])
@require_admin
def tour_capture_page():
    """Render the tour capture form."""
    return render_template('admin_tour_capture.html')


@admin_bp.route('/tour-capture/save', methods=['POST'])
@require_admin
def save_tour_capture():
    """Save a captured test step."""
    from models import TourCapture
    data = request.get_json(silent=True) or {}
    if not data.get('tour_name') or not data.get('step_label'):
        return jsonify({'error': 'tour_name and step_label required'}), 400

    capture = TourCapture(
        tour_name=data['tour_name'],
        step_number=data.get('step_number', 0),
        step_label=data['step_label'],
        user_input=data.get('user_input', ''),
        response_json=data.get('response_json', ''),
        notes=data.get('notes', ''),
        screenshot_url=data.get('screenshot_url', ''),
    )
    db.session.add(capture)
    try:
        db.session.commit()
        return jsonify({'success': True, 'capture': capture.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/tour-capture/list', methods=['GET'])
@require_admin
def list_tour_captures():
    """List all captured steps, optionally filtered by tour_name."""
    from models import TourCapture
    tour = request.args.get('tour')
    q = TourCapture.query.order_by(TourCapture.tour_name, TourCapture.step_number)
    if tour:
        q = q.filter_by(tour_name=tour)
    return jsonify({'captures': [c.to_dict() for c in q.all()]})


@admin_bp.route('/tour-capture/<int:capture_id>', methods=['DELETE'])
@require_admin
def delete_tour_capture(capture_id):
    """Delete a captured step."""
    from models import TourCapture
    capture = TourCapture.query.get(capture_id)
    if not capture:
        return jsonify({'error': 'Not found'}), 404
    db.session.delete(capture)
    db.session.commit()
    return jsonify({'success': True})


# ============================================================================
# MANUAL VERIFICATION (Admin PubMed search + verify)
# ============================================================================

@admin_bp.route('/verify-search', methods=['GET'])
@require_admin
def admin_verify_search():
    """Search PubMed + Radiopaedia for verification. Returns combined results."""
    query = request.args.get('q', '').strip()
    source = request.args.get('source', 'all')  # pubmed, radiopaedia, all
    if not query or len(query) < 3:
        return jsonify({'error': 'Query too short (min 3 chars)'}), 400

    results = []

    # PubMed
    if source in ('pubmed', 'all'):
        try:
            from pubmed_service import search_pubmed
            pm_results = search_pubmed(query, max_results=5)
            for r in pm_results:
                r['source'] = 'pubmed'
            results.extend(pm_results)
        except Exception as e:
            logger.warning("PubMed search failed for '%s': %s", query, e)

    # Radiopaedia articles (via DuckDuckGo scoped search — Radiopaedia renders client-side)
    if source in ('radiopaedia', 'all'):
        try:
            import requests as _req
            from bs4 import BeautifulSoup
            _ddg_resp = _req.post(
                'https://html.duckduckgo.com/html/',
                data={'q': f'site:radiopaedia.org/articles {query}'},
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'},
                timeout=10,
            )
            if _ddg_resp.status_code == 200:
                _ddg_soup = BeautifulSoup(_ddg_resp.text, 'html.parser')
                for a in _ddg_soup.select('.result__a')[:5]:
                    href = a.get('href', '')
                    title = a.get_text(strip=True)
                    if 'radiopaedia.org/articles/' in href and title:
                        # Clean URL (DuckDuckGo may add tracking params)
                        clean_url = href.split('?')[0] if '?' in href else href
                        if not clean_url.startswith('http'):
                            continue
                        results.append({
                            'source': 'radiopaedia',
                            'title': title,
                            'pubmed_link': clean_url,
                            'authors': [],
                            'journal': 'Radiopaedia.org',
                            'year': '',
                            'doi': None,
                            'pmid': None,
                            'has_free_full_text': True,
                        })
        except Exception as e:
            logger.warning("Radiopaedia search failed for '%s': %s", query, e)

    return jsonify({'results': results, 'query': query})


@admin_bp.route('/manual-verify', methods=['POST'])
@require_admin
def save_manual_verification():
    """Save a manual verification (admin selected text + PubMed reference)."""
    from models import ManualVerification
    data = request.get_json(silent=True) or {}
    selected = (data.get('selected_text') or '').strip()
    if not selected:
        return jsonify({'error': 'selected_text is required'}), 400

    mv = ManualVerification(
        content_type=(data.get('content_type') or 'unknown')[:50],
        content_id=(data.get('content_id') or '')[:100],
        selected_text=selected[:1000],
        custom_label=(data.get('custom_label') or '')[:1000] or None,
        pubmed_doi=(data.get('pubmed_doi') or '')[:200] or None,
        pubmed_pmid=(data.get('pubmed_pmid') or '')[:20] or None,
        pubmed_title=(data.get('pubmed_title') or '')[:500] or None,
        pubmed_authors=(data.get('pubmed_authors') or '')[:500] or None,
        pubmed_journal=(data.get('pubmed_journal') or '')[:200] or None,
        pubmed_year=(data.get('pubmed_year') or '')[:10] or None,
        verified_by_user_id=current_user.id,
    )
    db.session.add(mv)
    try:
        db.session.commit()
        return jsonify({'success': True, 'verification': mv.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/manual-verify', methods=['GET'])
@require_admin
def list_manual_verifications():
    """List manual verifications, optionally filtered by content_type/content_id."""
    from models import ManualVerification
    q = ManualVerification.query.order_by(ManualVerification.created_at.desc())
    ct = request.args.get('content_type')
    if ct:
        q = q.filter_by(content_type=ct)
    cid = request.args.get('content_id')
    if cid:
        q = q.filter_by(content_id=cid)
    return jsonify({'verifications': [v.to_dict() for v in q.limit(100).all()]})


@admin_bp.route('/manual-verify/<int:mv_id>', methods=['DELETE'])
@require_admin
def delete_manual_verification(mv_id):
    """Delete a manual verification."""
    from models import ManualVerification
    mv = ManualVerification.query.get(mv_id)
    if not mv:
        return jsonify({'error': 'Not found'}), 404
    db.session.delete(mv)
    db.session.commit()
    return jsonify({'success': True})


# ============================================================================
# CONTENT FLAGS (Global — submit open to all users, manage admin-only)
# ============================================================================

@admin_bp.route('/content-flags', methods=['POST'])
@login_required
def submit_content_flag():
    """Submit a content flag (any authenticated user)."""
    from models import PeerReviewFlag
    data = request.get_json(silent=True) or {}
    details = (data.get('details') or '').strip()
    if not details:
        return jsonify({'error': 'Please describe the issue.'}), 400

    flag = PeerReviewFlag(
        user_id=current_user.id,
        content_type=(data.get('content_type') or 'unknown')[:50],
        content_id=(data.get('content_id') or '')[:100],
        error_type=(data.get('error_type') or '')[:50],
        severity=(data.get('severity') or 'medium')[:10],
        selected_text=(data.get('selected_text') or '')[:1000],
        details=details[:2000],
        page_url=(data.get('page_url') or '')[:500],
    )
    db.session.add(flag)
    try:
        db.session.commit()
        logger.info("Content flag submitted: type=%s error=%s user=%d", flag.content_type, flag.error_type, current_user.id)
        return jsonify({'success': True, 'flag_id': flag.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/content-flags', methods=['GET'])
@require_admin
def list_content_flags():
    """List content flags with optional filters."""
    from models import PeerReviewFlag
    q = PeerReviewFlag.query.order_by(PeerReviewFlag.created_at.desc())

    ct = request.args.get('content_type')
    if ct:
        q = q.filter_by(content_type=ct)
    et = request.args.get('error_type')
    if et:
        q = q.filter_by(error_type=et)
    sev = request.args.get('severity')
    if sev:
        q = q.filter_by(severity=sev)
    resolved = request.args.get('resolved')
    if resolved == 'true':
        q = q.filter_by(is_resolved=True)
    elif resolved == 'false':
        q = q.filter_by(is_resolved=False)

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'flags': [f.to_dict() for f in paginated.items],
        'total': paginated.total,
        'pages': paginated.pages,
        'page': page,
    })


@admin_bp.route('/content-flags/<int:flag_id>/resolve', methods=['POST'])
@require_admin
def resolve_content_flag(flag_id):
    """Resolve a content flag."""
    from models import PeerReviewFlag
    flag = PeerReviewFlag.query.get(flag_id)
    if not flag:
        return jsonify({'error': 'Flag not found'}), 404

    data = request.get_json(silent=True) or {}
    flag.is_resolved = True
    flag.resolved_by_user_id = current_user.id
    flag.resolved_at = datetime.utcnow()
    flag.resolution_notes = (data.get('notes') or '')[:2000]

    try:
        db.session.commit()
        log_admin_action(current_user.id, 'flag_resolve', details=f'Resolved flag #{flag_id}')
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/content-flags/<int:flag_id>/dismiss', methods=['POST'])
@require_admin
def dismiss_content_flag(flag_id):
    """Dismiss a content flag (resolve without action)."""
    from models import PeerReviewFlag
    flag = PeerReviewFlag.query.get(flag_id)
    if not flag:
        return jsonify({'error': 'Flag not found'}), 404

    flag.is_resolved = True
    flag.resolved_by_user_id = current_user.id
    flag.resolved_at = datetime.utcnow()
    flag.resolution_notes = 'Dismissed'
    try:
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/content-flags/count', methods=['GET'])
@require_admin
def content_flags_count():
    """Return count of unresolved flags."""
    from models import PeerReviewFlag
    count = PeerReviewFlag.query.filter_by(is_resolved=False).count()
    return jsonify({'count': count})


# ============================================================================
# CLAUDE MEMORY SYNC
# ============================================================================

@admin_bp.route('/claude-memory-sync', methods=['GET'])
@require_admin
def get_memory_updates():
    """Get unsynced memory updates for Claude coding agent."""
    from models import ClaudeMemoryUpdate
    updates = ClaudeMemoryUpdate.query.filter_by(is_synced=False)\
        .order_by(ClaudeMemoryUpdate.created_at.asc()).all()
    return jsonify({'updates': [u.to_dict() for u in updates], 'count': len(updates)})


@admin_bp.route('/claude-memory-sync', methods=['POST'])
@require_admin
def create_memory_update():
    """Create a new memory update (from 'Sync to Dev Notes' button)."""
    from models import ClaudeMemoryUpdate
    data = request.get_json(silent=True) or {}
    summary = data.get('summary', '').strip()
    if not summary:
        return jsonify({'error': 'summary is required'}), 400

    update = ClaudeMemoryUpdate(
        category=data.get('category', 'project'),
        summary=summary,
        details=data.get('details', ''),
        source_doc_slug=data.get('source_doc_slug'),
        created_by=current_user.id,
    )
    db.session.add(update)
    try:
        db.session.commit()
        return jsonify({'success': True, 'update': update.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/claude-memory-sync/mark-synced', methods=['POST'])
@require_admin
def mark_memory_synced():
    """Mark all unsynced memory updates as synced."""
    from models import ClaudeMemoryUpdate
    updates = ClaudeMemoryUpdate.query.filter_by(is_synced=False).all()
    count = len(updates)
    for u in updates:
        u.is_synced = True
        u.synced_at = datetime.utcnow()
    try:
        db.session.commit()
        return jsonify({'success': True, 'synced_count': count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# ============================================================================
# CROSS-MODEL VERIFICATION (CMV) — PEER REVIEW ADMIN
# ============================================================================

@admin_bp.route('/peer-review/claims', methods=['GET'])
@require_admin
def list_cmv_claims():
    """List all CMV claims with filtering. Admin dashboard API."""
    from models import PeerReviewClaim

    content_type = request.args.get('content_type', '')
    content_id = request.args.get('content_id', '')
    content_ids = request.args.get('content_ids', '')  # comma-separated
    verdict = request.args.get('verdict', '')
    override = request.args.get('override', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    query = PeerReviewClaim.query

    if content_type:
        query = query.filter_by(content_type=content_type)
    if content_id:
        query = query.filter_by(content_id=str(content_id))
    elif content_ids:
        id_list = [cid.strip() for cid in content_ids.split(',') if cid.strip()]
        if id_list:
            query = query.filter(PeerReviewClaim.content_id.in_(id_list))
    if verdict:
        query = query.filter_by(gemini_verdict=verdict)
    if override == 'has_override':
        query = query.filter(PeerReviewClaim.admin_override.isnot(None))
    elif override == 'no_override':
        query = query.filter(PeerReviewClaim.admin_override.is_(None))

    query = query.order_by(PeerReviewClaim.created_at.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    # Summary stats
    total_claims = PeerReviewClaim.query.count()
    agreed_count = PeerReviewClaim.query.filter_by(gemini_verdict='agree').count()
    disputed_count = PeerReviewClaim.query.filter_by(gemini_verdict='disagree').count()
    uncertain_count = PeerReviewClaim.query.filter_by(gemini_verdict='uncertain').count()
    admin_reviewed = PeerReviewClaim.query.filter(PeerReviewClaim.admin_override.isnot(None)).count()

    return jsonify({
        'claims': [c.to_dict() for c in paginated.items],
        'total': paginated.total,
        'page': paginated.page,
        'pages': paginated.pages,
        'summary': {
            'total': total_claims,
            'agreed': agreed_count,
            'disputed': disputed_count,
            'uncertain': uncertain_count,
            'admin_reviewed': admin_reviewed,
        },
    })


def _apply_claim_correction(claim, corrected_text):
    """Find-and-replace the original claim text in the source content.

    Handles pipe-delimited claims (e.g. "Sign | Modality | Description")
    by trying to match the longest segment in the content.
    Also strips HTML tags from content for matching, then replaces in the
    original HTML by finding the matching plain-text substring.

    Returns True if content was updated, False if original text not found.
    """
    import re
    from models import ReportingAlgorithm, RadiologyPearl, Case, ImagingProtocol

    original = claim.claim_text
    if not original or not corrected_text:
        return False

    # Map content_type → (model, text_field)
    content_fields = {
        'anatomy_snippet': (ReportingAlgorithm, 'template_html'),
        'reporting_algorithm': (ReportingAlgorithm, 'template_html'),
        'radiology_pearl': (RadiologyPearl, 'pearl_text'),
        'case': (Case, 'discussion'),
        'protocol': (ImagingProtocol, 'detailed_protocol_html'),
    }

    mapping = content_fields.get(claim.content_type)
    if not mapping:
        return False

    model_cls, field_name = mapping
    try:
        record = model_cls.query.get(int(claim.content_id))
    except (ValueError, TypeError):
        return False

    if not record:
        return False

    current_content = getattr(record, field_name, '') or ''
    if not current_content:
        return False

    # Try direct match first (works if claim_text is verbatim from content)
    if original in current_content:
        updated_content = current_content.replace(original, corrected_text, 1)
        setattr(record, field_name, updated_content)
        return True

    # For pipe-delimited claims, try each segment (longest first)
    segments = [s.strip() for s in original.split('|') if s.strip()]
    # Also try semicolon-separated parts within segments
    all_parts = []
    for seg in segments:
        all_parts.append(seg)
        for sub in seg.split(';'):
            sub = sub.strip()
            if sub and sub != seg:
                all_parts.append(sub)

    # Sort by length descending — prefer longest match
    all_parts.sort(key=len, reverse=True)

    # Strip HTML to get plain text for matching
    plain_content = re.sub(r'<[^>]+>', '', current_content)

    for part in all_parts:
        if len(part) < 15:
            continue  # Skip very short segments to avoid false matches
        if part in plain_content:
            # Found in plain text — now find and replace in HTML content
            # The part should appear in the HTML too (just surrounded by tags)
            if part in current_content:
                updated_content = current_content.replace(part, corrected_text, 1)
                setattr(record, field_name, updated_content)
                return True

    return False


@admin_bp.route('/peer-review/claims/<int:claim_id>', methods=['PATCH'])
@require_admin
def update_cmv_claim(claim_id):
    """Admin override on a CMV claim: change verdict, add reference, dismiss."""
    from models import PeerReviewClaim

    claim = PeerReviewClaim.query.get_or_404(claim_id)
    data = request.get_json() or {}

    allowed_overrides = ('verified', 'incorrect', 'dismissed', None)
    override = data.get('admin_override')
    if override is not None and override not in allowed_overrides:
        return jsonify({'error': f'Invalid override value. Allowed: {allowed_overrides}'}), 400

    if 'admin_override' in data:
        claim.admin_override = data['admin_override']
    if 'admin_notes' in data:
        claim.admin_notes = data['admin_notes']
    if 'admin_reference_url' in data:
        claim.admin_reference_url = data['admin_reference_url']
    if 'admin_reference_title' in data:
        claim.admin_reference_title = data['admin_reference_title']

    # Inline content correction: find-and-replace claim text in the source content
    corrected_text = data.get('corrected_claim_text', '').strip()
    content_updated = False
    if corrected_text and corrected_text != claim.claim_text:
        claim.corrected_claim_text = corrected_text
        content_updated = _apply_claim_correction(claim, corrected_text)

    claim.reviewed_by_admin_id = current_user.id
    claim.reviewed_at = datetime.utcnow()

    db.session.commit()
    logger.info("Admin %s updated CMV claim #%d: override=%s content_updated=%s",
                current_user.email, claim_id, claim.admin_override, content_updated)

    result = claim.to_dict()
    result['content_updated'] = content_updated
    return jsonify({'success': True, 'claim': result})


@admin_bp.route('/peer-review/batch-admin-verify', methods=['POST'])
@require_admin
def batch_admin_verify_claims():
    """Batch admin-verify multiple claims in a single transaction."""
    from models import PeerReviewClaim

    data = request.get_json() or {}
    claim_ids = data.get('claim_ids', [])
    override = data.get('admin_override', 'verified')
    notes = data.get('admin_notes') or None

    if not claim_ids:
        return jsonify({'error': 'No claim_ids provided'}), 400

    updated = 0
    for cid in claim_ids:
        claim = PeerReviewClaim.query.get(cid)
        if not claim:
            continue
        claim.admin_override = override
        claim.admin_notes = notes
        claim.reviewed_by_admin_id = current_user.id
        claim.reviewed_at = datetime.utcnow()
        updated += 1

    db.session.commit()
    logger.info("Admin %s batch-verified %d claims (override=%s)", current_user.email, updated, override)

    return jsonify({'success': True, 'updated': updated, 'total': len(claim_ids)})


@admin_bp.route('/peer-review/claims/<int:claim_id>', methods=['DELETE'])
@require_admin
def delete_cmv_claim(claim_id):
    """Delete a CMV claim (noise removal)."""
    from models import PeerReviewClaim

    claim = PeerReviewClaim.query.get_or_404(claim_id)
    db.session.delete(claim)
    db.session.commit()
    logger.info("Admin %s deleted CMV claim #%d", current_user.email, claim_id)

    return jsonify({'success': True})


@admin_bp.route('/peer-review/content-claims', methods=['GET'])
@require_admin
def get_content_claims():
    """Get all CMV claims for a specific content item. Used by client-side badge rendering."""
    from models import PeerReviewClaim
    ctype = request.args.get('content_type', '')
    cid = request.args.get('content_id', '')
    if not ctype:
        return jsonify({'claims': []})
    query = PeerReviewClaim.query.filter_by(content_type=ctype)
    if cid:
        query = query.filter_by(content_id=cid)
    claims = query.order_by(PeerReviewClaim.id).all()
    return jsonify({'claims': [c.to_dict() for c in claims]})


@admin_bp.route('/peer-review/search-content', methods=['GET'])
@require_admin
def search_cmv_content():
    """Search for content items by type and name for CMV verification.

    By default shows unverified items first. If q is provided, searches by name.
    """
    ctype = request.args.get('content_type', '')
    q = request.args.get('q', '').strip()
    show = request.args.get('show', 'unverified')  # unverified, all, verified
    results = []

    # Get IDs that already have CMV claims for this content type
    verified_ids = set()
    try:
        from models import PeerReviewClaim
        existing = db.session.query(PeerReviewClaim.content_id).filter(
            PeerReviewClaim.content_type == ctype
        ).distinct().all()
        verified_ids = {r[0] for r in existing if r[0]}
    except Exception:
        pass

    try:
        if ctype in ('anatomy_snippet', 'reporting_algorithm'):
            from models import ReportingAlgorithm
            query = ReportingAlgorithm.query
            if ctype == 'anatomy_snippet':
                query = query.filter(ReportingAlgorithm.origin == 'anatomy_cache')
            else:
                query = query.filter(ReportingAlgorithm.origin != 'anatomy_cache')
            if q:
                query = query.filter(ReportingAlgorithm.title.ilike(f'%{q}%'))
            items = query.order_by(ReportingAlgorithm.id.desc()).limit(50).all()
            for item in items:
                has_claims = str(item.id) in verified_ids
                if show == 'unverified' and has_claims:
                    continue
                if show == 'verified' and not has_claims:
                    continue
                results.append({
                    'id': item.id,
                    'title': item.title or f'Algorithm #{item.id}',
                    'body_section': item.body_section or '',
                    'has_claims': has_claims,
                })

        elif ctype == 'radiology_pearl':
            from models import RadiologyPearl
            query = RadiologyPearl.query
            if q:
                query = query.filter(RadiologyPearl.pearl_text.ilike(f'%{q}%'))
            items = query.order_by(RadiologyPearl.id.desc()).limit(50).all()
            for item in items:
                has_claims = str(item.id) in verified_ids
                if show == 'unverified' and has_claims:
                    continue
                if show == 'verified' and not has_claims:
                    continue
                results.append({
                    'id': item.id,
                    'title': (item.pearl_text or '')[:80],
                    'body_section': item.body_section or '',
                    'has_claims': has_claims,
                })

        elif ctype == 'radiq_query':
            from models import RadIQQuery
            query = RadIQQuery.query
            if q:
                query = query.filter(RadIQQuery.question.ilike(f'%{q}%'))
            items = query.order_by(RadIQQuery.id.desc()).limit(50).all()
            for item in items:
                has_claims = str(item.id) in verified_ids
                if show == 'unverified' and has_claims:
                    continue
                if show == 'verified' and not has_claims:
                    continue
                results.append({
                    'id': item.id,
                    'title': (item.question or '')[:80],
                    'body_section': '',
                    'has_claims': has_claims,
                })

        elif ctype == 'case':
            from models import Case
            query = Case.query
            if q:
                query = query.filter(db.or_(
                    Case.diagnosis.ilike(f'%{q}%'),
                    Case.case_number.ilike(f'%{q}%'),
                ))
            items = query.order_by(Case.id.desc()).limit(50).all()
            for item in items:
                has_claims = str(item.id) in verified_ids
                if show == 'unverified' and has_claims:
                    continue
                if show == 'verified' and not has_claims:
                    continue
                results.append({
                    'id': item.id,
                    'title': f'{item.case_number or ""} — {item.diagnosis or ""}',
                    'body_section': item.body_part.value if item.body_part else '',
                    'has_claims': has_claims,
                })

        elif ctype == 'radiology_tool':
            from models import IncidentalFindingCalculator
            query = IncidentalFindingCalculator.query
            if q:
                query = query.filter(db.or_(
                    IncidentalFindingCalculator.finding_name.ilike(f'%{q}%'),
                    IncidentalFindingCalculator.keywords.ilike(f'%{q}%'),
                ))
            items = query.order_by(IncidentalFindingCalculator.id.desc()).limit(50).all()
            for item in items:
                has_claims = str(item.id) in verified_ids
                if show == 'unverified' and has_claims:
                    continue
                if show == 'verified' and not has_claims:
                    continue
                results.append({
                    'id': item.id,
                    'title': item.finding_name or f'Tool #{item.id}',
                    'body_section': item.body_section or '',
                    'has_claims': has_claims,
                })

        elif ctype == 'protocol':
            from models import ImagingProtocol
            query = ImagingProtocol.query
            if q:
                query = query.filter(ImagingProtocol.title.ilike(f'%{q}%'))
            items = query.order_by(ImagingProtocol.id.desc()).limit(50).all()
            for item in items:
                has_claims = str(item.id) in verified_ids
                if show == 'unverified' and has_claims:
                    continue
                if show == 'verified' and not has_claims:
                    continue
                results.append({
                    'id': item.id,
                    'title': item.title or f'Protocol #{item.id}',
                    'body_section': getattr(item, 'body_section', '') or '',
                    'has_claims': has_claims,
                })

    except Exception as exc:
        logger.error("CMV content search failed: %s", exc)

    return jsonify({'results': results, 'total': len(results)})


def _has_cmv_claims(content_type, content_id):
    """Check if content already has CMV claims."""
    try:
        from models import PeerReviewClaim
        return PeerReviewClaim.query.filter_by(
            content_type=content_type, content_id=content_id
        ).count() > 0
    except Exception:
        return False


@admin_bp.route('/peer-review/verify-content', methods=['POST'])
@require_admin
def verify_single_content():
    """Re-run CMV on a single content item by type and ID.

    Fetches the content from DB, sends to Gemini, persists claims.
    No regeneration needed — just re-verifies existing content.
    """
    from gemini_verify import verify_content
    from radinsight_peer_review import _persist_claims

    data = request.get_json() or {}
    ctype = data.get('content_type', '')
    cid = data.get('content_id', '')

    if not ctype:
        return jsonify({'error': 'content_type required'}), 400

    # Fetch content text from DB based on type
    content_text = ''
    topic = ''
    body_sec = ''
    mod = ''

    try:
        if ctype == 'reporting_algorithm':
            from models import ReportingAlgorithm
            obj = ReportingAlgorithm.query.get(int(cid))
            if obj:
                content_text = obj.template_html or obj.algorithm_html or ''
                topic = obj.title or ''
                body_sec = obj.body_section or ''
        elif ctype == 'anatomy_snippet':
            from models import ReportingAlgorithm
            obj = ReportingAlgorithm.query.get(int(cid))
            if obj:
                content_text = obj.template_html or ''
                topic = obj.title or ''
                body_sec = obj.body_section or ''
        elif ctype == 'radiology_pearl':
            from models import RadiologyPearl
            obj = RadiologyPearl.query.get(int(cid))
            if obj:
                content_text = obj.pearl_text or ''
                body_sec = obj.body_section or ''
                mod = obj.modality or ''
        elif ctype == 'radiq_query':
            from models import RadIQQuery
            obj = RadIQQuery.query.get(int(cid))
            if obj:
                content_text = obj.response_text or ''
                topic = obj.question[:80] if obj.question else ''
        elif ctype == 'case':
            from models import Case
            obj = Case.query.get(int(cid))
            if obj:
                content_text = obj.discussion or obj.ai_discussion or ''
                topic = obj.title or ''
                body_sec = getattr(obj, 'body_part', '') or ''
        elif ctype == 'radiology_tool':
            from models import IncidentalFindingCalculator
            obj = IncidentalFindingCalculator.query.get(int(cid))
            if obj:
                content_text = obj.algorithm_html or obj.description or ''
                topic = obj.title or ''
                body_sec = getattr(obj, 'body_section', '') or ''
        elif ctype == 'protocol':
            from models import ImagingProtocol
            obj = ImagingProtocol.query.get(int(cid))
            if obj:
                content_text = obj.detailed_protocol_html or obj.shorthand_text or ''
                topic = obj.title or ''
                body_sec = obj.body_section or ''
                mod = obj.modality or ''
        elif ctype in ('smart_reporter_assist', 'vetting_analysis',
                        'report_action_sba', 'report_action_viva', 'learning_question'):
            # These are transient AI outputs — no persistent DB content to re-verify
            return jsonify({'error': f'{ctype} is a transient AI output. It can only be verified at generation time.'}), 400
        else:
            return jsonify({'error': f'Unsupported content_type: {ctype}'}), 400
    except Exception as exc:
        return jsonify({'error': f'Failed to fetch content: {exc}'}), 500

    if not content_text:
        return jsonify({'error': 'Content not found or empty'}), 404

    # Strip any existing CMV badges before sending to Gemini (avoid badge HTML in verification)
    from radinsight_peer_review import strip_automated_badges
    clean_content = strip_automated_badges(content_text)

    # Run Gemini CMV
    gresult = verify_content(
        ai_output=clean_content,
        body_section=body_sec,
        modality=mod,
        topic=topic,
    )

    if gresult.get('error'):
        return jsonify({'error': f'Gemini verification failed: {gresult["error"]}'}), 502

    # Persist claims
    if gresult.get('claims'):
        _persist_claims(
            gresult['claims'], ctype, str(cid),
            body_section=body_sec, modality=mod,
            topic=topic, model=gresult.get('model', ''),
        )

    return jsonify({
        'success': True,
        'content_type': ctype,
        'content_id': cid,
        'claims_count': len(gresult.get('claims', [])),
        'summary': gresult.get('summary', {}),
    })


@admin_bp.route('/peer-review/bulk-verify', methods=['POST'])
@require_admin
def bulk_verify_content():
    """Trigger retroactive CMV on unverified content of a specific type.

    Respects Gemini free tier rate limits (15 RPM).
    """
    from models import PeerReviewClaim
    from gemini_verify import verify_content
    from radinsight_peer_review import _persist_claims, strip_automated_badges
    import time as _time

    data = request.get_json() or {}
    content_type = data.get('content_type', '')
    max_items = min(data.get('max_items', 10), 10)

    if not content_type:
        return jsonify({'error': 'content_type required'}), 400

    processed = 0
    errors = 0
    results = []

    # Get IDs already verified for this type
    verified_ids = set()
    existing = db.session.query(PeerReviewClaim.content_id).filter(
        PeerReviewClaim.content_type == content_type
    ).distinct().all()
    verified_ids = {r[0] for r in existing if r[0]}

    # Build list of (id, text, topic, body_section, modality) for the content type
    items_to_verify = []
    try:
        if content_type in ('anatomy_snippet', 'reporting_algorithm'):
            from models import ReportingAlgorithm
            query = ReportingAlgorithm.query.filter(ReportingAlgorithm.template_html.isnot(None))
            if content_type == 'anatomy_snippet':
                query = query.filter(ReportingAlgorithm.origin == 'anatomy_cache')
            else:
                query = query.filter(ReportingAlgorithm.origin != 'anatomy_cache')
            for obj in query.limit(max_items * 3).all():
                if str(obj.id) not in verified_ids:
                    items_to_verify.append((str(obj.id), obj.template_html, obj.title or '',
                                            obj.body_section or '', ''))

        elif content_type == 'radiology_pearl':
            from models import RadiologyPearl
            for obj in RadiologyPearl.query.limit(max_items * 3).all():
                if str(obj.id) not in verified_ids:
                    items_to_verify.append((str(obj.id), obj.pearl_text or '', '',
                                            obj.body_section or '', obj.modality or ''))

        elif content_type == 'radiq_query':
            from models import RadIQQuery
            for obj in RadIQQuery.query.order_by(RadIQQuery.id.desc()).limit(max_items * 3).all():
                if str(obj.id) not in verified_ids:
                    items_to_verify.append((str(obj.id), obj.response_text or '',
                                            (obj.question or '')[:80], '', ''))

        elif content_type == 'case':
            from models import Case
            for obj in Case.query.limit(max_items * 3).all():
                if str(obj.id) not in verified_ids:
                    text = obj.discussion or obj.ai_discussion or ''
                    items_to_verify.append((str(obj.id), text, obj.title or '',
                                            getattr(obj, 'body_part', '') or '', ''))

        elif content_type == 'radiology_tool':
            from models import IncidentalFindingCalculator
            for obj in IncidentalFindingCalculator.query.limit(max_items * 3).all():
                if str(obj.id) not in verified_ids:
                    text = obj.algorithm_html or obj.description or ''
                    items_to_verify.append((str(obj.id), text, obj.title or '',
                                            getattr(obj, 'body_section', '') or '', ''))

        elif content_type == 'protocol':
            from models import ImagingProtocol
            for obj in ImagingProtocol.query.limit(max_items * 3).all():
                if str(obj.id) not in verified_ids:
                    text = obj.detailed_protocol_html or obj.shorthand_text or ''
                    items_to_verify.append((str(obj.id), text, obj.title or '',
                                            obj.body_section or '', obj.modality or ''))
    except Exception as exc:
        return jsonify({'error': f'Failed to load content: {exc}'}), 500

    # Verify each item with rate limiting
    for cid, text, topic, body_sec, mod in items_to_verify[:max_items]:
        if not text or len(text.strip()) < 20:
            continue
        try:
            clean_text = strip_automated_badges(text) if '<' in text else text
            gresult = verify_content(
                ai_output=clean_text,
                body_section=body_sec,
                modality=mod,
                topic=topic,
            )
            if gresult.get('error'):
                errors += 1
                results.append({'id': cid, 'error': gresult['error']})
                if '429' in str(gresult['error']):
                    _time.sleep(10)  # Back off on rate limit
                continue
            if gresult.get('claims'):
                _persist_claims(
                    gresult['claims'], content_type, cid,
                    body_section=body_sec, modality=mod,
                    topic=topic, model=gresult.get('model', ''),
                )
            processed += 1
            results.append({'id': cid, 'claims': len(gresult.get('claims', []))})
            _time.sleep(5)  # Rate limit: ~12 RPM (safe for free tier)
        except Exception as exc:
            errors += 1
            logger.error("Bulk CMV failed for %s #%s: %s", content_type, cid, exc)

    return jsonify({
        'success': True,
        'processed': processed,
        'errors': errors,
        'results': results,
        'pending': len(items_to_verify) - processed - errors,
    })


@admin_bp.route('/peer-review/dashboard')
@require_admin
def cmv_dashboard():
    """Render the CMV admin dashboard page."""
    return render_template('admin_cmv_dashboard.html')


# ERROR HANDLERS
# ============================================================================

@admin_bp.errorhandler(403)
def forbidden(e):
    return jsonify({'error': 'Access denied. Admin role required.'}), 403


@admin_bp.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404
