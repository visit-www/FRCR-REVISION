/**
 * PII Guard v2 — UI Module
 * Layer 1: Ambient highlights (dotted underline) + header badge
 * Layer 2: Click-to-act popover (Redact / Remove / Dismiss per item)
 * Layer 3: Shield badge click → bulk Redact All / Remove All / Dismiss All dropdown
 *
 * API buttons are grayed out while unresolved PII exists — no gate modal needed.
 *
 * Depends on: pii-guard.js (window.PIIGuard)
 *
 * Usage:
 *   var ctrl = PIIGuard.protect({
 *       textareas: ['#editorInput', '#editorOutput'],
 *       bannerTarget: '.card-header .d-flex',
 *       apiButtons: ['#btnAskClaude', '#btnFinalizeToolbar', '#btnReviewReport2'],
 *       auditContext: 'smart-reporter'
 *   });
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
        var apiButtonSels = config.apiButtons || [];
        var auditContext = config.auditContext || 'unknown';

        var _textareas = [];
        var _overlays = {};
        var _badge = null;
        var _badgeDropdown = null;
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

        // ===================== HEADER BADGE =====================

        function _updateBadge(activeCount, dismissedCount) {
            if (!bannerTargetSel) return;
            if (_badge) { _badge.remove(); _badge = null; }
            _closeBadgeDropdown();
            if (activeCount === 0 && dismissedCount === 0) return;

            var target = document.querySelector(bannerTargetSel);
            if (!target) return;

            _badge = document.createElement('span');
            if (activeCount > 0) {
                _badge.className = 'pii-header-badge pii-header-badge-active';
                _badge.setAttribute('title', 'Please resolve PHI issues to comply with HIPAA guidelines');
                _badge.innerHTML = '<i class="fas fa-shield-alt"></i><span class="pii-header-badge-count">' + activeCount + '</span>';
                _badge.style.cursor = 'pointer';
                _badge.addEventListener('click', _onBadgeClick);
            } else {
                _badge.className = 'pii-header-badge pii-header-badge-clear';
                _badge.setAttribute('title', 'All PHI items reviewed (' + dismissedCount + ' dismissed)');
                _badge.innerHTML = '<i class="fas fa-shield-alt"></i>';
            }
            target.appendChild(_badge);
        }

        // ===================== BADGE DROPDOWN (bulk actions) =====================

        function _closeBadgeDropdown() {
            if (_badgeDropdown) { _badgeDropdown.remove(); _badgeDropdown = null; }
        }

        function _onBadgeClick(e) {
            e.stopPropagation();
            if (_badgeDropdown) { _closeBadgeDropdown(); return; }

            var hasHigh = false;
            for (var h = 0; h < _activeMatches.length; h++) {
                if (_activeMatches[h].tier === PIIGuard.TIER_HIGH) { hasHigh = true; break; }
            }

            _badgeDropdown = document.createElement('div');
            _badgeDropdown.className = 'pii-badge-dropdown';

            // Title
            _badgeDropdown.innerHTML =
                '<div class="pii-badge-dd-title">'
                + '<i class="fas fa-shield-alt"></i> '
                + _activeMatches.length + ' PHI item' + (_activeMatches.length !== 1 ? 's' : '')
                + '</div>';

            // Bulk buttons
            var btnsDiv = document.createElement('div');
            btnsDiv.className = 'pii-badge-dd-actions';

            var redactBtn = document.createElement('button');
            redactBtn.className = 'pii-badge-dd-btn pii-badge-dd-redact';
            redactBtn.innerHTML = '<i class="fas fa-eraser me-1"></i>Redact All';

            var removeBtn = document.createElement('button');
            removeBtn.className = 'pii-badge-dd-btn pii-badge-dd-remove';
            removeBtn.innerHTML = '<i class="fas fa-trash-alt me-1"></i>Remove All';

            var dismissBtn = document.createElement('button');
            dismissBtn.className = 'pii-badge-dd-btn pii-badge-dd-dismiss';
            dismissBtn.innerHTML = '<i class="fas fa-eye-slash me-1"></i>Dismiss All';

            btnsDiv.appendChild(redactBtn);
            btnsDiv.appendChild(removeBtn);
            btnsDiv.appendChild(dismissBtn);
            _badgeDropdown.appendChild(btnsDiv);

            // Dismiss confirmation area (hidden initially)
            var confirmArea = document.createElement('div');
            confirmArea.className = 'pii-badge-dd-confirm' + (hasHigh ? ' pii-high-warn' : '');
            confirmArea.innerHTML =
                '<div class="pii-badge-dd-confirm-msg">'
                + (hasHigh
                    ? '<strong>HIGH-sensitivity data detected.</strong> Dismissing will be audited and logged.'
                    : 'Dismissing all items will allow them through. This action will be audited.')
                + '</div>'
                + '<label class="pii-badge-dd-cb-row">'
                + '<input type="checkbox" class="pii-badge-dd-cb">'
                + '<span>I confirm this complies with data protection policy</span>'
                + '</label>'
                + '<button class="pii-badge-dd-ok" disabled>Confirm Dismiss All</button>';
            _badgeDropdown.appendChild(confirmArea);

            document.body.appendChild(_badgeDropdown);

            // Position below badge
            var rect = _badge.getBoundingClientRect();
            var ddW = _badgeDropdown.offsetWidth || 220;
            _badgeDropdown.style.top = (rect.bottom + 6) + 'px';
            _badgeDropdown.style.left = Math.min(rect.left, window.innerWidth - ddW - 10) + 'px';

            // Wire events
            redactBtn.addEventListener('click', function(ev) {
                ev.stopPropagation();
                _batchAction('redact', _activeMatches.slice());
                _closeBadgeDropdown();
            });
            removeBtn.addEventListener('click', function(ev) {
                ev.stopPropagation();
                _batchAction('remove', _activeMatches.slice());
                _closeBadgeDropdown();
            });
            dismissBtn.addEventListener('click', function(ev) {
                ev.stopPropagation();
                confirmArea.classList.add('visible');
                dismissBtn.style.display = 'none';
            });

            var cb = confirmArea.querySelector('.pii-badge-dd-cb');
            var okBtn = confirmArea.querySelector('.pii-badge-dd-ok');
            cb.addEventListener('change', function() { okBtn.disabled = !this.checked; });
            okBtn.addEventListener('click', function(ev) {
                ev.stopPropagation();
                if (!cb.checked) return;
                for (var i = 0; i < _activeMatches.length; i++) {
                    _dismissWithOverlaps(_activeMatches[i]);
                }
                var types = _activeMatches.map(function(m) { return m.type; });
                _logAction('batch_dismiss', types, _activeMatches.length);
                _closeBadgeDropdown();
                clearTimeout(_debounceTimer);
                _doScan();
            });
        }

        // ===================== API BUTTON GATING =====================

        function _updateApiButtons(hasActivePII) {
            for (var i = 0; i < apiButtonSels.length; i++) {
                var btns = document.querySelectorAll(apiButtonSels[i]);
                for (var b = 0; b < btns.length; b++) {
                    var btn = btns[b];
                    if (hasActivePII) {
                        btn.classList.add('pii-btn-blocked');
                        btn.setAttribute('data-pii-blocked', 'true');
                        btn.setAttribute('title', 'Resolve PHI issues before submitting');
                    } else {
                        btn.classList.remove('pii-btn-blocked');
                        btn.removeAttribute('data-pii-blocked');
                        var orig = btn.getAttribute('data-orig-title');
                        if (orig) btn.setAttribute('title', orig);
                    }
                }
            }
            // When all PII dismissed, set server-side override for subsequent requests
            if (!hasActivePII && _allMatches.length > 0) {
                if (typeof window._setPiiOverride === 'function') window._setPiiOverride();
            }
        }

        // Store original titles on first run
        function _storeOrigTitles() {
            for (var i = 0; i < apiButtonSels.length; i++) {
                var btns = document.querySelectorAll(apiButtonSels[i]);
                for (var b = 0; b < btns.length; b++) {
                    if (!btns[b].hasAttribute('data-orig-title')) {
                        btns[b].setAttribute('data-orig-title', btns[b].getAttribute('title') || '');
                    }
                }
            }
        }
        setTimeout(_storeOrigTitles, 100);

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

            var header = '<div class="pii-pop-header">'
                + '<span class="pii-pop-type">[' + escapeHtml(matchType) + ']</span>'
                + '<span class="pii-pop-match">"' + escapeHtml(truncate(matchText, 30)) + '"</span>'
                + '</div>';

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
                    ? 'This is HIGH-sensitivity data (e.g. NHS number, MRN). Dismissing will be audited and logged.'
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

            var rect = mark.getBoundingClientRect();
            var popW = _popover.offsetWidth || 220;
            _popover.style.left = Math.min(rect.left, window.innerWidth - popW - 10) + 'px';
            _popover.style.top = (rect.bottom + 4) + 'px';

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
                    _dismissWithOverlaps(match);
                    _logAction('dismiss', [match.type], 1);
                    clearTimeout(_debounceTimer);
                    _doScan();
                });
            }
        }

        // ===================== ACTIONS =====================

        // Dismiss a match AND all overlapping matches (text contained in or containing it)
        function _dismissWithOverlaps(match) {
            PIIGuard.dismiss(match);
            for (var i = 0; i < _allMatches.length; i++) {
                var other = _allMatches[i];
                if (other.match === match.match ||
                    match.match.indexOf(other.match) >= 0 ||
                    other.match.indexOf(match.match) >= 0) {
                    PIIGuard.dismiss(other);
                }
            }
        }

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

        // Merge overlapping matches — keep the longest match per text region
        function _dedupeOverlaps(matches) {
            if (!matches || matches.length <= 1) return matches;
            // Sort by index, then longest first
            var sorted = matches.slice().sort(function(a, b) {
                var d = (a.index || 0) - (b.index || 0);
                return d !== 0 ? d : (b.length || 0) - (a.length || 0);
            });
            var result = [sorted[0]];
            for (var i = 1; i < sorted.length; i++) {
                var prev = result[result.length - 1];
                var curr = sorted[i];
                var prevEnd = (prev.index || 0) + (prev.length || 0);
                // If current overlaps with previous, keep the longer one
                if ((curr.index || 0) < prevEnd) {
                    if ((curr.length || 0) > (prev.length || 0)) {
                        result[result.length - 1] = curr;
                    }
                    // else skip curr (prev is longer or equal)
                } else {
                    result.push(curr);
                }
            }
            return result;
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
                var matches = _dedupeOverlaps(result.matches || []);

                for (var i = 0; i < matches.length; i++) {
                    var m = matches[i];
                    var isDupe = false;
                    for (var j = 0; j < _allMatches.length; j++) {
                        if (_allMatches[j].match === m.match) {
                            isDupe = true; break;
                        }
                    }
                    if (!isDupe) _allMatches.push(m);
                    if (!isDupe && !PIIGuard.isDismissed(m)) _activeMatches.push(m);
                }

                if (_overlays[taId]) {
                    _renderOverlay(taId, text, matches);
                }
            }

            var dismissedCount = _allMatches.length - _activeMatches.length;
            _updateBadge(_activeMatches.length, dismissedCount);
            _updateApiButtons(_activeMatches.length > 0);

            // Set override flag for fetch interceptor when all dismissed
            if (_activeMatches.length === 0 && _allMatches.length > 0) {
                PIIGuard.setOverride(true);
            } else if (_activeMatches.length > 0) {
                PIIGuard.setOverride(false);
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
            if (_badgeDropdown && !_badgeDropdown.contains(e.target) && e.target !== _badge && !_badge.contains(e.target)) {
                _closeBadgeDropdown();
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
                delete _overlays[id];
            }
            if (_badge) { _badge.remove(); _badge = null; }
            _closePopover();
            _closeBadgeDropdown();
            _updateApiButtons(false);
        }

        // Public helper: check if PII is blocking
        function hasPII() {
            return _activeMatches.length > 0;
        }

        // Inject server-detected PII matches into the client UI so the user
        // can see, dismiss, redact, or remove them — then retry.
        function injectServerMatches(serverMatches) {
            if (!serverMatches || serverMatches.length === 0) return;

            // Un-dismiss any previously dismissed matches the server flagged
            for (var i = 0; i < serverMatches.length; i++) {
                if (serverMatches[i].match && PIIGuard.undismiss) {
                    PIIGuard.undismiss({ type: serverMatches[i].type, match: serverMatches[i].match });
                }
            }

            // If destroyed, fully re-initialize overlays and listeners
            if (_destroyed) {
                _destroyed = false;
                for (var t = 0; t < _textareas.length; t++) {
                    var ta = _textareas[t];
                    var taId = ta.id || ('pii-ta-' + t);
                    _setupOverlay(ta, taId);
                    ta.addEventListener('input', _onInput);
                    ta.addEventListener('scroll', _onScroll);
                }
                document.addEventListener('click', _onDocClick);
            }

            // Clear override — server just rejected us
            PIIGuard.setOverride(false);

            // Run a full scan — picks up everything the client can detect
            _doScan();

            // Inject any server-only matches the client scan missed
            for (var t2 = 0; t2 < _textareas.length; t2++) {
                var ta2 = _textareas[t2];
                var taId2 = ta2.id || ('pii-ta-' + t2);
                var text = ta2.value || '';

                for (var j = 0; j < serverMatches.length; j++) {
                    var sm = serverMatches[j];
                    if (!sm.match) continue;

                    var idx = text.indexOf(sm.match);
                    if (idx < 0) continue;

                    // Check if _doScan already found this match
                    var alreadyFound = false;
                    for (var k = 0; k < _allMatches.length; k++) {
                        if (_allMatches[k].type === sm.type && _allMatches[k].match === sm.match) {
                            alreadyFound = true; break;
                        }
                    }
                    if (alreadyFound) continue;

                    var m = {
                        type: sm.type || 'Unknown',
                        match: sm.match,
                        index: idx,
                        length: sm.match.length,
                        tier: sm.tier || 'medium',
                        description: sm.description || (sm.type + ' detected by server')
                    };
                    _allMatches.push(m);
                    _activeMatches.push(m);
                }

                // Re-render overlay if we added server-only matches
                if (_overlays[taId2]) {
                    var allForTa = [];
                    for (var n = 0; n < _allMatches.length; n++) {
                        if (text.indexOf(_allMatches[n].match) >= 0) {
                            allForTa.push(_allMatches[n]);
                        }
                    }
                    _renderOverlay(taId2, text, allForTa);
                }
            }

            // Final UI update
            var dismissedCount = _allMatches.length - _activeMatches.length;
            _updateBadge(_activeMatches.length, dismissedCount);
            _updateApiButtons(_activeMatches.length > 0);
        }

        return {
            scan: function() { _doScan(); },
            injectServerMatches: injectServerMatches,
            hasPII: hasPII,
            destroy: destroy
        };
    }

    // Inject protect() into PIIGuard namespace
    if (window.PIIGuard) {
        PIIGuard.protect = protect;
    }

})();
