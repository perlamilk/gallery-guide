#!/usr/bin/env python3
"""Build the Yale Center for British Art map guide (run: python3 tools/build_ycba.py CACHE_DIR).

    data/ycba/floors.json    the lower level and floors 1 to 4 seen from above (a flat 2D plan)
    data/ycba/artworks.json  every work the museum lists as on view, on the floor where it hangs

CACHE_DIR is what tools/harvest_ycba.py saved (onview.json and the works' IIIF manifests).

The map: Louis Kahn's building is a grid of 20-foot bays, 10 bays along Chapel Street and 6 deep, with two
courts: the Entrance Court (open from floor 1 to the roof) and the Library Court (open from floor 2). The walls,
courts, stairs and elevators follow Kahn's published plans (ground, second and third floors; the fourth floor
repeats the third). Coordinates are bays: 100 units a bay, with the building from (50, 50) to (1050, 650);
High Street is on the left, Chapel Street at the bottom and the entrance at the corner of the two.
What hangs where comes from the museum: its collection search says which works are on view and in which
display (the John Constable exhibition fills the second-floor galleries, "Sightlines" the third floor, the
collection rehang "In a New Light" and the Long Gallery the fourth floor). The rooms inside each floor are drawn
by us and are approximate; so is the lower level (restrooms, lockers), which no published plan shows.
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'ycba'
SOURCE = "Louis Kahn's plans of the building (1977) and the museum's collection search (on-view works and displays)"


def B(c, r):                                  # a bay corner → map units
    return [round(50 + 100 * c), round(50 + 100 * r)]


def box(c0, r0, c1, r1):
    return [B(c0, r0), B(c1, r0), B(c1, r1), B(c0, r1)]


def poly(*pts):
    return [B(c, r) for c, r in pts]


# The east half wraps the Entrance Court; the west half wraps the Library Court.
EAST_C = poly((0, 0), (4, 0), (4, 2), (1, 2), (1, 4), (4, 4), (4, 6), (0, 6))     # opens toward the core
WEST_C = poly((5, 0), (10, 0), (10, 6), (5, 6), (5, 4), (8, 4), (8, 2), (5, 2))    # opens toward the core
CORE = box(3, 2, 5, 4)                         # landing between the courts: elevators, stairs
CORE_HIGH = box(3, 2, 6, 4)                    # floors 3 and 4: the landing takes in the round stair
ENTRANCE_COURT = box(1, 2, 3, 4)
LIBRARY_COURT = box(5, 2, 8, 4)

ELEVATOR = (500, 418)                          # same spot on every floor, so directions can change floors
CYLINDER = (612, 345)                          # Kahn's round stair in the Library Court

ROOMS = {
    'LL': [
        ('LL-hall', 'corridor', 'Lower level hall', box(3, 2, 6, 4), None),
        ('Restrooms', 'space', 'Restrooms (gender-neutral, accessible)', box(3, 4, 5, 5), None),
        ('Lockers', 'space', 'Lockers', box(5, 4, 6, 5), None),
        ('Lecture Hall LL', 'space', 'Lecture Hall (lower seats)', box(6, 2, 9.5, 4), None),
    ],
    '1': [
        ('Porch', 'corridor', 'Entrance · corner of Chapel and High Streets', box(0, 4, 2, 6), None),
        ('Entrance Court', 'corridor', 'Entrance Court · Welcome Desk · round stair', box(1, 2, 6.8, 4), None),
        ('Bookshop', 'space', 'Museum Bookshop', box(0, 1, 1, 4), None),
        ('Lecture Hall', 'space', 'Lecture Hall', box(6.8, 2, 9.5, 4), None),
        ('Shops', 'space', 'Shops on Chapel Street (not part of the museum) · Atticus Bookstore Café',
         box(2, 4, 10, 6), None),
        ('Offices', 'space', 'Offices and stairs (staff only)', poly((0, 0), (10, 0), (10, 4), (9.5, 4), (9.5, 2),
                                                                     (1, 2), (1, 1), (0, 1)), None),
    ],
    '2': [
        ('Constable', 'gallery', 'John Constable: The Landscape Reimagined · second-floor galleries', EAST_C, 'Constable'),
        ('2-core', 'corridor', 'Landing · elevators', CORE, None),
        ('Library Court', 'space', 'Library Court', LIBRARY_COURT, None),
        ('Study Room', 'space', 'Study Room (prints, drawings, rare books; Tue–Fri)', box(5, 0, 10, 2), None),
        ('Reference Library', 'space', 'Reference Library', poly((5, 4), (8, 4), (8, 2), (10, 2), (10, 6), (5, 6)), None),
    ],
    '3': [
        ('Sightlines East', 'gallery', 'Sightlines: British Landscape Photography, 1840 to Now', EAST_C, 'Sightlines'),
        ('3-core', 'corridor', 'Landing · elevators · round stair', CORE_HIGH, None),
        ('Sightlines West', 'gallery', 'Sightlines: British Landscape Photography, 1840 to Now', WEST_C, 'Sightlines'),
    ],
    '4': [
        ('1500s–1600s', 'gallery', 'In a New Light · Tudors and Stuarts, 1500s–1600s', box(0, 0, 4, 2), '1500s–1600s'),
        ('1700s', 'gallery', 'In a New Light · Georgian Britain, 1700s', poly((0, 2), (1, 2), (1, 4), (4, 4), (4, 6), (0, 6)), '1700s'),
        ('4-core', 'corridor', 'Landing · elevators · round stair', CORE_HIGH, None),
        ('Long Gallery', 'gallery', 'Long Gallery (Gallery 408)', box(5, 0, 10, 1), 'Long Gallery'),
        ('1900s–today', 'gallery', 'In a New Light · 1900s to today', poly((5, 1), (10, 1), (10, 2), (8, 2), (8, 2), (5, 2)), '1900s–today'),
        ('1800s', 'gallery', 'In a New Light · 1800s: Turner, Constable and the Victorians', poly((5, 4), (8, 4), (8, 2), (10, 2), (10, 6), (5, 6)), '1800s'),
    ],
}

LABEL_AT = {'Constable': B(2, 1), 'Sightlines East': B(2, 1), 'Sightlines West': B(7.5, 1), '1700s': B(2, 5),
            '1800s': B(7, 5), 'Reference Library': B(7, 5), 'Offices': B(5, 1), 'Entrance Court': B(3, 3)}   # C- and L-shaped rooms

DOORS = {
    'LL': [('LL-hall', 'Restrooms', B(4, 4)), ('LL-hall', 'Lockers', B(5.5, 4)), ('LL-hall', 'Lecture Hall LL', B(6, 3))],
    '1': [('Porch', 'Entrance Court', B(1.4, 4)), ('Entrance Court', 'Bookshop', B(1, 3)),
          ('Entrance Court', 'Lecture Hall', B(6.8, 3))],
    '2': [('Constable', '2-core', B(3.5, 2)), ('Constable', '2-core', B(3.5, 4)), ('2-core', 'Library Court', B(5, 3)),
          ('Library Court', 'Study Room', B(6.5, 2)), ('Library Court', 'Reference Library', B(6.5, 4))],
    '3': [('Sightlines East', '3-core', B(3.5, 2)), ('Sightlines East', '3-core', B(3.5, 4)),
          ('3-core', 'Sightlines West', B(5.5, 2)), ('3-core', 'Sightlines West', B(5.5, 4))],
    '4': [('1500s–1600s', '4-core', B(3.5, 2)), ('1700s', '4-core', B(3.5, 4)), ('1500s–1600s', '1700s', B(0.5, 2)),
          ('4-core', '1900s–today', B(5.5, 2)), ('4-core', '1800s', B(5.5, 4)), ('1900s–today', 'Long Gallery', B(7.5, 1)),
          ('1900s–today', '1800s', B(9, 2))],
}

COMMON = [('elevator', *ELEVATOR)]       # the stair towers at the ends are fire exits, not visitor routes
AMENITIES = {
    'LL': [('elevator', *ELEVATOR), ('restroom', *B(4, 4.5)), ('coat', *B(5.5, 4.5)), ('stairs', *B(5.6, 3))],
    '1': COMMON + [('entrance', *B(0.5, 5.6)), ('info', *B(3.2, 3.6)), ('shop', *B(0.5, 2.5)),
                   ('stairs', *CYLINDER), ('dining', *B(3, 5.5))],
    '2': COMMON + [('stairs', *CYLINDER)],
    '3': COMMON + [('stairs', *CYLINDER)],
    '4': COMMON + [('stairs', *CYLINDER)],
}
APPROX = 'Rooms drawn by us on Kahn’s plan: approximate'
LABELS = {
    'LL': [('Lower level: layout approximate (no published plan)', 'note', 550, 700),
           ('Restrooms and lockers are down the stairs or elevator from the Entrance Court', 'note', 550, 730)],
    '1': [('High Street', 'place', 15, 350), ('Chapel Street', 'place', 550, 700),
          (APPROX, 'note', 550, 730)],
    '2': [('Entrance Court (open below)', 'place', *B(2, 3)), ('High Street', 'place', 15, 350),
          ('Chapel Street', 'place', 550, 700), (APPROX, 'note', 550, 730)],
    '3': [('Entrance Court (open below)', 'place', *B(2, 3)), ('Library Court (open below)', 'place', *B(6.8, 3)),
          ('High Street', 'place', 15, 350), ('Chapel Street', 'place', 550, 700), (APPROX, 'note', 550, 730)],
    '4': [('Entrance Court (open below)', 'place', *B(2, 3)), ('Library Court (open below)', 'place', *B(6.8, 3)),
          ('High Street', 'place', 15, 350), ('Chapel Street', 'place', 550, 700), (APPROX, 'note', 550, 730)],
}

FLOORS = [
    ('LL', 'Lower Level', 'Restrooms · lockers · Lecture Hall', 0),
    ('1', 'Floor 1', 'Entrance Court · Welcome Desk · Museum Bookshop · Lecture Hall', 1),
    ('2', 'Floor 2', 'John Constable exhibition · Library Court · Study Room · Reference Library', 2),
    ('3', 'Floor 3', 'Sightlines: British Landscape Photography', 3),
    ('4', 'Floor 4', 'The collection: In a New Light, five centuries of British art · Long Gallery', 4),
]


def build_floors():
    floors = []
    for fid, label, area, order in FLOORS:
        rooms = []
        for rid, kind, name, pts, short in ROOMS[fid]:
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': pts}
            if kind == 'gallery': r['label'] = short or rid
            if rid in LABEL_AT: r['labelAt'] = LABEL_AT[rid]
            rooms.append(r)
        ids = {r['id'] for r in rooms}
        doors = []
        for a, b, at in DOORS[fid]:
            assert a in ids and b in ids, (fid, a, b)
            doors.append({'a': a, 'b': b, 'at': at, 'width': 8, 'axis': 'o'})
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order, 'transform': [1, 0, 0],
                       'rooms': rooms, 'closed': [],
                       'amenities': [{'type': t, 'at': [x, y]} for t, x, y in AMENITIES[fid]],
                       'labels': [{'text': t, 'kind': k, 'at': [x, y]} for t, k, x, y in LABELS[fid]],
                       'doors': doors})
    return {'about': 'Built by tools/build_ycba.py from Louis Kahn’s plans of the building and the museum’s list of '
                     'works on view. Walls, courts, stairs and elevators follow Kahn; the rooms inside each floor and '
                     'the lower level are approximate.',
            'source': SOURCE, 'units': 'pixels', 'defaultFloor': '4', 'galleryWord': 'Gallery', 'floors': floors}


# ---- works ---------------------------------------------------------------------------------------------------

def year_of(date):
    m = re.search(r'\b(1[0-9]{3}|20[0-9]{2})\b', date or '')
    return int(m[1]) if m else None


def room_of(shows, year, kind):
    s = ' '.join(shows)
    if 'John Constable: The Landscape Reimagined' in s: return 'Constable', None
    if 'Sightlines' in s: return ('Sightlines East' if (year or 1900) < 1960 else 'Sightlines West'), 'room'
    if 'Long Gallery 408' in s: return 'Long Gallery', None
    if kind == 'Photographs': return 'Sightlines West', 'room'
    if year is None: return '1700s', 'room'
    if year < 1700: return '1500s–1600s', 'room'
    if year < 1790: return '1700s', 'room'
    if year < 1900: return '1800s', 'room'
    return '1900s–today', 'room'


def meta(m):
    out = {}
    for x in m.get('metadata', []):
        k = x['label'].get('en', [''])[0]
        v = x['value'].get('en') or next(iter(x['value'].values()), [''])
        out[k] = ' '.join(v).strip()
    return out


def build_works(floors, cache):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    onview = json.loads((cache / 'onview.json').read_text())
    out, guessed = [], 0
    for oid, info in onview.items():
        f = cache / 'man' / f'{oid}.json'
        if not f.exists(): continue
        m = json.loads(f.read_text())
        md = meta(m)
        title, creator = md.get('Title', ''), md.get('Creator', '')
        label = m.get('label', {}).get('en', [''])[0]
        date = label[len(f'{creator}, {title}, '):] if label.startswith(f'{creator}, {title}, ') else ''
        if not date:
            tail = label.rsplit(', ', 1)
            date = tail[1] if len(tail) == 2 and re.search(r'\d{3}', tail[1]) else ''
        artist = creator.split(',')[0].strip()                              # "Name, 1775–1862" or "Name, born in …"
        if re.match(r'(unknown|unidentified)', artist, re.I): artist = ''
        year = year_of(date)
        g, how = room_of(info['shows'], year, info.get('type'))
        floor, gname = rooms[g]
        note = None
        if how == 'room':
            guessed += 1
            note = ('On view on this floor (from the museum’s collection search). The room is our guess from the '
                    'work’s date: the galleries roughly follow the centuries.')
        img = None
        try:
            img = m['items'][0]['items'][0]['items'][0]['body']['service'][0]['@id']
        except (KeyError, IndexError, TypeError):
            pass
        a = {'id': f'ycba-{oid}', 'title': title, 'artist': artist, 'date': date, 'year': year,
             'medium': md.get('Medium', ''), 'dimensions': md.get('Physical Description', ''),
             'accession': md.get('Call Number', ''), 'type': (info.get('type') or '').rstrip('s').replace('Drawings & Watercolor', 'Drawing or watercolor'),
             'creditLine': md.get('Credit Line', ''), 'gallery': g, 'galleryName': gname, 'floor': floor,
             'placeNote': note, 'url': f'https://collections.britishart.yale.edu/catalog/tms:{oid}'}
        if img:
            a['image'] = f'{img}/full/600,/0/default.jpg'
            a['imageCredit'] = 'Yale Center for British Art' + (', public domain' if md.get('Copyright Statement') == 'Public Domain' else '')
        out.append({k: v for k, v in a.items() if v not in (None, '')})
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: i for i, f in enumerate(floors['floors'])}
    out.sort(key=lambda a: (forder[a['floor']], order[a['gallery']], a.get('year') or 0, a['title']))
    doc = {'source': 'Yale Center for British Art collection search and IIIF manifests (records CC0); on view as of '
                     + time.strftime('%Y-%m-%d'),
           'checked': time.strftime('%Y-%m-%d'), 'count': len(out), 'complete': True, 'artworks': out}
    return doc, guessed


def main():
    cache = Path(sys.argv[1] if len(sys.argv) > 1 else 'ycba-cache')
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works, guessed = build_works(floors, cache)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{works["count"]} works ({sum(1 for a in works["artworks"] if "image" in a)} with pictures), '
          f'{guessed} with the room guessed from the date')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    main()
