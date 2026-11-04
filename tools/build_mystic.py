#!/usr/bin/env python3
"""Build the Mystic Seaport Museum (Mystic, CT) map guide (run: python3 tools/build_mystic.py).

    data/mystic/floors.json      the 19-acre grounds seen from above (a flat 2D plan)
    data/mystic/artworks.json    the historic vessels, the Seaport Village exhibits and the exhibitions on view,
                                 each in the building or berth where it is
    data/mystic/images/          their pictures, made smaller for phones
    data/guides/Q1890082.json    the same list for the museum page, plus vessels and houses we can't place

The map is traced from the museum's own 2026 Map & Guide (mysticseaport.org/wp-content/uploads/2026/06/Summer_web.pdf,
linked from mysticseaport.org/visit/mystic-seaport-museum-map). Coordinates are pixels of that PDF drawn at 150 dpi,
less the top of the map (537 px). At that size one pixel is about 30 cm on the ground (the Joseph Conrad, 111 ft,
is about 110 px long), close to what the app's walking times assume. The numbered circles are read from the PDF's
own text, so every building sits where the museum's map puts its number; the outline of each building, the
walks and the berths are drawn by eye around them.

The works: Mystic Seaport has more than two million objects, but its online catalogue (mobius.mysticseaport.org)
says nothing about what is on view, and most records have no picture (none of its 67 figureheads do). So the guide
lists what a visitor actually walks through, from the museum's own pages (read once, slowly; robots.txt asks for
10 seconds between pages): the historic vessels (mysticseaport.org/explore/vessels), the trade shops and houses of
the Seaport Village (/explore/village) and the exhibitions now open (/exhibit/..., via its WordPress API).
"""
import html
import io
import json
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'mystic'
CACHE = ROOT / '.cache' / 'mystic'
MUSEUM = 'Q1890082'
SITE = 'https://mysticseaport.org'
MAP_PDF = SITE + '/wp-content/uploads/2026/06/Summer_web.pdf'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SOURCE = 'Mystic Seaport Museum 2026 Map & Guide (mysticseaport.org/visit/mystic-seaport-museum-map)'
OY = 537                     # top of the map on the PDF page at 150 dpi
_last = [0.0]


def get(url, name, binary=False, delay=10):
    """Read a page once, politely (the site's robots.txt asks for 10 s between requests), and keep it."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / name
    if not f.exists():
        wait = _last[0] + delay - time.time()
        if wait > 0: time.sleep(wait)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
        _last[0] = time.time()
        if not out: raise SystemExit(f'could not read {url}')
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(out)
    return f.read_bytes() if binary else f.read_text(errors='replace')


def text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def box(x, y, w=30, h=22):
    return rect(round(x - w / 2), round(y - h / 2), round(x + w / 2), round(y + h / 2))


def inside(pt, pg):
    x, y = pt
    hit = False
    for (x1, y1), (x2, y2) in zip(pg, pg[1:] + pg[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def centroid(pg):
    return [sum(p[0] for p in pg) / len(pg), sum(p[1] for p in pg) / len(pg)]


def seg_closest(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return [ax + t * dx, ay + t * dy]


def edge_point(pg, toward):
    """The point on a polygon's outline closest to `toward` (where its door goes)."""
    best = None
    for a, b in zip(pg, pg[1:] + pg[:1]):
        q = seg_closest(toward, a, b)
        d = (q[0] - toward[0]) ** 2 + (q[1] - toward[1]) ** 2
        if best is None or d < best[0]: best = (d, q)
    return [round(best[1][0], 1), round(best[1][1], 1)]


