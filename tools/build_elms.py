#!/usr/bin/env python3
"""Build The Elms (Newport, RI) map guide (run: python3 tools/harvest_elms.py, then this).

    data/elms/floors.json         the grounds and every floor of the house, seen from above (flat 2D, north up)
    data/elms/artworks.json       the house's objects, each in its room
    data/elms/images/             their pictures, made smaller for phones
    data/guides/Q7731834.json     the same objects, for the museum page

Where the information comes from
--------------------------------
The map
  - Grounds (floor G): OpenStreetMap (www.openstreetmap.org/api/0.6/map, cached in .cache/elms/osm.xml): the house
    (way 371945275), the grounds inside their wall (1474182186), the Carriage House (1474182182), the visitor parking
    by the house (1373931635), Bellevue Avenue (440717074), Bellevue Court (19357135) and the hedges of the Sunken
    Garden. Metres east/north of the house (41.47781 N, 71.30892 W). The Sunken Garden, the marble pavilions, the
    Grand Allée and the fountains are placed from the "Sketch map, The Elms" (Preservation Society, Aug. 1992) in the
    National Historic Landmark nomination. The Society's accessibility page gives the distances and the restrooms.
  - House floors 1, 2 and 3: traced from the measured plans in The Elms' National Historic Landmark nomination
    (preservation.ri.gov .../newp_bellevue-avenue_the-elms.pdf: page 19 first floor, 20 second floor, 25 third floor;
    drawn for the Preservation Society in 1994). Units: pixels of the pages at 110 dpi. The plans put the front
    (Bellevue Avenue, east) at the top and north on the left; we turn them a quarter turn so north is up, like the
    grounds. The plans name the rooms as built (Palm Room, Drawing Room); the map uses today's names (Conservatory,
    Salon) and gives the plan's name too.
  - Basement (floor B): no plan of the basement is published. The Society says the restrooms are down there (14 stairs
    from the entryway) and the tour ends there; the kitchen, laundry and the coal tunnel are on the Servant Life Tour.
    Only the house outline is drawn; the places inside it are approximate.
  - The house reopens on November 16, 2026 as "The Elms Experience" (timed tickets). The Society hasn't said which
    rooms the new route uses, so the map shows the house as it stands, and says so.

The objects
  The Preservation Society's Digital Collections (see tools/harvest_elms.py): objects that name The Elms or came from
  the Berwind family, who built the house (1899-1901) and lived in it until Julia Berwind's death in 1961. Rooms come
  from each record's own text; objects whose room no source gives are listed on the museum page but not put on the
  map.
"""
import html
import io
import json
import math
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'elms'
CACHE = ROOT / '.cache' / 'elms'
MUSEUM = 'Q7731834'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
COLL = 'https://newportmansions.rediscoverysoftware.com/'
APPROX = 'Approximate'

# ---- grounds (floor G) ----------------------------------------------------------------------------------------------

LAT0, LON0 = 41.47781, -71.30892
K = 2.4                     # map units per metre on the grounds


def G(x, y):
    """Metres east/north of the house -> map units (north up)."""
    return [round((x + 250) * K, 1), round((150 - y) * K, 1)]


def osm():
    f = CACHE / 'osm.xml'
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = 'https://www.openstreetmap.org/api/0.6/map?bbox=-71.3110,41.4755,-71.3050,41.4800'
        out = subprocess.run(['curl', '-s', '-f', '-m', '90', '-A', UA, url], capture_output=True).stdout
        if not out: raise SystemExit('OpenStreetMap did not answer')
        f.write_bytes(out)
    root = ET.parse(f).getroot()
    nodes = {n.get('id'): (float(n.get('lat')), float(n.get('lon'))) for n in root.iter('node')}
    ways = {}
    for w in root.iter('way'):
        pts = []
        for nd in w.findall('nd'):
            if nd.get('ref') not in nodes: continue
            lat, lon = nodes[nd.get('ref')]
            pts.append(((lon - LON0) * 111320 * math.cos(math.radians(LAT0)), (lat - LAT0) * 110540))
        ways[w.get('id')] = pts
    return ways


