/**
 * RadInsights Global Search
 * Debounced search against /api/algorithms/search — supports nav, mobile, and dashboard inputs.
 */
(function () {
    'use strict';

    var TYPE_CONFIG = {
        case:         { icon: 'fa-book-medical',    color: '#5E899E', bg: 'rgba(94,137,158,0.12)',  label: 'Case' },
        oncologic:    { icon: 'fa-dna',             color: '#6b46c1', bg: 'rgba(107,70,193,0.12)',  label: 'TNM Calculator' },
        tnm_case:     { icon: 'fa-layer-group',     color: '#6b46c1', bg: 'rgba(107,70,193,0.12)',  label: 'TNM Essentials' },
        protocol:     { icon: 'fa-shield-alt',      color: '#dc3545', bg: 'rgba(220,53,69,0.12)',   label: 'Protocol' },
        incidental:   { icon: 'fa-tools',           color: '#e96304', bg: 'rgba(233,99,4,0.12)',    label: 'Tool' },
        reporting:    { icon: 'fa-project-diagram', color: '#5E899E', bg: 'rgba(94,137,158,0.12)',  label: 'Algorithm' },
        template:     { icon: 'fa-clipboard-list',  color: '#2e7d5e', bg: 'rgba(168,213,186,0.18)', label: 'Template' },
        anatomy:      { icon: 'fa-bone',            color: '#6b46c1', bg: 'rgba(107,70,193,0.12)',  label: 'Anatomy' },
        pearl:        { icon: 'fa-gem',             color: '#b8860b', bg: 'rgba(255,193,7,0.15)',   label: 'Pearl' },
        intelligence: { icon: 'fa-lightbulb',       color: '#e96304', bg: 'rgba(233,99,4,0.10)',    label: 'RadInsight Note' }
    };

    function debounce(fn, ms) {
        var timer;
        return function () {
            var ctx = this, args = arguments;
            clearTimeout(timer);
            timer = setTimeout(function () { fn.apply(ctx, args); }, ms);
        };
    }

    function renderResults(results, container) {
        if (!results.length) {
            container.innerHTML = '<div class="global-search-empty"><i class="fas fa-search me-2"></i>No results found</div>';
            return;
        }
        var html = '';
        results.forEach(function (r) {
            var cfg = TYPE_CONFIG[r.type] || TYPE_CONFIG.case;
            var url = r.url || '#';
            var desc = r.description || r.subtitle || '';
            html += '<a href="' + url + '" class="global-search-result-item">' +
                '<div class="global-search-result-icon" style="background:' + cfg.bg + '; color:' + cfg.color + ';">' +
                '<i class="fas ' + cfg.icon + '"></i></div>' +
                '<div class="global-search-result-text">' +
                '<div class="global-search-result-title">' + escapeHtml(r.title || 'Untitled') + '</div>' +
                (desc ? '<div class="global-search-result-desc">' + escapeHtml(desc) + '</div>' : '') +
                '</div>' +
                '<span class="global-search-type-badge" style="background:' + cfg.bg + '; color:' + cfg.color + ';">' + cfg.label + '</span>' +
                '</a>';
        });
        container.innerHTML = html;
    }

    function escapeHtml(str) {
        var d = document.createElement('div');
        d.appendChild(document.createTextNode(str));
        return d.innerHTML;
    }

    function showLoading(container) {
        container.innerHTML = '<div class="global-search-loading"><i class="fas fa-spinner fa-spin me-2"></i>Searching...</div>';
        container.classList.remove('d-none');
    }

    /**
     * Initialise global search on a given input/results pair.
     * @param {string} inputId   — ID of the <input> element
     * @param {string} resultsId — ID of the results container <div>
     */
    window.initGlobalSearch = function (inputId, resultsId) {
        var input = document.getElementById(inputId);
        var resultsEl = document.getElementById(resultsId);
        if (!input || !resultsEl) return;

        var lastQuery = '';

        var doSearch = debounce(function () {
            var q = input.value.trim();
            if (q.length < 2) {
                resultsEl.classList.add('d-none');
                lastQuery = '';
                return;
            }
            if (q === lastQuery) return;
            lastQuery = q;
            showLoading(resultsEl);

            fetch('/api/algorithms/search?q=' + encodeURIComponent(q) + '&limit=8')
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (input.value.trim() !== q) return;  // stale
                    renderResults(data.results || [], resultsEl);
                    resultsEl.classList.remove('d-none');
                })
                .catch(function () {
                    resultsEl.innerHTML = '<div class="global-search-empty">Search unavailable</div>';
                    resultsEl.classList.remove('d-none');
                });
        }, 300);

        input.addEventListener('input', doSearch);
        input.addEventListener('focus', function () {
            if (input.value.trim().length >= 2 && resultsEl.innerHTML) {
                resultsEl.classList.remove('d-none');
            }
        });

        // Dismiss on click outside
        document.addEventListener('click', function (e) {
            if (!input.contains(e.target) && !resultsEl.contains(e.target)) {
                resultsEl.classList.add('d-none');
            }
        });

        // Dismiss on Escape
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                resultsEl.classList.add('d-none');
                input.blur();
            }
        });
    };
})();
