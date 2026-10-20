// Gallery Guide — interface. See design-system/MASTER.md.
// Structure: the 3D map fills the screen; a sheet floats over it; a tab bar switches between
// Explore · Tours · Saved · Visits. Each tab keeps its own stack of views (like a navigation stack).

import { loadData, shortArtist, FILTERS } from './data.js';
import { MuseumMap } from './map3d.js';
import { FACILITIES, facilitySVG } from './icons.js';
import { Visits, Favorites, duration } from './visits.js';
import { Router } from './routes.js';

const $ = sel => document.querySelector(sel);
const els = {
  app: $('#app'), canvas: $('#map'), sheet: $('#sheet'), grab: $('#grab'),
  header: $('#sheetHeader'), body: $('#body'), floors: $('#floors'), recenter: $('#recenter'),
  floorTitle: $('#floorTitle'), floorSub: $('#floorSub'), tools: document.querySelector('.map-tools'),
  tabbar: $('#tabbar'), toast: $('#toast'), visitPill: $('#visitPill'), visitPillText: $('#visitPillText'),
  visitBadge: $('#visitBadge'),
};

const PAGE = 60;
const FIND = ['restroom', 'dining', 'elevator', 'entrance', 'info', 'water', 'shop', 'coat'];
const TAB_ROOT = { explore: 'home', tours: 'tours', saved: 'saved', visits: 'visits' };

const state = {
  museum: null, map: null, router: null,
  floor: null,
  tab: 'explore',
  stacks: { explore: [{ type: 'home' }], tours: [{ type: 'tours' }], saved: [{ type: 'saved' }], visits: [{ type: 'visits' }] },
  query: '', results: [], places: [],
  filters: { type: '', country: '', period: '' },
  shown: PAGE,
  visit: null, diary: [], replaying: null,
  here: null, hereLabel: null, route: null, avoidStairs: false, picking: false,
  favorites: [], tours: [], tour: null,
};

// ---------- icons (line pictograms, one family) ----------
const I = {
  back: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 5-7 7 7 7"/></svg>',
  close: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17"/></svg>',
  chev: '<svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 5 7 7-7 7"/></svg>',
  search: '<svg class="search__icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/></svg>',
  walk: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="13" cy="4.5" r="1.8"/><path d="m9 21 2.5-6.5L14 17v4M10 12l1-4 3 2 3 1M11 8 8 10v3"/></svg>',
  check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>',
  circle: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/></svg>',
  heart: on => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"${on ? ' fill="currentColor"' : ''}/></svg>`,
  grid: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/></svg>',
  door: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 20V5a1 1 0 0 1 1-1h7v16M14 4l4 1.5V20M4 20h16"/><path d="M11 12h.01"/></svg>',
  floor: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 9l4-4 4 4M8 15l4 4 4-4"/></svg>',
  pin: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-6-5.6-6-11a6 6 0 0 1 12 0c0 5.4-6 11-6 11z"/><circle cx="12" cy="10" r="2.2"/></svg>',
  flag: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 21V4M6 4h11l-2.5 4L17 12H6"/></svg>',
  route: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="6" cy="18" r="2.2"/><circle cx="18" cy="6" r="2.2"/><path d="M8 18h7.5a3.5 3.5 0 0 0 0-7h-7a3.5 3.5 0 0 1 0-7H16"/></svg>',
  stairs: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 20h5v-5h5v-5h5V5h3"/></svg>',
  dot: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3" fill="currentColor"/></svg>',
};

boot().catch(err => {
  console.error(err);
  els.body.innerHTML = `<div class="empty"><strong>Couldn’t Load the Guide</strong>${escape(err.message)}</div>`;
});

async function boot() {
  state.museum = await loadData();
  state.map = new MuseumMap(els.canvas, state.museum, { onTap: onMapTap });
  state.router = new Router(state.museum);
  [state.favorites, state.diary, state.visit] = await Promise.all([
    Favorites.list().catch(() => []), Visits.list().catch(() => []), Visits.active().catch(() => null),
  ]);
  state.tours = (await fetch('data/tours.json').then(r => r.json()).catch(() => ({}))).tours ?? [];
  state.here = state.visit?.rooms.at(-1)?.id ?? null;

  buildFloorPicker();
  setFloor(state.museum.defaultFloor, { animate: false });
  showVisitedOnMap();
  updateVisitUI();

  wireTabs();
  wireSheetDrag();
  els.recenter.addEventListener('click', () => state.map.resetView());
  els.visitPill.addEventListener('click', () => { setTab('visits'); setSheet('half'); });
  setInterval(updateVisitUI, 30000);

  render();
  setSheet('peek');
  state.map.resetView({ animate: false });
  registerServiceWorker();
  window.guide = state; // for Safari's Web Inspector
}

// ---------- tabs & navigation stacks ----------

function current() { const s = state.stacks[state.tab]; return s[s.length - 1]; }
function previous() { const s = state.stacks[state.tab]; return s[s.length - 2] ?? null; }

function push(view, { sheet } = {}) {
  state.stacks[state.tab].push(view);
  state.shown = PAGE;
  render();
  if (sheet) setSheet(sheet);
}
function pop() {
  const s = state.stacks[state.tab];
  if (s.length > 1) s.pop();
  if (current().type !== 'room') state.map.select(null);
  render();
}
function resetTab(tab = state.tab) {
  state.stacks[tab] = [{ type: TAB_ROOT[tab] }];
}

function setTab(tab) {
  if (state.tab === tab) {
    // tapping the current tab returns to its root, like iOS
    if (state.stacks[tab].length > 1) { resetTab(tab); render(); }
    return;
  }
  state.tab = tab;
  for (const b of els.tabbar.querySelectorAll('[data-tab]')) b.setAttribute('aria-selected', String(b.dataset.tab === tab));
  state.picking = false;
  render();
}

function wireTabs() {
  els.tabbar.addEventListener('click', e => {
    const b = e.target.closest('[data-tab]');
    if (!b) return;
    setTab(b.dataset.tab);
    if (els.sheet.dataset.state === 'peek') setSheet('half');
  });
}

// ---------- floors ----------

function buildFloorPicker() {
  const floors = [...state.museum.floors].reverse();
  els.floors.innerHTML = floors.map(f => `
    <button class="floor" type="button" role="radio" data-floor="${f.id}" aria-checked="false" aria-label="${escape(f.label)}">
      ${escape(f.id)}<span class="floor__dot" aria-hidden="true"></span></button>`).join('');
  els.floors.addEventListener('click', e => {
    const b = e.target.closest('[data-floor]');
    if (b) setFloor(b.dataset.floor);
  });
}

function setFloor(id, { animate = true } = {}) {
  if (state.floor === id) return;
  state.floor = id;
  const floor = state.museum.floor(id);
  state.map.showFloor(id, { animate });
  for (const b of els.floors.children) b.setAttribute('aria-checked', String(b.dataset.floor === id));
  els.floorTitle.textContent = floor.label;
  els.floorSub.textContent = floor.area ?? '';
}

function markFloors(counts) {
  const hit = new Set([...counts.keys()].map(g => state.museum.roomInfo(g)?.floor.id).filter(Boolean));
  for (const b of els.floors.children) b.dataset.hasMatches = String(hit.has(b.dataset.floor));
  return hit;
}

// ---------- render ----------

const VIEWS = {
  home: () => [headerSearch(), homeBody()],
  results: () => [headerSearch(), resultsBody()],
  browse: () => [headerBar('All Works'), browseBody()],
  room: v => roomView(v.id),
  art: v => [headerBar('', { trailing: favButton(v.id) }), artBody(v.id)],
  directions: () => [headerBar('Directions', { close: 'clear-route' }), directionsBody()],
  tours: () => [headerTitle('Tours'), toursBody()],
  tour: v => [headerBar(''), tourBody(v.id)],
  'tour-stop': () => tourStopView(),
  saved: () => [headerTitle('Saved'), savedBody()],
  visits: () => [headerTitle('Visits'), visitsBody()],
  entry: v => [headerBar(''), entryBody(v.id)],
};

