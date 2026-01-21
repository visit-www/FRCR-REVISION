#!/usr/bin/env python3
"""
Fix User Schema - Add Notion and Anki columns
==============================================
Run this script to add the new Notion and Anki integration columns
to the user table in your database (SQLite or PostgreSQL).

Usage:
    python fix_user_schema.py

For Vercel/Neon, set DATABASE_URL environment variable first.
"""

import os
import sys

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

def get_database_url():
    """Get database URL from environment."""
    # Try various environment variable names
    for var in ['DATABASE_URL', 'POSTGRES_URL', 'NEON_DATABASE_URL']:
        url = os.getenv(var)
        if url:
            return url
    return None

def fix_sqlite(db_path):
    """Fix SQLite database schema."""
    import sqlite3
    
    print(f"[SQLite] Connecting to: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get current columns
    cursor.execute("PRAGMA table_info(user)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"[SQLite] Current columns: {len(columns)}")
    
    # New columns to add
    new_columns = [
        ('notion_access_token', 'VARCHAR(255)'),
        ('notion_workspace_id', 'VARCHAR(100)'),
        ('notion_connected_at', 'DATETIME'),
        ('anki_api_key', 'VARCHAR(255)'),
        ('anki_deck_name', 'VARCHAR(100)'),
        ('anki_connected_at', 'DATETIME'),
    ]
    
    added = 0
    for col_name, col_type in new_columns:
        if col_name not in columns:
            try:
                cursor.execute(f"ALTER TABLE user ADD COLUMN {col_name} {col_type}")
                print(f"[SQLite] Added column: {col_name}")
                added += 1
            except Exception as e:
                print(f"[SQLite] Error adding {col_name}: {e}")
        else:
            print(f"[SQLite] Column exists: {col_name}")
    
    conn.commit()
    conn.close()
    print(f"[SQLite] Done! Added {added} columns.")
    return True

def fix_postgres(database_url):
    """Fix PostgreSQL database schema."""
    import psycopg2
    
    print(f"[PostgreSQL] Connecting...")
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    
    # Get current columns
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'user'
    """)
    columns = [row[0] for row in cursor.fetchall()]
    print(f"[PostgreSQL] Current columns: {len(columns)}")
    
    # New columns to add
    new_columns = [
        ('notion_access_token', 'VARCHAR(255)'),
        ('notion_workspace_id', 'VARCHAR(100)'),
        ('notion_connected_at', 'TIMESTAMP'),
        ('anki_api_key', 'VARCHAR(255)'),
        ('anki_deck_name', 'VARCHAR(100)'),
        ('anki_connected_at', 'TIMESTAMP'),
    ]
    
    added = 0
    for col_name, col_type in new_columns:
        if col_name not in columns:
            try:
                cursor.execute(f'ALTER TABLE "user" ADD COLUMN {col_name} {col_type}')
                print(f"[PostgreSQL] Added column: {col_name}")
                added += 1
            except Exception as e:
                print(f"[PostgreSQL] Error adding {col_name}: {e}")
                conn.rollback()
        else:
            print(f"[PostgreSQL] Column exists: {col_name}")
    
    conn.commit()
    conn.close()
    print(f"[PostgreSQL] Done! Added {added} columns.")
    return True

def main():
    print("=" * 50)
    print("Fix User Schema - Add Notion/Anki Columns")
    print("=" * 50)
    
    database_url = get_database_url()
    
    if database_url and database_url.startswith('postgres'):
        try:
            import psycopg2
            fix_postgres(database_url)
        except ImportError:
            print("[ERROR] psycopg2 not installed. Run: pip install psycopg2-binary")
            sys.exit(1)
    else:
        # Fall back to SQLite
        db_path = 'instance/frcr_examiner.db'
        if os.path.exists(db_path):
            fix_sqlite(db_path)
        else:
            print(f"[ERROR] SQLite database not found at: {db_path}")
            print("[ERROR] Set DATABASE_URL for PostgreSQL or ensure SQLite exists.")
            sys.exit(1)
    
    print("\n✅ Schema fix complete!")

if __name__ == '__main__':
    main()
