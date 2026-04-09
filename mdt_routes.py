"""
MDT Suite Routes
────────────────

Multi-disciplinary team meeting workflow tool. See
docs/plans/MDT_SUITE_PLAN.md for the full design rationale.

Security model:
- All routes @login_required
- Every query filters by user_id == current_user.id
- No admin override — admins do not see other users' MDT data
- No public routes; auth-only blueprint
- PII Guard scans all textareas; server-side mirror blocks
  NHS-number / MRN-shaped input on case_reference

Day 1 status: stubs + scaffolding only. Day 2+ implements bodies.
"""
import logging
import re
from datetime import date as _date_type, datetime
from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user

from models import db, MdtMeeting, MdtCase

logger = logging.getLogger(__name__)
mdt_bp = Blueprint('mdt', __name__)


# ═══════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════

# Block obvious patient identifiers from the case_reference field.
# This is a server-side mirror of the frontend validation. It is intentionally
# strict because case_reference is the riskiest entry point for accidental
# identifier entry.
_NHS_NUMBER_RE = re.compile(r'^\s*\d{3}\s*\d{3}\s*\d{4}\s*$')   # 10 digits with optional spaces
_PLAIN_DIGITS_RE = re.compile(r'^\d{6,10}$')                   # 6-10 contiguous digits (MRN/NHS)


def _looks_like_patient_id(value: str) -> bool:
    """Return True if the string looks like a patient identifier."""
    if not value:
        return False
    s = value.strip().replace(' ', '').replace('-', '')
    if _PLAIN_DIGITS_RE.match(s):
        return True
    if _NHS_NUMBER_RE.match(value):
        return True
    return False


def _parse_date(value):
    """Parse a date string ('YYYY-MM-DD') into a date object. Returns None if invalid."""
    if not value:
        return None
    if isinstance(value, _date_type):
        return value
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _own_meeting_or_404(meeting_id):
    m = MdtMeeting.query.filter_by(id=meeting_id, user_id=current_user.id).first()
    if not m:
        abort(404)
    return m


def _own_case_or_404(case_id):
    c = MdtCase.query.filter_by(id=case_id, user_id=current_user.id).first()
    if not c:
        abort(404)
    return c


# ═══════════════════════════════════════════════════════════════════════════
#  PAGE ROUTES (HTML)
# ═══════════════════════════════════════════════════════════════════════════

@mdt_bp.route('/mdt')
@login_required
def mdt_landing():
    """Landing: date picker + recent meetings + diagnosis search."""
    return render_template('mdt_landing.html')


@mdt_bp.route('/mdt/meetings')
@login_required
def mdt_meetings_list():
    """All meetings list, filterable."""
    return render_template('mdt_meetings_list.html')


@mdt_bp.route('/mdt/meetings/<int:meeting_id>')
@login_required
def mdt_meeting_browser(meeting_id):
    """Cases table for one meeting."""
    meeting = _own_meeting_or_404(meeting_id)
    return render_template('mdt_meeting_browser.html', meeting=meeting)


@mdt_bp.route('/mdt/meetings/<int:meeting_id>/case/<int:case_id>')
@login_required
def mdt_case_detail(meeting_id, case_id):
    """Case detail / edit view."""
    meeting = _own_meeting_or_404(meeting_id)
    case = _own_case_or_404(case_id)
    if case.meeting_id != meeting.id:
        abort(404)
    import os
    return render_template(
        'mdt_case_detail.html',
        meeting=meeting,
        case=case,
        cloudinary_cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
        cloudinary_upload_preset=os.environ.get('CLOUDINARY_UPLOAD_PRESET', ''),
    )


@mdt_bp.route('/mdt/cases/search')
@login_required
def mdt_case_search():
    """Cross-meeting diagnosis search results."""
    q = (request.args.get('q') or '').strip()
    return render_template('mdt_case_search.html', query=q)


@mdt_bp.route('/mdt/meetings/<int:meeting_id>/bulk-import')
@login_required
def mdt_bulk_import(meeting_id):
    """Bulk-import consensus from offline HTML notes — paste + diff page."""
    meeting = _own_meeting_or_404(meeting_id)
    return render_template('mdt_bulk_import.html', meeting=meeting)


