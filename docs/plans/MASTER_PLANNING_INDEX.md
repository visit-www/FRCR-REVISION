# FRCR Revision App - Master Planning Index

> **Last Updated:** April 1, 2026
> **Status:** Active Development
> **Total Plans:** 18 Feature Areas

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
| 7 | Case DICOM Viewer | Medium-High | High | **Implemented** |
| 8 | DICOM/MPR Infrastructure | Very High | High | Future (Documented) |
| 9 | R2 Migration and Viewer Upgrade | Medium-High | High | Planned |
| 10 | Railway Migration | Low | High | Ready (Documented) |
| 11 | AI Reporting Assistant | Medium-High | Very High | Planned |
| 12 | TNM Prompt Engineering | Medium | High | Ready to Implement |
| 13 | PHI/PII Protection (5-Layer) | High | Critical | **P0 Done** |
| 14 | SEO & Architecture | Medium-High | High | **Phase 1 Done** |
| 17 | RadInsight Intelligence (User Prefs) | Medium | High | Planned |
| 18 | Vetting Tool (Imaging Protocols) | High | Very High | Planned |

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

### Reference Image: Beyond Google (Sub-plan)
Extend reference image search with Open-i, Bing, and Wikimedia Commons alongside Google.
- **Plan:** [reference_image-beyond-google.md](reference_image-beyond-google.md)
- **Status:** Implemented

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

### Implementation Status
- **Branch:** `main` (merged)
- **Status:** ✅ Fully Implemented
- **Features Completed:**
  - OneDrive OAuth and folder parsing
  - Self-hosted Cornerstone.js v4.x viewer
  - Mouse wheel scroll, zoom, pan, window/level
  - Admin annotation tools (arrow, text, freehand, length, ellipse)
  - Image proxy for CORS/expiry handling
  - CaseImageStack and CaseImageAnnotation models

---

## Plan 8: DICOM/MPR Infrastructure (Future)

**Priority:** 8 (Future Enhancement)  
**Complexity:** Very High  
**Estimated Effort:** 8-12 weeks  
**Dependencies:** DICOM server, Cornerstone3D, significant infrastructure

### Summary
Future plan to enable true Multi-Planar Reconstruction (MPR) viewing. Would require storing original DICOM volumetric data instead of pre-rendered 2D images, plus DICOM server infrastructure (Orthanc or cloud PACS).

### Why Not Now?
- Current pre-rendered 2D approach works well for FRCR education
- Full DICOM/MPR requires significant infrastructure investment
- Cost/benefit ratio not justified for current use case

### Key Requirements (If Implemented)
- DICOM server (Orthanc self-hosted or Google Cloud Healthcare)
- Cornerstone3D with volume rendering
- DICOMweb API proxy layer
- HIPAA compliance considerations

### Files Affected
- New DICOM server infrastructure
- `case_dicom_viewer/` module updates
- Database schema for DICOM metadata

### Plan Document
📄 **Location:** `docs/plans/DICOM_MPR_INFRASTRUCTURE_PLAN.md`

---

## Plan 9: R2 Migration and Viewer Upgrade

**Priority:** 9 (Case DICOM Viewer Upgrade)  
**Complexity:** Medium-High  
**Estimated Effort:** 3-4 weeks  
**Dependencies:** Plan 7 (Case DICOM Viewer), Cloudflare R2 account

### Summary
Migrate case image stacks from OneDrive to Cloudflare R2, upgrade the DICOM viewer for smooth plan switching and session-long caching, and repurpose OneDrive for folder browsing to support Claude AI context. No batch migration script: admins delete existing stacks and re-add via new "Upload from OneDrive to R2" admin UI.

### Key Deliverables
- R2 storage for case images (100-500 MB/case, direct CORS, no proxy)
- Admin UI: "Upload from OneDrive to R2" – browse OneDrive folder, backend downloads and uploads to R2
- Viewer upgrades: preload cancellation on plan switch, Cornerstone cache 2 GB
- OneDrive repurposed for folder browse -> AI context (future)

### Key Points
- No migration script: existing OneDrive-linked stacks are deleted and re-added manually
- Presigned or public R2 URLs; no Vercel Fast Origin Transfer for images
- Cloudinary for general app assets; R2 for DICOM stacks only