def band(pts, half=3.0):
    """A street drawn as a band `half` metres either side of its line."""
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        nx, ny = -dy / n * half, dx / n * half
        left.append((x + nx, y + ny)); right.append((x - nx, y - ny))
    return left + right[::-1]


def inside(pts, y0=-150, y1=140):
    return [p for p in pts if y0 <= p[1] <= y1]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def grounds(ways):
    rooms = [
        ('Grounds', 'space', 'The Elms grounds: the front lawn on Bellevue Avenue, the terraces and the great lawn '
                             'down to the Sunken Garden', ways['1474182186'][:-1]),
        ('The Elms', 'space', 'The Elms (1901): the house tour. Pick floor 1, 2, 3 or B above to see the rooms',
         ways['371945275'][:-1]),
        ('Sunken Garden', 'gallery', 'Sunken Garden, with the two marble pavilions, the Grand Allée and the fountains '
                                   '(outline from its wall in OpenStreetMap)', ways['1474182183'][:-1]),
        ('Carriage House', 'space', 'Carriage House at The Elms (1901, restored 2025): Museum Café, 11 am–5 pm (last '
                                    'seating 4 pm), indoor and outdoor tables; accessible', ways['1474182182'][:-1]),
        ('Parking', 'space', 'Visitor parking (free, 4 accessible spaces), next to the house: about 116 m (382 ft) '
                             'to the front door', ways['1373931635'][:-1]),
        ('Bellevue Avenue', 'corridor', 'Bellevue Avenue: the main gates and the circular drive',
         band(inside(ways['440717074']), 5)),
        ('Bellevue Court', 'corridor', 'Bellevue Court: bus parking; about 227 m (746 ft) and 6 steps to the front door',
         band(ways['19357135'], 4)),
    ]
    doors = [('Parking', 'Grounds', (0, -48)), ('Bellevue Avenue', 'Grounds', (45, -32)),
             ('Bellevue Avenue', 'Grounds', (48, 52)), ('Grounds', 'The Elms', (21, 0)),
             ('Grounds', 'Carriage House', (-163, 66)), ('Grounds', 'Sunken Garden', (-160, -40)),
             ('Bellevue Court', 'Grounds', (-60, 70))]
    amen = [('entrance', 25, 0), ('dining', -186, 67), ('entrance', -10, 27)]
    labels = [('P · Parking (free)', 'area', 0, -100), ('Main gates', 'area', 75, -40),
              ('Front door: 7 steps up', 'area', 45, 10), ('Exit (place approximate)', 'area', -10, 35),
              ('Great lawn and terraces', 'area', -80, -15), ('Grand Allée and the marble pavilions', 'area', -170, 10),
              ('Carriage House Café', 'area', -186, 95), ('Bus parking: Bellevue Court', 'area', -60, 88),
              ('Restrooms: in the house basement', 'area', 0, -30)]
    return rooms, [], doors, amen, labels


# ---- the house -------------------------------------------------------------------------------------------------------
# Units: pixels (110 dpi) of the 1994 plans in the National Historic Landmark nomination. On the plans the front door
# (east, Bellevue Avenue) is at the top and north is on the left; R() turns them so north is up.

