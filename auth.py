"""
User authentication module
Handles login, signup, password recovery, and session management
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, UserRole
from datetime import datetime
import os
import secrets

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def send_recovery_email(email, token):
    """
    Send password recovery email using free service
    Using Resend.com (free tier) or fallback to console for development
    """
    recovery_url = os.getenv('APP_URL', 'https://frcr-examiner.vercel.app') + url_for('auth.reset_password', token=token, _external=False)
    
    # For development, just log it
    if os.getenv('FLASK_ENV') == 'development':
        print(f"\n📧 Password Recovery Email:")
        print(f"   To: {email}")
        print(f"   Reset Link: {recovery_url}\n")
        return True
    
    # For production, use Resend (free tier: 100 emails/day)
    try:
        import requests
        resend_key = os.getenv('RESEND_API_KEY')
        
        if not resend_key:
            print(f"[EMAIL] ERROR: RESEND_API_KEY not set. Email not sent to {email}")
            print(f"[EMAIL] Recovery link (for debugging): {recovery_url}")
            return False
        
        print(f"[EMAIL] Sending recovery email to {email}")
        print(f"[EMAIL] Recovery URL: {recovery_url}")
        
        # Use onboarding@resend.dev for testing (Resend's test domain)
        # For production, replace with your verified domain
        from_email = os.getenv('EMAIL_FROM', 'onboarding@resend.dev')
        
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {resend_key}",
                "Content-Type": "application/json"
            },
            json={
                "from": from_email,
                "to": [email],
                "subject": "Reset Your FRCR Examiner Password",
                "html": f"""
                <h2>Password Reset Request</h2>
                <p>We received a request to reset your password.</p>
                <p><a href="{recovery_url}" style="background-color: #896b90; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                    Reset Password
                </a></p>
                <p>If you didn't request this, you can ignore this email.</p>
                <p><small>Link expires in 24 hours</small></p>
                """
            },
            timeout=10
        )
        
        print(f"[EMAIL] Response status: {response.status_code}")
        print(f"[EMAIL] Response body: {response.text}")
        
        if response.status_code != 200:
            print(f"[EMAIL] ERROR: Failed to send email. Status: {response.status_code}")
            return False
        
        print(f"[EMAIL] SUCCESS: Email sent to {email}")
        return True
        
    except Exception as e:
        print(f"[EMAIL] EXCEPTION: Error sending email: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        try:
            # Verify database connection is working
            try:
                # Simple query to test database connection
                test_count = User.query.limit(1).count()
                print(f"[REGISTER] Database connection verified (user count check)")
            except Exception as db_error:
                print(f"[REGISTER] Database connection error: {db_error}")
                import traceback
                traceback.print_exc()
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
            print(f"[REGISTER] Checking for existing user: {email}")
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                print(f"[REGISTER] User already exists: {email}")
                return jsonify({'error': 'Email already registered'}), 409
            
            # Check if this is the first user - make them admin
            user_count = User.query.count()
            is_first_user = user_count == 0
            
            # Create user
            print(f"[REGISTER] Creating new user: {email}")
            user = User(email=email, full_name=full_name)
            user.set_password(password)
            
            if is_first_user:
                user.is_admin = True
                user.role = UserRole.ADMIN  # Set role to ADMIN for first user
                print(f"[REGISTER] First user - granting admin privileges (is_admin=True, role=ADMIN)")
            else:
                user.is_admin = False
                user.role = UserRole.STUDENT  # Explicitly set role to STUDENT
                print(f"[REGISTER] Regular student user (role=STUDENT)")
            
            # Add user to session
            db.session.add(user)
            print(f"[REGISTER] User added to session")
            
            # Flush to get the user ID before commit (important for serverless)
            db.session.flush()
            user_id = user.id
            print(f"[REGISTER] User flushed - ID: {user_id}")
            
            # Commit transaction - ensure it completes
            try:
            db.session.commit()
                print(f"[REGISTER] User committed to database - ID: {user_id}")
            except Exception as commit_error:
                print(f"[REGISTER] Commit failed: {commit_error}")
                db.session.rollback()
                raise
            
            # Verify user was saved by querying it back in a fresh query
            # This ensures the transaction was actually persisted to the database
            # Expire all objects to force fresh load from database
            db.session.expire_all()
            
            # Query user again to verify it was actually saved to database
            # Use with_entities to ensure password_hash column is loaded
            verified_user = User.query.filter_by(id=user_id).first()
            if not verified_user:
                print(f"[REGISTER] ERROR: User was not saved! ID: {user_id}")
                return jsonify({'error': 'Registration failed. User was not saved to database.'}), 500
            
            print(f"[REGISTER] User verified in database - ID: {verified_user.id}, Email: {verified_user.email}")
            
            # Verify password_hash was saved correctly
            if not verified_user.password_hash:
                print(f"[REGISTER] ERROR: Password hash missing for verified user!")
                return jsonify({'error': 'Registration failed. Password was not saved correctly.'}), 500
            
            print(f"[REGISTER] Password hash verified - Length: {len(verified_user.password_hash)}")
            
            # Test password verification to ensure it works immediately after save
            try:
                test_verify = verified_user.check_password(password)
                print(f"[REGISTER] Password verification test: {test_verify}")
                if not test_verify:
                    print(f"[REGISTER] WARNING: Password verification failed immediately after save!")
                    print(f"[REGISTER] Password hash value (first 50 chars): {verified_user.password_hash[:50] if verified_user.password_hash else 'None'}")
            except Exception as verify_error:
                print(f"[REGISTER] ERROR testing password verification: {verify_error}")
                import traceback
                traceback.print_exc()
            
            # Refresh the user object from the verified query
            user = verified_user
            
            # Login user after successful save
            # Mark session as permanent for serverless environments (Vercel)
            # This ensures the session cookie persists across function invocations
            from flask import session as flask_session
            flask_session.permanent = True
            login_user(user, remember=True)
            print(f"[REGISTER] User logged in: {email}")
            
            # Debug session creation
            print(f"[REGISTER] Session ID after login: {flask_session.get('_id', 'NO SESSION')}")
            print(f"[REGISTER] Session permanent: {flask_session.permanent}")
            print(f"[REGISTER] Current user authenticated: {current_user.is_authenticated}")
            
            return jsonify({'success': True, 'message': 'Registration successful', 'user_id': user.id}), 201
            
        except Exception as e:
            print(f"[REGISTER] ERROR: {e}")
            import traceback
            traceback.print_exc()
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
            print(f"[AUTH] User not found: {email}")
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Debug: Check if user was properly loaded
        print(f"[AUTH] User found - ID: {user.id}, Email: {user.email}, Active: {user.is_active}")
        print(f"[AUTH] Password hash exists: {bool(user.password_hash)}, Length: {len(user.password_hash) if user.password_hash else 0}")
        
        # Ensure password_hash is loaded (refresh from database if needed)
        if not user.password_hash:
            print(f"[AUTH] WARNING: No password hash found for user {email}, refreshing from database")
            db.session.refresh(user)
            if not user.password_hash:
                print(f"[AUTH] ERROR: Password hash still missing after refresh for user {email}")
                return jsonify({'error': 'User account error. Please contact administrator.'}), 500
        
        # Debug password check with better error handling
        try:
        password_valid = user.check_password(password)
        print(f"[AUTH] Login attempt - Email: {email}, Password valid: {password_valid}, User active: {user.is_active}")
        except Exception as e:
            print(f"[AUTH] ERROR checking password: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': 'Authentication error. Please contact administrator.'}), 500
        
        if not password_valid:
            print(f"[AUTH] Password validation failed for: {email}")
            return jsonify({'error': 'Invalid email or password'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account is disabled'}), 403
        
        try:
            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Mark session as permanent for serverless environments (Vercel)
            # This ensures the session cookie persists across function invocations
            from flask import session as flask_session
            flask_session.permanent = True
            # Track last activity time for session timeout
            flask_session['last_activity'] = datetime.utcnow().isoformat()
            login_user(user, remember=True)  # Always remember in serverless
            
            # Debug session creation
            print(f"[AUTH] Successful login: {email}")
            print(f"[AUTH] Session created - User ID: {user.id}, Email: {user.email}")
            print(f"[AUTH] Session permanent: {flask_session.permanent}")
            print(f"[AUTH] Remember: True (forced for serverless)")
            
            return jsonify({'success': True, 'message': 'Login successful'}), 200
        
        except Exception as e:
            print(f"[LOGIN] ERROR: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return jsonify({'error': 'Login failed. Please contact administrator or check logs.'}), 500
    
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
        print(f"[AUTH] Error refreshing session: {e}")
        import traceback
        traceback.print_exc()
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
        data = request.get_json() if request.is_json else request.form
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({'error': 'Email required'}), 400
        
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate recovery token
            token = user.generate_recovery_token()
            db.session.commit()
            
            # Send email
            email_sent = send_recovery_email(email, token)
            
            if not email_sent:
                print(f"[AUTH] Failed to send recovery email to {email}")
                return jsonify({'error': 'Failed to send recovery email. Please try again or contact support.'}), 500
        
        # Return success if user exists and email sent (don't reveal if email doesn't exist)
        return jsonify({'success': True, 'message': 'Check your email for recovery link'}), 200
    
    return render_template('forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with token"""
    user = User.query.filter_by(recovery_token=token).first()
    
    if not user or not user.verify_recovery_token(token):
        return render_template('reset_password_expired.html'), 401
    
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


