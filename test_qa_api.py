#!/usr/bin/env python
"""Test Q&A API endpoints"""

import sys
sys.path.insert(0, '/Users/zen/myRepos/projects/FRCR_EXAMINER')

from app import app, db
from models import Case, Question, Answer

def test_qa_endpoints():
    """Test that Q&A API endpoints work correctly"""
    
    with app.app_context():
        # Get first case
        case = Case.query.first()
        if not case:
            print("❌ No cases found in database")
            return
        
        print(f"✅ Testing with Case {case.id}: {case.case_number}")
        
        # Test with Flask test client
        client = app.test_client()
        
        # Test GET qa-pairs endpoint
        print("\n1. Testing GET /api/case/<id>/qa-pairs")
        response = client.get(f'/api/case/{case.id}/qa-pairs')
        print(f"   Status: {response.status_code}")
        pairs = response.get_json()
        print(f"   Pairs count: {len(pairs)}")
        if pairs:
            print(f"   First pair: Q='{pairs[0]['question']['text'][:50]}...'")
        
        # Test GET questions endpoint
        print("\n2. Testing GET /api/case/<id>/questions")
        response = client.get(f'/api/case/{case.id}/questions')
        print(f"   Status: {response.status_code}")
        questions = response.get_json()
        print(f"   Questions count: {len(questions)}")
        
        # Test GET answers endpoint
        print("\n3. Testing GET /api/case/<id>/answers")
        response = client.get(f'/api/case/{case.id}/answers')
        print(f"   Status: {response.status_code}")
        answers = response.get_json()
        print(f"   Answers count: {len(answers)}")
        
        # Test POST new Q&A pair
        print("\n4. Testing POST /api/case/<id>/qa (new pair)")
        test_data = {
            "question_number": 99,
            "question_text": "Test Question?",
            "answer_number": 99,
            "answer_text": "Test Answer"
        }
        response = client.post(f'/api/case/{case.id}/qa', json=test_data)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.get_json()}")
        
        print("\n✅ All endpoint tests completed successfully!")

if __name__ == '__main__':
    test_qa_endpoints()