TB = 'the 1994 plans in the National Historic Landmark nomination'
HOUSE_1 = [
    ('Main Hall', 'gallery', 'Main Hall: the front stair hall and the long Gallery Hall with its two alcoves, '
                             'in Louis XV style',
     [(405, 200), (575, 200), (575, 262), (680, 262), (680, 380), (330, 380), (330, 262), (405, 262)], 'Main Hall'),
    ('Ballroom', 'gallery', 'Ballroom: the centre of the house, opening onto the garden terrace',
     [(405, 380), (575, 380), (575, 590), (405, 590)], 'Ballroom'),
    ('Salon', 'gallery', 'Salon: the Louis XVI drawing room (the plan’s “Drawing Room”)', rect(575, 380, 680, 535),
     'Salon'),
    ('Conservatory', 'gallery', 'Conservatory: marble floors, fountains and plants (the plan’s “Palm Room”)',
     rect(680, 380, 785, 535), 'Conservatory'),
    ('Library', 'gallery', 'Library: carved walnut panelling and a Renaissance-style fireplace', rect(680, 262, 785, 380),
     'Library'),
    ('Dining Room', 'gallery', 'Dining Room: the Berwinds’ formal dining room, with Venetian paintings', rect(330, 380, 405, 535),
     'Dining Room'),
    ('Breakfast Room', 'gallery', 'Breakfast Room: Chinese lacquer panels (1662-1722) set into the walls',
     rect(210, 450, 330, 535), 'Breakfast Room'),
    ('Butler’s Pantry', 'space', 'Butler’s Pantry', rect(210, 380, 330, 450), None),
    ('Garden Terrace', 'gallery', 'Upper terrace on the garden side, with marble statues, and the steps down to the '
                                  'great lawn', rect(395, 590, 585, 690), 'Terrace'),
    ('North Terrace', 'space', 'North terrace', rect(135, 255, 205, 545), None),
    ('South Terrace', 'gallery', 'South terrace, next to the Conservatory', rect(790, 255, 850, 545), 'Terrace'),
    ('Front Steps', 'space', 'The front steps: the way in from the drive on Bellevue Avenue', rect(420, 155, 560, 200),
     None),
]
HOUSE_1_CLOSED = [rect(210, 262, 330, 380)]                                # coat room and the service stairs
HOUSE_1_DOORS = [('Front Steps', 'Main Hall', (490, 200)), ('Main Hall', 'Ballroom', (490, 380)),
                 ('Main Hall', 'Dining Room', (365, 380)), ('Main Hall', 'Salon', (628, 380)),
                 ('Main Hall', 'Library', (680, 320)), ('Library', 'Conservatory', (735, 380)),
                 ('Ballroom', 'Salon', (575, 470)), ('Salon', 'Conservatory', (680, 470)),
                 ('Ballroom', 'Dining Room', (405, 470)), ('Dining Room', 'Breakfast Room', (330, 490)),
                 ('Butler’s Pantry', 'Dining Room', (330, 415)), ('Ballroom', 'Garden Terrace', (490, 590)),
                 ('Conservatory', 'South Terrace', (787, 470)), ('Breakfast Room', 'North Terrace', (207, 490))]
HOUSE_1_AMENITIES = [('entrance', 490, 175), ('stairs', 490, 280), ('stairs', 225, 300)]
HOUSE_1_LABELS = [('Restrooms: 14 steps down to the basement', 'area', 50, 400),
                  ('Front door: 7 steps up, then 7 more to this floor; no elevator, no ramps', 'area', 900, 400),
                  ('Reopens Nov 16, 2026 as “The Elms Experience”: the route may differ', 'area', 950, 400),
                  ('← West: the gardens · East: Bellevue Avenue →', 'area', 1000, 400)]

# Floor 2: page 20 is drawn at another size; F2 puts it over floor 1 (outer walls matched).
HOUSE_2 = [
    ('Upper Stair Hall', 'corridor', 'Upper stair hall and the bedroom corridor',
     [(395, 300), (590, 300), (590, 500), (825, 500), (825, 545), (170, 545), (170, 500), (395, 500)], None),
    ('Sitting Room', 'gallery', 'Upstairs Sitting Room, over the Ballroom, looking over the gardens',
     [(405, 545), (590, 545), (590, 745), (405, 745)], 'Sitting Room'),
    ('Mr. Berwind’s Bedroom', 'gallery', 'Mr. Berwind’s Bedroom: Edward Julius Berwind, coal magnate',
     rect(640, 550, 720, 690), 'Mr. Berwind'),
    ('Mrs. Berwind’s Bedroom', 'gallery', 'Mrs. Berwind’s Bedroom: Herminie Torrey Berwind', rect(720, 560, 825, 690),
     'Mrs. Berwind'),
    ('Van Alen Room', 'gallery', 'Van Alen Room: guest bedroom', rect(720, 375, 825, 500), 'Van Alen Room'),
    ('Satinwood Room', 'gallery', 'Satinwood Room: guest bedroom with satinwood furniture', rect(595, 375, 660, 500),
     'Satinwood'),
    ('Rose Room', 'gallery', 'Rose Room: guest bedroom', rect(330, 370, 395, 500), 'Rose'),
    ('Gold Bedroom', 'gallery', 'Gold Bedroom', rect(280, 560, 380, 690), 'Gold Bedroom'),
    ('Green Bedroom', 'gallery', 'Green Bedroom', rect(170, 545, 280, 690), 'Green Bedroom'),
]
HOUSE_2_CLOSED = [rect(170, 370, 330, 500), rect(660, 375, 720, 500), rect(380, 560, 405, 690),
                  rect(590, 550, 640, 690)]
