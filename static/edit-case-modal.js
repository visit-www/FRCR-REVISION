/**
 * Case Edit Interface - Full-page editing experience
 * Handles: Case details, Q&A pairs, images with descriptions
 */

const DEBUG = (window.location.hostname === 'localhost');

// Get API base URL from config.js
const getAPIUrl = (path) => {
    const baseUrl = (typeof API_BASE_URL !== 'undefined') ? API_BASE_URL : 'http://localhost:5000';
    return baseUrl + path;
};

// Initialize and navigate to the edit case page
function openCaseEditModal(caseId) {
    // Navigate to the full-page edit interface
    window.location.href = `/edit-case?id=${caseId}`;
}

// Populate modal with case data
function populateEditModal(caseData, images) {
    // Basic case fields
    document.getElementById('editCaseId').value = caseData.id;
    document.getElementById('editCaseNumber').value = caseData.case_number || '';
    document.getElementById('editCaseDiagnosis').value = caseData.diagnosis || '';
    document.getElementById('editCaseDiscussion').value = caseData.discussion || '';
        // Status is now the source of truth for visibility (is_public is auto-synced)
    
    // Update header info
    const headerInfo = document.getElementById('editCaseHeaderInfo');
    if (headerInfo) {
    const isPublic = document.getElementById('editCaseIsPublic')?.checked || false;
        headerInfo.textContent = `Case #${caseData.case_number} - ${caseData.diagnosis}`;
    }
    
    // Populate Q&A pairs from case data
    populateQAPairs(caseData);
    
    // Populate images
    populateImages(images);
}

// Populate Q&A pairs
function populateQAPairs(caseData) {
    const container = document.getElementById('qaPairsContainer');
    container.innerHTML = '';
    
    let hasQA = false;
    
    // Add question pairs if they exist
    if (caseData.questions && caseData.questions.length > 0) {
        caseData.questions.forEach((question, index) => {
            const answer = caseData.answers && caseData.answers[index] ? caseData.answers[index].answer_text : '';
            addQAPairRow(question.question_text || '', answer);
            hasQA = true;
        });
    }
    
    // Add answer-only pairs if they exist
    if (caseData.answers && caseData.answers.length > (caseData.questions?.length || 0)) {
        const startIndex = caseData.questions?.length || 0;
        for (let i = startIndex; i < caseData.answers.length; i++) {
            addQAPairRow('', caseData.answers[i].answer_text || '');
            hasQA = true;
        }
    }
    
    if (!hasQA) {
        container.innerHTML = '<p class="text-muted mb-3">No Q&A pairs yet. Add one below.</p>';
    }
}

// Add Q&A pair row (new or existing) with TinyMCE for answers
// isAiGenerated: if true, applies orange background styling (removed on save)
function addQAPairRow(questionText = '', answerText = '', isAiGenerated = false) {
    const container = document.getElementById('qaPairsContainer');
    const pairNum = container.querySelectorAll('.qa-pair-row').length + 1;
    const questionId = 'qa-question-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    const uniqueId = 'qa-answer-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    
    // AI badge indicator (orange brand color)
    const aiIndicator = isAiGenerated 
        ? '<span class="badge ms-2" style="background-color: var(--peachy-orange, #e96304); color: white;" title="AI Generated"><i class="fas fa-robot me-1"></i>AI</span>' 
        : '';
    
    const row = document.createElement('div');
    row.className = 'qa-pair-row p-3 mb-3 border rounded bg-light';
    
    // Add AI-generated styling (orange background) if applicable
    if (isAiGenerated) {
        row.classList.add('ai-generated-pair');
    }
    row.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-2">
            <h6 class="mb-0"><strong>Pair ${pairNum}</strong>${aiIndicator}</h6>
            <button type="button" class="btn btn-sm btn-danger" onclick="removeQAPair(this)">
                <i class="fas fa-trash me-1"></i>Remove
            </button>
        </div>
        <div class="qa-pair-grid">
            <div class="qa-question-col qa-question-card">
                <label class="form-label small text-info"><i class="fas fa-question-circle me-1"></i>Question (Rich Text)</label>
                <textarea class="form-control qa-question-text qa-rich-editor" id="${questionId}" data-qa-question="true" placeholder="Enter question with optional formatting...">${escapeHtml(questionText)}</textarea>
                <small class="text-muted d-block mt-1">Supports tables, lists, formatting</small>
            </div>
            <div class="qa-answer-col qa-answer-card">
                <label class="form-label small text-success"><i class="fas fa-edit me-1"></i>Answer (Rich Text)</label>
                <textarea class="form-control qa-answer-text qa-rich-editor" id="${uniqueId}" data-qa-answer="true" placeholder="Enter answer with optional formatting, tables, lists...">${escapeHtml(answerText)}</textarea>
                <small class="text-muted d-block mt-1">Supports tables, lists, formatting</small>
            </div>
        </div>
    `;
    
    container.appendChild(row);
    
    // Initialize TinyMCE for the question and answer fields
    initializeTinyMCE(questionId);
    initializeTinyMCE(uniqueId);
}

// Expose addQAPairRow immediately
if (typeof window !== 'undefined') {
    window.addQAPairRow = addQAPairRow;
}

// Initialize TinyMCE editor for a specific field
function initializeTinyMCE(elementId, retryCount = 0) {
    const MAX_RETRIES = 20; // Max 10 seconds of retries
    
    if (typeof tinymce === 'undefined' || !tinymce.init) {
        if (retryCount < MAX_RETRIES) {
            if (DEBUG) console.log(`TinyMCE not loaded yet for ${elementId}, retrying... (${retryCount + 1}/${MAX_RETRIES})`);
            setTimeout(() => initializeTinyMCE(elementId, retryCount + 1), 500);
            return;
        } else {
            console.error('TinyMCE failed to load after maximum retries for', elementId);
        return;
    }
    }
    
    // Check if element exists
    const element = document.getElementById(elementId);
    if (!element) {
        console.warn(`Element ${elementId} not found, cannot initialize TinyMCE`);
        return;
    }
    
    // Check if already initialized
    if (tinymce.get(elementId)) {
        if (DEBUG) console.log(`TinyMCE already initialized for ${elementId}`);
        return;
    }
    
    if (DEBUG) console.log(`Initializing TinyMCE for ${elementId}`);
    tinymce.init({
        selector: '#' + elementId,
        height: 300,
        menubar: false,
        toolbar: 'undo redo | blocks | bold italic underline strikethrough | numlist bullist indent outdent | table link image code removeformat',
        plugins: 'table link image code',
        // Use CDN for assets (themes, skins, etc.) since we only have the minified JS locally
        base_url: 'https://cdn.jsdelivr.net/npm/tinymce@6',
        // TinyMCE 6: paste is core; deprecated options removed
        table_advtab: false,
        table_cell_advtab: false,
        table_default_attributes: {
            border: '1',
            class: 'table table-sm table-bordered'
        },
        table_toolbar: 'tableprops tabledelete | tableinsertrowbefore tableinsertrowafter tabledeleterow | tableinsertcolbefore tableinsertcolafter tabledeletecol | tablemerge',
        image_advtab: true,
        link_assume_external_targets: true,
        content_css: 'default',
        skin: 'oxide',
        content_style: `
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                font-size: 14px;
                line-height: 1.6;
                text-align: left !important;
            }
            a {
                text-decoration: none !important;
            }
            a:hover {
                text-decoration: underline !important;
            }
            p, h1, h2, h3, h4, h5, h6, li, td, th {
                text-align: left !important;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 1rem 0;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            th {
                background-color: #f8f9fa;
                font-weight: 600;
            }
            @media (max-width: 640px) {
                table {
                    display: block;
                    overflow-x: auto;
                    -webkit-overflow-scrolling: touch;
                }
            }
        `,
        setup: function(editor) {
            editor.on('change', function() {
                tinymce.triggerSave();
            });
        }
    });
}

// Remove Q&A pair row
function removeQAPair(button) {
    const row = button.closest('.qa-pair-row');
    
    // Destroy TinyMCE instances in this row before removing
    const textareas = row.querySelectorAll('textarea.qa-rich-editor');
    textareas.forEach(textarea => {
        if (textarea.id && typeof tinymce !== 'undefined' && tinymce.get(textarea.id)) {
            tinymce.get(textarea.id).remove();
        }
    });
    
    row.remove();
}

// Add new Q&A pair
function addNewQAPair() {
    addQAPairRow();
}

// Populate images with improved UI
function populateImages(images) {
    if (DEBUG) console.log('[populateImages] Called with', images ? images.length : 0, 'images');
    const container = document.getElementById('editImagesContainer');
    if (!container) {
        console.error('[populateImages] Container editImagesContainer not found!');
        return;
    }
    container.innerHTML = '';
    
    if (!images || images.length === 0) {
        if (DEBUG) console.log('[populateImages] No images provided');
        container.innerHTML = '<p class="text-muted text-center py-3">No images uploaded yet</p>';
        return;
    }
    
    if (DEBUG) console.log('[populateImages] Processing', images.length, 'images');
    
    const grid = document.createElement('div');
    grid.className = 'row g-3';
    
    images.forEach(image => {
        const col = document.createElement('div');
        col.className = 'col-md-4';
        col.id = `image-card-${image.id}`;
        
        // Handle both filename and image_filename formats
        const imageFilename = image.filename || image.image_filename || 'image.jpg';
        const imageDescription = image.description || image.image_description || '';
        
        // For staging images, use data_url; for production images, use API endpoint
        let imageSrc;
        if (image.data_url) {
            // Already a complete data URL
            imageSrc = image.data_url;
        } else if (image.image_data) {
            // Base64 data without data URL prefix
            const imageType = image.image_type || 'image/jpeg';
            imageSrc = `data:${imageType};base64,${image.image_data}`;
        } else {
            // Production image - use API endpoint
            imageSrc = `/api/case-image/${image.id}`;
        }
        
        // Staging images can't be edited/deleted until promotion
        const isStaging = image.is_staging || image.id.toString().startsWith('staging-');
        const actionButtons = isStaging 
            ? '<small class="text-muted d-block mt-2"><i class="fas fa-info-circle"></i> Images will be available for editing after promotion</small>'
            : `
                    <div class="mt-2 d-flex gap-1">
                        <button type="button" class="btn btn-sm btn-info flex-grow-1" 
                            onclick="editImageDescription('${image.id}')">
                            <i class="fas fa-edit"></i> Desc
                        </button>
                        <button type="button" class="btn btn-sm btn-danger" 
                            onclick="deleteImage('${image.id}')">
                            <i class="fas fa-trash"></i> Del
                        </button>
                    </div>
            `;
        
        col.innerHTML = `
            <div class="card image-card h-100 shadow-sm">
                <img src="${imageSrc}" alt="${escapeHtml(imageFilename)}" 
                     class="card-img-top" style="height: 180px; object-fit: cover; cursor: pointer;"
                     onclick="${isStaging ? '' : `viewImageFull('${image.id}')`}" 
                     title="${isStaging ? 'Staging image - click to view' : 'Click to view full size'}">
                <div class="card-body p-3">
                    <small class="text-muted d-block text-truncate mb-2" title="${escapeHtml(imageFilename)}">
                        📁 ${escapeHtml(imageFilename)}
                    </small>
                    <div class="description-section mb-2">
                        <small class="image-description-text d-block" id="desc-${image.id}" style="min-height: 40px; word-wrap: break-word;">
                            ${imageDescription ? formatImageDescriptionForDisplay(imageDescription) : '<em class="text-muted">No description</em>'}
                        </small>
                    </div>
                    ${actionButtons}
                </div>
            </div>
        `;
        grid.appendChild(col);
    });
    
    container.appendChild(grid);
}

// Expose populateImages immediately
if (typeof window !== 'undefined') {
    window.populateImages = populateImages;
}

// Edit image description - improved with modal dialog
function editImageDescription(imageId) {
    // Fetch the original description from the API to get the unescaped version
    fetch(`/api/case-image/${imageId}/description`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch image description');
            }
            return response.json();
        })
        .then(data => {
            // Get the original description from the API response
            const currentDescription = data.description || '';

    // Create a modal for editing description with TinyMCE
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'descriptionModal';
    modal.innerHTML = `
        <div class="modal-dialog modal-xl" style="max-width: 98vw; width: 98vw;">
            <div class="modal-content">
                <div class="modal-header bg-info text-white" style="padding: 0.75rem 1rem;">
                    <h5 class="modal-title"><i class="fas fa-image me-2"></i>Edit Image Description</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body" style="padding: 0;">
                    <textarea class="form-control rich-editor" id="descriptionInput" rows="12" placeholder="Enter image description..." style="min-height: 400px; width: 100%; border: none;"></textarea>
                </div>
                <div class="modal-footer bg-dark text-white" style="padding: 0.75rem 1rem; display: flex; justify-content: space-between; align-items: center;">
                    <small class="text-white" style="margin: 0;">
                        <i class="fas fa-align-left me-1"></i><strong>Description:</strong> You can use rich text formatting for better descriptions.
                    </small>
                    <div>
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                            <i class="fas fa-times me-2"></i>Cancel
                        </button>
                        <button type="button" class="btn btn-info" onclick="saveImageDescription(${imageId})">
                            <i class="fas fa-save me-2"></i>Save
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Remove old modal if exists
    const oldModal = document.getElementById('descriptionModal');
    if (oldModal) oldModal.remove();

    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();

    // Initialize TinyMCE for the description textarea after modal is shown
            // Use the same initialization function as Q&A answers for consistency
    setTimeout(() => {
                const textarea = document.getElementById('descriptionInput');
                if (textarea) {
                    // Set value first as fallback
                    textarea.value = currentDescription;
                    
                    // Initialize TinyMCE with retry logic (same as Q&A answers)
                    // Use custom height for image description editor
                    setTimeout(() => {
                        if (typeof tinymce !== 'undefined' && tinymce.init) {
                            tinymce.init({
                                selector: '#descriptionInput',
                                height: 400,
                                menubar: false,
                                toolbar: 'undo redo | bold italic underline | numlist bullist | table link code removeformat',
                                plugins: 'table link code',
                                base_url: 'https://cdn.jsdelivr.net/npm/tinymce@6',
                                // Use TinyMCE's built-in paste handling
                                // TinyMCE 6: paste is core; deprecated options removed
                                content_style: `
                                    body {
                                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                                        font-size: 14px;
                                        line-height: 1.6;
                                    }
                                    a {
                                        text-decoration: none !important;
                                    }
                                    a:hover {
                                        text-decoration: underline !important;
                                    }
                                    table {
                                        border-collapse: collapse;
                                        width: 100%;
                                        margin: 1rem 0;
                                    }
                                    th, td {
                                        border: 1px solid #ddd;
                                        padding: 8px;
                                        text-align: left;
                                    }
                                    th {
                                        background-color: #f8f9fa;
                                        font-weight: 600;
                                    }
                                    @media (max-width: 640px) {
                                        table {
                                            display: block;
                                            overflow-x: auto;
                                            -webkit-overflow-scrolling: touch;
                                        }
                                    }
                                `,
                                content_css: 'default',
                                skin: 'oxide',
                                setup: function(editor) {
                                    editor.on('init', function() {
                                        editor.setContent(currentDescription);
                                    });
                                }
                            });
                        }
                    }, 100);
                    
                    // Wait for TinyMCE to initialize, then set content
                    function setContentWhenReady(retries = 0) {
                        if (retries > 20) {
                            console.warn('TinyMCE not ready for image description, using textarea fallback');
                            return;
                        }
                        if (typeof tinymce !== 'undefined' && tinymce.get('descriptionInput')) {
                            tinymce.get('descriptionInput').setContent(currentDescription);
                        } else {
                            setTimeout(() => setContentWhenReady(retries + 1), 100);
                        }
                    }
                    setContentWhenReady();
                }
            }, 300);

            // Clean up after modal closes
            modal.addEventListener('hidden.bs.modal', () => {
                if (typeof tinymce !== 'undefined' && tinymce.get('descriptionInput')) {
                    tinymce.get('descriptionInput').remove();
                }
                modal.remove();
            });
        })
        .catch(error => {
            console.error('Error fetching image description:', error);
            // Fallback: try to get from DOM element
            const descElement = document.getElementById(`desc-${imageId}`);
            let currentDescription = '';
            if (descElement) {
                const innerHTML = descElement.innerHTML.trim();
                if (innerHTML !== '<em class="text-muted">No description</em>') {
                    // Try to decode HTML entities
                    const textarea = document.createElement('textarea');
                    textarea.innerHTML = innerHTML;
                    currentDescription = textarea.value;
                }
            }
            
            // Create modal with fallback description
            const modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.id = 'descriptionModal';
            modal.innerHTML = `
                <div class="modal-dialog modal-xl" style="max-width: 98vw; width: 98vw;">
                    <div class="modal-content">
                        <div class="modal-header bg-info text-white" style="padding: 0.75rem 1rem;">
                    <h5 class="modal-title">Edit Image Description</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                        <div class="modal-body" style="padding: 0;">
                            <textarea class="form-control rich-editor" id="descriptionInput" rows="12" placeholder="Enter image description..." style="min-height: 400px; width: 100%; border: none;">${currentDescription}</textarea>
                </div>
                        <div class="modal-footer bg-dark text-white" style="padding: 0.75rem 1rem; display: flex; justify-content: space-between; align-items: center;">
                            <small class="text-white" style="margin: 0;">
                                <i class="fas fa-align-left me-1"></i><strong>Description:</strong> You can use rich text formatting for better descriptions.
                            </small>
                            <div>
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-info" onclick="saveImageDescription(${imageId})">Save</button>
                            </div>
                </div>
            </div>
        </div>
    `;

    const oldModal = document.getElementById('descriptionModal');
    if (oldModal) oldModal.remove();
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();

    setTimeout(() => {
                if (typeof tinymce !== 'undefined' && tinymce.init) {
            tinymce.init({
                selector: '#descriptionInput',
                height: 250,
                menubar: false,
                toolbar: 'undo redo | bold italic underline | numlist bullist | table link code removeformat',
                plugins: 'table link code',
                        // Use CDN for assets (themes, skins, etc.) since we only have the minified JS locally
                        base_url: 'https://cdn.jsdelivr.net/npm/tinymce@6',
                // Use TinyMCE's built-in paste handling
                // TinyMCE 6: paste is core; deprecated options removed
                content_css: 'default',
                content_style: `
                    a {
                        text-decoration: none !important;
                    }
                    a:hover {
                        text-decoration: underline !important;
                    }
                `,
                skin: 'oxide',
                setup: function(editor) {
                    editor.on('init', function() {
                        editor.setContent(currentDescription);
                    });
                }
            });
        }
    }, 300);

    modal.addEventListener('hidden.bs.modal', () => {
        if (typeof tinymce !== 'undefined' && tinymce.get('descriptionInput')) {
            tinymce.get('descriptionInput').remove();
        }
        modal.remove();
            });
    });
}

