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
  yale: {
    key: 'yale', id: 'Q1568434', short: 'Yale Art Gallery', name: 'Yale University Art Gallery',
    floors: 'data/yale/floors.json', artworks: 'data/yale/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-yale.json', packKey: 'gg-pack-yale',
    room: id => id,                          // galleries have names (European Art, Dura-Europos), not numbers
    website: 'View on the Yale Art Gallery Website',
    official: false,
    flat: true,
    blurb: 'Every work the Gallery has on view, in the gallery it names, on approximate plans of the Kahn building, the Old Yale Art Gallery and Street Hall, with directions and your visit diary.',
  },
  massmoca: {
    key: 'massmoca', id: 'Q588474', short: 'MASS MoCA', name: 'MASS MoCA',
    floors: 'data/massmoca/floors.json', artworks: 'data/massmoca/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-massmoca.json', packKey: 'gg-pack-massmoca',
    room: id => id,                          // places are buildings and floors ("Building 6 · Floor 2"), not numbers
    website: 'View on the MASS MoCA Website',
    official: false,
    flat: true,
    blurb: 'Floor plans of every building on the campus from the museum’s map, what is on view in each one (with all 88 Sol LeWitt wall drawings), directions and your visit diary.',
  },
  ica: {
    key: 'ica', id: 'Q3152226', short: 'ICA', name: 'Institute of Contemporary Art, Boston',
    floors: 'data/ica/floors.json', artworks: 'data/ica/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-ica.json', packKey: 'gg-pack-ica',
    room: id => id,                          // galleries have donors' names, not numbers
    website: 'View on the ICA Website',
    official: false,
    flat: true,
    blurb: 'All four floors, with the galleries traced from the ICA’s own gallery map, the works in this season’s shows in the gallery where they hang, directions and your visit diary.',
  },
  nbmaa: {
    key: 'nbmaa', id: 'Q7005718', short: 'NBMAA', name: 'New Britain Museum of American Art',
    floors: 'data/nbmaa/floors.json', artworks: 'data/nbmaa/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-nbmaa.json', packKey: 'gg-pack-nbmaa',
    room: id => id,                          // galleries have names (Benton Murals, Landers House), not numbers
    website: 'View on the NBMAA Collection Site',
    official: false,
    flat: true,
    blurb: 'An approximate floor plan of both floors inside the building’s real outline, every work in the museum’s online collection in the gallery for its period, directions and your visit diary.',
  },
  smith: {
    key: 'smith', id: 'Q14715853', short: 'SCMA', name: 'Smith College Museum of Art',
    floors: 'data/smith/floors.json', artworks: 'data/smith/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-smith.json', packKey: 'gg-pack-smith',
    room: id => id,                          // galleries have names (Art Before 1800, Asian Art Gallery), not numbers
    website: 'View on the Five College Museums Site',
    official: false,
    flat: true,
    blurb: 'All four floors traced from the museum’s own map, with the entrance, restrooms, shop and elevators, the works in this season’s shows in the gallery where they hang, directions and your visit diary.',
  },
  decordova: {
    key: 'decordova', id: 'Q2019741', short: 'deCordova', name: 'deCordova Sculpture Park and Museum',
    floors: 'data/decordova/floors.json', artworks: 'data/decordova/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-decordova.json', packKey: 'gg-pack-decordova',
    room: id => id,                          // lawns and gardens of the park (Pondside, South Lawn), not numbers
    website: 'View on the deCordova Website',
    official: false,
    flat: true,
    blurb: 'The whole sculpture park from the museum’s own map, with every one of its 53 numbered sculptures on the lawn where it stands, Admission, the café, store and restrooms, directions and your visit diary. The indoor galleries are closed for renovation.',
  },
  addison: {
    key: 'addison', id: 'Q4681251', short: 'The Addison', name: 'Addison Gallery of American Art',
    floors: 'data/addison/floors.json', artworks: 'data/addison/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-addison.json', packKey: 'gg-pack-addison',
    room: id => (/^\d{3}$/.test(id) ? `Gallery ${id}` : id),
    website: 'View on the Addison Collection Site',
    official: false,
    flat: true,
    blurb: 'All three levels traced from the Addison’s own gallery map, every work in America in the Making and the ship models in the gallery where it hangs, directions and your visit diary.',
  },
  davis: {
    key: 'davis', id: 'Q15694044', short: 'The Davis', name: 'Davis Museum at Wellesley College',
    floors: 'data/davis/floors.json', artworks: 'data/davis/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-davis.json', packKey: 'gg-pack-davis',
    room: id => id,                          // galleries are named by what they hold (Ancient World, Study Gallery)
    website: 'View on Google Arts & Culture',
    official: false,
    flat: true,
    blurb: 'An approximate plan of the five public floors inside the building’s real outline, with the entrance, front desk, restrooms and Collins Café, the works the Davis shows online in the gallery for their period, the current shows, directions and your visit diary.',
  },
  mead: {
    key: 'mead', id: 'Q6803132', short: 'The Mead', name: 'Mead Art Museum',
    floors: 'data/mead/floors.json', artworks: 'data/mead/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-mead.json', packKey: 'gg-pack-mead',
    room: id => id,                          // galleries have names (Fairchild, Rotherwas Room), not numbers
    website: 'View on the Five College Museums Site',
    official: false,
    flat: true,
    blurb: 'The one gallery floor with the entrance, coat room, restrooms and baby changing (an approximate plan: the Mead publishes none), the works in this season’s Whitney Collection show, the Rotherwas Room and its stained glass, the Assyrian reliefs, directions and your visit diary.',
  },
  flogris: {
    key: 'flogris', id: 'Q5460633', short: 'FloGris', name: 'Florence Griswold Museum',
    floors: 'data/flogris/floors.json', artworks: 'data/flogris/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-flogris.json', packKey: 'gg-pack-flogris',
    room: id => id,                          // rooms are named (Dining Room, Niblack Gallery)
    website: 'More about this work',
    official: false,
    flat: true,
    blurb: 'The 12-acre campus traced from the museum’s own map, with the Krieble Gallery, Café Flo, restrooms, gardens and studios, plus both floors of the Griswold House: every painted panel in the dining room where the artists left it, the collection highlights, directions and your visit diary.',
  },
  hillstead: {
    key: 'hillstead', id: 'Q1618645', short: 'Hill-Stead', name: 'Hill-Stead Museum',
    floors: 'data/hillstead/floors.json', artworks: 'data/hillstead/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-hillstead.json', packKey: 'gg-pack-hillstead',
    room: id => id,                          // rooms are named (Drawing Room, Morning Room)
    website: 'More about this work',
    official: false,
    flat: true,
    blurb: 'The grounds with the visitor center, Museum Shop, restrooms, parking and the Sunken Garden, and both floors of the Pope-Riddle House traced from the museum’s own guidebook plans: Monet, Manet, Degas and Cassatt in the rooms where they hang, directions and your visit diary.',
  },
  mystic: {
    key: 'mystic', id: 'Q1890082', short: 'Mystic Seaport', name: 'Mystic Seaport Museum',
    floors: 'data/mystic/floors.json', artworks: 'data/mystic/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-mystic.json', packKey: 'gg-pack-mystic',
    room: id => id,                          // buildings and ships have names (Cooperage, Charles W. Morgan)
    website: 'More on the Museum’s website',
    official: false,
    flat: true,
    blurb: 'The 19-acre grounds traced from the museum’s own 2026 map, with every numbered building, the ships at their berths, restrooms, cafés and both entrances: the Charles W. Morgan and the other historic vessels, the Seaport Village trade shops and the exhibitions open now, directions and your visit diary.',
  },
  newport: {
    key: 'newport', id: 'Q7018775', short: 'Newport Art', name: 'Newport Art Museum',
    floors: 'data/newport/floors.json', artworks: 'data/newport/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-newport.json', packKey: 'gg-pack-newport',
    room: id => id,                          // galleries have names (Ilgenfritz Gallery, Cushing Memorial Gallery)
    website: 'More on the Museum’s website',
    official: false,
    flat: true,
    blurb: 'The lawn campus on Bellevue Avenue with the Griswold House’s ground floor traced from its 1969 measured plan and the Cushing Memorial Gallery, parking, entrances, the lobby and restrooms (some rooms approximate: the museum publishes no plan), the works in the five shows open now, directions and your visit diary.',
  },
  breakers: {
    key: 'breakers', id: 'Q1786400', short: 'The Breakers', name: 'The Breakers',
    floors: 'data/breakers/floors.json', artworks: 'data/breakers/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-breakers.json', packKey: 'gg-pack-breakers',
    room: id => id,                          // rooms are named (Great Hall, Music Room)
    website: 'More about this object',
    official: false,
    flat: true,
    blurb: 'The grounds with the Welcome Center (tickets, café, restrooms), parking and the Cliff Walk, and both floors on the house tour traced from the National Register floor plans, plus the basement store and restrooms: the Vanderbilts’ own furniture, portraits and tapestry in the rooms where they stand, directions and your visit diary.',
  },
  nrm: {
    key: 'nrm', id: 'Q713204', short: 'Rockwell Museum', name: 'Norman Rockwell Museum',
    floors: 'data/nrm/floors.json', artworks: 'data/nrm/artworks.json',
    tours: null, curiosities: null, notice: false,
    pack: 'data/pack-nrm.json', packKey: 'gg-pack-nrm',
    room: id => id,                          // galleries have names (Four Freedoms Gallery)
    website: 'More about this work',
    official: false,
    flat: true,
    blurb: 'The grounds with parking, the lawn, the terrace and Rockwell’s own Studio, and the Main and Lower Levels of the museum (approximate: drawn inside the building’s real outline): the Four Freedoms in their octagonal gallery under the cupola, Rockwell’s Saturday Evening Post covers and civil-rights paintings, directions and your visit diary.',
  },
};

export const SITE = SITES[new URLSearchParams(location.search).get('museum')] ?? SITES.mfa;
export const siteById = id => Object.values(SITES).find(s => s.id === id) ?? null;
export const guideURL = (site, hash = '') => `guide.html${site.key === 'mfa' ? '' : `?museum=${site.key}`}${hash ? `#${hash}` : ''}`;
