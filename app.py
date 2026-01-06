from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
from models import db, ExamSession, Packet, Case, Candidate, CaseImage, Question, Answer
from backup_manager import init_backup_manager, get_backup_manager
from datetime import datetime
import os
from io import BytesIO
import mimetypes
import atexit

app = Flask(__name__)

# Ensure instance folder exists
instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
os.makedirs(instance_path, exist_ok=True)

# Configuration
# Use PostgreSQL on production (Railway), SQLite locally
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    # PostgreSQL on Railway
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL.replace('postgres://', 'postgresql://')
else:
    # SQLite for local development
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "frcr_examiner.db")}'
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

with app.app_context():
    db.create_all()
    # Initialize backup manager and create startup backup
    backup_manager = init_backup_manager(app)


# ==================== BACKUP HOOKS ====================

def backup_on_shutdown():
    """Create backup when application shuts down"""
    backup_manager = get_backup_manager()
    if backup_manager:
        backup_manager.create_backup(description="Auto backup on app shutdown")


# Register shutdown backup
atexit.register(backup_on_shutdown)


@app.route('/')
def index():
    """Smart dashboard - entry point for all workflows"""
    return render_template('dashboard.html')


# ==================== SETUP WORKFLOW ====================

@app.route('/setup/sessions')
def setup_sessions():
    """Manage exam sessions"""
    return render_template('setup_sessions.html')


@app.route('/setup/cases')
def setup_cases():
    """Case bank management"""
    return render_template('setup_cases.html')


@app.route('/setup/candidates')
def setup_candidates():
    """Candidate management"""
    return render_template('setup_candidates.html')


# ==================== EXAM WORKFLOW ====================

@app.route('/exam/start')
def exam_start():
    """Start exam - select candidate"""
    return render_template('exam_start.html')


@app.route('/prepare-exam')
def prepare_exam():
    """Deprecated - redirects to new setup"""
    return redirect(url_for('setup_sessions'))


@app.route('/api/exam/sessions')
def get_exam_sessions():
    """Get all exam sessions"""
    sessions = ExamSession.query.order_by(ExamSession.created_at.desc()).all()
    return jsonify([{
        'id': s.id,
        'session_name': s.session_name,
        'exam_date': s.exam_date.strftime('%Y-%m-%d'),
        'exam_time': s.exam_time,
        'created_at': s.created_at.strftime('%Y-%m-%d %H:%M:%S')
    } for s in sessions])


@app.route('/api/exam/create', methods=['POST'])
def create_exam():
    """Create a new exam session"""
    data = request.get_json()
    
    exam_date = datetime.strptime(data['exam_date'], '%Y-%m-%d').date()
    exam_time = data['exam_time']
    
    # Format session name: "05 Jan 2026 1:30 PM Exam Session"
    date_str = exam_date.strftime('%d %b %Y')
    
    # Convert 24-hour time to 12-hour format with AM/PM
    time_obj = datetime.strptime(exam_time, '%H:%M').time()
    time_str = time_obj.strftime('%I:%M %p')
    
    session_name = f"{date_str} {time_str} Exam Session"
    
    exam = ExamSession(
        exam_date=exam_date,
        exam_time=exam_time,
        session_name=session_name
    )
    db.session.add(exam)
    db.session.commit()
    
    return jsonify({
        'exam_id': exam.id,
        'session_name': session_name,
        'message': f'Exam session "{session_name}" created'
    })


@app.route('/api/packet/create', methods=['POST'])
def create_packet():
    """Create a new packet"""
    data = request.get_json()
    
    packet = Packet(
        exam_id=data['exam_id'],
        packet_number=data['packet_number'],
        packet_id=data['packet_id']
    )
    db.session.add(packet)
    db.session.commit()
    
    return jsonify({'packet_id': packet.id, 'message': 'Packet created'})