def dist_to_poly(p, pg):
    if inside(p, pg): return 0
    q = edge_point(pg, p)
    return ((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2) ** .5


# ---- the map --------------------------------------------------------------------------------------------------
# Walks and open ground (corridors): you go from one to the next through the doors in WALK_DOORS.
WALKS = [
    ('shipyard', 'Henry B. du Pont Preservation Shipyard grounds', [[230, 90], [560, 90], [570, 470], [230, 470]], (300, 200)),
    ('south-entrance', 'South Entrance plaza, by the Museum Store and Anchor Mystic Café',
     [[150, 470], [400, 470], [400, 700], [150, 700]], (250, 610)),
    ('waterfront-north', 'Waterfront walk along the Mystic River',
     [[400, 620], [470, 620], [560, 700], [700, 790], [820, 870], [810, 925], [690, 895], [600, 850], [450, 785],
      [400, 780]], (560, 760)),
    ('west-path', 'West path along Greenmanville Avenue (Route 27)', [[300, 700], [410, 700], [410, 1230], [300, 1230]],
     (380, 1000)),
    ('village-north', 'Seaport Village: the lane below the Village Green',
     [[410, 1000], [455, 1040], [560, 1040], [650, 1000], [650, 1090], [800, 1090], [800, 1140], [410, 1140]],
     (560, 1110)),
    ('village-south', 'Seaport Village: the main street',
     [[410, 1140], [710, 1140], [730, 1200], [640, 1260], [580, 1300], [470, 1300], [410, 1300]], (520, 1220)),
    ('green-west', 'Paths by the Planetarium and Family Fun',
     [[170, 1230], [410, 1230], [410, 1300], [470, 1300], [470, 1440], [170, 1440]], (330, 1400)),
    ('stage', 'Walk by the Performance Stage', [[470, 1300], [575, 1300], [575, 1440], [470, 1440]], (535, 1330)),
    ('quad', 'Exhibition quadrangle', [[170, 1440], [545, 1440], [545, 1590], [170, 1590]], (330, 1560)),
    ('north-campus', 'North campus, from the North Entrance', [[150, 1590], [545, 1590], [545, 1840], [150, 1840]],
     (300, 1620)),
    ('river-walk', 'Riverside walk', [[545, 1440], [600, 1440], [600, 1840], [545, 1840]], (572, 1640)),
    ('south-lawn', 'Lawn toward the Delamar Hotel', [[300, 1840], [600, 1840], [600, 1990], [300, 1990]], (520, 1900)),
    ('beach', 'Australia Beach and the boat shops', [[650, 895], [810, 925], [800, 1090], [650, 1090]], (705, 1000)),
    ('point', 'Lighthouse Point: the Ropewalk, the Boathouse and the Sailing Center',
     [[800, 900], [1000, 900], [1100, 990], [1180, 1080], [1150, 1190], [1000, 1210], [870, 1210], [800, 1150]],
     (960, 1010)),
]
WALK_DOORS = [
    ('shipyard', 'south-entrance', (380, 470)), ('south-entrance', 'waterfront-north', (400, 650)),
    ('south-entrance', 'west-path', (350, 700)), ('waterfront-north', 'west-path', (405, 740)),
    ('waterfront-north', 'Village Green', (520, 815)), ('west-path', 'Village Green', (410, 900)),
    ('west-path', 'village-north', (410, 1100)), ('west-path', 'green-west', (360, 1230)),
    ('Village Green', 'village-north', (520, 1040)), ('Village Green', 'beach', (650, 950)),
    ('waterfront-north', 'beach', (750, 910)), ('village-north', 'beach', (720, 1090)),
    ('village-north', 'village-south', (550, 1140)), ('village-north', 'point', (800, 1115)),
    ('beach', 'point', (805, 1000)), ('village-south', 'green-west', (410, 1265)),
    ('village-south', 'stage', (520, 1300)), ('stage', 'green-west', (470, 1370)),
    ('stage', "Chubb’s Wharf", (575, 1400)), ('stage', 'quad', (510, 1440)), ('stage', 'river-walk', (560, 1440)),
    ('green-west', 'quad', (300, 1440)), ('quad', 'north-campus', (350, 1590)), ('quad', 'river-walk', (545, 1510)),
    ('north-campus', 'river-walk', (545, 1700)), ('north-campus', 'south-lawn', (450, 1840)),
    ('river-walk', 'south-lawn', (572, 1840)), ("Chubb’s Wharf", 'river-walk', (590, 1450)),
]

# Places with the museum's map number: (number, id, kind, label, name, outline). Galleries hold works.
G, S = 'gallery', 'space'
PLACES = [
    (1, 'Thompson Exhibition Building', G, 'Thompson Building',
     'Thompson Exhibition Building: Collins Gallery (Monstrous) · Propeller Coffee Bar · restrooms', rect(255, 1665, 450, 1775)),
    (3, 'Meeting House', G, 'Meeting House', 'Meeting House on the McGraw Gallery Quadrangle', rect(195, 1578, 250, 1625)),
    (4, 'Mallory Buildings', G, 'Mallory Buildings',
     'C. D. Mallory and P. R. Mallory Buildings · Home Port (ages 8–12)', rect(318, 1488, 392, 1532)),
    (5, 'Wendell Building', G, 'Wendell Building', 'Wendell Building: figureheads and ship carvings', rect(395, 1488, 445, 1532)),
    (6, 'Stillman Building', G, 'Stillman Building', 'Stillman Building (two floors; the Packard cabin is upstairs)',
     rect(450, 1500, 515, 1640)),
    (7, 'Ships Playscapes', S, None, 'Ships Playscapes (children’s play ships)', rect(275, 1425, 320, 1468)),
    (8, 'Thomas Greenman House', G, 'Greenman House', 'Thomas Greenman House (1842)', rect(178, 1410, 240, 1455)),
    (9, 'Treworgy Planetarium', S, None, 'Treworgy Planetarium', rect(298, 1290, 345, 1345)),
    (10, 'Funk Children’s Museum', S, None, 'Funk Children’s Museum (ages 7 and under)', rect(366, 1338, 408, 1378)),
    (11, 'Buckingham-Hall House', G, 'Buckingham-Hall House', 'Buckingham-Hall House (hearth cooking)', rect(395, 1262, 438, 1302)),
    (13, 'Performance Stage', S, None, 'Performance Stage', rect(492, 1395, 532, 1425)),
    (14, 'Dock Office', S, None, 'Dock Office', rect(650, 1408, 690, 1434)),
    (15, 'Whaleboat Exhibit', G, 'Whaleboat', 'Whaleboat shed on Chubb’s Wharf', rect(692, 1388, 735, 1412)),
    (16, 'Schaefer’s Spouter Tavern', S, None, 'Schaefer’s Spouter Tavern (food and drink)', box(540, 1252, 36, 26)),
    (17, 'Mystic Bank', G, 'Bank', 'Mystic Bank and Shipping Office', box(578, 1240, 32, 24)),
    (18, 'Cooperage', G, 'Cooperage', 'Cooperage (barrel making)', box(606, 1214, 30, 22)),
    (19, 'Burrows House', G, 'Burrows House', 'Burrows House: Temperance and Trade', box(637, 1182, 28, 22)),
    (20, 'Middle Wharf', G, 'Middle Wharf', 'Middle Wharf', [[668, 1235], [690, 1225], [770, 1285], [752, 1298]]),
    (21, 'Mystic Print Shop', G, 'Print Shop', 'Mystic Press printing office', box(640, 1140, 28, 22)),
    (22, 'Hoop Shop', G, 'Hoop Shop', 'George W. Smith mast hoop shop', box(690, 1160, 26, 18)),
    (23, 'Nautical Instruments Shop', G, 'Instruments', 'Nautical Instruments Shop', box(724, 1128, 30, 20)),
    (24, 'Shipsmith Shop', G, 'Shipsmith', 'James Driggs Shipsmith Shop', box(780, 1110, 34, 22)),
    (25, 'Clam Shack', G, 'Clam Shack', 'Dave’s Clam Shack (on the pier)', box(848, 1185, 24, 18)),
    (26, 'Sail Loft', G, 'Sail Loft', 'Charles Mallory Sail Loft, Rigging Loft and Ship Chandlery', rect(835, 1060, 880, 1100)),
    (27, 'Ropewalk', G, 'Ropewalk', 'Plymouth Cordage Company Ropewalk (250 ft long)',
     [[885, 1112], [1080, 1048], [1092, 1076], [897, 1140]]),
    (28, 'Small Boat Exhibit', G, 'Small Boats', 'Small Boat Exhibit building (temporarily closed)',
     [[915, 1150], [1010, 1118], [1022, 1150], [927, 1184]]),
    (30, 'Sailing Center', S, None, 'Sailing Center', rect(1085, 1130, 1140, 1172)),
    (31, 'Brant Point Lighthouse', G, 'Lighthouse', 'Brant Point Lighthouse replica: Sentinels of the Sea',
     rect(1150, 1062, 1180, 1092)),
    (32, 'Tom Clagett Boat Shed', S, None, 'Tom Clagett Boat Shed', box(986, 950, 40, 30)),
    (33, 'Boathouse', S, None, 'Boathouse: rowboats, sailboats and pedal boats (seasonal, free)', box(916, 950, 40, 34)),
    (34, 'Australia Beach', S, None, 'Australia Beach', box(856, 960, 30, 50)),
    (35, 'Salmon Shack', G, 'Salmon Shack', 'Robie Ames Salmon Shack', box(822, 1022, 22, 16)),
    (36, 'Lobster Shack', G, 'Lobster Shack', 'Lobster Shack', box(778, 905, 22, 16)),
    (37, 'Life-Saving Station', G, 'Life-Saving Station', 'New Shoreham Life-Saving Station and the Halfway House',
     rect(722, 928, 758, 962)),
    (38, 'John Gardner Boat Shop', S, None, 'John Gardner Boat Shop', rect(740, 990, 785, 1028)),
    (39, 'Clift Block', S, None, 'Clift Block', rect(648, 1018, 685, 1050)),
    (40, 'Shipcarver’s Shop', G, 'Ship Carver', 'Shipcarver’s Shop', rect(592, 1098, 622, 1126)),
    (41, 'Drug Store', G, 'Drug Store', 'Drugstore and Doctor’s Office', rect(545, 1180, 580, 1210)),
    (42, 'Seamen’s Friend Society', G, 'Reading Room', 'Seamen’s Friend Society Reading Room', rect(505, 1058, 538, 1095)),
    (43, 'Stone’s Store', G, 'General Store', 'Geo. H. Stone General Store', rect(462, 1122, 492, 1150)),
    (44, 'School House', G, 'School', 'Boardman School', rect(432, 1166, 462, 1196)),
    (45, 'Chapel', G, 'Chapel', 'Fishtown Chapel', rect(408, 1218, 440, 1250)),
    (46, 'Discovery Barn', S, None, 'Discovery Barn (hands-on activities)', rect(345, 1060, 400, 1095)),
    (47, 'Mystic River Scale Model', G, 'Scale Model', 'Mystic River Scale Model building', rect(645, 915, 690, 958)),
    (48, 'Thomas Oyster House', G, 'Oyster House', 'Thomas Oyster House', rect(668, 805, 715, 840)),
    (49, 'Thames Keel Exhibit', G, 'Thames Keel', 'Thames Keel shipbuilding exhibit', rect(362, 298, 402, 355)),
    (50, 'Main Shop', G, 'Shipyard', 'Henry B. du Pont Preservation Shipyard: Main Shop and Shipyard Exhibit Gallery',
     rect(490, 160, 550, 280)),
    (54, 'Village Green', S, None, 'Village Green (games on the green)',
     [[410, 785], [450, 785], [600, 850], [650, 900], [650, 1000], [560, 1040], [455, 1040], [410, 1000]]),
    (55, 'Toy Boat Workshop', S, None, 'Toy Boat Workshop (seasonal)', rect(305, 925, 330, 965)),
    (56, 'Garden by the Discovery Barn', S, None, 'Garden', rect(345, 1130, 395, 1175)),
    (57, 'Garden by the Chapel', S, None, 'Garden', rect(340, 1235, 378, 1268)),
    (58, 'Garden by the Planetarium', S, None, 'Garden', rect(350, 1298, 392, 1332)),
    (59, 'Anchor Mystic Café', S, None, 'Anchor Mystic Café & Sweets', rect(205, 462, 275, 525)),
    (60, 'Greenmans’ Landing', S, None, 'Greenmans’ Landing (food and drink)', rect(325, 785, 355, 870)),
    (61, 'Museum Store', S, None, 'Museum Store', rect(290, 505, 370, 560)),
    (62, 'Delamar Hotel', S, None, 'Delamar Hotel and La Plage Restaurant (next to the Museum)', rect(370, 1845, 470, 1960)),
    (63, 'Waterfront Cruises', G, 'Cruises', 'Waterfront Cruises dock and ticket booth (seasonal): Sabino and Breck Marshall',
     [[445, 735], [505, 690], [525, 705], [462, 750]]),
    # ---- vessels, drawn where the map shows them (no number of their own)
    ('M', 'Charles W. Morgan', G, 'Charles W. Morgan', 'Whaleship Charles W. Morgan (1841), at Chubb’s Wharf',
     [[630, 1335], [700, 1305], [770, 1322], [762, 1348], [700, 1362], [640, 1354]]),
    (29, 'Joseph Conrad', G, 'Joseph Conrad', 'Ship Joseph Conrad (1882): the deck is open',
     [[925, 1265], [1045, 1222], [1052, 1238], [932, 1281]]),
    ('D', 'L. A. Dunton', G, 'L. A. Dunton', 'Schooner L. A. Dunton (1921), under restoration in the Shipyard',
     [[395, 425], [420, 410], [520, 412], [525, 430], [505, 445], [400, 440]]),
    ('B', 'Sabino', G, 'Sabino', 'Steamboat Sabino (1908)', rect(468, 640, 522, 672)),
    ('E', 'Emma C. Berry', G, 'Emma C. Berry', 'Smack Emma C. Berry (1866)', rect(520, 755, 575, 775)),
    ('F', 'Fire Fighter', G, 'Fire Fighter', 'Fireboat Fire Fighter (1938), docked on Chubb’s Wharf (berth approximate)',
     rect(600, 1466, 690, 1494)),
    ('K', 'Kingston II', G, 'Kingston II', 'Tugboat Kingston II, at the North Entrance', rect(232, 1685, 252, 1755)),
]
WHARF = ("Chubb’s Wharf", 'Chubb’s Wharf (the Charles W. Morgan’s berth)',
         [[575, 1362], [650, 1366], [770, 1392], [745, 1440], [690, 1460], [600, 1460], [575, 1440]])

AMENITIES = [
    ('entrance', 152, 1715), ('entrance', 152, 590),
    ('restroom', 210, 445), ('restroom', 322, 685), ('restroom', 307, 815), ('restroom', 388, 1032),
    ('restroom', 233, 1497), ('restroom', 357, 1702), ('restroom', 975, 1015),
    ('dining', 247, 445), ('dining', 310, 770), ('dining', 510, 1265), ('dining', 281, 1702), ('dining', 407, 1897),
    ('info', 440, 729), ('info', 475, 1424), ('info', 378, 1630),
    ('shop', 330, 532),
    ('water', 288, 685), ('water', 233, 1535), ('water', 318, 1702), ('water', 938, 1015), ('water', 460, 1465),
    ('emergency', 460, 1095),
]
LABELS = [
    ('Mystic River', 'area', 800, 600), ('Seaport Village', 'area', 600, 1060),
    ('Preservation Shipyard', 'area', 330, 240), ('North Entrance', 'area', 190, 1660),
    ('South Entrance', 'area', 190, 640), ('Parking', 'note', 80, 1750), ('Parking', 'note', 80, 490),
    ('Greenmanville Avenue (Route 27)', 'note', 130, 1100),
    ('Historic site: uneven ground, watch your step', 'note', 700, 1560),
]
APPROX = 'Buildings are placed by the museum’s map numbers; outlines are drawn by eye'


def map_numbers():
    """Where each numbered circle sits on the museum's map, read from the PDF's own text."""
    get(MAP_PDF, 'map.pdf', binary=True)
    out = subprocess.run(['pdftotext', '-bbox', str(CACHE / 'map.pdf'), '-'], capture_output=True, text=True).stdout
    spots = {}
    for m in re.finditer(r'xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(\d{1,2})<', out):
        x = (float(m[1]) + float(m[3])) / 2 * 150 / 72
        y = (float(m[2]) + float(m[4])) / 2 * 150 / 72 - OY
        if 0 < y < 2025 and x > 200:          # the map, not the legend below it or "RT 27"
            spots[int(m[5])] = (round(x), round(y))
    return spots


def build_floors():
    numbers = map_numbers()
    rooms, doors = [], []
    for wid, name, pg, at in WALKS:
        rooms.append({'id': wid, 'kind': 'corridor', 'name': name, 'poly': pg, 'labelAt': list(at), 'z': 0})
    wharf_id, wharf_name, wharf_pg = WHARF
    rooms.append({'id': wharf_id, 'kind': 'space', 'name': wharf_name, 'poly': wharf_pg, 'z': 1,
                  'labelAt': [660, 1440]})
    walks = {r['id']: r for r in rooms}
    for num, pid, kind, label, name, pg in PLACES:
        if isinstance(num, int):
            assert num in numbers, f'number {num} not on the map'
        r = {'id': pid, 'kind': kind, 'name': (f'{num} · ' if isinstance(num, int) else '') + name, 'poly': pg,
             'z': 1 if pid == 'Village Green' else 2}
        if kind == G: r['label'] = label
        rooms.append(r)
    ids = {r['id'] for r in rooms}
    for a, b, (x, y) in WALK_DOORS:
        assert a in ids and b in ids, (a, b)
        doors.append({'a': a, 'b': b, 'at': [x, y], 'width': 16, 'axis': 'o'})
    # every building opens onto the walk (or wharf) nearest to it
    reach = [r for r in rooms if r['kind'] == 'corridor'] + [walks[wharf_id]]
    for r in rooms:
        if r['kind'] == 'corridor' or r['id'] in (wharf_id, 'Village Green'): continue
        c = centroid(r['poly'])
        w = min(reach, key=lambda w: dist_to_poly(c, w['poly']))
        if r['id'] in ('Charles W. Morgan', 'Fire Fighter', 'Whaleship', 'Whaleboat Exhibit', 'Dock Office'):
            w = walks[wharf_id]
        doors.append({'a': w['id'], 'b': r['id'], 'at': edge_point(r['poly'], w.get('labelAt') or centroid(w['poly'])),
                      'width': 8, 'axis': 'o'})
    # the Village Green opens onto the walks around it (WALK_DOORS)
    labels = [{'text': t, 'kind': k, 'at': [x, y]} for t, k, x, y in LABELS]
    floor = {'id': 'G', 'label': 'Museum Grounds', 'order': 0,
             'area': 'The 19-acre campus: North campus galleries · Seaport Village · Chubb’s Wharf and the Charles W. '
                     'Morgan · Lighthouse Point · Preservation Shipyard',
             'transform': [1, 0, 0], 'rooms': rooms,
             'amenities': [{'type': t, 'at': [x, y]} for t, x, y in AMENITIES], 'labels': labels, 'doors': doors}
    return {'about': 'Built by tools/build_mystic.py, traced from Mystic Seaport Museum’s own 2026 Map & Guide. ' + APPROX
                     + '. Exhibition buildings have upper floors that are not drawn.',
            'source': SOURCE, 'units': 'pixels of the 2026 map at 150 dpi (about 30 cm each)', 'defaultFloor': 'G',
            'galleryWord': 'Building', 'floors': [floor]}, numbers


# ---- works ----------------------------------------------------------------------------------------------------
def wp(kind, page):
    return json.loads(get(f'{SITE}/wp-json/wp/v2/{kind}?per_page=100&page={page}&_embed=wp:featuredmedia',
                          f'{kind}-{page}.json'))


def all_pages():
    out = []
    for p in (1, 2, 3):
        try: out += wp('pages', p)
        except SystemExit: break
    return {e['link'].rstrip('/').rsplit('/', 1)[1]: e for e in out}


SKIP_IMG = r'logo|icon|favicon|Lockup|Bingo|BrickumentaryThumbnail|Screenshot|TheLegoMovie|button|donate'


def full_size(u):
    u = u.replace('//wp-content', '/wp-content')
    return re.sub(r'-\d{2,4}x\d{2,4}(?=\.(jpe?g|png)$)', '', u)


def first_image(entry):
    fm = (entry.get('_embedded', {}).get('wp:featuredmedia') or [{}])[0]
    if fm.get('source_url') and not re.search(SKIP_IMG, fm['source_url'], re.I):
        sizes = fm.get('media_details', {}).get('sizes', {})
        best = sizes.get('large') or sizes.get('1536x1536') or sizes.get('full') or {}
        return best.get('source_url') or fm['source_url']
    for src in re.findall(r'<img[^>]+src="([^"]+)"', entry['content']['rendered']):
        if not re.search(SKIP_IMG, src, re.I): return full_size(src)
    # some pages are built with Elementor and keep their picture outside the content: use the page's share picture
    slug = entry['link'].rstrip('/').rsplit('/', 1)[1]
    og = re.search(r'<meta property="og:image" content="([^"]+)"', get(entry['link'], f'page-{slug}.html'))
    return og[1] if og and not re.search(SKIP_IMG, og[1], re.I) else None


def paragraphs(entry, n=3):
    c = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', entry['content']['rendered'], flags=re.S)
    ps = [text(p) for p in re.findall(r'<p[^>]*>(.*?)</p>', c, re.S)]
    ps = [p for p in ps if len(p) > 80 and not re.search(r'PURCHASE TICKETS|click here|Learn More$', p, re.I)]
    return '\n\n'.join(ps[:n]) or None


def picture(key, url):
    """Download once (politely) and save a phone-sized JPEG; returns the app path."""
    if not url: return None
    raw = CACHE / 'img' / (key + (Path(urllib.parse.urlparse(url).path).suffix.lower() or '.jpg'))
    dest = OUT / 'images' / f'{key}.jpg'
    if not raw.exists():
        try: get(url, 'img/' + raw.name, binary=True, delay=4)
        except SystemExit: return None
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            im = Image.open(io.BytesIO(raw.read_bytes()))
        except Exception:
            raw.unlink(); return None
        im = im.convert('RGBA') if im.mode in ('P', 'LA') else im
        if im.mode == 'RGBA':
            bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=im.split()[3]); im = bg
        im = im.convert('RGB')
        im.thumbnail((1000, 1000))
        im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/mystic/images/{key}.jpg'


