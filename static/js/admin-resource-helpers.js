/**
 * Admin Resource Helpers — Shared JS for admin pages.
 *
 * Provides: reference rows, resource chips, unified content search,
 * PDF upload, resource collection/parsing, and HTML escaping.
 *
 * Requires: CLOUDINARY_CLOUD_NAME and CLOUDINARY_UPLOAD_PRESET globals for PDF upload.
 */

// ==================== REFERENCES ====================

function addReferenceRow(containerId, data) {
    data = data || {};
    var container = document.getElementById(containerId);
    if (!container) return;
    var row = document.createElement('div');
    row.className = 'reference-row d-flex gap-2 mb-2 align-items-start';
    row.innerHTML =
        '<div class="flex-grow-1">' +
            '<input type="text" class="form-control form-control-sm ref-source" placeholder="Source name" value="' + escAttr(data.source || '') + '">' +
        '</div>' +
        '<div style="width: 110px;">' +
            '<input type="text" class="form-control form-control-sm ref-version" placeholder="Version" value="' + escAttr(data.version || '') + '">' +
        '</div>' +
        '<div style="width: 170px;">' +
            '<input type="url" class="form-control form-control-sm ref-url" placeholder="URL (optional)" value="' + escAttr(data.url || '') + '">' +
        '</div>' +
        '<button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest(\'.reference-row\').remove()" title="Remove">' +
            '<i class="fas fa-times"></i>' +
        '</button>';
    container.appendChild(row);
}

function getReferences(containerId) {
    var rows = document.querySelectorAll('#' + containerId + ' .reference-row');
    var refs = [];
    rows.forEach(function(row) {
        var s = row.querySelector('.ref-source').value.trim();
        if (s) {
            refs.push({
                source: s,
                version: row.querySelector('.ref-version').value.trim(),
                url: row.querySelector('.ref-url').value.trim()
            });
        }
    });
    return refs;
}

function loadReferences(containerId, sourceCitation) {
    var container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';
    var refs = parseResources(sourceCitation).references;
    if (refs.length === 0) refs = [{ source: '', version: '', url: '' }];
    refs.forEach(function(r) { addReferenceRow(containerId, r); });
}

// ==================== RESOURCE PARSING ====================

function parseResources(val) {
    var empty = { references: [], linked_cases: [], linked_tnm: [], linked_algorithms: [], linked_templates: [], linked_pearls: [], pdfs: [] };
    if (!val) return empty;
    try {
        var parsed = JSON.parse(val);
        if (typeof parsed === 'string') parsed = JSON.parse(parsed);
        if (Array.isArray(parsed)) {
            return { references: parsed, linked_cases: [], linked_tnm: [], linked_algorithms: [], linked_templates: [], linked_pearls: [], pdfs: [] };
        }
        return {
            references: parsed.references || [],
            linked_cases: parsed.linked_cases || [],
            linked_tnm: parsed.linked_tnm || [],
            linked_algorithms: parsed.linked_algorithms || [],
            linked_templates: parsed.linked_templates || [],
            linked_pearls: parsed.linked_pearls || [],
            pdfs: parsed.pdfs || []
        };
    } catch (e) {
        if (val.trim() && val.trim().charAt(0) !== '{') {
            return { references: [{ source: val.trim(), version: '', url: '' }], linked_cases: [], linked_tnm: [], linked_algorithms: [], linked_templates: [], linked_pearls: [], pdfs: [] };
        }
        return empty;
    }
}

// ==================== COLLECT / LOAD (unified) ====================

