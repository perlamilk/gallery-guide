// The app around the museum guides: Home, Museums, Collection, Discover.
// Open data (Wikidata, Wikimedia Commons, Wikipedia) for museums across the US; the MFA's own
// data and 3D map guide live in guide.html. Everything you save stays on this device.

import { imgHTML, hydrateImages, blobURL, commons } from './images.js';
import { Visits, Favorites, MuseumFavorites, Lists, duration } from './visits.js';

const $ = sel => document.querySelector(sel);
const page = $('#page');
const MFA = 'Q49133';
const PAGE_SIZE = 30;

const D = {};          // data
const S = {            // state
  tab: 'home',
  here: null,          // [lat, lon] once you share your location
  museumsView: 'list', museumsFilter: 'all', query: '', area: null, shown: PAGE_SIZE,
  collTab: 'library', libView: 'list', libSort: 'new', libMuseum: '', selecting: false, selected: new Set(),
};
let maps = [];          // Leaflet maps on the current page
let navDepth = 0;       // pages opened in this session, so Back knows where to go

// ---------- icons ----------
const icon = d => `<svg viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;
const I = {
  back: icon('<path d="m15 5-7 7 7 7"/>'),
  chev: icon('<path d="m9 5 7 7-7 7"/>'),
  arrow: icon('<path d="M5 12h14M13 6l6 6-6 6"/>'),
  heart: on => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"${on ? ' fill="currentColor"' : ''}/></svg>`,
  search: icon('<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>'),
  list: icon('<path d="M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01"/>'),
  map: icon('<path d="M9 4 3 6.5v13.5l6-2.5 6 2.5 6-2.5V4l-6 2.5z"/><path d="M9 4v13.5M15 6.5V20"/>'),
  grid: icon('<path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z"/>'),
  filter: icon('<path d="M4 6h16M7 12h10M10 18h4"/>'),
  sort: icon('<path d="M12 4v16M6 14l6 6 6-6"/>'),
  check: icon('<path d="m5 12 4.5 4.5L19 7"/>'),
  checkCircle: icon('<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>'),
  pin: icon('<path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>'),
  ext: icon('<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>'),
  nav: icon('<path d="M20 4 4 11l7 2 2 7z"/>'),
  globe: icon('<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.7 5.6 3.7 9s-1.2 6.4-3.7 9c-2.5-2.6-3.7-5.6-3.7-9S9.5 5.6 12 3z"/>'),
  plus: icon('<path d="M12 5v14M5 12h14"/>'),
  locate: icon('<path d="M20 4 4 11l7 2 2 7z"/>'),
  museum: icon('<path d="M3 9 12 4l9 5zM5 9v9M9.5 9v9M14.5 9v9M19 9v9M3 20h18"/>'),
  sparkle: icon('<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>'),
};

// ---------- start ----------
boot();

async function boot() {
  const json = url => fetch(url).then(r => (r.ok ? r.json() : null)).catch(() => null);
  const [museums, discover, mfa, curio] = await Promise.all([
    json('data/museums.json'), json('data/discover.json'), json('data/artworks.json'), json('data/curiosities.json'),
  ]);
  D.museums = museums?.museums ?? [];
  D.byMuseum = new Map(D.museums.map(m => [m.id, m]));
  D.discover = discover ?? { works: {}, artists: {}, themes: [], popularArtworks: [], popularArtists: [], popularMuseums: [] };
  D.mfa = (mfa?.artworks ?? []).filter(a => a.onView !== false);
  D.mfaById = new Map(D.mfa.map(a => [a.id, a]));
  D.curio = curio ?? { works: {} };
  await refreshMine();

  wireTabs();
  page.addEventListener('click', onClick);
  page.addEventListener('input', onInput);
  page.addEventListener('change', onChange);
  window.addEventListener('hashchange', () => { navDepth++; route(); });
  route();
  locate(false).then(here => { if (here) { S.here = here; if (['home', 'museums'].includes(routeName())) route({ keepScroll: true }); } });
  registerServiceWorker();
}

async function refreshMine() {
  [S.favs, S.museumFavs, S.lists, S.visits, S.active] = await Promise.all([
    Favorites.entries().catch(() => []), MuseumFavorites.list().catch(() => []), Lists.all().catch(() => []),
    Visits.list().catch(() => []), Visits.active().catch(() => null),
  ]);
}

// ---------- routing ----------
const routeParts = () => decodeURIComponent(location.hash.slice(1)).split('/');
const routeName = () => routeParts()[0] || 'home';
const TAB_OF = { home: 'home', museums: 'museums', museum: 'museums', collection: 'collection', list: 'collection',
  discover: 'discover', artist: 'discover', theme: 'discover', work: 'discover', popular: 'discover' };

const PAGES = {
  home: homePage, museums: museumsPage, museum: museumPage, collection: collectionPage, list: listPage,
  discover: discoverPage, artist: artistPage, theme: themePage, work: workPage, popular: popularPage,
};

function route({ keepScroll = false } = {}) {
  const [name, arg] = routeParts();
  const key = PAGES[name] ? name : 'home';
  const tab = TAB_OF[key];
  if (['home', 'museums', 'collection', 'discover'].includes(key)) S.tab = tab;
  for (const b of document.querySelectorAll('#tabbar [data-tab]')) b.setAttribute('aria-selected', String(b.dataset.tab === (TAB_OF[key] ?? S.tab)));
  const top = page.scrollTop;
  maps.forEach(m => m.remove());
  maps = [];
  page.className = 'page';
  page.innerHTML = PAGES[key](arg);
  if (!keepScroll) page.scrollTop = 0; else page.scrollTop = top;
  hydrateImages(page);
  afterRender[key]?.(arg);
}
const afterRender = {};

function go(hash) { location.hash = hash; }
function back(fallback) {
  if (navDepth > 0) { navDepth -= 2; history.back(); }
  else go(fallback);
}

function wireTabs() {
  for (const b of document.querySelectorAll('#tabbar [data-tab]')) {
    b.addEventListener('click', () => {
      const tab = b.dataset.tab;
      if (routeName() === tab) { page.scrollTo({ top: 0, behavior: 'smooth' }); return; }
      S.selecting = false; S.selected.clear();
      go(tab);
    });
  }
}

// ---------- shared bits ----------
function topbar({ fallback, trailing = '' }) {
  return `<div class="topbar"><button class="round glass" type="button" data-back="${fallback}" aria-label="Back">${I.back}</button>${trailing}</div>`;
}

function initials(name) {
  const skip = new Set(['of', 'the', 'and', 'for', 'at', 'in', '&', 'de', 'la', 'le']);
  const w = name.replace(/[^\p{L}\s&-]/gu, ' ').split(/[\s-]+/).filter(x => x && !skip.has(x.toLowerCase()));
  return w.slice(0, 3).map(x => x[0].toUpperCase()).join('') || name.slice(0, 2).toUpperCase();
}