# Vessels: (page slug, place id or None, title, type, built, note)
VESSELS = [
    ('morgan', 'Charles W. Morgan', 'Charles W. Morgan', 'Whaleship', '1841',
     'National Historic Landmark. America’s oldest commercial ship still afloat; you can go on deck and below.'),
    ('l-a-dunton-fishing-schooner', 'L. A. Dunton', 'L. A. Dunton', 'Fishing schooner', '1921',
     'National Historic Landmark, under restoration in the Preservation Shipyard.'),
    ('emma-c-berry-noank-smack', 'Emma C. Berry', 'Emma C. Berry', 'Noank smack', '1866', 'National Historic Landmark.'),
    ('sabino-steamboat', 'Sabino', 'Sabino', 'Steamboat', '1908',
     'National Historic Landmark. River cruises in the warm months (daily through Oct 18 in 2026).'),
    ('joseph-conrad-full-rigged-ship', 'Joseph Conrad', 'Joseph Conrad', 'Full-rigged ship', '1882',
     'Only the deck is open.'),
    ('fire-fighter', 'Fire Fighter', 'Fire Fighter', 'FDNY fireboat', '1938',
     'National Historic Landmark, docked on Chubb’s Wharf and open for tours.'),
    ('kingston-ii-harbor-tugboat', 'Kingston II', 'Kingston II', 'Harbor tugboat', '1937', 'Stationed at the main entrance.'),
    ('breck-marshall-working-catboat', 'Waterfront Cruises', 'Breck Marshall', 'Working catboat', '1987',
     'Sails with passengers in season from the Waterfront Cruises dock.'),
    ('new-haven-sharpie-oyster-tonger', 'Main Shop', 'New Haven Sharpie', 'Oyster tonger', 'c. 1890',
     'Under restoration in the Preservation Shipyard.'),
    ('annie-sandbagger', None, 'Annie', 'Sandbagger', '1880', None),
    ('florence-dragger', None, 'Florence', 'Dragger', '1926', None),
    ('roann-eastern-rig-dragger', None, 'Roann', 'Eastern-rig dragger', '1947', None),
    ('regina-m-carry-away-sloop', None, 'Regina M.', 'Carry-away sloop', 'c. 1900', None),
    ('nellie-oyster-sloop', None, 'Nellie', 'Oyster sloop', '1891', None),
    ('star-noank-fish-and-lobster-boat', None, 'Star', 'Noank fish and lobster boat', '1950', None),
    ('amistad-replica-schooner', None, 'Amistad', 'Replica schooner', '2000', None),
]