function collectResources(prefix) {
    var res = {
        references: getReferences(prefix + 'RefsContainer'),
        linked_cases: [],
        linked_tnm: [],
        linked_algorithms: [],
        linked_templates: [],
        linked_pearls: [],
        pdfs: getChips(prefix + 'LinkedPdfs')
    };

    // Unified LinkedContent container — sort chips by their data-link-type
    var contentContainer = document.getElementById(prefix + 'LinkedContent');
    if (contentContainer) {
        var chips = contentContainer.querySelectorAll('.resource-chip');
        chips.forEach(function(chip) {
            try {
                var data = JSON.parse(chip.dataset.json);
                var lt = chip.dataset.linkType || '';
                if (lt === 'case') res.linked_cases.push(data);
                else if (lt === 'calculator' || lt === 'tnm') res.linked_tnm.push(data);
                else if (lt === 'reporting_algorithm') res.linked_algorithms.push(data);
                else if (lt === 'radiology_template') res.linked_templates.push(data);
                else if (lt === 'pearl') res.linked_pearls.push(data);
            } catch(e) {}
        });
    }

    // Legacy: also collect from old per-type containers if they exist
    var oldContainers = {
        'LinkedCases': 'linked_cases',
        'LinkedTnm': 'linked_tnm',
        'LinkedAlgorithms': 'linked_algorithms',
        'LinkedTemplates': 'linked_templates',
        'LinkedPearls': 'linked_pearls'
    };
    for (var suffix in oldContainers) {
        var el = document.getElementById(prefix + suffix);
        if (el) {
            var key = oldContainers[suffix];
            getChips(prefix + suffix).forEach(function(item) {
                // Avoid duplicates
                if (!res[key].some(function(x) { return x.id === item.id; })) {
                    res[key].push(item);
                }
            });
        }
    }

    return res;
}

function loadAllResources(prefix, sourceCitation) {
    var res = parseResources(sourceCitation);
    loadReferences(prefix + 'RefsContainer', sourceCitation);

    // Load PDFs
    var pdfsContainer = document.getElementById(prefix + 'LinkedPdfs');
    if (pdfsContainer) {
        pdfsContainer.innerHTML = '';
        res.pdfs.forEach(function(p) { addChip(prefix + 'LinkedPdfs', p, 'pdf'); });
    }

    // Load all linked content into unified container
    var contentContainer = document.getElementById(prefix + 'LinkedContent');
    if (contentContainer) {
        contentContainer.innerHTML = '';
        res.linked_cases.forEach(function(c) { addContentChip(prefix + 'LinkedContent', c, 'case'); });
        res.linked_tnm.forEach(function(t) { addContentChip(prefix + 'LinkedContent', t, 'calculator'); });
        res.linked_algorithms.forEach(function(a) { addContentChip(prefix + 'LinkedContent', a, 'reporting_algorithm'); });
        res.linked_templates.forEach(function(t) { addContentChip(prefix + 'LinkedContent', t, 'radiology_template'); });
        res.linked_pearls.forEach(function(p) { addContentChip(prefix + 'LinkedContent', p, 'pearl'); });
    }

    // Legacy: load into old per-type containers if they exist
    var legacyMap = [
        ['LinkedCases', res.linked_cases, 'case'],
        ['LinkedTnm', res.linked_tnm, 'tnm'],
        ['LinkedAlgorithms', res.linked_algorithms, 'algorithm_link'],
        ['LinkedTemplates', res.linked_templates, 'template_link'],
        ['LinkedPearls', res.linked_pearls, 'pearl_link'],
    ];
    legacyMap.forEach(function(entry) {
        var el = document.getElementById(prefix + entry[0]);
        if (el) {
            el.innerHTML = '';
            entry[1].forEach(function(item) { addChip(prefix + entry[0], item, entry[2]); });
        }
    });
}

// ==================== CHIPS ====================

// Type metadata for unified chips
var CONTENT_TYPE_META = {
    'case':                 { icon: 'fa-book-medical', color: '#5E899E', badge: 'Case', badgeBg: '#e4eff4' },
    'calculator':           { icon: 'fa-sitemap',      color: '#e96304', badge: 'TNM',  badgeBg: '#fdeee4' },
    'tnm':                  { icon: 'fa-sitemap',      color: '#e96304', badge: 'TNM',  badgeBg: '#fdeee4' },
    'reporting_algorithm':  { icon: 'fa-project-diagram', color: '#5E899E', badge: 'Algorithm', badgeBg: '#e4eff4' },
    'anatomy_snippet':      { icon: 'fa-bone',         color: '#6f42c1', badge: 'Anatomy', badgeBg: '#ece4f6' },
    'radiology_template':   { icon: 'fa-file-alt',     color: '#17a2b8', badge: 'Template', badgeBg: '#e1edfb' },
    'pearl':                { icon: 'fa-gem',          color: '#6b46c1', badge: 'Pearl', badgeBg: '#ece4f6' },
    'reference':            { icon: 'fa-bookmark',     color: '#6c757d', badge: 'Ref',   badgeBg: '#f0f1f3' },
};

