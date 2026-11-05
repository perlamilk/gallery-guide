# Museums in Massachusetts, Rhode Island and Connecticut

The plan for adding guides (works, and later maps) for every museum in the three states.
Guides are built with `tools/build_guides.py` from open data only (Wikidata, and museum APIs where they exist).

Status (Nov 4, 2026): batch 1 is built from Wikidata for 8 of its 10 museums. The ICA Boston (1 work) and MASS MoCA (0 works) have too little open data, so `build_guides.py` gives them no guide (MIN_WORKS). Harvard has Wikidata works only, without galleries, until the build runs with HARVARD_API_KEY.

Batch 2 (Nov 4, 2026): guides for Peabody Essex, Norman Rockwell, New Britain, Mead, Davis and D'Amour. Williams College, Hill-Stead, Lyman Allyn, Rose, Boston Athenæum and the Aldrich have under 20 works in Wikidata, so they get no guide until better open data turns up.

## How a museum gets a guide

1. `python3 tools/build_guides.py --batch N` writes `data/guides/<id>.json` and adds it to `data/guides.json`.
2. The museum's page in the app shows **In the Collection**: search by artist, title or gallery; **On View** when the museum's own data says so.
3. Bump `VERSION` in `sw.js`.

Worcester Art Museum (Nov 4, 2026): map guide at `guide.html?museum=worcester`. The floor plan is traced by
`tools/trace_worcester.py` from the museum's visitor map PDF (worcesterart.org/visit/floor-map/), an isometric drawing
turned back into flat plans (Ground Level and Levels 1–4, 47 numbered rooms, elevators, stairs, restrooms, café, shop,
coat rooms, entrances). Works come from Wikidata through `tools/build_worcester.py`: 1,500 in the collection, 835 placed
in their likely gallery by date and origin (the app says it's a guess and that the work may not be on view). The museum's
own collection site (worcester.emuseum.com) has a Cloudflare bot check, so it isn't read; on-view data would need the
museum's permission or a data export.

Isabella Stewart Gardner Museum (Nov 4, 2026): map guide at `guide.html?museum=gardner`, built by
`tools/build_gardner_map.py`. The rooms are read off the museum's visitor map PDF (gardnermuseum.org, "ISGM_Map_English
9.30.26.pdf"), which draws every floor flat: Floors 1–3 of the Palace and Floors 1–2 of the New Wing (entrance, tickets,
café, store, coat check, Calderwood Hall, Hostetter Gallery), joined by the walkway on Floor 1. Works: the 425 in Wikidata;
399 are placed in their exact room, because the museum's object numbers name the room (P21w27 = room 21, the Dutch Room,
west wall). The 1990 theft is noted on the stolen works (empty frames still hang). The collection site
(gardnermuseum.emuseum.com) and object pages have a Cloudflare bot check, so they aren't read; the museum holds about
7,500 objects in all.

Clark Art Institute (Nov 4, 2026): map guide at `guide.html?museum=clark`, built by `tools/build_clark.py`. The plan comes
from the Clark's visitor map PDF (clarkart.edu/getmedia/614f36ad-…/A-4547-8-5x14-Gallery-Closure-map_8-26.pdf, Aug 2021;
the only edition the cloud can download, since clarkart.edu pages sit behind a Cloudflare check). It is flat: Main Level
(Clark Center entrance, admissions, store; Museum Building galleries 1–20; Manton Research Center with British art, the
Thaw works-on-paper gallery, reading room, library), Lower Level (special exhibitions, Café 7, coat check, restrooms) and
Upper Level (American decorative arts, glass). Gallery numbers 1 and 5–14 were hidden under green "closed" shading and were
read from the PDF's text layer. Works: 563 of the 603 in Wikidata, placed in the gallery whose subject on the map fits
their artist, date and country (Degas → 14, Alfred Stevens → 15, Renoir → 2, British → Manton, works on paper → Thaw…),
each with a note that the gallery is a guess.

