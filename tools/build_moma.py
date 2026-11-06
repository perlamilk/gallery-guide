#!/usr/bin/env python3
"""Build the Museum of Modern Art (MoMA, New York) map guide (run: python3 tools/build_moma.py).

    data/moma/floors.json      every public floor seen from above (flat 2D plans)
    data/moma/artworks.json    every work MoMA lists as on view, in its gallery, with its picture
    data/moma/images/          the pictures, made smaller for phones
    data/guides/Q188740.json   the same list, for the museum page

First run tools/harvest_moma.py (MoMA's open data and the pictures) and, only if the plan changes,
tools/trace_moma.py (the rooms, from MoMA's 2025 floor plans, into tools/data/moma-plan.json).

The map
-------
Traced from MoMA's own 2025 visitor floor plans (seven drawings: floors 1-6 and the lower levels), so the shape of
every gallery, the lobbies, elevators, escalators, stairs, restrooms, cafés, stores and the four street entrances are
where the museum draws them. Room edges inside the open gallery suites (where the drawing shows no wall) were split
by the tracer and are approximate. Gallery themes change often, so rooms are named by number only.
Coordinates are the drawings' pixels (about 0.17 m each), north up (53rd Street at the bottom).

The works
---------
MoMA publishes its whole catalogue as open data (CC0) on GitHub, with an `OnView` field for each work on view
("MoMA, Floor 5, 516"). That field puts every work in its exact gallery. Works on view at MoMA PS1 (Queens) are left
out. Pictures are MoMA's own (www.moma.org/media), fetched once.
"""
import io
import json
import re
import sys
from datetime import date
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'moma'
CACHE = ROOT / '.cache' / 'moma'
MUSEUM = 'Q188740'
TODAY = date.today()
X0, Y0 = 220, 290              # drawing pixel -> map pixel
OFF = (200, 260)               # the crop the amenity points below were read in (as in trace_moma.py)
SHIFT = {1: 0, 2: 0, 3: 63, 4: 0, 5: 0, 6: 82, 7: 101}

FLOORS = [  # picture, floor id, label, order, area words
    (7, 'L', 'Lower levels', 0, 'Museum Store (level S) · Film Center and Theaters 1-2 (T1, T2) · Education Center: Theater 3 (M)'),
    (1, '1', 'Floor 1', 1, 'Lobby · tickets · Sculpture Garden · The Modern · Art Lab · street-level galleries · free to enter'),
    (2, '2', 'Floor 2', 2, 'Collection 1970s-present · Marron Atrium · Creativity Lab · Café 2 · Museum Store'),
    (3, '3', 'Floor 3', 3, 'Exhibitions: 3 North, 3 South (photography) and 3 East'),
    (4, '4', 'Floor 4', 4, 'Collection 1940s-1970s · Kravis Studio'),
    (5, '5', 'Floor 5', 5, 'Collection 1880s-1940s: The Starry Night, Les Demoiselles d’Avignon, Water Lilies'),
    (6, '6', 'Floor 6', 6, 'Special exhibitions (Cohen Center) · Terrace Café (6W)'),
]

