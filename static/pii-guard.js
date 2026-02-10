/**
 * PII Guard — Global Patient Data Detection
 * Dual-layer protection: client-side (this file) + server-side (pii_guard.py)
 * Loaded globally via base.html to intercept all fetch POST/PUT requests.
 */
(function() {
    'use strict';

    // ======================== PII PATTERNS ========================
    const PII_PATTERNS = [
        {
            type: 'NHS Number',
            regex: /\b\d{3}[-\s]?\d{3}[-\s]?\d{4}\b/g,
            description: 'NHS number detected'
        },
        {
            type: 'MRN / Hospital ID',
            regex: /\b(?:MRN|mrn|Mrn|hospital\s*(?:id|no|number|#)|hosp\s*id)[:\s#]*\d{4,10}\b/gi,
            description: 'Medical Record Number detected'
        },
        {
            type: 'Date of Birth',
            regex: /\b(?:DOB|dob|D\.O\.B|born|date\s*of\s*birth|birth\s*date)[:\s]*\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b/gi,
            description: 'Date of birth detected'
        },
        {
            type: 'UK Postcode',
            regex: /\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b/gi,
            description: 'UK postcode detected'
        },
        {
            type: 'Phone Number',
            regex: /\b(?:\+44|0)\d{4}[\s-]?\d{5,6}\b/g,
            description: 'Phone number detected'
        },
        {
            type: 'Email Address',
            regex: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g,
            description: 'Email address detected'
        },
        {
            type: 'Patient Name',
            regex: /\b(?:patient|pt|name)[:\s]+(?:Mr|Mrs|Ms|Miss|Dr)\.?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b/gi,
            description: 'Possible patient name detected'
        }
    ];

    // Fields to skip scanning (non-patient data)
    const SKIP_KEYS = new Set([
        'password', 'token', 'csrf', 'email', 'username',
        'model', 'provider', 'slug', 'category', 'status',
        'modality', 'body_section', 'image_url', 'image_public_id',
        'image_type', 'filename', 'image_thumbnail_url'
    ]);

    // ======================== SCANNER ========================

    function scan(text) {
        if (!text || typeof text !== 'string' || text.length < 5) {
            return { hasPII: false, matches: [] };
        }

        const matches = [];
        for (const pattern of PII_PATTERNS) {
            // Reset lastIndex for global regexes
            pattern.regex.lastIndex = 0;
            let match;
            while ((match = pattern.regex.exec(text)) !== null) {
                matches.push({
                    type: pattern.type,
                    match: match[0],
                    index: match.index,
                    description: pattern.description
                });
            }
        }

        return { hasPII: matches.length > 0, matches: matches };
    }

    function redact(text, matches) {
        if (!matches || matches.length === 0) return text;

        // Sort by index descending so replacements don't shift positions
        const sorted = [...matches].sort((a, b) => b.index - a.index);
        let result = text;
        for (const m of sorted) {
            result = result.substring(0, m.index) + '[REDACTED]' + result.substring(m.index + m.match.length);
        }
        return result;
    }

    // ======================== DEEP SCAN JSON ========================

    function scanObject(obj) {
        const allMatches = [];

        function recurse(val, path) {
            if (typeof val === 'string') {
                // Skip known non-patient fields
                const lastKey = path.split('.').pop();
                if (SKIP_KEYS.has(lastKey)) return;

                const result = scan(val);
                if (result.hasPII) {
                    result.matches.forEach(m => {
                        m.field = path;
                        allMatches.push(m);
                    });
                }
            } else if (Array.isArray(val)) {
                val.forEach((item, i) => recurse(item, path + '[' + i + ']'));
            } else if (val && typeof val === 'object') {
                Object.keys(val).forEach(key => recurse(val[key], path ? path + '.' + key : key));
            }
        }

        recurse(obj, '');
        return allMatches;
    }

    function redactObject(obj, matches) {
        if (!matches || matches.length === 0) return obj;

        // Deep clone
        const clone = JSON.parse(JSON.stringify(obj));

        // Group matches by field path
        const byField = {};
        matches.forEach(m => {
            if (!byField[m.field]) byField[m.field] = [];
            byField[m.field].push(m);
        });

        // Apply redactions
        for (const [path, fieldMatches] of Object.entries(byField)) {
            const parts = path.replace(/\[(\d+)\]/g, '.$1').split('.');
            let target = clone;
            for (let i = 0; i < parts.length - 1; i++) {
                target = target[parts[i]];
                if (!target) break;
            }
            if (target) {
                const lastKey = parts[parts.length - 1];
                if (typeof target[lastKey] === 'string') {
                    target[lastKey] = redact(target[lastKey], fieldMatches);
                }
            }
        }

        return clone;
    }

    // ======================== WARNING UI ========================

    function getWarningHTML(matches) {
        // Deduplicate by type+match
        const seen = new Set();
        const unique = matches.filter(m => {
            const key = m.type + ':' + m.match;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        });

        const typeColors = {
            'NHS Number': '#dc3545',
            'MRN / Hospital ID': '#dc3545',
            'Date of Birth': '#e96304',
            'UK Postcode': '#6b46c1',
            'Phone Number': '#0d6efd',
            'Email Address': '#0d6efd',
            'Patient Name': '#dc3545'
        };

        return unique.map(m => {
            const color = typeColors[m.type] || '#6c757d';
            const masked = m.match.substring(0, 3) + '***';
            return '<div class="d-flex align-items-center mb-2">' +
                '<span class="badge me-2" style="background:' + color + '; font-size: 0.7rem;">' + m.type + '</span>' +
                '<code class="small">' + masked + '</code>' +
                '</div>';
        }).join('');
    }

    function showPIIModal(matches) {
        return new Promise(function(resolve) {
            // Remove existing modal if any
            const existing = document.getElementById('piiGuardModal');
            if (existing) existing.remove();

            const backdrop = document.createElement('div');
            backdrop.id = 'piiGuardBackdrop';
            backdrop.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:10000;';

            const modal = document.createElement('div');
            modal.id = 'piiGuardModal';
            modal.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);' +
                'background:#fff;border-radius:12px;padding:24px;max-width:460px;width:90%;z-index:10001;' +
                'box-shadow:0 8px 32px rgba(0,0,0,0.3);';

            modal.innerHTML =
                '<div class="text-center mb-3">' +
                    '<i class="fas fa-shield-alt" style="font-size:2.5rem;color:#dc3545;"></i>' +
                    '<h5 class="mt-2 mb-1" style="color:#dc3545;">Patient Data Detected</h5>' +
                    '<p class="text-muted small mb-0">The following patient-identifiable information was found in your input.</p>' +
                '</div>' +
                '<div class="p-3 rounded mb-3" style="background:#fff3f3;border:1px solid #f5c6cb;max-height:200px;overflow-y:auto;">' +
                    getWarningHTML(matches) +
                '</div>' +
                '<p class="small text-muted mb-3">' +
                    '<i class="fas fa-info-circle me-1"></i>' +
                    'Patient data must not be entered into this application. Choose an action below.' +
                '</p>' +
                '<div class="d-flex gap-2">' +
                    '<button id="piiRedactBtn" class="btn btn-warning flex-fill">' +
                        '<i class="fas fa-eraser me-1"></i>Remove &amp; Continue' +
                    '</button>' +
                    '<button id="piiCancelBtn" class="btn btn-outline-secondary flex-fill">' +
                        '<i class="fas fa-times me-1"></i>Cancel' +
                    '</button>' +
                '</div>';

            document.body.appendChild(backdrop);
            document.body.appendChild(modal);

            document.getElementById('piiRedactBtn').addEventListener('click', function() {
                backdrop.remove();
                modal.remove();
                resolve('redact');
            });

            document.getElementById('piiCancelBtn').addEventListener('click', function() {
                backdrop.remove();
                modal.remove();
                resolve('cancel');
            });

            backdrop.addEventListener('click', function() {
                backdrop.remove();
                modal.remove();
                resolve('cancel');
            });
        });
    }

    // ======================== FETCH INTERCEPTOR ========================

    function attachToFetch() {
        const originalFetch = window.fetch;

        window.fetch = async function(url, options) {
            // Only intercept POST/PUT with JSON body
            if (!options || !options.body) return originalFetch.call(this, url, options);
            if (!options.method || !['POST', 'PUT'].includes(options.method.toUpperCase())) {
                return originalFetch.call(this, url, options);
            }

            // Skip non-JSON content types
            const contentType = (options.headers && (options.headers['Content-Type'] || options.headers['content-type'])) || '';
            if (!contentType.includes('application/json')) return originalFetch.call(this, url, options);

            // Skip auth/admin/backup routes
            const urlStr = typeof url === 'string' ? url : url.toString();
            const skipPrefixes = ['/auth/', '/api/admin/', '/api/backup', '/login', '/register'];
            if (skipPrefixes.some(function(p) { return urlStr.includes(p); })) {
                return originalFetch.call(this, url, options);
            }

            // Parse and scan the JSON body
            let body;
            try {
                body = JSON.parse(options.body);
            } catch(e) {
                return originalFetch.call(this, url, options);
            }

            const matches = scanObject(body);
            if (matches.length === 0) {
                return originalFetch.call(this, url, options);
            }

            // PII detected — show modal
            const action = await showPIIModal(matches);

            if (action === 'cancel') {
                // Return a fake response to prevent the request
                return new Response(JSON.stringify({
                    error: 'Submission cancelled — patient data detected.',
                    pii_blocked: true
                }), { status: 422, headers: { 'Content-Type': 'application/json' } });
            }

            // Redact and continue
            const cleaned = redactObject(body, matches);
            options.body = JSON.stringify(cleaned);
            return originalFetch.call(this, url, options);
        };
    }

    // ======================== PUBLIC API ========================

    window.PIIGuard = {
        scan: scan,
        redact: redact,
        scanObject: scanObject,
        redactObject: redactObject,
        getWarningHTML: getWarningHTML,
        showPIIModal: showPIIModal,
        attachToFetch: attachToFetch,
        PII_PATTERNS: PII_PATTERNS
    };

})();
