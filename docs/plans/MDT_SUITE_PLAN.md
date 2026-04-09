# MDT Suite — Implementation Plan

> **Status:** Ready to implement
> **Created:** 2026-04-09
> **Owner:** RadInsights core team
> **Complexity:** Medium-High
> **Impact:** Very High (workflow tool, daily use)
> **Depends on:** Smart Reporter (existing), PII Guard v2 (existing), TinyMCE (existing)
> **Blocks:** None
> **Estimated effort:** 3–5 days for v1

---

## 1. Executive summary

A workflow tool that lets a consultant radiologist (or registrar) collect cases discussed at a Multi-Disciplinary Team meeting, prepare them in advance, capture the meeting outcome live, and reference previous cases for the same condition — all **without ever storing patient identifiers**.

The MDT Suite extends the existing Smart Reporter MDT action button: instead of generating an MDT summary that lives only in a session card, the consultant can save it into a structured library, organised by meeting and date, with full searchable history.

### Key design constraints
- **Zero patient identifiers** — opaque user-chosen case references only. PII Guard scans every text field and blocks NHS numbers, MRNs, names, DOBs.
- **Single source of truth** — the app DB, never a downloaded file.
- **Mobile-first for live meeting use** — consultants edit on their phone or laptop in the meeting room.
- **No public URLs** — all sharing is auth-gated.
- **Builds on existing infrastructure** — no new AI calls beyond what Smart Reporter already does.

---

## 2. Goals & non-goals

### Goals (v1)
- Save MDT cases under a specific meeting + date
- Organise by date → meeting → cases
- Pre-meeting prep with rich clinical context (clinical hx, imaging, histology, labs, additional notes)
- AI-generated pre-MDT summary (re-uses existing Smart Reporter MDT prompt)
- Live in-meeting consensus and action plan capture
- Diagnosis-based case search across all the user's MDT history
- Link follow-up cases to previous discussions
- Export for offline meeting prep (landscape PDF + interactive HTML)
- Bulk paste-back of consensus from offline notes
- Status tracking: pending → discussed → closed
- Single-user (each user sees only their own cases)

### Non-goals (v1)
- ❌ Real patient identifiers (even hashed)
- ❌ Multi-user collaboration / sharing within trusts
- ❌ Public shareable URLs
- ❌ Write-back from unauthenticated endpoints
- ❌ Calendar widget / scheduling
- ❌ Multi-link case history (single self-FK only)
- ❌ Per-MDT-type templates (universal fields only)
- ❌ Real-time collaboration (no WebSockets / pusher)
- ❌ Offline-first PWA (v2)
- ❌ Outcome analytics dashboards (v2)

---

## 3. Schema

### 3.1 New tables — minimal

```python
class MdtMeeting(db.Model):
    """A scheduled or recurring MDT meeting."""
    __tablename__ = 'mdt_meeting'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'),
                        nullable=False, index=True)

    name = db.Column(db.String(150), nullable=False)
        # Free text — e.g. "Tuesday Lung MDT", "Weekly Hepatobiliary"
    mdt_type = db.Column(db.String(50), nullable=True, index=True)
        # Enum: lung, upper_gi, lower_gi, breast, hepatobiliary, neuro_onc,
        # gynae_onc, urology, head_neck, sarcoma, lymphoma, paeds,
        # vascular, transplant, other
    date = db.Column(db.Date, nullable=False, index=True)
        # The date this meeting occurred or will occur
    is_recurring = db.Column(db.Boolean, default=False, nullable=False)
        # If True, app may auto-create future instances (v2 feature, ignored in v1)

    created_at = db.Column(db.DateTime, default=datetime.utcnow,
                           nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('mdt_meetings',
                                                       lazy='dynamic'))
    cases = db.relationship('MdtCase', backref='meeting',
                            cascade='all, delete-orphan',
                            lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'name', 'date',
                            name='uq_mdt_meeting_user_name_date'),
        db.Index('ix_mdt_meeting_user_date', 'user_id', 'date'),
    )
```

