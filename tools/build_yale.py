#!/usr/bin/env python3
"""Build the Yale University Art Gallery map guide (run: python3 tools/build_yale.py CACHE_DIR).

    data/yale/floors.json    the lower lobby and four floors, seen from above (a flat 2D plan)
    data/yale/artworks.json  every work the Gallery lists as on view, in the gallery the Gallery names

CACHE_DIR is what tools/harvest_yale.py fetched: the Gallery's own "What's On View by Floor" lists and each
work's Linked Art record (CC0) from media.art.yale.edu.

The works are exact: the Gallery's website says where each one is on view ("On view, 2nd floor, European Art").

The map is approximate. The Gallery's only floor plan is inside the Smartify app, which can't be read from here.
So each floor is drawn from what the Gallery says in words: three joined buildings along Chapel Street (Louis
Kahn's 1953 building at York Street with the 1111 Chapel Street entrance, the 1928 Old Yale Art Gallery, and
Street Hall across High Street, reached by a bridge), what is on each floor of each building, and where the
elevators, restrooms and lower-level Nolen Center are. Every floor says on the map that it is approximate.
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'yale'
SOURCE = ('Yale University Art Gallery website: what is on view on each floor, accessibility and visit pages '
          '(layout drawn by hand, approximate)')


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# Footprints, Chapel Street along the bottom, York Street on the left. Rooms are drawn a little deeper than the
# buildings are, so their names fit on a phone.
KAHN = (100, 360, 215, 570)
OLD = (215, 430, 415, 570)
STREET = (465, 400, 545, 570)
BRIDGE = rect(415, 470, 465, 500)

ROOMS = {
    'LL': [
        ('Lower Lobby', 'gallery', 'Lower Lobby · photographs', rect(100, 460, 215, 570), 'Lower Lobby'),
        ('Sculpture Courtyard', 'gallery', 'Sculpture Courtyard', rect(100, 360, 215, 460), 'Courtyard'),
        ('Nolen Center', 'space', 'Nolen Center for Art and Education · classrooms', rect(*OLD), None),
    ],
    '1': [
        ('Lobby', 'gallery', 'Lobby · 1111 Chapel Street entrance · Museum Store', rect(150, 460, 215, 570), 'Lobby'),
        ('African Art', 'gallery', 'African Art', rect(100, 360, 150, 570), 'African'),
        ('Lecture Hall', 'space', 'Robert L. McNeil, Jr., Lecture Hall', rect(150, 360, 215, 460), None),
        ('Sculpture Garden', 'gallery', 'Sculpture Garden', rect(100, 280, 215, 360), 'Garden'),
        ('Ancient Americas', 'gallery', 'Art of the Ancient Americas', rect(215, 430, 285, 570), 'Americas'),
        ('Ancient Art', 'gallery', 'Ancient Art · Sculpture Hall', rect(285, 500, 415, 570), 'Ancient'),
        ('Dura-Europos', 'gallery', 'Dura-Europos', rect(285, 430, 350, 500), 'Dura'),
        ('Numismatics', 'gallery', 'Numismatics · coins and medals', rect(350, 430, 415, 500), 'Coins'),
        ('American Decorative Arts', 'gallery', 'American Decorative Arts before 1900 · Street Hall, floor 1E '
         '(from floor 2, cross the bridge and take the east elevator down)', rect(*STREET), 'Decorative'),
    ],
    '2': [
        ('Asian Art', 'gallery', 'Asian Art', rect(*KAHN), 'Asian'),
        ('European Art', 'gallery', 'European Art', rect(*OLD), 'European'),
        ('Bridge', 'corridor', 'Bridge over High Street', BRIDGE, None),
        ('American Art', 'gallery', 'American Art before 1900 · paintings and sculpture · Street Hall',
         rect(*STREET), 'American'),
    ],
    '3': [
        ('Indo-Pacific Art', 'gallery', 'Indo-Pacific Art', rect(*KAHN), 'Indo-Pacific'),
        ('Modern and Contemporary', 'gallery', 'Modern and Contemporary Art and Design', rect(*OLD), 'Modern'),
    ],
    '4': [
        ('Special Exhibitions', 'gallery', 'Special Exhibitions', rect(100, 460, 215, 570), 'Exhibitions'),
        ('Prints and Drawings', 'gallery', 'Prints, Drawings, and Photographs', rect(100, 360, 215, 460), 'Prints'),
        ('Sculpture Terrace', 'gallery', 'Sculpture Terrace · rooftop', rect(215, 430, 330, 570), 'Terrace'),
        ('East Galleries 4', 'corridor', 'East Galleries (floor 4M)', rect(330, 430, 415, 570), None),
    ],
}

DOORS = {
    'LL': [('Lower Lobby', 'Sculpture Courtyard', (158, 460)), ('Lower Lobby', 'Nolen Center', (215, 520))],
    '1': [('Lobby', 'African Art', (150, 520)), ('Lobby', 'Lecture Hall', (185, 460)),
          ('African Art', 'Sculpture Garden', (125, 360)), ('Lobby', 'Ancient Americas', (215, 520)),
          ('Ancient Americas', 'Ancient Art', (285, 535)), ('Ancient Americas', 'Dura-Europos', (285, 465)),
          ('Ancient Art', 'Dura-Europos', (318, 500)), ('Dura-Europos', 'Numismatics', (350, 465)),
          ('Ancient Art', 'Numismatics', (383, 500))],
    '2': [('Asian Art', 'European Art', (215, 520)), ('European Art', 'Bridge', (415, 485)),
          ('Bridge', 'American Art', (465, 485))],
    '3': [('Indo-Pacific Art', 'Modern and Contemporary', (215, 520))],
    '4': [('Special Exhibitions', 'Prints and Drawings', (158, 460)), ('Special Exhibitions', 'Sculpture Terrace', (215, 520)),
          ('Sculpture Terrace', 'East Galleries 4', (330, 500))],
}

KAHN_STAIR = (165, 415)    # Kahn's round staircase
KAHN_LIFT = (195, 415)
ENTRY_LIFT = (205, 555)    # the accessible elevator opposite the main entrance
EAST_STAIR = (400, 445)    # Old Yale Art Gallery, east end
EAST_LIFT = (480, 415)     # Street Hall ("east elevator")
STREET_STAIR = (530, 415)  # the round stair between Street Hall and the Old Yale Art Gallery
AMENITIES = {
    'LL': [('stairs', *KAHN_STAIR), ('elevator', *KAHN_LIFT), ('elevator', *ENTRY_LIFT), ('restroom', 120, 550),
           ('restroom', 395, 550), ('stairs', *EAST_STAIR)],
    '1': [('entrance', 185, 568), ('info', 170, 530), ('shop', 200, 495), ('elevator', *ENTRY_LIFT),
          ('stairs', *KAHN_STAIR), ('elevator', *KAHN_LIFT), ('restroom', 200, 440), ('stairs', *EAST_STAIR),
          ('elevator', *EAST_LIFT), ('stairs', *STREET_STAIR)],
    '2': [('stairs', *KAHN_STAIR), ('elevator', *KAHN_LIFT), ('elevator', *ENTRY_LIFT), ('restroom', 200, 440),
          ('stairs', *EAST_STAIR), ('elevator', *EAST_LIFT), ('stairs', *STREET_STAIR)],
    '3': [('stairs', *KAHN_STAIR), ('elevator', *KAHN_LIFT), ('elevator', *ENTRY_LIFT), ('restroom', 200, 440),
          ('stairs', *EAST_STAIR)],
    '4': [('stairs', *KAHN_STAIR), ('elevator', *KAHN_LIFT), ('elevator', *ENTRY_LIFT), ('restroom', 400, 550),
          ('stairs', *EAST_STAIR)],
}
APPROX = 'Approximate layout'
LABELS = {
    'LL': [(APPROX, 'note', 330, 400)],
    '1': [('Chapel Street', 'place', 330, 590), ('High Street', 'place', 440, 440), ('York Street', 'place', 160, 270),
          ('Entrance', 'note', 185, 590), ('No café inside', 'note', 500, 380), (APPROX, 'note', 560, 380)],
    '2': [('Street Hall', 'place', 505, 380), ('Bridge', 'note', 440, 440), (APPROX, 'note', 330, 400)],
    '3': [(APPROX, 'note', 330, 400)],
    '4': [(APPROX, 'note', 330, 400)],
}

FLOORS = [
    ('LL', 'Lower Lobby', 'Photographs · Sculpture Courtyard · Nolen Center · restrooms', 0),
    ('1', 'Floor 1', 'Entrance · Lobby · African · Ancient · Dura-Europos · Coins · Street Hall: American decorative arts', 1),
    ('2', 'Floor 2', 'Asian · European · bridge to Street Hall · American Art before 1900', 2),
    ('3', 'Floor 3', 'Indo-Pacific · Modern and Contemporary Art and Design', 3),
    ('4', 'Floor 4', 'Special Exhibitions · Prints, Drawings, and Photographs · rooftop Sculpture Terrace', 4),
]

# Where the Gallery says a work is on view -> room on the map
WHERE = {
    '1st and 2nd floor, Spiral Staircase': 'Lobby',
    '1st floor, African Art': 'African Art',
    '1st floor, American Decorative Arts before 1900': 'American Decorative Arts',
    '1st floor, Ancient Art': 'Ancient Art',
    '1st floor, Art of the Ancient Americas': 'Ancient Americas',
    '1st floor, Dura-Europos': 'Dura-Europos',
    '1st floor, Lecture Hall': 'Lobby',
    '1st floor, Lecture Hall Corridor': 'Lobby',
    '1st floor, Lobby': 'Lobby',
    '1st floor, Numismatics': 'Numismatics',
    '1st floor, Sculpture Garden': 'Sculpture Garden',
    '2nd floor, American Art before 1900': 'American Art',
    '2nd floor, Asian Art': 'Asian Art',
    '2nd floor, European Art': 'European Art',
    '3rd floor, Indo-Pacific Art': 'Indo-Pacific Art',
    '3rd floor, Modern and Contemporary Art and Design': 'Modern and Contemporary',
    '4th floor, Prints, Drawings, and Photographs': 'Prints and Drawings',
    '4th floor, Sculpture Terrace': 'Sculpture Terrace',
    '4th floor, Special Exhibitions': 'Special Exhibitions',
    'Lower Lobby, Photographs': 'Lower Lobby',
    'Lower Lobby, Sculpture Courtyard': 'Sculpture Courtyard',
}


def turn(pt):
    """Turn the plan a quarter so it fits a phone: Chapel Street runs down the left, York Street at the top."""
    x, y = pt
    # squeeze along Chapel Street and narrow High Street, so the plan is about as wide as it is tall
    x = 100 + (x - 100) * 0.8 if x <= 415 else 352 + (x - 415) * 0.5 if x <= 465 else 377 + (x - 465) * 0.9
    y = 570 - (570 - y) * 1.1
    return [round(630 - y, 1), round(x - 60, 1)]


def build_floors():
    floors = []
    for fid, label, area, order in FLOORS:
        rooms = []
        for rid, kind, name, poly, short in ROOMS[fid]:
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': [turn(p) for p in poly]}
            if kind == 'gallery': r['label'] = short or rid
            rooms.append(r)
        doors = [{'a': a, 'b': b, 'at': turn((x, y)), 'width': 6, 'axis': 'o'} for a, b, (x, y) in DOORS[fid]]
        amen = [{'type': t, 'at': turn((x, y))} for t, x, y in AMENITIES[fid]]
        labels = [{'text': t, 'kind': k, 'at': turn((x, y))} for t, k, x, y in LABELS[fid]]
        ids = {r['id'] for r in rooms}
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order, 'transform': [1, 0, 0],
                       'rooms': rooms, 'closed': [], 'amenities': amen, 'labels': labels, 'doors': doors})
    return {'about': 'Built by tools/build_yale.py. Which gallery each work is in comes from the Yale University Art '
                     'Gallery’s website. The floor layout is approximate: the Gallery’s own floor plan is only in the '
                     'Smartify app, so rooms are drawn from its descriptions of the three buildings.',
            'source': SOURCE, 'units': 'pixels', 'defaultFloor': '1', 'galleryWord': 'Gallery', 'floors': floors}


# ---- works ---------------------------------------------------------------------------------------------------

def statement(rec, label):
    for r in rec.get('referred_to_by', []):
        for c in r.get('classified_as', []):
            if c.get('_label') == label: return r.get('content', '')
    return ''


def plain(s):
    s = re.sub(r'<[^>]+>', ' ', s or '')
    s = re.sub(r'&nbsp;|\s+', ' ', s).replace('&amp;', '&').replace('&quot;', '"').strip()
    return s


ARTIST = re.compile(r'^(?:Artist|Maker|Designer|Manufacturer|Author|Photographer|Printer|Publisher|Silversmith|'
                    r'Cabinetmaker|Possibly|Probably|Attributed to)[^:]*:\s*', re.I)


def artist_of(creator):
    first = re.split(r'\s*;\s*|\s*\|\s*', creator or '')[0]
    name = ARTIST.sub('', first).strip()
    name = re.sub(r'\s*\([^)]*\)\s*$', '', name).strip()
    return '' if re.match(r'^(unknown|unidentified|anonymous)', name, re.I) else name


def year_of(rec):
    ts = (rec.get('produced_by') or {}).get('timespan') or {}
    b, e = ts.get('begin_of_the_begin'), ts.get('end_of_the_end')
    m = re.match(r'(-?)0*(\d+)-', b or '')
    if not m: return None, ''
    y = int(m[2]) * (-1 if m[1] else 1)
    m2 = re.match(r'(-?)0*(\d+)-', e or '')
    if m2:
        y2 = int(m2[2]) * (-1 if m2[1] else 1)
        if y2 - y < 400: y = (y + y2) // 2
    name = next((n.get('content', '') for n in ts.get('identified_by', [])), '')
    return y, name


def build_works(floors, cache):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    cards = json.loads((cache / 'cards.json').read_text())
    out, skipped = [], {}
    for oid, c in cards.items():
        where = [w.strip() for w in c['where'].split(';')]
        place = next((w[len('On view, '):] for w in where if w.startswith('On view, ')
                      and w[len('On view, '):] in WHERE), None)
        if not place:
            skipped[c['where']] = skipped.get(c['where'], 0) + 1
            continue
        g = WHERE[place]
        floor, gname = rooms[g]
        f = cache / 'lux' / f'{oid}.json'
        rec = json.loads(f.read_text()) if f.exists() else {}
        year, date = year_of(rec)
        acc = next((i['content'] for i in rec.get('identified_by', [])
                    if any(t.get('_label') == 'Accession Number' for t in i.get('classified_as', []))), '')
        life = re.search(r'\(([^)]*\d[^)]*)\)', re.split(r'\s*;\s*', c['creator'] or '')[0])
        a = {'id': f'yuag{oid}', 'title': c['title'], 'artist': artist_of(c['creator']),
             'artistDetails': life[1] if life and artist_of(c['creator']) else '', 'country': c['culture'],
             'date': date, 'year': year, 'medium': statement(rec, 'Medium'), 'dimensions': statement(rec, 'Dimensions'),
             'creditLine': statement(rec, 'Credit Line'), 'accession': acc, 'onView': True, 'type': c['type'],
             'department': c['department'], 'gallery': g, 'galleryName': gname, 'floor': floor,
             'placeNote': f'The Gallery lists this work as on view: {place}. Where the room sits on this map is approximate.',
             'url': f'https://artgallery.yale.edu/collections/objects/{oid}'}
        desc = plain(statement(rec, 'Description'))
        if desc: a['description'] = desc[:1200]
        if rec.get('representation') or not rec:
            a['image'] = f'https://media.collections.yale.edu/thumbnail/yuag/obj/{oid}'
            a['imageCredit'] = 'Yale University Art Gallery'
        if 'Highlight' in statement(rec, 'Status Flag'): a['highlight'] = True
        out.append({k: v for k, v in a.items() if v not in (None, '')})
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    out.sort(key=lambda a: (forder[a['floor']], order[a['gallery']], -('highlight' in a), -('image' in a),
                            a.get('year') if a.get('year') is not None else 9999))
    doc = {'source': 'Yale University Art Gallery website (works on view and where) and its Linked Art data (CC0)',
           'checked': time.strftime('%Y-%m-%d'), 'count': len(out), 'complete': True, 'artworks': out}
    return doc, skipped


def main():
    cache = Path(sys.argv[1])
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works, skipped = build_works(floors, cache)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{works["count"]} works on view ({sum(1 for a in works["artworks"] if "image" in a)} with pictures)')
    for k in sorted(by): print(f'  {k}: {by[k]}')
    for k, n in skipped.items(): print(f'  not on the map: {k} ({n})')


if __name__ == '__main__':
    main()