// Save image description
function saveImageDescription(imageId) {
    let newDescription = '';
    if (typeof tinymce !== 'undefined' && tinymce.get('descriptionInput')) {
        newDescription = tinymce.get('descriptionInput').getContent();
    } else {
        newDescription = document.getElementById('descriptionInput').value.trim();
    }

    fetch(`/api/case-image/${imageId}/description`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: newDescription })
    })
    .then(r => {
        if (!r.ok) {
            return r.json().then(err => {
                throw new Error(err.error || `HTTP ${r.status}: ${r.statusText}`);
            });
        }
        return r.json();
    })
    .then(data => {
        const modal = bootstrap.Modal.getInstance(document.getElementById('descriptionModal'));
        if (modal) {
        modal.hide();
        }

        // Update the description on the page - use the cleaned description from server
        const descElement = document.getElementById(`desc-${imageId}`);
        if (descElement) {
            const savedDescription = data.description || newDescription;
            descElement.innerHTML = savedDescription ? savedDescription : '<em class="text-muted">No description</em>';
        }
        
        if (DEBUG) console.log('Image description saved successfully');
    })
    .catch(error => {
        console.error('Error updating description:', error);
        alert('Error updating description: ' + error.message);
    });
}

// Delete image with confirmation
function deleteImage(imageId) {
    if (!confirm('Are you sure you want to delete this image? This action cannot be undone.')) {
        return;
    }
    
    // Show loading state
    const card = document.getElementById(`image-card-${imageId}`);
    if (card) {
        card.style.opacity = '0.5';
        card.style.pointerEvents = 'none';
    }
    
    fetch(`/api/case-image/${imageId}`, { method: 'DELETE' })
        .then(r => r.json())
        .then(data => {
            if (data.message || data.success) {
                // Remove card from DOM
                if (card) card.remove();
                
                // Check if any images remain
                const remainingCards = document.querySelectorAll('[id^="image-card-"]');
                if (remainingCards.length === 0) {
                    const container = document.getElementById('editImagesContainer');
                    container.innerHTML = '<p class="text-muted text-center py-3">No images uploaded yet</p>';
                }
            } else {
                alert('Error deleting image: ' + (data.error || 'Unknown error'));
                if (card) {
                    card.style.opacity = '1';
                    card.style.pointerEvents = 'auto';
                }
            }
        })
        .catch(error => {
            console.error('Error deleting image:', error);
            alert('Error deleting image');
            if (card) {
                card.style.opacity = '1';
                card.style.pointerEvents = 'auto';
            }
        });
}

// Reload images from server
function reloadImages(caseId) {
    fetch(`/api/case/${caseId}/images`)
        .then(r => r.json())
        .then(images => populateImages(images))
        .catch(error => console.error('Error reloading images:', error));
}

// View image in full size (new window)
function viewImageFull(imageId) {
    window.open(`/api/case-image/${imageId}`, '_blank');
}

// Escape HTML to prevent XSS and display special characters correctly
function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// Highlight courtesy/credits text while keeping main description readable
function formatImageDescriptionForDisplay(text) {
    const escaped = escapeHtml(text);
    if (!escaped) return '';
    const metaPattern = /(courtesy[^.]*\.|credit[s]?:?[^.]*\.)/gi;
    return escaped.replace(metaPattern, '<span class="image-desc-meta">$1</span>');
}

/**
 * Upload a file directly to Cloudinary (unsigned preset). Returns { secure_url, public_id }.
 * Use when CLOUDINARY_CLOUD_NAME and CLOUDINARY_UPLOAD_PRESET are set to avoid 413 on Vercel.
 */