RISD Museum (Nov 4, 2026): map guide at `guide.html?museum=risd`, built by `tools/build_risd.py`. risdmuseum.org sits
behind a Cloudflare block (from the cloud and from Grazi's Mac too), so the plan comes from copies of the museum's own maps
on all-maps.com: the 2020 "Floor 3 & 4" plan (image-only PDF; Benefit Street entrance, Café Pearl, Farago Wing, Radeke
Building, bridge, Chace Center special exhibitions) and the 2018 section map, which says what is on each floor of each
building and where the elevators, restrooms, coat check and entrances are. Floors 1, 2 (Chace Center: North Main Street
entrance, RISD Works, Metcalf Auditorium, Gelman student galleries) and 5, 6 (Grand Gallery, European, Greek and Roman,
Egyptian, Asian, Costume and Textiles, Pendleton House) are laid out by hand inside the same building outlines and say on
the map that they are approximate. Works: 1,465 of the ~1,900 in Wikidata (almost all paintings), placed by date, country
and type; works with no date use the artist's birth year + 35; each says the gallery is a guess.

Peabody Essex Museum (Nov 4, 2026): map guide at `guide.html?museum=pem`, built by `tools/build_pem.py`. The plan is PEM's
2024 visitor map (a vector PDF, copy on all-maps.com): Ground Level, Level 2 and Level 3 with gallery numbers 100–305,
entrances (Main, Charter Street, Groups), Atrium Café, shops, coatroom, restrooms, elevators and stairs. Rooms are drawn by
hand over it; Level 2 and 3 are moved up so the elevators line up. Only the east elevator (by Maritime Art) reaches
Fashion and Design on Level 3, and the map says so. Works: 279. pem.org is readable from the cloud: the collection pages'
highlights ("On view in the Byrne Family Gallery of Maritime Art") and the ongoing gallery pages give 132 works in a gallery
named by PEM, with PEM's pictures; the rest are highlights placed in the gallery of their collection area, and Wikidata's
works placed by subject, each with a note. Pages are cached in `.cache/pem` (one request every 2 s; `--refresh` re-reads).

Yale Center for British Art (Nov 4, 2026): map guide at `guide.html?museum=ycba`, built by `tools/harvest_ycba.py` +
`tools/build_ycba.py`. The works are exact: the museum's collection search (collections.britishart.yale.edu, CC0 records)
has an "On view" filter (about 550 works) and lists each work's exhibitions, so the current displays say the floor: the
John Constable exhibition fills floor 2, "Sightlines" (photography) floor 3, the "In a New Light" rehang and the Long
Gallery (408) floor 4. Pictures and details come from each work's IIIF manifest. The map follows Louis Kahn's published
plans (ground, second and third floors; 20-foot bays, Entrance Court and Library Court); the rooms inside each floor
and the lower level (restrooms, lockers) are drawn by us and labelled approximate. Within floor 4 the room is a guess
from the work's date. No café inside (Atticus Bookstore Café is in the building's Chapel Street shops).

Yale University Art Gallery (Nov 4, 2026): map guide at `guide.html?museum=yale`. `tools/harvest_yale.py` reads the
Gallery's own "What's On View by Floor" lists (linked from artgallery.yale.edu/permanent-collection, 24 works a page, one page
every 2 s) and each work's CC0 Linked Art record on media.art.yale.edu (date, medium, size, credit line, description);
`tools/build_yale.py` turns that cache into `data/yale/`. Works are exact: about 3,960 on view, each in the gallery the
Gallery names; pictures are the Gallery's own thumbnails (media.collections.yale.edu, loaded online). The site turns away
Python's HTTP client, so the harvester calls plain curl. The map is approximate: the only floor plan is in the Smartify app
(app.smartify.org blocks automated reading), so the lower lobby and floors 1–4 of the Kahn building, the Old Yale Art Gallery
and Street Hall (across High Street, by the floor-2 bridge) are drawn from the Gallery's descriptions and turned a quarter so
Chapel Street runs down the left. A photo of the Smartify floor plans would let the rooms be placed properly.
MASS MoCA (Nov 4, 2026): map guide at `guide.html?museum=massmoca`, built by `tools/build_massmoca.py`. MASS MoCA
has no collection: what it shows are long-term installations and exhibitions. The map is the museum's own October 2026
visitor map (vector PDF behind the map link on massmoca.org/visit, hosted on indd.adobe.com); building outlines,
restrooms, elevators and stairs are read from it, seasonal galleries, courtyards and paths are drawn over it. Works
(123): all 88 wall drawings of the Sol LeWitt retrospective (Building 7; floor from the year, since it runs in order)
and 35 installations and exhibitions in the building the map lists. massmoca.org pages sit behind a Cloudflare check,
so they were read once by hand into `tools/data/massmoca_works.tsv`; pictures come from its uploads folder and are
saved smaller in `data/massmoca/images/`. Seasonal galleries (Kiefer, Boiler House, Mary Lum) reopen in May.

