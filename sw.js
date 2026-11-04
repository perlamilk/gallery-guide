// Offline support.
// - On install: caches the app shell and data files; pictures are kept from the last version, new ones download after.
// - Data files: network first (so updated JSON arrives when online), cache as fallback.
// - Everything else: cache first, then network (and cache what comes back).
// Bump VERSION whenever app files change so phones pick up the new version.

const VERSION = 'v78';
const CACHE = `gallery-guide-${VERSION}`;

const SHELL = [
  './',
  'index.html',
  'guide.html',
  'css/shell.css',
  'js/shell.js',
  'js/images.js',
  'js/notice.js',
  'js/offline.js',
  'css/notice.css',
  'data/notice.json',
  'vendor/maplibre-gl.js',
  'vendor/maplibre-gl.css',
  'data/museums.json',
  'data/discover.json',
  'data/guides.json',
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
  'js/site.js',
  'data/wadsworth/floors.json',
  'data/wadsworth/artworks.json',
  'data/harvard/floors.json',
  'data/harvard/artworks.json',
  'data/worcester/floors.json',
  'data/worcester/artworks.json',
  'data/gardner/floors.json',
  'data/gardner/artworks.json',
  'data/clark/floors.json',
  'data/clark/artworks.json',
  'data/risd/floors.json',
  'data/risd/artworks.json',
  'data/pem/floors.json',
  'data/pem/artworks.json',
  'data/ycba/floors.json',
  'data/ycba/artworks.json',
  'data/yale/floors.json',
  'data/yale/artworks.json',
  'data/massmoca/floors.json',
  'data/massmoca/artworks.json',
  'data/ica/floors.json',
  'data/ica/artworks.json',
  'data/nbmaa/floors.json',
  'data/nbmaa/artworks.json',
  'data/smith/floors.json',
  'data/smith/artworks.json',
  'data/decordova/floors.json',
  'data/decordova/artworks.json',
  'data/addison/floors.json',
  'data/addison/artworks.json',
  'data/davis/floors.json',
  'data/davis/artworks.json',
  'data/mead/floors.json',
  'data/mead/artworks.json',
  'data/flogris/floors.json',
  'data/flogris/artworks.json',
  'data/hillstead/floors.json',
  'data/hillstead/artworks.json',
  'data/mystic/floors.json',
  'data/mystic/artworks.json',
  'data/newport/floors.json',
  'data/newport/artworks.json',
  'data/breakers/floors.json',
  'data/breakers/artworks.json',
  'data/nrm/floors.json',
  'data/nrm/artworks.json',
  'data/marble/floors.json',
  'data/marble/artworks.json',
  'data/jfk/floors.json',
  'data/jfk/artworks.json',
  'data/elms/floors.json',
  'data/elms/artworks.json',
  'data/rosecliff/floors.json',
  'data/rosecliff/artworks.json',
  'data/mos/floors.json',
  'data/mos/artworks.json',
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
        // keep pictures and the offline pack across updates, so nothing downloads twice
        if (/\/data\/(wadsworth\/)?(images|notice)\//.test(req.url) && !(await cache.match(req))) await cache.put(req, await prev.match(req));
      }
      await caches.delete(name);
    }
    await self.clients.claim();
    cacheArtworkImages(cache); // new pictures download in the background
  })());
});

// the app asks which version is running (Check for Updates)
self.addEventListener('message', event => {
  if (event.data === 'version') event.ports[0]?.postMessage(VERSION);
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
      return res;
    }
    // A page load that the sign-in screen redirects goes through, so the browser can show the login.
    // Data that comes back as an error (signed out, server hiccup) falls back to the saved copy.
    if (req.mode === 'navigate') return res;
    return (await cache.match(req, { ignoreSearch: true })) ?? res;
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
    // a whole-file request (the offline pack download) goes straight to the network; the page stores it
    if (!range) return fetch(req.url);
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
    // Pictures on a museum's own server (NBMAA, the Addison) are not fetched in bulk: thousands of requests would burden it.
    const urls = [...new Set((doc.artworks ?? []).map(a => a.image || a.img?.p).filter(Boolean))]
      .filter(u => !u.startsWith('https://ink.nbmaa.org/') && !u.startsWith('https://accessaddison.andover.edu/'));
    for (const u of urls) {
      if (!(await cache.match(u))) {
        try { await cache.add(u); } catch { /* skip a missing image, keep going */ }
      }
    }
  } catch { /* offline during install: images will be cached as they are viewed */ }
}