### Files Affected
- `case_dicom_viewer/routes.py`, `case_dicom_viewer/r2_service.py` (new)
- `case_dicom_viewer/static/case_dicom_viewer/viewer.js`
- `models.py` (CaseImageStack: storage_backend, r2_config_json)
- `templates/edit_case.html`, `templates/view_case.html`

### Plan Document
📄 **Location:** [docs/plans/R2_MIGRATION_AND_VIEWER_UPGRADE_PLAN.md](R2_MIGRATION_AND_VIEWER_UPGRADE_PLAN.md)

---

## Plan 10: Railway Migration (Infrastructure)

**Priority:** 10 (Infrastructure)
**Complexity:** Low
**Estimated Effort:** ~1 hour
**Dependencies:** None
**Status:** Ready to Execute

### Summary
Migrate hosting from Vercel (Hobby Plan) to Railway to overcome Vercel limitations: 10-second function timeout, daily-only cron jobs. Railway offers persistent services with no timeout limits and configurable cron jobs. All external services (Neon DB, Cloudflare R2, Resend, OneDrive) remain unchanged.

### Why Migrate?
| Issue | Vercel Hobby | Railway |
|-------|-------------|---------|
| Function timeout | 10 seconds | No limit |
| Cron jobs | Daily only | Any frequency |
| Cold starts | Yes | No |

### Key Deliverables
- Create `Procfile` and `runtime.txt`
- Copy environment variables to Railway dashboard
- Update DNS in Namecheap (CNAME to Railway)
- Update Azure App redirect URIs for OneDrive OAuth

### What Stays The Same (No Changes)
- Neon PostgreSQL database
- Cloudflare R2 storage
- Resend email service
- Claude API integration
- Cloudinary for forum images
- All application code

### Files Affected
- `Procfile` (new)
- `runtime.txt` (new)
- `railway.json` (new, optional)

### Plan Document
📄 **Location:** [docs/plans/RAILWAY_MIGRATION_PLAN.md](RAILWAY_MIGRATION_PLAN.md)

---

## Plan 11: AI Reporting Assistant

**Priority:** 11 (Teaching Tool)
**Complexity:** Medium-High
**Estimated Effort:** 2-3 weeks
**Dependencies:** Claude API (already integrated)
**Status:** Planned

### Summary
Build an AI-powered "Algorithmic Reporting Pathway Generator" that creates structured, diagnosis-agnostic decision trees for radiology case interpretation. This teaching tool helps FRCR trainees develop systematic approaches to image interpretation, ensuring no critical findings are missed.

### Core Principles
1. **WORST FIRST** - Life-threatening diagnoses first
2. **SYSTEMATIC BEFORE SPECIFIC** - Complete review before pattern matching
3. **BINARY DECISION LOGIC** - Yes/No branching narrows differential
4. **DIAGNOSIS-AGNOSTIC** - Works for ANY final diagnosis
5. **ACTIONABLE OUTPUT** - Clear impression with confidence levels

### Key Features
- **Standalone Generator** - Input modality/region/indication, get complete decision tree
- **Case Integration** - Generate pathways linked to existing cases
- **Refinement Mode** - Add lab values/clinical data to narrow differential
- **Visual Teaching Cards** - Printable, structured output with Teaching Pearls and Pitfalls

### Supports All Modalities
CT, MRI, X-ray, Ultrasound, Nuclear Medicine, CBCT, PET

### Output Structure (6 Steps)
1. Technical Adequacy & Orientation
2. Red Flags: Critical & Time-Sensitive Findings
3. Systematic Anatomical Review
4. Dominant Abnormality Characterisation (with staging/grading)
5. Differential Diagnosis (ranked)
6. Sample Structured Report

### Key Deliverables
- Database: `AlgorithmicPathway`, `PathwayRefinement` models
- AI Module: `ai_reporting_assistant/` with prompts, generator, routes
- UI: Generator page, pathway viewer, my pathways list
- Case integration button in view_case.html

### Files Affected
- `ai_reporting_assistant/` (new module)
- `models.py` (new models)
- `app.py` (blueprint registration)
- `templates/ai_reporting_assistant/` (new templates)
- `templates/view_case.html` (integration button)

### Plan Document
📄 **Location:** [docs/plans/AI_REPORTING_ASSISTANT_PLAN.md](AI_REPORTING_ASSISTANT_PLAN.md)

---

## Plan 12: TNM Prompt Engineering (Quality Improvement)

