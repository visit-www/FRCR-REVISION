# Data Migration Strategy - Visual Guide & Quick Reference

## 1. System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRCR-EXAMINER BACKUP JSON                    │
│  Contains: Users, ExamSessions, Cases, Images, Q&A, Candidates │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ ImportService.import_from_backup()
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│         IMPORTED_CASE_STAGING TABLE (Temporary)                 │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Status: pending                                          │   │
│  │ - Case #1: Raw diagnosis, Q&A                           │   │
│  │ - Case #2: Raw diagnosis, Q&A                           │   │
│  │ - Case #3: Raw diagnosis, Q&A                           │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────────┘
                         │
      ┌──────────────────┴──────────────────┐
      │                                     │
      ↓                                     ↓
┌──────────────────────┐        ┌──────────────────────┐
│   ADMIN UI PORTAL    │        │  API ENDPOINTS       │
├──────────────────────┤        ├──────────────────────┤
│ Enrichment Form:     │        │ /api/admin/          │
│ - Module dropdown    │        │  enrichment/pending  │
│ - Body Part dropdown │        │ /api/admin/          │
│ - Age Group select   │        │  enrichment/{id}     │
│ - Public toggle      │        │ /api/admin/          │
│ - Notes textarea     │        │  enrichment/{id}/    │
│ [SAVE] [APPROVE]     │        │  enrich              │
└──────────┬───────────┘        └──────────┬───────────┘
           │                               │
           └───────────────┬───────────────┘
                           │
                  Admin enriches cases with:
                  - FRCR Module
                  - Body Part
                  - Age Group (Adult/Pediatric)
                  - is_public flag
                  - Optional notes
                           │
                           ↓
┌──────────────────────────────────────────────────────────────────┐
│         IMPORTED_CASE_STAGING TABLE (Updated)                    │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Status: enriched                                           │  │
│  │ - Case #1: Module=Cardio, Body=Cardiovascular, Adult      │  │
│  │ - Case #2: Module=MSK, Body=Upper Limb, Pediatric        │  │
│  │ - Case #3: Module=GI, Body=Hepatopancreaticobiliary      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  enriched_by_user_id: 1                                         │
│  enriched_at: 2026-01-09 12:34:56                               │
│  enrichment_notes: "Clear diagnosis, good imagery"              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    [Admin Reviews]
                           │
                           ↓
┌──────────────────────────────────────────────────────────────────┐
│         IMPORTED_CASE_STAGING TABLE (Approved)                   │
│                                                                   │
│  Status: enriched → APPROVED                                     │
│  approved_by_user_id: 1                                          │
│  approved_at: 2026-01-09 12:40:00                                │
│  approval_notes: "Looks good, ready for production"              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    PromotionService.promote_case()
                           │
                           ↓
┌──────────────────────────────────────────────────────────────────┐
│                CASE TABLE (Production)                           │
│                                                                   │
│  Now cases are in the main system:                               │
│  - Visible to students                                           │
│  - Organized by module and body part                             │
│  - Searchable and filterable                                     │
│  - Can be used in revision sessions                              │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Flow for Each Case

