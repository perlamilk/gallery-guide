# Museums in New York

## The Museum of Modern Art (MoMA), Manhattan

Added Nov 6, 2026: map guide at `guide.html?museum=moma` (Wikidata Q188740), built by `tools/harvest_moma.py`,
`tools/trace_moma.py` and `tools/build_moma.py` (cache `.cache/moma`).

- **Works.** MoMA publishes its catalogue as open data (CC0) at github.com/MuseumofModernArt/collection. The files are
  in Git LFS: download them from `media.githubusercontent.com/media/MuseumofModernArt/collection/main/Artworks.json`.
  Each work on view has `OnView` = `"MoMA, Floor 5, 516"`, so every work sits in its real gallery. The export used here
  lists 1,511 works on view (9 at MoMA PS1 in Queens, left out). Pictures: each record's `ImageURL`
  (www.moma.org/media, 1024 px), fetched once 1.5 s apart and saved at 640 px. MoMA's web pages are behind a
  Cloudflare challenge from the cloud; the /media pictures and visit.moma.org (tickets, hours) are not.
- **Map.** Traced from MoMA's own 2025 visitor floor plans (floors 1-6 and the lower levels S, T1/T2 and M), as copied
  on all-maps.com (`MOMA-Museum-Map-2025-1..7-scaled.webp`). `trace_moma.py` floods each room from a hand-placed seed
  up to the drawn walls (OpenCV watershed) and writes `tools/data/moma-plan.json`; rooms in open gallery suites meet
  where the drawing has no wall, so those edges are approximate. Amenities (elevators, escalators drawn as stairs,
  stairs, restrooms, info desks, checkrooms, cafés, stores, the four street entrances) were read off the drawings in
  `build_moma.py`. Floor 6W (Terrace Café) is a squeezed side panel in MoMA's drawing; it is moved east so its elevator
  lines up with the west elevators below. The lower levels are three separate places drawn side by side; the Museum
  Store on level S cannot be routed to (its panel is not drawn to the building's scale).
- **Gallery themes** printed on the 2025 plan change often (the Oct 2026 data already differs), so galleries are named
  by number only.
- **Refresh:** delete `.cache/moma/Artworks.json`, run `harvest_moma.py` (new pictures only) and `build_moma.py`.
  If MoMA renumbers galleries, a work's gallery will be missing from the plan and `build_moma.py` stops with its name.
