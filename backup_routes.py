"""
Database Backup and Restore Routes for Web Deployment
Handles manual backup downloads and restore from uploads
"""
from flask import Blueprint, jsonify, send_file, request, session
from flask_login import login_required, current_user
from models import db, User, ExamSession, Packet, Case, Candidate, CaseImage, Question, Answer
from datetime import datetime, timedelta
import json
import io
import os

backup_bp = Blueprint('backup', __name__, url_prefix='/api/backup')

def check_admin():
    """Check if current user is admin (first registered user)"""
    try:
        if not current_user.is_authenticated:
            return False
        first_user = User.query.order_by(User.id).first()
        return first_user and current_user.id == first_user.id
    except Exception as e:
        print(f"[BACKUP] Admin check error: {e}")
        return False

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
                'database_type': 'postgresql' if os.getenv('DATABASE_URL') else 'sqlite',
                'version': '1.0'
            },
            'users': [],
            'exam_sessions': [],
            'packets': [],
            'cases': [],
            'candidates': [],
            'case_images': [],
            'questions': [],
            'answers': []
        }
        
        # Export users (without passwords for security)
        for user in User.query.all():
            backup_data['users'].append({
                'id': user.id,
                'email': user.email,
                'full_name': user.full_name,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat() if user.created_at else None
            })
        
        # Export exam sessions
        for exam_session in ExamSession.query.all():
            backup_data['exam_sessions'].append({
                'id': exam_session.id,
                'user_id': exam_session.user_id,
                'exam_date': exam_session.exam_date.isoformat() if exam_session.exam_date else None,
                'exam_time': exam_session.exam_time,
                'session_name': exam_session.session_name,
                'created_at': exam_session.created_at.isoformat() if exam_session.created_at else None
            })
        
        # Export packets
        for packet in Packet.query.all():
            backup_data['packets'].append({
                'id': packet.id,
                'exam_id': packet.exam_id,
                'packet_number': packet.packet_number,
                'packet_id': packet.packet_id
            })
        
        # Export cases
        for case in Case.query.all():
            backup_data['cases'].append({
                'id': case.id,
                'packet_id': case.packet_id,
                'case_number': case.case_number,
                'diagnosis': case.diagnosis,
                'questions': case.questions,
                'answers': case.answers,
                'discussion': case.discussion
            })
        
        # Export candidates
        for candidate in Candidate.query.all():
            backup_data['candidates'].append({
                'id': candidate.id,
                'exam_id': candidate.exam_id,
                'candidate_name': candidate.candidate_name,
                'candidate_number': candidate.candidate_number,
                'packet_number': candidate.packet_number
            })
        
        # Export case images (base64 encoded)
        import base64
        for image in CaseImage.query.all():
            backup_data['case_images'].append({
                'id': image.id,
                'case_id': image.case_id,
                'image_data': base64.b64encode(image.image_data).decode('utf-8'),
                'image_filename': image.image_filename,
                'image_type': image.image_type,
                'image_description': image.image_description,
                'created_at': image.created_at.isoformat() if image.created_at else None
            })
        
        # Export questions
        for question in Question.query.all():
            backup_data['questions'].append({
                'id': question.id,
                'case_id': question.case_id,
                'question_number': question.question_number,
                'question_text': question.question_text,
                'created_at': question.created_at.isoformat() if question.created_at else None
            })
        
        # Export answers
        for answer in Answer.query.all():
            backup_data['answers'].append({
                'id': answer.id,
                'case_id': answer.case_id,
                'answer_number': answer.answer_number,
                'answer_text': answer.answer_text,
                'created_at': answer.created_at.isoformat() if answer.created_at else None
            })
        
        # Create JSON file in memory
        json_data = json.dumps(backup_data, indent=2)
        json_bytes = io.BytesIO(json_data.encode('utf-8'))
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'frcr_examiner_backup_{timestamp}.json'
        
        # Update session with last backup time
        session['last_backup_time'] = datetime.utcnow().isoformat()
        
        return send_file(
            json_bytes,
            mimetype='application/json',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"[BACKUP] Error creating backup: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Backup failed: {str(e)}'}), 500


@backup_bp.route('/restore', methods=['POST'])
@login_required
def restore_backup():
    """Restore database from uploaded JSON backup"""
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
        backup_data = json.loads(file.read().decode('utf-8'))
        
        # Validate backup structure
        if 'metadata' not in backup_data:
            return jsonify({'error': 'Invalid backup file format'}), 400
        
        # Clear existing data (DANGEROUS - make sure user confirms)
        if not request.form.get('confirm_overwrite'):
            return jsonify({'error': 'Please confirm data overwrite'}), 400
        
        # Start restoration
        print("[RESTORE] Starting database restoration...")
        
        # Clear all tables (in correct order to respect foreign keys)
        Answer.query.delete()
        Question.query.delete()
        CaseImage.query.delete()
        Candidate.query.delete()
        Case.query.delete()
        Packet.query.delete()
        ExamSession.query.delete()
        # Don't delete users - keep existing users
        
        db.session.commit()
        print("[RESTORE] Cleared existing data")
        
        # Restore exam sessions
        for session_data in backup_data.get('exam_sessions', []):
            session = ExamSession(
                id=session_data['id'],
                user_id=current_user.id,  # Assign to current user
                exam_date=datetime.fromisoformat(session_data['exam_date']) if session_data.get('exam_date') else datetime.utcnow(),
                exam_time=session_data['exam_time'],
                session_name=session_data['session_name']
            )
            db.session.add(session)
        
        db.session.flush()
        print(f"[RESTORE] Restored {len(backup_data.get('exam_sessions', []))} exam sessions")
        
        # Restore packets
        for packet_data in backup_data.get('packets', []):
            packet = Packet(
                id=packet_data['id'],
                exam_id=packet_data['exam_id'],
                packet_number=packet_data['packet_number'],
                packet_id=packet_data['packet_id']
            )
            db.session.add(packet)
        
        db.session.flush()
        print(f"[RESTORE] Restored {len(backup_data.get('packets', []))} packets")
        
        # Restore cases
        for case_data in backup_data.get('cases', []):
            case = Case(
                id=case_data['id'],
                packet_id=case_data['packet_id'],
                case_number=case_data['case_number'],
                diagnosis=case_data['diagnosis'],
                questions=case_data['questions'],
                answers=case_data['answers'],
                discussion=case_data.get('discussion', '')
            )
            db.session.add(case)
        
        db.session.flush()
        print(f"[RESTORE] Restored {len(backup_data.get('cases', []))} cases")
        
        # Restore candidates
        for candidate_data in backup_data.get('candidates', []):
            candidate = Candidate(
                id=candidate_data['id'],
                exam_id=candidate_data['exam_id'],
                candidate_name=candidate_data['candidate_name'],
                candidate_number=candidate_data['candidate_number'],
                packet_number=candidate_data['packet_number']
            )
            db.session.add(candidate)
        
        db.session.flush()
        print(f"[RESTORE] Restored {len(backup_data.get('candidates', []))} candidates")
        
        # Restore case images
        import base64
        for image_data in backup_data.get('case_images', []):
            image = CaseImage(
                id=image_data['id'],
                case_id=image_data['case_id'],
                image_data=base64.b64decode(image_data['image_data']),
                image_filename=image_data['image_filename'],
                image_type=image_data['image_type'],
                image_description=image_data.get('image_description', '')
            )
            db.session.add(image)
        
        db.session.flush()
        print(f"[RESTORE] Restored {len(backup_data.get('case_images', []))} images")
        
        # Restore questions
        for question_data in backup_data.get('questions', []):
            question = Question(
                id=question_data['id'],
                case_id=question_data['case_id'],
                question_number=question_data['question_number'],
                question_text=question_data['question_text']
            )
            db.session.add(question)
        
        db.session.flush()
        print(f"[RESTORE] Restored {len(backup_data.get('questions', []))} questions")
        
        # Restore answers
        for answer_data in backup_data.get('answers', []):
            answer = Answer(
                id=answer_data['id'],
                case_id=answer_data['case_id'],
                answer_number=answer_data['answer_number'],
                answer_text=answer_data['answer_text']
            )
            db.session.add(answer)
        
        db.session.flush()
        print(f"[RESTORE] Restored {len(backup_data.get('answers', []))} answers")
        
        # Commit all changes
        db.session.commit()
        
        print("[RESTORE] Database restoration completed successfully")
        
        return jsonify({
            'success': True,
            'message': 'Database restored successfully',
            'stats': {
                'exam_sessions': len(backup_data.get('exam_sessions', [])),
                'packets': len(backup_data.get('packets', [])),
                'cases': len(backup_data.get('cases', [])),
                'candidates': len(backup_data.get('candidates', [])),
                'images': len(backup_data.get('case_images', [])),
                'questions': len(backup_data.get('questions', [])),
                'answers': len(backup_data.get('answers', []))
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"[RESTORE] Error restoring backup: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Restore failed: {str(e)}'}), 500


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
        'total_sessions': ExamSession.query.count(),
        'total_packets': Packet.query.count(),
        'total_cases': Case.query.count(),
        'total_candidates': Candidate.query.count(),
        'total_images': CaseImage.query.count()
    }
    
    return jsonify({
        'is_admin': True,
        'last_backup_time': last_backup,
        'hours_since_backup': hours_since,
        'needs_backup': needs_backup,
        'stats': stats
    })
