# FRCR Revision App - Master Planning Index

> **Last Updated:** January 31, 2026  
> **Status:** Active Development  
> **Total Plans:** 7 Feature Areas

---

## Overview

This document serves as the master index for all planned features and enhancements for the FRCR Revision application. Plans are ordered by priority: **quick wins first**, progressing to **more complex and disruptive features**.

---

## Priority Order Summary

| Priority | Feature | Complexity | Impact | Status |
|----------|---------|------------|--------|--------|
| 1 | TCIA Viewer Fix | Low | Medium | Planned |
| 2 | ClinicalKey Integration | Medium | Medium | Planned |
| 3 | Reference Image Curation | Medium | High | Planned |
| 4 | TNM Calculator (Standalone) | High | Very High | Planned |
| 5 | Business Model Implementation | High | Critical | Planned |
| 6 | AI/RAG Knowledge System | Very High | Transformative | Planned |
| 7 | Case DICOM Viewer | Medium-High | High | Planned |

---

## Plan 1: TCIA Viewer Fix

**Priority:** 1 (Quick Win)  
**Complexity:** Low  
**Estimated Effort:** 1-2 days  
**Dependencies:** None

### Summary
Fix TCIA (The Cancer Imaging Archive) viewer integration issues including viewer URL construction, auto-search on tab open, and fallback viewer options.

### Key Deliverables
- Fix viewer URL construction with collection context
- Add auto-search when TCIA tab is opened
- Provide fallback viewer options (NBIA, OHIF)
- Add debug logging for troubleshooting

### Files Affected
- `tcia_service.py`
- `resources_routes.py`
- `templates/view_case.html`

### Plan Document
📄 **Location:** `.cursor/plans/tcia_viewer_fix_6badd15c.plan.md`

---

## Plan 2: ClinicalKey Integration

**Priority:** 2 (Easy Win)  
**Complexity:** Medium  
**Estimated Effort:** 3-5 days  
**Dependencies:** None

### Summary
Implement ClinicalKey integration following the existing ScienceDirect pattern. Admin users get auto-login capability, while students must manually log in with connection validity tracking (1 year for admin, 3 months for students).

### Key Deliverables
- Database schema: Add ClinicalKey columns to User model
- Backend: Create `clinicalkey_service.py` and API routes
- Admin UI: Add ClinicalKey section to `edit_case.html`
- Student UI: Add ClinicalKey tab to `view_case.html`

### Files Affected
- `models.py`
- `resources_routes.py`
- `clinicalkey_service.py` (new)
- `templates/edit_case.html`
- `templates/view_case.html`

### Plan Document
📄 **Location:** `.cursor/plans/clinicalkey_integration_f70f003a.plan.md`

---

## Plan 3: Reference Image Curation Feature

**Priority:** 3 (High Value)  
**Complexity:** Medium  
**Estimated Effort:** 2-3 weeks  
**Dependencies:** Google Custom Search API setup

### Summary
Implement an admin-side AI-assisted reference image curation system that uses Google Custom Search + Claude AI to find, analyze, and store relevant radiology images for each case. Images are curated once by admin and displayed instantly to all students.

### Key Deliverables
- Database: `CaseReferenceImage` model
- Backend: Google Search service, AI image analysis service
- Admin UI: Search and select reference images during case creation
- Student UI: Display curated images in Anatomy tab

### Key Benefits
- One-time cost per case (vs. per-student search)
- Consistent, quality-controlled content
- Faster load times for students

### Files Affected
- `models.py`
- `google_search_service.py` (new)
- `ai_image_service.py` (new)
- `reference_image_routes.py` (new)
- `templates/edit_case.html`
- `templates/view_case.html`

### Plan Document
📄 **Location:** `.cursor/plans/reference_image_curation_feature_11c6d6e5.plan.md`

---

## Plan 4: TNM Calculator (Standalone Module)

**Priority:** 4 (Core Feature)  
**Complexity:** High  
**Estimated Effort:** 3-4 weeks  
**Dependencies:** Existing TNM JSON data

