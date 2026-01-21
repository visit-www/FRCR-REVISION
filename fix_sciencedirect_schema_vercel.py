#!/usr/bin/env python3
"""
Script to add ScienceDirect columns to user table on Vercel/PostgreSQL.
Run this if the migration doesn't work or to directly add the columns.

Usage:
    # For local testing with Vercel env vars:
    vercel env pull .env.vercel
    source venv/bin/activate
    python fix_sciencedirect_schema_vercel.py
    
    # Or set DATABASE_URL directly:
    export DATABASE_URL="postgresql://..."
    python fix_sciencedirect_schema_vercel.py
"""

import os
import sys
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# Load environment variables from .env.vercel if it exists
if os.path.exists('.env.vercel'):
    print("[INFO] Loading environment variables from .env.vercel")
    with open('.env.vercel', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                value = value.strip('"\'')
                os.environ[key] = value

# Get database URL
DATABASE_URL = (
    os.getenv('DATABASE_POSTGRES_URL_NON_POOLING')
    or os.getenv('POSTGRES_URL_NON_POOLING')
    or os.getenv('DATABASE_URL')
    or os.getenv('POSTGRES_URL')
    or os.getenv('DATABASE_POSTGRES_URL')
)

if not DATABASE_URL:
    print("[ERROR] DATABASE_URL not found in environment variables")
    print("[INFO] Please set DATABASE_URL or load .env.vercel file")
    sys.exit(1)

# Clean URL
db_uri = DATABASE_URL.replace('postgres://', 'postgresql://')
try:
    parsed = urlparse(db_uri)
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        unsupported_params = ['supa', 'pgbouncer', 'supabase']
        for param in unsupported_params:
            params.pop(param, None)
        new_query = urlencode(params, doseq=True)
        db_uri = urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            parsed.params, new_query, parsed.fragment
        ))
except Exception:
    pass

print(f"[INFO] Connecting to database...")
print(f"[INFO] Database: {parsed.netloc if 'parsed' in locals() else 'Unknown'}")

try:
    from sqlalchemy import create_engine, text
    
    engine = create_engine(db_uri, pool_pre_ping=True)
    
    with engine.connect() as conn:
        # Check if columns already exist
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'user' 
            AND column_name IN ('sciencedirect_session_cookies', 'sciencedirect_connected_at')
        """)
        result = conn.execute(check_query)
        existing_columns = [row[0] for row in result]
        
        print(f"[INFO] Existing ScienceDirect columns: {existing_columns}")
        
        # Add columns if they don't exist
        if 'sciencedirect_session_cookies' not in existing_columns:
            print("[INFO] Adding sciencedirect_session_cookies column...")
            conn.execute(text("ALTER TABLE \"user\" ADD COLUMN sciencedirect_session_cookies TEXT"))
            conn.commit()
            print("[OK] Added sciencedirect_session_cookies")
        else:
            print("[SKIP] sciencedirect_session_cookies already exists")
        
        if 'sciencedirect_connected_at' not in existing_columns:
            print("[INFO] Adding sciencedirect_connected_at column...")
            conn.execute(text("ALTER TABLE \"user\" ADD COLUMN sciencedirect_connected_at TIMESTAMP"))
            conn.commit()
            print("[OK] Added sciencedirect_connected_at")
        else:
            print("[SKIP] sciencedirect_connected_at already exists")
        
        print("\n" + "=" * 60)
        print("SUCCESS: ScienceDirect columns added to database!")
        print("=" * 60)
        
except Exception as e:
    print(f"\n[ERROR] Failed to add columns: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