function uploadFileToCloudinary(file) {
    const cloudName = window.CLOUDINARY_CLOUD_NAME;
    const preset = window.CLOUDINARY_UPLOAD_PRESET;
    if (!cloudName || !preset) {
        return Promise.reject(new Error('Direct upload not configured'));
    }
    const formData = new FormData();
    formData.append('file', file);
    formData.append('upload_preset', preset);
    formData.append('folder', 'frcr_revision/frcr_cases');
    const url = `https://api.cloudinary.com/v1_1/${cloudName}/image/upload`;
    return fetch(url, { method: 'POST', body: formData })
        .then(function(r) {
            if (!r.ok) {
                return r.json().then(function(d) {
                    throw new Error(d.error && d.error.message ? d.error.message : 'Cloudinary upload failed');
                }).catch(function(e) {
                    if (e instanceof Error && e.message !== 'Cloudinary upload failed') throw e;
                    throw new Error(r.statusText || 'Cloudinary upload failed');
                });
            }
            return r.json();
        })
        .then(function(data) {
            return { secure_url: data.secure_url, public_id: data.public_id };
        });
}

/**
 * Compress an image file using canvas to stay under server upload limits.
 * Returns a Promise that resolves to a compressed File object.
 * For JPEG/WebP: reduces quality. For PNG: converts to JPEG.
 * Target: under 4MB to stay within Vercel's ~4.5MB body limit.
 */
function compressImage(file, maxWidthPx, maxSizeMB) {
    maxWidthPx = maxWidthPx || 2048;
    maxSizeMB = maxSizeMB || 3.5;
    var maxSizeBytes = maxSizeMB * 1024 * 1024;

    // Skip if already under limit
    if (file.size <= maxSizeBytes) {
        return Promise.resolve(file);
    }

    return new Promise(function(resolve, reject) {
        var img = new Image();
        var url = URL.createObjectURL(file);

        img.onload = function() {
            URL.revokeObjectURL(url);

            var width = img.width;
            var height = img.height;

            // Scale down if wider than maxWidthPx
            if (width > maxWidthPx) {
                height = Math.round(height * (maxWidthPx / width));
                width = maxWidthPx;
            }

            var canvas = document.createElement('canvas');
            canvas.width = width;
            canvas.height = height;
            var ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, width, height);

            // Try progressively lower quality until under limit
            var mimeType = 'image/jpeg';
            var quality = 0.85;
            var minQuality = 0.4;

            function tryCompress() {
                canvas.toBlob(function(blob) {
                    if (!blob) {
                        reject(new Error('Canvas compression failed'));
                        return;
                    }
                    if (blob.size <= maxSizeBytes || quality <= minQuality) {
                        var compressedName = file.name.replace(/\.[^.]+$/, '') + '.jpg';
                        var compressedFile = new File([blob], compressedName, { type: mimeType });
                        if (DEBUG) console.log('[IMAGE] Compressed: ' + (file.size / 1024 / 1024).toFixed(1) + 'MB -> ' + (blob.size / 1024 / 1024).toFixed(1) + 'MB (quality=' + quality.toFixed(2) + ', ' + width + 'x' + height + ')');
                        resolve(compressedFile);
                    } else {
                        quality -= 0.1;
                        tryCompress();
                    }
                }, mimeType, quality);
            }

            tryCompress();
        };

        img.onerror = function() {
            URL.revokeObjectURL(url);
            reject(new Error('Failed to load image for compression'));
        };

        img.src = url;
    });
}

// Upload image with validation
function uploadImage() {
    const input = document.getElementById('editImageInput');
    const file = input.files[0];
    
    if (!file) {
        alert('Please select an image file');
        return;
    }
    
    // Validate file type
    if (!file.type.startsWith('image/')) {
        alert('Please select a valid image file (JPEG, PNG, GIF, WebP)');
        return;
    }
    
    // Validate file size (10MB max)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
        alert('File size exceeds 10MB limit');
        return;
    }
    
    const caseId = document.getElementById('editCaseId').value;
    if (DEBUG) console.log('[IMAGE] Upload attempt - caseId:', caseId, 'file:', file.name);
    
    // For new cases, store images temporarily and upload after case is saved
    if (!caseId || caseId === 'new' || caseId.startsWith('new-')) {
        if (DEBUG) console.log('[IMAGE] New case detected - storing image as pending');
        // Store image in temporary storage for upload after case creation
        if (!window.pendingImages) {
            window.pendingImages = [];
        }
        window.pendingImages.push(file);
        if (DEBUG) console.log('[IMAGE] Pending images count:', window.pendingImages.length);
        
        // Show preview of pending image
        const container = document.getElementById('editImagesContainer');
        if (container) {
            const reader = new FileReader();
            reader.onload = function(e) {
                const imageCard = document.createElement('div');
                imageCard.className = 'col-md-3 mb-3';
                imageCard.innerHTML = `
                    <div class="card image-card" style="opacity: 0.7;">
                        <img src="${e.target.result}" class="card-img-top" style="height: 180px; object-fit: cover;">
                        <div class="card-body p-2">
                            <small class="text-muted d-block text-truncate" title="${file.name}">
                                📁 ${file.name}
                            </small>
                            <small class="text-warning d-block mt-1">
                                <i class="fas fa-clock me-1"></i>Pending upload (save case first)
                            </small>
                        </div>
                    </div>
                `;
                container.appendChild(imageCard);
            };
            reader.readAsDataURL(file);
        }
        
        // Clear input
        input.value = '';
        
        // Show message
        if (typeof showToast === 'function') {
            showToast('Image will be uploaded after you save the case', 'info');
        } else {
            alert('Image added. It will be uploaded after you save the case.');
        }
        return;
    }
    
    const uploadBtn = (typeof event !== 'undefined' && event && event.target) ? event.target : document.querySelector('button[onclick*="uploadImage"]');
    const originalText = uploadBtn ? uploadBtn.innerHTML : '';
    if (uploadBtn) {
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Uploading...';
    }

    function onUploadSuccess(data) {
        if (DEBUG) console.log('[IMAGE] Upload response:', data);
        if (data.image_id || data.success) {
            input.value = '';
            setTimeout(function() { reloadImages(caseId); }, 300);
            if (typeof showToast === 'function') {
                showToast('Image uploaded successfully!', 'success');
            } else {
                alert('Image uploaded successfully!');
            }
        } else {
            console.error('[IMAGE] Upload failed - no image_id or success flag:', data);
            alert('Error: ' + (data.error || 'Upload failed'));
        }
    }

    function onUploadError(error) {
        console.error('Error uploading image:', error);
        var errorMsg = (error && error.message) ? error.message : (error && error.error) ? error.error : (typeof error === 'string') ? error : 'Unknown error occurred';
        if (errorMsg.indexOf('413') !== -1 || errorMsg.indexOf('too large') !== -1) {
            errorMsg = 'Image too large for server upload (limit ~4.5 MB). Try compressing or resizing the image, or ask an admin to enable direct Cloudinary upload.';
        }
        console.error('Full error object:', error);
        alert('Error uploading image: ' + errorMsg);
    }

    function doServerUpload() {
        // Compress image before server upload to stay under Vercel's ~4.5MB body limit
        return compressImage(file, 2048, 3.5).then(function(compressedFile) {
            var formData = new FormData();
            formData.append('image', compressedFile);
            return fetch('/api/case/' + caseId + '/image', { method: 'POST', body: formData, credentials: 'same-origin' })
                .then(async function(r) {
                    if (!r.ok) {
                        var errorMessage = r.statusText;
                        try {
                            var errorData = await r.json();
                            errorMessage = errorData.error || errorMessage;
                        } catch (e) {
                            if (r.status === 403) errorMessage = 'Access denied. Please ensure you have permission to edit this case.';
                            else if (r.status === 401) errorMessage = 'Unauthorized. Please log in again.';
                            else if (r.status === 500) errorMessage = 'Server error. Please try again or contact support.';
                        }
                        throw new Error(errorMessage);
                    }
                    var contentType = r.headers.get('content-type');
                    if (!contentType || contentType.indexOf('application/json') === -1) {
                        throw new Error('Server returned non-JSON response. Please try again.');
                    }
                    return r.json();
                });
        });
    }

    function doDirectUpload() {
        return uploadFileToCloudinary(file).then(function(result) {
            var cloudName = window.CLOUDINARY_CLOUD_NAME;
            var thumbUrl = 'https://res.cloudinary.com/' + cloudName + '/image/upload/w_200,h_200,c_fill/' + result.public_id;
            return fetch('/api/case/' + caseId + '/image-url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image_url: result.secure_url,
                    image_public_id: result.public_id,
                    thumbnail_url: thumbUrl,
                    filename: file.name || 'image.jpg',
                    description: '',
                    image_type: file.type || 'image/jpeg'
                }),
                credentials: 'same-origin'
            });
        }).then(async function(r) {
            if (!r.ok) {
                var errData = await r.json().catch(function() { return {}; });
                throw new Error((errData && errData.error) ? errData.error : r.statusText);
            }
            return r.json();
        });
    }

    var useDirect = window.CLOUDINARY_CLOUD_NAME && window.CLOUDINARY_UPLOAD_PRESET;
    var uploadPromise = useDirect
        ? doDirectUpload().catch(function(err) {
            console.warn('[IMAGE] Direct upload failed, falling back to server upload:', err);
            return doServerUpload();
        })
        : doServerUpload();

    uploadPromise
        .then(onUploadSuccess)
        .catch(onUploadError)
        .finally(function() {
            if (uploadBtn) {
                uploadBtn.disabled = false;
                uploadBtn.innerHTML = originalText;
            }
        });
}

/**
 * Remove AI-generated wrapper divs from HTML content.
 * This is used when saving to remove AI watermarks if case is published.
 * @param {string} html - HTML content with potential data-ai-generated="true" wrapper divs
 * @returns {string} - HTML with wrapper divs removed (content preserved)
 */
function stripAiGeneratedWrappers(html) {
    if (!html) return html;
    
    // Use regex to remove wrapper divs: <div data-ai-generated="true" class="ai-generated-wrapper">content</div>
    // This preserves the inner content while removing the wrapper
    let cleaned = html;
    
    // Match wrapper divs (handles both single-line and multi-line)
    const wrapperPattern = /<div\s+data-ai-generated=["']true["'][^>]*class=["'][^"']*ai-generated-wrapper[^"']*["'][^>]*>(.*?)<\/div>/gis;
    
    // Replace wrapper divs with their inner content
    cleaned = cleaned.replace(wrapperPattern, '$1');
    
    // Also handle cases where class might be in different order
    const wrapperPattern2 = /<div\s+class=["'][^"']*ai-generated-wrapper[^"']*["'][^>]*data-ai-generated=["']true["'][^>]*>(.*?)<\/div>/gis;
    cleaned = cleaned.replace(wrapperPattern2, '$1');
    
    return cleaned;
}

