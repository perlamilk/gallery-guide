#!/usr/bin/env python3
"""Build the Plimoth Patuxet Museums (Plymouth, MA) map guide (run: python3 tools/build_plimoth.py).

    data/plimoth/floors.json      a flat 2D map of the museum's three places (see below)
    data/plimoth/artworks.json    what you see at each place, in the building, deck or room where it is
    data/plimoth/images/          their pictures, made smaller for phones
    data/guides/Q1839461.json     the same list for the museum page, plus collection objects not on view

Plimoth Patuxet is one museum in three places: the main campus at 137 Warren Avenue (the Visitor Center, the
Historic Patuxet Homesite, the 17th-Century English Village and the Craft Center), Mayflower II at State Pier on
the downtown waterfront, and the Plimoth Grist Mill on Town Brook, about 3 miles north. The museum publishes no
map of its grounds, so:

  * P (Main Campus) is traced from OpenStreetMap (api.openstreetmap.org, ODbL), which has the English Village
    houses by family name, the Craft Center, the Accomack Building, the Nye Barn and the paths, and from Esri World
    Imagery for what OpenStreetMap lacks (the Visitor Center outline, the Homesite clearing, the parking lots).
    Coordinates are pixels of that imagery at zoom 18 (about 44 cm each), times 1.27 so one map unit is about
    35 cm, as the app's walking times assume. Amenities are placed from the museum's own words: restrooms on
    either side of the Visitor Center and in the Craft Center, the Plentiful Café in the Visitor Center, a café
    and shop in the Craft Center.
  * M and T (Mayflower II) and G and L (the Grist Mill) are diagrams, not to scale: the app keeps the same view
    when you change floors, so the ship and the mill are drawn large in the middle of the campus view. Their
    walking distances are scaled back down (floor.walkScale). The decks follow the museum's description (main
    deck, half deck, the 'tween deck where the passengers lived); the mill rooms follow its page (the grinding
    floor, the packing area and shop, the gears and the hands-on exhibit downstairs).

The works: the museum cares for over 400,000 objects, but its online catalogue (plimoth.catalogaccess.com) refuses
robots and says nothing about what is on view. What a visitor sees is the living history: the houses, the wetu,
the ship, the mill, and the current exhibitions. So the guide lists those, with the museum's own photographs and
words from plimoth.org (read once, slowly, and cached), plus collection objects the museum publishes in its
"You Are the Historian" pages, listed as not on view.
"""
import html
import io
import json
import math
import re
import subprocess
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'plimoth'
CACHE = ROOT / '.cache' / 'plimoth'
MUSEUM = 'Q1839461'
SITE = 'https://plimoth.org'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
CHECKED = time.strftime('%Y-%m-%d')
_last = [0.0]


def get(url, name, binary=False, delay=4):
    """Read a page once, politely, and keep it."""
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


def centroid(pg):
    return [sum(p[0] for p in pg) / len(pg), sum(p[1] for p in pg) / len(pg)]