**Priority:** 12 (Quality Improvement)
**Complexity:** Medium
**Estimated Effort:** 1-2 days
**Dependencies:** None
**Status:** Ready to Implement

### Summary
Fix the TNM calculator AI generation workflow to consistently produce oropharyngeal-quality calculators. The current prompt produces inferior results (larynx: 741 lines) compared to the gold standard (oropharynx: 1916 lines) because it lacks concrete examples, describes the wrong architecture, and has no quality criteria.

### Root Cause
- Prompt says "based on oropharynx" but provides NO actual example
- Describes "expandable cards" instead of form-based calculator + reference guide
- No automatic stage calculation (user manually selects T/N/M)
- No reasoning output explaining WHY each stage
- No quality criteria checklist

### Key Deliverables
- Replace `CALCULATOR_HTML_PROMPT` with comprehensive prompt including HTML excerpts
- Add `temperature=0.3` and increase `max_tokens` to 20000
- Add `validate_calculator_quality()` function
- Expand `DISEASE_DEFAULTS` with detailed guidance for each cancer

### Quality Criteria for Generated Calculators
- Form-based inputs (checkboxes, number inputs)
- Automatic stage calculation from findings
- Detailed reasoning in results
- 2+ mnemonics, 6+ imaging tips, 6+ pitfalls
- 8-step systematic reading approach
- 1500+ lines of HTML

### Files Affected
- `tnm_calculator/tnm_generator.py` (prompt, API params, validation)
- `scripts/generate_tnm_calculator.py` (disease defaults)

### Plan Document
📄 **Location:** [docs/plans/TNM_PROMPT_ENGINEERING_PLAN.md](TNM_PROMPT_ENGINEERING_PLAN.md)

---

## Plan 13: PHI/PII Protection (5-Layer Hybrid Architecture)

**Priority:** 13 (Security Critical)
**Complexity:** High
**Estimated Effort:** 4-6 weeks (phased)
**Dependencies:** Railway/Cloud Run for Presidio service (P2)
**Status:** P0 Complete, P1–P5 Planned

### Summary
Comprehensive PHI/PII protection system targeting >98% sensitivity and >95% specificity across all 18 HIPAA Safe Harbor identifiers. Combines our existing 24-pattern regex engine with Microsoft Presidio NLP/NER, fuzzy matching, adversarial detection, and quasi-identifier risk scoring. Includes admin audit dashboard, automated alerting, and HIPAA-compliant override workflows.

### 5-Layer Architecture
1. **Regex Engine** (Done) — 24 client+server patterns, fast pre-filter
2. **NLP/NER** (P2) — Microsoft Presidio with spaCy, free-text name/location detection
3. **Fuzzy Matching** (P2) — Levenshtein/Soundex for misspellings and phonetic variants
4. **Adversarial Detection** (P3) — Homoglyph normalization, spacing tricks, OCR noise
5. **Risk Scoring** (P3) — Quasi-identifier combination scoring for re-identification risk

### Implementation Phases
| Phase | Items | Effort | Status |
|-------|-------|--------|--------|
| P0 | Per-match redact/dismiss UI, audit trail | 1 day | **Done** |
| P1 | Regex expansion, medical allowlist | 2 days | Planned |
| P2 | Presidio integration, confidence scoring | 1 week | Planned |
| P3 | Admin dashboard, adversarial detection | 1 week | Planned |
| P4 | Alerting, read-path scanning | 3 days | Planned |
| P5 | BAA tooling, compliance reporting | 2 days | Planned |

### Key Deliverables
- Per-match Redact/Remove/Dismiss with HIPAA audit trail (Done)
- Medical term allowlist to reduce false positives
- Presidio microservice (Railway) with custom recognizers
- Admin audit dashboard with charts, filters, CSV export
- Email/Slack alerting on override spikes
- Read-path (GET response) PHI scanning

### Plan Document
📄 **Location:** [docs/plans/PHI_PROTECTION_PLAN.md](PHI_PROTECTION_PLAN.md)

---

## Plan 14: SEO & Architecture (Master SEO Plan)

**Priority:** 14 (Growth Critical)
**Complexity:** Medium-High
**Estimated Effort:** 6 phases, ~1 week total
**Dependencies:** None (incremental improvements)
**Status:** Phase 1 Done (Public Preview Pages — March 2026)

