#!/usr/bin/env python3
"""Build the Yale Center for British Art map guide (run: python3 tools/build_ycba.py CACHE_DIR).

    data/ycba/floors.json    the lower level and floors 1 to 4 seen from above (a flat 2D plan)
    data/ycba/artworks.json  every work the museum lists as on view, on the floor where it hangs

CACHE_DIR is what tools/harvest_ycba.py saved (onview.json and the works' IIIF manifests).

The map: Louis Kahn's building is a grid of 20-foot bays, 10 bays along Chapel Street and 6 deep, with two
courts: the Entrance Court (open from floor 1 to the roof) and the Library Court (open from floor 2). Walls, rooms,
courts, stairs, elevators, restrooms, lockers, the Welcome Desk and the shop are traced from the museum's own floor
plans in its Bloomberg Connects guide (captured on Grazi's Mac, Nov 11 2026). Coordinates are bays: 100 units a
bay, with the building from (50, 50) to (1050, 650); High Street is on the left, Chapel Street at the bottom and the
entrance at the corner of the two. What hangs where comes from the museum: its collection search says which works
are on view and in which display (the John Constable exhibition fills the second-floor galleries, "Sightlines" the
third floor, the collection rehang "In a New Light" and the Long Gallery the fourth floor). The app shows the fourth
floor as one "Permanent Collection Galleries" space; splitting it by century is ours.

    python3 tools/build_ycba.py --floors-only   redraws the map and moves the saved works onto it (no cache needed)
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'ycba'
SOURCE = "The museum's floor plans in its Bloomberg Connects guide (Nov 2026) and its collection search (on-view works and displays)"


def B(c, r):                                  # a bay corner → map units
    return [round(50 + 100 * c), round(50 + 100 * r)]


def box(c0, r0, c1, r1):
    return [B(c0, r0), B(c1, r0), B(c1, r1), B(c0, r1)]


def poly(*pts):
    return [B(c, r) for c, r in pts]


# Traced from the museum's own floor plans in its Bloomberg Connects guide (captured Nov 11 2026). The app draws the
# building upright with Chapel Street on the right and High Street at the bottom; here it is turned a quarter turn so
# High Street is on the left and Chapel Street at the bottom, as before. Bay c runs from High Street (0) to the far
# end (10), bay r from the north side (0) to Chapel Street (6).
ENTRANCE_COURT = box(1.06, 2, 3.0, 4)          # open from floor 1 to the roof
LIBRARY_COURT = box(5.09, 2, 8, 4)             # open from floor 2 to the roof
CORE = box(4.04, 2.6, 5.09, 3.8)               # the short hall between the courts: elevators
CORE_HIGH = box(4.04, 2.6, 6.4, 3.8)           # floors 3 and 4: the hall takes in the round stair

ELEVATOR = B(4.6, 3.55)                        # same spot on every floor, so directions can change floors
CYLINDER = B(5.62, 3.0)                        # Kahn's round stair at the Library Court

ROOMS = {
    'LL': [
        ('LL-hall', 'corridor', 'Lower level hall · elevators', CORE, None),
        ('Restrooms', 'space', 'Restrooms (men’s and women’s) around the round stair', box(5.04, 2, 6.38, 4), None),
        ('Lockers', 'space', 'Lockers · all-gender restrooms', box(3.62, 2, 4.04, 4), None),
    ],
    '1': [
        ('Porch', 'corridor', 'Entrance Portico · corner of Chapel and High Streets', box(0, 4, 2, 6), None),
        ('Entrance Court', 'corridor', 'Entrance Court · Welcome Desk · Museum Shop',
         poly((1.2, 2), (3.15, 2), (3.15, 1.5), (4, 1.5), (4, 2.6), (5, 2.6), (5, 2), (6.4, 2), (6.4, 4), (1.2, 4)), None),
        ('Classroom 1', 'space', 'Classroom', box(3.15, 0, 4, 1.5), None),
        ('Lecture Hall', 'space', 'Lecture Hall', box(6.4, 2, 9.4, 4), None),
        ('Shops', 'space', 'Shops on Chapel Street (not part of the museum) · Atticus Bookstore Café',
         box(2, 4, 10, 6), None),
        ('Offices', 'space', 'Offices (staff only)', poly((0, 0), (3.15, 0), (3.15, 2), (1.2, 2), (1.2, 4), (0, 4)), None),
        ('Offices E', 'space', 'Offices (staff only)', poly((4, 0), (10, 0), (10, 4), (9.4, 4), (9.4, 2), (5, 2),
                                                            (5, 2.6), (4, 2.6)), None),
    ],
    '2': [
        ('Constable', 'gallery', 'John Constable: The Landscape Reimagined · Exhibition Galleries',
         box(0, 1, 4.04, 6), 'Constable'),
        ('Classroom 2', 'space', 'Classroom', box(2.55, 0, 4.04, 1), None),
        ('2-core', 'corridor', 'Hall · elevators', CORE, None),
        ('Library Court', 'space', 'Library Court · round stair', LIBRARY_COURT, None),
        ('Reference Library', 'space', 'Reference Library', box(5.09, 0, 8, 2), None),
        ('Study Room', 'space', 'Study Room (prints, drawings, rare books; Tue–Fri)', box(5.09, 4, 8, 6), None),
    ],
    '3': [
        ('Sightlines', 'gallery', 'Sightlines: British Landscape Photography, 1840 to Now · Exhibition Galleries',
         box(0, 0.8, 4.04, 5.02), 'Sightlines'),
        ('3-core', 'corridor', 'Hall · elevators · round stair', CORE_HIGH, None),
    ],
    '4': [
        ('1500s–1600s', 'gallery', 'In a New Light · Tudors and Stuarts, 1500s–1600s',
         poly((0, 1.05), (5.09, 1.05), (5.09, 2), (4.04, 2), (4.04, 3), (3.0, 3), (3.0, 2), (1.06, 2), (1.06, 3), (0, 3)),
         '1500s–1600s'),
        ('1700s', 'gallery', 'In a New Light · Georgian Britain, 1700s',
         poly((0, 3), (1.06, 3), (1.06, 4), (3.0, 4), (3.0, 3), (4.04, 3), (4.04, 4), (5.09, 4), (5.09, 5.02),
              (4.96, 5.02), (4.96, 6), (0, 6)), '1700s'),
        ('4-core', 'corridor', 'Hall · elevators · round stair', CORE_HIGH, None),
        ('Long Gallery', 'gallery', 'Long Gallery (Gallery 408)', box(1.99, 0, 8.92, 1.05), 'Long Gallery'),
        ('Classroom 4', 'space', 'Classroom', box(0.97, 0, 1.99, 1.05), None),
        ('1800s', 'gallery', 'In a New Light · 1800s: Turner, Constable and the Victorians',
         poly((5.09, 1.05), (8.92, 1.05), (8.92, 4), (8, 4), (8, 2), (5.09, 2)), '1800s'),
        ('1900s–today', 'gallery', 'In a New Light · 1900s to today', box(5.09, 4, 8.92, 5.02), '1900s–today'),
    ],
}

HOLES = {'Constable': [ENTRANCE_COURT], 'Sightlines': [ENTRANCE_COURT]}   # the Entrance Court is open below

LABEL_AT = {'Constable': B(2, 5), 'Sightlines': B(2, 4.5), '1500s–1600s': B(2, 1.5), '1700s': B(2, 5),
            '1800s': B(7, 1.5), 'Offices': B(0.6, 1), 'Offices E': B(7, 1), 'Entrance Court': B(2.2, 3)}

DOORS = {
    'LL': [('LL-hall', 'Restrooms', B(5.04, 3.2)), ('LL-hall', 'Lockers', B(4.04, 3.2))],
    '1': [('Porch', 'Entrance Court', B(1.6, 4)), ('Entrance Court', 'Classroom 1', B(3.6, 1.5)),
          ('Entrance Court', 'Lecture Hall', B(6.4, 3))],
    '2': [('Constable', '2-core', B(4.04, 3.2)), ('2-core', 'Library Court', B(5.09, 3.2)),
          ('Library Court', 'Reference Library', B(6.5, 2)), ('Library Court', 'Study Room', B(6.5, 4)),
          ('Constable', 'Classroom 2', B(3.3, 1))],
    '3': [('Sightlines', '3-core', B(4.04, 3.2))],
    '4': [('1500s–1600s', '4-core', B(4.04, 2.8)), ('1700s', '4-core', B(4.04, 3.5)),
          ('1500s–1600s', '1700s', B(0.5, 3)), ('1500s–1600s', '1700s', B(3.5, 3)),
          ('1500s–1600s', 'Long Gallery', B(2.3, 1.05)), ('1500s–1600s', 'Classroom 4', B(1.5, 1.05)),
          ('1500s–1600s', '1800s', B(5.09, 1.5)), ('1700s', '1900s–today', B(5.09, 4.5)),
          ('1800s', '1900s–today', B(8.46, 4))],
}

COMMON = [('elevator', *ELEVATOR), ('stairs', *CYLINDER)]   # the stair towers at the ends are fire exits
AMENITIES = {
    'LL': COMMON + [('restroom', *B(6.03, 2.44)), ('restroom', *B(6.03, 3.59)), ('restroom', *B(3.83, 2.22)),
                    ('restroom', *B(3.83, 3.77)), ('coat', *B(3.83, 3.0))],
    '1': COMMON + [('entrance', *B(0.6, 5.4)), ('info', *B(3.56, 2.15)), ('shop', *B(3.56, 3.36)),
                   ('dining', *B(3, 5.5))],
    '2': COMMON,
    '3': COMMON,
    '4': COMMON,
}
STREETS = [('High Street', 'place', 15, 350), ('Chapel Street', 'place', 550, 700)]
SRC = 'Plan: the museum’s own floor plans (Bloomberg Connects guide)'
LABELS = {
    'LL': [('Restrooms and lockers: take the round stair or the elevators down from the Entrance Court', 'note', 550, 730)],
    '1': STREETS + [(SRC, 'note', 550, 730)],
    '2': STREETS + [('Entrance Court (open below)', 'place', *B(2.03, 3)), (SRC, 'note', 550, 730)],
    '3': STREETS + [('Entrance Court (open below)', 'place', *B(2.03, 3)), ('Library Court (open below)', 'place', *B(7, 3)),
                    (SRC, 'note', 550, 730)],
    '4': STREETS + [('Entrance Court (open below)', 'place', *B(2.03, 3)), ('Library Court (open below)', 'place', *B(7, 3)),
                    ('Rooms inside the Permanent Collection Galleries are split by century by us', 'note', 550, 760),
                    (SRC, 'note', 550, 730)],
}

FLOORS = [
    ('LL', 'Lower Level', 'Restrooms · lockers', 0),
    ('1', 'Floor 1', 'Entrance Court · Welcome Desk · Museum Shop · Lecture Hall', 1),
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
            if rid in HOLES: r['holes'] = HOLES[rid]
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
    return {'about': 'Built by tools/build_ycba.py from the museum’s own floor plans (its Bloomberg Connects guide) '
                     'and its list of works on view. The century rooms on floor 4 are our split of the Permanent '
                     'Collection Galleries.',
            'source': SOURCE, 'units': 'pixels', 'defaultFloor': '4', 'galleryWord': 'Gallery', 'floors': floors}


# ---- works ---------------------------------------------------------------------------------------------------

def year_of(date):
    m = re.search(r'\b(1[0-9]{3}|20[0-9]{2})\b', date or '')
    return int(m[1]) if m else None


def room_of(shows, year, kind):
    s = ' '.join(shows)
    if 'John Constable: The Landscape Reimagined' in s: return 'Constable', None
    if 'Sightlines' in s: return 'Sightlines', None
    if 'Long Gallery 408' in s: return 'Long Gallery', None
    if kind == 'Photographs': return 'Sightlines', 'room'
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


MOVED = {'Sightlines East': 'Sightlines', 'Sightlines West': 'Sightlines'}   # rooms from the earlier map


def floors_only(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    path = OUT / 'artworks.json'
    doc = json.loads(path.read_text())
    for a in doc['artworks']:
        g = MOVED.get(a['gallery'], a['gallery'])
        if g == 'Sightlines' and a.get('placeNote', '').startswith('On view on this floor'): a.pop('placeNote')
        a['gallery'], (a['floor'], a['galleryName']) = g, rooms[g]
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(',', ':')))
    print(f"{doc['count']} works moved onto the new map")


def main():
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    if sys.argv[1:2] == ['--floors-only']: return floors_only(floors)
    cache = Path(sys.argv[1] if len(sys.argv) > 1 else 'ycba-cache')
    works, guessed = build_works(floors, cache)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{works["count"]} works ({sum(1 for a in works["artworks"] if "image" in a)} with pictures), '
          f'{guessed} with the room guessed from the date')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    main()
