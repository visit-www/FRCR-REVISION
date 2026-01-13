#!/usr/bin/env python3
"""
Script to delete all staging cases from the database.
Use this before re-importing a backup to ensure images are properly stored.
"""
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, ImportedCaseStaging

def delete_all_staging_cases():
    """Delete all staging cases from the database"""
    with app.app_context():
        try:
            # Count staging cases
            count = ImportedCaseStaging.query.count()
            print(f"Found {count} staging cases to delete")
            
            if count == 0:
                print("No staging cases to delete.")
                return
            
            # Confirm deletion
            response = input(f"Are you sure you want to delete all {count} staging cases? (yes/no): ")
            if response.lower() != 'yes':
                print("Deletion cancelled.")
                return
            
            # Delete all staging cases
            deleted = ImportedCaseStaging.query.delete()
            db.session.commit()
            
            print(f"✓ Successfully deleted {deleted} staging cases")
            print("You can now re-import your backup file with the improved image matching logic.")
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error deleting staging cases: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    delete_all_staging_cases()
