/**
 * Selection Verify — Global text selection popup.
 *
 * Shows a floating popup when user selects text in content areas.
 * - All users: "Flag" button to report inaccuracies
 * - Admin only: "Verify" button (PubMed search — future Phase 1)
 *
 * Usage: SelectionVerify.init({ isAdmin: true/false })
 * Auto-detects content type from closest [data-content-type] attribute.
 */
(function() {
    'use strict';

    var _popup = null;
    var _isAdmin = false;
    var _currentSelection = { text: '', contentType: '', contentId: '' };

    // Content areas where selection popup should appear
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

        var html = '';

        // Flag button (all users)
        html += '<button class="btn btn-sm py-0 px-2" style="font-size:.75rem;background:var(--brand-neutral);color:#fff;border:none;border-radius:6px;" ' +
            'onclick="SelectionVerify._flag()" title="Flag this content">' +
            '<i class="fas fa-flag me-1"></i>Flag</button>';

        // Admin verify button (future — PubMed search)
        if (_isAdmin) {
            html += '<button class="btn btn-sm py-0 px-2" style="font-size:.75rem;background:#198754;color:#fff;border:none;border-radius:6px;" ' +
                'onclick="SelectionVerify._verify()" title="Verify with PubMed">' +
                '<i class="fas fa-check-circle me-1"></i>Verify</button>';
        }

        _popup.innerHTML = html;
        _popup.style.display = 'flex';

        // Position: above selection, centered
        var popW = 150;
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
        // Walk up from selection to find data-content-type
        var node = el;
        while (node && node !== document.body) {
            if (node.dataset && node.dataset.contentType) return node.dataset.contentType;
            if (node.dataset && node.dataset.contentId) {
                _currentSelection.contentId = node.dataset.contentId;
            }
            node = node.parentElement;
        }

        // Fallback: detect from container class/id
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
        // Small delay to let selection finalize
        setTimeout(function() {
            var sel = window.getSelection();
            var text = (sel ? sel.toString() : '').trim();

            if (text.length < 3) {
                _hide();
                return;
            }

            // Check if selection is within a content area
            var anchorNode = sel.anchorNode;
            var el = anchorNode && anchorNode.nodeType === 3 ? anchorNode.parentElement : anchorNode;
            if (!el || !el.closest(CONTENT_SELECTORS)) {
                _hide();
                return;
            }

            _currentSelection.text = text.substring(0, 500);
            _currentSelection.contentType = _detectContentType(el);
            _currentSelection.contentId = '';

            // Get position from selection range
            var range = sel.getRangeAt(0);
            var rect = range.getBoundingClientRect();
            _show(rect.left + rect.width / 2, rect.top);
        }, 50);
    }

    // Public API
    window.SelectionVerify = {
        init: function(opts) {
            opts = opts || {};
            _isAdmin = !!opts.isAdmin;
            document.addEventListener('mouseup', _onMouseUp);
            // Hide on click outside
            document.addEventListener('mousedown', function(e) {
                if (_popup && !_popup.contains(e.target)) _hide();
            });
            // Hide on scroll
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
            // Phase 1 future: open PubMed search panel
            if (window.showToast) {
                showToast('PubMed verification coming soon. Use Flag to report issues for now.', 'info');
            }
        },
    };
})();
