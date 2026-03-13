"""
User authentication module
Handles login, signup, password recovery, and session management
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, UserRole
from datetime import datetime, timedelta
import os
import secrets
import logging
import cloudinary
import cloudinary.uploader

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Account recovery period (days after soft delete during which account can be recovered)
RECOVERY_PERIOD_DAYS = 31  # 30 days + 1 day grace period

# Login rate limiting (brute force protection)
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15

def send_recovery_email(email, token):
    """
    Send password recovery email using Resend SDK
    Free tier: 100 emails/day, 3000/month
    """
    import resend
    
    # Build recovery URL properly
    app_url = os.getenv('APP_URL', 'https://www.radinsights.xyz').rstrip('/')
    reset_path = url_for('auth.reset_password', token=token, _external=False)
    recovery_url = f"{app_url}{reset_path}"
    logger.info(f"Recovery URL generated: {recovery_url}")
    
    # Get API key from environment
    resend_key = os.getenv('RESEND_API_KEY')
    
    if not resend_key:
        logger.warning("RESEND_API_KEY not configured - cannot send recovery email")
        return False
    
    resend.api_key = resend_key
    
    # Use verified domain or Resend's test domain
    from_email = os.getenv('EMAIL_FROM', "RadInsights <no-reply@radinsights.xyz>")
    
    try:
        params = {
            "from": from_email,
            "to": [email],
            "subject": "Reset Your RadInsights Password",
            "html": f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #2c3e50;">Password Reset Request</h2>
                <p>We received a request to reset your password for RadInsights.</p>
                <p style="margin: 30px 0;">
                    <a href="{recovery_url}" style="background-color: #e96304; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        Reset Password
                    </a>
                </p>
                <p style="color: #666;">If you didn't request this, you can safely ignore this email.</p>
                <p style="color: #999; font-size: 12px;">This link expires in 24 hours.</p>
            </div>
            """
        }
        
        response = resend.Emails.send(params)
        logger.info(f"Recovery email sent to {email}: {response}")
        return True

    except Exception as e:
        logger.error(f"Failed to send recovery email to {email}: {e}")
        return False