function addContentChip(containerId, data, linkType) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var meta = CONTENT_TYPE_META[linkType] || { icon: 'fa-link', color: '#6c757d', badge: linkType, badgeBg: '#f0f1f3' };

    var label = '';
    if (linkType === 'case') {
        label = (data.case_number || '#' + data.id) + ': ' + (data.diagnosis || '').substring(0, 50);
    } else if (linkType === 'calculator' || linkType === 'tnm') {
        label = data.cancer_name || data.slug || 'Calculator';
    } else if (linkType === 'pearl') {
        var tmp = document.createElement('div');
        tmp.innerHTML = data.pearl_text || data.title || 'Pearl';
        label = (tmp.textContent || tmp.innerText || 'Pearl').substring(0, 60);
    } else {
        label = (data.title || data.name || data.slug || '').substring(0, 60);
    }

    var chip = document.createElement('span');
    chip.className = 'resource-chip';
    chip.dataset.json = JSON.stringify(data);
    chip.dataset.linkType = linkType;
    chip.innerHTML =
        '<i class="fas ' + meta.icon + '" style="color: ' + meta.color + ';"></i>' +
        '<span class="chip-type-badge" style="background: ' + meta.badgeBg + '; color: ' + meta.color + ';">' + meta.badge + '</span>' +
        '<span>' + escHtml(label) + '</span>' +
        '<span class="remove-chip" onclick="this.parentElement.remove()" title="Remove"><i class="fas fa-times-circle"></i></span>';
    container.appendChild(chip);
}

// Legacy chip function (for PDF chips and backward compat)
function addChip(containerId, data, type) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var chip = document.createElement('span');
    chip.className = 'resource-chip';
    chip.dataset.json = JSON.stringify(data);

    var label = '', icon = '';
    if (type === 'case') {
        icon = '<i class="fas fa-book-medical" style="color: #5E899E;"></i>';
        label = (data.case_number || '#' + data.id) + ': ' + (data.diagnosis || '').substring(0, 50);
    } else if (type === 'tnm') {
        icon = '<i class="fas fa-sitemap" style="color: #e96304;"></i>';
        label = data.cancer_name || data.slug;
    } else if (type === 'algorithm_link') {
        icon = '<i class="fas fa-project-diagram" style="color: #5E899E;"></i>';
        label = (data.title || data.name || 'Algorithm').substring(0, 60);
    } else if (type === 'template_link') {
        icon = '<i class="fas fa-file-alt" style="color: #17a2b8;"></i>';
        label = (data.title || data.name || 'Template').substring(0, 60);
    } else if (type === 'pearl_link') {
        icon = '<i class="fas fa-gem" style="color: #6b46c1;"></i>';
        var tmp = document.createElement('div');
        tmp.innerHTML = data.pearl_text || data.title || 'Pearl';
        label = (tmp.textContent || tmp.innerText || 'Pearl').substring(0, 60);
    } else if (type === 'pdf') {
        icon = '<i class="fas fa-file-pdf" style="color: #dc3545;"></i>';
        var size = data.size ? ' (' + (data.size / 1048576).toFixed(1) + ' MB)' : '';
        label = (data.name || 'PDF') + size;
    }

    chip.innerHTML = icon + ' <span>' + escHtml(label) + '</span> <span class="remove-chip" onclick="this.parentElement.remove()" title="Remove"><i class="fas fa-times-circle"></i></span>';
    container.appendChild(chip);
}

