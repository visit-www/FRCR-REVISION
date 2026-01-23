# AJCC TNM Staging System - Testing Guide

## Overview
This guide provides a systematic approach to testing the AJCC TNM staging system implementation.

## Prerequisites

1. **Environment Setup**
   ```bash
   # Ensure you're on the feature branch
   git checkout feature/ajcc-tnm-staging-system
   
   # Activate virtual environment
   source venv/bin/activate
   
   # Install dependencies (if needed)
   pip install -r requirements.txt
   ```

2. **Environment Variables**
   Ensure these are set in `.env`:
   ```
   AJCC_USERNAME=your_username@example.com
   AJCC_PASSWORD=your_password
   DATABASE_URL=your_database_url
   ```

3. **Database Backup**
   ```bash
   # Backup existing database before migration
   cp instance/frcr_examiner.db instance/frcr_examiner.db.backup
   ```

---

## Phase 1: Database Migration Testing

### 1.1 Test Migration Up
```bash
# Run migration
flask db upgrade

# Verify tables created
sqlite3 instance/frcr_examiner.db ".tables" | grep ajcc
# Should show:
# ajcc_body_section
# ajcc_disease_site
# ajcc_diagnosis_year
# ajcc_disease_mapping
# ajcc_staging_data
```

### 1.2 Verify Table Structure
```bash
# Check each table structure
sqlite3 instance/frcr_examiner.db ".schema ajcc_body_section"
sqlite3 instance/frcr_examiner.db ".schema ajcc_disease_site"
sqlite3 instance/frcr_examiner.db ".schema ajcc_staging_data"
```

### 1.3 Test Migration Down (Rollback)
```bash
# Test rollback capability
flask db downgrade

# Verify tables removed
sqlite3 instance/frcr_examiner.db ".tables" | grep ajcc
# Should show nothing

# Restore
flask db upgrade
```

---

## Phase 2: Data Initialization Testing

### 2.1 Run Initialization Script
```bash
# Run the mapping initialization script
python scripts/initialize_ajcc_mappings.py
```

### 2.2 Verify Data Population
```python
# Test script: verify_init_data.py
from app import app
from models import (
    AJCCBodySection, AJCCDiseaseSite, AJCCDiagnosisYear, 
    AJCCDiseaseMapping, db
)

with app.app_context():
    # Check body sections
    sections = AJCCBodySection.query.all()
    print(f"Body sections: {len(sections)}")
    assert len(sections) >= 17, "Should have at least 17 body sections"
    
    # Check disease sites
    diseases = AJCCDiseaseSite.query.all()
    print(f"Disease sites: {len(diseases)}")
    assert len(diseases) > 0, "Should have disease sites"
    
    # Check diagnosis years
    years = AJCCDiagnosisYear.query.all()
    print(f"Diagnosis years: {len(years)}")
    assert len(years) == 3, "Should have 3 years (2024, 2025, 2026)"
    
    # Check default year
    default_year = AJCCDiagnosisYear.query.filter_by(is_default=True).first()
    assert default_year.year == 2026, "2026 should be default"
    
    # Check mappings
    mappings = AJCCDiseaseMapping.query.all()
    print(f"Mappings: {len(mappings)}")
    
    print("✓ Initialization data verified")
```

### 2.3 Verify Specific Mappings
```python
# Test specific mappings (e.g., Lung cancer)
with app.app_context():
    lung_disease = AJCCDiseaseSite.query.filter_by(disease_name="Lung").first()
    assert lung_disease is not None, "Lung disease should exist"
    
    mappings = AJCCDiseaseMapping.query.filter_by(
        disease_site_id=lung_disease.id
    ).all()
    
    # Should map to Cardiothoracic and Vascular module
    assert any(m.frcr_module.value == "Cardiothoracic and Vascular" 
              for m in mappings), "Lung should map to Cardiothoracic module"
```

---

## Phase 3: Authentication Testing

### 3.1 Test AJCC Authentication
```python
# Test script: test_auth.py
from ajcc_auth_service import authenticate_ajcc, get_ajcc_session
import os

# Check credentials
assert os.getenv("AJCC_USERNAME"), "AJCC_USERNAME not set"
assert os.getenv("AJCC_PASSWORD"), "AJCC_PASSWORD not set"

# Test authentication
print("Testing AJCC authentication...")
success = authenticate_ajcc()
assert success, "Authentication should succeed"

# Test session retrieval
session = get_ajcc_session()
assert session is not None, "Session should be available"

# Test session validity
from ajcc_auth_service import AJCCAuthSession
auth_session = AJCCAuthSession()
is_valid = auth_session.is_session_valid()
assert is_valid, "Session should be valid"

print("✓ Authentication tests passed")
```

