// DevBots Dashboard Service Worker
const CACHE_NAME = 'devbots-dashboard-v1';
const ASSETS = [
    '/',
    '/index.html',
    '/projects.html',
    '/bots.html',
    '/activity.html',
    '/calendar.html',
    '/notes.html',
    '/reports.html',
    '/report.html',
    '/css/reset.css',
    '/css/variables.css',
    '/css/base.css',
    '/css/layout.css',
    '/css/components.css',
    '/css/responsive.css',
    '/js/config.js',
    '/js/utils.js',
    '/js/api.js',
    '/js/ui.js',
    '/js/components.js',
    '/js/dashboard.js',
    '/js/projects.js',
    '/js/project-admin.js',
    '/js/report-generator.js',
    '/js/bots.js',
    '/js/reports.js',
    '/js/activity.js',
    '/js/calendar.js',
    '/js/notes.js',
    '/js/report-viewer.js',
    '/manifest.json'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                return cache.addAll(ASSETS);
            })
            .catch((error) => {
                console.error('Cache installation failed:', error);
            })
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((cacheName) => {
                        if (cacheName !== CACHE_NAME) {
                            return caches.delete(cacheName);
                        }
                    })
                );
            })
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    // Skip non-GET requests
    if (event.request.method !== 'GET') {
        return;
    }

    // Skip API routes and report files - always network first
    if (event.request.url.includes('/api/') || 
        event.request.url.includes('/reports/')) {
        event.respondWith(
            fetch(event.request).catch(() => {
                return caches.match(event.request);
            })
        );
        return;
    }

    event.respondWith(
        caches.match(event.request)
            .then((cachedResponse) => {
                if (cachedResponse) {
                    // Serve from cache, but update in background
                    fetchAndCache(event.request);
                    return cachedResponse;
                }
                return fetchAndCache(event.request);
            })
            .catch(() => {
                // If both fail, return offline page for HTML requests
                if (event.request.headers.get('accept').includes('text/html')) {
                    return caches.match('/');
                }
            })
    );
});

function fetchAndCache(request) {
    return fetch(request)
        .then((response) => {
            // Don't cache non-successful responses
            if (!response || response.status !== 200 || response.type !== 'basic') {
                return response;
            }

            // Clone response since we can only consume it once
            const responseToCache = response.clone();

            caches.open(CACHE_NAME)
                .then((cache) => {
                    cache.put(request, responseToCache);
                });

            return response;
        })
        .catch((error) => {
            console.error('Fetch failed:', error);
            throw error;
        });
}