function getChips(containerId) {
    var el = document.getElementById(containerId);
    if (!el) return [];
    var chips = el.querySelectorAll('.resource-chip');
    var items = [];
    chips.forEach(function(chip) {
        try { items.push(JSON.parse(chip.dataset.json)); } catch(e) {}
    });
    return items;
}

// ==================== UNIFIED CONTENT SEARCH ====================

var _searchTimeout = null;

function searchContent(inputId, resultsId, chipsId) {
    var query = document.getElementById(inputId).value.trim();
    if (query.length < 2) {
        document.getElementById(resultsId).classList.add('d-none');
        return;
    }

    clearTimeout(_searchTimeout);
    _searchTimeout = setTimeout(function() {
        fetch('/api/cases/search?type=all&q=' + encodeURIComponent(query) + '&limit=15')
            .then(function(r) { return r.json(); })
            .then(function(results) {
                var container = document.getElementById(resultsId);
                container.innerHTML = '';
                if (results.length === 0) {
                    container.innerHTML = '<div class="search-result-item text-muted">No results found</div>';
                    container.classList.remove('d-none');
                    return;
                }
                results.forEach(function(item) {
                    var lt = item.link_type || '';
                    var meta = CONTENT_TYPE_META[lt] || { icon: 'fa-link', color: '#6c757d', badge: lt, badgeBg: '#f0f1f3' };

                    var label = '';
                    if (lt === 'case') {
                        label = '<strong>' + escHtml(item.case_number) + '</strong>: ' + escHtml(item.diagnosis || '');
                    } else if (lt === 'calculator') {
                        label = '<strong>' + escHtml(item.cancer_name || item.slug) + '</strong>';
                        if (item.body_section) label += ' <small class="text-muted">(' + escHtml(item.body_section) + ')</small>';
                    } else if (lt === 'pearl') {
                        var pearlText = (item.title || '').replace(/<[^>]+>/g, '').substring(0, 80);
                        label = '<strong>' + escHtml(pearlText || 'Pearl #' + item.id) + '</strong>';
                    } else {
                        label = '<strong>' + escHtml(item.title || item.name || item.slug || '') + '</strong>';
                        if (item.body_section || item.category) label += ' <small class="text-muted">(' + escHtml(item.body_section || item.category || '') + ')</small>';
                    }

                    var div = document.createElement('div');
                    div.className = 'search-result-item d-flex align-items-center gap-2';
                    div.innerHTML =
                        '<i class="fas ' + meta.icon + '" style="color: ' + meta.color + '; width: 16px; text-align: center;"></i>' +
                        '<span class="chip-type-badge" style="background: ' + meta.badgeBg + '; color: ' + meta.color + '; font-size: 0.6rem; padding: 0 4px; border-radius: 3px; font-weight: 600; text-transform: uppercase;">' + meta.badge + '</span>' +
                        '<span class="flex-grow-1">' + label + '</span>';

                    div.onclick = function() {
                        // Check for duplicate
                        var existing = document.querySelectorAll('#' + chipsId + ' .resource-chip');
                        var isDuplicate = false;
                        existing.forEach(function(chip) {
                            try {
                                var d = JSON.parse(chip.dataset.json);
                                if (d.id === item.id && chip.dataset.linkType === lt) isDuplicate = true;
                            } catch(e) {}
                        });
                        if (!isDuplicate) {
                            addContentChip(chipsId, item, lt);
                        }
                        container.classList.add('d-none');
                        document.getElementById(inputId).value = '';
                    };
                    container.appendChild(div);
                });
                container.classList.remove('d-none');
            });
    }, 300);
}

