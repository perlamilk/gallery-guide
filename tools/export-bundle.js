// Export everything the harvester collected as ONE file: mfa-harvest.bundle
// Run in any tab on collections.mfa.org (it reads the same browser storage as harvest-mfa.js).
// One file, so Chrome never asks "allow multiple downloads?".
// Layout: "MFAHARV1" | uint32 LE length of JSON | JSON | image bytes
// Each artwork's img = { o, l } points into the image bytes; tools/import_bundle.py repacks them.
(async () => {
  const db = await new Promise((res, rej) => {
    const r = indexedDB.open('mfa-harvest');
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
  const all = store => new Promise((res, rej) => {
    const out = new Map();
    const r = db.transaction(store).objectStore(store).openCursor();
    r.onsuccess = () => { const c = r.result; if (!c) return res(out); out.set(c.key, c.value); c.continue(); };
    r.onerror = () => rej(r.error);
  });
  const records = [...(await all('records')).values()].filter(r => r && r.onView);
  const images = await all('images');
  db.close();
  records.sort((a, b) => String(a.gallery ?? 'zzz').localeCompare(String(b.gallery ?? 'zzz'), undefined, { numeric: true }));
  const parts = [];
  let size = 0, withImage = 0;
  for (const r of records) {
    delete r._media;
    delete r.img;
    const img = images.get(r.id);
    if (img && img.size) { r.img = { o: size, l: img.size }; parts.push(img); size += img.size; withImage++; }
  }
  const doc = {
    source: 'MFA Boston online collection (collections.mfa.org), works marked On View',
    checked: new Date().toISOString().slice(0, 10),
    count: records.length,
    artworks: records,
  };
  const json = new TextEncoder().encode(JSON.stringify(doc));
  const head = new Uint8Array(12);
  head.set(new TextEncoder().encode('MFAHARV1'));
  new DataView(head.buffer).setUint32(8, json.length, true);
  const blob = new Blob([head, json, ...parts], { type: 'application/octet-stream' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'mfa-harvest.bundle';
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 60000);
  return JSON.stringify({ works: records.length, withImage, megabytes: Math.round(blob.size / 1e6) });
})();