def send_admin_approval_email(requesting_admin_email, requesting_admin_name, target_user_email, 
                               target_user_name, action, code, action_details=None):
    """
    Send approval code email to superadmin when a non-superadmin admin tries to perform
    a restricted action (promote to admin, delete admin, etc.)
    
    Args:
        requesting_admin_email: Email of the admin requesting the action
        requesting_admin_name: Name of the admin requesting the action
        target_user_email: Email of the user being affected
        target_user_name: Name of the user being affected
        action: Description of the action (e.g., "promote to Admin", "delete user")
        code: The 8-character approval code
        action_details: Dict with additional details (old_role, new_role, etc.)
    
    Returns:
        dict: {'success': bool, 'error': str or None, 'email_id': str or None}
    """
    import resend
    from datetime import datetime
    
    # Superadmin email - configurable via env for testing with Resend free tier
    # In production with verified domain, this should always be the real superadmin
    SUPERADMIN_EMAIL = os.getenv('SUPERADMIN_EMAIL', 'lotusheart2016@gmail.com')
    
    resend_key = os.getenv('RESEND_API_KEY')
    
    if not resend_key:
        error_msg = "RESEND_API_KEY not configured"
        logger.warning(f"{error_msg} - cannot send approval email")
        return {'success': False, 'error': error_msg, 'email_id': None}
    
    resend.api_key = resend_key
    from_email = os.getenv('EMAIL_FROM', "RadInsights <no-reply@radinsights.xyz>")
    
    # Build details section
    details_html = ""
    if action_details:
        if 'old_role' in action_details and 'new_role' in action_details:
            details_html = f"""
            <p><strong>Role Change:</strong> {action_details.get('old_role', 'Unknown').upper()} → 
               <span style="color: #e96304; font-weight: bold;">{action_details.get('new_role', 'Unknown').upper()}</span></p>
            """
        elif 'target_role' in action_details:
            details_html = f"""
            <p><strong>Target's Current Role:</strong> {action_details.get('target_role', 'Unknown').upper()}</p>
            """
    
    # Create mailto link for easy reply
    reply_subject = f"RE: Approval Code for {action}"
    reply_body = f"Approval Code: {code}%0A%0AThis approves the following action:%0A- {action}%0A- Target: {target_user_name} ({target_user_email})"
    mailto_link = f"mailto:{requesting_admin_email}?subject={reply_subject}&body={reply_body}"
    
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    
    try:
        params = {
            "from": from_email,
            "to": [SUPERADMIN_EMAIL],
            "subject": f"🔐 Admin Action Approval Required: {action}",
            "html": f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 12px; overflow: hidden;">
                <!-- Header -->
                <div style="background: linear-gradient(135deg, #e96304 0%, #c75002 100%); color: white; padding: 20px; text-align: center;">
                    <h2 style="margin: 0;">⚠️ Admin Action Approval Required</h2>
                </div>
                
                <!-- Content -->
                <div style="padding: 25px;">
                    <!-- Request Summary Box -->
                    <div style="background-color: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
                        <h3 style="margin: 0 0 10px 0; color: #856404;">📋 Request Summary</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 5px 0; color: #666;"><strong>Requested By:</strong></td>
                                <td style="padding: 5px 0;">{requesting_admin_name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0; color: #666;"><strong>Admin Email:</strong></td>
                                <td style="padding: 5px 0;">
                                    <a href="mailto:{requesting_admin_email}" style="color: #5E899E;">{requesting_admin_email}</a>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0; color: #666;"><strong>Action Requested:</strong></td>
                                <td style="padding: 5px 0; color: #dc3545; font-weight: bold;">{action}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0; color: #666;"><strong>Target User:</strong></td>
                                <td style="padding: 5px 0;">{target_user_name} ({target_user_email})</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0; color: #666;"><strong>Timestamp:</strong></td>
                                <td style="padding: 5px 0;">{timestamp}</td>
                            </tr>
                        </table>
                        {details_html}
                    </div>
                    
                    <!-- Approval Code Box -->
                    <div style="text-align: center; margin: 25px 0;">
                        <p style="margin-bottom: 10px; color: #666;">To <strong>APPROVE</strong> this action, share this code with the requesting admin:</p>
                        <div style="background-color: #2c3e50; color: white; padding: 20px 30px; 
                                    border-radius: 8px; font-size: 32px; letter-spacing: 6px; 
                                    font-family: 'Courier New', monospace; display: inline-block;">
                            {code}
                        </div>
                        <p style="margin-top: 10px; color: #999; font-size: 12px;">
                            Code expires in <strong>24 hours</strong> • Single use only
                        </p>
                    </div>
                    
                    <!-- Quick Reply Button -->
                    <div style="text-align: center; margin: 25px 0;">
                        <a href="{mailto_link}" 
                           style="display: inline-block; background: linear-gradient(135deg, #5E899E 0%, #4a7085 100%); 
                                  color: white; padding: 12px 30px; text-decoration: none; 
                                  border-radius: 6px; font-weight: bold;">
                            📧 Send Approval Code to Admin
                        </a>
                        <p style="margin-top: 10px; color: #666; font-size: 12px;">
                            Click above to send the code directly to {requesting_admin_name}
                        </p>
                    </div>
                    
                    <!-- To Reject -->
                    <div style="background-color: #f8f9fa; border-radius: 8px; padding: 15px; margin-top: 20px;">
                        <p style="margin: 0; color: #666;">
                            <strong>To REJECT:</strong> Simply ignore this email. The code will expire automatically.
                            If you suspect unauthorized activity, investigate the requesting admin's account.
                        </p>
                    </div>
                </div>
                
                <!-- Footer -->
                <div style="background-color: #2c3e50; color: #aaa; padding: 15px; text-align: center; font-size: 12px;">
                    <p style="margin: 0;">RadInsights Admin System</p>
                    <p style="margin: 5px 0 0 0;">This is an automated security notification.</p>
                </div>
            </div>
            """
        }
        
        response = resend.Emails.send(params)
        email_id = response.get('id') if isinstance(response, dict) else str(response)
        logger.info(f"Approval email sent to superadmin for '{action}': ID={email_id}")
        return {'success': True, 'error': None, 'email_id': email_id}
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to send approval email: {error_msg}", exc_info=True)
        return {'success': False, 'error': error_msg, 'email_id': None}


def send_case_review_notification(case, submitter):
    """Send email to admin when a student submits a case for review."""
    resend_key = os.getenv('RESEND_API_KEY')
    if not resend_key:
        logger.warning("RESEND_API_KEY not configured — skipping review notification")
        return False

    import resend
    resend.api_key = resend_key
    from_email = os.getenv('EMAIL_FROM', "RadInsights <no-reply@radinsights.xyz>")
    admin_email = os.getenv('SUPERADMIN_EMAIL', 'lotusheart2016@gmail.com')
    app_url = os.getenv('APP_URL', 'https://www.radinsights.xyz').rstrip('/')
    review_url = f"{app_url}/view-case/{case.id}"

    try:
        params = {
            "from": from_email,
            "to": [admin_email],
            "subject": f"New Case Suggestion: {case.diagnosis[:60]}",
            "html": f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 12px; overflow: hidden;">
                <div style="background: linear-gradient(135deg, #5E899E 0%, #4a7285 100%); color: white; padding: 20px; text-align: center;">
                    <h2 style="margin: 0;">New Case Suggestion for Review</h2>
                </div>
                <div style="padding: 25px;">
                    <div style="background-color: #f0f8fc; border: 1px solid #5E899E; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr><td style="padding: 5px 0; color: #666;"><strong>Diagnosis:</strong></td><td>{case.diagnosis}</td></tr>
                            <tr><td style="padding: 5px 0; color: #666;"><strong>Module:</strong></td><td>{case.module.value if case.module else 'N/A'}</td></tr>
                            <tr><td style="padding: 5px 0; color: #666;"><strong>Body Part:</strong></td><td>{case.body_part.value if case.body_part else 'N/A'}</td></tr>
                            <tr><td style="padding: 5px 0; color: #666;"><strong>Submitted By:</strong></td><td>{submitter.full_name} ({submitter.email})</td></tr>
                            <tr><td style="padding: 5px 0; color: #666;"><strong>Images:</strong></td><td>{len(case.images) if case.images else 0} uploaded</td></tr>
                        </table>
                    </div>
                    <div style="text-align: center; margin: 25px 0;">
                        <a href="{review_url}" style="display: inline-block; background: linear-gradient(135deg, #e96304 0%, #c75002 100%); color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold;">Review Case</a>
                    </div>
                </div>
                <div style="background-color: #2c3e50; color: #aaa; padding: 15px; text-align: center; font-size: 12px;">
                    <p style="margin: 0;">RadInsights Admin Notification</p>
                </div>
            </div>"""
        }
        response = resend.Emails.send(params)
        logger.info(f"Case review notification sent for case {case.id}: {response}")
        return True
    except Exception as e:
        logger.error(f"Failed to send case review notification: {e}")
        return False


def generate_approval_code():
    """Generate an 8-character alphanumeric approval code"""
    import string
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(8))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        try:
            # Verify database connection is working
            try:
                test_count = User.query.limit(1).count()
            except Exception as db_error:
                return jsonify({'error': 'Database connection failed. Please try again later.'}), 503
            
            data = request.get_json() if request.is_json else request.form
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')
            full_name = data.get('full_name', '').strip()
            
            # Validation
            if not all([email, password, full_name]):
                return jsonify({'error': 'All fields required'}), 400
            
            if len(password) < 8:
                return jsonify({'error': 'Password must be at least 8 characters'}), 400
            
            # Check if user exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                return jsonify({'error': 'Email already registered'}), 409
            
            # Check if this is the first user - make them admin
            user_count = User.query.count()
            is_first_user = user_count == 0
            
            # Create user
            user = User(email=email, full_name=full_name)
            user.set_password(password)
            
            if is_first_user:
                user.is_admin = True
                user.role = UserRole.ADMIN
            else:
                user.is_admin = False
                user.role = UserRole.STUDENT
            
            # Add user to session and commit
            db.session.add(user)
            db.session.flush()
            user_id = user.id
            
            try:
                db.session.commit()
            except Exception as commit_error:
                db.session.rollback()
                raise
            
            # Verify user was saved
            db.session.expire_all()
            verified_user = User.query.filter_by(id=user_id).first()
            if not verified_user:
                return jsonify({'error': 'Registration failed. User was not saved to database.'}), 500
            
            if not verified_user.password_hash:
                return jsonify({'error': 'Registration failed. Password was not saved correctly.'}), 500
            
            user = verified_user
            
            # Login user after successful save (don't persist session - require explicit login next time)
            from flask import session as flask_session
            flask_session.permanent = True
            flask_session['last_activity'] = datetime.utcnow().isoformat()
            login_user(user, remember=False)  # New users must explicitly log in next session
            
            return jsonify({'success': True, 'message': 'Registration successful', 'user_id': user.id}), 201
            
        except Exception as e:
            db.session.rollback()
            # Return more detailed error in development, generic in production
            error_msg = 'Registration failed. Please contact administrator or check logs.'
            if os.getenv('FLASK_ENV') == 'development':
                error_msg = f'Registration failed: {str(e)}'
            return jsonify({'error': error_msg}), 500
    
    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        # Return JSON for fetch/XHR so client gets JSON instead of following redirect to HTML
        if request.method == 'POST' and (request.is_json or request.headers.get('Accept', '').find('application/json') >= 0):
            return jsonify({'success': True, 'message': 'Already logged in'}), 200
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        remember = data.get('remember', False)
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        # Query user and ensure password_hash is loaded
        user = User.query.filter_by(email=email).first()
        
        if not user:
            return jsonify({'error': 'Invalid email or password'}), 401

        # Brute force protection: check account lockout
        if user.locked_until and user.locked_until > datetime.utcnow():
            remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
            return jsonify({'error': f'Account temporarily locked. Try again in {remaining} minutes.'}), 429

        # Ensure password_hash is loaded
        if not user.password_hash:
            db.session.refresh(user)
            if not user.password_hash:
                return jsonify({'error': 'User account error. Please contact administrator.'}), 500
        
        try:
            password_valid = user.check_password(password)
        except Exception as e:
            return jsonify({'error': 'Authentication error. Please contact administrator.'}), 500
        
        if not password_valid:
            # Increment failed login counter
            user.failed_login_count = (user.failed_login_count or 0) + 1
            user.failed_login_last = datetime.utcnow()
            if user.failed_login_count >= MAX_FAILED_LOGINS:
                user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            return jsonify({'error': 'Invalid email or password'}), 401

        if not user.is_active:
            return jsonify({'error': 'Account is disabled'}), 403
        
        # Check if account is soft-deleted (recoverable)
        if user.is_deleted:
            days_remaining = 0
            deletion_date = None
            
            if user.deleted_at:
                days_since_deletion = (datetime.utcnow() - user.deleted_at).days
                days_remaining = max(0, RECOVERY_PERIOD_DAYS - days_since_deletion)
                deletion_date = user.deleted_at.strftime('%B %d, %Y')
                
                # Check if recovery period expired — auto-purge user data (GDPR right to erasure)
                if days_remaining <= 0:
                    try:
                        from access_control import delete_user_completely
                        delete_user_completely(user.id)
                        logger.info(f"Auto-purged soft-deleted account {user.id} (recovery period expired)")
                    except Exception as purge_err:
                        logger.error(f"Auto-purge failed for user {user.id}: {purge_err}")
                    return jsonify({
                        'error': 'This account has been permanently deleted.',
                        'account_deleted': True,
                        'recoverable': False
                    }), 403
            
            return jsonify({
                'error': 'Account is deactivated',
                'account_deleted': True,
                'recoverable': True,
                'deletion_date': deletion_date,
                'days_remaining': days_remaining,
                'email': user.email
            }), 403
        
        try:
            # Update last login and reset failed login counters
            user.last_login = datetime.utcnow()
            user.failed_login_count = 0
            user.locked_until = None
            db.session.commit()
            
            # Mark session as permanent for session timeout tracking
            from flask import session as flask_session
            flask_session.permanent = True
            # Track last activity time for session timeout
            flask_session['last_activity'] = datetime.utcnow().isoformat()
            
            # Use user's "Remember Me" preference
            # If remember=False: session expires when browser closes
            # If remember=True: session persists for REMEMBER_COOKIE_DURATION (7 days)
            login_user(user, remember=bool(remember))
            
            return jsonify({'success': True, 'message': 'Login successful'}), 200
        
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': 'Login failed. Please try again.'}), 500
    
    return render_template('login.html')