### Summary
Build a clinical-grade, deterministic, rule-based TNM staging calculator as a standalone reusable module. Features full explainability, data-driven rules from JSON, and no AI dependency. Designed for clinical practice and embeddable in other applications.

### Key Principles
- **Deterministic:** No AI or probabilistic logic
- **Explainable:** Every output includes complete reasoning
- **Data-driven:** All rules from JSON (no hard-coding)
- **Reusable:** Standalone module, callable as library or API
- **Safe:** Clear disclaimers, versioned rules, fully testable

### Key Deliverables
- Core engine: `TNMCalculator` class
- Rule system: JSON schema and cancer-specific rules
- Explainer: Human-readable staging explanations
- UI: Standalone calculator page
- Tests: Comprehensive test suite with known staging cases

### Files Affected
- `tnm_calculator/` (new module)
- `templates/tnm_calculator.html` (new)
- `static/tnm-calculator.js` (new)

### Plan Document
📄 **Location:** `.cursor/plans/tnm_calculator_standalone_module_d75d258d.plan.md`

### Implemented – Backend Documentation
📄 **Code flow & excluded slugs:** [TNM_CALCULATOR_BACKEND.md](../TNM_CALCULATOR_BACKEND.md)

---

## Plan 5: Business Model Implementation

**Priority:** 5 (Revenue Critical)  
**Complexity:** High  
**Estimated Effort:** 3-4 weeks  
**Dependencies:** Payment gateway accounts (Razorpay, Stripe)

### Summary
Implement a freemium business model with 7-day trial, tiered subscriptions (monthly/annual), dual-currency support (INR via Razorpay, GBP via Stripe), and progressive upgrade CTAs.

### Tier Structure

| Tier | Price (INR) | Price (GBP) | Access |
|------|-------------|-------------|--------|
| Trial | Free / 7 days | Free / 7 days | Full access |
| Free | Free | Free | Unlimited search, 3 case reads/month |
| Monthly | ₹999/mo | £9.99/mo | Unlimited access |
| Annual | ₹6,499/yr | £79.99/yr | Unlimited + priority |

### Key Deliverables
- Payment integration (Razorpay + Stripe)
- Subscription management
- Trial period handling
- Upgrade prompts and paywalls
- Billing history and invoices

### Files Affected
- `models.py` (subscription enhancements)
- `payment_routes.py` (new)
- `subscription_service.py` (new)
- `templates/pricing.html` (new)
- `templates/base.html` (upgrade CTAs)

### Plan Document
📄 **Location:** `docs/plans/BUSINESS_MODEL_PLAN.md`

---

## Plan 6: AI/RAG Knowledge System

**Priority:** 6 (Transformative)  
**Complexity:** Very High  
**Estimated Effort:** 8-12 weeks  
**Dependencies:** Vector database, all case content populated, Claude API

### Summary
Build an AI-powered knowledge system using RAG (Retrieval-Augmented Generation) that leverages the app's comprehensive case database, TNM staging data, and learning content to provide intelligent tutoring, case-based reasoning, differential diagnosis assistance, and personalized learning recommendations.

### Key Features
1. **AI Case Companion:** Contextual assistant on every case page
2. **Similar Case Finder:** Semantic search for related cases
3. **Differential Diagnosis Assistant:** AI-powered differentials grounded in app data
4. **Personalized Study Planner:** Learning recommendations based on user history
5. **AI Tutor (Socratic):** Interactive learning through guided questions

### Key Principles
- **Grounded:** All responses cite specific cases in the database
- **Safe:** Clinical disclaimers on all outputs
- **Personalized:** Adapts to user's learning history
- **Validated:** Citation checking and content validation

### Key Deliverables
- Vector database (pgvector in Supabase)
- Embedding pipeline for all cases
- RAG query pipeline
- AI companion chat interface
- Study planner dashboard
- Socratic tutor conversation flow

### Files Affected
- `ai_service/` (new module)
- `ai_routes.py` (new)
- `templates/ai_companion.html` (new)
- `static/ai-chat.js` (new)
- Database: Vector embedding tables

