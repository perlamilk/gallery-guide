import { loadData, shortArtist } from './data.js';
import { MuseumMap } from './map3d.js';

const $ = sel => document.querySelector(sel);
const els = {
  app: $('#app'), canvas: $('#map'), sheet: $('#sheet'), grab: $('#grab'), body: $('#body'),
  form: $('#searchForm'), q: $('#q'), clear: $('#clear'), floors: $('#floors'),
  recenter: $('#recenter'), floorTitle: $('#floorTitle'), floorSub: $('#floorSub'),
  tools: document.querySelector('.map-tools'), toast: $('#toast'),
};

const state = {
  museum: null,
  map: null,
  floor: null,
  query: '',
  results: [],
  // what the sheet shows: { type: 'home' } | { type: 'results' } | { type: 'room', id } | { type: 'art', id, from }
  view: { type: 'home' },
};

boot().catch(err => {
  console.error(err);
  els.body.innerHTML = `<div class="empty"><strong>Couldn’t load the guide</strong>${escape(err.message)}</div>`;
});

async function boot() {
  await document.fonts.load('120px "Instrument Serif"').catch(() => {});
  state.museum = await loadData();

  state.map = new MuseumMap(els.canvas, state.museum, { onRoomTap });
  buildFloorSwitcher();
  setFloor(state.museum.defaultFloor, { animate: false });
  setSheet('peek');
  state.map.resetView({ animate: false });

  wireSearch();
  wireSheetDrag();
  els.recenter.addEventListener('click', () => state.map.resetView());
  render();
  registerServiceWorker();
  window.guide = state; // handy for poking at the app from Safari's Web Inspector
}

// ---------- floors ----------

function buildFloorSwitcher() {
  const floors = [...state.museum.floors].reverse(); // highest floor on top
  els.floors.innerHTML = floors.map(f => `
    <button class="floor" type="button" role="radio" data-floor="${f.id}" aria-checked="false"
            aria-label="${escape(f.label)}">${escape(f.id)}<span class="floor__dot" aria-hidden="true"></span></button>
  `).join('');
  els.floors.addEventListener('click', e => {
    const btn = e.target.closest('[data-floor]');
    if (btn) setFloor(btn.dataset.floor);
  });
}

function setFloor(id, { animate = true } = {}) {
  if (state.floor === id) return;
  state.floor = id;
  const floor = state.museum.floor(id);
  state.map.showFloor(id, { animate });
  for (const b of els.floors.children) b.setAttribute('aria-checked', String(b.dataset.floor === id));
  const [title, sub] = (floor.area ?? floor.label).split(' · ');
  els.floorTitle.textContent = title;
  els.floorSub.textContent = `${floor.label}${sub ? ` · ${sub}` : ''}`;
}

function markFloorsWithMatches(counts) {
  const floorsWithHits = new Set([...counts.keys()].map(g => state.museum.roomInfo(g)?.floor.id).filter(Boolean));
  for (const b of els.floors.children) b.dataset.hasMatches = String(floorsWithHits.has(b.dataset.floor));
}

// ---------- search ----------

function wireSearch() {
  let timer;
  els.q.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => runSearch(els.q.value), 90);
    els.clear.hidden = !els.q.value;
  });
  els.q.addEventListener('focus', () => { if (sheetState() === 'peek') setSheet('half'); });
  els.form.addEventListener('submit', e => {
    e.preventDefault();
    els.q.blur();
    // Pressing Search brings every lit room on this floor into view.
    state.map.frameRooms([...state.museum.galleriesOf(state.results).keys()]);
  });
  els.clear.addEventListener('click', () => {
    els.q.value = '';
    els.clear.hidden = true;
    runSearch('');
    els.q.focus();
  });
}

function runSearch(query) {
  state.query = query.trim();
  // Results on the floor you're looking at come first.
  const here = r => (r.floor === state.floor ? 0 : 1);
  state.results = state.museum.search(state.query).sort((a, b) => here(a) - here(b));
  const counts = state.museum.galleriesOf(state.results);
  state.map.highlight(counts);
  markFloorsWithMatches(counts);
  state.map.select(null);

  // If nothing matches on this floor but something does on another, go there.
  const floorsHit = new Set([...counts.keys()].map(g => state.museum.roomInfo(g)?.floor.id).filter(Boolean));
  if (floorsHit.size && !floorsHit.has(state.floor)) {
    const target = [...floorsHit][0];
    setFloor(target);
    toast(`Matches on ${state.museum.floor(target).label}`);
    state.map.frameRooms([...counts.keys()]);
  }

  state.view = state.query ? { type: 'results' } : { type: 'home' };
  render();
}

