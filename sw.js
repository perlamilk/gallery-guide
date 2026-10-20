// Offline support.
// - On install: caches the app shell and data files; pictures are kept from the last version, new ones download after.
// - Data files: network first (so updated JSON arrives when online), cache as fallback.
// - Everything else: cache first, then network (and cache what comes back).
// Bump VERSION whenever app files change so phones pick up the new version.

const VERSION = 'v16';
const CACHE = `gallery-guide-${VERSION}`;

const SHELL = [
  './',
  'index.html',
  'manifest.webmanifest',
  'css/app.css',
  'js/app.js',
  'js/config.js',
  'js/data.js',
  'js/map3d.js',
  'js/icons.js',
  'js/visits.js',
  'js/routes.js',
  'vendor/three.module.min.js',
  'vendor/OrbitControls.js',
  'icons/apple-touch-icon.png',
  'icons/icon-192.png',
  'icons/icon-512.png',
  'data/floors.json',
  'data/artworks.json',
  'data/tours.json',
  'data/curiosities.json',
];

// Install only the app itself, so an update is quick and takes over right away;
// pictures already saved are carried over from the previous version instead of downloaded again.
self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(SHELL.map(u => new Request(u, { cache: 'reload' })));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    const old = (await caches.keys()).filter(k => k.startsWith('gallery-guide-') && k !== CACHE);
    for (const name of old) {
      const prev = await caches.open(name);
      for (const req of await prev.keys()) {
        if (/\/data\/images\//.test(req.url) && !(await cache.match(req))) await cache.put(req, await prev.match(req));
      }
      await caches.delete(name);
    }
    await self.clients.claim();
    cacheArtworkImages(cache); // new pictures download in the background
  })());
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // e.g. links to the MFA site

  if (url.pathname.endsWith('.bin')) {
    event.respondWith(packPiece(req));
  } else if (req.mode === 'navigate') {
    event.respondWith(networkFirst(req, 'index.html'));
  } else if (url.pathname.endsWith('.json')) {
    event.respondWith(networkFirst(req));
  } else {
    event.respondWith(cacheFirst(req));
  }
});

async function cacheFirst(req) {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(req, { ignoreSearch: true });
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) cache.put(req, res.clone());
  return res;
}

async function networkFirst(req, fallbackPath) {
  const cache = await caches.open(CACHE);
  try {
    const res = await fetch(req);
    if (res.ok) {
      cache.put(req, res.clone());
      if (req.url.endsWith('artworks.json')) cacheArtworkImages(cache, res.clone());
    }
    return res;
  } catch {
    return (await cache.match(req, { ignoreSearch: true }))
      ?? (fallbackPath && await cache.match(fallbackPath))
      ?? Response.error();
  }
}

// Image packs: answer "give me bytes X–Y" from the cached pack; fetch and cache the pack if it's missing.
const packDownloads = new Set();
async function packPiece(req) {
  const cache = await caches.open(CACHE);
  const full = await cache.match(req.url, { ignoreSearch: true });
  if (!full) {
    const range = req.headers.get('Range');
    // online and not cached yet: answer this piece straight away, store the whole pack once in the background
    if (!packDownloads.has(req.url)) {
      packDownloads.add(req.url);
      fetch(req.url).then(res => res.ok && cache.put(req.url, res)).catch(() => {}).finally(() => packDownloads.delete(req.url));
    }
    return fetch(req.url, range ? { headers: { Range: range } } : {});
  }
  const range = req.headers.get('Range');
  const m = range && range.match(/bytes=(\d+)-(\d+)?/);
  if (!m) return full;
  const blob = await full.blob();
  const start = Number(m[1]);
  const end = m[2] ? Number(m[2]) + 1 : blob.size;
  return new Response(blob.slice(start, end), {
    status: 206,
    headers: { 'Content-Type': 'application/octet-stream', 'Content-Range': `bytes ${start}-${end - 1}/${blob.size}` },
  });
}

// Download any artwork images not yet cached (also runs when a new artworks.json arrives).
async function cacheArtworkImages(cache, response) {
  try {
    const doc = await (response ?? await fetch('data/artworks.json', { cache: 'no-store' })).json();
    const urls = [...new Set((doc.artworks ?? []).map(a => a.image || a.img?.p).filter(Boolean))];
    for (const u of urls) {
      if (!(await cache.match(u))) {
        try { await cache.add(u); } catch { /* skip a missing image, keep going */ }
      }
    }
  } catch { /* offline during install: images will be cached as they are viewed */ }
}
