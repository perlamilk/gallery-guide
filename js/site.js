// Which museum the map guide (guide.html) shows. guide.html is MFA Boston; guide.html?museum=wadsworth
// is the Wadsworth Atheneum. Everything that differs between the two lives here, so the map, search,
// directions and visit diary code stays the same for both.

export const SITES = {
  mfa: {
    key: 'mfa', id: 'Q49133', short: 'MFA Boston', name: 'Museum of Fine Arts, Boston',
    floors: 'data/floors.json', artworks: 'data/artworks.json',
    tours: 'data/tours.json', curiosities: 'data/curiosities.json', notice: true,
    pack: 'data/pack-mfa.json', packKey: 'gg-pack-mfa',
    room: id => `Gallery ${id}`,           // how a room is called in the interface
    website: 'View on the MFA Website',
    official: true,
    flat: true,                            // 2D plan from above, like every museum (Grazi, Nov 2026)
  },
  wadsworth: {
    key: 'wadsworth', id: 'Q403080', short: 'The Wadsworth', name: 'Wadsworth Atheneum Museum of Art',
    floors: 'data/wadsworth/floors.json', artworks: 'data/wadsworth/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-wadsworth.json', packKey: 'gg-pack-wadsworth',
    room: id => id,                        // the map shows wings ("Avery 2"), not numbered galleries
    website: 'Search the Wadsworth Collection',
    official: false,
    flat: true,                            // a 2D plan from above: Grazi prefers it to the tilting 3D map
  },
};

export const SITE = SITES[new URLSearchParams(location.search).get('museum')] ?? SITES.mfa;
export const siteById = id => Object.values(SITES).find(s => s.id === id) ?? null;
export const guideURL = (site, hash = '') => `guide.html${site.key === 'mfa' ? '' : `?museum=${site.key}`}${hash ? `#${hash}` : ''}`;