HOUSE_2_DOORS = [('Upper Stair Hall', 'Sitting Room', (497, 545)), ('Upper Stair Hall', 'Mr. Berwind’s Bedroom', (680, 545)),
                 ('Upper Stair Hall', 'Mrs. Berwind’s Bedroom', (770, 545)), ('Upper Stair Hall', 'Van Alen Room', (770, 500)),
                 ('Upper Stair Hall', 'Satinwood Room', (625, 500)), ('Upper Stair Hall', 'Rose Room', (360, 500)),
                 ('Upper Stair Hall', 'Gold Bedroom', (330, 545)), ('Upper Stair Hall', 'Green Bedroom', (225, 545)),
                 ('Mr. Berwind’s Bedroom', 'Mrs. Berwind’s Bedroom', (720, 620))]
HOUSE_2_AMENITIES = [('stairs', 497, 400), ('stairs', 195, 470)]
HOUSE_2_LABELS = [('39 steps up from floor 1; 53 steps down to the basement at the end', 'area', 40, 520),
                  ('Bedroom names from ' + TB, 'area', 960, 520)]

# Floor 3 (page 25): staff bedrooms, seen only on the Servant Life Tour.
HOUSE_3 = [
    ('Roof', 'space', 'The roof, behind the balustrade; 8 more steps up to the lookout (Servant Life Tour)',
     [(70, 345), (305, 345), (305, 280), (535, 280), (535, 345), (780, 345), (780, 700), (70, 700)], None),
    ('Staff Bedrooms (east)', 'gallery', 'Staff bedrooms on the front (east) side: Servant Life Tour only',
     rect(150, 410, 705, 500), 'Staff Bedrooms'),
    ('Staff Corridor', 'corridor', 'Third-floor corridor', rect(110, 500, 705, 535), None),
    ('Staff Bedrooms (west)', 'gallery', 'Staff bedrooms on the garden (west) side: Servant Life Tour only',
     rect(110, 535, 705, 625), 'Staff Bedrooms'),
]
HOUSE_3_DOORS = [('Staff Corridor', 'Staff Bedrooms (east)', (400, 500)),
                 ('Staff Corridor', 'Staff Bedrooms (west)', (400, 535)), ('Staff Bedrooms (east)', 'Roof', (130, 410))]
HOUSE_3_AMENITIES = [('stairs', 128, 395)]
HOUSE_3_LABELS = [('Servant Life Tour only: guided, separate ticket, 107 steps up and 120 down', 'area', -40, 520),
                  ('Rooms simplified from ' + TB, 'area', 900, 520)]

F1_OUTLINE = [(200, 250), (405, 250), (405, 200), (575, 200), (575, 250), (790, 250), (790, 545), (585, 545),
              (585, 590), (395, 590), (395, 545), (200, 545)]
HOUSE_B = [
    ('Basement', 'space', 'Basement: the service floor (kitchen, laundry, servants’ hall) and the restrooms '
                          '(places approximate)', F1_OUTLINE, None),
]
HOUSE_B_DOORS = []
HOUSE_B_AMENITIES = [('stairs', 490, 280), ('restroom', 260, 330), ('restroom-all', 300, 330), ('entrance', 215, 300)]
HOUSE_B_LABELS = [('The tour ends here; exit to the parking, about 183 m (600 ft) (place approximate)', 'area', 100, 400),
                  ('Restrooms (one accessible): 14 steps down from the entryway', 'area', 300, 400),
                  ('Below: coal tunnel and boiler room (Servant Life Tour)', 'area', 600, 400),
                  (APPROX + ': no plan of the basement is published', 'area', 900, 400)]

