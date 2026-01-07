"""Create database tables on Supabase"""
import os
from app import app, db

with app.app_context():
    try:
        print("📊 Checking database connection...")
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        print(f"Database: {db_uri[:60]}...")
        
        print("\n🔨 Creating all tables...")
        db.create_all()
        
        print("✅ All tables created successfully!")
        
        # Verify tables exist
        from models import User, ExamSession
        print("\n📋 Verifying tables:")
        print(f"   - User table: {User.__tablename__}")
        print(f"   - ExamSession table: {ExamSession.__tablename__}")
        print("\n✅ Database migration complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
