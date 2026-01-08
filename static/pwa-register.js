/**
 * PWA Service Worker Registration
 * Registers the service worker and handles installation prompts
 */

// Check if service workers are supported by the browser
if ('serviceWorker' in navigator) {
  
  // Register service worker when page loads
  window.addEventListener('load', () => {
    
    navigator.serviceWorker.register('/static/service-worker.js')
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
 * You can customize this to match your app's design
 */
function showInstallButton() {
  // Check if there's an element with id="pwa-install-banner"
  const installBanner = document.getElementById('pwa-install-banner');
  if (installBanner) {
    installBanner.style.display = 'block';
  }
  
  // Check if there's a button with id="pwa-install-button"
  const installButton = document.getElementById('pwa-install-button');
  if (installButton) {
    installButton.style.display = 'inline-block';
    
    // Add click handler to trigger installation
    installButton.addEventListener('click', async () => {
      if (deferredPrompt) {
        // Show the browser's install prompt
        deferredPrompt.prompt();
        
        // Wait for user's response
        const { outcome } = await deferredPrompt.userChoice;
        
        if (outcome === 'accepted') {
          console.log('✅ User accepted installation');
        } else {
          console.log('❌ User declined installation');
        }
        
        // Clear the deferred prompt
        deferredPrompt = null;
      }
    });
  }
}

/**
 * Hide install button/banner after installation
 */
function hideInstallButton() {
  const installBanner = document.getElementById('pwa-install-banner');
  if (installBanner) {
    installBanner.style.display = 'none';
  }
  
  const installButton = document.getElementById('pwa-install-button');
  if (installButton) {
    installButton.style.display = 'none';
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
} else {
  console.log('ℹ️ Running in browser');
}

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