```python
class MdtCase(db.Model):
    """An individual case within an MDT meeting."""
    __tablename__ = 'mdt_case'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'),
                        nullable=False, index=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('mdt_meeting.id'),
                           nullable=False, index=True)

    # Identity (no patient identifiers)
    case_reference = db.Column(db.String(50), nullable=True)
        # User-chosen opaque reference, e.g. "L-2026-04-007".
        # Optional — user can leave blank if they don't want to use one.
        # PII Guard scans on save to block NHS/MRN/name patterns.

    diagnosis = db.Column(db.String(300), nullable=False, index=True)
        # Searchable via pg_trgm

    status = db.Column(db.String(20), nullable=False, default='pending')
        # Enum: pending, discussed, action_recorded, closed

    # Pre-meeting context
    clinical_history = db.Column(db.Text, nullable=True)
    imaging_findings = db.Column(db.Text, nullable=True)
    histology_biopsy = db.Column(db.Text, nullable=True)
    lab_values = db.Column(db.Text, nullable=True)
    additional_notes = db.Column(db.Text, nullable=True)
    pre_mdt_summary = db.Column(db.Text, nullable=True)
        # AI-generated 2-3 line summary, editable by user

    # Meeting outcome (filled live or after the meeting)
    mdt_consensus = db.Column(db.Text, nullable=True)
    action_plan = db.Column(db.Text, nullable=True)
    follow_up_date = db.Column(db.Date, nullable=True)

    # Linking to a previous case (single self-FK in v1)
    linked_case_id = db.Column(db.Integer, db.ForeignKey('mdt_case.id'),
                               nullable=True)

    # Source attribution (admin metadata)
    source_smart_reporter_session_id = db.Column(db.Integer, nullable=True)
        # If created from a Smart Reporter MDT card, link back

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow,
                           nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('mdt_cases',
                                                       lazy='dynamic'))
    linked_case = db.relationship('MdtCase', remote_side=[id])

    __table_args__ = (
        db.Index('ix_mdt_case_user_status', 'user_id', 'status'),
        db.Index('ix_mdt_case_meeting_status', 'meeting_id', 'status'),
    )
```

### 3.2 Migration block (idempotent, in `app.py`)

Add to the existing init block, after PR4 C3 sync:

```python
# -- PR4 / C4: create MDT Suite tables --
try:
    if 'mdt_meeting' not in insp.get_table_names():
        from models import MdtMeeting as _MM, MdtCase as _MC
        _MM.__table__.create(db.engine, checkfirst=True)
        _MC.__table__.create(db.engine, checkfirst=True)
        logger.info('PR4 C4: created mdt_meeting + mdt_case tables')
except Exception as _mdt_err:
    db.session.rollback()
    logger.warning('PR4 C4 MDT table creation skipped: %s', _mdt_err)
```

### 3.3 Postgres `pg_trgm` for diagnosis search

Already enabled in production (used by global search). Add an index:

```python
# In the migration block, after table creation:
try:
    with db.engine.connect() as conn:
        conn.execute(text(
            'CREATE INDEX IF NOT EXISTS ix_mdt_case_diagnosis_trgm '
            'ON mdt_case USING gin (diagnosis gin_trgm_ops)'
        ))
        conn.commit()
except Exception as _trgm_err:
    logger.warning('PR4 C4 trgm index skipped: %s', _trgm_err)
```

This enables fast fuzzy search like `WHERE diagnosis %% 'lung ca'` matching "lung cancer", "NSCLC RUL", "adenocarcinoma of lung", etc.

---

## 4. Routes

### 4.1 New blueprint: `mdt_routes.py`

```python
mdt_bp = Blueprint('mdt', __name__)

# ── Page routes (HTML) ──
GET  /mdt                                      → MDT Suite landing (date picker + recent meetings)
GET  /mdt/meetings                             → All meetings list (filterable by date range, type)
GET  /mdt/meetings/<int:meeting_id>            → Meeting browser (cases table)
GET  /mdt/meetings/<int:meeting_id>/case/<int:case_id>  → Case detail / edit view
GET  /mdt/cases/search?q=...                   → Cross-meeting diagnosis search
GET  /mdt/cases/<int:case_id>                  → Direct case view (used from search results)

# ── API routes (JSON) ──
POST /api/mdt/meetings                         → Create meeting
GET  /api/mdt/meetings                         → List user's meetings (filter by date, type, name autocomplete)
PUT  /api/mdt/meetings/<int:id>                → Update meeting
DELETE /api/mdt/meetings/<int:id>              → Delete meeting (cascades to cases)

POST /api/mdt/cases                            → Create case (under a meeting)
GET  /api/mdt/cases/<int:id>                   → Get case detail
PUT  /api/mdt/cases/<int:id>                   → Update case (autosave-friendly)
DELETE /api/mdt/cases/<int:id>                 → Delete case
POST /api/mdt/cases/<int:id>/generate-summary  → AI generate pre_mdt_summary (re-uses Smart Reporter MDT prompt)
POST /api/mdt/cases/<int:id>/link              → Link to a previous case (body: {linked_case_id})
GET  /api/mdt/cases/search?q=...               → Diagnosis search (pg_trgm)

# ── Export routes ──
GET  /api/mdt/meetings/<int:id>/export?format=pdf   → Landscape PDF download
GET  /api/mdt/meetings/<int:id>/export?format=html  → Self-contained interactive HTML download

# ── Bulk import routes ──
POST /api/mdt/meetings/<int:id>/bulk-consensus      → Parse pasted clipboard block, update cases
                                                       Body: { entries: [{case_reference, mdt_consensus,
                                                       action_plan, status}, ...] }
GET  /api/mdt/cases/parse-clipboard                  → POST endpoint to validate clipboard before commit
                                                       (returns diff preview)
```