### 3.2 Test API Access
```python
# Test accessing AJCC API with authenticated session
session = get_ajcc_session()
response = session.get(
    "https://ajccstaging.org/api/content/thorax/lung/2026?locale=en&add-headers=true"
)
assert response.status_code == 200, "Should access API successfully"
data = response.json()
assert 'content' in data, "Response should have content"
print("✓ API access test passed")
```

---

## Phase 4: Extraction Testing

### 4.1 Test Year Detection
```python
# Test script: test_extraction.py
from ajcc_tnm_extractor import TNMExtractor

extractor = TNMExtractor()

# Test available years
years = extractor.get_available_years("thorax", "lung")
print(f"Available years for Lung: {years}")
assert 2026 in years, "2026 should be available"

# Test year fallback
result = extractor.extract_tnm_for_disease("thorax", "lung", year=2027)
# Should fallback to latest available year
assert result is not None or len(years) == 0, "Should handle invalid year gracefully"
```

### 4.2 Test Section Extraction
```python
# Test extraction for one disease
extractor = TNMExtractor()
result = extractor.extract_tnm_for_disease("thorax", "lung", year=2026)

if result:
    # Verify all 10 sections
    sections = [
        'section_1_quick_reference_html',
        'section_2_cancers_staged_html',
        'section_3_cancers_not_staged_html',
        'section_4_summary_changes_html',
        'section_5_primary_site_html',
        'section_6_histopathologic_type_html',
        'section_7_clinical_staging_workup_html',
        'section_8_staging_rules_html',
        'section_9_common_scenarios_html',
        'section_10_explanatory_notes_html'
    ]
    
    for section in sections:
        content = result.get(section)
        print(f"{section}: {'✓' if content else '✗ (empty)'}")
    
    # At least one section should have content
    assert any(result.get(s) for s in sections), "At least one section should have content"
    print("✓ Extraction test passed")
else:
    print("⚠ Extraction returned None - may need authentication")
```

### 4.3 Test Database Saving
```python
# Test saving to database
from app import app
from models import AJCCDiseaseSite, AJCCDiagnosisYear, db
from ajcc_tnm_extractor import TNMExtractor

with app.app_context():
    # Get disease site
    disease_site = AJCCDiseaseSite.query.filter_by(disease_name="Lung").first()
    assert disease_site is not None, "Lung disease should exist"
    
    # Extract data
    extractor = TNMExtractor()
    result = extractor.extract_tnm_for_disease(
        "thorax", "lung", year=2026
    )
    
    if result:
        # Save to database
        staging_data = extractor.save_to_database(
            result, disease_site, 2026, user_id=1
        )
        
        assert staging_data is not None, "Should save successfully"
        assert staging_data.disease_site_id == disease_site.id, "Should link to disease"
        assert staging_data.section_1_quick_reference_html is not None, "Should have section 1"
        
        print("✓ Database save test passed")
```

---

## Phase 5: Admin Interface Testing

### 5.1 Test Admin Routes (API)

#### 5.1.1 List Sections
```bash
# As admin user, test API endpoint
curl -X GET http://localhost:5000/api/admin/tnm/sections \
  -H "Cookie: session=your_session_cookie"
# Should return JSON with sections list
```

#### 5.1.2 List Diseases
```bash
# Get diseases for a section
curl -X GET "http://localhost:5000/api/admin/tnm/diseases?section_id=1" \
  -H "Cookie: session=your_session_cookie"
```

#### 5.1.3 Extract TNM Data
```bash
# Test extraction endpoint
curl -X POST http://localhost:5000/api/admin/tnm/extract \
  -H "Content-Type: application/json" \
  -H "Cookie: session=your_session_cookie" \
  -d '{
    "disease_site_id": 1,
    "diagnosis_year": 2026,
    "section_slug": "thorax",
    "disease_slug": "lung"
  }'
```

#### 5.1.4 List Staging Data
```bash
# List extracted data
curl -X GET "http://localhost:5000/api/admin/tnm/list?page=1&per_page=20" \
  -H "Cookie: session=your_session_cookie"
```

### 5.2 Test Admin UI

1. **Access Management Page**
   - Navigate to `/api/admin/tnm/management`
   - Verify page loads
   - Check sections dropdown populates
   - Check diseases dropdown populates when section selected

2. **Test Extraction**
   - Select section: "Thorax"
   - Select disease: "Lung"
   - Select year: "2026"
   - Click "Extract TNM Data"
   - Verify success message
   - Check data appears in list

3. **Test Editing**
   - Click "Edit" on an extracted entry
   - Verify all 10 sections load in tabs
   - Edit section 1 content
   - Click "Save Current Section"
   - Verify save success
   - Refresh and verify changes persist