// Legacy per-type search (kept for backward compat with old templates)
function searchItems(inputId, resultsId, type) {
    var query = document.getElementById(inputId).value.trim();
    if (query.length < 2) {
        document.getElementById(resultsId).classList.add('d-none');
        return;
    }

    clearTimeout(_searchTimeout);
    _searchTimeout = setTimeout(function() {
        fetch('/api/cases/search?type=' + type + '&q=' + encodeURIComponent(query) + '&limit=10')
            .then(function(r) { return r.json(); })
            .then(function(results) {
                var container = document.getElementById(resultsId);
                container.innerHTML = '';
                if (results.length === 0) {
                    container.innerHTML = '<div class="search-result-item text-muted">No results found</div>';
                    container.classList.remove('d-none');
                    return;
                }
                results.forEach(function(item) {
                    var div = document.createElement('div');
                    div.className = 'search-result-item';
                    if (type === 'case') {
                        div.innerHTML = '<i class="fas fa-book-medical me-1" style="color: #5E899E;"></i><strong>' + escHtml(item.case_number) + '</strong>: ' + escHtml(item.diagnosis || '');
                    } else if (type === 'algorithm') {
                        div.innerHTML = '<i class="fas fa-sitemap me-1" style="color: #e96304;"></i><strong>' + escHtml(item.cancer_name || item.slug) + '</strong>' + (item.body_section ? ' <small class="text-muted">(' + escHtml(item.body_section) + ')</small>' : '');
                    } else if (type === 'reporting_algorithm') {
                        div.innerHTML = '<i class="fas fa-project-diagram me-1" style="color: #5E899E;"></i><strong>' + escHtml(item.title || item.name || '') + '</strong>' + (item.category ? ' <small class="text-muted">(' + escHtml(item.category) + ')</small>' : '');
                    } else if (type === 'radiology_template') {
                        div.innerHTML = '<i class="fas fa-file-alt me-1" style="color: #17a2b8;"></i><strong>' + escHtml(item.title || item.name || '') + '</strong>' + (item.body_section ? ' <small class="text-muted">(' + escHtml(item.body_section) + ')</small>' : '');
                    } else if (type === 'pearl') {
                        var pearlPreview = (item.pearl_text || '').replace(/<[^>]+>/g, '').substring(0, 80);
                        div.innerHTML = '<i class="fas fa-gem me-1" style="color: #6b46c1;"></i><strong>' + escHtml(pearlPreview || 'Pearl #' + item.id) + '</strong>' + (item.body_section ? ' <small class="text-muted">(' + escHtml(item.body_section) + ')</small>' : '');
                    } else {
                        div.innerHTML = '<i class="fas fa-link me-1 text-muted"></i><strong>' + escHtml(item.title || item.name || item.slug || '') + '</strong>';
                    }
                    div.onclick = function() {
                        var chipsId, chipType;
                        if (type === 'algorithm') {
                            chipsId = inputId.replace('TnmSearch', 'LinkedTnm');
                            chipType = 'tnm';
                        } else if (type === 'case') {
                            chipsId = inputId.replace('CaseSearch', 'LinkedCases');
                            chipType = 'case';
                        } else if (type === 'reporting_algorithm') {
                            chipsId = inputId.replace('AlgorithmSearch', 'LinkedAlgorithms');
                            chipType = 'algorithm_link';
                        } else if (type === 'radiology_template') {
                            chipsId = inputId.replace('TemplateSearch', 'LinkedTemplates');
                            chipType = 'template_link';
                        } else if (type === 'pearl') {
                            chipsId = inputId.replace('PearlSearch', 'LinkedPearls');
                            chipType = 'pearl_link';
                        }
                        var existing = getChips(chipsId);
                        var isDuplicate = existing.some(function(e) { return e.id === item.id; });
                        if (!isDuplicate) {
                            addChip(chipsId, item, chipType);
                        }
                        container.classList.add('d-none');
                        document.getElementById(inputId).value = '';
                    };
                    container.appendChild(div);
                });
                container.classList.remove('d-none');
            });
    }, 300);
}

// ==================== PDF UPLOAD ====================