function placeLine(m) {
  const where = [m.city, m.state].filter(Boolean).filter((x, i, a) => a.indexOf(x) === i).join(', ');
  const d = distance(m);
  return [where, d].filter(Boolean).join(' · ');
}

function distance(m) {
  if (!S.here || !m.at) return '';
  const mi = miles(S.here, m.at);
  return `${mi < 10 ? mi.toFixed(1) : Math.round(mi).toLocaleString('en-US')} mi`;
}

function miles([la1, lo1], [la2, lo2]) {
  const r = Math.PI / 180, R = 3958.8;
  const a = Math.sin((la2 - la1) * r / 2) ** 2 + Math.cos(la1 * r) * Math.cos(la2 * r) * Math.sin((lo2 - lo1) * r / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

const photo = (file, w, alt = '') => (file
  ? `<img class="ph" src="${commons(file, w)}" alt="${escape(alt)}" loading="lazy" decoding="async">`
  : '<span class="ph ph--empty" aria-hidden="true"></span>');

function museumCard(m, { overlay = false } = {}) {
  const fav = S.museumFavs.includes(m.id);
  return `<a class="pcard${overlay ? ' pcard--overlay' : ''}" href="#museum/${m.id}">
    <div class="pcard__img">${photo(m.image, overlay ? 500 : 800)}</div>
    <div class="pcard__body">
      ${overlay ? '' : `<span class="badge">${escape(initials(m.name))}</span>`}
      <div><p class="pcard__title">${escape(m.name)}</p><p class="pcard__sub">${escape(placeLine(m) || 'Museum')}</p></div>
    </div>
    ${overlay ? '' : `<button class="round glass pcard__heart" type="button" data-fav-museum="${m.id}" aria-pressed="${fav}" aria-label="${fav ? 'Remove from Favorites' : 'Add to Favorites'}">${I.heart(fav)}</button>`}
  </a>`;
}

// One shape for any artwork, from the MFA data or from open data.
function workInfo(id, fallback = null) {
  const a = D.mfaById.get(id);
  if (a) return { id, title: a.title, artist: a.artist, year: a.date, museum: 'MFA Boston', museumId: MFA,
    href: `guide.html#art/${id}`, thumb: cls => imgHTML(a, cls, a.title), mfa: true };
  const w = D.discover.works[id] ?? fallback;
  if (!w) return null;
  return { id, title: w.title, artist: w.artist, year: w.year, museum: shortMuseum(w.museumId, w.museum), museumId: w.museumId,
    href: `#work/${id}`, thumb: cls => (w.image ? `<img class="${cls}" src="${commons(w.image, 400)}" alt="${escape(w.title)}" loading="lazy">` : `<span class="${cls} img-empty"></span>`) };
}
const shortMuseum = (id, name) => (id === MFA ? 'MFA Boston' : D.byMuseum.get(id)?.name ?? name ?? '');

function rankedHTML(items) {
  return `<ol class="ranked">${items.map((x, i) => `<li><a href="${x.href}">
    <span class="rank">#${i + 1}</span>${x.thumb}
    <span><span class="ranked__title">${escape(x.title)}</span>${x.sub ? `<span class="ranked__sub">${escape(x.sub)}</span>` : ''}</span>
    ${I.chev}</a></li>`).join('')}</ol>`;
}

// Wikipedia's short summary of an article (online only; cached for the session).
const summaries = new Map();
function wikiSummary(title) {
  if (!title) return Promise.resolve(null);
  if (!summaries.has(title)) {
    summaries.set(title, fetch(`https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(title)}`)
      .then(r => (r.ok ? r.json() : null)).then(j => j?.extract ?? null).catch(() => null));
  }
  return summaries.get(title);
}
async function fillSummary(el, title, empty = '') {
  if (!el) return;
  const text = await wikiSummary(title);
  if (!el.isConnected) return;
  if (!text) { el.innerHTML = empty ? `<p>${escape(empty)}</p>` : ''; return; }
  const paras = text.split(/\n+/).filter(Boolean);
  el.innerHTML = `<div class="clamp">${paras.map(p => `<p>${escape(p)}</p>`).join('')}</div>
    <button class="btn btn--plain" type="button" data-more hidden>Show More</button>
    <p class="fine">From <a href="https://en.wikipedia.org/wiki/${encodeURIComponent(title)}" target="_blank" rel="noopener">Wikipedia</a></p>`;
  const box = el.querySelector('.clamp');
  if (box.scrollHeight > box.clientHeight + 2) el.querySelector('[data-more]').hidden = false;   // only when the text is cut
}

// ---------- maps ----------
// MapLibre with OpenFreeMap tiles (free, no key): Positron in light mode, Dark in dark mode.
const dark = () => matchMedia('(prefers-color-scheme: dark)').matches;
const cssVar = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const lngLat = at => [at[1], at[0]];

const US = [[-124.8, 24.4], [-66.9, 49.4]];   // the lower 48, the default view

function makeMap(el, { center = null, zoom = 8, cooperative = false } = {}) {
  if (!window.maplibregl || !el) return null;
  const map = new maplibregl.Map({
    container: el, style: `https://tiles.openfreemap.org/styles/${dark() ? 'dark' : 'positron'}`,
    ...(center ? { center: lngLat(center), zoom } : { bounds: US, fitBoundsOptions: { padding: 12 } }),
    attributionControl: { compact: true },
    dragRotate: false, pitchWithRotate: false, touchPitch: false, cooperativeGestures: cooperative,
  });
  map.touchZoomRotate.disableRotation();
  // credits stay one tap away (the ⓘ button) instead of covering the map
  map.once('idle', () => el.querySelector('.maplibregl-ctrl-attrib')?.classList.remove('maplibregl-compact-show'));
  maps.push(map);
  return map;
}

// Museums as one map layer; with `cluster`, nearby ones merge into numbered circles until you zoom in
// (HIG maps: "Cluster overlapping points of interest"). `on` museums are drawn in Klein blue.
function museumLayer(map, list, { cluster = true, on = new Set(), onPick = null } = {}) {
  const data = { type: 'FeatureCollection', features: list.filter(m => m.at).map(m => ({
    type: 'Feature', properties: { id: m.id, on: on.has(m.id) }, geometry: { type: 'Point', coordinates: lngLat(m.at) } })) };
  map.on('load', () => {
    const accent = cssVar('--accent') || '#002fa7', ink = cssVar('--accent-ink') || '#fff';
    map.addSource('museums', { type: 'geojson', data, cluster, clusterRadius: 46, clusterMaxZoom: 9 });
    map.addLayer({ id: 'clusters', type: 'circle', source: 'museums', filter: ['has', 'point_count'],
      paint: { 'circle-color': accent, 'circle-radius': ['step', ['get', 'point_count'], 15, 10, 18, 100, 22], 'circle-stroke-width': 2, 'circle-stroke-color': '#fff' } });
    map.addLayer({ id: 'cluster-count', type: 'symbol', source: 'museums', filter: ['has', 'point_count'],
      layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-font': ['Noto Sans Bold'], 'text-size': 12, 'text-allow-overlap': true },
      paint: { 'text-color': ink } });
    map.addLayer({ id: 'points', type: 'circle', source: 'museums', filter: ['!', ['has', 'point_count']],
      paint: { 'circle-color': ['case', ['get', 'on'], accent, dark() ? '#d1d1d6' : '#3a3a3c'], 'circle-radius': 7, 'circle-stroke-width': 2, 'circle-stroke-color': '#fff' } });
    map.addLayer({ id: 'picked', type: 'circle', source: 'museums', filter: ['==', ['get', 'id'], ''],
      paint: { 'circle-color': accent, 'circle-radius': 11, 'circle-stroke-width': 3, 'circle-stroke-color': '#fff' } });
    map.on('click', 'clusters', async e => {
      const f = e.features[0];
      const zoom = await map.getSource('museums').getClusterExpansionZoom(f.properties.cluster_id);
      map.easeTo({ center: f.geometry.coordinates, zoom });
    });
    map.on('click', 'points', e => {
      const id = e.features[0].properties.id;
      map.setFilter('picked', ['==', ['get', 'id'], id]);   // HIG: clearly identify the selection
      onPick ? onPick(D.byMuseum.get(id)) : go(`museum/${id}`);
    });
    for (const l of ['clusters', 'points']) {
      map.on('mouseenter', l, () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', l, () => { map.getCanvas().style.cursor = ''; });
    }
  });
}

function meMarker(map, at) {
  const el = document.createElement('span');
  el.className = 'pin pin--me';
  el.setAttribute('aria-label', 'You are here');
  new maplibregl.Marker({ element: el }).setLngLat(lngLat(at)).addTo(map);
}

function fitTo(map, list, maxZoom = 11) {
  const pts = list.filter(m => m.at);
  if (!pts.length) return;
  const lons = pts.map(m => m.at[1]), lats = pts.map(m => m.at[0]);
  map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: 48, maxZoom, duration: 0 });
}

// ---------- location ----------
// Asks only when you tap "Show Museums Near Me"; afterwards it's remembered on this device.
async function locate(ask) {
  if (!navigator.geolocation) return null;
  let allowed = false;
  try { allowed = localStorage.getItem('gg-loc') === '1'; } catch { /* storage off */ }
  if (!ask && !allowed) return null;
  return new Promise(res => navigator.geolocation.getCurrentPosition(
    p => { try { localStorage.setItem('gg-loc', '1'); } catch { /* fine */ } res([p.coords.latitude, p.coords.longitude]); },
    () => res(null), { maximumAge: 10 * 60e3, timeout: 12e3 }));
}

// ---------- Home ----------
function homePage() {
  return `
    <h1 class="large-title">Gallery Guide</h1>
    <p class="lede">Art museums across the US, and your own collection.</p>
    <div class="s-section" style="margin-top:18px">${continueCard()}</div>
    ${didYouKnow()}
    <section class="s-section"><div class="s-head"><h2>Your Top Artists</h2></div>${topArtists()}</section>
    <section class="s-section"><div class="s-head"><h2>Your Museum Map</h2></div><div class="mini-map" id="homeMap"></div>
      <p class="fine" id="homeMapNote"></p></section>
    <section class="s-section"><div class="s-head"><h2>Museums Nearby</h2><a href="#museums">Full List</a></div>${nearby()}</section>
    <p class="fine" style="margin-top:28px">Museum data from Wikidata, photos from Wikimedia Commons. <button class="btn--plain" type="button" data-update style="color:var(--accent);font-weight:600">Check for Updates</button></p>`;
}

function continueCard() {
  const m = D.byMuseum.get(MFA);
  const live = S.active;
  return `<a class="cont" href="${live ? 'guide.html#visits' : 'guide.html'}">
    <span class="cont__img">${photo(m?.image, 300)}</span>
    <span><p class="cont__title">${live ? '<span class="live-dot"></span>Visit in progress' : 'MFA Boston'}</p>
      <p class="cont__sub">${live ? `${live.rooms.length} room${live.rooms.length === 1 ? '' : 's'} so far · open the map guide` : '3D map guide, tours and directions'}</p></span>
    <span class="cont__go">${I.chev}</span></a>`;
}

// One curiosity a day, about a work at the MFA.
function didYouKnow() {
  const ids = Object.keys(D.curio.works ?? {}).filter(id => D.mfaById.has(id));
  if (!ids.length) return '';
  const day = Math.floor(Date.now() / 864e5);
  const id = ids[day % ids.length];
  const facts = D.curio.works[id];
  const a = D.mfaById.get(id);
  return `<section class="s-section"><a class="dyk" href="guide.html#art/${id}">
    <p class="eyebrow">Did you know?</p>
    <p class="dyk__fact">${escape(facts[day % facts.length])}</p>
    <span class="dyk__work">${imgHTML(a, '', a.title)}<span>${escape(a.title)}${a.artist ? ` · ${escape(a.artist)}` : ''}</span></span>
  </a></section>`;
}

function savedWorks() {
  return S.favs.map(f => workInfo(f.id, f.work)).filter(Boolean);
}

function topArtists() {
  const count = new Map();
  for (const w of savedWorks()) if (w.artist) count.set(w.artist, (count.get(w.artist) ?? 0) + 1);
  const top = [...count].sort((a, b) => b[1] - a[1]).slice(0, 8);
  const byName = new Map(Object.values(D.discover.artists).map(a => [a.name, a]));
  if (!top.length) {
    const vg = D.discover.artists.Q5582;
    return `<div class="artist-cards"><a class="acard acard--locked" href="#discover">
      ${vg?.image ? `<img src="${commons(vg.image, 500)}" alt="" class="ph">` : ''}
      <span class="acard__lock">SAVE TO REVEAL</span>
      <span class="acard__body"><p class="acard__name">Your Top Artists</p><p class="acard__sub">Save works you love and your favourite artists appear here</p></span></a></div>`;
  }
  return `<div class="artist-cards">${top.map(([name, n]) => {
    const a = byName.get(name);
    const pic = a?.image ? `<img class="ph" src="${commons(a.image, 400)}" alt="">` : (savedWorks().find(w => w.artist === name)?.thumb('ph') ?? '');
    return `<a class="acard" href="${a ? `#artist/${a.id}` : '#collection'}">${pic}
      <span class="acard__body"><p class="acard__name">${escape(name)}</p><p class="acard__sub">${n} saved</p></span></a>`;
  }).join('')}</div>`;
}

function nearby() {
  if (!S.here) {
    return `<div class="info-card" style="text-align:center"><p style="color:var(--ink-2)">See the art museums closest to you.</p>
      <button class="btn" type="button" data-locate>${I.locate}Show Museums Near Me</button></div>`;
  }
  const near = D.museums.filter(m => m.at).map(m => [miles(S.here, m.at), m]).sort((a, b) => a[0] - b[0]).slice(0, 10).map(x => x[1]);
  return `<div class="hscroll">${near.map(m => museumCard(m, { overlay: true })).join('')}</div>`;
}

afterRender.home = () => {
  const visited = new Set();
  if (S.visits.length || S.active) visited.add(MFA);
  const ids = [...visited, ...S.museumFavs.filter(id => !visited.has(id))];
  const pts = ids.map(id => D.byMuseum.get(id)).filter(m => m?.at);
  const map = makeMap($('#homeMap'), { cooperative: true });
  if (!map) return;
  museumLayer(map, pts, { cluster: false, on: visited });
  if (S.here) meMarker(map, S.here);
  if (pts.length === 1) map.jumpTo({ center: lngLat(pts[0].at), zoom: 9 });
  else if (pts.length > 1) fitTo(map, pts, 9);
  $('#homeMapNote').textContent = pts.length
    ? `Blue: museums you've visited${pts.length > visited.size ? ' · grey: your favourites' : ''}.`
    : 'Museums you visit and favourite will appear here.';
};

// ---------- Museums ----------
function museumsList() {
  let list = D.museums;
  if (S.museumsFilter === 'fav') list = S.museumFavs.map(id => D.byMuseum.get(id)).filter(Boolean);
  const q = norm(S.query);
  if (q) list = list.filter(m => norm(`${m.name} ${m.city ?? ''} ${m.state ?? ''}`).includes(q));
  if (S.area) list = list.filter(m => m.at && S.area.contains(m.at));
  if (S.here && S.museumsFilter !== 'fav') list = [...list].sort((a, b) => (a.at ? miles(S.here, a.at) : 1e9) - (b.at ? miles(S.here, b.at) : 1e9));
  return list;
}

function museumsPage() {
  const view = S.museumsView;
  return `
    <h1 class="large-title">Museums</h1>
    <div class="searchbar">
      <label class="field">${I.search}<input id="museumQuery" type="search" placeholder="Museums or cities" value="${escape(S.query)}" autocomplete="off" enterkeyhint="search" aria-label="Search museums"></label>
      <div class="seg" role="group" aria-label="View">
        <button type="button" data-mview="list" aria-pressed="${view === 'list'}" aria-label="List">${I.list}</button>
        <button type="button" data-mview="map" aria-pressed="${view === 'map'}" aria-label="Map">${I.map}</button>
      </div>
    </div>
    <div class="chips">
      <button class="chip" type="button" data-mfilter="all" aria-pressed="${S.museumsFilter === 'all'}">All</button>
      <button class="chip" type="button" data-mfilter="fav" aria-pressed="${S.museumsFilter === 'fav'}">${I.heart(false)}Favorites</button>
      ${S.area ? `<button class="chip" type="button" data-clear-area aria-pressed="true">In this area ✕</button>` : ''}
    </div>
    <div id="museumsBody">${view === 'map' ? '<div class="museum-map"><div class="map" id="museumMap"></div></div>' : museumsListHTML()}</div>`;
}

function museumsListHTML() {
  const list = museumsList();
  if (!list.length) {
    return S.museumsFilter === 'fav'
      ? `<div class="s-empty"><h2>No Favorites Yet</h2><p>Tap the heart on a museum to keep it here.</p></div>`
      : `<div class="s-empty"><h2>No Museums Found</h2><p>Try another name or city.</p></div>`;
  }
  return `<div class="stack-list" style="margin-top:16px">${list.slice(0, S.shown).map(m => museumCard(m)).join('')}</div>
    ${list.length > S.shown ? `<button class="btn btn--gray more" type="button" data-more-museums>Show More (${(list.length - S.shown).toLocaleString('en-US')})</button>` : ''}
    <p class="fine">${list.length.toLocaleString('en-US')} museums · data from Wikidata, photos from Wikimedia Commons</p>`;
}

afterRender.museums = () => {
  if (S.museumsView !== 'map') return;
  const el = $('#museumMap');
  const wrap = el.parentElement;
  const list = museumsList();
  const map = makeMap(el, S.here ? { center: S.here, zoom: 8 } : {});
  if (!map) return;
  museumLayer(map, list, { onPick: m => {
    wrap.querySelector('.map-preview')?.remove();
    wrap.insertAdjacentHTML('beforeend', `<div class="map-preview">${museumCard(m)}</div>`);
  } });
  if (S.here) meMarker(map, S.here);
  else if (list.length && list.length < 200) fitTo(map, list);
  map.on('movestart', e => {
    if (!e.originalEvent || wrap.querySelector('.map-area')) return;   // only after you move the map yourself
    wrap.insertAdjacentHTML('beforeend', '<button class="map-area" type="button" data-area>Search This Area</button>');
    wrap.querySelector('[data-area]').addEventListener('click', () => {
      const b = map.getBounds();
      S.area = { contains: at => b.contains(lngLat(at)) };
      S.museumsView = 'list'; S.shown = PAGE_SIZE; route();
    });
  });
};

// ---------- Museum page ----------
function museumPage(id) {
  const m = D.byMuseum.get(id);
  if (!m) return `${topbar({ fallback: 'museums' })}<div class="s-empty"><h2>Museum Not Found</h2></div>`;
  const fav = S.museumFavs.includes(id);
  const highlights = museumHighlights(id);
  page.classList.add('page--hero');
  return `
    ${topbar({ fallback: 'museums', trailing: `<button class="round glass" type="button" data-fav-museum="${id}" aria-pressed="${fav}" aria-label="${fav ? 'Remove from Favorites' : 'Add to Favorites'}">${I.heart(fav)}</button>` })}
    <div class="hero">${m.image ? `<img src="${commons(m.image, 1100)}" alt="">` : ''}
      <div class="hero__text"><p class="eyebrow">Museum</p><h1>${escape(m.name)}</h1></div></div>
    <div class="info-card">
      <div class="mplace"><span class="badge">${escape(initials(m.name))}</span>
        <div><p class="mplace__name">${escape([m.city, m.state].filter(Boolean).join(', ') || 'United States')}</p>
        ${m.address || distance(m) ? `<p class="mplace__sub">${escape([m.address, distance(m)].filter(Boolean).join(' · '))}</p>` : ''}</div></div>
      <div class="links">
        ${m.wikipedia ? `<a href="https://en.wikipedia.org/wiki/${encodeURIComponent(m.wikipedia)}" target="_blank" rel="noopener">Wikipedia ${I.ext}</a>` : ''}
        ${m.website ? `<a href="${escape(m.website)}" target="_blank" rel="noopener">${escape(host(m.website))} ${I.ext}</a>` : ''}
      </div>
      ${id === MFA ? `<div class="btn-row"><a class="btn" href="guide.html">${I.map}Open the Map Guide</a></div>
        <p class="fine">3D floor plans, search for every work on view, tours, directions and your visit diary.</p>` : ''}
    </div>
    <div class="info-card"><h2>Welcome to ${escape(m.name)}</h2><div id="museumAbout"><p style="color:var(--ink-3)">Loading…</p></div></div>
    <div class="info-card"><h2>Visit Information</h2>
      <dl class="kv">
        <dt>Address</dt><dd>${escape(m.address || [m.city, m.state].filter(Boolean).join(', ') || '—')}</dd>
        <dt>Hours</dt><dd>Check the museum's website for current hours</dd>
        ${m.website ? `<dt>Website</dt><dd>${escape(host(m.website))}</dd>` : ''}
      </dl>
      <div class="btn-row">
        ${m.at ? `<a class="btn btn--gray" href="https://maps.apple.com/?daddr=${m.at.join(',')}&q=${encodeURIComponent(m.name)}" target="_blank" rel="noopener">${I.nav}Get Directions</a>` : ''}
        ${m.website ? `<a class="btn btn--gray" href="${escape(m.website)}" target="_blank" rel="noopener">${I.ext}Open Website</a>` : ''}
      </div>
    </div>
    ${highlights.length ? `<section class="s-section"><div class="s-head"><h2>Highlights</h2></div>
      <div class="tiles">${highlights.map(tileHTML).join('')}</div></section>` : ''}
    <p class="fine" style="margin-top:20px">Photo: Wikimedia Commons · Data: Wikidata${m.wikipedia ? ' · Text: Wikipedia' : ''}</p>`;
}
afterRender.museum = id => fillSummary($('#museumAbout'), D.byMuseum.get(id)?.wikipedia, 'No description yet.');

function museumHighlights(id) {
  if (id === MFA) {
    const famous = Object.keys(D.curio.works ?? {}).filter(x => D.mfaById.get(x)?.image || D.mfaById.get(x)?.img);
    return famous.slice(0, 8).map(x => workInfo(x));
  }
  return Object.values(D.discover.works).filter(w => w.museumId === id).sort((a, b) => b.links - a.links).slice(0, 8).map(w => workInfo(w.id));
}

function tileHTML(w) {
  return `<a class="tile" href="${w.href}"><div class="tile__img">${w.thumb('ph')}</div>
    <p class="tile__title">${escape(w.title)}</p><p class="tile__sub">${escape([w.artist, w.year].filter(Boolean).join(' · '))}</p></a>`;
}

const host = url => { try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; } };

