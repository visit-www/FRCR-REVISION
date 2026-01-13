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
            'staging': {'added': 0},  # Cases sent to staging for review
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
                            except:
                                pass
                        elif key == 'subscription_status' and value:
                            from models import SubscriptionStatus
                            try:
                                existing_user.subscription_status = SubscriptionStatus(value)
                            except:
                                pass
                        elif key == 'payment_status' and value:
                            from models import PaymentStatus
                            try:
                                existing_user.payment_status = PaymentStatus(value)
                            except:
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
                user = User(
                    email=filtered_data.get('email'),
                    password_hash=filtered_data.get('password_hash', ''),
                    full_name=filtered_data.get('full_name', ''),
                    role=UserRole(filtered_data.get('role', 'student')),
                    is_active=filtered_data.get('is_active', True),
                )
                if filtered_data.get('subscription_status'):
                    from models import SubscriptionStatus
                    user.subscription_status = SubscriptionStatus(filtered_data['subscription_status'])
                if filtered_data.get('payment_status'):
                    from models import PaymentStatus
                    user.payment_status = PaymentStatus(filtered_data['payment_status'])
                if filtered_data.get('created_at'):
                    user.created_at = datetime.fromisoformat(filtered_data['created_at'])
                db.session.add(user)
                stats['users']['added'] += 1
        
        db.session.commit()
        
        # Build user email to ID mapping and old ID to new ID mapping
        user_email_map = {u.email: u.id for u in User.query.all()}
        user_id_map = {}  # Map old user IDs from backup to new user IDs
        
        # Build ID mapping for users (old backup ID -> new database ID)
        for user_data in backup_data.get('users', []):
            old_id = user_data.get('id')
            email = user_data.get('email')
            if old_id and email:
                new_user = User.query.filter_by(email=email).first()
                if new_user:
                    user_id_map[old_id] = new_user.id
        
        # Import Cases
        case_id_map = {}  # Map old case IDs from backup to new case IDs
        
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
                                if key == 'module':
                                    # Try by value first (export format), then by name
                                    try:
                                        existing_case.module = FRCRModule(value)
                                    except (ValueError, KeyError):
                                        existing_case.module = FRCRModule[value]
                                elif key == 'body_part':
                                    try:
                                        existing_case.body_part = BodyPart(value)
                                    except (ValueError, KeyError):
                                        existing_case.body_part = BodyPart[value]
                                elif key == 'age_group':
                                    try:
                                        existing_case.age_group = AgeGroup(value)
                                    except (ValueError, KeyError):
                                        existing_case.age_group = AgeGroup[value]
                            except Exception as e:
                                print(f"[IMPORT] Warning: Could not set {key} to {value}: {e}")
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
                                    image_data_binary = base64.b64decode(img_data['image_data'])
                                
                                # Only create image if we have image data
                                if image_data_binary:
                                    image = CaseImage(
                                        case_id=existing_case.id,
                                        image_filename=img_data.get('filename', ''),
                                        image_type=img_data.get('image_type', 'image/jpeg'),
                                        image_description=img_data.get('description', ''),
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
                    
                    staging = ImportedCaseStaging(
                        original_id=old_case_id,
                        case_number=filtered_data.get('case_number'),
                        diagnosis=filtered_data.get('diagnosis', ''),
                        discussion=filtered_data.get('discussion', ''),
                        questions=questions_json,  # Legacy format for staging
                        answers=answers_json,  # Legacy format for staging
                        enrichment_status='pending',
                        import_batch_id=import_batch_id,
                        source_system='backup_import',
                        enrichment_notes=f"Missing fields: {', '.join(missing_fields)}. Requires admin review.",
                    )
                    db.session.add(staging)
                    db.session.flush()
                    
                    # Store images temporarily (will be migrated on promotion)
                    # For now, we'll need to handle images separately
                    # Images will be stored when case is promoted
                    
                    stats['staging']['added'] += 1
                    # Don't create case_id_map entry for staging cases
                    continue
                
                # All critical fields present - create case directly
                case = Case(
                    case_number=filtered_data.get('case_number', ''),
                    diagnosis=filtered_data.get('diagnosis', ''),
                    discussion=filtered_data.get('discussion', ''),
                    is_public=filtered_data.get('is_public', True),
                )
                
                # Set enums - try by value first (export format), then by name
                if filtered_data.get('module'):
                    try:
                        case.module = FRCRModule(filtered_data['module'])
                    except (ValueError, KeyError):
                        try:
                            case.module = FRCRModule[filtered_data['module']]
                        except (ValueError, KeyError) as e:
                            print(f"[IMPORT] Warning: Could not set module to {filtered_data['module']}: {e}")
                if filtered_data.get('body_part'):
                    try:
                        case.body_part = BodyPart(filtered_data['body_part'])
                    except (ValueError, KeyError):
                        try:
                            case.body_part = BodyPart[filtered_data['body_part']]
                        except (ValueError, KeyError) as e:
                            print(f"[IMPORT] Warning: Could not set body_part to {filtered_data['body_part']}: {e}")
                if filtered_data.get('age_group'):
                    try:
                        case.age_group = AgeGroup(filtered_data['age_group'])
                    except (ValueError, KeyError):
                        try:
                            case.age_group = AgeGroup[filtered_data['age_group']]
                        except (ValueError, KeyError) as e:
                            print(f"[IMPORT] Warning: Could not set age_group to {filtered_data['age_group']}: {e}")
                
                # Map created_by_user_id from backup using ID mapping
                if filtered_data.get('created_by_user_id'):
                    old_user_id = filtered_data.get('created_by_user_id')
                    case.created_by_user_id = user_id_map.get(old_user_id, current_user.id)
                if filtered_data.get('created_at'):
                    case.created_at = datetime.fromisoformat(filtered_data['created_at'])
                
                db.session.add(case)
                db.session.flush()
                
                # Add Q&A
                for q_data in case_data.get('questions', []):
                    question = Question(
                        case_id=case.id,
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
                            image_data_binary = base64.b64decode(img_data['image_data'])
                    
                    # Only create image if we have image data
                    if image_data_binary:
                        image = CaseImage(
                            case_id=case.id,
                            image_filename=img_data.get('filename', ''),
                            image_type=img_data.get('image_type', 'image/jpeg'),
                            image_description=img_data.get('description', ''),
                            image_data=image_data_binary
                        )
                        db.session.add(image)
                        stats['images']['added'] += 1
                
                stats['cases']['added'] += 1
                new_case_id = case.id
            
            # Store case ID mapping (for both new and existing cases)
            if old_case_id and new_case_id:
                case_id_map[old_case_id] = new_case_id
        
        db.session.commit()
        
        # Import revision sessions
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
                    rev_session.created_at = datetime.fromisoformat(session_data['created_at'])
                db.session.add(rev_session)
                stats['revision_sessions']['added'] += 1
        
        # Import case flags
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
                flag.created_at = datetime.fromisoformat(flag_data['created_at'])
            db.session.add(flag)
            stats['case_flags']['added'] += 1
        
        # Import highlights
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
                highlight.created_at = datetime.fromisoformat(highlight_data['created_at'])
            db.session.add(highlight)
            stats['highlights']['added'] += 1
        
        # Import notes
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
                note.created_at = datetime.fromisoformat(note_data['created_at'])
            db.session.add(note)
            stats['notes']['added'] += 1
        
        db.session.commit()
        
        # Build response message
        message_parts = ['Database imported successfully']
        if stats['staging']['added'] > 0:
            message_parts.append(f"{stats['staging']['added']} case(s) sent to staging for review (missing critical fields).")
        
        return jsonify({
            'success': True,
            'message': ' '.join(message_parts),
            'stats': stats,
            'staging_count': stats['staging']['added'],
            'import_batch_id': import_batch_id if stats['staging']['added'] > 0 else None
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Import failed: {str(e)}'}), 500


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