function setQuery(text) {
  els.q.value = text;
  els.clear.hidden = !text;
  runSearch(text);
  if (sheetState() === 'peek') setSheet('half');
}

// ---------- map taps ----------

function onRoomTap(galleryId) {
  if (!galleryId) {
    if (state.view.type === 'room') closeRoom();
    return;
  }
  openRoom(galleryId);
}

function openRoom(id, { fly = false } = {}) {
  state.view = { type: 'room', id };
  state.map.select(id);
  if (fly) state.map.focusRoom(id);
  if (sheetState() === 'peek') setSheet('half');
  render();
}

function closeRoom() {
  state.map.select(null);
  state.view = state.query ? { type: 'results' } : { type: 'home' };
  render();
}

function openArt(id) {
  const art = state.museum.artworks.find(a => a.id === id);
  if (!art) return;
  state.view = { type: 'art', id, from: state.view };
  if (state.museum.isMapped(art.gallery)) {
    state.map.select(art.gallery);
    state.map.focusRoom(art.gallery, { zoom: false });
  }
  setSheet('full'); // the artwork is the point of this view
  render();
}

// ---------- rendering ----------

function render() {
  const v = state.view;
  const html = v.type === 'room' ? roomView(v.id)
    : v.type === 'art' ? artView(v.id)
    : v.type === 'results' ? resultsView()
    : homeView();
  els.body.innerHTML = `<div class="view">${html}</div>`;
  els.body.scrollTop = 0;
}

function homeView() {
  const chips = state.museum.topArtists(7)
    .map(name => `<button class="chip" type="button" data-query="${escape(name)}">${escape(name)}</button>`).join('');
  const n = state.museum.artworks.length;
  return `
    <div class="chips">${chips}</div>
    <p class="hint">Tap a gallery on the map to see what’s inside — or search for an artist like <em>Van Gogh</em>.</p>
    <p class="eyebrow">In this guide</p>
    <p class="hint">${n} works on view across ${state.museum.byGallery.size} galleries · checked ${formatDate(state.museum.meta.checked)}</p>
    <p class="offline" id="offline">Checking offline copy…</p>`;
}

function resultsView() {
  const res = state.results;
  if (!res.length) {
    return `<div class="empty"><strong>No works found</strong>Nothing on view here matches “${escape(state.query)}”. Try an artist’s surname or a gallery number.</div>`;
  }
  const rooms = state.museum.galleriesOf(res).size;
  return `
    <div class="summary">
      <p class="summary__count">${res.length} ${res.length === 1 ? 'work' : 'works'} <i>in ${rooms} ${rooms === 1 ? 'gallery' : 'galleries'}</i></p>
    </div>
    <ul class="list">${res.map(rowHTML).join('')}</ul>`;
}

function rowHTML(a) {
  const mapped = state.museum.isMapped(a.gallery);
  return `
    <li><button class="row" type="button" data-art="${a.id}">
      <img class="thumb" src="${a.image}" alt="" loading="lazy" decoding="async">
      <span>
        <p class="row__title">${escape(a.title)}</p>
        <p class="row__meta">${escape(shortArtist(a.artist))} · ${escape(a.date)}</p>
      </span>
      <span class="badge ${mapped ? '' : 'badge--off'}"><small>Gal.</small>${escape(a.gallery)}</span>
    </button></li>`;
}