ICA Boston (Nov 4, 2026): map guide at `guide.html?museum=ica`, built by `tools/harvest_ica.py` + `tools/build_ica.py`.
All the galleries are on the 4th floor; that floor is traced from the ICA's own gallery map (ica-gallery-map.png on
icaboston.org). The ICA publishes no plan of floors 1–3, so they are drawn from its descriptions of the building (lobby,
visitor center, store, Wine + Coffee Bar, Art Lab, Fineberg Art Wall, restrooms on 1 and 4, theater on 2–3) and the map says
they are approximate. Works: icaboston.org is readable from the cloud; the collection search loads from
`wp-admin/admin-ajax.php?action=fetch_artworks` (all ~400 works, 16 a page) and each work page has year, materials,
dimensions, credit, accession and a text. Exhibition pages name their gallery, so works pictured there go in it; 90 YEARS —
Beyond the Galleries names one work per floor; works given by Fotene Demoulas and Tom Coté go in To My Best Friend with a
note. The museum page lists the whole collection (`data/guides/Q3152226.json`, on view = in a current show). Shows change
often: re-run both scripts (with `--refresh`) and update `EXHIBITIONS`/`BEYOND` in build_ica.py when they do.
New Britain Museum of American Art (Nov 4, 2026): map guide at `guide.html?museum=nbmaa`, built by
`tools/build_nbmaa.py`. The museum publishes no floor plan. The building's real outline (Chase Family Building, west wing,
Landers House) is traced from the grounds map in its family guide PDF (nbmaa.org/pdfs/Sculpture-Garden-Tour-2024…pdf);
the rooms inside are laid out by hand and the map says so: Main Floor (Lexington Street entrance, lobby, café, store, Benton
murals, Colonial, Hudson River School, 19th century and Impressionism, Landers House, west-wing exhibitions) and Upper Floor
(Early Modernism, Regionalism, Post-War, McKernan Gallery, Sol LeWitt, Low Illustration, exhibitions). Works come from the
museum's own collection site, ink.nbmaa.org (eMuseum, reachable from the cloud), read politely by
`tools/harvest_nbmaa.py` (12 works a page, 1.5 s apart, so a full run takes a couple of hours). There is no on-view data:
works in the museum's themed highlight sets go to that period's gallery, the rest by date and medium, each with a note.
Pictures load from ink.nbmaa.org as they are viewed; sw.js does not download them in bulk.
Smith College Museum of Art (Nov 4, 2026): map guide at `guide.html?museum=smith`, built by `tools/build_smith.py`.
All four floors (Lower Level, 1, 2, 3) are traced by hand from the museum's own map
(scma.smith.edu/sites/default/files/SCMA_General_Map_for_Website_0.jpg, linked from /visit), so rooms, entrance, restrooms,
baby changing, shop, coatroom/lockers and elevator are real; there is no café. SCMA has 29,000+ works, but the full
catalogue lives in the Five College Museums database, whose robots.txt blocks AI crawlers, so it is not read. Works on
the map are the ones pictured on each current show's page on scma.smith.edu, in that show's gallery (Coco Fusco and Painting
Nature name their gallery; the others are reasoned and the note says so). The museum page also lists the Highlights
pages' works and the ~100 SCMA works in Wikidata, not placed. Shows change: update `SHOWS`/`SHOW_WORKS` and re-run.
SCMA was missing from museums.json (its Wikidata type isn't one build_open_data.py asks for); `EXTRA` in
tools/visit_info.py adds it back after any rebuild.

deCordova Sculpture Park and Museum (Nov 4, 2026): map guide at `guide.html?museum=decordova`, built by
`tools/build_decordova.py`. The indoor galleries are closed for renovation, so the guide is the 30-acre park. The map is
traced from deCordova's own Summer 2026 park map (a vector PDF on thetrustees.org); the 53 numbered circles are read from
the PDF's text, so every number sits where the museum prints it, and each sculpture is filed under the lawn or garden
around it. Each sculpture's picture, medium, size, credit line and text come from its page on thetrustees.org (linked
from /content/decordovasculpturepark). Nature Sanctuary (works marked * on the map) ended Oct 4, 2026; those works say
they may have left. When a new park map comes out, update `MAP_PDF` and `MAP_LIST` and re-run.
Addison Gallery of American Art (Nov 4, 2026): not in Wikidata's museum list, so `tools/visit_info.py` adds it (`ADD`,
Q4681251). Map guide at `guide.html?museum=addison`, built by `tools/build_addison.py`, traced from the museum's own gallery
maps (addison.andover.edu/visit/gallery-map: Level 1 and Level 2 from September 2026, Lower Level from 2023) and its Fall
2026 visitor guide PDF (coatroom, water, accessible restroom, main entrance). Works come from the museum's collection search
(an EmbARK kiosk shown through addison.andover.edu/search-the-collection/?embark_query=…; accessaddison.andover.edu itself
refuses direct reading), read by `tools/harvest_addison.py`: every work in the current show's portfolio (America in the
Making, portfolio 2600) and the ship models (212). The museum names the gallery range of each section of the show; the room
within a section is guessed from date and medium (each work says so), except works the gallery map pins to a room. When the
next season opens, add its portfolio number to `PORTFOLIOS` and the room ranges to build_addison.py. The collection has 29,000+
works; only the ones on view are in the guide. Pictures load from accessaddison.andover.edu as they are viewed.
Davis Museum at Wellesley College (Nov 4, 2026): map guide at `guide.html?museum=davis`, built by `tools/build_davis.py`.
The map is approximate: the Davis hands out a paper gallery map but publishes no floor plan, so the five public floors (Lower
Level, 1, 2, 4, 5; floor 3 has no galleries) are drawn inside the building's real outline from OpenStreetMap, following the
museum's own description of each floor (building page, 2016 reinstallation press release, visit and accessibility pages).
The collection site (davis.emuseum.com) and the Bloomberg Connects guide refuse cloud machines, so works come from the
Davis's pages on Google Arts & Culture (read by `tools/harvest_davis.py`, robots.txt allows it), Wikidata and the two
current shows (Excavating Antioch, Shi: Stories in Stone, through May 30, 2027). Each work sits in the gallery for its date
and origin and says it may be in storage. To improve: a photo of the paper gallery map, or on-view data from the museum.

