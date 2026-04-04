/**
 * PII Guard — Global Patient Data Detection
 * Dual-layer protection: client-side (this file) + server-side (pii_guard.py)
 * Loaded globally via base.html to intercept all fetch POST/PUT requests.
 */
(function() {
    'use strict';

    // ======================== MEDICAL ALLOWLIST ========================
    // Known medical/radiology terms that should NOT trigger PII warnings.
    // Suppresses false positives from vertebral levels, TNM staging, MRI sequences, etc.

    const MEDICAL_ALLOWLIST = new Set([
        // Vertebral levels
        'C1','C2','C3','C4','C5','C6','C7',
        'T1','T2','T3','T4','T5','T6','T7','T8','T9','T10','T11','T12',
        'L1','L2','L3','L4','L5','S1','S2','S3','S4','S5',
        // Vertebral ranges (hyphenated)
        'C1-C2','C2-C3','C3-C4','C4-C5','C5-C6','C6-C7',
        'T1-T2','T2-T3','T3-T4','T4-T5','T5-T6','T6-T7','T7-T8','T8-T9','T9-T10','T10-T11','T11-T12','T12-L1',
        'L1-L2','L2-L3','L3-L4','L4-L5','L5-S1',
        // TNM staging
        'T0','T1A','T1B','T1C','T2A','T2B','T2C','T3A','T3B','T4A','T4B',
        'N0','N1','N1A','N1B','N2','N2A','N2B','N3','N3A','N3B',
        'M0','M1','M1A','M1B','M1C',
        'STAGE I','STAGE IA','STAGE IB','STAGE II','STAGE IIA','STAGE IIB','STAGE IIC',
        'STAGE III','STAGE IIIA','STAGE IIIB','STAGE IIIC','STAGE IV','STAGE IVA','STAGE IVB',
        // Common radiology / imaging terms
        'CT','MRI','MRA','MRV','PET','SPECT','DEXA','BMD',
        'FLAIR','DWI','ADC','SWI','GRE','STIR','FIESTA','CISS',
        'T1W','T2W','T1 WEIGHTED','T2 WEIGHTED','T1 W','T2 W',
        'DR','CR','US','XR',
        // Measurements & units used in radiology
        'HU','SUV','ADC VALUE','SUV MAX','SUVMAX',
        // Contrast phases
        'IV CONTRAST',
        // Grading
        'G1','G2','G3','G4','GX',
        // BIRADS / PIRADS / TIRADS / LIRADS
        'BI-RADS','BIRADS','PI-RADS','PIRADS','TI-RADS','TIRADS','LI-RADS','LIRADS',
        // Common anatomy abbreviations that look like IDs
        'SA NODE','AV NODE','SI JOINT','SI JOINTS',
    ]);

    // Imaging modality terms that should never be treated as part of a person's name.
    // Prevents false positives like "Pt CT Facial Bones" being flagged as a patient name.
    const IMAGING_MODALITY_TERMS = new Set([
        'CT','MRI','MRA','MRV','PET','SPECT','DEXA','BMD',
        'FLAIR','DWI','ADC','SWI','GRE','STIR','FIESTA','CISS',
        'XR','CXR','AXR','USS','HRCT','CECT','NCCT','MRE','MRCP',
    ]);

    function _isMedicalTerm(matchText) {
        if (!matchText) return false;
        var upper = matchText.trim().toUpperCase();
        if (MEDICAL_ALLOWLIST.has(upper)) return true;
        // Check hyphenated/slashed compound terms (e.g. "C3-C4", "L4/L5")
        var parts = upper.split(/[-\/]/);
        if (parts.length >= 2 && parts.every(function(p) { return MEDICAL_ALLOWLIST.has(p.trim()); })) {
            return true;
        }
        return false;
    }

    // ======================== PII PATTERNS ========================

    // Common English words that must NOT be treated as parts of a person's name.
    // Used as a per-word negative lookahead in name-detection patterns.
    var _NAME_STOP = "(?!(?:for|was|is|has|had|the|with|by|and|or|in|at|to|of|on|an|a"
        + "|this|that|no|who|will|may|should|could|would|not|been|being"
        + "|reviewed|presented|attended|referred|consulted|evaluated|diagnosed"
        + "|from|about|into|over|under|after|before|during|through)\\b)";

    const PII_PATTERNS = [
        {
            type: 'NHS Number',
            regex: /\bNHS\s*(?:no|number|#)?[:\s]+\d{3}[-\s]?\d{3}[-\s]?\d{4}\b/gi,
            description: 'NHS number detected'
        },
        {
            type: 'NHS Number',
            regex: /\bNHS\s*(?:no|number|#)?[:\s]+\d{6,10}\b/gi,
            description: 'NHS number detected (short format)'
        },
        {
            type: 'NHS Number',
            regex: /\b\d{3}[-\s]\d{3}[-\s]\d{4}\b/g,
            description: 'NHS number detected (format)'
        },
        {
            type: 'US SSN',
            regex: /\b\d{3}-\d{2}-\d{4}\b/g,
            description: 'US Social Security Number detected'
        },
        {
            type: 'MRN / Hospital ID',
            regex: /\b(?:MRN|UHID|hospital\s*(?:id|no|number|#)|hosp\s*id|patient\s*id)[:\s#]*\d{4,10}\b/gi,
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
            regex: /\b(?:phone|tel|mobile|cell|contact|ph)\s*[:=\-#]?\s*\+?[(\d][\d\s\-.()]{7,15}\d/gi,
            description: 'Phone number detected'
        },
        {
            type: 'Phone Number',
            regex: /\b(?:his|her|my|their|the)\s+(?:number|no|contact)\s+(?:is|was)\s*:?\s*\+?[\d][\d\s\-.()]{6,15}\d\b/gi,
            description: 'Phone number detected (context)'
        },
        {
            type: 'Phone Number',
            regex: /\bnumber\s+(?:is|was)\s*:?\s*\+?[\d][\d\s\-.()]{6,15}\d\b/gi,
            description: 'Phone number detected (keyword)'
        },
        {
            type: 'Phone Number',
            regex: /\+\d{1,3}[\s.-]?\d{4,5}[\s.-]?\d{4,6}\b/g,
            description: 'International phone number detected'
        },
        {
            type: 'Email Address',
            regex: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g,
            description: 'Email address detected'
        },
        {
            type: 'Patient Name',
            regex: /\b(?:patient\s*name|patient|pt\s*name|pt|name)\s*[:=\-]\s*(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?\s*[A-Za-z][A-Za-z'-]+(?:\s+[A-Za-z][A-Za-z'-]+){0,3}(?=\s*(?:[,;.\n|]|\bage\b|\bgender\b|\bsex\b|\bdob\b|\baddress\b|\bmrn\b|\bnhs\b|$))/gi,
            description: 'Possible patient name detected (with keyword + title)'
        },
        {
            type: 'Patient Name',
            regex: new RegExp(
                "\\b(?:Mr|Mrs|Ms|Miss|Dr|Prof)\\b\\.?\\s*"
                + _NAME_STOP + "[A-Za-z][a-zA-Z'\\-]+"
                + "(?:\\s+" + _NAME_STOP + "[A-Za-z][a-zA-Z'\\-]+){0,3}"
                + "(?=\\s*(?:[,;.\\n|/()]|\\d|\\bage\\b|\\bgender\\b|\\bsex\\b|\\bdob\\b|\\bpresented\\b|\\battended\\b|\\bwas\\b|\\bis\\b|\\bhas\\b|\\bfor\\b|\\bwith\\b|\\breviewed\\b|\\breferred\\b|$))",
                "g"
            ),
            description: 'Patient name with title detected'
        },
        {
            type: 'Patient Name',
            regex: /\b(?:patient\s*name|pt\s*name)\s*[:=\-]\s*[A-Za-z][A-Za-z'-]+(?:\s+[A-Za-z][A-Za-z'-]+){0,3}(?=\s*(?:[,;.\n|]|\bage\b|\bgender\b|\bsex\b|\bdob\b|\baddress\b|\bmrn\b|\bnhs\b|$))/gi,
            description: 'Possible patient name detected'
        },
        {
            type: 'Patient Name',
            regex: /\bname\s*[:=\-]\s*[A-Za-z][A-Za-z'-]+(?:\s+[A-Za-z][A-Za-z'-]+){1,3}(?=\s*(?:[,;.\n|]|\bage\b|\bgender\b|\bsex\b|\bdob\b|\baddress\b|\bmrn\b|\bnhs\b|\d|$))/gi,
            description: 'Possible patient name detected (name keyword)'
        },
        {
            type: 'Patient Name',
            regex: /\d{1,3}[-\s]?year[-\s]?old\b[^.\n]{0,30}?([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){1,3})(?=\s*(?:[,;.\n|]|\bpresented\b|\battended\b|\bwas\b|\bis\b|\bhas\b|\bwith\b|$))/g,
            description: 'Patient name after age context detected'
        },
        {
            type: 'Patient Name',
            regex: new RegExp(
                "\\b[Pp](?:atient|t)(?:\\s*[:=\\-]\\s*|\\s+)"
                + _NAME_STOP + "([A-Z][a-zA-Z'\\-]+"
                + "(?:\\s+" + _NAME_STOP + "[A-Z][a-zA-Z'\\-]+){0,3})"
                + "(?=\\s*(?:[,;.\\n|/()]|\\d|\\bpresented\\b|\\battended\\b|\\bwas\\b|\\bis\\b|\\bhas\\b|\\bwith\\b|\\bfor\\b|$))",
                "g"
            ),
            description: 'Patient name after keyword detected'
        },
        {
            type: 'Patient Name',
            regex: new RegExp(
                "\\b[Tt]his\\s+is\\s+"
                + _NAME_STOP + "[A-Z][a-zA-Z'\\-]{2,}"
                + "(?:\\s+" + _NAME_STOP + "[A-Z][a-zA-Z'\\-]+){1,3}"
                + "(?=\\s*,?\\s+(?:a\\s+|an\\s+)?\\d{1,3}[\\-\\s]?years?[\\-\\s]?old\\b)",
                "g"
            ),
            description: 'Patient name after introduction detected'
        },
        {
            type: 'Doctor / Clinician Name',
            regex: /\b(?:referred\s+by|reporting\s+(?:radiologist|doctor|consultant)|reported\s+by|consultant|registrar|SpR|SHO|GP)\b\s*[:=\-]?\s*(?:Dr\.?\s+)?[A-Z][a-zA-Z'-]+(?:\s+[A-Z]\.?[a-zA-Z'-]*){0,3}/gi,
            description: 'Referring/reporting clinician name detected'
        },
        {
            type: 'Doctor / Clinician Name',
            regex: /\bDr\.?\s+[A-Z][a-zA-Z'-]+(?:\s+[A-Z]\.?[a-zA-Z'-]*){1,3}\b/g,
            description: 'Doctor name detected'
        },
        {
            type: 'Possible Patient ID',
            regex: /^\d{7,10}$/gm,
            description: 'Bare number on own line — likely hospital number or patient ID'
        },
        {
            type: 'Patient Age',
            regex: /\b(?:age|aged)\s*[:=\-]\s*\d{1,3}\b/gi,
            description: 'Patient age detected'
        },
        {
            type: 'Patient Gender',
            regex: /\b(?:gender|sex)\s*[:=\-]\s*(?:male|female|m|f|other|non-binary)\b/gi,
            description: 'Patient gender detected'
        },
        {
            type: 'Patient Address',
            regex: /\b(?:address|addr|home)\s*[:=\-]\s*[A-Za-z0-9][A-Za-z0-9\s,.''-]{5,}/gi,
            description: 'Patient address detected'
        },
        {
            type: 'UK National Insurance Number',
            regex: /\b[A-Z]{2}\d{6}[A-D]\b/gi,
            description: 'UK National Insurance Number detected'
        },
        {
            type: 'IP Address',
            regex: /\b(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\b/g,
            description: 'IP address detected (HIPAA identifier)'
        },
        {
            type: 'Aadhaar Number',
            regex: /\b\d{4}\s?\d{4}\s?\d{4}\b/g,
            description: 'Indian Aadhaar number detected'
        },
        {
            type: 'PAN Card',
            regex: /\b[A-Z]{5}\d{4}[A-Z]\b/g,
            description: 'Indian PAN card number detected'
        }
    ];

    // Fields to skip scanning (non-patient data)
    const SKIP_KEYS = new Set([
        'password', 'token', 'csrf', 'username',
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

        // Filter out known medical/radiology terms (false positive suppression)
        var filtered = matches.filter(function(m) { return !_isMedicalTerm(m.match); });

        // Filter out Patient/Doctor Name matches containing imaging modality terms
        // e.g. "Pt CT Facial Bones" — "CT" is an imaging modality, not a person's name
        filtered = filtered.filter(function(m) {
            if (m.type === 'Patient Name' || m.type === 'Doctor / Clinician Name') {
                var words = m.match.split(/[\s:=\-]+/);
                for (var i = 0; i < words.length; i++) {
                    if (words[i] && IMAGING_MODALITY_TERMS.has(words[i].toUpperCase())) return false;
                }
            }
            return true;
        });

        return { hasPII: filtered.length > 0, matches: filtered };
    }

    function _dedupeMatches(matches) {
        var seen = new Set();
        var unique = [];
        for (var i = 0; i < matches.length; i++) {
            var key = matches[i].match;
            if (key && !seen.has(key)) {
                seen.add(key);
                unique.push(matches[i]);
            }
        }
        // Sort by match length descending — replace longer matches first
        unique.sort(function(a, b) { return b.match.length - a.match.length; });
        return unique;
    }

    function redact(text, matches) {
        if (!matches || matches.length === 0) return text;
        var unique = _dedupeMatches(matches);
        var result = text;
        for (var i = 0; i < unique.length; i++) {
            var matchText = unique[i].match;
            if (matchText && result.indexOf(matchText) !== -1) {
                result = result.split(matchText).join('[REDACTED]');
            }
        }
        return result;
    }

    function remove(text, matches) {
        if (!matches || matches.length === 0) return text;
        var unique = _dedupeMatches(matches);
        var result = text;
        for (var i = 0; i < unique.length; i++) {
            var matchText = unique[i].match;
            if (matchText && result.indexOf(matchText) !== -1) {
                result = result.split(matchText).join('');
            }
        }
        // Clean up leftover whitespace (double spaces, leading/trailing)
        return result.replace(/  +/g, ' ').trim();
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

    function _applyToObject(obj, matches, transformFn) {
        if (!matches || matches.length === 0) return obj;

        const clone = JSON.parse(JSON.stringify(obj));

        const byField = {};
        matches.forEach(m => {
            if (!byField[m.field]) byField[m.field] = [];
            byField[m.field].push(m);
        });

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
                    target[lastKey] = transformFn(target[lastKey], fieldMatches);
                }
            }
        }

        return clone;
    }

    function redactObject(obj, matches) {
        return _applyToObject(obj, matches, redact);
    }

    function removeObject(obj, matches) {
        return _applyToObject(obj, matches, remove);
    }

    // ======================== WARNING UI ========================

    const TYPE_COLORS = {
        'NHS Number': '#dc3545',
        'US SSN': '#dc3545',
        'MRN / Hospital ID': '#dc3545',
        'Date of Birth': '#e96304',
        'UK Postcode': '#6b46c1',
        'Phone Number': '#0d6efd',
        'Email Address': '#0d6efd',
        'Patient Name': '#dc3545',
        'Doctor / Clinician Name': '#e96304',
        'Patient Age': '#e96304',
        'Patient Gender': '#e96304',
        'Patient Address': '#6b46c1',
        'UK National Insurance Number': '#dc3545',
        'IP Address': '#6b46c1',
        'Aadhaar Number': '#dc3545',
        'PAN Card': '#dc3545',
        'Possible Patient ID': '#dc3545'
    };

    function _escapeHtml(str) {
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function getWarningHTML(matches) {
        const seen = new Set();
        const unique = matches.filter(m => {
            const key = m.type + ':' + m.match;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        });

        return unique.map(m => {
            const color = TYPE_COLORS[m.type] || '#6c757d';
            const masked = m.match.substring(0, 3) + '***';
            return '<div class="d-flex align-items-center mb-2">' +
                '<span class="badge me-2" style="background:' + color + '; font-size: 0.7rem;">' + m.type + '</span>' +
                '<code class="small">' + masked + '</code>' +
                '</div>';
        }).join('');
    }

    /**
     * Build a preview of the source text with all PII highlighted.
     * Extracts string values from the JSON body object and renders them
     * with detected PII wrapped in highlighted spans.
     */
    function getHighlightedPreview(body, matches) {
        if (!matches || matches.length === 0) return '';

        // Group matches by field
        const byField = {};
        matches.forEach(m => {
            if (!byField[m.field]) byField[m.field] = [];
            byField[m.field].push(m);
        });

        var html = '';
        for (const [field, fieldMatches] of Object.entries(byField)) {
            // Resolve field value from body
            const parts = field.replace(/\[(\d+)\]/g, '.$1').split('.');
            let val = body;
            for (let i = 0; i < parts.length; i++) {
                if (!val) break;
                val = val[parts[i]];
            }
            if (typeof val !== 'string' || !val) continue;

            // Deduplicate matches for this field
            const seen = new Set();
            const uniqueField = fieldMatches.filter(m => {
                if (seen.has(m.match)) return false;
                seen.add(m.match);
                return true;
            });
            // Sort by length descending for replacement
            uniqueField.sort((a, b) => b.match.length - a.match.length);

            // Build highlighted text: replace PII with highlighted spans
            // Use placeholders to avoid double-replacement
            var processed = val;
            var placeholders = [];
            for (var i = 0; i < uniqueField.length; i++) {
                var m = uniqueField[i];
                var color = TYPE_COLORS[m.type] || '#6c757d';
                var placeholder = '\x00PII' + i + '\x00';
                var replacement = '<span class="pii-highlight" style="background:' + color + '20; border: 1.5px solid ' + color + '; border-radius: 3px; padding: 0 3px;">' +
                    _escapeHtml(m.match) +
                    '<sup class="pii-highlight-label" style="color:' + color + '; font-size:0.6rem; font-weight:700; margin-left:2px;">' + m.type + '</sup>' +
                    '</span>';
                placeholders.push({ placeholder: placeholder, replacement: replacement });
                processed = processed.split(m.match).join(placeholder);
            }

            // Escape HTML in non-PII text, then restore placeholders
            processed = _escapeHtml(processed);
            for (var i = 0; i < placeholders.length; i++) {
                processed = processed.split(_escapeHtml(placeholders[i].placeholder)).join(placeholders[i].replacement);
            }

            // Truncate long text — show first ~500 chars
            var lines = processed.split('\n');
            var truncated = false;
            var output = '';
            var charCount = 0;
            for (var j = 0; j < lines.length; j++) {
                charCount += lines[j].length;
                if (charCount > 500 && j > 0) {
                    truncated = true;
                    break;
                }
                output += (j > 0 ? '<br>' : '') + lines[j];
            }
            if (truncated) output += '<br><span class="text-muted">...</span>';

            html += '<div class="pii-preview-block">' +
                '<div class="pii-preview-text">' + output + '</div>' +
                '</div>';
        }

        return html;
    }

    function showPIIModal(matches, body) {
        return new Promise(function(resolve) {
            // Remove existing modal if any
            var existing = document.getElementById('piiGuardModal');
            if (existing) {
                var oldInstance = bootstrap.Modal.getInstance(existing);
                if (oldInstance) oldInstance.dispose();
                existing.remove();
            }

            // Build preview with highlighted PII if body is available
            var previewHTML = '';
            if (body) {
                previewHTML = getHighlightedPreview(body, matches);
            }

            // Build Bootstrap modal following app design (scoped via .app-content-modal.pii-guard-modal)
            var wrapper = document.createElement('div');
            wrapper.innerHTML =
                '<div class="modal fade app-content-modal pii-guard-modal" id="piiGuardModal" tabindex="-1" data-bs-backdrop="static">' +
                  '<div class="modal-dialog modal-dialog-centered' + (previewHTML ? ' modal-lg' : '') + '">' +
                    '<div class="modal-content">' +
                      '<div class="modal-header">' +
                        '<h5 class="modal-title">' +
                          '<i class="fas fa-shield-alt"></i> Patient Data Detected' +
                        '</h5>' +
                        '<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>' +
                      '</div>' +
                      '<div class="modal-body">' +
                        '<p class="text-muted small mb-2">' +
                          'The following patient-identifiable information was found in your input. Highlighted items will be affected by your choice.' +
                        '</p>' +
                        (previewHTML
                          ? '<div class="pii-preview-container mb-3">' + previewHTML + '</div>'
                          : '<div class="pii-matches-list mb-3">' + getWarningHTML(matches) + '</div>'
                        ) +
                        '<div class="d-flex align-items-start gap-2 small text-muted mb-3" style="line-height:1.4;">' +
                          '<i class="fas fa-info-circle mt-1" style="flex-shrink:0;"></i>' +
                          '<span><strong>Redact</strong> replaces highlighted data with [REDACTED]. <strong>Remove</strong> deletes it entirely.</span>' +
                        '</div>' +
                        '<div class="pii-override-section">' +
                          '<div class="form-check mb-1">' +
                            '<input class="form-check-input" type="checkbox" id="piiOverrideCheck">' +
                            '<label class="form-check-label small" for="piiOverrideCheck">' +
                              'I confirm this does not contain patient-identifiable information' +
                            '</label>' +
                          '</div>' +
                          '<div class="d-flex align-items-center gap-1 mb-0" style="margin-left: 1.5rem;">' +
                            '<i class="fas fa-exclamation-triangle" style="color: #e96304; font-size: 0.65rem;"></i>' +
                            '<span class="text-muted" style="font-size: 0.7rem;">Overrides are logged in the system audit trail</span>' +
                          '</div>' +
                        '</div>' +
                      '</div>' +
                      '<div class="modal-footer">' +
                        '<button type="button" class="btn btn-pii-cancel" id="piiCancelBtn">' +
                          '<i class="fas fa-times me-1"></i>Cancel' +
                        '</button>' +
                        '<button type="button" class="btn btn-pii-override" id="piiOverrideBtn" disabled title="Confirm checkbox above to enable">' +
                          '<i class="fas fa-forward me-1"></i>Send Anyway' +
                        '</button>' +
                        '<button type="button" class="btn btn-pii-redact" id="piiRedactBtn" title="Replace detected data with [REDACTED] and continue">' +
                          '<i class="fas fa-marker me-1"></i>Redact' +
                        '</button>' +
                        '<button type="button" class="btn btn-pii-remove" id="piiRemoveBtn" title="Delete detected data entirely and continue">' +
                          '<i class="fas fa-eraser me-1"></i>Remove' +
                        '</button>' +
                      '</div>' +
                    '</div>' +
                  '</div>' +
                '</div>';

            var modalEl = wrapper.firstChild;
            document.body.appendChild(modalEl);

            var bsModal = new bootstrap.Modal(modalEl);
            var resolved = false;

            // Checkbox enables/disables override button
            document.getElementById('piiOverrideCheck').addEventListener('change', function() {
                document.getElementById('piiOverrideBtn').disabled = !this.checked;
            });

            document.getElementById('piiOverrideBtn').addEventListener('click', function() {
                resolved = true;
                bsModal.hide();
                resolve('override');
            });

            document.getElementById('piiRedactBtn').addEventListener('click', function() {
                resolved = true;
                bsModal.hide();
                resolve('redact');
            });

            document.getElementById('piiRemoveBtn').addEventListener('click', function() {
                resolved = true;
                bsModal.hide();
                resolve('remove');
            });

            document.getElementById('piiCancelBtn').addEventListener('click', function() {
                resolved = true;
                bsModal.hide();
                resolve('cancel');
            });

            // Clean up DOM after hidden; resolve as cancel if X button or backdrop clicked
            modalEl.addEventListener('hidden.bs.modal', function() {
                bsModal.dispose();
                modalEl.remove();
                if (!resolved) resolve('cancel');
            });

            bsModal.show();
        });
    }

    // ======================== DISMISS TRACKING ========================

    // Per-session dismissed items: stores "type:matchText" keys
    var _dismissedKeys = new Set();

    function _dismissKey(match) {
        return match.type + ':' + match.match;
    }

    function dismiss(match) {
        _dismissedKeys.add(_dismissKey(match));
    }

    function dismissType(type, matches) {
        for (var i = 0; i < matches.length; i++) {
            if (matches[i].type === type) {
                _dismissedKeys.add(_dismissKey(matches[i]));
            }
        }
    }

    function isDismissed(match) {
        return _dismissedKeys.has(_dismissKey(match));
    }

    function filterDismissed(matches) {
        return matches.filter(function(m) { return !_dismissedKeys.has(_dismissKey(m)); });
    }

    function clearDismissals() {
        _dismissedKeys.clear();
    }

    // ======================== ACTIONABLE WARNING UI ========================

    function getActionableWarningHTML(matches) {
        // Dedupe matches
        var seen = new Set();
        var unique = matches.filter(function(m) {
            var key = m.type + ':' + m.match;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        });

        if (unique.length === 0) return '';

        // Group by type
        var groups = {};
        var groupOrder = [];
        for (var i = 0; i < unique.length; i++) {
            var m = unique[i];
            if (!groups[m.type]) {
                groups[m.type] = [];
                groupOrder.push(m.type);
            }
            groups[m.type].push({ match: m, originalIndex: i });
        }

        // Build HTML
        var html = '';

        // Bulk actions header
        html += '<div class="d-flex align-items-center gap-2 mb-2">';
        html += '<button class="btn btn-sm py-0 px-2" style="font-size:0.72rem;background:#dc3545;color:#fff;border:none;border-radius:3px;" onclick="piiRedactAll()" title="Replace all detected items with [REDACTED]"><i class="fas fa-marker me-1"></i>Redact All</button>';
        html += '<button class="btn btn-sm py-0 px-2" style="font-size:0.72rem;background:#e96304;color:#fff;border:none;border-radius:3px;" onclick="piiRemoveAll()" title="Delete all detected items from text"><i class="fas fa-eraser me-1"></i>Remove All</button>';
        html += '<span class="ms-auto text-muted" style="font-size:0.7rem;">' + unique.length + ' item' + (unique.length !== 1 ? 's' : '') + ' detected</span>';
        html += '</div>';

        // Per-type groups
        for (var g = 0; g < groupOrder.length; g++) {
            var type = groupOrder[g];
            var items = groups[type];
            var color = TYPE_COLORS[type] || '#6c757d';

            html += '<div class="mb-2 pb-2" style="border-bottom:1px solid #ffe69c;">';

            // Type header with batch dismiss
            html += '<div class="d-flex align-items-center gap-2 mb-1">';
            html += '<span class="badge" style="background:' + color + ';font-size:0.68rem;">' + _escapeHtml(type) + '</span>';
            html += '<span class="text-muted" style="font-size:0.7rem;">(' + items.length + ')</span>';
            if (items.length >= 2) {
                html += '<button class="btn btn-sm py-0 px-2 ms-auto" style="font-size:0.65rem;background:#f8f9fa;color:#856404;border:1px solid #ffe69c;border-radius:3px;" onclick="piiDismissType(\'' + _escapeHtml(type).replace(/'/g, "\\'") + '\')" title="Dismiss all ' + _escapeHtml(type) + ' — dismissals are audited">Dismiss all ' + _escapeHtml(type) + '</button>';
            }
            html += '</div>';

            // Individual matches
            for (var j = 0; j < items.length; j++) {
                var item = items[j];
                var masked = item.match.match.length > 3 ? item.match.match.substring(0, 3) + '***' : '***';
                var idx = item.originalIndex;

                html += '<div class="d-flex align-items-center gap-1 mb-1 pii-match-row" data-pii-index="' + idx + '" style="padding-left:0.5rem;">';
                html += '<code class="small" style="color:' + color + ';">' + _escapeHtml(masked) + '</code>';
                html += '<div class="ms-auto d-flex gap-1">';
                html += '<button class="btn btn-sm py-0 px-1" style="font-size:0.65rem;background:#dc354520;color:#dc3545;border:1px solid #dc354540;border-radius:3px;" onclick="piiAction(\'redact\',' + idx + ')" title="Replace with [REDACTED]">Redact</button>';
                html += '<button class="btn btn-sm py-0 px-1" style="font-size:0.65rem;background:#e9630420;color:#e96304;border:1px solid #e9630440;border-radius:3px;" onclick="piiAction(\'remove\',' + idx + ')" title="Delete from text">Remove</button>';
                html += '<button class="btn btn-sm py-0 px-1" style="font-size:0.65rem;background:#ffc10720;color:#856404;border:1px solid #ffc10740;border-radius:3px;" onclick="piiAction(\'dismiss\',' + idx + ')" title="Dismiss — dismissals are audited">Dismiss <small>\u2715</small></button>';
                html += '</div>';
                html += '</div>';
            }

            html += '</div>';
        }

        return html;
    }

    // ======================== FETCH INTERCEPTOR ========================

    // Decision cache: prevents re-prompting when the same URL is re-submitted
    // after redact/remove/override within a short window.
    var _piiDecisionCache = {};
    var _PII_CACHE_TTL = 120000; // 2 minutes

    function _getCachedDecision(urlStr) {
        var entry = _piiDecisionCache[urlStr];
        if (entry && (Date.now() - entry.ts) < _PII_CACHE_TTL) return entry.action;
        delete _piiDecisionCache[urlStr];
        return null;
    }

    function _cacheDecision(urlStr, action) {
        _piiDecisionCache[urlStr] = { action: action, ts: Date.now() };
    }

    function _applyDecision(action, body, matches, url, options, originalFetch, context, urlStr) {
        if (action === 'override') {
            // Add header so server-side PII middleware allows it through
            if (!options.headers) options.headers = {};
            if (options.headers instanceof Headers) {
                options.headers.set('X-PII-Override', '1');
            } else {
                options.headers['X-PII-Override'] = '1';
            }
            return originalFetch.call(context, url, options);
        }
        // Redact or Remove
        var cleaned = action === 'remove'
            ? removeObject(body, matches)
            : redactObject(body, matches);
        options.body = JSON.stringify(cleaned);
        return originalFetch.call(context, url, options);
    }

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

            // Skip auth/admin/backup routes and Smart Reporter AI routes
            // (Smart Reporter has its own checkEditorPII pre-check that cleans the textarea)
            const urlStr = typeof url === 'string' ? url : url.toString();
            // Smart Reporter has its own PII checking (livePIIScan + checkEditorPII)
            // so skip all its routes in the global interceptor
            const skipPrefixes = ['/auth/', '/api/admin/', '/api/backup', '/login', '/register',
                '/api/pii-override-log',
                '/radiology-protocols/admin/', '/incidental-findings/admin/', '/admin/reporting-algorithms/',
                '/api/smart-reporter/'];
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

            // Check if user already made a decision for this URL recently
            var cachedAction = _getCachedDecision(urlStr);
            if (cachedAction) {
                return _applyDecision(cachedAction, body, matches, url, options, originalFetch, this, urlStr);
            }

            // PII detected — show modal with highlighted preview
            const action = await showPIIModal(matches, body);

            if (action === 'cancel') {
                return new Response(JSON.stringify({
                    error: 'Submission cancelled — patient data detected.',
                    pii_blocked: true
                }), { status: 422, headers: { 'Content-Type': 'application/json' } });
            }

            // Cache the decision so re-submits don't re-prompt
            _cacheDecision(urlStr, action);

            if (action === 'override') {
                // Log the override to audit trail (fire-and-forget)
                var flaggedTypes = [];
                var seen = {};
                matches.forEach(function(m) {
                    if (!seen[m.type]) { seen[m.type] = true; flaggedTypes.push(m.type); }
                });
                originalFetch.call(this, '/api/pii-override-log', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({
                        flagged_types: flaggedTypes,
                        flagged_count: matches.length,
                        target_url: urlStr
                    })
                }).catch(function() {});
            }

            return _applyDecision(action, body, matches, url, options, originalFetch, this, urlStr);
        };
    }

    // ======================== PUBLIC API ========================

    window.PIIGuard = {
        scan: scan,
        redact: redact,
        remove: remove,
        scanObject: scanObject,
        redactObject: redactObject,
        removeObject: removeObject,
        getWarningHTML: getWarningHTML,
        getActionableWarningHTML: getActionableWarningHTML,
        showPIIModal: showPIIModal,
        attachToFetch: attachToFetch,
        dismiss: dismiss,
        dismissType: dismissType,
        isDismissed: isDismissed,
        filterDismissed: filterDismissed,
        clearDismissals: clearDismissals,
        PII_PATTERNS: PII_PATTERNS,
        MEDICAL_ALLOWLIST: MEDICAL_ALLOWLIST,
        IMAGING_MODALITY_TERMS: IMAGING_MODALITY_TERMS,
        isMedicalTerm: _isMedicalTerm,
        TYPE_COLORS: TYPE_COLORS
    };

})();