function render() {
  const v = current();
  const [header, body] = (VIEWS[v.type] ?? VIEWS.home)(v);
  els.header.innerHTML = header;
  els.body.innerHTML = `<div class="view">${body}</div>`;
  els.body.scrollTop = 0;
  hydrateImages(els.body);
  wireHeader();
  applyHighlights();
  measurePeek();
  setOffline(...offlineStatus);
}

// What the map lights up depends on where you are.
function applyHighlights() {
  const v = current();
  let counts = new Map();
  if (state.tab === 'explore' && ['results', 'browse', 'room', 'art'].includes(v.type)) counts = worksCounts();
  else if (state.tab === 'saved') counts = state.museum.galleriesOf(favoriteWorks());
  else if (state.tab === 'tours') {
    const t = v.type === 'tour' ? state.tours.find(x => x.id === v.id) : v.type === 'tour-stop' ? currentTour() : null;
    if (t) for (const s of t.stops) counts.set(s.gallery, tourWorks(s).length || 1);
  }
  state.map.highlight(counts);
  markFloors(counts);
  if (state.tab !== 'explore' || !state.places.some(p => p.kind === 'facility')) state.map.highlightFacilities(null);
}

function worksCounts() {
  return Object.values(state.filters).some(Boolean) || state.query ? state.museum.galleriesOf(state.results) : new Map();
}

// ---------- headers ----------

function headerSearch() {
  return `<form class="search" id="searchForm" role="search" autocomplete="off">
      ${I.search}
      <input class="search__input" id="q" type="search" inputmode="search" enterkeyhint="search"
        placeholder="Search artists, works, places" aria-label="Search the museum" spellcheck="false" autocapitalize="off" value="${escape(state.query)}">
      <button class="search__clear" id="clear" type="button" aria-label="Clear Search" ${state.query ? '' : 'hidden'}><span>${I.close}</span></button>
    </form>`;
}

function headerTitle(title, trailing = '') {
  return `<div class="bar"><h2 class="bar__title">${escape(title)}</h2>${trailing}</div>`;
}

function headerBar(title, { close, trailing } = {}) {
  const prev = previous();
  const back = prev ? `<button class="bar__back" type="button" data-action="pop">${I.back}${escape(viewTitle(prev))}</button>` : '';
  const end = close ? `<button class="circle-btn" type="button" data-action="${close}" aria-label="Close">${I.close}</button>` : (trailing ?? '');
  return `<div class="bar">${back}${title ? `<h2 class="bar__title">${escape(title)}</h2>` : '<span class="bar__spacer"></span>'}${end}</div>`;
}

function viewTitle(v) {
  return {
    home: 'Explore', results: 'Results', browse: 'All Works', art: 'Work', tours: 'Tours', tour: 'Tour',
    'tour-stop': 'Tour', saved: 'Saved', visits: 'Visits', directions: 'Directions', entry: 'Visit',
  }[v.type] ?? (v.type === 'room' ? shortRoomLabel(v.id) : 'Back');
}

function wireHeader() {
  const q = $('#q');
  if (!q) return;
  let timer;
  q.addEventListener('input', () => {
    clearTimeout(timer);
    $('#clear').hidden = !q.value;
    timer = setTimeout(() => runSearch(q.value), 90);
  });
  q.addEventListener('focus', () => { if (els.sheet.dataset.state !== 'full') setSheet('full'); });
  $('#searchForm').addEventListener('submit', e => {
    e.preventDefault();
    q.blur();
    setSheet('half');
    state.map.frameRooms([...state.museum.galleriesOf(state.results).keys()]);
  });
  $('#clear').addEventListener('click', () => { q.value = ''; runSearch(''); q.focus(); });
}

// ---------- search ----------

function runSearch(query) {
  state.query = query.trim();
  state.places = state.museum.searchPlaces(state.query);
  state.map.highlightFacilities(new Set(state.places.filter(p => p.kind === 'facility').map(p => p.type)));
  const s = state.stacks.explore;
  s.length = 1;
  if (state.query) s.push({ type: 'results' });
  computeWorks();
  // keep focus in the field while typing: only the body re-renders
  const [, body] = (state.query ? VIEWS.results : VIEWS.home)();
  els.body.innerHTML = `<div class="view">${body}</div>`;
  hydrateImages(els.body);
  applyHighlights();
  setOffline(...offlineStatus);
  const clear = $('#clear');
  if (clear) clear.hidden = !state.query;

  const counts = state.museum.galleriesOf(state.results);
  const floorsHit = new Set([...counts.keys()].map(g => state.museum.roomInfo(g)?.floor.id).filter(Boolean));
  if (state.query && floorsHit.size && !floorsHit.has(state.floor)) {
    const target = [...floorsHit][0];
    setFloor(target);
    toast(`Matches on ${state.museum.floor(target).label}`);
    state.map.frameRooms([...counts.keys()]);
  }
}

function computeWorks() {
  const here = r => (r.floor === state.floor ? 0 : 1);
  const filtering = Object.values(state.filters).some(Boolean);
  const browsing = state.tab === 'explore' && current().type === 'browse';
  state.results = state.query || filtering
    ? state.museum.search(state.query, state.filters).sort((a, b) => here(a) - here(b))
    : browsing ? [...state.museum.artworks].sort((a, b) => here(a) - here(b)) : [];
}

function homeBody() {
  const find = FIND.filter(t => state.museum.facilitiesOfType(t).length).map(t => `
    <button class="find__btn" type="button" data-facility="${t}">
      <span class="find__icon">${facilitySVG(t, { size: 24 })}</span>${escape(FACILITIES[t].short ?? FACILITIES[t].label)}</button>`).join('');
  const n = state.museum.artworks.length;
  return `
    <section class="section">
      <ul class="group">
        <li><button class="row" type="button" data-action="browse">
          <span class="row__icon row__icon--accent">${I.grid}</span>
          <span class="row__text"><span class="row__title">All Works</span><span class="row__sub">${n} on view · filter by type, country, period</span></span>
          ${I.chev}</button></li>
      </ul>
    </section>
    <section class="section">
      <div class="section__head"><h3 class="section__title">Find</h3></div>
      <div class="find">${find}</div>
    </section>
    <p class="caption" id="offline"></p>`;
}

function resultsBody() {
  const places = placesHTML();
  const res = state.results;
  const filters = activeFiltersHTML();
  if (!res.length) {
    return places + filters + (places ? '' : emptyHTML(I.search.replace('search__icon', ''), 'No Results', `Nothing on view matches “${escape(state.query)}”. Try an artist’s surname, a gallery number, or a place like “restroom”.`));
  }
  const rooms = state.museum.galleriesOf(res).size;
  return `${places}
    <section class="section">
      <div class="section__head"><h3 class="section__title">Works</h3><span class="row__detail">${res.length} in ${rooms} ${rooms === 1 ? 'gallery' : 'galleries'}</span></div>
      ${filters}${worksHTML(res)}
    </section>`;
}

function placesHTML() {
  if (!state.places.length) return '';
  const rows = state.places.map(p => {
    if (p.kind === 'facility') {
      const floors = [...p.byFloor.entries()]
        .sort((a, b) => (state.museum.floor(a[0]).order ?? 0) - (state.museum.floor(b[0]).order ?? 0))
        .map(([id, n]) => `${floorShort(id)}${n > 1 ? ` ×${n}` : ''}`).join(' · ');
      return `<li><button class="row" type="button" data-facility="${p.type}">
        <span class="row__icon">${facilitySVG(p.type, { size: 18 })}</span>
        <span class="row__text"><span class="row__title">${escape(p.label)}</span><span class="row__sub">${escape(floors)}</span></span>${I.chev}</button></li>`;
    }
    return `<li><button class="row" type="button" data-room="${escape(p.room.id)}">
      <span class="row__icon">${I.pin}</span>
      <span class="row__text"><span class="row__title">${escape(p.room.name)}</span><span class="row__sub">${escape(p.floor.label)}</span></span>${I.chev}</button></li>`;
  }).join('');
  return `<section class="section"><div class="section__head"><h3 class="section__title">Places</h3></div><ul class="group">${rows}</ul></section>`;
}

