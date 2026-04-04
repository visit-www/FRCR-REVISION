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
        this.expired = false; // Re-entry guard for handleSessionExpired
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
        if (this.expired) return; // Don't track activity after session expiry

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
        if (this.expired) return; // Don't refresh after session expiry

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
                this.handleSessionExpired();
                return;
            }

            if (response.ok) {
                const data = await response.json().catch(() => ({}));
                this.lastActivity = Date.now();
                this.warningShown = false;
                return data;
            }
        } catch (error) {
            // Session refresh failed silently
        }
    }
    
    async checkSessionStatus() {
        if (this.expired) return; // Don't check after session expiry

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
                
                // Only show warning if:
                // 1. Time remaining is between 0 and 5 minutes (25-30 minutes of inactivity)
                // 2. Warning hasn't been shown yet
                // 3. At least 25 minutes have passed (timeRemaining <= 5 minutes = 300 seconds)
                // 4. Not immediately after page load
                if (timeRemaining > 0 && timeRemaining <= 300 && !this.warningShown) {
                    // Check if this is a fresh page load (don't show warning immediately)
                    const pageLoadTime = performance.timing?.navigationStart || Date.now();
                    const timeSinceLoad = Date.now() - pageLoadTime;
                    
                    // Calculate how long user has been inactive
                    // If timeRemaining is 300 seconds (5 min), that means 25 minutes (1500 seconds) have passed
                    const inactivityMinutes = (1800 - timeRemaining) / 60; // 30 min total - remaining = inactive time
                    
                    // Only show warning if:
                    // - At least 25 minutes of inactivity (timeRemaining <= 300 seconds)
                    // - Page has been loaded for at least 2 minutes (prevents showing on refresh)
                    // - User has actually been inactive for 25+ minutes
                    if (inactivityMinutes >= 25 && timeSinceLoad > 120000) {
                        this.showExpirationWarning(timeRemaining);
                    }
                }
                
                // Auto-logout if expired
                if (timeRemaining <= 0) {
                    this.handleSessionExpired();
                }
            }
        } catch (error) {
            // Session status check failed silently
        }
    }
    
    showExpirationWarning(timeRemaining) {
        this.warningShown = true;
        const minutes = Math.ceil(timeRemaining / 60);
        const seconds = Math.ceil(timeRemaining % 60);
        
        // Show toast notification with orange background and black text
        const message = `Your session will expire in ${minutes} minute${minutes !== 1 ? 's' : ''}. Click to stay logged in.`;
        
        // Use global showToast function if available, otherwise create custom toast
        if (typeof showToast === 'function') {
            // Show persistent toast that doesn't auto-dismiss
            const toastId = 'session-warning-toast';
            let existingToast = document.getElementById(toastId);
            
            if (!existingToast) {
                // Create a special persistent toast with action button
                const toastContainer = document.getElementById('toast-container');
                if (toastContainer) {
                    existingToast = document.createElement('div');
                    existingToast.id = toastId;
                    existingToast.className = 'session-toast';
                    existingToast.setAttribute('role', 'alert');
                    
                    existingToast.style.cssText = `
                        background: #ffc107;
                        color: #000000;
                        padding: 16px 20px;
                        margin-bottom: 12px;
                        border-radius: 8px;
                        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                        min-width: 300px;
                        max-width: 400px;
                        font-size: 14px;
                        font-weight: 500;
                        opacity: 0;
                        transform: translateX(100%);
                        transition: all 0.3s ease;
                        border-left: 4px solid rgba(0,0,0,0.3);
                        cursor: pointer;
                    `;
                    
                    existingToast.innerHTML = `
                        <div style="display: flex; align-items: center; flex: 1;">
                            <i class="fas fa-exclamation-triangle me-2"></i>
                            <span>${message}</span>
                        </div>
                        <button type="button" class="btn btn-sm btn-dark ms-3" onclick="sessionManager.refreshSession(); this.closest('.session-toast').remove();" style="font-size: 12px; padding: 4px 12px;">
                            Stay In
                        </button>
                    `;
                    
                    existingToast.addEventListener('click', (e) => {
                        if (e.target.tagName !== 'BUTTON') {
                            this.refreshSession();
                            existingToast.remove();
                        }
                    });
                    
                    toastContainer.appendChild(existingToast);
                    
                    // Animate in
                    setTimeout(() => {
                        existingToast.style.opacity = '1';
                        existingToast.style.transform = 'translateX(0)';
                    }, 10);
                }
            } else {
                // Update existing toast message
                const messageSpan = existingToast.querySelector('span');
                if (messageSpan) {
                    messageSpan.textContent = message;
                }
            }
            
            // Auto-remove and logout when session expires
            clearTimeout(this.warningTimer);
            this.warningTimer = setTimeout(() => {
                if (existingToast) {
                    existingToast.remove();
                }
                this.handleSessionExpired();
            }, timeRemaining * 1000);
        }
    }
    
    handleSessionExpired() {
        // Re-entry guard: prevent multiple calls causing toast flashing
        if (this.expired) return;
        this.expired = true;

        // Clear all timers immediately
        this.cleanup();

        // Remove any existing warning toast
        const warningToast = document.getElementById('session-warning-toast');
        if (warningToast) {
            warningToast.remove();
        }

        // Already on login page — nothing to do
        if (window.location.pathname.startsWith('/auth/login')) {
            return;
        }

        // Signal to beforeunload handlers: session expired, let the redirect through
        window._sessionExpired = true;

        // Stop all pending network requests and page activity before redirecting
        try { window.stop(); } catch (e) { /* ignore */ }

        // Show expiration message with toast
        const message = 'Your session has expired due to inactivity. Redirecting to login...';

        if (typeof showToast === 'function') {
            showToast(message, 'session-warning', 3000);
        } else {
            alert(message);
        }

        // Force redirect to login — use replace() so back button won't return to expired page
        const redirectUrl = '/auth/login?expired=1';
        try {
            window.location.replace(redirectUrl);
        } catch (error) {
            // Immediate redirect failed, fallback below
        }

        // Hard fallback: if replace() didn't navigate (e.g. blocked by pending JS), retry
        setTimeout(() => {
            if (!window.location.pathname.startsWith('/auth/login')) {
                window.location.replace(redirectUrl);
            }
        }, 1500);

        // Last-resort fallback using href assignment
        setTimeout(() => {
            if (!window.location.pathname.startsWith('/auth/login')) {
                window.location.href = redirectUrl;
            }
        }, 3000);
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
            // Logout error - redirect anyway
        } finally {
            window.location.href = '/auth/login';
        }
    }
    
    setupFetchInterceptor() {
        // Intercept fetch to handle 401/403 globally
        const originalFetch = window.fetch;
        const self = this;

        window.fetch = async function(...args) {
            // Skip interception if session already expired (avoid cascading 401s)
            if (self.expired) {
                return originalFetch.apply(this, args);
            }

            // Identify session manager's own internal calls to avoid recursive handling
            const url = (typeof args[0] === 'string') ? args[0] : args[0]?.url || '';
            const isSessionCall = url.includes('/auth/session/');

            let response;
            try {
                response = await originalFetch.apply(this, args);
            } catch (error) {
                throw error;
            }

            // Don't intercept responses after expiry triggered
            if (self.expired) return response;

            // Handle 401 Unauthorized — session manager only runs for
            // authenticated users, so any 401 means session expired.
            // Skip for session manager's own calls (handled by caller directly).
            if (response.status === 401 && !isSessionCall) {
                self.handleSessionExpired();
                return response;
            }

            // Handle 403 Forbidden (might be session issue)
            if (response.status === 403 && !isSessionCall) {
                try {
                    const cloned = response.clone();
                    const data = await cloned.json().catch(() => ({}));
                    if (data.error?.includes('session') || data.error?.includes('expired')) {
                        self.handleSessionExpired();
                    }
                } catch (e) {
                    // Ignore clone/parse errors
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