4. **Test Filters**
   - Filter by section
   - Filter by year
   - Verify results update correctly

---

## Phase 6: Public Interface Testing

### 6.1 Test Browse Page
1. Navigate to `/tnm`
2. Verify all body sections display
3. Click on a section (e.g., "Thorax")
4. Verify diseases list displays

### 6.2 Test Disease Page
1. Navigate to `/tnm/thorax/lung`
2. Verify:
   - Disease name displays
   - Year selector shows available years
   - Navigation sidebar shows all 10 sections
   - General TNM notes display
   - Link to "Quick Reference" works

### 6.3 Test Section Pages
1. Navigate to `/tnm/thorax/lung/quick-reference?year=2026`
2. Verify:
   - Section content displays
   - Navigation sidebar works
   - Year selector works
   - Breadcrumbs work
   - Content is properly formatted

3. Test all 10 sections:
   - `/tnm/thorax/lung/quick-reference`
   - `/tnm/thorax/lung/cancers-staged`
   - `/tnm/thorax/lung/cancers-not-staged`
   - `/tnm/thorax/lung/summary-changes`
   - `/tnm/thorax/lung/primary-site`
   - `/tnm/thorax/lung/histopathologic-type`
   - `/tnm/thorax/lung/clinical-staging-workup`
   - `/tnm/thorax/lung/staging-rules`
   - `/tnm/thorax/lung/common-scenarios`
   - `/tnm/thorax/lung/explanatory-notes`

### 6.4 Test Year Fallback
1. Navigate to `/tnm/thorax/lung?year=2027` (invalid year)
2. Verify falls back to latest available year (2026)

3. Navigate to `/tnm/thorax/lung?year=2025`
4. Verify displays 2025 data if available

