/**
 * PII Guard UI Kit — 3-Layer Progressive Escalation
 *
 * Layer 1: Ambient Awareness (inline highlights, floating widget, header badge, border glow)
 * Layer 2: Detail on Demand (popover with per-match actions)
 * Layer 3: Commit-Gate Modal (blocking modal before AI calls)
 *
 * Depends on: pii-guard.js (window.PIIGuard)
 */
(function() {
    'use strict';

    var HARD_TYPES = [
        'NHS Number', 'US SSN', 'MRN / Hospital ID', 'Patient Name',
        'Possible Patient ID', 'Aadhaar Number', 'PAN Card', 'UK National Insurance Number'
    ];

    function isHard(type) {
        return HARD_TYPES.indexOf(type) !== -1;
    }

    function maskText(text) {
        if (!text) return '';
        if (text.length <= 3) return text + '***';
        return text.substring(0, 3) + text.substring(3).replace(/[A-Za-z0-9]/g, '*');
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    function getTypeColor(type) {
        var colors = (window.PIIGuard && PIIGuard.TYPE_COLORS) || {};
        return colors[type] || '#dc3545';
    }

    function hexToRgba(hex, alpha) {
        hex = hex.replace('#', '');
        var r = parseInt(hex.substring(0, 2), 16);
        var g = parseInt(hex.substring(2, 4), 16);
        var b = parseInt(hex.substring(4, 6), 16);
        return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
    }

    /** Detect if a textarea has a dark background */
    function isDarkBg(textarea) {
        var bg = window.getComputedStyle(textarea).backgroundColor;
        if (!bg || bg === 'transparent' || bg === 'rgba(0, 0, 0, 0)') {
            // Check parent
            var parent = textarea.closest('.pacs-output-card, .card');
            if (parent) bg = window.getComputedStyle(parent).backgroundColor;
        }
        if (!bg || bg === 'transparent') return false;
        var m = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
        if (!m) return false;
        var luminance = (0.299 * parseInt(m[1]) + 0.587 * parseInt(m[2]) + 0.114 * parseInt(m[3])) / 255;
        return luminance < 0.35;
    }

    /** Copy computed text styles from textarea to backdrop */
    function syncStyles(textarea, backdrop) {
        var cs = window.getComputedStyle(textarea);
        var props = [
            'fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'lineHeight',
            'letterSpacing', 'wordSpacing', 'textIndent', 'whiteSpace', 'wordWrap',
            'overflowWrap', 'wordBreak', 'paddingTop', 'paddingRight', 'paddingBottom',
            'paddingLeft', 'borderTopWidth', 'borderRightWidth', 'borderBottomWidth',
            'borderLeftWidth', 'boxSizing', 'textTransform'
        ];
        for (var i = 0; i < props.length; i++) {
            backdrop.style[props[i]] = cs[props[i]];
        }
        backdrop.style.width = textarea.offsetWidth + 'px';
        backdrop.style.height = textarea.offsetHeight + 'px';
    }

    // ===================== PIIGuardUI.attach() =====================

    function attach(config) {
        if (!window.PIIGuard) {
            console.warn('PIIGuardUI: PIIGuard not loaded');
            return null;
        }

        config = config || {};
        var selectors = config.textareas || [];
        var headerSelector = config.headerSelector || null;
        var debounceMs = config.debounceMs || 400;
        var enableOverlay = config.highlightOverlay !== false;
        var enableWidget = config.floatingWidget !== false;
        var enableBadge = config.headerBadge !== false;
        var auditContext = config.auditContext || 'unknown';
        var onStateChange = config.onStateChange || null;

        var _textareas = [];
        var _overlays = {};     // keyed by textarea id/index
        var _widgets = {};
        var _badge = null;
        var _detailPopover = null;
        var _debounceTimer = null;
        var _allMatches = [];   // current filtered matches across all textareas
        var _matchesByTa = {};  // matches per textarea
        var _blocked = false;
        var _destroyed = false;

        // Resolve textareas
        for (var s = 0; s < selectors.length; s++) {
            var el = document.querySelector(selectors[s]);
            if (el) _textareas.push(el);
        }
        if (_textareas.length === 0) return null;

        // --- Setup overlay containers ---
        for (var t = 0; t < _textareas.length; t++) {
            var ta = _textareas[t];
            var taId = ta.id || ('pii-ta-' + t);

            if (enableOverlay) {
                _setupOverlay(ta, taId);
            }
            if (enableWidget) {
                _setupWidget(ta, taId);
            }

            // Attach input listeners
            ta.addEventListener('input', _onInput);
            ta.addEventListener('scroll', _onScroll);
        }

        // Setup header badge
        if (enableBadge && headerSelector) {
            _setupBadge(headerSelector);
        }

        // Resize observer for overlay sync
        if (enableOverlay && window.ResizeObserver) {
            var ro = new ResizeObserver(function() {
                if (_destroyed) return;
                _syncAllOverlays();
            });
            for (var r = 0; r < _textareas.length; r++) {
                ro.observe(_textareas[r]);
            }
        }

        // Close detail popover on outside click
        document.addEventListener('click', _onDocClick);

        // Initial scan
        setTimeout(_doScan, 50);

        // ===================== OVERLAY =====================
        function _setupOverlay(textarea, id) {
            var parent = textarea.parentNode;
            // Wrap if not already in overlay container
            if (!parent.classList.contains('pii-overlay-container')) {
                var wrapper = document.createElement('div');
                wrapper.className = 'pii-overlay-container';
                parent.insertBefore(wrapper, textarea);
                wrapper.appendChild(textarea);
                parent = wrapper;
            }
            var backdrop = document.createElement('div');
            backdrop.className = 'pii-overlay-backdrop';
            if (isDarkBg(textarea)) {
                backdrop.style.background = '#0d1117';
            }
            parent.insertBefore(backdrop, textarea);
            syncStyles(textarea, backdrop);
            _overlays[id] = { backdrop: backdrop, container: parent, textarea: textarea };
        }

        function _renderOverlay(id, text, matches) {
            var ov = _overlays[id];
            if (!ov) return;
            syncStyles(ov.textarea, ov.backdrop);

            if (!matches || matches.length === 0) {
                ov.backdrop.innerHTML = escapeHtml(text);
                ov.container.classList.remove('pii-has-matches');
                return;
            }

            ov.container.classList.add('pii-has-matches');
            var dark = isDarkBg(ov.textarea);
            var alpha = dark ? 0.35 : 0.2;

            // Sort matches by index (position in text) for correct rendering
            var sorted = matches.slice().sort(function(a, b) { return (a.index || 0) - (b.index || 0); });

            // Build highlighted text
            var html = '';
            var lastEnd = 0;
            for (var i = 0; i < sorted.length; i++) {
                var m = sorted[i];
                var idx = text.indexOf(m.match, lastEnd);
                if (idx === -1) idx = text.indexOf(m.match);
                if (idx === -1) continue;
                // Text before match
                html += escapeHtml(text.substring(lastEnd, idx));
                // The match itself
                var color = getTypeColor(m.type);
                html += '<mark class="pii-overlay-mark" style="background:' + hexToRgba(color, alpha) + ';">' +
                    escapeHtml(m.match) + '</mark>';
                lastEnd = idx + m.match.length;
            }
            html += escapeHtml(text.substring(lastEnd));
            ov.backdrop.innerHTML = html;
        }

        function _syncAllOverlays() {
            for (var id in _overlays) {
                syncStyles(_overlays[id].textarea, _overlays[id].backdrop);
            }
        }

        // ===================== WIDGET =====================
        function _setupWidget(textarea, id) {
            var container = textarea.closest('.pii-overlay-container') || textarea.parentNode;
            var widget = document.createElement('div');
            widget.className = 'pii-float-widget';
            widget.innerHTML = '<i class="fas fa-shield-alt" style="font-size:0.7rem;"></i><span class="pii-widget-count"></span>';
            widget.addEventListener('click', function(e) {
                e.stopPropagation();
                _toggleDetail(container, widget);
            });
            container.appendChild(widget);
            _widgets[id] = widget;
        }

        function _updateWidget(id, matches) {
            var w = _widgets[id];
            if (!w) return;
            if (!matches || matches.length === 0) {
                w.classList.remove('visible', 'pii-float-widget--hard', 'pii-float-widget--soft');
                return;
            }
            var hasHard = matches.some(function(m) { return isHard(m.type); });
            w.classList.add('visible');
            w.classList.toggle('pii-float-widget--hard', hasHard);
            w.classList.toggle('pii-float-widget--soft', !hasHard);
            w.querySelector('.pii-widget-count').textContent = matches.length;
        }

        // ===================== BADGE =====================
        function _setupBadge(selector) {
            var header = document.querySelector(selector);
            if (!header) return;
            _badge = document.createElement('span');
            _badge.className = 'badge bg-danger pii-header-badge ms-2';
            _badge.style.cursor = 'pointer';
            _badge.addEventListener('click', function(e) {
                e.stopPropagation();
                // Find first widget container for popover anchoring
                var firstId = _textareas[0] && (_textareas[0].id || 'pii-ta-0');
                var w = _widgets[firstId];
                if (w) {
                    var container = w.parentNode;
                    _toggleDetail(container, w);
                }
            });
            header.appendChild(_badge);
        }

        function _updateBadge(total) {
            if (!_badge) return;
            if (total === 0) {
                _badge.classList.remove('visible');
            } else {
                _badge.classList.add('visible');
                _badge.textContent = 'PII: ' + total;
            }
        }

        // ===================== DETAIL POPOVER =====================
        function _toggleDetail(container, anchorWidget) {
            if (_detailPopover && _detailPopover.classList.contains('open')) {
                _closeDetail();
                return;
            }
            _showDetail(container, anchorWidget);
        }

        function _showDetail(container, anchorWidget) {
            _closeDetail();
            if (_allMatches.length === 0) return;

            _detailPopover = document.createElement('div');
            _detailPopover.className = 'pii-float-detail open';

            // Header with batch buttons
            var header = document.createElement('div');
            header.className = 'pii-detail-header';
            header.innerHTML =
                '<span class="pii-detail-header-title">' + _allMatches.length + ' PII match' + (_allMatches.length !== 1 ? 'es' : '') + '</span>' +
                '<div class="pii-detail-batch-btns">' +
                    '<button class="pii-detail-btn-redact" data-batch="redact">Redact All</button>' +
                    '<button class="pii-detail-btn-remove" data-batch="remove">Remove All</button>' +
                '</div>';
            _detailPopover.appendChild(header);

            header.querySelector('[data-batch="redact"]').addEventListener('click', function(e) {
                e.stopPropagation();
                _batchAction('redact');
            });
            header.querySelector('[data-batch="remove"]').addEventListener('click', function(e) {
                e.stopPropagation();
                _batchAction('remove');
            });

            // Match rows
            var body = document.createElement('div');
            body.style.padding = '4px 0';
            for (var i = 0; i < _allMatches.length; i++) {
                body.appendChild(_createDetailRow(_allMatches[i], i));
            }
            _detailPopover.appendChild(body);

            container.appendChild(_detailPopover);
        }

        function _closeDetail() {
            if (_detailPopover) {
                _detailPopover.remove();
                _detailPopover = null;
            }
        }

        function _createDetailRow(match, index) {
            var row = document.createElement('div');
            row.className = 'pii-detail-row';
            row.dataset.index = index;

            var color = getTypeColor(match.type);
            row.innerHTML =
                '<span class="pii-detail-dot" style="background:' + color + ';"></span>' +
                '<span class="pii-detail-text"><strong>' + escapeHtml(match.type) + ':</strong> ' + escapeHtml(maskText(match.match)) + '</span>' +
                '<span class="pii-detail-actions">' +
                    '<button class="act-redact" data-action="redact">Redact</button>' +
                    '<button class="act-remove" data-action="remove">Remove</button>' +
                    '<button class="act-dismiss" data-action="dismiss">Dismiss</button>' +
                '</span>';

            row.querySelector('.act-redact').addEventListener('click', function(e) { e.stopPropagation(); _singleAction('redact', match, row); });
            row.querySelector('.act-remove').addEventListener('click', function(e) { e.stopPropagation(); _singleAction('remove', match, row); });
            row.querySelector('.act-dismiss').addEventListener('click', function(e) { e.stopPropagation(); _singleDismiss(match, row); });

            return row;
        }

        // ===================== ACTIONS =====================
        function _singleAction(action, match, row) {
            var replacement = action === 'redact' ? '[REDACTED]' : '';
            for (var t = 0; t < _textareas.length; t++) {
                var ta = _textareas[t];
                if (ta.value.indexOf(match.match) !== -1) {
                    ta.value = ta.value.split(match.match).join(replacement);
                    if (action === 'remove') ta.value = ta.value.replace(/  +/g, ' ');
                    // Trigger change for any external listeners
                    ta.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }
            _logAction(action, [match.type], 1);
            if (row) { row.classList.add('fading'); setTimeout(function() { row.remove(); }, 300); }
            _doScan();
        }

        function _batchAction(action) {
            var matches = _allMatches.slice();
            for (var t = 0; t < _textareas.length; t++) {
                var ta = _textareas[t];
                if (action === 'redact') {
                    ta.value = PIIGuard.redact(ta.value, matches);
                } else {
                    ta.value = PIIGuard.remove(ta.value, matches);
                }
                ta.dispatchEvent(new Event('input', { bubbles: true }));
            }
            var types = matches.map(function(m) { return m.type; });
            _logAction('batch_' + action, types, matches.length);
            _closeDetail();
            _doScan();
        }

        function _singleDismiss(match, row) {
            _showDismissConfirm(function() {
                PIIGuard.dismiss(match);
                _logAction('dismiss', [match.type], 1);
                if (row) { row.classList.add('fading'); setTimeout(function() { row.remove(); }, 300); }
                _doScan();
            });
        }

        function _showDismissConfirm(onConfirm) {
            var existing = document.getElementById('piiDismissConfirmOverlay');
            if (existing) existing.remove();

            var overlay = document.createElement('div');
            overlay.id = 'piiDismissConfirmOverlay';
            overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:11000;display:flex;align-items:center;justify-content:center;';

            var dialog = document.createElement('div');
            dialog.style.cssText = 'background:#fff;border-radius:8px;padding:1.25rem;max-width:420px;width:90%;box-shadow:0 8px 24px rgba(0,0,0,0.2);';
            dialog.innerHTML =
                '<div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.75rem;">' +
                    '<i class="fas fa-exclamation-triangle" style="color:#dc3545;font-size:1.1rem;"></i>' +
                    '<strong style="font-size:0.95rem;">Confirm Dismissal</strong>' +
                '</div>' +
                '<p style="font-size:0.82rem;color:#444;margin-bottom:0.75rem;line-height:1.5;">' +
                    'Dismissing a PII flag means this text will be sent to external AI services. ' +
                    'You must ensure the flagged text does <strong>not</strong> contain protected health information (PHI).' +
                '</p>' +
                '<div style="background:#fff3cd;border:1px solid #ffc107;border-radius:6px;padding:0.5rem 0.75rem;margin-bottom:0.75rem;">' +
                    '<label style="display:flex;align-items:flex-start;gap:0.5rem;cursor:pointer;font-size:0.8rem;color:#664d03;margin:0;">' +
                        '<input type="checkbox" class="pii-dismiss-cb" style="margin-top:3px;flex-shrink:0;">' +
                        '<span>I confirm this is <strong>not</strong> patient-identifiable information and I authorise this dismissal. This action will be logged.</span>' +
                    '</label>' +
                '</div>' +
                '<div style="display:flex;gap:0.5rem;justify-content:flex-end;">' +
                    '<button class="btn btn-sm btn-outline-secondary pii-dismiss-cancel-btn">Cancel</button>' +
                    '<button class="btn btn-sm pii-dismiss-confirm-btn" style="background:#dc3545;color:#fff;opacity:0.5;pointer-events:none;" disabled>Dismiss</button>' +
                '</div>';

            overlay.appendChild(dialog);
            document.body.appendChild(overlay);

            var checkbox = dialog.querySelector('.pii-dismiss-cb');
            var confirmBtn = dialog.querySelector('.pii-dismiss-confirm-btn');
            var cancelBtn = dialog.querySelector('.pii-dismiss-cancel-btn');

            checkbox.addEventListener('change', function() {
                confirmBtn.disabled = !this.checked;
                confirmBtn.style.opacity = this.checked ? '1' : '0.5';
                confirmBtn.style.pointerEvents = this.checked ? 'auto' : 'none';
            });
            cancelBtn.addEventListener('click', function() { overlay.remove(); });
            overlay.addEventListener('click', function(e) { if (e.target === overlay) overlay.remove(); });
            confirmBtn.addEventListener('click', function() {
                overlay.remove();
                onConfirm();
            });
            setTimeout(function() { checkbox.focus(); }, 100);
        }

        // ===================== SCANNING =====================
        function _onInput() {
            clearTimeout(_debounceTimer);
            _debounceTimer = setTimeout(_doScan, debounceMs);
        }

        function _onScroll() {
            // Sync overlay scroll
            for (var id in _overlays) {
                var ov = _overlays[id];
                ov.backdrop.scrollTop = ov.textarea.scrollTop;
            }
        }

        function _doScan() {
            if (_destroyed) return;
            _allMatches = [];
            _matchesByTa = {};

            for (var t = 0; t < _textareas.length; t++) {
                var ta = _textareas[t];
                var taId = ta.id || ('pii-ta-' + t);
                var text = ta.value || '';
                var result = PIIGuard.scan(text);
                var matches = PIIGuard.filterDismissed ? PIIGuard.filterDismissed(result.matches || []) : (result.matches || []);

                _matchesByTa[taId] = matches;

                // Dedupe into _allMatches
                for (var i = 0; i < matches.length; i++) {
                    var m = matches[i];
                    var isDupe = false;
                    for (var j = 0; j < _allMatches.length; j++) {
                        if (_allMatches[j].type === m.type && _allMatches[j].match === m.match) {
                            isDupe = true;
                            break;
                        }
                    }
                    if (!isDupe) _allMatches.push(m);
                }

                // Update overlay
                if (enableOverlay && _overlays[taId]) {
                    _renderOverlay(taId, text, matches);
                }
                // Update widget
                if (enableWidget) {
                    _updateWidget(taId, matches);
                }
            }

            // Update badge
            if (enableBadge) {
                _updateBadge(_allMatches.length);
            }

            // Update blocked state
            var wasBlocked = _blocked;
            _blocked = _allMatches.length > 0;

            if (onStateChange && (_blocked !== wasBlocked || _allMatches.length > 0)) {
                onStateChange({ blocked: _blocked, count: _allMatches.length, matches: _allMatches });
            }
        }

        // ===================== GATE (Layer 3) =====================
        function gate() {
            return new Promise(function(resolve) {
                if (_destroyed) { resolve({ allowed: true }); return; }

                // Fresh scan
                _doScan();

                if (_allMatches.length === 0) {
                    resolve({ allowed: true });
                    return;
                }

                _showGateModal(_allMatches.slice(), resolve);
            });
        }

        function _showGateModal(matches, resolve) {
            var hard = matches.filter(function(m) { return isHard(m.type); });
            var soft = matches.filter(function(m) { return !isHard(m.type); });
            var resolved = false;

            function finish(result) {
                if (resolved) return;
                resolved = true;
                if (overlay.parentNode) overlay.remove();
                // Re-scan to update UI
                _doScan();
                resolve(result);
            }

            var overlay = document.createElement('div');
            overlay.className = 'pii-gate-overlay';

            var modal = document.createElement('div');
            modal.className = 'pii-gate-modal';

            // Header
            modal.innerHTML =
                '<div class="pii-gate-modal-header">' +
                    '<i class="fas fa-shield-alt"></i>' +
                    '<h5>Patient Data Review Required</h5>' +
                    '<button class="pii-gate-close">&times;</button>' +
                '</div>';

            var body = document.createElement('div');
            body.className = 'pii-gate-body';

            // Hard section
            var hardSection = null;
            if (hard.length > 0) {
                hardSection = document.createElement('div');
                hardSection.className = 'pii-gate-section pii-gate-hard-section';
                hardSection.innerHTML = '<div class="pii-gate-section-title"><i class="fas fa-exclamation-circle me-1"></i>Must Resolve (' + hard.length + ')</div>';
                for (var h = 0; h < hard.length; h++) {
                    hardSection.appendChild(_createGateRow(hard[h], 'hard', onMatchResolved));
                }
                body.appendChild(hardSection);
            }

            // Soft section
            var softSection = null;
            if (soft.length > 0) {
                softSection = document.createElement('div');
                softSection.className = 'pii-gate-section pii-gate-soft-section';
                softSection.innerHTML = '<div class="pii-gate-section-title"><i class="fas fa-info-circle me-1"></i>Review (' + soft.length + ')</div>';
                for (var s = 0; s < soft.length; s++) {
                    softSection.appendChild(_createGateRow(soft[s], 'soft', onMatchResolved));
                }
                body.appendChild(softSection);
            }

            modal.appendChild(body);

            // Footer
            var footer = document.createElement('div');
            footer.className = 'pii-gate-footer';

            // Confirm checkbox row
            var confirmRow = document.createElement('div');
            confirmRow.className = 'pii-gate-confirm-row';
            confirmRow.innerHTML =
                '<input type="checkbox" class="pii-gate-checkbox">' +
                '<span>I confirm this does not contain protected health information (PHI). This will be logged.</span>';
            footer.appendChild(confirmRow);

            var btnRow = document.createElement('div');
            btnRow.className = 'pii-gate-btn-row';
            btnRow.innerHTML =
                '<button class="pii-gate-btn-cancel">Cancel</button>' +
                '<button class="pii-gate-btn-remove-all">Remove All</button>' +
                '<button class="pii-gate-btn-redact-all">Redact All & Continue</button>' +
                '<button class="pii-gate-btn-override" disabled>Send Anyway</button>';
            footer.appendChild(btnRow);
            modal.appendChild(footer);

            overlay.appendChild(modal);
            document.body.appendChild(overlay);

            // Wire events
            var closeBtn = modal.querySelector('.pii-gate-close');
            var cancelBtn = modal.querySelector('.pii-gate-btn-cancel');
            var redactAllBtn = modal.querySelector('.pii-gate-btn-redact-all');
            var removeAllBtn = modal.querySelector('.pii-gate-btn-remove-all');
            var overrideBtn = modal.querySelector('.pii-gate-btn-override');
            var checkbox = modal.querySelector('.pii-gate-checkbox');

            // Remaining match tracking
            var remainingHard = hard.slice();
            var remainingSoft = soft.slice();

            function updateOverrideState() {
                var canOverride = remainingHard.length === 0 && checkbox.checked;
                overrideBtn.disabled = !canOverride;
                // Hide override if there are still hard matches
                overrideBtn.style.display = remainingHard.length > 0 ? 'none' : '';
            }
            updateOverrideState();

            function onMatchResolved(match, action) {
                // Apply action to textareas
                var replacement = action === 'redact' ? '[REDACTED]' : '';
                for (var t = 0; t < _textareas.length; t++) {
                    var ta = _textareas[t];
                    if (ta.value.indexOf(match.match) !== -1) {
                        ta.value = ta.value.split(match.match).join(replacement);
                        if (action === 'remove') ta.value = ta.value.replace(/  +/g, ' ');
                    }
                }
                _logAction(action, [match.type], 1);

                // Remove from tracking
                remainingHard = remainingHard.filter(function(m) { return m.match !== match.match || m.type !== match.type; });
                remainingSoft = remainingSoft.filter(function(m) { return m.match !== match.match || m.type !== match.type; });

                // Update section counts
                if (hardSection) {
                    var hTitle = hardSection.querySelector('.pii-gate-section-title');
                    hTitle.innerHTML = '<i class="fas fa-exclamation-circle me-1"></i>Must Resolve (' + remainingHard.length + ')';
                    if (remainingHard.length === 0) hardSection.style.display = 'none';
                }
                if (softSection) {
                    var sTitle = softSection.querySelector('.pii-gate-section-title');
                    sTitle.innerHTML = '<i class="fas fa-info-circle me-1"></i>Review (' + remainingSoft.length + ')';
                    if (remainingSoft.length === 0) softSection.style.display = 'none';
                }

                // If all resolved, auto-close
                if (remainingHard.length === 0 && remainingSoft.length === 0) {
                    finish({ allowed: true, action: action });
                    return;
                }

                updateOverrideState();
            }

            closeBtn.addEventListener('click', function() { finish({ allowed: false, reason: 'cancel' }); });
            cancelBtn.addEventListener('click', function() { finish({ allowed: false, reason: 'cancel' }); });

            redactAllBtn.addEventListener('click', function() {
                var allRemaining = remainingHard.concat(remainingSoft);
                for (var t = 0; t < _textareas.length; t++) {
                    _textareas[t].value = PIIGuard.redact(_textareas[t].value, allRemaining);
                }
                var types = allRemaining.map(function(m) { return m.type; });
                _logAction('batch_redact', types, allRemaining.length);
                finish({ allowed: true, action: 'redact' });
            });

            removeAllBtn.addEventListener('click', function() {
                var allRemaining = remainingHard.concat(remainingSoft);
                for (var t = 0; t < _textareas.length; t++) {
                    _textareas[t].value = PIIGuard.remove(_textareas[t].value, allRemaining);
                }
                var types = allRemaining.map(function(m) { return m.type; });
                _logAction('batch_remove', types, allRemaining.length);
                finish({ allowed: true, action: 'remove' });
            });

            checkbox.addEventListener('change', function() { updateOverrideState(); });

            overrideBtn.addEventListener('click', function() {
                var types = remainingSoft.map(function(m) { return m.type; });
                _logAction('override', types, remainingSoft.length);
                finish({ allowed: true, action: 'override' });
            });

            // Prevent closing on backdrop click (static backdrop)
            overlay.addEventListener('click', function(e) {
                if (e.target === overlay) {
                    modal.style.animation = 'none';
                    modal.offsetHeight; // force reflow
                    modal.style.animation = 'piiGateShake 0.3s ease';
                }
            });
        }

        function _createGateRow(match, hardOrSoft, onResolved) {
            var row = document.createElement('div');
            row.className = 'pii-gate-match-row';

            var color = getTypeColor(match.type);
            var dotColor = hardOrSoft === 'hard' ? '#dc3545' : '#e96304';
            var dismissBtn = hardOrSoft === 'soft'
                ? '<button class="gate-dismiss" data-action="dismiss">Dismiss</button>'
                : '';

            row.innerHTML =
                '<span class="pii-gate-match-dot" style="background:' + dotColor + ';"></span>' +
                '<span class="pii-gate-match-text">' +
                    '<span class="pii-gate-match-type">' + escapeHtml(match.type) + ':</span>' +
                    '<span class="pii-gate-match-preview">' + escapeHtml(maskText(match.match)) + '</span>' +
                '</span>' +
                '<span class="pii-gate-match-actions">' +
                    '<button class="gate-redact" data-action="redact">Redact</button>' +
                    '<button class="gate-remove" data-action="remove">Remove</button>' +
                    dismissBtn +
                '</span>';

            row.querySelector('.gate-redact').addEventListener('click', function(e) {
                e.stopPropagation();
                row.classList.add('resolved');
                onResolved(match, 'redact');
            });
            row.querySelector('.gate-remove').addEventListener('click', function(e) {
                e.stopPropagation();
                row.classList.add('resolved');
                onResolved(match, 'remove');
            });
            var dismissEl = row.querySelector('.gate-dismiss');
            if (dismissEl) {
                dismissEl.addEventListener('click', function(e) {
                    e.stopPropagation();
                    _showDismissConfirm(function() {
                        PIIGuard.dismiss(match);
                        row.classList.add('resolved');
                        onResolved(match, 'dismiss');
                    });
                });
            }

            return row;
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
            if (_detailPopover && !_detailPopover.contains(e.target)) {
                var clickedWidget = false;
                for (var id in _widgets) {
                    if (_widgets[id].contains(e.target)) { clickedWidget = true; break; }
                }
                if (!clickedWidget && !(_badge && _badge.contains(e.target))) {
                    _closeDetail();
                }
            }
        }

        // ===================== PUBLIC CONTROLLER =====================
        function scan() { _doScan(); }

        function redactAll() {
            _batchAction('redact');
        }

        function destroy() {
            _destroyed = true;
            document.removeEventListener('click', _onDocClick);
            for (var t = 0; t < _textareas.length; t++) {
                _textareas[t].removeEventListener('input', _onInput);
                _textareas[t].removeEventListener('scroll', _onScroll);
            }
            // Remove overlay elements
            for (var id in _overlays) {
                var ov = _overlays[id];
                ov.backdrop.remove();
                ov.container.classList.remove('pii-has-matches', 'pii-overlay-container');
                // Unwrap textarea if we wrapped it
                if (ov.container.classList.length === 0 && ov.container.childNodes.length === 1) {
                    ov.container.parentNode.insertBefore(ov.textarea, ov.container);
                    ov.container.remove();
                }
            }
            // Remove widgets
            for (var wid in _widgets) { _widgets[wid].remove(); }
            // Remove badge
            if (_badge) _badge.remove();
            _closeDetail();
        }

        return {
            gate: gate,
            scan: scan,
            redactAll: redactAll,
            destroy: destroy,
            getState: function() {
                return { blocked: _blocked, count: _allMatches.length, matches: _allMatches };
            }
        };
    }

    // ===================== PUBLIC NAMESPACE =====================
    window.PIIGuardUI = {
        attach: attach
    };

})();
