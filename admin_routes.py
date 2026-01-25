"""
Admin Routes - User Management & Case Management API Endpoints
Provides CRUD operations for user management and case management with role-based access control
"""

from flask import Blueprint, request, jsonify, render_template_string
from flask_login import login_required, current_user
from models import db, User, UserRole, SubscriptionStatus, CaseAuditLog, Case
from access_control import require_admin, require_role, delete_user_completely, can_delete_user, upgrade_to_paid, downgrade_to_free
from datetime import datetime
from sqlalchemy import or_, and_
import logging
import os
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
    
    Body: { "role": "content_manager" }
    """
    try:
        # Get target user
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if trying to demote self
        if user.id == current_user.id:
            return jsonify({'error': 'Cannot change your own role'}), 400
        
        # Get new role from request
        data = request.get_json()
        new_role = data.get('role', '').lower()
        
        # Validate role
        valid_roles = [r.value for r in UserRole]
        if new_role not in valid_roles:
            return jsonify({'error': f'Invalid role. Valid: {valid_roles}'}), 400
        
        # Update role
        old_role = user.role.value if user.role else None
        user.role = UserRole(new_role)
        db.session.commit()
        
        # Log action
        logger.info(f"Admin {current_user.email} changed {user.email} role from {old_role} to {new_role}")
        
        return jsonify({
            'message': f'User role updated to {new_role}',
            'user_id': user.id,
            'old_role': old_role,
            'new_role': new_role
        }), 200
    
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
    
    DELETES: Private data (notes, highlights, revision sessions, view logs, votes, flags)
    PRESERVES: Forum messages (anonymized), case data (author references nullified)
    
    This is a hard delete - the user and their private data are permanently removed.
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if allowed to delete
        can_delete, error_msg = can_delete_user(user, current_user)
        if not can_delete:
            return jsonify({'error': error_msg}), 400
        
        email = user.email
        user_role = user.role.value if hasattr(user.role, 'value') else str(user.role)
        
        # Perform complete deletion with cleanup
        success, result = delete_user_completely(user)
        
        if not success:
            logger.error(f"Failed to delete user {email}: {result}")
            return jsonify({'error': f'Failed to delete user: {result}'}), 500
        
        # Log the deletion with stats
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
            # Get creator's name
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
    if case.created_by_user_id:
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
        'status': case.status.name if case.status else 'DRAFT',
        'is_public': case.is_public,
        'created_by_user_id': case.created_by_user_id,
        'created_by_name': creator_name,
        'created_at': case.created_at.isoformat() if case.created_at else None,
    }), 200

# ============================================================================
# APP DOCUMENTATION ENDPOINTS
# ============================================================================

@admin_bp.route('/docs', methods=['GET'])
@require_admin
def list_docs():
    """
    List all markdown documentation files in the docs/ folder
    Returns: { docs: [{ name, path, title }] }
    """
    docs_dir = os.path.join(os.path.dirname(__file__), 'docs')
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
    """
    docs_dir = os.path.join(os.path.dirname(__file__), 'docs')
    file_path = os.path.join(docs_dir, doc_path)
    
    # Security: Ensure path is within docs directory
    real_docs_dir = os.path.realpath(docs_dir)
    real_file_path = os.path.realpath(file_path)
    
    if not real_file_path.startswith(real_docs_dir):
        return jsonify({'success': False, 'error': 'Invalid path'}), 403
    
    if not os.path.exists(file_path):
        return jsonify({'success': False, 'error': 'Document not found'}), 404
    
    if not file_path.endswith('.md'):
        return jsonify({'success': False, 'error': 'Invalid file type'}), 400
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
        
        # Convert markdown to HTML with extensions
        md = markdown.Markdown(extensions=[
            'tables',
            'fenced_code',
            'codehilite',
            'toc',
            'nl2br'
        ])
        content_html = md.convert(raw_content)
        
        # Generate title from filename
        title = os.path.basename(doc_path).replace('.md', '').replace('_', ' ').replace('-', ' ')
        
        return jsonify({
            'success': True,
            'title': title,
            'path': doc_path,
            'content_html': content_html,
            'raw_content': raw_content
        })
    except Exception as e:
        logger.error(f"Error reading doc {doc_path}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@admin_bp.errorhandler(403)
def forbidden(e):
    return jsonify({'error': 'Access denied. Admin role required.'}), 403


@admin_bp.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404