# Seaport Village pages: slug -> place id (None = on the grounds but not numbered on the 2026 map)
VILLAGE = {
    'thomas-greenman-house': 'Thomas Greenman House', 'buckingham-hall-house': 'Buckingham-Hall House',
    'chubbs-wharf': None, 'mystic-bank': 'Mystic Bank', 'shipping-office': 'Mystic Bank', 'cooperage': 'Cooperage',
    'burrows-house': 'Burrows House', 'middle-wharf': 'Middle Wharf', 'printing-office': 'Mystic Print Shop',
    'hoop-maker': 'Hoop Shop', 'nautical-instruments-shop': 'Nautical Instruments Shop', 'shipsmith': 'Shipsmith Shop',
    'clam-shack': 'Clam Shack', 'sail-loft': 'Sail Loft', 'rigging-loft': 'Sail Loft', 'ship-chandlery': 'Sail Loft',
    'ropewalk': 'Ropewalk', 'salmon-shack': 'Salmon Shack', 'lobster-shack': 'Lobster Shack',
    'life-saving-station': 'Life-Saving Station', 'halfway-house': 'Life-Saving Station',
    'ship-carver': 'Shipcarver’s Shop', 'drugstore-and-doctors-office': 'Drug Store',
    'reading-room': 'Seamen’s Friend Society', 'general-store': 'Stone’s Store', 'boardman-school': 'School House',
    'fishtown-chapel': 'Chapel', 'oyster-house': 'Thomas Oyster House', 'meeting-house': 'Meeting House',
    'fire-engine': None, 'william-haynes-house': None, 'langworthy-house': None, 'lewis-house': None,
    'dickerman-house': None, 'brustolon-house': None, 'constantine-house': None, 'clark-greenman-house': None,
    'george-greenman-house': None, 'shipyard-privy': None, 'greenmanville': None,
}

