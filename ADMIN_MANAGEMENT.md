# Admin User Management Endpoints

Add these routes to auth.py after the debug_auth route:

```python
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
```

## How to Use:

### Via Browser Console (when logged in as admin):

```javascript
// Promote a user to admin
fetch('/auth/admin/promote-user', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({email: 'student@frcrrevision.com'})
}).then(r => r.json()).then(console.log);

// List all users
fetch('/auth/admin/list-users')
    .then(r => r.json())
    .then(console.log);
```

### Via curl:

```bash
# Promote user (must be logged in as admin first)
curl -X POST http://localhost:5000/auth/admin/promote-user \
  -H "Content-Type: application/json" \
  -d '{"email": "student@frcrrevision.com"}' \
  --cookie "session=YOUR_SESSION_COOKIE"
```
