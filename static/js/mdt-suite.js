/**
 * MDT Suite — shared frontend logic
 * ─────────────────────────────────
 * - Quick-start meeting create/open
 * - Meeting browser case table + filters
 * - Case detail form with debounced auto-save
 * - Diagnosis search
 * - Case linking modal
 * - Status badges
 *
 * No framework — vanilla JS, scoped under window.MdtSuite
 */
(function() {
    'use strict';

    var MdtSuite = window.MdtSuite = {};

    // ── Utilities ─────────────────────────────────────────────────

    function $(sel, root) { return (root || document).querySelector(sel); }
    function $$(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

    function debounce(fn, ms) {
        var t;
        return function() {
            var args = arguments, ctx = this;
            clearTimeout(t);
            t = setTimeout(function() { fn.apply(ctx, args); }, ms);
        };
    }

    function fetchJson(url, opts) {
        opts = opts || {};
        opts.headers = Object.assign({ 'Content-Type': 'application/json' }, opts.headers || {});
        if (opts.body && typeof opts.body !== 'string') {
            opts.body = JSON.stringify(opts.body);
        }
        return fetch(url, opts).then(function(r) {
            return r.json().then(function(j) {
                if (!r.ok) {
                    var err = new Error(j.error || 'Request failed');
                    err.status = r.status;
                    err.payload = j;
                    throw err;
                }
                return j;
            });
        });
    }

    function escapeHtml(s) {
        if (s == null) return '';
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function todayIso() {
        var d = new Date();
        return d.getFullYear() + '-' +
               String(d.getMonth() + 1).padStart(2, '0') + '-' +
               String(d.getDate()).padStart(2, '0');
    }

    function showToast(msg, type) {
        // Re-use the global app toast if available
        if (typeof window.showToast === 'function') {
            return window.showToast(msg, type || 'info');
        }
        // Fallback
        console.log('[MDT]', type || 'info', msg);
    }

    var STATUS_META = {
        'pending':         { label: 'Pending',         badge: 'bg-warning text-dark', icon: 'fa-clock' },
        'discussed':       { label: 'Discussed',       badge: 'bg-info',              icon: 'fa-comments' },
        'action_recorded': { label: 'Action recorded', badge: 'bg-success',           icon: 'fa-check-circle' },
        'closed':          { label: 'Closed',          badge: 'bg-secondary',         icon: 'fa-archive' },
    };

    function statusBadge(status) {
        var s = STATUS_META[status] || STATUS_META.pending;
        return '<span class="badge ' + s.badge + '"><i class="fas ' + s.icon + ' me-1"></i>' + s.label + '</span>';
    }

    MdtSuite.STATUS_META = STATUS_META;
    MdtSuite.statusBadge = statusBadge;
    MdtSuite.escapeHtml = escapeHtml;
    MdtSuite.fetchJson = fetchJson;
    MdtSuite.debounce = debounce;
    MdtSuite.todayIso = todayIso;
    MdtSuite.showToast = showToast;

    // ── MDT summary plain-text → HTML renderer ─────────────────────
    // Mirrors ai_smart_reporter.mdt_summary_to_html() in Python.
    // Used by the case detail page to show a formatted preview of the
    // AI summary textarea, and to provide rich-text clipboard copy.
    var MDT_SECTION_KEYS = [
        'INDICATION',
        'KEY IMAGING FINDINGS',
        'HISTOLOGY & LAB CORRELATION',
        'HISTOLOGY AND LAB CORRELATION',
        'RADIOLOGICAL IMPRESSION',
        'IMAGING RECOMMENDATIONS',
        'FOR MDT DISCUSSION',
        'RECOMMENDATIONS',          // legacy
        'SUGGESTED NEXT STEP',      // legacy
        'CLINICAL ALERT'
    ];

    function parseSections(text) {
        var sections = {};
        MDT_SECTION_KEYS.forEach(function(k) { sections[k] = ''; });
        var current = null;
        (text || '').split('\n').forEach(function(line) {
            var stripped = line.trim();
            if (!stripped) return;
            var matched = false;
            for (var i = 0; i < MDT_SECTION_KEYS.length; i++) {
                var key = MDT_SECTION_KEYS[i];
                if (stripped.toUpperCase().indexOf(key) === 0) {
                    current = key;
                    var rest = stripped.substring(key.length).replace(/^[:\s]+/, '');
                    if (rest) sections[current] = rest;
                    matched = true;
                    break;
                }
            }
            if (matched) return;
            if (current !== null) {
                sections[current] = sections[current] ? (sections[current] + '\n' + stripped) : stripped;
            }
        });
        return sections;
    }

    function bulletsOrPara(text, ordered) {
        var lines = (text || '').split('\n').map(function(l) { return l.trim(); }).filter(Boolean);
        if (!lines.length) return '';
        var isOrdered = ordered || lines.every(function(l) { return /^\d+[\.\)]\s/.test(l); });
        if (isOrdered && lines.some(function(l) { return /^\d+[\.\)]\s/.test(l); })) {
            return '<ol class="mdt-preview-ol">' + lines.map(function(l) {
                return '<li>' + escapeHtml(l.replace(/^\d+[\.\)]\s*/, '')) + '</li>';
            }).join('') + '</ol>';
        }
        if (lines.some(function(l) { return /^[-•]/.test(l); })) {
            return '<ul class="mdt-preview-ul">' + lines.map(function(l) {
                return '<li>' + escapeHtml(l.replace(/^[-•]\s*/, '')) + '</li>';
            }).join('') + '</ul>';
        }
        return '<p>' + escapeHtml(text) + '</p>';
    }

    MdtSuite.summaryToHtml = function(plainText) {
        if (!plainText || !plainText.trim()) {
            return '<p class="text-muted fst-italic mb-0">No summary yet. Click <strong>Generate / Regenerate</strong> to produce one.</p>';
        }
        var s = parseSections(plainText);
        var parts = [];

        if (s['INDICATION']) {
            parts.push('<div class="mdt-preview-sec"><span class="mdt-preview-label">Indication</span>' +
                       '<p>' + escapeHtml(s['INDICATION']) + '</p></div>');
        }
        if (s['KEY IMAGING FINDINGS']) {
            parts.push('<div class="mdt-preview-sec"><span class="mdt-preview-label">Key Imaging Findings</span>' +
                       bulletsOrPara(s['KEY IMAGING FINDINGS']) + '</div>');
        }
        var histo = s['HISTOLOGY & LAB CORRELATION'] || s['HISTOLOGY AND LAB CORRELATION'];
        if (histo) {
            parts.push('<div class="mdt-preview-sec"><span class="mdt-preview-label">Histology &amp; Lab Correlation</span>' +
                       '<p>' + escapeHtml(histo) + '</p></div>');
        }
        if (s['RADIOLOGICAL IMPRESSION']) {
            parts.push('<div class="mdt-preview-sec"><span class="mdt-preview-label">Radiological Impression</span>' +
                       '<p>' + escapeHtml(s['RADIOLOGICAL IMPRESSION']) + '</p></div>');
        }
        var recs = s['IMAGING RECOMMENDATIONS'] || s['RECOMMENDATIONS'] || s['SUGGESTED NEXT STEP'];
        if (recs) {
            parts.push('<div class="mdt-preview-sec"><span class="mdt-preview-label">Imaging Recommendations</span>' +
                       bulletsOrPara(recs, true) + '</div>');
        }
        if (s['FOR MDT DISCUSSION']) {
            parts.push('<div class="mdt-preview-sec"><span class="mdt-preview-label">For MDT Discussion</span>' +
                       bulletsOrPara(s['FOR MDT DISCUSSION']) + '</div>');
        }
        if (s['CLINICAL ALERT']) {
            parts.push('<div class="mdt-preview-alert mdt-preview-alert-warning">' +
                       '<strong>⚠ Clinical Alert:</strong> ' + escapeHtml(s['CLINICAL ALERT']) + '</div>');
        }
        return parts.join('');
    };

    // Convert the rendered HTML to clean plain text (preserving bullets and
    // section breaks) for clipboard plain-text fallback.
    MdtSuite.previewToPlainText = function(previewEl) {
        if (!previewEl) return '';
        // Clone so we can mutate without affecting the live DOM
        var clone = previewEl.cloneNode(true);
        // Replace <li> with "- " bullets or "1. " numbered
        clone.querySelectorAll('ul li').forEach(function(li) {
            li.textContent = '- ' + li.textContent;
        });
        var olLists = clone.querySelectorAll('ol');
        olLists.forEach(function(ol) {
            var idx = 1;
            ol.querySelectorAll('li').forEach(function(li) {
                li.textContent = (idx++) + '. ' + li.textContent;
            });
        });
        // Add blank lines between sections for readability
        clone.querySelectorAll('.mdt-preview-sec').forEach(function(sec) {
            sec.textContent = '\n' + sec.querySelector('.mdt-preview-label').textContent.toUpperCase() + ':\n' +
                              (sec.querySelector('p, ul, ol') ? sec.querySelector('p, ul, ol').innerText : '');
        });
        return (clone.innerText || clone.textContent || '').trim();
    };

    // ── Quick start (landing page) ────────────────────────────────

    MdtSuite.initQuickStart = function() {
        var dateEl = $('#mdtQuickDate');
        var nameEl = $('#mdtQuickName');
        var typeEl = $('#mdtQuickType');
        var openBtn = $('#mdtQuickOpen');
        var newBtn = $('#mdtQuickNew');
        if (!dateEl || !nameEl || !openBtn) return;

        dateEl.value = dateEl.value || todayIso();

        // Autocomplete: fetch user's recent meeting names matching input
        var nameDropdown = $('#mdtQuickNameDropdown');
        var nameTimer = null;
        nameEl.addEventListener('input', function() {
            clearTimeout(nameTimer);
            var q = nameEl.value.trim();
            if (q.length < 2) { nameDropdown.classList.add('d-none'); return; }
            nameTimer = setTimeout(function() {
                fetchJson('/api/mdt/meetings?name=' + encodeURIComponent(q))
                    .then(function(d) {
                        var matches = (d.meetings || []).slice(0, 6);
                        if (!matches.length) { nameDropdown.classList.add('d-none'); return; }
                        nameDropdown.innerHTML = matches.map(function(m) {
                            return '<button type="button" class="list-group-item list-group-item-action small py-1" ' +
                                   'data-id="' + m.id + '" data-name="' + escapeHtml(m.name) + '" data-date="' + m.date + '" ' +
                                   'data-type="' + escapeHtml(m.mdt_type || '') + '">' +
                                   escapeHtml(m.name) + ' <span class="text-muted">— ' + m.date + '</span></button>';
                        }).join('');
                        nameDropdown.classList.remove('d-none');
                    });
            }, 200);
        });

        nameDropdown && nameDropdown.addEventListener('click', function(e) {
            var btn = e.target.closest('[data-id]');
            if (!btn) return;
            // Open this meeting directly
            window.location.href = '/mdt/meetings/' + btn.dataset.id;
        });

        document.addEventListener('click', function(e) {
            if (nameDropdown && !nameDropdown.contains(e.target) && e.target !== nameEl) {
                nameDropdown.classList.add('d-none');
            }
        });

        openBtn.addEventListener('click', function() {
            var name = nameEl.value.trim();
            var date = dateEl.value;
            if (!name || !date) {
                showToast('Enter a meeting name and date.', 'warning');
                return;
            }
            // Find existing — if found, navigate; if not, ask if they want to create
            fetchJson('/api/mdt/meetings?name=' + encodeURIComponent(name))
                .then(function(d) {
                    var match = (d.meetings || []).find(function(m) { return m.date === date; });
                    if (match) {
                        window.location.href = '/mdt/meetings/' + match.id;
                    } else {
                        if (confirm('No "' + name + '" meeting on ' + date + '. Create it?')) {
                            createAndOpen(name, date, typeEl ? typeEl.value : null);
                        }
                    }
                });
        });

        newBtn && newBtn.addEventListener('click', function() {
            var name = nameEl.value.trim();
            var date = dateEl.value;
            if (!name || !date) {
                showToast('Enter a meeting name and date first.', 'warning');
                return;
            }
            createAndOpen(name, date, typeEl ? typeEl.value : null);
        });

        function createAndOpen(name, date, mdtType) {
            fetchJson('/api/mdt/meetings', {
                method: 'POST',
                body: { name: name, date: date, mdt_type: mdtType || null }
            }).then(function(d) {
                window.location.href = '/mdt/meetings/' + d.meeting.id;
            }).catch(function(err) {
                showToast('Could not create meeting: ' + err.message, 'error');
            });
        }
    };

    MdtSuite.loadRecentMeetings = function(targetSelector, days) {
        var el = $(targetSelector);
        if (!el) return;
        var now = new Date();
        var to = new Date(now.getTime() + (days || 14) * 24 * 60 * 60 * 1000);
        var from = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        var fromStr = from.toISOString().slice(0, 10);
        var toStr = to.toISOString().slice(0, 10);
        fetchJson('/api/mdt/meetings?from=' + fromStr + '&to=' + toStr)
            .then(function(d) {
                var meetings = d.meetings || [];
                if (!meetings.length) {
                    el.innerHTML = '<p class="text-muted small mb-0">No meetings in the next 2 weeks. Create one above.</p>';
                    return;
                }
                el.innerHTML = '<div class="list-group list-group-flush">' +
                    meetings.slice(0, 10).map(function(m) {
                        var pendChip = m.pending_count > 0
                            ? ' <span class="badge bg-warning text-dark ms-1">' + m.pending_count + ' pending</span>' : '';
                        return '<a href="/mdt/meetings/' + m.id + '" class="list-group-item list-group-item-action small py-2">' +
                               '<div class="d-flex justify-content-between align-items-center">' +
                               '<div><strong>' + escapeHtml(m.name) + '</strong>' +
                               (m.mdt_type ? ' <span class="text-muted">· ' + escapeHtml(m.mdt_type) + '</span>' : '') + '</div>' +
                               '<div class="text-muted">' + m.date + ' · ' + m.case_count + ' case' + (m.case_count !== 1 ? 's' : '') + pendChip + '</div>' +
                               '</div></a>';
                    }).join('') + '</div>';
            });
    };

    MdtSuite.initSearchBox = function(inputSelector, resultsSelector) {
        var input = $(inputSelector);
        var results = $(resultsSelector);
        if (!input || !results) return;
        var timer = null;
        input.addEventListener('input', function() {
            clearTimeout(timer);
            var q = input.value.trim();
            if (q.length < 2) { results.innerHTML = ''; return; }
            timer = setTimeout(function() {
                fetchJson('/api/mdt/cases/search?q=' + encodeURIComponent(q))
                    .then(function(d) {
                        var rs = d.results || [];
                        if (!rs.length) {
                            results.innerHTML = '<p class="text-muted small mb-0 mt-2">No cases found.</p>';
                            return;
                        }
                        results.innerHTML = '<div class="list-group list-group-flush mt-2">' +
                            rs.map(function(c) {
                                var ref = c.case_reference ? '<span class="text-muted small me-2">' + escapeHtml(c.case_reference) + '</span>' : '';
                                var meeting = c.meeting ? ' <span class="text-muted small">— ' + escapeHtml(c.meeting.name) + ' · ' + c.meeting.date + '</span>' : '';
                                return '<a href="/mdt/cases/' + c.id + '" class="list-group-item list-group-item-action small py-2">' +
                                       ref + '<strong>' + escapeHtml(c.diagnosis) + '</strong>' + meeting +
                                       '<span class="ms-2">' + statusBadge(c.status) + '</span></a>';
                            }).join('') + '</div>';
                    });
            }, 300);
        });
    };

    // ── Meeting browser cases table ───────────────────────────────

    MdtSuite.initMeetingBrowser = function(meetingId) {
        loadCases(meetingId);

        var addBtn = $('#mdtAddCaseBtn');
        if (addBtn) addBtn.addEventListener('click', function() { openNewCaseModal(meetingId); });

        var modalForm = $('#mdtNewCaseForm');
        if (modalForm) {
            modalForm.addEventListener('submit', function(e) {
                e.preventDefault();
                submitNewCase(meetingId);
            });
        }
    };

    function loadCases(meetingId) {
        var tbody = $('#mdtCasesTbody');
        if (!tbody) return;
        fetchJson('/api/mdt/meetings/' + meetingId)
            .then(function(d) {
                var cases = d.meeting.cases || [];
                if (!cases.length) {
                    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">No cases yet. Click "Add case" to start.</td></tr>';
                } else {
                    tbody.innerHTML = cases.map(function(c) {
                        return '<tr>' +
                            '<td><span class="text-muted small">' + escapeHtml(c.case_reference || '—') + '</span></td>' +
                            '<td><a href="/mdt/meetings/' + meetingId + '/case/' + c.id + '" class="text-decoration-none fw-semibold">' + escapeHtml(c.diagnosis) + '</a></td>' +
                            '<td>' + statusBadge(c.status) + '</td>' +
                            '<td class="text-muted small">' + escapeHtml((c.clinical_history || '').substring(0, 80)) + '</td>' +
                            '<td class="text-end">' +
                                '<a href="/mdt/meetings/' + meetingId + '/case/' + c.id + '" class="btn btn-sm btn-outline-secondary"><i class="fas fa-edit"></i></a> ' +
                                '<button class="btn btn-sm btn-outline-danger" onclick="MdtSuite.deleteCase(' + c.id + ', ' + meetingId + ')"><i class="fas fa-trash"></i></button>' +
                            '</td>' +
                            '</tr>';
                    }).join('');
                }
                var countEl = $('#mdtCasesCount');
                if (countEl) countEl.textContent = cases.length + ' case' + (cases.length !== 1 ? 's' : '');
            });
    }

    function openNewCaseModal(meetingId) {
        var modalEl = $('#mdtNewCaseModal');
        if (!modalEl) return;
        var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        $('#mdtNewCaseForm').reset();
        modal.show();
    }

    function submitNewCase(meetingId) {
        var form = $('#mdtNewCaseForm');
        var payload = {
            meeting_id: meetingId,
            case_reference: $('#mdtNewCaseRef').value.trim() || null,
            diagnosis: $('#mdtNewCaseDiagnosis').value.trim(),
            clinical_history: $('#mdtNewCaseHistory').value.trim() || null,
        };
        if (!payload.diagnosis) {
            showToast('Diagnosis is required.', 'warning');
            return;
        }
        fetchJson('/api/mdt/cases', { method: 'POST', body: payload })
            .then(function(d) {
                bootstrap.Modal.getInstance($('#mdtNewCaseModal')).hide();
                showToast('Case added.', 'success');
                loadCases(meetingId);
            })
            .catch(function(err) {
                showToast(err.message || 'Could not create case.', 'error');
            });
    }

    MdtSuite.deleteCase = function(caseId, meetingId) {
        if (!confirm('Delete this case?')) return;
        fetchJson('/api/mdt/cases/' + caseId, { method: 'DELETE' })
            .then(function() {
                showToast('Case deleted.', 'success');
                loadCases(meetingId);
            });
    };

    // ── Case detail form (auto-save) ──────────────────────────────

    MdtSuite.initCaseForm = function(caseId) {
        var form = $('#mdtCaseForm');
        if (!form) return;

        var statusEl = $('#mdtSaveStatus');
        function showSaved() {
            if (!statusEl) return;
            statusEl.textContent = 'Saved ' + new Date().toLocaleTimeString();
            statusEl.className = 'small text-success';
        }
        function showSaving() {
            if (!statusEl) return;
            statusEl.textContent = 'Saving…';
            statusEl.className = 'small text-muted';
        }
        function showError(msg) {
            if (!statusEl) return;
            statusEl.textContent = msg || 'Save failed';
            statusEl.className = 'small text-danger';
        }
        function showPiiBlocked() {
            if (!statusEl) return;
            statusEl.innerHTML = '<i class="fas fa-shield-alt me-1"></i>Save blocked — resolve flagged PII above (Redact / Remove / Dismiss)';
            statusEl.className = 'small text-warning';
        }

        // Track failed saves per field so we can retry after PII is resolved.
        var _pendingPiiBlocked = {};   // field -> last value attempted

        function attemptSave(field, value) {
            showSaving();
            var payload = {};
            payload[field] = value;
            return fetchJson('/api/mdt/cases/' + caseId, { method: 'PUT', body: payload })
                .then(function(r) {
                    delete _pendingPiiBlocked[field];
                    showSaved();
                    return r;
                })
                .catch(function(err) {
                    if (err.payload && err.payload.pii_blocked) {
                        _pendingPiiBlocked[field] = value;
                        showPiiBlocked();
                    } else {
                        showError(err.message);
                    }
                    throw err;
                });
        }

        // One debouncer PER FIELD — a shared instance means typing in field A
        // then field B within the window cancels A's save (silent data loss)
        var _fieldSavers = {};
        var _dirtyFields = {};   // field -> latest unsaved value
        function save(field, value) {
            _dirtyFields[field] = value;
            if (!_fieldSavers[field]) {
                _fieldSavers[field] = debounce(function(f, v) {
                    delete _dirtyFields[f];
                    attemptSave(f, v).catch(function() {});
                }, 1000);
            }
            _fieldSavers[field](field, value);
        }

        // Flush unsaved fields when the user navigates/switches away
        function _flushDirty() {
            Object.keys(_dirtyFields).forEach(function(f) {
                var v = _dirtyFields[f];
                delete _dirtyFields[f];
                var payload = {};
                payload[f] = v;
                // keepalive so the PUT survives page unload
                fetchJson('/api/mdt/cases/' + caseId, { method: 'PUT', body: payload, keepalive: true })
                    .catch(function() {});
            });
        }
        document.addEventListener('visibilitychange', function() {
            if (document.visibilityState === 'hidden') _flushDirty();
        });
        window.addEventListener('pagehide', _flushDirty);

        // Wire all auto-save inputs
        $$('[data-mdt-autosave]', form).forEach(function(el) {
            el.addEventListener('input', function() {
                save(el.dataset.field, el.value);
            });
        });

        // Status radios save immediately on change (no debounce)
        $$('input[name="mdtStatus"]', form).forEach(function(radio) {
            radio.addEventListener('change', function() {
                attemptSave('status', radio.value).catch(function() {});
            });
        });

        // ── PII-resolved retry watchdog ─────────────────────────────────
        // The three resolution actions behave differently w.r.t. auto-save:
        //   Redact / Remove → modify textarea text → fires `input` → debounced
        //                     auto-save fires → consumes override → success
        //   Dismiss         → does NOT modify text, no input event → save
        //                     never re-fires on its own
        //
        // Watchdog handles BOTH paths uniformly: poll _piiCtrl.hasPII() and
        // when (a) no active PII remains AND (b) we have pending blocked
        // saves, retry the failed PUTs sequentially. Each save re-arms the
        // PIIGuard override flag immediately before its fetch — the
        // interceptor consumes the flag on each call so we MUST re-set it
        // per-save, not just once per batch.
        function _retryPendingSaves() {
            var fields = Object.keys(_pendingPiiBlocked);
            if (!fields.length) return Promise.resolve();
            // Sequential chain so each save re-arms the override individually
            return fields.reduce(function(chain, field) {
                return chain.then(function() {
                    var el = form.querySelector('[data-field="' + field + '"]');
                    var current = el ? el.value : _pendingPiiBlocked[field];
                    // Re-arm override RIGHT BEFORE this save — the fetch
                    // interceptor consumes _overrideActive after adding the
                    // header, so we have to re-arm per-save
                    if (window.PIIGuard && window.PIIGuard.setOverride) {
                        window.PIIGuard.setOverride(true);
                    }
                    return attemptSave(field, current).catch(function() {});
                });
            }, Promise.resolve());
        }

        var _hadPiiLastTick = false;
        setInterval(function() {
            if (!window._piiCtrl || typeof window._piiCtrl.hasPII !== 'function') return;
            var hasPii = window._piiCtrl.hasPII();
            // Edge: PII just cleared (transition true → false) and there are
            // pending blocked saves
            if (!hasPii && _hadPiiLastTick && Object.keys(_pendingPiiBlocked).length) {
                _retryPendingSaves();
            }
            _hadPiiLastTick = hasPii;
        }, 400);

        // Generate AI summary button (Day 3)
        var genBtn = $('#mdtGenerateSummaryBtn');
        if (genBtn) {
            genBtn.addEventListener('click', function() {
                genBtn.disabled = true;
                genBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Generating…';
                fetchJson('/api/mdt/cases/' + caseId + '/generate-summary', { method: 'POST' })
                    .then(function(d) {
                        var summaryEl = $('#mdtPreSummary');
                        if (summaryEl) summaryEl.value = d.summary || '';
                        // Tell the page to re-render the preview NOW — fixed
                        // 1s/3s/6s timeouts missed generations slower than 6s
                        document.dispatchEvent(new CustomEvent('mdt:summary-updated'));
                        showSaved();
                        // Admin cost badge
                        if (window.showAdminCostBadge && d.api_cost_usd != null) {
                            showAdminCostBadge(d.api_cost_usd, genBtn.parentElement);
                        }
                    })
                    .catch(function(err) { showError(err.message || 'Generation failed'); })
                    .finally(function() {
                        genBtn.disabled = false;
                        genBtn.innerHTML = '<i class="fas fa-magic me-1"></i>Generate / Regenerate';
                    });
            });
        }

        // Toggle case_reference visibility (eye icon)
        var refInput = $('#mdtCaseRef');
        var refToggle = $('#mdtCaseRefToggle');
        if (refToggle && refInput) {
            refToggle.addEventListener('click', function(e) {
                e.preventDefault();
                if (refInput.type === 'password') {
                    refInput.type = 'text';
                    refToggle.innerHTML = '<i class="fas fa-eye-slash"></i>';
                } else {
                    refInput.type = 'password';
                    refToggle.innerHTML = '<i class="fas fa-eye"></i>';
                }
            });
        }
    };
})();