# The village pages' own titles are empty or in capitals: names as the museum's Seaport Village page lists them
TITLES = {
    'thomas-greenman-house': 'Thomas Greenman House', 'buckingham-hall-house': 'Buckingham-Hall House',
    'chubbs-wharf': 'Chubb’s Wharf', 'mystic-bank': 'Mystic Bank', 'shipping-office': 'Samuel Thompson’s Nephew & Co. Shipping Office',
    'cooperage': 'Cooperage', 'burrows-house': 'Burrows House', 'middle-wharf': 'Middle Wharf',
    'printing-office': 'Mystic Press Printing Office', 'hoop-maker': 'George W. Smith, Mast Hoop Manufacturer',
    'nautical-instruments-shop': 'Nautical Instruments Shop', 'shipsmith': 'James Driggs Shipsmith Shop',
    'clam-shack': 'Dave’s Clam Shack', 'sail-loft': 'Charles Mallory Sail Loft', 'rigging-loft': 'Rigging Loft',
    'ship-chandlery': 'Ship Chandlery', 'ropewalk': 'Plymouth Cordage Company Ropewalk',
    'salmon-shack': 'Robie Ames Salmon Shack', 'lobster-shack': 'Lobster Shack',
    'life-saving-station': 'New Shoreham Life-Saving Station', 'halfway-house': 'U.S. Life-Saving Service Halfway House',
    'ship-carver': 'Ship Carver', 'drugstore-and-doctors-office': 'Drugstore and Doctor’s Office',
    'reading-room': 'Seamen’s Friend Society Reading Room', 'general-store': 'Geo. H. Stone General Store',
    'boardman-school': 'Boardman School', 'fishtown-chapel': 'Fishtown Chapel', 'oyster-house': 'Thomas Oyster House',
    'meeting-house': 'Meeting House', 'fire-engine': 'Block Island Fire Engine #1', 'william-haynes-house': 'William Haynes House',
    'langworthy-house': 'Langworthy House', 'lewis-house': 'Lewis House', 'dickerman-house': 'Dickerman House',
    'brustolon-house': 'Brustolon House', 'constantine-house': 'Constantine House', 'clark-greenman-house': 'Clark Greenman House',
    'george-greenman-house': 'George Greenman House', 'shipyard-privy': 'Newbert & Wallace Shipyard Privy',
    'greenmanville': 'Greenmanville',
}

