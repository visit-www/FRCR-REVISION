/**
 * Content Interact v2 — Notes side panel, highlights, linked notes, discussion forum.
 *
 * Usage:
 *   ContentInteract.init({
 *     contentType: 'osce_ref',
 *     contentKey: 'cxr',
 *     contentArea: '#mainContent',             // main content container (will resize to 80%)
 *     notesToggleBtn: '#notesToggleBtn',        // toggle button for notes panel
 *     highlightContainers: ['.my-content'],     // CSS selectors of highlightable areas
 *     forumContainer: '#myForumDiv',            // optional
 *   });
 *
 * Features:
 *   - Side panel (20% width) with notes, toggled via button
 *   - Text selection → popup with Highlight + Add Note buttons
 *   - Linked notes: selected text is captured as reference, superscript markers in content
 *   - Discussion forum with voting
 */
var ContentInteract = (function() {
  'use strict';

  var API_BASE = '/api/content';
  var _cfg = {};
  var _noteSaveTimer = null;
  var _noteCounter = 0;
  var _panelOpen = false;

  // ── Helpers ──
  function _esc(s) {
    if (!s) return '';
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function _timeAgo(isoStr) {
    if (!isoStr) return '';
    var d = new Date(isoStr);
    var now = new Date();
    var diff = Math.floor((now - d) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    if (diff < 604800) return Math.floor(diff / 86400) + 'd ago';
    return d.toLocaleDateString();
  }

  function _flash(msg, type) {
    var toast = document.createElement('div');
    toast.className = 'ci-toast ci-toast-' + (type || 'info');
    toast.innerHTML = '<i class="fas fa-' + (type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle') + ' me-1"></i>' + _esc(msg);
    document.body.appendChild(toast);
    setTimeout(function() { toast.classList.add('ci-toast-show'); }, 10);
    setTimeout(function() { toast.classList.remove('ci-toast-show'); setTimeout(function() { toast.remove(); }, 300); }, 2500);
  }

  function _api(method, path, body) {
    var opts = { method: method, headers: {} };
    if (body && !(body instanceof FormData)) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    } else if (body) {
      opts.body = body;
    }
    return fetch(API_BASE + path, opts).then(function(r) { return r.json(); });
  }

  function _contentPath() {
    return '/' + _cfg.contentType + '/' + _cfg.contentKey;
  }

  function _generateNoteId() {
    _noteCounter++;
    return 'n' + Date.now().toString(36) + _noteCounter;
  }


  // =========================================================================
  // SIDE PANEL
  // =========================================================================

  var _panel = null;
  var _contentArea = null;

  function _createSidePanel() {
    // Create the panel element
    _panel = document.getElementById('ciSidePanel');
    if (_panel) return; // already created

    _panel = document.createElement('div');
    _panel.id = 'ciSidePanel';
    _panel.className = 'ci-side-panel';
    _panel.innerHTML =
      '<div class="ci-side-panel-header">'
      + '<span class="ci-side-panel-title"><i class="fas fa-sticky-note me-1"></i>My Notes</span>'
      + '<button class="ci-side-panel-close" id="ciPanelClose" title="Close notes"><i class="fas fa-times"></i></button>'
      + '</div>'
      + '<div class="ci-side-panel-status" id="ciPanelStatus"></div>'
      + '<textarea class="ci-side-panel-textarea" id="ciPanelNotes" placeholder="Type your notes here...\n\nTip: Select text in the content and click \'Add Note\' to link it here."></textarea>'
      + '<div class="ci-side-panel-footer">'
      +   '<button class="ci-btn ci-btn-sm ci-btn-danger" id="ciPanelClear"><i class="fas fa-trash me-1"></i>Clear</button>'
      + '</div>'
      // Discussion forum below notes
      + '<div class="ci-side-panel-divider"></div>'
      + '<div class="ci-side-panel-forum" id="ciPanelForum"></div>';

    document.body.appendChild(_panel);

    // Close button
    document.getElementById('ciPanelClose').addEventListener('click', function() {
      _togglePanel(false);
    });

    // Clear button
    document.getElementById('ciPanelClear').addEventListener('click', function() {
      if (!confirm('Clear all your notes for this section?')) return;
      var textarea = document.getElementById('ciPanelNotes');
      textarea.value = '';
      textarea.dataset.rawNotes = '';
      _api('DELETE', _contentPath() + '/note').then(function() {
        document.getElementById('ciPanelStatus').innerHTML = '<i class="fas fa-check-circle text-muted me-1"></i>Cleared';
      });
    });

    // Auto-save on typing
    var textarea = document.getElementById('ciPanelNotes');
    textarea.addEventListener('input', function() {
      document.getElementById('ciPanelStatus').innerHTML = '<i class="fas fa-circle text-warning me-1" style="font-size:0.5rem;"></i>Unsaved';
      clearTimeout(_noteSaveTimer);
      _noteSaveTimer = setTimeout(function() {
        _saveNotes();
      }, 1500);
    });
  }

  function _togglePanel(forceState) {
    _panelOpen = (forceState !== undefined) ? forceState : !_panelOpen;

    _contentArea = document.querySelector(_cfg.contentArea);
    if (!_contentArea) return;

    if (_panelOpen) {
      _panel.classList.add('ci-side-panel-open');
      _contentArea.classList.add('ci-content-shifted');
      // Load notes + forum
      _loadNotes();
      _initForum();
    } else {
      _panel.classList.remove('ci-side-panel-open');
      _contentArea.classList.remove('ci-content-shifted');
    }

    // Update toggle button state
    var btn = document.querySelector(_cfg.notesToggleBtn);
    if (btn) {
      btn.classList.toggle('ci-toggle-active', _panelOpen);
    }
  }


  // =========================================================================
  // NOTES (in side panel)
  // =========================================================================

  function _loadNotes() {
    _api('GET', _contentPath() + '/note').then(function(data) {
      var textarea = document.getElementById('ciPanelNotes');
      var status = document.getElementById('ciPanelStatus');
      if (data.note_text) {
        // Store raw notes (with tags) and display formatted
        textarea.dataset.rawNotes = data.note_text;
        textarea.value = _formatNotesForDisplay(data.note_text);
        if (data.updated_at) {
          status.innerHTML = '<i class="fas fa-check-circle text-success me-1"></i>Saved';
        }
        // Render markers in content
        setTimeout(function() { _renderNoteMarkers(data.note_text); }, 500);
      }
    });
  }

  function _saveNotes() {
    var textarea = document.getElementById('ciPanelNotes');
    var raw = textarea.dataset.rawNotes || textarea.value;
    if (!raw.trim()) return;
    _api('POST', _contentPath() + '/note', { note_text: raw }).then(function(data) {
      if (data.success) {
        var now = new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
        document.getElementById('ciPanelStatus').innerHTML = '<i class="fas fa-check-circle text-success me-1"></i>Saved at ' + now;
      }
    });
  }

  function _formatNotesForDisplay(rawNotes) {
    // Convert [note:ID][from CTX][text:SEL] content [/note:ID] → bullet points
    return rawNotes.replace(/\[note:[^\]]+\]\[from ([^\]]+)\](?:\[text:[^\]]*\])?\s*(.*?)\[\/note:[^\]]+\]/gs, function(match, ctx, content) {
      return '\n\u2022 ' + content.trim();
    }).trim();
  }

  function _addLinkedNote(selectedText, fieldName, userNote) {
    var noteId = _generateNoteId();
    var ctx = fieldName || 'content';
    var escapedText = selectedText.replace(/\]/g, '\\]').substring(0, 100);
    var fragment = '\n\n[note:' + noteId + '][from ' + ctx + '][text:' + escapedText + '] ' + userNote + '[/note:' + noteId + ']';

    var textarea = document.getElementById('ciPanelNotes');
    if (!textarea) return;

    var raw = (textarea.dataset.rawNotes || textarea.value || '') + fragment;
    textarea.dataset.rawNotes = raw;
    textarea.value = _formatNotesForDisplay(raw);
    _saveNotes();

    // Add marker in content
    _addSingleMarker(selectedText, noteId);
    _flash('Note added!', 'success');
  }


  // =========================================================================
  // NOTE MARKERS (superscript in content)
  // =========================================================================

  function _renderNoteMarkers(rawNotes) {
    if (!rawNotes) return;
    var pattern = /\[note:([^\]]+)\]\[from ([^\]]+)\](?:\[text:([^\]]*)\])?\s*(.*?)\[\/note:\1\]/gs;
    var match;
    while ((match = pattern.exec(rawNotes)) !== null) {
      var noteId = match[1];
      var selectedText = match[3] ? match[3].replace(/\\\]/g, ']') : null;
      if (!selectedText || document.querySelector('[data-note-id="' + noteId + '"]')) continue;
      _addSingleMarker(selectedText, noteId);
    }
  }

  function _addSingleMarker(text, noteId) {
    var containers = [];
    (_cfg.highlightContainers || []).forEach(function(sel) {
      document.querySelectorAll(sel).forEach(function(el) { containers.push(el); });
    });
    for (var i = 0; i < containers.length; i++) {
      if (_insertMarkerInElement(containers[i], text, noteId)) break;
    }
  }

  function _insertMarkerInElement(container, text, noteId) {
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
    var node;
    while ((node = walker.nextNode())) {
      var idx = node.textContent.indexOf(text);
      if (idx === -1) continue;
      try {
        var range = document.createRange();
        range.setStart(node, idx + text.length);
        range.setEnd(node, idx + text.length);
        var marker = document.createElement('sup');
        marker.className = 'ci-note-marker';
        marker.dataset.noteId = noteId;
        marker.innerHTML = '<i class="fas fa-sticky-note"></i>';
        marker.title = 'Click to view note';
        marker.addEventListener('click', function(e) {
          e.stopPropagation();
          // Open panel and scroll to note
          if (!_panelOpen) _togglePanel(true);
          _flash('Note is in the side panel', 'info');
        });
        range.insertNode(marker);
        return true;
      } catch (e) { /* skip */ }
    }
    return false;
  }


  // =========================================================================
  // TEXT SELECTION → POPUP (Highlight + Add Note)
  // =========================================================================

  function _initSelection() {
    if (!_cfg.highlightContainers || !_cfg.highlightContainers.length) return;

    // Load saved highlights
    _api('GET', _contentPath() + '/highlights').then(function(data) {
      if (data.success && data.highlights) {
        data.highlights.forEach(function(h) { _renderSavedHighlight(h); });
      }
    });

    // Listen for text selection
    document.addEventListener('mouseup', _handleSelection);
  }

  function _handleSelection(e) {
    // Don't trigger on buttons/links
    if (e.target.closest('button, a, .btn, .ci-side-panel, .ci-highlight-popup, #ciNotePopup')) return;

    var selection = window.getSelection();
    if (!selection || selection.isCollapsed) return;
    var text = selection.toString().trim();
    if (text.length < 3 || text.length > 500) return;

    // Check if selection is inside a highlightable area
    var range = selection.getRangeAt(0);
    var ancestor = range.commonAncestorContainer;
    var el = ancestor.nodeType === Node.TEXT_NODE ? ancestor.parentElement : ancestor;
    var annotatable = null;
    (_cfg.highlightContainers || []).forEach(function(sel) {
      if (!annotatable && el.closest(sel)) annotatable = el.closest(sel);
    });
    if (!annotatable) return;

    _showSelectionPopup(e, text, annotatable);
  }

  function _showSelectionPopup(event, text, element) {
    var old = document.getElementById('ciSelectionPopup');
    if (old) old.remove();

    var popup = document.createElement('div');
    popup.id = 'ciSelectionPopup';
    popup.className = 'ci-selection-popup';
    popup.innerHTML =
      '<button class="ci-sel-btn ci-sel-highlight" title="Highlight"><i class="fas fa-highlighter"></i> Highlight</button>'
      + '<button class="ci-sel-btn ci-sel-note" title="Add Note"><i class="fas fa-sticky-note"></i> Note</button>';

    var x = event.clientX || 0;
    var y = event.clientY || 0;
    popup.style.left = x + 'px';
    popup.style.top = Math.max(10, y - 50) + 'px';
    document.body.appendChild(popup);

    var fieldName = element.dataset.field || element.id || 'content';

    // Highlight button
    popup.querySelector('.ci-sel-highlight').addEventListener('click', function() {
      _createHighlight(text, 'yellow', element);
      popup.remove();
    });

    // Note button
    popup.querySelector('.ci-sel-note').addEventListener('click', function() {
      popup.remove();
      _openNotePopup(text, fieldName);
    });

    // Close on click outside
    setTimeout(function() {
      document.addEventListener('click', function handler(e) {
        if (!popup.contains(e.target)) { popup.remove(); document.removeEventListener('click', handler); }
      });
    }, 100);
  }


  // =========================================================================
  // NOTE POPUP (linked note entry)
  // =========================================================================

  function _openNotePopup(selectedText, fieldName) {
    var old = document.getElementById('ciNotePopup');
    if (old) old.remove();

    var popup = document.createElement('div');
    popup.id = 'ciNotePopup';
    popup.className = 'ci-note-popup';
    popup.innerHTML =
      '<div class="ci-note-popup-header">'
      + '<span><i class="fas fa-sticky-note me-1"></i>Add Note</span>'
      + '<button class="ci-note-popup-close" id="ciNotePopupClose"><i class="fas fa-times"></i></button>'
      + '</div>'
      + '<div class="ci-note-popup-ref">'
      + '<i class="fas fa-quote-left me-1" style="color:#9ca3af;"></i>'
      + '<span class="ci-note-popup-ref-text">' + _esc(selectedText.substring(0, 120)) + (selectedText.length > 120 ? '...' : '') + '</span>'
      + '</div>'
      + '<textarea class="ci-note-popup-input" id="ciNotePopupInput" placeholder="Type your note about this text..." rows="3"></textarea>'
      + '<div class="ci-note-popup-actions">'
      + '<button class="ci-btn ci-btn-sm ci-btn-primary" id="ciNotePopupSave"><i class="fas fa-save me-1"></i>Save Note</button>'
      + '</div>';

    document.body.appendChild(popup);

    // Auto-open panel if closed
    if (!_panelOpen) _togglePanel(true);

    // Focus input
    setTimeout(function() { document.getElementById('ciNotePopupInput').focus(); }, 100);

    // Close
    document.getElementById('ciNotePopupClose').addEventListener('click', function() { popup.remove(); });

    // Save
    document.getElementById('ciNotePopupSave').addEventListener('click', function() {
      var noteText = document.getElementById('ciNotePopupInput').value.trim();
      if (!noteText) { _flash('Please type a note', 'warning'); return; }
      _addLinkedNote(selectedText, fieldName, noteText);
      popup.remove();
    });

    // Enter to save
    document.getElementById('ciNotePopupInput').addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        document.getElementById('ciNotePopupSave').click();
      }
    });
  }


  // =========================================================================
  // HIGHLIGHTS
  // =========================================================================

  function _createHighlight(text, color, element) {
    var selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;
    var range = selection.getRangeAt(0);
    var fieldName = element.dataset.field || element.id || 'content';
    var fullText = element.textContent || '';
    var startIndex = fullText.indexOf(text);
    var contextBefore = startIndex > 0 ? fullText.substring(Math.max(0, startIndex - 50), startIndex) : '';
    var contextAfter = startIndex >= 0 ? fullText.substring(startIndex + text.length, startIndex + text.length + 50) : '';

    try {
      var mark = document.createElement('mark');
      mark.className = 'ci-user-highlight';
      mark.style.backgroundColor = '#FFEB3B';
      mark.style.cursor = 'pointer';
      mark.title = 'Click to remove';
      range.surroundContents(mark);
      selection.removeAllRanges();

      _api('POST', _contentPath() + '/highlight', {
        text_content: text, highlight_color: color, field_name: fieldName,
        context_before: contextBefore, context_after: contextAfter
      }).then(function(data) {
        if (data.success) {
          mark.dataset.highlightId = data.id;
          mark.addEventListener('click', function(e) {
            e.stopPropagation();
            if (confirm('Remove this highlight?')) _deleteHighlight(data.id, mark);
          });
          _flash('Highlighted!', 'success');
        } else { _unwrapMark(mark); }
      }).catch(function() { _unwrapMark(mark); });
    } catch (e) { _flash('Cannot highlight across elements', 'warning'); }
  }

  function _renderSavedHighlight(h) {
    var containers = [];
    (_cfg.highlightContainers || []).forEach(function(sel) {
      document.querySelectorAll(sel).forEach(function(el) { containers.push(el); });
    });
    for (var i = 0; i < containers.length; i++) {
      if (_highlightInElement(containers[i], h.text_content, h.context_before, h.id)) break;
    }
  }

  function _highlightInElement(container, text, ctxBefore, highlightId) {
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
    var node;
    while ((node = walker.nextNode())) {
      var idx = node.textContent.indexOf(text);
      if (idx === -1) continue;
      try {
        var range = document.createRange();
        range.setStart(node, idx);
        range.setEnd(node, idx + text.length);
        var mark = document.createElement('mark');
        mark.className = 'ci-user-highlight';
        mark.style.backgroundColor = '#FFEB3B';
        mark.style.cursor = 'pointer';
        mark.title = 'Click to remove';
        mark.dataset.highlightId = highlightId;
        range.surroundContents(mark);
        mark.addEventListener('click', function(e) {
          e.stopPropagation();
          if (confirm('Remove this highlight?')) _deleteHighlight(parseInt(this.dataset.highlightId), this);
        });
        return true;
      } catch (e) { return false; }
    }
    return false;
  }

  function _deleteHighlight(id, markEl) {
    _api('DELETE', '/highlight/' + id).then(function(data) {
      if (data.success) { _unwrapMark(markEl); _flash('Highlight removed', 'success'); }
    });
  }

  function _unwrapMark(mark) {
    var parent = mark.parentNode;
    while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
    parent.removeChild(mark);
  }


  // =========================================================================
  // DISCUSSION FORUM (in side panel)
  // =========================================================================

  function _initForum() {
    var container = document.getElementById('ciPanelForum');
    if (!container) return;

    container.innerHTML =
      '<div class="ci-forum-header">'
      + '<span class="ci-forum-title"><i class="fas fa-comments me-1"></i>Discussion</span>'
      + '<span class="ci-forum-count" id="ciForumCount"></span>'
      + '</div>'
      + '<div class="ci-forum-messages" id="ciForumMessages"></div>'
      + '<div class="ci-forum-compose">'
      + '<textarea class="ci-forum-input" id="ciForumInput" placeholder="Join the discussion..." rows="2"></textarea>'
      + '<div class="ci-forum-compose-actions">'
      + '<button class="ci-btn ci-btn-sm ci-btn-primary" id="ciForumSend"><i class="fas fa-paper-plane me-1"></i>Post</button>'
      + '</div></div>';

    _loadForumMessages();

    document.getElementById('ciForumSend').addEventListener('click', function() {
      var input = document.getElementById('ciForumInput');
      var text = input.value.trim();
      if (!text) return;
      this.disabled = true;
      _api('POST', _contentPath() + '/forum', { content: text }).then(function(data) {
        document.getElementById('ciForumSend').disabled = false;
        if (data.success) { input.value = ''; _loadForumMessages(); }
        else _flash(data.error || 'Failed', 'error');
      }).catch(function() { document.getElementById('ciForumSend').disabled = false; });
    });
  }

  function _loadForumMessages() {
    _api('GET', _contentPath() + '/forum').then(function(data) {
      var msgDiv = document.getElementById('ciForumMessages');
      var countEl = document.getElementById('ciForumCount');
      if (!data.success) return;
      if (countEl) countEl.textContent = data.total ? '(' + data.total + ')' : '';
      if (!data.messages || !data.messages.length) {
        msgDiv.innerHTML = '<p class="ci-forum-empty">No messages yet.</p>';
        return;
      }
      msgDiv.innerHTML = data.messages.map(function(m) {
        var voteUp = m.user_vote === 1 ? ' ci-vote-active' : '';
        var voteDown = m.user_vote === -1 ? ' ci-vote-active' : '';
        return '<div class="ci-forum-msg' + (m.is_pinned ? ' ci-forum-msg-pinned' : '') + '">'
          + '<div class="ci-forum-msg-header">'
          + '<span class="ci-forum-msg-author">' + _esc(m.user_name) + (m.is_admin ? ' <span class="ci-badge-admin">Admin</span>' : '') + '</span>'
          + '<span class="ci-forum-msg-time">' + _timeAgo(m.created_at) + '</span>'
          + '</div>'
          + '<div class="ci-forum-msg-body">' + _esc(m.content) + '</div>'
          + '<div class="ci-forum-msg-actions">'
          + '<button class="ci-vote-btn' + voteUp + '" onclick="ContentInteract.vote(' + m.id + ', 1)"><i class="fas fa-arrow-up"></i></button>'
          + '<span class="ci-vote-score">' + m.vote_score + '</span>'
          + '<button class="ci-vote-btn' + voteDown + '" onclick="ContentInteract.vote(' + m.id + ', -1)"><i class="fas fa-arrow-down"></i></button>'
          + (m.is_own ? '<button class="ci-delete-btn" onclick="ContentInteract.deleteMsg(' + m.id + ')"><i class="fas fa-trash"></i></button>' : '')
          + '</div></div>';
      }).join('');
    });
  }


  // =========================================================================
  // PUBLIC API
  // =========================================================================

  return {
    init: function(config) {
      _cfg = config;
      if (!_cfg.contentType || !_cfg.contentKey) {
        console.error('[ContentInteract] contentType and contentKey required');
        return;
      }
      _createSidePanel();
      _initSelection();

      // Toggle button
      if (_cfg.notesToggleBtn) {
        var btn = document.querySelector(_cfg.notesToggleBtn);
        if (btn) {
          btn.addEventListener('click', function() { _togglePanel(); });
        }
      }
    },

    toggle: function() { _togglePanel(); },

    vote: function(msgId, value) {
      _api('POST', '/forum/' + msgId + '/vote', { vote: value }).then(function(data) {
        if (data.success) _loadForumMessages();
      });
    },

    deleteMsg: function(msgId) {
      if (!confirm('Delete this message?')) return;
      _api('DELETE', '/forum/' + msgId).then(function(data) {
        if (data.success) _loadForumMessages();
      });
    }
  };
})();
