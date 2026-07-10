"""
My Study Notes — Evernote-like unified notes dashboard.

Browse, search, filter, tag, and manage all notes across every content type.
"""

import logging
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from models import db, CandidateNote, TextHighlight, NoteTag

logger = logging.getLogger(__name__)

my_notes_bp = Blueprint('my_notes', __name__)


# ── Content type display metadata ──
CONTENT_TYPE_META = {
    'case':             {'label': 'Cases',              'icon': 'fa-book-medical',    'color': '#e96304'},
    'osce_guide':       {'label': 'OSCE Guide',         'icon': 'fa-x-ray',          'color': '#5E899E'},
    'osce_case':        {'label': 'OSCE Cases',         'icon': 'fa-x-ray',          'color': '#5E899E'},
    'tnm_essentials':   {'label': 'TNM Essentials',     'icon': 'fa-book',            'color': '#6b46c1'},
    'tnm_staging':      {'label': 'TNM Staging',        'icon': 'fa-dna',             'color': '#6b46c1'},
    'protocol':         {'label': 'Protocols',          'icon': 'fa-clipboard-list',  'color': '#17a2b8'},
    'contrast_card':    {'label': 'Contrast Card',      'icon': 'fa-flask',           'color': '#dc3545'},
    'anatomy':          {'label': 'Anatomy',            'icon': 'fa-bone',            'color': '#28a745'},
    'pearl':            {'label': 'Pearls',             'icon': 'fa-gem',             'color': '#6b46c1'},
    'vetting':          {'label': 'Vetting',            'icon': 'fa-graduation-cap',  'color': '#ffc107'},
}


def _content_url(content_type, content_key):
    """Generate a URL to the source content."""
    urls = {
        'case':           '/view-case/{}',
        'osce_guide':     '/osce-radiology-guide',
        'osce_case':      '/osce-radiology-guide',
        'tnm_essentials': '/essential-tnm-concepts',
        'tnm_staging':    '/tnm/{}',
        'protocol':       '/radiology-protocols/view/{}',
        'contrast_card':  '/contrast-reaction-card',
        'anatomy':        '/anatomy-snippets/{}',
        'pearl':          '/radiology-pearls',
        'vetting':        '/vetting-essentials',
    }
    pattern = urls.get(content_type, '')
    if '{}' in pattern:
        return pattern.format(content_key)
    return pattern


@my_notes_bp.route('/my-notes')
@login_required
def my_notes_page():
    """Render the My Study Notes page."""
    return render_template('my_notes.html', content_type_meta=CONTENT_TYPE_META)


@my_notes_bp.route('/api/my-notes')
@login_required
def api_my_notes():
    """Get all user notes with tags and metadata, with optional filters."""
    q = CandidateNote.query.filter_by(user_id=current_user.id)\
        .filter(CandidateNote.content_type.isnot(None))\
        .filter(CandidateNote.content_type != '__migration_v1__')

    # Filters
    ct = request.args.get('content_type')
    if ct:
        q = q.filter_by(content_type=ct)
    starred = request.args.get('starred')
    if starred == '1':
        q = q.filter_by(is_starred=True)
    tag_filter = request.args.get('tag')
    if tag_filter:
        q = q.filter(CandidateNote.id.in_(
            db.session.query(NoteTag.note_id).filter_by(user_id=current_user.id, tag=tag_filter)
        ))
    search = request.args.get('search', '').strip()
    if search:
        q = q.filter(
            db.or_(
                CandidateNote.note_text.ilike(f'%{search}%'),
                CandidateNote.source_title.ilike(f'%{search}%'),
            )
        )
    body_sec = request.args.get('body_section')
    if body_sec:
        q = q.filter_by(body_section=body_sec)

    notes = q.order_by(CandidateNote.updated_at.desc()).limit(200).all()

    result = []
    for n in notes:
        tags = [t.tag for t in (n.tags or [])]
        meta = CONTENT_TYPE_META.get(n.content_type, {})
        result.append({
            'id': n.id,
            'content_type': n.content_type,
            'content_key': n.content_key,
            'note_text': n.note_text,
            'source_title': n.source_title or _default_title(n.content_type, n.content_key),
            'source_url': _content_url(n.content_type, n.content_key),
            'body_section': n.body_section,
            'modality': n.modality,
            'is_starred': n.is_starred or False,
            'tags': tags,
            'type_label': meta.get('label', n.content_type),
            'type_icon': meta.get('icon', 'fa-sticky-note'),
            'type_color': meta.get('color', '#666'),
            'created_at': n.created_at.isoformat() if n.created_at else None,
            'updated_at': n.updated_at.isoformat() if n.updated_at else None,
        })

    return jsonify({'success': True, 'notes': result, 'total': len(result)})