Mead Art Museum (Nov 4, 2026): map guide at `guide.html?museum=mead`, built by `tools/build_mead.py`. www.amherst.edu shows a
CAPTCHA to every script (even from Grazi's Mac), so the Mead's pages were read from Internet Archive copies, fetched on the Mac
into `.cache/mead/raw` (a temporary `mead-raw` branch carried them to the cloud). The Mead publishes no floor plan: the one
gallery floor is APPROXIMATE, from the OpenStreetMap outline, the architects' 1948 plan on Wikimedia Commons and the
accessibility page (Fairchild Gallery, restrooms, coat room, entrance). Works on the map: the 8 named works of "My beautiful,
pitiful age" (Aug 25, 2026 – Jan 3, 2027; gallery guessed as the Fairchild), the Rotherwas Room and its stained glass, the
Assyrian relief. The collection list adds Collection Highlights, Mead files on Wikimedia Commons and Wikidata (103 works).
The full catalogue (Five College Museums database, 20,000+ works) blocks AI crawlers and is not read. When the spring show
(Anchors and Aspirations, Feb 23 – Jul 3, 2027) opens, update `SHOW_WORKS` and re-run.
Florence Griswold Museum, Old Lyme (Nov 4, 2026): map guide at `guide.html?museum=flogris`, built by `tools/build_flogris.py`.
The grounds are traced from the museum's numbered campus map (flogris.org/visit/museum-campus, 2025): Griswold House,
Krieble Gallery with Café Flo, Artists' Trail, gardens, Rafal Landscape Center, Chadwick Studio, Hartman Education Center,
parking. The rooms inside the Krieble Gallery and the two House floors are approximate (from the museum's descriptions and its
Matterport tours). The collection database (EmbARK kiosk, collections.flogris.org) disallows robots everywhere but its home
page, so works come from the museum's own WordPress pages: the dining-room painted panels (exact, always on view; door panels
in the rooms their picture names), the works pictured on the two ongoing shows' pages, the Collections Highlights and Hartford
Steam Boiler pages (via /wp-json/wp/v2/avada_portfolio) and Wikidata. Changing shows in the Krieble Gallery aren't listed
(Patchwork closes Nov 8, 2026); add the next show's works when its page is up.

