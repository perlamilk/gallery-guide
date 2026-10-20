// Loads data/floors.json and data/artworks.json and answers questions about them.
// The app never reads the JSON directly: everything goes through this module,
// so the data files can be regenerated (e.g. by a weekly scraper) without code changes.

import { FACILITIES } from './icons.js';

export async function loadData() {
  const [floorsDoc, artDoc, curiosities] = await Promise.all([
    fetchJSON('data/floors.json'),
    fetchJSON('data/artworks.json'),
    fetchJSON('data/curiosities.json').catch(() => null),
  ]);
  const museum = new Museum(floorsDoc, artDoc);
  museum.curiosities = new Curiosities(curiosities);
  return museum;
}

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Could not load ${url} (${res.status})`);
  return res.json();
}

// Lowercase, strip accents and punctuation: "Cézanne" -> "cezanne", "Van-Gogh" -> "van gogh".
export function normalize(s) {
  return String(s ?? '')
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

// The filters the browse menu offers, in the order they appear.
export const FILTERS = [
  { key: 'type', label: 'Type', all: 'All types' },
  { key: 'country', label: 'Country', all: 'All countries' },
  { key: 'period', label: 'Period', all: 'All periods' },
];

class Museum {
  constructor(floorsDoc, artDoc) {
    this.floors = [...floorsDoc.floors].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
    this.defaultFloor = floorsDoc.defaultFloor ?? this.floors.at(-1).id;
    this.meta = { checked: artDoc.checked, source: artDoc.source };

    // gallery id (and aliases) or space id -> { room, floor }
    this.rooms = new Map();
    this.spaces = [];
    this.facilities = [];
    for (const floor of this.floors) {
      for (const room of floor.rooms) {
        if (room.kind === 'gallery' || room.kind === undefined) {
          for (const id of [room.id, ...(room.aliases ?? [])]) this.rooms.set(id, { room, floor });
        } else if (room.kind === 'space') {
          this.rooms.set(room.id, { room, floor });
          this.spaces.push({ room, floor, _haystack: normalize(room.name) });
        }
      }
      for (const f of floor.amenities ?? []) this.facilities.push({ ...f, floor });
    }

    // doorways: room id -> set of room ids you can walk straight into (corridors included)
    this.links = new Map();
    this.kinds = new Map();
    for (const floor of this.floors) {
      for (const r of floor.rooms) this.kinds.set(r.id, r.kind);
      for (const d of floor.doors ?? []) {
        for (const [x, y] of [[d.a, d.b], [d.b, d.a]]) {
          if (!this.links.has(x)) this.links.set(x, new Set());
          this.links.get(x).add(y);
        }
      }
    }

    this.artworks = (artDoc.artworks ?? []).filter(a => a.onView !== false);
    for (const a of this.artworks) {
      a._haystack = normalize([a.title, a.artist, a.artistDetails, a.date, a.medium,
        a.type, a.country, a.period, a.culture, a.classification, a.collection, a.description].join(' '));
      a._artist = normalize(a.artist);
      // alcoves the map doesn't draw ("204A", "219.4") belong to their main gallery
      if (a.gallery && !this.rooms.has(a.gallery)) {
        const main = String(a.gallery).match(/^(\d+)[A-Za-z.]/)?.[1];
        if (main && this.rooms.has(main)) a.gallery = main;
      }
      a.floor = a.floor ?? this.rooms.get(a.gallery)?.floor.id ?? null;
    }

    this.byGallery = new Map();
    for (const a of this.artworks) {
      if (!a.gallery) continue;
      if (!this.byGallery.has(a.gallery)) this.byGallery.set(a.gallery, []);
      this.byGallery.get(a.gallery).push(a);
    }
  }

  floor(id) { return this.floors.find(f => f.id === id); }
  roomInfo(id) { return this.rooms.get(id) ?? null; }
  isMapped(galleryId) { return this.rooms.get(galleryId)?.room.kind !== 'space' && this.rooms.has(galleryId); }

  // Works in a room, including every gallery number that shares its shape on the map.
  worksIn(id) {
    const info = this.rooms.get(id);
    const ids = info ? [info.room.id, ...(info.room.aliases ?? [])] : [id];
    return ids.flatMap(g => this.byGallery.get(g) ?? []);
  }

  // The map's name for a room, or the name the collection uses for it.
  galleryName(id) {
    const info = this.rooms.get(id);
    return info?.room.name ?? this.worksIn(id).find(a => a.galleryName)?.galleryName ?? null;
  }

  // Where you can go from a room: galleries and named spaces behind its doorways, and the ones
  // reached by walking through the corridors it opens onto.
  connections(id) {
    const room = this.rooms.get(id)?.room;
    const start = room?.id ?? id;
    const direct = new Set();
    const viaCorridor = new Set();
    const seen = new Set([start]);
    let frontier = [];
    for (const n of this.links.get(start) ?? []) {
      seen.add(n);
      if (this.kinds.get(n) === 'corridor') frontier.push(n); else direct.add(n);
    }
    for (let depth = 0; depth < 4 && frontier.length; depth++) {
      const next = [];
      for (const c of frontier) {
        for (const n of this.links.get(c) ?? []) {
          if (seen.has(n)) continue;
          seen.add(n);
          if (this.kinds.get(n) === 'corridor') next.push(n); else viaCorridor.add(n);
        }
      }
      frontier = next;
    }
    const sort = set => [...set].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
    return { direct: sort(direct), viaCorridor: sort(viaCorridor) };
  }

  // Every query token must appear somewhere in the work's text.
  // A bare gallery number ("255", "gallery 241a") matches that room.
  // `filters`: { type, country, period } exact matches; empty values are ignored.
  search(query, filters = {}) {
    const q = normalize(query);
    const tokens = q ? q.split(' ').filter(t => t !== 'gallery') : [];
    const one = tokens.length === 1 ? tokens[0].toUpperCase() : null;
    const galleryHit = one && this.rooms.has(one) && this.rooms.get(one).room.kind !== 'space';
    if (!tokens.length && !hasFilters(filters)) return [];

    const results = this.artworks.filter(a => {
      if (!passesFilters(a, filters)) return false;
      if (galleryHit) return this.worksIn(one).includes(a);
      return tokens.every(t => a._haystack.includes(t));
    });

    // Artist-name matches first, then by gallery, then title.
    const artistFirst = a => (tokens.length && tokens.every(t => a._artist.includes(t)) ? 0 : 1);
    return results.sort((a, b) =>
      artistFirst(a) - artistFirst(b) ||
      String(a.gallery ?? '~').localeCompare(String(b.gallery ?? '~'), undefined, { numeric: true }) ||
      a.title.localeCompare(b.title));
  }

  // Places for a query: facility types ("restroom", "café", "banheiro") and named spaces ("courtyard").
  searchPlaces(query) {
    const q = normalize(query);
    if (q.length < 2) return [];
    const tokens = q.split(' ');
    const out = [];
    for (const [type, f] of Object.entries(FACILITIES)) {
      const words = normalize(`${f.label} ${f.words}`).split(' ');
      if (!tokens.every(t => words.some(w => w.startsWith(t)))) continue;
      const here = this.facilities.filter(x => x.type === type);
      if (!here.length) continue;
      const byFloor = new Map();
      for (const x of here) byFloor.set(x.floor.id, (byFloor.get(x.floor.id) ?? 0) + 1);
      out.push({ kind: 'facility', type, label: f.label, byFloor, count: here.length });
    }
    for (const s of this.spaces) {
      if (tokens.every(t => s._haystack.includes(t))) out.push({ kind: 'space', room: s.room, floor: s.floor });
    }
    return out;
  }

  facilitiesOfType(type) { return this.facilities.filter(f => f.type === type); }

  // Galleries (ids) that hold at least one of the given works, with counts.
  galleriesOf(works) {
    const counts = new Map();
    for (const a of works) if (a.gallery) counts.set(a.gallery, (counts.get(a.gallery) ?? 0) + 1);
    return counts;
  }

  // Values for one filter with how many works each has, given the other active filters.
  filterOptions(key, filters = {}) {
    const others = { ...filters, [key]: '' };
    const counts = new Map();
    for (const a of this.artworks) {
      if (!a[key] || !passesFilters(a, others)) continue;
      counts.set(a[key], (counts.get(a[key]) ?? 0) + 1);
    }
    const values = [...counts.entries()];
    if (key === 'period') values.sort((a, b) => periodKey(a[0]) - periodKey(b[0]));
    else values.sort((a, b) => a[0].localeCompare(b[0]));
    return values.map(([value, count]) => ({ value, count }));
  }

  // Artists with the most works, for the quick-pick chips.
  topArtists(n = 6) {
    const counts = new Map();
    for (const a of this.artworks) if (a.artist) counts.set(a.artist, (counts.get(a.artist) ?? 0) + 1);
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, n)
      .map(([name]) => shortArtist(name));
  }
}

const hasFilters = filters => Object.values(filters).some(Boolean);

function passesFilters(a, filters) {
  return Object.entries(filters).every(([key, value]) => !value || a[key] === value);
}

// "5th century B.C." -> -5, "19th century" -> 19, anything else sorts last
function periodKey(label) {
  const m = String(label).match(/(\d+)/);
  if (!m) return 999;
  return /B\.?C/i.test(label) ? -Number(m[1]) : Number(m[1]);
}

// "Rembrandt Harmensz. van Rijn" -> "Rembrandt"; "Claude Monet" -> "Monet"; "Vincent van Gogh" -> "Van Gogh".
export function shortArtist(name) {
  if (!name) return '';
  const known = {
    'Rembrandt Harmensz. van Rijn': 'Rembrandt',
    'Rosso Fiorentino (Giovanni Battista di Jacopo)': 'Rosso Fiorentino',
  };
  if (known[name]) return known[name];
  const clean = name.replace(/\s*\(.*\)\s*/g, ' ').trim();
  const m = clean.match(/\b(van|de|del|della|da|di|le|la)\s+\S+$/i);
  if (m) return m[0].replace(/^\w/, c => c.toUpperCase());
  if (/^El Greco/.test(clean)) return 'El Greco';
  return clean.split(' ').at(-1);
}

// Curiosities (data/curiosities.json) come in three layers, most specific first:
// facts about this very work, about its artist, and about the kind of object it is.
// Kinds are matched by rules, so newly harvested works pick them up without editing the file.
class Curiosities {
  constructor(doc) {
    this.works = doc?.works ?? {};
    this.artists = doc?.artists ?? {};
    this.kinds = (doc?.kinds ?? []).map(k => ({
      ...k,
      tests: Object.entries(k.match ?? {}).map(([field, re]) => [field, new RegExp(re, 'i')]),
    }));
  }

  for(a) {
    const out = [];
    const own = this.works[a.id];
    if (own?.length) out.push({ label: 'This Work', facts: own });
    const artist = this.artists[a.artist];
    if (artist?.facts?.length) out.push({ label: `About ${artist.name ?? a.artist}`, facts: artist.facts });
    const kind = this.kinds.find(k => k.tests.length && k.tests.every(([field, re]) => re.test(a[field] ?? '')));
    if (kind) out.push({ label: kind.title, facts: kind.facts });
    return out;
  }
}
