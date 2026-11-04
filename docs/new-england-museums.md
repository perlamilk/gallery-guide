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