// Save all changes - improved with validation and error handling
function saveEditedCase(event) {
    // Prevent any form submission
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    const caseIdField = document.getElementById('editCaseId').value;
    const caseNumber = document.getElementById('editCaseNumber').value.trim();
    const diagnosis = document.getElementById('editCaseDiagnosis').value.trim();
    
    // Get discussion from TinyMCE or fallback to textarea
    let discussion = '';
    if (typeof tinymce !== 'undefined' && tinymce.get('editCaseDiscussion')) {
        discussion = tinymce.get('editCaseDiscussion').getContent().trim();
        // Guard: if TinyMCE returns empty but textarea has content, use textarea
        if (!discussion) {
            const fallback = document.getElementById('editCaseDiscussion').value.trim();
            if (fallback) {
                discussion = fallback;
            }
        }
    } else {
        discussion = document.getElementById('editCaseDiscussion').value.trim();
    }
    
    // Get RadInsights fields
    const module = document.getElementById('editCaseModule')?.value || null;
    const bodyPart = document.getElementById('editCaseBodyPart')?.value || null;
    const ageGroup = document.getElementById('editCaseAgeGroup')?.value || null;
    const calculatorSlug = document.getElementById('editCaseCalculator')?.value || null;
    const status = document.getElementById('editCaseStatus')?.value || 'DRAFT';
    // Automatically set is_public based on status: PUBLISHED = true, all others = false
    const isPublic = status === 'PUBLISHED';
    const isPublished = status === 'PUBLISHED';
    
    // Watermark preservation logic:
    // - If published OR public: strip watermarks
    // - Otherwise: preserve watermarks
    if (isPublished || isPublic) {
        discussion = stripAiGeneratedWrappers(discussion);
    }
    
    // Validate required fields (case_number is optional - auto-generated from body_part)
    if (!module) {
        alert('Module is required');
        document.getElementById('editCaseModule')?.focus();
        return;
    }
    if (!bodyPart) {
        alert('Body Part is required');
        document.getElementById('editCaseBodyPart')?.focus();
        return;
    }
    if (!diagnosis) {
        alert('Diagnosis is required');
        return;
    }
    
    // Collect all Q&A pairs (only those with content)
    const pairs = [];
    document.querySelectorAll('.qa-pair-row').forEach((row, index) => {
        // Check if this is an AI-generated pair
        const isAiGenerated = row.classList.contains('ai-generated-pair');
        
        // Get question text from TinyMCE or textarea
        let questionText = '';
        const questionField = row.querySelector('.qa-question-text');
        if (questionField.id && typeof tinymce !== 'undefined' && tinymce.get(questionField.id)) {
            questionText = tinymce.get(questionField.id).getContent().trim();
        } else {
            questionText = questionField.value.trim();
        }
        
        // Get answer text from TinyMCE or textarea
        let answerText = '';
        const answerField = row.querySelector('.qa-answer-text');
        if (answerField.id && typeof tinymce !== 'undefined' && tinymce.get(answerField.id)) {
            answerText = tinymce.get(answerField.id).getContent().trim();
        } else {
            answerText = answerField.value.trim();
        }
        
        // Strip AI-generated wrapper divs from question and answer text only if published/public
        if (isPublished || isPublic) {
            questionText = stripAiGeneratedWrappers(questionText);
            answerText = stripAiGeneratedWrappers(answerText);
        }
        // If not published, wrapper divs are preserved (they provide visual distinction)
        
        // Only add pairs that have at least a question or answer
        if (questionText || answerText) {
            pairs.push({
                question_text: questionText,
                answer_text: answerText,
                is_ai_generated: isAiGenerated && !isPublished && !isPublic  // Store flag for view mode
            });
        }
    });
    
    // Check if this is a staging case
    const isStagingCase = caseIdField && caseIdField.toString().startsWith('staging-');
    const stagingId = isStagingCase ? caseIdField.toString().replace('staging-', '') : null;
    
    // Prepare data payload (case_number can be empty - server will auto-generate from body_part)
    const payload = {
        case_number: caseNumber || null,
        diagnosis: diagnosis,
        discussion: discussion || null,
        module: module,
        body_part: bodyPart,
        age_group: ageGroup,
        calculator_slug: calculatorSlug,
        status: status,
        is_public: isPublic,  // Syncs with status: PUBLISHED = true
        pairs: pairs
    };
    
    // Show loading state
    // Get the save button - handle both event.target and direct button lookup
    const saveBtn = (event && event.target) || document.querySelector('button[onclick*="saveEditedCase"]') || document.querySelector('button:has(i.fa-save)');
    if (!saveBtn) {
        console.error('Save button not found');
        return;
    }
    const originalText = saveBtn.innerHTML;
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Saving...';
    
    // Get return_to parameter from URL if present
    const params = new URLSearchParams(window.location.search);
    const returnTo = params.get('returnTo');
    const urlIsNew = params.get('new') === 'true';
    
    // Check if this is a new case - either from URL parameter OR caseIdField is 'new' or starts with 'new-'
    const isNew = urlIsNew || !caseIdField || caseIdField === 'new' || caseIdField.toString().startsWith('new-');
    
    if (DEBUG) console.log('[SAVE] Case state check - caseIdField:', caseIdField, 'urlIsNew:', urlIsNew, 'isNew:', isNew);
    
    // Determine endpoint and method
    let endpoint = '';
    let method = '';
    
    if (isStagingCase && stagingId) {
        // Updating staging case and promoting to production
        endpoint = `/api/admin/enrichment/${stagingId}/enrich-and-promote`;
        method = 'PUT';
    } else if (isNew) {
        // Creating new case (with or without packet)
        endpoint = '/api/case/create';
        method = 'POST';
    } else if (caseIdField && !caseIdField.startsWith('new')) {
        // Editing existing case
        endpoint = `/api/case/${caseIdField}`;
        method = 'PUT';
    } else {
        alert('Error: Invalid case state');
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalText;
        return;
    }
    
    // Send request to server
    if (DEBUG) console.log('[SAVE] Sending request to:', endpoint, 'Method:', method, 'Payload:', payload);
    
    fetch(endpoint, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(async r => {
        const responseText = await r.text();
        if (DEBUG) console.log('[SAVE] Response status:', r.status, 'Response:', responseText);
        
        let responseData;
        try {
            responseData = JSON.parse(responseText);
        } catch (e) {
            responseData = { error: responseText || 'Unknown error' };
        }
        
        // Handle duplicate detection (409 Conflict)
        if (r.status === 409 && responseData.duplicate) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = originalText;
            
            // Show duplicate handling modal
            showDuplicateHandlingModal(responseData, diagnosis, payload, endpoint, method, saveBtn, originalText);
            // Return a rejected promise to stop the chain
            return Promise.reject(new Error('DUPLICATE_DETECTED'));
        }
        
        if (!r.ok) {
            let errorMsg = `HTTP ${r.status}`;
            if (responseData.error) {
                errorMsg = responseData.error;
            } else if (responseData.message) {
                errorMsg = responseData.message;
            }
            throw new Error(errorMsg);
        }
        
        return responseData;
    })
    .then(data => {
        // Skip if data is undefined (shouldn't happen, but safety check)
        if (!data) {
            console.warn('[SAVE] No data received, skipping success handler');
            return;
        }
        
        if (DEBUG) console.log('[SAVE] Parsed response data:', data);
        
        if (data.success || data.id || data.case_id) {
            if (DEBUG) console.log('[SAVE] Case save successful. isNew:', isNew, 'data:', data);
            if (DEBUG) console.log('[SAVE] window.pendingImages:', window.pendingImages ? window.pendingImages.length : 'undefined');
            
            // If this was a new case, update the caseId field and upload pending images
            if (isNew && (data.id || data.case_id)) {
                const newCaseId = data.id || data.case_id;
                document.getElementById('editCaseId').value = newCaseId;
                if (DEBUG) console.log('[SAVE] Updated caseId to:', newCaseId, 'for image uploads');
                
                // Upload any pending images that were added before saving
                const pendingCount = window.pendingImages ? window.pendingImages.length : 0;
                if (DEBUG) console.log('[SAVE] Checking for pending images. Count:', pendingCount);
                
                // Set uploadsInProgress flag EARLY if we have pending images
                // This must be set before any redirect logic runs
                if (window.pendingImages && window.pendingImages.length > 0) {
                    window.uploadsInProgress = true;
                    if (DEBUG) console.log('[SAVE] Set uploadsInProgress flag to true (early)');
                }
                
                if (window.pendingImages && window.pendingImages.length > 0) {
                    if (DEBUG) console.log('[SAVE] Uploading', window.pendingImages.length, 'pending images for case', newCaseId);
                    // Flag already set above, just copy array
                    const pendingImages = [...window.pendingImages]; // Copy array
                    // Don't clear window.pendingImages yet - we need it for the redirect check
                    
                    // Wait a moment after case creation to ensure case is fully committed
                    if (DEBUG) console.log('[SAVE] Waiting 500ms before starting image uploads...');
                    setTimeout(() => {
                        // Upload all images and wait for them to complete before redirecting
                        const uploadPromises = pendingImages.map((file, index) => {
                            return new Promise((resolve, reject) => {
                                setTimeout(() => {
                                    // Verify file is still valid
                                    if (!file) {
                                        console.error('[SAVE] File is null or undefined');
                                        reject(new Error('File object is missing'));
                                        return;
                                    }
                                    
                                    // Check if file is a File or Blob
                                    const isFile = file instanceof File;
                                    const isBlob = file instanceof Blob;
                                    
                                    if (!isFile && !isBlob) {
                                        console.error('[SAVE] Invalid file object type:', typeof file, file);
                                        reject(new Error('File object is invalid or corrupted'));
                                        return;
                                    }
                                    
                                    // Check file size
                                    if (file.size === 0) {
                                        console.error('[SAVE] File is empty:', file.name);
                                        reject(new Error('File is empty'));
                                        return;
                                    }
                                    
                                    const controller = new AbortController();
                                    const timeoutId = setTimeout(() => controller.abort(), 30000);
                                    if (DEBUG) console.log('[SAVE] Uploading pending image:', file.name, 'size:', file.size, 'type:', file.type, 'isFile:', isFile, 'isBlob:', isBlob, 'to case', newCaseId);
                                    
                                    // Direct Cloudinary upload when configured (avoids 413 for large files)
                                    if (window.CLOUDINARY_CLOUD_NAME && window.CLOUDINARY_UPLOAD_PRESET) {
                                        uploadFileToCloudinary(file).then(function(result) {
                                            var cloudName = window.CLOUDINARY_CLOUD_NAME;
                                            var thumbUrl = 'https://res.cloudinary.com/' + cloudName + '/image/upload/w_200,h_200,c_fill/' + result.public_id;
                                            return fetch('/api/case/' + newCaseId + '/image-url', {
                                                method: 'POST',
                                                headers: { 'Content-Type': 'application/json' },
                                                body: JSON.stringify({
                                                    image_url: result.secure_url,
                                                    image_public_id: result.public_id,
                                                    thumbnail_url: thumbUrl,
                                                    filename: file.name || 'image.jpg',
                                                    description: '',
                                                    image_type: file.type || 'image/jpeg'
                                                }),
                                                credentials: 'same-origin'
                                            });
                                        }).then(function(r) {
                                            if (!r.ok) return r.json().then(function(d) { throw new Error(d.error || r.statusText); });
                                            return r.json();
                                        }).then(function(data) {
                                            clearTimeout(timeoutId);
                                            if (DEBUG) console.log('[SAVE] Pending image uploaded successfully (direct):', file.name, data);
                                            var idx = window.pendingImages.indexOf(file);
                                            if (idx > -1) window.pendingImages.splice(idx, 1);
                                            resolve(data);
                                        }).catch(function(err) {
                                            clearTimeout(timeoutId);
                                            console.error('[SAVE] Direct upload failed for pending image:', file.name, err);
                                            reject(err);
                                        });
                                        return;
                                    }
                                    
                                    const formData = new FormData();
                                    formData.append('image', file, file.name || 'image.jpg');
                                    
                                    // Retry logic for network errors
                                    let retryCount = 0;
                                    const maxRetries = 2;
                                    
                                    function attemptUpload() {
                                        if (DEBUG) console.log('[SAVE] Starting fetch request for ' + file.name + ' to /api/case/' + newCaseId + '/image');
                                        fetch('/api/case/' + newCaseId + '/image', {
                                            method: 'POST',
                                            body: formData,
                                            credentials: 'same-origin', // Ensure cookies are sent
                                            signal: controller.signal,
                                            headers: {
                                                // Don't set Content-Type - let browser set it with boundary for FormData
                                            }
                                        })
                                        .then(async r => {
                                            if (DEBUG) console.log('[SAVE] Upload response status:', r.status, 'for', file.name);
                                            if (!r.ok) {
                                                let errorMessage = r.statusText;
                                                try {
                                                    const errorData = await r.json();
                                                    errorMessage = errorData.error || errorMessage;
                                                    console.error('[SAVE] Upload error response:', errorData);
                                                } catch (e) {
                                                    // Not JSON, try to get text
                                                    try {
                                                        const errorText = await r.text();
                                                        errorMessage = errorText || errorMessage;
                                                    } catch (e2) {
                                                        // Can't read response
                                                    }
                                                }
                                                throw new Error(`Upload failed (${r.status}): ${errorMessage}`);
                                            }
                                            const contentType = r.headers.get('content-type');
                                            if (!contentType || !contentType.includes('application/json')) {
                                                const responseText = await r.text();
                                                console.warn('[SAVE] Non-JSON response:', responseText.substring(0, 100));
                                                throw new Error('Server returned non-JSON response');
                                            }
        return r.json();
    })
    .then(data => {
                                            clearTimeout(timeoutId);
                                            if (DEBUG) console.log('[SAVE] Pending image uploaded successfully:', file.name, data);
                                            // Clear the pending image from the array after successful upload
                                            const index = window.pendingImages.indexOf(file);
                                            if (index > -1) {
                                                window.pendingImages.splice(index, 1);
                                            }
                                            resolve(data);
                                        })
                                        .catch(error => {
                                            clearTimeout(timeoutId);
                                            console.error('[SAVE] Error uploading pending image (attempt ' + (retryCount + 1) + '):', file.name, error);
                                            
                                            // Retry on network errors
                                            if ((error.message.includes('Load failed') || error.message.includes('Failed to fetch') || error.name === 'TypeError') && retryCount < maxRetries) {
                                                retryCount++;
                                                if (DEBUG) console.log('[SAVE] Retrying upload for', file.name, '- attempt', retryCount + 1);
                                                setTimeout(() => {
                                                    attemptUpload();
                                                }, 1000 * retryCount); // Exponential backoff
                                                return;
                                            }
                                            
                                            console.error('[SAVE] Error details:', {
                                                name: error.name,
                                                message: error.message,
                                                stack: error.stack
                                            });
                                            
                                            // Provide more specific error message
                                            let errorMsg = error.message;
                                            if (error.name === 'AbortError') {
                                                errorMsg = 'Upload timeout - file may be too large or network is slow';
                                            } else if (error.message.includes('Load failed') || error.message.includes('Failed to fetch')) {
                                                errorMsg = 'Network error - please check your connection and try again';
                                            }
                                            
                                            reject(new Error(errorMsg));
                                        });
                                    }
                                    
                                    attemptUpload();
                                }, index * 500); // Stagger uploads more (500ms between each)
                            });
                        });
                        
                        // Wait for all uploads to complete before showing success message or redirecting
                        Promise.all(uploadPromises)
                        .then(results => {
                            if (DEBUG) console.log('[SAVE] All pending images uploaded successfully:', results);
                            
                            // Clear the pending images array and upload flag
                            window.pendingImages = [];
                            window.uploadsInProgress = false;
                            
                            // Show success message
                            if (isStagingCase) {
                                alert('Case reviewed and promoted to production successfully!');
                            } else {
                                alert('Case saved successfully! Images uploaded.');
                            }
                            
                            // Wait a moment to ensure database commits are fully processed
                            // This prevents the view case page from loading before images are available
                            setTimeout(() => {
                                // Redirect if there's a pending redirect URL
                                if (window.pendingRedirectUrl) {
                                    if (DEBUG) console.log('[SAVE] Redirecting to:', window.pendingRedirectUrl);
                                    const redirectUrl = window.pendingRedirectUrl;
                                    window.pendingRedirectUrl = null;
                                    // Add timestamp to force fresh load
                                    window.location.href = redirectUrl + (redirectUrl.includes('?') ? '&' : '?') + '_t=' + Date.now();
                                } else {
                                    // Default: redirect to view the new case with timestamp to force fresh load
                                    if (DEBUG) console.log('[SAVE] Redirecting to view case:', newCaseId);
                                    window.location.href = `/view-case/${newCaseId}?_t=${Date.now()}`;
                                }
                            }, 1000); // Wait 1 second for database to fully commit
                        })
                        .catch(error => {
                            console.error('[SAVE] Some pending images failed to upload:', error);
                            // Clear the upload flag even on error
                            window.uploadsInProgress = false;
                            const errorMsg = error.message || error.toString();
                            alert(`Case saved, but some images failed to upload: ${errorMsg}\n\nPlease try uploading them again from the edit case page.`);
                            // Still redirect to view case so user can edit and upload images
                            if (window.pendingRedirectUrl) {
                                window.location.href = window.pendingRedirectUrl;
                            } else {
                                window.location.href = `/view-case/${newCaseId}`;
                            }
                        });
                    }, 500); // Wait 500ms after case creation before starting uploads
                } else {
                    if (DEBUG) console.log('[SAVE] No pending images to upload. window.pendingImages:', window.pendingImages);
                    if (DEBUG) console.log('[SAVE] isNew:', isNew, 'newCaseId:', data.id || data.case_id);
                }
            } else {
                if (DEBUG) console.log('[SAVE] Not a new case or no case ID. isNew:', isNew, 'case_id:', data.id || data.case_id);
                if (DEBUG) console.log('[SAVE] caseIdField:', caseIdField);
            }
            
            // Determine redirect destination
            let redirectUrl = '/dashboard';
            
            // For new cases with pending images, don't show alert or redirect immediately
            // Check both pendingImages array and uploadsInProgress flag
            const hasPendingImages = window.pendingImages && window.pendingImages.length > 0;
            const uploadsInProgress = window.uploadsInProgress === true;
            const shouldWaitForImages = isNew && (hasPendingImages || uploadsInProgress);
            
            if (DEBUG) console.log('[SAVE] Redirect check - hasPendingImages:', hasPendingImages, 'uploadsInProgress:', uploadsInProgress, 'shouldWaitForImages:', shouldWaitForImages);
            
            if (!shouldWaitForImages) {
                if (isStagingCase) {
                    alert('Case reviewed and promoted to production successfully!');
                } else if (isNew) {
                    alert('Case saved successfully! You can now link an Image Stack if needed.');
                } else {
                    alert('Case saved successfully!');
                }
            } else {
                if (DEBUG) console.log('[SAVE] Deferring alert and redirect - waiting for pending images to upload');
            }
            
            // Priority: For staging cases, always go to view case (ignore returnTo if it's staging list)
            if (isStagingCase) {
                // Redirect to the promoted case view with from_staging parameter
                // Try multiple possible field names from the response
                const promotedId = data.case_id || data.id || data.promoted_case_id;
                if (DEBUG) console.log('[SAVE] Staging case - promoted ID:', promotedId, 'from data:', data);
                if (promotedId) {
                    redirectUrl = `/view-case/${promotedId}?from_staging=true`;
                } else {
                    console.warn('[SAVE] No promoted case ID found in response, redirecting to staging list');
                    redirectUrl = '/admin/staging-cases';
                }
            } else if (returnTo && !returnTo.includes('staging-cases')) {
                // Only use returnTo if it's not staging cases
                redirectUrl = returnTo;
            } else if (isNew) {
                const newId = data.id || data.case_id;
                if (newId) {
                    redirectUrl = `/edit-case?id=${newId}`;
            } else {
                    redirectUrl = '/cases';
                }
            } else if (caseIdField && !caseIdField.toString().startsWith('staging-') && !caseIdField.toString().startsWith('new')) {
                redirectUrl = `/view-case/${caseIdField}`;
            } else {
                // Default fallback
                redirectUrl = '/cases';
            }
            
            // Only redirect if we're not waiting for pending images
            if (!shouldWaitForImages) {
                if (DEBUG) console.log('[SAVE] Redirecting to:', redirectUrl);
            window.location.href = redirectUrl;
        } else {
                if (DEBUG) console.log('[SAVE] Deferring redirect - waiting for pending images to upload');
                // Store redirect URL to use after images are uploaded
                window.pendingRedirectUrl = redirectUrl;
            }
        } else {
            const errorMsg = data.error || 'Failed to save case';
            console.error('[SAVE] Save failed:', data);
            alert('Error: ' + errorMsg);
            saveBtn.disabled = false;
            saveBtn.innerHTML = originalText;
        }
    })
    .catch(error => {
        // Don't show error alert for duplicate detection (handled by modal)
        if (error.message === 'DUPLICATE_DETECTED') {
            if (DEBUG) console.log('[SAVE] Duplicate detected, handled by modal');
            return;
        }
        
        console.error('[SAVE] Error saving case:', error);
        alert('Error saving case: ' + error.message);
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalText;
    });
}