// ---------- Collection ----------
function collectionPage() {
  const works = savedWorks();
  const t = S.collTab;
  return `
    <div class="coll-head"><div><h1 class="large-title">Your Collection</h1>
      <p class="lede">${works.length} artwork${works.length === 1 ? '' : 's'} · ${S.visits.length} visit${S.visits.length === 1 ? '' : 's'} · ${S.lists.length} collection${S.lists.length === 1 ? '' : 's'}</p></div></div>
    <div class="seg seg--wide" role="tablist" aria-label="Collection">
      <button type="button" data-coll="library" aria-pressed="${t === 'library'}">Library</button>
      <button type="button" data-coll="visits" aria-pressed="${t === 'visits'}">Visits</button>
      <button type="button" data-coll="lists" aria-pressed="${t === 'lists'}">Collections</button>
    </div>
    ${t === 'library' ? libraryHTML(works) : t === 'visits' ? visitsHTML() : listsHTML()}`;
}

function libraryToolbar(works) {
  const museums = [...new Set(works.map(w => w.museum).filter(Boolean))].sort();
  return `<div class="toolbar" role="toolbar" aria-label="Library tools">
    <label aria-label="Filter by museum" ${S.libMuseum ? 'aria-pressed="true"' : ''}>${I.filter}
      <select data-lib-museum><option value="">All museums</option>${museums.map(m => `<option ${m === S.libMuseum ? 'selected' : ''}>${escape(m)}</option>`).join('')}</select></label>
    <label aria-label="Sort">${I.sort}
      <select data-lib-sort>${[['new', 'Recently saved'], ['title', 'Title'], ['artist', 'Artist']].map(([v, l]) => `<option value="${v}" ${v === S.libSort ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
    <button type="button" data-lib-view aria-label="${S.libView === 'grid' ? 'List view' : 'Grid view'}" aria-pressed="${S.libView === 'grid'}">${S.libView === 'grid' ? I.list : I.grid}</button>
    <button type="button" data-select aria-label="Select" aria-pressed="${S.selecting}">${I.checkCircle}</button>
  </div>`;
}

function libraryHTML(all, { listId = null } = {}) {
  let works = all;
  if (S.libMuseum) works = works.filter(w => w.museum === S.libMuseum);
  if (S.libSort === 'title') works = [...works].sort((a, b) => a.title.localeCompare(b.title));
  if (S.libSort === 'artist') works = [...works].sort((a, b) => (a.artist ?? '~').localeCompare(b.artist ?? '~'));
  if (!all.length) {
    return listId
      ? `<div class="s-empty"><h2>Empty Collection</h2><p>In your Library, tap Select, choose works and add them here.</p></div>`
      : `<div class="s-empty"><div class="s-empty__art">${D.discover.works.Q185372?.image ? `<img src="${commons(D.discover.works.Q185372.image, 300)}" alt="">` : ''}</div>
        <h2>Nothing Saved Yet</h2><p>Tap the heart on any artwork, here or in the MFA guide, to keep it in your Library.</p>
        <a class="btn" href="#discover">Discover Art</a></div>`;
  }
  const rows = works.map(w => {
    const checked = S.selected.has(w.id);
    const inner = `<span class="check">${I.check}</span>${w.thumb('thumb')}
      <span><span class="lib-row__title">${escape(w.title)}</span>
      <span class="lib-row__sub">${escape([w.artist, w.year].filter(Boolean).join(' · '))}</span>
      ${w.museum ? `<span class="lib-row__where">${I.pin}${escape(w.museum)}</span>` : ''}</span>
      <svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 5 7 7-7 7"/></svg>`;
    return `<li>${S.selecting
      ? `<button class="lib-row" type="button" role="checkbox" aria-checked="${checked}" data-pick="${w.id}">${inner}</button>`
      : `<a class="lib-row" href="${w.href}">${inner}</a>`}</li>`;
  }).join('');
  return `${libraryToolbar(all)}
    <ul class="${S.libView === 'grid' ? 'lib-grid' : 'lib-list'} ${S.selecting ? 'selecting' : ''}">${rows}</ul>
    ${S.selecting ? `<div class="select-bar glass">
      ${listId ? `<button class="btn btn--gray" type="button" data-remove-from-list="${listId}" ${S.selected.size ? '' : 'disabled'}>Remove (${S.selected.size})</button>`
        : `<button class="btn" type="button" data-add-to-list ${S.selected.size ? '' : 'disabled'}>${I.plus}Add to Collection (${S.selected.size})</button>
           <button class="btn btn--gray" type="button" data-unsave ${S.selected.size ? '' : 'disabled'}>Remove</button>`}
    </div>` : ''}`;
}

