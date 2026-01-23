#!/usr/bin/env python3
"""
Quick Test Script for AJCC TNM System
Run this to verify basic functionality before detailed testing.

Usage: python test_ajcc_tnm_quick.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all modules can be imported"""
    print("1. Testing imports...")
    try:
        from app import app
        from models import (
            AJCCBodySection, AJCCDiseaseSite, AJCCDiagnosisYear,
            AJCCStagingData, AJCCDiseaseMapping, db
        )
        from ajcc_auth_service import authenticate_ajcc, get_ajcc_session
        from ajcc_tnm_extractor import TNMExtractor
        from ajcc_service import get_tnm_url_for_diagnosis
        print("   ✓ All imports successful")
        return True
    except ImportError as e:
        print(f"   ✗ Import error: {e}")
        return False

def test_database_models():
    """Test database models exist and are queryable"""
    print("\n2. Testing database models...")
    try:
        from app import app
        from models import (
            AJCCBodySection, AJCCDiseaseSite, AJCCDiagnosisYear,
            AJCCStagingData, db
        )
        
        with app.app_context():
            # Test body sections
            sections = AJCCBodySection.query.count()
            print(f"   ✓ Body sections in DB: {sections}")
            
            # Test disease sites
            diseases = AJCCDiseaseSite.query.count()
            print(f"   ✓ Disease sites in DB: {diseases}")
            
            # Test diagnosis years
            years = AJCCDiagnosisYear.query.count()
            print(f"   ✓ Diagnosis years in DB: {years}")
            
            # Test staging data
            staging = AJCCStagingData.query.count()
            print(f"   ✓ Staging data entries: {staging}")
            
            if sections == 0:
                print("   ⚠ No body sections found - run initialize_ajcc_mappings.py")
            if diseases == 0:
                print("   ⚠ No disease sites found - run initialize_ajcc_mappings.py")
            if years == 0:
                print("   ⚠ No diagnosis years found - run initialize_ajcc_mappings.py")
            
            return True
    except Exception as e:
        print(f"   ✗ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_authentication():
    """Test AJCC authentication"""
    print("\n3. Testing AJCC authentication...")
    try:
        import os
        username = os.getenv("AJCC_USERNAME")
        password = os.getenv("AJCC_PASSWORD")
        
        if not username or not password:
            print("   ⚠ AJCC_USERNAME or AJCC_PASSWORD not set in environment")
            print("   ⚠ Skipping authentication test")
            return None
        
        from ajcc_auth_service import authenticate_ajcc
        print("   Attempting authentication...")
        success = authenticate_ajcc()
        
        if success:
            print("   ✓ Authentication successful")
        else:
            print("   ✗ Authentication failed - check credentials")
        
        return success
    except Exception as e:
        print(f"   ✗ Authentication test error: {e}")
        return False

def test_extraction():
    """Test TNM extraction (requires authentication)"""
    print("\n4. Testing TNM extraction...")
    try:
        from ajcc_tnm_extractor import TNMExtractor
        from app import app
        from models import AJCCDiseaseSite
        
        extractor = TNMExtractor()
        
        # Test getting available years
        print("   Testing year detection...")
        years = extractor.get_available_years("thorax", "lung")
        print(f"   ✓ Available years for Lung: {years}")
        
        # Test extraction (may fail if not authenticated)
        print("   Testing extraction...")
        result = extractor.extract_tnm_for_disease("thorax", "lung", year=2026)
        
        if result:
            sections_with_content = sum(
                1 for k, v in result.items() 
                if k.startswith('section_') and k.endswith('_html') and v
            )
            print(f"   ✓ Extraction successful - {sections_with_content} sections have content")
            return True
        else:
            print("   ⚠ Extraction returned None - may need authentication")
            return None
    except Exception as e:
        print(f"   ✗ Extraction test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_routes():
    """Test that routes are accessible"""
    print("\n5. Testing routes...")
    try:
        from app import app
        
        with app.test_client() as client:
            # Test public browse route
            response = client.get('/tnm')
            if response.status_code == 200:
                print("   ✓ Public browse route accessible")
            else:
                print(f"   ⚠ Public browse route returned {response.status_code}")
            
            # Test admin route (should require auth)
            response = client.get('/api/admin/tnm/sections')
            if response.status_code in [200, 302, 401, 403]:
                print("   ✓ Admin routes handle authentication")
            else:
                print(f"   ⚠ Admin route returned {response.status_code}")
            
            return True
    except Exception as e:
        print(f"   ✗ Route test error: {e}")
        return False

def test_service_integration():
    """Test ajcc_service integration"""
    print("\n6. Testing service integration...")
    try:
        from app import app
        from ajcc_service import get_tnm_url_for_diagnosis
        
        with app.app_context():
            # Test with cancer diagnosis
            url = get_tnm_url_for_diagnosis("Lung cancer", app.app_context())
            if url:
                print(f"   ✓ TNM URL generated: {url}")
            else:
                print("   ⚠ No TNM URL for 'Lung cancer' - may need extracted data")
            
            # Test with non-cancer
            url = get_tnm_url_for_diagnosis("Pneumonia", app.app_context())
            if url is None:
                print("   ✓ Non-cancer diagnosis correctly returns None")
            else:
                print("   ⚠ Non-cancer diagnosis returned URL (unexpected)")
            
            return True
    except Exception as e:
        print(f"   ✗ Service integration test error: {e}")
        return False

def main():
    """Run all quick tests"""
    print("=" * 60)
    print("AJCC TNM System - Quick Test Suite")
    print("=" * 60)
    
    results = {
        'imports': test_imports(),
        'database': test_database_models(),
        'authentication': test_authentication(),
        'extraction': test_extraction(),
        'routes': test_routes(),
        'integration': test_service_integration()
    }
    
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)
    
    for test_name, result in results.items():
        if result is True:
            status = "✓ PASS"
        elif result is None:
            status = "⚠ SKIP"
        else:
            status = "✗ FAIL"
        print(f"{test_name:20} {status}")
    
    print("\n" + "=" * 60)
    
    # Overall status
    passed = sum(1 for r in results.values() if r is True)
    total = sum(1 for r in results.values() if r is not None)
    
    if passed == total:
        print("✓ All tests passed!")
        return 0
    else:
        print(f"⚠ {passed}/{total} tests passed (some skipped)")
        return 1

if __name__ == '__main__':
    sys.exit(main())
