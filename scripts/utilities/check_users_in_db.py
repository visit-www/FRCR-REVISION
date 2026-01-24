#!/usr/bin/env python3
"""
Script to verify that users and password hashes are stored in the database.
Run this to check if credentials are actually being saved.

Usage:
    python check_users_in_db.py
"""

import os
import sys
from app import app, db
from models import User

def check_users_in_database():
    """Check if users and password hashes exist in the database"""
    with app.app_context():
        try:
            # Query all users
            users = User.query.all()
            
            print(f"\n{'='*60}")
            print(f"Database User Verification")
            print(f"{'='*60}\n")
            
            if not users:
                print("❌ NO USERS FOUND IN DATABASE!")
                print("   This means registration is NOT saving users to the database.")
                return False
            
            print(f"✅ Found {len(users)} user(s) in database\n")
            
            for user in users:
                print(f"User ID: {user.id}")
                print(f"  Email: {user.email}")
                print(f"  Full Name: {user.full_name}")
                print(f"  Is Admin: {user.is_admin}")
                print(f"  Is Active: {user.is_active}")
                print(f"  Created At: {user.created_at}")
                
                # Check password hash
                if user.password_hash:
                    hash_length = len(user.password_hash)
                    hash_preview = user.password_hash[:30] + '...' if len(user.password_hash) > 30 else user.password_hash
                    
                    print(f"  ✅ Password Hash EXISTS")
                    print(f"     Length: {hash_length} characters")
                    print(f"     Preview: {hash_preview}")
                    
                    # Valid Werkzeug hashes are usually 100+ characters
                    if hash_length < 50:
                        print(f"     ⚠️  WARNING: Hash seems too short (should be 100+ chars)")
                    else:
                        print(f"     ✅ Hash length looks valid")
                else:
                    print(f"  ❌ Password Hash MISSING!")
                    print(f"     This user cannot log in - password was not saved!")
                
                print()
            
            print(f"{'='*60}")
            print("Summary:")
            print(f"  Total users: {len(users)}")
            users_with_hash = sum(1 for u in users if u.password_hash)
            print(f"  Users with password hash: {users_with_hash}/{len(users)}")
            
            if users_with_hash == len(users):
                print(f"  ✅ All users have password hashes stored in database")
            else:
                print(f"  ❌ Some users are missing password hashes!")
            
            print(f"{'='*60}\n")
            
            return True
            
        except Exception as e:
            print(f"\n❌ ERROR querying database: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    print("Checking database for users and password hashes...")
    check_users_in_database()