function visitsHTML() {
  const rows = [];
  if (S.active) {
    rows.push(`<li><a class="lib-row" href="guide.html#visits"><span class="check"></span><span class="mosaic"></span>
      <span><span class="lib-row__title"><span class="live-dot"></span>Visit in progress</span>
      <span class="lib-row__sub">MFA Boston · ${S.active.rooms.length} room${S.active.rooms.length === 1 ? '' : 's'} · ${duration(S.active)}</span></span>${I.chev}</a></li>`);
  }
  for (const v of S.visits) {
    const snap = v.snapshots ? Object.entries(v.snapshots)[0] : null;
    rows.push(`<li><a class="lib-row" href="guide.html#entry/${v.id}"><span class="check"></span>
      ${snap ? `<img class="thumb" src="${blobURL(`${v.id}:${snap[0]}`, snap[1])}" alt="">` : '<span class="thumb"></span>'}
      <span><span class="lib-row__title">${new Date(v.startedAt).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</span>
      <span class="lib-row__sub">${v.rooms.length} room${v.rooms.length === 1 ? '' : 's'} · ${duration(v)}</span>
      <span class="lib-row__where">${I.pin}MFA Boston</span></span>${I.chev}</a></li>`);
  }
  if (!rows.length) {
    return `<div class="s-empty"><h2>No Visits Yet</h2><p>Start a visit in the MFA map guide and mark the rooms you walk through. It becomes a diary here.</p>
      <a class="btn" href="guide.html#visits">Open the Map Guide</a></div>`;
  }
  return `<ul class="lib-list">${rows.join('')}</ul>`;
}

