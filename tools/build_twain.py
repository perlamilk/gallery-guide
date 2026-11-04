#!/usr/bin/env python3
"""Build the Mark Twain House & Museum (Hartford, CT) map guide: python3 tools/build_twain.py

    data/twain/floors.json         the grounds, the Museum Center and every floor of the house, seen from above (flat 2D)
    data/twain/artworks.json       the rooms, their famous features and the Museum Center's exhibits, each in its place
    data/twain/images/             their pictures, made smaller for phones
    data/guides/Q4165331.json      the same, for the museum page

Where the information comes from
--------------------------------
The map
  - Grounds (floor G): OpenStreetMap (cached in .cache/twain/osm.xml): the house (way 194716932), the Museum Center
    (194716940), the Carriage House (194716930), the parking lots (907546979, 907546981, 194716931 off Farmington
    Avenue; 907546976 off Forest Street), the footpaths, Farmington Avenue and Forest Street, the Stowe House next
    door. Metres east/north of the house. The museum's Directions & Parking and Guide to Visiting pages give the
    lots, the ramp, the walk between the buildings and the bus stop. The gardens are placed from the museum's garden
    pages (turn-around bed by the Carriage House, the Fran Gordon Garden by the patio, the Sundial Garden on the
    Museum Center's roof): their outlines are approximate.
  - The house (floors B, 1, 2, 3): traced from the Historic American Buildings Survey drawings of the house
    (HABS CT-359, 1995, sheets 2-5; public domain, Library of Congress loc.gov/item/ct0332). Units: pixels of the
    first-floor sheet at 3200 px wide; the other sheets are lined up with it by their outer walls. On the sheets
    north is to the right (the service wing faces Farmington Avenue, the front door and porte-cochère face east);
    R() turns them so north is up, like the grounds. Room names are the drawings' own.
  - Museum Center (floors C1, C2): no plan is published. The outline is OpenStreetMap's; the rooms inside are
    placed from the museum's exhibit page ("First Floor: Aetna Gallery, Entrance Hall, Small Theatre, Hal Holbrook
    Hall; Second Floor: Nook Café, Hallway") and are approximate.

The works
  The house is the museum's great work, so its rooms and their best-known features are listed, each with a HABS photo
  (Jack E. Boucher, 1995, public domain); plus the Museum Center's permanent exhibits from marktwainhouse.org
  (exhibitions/permanent-exhibits), with the museum's own pictures.
"""
import io
import json
import math
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'twain'
CACHE = ROOT / '.cache' / 'twain'
MUSEUM = 'Q4165331'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SITE = 'https://marktwainhouse.org'
HABS = 'https://tile.loc.gov/storage-services/service/pnp/habshaer/ct/ct0300/ct0332/photos/'
HABS_ITEM = 'https://www.loc.gov/pictures/item/ct0332.photos.'
APPROX = 'Approximate'

# ---- grounds (floor G) ----------------------------------------------------------------------------------------------

LAT0, LON0 = 41.76706, -72.70144
K = 5.0                     # map units per metre on the grounds


def G(x, y):
    """Metres east/north of the house -> map units (north up)."""
    return [round((x + 125) * K, 1), round((50 - y) * K, 1)]


def osm():
    f = CACHE / 'osm.xml'
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = 'https://www.openstreetmap.org/api/0.6/map?bbox=-72.7050,41.7652,-72.6985,41.7685'
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
            pts.append((round((lon - LON0) * 111320 * math.cos(math.radians(LAT0)), 2), round((lat - LAT0) * 110540, 2)))
        ways[w.get('id')] = pts
        name = next((t.get('v') for t in w.findall('tag') if t.get('k') == 'name'), None)
        if name: ways.setdefault('_named', {}).setdefault(name, []).append(w.get('id'))
    return ways


def band(pts, half=3.0):
    """A street or path drawn as a band `half` metres either side of its line."""
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        nx, ny = -dy / n * half, dx / n * half
        left.append((x + nx, y + ny)); right.append((x - nx, y - ny))
    return left + right[::-1]