@mdt_bp.route('/mdt/cases/<int:case_id>')
@login_required
def mdt_case_view(case_id):
    """Direct case view (used from search)."""
    case = _own_case_or_404(case_id)
    import os
    return render_template(
        'mdt_case_detail.html',
        meeting=case.meeting,
        case=case,
        cloudinary_cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
        cloudinary_upload_preset=os.environ.get('CLOUDINARY_UPLOAD_PRESET', ''),
    )


# ═══════════════════════════════════════════════════════════════════════════
#  MEETING API ROUTES (Day 2)
# ═══════════════════════════════════════════════════════════════════════════

@mdt_bp.route('/api/mdt/meetings', methods=['GET'])
@login_required
def api_list_meetings():
    """List user's meetings, filterable by date range, type, name search."""
    q = MdtMeeting.query.filter_by(user_id=current_user.id)

    name = request.args.get('name')
    if name:
        q = q.filter(MdtMeeting.name.ilike(f'%{name}%'))

    mdt_type = request.args.get('mdt_type')
    if mdt_type:
        q = q.filter_by(mdt_type=mdt_type)

    from_date = _parse_date(request.args.get('from'))
    to_date = _parse_date(request.args.get('to'))
    if from_date:
        q = q.filter(MdtMeeting.date >= from_date)
    if to_date:
        q = q.filter(MdtMeeting.date <= to_date)

    meetings = q.order_by(MdtMeeting.date.desc()).limit(100).all()
    return jsonify({'meetings': [m.to_dict(include_case_count=True) for m in meetings]})