function roomView(id) {
  const info = state.museum.roomInfo(id);
  const hits = new Set(state.results.map(a => a.id));
  const works = [...state.museum.worksIn(id)].sort((a, b) => hits.has(b.id) - hits.has(a.id));
  const name = info?.room.name;
  const cards = works.length
    ? `<div class="grid">${works.map(a => `
        <button class="card" type="button" data-art="${a.id}">
          ${hits.has(a.id) ? '<span class="card__match">Match</span>' : ''}
          <img class="card__img" src="${a.image}" alt="" loading="lazy" decoding="async">
          <p class="card__title">${escape(a.title)}</p>
          <p class="card__meta">${escape(shortArtist(a.artist))} · ${escape(a.date)}</p>
        </button>`).join('')}</div>`
    : `<div class="empty"><strong>Nothing listed yet</strong>No works in this sample data are in Gallery ${escape(id)}. When the full on-view list is loaded, they’ll appear here.</div>`;
  return `
    <div class="head">
      <div>
        <h2 class="head__title">Gallery ${escape(id)}</h2>
        ${name ? `<p class="head__name">${escape(name)}</p>` : ''}
        <p class="head__meta">${escape(info?.floor.label ?? '')} · ${works.length} ${works.length === 1 ? 'work' : 'works'}</p>
      </div>
      <button class="icon-btn" type="button" data-action="close-room" aria-label="Close gallery">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17"/></svg>
      </button>
    </div>
    ${cards}`;
}

function artView(id) {
  const a = state.museum.artworks.find(x => x.id === id);
  const info = state.museum.roomInfo(a.gallery);
  const backLabel = state.view.from?.type === 'room' ? `Gallery ${state.view.from.id}` : state.query ? 'Results' : 'Back';
  return `
    <button class="back" type="button" data-action="back">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14.5 6-6 6 6 6"/></svg>${escape(backLabel)}
    </button>
    <div class="art__frame"><img class="art__img" src="${a.image}" alt="${escape(a.title)}"></div>
    <h2 class="art__title">${escape(a.title)}</h2>
    <p class="art__artist">${escape(a.artist)}</p>
    <p class="art__life">${escape(a.artistDetails ?? '')}</p>
    <dl class="facts">
      <div><dt>Date</dt><dd>${escape(a.date)}</dd></div>
      <div><dt>Medium</dt><dd>${escape(a.medium)}</dd></div>
      <div><dt>Gallery</dt><dd>${info
        ? `<button class="gallery-link" type="button" data-room="${a.gallery}">Gallery ${escape(a.gallery)}</button> · ${escape(info.floor.label)}${a.galleryName ? `<br><span style="color:var(--ink-2)">${escape(a.galleryName)}</span>` : ''}`
        : `Gallery ${escape(a.gallery)} <span style="color:var(--ink-3)">(not on this map yet)</span>`}</dd></div>
      <div><dt>Accession</dt><dd>${escape(a.accession ?? '')}</dd></div>
    </dl>
    <a class="cta" href="${a.url}" target="_blank" rel="noopener">
      View on the MFA collection site
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 16 16 8M9 8h7v7"/></svg>
    </a>
    ${a.imageSource ? `<p class="credit">Image: <a href="${a.imageSource}" target="_blank" rel="noopener">${escape(a.imageCredit ?? 'source')}</a></p>` : ''}`;
}

// One delegated handler for everything inside the sheet.
els.body.addEventListener('click', e => {
  const t = e.target.closest('[data-query],[data-art],[data-room],[data-action]');
  if (!t) return;
  if (t.dataset.query) {
    setQuery(t.dataset.query);
    state.map.frameRooms([...state.museum.galleriesOf(state.results).keys()]);
  }
  else if (t.dataset.art) openArt(t.dataset.art);
  else if (t.dataset.room) { setSheet('half'); openRoom(t.dataset.room, { fly: true }); }
  else if (t.dataset.action === 'close-room') closeRoom();
  else if (t.dataset.action === 'back') {
    const from = state.view.from ?? { type: 'home' };
    state.view = from;
    state.map.select(from.type === 'room' ? from.id : null);
    setSheet('half');
    render();
  }
});

// ---------- bottom sheet ----------

function sheetState() { return els.sheet.dataset.state; }

function setSheet(s) {
  els.sheet.dataset.state = s;
  els.grab.setAttribute('aria-expanded', String(s !== 'peek'));
  updateInsets();
}

// Keep the map tools and the map's centre above the sheet.
// Uses the sheet's resting height for its state (or its live position while dragging).
function updateInsets() {
  const wide = matchMedia('(min-width: 760px)').matches;
  const h = els.app.clientHeight;
  const sheetH = els.sheet.offsetHeight;
  let visible;
  if (els.sheet.classList.contains('dragging')) visible = h - els.sheet.getBoundingClientRect().top;
  else visible = { peek: 196 + safeBottom(), half: sheetH * 0.56, full: sheetH }[sheetState()];
  visible = wide ? 0 : Math.max(0, visible);
  if (!wide) els.tools.style.bottom = `${Math.min(visible, h * 0.62) + 16}px`;
  else els.tools.style.bottom = '';
  const left = wide ? els.sheet.getBoundingClientRect().right : 0;
  state.map?.setViewInsets({ bottom: Math.min(visible, h * 0.6), left });
}
window.addEventListener('resize', updateInsets);