def clip(pts, x0=-122, x1=110, y0=-100, y1=48):
    return [p for p in pts if x0 <= p[0] <= x1 and y0 <= p[1] <= y1]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def circle(cx, cy, r, n=16):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def grounds(ways):
    farm = []                                         # Farmington Avenue: its pieces joined west to east
    for wid in ways['_named']['Farmington Avenue']:
        farm += ways[wid]
    farm = sorted(clip(farm, y0=0, y1=60), key=lambda p: p[0])
    rooms = [
        ('Grounds', 'space', 'The Mark Twain House & Museum grounds, between Farmington Avenue and the Museum Center '
                             '(boundary approximate)', rect(-120, -96, 98, 40)),
        ('House', 'space', 'The Mark Twain House (1874): guided tours only. Pick floor B, 1, 2 or 3 above to see its rooms',
         ways['194716932'][:-1]),
        ('Museum Center', 'space', 'The Webster Bank Museum Center: tickets, every tour starts here; galleries, film, '
                                   'store, café and restrooms. Pick floor C1 or C2 above', ways['194716940'][:-1]),
        ('Carriage House', 'gallery', 'The Clemenses’ Carriage House (1874), where the coachman Patrick McAleer lived '
                                      'with his family: not open to the public (offices and a rental hall)',
         ways['194716930'][:-1]),
        ('Turn-Around Garden', 'gallery', 'The Turn-Around Garden, where carriages circled a round flower bed by the '
                                          'Carriage House (place approximate)', circle(5, -24, 4.5)),
        ('Fran Gordon Garden', 'gallery', 'The Fran Gordon Garden on the patio by the Carriage House, where tours pause '
                                          '(place approximate)', rect(28, -60, 44, -54)),
        ('Sundial Garden', 'gallery', 'The Sundial Garden, a pollination garden on the roof of the Museum Center '
                                      '(place approximate)', rect(30, -66.5, 42, -62)),
        ('Parking', 'space', 'Main parking lot (free): GPS 385 Farmington Avenue. The entrance is a few hundred feet '
                             'west of the house', ways['907546979'][:-1]),
        ('Lower Parking', 'space', 'Parking (free), part of the main lot', ways['907546981'][:-1]),
        ('South Parking', 'space', 'Parking (free) by the path to the Museum Center', ways['194716931'][:-1]),
        ('Forest Street Parking', 'space', 'Smaller rear lot at 65 Forest Street, for visitors with limited mobility: '
                                           'closest to the Museum Center', ways['907546976'][:-1]),
        ('Stowe House', 'space', 'Harriet Beecher Stowe House, next door: a separate museum (Stowe Center), own tickets',
         ways['194716938'][:-1]),
        ('Path to the Museum Center', 'corridor', 'Path from the main lot to the Museum Center: stairs, or the '
                                                  'accessible ramp to their right', band(ways['907546977'][:13], 1.5)),
        ('Steps', 'corridor', 'Steps and ramp to the Museum Center door', band([(-21.5, -58.5), (2.0, -60.1),
                                                                               (6.2, -60.5), (6.1, -70.7)], 1.5)),
        ('Path to the House', 'corridor', 'Gravel and stone path from the Museum Center to the house (uneven, slippery '
                                          'when wet)', band([(6.2, -60.5), (7.1, -50.2), (9.8, -26.7), (15.5, -21.1),
                                                             (16.4, -19.2), (16.0, -13.3), (14.2, -6.4),
                                                             (13.8, -1.3)], 1.5)),
        ('Patio Path', 'corridor', 'Path along the patio to Forest Street',
         band([(6.2, -60.5), (26.4, -61.9), (26.8, -57.6), (27.5, -56.7), (60.9, -60.8), (98, -65.1)], 1.5)),
        ('Farmington Avenue', 'corridor', 'Farmington Avenue: CT Transit buses 60, 62, 64 and 66 stop at Woodland '
                                          'Street, next to the museum', band(farm, 7)),
        ('Forest Street', 'corridor', 'Forest Street', band(clip(ways['17174522'], x1=125, y0=-104, y1=40), 4)),
    ]
    doors = [('Parking', 'Path to the Museum Center', (-60.5, -53)), ('Path to the Museum Center', 'Steps', (-21.5, -58.5)),
             ('Steps', 'Museum Center', (6.1, -70.7)), ('Steps', 'Path to the House', (6.2, -60.5)),
             ('Path to the House', 'House', (13.8, -1.3)), ('Steps', 'Patio Path', (8, -60.6)),
             ('Patio Path', 'Fran Gordon Garden', (36, -59.5)), ('Patio Path', 'Forest Street Parking', (75, -62.5)),
             ('Path to the House', 'Turn-Around Garden', (9.5, -24)), ('Grounds', 'Carriage House', (14, -30.5)),
             ('Grounds', 'Lower Parking', (-80, -52)), ('Grounds', 'South Parking', (-78, -73)),
             ('Grounds', 'Stowe House', (80, -25)), ('Grounds', 'Sundial Garden', (36, -62))]
    amen = [('entrance', 6.1, -70.7), ('entrance', 13.8, -1.3), ('restroom', 30, -78), ('dining', 15, -76),
            ('shop', 45, -76)]
    labels = [('P · Main lot (free)', 'area', -86, -20),
              ('P · 65 Forest Street (limited mobility)', 'area', 74, -90),
              ('Start here: tickets, restrooms, café', 'area', 38, -95),
              ('Front door (tours only)', 'area', 34, 4),
              ('Bus stop: Farmington Ave at Woodland St', 'area', 50, 36),
              ('No restrooms in the house', 'area', -38, 8)]
    return rooms, [], doors, amen, labels


# ---- the house -------------------------------------------------------------------------------------------------------
# Units: pixels of the HABS first-floor sheet (3200 px wide). North is to the right on the sheets; R() turns it up.

