#!/usr/bin/env python3
"""Build the Addison Gallery of American Art map guide (run: python3 tools/build_addison.py HARVEST.json).

    data/addison/floors.json    the Lower Level, Level 1 and Level 2 seen from above (a flat 2D plan)
    data/addison/artworks.json  the works on view, in the gallery where each one hangs

The map is traced from the museum's own gallery maps on addison.andover.edu/visit/gallery-map (Level 1 and
Level 2 from September 2026, the Lower Level from 2023) and its Fall 2026 visitor guide PDF, which adds the
coatroom, water fountain, accessible restroom and the main entrance. Coordinates are in Level 1 map pixels
(the 2000-pixel-wide picture) divided by 4; Level 2 and the Lower Level are scaled and shifted so their
elevators and stairs sit over the Level 1 ones.

The works come from tools/harvest_addison.py: every work in the current exhibition, America in the Making
(Levels 1 and 2), and in the permanent ship model installation (Lower Level). The museum names the
section each part of the show is in (18th and 19th Century: Galleries 101–105; Portrait Miniatures and Early
Photography: the Director's Office; American Impressionism to Early 20th Century: the Exhibition Hall and
Gallery 109; Early Modernism to Midcentury: Galleries 201–205; 1960s–Present: Galleries 206–209). Works are
put in their section by date and medium, and in a room of that section by a guess, except the works the
museum's gallery map pins to a room (KNOWN below).
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'addison'
SOURCE = 'https://addison.andover.edu/visit/gallery-map/'
KIOSK = 'https://addison.andover.edu/search-the-collection/?embark_query='
Q = 0.25   # Level 1 map pixels -> map units


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def l2(x, y):  # Level 2 map picture (1406 x 1749) -> Level 1 pixels
    return [0.92 * (x - 763) + 1332, 0.92 * (y - 443) + 400]


def ll(x, y):  # Lower Level map picture (1312 x 1766) -> Level 1 pixels
    return [0.917 * (x - 720) + 1332, 0.917 * (y - 400) + 400]


def scale(poly, f=None):
    return [[round(c * Q, 1) for c in (f(*p) if f else p)] for p in poly]


# ---- Level 1 (pixels of GalleryMapL1_09.08.26, shown 2000 wide) -------------------------------------------------
L1 = [
    ('101', 'gallery', 'Rotunda · America in the Making: 18th and 19th Century · Paul Manship’s Venus fountain',
     [[1218, 970], [1335, 970], [1430, 1060], [1555, 1060], [1555, 1185], [1440, 1185], [1365, 1285],
      [1195, 1285], [1130, 1185], [1000, 1185], [1000, 1060], [1110, 1060]]),
    ('102', 'gallery', 'America in the Making: 18th and 19th Century', [[1555, 975], [1870, 975], [1870, 1222], [1555, 1222]]),
    ('103', 'gallery', 'America in the Making: 18th and 19th Century', [[1555, 1222], [1870, 1222], [1870, 1490], [1555, 1490]]),
    ('104', 'gallery', 'America in the Making: 18th and 19th Century', [[688, 1222], [1000, 1222], [1000, 1490], [688, 1490]]),
    ('105', 'gallery', 'America in the Making: 18th and 19th Century', [[688, 975], [1000, 975], [1000, 1222], [688, 1222]]),
    ('Miniatures', 'gallery', 'Director’s Office · America in the Making: Portrait Miniatures and Early Photography',
     [[1000, 1185], [1130, 1185], [1195, 1285], [1195, 1385], [1000, 1385]]),
    ('Exhibition Hall', 'gallery', 'Exhibition Hall · America in the Making: American Impressionism to Early 20th Century',
     [[1218, 390], [1332, 390], [1332, 970], [1218, 970]]),
    ('109', 'gallery', 'America in the Making: American Impressionism to Early 20th Century', [[1000, 75], [1555, 75], [1555, 390], [1000, 390]]),
    ('1-entrance', 'corridor', 'Main entrance', [[1195, 1285], [1365, 1285], [1365, 1385], [1195, 1385]]),
    ('Museum Shop', 'space', 'Museum Shop', [[1365, 1285], [1440, 1185], [1555, 1185], [1555, 1385], [1365, 1385]]),
    ('Visitor Services', 'space', 'Visitor Services · information · coatroom', [[1335, 975], [1555, 975], [1555, 1060], [1430, 1060]]),
    ('1-restroom', 'space', 'Accessible restroom', [[1000, 975], [1218, 975], [1110, 1060], [1000, 1060]]),
    ('1-elevator', 'space', 'Elevator', rect(1332, 400, 1550, 485)),
    ('1-stairs', 'space', 'Stairs', rect(1332, 760, 1550, 965)),
    ('Library', 'space', 'Library', rect(800, 632, 1215, 970)),
    ('Learning Center', 'gallery', 'Museum Learning Center · Peter Halley mural · view of the green roof',
     [[185, 535], [605, 535], [605, 680], [675, 680], [675, 765], [800, 765], [800, 1100], [185, 1100]]),
    ('Green Roof', 'gallery', 'Green roof · Dale Chihuly’s Black Niijima Floats (seen from the Learning Center)',
     [[110, 1045], [185, 1045], [185, 1100], [688, 1100], [688, 1490], [110, 1490]]),
]
L1_DOORS = [('1-entrance', '101', (1280, 1285)), ('101', '105', (1000, 1120)), ('101', '102', (1555, 1120)),
            ('105', '104', (842, 1222)), ('102', '103', (1712, 1222)), ('101', 'Exhibition Hall', (1275, 970)),
            ('Exhibition Hall', '109', (1275, 390)), ('Exhibition Hall', 'Library', (1215, 870)),
            ('Library', 'Learning Center', (800, 860)), ('101', 'Miniatures', (1050, 1185)),
            ('101', 'Museum Shop', (1500, 1185)), ('101', '1-restroom', (1060, 1060)),
            ('101', 'Visitor Services', (1490, 1060)), ('Exhibition Hall', '1-elevator', (1332, 442)),
            ('Exhibition Hall', '1-stairs', (1332, 862))]

# ---- Level 2 (pixels of GalleryMapL2.F26) ---------------------------------------------------------------------
L2 = [
    ('201', 'gallery', 'America in the Making: Early Modernism to Midcentury · Sol LeWitt’s Wall Drawing #713 on the vaulted ceiling',
     rect(403, 1110, 1007, 1505)),
    ('202', 'gallery', 'America in the Making: Early Modernism to Midcentury', rect(1007, 1063, 1340, 1335)),
    ('203', 'gallery', 'America in the Making: Early Modernism to Midcentury', rect(1007, 1335, 1340, 1620)),
    ('204', 'gallery', 'America in the Making: Early Modernism to Midcentury', rect(68, 1340, 403, 1620)),
    ('205', 'gallery', 'America in the Making: Early Modernism to Midcentury', rect(68, 1063, 403, 1340)),
    ('206', 'gallery', 'America in the Making: 1960s–Present', rect(403, 875, 640, 1110)),
    ('207', 'gallery', 'America in the Making: 1960s–Present', rect(403, 570, 640, 875)),
    ('208', 'gallery', 'America in the Making: 1960s–Present',
     [[640, 437], [763, 437], [763, 540], [1000, 540], [1000, 830], [763, 830], [763, 1110], [640, 1110]]),
    ('209', 'gallery', 'America in the Making: 1960s–Present', rect(403, 90, 1007, 437)),
    ('2-elevator', 'space', 'Elevator', rect(763, 443, 1000, 540)),
    ('2-stairs', 'space', 'Stairs', rect(763, 830, 1000, 1060)),
]
L2_DOORS = [('208', '201', (701, 1110)), ('208', '209', (701, 437)), ('208', '207', (640, 670)),
            ('208', '206', (640, 1075)), ('207', '206', (470, 875)), ('201', '205', (403, 1195)),
            ('201', '204', (403, 1460)), ('205', '204', (230, 1340)), ('201', '202', (1007, 1195)),
            ('201', '203', (1007, 1460)), ('202', '203', (1175, 1335)), ('208', '2-elevator', (763, 491)),
            ('208', '2-stairs', (763, 945))]

# ---- Lower Level (pixels of GalleryMap.LL_.F23) ----------------------------------------------------------------
LL = [
    ('Ship Models', 'gallery', 'Models of American Sailing Ships · permanently installed',
     [[597, 395], [720, 395], [720, 1090], [965, 1090], [965, 1243], [357, 1243], [357, 1090], [597, 1090]]),
    ('LL-men', 'space', 'Men’s room', rect(365, 545, 590, 718)),
    ('LL-women', 'space', 'Women’s room', [[720, 505], [958, 505], [958, 783], [720, 783]]),
    ('LL-elevator', 'space', 'Elevator', rect(720, 400, 958, 493)),
    ('LL-stairs', 'space', 'Stairs', rect(720, 795, 958, 1020)),
]
LL_DOORS = [('Ship Models', 'LL-men', (597, 630)), ('Ship Models', 'LL-women', (720, 760)),
            ('Ship Models', 'LL-elevator', (720, 446)), ('Ship Models', 'LL-stairs', (720, 907))]

SHORT = {'101': 'Rotunda 101', 'Miniatures': 'Miniatures', 'Exhibition Hall': 'Exhibition Hall',
         'Learning Center': 'Learning Center', 'Green Roof': 'Green Roof', 'Ship Models': 'Ship Models'}

ELEV, STAIRS = (1441, 442), (1441, 862)
AMENITIES = {
    'LL': [('elevator', *ELEV), ('stairs', *STAIRS), ('restroom', *ll(478, 630)), ('restroom', *ll(840, 650)),
           ('water', *ll(690, 1000))],
    '1': [('elevator', *ELEV), ('stairs', *STAIRS), ('restroom-all', 1065, 1010), ('info', 1470, 1015),
          ('coat', 1515, 1035), ('shop', 1470, 1320), ('entrance', 1280, 1385)],
    '2': [('elevator', *ELEV), ('stairs', *STAIRS)],
}
LABELS = {
    'LL': [('Restrooms are on this level', 'note', *ll(660, 1330))],
    '1': [('Main entrance (Chapel Avenue)', 'note', 1280, 1440), ('Phillips Academy campus', 'place', 1280, 1540)],
    '2': [],
}
FLOORS = [
    ('LL', 'Lower Level', 'Models of American Sailing Ships · Restrooms · Water fountain', 0, LL, LL_DOORS, ll),
    ('1', 'Level 1', 'Entrance · Visitor Services · Shop · 18th and 19th century · Impressionism · Library', 1, L1, L1_DOORS, None),
    ('2', 'Level 2', 'Early Modernism to Midcentury · 1960s to today', 2, L2, L2_DOORS, l2),
]


def build_floors():
    floors = []
    for fid, label, area, order, rooms_src, doors_src, f in FLOORS:
        rooms = []
        for rid, kind, name, poly in rooms_src:
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': scale(poly, f)}
            if kind == 'gallery': r['label'] = SHORT.get(rid, rid)
            rooms.append(r)
        ids = {r['id'] for r in rooms}
        doors = []
        for a, b, (x, y) in doors_src:
            assert a in ids and b in ids, (fid, a, b)
            doors.append({'a': a, 'b': b, 'at': scale([[x, y]], f)[0], 'width': 8, 'axis': 'o'})
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order, 'transform': [1, 0, 0],
                       'rooms': rooms, 'closed': [],
                       'amenities': [{'type': t, 'at': scale([[x, y]])[0]} for t, x, y in AMENITIES[fid]],
                       'labels': [{'text': t, 'kind': k, 'at': scale([[x, y]])[0]} for t, k, x, y in LABELS[fid]],
                       'doors': doors})
    return {'about': 'Built by tools/build_addison.py, traced from the Addison’s own gallery maps (Levels 1 and 2, '
                     'September 2026; Lower Level, 2023) and its Fall 2026 visitor guide.',
            'source': SOURCE, 'units': 'quarter-pixels', 'defaultFloor': '1', 'galleryWord': 'Gallery',
            'floors': floors}


# ---- works ---------------------------------------------------------------------------------------------------

SECTIONS = {
    'early': ('18th and 19th Century', 'Galleries 101–105'),
    'mini': ('Portrait Miniatures and Early Photography', 'the Director’s Office'),
    'impr': ('American Impressionism to Early 20th Century', 'the Exhibition Hall and Gallery 109'),
    'modern': ('Early Modernism to Midcentury', 'Galleries 201–205'),
    'now': ('1960s–Present', 'Galleries 206–209'),
}
# Works the museum's gallery map pins to a room (accession number -> room)
KNOWN = {'1930.291': '101', '1932.17': '109', '1928.53': 'Exhibition Hall', '1942.32': '104', '2024.96.31': 'Miniatures',
         '1945.4': '103', '2022.112': '209', '1983.36': '208', '2020.69': '207', '1951.3': '201', '2007.44': '203',
         '2005.8': '204', '1993.49': '201', '2010.96a-j': 'Green Roof', '1931.S7': 'Library'}
ROOM_SECTION = {'101': 'early', '102': 'early', '103': 'early', '104': 'early', '105': 'early', 'Miniatures': 'mini',
                'Exhibition Hall': 'impr', '109': 'impr', '201': 'modern', '202': 'modern', '203': 'modern',
                '204': 'modern', '205': 'modern', '206': 'now', '207': 'now', '208': 'now', '209': 'now'}
MODERNISTS = re.compile(r"O'Keeffe|O’Keeffe|Dove|Marin|Hartley|Demuth|Sheeler|Stuart Davis|Bluemner|Maurer|Bruce|"
                        r'Stella|Weber|Walkowitz|Man Ray|Stieglitz|Strand|Steichen|Lozowick|Spencer|Crawford|Gorky|'
                        r'Calder|Nadelman|Zorach|Lachaise|Dickinson|Avery|Albers|Moholy|Kepes|Gabo|Pereira', re.I)
EARLY_PHOTO = re.compile(r'daguerreotype|ambrotype|tintype|salted paper|miniature|on ivory|cased', re.I)
PHOTO = re.compile(r'gelatin|silver print|albumen|platinum|chromogenic|photograph|pigment print|inkjet|dye', re.I)
PAPER = re.compile(r'paper|lithograph|etching|engraving|woodcut|screenprint|drypoint|watercolor|pastel|graphite|'
                   r'charcoal|ink\b', re.I)
SCULPTURE = re.compile(r'bronze|marble|steel|wood|plaster|stone|glass|silver\b|ceramic|aluminum|found objects|'
                       r'iron|brass|poplar|walnut|mahogany|pine|maple|cherry|clay', re.I)


def year_of(date):
    m = re.search(r'(1[6-9]\d\d|20[0-2]\d)', date or '')
    return int(m[1]) if m else None


def section_of(w, y):
    medium, artist = w.get('medium', ''), w.get('artist', '')
    if y is None: return 'early'
    if EARLY_PHOTO.search(medium) and y < 1900: return 'mini'
    if y < 1880: return 'early'
    if y >= 1960: return 'now'
    if y >= 1935: return 'modern'
    if y >= 1905 and MODERNISTS.search(artist): return 'modern'
    if PHOTO.search(medium) and y >= 1905: return 'modern'
    return 'impr'


def room_in(section, w, y):
    medium = w.get('medium', '')
    sculpt = SCULPTURE.search(medium) and not PAPER.search(medium) and not PHOTO.search(medium)
    if section == 'mini': return 'Miniatures'
    if section == 'early':
        if sculpt and y and y >= 1830: return '101'
        if not y or y < 1800: return '104'
        if y < 1840: return '105'
        if y < 1860: return '102'
        return '103'
    if section == 'impr':
        return 'Exhibition Hall' if PAPER.search(medium) or PHOTO.search(medium) else '109'
    if section == 'modern':
        if sculpt: return '201'
        if PHOTO.search(medium): return '204'
        if y < 1925: return '205'
        if y < 1940: return '202'
        return '203'
    if PHOTO.search(medium) or PAPER.search(medium): return '206'
    if sculpt: return '208'
    return '209' if y < 1985 else '207'


def build_works(floors, harvest):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    out = []
    for w in harvest['works']:
        if not w.get('title'):
            continue
        y = year_of(w.get('date'))
        num = w.get('number', '')
        if w['portfolio'] == '212' and num not in KNOWN:
            g, note = 'Ship Models', 'Part of the Addison’s permanently installed ship models on the Lower Level.'
        elif num in KNOWN:
            g = KNOWN[num]
            note = 'The Addison’s gallery map shows this work here.'
        else:
            sec = section_of(w, y)
            g = room_in(sec, w, y)
            name, where = SECTIONS[sec]
            note = (f'America in the Making, {name} section ({where}). The museum does not list each work’s room, '
                    f'so the room is our guess from its date and medium; look around the section if it is not here.')
            if sec == 'mini': note = f'America in the Making, {name}, in {where}.'
        floor, gname = rooms[g]
        url = (f'{KIOSK}/objects-1/info/{w["oid"]}' if w.get('oid')
               else f'{KIOSK}/objects-1/info?query=mfs%20all%20%22{num}%22')
        a = {'id': f'addison-{num or w.get("oid")}', 'title': w['title'], 'artist': w.get('artist', ''),
             'artistDetails': w.get('artistDates', ''), 'date': w.get('date', ''), 'year': y,
             'medium': w.get('medium', ''), 'dimensions': w.get('dimensions', ''), 'creditLine': w.get('credit', ''),
             'accession': num, 'gallery': g, 'galleryName': gname, 'floor': floor, 'placeNote': note,
             'exhibition': {'2600': 'America in the Making (September 8, 2026 – spring 2027)',
                            '212': 'Models of American Sailing Ships (permanently installed)'}.get(w['portfolio'],
                                                                                                   'Permanently installed'),
             'description': w.get('commentary', ''),
             'descriptionKind': 'Commentary from the Addison Gallery of American Art' if w.get('commentary') else '',
             'url': url, 'onView': True}
        if w.get('large') or w.get('preview'):
            a['image'] = w.get('large') or w['preview']
            a['imageCredit'] = 'Addison Gallery of American Art, Phillips Academy'
        out.append({k: v for k, v in a.items() if v not in (None, '')})
    seen, uniq = set(), []
    for a in out:
        if a['id'] in seen: continue
        seen.add(a['id'])
        uniq.append(a)
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    uniq.sort(key=lambda a: (forder[a['floor']], order[a['gallery']], -('image' in a), a.get('year') or 0))
    return {'source': 'Addison Gallery of American Art collection search (works in America in the Making and the '
                      'ship model installation); rooms from the museum’s gallery map',
            'checked': harvest.get('harvested') or time.strftime('%Y-%m-%d'), 'count': len(uniq), 'complete': True,
            'artworks': uniq}


MUSEUM = 'Q4681251'


def build_guide(works):
    rows = [{'id': a['id'], 'title': a['title'], 'artist': a.get('artist', ''), 'date': a.get('date', ''),
             'year': a.get('year'), 'medium': a.get('medium', ''), 'accession': a.get('accession', ''),
             'url': a['url'], 'imageUrl': a.get('image', ''), 'onView': True, 'gallery': a['gallery'],
             'floor': a['floor']} for a in works['artworks']]
    return {'museum': MUSEUM, 'name': 'Addison Gallery of American Art', 'checked': works['checked'],
            'source': 'Addison Gallery of American Art collection search', 'onViewKnown': True,
            'note': 'The works on view now: America in the Making and the ship models. The Addison owns more than '
                    '29,000 works; the rest can be searched on the museum’s own collection site.',
            'works': [{k: v for k, v in r.items() if v not in (None, '')} for r in rows]}


def main():
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    if len(sys.argv) < 2:
        print('floors only (no harvest given)')
        return
    works = build_works(floors, json.load(open(sys.argv[1])))
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': len(guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{works["count"]} works ({sum(1 for a in works["artworks"] if "image" in a)} with pictures)')
    for k, n in sorted(by.items(), key=lambda kv: -kv[1]): print(f'  {k}: {n}')


if __name__ == '__main__':
    main()