@mdt_bp.route('/api/mdt/meetings', methods=['POST'])
@login_required
def api_create_meeting():
    """Create a new MDT meeting."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Meeting name required'}), 400
    meeting_date = _parse_date(data.get('date'))
    if not meeting_date:
        return jsonify({'error': 'Valid date (YYYY-MM-DD) required'}), 400

    # Avoid duplicate (user_id, name, date)
    existing = MdtMeeting.query.filter_by(
        user_id=current_user.id, name=name, date=meeting_date
    ).first()
    if existing:
        return jsonify({'meeting': existing.to_dict(), 'duplicate': True})

    m = MdtMeeting(
        user_id=current_user.id,
        name=name,
        mdt_type=(data.get('mdt_type') or '').strip() or None,
        date=meeting_date,
        is_recurring=bool(data.get('is_recurring')),
    )
    db.session.add(m)
    db.session.commit()
    return jsonify({'meeting': m.to_dict()})


@mdt_bp.route('/api/mdt/meetings/<int:meeting_id>', methods=['GET'])
@login_required
def api_get_meeting(meeting_id):
    m = _own_meeting_or_404(meeting_id)
    cases = [c.to_dict() for c in m.cases.order_by(MdtCase.created_at).all()]
    payload = m.to_dict(include_case_count=True)
    payload['cases'] = cases
    return jsonify({'meeting': payload})


@mdt_bp.route('/api/mdt/meetings/<int:meeting_id>', methods=['PUT'])
@login_required
def api_update_meeting(meeting_id):
    m = _own_meeting_or_404(meeting_id)
    data = request.get_json() or {}
    if 'name' in data:
        m.name = (data['name'] or '').strip() or m.name
    if 'mdt_type' in data:
        m.mdt_type = (data['mdt_type'] or '').strip() or None
    if 'date' in data:
        d = _parse_date(data['date'])
        if d:
            m.date = d
    if 'is_recurring' in data:
        m.is_recurring = bool(data['is_recurring'])
    db.session.commit()
    return jsonify({'meeting': m.to_dict()})


@mdt_bp.route('/api/mdt/meetings/<int:meeting_id>', methods=['DELETE'])
@login_required
def api_delete_meeting(meeting_id):
    m = _own_meeting_or_404(meeting_id)
    db.session.delete(m)
    db.session.commit()
    return jsonify({'success': True})


# ═══════════════════════════════════════════════════════════════════════════
#  CASE API ROUTES (Day 2)
# ═══════════════════════════════════════════════════════════════════════════

@mdt_bp.route('/api/mdt/cases', methods=['POST'])
@login_required
def api_create_case():
    """Create a new MDT case under a meeting."""
    data = request.get_json() or {}
    meeting_id = data.get('meeting_id')
    if not meeting_id:
        return jsonify({'error': 'meeting_id required'}), 400
    meeting = _own_meeting_or_404(meeting_id)

    # Diagnosis is OPTIONAL. User may not know the final diagnosis at MDT
    # time — the whole point of MDT is often to establish it. Empty string
    # is allowed; the case list shows "— pending —" when empty.
    diagnosis = (data.get('diagnosis') or '').strip() or '— pending —'

    case_ref = (data.get('case_reference') or '').strip() or None
    if case_ref and _looks_like_patient_id(case_ref):
        return jsonify({
            'error': 'Case reference looks like a patient identifier (NHS number / MRN). '
                     'Use a local opaque label instead (e.g. L-2026-04-007).'
        }), 400

    follow_up = _parse_date(data.get('follow_up_date'))

    c = MdtCase(
        user_id=current_user.id,
        meeting_id=meeting.id,
        case_reference=case_ref,
        diagnosis=diagnosis,
        status=(data.get('status') or 'pending'),
        clinical_history=data.get('clinical_history'),
        imaging_findings=data.get('imaging_findings'),
        histology_biopsy=data.get('histology_biopsy'),
        lab_values=data.get('lab_values'),
        additional_notes=data.get('additional_notes'),
        pre_mdt_summary=data.get('pre_mdt_summary'),
        mdt_consensus=data.get('mdt_consensus'),
        action_plan=data.get('action_plan'),
        follow_up_date=follow_up,
        linked_case_id=data.get('linked_case_id'),
        source_smart_reporter_session_id=data.get('source_smart_reporter_session_id'),
    )
    db.session.add(c)
    db.session.commit()
    return jsonify({'case': c.to_dict()})


@mdt_bp.route('/api/mdt/cases/<int:case_id>', methods=['GET'])
@login_required
def api_get_case(case_id):
    c = _own_case_or_404(case_id)
    return jsonify({'case': c.to_dict(include_meeting=True)})


@mdt_bp.route('/api/mdt/cases/<int:case_id>', methods=['PUT'])
@login_required
def api_update_case(case_id):
    """Auto-save friendly: any subset of fields may be sent."""
    c = _own_case_or_404(case_id)
    data = request.get_json() or {}

    # case_reference: re-validate if changed
    if 'case_reference' in data:
        new_ref = (data['case_reference'] or '').strip() or None
        if new_ref and _looks_like_patient_id(new_ref):
            return jsonify({
                'error': 'Case reference looks like a patient identifier. Use a local label.'
            }), 400
        c.case_reference = new_ref

    if 'diagnosis' in data:
        new_diag = (data['diagnosis'] or '').strip()
        if new_diag:
            c.diagnosis = new_diag

    if 'status' in data and data['status'] in MdtCase.STATUSES:
        c.status = data['status']

    for f in ('clinical_history', 'imaging_findings', 'histology_biopsy',
              'lab_values', 'additional_notes', 'pre_mdt_summary',
              'mdt_consensus', 'action_plan'):
        if f in data:
            setattr(c, f, data[f])

    if 'follow_up_date' in data:
        c.follow_up_date = _parse_date(data['follow_up_date'])

    if 'linked_case_id' in data:
        c.linked_case_id = data['linked_case_id'] or None

    db.session.commit()
    return jsonify({'case': c.to_dict()})


@mdt_bp.route('/api/mdt/cases/<int:case_id>', methods=['DELETE'])
@login_required
def api_delete_case(case_id):
    c = _own_case_or_404(case_id)
    db.session.delete(c)
    db.session.commit()
    return jsonify({'success': True})


@mdt_bp.route('/api/mdt/cases/<int:case_id>/generate-summary', methods=['POST'])
@login_required
def api_generate_summary(case_id):
    """Generate AI pre_mdt_summary from the 5 context fields.

    Re-uses generate_mdt_summary_for_case from ai_smart_reporter — same
    Sonnet model used by the Smart Reporter MDT action card.
    """
    c = _own_case_or_404(case_id)

    # Rate limit (shares Smart Reporter quota — MDT generation is a Smart
    # Reporter cousin, not vetting)
    try:
        from reporting_routes import _check_ai_rate_limit
        ok, remaining, err = _check_ai_rate_limit(usage_type='sr')
        if not ok:
            return err
    except Exception:
        # If the rate-limit helper is unavailable, fall through (dev only)
        remaining = None

    try:
        from ai_smart_reporter import generate_mdt_summary_for_case, mdt_summary_to_html
        # Same prompt + same model as Smart Reporter MDT card. Model emits
        # plain text; we convert to HTML via mdt_summary_to_html() so the
        # stored field and the rendered view share one format. TinyMCE
        # (Edit mode) then operates on the HTML directly.
        plain_summary, model_used, tokens = generate_mdt_summary_for_case({
            'diagnosis': c.diagnosis,
            'clinical_history': c.clinical_history,
            'imaging_findings': c.imaging_findings,
            'histology_biopsy': c.histology_biopsy,
            'lab_values': c.lab_values,
            'additional_notes': c.additional_notes,
        })
        html_summary = mdt_summary_to_html(plain_summary)
    except Exception as e:
        logger.error("MDT summary generation failed for case %s: %s", case_id, e)
        return jsonify({'error': str(e)}), 500

    # Persist HTML (source of truth after generation)
    c.pre_mdt_summary = html_summary
    db.session.commit()

    return jsonify({
        'summary': html_summary,
        'summary_plain': plain_summary,
        'model_used': model_used,
        'tokens': tokens,
        'remaining_requests': remaining,
        'case': c.to_dict(),
    })


@mdt_bp.route('/api/mdt/cases/<int:case_id>/link', methods=['POST'])
@login_required
def api_link_case(case_id):
    """Link this case to a previous one."""
    c = _own_case_or_404(case_id)
    data = request.get_json() or {}
    target_id = data.get('linked_case_id')
    if target_id:
        target = _own_case_or_404(target_id)
        c.linked_case_id = target.id
    else:
        c.linked_case_id = None
    db.session.commit()
    return jsonify({'case': c.to_dict()})


@mdt_bp.route('/api/mdt/cases/search')
@login_required
def api_search_cases():
    """Diagnosis search across all the user's MDT cases. Day 3 implementation."""
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify({'results': []})

    # Postgres pg_trgm fuzzy match; SQLite ILIKE fallback
    if db.engine.dialect.name == 'postgresql':
        from sqlalchemy import text as _text
        try:
            results = (db.session.query(MdtCase)
                       .filter(MdtCase.user_id == current_user.id)
                       .filter(_text("diagnosis %% :q"))
                       .params(q=q)
                       .limit(20)
                       .all())
        except Exception:
            # Fallback if pg_trgm not enabled
            like = f'%{q}%'
            results = (MdtCase.query
                       .filter(MdtCase.user_id == current_user.id)
                       .filter(MdtCase.diagnosis.ilike(like))
                       .limit(20)
                       .all())
    else:
        like = f'%{q}%'
        results = (MdtCase.query
                   .filter(MdtCase.user_id == current_user.id)
                   .filter(MdtCase.diagnosis.ilike(like))
                   .order_by(MdtCase.created_at.desc())
                   .limit(20)
                   .all())

    return jsonify({'results': [c.to_dict(include_meeting=True) for c in results]})