# Exhibitions now open: slug -> place id (None = panels all over the grounds)
EXHIBITS = {
    'monstrous': 'Thompson Exhibition Building', 'brickwrecks': 'Stillman Building',
    'benjamin-f-packard-cabin': 'Stillman Building', 'artoftheboat': 'Meeting House', 'fish-forrest': 'Mallory Buildings',
    'figureheads-and-shipcarvings': 'Wendell Building', 'temperance-and-trade': 'Burrows House',
    'whaleboat-exhibit': 'Whaleboat Exhibit', 'sentinels-of-the-sea-lighthouses': 'Brant Point Lighthouse',
    'thames-keel-shipbuilding-exhibit': 'Thames Keel Exhibit', 'small-boats': 'Small Boat Exhibit',
    'mystic-river-scale-model': 'Mystic River Scale Model', 'the-sea-connects-us': None,
}
EXTRA_PAGES = {'henry-b-du-pont-preservation-shipyard': 'Main Shop'}


def exhibit_dates(entry):
    t = text(entry['content']['rendered'])[:400]
    m = re.search(r'(?:through|until)\s+([A-Z][a-z]+ \d{1,2}, \d{4})', t, re.I)
    if m: return f'On view through {m[1]}'
    if re.search(r'Temporarily Closed', t, re.I): return 'Temporarily closed'
    if re.search(r'Open Year-round', t, re.I): return 'Open year-round'
    return 'Now on view'


