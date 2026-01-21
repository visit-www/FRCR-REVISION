/**
 * PWA Service Worker Registration
 * Registers the service worker and handles installation prompts
 */

// Platform detection
const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
const isAndroid = /Android/.test(navigator.userAgent);
const isMobile = isIOS || isAndroid;
const isStandalone = window.matchMedia('(display-mode: standalone)').matches || 
                     window.navigator.standalone === true;

// Check if service workers are supported by the browser
if ('serviceWorker' in navigator) {
  
  // Register service worker when page loads
  window.addEventListener('load', () => {
    
    navigator.serviceWorker.register('/static/service-worker.js', { scope: '/' })
      .then((registration) => {
        console.log('✅ Service Worker registered successfully:', registration.scope);
        
        // Check for updates periodically
        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing;
          console.log('🔄 New Service Worker version found, updating...');
          
          newWorker.addEventListener('statechange', () => {
            if (newWorker.state === 'activated') {
              console.log('✅ New Service Worker activated');
              // Optionally show a notification to user that app was updated
              if (typeof showToast === 'function') {
                showToast('App updated! Refresh to see the latest changes.', 'success');
              }
            }
          });
        });
      })
      .catch((error) => {
        console.error('❌ Service Worker registration failed:', error);
      });
  });
  
} else {
  console.log('ℹ️ Service Workers not supported in this browser');
}

/**
 * PWA Install Prompt Handler
 * Shows a custom install button/banner when app can be installed
 */
let deferredPrompt; // Store the install prompt event

// Listen for the browser's install prompt
window.addEventListener('beforeinstallprompt', (event) => {
  console.log('📱 PWA installation available');
  
  // Prevent the default browser install prompt
  event.preventDefault();
  
  // Store the event so we can trigger it later
  deferredPrompt = event;
  
  // Show custom install UI (optional - you can add a button later)
  showInstallButton();
});

// Handle successful installation
window.addEventListener('appinstalled', (event) => {
  console.log('✅ PWA installed successfully');
  
  // Clear the deferred prompt
  deferredPrompt = null;
  
  // Hide install button
  hideInstallButton();
  
  // Optional: Track installation for analytics
  // trackInstallation();
});

/**
 * Show custom install button/banner
 * Platform-aware installation UI
 */
function showInstallButton() {
  // Don't show if already installed
  if (isStandalone) {
    return;
  }
  
  // iOS: Show custom instructions (no beforeinstallprompt support)
  if (isIOS) {
    showIOSInstallInstructions();
    return;
  }
  
  // Android/Desktop: Show install banner and button
  const installBanner = document.getElementById('pwa-install-banner');
  if (installBanner) {
    installBanner.classList.remove('d-none');
    installBanner.style.display = 'block';
  }
  
  const installButton = document.getElementById('pwa-install-button');
  if (installButton) {
    installButton.classList.remove('d-none');
    installButton.style.display = 'inline-block';
    
    // Remove existing listeners to avoid duplicates
    const newButton = installButton.cloneNode(true);
    installButton.parentNode.replaceChild(newButton, installButton);
    
    // Add click handler to trigger installation
    newButton.addEventListener('click', handleInstallClick);
  }
  
  // Also handle banner button
  const bannerButton = document.getElementById('pwa-install-banner-button');
  if (bannerButton) {
    bannerButton.addEventListener('click', handleInstallClick);
  }
}

/**
 * Handle install button click
 */
async function handleInstallClick() {
  if (deferredPrompt) {
    try {
      // Show the browser's install prompt
      deferredPrompt.prompt();
      
      // Wait for user's response
      const { outcome } = await deferredPrompt.userChoice;
      
      if (outcome === 'accepted') {
        console.log('✅ User accepted installation');
        if (typeof showToast === 'function') {
          showToast('App installation started!', 'success');
        }
      } else {
        console.log('❌ User declined installation');
      }
      
      // Clear the deferred prompt
      deferredPrompt = null;
      hideInstallButton();
    } catch (error) {
      console.error('Install error:', error);
    }
  }
}

/**
 * Show iOS-specific install instructions
 */
function showIOSInstallInstructions() {
  const installBanner = document.getElementById('pwa-install-banner');
  if (installBanner) {
    const bannerContent = installBanner.querySelector('.d-flex');
    if (bannerContent) {
      bannerContent.innerHTML = `
        <div class="d-flex align-items-center">
          <i class="fas fa-mobile-alt me-2" style="font-size: 1.2rem;"></i>
          <div>
            <strong>Install FRCR Revision</strong>
            <div class="small mt-1">Tap <i class="fas fa-share"></i> Share → "Add to Home Screen"</div>
          </div>
        </div>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="alert" aria-label="Close"></button>
      `;
      installBanner.classList.remove('d-none');
      installBanner.style.display = 'block';
    }
  }
}

/**
 * Hide install button/banner after installation
 */
function hideInstallButton() {
  const installBanner = document.getElementById('pwa-install-banner');
  if (installBanner) {
    installBanner.style.display = 'none';
    installBanner.classList.add('d-none');
  }
  
  const installButton = document.getElementById('pwa-install-button');
  if (installButton) {
    installButton.style.display = 'none';
    installButton.classList.add('d-none');
  }
}

/**
 * Check if app is running as installed PWA
 * Useful for showing different UI based on installation state
 */
function isPWA() {
  return window.matchMedia('(display-mode: standalone)').matches ||
         window.navigator.standalone === true;
}

// Log PWA status on load
if (isPWA()) {
  console.log('✅ Running as installed PWA');
  // Hide install buttons if already installed
  hideInstallButton();
} else {
  console.log('ℹ️ Running in browser');
  // Check if we should show install prompt after a delay (better UX)
  setTimeout(() => {
    // Only show if not dismissed recently (check localStorage)
    const installDismissed = localStorage.getItem('pwa-install-dismissed');
    const dismissTime = installDismissed ? parseInt(installDismissed) : 0;
    const oneDayAgo = Date.now() - (24 * 60 * 60 * 1000);
    
    // Show if not dismissed in last 24 hours
    if (!installDismissed || dismissTime < oneDayAgo) {
      // iOS: Always show instructions (no beforeinstallprompt)
      if (isIOS && !isStandalone) {
        showIOSInstallInstructions();
      }
    }
  }, 3000); // Show after 3 seconds
}

// Handle banner dismissal
document.addEventListener('DOMContentLoaded', () => {
  const installBanner = document.getElementById('pwa-install-banner');
  if (installBanner) {
    installBanner.addEventListener('closed.bs.alert', () => {
      // Store dismissal time
      localStorage.setItem('pwa-install-dismissed', Date.now().toString());
    });
  }
});

/**
 * Network status detection
 * Shows online/offline status to users
 */
window.addEventListener('online', () => {
  console.log('✅ Back online');
  // Optional: Show notification or update UI
  const offlineAlert = document.getElementById('offline-alert');
  if (offlineAlert) {
    offlineAlert.style.display = 'none';
  }
});

window.addEventListener('offline', () => {
  console.log('⚠️ Went offline');
  // Optional: Show notification or update UI
  const offlineAlert = document.getElementById('offline-alert');
  if (offlineAlert) {
    offlineAlert.style.display = 'block';
  }
});
