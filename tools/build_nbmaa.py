#!/usr/bin/env python3
"""Build the New Britain Museum of American Art map guide (run: python3 tools/build_nbmaa.py HARVEST.json).

    data/nbmaa/floors.json    two levels seen from above (a flat 2D plan)
    data/nbmaa/artworks.json  the museum's collection (from its own collection site) in the gallery where
                              each work most likely hangs

The map: the museum publishes no floor plan. The building's outline is traced from the grounds map in the
museum's own "Exploring the Grounds" family guide (nbmaa.org/pdfs/Sculpture-Garden-Tour-2024...pdf, page 3),
turned 14.5 degrees so the walls run square, in units of a quarter PDF point. Inside that outline the rooms
are laid out by hand from what the museum says about itself: the main entrance faces Lexington Street (the
"Boys of Summer" penguins stand opposite it), the LeWitt Family Staircase rises on the park side, Chihuly's
"Blue and Beyond Blue" hangs in the west wing, the Benton murals have a gallery of their own, the Landers
House (the 1911 house the museum started in) is joined at the north corner, and the permanent collection
runs chronologically: earlier American art on the main floor, modern and contemporary art upstairs. So the
rooms are approximate, and the guide says so.

The works: harvest_nbmaa.py reads ink.nbmaa.org (eMuseum). It has no "on view" data, so each work is put in
the gallery whose subject fits it (the museum's themed collections first, then date and medium).
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'nbmaa'
SOURCE = 'https://www.nbmaa.org/pdfs/Sculpture-Garden-Tour-2024-2-compressed_2024-02-07-174944_lhrd.pdf'
EMUSEUM = 'https://ink.nbmaa.org'


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# The building, traced from the grounds map (see above). Main block + west wing + Landers House.
LANDERS = [[476.3, -41.4], [486.8, -41.5], [486.3, -78.1], [591.3, -77.5], [592.5, 31.7], [477.4, 33.5]]
LINK = rect(486.0, 33.0, 522.0, 88.0)
CAFE = [[522.0, 87.2], [636.4, 68.0], [635.0, 160.0], [522.0, 160.0]]
HALL1 = [[440.0, 101.1], [522.0, 87.2], [522.0, 190.0], [440.0, 190.0]]
NW = [[343.5, 117.5], [440.0, 101.1], [440.0, 190.0], [337.5, 190.0]]
MIDWEST = [[310.0, 190.0], [440.0, 190.0], [440.0, 300.0], [273.5, 300.0], [273.5, 244.0], [310.0, 244.0]]
WEST_HALL = [[139.0, 333.0], [190.8, 330.4], [195.4, 289.1], [273.5, 278.5], [273.5, 300.0], [296.0, 300.0],
             [296.0, 372.0], [139.0, 372.0]]
WEST_SOUTH = [[139.0, 372.0], [295.6, 372.2], [292.0, 464.9], [264.5, 463.1], [261.0, 508.6], [139.8, 505.8]]

FLOOR_ROOMS = {
    '1': [
        ('Landers House', 'gallery', 'Landers House · the museum’s first home (1911) · ArtLab and changing shows', LANDERS),
        ('1-link', 'corridor', 'Passage to the Landers House', LINK),
        ('Museum Café', 'space', 'Museum Café', CAFE),
        ('Lobby', 'corridor', 'Lobby · main entrance · front desk · Sol LeWitt wall drawing', rect(522.0, 160.0, 635.2, 279.2)),
        ('Museum Store', 'space', 'Museum Store', rect(522.0, 279.2, 595.6, 339.5)),
        ('1-hall', 'corridor', 'Hall · LeWitt Family Staircase · elevator · restrooms', HALL1),
        ('Benton Murals', 'gallery', 'Thomas Hart Benton · The Arts of Life in America (1932)', rect(440.0, 190.0, 522.0, 339.5)),
        ('Colonial & Federal', 'gallery', 'Colonial and Federal America · 1700–1830', NW),
        ('Hudson River School', 'gallery', 'Hudson River School and 19th-century landscapes', MIDWEST),
        ('Gilded Age', 'gallery', '19th-century genre, sculpture and American Impressionism', rect(296.0, 300.0, 451.0, 371.0)),
        ('1-west-hall', 'corridor', 'West wing hall · Chihuly’s Blue and Beyond Blue', WEST_HALL),
        ('Special Exhibitions', 'gallery', 'Special exhibitions · west wing', WEST_SOUTH),
    ],
    '2': [
        ('2-hall', 'corridor', 'Upper hall · LeWitt Family Staircase · elevator · restrooms', HALL1),
        ('Early Modernism', 'gallery', 'Early Modernism · 1900–1945', [[522.0, 87.2], [636.4, 68.0], [635.2, 190.0], [522.0, 190.0]]),
        ('Regionalism', 'gallery', 'Social Realism and Regionalism', rect(522.0, 190.0, 635.2, 279.2)),
        ('Post-War', 'gallery', 'Post-War and Contemporary Art · 1945–2000',
         [[440.0, 190.0], [522.0, 190.0], [522.0, 279.2], [595.6, 279.2], [595.6, 339.5], [440.0, 339.5]]),
        ('Sol LeWitt', 'gallery', 'A Connecticut Legacy: Sol LeWitt', NW),
        ('McKernan Gallery', 'gallery', 'McKernan Gallery · art since 2000 and new media', MIDWEST),
        ('Low Illustration', 'gallery', 'Sanford B. D. Low Illustration Gallery', rect(296.0, 300.0, 451.0, 371.0)),
        ('2-west-hall', 'corridor', 'West wing upper hall', WEST_HALL),
        ('Upper Exhibitions', 'gallery', 'Special exhibitions · works on paper and photographs', WEST_SOUTH),
    ],
}
SHORT = {'Landers House': 'Landers House', 'Benton Murals': 'Benton', 'Colonial & Federal': 'Colonial',
         'Hudson River School': 'Hudson River', 'Gilded Age': '19th c.', 'Special Exhibitions': 'Exhibitions',
         'Early Modernism': 'Modernism', 'Regionalism': 'Regionalism', 'Post-War': 'Post-War',
         'McKernan Gallery': 'McKernan', 'Sol LeWitt': 'LeWitt', 'Low Illustration': 'Illustration', 'Upper Exhibitions': 'Exhibitions'}

DOORS = {
    '1': [('Landers House', '1-link', (504.0, 33.0)), ('1-link', '1-hall', (504.0, 90.0)),
          ('1-hall', 'Museum Café', (522.0, 140.0)), ('Museum Café', 'Lobby', (578.0, 160.0)),
          ('1-hall', 'Lobby', (522.0, 175.0)), ('Lobby', 'Museum Store', (560.0, 279.2)),
          ('1-hall', 'Benton Murals', (480.0, 190.0)), ('1-hall', 'Colonial & Federal', (440.0, 150.0)),
          ('Lobby', 'Benton Murals', (522.0, 230.0)), ('Colonial & Federal', 'Hudson River School', (390.0, 190.0)),
          ('Benton Murals', 'Hudson River School', (440.0, 250.0)),
          ('Hudson River School', 'Gilded Age', (380.0, 300.0)), ('Benton Murals', 'Gilded Age', (445.0, 339.5)),
          ('Hudson River School', '1-west-hall', (285.0, 300.0)), ('Gilded Age', '1-west-hall', (296.0, 340.0)),
          ('1-west-hall', 'Special Exhibitions', (215.0, 372.0))],
    '2': [('2-hall', 'Early Modernism', (560.0, 120.0)), ('Early Modernism', 'Regionalism', (580.0, 190.0)),
          ('2-hall', 'Post-War', (480.0, 190.0)), ('Regionalism', 'Post-War', (522.0, 240.0)),
          ('2-hall', 'Sol LeWitt', (440.0, 150.0)), ('Sol LeWitt', 'McKernan Gallery', (390.0, 190.0)),
          ('Post-War', 'McKernan Gallery', (440.0, 250.0)), ('McKernan Gallery', 'Low Illustration', (380.0, 300.0)),
          ('Post-War', 'Low Illustration', (445.0, 339.5)), ('McKernan Gallery', '2-west-hall', (285.0, 300.0)),
          ('Low Illustration', '2-west-hall', (296.0, 340.0)), ('2-west-hall', 'Upper Exhibitions', (215.0, 372.0))],
}

CORE = [('elevator', 460.0, 125.0), ('stairs', 465.0, 170.0), ('restroom', 500.0, 118.0),
        ('restroom-all', 503.0, 170.0), ('elevator', 160.0, 350.0), ('stairs', 240.0, 320.0)]
AMENITIES = {
    '1': CORE + [('entrance', 635.2, 220.0), ('info', 590.0, 220.0), ('coat', 560.0, 255.0),
                 ('shop', 560.0, 310.0), ('dining', 580.0, 120.0), ('entrance', 200.0, 507.0)],
    '2': CORE,
}
LABELS = {
    '1': [('Lexington Street entrance', 'note', 665.0, 235.0), ('Walnut Hill Park', 'place', 300.0, 40.0),
          ('Parking lot entrance', 'note', 200.0, 535.0), ('Lexington Street', 'place', 665.0, 330.0),
          ('Approximate layout: ask at the front desk what is on view', 'note', 380.0, 560.0)],
    '2': [('Approximate layout: galleries are rehung from time to time', 'note', 380.0, 560.0)],
}
FLOORS = [
    ('1', 'Main Floor', 'Entrance · Lobby · Café · Store · Benton murals · American art to 1900 · Landers House', 0),
    ('2', 'Upper Floor', 'Modern and contemporary art · Illustration · Special exhibitions', 1),
]


def build_floors():
    floors = []
    for fid, label, area, order in FLOORS:
        rooms = []
        for rid, kind, name, poly in FLOOR_ROOMS[fid]:
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': poly}
            if kind == 'gallery': r['label'] = SHORT.get(rid, rid)
            rooms.append(r)
        ids = {r['id'] for r in rooms}
        doors = [{'a': a, 'b': b, 'at': [x, y], 'width': 8, 'axis': 'o'} for a, b, (x, y) in DOORS[fid]]
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order, 'transform': [1, 0, 0],
                       'rooms': rooms, 'closed': [],
                       'amenities': [{'type': t, 'at': [x, y]} for t, x, y in AMENITIES[fid]],
                       'labels': [{'text': t, 'kind': k, 'at': [x, y]} for t, k, x, y in LABELS[fid]],
                       'doors': doors})
    return {'about': 'Built by tools/build_nbmaa.py. The building outline comes from the grounds map in the '
                     'museum’s family guide; the museum publishes no floor plan, so the rooms inside are an '
                     'approximate layout. Galleries are rehung from time to time.',
            'source': SOURCE, 'units': 'quarter-points', 'defaultFloor': '1', 'galleryWord': 'Gallery',
            'floors': floors}


# ---- works ---------------------------------------------------------------------------------------------------

THEME_ROOM = {'colonial': 'Colonial & Federal', 'hudson': 'Hudson River School', 'ctlandscape': 'Hudson River School',
              'genre': 'Gilded Age', 'impressionism': 'Gilded Age', 'modernism': 'Early Modernism',
              'regionalism': 'Regionalism', 'contemporary': 'Post-War', 'illustration': 'Low Illustration'}
REGIONALISTS = re.compile(r'Benton|Grant Wood|John Steuart Curry|Ben Shahn|Jacob Lawrence|Romare Bearden|'
                          r'Jack Levine|Reginald Marsh|Isabel Bishop|Raphael Soyer|Moses Soyer|Philip Evergood|'
                          r'Paul Cadmus|William Gropper|Doris Lee|Joe Jones|Aaron Douglas|Charles White', re.I)
PAPER = re.compile(r'paper|lithograph|etching|engraving|woodcut|screenprint|serigraph|silkscreen|aquatint|'
                   r'photograph|gelatin|print|drypoint|linocut|pigment', re.I)
PLACE_NOTE = ('Gallery guessed from the work’s subject, date and medium: the museum publishes no gallery list, '
              'and its collection site lists everything it owns, so this work may not be on view.')
THEME_NOTE = ('The museum lists this work among its highlights for this part of the collection; the gallery is '
              'the one that shows that period on our approximate map.')


def year_of(date):
    m = re.search(r'(1[6-9]\d\d|20[0-2]\d)', date or '')
    return int(m[1]) if m else None


def room_of(w):
    themes = w.get('themes') or []
    title, artist, medium = w.get('title') or '', w.get('artist') or '', w.get('medium') or ''
    if 'Benton' in artist and re.search(r'Arts of', title): return 'Benton Murals', True
    if artist == 'Sol LeWitt': return 'Sol LeWitt', False
    for t in themes:
        if t in THEME_ROOM: return THEME_ROOM[t], t != 'illustration'
    if re.search(r'LIC\b', w.get('number') or ''): return 'Low Illustration', False
    y = year_of(w.get('date'))
    if y is None: return None, False
    if PAPER.search(medium) and y >= 1900: return 'Upper Exhibitions', False
    if y < 1830: return 'Colonial & Federal', False
    if y < 1880: return 'Hudson River School', False
    if y < 1910: return 'Gilded Age', False
    if y < 1946: return ('Regionalism' if REGIONALISTS.search(artist) else 'Early Modernism'), False
    if y < 2000: return 'Post-War', False
    return 'McKernan Gallery', False


def build_works(floors, harvest):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    out, skipped = [], 0
    for w in harvest['works']:
        if not w.get('title'):
            skipped += 1
            continue
        g, highlight = room_of(w)
        if not g:
            skipped += 1
            continue
        floor, gname = rooms[g]
        y = year_of(w.get('date'))
        a = {'id': f'nbmaa-{w["oid"]}', 'title': w['title'], 'artist': w.get('artist', ''),
             'date': w.get('date', ''), 'year': y, 'medium': w.get('medium', ''), 'accession': w.get('number', ''),
             'gallery': g, 'galleryName': gname, 'floor': floor,
             'placeNote': THEME_NOTE if highlight else PLACE_NOTE,
             'url': f'{EMUSEUM}/objects/{w["oid"]}/{w.get("slug", "")}'}
        if highlight: a['highlight'] = True
        if w.get('media'):
            a['image'] = f'{EMUSEUM}/internal/media/dispatcher/{w["media"]}/preview'
            a['imageCredit'] = 'New Britain Museum of American Art'
        out.append({k: v for k, v in a.items() if v not in (None, '')})
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    out.sort(key=lambda a: (a['floor'], order[a['gallery']], -('highlight' in a), -('image' in a), a.get('year') or 0))
    doc = {'source': 'New Britain Museum of American Art collection site (ink.nbmaa.org); galleries guessed from '
                     'subject, date and medium',
           'checked': harvest.get('harvested') or time.strftime('%Y-%m-%d'), 'count': len(out), 'complete': True,
           'artworks': out}
    return doc, skipped


def main():
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    harvest = json.load(open(sys.argv[1]))
    works, skipped = build_works(floors, harvest)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{works["count"]} works placed ({sum(1 for a in works["artworks"] if "image" in a)} with pictures), '
          f'{skipped} without a likely gallery')
    for k, n in sorted(by.items(), key=lambda kv: -kv[1]): print(f'  {k}: {n}')


if __name__ == '__main__':
    main()
