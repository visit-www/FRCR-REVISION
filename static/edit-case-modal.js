/**
 * Case Edit Interface - Full-page editing experience
 * Handles: Case details, Q&A pairs, images with descriptions
 */

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
function addQAPairRow(questionText = '', answerText = '') {
    const container = document.getElementById('qaPairsContainer');
    const pairNum = container.querySelectorAll('.qa-pair-row').length + 1;
    const uniqueId = 'qa-answer-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    
    const row = document.createElement('div');
    row.className = 'qa-pair-row p-3 mb-3 border rounded bg-light';
    row.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-2">
            <h6 class="mb-0"><strong>Pair ${pairNum}</strong></h6>
            <button type="button" class="btn btn-sm btn-danger" onclick="removeQAPair(this)">
                <i class="fas fa-trash me-1"></i>Remove
            </button>
        </div>
        <div class="row g-2">
            <div class="col-md-6">
                <label class="form-label small text-info"><i class="fas fa-question-circle me-1"></i>Question</label>
                <textarea class="form-control qa-question-text" rows="4" placeholder="Enter question">${escapeHtml(questionText)}</textarea>
                <small class="text-muted d-block mt-1">Plain text question</small>
            </div>
            <div class="col-md-6">
                <label class="form-label small text-success"><i class="fas fa-edit me-1"></i>Answer (Rich Text)</label>
                <textarea class="form-control qa-answer-text qa-rich-editor" id="${uniqueId}" data-qa-answer="true" placeholder="Enter answer with optional formatting, tables, lists...">${escapeHtml(answerText)}</textarea>
                <small class="text-muted d-block mt-1">Supports tables, lists, formatting</small>
            </div>
        </div>
    `;
    
    container.appendChild(row);
    
    // Initialize TinyMCE for the answer field
    initializeTinyMCE(uniqueId);
}

// Initialize TinyMCE editor for a specific field
function initializeTinyMCE(elementId, retryCount = 0) {
    const MAX_RETRIES = 20; // Max 10 seconds of retries
    
    if (typeof tinymce === 'undefined' || !tinymce.init) {
        if (retryCount < MAX_RETRIES) {
            console.log(`TinyMCE not loaded yet for ${elementId}, retrying... (${retryCount + 1}/${MAX_RETRIES})`);
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
        console.log(`TinyMCE already initialized for ${elementId}`);
        return;
    }
    
    console.log(`Initializing TinyMCE for ${elementId}`);
    tinymce.init({
        selector: '#' + elementId,
        height: 300,
        menubar: false,
        toolbar: 'undo redo | blocks | bold italic underline strikethrough | numlist bullist indent outdent | table link image code removeformat',
        plugins: 'table link image code',
        // Use CDN for assets (themes, skins, etc.) since we only have the minified JS locally
        base_url: 'https://cdn.jsdelivr.net/npm/tinymce@6',
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
    console.log('[populateImages] Called with', images ? images.length : 0, 'images');
    const container = document.getElementById('editImagesContainer');
    if (!container) {
        console.error('[populateImages] Container editImagesContainer not found!');
        return;
    }
    container.innerHTML = '';
    
    if (!images || images.length === 0) {
        console.log('[populateImages] No images provided');
        container.innerHTML = '<p class="text-muted text-center py-3">No images uploaded yet</p>';
        return;
    }
    
    console.log('[populateImages] Processing', images.length, 'images');
    
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
                        <small class="text-secondary d-block" id="desc-${image.id}" style="min-height: 40px; word-wrap: break-word;">
                            ${imageDescription ? escapeHtml(imageDescription) : '<em class="text-muted">No description</em>'}
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
                content_css: 'default',
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
        
        console.log('Image description saved successfully');
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
    console.log('[IMAGE] Upload attempt - caseId:', caseId, 'file:', file.name);
    
    // For new cases, store images temporarily and upload after case is saved
    if (!caseId || caseId === 'new' || caseId.startsWith('new-')) {
        console.log('[IMAGE] New case detected - storing image as pending');
        // Store image in temporary storage for upload after case creation
        if (!window.pendingImages) {
            window.pendingImages = [];
        }
        window.pendingImages.push(file);
        console.log('[IMAGE] Pending images count:', window.pendingImages.length);
        
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
    
    const formData = new FormData();
    formData.append('image', file);
    
    // Show upload progress
    const uploadBtn = event.target;
    const originalText = uploadBtn.innerHTML;
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Uploading...';
    
    fetch(`/api/case/${caseId}/image`, {
        method: 'POST',
        body: formData
    })
    .then(async r => {
        // Check if response is OK and is JSON
        if (!r.ok) {
            // Try to parse error as JSON, otherwise use status text
            let errorMessage = r.statusText;
            try {
                const errorData = await r.json();
                errorMessage = errorData.error || errorMessage;
            } catch (e) {
                // Not JSON, use status text
                if (r.status === 403) {
                    errorMessage = 'Access denied. Please ensure you have permission to edit this case.';
                } else if (r.status === 401) {
                    errorMessage = 'Unauthorized. Please log in again.';
                } else if (r.status === 500) {
                    errorMessage = 'Server error. Please try again or contact support.';
                }
            }
            throw new Error(errorMessage);
        }
        
        // Check content type before parsing
        const contentType = r.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error('Server returned non-JSON response. Please try again.');
        }
        
        return r.json();
    })
    .then(data => {
        console.log('[IMAGE] Upload response:', data);
        if (data.image_id || data.success) {
            input.value = '';
            // Wait a moment before reloading to ensure database is updated
            setTimeout(() => {
                reloadImages(caseId);
            }, 300);
            // Show success message
            if (typeof showToast === 'function') {
                showToast('Image uploaded successfully!', 'success');
            } else {
                alert('Image uploaded successfully!');
            }
        } else {
            console.error('[IMAGE] Upload failed - no image_id or success flag:', data);
            alert('Error: ' + (data.error || 'Upload failed'));
        }
    })
    .catch(error => {
        console.error('Error uploading image:', error);
        let errorMsg = 'Unknown error occurred';
        
        if (error.message) {
            errorMsg = error.message;
        } else if (error.error) {
            errorMsg = error.error;
        } else if (typeof error === 'string') {
            errorMsg = error;
        }
        
        // Log full error for debugging
        console.error('Full error object:', error);
        
        alert('Error uploading image: ' + errorMsg);
    })
    .finally(() => {
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = originalText;
    });
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
    } else {
        discussion = document.getElementById('editCaseDiscussion').value.trim();
    }
    
    // Get FRCR Revision fields
    const module = document.getElementById('editCaseModule')?.value || null;
    const bodyPart = document.getElementById('editCaseBodyPart')?.value || null;
    const ageGroup = document.getElementById('editCaseAgeGroup')?.value || null;
    const status = document.getElementById('editCaseStatus')?.value || 'DRAFT';
    // Automatically set is_public based on status: PUBLISHED = true, all others = false
    const isPublic = status === 'PUBLISHED';
    
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
        const questionText = row.querySelector('.qa-question-text').value.trim();
        let answerText = '';
        
        // Get answer from TinyMCE editor if available
        const answerField = row.querySelector('.qa-answer-text');
        if (answerField.id && typeof tinymce !== 'undefined' && tinymce.get(answerField.id)) {
            answerText = tinymce.get(answerField.id).getContent().trim();
        } else {
            answerText = answerField.value.trim();
        }
        
        // Only add pairs that have at least a question or answer
        if (questionText || answerText) {
            pairs.push({
                question_text: questionText,
                answer_text: answerText
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
        status: status,
        is_public: isPublic,  // Legacy field, status takes precedence
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
    const isNew = params.get('new') === 'true';
    const packetId = params.get('packetId');
    
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
    console.log('[SAVE] Sending request to:', endpoint, 'Method:', method, 'Payload:', payload);
    
    fetch(endpoint, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(async r => {
        const responseText = await r.text();
        console.log('[SAVE] Response status:', r.status, 'Response:', responseText);
        
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
        
        console.log('[SAVE] Parsed response data:', data);
        
        if (data.success || data.id || data.case_id) {
            console.log('[SAVE] Case save successful. isNew:', isNew, 'data:', data);
            console.log('[SAVE] window.pendingImages:', window.pendingImages ? window.pendingImages.length : 'undefined');
            
            // If this was a new case, update the caseId field and upload pending images
            if (isNew && (data.id || data.case_id)) {
                const newCaseId = data.id || data.case_id;
                document.getElementById('editCaseId').value = newCaseId;
                console.log('[SAVE] Updated caseId to:', newCaseId, 'for image uploads');
                
                // Upload any pending images that were added before saving
                const pendingCount = window.pendingImages ? window.pendingImages.length : 0;
                console.log('[SAVE] Checking for pending images. Count:', pendingCount);
                
                if (window.pendingImages && window.pendingImages.length > 0) {
                    console.log('[SAVE] Uploading', window.pendingImages.length, 'pending images for case', newCaseId);
                    const pendingImages = [...window.pendingImages]; // Copy array
                    window.pendingImages = []; // Clear array
                    
                    // Upload all images and wait for them to complete before redirecting
                    const uploadPromises = pendingImages.map((file, index) => {
                        return new Promise((resolve, reject) => {
                            setTimeout(() => {
                                const formData = new FormData();
                                formData.append('image', file);
                                
                                console.log('[SAVE] Uploading pending image:', file.name, 'to case', newCaseId);
                                
                                fetch(`/api/case/${newCaseId}/image`, {
                                    method: 'POST',
                                    body: formData
                                })
                                .then(async r => {
                                    if (!r.ok) {
                                        let errorMessage = r.statusText;
                                        try {
                                            const errorData = await r.json();
                                            errorMessage = errorData.error || errorMessage;
                                        } catch (e) {
                                            // Not JSON
                                        }
                                        throw new Error(errorMessage);
                                    }
                                    const contentType = r.headers.get('content-type');
                                    if (!contentType || !contentType.includes('application/json')) {
                                        throw new Error('Server returned non-JSON response');
                                    }
                                    return r.json();
                                })
                                .then(data => {
                                    console.log('[SAVE] Pending image uploaded successfully:', file.name, data);
                                    resolve(data);
                                })
                                .catch(error => {
                                    console.error('[SAVE] Error uploading pending image:', file.name, error);
                                    reject(error);
                                });
                            }, index * 300); // Stagger uploads slightly
                        });
                    });
                    
                    // Wait for all uploads to complete before showing success message or redirecting
                    Promise.all(uploadPromises)
                        .then(results => {
                            console.log('[SAVE] All pending images uploaded successfully:', results);
                            
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
                                    console.log('[SAVE] Redirecting to:', window.pendingRedirectUrl);
                                    const redirectUrl = window.pendingRedirectUrl;
                                    window.pendingRedirectUrl = null;
                                    // Add timestamp to force fresh load
                                    window.location.href = redirectUrl + (redirectUrl.includes('?') ? '&' : '?') + '_t=' + Date.now();
                                } else {
                                    // Default: redirect to view the new case with timestamp to force fresh load
                                    console.log('[SAVE] Redirecting to view case:', newCaseId);
                                    window.location.href = `/view-case/${newCaseId}?_t=${Date.now()}`;
                                }
                            }, 1000); // Wait 1 second for database to fully commit
                        })
                        .catch(error => {
                            console.error('[SAVE] Some pending images failed to upload:', error);
                            alert('Case saved, but some images failed to upload. Please try uploading them again.');
                            // Still redirect to view case
                            if (window.pendingRedirectUrl) {
                                window.location.href = window.pendingRedirectUrl;
                            } else {
                                window.location.href = `/view-case/${newCaseId}`;
                            }
                        });
                } else {
                    console.log('[SAVE] No pending images to upload');
                }
            }
            
            // Determine redirect destination
            let redirectUrl = '/dashboard';
            
            // For new cases with pending images, don't show alert or redirect immediately
            const hasPendingImages = window.pendingImages && window.pendingImages.length > 0;
            const shouldWaitForImages = isNew && hasPendingImages;
            
            if (!shouldWaitForImages) {
                if (isStagingCase) {
                    alert('Case reviewed and promoted to production successfully!');
                } else {
                    alert('Case saved successfully!');
                }
            }
            
            // Priority: For staging cases, always go to view case (ignore returnTo if it's staging list)
            if (isStagingCase) {
                // Redirect to the promoted case view with from_staging parameter
                // Try multiple possible field names from the response
                const promotedId = data.case_id || data.id || data.promoted_case_id;
                console.log('[SAVE] Staging case - promoted ID:', promotedId, 'from data:', data);
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
                    redirectUrl = `/view-case/${newId}`;
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
                console.log('[SAVE] Redirecting to:', redirectUrl);
                window.location.href = redirectUrl;
            } else {
                console.log('[SAVE] Deferring redirect - waiting for pending images to upload');
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
            console.log('[SAVE] Duplicate detected, handled by modal');
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
                        ${isExactMatch ? `
                            <div class="alert alert-danger duplicate-alert mb-4" role="alert">
                                <strong><i class="fas fa-exclamation-circle me-2"></i>Exact match detected!</strong> 
                                You cannot save a case with an identical diagnosis. Please choose which case to reject, or change the diagnosis name.
                            </div>
                        ` : `
                            <div class="alert alert-info duplicate-alert mb-4" role="alert">
                                <strong><i class="fas fa-info-circle me-2"></i>Similar diagnosis detected.</strong> 
                                These cases may be duplicates. Please review and decide which case to keep.
                            </div>
                        `}
                        
                        <div class="row g-4 duplicate-comparison-row">
                            <!-- Left Column: Existing Case -->
                            <div class="col-lg-6">
                                <div class="card duplicate-case-card duplicate-case-existing h-100">
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
                                <div class="card duplicate-case-card duplicate-case-new h-100">
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
                        
                        <!-- Change Diagnosis Name Section -->
                        <div class="duplicate-rename-section mt-5 pt-4">
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

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Expose saveEditedCase globally for onclick handlers
if (typeof window !== 'undefined') {
    window.saveEditedCase = saveEditedCase;
}