function browseBody() {
  computeWorks();
  const res = state.results;
  const selects = FILTERS.map(f => {
    const value = state.filters[f.key];
    const options = state.museum.filterOptions(f.key, state.filters);
    return `<label class="select ${value ? 'select--on' : ''}">
      <span class="visually-hidden">${escape(f.label)}</span>
      <select data-filter="${f.key}">
        <option value="">${escape(f.all)}</option>
        ${options.map(o => `<option value="${escape(o.value)}" ${o.value === value ? 'selected' : ''}>${escape(o.value)} (${o.count})</option>`).join('')}
      </select>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 10 5 5 5-5"/></svg>
    </label>`;
  }).join('');
  const filtering = Object.values(state.filters).some(Boolean);
  const rooms = state.museum.galleriesOf(res).size;
  return `
    <div class="filters">${selects}</div>
    <p class="caption">${res.length} ${res.length === 1 ? 'work' : 'works'} in ${rooms} ${rooms === 1 ? 'gallery' : 'galleries'}${filtering ? ' · <button class="link" type="button" data-action="clear-filters">Clear Filters</button>' : ''}</p>
    <div class="section">${res.length ? worksHTML(res) : emptyHTML(I.grid, 'No Works', 'Nothing on view matches these filters.')}</div>`;
}

function activeFiltersHTML() {
  const active = FILTERS.filter(f => state.filters[f.key]).map(f => state.filters[f.key]);
  if (!active.length) return '';
  return `<p class="caption">Filtered: ${escape(active.join(' · '))} · <button class="link" type="button" data-action="clear-filters">Clear</button></p>`;
}

function worksHTML(works) {
  const shown = works.slice(0, state.shown);
  const more = works.length - shown.length;
  const lit = new Set(state.query || Object.values(state.filters).some(Boolean) ? state.results.map(a => a.gallery) : []);
  return `<ul class="work-list">${shown.map(a => `
    <li><button class="work" type="button" data-art="${a.id}">
      ${imgHTML(a, 'thumb')}
      <span><span class="work__title">${escape(a.title)}</span>
      <span class="work__meta">${escape([shortArtist(a.artist), a.date].filter(Boolean).join(' · '))}</span></span>
      <span class="gal ${lit.has(a.gallery) ? 'gal--lit' : ''}" aria-label="Gallery ${escape(a.gallery ?? 'not listed')}">${a.gallery ? escape(a.gallery) : '—'}</span>
    </button></li>`).join('')}</ul>
    ${more > 0 ? `<button class="more-btn" type="button" data-action="more">Show ${Math.min(more, PAGE)} More</button>` : ''}`;
}

function setFilter(key, value) {
  state.filters[key] = value;
  state.shown = PAGE;
  render();
  const ids = [...state.museum.galleriesOf(state.results).keys()];
  const floors = new Set(ids.map(g => state.museum.roomInfo(g)?.floor.id).filter(Boolean));
  if (floors.size && !floors.has(state.floor)) setFloor([...floors][0]);
}

// ---------- rooms & spaces ----------

function roomView(id) {
  const info = state.museum.roomInfo(id);
  if (info?.room.kind === 'space') return spaceView(info);
  const hits = new Set(state.results.map(a => a.id));
  const works = [...state.museum.worksIn(id)].sort((a, b) => hits.has(b.id) - hits.has(a.id));
  const name = state.museum.galleryName(id);
  const roomId = info?.room.id ?? id;
  const body = `
    ${name ? `<p class="place__name">${escape(name)}</p>` : ''}
    <p class="place__sub">${escape(info?.floor.label ?? '')} · ${works.length} ${works.length === 1 ? 'work' : 'works'} on view</p>
    ${info ? `<div class="btn-row">
      <button class="btn" type="button" data-action="directions" data-id="${escape(roomId)}">${I.walk}Directions</button>
      ${visitedButton(roomId)}
    </div>` : ''}
    ${works.length ? `<section class="section"><div class="cards">${works.slice(0, state.shown).map(a => `
      <button class="card" type="button" data-art="${a.id}">
        ${hits.has(a.id) && state.query ? '<span class="card__badge">Match</span>' : ''}
        ${imgHTML(a, 'card__img')}
        <p class="card__title">${escape(a.title)}</p>
        <p class="card__meta">${escape([shortArtist(a.artist), a.date].filter(Boolean).join(' · '))}</p>
      </button>`).join('')}</div>
      ${works.length > state.shown ? '<button class="more-btn" type="button" data-action="more">Show More</button>' : ''}</section>`
      : emptyHTML(I.grid, 'No Works Listed', 'The guide has no works on view in this gallery yet.')}
    ${connectionsHTML(roomId)}`;
  return [headerBar(roomLabel(roomId)), body];
}

function spaceView(info) {
  const { room, floor } = info;
  const inside = (floor.amenities ?? []).filter(a => pointInPoly(a.at, room.poly));
  const types = [...new Set(inside.map(a => a.type))];
  const body = `
    <p class="place__sub">${escape(floor.label)}</p>
    <div class="btn-row">
      <button class="btn" type="button" data-action="directions" data-id="${escape(room.id)}">${I.walk}Directions</button>
      ${visitedButton(room.id)}
    </div>
    ${types.length ? `<section class="section"><div class="section__head"><h3 class="section__title">Here</h3></div>
      <ul class="group">${types.map(t => `<li><button class="row" type="button" data-facility="${t}">
        <span class="row__icon">${facilitySVG(t, { size: 18 })}</span><span class="row__text"><span class="row__title">${escape(FACILITIES[t]?.label ?? t)}</span></span>${I.chev}</button></li>`).join('')}</ul></section>` : ''}
    ${connectionsHTML(room.id)}`;
  return [headerBar(room.name), body];
}

function connectionsHTML(id) {
  const { direct, viaCorridor } = state.museum.connections(id);
  if (!direct.length && !viaCorridor.length) return '';
  const row = rid => `<li><button class="row" type="button" data-room="${escape(rid)}">
    <span class="row__icon">${I.door}</span>
    <span class="row__text"><span class="row__title">${escape(roomLabel(rid))}</span></span>${I.chev}</button></li>`;
  return `
    ${direct.length ? `<section class="section"><div class="section__head"><h3 class="section__title">Doorways</h3></div><ul class="group">${direct.map(row).join('')}</ul></section>` : ''}
    ${viaCorridor.length ? `<section class="section"><div class="section__head"><h3 class="section__title">Through the Corridor</h3></div><ul class="group">${viaCorridor.map(row).join('')}</ul></section>` : ''}`;
}

function openRoom(id, { fly = false } = {}) {
  const info = state.museum.roomInfo(id);
  const view = { type: 'room', id: info?.room.id ?? id };
  const s = state.stacks[state.tab];
  if (current().type === 'room') s[s.length - 1] = view;   // swap rooms instead of piling them up
  else s.push(view);
  state.map.select(id);
  if (fly) state.map.focusRoom(id);
  state.shown = PAGE;
  render();
  if (els.sheet.dataset.state === 'peek') setSheet('half');
}

// ---------- artwork ----------

function artBody(id) {
  const a = state.museum.artworks.find(x => x.id === id);
  if (!a) return emptyHTML(I.grid, 'Not Found', '');
  const info = state.museum.roomInfo(a.gallery);
  const facts = [['Date', a.date], ['Medium', a.medium], ['Size', a.dimensions], ['Type', a.type], ['Country', a.country],
    ['Credit', a.creditLine], ['Accession', a.accession], ['Acquired', acquired(a)]]
    .filter(([, v]) => v).map(([k, v]) => `<li><div class="row"><dt>${k}</dt><dd>${escape(v)}</dd></div></li>`).join('');
  return `
    ${a.image || a.img ? `<div class="art__frame">${imgHTML(a, 'art__img', a.title)}</div>` : ''}
    <div class="art__head"><h2 class="art__title">${escape(a.title)}</h2></div>
    ${a.artist ? `<p class="art__artist">${escape(a.artist)}</p>` : ''}
    ${a.artistDetails ? `<p class="art__life">${escape(a.artistDetails)}</p>` : ''}
    ${info ? `<div class="btn-row">
      <button class="btn" type="button" data-action="directions" data-id="${escape(info.room.id)}">${I.walk}Directions</button>
      <button class="btn btn--gray" type="button" data-room="${escape(a.gallery)}">${I.pin}Gallery ${escape(a.gallery)}</button>
    </div>` : ''}
    ${aboutHTML(a.description)}
    ${curiositiesHTML(state.museum.curiosities?.for(a) ?? [])}
    <dl class="facts"><ul class="group">${facts}
      <li><div class="row"><dt>Where</dt><dd>${info ? `${escape(info.floor.label)} · Gallery ${escape(a.gallery)}${a.galleryName ? `<br><span style="color:var(--ink-2)">${escape(a.galleryName)}</span>` : ''}`
        : escape(a.location || (a.gallery ? `Gallery ${a.gallery} (not on the map)` : 'On view'))}</dd></div></li>
    </ul></dl>
    <div class="stack"><a class="btn btn--ink" href="${a.url}" target="_blank" rel="noopener">View on the MFA Website</a></div>
    ${a.imageSource ? `<p class="credit">Image: <a href="${a.imageSource}" target="_blank" rel="noopener">${escape(a.imageCredit ?? 'source')}</a></p>`
      : a.img ? '<p class="credit">Image: Museum of Fine Arts, Boston</p>' : ''}`;
}

