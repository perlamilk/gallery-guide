import { loadData, shortArtist, FILTERS } from './data.js';
import { MuseumMap } from './map3d.js';
import { FACILITIES, facilitySVG } from './icons.js';
import { Visits, Favorites, duration } from './visits.js';
import { Router, roomName } from './routes.js';

const $ = sel => document.querySelector(sel);
const els = {
  app: $('#app'), canvas: $('#map'), sheet: $('#sheet'), grab: $('#grab'), body: $('#body'),
  form: $('#searchForm'), q: $('#q'), clear: $('#clear'), floors: $('#floors'),
  recenter: $('#recenter'), floorTitle: $('#floorTitle'), floorSub: $('#floorSub'),
  tools: document.querySelector('.map-tools'), toast: $('#toast'),
  visitPill: $('#visitPill'), visitPillText: $('#visitPillText'),
};

const PAGE = 60; // works rendered at a time in long lists
const QUICK_FACILITIES = ['restroom', 'dining', 'elevator', 'entrance', 'info', 'water'];

const state = {
  museum: null,
  map: null,
  floor: null,
  query: '',
  results: [],
  places: [],
  filters: { type: '', country: '', period: '' },
  shown: PAGE,
  visit: null,          // the visit in progress, if any
  diary: [],            // finished visits, newest first
  replaying: null,      // a past visit shown on the map
  router: null,
  here: null,           // the room you're in: last room you checked off, or the one you picked
  hereLabel: null,      // how to call it, when picked as an entrance
  route: null,          // { stops, title, result } of the directions being shown
  avoidStairs: false,
  picking: false,       // waiting for a tap on the room you're in
  favorites: [],        // artwork ids
  tours: [],
  tour: null,           // { id, index } of the tour in progress
  // what the sheet shows: home | results | browse | room {id} | art {id, from} | facility {type}
  view: { type: 'home' },
};

boot().catch(err => {
  console.error(err);
  els.body.innerHTML = `<div class="empty"><strong>Couldn’t load the guide</strong>${escape(err.message)}</div>`;
});

async function boot() {
  await document.fonts.load('120px "Instrument Serif"').catch(() => {});
  state.museum = await loadData();

  state.map = new MuseumMap(els.canvas, state.museum, { onTap: onMapTap });
  buildFloorSwitcher();
  setFloor(state.museum.defaultFloor, { animate: false });
  setSheet('peek');
  state.map.resetView({ animate: false });

  wireSearch();
  wireSheetDrag();
  els.recenter.addEventListener('click', () => state.map.resetView());
  state.router = new Router(state.museum);
  state.favorites = await Favorites.list().catch(() => []);
  state.tours = (await fetch('data/tours.json').then(r => r.json()).catch(() => ({}))).tours ?? [];
  state.visit = await Visits.active().catch(() => null);
  state.here = state.visit?.rooms.at(-1)?.id ?? null;
  state.diary = await Visits.list().catch(() => []);
  showVisitedOnMap();
  updateVisitPill();
  els.visitPill.addEventListener('click', () => { state.view = { type: 'visit' }; setSheet('half'); render(); });
  setInterval(updateVisitPill, 30000);

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

// ---------- search & filters ----------

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
  state.shown = PAGE;
  state.places = state.museum.searchPlaces(state.query);
  state.map.highlightFacilities(new Set(state.places.filter(p => p.kind === 'facility').map(p => p.type)));
  updateWorks();

  // If no work matches on this floor but some do on another, go there.
  const counts = state.museum.galleriesOf(state.results);
  const floorsHit = new Set([...counts.keys()].map(g => state.museum.roomInfo(g)?.floor.id).filter(Boolean));
  if (state.query && floorsHit.size && !floorsHit.has(state.floor)) {
    const target = [...floorsHit][0];
    setFloor(target);
    toast(`Matches on ${state.museum.floor(target).label}`);
    state.map.frameRooms([...counts.keys()]);
  }

  state.view = state.query ? { type: 'results' } : (state.view.type === 'browse' ? state.view : { type: 'home' });
  render();
}

// Works matching the search text and the filters; lights up their galleries.
function updateWorks() {
  const here = r => (r.floor === state.floor ? 0 : 1);
  const filtering = Object.values(state.filters).some(Boolean);
  const browsing = state.view.type === 'browse' && !state.query;
  state.results = state.query || filtering
    ? state.museum.search(state.query, state.filters).sort((a, b) => here(a) - here(b))
    : browsing ? [...state.museum.artworks].sort((a, b) => here(a) - here(b)) : [];
  // with nothing typed and no filter, browsing everything shouldn't light up the whole museum
  const counts = state.query || filtering ? state.museum.galleriesOf(state.results) : new Map();
  state.map.highlight(counts);
  markFloorsWithMatches(counts);
  state.map.select(null);
}

function setQuery(text) {
  els.q.value = text;
  els.clear.hidden = !text;
  runSearch(text);
  if (sheetState() === 'peek') setSheet('half');
}

function setFilter(key, value) {
  state.filters[key] = value;
  state.shown = PAGE;
  updateWorks();
  render();
  const ids = [...state.museum.galleriesOf(state.results).keys()];
  const floorsHit = new Set(ids.map(g => state.museum.roomInfo(g)?.floor.id).filter(Boolean));
  if (floorsHit.size && !floorsHit.has(state.floor)) setFloor([...floorsHit][0]);
}

function clearFilters() {
  state.filters = { type: '', country: '', period: '' };
  state.shown = PAGE;
  updateWorks();
  render();
}

// ---------- map taps ----------

function onMapTap(hit) {
  if (state.picking && (hit.kind === 'gallery' || hit.kind === 'space')) {
    state.picking = false;
    setHere(hit.id);
    return;
  }
  if (hit.long) {
    toggleVisited(hit.id, hit.floorId);
    return;
  }
  if (hit.kind === 'facility') {
    const f = FACILITIES[hit.type];
    toast(`${f?.label ?? hit.type} · ${state.museum.floor(hit.floorId).label}`);
    return;
  }
  if (!hit.kind) {
    if (state.view.type === 'room') closeRoom();
    return;
  }
  openRoom(hit.id);
}

function openRoom(id, { fly = false } = {}) {
  state.view = { type: 'room', id, from: state.view.type === 'room' ? state.view.from : state.view };
  state.map.select(id);
  if (fly) state.map.focusRoom(id);
  if (sheetState() === 'peek') setSheet('half');
  render();
}