function listsHTML() {
  const rows = S.lists.map(l => {
    const pics = l.items.slice(0, 4).map(id => workInfo(id, S.favs.find(f => f.id === id)?.work)).filter(Boolean);
    return `<li><a class="lib-row" href="#list/${l.id}"><span class="check"></span>
      <span class="mosaic">${pics.map(w => w.thumb('')).join('')}</span>
      <span><span class="lib-row__title">${escape(l.name)}</span><span class="lib-row__sub">${l.items.length} artwork${l.items.length === 1 ? '' : 's'}</span></span>${I.chev}</a></li>`;
  }).join('');
  return `<button class="btn btn--gray more" type="button" data-new-list>${I.plus}New Collection</button>
    ${rows ? `<ul class="lib-list">${rows}</ul>` : `<div class="s-empty"><h2>Make Your Own Collections</h2><p>Group works you love: "Blues I loved", "For mom", "Next visit"…</p></div>`}`;
}

function listPage(id) {
  const l = S.lists.find(x => x.id === id);
  if (!l) return `${topbar({ fallback: 'collection' })}<div class="s-empty"><h2>Collection Not Found</h2></div>`;
  const works = l.items.map(x => workInfo(x, S.favs.find(f => f.id === x)?.work)).filter(Boolean);
  return `${topbar({ fallback: 'collection' })}
    <h1 class="large-title">${escape(l.name)}</h1>
    <p class="lede">${works.length} artwork${works.length === 1 ? '' : 's'}</p>
    <div class="btn-row" style="margin-top:10px"><button class="btn btn--gray" type="button" data-rename-list="${id}">Rename</button>
      <button class="btn btn--danger" type="button" data-delete-list="${id}">Delete Collection</button></div>
    ${libraryHTML(works, { listId: id })}`;
}

