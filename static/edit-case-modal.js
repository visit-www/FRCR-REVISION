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
    
    // Update header info
    const headerInfo = document.getElementById('editCaseHeaderInfo');
    if (headerInfo) {
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

// Add Q&A pair row (new or existing)
function addQAPairRow(questionText = '', answerText = '') {
    const container = document.getElementById('qaPairsContainer');
    const pairNum = container.querySelectorAll('.qa-pair-row').length + 1;
    
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
                <label class="form-label small text-info">Question</label>
                <textarea class="form-control qa-question-text" rows="4" placeholder="Enter question">${escapeHtml(questionText)}</textarea>
            </div>
            <div class="col-md-6">
                <label class="form-label small text-success">Answer</label>
                <textarea class="form-control qa-answer-text" rows="4" placeholder="Enter answer">${escapeHtml(answerText)}</textarea>
            </div>
        </div>
    `;
    
    container.appendChild(row);
}

// Remove Q&A pair row
function removeQAPair(button) {
    button.closest('.qa-pair-row').remove();
}

// Add new Q&A pair
function addNewQAPair() {
    addQAPairRow();
}

// Populate images with improved UI
function populateImages(images) {
    const container = document.getElementById('editImagesContainer');
    container.innerHTML = '';
    
    if (!images || images.length === 0) {
        container.innerHTML = '<p class="text-muted text-center py-3">No images uploaded yet</p>';
        return;
    }
    
    const grid = document.createElement('div');
    grid.className = 'row g-3';
    
    images.forEach(image => {
        const col = document.createElement('div');
        col.className = 'col-md-4';
        col.id = `image-card-${image.id}`;
        
        col.innerHTML = `
            <div class="card image-card h-100 shadow-sm">
                <img src="/api/case-image/${image.id}" alt="${escapeHtml(image.filename)}" 
                     class="card-img-top" style="height: 180px; object-fit: cover; cursor: pointer;"
                     onclick="viewImageFull('${image.id}')" title="Click to view full size">
                <div class="card-body p-3">
                    <small class="text-muted d-block text-truncate mb-2" title="${escapeHtml(image.filename)}">
                        📁 ${escapeHtml(image.filename)}
                    </small>
                    <div class="description-section mb-2">
                        <small class="text-secondary d-block" id="desc-${image.id}" style="min-height: 40px; word-wrap: break-word;">
                            ${image.description ? escapeHtml(image.description) : '<em class="text-muted">No description</em>'}
                        </small>
                    </div>
                    <div class="mt-2 d-flex gap-1">
                        <button type="button" class="btn btn-sm btn-info flex-grow-1" 
                                onclick="editImageDescription(${image.id})">
                            <i class="fas fa-edit"></i> Desc
                        </button>
                        <button type="button" class="btn btn-sm btn-danger" 
                                onclick="deleteImage(${image.id})">
                            <i class="fas fa-trash"></i> Del
                        </button>
                    </div>
                </div>
            </div>
        `;
        grid.appendChild(col);
    });
    
    container.appendChild(grid);
}

// Edit image description - improved with modal dialog
function editImageDescription(imageId) {
    // Get current description
    const descElement = document.getElementById(`desc-${imageId}`);
    const currentDescription = descElement.innerText.trim() === 'No description' ? '' : descElement.innerText;
    
    // Create a modal for editing description
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'descriptionModal';
    modal.innerHTML = `
        <div class="modal-dialog modal-sm">
            <div class="modal-content">
                <div class="modal-header bg-info text-white">
                    <h5 class="modal-title">Edit Image Description</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <textarea class="form-control" id="descriptionInput" rows="4" placeholder="Enter image description...">${escapeHtml(currentDescription)}</textarea>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-info" onclick="saveImageDescription(${imageId})">Save</button>
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
    
    // Clean up after modal closes
    modal.addEventListener('hidden.bs.modal', () => modal.remove());
}

// Save image description
function saveImageDescription(imageId) {
    const newDescription = document.getElementById('descriptionInput').value.trim();
    
    fetch(`/api/case-image/${imageId}/description`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: newDescription })
    })
    .then(r => r.json())
    .then(data => {
        const modal = bootstrap.Modal.getInstance(document.getElementById('descriptionModal'));
        modal.hide();
        
        // Update the description on the page
        const descElement = document.getElementById(`desc-${imageId}`);
        if (descElement) {
            descElement.innerHTML = newDescription ? escapeHtml(newDescription) : '<em class="text-muted">No description</em>';
        }
    })
    .catch(error => {
        console.error('Error updating description:', error);
        alert('Error updating description');
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
    .then(r => r.json())
    .then(data => {
        if (data.image_id || data.success) {
            input.value = '';
            reloadImages(caseId);
        } else {
            alert('Error: ' + (data.error || 'Upload failed'));
        }
    })
    .catch(error => {
        console.error('Error uploading image:', error);
        alert('Error uploading image: ' + error.message);
    })
    .finally(() => {
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = originalText;
    });
}

// Save all changes - improved with validation and error handling
function saveEditedCase() {
    const caseIdField = document.getElementById('editCaseId').value;
    const caseNumber = document.getElementById('editCaseNumber').value.trim();
    const diagnosis = document.getElementById('editCaseDiagnosis').value.trim();
    const discussion = document.getElementById('editCaseDiscussion').value.trim();
    
    // Validate required fields
    if (!caseNumber) {
        alert('Case number is required');
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
        const answerText = row.querySelector('.qa-answer-text').value.trim();
        
        // Only add pairs that have at least a question or answer
        if (questionText || answerText) {
            pairs.push({
                question_text: questionText,
                answer_text: answerText
            });
        }
    });
    
    // Prepare data payload
    const payload = {
        case_number: caseNumber,
        diagnosis: diagnosis,
        discussion: discussion || null,
        pairs: pairs
    };
    
    // Show loading state
    const saveBtn = event.target;
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
    
    if (isNew && packetId) {
        // Creating new case
        endpoint = '/api/case/create';
        method = 'POST';
        payload.packet_id = packetId;
    } else if (caseIdField && !caseIdField.startsWith('new-')) {
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
    fetch(endpoint, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
    })
    .then(data => {
        if (data.success || data.id) {
            alert('Case saved successfully!');
            
            // Determine redirect destination
            let redirectUrl = '/start-exam';
            if (returnTo) {
                redirectUrl = returnTo;
            } else if (isNew) {
                redirectUrl = `/view-case/${data.id || data.case_id}`;
            } else {
                redirectUrl = `/view-case/${caseIdField}`;
            }
            
            window.location.href = redirectUrl;
        } else {
            alert('Error: ' + (data.error || 'Failed to save case'));
        }
    })
    .catch(error => {
        console.error('Error saving case:', error);
        alert('Error saving case: ' + error.message);
    })
    .finally(() => {
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalText;
    });
}