def sabino_picture():
    """Sabino's page has no picture; the museum's 2026 map has her on its cover. Cut that photo out of the PDF."""
    dest = OUT / 'images' / 'mystic-vessel-sabino.jpg'
    if not dest.exists():
        subprocess.run(['pdftoppm', '-r', '150', '-png', '-singlefile', str(CACHE / 'map.pdf'), str(CACHE / 'map-page')],
                       check=True)
        im = Image.open(CACHE / 'map-page.png').convert('RGB').crop((330, 150, 1200, 520))
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, 'JPEG', quality=82, optimize=True, progressive=True)
    return 'data/mystic/images/mystic-vessel-sabino.jpg'


def build_works(floors):
    rooms = {r['id']: r for r in floors['floors'][0]['rooms']}
    pages = all_pages()
    exhibits = {e['slug']: e for e in json.loads(get(f'{SITE}/wp-json/wp/v2/exhibits?per_page=100&_embed=wp:featuredmedia',
                                                       'exhibits.json'))}
    placed, unplaced = [], []

    def add(key, title, artist, date, kind, place, entry, url, note=None, extra=None):
        img = first_image(entry) if entry else None
        a = {'id': key, 'title': title, 'artist': artist, 'date': date, 'medium': kind,
             'description': paragraphs(entry) if entry else None,
             'descriptionKind': 'From the museum’s page' if entry else None,
             'url': url, 'image': picture(key, img), 'imageCredit': 'Mystic Seaport Museum' if img else None,
             'placeNote': note}
        if extra: a.update(extra)
        y = re.search(r'(\d{4})', date or '')
        if y: a['year'] = int(y[1])
        if place:
            a.update(gallery=place, galleryName=rooms[place]['name'], floor='G')
            placed.append({k: v for k, v in a.items() if v not in (None, '')})
        else:
            unplaced.append({k: v for k, v in a.items() if v not in (None, '')})

    for slug, place, title, kind, built, note in VESSELS:
        e = pages.get(slug)
        url = e['link'] if e else f'{SITE}/explore/vessels/'
        add(f'mystic-vessel-{slug.split("-")[0]}', title, f'{kind}, built {built}', built, kind, place, e, url,
            note or ('Part of the watercraft collection; where it is shown changes, ask at the Dock Office.'))
    for a in placed:
        if a['id'] == 'mystic-vessel-sabino' and 'image' not in a:
            a['image'] = sabino_picture()
            a['imageCredit'] = 'Mystic Seaport Museum (cover of its 2026 Map & Guide)'
    for slug, place in VILLAGE.items():
        e = pages.get(slug)
        if not e: continue
        title = TITLES[slug]
        add(f'mystic-village-{slug}', title, 'Seaport Village', None, 'Historic building and trade exhibit', place, e,
            e['link'], None if place else 'On the Museum grounds; not numbered on the 2026 map.')
    for slug, place in EXHIBITS.items():
        e = exhibits.get(slug)
        if not e: continue
        title = re.sub(r'\s+', ' ', html.unescape(e['title']['rendered'])).strip()
        when = exhibit_dates(e)
        add(f'mystic-exhibit-{slug}', title, 'Exhibition', None, 'Exhibition', place, e, e['link'],
            when + ('' if place else '; panels are set up all over the Museum grounds.'),
            {'exhibition': f'{title} ({when.lower()})'})
    for slug, place in EXTRA_PAGES.items():
        e = pages.get(slug)
        if e: add(f'mystic-page-{slug}', 'Henry B. du Pont Preservation Shipyard', 'Preservation Shipyard', None,
                  'Working shipyard', place, e, e['link'], 'Watch shipwrights at work on the Museum’s vessels.')
    order = {r['id']: i for i, r in enumerate(floors['floors'][0]['rooms'])}
    placed.sort(key=lambda a: (order[a['gallery']], a['id']))
    return {'source': 'Mystic Seaport Museum website (vessels, Seaport Village and exhibition pages)',
            'checked': time.strftime('%Y-%m-%d'), 'count': len(placed), 'complete': False, 'artworks': placed}, unplaced


