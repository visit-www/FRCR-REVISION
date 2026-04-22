"""
Generic Content Interaction Routes

Provides notes, highlights, and discussion forum for ANY content type
(cases, OSCE guide sections, learning modules, etc.) via a unified API.

URL pattern: /api/content/<content_type>/<content_key>/...

Keeps backward compatibility — legacy /api/case/<id>/note endpoints still work.
This module adds the generic layer on top.
"""

import json
import logging
from datetime import datetime

import cloudinary.uploader
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from models import db, CandidateNote, TextHighlight, ForumMessage, ForumMessageVote, User

logger = logging.getLogger(__name__)

content_bp = Blueprint('content_interact', __name__, url_prefix='/api/content')


# =========================================================================
# NOTES
# =========================================================================

@content_bp.route('/<content_type>/<content_key>/note', methods=['GET'])
@login_required
def get_note(content_type, content_key):
    """Get the current user's note for this content."""
    note = CandidateNote.query.filter_by(
        content_type=content_type,
        content_key=content_key,
        user_id=current_user.id
    ).first()
    if not note:
        return jsonify({'note_text': '', 'id': None})
    return jsonify({
        'id': note.id,
        'note_text': note.note_text,
        'created_at': note.created_at.isoformat() if note.created_at else None,
        'updated_at': note.updated_at.isoformat() if note.updated_at else None,
    })


@content_bp.route('/<content_type>/<content_key>/note', methods=['POST'])
@login_required
def save_note(content_type, content_key):
    """Create or update a note for this content."""
    data = request.get_json() or {}
    note_text = (data.get('note_text') or '').strip()
    if not note_text:
        return jsonify({'error': 'Note text is required'}), 400

    note = CandidateNote.query.filter_by(
        content_type=content_type,
        content_key=content_key,
        user_id=current_user.id
    ).first()

    if note:
        note.note_text = note_text
        note.updated_at = datetime.utcnow()
    else:
        note = CandidateNote(
            content_type=content_type,
            content_key=content_key,
            user_id=current_user.id,
            note_text=note_text,
        )
        db.session.add(note)

    db.session.commit()
    return jsonify({'success': True, 'id': note.id})


@content_bp.route('/<content_type>/<content_key>/note', methods=['DELETE'])
@login_required
def delete_note(content_type, content_key):
    """Delete the current user's note for this content."""
    note = CandidateNote.query.filter_by(
        content_type=content_type,
        content_key=content_key,
        user_id=current_user.id
    ).first()
    if note:
        db.session.delete(note)
        db.session.commit()
    return jsonify({'success': True})


# =========================================================================
# HIGHLIGHTS
# =========================================================================

@content_bp.route('/<content_type>/<content_key>/highlights', methods=['GET'])
@login_required
def get_highlights(content_type, content_key):
    """Get all highlights for this content by the current user."""
    highlights = TextHighlight.query.filter_by(
        content_type=content_type,
        content_key=content_key,
        user_id=current_user.id
    ).order_by(TextHighlight.created_at).all()

    return jsonify({
        'success': True,
        'highlights': [{
            'id': h.id,
            'text_content': h.text_content,
            'highlight_color': h.highlight_color,
            'field_name': h.field_name,
            'context_before': h.context_before,
            'context_after': h.context_after,
            'created_at': h.created_at.isoformat() if h.created_at else None,
        } for h in highlights]
    })


@content_bp.route('/<content_type>/<content_key>/highlight', methods=['POST'])
@login_required
def create_highlight(content_type, content_key):
    """Create a text highlight."""
    data = request.get_json() or {}
    text_content = (data.get('text_content') or '').strip()
    if not text_content:
        return jsonify({'error': 'text_content is required'}), 400

    highlight = TextHighlight(
        content_type=content_type,
        content_key=content_key,
        user_id=current_user.id,
        text_content=text_content,
        highlight_color=data.get('highlight_color', 'yellow'),
        field_name=data.get('field_name', 'content'),
        context_before=data.get('context_before', '')[:100],
        context_after=data.get('context_after', '')[:100],
    )
    db.session.add(highlight)
    db.session.commit()

    return jsonify({'success': True, 'id': highlight.id}), 201


@content_bp.route('/highlight/<int:highlight_id>', methods=['DELETE'])
@login_required
def delete_highlight(highlight_id):
    """Delete a highlight (must be owned by current user)."""
    h = TextHighlight.query.get_or_404(highlight_id)
    if h.user_id != current_user.id:
        return jsonify({'error': 'Not your highlight'}), 403
    db.session.delete(h)
    db.session.commit()
    return jsonify({'success': True})


# =========================================================================
# DISCUSSION FORUM
# =========================================================================

