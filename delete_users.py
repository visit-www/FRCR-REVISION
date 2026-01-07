"""Delete all users from database"""
import os
from app import app, db
from models import User

with app.app_context():
    try:
        users = User.query.all()
        print(f"Found {len(users)} users:")
        for user in users:
            print(f"  - ID: {user.id}, Email: {user.email}")
        
        # Delete all
        db.session.query(User).delete()
        db.session.commit()
        
        print(f"\n✅ Deleted all users from database")
        
        # Verify
        remaining = User.query.count()
        print(f"Remaining users: {remaining}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.session.rollback()
