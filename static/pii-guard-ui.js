/**
 * PII Guard v2 — UI Module
 * Layer 1: Ambient highlights (dotted underline) + banner
 * Layer 2: Click-to-act popover (Redact / Remove / Dismiss with confirmation)
 * Layer 3: Gate modal (per-item actions + bulk Redact All / Remove All / Dismiss All)
 *
 * Depends on: pii-guard.js (window.PIIGuard)
 *
 * Usage:
 *   var ctrl = PIIGuard.protect({
 *       textareas: ['#editorInput', '#editorOutput'],
 *       bannerTarget: '.card-header .d-flex',
 *       auditContext: 'smart-reporter'
 *   });
 *   // Before API call:
 *   var r = await ctrl.gate(); if (!r.allowed) return;
 */
(function() {
    'use strict';

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    function syncStyles(textarea, backdrop) {
        var cs = window.getComputedStyle(textarea);
        var props = [
            'fontFamily','fontSize','fontWeight','fontStyle','lineHeight',
            'letterSpacing','wordSpacing','textIndent','whiteSpace','wordWrap',
            'overflowWrap','wordBreak','paddingTop','paddingRight','paddingBottom',
            'paddingLeft','borderTopWidth','borderRightWidth','borderBottomWidth',
            'borderLeftWidth','boxSizing','textTransform'
        ];
        for (var i = 0; i < props.length; i++) {
            backdrop.style[props[i]] = cs[props[i]];
        }
        backdrop.style.width = textarea.offsetWidth + 'px';
        backdrop.style.height = textarea.offsetHeight + 'px';
        var scrollbarW = textarea.offsetWidth - textarea.clientWidth
            - (parseFloat(cs.borderLeftWidth) || 0) - (parseFloat(cs.borderRightWidth) || 0);
        if (scrollbarW > 0) {
            backdrop.style.paddingRight = ((parseFloat(cs.paddingRight) || 0) + scrollbarW) + 'px';
        }
    }

    function truncate(str, len) {
        return str.length > len ? str.substring(0, len) + '...' : str;
    }

    // ===================== PIIGuard.protect() =====================

    function protect(config) {
        if (!window.PIIGuard) {
            console.warn('PIIGuard.protect: PIIGuard not loaded');
            return null;
        }

        config = config || {};
        var selectors = config.textareas || [];
        var bannerTargetSel = config.bannerTarget || null;
        var auditContext = config.auditContext || 'unknown';

        var _textareas = [];
        var _overlays = {};
        var _banner = null;
        var _popover = null;
        var _debounceTimer = null;
        var _allMatches = [];       // ALL matches (including dismissed)
        var _activeMatches = [];    // non-dismissed matches only
        var _destroyed = false;

        // Resolve textareas
        for (var s = 0; s < selectors.length; s++) {
            var el = document.querySelector(selectors[s]);
            if (el) _textareas.push(el);
        }
        if (_textareas.length === 0) return null;

        // Setup overlays
        for (var t = 0; t < _textareas.length; t++) {
            var ta = _textareas[t];
            var taId = ta.id || ('pii-ta-' + t);
            _setupOverlay(ta, taId);
            ta.addEventListener('input', _onInput);
            ta.addEventListener('scroll', _onScroll);
        }

        // ResizeObserver
        if (window.ResizeObserver) {
            var ro = new ResizeObserver(function() {
                if (_destroyed) return;
                _syncAllOverlays();
            });
            for (var r = 0; r < _textareas.length; r++) ro.observe(_textareas[r]);
        }

        document.addEventListener('click', _onDocClick);
        setTimeout(_doScan, 50);

        // ===================== OVERLAY =====================

        function _setupOverlay(textarea, id) {
            var parent = textarea.parentNode;
            if (!parent.classList.contains('pii-overlay-container')) {
                var wrapper = document.createElement('div');
                wrapper.className = 'pii-overlay-container';
                wrapper.style.width = '100%';
                parent.insertBefore(wrapper, textarea);
                wrapper.appendChild(textarea);
                parent = wrapper;
            }
            // Backdrop goes AFTER textarea in DOM → paints on top.
            // CSS: z-index:2, transparent bg, pointer-events:none. Marks: pointer-events:auto.
            var backdrop = document.createElement('div');
            backdrop.className = 'pii-overlay-backdrop';
            parent.appendChild(backdrop);
            syncStyles(textarea, backdrop);
            _overlays[id] = { backdrop: backdrop, container: parent, textarea: textarea };
        }

        function _renderOverlay(id, text, matches) {
            var ov = _overlays[id];
            if (!ov) return;
            syncStyles(ov.textarea, ov.backdrop);

            if (!matches || matches.length === 0) {
                ov.backdrop.textContent = text;
                ov.container.classList.remove('pii-has-matches', 'pii-all-dismissed');
                return;
            }

            // Sort by index for correct rendering
            var sorted = matches.slice().sort(function(a, b) { return (a.index || 0) - (b.index || 0); });

            var html = '';
            var lastEnd = 0;
            for (var i = 0; i < sorted.length; i++) {
                var m = sorted[i];
                var idx = m.index;
                if (typeof idx !== 'number' || idx < lastEnd) continue;
                if (idx + m.length > text.length) continue;

                html += escapeHtml(text.substring(lastEnd, idx));
                var dismissed = PIIGuard.isDismissed(m);
                html += '<mark class="pii-mark" data-tier="' + (m.tier || 'medium')
                    + '" data-pii-type="' + escapeHtml(m.type)
                    + '" data-pii-match="' + escapeHtml(m.match)
                    + '"' + (dismissed ? ' data-dismissed="true"' : '')
                    + '>' + escapeHtml(m.match) + '</mark>';
                lastEnd = idx + m.length;
            }
            html += escapeHtml(text.substring(lastEnd));
            ov.backdrop.innerHTML = html;

            // Check if all matches are dismissed
            var activeCount = 0;
            for (var j = 0; j < matches.length; j++) {
                if (!PIIGuard.isDismissed(matches[j])) activeCount++;
            }

            if (activeCount > 0) {
                ov.container.classList.add('pii-has-matches');
                ov.container.classList.remove('pii-all-dismissed');
            } else {
                ov.container.classList.remove('pii-has-matches');
                ov.container.classList.add('pii-all-dismissed');
            }

            // Attach click handlers
            var marks = ov.backdrop.querySelectorAll('.pii-mark');
            for (var mi = 0; mi < marks.length; mi++) {
                marks[mi].addEventListener('click', _onMarkClick);
            }
        }

        function _syncAllOverlays() {
            for (var id in _overlays) {
                syncStyles(_overlays[id].textarea, _overlays[id].backdrop);
            }
        }

        // ===================== BANNER =====================

        function _updateBanner(activeCount, dismissedCount) {
            if (!bannerTargetSel) return;
            if (_banner) { _banner.remove(); _banner = null; }
            if (activeCount === 0 && dismissedCount === 0) return;

            var target = document.querySelector(bannerTargetSel);
            if (!target) return;

            _banner = document.createElement('div');
            _banner.className = 'pii-banner';
            if (activeCount > 0) {
                _banner.innerHTML = '<i class="fas fa-shield-alt" style="font-size:0.7rem"></i> Sensitive data detected (' + activeCount + ' item' + (activeCount !== 1 ? 's' : '') + ')';
            } else {
                _banner.className += ' pii-banner-clear';
                _banner.innerHTML = '<i class="fas fa-check-circle" style="font-size:0.7rem"></i> All items reviewed (' + dismissedCount + ' dismissed)';
            }
            target.appendChild(_banner);
        }

        // ===================== POPOVER (Layer 2) =====================

        function _closePopover() {
            if (_popover) { _popover.remove(); _popover = null; }
        }

        function _onMarkClick(e) {
            e.stopPropagation();
            e.preventDefault();
            var mark = e.currentTarget;
            var matchType = mark.getAttribute('data-pii-type');
            var matchText = mark.getAttribute('data-pii-match');
            if (!matchType || !matchText) return;

            // Find the match object
            var match = null;
            for (var i = 0; i < _allMatches.length; i++) {
                if (_allMatches[i].type === matchType && _allMatches[i].match === matchText) {
                    match = _allMatches[i]; break;
                }
            }
            if (!match) return;

            var isDismissedItem = PIIGuard.isDismissed(match);
            _closePopover();

            _popover = document.createElement('div');
            _popover.className = 'pii-popover';

            // Header
            var header = '<div class="pii-pop-header">'
                + '<span class="pii-pop-type">[' + escapeHtml(matchType) + ']</span>'
                + '<span class="pii-pop-match">"' + escapeHtml(truncate(matchText, 30)) + '"</span>'
                + '</div>';

            // Actions
            var actions = '<div class="pii-pop-actions">'
                + '<button class="pop-redact">Redact</button>'
                + '<button class="pop-remove">Remove</button>';
            if (!isDismissedItem) {
                actions += '<button class="pop-dismiss">Dismiss</button>';
            }
            actions += '</div>';

            // Dismiss confirmation section (hidden initially)
            var isHigh = match.tier === PIIGuard.TIER_HIGH;
            var confirmSection = '<div class="pii-pop-dismiss-confirm' + (isHigh ? ' pii-high-warn' : '') + '">'
                + '<div class="pii-pop-dismiss-warn">'
                + (isHigh
                    ? '⚠ This is HIGH-sensitivity data (e.g. NHS number, MRN). Dismissing will be audited and logged.'
                    : 'Dismissing will allow this item through. This action will be audited.')
                + '</div>'
                + '<label class="pii-pop-dismiss-cb-row">'
                + '<input type="checkbox" class="pii-pop-cb">'
                + '<span>I confirm this complies with data protection policy</span>'
                + '</label>'
                + '<button class="pii-pop-confirm-btn" disabled>Confirm Dismiss</button>'
                + '</div>';

            _popover.innerHTML = header + actions + confirmSection;
            document.body.appendChild(_popover);

            // Position
            var rect = mark.getBoundingClientRect();
            var popW = _popover.offsetWidth || 220;
            _popover.style.left = Math.min(rect.left, window.innerWidth - popW - 10) + 'px';
            _popover.style.top = (rect.bottom + 4) + 'px';

            // Wire action buttons
            _popover.querySelector('.pop-redact').addEventListener('click', function(ev) {
                ev.stopPropagation(); _closePopover(); _singleAction('redact', match);
            });
            _popover.querySelector('.pop-remove').addEventListener('click', function(ev) {
                ev.stopPropagation(); _closePopover(); _singleAction('remove', match);
            });

            if (!isDismissedItem) {
                var dismissBtn = _popover.querySelector('.pop-dismiss');
                var confirmDiv = _popover.querySelector('.pii-pop-dismiss-confirm');
                var cb = _popover.querySelector('.pii-pop-cb');
                var confirmBtn = _popover.querySelector('.pii-pop-confirm-btn');

                dismissBtn.addEventListener('click', function(ev) {
                    ev.stopPropagation();
                    // Show confirmation section
                    confirmDiv.classList.add('visible');
                    dismissBtn.style.display = 'none';
                });

                cb.addEventListener('change', function() {
                    confirmBtn.disabled = !this.checked;
                });

                confirmBtn.addEventListener('click', function(ev) {
                    ev.stopPropagation();
                    if (!cb.checked) return;
                    _closePopover();
                    PIIGuard.dismiss(match);
                    _logAction('dismiss', [match.type], 1);
                    _doScan(); // mark turns green
                });
            }
        }

        // ===================== ACTIONS =====================

        function _singleAction(action, match) {
            var replacement = action === 'redact' ? '[REDACTED]' : '';
            for (var t = 0; t < _textareas.length; t++) {
                var ta = _textareas[t];
                if (ta.value.indexOf(match.match) !== -1) {
                    ta.value = ta.value.split(match.match).join(replacement);
                    if (action === 'remove') ta.value = ta.value.replace(/  +/g, ' ');
                    ta.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }
            _logAction(action, [match.type], 1);
            _doScan();
        }

        function _batchAction(action, matches) {
            if (!matches || matches.length === 0) return;
            for (var t = 0; t < _textareas.length; t++) {
                var ta = _textareas[t];
                if (action === 'redact') {
                    ta.value = PIIGuard.redact(ta.value, matches);
                } else if (action === 'remove') {
                    ta.value = PIIGuard.remove(ta.value, matches);
                }
                ta.dispatchEvent(new Event('input', { bubbles: true }));
            }
            var types = matches.map(function(m) { return m.type; });
            _logAction('batch_' + action, types, matches.length);
            _doScan();
        }

        // ===================== SCANNING =====================

        function _onInput(e) {
            // Immediately clear stale highlights
            var ta = e.target;
            var taId = ta.id || ('pii-ta-' + Array.prototype.indexOf.call(_textareas, ta));
            if (_overlays[taId]) {
                _overlays[taId].backdrop.textContent = ta.value;
                _overlays[taId].container.classList.remove('pii-has-matches', 'pii-all-dismissed');
            }
            clearTimeout(_debounceTimer);
            _debounceTimer = setTimeout(_doScan, 250);
        }

        function _onScroll() {
            for (var id in _overlays) {
                _overlays[id].backdrop.scrollTop = _overlays[id].textarea.scrollTop;
            }
        }

        function _doScan() {
            if (_destroyed) return;
            _allMatches = [];
            _activeMatches = [];

            for (var t = 0; t < _textareas.length; t++) {
                var ta = _textareas[t];
                var taId = ta.id || ('pii-ta-' + t);
                var text = ta.value || '';
                var result = PIIGuard.scan(text);
                var matches = result.matches || [];

                // Collect all matches (including dismissed)
                for (var i = 0; i < matches.length; i++) {
                    var m = matches[i];
                    var isDupe = false;
                    for (var j = 0; j < _allMatches.length; j++) {
                        if (_allMatches[j].type === m.type && _allMatches[j].match === m.match) {
                            isDupe = true; break;
                        }
                    }
                    if (!isDupe) _allMatches.push(m);
                    if (!isDupe && !PIIGuard.isDismissed(m)) _activeMatches.push(m);
                }

                // Render overlay with ALL matches (dismissed shown green)
                if (_overlays[taId]) {
                    _renderOverlay(taId, text, matches);
                }
            }

            var dismissedCount = _allMatches.length - _activeMatches.length;
            _updateBanner(_activeMatches.length, dismissedCount);
        }

        // ===================== GATE MODAL (Layer 3) =====================

        function gate() {
            return new Promise(function(resolve) {
                if (_destroyed) { resolve({ allowed: true }); return; }

                _doScan();

                // If no active PII (all dismissed or none)
                if (_activeMatches.length === 0) {
                    if (_allMatches.length > 0) {
                        // All are dismissed — set override for fetch interceptor
                        PIIGuard.setOverride(true);
                    }
                    resolve({ allowed: true });
                    return;
                }

                _showGateModal(resolve);
            });
        }

        function _showGateModal(resolve) {
            var resolved = false;

            function finish(result) {
                if (resolved) return;
                resolved = true;
                if (overlay.parentNode) overlay.remove();
                _doScan();
                resolve(result);
            }

            var overlay = document.createElement('div');
            overlay.className = 'pii-gate-overlay';

            var modal = document.createElement('div');
            modal.className = 'pii-gate-modal';

            // Header
            modal.innerHTML =
                '<div class="pii-gate-header">'
                + '<i class="fas fa-shield-alt"></i>'
                + '<h5>Review Required</h5>'
                + '<button class="pii-gate-close">&times;</button>'
                + '</div>';

            // Body
            var body = document.createElement('div');
            body.className = 'pii-gate-body';
            body.innerHTML = '<p>' + _activeMatches.length + ' item' + (_activeMatches.length !== 1 ? 's' : '') + ' detected in your text:</p>';

            // Per-item rows
            var itemsContainer = document.createElement('div');
            itemsContainer.className = 'pii-gate-items';

            // Track item states: { match, el, status }
            var itemStates = [];

            for (var i = 0; i < _activeMatches.length; i++) {
                (function(match, idx) {
                    var row = document.createElement('div');
                    row.className = 'pii-gate-item';

                    var info = document.createElement('div');
                    info.className = 'pii-gate-item-info';
                    info.innerHTML = '<span class="pii-gate-item-type">' + escapeHtml(match.type) + '</span>'
                        + '<span class="pii-gate-item-match">"' + escapeHtml(truncate(match.match, 30)) + '"</span>';

                    var tierBadge = document.createElement('span');
                    tierBadge.className = 'pii-gate-item-tier tier-' + (match.tier || 'medium');
                    tierBadge.textContent = (match.tier || 'medium').toUpperCase();

                    var actionsDiv = document.createElement('div');
                    actionsDiv.className = 'pii-gate-item-actions';
                    actionsDiv.innerHTML =
                        '<button class="gate-redact">Redact</button>'
                        + '<button class="gate-remove">Remove</button>'
                        + '<button class="gate-dismiss">Dismiss</button>';

                    var statusSpan = document.createElement('span');
                    statusSpan.className = 'pii-gate-item-status';
                    statusSpan.style.display = 'none';

                    row.appendChild(info);
                    row.appendChild(tierBadge);
                    row.appendChild(actionsDiv);
                    row.appendChild(statusSpan);
                    itemsContainer.appendChild(row);

                    var state = { match: match, el: row, actionsDiv: actionsDiv, statusSpan: statusSpan, status: 'pending' };
                    itemStates.push(state);

                    // Wire per-item buttons
                    actionsDiv.querySelector('.gate-redact').addEventListener('click', function() {
                        _singleAction('redact', match);
                        _markItemDone(state, 'Redacted ✓');
                        _checkAllDone();
                    });
                    actionsDiv.querySelector('.gate-remove').addEventListener('click', function() {
                        _singleAction('remove', match);
                        _markItemDone(state, 'Removed ✓');
                        _checkAllDone();
                    });
                    actionsDiv.querySelector('.gate-dismiss').addEventListener('click', function() {
                        _showItemDismissConfirm(state);
                    });
                })(_activeMatches[i], i);
            }

            body.appendChild(itemsContainer);
            modal.appendChild(body);

            // Footer with bulk actions
            var footer = document.createElement('div');
            footer.className = 'pii-gate-footer';

            var bulkRow = document.createElement('div');
            bulkRow.className = 'pii-gate-bulk-row';

            var cancelBtn = _btn('Cancel', 'pii-gate-btn-cancel');
            var redactAllBtn = _btn('Redact All', 'pii-gate-btn-redact-all');
            var removeAllBtn = _btn('Remove All', 'pii-gate-btn-remove-all');
            var dismissAllBtn = _btn('Dismiss All', 'pii-gate-btn-dismiss-all');
            var continueBtn = _btn('Continue', 'pii-gate-btn-continue');

            bulkRow.appendChild(cancelBtn);
            bulkRow.appendChild(redactAllBtn);
            bulkRow.appendChild(removeAllBtn);
            bulkRow.appendChild(dismissAllBtn);
            bulkRow.appendChild(continueBtn);
            footer.appendChild(bulkRow);

            // Dismiss-all confirmation
            var hasHigh = false;
            for (var h = 0; h < _activeMatches.length; h++) {
                if (_activeMatches[h].tier === PIIGuard.TIER_HIGH) { hasHigh = true; break; }
            }

            var dismissConfirm = document.createElement('div');
            dismissConfirm.className = 'pii-gate-dismiss-confirm' + (hasHigh ? ' pii-high-warn' : '');
            dismissConfirm.innerHTML =
                '<div>' + (hasHigh
                    ? '⚠ <strong>HIGH-sensitivity data detected</strong> (e.g. NHS numbers, MRNs). Dismissing all items will be audited and permanently logged.'
                    : 'Dismissing all items will allow them through. This action will be audited.')
                + '</div>'
                + '<label style="display:flex;align-items:flex-start;gap:6px;font-size:0.72rem">'
                + '<input type="checkbox" class="pii-gate-dismiss-cb" style="margin-top:2px">'
                + '<span>I confirm this complies with data protection policy</span>'
                + '</label>'
                + '<button class="pii-gate-confirm-send" disabled>Confirm Dismiss All</button>';
            footer.appendChild(dismissConfirm);

            modal.appendChild(footer);
            overlay.appendChild(modal);
            document.body.appendChild(overlay);

            // Wire events
            modal.querySelector('.pii-gate-close').addEventListener('click', function() { finish({ allowed: false }); });
            cancelBtn.addEventListener('click', function() { finish({ allowed: false }); });

            redactAllBtn.addEventListener('click', function() {
                var pending = _getPending();
                _batchAction('redact', pending);
                for (var i = 0; i < itemStates.length; i++) {
                    if (itemStates[i].status === 'pending') _markItemDone(itemStates[i], 'Redacted ✓');
                }
                _checkAllDone();
            });

            removeAllBtn.addEventListener('click', function() {
                var pending = _getPending();
                _batchAction('remove', pending);
                for (var i = 0; i < itemStates.length; i++) {
                    if (itemStates[i].status === 'pending') _markItemDone(itemStates[i], 'Removed ✓');
                }
                _checkAllDone();
            });

            dismissAllBtn.addEventListener('click', function() {
                dismissConfirm.classList.add('visible');
                dismissAllBtn.style.display = 'none';
            });

            var dismissCb = dismissConfirm.querySelector('.pii-gate-dismiss-cb');
            var confirmSendBtn = dismissConfirm.querySelector('.pii-gate-confirm-send');

            dismissCb.addEventListener('change', function() {
                confirmSendBtn.disabled = !this.checked;
            });

            confirmSendBtn.addEventListener('click', function() {
                if (!dismissCb.checked) return;
                // Dismiss all pending
                for (var i = 0; i < itemStates.length; i++) {
                    if (itemStates[i].status === 'pending') {
                        PIIGuard.dismiss(itemStates[i].match);
                        _markItemDone(itemStates[i], 'Dismissed ✓');
                    }
                }
                var types = _activeMatches.map(function(m) { return m.type; });
                _logAction('batch_dismiss', types, _activeMatches.length);
                dismissConfirm.classList.remove('visible');
                _doScan();
                _checkAllDone();
            });

            continueBtn.addEventListener('click', function() {
                // All items addressed — check if any were dismissed (need override)
                var hasDismissed = false;
                for (var i = 0; i < itemStates.length; i++) {
                    if (itemStates[i].statusText === 'Dismissed ✓') { hasDismissed = true; break; }
                }
                if (hasDismissed) PIIGuard.setOverride(true);
                finish({ allowed: true, action: hasDismissed ? 'override' : 'redact' });
            });

            // Static backdrop shake
            overlay.addEventListener('click', function(e) {
                if (e.target === overlay) {
                    modal.style.animation = 'none';
                    modal.offsetHeight;
                    modal.style.animation = 'piiGateShake 0.3s ease';
                }
            });

            // --- Helpers ---

            function _btn(text, cls) {
                var b = document.createElement('button');
                b.className = cls;
                b.textContent = text;
                return b;
            }

            function _markItemDone(state, label) {
                state.status = 'done';
                state.statusText = label;
                state.actionsDiv.style.display = 'none';
                state.statusSpan.textContent = label;
                state.statusSpan.style.display = 'inline';
                state.el.classList.add('pii-item-done');
            }

            function _getPending() {
                var arr = [];
                for (var i = 0; i < itemStates.length; i++) {
                    if (itemStates[i].status === 'pending') arr.push(itemStates[i].match);
                }
                return arr;
            }

            function _checkAllDone() {
                var pending = _getPending();
                if (pending.length === 0) {
                    // Hide bulk action buttons, show Continue
                    redactAllBtn.style.display = 'none';
                    removeAllBtn.style.display = 'none';
                    dismissAllBtn.style.display = 'none';
                    dismissConfirm.classList.remove('visible');
                    continueBtn.classList.add('visible');
                }
            }

            function _showItemDismissConfirm(state) {
                var match = state.match;
                var isHigh = match.tier === PIIGuard.TIER_HIGH;

                // Replace action buttons with inline confirmation
                state.actionsDiv.innerHTML =
                    '<div style="display:flex;flex-direction:column;gap:3px;font-size:0.62rem;max-width:200px;white-space:normal">'
                    + '<div style="color:' + (isHigh ? '#721c24;font-weight:600' : '#856404') + '">'
                    + (isHigh ? '⚠ HIGH-sensitivity. Will be audited.' : 'Will be audited.')
                    + '</div>'
                    + '<label style="display:flex;align-items:flex-start;gap:4px">'
                    + '<input type="checkbox" class="item-dismiss-cb" style="margin-top:1px">'
                    + '<span>I confirm</span></label>'
                    + '<button class="item-dismiss-ok" disabled style="font-size:0.58rem;padding:1px 6px;border-radius:3px;border:none;background:#28a745;color:#fff;cursor:pointer">OK</button>'
                    + '</div>';

                var cb = state.actionsDiv.querySelector('.item-dismiss-cb');
                var okBtn = state.actionsDiv.querySelector('.item-dismiss-ok');

                cb.addEventListener('change', function() { okBtn.disabled = !this.checked; });
                okBtn.addEventListener('click', function() {
                    PIIGuard.dismiss(match);
                    _logAction('dismiss', [match.type], 1);
                    _markItemDone(state, 'Dismissed ✓');
                    _doScan();
                    _checkAllDone();
                });
            }
        }

        // ===================== AUDIT LOGGING =====================

        function _logAction(action, types, count) {
            try {
                fetch('/api/pii-override-log', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({
                        action: action,
                        flagged_types: types,
                        flagged_count: count,
                        target_url: auditContext
                    })
                }).catch(function() {});
            } catch(e) {}
        }

        // ===================== MISC =====================

        function _onDocClick(e) {
            if (_popover && !_popover.contains(e.target) && !e.target.classList.contains('pii-mark')) {
                _closePopover();
            }
        }

        function destroy() {
            _destroyed = true;
            document.removeEventListener('click', _onDocClick);
            for (var t = 0; t < _textareas.length; t++) {
                _textareas[t].removeEventListener('input', _onInput);
                _textareas[t].removeEventListener('scroll', _onScroll);
            }
            for (var id in _overlays) {
                var ov = _overlays[id];
                ov.backdrop.remove();
                ov.container.classList.remove('pii-has-matches', 'pii-all-dismissed', 'pii-overlay-container');
                if (ov.container.classList.length === 0 && ov.container.childNodes.length === 1) {
                    ov.container.parentNode.insertBefore(ov.textarea, ov.container);
                    ov.container.remove();
                }
            }
            if (_banner) _banner.remove();
            _closePopover();
        }

        return {
            gate: gate,
            scan: function() { _doScan(); },
            destroy: destroy
        };
    }

    // Inject protect() into PIIGuard namespace
    if (window.PIIGuard) {
        PIIGuard.protect = protect;
    }

})();
