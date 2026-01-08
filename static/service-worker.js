/**
 * FRCR Examiner Service Worker
 * Provides offline capabilities and PWA installation
 * SAFE: Only caches static files, never interferes with database operations
 */

const CACHE_NAME = 'frcr-examiner-v1';
const STATIC_CACHE = 'frcr-static-v1';

// Files to cache for offline use (static assets only)
const STATIC_ASSETS = [
  '/',
  '/static/style.css',
  '/static/config.js',
  '/static/manifest.json',
  '/static/images/icon-192x192.png',
  '/static/images/icon-512x512.png',
  // Bootstrap & Font Awesome are loaded from CDN, cached by browser automatically
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
  console.log('[Service Worker] Installing...');
  
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => {
        console.log('[Service Worker] Caching static assets');
        // Use addAll with error handling for individual files
        return Promise.all(
          STATIC_ASSETS.map((url) => {
            return cache.add(url).catch((err) => {
              console.warn(`[Service Worker] Failed to cache ${url}:`, err);
            });
          })
        );
      })
      .then(() => {
        console.log('[Service Worker] Installation complete');
        return self.skipWaiting(); // Activate immediately
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[Service Worker] Activating...');
  
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          // Delete old caches
          if (cacheName !== STATIC_CACHE && cacheName !== CACHE_NAME) {
            console.log('[Service Worker] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
    .then(() => {
      console.log('[Service Worker] Activation complete');
      return self.clients.claim(); // Take control immediately
    })
  );
});

// Fetch event - handle requests
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  
  // CRITICAL: Always use network for API calls (database operations)
  // This ensures database integrity - no offline data changes!
  if (url.pathname.startsWith('/api/') || 
      request.method !== 'GET' ||
      url.pathname.includes('/setup/') ||
      url.pathname.includes('/exam/') ||
      url.pathname.includes('/admin/')) {
    
    // Network-only for all dynamic content and API calls
    event.respondWith(
      fetch(request).catch(() => {
        // If offline, return a proper error response
        return new Response(
          JSON.stringify({ 
            error: 'Internet connection required for this operation',
            offline: true 
          }),
          {
            status: 503,
            statusText: 'Service Unavailable',
            headers: { 'Content-Type': 'application/json' }
          }
        );
      })
    );
    return;
  }
  
  // For static assets: Cache first, then network
  event.respondWith(
    caches.match(request)
      .then((cachedResponse) => {
        if (cachedResponse) {
          // Return cached version
          return cachedResponse;
        }
        
        // Not in cache, fetch from network
        return fetch(request)
          .then((response) => {
            // Don't cache non-successful responses
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }
            
            // Clone the response (can only be consumed once)
            const responseToCache = response.clone();
            
            // Cache for future use
            caches.open(STATIC_CACHE)
              .then((cache) => {
                cache.put(request, responseToCache);
              });
            
            return response;
          })
          .catch(() => {
            // Network failed and no cache - show offline message
            if (request.destination === 'document') {
              return new Response(
                `
                <!DOCTYPE html>
                <html>
                <head>
                  <title>Offline - FRCR Examiner</title>
                  <style>
                    body { 
                      font-family: Arial, sans-serif; 
                      display: flex; 
                      align-items: center; 
                      justify-content: center; 
                      height: 100vh; 
                      margin: 0;
                      background: #f8f9fa;
                    }
                    .offline-message {
                      text-align: center;
                      padding: 2rem;
                      background: white;
                      border-radius: 8px;
                      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    }
                    .offline-icon { font-size: 4rem; margin-bottom: 1rem; }
                    h1 { color: #333; }
                    p { color: #666; }
                  </style>
                </head>
                <body>
                  <div class="offline-message">
                    <div class="offline-icon">📡</div>
                    <h1>You're Offline</h1>
                    <p>FRCR Examiner requires an internet connection.</p>
                    <p>Please check your connection and try again.</p>
                  </div>
                </body>
                </html>
                `,
                {
                  headers: { 'Content-Type': 'text/html' }
                }
              );
            }
            
            return new Response('Offline', { status: 503 });
          });
      })
  );
});

// Background sync (for future enhancements)
self.addEventListener('sync', (event) => {
  console.log('[Service Worker] Background sync:', event.tag);
  // Currently not used, but available for future offline-to-online sync features
});

// Push notifications (for future enhancements)
self.addEventListener('push', (event) => {
  console.log('[Service Worker] Push notification received');
  // Currently not used, but available for future notification features
});
