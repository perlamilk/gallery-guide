// Loads data/floors.json and data/artworks.json and answers questions about them.
// The app never reads the JSON directly: everything goes through this module,
// so the data files can be regenerated (e.g. by a weekly scraper) without code changes.

export async function loadData() {
  const [floorsDoc, artDoc] = await Promise.all([
    fetchJSON('data/floors.json'),
    fetchJSON('data/artworks.json'),
  ]);
  return new Museum(floorsDoc, artDoc);
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

class Museum {
  constructor(floorsDoc, artDoc) {
    this.floors = [...floorsDoc.floors].sort((a, b) => a.order - b.order);
    this.defaultFloor = floorsDoc.defaultFloor ?? this.floors.at(-1).id;
    this.meta = { checked: artDoc.checked, source: artDoc.source };

    // gallery id -> { room, floor }
    this.rooms = new Map();
    for (const floor of this.floors) {
      for (const room of floor.rooms) this.rooms.set(room.id, { room, floor });
    }

    this.artworks = (artDoc.artworks ?? []).filter(a => a.onView !== false);
    for (const a of this.artworks) {
      a._haystack = normalize([a.title, a.artist, a.artistDetails, a.date, a.medium,
        a.type, a.country, a.period].join(' '));
      a._artist = normalize(a.artist);
      a.floor = a.floor ?? this.rooms.get(a.gallery)?.floor.id ?? null;
    }

    this.byGallery = new Map();
    for (const a of this.artworks) {
      if (!this.byGallery.has(a.gallery)) this.byGallery.set(a.gallery, []);
      this.byGallery.get(a.gallery).push(a);
    }
  }

  floor(id) { return this.floors.find(f => f.id === id); }
  roomInfo(galleryId) { return this.rooms.get(galleryId) ?? null; }
  worksIn(galleryId) { return this.byGallery.get(galleryId) ?? []; }
  isMapped(galleryId) { return this.rooms.has(galleryId); }

  // Every query token must appear somewhere in the work's text.
  // A bare gallery number ("255", "gallery 241a") matches that room.
  // `filters` is reserved for later: { period, country, type } exact matches.
  search(query, filters = {}) {
    const q = normalize(query);
    if (!q) return [];
    const tokens = q.split(' ').filter(t => t !== 'gallery');
    const galleryHit = tokens.length === 1 && this.rooms.has(tokens[0].toUpperCase());

    const results = this.artworks.filter(a => {
      if (!passesFilters(a, filters)) return false;
      if (galleryHit) return a.gallery === tokens[0].toUpperCase();
      return tokens.every(t => a._haystack.includes(t));
    });

    // Artist-name matches first, then by gallery, then title.
    const artistFirst = a => (tokens.every(t => a._artist.includes(t)) ? 0 : 1);
    return results.sort((a, b) =>
      artistFirst(a) - artistFirst(b) ||
      a.gallery.localeCompare(b.gallery, undefined, { numeric: true }) ||
      a.title.localeCompare(b.title));
  }

  // Galleries (ids) that hold at least one of the given works, with counts.
  galleriesOf(works) {
    const counts = new Map();
    for (const a of works) counts.set(a.gallery, (counts.get(a.gallery) ?? 0) + 1);
    return counts;
  }

  // Artists with the most works, for the quick-pick chips.
  topArtists(n = 6) {
    const counts = new Map();
    for (const a of this.artworks) counts.set(a.artist, (counts.get(a.artist) ?? 0) + 1);
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, n)
      .map(([name]) => shortArtist(name));
  }
}

function passesFilters(a, filters) {
  return Object.entries(filters).every(([key, value]) => !value || a[key] === value);
}

// "Rembrandt Harmensz. van Rijn" -> "Rembrandt"; "Claude Monet" -> "Monet"; "Vincent van Gogh" -> "Van Gogh".
export function shortArtist(name) {
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