HD = 'Historic American Buildings Survey drawings (HABS CT-359, 1995)'
HOUSE_1 = [
    ('Entrance Hall', 'gallery', 'Entrance Hall: Associated Artists’ 1881 stencils, the carved staircase and the '
                                 'fireplace', rect(1328, 1024, 1745, 1504), 'Entrance Hall'),
    ('Drawing Room', 'gallery', 'Drawing Room', [(1745, 1024), (2080, 1024), (2080, 1150), (2200, 1180), (2225, 1280),
                                                 (2200, 1380), (2080, 1410), (2080, 1520), (1745, 1520)], None),
    ('Dining Room', 'gallery', 'Dining Room', rect(1600, 704, 2080, 1008), None),
    ('Library', 'gallery', 'Library, with the carved Scottish mantel', [
        (1056, 704), (1216, 704), (1216, 560), (1290, 544), (1390, 544), (1450, 580), (1450, 704), (1600, 704),
        (1600, 1008), (1056, 1008)], None),
    ('Conservatory', 'gallery', 'Conservatory, with its fountain (the girls called it “the Jungle”)',
     [(1056, 712), (940, 712), (850, 750), (795, 850), (805, 950), (870, 1020), (1056, 1020)], None),
    ('Mahogany Guest Room', 'gallery', 'Mahogany Guest Room', [(1320, 1024), (900, 1024), (864, 1090), (864, 1230),
                                                               (900, 1296), (1320, 1296)], 'Mahogany Room'),
    ('Dressing Room', 'gallery', 'Dressing Room of the guest suite', rect(872, 1312, 1152, 1504), None),
    ('Guest Bath', 'gallery', 'Bathroom of the guest suite', rect(1152, 1312, 1328, 1504), 'Bath'),
    ('Butler’s Pantry', 'gallery', 'Butler’s Pantry (George Griffin’s domain)', rect(1790, 470, 2000, 700), 'Pantry'),
    ('Service Hall', 'corridor', 'Service hall and the back stairs', rect(2000, 700, 2600, 790), None),
    ('Kitchen', 'gallery', 'Kitchen: house tours end here, 40 steps down from the Billiard Room',
     rect(2184, 432, 2496, 700), None),
    ('Servants’ Hall', 'gallery', 'Servants’ Hall', rect(2504, 392, 2792, 600), None),
    ('Service Entry', 'space', 'Service entry: the way out after the tour', rect(2600, 608, 2792, 784), None),
    ('Ombra', 'gallery', 'The Ombra (Italian for “shade”): the big covered porch', [
        (520, 1240), (864, 1240), (864, 1504), (1760, 1504), (1760, 1680), (530, 1680), (408, 1600), (408, 1320)],
     None),
    ('Porte-cochère', 'gallery', 'Porte-cochère and the front steps, where tours go in', rect(1480, 1680, 1824, 2064),
     None),
]
HOUSE_1_CLOSED = [rect(2032, 432, 2184, 700)]                        # back stairs, closets
HOUSE_1_DOORS = [('Porte-cochère', 'Ombra', (1650, 1680)), ('Ombra', 'Entrance Hall', (1650, 1504)),
                 ('Entrance Hall', 'Drawing Room', (1745, 1150)), ('Entrance Hall', 'Library', (1536, 1008)),
                 ('Entrance Hall', 'Dining Room', (1664, 1008)), ('Library', 'Dining Room', (1600, 850)),
                 ('Library', 'Conservatory', (1056, 860)), ('Library', 'Mahogany Guest Room', (1104, 1012)),
                 ('Mahogany Guest Room', 'Entrance Hall', (1325, 1250)),
                 ('Mahogany Guest Room', 'Dressing Room', (1000, 1300)), ('Dressing Room', 'Guest Bath', (1152, 1400)),
                 ('Mahogany Guest Room', 'Ombra', (868, 1260)), ('Dining Room', 'Butler’s Pantry', (1900, 704)),
                 ('Butler’s Pantry', 'Service Hall', (2000, 720)), ('Service Hall', 'Kitchen', (2300, 700)),
                 ('Service Hall', 'Service Entry', (2600, 740)), ('Service Entry', 'Servants’ Hall', (2700, 604))]
HOUSE_1_AMENITIES = [('entrance', 1650, 1900), ('entrance', 2660, 860), ('stairs', 1360, 1150),
                     ('stairs', 2100, 600)]
HOUSE_1_LABELS = [('Tours go in here, under the porte-cochère', 'area', 1650, 2150),
                  ('Way out: down the back stairs to the kitchen', 'area', 2700, 950),
                  ('Floor 1 is wheelchair accessible; no elevator to floors 2 and 3', 'area', 600, 1000),
                  ('No restrooms in the house: use the Museum Center', 'area', 2400, 1200),
                  ('North: Farmington Avenue', 'area', 2850, 1100)]

HOUSE_B = [
    ('Basement Hall', 'gallery', 'Basement hall (the gift shop and visitor center in 1995): seen on Living History '
                                 'tours, where photos are allowed', rect(1089, 733, 2037, 997), 'Basement'),
    ('Basement Entry', 'space', 'Basement entry under the pantry', rect(1790, 470, 2037, 733), None),
    ('Display Room', 'gallery', 'Display room', rect(1313, 1009, 1738, 1273), None),
]
HOUSE_B_CLOSED = [rect(864, 1043, 1301, 1308), rect(876, 1308, 1738, 1498), rect(1738, 1193, 2037, 1498),
                  rect(2043, 537, 2256, 756), rect(2256, 537, 2491, 698), rect(2509, 388, 2785, 790)]
HOUSE_B_DOORS = [('Basement Entry', 'Basement Hall', (1900, 733)), ('Basement Hall', 'Display Room', (1700, 1000))]
HOUSE_B_AMENITIES = [('stairs', 1347, 1112)]
HOUSE_B_LABELS = [('Boiler rooms, storage and staff rooms: closed', 'area', 1100, 1600)]

F2 = (-33, 0)                                         # floor-2 sheet -> floor-1 sheet (outer walls matched)
HOUSE_2 = [
    ('Upper Hall', 'gallery', 'Upper hall, over the Entrance Hall', rect(1350, 1012, 1781, 1287), 'Upper Hall'),
    ('Clemens Bedroom', 'gallery', 'Mr. and Mrs. Clemens’ Bedroom', [
        (1781, 1100), (2112, 1100), (2112, 1112), (2287, 1150), (2287, 1350), (2112, 1387), (2112, 1506),
        (1781, 1506)], 'Clemens Bedroom'),
    ('Small Room', 'gallery', 'Small room off the upper hall (10 x 10 ft)', rect(1581, 1294, 1781, 1500), None),
    ('Susy’s Bedroom', 'gallery', 'Susy’s Bedroom', rect(1256, 1294, 1581, 1506), 'Susy’s Room'),
    ('South-east Bath', 'gallery', 'Bathroom (south-east corner)', rect(1087, 1306, 1256, 1506), 'Bath'),
    ('Clara and Jean’s Bedroom', 'gallery', 'Clara and Jean’s Bedroom', [
        (1350, 1012), (940, 1012), (900, 1080), (900, 1240), (940, 1306), (1350, 1306)], 'Clara & Jean'),
    ('School Room', 'gallery', 'School Room: the girls’ schoolroom', [
        (1100, 680), (1250, 680), (1250, 525), (1481, 525), (1481, 680), (1475, 680), (1475, 1000), (1100, 1000)],
     None),
    ('West Bath', 'gallery', 'Bathroom (west side)', rect(1472, 706, 1631, 894), 'Bath'),
    ('Langdon Guest Room', 'gallery', 'Langdon Guest Room', rect(1637, 706, 1887, 1006), 'Langdon Room'),
    ('Back Hall', 'corridor', 'Back hall and service stairs', rect(2031, 706, 2525, 769), None),
]
HOUSE_2_CLOSED = [rect(1472, 894, 1631, 1006), rect(1887, 706, 2031, 1006), rect(2081, 400, 2531, 619),
                  rect(2543, 369, 2825, 638), rect(2531, 638, 2825, 763), rect(1787, 1012, 2094, 1087)]
