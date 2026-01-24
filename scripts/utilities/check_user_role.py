#!/usr/bin/env python3
"""
Script to check and update user role in Vercel deployment
Usage: python check_user_role.py <email> [--env-file .env.vercel.production]
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models import User, UserRole, db

# Load environment variables from file if provided
if '--env-file' in sys.argv:
    env_file_idx = sys.argv.index('--env-file')
    if env_file_idx + 1 < len(sys.argv):
        env_file = sys.argv[env_file_idx + 1]
        print(f"Loading environment from: {env_file}")
        # Parse .env file manually
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Remove quotes if present
                        value = value.strip('"\'')
                        os.environ[key.strip()] = value
            print(f"Loaded environment variables from {env_file}")
        except Exception as e:
            print(f"Warning: Could not load {env_file}: {e}")
        # Remove from sys.argv so email parsing works
        sys.argv.pop(env_file_idx)
        sys.argv.pop(env_file_idx)

def get_database_url():
    """Get database URL from environment variables"""
    # Vercel uses POSTGRES_URL_NON_POOLING for direct connections
    database_url = (
        os.getenv('POSTGRES_URL_NON_POOLING') or 
        os.getenv('DATABASE_POSTGRES_URL_NON_POOLING') or 
        os.getenv('DATABASE_URL') or 
        os.getenv('DATABASE_POSTGRES_URL') or 
        os.getenv('POSTGRES_URL')
    )
    
    if not database_url:
        print("ERROR: No database URL found in environment variables")
        print("Available env vars:", [k for k in os.environ.keys() if 'DATABASE' in k or 'POSTGRES' in k])
        sys.exit(1)
    
    return database_url

def check_and_update_user(email):
    """Check user role and update to admin if needed"""
    database_url = get_database_url()
    
    # Convert postgres:// to postgresql:// for SQLAlchemy
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    print(f"Connecting to database...")
    print(f"Database URL: {database_url[:50]}...")  # Show first 50 chars only
    
    try:
        # Create engine and session
        engine = create_engine(database_url, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Find user by email (case-insensitive)
        print(f"\nLooking for user: {email}")
        user = session.query(User).filter(User.email.ilike(email)).first()
        
        if not user:
            # List all users to help debug
            print(f"\nERROR: User '{email}' not found in database")
            print(f"\nListing all users in database:")
            all_users = session.query(User).all()
            if all_users:
                for u in all_users:
                    print(f"  - {u.email} (ID: {u.id}, Role: {u.role.value if u.role else 'None'})")
            else:
                print("  No users found in database")
            session.close()
            return False
        
        # Display current user info
        print(f"\n=== USER FOUND ===")
        print(f"ID: {user.id}")
        print(f"Email: {user.email}")
        print(f"Full Name: {user.full_name}")
        print(f"Current Role: {user.role.value if user.role else 'None'}")
        print(f"is_admin (deprecated): {user.is_admin}")
        print(f"is_active: {user.is_active}")
        print(f"is_deleted: {user.is_deleted}")
        
        # Check if role is ADMIN
        if user.role == UserRole.ADMIN:
            print(f"\n✓ User is already ADMIN - no changes needed")
            session.close()
            return True
        
        # Update to ADMIN
        print(f"\n⚠ User is NOT admin (current role: {user.role.value})")
        print(f"Updating role to ADMIN...")
        
        user.role = UserRole.ADMIN
        user.is_admin = True  # Also set deprecated field for compatibility
        
        session.commit()
        
        # Verify update
        session.refresh(user)
        print(f"\n✓ Successfully updated user role to ADMIN")
        print(f"New Role: {user.role.value}")
        
        session.close()
        return True
        
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python check_user_role.py <email>")
        print("Example: python check_user_role.py garuav0133@gmail.com")
        sys.exit(1)
    
    email = sys.argv[1].strip().lower()
    print(f"Checking user role for: {email}\n")
    
    success = check_and_update_user(email)
    sys.exit(0 if success else 1)