NAMES = {   # traced room id -> (id in the app, kind, name, short label)
    'W5': ('West 5', 'corridor', 'West elevators and stairs', None),
    'S5': ('South 5', 'corridor', 'South lobby: elevators, escalators, restrooms, audio guides', None),
    'W4': ('West 4', 'corridor', 'West elevators and stairs', None),
    'S4': ('South 4', 'corridor', 'South lobby: elevators, escalators, restrooms', None),
    'Studio': ('Studio', 'gallery', 'The Marie-Josée and Henry Kravis Studio (performance, film and sound)', 'Studio'),
    'W3': ('West 3', 'corridor', 'West elevators, stairs and all-gender restrooms (Floor 3W)', None),
    'S3': ('South 3', 'corridor', 'South lobby: elevators, escalators, restrooms, lounge, charging', None),
    '3 North': ('3 North', 'gallery', '3 North: The Philip Johnson Galleries (exhibitions)', '3 North'),
    '3 South': ('3 South', 'gallery', '3 South: The Edward Steichen Galleries (photography)', '3 South'),
    '3 East': ('3 East', 'gallery', '3 East: The Robert B. Menschel Galleries (exhibitions)', '3 East'),
    'W2': ('West 2', 'corridor', 'West elevators and stairs', None),
    'N2': ('North 2', 'corridor', 'North elevators', None),
    'S2': ('South 2', 'corridor', 'South lobby: elevators, escalators, restrooms, audio desk', None),
    'E2': ('East 2', 'corridor', 'East elevators and stairs · way to the Education and Research Building', None),
    'Atrium': ('Atrium', 'gallery', 'The Donald B. and Catherine C. Marron Family Atrium', 'Atrium'),
    'Creativity Lab': ('Creativity Lab', 'space', 'The Paula and James Crown Creativity Lab (hands-on, free)', 'Creativity Lab'),
    'Store': ('Store 2', 'space', 'Museum Store and Bookstore · lounge · charging · espresso bar', 'Store'),
    'Cafe 2': ('Café 2', 'space', 'Café 2 (Italian-inspired; wine and beer)', 'Café 2'),
    '2 South': ('2 South', 'gallery', '2 South: The Paul J. Sachs Galleries (prints and drawings)', '2 South'),
    '1 North': ('1 North', 'gallery', '1 North: street-level gallery (free)', '1 North'),
    '1 South': ('1 South', 'gallery', '1 South: street-level gallery (free)', '1 South'),
    'Sculpture Garden': ('Sculpture Garden', 'gallery', 'The Abby Aldrich Rockefeller Sculpture Garden', 'Sculpture Garden'),
    'Lobby': ('Lobby', 'corridor', 'Lobby: tickets, checkroom, information, from 53rd to 54th Street', 'Lobby'),
    'East Lobby': ('East Lobby', 'corridor', 'East lobby: film desk, member reception, way down to the Film Center', None),
    'The Modern': ('The Modern', 'space', 'The Modern (restaurant and Bar Room)', 'The Modern'),
    'E1': ('East 1', 'corridor', 'Art Lab (The Samuel and Ronnie Heyman Family Art Lab) · east elevators · Education, '
                                 'Library and School Group Entrance', 'Art Lab'),
    '6': ('6', 'gallery', 'The Steven and Alexandra Cohen Center for Special Exhibitions', 'Special exhibitions'),
    'N6': ('North 6', 'corridor', 'North elevators, escalator, exhibition store, restrooms', None),
    'Terrace Cafe': ('Terrace Café', 'space', 'The Carroll and Milton Petrie Terrace Café (6W: west elevators and stairs)',
                     'Terrace Café'),
    'Museum Store': ('Museum Store', 'space', 'Museum Store, level S (stairs and elevator from the west lobby)', 'Store'),
    'Theater 2': ('Theater 2', 'space', 'The Roy and Niuta Titus Theater 2 (level T2)', 'Theater 2'),
    'Theater 1': ('Theater 1', 'space', 'The Roy and Niuta Titus Theater 1 (level T1)', 'Theater 1'),
    'Film Center': ('Film Center', 'corridor', 'The Debra and Leon Black Family Film Center (escalators from Floor 1)',
                    'Film Center'),
    'Theater 3': ('Theater 3', 'space', 'The Celeste Bartos Theater 3 (Education Center, level M)', 'Theater 3'),
    'Tisch Atrium': ('Tisch Atrium', 'corridor', 'The Joan H. Tisch Atrium (Education Center, level M)', None),
}