function closeRoom() {
  state.map.select(null);
  const from = state.view.from;
  state.view = from && from.type !== 'room' && from.type !== 'art' ? from : (state.query ? { type: 'results' } : { type: 'home' });
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

function openBrowse() {
  state.view = { type: 'browse' };
  state.shown = PAGE;
  updateWorks();
  setSheet('full');
  render();
}

// Show where a facility is: this floor if it has one, otherwise the nearest floor that does.
function openFacility(type) {
  const all = state.museum.facilitiesOfType(type);
  if (!all.length) return;
  const floors = [...new Set(all.map(f => f.floor.id))];
  const target = floors.includes(state.floor) ? state.floor : floors[0];
  setFloor(target);
  state.map.highlightFacilities(new Set([type]));
  const here = all.filter(f => f.floor.id === target);
  state.map.frameRooms([], here.map(f => state.map.toWorld(f.at, f.floor)));
  setSheet('half');
  toast(`${FACILITIES[type].label} · ${state.museum.floor(target).label}: ${here.length}`);
}

// ---------- rendering ----------

function render() {
  const v = state.view;
  const html = v.type === 'directions' ? directionsView()
    : v.type === 'favorites' ? favoritesView()
    : v.type === 'tours' ? toursView()
    : v.type === 'tour' ? tourView(v.id)
    : v.type === 'tour-stop' ? tourStopView()
    : v.type === 'visit' ? visitView()
    : v.type === 'diary' ? diaryView()
    : v.type === 'entry' ? entryView(v.id)
    : v.type === 'room' ? roomView(v.id)
    : v.type === 'art' ? artView(v.id)
    : v.type === 'browse' ? browseView()
    : v.type === 'results' ? resultsView()
    : homeView();
  els.body.innerHTML = `<div class="view">${html}</div>`;
  els.body.scrollTop = 0;
  hydrateImages(els.body);
}

function homeView() {
  const chips = state.museum.topArtists(6)
    .map(name => `<button class="chip" type="button" data-query="${escape(name)}">${escape(name)}</button>`).join('');
  const quick = QUICK_FACILITIES.filter(t => state.museum.facilitiesOfType(t).length)
    .map(t => `<button class="chip chip--icon" type="button" data-facility="${t}">${facilitySVG(t, { size: 18 })}${escape(FACILITIES[t].label)}</button>`).join('');
  const n = state.museum.artworks.length;
  return `
    <div class="chips">${chips}</div>
    <button class="menu-row" type="button" data-action="browse">
      <span class="menu-row__icon" aria-hidden="true">
        <svg viewBox="0 0 24 24"><path d="M4 5h16M4 12h16M4 19h10"/></svg>
      </span>
      <span class="menu-row__text">
        <span class="menu-row__title">All works</span>
        <span class="menu-row__meta">${n} on view · filter by type, country and period</span>
      </span>
      <svg class="menu-row__chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 6 6 6-6 6"/></svg>
    </button>
    ${tourFavRowsHTML()}
    ${visitRowHTML()}
    <p class="eyebrow">Around the museum</p>
    <div class="chips">${quick}</div>
    <p class="hint">Tap a gallery on the map to see what’s inside — or search for an artist like <em>Van Gogh</em>, or for <em>restroom</em> or <em>café</em>.</p>
    <p class="offline" id="offline">Checking offline copy…</p>`;
}

function placesHTML() {
  if (!state.places.length) return '';
  const rows = state.places.map(p => {
    if (p.kind === 'facility') {
      const floors = [...p.byFloor.entries()]
        .sort((a, b) => (state.museum.floor(a[0]).order ?? 0) - (state.museum.floor(b[0]).order ?? 0))
        .map(([id, n]) => `${floorShort(id)}${n > 1 ? ` (${n})` : ''}`).join(' · ');
      return `<li><button class="row row--place" type="button" data-facility="${p.type}">
        <span class="place-icon">${facilitySVG(p.type, { size: 24 })}</span>
        <span><p class="row__title">${escape(p.label)}</p><p class="row__meta">${escape(floors)}</p></span>
        <svg class="menu-row__chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 6 6 6-6 6"/></svg>
      </button></li>`;
    }
    return `<li><button class="row row--place" type="button" data-room="${escape(p.room.id)}">
      <span class="place-icon"><svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><path d="M4 20V9l8-5 8 5v11zM9 20v-6h6v6"/></svg></span>
      <span><p class="row__title">${escape(p.room.name)}</p><p class="row__meta">${escape(p.floor.label)}</p></span>
      <svg class="menu-row__chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 6 6 6-6 6"/></svg>
    </button></li>`;
  }).join('');
  return `<p class="eyebrow">Places</p><ul class="list list--places">${rows}</ul>`;
}

function resultsView() {
  const res = state.results;
  const places = placesHTML();
  const filtersNote = activeFiltersHTML();
  if (!res.length) {
    if (places) return places + filtersNote;
    return `${filtersNote}<div class="empty"><strong>No works found</strong>Nothing on view matches “${escape(state.query)}”. Try an artist’s surname, a gallery number, or a place like “restroom”.</div>`;
  }
  const rooms = state.museum.galleriesOf(res).size;
  return `
    ${places}
    ${places ? '<p class="eyebrow">Works</p>' : ''}
    <div class="summary">
      <p class="summary__count">${res.length} ${res.length === 1 ? 'work' : 'works'} <i>in ${rooms} ${rooms === 1 ? 'gallery' : 'galleries'}</i></p>
    </div>
    ${filtersNote}
    ${listHTML(res)}`;
}

function browseView() {
  const res = state.results;
  const selects = FILTERS.map(f => {
    const options = state.museum.filterOptions(f.key, state.filters);
    const value = state.filters[f.key];
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
    <div class="head">
      <div>
        <h2 class="head__title">All works</h2>
        <p class="head__meta">${res.length} ${res.length === 1 ? 'work' : 'works'} in ${rooms} ${rooms === 1 ? 'gallery' : 'galleries'}${state.query ? ` · matching “${escape(state.query)}”` : ''}</p>
      </div>
      <button class="icon-btn" type="button" data-action="home" aria-label="Close all works">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17"/></svg>
      </button>
    </div>
    <div class="filters">${selects}</div>
    ${filtering ? '<button class="link-btn" type="button" data-action="clear-filters">Clear filters</button>' : ''}
    ${res.length ? listHTML(res) : '<div class="empty"><strong>No works</strong>Nothing on view matches these filters.</div>'}`;
}

function activeFiltersHTML() {
  const active = FILTERS.filter(f => state.filters[f.key]).map(f => state.filters[f.key]);
  if (!active.length) return '';
  return `<p class="filter-note">Filtered: ${escape(active.join(' · '))} <button class="link-btn" type="button" data-action="clear-filters">Clear</button></p>`;
}

function listHTML(works) {
  const shown = works.slice(0, state.shown);
  const more = works.length - shown.length;
  return `<ul class="list">${shown.map(rowHTML).join('')}</ul>
    ${more > 0 ? `<button class="more-btn" type="button" data-action="more">Show ${Math.min(more, PAGE)} more <span>of ${more}</span></button>` : ''}`;
}

function rowHTML(a) {
  const mapped = state.museum.isMapped(a.gallery);
  return `
    <li><button class="row" type="button" data-art="${a.id}">
      ${imgHTML(a, 'thumb')}
      <span>
        <p class="row__title">${escape(a.title)}</p>
        <p class="row__meta">${escape([shortArtist(a.artist), a.date].filter(Boolean).join(' · '))}</p>
      </span>
      ${a.gallery
        ? `<span class="badge ${mapped ? '' : 'badge--off'}"><small>Gal.</small>${escape(a.gallery)}</span>`
        : '<span class="badge badge--off"><small>Off</small>map</span>'}
    </button></li>`;
}

function roomView(id) {
  const info = state.museum.roomInfo(id);
  if (info?.room.kind === 'space') return spaceView(info);
  const hits = new Set(state.results.map(a => a.id));
  const works = [...state.museum.worksIn(id)].sort((a, b) => hits.has(b.id) - hits.has(a.id));
  const name = state.museum.galleryName(id);
  const ids = info ? [info.room.id, ...(info.room.aliases ?? [])] : [id];
  const title = ids.length > 3 ? `Galleries ${ids[0]}–${ids.at(-1)}` : `Galler${ids.length > 1 ? 'ies' : 'y'} ${ids.join(' / ')}`;
  const cards = works.length
    ? `<div class="grid">${works.slice(0, state.shown).map(a => `
        <button class="card" type="button" data-art="${a.id}">
          ${hits.has(a.id) ? '<span class="card__match">Match</span>' : ''}
          ${imgHTML(a, 'card__img')}
          <p class="card__title">${escape(a.title)}</p>
          <p class="card__meta">${escape([shortArtist(a.artist), a.date].filter(Boolean).join(' · '))}</p>
        </button>`).join('')}</div>
      ${works.length > state.shown ? `<button class="more-btn" type="button" data-action="more">Show more <span>of ${works.length - state.shown}</span></button>` : ''}`
    : `<div class="empty"><strong>No works listed yet</strong>The guide has no works on view in this gallery yet.</div>`;
  return `
    <div class="head">
      <div>
        <h2 class="head__title">${escape(title)}</h2>
        ${name ? `<p class="head__name">${escape(name)}</p>` : ''}
        <p class="head__meta">${escape(info?.floor.label ?? '')} · ${works.length} ${works.length === 1 ? 'work' : 'works'}</p>
      </div>
      <button class="icon-btn" type="button" data-action="close-room" aria-label="Close gallery">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17"/></svg>
      </button>
    </div>
    ${info ? `<div class="room-actions">${directionsButtonHTML(info.room.id)}${visitedToggleHTML(info.room.id)}</div>` : ''}
    ${connectionsHTML(info?.room.id ?? id)}
    ${cards}`;
}

// "Doors to" / "Through the corridor": every room you can walk to from here.
function connectionsHTML(id) {
  const { direct, viaCorridor } = state.museum.connections(id);
  if (!direct.length && !viaCorridor.length) return '';
  const chip = rid => {
    const info = state.museum.roomInfo(rid);
    const label = info?.room.kind === 'space' ? info.room.name : `Gallery ${[rid, ...(info?.room.aliases ?? [])].join(' / ')}`;
    return `<button class="chip chip--small" type="button" data-room="${escape(rid)}">${escape(label)}</button>`;
  };
  return `<div class="exits">
    ${direct.length ? `<p class="eyebrow">Doorways to</p><div class="chips">${direct.map(chip).join('')}</div>` : ''}
    ${viaCorridor.length ? `<p class="eyebrow">Through the corridor</p><div class="chips">${viaCorridor.map(chip).join('')}</div>` : ''}
  </div>`;
}

// A courtyard, café, shop or auditorium: its name, floor and the facilities inside it.
function spaceView(info) {
  const { room, floor } = info;
  const inside = (floor.amenities ?? []).filter(a => pointInPoly(a.at, room.poly));
  const types = [...new Set(inside.map(a => a.type))];
  return `
    <div class="head">
      <div>
        <h2 class="head__title head__title--small">${escape(room.name)}</h2>
        <p class="head__meta">${escape(floor.label)}</p>
      </div>
      <button class="icon-btn" type="button" data-action="close-room" aria-label="Close">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17"/></svg>
      </button>
    </div>
    <div class="room-actions">${directionsButtonHTML(room.id)}${visitedToggleHTML(room.id)}</div>
    ${connectionsHTML(room.id)}
    ${types.length ? `<p class="eyebrow">Here</p><div class="chips">${types.map(t =>
      `<button class="chip chip--icon" type="button" data-facility="${t}">${facilitySVG(t, { size: 18 })}${escape(FACILITIES[t]?.label ?? t)}</button>`).join('')}</div>` : ''}`;
}

function artView(id) {
  const a = state.museum.artworks.find(x => x.id === id);
  const info = state.museum.roomInfo(a.gallery);
  const from = state.view.from;
  const backLabel = from?.type === 'room' ? `Gallery ${from.id}` : from?.type === 'browse' ? 'All works'
    : from?.type === 'favorites' ? 'Favorites' : from?.type === 'tour' || from?.type === 'tour-stop' ? 'Tour'
    : state.query ? 'Results' : 'Back';
  const facts = [
    ['Date', a.date], ['Medium', a.medium], ['Type', a.type], ['Country', a.country],
  ].filter(([, v]) => v).map(([k, v]) => `<div><dt>${k}</dt><dd>${escape(v)}</dd></div>`).join('');
  return `
    <button class="back" type="button" data-action="back">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14.5 6-6 6 6 6"/></svg>${escape(backLabel)}
    </button>
    ${a.image || a.img ? `<div class="art__frame">${imgHTML(a, 'art__img', a.title)}</div>` : ''}
    <div class="art__head">
      <h2 class="art__title">${escape(a.title)}</h2>
      ${favButtonHTML(a.id)}
    </div>
    ${a.artist ? `<p class="art__artist">${escape(a.artist)}</p>` : ''}
    ${a.artistDetails ? `<p class="art__life">${escape(a.artistDetails)}</p>` : ''}
    <dl class="facts">
      ${facts}
      <div><dt>Gallery</dt><dd>${info
        ? `<button class="gallery-link" type="button" data-room="${a.gallery}">Gallery ${escape(a.gallery)}</button> · ${escape(info.floor.label)}${a.galleryName ? `<br><span style="color:var(--ink-2)">${escape(a.galleryName)}</span>` : ''}`
        : a.gallery ? `Gallery ${escape(a.gallery)} <span style="color:var(--ink-3)">(not on the map)</span>`
        : escape(a.location || a.galleryName || 'On view')}</dd></div>
      ${a.accession ? `<div><dt>Accession</dt><dd>${escape(a.accession)}</dd></div>` : ''}
    </dl>
    ${info ? `<div class="room-actions">${directionsButtonHTML(info.room.id, `Directions to Gallery ${a.gallery}`)}</div>` : ''}
    <a class="cta" href="${a.url}" target="_blank" rel="noopener">
      View on the MFA collection site
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 16 16 8M9 8h7v7"/></svg>
    </a>
    ${a.imageSource ? `<p class="credit">Image: <a href="${a.imageSource}" target="_blank" rel="noopener">${escape(a.imageCredit ?? 'source')}</a></p>`
      : a.img ? '<p class="credit">Image: Museum of Fine Arts, Boston</p>' : ''}`;
}

// One delegated handler for everything inside the sheet.
els.body.addEventListener('click', e => {
  const t = e.target.closest('[data-query],[data-art],[data-room],[data-facility],[data-action]');
  if (!t) return;
  const action = t.dataset.action;
  if (t.dataset.query) {
    setQuery(t.dataset.query);
    state.map.frameRooms([...state.museum.galleriesOf(state.results).keys()]);
  }
  else if (t.dataset.art) openArt(t.dataset.art);
  else if (t.dataset.room) { setSheet('half'); openRoom(t.dataset.room, { fly: true }); }
  else if (t.dataset.facility) openFacility(t.dataset.facility);
  else if (action === 'close-room') closeRoom();
  else if (action === 'toggle-visited') toggleVisited(t.dataset.id, t.dataset.floor);
  else if (action === 'start-visit') startVisit();
  else if (action === 'open-visit') { state.view = { type: 'visit' }; render(); }
  else if (action === 'finish-visit') finishVisit();
  else if (action === 'discard-visit') discardVisit(t);
  else if (action === 'diary') { state.view = { type: 'diary' }; setSheet('full'); render(); }
  else if (action === 'entry') { state.view = { type: 'entry', id: t.dataset.id }; setSheet('full'); render(); }
  else if (action === 'replay') replayVisit(t.dataset.id);
  else if (action === 'delete-entry') deleteEntry(t);
  else if (action === 'browse') openBrowse();
  else if (action === 'directions') directionsTo([t.dataset.id], { title: t.dataset.title });
  else if (action === 'pick-here') { state.picking = true; setSheet('peek'); toast('Tap the room you’re in'); }
  else if (action === 'set-here') setHere(t.dataset.id, t.dataset.label);
  else if (action === 'avoid-stairs') { state.avoidStairs = !state.avoidStairs; computeRoute(); render(); }
  else if (action === 'clear-route') clearRoute();
  else if (action === 'show-floor') showRouteFloor(t.dataset.floor);
  else if (action === 'favorite') toggleFavorite(t.dataset.id, t);
  else if (action === 'favorites') openFavorites();
  else if (action === 'route-favorites') routeFavorites();
  else if (action === 'tours') { state.view = { type: 'tours' }; setSheet('full'); render(); }
  else if (action === 'tour') { state.view = { type: 'tour', id: t.dataset.id }; setSheet('full'); render(); }
  else if (action === 'start-tour') startTour(t.dataset.id);
  else if (action === 'next-stop') nextStop();
  else if (action === 'stop-route') routeToStop();
  else if (action === 'end-tour') endTour();
  else if (action === 'clear-filters') clearFilters();
  else if (action === 'more') {
    const top = els.body.scrollTop;
    state.shown += PAGE;
    render();
    els.body.scrollTop = top;
    hydrateImages(els.body);
  }
  else if (action === 'home') {
    if (state.replaying) { state.replaying = null; showVisitedOnMap(); }
    state.picking = false;
    state.view = state.query ? { type: 'results' } : { type: 'home' };
    updateWorks();
    setSheet('half');
    render();
  }
  else if (action === 'back') {
    const from = state.view.from ?? { type: 'home' };
    state.view = from;
    state.map.select(from.type === 'room' ? from.id : null);
    setSheet(from.type === 'browse' ? 'full' : 'half');
    render();
  }
});

els.body.addEventListener('change', e => {
  const sel = e.target.closest('[data-filter]');
  if (sel) setFilter(sel.dataset.filter, sel.value);
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
  const urls = ['index.html', 'data/artworks.json', 'data/floors.json',
    ...new Set(state.museum.artworks.map(a => a.image || a.img?.p).filter(Boolean))];
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

// ---------- directions ----------

const ARROW = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h12M13 7l5 5-5 5"/></svg>';
const HEART = on => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" ${on ? 'fill="currentColor"' : ''}/></svg>`;

function directionsButtonHTML(id, label = 'Directions') {
  return `<button class="action-btn" type="button" data-action="directions" data-id="${escape(id)}">${ARROW}${escape(label)}</button>`;
}

// Show the way to one or more rooms (in order), from where you are.
function directionsTo(stops, { title } = {}) {
  state.route = { stops, title: title || `To ${roomLabel(stops.at(-1))}`, result: null };
  state.view = { type: 'directions', from: state.view };
  computeRoute();
  setSheet('half');
  render();
}

function computeRoute() {
  const r = state.route;
  if (!r) return;
  state.map.clearRoute();
  r.result = null;
  if (!state.here) return; // the view asks where you are
  const stops = r.stops.filter(id => id !== state.here);
  r.result = stops.length ? state.router.routeThrough([state.here, ...stops], { avoidStairs: state.avoidStairs }) : null;
  if (!r.result) return;
  const segs = state.router.segments(r.result);
  r.segments = segs;
  state.map.showRoute(segs);
  showRouteFloor(segs[0].floorId);
}

function showRouteFloor(floorId) {
  const seg = state.route?.segments?.find(s => s.floorId === floorId);
  setFloor(floorId);
  if (seg) state.map.frameRooms([], seg.points.map(p => state.map.toWorld(p, state.museum.floor(floorId))));
}

function setHere(id, label = null) {
  state.here = state.museum.roomInfo(id)?.room.id ?? id;
  state.hereLabel = label;
  toast(`You’re at ${hereName()}`);
  if (state.tour) { routeToStop(); return; }
  if (state.route) { computeRoute(); state.view = { type: 'directions', from: state.view.from ?? { type: 'home' } }; setSheet('half'); }
  render();
}

function clearRoute() {
  state.map.clearRoute();
  state.route = null;
  state.picking = false;
  state.view = state.tour ? { type: 'tour-stop' } : { type: 'home' };
  render();
}

// Rooms with an entrance icon: handy starting points.
function entranceRooms() {
  const out = [];
  for (const floor of state.museum.floors) {
    for (const f of floor.amenities ?? []) {
      if (f.type !== 'entrance') continue;
      // entrance icons often sit just outside the building outline: use the nearest public room
      const room = floor.rooms.find(r => r.kind !== 'corridor' && pointInPoly(f.at, r.poly))
        ?? floor.rooms.find(r => pointInPoly(f.at, r.poly))
        ?? nearestRoomTo(floor, f.at);
      const note = (floor.labels ?? []).filter(l => /entrance/i.test(l.text))
        .sort((a, b) => Math.hypot(a.at[0] - f.at[0], a.at[1] - f.at[1]) - Math.hypot(b.at[0] - f.at[0], b.at[1] - f.at[1]))[0];
      if (room) out.push({ id: room.id, label: note ? note.text.replace(/\s*\(.*\)\s*/, '') : `Entrance · ${floor.label}` });
    }
  }
  return out.filter((e, i) => out.findIndex(x => x.id === e.id) === i);
}

function hereName() {
  return state.hereLabel || roomLabel(state.here);
}

function nearestRoomTo(floor, at) {
  let best = null, bd = Infinity;
  for (const r of floor.rooms) {
    for (const [x, y] of r.poly) {
      const d = Math.hypot(x - at[0], y - at[1]);
      if (d < bd) { bd = d; best = r; }
    }
  }
  return bd < 60 ? best : null;
}

function directionsView() {
  const r = state.route;
  if (!r) return homeView();
  const head = `
    <div class="head">
      <div>
        <h2 class="head__title head__title--small">${escape(r.title)}</h2>
        ${state.here ? `<p class="head__meta">From ${escape(hereName())} · <button class="link-btn link-btn--inline" type="button" data-action="pick-here">change</button></p>` : ''}
      </div>
      <button class="icon-btn" type="button" data-action="clear-route" aria-label="Close directions">${CLOSE}</button>
    </div>`;
  if (!state.here) {
    const recent = [...new Set((state.visit?.rooms ?? []).map(x => x.id).reverse())].slice(0, 4);
    return `${head}
      <p class="hint">Where are you now? Tap the room you’re in on the map, or choose:</p>
      <div class="chips">
        ${recent.map(id => `<button class="chip" type="button" data-action="set-here" data-id="${escape(id)}">${escape(roomLabel(id))}</button>`).join('')}
        ${entranceRooms().map(e => `<button class="chip" type="button" data-action="set-here" data-id="${escape(e.id)}" data-label="${escape(e.label)}">${escape(e.label)}</button>`).join('')}
      </div>
      <button class="action-btn action-btn--wide" type="button" data-action="pick-here">Tap my room on the map</button>`;
  }
  const res = r.result;
  const stairsToggle = `<button class="switch" type="button" role="switch" aria-checked="${state.avoidStairs}" data-action="avoid-stairs">
      <span class="switch__track"><span class="switch__knob"></span></span>Avoid stairs</button>`;
  if (!res) {
    const same = r.stops.length === 1 && r.stops[0] === state.here;
    return `${head}<div class="empty"><strong>${same ? 'You’re already here' : 'No way found'}</strong>${same ? '' : 'The map has no connection between these rooms. Try another starting room.'}</div>${stairsToggle}`;
  }
  const steps = state.router.steps(res);
  const floors = [...new Set(state.route.segments.map(s => s.floorId))];
  return `${head}
    <p class="route-summary"><strong>${state.router.minutes(res)} min</strong> · about ${state.router.meters(res)} m${floors.length > 1 ? ` · ${floors.length} floors` : ''}</p>
    ${stairsToggle}
    <ol class="steps">
      <li class="steps__start">Start at ${escape(hereName())}</li>
      ${steps.map(st => st.kind === 'stairs' || st.kind === 'elevator'
        ? `<li class="steps__floor"><button class="link-btn" type="button" data-action="show-floor" data-floor="${escape(floorFromStep(st))}">${escape(st.text)}</button></li>`
        : r.stops.includes(st.id)
          ? `<li class="steps__stop">${escape(st.text)} <span>${r.stops.length > 1 ? `stop ${r.stops.indexOf(st.id) + 1}` : 'arrive'}</span></li>`
          : `<li>${escape(st.text)}</li>`).join('')}
    </ol>
    ${floors.length > 1 ? `<div class="chips">${floors.map(f => `<button class="chip chip--small" type="button" data-action="show-floor" data-floor="${escape(f)}">Show ${escape(state.museum.floor(f).label)}</button>`).join('')}</div>` : ''}`;
}

function floorFromStep(step) {
  const m = step.text.match(/to (Level .+)$/);
  return state.museum.floors.find(f => f.label === m?.[1])?.id ?? '';
}

// ---------- favorites ----------

function favButtonHTML(id) {
  const on = state.favorites.includes(id);
  return `<button class="fav-btn ${on ? 'fav-btn--on' : ''}" type="button" data-action="favorite" data-id="${escape(id)}"
    aria-pressed="${on}" aria-label="${on ? 'Remove from favorites' : 'Add to favorites'}">${HEART(on)}</button>`;
}

async function toggleFavorite(id, button) {
  const on = await Favorites.toggle(id);
  state.favorites = await Favorites.list();
  if (button) {
    button.outerHTML = favButtonHTML(id);
  }
  toast(on ? 'Added to favorites' : 'Removed from favorites');
  if (state.view.type === 'favorites') { highlightFavorites(); render(); }
}

function favoriteWorks() {
  return state.favorites.map(id => state.museum.artworks.find(a => a.id === id)).filter(Boolean);
}

function highlightFavorites() {
  const counts = state.museum.galleriesOf(favoriteWorks());
  state.map.highlight(counts);
  markFloorsWithMatches(counts);
}

function openFavorites() {
  state.view = { type: 'favorites' };
  state.shown = PAGE;
  highlightFavorites();
  setSheet('full');
  render();
}

function favoritesView() {
  const works = favoriteWorks();
  const rooms = [...state.museum.galleriesOf(works).keys()].filter(g => state.museum.isMapped(g));
  return `
    <div class="head">
      <div>
        <h2 class="head__title">Favorites</h2>
        <p class="head__meta">${works.length} ${works.length === 1 ? 'work' : 'works'} in ${rooms.length} ${rooms.length === 1 ? 'gallery' : 'galleries'}</p>
      </div>
      <button class="icon-btn" type="button" data-action="home" aria-label="Close favorites">${CLOSE}</button>
    </div>
    ${rooms.length ? `<button class="cta cta--accent" type="button" data-action="route-favorites">${ARROW}Walk to all my favorites</button>` : ''}
    ${works.length ? listHTML(works) : '<div class="empty"><strong>No favorites yet</strong>Tap the heart on any work to keep it here.</div>'}`;
}

function routeFavorites() {
  const rooms = [...state.museum.galleriesOf(favoriteWorks()).keys()].filter(g => state.museum.isMapped(g));
  if (!rooms.length) return;
  const order = state.router.orderStops(state.here ?? rooms[0], rooms, { avoidStairs: state.avoidStairs });
  directionsTo(order, { title: `My favorites · ${order.length} ${order.length === 1 ? 'gallery' : 'galleries'}` });
}

// ---------- tours ----------

function tourFavRowsHTML() {
  const rows = [];
  if (state.tours.length) {
    rows.push(state.tour ? `<button class="menu-row menu-row--live" type="button" data-action="tour" data-id="${state.tour.id}">
        <span class="menu-row__icon" aria-hidden="true">${ARROW}</span>
        <span class="menu-row__text"><span class="menu-row__title">${escape(currentTour()?.title ?? 'Tour')}</span>
        <span class="menu-row__meta">Stop ${state.tour.index + 1} of ${currentTour()?.stops.length} · tap to continue</span></span>
        <svg class="menu-row__chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 6 6 6-6 6"/></svg></button>`
      : `<button class="menu-row" type="button" data-action="tours">
        <span class="menu-row__icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 18c3-6 5-9 8-9s5 3 8-3"/><circle cx="4" cy="18" r="1.6"/><circle cx="20" cy="6" r="1.6"/></svg></span>
        <span class="menu-row__text"><span class="menu-row__title">Tours</span>
        <span class="menu-row__meta">${state.tours.length} ready-made routes through the galleries</span></span>
        <svg class="menu-row__chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 6 6 6-6 6"/></svg></button>`);
  }
  rows.push(`<button class="menu-row" type="button" data-action="favorites">
      <span class="menu-row__icon" aria-hidden="true">${HEART(false)}</span>
      <span class="menu-row__text"><span class="menu-row__title">Favorites</span>
      <span class="menu-row__meta">${state.favorites.length ? `${state.favorites.length} ${state.favorites.length === 1 ? 'work' : 'works'} · walk to all of them` : 'Tap the heart on a work to keep it here'}</span></span>
      <svg class="menu-row__chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 6 6 6-6 6"/></svg></button>`);
  return rows.join('');
}

function currentTour() { return state.tours.find(t => t.id === state.tour?.id) ?? null; }

function tourWorks(stop) {
  return (stop.works ?? []).map(id => state.museum.artworks.find(a => a.id === id)).filter(Boolean);
}

function toursView() {
  return `
    <div class="head">
      <div><h2 class="head__title">Tours</h2><p class="head__meta">Ready-made routes · edit them in data/tours.json</p></div>
      <button class="icon-btn" type="button" data-action="home" aria-label="Close tours">${CLOSE}</button>
    </div>
    <ul class="tour-list">${state.tours.map(t => {
      const cover = tourWorks(t.stops[0])[0];
      return `<li><button class="tour-card" type="button" data-action="tour" data-id="${t.id}">
        ${cover ? imgHTML(cover, 'tour-card__img') : '<span class="tour-card__img img-empty"></span>'}
        <span class="tour-card__text">
          <span class="tour-card__title">${escape(t.title)}</span>
          <span class="tour-card__meta">${t.minutes} min · ${t.stops.length} stops · ${escape([...new Set(t.stops.map(s => state.museum.roomInfo(s.gallery)?.floor.label).filter(Boolean))].join(', '))}</span>
          <span class="tour-card__sub">${escape(t.subtitle ?? '')}</span>
        </span>
      </button></li>`;
    }).join('')}</ul>`;
}

function tourView(id) {
  const t = state.tours.find(x => x.id === id);
  if (!t) return toursView();
  if (state.tour?.id === id) return tourStopView();
  return `
    <button class="back" type="button" data-action="tours">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14.5 6-6 6 6 6"/></svg>Tours
    </button>
    <h2 class="art__title">${escape(t.title)}</h2>
    <p class="head__meta">${t.minutes} min · ${t.stops.length} stops</p>
    <p class="tour-desc">${escape(t.description ?? '')}</p>
    <ol class="tour-stops">${t.stops.map((s, i) => `
      <li>
        <button class="tour-stop__name" type="button" data-room="${escape(s.gallery)}"><span>${i + 1}</span>${escape(roomLabel(s.gallery))}</button>
        <p class="tour-stop__note">${escape(s.note ?? '')}</p>
        <div class="tour-thumbs">${tourWorks(s).map(a => `<button type="button" data-art="${a.id}" aria-label="${escape(a.title)}">${imgHTML(a, 'thumb')}</button>`).join('')}</div>
      </li>`).join('')}</ol>
    <button class="cta cta--accent" type="button" data-action="start-tour" data-id="${t.id}">${ARROW}Start this tour</button>`;
}

async function startTour(id) {
  const t = state.tours.find(x => x.id === id);
  if (!t) return;
  state.tour = { id, index: 0 };
  if (!state.visit) { state.visit = await Visits.start(); updateVisitPill(); }
  state.view = { type: 'tour-stop' };
  routeToStop();
}

// Directions from where you are to the tour's current stop.
function routeToStop() {
  const t = currentTour();
  if (!t) return;
  const stop = t.stops[state.tour.index];
  state.route = { stops: [stop.gallery], title: `Stop ${state.tour.index + 1}: ${roomLabel(stop.gallery)}` };
  computeRoute();
  if (!state.route.result) {
    // already there, or no starting point yet: just show the stop
    state.map.focusRoom(stop.gallery, { zoom: false });
  }
  state.map.select(stop.gallery);
  state.view = state.here ? { type: 'tour-stop' } : { type: 'directions', from: { type: 'tour-stop' } };
  setSheet('half');
  render();
}

function tourStopView() {
  const t = currentTour();
  if (!t) return homeView();
  const i = state.tour.index;
  const stop = t.stops[i];
  const last = i === t.stops.length - 1;
  const res = state.route?.result;
  return `
    <div class="head">
      <div>
        <p class="eyebrow">${escape(t.title)} · stop ${i + 1} of ${t.stops.length}</p>
        <h2 class="head__title head__title--small">${escape(roomLabel(stop.gallery))}</h2>
        <p class="head__meta">${escape(state.museum.roomInfo(stop.gallery)?.floor.label ?? '')}${res ? ` · ${state.router.minutes(res)} min walk` : state.here === state.museum.roomInfo(stop.gallery)?.room.id ? ' · you’re here' : ''}</p>
      </div>
      <button class="icon-btn" type="button" data-action="end-tour" aria-label="End tour">${CLOSE}</button>
    </div>
    <p class="tour-desc">${escape(stop.note ?? '')}</p>
    <div class="grid">${tourWorks(stop).map(a => `
      <button class="card" type="button" data-art="${a.id}">
        ${imgHTML(a, 'card__img')}
        <p class="card__title">${escape(a.title)}</p>
        <p class="card__meta">${escape([shortArtist(a.artist), a.date].filter(Boolean).join(' · '))}</p>
      </button>`).join('')}</div>
    <div class="room-actions">
      ${res ? `<button class="action-btn" type="button" data-action="show-floor" data-floor="${escape(state.route.segments[0].floorId)}">${ARROW}Show the way</button>` : ''}
      <button class="cta cta--accent" type="button" data-action="next-stop">${last ? 'Finish tour' : `I’ve seen it · next stop`}</button>
    </div>`;
}

async function nextStop() {
  const t = currentTour();
  if (!t) return;
  const stop = t.stops[state.tour.index];
  const roomId = state.museum.roomInfo(stop.gallery)?.room.id ?? stop.gallery;
  if (state.visit && !visitedIds().has(roomId)) {
    state.visit = await Visits.toggle(state.visit, roomId, state.museum.roomInfo(stop.gallery)?.floor.id);
    showVisitedOnMap();
    updateVisitPill();
  }
  state.here = roomId;
  state.hereLabel = null;
  if (state.tour.index >= t.stops.length - 1) {
    state.tour = null;
    state.map.clearRoute();
    state.route = null;
    toast('Tour complete');
    state.view = state.visit ? { type: 'visit' } : { type: 'home' };
    render();
    return;
  }
  state.tour.index++;
  routeToStop();
}

function endTour() {
  state.tour = null;
  state.map.clearRoute();
  state.map.select(null);
  state.route = null;
  state.view = { type: 'home' };
  render();
}

// ---------- visit diary ----------

const FLAG = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 21V4M6 4h11l-2.5 4L17 12H6"/></svg>';
const BOOK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h10a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3zM5 17a3 3 0 0 1 3-3h10"/></svg>';
const CLOSE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17"/></svg>';

function visitedIds() { return new Set(state.visit?.rooms.map(r => r.id) ?? []); }

// The map shows the visit in progress, or a past visit while it's being replayed.
function showVisitedOnMap() {
  const source = state.replaying ?? state.visit;
  state.map.setVisited(source ? source.rooms.map(r => r.id) : []);
}

function updateVisitPill() {
  const v = state.visit;
  els.visitPill.hidden = !v;
  if (v) els.visitPillText.textContent = `Visit · ${v.rooms.length} ${v.rooms.length === 1 ? 'room' : 'rooms'} · ${duration(v)}`;
}

async function startVisit() {
  state.visit = await Visits.start();
  state.replaying = null;
  showVisitedOnMap();
  updateVisitPill();
  toast('Visit started — check off rooms as you go');
  render();
}

async function toggleVisited(id, floorId) {
  if (!id) return;
  const info = state.museum.roomInfo(id);
  const roomId = info?.room.id ?? id;
  if (!state.visit) {
    state.visit = await Visits.start();
    toast('Visit started');
  }
  const was = visitedIds().has(roomId);
  state.visit = await Visits.toggle(state.visit, roomId, floorId ?? info?.floor.id);
  if (!was) { state.here = roomId; state.hereLabel = null; } // you're standing in the room you just checked off
  state.replaying = null;
  showVisitedOnMap();
  updateVisitPill();
  toast(`${roomLabel(roomId)} ${was ? 'unmarked' : 'visited ✓'}`);
  if (['room', 'visit', 'home'].includes(state.view.type)) render();
}

async function finishVisit() {
  const v = state.visit;
  if (!v) return;
  if (!v.rooms.length) { await discardVisit(null, true); return; }
  els.body.innerHTML = '<div class="view"><div class="empty"><strong>Saving your visit…</strong>Drawing the map of each floor you walked.</div></div>';
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
  updateVisitPill();
  state.view = { type: 'entry', id: saved.id };
  setSheet('full');
  render();
}

async function discardVisit(button, silent = false) {
  if (!silent && button && !button.dataset.confirm) {
    button.dataset.confirm = '1';
    button.textContent = 'Tap again to discard';
    return;
  }
  await Visits.discard();
  state.visit = null;
  showVisitedOnMap();
  updateVisitPill();
  state.view = { type: 'home' };
  render();
}

async function replayVisit(id) {
  const entry = state.diary.find(e => e.id === id);
  if (!entry) return;
  state.replaying = entry;
  showVisitedOnMap();
  const first = entry.rooms[0];
  if (first) setFloor(first.floor);
  state.map.frameRooms(entry.rooms.filter(r => r.floor === state.floor).map(r => r.id));
  setSheet('peek');
  toast(`Showing your visit of ${formatDay(entry.startedAt)}`);
}

async function deleteEntry(button) {
  if (!button.dataset.confirm) {
    button.dataset.confirm = '1';
    button.textContent = 'Tap again to delete';
    return;
  }
  await Visits.remove(button.dataset.id);
  state.diary = await Visits.list();
  if (state.replaying?.id === button.dataset.id) { state.replaying = null; showVisitedOnMap(); }
  state.view = { type: 'diary' };
  render();
}

function roomLabel(id) {
  const info = state.museum.roomInfo(id);
  if (info?.room.kind === 'space') return info.room.name;
  return `Gallery ${[id, ...(info?.room.aliases ?? [])].join(' / ')}`;
}

function visitRowHTML() {
  const v = state.visit;
  const rows = [];
  if (v) {
    rows.push(`<button class="menu-row menu-row--live" type="button" data-action="open-visit">
      <span class="menu-row__icon" aria-hidden="true">${FLAG}</span>
      <span class="menu-row__text"><span class="menu-row__title">Visit in progress</span>
      <span class="menu-row__meta">${v.rooms.length} ${v.rooms.length === 1 ? 'room' : 'rooms'} · ${duration(v)} · press and hold a room to check it off</span></span>
      <svg class="menu-row__chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 6 6 6-6 6"/></svg>
    </button>`);
  } else {
    rows.push(`<button class="menu-row" type="button" data-action="start-visit">
      <span class="menu-row__icon" aria-hidden="true">${FLAG}</span>
      <span class="menu-row__text"><span class="menu-row__title">Start a visit</span>
      <span class="menu-row__meta">Check off rooms as you walk; save the tour when you leave</span></span>
      <svg class="menu-row__chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 6 6 6-6 6"/></svg>
    </button>`);
  }
  if (state.diary.length) {
    rows.push(`<button class="menu-row" type="button" data-action="diary">
      <span class="menu-row__icon" aria-hidden="true">${BOOK}</span>
      <span class="menu-row__text"><span class="menu-row__title">Visit diary</span>
      <span class="menu-row__meta">${state.diary.length} ${state.diary.length === 1 ? 'visit' : 'visits'} · last ${formatDay(state.diary[0].startedAt)}</span></span>
      <svg class="menu-row__chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 6 6 6-6 6"/></svg>
    </button>`);
  }
  return rows.join('');
}

function visitedToggleHTML(roomId) {
  const on = visitedIds().has(roomId);
  const floor = state.museum.roomInfo(roomId)?.floor.id ?? '';
  return `<button class="visit-toggle ${on ? 'visit-toggle--on' : ''}" type="button" aria-pressed="${on}"
      data-action="toggle-visited" data-id="${escape(roomId)}" data-floor="${escape(floor)}">
    <svg viewBox="0 0 24 24" aria-hidden="true">${on ? '<path d="m5 12.5 4.5 4.5L19 7.5"/>' : '<circle cx="12" cy="12" r="8"/>'}</svg>
    ${on ? 'Visited' : state.visit ? 'Mark as visited' : 'Start a visit and mark this room'}
  </button>`;
}

function visitView() {
  const v = state.visit;
  if (!v) return homeView();
  const rooms = [...v.rooms].reverse();
  return `
    <div class="head">
      <div>
        <h2 class="head__title head__title--small">Visit in progress</h2>
        <p class="head__meta">Started ${formatTime(v.startedAt)} · ${duration(v)} · ${v.rooms.length} ${v.rooms.length === 1 ? 'room' : 'rooms'}</p>
      </div>
      <button class="icon-btn" type="button" data-action="home" aria-label="Close">${CLOSE}</button>
    </div>
    <p class="hint">Tap a room and choose <em>Mark as visited</em> — or press and hold it on the map.</p>
    ${rooms.length ? `<ol class="timeline">${rooms.map(r => `
      <li><button class="timeline__row" type="button" data-room="${escape(r.id)}">
        <span class="timeline__time">${formatTime(r.at)}</span>
        <span class="timeline__name">${escape(roomLabel(r.id))}</span>
        <span class="timeline__floor">${escape(floorShort(r.floor))}</span>
      </button></li>`).join('')}</ol>` : ''}
    <button class="cta" type="button" data-action="finish-visit">Finish visit</button>
    <button class="link-btn link-btn--center" type="button" data-action="discard-visit">Discard this visit</button>`;
}

function diaryView() {
  return `
    <div class="head">
      <div>
        <h2 class="head__title">Visit diary</h2>
        <p class="head__meta">${state.diary.length} ${state.diary.length === 1 ? 'visit' : 'visits'}</p>
      </div>
      <button class="icon-btn" type="button" data-action="home" aria-label="Close diary">${CLOSE}</button>
    </div>
    ${state.diary.length ? `<ul class="list">${state.diary.map(e => {
      const snap = Object.values(e.snapshots ?? {})[0];
      return `<li><button class="row row--entry" type="button" data-action="entry" data-id="${e.id}">
        ${snap ? `<img class="thumb thumb--map" src="${blobURL(e.id, snap)}" alt="">` : '<span class="thumb thumb--empty" aria-hidden="true"></span>'}
        <span><p class="row__title">${escape(formatDay(e.startedAt))}</p>
        <p class="row__meta">${e.rooms.length} ${e.rooms.length === 1 ? 'room' : 'rooms'} · ${duration(e)}</p></span>
        <svg class="menu-row__chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 6 6 6-6 6"/></svg>
      </button></li>`;
    }).join('')}</ul>` : '<div class="empty"><strong>No visits yet</strong>Start a visit from the home screen.</div>'}`;
}

function entryView(id) {
  const e = state.diary.find(x => x.id === id);
  if (!e) return diaryView();
  const floors = Object.keys(e.snapshots ?? {});
  const works = new Set(e.rooms.flatMap(r => state.museum.worksIn(r.id).map(a => a.id))).size;
  return `
    <button class="back" type="button" data-action="diary">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14.5 6-6 6 6 6"/></svg>Visit diary
    </button>
    <h2 class="art__title">${escape(formatDay(e.startedAt))}</h2>
    <p class="head__meta">${formatTime(e.startedAt)}–${formatTime(e.endedAt)} · ${duration(e)} · ${e.rooms.length} ${e.rooms.length === 1 ? 'room' : 'rooms'}${works ? ` · ${works} works on view there` : ''}</p>
    ${floors.map(f => `<figure class="snapshot">
      <img src="${blobURL(`${e.id}:${f}`, e.snapshots[f])}" alt="Map of ${escape(state.museum.floor(f)?.label ?? f)} with the rooms you visited">
      <figcaption>${escape(state.museum.floor(f)?.label ?? f)}</figcaption>
    </figure>`).join('')}
    <p class="eyebrow">Your route</p>
    <ol class="timeline">${e.rooms.map(r => `
      <li><button class="timeline__row" type="button" data-room="${escape(r.id)}">
        <span class="timeline__time">${formatTime(r.at)}</span>
        <span class="timeline__name">${escape(roomLabel(r.id))}</span>
        <span class="timeline__floor">${escape(floorShort(r.floor))}</span>
      </button></li>`).join('')}</ol>
    <button class="cta" type="button" data-action="replay" data-id="${e.id}">Show on the 3D map</button>
    <button class="link-btn link-btn--center" type="button" data-action="delete-entry" data-id="${e.id}">Delete this visit</button>`;
}

const blobURLs = new Map();
function blobURL(key, blob) {
  if (!blob) return BLANK;
  if (!blobURLs.has(key)) blobURLs.set(key, URL.createObjectURL(blob));
  return blobURLs.get(key);
}

function formatDay(iso) {
  return new Date(iso).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
}
function formatTime(iso) {
  return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

// ---------- images ----------
// Sample works have one file per image (`image`). The full collection keeps small images in a few
// large "pack" files (`img: {p, o, l}` = file, byte offset, length), read piece by piece when needed.

const BLANK = 'data:image/gif;base64,R0lGODlhAQABAAAAACw=';

function imgHTML(a, cls, alt = '') {
  if (a.image) return `<img class="${cls}" src="${a.image}" alt="${escape(alt)}" loading="lazy" decoding="async">`;
  if (a.img) return `<img class="${cls}" src="${BLANK}" alt="${escape(alt)}" data-pack="${a.img.p}" data-o="${a.img.o}" data-l="${a.img.l}">`;
  return `<span class="${cls} img-empty" aria-hidden="true"></span>`;
}

const packedURLs = new Map();
async function packedImage(p, o, l) {
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

// Fill in packed images as they scroll into view.
const imageObserver = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
  for (const e of entries) {
    if (!e.isIntersecting) continue;
    imageObserver.unobserve(e.target);
    loadPacked(e.target);
  }
}, { root: null, rootMargin: '300px' }) : null;

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

// ---------- utils ----------

let toastTimer;
function toast(msg) {
  els.toast.textContent = msg;
  els.toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => els.toast.classList.remove('show'), 2200);
}

// "Level 1" -> "L1", "Level G/LG" -> "G/LG"
function floorShort(id) {
  return id === 'G' ? 'G/LG' : `L${id}`;
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
