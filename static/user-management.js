/**
 * User Management JavaScript
 * Handles user list, search, filter, and CRUD operations
 */

class UserManagement {
    constructor() {
        this.users = [];
        this.currentPage = 1;
        this.totalPages = 1;
        this.selectedUser = null;
        this.modalMode = 'view'; // 'view' or 'edit'
        this.init();
    }
    
    /**
     * Get display label for role
     */
    getRoleDisplayLabel(role, isSuperadmin = false) {
        if (isSuperadmin) return 'Super Admin';
        const labels = {
            'admin': 'Admin',
            'content_manager': 'Content Manager',
            'student': 'Student'
        };
        return labels[role] || role.replace(/_/g, ' ').toUpperCase();
    }
    
    /**
     * Get badge class for role highlighting
     * - superadmin: red
     * - admin: orange
     * - content_manager: blue
     * - student: green
     */
    getRoleBadgeClass(role, isSuperadmin = false) {
        if (isSuperadmin) return 'role-superadmin';
        const classes = {
            'admin': 'role-admin',
            'content_manager': 'role-content-manager',
            'student': 'role-student'
        };
        return classes[role] || 'role-student';
    }
    
    init() {
        this.setupEventListeners();
        this.loadUsers();
    }
    
    setupEventListeners() {
        // Filter dropdowns trigger immediate search
        document.getElementById('userRoleFilter')?.addEventListener('change', (e) => {
            this.currentPage = 1;
            this.loadUsers();
        });
        
        document.getElementById('userSubscriptionFilter')?.addEventListener('change', (e) => {
            this.currentPage = 1;
            this.loadUsers();
        });
        
        // Search box: Allow Enter key to trigger search
        document.getElementById('userSearch')?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.currentPage = 1;
                this.loadUsers();
            }
        });
        
        // Clear search button (X icon)
        document.getElementById('clearSearchBtn')?.addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('userSearch').value = '';
            document.getElementById('userSearch').focus();
            this.currentPage = 1;
            this.loadUsers();
        });
        
        // Reset all filters button
        document.getElementById('resetFiltersBtn')?.addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('userSearch').value = '';
            document.getElementById('userRoleFilter').value = '';
            document.getElementById('userSubscriptionFilter').value = '';
            this.currentPage = 1;
            this.loadUsers();
        });
        
        // Pagination
        document.getElementById('prevPage')?.addEventListener('click', () => this.previousPage());
        document.getElementById('nextPage')?.addEventListener('click', () => this.nextPage());
        
        // Modal
        document.getElementById('closeUserModal')?.addEventListener('click', () => this.closeModal());
        document.getElementById('closeUserModal2')?.addEventListener('click', () => this.closeModal());
        document.getElementById('userDetailModal')?.addEventListener('click', (e) => {
            if (e.target.id === 'userDetailModal') this.closeModal();
        });
        
        // Edit/View toggle - use event delegation with closest() to handle nested elements
        document.addEventListener('click', (e) => {
            // Use closest() to find the button element even when clicking on nested children
            const editBtn = e.target.closest('#editUserBtn');
            const cancelBtn = e.target.closest('#cancelEditBtn');
            const saveBtn = e.target.closest('#saveChangesBtn');
            const deleteBtn = e.target.closest('#deleteUserBtn');
            const confirmDeleteBtn = e.target.closest('#confirmDeleteBtn');
            
            // Check by ID first (for direct clicks), then by closest element
            if (e.target.id === 'editUserBtn' || editBtn) {
                this.switchToEditMode();
            } else if (e.target.id === 'cancelEditBtn' || cancelBtn) {
                this.switchToViewMode();
            } else if (e.target.id === 'saveChangesBtn' || saveBtn) {
                this.saveAllChanges();
            } else if (e.target.id === 'deleteUserBtn' || deleteBtn) {
                this.showDeleteConfirmation();
            } else if (e.target.id === 'confirmDeleteBtn' || confirmDeleteBtn) {
                e.preventDefault();
                e.stopPropagation();
                this.confirmDeleteUser();
            }
        });
    }
    
    async loadUsers() {
        try {
            const search = document.getElementById('userSearch')?.value || '';
            const role = document.getElementById('userRoleFilter')?.value || '';
            const subscription = document.getElementById('userSubscriptionFilter')?.value || '';
            
            const params = new URLSearchParams({
                page: this.currentPage,
                per_page: 10,
                search: search,
                role: role,
                subscription: subscription,
                _: Date.now()  // Cache-busting
            });
            
            const response = await fetch(`/api/admin/users?${params}`);
            if (!response.ok) {
                throw new Error(`Failed to load users: ${response.status}`);
            }
            
            const data = await response.json();
            this.users = data.users;
            this.totalPages = data.pages;
            
            this.renderUserList();
            this.updatePagination();
            
        } catch (error) {
            console.error('Error loading users:', error);
            this.showError(`Failed to load users: ${error.message}`);
        }
    }
    
    renderUserList() {
        const tbody = document.getElementById('userTableBody');
        if (!tbody) return;
        
        if (this.users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4">No users found</td></tr>';
            return;
        }
        
        tbody.innerHTML = this.users.map(user => `
            <tr>
                <td>${this.escapeHtml(user.email)}</td>
                <td>${this.escapeHtml(user.full_name)}</td>
                <td>
                    <span class="badge ${this.getRoleBadgeClass(user.role, user.is_superadmin)}">
                        ${this.getRoleDisplayLabel(user.role, user.is_superadmin)}
                    </span>
                </td>
                <td>
                    <span class="badge badge-${this.getSubscriptionBadgeClass(user.subscription_status)}">
                        ${user.subscription_status.toUpperCase()}
                    </span>
                </td>
                <td>
                    <span class="status-${user.is_active ? 'active' : 'inactive'}">
                        ${user.is_active ? '✅ Active' : '❌ Inactive'}
                    </span>
                </td>
                <td>
                    <div class="action-buttons">
                        <button class="btn btn-sm btn-view" onclick="userMgmt.showUserDetail(${user.id}, 'view')" title="View user details">
                            <i class="fas fa-eye"></i> View
                        </button>
                        ${user.is_superadmin ? '' : `
                            <button class="btn btn-sm btn-edit" onclick="userMgmt.showUserDetail(${user.id}, 'edit')" title="Edit user">
                                <i class="fas fa-edit"></i> Edit
                            </button>
                            <button class="btn btn-sm btn-delete" onclick="userMgmt.deleteUserFromTable(${user.id}, '${this.escapeHtml(user.email)}')" title="Delete user">
                                <i class="fas fa-trash"></i> Delete
                            </button>
                        `}
                    </div>
                </td>
            </tr>
        `).join('');
    }
    
    async showUserDetail(userId, mode = 'view') {
        try {
            // Add cache-busting parameter to ensure fresh data
            const response = await fetch(`/api/admin/users/${userId}?_=${Date.now()}`);
            if (!response.ok) {
                throw new Error(`Failed to load user: ${response.status}`);
            }
            
            const user = await response.json();
            this.selectedUser = user;
            this.modalMode = mode;
            this.renderUserModal(user, mode);
            
            document.getElementById('userDetailModal')?.classList.add('show');
            
        } catch (error) {
            console.error('Error loading user detail:', error);
            this.showError(`Failed to load user: ${error.message}`);
        }
    }
    
    renderUserModal(user, mode = 'view') {
        const modal = document.getElementById('userDetailModal');
        if (!modal) return;
        
        const content = document.getElementById('userModalContent');
        const createdDate = new Date(user.created_at).toLocaleDateString();
        const lastLogin = user.last_login ? new Date(user.last_login).toLocaleString() : 'Never';
        const isReadOnly = mode === 'view';
        
        content.innerHTML = `
            <div class="modal-body">
                <!-- User Header -->
                <div class="user-detail-header">
                    <h3><i class="fas fa-user-circle"></i> ${this.escapeHtml(user.full_name)}</h3>
                    <p class="mb-2"><i class="fas fa-envelope"></i> ${this.escapeHtml(user.email)}</p>
                    <span class="mode-indicator">
                        ${isReadOnly ? '<i class="fas fa-book"></i> View Mode' : '<i class="fas fa-edit"></i> Edit Mode'}
                    </span>
                </div>
                
                <!-- Editable Fields -->
                <div class="user-details mt-4">
                    <!-- Role Field -->
                    <div class="detail-row">
                        <label><i class="fas fa-user-tag"></i> Role:</label>
                        ${isReadOnly ? `
                            <span class="badge ${this.getRoleBadgeClass(user.role, user.is_superadmin)}">
                                ${this.getRoleDisplayLabel(user.role, user.is_superadmin)}
                            </span>
                        ` : `
                            <select id="editRole" class="form-select">
                                <option value="student" ${user.role === 'student' ? 'selected' : ''}>Student</option>
                                <option value="content_manager" ${user.role === 'content_manager' ? 'selected' : ''}>Content Manager</option>
                                <option value="admin" ${user.role === 'admin' ? 'selected' : ''}>Admin</option>
                            </select>
                        `}
                    </div>
                    
                    <!-- Subscription Field -->
                    <div class="detail-row mt-3">
                        <label><i class="fas fa-credit-card"></i> Subscription:</label>
                        ${isReadOnly ? `
                            <span class="badge badge-${this.getSubscriptionBadgeClass(user.subscription_status)}">
                                ${user.subscription_status.toUpperCase()}
                            </span>
                        ` : `
                            <select id="editSubscription" class="form-select">
                                <option value="free" ${user.subscription_status === 'free' ? 'selected' : ''}>Free</option>
                                <option value="paid" ${user.subscription_status === 'paid' ? 'selected' : ''}>Paid</option>
                                <option value="canceled" ${user.subscription_status === 'canceled' ? 'selected' : ''}>Canceled</option>
                            </select>
                        `}
                    </div>
                    
                    <!-- Read-only Information Fields -->
                    <div class="detail-row mt-3">
                        <label><i class="fas fa-check-circle"></i> Status:</label>
                        <span class="status-${user.is_active ? 'active' : 'inactive'}">
                            ${user.is_active ? '✅ Active' : '❌ Inactive'}
                        </span>
                    </div>
                    
                    <div class="detail-row mt-3">
                        <label><i class="fas fa-calendar-plus"></i> Created:</label>
                        <span>${createdDate}</span>
                    </div>
                    
                    <div class="detail-row mt-3">
                        <label><i class="fas fa-sign-in-alt"></i> Last Login:</label>
                        <span>${lastLogin}</span>
                    </div>
                    
                    ${user.stats ? `
                        <div class="detail-row mt-3">
                            <label><i class="fas fa-file-medical"></i> Cases Created:</label>
                            <span><strong>${user.stats.cases_created}</strong></span>
                        </div>
                        
                        <div class="detail-row mt-2">
                            <label><i class="fas fa-eye"></i> Cases Viewed:</label>
                            <span><strong>${user.stats.cases_viewed}</strong></span>
                        </div>
                    ` : ''}
                </div>
                
                <!-- Action Buttons Section -->
                <div class="modal-actions">
                    ${user.is_superadmin ? `
                        <!-- Superadmin - Read Only -->
                        <div class="alert alert-warning" style="margin: 0;">
                            <i class="fas fa-shield-alt"></i> <strong>Protected Account</strong><br>
                            <small>The superadmin account cannot be edited or deleted.</small>
                        </div>
                    ` : isReadOnly ? `
                        <!-- View Mode Buttons -->
                        <div class="d-flex gap-2 flex-wrap">
                            <button id="editUserBtn" class="btn btn-edit flex-grow-1">
                                <i class="fas fa-edit"></i> Edit User
                            </button>
                            <button id="deleteUserBtn" class="btn btn-delete flex-grow-1">
                                <i class="fas fa-trash"></i> Delete User
                            </button>
                        </div>
                    ` : `
                        <!-- Edit Mode Buttons -->
                        <div class="d-flex gap-2 flex-wrap">
                            <button id="saveChangesBtn" class="btn btn-success flex-grow-1">
                                <i class="fas fa-save"></i> Save Changes
                            </button>
                            <button id="cancelEditBtn" class="btn btn-secondary flex-grow-1">
                                <i class="fas fa-times"></i> Cancel
                            </button>
                        </div>
                    `}
                </div>
                
                <!-- Delete Confirmation Section (Hidden by default) -->
                <div id="deleteConfirmDiv" style="display:none;">
                    <div class="delete-options-section">
                        <h5><i class="fas fa-exclamation-triangle text-danger"></i> Confirm Delete</h5>
                        <p class="text-danger"><strong>This action cannot be undone!</strong></p>
                        <p>This will permanently delete the user and:</p>
                        <ul class="small text-muted">
                            <li>Remove their private notes and highlights</li>
                            <li>Remove their revision history and view logs</li>
                            <li>Anonymize their forum comments (content preserved)</li>
                            <li>Preserve any cases they created (author cleared)</li>
                        </ul>
                        <button id="confirmDeleteBtn" class="btn btn-danger w-100 mb-2">
                            <i class="fas fa-trash"></i> Yes, Delete User Permanently
                        </button>
                        <button class="btn btn-secondary w-100" onclick="document.getElementById('deleteConfirmDiv').style.display='none'">
                            <i class="fas fa-times"></i> Cancel
                        </button>
                    </div>
                </div>
            </div>
        `;
    }
    
    switchToEditMode() {
        if (this.selectedUser) {
            this.modalMode = 'edit';
            this.renderUserModal(this.selectedUser, 'edit');
        }
    }
    
    switchToViewMode() {
        if (this.selectedUser) {
            this.modalMode = 'view';
            this.renderUserModal(this.selectedUser, 'view');
        }
    }
    
    async saveAllChanges() {
        if (!this.selectedUser) return;
        
        const newRole = document.getElementById('editRole')?.value;
        const newSubscription = document.getElementById('editSubscription')?.value;
        
        if (!newRole || !newSubscription) {
            this.showError('Please select both role and subscription');
            return;
        }
        
        let errors = [];
        
        try {
            // Update role if changed
            if (newRole !== this.selectedUser.role) {
                const roleResponse = await fetch(`/api/admin/users/${this.selectedUser.id}/role`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ role: newRole })
                });
                
                const roleData = await roleResponse.json();
                
                // Handle approval required (202 response)
                if (roleResponse.status === 202 && roleData.requires_approval) {
                    if (roleData.already_pending) {
                        // Show already pending modal with option to resend
                        this.showAlreadyPendingModal('role', this.selectedUser.id, newRole, roleData);
                    } else {
                        this.showApprovalCodeModal('role', this.selectedUser.id, newRole, roleData.action);
                    }
                    return;
                }
                
                if (!roleResponse.ok) {
                    if (roleData.requires_approval) {
                        if (roleData.already_pending) {
                            this.showAlreadyPendingModal('role', this.selectedUser.id, newRole, roleData);
                        } else {
                            this.showApprovalCodeModal('role', this.selectedUser.id, newRole, roleData.action || 'change role');
                        }
                        return;
                    }
                    errors.push(`Role update failed: ${roleData.error || 'Unknown error'}`);
                } else if (roleData.warning) {
                    // Show warning for superadmin
                    this.showWarning(roleData.warning);
                }
            }
            
            // Update subscription if changed
            if (newSubscription !== this.selectedUser.subscription_status) {
                const subResponse = await fetch(`/api/admin/users/${this.selectedUser.id}/subscription`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ subscription_status: newSubscription })
                });
                if (!subResponse.ok) {
                    const error = await subResponse.json();
                    errors.push(`Subscription update failed: ${error.error || 'Unknown error'}`);
                }
            }
            
            if (errors.length === 0) {
                this.showSuccess('✅ All changes saved successfully');
                // Store userId before selectedUser might change
                const userId = this.selectedUser.id;
                // Force refresh the user list first
                await this.loadUsers();
                // Then reload the user detail with fresh data
                setTimeout(() => this.showUserDetail(userId, 'view'), 300);
            } else {
                this.showError(errors.join(' | '));
            }
            
        } catch (error) {
            console.error('Error saving changes:', error);
            this.showError(`Error saving changes: ${error.message}`);
        }
    }
    
    showApprovalCodeModal(action, userId, newValue, actionDescription) {
        // Store pending action
        this.pendingApproval = { action, userId, newValue, actionDescription };
        
        // Create modal HTML
        const modalHtml = `
            <div id="approvalCodeModal" class="custom-modal show" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 2000; display: flex; align-items: center; justify-content: center;">
                <div style="background: white; padding: 30px; border-radius: 10px; max-width: 450px; width: 90%;">
                    <h4 style="color: #e96304; margin-bottom: 15px;">
                        <i class="fas fa-lock"></i> Superadmin Approval Required
                    </h4>
                    <p>This action requires superadmin approval:</p>
                    <p style="background: #f8f9fa; padding: 10px; border-radius: 5px; font-weight: bold;">
                        ${actionDescription}
                    </p>
                    <p style="color: #666; font-size: 14px;">
                        An email has been sent to the superadmin with an approval code.
                        Enter the code below to complete this action.
                    </p>
                    <input type="text" id="approvalCodeInput" placeholder="Enter 8-character code" 
                           style="width: 100%; padding: 12px; font-size: 18px; text-align: center; 
                                  letter-spacing: 3px; text-transform: uppercase; border: 2px solid #ddd; 
                                  border-radius: 5px; margin: 15px 0;" maxlength="8">
                    <div style="display: flex; gap: 10px; margin-top: 15px;">
                        <button onclick="userMgmt.submitApprovalCode()" class="btn btn-success" style="flex: 1;">
                            <i class="fas fa-check"></i> Submit Code
                        </button>
                        <button onclick="userMgmt.closeApprovalModal()" class="btn btn-secondary" style="flex: 1;">
                            Cancel
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        document.getElementById('approvalCodeInput').focus();
    }
    
    showAlreadyPendingModal(action, userId, newValue, responseData) {
        // Store pending action for resend and code entry
        this.pendingApproval = { 
            action, 
            userId, 
            newValue, 
            actionDescription: responseData.action,
            pendingId: responseData.pending_id
        };
        
        const createdAt = new Date(responseData.created_at).toLocaleString();
        
        // Create modal HTML showing pending status with options
        const modalHtml = `
            <div id="alreadyPendingModal" class="custom-modal show" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 2000; display: flex; align-items: center; justify-content: center;">
                <div style="background: white; padding: 30px; border-radius: 10px; max-width: 500px; width: 90%;">
                    <h4 style="color: #5E899E; margin-bottom: 15px;">
                        <i class="fas fa-clock"></i> Approval Already Requested
                    </h4>
                    
                    <div style="background: #f0f6f9; padding: 15px; border-radius: 8px; border-left: 3px solid #5E899E; margin-bottom: 15px;">
                        <p style="margin: 0 0 10px 0;"><strong>Action:</strong> ${responseData.action}</p>
                        <p style="margin: 0 0 10px 0;"><strong>Requested:</strong> ${createdAt}</p>
                        <p style="margin: 0;"><strong>Expires in:</strong> ${responseData.expires_in}</p>
                    </div>
                    
                    <p style="color: #666; font-size: 14px; margin-bottom: 15px;">
                        A request for this action is already pending Super Admin approval.
                        You can either enter the approval code if you have it, or resend the notification email.
                    </p>
                    
                    <!-- Option 1: Enter existing code -->
                    <div style="background: #fff8e6; padding: 15px; border-radius: 8px; border-left: 3px solid #ffc107; margin-bottom: 15px;">
                        <h6 style="margin: 0 0 10px 0; color: #856404;">
                            <i class="fas fa-key"></i> Have the approval code?
                        </h6>
                        <input type="text" id="pendingApprovalCodeInput" placeholder="Enter 8-character code" 
                               style="width: 100%; padding: 10px; font-size: 16px; text-align: center; 
                                      letter-spacing: 3px; text-transform: uppercase; border: 2px solid #ddd; 
                                      border-radius: 5px; margin-bottom: 10px;" maxlength="8">
                        <button onclick="userMgmt.submitPendingApprovalCode()" class="btn btn-success" style="width: 100%;">
                            <i class="fas fa-check"></i> Submit Code
                        </button>
                    </div>
                    
                    <!-- Option 2: Resend email -->
                    <div style="background: #f5f5f3; padding: 15px; border-radius: 8px; border-left: 3px solid #6c757d; margin-bottom: 15px;">
                        <h6 style="margin: 0 0 10px 0; color: #5a6270;">
                            <i class="fas fa-envelope"></i> Need a new code?
                        </h6>
                        <p style="font-size: 13px; color: #666; margin-bottom: 10px;">
                            This will cancel the previous code and send a new one to the Super Admin.
                        </p>
                        <button onclick="userMgmt.resendApprovalCode()" class="btn btn-outline-secondary" style="width: 100%;" id="resendCodeBtn">
                            <i class="fas fa-redo"></i> Resend Approval Request
                        </button>
                    </div>
                    
                    <button onclick="userMgmt.closeAlreadyPendingModal()" class="btn btn-secondary" style="width: 100%;">
                        Cancel
                    </button>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        document.getElementById('pendingApprovalCodeInput').focus();
    }
    
    closeAlreadyPendingModal() {
        const modal = document.getElementById('alreadyPendingModal');
        if (modal) modal.remove();
        this.pendingApproval = null;
    }
    
    async submitPendingApprovalCode() {
        const code = document.getElementById('pendingApprovalCodeInput').value.trim().toUpperCase();
        if (!code || code.length !== 8) {
            alert('Please enter a valid 8-character approval code');
            return;
        }
        
        const { action, userId, newValue } = this.pendingApproval || {};
        if (!action) return;
        
        // Close the already pending modal
        this.closeAlreadyPendingModal();
        
        // Submit the code directly
        try {
            let response;
            if (action === 'role') {
                response = await fetch(`/api/admin/users/${userId}/role`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ role: newValue, approval_code: code })
                });
            } else if (action === 'delete') {
                response = await fetch(`/api/admin/users/${userId}?confirmed=true&approval_code=${code}`, {
                    method: 'DELETE'
                });
            }
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Action failed');
            }
            
            this.showSuccess(`✅ Action completed: ${data.message || 'Success'}`);
            this.pendingApproval = null;
            await this.loadUsers();
            
            // Refresh user detail if modal is open
            if (this.selectedUser && action === 'role') {
                setTimeout(() => this.showUserDetail(userId, 'view'), 300);
            } else {
                this.closeModal();
            }
            
        } catch (error) {
            console.error('Error submitting approval code:', error);
            this.showError(`Failed: ${error.message}`);
        }
    }
    
    async resendApprovalCode() {
        const { action, userId, newValue } = this.pendingApproval || {};
        if (!action) return;
        
        const btn = document.getElementById('resendCodeBtn');
        const originalText = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sending...';
        btn.disabled = true;
        
        try {
            let response;
            if (action === 'role') {
                response = await fetch(`/api/admin/users/${userId}/role`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ role: newValue, resend_code: true })
                });
            } else if (action === 'delete') {
                response = await fetch(`/api/admin/users/${userId}?resend_code=true`, {
                    method: 'DELETE'
                });
            }
            
            const data = await response.json();
            
            if (response.status === 202 && data.status === 'pending_approval') {
                // Success - new code sent
                this.closeAlreadyPendingModal();
                this.showApprovalCodeModal(action, userId, newValue, data.action);
                this.showSuccess('✅ New approval request sent to Super Admin');
            } else if (!response.ok) {
                throw new Error(data.error || 'Failed to resend');
            }
            
        } catch (error) {
            console.error('Error resending approval code:', error);
            btn.innerHTML = originalText;
            btn.disabled = false;
            this.showError(`Failed to resend: ${error.message}`);
        }
    }
    
    closeApprovalModal() {
        const modal = document.getElementById('approvalCodeModal');
        if (modal) modal.remove();
        this.pendingApproval = null;
    }
    
    async submitApprovalCode() {
        const code = document.getElementById('approvalCodeInput').value.trim().toUpperCase();
        if (!code || code.length !== 8) {
            alert('Please enter a valid 8-character approval code');
            return;
        }
        
        const { action, userId, newValue } = this.pendingApproval;
        
        try {
            let response;
            if (action === 'role') {
                response = await fetch(`/api/admin/users/${userId}/role`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ role: newValue, approval_code: code })
                });
            } else if (action === 'delete') {
                response = await fetch(`/api/admin/users/${userId}?approval_code=${code}&confirmed=true`, {
                    method: 'DELETE'
                });
            }
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Action failed');
            }
            
            this.closeApprovalModal();
            this.showSuccess('✅ Action completed successfully');
            this.closeModal();
            this.loadUsers();
            
        } catch (error) {
            alert(`Error: ${error.message}`);
        }
    }
    
    showWarning(message) {
        alert(`⚠️ Warning:\n\n${message}`);
    }
    
    showDeleteConfirmation() {
        const deleteDiv = document.getElementById('deleteConfirmDiv');
        if (deleteDiv) {
            deleteDiv.style.display = deleteDiv.style.display === 'none' ? 'block' : 'none';
        }
    }
    
    async confirmDeleteUser() {
        if (!this.selectedUser) return;
        await this.deleteUser(this.selectedUser.id);
    }
    
    async deleteUser(userId, confirmed = false) {
        try {
            const url = confirmed 
                ? `/api/admin/users/${userId}?confirmed=true` 
                : `/api/admin/users/${userId}`;
                
            const response = await fetch(url, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            // Handle approval required (202 response)
            if (response.status === 202 && data.requires_approval) {
                if (data.already_pending) {
                    // Show already pending modal with option to resend
                    this.showAlreadyPendingModal('delete', userId, null, data);
                } else {
                    this.showApprovalCodeModal('delete', userId, null, data.action);
                }
                return;
            }
            
            // Handle confirmation required (superadmin preview)
            if (response.ok && data.requires_confirmation) {
                const preview = data.preview;
                const confirmMsg = `Delete ${data.target_user.name} (${data.target_user.email})?\n\n` +
                    `WILL DELETE:\n` +
                    `  - ${preview.will_delete.notes} notes\n` +
                    `  - ${preview.will_delete.highlights} highlights\n` +
                    `  - ${preview.will_delete.revision_sessions} revision sessions\n\n` +
                    `WILL PRESERVE:\n` +
                    `  - ${preview.will_preserve.forum_messages} forum comments (anonymized)\n` +
                    `  - ${preview.will_preserve.cases_created} cases created\n\n` +
                    `This action CANNOT be undone!`;
                
                if (confirm(confirmMsg)) {
                    await this.deleteUser(userId, true);
                }
                return;
            }
            
            if (!response.ok) {
                if (data.requires_approval) {
                    if (data.already_pending) {
                        this.showAlreadyPendingModal('delete', userId, null, data);
                    } else {
                        this.showApprovalCodeModal('delete', userId, null, data.action || 'delete user');
                    }
                    return;
                }
                throw new Error(data.error || 'Failed to delete user');
            }
            
            // Show success with cleanup stats
            const stats = data.cleanup_stats || {};
            let message = '✅ User permanently deleted.';
            if (stats.notes_deleted || stats.highlights_deleted || stats.forum_messages_anonymized) {
                message += ` Cleaned up: ${stats.notes_deleted || 0} notes, ${stats.highlights_deleted || 0} highlights.`;
            }
            
            this.showSuccess(message);
            this.closeModal();
            this.loadUsers();
            
        } catch (error) {
            console.error('Error deleting user:', error);
            this.showError(`Failed to delete user: ${error.message}`);
        }
    }
    
    async deleteUserFromTable(userId, userEmail) {
        // Show confirmation dialog
        if (confirm(`Delete user: ${userEmail}?\n\nThis will permanently remove the user and their private data.\nForum comments will be preserved (anonymized).`)) {
            await this.deleteUser(userId);
        }
    }
    
    closeModal() {
        const modal = document.getElementById('userDetailModal');
        if (modal) {
            modal.classList.remove('show');
            this.selectedUser = null;
        }
    }
    
    previousPage() {
        if (this.currentPage > 1) {
            this.currentPage--;
            this.loadUsers();
        }
    }
    
    nextPage() {
        if (this.currentPage < this.totalPages) {
            this.currentPage++;
            this.loadUsers();
        }
    }
    
    updatePagination() {
        document.getElementById('pageInfo').textContent = 
            `Page ${this.currentPage} of ${this.totalPages}`;
        document.getElementById('prevPage').disabled = this.currentPage === 1;
        document.getElementById('nextPage').disabled = this.currentPage === this.totalPages;
    }
    
    getSubscriptionBadgeClass(status) {
        switch(status) {
            case 'paid': return 'paid';
            case 'canceled': return 'canceled';
            default: return 'free';
        }
    }
    
    showSuccess(message) {
        const alert = document.createElement('div');
        alert.className = 'alert alert-success alert-dismissible fade show';
        alert.innerHTML = `
            ${message}
            <button type="button" class="close" data-dismiss="alert">&times;</button>
        `;
        document.body.insertBefore(alert, document.body.firstChild);
        setTimeout(() => alert.remove(), 4000);
    }
    
    showError(message) {
        const alert = document.createElement('div');
        alert.className = 'alert alert-danger alert-dismissible fade show';
        alert.innerHTML = `
            ${message}
            <button type="button" class="close" data-dismiss="alert">&times;</button>
        `;
        document.body.insertBefore(alert, document.body.firstChild);
        setTimeout(() => alert.remove(), 5000);
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize when document is ready
let userMgmt;
document.addEventListener('DOMContentLoaded', () => {
    userMgmt = new UserManagement();
});