def _default_title(content_type, content_key):
    """Fallback title when source_title is not cached."""
    meta = CONTENT_TYPE_META.get(content_type, {})
    label = meta.get('label', content_type or 'Note')
    if content_key and content_key not in ('main', 'guide', 'browse'):
        return f'{label}: {content_key}'
    return label


@my_notes_bp.route('/api/my-notes/tags')
@login_required
def api_my_notes_tags():
    """Get all tags for the current user with counts."""
    rows = db.session.query(NoteTag.tag, db.func.count(NoteTag.id))\
        .filter_by(user_id=current_user.id)\
        .group_by(NoteTag.tag)\
        .order_by(db.func.count(NoteTag.id).desc())\
        .all()
    return jsonify({'success': True, 'tags': [{'tag': r[0], 'count': r[1]} for r in rows]})


@my_notes_bp.route('/api/my-notes/stats')
@login_required
def api_my_notes_stats():
    """Get stats: counts by content_type, total notes, total highlights."""
    type_counts = db.session.query(CandidateNote.content_type, db.func.count(CandidateNote.id))\
        .filter_by(user_id=current_user.id)\
        .filter(CandidateNote.content_type.isnot(None))\
        .filter(CandidateNote.content_type != '__migration_v1__')\
        .group_by(CandidateNote.content_type).all()

    highlight_count = TextHighlight.query.filter_by(user_id=current_user.id).count()

    starred_count = CandidateNote.query.filter_by(user_id=current_user.id, is_starred=True)\
        .filter(CandidateNote.content_type != '__migration_v1__').count()

    notebooks = {}
    for ct, count in type_counts:
        meta = CONTENT_TYPE_META.get(ct, {})
        notebooks[ct] = {
            'count': count,
            'label': meta.get('label', ct),
            'icon': meta.get('icon', 'fa-sticky-note'),
            'color': meta.get('color', '#666'),
        }

    return jsonify({
        'success': True,
        'notebooks': notebooks,
        'total_notes': sum(c for _, c in type_counts),
        'total_highlights': highlight_count,
        'starred_count': starred_count,
    })


@my_notes_bp.route('/api/my-notes/<int:note_id>/star', methods=['POST'])
@login_required
def api_toggle_star(note_id):
    """Toggle starred status on a note."""
    note = CandidateNote.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    note.is_starred = not (note.is_starred or False)
    db.session.commit()
    return jsonify({'success': True, 'is_starred': note.is_starred})


@my_notes_bp.route('/api/my-notes/<int:note_id>/tags', methods=['POST'])
@login_required
def api_update_tags(note_id):
    """Add or remove a tag from a note."""
    note = CandidateNote.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json() or {}
    action = data.get('action', 'add')
    tag = (data.get('tag') or '').strip().lower()[:50]
    if not tag:
        return jsonify({'error': 'Tag required'}), 400

    if action == 'add':
        existing = NoteTag.query.filter_by(note_id=note_id, tag=tag).first()
        if not existing:
            db.session.add(NoteTag(note_id=note_id, tag=tag, user_id=current_user.id))
            db.session.commit()
    elif action == 'remove':
        NoteTag.query.filter_by(note_id=note_id, tag=tag).delete()
        db.session.commit()

    tags = [t.tag for t in NoteTag.query.filter_by(note_id=note_id).all()]
    return jsonify({'success': True, 'tags': tags})


@my_notes_bp.route('/api/my-notes/<int:note_id>', methods=['PUT'])
@login_required
def api_update_note(note_id):
    """Inline edit a note's text."""
    note = CandidateNote.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json() or {}
    note_text = (data.get('note_text') or '').strip()
    if not note_text:
        return jsonify({'error': 'Note text required'}), 400

    note.note_text = note_text
    note.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True, 'updated_at': note.updated_at.isoformat()})


@my_notes_bp.route('/api/my-notes/<int:note_id>', methods=['DELETE'])
@login_required
def api_delete_note(note_id):
    """Delete a note and its tags."""
    note = CandidateNote.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    # Tags cascade via relationship, but be explicit
    NoteTag.query.filter_by(note_id=note_id).delete()
    db.session.delete(note)
    db.session.commit()
    return jsonify({'success': True})