HOUSE_2_DOORS = [('Upper Hall', 'Clara and Jean’s Bedroom', (1350, 1150)), ('Upper Hall', 'Susy’s Bedroom', (1330, 1294)),
                 ('Upper Hall', 'School Room', (1419, 1006)), ('Upper Hall', 'Langdon Guest Room', (1675, 1009)),
                 ('Upper Hall', 'Clemens Bedroom', (1781, 1180)), ('Upper Hall', 'Small Room', (1650, 1290)),
                 ('School Room', 'West Bath', (1474, 800)), ('Clara and Jean’s Bedroom', 'South-east Bath', (1150, 1306)),
                 ('Langdon Guest Room', 'Back Hall', (2031, 740))]
HOUSE_2_AMENITIES = [('stairs', 1460, 1150), ('stairs', 2070, 1000)]
HOUSE_2_LABELS = [('Offices in the service wing: closed', 'area', 2450, 300)]

F3 = (-8, 4)                                          # floor-3 sheet -> floor-1 sheet
HOUSE_3 = [
    ('Billiard Room', 'gallery', 'Billiard Room: Mark Twain’s study, where he wrote Huckleberry Finn', [
        (1068, 712), (1212, 712), (1212, 580), (1260, 538), (1410, 538), (1458, 580), (1458, 712), (1608, 712),
        (1608, 1024), (1068, 1024)], None),
    ('Third-floor Guest Room', 'gallery', 'Third-floor guest room', rect(1614, 712, 2070, 1018), 'Guest Room'),
    ('Third-floor Hall', 'gallery', 'Third-floor hall', rect(1188, 1030, 1740, 1300), 'Hall'),
    ('Texas Deck', 'gallery', 'The “Texas deck”: a porch named after the top deck of a Mississippi steamboat', [
        (1128, 1006), (900, 1006), (846, 1080), (846, 1250), (900, 1330), (1128, 1330)], None),
    ('Servants’ Room', 'gallery', 'Servants’ room', rect(1752, 1108, 1986, 1498), None),
]
HOUSE_3_CLOSED = [rect(1152, 1228, 1314, 1498), rect(1314, 1312, 1752, 1390), rect(2094, 460, 2520, 652),
                  rect(1740, 1030, 1980, 1108)]
HOUSE_3_DOORS = [('Third-floor Hall', 'Billiard Room', (1520, 1027)), ('Third-floor Hall', 'Third-floor Guest Room', (1680, 1024)),
                 ('Third-floor Hall', 'Texas Deck', (1150, 1150)), ('Third-floor Hall', 'Servants’ Room', (1752, 1150)),
                 ('Billiard Room', 'Third-floor Guest Room', (1611, 850))]
HOUSE_3_AMENITIES = [('stairs', 1340, 1150), ('stairs', 1860, 1070)]
HOUSE_3_LABELS = [('41 steps up from floor 1; no elevator', 'area', 1400, 1700)]

S = 0.45                # map units per pixel of the sheets
C = 3000                # R(x, y) = (y, C - x): the sheets' right (north) goes to the top


def R(dx=0, dy=0):
    return lambda x, y: [round((y + dy) * S, 1), round((C - (x + dx)) * S, 1)]


# ---- the Museum Center (approximate) --------------------------------------------------------------------------------
MK = 8                  # map units per metre in the Museum Center


def M(x, y):
    return [round(x * MK, 1), round((-60 - y) * MK, 1)]


def museum_center(ways):
    outline = ways['194716940'][:-1]
    c1 = [
        ('Entrance Hall (MC)', 'gallery', 'Entrance Hall: tickets, the introduction panels, the Mark Twain bench and '
                                          'LEGO Mark Twain; every tour starts here', rect(1.5, -80, 14, -70.7),
         'Entrance Hall'),
        ('Museum Store', 'gallery', 'Museum Store: books, souvenirs, Victorian gifts', rect(14, -80, 28, -66.5), None),
        ('Small Theatre', 'gallery', 'Small Theatre: Ken Burns’s 23-minute film on Mark Twain, on the half hour',
         rect(28, -80, 42, -66.5), None),
        ('Aetna Gallery', 'gallery', 'Aetna Gallery: “Mark Twain: I have sampled this life” and the Paige Compositor',
         rect(42, -80, 58.5, -64), None),
        ('Restrooms (MC)', 'space', 'Restrooms', rect(58.5, -79, 67.5, -66), None),
        ('Hal Holbrook Hall', 'gallery', 'Hal Holbrook Hall', [(61.6, -82.6), (67.9, -83.5), (68.2, -81.5),
                                                               (80.3, -83.0), (79.2, -91.5), (67.5, -90.0)], None),
        ('Lobby', 'corridor', 'Hallway', [(9.5, -80.3), (61.6, -80.3), (61.6, -82.6), (67.5, -89.8), (9.3, -82.3)],
         None),
    ]
    c1_doors = [('Entrance Hall (MC)', 'Lobby', (11, -80.3)), ('Lobby', 'Museum Store', (21, -80)),
                ('Lobby', 'Small Theatre', (35, -80)), ('Lobby', 'Aetna Gallery', (50, -80)),
                ('Lobby', 'Restrooms (MC)', (60, -80)), ('Lobby', 'Hal Holbrook Hall', (64, -86)),
                ('Entrance Hall (MC)', 'Museum Store', (14, -75))]
    c1_amen = [('entrance', 6.1, -70.7), ('info', 8, -76), ('shop', 21, -73), ('restroom', 63, -72),
               ('elevator', 4, -78), ('stairs', 11, -78)]
    c1_labels = [(APPROX + ': no plan of the Museum Center is published; rooms placed from the museum’s pages',
                  'area', 40, -96), ('Door from the steps and the ramp', 'area', 6, -64)]
    c2 = [
        ('Nook Café', 'gallery', 'The Nook Farm Café (Café Louise): May–October, about 11 am–3 pm', rect(1.5, -80, 20, -70.7),
         None),
        ('Upstairs Hallway', 'corridor', 'Second-floor hallway', rect(20, -80, 42, -76), None),
        ('Second Gallery', 'gallery', 'Second gallery: changing exhibitions (a new one opens in fall 2026)',
         rect(20, -76, 42, -66.5), 'Gallery 2'),
    ]
    c2_doors = [('Nook Café', 'Upstairs Hallway', (20, -78)), ('Upstairs Hallway', 'Second Gallery', (31, -76))]
    c2_amen = [('dining', 10, -75), ('elevator', 4, -78), ('stairs', 11, -78)]
    c2_labels = [(APPROX + ': places on this floor are a guess', 'area', 40, -96)]
    return outline, (c1, c1_doors, c1_amen, c1_labels), (c2, c2_doors, c2_amen, c2_labels)