### Plan Document
📄 **Location:** `.cursor/plans/ai_rag_knowledge_system_38b14f76.plan.md`

---

## Plan 7: Case DICOM Viewer

**Priority:** 7 (Content Enhancement)  
**Complexity:** Medium-High  
**Estimated Effort:** ~12 days  
**Dependencies:** Azure app registration, OneDrive account  
**Branch:** `feature/case-dicom-viewer`

### Summary
Build a standalone, exportable module (`case_dicom_viewer`) that links OneDrive folders to cases via OAuth and share links, and displays image stacks (JPEG) in a DICOM-like viewer using Cornerstone3D. Admin adds image stack in edit_case; students view in view_case sidebar tab.

### Key Deliverables
- OneDrive OAuth and folder listing (share link parsing, Graph API)
- Cornerstone3D viewer with plan selection (axial, sagittal, etc.) and slice scrolling
- Admin UI: "Upload Image Stack" button and OneDrive link modal
- Student UI: Image Stack tab with viewer component
- Standalone module structure for export to other apps

### Files Affected
- `case_dicom_viewer/` (new module)
- `models.py` (CaseImageStack)
- `app.py` (blueprint registration)
- `templates/edit_case.html`
- `templates/view_case.html`

### Plan Document
📄 **Location:** `docs/plans/CASE_DICOM_VIEWER_PLAN.md`

---

## Implementation Roadmap

```
Phase 1: Quick Wins (Week 1-2)
├── TCIA Viewer Fix
└── ClinicalKey Integration

Phase 2: Content Enhancement (Week 3-5)
├── Reference Image Curation
└── Case DICOM Viewer

Phase 3: Core Features (Week 6-9)
├── TNM Calculator
└── Business Model Implementation

Phase 4: AI Transformation (Week 10-20)
└── AI/RAG Knowledge System
```

---

## Style and Branding Requirements

**All implementations MUST follow existing app design patterns:**

### Color Palette
| Color | Hex | Usage |
|-------|-----|-------|
| Primary Blue | `#5E899E` | Headers, primary actions, anatomy |
| Success Green | `#28a745` | Connected states, relevant badges |
| Warning Orange | `#ffc107` | Expired states, warnings |
| Danger Red | `#dc3545` | Errors, M1/Stage IV |
| Info Blue | `#17a2b8` | Hints, explanations |
| AI Purple | `#6f42c1` | AI-generated content |

### UI Standards
- Bootstrap 5 classes consistently
- FontAwesome 5 icons
- Existing tab/card/modal patterns
- Console logging with `[FEATURE]` prefixes
- Error handling with `showFlash()` function

### Code Standards
- Follow existing Python patterns (Flask, SQLAlchemy)
- JavaScript: async/await, ES6+
- Jinja2 templating conventions
- Comment style matching existing code

---

## Plan Document Locations

| Plan | Cursor Plans Folder | Docs Folder |
|------|---------------------|-------------|
| TCIA Viewer Fix | `.cursor/plans/tcia_viewer_fix_*.plan.md` | - |
| ClinicalKey Integration | `.cursor/plans/clinicalkey_integration_*.plan.md` | - |
| Reference Image Curation | `.cursor/plans/reference_image_curation_*.plan.md` | - |
| TNM Calculator | `.cursor/plans/tnm_calculator_standalone_*.plan.md` | - |
| Business Model | - | `docs/plans/BUSINESS_MODEL_PLAN.md` |
| AI/RAG System | `.cursor/plans/ai_rag_knowledge_system_*.plan.md` | - |
| Case DICOM Viewer | - | `docs/plans/CASE_DICOM_VIEWER_PLAN.md` |

---

## How to Use This Index

1. **Starting a new feature:** Check this index for priority order
2. **Before implementing:** Read the full plan document
3. **During implementation:** Follow style/branding guidelines
4. **After completion:** Update status in this index
5. **Adding new plans:** Add to this index with appropriate priority

---

## Version History

| Date | Change | Author |
|------|--------|--------|
| 2026-01-29 | Initial master index created | AI Assistant |
| 2026-01-31 | Added Case DICOM Viewer plan | AI Assistant |

