#!/usr/bin/env python3
"""
Clear all candidate notes from the database for fresh testing.
USE WITH CAUTION - THIS DELETES ALL NOTES!
"""

import sys
from app import app, db
from models import CandidateNote

def clear_all_notes():
    """Delete all candidate notes from the database."""
    with app.app_context():
        try:
            # Count notes before deletion
            count = CandidateNote.query.count()
            print(f"Found {count} notes in database")
            
            if count == 0:
                print("No notes to delete.")
                return
            
            # Ask for confirmation
            confirm = input(f"Are you sure you want to delete ALL {count} notes? (yes/no): ")
            if confirm.lower() != 'yes':
                print("Cancelled.")
                return
            
            # Delete all notes
            CandidateNote.query.delete()
            db.session.commit()
            
            print(f"✅ Successfully deleted {count} notes from database.")
            print("\nNext steps:")
            print("1. Open your browser")
            print("2. Open console (F12)")
            print("3. Run: localStorage.clear()")
            print("4. Reload the page")
            print("5. Test creating a new note on some text")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error: {e}")
            sys.exit(1)

if __name__ == '__main__':
    print("=" * 60)
    print("CLEAR ALL CANDIDATE NOTES")
    print("=" * 60)
    print("\nWARNING: This will delete ALL notes from the database!")
    print("This is for testing purposes only.\n")
    
    clear_all_notes()