@auth_bp.route('/session/refresh', methods=['POST'])
@login_required
def refresh_session():
    """
    Refresh user session and update last activity time
    This extends the session lifetime and reloads user data from database
    """
    try:
        from flask import session as flask_session
        from datetime import datetime, timedelta
        
        # Update last activity time
        flask_session['last_activity'] = datetime.utcnow().isoformat()
        flask_session.permanent = True
        
        # Reload user from database to get latest role/permissions
        db.session.refresh(current_user)
        
        # Check if session should expire (30 minutes of inactivity)
        last_activity_str = flask_session.get('last_activity')
        if last_activity_str:
            try:
                last_activity = datetime.fromisoformat(last_activity_str)
                time_since_activity = datetime.utcnow() - last_activity
                
                # If more than 30 minutes of inactivity, expire session
                if time_since_activity > timedelta(seconds=1800):
                    logout_user()
                    return jsonify({
                        'success': False,
                        'expired': True,
                        'message': 'Session expired due to inactivity'
                    }), 401
            except (ValueError, TypeError):
                # Invalid timestamp, reset it
                flask_session['last_activity'] = datetime.utcnow().isoformat()
        
        return jsonify({
            'success': True,
            'user': {
                'id': current_user.id,
                'email': current_user.email,
                'role': current_user.role.value if current_user.role else 'student',
                'is_admin': current_user.role == UserRole.ADMIN if current_user.role else False
            },
            'last_activity': flask_session.get('last_activity')
        }), 200
        
    except Exception as e:
        pass  # Session refresh failed, non-critical
        return jsonify({'error': 'Failed to refresh session'}), 500