```
SINGLE CASE JOURNEY:

┌─────────────────────────────────────────────┐
│ FRCR-Examiner JSON                          │
│ {                                           │
│   id: 42,                                   │
│   case_number: 1,                           │
│   diagnosis: "Pneumonia",                   │
│   questions: "What is the diagnosis?",      │
│   answers: "Bacterial pneumonia"            │
│ }                                           │
└─────────────────────┬───────────────────────┘
                      │
                      ↓ ImportService.import_from_backup()
┌─────────────────────────────────────────────┐
│ ImportedCaseStaging (NEW)                   │
│ ├─ enrichment_status: "pending"             │
│ ├─ import_batch_id: "uuid-123"              │
│ ├─ source_system: "frcr_examiner"           │
│ ├─ module: NULL                             │
│ ├─ body_part: NULL                          │
│ ├─ age_group: NULL                          │
│ ├─ is_public: FALSE                         │
│ └─ enrichment_status: "pending"             │
└─────────────────────┬───────────────────────┘
                      │
              Admin opens enrichment form
                      │
                      ↓
┌─────────────────────────────────────────────┐
│ Admin selects:                              │
│ ├─ Module: "Cardiothoracic and Vascular"   │
│ ├─ Body Part: "Lung and Mediastinum"       │
│ ├─ Age Group: "Adult"                      │
│ ├─ is_public: TRUE                         │
│ └─ notes: "Typical case, good teaching"    │
└─────────────────────┬───────────────────────┘
                      │
                      ↓ PUT /api/admin/enrichment/1/enrich
┌─────────────────────────────────────────────┐
│ ImportedCaseStaging (UPDATED)               │
│ ├─ enrichment_status: "enriched"            │
│ ├─ module: "Cardiothoracic and Vascular"   │
│ ├─ body_part: "Lung and Mediastinum"       │
│ ├─ age_group: "Adult"                      │
│ ├─ is_public: TRUE                         │
│ ├─ enriched_by_user_id: 1                  │
│ ├─ enriched_at: 2026-01-09 12:30:00        │
│ └─ enrichment_notes: "Typical case..."     │
└─────────────────────┬───────────────────────┘
                      │
              Admin clicks APPROVE
                      │
                      ↓ POST /api/admin/enrichment/1/approve
┌─────────────────────────────────────────────┐
│ ImportedCaseStaging (APPROVED)              │
│ ├─ enrichment_status: "enriched"            │
│ ├─ approved_by_user_id: 1                  │
│ ├─ approved_at: 2026-01-09 12:35:00        │
│ └─ approval_notes: "Ready for production"  │
└─────────────────────┬───────────────────────┘
                      │
              Admin clicks PROMOTE or
              Bulk promote triggered
                      │
                      ↓ PromotionService.promote_case()
┌─────────────────────────────────────────────┐
│ Case (PRODUCTION)                           │
│ ├─ id: 105 (NEW ID in Case table)          │
│ ├─ case_number: 1                          │
│ ├─ diagnosis: "Pneumonia"                  │
│ ├─ module: "Cardiothoracic and Vascular"   │
│ ├─ body_part: "Lung and Mediastinum"       │
│ ├─ age_group: "Adult"                      │
│ ├─ status: "PUBLISHED"                     │
│ ├─ is_public: TRUE                         │
│ ├─ created_by_user_id: 1                   │
│ └─ created_at: 2026-01-09 12:40:00         │
└─────────────────────┬───────────────────────┘
                      │
              Case now visible to students!
                      │
            ✓ Can search by module
            ✓ Can filter by body part
            ✓ Can sort by age group
            ✓ Appears in revision sessions
            ✓ Can be added to packets
```

---

## 3. Admin Dashboard Views

