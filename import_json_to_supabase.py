#!/usr/bin/env python3
"""
Direct import script for FRCR-Revision JSON backup to Supabase PostgreSQL
Bypasses Vercel's 4.5MB request limit by connecting directly to Supabase

Usage:
    python import_json_to_supabase.py backup_file.json [--password YOUR_PASSWORD] [--overwrite]
"""

import sys
import json
import os
import argparse
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models import (
    db, User, Case, CaseImage, Question, Answer,
    RevisionSession, RevisionHistory, CaseFlag, TextHighlight, CandidateNote,
    ImportedCaseStaging, UserRole, FRCRModule, BodyPart, AgeGroup,
    SubscriptionStatus, PaymentStatus
)

# Supabase connection string template
# Use the non-pooling connection for direct imports
SUPABASE_CONNECTION_TEMPLATE = "postgresql://postgres.qtucmbwxlssffvlqjhvh:{password}@aws-1-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require"

def get_connection_string(password):
    """Get Supabase connection string with password"""
    return SUPABASE_CONNECTION_TEMPLATE.format(password=password)

def read_json_backup(file_path):
    """Read JSON backup file in chunks for large files"""
    print(f"[IMPORT] Reading backup file: {file_path}")
    
    file_size = os.path.getsize(file_path)
    print(f"[IMPORT] File size: {file_size / 1024 / 1024:.2f} MB")
    
    # Read file in chunks
    file_content_parts = []
    chunk_size = 1024 * 1024  # 1MB chunks
    total_read = 0
    
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            file_content_parts.append(chunk)
            total_read += len(chunk)
            print(f"[IMPORT] Read: {total_read / 1024 / 1024:.2f} MB / {file_size / 1024 / 1024:.2f} MB")
    
    # Combine and decode
    file_content = b''.join(file_content_parts).decode('utf-8')
    backup_data = json.loads(file_content)
    
    print(f"[IMPORT] Successfully loaded JSON backup")
    return backup_data

