/* Service worker for the Jarvis HUD.
 *
 * Two strategies on purpose:
 *   - the app shell is cache-first, so a cold start on a phone is instant and
 *     works offline
 *   - data/*.json is NETWORK-first, because a dashboard that serves yesterday's
 *     prices out of the cache is worse than no dashboard; the cache is only the
 *     offline fallback
 *
 * Bump CACHE whenever a shell file changes, or phones keep the old build.
 */
const CACHE = 'wilson-jarvis-v4';

const SHELL = [
  './',
  './index.html',
  './manifest.json',
  './icon-192.png',
  './icon-512.png',
  './icon-maskable-192.png',
  './icon-maskable-512.png'
];

const DATA = [
  './data/status.json',
  './data/watchlist.json',
  './data/memory.json',
  './data/queue.json',
  './data/commands.json'
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(SHELL);
    // Best effort: one missing data file must not break the install.
    await Promise.all(DATA.map((u) => cache.add(u).catch(() => {})));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.includes('/data/')) {
    event.respondWith((async () => {
      try {
        const fresh = await fetch(req, { cache: 'no-store' });
        if (fresh && fresh.status === 200) {
          const cache = await caches.open(CACHE);
          cache.put(req, fresh.clone());
        }
        return fresh;
      } catch (err) {
        const cached = await caches.match(req);
        if (cached) return cached;
        throw err;
      }
    })());
    return;
  }

  event.respondWith((async () => {
    const cached = await caches.match(req);
    const network = fetch(req).then((res) => {
      if (res && res.status === 200) {
        caches.open(CACHE).then((cache) => cache.put(req, res.clone()));
      }
      return res;
    }).catch(() => cached);
    return cached || network;
  })());
});
