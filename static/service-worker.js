/**
 * RadInsights Service Worker
 * Provides offline capabilities and PWA installation
 * SAFE: Only caches static files, never interferes with database operations
 */

const CACHE_VERSION = 'v13';
const CACHE_NAME = `frcr-revision-${CACHE_VERSION}`;
const STATIC_CACHE = `frcr-static-${CACHE_VERSION}`;
const PAGES_CACHE = `frcr-pages-${CACHE_VERSION}`;

// Files to cache immediately on install (critical assets)
const STATIC_ASSETS = [
  '/',
  '/static/style.css',
  '/static/config.js',
  '/static/js/global-search.js',
  '/static/js/speech-to-text.js',
  '/manifest.json',
  // Icons are now on Cloudinary, cached by browser automatically
  // Bootstrap & Font Awesome are loaded from CDN, cached by browser automatically
];

// Pages to cache for offline viewing (read-only pages)
const CACHEABLE_PAGES = [
  '/',
  '/modules',
  '/cases',
  '/auth/login',
  '/auth/register',
  '/about',
  '/privacy',
  '/terms'
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
  console.log('[Service Worker] Installing version', CACHE_VERSION);
  
  event.waitUntil(
    Promise.all([
      // Cache static assets
      caches.open(STATIC_CACHE).then((cache) => {
        console.log('[Service Worker] Caching static assets');
        return Promise.all(
          STATIC_ASSETS.map((url) => {
            return cache.add(url).catch((err) => {
              console.warn(`[Service Worker] Failed to cache ${url}:`, err);
            });
          })
        );
      }),
      // Pre-cache important pages
      caches.open(PAGES_CACHE).then((cache) => {
        console.log('[Service Worker] Pre-caching pages');
        return Promise.all(
          CACHEABLE_PAGES.map((url) => {
            return cache.add(url).catch((err) => {
              console.warn(`[Service Worker] Failed to pre-cache ${url}:`, err);
            });
          })
        );
      })
    ]).then(() => {
      console.log('[Service Worker] Installation complete');
      return self.skipWaiting(); // Activate immediately
    })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[Service Worker] Activating version', CACHE_VERSION);
  
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          // Delete old caches (keep only current version)
          if (cacheName !== STATIC_CACHE && 
              cacheName !== PAGES_CACHE && 
              cacheName !== CACHE_NAME &&
              cacheName.startsWith('frcr-')) {
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

  // Skip cross-origin requests — let the browser handle them directly.
  // CDN resources (Bootstrap, Font Awesome, Cloudinary) are governed by
  // style-src/script-src/img-src CSP directives, not connect-src.
  // If the SW intercepts them, its own connect-src 'self' blocks the fetch.
  if (url.origin !== self.location.origin) {
    return;
  }

  // CRITICAL: Always use network for API calls (database operations)
  // This ensures database integrity - no offline data changes!
  if (url.pathname.startsWith('/api/') || 
      request.method !== 'GET' ||
      url.pathname.includes('/setup/') ||
      url.pathname.includes('/exam/') ||
      url.pathname.includes('/admin/') ||
      url.pathname.includes('/stack/upload')) {
    
    // Network-only for all dynamic content and API calls
    event.respondWith(
      fetch(request).catch((err) => {
        // Fetch failed: offline, timeout, or connection reset (e.g. large upload)
        const isUpload = request.method === 'POST' && url.pathname.includes('/stack/upload');
        const errorMsg = isUpload
          ? 'Upload failed—connection may have timed out. Try fewer files or one series at a time.'
          : 'Internet connection required for this operation';
        return new Response(
          JSON.stringify({ 
            error: errorMsg,
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
  
  // For HTML pages: Network first, fallback to cache
  if (request.destination === 'document' || 
      (request.headers.get('accept') && request.headers.get('accept').includes('text/html'))) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Cache successful responses
          if (response && response.status === 200 && response.type === 'basic') {
            const responseToCache = response.clone();
            caches.open(PAGES_CACHE).then((cache) => {
              cache.put(request, responseToCache);
            });
          }
          return response;
        })
        .catch(() => {
          // Network failed, try cache
          return caches.match(request).then((cachedResponse) => {
            if (cachedResponse) {
              return cachedResponse;
            }
            // No cache, show offline page
            return new Response(
              `
              <!DOCTYPE html>
              <html>
              <head>
                <title>Offline - RadInsights</title>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                  body { 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; 
                    display: flex; 
                    align-items: center; 
                    justify-content: center; 
                    height: 100vh; 
                    margin: 0;
                    background: linear-gradient(135deg, #5E899E 0%, #4D7A8D 100%);
                    color: #fff;
                  }
                  .offline-message {
                    text-align: center;
                    padding: 3rem 2rem;
                    background: rgba(255, 255, 255, 0.95);
                    border-radius: 12px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
                    max-width: 400px;
                    color: #333;
                  }
                  .offline-icon { font-size: 4rem; margin-bottom: 1rem; }
                  h1 { color: #5E899E; margin-bottom: 1rem; }
                  p { color: #666; line-height: 1.6; }
                  .retry-btn {
                    margin-top: 1.5rem;
                    padding: 10px 20px;
                    background: #5E899E;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 1rem;
                  }
                  .retry-btn:hover { background: #4D7A8D; }
                </style>
              </head>
              <body>
                <div class="offline-message">
                  <div class="offline-icon">📡</div>
                  <h1>You're Offline</h1>
                  <p>RadInsights requires an internet connection for full functionality.</p>
                  <p>Some cached content may be available.</p>
                  <button class="retry-btn" onclick="window.location.reload()">Retry</button>
                </div>
              </body>
              </html>
              `,
              {
                headers: { 'Content-Type': 'text/html' }
              }
            );
          });
        })
    );
    return;
  }
  
  // For static assets: Cache first, then network (stale-while-revalidate)
  event.respondWith(
    caches.match(request)
      .then((cachedResponse) => {
        // Return cached version immediately
        if (cachedResponse) {
          // Update cache in background (stale-while-revalidate)
          fetch(request)
            .then((response) => {
              if (response && response.status === 200 && response.type === 'basic') {
                const responseToCache = response.clone();
                caches.open(STATIC_CACHE).then((cache) => {
                  cache.put(request, responseToCache);
                });
              }
            })
            .catch(() => {
              // Network failed, but we have cache, so that's fine
            });
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
            // Network failed and no cache
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