S = 0.6                 # map units per pixel of the plans
C = 760                 # turns the plans: R(x, y) = (C - y, x) puts north (the plan's left) at the top


def build_floors(ways):
    g_rooms, g_closed, g_doors, g_amen, g_labels = grounds(ways)
    f1 = lambda x, y: [round((C - y) * S, 1), round(x * S, 1)]
    f2 = lambda x, y: f1(200 + (x - 160) * 590 / 670, 250 + (y - 350) * 295 / 345)
    f3 = lambda x, y: f1(200 + (x - 70) * 590 / 710, 250 + (y - 345) * 295 / 355)
    # put the house floors over the house on the grounds map, so switching floors keeps the house in view
    hp = ways['371945275'][:-1]
    hx = sum(p[0] for p in hp) / len(hp)
    hy = sum(p[1] for p in hp) / len(hp)
    cx, cy = f1(495, 395)
    gx, gy = G(hx, hy)
    shift = (round(gx - cx, 1), round(gy - cy, 1))
    spec = [
        ('G', 'Grounds & Carriage House', 'Parking · gardens · Sunken Garden · Carriage House Café', 0, G,
         [(a, b, c, d, None) for a, b, c, d in g_rooms], g_closed, g_doors, g_amen, g_labels),
        ('B', 'House · Basement', 'Restrooms · service rooms (places approximate)', 1, f1, HOUSE_B, [], HOUSE_B_DOORS,
         HOUSE_B_AMENITIES, HOUSE_B_LABELS),
        ('1', 'House · Floor 1', 'Main Hall · Ballroom · Salon · Conservatory · Library · Dining Room', 2, f1, HOUSE_1,
         HOUSE_1_CLOSED, HOUSE_1_DOORS, HOUSE_1_AMENITIES, HOUSE_1_LABELS),
        ('2', 'House · Floor 2', 'Mr. and Mrs. Berwind’s bedrooms · Sitting Room · guest rooms', 3, f2, HOUSE_2,
         HOUSE_2_CLOSED, HOUSE_2_DOORS, HOUSE_2_AMENITIES, HOUSE_2_LABELS),
        ('3', 'House · Floor 3', 'Staff bedrooms and the roof (Servant Life Tour only)', 4, f3, HOUSE_3, [],
         HOUSE_3_DOORS, HOUSE_3_AMENITIES, HOUSE_3_LABELS),
    ]
    floors = []
    for fid, label, area, order, pt, rooms_in, closed_in, doors_in, amen, labels in spec:
        rooms = []
        for rid, kind, name, poly, short in rooms_in:
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': [pt(*q) for q in poly]}
            if kind == 'gallery': r['label'] = short or rid
            rooms.append(r)
        ids = {r['id'] for r in rooms}
        doors = [{'a': a, 'b': b, 'at': pt(x, y), 'width': 14, 'axis': 'o'} for a, b, (x, y) in doors_in]
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order,
                       'transform': [1, 0, 0] if fid == 'G' else [1, *shift],
                       'rooms': rooms, 'closed': [{'poly': [pt(*q) for q in c]} for c in closed_in],
                       'amenities': [{'type': t, 'at': pt(x, y)} for t, x, y in amen],
                       'labels': [{'text': t, 'kind': k, 'at': pt(x, y)} for t, k, x, y in labels],
                       'doors': doors, **({'homeView': ['The Elms', 'Parking', 'Carriage House', 'Sunken Garden']}
                                          if fid == 'G' else {})})
    return {'about': 'Built by tools/build_elms.py. The grounds come from OpenStreetMap and the Society’s 1992 sketch '
                     'map; floors 1, 2 and 3 are traced from the 1994 measured plans in The Elms’ National Historic '
                     'Landmark nomination, turned so north is up. The basement has no published plan: only its '
                     'outline is drawn, and the places in it are approximate. The house reopens on November 16, 2026 '
                     'as “The Elms Experience”, whose route may differ.',
            'source': 'OpenStreetMap (grounds), The Elms National Historic Landmark nomination (plans of floors 1-3, '
                      'sketch map of the grounds), the Preservation Society of Newport County’s accessibility page '
                      '(visitor facilities)',
            'units': f'grounds: metres x {K}, north up; house: pixels of the plans x {S}, turned north up',
            'defaultFloor': '1', 'galleryWord': 'Room', 'floors': floors}