// ---------- Discover ----------
function discoverPage() {
  const d = D.discover;
  const works = d.popularArtworks.map(id => workInfo(id)).filter(Boolean);
  const [first, ...rest] = works;
  return `
    <h1 class="large-title">Discover</h1>
    <p class="lede">The best-known art in American museums.</p>
    ${first ? `<section class="s-section"><div class="s-head"><h2>Popular Artworks</h2><a href="#popular/artworks">See All ${I.chev}</a></div>
      <a class="feature" href="${first.href}"><div class="feature__img">${first.thumb('ph')}</div>
        <div class="feature__row"><span class="rank">1</span><div><p class="feature__title">${escape(first.title)}</p>
        <p class="feature__sub">${escape(first.artist ?? '')}</p><p class="feature__sub">${escape(first.museum)}</p></div></div></a>
      <div class="tiles">${rest.slice(0, 4).map(tileHTML).join('')}</div></section>` : ''}
    <section class="s-section"><div class="s-head"><h2>Popular Museums</h2><a href="#popular/museums">See All ${I.chev}</a></div>
      <div class="tiles">${d.popularMuseums.slice(0, 4).map(id => D.byMuseum.get(id)).filter(Boolean).map(m => `<a class="tile tile--wide" href="#museum/${m.id}">
        <div class="tile__img">${photo(m.image, 500)}</div><p class="tile__title">${escape(m.name)}</p><p class="tile__sub">${escape([m.city, m.state].filter(Boolean).join(', '))}</p></a>`).join('')}</div></section>
    <section class="s-section"><div class="s-head"><h2>Popular Artists</h2><a href="#popular/artists">See All ${I.chev}</a></div>
      <div class="people">${d.popularArtists.slice(0, 4).map(id => d.artists[id]).filter(Boolean).map(personHTML).join('')}</div></section>
    <section class="s-section"><div class="s-head"><h2>Explore Art</h2></div>
      <div class="tiles">${d.themes.filter(t => t.works.length >= 2).map(t => {
        const [a, b] = t.works.map(id => workInfo(id));
        return `<a class="tile" href="#theme/${t.id}"><div class="diptych">${a.thumb('')}${b.thumb('')}</div>
          <p class="tile__sub" style="margin-top:8px">${escape(t.kind)}</p><p class="tile__title" style="margin-top:2px">${escape(t.title)}</p></a>`;
      }).join('')}</div></section>
    <p class="fine" style="margin-top:24px">Ranked by how many Wikipedia languages write about them. Data from Wikidata, pictures from Wikimedia Commons.</p>`;
}

function personHTML(a) {
  return `<a class="person" href="#artist/${a.id}"><div class="person__img">${photo(a.image, 300)}</div><p class="person__name">${escape(a.name)}</p></a>`;
}

