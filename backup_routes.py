"""
Database Backup and Restore Routes for Web Deployment
Handles manual backup downloads and restore from uploads
"""
from flask import Blueprint, jsonify, send_file, request, session
from flask_login import login_required, current_user
from models import (
    db, User, Case, CaseImage, Question, Answer,
    RevisionSession, RevisionHistory, CaseFlag, TextHighlight, CandidateNote,
    ImportedCaseStaging, UserRole, FRCRModule, BodyPart, AgeGroup
)
from datetime import datetime, timedelta
from sqlalchemy import inspect
import json
import io
import os
import uuid

backup_bp = Blueprint('backup', __name__, url_prefix='/api/backup')

def check_admin():
    """Check if current user is admin"""
    try:
        if not current_user.is_authenticated:
            return False
        # Check if user is admin or content manager
        return (hasattr(current_user, 'role') and 
                current_user.role in [UserRole.ADMIN, UserRole.CONTENT_MANAGER])
    except Exception as e:
        return False

def get_model_fields(model_class):
    """Get all column names for a model class"""
    return [column.name for column in inspect(model_class).columns]

@backup_bp.route('/download', methods=['GET'])
@login_required
def download_backup():
    """Download complete database backup as JSON"""
    if not check_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    try:
        # Collect all data
        backup_data = {
            'metadata': {
                'backup_date': datetime.utcnow().isoformat(),
                'database_type': 'postgresql' if os.getenv('DATABASE_URL') or os.getenv('DATABASE_POSTGRES_URL_NON_POOLING') else 'sqlite',
                'version': '2.0',
                'app_name': 'FRCR_REVISION'
            },
            'users': [],
            'cases': [],
            'case_images': [],
            'questions': [],
            'answers': [],
            'revision_sessions': [],
            'case_flags': [],
            'highlights': [],
            'notes': []
        }
        
        # Export users (with passwords for sync purposes)
        for user in User.query.filter_by(is_deleted=False).all():
            user_data = {
                'id': user.id,  # Include ID for proper mapping
                'email': user.email,
                'password_hash': user.password_hash,
                'full_name': user.full_name,
                'role': user.role.value if user.role else 'student',
                'is_active': user.is_active,
                'subscription_status': user.subscription_status.value if user.subscription_status else 'free',
                'payment_status': user.payment_status.value if user.payment_status else 'no_subscription',
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'last_login': user.last_login.isoformat() if user.last_login else None,
            }
            backup_data['users'].append(user_data)
        
        # Export cases
        for case in Case.query.all():
            case_data = {
                'id': case.id,  # Include ID for proper mapping
                'case_number': case.case_number,
                'diagnosis': case.diagnosis,
                'discussion': case.discussion or '',
                'module': case.module.value if case.module else None,
                'body_part': case.body_part.value if case.body_part else None,
                'age_group': case.age_group.value if case.age_group else None,
                'is_public': case.is_public,
                'created_at': case.created_at.isoformat() if case.created_at else None,
                'created_by_user_id': case.created_by_user_id,
            }
            
            # Export Questions for this case
            questions = Question.query.filter_by(case_id=case.id).order_by(Question.question_number).all()
            case_data['questions'] = [{
                'question_number': q.question_number,
                'question_text': q.question_text,
            } for q in questions]
            
            # Export Answers for this case
            answers = Answer.query.filter_by(case_id=case.id).order_by(Answer.answer_number).all()
            case_data['answers'] = [{
                'answer_number': a.answer_number,
                'answer_text': a.answer_text,
            } for a in answers]
            
            # Export Images for this case
            images = CaseImage.query.filter_by(case_id=case.id).all()
            import base64
            case_data['images'] = [{
                'filename': img.image_filename or '',
                'image_type': img.image_type or '',
                'description': img.image_description or '',
                'image_data': base64.b64encode(img.image_data).decode('utf-8') if img.image_data else None,
            } for img in images]
            
            backup_data['cases'].append(case_data)
        
        # Export revision sessions
        for rev_session in RevisionSession.query.all():
            backup_data['revision_sessions'].append({
                'user_id': rev_session.user_id,
                'case_ids': rev_session.get_case_ids_list() if hasattr(rev_session, 'get_case_ids_list') else json.loads(rev_session.case_ids or '[]'),
                'current_case_index': rev_session.current_case_index,
                'created_at': rev_session.created_at.isoformat() if rev_session.created_at else None,
            })
        
        # Export case flags
        for flag in CaseFlag.query.all():
            backup_data['case_flags'].append({
                'user_id': flag.user_id,
                'case_id': flag.case_id,
                'created_at': flag.created_at.isoformat() if flag.created_at else None,
            })
        
        # Export highlights
        for highlight in TextHighlight.query.all():
            backup_data['highlights'].append({
                'user_id': highlight.user_id,
                'case_id': highlight.case_id,
                'text_content': highlight.text_content or '',
                'highlight_color': highlight.highlight_color or 'yellow',
                'field_name': highlight.field_name or 'discussion',
                'created_at': highlight.created_at.isoformat() if highlight.created_at else None,
            })
        
        # Export notes
        for note in CandidateNote.query.all():
            backup_data['notes'].append({
                'user_id': note.user_id,
                'case_id': note.case_id,
                'note_text': note.note_text or '',
                'created_at': note.created_at.isoformat() if note.created_at else None,
            })
        
        # Create JSON file in memory
        json_data = json.dumps(backup_data, indent=2)
        json_bytes = io.BytesIO(json_data.encode('utf-8'))
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'frcr_revision_backup_{timestamp}.json'
        
        # Update session with last backup time
        session['last_backup_time'] = datetime.utcnow().isoformat()
        
        return send_file(
            json_bytes,
            mimetype='application/json',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'error': f'Backup failed: {str(e)}'}), 500