def build_guide(works, unplaced):
    rows = []
    for a, on in [(a, True) for a in works['artworks']] + [(a, False) for a in unplaced]:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a.get('title') or a['id'], 'artist': a.get('artist'), 'date': a.get('date'),
                     'year': a.get('year'), 'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'),
                     'onView': on, 'gallery': a.get('gallery'), 'floor': a.get('floor')}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': 'Mystic Seaport Museum', 'checked': time.strftime('%Y-%m-%d'),
            'source': 'Mystic Seaport Museum 2026 map and website', 'onViewKnown': True,
            'note': 'Mystic Seaport has more than two million objects and about 650 boats, but its online catalogue does '
                    'not say what is on view and has few pictures. This guide lists what you walk through: the historic '
                    'vessels, the Seaport Village shops and houses, and the exhibitions open now. Vessels and houses not '
                    'on the 2026 map are listed but not placed.',
            'works': rows}


def main():
    OUT.mkdir(exist_ok=True)
    floors, _ = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works, unplaced = build_works(floors)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works, unplaced)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': sum(w['onView'] for w in guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    print(f'{works["count"]} placed, {len(unplaced)} not placed; '
          f'{sum("image" in a for a in works["artworks"])} placed with pictures, '
          f'{sum("description" in a for a in works["artworks"])} with text')
    print('no picture:', [a['id'] for a in works['artworks'] + unplaced if 'image' not in a])


if __name__ == '__main__':
    sys.exit(main())
