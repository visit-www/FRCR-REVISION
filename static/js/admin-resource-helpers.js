/**
 * Admin Resource Helpers — Shared JS for IF Calculator and Reporting Template admin pages.
 *
 * Provides: reference rows, resource chips (cases, TNM, PDFs), search, PDF upload,
 * resource collection/parsing, and HTML escaping.
 *
 * Requires: CLOUDINARY_CLOUD_NAME and CLOUDINARY_UPLOAD_PRESET globals for PDF upload.
 */

// ==================== REFERENCES ====================

function addReferenceRow(containerId, data) {
    data = data || {};
    var container = document.getElementById(containerId);
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
    container.innerHTML = '';
    var refs = parseResources(sourceCitation).references;
    if (refs.length === 0) refs = [{ source: '', version: '', url: '' }];
    refs.forEach(function(r) { addReferenceRow(containerId, r); });
}

// ==================== RESOURCE PARSING ====================

function parseResources(val) {
    var empty = { references: [], linked_cases: [], linked_tnm: [], pdfs: [] };
    if (!val) return empty;
    try {
        var parsed = JSON.parse(val);
        if (Array.isArray(parsed)) {
            return { references: parsed, linked_cases: [], linked_tnm: [], pdfs: [] };
        }
        return {
            references: parsed.references || [],
            linked_cases: parsed.linked_cases || [],
            linked_tnm: parsed.linked_tnm || [],
            pdfs: parsed.pdfs || []
        };
    } catch (e) {
        if (val.trim()) {
            return { references: [{ source: val.trim(), version: '', url: '' }], linked_cases: [], linked_tnm: [], pdfs: [] };
        }
        return empty;
    }
}

function collectResources(prefix) {
    return {
        references: getReferences(prefix + 'RefsContainer'),
        linked_cases: getChips(prefix + 'LinkedCases'),
        linked_tnm: getChips(prefix + 'LinkedTnm'),
        pdfs: getChips(prefix + 'LinkedPdfs')
    };
}

function loadAllResources(prefix, sourceCitation) {
    var res = parseResources(sourceCitation);
    loadReferences(prefix + 'RefsContainer', sourceCitation);

    var casesContainer = document.getElementById(prefix + 'LinkedCases');
    casesContainer.innerHTML = '';
    res.linked_cases.forEach(function(c) { addChip(prefix + 'LinkedCases', c, 'case'); });

    var tnmContainer = document.getElementById(prefix + 'LinkedTnm');
    tnmContainer.innerHTML = '';
    res.linked_tnm.forEach(function(t) { addChip(prefix + 'LinkedTnm', t, 'tnm'); });

    var pdfsContainer = document.getElementById(prefix + 'LinkedPdfs');
    pdfsContainer.innerHTML = '';
    res.pdfs.forEach(function(p) { addChip(prefix + 'LinkedPdfs', p, 'pdf'); });
}

// ==================== CHIPS ====================

function addChip(containerId, data, type) {
    var container = document.getElementById(containerId);
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
    } else if (type === 'pdf') {
        icon = '<i class="fas fa-file-pdf" style="color: #dc3545;"></i>';
        var size = data.size ? ' (' + (data.size / 1048576).toFixed(1) + ' MB)' : '';
        label = (data.name || 'PDF') + size;
    }

    chip.innerHTML = icon + ' <span>' + escHtml(label) + '</span> <span class="remove-chip" onclick="this.parentElement.remove()" title="Remove"><i class="fas fa-times-circle"></i></span>';
    container.appendChild(chip);
}

function getChips(containerId) {
    var chips = document.querySelectorAll('#' + containerId + ' .resource-chip');
    var items = [];
    chips.forEach(function(chip) {
        try { items.push(JSON.parse(chip.dataset.json)); } catch(e) {}
    });
    return items;
}

// ==================== SEARCH ====================

var _searchTimeout = null;

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
                    } else {
                        div.innerHTML = '<i class="fas fa-sitemap me-1" style="color: #e96304;"></i><strong>' + escHtml(item.cancer_name || item.slug) + '</strong>' + (item.body_section ? ' <small class="text-muted">(' + escHtml(item.body_section) + ')</small>' : '');
                    }
                    div.onclick = function() {
                        var chipsId;
                        if (type === 'algorithm') {
                            chipsId = inputId.replace('TnmSearch', 'LinkedTnm');
                        } else {
                            chipsId = inputId.replace('CaseSearch', 'LinkedCases');
                        }
                        var existing = getChips(chipsId);
                        var isDuplicate = existing.some(function(e) {
                            if (type === 'case') return e.id === item.id;
                            return e.slug === item.slug;
                        });
                        if (!isDuplicate) {
                            addChip(chipsId, item, type === 'algorithm' ? 'tnm' : 'case');
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

    // Validate all files first
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

    // Upload files sequentially
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
    // Attach Enter key prevention + live search to all search inputs
    document.querySelectorAll('[id$="CaseSearch"], [id$="TnmSearch"]').forEach(function(input) {
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') e.preventDefault();
        });
        input.addEventListener('input', function() {
            var resultsId = this.id.replace('Search', 'Results');
            var type = this.id.includes('Tnm') ? 'algorithm' : 'case';
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