# amenities: (type, crop x, crop y), read off the drawings
AMEN = {
    5: [('elevator', 740, 85), ('elevator', 762, 288), ('elevator', 332, 412), ('stairs', 765, 325),
        ('stairs', 512, 253), ('stairs', 355, 465), ('info', 720, 288), ('info', 368, 403),
        ('restroom-all', 878, 265), ('restroom', 871, 378)],
    4: [('elevator', 738, 85), ('elevator', 762, 288), ('elevator', 327, 412), ('stairs', 762, 323),
        ('stairs', 512, 256), ('stairs', 352, 466), ('info', 718, 288), ('info', 366, 404), ('restroom', 870, 378)],
    3: [('elevator', 738, 148), ('elevator', 762, 350), ('elevator', 330, 476), ('stairs', 762, 388),
        ('stairs', 352, 528), ('stairs', 942, 535), ('info', 718, 350), ('restroom-all', 262, 377),
        ('restroom', 870, 442)],
    2: [('elevator', 735, 85), ('elevator', 758, 288), ('elevator', 327, 412), ('elevator', 1450, 210),
        ('stairs', 760, 325), ('stairs', 727, 232), ('stairs', 350, 465), ('stairs', 940, 474), ('stairs', 1462, 265),
        ('info', 705, 289), ('info', 363, 403), ('restroom', 866, 378), ('dining', 1227, 407), ('dining', 1160, 320),
        ('shop', 1001, 395)],
    1: [('elevator', 736, 85), ('elevator', 758, 288), ('elevator', 326, 413), ('elevator', 508, 482),
        ('elevator', 1453, 230), ('stairs', 760, 323), ('stairs', 815, 225), ('stairs', 510, 435), ('stairs', 348, 485),
        ('stairs', 940, 475), ('stairs', 1012, 290), ('stairs', 1497, 258), ('stairs', 1460, 105),
        ('info', 853, 320), ('info', 497, 313), ('restroom-all', 850, 405), ('coat', 519, 219), ('coat', 884, 483),
        ('dining', 1068, 340), ('shop', 395, 485), ('entrance', 617, 503), ('entrance', 615, 52),
        ('entrance', 1134, 503), ('entrance', 1514, 52)],
    6: [('elevator', 738, 187), ('elevator', 210, 495), ('stairs', 735, 277), ('stairs', 235, 528),
        ('restroom-all', 137, 365), ('restroom', 738, 487), ('dining', 110, 510), ('shop', 778, 268)],
    7: [('elevator', 362, 510), ('stairs', 380, 428), ('restroom-all', 168, 498), ('shop', 228, 435),
        ('stairs', 850, 303), ('stairs', 773, 408), ('restroom-all', 880, 548), ('elevator', 1455, 333),
        ('stairs', 1422, 217), ('restroom-all', 1365, 172)],
}

LABELS = {
    1: [('West 54th Street', 'area', 615, 20), ('West 53rd Street', 'area', 617, 545),
        ('54 Street Entrance', 'note', 615, 35), ('53 Street Entrance (main; the lobby runs through to 54 Street)', 'note', 617, 525),
        ('Member, Film, and Administrative Entrance', 'note', 1134, 525),
        ('Education, Library, and School Group Entrance (4 West 54 St)', 'note', 1514, 35),
        ('Floor 1 is free and open to all: lobby, Sculpture Garden, street-level galleries, store', 'note', 300, 570)],
    2: [('Access to the Education and Research Building', 'note', 1265, 220)],
    3: [('3W: offices (not open) · west elevators reach the all-gender restrooms', 'note', 120, 600)],
    6: [('6W: Terrace Café, by the west elevator and stair', 'note', 120, 610)],
    7: [('S: Museum Store', 'area', 70, 190), ('T1 · T2: Film Center', 'area', 545, 190),
        ('M: Education Center', 'area', 1230, 190),
        ('Three separate lower levels, each reached from Floor 1', 'note', 600, 600)],
}


# rooms that meet where the tracer found no opening (an open hall drawn with a line, or a doorway under a label)
EXTRA_DOORS = {2: [('North 2', 'South 2')], 7: [('Theater 1', 'Film Center')]}
# Floor 6W (the Terrace Café) is drawn as a squeezed side panel: move it east so its west elevator and stair line up
# with the west elevator and stairs on the floors below
SHIFT_6W = 122


def nearest_midpoint(pa, pb):
    best = min(((a, b) for a in pa for b in pb), key=lambda ab: (ab[0][0] - ab[1][0]) ** 2 + (ab[0][1] - ab[1][1]) ** 2)
    return [round((best[0][0] + best[1][0]) / 2), round((best[0][1] + best[1][1]) / 2)]