### Summary
Comprehensive SEO overhaul: Open Graph tags, Twitter Cards, Schema.org JSON-LD (MedicalWebPage, Organization, SoftwareApplication, FAQ), per-page meta descriptions, dynamic sitemap, and content-driven keyword strategy targeting "radiology education platform", "TNM staging calculator", "FRCR revision", and "AI radiology reporting".

### Phase 1 — Public Preview Pages (DONE — March 2026)

Made all educational content publicly accessible with SEO optimization:

**New files created:**
- `public_routes.py` — Blueprint for `/case-library` and `/case-library/<id>` public case routes
- `templates/public_case_library.html` — Public case browse page with filters
- `templates/public_case_preview.html` — Public case preview with content gating
- `templates/partials/_public_cta.html` — Reusable CTA banner for unauthenticated users
- `templates/partials/_schema_medical.html` — Schema.org JSON-LD macros (MedicalWebPage, MedicalCondition, CollectionPage, LearningResource)

**Routes made public (removed @login_required):**
- Reporting Algorithms: `/reporting-algorithms` (browse), `/reporting-template/<slug>` (view)
- Radiology Templates: `/reporting-templates` (browse), `/radiology-template/view/<id>` (view — gated text)
- Radiology Tools: `/incidental-findings/` (browse), `/incidental-findings/<slug>` (view)
- Clinical Protocols: `/radiology-protocols` (browse), `/radiology-protocols/view/<id>` (view — gated content)
- Knowledge Hub: `/knowledge-hub`, `/anatomy-snippets/<slug>`, `/radiology-pearls`

**Content gating strategy:**
- Educational content (algorithms, tools, pearls, anatomy): shown in full
- Patient-adjacent content (cases, protocols, templates): preview + fade overlay + CTA

**SEO enhancements:**
- Schema.org JSON-LD on all public pages (CollectionPage for browse, LearningResource for view)
- Open Graph + Twitter Card meta tags on all public templates
- Per-page meta descriptions on all public templates
- Dynamic sitemap expanded to 100+ URLs (cases, algorithms, templates, anatomy snippets)
- robots.txt updated with Allow directives for all public paths
- noindex added to authenticated-only templates (login, register, dashboard, etc.)
- CSS classes: `.gated-fade-overlay`, `.content-teaser`, `.public-cta-banner`

### Remaining SEO Phases (TODO)
| Phase | Items | Effort |
|-------|-------|--------|
| P2 | Schema.org Organization (base.html), MedicalWebPage + SoftwareApplication (landing.html), FAQPage (pricing) | 1 day |
| P3 | Landing page "Beyond the Shorthand" AI section + keyword optimization | 1 day |
| P4 | Remaining per-page title/description updates, canonical context processor | 1 day |
| P5 | Core Web Vitals optimization, preconnect hints | 1 day |
| P6 | Content strategy, internal linking, keyword monitoring | Ongoing |

### Plan Document
📄 **Location:** [docs/plans/SEO_MASTER_PLAN.md](SEO_MASTER_PLAN.md)

---

## Plan 15: Stripe Payment Gateway Testing

**Priority:** P0 — Revenue-Critical
**Status:** Planned
**Dependencies:** Existing Stripe integration (stripe_routes.py, access_control.py)

### Summary
Comprehensive test plan covering 56+ test cases across 10 suites: signup/trial flows, upgrades with proration, downgrades (end-of-cycle), cancellation, payment failures, edge cases (double-click, idempotency), webhook verification, AI rate limiting, UI/UX, and security.

### Plan Document
📄 **Location:** [docs/plans/STRIPE_TEST_PLAN.md](STRIPE_TEST_PLAN.md)

---

## Plan 16: RadIQ Custom Hospital Protocols (Future Idea)

**Priority:** P3 — Exploratory / Under Evaluation
**Status:** Idea — utility not yet confirmed
**Dependencies:** RadIQ module (radiq_routes.py, ai_radiq.py)

### Summary
Currently RadIQ provides **general best practice** only — all protocols are admin-curated and published. There is no way for users to input their own department or hospital protocols. Adding custom protocol upload would move RadIQ from "study aid" to "essential departmental tool." Requires: hospital/department fields on User model, personal protocol table, filtered context injection in AI prompts. **On hold pending utility assessment.**

---

## Plan 17: RadInsight Intelligence — User Reporting Preferences