def inside(pt, pg):
    x, y = pt
    hit = False
    for (x1, y1), (x2, y2) in zip(pg, pg[1:] + pg[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def seg_closest(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return [ax + t * dx, ay + t * dy]


def edge_point(pg, toward):
    best = None
    for a, b in zip(pg, pg[1:] + pg[:1]):
        q = seg_closest(toward, a, b)
        d = (q[0] - toward[0]) ** 2 + (q[1] - toward[1]) ** 2
        if best is None or d < best[0]: best = (d, q)
    return [round(best[1][0], 1), round(best[1][1], 1)]


def dist_to_poly(p, pg):
    if inside(p, pg): return 0
    q = edge_point(pg, p)
    return math.hypot(q[0] - p[0], q[1] - p[1])


# ---- the main campus: OpenStreetMap + aerial imagery ---------------------------------------------------------
OSM_BBOX = (-70.636, 41.930, -70.615, 41.946)
LON0, LAT1, Z = -70.6290, 41.9425, 18          # top-left of the traced area, Esri World Imagery zoom 18
K = 1.27                                        # imagery pixels (0.444 m) -> map units (0.35 m)
SHIFT = 100                                     # drop the empty strip on the west


def tile_px(lon, lat):
    x = (lon + 180) / 360 * 2 ** Z * 256
    r = math.radians(lat)
    y = (1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * 2 ** Z * 256
    return x, y


OX, OY = tile_px(LON0, LAT1)


def A(x, y):
    """Imagery pixel -> map unit."""
    return [round((x - SHIFT) * K, 1), round(y * K, 1)]


def AP(pts):
    return [A(x, y) for x, y in pts]


def osm():
    raw = get('https://api.openstreetmap.org/api/0.6/map?bbox=' + ','.join(map(str, OSM_BBOX)), 'campus.osm', delay=1)
    root = ET.fromstring(raw)
    nodes = {n.get('id'): (float(n.get('lon')), float(n.get('lat'))) for n in root.findall('node')}
    ways = {}
    for w in root.findall('way'):
        tags = {t.get('k'): t.get('v') for t in w.findall('tag')}
        pts = []
        for n in w.findall('nd'):
            lon, lat = nodes[n.get('ref')]
            x, y = tile_px(lon, lat)
            pts.append(A(x - OX, y - OY))
        if pts and pts[0] == pts[-1]: pts = pts[:-1]
        ways[w.get('id')] = (tags, pts)
    return ways


# OpenStreetMap buildings used on the map: way id -> (room id, kind, label, name)
G, S = 'gallery', 'space'
OSM_BUILDINGS = {
    '215731602': ('Fort-Meetinghouse', G, 'Fort-Meetinghouse', 'The Fort-Meetinghouse at the top of the village street'),
    '215731562': ('Bradford House', G, 'Bradford', 'Bradford house'),
    '215731584': ('Standish House', G, 'Standish', 'Standish house'),
    '215731540': ('Brewster House', G, 'Brewster', 'Brewster house'),
    '215731564': ('Winslow House', G, 'Winslow', 'Winslow house'),
    '215731578': ('Alden House', G, 'Alden', 'Alden house'),
    '215731548': ('Allerton House', G, 'Allerton', 'Allerton house'),
    '215731554': ('Cooke House', G, 'Cooke', 'Cooke house'),
    '215731551': ('Hopkins House', G, 'Hopkins', 'Hopkins house'),
    '215731532': ('Billington House', G, 'Billington', 'Billington house'),
    '215731549': ('Fuller House', G, 'Fuller', 'Fuller house'),
    '215731537': ('Hicks House', G, 'Hicks', 'Hicks house'),
    '215731514': ('North Storehouse', S, None, 'Storehouse'),
    '215731520': ('Storehouse', S, None, 'Storehouse'),
    '215731518': ('Beasthouse', S, None, 'Beasthouse (the village’s animals)'),
    '215731830': ('Craft Center', G, 'Craft Center',
                  'Craft Center: potters at work, the Apothecary Exhibit, Threads of Identity · café, shop and restrooms'),
    '215731791': ('Accomack Building', S, None, 'Accomack Building'),
    '215731610': ('Nye Barn', G, 'Nye Barn', 'Nye Barn: the museum’s rare-breed animals'),
    '215731558': ('Peabody Pavilion', S, None, 'Peabody Pavilion (events)'),
}
VILLAGE_PALISADE = [[800, 52], [902, 40], [938, 118], [936, 300], [880, 472], [796, 474], [788, 300]]

# Walks and open ground (corridors), in imagery pixels: (id, name, outline, label point)
CAMPUS_WALKS = [
    ('main-lot', 'Main parking lot (free)', [[165, 1000], [290, 872], [430, 1035], [425, 1150], [330, 1232], [160, 1085]],
     (300, 1060)),
    ('arrival', 'Walk from the main parking lot to the Visitor Center', [[425, 1120], [585, 1120], [585, 1176], [425, 1176]],
     (505, 1150)),
    ('vc-front', 'Visitor Center entrance and drop-off loop', [[585, 1134], [800, 1134], [800, 1242], [585, 1242]],
     (700, 1195)),
    ('lower-lot', 'Lower parking lot: accessible parking and buses', [[650, 1244], [800, 1244], [800, 1400], [665, 1400]],
     (735, 1330)),
    ('vc-lawn', 'Lawn by the Peabody Pavilion', [[762, 1000], [925, 1000], [925, 1134], [762, 1134]], (800, 1020)),
    ('vc-north', 'Path behind the Visitor Center', [[590, 966], [762, 966], [762, 1022], [590, 1022]], (680, 995)),
    ('homesite-trail', 'Trail from the Visitor Center down to the Homesite',
     [[590, 966], [650, 880], [690, 800], [735, 800], [700, 900], [645, 966]], (660, 905)),
    ('craft-road', 'Path between the Craft Center and the Visitor Center',
     [[505, 662], [578, 662], [584, 966], [508, 966]], (545, 820)),
    ('cross-path', 'Path from the Craft Center path to the Homesite', [[578, 770], [700, 790], [700, 815], [578, 800]],
     (630, 795)),
    ('village-path', 'Path from the Craft Center up to the English Village',
     [[575, 592], [780, 476], [806, 500], [602, 626]], (690, 548)),
    ('village-west-path', 'Upper path into the English Village', [[728, 238], [766, 240], [742, 420], [694, 540], [656, 540],
                                                                      [712, 410]], (735, 380)),
    ('village-street', 'The village street', [[856, 60], [888, 62], [858, 466], [826, 464]], (857, 340)),
    ('village-cross', 'Village cross street', [[745, 228], [925, 240], [922, 266], [745, 254]], (900, 252)),
]
CAMPUS_WALK_DOORS = [
    ('main-lot', 'arrival', (428, 1148)), ('arrival', 'vc-front', (585, 1155)), ('vc-front', 'lower-lot', (725, 1243)),
    ('vc-front', 'vc-lawn', (780, 1134)), ('vc-lawn', 'vc-north', (762, 990)), ('vc-north', 'homesite-trail', (620, 966)),
    ('vc-north', 'craft-road', (587, 990)), ('arrival', 'craft-road', (560, 1120)),
    ('craft-road', 'cross-path', (580, 785)), ('craft-road', 'village-path', (575, 640)),
    ('village-path', 'village-west-path', (675, 540)), ('village-path', 'English Village', (795, 488)),
    ('village-west-path', 'village-cross', (748, 242)), ('village-cross', 'village-street', (872, 248)),
    ('village-street', 'English Village', (842, 400)),
]
HOMESITE = [[690, 690], [790, 650], [900, 664], [936, 730], [930, 880], [880, 930], [790, 900], [722, 836]]
VISITOR_CENTER = [[580, 1022], [762, 1022], [762, 1132], [580, 1132]]
CRAFT_GARDEN = [[612, 608], [642, 608], [642, 650], [612, 650]]
CAMPUS_AMENITIES = [
    ('entrance', 648, 1138), ('info', 662, 1112),
    ('restroom', 594, 1078), ('restroom', 748, 1078), ('restroom', 566, 628),
    ('dining', 705, 1048), ('dining', 594, 612),
    ('shop', 625, 1048), ('shop', 556, 640),
]
CAMPUS_LABELS = [
    ('Eel River', 'area', 960, 800), ('English Village', 'area', 760, 120), ('Historic Patuxet Homesite', 'area', 820, 960),
    ('Main parking', 'area', 290, 960), ('Warren Avenue (Route 3A) · Cape Cod Bay', 'note', 640, 30),
    ('Paths are mostly unpaved, some steep: free golf-cart rides, ask any staff member', 'note', 380, 760),
    ('Mayflower II and the Grist Mill are downtown, about 3 miles north: floors M, T, G and L', 'note', 330, 1330),
]


def campus_floor():
    ways = osm()
    rooms, doors = [], []
    for wid, name, pg, at in CAMPUS_WALKS:
        rooms.append({'id': wid, 'kind': 'corridor', 'name': name, 'poly': AP(pg), 'labelAt': A(*at), 'z': 0})
    rooms.append({'id': 'English Village', 'kind': S, 'name': 'The 17th-Century English Village (the year is 1627)',
                  'poly': AP(VILLAGE_PALISADE), 'z': 1, 'labelAt': A(905, 150)})
    rooms.append({'id': 'Historic Patuxet Homesite', 'kind': G, 'label': 'Patuxet Homesite',
                  'name': 'Historic Patuxet Homesite on the Eel River: the nuhshwetu, the mishoon, the cooking arbor, the garden',
                  'poly': AP(HOMESITE), 'z': 1})
    rooms.append({'id': 'Visitor Center', 'kind': G, 'label': 'Visitor Center',
                  'name': 'Henry Hornblower II Visitor Center: tickets, orientation film, exhibitions, Plentiful Café, '
                          'shops and restrooms', 'poly': AP(VISITOR_CENTER), 'z': 2})
    rooms.append({'id': 'Humoral Gardens', 'kind': S, 'name': 'Humoral Gardens (17th-century medicinal plants)',
                  'poly': AP(CRAFT_GARDEN), 'z': 2})
    for wid, (rid, kind, label, name) in OSM_BUILDINGS.items():
        tags, pts = ways[wid]
        assert 'building' in tags, wid
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': pts, 'z': 2}
        if label: r['label'] = label
        rooms.append(r)
    # the other village buildings OpenStreetMap has no name for (outbuildings, houses of other families)
    pal = AP(VILLAGE_PALISADE)
    named = set(OSM_BUILDINGS)
    n = 0
    for wid, (tags, pts) in ways.items():
        if 'building' in tags and wid not in named and pts and inside(centroid(pts), pal):
            n += 1
            rooms.append({'id': f'Village building {n}', 'kind': S, 'name': 'Village house or outbuilding', 'poly': pts,
                          'z': 2})
    ids = {r['id'] for r in rooms}
    for a, b, at in CAMPUS_WALK_DOORS:
        assert a in ids and b in ids, (a, b)
        doors.append({'a': a, 'b': b, 'at': A(*at), 'width': 16, 'axis': 'o'})
    walks = [r for r in rooms if r['kind'] == 'corridor']
    byid = {r['id']: r for r in rooms}
    special = {'Historic Patuxet Homesite': ('homesite-trail', (712, 806)), 'Visitor Center': ('vc-front', (648, 1132)),
               'Humoral Gardens': ('village-path', (612, 615))}
    village = [w for w in walks if w['id'] in ('village-street', 'village-cross')]
    for r in rooms:
        if r['kind'] == 'corridor' or r['id'] == 'English Village': continue
        if r['id'] in special:
            wid, at = special[r['id']]
            doors.append({'a': wid, 'b': r['id'], 'at': A(*at), 'width': 10, 'axis': 'o'})
            continue
        c = centroid(r['poly'])
        pool = village if inside(c, pal) else walks
        w = min(pool, key=lambda w: dist_to_poly(c, w['poly']))
        doors.append({'a': w['id'], 'b': r['id'], 'at': edge_point(r['poly'], w.get('labelAt') or centroid(w['poly'])),
                      'width': 6, 'axis': 'o'})
    # a second way into the Visitor Center, from the path behind it
    doors.append({'a': 'vc-north', 'b': 'Visitor Center', 'at': A(670, 1022), 'width': 10, 'axis': 'o'})
    return {'id': 'P', 'label': 'Main Campus', 'order': 0,
            'area': 'Visitor Center · Historic Patuxet Homesite · 17th-Century English Village · Craft Center',
            'transform': [1, 0, 0], 'rooms': rooms,
            'amenities': [{'type': t, 'at': A(x, y)} for t, x, y in CAMPUS_AMENITIES],
            'labels': [{'text': t, 'kind': k, 'at': A(x, y)} for t, k, x, y in CAMPUS_LABELS], 'doors': doors}


# ---- Mayflower II and the Grist Mill: diagrams drawn large over the middle of the campus view -----------------
def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


HULL_BOW = [[650, 470], [700, 520], [740, 600], [754, 690], [546, 690], [560, 600], [600, 520]]
STERN = [[544, 1250], [756, 1250], [756, 1290], [740, 1370], [560, 1370], [544, 1290]]
SHIP_NOTE = 'Diagram, not to scale: the ship is drawn large'


def mayflower_floors():
    pier = {'id': 'State Pier', 'kind': 'corridor', 'name': 'State Pier on the Plymouth waterfront',
            'poly': rect(330, 380, 520, 1450), 'labelAt': [425, 560], 'z': 0}
    gang = {'id': 'Gangway', 'kind': 'corridor', 'name': 'Gangway onto the main deck (ramps can be steep with the tide)',
            'poly': rect(520, 880, 546, 930), 'labelAt': [533, 905], 'z': 0}
    rooms = [pier, gang,
             {'id': 'Dockside exhibit', 'kind': G, 'label': 'Dockside exhibit', 'z': 1, 'poly': rect(350, 700, 505, 1050),
              'name': 'Dockside exhibit: photographs of the ship’s interior, talk with the crew (open to everyone)'},
             {'id': 'Plymouth Rock', 'kind': S, 'z': 1, 'poly': rect(360, 1490, 490, 1580),
              'name': 'Plymouth Rock in Pilgrim Memorial State Park, a short walk south on Water Street (free)'},
             {'id': 'Forecastle', 'kind': G, 'label': 'Forecastle', 'z': 1, 'poly': HULL_BOW,
              'name': 'Forecastle at the bow: the crew’s quarters'},
             {'id': 'Main deck', 'kind': G, 'label': 'Main deck', 'z': 1, 'poly': rect(546, 690, 755, 1080),
              'name': 'Main deck (the waist): the masts, the capstan and the hatch down to the ’tween deck'},
             {'id': 'Half deck', 'kind': G, 'label': 'Half deck', 'z': 1, 'poly': rect(544, 1080, 756, 1250),
              'name': 'Half deck at the stern: the steerage, where the helmsman steered with the whipstaff'},
             {'id': 'Great cabin', 'kind': G, 'label': 'Great cabin', 'z': 1, 'poly': STERN,
              'name': 'Great cabin of the ship’s master, at the very stern'}]
    doors = [{'a': 'State Pier', 'b': 'Gangway', 'at': [520, 905], 'width': 16, 'axis': 'o'},
             {'a': 'Gangway', 'b': 'Main deck', 'at': [546, 905], 'width': 16, 'axis': 'o'},
             {'a': 'State Pier', 'b': 'Dockside exhibit', 'at': [505, 760], 'width': 10, 'axis': 'o'},
             {'a': 'State Pier', 'b': 'Plymouth Rock', 'at': [425, 1470], 'width': 10, 'axis': 'o'},
             {'a': 'Main deck', 'b': 'Forecastle', 'at': [650, 690], 'width': 12, 'axis': 'o'},
             {'a': 'Main deck', 'b': 'Half deck', 'at': [650, 1080], 'width': 12, 'axis': 'o'},
             {'a': 'Half deck', 'b': 'Great cabin', 'at': [650, 1250], 'width': 10, 'axis': 'o'}]
    m = {'id': 'M', 'label': 'Mayflower II · Main Deck', 'order': 2,
         'area': 'State Pier, 75 Water Street, downtown Plymouth · main deck, half deck and great cabin · dockside exhibit',
         'transform': [1, 0, 0], 'walkScale': 0.15, 'rooms': rooms, 'doors': doors,
         'amenities': [{'type': 'stairs', 'at': [650, 960]}, {'type': 'entrance', 'at': [425, 1440]},
                       {'type': 'info', 'at': [470, 1400]}, {'type': 'shop', 'at': [380, 1300]},
                       {'type': 'restroom', 'at': [345, 1410]}],
         'labels': [{'text': 'Plymouth Harbor', 'kind': 'area', 'at': [900, 900]},
                    {'text': 'Bow', 'kind': 'note', 'at': [650, 445]}, {'text': 'Stern', 'kind': 'note', 'at': [650, 1400]},
                    {'text': 'Water Street', 'kind': 'note', 'at': [230, 1450]},
                    {'text': SHIP_NOTE + '. Not wheelchair accessible; steep stairs inside', 'kind': 'note',
                     'at': [880, 1250]}]}
    tween = [{'id': 'Forepeak', 'kind': S, 'z': 1, 'poly': [[650, 470], [700, 520], [740, 600], [560, 600], [600, 520]],
              'name': 'Forepeak in the bow (stores)'},
             {'id': 'Tween deck', 'kind': G, 'label': '’Tween deck', 'z': 1,
              'poly': [[560, 600], [740, 600], [756, 700], [756, 1180], [544, 1180], [544, 700]],
              'name': '’Tween deck: where the 102 passengers lived for the voyage'},
             {'id': 'Gunroom', 'kind': G, 'label': 'Gunroom', 'z': 1,
              'poly': [[544, 1180], [756, 1180], [756, 1290], [740, 1370], [560, 1370], [544, 1290]],
              'name': 'Gunroom at the stern'}]
    tdoors = [{'a': 'Tween deck', 'b': 'Forepeak', 'at': [650, 600], 'width': 10, 'axis': 'o'},
              {'a': 'Tween deck', 'b': 'Gunroom', 'at': [650, 1180], 'width': 10, 'axis': 'o'}]
    t = {'id': 'T', 'label': 'Mayflower II · ’Tween Deck', 'order': 1,
         'area': 'The deck below: the passengers’ quarters and the gunroom',
         'transform': [1, 0, 0], 'walkScale': 0.15, 'rooms': tween, 'doors': tdoors,
         'amenities': [{'type': 'stairs', 'at': [650, 960]}],
         'labels': [{'text': 'Bow', 'kind': 'note', 'at': [650, 445]}, {'text': 'Stern', 'kind': 'note', 'at': [650, 1400]},
                    {'text': SHIP_NOTE, 'kind': 'note', 'at': [880, 1250]}]}
    return m, t


def mill_floors():
    yard = {'id': 'Mill yard', 'kind': 'corridor', 'name': 'Spring Lane and the mill entrance',
            'poly': [[300, 590], [1000, 590], [1000, 700], [420, 700], [420, 1200], [300, 1200]], 'labelAt': [700, 640],
            'z': 0}
    brook = {'id': 'Town Brook walk', 'kind': 'corridor',
             'name': 'Town Brook walk through Brewster Gardens to the waterfront, Plymouth Rock and Mayflower II',
             'poly': [[300, 1200], [1150, 1150], [1150, 1300], [300, 1340]], 'labelAt': [900, 1240], 'z': 0}
    g = [yard, brook,
         {'id': 'Grinding floor', 'kind': G, 'label': 'Grinding floor', 'z': 1, 'poly': rect(420, 700, 700, 1080),
          'name': 'Grinding floor: the 54-inch millstones'},
         {'id': 'Packing area', 'kind': G, 'label': 'Packing area', 'z': 1, 'poly': rect(700, 700, 880, 880),
          'name': 'Packing area: what the stones make, and where the grains come from'},
         {'id': 'Mill Shop', 'kind': S, 'z': 1, 'poly': rect(700, 880, 880, 1080),
          'name': 'Plimoth Grist Mill Shop: stone-ground cornmeal, sampe and other grains'},
         {'id': 'Waterwheel', 'kind': G, 'label': 'Waterwheel', 'z': 1, 'poly': rect(520, 1080, 660, 1190),
          'name': 'The 14-foot waterwheel, turned by water from Town Brook'}]
    gdoors = [{'a': 'Mill yard', 'b': 'Grinding floor', 'at': [560, 700], 'width': 14, 'axis': 'o'},
              {'a': 'Mill yard', 'b': 'Town Brook walk', 'at': [360, 1200], 'width': 16, 'axis': 'o'},
              {'a': 'Grinding floor', 'b': 'Packing area', 'at': [700, 790], 'width': 12, 'axis': 'o'},
              {'a': 'Packing area', 'b': 'Mill Shop', 'at': [790, 880], 'width': 12, 'axis': 'o'},
              {'a': 'Mill yard', 'b': 'Mill Shop', 'at': [880, 700], 'width': 10, 'axis': 'o'},
              {'a': 'Town Brook walk', 'b': 'Waterwheel', 'at': [590, 1190], 'width': 10, 'axis': 'o'}]
    gf = {'id': 'G', 'label': 'Grist Mill · Grinding Floor', 'order': 4,
          'area': '6 Spring Lane, downtown Plymouth · millstones, packing area, shop and the waterwheel on Town Brook',
          'transform': [1, 0, 0], 'walkScale': 0.12, 'rooms': g, 'doors': gdoors,
          'amenities': [{'type': 'entrance', 'at': [560, 690]}, {'type': 'stairs', 'at': [450, 1050]},
                        {'type': 'shop', 'at': [790, 990]}],
          'labels': [{'text': 'Jenney Pond', 'kind': 'area', 'at': [190, 900]},
                     {'text': 'Town Brook', 'kind': 'area', 'at': [700, 1380]},
                     {'text': 'Diagram, not to scale: the mill is drawn large', 'kind': 'note', 'at': [700, 540]}]}
    low = [{'id': 'Gear room', 'kind': G, 'label': 'Gears', 'z': 1, 'poly': rect(420, 700, 650, 1080),
            'name': 'The gears: the great face gear and the wallower that turn the runner stone'},
           {'id': 'Hands-on exhibit', 'kind': G, 'label': 'Hands-on exhibit', 'z': 1, 'poly': rect(650, 700, 880, 1080),
            'name': 'Hands-on exhibit: water power, simple machines and the river herring of Town Brook'}]
    ldoors = [{'a': 'Gear room', 'b': 'Hands-on exhibit', 'at': [650, 890], 'width': 14, 'axis': 'o'}]
    lf = {'id': 'L', 'label': 'Grist Mill · Lower Level', 'order': 3, 'area': 'Downstairs: the gears and the hands-on exhibit',
          'transform': [1, 0, 0], 'walkScale': 0.12, 'rooms': low, 'doors': ldoors,
          'amenities': [{'type': 'stairs', 'at': [450, 1050]}],
          'labels': [{'text': 'Diagram, not to scale: the mill is drawn large', 'kind': 'note', 'at': [700, 540]}]}
    return lf, gf


def build_floors():
    p = campus_floor()
    m, t = mayflower_floors()
    lf, gf = mill_floors()
    return {'about': 'Built by tools/build_plimoth.py. The main campus is traced from OpenStreetMap (© OpenStreetMap '
                     'contributors, ODbL) and aerial imagery, because the museum publishes no map of its grounds; the '
                     'Visitor Center, Homesite and paths are drawn by eye and amenities placed from the museum’s own '
                     'descriptions. Mayflower II and the Grist Mill are diagrams drawn large, not to scale.',
            'source': 'OpenStreetMap, Esri World Imagery and plimoth.org', 'approximate': True,
            'units': 'about 35 cm per unit on the main campus; Mayflower II and the Grist Mill are diagrams',
            'defaultFloor': 'P', 'galleryWord': 'Place', 'floors': [p, t, m, lf, gf]}


# ---- works ----------------------------------------------------------------------------------------------------
PAGES = {
    'village': 'plan-your-visit/explore-our-sites/17th-century-english-village',
    'homesite': 'plan-your-visit/explore-our-sites/historic-patuxet',
    'craft': 'plan-your-visit/explore-our-sites/craft-center',
    'mayflower': 'plan-your-visit/explore-our-sites/mayflower-ii',
    'mill': 'plan-your-visit/explore-our-sites/plimoth-grist-mill',
    'exhibitions': 'collections-research/exhibitions',
    'teacher': 'for-teachers/teacher-tools/teacher-guide-to-the-museum',
    'animals': 'for-students/homework-help/animals',
    'building': 'for-students/homework-help/building-a-home',
    'cinema': 'explore/cinema',
    'cafe': 'explore/event-venues-and-dining/plentiful-caf%C3%A9',
    'shops': 'explore/museum-shops',
    'one': 'one-museum',
    'practical': 'plan-your-visit/visitor-guide/practical-questions-for-visiting',
    'tickets': 'plan-your-visit/hours-tickets-directions',
    'sails': 'mayflower-sails-2026',
    'parking': 'plan-your-visit/visitor-guide/parking-accessibility',
    'explore': 'explore',
    'sites': 'plan-your-visit/explore-our-sites',
    'directions': 'plan-your-visit/hours-tickets-directions/getting-here',
    'visitor': 'plan-your-visit/visitor-guide',
}


def page(key):
    return get(f'{SITE}/{PAGES[key]}', 'page-' + PAGES[key].replace('/', '_').replace('%', '') + '.html')


def image_url(stem):
    """The museum's own picture whose file name starts with `stem`, as one of its cached pages shows it."""
    for key in PAGES:
        for src in re.findall(r'src="(https://plimoth\.nyc3\.digitaloceanspaces\.com/[^"]+)"', page(key)):
            if src.rsplit('/', 1)[1].startswith(stem + '_') or src.rsplit('/', 1)[1].startswith(stem + '.'):
                return src
    for f in sorted(CACHE.glob('yath-*.html')):
        for src in re.findall(r'src="(https://plimoth\.nyc3\.digitaloceanspaces\.com/[^"]+)"', f.read_text(errors='replace')):
            if src.rsplit('/', 1)[1].startswith(stem + '_'):
                return src
    raise SystemExit(f'no picture named {stem}')


def picture(key, stem):
    if not stem: return None
    url = image_url(stem)
    raw = CACHE / 'img' / (key + (Path(urllib.parse.urlparse(url).path).suffix.lower() or '.jpg'))
    dest = OUT / 'images' / f'{key}.jpg'
    if not raw.exists():
        get(url, 'img/' + raw.name, binary=True)
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(io.BytesIO(raw.read_bytes()))
        im = im.convert('RGBA') if im.mode in ('P', 'LA') else im
        if im.mode == 'RGBA':
            bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=im.split()[3]); im = bg
        im = im.convert('RGB')
        im.thumbnail((1000, 1000))
        im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/plimoth/images/{key}.jpg'


def url(key):
    return f'{SITE}/{PAGES[key]}'


# On view: (id, title, kind/artist line, medium, place, floor, picture file stem, page key, description, note)
ON_VIEW = [
    # Visitor Center
    ('vc-we-gather-together', 'We Gather Together: Thanksgiving, Gratitude, and the Making of an American Holiday',
     'Exhibition', 'Exhibition', 'Visitor Center', 'P', '59D9A9B2-5D40-4F9F-87A5-B0B8B81ECA1C', 'exhibitions',
     'This exhibit focuses on the origins of one of America’s quintessential holidays. Plymouth/Patuxet is the place '
     'where the ancient traditions of gratitude in both the Indigenous and European cultures merged in the autumn of '
     '1621, and a new holiday of gathering and giving thanks began.', 'In the Visitor Center exhibit galleries'),
    ('vc-painting-the-past', 'Painting the Past: The Marcia Sewall Illustrations', 'Exhibition, April 2026 to November 2027',
     'Watercolor illustrations', 'Visitor Center', 'P', 'marcia-sewall-artwork-english-village-pilgrims-exhibition',
     'exhibitions',
     'The artwork of Marcia Sewall, award-winning children’s book author and illustrator, from her three books inspired '
     'by the museum: The Pilgrims of Plimoth (1986), People of the Breaking Day (1990) and Thunder from the Clear Sky '
     '(1995). With hands-on activities and a reading nook for children.', 'Davis Exhibition Gallery, Visitor Center'),
    ('vc-orientation-film', 'Along the Shores of Change', 'Orientation film', 'Film', 'Visitor Center', 'P', None, 'teacher',
     'Your journey begins at the Visitor Center: after the brief orientation film, follow the pathways to the living '
     'history exhibits.', 'Orientation theater, Visitor Center'),
    ('vc-plimoth-cinema', 'Plimoth Cinema', 'Independent film theater', 'Cinema', 'Visitor Center', 'P', 'plimoth-cinema',
     'cinema', 'The museum’s cinema shows independent and documentary films; see the website for what is playing.',
     'In the Visitor Center (separate tickets)'),
    # Historic Patuxet Homesite
    ('homesite-nuhshwetu', 'Nuhshwetu (house)', 'Historic Patuxet Homesite', 'Wampanoag house of saplings and bark',
     'Historic Patuxet Homesite', 'P', 'wetu-historic-patuxet-homesite-plimoth', 'homesite',
     'Step inside a wetu (house)! Take a seat on the soft fur-lined benches, warm yourself by the fire on cold days, '
     'and learn about home and family life of Wampanoag communities in the 17th century.',
     'The nuhshwetu has limited space: you may have to wait to go inside.'),
    ('homesite-mishoon', 'Mishoon (dugout canoe)', 'Historic Patuxet Homesite', 'Wood, shaped with fire',
     'Historic Patuxet Homesite', 'P', 'guest-educator-regalia-mishoon-homesite', 'homesite',
     'Watch staff work on making a mishoon (dug-out canoe), using fire as a tool to shape the vessel. You may be asked '
     'to help by using shells to scrape the inside of the mishoon.', None),
    ('homesite-cooking-arbor', 'Cooking area', 'Historic Patuxet Homesite', 'Outdoor cooking arbor',
     'Historic Patuxet Homesite', 'P', 'historic-patuxet-homesite-cooking-educator', 'homesite',
     'At the cooking area, learn about the Wampanoag seasonal diet. Maybe something will even be cooking, like meat '
     'over the fire, or soup or tea over the hot coals.', None),
    ('homesite-garden', 'Garden of corn, beans and squash', 'Historic Patuxet Homesite', 'Garden',
     'Historic Patuxet Homesite', 'P', 'homesite-corn-planting', 'homesite',
     'You may see staff working in the garden, growing corn, squash, and beans. They will tell you about the seasonal '
     'work of growing food.', None),
    # Craft Center
    ('craft-threads-of-identity', 'Threads of Identity: Wampanoag Clothing Across Generations',
     'Exhibition, August 2026 to November 2027', 'Exhibition', 'Craft Center', 'P', 'threads-of-identity-wampanoag-clothing',
     'exhibitions',
     'Clothing as communication and expression: among the Wampanoag, dress over the centuries speaks to a story of '
     'cultural resilience and adaptation. The exhibit features work curated and created by Indigenous staff and Native '
     'artisans from across the Northeast.', None),
    ('craft-potters', 'Potters at work', 'Craft Center', 'Reproduction 17th-century ceramics', 'Craft Center', 'P',
     'craft-center-plimoth-patuxet', 'craft',
     'Inside the Craft Center you’ll see potters at work: skilled artisans create reproductions of historic items made '
     'in England and other parts of Europe during the 17th century, used in the English Village and sold in the shop.',
     None),
    ('craft-apothecary', 'Apothecary Exhibit', 'Craft Center', 'Exhibit', 'Craft Center', 'P', None, 'craft',
     'Learn about the Doctrine of the Humors, the prevailing medical theory in 17th-century England and Plymouth Colony.',
     None),
    ('craft-humoral-gardens', 'Humoral Gardens', 'Craft Center', 'Period medicinal gardens', 'Humoral Gardens', 'P',
     'gardens-craft-center-green-flowers', 'craft',
     'Period medicinal gardens outside the Craft Center that demonstrate the Doctrine of the Humors.', None),
    # English Village
    ('village-fort-meetinghouse', 'The Fort-Meetinghouse', '17th-Century English Village', 'Re-created building',
     'Fort-Meetinghouse', 'P', 'fortmeeting-house-pilgrim-guest-conversation', 'practical',
     'The colony’s fort, which was also its meetinghouse, at the top of the village street.', None),
    ('village-street-life', 'Life in the village, 1627', '17th-Century English Village', 'Living history',
     'English Village', 'P', 'english-village-pilgrims-crowd-houses', 'village',
     'When you encounter someone wearing historical clothing, they are playing the role of an actual inhabitant of '
     'Plymouth Colony. They will talk about historical events and lifeways as if they are happening in the present. '
     'You may tour the Village and enter about a dozen re-created buildings.', 'Most visitors spend at least 2 hours.'),
    ('village-muster', 'Muster drill', '17th-Century English Village', 'Living history', 'English Village', 'P',
     'pike-drill-plymouth-colony', 'village',
     'You may be called upon to participate in a muster drill! Captain Miles Standish will teach you to follow his '
     'commands, and how the Pilgrims prepared themselves to keep their town safe.', None),
    ('village-gardens', 'Kitchen gardens', '17th-Century English Village', 'Gardens', 'English Village', 'P',
     'english-village-garden-pilgrim', 'village',
     'A goodwife might ask you to help her pound corn, visit the garden with her or help her make sage and salt '
     'toothpaste.', None),
    ('village-games', 'Pilgrim games', '17th-Century English Village', 'Living history', 'English Village', 'P',
     'games-hoop-pilgrims', 'village',
     'The Pilgrims worked very hard, but they had some time for recreation, especially activities that made them '
     'exercise their minds.', None),
    ('village-rare-breeds', 'Rare-breed animals', 'Nye Barn', 'Heritage-breed livestock', 'Nye Barn', 'P',
     'lamb-rare-breeds-plymouth-colony', 'animals',
     'The English colonists relied on their farm animals for milk, meat and eggs. They probably brought goats, pigs and '
     'chickens on Mayflower in 1620; cows and sheep came a few years later. The museum keeps heritage breeds like them.',
     'Only service animals may come in, to protect the rare-breed animals.'),
    # Mayflower II
    ('mayflower-ii', 'Mayflower II', 'Full-scale reproduction of the 1620 ship, built 1955–57', 'Ship', 'Main deck', 'M',
     'mayflower-ii', 'mayflower',
     'Plimoth’s full-scale reproduction of the tall ship that brought the Pilgrims to Plymouth in 1620. Built in '
     'Brixham, England, she arrived in Plymouth on June 13, 1957. About 25 feet wide and 106 feet long, with four '
     'masts and six sails; on the National Register of Historic Places since her restoration in 2020.',
     'Walk the main deck, the ’tween deck and the half deck. Not wheelchair accessible.'),
    ('mayflower-main-deck', 'The main deck', 'Mayflower II', 'Ship’s deck', 'Main deck', 'M',
     'mayflower-guests-main-deck-educator', 'tickets',
     'Talk with the crew and role players about the 1620 voyage and the ship’s working life.', None),
    ('mayflower-tween-deck', 'The ’tween deck', 'Mayflower II', 'Passengers’ quarters', 'Tween deck', 'T',
     'collage-life-aboard-mayflower', 'mayflower',
     '“I was immediately struck by how small the ship seemed, particularly in the ’tween decks, where the passengers '
     'were confined. How could 102 people, including three pregnant mothers, have survived more than ten weeks in a '
     'space this size?” (Nathaniel Philbrick)', 'Down the large modern staircase from the main deck.'),
    ('mayflower-dockside', 'Dockside exhibit', 'Mayflower II', 'Exhibit', 'Dockside exhibit', 'M',
     'mayflower_crew_and_guest', 'mayflower',
     'Those unable to board can enjoy a close-up view of Mayflower from the dock, visit the dockside exhibit area, talk '
     'to modern crewmembers, and look at photographs of the interior of the ship.', None),
    # Grist Mill
    ('mill-waterwheel', 'The waterwheel', 'Plimoth Grist Mill', '14-foot waterwheel', 'Waterwheel', 'G',
     'plimoth-grist-mill-waterwheel', 'mill',
     'Water diverted from Town Brook turns the 14-foot diameter waterwheel that powers the mill. The mill reproduces '
     'the Plymouth colonists’ original 1636 grain mill on Town Brook.', None),
    ('mill-millstones', 'The millstones', 'Plimoth Grist Mill', '54-inch bed and runner stones, 200 years old',
     'Grinding floor', 'G', 'grist-mill-grinding-stone-guets', 'mill',
     'On the grinding floor, the 54-inch bed and runner stones grind corn into finer and finer pieces. Most Saturday '
     'afternoons are grinding days: watch the miller turn out cornmeal and sampe (a northern form of grits).', None),
    ('mill-packing', 'Packing area', 'Plimoth Grist Mill', 'Working mill', 'Packing area', 'G',
     'corn-dried-basket-mill', 'mill',
     'The millers fill real orders for grits, cornmeal and flour. Learn how the millstones grind different products, '
     'what can be cooked with them, and which local farms grow the grain.', None),
    ('mill-gears', 'The gears', 'Plimoth Grist Mill', 'Face gear and wallower', 'Gear room', 'L',
     'plimoth-grist-mill-gears', 'mill',
     'Downstairs, come face to face with the mill’s gears: the massive face gear and the smaller wallower or lantern '
     'gear turn the vertical power of the waterwheel into the horizontal power that turns the runner stone.', None),
    ('mill-hands-on', 'Water power and river herring', 'Plimoth Grist Mill', 'Hands-on exhibit', 'Hands-on exhibit', 'L',
     'plimoth-grist-mill-interior', 'mill',
     'Experiment with water power and simple machines, and learn about the river herring that swim past the mill in '
     'the spring to spawn.', None),
    ('mill-town-brook', 'Town Brook', 'Plimoth Grist Mill', 'Brook and walk', 'Town Brook walk', 'G', 'town-brook', 'mill',
     'A short, beautiful walk along Town Brook through Brewster Gardens leads to Plymouth’s waterfront, Plymouth Rock '
     'and Mayflower II.', 'In spring you might see herring swimming upstream.'),
]

# The re-created houses of the English Village: OpenStreetMap names them by family (room id, household)
HOUSES = [
    ('Bradford House', 'William Bradford', 'governor of Plymouth Colony'),
    ('Standish House', 'Myles Standish', 'captain of the colony’s militia'),
    ('Brewster House', 'William Brewster', 'elder of the Pilgrims’ church'),
    ('Winslow House', 'Edward Winslow', 'who wrote the only eyewitness account of the 1621 harvest feast'),
    ('Alden House', 'John Alden', 'a cooper who came on the Mayflower'),
    ('Allerton House', 'Isaac Allerton', 'a merchant and the governor’s assistant'),
    ('Cooke House', 'Francis Cooke', 'a Mayflower passenger'),
    ('Hopkins House', 'Stephen Hopkins', 'a Mayflower passenger'),
    ('Billington House', 'John Billington', 'a Mayflower passenger'),
    ('Fuller House', 'Samuel Fuller', 'the colony’s surgeon'),
    ('Hicks House', 'Robert Hicks', 'who came on the Fortune in 1621'),
]

# Collection objects the museum publishes in "You Are the Historian" (not on view): page slug
COLLECTION = ['unit-3/manomet-pot', 'unit-1/wampanoag-pottery-sherd', 'unit-1/brass-point', 'unit-1/gorget',
              'unit-1/postglacial-spear-point', 'unit-3/stone-hoe', 'unit-3/wampanoag-stone-pestle',
              'unit-3/english-mortar-and-pestle', 'unit-2/wampum-belt', 'unit-1/bone-fishing-hook',
              'unit-5/the-plymouth-scene-by-lowell-school-in-philadelphia-pa']


def yath(slug):
    raw = get(f'{SITE}/yath/{slug}', 'yath-' + slug.replace('/', '_') + '.html')
    body = raw[raw.find('<main'):]
    clean = re.sub(r'<(script|style|svg)[^>]*>.*?</\1>', '', body, flags=re.S)
    t = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '\n', clean))).split("You can't change history")[0]
    t = t.split('Bibliography', 1)[1].strip()
    fields = {}
    keys = ['Object ID', 'Date', 'Material', 'Author/Maker', 'Source', 'Description', 'Discussion Questions', 'Media']
    pat = '(' + '|'.join(re.escape(k) for k in keys) + ')'
    parts = re.split(pat, t)
    title = parts[0].strip()
    for k, v in zip(parts[1::2], parts[2::2]):
        fields.setdefault(k, v.strip())
    desc = re.sub(r'\s*\d+\s*$', '', fields.get('Description', ''))
    desc = re.sub(r'(?<=[.”"]) ?\d+(?= |$)', '', desc)          # footnote numbers
    sentences = re.split(r'(?<=[.!?”])\s+', desc)
    short = ''
    for s in sentences:
        if len(short) + len(s) > 600: break
        short += (' ' if short else '') + s
    img = re.search(r'src="(https://plimoth\.nyc3\.digitaloceanspaces\.com/[^"]+)"', body)
    return title, fields, short or None, img[1].rsplit('/', 1)[1].split('_')[0] if img else None