Hill-Stead Museum (Nov 4, 2026): map guide at `guide.html?museum=hillstead`, built by `tools/harvest_hillstead.py` (Google
Arts & Culture) and `tools/build_hillstead.py`. hillstead.org answers 403 (Cloudflare) and its robots.txt shuts out AI
crawlers, so it is not read. Map: floor G (grounds) from OpenStreetMap (house and barn outline, Sunken Garden, parking,
drive, Riddle's Pond); the renovated Carriage Barn is the visitor center (Museum Shop/tickets, lockers, restrooms, exhibition
gallery), places inside it approximate. House floors 1 and 2 traced from the plans in Hill-Stead's illustrated museum guide
(reproduced on bigoldhouses.blogspot.com, 2013), drawn as in the book (south at the top) and moved over the house on the
grounds map. Works: 27 from Google Arts & Culture + 5 more from Wikidata (32 on the map, 29 pictures). The house stays as
Theodate Pope Riddle left it, so all works are on view; rooms come from Side of Culture (May 2022) and Galerie captions,
and 13 rooms are guesses, marked on each work. To improve: Hill-Stead's own room list, or a photo of a tour handout.
Mystic Seaport Museum, Mystic (Nov 4, 2026): map guide at `guide.html?museum=mystic`, built by `tools/build_mystic.py`.
The 19-acre grounds are traced from the museum's 2026 Map & Guide PDF (mysticseaport.org/visit/mystic-seaport-museum-map):
every numbered building is placed by the number the PDF's own text gives, outlines and walks are drawn by eye, and the
Charles W. Morgan, Joseph Conrad, L. A. Dunton, Sabino, Emma C. Berry, Fire Fighter and Kingston II sit at their berths.
Upper floors of the exhibition buildings aren't drawn. Works: the online catalogue (mobius.mysticseaport.org) says nothing
about what is on view and has few pictures, so the guide lists the historic vessels, the Seaport Village buildings and the
exhibitions now open, from the museum's WordPress pages (robots.txt crawl delay 10 s). Monstrous closes Jan 10, 2027 and
Brickwrecks Mar 14, 2027: re-run when the exhibitions change.
Newport Art Museum, Newport (Nov 4, 2026): map guide at `guide.html?museum=newport`, built by `tools/harvest_newport.py`
and `tools/build_newport.py`. The museum publishes no floor plan. The campus comes from OpenStreetMap; the Griswold
House's ground floor is traced from the Historic American Buildings Survey's measured plan (HABS RI-322, 1969-70, on
Wikimedia Commons). Drury (old dining room), Library, Parlor and Corridor galleries are known; Ilgenfritz, Wright,
Studio, Damon and Blue Room placements, the Cushing building's rooms and the lobby's desk, shop and restrooms are
guesses, marked on the map. Upper floor not drawn. Works: the five shows now on view and the museum's own Cushing
paintings, from newportartmuseum.org (WordPress, robots.txt crawl delay 10 s); only Rediscoveries (Cushing Gallery) and
Unfurling (Griswold House) name their gallery. Plus 60 collection highlights on the museum page. Re-run when shows
change (Unfurling ends Dec 31, 2026; Isham Jan 4, Otero Jan 10, Play / Pretend Jan 31, 2027).

The Breakers, Newport (Nov 4, 2026): map guide at `guide.html?museum=breakers`, built by `tools/harvest_breakers.py`
(the Preservation Society's Digital Collections site, newportmansions.rediscoverysoftware.com, through the JSON service its
own pages use; the server drops connections now and then, so the script retries slowly) and `tools/build_breakers.py`.
Map: floor G (grounds, Welcome Center, Caretaker's and Children's Cottages, parking, Cliff Walk) from OpenStreetMap; floors
1 and 2 traced from the floor plans in the National Register nomination (preservation.ri.gov PDF, pages 35-36), ocean side
at the top; basement (Museum Store, restrooms) only as an outline with approximate places. Works: 61 objects that name the
house or came down from Cornelius Vanderbilt II / Countess Széchényi; 25 placed (room from the record, or a portrait in its
sitter's bedroom, marked as a guess), the rest listed on the museum page without a room.

Marble House, Newport (Nov 4, 2026): map guide at `guide.html?museum=marble`, built by `tools/harvest_marble.py` (the
same Preservation Society Digital Collections service as The Breakers) and `tools/build_marble.py`. Map: floor G (grounds,
parking across Bellevue Avenue, Chinese Tea House, Cliff Walk) from OpenStreetMap; floors 1 and 2 traced from Richard
Morris Hunt's 1889 office-copy plans at the Library of Congress (LCCN 2024633241 first story, 2017648779 second story),
ocean side at the top; the plan's Grand Salon/Library/Morning Room are today's Gold Room/Gothic Room/Library; bedroom
owners on floor 2 read from the plan (approximate); basement (store, restrooms) as an outline with approximate places.
Works: 30 objects that name the house or came from Alva Belmont / Frederick H. Prince; 10 placed (9 guessed, marked).

The Elms, Newport (Nov 4, 2026): map guide at `guide.html?museum=elms`, built by `tools/harvest_elms.py` (the same
Preservation Society Digital Collections service) and `tools/build_elms.py`. Map: floor G (grounds, parking by the house,
Bellevue Court bus parking, Sunken Garden, Carriage House Café) from OpenStreetMap; floors 1, 2 and 3 traced from the 1994
measured plans in the National Historic Landmark nomination (preservation.ri.gov newp_bellevue-avenue_the-elms.pdf, pages
19, 20, 25; page 21 is a sketch map of the grounds with a statuary list), turned so north is up; basement (restrooms) as an
outline with approximate places. The house reopens Nov 16, 2026 as "The Elms Experience" (timed tickets), whose route
isn't published yet. Works: objects that name the house or came from the Berwinds (gifts from the Edward J. Berwind II
family are left out); some placed from their records or the statuary list, a few guessed (marked).

