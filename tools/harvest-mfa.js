/*
  MFA on-view harvester - run it yourself, in your own browser.

  1. Open https://collections.mfa.org in Chrome (or Safari) in its own window.
  2. Open the console: Chrome  Cmd+Option+J  |  Safari  Cmd+Option+C (turn on Develop menu first).
     Chrome asks you to type  allow pasting  the first time.
  3. Paste this whole file and press Enter. A small panel appears at the bottom right. Click Start.

  It reads every work marked "On view": first the search result pages, then each work's page,
  then a small copy of each image. One request at a time with a pause between them, so the site
  isn't overloaded. If the site answers with an error it waits and slows down; after repeated errors
  it stops and keeps what it has. Progress is saved in this browser: paste the script again and click
  Start to continue where it stopped.

  When it's done, click Download. You get:
    artworks.json           -> replaces mfa-guide/data/artworks.json
    images-001.bin, ...       -> go into mfa-guide/data/images/
  (the browser may ask to allow several downloads: allow it)
*/
(() => {
  const CONFIG = {
    pause: 5000,           // ms between requests (the site blocks faster harvesting)
    imageMax: 420,         // longest side of saved images, px
    imageQuality: 0.72,    // JPEG quality
    packSize: 15e6,        // bytes per image pack file (GitHub's web upload limit is 25 MB)
    perPage: 12,           // results per search page on the site
  };
  const SEARCH = '/search/objects/*/*?filter=onview%3Atrue';

  // ---------- storage (IndexedDB, so progress survives closing the tab) ----------
  const DB_NAME = 'mfa-harvest';
  const open = () => new Promise((res, rej) => {
    const r = indexedDB.open(DB_NAME, 1);
    r.onupgradeneeded = () => {
      const db = r.result;
      for (const s of ['ids', 'records', 'images', 'meta']) if (!db.objectStoreNames.contains(s)) db.createObjectStore(s);
    };
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
  let db;
  const tx = (store, mode, fn) => new Promise((res, rej) => {
    const t = db.transaction(store, mode);
    const out = fn(t.objectStore(store));
    // a request's result is the value (undefined when nothing is stored under that key)
    t.oncomplete = () => res(out instanceof IDBRequest ? out.result : out);
    t.onerror = () => rej(t.error);
  });
  const put = (store, key, value) => tx(store, 'readwrite', s => s.put(value, key));
  const get = (store, key) => tx(store, 'readonly', s => s.get(key));
  const keys = store => tx(store, 'readonly', s => s.getAllKeys());
  const count = store => tx(store, 'readonly', s => s.count());

  // ---------- panel ----------
  document.getElementById('mfa-harvest-panel')?.remove();
  const panel = document.createElement('div');
  panel.id = 'mfa-harvest-panel';
  panel.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:2147483647;width:340px;padding:16px;border-radius:14px;background:#fff;color:#1f1c18;box-shadow:0 10px 40px rgba(0,0,0,.25);font:13px/1.45 -apple-system,Helvetica,sans-serif';
  panel.innerHTML = `
    <div style="font:600 15px -apple-system,sans-serif;margin-bottom:6px">MFA on-view harvester</div>
    <div id="h-status">Ready.</div>
    <div style="height:6px;background:#eee;border-radius:3px;margin:10px 0;overflow:hidden"><div id="h-bar" style="height:100%;width:0;background:#2b44c9"></div></div>
    <div id="h-detail" style="color:#6b655b;min-height:36px"></div>
    <div style="display:flex;gap:8px;margin-top:10px">
      <button id="h-start" style="flex:1;padding:8px;border-radius:8px;border:0;background:#1f1c18;color:#fff;font:inherit">Start</button>
      <button id="h-download" style="flex:1;padding:8px;border-radius:8px;border:1px solid #ccc;background:#fff;font:inherit">Download</button>
    </div>
    <button id="h-reset" style="margin-top:8px;padding:4px 0;border:0;background:none;color:#a33;font:inherit;text-decoration:underline">Reset saved progress</button>
    <div style="margin-top:8px;color:#6b655b">Keep this window visible and the Mac awake.</div>`;
  document.body.appendChild(panel);
  const $ = id => panel.querySelector(id);
  const status = (msg, detail = '', frac = null) => {
    if (msg !== status.last) { console.log('[harvester]', msg, detail); status.last = msg; }
    $('#h-status').textContent = msg;
    $('#h-detail').textContent = detail;
    if (frac !== null) $('#h-bar').style.width = `${Math.round(frac * 100)}%`;
  };

  // ---------- polite fetching ----------
  let running = false;
  let pause = CONFIG.pause;
  let failures = 0;
  // timers in a worker keep full speed when this tab is in the background
  let timer = null;
  try { timer = new Worker(URL.createObjectURL(new Blob(['onmessage=e=>setTimeout(()=>postMessage(e.data),e.data.ms)'], { type: 'text/javascript' }))); } catch { timer = null; }
  const waiting = new Map();
  let ticket = 0;
  if (timer) timer.onmessage = e => { waiting.get(e.data.id)?.(); waiting.delete(e.data.id); };
  const sleep = ms => new Promise(r => {
    if (!timer) return setTimeout(r, ms);
    const id = ++ticket;
    waiting.set(id, r);
    timer.postMessage({ id, ms });
  });

  async function politeFetch(url, as = 'text') {
    for (;;) {
      if (!running) throw new Error('paused');
      await sleep(pause);
      let res;
      try { res = await fetch(url, { credentials: 'include' }); } catch (e) { res = null; }
      // 202 with an empty body: the site's traffic filter. Stop; reload the tab, paste again and press Start later.
      if (res && res.status === 202) { running = false; throw new Error('The site paused us. Reload this tab, paste the script again and press Start (wait a bit first).'); }
      // 202 with an empty body is the site's traffic filter asking us to slow down
      const blocked = !res || res.status === 202 || res.status === 403 || res.status === 429 || res.status >= 500;
      if (!blocked && res.ok) {
        const body = as === 'blob' ? await res.blob() : await res.text();
        if (as === 'text' && /awswaf|captcha/i.test(body.slice(0, 3000)) && !/detailField|search-results|objects\//.test(body)) {
          // the site served a challenge page instead of content
        } else {
          failures = 0;
          pause = Math.max(CONFIG.pause, pause * 0.9);
          return body;
        }
      } else if (res && res.status === 404) {
        return null;
      }
      failures++;
      if (failures >= 6) {
        running = false;
        throw new Error('The site keeps refusing requests. Progress is saved \u2014 try again in an hour or two.');
      }
      pause = Math.min(pause * 2, 10000);
      const wait = 60000 * failures;
      status('Site asked to slow down \u2014 waiting\u2026', `Retrying in ${Math.round(wait / 1000)} s (attempt ${failures}/5). Pause between requests now ${pause} ms.`);
      await sleep(wait);
    }
  }

  const parse = html => new DOMParser().parseFromString(html, 'text/html');
  const txt = el => (el ? el.textContent.replace(/\s+/g, ' ').trim() : '');

  // ---------- phase 1: list every on-view object ----------
  async function collectIds() {
    let emptyTries = 0;
    let total = (await get('meta', 'total')) ?? null;
    let page = ((await get('meta', 'lastPage')) ?? 0) + 1;
    for (;;) {
      const pages = total ? Math.ceil(total / CONFIG.perPage) : null;
      if (pages && page > pages) break;
      status('1/3 \u00b7 Listing works on view', `Search page ${page}${pages ? ` of ${pages}` : ''}`, pages ? page / pages / 3 : 0);
      const html = await politeFetch(`${SEARCH}&page=${page}`);
      const d = parse(html || '<p></p>');
      if (!total) {
        const text = d.body.textContent.replace(/\s+/g, ' ');
        const m = text.match(/of\s+([\d,]+)\s+for/) || text.match(/\d+\s+to\s+\d+\s+of\s+([\d,]+)/);
        if (m) { total = Number(m[1].replace(/,/g, '')); await put('meta', 'total', total); }
      }
      const found = new Set();
      d.querySelectorAll('a[href*="/objects/"]').forEach(a => {
        const m = a.getAttribute('href').match(/\/objects\/(\d+)/);
        if (m) found.add(m[1]);
      });
      if (!found.size) {
        // an empty page before the last one is a hiccup (slow site, challenge page), not the end: wait and retry
        if (pages && page < pages) {
          emptyTries = (emptyTries || 0) + 1;
          if (emptyTries > 4) throw new Error(`Search page ${page} keeps coming back empty. Progress is saved; reload, paste and press Start in a while.`);
          status('Search page came back empty \u2014 retrying\u2026', `Page ${page} of ${pages}, attempt ${emptyTries} of 4`);
          await sleep(30000 * emptyTries);
          continue;
        }
        break;
      }
      emptyTries = 0;
      for (const id of found) await put('ids', id, 1);
      await put('meta', 'lastPage', page);
      page++;
    }
    const lastPage = (await get('meta', 'lastPage')) ?? 0;
    const pages = total ? Math.ceil(total / CONFIG.perPage) : 0;
    if ((await count('ids')) && (!pages || lastPage >= pages)) await put('meta', 'idsDone', true);
  }

  // ---------- phase 2: read each work's page ----------
  const COUNTRY = {
    French: 'France', Dutch: 'Netherlands', Flemish: 'Flanders', Netherlandish: 'Netherlands', Belgian: 'Belgium',
    Italian: 'Italy', Spanish: 'Spain', English: 'England', British: 'Great Britain', Scottish: 'Scotland',
    Irish: 'Ireland', German: 'Germany', Austrian: 'Austria', Swiss: 'Switzerland', Norwegian: 'Norway',
    Swedish: 'Sweden', Danish: 'Denmark', Russian: 'Russia', Polish: 'Poland', Greek: 'Greece', Roman: 'Roman Empire',
    Egyptian: 'Egypt', American: 'United States', Mexican: 'Mexico', Canadian: 'Canada', Peruvian: 'Peru',
    Brazilian: 'Brazil', Japanese: 'Japan', Chinese: 'China', Korean: 'Korea', Indian: 'India', Persian: 'Iran',
    Iranian: 'Iran', Turkish: 'Turkey', Ottoman: 'Ottoman Empire', Byzantine: 'Byzantine Empire', Etruscan: 'Etruria',
    Nubian: 'Nubia', Kushite: 'Nubia', Cypriot: 'Cyprus', Portuguese: 'Portugal', Czech: 'Czech Republic',
    Hungarian: 'Hungary', Finnish: 'Finland', Australian: 'Australia', Nigerian: 'Nigeria', Ghanaian: 'Ghana',
  };
  function countryOf(nationality, culture, geography) {
    for (const src of [nationality, culture]) {
      const word = (src || '').match(/[A-Z][a-z]+/)?.[0];
      if (word && COUNTRY[word]) return COUNTRY[word];
    }
    const g = (geography || '').replace(/^[^:]*:\s*/, '').split(',')[0].trim();
    return g || (culture || '').trim() || '';
  }
  function centuryOf(date) {
    const d = (date || '').replace(/,/g, '');
    const named = d.match(/(\d{1,2})(?:st|nd|rd|th)\s+century(\s+B\.?C\.?)?/i);
    if (named) return `${ordinal(+named[1])} century${named[2] ? ' B.C.' : ''}`;
    const bc = d.match(/(\d{1,4})\s*(?:\u2013\s*\d+\s*)?B\.?C/i);
    if (bc) return `${ordinal(Math.floor((+bc[1] - 1) / 100) + 1)} century B.C.`;
    const y = d.match(/(\d{3,4})/);
    if (y) return `${ordinal(Math.floor((+y[1] - 1) / 100) + 1)} century`;
    return '';
  }
  const ordinal = n => n + (n % 100 >= 11 && n % 100 <= 13 ? 'th' : { 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th');
  function typeOf(classification) {
    let t = (classification || '').split(' \u2013 ')[0].trim();
    if (/^[A-Z][a-z]+s$/.test(t) && !/(ics|ss)$/.test(t)) t = t.slice(0, -1); // Paintings -> Painting
    return t;
  }
  function galleryOf(onview) {
    const m = onview.match(/\(Gallery\s+([^)]+)\)/i);
    if (!m) return null;
    let g = m[1].trim().toUpperCase();
    const range = g.match(/^(\d+)([A-Z])\s*[-\u2013]\s*[A-Z]$/);  // 212A-B -> 212A
    if (range) g = range[1] + range[2];
    const span = g.match(/^(\d+)\s*[-\u2013]\s*\d+$/);             // 260-263 -> 260
    if (span) g = span[1];
    return g;
  }
  function floorOf(g) {
    if (!g) return null;
    if (/^L?G/.test(g)) return 'G';
    const m = g.match(/^(\d)/);
    return m ? m[1] : null;
  }

  function record(id, html) {
    const d = parse(html);
    const titleEl = d.querySelector('.titleField');
    const title = txt(titleEl?.firstElementChild) || txt(titleEl);
    const people = txt(d.querySelector('.peopleField')).replace(/Lent by:.*$/, '').trim();
    const artist = people.replace(/\s*\(.*$/, '').trim();
    const artistDetails = (people.match(/\((.*)\)\s*$/) || [])[1] || '';
    const date = txt(d.querySelector('.displayDateField'));
    const culture = txt(d.querySelector('.cultureField')).replace(/^Culture\s*/, '');
    const geography = [...d.querySelectorAll('.objectGeographyField')].map(txt).find(Boolean) || '';
    const onview = txt(d.querySelector('.onviewField')).replace(/^ON VIEW\s*/i, '');
    const gallery = galleryOf(onview);
    const classification = txt(d.querySelector('.classificationsField .detailFieldValue'));
    // the museum's own text about the work (paragraphs are separated by <br>)
    const descEl = d.querySelector('.webDescriptionField');
    let description = '';
    if (descEl) {
      descEl.querySelectorAll('br').forEach(br => br.replaceWith('\u2029'));
      description = descEl.textContent.split(/\u2029+/).map(t => t.replace(/\s+/g, ' ').trim()).filter(Boolean).join('\n\n');
    }
    const value = sel => txt(d.querySelector(`${sel} .detailFieldValue`));
    const media = d.querySelector('img[src*="/preview"]')?.getAttribute('src')?.match(/dispatcher\/(\d+)/)?.[1] ?? null;
    return {
      id, title, artist, artistDetails, date,
      medium: txt(d.querySelector('.mediumField .detailFieldValue')),
      dimensions: value('.dimensionsField'),
      creditLine: value('.creditlineField'),
      description,
      gallery,
      galleryName: onview.replace(/\s*\(Gallery[^)]*\)\s*$/i, '').trim() || null,
      location: gallery ? null : onview || null,
      floor: floorOf(gallery),
      accession: txt(d.querySelector('.invnolineField .detailFieldValue')),
      onView: !!onview,
      type: typeOf(classification),
      classification,
      country: countryOf(artistDetails, culture, geography),
      period: centuryOf(date),
      culture,
      collection: txt(d.querySelector('.collectionTermsField .detailFieldValue')),
      url: `https://collections.mfa.org/objects/${id}`,
      imageUrl: media ? `https://collections.mfa.org/internal/media/dispatcher/${media}/preview` : null,
      _media: media,
    };
  }

  async function collectRecords() {
    const ids = await keys('ids');
    const done = new Set(await keys('records'));
    let i = done.size;
    for (const id of ids) {
      if (done.has(id)) continue;
      const html = await politeFetch(`/objects/${id}`);
      if (html) await put('records', id, record(id, html));
      i++;
      status('2/3 \u00b7 Reading works', `${i} of ${ids.length} \u00b7 about ${eta(ids.length - i, 2)} left`, 1 / 3 + (i / ids.length) / 3);
    }
  }

  // works read before descriptions were collected are read again (after everything else)
  async function backfillDescriptions() {
    const ids = await keys('records');
    let i = 0;
    for (const id of ids) {
      i++;
      const old = await get('records', id);
      if (!old || 'description' in old) continue;
      const html = await politeFetch(`/objects/${id}`);
      if (html) await put('records', id, { ...record(id, html), _media: old._media ?? null });
      status('Adding descriptions', `${i} of ${ids.length}`, i / ids.length);
    }
  }

  // ---------- phase 3: small copy of each image ----------
  async function shrink(blob) {
    const bmp = await createImageBitmap(blob);
    const s = Math.min(1, CONFIG.imageMax / Math.max(bmp.width, bmp.height));
    const w = Math.max(1, Math.round(bmp.width * s)), h = Math.max(1, Math.round(bmp.height * s));
    const canvas = new OffscreenCanvas(w, h);
    canvas.getContext('2d').drawImage(bmp, 0, 0, w, h);
    return canvas.convertToBlob({ type: 'image/jpeg', quality: CONFIG.imageQuality });
  }

  async function collectImages() {
    const ids = await keys('records');
    const todo = ids.length;
    let i = 0;
    for (const id of ids) {
      i++;
      const r = await get('records', id);
      // a picture that failed earlier (stored as null) is tried again
      if ((await get('images', id)) || !r?._media) {
        if (!r?._media && (await get('images', id)) === undefined) await put('images', id, null);
        continue;
      }
      {
        const blob = await politeFetch(`/internal/media/dispatcher/${r._media}/preview`, 'blob');
        if (blob && blob.size) {
          try { await put('images', id, await shrink(blob)); } catch { await put('images', id, null); }
        } else await put('images', id, null);
      }
      status('3/3 \u00b7 Saving images', `${i} of ${todo} \u00b7 about ${eta(todo - i, 1)} left`, 2 / 3 + (i / todo) / 3);
    }
  }

  const eta = (n, perItem) => {
    const s = n * perItem * (pause + 350) / 1000;
    return s > 3600 ? `${(s / 3600).toFixed(1)} h` : `${Math.ceil(s / 60)} min`;
  };

  // ---------- output ----------
  async function download() {
    status('Preparing files\u2026', '');
    const ids = await keys('records');
    const records = [];
    for (const id of ids) {
      const r = await get('records', id);
      if (r && r.onView) records.push(r);
    }
    // images that sit together in the museum go in the same pack
    records.sort((a, b) => String(a.gallery ?? 'zzz').localeCompare(String(b.gallery ?? 'zzz'), undefined, { numeric: true }));
    const packs = [];
    let parts = [], size = 0;
    const flush = () => { if (parts.length) packs.push(new Blob(parts, { type: 'application/octet-stream' })); parts = []; size = 0; };
    for (const r of records) {
      const img = await get('images', r.id);
      if (img) {
        if (size + img.size > CONFIG.packSize) flush();
        r.img = { p: `data/images/images-${String(packs.length + 1).padStart(3, '0')}.bin`, o: size, l: img.size };
        parts.push(img);
        size += img.size;
      }
      delete r._media;
    }
    flush();
    const today = new Date().toISOString().slice(0, 10);
    const doc = { source: 'MFA Boston online collection (collections.mfa.org), works marked On View', checked: today, count: records.length, artworks: records };
    save(new Blob([JSON.stringify(doc)], { type: 'application/json' }), 'artworks.json');
    for (let i = 0; i < packs.length; i++) {
      await sleep(800);
      save(packs[i], `images-${String(i + 1).padStart(3, '0')}.bin`);
    }
    status('Done \u2014 files downloaded.', `${records.length} works \u00b7 ${packs.length} image packs. Move them into the mfa-guide/data folder (see README).`, 1);
  }
  function save(blob, name) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 4000);
  }

  // for checking the parser from the console: mfaHarvest.record(id, html)
  window.mfaHarvest = { record, centuryOf, countryOf, typeOf, galleryOf };

  // ---------- controls ----------
  async function run() {
    running = true;
    $('#h-start').textContent = 'Pause';
    try {
      // a listing that found nothing is not a finished listing: start it again;
      // one that stopped early (fewer pages read than the site has) carries on from where it stopped
      const total = await get('meta', 'total');
      const lastPage = (await get('meta', 'lastPage')) ?? 0;
      const pagesNeeded = total ? Math.ceil(total / CONFIG.perPage) : 0;
      console.log('[harvester] saved progress:', { total, lastPage, pagesNeeded, listed: await count('ids'), read: await count('records') });
      if (!(await count('ids'))) { await put('meta', 'lastPage', 0); await put('meta', 'idsDone', false); }
      // the listing only counts as finished when we know the total and have read every page
      else if (!pagesNeeded || lastPage < pagesNeeded) {
        await put('meta', 'idsDone', false);
        status('1/3 \u00b7 Resuming the listing', `Continuing from search page ${lastPage + 1}${pagesNeeded ? ` of ${pagesNeeded}` : ''}`);
      }
      if (!(await get('meta', 'idsDone'))) await collectIds();
      const listed = await count('ids');
      if (!listed) throw new Error('The search pages returned no works. Open https://collections.mfa.org/search/objects/*/*?filter=onview%3Atrue in this tab, reload, paste the script again and press Start.');
      // a listing cut short by the site gets another go, then the new works are read too
      for (let pass = 0; ; pass++) {
        await collectRecords();
        await collectImages();
        if ((await get('meta', 'idsDone')) || pass >= 3) break;
        await collectIds();
      }
      if (!(await get('meta', 'idsDone'))) throw new Error('The listing is still incomplete. Progress is saved; press Start again in a while.');
      await backfillDescriptions();
      status('Finished collecting.', 'Click Download to save the files.', 1);
    } catch (e) {
      if (e.message !== 'paused') status('Stopped.', e.message);
      else status('Paused.', 'Click Start to continue.');
    }
    running = false;
    $('#h-start').textContent = 'Start';
  }
  $('#h-start').onclick = () => { if (running) running = false; else run(); };
  $('#h-download').onclick = async () => {
    if (!(await count('records'))) { status('Nothing to download yet.', 'Click Start first. Download is for the end, after "Finished collecting".'); return; }
    download().catch(e => status('Download failed.', e.message));
  };
  $('#h-reset').onclick = async () => {
    if (running) { status('Pause first, then reset.'); return; }
    if (!confirm('Forget everything collected so far and start over?')) return;
    for (const store of ['ids', 'records', 'images', 'meta']) await tx(store, 'readwrite', s => s.clear());
    status('Reset.', 'Click Start to begin.', 0);
  };

  open().then(async d => {
    db = d;
    const [ids, recs, imgs] = await Promise.all([count('ids'), count('records'), count('images')]);
    status(ids ? 'Saved progress found.' : 'Ready.', ids ? `${ids} works listed \u00b7 ${recs} read \u00b7 ${imgs} images. Click Start to continue.` : 'Click Start to begin.');
  });
})();