// How and when the work came to the museum: "Gift · March 31, 1919".
// The method comes from the credit line; the date from the provenance, or else the year in the
// accession number (58.356 came in 1958; 1983.12 in 1983). Two-digit numbers from 70 up are left
// alone, since they could mean the 1870s or the 1970s.
function acquired(a) {
  const c = a.creditLine ?? '';
  const how = /expedition/i.test(c) ? 'Excavation'
    : /^bequest|\bbequest of\b/i.test(c) ? 'Bequest'
    : /\bexchange\b/i.test(c) ? 'Exchange'
    : /purchase|\bfund\b|\bfunds\b/i.test(c) ? 'Purchase'
    : /\bgift\b/i.test(c) ? 'Gift'
    : '';
  let when = a.accessionDate ?? '';
  if (!when) {
    const m = String(a.accession ?? '').match(/^(\d{2,4})\./);
    if (m && m[1].length === 4) when = m[1];
    else if (m && m[1].length === 2 && +m[1] < 70) when = `19${m[1]}`;
  }
  return [how, when].filter(Boolean).join(' · ');
}

// The museum's own text about the work, set like a wall label. Long texts open with Read More.
function aboutHTML(text) {
  if (!text) return '';
  const paras = text.split(/\n{2,}/).map(p => `<p>${escape(p)}</p>`).join('');
  const long = text.length > 420;
  return `<section class="about${long ? ' about--folded' : ''}" aria-labelledby="aboutTitle">
    <h3 class="about__title" id="aboutTitle">About This Work</h3>
    <div class="about__text">${paras}</div>
    ${long ? '<button class="about__more" type="button" data-action="read-more" aria-expanded="false">Read More</button>' : ''}
  </section>`;
}

// Did-you-know notes written for the app (see data/curiosities.json), grouped by layer.
function curiositiesHTML(groups) {
  if (!groups.length) return '';
  return `<section class="curio" aria-labelledby="curioTitle">
    <h3 class="about__title" id="curioTitle">Curiosities</h3>
    ${groups.map(g => `<div class="curio__group">
      <p class="curio__label">${escape(g.label)}</p>
      <ul class="curio__list">${g.facts.map(f => `<li>${escape(f)}</li>`).join('')}</ul>
    </div>`).join('')}
    <p class="curio__note">Written for this app from general art-history knowledge, not by the MFA. May contain mistakes.</p>
  </section>`;
}

function openArt(id) {
  const art = state.museum.artworks.find(a => a.id === id);
  if (!art) return;
  if (state.museum.isMapped(art.gallery)) {
    state.map.select(art.gallery);
    state.map.focusRoom(art.gallery, { zoom: false });
  }
  push({ type: 'art', id }, { sheet: 'full' });
}

function favButton(id) {
  const on = state.favorites.includes(id);
  return `<button class="fav-btn ${on ? 'fav-btn--on' : ''}" type="button" data-action="favorite" data-id="${escape(id)}"
    aria-pressed="${on}" aria-label="${on ? 'Remove from Saved' : 'Save'}">${I.heart(on)}</button>`;
}

async function toggleFavorite(id) {
  const on = await Favorites.toggle(id);
  state.favorites = await Favorites.list();
  const btn = els.header.querySelector('[data-action="favorite"]');
  if (btn) btn.outerHTML = favButton(id);
  toast(on ? 'Saved' : 'Removed from Saved');
}

function favoriteWorks() {
  return state.favorites.map(id => state.museum.artworks.find(a => a.id === id)).filter(Boolean);
}

// ---------- saved ----------

function savedBody() {
  const works = favoriteWorks();
  if (!works.length) return emptyHTML(I.heart(false), 'Nothing Saved Yet', 'Tap the heart on any work to keep it here, then walk to all of them in one route.');
  const rooms = [...state.museum.galleriesOf(works).keys()].filter(g => state.museum.isMapped(g));
  return `
    <p class="lead">${works.length} ${works.length === 1 ? 'work' : 'works'} in ${rooms.length} ${rooms.length === 1 ? 'gallery' : 'galleries'}</p>
    ${rooms.length ? `<div class="stack"><button class="btn" type="button" data-action="route-favorites">${I.walk}Walk to All</button></div>` : ''}
    <section class="section">${worksHTML(works)}</section>`;
}

function routeFavorites() {
  const rooms = [...state.museum.galleriesOf(favoriteWorks()).keys()].filter(g => state.museum.isMapped(g));
  if (!rooms.length) return;
  const order = state.router.orderStops(state.here ?? rooms[0], rooms, { avoidStairs: state.avoidStairs });
  directionsTo(order, { title: `Saved · ${order.length} ${order.length === 1 ? 'gallery' : 'galleries'}` });
}

// ---------- directions ----------

function directionsTo(stops, { title } = {}) {
  state.route = { stops, title: title || `To ${roomLabel(stops.at(-1))}`, result: null };
  computeRoute();
  push({ type: 'directions' }, { sheet: 'half' });
}

function computeRoute() {
  const r = state.route;
  if (!r) return;
  state.map.clearRoute();
  r.result = null;
  r.segments = null;
  if (!state.here) return;
  const stops = r.stops.filter(id => id !== state.here);
  r.result = stops.length ? state.router.routeThrough([state.here, ...stops], { avoidStairs: state.avoidStairs }) : null;
  if (!r.result) return;
  r.segments = state.router.segments(r.result);
  state.map.showRoute(r.segments);
  showRouteFloor(r.segments[0].floorId);
}

function showRouteFloor(floorId) {
  const seg = state.route?.segments?.find(s => s.floorId === floorId);
  setFloor(floorId);
  if (seg) state.map.frameRooms([], seg.points.map(p => state.map.toWorld(p, state.museum.floor(floorId))));
}

function clearRoute() {
  state.map.clearRoute();
  state.route = null;
  state.picking = false;
  pop();
}

function setHere(id, label = null) {
  state.here = state.museum.roomInfo(id)?.room.id ?? id;
  state.hereLabel = label;
  state.picking = false;
  toast(`Starting from ${hereName()}`);
  if (state.tour && state.tab === 'tours') { routeToStop(); return; }
  computeRoute();
  render();
  setSheet('half');
}

function hereName() { return state.hereLabel || roomLabel(state.here); }

