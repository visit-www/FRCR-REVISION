#!/usr/bin/env python3
"""
Initialize database tables for production.
Run this script to create all tables in your Neon/PostgreSQL database.

Usage:
    python init_database.py
"""

import os
import sys
from app import app, db
from models import User

def init_database():
    """Create all database tables"""
    with app.app_context():
        try:
            print("=" * 60)
            print("Database Initialization")
            print("=" * 60)
            print()
            
            # Check current database state
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            print(f"Current tables in database: {existing_tables}")
            print()
            
            # Create all tables
            print("Creating database tables...")
            db.create_all()
            
            # Verify tables were created
            inspector = inspect(db.engine)
            new_tables = inspector.get_table_names()
            
            print(f"✅ Tables created successfully!")
            print(f"   Tables now in database: {new_tables}")
            print()
            
            # Check if user table has data
            try:
                user_count = User.query.count()
                print(f"   Users in database: {user_count}")
            except Exception as e:
                print(f"   ⚠️  Could not query users: {e}")
            
            print()
            print("=" * 60)
            print("Database initialization complete!")
            print("=" * 60)
            
            return True
            
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    # Check if DATABASE_URL is set
    if not os.getenv('DATABASE_URL') and not os.getenv('DATABASE_POSTGRES_URL_NON_POOLING'):
        print("⚠️  WARNING: DATABASE_URL not set!")
        print("   Set DATABASE_URL environment variable before running this script.")
        print("   For Neon: Use the connection string from your project settings.")
        sys.exit(1)
    
    print("Initializing database...")
    success = init_database()
    sys.exit(0 if success else 1)
