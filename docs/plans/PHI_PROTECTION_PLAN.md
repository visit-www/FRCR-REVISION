# PHI/PII Protection — Comprehensive Implementation Plan

> **Created:** March 30, 2026
> **Status:** In Progress (P0 complete, P1–P5 planned)
> **Goal:** HIPAA-grade PHI detection with >98% sensitivity, >95% specificity
> **Keyword:** `RADINSIGHTS-PHI-GUARD-2026`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State — What We Have](#2-current-state)
3. [Gap Analysis — What's Missing](#3-gap-analysis)
4. [5-Layer Hybrid Architecture](#4-five-layer-architecture)
5. [Implementation Phases (P0–P5)](#5-implementation-phases)
6. [Phase Details](#6-phase-details)
7. [Presidio Integration Architecture](#7-presidio-integration)
8. [Detection Target Matrix](#8-detection-targets)
9. [False Positive Reduction Strategy](#9-false-positive-strategy)
10. [Admin Audit Dashboard](#10-admin-audit-dashboard)
11. [Alerting System](#11-alerting-system)
12. [Deployment & Infrastructure](#12-deployment)
13. [Cost Projections](#13-costs)
14. [Testing & Validation](#14-testing)
15. [File Inventory](#15-file-inventory)
16. [Version History](#16-version-history)

---

## 1. Executive Summary

RadInsights' PHI Guard protects users from accidentally submitting patient-identifiable information through the app. The system uses a dual-layer architecture (client-side JavaScript + server-side Python middleware) with 24 regex pattern categories.

**Current strengths:** Dual-layer detection, live Smart Reporter scanning, per-match actionable UI, HIPAA-compliant override audit trail.

**Critical gaps:** No NLP/NER engine (names in free text), no admin audit dashboard, no alerting, no Presidio integration, pattern gaps in dates/phones/addresses.

**Target architecture:** 5-layer hybrid pipeline (Regex → NLP/NER → Fuzzy Matching → Adversarial Detection → Risk Scoring) combining our custom regex with Microsoft Presidio server-side.

---

## 2. Current State

### 2.1 Client-Side Detection (`static/pii-guard.js` + `static/pii-guard-ui.js`)

**Architecture (v2 — Apr 2026):** Standalone reusable package. `pii-guard.js` is the detection engine (~400 lines). `pii-guard-ui.js` is the UI module (~350 lines). `pii-guard.css` styles (~310 lines). All 3 files loaded globally via `base.html` for authenticated users.

**Standalone API:**
```javascript
PIIGuard.protect({
    textareas: ['#editorInput'],
    bannerTarget: '.card-header .d-flex',
    apiButtons: ['#btnSubmit', '#btnAnalyse'],
    auditContext: 'smart-reporter'
});
```

| Feature | Status |
|---------|--------|
| 28 regex patterns + HIGH/MEDIUM/LOW tiers | Done (v2) |
| Spell-check-feel highlights (dotted underline overlay) | Done (v2) |
| Per-match click popover (Redact / Remove / Dismiss) | Done (v2) |
| Dismiss flow: checkbox confirmation → mark turns green | Done (v2) |
| Red shield badge in card header (click → bulk actions) | Done (v2) |
| API buttons grayed out while unresolved PII exists | Done (v2) |
| Fetch interceptor (POST/PUT) with X-PII-Override | Done |
| Per-session dismissed items memory | Done |
| Medical allowlist (43 terms), eponym filter | Done (v2) |
| NHS MOD-11 checksum, enhanced NINO/MRN patterns | Done (v2) |
| Skip routes (admin, auth, AI) | Done |

**Integrated in:** Smart Reporter, Vetting, RadIQ

### 2.2 Server-Side Detection (`pii_guard.py`)

**Architecture (v2):** Regex-only (~200 lines). spaCy dropped entirely (eliminates 3-8s Vercel cold starts).

| Feature | Status |
|---------|--------|
| 27 regex patterns with tier info in 422 response | Done (v2) |
| Flask middleware (POST/PUT intercept) | Done |
| 422 response with `pii_blocked: true` + tier info | Done (v2) |
| `X-PII-Override` header bypass | Done |
| Recursive JSON scanning | Done |
| Safe key skip list | Done |

### 2.3 Audit Trail

| Feature | Status |
|---------|--------|
| `PiiOverrideLog` model | Done |
| `action` column (override/dismiss/batch_dismiss) | Done (P0) |
| User ID, flagged types, count, timestamp | Done |
| POST `/api/pii-override-log` | Done |
| GET endpoint for reading logs | **Missing** |
| Admin dashboard UI | **Missing** |
| Alerting on override spikes | **Missing** |

### 2.4 App Integration (v2 — Standalone Package)

PII Guard v2 is a **standalone reusable module**. Each page integrates via a single `PIIGuard.protect()` call:

| Page | Textareas | API Buttons Blocked | Status |
|------|-----------|-------------------|--------|
| Smart Reporter | `#editorInput`, `#editorOutput` | Ask Claude, Finalize, Review, Report Actions | Done (v2) |
| Vetting | `#referralText` | Analyse, Quick Clean, Continue | Done (v2) |
| RadIQ | `#queryInput` | Submit Query | Done (v2) |

**UX Flow (v2):**
1. User types → PII highlighted inline (dotted underline, spell-check-feel)
2. Red shield badge appears in card header with count
3. API buttons **grayed out** while unresolved PII exists
4. Click highlighted PII → popover: Redact / Remove / Dismiss
5. Dismiss → checkbox confirmation → mark turns green
6. Click shield badge → dropdown: Redact All / Remove All / Dismiss All
7. All PII resolved → API buttons re-enabled, badge turns green
8. No gate modal — blocking is done at the button level

### 2.5 Pattern Coverage (24 categories)

| Pattern Type | Count | Notes |
|-------------|-------|-------|
| NHS Number | 3 variants | Standard + short + format-only |
| US SSN | 1 | Standard format |
| MRN / Hospital ID | 1 | Keyword-anchored |
| Date of Birth | 1 | Keyword + DD/MM/YYYY only |
| UK Postcode | 1 | Standard format |
| Phone Number | 4 variants | Keyword, context, international |
| Email Address | 1 | Standard format |
| Patient Name | 7 variants | Title, keyword, age-context, intro |
| Doctor / Clinician Name | 2 variants | Referral keywords, Dr. prefix |
| Possible Patient ID | 1 | Bare 7-10 digit line |
| Patient Age | 1 | `age: 65` format |
| Patient Gender | 1 | `gender: male` format |
| Patient Address | 1 | Keyword-anchored |
| UK National Insurance Number | 1 | Standard format |
| IP Address | 1 | IPv4 |
| Aadhaar Number | 1 | 12-digit groups |
| PAN Card | 1 | Indian format |

---

## 3. Gap Analysis

### 3.1 Detection Gaps

| Category | Current | Missing | Impact |
|----------|---------|---------|--------|
| **Names (free text)** | Only keyword/title-anchored | Names without anchors (`John Smith arrived`), reversed names (`Smith, John`), phonetic variants, OCR noise | High — most common PHI in radiology reports |
| **Dates** | Only `DOB: DD/MM/YYYY` | Written dates (`March 12, 2024`, `15th June`), verbal (`born in early 90s`), mixed (`12.Mar.24`), admission/discharge/death dates | High |
| **Phones** | Keyword-anchored + international | Spelled-out numbers, broken formats, OCR noise | Medium |
| **Addresses** | Only `address:` keyword | Standalone street addresses, landmarks, partial references | Medium |
| **Free-text narrative** | None | Relational (`his wife Sunita`), event-based (`injured near Eiffel Tower`), unique context (`only neurosurgeon in town`) | High |
| **Multi-field re-ID** | None | Quasi-identifier combinations (age + rare disease + location) | Medium |
| **Adversarial** | None | Homoglyphs, spacing tricks, encoding (Base64/hex), OCR noise | Low (educational context) |
| **Additional IDs** | None | Passport numbers, driving licenses, vehicle/device serial numbers, ABHA ID | Low |

### 3.2 HIPAA Safe Harbor — 18 Identifier Compliance

| # | Identifier | Status | Notes |
|---|-----------|--------|-------|
| 1 | Names | Partial | Missing free-text names without anchors |
| 2 | Geographic (below state) | Partial | Only keyword `address:` + UK postcode |
| 3 | Dates (all elements) | Partial | Only DOB format, missing admission/discharge/death |
| 4 | Phone numbers | Done | 4 variants |
| 5 | Fax numbers | Missing | Not detected |
| 6 | Email addresses | Done | |
| 7 | Social Security numbers | Done | US SSN |
| 8 | Medical record numbers | Done | MRN/UHID |
| 9 | Health plan beneficiary numbers | Missing | |
| 10 | Account numbers | Missing | |
| 11 | Certificate/license numbers | Missing | |
| 12 | Vehicle identifiers | Missing | |
| 13 | Device identifiers | Missing | |
| 14 | Web URLs | Missing | |
| 15 | IP addresses | Done | IPv4 |
| 16 | Biometric identifiers | Missing | |
| 17 | Full-face photos | N/A | Text-only system |
| 18 | Any other unique identifier | Partial | Aadhaar, PAN, NINO covered |

**Current coverage: ~10/18 identifiers. Target: 18/18.**

### 3.3 Infrastructure Gaps

| Gap | Description | Priority |
|-----|-------------|----------|
| **No admin audit dashboard** | PII override logs stored in DB but no UI to browse, filter, or export them | P3 |
| **No GET endpoint for logs** | `/api/pii-override-log` is write-only, no read API | P3 |
| **No read-path scanning** | Only POST/PUT intercepted; GET responses with PHI pass through unchecked | P4 |
| **No BAA tooling** | Only Anthropic DPA exists; no formal BAA management or documentation system | P5 |
| **No automated alerting** | No email/Slack notification when override frequency spikes | P4 |
| **No NLP/NER engine** | Regex-only; no machine learning entity recognition for names/locations in free text | P2 |
| **No fuzzy matching** | Misspellings, phonetic variants, OCR noise all missed | P2 |
| **No confidence scoring** | Binary match/no-match; no threshold tuning for sensitivity vs specificity | P2 |
| **No medical allowlist** | Clinical terms (T1, C3-C4, Stage IV) incorrectly flagged as PII | P1 |

---

## 4. 5-Layer Hybrid Architecture

```
User Input (textarea / JSON body)
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  LAYER 1: Regex Engine (Client + Server)            │
│  • Current 24 patterns + expanded library           │
│  • Fast pre-filter, catches structured IDs          │
│  • ~85% sensitivity / ~90% specificity              │
│  Status: DONE (expand patterns in P1)               │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│  LAYER 2: NLP/NER (Server-side — Presidio)          │
│  • Microsoft Presidio with spaCy NER                │
│  • Names, locations, organizations in free text     │
│  • Confidence scoring per match (0.0–1.0)           │
│  • Custom recognizers for medical IDs               │
│  • ~95% sensitivity / ~92% specificity              │
│  Status: PLANNED (P2)                               │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│  LAYER 3: Fuzzy Matching (Server-side)              │
│  • Levenshtein distance for misspellings            │
│  • Soundex/Metaphone for phonetic variants          │
│  • Catches: Jhn Smth, Jon Smyth, Chandigar         │
│  • ~97% sensitivity / ~94% specificity              │
│  Status: PLANNED (P2)                               │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│  LAYER 4: Adversarial Detection (Server-side)       │
│  • Text normalization before scanning               │
│  • Strip homoglyphs (Cyrillic → Latin)              │
│  • Collapse spacing tricks (J o h n → John)         │
│  • Decode Base64/hex-encoded text                   │
│  • OCR noise correction (0→O, 1→I, 5→S)            │
│  Status: PLANNED (P3)                               │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│  LAYER 5: Risk Scoring (Server-side)                │
│  • Combine quasi-identifiers for re-ID risk         │
│  • age + rare disease + location = HIGH risk        │
│  • Flag high re-identification probability          │
│  • User-trained allowlist feedback loop              │
│  • Target: >98% sensitivity / >95% specificity      │
│  Status: PLANNED (P3)                               │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
      ┌───────────────────────┐
      │  DECISION ENGINE      │
      │  score < 0.4 → PASS   │
      │  0.4–0.7 → WARN       │
      │  > 0.7 → BLOCK        │
      └───────────────────────┘
```

### Data Flow

```
Client (pii-guard.js)                     Server (pii_guard.py + Presidio)
─────────────────────                     ──────────────────────────────────
1. User types in editor
2. livePIIScan() — L1 regex
3. Warning bar + action buttons
4. User clicks Submit
5. Fetch interceptor — L1 regex scan
6. If PII found → modal
7. Clean/override → send request ───────► 8. Middleware — L1 regex check
                                          9. If not skipped → Presidio API call
                                          10. L2 NER + L3 Fuzzy + L4 Adversarial
                                          11. L5 Risk scoring
                                          12. Aggregate score → PASS/WARN/BLOCK
                                          13. If BLOCK → 422 response
                                          14. If PASS → route handler
```

---

## 5. Implementation Phases

| Phase | Priority | Items | Effort | Status |
|-------|----------|-------|--------|--------|
| **P0** | Per-match UI + audit | Redact/Remove/Dismiss per match, batch dismiss, audit `action` column | 1 day | **DONE** |
| **P1** | Regex expansion + allowlist | Expand date/phone/address patterns, add medical term allowlist, fax/URL detection | 2 days | Planned |
| **P2** | Presidio integration | Server-side NLP/NER, confidence scoring, custom recognizers, fuzzy matching | 1 week | Planned |
| **P3** | Admin dashboard + adversarial | Audit log UI, GET endpoint, read-path scanning, adversarial detection, risk scoring | 1 week | Planned |
| **P4** | Alerting + monitoring | Email/Slack alerts on override spikes, metrics dashboard, read-path scanning | 3 days | Planned |
| **P5** | BAA + compliance tooling | BAA documentation system, compliance reporting, data retention automation | 2 days | Planned |

---

## 6. Phase Details

### 6.1 P0 — Per-Match UI + Audit Trail (DONE)

**Shipped:** March 30, 2026

**What was delivered:**
- Per-match **Redact / Remove / Dismiss** buttons in Smart Reporter warning bar
- **Batch dismiss by type** ("Dismiss all Patient Age") for types with 2+ matches
- **Bulk Redact All / Remove All** buttons at top of warning bar
- Per-session `_dismissedKeys` Set in `pii-guard.js` — dismissed items don't re-trigger
- `PIIGuard.clearDismissals()` called on session reset ("Done — Start New")
- `PiiOverrideLog.action` column: `override` | `dismiss` | `batch_dismiss`
- Migration in `app.py`: `_add_col_if_missing('pii_override_log', 'action', ...)`
- Updated `/api/pii-override-log` POST to accept and validate `action` field
- Fire-and-forget `_logPIIAction()` in Smart Reporter for dismiss audit
- **48 automated tests passing** (model, route, JS API, integration, edge cases, fetch interceptor)

**Files modified:**
- `models.py` — `PiiOverrideLog.action` column
- `app.py` — Migration block + route update
- `static/pii-guard.js` — Dismiss tracking, `getActionableWarningHTML()`, 6 new public API methods
- `templates/smart_reporter.html` — Warning bar UI, action handlers, livePIIScan update

---

### 6.2 P1 — Regex Expansion + Medical Allowlist

**Goal:** +10% sensitivity, -50% false positives

#### 6.2.1 Expanded Date Patterns

Add to both `pii-guard.js` and `pii_guard.py`:

```
Written months:     January 15, 2024 / 15th March 2024 / 3rd Jun 1990
Mixed formats:      12.Mar.24 / 2024-03-12 / Mar 12 '24
Admission/discharge: admitted 12/03/2024 / discharged on March 15
Date ranges:        from 01/01/2024 to 15/01/2024
Age over 89:        90-year-old / aged 92 (HIPAA requires masking ages >89)
```

#### 6.2.2 Additional HIPAA Identifiers

```
Fax numbers:        fax: +1-202-555-0123 / fax no: 020 7123 4567
Web URLs:           http://hospital.com/patient/123 / www.nhs.uk/record/456
Account numbers:    account no: 12345678 / acct #: 9876
License numbers:    license: DL-0420110149646 / cert: ABC123456
Device IDs:         serial: SN12345678 / device ID: DEV-2024-001
```

#### 6.2.3 Free-Text Relational Patterns

```
Relational:         his/her wife/husband/son/daughter [Name]
                    mother of [Name] / father [Name]
                    next of kin: [Name]
                    emergency contact: [Name]
```

#### 6.2.4 Medical Term Allowlist

Add `MEDICAL_ALLOWLIST` Set to both client and server:

```javascript
const MEDICAL_ALLOWLIST = new Set([
    // Vertebral levels
    'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7',
    'T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8', 'T9', 'T10', 'T11', 'T12',
    'L1', 'L2', 'L3', 'L4', 'L5', 'S1', 'S2',
    // TNM staging
    'T1a', 'T1b', 'T2a', 'T2b', 'T3', 'T4', 'N0', 'N1', 'N2', 'N3', 'M0', 'M1',
    'Stage I', 'Stage II', 'Stage III', 'Stage IV',
    // Common radiology terms
    'CT', 'MRI', 'PET', 'SPECT', 'FLAIR', 'DWI', 'ADC',
    // Measurements
    'HU', 'SUV', 'ADC value',
]);
```

Post-scan filter: if `match.match` is in `MEDICAL_ALLOWLIST`, suppress it.

#### 6.2.5 Files to Modify

- `static/pii-guard.js` — Add patterns, add allowlist filter
- `pii_guard.py` — Mirror new patterns, add allowlist filter

---

### 6.3 P2 — Microsoft Presidio Integration

**Goal:** NLP/NER for free-text names/locations, confidence scoring, +10% sensitivity

#### 6.3.1 Why Presidio

- Open-source (MIT license), maintained by Microsoft
- Covers all **18 HIPAA Safe Harbor identifiers** out of the box
- **Recognizer registry** — plug in our custom regex patterns alongside NER
- **Confidence scoring** (0.0–1.0) per match — key for reducing false positives
- `analyze()` → `anonymize()` pipeline with `replace`, `redact`, `hash`, `mask` operators
- Python SDK: `presidio-analyzer` + `presidio-anonymizer`

#### 6.3.2 Architecture Decision: Separate Microservice

**Presidio CANNOT run on Vercel serverless** because:
- spaCy NER models need 1.5–2GB+ memory (Vercel Pro: 2–4GB total)
- Cold start: 10–30 seconds to load models
- Model files inflate deployment package

**Recommended deployment:**
- **Railway** (separate service) — persistent container, 2GB+ RAM, no cold starts
- OR **Google Cloud Run** with min-instances=1 to avoid cold starts
- RadInsights on Vercel calls Presidio service via HTTP API

#### 6.3.3 Presidio Service API

```
POST /analyze
{
  "text": "Patient John Smith, age 65, from London...",
  "language": "en",
  "score_threshold": 0.5,
  "entities": ["PERSON", "LOCATION", "DATE_TIME", "PHONE_NUMBER", ...]
}

Response:
[
  {"entity_type": "PERSON", "start": 8, "end": 18, "score": 0.92, "text": "John Smith"},
  {"entity_type": "LOCATION", "start": 33, "end": 39, "score": 0.85, "text": "London"}
]
```

#### 6.3.4 Custom Recognizers

Register our existing regex patterns as Presidio `PatternRecognizer`s:

```python
from presidio_analyzer import Pattern, PatternRecognizer

nhs_recognizer = PatternRecognizer(
    supported_entity="UK_NHS_NUMBER",
    patterns=[
        Pattern(name="nhs_standard", regex=r"\bNHS\s*(?:no|number|#)?[:\s]+\d{3}[-\s]?\d{3}[-\s]?\d{4}\b", score=0.9),
        Pattern(name="nhs_short", regex=r"\bNHS\s*(?:no|number|#)?[:\s]+\d{6,10}\b", score=0.7),
        Pattern(name="nhs_format", regex=r"\b\d{3}[-\s]\d{3}[-\s]\d{4}\b", score=0.5),
    ]
)
```

This means our existing patterns contribute to Presidio's scoring rather than being a separate system.

#### 6.3.5 Integration in `pii_guard.py`

```python
# After local regex check, call Presidio for NER-based detection
import requests

def _call_presidio(text, threshold=0.5):
    """Call external Presidio service for NLP-based PHI detection."""
    try:
        resp = requests.post(
            PRESIDIO_API_URL + '/analyze',
            json={'text': text, 'language': 'en', 'score_threshold': threshold},
            timeout=5
        )
        if resp.ok:
            return resp.json()
    except Exception:
        pass  # Fail open — regex layer still catches structured IDs
    return []
```

**Fail-open design:** If Presidio service is down, regex layer still provides protection. Presidio adds NER capability on top, not as a replacement.

#### 6.3.6 Confidence Thresholds

| Score Range | Action | Example |
|-------------|--------|---------|
| < 0.4 | Pass (ignore) | "T1 weighted" (vertebral level, not name) |
| 0.4–0.7 | Warn (show in bar, don't block) | "65" near age context |
| > 0.7 | Block (require action) | "John Smith" with PERSON NER |

#### 6.3.7 Files to Create/Modify

- `presidio_service/` — New microservice directory (separate deployment)
  - `app.py` — Flask REST API wrapping Presidio
  - `custom_recognizers.py` — Our regex patterns as Presidio recognizers
  - `Dockerfile` + `requirements.txt`
- `pii_guard.py` — Add `_call_presidio()` integration
- `.env` — Add `PRESIDIO_API_URL`

---

### 6.4 P3 — Admin Audit Dashboard + Adversarial Detection

#### 6.4.1 Admin Audit Dashboard

**New admin page:** `/admin/pii-audit`

Features:
- **Log browser:** Paginated table of all PII override/dismiss events
- **Filters:** By user, action type, date range, flagged type
- **Aggregations:** Override frequency by type (chart), top overriding users, trend over time
- **Export:** CSV download of filtered logs
- **Alert config:** Set threshold for automated alerts (see P4)

**GET API endpoint:** `GET /api/admin/pii-audit-logs`

```json
{
  "logs": [
    {
      "id": 1,
      "user_email": "user@example.com",
      "action": "dismiss",
      "flagged_types": "Patient Age",
      "flagged_count": 1,
      "target_url": "smart-reporter-editor",
      "created_at": "2026-03-30T22:00:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "per_page": 50,
  "aggregations": {
    "by_action": {"override": 10, "dismiss": 120, "batch_dismiss": 20},
    "by_type": {"Patient Age": 80, "Patient Name": 30, ...},
    "daily_trend": [{"date": "2026-03-30", "count": 15}, ...]
  }
}
```

**Files to create/modify:**
- `admin_routes.py` — Add `/api/admin/pii-audit-logs` GET + `/admin/pii-audit` page route
- `templates/admin_pii_audit.html` — New admin template
- `static/admin-pii-audit.js` — Chart rendering (Chart.js), table, filters

#### 6.4.2 Adversarial Detection (Layer 4)

**Text normalizer** applied before regex scanning:

```python
def normalize_adversarial(text):
    """Normalize text to defeat common adversarial techniques."""
    # 1. Collapse spacing tricks: "J o h n" → "John"
    text = re.sub(r'(?<=[A-Za-z])\s(?=[A-Za-z](?:\s[A-Za-z]){2,})', '', text)

    # 2. Homoglyph normalization (Cyrillic → Latin)
    HOMOGLYPHS = {'А':'A', 'В':'B', 'С':'C', 'Е':'E', 'Н':'H', 'О':'O', 'Р':'P', 'Т':'T', ...}
    for k, v in HOMOGLYPHS.items():
        text = text.replace(k, v)

    # 3. OCR noise: 0→O, 1→I in name-like contexts
    # (context-aware — only in alphabetic sequences)

    # 4. Strip obfuscation characters: @ → a, ! → i in name contexts

    return text
```

#### 6.4.3 Risk Scoring (Layer 5)

Quasi-identifier combination scoring:

```python
QUASI_IDENTIFIERS = {
    'age': 0.2,
    'gender': 0.1,
    'location_partial': 0.3,
    'rare_disease': 0.4,
    'occupation': 0.3,
    'exact_date': 0.2,
}

def calculate_reidentification_risk(matches):
    """Score re-identification risk from quasi-identifier combinations."""
    risk = 0.0
    for m in matches:
        risk += QUASI_IDENTIFIERS.get(m.type_category, 0.1)
    # Cap at 1.0
    return min(risk, 1.0)
```

If combined risk > 0.6, flag even if individual matches are below threshold.

---

### 6.5 P4 — Alerting + Read-Path Scanning

#### 6.5.1 Automated Alerting

**Trigger:** When a single user's override count in the last 24h exceeds a configurable threshold (default: 10).

**Implementation:** Background check on each override log write:

```python
@app.route('/api/pii-override-log', methods=['POST'])
def pii_override_log():
    # ... existing logic ...

    # Check if alert threshold exceeded
    _check_override_alert(current_user.id)

def _check_override_alert(user_id):
    """Fire alert if user override count exceeds threshold in 24h."""
    cutoff = datetime.utcnow() - timedelta(hours=24)
    count = PiiOverrideLog.query.filter(
        PiiOverrideLog.user_id == user_id,
        PiiOverrideLog.created_at >= cutoff
    ).count()

    if count >= PII_ALERT_THRESHOLD:
        _send_pii_alert(user_id, count)
```

**Alert channels:**
- Email to admin (via Resend, already integrated)
- Optional: Slack webhook (`PII_SLACK_WEBHOOK_URL` env var)

**Admin config:** Threshold stored in app config or admin settings page.

#### 6.5.2 Read-Path Scanning

**Problem:** Currently only POST/PUT requests are scanned. If PHI exists in the database (from before PII Guard was added, or from a compromised import), GET responses could serve it unchecked.

**Solution:** Response middleware that scans JSON responses for PHI:

```python
@app.after_request
def scan_response_for_pii(response):
    """Scan outbound JSON responses for PHI (read-path protection)."""
    if response.content_type != 'application/json':
        return response
    # Only scan user-facing routes (not admin)
    if request.path.startswith('/api/admin/'):
        return response
    # Scan and log (don't block — just audit)
    try:
        body = response.get_json(silent=True)
        if body:
            matches = scan_object_for_pii(body)
            if matches:
                logger.warning(f'PHI detected in response: {request.path} types={[m["type"] for m in matches]}')
    except Exception:
        pass
    return response
```

**Design choice:** Read-path scanning is **audit-only** (log, don't block) to avoid breaking existing functionality. Blocking can be enabled per-route later.

---

### 6.6 P5 — BAA + Compliance Tooling

#### 6.6.1 BAA Documentation System

**Admin page:** `/admin/compliance`

Features:
- Upload and manage BAA documents (PDF)
- Track BAA status per vendor (Anthropic, Neon, Vercel, Cloudinary, Resend)
- Expiry tracking with email reminders
- Compliance checklist (HIPAA, UK GDPR, EU GDPR)

#### 6.6.2 Data Retention Automation

- Auto-purge PII override logs older than configurable period (default: 2 years)
- Scheduled job (Vercel cron or Railway cron) to clean up expired records
- Admin confirmation required before purge executes

#### 6.6.3 Compliance Report Generation

- One-click report: "PHI Protection Summary for [date range]"
- Includes: total scans, detection rates, override counts, dismissal patterns
- PDF export for compliance officers

---

## 7. Presidio Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  RadInsights App (Vercel)                                   │
│                                                             │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │ pii-guard.js│    │ Smart        │    │ pii_guard.py  │  │
│  │ (client L1) │    │ Reporter     │    │ (server L1)   │  │
│  │ 24 regex    │    │ livePIIScan  │    │ 24 regex      │  │
│  │ patterns    │    │ + action UI  │    │ + middleware   │  │
│  └─────────────┘    └──────────────┘    └───────┬───────┘  │
│                                                  │          │
│                                          HTTP call if       │
│                                          regex passes       │
│                                                  │          │
└──────────────────────────────────────────────────┼──────────┘
                                                   │
                                                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Presidio Service (Railway / Cloud Run)                     │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  presidio-analyzer                                  │    │
│  │  ├─ spaCy NER (en_core_web_lg)     ← L2 NLP       │    │
│  │  ├─ Custom recognizers (our regex)  ← L1 enhanced  │    │
│  │  ├─ Fuzzy matcher                   ← L3           │    │
│  │  └─ Adversarial normalizer          ← L4           │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  presidio-anonymizer                                │    │
│  │  ├─ Replace with [REDACTED]                         │    │
│  │  ├─ Mask (Joh***)                                   │    │
│  │  └─ Hash (SHA-256)                                  │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Risk Scorer                        ← L5           │    │
│  │  └─ Quasi-identifier combination scoring            │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Endpoints:                                                 │
│    POST /analyze   → detect entities with scores            │
│    POST /anonymize → redact/mask/hash text                  │
│    GET  /health    → service health check                   │
│                                                             │
│  Memory: 2-4 GB | CPU: 1-2 vCPUs | Always-on               │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Detection Target Matrix

Target performance after each phase:

| Metric | Current (P0) | After P1 | After P2 | After P3 | Target |
|--------|-------------|----------|----------|----------|--------|
| **Sensitivity** | ~85% | ~88% | ~95% | ~98% | >98% |
| **Specificity** | ~90% | ~94% | ~95% | ~97% | >95% |
| **HIPAA identifiers** | 10/18 | 14/18 | 18/18 | 18/18 | 18/18 |
| **Free-text names** | No | No | Yes | Yes | Yes |
| **Confidence scoring** | No | No | Yes | Yes | Yes |
| **Adversarial resistance** | No | No | No | Yes | Yes |
| **Re-ID risk scoring** | No | No | No | Yes | Yes |

---

## 9. False Positive Reduction Strategy

### 9.1 Medical Term Allowlist (P1)

Suppress matches where the detected text is a known medical term. ~50% reduction in false positives from:
- Vertebral levels (C1-C7, T1-T12, L1-L5) triggering name patterns
- TNM staging codes triggering ID patterns
- Measurement units triggering number patterns

### 9.2 Confidence Thresholds (P2)

Presidio's per-match scoring allows granular control:
- **Bare 12-digit number** near "Aadhaar": score 0.9 → BLOCK
- **Bare 12-digit number** standalone: score 0.3 → PASS
- **"Dr. Smith"** in referral context: score 0.95 → BLOCK
- **"CT scan"** with C triggering name pattern: score 0.1 → PASS

### 9.3 User Feedback Loop (P3)

- Track which types users dismiss most frequently
- If a specific pattern type has >80% dismiss rate → automatically downgrade to WARN level
- Admin can review and adjust pattern sensitivity based on real usage data

### 9.4 Context-Aware Suppression (P2+)

- Patient Age `age: 65` in a radiology report describing findings → likely FP, WARN only
- Patient Age `age: 65` in a demographic header → likely TP, BLOCK
- Context window: check 50 chars before/after match for clinical vs demographic language

---

## 10. Admin Audit Dashboard

### 10.1 Page Layout

```
┌────────────────────────────────────────────────────────────────┐
│  PII Guard Audit Trail                              [Export CSV]│
├────────────────────────────────────────────────────────────────┤
│  Filters: [User ▼] [Action ▼] [Type ▼] [Date Range] [Apply]  │
├──────────────────────┬─────────────────────────────────────────┤
│  Summary Cards       │  Override Trend (30 days)               │
│  ┌──────┐ ┌──────┐  │  ┌─────────────────────────────┐       │
│  │  42  │ │ 185  │  │  │  📈 Chart.js line chart      │       │
│  │overr.│ │dism. │  │  │                               │       │
│  └──────┘ └──────┘  │  └─────────────────────────────┘       │
│  ┌──────┐ ┌──────┐  │                                         │
│  │  28  │ │ 255  │  │  Top Flagged Types (pie chart)          │
│  │batch │ │total │  │  ┌─────────────────────────────┐       │
│  └──────┘ └──────┘  │  │  🥧 Patient Age: 40%         │       │
│                      │  │     Patient Name: 25%        │       │
│                      │  │     NHS Number: 15%          │       │
│                      │  └─────────────────────────────┘       │
├──────────────────────┴─────────────────────────────────────────┤
│  Log Table                                                      │
│  ┌────┬──────────┬──────────┬──────────┬───────┬─────────────┐ │
│  │ ID │ User     │ Action   │ Types    │ Count │ Timestamp   │ │
│  ├────┼──────────┼──────────┼──────────┼───────┼─────────────┤ │
│  │ 42 │ user@... │ dismiss  │ Pat. Age │ 1     │ 30 Mar 22:00│ │
│  │ 41 │ user@... │ override │ Name,NHS │ 3     │ 30 Mar 21:55│ │
│  └────┴──────────┴──────────┴──────────┴───────┴─────────────┘ │
│  [< Prev] Page 1 of 5 [Next >]                                 │
└────────────────────────────────────────────────────────────────┘
```

### 10.2 Access Control

- Admin-only (via `@require_admin` decorator)
- Route: `/admin/pii-audit`
- API: `/api/admin/pii-audit-logs` (GET, paginated, filterable)

---

## 11. Alerting System

### 11.1 Alert Triggers

| Trigger | Threshold | Channel |
|---------|-----------|---------|
| User override spike | >10 overrides/24h per user | Email to admin |
| Global override spike | >50 overrides/24h total | Email + Slack |
| New PII type detected | First occurrence of type never seen before | Email |
| Presidio service down | Health check fails 3x consecutively | Slack |

### 11.2 Alert Content

```
Subject: [PII Alert] User override threshold exceeded

User: user@example.com (ID: 42)
Overrides in last 24h: 15
Breakdown:
  - dismiss: 10 (Patient Age x 8, NHS Number x 2)
  - override: 5 (Patient Name x 3, DOB x 2)

Action required: Review at /admin/pii-audit?user=42
```

### 11.3 Implementation

- **Email:** Via Resend (already integrated)
- **Slack:** Optional webhook via `PII_SLACK_WEBHOOK_URL` env var
- **Config:** Admin settings page or `.env` variables

---

## 12. Deployment & Infrastructure

### 12.1 Current (Vercel)

```
Vercel Pro
├── Flask app (all routes)
├── pii-guard.js (client)
├── pii_guard.py (server middleware)
└── SQLite (local) / Neon PostgreSQL (production)
```

### 12.2 After P2 (Vercel + Presidio Service)

```
Vercel Pro                           Railway / Cloud Run
├── Flask app                        ├── Presidio Flask API
├── pii-guard.js (L1 client)        ├── spaCy en_core_web_lg
├── pii_guard.py (L1 server)        ├── Custom recognizers
│   └── calls Presidio API ────────►├── presidio-analyzer
└── Neon PostgreSQL                  └── presidio-anonymizer

                                     Memory: 2-4 GB
                                     CPU: 1-2 vCPUs
                                     Always-on (no cold starts)
```

### 12.3 Presidio Service Deployment

```dockerfile
FROM python:3.11-slim

RUN pip install presidio-analyzer presidio-anonymizer spacy flask gunicorn
RUN python -m spacy download en_core_web_lg

COPY app.py custom_recognizers.py ./

EXPOSE 8080
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:8080", "-w", "2"]
```

**Railway config:**
- Service name: `radinsights-presidio`
- Memory: 2 GB minimum
- Health check: `GET /health`
- Internal networking (private URL, no public access)

---

## 13. Cost Projections

### 13.1 Presidio Service (Railway)

| Item | Cost |
|------|------|
| Railway Hobby ($5/mo) | $5/mo base |
| RAM (2 GB) | ~$10/mo |
| CPU (always-on, low usage) | ~$5/mo |
| **Total** | **~$20/mo** |

### 13.2 Alternative: Google Cloud Run

| Item | Cost |
|------|------|
| Memory (2 GB, min-instances=1) | ~$15/mo |
| CPU (1 vCPU) | ~$10/mo |
| **Total** | **~$25/mo** |

### 13.3 No Additional API Costs

Presidio runs entirely locally — no per-request charges. spaCy models are included in the container.

---

## 14. Testing & Validation

### 14.1 Test Corpus

Build a test corpus of 500+ text samples:
- 200 with known PHI (names, IDs, dates, addresses)
- 200 clean medical texts (should NOT trigger)
- 100 edge cases (medical terms, abbreviations, partial matches)

### 14.2 Metrics Tracking

After each phase, measure:
- **True positive rate** (sensitivity): PHI correctly detected
- **False positive rate** (1 - specificity): Clean text incorrectly flagged
- **F1 score**: Harmonic mean of precision and recall
- **Per-type accuracy**: Breakdown by identifier category

### 14.3 Automated Test Suite

```
tests/
├── test_pii_patterns.py      # Regex pattern unit tests
├── test_pii_guard_client.js   # Client-side JS tests (Node.js)
├── test_pii_guard_server.py   # Server middleware tests
├── test_pii_presidio.py       # Presidio integration tests
├── test_pii_audit.py          # Audit trail route tests
├── test_pii_allowlist.py      # Medical allowlist tests
├── corpus/
│   ├── phi_positive.jsonl     # Known PHI samples
│   ├── phi_negative.jsonl     # Clean medical text
│   └── phi_edge_cases.jsonl   # Edge cases
```

### 14.4 Current Test Results (P0)

| Suite | Tests | Status |
|-------|-------|--------|
| Model (PiiOverrideLog) | 3 | PASS |
| Route (/api/pii-override-log) | 4 | PASS |
| JS API (pii-guard.js) | 17 | PASS |
| Integration (Smart Reporter) | 10 | PASS |
| Edge Cases | 9 | PASS |
| Fetch Interceptor | 5 | PASS |
| **Total** | **48** | **ALL PASS** |

---

## 15. File Inventory

### 15.1 Existing Files

| File | Role | Lines | Layer |
|------|------|-------|-------|
| `static/pii-guard.js` | Detection engine: 28 regex patterns, tiers, scan/redact/remove, fetch interceptor, dismiss tracking | ~400 | L1 Client |
| `static/pii-guard-ui.js` | UI module: overlay highlights, header badge, click popover, badge dropdown, API button blocking | ~350 | L1 Client |
| `static/pii-guard.css` | All PII Guard styles: marks, badge, dropdown, popover, button blocked state | ~310 | L1 Client |
| `pii_guard.py` | Server-side middleware: regex-only (no spaCy), 422 response with tier info | ~200 | L1 Server |
| `models.py` → `PiiOverrideLog` | Audit trail model | — | Audit |
| `app.py` → `/api/pii-override-log` | Audit log route | — | Audit |
| `templates/smart_reporter.html` | `PIIGuard.protect()` integration | ~6 | UI |
| `templates/vetting.html` | `PIIGuard.protect()` integration | ~6 | UI |
| `templates/radiq.html` | `PIIGuard.protect()` integration | ~6 | UI |
| `templates/base.html` | Global CSS/JS includes (authenticated only) | ~8 | UI |

### 15.2 Files to Create

| File | Phase | Role |
|------|-------|------|
| `presidio_service/app.py` | P2 | Presidio REST API |
| `presidio_service/custom_recognizers.py` | P2 | Our regex as Presidio recognizers |
| `presidio_service/Dockerfile` | P2 | Container deployment |
| `presidio_service/requirements.txt` | P2 | Python dependencies |
| `templates/admin_pii_audit.html` | P3 | Admin audit dashboard |
| `static/admin-pii-audit.js` | P3 | Dashboard charts + table |
| `tests/test_pii_*.py` | P1+ | Test suites |
| `tests/corpus/*.jsonl` | P1+ | Test corpus |

### 15.3 Files to Modify

| File | Phase | Changes |
|------|-------|---------|
| `static/pii-guard.js` | P1 | Expanded patterns, medical allowlist |
| `pii_guard.py` | P1, P2 | Expanded patterns, Presidio call, allowlist |
| `admin_routes.py` | P3 | GET audit logs endpoint, dashboard route |
| `app.py` | P4 | Alert logic in override log route |
| `.env` | P2 | `PRESIDIO_API_URL` |

---

## 16. Version History

| Date | Phase | Change |
|------|-------|--------|
| 2026-03-30 | P0 | Per-match Redact/Remove/Dismiss UI, batch dismiss, audit `action` column, 48 tests |
| 2026-04-06 | v2 | **Complete rewrite.** Standalone package (3 files). Spell-check-feel highlights. Red shield badge with click-to-bulk-action dropdown. API buttons grayed out (no gate modal). HIGH/MEDIUM/LOW tiers. NHS MOD-11 checksum. spaCy dropped. Integrated in Smart Reporter + Vetting + RadIQ. |
| — | P1 | (Planned) Regex expansion, medical allowlist |
| — | P2 | (Planned) Presidio integration, confidence scoring |
| — | P3 | (Planned) Admin dashboard, adversarial detection, risk scoring |
| — | P4 | (Planned) Alerting, read-path scanning |
| — | P5 | (Planned) BAA tooling, compliance reporting |
