#!/usr/bin/env python3
"""
Migration script to split monolithic questions and answers into separate records.
Splits by newline and creates individual Question and Answer records for each line.
"""

import sys
sys.path.insert(0, '.')

from app import app, db
from models import Case, Question, Answer

def migrate_questions_and_answers():
    """Migrate questions and answers from text fields to separate records"""
    
    with app.app_context():
        cases = Case.query.all()
        migrated_count = 0
        
        for case in cases:
            # Check if already migrated (has question_items)
            if case.question_items:
                print(f"Case {case.id} already migrated, skipping...")
                continue
            
            # Split questions by newline and filter empty lines
            question_lines = [q.strip() for q in case.questions.split('\n') if q.strip()]
            answer_lines = [a.strip() for a in case.answers.split('\n') if a.strip()]
            
            # Ensure equal number of Q&A pairs
            max_pairs = max(len(question_lines), len(answer_lines))
            
            # Pad with empty strings if needed
            while len(question_lines) < max_pairs:
                question_lines.append("")
            while len(answer_lines) < max_pairs:
                answer_lines.append("")
            
            # Create Question records
            for idx, question_text in enumerate(question_lines, 1):
                if question_text:  # Only create if not empty
                    q = Question(
                        case_id=case.id,
                        question_number=idx,
                        question_text=question_text
                    )
                    db.session.add(q)
            
            # Create Answer records
            for idx, answer_text in enumerate(answer_lines, 1):
                if answer_text:  # Only create if not empty
                    a = Answer(
                        case_id=case.id,
                        answer_number=idx,
                        answer_text=answer_text
                    )
                    db.session.add(a)
            
            migrated_count += 1
            print(f"✅ Migrated Case {case.id}: {len(question_lines)} questions, {len(answer_lines)} answers")
        
        try:
            db.session.commit()
            print(f"\n✅ Migration complete! {migrated_count} cases migrated.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {e}")
            sys.exit(1)

if __name__ == '__main__':
    print("Starting Q&A migration...")
    migrate_questions_and_answers()
    print("Done!")