@app.route('/api/case/create', methods=['POST'])
def create_case():
    """Create a new case"""
    data = request.get_json()
    
    # Extract questions and answers from pairs
    questions = []
    answers = []
    if 'pairs' in data:
        for pair in data['pairs']:
            if pair.get('question_text'):
                questions.append({'question_text': pair['question_text']})
            if pair.get('answer_text'):
                answers.append({'answer_text': pair['answer_text']})
    
    # If questions/answers are provided directly (for backwards compatibility)
    if 'questions' in data:
        questions = data['questions']
    if 'answers' in data:
        answers = data['answers']
    
    case = Case(
        packet_id=data['packet_id'],
        case_number=data['case_number'],
        diagnosis=data['diagnosis'],
        questions=questions or [],
        answers=answers or [],
        discussion=data.get('discussion', '')
    )
    db.session.add(case)
    db.session.commit()
    
    return jsonify({'success': True, 'id': case.id, 'case_id': case.id, 'message': 'Case created'})


@app.route('/api/candidate/create', methods=['POST'])
def create_candidate():
    """Create a new candidate"""
    data = request.get_json()
    
    candidate = Candidate(
        exam_id=data['exam_id'],
        candidate_name=data['candidate_name'],
        candidate_number=data['candidate_number'],
        packet_number=data['candidate_number']  # Candidate number maps to packet number
    )
    db.session.add(candidate)
    db.session.commit()
    
    return jsonify({'candidate_id': candidate.id, 'message': 'Candidate created'})


@app.route('/start-exam')
def start_exam():
    """Deprecated - redirects to new exam start"""
    return redirect(url_for('exam_start'))


@app.route('/exam/select-candidate')
def exam_select_candidate():
    """Select candidate from session"""
    exam_sessions = ExamSession.query.order_by(ExamSession.created_at.desc()).all()
    
    if not exam_sessions:
        return redirect(url_for('setup_sessions'))
    
    return render_template('start_exam.html', exams=exam_sessions)


@app.route('/select-candidate')
def select_candidate():
    """Deprecated - redirects to new workflow"""
    return redirect(url_for('exam_select_candidate'))


@app.route('/api/candidates/<int:exam_id>')
def get_candidates(exam_id):
    """Get all candidates for an exam"""
    candidates = Candidate.query.filter_by(exam_id=exam_id).all()
    return jsonify([{
        'id': c.id,
        'candidate_name': c.candidate_name,
        'candidate_number': c.candidate_number,
        'packet_number': c.packet_number
    } for c in candidates])


@app.route('/view-packet/<int:candidate_id>')
def view_packet(candidate_id):
    """View packet for a specific candidate"""
    candidate = Candidate.query.get(candidate_id)
    
    if not candidate:
        return redirect(url_for('start_exam'))
    
    # Get the packet corresponding to the candidate's packet number
    packet = Packet.query.filter_by(
        exam_id=candidate.exam_id,
        packet_number=candidate.packet_number
    ).first()
    
    session['current_candidate_id'] = candidate_id
    session['current_packet_id'] = packet.id if packet else None
    
    return render_template('view_packet.html', candidate=candidate, packet=packet)


@app.route('/api/packet/<int:packet_id>/cases')
def get_packet_cases(packet_id):
    """Get all cases for a packet"""
    cases = Case.query.filter_by(packet_id=packet_id).order_by(Case.case_number).all()
    return jsonify([{
        'id': c.id,
        'case_number': c.case_number,
        'diagnosis': c.diagnosis,
        'questions': c.questions,
        'answers': c.answers,
        'discussion': c.discussion
    } for c in cases])


@app.route('/view-case/<int:case_id>')
def view_case(case_id):
    """View a specific case"""
    case = Case.query.get(case_id)
    
    if not case:
        return redirect(url_for('start_exam'))
    
    packet = Packet.query.get(case.packet_id)
    candidate_id = session.get('current_candidate_id')
    candidate = Candidate.query.get(candidate_id) if candidate_id else None
    
    return render_template('view_case.html', case=case, packet=packet, candidate=candidate)