@backup_bp.route('/restore', methods=['POST'])
@login_required
def restore_backup():
    """Restore database from uploaded JSON backup with smart merge"""
    if not check_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    if 'backup_file' not in request.files:
        return jsonify({'error': 'No backup file provided'}), 400
    
    file = request.files['backup_file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.json'):
        return jsonify({'error': 'Only JSON backup files are supported'}), 400
    
    try:
        # Read and parse JSON
        file_content = file.read().decode('utf-8')
        
        # Handle case where file might already be a string (double-encoded)
        if isinstance(file_content, str):
            try:
                backup_data = json.loads(file_content)
            except json.JSONDecodeError:
                # If it's already a dict (shouldn't happen but handle it)
                backup_data = file_content if isinstance(file_content, dict) else json.loads(file_content)
        else:
            backup_data = file_content
        
        # Ensure backup_data is a dictionary
        if not isinstance(backup_data, dict):
            return jsonify({'error': f'Invalid backup file format: expected dict, got {type(backup_data).__name__}'}), 400
        
        # Validate backup structure
        if 'metadata' not in backup_data:
            return jsonify({'error': 'Invalid backup file format: missing metadata'}), 400
        
        # Detect source system (FRCR Examiner vs FRCR Revision)
        metadata = backup_data.get('metadata', {})
        app_name = metadata.get('app_name', '').upper()
        is_frcr_examiner = 'EXAMINER' in app_name or metadata.get('source_system') == 'frcr_examiner'
        is_frcr_revision = 'REVISION' in app_name or metadata.get('app_name') == 'FRCR_REVISION'
        
        # Default to FRCR Examiner if cannot determine (for backward compatibility)
        if not is_frcr_examiner and not is_frcr_revision:
            # Check if backup has FRCR Examiner structure (separate case_images array)
            if 'case_images' in backup_data and isinstance(backup_data.get('case_images'), list):
                is_frcr_examiner = True
            else:
                is_frcr_revision = True
        
        print(f"[IMPORT] Detected backup source: {'FRCR_EXAMINER' if is_frcr_examiner else 'FRCR_REVISION'}")
        
        # Check if user confirmed overwrite for existing data
        # Support both form data and JSON data
        if request.is_json:
            json_data = request.get_json() or {}
            overwrite_existing = json_data.get('overwrite_existing') == True or json_data.get('overwrite_existing') == 'true'
            confirm_overwrite = json_data.get('confirm_overwrite') == True or json_data.get('confirm_overwrite') == 'true'
        else:
            overwrite_existing = request.form.get('overwrite_existing') == 'true'
            confirm_overwrite = request.form.get('confirm_overwrite') == 'true'
        
        if not confirm_overwrite:
            return jsonify({'error': 'Please confirm data import'}), 400
        
        stats = {
            'users': {'added': 0, 'updated': 0, 'skipped': 0},
            'cases': {'added': 0, 'updated': 0, 'skipped': 0},
            'staging': {'added': 0, 'images_stored': 0},  # Cases sent to staging for review, and images stored in them
            'questions': {'added': 0},
            'answers': {'added': 0},
            'images': {'added': 0},
            'revision_sessions': {'added': 0, 'skipped': 0},
            'case_flags': {'added': 0, 'skipped': 0},
            'highlights': {'added': 0},
            'notes': {'added': 0},
        }
        
        # Generate import batch ID for staging cases
        import_batch_id = f"backup_import_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        
        # Get valid field names for each model
        valid_user_fields = get_model_fields(User)
        valid_case_fields = get_model_fields(Case)
        
        # Import Users
        # For FRCR Examiner: Skip user import, all cases will be mapped to current_user
        # For FRCR Revision: Import users normally
        user_id_map = {}  # Map old user IDs from backup to new user IDs
        
        if is_frcr_examiner:
            # FRCR Examiner: Don't import users, map everything to current_user
            print(f"[IMPORT] FRCR Examiner backup: Skipping user import, mapping all cases to current user {current_user.id}")
            # Create a dummy mapping for any user references (they'll be replaced with current_user.id)
            users_list = backup_data.get('users', [])
            if isinstance(users_list, list):
                for user_data in users_list:
                    old_id = user_data.get('id') if isinstance(user_data, dict) else None
                    if old_id:
                        user_id_map[old_id] = current_user.id
        else:
            # FRCR Revision: Import users normally
            users_list = backup_data.get('users', [])
            if not isinstance(users_list, list):
                return jsonify({'error': 'Invalid backup format: users must be a list'}), 400
            
            for user_data in users_list:
                # Ensure user_data is a dictionary
                if not isinstance(user_data, dict):
                    print(f"[IMPORT] Warning: Skipping invalid user data (not a dict): {type(user_data).__name__}")
                    continue
                
                # Filter out unknown fields
                filtered_data = {k: v for k, v in user_data.items() if k in valid_user_fields or k in ['email', 'password_hash', 'full_name', 'role', 'is_active', 'subscription_status', 'payment_status']}
                
                existing_user = User.query.filter_by(email=user_data.get('email')).first()
                
                if existing_user:
                    if overwrite_existing:
                        # Update existing user
                        for key, value in filtered_data.items():
                            if key == 'role' and value:
                                try:
                                    existing_user.role = UserRole(value)
                                except (ValueError, KeyError) as e:
                                    print(f"[IMPORT] Warning: Could not set user role to {value}: {e}")
                                    pass
                            elif key == 'subscription_status' and value:
                                from models import SubscriptionStatus
                                try:
                                    existing_user.subscription_status = SubscriptionStatus(value)
                                except (ValueError, KeyError) as e:
                                    print(f"[IMPORT] Warning: Could not set subscription_status to {value}: {e}")
                                    pass
                            elif key == 'payment_status' and value:
                                from models import PaymentStatus
                                try:
                                    existing_user.payment_status = PaymentStatus(value)
                                except (ValueError, KeyError) as e:
                                    print(f"[IMPORT] Warning: Could not set payment_status to {value}: {e}")
                                    pass
                            elif key in ['created_at', 'last_login'] and value:
                                # Convert ISO string to datetime object for SQLite compatibility
                                try:
                                    if isinstance(value, str):
                                        existing_user.__setattr__(key, datetime.fromisoformat(value))
                                    elif isinstance(value, datetime):
                                        existing_user.__setattr__(key, value)
                                except (ValueError, TypeError) as e:
                                    print(f"[IMPORT] Warning: Could not parse {key} datetime: {value}, error: {e}")
                                    pass
                            elif key not in ['email', 'id'] and hasattr(existing_user, key):
                                setattr(existing_user, key, value)
                        stats['users']['updated'] += 1
                    else:
                        stats['users']['skipped'] += 1
                else:
                    # Create new user
                    try:
                        role_value = filtered_data.get('role', 'student')
                        user_role = UserRole(role_value) if role_value else UserRole.STUDENT
                    except (ValueError, KeyError) as e:
                        print(f"[IMPORT] Warning: Could not set user role to {filtered_data.get('role')}, defaulting to student: {e}")
                        user_role = UserRole.STUDENT
                    
                    user = User(
                        email=filtered_data.get('email'),
                        password_hash=filtered_data.get('password_hash', ''),
                        full_name=filtered_data.get('full_name', ''),
                        role=user_role,
                        is_active=filtered_data.get('is_active', True),
                    )
                    if filtered_data.get('subscription_status'):
                        from models import SubscriptionStatus
                        try:
                            user.subscription_status = SubscriptionStatus(filtered_data['subscription_status'])
                        except (ValueError, KeyError) as e:
                            print(f"[IMPORT] Warning: Could not set subscription_status to {filtered_data.get('subscription_status')}: {e}")
                    if filtered_data.get('payment_status'):
                        from models import PaymentStatus
                        try:
                            user.payment_status = PaymentStatus(filtered_data['payment_status'])
                        except (ValueError, KeyError) as e:
                            print(f"[IMPORT] Warning: Could not set payment_status to {filtered_data.get('payment_status')}: {e}")
                    if filtered_data.get('created_at'):
                        try:
                            if isinstance(filtered_data['created_at'], str):
                                user.created_at = datetime.fromisoformat(filtered_data['created_at'])
                            elif isinstance(filtered_data['created_at'], datetime):
                                user.created_at = filtered_data['created_at']
                        except (ValueError, TypeError) as e:
                            print(f"[IMPORT] Warning: Could not parse user created_at datetime: {filtered_data.get('created_at')}, error: {e}")
                    db.session.add(user)
                    stats['users']['added'] += 1
            
            try:
                db.session.commit()
            except Exception as commit_error:
                db.session.rollback()
                print(f"[IMPORT] ERROR during user commit: {commit_error}")
                import traceback
                traceback.print_exc()
                raise
            
            # Build user email to ID mapping and old ID to new ID mapping
            user_email_map = {u.email: u.id for u in User.query.all()}
            
            # Build ID mapping for users (old backup ID -> new database ID)
            for user_data in backup_data.get('users', []):
                if not isinstance(user_data, dict):
                    continue
                old_id = user_data.get('id')
                email = user_data.get('email')
                if old_id and email:
                    new_user = User.query.filter_by(email=email).first()
                    if new_user:
                        user_id_map[old_id] = new_user.id
        
        # Import Cases
        case_id_map = {}  # Map old case IDs from backup to new case IDs (production cases only)
        staging_id_map = {}  # Map old case IDs from backup to staging IDs (staging cases only)
        
        for case_data in backup_data.get('cases', []):
            # Filter out unknown fields - only keep fields that exist in Case model
            valid_case_keys = ['case_number', 'diagnosis', 'discussion', 'module', 'body_part', 'age_group', 'is_public', 'created_by_user_id', 'created_at']
            filtered_data = {k: v for k, v in case_data.items() if k in valid_case_keys}
            
            old_case_id = case_data.get('id')  # Store old ID for mapping
            
            # Find existing case by case_number (or create new)
            case_number = filtered_data.get('case_number')
            existing_case = Case.query.filter_by(case_number=case_number).first() if case_number else None
            
            if existing_case:
                if overwrite_existing:
                    # Update existing case
                    for key, value in filtered_data.items():
                        if key in ['module', 'body_part', 'age_group'] and value:
                            from models import FRCRModule, BodyPart, AgeGroup
                            try:
                                # Convert to string and strip whitespace
                                enum_value_str = str(value).strip() if value is not None else None
                                if not enum_value_str:
                                    continue
                                    
                                if key == 'module':
                                    # Try by value first (export format), then by name
                                    try:
                                        existing_case.module = FRCRModule(enum_value_str)
                                    except (ValueError, KeyError):
                                        try:
                                            existing_case.module = FRCRModule[enum_value_str]
                                        except (ValueError, KeyError) as e:
                                            print(f"[IMPORT] Warning: Could not set module to '{enum_value_str}' (type: {type(value).__name__}): {e}")
                                elif key == 'body_part':
                                    try:
                                        existing_case.body_part = BodyPart(enum_value_str)
                                    except (ValueError, KeyError):
                                        try:
                                            existing_case.body_part = BodyPart[enum_value_str]
                                        except (ValueError, KeyError) as e:
                                            print(f"[IMPORT] Warning: Could not set body_part to '{enum_value_str}' (type: {type(value).__name__}): {e}")
                                elif key == 'age_group':
                                    try:
                                        existing_case.age_group = AgeGroup(enum_value_str)
                                    except (ValueError, KeyError):
                                        try:
                                            existing_case.age_group = AgeGroup[enum_value_str]
                                        except (ValueError, KeyError) as e:
                                            print(f"[IMPORT] Warning: Could not set age_group to '{enum_value_str}' (type: {type(value).__name__}): {e}")
                            except Exception as e:
                                print(f"[IMPORT] Warning: Could not set {key} to {value} (type: {type(value).__name__}): {e}")
                                pass
                        elif key == 'created_at' and value:
                            # Convert ISO string to datetime object for SQLite compatibility
                            try:
                                if isinstance(value, str):
                                    existing_case.created_at = datetime.fromisoformat(value)
                                elif isinstance(value, datetime):
                                    existing_case.created_at = value
                            except (ValueError, TypeError) as e:
                                print(f"[IMPORT] Warning: Could not parse case created_at datetime: {value}, error: {e}")
                                pass
                        elif key not in ['id', 'case_number'] and hasattr(existing_case, key):
                            setattr(existing_case, key, value)
                    
                    # Update Q&A if overwriting
                    if overwrite_existing:
                        # Delete existing Q&A
                        Question.query.filter_by(case_id=existing_case.id).delete()
                        Answer.query.filter_by(case_id=existing_case.id).delete()
                        # Add new Q&A
                        questions_list = case_data.get('questions', [])
                        if isinstance(questions_list, list):
                            for q_data in questions_list:
                                if not isinstance(q_data, dict):
                                    print(f"[IMPORT] Warning: Skipping invalid question data (not a dict)")
                                    continue
                                question = Question(
                                    case_id=existing_case.id,
                                    question_number=q_data.get('question_number', 0),
                                    question_text=q_data.get('question_text', ''),
                            )
                            db.session.add(question)
                            stats['questions']['added'] += 1
                        
                        answers_list = case_data.get('answers', [])
                        if isinstance(answers_list, list):
                            for a_data in answers_list:
                                if not isinstance(a_data, dict):
                                    print(f"[IMPORT] Warning: Skipping invalid answer data (not a dict)")
                                    continue
                                answer = Answer(
                                    case_id=existing_case.id,
                                    answer_number=a_data.get('answer_number', 0),
                                    answer_text=a_data.get('answer_text', ''),
                                )
                                db.session.add(answer)
                                stats['answers']['added'] += 1
                        
                        # Update images if overwriting
                        CaseImage.query.filter_by(case_id=existing_case.id).delete()
                        import base64
                        images_list = case_data.get('images', [])
                        if isinstance(images_list, list):
                            for img_data in images_list:
                                if not isinstance(img_data, dict):
                                    print(f"[IMPORT] Warning: Skipping invalid image data (not a dict)")
                                    continue
                                image_data_binary = None
                                if img_data.get('image_data'):
                                    try:
                                        image_data_binary = base64.b64decode(img_data['image_data'])
                                    except Exception as e:
                                        print(f"[IMPORT] Warning: Failed to decode image data: {e}")
                                        continue
                                
                                # Only create image if we have image data
                                if image_data_binary:
                                    # Support both field name formats: 'image_filename'/'image_description' (FRCR Examiner) and 'filename'/'description' (FRCR Revision)
                                    image_filename = img_data.get('image_filename') or img_data.get('filename', '')
                                    image_description = img_data.get('image_description') or img_data.get('description', '')
                                    image_type = img_data.get('image_type', 'image/jpeg')
                                    
                                    image = CaseImage(
                                        case_id=existing_case.id,
                                        image_filename=image_filename,
                                        image_type=image_type,
                                        image_description=image_description,
                                        image_data=image_data_binary
                                    )
                                    db.session.add(image)
                                    stats['images']['added'] += 1
                    
                    stats['cases']['updated'] += 1
                    new_case_id = existing_case.id
                else:
                    stats['cases']['skipped'] += 1
                    new_case_id = existing_case.id
            else:
                # Check for missing critical fields
                missing_fields = []
                if not filtered_data.get('module'):
                    missing_fields.append('module')
                if not filtered_data.get('body_part'):
                    missing_fields.append('body_part')
                if not filtered_data.get('age_group'):
                    missing_fields.append('age_group')
                
                # If missing critical fields, send to staging for review
                if missing_fields:
                    # Create staging entry for admin review
                    import base64
                    import json as json_lib
                    
                    # Store Q&A as JSON for staging (legacy format for compatibility)
                    questions_list = case_data.get('questions', [])
                    if not isinstance(questions_list, list):
                        questions_list = []
                    questions_json = json_lib.dumps([{
                        'question_number': q.get('question_number', 0) if isinstance(q, dict) else 0,
                        'question_text': q.get('question_text', '') if isinstance(q, dict) else str(q)
                    } for q in questions_list if isinstance(q, dict)])
                    
                    answers_list = case_data.get('answers', [])
                    if not isinstance(answers_list, list):
                        answers_list = []
                    answers_json = json_lib.dumps([{
                        'answer_number': a.get('answer_number', 0) if isinstance(a, dict) else 0,
                        'answer_text': a.get('answer_text', '') if isinstance(a, dict) else str(a)
                    } for a in answers_list if isinstance(a, dict)])
                    
                    # For FRCR Examiner: Store source system as 'frcr_examiner' to track origin
                    source_system = 'frcr_examiner' if is_frcr_examiner else 'backup_import'
                    
                    staging = ImportedCaseStaging(
                        original_id=old_case_id,
                        case_number=filtered_data.get('case_number'),
                        diagnosis=filtered_data.get('diagnosis', ''),
                        discussion=filtered_data.get('discussion', ''),
                        questions=questions_json,  # Legacy format for staging
                        answers=answers_json,  # Legacy format for staging
                        enrichment_status='pending',
                        import_batch_id=import_batch_id,
                        source_system=source_system,
                        enrichment_notes=f"Missing fields: {', '.join(missing_fields)}. Requires admin review.",
                    )
                    db.session.add(staging)
                    try:
                        db.session.flush()
                    except Exception as flush_error:
                        db.session.rollback()
                        print(f"[IMPORT] ERROR during staging flush: {flush_error}")
                        import traceback
                        traceback.print_exc()
                        raise
                    
                    # Store images temporarily in enrichment_notes (will be migrated on promotion)
                    # Process images from separate case_images array for this staging case
                    import base64
                    import json as json_lib
                    staging_images = []
                    case_number_for_match = filtered_data.get('case_number')
                    
                    # Normalize case_number for comparison (convert to string)
                    case_number_str = str(case_number_for_match) if case_number_for_match is not None else None
                    
                    print(f"[IMPORT] Looking for images for staging case: old_case_id={old_case_id} (type: {type(old_case_id).__name__}), case_number={case_number_for_match} (type: {type(case_number_for_match).__name__})")
                    print(f"[IMPORT] Total images in backup: {len(backup_data.get('case_images', []))}")
                    
                    for img_data in backup_data.get('case_images', []):
                        if not isinstance(img_data, dict):
                            continue
                        
                        # Try to match by case_id first, then by case_number if available
                        img_case_id = img_data.get('case_id')
                        img_case_number = img_data.get('case_number')
                        
                        # Normalize types for comparison
                        # Convert both to same type (prefer int for IDs, string for case_numbers)
                        img_case_id_normalized = int(img_case_id) if img_case_id is not None and str(img_case_id).isdigit() else img_case_id
                        old_case_id_normalized = int(old_case_id) if old_case_id is not None and str(old_case_id).isdigit() else old_case_id
                        
                        img_case_number_str = str(img_case_number) if img_case_number is not None else None
                        
                        # Match if case_id matches OR case_number matches
                        matches = False
                        if old_case_id_normalized is not None and img_case_id_normalized is not None:
                            if img_case_id_normalized == old_case_id_normalized:
                                matches = True
                                print(f"[IMPORT] ✓ Matched image by case_id: {old_case_id_normalized}")
                        elif case_number_str and img_case_number_str:
                            # Try exact match first
                            if img_case_number_str == case_number_str:
                                matches = True
                                print(f"[IMPORT] ✓ Matched image by case_number (exact): {case_number_str}")
                            # Try numeric comparison if both are numeric
                            elif case_number_str.isdigit() and img_case_number_str.isdigit():
                                if int(case_number_str) == int(img_case_number_str):
                                    matches = True
                                    print(f"[IMPORT] ✓ Matched image by case_number (numeric): {case_number_str}")
                        
                        if matches:
                            # This image belongs to this staging case
                            try:
                                image_filename = img_data.get('image_filename') or img_data.get('filename', '')
                                image_description = img_data.get('image_description') or img_data.get('description', '')
                                image_type = img_data.get('image_type', 'image/jpeg')
                                image_data_base64 = img_data.get('image_data')
                                
                                if image_data_base64:
                                    staging_images.append({
                                        'filename': image_filename,
                                        'image_type': image_type,
                                        'description': image_description,
                                        'image_data': image_data_base64  # Keep as base64 string
                                    })
                                    print(f"[IMPORT] Added image to staging: {image_filename} (data length: {len(image_data_base64)})")
                                else:
                                    print(f"[IMPORT] Warning: Image {image_filename} has no image_data")
                            except Exception as img_err:
                                print(f"[IMPORT] Warning: Failed to process image for staging case {old_case_id}: {img_err}")
                                import traceback
                                traceback.print_exc()
                    
                    if not staging_images:
                        print(f"[IMPORT] ⚠️ Warning: No images found for staging case (old_case_id={old_case_id}, case_number={case_number_for_match})")
                        print(f"[IMPORT] Total images in backup: {len(backup_data.get('case_images', []))}")
                        # Debug: show first few image case_ids and case_numbers
                        sample_data = []
                        for img in backup_data.get('case_images', [])[:10]:
                            if isinstance(img, dict):
                                sample_data.append({
                                    'case_id': img.get('case_id'),
                                    'case_number': img.get('case_number'),
                                    'filename': img.get('image_filename') or img.get('filename', 'N/A')
                                })
                        print(f"[IMPORT] Sample image data (first 10): {sample_data}")
                        # Also check if any images have matching case_number
                        matching_by_number = [img for img in backup_data.get('case_images', []) 
                                            if isinstance(img, dict) and 
                                            str(img.get('case_number', '')) == case_number_str]
                        if matching_by_number:
                            print(f"[IMPORT] Found {len(matching_by_number)} images with matching case_number but didn't match - check logic")
                    
                    # Store images JSON in enrichment_notes with special marker
                    if staging_images:
                        images_json_str = json_lib.dumps(staging_images)
                        if staging.enrichment_notes:
                            staging.enrichment_notes = f"[IMAGES_JSON]{images_json_str}[/IMAGES_JSON]\n{staging.enrichment_notes}"
                        else:
                            staging.enrichment_notes = f"[IMAGES_JSON]{images_json_str}[/IMAGES_JSON]"
                        
                        # Explicitly mark the object as modified to ensure SQLAlchemy tracks the change
                        from sqlalchemy.orm.attributes import flag_modified
                        flag_modified(staging, 'enrichment_notes')
                        
                        print(f"[IMPORT] ✓ Stored {len(staging_images)} images in staging case {staging.id} enrichment_notes")
                        print(f"[IMPORT] Enrichment notes length: {len(staging.enrichment_notes)}")
                        print(f"[IMPORT] Enrichment notes preview: {staging.enrichment_notes[:200]}...")
                        stats['staging']['images_stored'] += len(staging_images)
                    else:
                        print(f"[IMPORT] ⚠️ No images to store for staging case {staging.id}")
                    
                    stats['staging']['added'] += 1
                    # Store staging ID mapping (for image processing)
                    if old_case_id:
                        staging_id_map[old_case_id] = staging.id
                    # Don't create case_id_map entry for staging cases (they're not in production yet)
                    continue
                
                # All critical fields present - create case directly
                case = Case(
                    case_number=filtered_data.get('case_number', ''),
                    diagnosis=filtered_data.get('diagnosis', ''),
                    discussion=filtered_data.get('discussion', ''),
                    is_public=filtered_data.get('is_public', True),
                )
                
                # Set enums - try by value first (export format), then by name
                # Validate and convert to string first to avoid pattern matching errors
                if filtered_data.get('module'):
                    module_value = filtered_data['module']
                    if module_value is not None:
                        try:
                            # Convert to string and strip whitespace
                            module_str = str(module_value).strip()
                            if module_str:
                                try:
                                    case.module = FRCRModule(module_str)
                                except (ValueError, KeyError):
                                    try:
                                        case.module = FRCRModule[module_str]
                                    except (ValueError, KeyError) as e:
                                        print(f"[IMPORT] Warning: Could not set module to '{module_str}' (type: {type(module_value).__name__}): {e}")
                                except Exception as e:
                                    print(f"[IMPORT] Warning: Unexpected error setting module to '{module_str}': {e}")
                        except Exception as e:
                            print(f"[IMPORT] Warning: Could not process module value {module_value}: {e}")
                if filtered_data.get('body_part'):
                    body_part_value = filtered_data['body_part']
                    if body_part_value is not None:
                        try:
                            body_part_str = str(body_part_value).strip()
                            if body_part_str:
                                try:
                                    case.body_part = BodyPart(body_part_str)
                                except (ValueError, KeyError):
                                    try:
                                        case.body_part = BodyPart[body_part_str]
                                    except (ValueError, KeyError) as e:
                                        print(f"[IMPORT] Warning: Could not set body_part to '{body_part_str}' (type: {type(body_part_value).__name__}): {e}")
                                except Exception as e:
                                    print(f"[IMPORT] Warning: Unexpected error setting body_part to '{body_part_str}': {e}")
                        except Exception as e:
                            print(f"[IMPORT] Warning: Could not process body_part value {body_part_value}: {e}")
                if filtered_data.get('age_group'):
                    age_group_value = filtered_data['age_group']
                    if age_group_value is not None:
                        try:
                            age_group_str = str(age_group_value).strip()
                            if age_group_str:
                                try:
                                    case.age_group = AgeGroup(age_group_str)
                                except (ValueError, KeyError):
                                    try:
                                        case.age_group = AgeGroup[age_group_str]
                                    except (ValueError, KeyError) as e:
                                        print(f"[IMPORT] Warning: Could not set age_group to '{age_group_str}' (type: {type(age_group_value).__name__}): {e}")
                                except Exception as e:
                                    print(f"[IMPORT] Warning: Unexpected error setting age_group to '{age_group_str}': {e}")
                        except Exception as e:
                            print(f"[IMPORT] Warning: Could not process age_group value {age_group_value}: {e}")
                
                # Map created_by_user_id from backup using ID mapping
                # For FRCR Examiner: Always use current_user.id
                # For FRCR Revision: Use user_id_map to preserve original ownership
                if is_frcr_examiner:
                    case.created_by_user_id = current_user.id
                else:
                    if filtered_data.get('created_by_user_id'):
                        old_user_id = filtered_data.get('created_by_user_id')
                        case.created_by_user_id = user_id_map.get(old_user_id, current_user.id)
                if filtered_data.get('created_at'):
                    try:
                        if isinstance(filtered_data['created_at'], str):
                            case.created_at = datetime.fromisoformat(filtered_data['created_at'])
                        elif isinstance(filtered_data['created_at'], datetime):
                            case.created_at = filtered_data['created_at']
                    except (ValueError, TypeError) as e:
                        print(f"[IMPORT] Warning: Could not parse case created_at datetime: {filtered_data.get('created_at')}, error: {e}")
                
                db.session.add(case)
                try:
                    db.session.flush()
                except Exception as flush_error:
                    db.session.rollback()
                    print(f"[IMPORT] ERROR during case flush: {flush_error}")
                    print(f"[IMPORT] Case data that failed: case_number={filtered_data.get('case_number')}, module={filtered_data.get('module')}, body_part={filtered_data.get('body_part')}, age_group={filtered_data.get('age_group')}")
                    import traceback
                    traceback.print_exc()
                    raise
        
                # Add Q&A
                questions_list = case_data.get('questions', [])
                if isinstance(questions_list, list):
                    for q_data in questions_list:
                        if not isinstance(q_data, dict):
                            print(f"[IMPORT] Warning: Skipping invalid question data (not a dict)")
                            continue
                        question = Question(
                            case_id=case.id,
                            question_number=q_data.get('question_number', 0),
                            question_text=q_data.get('question_text', ''),
                        )
                        db.session.add(question)
                        stats['questions']['added'] += 1
                
                # Add answers
                answers_list = case_data.get('answers', [])
                if isinstance(answers_list, list):
                    for a_data in answers_list:
                        if not isinstance(a_data, dict):
                            print(f"[IMPORT] Warning: Skipping invalid answer data (not a dict)")
                            continue
                        answer = Answer(
                            case_id=case.id,
                            answer_number=a_data.get('answer_number', 0),
                            answer_text=a_data.get('answer_text', ''),
                        )
                        db.session.add(answer)
                        stats['answers']['added'] += 1
                
                # Add images
                import base64
                images_list = case_data.get('images', [])
                if isinstance(images_list, list):
                    for img_data in images_list:
                        if not isinstance(img_data, dict):
                            print(f"[IMPORT] Warning: Skipping invalid image data (not a dict)")
                            continue
                        image_data_binary = None
                        if img_data.get('image_data'):
                            try:
                                image_data_binary = base64.b64decode(img_data['image_data'])
                            except Exception as e:
                                print(f"[IMPORT] Warning: Failed to decode image data: {e}")
                                continue
                        
                        # Only create image if we have image data
                        if image_data_binary:
                            # Support both field name formats: 'image_filename'/'image_description' (FRCR Examiner) and 'filename'/'description' (FRCR Revision)
                            image_filename = img_data.get('image_filename') or img_data.get('filename', '')
                            image_description = img_data.get('image_description') or img_data.get('description', '')
                            image_type = img_data.get('image_type', 'image/jpeg')
                            
                            image = CaseImage(
                                case_id=case.id,
                                image_filename=image_filename,
                                image_type=image_type,
                                image_description=image_description,
                                image_data=image_data_binary
                            )
                            db.session.add(image)
                            stats['images']['added'] += 1
                
                stats['cases']['added'] += 1
                new_case_id = case.id
            
            # Store case ID mapping (for both new and existing cases)
            if old_case_id and new_case_id:
                case_id_map[old_case_id] = new_case_id
        
        try:
            db.session.commit()
        except Exception as commit_error:
            db.session.rollback()
            print(f"[IMPORT] ERROR during case commit: {commit_error}")
            print(f"[IMPORT] Case data that failed: case_number={filtered_data.get('case_number')}, module={filtered_data.get('module')}, body_part={filtered_data.get('body_part')}, age_group={filtered_data.get('age_group')}")
            import traceback
            traceback.print_exc()
            raise
        
        # Import images from separate case_images array (FRCR Examiner format)
        # This handles backups where images are stored separately, not in case['images']
        # Note: Images for staging cases are already stored in enrichment_notes during case import
        # This section only processes images for cases that went directly to production
        case_images_list = backup_data.get('case_images', [])
        if isinstance(case_images_list, list) and len(case_images_list) > 0:
            import base64
            print(f"[IMPORT] Found {len(case_images_list)} images in separate case_images array")
            print(f"[IMPORT] Case ID map contains {len(case_id_map)} mappings: {case_id_map}")
            print(f"[IMPORT] Staging ID map contains {len(staging_id_map)} mappings: {staging_id_map}")
            for img_data in case_images_list:
                if not isinstance(img_data, dict):
                    print(f"[IMPORT] Warning: Skipping invalid image data (not a dict)")
                    continue
                
                # Map old case_id to new case_id
                old_case_id = img_data.get('case_id')
                if not old_case_id:
                    print(f"[IMPORT] Warning: Skipping image without case_id")
                    continue
                
                # Check if this is a staging case (images already stored in enrichment_notes)
                if old_case_id in staging_id_map:
                    print(f"[IMPORT] Skipping image for case_id {old_case_id} (already stored in staging case {staging_id_map[old_case_id]} enrichment_notes)")
                    continue
                
                new_case_id = case_id_map.get(old_case_id)
                if not new_case_id:
                    print(f"[IMPORT] Warning: Skipping image for case_id {old_case_id} (case not imported or not in case_id_map)")
                    print(f"[IMPORT] Available case IDs in map: {list(case_id_map.keys())}")
                    continue
                
                # Check if image already exists (if overwriting)
                if overwrite_existing:
                    CaseImage.query.filter_by(case_id=new_case_id, image_filename=img_data.get('image_filename') or img_data.get('filename', '')).delete()
                
                # Handle field name mapping: FRCR Examiner uses 'image_filename' and 'image_description'
                # Support both formats: 'image_filename'/'image_description' (FRCR Examiner) and 'filename'/'description' (FRCR Revision)
                image_filename = img_data.get('image_filename') or img_data.get('filename', '')
                image_description = img_data.get('image_description') or img_data.get('description', '')
                image_type = img_data.get('image_type', 'image/jpeg')
                
                # Decode image data
                image_data_binary = None
                if img_data.get('image_data'):
                    try:
                        image_data_binary = base64.b64decode(img_data['image_data'])
                    except Exception as e:
                        print(f"[IMPORT] Warning: Failed to decode image data for {image_filename}: {e}")
                        continue
                
                # Only create image if we have image data
                if image_data_binary:
                    image = CaseImage(
                        case_id=new_case_id,
                        image_filename=image_filename,
                        image_type=image_type,
                        image_description=image_description,
                        image_data=image_data_binary
                    )
                    db.session.add(image)
                    stats['images']['added'] += 1
                    print(f"[IMPORT] Added image {image_filename} to case {new_case_id}")
        
        try:
            db.session.commit()
        except Exception as commit_error:
            db.session.rollback()
            print(f"[IMPORT] ERROR during image commit: {commit_error}")
            import traceback
            traceback.print_exc()
            raise
        
        # Import revision sessions
        # For FRCR Examiner: Skip user-specific data (sessions, flags, highlights, notes)
        # For FRCR Revision: Import all user data
        if not is_frcr_examiner:
            for session_data in backup_data.get('revision_sessions', []):
                # Map user_id from backup using ID mapping
                old_user_id = session_data.get('user_id')
                user_id = user_id_map.get(old_user_id) if old_user_id else current_user.id
                
                if not user_id:
                    stats['revision_sessions']['skipped'] += 1
                    continue
                
                # Map case_ids from backup (old IDs -> new IDs)
                old_case_ids = session_data.get('case_ids', [])
                case_ids = [case_id_map.get(cid) for cid in old_case_ids if case_id_map.get(cid)]
                
                if not case_ids:
                    stats['revision_sessions']['skipped'] += 1
                    continue
                
                # Check if session already exists
                existing = RevisionSession.query.filter_by(user_id=user_id).first()
                if existing and not overwrite_existing:
                    stats['revision_sessions']['skipped'] += 1
                    continue
                
                if existing and overwrite_existing:
                    existing.set_case_ids_list(case_ids)
                    existing.current_case_index = session_data.get('current_case_index', 0)
                    # Update created_at if provided
                    if session_data.get('created_at'):
                        try:
                            if isinstance(session_data['created_at'], str):
                                existing.created_at = datetime.fromisoformat(session_data['created_at'])
                            elif isinstance(session_data['created_at'], datetime):
                                existing.created_at = session_data['created_at']
                        except (ValueError, TypeError) as e:
                            print(f"[IMPORT] Warning: Could not parse session created_at datetime: {session_data.get('created_at')}, error: {e}")
                    stats['revision_sessions']['added'] += 1
                else:
                    # Create new session - case_ids is required (nullable=False), so provide empty JSON array initially
                    rev_session = RevisionSession(
                        user_id=user_id,
                        case_ids='[]',  # Will be set by set_case_ids_list below
                        current_case_index=session_data.get('current_case_index', 0),
                    )
                    rev_session.set_case_ids_list(case_ids)
                    # Set created_at if provided in backup data
                    if session_data.get('created_at'):
                        try:
                            if isinstance(session_data['created_at'], str):
                                rev_session.created_at = datetime.fromisoformat(session_data['created_at'])
                            elif isinstance(session_data['created_at'], datetime):
                                rev_session.created_at = session_data['created_at']
                        except (ValueError, TypeError) as e:
                            print(f"[IMPORT] Warning: Could not parse session created_at datetime: {session_data.get('created_at')}, error: {e}")
                    db.session.add(rev_session)
                    stats['revision_sessions']['added'] += 1
        
        # Import case flags
        # For FRCR Examiner: Skip user-specific data
        if not is_frcr_examiner:
            for flag_data in backup_data.get('case_flags', []):
                # Map user_id and case_id from backup using ID mappings
                old_user_id = flag_data.get('user_id')
                old_case_id = flag_data.get('case_id')
                
                user_id = user_id_map.get(old_user_id) if old_user_id else None
                case_id = case_id_map.get(old_case_id) if old_case_id else None
                
                # Validate mapped IDs exist
                if not user_id or not User.query.get(user_id):
                    stats['case_flags']['skipped'] += 1
                    continue
                if not case_id or not Case.query.get(case_id):
                    stats['case_flags']['skipped'] += 1
                    continue
                
                # Check if flag already exists
                existing = CaseFlag.query.filter_by(user_id=user_id, case_id=case_id).first()
                if existing:
                    if overwrite_existing:
                        # Update timestamp if overwriting
                        if flag_data.get('created_at'):
                            try:
                                if isinstance(flag_data['created_at'], str):
                                    existing.created_at = datetime.fromisoformat(flag_data['created_at'])
                                elif isinstance(flag_data['created_at'], datetime):
                                    existing.created_at = flag_data['created_at']
                            except (ValueError, TypeError) as e:
                                print(f"[IMPORT] Warning: Could not parse flag created_at datetime: {flag_data.get('created_at')}, error: {e}")
                        stats['case_flags']['added'] += 1
                    else:
                        stats['case_flags']['skipped'] += 1
                    continue
                
                flag = CaseFlag(
                    user_id=user_id,
                    case_id=case_id,
                )
                if flag_data.get('created_at'):
                    try:
                        if isinstance(flag_data['created_at'], str):
                            flag.created_at = datetime.fromisoformat(flag_data['created_at'])
                        elif isinstance(flag_data['created_at'], datetime):
                            flag.created_at = flag_data['created_at']
                    except (ValueError, TypeError) as e:
                        print(f"[IMPORT] Warning: Could not parse flag created_at datetime: {flag_data.get('created_at')}, error: {e}")
                db.session.add(flag)
                stats['case_flags']['added'] += 1
        
        # Import highlights
        # For FRCR Examiner: Skip user-specific data
        if not is_frcr_examiner:
            for highlight_data in backup_data.get('highlights', []):
                # Map user_id and case_id from backup using ID mappings
                old_user_id = highlight_data.get('user_id')
                old_case_id = highlight_data.get('case_id')
                
                user_id = user_id_map.get(old_user_id) if old_user_id else None
                case_id = case_id_map.get(old_case_id) if old_case_id else None
                
                # Validate mapped IDs exist
                if not user_id or not User.query.get(user_id):
                    continue
                if not case_id or not Case.query.get(case_id):
                    continue
                
                highlight = TextHighlight(
                    user_id=user_id,
                    case_id=case_id,
                    text_content=highlight_data.get('text_content', ''),
                    highlight_color=highlight_data.get('highlight_color', 'yellow'),
                    field_name=highlight_data.get('field_name', 'discussion'),
                )
                if highlight_data.get('created_at'):
                    try:
                        if isinstance(highlight_data['created_at'], str):
                            highlight.created_at = datetime.fromisoformat(highlight_data['created_at'])
                        elif isinstance(highlight_data['created_at'], datetime):
                            highlight.created_at = highlight_data['created_at']
                    except (ValueError, TypeError) as e:
                        print(f"[IMPORT] Warning: Could not parse highlight created_at datetime: {highlight_data.get('created_at')}, error: {e}")
                db.session.add(highlight)
                stats['highlights']['added'] += 1
        
        # Import notes
        # For FRCR Examiner: Skip user-specific data
        if not is_frcr_examiner:
            for note_data in backup_data.get('notes', []):
                # Map user_id and case_id from backup using ID mappings
                old_user_id = note_data.get('user_id')
                old_case_id = note_data.get('case_id')
                
                user_id = user_id_map.get(old_user_id) if old_user_id else None
                case_id = case_id_map.get(old_case_id) if old_case_id else None
                
                # Validate mapped IDs exist
                if not user_id or not User.query.get(user_id):
                    continue
                if not case_id or not Case.query.get(case_id):
                    continue
                
                note = CandidateNote(
                    user_id=user_id,
                    case_id=case_id,
                    note_text=note_data.get('note_text', ''),
                )
                if note_data.get('created_at'):
                    try:
                        if isinstance(note_data['created_at'], str):
                            note.created_at = datetime.fromisoformat(note_data['created_at'])
                        elif isinstance(note_data['created_at'], datetime):
                            note.created_at = note_data['created_at']
                    except (ValueError, TypeError) as e:
                        print(f"[IMPORT] Warning: Could not parse note created_at datetime: {note_data.get('created_at')}, error: {e}")
                db.session.add(note)
                stats['notes']['added'] += 1
        
        # Commit all notes at once (batch commit)
        # For PostgreSQL/Supabase: Handle connection timeouts and transaction issues
        try:
            db.session.commit()
        except Exception as commit_error:
            db.session.rollback()
            error_str = str(commit_error).lower()
            print(f"[IMPORT] ERROR during notes batch commit: {commit_error}")
            import traceback
            traceback.print_exc()
            
            # Check for PostgreSQL-specific errors
            if 'timeout' in error_str or 'connection' in error_str:
                raise Exception('Database connection timeout. The import may be too large. Please try importing in smaller batches.')
            elif 'deadlock' in error_str or 'lock' in error_str:
                raise Exception('Database transaction conflict. Please try again in a few moments.')
            else:
                raise
        
        # Build response message
        message_parts = ['Database imported successfully']
        if stats['staging']['added'] > 0:
            staging_msg = f"{stats['staging']['added']} case(s) sent to staging for review (missing critical fields)."
            if stats['staging']['images_stored'] > 0:
                staging_msg += f" {stats['staging']['images_stored']} image(s) stored in staging cases."
            message_parts.append(staging_msg)
        
        # Include debug info about image matching in response
        debug_info = {
            'total_images_in_backup': len(backup_data.get('case_images', [])),
            'staging_cases_with_images': stats['staging']['images_stored'],
            'staging_cases_total': stats['staging']['added'],
        }
        
        return jsonify({
            'success': True,
            'message': ' '.join(message_parts),
            'stats': stats,
            'staging_count': stats['staging']['added'],
            'staging_images_count': stats['staging']['images_stored'],
            'import_batch_id': import_batch_id if stats['staging']['added'] > 0 else None,
            'debug': debug_info
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        error_traceback = traceback.format_exc()
        error_message = str(e)
        error_lower = error_message.lower()
        
        # Handle PostgreSQL/Supabase specific errors
        # Check for actual PostgreSQL error codes and messages
        if hasattr(e, 'orig') and hasattr(e.orig, 'pgcode'):
            # PostgreSQL specific error
            pgcode = e.orig.pgcode
            if pgcode == '40001':  # Serialization failure
                error_message = 'Database transaction conflict. Please try again in a few moments.'
            elif pgcode == '40P01':  # Deadlock detected
                error_message = 'Database deadlock detected. Please try again.'
            elif pgcode == '23505':  # Unique violation
                error_message = 'Duplicate entry detected. Some data may already exist in the database.'
            elif pgcode == '23503':  # Foreign key violation
                error_message = 'Data integrity error. The backup file may contain invalid references.'
            elif pgcode == '23502':  # Not null violation
                error_message = 'Missing required data. The backup file may be incomplete.'
        
        # Fallback to string matching
        if 'timeout' in error_lower or 'connection' in error_lower or 'timed out' in error_lower:
            error_message = 'Database connection timeout. The import operation may be too large or taking too long. Please try importing in smaller batches or contact support.'
        elif 'deadlock' in error_lower or ('lock' in error_lower and 'waiting' in error_lower):
            error_message = 'Database transaction conflict. Another operation may be in progress. Please try again in a few moments.'
        elif 'disturbed' in error_lower or 'body' in error_lower or 'request entity too large' in error_lower:
            # This might be a request body size issue or connection issue
            error_message = 'Request body error. The backup file may be too large (Vercel limit: 4.5MB) or the connection was interrupted. Please try a smaller backup file or split the import.'
        elif 'violates' in error_lower and 'constraint' in error_lower:
            error_message = 'Data integrity error. The backup file may contain invalid data or duplicate entries. Please verify the backup file.'
        elif 'syntax error' in error_lower or 'invalid' in error_lower or 'malformed' in error_lower:
            error_message = 'Invalid data format. Please ensure the backup file is valid JSON and was exported from a compatible version.'
        elif 'operationalerror' in error_lower or 'database' in error_lower:
            error_message = f'Database error: {str(e)[:200]}. Please check Vercel logs for details.'
        
        print(f"[IMPORT] ERROR: {error_message}")
        print(f"[IMPORT] Original error: {str(e)}")
        print(f"[IMPORT] TRACEBACK:\n{error_traceback}")
        # Log to stderr for Vercel logs
        import sys
        sys.stderr.write(f"[IMPORT] ERROR: {error_message}\n")
        sys.stderr.write(f"[IMPORT] Original: {str(e)}\n")
        sys.stderr.write(f"[IMPORT] TRACEBACK:\n{error_traceback}\n")
        return jsonify({
            'error': f'Import failed: {error_message}',
            'details': error_traceback.split('\n')[-5:] if len(error_traceback) > 0 else []
        }), 500


@backup_bp.route('/status', methods=['GET'])
@login_required
def backup_status():
    """Get backup status and reminder info"""
    if not check_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    last_backup = session.get('last_backup_time')
    
    if last_backup:
        last_backup_dt = datetime.fromisoformat(last_backup)
        hours_since = (datetime.utcnow() - last_backup_dt).total_seconds() / 3600
        needs_backup = hours_since >= 24
    else:
        needs_backup = True
        hours_since = None
    
    # Count records
    stats = {
        'total_users': User.query.filter_by(is_deleted=False).count(),
        'total_cases': Case.query.count(),
        'total_questions': Question.query.count(),
        'total_answers': Answer.query.count(),
        'total_images': CaseImage.query.count(),
        'total_sessions': RevisionSession.query.count(),
        'total_flags': CaseFlag.query.count(),
    }
    
    return jsonify({
        'is_admin': True,
        'last_backup_time': last_backup,
        'hours_since_backup': hours_since,
        'needs_backup': needs_backup,
        'stats': stats
    })
