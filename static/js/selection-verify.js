/**
 * Selection Verify — Global text selection popup.
 *
 * Shows a floating popup when user selects text in content areas.
 * - All users: "Flag" button to report inaccuracies
 * - Admin only: "Verify" button → PubMed search + save verification
 *
 * Usage: SelectionVerify.init({ isAdmin: true/false })
 */
(function() {
    'use strict';

    var _popup = null;
    var _verifyPanel = null;
    var _isAdmin = false;
    var _currentSelection = { text: '', contentType: '', contentId: '' };

    // Quote-aware escape — safe in both text and attribute contexts
    function _escHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
    function _escAttr(s) { return _escHtml(s); }
    // Only allow http(s)/relative URLs in generated hrefs (blocks javascript: etc.)
    function _safeUrl(u) {
        u = String(u == null ? '' : u).trim();
        if (!u) return '#';
        if (/^(https?:)?\/\//i.test(u) || u.charAt(0) === '/' || u.charAt(0) === '#') return u;
        return '#';
    }

    var CONTENT_SELECTORS = [
        '#anatomyHistory',
        '.ai-answer-text',
        '.report-action-content',
        '.radiq-response',
        '.vetting-analysis',
        '#caseDiscussion',
        '#caseFindingsText',
        '.algorithm-content',
        '.template-content',
        '.pearl-content',
        '.doc-content',
        '.markdown-body',
        '.anatomy-content',
        '#detailContent',
        '.detail-body',
        '[data-selectable="true"]',
    ].join(', ');

    function _createPopup() {
        var el = document.createElement('div');
        el.id = 'selectionVerifyPopup';
        el.style.cssText = 'position:fixed;background:#fff;border:2px solid var(--brand-neutral,#5E899E);' +
            'border-radius:8px;padding:6px 8px;box-shadow:0 4px 12px rgba(0,0,0,.15);z-index:10000;' +
            'display:none;gap:6px;align-items:center;';
        document.body.appendChild(el);
        return el;
    }

    function _show(x, y) {
        if (!_popup) _popup = _createPopup();

        var html = '<button class="btn btn-sm py-0 px-2" style="font-size:.75rem;background:var(--brand-neutral);color:#fff;border:none;border-radius:6px;" ' +
            'onclick="SelectionVerify._flag()" title="Flag this content">' +
            '<i class="fas fa-flag me-1"></i>Flag</button>';

        if (_isAdmin) {
            html += '<button class="btn btn-sm py-0 px-2" style="font-size:.75rem;background:#198754;color:#fff;border:none;border-radius:6px;" ' +
                'onclick="SelectionVerify._verify()" title="Verify with PubMed">' +
                '<i class="fas fa-check-circle me-1"></i>Verify</button>';
        }

        _popup.innerHTML = html;
        _popup.style.display = 'flex';

        var popW = _isAdmin ? 180 : 90;
        var popH = 36;
        var left = Math.min(Math.max(10, x - popW / 2), window.innerWidth - popW - 10);
        var top = Math.max(10, y - popH - 10);
        _popup.style.left = left + 'px';
        _popup.style.top = top + 'px';
    }

    function _hide() {
        if (_popup) _popup.style.display = 'none';
    }

    function _detectContentType(el) {
        var node = el;
        while (node && node !== document.body) {
            // Record contentId before the contentType early-return — the same
            // element often carries both data attributes
            if (node.dataset && node.dataset.contentId && !_currentSelection.contentId) {
                _currentSelection.contentId = node.dataset.contentId;
            }
            if (node.dataset && node.dataset.contentType) return node.dataset.contentType;
            node = node.parentElement;
        }
        if (el.closest('#anatomyHistory')) return 'anatomy_snippet';
        if (el.closest('.ai-answer-text')) return 'smart_reporter_qa';
        if (el.closest('.report-action-content')) {
            var card = el.closest('[data-action-type]');
            if (card) {
                var at = card.dataset.actionType;
                if (at === 'sba') return 'sba_question';
                if (at === 'viva') return 'viva_question';
            }
            return 'smart_reporter_report';
        }
        if (el.closest('.radiq-response')) return 'radiq_answer';
        if (el.closest('.vetting-analysis')) return 'vetting_analysis';
        if (el.closest('#caseDiscussion, #caseFindingsText')) return 'case_discussion';
        if (el.closest('.algorithm-content')) return 'reporting_algorithm';
        if (el.closest('.template-content')) return 'radiology_template';
        if (el.closest('.pearl-content')) return 'radiology_pearl';
        if (el.closest('.anatomy-content')) return 'anatomy_snippet';
        if (el.closest('#detailContent')) {
            var dc = el.closest('[data-content-type]');
            if (dc) return dc.dataset.contentType;
            return 'anatomy_snippet';
        }
        return '';
    }

    function _onMouseUp(e) {
        setTimeout(function() {
            var sel = window.getSelection();
            var text = (sel ? sel.toString() : '').trim();
            if (text.length < 3) { _hide(); return; }

            var anchorNode = sel.anchorNode;
            var el = anchorNode && anchorNode.nodeType === 3 ? anchorNode.parentElement : anchorNode;
            if (!el || !(el.closest(CONTENT_SELECTORS) || el.closest('#detailPanel'))) { _hide(); return; }

            _currentSelection.text = text.substring(0, 500);
            _currentSelection.contentId = '';  // reset BEFORE detection — _detectContentType fills it
            _currentSelection.contentType = _detectContentType(el);

            var range = sel.getRangeAt(0);
            var rect = range.getBoundingClientRect();
            _show(rect.left + rect.width / 2, rect.top);
        }, 50);
    }

    // ── Verify Panel (Admin PubMed search) ──
    function _createVerifyPanel() {
        var el = document.createElement('div');
        el.id = 'verifyPanel';
        el.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);' +
            'background:var(--brand-bg-offwhite,#fdfdfb);border:2px solid var(--brand-success,#a8d5ba);' +
            'border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.2);z-index:10001;width:480px;max-width:90vw;' +
            'max-height:80vh;overflow-y:auto;display:none;';
        el.innerHTML =
            '<div style="background:linear-gradient(135deg,#5E899E 0%,#4a7285 100%);color:#fff;padding:12px 16px;border-radius:10px 10px 0 0;display:flex;justify-content:space-between;align-items:center;">' +
                '<span style="font-weight:600;font-size:.95rem;"><i class="fas fa-check-circle me-2"></i>Verify Reference</span>' +
                '<button onclick="SelectionVerify._closeVerify()" style="background:none;border:none;color:#fff;font-size:1.1rem;cursor:pointer;"><i class="fas fa-times"></i></button>' +
            '</div>' +
            '<div style="padding:16px;">' +
                '<div class="mb-2">' +
                    '<label style="font-weight:500;font-size:.85rem;margin-bottom:4px;display:block;">Selected Text</label>' +
                    '<div id="verifySelectedText" style="background:rgba(94,137,158,.08);border-left:3px solid var(--brand-neutral);padding:8px 10px;border-radius:4px;font-size:.85rem;font-style:italic;"></div>' +
                '</div>' +
                '<div class="mb-2">' +
                    '<label style="font-weight:500;font-size:.85rem;margin-bottom:4px;display:block;">Custom Verification Label <small class="text-muted">(optional — rewrite for clarity)</small></label>' +
                    '<input type="text" id="verifyCustomLabel" class="form-control form-control-sm" placeholder="e.g. normal stapes footplate thickness range">' +
                '</div>' +
                // Search section
                '<div class="mb-2">' +
                    '<label style="font-weight:500;font-size:.85rem;margin-bottom:4px;display:block;">Search PubMed & Radiopaedia</label>' +
                    '<div class="input-group input-group-sm">' +
                        '<input type="text" id="verifySearchQuery" class="form-control" placeholder="Search for references...">' +
                        '<select id="verifySearchSource" class="form-select" style="max-width:120px;font-size:.8rem;">' +
                            '<option value="all">All</option>' +
                            '<option value="pubmed">PubMed</option>' +
                            '<option value="radiopaedia">Radiopaedia</option>' +
                        '</select>' +
                        '<button class="btn btn-sm" style="background:var(--brand-neutral);color:#fff;" onclick="SelectionVerify._searchVerify()"><i class="fas fa-search"></i></button>' +
                    '</div>' +
                '</div>' +
                '<div id="verifyResults" style="font-size:.85rem;"></div>' +
                // Selected references list
                '<div class="mb-2">' +
                    '<label style="font-weight:500;font-size:.85rem;margin-bottom:4px;display:block;">Selected References <small class="text-muted" id="verifyRefCount">(0)</small></label>' +
                    '<div id="verifySelectedRefs" style="font-size:.82rem;"></div>' +
                '</div>' +
                // Manual add section
                '<div class="mb-2" style="border-top:1px dashed #ccc;padding-top:8px;">' +
                    '<label style="font-weight:500;font-size:.85rem;margin-bottom:4px;display:block;"><i class="fas fa-plus-circle me-1" style="color:var(--brand-primary);"></i>Add Reference Manually</label>' +
                    '<div class="row g-1 mb-1">' +
                        '<div class="col-8"><input type="text" id="manualRefTitle" class="form-control form-control-sm" placeholder="Title"></div>' +
                        '<div class="col-4"><input type="text" id="manualRefYear" class="form-control form-control-sm" placeholder="Year"></div>' +
                    '</div>' +
                    '<div class="row g-1 mb-1">' +
                        '<div class="col-6"><input type="text" id="manualRefAuthors" class="form-control form-control-sm" placeholder="Authors (e.g. Smith J, Jones A)"></div>' +
                        '<div class="col-6"><input type="text" id="manualRefJournal" class="form-control form-control-sm" placeholder="Journal"></div>' +
                    '</div>' +
                    '<div class="row g-1 mb-1">' +
                        '<div class="col-8"><input type="text" id="manualRefDoi" class="form-control form-control-sm" placeholder="DOI or URL (optional)"></div>' +
                        '<div class="col-4"><button class="btn btn-sm w-100" style="background:var(--brand-primary);color:#fff;" onclick="SelectionVerify._addManualRef()"><i class="fas fa-plus me-1"></i>Add</button></div>' +
                    '</div>' +
                '</div>' +
                '<div class="mt-3 d-flex gap-2 justify-content-end">' +
                    '<button class="btn btn-sm" style="background:#6c757d;color:#fff;" onclick="SelectionVerify._closeVerify()">Cancel</button>' +
                    '<button id="verifySaveBtn" class="btn btn-sm" style="background:var(--brand-primary);color:#fff;" onclick="SelectionVerify._saveVerification()"><i class="fas fa-check me-1"></i>Save All</button>' +
                '</div>' +
            '</div>';
        document.body.appendChild(el);
        return el;
    }

    var _selectedPapers = [];

    function _showVerifyPanel() {
        if (!_verifyPanel) _verifyPanel = _createVerifyPanel();
        _selectedPapers = [];

        document.getElementById('verifySelectedText').textContent = _currentSelection.text;
        document.getElementById('verifyCustomLabel').value = '';
        document.getElementById('verifySearchQuery').value = _currentSelection.text.substring(0, 80);
        document.getElementById('verifyResults').innerHTML = '<small class="text-muted">Click search to find references</small>';
        _renderSelectedRefs();

        // Clear manual fields
        ['manualRefTitle','manualRefYear','manualRefAuthors','manualRefJournal','manualRefDoi'].forEach(function(id) {
            var el = document.getElementById(id); if (el) el.value = '';
        });

        _verifyPanel.style.display = 'block';
    }

    function _renderSelectedRefs() {
        var container = document.getElementById('verifySelectedRefs');
        var countEl = document.getElementById('verifyRefCount');
        if (!container) return;
        countEl.textContent = '(' + _selectedPapers.length + ')';
        if (!_selectedPapers.length) {
            container.innerHTML = '<small class="text-muted">No references added yet. Search or add manually below.</small>';
            return;
        }
        var html = '';
        _selectedPapers.forEach(function(p, i) {
            var authors = typeof p.pubmed_authors === 'string' ? p.pubmed_authors : (p.authors || []).map(function(a) { return typeof a === 'object' ? (a.name || '') : String(a); }).join(', ');
            var shortAuth = authors.length > 40 ? authors.substring(0, 40) + '...' : authors;
            var srcBadge = p.source === 'radiopaedia'
                ? '<span class="badge" style="font-size:.5rem;background:#2d6b4f;color:#fff;">Radiopaedia</span>'
                : p.source === 'manual'
                ? '<span class="badge" style="font-size:.5rem;background:var(--brand-primary);color:#fff;">Manual</span>'
                : '<span class="badge" style="font-size:.5rem;background:#1a5276;color:#fff;">PubMed</span>';
            html += '<div class="d-flex justify-content-between align-items-center p-1 mb-1 rounded" style="background:rgba(25,135,84,.06);border:1px solid rgba(25,135,84,.2);">' +
                '<small><strong>' + _escHtml((p.title || 'Untitled').substring(0, 50)) + '</strong> ' + srcBadge +
                '<br><span class="text-muted">' + _escHtml(shortAuth) + (p.year ? ' (' + _escHtml(p.year) + ')' : '') + '</span></small>' +
                '<button class="btn btn-sm py-0 px-1" style="font-size:.7rem;color:#dc3545;" onclick="SelectionVerify._removeRef(' + i + ')" title="Remove"><i class="fas fa-times"></i></button>' +
                '</div>';
        });
        container.innerHTML = html;
    }

    // Public API
    window.SelectionVerify = {
        init: function(opts) {
            opts = opts || {};
            _isAdmin = !!opts.isAdmin;
            document.addEventListener('mouseup', _onMouseUp);
            document.addEventListener('mousedown', function(e) {
                if (_popup && !_popup.contains(e.target)) _hide();
            });
            document.addEventListener('scroll', _hide, true);
        },

        _flag: function() {
            _hide();
            if (window.openGlobalFlagModal) {
                openGlobalFlagModal({
                    contentType: _currentSelection.contentType,
                    contentId: _currentSelection.contentId,
                    selectedText: _currentSelection.text,
                });
            }
        },

        _verify: function() {
            _hide();
            _showVerifyPanel();
        },

        _closeVerify: function() {
            if (_verifyPanel) _verifyPanel.style.display = 'none';
        },

        _searchVerify: function() {
            var query = document.getElementById('verifySearchQuery').value.trim();
            if (!query) return;
            var source = document.getElementById('verifySearchSource').value;
            var resultsDiv = document.getElementById('verifyResults');
            resultsDiv.innerHTML = '<div class="text-center py-2"><div class="spinner-border spinner-border-sm text-primary"></div> Searching...</div>';

            fetch('/api/admin/verify-search?q=' + encodeURIComponent(query) + '&source=' + source)
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var results = data.results || [];
                    if (!results.length) {
                        resultsDiv.innerHTML = '<small class="text-muted">No results found. Try different search terms.</small>';
                        return;
                    }
                    var html = '';
                    results.forEach(function(r, i) {
                        var authorList = (r.authors || []).map(function(a) { return typeof a === 'object' ? (a.name || '') : String(a); });
                        var authors = authorList.slice(0, 3).join(', ');
                        if (authorList.length > 3) authors += ' et al.';
                        var title = String(r.title || 'Untitled');
                        var link = r.pubmed_link || ('https://pubmed.ncbi.nlm.nih.gov/' + (r.pmid || '') + '/');
                        var srcBadge = r.source === 'radiopaedia'
                            ? '<span class="badge" style="font-size:.55rem;background:#2d6b4f;color:#fff;">Radiopaedia</span>'
                            : '<span class="badge" style="font-size:.55rem;background:#1a5276;color:#fff;">PubMed</span>';
                        html += '<div class="p-2 mb-1 rounded" style="border:1px solid #e0e0e0;cursor:pointer;transition:background .15s;" ' +
                            'onmouseover="this.style.background=\'#f0f7ff\'" onmouseout="this.style.background=\'#fff\'" ' +
                            'onclick="SelectionVerify._pickPaper(' + i + ')" data-paper-idx="' + i + '">' +
                            '<div class="d-flex justify-content-between align-items-start">' +
                            '<div><strong style="font-size:.8rem;">' + _escHtml(title) + '</strong> ' + srcBadge + '</div>' +
                            '<a href="' + _escHtml(_safeUrl(link)) + '" target="_blank" rel="noopener" onclick="event.stopPropagation();" ' +
                            'style="font-size:.7rem;white-space:nowrap;margin-left:8px;" title="Open reference">' +
                            '<i class="fas fa-external-link-alt"></i></a></div>' +
                            '<small class="text-muted">' + (authors ? _escHtml(authors) + ' — ' : '') + _escHtml(r.journal || '') + (r.year ? ' (' + _escHtml(r.year) + ')' : '') +
                            (r.has_free_full_text ? ' <span class="badge bg-success" style="font-size:.6rem;">Free</span>' : '') +
                            '</small></div>';
                    });
                    resultsDiv.innerHTML = html;
                    // Store results for picking
                    resultsDiv._papers = results;
                })
                .catch(function(err) {
                    resultsDiv.innerHTML = '<small class="text-danger">Error: ' + err.message + '</small>';
                });
        },

        _pickPaper: function(idx) {
            var resultsDiv = document.getElementById('verifyResults');
            var papers = resultsDiv._papers || [];
            if (!papers[idx]) return;
            var p = papers[idx];

            // Avoid duplicates
            var isDupe = _selectedPapers.some(function(sp) {
                return (sp.pmid && sp.pmid === p.pmid) || (sp.title === p.title && sp.source === p.source);
            });
            if (isDupe) { if (window.showToast) showToast('Already added', 'info'); return; }

            var authorList = (p.authors || []).map(function(a) { return typeof a === 'object' ? (a.name || '') : String(a); });
            _selectedPapers.push({
                source: p.source || 'pubmed',
                title: String(p.title || ''),
                authors: authorList,
                pubmed_authors: authorList.join(', '),
                journal: p.journal || '',
                year: p.year || '',
                doi: p.doi || '',
                pmid: p.pmid || '',
                pubmed_link: p.pubmed_link || '',
            });
            _renderSelectedRefs();

            // Highlight in results
            resultsDiv.querySelectorAll('[data-paper-idx]').forEach(function(el) {
                el.style.background = el.dataset.paperIdx == idx ? 'rgba(25,135,84,.1)' : '#fff';
                el.style.borderColor = el.dataset.paperIdx == idx ? 'var(--brand-success)' : '#e0e0e0';
            });
        },

        _addManualRef: function() {
            var title = (document.getElementById('manualRefTitle').value || '').trim();
            if (!title) { if (window.showToast) showToast('Title is required', 'warning'); return; }

            _selectedPapers.push({
                source: 'manual',
                title: title,
                authors: [],
                pubmed_authors: (document.getElementById('manualRefAuthors').value || '').trim(),
                journal: (document.getElementById('manualRefJournal').value || '').trim(),
                year: (document.getElementById('manualRefYear').value || '').trim(),
                doi: (document.getElementById('manualRefDoi').value || '').trim(),
                pmid: '',
                pubmed_link: (document.getElementById('manualRefDoi').value || '').trim(),
            });
            _renderSelectedRefs();

            // Clear manual fields
            ['manualRefTitle','manualRefYear','manualRefAuthors','manualRefJournal','manualRefDoi'].forEach(function(id) {
                var el = document.getElementById(id); if (el) el.value = '';
            });
        },

        _removeRef: function(idx) {
            _selectedPapers.splice(idx, 1);
            _renderSelectedRefs();
        },

        _saveVerification: function() {
            if (!_selectedPapers.length) {
                if (window.showToast) showToast('Add at least one reference before saving.', 'warning');
                return;
            }

            var btn = document.getElementById('verifySaveBtn');
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Saving...';

            var customLabel = document.getElementById('verifyCustomLabel').value.trim();
            var saved = 0;
            var total = _selectedPapers.length;

            // Save each reference as a separate ManualVerification
            _selectedPapers.forEach(function(paper) {
                var payload = {
                    content_type: _currentSelection.contentType,
                    content_id: _currentSelection.contentId,
                    selected_text: _currentSelection.text,
                    custom_label: customLabel,
                    pubmed_doi: paper.doi || '',
                    pubmed_pmid: paper.pmid || '',
                    pubmed_title: paper.title || '',
                    pubmed_authors: paper.pubmed_authors || '',
                    pubmed_journal: paper.journal || '',
                    pubmed_year: paper.year || '',
                };

                fetch('/api/admin/manual-verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    saved++;
                    if (saved === total) {
                        btn.disabled = false;
                        btn.innerHTML = '<i class="fas fa-check me-1"></i>Save All';
                        SelectionVerify._closeVerify();
                        // Inject badge for the first reference
                        SelectionVerify._injectManualBadge(_currentSelection.text, _selectedPapers[0]);
                        if (window.showToast) showToast(total + ' reference' + (total > 1 ? 's' : '') + ' saved.', 'success');
                    }
                })
                .catch(function() {
                    saved++;
                    if (saved === total) {
                        btn.disabled = false;
                        btn.innerHTML = '<i class="fas fa-check me-1"></i>Save All';
                    }
                });
            });
        },

        /**
         * Inject a manual verification badge next to matching text in the DOM.
         */
        _injectManualBadge: function(selectedText, verification) {
            if (!selectedText || selectedText.length < 3) return;
            var containers = document.querySelectorAll(CONTENT_SELECTORS);
            var label = verification.custom_label || selectedText;
            var doi = verification.pubmed_doi;
            var link = doi ? 'https://doi.org/' + doi : (verification.pubmed_pmid ? 'https://pubmed.ncbi.nlm.nih.gov/' + verification.pubmed_pmid + '/' : '');
            var tooltip = 'Manually verified' + (verification.pubmed_journal ? ': ' + verification.pubmed_journal + ' ' + (verification.pubmed_year || '') : '');

            containers.forEach(function(container) {
                _findAndBadge(container, selectedText, link, tooltip);
            });
        },

        /**
         * Admin: dismiss an unverified badge (remove from DOM).
         */
        _dismissUnverified: function(el) {
            if (el && el.parentElement) {
                el.remove();
                _updateVerificationSummary();
            }
        },

        /**
         * Admin: show inline actions popup for a CMV badge claim.
         */
        _showClaimActions: function(badge, claimId) {
            // Remove any existing popup
            var old = document.getElementById('cmvClaimPopup');
            if (old) old.remove();

            var popup = document.createElement('div');
            popup.id = 'cmvClaimPopup';
            popup.style.cssText = 'position:fixed;background:#fff;border:2px solid var(--brand-neutral,#5E899E);' +
                'border-radius:8px;padding:8px 10px;box-shadow:0 4px 16px rgba(0,0,0,.2);z-index:10001;' +
                'display:flex;gap:6px;align-items:center;flex-wrap:wrap;max-width:320px;';

            popup.innerHTML =
                '<button class="btn btn-sm py-0 px-2" style="font-size:.72rem;background:#198754;color:#fff;border:none;border-radius:5px;" ' +
                'onclick="SelectionVerify._updateClaim(' + claimId + ',\'verified\')" title="Confirm correct">' +
                '<i class="fas fa-check me-1"></i>Verify</button>' +
                '<button class="btn btn-sm py-0 px-2" style="font-size:.72rem;background:#dc3545;color:#fff;border:none;border-radius:5px;" ' +
                'onclick="SelectionVerify._updateClaim(' + claimId + ',\'incorrect\')" title="Mark incorrect">' +
                '<i class="fas fa-times me-1"></i>Incorrect</button>' +
                '<button class="btn btn-sm py-0 px-2" style="font-size:.72rem;background:#6c757d;color:#fff;border:none;border-radius:5px;" ' +
                'onclick="SelectionVerify._updateClaim(' + claimId + ',\'dismissed\')" title="Not a real claim">' +
                '<i class="fas fa-ban me-1"></i>Dismiss</button>' +
                '<button class="btn btn-sm py-0 px-2" style="font-size:.72rem;background:var(--brand-neutral);color:#fff;border:none;border-radius:5px;" ' +
                'onclick="SelectionVerify._editClaim(' + claimId + ')" title="Review with notes & references">' +
                '<i class="fas fa-pen me-1"></i>Review</button>';

            document.body.appendChild(popup);

            var rect = badge.getBoundingClientRect();
            popup.style.left = Math.min(rect.left, window.innerWidth - 340) + 'px';
            popup.style.top = (rect.bottom + 4) + 'px';

            // Close on outside click
            setTimeout(function() {
                document.addEventListener('click', function _close(ev) {
                    if (!popup.contains(ev.target) && ev.target !== badge) {
                        popup.remove();
                        document.removeEventListener('click', _close);
                    }
                });
            }, 50);
        },

        /**
         * Admin: open full review panel for a CMV claim (notes, reference, override).
         */
        _editClaim: function(claimId) {
            var popup = document.getElementById('cmvClaimPopup');
            if (popup) popup.remove();

            // Fetch claim data first
            fetch('/api/admin/peer-review/claims?per_page=500')
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var claim = (data.claims || []).find(function(c) { return c.id === claimId; });
                    if (!claim) { alert('Claim not found'); return; }

                    var panel = document.createElement('div');
                    panel.id = 'cmvEditPanel';
                    panel.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);' +
                        'background:var(--brand-bg-offwhite,#fdfdfb);border:2px solid var(--brand-neutral,#5E899E);' +
                        'border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,.25);z-index:10002;width:500px;max-width:95vw;' +
                        'max-height:85vh;overflow-y:auto;';

                    var geminiInfo = (claim.gemini_verdict || '').toUpperCase() + ' (' + (claim.gemini_confidence || 'n/a') + ')';
                    if (claim.gemini_reasoning) geminiInfo += ' — ' + claim.gemini_reasoning;
                    if (claim.gemini_correction) geminiInfo += ' | Correction: ' + claim.gemini_correction;

                    panel.innerHTML =
                        '<div style="background:linear-gradient(135deg,#5E899E,#4a7285);color:#fff;padding:12px 16px;border-radius:10px 10px 0 0;display:flex;justify-content:space-between;align-items:center;">' +
                        '  <strong><i class="fas fa-shield-alt me-2"></i>Review Claim #' + claimId + '</strong>' +
                        '  <button onclick="document.getElementById(\'cmvEditPanel\').remove()" style="background:none;border:none;color:#fff;font-size:1.2rem;cursor:pointer;">&times;</button>' +
                        '</div>' +
                        '<div style="padding:16px;">' +
                        '  <div class="mb-3"><label class="form-label fw-bold small">Claim</label><p class="bg-light p-2 rounded small mb-0">' + _escHtml(claim.claim_text) + '</p></div>' +
                        '  <div class="mb-3"><label class="form-label fw-bold small">Gemini Says</label><p class="small text-muted mb-0">' + _escHtml(geminiInfo) + '</p></div>' +
                        '  <div class="mb-3"><label class="form-label fw-bold small">Override</label>' +
                        '    <select class="form-select form-select-sm" id="cmvEditOverride">' +
                        '      <option value=""' + (!claim.admin_override ? ' selected' : '') + '>No override</option>' +
                        '      <option value="verified"' + (claim.admin_override === 'verified' ? ' selected' : '') + '>Verified</option>' +
                        '      <option value="incorrect"' + (claim.admin_override === 'incorrect' ? ' selected' : '') + '>Incorrect</option>' +
                        '      <option value="dismissed"' + (claim.admin_override === 'dismissed' ? ' selected' : '') + '>Dismissed</option>' +
                        '    </select></div>' +
                        '  <div class="mb-3"><label class="form-label fw-bold small">Reference URL</label>' +
                        '    <input type="url" class="form-control form-control-sm" id="cmvEditRefUrl" placeholder="https://pubmed.ncbi.nlm.nih.gov/..." value="' + _escAttr(claim.admin_reference_url || '') + '"></div>' +
                        '  <div class="mb-3"><label class="form-label fw-bold small">Reference Title</label>' +
                        '    <input type="text" class="form-control form-control-sm" id="cmvEditRefTitle" placeholder="Author et al. (Year)" value="' + _escAttr(claim.admin_reference_title || '') + '"></div>' +
                        '  <div class="mb-3"><label class="form-label fw-bold small">Notes</label>' +
                        '    <textarea class="form-control form-control-sm" id="cmvEditNotes" rows="2">' + _escHtml(claim.admin_notes || '') + '</textarea></div>' +
                        '  <div class="d-flex gap-2">' +
                        '    <button class="btn btn-brand-primary btn-sm" onclick="SelectionVerify._saveClaimEdit(' + claimId + ')"><i class="fas fa-save me-1"></i>Save</button>' +
                        '    <button class="btn btn-outline-secondary btn-sm" onclick="document.getElementById(\'cmvEditPanel\').remove()">Cancel</button>' +
                        '  </div>' +
                        '</div>';

                    document.body.appendChild(panel);
                });
        },

        _saveClaimEdit: function(claimId) {
            var body = {
                admin_override: document.getElementById('cmvEditOverride').value || null,
                admin_reference_url: document.getElementById('cmvEditRefUrl').value || null,
                admin_reference_title: document.getElementById('cmvEditRefTitle').value || null,
                admin_notes: document.getElementById('cmvEditNotes').value || null,
            };
            fetch('/api/admin/peer-review/claims/' + claimId, {
                method: 'PATCH',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body),
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var panel = document.getElementById('cmvEditPanel');
                if (panel) panel.remove();
                if (data.success) {
                    // Update badge in DOM
                    var badge = document.querySelector('.cmv-badge[data-claim-id="' + claimId + '"]');
                    if (badge && body.admin_override === 'verified') {
                        badge.className = 'cmv-badge cmv-badge-admin-verified';
                        badge.querySelector('i').className = 'fas fa-shield-alt';
                    } else if (badge && body.admin_override === 'dismissed') {
                        badge.style.display = 'none';
                    } else if (badge && body.admin_override === 'incorrect') {
                        badge.className = 'cmv-badge cmv-badge-disputed';
                        badge.querySelector('i').className = 'fas fa-times-circle';
                    }
                } else {
                    alert(data.error || 'Save failed');
                }
            });
        },

        /**
         * Admin: update a CMV claim override via API (quick action).
         */
        _updateClaim: function(claimId, override) {
            fetch('/api/admin/peer-review/claims/' + claimId, {
                method: 'PATCH',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ admin_override: override }),
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var popup = document.getElementById('cmvClaimPopup');
                if (popup) popup.remove();
                if (data.success) {
                    // Update badge appearance in DOM
                    var badge = document.querySelector('.cmv-badge[data-claim-id="' + claimId + '"]');
                    if (badge) {
                        if (override === 'dismissed') {
                            badge.style.display = 'none';
                        } else if (override === 'verified') {
                            badge.className = 'cmv-badge cmv-badge-admin-verified';
                            badge.querySelector('i').className = 'fas fa-shield-alt';
                        } else if (override === 'incorrect') {
                            badge.className = 'cmv-badge cmv-badge-disputed';
                            badge.querySelector('i').className = 'fas fa-times-circle';
                        }
                    }
                }
            });
        },

        /**
         * Load and render manual verifications for content visible on page.
         * Call after content loads (e.g., anatomy snippet, RadIQ answer).
         */
        renderManualBadges: function(contentType, contentId) {
            fetch('/api/admin/manual-verify?content_type=' + encodeURIComponent(contentType || '') +
                  (contentId ? '&content_id=' + encodeURIComponent(contentId) : ''))
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    (data.verifications || []).forEach(function(v) {
                        SelectionVerify._injectManualBadge(v.selected_text, v);
                    });
                })
                .catch(function() {});
        },

        /**
         * Add dismiss buttons to all unverified badges (admin only).
         */
        initAdminBadgeControls: function() {
            if (!_isAdmin) return;

            // Legacy peer-review badges
            document.querySelectorAll('.peer-review-badge.unverified').forEach(function(badge) {
                if (badge.dataset.dismissReady) return;
                badge.dataset.dismissReady = 'true';
                badge.style.cursor = 'pointer';
                badge.title = (badge.title || '') + ' (click to dismiss)';
                badge.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    if (confirm('Dismiss this unverified warning?')) {
                        SelectionVerify._dismissUnverified(badge);
                    }
                });
            });

            // CMV badges are handled by CmvBadges' container delegation
            // (cmv-badges.js), which opens the full review panel including the
            // Corrected Text field. Attaching per-badge listeners here used to
            // stopPropagation and hijack every click into this legacy popup,
            // making inline correction unreachable. Only fall back to the
            // legacy popup when cmv-badges.js is not loaded on this page.
            if (!window.CmvBadges) {
                document.querySelectorAll('.cmv-badge[data-claim-id]').forEach(function(badge) {
                    if (badge.dataset.adminReady) return;
                    badge.dataset.adminReady = 'true';
                    badge.style.cursor = 'pointer';
                    badge.addEventListener('click', function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        var claimId = badge.dataset.claimId;
                        if (!claimId) return;
                        SelectionVerify._showClaimActions(badge, claimId);
                    });
                });
            }
        },

        /**
         * Auto-detect content areas on page and render manual verifications.
         * Also watches for dynamically loaded content (AJAX responses).
         */
        autoRenderManualBadges: function() {
            // Detect content types from DOM and fetch their manual verifications
            var _contentMap = {
                '#anatomyHistory': 'anatomy_snippet',
                '.ai-answer-text': 'smart_reporter_qa',
                '.radiq-response': 'radiq_answer',
                '.vetting-analysis': 'vetting_analysis',
                '#caseDiscussion': 'case_discussion',
                '.algorithm-content': 'reporting_algorithm',
                '.template-content': 'radiology_template',
                '.pearl-content': 'radiology_pearl',
                '.anatomy-content': 'anatomy_snippet',
                '#detailContent': 'anatomy_snippet',
            };

            // Check which content types are present on this page
            var typesPresent = {};
            Object.keys(_contentMap).forEach(function(sel) {
                if (document.querySelector(sel)) {
                    typesPresent[_contentMap[sel]] = true;
                }
            });

            // Fetch manual verifications for each present type
            Object.keys(typesPresent).forEach(function(ct) {
                SelectionVerify.renderManualBadges(ct);
            });

            // Watch for dynamically added content (AJAX-loaded)
            var observer = new MutationObserver(function(mutations) {
                var needsInit = false;
                mutations.forEach(function(m) {
                    if (m.addedNodes.length) {
                        m.addedNodes.forEach(function(node) {
                            if (node.nodeType === 1) {
                                // Check if new content has peer review badges
                                if (node.querySelector && (node.querySelector('.peer-review-badge') || node.querySelector('.cmv-badge'))) {
                                    needsInit = true;
                                }
                                // Check if new content matches any content selector
                                if (node.matches && CONTENT_SELECTORS.split(', ').some(function(s) {
                                    try { return node.matches(s) || node.querySelector(s); } catch(e) { return false; }
                                })) {
                                    needsInit = true;
                                }
                            }
                        });
                    }
                });
                if (needsInit) {
                    // Debounce — wait for all mutations to settle
                    clearTimeout(SelectionVerify._mutationTimer);
                    SelectionVerify._mutationTimer = setTimeout(function() {
                        SelectionVerify.initAdminBadgeControls();
                    }, 300);
                }
            });

            observer.observe(document.body, { childList: true, subtree: true });
        },

        _mutationTimer: null,
    };

    // Helper: find text in container and inject badge after it
    function _findAndBadge(container, text, link, tooltip) {
        var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
        var node;
        while (node = walker.nextNode()) {
            var idx = node.textContent.indexOf(text);
            if (idx === -1) continue;

            // Found the text — inject badge after it
            var badge;
            if (link) {
                badge = document.createElement('a');
                badge.href = link;
                badge.target = '_blank';
                badge.rel = 'noopener noreferrer';
            } else {
                badge = document.createElement('span');
            }
            badge.className = 'peer-review-badge manual-verified';
            badge.title = tooltip;
            badge.innerHTML = ' <i class="fas fa-user-check" style="color:#198754;font-size:.75em;"></i>';

            // Split the text node and insert badge
            var after = node.splitText(idx + text.length);
            node.parentNode.insertBefore(badge, after);
            return; // Only badge first occurrence
        }
    }

    function _updateVerificationSummary() {
        // Recount badges and update any summary elements
        var verified = document.querySelectorAll('.peer-review-badge.verified, .peer-review-badge.manual-verified').length;
        var unverified = document.querySelectorAll('.peer-review-badge.unverified').length;
        document.querySelectorAll('.peer-review-summary-verified').forEach(function(el) { el.textContent = verified; });
        document.querySelectorAll('.peer-review-summary-unverified').forEach(function(el) { el.textContent = unverified; });
    }
})();