@auth_bp.route('/session/status', methods=['GET'])
@login_required
def session_status():
    """Get current session status and time remaining"""
    try:
        from flask import session as flask_session
        from datetime import datetime, timedelta
        
        last_activity_str = flask_session.get('last_activity')
        if not last_activity_str:
            return jsonify({
                'authenticated': True,
                'time_remaining': 1800,  # 30 minutes in seconds
                'expires_at': None
            }), 200
        
        last_activity = datetime.fromisoformat(last_activity_str)
        expires_at = last_activity + timedelta(seconds=1800)
        time_remaining = (expires_at - datetime.utcnow()).total_seconds()
        
        return jsonify({
            'authenticated': True,
            'time_remaining': max(0, int(time_remaining)),
            'expires_at': expires_at.isoformat(),
            'last_activity': last_activity_str
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """User logout"""
    logout_user()
    return jsonify({'success': True, 'message': 'Logged out'}), 200


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request password recovery"""
    if request.method == 'POST':
        try:
            logger.debug("Forgot password - processing request")
            data = request.get_json() if request.is_json else request.form
            email = data.get('email', '').strip().lower()
            logger.debug(f"Forgot password - email: {email}")
            
            if not email:
                return jsonify({'error': 'Email required'}), 400
            
            user = User.query.filter_by(email=email).first()
            logger.debug(f"Forgot password - user found: {user is not None}")
            
            if user:
                # Generate recovery token
                logger.debug("Generating recovery token...")
                token = user.generate_recovery_token()
                logger.debug("Token generated, committing to DB...")
                db.session.commit()
                logger.debug("Token saved to DB")
                
                # Send email
                try:
                    logger.debug("Attempting to send recovery email...")
                    email_sent = send_recovery_email(email, token)
                    logger.debug(f"Email sent result: {email_sent}")

                    if not email_sent:
                        logger.warning(f"Recovery email failed to send for {email}")
                except Exception as email_error:
                    logger.error(f"Email sending exception for {email}: {email_error}", exc_info=True)
            
            # Always return success (don't reveal if email exists or not)
            logger.debug("Returning success response")
            return jsonify({'success': True, 'message': 'If an account with that email exists, you will receive a recovery link shortly.'}), 200
            
        except Exception as e:
            logger.error(f"Forgot password error: {e}", exc_info=True)
            db.session.rollback()
            return jsonify({'error': 'An error occurred. Please try again.'}), 500
    
    return render_template('forgot_password.html')



@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with token"""
    try:
        logger.debug(f"Reset password page accessed with token: {token[:20]}...")

        user = User.query.filter_by(recovery_token=token).first()

        if not user:
            logger.debug("Reset password: No user found for token")
            return render_template('reset_password_expired.html'), 401

        logger.debug(f"Reset password: User found - {user.email}")

        if not user.verify_recovery_token(token):
            logger.debug(f"Reset password: Token verification failed for {user.email}")
            logger.debug(f"Token expires: {user.recovery_token_expires}, Now: {datetime.utcnow()}")
            return render_template('reset_password_expired.html'), 401

        logger.debug("Reset password: Token valid, showing reset form")
        
        if request.method == 'POST':
            data = request.get_json() if request.is_json else request.form
            new_password = data.get('password', '')
            
            if not new_password or len(new_password) < 8:
                return jsonify({'error': 'Password must be at least 8 characters'}), 400
            
            # Set new password
            user.set_password(new_password)
            user.clear_recovery_token()
            db.session.commit()
            
            login_user(user)
            return jsonify({'success': True, 'message': 'Password reset successful'}), 200
        
        return render_template('reset_password.html', token=token)
        
    except Exception as e:
        logger.error(f"Reset password error: {e}", exc_info=True)
        return render_template('reset_password_expired.html'), 500


@auth_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    """Get current user profile"""
    # Return HTML page if requested via browser, JSON for API
    if request.headers.get('Accept') == 'application/json':
        return jsonify({
            'id': current_user.id,
            'email': current_user.email,
            'full_name': current_user.full_name,
            'created_at': current_user.created_at.isoformat(),
            'last_login': current_user.last_login.isoformat() if current_user.last_login else None
        }), 200
    
    # Return HTML profile page
    return render_template('profile.html', user=current_user)



@auth_bp.route('/logout-redirect', methods=['GET'])
def logout_redirect():
    """Logout and redirect to login page"""
    logout_user()
    return redirect(url_for('auth.login'))


@auth_bp.route('/account-deactivated', methods=['GET'])
def account_deactivated_page():
    """Show account deactivated/recovery page"""
    return render_template('account_deactivated.html')


# ==================== STUDENT ACCOUNT SOFT DELETE & RECOVERY ====================


@auth_bp.route('/account/soft-delete', methods=['POST'])
@login_required
def soft_delete_account():
    """
    Soft delete the current user's account (students only).
    Account can be recovered within 31 days.
    """
    try:
        # Only students can self-delete
        if current_user.role != UserRole.STUDENT:
            return jsonify({'error': 'Only student accounts can be self-deleted. Contact support for other account types.'}), 403
        
        # Check if already deleted
        if current_user.is_deleted:
            return jsonify({'error': 'Account is already deactivated'}), 400
        
        # Clear subscription (this is permanent - not restored on recovery)
        from models import SubscriptionStatus, PaymentStatus
        current_user.subscription_status = SubscriptionStatus.CANCELED
        current_user.payment_status = PaymentStatus.NO_SUBSCRIPTION
        current_user.subscription_end_date = datetime.utcnow()
        
        # Mark as soft deleted
        current_user.is_deleted = True
        current_user.deleted_at = datetime.utcnow()
        current_user.deleted_by_user_id = current_user.id  # Self-deleted
        
        db.session.commit()
        
        # Log the deletion
        logger.info(f"User {current_user.email} soft-deleted their account")
        
        return jsonify({
            'success': True,
            'message': 'Account deactivated. You can recover within 30 days.',
            'recovery_deadline': (datetime.utcnow() + timedelta(days=RECOVERY_PERIOD_DAYS)).isoformat()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Soft delete error: {e}")
        return jsonify({'error': 'Failed to delete account'}), 500


def send_recovery_code_email(email, code, request_metadata=None):
    """Send account recovery code email"""
    import resend
    
    resend_key = os.getenv('RESEND_API_KEY')
    if not resend_key:
        logger.warning("RESEND_API_KEY not configured")
        return False
    
    resend.api_key = resend_key
    from_email = os.getenv('EMAIL_FROM', "RadInsights <no-reply@radinsights.xyz>")
    
    metadata_html = ""
    if request_metadata:
        metadata_html = f"<p><small>Request IP: {request_metadata.get('ip', 'Unknown')}<br>Device: {request_metadata.get('user_agent', 'Unknown')[:50]}...</small></p>"
    
    try:
        params = {
            "from": from_email,
            "to": [email],
            "subject": "Account Recovery Request – RadInsights",
            "html": f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #5E899E;">Account Recovery Request</h2>
                
                <p>We received a request to recover your account.</p>
                
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <p><strong>Account details:</strong></p>
                    <ul>
                        <li>Email: {email}</li>
                        <li>Request date: {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}</li>
                    </ul>
                    {metadata_html}
                </div>
                
                <p><strong>Your recovery code:</strong></p>
                
                <div style="background-color: #2c3e50; color: white; padding: 20px; text-align: center; 
                            border-radius: 8px; margin: 20px 0; font-size: 32px; letter-spacing: 6px; font-family: monospace;">
                    {code}
                </div>
                
                <p style="color: #666;">If this was not you, you can safely ignore this email.</p>
                <p style="color: #dc3545; font-size: 12px;"><strong>This code will expire in 15 minutes.</strong></p>
            </div>
            """
        }
        
        response = resend.Emails.send(params)
        logger.info(f"Recovery code sent to {email}: {response}")
        return True

    except Exception as e:
        logger.error(f"Failed to send recovery code: {e}")
        return False


@auth_bp.route('/account/request-recovery', methods=['POST'])
def request_account_recovery():
    """
    Request a recovery code for a soft-deleted account.
    Rate limited to prevent abuse.
    """
    try:
        data = request.get_json() or {}
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({'error': 'Email required'}), 400
        
        # Find the user
        user = User.query.filter_by(email=email).first()
        
        if not user:
            # Don't reveal if email exists
            return jsonify({'success': True, 'message': 'If the account exists and is recoverable, a code has been sent.'}), 200
        
        if not user.is_deleted:
            # Account is active - shouldn't be trying to recover
            return jsonify({'error': 'This account is active. Please login normally.'}), 400
        
        # Check if recovery period has expired
        if user.deleted_at:
            days_since_deletion = (datetime.utcnow() - user.deleted_at).days
            if days_since_deletion >= RECOVERY_PERIOD_DAYS:
                return jsonify({'error': 'Recovery period has expired. This account cannot be recovered.'}), 400
        
        # Rate limiting - check recent recovery code requests
        from models import AccountRecoveryCode
        recent_codes = AccountRecoveryCode.query.filter(
            AccountRecoveryCode.user_id == user.id,
            AccountRecoveryCode.created_at > datetime.utcnow() - timedelta(minutes=5)
        ).count()
        
        if recent_codes >= 3:
            return jsonify({'error': 'Too many recovery attempts. Please wait 5 minutes.'}), 429
        
        # Generate recovery code
        import string
        alphabet = string.ascii_uppercase + string.digits
        code = ''.join(secrets.choice(alphabet) for _ in range(8))
        
        # Store the code
        recovery_code = AccountRecoveryCode(
            code=code,
            user_id=user.id,
            request_ip=request.remote_addr,
            request_user_agent=request.headers.get('User-Agent', '')[:500],
            expires_at=datetime.utcnow() + timedelta(minutes=15)
        )
        db.session.add(recovery_code)
        db.session.commit()
        
        # Send email
        metadata = {
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')
        }
        email_sent = send_recovery_code_email(email, code, metadata)
        
        if not email_sent:
            return jsonify({'error': 'Failed to send recovery email. Please try again.'}), 500
        
        # Calculate days remaining
        days_remaining = RECOVERY_PERIOD_DAYS - (datetime.utcnow() - user.deleted_at).days if user.deleted_at else RECOVERY_PERIOD_DAYS
        
        return jsonify({
            'success': True,
            'message': 'Recovery code sent to your email.',
            'days_remaining': days_remaining
        }), 200
        
    except Exception as e:
        logger.error(f"Request recovery error: {e}", exc_info=True)
        return jsonify({'error': 'An error occurred'}), 500


@auth_bp.route('/account/verify-recovery', methods=['POST'])
def verify_recovery_code():
    """
    Verify a recovery code and return a recovery token.
    User must then set a new password.
    """
    try:
        data = request.get_json() or {}
        email = data.get('email', '').strip().lower()
        code = data.get('code', '').strip().upper()
        
        if not email or not code:
            return jsonify({'error': 'Email and code required'}), 400
        
        # Find the user
        user = User.query.filter_by(email=email).first()
        if not user or not user.is_deleted:
            return jsonify({'error': 'Invalid recovery request'}), 400
        
        # Find the recovery code
        from models import AccountRecoveryCode
        recovery = AccountRecoveryCode.query.filter_by(
            user_id=user.id,
            code=code
        ).first()
        
        if not recovery:
            return jsonify({'error': 'Invalid recovery code'}), 400
        
        # Record the attempt
        recovery.record_attempt()
        db.session.commit()
        
        # Check if too many attempts
        if recovery.attempts > 5:
            return jsonify({'error': 'Too many attempts. Please request a new code.'}), 429
        
        if not recovery.is_valid():
            return jsonify({'error': 'Recovery code expired. Please request a new one.'}), 400
        
        # Mark code as used
        recovery.mark_used()
        
        # Generate a recovery token for password reset
        recovery_token = secrets.token_urlsafe(32)
        user.recovery_token = recovery_token
        user.recovery_token_expires = datetime.utcnow() + timedelta(hours=1)
        
        db.session.commit()
        
        logger.info(f"Recovery code verified for {email}")
        
        return jsonify({
            'success': True,
            'recovery_token': recovery_token,
            'message': 'Code verified. Please set a new password.'
        }), 200
        
    except Exception as e:
        logger.error(f"Verify recovery error: {e}")
        return jsonify({'error': 'An error occurred'}), 500


@auth_bp.route('/account/complete-recovery', methods=['POST'])
def complete_account_recovery():
    """
    Complete account recovery by setting a new password.
    This reactivates the account.
    """
    try:
        data = request.get_json() or {}
        recovery_token = data.get('recovery_token', '')
        new_password = data.get('new_password', '')
        
        if not recovery_token or not new_password:
            return jsonify({'error': 'Recovery token and new password required'}), 400
        
        if len(new_password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        
        # Find user by recovery token
        user = User.query.filter_by(recovery_token=recovery_token).first()
        
        if not user:
            return jsonify({'error': 'Invalid recovery token'}), 400
        
        # Check token expiry
        if not user.recovery_token_expires or user.recovery_token_expires < datetime.utcnow():
            return jsonify({'error': 'Recovery token expired. Please start over.'}), 400
        
        # Check password is not the same as before
        if user.check_password(new_password):
            return jsonify({'error': 'New password cannot be the same as your previous password'}), 400
        
        # Reactivate account
        user.is_deleted = False
        user.deleted_at = None
        user.deleted_by_user_id = None
        
        # Set new password
        user.set_password(new_password)
        
        # Clear recovery token
        user.recovery_token = None
        user.recovery_token_expires = None
        
        # Note: Subscription is NOT restored (as per spec)
        
        db.session.commit()
        
        logger.info(f"Account recovered successfully for {user.email}")
        
        # Log the user in
        login_user(user)
        
        return jsonify({
            'success': True,
            'message': 'Account recovered successfully!',
            'subscription_note': 'Your previous subscription was not restored.'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Complete recovery error: {e}")
        return jsonify({'error': 'An error occurred'}), 500



# ==================== ADMIN USER MANAGEMENT ====================

@auth_bp.route('/admin/promote-user', methods=['POST'])
@login_required
def promote_user():
    """Promote a user to admin - only accessible by existing admins"""
    if current_user.role != UserRole.ADMIN:
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.get_json()
    user_email = data.get('email', '').strip().lower()
    
    if not user_email:
        return jsonify({'error': 'Email required'}), 400
    
    user = User.query.filter_by(email=user_email).first()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if user.is_admin:
        return jsonify({'message': 'User is already an admin'}), 200
    
    user.is_admin = True
    db.session.commit()
    
    
    return jsonify({'success': True, 'message': f'User {user_email} promoted to admin'}), 200


@auth_bp.route('/admin/list-users', methods=['GET'])
@login_required  
def list_users():
    """List all users with their admin status - admin only"""
    if current_user.role != UserRole.ADMIN:
        return jsonify({'error': 'Admin access required'}), 403
    
    users = User.query.order_by(User.created_at).all()
    
    return jsonify({
        'users': [{
            'id': u.id,
            'email': u.email,
            'full_name': u.full_name,
            'is_admin': u.is_admin,
            'created_at': u.created_at.isoformat() if u.created_at else None
        } for u in users]
    }), 200

# ==================== PROFILE MANAGEMENT ====================

@auth_bp.route('/profile/picture', methods=['POST'])
@login_required
def upload_profile_picture():
    """Upload profile picture - stores in Cloudinary"""
    try:
        data = request.get_json()
        picture_base64 = data.get('picture')
        
        if not picture_base64:
            return jsonify({'error': 'No picture provided'}), 400
        
        # Validate base64 format
        if not picture_base64.startswith('data:image/'):
            return jsonify({'error': 'Invalid image format'}), 400
        
        # Delete old Cloudinary image if exists
        if current_user.profile_picture_public_id:
            try:
                cloudinary.uploader.destroy(current_user.profile_picture_public_id)
            except Exception:
                pass  # Ignore deletion errors for old image
        
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            picture_base64,
            folder='frcr_revision/frcr_profile',
            resource_type='image',
            transformation=[
                {'width': 200, 'height': 200, 'crop': 'fill', 'gravity': 'face'},
                {'quality': 'auto', 'fetch_format': 'auto'}
            ]
        )
        
        # Store Cloudinary URL instead of base64
        current_user.profile_picture = upload_result['secure_url']
        current_user.profile_picture_public_id = upload_result['public_id']
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Profile picture updated',
            'picture_url': upload_result['secure_url']
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to upload picture: {str(e)}'}), 500


@auth_bp.route('/profile/picture', methods=['DELETE'])
@login_required
def remove_profile_picture():
    """Remove profile picture - cleans up Cloudinary"""
    try:
        # Delete from Cloudinary if applicable
        if current_user.profile_picture_public_id:
            try:
                cloudinary.uploader.destroy(current_user.profile_picture_public_id)
            except Exception:
                pass  # Log but don't fail
        
        current_user.profile_picture = None
        current_user.profile_picture_public_id = None
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Profile picture removed'}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to remove picture'}), 500


@auth_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Update user profile (name, email, and public display name)"""
    try:
        data = request.get_json()
        full_name = data.get('full_name', '').strip()
        email = data.get('email', '').strip().lower()
        public_display_name = data.get('public_display_name', '').strip() if data.get('public_display_name') else None
        
        if not full_name or not email:
            return jsonify({'error': 'Name and email are required'}), 400
        
        # Validate public_display_name if provided
        if public_display_name:
            if len(public_display_name) < 2 or len(public_display_name) > 30:
                return jsonify({'error': 'Public name must be 2-30 characters'}), 400
            # Only allow letters, numbers, and spaces (no HTML, no emails)
            import re
            if not re.match(r'^[a-zA-Z0-9 ]+$', public_display_name):
                return jsonify({'error': 'Public name can only contain letters, numbers, and spaces'}), 400
            if '@' in public_display_name:
                return jsonify({'error': 'Public name cannot contain email addresses'}), 400
        
        # Check if email is already taken by another user
        if email != current_user.email:
            existing = User.query.filter_by(email=email).first()
            if existing:
                return jsonify({'error': 'Email already in use'}), 409
        
        current_user.full_name = full_name
        current_user.email = email
        current_user.public_display_name = public_display_name if public_display_name else None
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Profile updated',
            'display_name': current_user.get_display_name()
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update profile'}), 500


@auth_bp.route('/profile/display-name', methods=['POST'])
@login_required
def update_display_name():
    """Update public display name only (for forum inline editing)"""
    try:
        data = request.get_json()
        public_display_name = data.get('public_display_name', '').strip() if data.get('public_display_name') else None
        
        # Validate public_display_name if provided
        if public_display_name:
            if len(public_display_name) < 2 or len(public_display_name) > 30:
                return jsonify({'error': 'Public name must be 2-30 characters'}), 400
            # Only allow letters, numbers, and spaces (no HTML, no emails)
            import re
            if not re.match(r'^[a-zA-Z0-9 ]+$', public_display_name):
                return jsonify({'error': 'Public name can only contain letters, numbers, and spaces'}), 400
            if '@' in public_display_name:
                return jsonify({'error': 'Public name cannot contain email addresses'}), 400
        
        current_user.public_display_name = public_display_name if public_display_name else None
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Display name updated',
            'display_name': current_user.get_display_name()
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update display name'}), 500


@auth_bp.route('/profile/password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({'error': 'Current and new password required'}), 400
        
        # Verify current password
        if not current_user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 401
        
        # Validate new password
        if len(new_password) < 8:
            return jsonify({'error': 'New password must be at least 8 characters'}), 400
        
        # Update password
        current_user.set_password(new_password)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Password updated'}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to change password'}), 500