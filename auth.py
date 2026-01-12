"""
User authentication module
Handles login, signup, password recovery, and session management
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User
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
            
            # Create user
            print(f"[REGISTER] Creating new user: {email}")
            user = User(email=email, full_name=full_name)
            user.set_password(password)
            
            # Check if this is the first user - make them admin
            user_count = User.query.count()
            if user_count == 0:
                user.is_admin = True
                print(f"[REGISTER] First user - granting admin privileges")
            else:
                user.is_admin = False
                print(f"[REGISTER] Regular student user")
            
            db.session.add(user)
            print(f"[REGISTER] User added to session")
            
            db.session.commit()
            print(f"[REGISTER] User committed to database - ID: {user.id}")
            
            login_user(user)
            print(f"[REGISTER] User logged in: {email}")
            
            # Debug session creation
            from flask import session as flask_session
            print(f"[REGISTER] Session ID after login: {flask_session.get('_id', 'NO SESSION')}")
            print(f"[REGISTER] Current user authenticated: {current_user.is_authenticated}")
            
            return jsonify({'success': True, 'message': 'Registration successful'}), 201
            
        except Exception as e:
            print(f"[REGISTER] ERROR: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            # Don't expose database errors to users
            return jsonify({'error': 'Registration failed. Please contact administrator or check logs.'}), 500
        
        login_user(user)
        return jsonify({'success': True, 'message': 'Registration successful'}), 201
    
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
        
        user = User.query.filter_by(email=email).first()
        
        if not user:
            print(f"[AUTH] User not found: {email}")
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Debug password check with better error handling
        try:
            password_valid = user.check_password(password)
            print(f"[AUTH] Login attempt - Email: {email}, Password valid: {password_valid}, User active: {user.is_active}")
            print(f"[AUTH] Password hash exists: {bool(user.password_hash)}, Length: {len(user.password_hash) if user.password_hash else 0}")
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
            
            login_user(user, remember=remember)
            
            # Debug session creation
            print(f"[AUTH] Successful login: {email}")
            print(f"[AUTH] Session created - User ID: {user.id}, Email: {user.email}")
            print(f"[AUTH] Remember: {remember}")
            
            return jsonify({'success': True, 'message': 'Login successful'}), 200
        
        except Exception as e:
            print(f"[LOGIN] ERROR: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return jsonify({'error': 'Login failed. Please contact administrator or check logs.'}), 500
    
    return render_template('login.html')


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