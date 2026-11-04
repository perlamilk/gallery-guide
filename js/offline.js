// Offline pack: download everything a museum's guide needs before you go
// (museum Wi-Fi and cell signal are often poor). Files go into the same cache the
// service worker serves from, so the guide then works with no connection at all.

// The pack's file list and sizes come from data/pack-<museum>.json (written by tools/build_pack.py at
// each publish), so the app can say how big it is and show progress by megabytes, not file count.
// `site` is one of SITES in site.js (MFA Boston, the Wadsworth).
export async function packFiles(site) {
  const list = site.pack;
  try {
    const r = await fetch(list, { cache: 'no-store' });
    if (r.ok) { const p = await r.json(); return { files: [{ u: list, s: 0 }, ...p.files], bytes: p.bytes, works: p.works, notice: p.notice }; }
  } catch { /* offline: fall back to the cached copy */ }
  const cached = await caches.match(list, { ignoreSearch: true });
  const p = cached ? await cached.json() : { files: [], bytes: 0, works: 0, notice: 0 };
  return { files: [{ u: list, s: 0 }, ...p.files], bytes: p.bytes, works: p.works, notice: p.notice };
}

async function cacheName() {
  const sw = navigator.serviceWorker?.controller;
  if (sw) {
    const v = await new Promise(res => {
      const ch = new MessageChannel();
      ch.port1.onmessage = e => res(e.data);
      sw.postMessage('version', [ch.port2]);
      setTimeout(() => res(null), 1500);
    });
    if (v) return `gallery-guide-${v}`;
  }
  const keys = (await caches.keys()).filter(k => k.startsWith('gallery-guide-'));
  return keys.sort().at(-1) ?? 'gallery-guide-offline';
}

export async function packStatus(site) {
  if (!('caches' in window)) return { supported: false };
  const { files, bytes, works, notice } = await packFiles(site);
  const hits = await Promise.all(files.map(f => caches.match(f.u, { ignoreSearch: true })));
  const have = files.filter((f, k) => hits[k]);
  const haveBytes = have.reduce((t, f) => t + f.s, 0);
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(site.packKey) || 'null'); } catch { /* storage off */ }
  return { supported: true, total: files.length, have: have.length, bytes, haveBytes, ready: files.length > 0 && have.length === files.length, works, notice, saved };
}

// Downloads what's missing, 4 at a time. onProgress({ done, total, bytes, totalBytes }).
// Stop with the returned controller; whatever finished stays saved, and the next run continues.
export function downloadPack(site, onProgress) {
  let stopped = false;
  const run = (async () => {
    navigator.storage?.persist?.().catch(() => {});   // ask the phone not to clear it when space runs low
    const cache = await caches.open(await cacheName());
    const { files, bytes: totalBytes } = await packFiles(site);
    const missing = [];
    let doneBytes = 0;
    for (const f of files) {
      if (await caches.match(f.u, { ignoreSearch: true })) doneBytes += f.s;
      else missing.push(f);
    }
    const total = files.length;
    let done = total - missing.length, failed = 0;
    onProgress?.({ done, total, bytes: doneBytes, totalBytes });
    const next = async () => {
      while (!stopped && missing.length) {
        const f = missing.shift();
        try {
          const res = await fetch(f.u, { cache: 'no-store' });
          if (!res.ok) throw new Error(res.status);
          const blob = await res.blob();
          await cache.put(f.u, new Response(blob, { headers: { 'Content-Type': res.headers.get('Content-Type') || 'application/octet-stream' } }));
          doneBytes += f.s || blob.size;
          done++;
        } catch { failed++; }
        onProgress?.({ done, total, bytes: doneBytes, totalBytes });
      }
    };
    await Promise.all([next(), next(), next(), next()]);
    const ok = !stopped && done === total;
    if (ok) {
      try { localStorage.setItem(site.packKey, JSON.stringify({ at: new Date().toISOString(), total })); } catch { /* fine */ }
    }
    return { ok, done, total, failed, stopped };
  })();
  return { done: run, stop: () => { stopped = true; } };
}

export const mb = bytes => (bytes < 1e6 ? `${Math.max(1, Math.round(bytes / 1e3))} KB` : `${(bytes / 1e6).toFixed(bytes < 1e7 ? 1 : 0)} MB`);