@app.route('/edit-case')
def edit_case():
    """Full-page edit interface for a case"""
    case_id = request.args.get('id', type=int)
    is_new = request.args.get('new', 'false').lower() == 'true'
    packet_id = request.args.get('packetId', type=int)
    return_to = request.args.get('returnTo', url_for('start_exam'))
    
    if not is_new and not case_id:
        return redirect(url_for('start_exam'))
    
    if is_new and not packet_id:
        return redirect(url_for('start_exam'))
    
    case = Case.query.get(case_id) if case_id else None
    if not is_new and not case:
        return redirect(url_for('start_exam'))
    
    return render_template('edit_case.html', 
                         is_new=is_new,
                         packet_id=packet_id,
                         return_to=return_to,
                         case=case)


@app.route('/api/case/<int:case_id>', methods=['GET', 'PUT'])
def get_case(case_id):
    """Get case details as JSON or update case"""
    case = Case.query.get(case_id)
    
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    
    # Handle GET request
    if request.method == 'GET':
        return jsonify({
            'id': case.id,
            'case_number': case.case_number,
            'diagnosis': case.diagnosis,
            'questions': [{'question_text': q.question_text, 'id': q.id} for q in case.question_items],
            'answers': [{'answer_text': a.answer_text, 'id': a.id} for a in case.answer_items],
            'discussion': case.discussion
        })
    
    # Handle PUT request - update case
    data = request.get_json()
    
    try:
        # Update basic case fields
        if 'diagnosis' in data:
            case.diagnosis = data['diagnosis'].strip()
        if 'discussion' in data:
            case.discussion = data['discussion'].strip() if data['discussion'] else None
        if 'case_number' in data:
            case.case_number = data['case_number']
        
        # Handle Q&A pairs if provided
        if 'pairs' in data:
            # Delete existing pairs
            Question.query.filter_by(case_id=case_id).delete()
            Answer.query.filter_by(case_id=case_id).delete()
            
            # Create new pairs
            for index, pair in enumerate(data['pairs'], start=1):
                question_text = (pair.get('question_text') or '').strip()
                answer_text = (pair.get('answer_text') or '').strip()
                
                if question_text or answer_text:
                    if question_text:
                        question = Question(
                            case_id=case_id,
                            question_number=index,
                            question_text=question_text
                        )
                        db.session.add(question)
                    
                    if answer_text:
                        answer = Answer(
                            case_id=case_id,
                            answer_number=index,
                            answer_text=answer_text
                        )
                        db.session.add(answer)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Case updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/manage-session/<int:session_id>')
def manage_session(session_id):
    """Manage exam session - edit packets and candidates"""
    exam = ExamSession.query.get(session_id)
    
    if not exam:
        return redirect(url_for('index'))
    
    session['current_exam_id'] = session_id
    return render_template('manage_session.html', session=exam)


@app.route('/api/session/<int:session_id>/packets')
def get_session_packets(session_id):
    """Get all packets for a session"""
    packets = Packet.query.filter_by(exam_id=session_id).all()
    return jsonify([{
        'id': p.id,
        'packet_number': p.packet_number,
        'packet_id': p.packet_id
    } for p in packets])


@app.route('/api/packet/<int:packet_id>', methods=['DELETE'])
def delete_packet(packet_id):
    """Delete a packet and all its cases"""
    packet = Packet.query.get(packet_id)
    
    if not packet:
        return jsonify({'error': 'Packet not found'}), 404
    
    # Delete all cases in this packet
    Case.query.filter_by(packet_id=packet_id).delete()
    
    db.session.delete(packet)
    db.session.commit()
    
    return jsonify({'message': 'Packet deleted successfully'})