# ═══════════════════════════════════════════════════════════════════════════
#  EXPORT ROUTES (Day 4 — stubs only)
# ═══════════════════════════════════════════════════════════════════════════

@mdt_bp.route('/api/mdt/meetings/<int:meeting_id>/export')
@login_required
def api_export_meeting(meeting_id):
    """Export a meeting as interactive HTML or landscape PDF.

    HTML: self-contained downloadable file with editable consensus
    textareas, localStorage persistence, and clipboard JSON export
    for paste-back via the bulk import endpoint.

    PDF: same content, rendered landscape A4 via WeasyPrint. If
    WeasyPrint is not installed, returns the HTML with print CSS so
    the user can browser-print to PDF.
    """
    from flask import render_template, make_response
    from datetime import datetime as _dt

    meeting = _own_meeting_or_404(meeting_id)
    fmt = (request.args.get('format') or 'html').lower()

    cases = (meeting.cases
             .order_by(MdtCase.created_at)
             .all())

    html_str = render_template(
        'partials/_mdt_export_html.html',
        meeting=meeting,
        cases=cases,
        generated_at=_dt.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
    )

    safe_name = re.sub(r'[^\w\-]+', '_', meeting.name)[:60]
    safe_date = meeting.date.isoformat() if meeting.date else 'undated'
    base_filename = f'mdt_{safe_name}_{safe_date}'

    if fmt == 'pdf':
        try:
            from weasyprint import HTML, CSS
            pdf_bytes = HTML(string=html_str).write_pdf(stylesheets=[
                CSS(string='@page { size: A4 landscape; margin: 1cm; } '
                            '.toolbar { display: none !important; } '
                            '.privacy-banner { background: #f5f5f5 !important; }')
            ])
            resp = make_response(pdf_bytes)
            resp.headers['Content-Type'] = 'application/pdf'
            resp.headers['Content-Disposition'] = f'attachment; filename="{base_filename}.pdf"'
            return resp
        except ImportError:
            logger.warning('WeasyPrint not installed — falling back to HTML for PDF export')
            # Fall through to HTML download
        except Exception as e:
            logger.error('WeasyPrint render failed: %s', e)
            # Fall through to HTML

    # HTML export (default + PDF fallback)
    resp = make_response(html_str)
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename="{base_filename}.html"'
    return resp


