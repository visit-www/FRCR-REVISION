#!/usr/bin/env python3
"""
Script to run database migrations on Vercel/Supabase.
Can be run locally with Vercel environment variables.

Usage:
    vercel env pull .env.vercel
    source venv/bin/activate
    python3 run_migration.py
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
                # Remove quotes if present
                value = value.strip('"\'')
                os.environ[key] = value

# Set Flask app
os.environ['FLASK_APP'] = 'app.py'

# Import Flask app and migrate
from app import app
from flask_migrate import upgrade

def run_migration():
    """Run database migrations"""
    print("=" * 60)
    print("Running Database Migrations")
    print("=" * 60)
    
    with app.app_context():
        try:
            print("\n[INFO] Running migrations...")
            upgrade()
            print("\n" + "=" * 60)
            print("SUCCESS: Migrations completed successfully!")
            print("=" * 60)
        except Exception as e:
            print(f"\n[ERROR] Migration failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    # Check if running in Vercel environment
    if os.getenv('VERCEL'):
        print("[INFO] Running in Vercel environment")
    else:
        print("[INFO] Running in local environment")
        print("[INFO] Make sure you have loaded environment variables")
        print("[INFO] Use: vercel env pull (if using Vercel CLI)")
    
    run_migration()
