"""Delete all users from Supabase database"""
import os
from dotenv import load_dotenv

# Load environment variables from Vercel
load_dotenv('.env.production.local')

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment!")
    exit(1)

print(f"📊 Connecting to Supabase: {DATABASE_URL.split('@')[1][:50]}...")

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    # Connect to database
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get current users
    cursor.execute('SELECT id, email FROM "user"')
    users = cursor.fetchall()
    
    if users:
        print(f"\n📋 Found {len(users)} users:")
        for user in users:
            print(f"   - ID: {user['id']}, Email: {user['email']}")
        
        # Delete all users
        cursor.execute('DELETE FROM "user"')
        conn.commit()
        
        print(f"\n✅ Deleted all users from Supabase")
    else:
        print(f"\n✅ No users found (database already clean)")
    
    # Verify deletion
    cursor.execute('SELECT COUNT(*) as count FROM "user"')
    result = cursor.fetchone()
    print(f"✅ Remaining users: {result['count']}")
    
    cursor.close()
    conn.close()
    
except ImportError:
    print("❌ psycopg2 not installed. Installing...")
    os.system('pip install psycopg2-binary python-dotenv')
    print("\nTry running the script again!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