// Show duplicate handling modal
function showDuplicateHandlingModal(duplicateData, currentDiagnosis, payload, endpoint, method, saveBtn, originalText) {
    const isExactMatch = duplicateData.exact_match;
    const existingCases = duplicateData.existing_cases || [];
    const firstExistingCase = existingCases[0] || {};
    
    // Create modal HTML with premium two-panel layout
    let modalHtml = `
        <div class="modal fade" id="duplicateModal" tabindex="-1" aria-labelledby="duplicateModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-dialog-centered duplicate-modal-dialog">
                <div class="modal-content duplicate-modal-content">
                    <div class="modal-header duplicate-modal-header ${isExactMatch ? 'duplicate-modal-header-danger' : 'duplicate-modal-header-warning'}">
                        <h5 class="modal-title duplicate-modal-title" id="duplicateModalLabel">
                            <i class="fas fa-exclamation-triangle me-2"></i>
                            ${isExactMatch ? 'Exact Duplicate Diagnosis Found' : 'Similar Diagnosis Found'}
                        </h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body duplicate-modal-body">
                        <div class="row g-4 duplicate-comparison-row">
                            <!-- Left Column: Existing Case -->
                            <div class="col-lg-6">
                                <div class="card duplicate-case-card duplicate-case-existing duplicate-top-card">
                                    <div class="card-header duplicate-case-header duplicate-case-header-existing">
                                        <h6 class="mb-0 duplicate-case-title">
                                            <i class="fas fa-database me-2"></i>Existing Saved Case
                                        </h6>
                                    </div>
                                    <div class="card-body duplicate-case-body">
                                        <div class="duplicate-case-field mb-3">
                                            <label class="duplicate-case-label">Case ID</label>
                                            <div class="duplicate-case-value duplicate-case-id">#${firstExistingCase.id || 'N/A'}</div>
                                        </div>
                                        <div class="duplicate-case-field mb-3">
                                            <label class="duplicate-case-label">Diagnosis</label>
                                            <div class="duplicate-case-value duplicate-case-diagnosis">${escapeHtml(firstExistingCase.diagnosis || 'N/A')}</div>
                                        </div>
                                        <div class="duplicate-case-field mb-3">
                                            <label class="duplicate-case-label">Module</label>
                                            <div class="duplicate-case-value">${escapeHtml(firstExistingCase.module || 'N/A')}</div>
                                        </div>
                                        <div class="duplicate-case-field mb-3">
                                            <label class="duplicate-case-label">Status</label>
                                            <div class="duplicate-case-value">
                                                <span class="badge duplicate-badge ${firstExistingCase.status === 'published' ? 'duplicate-badge-success' : 'duplicate-badge-secondary'}">
                                                    ${escapeHtml(firstExistingCase.status || 'N/A')}
                                                </span>
                                            </div>
                                        </div>
                                        <div class="duplicate-case-field mb-3">
                                            <label class="duplicate-case-label">Visibility</label>
                                            <div class="duplicate-case-value">
                                                ${firstExistingCase.is_public ? 
                                                    '<span class="badge duplicate-badge duplicate-badge-success">Public</span>' : 
                                                    '<span class="badge duplicate-badge duplicate-badge-secondary">Private</span>'}
                                            </div>
                                        </div>
                                        ${isExactMatch ? `
                                            <button type="button" class="btn duplicate-action-btn duplicate-btn-reject w-100 mt-3" onclick="rejectExistingCase(${firstExistingCase.id})">
                                                <i class="fas fa-times-circle me-2"></i>Reject This Case
                                            </button>
                                        ` : ''}
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Right Column: New Incoming Case -->
                            <div class="col-lg-6">
                                <div class="card duplicate-case-card duplicate-case-new duplicate-top-card">
                                    <div class="card-header duplicate-case-header duplicate-case-header-new">
                                        <h6 class="mb-0 duplicate-case-title">
                                            <i class="fas fa-file-import me-2"></i>New Incoming Case
                                        </h6>
                                    </div>
                                    <div class="card-body duplicate-case-body">
                                        <div class="duplicate-case-field mb-3">
                                            <label class="duplicate-case-label">Diagnosis</label>
                                            <div class="duplicate-case-value duplicate-case-diagnosis duplicate-case-diagnosis-new">${escapeHtml(currentDiagnosis || 'N/A')}</div>
                                        </div>
                                        <div class="duplicate-case-field mb-3">
                                            <label class="duplicate-case-label">Module</label>
                                            <div class="duplicate-case-value">${escapeHtml(payload.module || 'N/A')}</div>
                                        </div>
                                        <div class="duplicate-case-field mb-3">
                                            <label class="duplicate-case-label">Body Part</label>
                                            <div class="duplicate-case-value">${escapeHtml(payload.body_part || 'N/A')}</div>
                                        </div>
                                        <div class="duplicate-case-field mb-3">
                                            <label class="duplicate-case-label">Age Group</label>
                                            <div class="duplicate-case-value">${escapeHtml(payload.age_group || 'N/A')}</div>
                                        </div>
                                        ${isExactMatch ? `
                                            <button type="button" class="btn duplicate-action-btn duplicate-btn-reject-new w-100 mt-3" onclick="rejectNewCase()">
                                                <i class="fas fa-times-circle me-2"></i>Reject This Case
                                            </button>
                                        ` : ''}
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Bottom Row: Match Summary + Rename -->
                        <div class="row g-4 mt-4 duplicate-bottom-row">
                            <div class="col-lg-6">
                                <div class="card duplicate-case-card duplicate-summary-card h-100">
                                    <div class="card-body duplicate-case-body">
                                        <h6 class="duplicate-section-title mb-3">
                                            <i class="fas fa-shield-alt me-2"></i>${isExactMatch ? 'Exact Case Match' : 'Similar Case Match'}
                                        </h6>
                                        ${isExactMatch ? `
                                            <div class="alert alert-danger duplicate-alert mb-0" role="alert">
                                                <strong><i class="fas fa-exclamation-circle me-2"></i>Exact match detected!</strong> 
                                                You cannot save a case with an identical diagnosis. Please choose which case to reject, or change the diagnosis name.
                                            </div>
                                        ` : `
                                            <div class="alert alert-info duplicate-alert mb-0" role="alert">
                                                <strong><i class="fas fa-info-circle me-2"></i>Similar diagnosis detected.</strong> 
                                                These cases may be duplicates. Please review and decide which case to keep.
                                            </div>
                                        `}
                                    </div>
                                </div>
                            </div>
                            <div class="col-lg-6">
                                <div class="card duplicate-case-card duplicate-rename-card h-100">
                                    <div class="card-body duplicate-case-body">
                                        <h6 class="duplicate-section-title mb-3">
                                            <i class="fas fa-edit me-2"></i>Change Diagnosis Name
                                        </h6>
                                        <p class="duplicate-section-description mb-3">
                                            If you change the diagnosis name, the system will re-check for duplicates. 
                                            If the new name is unique, you can save normally.
                                        </p>
                                        <div class="row g-2">
                                            <div class="col-md-8">
                                                <input type="text" class="form-control form-control-lg duplicate-rename-input" id="newDiagnosisInput" 
                                                   value="${escapeHtml(currentDiagnosis)}" 
                                                   placeholder="Enter new diagnosis name">
                                            </div>
                                            <div class="col-md-4">
                                                <button type="button" class="btn duplicate-action-btn duplicate-btn-save w-100" onclick="saveWithNewDiagnosis()">
                                                    <i class="fas fa-save me-2"></i>Save with New Name
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer duplicate-modal-footer">
                        <button type="button" class="btn duplicate-action-btn duplicate-btn-cancel" data-bs-dismiss="modal">
                            <i class="fas fa-times me-2"></i>Cancel
                        </button>
                        ${!isExactMatch ? `
                            <button type="button" class="btn duplicate-action-btn duplicate-btn-override" onclick="overrideDuplicateCase()">
                                <i class="fas fa-exclamation-circle me-2"></i>Override & Save Anyway
                            </button>
                        ` : ''}
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal if any
    const existingModal = document.getElementById('duplicateModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Store context for modal actions
    window.duplicateModalContext = {
        payload: payload,
        endpoint: endpoint,
        method: method,
        saveBtn: saveBtn,
        originalText: originalText,
        existingCases: existingCases,
        isExactMatch: isExactMatch,
        currentDiagnosis: currentDiagnosis
    };
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('duplicateModal'));
    modal.show();
}

// Save with new diagnosis name
function saveWithNewDiagnosis() {
    const context = window.duplicateModalContext;
    if (!context) return;
    
    const newDiagnosis = document.getElementById('newDiagnosisInput').value.trim();
    if (!newDiagnosis) {
        alert('Please enter a new diagnosis name');
        return;
    }
    
    if (newDiagnosis.toLowerCase().trim() === context.currentDiagnosis.toLowerCase().trim()) {
        alert('Please enter a different diagnosis name');
        return;
    }
    
    // Update payload with new diagnosis (create copy to avoid mutating original)
    const updatedPayload = { ...context.payload };
    updatedPayload.diagnosis = newDiagnosis;
    
    // Close modal
    const modalElement = document.getElementById('duplicateModal');
    const modal = bootstrap.Modal.getInstance(modalElement);
    if (modal) modal.hide();
    
    // Retry save with new diagnosis - this will re-run duplicate detection on the server
    const saveBtn = context.saveBtn;
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Checking duplicates...';
    
    fetch(context.endpoint, {
        method: context.method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatedPayload)
    })
    .then(async r => {
        const responseText = await r.text();
        let responseData;
        try {
            responseData = JSON.parse(responseText);
        } catch (e) {
            responseData = { error: responseText || 'Unknown error' };
        }
        
        // Handle duplicate detection again (409 Conflict) - re-run check with new name
        if (r.status === 409 && responseData.duplicate) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = context.originalText;
            
            // Show duplicate handling modal again with new diagnosis
            showDuplicateHandlingModal(responseData, newDiagnosis, updatedPayload, context.endpoint, context.method, saveBtn, context.originalText);
            return Promise.reject(new Error('DUPLICATE_DETECTED'));
        }
        
        if (!r.ok) {
            throw new Error(responseData.error || responseData.message || `HTTP ${r.status}`);
        }
        
        return responseData;
    })
    .then(data => {
        if (data && (data.success || data.id || data.case_id)) {
            alert('Case saved successfully with new diagnosis name!');
            const promotedId = data.case_id || data.id || data.promoted_case_id;
            if (promotedId) {
                window.location.href = `/view-case/${promotedId}?from_staging=true`;
            } else {
                window.location.reload();
            }
        } else {
            throw new Error(data?.error || 'Failed to save case');
        }
    })
    .catch(error => {
        if (error.message === 'DUPLICATE_DETECTED') {
            // Already handled by modal
            return;
        }
        console.error('[SAVE] Error saving with new diagnosis:', error);
        alert('Error saving case: ' + error.message);
        saveBtn.disabled = false;
        saveBtn.innerHTML = context.originalText;
    });
}

// Override duplicate case (only for similar, not exact matches)
function overrideDuplicateCase() {
    const context = window.duplicateModalContext;
    if (!context || context.isExactMatch) {
        alert('Cannot override exact duplicates. Please change the diagnosis name.');
        return;
    }
    
    if (!confirm('Are you sure you want to override and save this case? This will create a new case even though similar cases exist.')) {
        return;
    }
    
    // Add override flag to payload
    context.payload.override_duplicate = true;
    
    // Close modal
    const modalElement = document.getElementById('duplicateModal');
    const modal = bootstrap.Modal.getInstance(modalElement);
    if (modal) modal.hide();
    
    // Retry save with override flag
    const saveBtn = context.saveBtn;
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Saving...';
    
    fetch(context.endpoint, {
        method: context.method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(context.payload)
    })
    .then(async r => {
        const responseText = await r.text();
        let responseData;
        try {
            responseData = JSON.parse(responseText);
        } catch (e) {
            responseData = { error: responseText || 'Unknown error' };
        }
        
        if (!r.ok) {
            throw new Error(responseData.error || responseData.message || `HTTP ${r.status}`);
        }
        
        return responseData;
    })
    .then(data => {
        if (data.success || data.id || data.case_id) {
            alert('Case saved successfully (override)!');
            const promotedId = data.case_id || data.id || data.promoted_case_id;
            if (promotedId) {
                window.location.href = `/view-case/${promotedId}?from_staging=true`;
            } else {
                window.location.reload();
            }
        } else {
            throw new Error(data.error || 'Failed to save case');
        }
    })
    .catch(error => {
        console.error('[SAVE] Error saving with override:', error);
        alert('Error saving case: ' + error.message);
        saveBtn.disabled = false;
        saveBtn.innerHTML = context.originalText;
    });
}

// Reject existing case (mark as rejected instead of deleting)
function rejectExistingCase(caseId) {
    if (!confirm('Are you sure you want to reject this existing case? It will be marked as rejected but can be recovered later.')) {
        return;
    }
    
    fetch(`/api/case/${caseId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            // Close modal first
            const modalElement = document.getElementById('duplicateModal');
            const modal = bootstrap.Modal.getInstance(modalElement);
            if (modal) modal.hide();
            
            // Show success message briefly, then retry
            const context = window.duplicateModalContext;
            if (context) {
                // Small delay to ensure database transaction is committed
                setTimeout(() => {
                    const saveBtn = context.saveBtn;
                    saveBtn.disabled = true;
                    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Saving...';
                    
                    fetch(context.endpoint, {
                        method: context.method,
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(context.payload)
                    })
                    .then(async r => {
                        const responseText = await r.text();
                        let responseData;
                        try {
                            responseData = JSON.parse(responseText);
                        } catch (e) {
                            responseData = { error: responseText || 'Unknown error' };
                        }
                        
                        // Check for duplicates again (in case there are multiple)
                        // Note: Rejected cases are now excluded from duplicate detection
                        if (r.status === 409 && responseData.duplicate) {
                            saveBtn.disabled = false;
                            saveBtn.innerHTML = context.originalText;
                            showDuplicateHandlingModal(responseData, context.currentDiagnosis, context.payload, context.endpoint, context.method, saveBtn, context.originalText);
                            return Promise.reject(new Error('DUPLICATE_DETECTED'));
                        }
                    
                    if (!r.ok) {
                        throw new Error(responseData.error || responseData.message || `HTTP ${r.status}`);
                    }
                    
                    return responseData;
                })
                .then(data => {
                    if (data && (data.success || data.id || data.case_id)) {
                        alert('Case saved successfully!');
                        const promotedId = data.case_id || data.id || data.promoted_case_id;
                        if (promotedId) {
                            window.location.href = `/view-case/${promotedId}?from_staging=true`;
                        } else {
                            window.location.reload();
                        }
                    } else {
                        throw new Error(data?.error || 'Failed to save case');
                    }
                })
                .catch(error => {
                    if (error.message === 'DUPLICATE_DETECTED') {
                        return; // Already handled by modal
                    }
                    console.error('[SAVE] Error saving after reject:', error);
                    alert('Error saving case: ' + error.message);
                    saveBtn.disabled = false;
                    saveBtn.innerHTML = context.originalText;
                });
                }, 500); // 500ms delay to ensure rejection is committed to database
            }
        } else {
            alert('Error rejecting case: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('[REJECT] Error rejecting case:', error);
        alert('Error rejecting case: ' + error.message);
    });
}