@auth_bp.route('/test-email', methods=['GET'])
def test_email():
    """Test email configuration"""
    try:
        import requests
        resend_key = os.getenv('RESEND_API_KEY')
        
        result = {
            'resend_key_set': bool(resend_key),
            'resend_key_length': len(resend_key) if resend_key else 0,
            'requests_available': True,
            'app_url': os.getenv('APP_URL', 'https://frcr-examiner.vercel.app'),
            'email_from': os.getenv('EMAIL_FROM', 'onboarding@resend.dev')
        }
        
        return jsonify(result), 200
    except ImportError as e:
        return jsonify({'error': f'Import error: {str(e)}', 'requests_available': False}), 500
    except Exception as e:
        return jsonify({'error': f'Error: {str(e)}'}), 500


@auth_bp.route('/test-send-email', methods=['GET'])
def test_send_email():
    """Actually try to send a test email and return full response"""
    try:
        import requests
        resend_key = os.getenv('RESEND_API_KEY')
        
        if not resend_key:
            return jsonify({'error': 'RESEND_API_KEY not set'}), 500
        
        from_email = os.getenv('EMAIL_FROM', 'onboarding@resend.dev')
        test_to = 'test@example.com'  # Use a test email
        
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {resend_key}",
                "Content-Type": "application/json"
            },
            json={
                "from": from_email,
                "to": [test_to],
                "subject": "Test Email from FRCR Examiner",
                "html": "<h1>Test Email</h1><p>This is a test email.</p>"
            },
            timeout=10
        )
        
        return jsonify({
            'status_code': response.status_code,
            'response_text': response.text,
            'response_json': response.json() if response.headers.get('content-type', '').startswith('application/json') else None,
            'from_email': from_email,
            'to_email': test_to
        }), 200
        
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@auth_bp.route('/debug', methods=['GET'])
def debug_auth():
    """Debug authentication status"""
    from flask import session
    return jsonify({
        'is_authenticated': current_user.is_authenticated,
        'user_id': current_user.id if current_user.is_authenticated else None,
        'email': current_user.email if current_user.is_authenticated else None,
        'session_id': session.get('_id', 'No session'),
        'session_keys': list(session.keys())
    }), 200