function directionsBody() {
  const r = state.route;
  if (!r) return '';
  const to = `<li><div class="row"><span class="row__icon row__icon--accent">${I.pin}</span>
      <span class="row__text"><span class="row__sub">To</span><span class="row__title">${escape(r.title.replace(/^To /, ''))}</span></span><span></span></div></li>`;
  if (!state.here) {
    const recent = [...new Set((state.visit?.rooms ?? []).map(x => x.id).reverse())].slice(0, 3);
    const options = [
      ...recent.map(id => ({ id, label: roomLabel(id), icon: I.check })),
      ...entranceRooms().map(e => ({ id: e.id, label: e.label, icon: facilitySVG('entrance', { size: 18 }) })),
    ];
    return `
      <ul class="group">${to}</ul>
      <section class="section">
        <div class="section__head"><h3 class="section__title">Where Are You?</h3></div>
        <ul class="group">${options.map(o => `<li><button class="row" type="button" data-action="set-here" data-id="${escape(o.id)}" data-label="${escape(o.label)}">
          <span class="row__icon">${o.icon}</span><span class="row__text"><span class="row__title">${escape(o.label)}</span></span>${I.chev}</button></li>`).join('')}</ul>
        <div class="stack"><button class="btn btn--gray" type="button" data-action="pick-here">${I.pin}Tap My Room on the Map</button></div>
      </section>`;
  }
  const from = `<li><button class="row" type="button" data-action="pick-here"><span class="row__icon">${I.dot}</span>
      <span class="row__text"><span class="row__sub">From</span><span class="row__title">${escape(hereName())}</span></span><span class="row__detail">Change ${I.chev}</span></button></li>`;
  const toggle = `<ul class="group"><li><button class="switch" type="button" role="switch" aria-checked="${state.avoidStairs}" data-action="avoid-stairs">
      Avoid Stairs<span class="switch__track"><span class="switch__knob"></span></span></button></li></ul>`;
  const res = r.result;
  if (!res) {
    const same = r.stops.length === 1 && r.stops[0] === state.here;
    return `<ul class="group">${from}${to}</ul>
      ${emptyHTML(I.walk, same ? 'You’re Already Here' : 'No Route Found', same ? '' : 'The map has no connection between these rooms. Try another starting point.')}
      <section class="section">${toggle}</section>`;
  }
  const steps = state.router.steps(res);
  const floors = [...new Set(r.segments.map(s => s.floorId))];
  let n = 0;
  const stepRows = [
    `<li><div class="step step--start"><span class="step__dot">${I.dot}</span><span class="step__text">Start at <em>${escape(hereName())}</em></span></div></li>`,
    ...steps.map(st => {
      if (st.kind === 'stairs' || st.kind === 'elevator') {
        return `<li><div class="step step--floor"><span class="step__dot">${st.kind === 'stairs' ? I.stairs : facilitySVG('elevator', { size: 16 })}</span>
          <button class="step__text" type="button" data-action="show-floor" data-floor="${escape(floorFromStep(st))}">${escape(st.text)}</button></div></li>`;
      }
      const stop = r.stops.includes(st.id);
      n++;
      const name = st.text.replace(/^(Go into|Into) /, '');
      return `<li><div class="step ${stop ? 'step--stop' : ''}"><span class="step__dot">${stop ? I.pin : n}</span>
        <span class="step__text">${st.kind === 'corridor' ? escape(st.text) : `Into <em>${escape(name)}</em>`}${stop ? `<span class="step__tag">${r.stops.length > 1 ? `Stop ${r.stops.indexOf(st.id) + 1}` : 'Arrive'}</span>` : ''}</span></div></li>`;
    }),
  ].join('');
  return `
    <ul class="group">${from}${to}</ul>
    <div class="route-sum"><strong>${state.router.minutes(res)} min</strong><span>${state.router.meters(res)} m${floors.length > 1 ? ` · ${floors.length} floors` : ''}</span></div>
    <section class="section">${toggle}</section>
    <section class="section"><ul class="group">${stepRows}</ul></section>
    ${floors.length > 1 ? `<section class="section"><div class="pills">${floors.map(f => `<button class="pill" type="button" data-action="show-floor" data-floor="${escape(f)}">${I.floor}${escape(state.museum.floor(f).label)}</button>`).join('')}</div></section>` : ''}`;
}

function floorFromStep(step) {
  const m = step.text.match(/to (Level .+)$/);
  return state.museum.floors.find(f => f.label === m?.[1])?.id ?? '';
}

function entranceRooms() {
  const out = [];
  for (const floor of state.museum.floors) {
    for (const f of floor.amenities ?? []) {
      if (f.type !== 'entrance') continue;
      const room = floor.rooms.find(r => r.kind !== 'corridor' && pointInPoly(f.at, r.poly))
        ?? floor.rooms.find(r => pointInPoly(f.at, r.poly)) ?? nearestRoomTo(floor, f.at);
      const note = (floor.labels ?? []).filter(l => /entrance/i.test(l.text))
        .sort((a, b) => Math.hypot(a.at[0] - f.at[0], a.at[1] - f.at[1]) - Math.hypot(b.at[0] - f.at[0], b.at[1] - f.at[1]))[0];
      if (room) out.push({ id: room.id, label: note ? note.text.replace(/\s*\(.*\)\s*/, '') : `Entrance · ${floor.label}` });
    }
  }
  return out.filter((e, i) => out.findIndex(x => x.id === e.id) === i);
}

function nearestRoomTo(floor, at) {
  let best = null, bd = Infinity;
  for (const r of floor.rooms) for (const [x, y] of r.poly) {
    const d = Math.hypot(x - at[0], y - at[1]);
    if (d < bd) { bd = d; best = r; }
  }
  return bd < 60 ? best : null;
}

// Show where a facility is: this floor if it has one, otherwise the first floor that does.
function openFacility(type) {
  const all = state.museum.facilitiesOfType(type);
  if (!all.length) return;
  const floors = [...new Set(all.map(f => f.floor.id))];
  const target = floors.includes(state.floor) ? state.floor : floors[0];
  setFloor(target);
  state.map.highlightFacilities(new Set([type]));
  const here = all.filter(f => f.floor.id === target);
  state.map.frameRooms([], here.map(f => state.map.toWorld(f.at, f.floor)));
  setSheet('peek');
  toast(`${FACILITIES[type].label} · ${state.museum.floor(target).label}${here.length > 1 ? ` · ${here.length}` : ''}`);
}

// ---------- tours ----------

function currentTour() { return state.tours.find(t => t.id === state.tour?.id) ?? null; }
function tourWorks(stop) { return (stop.works ?? []).map(id => state.museum.artworks.find(a => a.id === id)).filter(Boolean); }

function toursBody() {
  const active = currentTour();
  const live = active ? `<ul class="group"><li><button class="row" type="button" data-action="resume-tour">
      <span class="row__icon row__icon--live">${I.route}</span>
      <span class="row__text"><span class="row__title">${escape(active.title)}</span><span class="row__sub">Stop ${state.tour.index + 1} of ${active.stops.length} · Continue</span></span>${I.chev}</button></li></ul>` : '';
  return `${live}<section class="section">${state.tours.map(t => {
    const works = t.stops.flatMap(tourWorks).slice(0, 3);
    const floors = [...new Set(t.stops.map(s => state.museum.roomInfo(s.gallery)?.floor.label).filter(Boolean))];
    return `<button class="tour-card" type="button" data-action="tour" data-id="${t.id}">
      <span class="tour-card__strip">${[0, 1, 2].map(i => works[i] ? imgHTML(works[i], '') : '<span></span>').join('')}</span>
      <span class="tour-card__body">
        <span class="tour-card__title">${escape(t.title)}</span>
        <span class="tour-card__meta">${t.minutes} min · ${t.stops.length} stops · ${escape(floors.join(', '))}</span>
      </span></button>`;
  }).join('')}</section>`;
}

function tourBody(id) {
  const t = state.tours.find(x => x.id === id);
  if (!t) return '';
  return `
    <h2 class="art__title">${escape(t.title)}</h2>
    <p class="place__sub">${t.minutes} min · ${t.stops.length} stops</p>
    <p class="lead" style="margin-left:0">${escape(t.description ?? '')}</p>
    <div class="stack"><button class="btn" type="button" data-action="start-tour" data-id="${t.id}">${I.walk}Start Tour</button></div>
    <ol class="stops">${t.stops.map(s => `
      <li class="stop">
        <button class="stop__name" type="button" data-room="${escape(s.gallery)}">${escape(roomLabel(s.gallery))}</button>
        <p class="stop__note">${escape(s.note ?? '')}</p>
        <div class="stop__thumbs">${tourWorks(s).map(a => `<button type="button" data-art="${a.id}" aria-label="${escape(a.title)}">${imgHTML(a, 'thumb')}</button>`).join('')}</div>
      </li>`).join('')}</ol>`;
}

async function startTour(id) {
  state.tour = { id, index: 0 };
  if (!state.visit) { state.visit = await Visits.start(); updateVisitUI(); }
  routeToStop();
}