### 4.2 Authentication

All routes require `@login_required`. Personal data — never expose to anonymous users. No public routes for MDT.

### 4.3 Authorisation

Every query filters by `user_id == current_user.id`. A user can never see another user's MDT cases via any route. No admin override.

---

## 5. Templates

### 5.1 New templates

```
templates/
├── mdt_landing.html              ← /mdt — entry page with date picker, recent meetings list, "Search by diagnosis" box
├── mdt_meetings_list.html        ← /mdt/meetings — full filterable meeting list
├── mdt_meeting_browser.html      ← /mdt/meetings/<id> — cases table for one meeting
├── mdt_case_detail.html          ← /mdt/meetings/<id>/case/<id> — case form (5 sections)
├── mdt_case_search.html          ← /mdt/cases/search — diagnosis search results
└── partials/
    ├── _mdt_case_form.html       ← reusable case form (used in detail + bulk import)
    ├── _mdt_case_card.html       ← compact card for list views
    └── _mdt_export_html.html     ← interactive HTML export template (self-contained, downloaded)
```

### 5.2 mdt_landing.html structure

```
┌──────────────────────────────────────────────────┐
│ 🏥 MDT Suite                                     │
│    Workflow tool for multi-disciplinary cases    │
├──────────────────────────────────────────────────┤
│  Quick start:                                    │
│  ┌────────────────────────────────────────────┐  │
│  │ Date    [_______]  Meeting [autocomplete]  │  │
│  │ [Open] [+ New Meeting]                     │  │
│  └────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────┤
│  📋 This week (4)                                │
│   • Tue 2026-04-15 — Lung MDT (8 cases · 3 pending) │
│   • Wed 2026-04-16 — Hepatobiliary (5 cases)     │
│   • Thu 2026-04-17 — Breast (12 cases · 7 pending)│
│   • Fri 2026-04-18 — Neuro-onc (3 cases)         │
├──────────────────────────────────────────────────┤
│  🔍 Search all cases by diagnosis                │
│   [_______________________________]              │
└──────────────────────────────────────────────────┘
```

### 5.3 mdt_case_detail.html — the case form

Five clearly delineated sections (matches the agreed layout in the conversation):

1. **Case identity** — case reference (password-style input), diagnosis, status radio buttons
2. **Pre-meeting context** — 5 textareas: clinical history, imaging findings, histology/biopsy, lab values, additional notes
3. **AI pre-MDT summary** — generate / regenerate button, editable textarea
4. **Meeting outcome** — consensus, action plan, follow-up date
5. **Linking** — "Link to previous case" button with diagnosis search modal

Each section is a `card` with its own header. Auto-save fires on blur for each field individually (debounced 1s).

### 5.4 _mdt_case_form.html — reusable partial

Same structure as the case detail page but stripped of breadcrumbs and title — used in both the case detail page and the in-meeting mobile view.

### 5.5 _mdt_export_html.html — interactive HTML export

Self-contained, single file, no external assets:
- All CSS inline
- All JS inline
- Each case = a 2-column block (left = data, right = textarea + radio for consensus/action/status)
- Top of file: clipboard-copy button that serialises all consensus entries as JSON
- Bottom of file: instructions for pasting back into the app

---

## 6. PDF export — landscape A4

### 6.1 Approach

Server-side rendering. Two options:

**Option A — WeasyPrint** (HTML → PDF, supports CSS landscape)
```python
from weasyprint import HTML, CSS
html_string = render_template('partials/_mdt_export_pdf.html', meeting=m, cases=cs)
pdf = HTML(string=html_string).write_pdf(stylesheets=[
    CSS(string='@page { size: A4 landscape; margin: 1cm; }')
])
```

**Option B — ReportLab** (programmatic PDF construction)
- More work, more control
- No HTML/CSS dependency
- Already used elsewhere in the project? (Check `requirements.txt`)

**Recommendation: WeasyPrint.** Allows reusing the HTML export template with a different stylesheet, single source of truth for layout. Add to `requirements.txt`:
```
weasyprint>=60.0
```

### 6.2 PDF layout (landscape A4)

Per case (one page or one card per page depending on density):