// Reject new incoming case (close modal and cancel save, or reject staging case)
function rejectNewCase() {
    if (!confirm('Are you sure you want to reject this new case? It will be marked as rejected and will not be saved.')) {
        return;
    }
    
    const context = window.duplicateModalContext;
    if (!context) {
        alert('Error: No context found');
        return;
    }
    
    // Check if this is a staging case by looking at the endpoint
    const isStagingCase = context.endpoint && context.endpoint.includes('/api/admin/enrichment/');
    let stagingId = null;
    
    if (isStagingCase) {
        // Extract staging ID from endpoint: /api/admin/enrichment/{id}/enrich-and-promote
        const match = context.endpoint.match(/\/api\/admin\/enrichment\/(\d+)\//);
        if (match) {
            stagingId = match[1];
        }
    }
    
    // If it's a staging case, call the reject endpoint
    if (isStagingCase && stagingId) {
        fetch(`/api/admin/enrichment/${stagingId}/reject`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: 'Rejected due to duplicate detection' })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                alert('Staging case rejected successfully. It has been marked as rejected.');
                // Close modal
                const modalElement = document.getElementById('duplicateModal');
                const modal = bootstrap.Modal.getInstance(modalElement);
                if (modal) modal.hide();
                
                // Reset save button
                context.saveBtn.disabled = false;
                context.saveBtn.innerHTML = context.originalText;
                
                // Redirect to staging cases list
                window.location.href = '/admin/staging-cases?status=rejected';
            } else {
                throw new Error(data.error || 'Failed to reject staging case');
            }
        })
        .catch(error => {
            console.error('[REJECT] Error rejecting staging case:', error);
            alert('Error rejecting staging case: ' + error.message);
        });
    } else {
        // Not a staging case - just close modal and cancel
        const modalElement = document.getElementById('duplicateModal');
        const modal = bootstrap.Modal.getInstance(modalElement);
        if (modal) modal.hide();
        
        // Reset save button
        context.saveBtn.disabled = false;
        context.saveBtn.innerHTML = context.originalText;
        
        alert('New case rejected. No changes were saved.');
    }
}