function routeToStop() {
  const t = currentTour();
  if (!t) return;
  const stop = t.stops[state.tour.index];
  state.route = { stops: [stop.gallery], title: `To ${roomLabel(stop.gallery)}` };
  computeRoute();
  if (!state.route.result) state.map.focusRoom(stop.gallery, { zoom: false });
  state.map.select(stop.gallery);
  state.stacks.tours = [{ type: 'tours' }, { type: 'tour-stop' }];
  if (!state.here) state.stacks.tours.push({ type: 'directions' });
  if (state.tab !== 'tours') setTab('tours'); else render();
  setSheet('half');
}

function tourStopView() {
  const t = currentTour();
  if (!t) return [headerTitle('Tours'), toursBody()];
  const i = state.tour.index;
  const stop = t.stops[i];
  const last = i === t.stops.length - 1;
  const res = state.route?.result;
  const info = state.museum.roomInfo(stop.gallery);
  const atStop = state.here === info?.room.id;
  const header = headerBar(`Stop ${i + 1} of ${t.stops.length}`, { close: 'end-tour' });
  const body = `
    <div class="progress">${t.stops.map((_, j) => `<span class="${j < i ? 'done' : j === i ? 'now' : ''}"></span>`).join('')}</div>
    <h2 class="art__title" style="margin-top:12px">${escape(roomLabel(stop.gallery))}</h2>
    <p class="place__sub">${escape(info?.floor.label ?? '')}${res ? ` · ${state.router.minutes(res)} min walk` : atStop ? ' · You’re here' : ''}</p>
    <p class="lead" style="margin-left:0">${escape(stop.note ?? '')}</p>
    <div class="btn-row">
      ${res ? `<button class="btn btn--gray" type="button" data-action="show-floor" data-floor="${escape(state.route.segments[0].floorId)}">${I.route}Show Route</button>` : ''}
      <button class="btn" type="button" data-action="next-stop">${last ? 'Finish Tour' : 'Next Stop'}</button>
    </div>
    <section class="section"><div class="cards">${tourWorks(stop).map(a => `
      <button class="card" type="button" data-art="${a.id}">${imgHTML(a, 'card__img')}
        <p class="card__title">${escape(a.title)}</p>
        <p class="card__meta">${escape([shortArtist(a.artist), a.date].filter(Boolean).join(' · '))}</p></button>`).join('')}</div></section>
    <p class="caption">${escape(t.title)}</p>`;
  return [header, body];
}

async function nextStop() {
  const t = currentTour();
  if (!t) return;
  const stop = t.stops[state.tour.index];
  const info = state.museum.roomInfo(stop.gallery);
  const roomId = info?.room.id ?? stop.gallery;
  if (state.visit && !visitedIds().has(roomId)) {
    state.visit = await Visits.toggle(state.visit, roomId, info?.floor.id);
    showVisitedOnMap();
    updateVisitUI();
  }
  state.here = roomId;
  state.hereLabel = null;
  if (state.tour.index >= t.stops.length - 1) { endTour({ done: true }); return; }
  state.tour.index++;
  routeToStop();
}

function endTour({ done = false } = {}) {
  state.tour = null;
  state.map.clearRoute();
  state.map.select(null);
  state.route = null;
  resetTab('tours');
  if (done) { toast('Tour Complete'); setTab('visits'); }
  render();
}

// ---------- visits ----------

function visitedIds() { return new Set(state.visit?.rooms.map(r => r.id) ?? []); }

function showVisitedOnMap() {
  const source = state.replaying ?? state.visit;
  state.map.setVisited(source ? source.rooms.map(r => r.id) : []);
}

function updateVisitUI() {
  const v = state.visit;
  els.visitPill.hidden = !v;
  els.visitBadge.hidden = !v;
  if (v) els.visitPillText.textContent = `${v.rooms.length} ${v.rooms.length === 1 ? 'room' : 'rooms'} · ${duration(v)}`;
}

function visitedButton(roomId) {
  const on = visitedIds().has(roomId);
  return `<button class="check-btn" type="button" aria-pressed="${on}" data-action="toggle-visited" data-id="${escape(roomId)}">
    ${on ? I.check : I.circle}${on ? 'Visited' : 'Mark Visited'}</button>`;
}

async function toggleVisited(id, floorId) {
  if (!id) return;
  const info = state.museum.roomInfo(id);
  const roomId = info?.room.id ?? id;
  if (!state.visit) { state.visit = await Visits.start(); toast('Visit Started'); }
  const was = visitedIds().has(roomId);
  state.visit = await Visits.toggle(state.visit, roomId, floorId ?? info?.floor.id);
  if (!was) { state.here = roomId; state.hereLabel = null; }
  state.replaying = null;
  showVisitedOnMap();
  updateVisitUI();
  toast(`${shortRoomLabel(roomId)} ${was ? 'Unmarked' : 'Visited'}`);
  const btn = els.body.querySelector(`[data-action="toggle-visited"][data-id="${CSS.escape(roomId)}"]`);
  if (btn) btn.outerHTML = visitedButton(roomId);
  else if (state.tab === 'visits') render();
}

async function startVisit() {
  state.visit = await Visits.start();
  state.replaying = null;
  showVisitedOnMap();
  updateVisitUI();
  toast('Visit Started');
  render();
}

function visitsBody() {
  const v = state.visit;
  const live = v ? `
    <div class="live">
      <div class="live__stats">
        <div class="live__stat"><strong>${v.rooms.length}</strong><span>${v.rooms.length === 1 ? 'Room' : 'Rooms'}</span></div>
        <div class="live__stat"><strong>${duration(v)}</strong><span>Since ${formatTime(v.startedAt)}</span></div>
        <div class="live__stat"><strong>${new Set(v.rooms.map(r => r.floor)).size}</strong><span>Floors</span></div>
      </div>
      <div class="stack"><button class="btn" type="button" data-action="finish-visit">${I.flag}Finish Visit</button></div>
    </div>
    <p class="caption">Mark rooms from their page, or press and hold a room on the map.</p>
    ${v.rooms.length ? `<section class="section"><div class="section__head"><h3 class="section__title">This Visit</h3></div>
      <ul class="group timeline">${[...v.rooms].reverse().map(timelineRow).join('')}</ul></section>` : ''}
    <button class="btn btn--danger" type="button" data-action="discard-visit">Discard Visit</button>`
    : `<div class="live">
        <p class="lead" style="margin:0 0 4px">Check off rooms as you walk. When you leave, the visit is saved with a map of your route.</p>
        <div class="stack"><button class="btn" type="button" data-action="start-visit">${I.flag}Start a Visit</button></div>
      </div>`;
  const diary = state.diary.length ? `
    <section class="section"><div class="section__head"><h3 class="section__title">Diary</h3></div>
      <ul class="group" style="--sep-inset:80px">${state.diary.map(e => {
        const snap = Object.values(e.snapshots ?? {})[0];
        return `<li><button class="row" type="button" data-action="entry" data-id="${e.id}">
          ${snap ? `<img class="entry-thumb" src="${blobURL(e.id, snap)}" alt="">` : '<span class="entry-thumb"></span>'}
          <span class="row__text"><span class="row__title">${escape(formatDay(e.startedAt))}</span>
          <span class="row__sub">${e.rooms.length} ${e.rooms.length === 1 ? 'room' : 'rooms'} · ${duration(e)}</span></span>${I.chev}</button></li>`;
      }).join('')}</ul></section>` : '';
  return live + diary;
}

function timelineRow(r) {
  return `<li><button class="row" type="button" data-room="${escape(r.id)}">
    <span class="timeline__time">${formatTime(r.at)}</span>
    <span class="timeline__name">${escape(roomLabel(r.id))}</span>
    <span class="row__detail">${escape(floorShort(r.floor))}</span></button></li>`;
}

async function finishVisit() {
  const v = state.visit;
  if (!v) return;
  if (!v.rooms.length) { await Visits.discard(); state.visit = null; updateVisitUI(); render(); return; }
  els.body.innerHTML = `<div class="view">${emptyHTML(I.flag, 'Saving Your Visit…', 'Drawing a map of each floor you walked.')}</div>`;
  const floors = [...new Set(v.rooms.map(r => r.floor))]
    .sort((a, b) => (state.museum.floor(a)?.order ?? 0) - (state.museum.floor(b)?.order ?? 0));
  const snapshots = {};
  state.map.setVisited(v.rooms.map(r => r.id));
  for (const f of floors) {
    try { snapshots[f] = await state.map.snapshot(f, { route: v.rooms.map(r => r.id) }); } catch (err) { console.warn('snapshot failed', err); }
  }
  const saved = await Visits.finish(v, snapshots);
  state.visit = null;
  state.diary = await Visits.list();
  showVisitedOnMap();
  updateVisitUI();
  state.stacks.visits = [{ type: 'visits' }, { type: 'entry', id: saved.id }];
  render();
  setSheet('full');
}