```
┌────────────────────────────────────────┬────────────────────────┐
│ CASE: L-2026-04-007                    │ CONSENSUS              │
│ DIAGNOSIS: Adenocarcinoma RUL          │ ────────────────       │
│ TYPE: Lung MDT  STATUS: Pending        │                        │
├────────────────────────────────────────┤ ────────────────       │
│ Clinical history                       │                        │
│ ────────────────                       │ ────────────────       │
│ 67M ex-smoker, 6/52 weight loss…       │                        │
│                                        │ ────────────────       │
│ Imaging findings                       │                        │
│ ────────────────                       │ ACTION PLAN            │
│ RUL spiculated 4 cm mass…              │ ────────────────       │
│                                        │                        │
│ Histology / biopsy                     │ ────────────────       │
│ ────────────────                       │                        │
│ CNB: adeno, EGFR ex19del…              │ ────────────────       │
│                                        │                        │
│ Lab values                             │ FOLLOW-UP: ___/___     │
│ ────────────────                       │                        │
│ WCC 9, Hb 12, eGFR 65…                 │ STATUS:                │
│                                        │  ☐ Discussed           │
│ Additional notes                       │  ☐ Action recorded     │
│ ────────────────                       │  ☐ Closed              │
│ ECOG 1, COPD GOLD 2…                   │                        │
│                                        │                        │
│ AI pre-MDT summary                     │                        │
│ ────────────────                       │                        │
│ [2-line generated summary]             │                        │
└────────────────────────────────────────┴────────────────────────┘

   RadInsights MDT Suite — Lung MDT — 2026-04-15      page 1 of 8
```

### 6.3 PDF safety

Each PDF is generated on-demand, never cached server-side. No URL leaks the PDF — the route always validates `current_user.id == meeting.user_id` first.

---

## 7. Interactive HTML export

### 7.1 Structure

Self-contained HTML5 document, ~50–100 KB depending on case count.

```html
<!DOCTYPE html>
<html>
<head>
  <title>Lung MDT — 2026-04-15</title>
  <style>/* ALL CSS INLINE */</style>
</head>
<body>
  <header>
    <h1>Lung MDT — 2026-04-15</h1>
    <p>RadInsights MDT Suite export · Generated 2026-04-14 23:00</p>
    <div class="export-toolbar">
      <button onclick="copyConsensusToClipboard()">📋 Copy all consensus</button>
      <button onclick="window.print()">🖨️ Print</button>
    </div>
  </header>

  <main>
    <article class="mdt-case" data-case-ref="L-2026-04-007">
      <div class="case-data">
        <h2>L-2026-04-007 · Adenocarcinoma RUL</h2>
        <section><h3>Clinical history</h3><p>...</p></section>
        <section><h3>Imaging findings</h3><p>...</p></section>
        <section><h3>Histology / biopsy</h3><p>...</p></section>
        <section><h3>Lab values</h3><p>...</p></section>
        <section><h3>Additional notes</h3><p>...</p></section>
        <section><h3>AI pre-MDT summary</h3><p>...</p></section>
      </div>
      <div class="case-input">
        <h3>MDT consensus</h3>
        <textarea data-field="mdt_consensus" rows="6"></textarea>
        <h3>Action plan</h3>
        <textarea data-field="action_plan" rows="4"></textarea>
        <label>Status:
          <select data-field="status">
            <option value="pending" selected>Pending</option>
            <option value="discussed">Discussed</option>
            <option value="action_recorded">Action recorded</option>
            <option value="closed">Closed</option>
          </select>
        </label>
      </div>
    </article>
    <!-- ...more cases... -->
  </main>

  <script>
    // Local storage persistence
    function saveLocal() { /* serialise all textareas + selects to localStorage */ }
    document.querySelectorAll('textarea, select').forEach(
        el => el.addEventListener('input', debounce(saveLocal, 500))
    );
    // Restore on load
    function restoreLocal() { /* ... */ }
    restoreLocal();

    // Clipboard copy — produces a structured JSON block
    function copyConsensusToClipboard() {
      const cases = [...document.querySelectorAll('.mdt-case')].map(c => ({
        case_reference: c.dataset.caseRef,
        mdt_consensus: c.querySelector('[data-field="mdt_consensus"]').value,
        action_plan: c.querySelector('[data-field="action_plan"]').value,
        status: c.querySelector('[data-field="status"]').value
      }));
      navigator.clipboard.writeText(JSON.stringify(cases, null, 2));
      alert('Copied ' + cases.length + ' cases. Paste into RadInsights MDT Suite → Bulk Import.');
    }
  </script>
</body>
</html>
```

### 7.2 Bulk paste-back endpoint