@app.route('/api/packet/<int:packet_id>', methods=['PUT'])
def update_packet(packet_id):
    """Update a packet"""
    packet = Packet.query.get(packet_id)
    
    if not packet:
        return jsonify({'error': 'Packet not found'}), 404
    
    data = request.get_json()
    
    if 'packet_number' in data:
        packet.packet_number = data['packet_number']
    if 'packet_id' in data:
        packet.packet_id = data['packet_id']
    
    db.session.commit()
    
    return jsonify({'message': 'Packet updated successfully'})


@app.route('/api/case/<int:case_id>', methods=['DELETE'])
def delete_case(case_id):
    """Delete a case"""
    case = Case.query.get(case_id)
    
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    
    db.session.delete(case)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Case deleted successfully'})


@app.route('/api/case/<int:case_id>/image', methods=['POST'])
def upload_case_image(case_id):
    """Upload an image for a case"""
    case = Case.query.get(case_id)
    
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400
    
    file = request.files['image']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check file size (max 10MB)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > 10 * 1024 * 1024:  # 10MB
        return jsonify({'error': 'File size exceeds 10MB limit'}), 400
    
    # Check file type
    allowed_types = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    file_type = mimetypes.guess_type(file.filename)[0]
    
    if file_type not in allowed_types:
        return jsonify({'error': 'Only image files (JPEG, PNG, GIF, WebP) are allowed'}), 400
    
    image_data = file.read()
    
    # Get description from form data
    description = request.form.get('description', '')
    
    case_image = CaseImage(
        case_id=case_id,
        image_data=image_data,
        image_filename=file.filename,
        image_type=file_type,
        image_description=description
    )
    
    db.session.add(case_image)
    db.session.commit()
    
    return jsonify({
        'image_id': case_image.id,
        'filename': case_image.image_filename,
        'message': 'Image uploaded successfully'
    })


@app.route('/api/case/<int:case_id>/images')
def get_case_images(case_id):
    """Get all images for a case"""
    images = CaseImage.query.filter_by(case_id=case_id).order_by(CaseImage.created_at).all()
    return jsonify([{
        'id': img.id,
        'filename': img.image_filename,
        'description': img.image_description if img.image_description else '',
        'created_at': img.created_at.strftime('%Y-%m-%d %H:%M:%S')
    } for img in images])


@app.route('/api/case-image/<int:image_id>')
def get_case_image(image_id):
    """Retrieve a case image by ID"""
    image = CaseImage.query.get(image_id)
    
    if not image:
        return jsonify({'error': 'Image not found'}), 404
    
    return send_file(
        BytesIO(image.image_data),
        mimetype=image.image_type,
        as_attachment=False,
        download_name=image.image_filename
    )


@app.route('/api/case-image/<int:image_id>', methods=['DELETE'])
def delete_case_image(image_id):
    """Delete a case image"""
    image = CaseImage.query.get(image_id)
    
    if not image:
        return jsonify({'error': 'Image not found'}), 404
    
    db.session.delete(image)
    db.session.commit()
    
    return jsonify({'message': 'Image deleted successfully'})


@app.route('/api/case-image/<int:image_id>/description', methods=['PUT'])
def update_image_description(image_id):
    """Update image description"""
    image = CaseImage.query.get(image_id)
    
    if not image:
        return jsonify({'error': 'Image not found'}), 404
    
    data = request.get_json()
    description = data.get('description', '')
    
    image.image_description = description
    db.session.commit()
    
    return jsonify({
        'image_id': image.id,
        'description': image.image_description,
        'message': 'Description updated successfully'
    })





@app.route('/api/candidate/<int:candidate_id>', methods=['PUT'])
def update_candidate(candidate_id):
    """Update a candidate"""
    candidate = Candidate.query.get(candidate_id)
    
    if not candidate:
        return jsonify({'error': 'Candidate not found'}), 404
    
    data = request.get_json()
    
    if 'candidate_name' in data:
        candidate.candidate_name = data['candidate_name']
    if 'candidate_number' in data:
        candidate.candidate_number = data['candidate_number']
    
    db.session.commit()
    
    return jsonify({'message': 'Candidate updated successfully'})