async function discardVisit(button) {
  if (!button.dataset.confirm) {
    button.dataset.confirm = '1';
    button.textContent = 'Tap Again to Discard';
    return;
  }
  await Visits.discard();
  state.visit = null;
  showVisitedOnMap();
  updateVisitUI();
  render();
}

function entryBody(id) {
  const e = state.diary.find(x => x.id === id);
  if (!e) return '';
  const floors = Object.keys(e.snapshots ?? {});
  const works = new Set(e.rooms.flatMap(r => state.museum.worksIn(r.id).map(a => a.id))).size;
  return `
    <h2 class="art__title">${escape(formatDay(e.startedAt))}</h2>
    <p class="place__sub">${formatTime(e.startedAt)}–${formatTime(e.endedAt)} · ${duration(e)} · ${e.rooms.length} ${e.rooms.length === 1 ? 'room' : 'rooms'}${works ? ` · ${works} works` : ''}</p>
    <div class="stack"><button class="btn" type="button" data-action="replay" data-id="${e.id}">${I.route}Show on Map</button></div>
    ${floors.map(f => `<figure class="snapshot">
      <img src="${blobURL(`${e.id}:${f}`, e.snapshots[f])}" alt="Map of ${escape(state.museum.floor(f)?.label ?? f)} with the rooms you visited">
      <figcaption>${escape(state.museum.floor(f)?.label ?? f)}</figcaption></figure>`).join('')}
    <section class="section"><div class="section__head"><h3 class="section__title">Your Route</h3></div>
      <ul class="group timeline">${e.rooms.map(timelineRow).join('')}</ul></section>
    <button class="btn btn--danger" type="button" data-action="delete-entry" data-id="${e.id}">Delete Visit</button>`;
}

function replayVisit(id) {
  const entry = state.diary.find(e => e.id === id);
  if (!entry) return;
  state.replaying = entry;
  showVisitedOnMap();
  const first = entry.rooms[0];
  if (first) setFloor(first.floor);
  state.map.frameRooms(entry.rooms.filter(r => r.floor === state.floor).map(r => r.id));
  setSheet('peek');
  toast(`Your Visit of ${formatDay(entry.startedAt)}`);
}

async function deleteEntry(button) {
  if (!button.dataset.confirm) {
    button.dataset.confirm = '1';
    button.textContent = 'Tap Again to Delete';
    return;
  }
  await Visits.remove(button.dataset.id);
  state.diary = await Visits.list();
  if (state.replaying?.id === button.dataset.id) { state.replaying = null; showVisitedOnMap(); }
  resetTab('visits');
  render();
}

// ---------- map taps ----------

function onMapTap(hit) {
  if (state.picking && (hit.kind === 'gallery' || hit.kind === 'space')) { setHere(hit.id); return; }
  if (hit.long) { toggleVisited(hit.id, hit.floorId); return; }
  if (hit.kind === 'facility') {
    toast(`${FACILITIES[hit.type]?.label ?? hit.type} · ${state.museum.floor(hit.floorId).label}`);
    return;
  }
  if (!hit.kind) {
    if (current().type === 'room') pop();
    return;
  }
  openRoom(hit.id);
}

// ---------- one handler for everything in the sheet ----------

els.sheet.addEventListener('click', e => {
  const t = e.target.closest('[data-query],[data-art],[data-room],[data-facility],[data-action]');
  if (!t) return;
  const a = t.dataset.action;
  if (t.dataset.query) {
    const q = $('#q');
    if (q) q.value = t.dataset.query;
    runSearch(t.dataset.query);
    setSheet('half');
    state.map.frameRooms([...state.museum.galleriesOf(state.results).keys()]);
  }
  else if (t.dataset.art) openArt(t.dataset.art);
  else if (t.dataset.room) openRoom(t.dataset.room, { fly: true });
  else if (t.dataset.facility) openFacility(t.dataset.facility);
  else if (a === 'pop') pop();
  else if (a === 'browse') push({ type: 'browse' }, { sheet: 'full' });
  else if (a === 'clear-filters') { state.filters = { type: '', country: '', period: '' }; computeWorks(); render(); }
  else if (a === 'more') { const top = els.body.scrollTop; state.shown += PAGE; render(); els.body.scrollTop = top; }
  else if (a === 'read-more') {
    const box = t.closest('.about');
    const open = box.classList.toggle('about--folded') === false;
    t.textContent = open ? 'Show Less' : 'Read More';
    t.setAttribute('aria-expanded', String(open));
  }
  else if (a === 'favorite') toggleFavorite(t.dataset.id);
  else if (a === 'route-favorites') routeFavorites();
  else if (a === 'directions') directionsTo([t.dataset.id]);
  else if (a === 'pick-here') { state.picking = true; setSheet('peek'); toast('Tap the room you’re in'); }
  else if (a === 'set-here') setHere(t.dataset.id, t.dataset.label);
  else if (a === 'avoid-stairs') { state.avoidStairs = !state.avoidStairs; computeRoute(); render(); }
  else if (a === 'clear-route') clearRoute();
  else if (a === 'show-floor') { showRouteFloor(t.dataset.floor); setSheet('peek'); }
  else if (a === 'tour') push({ type: 'tour', id: t.dataset.id }, { sheet: 'full' });
  else if (a === 'resume-tour') { state.stacks.tours = [{ type: 'tours' }, { type: 'tour-stop' }]; render(); }
  else if (a === 'start-tour') startTour(t.dataset.id);
  else if (a === 'next-stop') nextStop();
  else if (a === 'end-tour') endTour();
  else if (a === 'toggle-visited') toggleVisited(t.dataset.id);
  else if (a === 'start-visit') startVisit();
  else if (a === 'finish-visit') finishVisit();
  else if (a === 'discard-visit') discardVisit(t);
  else if (a === 'entry') push({ type: 'entry', id: t.dataset.id }, { sheet: 'full' });
  else if (a === 'replay') replayVisit(t.dataset.id);
  else if (a === 'delete-entry') deleteEntry(t);
});

els.body.addEventListener('change', e => {
  const sel = e.target.closest('[data-filter]');
  if (sel) setFilter(sel.dataset.filter, sel.value);
});

// ---------- sheet ----------

function setSheet(s) {
  els.sheet.dataset.state = s;
  els.grab.setAttribute('aria-expanded', String(s !== 'peek'));
  updateInsets();
}

// Peek shows the grabber and the header (search field or title).
function measurePeek() {
  const peek = Math.round(22 + els.header.offsetHeight + 6);
  els.sheet.style.setProperty('--peek', `${peek}px`);
  state.peek = peek;
  updateInsets();
}

function restingVisible(s) {
  const h = els.sheet.offsetHeight;
  // fully open, the sheet also runs under the tab bar: count only what's above it
  return { peek: state.peek ?? 120, half: h * 0.52, full: h - (els.sheet.dataset.state === 'full' ? tabbarSpace() : 0) }[s];
}

// space below the sheet's frame: the tab bar and its margins
function tabbarSpace() {
  return els.app.clientHeight - $('#sheetClip').getBoundingClientRect().bottom;
}

function updateInsets() {
  const wide = matchMedia('(min-width: 760px)').matches;
  const appH = els.app.clientHeight;
  const tabH = tabbarSpace();
  let visible = els.sheet.classList.contains('dragging')
    ? appH - els.sheet.getBoundingClientRect().top - tabH
    : restingVisible(els.sheet.dataset.state);
  visible = wide ? 0 : Math.max(0, visible);
  const covered = wide ? 0 : visible + tabH;
  if (!wide) els.tools.style.bottom = `${Math.min(covered, appH * 0.66) + 14}px`;
  else els.tools.style.bottom = '';
  const left = wide ? els.sheet.getBoundingClientRect().right : 0;
  state.map?.setViewInsets({ bottom: Math.min(covered, appH * 0.62), left });
}
window.addEventListener('resize', updateInsets);