Rosecliff, Newport (Nov 4, 2026): map guide at `guide.html?museum=rosecliff`, built by `tools/harvest_rosecliff.py` (the
same Preservation Society Digital Collections service) and `tools/build_rosecliff.py`. Map: floor G (parking next to the
house, the drive, the rose garden, the lawn to the Cliff Walk) from OpenStreetMap, estate boundary approximate; floors 1
and 2 traced from Stanford White's own 1902 plans, plate 173 of "A Monograph of the Work of McKim, Mead & White" (vol. 2,
Internet Archive gri_33125006526137, page n154), turned so north is up. The 1972 National Register nomination has no
plans. Floor 2 is the exhibition floor today; basement (Museum Store, restrooms) as an outline with approximate places.
Works: objects that name the house or came from Theresa Fair Oelrichs or the J. Edgar Monroe family.

Mark Twain House & Museum, Hartford (Nov 4, 2026): map guide at `guide.html?museum=twain`, built by
`tools/build_twain.py`. Map: grounds from OpenStreetMap (parking at 385 Farmington Avenue and 65 Forest Street, the
paths, the Carriage House; gardens placed from the museum's garden pages, approximate); the house's basement and floors
1-3 traced from the Historic American Buildings Survey drawings (HABS CT-359, 1995, Library of Congress ct0332), turned
so north is up (on the sheets north is to the right). The Museum Center has no published plan: OpenStreetMap outline,
rooms placed from the museum's exhibit page (approximate). Works: the rooms and their famous features with HABS photos,
plus the Museum Center's permanent exhibits.

Maps: only the MFA has a 3D map, traced from its own PDF. Other museums don't publish floor plans as open data, so their guides start without a map.

Open APIs worth an adapter later: Harvard Art Museums (done, needs a free key), Yale University Art Gallery and Yale Center for British Art (LUX, open linked data), RISD Museum (collection site).

## Batch 1

- Harvard Art Museums — Cambridge, Massachusetts (`Q3783572`)
- Isabella Stewart Gardner Museum — Boston, Massachusetts (`Q49135`)
- Institute of Contemporary Art, Boston — Boston, Massachusetts (`Q3152226`)
- Worcester Art Museum — Worcester, Massachusetts (`Q847508`)
- Clark Art Institute — Massachusetts (`Q1465805`)
- MASS MoCA — Massachusetts (`Q588474`)
- RISD Museum — Providence, Rhode Island (`Q2148186`)
- Yale University Art Gallery — New Haven, Connecticut (`Q1568434`)
- Yale Center for British Art — New Haven, Connecticut (`Q6352575`)
- Wadsworth Atheneum — Hartford, Connecticut (`Q403080`)

## Batch 2

- Peabody Essex Museum — Salem, Massachusetts (`Q3373790`)
- Norman Rockwell Museum — Stockbridge, Massachusetts (`Q713204`)
- New Britain Museum of American Art — New Britain, Connecticut (`Q7005718`)
- Mead Art Museum — Amherst, Massachusetts (`Q6803132`)
- Williams College Museum of Art — Williamstown, Massachusetts (`Q12072937`)
- Hill-Stead Museum — Farmington, Connecticut (`Q1618645`)
- Lyman Allyn Art Museum — New London, Connecticut (`Q14714982`)
- Rose Art Museum — Waltham, Massachusetts (`Q7367636`)
- Davis Museum — Wellesley, Massachusetts (`Q15694044`)
- D'Amour Museum of Fine Arts — Springfield, Massachusetts (`Q41512158`)
- Boston Athenæum — Boston, Massachusetts (`Q478013`)
- Aldrich Contemporary Art Museum — Connecticut, Connecticut (`Q4713992`)

## Later batches (art museums already in the app)

### Massachusetts

- Museum of Bad Art — Boston (`Q11643`)
- Fogg Museum — Cambridge (`Q809600`) (part of Harvard Art Museums)
- Busch–Reisinger Museum — Cambridge (`Q1017269`) (part of Harvard Art Museums)
- Fitchburg Art Museum — Massachusetts (`Q5455423`)
- Fuller Craft Museum — Massachusetts (`Q5508243`)
- Abbotsford — Boston (`Q4664294`)
- Berkshire Museum — Pittsfield (`Q4892280`)
- DeCordova Museum and Sculpture Park — Massachusetts (`Q2019741`)
- Art Complex Museum — Massachusetts (`Q4796749`)
- Eric Carle Museum of Picture Book Art — Massachusetts (`Q5386237`)
- Cyrus E. Dallin Art Museum — Arlington (`Q74035008`)
- George Walter Vincent Smith Art Museum — Springfield (`Q105553919`)
- Cahoon Museum of American Art — Massachusetts (`Q5017445`)
- McMullen Museum of Art — Massachusetts (`Q6802407`)
- Icon Museum and Study Center — Massachusetts (`Q6941007`)
- University Museum of Contemporary Art — Massachusetts (`Q7894833`)
- Danforth Museum — Framingham (`Q16954084`)
- Gallery East — Boston (`Q5518987`)
- Fall River Museum of Contemporary Art — Fall River (`Q138002039`)
- Cape Cod Museum of Art — Massachusetts (`Q14715429`)
- Museum of American Bird Art — Massachusetts (`Q18965051`)
- Boston Sculptors Gallery — Massachusetts (`Q4948083`)
- Lumen Eclipse — Massachusetts (`Q6703189`)
- New Salem Museum and Academy of Fine Art — New Salem (`Q140842682`)
- Lunder Arts Center — Cambridge (`Q123689395`)

### Rhode Island

- Annmary Brown Memorial — Rhode Island (`Q4769571`)
- National Museum of American Illustration — Rhode Island (`Q6974447`)
- Newport Art Museum — Newport (`Q7018775`)

### Connecticut

- Paul Mellon Arts Center — Wallingford (`Q7152453`)
- Housatonic Museum of Art — Connecticut (`Q5913507`)
- Ballard Institute and Museum of Puppetry — Storrs-Mansfield (`Q24534715`)
- Yale University Art Gallery Main Building — New Haven (`Q131342274`)
- Artspace — Connecticut (`Q4801555`)
- University of Saint Joseph Art Gallery — Hartford (`Q18325686`)

## Not in the app yet

`data/museums.json` lists art museums only (57 in the three states, with the MFA). History, science, maritime, children's and house museums are added with `python3 tools/build_guides.py --region`, then get guides in later batches.

Norman Rockwell Museum (Nov 4, 2026): map guide at `guide.html?museum=nrm`, built by `tools/harvest_nrm.py` +
`tools/build_nrm.py`. nrm.org and collection.nrm.org answer 403 to cloud machines (bot check), and the Internet
Archive can't be reached from the cloud, so no floor plan from the museum was seen. The map is APPROXIMATE and says so:
the grounds (lawn, drive, parking, terrace with the summer Terrace Café, Linwood House, Rockwell's Studio and the walk to
it) and the building's outline come from OpenStreetMap; inside, the Main Level (entrance hall, octagonal Four Freedoms
gallery under the cupola, Rockwell galleries north and south, Museum Store, terrace door) and the Lower Level
(exhibition galleries, restrooms) follow descriptions of the Stern building. Works come from the museum's pages on
Google Arts & Culture and Wikidata: 34 Rockwell paintings and studies on the map (the Four Freedoms in their gallery,
the others in a Rockwell gallery by date, marked as a guess), plus 41 archive photos, letters and other illustrators
on the museum page. Shows from Nov 14, 2026 (Exploring Calvin and Hobbes, The Human Touch) are named in the room
names; update `SHOWS` when they change. To improve: a photo of the museum's gallery map.

