// AJCC TNM Cookie Sync - Background Service Worker

const AJCC_DOMAINS = ['ajccstaging.org', 'login.facs.org'];
const LOCAL_APP_URL = 'http://localhost:5000';

// Listen for cookie changes on AJCC domains
chrome.cookies.onChanged.addListener(async (changeInfo) => {
  const cookie = changeInfo.cookie;
  
  // Only process AJCC-related cookies
  if (!AJCC_DOMAINS.some(domain => cookie.domain.includes(domain.replace('https://', '')))) {
    return;
  }
  
  // Don't process removed cookies (only additions/updates)
  if (changeInfo.removed && changeInfo.cause !== 'overwrite') {
    return;
  }
  
  console.log(`[AJCC Sync] Cookie changed: ${cookie.name} on ${cookie.domain}`);
  
  // Sync cookies to local app
  await syncCookiesToApp();
});

// Sync all AJCC cookies to the local Flask app
async function syncCookiesToApp() {
  try {
    const cookies = await getAllAJCCCookies();
    
    if (cookies.length === 0) {
      console.log('[AJCC Sync] No AJCC cookies to sync');
      updateBadge('?', '#888');
      return;
    }
    
    console.log(`[AJCC Sync] Syncing ${cookies.length} cookies to local app...`);
    
    const response = await fetch(`${LOCAL_APP_URL}/api/admin/tnm/extension-cookies`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        cookies: cookies,
        timestamp: Date.now()
      })
    });
    
    if (response.ok) {
      const data = await response.json();
      if (data.success) {
        console.log('[AJCC Sync] Cookies synced successfully');
        updateBadge('✓', '#4CAF50');
        
        // Store last sync time
        chrome.storage.local.set({
          lastSync: Date.now(),
          cookieCount: cookies.length
        });
      } else {
        console.error('[AJCC Sync] Server error:', data.error);
        updateBadge('!', '#f44336');
      }
    } else {
      console.error('[AJCC Sync] HTTP error:', response.status);
      updateBadge('!', '#f44336');
    }
  } catch (error) {
    console.error('[AJCC Sync] Error syncing cookies:', error);
    updateBadge('×', '#f44336');
  }
}

// Get all cookies from AJCC domains
async function getAllAJCCCookies() {
  const allCookies = [];
  
  for (const domain of AJCC_DOMAINS) {
    try {
      const cookies = await chrome.cookies.getAll({ domain: domain });
      allCookies.push(...cookies.map(c => ({
        name: c.name,
        value: c.value,
        domain: c.domain,
        path: c.path,
        secure: c.secure,
        httpOnly: c.httpOnly,
        expirationDate: c.expirationDate
      })));
    } catch (error) {
      console.error(`[AJCC Sync] Error getting cookies for ${domain}:`, error);
    }
  }
  
  return allCookies;
}

// Update extension badge
function updateBadge(text, color) {
  try {
    // Use simple ASCII characters for badge (emojis can cause issues)
    const safeText = text === '✓' ? 'OK' : text === '×' ? 'X' : text;
    chrome.action.setBadgeText({ text: safeText });
    chrome.action.setBadgeBackgroundColor({ color: color });
  } catch (error) {
    console.error('[AJCC Sync] Error updating badge:', error);
  }
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'syncNow') {
    syncCookiesToApp().then(() => {
      sendResponse({ success: true });
    }).catch(error => {
      sendResponse({ success: false, error: error.message });
    });
    return true; // Keep message channel open for async response
  }
  
  if (message.action === 'getStatus') {
    chrome.storage.local.get(['lastSync', 'cookieCount'], (data) => {
      getAllAJCCCookies().then(cookies => {
        sendResponse({
          lastSync: data.lastSync,
          cookieCount: cookies.length,
          isLoggedIn: cookies.some(c => 
            c.name.includes('session') || 
            c.name.includes('okta') || 
            c.name.includes('idx')
          )
        });
      });
    });
    return true;
  }
  
  if (message.action === 'openAJCC') {
    chrome.tabs.create({ url: 'https://ajccstaging.org/en/login' });
    sendResponse({ success: true });
    return false;
  }
});

// Initial sync on extension load (with error handling)
(async () => {
  try {
    await syncCookiesToApp();
  } catch (error) {
    console.log('[AJCC Sync] Initial sync skipped (Flask app may not be running):', error.message);
  }
})();

console.log('[AJCC Sync] Background service worker started');