```python
@mdt_bp.route('/api/mdt/meetings/<int:meeting_id>/bulk-consensus', methods=['POST'])
@login_required
def bulk_consensus(meeting_id):
    meeting = MdtMeeting.query.filter_by(
        id=meeting_id, user_id=current_user.id
    ).first_or_404()
    payload = request.get_json()
    entries = payload.get('entries', [])

    diff = []
    for entry in entries:
        case = MdtCase.query.filter_by(
            meeting_id=meeting.id,
            case_reference=entry.get('case_reference'),
            user_id=current_user.id
        ).first()
        if case:
            diff.append({
                'case_id': case.id,
                'case_reference': case.case_reference,
                'old_consensus': case.mdt_consensus,
                'new_consensus': entry.get('mdt_consensus'),
                'old_status': case.status,
                'new_status': entry.get('status'),
            })
            case.mdt_consensus = entry.get('mdt_consensus') or case.mdt_consensus
            case.action_plan = entry.get('action_plan') or case.action_plan
            case.status = entry.get('status') or case.status

    db.session.commit()
    return jsonify({'updated': len(diff), 'diff': diff})
```

A confirmation page shows the diff before commit (uses `?dry_run=1` query param).

---

## 8. Smart Reporter integration

### 8.1 New "Save to MDT Suite" button on the MDT action card

Currently, when a user generates an MDT summary in Smart Reporter, the result lives in a `state.reportActionHistory[]` card. Add a new button next to the existing Copy/Remove buttons:

```html
<button class="btn btn-sm btn-brand-primary" onclick="saveMdtToSuite(<index>)">
  <i class="fas fa-save me-1"></i>Save to MDT Suite
</button>
```

### 8.2 saveMdtToSuite() — frontend

Opens a small modal pre-filled with:
- **Date**: today (editable date picker)
- **Meeting name**: autocomplete from user's previous meetings (last 30 days)
- **MDT type**: dropdown (lung, breast, etc.)
- **Diagnosis**: pre-filled from the AI MDT card if extractable, else blank
- **Case reference**: blank, user types

On save, the modal POSTs to `/api/mdt/cases` with:
- All 5 pre-meeting context fields pre-filled from the Smart Reporter session (clinical_history, imaging_findings)
- pre_mdt_summary = the AI-generated MDT card content
- meeting_id resolved or created on the fly
- source_smart_reporter_session_id = current session

After save, a toast appears: "Saved to Lung MDT 2026-04-15 → [view in MDT Suite]" with a link.

### 8.3 Backend reuse

The Smart Reporter MDT generation prompt is already in `ai_smart_reporter.py`. The MDT Suite reuses it by calling the same function:

```python
# In mdt_routes.py
from ai_smart_reporter import generate_mdt_summary

@mdt_bp.route('/api/mdt/cases/<int:case_id>/generate-summary', methods=['POST'])
@login_required
def generate_mdt_summary_for_case(case_id):
    case = MdtCase.query.filter_by(id=case_id, user_id=current_user.id).first_or_404()
    # Build context from all 5 pre-meeting fields
    context = {
        'clinical_history': case.clinical_history,
        'imaging_findings': case.imaging_findings,
        'histology_biopsy': case.histology_biopsy,
        'lab_values': case.lab_values,
        'additional_notes': case.additional_notes,
        'diagnosis': case.diagnosis,
    }
    summary = generate_mdt_summary(context)  # Uses Sonnet, same model as Smart Reporter MDT
    case.pre_mdt_summary = summary
    db.session.commit()
    return jsonify({'success': True, 'summary': summary})
```

### 8.4 AI cost

Zero new model calls per case beyond what the user explicitly triggers. The MDT generation is opt-in (button click), uses Sonnet (cheap), and produces ~200 tokens of output. Negligible cost increment.

---

## 9. PII Guard integration

### 9.1 Field-level scanning

PII Guard v2 already scans textareas across the app. The MDT case form fields opt-in via the standard pattern:

```html
<textarea id="caseClinicalHistory"
          data-pii-guard="true"
          data-pii-guard-tier="HIGH"></textarea>
```

The Guard:
- Detects NHS number, MRN, DOB, name, address, postcode patterns
- Highlights matches with dotted underline
- Disables the "Save" button until resolved (Redact / Remove / Dismiss)

### 9.2 Special handling for case_reference

The case reference field is the riskiest entry point because users may instinctively type a real MRN. Extra-tight validation:

```javascript
function validateCaseReference(value) {
    // Block 10-digit numbers (NHS number format)
    if (/^\d{10}$/.test(value)) {
        showError('Looks like an NHS number — use a local reference instead');
        return false;
    }
    // Block 6-8 digit numbers (typical MRN format)
    if (/^\d{6,8}$/.test(value)) {
        showError('Looks like a hospital MRN — use a local reference instead');
        return false;
    }
    return true;
}
```

Server-side mirror of the same checks. Reject the save if either fails.

### 9.3 Visible warning

The case reference label always reads:

