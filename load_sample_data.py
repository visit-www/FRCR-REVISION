"""
Sample Data Loader for FRCR Examiner
Run this script to populate the database with sample data for testing
"""

from app import app, db
from models import ExamSession, Packet, Case, Candidate
from datetime import datetime, date

def load_sample_data():
    """Load sample exam data into the database"""
    
    with app.app_context():
        # Clear existing data (optional - remove the next line to keep existing data)
        # db.drop_all()
        # db.create_all()
        
        # Create exam session
        exam_date = date.today()
        exam_time = '09:00'
        date_str = exam_date.strftime('%d %b %Y')
        time_obj = datetime.strptime(exam_time, '%H:%M').time()
        time_str = time_obj.strftime('%I:%M %p')
        session_name = f"{date_str} {time_str} Exam Session"
        
        exam = ExamSession(
            exam_date=exam_date,
            exam_time=exam_time,
            session_name=session_name
        )
        db.session.add(exam)
        db.session.flush()  # Get the exam ID
        
        # Create 4 packets with sample data
        packets = []
        for i in range(1, 5):
            packet = Packet(
                exam_id=exam.id,
                packet_number=i,
                packet_id=f'FORM{i:03d}'
            )
            db.session.add(packet)
            db.session.flush()
            packets.append(packet)
            
            # Add 3 cases to each packet
            for case_num in range(1, 4):
                case = Case(
                    packet_id=packet.id,
                    case_number=case_num,
                    diagnosis=f'Packet {i}, Case {case_num}: Sample Diagnosis - This is a test case for diagnosis {i}-{case_num}',
                    questions=f"""Question 1: What is the key finding in this case?
Question 2: What differential diagnoses should be considered?
Question 3: What is the most likely diagnosis based on imaging?
Question 4: What management would you recommend?""",
                    answers=f"""Answer 1: The key finding is [describe imaging finding for case {i}-{case_num}]
Answer 2: Differential diagnoses include:
  - Diagnosis A
  - Diagnosis B
  - Diagnosis C
Answer 3: The most likely diagnosis is [specific diagnosis for case {i}-{case_num}]
Answer 4: Recommended management:
  - Initial imaging: [imaging type]
  - Follow-up: [follow-up recommendation]
  - Treatment: [treatment option]""",
                    discussion=f"""Case Discussion for Packet {i}, Case {case_num}:

This case demonstrates important radiological findings relevant to FRCR examination.

Key Teaching Points:
- Point 1: Clinical significance of the imaging finding
- Point 2: Differential diagnosis considerations
- Point 3: Management implications
- Point 4: Follow-up recommendations

Clinical Context:
This is a typical case seen in clinical practice with important diagnostic implications.

Further Resources:
- Reference textbook pages: XX-YY
- Similar cases: See Case {case_num-1 if case_num > 1 else 1}
- Current guidelines: [relevant guidelines]"""
                )
                db.session.add(case)
        
        db.session.commit()
        
        # Create 4 sample candidates
        for i in range(1, 5):
            candidate = Candidate(
                exam_id=exam.id,
                candidate_name=f'Candidate {chr(64+i)}',  # A, B, C, D
                candidate_number=i,
                packet_number=i
            )
            db.session.add(candidate)
        
        db.session.commit()
        
        print("✓ Sample data loaded successfully!")
        print(f"  - Exam Date: {exam.exam_date}")
        print(f"  - Exam Time: {exam.exam_time}")
        print(f"  - Packets: 4 (FORM001 - FORM004)")
        print(f"  - Cases per Packet: 3")
        print(f"  - Candidates: 4 (Candidate A - D)")
        print(f"\nTotal database entries:")
        print(f"  - ExamSessions: {ExamSession.query.count()}")
        print(f"  - Packets: {Packet.query.count()}")
        print(f"  - Cases: {Case.query.count()}")
        print(f"  - Candidates: {Candidate.query.count()}")
        print("\nDatabase ready for testing!")
        print("Visit http://localhost:5000 to access the application")

if __name__ == '__main__':
    load_sample_data()
