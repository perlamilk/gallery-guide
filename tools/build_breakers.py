#!/usr/bin/env python3
"""Build The Breakers (Newport, RI) map guide (run: python3 tools/harvest_breakers.py, then this).

    data/breakers/floors.json       the grounds, the basement and the two floors on the tour, seen from above (flat 2D)
    data/breakers/artworks.json     the house's objects, each in its room
    data/breakers/images/           their pictures, made smaller for phones
    data/guides/Q1786400.json       the same objects, for the museum page

Where the information comes from
--------------------------------
The map
  - Grounds (floor G): OpenStreetMap (www.openstreetmap.org/api/0.6/map, cached in .cache/breakers/osm.xml): the
    house (way 227360878), the Welcome Center (1192968513, with the "Welcome Center Cafe" node), the Caretaker's
    Cottage by the main gate (1192968515), the Children's Cottage (1192968514), the 13-acre grounds (1472011673), the
    visitor parking across Ochre Point Avenue (227360913), the avenue (19360132), the walk from the Welcome Center to
    the house (1285803607) and the Cliff Walk (629887169). Metres east/north of 41.4697 N, 71.2986 W. Which building
    is which comes from the 1971 National Register nomination's sketch map and the Society's accessibility page.
  - House floors 1 and 2: traced from the first- and second-floor plans in the National Register of Historic Places
    nomination for The Breakers (Commonwealth Engineers & Consultants for the Preservation Society; scanned at
    preservation.ri.gov). Drawn as on the plans: the ocean (east) side at the top, the porte-cochère at the bottom.
    Units: half a pixel of the plans scanned at 300 dpi.
  - Basement (floor B): no plan is published. The Society says the Museum Store and restrooms are down there, reached
    by stairs at the end of the tour or from the service drive outside. Only the house outline is drawn; where the
    store and restrooms sit inside it is our guess, and the map says so.
  - Visitor facts (Welcome Center with tickets, café and restrooms; the elevator between floors 1 and 2; 40 stairs
    up; the basement store): newportmansions.org, "The Breakers: Partially accessible" (checked Nov 2026).

The objects: the Preservation Society's own Digital Collections site (tools/harvest_breakers.py). Kept: objects that
name The Breakers, or came down from Cornelius Vanderbilt II and his daughter Countess Széchényi, who kept the house
until 1965. Rooms come from each record's own text (the Billiard Room suite, the Dining Room table, the Great Hall
fireback, the tapestry on the stair landing, the garden fountains) or, for the Library chimneypiece, from
descriptions of the Library that quote its motto. Portraits are placed in the bedroom of the person they show; that is our guess
and the work says so. Objects whose room no source gives are listed on the museum page but not put on the map.
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
OUT = ROOT / 'data' / 'breakers'
CACHE = ROOT / '.cache' / 'breakers'
MUSEUM = 'Q1786400'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
COLL = 'https://newportmansions.rediscoverysoftware.com/'
APPROX = 'Approximate'

# ---- grounds (floor G) ----------------------------------------------------------------------------------------------

LAT0, LON0 = 41.4697, -71.2986
K = 2.4                     # map units per metre on the grounds


def G(x, y):
    """Metres east/north of the reference point -> map units (north up)."""
    return [round((x + 170) * K, 1), round((140 - y) * K, 1)]


def osm():
    f = CACHE / 'osm.xml'
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = 'https://www.openstreetmap.org/api/0.6/map?bbox=-71.3030,41.4670,-71.2955,41.4725'
        out = subprocess.run(['curl', '-s', '-f', '-m', '90', '-A', UA, url], capture_output=True).stdout
        if not out: raise SystemExit('OpenStreetMap did not answer')
        f.write_bytes(out)
    root = ET.parse(f).getroot()
    nodes = {n.get('id'): (float(n.get('lat')), float(n.get('lon'))) for n in root.iter('node')}
    ways = {}
    for w in root.iter('way'):
        pts = []
        for nd in w.findall('nd'):
            lat, lon = nodes[nd.get('ref')]
            pts.append(((lon - LON0) * 111320 * math.cos(math.radians(LAT0)), (lat - LAT0) * 110540))
        ways[w.get('id')] = pts
    return ways


def band(pts, half=3.0):
    """A path drawn as a band `half` metres either side of its line."""
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        nx, ny = -dy / n * half, dx / n * half
        left.append((x + nx, y + ny)); right.append((x - nx, y - ny))
    return left + right[::-1]


def inside(pts, y0=-135, y1=140):
    return [p for p in pts if y0 <= p[1] <= y1]


def grounds(ways):
    rooms = [
        ('Grounds', 'space', 'The Breakers grounds: 13 acres of lawn and gardens above the ocean', ways['1472011673'][:-1]),
        ('The Breakers', 'space', 'The Breakers (1895): the house tour. Pick floor 1, 2 or B above to see the rooms',
         ways['227360878'][:-1]),
        ('Welcome Center', 'space', 'Welcome Center: tickets, The Breakers Café, restrooms', ways['1192968513'][:-1]),
        ('Caretaker’s Cottage', 'space', 'Caretaker’s Cottage by the main gate: the Beneath The Breakers tour starts '
                                         'outside it', ways['1192968515'][:-1]),
        ('Children’s Cottage', 'space', 'Children’s Cottage: the Vanderbilt children’s playhouse (open in season; '
                                        '6 steps)', ways['1192968514'][:-1]),
        ('Parking', 'space', 'Visitor parking (free), across Ochre Point Avenue', ways['227360913'][:-1]),
        ('Ochre Point Avenue', 'corridor', 'Ochre Point Avenue: the main gates', band(inside(ways['19360132']), 5)),
        ('Cliff Walk', 'corridor', 'Cliff Walk: the public path along the ocean, below the back lawn',
         band(inside(ways['629887169'], -118, 140), 2.5)),
    ]
    closed = [ways['1472011653'][:-1], ways['1472011655'][:-1]]      # service wings joined to the house
    doors = [('Parking', 'Ochre Point Avenue', (-92, -15)), ('Ochre Point Avenue', 'Grounds', (-78, 20)),
             ('Grounds', 'Welcome Center', (-52, 44)), ('Grounds', 'Caretaker’s Cottage', (-64, 30)),
             ('Grounds', 'The Breakers', (6, 10)), ('Grounds', 'Children’s Cottage', (22, 86)),
             ('Grounds', 'Cliff Walk', (150, -40))]
    amen = [('info', -64, 50), ('dining', -58, 58), ('restroom', -54, 48), ('entrance', -80, 20),
            ('entrance', 4, 11)]
    labels = [('P · Parking (free)', 'area', -122, -30), ('Main gates', 'area', -100, 34),
              ('Welcome Center', 'area', -50, 72), ('The Breakers', 'area', 40, -30),
              ('Back lawn and the ocean view', 'area', 110, 20), ('Atlantic Ocean', 'area', 175, -110),
              ('Breakers Observation Area on the Cliff Walk', 'area', 150, -62),
              ('Welcome Center to the house: about 100 m (335 ft)', 'area', -30, -60)]
    return rooms, closed, doors, amen, labels


# ---- the house (floors 1, 2 and B) -----------------------------------------------------------------------------------
# Units: pixels of the National Register plans scanned at 300 dpi (crops of the plan sheets); the top is the ocean side.

def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def apse(x, y0, y1, depth, n=7):
    """Points of a half-round bay on the right of a wall at x, from y0 to y1."""
    cy, r = (y0 + y1) / 2, (y1 - y0) / 2
    return [(x + depth * math.sin(math.pi * i / n), cy - r * math.cos(math.pi * i / n)) for i in range(n + 1)]


HOUSE_1 = [
    ('Great Hall', 'gallery', 'Great Hall: 50 feet high, the grand staircase and the stair-landing tapestry',
     rect(490, 265, 940, 580), 'Great Hall'),
    ('Lower Loggia', 'gallery', 'Lower Loggia: the open arcade toward the ocean, with its mosaic vaults',
     rect(665, 65, 940, 265), 'Lower Loggia'),
    ('Billiard Room', 'gallery', 'Billiard Room: gray-green marble, alabaster and mosaics; its 1895 furniture',
     rect(460, 50, 665, 265), 'Billiard Room'),
    ('Morning Room', 'gallery', 'Morning Room: panels made in Paris by Allard, with platinum leaf',
     rect(940, 50, 1150, 265), 'Morning Room'),
    ('Arcade', 'corridor', 'Arcade between the Great Hall and the Music Room', rect(940, 265, 1045, 590), None),
    ('Music Room', 'gallery', 'Music Room: built by Allard in France, taken apart and put back together here',
     [(1045, 265), (1235, 265)] + apse(1235, 345, 515, 95) + [(1235, 590), (1045, 590)], 'Music Room'),
    ('Dining Room', 'gallery', 'Dining Room: two storeys high, alabaster columns, two Baccarat crystal chandeliers',
     rect(275, 260, 490, 570), 'Dining Room'),
    ('Service Hall', 'corridor', 'Hall from the Foyer to the Breakfast Room, the Dining Room and the Pantry',
     rect(445, 580, 740, 630), None),
    ('Breakfast Room', 'gallery', 'Breakfast Room: the family’s everyday dining room', rect(445, 630, 645, 780),
     'Breakfast Room'),
    ('Butler’s Pantry', 'gallery', 'Butler’s Pantry: two storeys of china, crystal and silver', rect(205, 575, 445, 770),
     'Pantry'),
    ('Kitchen', 'gallery', 'Kitchen: in its own wing, behind fire doors', rect(40, 560, 205, 905), 'Kitchen'),
    ('Foyer', 'corridor', 'Entrance Foyer', rect(740, 590, 845, 820), None),
    ('Ladies’ Reception Room', 'gallery', 'Ladies’ Reception Room', rect(650, 700, 740, 810), 'Ladies’ Reception'),
    ('Gentlemen’s Reception Room', 'gallery', 'Gentlemen’s Reception Room', rect(845, 710, 935, 810),
     'Gentlemen’s Reception'),
    ('Library', 'gallery', 'Library: walnut, gilded leather and a 16th-century French chimneypiece',
     rect(940, 590, 1130, 790), 'Library'),
    ('Library Alcove', 'gallery', 'Library Alcove', rect(1130, 590, 1225, 790), 'Library Alcove'),
    ('Porte-Cochère', 'space', 'Porte-cochère: the front door, facing Ochre Point Avenue', rect(705, 820, 870, 990),
     None),
]
HOUSE_1_CLOSED = [rect(845, 590, 935, 710)]                                  # the family stair
HOUSE_1_DOORS = [('Porte-Cochère', 'Foyer', (790, 820)), ('Foyer', 'Great Hall', (790, 590)),
                 ('Foyer', 'Ladies’ Reception Room', (740, 760)), ('Foyer', 'Gentlemen’s Reception Room', (845, 760)),
                 ('Foyer', 'Service Hall', (740, 610)), ('Service Hall', 'Breakfast Room', (550, 630)),
                 ('Service Hall', 'Dining Room', (465, 578)), ('Service Hall', 'Butler’s Pantry', (445, 600)),
                 ('Butler’s Pantry', 'Kitchen', (205, 660)), ('Butler’s Pantry', 'Dining Room', (380, 572)),
                 ('Great Hall', 'Lower Loggia', (790, 265)), ('Lower Loggia', 'Billiard Room', (665, 160)),
                 ('Lower Loggia', 'Morning Room', (940, 160)), ('Great Hall', 'Arcade', (940, 430)),
                 ('Arcade', 'Music Room', (1045, 430)), ('Arcade', 'Morning Room', (990, 265)),
                 ('Arcade', 'Library', (990, 590)), ('Library', 'Library Alcove', (1130, 690)),
                 ('Great Hall', 'Dining Room', (490, 520))]
HOUSE_1_AMENITIES = [('entrance', 790, 960), ('stairs', 575, 420), ('stairs', 890, 650)]
HOUSE_1_LABELS = [('Back terrace (ocean side)', 'area', 800, 20), ('Terrace', 'area', 1390, 430),
                  ('Restrooms and the Museum Store: in the basement, at the end of the tour', 'area', 280, 960),
                  ('Elevator to floor 2: ask a staff member', 'area', 1150, 960)]

# Floor 2: the plan sheet is drawn 5 px left of and 10 px above floor 1's; F2 puts it back over floor 1.
HOUSE_2 = [
    ('Gallery', 'corridor', 'Upper gallery around the Great Hall',
     [(605, 250), (990, 250), (990, 380), (1110, 380), (1110, 440), (990, 440), (990, 580), (650, 580), (650, 760),
      (605, 760)], None),
    ('Great Hall (below)', 'space', 'Open to the Great Hall below', rect(680, 265, 910, 525), None),
    ('Guest Bedroom', 'gallery', 'Guest Bedroom', rect(455, 60, 645, 255), 'Guest Bedroom'),
    ('Upper Loggia', 'gallery', 'Upper Loggia: painted canopies of sky, open to the sea air', rect(645, 60, 930, 250),
     'Upper Loggia'),
    ('Miss Gertrude’s Bedroom', 'gallery', 'Gertrude Vanderbilt’s Bedroom: the eldest daughter, later the sculptor '
                                           'Gertrude Vanderbilt Whitney', rect(940, 60, 1135, 250), 'Gertrude’s Room'),
    ('Mrs. Vanderbilt’s Bedroom', 'gallery', 'Mrs. Vanderbilt’s Bedroom: Alice Vanderbilt’s oval room, designed by '
                                             'Ogden Codman',
     [(1110, 330), (1240, 330)] + apse(1240, 330, 485, 80) + [(1110, 485)], 'Mrs. Vanderbilt'),
    ('Master Bath', 'gallery', 'Master Bath: hot and cold, fresh and salt water', rect(1120, 485, 1225, 550),
     'Master Bath'),
    ('Bedroom 6', 'gallery', 'Bedroom', rect(460, 640, 605, 750), 'Bedroom'),
    ('Bedroom 7', 'gallery', 'Bedroom', rect(650, 620, 745, 785), 'Bedroom'),
    ('Countess Széchényi’s Bedroom', 'gallery', 'Countess Széchényi’s Bedroom: Gladys, the youngest daughter, who '
                                                'opened the house to visitors in 1948', rect(745, 580, 850, 790),
     'Countess Széchényi'),
    ('Bath', 'gallery', 'Bath', rect(850, 705, 945, 790), 'Bath'),
    ('Mr. Vanderbilt’s Bedroom', 'gallery', 'Mr. Vanderbilt’s Bedroom: Cornelius Vanderbilt II', rect(945, 580, 1135, 770),
     'Mr. Vanderbilt'),
]
HOUSE_2_CLOSED = [rect(270, 255, 500, 545),       # the Dining Room's ceiling (it is two storeys high)
                  rect(990, 250, 1110, 380), rect(990, 440, 1110, 550),   # Mrs. Vanderbilt's dressing rooms
                  rect(850, 580, 945, 705), rect(460, 550, 605, 640)]    # stairs and service rooms
HOUSE_2_DOORS = [('Gallery', 'Guest Bedroom', (625, 252)), ('Gallery', 'Upper Loggia', (790, 250)),
                 ('Gallery', 'Miss Gertrude’s Bedroom', (965, 250)), ('Gallery', 'Mrs. Vanderbilt’s Bedroom', (1110, 410)),
                 ('Mrs. Vanderbilt’s Bedroom', 'Master Bath', (1170, 485)), ('Gallery', 'Countess Széchényi’s Bedroom',
                                                                             (800, 580)),
                 ('Gallery', 'Bedroom 7', (650, 700)), ('Gallery', 'Bedroom 6', (605, 700)),
                 ('Gallery', 'Mr. Vanderbilt’s Bedroom', (980, 580)), ('Mr. Vanderbilt’s Bedroom', 'Bath', (945, 750)),
                 ('Gallery', 'Great Hall (below)', (795, 525))]
HOUSE_2_AMENITIES = [('stairs', 570, 410), ('stairs', 885, 640)]
HOUSE_2_LABELS = [('Over the Dining Room (two storeys high)', 'area', 385, 400),
                  ('Third floor: only on the guided Preservation in Progress tour', 'area', 760, 900)]

OUTLINE = [(270, 255), (455, 255), (455, 45), (1160, 45), (1160, 265), (1240, 265), (1240, 800), (940, 800),
           (940, 820), (650, 820), (650, 800), (345, 800), (345, 775), (205, 775), (205, 905), (40, 905), (40, 560),
           (270, 560)]
HOUSE_B = [
    ('Basement', 'space', 'Basement: service rooms; the Museum Store and restrooms (places approximate)', OUTLINE, None),
    ('Museum Store', 'space', 'The Museum Store (place approximate)', rect(300, 300, 640, 540), None),
]
HOUSE_B_CLOSED = []
HOUSE_B_DOORS = [('Basement', 'Museum Store', (470, 540))]
HOUSE_B_AMENITIES = [('stairs', 890, 650), ('shop', 470, 420), ('restroom', 760, 420), ('entrance', 120, 880)]
HOUSE_B_LABELS = [(APPROX + ': no plan of the basement is published', 'area', 760, 960),
                  ('Exit to the service drive', 'area', 120, 960)]

S = 0.45                # map units per pixel of the plans
# The house floors are moved so their middle sits on the house on the grounds map: switching between the grounds and
# a house floor keeps the house in view.
HOUSE_SHIFT = (157, 88)


def build_floors(ways):
    g_rooms, g_closed, g_doors, g_amen, g_labels = grounds(ways)
    f1 = lambda x, y: [round(x * S, 1), round(y * S, 1)]
    f2 = lambda x, y: [round((x + 5) * S, 1), round((y + 10) * S, 1)]
    spec = [
        ('G', 'Grounds & Welcome Center', 'Welcome Center (tickets, café, restrooms) · parking · grounds · Cliff Walk',
         0, G, [(a, b, c, d, None) for a, b, c, d in g_rooms], g_closed, g_doors, g_amen, g_labels),
        ('B', 'House · Basement', 'Museum Store · restrooms (places approximate)', 1, f1, HOUSE_B, HOUSE_B_CLOSED,
         HOUSE_B_DOORS, HOUSE_B_AMENITIES, HOUSE_B_LABELS),
        ('1', 'House · Floor 1', 'Great Hall · Music Room · Morning Room · Library · Dining Room · Billiard Room', 2, f1,
         HOUSE_1, HOUSE_1_CLOSED, HOUSE_1_DOORS, HOUSE_1_AMENITIES, HOUSE_1_LABELS),
        ('2', 'House · Floor 2', 'Family bedrooms · Upper Loggia', 3, f2, HOUSE_2, HOUSE_2_CLOSED, HOUSE_2_DOORS,
         HOUSE_2_AMENITIES, HOUSE_2_LABELS),
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
        shift = [0, 0] if fid == 'G' else list(HOUSE_SHIFT)
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order, 'transform': [1, *shift],
                       'rooms': rooms, 'closed': [{'poly': [pt(*q) for q in c]} for c in closed_in],
                       'amenities': [{'type': t, 'at': pt(x, y)} for t, x, y in amen],
                       'labels': [{'text': t, 'kind': k, 'at': pt(x, y)} for t, k, x, y in labels],
                       'doors': doors, **({'homeView': ['The Breakers', 'Welcome Center', 'Parking']}
                                          if fid == 'G' else {})})
    return {'about': 'Built by tools/build_breakers.py. The grounds come from OpenStreetMap; floors 1 and 2 are traced '
                     'from the plans in the National Register of Historic Places nomination for The Breakers. The '
                     'basement has no published plan: only its outline is drawn, and the places in it are approximate.',
            'source': 'OpenStreetMap (grounds), National Register of Historic Places nomination floor plans (house), '
                      'the Preservation Society of Newport County’s accessibility page (visitor facilities)',
            'units': f'grounds: metres x {K}, north up; house: pixels of the plans x {S} (the ocean side at the top)',
            'defaultFloor': '1', 'galleryWord': 'Room', 'floors': floors}


# ---- objects -------------------------------------------------------------------------------------------------------

REC = 'its record in the Preservation Society’s collection'
# catalog number -> (room, how we know, guessed); objects not listed here are not put on the map
PLACES = {
    'PSNC.2459': ('Billiard Room', f'Made for the Billiard Room ({REC}).', False),
    'PSNC.2465': ('Billiard Room', f'Made for the Billiard Room ({REC}).', False),
    'PSNC.2467': ('Billiard Room', f'Made for the Billiard Room ({REC}).', False),
    'PSNC.2470': ('Billiard Room', f'Made for the Billiard Room ({REC}).', False),
    'PSNC.2471': ('Billiard Room', f'Made for the Billiard Room ({REC}).', False),
    'PSNC.2511': ('Dining Room', f'Made for the Dining Room; with its seven leaves it seats 34 ({REC}).', False),
    'PSNC.14509': ('Great Hall', f'In the Great Hall fireplace ({REC}).', False),
    'PSNC.10462': ('Great Hall', f'Hung by Allard on the landing of the grand staircase ({REC}).', False),
    'PSNC.11741': ('Great Hall', f'Stood in the Great Hall from 1926 to 1973 and came back in 2007 ({REC}); that it '
                                 'is in the Great Hall today is our guess.', True),
    'PSNC.12017': ('Library', 'The Library’s chimneypiece: descriptions of the Library quote its Old French motto, '
                              '“Little do I care for riches” (Wikipedia, The Breakers).', False),
    'PSNC.2379': ('Music Room', f'The family’s Steinway, delivered June 1895 ({REC}); that it stands in the Music Room '
                                'is our guess.', True),
    'PSNC.8112': ('Mrs. Vanderbilt’s Bedroom', 'A portrait of Alice Vanderbilt; that it hangs in her bedroom is our '
                                               'guess.', True),
    'PSNC.8111': ('Mr. Vanderbilt’s Bedroom', 'A portrait of Cornelius Vanderbilt II; that it hangs in his bedroom is our '
                                              'guess.', True),
    'PSNC.12018': ('Mr. Vanderbilt’s Bedroom', 'Sargent’s study of Cornelius Vanderbilt II; that it hangs in his bedroom '
                                               'is our guess.', True),
    'PSNC.14537': ('Miss Gertrude’s Bedroom', 'A portrait of Gertrude Vanderbilt as a girl; that it hangs in her bedroom '
                                              'is our guess.', True),
    'PSNC.12610': ('Countess Széchényi’s Bedroom', 'A portrait of Gladys, Countess Széchényi; that it hangs in her '
                                                   'bedroom is our guess.', True),
    'PSNC.10968': ('Grounds', f'On the serpentine walk, in line with the middle of the house ({REC}).', False),
    'PSNC.7905': ('Grounds', f'From The Breakers estate ({REC}); where on the grounds is not given.', True),
}
GARDEN = re.compile(r'Fountain|Bird Bath|Garden Basin|Cistern|Sundial|Statue of Athena')
NOT_SHOWN = re.compile(r'Napkin|Sleigh|Carriage|Brougham|Omnibus|Coupe|Sporting Break|Wagonette|Road Coach|Replica|Rendering')


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
    return f'data/breakers/images/{key}.jpg'


def build_works(floors):
    names = {r['id']: (r['name'], f['id']) for f in floors['floors'] for r in f['rooms']}
    objs = json.loads((CACHE / 'objects.json').read_text())
    objs.pop('_words', None)
    works, extra = [], []
    for r in objs.values():
        if 'images' not in r: continue                      # not one of The Breakers' objects
        if NOT_SHOWN.search(r['FORM'] + ' ' + r.get('OBJ_MEM', '')[:400]): continue
        key = 'breakers-' + re.sub(r'[^a-z0-9]+', '-', r['CAT_NBR'].lower()).strip('-')
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
        if not place and GARDEN.search(r['FORM']):
            place = ('Grounds', f'A garden piece from The Breakers ({REC}); where on the grounds is not given.', True)
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
    return {'museum': MUSEUM, 'name': 'The Breakers', 'checked': works['checked'],
            'source': 'The Preservation Society of Newport County, Digital Collections', 'onViewKnown': False,
            'note': 'The Breakers’ own furniture, portraits, sculpture and garden pieces from the Preservation '
                    'Society’s Digital Collections: objects that name the house or came down from the Vanderbilts and '
                    'Countess Széchényi. The house holds far more than is published online. Objects without a room are '
                    'in the collection, but the Society doesn’t say where they are shown.',
            'works': rows}


def main():
    if not (CACHE / 'objects.json').exists():
        raise SystemExit('run tools/harvest_breakers.py first')
    OUT.mkdir(exist_ok=True)
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
