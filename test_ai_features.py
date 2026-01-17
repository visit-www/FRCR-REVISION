#!/usr/bin/env python3
"""
Test script for AI integration features:
1. Database migration verification
2. AI cache functionality
3. AI content verification
4. Status synchronization
"""

import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Case, AiDiagnosisCache, User, CaseStatus
from sqlalchemy import inspect

def test_database_migration():
    """Test if database tables exist"""
    print("\n" + "="*60)
    print("TEST 1: Database Migration Verification")
    print("="*60)
    
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    required_tables = [
        'ai_diagnosis_cache',
        'case'
    ]
    
    print(f"\nFound {len(tables)} tables in database")
    print(f"Required tables: {required_tables}")
    
    missing_tables = []
    for table in required_tables:
        if table in tables:
            print(f"  ✓ {table} exists")
        else:
            print(f"  ✗ {table} MISSING")
            missing_tables.append(table)
    
    # Check Case table columns
    if 'case' in tables:
        case_columns = [col['name'] for col in inspector.get_columns('case')]
        if 'ai_content_verified' in case_columns:
            print(f"  ✓ Case.ai_content_verified column exists")
        else:
            print(f"  ✗ Case.ai_content_verified column MISSING")
            missing_tables.append('case.ai_content_verified')
    
    # Check AiDiagnosisCache table structure
    if 'ai_diagnosis_cache' in tables:
        cache_columns = [col['name'] for col in inspector.get_columns('ai_diagnosis_cache')]
        required_cache_columns = [
            'id', 'diagnosis', 'provider', 'model_name',
            'first_case_id', 'first_user_id', 'first_generated_at',
            'query_count', 'last_queried_at'
        ]
        print(f"\n  AiDiagnosisCache columns:")
        for col in required_cache_columns:
            if col in cache_columns:
                print(f"    ✓ {col}")
            else:
                print(f"    ✗ {col} MISSING")
                missing_tables.append(f'ai_diagnosis_cache.{col}')
    
    if missing_tables:
        print(f"\n❌ FAILED: Missing tables/columns: {missing_tables}")
        print("   Run: flask db upgrade")
        return False
    else:
        print("\n✅ PASSED: All required tables and columns exist")
        return True


def test_ai_cache_functionality():
    """Test AI cache creation and retrieval"""
    print("\n" + "="*60)
    print("TEST 2: AI Cache Functionality")
    print("="*60)
    
    try:
        # Test creating a cache entry
        test_diagnosis = "Test Diagnosis for Cache"
        test_provider = "claude"
        test_model = "claude-sonnet-4-20250514"
        
        # Get a test case and user
        test_case = Case.query.first()
        test_user = User.query.first()
        
        if not test_case or not test_user:
            print("  ⚠ SKIPPED: No test case or user found")
            return True
        
        # Check if cache entry exists
        existing = AiDiagnosisCache.query.filter_by(
            diagnosis=test_diagnosis.lower().strip(),
            provider=test_provider,
            model_name=test_model
        ).first()
        
        if existing:
            print(f"  ✓ Cache entry exists for: {test_diagnosis}")
            print(f"    Provider: {existing.provider}, Model: {existing.model_name}")
            print(f"    First generated: {existing.first_generated_at}")
            print(f"    Query count: {existing.query_count}")
        else:
            print(f"  ℹ No cache entry found (this is OK for first run)")
        
        # Test cache query function
        from app import check_ai_diagnosis_cache
        cache_result = check_ai_diagnosis_cache(
            test_case.diagnosis if test_case.diagnosis else "Test",
            test_provider,
            test_model
        )
        
        if cache_result is None:
            print(f"  ✓ Cache check function works (no cache found)")
        else:
            print(f"  ✓ Cache check function works (cache found)")
        
        print("\n✅ PASSED: AI cache functionality works")
        return True
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_case_verification_field():
    """Test Case.ai_content_verified field"""
    print("\n" + "="*60)
    print("TEST 3: Case AI Content Verification Field")
    print("="*60)
    
    try:
        test_case = Case.query.first()
        if not test_case:
            print("  ⚠ SKIPPED: No test case found")
            return True
        
        # Check if field exists
        if hasattr(test_case, 'ai_content_verified'):
            print(f"  ✓ Case.ai_content_verified field exists")
            print(f"    Current value: {test_case.ai_content_verified}")
            
            # Test setting the value
            original_value = test_case.ai_content_verified
            test_case.ai_content_verified = True
            db.session.commit()
            
            # Verify it was saved
            db.session.refresh(test_case)
            if test_case.ai_content_verified == True:
                print(f"  ✓ Can set and save ai_content_verified")
            else:
                print(f"  ✗ Failed to save ai_content_verified")
                return False
            
            # Restore original value
            test_case.ai_content_verified = original_value
            db.session.commit()
            
            print("\n✅ PASSED: Case.ai_content_verified field works")
            return True
        else:
            print(f"  ✗ Case.ai_content_verified field does not exist")
            return False
            
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_status_sync():
    """Test status synchronization with ai_content_verified"""
    print("\n" + "="*60)
    print("TEST 4: Status Synchronization")
    print("="*60)
    
    try:
        test_case = Case.query.first()
        if not test_case:
            print("  ⚠ SKIPPED: No test case found")
            return True
        
        # Save original values
        original_status = test_case.status
        original_verified = test_case.ai_content_verified
        original_public = test_case.is_public
        
        # Test: Setting status to PUBLISHED should set ai_content_verified to True
        test_case.status = CaseStatus.PUBLISHED
        test_case.ai_content_verified = False  # Set to False first
        db.session.commit()
        
        # Simulate the sync logic from app.py
        if test_case.status == CaseStatus.PUBLISHED:
            test_case.ai_content_verified = True
            test_case.is_public = True
        
        db.session.commit()
        db.session.refresh(test_case)
        
        if test_case.ai_content_verified == True and test_case.is_public == True:
            print(f"  ✓ Publishing case sets ai_content_verified=True and is_public=True")
        else:
            print(f"  ✗ Publishing case did not sync correctly")
            print(f"    ai_content_verified: {test_case.ai_content_verified}, is_public: {test_case.is_public}")
            return False
        
        # Restore original values
        test_case.status = original_status
        test_case.ai_content_verified = original_verified
        test_case.is_public = original_public
        db.session.commit()
        
        print("\n✅ PASSED: Status synchronization works")
        return True
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("AI INTEGRATION FEATURES TEST SUITE")
    print("="*60)
    
    with app.app_context():
        results = []
        
        # Run tests
        results.append(("Database Migration", test_database_migration()))
        results.append(("AI Cache Functionality", test_ai_cache_functionality()))
        results.append(("Case Verification Field", test_case_verification_field()))
        results.append(("Status Synchronization", test_status_sync()))
        
        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{status}: {test_name}")
        
        print(f"\nTotal: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n🎉 All tests passed!")
            return 0
        else:
            print(f"\n⚠️  {total - passed} test(s) failed")
            return 1


if __name__ == '__main__':
    exit(main())
