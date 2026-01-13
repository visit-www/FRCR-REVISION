/**
 * Session Manager - Industry Standard Session Management
 * 
 * Features:
 * - 30-minute session timeout
 * - Activity tracking (mouse, keyboard, scroll, touch)
 * - Warning before expiration (5 minutes remaining)
 * - Auto-logout on expiration
 * - Session refresh on activity
 * - Handles 401/403 responses globally
 */

class SessionManager {
    constructor() {
        this.SESSION_TIMEOUT = 30 * 60 * 1000; // 30 minutes in milliseconds
        this.WARNING_TIME = 5 * 60 * 1000; // Show warning 5 minutes before expiration
        this.REFRESH_INTERVAL = 5 * 60 * 1000; // Refresh session every 5 minutes
        this.ACTIVITY_CHECK_INTERVAL = 60000; // Check activity every minute
        
        this.lastActivity = Date.now();
        this.warningShown = false;
        this.refreshTimer = null;
        this.activityTimer = null;
        this.warningTimer = null;
        
        this.init();
    }
    
    init() {
        // Only initialize if user is authenticated
        if (!this.isAuthenticated()) {
            return;
        }
        
        console.log('[SessionManager] Initializing session management');
        
        // Track user activity
        this.setupActivityTracking();
        
        // Start periodic session refresh
        this.startSessionRefresh();
        
        // Start activity monitoring
        this.startActivityMonitoring();
        
        // Intercept fetch requests to handle 401/403
        this.setupFetchInterceptor();
        
        // Check session status on load
        this.checkSessionStatus();
    }
    
    isAuthenticated() {
        // Check if user is authenticated (you may need to adjust this based on your setup)
        return document.body.classList.contains('authenticated') || 
               document.querySelector('[data-user-id]') !== null ||
               window.currentUser !== undefined;
    }
    
    setupActivityTracking() {
        // Track various user activities
        const activities = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];
        
        activities.forEach(activity => {
            document.addEventListener(activity, () => this.onActivity(), { passive: true });
        });
        