@auth_bp.route('/debug/verify-db-users', methods=['GET'])
@login_required
def verify_db_users():
    """
    Verify that users and password hashes are stored in the database.
    Admin only - shows user info but NOT full password hashes (security).
    """
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    try:
        # Query all users from database
        users = User.query.all()
        
        users_data = []
        for user in users:
            # Check if password_hash exists and get its length (don't expose the hash itself)
            password_hash_exists = bool(user.password_hash)
            password_hash_length = len(user.password_hash) if user.password_hash else 0
            
            # Show first 20 chars of hash for verification (not the full hash)
            password_hash_preview = user.password_hash[:20] + '...' if user.password_hash and len(user.password_hash) > 20 else (user.password_hash if user.password_hash else None)
            
            users_data.append({
                'id': user.id,
                'email': user.email,
                'full_name': user.full_name,
                'is_admin': user.is_admin,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                # Password hash verification (safe to expose - it's a hash, not the password)
                'password_hash_exists': password_hash_exists,
                'password_hash_length': password_hash_length,
                'password_hash_preview': password_hash_preview,  # First 20 chars only
                'has_valid_password_hash': password_hash_exists and password_hash_length > 50  # Valid hashes are usually 100+ chars
            })
        
        return jsonify({
            'success': True,
            'total_users': len(users_data),
            'users': users_data,
            'message': f'Found {len(users_data)} user(s) in database. Password hashes are stored in the "password_hash" column.'
        }), 200
        
    except Exception as e:
        print(f"[DEBUG] Error verifying users: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error querying database: {str(e)}'}), 500


# ==================== ADMIN USER MANAGEMENT ====================

@auth_bp.route('/admin/promote-user', methods=['POST'])
@login_required
def promote_user():
    """Promote a user to admin - only accessible by existing admins"""
    if not current_user.is_admin:
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
    
    print(f"[ADMIN] User promoted to admin: {user_email} by {current_user.email}")
    
    return jsonify({'success': True, 'message': f'User {user_email} promoted to admin'}), 200


@auth_bp.route('/admin/list-users', methods=['GET'])
@login_required  
def list_users():
    """List all users with their admin status - admin only"""
    if not current_user.is_admin:
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
    """Upload profile picture"""
    try:
        data = request.get_json()
        picture_base64 = data.get('picture')
        
        if not picture_base64:
            return jsonify({'error': 'No picture provided'}), 400
        
        # Validate base64 format
        if not picture_base64.startswith('data:image/'):
            return jsonify({'error': 'Invalid image format'}), 400
        
        # Store base64 in database
        current_user.profile_picture = picture_base64
        db.session.commit()
        
        print(f"[PROFILE] Picture updated for user: {current_user.email}")
        return jsonify({'success': True, 'message': 'Profile picture updated'}), 200
        
    except Exception as e:
        print(f"[PROFILE] Error uploading picture: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to upload picture'}), 500


@auth_bp.route('/profile/picture', methods=['DELETE'])
@login_required
def remove_profile_picture():
    """Remove profile picture"""
    try:
        current_user.profile_picture = None
        db.session.commit()
        
        print(f"[PROFILE] Picture removed for user: {current_user.email}")
        return jsonify({'success': True, 'message': 'Profile picture removed'}), 200
        
    except Exception as e:
        print(f"[PROFILE] Error removing picture: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to remove picture'}), 500


@auth_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Update user profile (name and email)"""
    try:
        data = request.get_json()
        full_name = data.get('full_name', '').strip()
        email = data.get('email', '').strip().lower()
        
        if not full_name or not email:
            return jsonify({'error': 'Name and email are required'}), 400
        
        # Check if email is already taken by another user
        if email != current_user.email:
            existing = User.query.filter_by(email=email).first()
            if existing:
                return jsonify({'error': 'Email already in use'}), 409
        
        current_user.full_name = full_name
        current_user.email = email
        db.session.commit()
        
        print(f"[PROFILE] Profile updated for user: {email}")
        return jsonify({'success': True, 'message': 'Profile updated'}), 200
        
    except Exception as e:
        print(f"[PROFILE] Error updating profile: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update profile'}), 500


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
        
        print(f"[PROFILE] Password changed for user: {current_user.email}")
        return jsonify({'success': True, 'message': 'Password updated'}), 200
        
    except Exception as e:
        print(f"[PROFILE] Error changing password: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to change password'}), 500