**Priority:** 17 (Smart Reporter Enhancement)
**Complexity:** Medium
**Estimated Effort:** Phase 1 ~5.5 hours, Phase 2 ~4 hours
**Dependencies:** Smart Reporter (already built)
**Status:** Planned

### Summary
Track user editing patterns (rejected placeholders, correction rejections, fill-in defaults, language edits) and inject them as preference rules into future Smart Reporter prompts. Reports progressively align with the user's reporting style without compromising clinical quality.

### Architecture
- **Storage:** `reporting_preferences` JSONB column on User model (no new tables)
- **Injection:** ~200 token preference section appended to `unified_ai_assist()` prompt
- **Signals:** Placeholder rejections, correction rejections, fill-in chip defaults (Phase 1); manual text-diff edits (Phase 2)
- **Activation threshold:** 3 occurrences before a rule becomes active
- **Guardrails:** Style/phrasing only (never clinical), 20-rule cap, 60-day staleness decay

### Phases
| Phase | Scope | Effort |
|-------|-------|--------|
| Phase 1 | Explicit signals (button clicks), API endpoint, prompt injection, settings UI | ~5.5 hours |
| Phase 2 | Silent text-diff tracking for language preferences | ~4 hours |

### Files Affected
- `models.py` — Add `reporting_preferences` column
- `app.py` — Migration block
- `ai_smart_reporter.py` — `build_preference_section()`, inject into prompt
- `reporting_routes.py` — `/api/smart-reporter/preferences` endpoint
- `templates/smart_reporter.html` — JS signal capture, opt-in toast
- `templates/settings.html` — Preferences management UI

### Plan Document
📄 **Location:** [docs/plans/RADINSIGHT_INTELLIGENCE_PLAN.md](RADINSIGHT_INTELLIGENCE_PLAN.md)

---

## Implementation Roadmap

```
Phase 1: Quick Wins (Week 1-2)
├── TCIA Viewer Fix
└── ClinicalKey Integration

Phase 2: Content Enhancement (Week 3-5)
├── Reference Image Curation
├── Case DICOM Viewer
└── R2 Migration and Viewer Upgrade

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
| DICOM/MPR Infrastructure | - | `docs/plans/DICOM_MPR_INFRASTRUCTURE_PLAN.md` |
| R2 Migration and Viewer Upgrade | - | `docs/plans/R2_MIGRATION_AND_VIEWER_UPGRADE_PLAN.md` |
| Railway Migration | - | `docs/plans/RAILWAY_MIGRATION_PLAN.md` |
| AI Reporting Assistant | - | `docs/plans/AI_REPORTING_ASSISTANT_PLAN.md` |
| TNM Prompt Engineering | - | `docs/plans/TNM_PROMPT_ENGINEERING_PLAN.md` |
| RadInsight Intelligence | - | `docs/plans/RADINSIGHT_INTELLIGENCE_PLAN.md` |
| Vetting Tool | - | `docs/plans/VETTING_TOOL_PLAN.md` |

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
| 2026-02-02 | Case DICOM Viewer marked implemented; added DICOM/MPR Infrastructure plan | AI Assistant |
| 2026-02-02 | Added R2 Migration and Viewer Upgrade plan (Plan 9); no migration script, admin UI only | AI Assistant |
| 2026-02-05 | Added Railway Migration plan (Plan 10); migrate from Vercel to Railway for better timeouts/cron | AI Assistant |
| 2026-02-05 | Added AI Reporting Assistant plan (Plan 11); diagnosis-agnostic algorithmic pathway generator | AI Assistant |
| 2026-02-05 | Added TNM Prompt Engineering plan (Plan 12); fix AI workflow to produce oropharynx-quality calculators | AI Assistant |
| 2026-03-30 | Added PHI Protection (Plan 13), SEO (Plan 14), Stripe Testing (Plan 15), RadIQ Custom Protocols idea (Plan 16) | AI Assistant |
| 2026-03-31 | SEO Plan 14 Phase 1 complete: public preview pages for all content types, Schema.org macros, dynamic sitemap expansion, content gating | AI Assistant |
| 2026-04-01 | Added RadInsight Intelligence plan (Plan 17); user reporting preference learning for Smart Reporter | AI Assistant |
| 2026-04-01 | Added Vetting Tool plan (Plan 18); structured imaging protocol vetting workflow with safety checklist and protocol library | AI Assistant |

