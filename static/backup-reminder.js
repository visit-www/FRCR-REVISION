/**
 * Backup Reminder System
 * Checks if backup is needed and reminds user
 */

class BackupReminder {
    constructor() {
        this.checkInterval = 24 * 60 * 60 * 1000; // 24 hours
        this.lastCheckKey = 'backup_last_check';
        this.dismissedKey = 'backup_reminder_dismissed';
    }
    
    async init() {
        // Only check for admin users
        const isAdmin = await this.checkIfAdmin();
        if (!isAdmin) return;
        
        // Check if we should show reminder
        const shouldCheck = this.shouldCheckBackup();
        if (shouldCheck) {
            await this.checkBackupStatus();
        }
    }
    
    async checkIfAdmin() {
        try {
            const response = await fetch('/api/backup/status');
            if (response.ok) {
                const data = await response.json();
                return data.is_admin === true;
            }
        } catch (error) {
            console.log('Not admin or backup status not available');
        }
        return false;
    }
    
    shouldCheckBackup() {
        const lastCheck = localStorage.getItem(this.lastCheckKey);
        const dismissed = sessionStorage.getItem(this.dismissedKey);
        
        // Don't show if dismissed this session
        if (dismissed) return false;
        
        // Check if 24 hours passed since last check
        if (!lastCheck) return true;
        
        const lastCheckTime = parseInt(lastCheck);
        const now = Date.now();
        
        return (now - lastCheckTime) >= this.checkInterval;
    }
    
    async checkBackupStatus() {
        try {
            const response = await fetch('/api/backup/status');
            if (!response.ok) return;
            
            const data = await response.json();
            
            // Update last check time
            localStorage.setItem(this.lastCheckKey, Date.now().toString());
            
            // Show reminder if backup needed
            if (data.needs_backup) {
                this.showReminder(data.hours_since_backup);
            }
        } catch (error) {
            console.error('Error checking backup status:', error);
        }
    }
    
    showReminder(hoursSince) {
        // Create reminder element
        const reminder = document.createElement('div');
        reminder.className = 'backup-reminder-toast';
        reminder.innerHTML = `
            <div class="toast-header bg-peachy-orange text-dark">
                <i class="bi fas fa-exclamation-triangle me-2"></i>
                <strong class="me-auto">Backup Reminder</strong>
                <button type="button" class="btn-close" data-dismiss="reminder"></button>
            </div>
            <div class="toast-body">
                <p class="mb-2">
                    ${hoursSince ? 
                        `It's been ${Math.floor(hoursSince)} hours since your last backup.` : 
                        'You haven\'t created a backup yet.'}
                </p>
                <p class="mb-3">Keep your data safe by downloading a backup now!</p>
                <div class="d-grid gap-2">
                    <a href="/api/backup/manager" class="btn btn-success btn-sm">
                        <i class="bi fas fa-download"></i> Go to Backup Manager
                    </a>
                    <button class="btn btn-outline-secondary btn-sm" data-dismiss="reminder">
                        Remind Me Later
                    </button>
                </div>
            </div>
        `;
        
        // Add styles
        this.addStyles();
        
        // Add to page
        document.body.appendChild(reminder);
        
        // Show with animation
        setTimeout(() => reminder.classList.add('show'), 100);
        
        // Handle dismiss buttons
        reminder.querySelectorAll('[data-dismiss="reminder"]').forEach(btn => {
            btn.addEventListener('click', () => this.dismissReminder(reminder));
        });
        
        // Auto-dismiss after 30 seconds
        setTimeout(() => {
            if (reminder.parentElement) {
                this.dismissReminder(reminder);
            }
        }, 30000);
    }
    
    dismissReminder(element) {
        element.classList.remove('show');
        setTimeout(() => element.remove(), 300);
        
        // Mark as dismissed for this session
        sessionStorage.setItem(this.dismissedKey, 'true');
    }
    
    addStyles() {
        if (document.getElementById('backup-reminder-styles')) return;
        
        const styles = document.createElement('style');
        styles.id = 'backup-reminder-styles';
        styles.textContent = `
            .backup-reminder-toast {
                position: fixed;
                bottom: 20px;
                right: 20px;
                width: 350px;
                max-width: calc(100vw - 40px);
                background: white;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                z-index: 9999;
                opacity: 0;
                transform: translateY(20px);
                transition: all 0.3s ease;
            }
            
            .backup-reminder-toast.show {
                opacity: 1;
                transform: translateY(0);
            }
            
            .backup-reminder-toast .toast-header {
                padding: 12px 16px;
                border-radius: 8px 8px 0 0;
                border-bottom: 1px solid rgba(0,0,0,0.1);
            }
            
            .backup-reminder-toast .toast-body {
                padding: 16px;
            }
            
            @media (max-width: 576px) {
                .backup-reminder-toast {
                    bottom: 10px;
                    right: 10px;
                    left: 10px;
                    width: auto;
                }
            }
        `;
        document.head.appendChild(styles);
    }
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        const reminder = new BackupReminder();
        reminder.init();
    });
} else {
    const reminder = new BackupReminder();
    reminder.init();
}