def centre(pts):
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def build_floors(ways):
    g_rooms, g_closed, g_doors, g_amen, g_labels = grounds(ways)
    f1, f2, f3 = R(), R(*F2), R(*F3)
    hx, hy = centre(ways['194716932'][:-1])
    cx, cy = f1(1800, 1100)
    gx, gy = G(hx, hy)
    hshift = (round(gx - cx, 1), round(gy - cy, 1))
    outline, (c1, c1d, c1a, c1l), (c2, c2d, c2a, c2l) = museum_center(ways)
    mx, my = centre(outline)
    mgx, mgy = G(mx, my)
    mcx, mcy = M(mx, my)
    mshift = (round(mgx - mcx, 1), round(mgy - mcy, 1))
    mc_closed = []
    spec = [
        ('G', 'Grounds', 'Parking · Museum Center · the house · Carriage House · gardens', 0, G, (0, 0),
         [(a, b, c, d, None) for a, b, c, d in g_rooms], g_closed, g_doors, g_amen, g_labels),
        ('C1', 'Museum Center · Floor 1', 'Tickets · film · Aetna Gallery · store · restrooms (inside approximate)', 1,
         M, mshift, [('Museum Center (outline)', 'space', 'Museum Center', outline, None)] + c1, mc_closed, c1d, c1a, c1l),
        ('C2', 'Museum Center · Floor 2', 'Nook Café · second gallery (approximate)', 2, M, mshift,
         [('Museum Center (floor 2)', 'space', 'Museum Center, second floor', outline, None)] + c2, [], c2d, c2a, c2l),
        ('B', 'House · Basement', 'Seen on Living History tours', 3, f1, hshift, HOUSE_B, HOUSE_B_CLOSED,
         HOUSE_B_DOORS, HOUSE_B_AMENITIES, HOUSE_B_LABELS),
        ('1', 'House · Floor 1', 'Entrance Hall · Library · Conservatory · Dining and Drawing Rooms · kitchen', 4, f1,
         hshift, HOUSE_1, HOUSE_1_CLOSED, HOUSE_1_DOORS, HOUSE_1_AMENITIES, HOUSE_1_LABELS),
        ('2', 'House · Floor 2', 'The Clemenses’ bedroom · Susy’s room · School Room · guest room', 5, f2, hshift,
         HOUSE_2, HOUSE_2_CLOSED, HOUSE_2_DOORS, HOUSE_2_AMENITIES, HOUSE_2_LABELS),
        ('3', 'House · Floor 3', 'Billiard Room (Twain’s study) · Texas deck', 6, f3, hshift, HOUSE_3, HOUSE_3_CLOSED,
         HOUSE_3_DOORS, HOUSE_3_AMENITIES, HOUSE_3_LABELS),
    ]
    floors = []
    seen = set()
    for fid, label, area, order, pt, shift, rooms_in, closed_in, doors_in, amen, labels in spec:
        rooms = []
        for rid, kind, name, poly, short in rooms_in:
            assert rid not in seen, rid
            seen.add(rid)
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': [pt(*q) for q in poly]}
            if kind == 'gallery': r['label'] = short or rid
            rooms.append(r)
        ids = {r['id'] for r in rooms}
        doors = [{'a': a, 'b': b, 'at': pt(x, y), 'width': 14, 'axis': 'o'} for a, b, (x, y) in doors_in]
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order,
                       'transform': [1, *shift] if fid != 'G' else [1, 0, 0],
                       'rooms': rooms, 'closed': [{'poly': [pt(*q) for q in c]} for c in closed_in],
                       'amenities': [{'type': t, 'at': pt(x, y)} for t, x, y in amen],
                       'labels': [{'text': t, 'kind': k, 'at': pt(x, y)} for t, k, x, y in labels],
                       'doors': doors, **({'homeView': ['House', 'Museum Center', 'Carriage House', 'Steps']}
                                          if fid == 'G' else {})})
    return {'about': 'Built by tools/build_twain.py. The grounds come from OpenStreetMap (the property line and the '
                     'gardens are approximate); the house is traced from the Historic American Buildings Survey '
                     'drawings (HABS CT-359, 1995), turned so north is up. The Museum Center has no published plan: '
                     'its outline is OpenStreetMap’s and the rooms inside are approximate.',
            'source': 'OpenStreetMap (grounds), Historic American Buildings Survey CT-359 (house plans, Library of '
                      'Congress), The Mark Twain House & Museum’s visitor pages (parking, accessibility, Museum Center)',
            'units': f'grounds: metres x {K}, north up; house: pixels of the HABS sheets x {S}, turned north up; '
                     f'Museum Center: metres x {MK}',
            'defaultFloor': 'G', 'galleryWord': 'Room', 'floors': floors}


