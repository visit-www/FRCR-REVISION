#!/usr/bin/env python3
"""
Script to run database migrations on Vercel/Neon PostgreSQL.
Can be run locally with Vercel environment variables.

Usage:
    vercel env pull .env.vercel
    source venv/bin/activate
    python scripts/utilities/run_migration.py
"""

import os
import sys
from pathlib import Path

# Add project root to path so "from app import app" works
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load environment variables from .env.vercel if it exists (project root)
_env_vercel = _PROJECT_ROOT / '.env.vercel'
if _env_vercel.exists():
    print("[INFO] Loading environment variables from .env.vercel")
    with open(_env_vercel, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes and whitespace (e.g. trailing newline from .env)
                value = value.strip().strip('"\'')
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
            print("\n[INFO] Checking current migration status...")
            from flask_migrate import current, heads
            current_rev = current()
            head_revs = heads()
            print(f"[INFO] Current revision: {current_rev}")
            print(f"[INFO] Head revisions: {head_revs}")
            
            print("\n[INFO] Running migrations to head...")
            upgrade()
            print("\n" + "=" * 60)
            print("SUCCESS: Migrations completed successfully!")
            print("=" * 60)
        except Exception as e:
            error_msg = str(e)
            print(f"\n[ERROR] Migration failed: {error_msg}")
            
            # If it's a multiple heads error, suggest merge
            if 'Multiple head revisions' in error_msg:
                print("\n[INFO] Multiple head revisions detected.")
                print("[INFO] A merge migration has been created.")
                print("[INFO] Try running the migration again.")
            else:
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