@content_bp.route('/<content_type>/<content_key>/forum', methods=['GET'])
@login_required
def get_forum_messages(content_type, content_key):
    """Get forum messages for this content, sorted by votes then date."""
    messages = ForumMessage.query.filter_by(
        content_type=content_type,
        content_key=content_key,
        is_deleted=False,
    ).order_by(
        ForumMessage.is_pinned.desc(),
        ForumMessage.vote_score.desc(),
        ForumMessage.created_at.desc()
    ).limit(100).all()

    # Get current user's votes
    msg_ids = [m.id for m in messages]
    user_votes = {}
    if msg_ids:
        votes = ForumMessageVote.query.filter(
            ForumMessageVote.message_id.in_(msg_ids),
            ForumMessageVote.user_id == current_user.id
        ).all()
        user_votes = {v.message_id: v.vote_value for v in votes}

    return jsonify({
        'success': True,
        'messages': [{
            'id': m.id,
            'content': m.content,
            'user_name': m.author.full_name or m.author.email.split('@')[0] if m.author else 'Unknown',
            'user_picture': m.author.profile_picture if m.author else None,
            'vote_score': m.vote_score,
            'user_vote': user_votes.get(m.id, 0),
            'is_pinned': m.is_pinned,
            'is_own': m.user_id == current_user.id,
            'is_admin': getattr(m.author, 'is_admin', False) if m.author else False,
            'image_url': m.image_url,
            'image_thumbnail_url': m.image_thumbnail_url,
            'created_at': m.created_at.isoformat() if m.created_at else None,
        } for m in messages],
        'total': len(messages),
    })


@content_bp.route('/<content_type>/<content_key>/forum', methods=['POST'])
@login_required
def post_forum_message(content_type, content_key):
    """Post a new forum message."""
    # Support both JSON and multipart (for image uploads)
    if request.content_type and 'multipart/form-data' in request.content_type:
        content_text = (request.form.get('content') or '').strip()
        image_file = request.files.get('image')
    else:
        data = request.get_json() or {}
        content_text = (data.get('content') or '').strip()
        image_file = None

    if not content_text:
        return jsonify({'error': 'Message content is required'}), 400

    msg = ForumMessage(
        content_type=content_type,
        content_key=content_key,
        user_id=current_user.id,
        content=content_text,
    )

    # Handle image upload
    if image_file and image_file.filename:
        try:
            from app import _strip_exif
            image_file = _strip_exif(image_file)
            upload_result = cloudinary.uploader.upload(
                image_file,
                folder='frcr_revision/forum',
                resource_type='image',
                transformation=[{'quality': 'auto', 'fetch_format': 'auto'}]
            )
            msg.image_url = upload_result['secure_url']
            msg.image_public_id = upload_result['public_id']
            msg.image_thumbnail_url = cloudinary.CloudinaryImage(
                upload_result['public_id']
            ).build_url(width=300, height=200, crop='fill', quality='auto')
        except Exception as exc:
            logger.warning("Forum image upload failed: %s", exc)

    db.session.add(msg)
    db.session.commit()

    return jsonify({
        'success': True,
        'id': msg.id,
        'user_name': current_user.full_name or current_user.email.split('@')[0],
    }), 201


@content_bp.route('/forum/<int:message_id>/vote', methods=['POST'])
@login_required
def vote_forum_message(message_id):
    """Vote on a forum message (+1 or -1)."""
    data = request.get_json() or {}
    vote_value = data.get('vote', 0)
    if vote_value not in (1, -1):
        return jsonify({'error': 'Vote must be 1 or -1'}), 400

    msg = ForumMessage.query.get_or_404(message_id)
    existing = ForumMessageVote.query.filter_by(
        message_id=message_id, user_id=current_user.id
    ).first()

    if existing:
        if existing.vote_value == vote_value:
            # Toggle off
            msg.vote_score -= existing.vote_value
            db.session.delete(existing)
        else:
            # Change vote
            msg.vote_score -= existing.vote_value
            existing.vote_value = vote_value
            msg.vote_score += vote_value
    else:
        vote = ForumMessageVote(
            message_id=message_id,
            user_id=current_user.id,
            vote_value=vote_value,
        )
        db.session.add(vote)
        msg.vote_score += vote_value

    db.session.commit()
    return jsonify({'success': True, 'vote_score': msg.vote_score})


@content_bp.route('/forum/<int:message_id>', methods=['DELETE'])
@login_required
def delete_forum_message(message_id):
    """Soft-delete a forum message (own messages or admin)."""
    msg = ForumMessage.query.get_or_404(message_id)
    if msg.user_id != current_user.id and not getattr(current_user, 'is_admin', False):
        return jsonify({'error': 'Not authorized'}), 403
    msg.is_deleted = True
    db.session.commit()
    return jsonify({'success': True})