> **Local case reference** *(your own label — never enter NHS number or patient name)*

Render as `<input type="password">` with eye-toggle so the visual cue reinforces the rule.

---

## 10. Mobile / in-meeting experience

### 10.1 Responsive layout

The case detail template uses Bootstrap's responsive grid. On mobile:
- Sections stack vertically
- Each textarea expands to full width
- Larger tap targets on Save / Status buttons
- Bottom-anchored "Saved 3s ago" indicator

### 10.2 Auto-save

```javascript
// Per-field debounced auto-save
const autoSave = debounce(async (caseId, field, value) => {
    const r = await fetch(`/api/mdt/cases/${caseId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: value })
    });
    showSaveIndicator(r.ok);
}, 1000);

document.querySelectorAll('[data-mdt-autosave]').forEach(el => {
    el.addEventListener('input', () => autoSave(caseId, el.dataset.field, el.value));
});
```

### 10.3 Offline queue (v2 — not in v1)

For unreliable hospital WiFi, queue failed saves in localStorage and replay when the connection returns. Skip in v1; rely on the user's 4G/5G if WiFi drops.

### 10.4 PWA installability (v2 — not in v1)

Add a manifest + service worker so consultants can install RadInsights as a home-screen app on iPad/iPhone. Skip in v1.

---

## 11. Navigation placement

### 11.1 Desktop main nav

Add to the **Resources** dropdown (NOT Quick Reference, because it's a workflow tool not a reference card):

```
Resources ▾
├── Radiology Tools
├── Clinical Guidelines & Safety
├── TNM Calculators
├── Vetting Tool
└── MDT Suite          ← NEW
```

### 11.2 Mobile nav

Same — added to the Resources collapse.

### 11.3 Smart Reporter

The "Save to MDT Suite" button on the MDT action card is the primary entry point during the report-then-save workflow.

### 11.4 New active block names

```jinja
{% block tool_active_mdt %}{% endblock %}
{% block mobile_active_mdt %}{% endblock %}
```

Used by `mdt_*.html` templates to highlight the nav item.

---

## 12. Authentication & authorisation matrix

| Route | Auth | User ownership check |
|---|---|---|
| `/mdt` and child page routes | `@login_required` | filter by `user_id` |
| `/api/mdt/*` | `@login_required` | filter by `user_id` on every query |
| Export routes | `@login_required` | confirm `meeting.user_id == current_user.id` before generating |
| Bulk paste-back | `@login_required` | confirm meeting ownership; per-case ownership confirmed by FK chain |

**No admin override.** Admins do not see other users' MDT data even if they want to. This is enforced at the query level and there's no `is_admin` bypass anywhere in the routes.

---

## 13. Search behaviour

### 13.1 Diagnosis search

```python
@mdt_bp.route('/api/mdt/cases/search')
@login_required
def search_cases():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'results': []})

    if db.engine.dialect.name == 'postgresql':
        # pg_trgm fuzzy match
        results = (db.session.query(MdtCase)
                   .filter(MdtCase.user_id == current_user.id)
                   .filter(text("diagnosis %% :q"))
                   .params(q=q)
                   .order_by(text("similarity(diagnosis, :q) DESC"))
                   .params(q=q)
                   .limit(20)
                   .all())
    else:
        # SQLite fallback for local dev — ILIKE
        like = f'%{q}%'
        results = (MdtCase.query
                   .filter(MdtCase.user_id == current_user.id)
                   .filter(MdtCase.diagnosis.ilike(like))
                   .order_by(MdtCase.created_at.desc())
                   .limit(20)
                   .all())

    return jsonify({'results': [c.to_dict() for c in results]})
```

### 13.2 Search result display

Each result shows:
- Case reference
- Diagnosis
- Meeting name + date
- Status badge
- Click → opens the case detail

---

## 14. Export & import flows

### 14.1 Pre-meeting prep flow

1. Consultant creates cases throughout the week, generates AI summaries
2. Night before the meeting: navigate to `/mdt/meetings/<id>` → click **Export PDF (landscape)**
3. PDF downloads to laptop / phone
4. Read on commute / print on hospital printer
5. Walk into the meeting with context loaded

### 14.2 In-meeting (live, online) flow

1. Open phone / laptop in meeting room
2. Log in to RadInsights → Resources → MDT Suite
3. Open today's meeting
4. As each case is discussed, tap the card → consensus textarea
5. Type live → auto-saved every 1s
6. Tick status → Discussed
7. Auto-advance to next case (button)

### 14.3 In-meeting (offline / paper) flow

1. Pre-meeting: download the **landscape PDF**
2. Print or load on iPad
3. During meeting: write consensus by hand in the right column
4. After meeting: type up consensus into the app manually OR
5. **Better: download the interactive HTML export instead of PDF**, type into textareas during the meeting (works offline once loaded), then on returning to wifi:
   - Click "Copy all consensus" → JSON in clipboard
   - Open `/mdt/meetings/<id>/bulk-import` in the app
   - Paste → diff preview → confirm → cases updated in one transaction

### 14.4 Why bulk paste-back works

- Single source of truth preserved (app DB)
- Human-in-the-loop (diff preview before commit)
- Only 1 round-trip (no per-case API call)
- Dry-run option = no accidental writes
- Audit trail = single bulk operation, easy to review

---

## 15. Data lifecycle

### 15.1 Retention

- MDT cases live as long as the user account exists
- Soft-delete: a `deleted_at` column on `MdtCase` (add in v1.1 if needed) lets us hide deleted cases without losing audit trail
- Hard delete: DELETE endpoint on the case + cascade from meeting

### 15.2 Account deletion

When a user deletes their account, cascade-delete all their MDT meetings + cases. Already covered by the existing `User.delete()` flow if we add `cascade='all, delete-orphan'` on the relationship (already in the schema above).

### 15.3 Export-on-account-deletion (compliance feature)

Optional: before account deletion, offer a one-click "Download all MDT data" zip. Useful for data portability under GDPR Art. 20.

---

## 16. Testing strategy

### 16.1 Unit tests (`tests/test_mdt.py`)

- `MdtMeeting` model: create, list-by-user, unique constraint
- `MdtCase` model: create, status transitions, link to previous case
- PII Guard: case_reference rejects 10-digit NHS, 6-8-digit MRN
- Diagnosis search: pg_trgm matches "lung ca" → "lung cancer"
- Bulk paste-back: parses well-formed JSON, rejects malformed

### 16.2 Integration tests

- Create meeting → create case → generate summary → save consensus → bulk export → bulk import diff
- Authorisation: user A cannot fetch user B's case (404 not 403, to avoid information leak)
- Smart Reporter → MDT Suite save button → meeting created → case appears

### 16.3 Manual / UI tests

Create `docs/tests/mdt_test.md` (mirroring the format of `vetting_test.md` and `smart_reporter_test.md`) once v1 is built. **Defer until after build** — test plans are easier to write against an implemented system.

---

## 17. Implementation order (3–5 day estimate)

### Day 1 — Schema + scaffolding
- Add `MdtMeeting` and `MdtCase` models to `models.py`
- Add migration block to `app.py` (PR4 C4)
- Verify table creation locally + on first deploy (Postgres trgm index)
- Create `mdt_routes.py` blueprint, register in `app.py`
- Stub all routes returning placeholder data
- Add nav entry + breadcrumb blocks to `base.html`

### Day 2 — Core CRUD + case form
- Implement meeting CRUD (POST/GET/PUT/DELETE)
- Implement case CRUD with all 5 pre-meeting fields + outcome fields
- Build `mdt_case_detail.html` with the 5-section layout
- Wire PII Guard to all textareas
- Auto-save on field blur

### Day 3 — Browse + search + AI summary
- Build `mdt_landing.html` (date picker + recent meetings)
- Build `mdt_meeting_browser.html` (cases table + filter)
- Implement diagnosis search with pg_trgm
- Wire AI summary generation (re-use `generate_mdt_summary` from `ai_smart_reporter.py`)
- Add status badges and case reference display

### Day 4 — Smart Reporter integration + export
- Add "Save to MDT Suite" button + modal to Smart Reporter MDT card
- Frontend modal flow: pick date + meeting + type + diagnosis + reference
- POST to `/api/mdt/cases` from Smart Reporter context
- Build `_mdt_export_html.html` interactive template
- Implement HTML export route
- Implement WeasyPrint PDF export route (landscape A4)
- Add "Export" buttons to meeting browser

### Day 5 — Bulk import + polish
- Build bulk paste-back parser + diff preview page
- Wire clipboard copy from HTML export
- Implement case linking modal (search by diagnosis → click → save linked_case_id)
- Mobile testing (responsive case form, auto-save indicator)
- Write `docs/tests/mdt_test.md`
- Update `docs/COMPREHENSIVE_TODO.md`
- Update `MASTER_PLANNING_INDEX.md`

---

## 18. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| User accidentally types NHS number into case_reference | Medium | High | Server-side regex + Mod-11 check + visible warning + password-style input |
| Bulk paste-back overwrites correct data | Low | High | Diff preview before commit + dry-run flag |
| WeasyPrint not installable on Vercel | Low | Medium | Fallback: render HTML and use browser print-to-PDF; or switch to ReportLab |
| pg_trgm not enabled on local SQLite | Certain | Low | ILIKE fallback in search (already specified above) |
| User loses unsaved consensus when phone screen locks | Medium | Medium | Auto-save every 1s + visible "Saved Xs ago" indicator |
| Compliance creep — pressure to add real patient IDs | Medium | Critical | Architectural decision documented here. If/when needed, build as a separate compliant variant. |
| HTML export shared accidentally via email | Low | Medium | Clear "for personal use only — does not contain patient identifiers" header in the file; reinforced by the no-PII architecture |

---

## 19. v2 follow-on features (out of scope for v1)

- Per-MDT-type templates (lung-specific, breast-specific prompts and field labels)
- Multi-user collaboration (share meeting with another user, audit log)
- PWA installability + offline-first service worker
- Calendar view of upcoming meetings (FullCalendar or similar)
- Recurring meeting auto-creation (weekly, fortnightly)
- Per-case attachment uploads (images, lab PDFs) — needs R2 / blob storage
- Outcome analytics (most common diagnoses, average pending → discussed time)
- Multi-link case history (chain of follow-ups, not just one previous case)
- Trust-level deployment with real NHS numbers + DPIA + DSPT registration
- Voice dictation in the consensus textarea (re-use `speech-to-text.js`)
- AI-suggested action plans based on the consensus text
- Direct integration with hospital PACS via Orthanc / OHIF for image links
- Export to NHS-friendly formats (FHIR, HL7) if hospital deployment

---

## 20. Files touched / created

### New files
```
mdt_routes.py                              ← new blueprint
templates/mdt_landing.html                 ← entry page
templates/mdt_meetings_list.html           ← all meetings
templates/mdt_meeting_browser.html         ← cases table for one meeting
templates/mdt_case_detail.html             ← case form
templates/mdt_case_search.html             ← search results
templates/partials/_mdt_case_form.html     ← reusable form
templates/partials/_mdt_case_card.html     ← reusable list card
templates/partials/_mdt_export_html.html   ← interactive HTML export template
templates/partials/_mdt_export_pdf.html    ← PDF export template (WeasyPrint input)
static/js/mdt-suite.js                     ← case form JS (autosave, search, link modal)
docs/tests/mdt_test.md                     ← interactive test plan (write after build)
```

### Modified files
```
models.py                                  ← MdtMeeting + MdtCase
app.py                                     ← register mdt_bp, PR4 C4 migration, sitemap entries
templates/base.html                        ← Resources dropdown + mobile nav entry
templates/smart_reporter.html              ← "Save to MDT Suite" button + modal
ai_smart_reporter.py                       ← refactor generate_mdt_summary so it accepts the MDT context dict (no breaking change)
public_routes.py                           ← N/A (MDT is auth-only, not public)
requirements.txt                           ← + weasyprint>=60.0
```

---

## 21. Acceptance criteria for v1

A user must be able to, in a single session:

1. ✅ Create a new MDT meeting (date + name + type)
2. ✅ Add a case under that meeting with all 5 pre-meeting context fields
3. ✅ Generate an AI pre-MDT summary
4. ✅ Search by diagnosis across all their meetings
5. ✅ Link a follow-up case to a previous case
6. ✅ Export the meeting as landscape PDF (with blank consensus boxes)
7. ✅ Export the meeting as interactive HTML (with consensus textareas)
8. ✅ Open the HTML offline, type consensus, click "Copy all"
9. ✅ Paste back into the app's bulk import → review diff → commit
10. ✅ Mark cases as discussed / closed
11. ✅ Save a Smart Reporter MDT card directly into the MDT Suite
12. ✅ Be unable to see any other user's cases via any route
13. ✅ Have the case_reference field reject NHS-number-shaped input

If all 13 pass, v1 ships. If any fail, fix before deploy.

---

## 22. Open questions to resolve before build

1. **WeasyPrint vs ReportLab vs browser print-to-PDF** — needs a quick test on Vercel to confirm WeasyPrint works in the serverless environment. If not, fall back to browser-side print.
2. **Soft delete on `MdtCase`** — yes or no for v1? Lean toward NO for v1 simplicity; add `deleted_at` in v1.1 if needed.
3. **Per-user MDT templates** — should we ship a "Lung MDT default fields" config for v1, or wait for v2? Wait for v2.
4. **Voice dictation in consensus textarea** — re-use existing `speech-to-text.js` is trivial. Recommend including in v1 since it's nearly free.
5. **Email notifications** ("You have 3 cases pending for tomorrow's MDT") — out of scope for v1, would need a cron job + email service.

---

## 23. Sign-off

This plan is complete and shippable as written. No more architecture decisions pending. Ready to build on user approval.

Once approved, the build proceeds in the order described in §17. Each day's work is committed and pushed independently so progress is visible and reviewable.

**End of plan.**