# ---- the works -------------------------------------------------------------------------------------------------------
TIFF = 'Louis C. Tiffany & Co., Associated Artists'
HOUSE_BY = 'Edward Tuckerman Potter (architect)'
HABS_CREDIT = 'Jack E. Boucher, Historic American Buildings Survey (Library of Congress), public domain'
# id, title, artist, date, room, photo (HABS number or museum picture URL), text
WORKS = [
    ('house', 'The Mark Twain House', HOUSE_BY, '1873–1874', 'House', '023151',
     'Sam and Olivia (Livy) Clemens built this 25-room, three-floor house of brick and brownstone in 1873–74 and lived '
     'here with their daughters Susy, Clara and Jean from 1874 to 1891, what Mark Twain called the happiest and most '
     'productive years of his life. Here he wrote The Adventures of Tom Sawyer, The Prince and the Pauper, Adventures '
     'of Huckleberry Finn and A Connecticut Yankee in King Arthur’s Court. The house was shown only by guided tour; '
     'the photo shows the east (front) side.'),
    ('street-side', 'The street side and the service wing', HOUSE_BY, '1874', 'House', '023150',
     'The side facing Farmington Avenue, with the service wing: the kitchen, the butler’s pantry and the servants’ '
     'rooms, where the butler George Griffin, the cook, the maids and the nurse worked. Its gables, balconies and '
     'porches gave the house its nickname as a “Mississippi steamboat”.'),
    ('carriage-house', 'The Carriage House', HOUSE_BY, '1874', 'Carriage House', 'ct0640:183886',
     'The Clemenses’ stable and carriage house. The coachman Patrick McAleer, their highest-paid servant, lived '
     'upstairs with his wife and children; Twain called him his idea of “an ideal gentleman”. Today the hayloft holds '
     'offices and the barn floor is a rental hall, so it is not part of the tour.'),
    ('porte-cochere', 'The porte-cochère', HOUSE_BY, '1874', 'Porte-cochère', '023165',
     'Carriages drove up the hill from Farmington Avenue and under this covered entrance, so guests could step out of '
     'the rain at the front door. Tours go into the house here.'),
    ('ombra', 'The Ombra', HOUSE_BY, '1874', 'Ombra', '023172',
     'The large covered porch the family called the Ombra (Italian for “shade”). In summer it was an outdoor living '
     'room; the carriage drive ran alongside it to the Carriage House.'),
    ('entrance-hall', 'The Entrance Hall', TIFF, '1881', 'Entrance Hall', '023185',
     'In 1881 the Clemenses hired Louis C. Tiffany’s firm, Associated Artists, to decorate the newly enlarged hall and '
     'the main rooms. The dark red walls and ceiling are covered with silver-stencilled patterns inspired by Morocco, '
     'India, Japan, China and Turkey. The same year, the firm redecorated the state rooms of the White House.'),
    ('hall-fireplace', 'Fireplace of the Entrance Hall', TIFF, '1881', 'Entrance Hall', '023187',
     'The fireplace on the north wall of the hall, framed by Associated Artists’ carved woodwork and stencilling.'),
    ('staircase', 'The main staircase', HOUSE_BY, '1874; decorated 1881', 'Entrance Hall', '023188',
     'The carved staircase rises from the south-west corner of the hall to the second and third floors. The house has '
     'no elevator: a full tour climbs 41 steps to the Billiard Room.'),
    ('newel-post', 'Newel post with lamps', TIFF, '1881', 'Entrance Hall', '023189',
     'The lamps on the newel post at the foot of the staircase. The house had the latest comforts of the 1870s: gas '
     'light, central heating, plumbing, a burglar alarm, speaking tubes and one of the first private telephones in '
     'Hartford.'),
    ('bust', 'Bust of Samuel Clemens', None, None, 'Entrance Hall', '023190',
     'A bust of Samuel Clemens in the hall, in front of the stencilled walls.'),
    ('drawing-room', 'The Drawing Room', TIFF, '1881', 'Drawing Room', '023192',
     'The formal parlour where Livy received callers and the family put on plays and charades. Associated Artists '
     'decorated it with pale walls and stencilling inspired by India.'),
    ('drawing-room-fireplace', 'Drawing Room fireplace', TIFF, '1881', 'Drawing Room', '023193',
     'The south wall of the Drawing Room with its fireplace.'),
    ('dining-room', 'The Dining Room', TIFF, '1881', 'Dining Room', '023197',
     'Where the Clemenses entertained guests such as William Dean Howells. The walls are covered with embossed, '
     'gilded paper chosen by Associated Artists.'),
    ('dining-fireplace', 'The window above the fireplace', HOUSE_BY, '1874', 'Dining Room', '023201',
     'The chimney of the Dining Room splits around a window, so the family could watch the snow falling outside '
     'right above the flames of the fire.'),
    ('library', 'The Library and its Scottish mantel', None, 'mantel 17th century; installed 1879', 'Library', '023205',
     'The family’s favourite room. The carved wooden mantel came from Ayton Castle in Scotland; the Clemenses bought it '
     'on their travels in 1879. Twain made up stories for his daughters that had to include every object on the '
     'mantel, in order, from the painting at one end to the one at the other.'),
    ('library-alcove', 'The Library alcove', HOUSE_BY, '1874', 'Library', '023203',
     'The bay window alcove on the west side of the Library, looking out over the hill where the Park River once ran.'),
    ('conservatory', 'The Conservatory', HOUSE_BY, '1874', 'Conservatory', '023209',
     'Opening off the Library, the glass conservatory has a fountain and a marble-chip floor and is filled with '
     'plants, kept today by UConn Master Gardeners. The Clemens girls called it “the Jungle”.'),
    ('mahogany-room', 'The Mahogany Guest Room', None, None, 'Mahogany Guest Room', '023211',
     'The first-floor guest room, with its own dressing room and bathroom, so important guests did not have to climb '
     'the stairs.'),
    ('speaking-tube', 'Speaking tube to the kitchen', None, '1870s', 'Mahogany Guest Room', '023212',
     'The mouthpiece of a speaking tube: guests could talk straight to the kitchen and ask the servants for '
     'what they needed.'),
    ('dressing-room', 'Dressing Room of the guest suite', None, None, 'Dressing Room', '023214',
     'The dressing room of the first-floor guest suite.'),
    ('guest-bath', 'Bathroom of the guest suite', None, '1870s', 'Guest Bath', '023215',
     'The guest bathroom, with running water: a luxury in the 1870s. The house had several bathrooms with flush '
     'toilets.'),
    ('upper-hall', 'The second-floor stair hall', None, None, 'Upper Hall', '023217',
     'The second-floor hall at the top of the main staircase, which leads to the family’s bedrooms.'),
    ('venetian-bed', 'Mr. and Mrs. Clemens’ bedroom and the Venetian bed', None, 'bed bought 1878', 'Clemens Bedroom',
     '023219',
     'The carved bed, with angels on the posts and headboard, was bought in Venice in 1878. The Clemenses slept with '
     'their heads at the foot of the bed so they could look at the carving. The girls were allowed to take down the '
     'small angels and play with them.'),
    ('gas-cord', 'Gas “cord” to a lamp', None, '1870s', 'Clemens Bedroom', '023220',
     'A flexible tube carried gas from the ceiling gasolier to a lamp beside the bed: the latest thing in home '
     'lighting before electricity.'),
    ('langdon-room', 'The Langdon Guest Room', None, None, 'Langdon Guest Room', '023222',
     'A second-floor guest room.'),
    ('west-bath', 'Second-floor bathroom', None, '1870s', 'West Bath', '023224',
     'A bathroom on the west side of the second floor, with its tub.'),
    ('school-room', 'The School Room', None, None, 'School Room', '023226',
     'Twain first used this room as his study; then it became the schoolroom where Susy, Clara and Jean had their '
     'lessons with a governess, and Twain moved his writing up to the Billiard Room.'),
    ('se-bath', 'South-east bathroom', None, '1870s', 'South-east Bath', '023227',
     'The bathroom in the south-east corner of the second floor.'),
    ('clara-jean', 'Clara and Jean’s Bedroom', None, None, 'Clara and Jean’s Bedroom', '023228',
     'The bedroom of the two younger daughters, Clara (born 1874) and Jean (born 1880), with its fireplace.'),
    ('susy', 'Susy’s Bedroom', None, None, 'Susy’s Bedroom', '023229',
     'The room of the eldest daughter, Susy, who at 13 wrote a biography of her father (“We are a very happy family!”). '
     'She died of meningitis in this house in 1896, aged 24, while her parents were abroad.'),
    ('third-hall', 'The third-floor stair hall', None, None, 'Third-floor Hall', '023230',
     'The hall at the top of the stairs, leading to the Billiard Room, the guest room, the servants’ room and the Texas '
     'deck.'),
    ('billiard-room', 'The Billiard Room, Mark Twain’s study', None, None, 'Billiard Room', '023231',
     'Twain’s private hideaway, where he played billiards with friends, smoked and wrote: Adventures of Huckleberry '
     'Finn was finished here. The ceiling is stencilled with crossed billiard cues, pipes and cigars.'),
    ('marble-window', 'Carved marble window', None, None, 'Billiard Room', '023232',
     'A translucent, carved marble window in the south wall of the Billiard Room.'),
    ('texas-deck', 'The Texas deck', HOUSE_BY, '1874', 'Texas Deck', '023182',
     'A third-floor porch named after the “Texas deck”, the top deck of a Mississippi steamboat, where the pilot and '
     'the officers lived: a nod to Twain’s years as a river pilot.'),
    # Museum Center (marktwainhouse.org/exhibitions/permanent-exhibits/)
    ('sampled-this-life', 'Mark Twain: I have sampled this life', 'Exhibition', None, 'Aetna Gallery',
     'loc:3c27284',
     'The life and work of Samuel Clemens (1835–1910): journalist, lecturer, entrepreneur, inventor and one of the most '
     'celebrated American writers. On view: first editions of his books, spectacles he wore, and the Paige '
     'Compositor.'),
    ('paige-compositor', 'The Paige Compositor', 'James W. Paige (inventor)', '1880s', 'Aetna Gallery',
     '/wp-content/uploads/2024/08/Compositor-drawing-622-1024x746.jpg',
     'A typesetting machine meant to set type automatically. Twain poured a fortune into it; only two were ever fully '
     'built and neither went beyond testing. This is the only one left. A newspaper called it “marvelously ingenious… '
     'worthless commercially, the costliest machine ever built.”'),
    ('twain-bench', 'Mark Twain Bench', 'Gary Lee Price', None, 'Entrance Hall (MC)',
     '/wp-content/uploads/2022/06/twainBench_crop-238x300.jpg',
     'A bronze bench where you can sit next to Mark Twain (and take a selfie, #SittingWithSam). Donated in memory of '
     'Alexander “Sandy” Gaston (1946–2021).'),
    ('lego-twain', 'LEGO Mark Twain', 'LEGO master builders, Enfield, CT', '2009', 'Entrance Hall (MC)',
     '',
     'A 6-foot-tall, 150-pound Mark Twain made of LEGO bricks, welcoming visitors since 2009. On loan from LEGO '
     'Systems Inc.'),
    ('introduction', 'The Mark Twain House: Introduction', 'Joseph Philippon (design)', '2020', 'Entrance Hall (MC)',
     '/wp-content/uploads/2021/06/Introduction-2-300x200.jpg',
     'Panels at the entrance that introduce the house and the family who lived in it: Sam, Livy, Susy, Clara and Jean. '
     'A good start before your tour.'),
    ('ken-burns-film', 'Mark Twain, a film by Ken Burns', 'Ken Burns, Florentine Films', '2001', 'Small Theatre',
     'loc:3a29547',
     'A 23-minute introduction to Mark Twain’s life, his family and the house, shown on a loop (on the half hour). '
     'Included with any ticket.'),
    ('giant-puppet', 'Mark Twain giant puppet', 'Anne Cubberly’s Giant Puppets', '2023–2024', 'Hal Holbrook Hall',
     '/wp-content/uploads/2024/03/Puppet-WebBlocks.png',
     'A large-scale puppet of Mark Twain, made with a 2023 Roberts Foundation for the Arts grant, that goes out as the '
     'museum’s ambassador to the community.'),
    ('twains-world', 'Twain’s World', 'Karen Rossi', '1995', 'Nook Café',
     '/wp-content/uploads/2022/06/20220228_091153-scaled.jpg',
     'A metal mobile with about 40 figures celebrating Hartford’s cultural history, made for a 1995 project of the '
     'Hartford Courant’s Sunday magazine. Can you name them all?'),
    ('elm-bench', 'Suffield Elm Bench', 'City Bench, Higganum, CT', '2009', 'Upstairs Hallway',
     '',
     'A bench made from the largest American elm in Connecticut, which grew on a farm in Suffield and came down in '
     '2009. The makers counted 148 growth rings.'),
    ('bontorno', 'Untitled (Mark Twain’s Birth and Death Places)', 'Nick Bontorno', '2009', 'Nook Café',
     '/wp-content/uploads/2021/06/stormfield-1-1-200x300.jpg',
     'Two paintings: the small farmhouse in Florida, Missouri, where Samuel Clemens was born, and Stormfield, the '
     'mansion in Redding, Connecticut, where he died. Bontorno was caretaker of Quarry Farm in Elmira, New York, '
     'where the Clemenses spent their summers. Oil on cloth; gift of Patty and John Pascal.'),
]
GUESSED = {'bust', 'twain-bench', 'lego-twain', 'introduction', 'giant-puppet', 'twains-world', 'elm-bench', 'bontorno',
           'sampled-this-life', 'paige-compositor', 'ken-burns-film'}