function popularPage(kind) {
  const d = D.discover;
  const title = { artworks: 'Popular Artworks', artists: 'Popular Artists', museums: 'Popular Museums' }[kind] ?? 'Popular';
  let items = [];
  if (kind === 'artworks') items = d.popularArtworks.map(id => workInfo(id)).filter(Boolean)
    .map(w => ({ href: w.href, title: w.title, sub: [w.artist, w.museum].filter(Boolean).join(' · '), thumb: w.thumb('thumb') }));
  if (kind === 'artists') items = d.popularArtists.map(id => d.artists[id]).filter(Boolean)
    .map(a => ({ href: `#artist/${a.id}`, title: a.name, sub: life(a), thumb: a.image ? `<img class="thumb thumb--round" src="${commons(a.image, 200)}" alt="" loading="lazy">` : '<span class="thumb thumb--round"></span>' }));
  if (kind === 'museums') items = D.museums.slice(0, 30)
    .map(m => ({ href: `#museum/${m.id}`, title: m.name, sub: [m.city, m.state].filter(Boolean).join(', '), thumb: m.image ? `<img class="thumb" src="${commons(m.image, 200)}" alt="" loading="lazy">` : '<span class="thumb"></span>' }));
  return `${topbar({ fallback: 'discover' })}<h1 class="large-title">${title}</h1>
    <p class="lede">Ranked by how many Wikipedia languages write about them.</p>
    <div style="margin-top:12px">${rankedHTML(items)}</div>`;
}

const life = a => (a.born || a.died ? `${a.born ?? '?'}–${a.died ?? ''}` : '');

function artistPage(id) {
  const a = D.discover.artists[id];
  if (!a) return `${topbar({ fallback: 'discover' })}<div class="s-empty"><h2>Artist Not Found</h2></div>`;
  const works = a.works.map(x => workInfo(x)).filter(Boolean);
  return `${topbar({ fallback: 'discover' })}
    <div class="portrait">${photo(a.image ?? D.discover.works[a.works[0]]?.image, 900, a.name)}</div>
    <h1 class="work-title">${escape(a.name)}</h1>
    ${life(a) ? `<p class="work-sub">${life(a)}</p>` : ''}
    <section class="s-section"><div class="s-head"><h2>About the Artist</h2></div><div id="artistAbout"><p style="color:var(--ink-3)">Loading…</p></div></section>
    <section class="s-section"><div class="s-head"><h2>Popular Artworks</h2></div>
      ${rankedHTML(works.map(w => ({ href: w.href, title: w.title, sub: [w.year, w.museum].filter(Boolean).join(' · '), thumb: w.thumb('thumb') })))}</section>
    <section class="s-section"><div class="s-head"><h2>Where to See Their Work</h2></div>
      ${a.museums.filter(m => D.byMuseum.has(m.id)).map(m => `<a class="link-card" href="#museum/${m.id}"><div><strong>${escape(shortMuseum(m.id, m.name))}</strong>
        <span>${escape(placeLine(D.byMuseum.get(m.id) ?? {}) || 'View museum')}</span></div>${I.arrow}</a>`).join('')}</section>
    <p class="fine" style="margin-top:20px">Works with a picture in Wikimedia Commons, in US collections listed on Wikidata.</p>`;
}
afterRender.artist = id => fillSummary($('#artistAbout'), D.discover.artists[id]?.wikipedia, '');

function themePage(id) {
  const t = D.discover.themes.find(x => x.id === id);
  if (!t) return `${topbar({ fallback: 'discover' })}<div class="s-empty"><h2>Not Found</h2></div>`;
  const works = t.works.map(x => workInfo(x)).filter(Boolean);
  return `${topbar({ fallback: 'discover' })}
    <div class="triptych">${works.slice(0, 3).map(w => w.thumb('')).join('')}</div>
    <p class="eyebrow" style="margin-top:20px">${escape(t.kind === 'Era' ? 'Through time' : `The ${t.kind.toLowerCase()}`)}</p>
    <h1 class="large-title">${escape(t.title)}</h1>
    <p class="lede">${escape(t.tagline)}</p>
    <section class="s-section"><div class="s-head"><h2>About</h2></div><div id="themeAbout"><p style="color:var(--ink-3)">Loading…</p></div></section>
    <section class="s-section"><div class="s-head"><h2>In US Museums</h2></div>
      ${rankedHTML(works.map(w => ({ href: w.href, title: w.title, sub: [w.artist, w.year].filter(Boolean).join(' · '), thumb: w.thumb('thumb') })))}</section>`;
}
afterRender.theme = id => fillSummary($('#themeAbout'), D.discover.themes.find(x => x.id === id)?.wikipedia, '');

function workPage(id) {
  const w = D.discover.works[id] ?? S.favs.find(f => f.id === id)?.work;
  if (!w) return `${topbar({ fallback: 'discover' })}<div class="s-empty"><h2>Artwork Not Found</h2></div>`;
  const saved = S.favs.some(f => f.id === id);
  const artist = w.artistId && D.discover.artists[w.artistId];
  const more = artist ? artist.works.filter(x => x !== id).slice(0, 6).map(x => workInfo(x)).filter(Boolean) : [];
  const m = D.byMuseum.get(w.museumId);
  return `${topbar({ fallback: 'discover', trailing: `<button class="round glass" type="button" data-save-work="${id}" aria-pressed="${saved}" aria-label="${saved ? 'Remove from Library' : 'Save to Library'}">${I.heart(saved)}</button>` })}
    <div class="work-hero">${w.image ? `<img src="${commons(w.image, 1000)}" alt="${escape(w.title)}">` : ''}</div>
    <h1 class="work-title">${escape(w.title)}</h1>
    <p class="work-sub">${escape([w.artist, w.year].filter(Boolean).join(' · '))}</p>
    <section class="s-section">
      ${artist ? `<a class="link-card" href="#artist/${artist.id}"><div><strong>${escape(artist.name)}</strong><span>About the artist</span></div>${I.arrow}</a>` : ''}
      ${w.museumId ? `<a class="link-card" href="#museum/${w.museumId}"><div><strong>${escape(shortMuseum(w.museumId, w.museum))}</strong><span>${escape(m ? placeLine(m) || 'View museum' : 'View museum')}</span></div>${I.arrow}</a>` : ''}
    </section>
    ${more.length ? `<section class="s-section"><div class="s-head"><h2>More by This Artist</h2></div>
      ${rankedHTML(more.map(x => ({ href: x.href, title: x.title, sub: [x.year, x.museum].filter(Boolean).join(' · '), thumb: x.thumb('thumb') })))}</section>` : ''}
    <p class="fine" style="margin-top:20px">Picture: <a href="https://commons.wikimedia.org/wiki/File:${encodeURIComponent(w.image ?? '')}" target="_blank" rel="noopener">Wikimedia Commons</a> · Data: <a href="https://www.wikidata.org/wiki/${id}" target="_blank" rel="noopener">Wikidata</a></p>`;
}