### View 1: Import Status Dashboard
```
┌──────────────────────────────────────────────────────────────┐
│ 📊 IMPORT & ENRICHMENT STATUS                               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ Latest Import: frcr_examiner_backup_20260109_115350.json    │
│ Batch ID: a1b2c3d4-e5f6-g7h8-i9j0                           │
│ Import Date: Jan 9, 2026 11:53 AM                           │
│                                                              │
│ ┌────────────────────────────────────────────────────────┐  │
│ │ ENRICHMENT PROGRESS                                    │  │
│ ├────────────────────────────────────────────────────────┤  │
│ │ ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  67%     │  │
│ │                                                        │  │
│ │ ✓ Enriched: 67/100 cases                              │  │
│ │ ⧗ Pending:  33/100 cases                              │  │
│ │ ⨯ Rejected: 0/100 cases                               │  │
│ │                                                        │  │
│ │ [ENRICH NEXT] [PROMOTE ALL APPROVED] [VIEW BATCH]     │  │
│ └────────────────────────────────────────────────────────┘  │
│                                                              │
│ NEXT PENDING CASE                                           │
│ ┌────────────────────────────────────────────────────────┐  │
│ │ Case #34                                               │  │
│ │ Diagnosis: Acute myocardial infarction               │  │
│ │ Q: Describe the imaging findings...                   │  │
│ │                                                        │  │
│ │ Module: [ Cardiothoracic & Vascular ▼ ]              │  │
│ │ Body Part: [ Cardiovascular ▼ ]                       │  │
│ │ Age Group: [ Adult ▼ ]                                │  │
│ │ ☑ Public (visible to students)                        │  │
│ │                                                        │  │
│ │ Notes: ________________________                        │  │
│ │                                                        │  │
│ │ [SAVE & NEXT] [SKIP] [REJECT]                         │  │
│ └────────────────────────────────────────────────────────┘  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### View 2: Pending Cases List
```
┌──────────────────────────────────────────────────────────────┐
│ 📋 PENDING ENRICHMENT (33 remaining)                         │
├──────────────────────────────────────────────────────────────┤
│ Case# │ Diagnosis          │ Module │ Body Part │ Status    │
├───────┼────────────────────┼────────┼───────────┼───────────┤
│  34   │ Pneumonia          │  [---] │  [-----]  │ pending   │
│  35   │ Meningitis         │  [---] │  [-----]  │ pending   │
│  36   │ Fracture           │  [---] │  [-----]  │ pending   │
│  37   │ Asthma exacerbation│  [---] │  [-----]  │ pending   │
│  38   │ Appendicitis       │  [---] │  [-----]  │ pending   │
│       │                    │        │           │           │
│ [ENRICH ALL] [BULK REJECT] [EXPORT PENDING]                │
└──────────────────────────────────────────────────────────────┘
```

### View 3: Promotion Review
```
┌──────────────────────────────────────────────────────────────┐
│ ✓ READY FOR PROMOTION (67 enriched cases)                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ READY TO MOVE TO PRODUCTION                                │
│ ┌────────────────────────────────────────────────────────┐  │
│ │ ☑ Case #1  - Pneumonia                                │  │
│ │ ☑ Case #2  - Meningitis                               │  │
│ │ ☑ Case #3  - Fracture                                 │  │
│ │ ... (67 total)                                        │  │
│ │                                                        │  │
│ │ All required fields populated:                         │  │
│ │ ✓ Module assigned                                     │  │
│ │ ✓ Body part assigned                                  │  │
│ │ ✓ Age group assigned                                  │  │
│ │ ✓ Public visibility set                               │  │
│ │                                                        │  │
│ │ [PROMOTE ALL 67] [PROMOTE SELECTED] [DESELECT ALL]    │  │
│ └────────────────────────────────────────────────────────┘  │
│                                                              │
│ After promotion, these cases will appear in:                │
│ • Student revision sessions                                │
│ • Case search/filtering                                    │
│ • Module organization                                      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. State Machine Diagram

```
                    ┌─────────────────┐
                    │   NEW IMPORT    │
                    └────────┬────────┘
                             │
                             ↓
                    ┌─────────────────┐
                    │  PENDING        │◄──┐
                    │  enrichment_    │   │
                    │  status='pending'│   │
                    └────────┬────────┘   │
                             │           │
                    [Admin skips]─────────┘
                             │
                             ↓
                    ┌─────────────────┐
              ┌────►│  IN_PROGRESS    │
              │     │  enrichment_    │
              │     │  status='in_    │
              │     │  progress'      │
              │     └────────┬────────┘
              │              │
    [Admin clicks]    [Admin completes]
    [ENRICH]              enrichment
              │              │
              └──────────────┘
                             │
                             ↓
                    ┌─────────────────┐
              ┌────►│  ENRICHED       │
              │     │  enrichment_    │
              │     │  status=        │
              │     │  'enriched'     │
              │     └────────┬────────┘
              │              │
    [Incomplete]      [Complete: all fields]
              │              │
              │         [Admin approves]
              │              │
              │              ↓
              │     ┌─────────────────┐
              │     │  APPROVED       │
              │     │  approved_at    │
              │     │  set            │
              │     └────────┬────────┘
              │              │
              │         [Promote]
              │              │
              │              ↓
              │     ┌─────────────────┐
              │     │  PROMOTED       │
              │     │  Case created   │
              │     │  in production  │
              │     └─────────────────┘
              │
    [Admin clicks     
     REJECT]          ┌─────────────────┐
              └──────►│  REJECTED       │
                      │  enrichment_    │
                      │  status=        │
                      │  'rejected'     │
                      └─────────────────┘
```

