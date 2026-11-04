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
  harvard: {
    key: 'harvard', id: 'Q3783572', short: 'Harvard Art Museums', name: 'Harvard Art Museums',
    floors: 'data/harvard/floors.json', artworks: 'data/harvard/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-harvard.json', packKey: 'gg-pack-harvard',
    room: id => (/^\d{4}$/.test(id) ? `Gallery ${id}` : id),
    website: 'View on the Harvard Art Museums Website',
    official: false,
    flat: true,
  },
  worcester: {
    key: 'worcester', id: 'Q847508', short: 'Worcester Art Museum', name: 'Worcester Art Museum',
    floors: 'data/worcester/floors.json', artworks: 'data/worcester/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-worcester.json', packKey: 'gg-pack-worcester',
    room: id => (/^\d{4}$/.test(id) ? `Gallery ${id}` : id),
    website: 'View on Wikidata',             // the museum's own collection site blocks automated reading
    official: false,
    flat: true,
    blurb: 'Floor plans from the museum’s map, works from its collection in the gallery where they most likely hang, directions and your visit diary.',
  },
  gardner: {
    key: 'gardner', id: 'Q49135', short: 'The Gardner', name: 'Isabella Stewart Gardner Museum',
    floors: 'data/gardner/floors.json', artworks: 'data/gardner/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-gardner.json', packKey: 'gg-pack-gardner',
    room: id => id,                          // rooms have names (Dutch Room, Titian Room), not numbers
    website: 'View on the Gardner Website',
    official: false,
    flat: true,
    blurb: 'Floor plans of the Palace and the New Wing from the museum’s map, works in the room where Isabella placed them, directions and your visit diary.',
  },
  clark: {
    key: 'clark', id: 'Q1465805', short: 'The Clark', name: 'Clark Art Institute',
    floors: 'data/clark/floors.json', artworks: 'data/clark/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-clark.json', packKey: 'gg-pack-clark',
    room: id => (/^\d+$/.test(id) ? `Gallery ${id}` : id),
    website: 'View on Wikidata',             // the Clark's own collection site blocks automated reading
    official: false,
    flat: true,
    blurb: 'Floor plans of the Clark Center, the Museum Building and the Manton Research Center from the museum’s map, works in the gallery where they most likely hang, directions and your visit diary.',
  },
  risd: {
    key: 'risd', id: 'Q2148186', short: 'RISD Museum', name: 'RISD Museum',
    floors: 'data/risd/floors.json', artworks: 'data/risd/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-risd.json', packKey: 'gg-pack-risd',
    room: id => id,                          // galleries have names (Grand Gallery, Pendleton House), not numbers
    website: 'View on Wikidata',             // the museum's own collection site blocks automated reading
    official: false,
    flat: true,
    blurb: 'Floor plans of the Radeke Building, Pendleton House and the Chace Center from the museum’s maps, works in the gallery where they most likely hang, directions and your visit diary.',
  },
  pem: {
    key: 'pem', id: 'Q3373790', short: 'PEM', name: 'Peabody Essex Museum',
    floors: 'data/pem/floors.json', artworks: 'data/pem/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-pem.json', packKey: 'gg-pack-pem',
    room: id => (/^\d{3}$/.test(id) ? `Gallery ${id}` : id),
    website: 'View on the PEM Website',
    official: false,
    flat: true,
    blurb: 'Floor plans of all three levels from the museum’s map, works from PEM’s website in the gallery where they are shown, directions and your visit diary.',
  },
  ycba: {
    key: 'ycba', id: 'Q6352575', short: 'British Art Center', name: 'Yale Center for British Art',
    floors: 'data/ycba/floors.json', artworks: 'data/ycba/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-ycba.json', packKey: 'gg-pack-ycba',
    room: id => id,                          // displays and galleries have names, not numbers
    website: 'View on the YCBA Collection Site',
    official: false,
    flat: true,
    blurb: 'Floor plans of Louis Kahn’s building, every work the museum lists as on view on the floor where it hangs, directions and your visit diary.',
  },
};

export const SITE = SITES[new URLSearchParams(location.search).get('museum')] ?? SITES.mfa;
export const siteById = id => Object.values(SITES).find(s => s.id === id) ?? null;
export const guideURL = (site, hash = '') => `guide.html${site.key === 'mfa' ? '' : `?museum=${site.key}`}${hash ? `#${hash}` : ''}`;