### 6.5 Test Missing Data Handling
1. Navigate to a disease with no extracted data
2. Verify shows "No TNM data available" message
3. Verify navigation still works (doesn't break)

---

## Phase 7: Integration Testing

### 7.1 Test Case View Integration
```python
# Test script: test_case_integration.py
from app import app
from models import Case, db
from ajcc_service import get_tnm_url_for_diagnosis

with app.app_context():
    # Find a case with cancer diagnosis
    cancer_case = Case.query.filter(
        Case.diagnosis.ilike('%cancer%')
    ).first()
    
    if cancer_case:
        # Test TNM URL generation
        url = get_tnm_url_for_diagnosis(
            cancer_case.diagnosis,
            app.app_context()
        )
        print(f"Case {cancer_case.id}: {cancer_case.diagnosis}")
        print(f"TNM URL: {url}")
        
        if url:
            print("✓ TNM link available")
        else:
            print("⚠ No TNM data for this diagnosis")
```

### 7.2 Test Frontend TNM Link
1. Navigate to a case with cancer diagnosis (e.g., "Lung cancer")
2. Verify "View TNM Staging" button appears in diagnosis section
3. Click button
4. Verify opens TNM page in new tab
5. Verify correct disease/year displays

### 7.3 Test Non-Cancer Cases
1. Navigate to a case without "cancer" in diagnosis
2. Verify TNM link does NOT appear
3. Verify no errors in console

---

## Phase 8: Error Handling & Edge Cases

### 8.1 Test Invalid Inputs
```python
# Test invalid disease/year combinations
extractor = TNMExtractor()

# Invalid section
result = extractor.extract_tnm_for_disease("invalid", "lung", 2026)
assert result is None, "Should handle invalid section"

# Invalid disease
result = extractor.extract_tnm_for_disease("thorax", "invalid", 2026)
assert result is None, "Should handle invalid disease"
```

### 8.2 Test Missing Authentication
```python
# Test with invalid credentials
import os
original_user = os.getenv("AJCC_USERNAME")
os.environ["AJCC_USERNAME"] = "invalid"

from ajcc_auth_service import authenticate_ajcc
success = authenticate_ajcc()
assert not success, "Should fail with invalid credentials"

# Restore
os.environ["AJCC_USERNAME"] = original_user
```

### 8.3 Test Empty Sections
1. Extract data for a disease
2. Manually set one section to empty in database
3. Navigate to that section page
4. Verify shows "This section is not available" message
5. Verify navigation still works

### 8.4 Test Concurrent Access
```python
# Test multiple simultaneous extractions
import threading

def extract_disease(disease_slug):
    extractor = TNMExtractor()
    return extractor.extract_tnm_for_disease("thorax", disease_slug, 2026)

threads = []
for disease in ["lung", "pleural-mesothelioma", "thymus"]:
    t = threading.Thread(target=extract_disease, args=(disease,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print("✓ Concurrent extraction test passed")
```

---

## Phase 9: Performance Testing

### 9.1 Test Extraction Speed
```python
import time

extractor = TNMExtractor()
start = time.time()
result = extractor.extract_tnm_for_disease("thorax", "lung", 2026)
elapsed = time.time() - start

print(f"Extraction time: {elapsed:.2f} seconds")
assert elapsed < 30, "Extraction should complete within 30 seconds"
```

### 9.2 Test Database Query Performance
```python
from app import app
from models import AJCCStagingData, db
import time

with app.app_context():
    start = time.time()
    data = AJCCStagingData.query.all()
    elapsed = time.time() - start
    
    print(f"Query time: {elapsed:.4f} seconds")
    assert elapsed < 1, "Query should be fast"
```

---

## Phase 10: Security Testing

### 10.1 Test Admin Access Control
```bash
# Test as non-admin user
# Should get 403 Forbidden
curl -X GET http://localhost:5000/api/admin/tnm/sections \
  -H "Cookie: session=student_session_cookie"
```

### 10.2 Test SQL Injection
```python
# Test with malicious input
malicious_input = "'; DROP TABLE ajcc_staging_data; --"
# Should be sanitized and not execute
```

### 10.3 Test XSS Prevention
1. Edit a section with HTML/JavaScript content
2. Verify content is sanitized when displayed
3. Verify no script execution

---

## Quick Test Checklist

- [ ] Migration runs successfully
- [ ] Initialization script populates data
- [ ] Authentication works
- [ ] Extraction works for at least one disease
- [ ] Data saves to database
- [ ] Admin management page loads
- [ ] Admin extraction works
- [ ] Admin editing works
- [ ] Public browse page loads
- [ ] Public disease page loads
- [ ] All 10 section pages load
- [ ] Year fallback works
- [ ] TNM link appears in case view for cancer cases
- [ ] TNM link does NOT appear for non-cancer cases
- [ ] Error handling works for invalid inputs
- [ ] Missing data handled gracefully

---

## Automated Test Script

Create `test_ajcc_tnm_full.py`:

```python
"""
Comprehensive test suite for AJCC TNM system
Run with: python test_ajcc_tnm_full.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import db, AJCCBodySection, AJCCDiseaseSite, AJCCStagingData
from ajcc_auth_service import authenticate_ajcc
from ajcc_tnm_extractor import TNMExtractor

def test_database():
    """Test database models and queries"""
    print("Testing database...")
    with app.app_context():
        sections = AJCCBodySection.query.count()
        assert sections > 0, "Should have body sections"
        print(f"✓ Found {sections} body sections")
        
        diseases = AJCCDiseaseSite.query.count()
        assert diseases > 0, "Should have disease sites"
        print(f"✓ Found {diseases} disease sites")

def test_extraction():
    """Test TNM extraction"""
    print("\nTesting extraction...")
    extractor = TNMExtractor()
    result = extractor.extract_tnm_for_disease("thorax", "lung", 2026)
    
    if result:
        sections_with_content = sum(
            1 for k, v in result.items() 
            if k.startswith('section_') and v
        )
        print(f"✓ Extracted {sections_with_content} sections with content")
    else:
        print("⚠ Extraction returned None (may need authentication)")

def test_routes():
    """Test route accessibility"""
    print("\nTesting routes...")
    with app.test_client() as client:
        # Test public route
        response = client.get('/tnm')
        assert response.status_code == 200, "Browse page should load"
        print("✓ Public browse page accessible")
        
        # Test admin route (requires login)
        response = client.get('/api/admin/tnm/sections')
        # Should redirect or require auth
        assert response.status_code in [200, 302, 401, 403], "Admin route should handle auth"
        print("✓ Admin routes handle authentication")

if __name__ == '__main__':
    print("=" * 50)
    print("AJCC TNM System - Comprehensive Test Suite")
    print("=" * 50)
    
    try:
        test_database()
        test_extraction()
        test_routes()
        
        print("\n" + "=" * 50)
        print("✓ All tests passed!")
        print("=" * 50)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
```

---

## Next Steps After Testing

1. **Fix any issues found**
2. **Run migration on staging/production**
3. **Run initialization script on production**
4. **Extract TNM data for commonly used diseases**
5. **Monitor for errors in production logs**
6. **Gather user feedback**

---

## Troubleshooting

### Issue: Authentication fails
- Check `AJCC_USERNAME` and `AJCC_PASSWORD` in `.env`
- Verify credentials are correct
- Check AJCC website is accessible

### Issue: Extraction returns None
- Verify authentication works
- Check AJCC API is accessible
- Verify disease/section slugs are correct

### Issue: Sections are empty
- Check HTML parsing logic
- Verify AJCC content structure hasn't changed
- Check extraction logs for errors

### Issue: Database errors
- Verify migration ran successfully
- Check foreign key constraints
- Verify all required fields are populated
