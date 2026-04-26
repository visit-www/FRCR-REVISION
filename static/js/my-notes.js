/**
 * My Study Notes — Evernote-like unified notes dashboard.
 */
(function() {
  'use strict';

  var _notes = [];
  var _filtered = [];
  var _selectedId = null;
  var _saveTimer = null;
  var _currentFilter = { type: 'all', tag: null, starred: false, search: '', sort: 'recent', bodySection: null };

  // ── Helpers ──
  function esc(s) {
    if (!s) return '';
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function timeAgo(isoStr) {
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

  function stripNoteTags(raw) {
    if (!raw) return '';
    return raw.replace(/\[note:[^\]]+\]\[from [^\]]+\](?:\[text:[^\]]*\])?\s*/gs, '')
              .replace(/\[\/note:[^\]]+\]/gs, '').trim();
  }

  function preview(text, len) {
    var clean = stripNoteTags(text);
    return clean.length > (len || 120) ? clean.substring(0, len || 120) + '...' : clean;
  }

  // ── API ──
  function api(method, url, body) {
    var opts = { method: method, headers: {} };
    if (body) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
    return fetch(url, opts).then(function(r) { return r.json(); });
  }

  // ── Load data ──
  function loadNotes() {
    var params = [];
    if (_currentFilter.type !== 'all' && _currentFilter.type !== 'starred') {
      params.push('content_type=' + encodeURIComponent(_currentFilter.type));
    }
    if (_currentFilter.starred || _currentFilter.type === 'starred') {
      params.push('starred=1');
    }
    if (_currentFilter.tag) { params.push('tag=' + encodeURIComponent(_currentFilter.tag)); }
    if (_currentFilter.search) { params.push('search=' + encodeURIComponent(_currentFilter.search)); }
    if (_currentFilter.bodySection) { params.push('body_section=' + encodeURIComponent(_currentFilter.bodySection)); }

    var url = '/api/my-notes' + (params.length ? '?' + params.join('&') : '');
    api('GET', url).then(function(data) {
      if (!data.success) return;
      _notes = data.notes;
      _applySort();
      renderList();
      // Update total count
      var countAll = document.getElementById('mnCountAll');
      if (countAll) countAll.textContent = data.total;
    });
  }

  function loadStats() {
    api('GET', '/api/my-notes/stats').then(function(data) {
      if (!data.success) return;
      var container = document.getElementById('mnNotebooks');
      if (!container) return;
      var html = '';
      var notebooks = data.notebooks || {};
      var types = Object.keys(notebooks).sort(function(a, b) {
        return (notebooks[b].count || 0) - (notebooks[a].count || 0);
      });
      types.forEach(function(ct) {
        var nb = notebooks[ct];
        html += '<a class="mn-sidebar-item" data-filter="' + esc(ct) + '" href="#">'
          + '<i class="fas ' + esc(nb.icon) + ' me-2" style="color:' + esc(nb.color) + ';width:16px;text-align:center;"></i>'
          + esc(nb.label) + ' <span class="mn-count">' + nb.count + '</span></a>';
      });
      container.innerHTML = html || '<span class="mn-sidebar-empty">No notebooks yet</span>';

      // Starred count
      var starredCount = 0;
      _notes.forEach(function(n) { if (n.is_starred) starredCount++; });
      var cs = document.getElementById('mnCountStarred');
      if (cs) cs.textContent = starredCount;

      // Bind clicks
      container.querySelectorAll('.mn-sidebar-item').forEach(function(el) {
        el.addEventListener('click', function(e) {
          e.preventDefault();
          _setFilter('type', this.dataset.filter);
        });
      });
    });
  }

  function loadTags() {
    api('GET', '/api/my-notes/tags').then(function(data) {
      if (!data.success) return;
      var container = document.getElementById('mnTags');
      if (!container) return;
      if (!data.tags || !data.tags.length) {
        container.innerHTML = '<span class="mn-sidebar-empty">No tags yet</span>';
        return;
      }
      container.innerHTML = data.tags.map(function(t) {
        return '<button class="mn-sidebar-tag" data-tag="' + esc(t.tag) + '">'
          + esc(t.tag) + ' <span style="opacity:0.6;">(' + t.count + ')</span></button>';
      }).join('');
      container.querySelectorAll('.mn-sidebar-tag').forEach(function(el) {
        el.addEventListener('click', function() {
          var tag = this.dataset.tag;
          _setFilter('tag', _currentFilter.tag === tag ? null : tag);
        });
      });
    });
  }

  // ── Filtering + sorting ──
  function _setFilter(key, value) {
    if (key === 'type') {
      _currentFilter.type = value;
      _currentFilter.tag = null;
      _currentFilter.starred = (value === 'starred');
    } else if (key === 'tag') {
      _currentFilter.tag = value;
    } else if (key === 'search') {
      _currentFilter.search = value;
    }
    _updateSidebarActive();
    loadNotes();
  }

  function _updateSidebarActive() {
    document.querySelectorAll('.mn-sidebar-item').forEach(function(el) {
      el.classList.toggle('mn-sidebar-item-active', el.dataset.filter === _currentFilter.type);
    });
    document.querySelectorAll('.mn-sidebar-tag').forEach(function(el) {
      el.classList.toggle('mn-sidebar-tag-active', el.dataset.tag === _currentFilter.tag);
    });
  }

  function _applySort() {
    _filtered = _notes.slice();
    var sort = _currentFilter.sort;
    if (sort === 'recent') {
      _filtered.sort(function(a, b) { return (b.updated_at || '').localeCompare(a.updated_at || ''); });
    } else if (sort === 'oldest') {
      _filtered.sort(function(a, b) { return (a.updated_at || '').localeCompare(b.updated_at || ''); });
    } else if (sort === 'alpha') {
      _filtered.sort(function(a, b) { return (a.source_title || '').localeCompare(b.source_title || ''); });
    } else if (sort === 'starred') {
      _filtered.sort(function(a, b) {
        if (a.is_starred && !b.is_starred) return -1;
        if (!a.is_starred && b.is_starred) return 1;
        return (b.updated_at || '').localeCompare(a.updated_at || '');
      });
    }
  }

  // ── Render ──
  function renderList() {
    var list = document.getElementById('mnList');
    var empty = document.getElementById('mnEmpty');
    if (!_filtered.length) {
      list.innerHTML = '';
      list.appendChild(empty);
      empty.style.display = '';
      return;
    }
    empty.style.display = 'none';

    list.innerHTML = _filtered.map(function(n) {
      var active = n.id === _selectedId ? ' mn-note-card-active' : '';
      var tagHtml = (n.tags || []).slice(0, 3).map(function(t) {
        return '<span class="mn-note-card-tag">' + esc(t) + '</span>';
      }).join('');
      return '<div class="mn-note-card' + active + '" data-id="' + n.id + '">'
        + '<div class="mn-note-card-header">'
        + '<span class="mn-note-type-badge" style="background:' + esc(n.type_color) + ';">' + esc(n.type_label) + '</span>'
        + '<span class="mn-note-card-title">' + esc(n.source_title) + '</span>'
        + (n.is_starred ? '<i class="fas fa-star mn-note-card-star"></i>' : '')
        + '</div>'
        + '<div class="mn-note-card-preview">' + esc(preview(n.note_text, 100)) + '</div>'
        + '<div class="mn-note-card-meta">'
        + '<span class="mn-note-card-time">' + timeAgo(n.updated_at) + '</span>'
        + '<div class="mn-note-card-tags">' + tagHtml + '</div>'
        + '</div></div>';
    }).join('');

    // Click handlers
    list.querySelectorAll('.mn-note-card').forEach(function(el) {
      el.addEventListener('click', function() {
        selectNote(parseInt(this.dataset.id));
      });
    });
  }

  function selectNote(noteId) {
    _selectedId = noteId;
    var note = null;
    for (var i = 0; i < _notes.length; i++) {
      if (_notes[i].id === noteId) { note = _notes[i]; break; }
    }
    if (!note) return;

    // Highlight in list
    document.querySelectorAll('.mn-note-card').forEach(function(el) {
      el.classList.toggle('mn-note-card-active', parseInt(el.dataset.id) === noteId);
    });

    // Show detail
    document.getElementById('mnDetailPlaceholder').style.display = 'none';
    var content = document.getElementById('mnDetailContent');
    content.style.display = 'flex';

    // Badge
    var badge = document.getElementById('mnDetailBadge');
    badge.textContent = note.type_label;
    badge.style.background = note.type_color;

    // Source link
    var source = document.getElementById('mnDetailSource');
    source.href = note.source_url || '#';
    document.getElementById('mnDetailTitle').textContent = note.source_title;

    // Star
    var starBtn = document.getElementById('mnDetailStar');
    starBtn.classList.toggle('mn-starred', !!note.is_starred);

    // Text
    var textarea = document.getElementById('mnDetailText');
    textarea.value = note.note_text;
    document.getElementById('mnDetailStatus').innerHTML = note.updated_at
      ? '<i class="fas fa-check-circle text-success me-1"></i>Last saved ' + timeAgo(note.updated_at)
      : '';

    // Tags
    renderDetailTags(note);

    // Meta
    var meta = [];
    if (note.body_section) meta.push('<i class="fas fa-body me-1"></i>' + esc(note.body_section));
    if (note.modality) meta.push('<i class="fas fa-x-ray me-1"></i>' + esc(note.modality));
    if (note.created_at) meta.push('Created ' + new Date(note.created_at).toLocaleDateString());
    document.getElementById('mnDetailMeta').innerHTML = meta.join(' &middot; ');
  }

  function renderDetailTags(note) {
    var container = document.getElementById('mnDetailTags');
    container.innerHTML = (note.tags || []).map(function(t) {
      return '<span class="mn-detail-tag">' + esc(t)
        + '<button class="mn-detail-tag-remove" data-tag="' + esc(t) + '"><i class="fas fa-times"></i></button></span>';
    }).join('');
    container.querySelectorAll('.mn-detail-tag-remove').forEach(function(btn) {
      btn.addEventListener('click', function(e) {
        e.stopPropagation();
        var tag = this.dataset.tag;
        api('POST', '/api/my-notes/' + _selectedId + '/tags', { action: 'remove', tag: tag }).then(function(data) {
          if (data.success) {
            var n = _findNote(_selectedId);
            if (n) { n.tags = data.tags; renderDetailTags(n); loadTags(); }
          }
        });
      });
    });
  }

  function _findNote(id) {
    for (var i = 0; i < _notes.length; i++) { if (_notes[i].id === id) return _notes[i]; }
    return null;
  }

  // ── Events ──
  function init() {
    // Search
    var searchInput = document.getElementById('mnSearch');
    var searchTimer = null;
    searchInput.addEventListener('input', function() {
      clearTimeout(searchTimer);
      var val = this.value;
      searchTimer = setTimeout(function() { _setFilter('search', val); }, 300);
    });

    // Sort
    document.getElementById('mnSort').addEventListener('change', function() {
      _currentFilter.sort = this.value;
      _applySort();
      renderList();
    });

    // Sidebar "All Notes" + "Starred"
    document.querySelectorAll('.mn-sidebar-item[data-filter]').forEach(function(el) {
      el.addEventListener('click', function(e) {
        e.preventDefault();
        _setFilter('type', this.dataset.filter);
      });
    });

    // Sidebar toggle (mobile)
    var sidebar = document.getElementById('mnSidebar');
    var toggleBtn = document.getElementById('mnSidebarToggle');
    var closeBtn = document.getElementById('mnSidebarClose');
    if (toggleBtn) toggleBtn.addEventListener('click', function() { sidebar.classList.add('mn-sidebar-open'); });
    if (closeBtn) closeBtn.addEventListener('click', function() { sidebar.classList.remove('mn-sidebar-open'); });

    // Star
    document.getElementById('mnDetailStar').addEventListener('click', function() {
      if (!_selectedId) return;
      api('POST', '/api/my-notes/' + _selectedId + '/star').then(function(data) {
        if (data.success) {
          var n = _findNote(_selectedId);
          if (n) { n.is_starred = data.is_starred; selectNote(_selectedId); renderList(); }
        }
      });
    });

    // Delete
    document.getElementById('mnDetailDelete').addEventListener('click', function() {
      if (!_selectedId) return;
      if (!confirm('Delete this note permanently?')) return;
      api('DELETE', '/api/my-notes/' + _selectedId).then(function(data) {
        if (data.success) {
          _notes = _notes.filter(function(n) { return n.id !== _selectedId; });
          _selectedId = null;
          _applySort();
          renderList();
          document.getElementById('mnDetailContent').style.display = 'none';
          document.getElementById('mnDetailPlaceholder').style.display = '';
          loadStats(); loadTags();
        }
      });
    });

    // Auto-save note edits
    document.getElementById('mnDetailText').addEventListener('input', function() {
      var statusEl = document.getElementById('mnDetailStatus');
      statusEl.innerHTML = '<i class="fas fa-circle text-warning me-1" style="font-size:0.5rem;"></i>Unsaved';
      clearTimeout(_saveTimer);
      var noteId = _selectedId;
      var text = this.value;
      _saveTimer = setTimeout(function() {
        if (!noteId) return;
        api('PUT', '/api/my-notes/' + noteId, { note_text: text }).then(function(data) {
          if (data.success) {
            statusEl.innerHTML = '<i class="fas fa-check-circle text-success me-1"></i>Saved ' + timeAgo(data.updated_at);
            var n = _findNote(noteId);
            if (n) { n.note_text = text; n.updated_at = data.updated_at; renderList(); }
          }
        });
      }, 1500);
    });

    // Add tag
    var tagInput = document.getElementById('mnTagInput');
    var tagAddBtn = document.getElementById('mnTagAddBtn');
    function addTag() {
      var tag = tagInput.value.trim().toLowerCase();
      if (!tag || !_selectedId) return;
      api('POST', '/api/my-notes/' + _selectedId + '/tags', { action: 'add', tag: tag }).then(function(data) {
        if (data.success) {
          tagInput.value = '';
          var n = _findNote(_selectedId);
          if (n) { n.tags = data.tags; renderDetailTags(n); loadTags(); }
        }
      });
    }
    tagAddBtn.addEventListener('click', addTag);
    tagInput.addEventListener('keydown', function(e) { if (e.key === 'Enter') addTag(); });

    // Initial load
    loadNotes();
    loadStats();
    loadTags();
  }

  // ── Boot ──
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
