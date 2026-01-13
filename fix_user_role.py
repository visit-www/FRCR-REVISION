#!/usr/bin/env python3
"""
Script to fix user role in Vercel deployment database
Usage: python fix_user_role.py <email> [--env-file .env.vercel.production]
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

def fix_user_role(email):
    """Fix user role to admin in database"""
    database_url = get_database_url()
    
    # Convert postgres:// to postgresql:// for SQLAlchemy
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    print(f"Connecting to database...")
    print(f"Database URL: {database_url[:50]}...")
    
    try:
        # Create engine and session
        engine = create_engine(database_url, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Find user by email
        print(f"\nLooking for user: {email}")
        user = session.query(User).filter(User.email.ilike(email)).first()
        
        if not user:
            print(f"ERROR: User '{email}' not found in database")
            session.close()
            return False
        
        # Display current user info
        print(f"\n=== USER FOUND ===")
        print(f"ID: {user.id}")
        print(f"Email: {user.email}")
        print(f"Full Name: {user.full_name}")
        print(f"Current Role: {user.role.value if hasattr(user.role, 'value') else user.role}")
        print(f"Role Type: {type(user.role).__name__}")
        print(f"is_admin (deprecated): {user.is_admin}")
        print(f"is_active: {user.is_active}")
        print(f"is_deleted: {user.is_deleted}")
        
        # Check current role value in database using raw SQL
        result = session.execute(text("SELECT role FROM \"user\" WHERE id = :user_id"), {"user_id": user.id})
        db_role_value = result.scalar()
        print(f"Role in database (raw): {db_role_value}, type: {type(db_role_value).__name__}")
        
        # Force update role to ADMIN using raw SQL (bypasses any enum issues)
        print(f"\n=== FIXING ROLE ===")
        print("Updating role to ADMIN in database using raw SQL...")
        
        # Check what enum values exist in the database
        try:
            enum_result = session.execute(text("SELECT unnest(enum_range(NULL::userrole))"))
            enum_values = [row[0] for row in enum_result]
            print(f"Available enum values in database: {enum_values}")
        except Exception as e:
            print(f"Could not query enum values: {e}")
            enum_values = ['ADMIN', 'admin', 'CONTENT_MANAGER', 'STUDENT']  # Common values
        
        # Try different case variations
        role_value = None
        for possible_value in ['ADMIN', 'admin', 'Admin']:
            if possible_value in enum_values or not enum_values:
                role_value = possible_value
                break
        
        if not role_value:
            role_value = 'ADMIN'  # Default to uppercase
        
        print(f"Using role value: {role_value}")
        
        # Update using raw SQL - try with the enum value directly
        # PostgreSQL enum casting: use the exact enum value
        try:
            session.execute(
                text("UPDATE \"user\" SET role = :role_value::userrole WHERE id = :user_id"),
                {"role_value": role_value, "user_id": user.id}
            )
            session.commit()
            print("✓ Updated using SQL enum cast")
        except Exception as e:
            print(f"SQL enum cast failed: {e}")
            # Try using SQLAlchemy enum instead
            try:
                user.role = UserRole.ADMIN
                session.commit()
                print("✓ Updated using SQLAlchemy enum")
            except Exception as e2:
                print(f"SQLAlchemy update also failed: {e2}")
                raise
        
        # Also update is_admin flag
        session.execute(
            text("UPDATE \"user\" SET is_admin = true WHERE id = :user_id"),
            {"user_id": user.id}
        )
        session.commit()
        
        # Verify update
        session.refresh(user)
        result = session.execute(text("SELECT role FROM \"user\" WHERE id = :user_id"), {"user_id": user.id})
        db_role_value = result.scalar()
        
        print(f"\n=== VERIFICATION ===")
        print(f"Role in database (raw): {db_role_value}")
        print(f"User.role: {user.role.value if hasattr(user.role, 'value') else user.role}")
        print(f"User.role type: {type(user.role).__name__}")
        print(f"is_admin: {user.is_admin}")
        
        # Check if it's actually admin
        if isinstance(user.role, UserRole) and user.role == UserRole.ADMIN:
            print(f"\n✓ Successfully fixed user role to ADMIN")
        elif str(db_role_value).lower() == 'admin':
            print(f"\n✓ Role value in database is 'admin'")
            print(f"  Note: Role object type may need refresh, but database value is correct")
        else:
            print(f"\n⚠ Warning: Role may not be properly set. Database value: {db_role_value}")
        
        session.close()
        return True
        
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python fix_user_role.py <email> [--env-file .env.vercel.production]")
        print("Example: python fix_user_role.py gaurav0133@gmail.com --env-file .env.vercel.production")
        sys.exit(1)
    
    email = sys.argv[1].strip().lower()
    print(f"Fixing user role for: {email}\n")
    
    success = fix_user_role(email)
    sys.exit(0 if success else 1)
