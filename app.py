from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from models import db, ExamSession, Packet, Case, Candidate
from datetime import datetime
import os

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


@app.route('/')
def index():
    """Home page with two tabs"""
    return render_template('index.html')


@app.route('/prepare-exam')
def prepare_exam():
    """Prepare exam page - enter exam details and cases"""
    return render_template('prepare_exam.html')


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
    
    case = Case(
        packet_id=data['packet_id'],
        case_number=data['case_number'],
        diagnosis=data['diagnosis'],
        questions=data['questions'],
        answers=data['answers'],
        discussion=data.get('discussion', '')
    )
    db.session.add(case)
    db.session.commit()
    
    return jsonify({'case_id': case.id, 'message': 'Case created'})


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
    """Start exam page - select candidate and view packets"""
    exam_sessions = ExamSession.query.order_by(ExamSession.created_at.desc()).first()
    
    if not exam_sessions:
        return redirect(url_for('prepare_exam'))
    
    session['current_exam_id'] = exam_sessions.id
    return render_template('start_exam.html', exam=exam_sessions)


@app.route('/select-candidate')
def select_candidate():
    """Select candidate page"""
    exam_id = request.args.get('exam_id')
    exam = ExamSession.query.get(exam_id)
    
    if not exam:
        return redirect(url_for('start_exam'))
    
    session['current_exam_id'] = exam_id
    return render_template('select_candidate.html', exam=exam)


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


@app.route('/api/case/<int:case_id>')
def get_case(case_id):
    """Get case details as JSON"""
    case = Case.query.get(case_id)
    
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    
    return jsonify({
        'id': case.id,
        'case_number': case.case_number,
        'diagnosis': case.diagnosis,
        'questions': case.questions,
        'answers': case.answers,
        'discussion': case.discussion
    })


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
    
    return jsonify({'message': 'Case deleted successfully'})


@app.route('/api/case/<int:case_id>', methods=['PUT'])
def update_case(case_id):
    """Update a case"""
    case = Case.query.get(case_id)
    
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    
    data = request.get_json()
    
    if 'case_number' in data:
        case.case_number = data['case_number']
    if 'diagnosis' in data:
        case.diagnosis = data['diagnosis']
    if 'questions' in data:
        case.questions = data['questions']
    if 'answers' in data:
        case.answers = data['answers']
    if 'discussion' in data:
        case.discussion = data['discussion']
    
    db.session.commit()
    
    return jsonify({'message': 'Case updated successfully'})


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


if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000)
