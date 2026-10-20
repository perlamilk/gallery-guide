// Visit diary: the visit in progress and the saved visits, kept on the device (IndexedDB),
// so it works offline and survives closing the app. Nothing is sent anywhere.
//
// A visit: { id, startedAt, endedAt?, rooms: [{ id, floor, at }], snapshots?: { [floorId]: Blob } }

const DB = 'gallery-guide';
const STORE = 'visits';     // finished visits, by id
const ACTIVE = 'active';    // the one in progress, under the key 'current'
const FAVS = 'favorites';   // artwork id -> { id, at, work? } (work: details for works outside the MFA data)
const MUSEUMS = 'museums';  // favourite museums: Wikidata id -> { id, at }
const LISTS = 'lists';      // your collections: { id, name, at, items: [artwork id] }

let dbPromise;
function db() {
  dbPromise ??= new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 3);
    req.onupgradeneeded = () => {
      const d = req.result;
      if (!d.objectStoreNames.contains(STORE)) d.createObjectStore(STORE, { keyPath: 'id' });
      if (!d.objectStoreNames.contains(ACTIVE)) d.createObjectStore(ACTIVE);
      if (!d.objectStoreNames.contains(FAVS)) d.createObjectStore(FAVS, { keyPath: 'id' });
      if (!d.objectStoreNames.contains(MUSEUMS)) d.createObjectStore(MUSEUMS, { keyPath: 'id' });
      if (!d.objectStoreNames.contains(LISTS)) d.createObjectStore(LISTS, { keyPath: 'id' });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbPromise;
}

async function run(store, mode, fn) {
  const d = await db();
  return new Promise((resolve, reject) => {
    const t = d.transaction(store, mode);
    const req = fn(t.objectStore(store));
    t.oncomplete = () => resolve(req?.result);
    t.onerror = () => reject(t.error);
  });
}

export const Visits = {
  async active() {
    return (await run(ACTIVE, 'readonly', s => s.get('current'))) ?? null;
  },

  async start() {
    const visit = { id: `v${Date.now()}`, startedAt: new Date().toISOString(), rooms: [] };
    await run(ACTIVE, 'readwrite', s => s.put(visit, 'current'));
    // ask the browser to keep this data even when the phone is short on space
    navigator.storage?.persist?.().catch(() => {});
    return visit;
  },

  // Mark or unmark a room in the visit in progress; returns the updated visit.
  async toggle(visit, roomId, floorId) {
    const i = visit.rooms.findIndex(r => r.id === roomId);
    if (i >= 0) visit.rooms.splice(i, 1);
    else visit.rooms.push({ id: roomId, floor: floorId, at: new Date().toISOString() });
    await run(ACTIVE, 'readwrite', s => s.put(visit, 'current'));
    return visit;
  },

  async finish(visit, snapshots) {
    const done = { ...visit, endedAt: new Date().toISOString(), snapshots };
    await run(STORE, 'readwrite', s => s.put(done));
    await run(ACTIVE, 'readwrite', s => s.delete('current'));
    return done;
  },

  async discard() {
    await run(ACTIVE, 'readwrite', s => s.delete('current'));
  },

  async list() {
    const all = (await run(STORE, 'readonly', s => s.getAll())) ?? [];
    return all.sort((a, b) => b.startedAt.localeCompare(a.startedAt));
  },

  async get(id) {
    return (await run(STORE, 'readonly', s => s.get(id))) ?? null;
  },

  async remove(id) {
    await run(STORE, 'readwrite', s => s.delete(id));
  },
};

// Favourite artworks, newest first. `work` keeps title/artist/picture for works the app
// only knows from open data (Wikidata ids like "Q12418"), so they still show offline.
export const Favorites = {
  async list() {
    return (await this.entries()).map(f => f.id);
  },
  async entries() {
    const all = (await run(FAVS, 'readonly', s => s.getAll())) ?? [];
    return all.sort((a, b) => b.at.localeCompare(a.at));
  },
  async toggle(id, work = null) {
    const has = await run(FAVS, 'readonly', s => s.get(id));
    if (has) await run(FAVS, 'readwrite', s => s.delete(id));
    else {
      await run(FAVS, 'readwrite', s => s.put({ id, at: new Date().toISOString(), ...(work ? { work } : {}) }));
      navigator.storage?.persist?.().catch(() => {});
    }
    return !has;
  },
};

// Favourite museums (Wikidata ids), newest first.
export const MuseumFavorites = {
  async list() {
    const all = (await run(MUSEUMS, 'readonly', s => s.getAll())) ?? [];
    return all.sort((a, b) => b.at.localeCompare(a.at)).map(f => f.id);
  },
  async toggle(id) {
    const has = await run(MUSEUMS, 'readonly', s => s.get(id));
    if (has) await run(MUSEUMS, 'readwrite', s => s.delete(id));
    else await run(MUSEUMS, 'readwrite', s => s.put({ id, at: new Date().toISOString() }));
    return !has;
  },
};

// Your own collections of artworks ("Blues I loved", "For mom"…).
export const Lists = {
  async all() {
    const all = (await run(LISTS, 'readonly', s => s.getAll())) ?? [];
    return all.sort((a, b) => b.at.localeCompare(a.at));
  },
  async create(name) {
    const list = { id: `l${Date.now()}`, name, at: new Date().toISOString(), items: [] };
    await run(LISTS, 'readwrite', s => s.put(list));
    return list;
  },
  async add(id, ids) {
    const list = await run(LISTS, 'readonly', s => s.get(id));
    if (!list) return null;
    list.items = [...new Set([...ids, ...list.items])];
    await run(LISTS, 'readwrite', s => s.put(list));
    return list;
  },
  async removeItems(id, ids) {
    const list = await run(LISTS, 'readonly', s => s.get(id));
    if (!list) return null;
    list.items = list.items.filter(x => !ids.includes(x));
    await run(LISTS, 'readwrite', s => s.put(list));
    return list;
  },
  async remove(id) {
    await run(LISTS, 'readwrite', s => s.delete(id));
  },
};

export function duration(visit) {
  const ms = new Date(visit.endedAt ?? Date.now()) - new Date(visit.startedAt);
  const min = Math.max(1, Math.round(ms / 60000));
  return min < 60 ? `${min} min` : `${Math.floor(min / 60)} h ${String(min % 60).padStart(2, '0')}`;
}