// iOS-style sheet dragging: from anywhere on the sheet; content moves the sheet until it's fully open;
// at full height the content scrolls and pulling down at the top closes; releases settle on the
// nearest resting height, carried further by a flick.
function wireSheetDrag() {
  const order = ['peek', 'half', 'full'];
  let drag = null;
  let blockClickUntil = 0;

  const begin = (y, target) => {
    drag = {
      y0: y, lastY: y, lastT: performance.now(), v: 0,
      offset0: new DOMMatrixReadOnly(getComputedStyle(els.sheet).transform).m42,
      inBody: !!target.closest('#body'), active: false,
    };
  };
  const claim = dy => {
    if (drag.inBody && els.sheet.dataset.state === 'full' && !(els.body.scrollTop <= 0 && dy > 0)) return false;
    drag.active = true;
    els.sheet.classList.add('dragging');
    if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur();
    return true;
  };
  const move = y => {
    const now = performance.now();
    const dy = y - drag.y0;
    if (!drag.active) {
      if (Math.abs(dy) < 6) return false;
      if (!claim(dy)) { drag = null; return false; }
    }
    drag.v = (y - drag.lastY) / Math.max(1, now - drag.lastT);
    drag.lastY = y; drag.lastT = now;
    let offset = drag.offset0 + dy;
    if (offset < 0) offset = -Math.sqrt(-offset) * 2;   // rubber band past fully open
    els.sheet.style.transform = `translateY(${offset}px)`;
    updateInsets();
    return true;
  };
  const finish = () => {
    if (!drag) return;
    const { active, v } = drag;
    drag = null;
    if (!active) return;
    blockClickUntil = performance.now() + 350;
    const visible = els.app.clientHeight - els.sheet.getBoundingClientRect().top - tabbarSpace();
    const projected = visible - v * 220;
    let best = 'half', bestD = Infinity;
    for (const s of order) {
      const d = Math.abs(restingVisible(s) - projected);
      if (d < bestD) { bestD = d; best = s; }
    }
    els.sheet.classList.remove('dragging');
    els.sheet.style.transform = '';
    setSheet(best);
  };

  els.sheet.addEventListener('touchstart', e => {
    if (e.touches.length !== 1 || e.target.closest('select')) { drag = null; return; }
    begin(e.touches[0].clientY, e.target);
  }, { passive: true });
  els.sheet.addEventListener('touchmove', e => {
    if (drag && move(e.touches[0].clientY)) e.preventDefault();
  }, { passive: false });
  els.sheet.addEventListener('touchend', finish);
  els.sheet.addEventListener('touchcancel', finish);

  els.grab.addEventListener('pointerdown', e => {
    if (e.pointerType !== 'mouse') return;
    begin(e.clientY, e.target);
    const onMove = ev => move(ev.clientY);
    const onUp = () => { window.removeEventListener('pointermove', onMove); window.removeEventListener('pointerup', onUp); finish(); };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  });
  els.grab.addEventListener('click', () => {
    if (performance.now() < blockClickUntil) return;
    setSheet({ peek: 'half', half: 'full', full: 'half' }[els.sheet.dataset.state]);
  });
  els.sheet.addEventListener('click', e => {
    if (performance.now() < blockClickUntil) { e.stopPropagation(); e.preventDefault(); }
  }, true);
}

// ---------- offline ----------

let offlineStatus = [false, 'Checking offline copy…'];

async function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return setOffline(false, 'Offline use isn’t supported in this browser');
  try {
    // when an update takes over, reload once so the new version shows straight away
    const hadController = !!navigator.serviceWorker.controller;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (hadController && !registerServiceWorker.reloaded) { registerServiceWorker.reloaded = true; location.reload(); }
    });
    const reg = await navigator.serviceWorker.register('sw.js');
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') reg.update().catch(() => {}); });
    await navigator.serviceWorker.ready;
    checkOffline();
  } catch (err) {
    console.warn('Service worker failed', err);
    setOffline(false, 'Offline copy unavailable');
  }
}

async function checkOffline() {
  if (!('caches' in window)) return;
  const urls = ['index.html', 'data/artworks.json', 'data/floors.json', 'data/curiosities.json',
    ...new Set(state.museum.artworks.map(a => a.image || a.img?.p).filter(Boolean))];
  const hits = await Promise.all(urls.map(u => caches.match(u)));
  const missing = hits.filter(h => !h).length;
  if (!missing) setOffline(true, `Saved for offline use · ${state.museum.artworks.length} works · checked ${formatDay(`${state.museum.meta.checked}T12:00:00`)}`);
  else { setOffline(false, `Saving for offline… ${urls.length - missing} of ${urls.length}`); setTimeout(checkOffline, 1500); }
}

function setOffline(ready, text) {
  offlineStatus = [ready, text];
  const el = document.getElementById('offline');
  if (el) el.textContent = text;
}

// ---------- images ----------
// Sample works have one file each (`image`); the full collection packs small images into a few
// large files (`img: {p, o, l}` = file, offset, length), read piece by piece as they scroll into view.

const BLANK = 'data:image/gif;base64,R0lGODlhAQABAAAAACw=';

function imgHTML(a, cls, alt = '') {
  if (a.image) return `<img class="${cls}" src="${a.image}" alt="${escape(alt)}" loading="lazy" decoding="async">`;
  if (a.img) return `<img class="${cls}" src="${BLANK}" alt="${escape(alt)}" data-pack="${a.img.p}" data-o="${a.img.o}" data-l="${a.img.l}">`;
  return `<span class="${cls} img-empty" aria-hidden="true"></span>`;
}

const packedURLs = new Map();
function packedImage(p, o, l) {
  const key = `${p}:${o}`;
  if (!packedURLs.has(key)) {
    packedURLs.set(key, (async () => {
      const res = await fetch(p, { headers: { Range: `bytes=${o}-${o + l - 1}` } });
      const blob = await res.blob();
      const part = res.status === 206 ? blob : blob.slice(o, o + l);
      return URL.createObjectURL(new Blob([part], { type: 'image/jpeg' }));
    })().catch(err => { packedURLs.delete(key); throw err; }));
  }
  return packedURLs.get(key);
}
const imageObserver = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
  for (const e of entries) if (e.isIntersecting) { imageObserver.unobserve(e.target); loadPacked(e.target); }
}, { rootMargin: '300px' }) : null;
function loadPacked(img) {
  const { pack, o, l } = img.dataset;
  packedImage(pack, Number(o), Number(l)).then(url => { img.src = url; }).catch(() => img.classList.add('img-empty'));
}
function hydrateImages(root) {
  for (const img of root.querySelectorAll('img[data-pack]:not([data-seen])')) {
    img.dataset.seen = '1';
    if (imageObserver) imageObserver.observe(img); else loadPacked(img);
  }
}

const blobURLs = new Map();
function blobURL(key, blob) {
  if (!blob) return BLANK;
  if (!blobURLs.has(key)) blobURLs.set(key, URL.createObjectURL(blob));
  return blobURLs.get(key);
}

// ---------- small helpers ----------

function emptyHTML(icon, title, text) {
  return `<div class="empty"><div class="empty__icon">${icon}</div><strong>${escape(title)}</strong>${text}</div>`;
}

function roomLabel(id) {
  const info = state.museum.roomInfo(id);
  if (info?.room.kind === 'space') return info.room.name;
  return `Gallery ${[info?.room.id ?? id, ...(info?.room.aliases ?? [])].join(' / ')}`;
}
function shortRoomLabel(id) {
  const info = state.museum.roomInfo(id);
  return info?.room.kind === 'space' ? info.room.name : `Gallery ${info?.room.id ?? id}`;
}
function floorShort(id) { return id === 'G' ? 'G/LG' : `L${id}`; }

let toastTimer;
function toast(msg) {
  els.toast.textContent = msg;
  els.toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => els.toast.classList.remove('show'), 2200);
}

function formatDay(iso) {
  return new Date(iso).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
}
function formatTime(iso) {
  return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

function pointInPoly([x, y], poly) {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i]; const [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
}

function escape(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
