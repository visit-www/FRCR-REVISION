/**
 * Content Interact — Reusable notes, highlights, and discussion forum.
 *
 * Works with ANY content type via /api/content/<type>/<key>/ endpoints.
 * Drop into any page with:
 *
 *   ContentInteract.init({
 *     contentType: 'osce_ref',
 *     contentKey: 'cxr',
 *     notesContainer: '#myNotesDiv',        // optional
 *     highlightContainers: ['.my-content'],  // optional — CSS selectors of highlightable areas
 *     forumContainer: '#myForumDiv',         // optional
 *   });
 *
 * Extracted from view_case.html (battle-tested notes/highlights/forum).
 */
var ContentInteract = (function() {
  'use strict';

  var API_BASE = '/api/content';
  var _cfg = {};
  var _noteSaveTimer = null;

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
    // Create a brief toast notification
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


  // =========================================================================
  // NOTES
  // =========================================================================

  function _initNotes() {
    var container = document.querySelector(_cfg.notesContainer);
    if (!container) return;

    container.innerHTML =
      '<div class="ci-notes-panel">'
      + '<div class="ci-notes-header">'
      +   '<span class="ci-notes-title"><i class="fas fa-sticky-note me-1"></i>My Notes</span>'
      +   '<span class="ci-notes-status" id="ciNoteStatus"></span>'
      + '</div>'
      + '<textarea class="ci-notes-textarea" id="ciNoteText" placeholder="Type your notes here... (auto-saves)"></textarea>'
      + '<div class="ci-notes-actions">'
      +   '<button class="ci-btn ci-btn-sm ci-btn-danger" id="ciNoteClear" title="Clear notes"><i class="fas fa-trash me-1"></i>Clear</button>'
      + '</div>'
      + '</div>';

    var textarea = document.getElementById('ciNoteText');
    var status = document.getElementById('ciNoteStatus');
    var clearBtn = document.getElementById('ciNoteClear');

    // Load existing note
    _api('GET', _contentPath() + '/note').then(function(data) {
      if (data.note_text) {
        textarea.value = data.note_text;
        if (data.updated_at) {
          status.innerHTML = '<i class="fas fa-check-circle text-success me-1"></i>Saved';
        }
      }
    });

    // Auto-save on typing (debounced 1.5s)
    textarea.addEventListener('input', function() {
      status.innerHTML = '<i class="fas fa-circle text-warning me-1" style="font-size:0.5rem;"></i>Unsaved';
      clearTimeout(_noteSaveTimer);
      _noteSaveTimer = setTimeout(function() {
        var text = textarea.value.trim();
        if (!text) return;
        _api('POST', _contentPath() + '/note', { note_text: text }).then(function(data) {
          if (data.success) {
            var now = new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
            status.innerHTML = '<i class="fas fa-check-circle text-success me-1"></i>Saved at ' + now;
          }
        });
      }, 1500);
    });

    // Clear button
    clearBtn.addEventListener('click', function() {
      if (!confirm('Clear your notes for this section?')) return;
      textarea.value = '';
      _api('DELETE', _contentPath() + '/note').then(function() {
        status.innerHTML = '<i class="fas fa-check-circle text-muted me-1"></i>Cleared';
      });
    });
  }


  // =========================================================================
  // HIGHLIGHTS
  // =========================================================================

  function _initHighlights() {
    if (!_cfg.highlightContainers || !_cfg.highlightContainers.length) return;

    // Load saved highlights
    _api('GET', _contentPath() + '/highlights').then(function(data) {
      if (data.success && data.highlights) {
        data.highlights.forEach(function(h) {
          _renderSavedHighlight(h);
        });
      }
    });

    // Listen for text selection in highlight containers
    _cfg.highlightContainers.forEach(function(sel) {
      var els = document.querySelectorAll(sel);
      els.forEach(function(el) {
        el.addEventListener('mouseup', function(e) {
          var selection = window.getSelection();
          if (!selection || selection.isCollapsed) return;
          var selectedText = selection.toString().trim();
          if (selectedText.length < 3 || selectedText.length > 500) return;

          // Show highlight popup
          _showHighlightPopup(e, selectedText, el);
        });
      });
    });
  }

  function _showHighlightPopup(event, text, element) {
    // Remove existing popup
    var old = document.getElementById('ciHighlightPopup');
    if (old) old.remove();

    var colors = [
      { name: 'yellow', hex: '#FFEB3B' },
      { name: 'green', hex: '#A5D6A7' },
      { name: 'pink', hex: '#F48FB1' },
      { name: 'blue', hex: '#90CAF9' },
    ];

    var popup = document.createElement('div');
    popup.id = 'ciHighlightPopup';
    popup.className = 'ci-highlight-popup';
    popup.innerHTML = '<span class="ci-highlight-popup-label">Highlight:</span> '
      + colors.map(function(c) {
        return '<button class="ci-highlight-color-btn" data-color="' + c.name + '" style="background:' + c.hex + ';" title="' + c.name + '"></button>';
      }).join('');
    popup.style.left = event.pageX + 'px';
    popup.style.top = (event.pageY - 40) + 'px';
    document.body.appendChild(popup);

    popup.querySelectorAll('.ci-highlight-color-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        _createHighlight(text, this.dataset.color, element);
        popup.remove();
      });
    });

    // Remove popup on click elsewhere
    setTimeout(function() {
      document.addEventListener('click', function handler(e) {
        if (!popup.contains(e.target)) {
          popup.remove();
          document.removeEventListener('click', handler);
        }
      });
    }, 100);
  }

  function _createHighlight(text, color, element) {
    var selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;

    var range = selection.getRangeAt(0);
    var fieldName = element.dataset.field || element.id || 'content';
    var fullText = element.textContent || '';
    var startIndex = fullText.indexOf(text);
    var contextBefore = startIndex > 0 ? fullText.substring(Math.max(0, startIndex - 50), startIndex) : '';
    var contextAfter = startIndex >= 0 ? fullText.substring(startIndex + text.length, startIndex + text.length + 50) : '';

    var colorMap = { yellow: '#FFEB3B', green: '#A5D6A7', pink: '#F48FB1', blue: '#90CAF9' };

    try {
      var mark = document.createElement('mark');
      mark.className = 'ci-user-highlight';
      mark.style.backgroundColor = colorMap[color] || '#FFEB3B';
      mark.style.cursor = 'pointer';
      mark.title = 'Click to remove';
      range.surroundContents(mark);
      selection.removeAllRanges();

      _api('POST', _contentPath() + '/highlight', {
        text_content: text,
        highlight_color: color,
        field_name: fieldName,
        context_before: contextBefore,
        context_after: contextAfter
      }).then(function(data) {
        if (data.success) {
          mark.dataset.highlightId = data.id;
          mark.addEventListener('click', function(e) {
            e.stopPropagation();
            if (confirm('Remove this highlight?')) {
              _deleteHighlight(data.id, mark);
            }
          });
          _flash('Highlighted!', 'success');
        } else {
          _unwrapMark(mark);
        }
      }).catch(function() { _unwrapMark(mark); });
    } catch (e) {
      _flash('Cannot highlight across elements', 'warning');
    }
  }

  function _renderSavedHighlight(h) {
    // Find the text in highlight containers and wrap it
    var colorMap = { yellow: '#FFEB3B', green: '#A5D6A7', pink: '#F48FB1', blue: '#90CAF9' };
    var containers = [];
    (_cfg.highlightContainers || []).forEach(function(sel) {
      document.querySelectorAll(sel).forEach(function(el) { containers.push(el); });
    });

    for (var i = 0; i < containers.length; i++) {
      var el = containers[i];
      if (_highlightTextInElement(el, h.text_content, h.context_before, h.context_after, colorMap[h.highlight_color] || '#FFEB3B', h.id)) {
        break;
      }
    }
  }

  function _highlightTextInElement(container, text, ctxBefore, ctxAfter, bgColor, highlightId) {
    // Use TreeWalker to find text nodes containing the highlight text
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
    var node;
    while ((node = walker.nextNode())) {
      var idx = node.textContent.indexOf(text);
      if (idx === -1) continue;

      // Verify context if available
      if (ctxBefore) {
        var fullBefore = '';
        var prev = node.previousSibling;
        while (prev) { fullBefore = (prev.textContent || '') + fullBefore; prev = prev.previousSibling; }
        fullBefore += node.textContent.substring(0, idx);
        if (fullBefore.length >= ctxBefore.length && !fullBefore.endsWith(ctxBefore)) continue;
      }

      var range = document.createRange();
      range.setStart(node, idx);
      range.setEnd(node, idx + text.length);
      var mark = document.createElement('mark');
      mark.className = 'ci-user-highlight';
      mark.style.backgroundColor = bgColor;
      mark.style.cursor = 'pointer';
      mark.title = 'Click to remove';
      mark.dataset.highlightId = highlightId;
      try {
        range.surroundContents(mark);
        mark.addEventListener('click', function(e) {
          e.stopPropagation();
          if (confirm('Remove this highlight?')) {
            _deleteHighlight(parseInt(this.dataset.highlightId), this);
          }
        });
        return true;
      } catch (e) { return false; }
    }
    return false;
  }

  function _deleteHighlight(id, markEl) {
    _api('DELETE', '/highlight/' + id).then(function(data) {
      if (data.success) {
        _unwrapMark(markEl);
        _flash('Highlight removed', 'success');
      }
    });
  }

  function _unwrapMark(mark) {
    var parent = mark.parentNode;
    while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
    parent.removeChild(mark);
  }


  // =========================================================================
  // DISCUSSION FORUM
  // =========================================================================

  function _initForum() {
    var container = document.querySelector(_cfg.forumContainer);
    if (!container) return;

    container.innerHTML =
      '<div class="ci-forum-panel">'
      + '<div class="ci-forum-header">'
      +   '<span class="ci-forum-title"><i class="fas fa-comments me-1"></i>Discussion</span>'
      +   '<span class="ci-forum-count" id="ciForumCount"></span>'
      + '</div>'
      + '<div class="ci-forum-messages" id="ciForumMessages"></div>'
      + '<div class="ci-forum-compose">'
      +   '<textarea class="ci-forum-input" id="ciForumInput" placeholder="Join the discussion..." rows="2"></textarea>'
      +   '<div class="ci-forum-compose-actions">'
      +     '<button class="ci-btn ci-btn-sm ci-btn-primary" id="ciForumSend"><i class="fas fa-paper-plane me-1"></i>Post</button>'
      +   '</div>'
      + '</div>'
      + '</div>';

    _loadForumMessages();

    document.getElementById('ciForumSend').addEventListener('click', function() {
      var input = document.getElementById('ciForumInput');
      var text = input.value.trim();
      if (!text) return;
      this.disabled = true;
      _api('POST', _contentPath() + '/forum', { content: text }).then(function(data) {
        document.getElementById('ciForumSend').disabled = false;
        if (data.success) {
          input.value = '';
          _loadForumMessages();
        } else {
          _flash(data.error || 'Failed to post', 'error');
        }
      }).catch(function() {
        document.getElementById('ciForumSend').disabled = false;
      });
    });
  }

  function _loadForumMessages() {
    _api('GET', _contentPath() + '/forum').then(function(data) {
      var msgDiv = document.getElementById('ciForumMessages');
      var countEl = document.getElementById('ciForumCount');
      if (!data.success) return;

      if (countEl) countEl.textContent = data.total ? '(' + data.total + ')' : '';

      if (!data.messages || !data.messages.length) {
        msgDiv.innerHTML = '<p class="ci-forum-empty">No messages yet. Start the discussion!</p>';
        return;
      }

      msgDiv.innerHTML = data.messages.map(function(m) {
        var voteUp = m.user_vote === 1 ? ' ci-vote-active' : '';
        var voteDown = m.user_vote === -1 ? ' ci-vote-active' : '';
        return '<div class="ci-forum-msg' + (m.is_pinned ? ' ci-forum-msg-pinned' : '') + '">'
          + '<div class="ci-forum-msg-header">'
          +   (m.user_picture ? '<img src="' + _esc(m.user_picture) + '" class="ci-forum-avatar">' : '<i class="fas fa-user-circle ci-forum-avatar-icon"></i>')
          +   '<span class="ci-forum-msg-author">' + _esc(m.user_name) + (m.is_admin ? ' <span class="ci-badge-admin">Admin</span>' : '') + '</span>'
          +   '<span class="ci-forum-msg-time">' + _timeAgo(m.created_at) + '</span>'
          +   (m.is_pinned ? '<span class="ci-badge-pinned"><i class="fas fa-thumbtack"></i></span>' : '')
          + '</div>'
          + '<div class="ci-forum-msg-body">' + _esc(m.content) + '</div>'
          + (m.image_thumbnail_url ? '<img src="' + _esc(m.image_thumbnail_url) + '" class="ci-forum-msg-img">' : '')
          + '<div class="ci-forum-msg-actions">'
          +   '<button class="ci-vote-btn' + voteUp + '" onclick="ContentInteract.vote(' + m.id + ', 1)"><i class="fas fa-arrow-up"></i></button>'
          +   '<span class="ci-vote-score">' + m.vote_score + '</span>'
          +   '<button class="ci-vote-btn' + voteDown + '" onclick="ContentInteract.vote(' + m.id + ', -1)"><i class="fas fa-arrow-down"></i></button>'
          +   (m.is_own ? '<button class="ci-delete-btn" onclick="ContentInteract.deleteMsg(' + m.id + ')"><i class="fas fa-trash"></i></button>' : '')
          + '</div>'
          + '</div>';
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
        console.error('[ContentInteract] contentType and contentKey are required');
        return;
      }
      if (_cfg.notesContainer) _initNotes();
      if (_cfg.highlightContainers) _initHighlights();
      if (_cfg.forumContainer) _initForum();
    },

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