// env(safe-area-inset-bottom) in px, read once from a probe element.
let safeB;
function safeBottom() {
  if (safeB === undefined) {
    const probe = document.createElement('div');
    probe.style.cssText = 'position:fixed;bottom:0;height:env(safe-area-inset-bottom,0px);visibility:hidden';
    document.body.appendChild(probe);
    safeB = probe.offsetHeight;
    probe.remove();
  }
  return safeB;
}

function wireSheetDrag() {
  const order = ['peek', 'half', 'full'];
  let start = null;

  const onDown = e => {
    if (e.target.closest('input, button') && e.currentTarget !== els.grab) return;
    start = { y: e.clientY, top: els.sheet.getBoundingClientRect().top, t: performance.now(), moved: false };
    els.sheet.setPointerCapture?.(e.pointerId);
  };
  const onMove = e => {
    if (!start) return;
    const dy = e.clientY - start.y;
    if (!start.moved && Math.abs(dy) < 6) return;
    start.moved = true;
    els.sheet.classList.add('dragging');
    const h = els.sheet.offsetHeight;
    const parentH = els.app.clientHeight;
    const top = Math.max(parentH - h, start.top + dy);
    els.sheet.style.transform = `translateY(${top - (parentH - h)}px)`;
    updateInsets();
  };
  const onUp = e => {
    if (!start) return;
    const dy = e.clientY - start.y;
    const v = dy / Math.max(1, performance.now() - start.t);
    const moved = start.moved;
    start = null;
    els.sheet.classList.remove('dragging');
    els.sheet.style.transform = '';
    if (!moved) {
      // tap on the handle cycles peek <-> half
      if (e.target.closest('#grab')) setSheet(sheetState() === 'peek' ? 'half' : 'peek');
      return;
    }
    const i = order.indexOf(sheetState());
    let next = i;
    if (v < -0.4 || dy < -80) next = Math.min(order.length - 1, i + (dy < -260 ? 2 : 1));
    else if (v > 0.4 || dy > 80) next = Math.max(0, i - (dy > 260 ? 2 : 1));
    if (next === 0) els.q.blur();
    setSheet(order[next]);
  };

  for (const el of [els.grab, els.form]) el.addEventListener('pointerdown', onDown);
  // Keyboard / VoiceOver activation of the grabber cycles through the detents.
  els.grab.addEventListener('click', e => {
    if (e.detail !== 0) return; // pointer taps are handled in onUp
    setSheet(order[(order.indexOf(sheetState()) + 1) % order.length]);
  });
  els.sheet.addEventListener('pointermove', onMove);
  els.sheet.addEventListener('pointerup', onUp);
  els.sheet.addEventListener('pointercancel', onUp);
}

// ---------- offline ----------

async function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return setOffline(false, 'Offline mode isn’t supported in this browser');
  try {
    await navigator.serviceWorker.register('sw.js');
    await navigator.serviceWorker.ready;
    checkOffline();
  } catch (err) {
    console.warn('Service worker failed', err);
    setOffline(false, 'Offline copy unavailable');
  }
}

async function checkOffline() {
  if (!('caches' in window)) return;
  const urls = ['index.html', 'data/artworks.json', 'data/floors.json', ...state.museum.artworks.map(a => a.image)];
  const hits = await Promise.all(urls.map(u => caches.match(u)));
  const missing = hits.filter(h => !h).length;
  if (!missing) setOffline(true, 'Saved for offline use — works without signal');
  else {
    setOffline(false, `Saving for offline… ${urls.length - missing}/${urls.length}`);
    setTimeout(checkOffline, 1500);
  }
}

function setOffline(ready, text) {
  const el = document.getElementById('offline');
  if (!el) return;
  el.dataset.ready = String(ready);
  el.textContent = text;
}

// ---------- utils ----------

let toastTimer;
function toast(msg) {
  els.toast.textContent = msg;
  els.toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => els.toast.classList.remove('show'), 1800);
}

function formatDate(iso) {
  if (!iso) return '';
  return new Date(iso + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function escape(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