def fetch(url, dest):
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
        time.sleep(1.5)
        if not out: return None
        dest.write_bytes(out)
    return dest


def picture(key, photo):
    """Download once and save a phone-sized JPEG; returns (app path, credit, page)."""
    if not photo: return None, None, SITE + '/exhibitions/permanent-exhibits/'
    if photo.startswith('loc:'):
        n = photo[4:]
        src = f'https://tile.loc.gov/storage-services/service/pnp/cph/{n[:2]}{n[2]}0000/{n[:3]}{n[3]}000/{n[:4]}{n[4]}00/{n}r.jpg'
        credit, page = 'Mark Twain (Library of Congress), not a photo of the exhibit', SITE + '/exhibitions/permanent-exhibits/'
    elif photo.startswith('/'):
        src, credit, page = SITE + photo, 'The Mark Twain House & Museum', SITE + '/exhibitions/permanent-exhibits/'
    elif photo.startswith('ct0640:'):
        n = photo.split(':')[1]
        src = f'https://tile.loc.gov/storage-services/service/pnp/habshaer/ct/ct0600/ct0640/photos/{n}pv.jpg'
        credit, page = 'Historic American Buildings Survey (Library of Congress), public domain', \
            f'https://www.loc.gov/pictures/item/ct0640.photos.{n}p/'
    else:
        src, credit, page = f'{HABS}{photo}pv.jpg', HABS_CREDIT, f'{HABS_ITEM}{photo}p/'
    raw = fetch(src, CACHE / 'img' / f'{key}.bin')
    if not raw: return None, None, page
    dest = OUT / 'images' / f'{key}.jpg'
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(io.BytesIO(raw.read_bytes()))
        if im.mode in ('RGBA', 'LA', 'P'):
            im = im.convert('RGBA')
            bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=im.split()[-1]); im = bg
        im = im.convert('RGB')
        im.thumbnail((1000, 1000))
        im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/twain/images/{key}.jpg', credit, page


