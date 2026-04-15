/**
 * JSON Content Renderer — Universal client-side renderer for AI-generated structured JSON content.
 *
 * Usage:
 *   JsonContentRenderer.render(jsonData)           → returns HTML string
 *   JsonContentRenderer.renderInto(el, jsonData)   → renders into DOM element
 *   JsonContentRenderer.emphCaps(text)             → style ALL CAPS phrases in escaped text
 *   JsonContentRenderer.isJson(rawString)          → true if string is JSON discussion
 *
 * Handles: flexible sections, staging/classification tables, step-by-step cards,
 * key findings, differentials, key image, and any custom section type.
 *
 * ALL CAPS styling:
 *   - Safety words (NEVER, DO NOT, ALWAYS...) → bold red underline
 *   - STEP N → red bold
 *   - Multi-word ALL CAPS phrases → grey pill (medical abbreviations excluded)
 */
(function() {
    'use strict';

    // ── Helpers ──

    function esc(s) {
        var d = document.createElement('div');
        d.textContent = s || '';
        return d.innerHTML;
    }

    // ── ALL CAPS styling ──

    var _safetyWords = /\b(NEVER|ALWAYS|DO NOT|MUST NOT|CRITICAL|WARNING|CAUTION|IMPORTANT|MANDATORY|CONTRAINDICATED)\b/g;
    var _stepNum = /\b(STEP \d+)\b/g;
    var _capsPhrase = /(?:\()?[A-Z][A-Z0-9]{2,}(?:[\s\-]+[A-Z][A-Z0-9]{1,}){1,}(?:\))?(?:\s*[:—–])?/g;

    // Comprehensive medical abbreviation exclusion (~250 terms)
    var _medTerms = /^(CT|MRI|MRA|MRV|CTA|CTV|PET|PET-CT|SPECT|USS|DSA|DWI|ADC|FLAIR|STIR|GRE|SWI|EPI|TOF|CEUS|HRCT|CTPA|NCCT|CXR|AXR|OPG|HSG|IVU|IVP|MRCP|ERCP|PTC|DEXA|BMD|FRCR|RCR|ACR|ESR|BSR|NICE|WHO|AJCC|TNM|BIRADS|BI-RADS|LI-RADS|LR-\w+|TI-RADS|PI-RADS|O-RADS|NI-RADS|LUNG-RADS|CAD-RADS|HCC|CCA|RCC|SCC|TCC|NHL|AML|ALL|CML|CLL|GBM|DCIS|LCIS|IPMN|MCN|HCA|FNH|NET|GIST|EHE|HHT|NF1|NF2|VHL|TSC|MEN|FAP|HNPCC|AIDS|HIV|HBV|HCV|HPV|EBV|CMV|HSV|TB|COPD|IPF|UIP|NSIP|COP|DAD|ARDS|CHF|CCF|DVT|PE|AAA|ASD|VSD|PDA|PFO|AVM|AVF|DAVF|SAH|SDH|EDH|ICH|IVH|TIA|CVA|NAI|GCS|FAST|WBCT|RTA|RSI|CPR|ALS|BLS|ABC|ATLS|GFR|eGFR|BUN|CRP|LDH|AFP|CEA|PSA|CA125|HCG|TSH|PTH|ACTH|ADH|FSH|ANCA|ANA|IgG|IgA|IgM|IgE|CSF|INR|PTT|APTT|FBC|WBC|RBC|Hb|HbA1c|ABG|ECG|EEG|EMG|NCS|PFT|FEV1|FVC|TLCO|BMI|BSA|IV|IM|SC|PO|PR|IO|ITU|ICU|HDU|NICU|PICU|MDT|MDM|BCLC|OKUDA|CLIP|MELD|CTP|TACE|SIRT|RFA|MWA|HIFU|SRS|SBRT|IMRT|VMAT|IGRT|EBRT|HDR|LDR|TURBT|TURP|PCNL|ESWL|EUS|HIDA|MAG3|DMSA|DTPA|GI|GU|MSK|ENT|CNS|PNS|ANS|IVC|SVC|SMV|IMV|PV|HV|CBD|CHD|CHA|SMA|IMA|ACA|MCA|PCA|PICA|AICA|SCA|ICA|ECA|CCA|LSA|RSA|PA|RV|LV|RA|LA|AO|AA|DA|MPA|RPA|LPA|RVOT|LVOT|SAM|MVP|AVR|MVR|PCI|CABG|ECMO|IABP|VAD|LVAD|PICC|CVC|WLE|SLN|ALND|SLNB|TAH|BSO|LLETZ|LEEP|IVF|ICSI|IUI|LSCS|VBAC|APH|PPH|IUGR|SGA|LGA|NRFS|ARM|MCUG|VCUG|RUG|PPR)$/i;

    function emphCaps(s) {
        var out = esc(s);
        out = out.replace(_safetyWords,
            '<strong style="font-weight:700;text-decoration:underline;text-decoration-color:#e74c3c;text-underline-offset:2px;">$1</strong>');
        out = out.replace(_stepNum,
            '<strong style="color:#e74c3c;font-weight:700;">$1</strong>');
        out = out.replace(_capsPhrase, function(match) {
            var stripped = match.replace(/[^A-Z]/g, '');
            if (stripped.length < 5) return match;
            var trimmed = match.replace(/[\s:—–\(\)]/g, ' ').trim();
            var words = trimmed.split(/\s+/);
            if (words.length <= 2 && words.every(function(w) { return _medTerms.test(w); })) return match;
            return '<span style="background:#f0f1f3;padding:1px 6px;border-radius:3px;font-weight:600;font-size:0.9em;">' + match + '</span>';
        });
        return out;
    }

    // ── CSS class map ──

    var cssMap = {
        key_findings: 'key-finding', dangerous_anatomy: 'clinical-note',
        differentials: 'differential-dx', pitfalls: 'pitfall',
        teaching_points: 'teaching-pearl', staging: 'staging-info',
        classification: 'staging-info', imaging_approach: 'clinical-note',
        complications: 'pitfall', management_impact: 'key-finding',
        anatomy: 'clinical-note', key_image: 'image-finding',
        custom: 'teaching-pearl',
    };

    // ── Staging / Classification table ──

    function renderStagingTable(title, staging, cls) {
        var system = esc(staging.system || '');
        var heading = system ? title + ': ' + system : title;
        var stages = staging.stages || staging.grades || staging.categories || [];
        if (!stages.length) {
            if (staging.description) return '<div class="' + cls + '" data-field="staging"><strong>' + esc(heading) + '</strong><p>' + esc(staging.description) + '</p></div>';
            return '';
        }
        // Auto-detect label key
        var labelKeys = ['stage', 'grade', 'category', 'name', 'class', 'type', 'level'];
        var sample = stages[0] || {};
        var labelKey = null;
        for (var i = 0; i < labelKeys.length; i++) { if (sample[labelKeys[i]] !== undefined) { labelKey = labelKeys[i]; break; } }
        var valKeys = [];
        stages.forEach(function(s) {
            if (typeof s !== 'object') return;
            Object.keys(s).forEach(function(k) { if (k !== labelKey && valKeys.indexOf(k) === -1) valKeys.push(k); });
        });
        var header = '<th>' + esc((labelKey || 'Item').replace(/_/g, ' ')) + '</th>';
        valKeys.forEach(function(vk) { header += '<th>' + esc(vk.replace(/_/g, ' ')) + '</th>'; });
        var rows = '';
        stages.forEach(function(s) {
            if (typeof s !== 'object') return;
            var label = esc(labelKey ? (s[labelKey] || '') : '');
            rows += '<tr><td><strong>' + label + '</strong></td>';
            valKeys.forEach(function(vk) { rows += '<td>' + esc(String(s[vk] || '')) + '</td>'; });
            rows += '</tr>';
        });
        return '<div class="' + cls + '" data-field="staging"><strong>' + esc(heading) + '</strong>' +
            '<table class="table table-sm table-bordered"><thead><tr>' + header + '</tr></thead><tbody>' + rows + '</tbody></table></div>';
    }

    // ── Main renderer ──

    function render(disc) {
        var parts = [];

        parts.push('<div data-ai-generated="true" class="ai-generated-wrapper">');
        parts.push('<h4>Discussion</h4>');

        // Diagnosis summary
        if (disc.diagnosis_summary) {
            parts.push('<div class="diagnosis-box"><strong>Diagnosis Summary</strong><p>' + esc(disc.diagnosis_summary) + '</p></div>');
        }

        // Sections array
        var sections = disc.sections || [];
        sections.forEach(function(sec, secIdx) {
            var stype = sec.type || 'custom';
            var title = esc(sec.title || stype.replace(/_/g, ' '));
            var content = sec.content;
            var cls = cssMap[stype] || 'teaching-pearl';
            if (!content) return;

            // Staging / classification table
            if ((stype === 'staging' || stype === 'classification') && typeof content === 'object' && !Array.isArray(content)) {
                parts.push(renderStagingTable(title, content, cls));
                return;
            }

            // Key image
            if (stype === 'key_image' && typeof content === 'object' && !Array.isArray(content)) {
                var mod = esc(content.modality || '');
                var app = esc(content.appearance || '');
                var search = content.search_term || '';
                parts.push('<div class="' + cls + '" data-field="' + stype + '" data-section-title="' + esc(sec.title) + '"><strong>' + title + '</strong>' +
                    '<p>On <span class="anatomy-label">' + mod + '</span>, look for ' + app + '.' + (search ? ' [' + esc(search) + ']' : '') + '</p></div>');
                return;
            }

            // Key findings
            if (stype === 'key_findings' && Array.isArray(content)) {
                var items = content.map(function(f) {
                    if (typeof f === 'object') {
                        var name = esc(f.finding || '');
                        var desc = esc(f.description || '');
                        var meas = f.measurement ? ' <span class="measurement">' + esc(f.measurement) + '</span>' : '';
                        return '<li data-claim-anchor="' + esc(f.finding) + '"><span class="anatomy-label">' + name + '</span> &mdash; ' + desc + meas + '</li>';
                    }
                    return '<li>' + emphCaps(f) + '</li>';
                }).join('');
                if (items) parts.push('<div class="' + cls + '" data-field="' + stype + '" data-section-title="' + esc(sec.title) + '"><strong>' + title + '</strong><ul>' + items + '</ul></div>');
                return;
            }

            // Differentials
            if (stype === 'differentials' && Array.isArray(content)) {
                var dItems = content.map(function(d) {
                    if (typeof d === 'object') {
                        return '<li data-claim-anchor="' + esc(d.name) + '"><strong>' + esc(d.name || '') + '</strong> &mdash; ' + esc(d.distinguishing_feature || '') + '</li>';
                    }
                    return '<li>' + emphCaps(d) + '</li>';
                }).join('');
                if (dItems) parts.push('<div class="' + cls + '" data-field="' + stype + '" data-section-title="' + esc(sec.title) + '"><strong>' + title + '</strong><ul>' + dItems + '</ul></div>');
                return;
            }

            // Imaging approach / step-by-step → numbered step cards
            if (stype === 'imaging_approach' && Array.isArray(content)) {
                var steps = content.map(function(item, idx) {
                    var text = typeof item === 'string' ? item : JSON.stringify(item);
                    var dashIdx = text.indexOf('\u2014'); // —
                    var colonIdx = text.indexOf(':');
                    var splitIdx = dashIdx > 0 ? dashIdx : (colonIdx > 0 && colonIdx < 60 ? colonIdx : -1);
                    var label, desc;
                    if (splitIdx > 0) {
                        label = text.substring(0, splitIdx).trim();
                        desc = text.substring(splitIdx + 1).trim();
                    } else { label = ''; desc = text; }
                    var stepNum = idx + 1;
                    return '<div style="display:flex;gap:12px;align-items:flex-start;margin:8px 0;padding:10px 14px;background:#f8f9fb;border-radius:6px;border-left:3px solid var(--brand-neutral,#5E899E);">' +
                        '<div style="min-width:32px;height:32px;border-radius:50%;background:var(--brand-neutral,#5E899E);color:white;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:0.85em;flex-shrink:0;">' + stepNum + '</div>' +
                        '<div style="flex:1;"><strong style="color:var(--brand-neutral,#5E899E);">' + (label ? emphCaps(label) : 'Step ' + stepNum) + '</strong>' +
                        (desc ? '<br><span style="color:#4a5568;">' + emphCaps(desc) + '</span>' : '') + '</div></div>';
                }).join('');
                if (steps) parts.push('<div class="' + cls + '" data-field="' + stype + '" data-section-title="' + esc(sec.title) + '"><strong>' + title + '</strong>' + steps + '</div>');
                return;
            }

            // Management / recommendation sections → render as table if items have : or = splitting
            if ((stype === 'management_impact' || stype === 'custom') && Array.isArray(content) && content.length >= 3) {
                var strItems = content.filter(function(i) { return typeof i === 'string'; });
                // Detect decision-matrix pattern: most items contain = or : with a clear split
                var eqCount = strItems.filter(function(s) { return /\s=\s/.test(s); }).length;
                var colonCount = strItems.filter(function(s) { var ci = s.indexOf(':'); return ci > 2 && ci < s.length - 5; }).length;

                if (eqCount > strItems.length * 0.4) {
                    // Decision matrix: split on = → Condition | Result table
                    var mRows = strItems.map(function(s) {
                        var parts2 = s.split(/\s=\s/);
                        if (parts2.length >= 2) {
                            return '<tr><td>' + emphCaps(parts2[0].trim()) + '</td><td><strong>' + emphCaps(parts2.slice(1).join(' = ').trim()) + '</strong></td></tr>';
                        }
                        return '<tr><td colspan="2">' + emphCaps(s) + '</td></tr>';
                    }).join('');
                    parts.push('<div class="' + cls + '" data-field="' + stype + '" data-section-title="' + esc(sec.title) + '"><strong>' + title + '</strong>' +
                        '<table class="table table-sm table-bordered mt-2"><thead><tr><th>Condition</th><th>Category</th></tr></thead><tbody>' + mRows + '</tbody></table></div>');
                    return;
                }

                if (colonCount > strItems.length * 0.4) {
                    // Recommendation table: split on first : → Category | Recommendation
                    var rRows = strItems.map(function(s) {
                        var ci = s.indexOf(':');
                        if (ci > 2 && ci < s.length - 5) {
                            return '<tr><td><strong>' + emphCaps(s.substring(0, ci).trim()) + '</strong></td><td>' + emphCaps(s.substring(ci + 1).trim()) + '</td></tr>';
                        }
                        return '<tr><td colspan="2">' + emphCaps(s) + '</td></tr>';
                    }).join('');
                    parts.push('<div class="' + cls + '" data-field="' + stype + '" data-section-title="' + esc(sec.title) + '"><strong>' + title + '</strong>' +
                        '<table class="table table-sm table-bordered mt-2"><tbody>' + rRows + '</tbody></table></div>');
                    return;
                }
            }

            // Generic array
            if (Array.isArray(content)) {
                var gItems = content.map(function(item) {
                    if (typeof item === 'string') return '<li>' + emphCaps(item) + '</li>';
                    if (typeof item === 'object') {
                        var vals = Object.entries(item).map(function(kv) {
                            return kv[1] && String(kv[1]) !== 'null' ? '<strong>' + esc(kv[0]) + ':</strong> ' + emphCaps(String(kv[1])) : '';
                        }).filter(Boolean).join(' &mdash; ');
                        return vals ? '<li>' + vals + '</li>' : '';
                    }
                    return '';
                }).filter(Boolean).join('');
                if (gItems) parts.push('<div class="' + cls + '" data-field="' + stype + '" data-section-title="' + esc(sec.title) + '"><strong>' + title + '</strong><ul>' + gItems + '</ul></div>');
                return;
            }

            // String content
            if (typeof content === 'string') {
                parts.push('<div class="' + cls + '" data-field="' + stype + '" data-section-title="' + esc(sec.title) + '"><strong>' + title + '</strong><p>' + emphCaps(content) + '</p></div>');
            }
        });

        // Appended images
        if (disc._appended_images_html) {
            parts.push(disc._appended_images_html);
        }

        // Attribution footer
        var meta = disc._meta || {};
        var ts = meta.generated_at ? new Date(meta.generated_at).toLocaleString() : '';
        var contributor = meta.contributor ? 'with inputs from <strong>' + esc(meta.contributor) + '</strong> ' : '';
        parts.push('<div style="background:#f3f4f6;padding:12px 16px;border-top:1px solid #e5e7eb;margin-top:20px;border-radius:0 0 8px 8px;">' +
            '<p style="font-size:0.82em;color:#8b94a3;font-style:italic;margin:4px 0 0 0;">Generated ' + contributor + 'by RadInsights Intelligence' + (ts ? ' on ' + esc(ts) : '') + '</p>' +
            '<div style="display:flex;align-items:center;justify-content:flex-end;gap:8px;margin-top:6px;">' +
            '<img style="width:30px;height:30px;object-fit:contain;" src="https://res.cloudinary.com/dx7b7chvn/image/upload/f_auto,q_auto,w_300/v1769503548/frcr-rev-logo-transp_o2hmrq.png" alt="RadiologyInsights Logo">' +
            '<span style="font-size:0.85em;color:#6b7280;">&copy; All rights reserved RadiologyInsights</span></div></div>');

        parts.push('</div>');
        return parts.join('\n');
    }

    function renderInto(el, jsonData) {
        el.innerHTML = render(jsonData);
        el._jsonDiscussion = jsonData;
    }

    function isJson(rawString) {
        if (!rawString || typeof rawString !== 'string') return false;
        var trimmed = rawString.trim();
        if (!trimmed.startsWith('{')) return false;
        try {
            var obj = JSON.parse(trimmed);
            return !!(obj.diagnosis_summary || obj.sections);
        } catch(e) { return false; }
    }

    // ── Public API ──
    window.JsonContentRenderer = {
        render: render,
        renderInto: renderInto,
        emphCaps: emphCaps,
        isJson: isJson,
        renderStagingTable: renderStagingTable,
        esc: esc,
    };
})();