# ═══════════════════════════════════════════════════════════════════════════
#  BULK IMPORT ROUTES (Day 5 — stubs only)
# ═══════════════════════════════════════════════════════════════════════════

@mdt_bp.route('/api/mdt/meetings/<int:meeting_id>/bulk-consensus', methods=['POST'])
@login_required
def api_bulk_consensus(meeting_id):
    """Parse a clipboard JSON block from the HTML export and update cases.

    Body shape (matches the JSON produced by _mdt_export_html.html):
        {
          "meeting_id": 1,
          "entries": [
            {
              "case_id": 12,
              "case_reference": "L-001",
              "mdt_consensus": "...",
              "action_plan": "...",
              "status": "discussed"
            },
            ...
          ]
        }

    Query params:
        ?dry_run=1  → return diff without committing

    Matches cases by case_id first (preferred — survives reference
    changes), then by case_reference as a fallback.
    """
    meeting = _own_meeting_or_404(meeting_id)
    payload = request.get_json() or {}
    entries = payload.get('entries', [])
    if not isinstance(entries, list):
        return jsonify({'error': 'entries must be a list'}), 400

    dry_run = request.args.get('dry_run', '').strip() in ('1', 'true', 'yes')

    diff = []
    skipped = []
    matched_count = 0

    for entry in entries:
        if not isinstance(entry, dict):
            skipped.append({'reason': 'not a dict', 'entry': entry})
            continue

        case = None
        # Prefer case_id (stable across reference renames)
        cid = entry.get('case_id')
        if cid:
            case = MdtCase.query.filter_by(id=cid, user_id=current_user.id).first()
        # Fallback to case_reference within this meeting
        if not case and entry.get('case_reference'):
            case = MdtCase.query.filter_by(
                meeting_id=meeting.id,
                case_reference=entry['case_reference'],
                user_id=current_user.id,
            ).first()

        if not case:
            skipped.append({
                'reason': 'no matching case',
                'case_id': cid,
                'case_reference': entry.get('case_reference'),
            })
            continue

        # Build the diff
        new_consensus = entry.get('mdt_consensus')
        new_action = entry.get('action_plan')
        new_status = entry.get('status')

        # Validate status
        if new_status and new_status not in MdtCase.STATUSES:
            new_status = None

        diff.append({
            'case_id': case.id,
            'case_reference': case.case_reference,
            'diagnosis': case.diagnosis,
            'old_consensus': case.mdt_consensus,
            'new_consensus': new_consensus,
            'old_action_plan': case.action_plan,
            'new_action_plan': new_action,
            'old_status': case.status,
            'new_status': new_status,
        })

        if not dry_run:
            if new_consensus is not None:
                case.mdt_consensus = new_consensus
            if new_action is not None:
                case.action_plan = new_action
            if new_status:
                case.status = new_status
            matched_count += 1

    if not dry_run and matched_count:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error('Bulk consensus commit failed: %s', e)
            return jsonify({'error': 'Database commit failed'}), 500

    return jsonify({
        'dry_run': dry_run,
        'matched': len(diff),
        'updated': matched_count if not dry_run else 0,
        'skipped': len(skipped),
        'diff': diff,
        'skipped_entries': skipped,
    })
