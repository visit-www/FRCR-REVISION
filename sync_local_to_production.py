#!/usr/bin/env python3
"""
Sync Local SQLite Database to Production Supabase PostgreSQL

This script exports data from your local SQLite database and imports it
into your production Supabase PostgreSQL database.

Usage:
    python3 sync_local_to_production.py

Requirements:
    - Local SQLite database at instance/frcr_examiner.db
    - Production database connection string in environment variable
    - DATABASE_POSTGRES_URL_NON_POOLING or DATABASE_URL set
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app import app, db
from models import (
    User, Case, CaseImage, Question, Answer, ExamSession, Packet, Candidate,
    RevisionSession, RevisionHistory, CaseFlag, TextHighlight, CandidateNote,
    ImportedCaseStaging
)

def export_local_data():
    """Export all data from local SQLite database to JSON"""
    print("=" * 70)
    print("EXPORTING LOCAL DATABASE")
    print("=" * 70)
    print()
    
    with app.app_context():
        data = {}
        
        # Export Users
        print("Exporting Users...")
        users = User.query.filter_by(is_deleted=False).all()
        data['users'] = [{
            'email': u.email,
            'password_hash': u.password_hash,
            'full_name': u.full_name,
            'role': u.role.value if u.role else 'student',
            'is_active': u.is_active,
            'subscription_status': u.subscription_status.value if u.subscription_status else 'free',
            'payment_status': u.payment_status.value if u.payment_status else 'no_subscription',
            'created_at': u.created_at.isoformat() if u.created_at else None,
            'last_login': u.last_login.isoformat() if u.last_login else None,
        } for u in users]
        print(f"  ✓ Exported {len(data['users'])} users")
        
        # Export Cases
        print("Exporting Cases...")
        cases = Case.query.all()
        data['cases'] = []
        for case in cases:
            case_data = {
                'case_number': case.case_number,
                'diagnosis': case.diagnosis,
                'discussion': case.discussion,
                'modality': case.modality,
                'module': case.module.value if case.module else None,
                'body_part': case.body_part.value if case.body_part else None,
                'age_group': case.age_group.value if case.age_group else None,
                'is_public': case.is_public,
                'created_at': case.created_at.isoformat() if case.created_at else None,
                'created_by_user_id': case.created_by_user_id,
            }
            
            # Export Questions
            questions = Question.query.filter_by(case_id=case.id).order_by(Question.question_number).all()
            case_data['questions'] = [{
                'question_number': q.question_number,
                'question_text': q.question_text,
            } for q in questions]
            
            # Export Answers
            answers = Answer.query.filter_by(case_id=case.id).order_by(Answer.answer_number).all()
            case_data['answers'] = [{
                'answer_number': a.answer_number,
                'answer_text': a.answer_text,
            } for a in answers]
            
            # Export Images
            images = CaseImage.query.filter_by(case_id=case.id).all()
            case_data['images'] = [{
                'filename': img.filename,
                'image_type': img.image_type,
                'description': img.description,
                'image_data': img.image_data.hex() if img.image_data else None,  # Convert binary to hex
            } for img in images]
            
            data['cases'].append(case_data)
        print(f"  ✓ Exported {len(data['cases'])} cases")
        
        # Export other data
        print("Exporting Revision Sessions...")
        sessions = RevisionSession.query.all()
        data['revision_sessions'] = [{
            'user_id': s.user_id,
            'case_ids': s.get_case_ids_list() if hasattr(s, 'get_case_ids_list') else json.loads(s.case_ids or '[]'),
            'current_case_index': s.current_case_index,
            'created_at': s.created_at.isoformat() if s.created_at else None,
        } for s in sessions]
        print(f"  ✓ Exported {len(data['revision_sessions'])} revision sessions")
        
        print("Exporting Case Flags...")
        flags = CaseFlag.query.all()
        data['case_flags'] = [{
            'user_id': f.user_id,
            'case_id': f.case_id,
            'created_at': f.created_at.isoformat() if f.created_at else None,
        } for f in flags]
        print(f"  ✓ Exported {len(data['case_flags'])} case flags")
        
        print("Exporting Highlights...")
        highlights = TextHighlight.query.all()
        data['highlights'] = [{
            'user_id': h.user_id,
            'case_id': h.case_id,
            'text_content': h.text_content,
            'highlight_color': h.highlight_color,
            'field_name': h.field_name,
            'created_at': h.created_at.isoformat() if h.created_at else None,
        } for h in highlights]
        print(f"  ✓ Exported {len(data['highlights'])} highlights")
        
        print("Exporting Notes...")
        notes = CandidateNote.query.all()
        data['notes'] = [{
            'user_id': n.user_id,
            'case_id': n.case_id,
            'note_text': n.note_text,
            'created_at': n.created_at.isoformat() if n.created_at else None,
        } for n in notes]
        print(f"  ✓ Exported {len(data['notes'])} notes")
        
        return data

def import_to_production(data):
    """Import data into production PostgreSQL database"""
    print()
    print("=" * 70)
    print("IMPORTING TO PRODUCTION DATABASE")
    print("=" * 70)
    print()
    
    # Switch to production database
    prod_db_url = os.getenv('DATABASE_POSTGRES_URL_NON_POOLING') or os.getenv('DATABASE_URL')
    if not prod_db_url:
        print("❌ ERROR: Production database URL not found!")
        print("   Set DATABASE_POSTGRES_URL_NON_POOLING or DATABASE_URL environment variable")
        return False
    
    # Update app config to use production database
    original_db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
    app.config['SQLALCHEMY_DATABASE_URI'] = prod_db_url.replace('postgres://', 'postgresql://')
    
    # Remove query parameters that might cause issues
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    try:
        parsed = urlparse(app.config['SQLALCHEMY_DATABASE_URI'])
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            unsupported_params = ['supa', 'pgbouncer', 'supabase']
            for param in unsupported_params:
                params.pop(param, None)
            new_query = urlencode(params, doseq=True) if params else ''
            app.config['SQLALCHEMY_DATABASE_URI'] = urlunparse((
                parsed.scheme, parsed.netloc, parsed.path,
                parsed.params, new_query, parsed.fragment
            ))
    except Exception as e:
        print(f"Warning: Could not clean URL parameters: {e}")
    
    with app.app_context():
        try:
            # Test connection
            print("Testing production database connection...")
            db.engine.connect()
            print("  ✓ Connected to production database")
            print()
            
            # Import Users
            print("Importing Users...")
            imported_users = 0
            user_id_map = {}  # Map old user IDs to new user IDs
            
            for user_data in data.get('users', []):
                # Check if user already exists
                existing = User.query.filter_by(email=user_data['email']).first()
                if existing:
                    print(f"  ⚠️  User {user_data['email']} already exists, skipping...")
                    user_id_map[user_data.get('id', 0)] = existing.id
                    continue
                
                user = User(
                    email=user_data['email'],
                    password_hash=user_data['password_hash'],
                    full_name=user_data['full_name'],
                    role=user_data.get('role', 'student'),
                    is_active=user_data.get('is_active', True),
                    subscription_status=user_data.get('subscription_status', 'free'),
                    payment_status=user_data.get('payment_status', 'no_subscription'),
                )
                if user_data.get('created_at'):
                    user.created_at = datetime.fromisoformat(user_data['created_at'])
                if user_data.get('last_login'):
                    user.last_login = datetime.fromisoformat(user_data['last_login'])
                
                db.session.add(user)
                db.session.flush()  # Get the new ID
                old_id = user_data.get('id', 0)
                if old_id:
                    user_id_map[old_id] = user.id
                imported_users += 1
            
            db.session.commit()
            print(f"  ✓ Imported {imported_users} users")
            
            # Import Cases
            print("Importing Cases...")
            imported_cases = 0
            case_id_map = {}  # Map old case IDs to new case IDs
            
            for case_data in data.get('cases', []):
                case = Case(
                    case_number=case_data['case_number'],
                    diagnosis=case_data['diagnosis'],
                    discussion=case_data.get('discussion', ''),
                    modality=case_data.get('modality', ''),
                    module=case_data.get('module'),
                    body_part=case_data.get('body_part'),
                    age_group=case_data.get('age_group'),
                    is_public=case_data.get('is_public', True),
                    created_by_user_id=user_id_map.get(case_data.get('created_by_user_id', 0)) if case_data.get('created_by_user_id') else None,
                )
                if case_data.get('created_at'):
                    case.created_at = datetime.fromisoformat(case_data['created_at'])
                
                db.session.add(case)
                db.session.flush()
                old_case_id = case_data.get('id', 0)
                if old_case_id:
                    case_id_map[old_case_id] = case.id
                new_case_id = case.id
                
                # Import Questions
                for q_data in case_data.get('questions', []):
                    question = Question(
                        case_id=new_case_id,
                        question_number=q_data['question_number'],
                        question_text=q_data['question_text'],
                    )
                    db.session.add(question)
                
                # Import Answers
                for a_data in case_data.get('answers', []):
                    answer = Answer(
                        case_id=new_case_id,
                        answer_number=a_data['answer_number'],
                        answer_text=a_data['answer_text'],
                    )
                    db.session.add(answer)
                
                # Import Images
                for img_data in case_data.get('images', []):
                    image = CaseImage(
                        case_id=new_case_id,
                        filename=img_data.get('filename', ''),
                        image_type=img_data.get('image_type', ''),
                        description=img_data.get('description', ''),
                    )
                    if img_data.get('image_data'):
                        # Convert hex back to binary
                        image.image_data = bytes.fromhex(img_data['image_data'])
                    db.session.add(image)
                
                imported_cases += 1
            
            db.session.commit()
            print(f"  ✓ Imported {imported_cases} cases with Q&A and images")
            
            # Import other data
            print("Importing Revision Sessions...")
            imported_sessions = 0
            for session_data in data.get('revision_sessions', []):
                user_id = user_id_map.get(session_data.get('user_id', 0))
                if not user_id:
                    continue
                
                session = RevisionSession(
                    user_id=user_id,
                    current_case_index=session_data.get('current_case_index', 0),
                )
                case_ids = session_data.get('case_ids', [])
                # Map old case IDs to new ones
                mapped_case_ids = [case_id_map.get(cid, cid) for cid in case_ids if case_id_map.get(cid)]
                if mapped_case_ids:
                    session.set_case_ids_list(mapped_case_ids)
                if session_data.get('created_at'):
                    session.created_at = datetime.fromisoformat(session_data['created_at'])
                
                db.session.add(session)
                imported_sessions += 1
            db.session.commit()
            print(f"  ✓ Imported {imported_sessions} revision sessions")
            
            print("Importing Case Flags...")
            imported_flags = 0
            for flag_data in data.get('case_flags', []):
                user_id = user_id_map.get(flag_data.get('user_id', 0))
                case_id = case_id_map.get(flag_data.get('case_id', 0))
                if not user_id or not case_id:
                    continue
                
                # Check if flag already exists
                existing = CaseFlag.query.filter_by(user_id=user_id, case_id=case_id).first()
                if existing:
                    continue
                
                flag = CaseFlag(
                    user_id=user_id,
                    case_id=case_id,
                )
                if flag_data.get('created_at'):
                    flag.created_at = datetime.fromisoformat(flag_data['created_at'])
                db.session.add(flag)
                imported_flags += 1
            db.session.commit()
            print(f"  ✓ Imported {imported_flags} case flags")
            
            print("Importing Highlights...")
            imported_highlights = 0
            for highlight_data in data.get('highlights', []):
                user_id = user_id_map.get(highlight_data.get('user_id', 0))
                case_id = case_id_map.get(highlight_data.get('case_id', 0))
                if not user_id or not case_id:
                    continue
                
                highlight = TextHighlight(
                    user_id=user_id,
                    case_id=case_id,
                    text_content=highlight_data.get('text_content', ''),
                    highlight_color=highlight_data.get('highlight_color', 'yellow'),
                    field_name=highlight_data.get('field_name', 'discussion'),
                )
                if highlight_data.get('created_at'):
                    highlight.created_at = datetime.fromisoformat(highlight_data['created_at'])
                db.session.add(highlight)
                imported_highlights += 1
            db.session.commit()
            print(f"  ✓ Imported {imported_highlights} highlights")
            
            print("Importing Notes...")
            imported_notes = 0
            for note_data in data.get('notes', []):
                user_id = user_id_map.get(note_data.get('user_id', 0))
                case_id = case_id_map.get(note_data.get('case_id', 0))
                if not user_id or not case_id:
                    continue
                
                note = CandidateNote(
                    user_id=user_id,
                    case_id=case_id,
                    note_text=note_data.get('note_text', ''),
                )
                if note_data.get('created_at'):
                    note.created_at = datetime.fromisoformat(note_data['created_at'])
                db.session.add(note)
                imported_notes += 1
            db.session.commit()
            print(f"  ✓ Imported {imported_notes} notes")
            
            print()
            print("=" * 70)
            print("✅ SYNC COMPLETE!")
            print("=" * 70)
            print()
            print("Summary:")
            print(f"  • Users: {imported_users}")
            print(f"  • Cases: {imported_cases}")
            print(f"  • Revision Sessions: {imported_sessions}")
            print(f"  • Case Flags: {imported_flags}")
            print(f"  • Highlights: {imported_highlights}")
            print(f"  • Notes: {imported_notes}")
            print()
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Restore original database URI
            if original_db_uri:
                app.config['SQLALCHEMY_DATABASE_URI'] = original_db_uri

def main():
    """Main sync function"""
    print()
    print("=" * 70)
    print("SYNC LOCAL DATABASE TO PRODUCTION")
    print("=" * 70)
    print()
    print("This will:")
    print("  1. Export data from local SQLite database")
    print("  2. Import data into production Supabase PostgreSQL")
    print()
    print("⚠️  WARNING: This will add data to production database.")
    print("   Existing data will NOT be deleted, but duplicates may be created.")
    print()
    
    response = input("Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted.")
        return
    
    # Export from local
    data = export_local_data()
    
    if not data:
        print("❌ Failed to export local data")
        return
    
    # Import to production
    success = import_to_production(data)
    
    if success:
        print("✅ Sync completed successfully!")
    else:
        print("❌ Sync failed. Check errors above.")

if __name__ == '__main__':
    main()