def build_works(floors):
    rooms = {(f['id'], r['id']): r for f in floors['floors'] for r in f['rooms']}
    placed, unplaced = [], []

    def add(a, place, floor):
        if place:
            a.update(gallery=place, galleryName=rooms[(floor, place)]['name'], floor=floor)
            placed.append({k: v for k, v in a.items() if v not in (None, '')})
        else:
            unplaced.append({k: v for k, v in a.items() if v not in (None, '')})

    for key, title, artist, medium, place, floor, stem, pg, desc, note in ON_VIEW:
        wid = f'plimoth-{key}'
        img = picture(wid, stem)
        add({'id': wid, 'title': title, 'artist': artist, 'medium': medium, 'description': desc,
             'descriptionKind': 'From the museum’s website', 'url': url(pg), 'image': img,
             'imageCredit': 'Plimoth Patuxet Museums' if img else None, 'placeNote': note}, place, floor)
    for room, person, who in HOUSES:
        wid = 'plimoth-house-' + person.split()[-1].lower()
        add({'id': wid, 'title': f'{person}’s house', 'artist': '17th-Century English Village',
             'medium': 'Re-created timber-framed house', 'date': 'the year 1627',
             'description': f'A re-creation of the house of {person}, {who}. The houses are furnished with reproductions '
                            'of the kinds of objects the Pilgrims owned, with kitchen gardens behind them. When a role '
                            'player is at home, they will talk to you as if it were 1627.',
             'descriptionKind': 'Our note; the house names come from OpenStreetMap',
             'url': url('village'), 'placeNote': 'Not every house has someone at home: feel free to look inside.'},
            room, 'P')
    for slug in COLLECTION:
        title, f, desc, stem = yath(slug)
        wid = 'plimoth-yath-' + slug.split('/')[1][:40]
        img = picture(wid, stem)
        y = re.search(r'\b(1[0-9]{3})\b', f.get('Date', ''))
        maker = f.get('Author/Maker') or ''
        if re.search(r'no longer known', maker):
            maker = 'Maker unknown' + (' (excavated in 1942)' if 'excavated by Jesse Brewer' in maker else '')
        if slug.endswith('postglacial-spear-point'):        # the page repeats the pottery sherd's material and date
            f['Material'], f['Date'] = 'Stone, rhyolite', 'More than 10,000 years ago'
        a = {'id': wid, 'title': title, 'artist': maker, 'date': f.get('Date'),
             'medium': f.get('Material'), 'objectNumber': f.get('Object ID'), 'description': desc,
             'descriptionKind': 'From the museum’s “You Are the Historian” pages', 'url': f'{SITE}/yath/{slug}',
             'image': img, 'imageCredit': 'Plimoth Patuxet Museums' if img else None,
             'placeNote': 'In the museum’s collection; not on view.'}
        if y: a['year'] = int(y[1])
        add(a, None, None)
    order = {(f['id'], r['id']): (i, j) for i, f in enumerate(floors['floors']) for j, r in enumerate(f['rooms'])}
    floor_order = {'P': 0, 'M': 1, 'T': 2, 'G': 3, 'L': 4}
    placed.sort(key=lambda a: (floor_order[a['floor']], order[(a['floor'], a['gallery'])][1]))
    return {'source': 'Plimoth Patuxet Museums website (plimoth.org)', 'checked': CHECKED, 'count': len(placed),
            'complete': False, 'artworks': placed}, unplaced


def build_guide(works, unplaced):
    rows = []
    for a, on in [(a, True) for a in works['artworks']] + [(a, False) for a in unplaced]:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a.get('artist'), 'date': a.get('date'),
                     'year': a.get('year'), 'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'),
                     'onView': on, 'gallery': a.get('gallery'), 'floor': a.get('floor')}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': 'Plimoth Patuxet Museums', 'checked': CHECKED,
            'source': 'Plimoth Patuxet Museums website and OpenStreetMap', 'onViewKnown': True,
            'note': 'Plimoth Patuxet is a living history museum: what you see are the Historic Patuxet Homesite, the '
                    're-created houses of the 17th-Century English Village, Mayflower II and the Grist Mill, with people '
                    'at work in them. This guide lists those places and the exhibitions now open. Its online catalogue '
                    'of over 400,000 objects says nothing about what is on view, so collection objects are listed only '
                    'from the museum’s own teaching pages, as not on view.',
            'works': rows}


def main():
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
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
          f'{sum("image" in a for a in works["artworks"])} placed with pictures')
    print('no picture:', [a['id'] for a in works['artworks'] + unplaced if 'image' not in a])


if __name__ == '__main__':
    sys.exit(main())