        // Also track window focus
        window.addEventListener('focus', () => this.onActivity());
    }
    
    onActivity() {
        const now = Date.now();
        const timeSinceLastActivity = now - this.lastActivity;
        
        // Only refresh if at least 1 minute has passed since last activity
        // This prevents excessive API calls
        if (timeSinceLastActivity > 60000) {
            this.lastActivity = now;
            this.refreshSession();
            this.warningShown = false; // Reset warning if user is active
        }
    }
    
    startSessionRefresh() {
        // Refresh session periodically
        this.refreshTimer = setInterval(() => {
            this.refreshSession();
        }, this.REFRESH_INTERVAL);
        
        // Initial refresh
        this.refreshSession();
    }
    
    startActivityMonitoring() {
        this.activityTimer = setInterval(() => {
            this.checkSessionStatus();
        }, this.ACTIVITY_CHECK_INTERVAL);
    }
    
    async refreshSession() {
        try {
            const response = await fetch('/auth/session/refresh', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'include'
            });
            
            if (response.status === 401) {
                const data = await response.json();
                if (data.expired) {
                    this.handleSessionExpired();
                    return;
                }
            }
            
            if (response.ok) {
                const data = await response.json();
                this.lastActivity = Date.now();
                this.warningShown = false;
                console.log('[SessionManager] Session refreshed successfully');
                return data;
            }
        } catch (error) {
            console.error('[SessionManager] Error refreshing session:', error);
        }
    }
    
    async checkSessionStatus() {
        try {
            const response = await fetch('/auth/session/status', {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'include'
            });
            
            if (response.status === 401) {
                this.handleSessionExpired();
                return;
            }
            
            if (response.ok) {
                const data = await response.json();
                const timeRemaining = data.time_remaining || 0;
                
                // Show warning if less than 5 minutes remaining
                if (timeRemaining > 0 && timeRemaining < this.WARNING_TIME && !this.warningShown) {
                    this.showExpirationWarning(timeRemaining);
                }
                
                // Auto-logout if expired
                if (timeRemaining <= 0) {
                    this.handleSessionExpired();
                }
            }
        } catch (error) {
            console.error('[SessionManager] Error checking session status:', error);
        }
    }
    
    showExpirationWarning(timeRemaining) {
        this.warningShown = true;
        const minutes = Math.ceil(timeRemaining / 60);
        
        // Create or update warning modal
        let warningModal = document.getElementById('session-warning-modal');
        if (!warningModal) {
            warningModal = this.createWarningModal();
            document.body.appendChild(warningModal);
        }
        
        const message = warningModal.querySelector('.warning-message');
        message.textContent = `Your session will expire in ${minutes} minute${minutes !== 1 ? 's' : ''}. Click "Stay Logged In" to continue.`;
        
        // Show modal
        const bsModal = new bootstrap.Modal(warningModal);
        bsModal.show();
        
        // Auto-hide after session expires
        clearTimeout(this.warningTimer);
        this.warningTimer = setTimeout(() => {
            bsModal.hide();
            this.handleSessionExpired();
        }, timeRemaining * 1000);
    }
    
    createWarningModal() {
        const modal = document.createElement('div');
        modal.id = 'session-warning-modal';
        modal.className = 'modal fade';
        modal.setAttribute('tabindex', '-1');
        modal.setAttribute('data-bs-backdrop', 'static');
        modal.setAttribute('data-bs-keyboard', 'false');
        modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header bg-warning">
                        <h5 class="modal-title">
                            <i class="fas fa-exclamation-triangle me-2"></i>Session Expiring Soon
                        </h5>
                    </div>
                    <div class="modal-body">
                        <p class="warning-message"></p>
                        <p class="text-muted small">For security, your session will automatically expire after 30 minutes of inactivity.</p>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-primary" onclick="sessionManager.refreshSession(); bootstrap.Modal.getInstance(document.getElementById('session-warning-modal')).hide();">
                            <i class="fas fa-sync me-2"></i>Stay Logged In
                        </button>
                        <button type="button" class="btn btn-secondary" onclick="sessionManager.handleLogout();">
                            <i class="fas fa-sign-out-alt me-2"></i>Log Out
                        </button>
                    </div>
                </div>
            </div>
        `;
        return modal;
    }
    
    handleSessionExpired() {
        console.log('[SessionManager] Session expired - logging out');
        
        // Clear all timers
        this.cleanup();
        
        // Show expiration message
        const message = 'Your session has expired due to inactivity. Please log in again.';
        
        // Try to show a toast or alert
        if (typeof showToast === 'function') {
            showToast(message, 'warning');
        } else {
            alert(message);
        }
        
        // Redirect to login
        setTimeout(() => {
            window.location.href = '/auth/login?expired=1';
        }, 2000);
    }
    
    async handleLogout() {
        try {
            await fetch('/auth/logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'include'
            });
        } catch (error) {
            console.error('[SessionManager] Error during logout:', error);
        } finally {
            window.location.href = '/auth/login';
        }
    }
    
    setupFetchInterceptor() {
        // Intercept fetch to handle 401/403 globally
        const originalFetch = window.fetch;
        const self = this;
        
        window.fetch = async function(...args) {
            const response = await originalFetch.apply(this, args);
            
            // Handle 401 Unauthorized
            if (response.status === 401) {
                const data = await response.json().catch(() => ({}));
                if (data.expired || data.error?.includes('expired') || data.error?.includes('Session')) {
                    self.handleSessionExpired();
                    return response;
                }
            }
            
            // Handle 403 Forbidden (might be session issue)
            if (response.status === 403) {
                // Check if it's a session-related 403
                const data = await response.json().catch(() => ({}));
                if (data.error?.includes('session') || data.error?.includes('expired')) {
                    self.handleSessionExpired();
                    return response;
                }
            }
            
            return response;
        };
    }
    
    cleanup() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
        if (this.activityTimer) {
            clearInterval(this.activityTimer);
            this.activityTimer = null;
        }
        if (this.warningTimer) {
            clearTimeout(this.warningTimer);
            this.warningTimer = null;
        }
    }
}

// Initialize session manager when DOM is ready
let sessionManager;
document.addEventListener('DOMContentLoaded', () => {
    sessionManager = new SessionManager();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (sessionManager) {
        sessionManager.cleanup();
    }
});