# ---- objects -------------------------------------------------------------------------------------------------------

REC = 'its record in the Preservation Society’s collection'
GUESS = ' (our guess: the Society doesn’t say which room it is in today)'
SKETCH = 'the Society’s 1992 sketch map of the grounds and its statuary list (National Historic Landmark nomination)'
PLACES = {
    'PSNC.10549': ('Main Hall', f'Installed in the ceiling above the main staircase ({REC}).', False),
    'PSNC.10554': ('Salon', f'Installed in the ceiling of the Drawing Room, today’s Salon ({REC}).', False),
    'PSNC.9900': ('Sitting Room', f'The Berwinds had it in the Sitting Room ({REC}).', False),
    'PSNC.9901': ('Sitting Room', f'The Berwinds had it in the Sitting Room ({REC}).', False),
    'PSNC.1852': ('Garden Terrace', f'On the upper terrace ({REC}); “Female Figure with Torch” on {SKETCH}.', False),
    'PSNC.1851': ('Garden Terrace', f'“Abundance” on the upper terrace on {SKETCH}.', False),
    'PSNC.1853': ('South Terrace', f'“Venus”, beside the south side of the house on {SKETCH}.', False),
    'PSNC.1874': ('Sunken Garden', f'The wellhead in the Sunken Garden on {SKETCH}.', False),
    'PSNC.11615': ('Dining Room', 'The Berwinds’ dining table, made by Allard, who made the room' + GUESS + '.', True),
    'PSNC.2619': ('Library', 'A carved walnut library table from the house' + GUESS + '.', True),
    'PSNC.2626': ('Mr. Berwind’s Bedroom', 'A portrait of Edward J. Berwind' + GUESS + '.', True),
    'PSNC.2157': ('Mrs. Berwind’s Bedroom', 'A Louis XVI-style dressing table from the house' + GUESS + '.', True),
    'PSNC.8519': ('Conservatory', 'A painted wicker chair from the house, the kind used in a conservatory' + GUESS + '.',
                  True),
}
NOT_ELMS = re.compile(r'Road Coach|Sleigh|Brougham|Omnibus', re.I)
sys.path.insert(0, str(ROOT / 'tools'))
from harvest_elms import of_elms          # noqa: E402  (which records belong to The Elms)
SKIP = set()

def clean(s):
    s = html.unescape(re.sub(r'<br\s*/?>', '\n', s or ''))
    return re.sub(r'[ \t]+', ' ', re.sub(r'<[^>]+>', '', s)).strip()


def artists(s):
    names = []
    for part in (s or '').split('||'):
        name, _, role = part.partition('__')
        name = name.strip()
        if not name or name.lower().startswith('undetermined'): continue
        if ',' in name and not re.search(r'&|Inc|Co\.|Fils|Studios', name):
            last, first = [x.strip() for x in name.split(',', 1)]
            name = f'{first} {last}'
        role = role.strip().strip('[]')
        if names and role in ('Manufacturer', 'Retailer'): continue      # the designer is named already
        names.append(name + (f' ({role.lower()})' if role and role not in ('Artist', 'Maker', 'Creator') else ''))
    return ', '.join(names) or 'Unknown maker'


def year_of(date):
    m = re.search(r'(\d{4})', date or '')
    if m: return int(m[1])
    m = re.search(r'(\d+)(?:st|nd|rd|th)[- ]+c', (date or '').lower())
    return (int(m[1]) - 1) * 100 + 50 if m else None