def to_map(n, cx, cy):
    """Crop point on picture n -> map pixel (frames lined up)."""
    if n == 6 and cx < 290: cx += SHIFT_6W
    return [cx + OFF[0] - X0, cy + OFF[1] - SHIFT[n] - Y0]


def shift6w(n, poly):
    if n != 6 or max(x for x, _ in poly) > 300 + OFF[0]: return poly
    return [[x + SHIFT_6W, y] for x, y in poly]


def build_floors():
    plan = json.loads((ROOT / 'tools' / 'data' / 'moma-plan.json').read_text())
    floors = []
    for n, fid, label, order, area in FLOORS:
        p = plan[str(n)]
        rooms, rename = [], {}
        for r in p['rooms']:
            rid, kind, name, short = NAMES.get(r['id'], (r['id'], r['kind'], f'Gallery {r["id"]}', r['id']))
            rename[r['id']] = rid
            room = {'id': rid, 'kind': kind, 'name': name,
                    'poly': [[x - X0, y - Y0] for x, y in shift6w(n, r['poly'])]}
            if short: room['label'] = short
            rooms.append(room)
        doors, seen = [], set()
        for d in sorted(p['doors'], key=lambda d: -d['size']):
            a, b = rename[d['a']], rename[d['b']]
            key = (a, b, round(d['at'][0] / 40), round(d['at'][1] / 40))
            if key in seen: continue
            seen.add(key)
            doors.append({'a': a, 'b': b, 'at': [d['at'][0] - X0, d['at'][1] - Y0], 'width': 12, 'axis': 'o'})
        by_id = {r['id']: r for r in rooms}
        for a, b in EXTRA_DOORS.get(n, []):
            doors.append({'a': a, 'b': b, 'at': nearest_midpoint(by_id[a]['poly'], by_id[b]['poly']), 'width': 12,
                          'axis': 'o'})
        closed = [{'id': f'building-{fid}-{i}', 'kind': 'closed', 'poly': [[x - X0, y - Y0] for x, y in o]}
                  for i, o in enumerate(p['outline'])]
        floors.append({
            'id': fid, 'label': label, 'order': order, 'transform': [1, 0, 0], 'area': area,
            'rooms': rooms, 'closed': closed,
            'amenities': [{'type': t, 'at': to_map(n, x, y)} for t, x, y in AMEN[n]],
            'labels': [{'text': t, 'kind': k, 'at': to_map(n, x, y)} for t, k, x, y in LABELS.get(n, [])],
            'doors': doors,
        })
    return {'about': 'Built by tools/build_moma.py from MoMA’s own 2025 visitor floor plans (traced by '
                     'tools/trace_moma.py). Room edges inside open gallery suites are approximate.',
            'source': 'MoMA visitor floor plans (2025)', 'units': 'plan pixels (about 0.17 m), north up',
            'approximate': False, 'defaultFloor': '5', 'galleryWord': 'Gallery', 'floors': floors}


# ---- works ---------------------------------------------------------------------------------------------------

def place(onview):
    """'"MoMA, Floor 5, 516"' -> (floor, room id, note)."""
    m = re.match(r'"MoMA, Floor (\d)(?:, (.+))?"$', onview)
    if not m: return None
    fl, room = m[1], m[2]
    if room == 'Podium': return fl, 'Atrium', 'On the podium in the Marron Atrium'
    if room: return fl, room, None
    fallback = {'1': 'Lobby', '2': 'Atrium', '3': 'South 3', '4': 'South 4', '5': 'South 5', '6': '6'}[fl]
    note = None if fl == '6' else f'Somewhere on Floor {fl}: MoMA does not say which gallery'
    return fl, fallback, note


def year_of(d):
    m = re.search(r'\b(1[5-9]\d\d|20[0-2]\d)\b', d or '')
    return int(m[1]) if m else None


def picture(oid):
    src = CACHE / 'img' / f'{oid}.jpg'
    if not src.exists(): return None
    dest = OUT / 'images' / f'moma-{oid}.jpg'
    if not dest.exists():
        try: im = Image.open(io.BytesIO(src.read_bytes()))
        except Exception: return None
        if im.mode in ('RGBA', 'LA', 'P'):
            im = im.convert('RGBA'); bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=im.split()[3]); im = bg
        im = im.convert('RGB')
        im.thumbnail((640, 640))
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, 'JPEG', quality=72, optimize=True, progressive=True)
    return f'data/moma/images/moma-{oid}.jpg'