---

## 5. Key Attributes in ImportedCaseStaging

```
RAW DATA (From FRCR-Examiner):
├─ original_id           : Integer    | Original case ID in examiner DB
├─ case_number           : Integer    | Case number (1, 2, 3...)
├─ diagnosis             : Text       | Patient diagnosis/summary
├─ questions             : Text       | Exam questions
├─ answers               : Text       | Answers provided
└─ discussion            : Text       | Teaching discussion

ENRICHMENT METADATA (Admin-added):
├─ module                : FRCRModule | CARDIOTHORACIC_VASCULAR, MSK, GI, etc.
├─ body_part             : BodyPart   | CARDIOVASCULAR, LUNG_MEDIASTINUM, etc.
├─ age_group             : AgeGroup   | ADULT or PEDIATRIC
└─ is_public             : Boolean    | TRUE = visible to students, FALSE = hidden

ENRICHMENT TRACKING:
├─ enrichment_status     : String     | pending, in_progress, enriched, rejected
├─ enriched_by_user_id   : Integer    | Which admin enriched it
├─ enriched_at           : DateTime   | When enriched
└─ enrichment_notes      : Text       | Admin notes during enrichment

APPROVAL WORKFLOW:
├─ approved_by_user_id   : Integer    | Which admin approved
├─ approved_at           : DateTime   | When approved
└─ approval_notes        : Text       | QA comments

BATCH TRACKING:
├─ import_batch_id       : String     | UUID grouping all imports from one file
├─ source_system         : String     | 'frcr_examiner' (for future extensibility)
└─ import_timestamp      : DateTime   | When case was imported
```

---

## 6. API Endpoints Summary

```
IMPORT ENDPOINTS:
POST   /api/admin/enrichment/import
       → Upload backup.json → Imports to staging
       
GET    /api/admin/enrichment/stats?batch_id=uuid
       → Get completion stats

ENRICHMENT ENDPOINTS:
GET    /api/admin/enrichment/pending?page=1&per_page=20
       → List cases pending enrichment
       
GET    /api/admin/enrichment/<id>
       → Get full case details for enrichment
       
PUT    /api/admin/enrichment/<id>/enrich
       → Save enrichment (module, body_part, age_group, is_public)
       
POST   /api/admin/enrichment/<id>/approve
       → Approve enriched case for promotion
       
POST   /api/admin/enrichment/<id>/reject
       → Reject case from import

PROMOTION ENDPOINTS:
POST   /api/admin/enrichment/<id>/promote
       → Promote single case to production
       
POST   /api/admin/enrichment/batch/<batch_id>/promote
       → Bulk promote all approved cases in batch
```

---

## 7. Implementation Checklist

### Phase 1: Models & Services
- [ ] Add ImportedCaseStaging to models.py
- [ ] Create migration file
- [ ] Create services/import_service.py with ImportService
- [ ] Add PromotionService to services/import_service.py
- [ ] Add FK relationships in models

### Phase 2: Backend API
- [ ] Create admin_enrichment_routes.py
- [ ] Register blueprint in app.py
- [ ] Test all endpoints with cURL
- [ ] Add proper error handling
- [ ] Add audit logging

### Phase 3: Frontend
- [ ] Create Import component (file upload)
- [ ] Create ImportStatus dashboard
- [ ] Create EnrichmentForm modal/panel
- [ ] Create PendingCasesList table
- [ ] Create PromotionReview screen
- [ ] Add loading states & progress bars

### Phase 4: Testing
- [ ] Test import with sample backup
- [ ] Test enrichment workflow
- [ ] Test approval workflow
- [ ] Test promotion to production
- [ ] Verify cases appear in revision
- [ ] Test bulk operations

---

## 8. Success Metrics

✓ **Import Phase**: 100 cases imported in < 5 seconds
✓ **Enrichment**: Admin can enrich case in < 30 seconds each
✓ **Approval**: Clear visual confirmation of enrichment completion
✓ **Promotion**: Cases available in revision immediately after promotion
✓ **Data Quality**: 0 cases with missing required fields reach production