function appendDiscussionHtml(html) {
    if (!html) return;
    if (typeof tinymce !== 'undefined' && tinymce.get('editCaseDiscussion')) {
        const editor = tinymce.get('editCaseDiscussion');
        const existing = editor.getContent() || '';
        editor.setContent(existing + html);
        editor.save();
        return;
    }
    const discussionField = document.getElementById('editCaseDiscussion');
    if (discussionField) {
        const existing = discussionField.value || '';
        discussionField.value = existing + '\n' + html;
    }
}

/**
 * Check AI cache and show warning dialog if cached
 */
function checkAiCacheAndPrompt(caseId, model, diagnosis, btn) {
    // Check cache status
    fetch(`/api/case/${caseId}/ai-prelim/check-cache?model=${encodeURIComponent(model)}`)
        .then(async r => {
            const text = await r.text();
            let cacheData;
            try {
                cacheData = JSON.parse(text);
            } catch (e) {
                // If response is not JSON, it's likely an error page
                console.warn('Cache check returned non-JSON response, proceeding anyway');
                // Proceed with generation (don't block user)
                createPrelimCaseData(true);
                return;
            }
            return cacheData;
        })
        .then(cacheData => {
            if (!cacheData) return; // Already handled in previous then
            if (cacheData.cached && cacheData.cache_entry) {
                // Show warning dialog
                const modelName = cacheData.cache_entry.model_name || model;
                const allModels = cacheData.all_used_models || [];
                const allModelsUsed = allModels.length > 0;
                
                let message = `This diagnosis has already been generated using <strong style="color: #e96304;">${modelName}</strong>. `;
                if (allModelsUsed && allModels.length > 1) {
                    message += `All available AI models have already been used for this diagnosis. `;
                }
                message += `Do you want to regenerate the content using the same model, or cancel and choose another model?`;
                
                // Create modal dialog with app brand styling
                const modal = document.createElement('div');
                modal.className = 'modal fade show ai-cache-modal';
                modal.style.display = 'flex';
                modal.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
                modal.style.zIndex = '9999';
                modal.innerHTML = `
                    <div class="modal-dialog modal-dialog-centered" style="max-width: 600px; width: 90vw;">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">
                                    <i class="fas fa-exclamation-triangle"></i>
                                    AI Content Already Generated
                                </h5>
                                <button type="button" class="btn-close btn-close-white" onclick="this.closest('.modal').remove()" style="opacity: 0.8;"></button>
                            </div>
                            <div class="modal-body">
                                <div class="row g-3">
                                    <div class="col-auto">
                                        <div class="card border-0 shadow-sm" style="background-color: #f8f9fa; border-left: 4px solid #5E899E !important;">
                                            <div class="card-body p-3">
                                                <p class="card-text mb-0" style="color: #2c3e50; font-size: 1rem; line-height: 1.6;">${message}</p>
                                            </div>
                                        </div>
                                    </div>
                                    ${cacheData.cache_entry ? `
                                    <div class="col-auto">
                                        <div class="card border-0 shadow-sm" style="background-color: #f0f8fc; border-left: 4px solid #5E899E !important;">
                                            <div class="card-body p-3">
                                                <div style="font-size: 0.875rem; line-height: 1.6;">
                                                    <div style="margin-bottom: 0.5rem;">
                                                        <span class="info-label">First generated:</span> 
                                                        <span class="info-value" style="color: #e96304; font-weight: 500;">${new Date(cacheData.cache_entry.first_generated_at).toLocaleString()}</span>
                                                    </div>
                                                    <div>
                                                        <span class="info-label">Times queried:</span> 
                                                        <span class="info-value">${cacheData.cache_entry.query_count}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    ` : ''}
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-cancel" onclick="this.closest('.modal').remove()">
                                    Cancel
                                </button>
                                ${cacheData.has_stored_data ? `
                                <button type="button" class="btn btn-outline-primary" onclick="
                                    this.closest('.modal').remove();
                                    reloadPrelimCaseData();
                                ">
                                    <i class="fas fa-history me-1"></i>Reload Previous
                                </button>
                                ` : ''}
                                <button type="button" class="btn btn-regenerate" onclick="
                                    this.closest('.modal').remove();
                                    createPrelimCaseData(true);
                                ">
                                    <i class="fas fa-redo me-1"></i>Regenerate using ${modelName}
                                </button>
                            </div>
                        </div>
                    </div>
                `;
                document.body.appendChild(modal);

                // Close on backdrop click
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) {
                        modal.remove();
                    }
                });
            } else if (!cacheData.cached && cacheData.has_stored_data) {
                // Not cached but has stored data — offer reload or generate new
                const storedInfo = cacheData.stored_data_info || {};
                const storedDate = storedInfo.generated_at ? new Date(storedInfo.generated_at).toLocaleString() : 'unknown';
                const storedModel = storedInfo.model_name || 'unknown';

                const modal = document.createElement('div');
                modal.className = 'modal fade show ai-cache-modal';
                modal.style.display = 'flex';
                modal.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
                modal.style.zIndex = '9999';
                modal.innerHTML = `
                    <div class="modal-dialog modal-dialog-centered" style="max-width: 500px; width: 90vw;">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">
                                    <i class="fas fa-database"></i>
                                    Previous AI Data Available
                                </h5>
                                <button type="button" class="btn-close btn-close-white" onclick="this.closest('.modal').remove()" style="opacity: 0.8;"></button>
                            </div>
                            <div class="modal-body">
                                <div class="card border-0 shadow-sm" style="background-color: #f8f9fa; border-left: 4px solid #5E899E !important;">
                                    <div class="card-body p-3">
                                        <p class="card-text mb-2" style="color: #2c3e50; line-height: 1.6;">
                                            This case has previously generated AI data (${storedModel}, ${storedDate}).
                                        </p>
                                        <p class="card-text mb-0" style="color: #2c3e50; line-height: 1.6;">
                                            You can <strong>reload</strong> the stored data or <strong>generate new</strong> content.
                                        </p>
                                    </div>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-cancel" onclick="this.closest('.modal').remove()">Cancel</button>
                                <button type="button" class="btn btn-outline-primary" onclick="
                                    this.closest('.modal').remove();
                                    reloadPrelimCaseData();
                                ">
                                    <i class="fas fa-history me-1"></i>Reload Previous
                                </button>
                                <button type="button" class="btn btn-regenerate" onclick="
                                    this.closest('.modal').remove();
                                    createPrelimCaseData(true);
                                ">
                                    <i class="fas fa-wand-magic-sparkles me-1"></i>Generate New
                                </button>
                            </div>
                        </div>
                    </div>
                `;
                document.body.appendChild(modal);
                modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });
            } else {
                // Not cached and no stored data, proceed directly
                createPrelimCaseData(true);
            }
        })
        .catch(err => {
            console.error('Cache check failed:', err);
            // On error, proceed anyway (don't block user)
            createPrelimCaseData(true);
        });
}

