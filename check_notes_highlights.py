#!/usr/bin/env python3
"""
Script to check for duplicate notes and highlights, and verify counts
"""

import sys
from app import app, db
from models import CandidateNote, TextHighlight, User

def check_duplicates():
    """Check for duplicate notes and highlights"""
    with app.app_context():
        print("=" * 80)
        print("CHECKING NOTES AND HIGHLIGHTS FOR DUPLICATES")
        print("=" * 80)
        
        # Get all users
        users = User.query.all()
        
        for user in users:
            print(f"\n{'='*80}")
            print(f"User: {user.email} (ID: {user.id}, Role: {user.role.value if user.role else 'N/A'})")
            print(f"{'='*80}")
            
            # Check notes
            notes = CandidateNote.query.filter_by(user_id=user.id).all()
            notes_count = len(notes)
            
            # Check for duplicate notes (same case_id, user_id, and note_text)
            notes_by_case = {}
            duplicate_notes = []
            
            for note in notes:
                key = (note.case_id, note.user_id, note.note_text)
                if key in notes_by_case:
                    duplicate_notes.append(note)
                else:
                    notes_by_case[key] = note
            
            print(f"\n📝 NOTES:")
            print(f"  Total notes: {notes_count}")
            print(f"  Unique notes: {len(notes_by_case)}")
            print(f"  Duplicate notes: {len(duplicate_notes)}")
            
            if duplicate_notes:
                print(f"\n  ⚠️  DUPLICATE NOTES FOUND:")
                for note in duplicate_notes:
                    print(f"    - Note ID: {note.id}, Case ID: {note.case_id}, Created: {note.created_at}")
                    print(f"      Text preview: {note.note_text[:50]}...")
            
            # Check highlights
            highlights = TextHighlight.query.filter_by(user_id=user.id).all()
            highlights_count = len(highlights)
            
            # Check for duplicate highlights (same case_id, user_id, text_content, and highlight_color)
            highlights_by_content = {}
            duplicate_highlights = []
            
            for highlight in highlights:
                key = (highlight.case_id, highlight.user_id, highlight.text_content, highlight.highlight_color)
                if key in highlights_by_content:
                    duplicate_highlights.append(highlight)
                else:
                    highlights_by_content[key] = highlight
            
            print(f"\n🖍️  HIGHLIGHTS:")
            print(f"  Total highlights: {highlights_count}")
            print(f"  Unique highlights: {len(highlights_by_content)}")
            print(f"  Duplicate highlights: {len(duplicate_highlights)}")
            
            if duplicate_highlights:
                print(f"\n  ⚠️  DUPLICATE HIGHLIGHTS FOUND:")
                for highlight in duplicate_highlights[:10]:  # Show first 10
                    print(f"    - Highlight ID: {highlight.id}, Case ID: {highlight.case_id}, Created: {highlight.created_at}")
                    print(f"      Text preview: {highlight.text_content[:50]}...")
                if len(duplicate_highlights) > 10:
                    print(f"    ... and {len(duplicate_highlights) - 10} more duplicates")
            
            # Count reviewed cases (distinct case_ids with notes)
            reviewed_cases = db.session.query(CandidateNote.case_id).filter_by(user_id=user.id).distinct().count()
            print(f"\n📊 REVIEWED CASES:")
            print(f"  Cases with notes: {reviewed_cases}")
            
            # Summary
            if duplicate_notes or duplicate_highlights:
                print(f"\n⚠️  SUMMARY FOR {user.email}:")
                if duplicate_notes:
                    print(f"  - {len(duplicate_notes)} duplicate notes need cleanup")
                if duplicate_highlights:
                    print(f"  - {len(duplicate_highlights)} duplicate highlights need cleanup")
            else:
                print(f"\n✅ No duplicates found for {user.email}")
        
        print(f"\n{'='*80}")
        print("CHECK COMPLETE")
        print(f"{'='*80}\n")

def clean_duplicates(dry_run=True):
    """Remove duplicate notes and highlights, keeping the oldest one"""
    with app.app_context():
        print("=" * 80)
        print(f"{'DRY RUN - ' if dry_run else ''}CLEANING DUPLICATES")
        print("=" * 80)
        
        users = User.query.all()
        total_notes_removed = 0
        total_highlights_removed = 0
        
        for user in users:
            print(f"\nProcessing user: {user.email} (ID: {user.id})")
            
            # Clean duplicate notes
            notes = CandidateNote.query.filter_by(user_id=user.id).order_by(CandidateNote.created_at).all()
            seen_notes = {}
            notes_to_delete = []
            
            for note in notes:
                key = (note.case_id, note.user_id, note.note_text)
                if key in seen_notes:
                    # This is a duplicate - mark for deletion
                    notes_to_delete.append(note)
                else:
                    seen_notes[key] = note
            
            if notes_to_delete:
                print(f"  Found {len(notes_to_delete)} duplicate notes to remove")
                if not dry_run:
                    for note in notes_to_delete:
                        db.session.delete(note)
                    db.session.commit()
                    print(f"  ✅ Removed {len(notes_to_delete)} duplicate notes")
                total_notes_removed += len(notes_to_delete)
            
            # Clean duplicate highlights
            highlights = TextHighlight.query.filter_by(user_id=user.id).order_by(TextHighlight.created_at).all()
            seen_highlights = {}
            highlights_to_delete = []
            
            for highlight in highlights:
                key = (highlight.case_id, highlight.user_id, highlight.text_content, highlight.highlight_color)
                if key in seen_highlights:
                    # This is a duplicate - mark for deletion
                    highlights_to_delete.append(highlight)
                else:
                    seen_highlights[key] = highlight
            
            if highlights_to_delete:
                print(f"  Found {len(highlights_to_delete)} duplicate highlights to remove")
                if not dry_run:
                    for highlight in highlights_to_delete:
                        db.session.delete(highlight)
                    db.session.commit()
                    print(f"  ✅ Removed {len(highlights_to_delete)} duplicate highlights")
                total_highlights_removed += len(highlights_to_delete)
        
        print(f"\n{'='*80}")
        if dry_run:
            print("DRY RUN SUMMARY:")
            print(f"  Would remove {total_notes_removed} duplicate notes")
            print(f"  Would remove {total_highlights_removed} duplicate highlights")
            print("\nTo actually remove duplicates, run with --clean flag")
        else:
            print("CLEANUP SUMMARY:")
            print(f"  ✅ Removed {total_notes_removed} duplicate notes")
            print(f"  ✅ Removed {total_highlights_removed} duplicate highlights")
        print(f"{'='*80}\n")

if __name__ == '__main__':
    if '--clean' in sys.argv:
        print("⚠️  WARNING: This will permanently delete duplicate notes and highlights!")
        if '--force' in sys.argv:
            print("--force flag detected, proceeding with cleanup...")
            clean_duplicates(dry_run=False)
        else:
            response = input("Are you sure you want to proceed? (yes/no): ")
            if response.lower() == 'yes':
                clean_duplicates(dry_run=False)
            else:
                print("Cancelled.")
    else:
        check_duplicates()
        print("\n" + "=" * 80)
        print("To remove duplicates, run: python check_notes_highlights.py --clean")
        print("Or force cleanup: python check_notes_highlights.py --clean --force")
        print("=" * 80)
