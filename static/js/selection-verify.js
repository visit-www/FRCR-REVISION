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
        '.protocol-content',
        '.pearl-content',
        '.doc-content',
        '.markdown-body',
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
            if (node.dataset && node.dataset.contentType) return node.dataset.contentType;
            if (node.dataset && node.dataset.contentId) _currentSelection.contentId = node.dataset.contentId;
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
        if (el.closest('.protocol-content')) return 'imaging_protocol';
        if (el.closest('.pearl-content')) return 'radiology_pearl';
        return '';
    }

    function _onMouseUp(e) {
        setTimeout(function() {
            var sel = window.getSelection();
            var text = (sel ? sel.toString() : '').trim();
            if (text.length < 3) { _hide(); return; }

            var anchorNode = sel.anchorNode;
            var el = anchorNode && anchorNode.nodeType === 3 ? anchorNode.parentElement : anchorNode;
            if (!el || !el.closest(CONTENT_SELECTORS)) { _hide(); return; }

            _currentSelection.text = text.substring(0, 500);
            _currentSelection.contentType = _detectContentType(el);
            _currentSelection.contentId = '';

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
                '<span style="font-weight:600;font-size:.95rem;"><i class="fas fa-check-circle me-2"></i>Verify with PubMed</span>' +
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
                '<div id="verifySelectedPaper" class="d-none mt-2 p-2 rounded" style="background:rgba(25,135,84,.08);border:1px solid var(--brand-success);font-size:.85rem;"></div>' +
                '<div class="mt-3 d-flex gap-2 justify-content-end">' +
                    '<button class="btn btn-sm" style="background:#6c757d;color:#fff;" onclick="SelectionVerify._closeVerify()">Cancel</button>' +
                    '<button id="verifySaveBtn" class="btn btn-sm" style="background:var(--brand-primary);color:#fff;" onclick="SelectionVerify._saveVerification()"><i class="fas fa-check me-1"></i>Save Verification</button>' +
                '</div>' +
            '</div>';
        document.body.appendChild(el);
        return el;
    }

    var _selectedPaper = null;

    function _showVerifyPanel() {
        if (!_verifyPanel) _verifyPanel = _createVerifyPanel();
        _selectedPaper = null;

        document.getElementById('verifySelectedText').textContent = _currentSelection.text;
        document.getElementById('verifyCustomLabel').value = '';
        document.getElementById('verifySearchQuery').value = _currentSelection.text.substring(0, 80);
        document.getElementById('verifyResults').innerHTML = '<small class="text-muted">Click search to find PubMed references</small>';
        document.getElementById('verifySelectedPaper').classList.add('d-none');

        _verifyPanel.style.display = 'block';
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
                            '<div><strong style="font-size:.8rem;">' + title + '</strong> ' + srcBadge + '</div>' +
                            '<a href="' + link + '" target="_blank" rel="noopener" onclick="event.stopPropagation();" ' +
                            'style="font-size:.7rem;white-space:nowrap;margin-left:8px;" title="Open reference">' +
                            '<i class="fas fa-external-link-alt"></i></a></div>' +
                            '<small class="text-muted">' + (authors ? authors + ' — ' : '') + (r.journal || '') + (r.year ? ' (' + r.year + ')' : '') +
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
            _selectedPaper = papers[idx];

            var sp = document.getElementById('verifySelectedPaper');
            var authorList = (_selectedPaper.authors || []).map(function(a) { return typeof a === 'object' ? (a.name || '') : String(a); });
            var authors = authorList.slice(0, 3).join(', ');
            if (authorList.length > 3) authors += ' et al.';
            sp.innerHTML = '<i class="fas fa-check-circle text-success me-1"></i><strong>' + (_selectedPaper.title || '') + '</strong><br>' +
                '<small>' + authors + ' — ' + (_selectedPaper.journal || '') + ' (' + (_selectedPaper.year || '') + ')</small>';
            sp.classList.remove('d-none');

            // Highlight selected in results
            resultsDiv.querySelectorAll('[data-paper-idx]').forEach(function(el) {
                el.style.background = el.dataset.paperIdx == idx ? 'rgba(25,135,84,.1)' : '#fff';
                el.style.borderColor = el.dataset.paperIdx == idx ? 'var(--brand-success)' : '#e0e0e0';
            });
        },

        _saveVerification: function() {
            var btn = document.getElementById('verifySaveBtn');
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Saving...';

            var payload = {
                content_type: _currentSelection.contentType,
                content_id: _currentSelection.contentId,
                selected_text: _currentSelection.text,
                custom_label: document.getElementById('verifyCustomLabel').value.trim(),
            };

            if (_selectedPaper) {
                payload.pubmed_doi = _selectedPaper.doi || '';
                payload.pubmed_pmid = _selectedPaper.pmid || '';
                payload.pubmed_title = _selectedPaper.title || '';
                payload.pubmed_authors = (_selectedPaper.authors || []).map(function(a) { return typeof a === 'object' ? (a.name || '') : String(a); }).join(', ');
                payload.pubmed_journal = _selectedPaper.journal || '';
                payload.pubmed_year = _selectedPaper.year || '';
            }

            fetch('/api/admin/manual-verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-check me-1"></i>Save Verification';
                if (data.success) {
                    SelectionVerify._closeVerify();
                    // Inject the badge inline immediately
                    SelectionVerify._injectManualBadge(
                        _currentSelection.text,
                        data.verification || payload
                    );
                    if (window.showToast) showToast('Verification saved successfully.', 'success');
                } else {
                    if (window.showToast) showToast('Error: ' + (data.error || 'Unknown'), 'error');
                }
            })
            .catch(function(err) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-check me-1"></i>Save Verification';
                if (window.showToast) showToast('Network error: ' + err.message, 'error');
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
                // Update summary counts if present
                _updateVerificationSummary();
            }
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
            document.querySelectorAll('.peer-review-badge.unverified').forEach(function(badge) {
                if (badge.dataset.dismissReady) return; // avoid double-init
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
        },
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