function uploadPDFs(input, chipsContainerId, progressId) {
    var files = Array.from(input.files);
    if (!files.length) return;

    if (typeof CLOUDINARY_CLOUD_NAME === 'undefined' || !CLOUDINARY_CLOUD_NAME ||
        typeof CLOUDINARY_UPLOAD_PRESET === 'undefined' || !CLOUDINARY_UPLOAD_PRESET) {
        alert('PDF upload not configured. Please set Cloudinary environment variables.');
        input.value = '';
        return;
    }

    for (var i = 0; i < files.length; i++) {
        if (!files[i].name.toLowerCase().endsWith('.pdf')) {
            alert(files[i].name + ' is not a PDF. Only PDF files are allowed.');
            input.value = '';
            return;
        }
        if (files[i].size > 10 * 1024 * 1024) {
            alert(files[i].name + ' exceeds 10 MB limit.');
            input.value = '';
            return;
        }
    }

    var progressDiv = document.getElementById(progressId);
    var progressBar = progressDiv.querySelector('.progress-bar');

    var idx = 0;
    function uploadNext() {
        if (idx >= files.length) {
            progressDiv.classList.add('d-none');
            input.value = '';
            return;
        }
        var file = files[idx];
        progressDiv.classList.remove('d-none');
        progressBar.style.width = '0%';
        progressBar.textContent = (idx + 1) + '/' + files.length;

        var formData = new FormData();
        formData.append('file', file);
        formData.append('upload_preset', CLOUDINARY_UPLOAD_PRESET);
        formData.append('folder', 'frcr_revision/admin_pdfs');

        var xhr = new XMLHttpRequest();
        xhr.upload.onprogress = function(e) {
            if (e.lengthComputable) {
                progressBar.style.width = Math.round((e.loaded / e.total) * 100) + '%';
            }
        };
        xhr.onload = function() {
            if (xhr.status >= 200 && xhr.status < 300) {
                var data = JSON.parse(xhr.responseText);
                addChip(chipsContainerId, {
                    url: data.secure_url,
                    name: file.name,
                    public_id: data.public_id,
                    size: file.size
                }, 'pdf');
            } else {
                alert('Upload failed for ' + file.name);
            }
            idx++;
            uploadNext();
        };
        xhr.onerror = function() {
            alert('Upload failed for ' + file.name);
            idx++;
            uploadNext();
        };
        xhr.open('POST', 'https://api.cloudinary.com/v1_1/' + CLOUDINARY_CLOUD_NAME + '/raw/upload');
        xhr.send(formData);
    }
    uploadNext();
}

// ==================== UTILITY ====================

function escHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escAttr(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ==================== AUTO-INIT ====================

document.addEventListener('DOMContentLoaded', function() {
    // Attach unified content search to all ContentSearch inputs
    document.querySelectorAll('[id$="ContentSearch"]').forEach(function(input) {
        input.addEventListener('keydown', function(e) { if (e.key === 'Enter') e.preventDefault(); });
        input.addEventListener('input', function() {
            var prefix = this.id.replace('ContentSearch', '');
            searchContent(this.id, prefix + 'ContentResults', prefix + 'LinkedContent');
        });
    });

    // Legacy: attach per-type search to old-style inputs if they exist
    var _searchTypeMap = {
        'CaseSearch': 'case',
        'TnmSearch': 'algorithm',
        'AlgorithmSearch': 'reporting_algorithm',
        'TemplateSearch': 'radiology_template',
        'PearlSearch': 'pearl'
    };
    document.querySelectorAll('[id$="CaseSearch"], [id$="TnmSearch"], [id$="AlgorithmSearch"], [id$="TemplateSearch"], [id$="PearlSearch"]').forEach(function(input) {
        input.addEventListener('keydown', function(e) { if (e.key === 'Enter') e.preventDefault(); });
        input.addEventListener('input', function() {
            var resultsId = this.id.replace('Search', 'Results');
            var type = 'case';
            for (var suffix in _searchTypeMap) {
                if (this.id.endsWith(suffix)) { type = _searchTypeMap[suffix]; break; }
            }
            searchItems(this.id, resultsId, type);
        });
    });

    // Init generate modal with one empty reference row
    var genRefsContainer = document.getElementById('genRefsContainer');
    if (genRefsContainer) addReferenceRow('genRefsContainer');
});

// Close search results when clicking outside
document.addEventListener('click', function(e) {
    if (!e.target.closest('.input-group') && !e.target.closest('.search-results-dropdown')) {
        document.querySelectorAll('.search-results-dropdown').forEach(function(el) {
            el.classList.add('d-none');
        });
    }
});
