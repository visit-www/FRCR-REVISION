from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from models import db, ExamSession, Packet, Case, Candidate
from datetime import datetime
import os

app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/frcr_examiner.db'
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


@app.route('/api/exam/create', methods=['POST'])
def create_exam():
    """Create a new exam session"""
    data = request.get_json()
    
    exam_date = datetime.strptime(data['exam_date'], '%Y-%m-%d').date()
    exam_time = data['exam_time']
    
    exam = ExamSession(exam_date=exam_date, exam_time=exam_time)
    db.session.add(exam)
    db.session.commit()
    
    return jsonify({'exam_id': exam.id, 'message': 'Exam session created'})


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


if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000)
