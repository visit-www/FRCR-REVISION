/**
 * CMV Badge System — Client-side badge rendering from PeerReviewClaim DB.
 *
 * Loads claims via API, injects badges into content, handles admin popup actions.
 * Works across all content types (knowledge hub, smart reporter, radiq, etc.)
 *
 * Usage: CmvBadges.load(containerEl, contentType, contentId)
 */
(function() {
    'use strict';

    function _checkAdmin() { return document.body && document.body.classList.contains('is-admin'); }

    function _escHtml(s) { var d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }

    // ── Badge injection (tiered search) ──

    function _injectBadges(containerEl, claims) {
        var badgedNodes = new Set();
        var unplaced = [];

        claims.forEach(function(claim) {
            if (claim.badge_state === 'dismissed' && !_checkAdmin()) return;

            var conf = (claim.gemini_confidence || '').toLowerCase();
            var agreedCls = conf === 'high' ? 'cmv-badge-agreed' : 'cmv-badge-agreed-medium';
            var agreedIcon = conf === 'high' ? 'fa-check-circle' : 'fa-check';
            var cfgMap = {
                agreed: {cls: agreedCls, icon: agreedIcon},
                disputed: {cls:'cmv-badge-disputed', icon:'fa-times-circle'},
                uncertain: {cls:'cmv-badge-uncertain', icon:'fa-question-circle'},
                admin_verified: {cls:'cmv-badge-admin-verified', icon:'fa-shield-alt'},
            };
            var bc = cfgMap[claim.badge_state] || cfgMap.uncertain;

            // Build tooltip
            var confLabel = (claim.gemini_confidence || '').toUpperCase();
            var tooltip = '';
            if (claim.badge_state === 'admin_verified') {
                tooltip = 'Admin verified.';
                if (confLabel) tooltip += ' [' + confLabel + ']';
                if (claim.gemini_reasoning) tooltip += ' RadInsights CMV: ' + claim.gemini_reasoning;
                if (claim.admin_reference_title) tooltip += ' | Ref: ' + claim.admin_reference_title;
                if (claim.admin_notes) tooltip += ' | Notes: ' + claim.admin_notes;
                if (claim.admin_reference_url) tooltip += ' | Click to view.';
            } else if (claim.badge_state === 'disputed') {
                tooltip = 'Disputed.';
                if (confLabel) tooltip += ' [' + confLabel + ']';
                if (claim.admin_notes) tooltip += ' ' + claim.admin_notes;
                if (claim.gemini_correction) tooltip += ' | Correction: ' + claim.gemini_correction;
            } else if (claim.badge_state === 'dismissed') {
                tooltip = 'Dismissed.';
                if (claim.admin_notes) tooltip += ' ' + claim.admin_notes;
            } else {
                if (confLabel) tooltip = '[' + confLabel + '] ';
                tooltip += claim.gemini_reasoning || '';
                if (claim.admin_notes) tooltip += ' | Admin: ' + claim.admin_notes;
            }

            // Create badge element
            var el;
            if (claim.badge_state === 'admin_verified' && claim.admin_reference_url) {
                el = document.createElement('a');
                el.href = claim.admin_reference_url;
                el.target = '_blank';
                el.rel = 'noopener noreferrer';
            } else {
                el = document.createElement('span');
            }
            el.className = 'cmv-badge ' + bc.cls;
            el.setAttribute('data-bs-toggle', 'tooltip');
            el.setAttribute('data-bs-placement', 'top');
            el.setAttribute('data-bs-html', 'true');
            el.setAttribute('data-bs-title', tooltip);
            el.setAttribute('data-claim-id', claim.id);
            el.innerHTML = '<i class="fas ' + bc.icon + '"></i>';

            var claimText = (claim.claim_text || '').replace(/\s*\|\s*/g, ' ').trim();
            var words = claimText.split(/\s+/);

            unplaced.push({
                el: el,
                claim: claim,
                full: claimText.replace(/\s+/g, ' ').toLowerCase(),
                w8: words.length >= 8 ? words.slice(0, 8).join(' ').toLowerCase() : '',
                w5: words.length >= 5 ? words.slice(0, 5).join(' ').toLowerCase() : '',
                w3: words.length >= 3 ? words.slice(0, 3).join(' ').toLowerCase() : '',
                wLast5: words.length >= 5 ? words.slice(-5).join(' ').toLowerCase() : '',
            });
        });

        // Collect all content elements (li, td, p, div with data-field) that hold text
        var contentEls = [];
        containerEl.querySelectorAll('li, td, p, div[data-field]').forEach(function(el) {
            // Skip elements that are just containers of other content elements
            if (el.tagName === 'DIV' && el.querySelector('ul, ol, table, p')) return;
            var text = (el.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();
            if (text.length > 3) {
                contentEls.push({ el: el, text: text });
            }
        });

        function tryPlaceOnElement(searchText, item) {
            if (!searchText || searchText.length < 4) return false;
            // Find the best matching element — prefer longest overlap
            var bestEl = null;
            var bestScore = 0;
            for (var i = 0; i < contentEls.length; i++) {
                var ce = contentEls[i];
                if (badgedNodes.has(ce.el)) continue;
                if (ce.text.indexOf(searchText) !== -1) {
                    // Full match — score by specificity (shorter element = more specific)
                    var score = searchText.length / ce.text.length;
                    if (score > bestScore) { bestScore = score; bestEl = ce; }
                }
            }
            if (bestEl) {
                // Avoid duplicate badge on same element
                if (bestEl.el.querySelector('.cmv-badge')) {
                    // Already has a badge — append after existing
                    bestEl.el.appendChild(document.createTextNode(' '));
                    bestEl.el.appendChild(item.el);
                } else {
                    bestEl.el.appendChild(document.createTextNode(' '));
                    bestEl.el.appendChild(item.el);
                }
                badgedNodes.add(bestEl.el);
                return true;
            }
            return false;
        }

        // Tiered element-level search: full → 8 words → 5 words → 3 words → last 5 words
        unplaced = unplaced.filter(function(i) { return !tryPlaceOnElement(i.full, i); });
        unplaced = unplaced.filter(function(i) { return !tryPlaceOnElement(i.w8, i); });
        unplaced = unplaced.filter(function(i) { return !tryPlaceOnElement(i.w5, i); });
        unplaced = unplaced.filter(function(i) { return !tryPlaceOnElement(i.w3, i); });
        unplaced = unplaced.filter(function(i) { return !tryPlaceOnElement(i.wLast5, i); });

        // Any remaining unplaced disputed/uncertain badges — show in summary block
        var importantUnplaced = unplaced.filter(function(i) {
            return i.claim.badge_state === 'disputed' || i.claim.badge_state === 'uncertain';
        });
        if (importantUnplaced.length > 0) {
            var block = document.createElement('div');
            block.className = 'cmv-unplaced-disputed mt-3 p-2 border border-danger rounded';
            block.style.cssText = 'background:#fff5f5;';
            block.innerHTML = '<strong class="text-danger"><i class="fas fa-exclamation-triangle me-1"></i>Disputed / Uncertain Claims:</strong>';
            var list = document.createElement('ul');
            list.className = 'mb-0 mt-1 small';
            importantUnplaced.forEach(function(i) {
                var li = document.createElement('li');
                li.className = i.claim.badge_state === 'disputed' ? 'text-danger' : 'text-warning';
                li.textContent = i.claim.claim_text;
                li.appendChild(document.createTextNode(' '));
                li.appendChild(i.el);
                list.appendChild(li);
            });
            block.appendChild(list);
            containerEl.appendChild(block);
        }
    }

    // ── Trust badge ──

    function _renderTrustBadge(containerEl, summary) {
        if (!summary || summary.total === 0) {
            containerEl.insertAdjacentHTML('afterbegin',
                '<div class="cmv-trust-badge cmv-trust-pending mb-2"><div class="cmv-trust-header">' +
                '<i class="fas fa-hourglass-half me-2"></i><strong>Pending Peer Review</strong> ' +
                '<span class="badge bg-secondary">awaiting verification</span></div></div>');
            return;
        }
        var cls = summary.disputed > 0 ? 'cmv-trust-caution' : (summary.uncertain > summary.total * 0.5 ? 'cmv-trust-partial' : 'cmv-trust-passed');
        var label = summary.disputed > 0 ? 'Cross-Model Verified — Issues Found' : 'Cross-Model Verified';
        containerEl.insertAdjacentHTML('afterbegin',
            '<div class="cmv-trust-badge ' + cls + ' mb-2"><div class="cmv-trust-header">' +
            '<i class="fas fa-shield-alt me-2"></i><strong>' + label + '</strong> ' +
            (summary.agreed ? '<span class="badge bg-success">' + summary.agreed + ' agreed</span> ' : '') +
            (summary.admin_verified ? '<span class="badge bg-primary">' + summary.admin_verified + ' admin verified</span> ' : '') +
            (summary.uncertain ? '<span class="badge bg-warning text-dark">' + summary.uncertain + ' uncertain</span> ' : '') +
            (summary.disputed ? '<span class="badge bg-danger">' + summary.disputed + ' disputed</span> ' : '') +
            '<button class="cmv-info-btn btn btn-link btn-sm p-0 ms-2" data-bs-toggle="popover" data-bs-trigger="hover focus" data-bs-html="true" data-bs-placement="bottom" ' +
            'data-bs-content="Each content generated by RadInsight Intelligence undergoes secondary peer review through an independent AI model (Cross-Model Verification). ' +
            'We also endeavour to verify as many claims as possible manually &mdash; however you are advised to treat every piece of information as suggestive and not prescriptive.">' +
            '<i class="fas fa-info-circle"></i> How this works</button></div></div>');
    }

    // ── References section ──

    function _renderReferences(containerEl, claims) {
        var refs = claims.filter(function(c) { return c.admin_reference_url; });
        if (refs.length === 0) return;
        var html = '<div class="cmv-references mt-3"><div class="card border"><div class="card-header bg-light py-2">' +
            '<i class="fas fa-book-medical me-2 text-muted"></i><strong class="text-muted">Verified References</strong></div>' +
            '<div class="card-body p-3"><ul class="list-unstyled mb-0">';
        refs.forEach(function(r) {
            html += '<li class="mb-2"><i class="fas fa-file-medical me-1 text-success"></i>' +
                '<a href="' + r.admin_reference_url + '" target="_blank" rel="noopener noreferrer">' +
                _escHtml(r.admin_reference_title || r.admin_reference_url) + '</a></li>';
        });
        html += '</ul></div></div></div>';
        containerEl.insertAdjacentHTML('beforeend', html);
    }

    // ── Admin popup ──

    function _showPopup(badge, claimId) {
        var old = document.getElementById('cmvClaimPopup');
        if (old) old.remove();

        var popup = document.createElement('div');
        popup.id = 'cmvClaimPopup';
        popup.style.cssText = 'position:fixed;background:#fff;border:2px solid var(--brand-neutral,#5E899E);' +
            'border-radius:8px;padding:8px 10px;box-shadow:0 4px 16px rgba(0,0,0,.2);z-index:10001;' +
            'display:flex;gap:6px;align-items:center;flex-wrap:wrap;max-width:360px;';
        popup.innerHTML =
            '<button class="btn btn-sm py-0 px-2" style="font-size:.75rem;background:#198754;color:#fff;border:none;border-radius:5px;" ' +
            'onclick="CmvBadges._quickUpdate(' + claimId + ',\'verified\')"><i class="fas fa-check me-1"></i>Verify</button>' +
            '<button class="btn btn-sm py-0 px-2" style="font-size:.75rem;background:#dc3545;color:#fff;border:none;border-radius:5px;" ' +
            'onclick="CmvBadges._quickUpdate(' + claimId + ',\'incorrect\')"><i class="fas fa-times me-1"></i>Incorrect</button>' +
            '<button class="btn btn-sm py-0 px-2" style="font-size:.75rem;background:#6c757d;color:#fff;border:none;border-radius:5px;" ' +
            'onclick="CmvBadges._quickUpdate(' + claimId + ',\'dismissed\')"><i class="fas fa-ban me-1"></i>Dismiss</button>' +
            '<button class="btn btn-sm py-0 px-2" style="font-size:.75rem;background:var(--brand-neutral);color:#fff;border:none;border-radius:5px;" ' +
            'onclick="CmvBadges._openReview(' + claimId + ')"><i class="fas fa-pen me-1"></i>Review</button>';
        document.body.appendChild(popup);

        var rect = badge.getBoundingClientRect();
        popup.style.left = Math.min(rect.left, window.innerWidth - 380) + 'px';
        popup.style.top = (rect.bottom + 6) + 'px';

        setTimeout(function() {
            document.addEventListener('click', function _close(ev) {
                if (!popup.contains(ev.target) && !ev.target.closest('.cmv-badge')) {
                    popup.remove();
                    document.removeEventListener('click', _close);
                }
            });
        }, 100);
    }

    function _quickUpdate(claimId, override) {
        fetch('/api/admin/peer-review/claims/' + claimId, {
            method: 'PATCH', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ admin_override: override }),
        }).then(function(r) { return r.json(); }).then(function(data) {
            var popup = document.getElementById('cmvClaimPopup');
            if (popup) popup.remove();
            if (data.success) {
                var badge = document.querySelector('.cmv-badge[data-claim-id="' + claimId + '"]');
                if (badge) {
                    if (override === 'dismissed') badge.style.display = 'none';
                    else if (override === 'verified') { badge.className = 'cmv-badge cmv-badge-admin-verified'; badge.querySelector('i').className = 'fas fa-shield-alt'; }
                    else if (override === 'incorrect') { badge.className = 'cmv-badge cmv-badge-disputed'; badge.querySelector('i').className = 'fas fa-times-circle'; }
                }
            }
        });
    }

    function _openReview(claimId) {
        var popup = document.getElementById('cmvClaimPopup');
        if (popup) popup.remove();

        fetch('/api/admin/peer-review/claims?per_page=500')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var claim = (data.claims || []).find(function(c) { return c.id === claimId; });
                if (!claim) { alert('Claim not found'); return; }

                var panel = document.createElement('div');
                panel.id = 'cmvEditPanel';
                panel.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);' +
                    'background:var(--brand-bg-offwhite,#fdfdfb);border:2px solid var(--brand-neutral,#5E899E);' +
                    'border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,.25);z-index:10002;width:500px;max-width:95vw;max-height:85vh;overflow-y:auto;';

                var info = (claim.gemini_verdict || '').toUpperCase() + ' (' + (claim.gemini_confidence || '') + ') — ' + (claim.gemini_reasoning || '');
                if (claim.gemini_correction) info += ' | Correction: ' + claim.gemini_correction;

                panel.innerHTML =
                    '<div style="background:linear-gradient(135deg,#5E899E,#4a7285);color:#fff;padding:12px 16px;border-radius:10px 10px 0 0;display:flex;justify-content:space-between;align-items:center;">' +
                    '<strong><i class="fas fa-shield-alt me-2"></i>Review Claim</strong>' +
                    '<button onclick="document.getElementById(\'cmvEditPanel\').remove()" style="background:none;border:none;color:#fff;font-size:1.2rem;cursor:pointer;">&times;</button></div>' +
                    '<div style="padding:16px;">' +
                    '<div class="mb-3"><label class="form-label fw-bold small">Claim</label><p class="bg-light p-2 rounded small">' + _escHtml(claim.claim_text) + '</p></div>' +
                    '<div class="mb-3"><label class="form-label fw-bold small">CMV Peer Review</label><p class="small text-muted">' + _escHtml(info) + '</p></div>' +
                    '<div class="mb-3"><label class="form-label fw-bold small">Override</label><select class="form-select form-select-sm" id="cmvEditOverride">' +
                    '<option value=""' + (!claim.admin_override ? ' selected' : '') + '>No override</option>' +
                    '<option value="verified"' + (claim.admin_override === 'verified' ? ' selected' : '') + '>Verified</option>' +
                    '<option value="incorrect"' + (claim.admin_override === 'incorrect' ? ' selected' : '') + '>Incorrect</option>' +
                    '<option value="dismissed"' + (claim.admin_override === 'dismissed' ? ' selected' : '') + '>Dismissed</option></select></div>' +
                    '<div class="mb-3"><label class="form-label fw-bold small">Reference URL</label><input type="url" class="form-control form-control-sm" id="cmvEditRefUrl" value="' + (claim.admin_reference_url || '').replace(/"/g,'&quot;') + '"></div>' +
                    '<div class="mb-3"><label class="form-label fw-bold small">Reference Title</label><input type="text" class="form-control form-control-sm" id="cmvEditRefTitle" value="' + (claim.admin_reference_title || '').replace(/"/g,'&quot;') + '"></div>' +
                    '<div class="mb-3"><label class="form-label fw-bold small">Notes</label><textarea class="form-control form-control-sm" id="cmvEditNotes" rows="2">' + _escHtml(claim.admin_notes || '') + '</textarea></div>' +
                    '<div class="d-flex gap-2"><button class="btn btn-brand-primary btn-sm" onclick="CmvBadges._saveReview(' + claimId + ')"><i class="fas fa-save me-1"></i>Save</button>' +
                    '<button class="btn btn-outline-secondary btn-sm" onclick="document.getElementById(\'cmvEditPanel\').remove()">Cancel</button></div></div>';

                document.body.appendChild(panel);
            });
    }

    function _saveReview(claimId) {
        fetch('/api/admin/peer-review/claims/' + claimId, {
            method: 'PATCH', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                admin_override: document.getElementById('cmvEditOverride').value || null,
                admin_reference_url: document.getElementById('cmvEditRefUrl').value || null,
                admin_reference_title: document.getElementById('cmvEditRefTitle').value || null,
                admin_notes: document.getElementById('cmvEditNotes').value || null,
            }),
        }).then(function(r) { return r.json(); }).then(function(data) {
            var panel = document.getElementById('cmvEditPanel');
            if (panel) panel.remove();
            if (data.success) {
                var badge = document.querySelector('.cmv-badge[data-claim-id="' + claimId + '"]');
                if (badge && data.claim) {
                    var bs = data.claim.badge_state;
                    if (bs === 'admin_verified') { badge.className = 'cmv-badge cmv-badge-admin-verified'; badge.querySelector('i').className = 'fas fa-shield-alt'; }
                    else if (bs === 'disputed') { badge.className = 'cmv-badge cmv-badge-disputed'; badge.querySelector('i').className = 'fas fa-times-circle'; }
                    else if (bs === 'dismissed') badge.style.display = 'none';
                }
            } else {
                alert(data.error || 'Save failed');
            }
        });
    }

    // ── Scroll-to-claim from URL ──

    function _scrollToClaimFromUrl() {
        var params = new URLSearchParams(window.location.search);
        var claimId = params.get('claim');
        if (!claimId) return;

        // Small delay to ensure badges are in the DOM
        setTimeout(function() {
            var badge = document.querySelector('.cmv-badge[data-claim-id="' + claimId + '"]');
            if (!badge) {
                // Check unplaced block too
                var unplacedBadge = document.querySelector('.cmv-unplaced-disputed .cmv-badge[data-claim-id="' + claimId + '"]');
                badge = unplacedBadge;
            }
            if (badge) {
                badge.scrollIntoView({ behavior: 'smooth', block: 'center' });
                // Flash highlight
                badge.style.transition = 'box-shadow 0.3s, transform 0.3s';
                badge.style.boxShadow = '0 0 0 4px rgba(233, 99, 4, 0.5)';
                badge.style.transform = 'scale(2)';
                setTimeout(function() {
                    badge.style.boxShadow = '';
                    badge.style.transform = '';
                }, 2500);
            }
        }, 500);
    }

    // ── Public API ──

    window.CmvBadges = {
        /**
         * Load and render CMV badges for a content item.
         * @param {HTMLElement} containerEl — the content container
         * @param {string} contentType — e.g. 'anatomy_snippet'
         * @param {string} contentId — DB id
         */
        load: function(containerEl, contentType, contentId) {
            if (!containerEl || !contentType || !contentId) return;
            if (containerEl.dataset.cmvLoaded === contentId) return;
            containerEl.dataset.cmvLoaded = contentId;

            fetch('/api/peer-review/claims?content_type=' + encodeURIComponent(contentType) + '&content_id=' + encodeURIComponent(contentId))
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    _renderTrustBadge(containerEl, data.claims && data.claims.length > 0 ? data.summary : null);

                    if (!data.claims || data.claims.length === 0) return;

                    _injectBadges(containerEl, data.claims);
                    _renderReferences(containerEl, data.claims);

                    // Init tooltips
                    if (typeof initCmvTooltips === 'function') initCmvTooltips();

                    // Admin: event delegation for badge clicks
                    if (_checkAdmin() && !containerEl.dataset.cmvClickReady) {
                        containerEl.dataset.cmvClickReady = 'true';
                        containerEl.addEventListener('click', function(e) {
                            var badge = e.target.closest('.cmv-badge[data-claim-id]');
                            if (!badge) return;
                            e.preventDefault();
                            e.stopPropagation();
                            _showPopup(badge, parseInt(badge.dataset.claimId));
                        });
                    }

                    // Auto-scroll to claim if ?claim=<id> is in URL
                    _scrollToClaimFromUrl();
                });
        },

        /**
         * Scroll to and highlight a specific claim badge by ID.
         * Called automatically after badge load if ?claim= param is present.
         */
        scrollToClaim: _scrollToClaimFromUrl,

        // Exposed for onclick handlers in popup HTML
        _quickUpdate: _quickUpdate,
        _openReview: _openReview,
        _saveReview: _saveReview,
    };
})();
