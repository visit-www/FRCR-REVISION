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
        
        // Edit/View toggle
        document.addEventListener('click', (e) => {
            if (e.target.id === 'editUserBtn') this.switchToEditMode();
            if (e.target.id === 'cancelEditBtn') this.switchToViewMode();
            if (e.target.id === 'saveChangesBtn') this.saveAllChanges();
            if (e.target.id === 'deleteUserBtn') this.showDeleteOptions();
            if (e.target.id === 'confirmSoftDeleteBtn') this.confirmSoftDelete();
            if (e.target.id === 'confirmPermanentDeleteBtn') this.confirmPermanentDelete();
            if (e.target.id === 'restoreUserBtn') this.restoreUser();
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
                subscription: subscription
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
            <tr class="${user.is_deleted ? 'status-deleted' : ''}">
                <td>${this.escapeHtml(user.email)}</td>
                <td>${this.escapeHtml(user.full_name)}</td>
                <td>
                    <span class="badge badge-${user.role}">
                        ${user.role.replace(/_/g, ' ').toUpperCase()}
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
                        <button class="btn btn-sm btn-view" onclick="userMgmt.showUserDetail(${user.id}, 'view')">
                            <i class="fas fa-eye"></i> View
                        </button>
                        ${user.is_deleted ? '' : `
                            <button class="btn btn-sm btn-edit" onclick="userMgmt.showUserDetail(${user.id}, 'edit')">
                                <i class="fas fa-edit"></i> Edit
                            </button>
                        `}
                    </div>
                </td>
            </tr>
        `).join('');
    }
    
    async showUserDetail(userId, mode = 'view') {
        try {
            const response = await fetch(`/api/admin/users/${userId}`);
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
                            <span class="badge badge-${user.role}">
                                ${user.role.replace(/_/g, ' ').toUpperCase()}
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
                    ${isReadOnly ? `
                        <!-- View Mode Buttons -->
                        <div class="d-flex gap-2 flex-wrap">
                            ${!user.is_deleted ? `
                                <button id="editUserBtn" class="btn btn-edit flex-grow-1">
                                    <i class="fas fa-edit"></i> Edit User
                                </button>
                                <button id="deleteUserBtn" class="btn btn-delete flex-grow-1">
                                    <i class="fas fa-trash"></i> Delete User
                                </button>
                            ` : `
                                <button id="restoreUserBtn" class="btn btn-restore flex-grow-1">
                                    <i class="fas fa-undo"></i> Restore User
                                </button>
                            `}
                        </div>
                        ${user.is_deleted ? `
                            <div class="soft-delete-info mt-3">
                                <strong><i class="fas fa-info-circle"></i> Soft Deleted</strong><br>
                                <small>Deleted: ${new Date(user.deleted_at).toLocaleString()}<br>
                                Data is preserved and can be restored at any time.</small>
                            </div>
                        ` : ''}
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
                
                <!-- Delete Options Section (Hidden by default) -->
                <div id="deleteOptionsDiv" style="display:none;">
                    <div class="delete-options-section">
                        <h5><i class="fas fa-exclamation-triangle"></i> Delete User: Choose Option</h5>
                        <p>How would you like to delete this user?</p>
                        <button id="confirmSoftDeleteBtn" class="delete-option-button soft-delete">
                            <span class="btn-title">🔄 Soft Delete (Recommended)</span>
                            <span class="btn-description">Preserve user data • Can be restored later</span>
                        </button>
                        <button id="confirmPermanentDeleteBtn" class="delete-option-button permanent-delete">
                            <span class="btn-title">🗑️ Permanent Delete (Irreversible)</span>
                            <span class="btn-description">Remove all user data • Cannot be undone</span>
                        </button>
                        <button class="btn btn-secondary w-100 mt-2" onclick="document.getElementById('deleteOptionsDiv').style.display='none'">
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
                if (!roleResponse.ok) {
                    const error = await roleResponse.json();
                    errors.push(`Role update failed: ${error.error || 'Unknown error'}`);
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
                this.loadUsers();
                setTimeout(() => this.showUserDetail(this.selectedUser.id, 'view'), 500);
            } else {
                this.showError(errors.join(' | '));
            }
            
        } catch (error) {
            console.error('Error saving changes:', error);
            this.showError(`Error saving changes: ${error.message}`);
        }
    }
    
    showDeleteOptions() {
        const deleteDiv = document.getElementById('deleteOptionsDiv');
        if (deleteDiv) {
            deleteDiv.style.display = deleteDiv.style.display === 'none' ? 'block' : 'none';
        }
    }
    
    async confirmSoftDelete() {
        if (!this.selectedUser) return;
        if (confirm('Soft delete preserves user data and can be restored. Continue?')) {
            this.softDeleteUser(this.selectedUser.id);
        }
    }
    
    async confirmPermanentDelete() {
        if (!this.selectedUser) return;
        if (confirm('⚠️ WARNING: Permanent delete removes ALL data for this user and cannot be undone!\n\nContinue?')) {
            if (confirm('Click OK to confirm permanent deletion.')) {
                this.permanentDeleteUser(this.selectedUser.id);
            }
        }
    }
    
    async softDeleteUser(userId) {
        try {
            const response = await fetch(`/api/admin/users/${userId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to delete user');
            }
            
            this.showSuccess('✅ User soft-deleted. Data preserved. Can be restored.');
            this.closeModal();
            this.loadUsers();
            
        } catch (error) {
            console.error('Error deleting user:', error);
            this.showError(`Failed to delete user: ${error.message}`);
        }
    }
    
    async permanentDeleteUser(userId) {
        try {
            const response = await fetch(`/api/admin/users/${userId}?permanent=true`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to permanently delete user');
            }
            
            this.showSuccess('🗑️ User permanently deleted');
            this.closeModal();
            this.loadUsers();
            
        } catch (error) {
            console.error('Error permanently deleting user:', error);
            this.showError(`Failed to permanently delete user: ${error.message}`);
        }
    }
    
    async restoreUser() {
        if (!this.selectedUser) return;
        if (confirm('Restore this user? All data will be recovered.')) {
            try {
                const response = await fetch(`/api/admin/users/${this.selectedUser.id}/restore`, {
                    method: 'POST'
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to restore user');
                }
                
                this.showSuccess('User restored successfully');
                this.closeModal();
                this.loadUsers();
                
            } catch (error) {
                console.error('Error restoring user:', error);
                this.showError(`Failed to restore user: ${error.message}`);
            }
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