// ---------- events ----------
async function onClick(e) {
  const t = e.target.closest('[data-back],[data-fav-museum],[data-mview],[data-mfilter],[data-clear-area],[data-more-museums],[data-locate],[data-coll],[data-lib-view],[data-select],[data-pick],[data-add-to-list],[data-unsave],[data-new-list],[data-rename-list],[data-delete-list],[data-remove-from-list],[data-save-work],[data-more],[data-update]');
  if (!t) return;
  const d = t.dataset;
  if (d.back !== undefined) return back(d.back);
  if (d.favMuseum) {
    e.preventDefault(); e.stopPropagation();
    const on = await MuseumFavorites.toggle(d.favMuseum);
    S.museumFavs = await MuseumFavorites.list();
    for (const b of page.querySelectorAll(`[data-fav-museum="${d.favMuseum}"]`)) { b.setAttribute('aria-pressed', String(on)); b.innerHTML = I.heart(on); }
    return toast(on ? 'Added to Favorites' : 'Removed from Favorites');
  }
  if (d.mview) { S.museumsView = d.mview; return route({ keepScroll: true }); }
  if (d.mfilter) { S.museumsFilter = d.mfilter; S.shown = PAGE_SIZE; return route({ keepScroll: true }); }
  if (d.clearArea !== undefined) { S.area = null; return route({ keepScroll: true }); }
  if (d.moreMuseums !== undefined) { S.shown += PAGE_SIZE * 2; return route({ keepScroll: true }); }
  if (d.locate !== undefined) {
    t.disabled = true; t.textContent = 'Finding you…';
    S.here = await locate(true);
    if (!S.here) toast('Location is off. You can allow it in Settings › Privacy.');
    return route({ keepScroll: true });
  }
  if (d.coll) { S.collTab = d.coll; S.selecting = false; S.selected.clear(); return route({ keepScroll: true }); }
  if (d.libView !== undefined) { S.libView = S.libView === 'grid' ? 'list' : 'grid'; return route({ keepScroll: true }); }
  if (d.select !== undefined) { S.selecting = !S.selecting; S.selected.clear(); return route({ keepScroll: true }); }
  if (d.pick) { S.selected.has(d.pick) ? S.selected.delete(d.pick) : S.selected.add(d.pick); return route({ keepScroll: true }); }
  if (d.addToList !== undefined) return pickList([...S.selected]);
  if (d.unsave !== undefined) {
    for (const id of S.selected) await Favorites.toggle(id);
    toast(`Removed ${S.selected.size} from Library`);
    S.selected.clear(); S.selecting = false; await refreshMine(); return route({ keepScroll: true });
  }
  if (d.newList !== undefined) {
    const name = prompt('Name your collection', '');
    if (!name?.trim()) return;
    await Lists.create(name.trim()); await refreshMine(); return route({ keepScroll: true });
  }
  if (d.renameList) {
    const l = S.lists.find(x => x.id === d.renameList);
    const name = prompt('Rename collection', l?.name ?? '');
    if (!name?.trim() || !l) return;
    await Lists.remove(l.id);
    const fresh = await Lists.create(name.trim());
    await Lists.add(fresh.id, l.items);
    await refreshMine(); return go(`list/${fresh.id}`);
  }
  if (d.deleteList) {
    if (!confirm('Delete this collection? The works stay in your Library.')) return;
    await Lists.remove(d.deleteList); await refreshMine(); return go('collection');
  }
  if (d.removeFromList) {
    await Lists.removeItems(d.removeFromList, [...S.selected]);
    S.selected.clear(); S.selecting = false; await refreshMine(); return route({ keepScroll: true });
  }
  if (d.saveWork) {
    const w = D.discover.works[d.saveWork];
    const on = await Favorites.toggle(d.saveWork, w ? { title: w.title, artist: w.artist, year: w.year, image: w.image, museum: w.museum, museumId: w.museumId, artistId: w.artistId } : null);
    await refreshMine();
    t.setAttribute('aria-pressed', String(on)); t.innerHTML = I.heart(on);
    return toast(on ? 'Saved to your Library' : 'Removed from Library');
  }
  if (d.more !== undefined) { t.previousElementSibling?.classList.remove('clamp'); t.remove(); return; }
  if (d.update !== undefined) return checkForUpdate(t);
}

let queryTimer;
function onInput(e) {
  if (e.target.id === 'museumQuery') {
    clearTimeout(queryTimer);
    queryTimer = setTimeout(() => {
      S.query = e.target.value; S.shown = PAGE_SIZE;
      const body = $('#museumsBody');
      if (S.museumsView === 'list' && body) { body.innerHTML = museumsListHTML(); }
      else route({ keepScroll: true });
    }, 180);
  }
}

function onChange(e) {
  if (e.target.matches('[data-lib-museum]')) { S.libMuseum = e.target.value; route({ keepScroll: true }); }
  if (e.target.matches('[data-lib-sort]')) { S.libSort = e.target.value; route({ keepScroll: true }); }
}

// "Add to Collection": choose one of your collections, or make a new one.
function pickList(ids) {
  const el = document.createElement('div');
  el.className = 'picker';
  el.innerHTML = `<div class="picker__panel" role="dialog" aria-label="Add to Collection">
    <h2>Add ${ids.length} to…</h2>
    <ul class="lib-list">${S.lists.map(l => `<li><button class="lib-row" type="button" data-to="${l.id}" style="grid-template-columns:1fr auto">
      <span><span class="lib-row__title">${escape(l.name)}</span><span class="lib-row__sub">${l.items.length} artworks</span></span>${I.chev}</button></li>`).join('')}</ul>
    <button class="btn more" type="button" data-to-new>${I.plus}New Collection</button>
    <button class="btn btn--plain more" type="button" data-cancel>Cancel</button></div>`;
  document.body.appendChild(el);
  el.addEventListener('click', async e => {
    if (e.target === el || e.target.closest('[data-cancel]')) return el.remove();
    let id = e.target.closest('[data-to]')?.dataset.to;
    if (e.target.closest('[data-to-new]')) {
      const name = prompt('Name your collection', '');
      if (!name?.trim()) return;
      id = (await Lists.create(name.trim())).id;
    }
    if (!id) return;
    await Lists.add(id, ids);
    el.remove();
    S.selected.clear(); S.selecting = false;
    await refreshMine();
    toast('Added to your collection');
    route({ keepScroll: true });
  });
}

// ---------- toast ----------
let toastTimer;
function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.add('toast--show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('toast--show'), 2400);
}

// ---------- updates (same service worker as the guide) ----------
async function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return;
  const hadController = !!navigator.serviceWorker.controller;
  let reloaded = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => { if (hadController && !reloaded) { reloaded = true; location.reload(); } });
  try {
    const reg = await navigator.serviceWorker.register('sw.js');
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') reg.update().catch(() => {}); });
  } catch { /* offline copy unavailable */ }
}

async function checkForUpdate(btn) {
  const reg = await navigator.serviceWorker?.getRegistration();
  if (!reg) return toast('Updates need an internet connection');
  btn.disabled = true; btn.textContent = 'Checking…';
  try {
    await reg.update();
    if (reg.installing || reg.waiting) { btn.textContent = 'Updating…'; return toast('New version found. Updating…'); }
    toast('You have the latest version');
  } catch { toast('Couldn’t check. Are you online?'); }
  btn.disabled = false; btn.textContent = 'Check for Updates';
}

// ---------- helpers ----------
function norm(s) {
  return String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}
function escape(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