@app.route('/api/candidate/<int:candidate_id>', methods=['DELETE'])
def delete_candidate(candidate_id):
    """Delete a candidate"""
    candidate = Candidate.query.get(candidate_id)
    
    if not candidate:
        return jsonify({'error': 'Candidate not found'}), 404
    
    db.session.delete(candidate)
    db.session.commit()
    
    return jsonify({'message': 'Candidate deleted successfully'})


# ==================== BACKUP MANAGEMENT ENDPOINTS ====================

@app.route('/admin')
def admin_dashboard():
    """Admin dashboard for backup management"""
    return render_template('admin_dashboard.html')


@app.route('/api/backup/create', methods=['POST'])
def create_backup():
    """Create a new backup"""
    backup_manager = get_backup_manager()
    
    if backup_manager is None:
        return jsonify({'error': 'Backup manager not initialized'}), 500
    
    data = request.get_json() or {}
    description = data.get('description', 'Manual backup')
    
    result = backup_manager.create_backup(description)
    
    if result:
        return jsonify({
            'success': True,
            'message': 'Backup created successfully',
            'backup': result
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Backup creation failed'
        }), 500


@app.route('/api/backup/list')
def list_backups():
    """Get list of all backups"""
    backup_manager = get_backup_manager()
    
    if backup_manager is None:
        return jsonify({'error': 'Backup manager not initialized'}), 500
    
    backups = backup_manager.get_backup_list()
    
    return jsonify({
        'success': True,
        'backups': backups,
        'total_count': len(backups)
    })


@app.route('/api/backup/statistics')
def backup_statistics():
    """Get backup system statistics"""
    backup_manager = get_backup_manager()
    
    if backup_manager is None:
        return jsonify({'error': 'Backup manager not initialized'}), 500
    
    stats = backup_manager.get_statistics()
    
    return jsonify({
        'success': True,
        'statistics': stats
    })


@app.route('/api/backup/restore/<timestamp>', methods=['POST'])
def restore_backup(timestamp):
    """Restore database from backup"""
    backup_manager = get_backup_manager()
    
    if backup_manager is None:
        return jsonify({'error': 'Backup manager not initialized'}), 500
    
    result = backup_manager.restore_backup(timestamp)
    
    return jsonify(result)


@app.route('/api/backup/log')
def backup_log():
    """Get backup log entries"""
    backup_manager = get_backup_manager()
    
    if backup_manager is None:
        return jsonify({'error': 'Backup manager not initialized'}), 500
    
    lines = request.args.get('lines', 50, type=int)
    log_entries = backup_manager.get_log(lines)
    
    return jsonify({
        'success': True,
        'log': [entry.rstrip() for entry in log_entries]
    })


import socket