def build_works(floors):
    names = {r['id']: (r['name'], f['id']) for f in floors['floors'] for r in f['rooms']}
    works = []
    for wid, title, artist, date, room, photo, text in WORKS:
        key = 'twain-' + wid
        img, credit, page = picture(key, photo)
        name, floor = names[room]
        a = {'id': key, 'title': title, 'artist': artist or ('Room' if floor not in ('C1', 'C2') else 'Exhibit'),
             'date': date, 'year': int(date[:4]) if date and date[:4].isdigit() else None,
             'type': 'Exhibit' if floor in ('C1', 'C2') else 'Historic room',
             'description': text, 'url': page, 'image': img, 'imageCredit': credit,
             'gallery': room, 'galleryName': name, 'floor': floor,
             'placeNote': ('In the room the museum’s exhibit page names; the place of the room is our guess.'
                           if wid in GUESSED else 'Room from the Historic American Buildings Survey photo caption.')}
        if wid in GUESSED: a['placeGuessed'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '')})
    return {'source': 'Historic American Buildings Survey CT-359 photos (Library of Congress) and The Mark Twain House & '
                      'Museum’s exhibit pages', 'checked': time.strftime('%Y-%m-%d'), 'count': len(works),
            'complete': False, 'artworks': works}


def build_guide(works):
    rows = [{k: v for k, v in {
        'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'), 'year': a.get('year'),
        'url': a['url'], 'imageUrl': a.get('image'), 'onView': True, 'gallery': a['gallery'],
        'floor': a['floor']}.items() if v not in (None, '')} for a in works['artworks']]
    return {'museum': MUSEUM, 'name': 'Mark Twain House & Museum', 'checked': works['checked'],
            'source': works['source'], 'onViewKnown': True,
            'note': 'The house itself is the great work here: its rooms, decorated in 1881 by Louis C. Tiffany’s '
                    'Associated Artists, and their famous details, with photos from the Historic American Buildings '
                    'Survey; plus the exhibits in the Museum Center. The house is shown only by guided tour, and '
                    'photos aren’t allowed inside.',
            'works': rows}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    floors = build_floors(osm())
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works = build_works(floors)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': len(guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    print(f'{works["count"]} works, {sum("image" in a for a in works["artworks"])} pictures')


if __name__ == '__main__':
    sys.exit(main())