def clean(s):
    return re.sub(r'\s+', ' ', (s or '').replace('\r', ' ')).strip()


def build_works(rooms_by_id):
    data = json.loads((CACHE / 'Artworks.json').read_text())
    out = []
    for w in data:
        p = place(w.get('OnView') or '')
        if not p: continue
        fl, room, note = p
        assert room in rooms_by_id, (room, w['OnView'])
        artists = [a for a in (w.get('Artist') or []) if a]
        bios = [clean(b) for b in (w.get('ArtistBio') or []) if b]
        artist = ', '.join(dict.fromkeys(artists)) or None
        details = ' · '.join(dict.fromkeys(f'{a} ({b.strip("()")})' if len(artists) > 1 else b.strip('()')
                                           for a, b in zip(artists, bios) if b)) or None
        im = picture(w['ObjectID'])
        a = {'id': f'moma-{w["ObjectID"]}', 'title': clean(w['Title']) or 'Untitled', 'artist': artist,
             'artistDetails': details, 'date': clean(w.get('Date')) or None, 'year': year_of(w.get('Date')),
             'medium': clean(w.get('Medium')) or None, 'dimensions': clean(w.get('Dimensions')) or None,
             'type': w.get('Classification') if w.get('Classification') != '(not assigned)' else None,
             'department': w.get('Department'), 'accession': w.get('AccessionNumber'),
             'creditLine': clean(w.get('CreditLine')) or None, 'onView': True,
             'gallery': room, 'galleryName': None if room.isdigit() else rooms_by_id[room]['name'], 'floor': fl,
             'placeNote': note,
             'url': w.get('URL'), 'image': im, 'imageCredit': im and 'The Museum of Modern Art'}
        out.append({k: v for k, v in a.items() if v not in (None, '')})
    order = {f['id']: f['order'] for f in FLOORS_OUT}
    out.sort(key=lambda a: (-order.get(a['floor'], 0), a['gallery'], a.get('artist') or '', a.get('year') or 0))
    return {'source': 'The Museum of Modern Art collection data (github.com/MuseumofModernArt/collection, CC0), '
                      'works marked on view', 'checked': TODAY.isoformat(), 'count': len(out), 'complete': True,
            'artworks': out}


def build_guide(works):
    rows = [{k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a.get('artist'), 'date': a.get('date'),
                               'year': a.get('year'), 'medium': a.get('medium'), 'url': a.get('url'),
                               'imageUrl': a.get('image'), 'onView': True, 'gallery': a['gallery'],
                               'floor': a['floor']}.items() if v not in (None, '')} for a in works['artworks']]
    return {'museum': MUSEUM, 'name': 'The Museum of Modern Art', 'checked': TODAY.isoformat(),
            'source': 'MoMA collection open data (GitHub, CC0); MoMA 2025 floor plans', 'onViewKnown': True,
            'note': f'MoMA’s collection holds about 200,000 works; its open data lists {len(rows):,} of them on view in '
                    f'the galleries in Midtown, each with its gallery. The collection galleries run from the 1880s on '
                    f'Floor 5 (The Starry Night, Les Demoiselles d’Avignon, Water Lilies) down to today on Floor 2.',
            'works': rows}


FLOORS_OUT = []


def main():
    if not (CACHE / 'Artworks.json').exists():
        raise SystemExit('run tools/harvest_moma.py first')
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    FLOORS_OUT.extend(floors['floors'])
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    rooms = {r['id']: r for f in floors['floors'] for r in f['rooms']}
    works = build_works(rooms)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': len(guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    print(f'{works["count"]} works, {sum("image" in a for a in works["artworks"])} with pictures; '
          f'{sum(len(f["rooms"]) for f in floors["floors"])} rooms on {len(floors["floors"])} floors')


if __name__ == '__main__':
    sys.exit(main())