John F. Kennedy Presidential Library and Museum (Nov 4, 2026): map guide at `guide.html?museum=jfk`, built by
`tools/harvest_jfk.py` + `tools/build_jfk.py`. jfklibrary.org answers 403 to cloud machines and its robots.txt shuts
out AI agents, so the guide does not read it. The map is traced from I. M. Pei's published 1979 plans (Level 2,
Entrance Level: glass lobby, theater lobby, Theaters I and II, store at the foot of the tower; Level 1, Exhibit Level:
the galleries, the glass Pavilion, restrooms) and is APPROXIMATE: the exhibits were rebuilt in 1993, so which exhibit
is in which room follows visitors' accounts of the route. Works: 17 permanent exhibits in the order of the visit, plus
the 28 objects, photographs and papers the museum publishes on Google Arts & Culture, each in the gallery about its
subject and marked "may not be on view". To improve: a photo of the museum's paper map.

Museum of Science, Boston (Nov 4, 2026): map guide at `guide.html?museum=mos`, built by `tools/harvest_mos.py` +
`tools/build_mos.py`. mos.org is open to robots and lists every page in its sitemap. The map is traced from the
museum's own visitor map (October 2026, mos.org/visit/map): Level 2, Level 1 and the Lower Level with the Red, Green
and Blue Wings, restrooms, stairs, elevators, café, store, info desk, lockers, theaters. Walls are simplified; rooms
and amenities are where the museum puts them. Works: every current exhibit, live presentation and drop-in activity page
(each states its wing and level; past exhibits are left out), plus the theaters and the best-known things to see
(Van de Graaff generator, Foucault's Pendulum, Archimedean Excogitation, Apollo capsule, T. rex, Cliff the
Triceratops). Weems sculptures, the Washburn exhibit, Transportation, Faces of Science and the Rock Garden give only a
wing, so their room is a guess and says so. Seasonal "All Aboard! Trains" (Green Wing, Level 2) is not on the map yet.