function createPrelimCaseData(forceRegenerate = false) {
    const caseIdField = document.getElementById('editCaseId')?.value;
    const diagnosis = document.getElementById('editCaseDiagnosis')?.value.trim();

    // Read context from stored global (set by submitAiGenerate before modal close)
    // or fall back to DOM elements if they still exist
    const ctx = window._aiGenerateContext || {};
    const model = ctx.model || document.getElementById('aiModelSelect')?.value || 'claude-sonnet-4-6';
    const isOpus = model.includes('opus');
    const btn = document.getElementById('aiPrelimBtn');
    const cancelBtn = document.getElementById('aiCancelBtn');

    const isStagingCase = caseIdField && caseIdField.toString().startsWith('staging-');
    const isNew = !caseIdField || caseIdField === 'new' || caseIdField.toString().startsWith('new-');

    if (isNew || isStagingCase) {
        alert('Please save the case first before generating preliminary data.');
        return;
    }
    if (!diagnosis) {
        alert('Diagnosis is required to generate preliminary data.');
        return;
    }

    // Check cache first (unless forcing regenerate)
    if (!forceRegenerate) {
        checkAiCacheAndPrompt(caseIdField, model, diagnosis, btn);
        return;
    }

    // Proceed with generation (user confirmed regenerate)
    // Create abort controller for cancellation
    let abortController = new AbortController();
    window.aiGenerationAbortController = abortController;

    // Update button state
    if (btn) {
        btn.disabled = true;
        btn.dataset.originalText = btn.innerHTML;
        btn.innerHTML = `<i class="fas fa-spinner fa-spin me-1"></i>${isOpus ? 'Opus...' : 'Generating...'}`;
    }

    // Show and setup cancel button RIGHT BEFORE fetch starts
    if (cancelBtn) {
        cancelBtn.style.display = 'inline-block';
        cancelBtn.onclick = () => {
            abortController.abort();
            window.aiGenerationAbortController = null;
            // Reset button state
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = btn.dataset.originalText || '<i class="fas fa-wand-magic-sparkles me-2"></i>Create Preliminary Case Data';
            }
            // Hide cancel button
            cancelBtn.style.display = 'none';
            if (DEBUG) console.log('[AI PRELIM] Generation cancelled by user');
        };
    }

    // Use stored context from modal (or fall back to DOM)
    const aiInstructions = (ctx.instructions || document.getElementById('aiPrelimInstructions')?.value || '').trim();
    const aiRefUrls = ctx.refUrls && ctx.refUrls.length > 0 ? ctx.refUrls : [];
    const aiPdfFiles = ctx.pdfFiles && ctx.pdfFiles.length > 0 ? ctx.pdfFiles : [];

    // If no stored context, try DOM as fallback
    if (!ctx.refUrls) {
        document.querySelectorAll('#aiPrelimRefUrlList .ref-url-input').forEach(input => {
            const v = (input.value || '').trim();
            if (v) aiRefUrls.push(v);
        });
    }
    if (!ctx.pdfFiles) {
        const aiPdfInput = document.getElementById('aiPrelimPdf');
        if (aiPdfInput) aiPdfFiles.push(...Array.from(aiPdfInput.files));
    }

    let fetchOpts;
    if (aiPdfFiles.length > 0) {
        const fd = new FormData();
        fd.append('model', model);
        fd.append('force_regenerate', 'true');
        if (aiInstructions) fd.append('instructions', aiInstructions);
        aiRefUrls.forEach(u => fd.append('reference_url', u));
        aiPdfFiles.forEach(f => fd.append('pdf', f));
        fetchOpts = { method: 'POST', body: fd, signal: abortController.signal };
    } else {
        const payload = { model, force_regenerate: true };
        if (aiInstructions) payload.instructions = aiInstructions;
        if (aiRefUrls.length) payload.reference_urls = aiRefUrls;
        fetchOpts = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal: abortController.signal };
    }

    // Start fetch request
    fetch(`/api/case/${caseIdField}/ai-prelim`, fetchOpts)
    .then(async r => {
        const text = await r.text();
        let payload;
        try {
            payload = JSON.parse(text);
        } catch (e) {
            payload = { error: text || 'Unknown error' };
        }
        if (!r.ok) {
            throw new Error(payload.error || 'Failed to generate preliminary data.');
        }
        return payload;
    })
    .then(data => {
        const pairs = data.added_pairs || [];
        pairs.forEach(pair => {
            // Pass true for isAiGenerated to apply orange background styling
            addQAPairRow(pair.question || '', pair.answer || '', true);
        });
        if (data.discussion_html) {
            appendDiscussionHtml(data.discussion_html);
        }
        
        // AI content added - wrapper divs will be preserved unless case is published/public
        
        // Show success flash message with counts
        const pairsCount = data.pairs_count || pairs.length || 0;
        const discussionAppended = data.discussion_appended || false;
        
        let message = `✅ AI Generation Complete\n\n`;
        message += `Generated ${pairsCount} Q&A pair${pairsCount !== 1 ? 's' : ''}.`;
        if (discussionAppended) {
            message += ` Discussion appended.`;
        } else {
            message += ` No discussion content generated.`;
        }
        
        if (data.warnings && data.warnings.length) {
            message += `\n\n⚠️ Warnings: ${data.warnings.join('; ')}`;
        }
        
        // Show Bootstrap alert/toast
        showAiGenerationFlash(message, pairsCount, discussionAppended);
    })
    .catch(error => {
        // Don't show error if user cancelled
        if (error.name === 'AbortError') {
            if (DEBUG) console.log('[AI PRELIM] Generation cancelled by user');
            return;
        }
        console.error('[AI PRELIM] Error:', error);
        alert(error.message || 'Failed to generate preliminary case data.');
    })
    .finally(() => {
        // Always reset button state and hide cancel button
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = btn.dataset.originalText || '<i class="fas fa-wand-magic-sparkles me-2"></i>Create Preliminary Case Data';
        }
        if (cancelBtn) {
            cancelBtn.style.display = 'none';
        }
        window.aiGenerationAbortController = null;
    });
}

/**
 * Reload Q&A and discussion from stored AI response_payload (no new AI call).
 */
function reloadPrelimCaseData() {
    const caseIdField = document.getElementById('editCaseId')?.value;
    if (!caseIdField || caseIdField === 'new' || caseIdField.toString().startsWith('new-') || caseIdField.toString().startsWith('staging-')) {
        alert('Cannot reload: case must be saved first.');
        return;
    }
    if (!confirm('This will replace all current Q&A pairs and discussion with the previously generated AI data. Continue?')) {
        return;
    }

    const btn = document.getElementById('aiReloadBtn');
    if (btn) {
        btn.disabled = true;
        btn.dataset.originalText = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Reloading...';
    }

    fetch(`/api/case/${caseIdField}/ai-prelim/reload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
    })
    .then(async r => {
        const text = await r.text();
        let payload;
        try { payload = JSON.parse(text); } catch(e) { payload = { error: text || 'Unknown error' }; }
        if (!r.ok) throw new Error(payload.error || 'Failed to reload AI data.');
        return payload;
    })
    .then(data => {
        // Clear existing Q&A in DOM
        const container = document.getElementById('qaPairsContainer');
        if (container) container.innerHTML = '';

        // Clear discussion editor
        if (typeof tinymce !== 'undefined' && tinymce.get('editCaseDiscussion')) {
            tinymce.get('editCaseDiscussion').setContent('');
        } else {
            const ta = document.getElementById('editCaseDiscussion');
            if (ta) ta.value = '';
        }

        // Add Q&A pairs
        const pairs = data.added_pairs || [];
        pairs.forEach(pair => {
            addQAPairRow(pair.question || '', pair.answer || '', true);
        });

        // Append discussion
        if (data.discussion_html) {
            appendDiscussionHtml(data.discussion_html);
        }

        const pairsCount = data.pairs_count || pairs.length || 0;
        let message = `Reload Complete\n\nRestored ${pairsCount} Q&A pair${pairsCount !== 1 ? 's' : ''}.`;
        if (data.discussion_appended) message += ' Discussion restored.';
        if (data.originally_generated_at) {
            message += `\nOriginally generated: ${new Date(data.originally_generated_at).toLocaleString()}`;
        }
        showAiGenerationFlash(message, pairsCount, data.discussion_appended || false);
    })
    .catch(error => {
        console.error('[AI RELOAD] Error:', error);
        alert(error.message || 'Failed to reload AI data.');
    })
    .finally(() => {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = btn.dataset.originalText || '<i class="fas fa-redo me-1"></i>Reload Previous Data';
        }
    });
}

/**
 * Cancel AI generation
 * Always hides the cancel button, even if no active generation
 */
function cancelAiGeneration() {
    const cancelBtn = document.getElementById('aiCancelBtn');
    const btn = document.getElementById('aiPrelimBtn');
    
    // Always hide cancel button
    if (cancelBtn) {
        cancelBtn.style.display = 'none';
    }
    
    // If there's an active generation, abort it
    if (window.aiGenerationAbortController) {
        window.aiGenerationAbortController.abort();
        window.aiGenerationAbortController = null;
        
        // Reset button state
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = btn.dataset.originalText || '<i class="fas fa-wand-magic-sparkles me-2"></i>Create Preliminary Case Data';
        }
        
        if (DEBUG) console.log('[AI PRELIM] Generation cancelled by user');
    }
}


// Helper function to escape HTML
// escapeHtml() — duplicate removed; using definition at line ~662

/**
 * Show flash message for AI generation success
 * @param {string} message - Main message text
 * @param {number} pairsCount - Number of Q&A pairs generated
 * @param {boolean} discussionAppended - Whether discussion was appended
 */
function showAiGenerationFlash(message, pairsCount, discussionAppended) {
    // Create alert element
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-success alert-dismissible fade show';
    alertDiv.setAttribute('role', 'alert');
    alertDiv.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; min-width: 300px; max-width: 500px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);';
    
    alertDiv.innerHTML = `
        <div class="d-flex align-items-start">
            <i class="fas fa-check-circle me-2" style="font-size: 1.5rem; color: #198754;"></i>
            <div class="flex-grow-1">
                <h6 class="alert-heading mb-2" style="color: #198754; font-weight: 600;">
                    <i class="fas fa-robot me-1"></i>AI Generation Complete
                </h6>
                <div style="line-height: 1.6;">
                    <p class="mb-1"><strong>Generated ${pairsCount} Q&A pair${pairsCount !== 1 ? 's' : ''}.</strong></p>
                    <p class="mb-0">Discussion ${discussionAppended ? '<span class="text-success">appended</span>' : '<span class="text-muted">not generated</span>'}.</p>
                </div>
            </div>
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
    
    // Remove any existing alerts
    const existingAlert = document.querySelector('.alert.alert-success[role="alert"]');
    if (existingAlert) {
        existingAlert.remove();
    }
    
    // Append to body
    document.body.appendChild(alertDiv);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.classList.remove('show');
            setTimeout(() => alertDiv.remove(), 150);
        }
    }, 5000);
}

// Expose functions globally for use in edit_case.html
if (typeof window !== 'undefined') {
    window.saveEditedCase = saveEditedCase;
    window.addQAPairRow = addQAPairRow;
    window.populateImages = populateImages;
    window.populateQAPairs = populateQAPairs;
    window.addNewQAPair = addNewQAPair;
    window.removeQAPair = removeQAPair;
    window.uploadImage = uploadImage;
    window.editImageDescription = editImageDescription;
    window.saveImageDescription = saveImageDescription;
    window.deleteImage = deleteImage;
    window.viewImageFull = viewImageFull;
    window.initializeTinyMCE = initializeTinyMCE;
    window.createPrelimCaseData = createPrelimCaseData;
    window.reloadPrelimCaseData = reloadPrelimCaseData;
    window.stripAiGeneratedWrappers = stripAiGeneratedWrappers;
    window.cancelAiGeneration = cancelAiGeneration;
    window.showAiGenerationFlash = showAiGenerationFlash;
}