def picture(key, path):
    """Download once (politely) and save a phone-sized JPEG; returns the app path."""
    if not path: return None
    raw = CACHE / 'img' / f'{key}.bin'
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        url = COLL + 'FullImages' + path
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
        time.sleep(2)
        if not out: return None
        raw.write_bytes(out)
    dest = OUT / 'images' / f'{key}.jpg'
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            im = Image.open(io.BytesIO(raw.read_bytes()))
        except Exception:
            raw.unlink()
            return None
        im = im.convert('RGB')
        im.thumbnail((1000, 1000))
        im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/elms/images/{key}.jpg'



def build_works(floors):
    names = {r['id']: (r['name'], f['id']) for f in floors['floors'] for r in f['rooms']}
    objs = json.loads((CACHE / 'objects.json').read_text())
    objs.pop('_words', None)
    works, extra = [], []
    for r in objs.values():
        if 'images' not in r or not of_elms(r): continue    # not one of The Elms' objects
        if r['CAT_NBR'] in SKIP or NOT_ELMS.search(r['FORM'] + ' ' + r.get('CATEG_20', '')): continue
        key = 'elms-' + re.sub(r'[^a-z0-9]+', '-', r['CAT_NBR'].lower()).strip('-')
        img = picture(key, (r['images'] or [None])[0])
        text = clean(r.get('OBJ_MEM'))
        a = {'id': key, 'title': clean(r['FORM']), 'artist': artists(r.get('ARTIST')), 'date': r.get('CATEG_16') or None,
             'year': year_of(r.get('CATEG_16')), 'medium': (r.get('MATERIAL') or '').replace(' --', ',').title() or None,
             'type': (r.get('CAT_NAM') or '').title() or None,
             'dimensions': re.sub(r'\s*__\s*', ' · ', re.sub(r'\[(\w)\]', r'\1 ', r.get('WEIGHT') or '')).strip() or None,
             'description': text[:1500] or None, 'credit': r.get('CREDIT_LINE') or None,
             'accession': r['CAT_NBR'],
             'url': f'{COLL}mDetail.aspx?rID={r["record_id"]}&db=objects&dir=NEWPHIST',
             'image': img, 'imageCredit': 'The Preservation Society of Newport County' if img else None}
        place = PLACES.get(r['CAT_NBR'])
        if not place:
            extra.append({x: y for x, y in a.items() if y not in (None, '')})
            continue
        room, how, guessed = place
        name, floor = names[room]
        a.update({'gallery': room, 'galleryName': name, 'floor': floor, 'placeNote': how})
        if guessed: a['placeGuessed'] = True
        works.append({x: y for x, y in a.items() if y not in (None, '')})
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    works.sort(key=lambda a: (forder[a['floor']], order[a['gallery']], a.get('year') or 0))
    extra.sort(key=lambda a: a.get('year') or 0)
    return ({'source': 'The Preservation Society of Newport County, Digital Collections; rooms from each record',
             'checked': time.strftime('%Y-%m-%d'), 'count': len(works), 'complete': False, 'artworks': works}, extra)



def build_guide(works, extra):
    rows = []
    for a in works['artworks'] + extra:
        rows.append({k: v for k, v in {
            'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'), 'year': a.get('year'),
            'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'), 'onView': 'gallery' in a,
            'gallery': a.get('gallery'), 'floor': a.get('floor')}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': 'The Elms', 'checked': works['checked'],
            'source': 'The Preservation Society of Newport County, Digital Collections', 'onViewKnown': False,
            'note': 'The Elms’ own furniture, paintings and treasures from the Preservation Society’s Digital '
                    'Collections: objects that name the house or came from the Berwind family, who lived there from '
                    '1901 until 1961. The house holds far more than is published online. Objects without a room are '
                    'in the collection, but the Society doesn’t say where they are shown.',
            'works': rows}


def main():
    if not (CACHE / 'objects.json').exists():
        raise SystemExit('run tools/harvest_elms.py first')
    OUT.mkdir(parents=True, exist_ok=True)
    floors = build_floors(osm())
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works, extra = build_works(floors)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works, extra)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': sum(w['onView'] for w in guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{works["count"]} objects on the map ({sum(bool(a.get("placeGuessed")) for a in works["artworks"])} with a '
          f'guessed room), {len(extra)} more without a room, '
          f'{sum("image" in a for a in works["artworks"] + extra)} pictures')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