New Bedford Whaling Museum (Nov 4, 2026): map guide at `guide.html?museum=nbwm`, built by `tools/harvest_nbwm.py` +
`tools/build_nbwm.py`. whalingmuseum.org pages answer 403 to scripts, but its robots.txt allows everything and the
WordPress REST API (`/wp-json/wp/v2/exhibition`, `/pages/<id>`) and `/wp-content/uploads/` answer normally. The
collection database (newbedford.emuseum.com) is behind a Cloudflare check and the Bloomberg Connects guide disallows
robots, so neither is used. The map is traced from the museum's own three-level map (2026 self-guide PDF; key from the
Visitors Guide PDF): Lobby & Lower Level, Main Level, Upper Level, all aligned to the Main Level picture (Upper x 1/0.76,
Lower x 1.5; the elevators line up). Captain Paul Cuffe Park outside is approximate. Works: the galleries and the
exhibitions on view, the whale skeletons (Kobo, Quasimodo, Reyna, the sperm whale), the Lagoda, the blue whale heart,
and the objects pictured with captions on the pages of the exhibitions on view. Forging Independence, Coquilla Nut
Carvings and Bristol County: Incarcerated are matched to the map's "Rotating Exhibition" rooms by guess and say so.
Upcoming: The State of Water (upper level, Nov 20, 2026), New Ecologies: May Babcock (Center Street Gallery, Nov 20);
Sailor's Valentines closes Nov 8, 2026.

Yale Peabody Museum (Nov 4, 2026): map guide at `guide.html?museum=ypm`, built by `tools/harvest_ypm.py` +
`tools/build_ypm.py`. peabody.yale.edu answers scripts and its robots.txt allows the pages used. The map is traced from
the museum's own floor plan (3 pages, dated Oct 3, 2025, the "Download Map (PDF)" link on /visit): Floors 1, 2 and 3 on
one frame, with restrooms, the all-gender restrooms, elevators, stairs, information desk, coatroom, lockers, store,
classrooms and staff-only areas. The wellness room is on the lower level, which the plan doesn't draw. Works: the
galleries and the cards (photo, text, catalogue number) on each page under /explore/exhibitions, plus the Stegosaurus.
The collection database (peabody.collections.yale.edu) is a JavaScript app behind CloudFront that blocks scripts.
Temporary shows are placed in the second-floor Special Exhibitions gallery by guess and say so; Spineless is in the
Student Gallery. Indigenous Connections / Mesoamerican & Andean Civilizations share one open room, split by guess.
Admission is free.

Harvard Museum of Natural History (Nov 4, 2026): map guide at `guide.html?museum=hmnh`, built by
`tools/harvest_hmnh.py` + `tools/build_hmnh.py`. hmnh.harvard.edu, mcz.harvard.edu, oeb.harvard.edu and
peabody.harvard.edu all answer scripts with 403 (Akamai), and the Wayback Machine is unreachable from the cloud. The map
is traced from the floor plan in the Harvard Museums of Science & Culture wayfinding brochure (July 2023, a PDF on
websites.harvard.edu): every gallery is on the third floor, with admissions and the shop at the top of the stairs from
26 Oxford Street, the elevator from the ground-level accessible entrance, restrooms, accessible restroom, water and the
way into the Peabody Museum. The plan is a diagram, so the map says it is approximate. Works: photos visitors took in the
galleries and shared on Wikimedia Commons (museum, Glass Flowers, minerals and meteorites categories, plus a file
search), read from the HTML pages because the Commons API rate-limits the cloud. Galleries are given by what each photo
shows (GALLERY_RULES); mammals, birds and arthropods without a clear gallery are marked as placed by guess.
Admission from July 1, 2026: adults $20, seniors $18, students and youth 3–18 $15.
