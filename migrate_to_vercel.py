#!/usr/bin/env python3
"""
Database Migration Script: SQLite to PostgreSQL
Exports data from local SQLite and imports to Vercel Postgres
"""
import sqlite3
import psycopg2
from psycopg2.extras import execute_values
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Local SQLite database
LOCAL_DB = "/Users/zen/myRepos/projects/FRCR_EXAMINER/instance/frcr_examiner.db"

# PostgreSQL connection (from environment variable)
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("❌ Error: DATABASE_URL environment variable not set")
    print("Set it in Vercel: vercel env add DATABASE_URL")
    exit(1)

def get_sqlite_data():
    """Extract all data from SQLite database"""
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    data = {}
    
    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT * FROM {table_name}")
        data[table_name] = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return data

def migrate_to_postgres(data):
    """Migrate data to PostgreSQL"""
    # Convert postgres:// to postgresql:// for SQLAlchemy
    db_url = DATABASE_URL.replace('postgres://', 'postgresql://')
    
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        total_records = 0
        
        for table_name, rows in data.items():
            if not rows:
                print(f"  ⊘ {table_name}: no records")
                continue
            
            # Get column names from first row
            columns = list(rows[0].keys())
            
            # Prepare INSERT statement
            placeholders = ', '.join(['%s'] * len(columns))
            insert_query = f"""
                INSERT INTO {table_name} ({', '.join(columns)})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """
            
            # Extract values in correct order
            values = [
                [row.get(col) for col in columns]
                for row in rows
            ]
            
            # Execute batch insert
            cursor.executemany(insert_query, values)
            
            record_count = len(rows)
            total_records += record_count
            print(f"  ✓ {table_name}: {record_count} records")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"\n✅ Migration complete: {total_records} total records transferred")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("🔄 Starting SQLite → PostgreSQL migration...\n")
    
    # Check if local DB exists
    if not os.path.exists(LOCAL_DB):
        print(f"❌ Local database not found: {LOCAL_DB}")
        exit(1)
    
    print("📊 Extracting data from local SQLite database...")
    data = get_sqlite_data()
    
    print(f"Found {len(data)} tables:\n")
    for table in data.keys():
        record_count = len(data[table])
        print(f"  • {table}: {record_count} records")
    
    print("\n📤 Uploading to PostgreSQL...\n")
    success = migrate_to_postgres(data)
    
    if success:
        print("\n🎉 Your Vercel app now has all your data!")
        print("   Redeploy your app to use the new database:")
        print("   $ vercel --prod")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