def find_free_port(start_port=5000, max_tries=20):
    port = start_port
    for _ in range(max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                port += 1
    raise RuntimeError("No free port found.")


import sys

def show_macos_gatekeeper_popup():
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        message = (
            "macOS Security Notice:\n\n"
            "If you see a message like:\n"
            "'FRCR_Examiner.app cannot be opened because it is from an unidentified developer.'\n\n"
            "This is normal for apps not downloaded from the App Store.\n\n"
            "How to open the app:\n"
            "1. Open Finder and locate FRCR_Examiner.app (in Applications or Downloads)\n"
            "2. Right-click (or Control-click) the app and select Open\n"
            "3. In the dialog, click Open again\n"
            "4. If you still can't open it, go to System Settings → Privacy & Security,\n"
            "   scroll to Security, click 'Allow Anyway', then try again.\n\n"
            "This only needs to be done the first time."
        )
        messagebox.showinfo("FRCR Examiner - macOS Info", message)
        root.destroy()
    except Exception:
        pass


# ==================== Question & Answer Management Endpoints ====================

@app.route('/api/case/<int:case_id>/questions', methods=['GET'])
def get_case_questions(case_id):
    """Get all questions for a case"""
    case = Case.query.get(case_id)
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    
    questions = Question.query.filter_by(case_id=case_id).order_by(Question.question_number).all()
    return jsonify([{
        'id': q.id,
        'number': q.question_number,
        'text': q.question_text
    } for q in questions])


@app.route('/api/case/<int:case_id>/answers', methods=['GET'])
def get_case_answers(case_id):
    """Get all answers for a case"""
    case = Case.query.get(case_id)
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    
    answers = Answer.query.filter_by(case_id=case_id).order_by(Answer.answer_number).all()
    return jsonify([{
        'id': a.id,
        'number': a.answer_number,
        'text': a.answer_text
    } for a in answers])


@app.route('/api/question/<int:question_id>', methods=['PUT'])
def update_question(question_id):
    """Update a single question's text"""
    question = Question.query.get(question_id)
    if not question:
        return jsonify({'error': 'Question not found'}), 404
    
    data = request.get_json()
    question.question_text = data.get('text', '').strip()
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Question updated'})


@app.route('/api/answer/<int:answer_id>', methods=['PUT'])
def update_answer(answer_id):
    """Update a single answer's text"""
    answer = Answer.query.get(answer_id)
    if not answer:
        return jsonify({'error': 'Answer not found'}), 404
    
    data = request.get_json()
    answer.answer_text = data.get('text', '').strip()
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Answer updated'})


@app.route('/api/case/<int:case_id>/qa-pairs', methods=['GET'])
def get_case_qa_pairs(case_id):
    """Get Q&A pairs for a case"""
    case = Case.query.get(case_id)
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    
    questions = Question.query.filter_by(case_id=case_id).order_by(Question.question_number).all()
    answers = Answer.query.filter_by(case_id=case_id).order_by(Answer.answer_number).all()
    
    pairs = []
    max_pairs = max(len(questions), len(answers))
    
    for i in range(max_pairs):
        pair = {
            'number': i + 1,
            'question': {
                'id': questions[i].id,
                'text': questions[i].question_text
            } if i < len(questions) else {'id': None, 'text': ''},
            'answer': {
                'id': answers[i].id,
                'text': answers[i].answer_text
            } if i < len(answers) else {'id': None, 'text': ''}
        }
        pairs.append(pair)
    
    return jsonify(pairs)


# ==================== SIMPLIFIED Q&A ENDPOINTS ====================

@app.route('/api/case/<int:case_id>/qa-pairs', methods=['PUT'])
def update_case_qa_pairs(case_id):
    """
    Simplified endpoint to update all Q&A pairs for a case in one request.
    Deletes old pairs and creates new ones based on provided data.
    """
    case = Case.query.get(case_id)
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    
    data = request.get_json()
    pairs = data.get('pairs', [])
    
    if not isinstance(pairs, list):
        return jsonify({'error': 'pairs must be an array'}), 400
    
    try:
        # Delete all existing Q&A pairs
        Question.query.filter_by(case_id=case_id).delete()
        Answer.query.filter_by(case_id=case_id).delete()
        
        # Create new pairs
        for index, pair in enumerate(pairs, start=1):
            question_text = (pair.get('question_text') or '').strip()
            answer_text = (pair.get('answer_text') or '').strip()
            
            # Only create if at least one has content
            if question_text or answer_text:
                if question_text:
                    question = Question(
                        case_id=case_id,
                        question_number=index,
                        question_text=question_text
                    )
                    db.session.add(question)
                
                if answer_text:
                    answer = Answer(
                        case_id=case_id,
                        answer_number=index,
                        answer_text=answer_text
                    )
                    db.session.add(answer)
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'Updated {len(pairs)} Q&A pairs'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    if sys.platform == 'darwin':
        show_macos_gatekeeper_popup()
    port = find_free_port(5000, 20)
    print(f"Starting server on http://127.0.0.1:{port}")
    app.run(debug=True, host='127.0.0.1', port=port)