def import_to_supabase(backup_data, engine, overwrite_existing=False):
    """Import backup data to Supabase using existing backup_routes logic"""
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()
    
    stats = {
        'users': {'added': 0, 'updated': 0, 'skipped': 0},
        'cases': {'added': 0, 'updated': 0, 'skipped': 0},
        'questions': {'added': 0},
        'answers': {'added': 0},
        'images': {'added': 0},
        'revision_sessions': {'added': 0, 'skipped': 0},
        'case_flags': {'added': 0, 'skipped': 0},
        'highlights': {'added': 0},
        'notes': {'added': 0},
    }
    
    try:
        # Import Users
        print(f"[IMPORT] Importing users...")
        users_list = backup_data.get('users', [])
        user_id_map = {}
        
        for user_data in users_list:
            if not isinstance(user_data, dict):
                continue
            
            existing_user = session.query(User).filter_by(email=user_data.get('email')).first()
            
            if existing_user:
                if overwrite_existing:
                    # Update existing user
                    for key, value in user_data.items():
                        if key == 'role' and value:
                            try:
                                existing_user.role = UserRole(value)
                            except (ValueError, KeyError):
                                pass
                        elif key == 'subscription_status' and value:
                            try:
                                existing_user.subscription_status = SubscriptionStatus(value)
                            except (ValueError, KeyError):
                                pass
                        elif key == 'payment_status' and value:
                            try:
                                existing_user.payment_status = PaymentStatus(value)
                            except (ValueError, KeyError):
                                pass
                        elif key == 'created_at' and value:
                            try:
                                if isinstance(value, str):
                                    existing_user.created_at = datetime.fromisoformat(value)
                            except (ValueError, TypeError):
                                pass
                        elif key not in ['email', 'id', 'password_hash'] and hasattr(existing_user, key):
                            setattr(existing_user, key, value)
                    stats['users']['updated'] += 1
                else:
                    stats['users']['skipped'] += 1
                user_id_map[user_data.get('id')] = existing_user.id
            else:
                # Create new user
                try:
                    role_value = user_data.get('role', 'student')
                    user_role = UserRole(role_value) if role_value else UserRole.STUDENT
                except (ValueError, KeyError):
                    user_role = UserRole.STUDENT
                
                try:
                    sub_status_value = user_data.get('subscription_status', 'free')
                    subscription_status = SubscriptionStatus(sub_status_value) if sub_status_value else SubscriptionStatus.FREE
                except (ValueError, KeyError):
                    subscription_status = SubscriptionStatus.FREE
                
                try:
                    pay_status_value = user_data.get('payment_status', 'no_subscription')
                    payment_status = PaymentStatus(pay_status_value) if pay_status_value else PaymentStatus.NO_SUBSCRIPTION
                except (ValueError, KeyError):
                    payment_status = PaymentStatus.NO_SUBSCRIPTION
                
                user = User(
                    email=user_data.get('email'),
                    password_hash=user_data.get('password_hash', ''),
                    full_name=user_data.get('full_name', ''),
                    role=user_role,
                    subscription_status=subscription_status,
                    payment_status=payment_status,
                    is_active=user_data.get('is_active', True),
                )
                if user_data.get('created_at'):
                    try:
                        if isinstance(user_data['created_at'], str):
                            user.created_at = datetime.fromisoformat(user_data['created_at'])
                    except (ValueError, TypeError):
                        pass
                
                session.add(user)
                session.flush()
                stats['users']['added'] += 1
                user_id_map[user_data.get('id')] = user.id
        
        session.commit()
        print(f"[IMPORT] Users: {stats['users']['added']} added, {stats['users']['updated']} updated")
        
        # Import Cases with batch commits
        print(f"[IMPORT] Importing cases...")
        CASE_BATCH_SIZE = 50
        cases_list = backup_data.get('cases', [])
        case_id_map = {}
        
        for case_idx, case_data in enumerate(cases_list):
            case_number = case_data.get('case_number')
            existing_case = session.query(Case).filter_by(case_number=case_number).first() if case_number else None
            
            old_case_id = case_data.get('id')
            
            if existing_case:
                if overwrite_existing:
                    # Update existing case - only update scalar fields, not relationships
                    for key, value in case_data.items():
                        # Skip relationship fields and nested data
                        if key in ['questions', 'answers', 'images', 'id', 'case_number']:
                            continue
                        elif key in ['module', 'body_part', 'age_group'] and value:
                            try:
                                if key == 'module':
                                    existing_case.module = FRCRModule(value)
                                elif key == 'body_part':
                                    existing_case.body_part = BodyPart(value)
                                elif key == 'age_group':
                                    existing_case.age_group = AgeGroup(value)
                            except (ValueError, KeyError):
                                pass
                        elif hasattr(existing_case, key) and not hasattr(getattr(existing_case, key, None), '__iter__'):
                            # Only set scalar attributes, not relationships
                            try:
                                setattr(existing_case, key, value)
                            except Exception as e:
                                print(f"[IMPORT] Warning: Could not set {key}: {e}")
                    stats['cases']['updated'] += 1
                    new_case_id = existing_case.id
                else:
                    stats['cases']['skipped'] += 1
                    new_case_id = existing_case.id
            else:
                # Create new case
                case = Case(
                    case_number=case_data.get('case_number', ''),
                    diagnosis=case_data.get('diagnosis', ''),
                    discussion=case_data.get('discussion', ''),
                    is_public=case_data.get('is_public', True),
                )
                
                # Set enums
                if case_data.get('module'):
                    try:
                        case.module = FRCRModule(case_data['module'])
                    except (ValueError, KeyError):
                        pass
                if case_data.get('body_part'):
                    try:
                        case.body_part = BodyPart(case_data['body_part'])
                    except (ValueError, KeyError):
                        pass
                if case_data.get('age_group'):
                    try:
                        case.age_group = AgeGroup(case_data['age_group'])
                    except (ValueError, KeyError):
                        pass
                
                session.add(case)
                session.flush()
                stats['cases']['added'] += 1
                new_case_id = case.id
                
                # Add Questions
                for q_data in case_data.get('questions', []):
                    if isinstance(q_data, dict):
                        question = Question(
                            case_id=case.id,
                            question_number=q_data.get('question_number', 0),
                            question_text=q_data.get('question_text', ''),
                        )
                        session.add(question)
                        stats['questions']['added'] += 1
                
                # Add Answers
                for a_data in case_data.get('answers', []):
                    if isinstance(a_data, dict):
                        answer = Answer(
                            case_id=case.id,
                            answer_number=a_data.get('answer_number', 0),
                            answer_text=a_data.get('answer_text', ''),
                        )
                        session.add(answer)
                        stats['answers']['added'] += 1
                
                # Add Images
                import base64
                for img_data in case_data.get('images', []):
                    if isinstance(img_data, dict) and img_data.get('image_data'):
                        try:
                            image_data_binary = base64.b64decode(img_data['image_data'])
                            image = CaseImage(
                                case_id=case.id,
                                image_filename=img_data.get('image_filename') or img_data.get('filename', ''),
                                image_type=img_data.get('image_type', 'image/jpeg'),
                                image_description=img_data.get('image_description') or img_data.get('description', ''),
                                image_data=image_data_binary
                            )
                            session.add(image)
                            stats['images']['added'] += 1
                        except Exception as e:
                            print(f"[IMPORT] Warning: Failed to decode image: {e}")
            
            if old_case_id and new_case_id:
                case_id_map[old_case_id] = new_case_id
            
            # Batch commit
            if (case_idx + 1) % CASE_BATCH_SIZE == 0:
                session.commit()
                print(f"[IMPORT] Committed batch: {case_idx + 1}/{len(cases_list)} cases")
        
        session.commit()
        print(f"[IMPORT] Cases: {stats['cases']['added']} added, {stats['cases']['updated']} updated")
        
        # Import other data (highlights, notes, etc.)
        print(f"[IMPORT] Importing highlights, notes, flags...")
        BATCH_SIZE = 100
        
        # Highlights
        highlights_list = backup_data.get('highlights', [])
        for idx, highlight_data in enumerate(highlights_list):
            old_user_id = highlight_data.get('user_id')
            old_case_id = highlight_data.get('case_id')
            
            user_id = user_id_map.get(old_user_id)
            case_id = case_id_map.get(old_case_id)
            
            if user_id and case_id:
                highlight = TextHighlight(
                    user_id=user_id,
                    case_id=case_id,
                    text_content=highlight_data.get('text_content', ''),
                    highlight_color=highlight_data.get('highlight_color', 'yellow'),
                    field_name=highlight_data.get('field_name', 'discussion'),
                )
                session.add(highlight)
                stats['highlights']['added'] += 1
                
                if (idx + 1) % BATCH_SIZE == 0:
                    session.commit()
                    print(f"[IMPORT] Committed {idx + 1} highlights")
        
        # Notes
        notes_list = backup_data.get('notes', [])
        for idx, note_data in enumerate(notes_list):
            old_user_id = note_data.get('user_id')
            old_case_id = note_data.get('case_id')
            
            user_id = user_id_map.get(old_user_id)
            case_id = case_id_map.get(old_case_id)
            
            if user_id and case_id:
                note = CandidateNote(
                    user_id=user_id,
                    case_id=case_id,
                    note_text=note_data.get('note_text', ''),
                )
                session.add(note)
                stats['notes']['added'] += 1
                
                if (idx + 1) % BATCH_SIZE == 0:
                    session.commit()
                    print(f"[IMPORT] Committed {idx + 1} notes")
        
        session.commit()
        print(f"[IMPORT] Import complete!")
        
        return stats
        
    except Exception as e:
        session.rollback()
        print(f"[IMPORT] ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        session.close()

def main():
    parser = argparse.ArgumentParser(description='Import FRCR-Revision JSON backup to Supabase')
    parser.add_argument('backup_file', help='Path to JSON backup file')
    
    # Try to get password from multiple sources
    default_password = (
        os.getenv('POSTGRES_PASSWORD') or 
        os.getenv('DATABASE_PASSWORD') or
        None
    )
    
    parser.add_argument('--password', help='Supabase postgres password (or set POSTGRES_PASSWORD env var)', 
                       default=default_password)
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing records')
    
    args = parser.parse_args()
    
    # Check if password is provided
    if not args.password:
        print("Error: Supabase postgres password is required.")
        print("Provide it via --password flag or set POSTGRES_PASSWORD environment variable.")
        print("\nTo get your password:")
        print("1. Go to Supabase Dashboard: https://supabase.com/dashboard")
        print("2. Select your project")
        print("3. Go to Settings > Database")
        print("4. Find 'Connection string' or 'Database password'")
        print("\nOr set environment variable:")
        print("  export POSTGRES_PASSWORD='your_password'")
        sys.exit(1)
    
    if not os.path.exists(args.backup_file):
        print(f"Error: Backup file not found: {args.backup_file}")
        sys.exit(1)
    
    # Read backup
    backup_data = read_json_backup(args.backup_file)
    
    # Connect to Supabase
    connection_string = get_connection_string(args.password)
    print(f"[IMPORT] Connecting to Supabase...")
    engine = create_engine(connection_string, poolclass=None, pool_pre_ping=True, connect_args={'sslmode': 'require'})
    
    # Test connection
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print(f"[IMPORT] Connected to Supabase successfully")
    except Exception as e:
        print(f"[IMPORT] ERROR: Failed to connect to Supabase: {e}")
        print(f"[IMPORT] Connection string format: postgresql://postgres.qtucmbwxlssffvlqjhvh:PASSWORD@aws-1-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require")
        sys.exit(1)
    
    # Import data
    try:
        stats = import_to_supabase(backup_data, engine, args.overwrite)
        
        print("\n" + "="*50)
        print("IMPORT SUMMARY")
        print("="*50)
        for category, values in stats.items():
            if isinstance(values, dict):
                parts = []
                if values.get('added'): parts.append(f"Added: {values['added']}")
                if values.get('updated'): parts.append(f"Updated: {values['updated']}")
                if values.get('skipped'): parts.append(f"Skipped: {values['skipped']}")
                if parts:
                    print(f"{category.capitalize()}: {', '.join(parts)}")
            else:
                print(f"{category.capitalize()}: {values}")
        print("="*50)
        
    except Exception as e:
        print(f"\n[IMPORT] FAILED: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
