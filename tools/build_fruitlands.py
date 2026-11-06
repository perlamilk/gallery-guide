#!/usr/bin/env python3
"""Build the Fruitlands Museum (Harvard, MA) map guide (run: python3 tools/build_fruitlands.py).

    data/fruitlands/floors.json      the 210-acre grounds seen from above (a flat 2D plan): every museum building,
                                     the drive, parking, trails, restrooms, café, shop and the historic sites
    data/fruitlands/artworks.json    works on view in each building and outdoors, and the historic buildings themselves
    data/fruitlands/images/          their pictures, made smaller for phones
    data/guides/Q5506454.json        the same list for the museum page, plus collection works not on view now

The map is traced from Fruitlands' own trail map (thetrustees.org/wp-content/uploads/2025/08/Fruitlands-Trail-Map.pdf,
the "download a trail map" link on thetrustees.org/place/fruitlands-museum, August 2024 edition). It is a vector PDF
drawn to scale from USGS and MassGIS data, so the shapes come straight out of it: the buildings are the PDF's own
building rectangles, the drive, lots and every trail are the PDF's own lines (turned into walkable paths), and the
names, parking and restroom icons sit where the map prints them. The map is kept as the museum prints it (north points
up and to the right, the arrow on the map), so it matches the paper copy at the parking area.
Map units are PDF points x K. The scale bar says 1000 ft = 152.6 points, so one point is 2.0 m. Buildings on the trail
map are small symbols; each is drawn a little larger around its own centre so it can be tapped.

The museum publishes no floor plans. Each building is one room, except the Four Seasons Gallery (the former Art Museum),
which holds two exhibitions in a larger and a smaller gallery (thetrustees.org and The Harvard Press, 2024): it is split
into those two, which is APPROXIMATE.

The works: the current exhibitions' pages on thetrustees.org (Eye of the Beholder, Across Boundaries Across Barriers,
both in the Four Seasons Gallery), the historic buildings and the outdoor sculptures and objects photographed at
Fruitlands on Wikimedia Commons (public domain or Creative Commons, credited), and works from the Fruitlands collection
shown in past exhibitions (listed on the museum page, not on the map). The museum's collection (about 6,000 objects) is
not online.
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
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'fruitlands'
CACHE = ROOT / '.cache' / 'fruitlands'
MUSEUM = 'Q5506454'
SITE = 'https://thetrustees.org'
MAP_PDF = SITE + '/wp-content/uploads/2025/08/Fruitlands-Trail-Map.pdf'
PLACE = SITE + '/place/fruitlands-museum/'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SOURCE = 'Fruitlands Museum trail map (The Trustees, August 2024; thetrustees.org/place/fruitlands-museum)'
COMMONS = 'https://commons.wikimedia.org/w/api.php'

K = 4                    # map units per PDF point
M_PER_PT = 2.0           # metres per PDF point (scale bar)
WALK = round(M_PER_PT / K / 0.35, 3)       # floor.walkScale: the app counts 0.35 m per unit


def get(url, name, binary=False):
    """Read a page once, politely, and keep it in .cache/fruitlands."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / name
    if not f.exists():
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, url], capture_output=True).stdout
        time.sleep(2)
        if not out: raise SystemExit(f'could not read {url}')
        f.write_bytes(out)
    return f.read_bytes() if binary else f.read_text(errors='replace')


def text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def P(x, y):
    """A point on the PDF page (points) -> map units."""
    return [round(x * K, 1), round(y * K, 1)]


# ---- geometry -------------------------------------------------------------------------------------------------
def centroid(pg):
    return [sum(p[0] for p in pg) / len(pg), sum(p[1] for p in pg) / len(pg)]


def hull(pts):
    pts = sorted(set(map(tuple, pts)))
    if len(pts) < 3: return [list(p) for p in pts]
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return [list(p) for p in lo[:-1] + up[:-1]]


def grow(pg, f):
    cx, cy = centroid(pg)
    return [[cx + (x - cx) * f, cy + (y - cy) * f] for x, y in pg]


def seg_closest(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return [ax + t * dx, ay + t * dy]


def line_closest(p, line):
    best = None
    for a, b in zip(line, line[1:]):
        q = seg_closest(p, a, b)
        d = math.dist(p, q)
        if best is None or d < best[0]: best = (d, q)
    return best


def band(pts, half):
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        nx, ny = -dy / n * half, dx / n * half
        left.append([round(x + nx, 1), round(y + ny, 1)]); right.append([round(x - nx, 1), round(y - ny, 1)])
    return left + right[::-1]


def along(line, frac=0.5):
    total = sum(math.dist(a, b) for a, b in zip(line, line[1:]))
    goal, run = total * frac, 0
    for a, b in zip(line, line[1:]):
        d = math.dist(a, b)
        if run + d >= goal and d:
            t = (goal - run) / d
            return [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]
        run += d
    return line[-1]


def inside(pt, pg):
    x, y = pt
    hit = False
    for (x1, y1), (x2, y2) in zip(pg, pg[1:] + pg[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def circle(cx, cy, r, n=14):
    return [[cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)] for i in range(n)]


# ---- reading the museum's map ---------------------------------------------------------------------------------
def svg():
    get(MAP_PDF, 'trail-map.pdf', binary=True)
    f = CACHE / 'trail-map.svg'
    if not f.exists():
        subprocess.run(['pdftocairo', '-svg', str(CACHE / 'trail-map.pdf'), str(f)], check=True)
    return f.read_text()


def path_points(d, tr):
    """The corner points of an SVG path (curves by their end points), with its transform applied."""
    a, b, c, dd, e, f = tr
    nums = [float(v) for v in re.findall(r'-?[\d.]+(?:e-?\d+)?', re.sub(r'[MLCZ]', ' ', d))]
    cmds = re.findall(r'[MLCZ]', d)
    pts, i = [], 0
    for cmd in cmds:
        if cmd in 'ML': xy = nums[i:i + 2]; i += 2
        elif cmd == 'C': xy = nums[i + 4:i + 6]; i += 6
        else: continue
        x, y = xy
        pts.append([a * x + c * y + e, b * x + dd * y + f])
    return pts


def colour(s):
    return tuple(round(float(v)) for v in re.findall(r'([\d.]+)%', s))


TRAILS = {  # stroke colour (rounded %) -> name and length printed in the map's key
    (98, 87, 2): ('Yellow Trail', '0.8 miles'), (85, 11, 17): ('Red Trail', '0.9 miles'),
    (96, 53, 8): ('Orange Trail', '0.8 miles'), (13, 32, 66): ('Blue Trail (Old Union Turnpike)', '0.3 miles'),
    (100, 100, 100): ('White Trail (Historic Road)', '0.4 miles'), (13, 11, 11): ('Old Meadow loop', None),
    (6, 6, 5): ('Trail', None), (64, 63, 63): ('Museum drive', None),
}
LOT = (64, 63, 63)          # the parking lots are filled with the drive's grey


def read_map(s):
    buildings, lines, lots = [], [], []
    for m in re.finditer(r'<path ([^>]*?)d="([^"]+)"([^>]*)/>', s):
        attrs = m[1] + m[3]
        tr = re.search(r'transform="matrix\(([^)]+)\)"', attrs)
        tr = [float(v) for v in tr[1].split(',')] if tr else [1, 0, 0, 1, 0, 0]
        fill = re.search(r'fill="(rgb[^"]+)"', attrs)
        stroke = re.search(r'stroke="(rgb[^"]+)"', attrs)
        width = re.search(r'stroke-width="([^"]+)"', attrs)
        if fill and colour(fill[1]) == (13, 11, 11) and not stroke:
            buildings.append(path_points(m[2], tr))
        elif fill and colour(fill[1]) == LOT and not stroke:
            pts = path_points(m[2], tr)
            if 300 < centroid(pts)[1] < 430: lots.append(pts)
        elif stroke and width and float(width[1]) >= 1.5 and colour(stroke[1]) in TRAILS:
            pts = path_points(m[2], tr)
            if len(pts) < 2 or min(p[1] for p in pts) < 215: continue            # the key above the map
            lines.append((colour(stroke[1]), float(width[1]), pts))
    # the same line is often drawn twice (a white casing under the colour): keep one
    seen, out = set(), []
    for c, w, pts in sorted(lines, key=lambda l: l[0] == (100, 100, 100)):
        key = tuple(round(v) for p in pts[:3] for v in p)
        if key in seen: continue
        seen.add(key); out.append((c, w, pts))
    return buildings, out, lots


# ---- the map --------------------------------------------------------------------------------------------------
# The buildings on the trail map (each a few dark rectangles), by a point inside each one (PDF points)
BUILDINGS = [
    # id, kind, name, a point in it, grow
    ('Admissions', 'space', 'Admissions, Museum Store and Fruitlands Café (Prospect House) · accessible restrooms',
     (573, 420), 1.5),
    ('Wayside', 'space', 'Wayside Visitor Center: classroom, education and exhibit space · accessible restrooms',
     (599, 368), 1.8),
    ('Four Seasons', 'gallery', 'Four Seasons Gallery', (620, 385), 1.7),
    ('Seasonal Gallery', 'gallery', 'Seasonal Gallery (built in 1928 as the Native American Museum): Shaker exhibitions',
     (635, 353), 1.5),
    ('Shaker Gallery', 'gallery', 'Shaker Gallery: the 1794 Shaker Office, moved from the Harvard Shaker Village in 1920 '
                                  '(steps; not wheelchair-accessible)', (620, 340), 2.6),
    ('Farmhouse', 'gallery', 'Fruitlands Farmhouse (1820s), home of the Alcotts’ 1843 Transcendentalist community '
                             '(steps; not wheelchair-accessible)', (651, 298), 1.5),
]
CLOSED_BUILDINGS = [(583, 449), (655, 470), (292, 510)]   # offices, Red Barn service area, private residence

# Outdoor places (PDF points): id, name, polygon, label
AREAS = [   # drawn beside the paths, not over them, so the drive and trails stay visible
    ('Museum Hill', 'Museum Hill: the lawn between the Wayside and the Shaker Gallery, with the outdoor sculptures',
     [(600, 349), (613, 343), (617, 350), (615, 358), (607, 364), (600, 359)], 'Lawn'),
    ('Farmhouse Grounds', 'Farmhouse grounds and the view west over the Nashua River valley',
     [(623, 299), (636, 291), (641, 298), (634, 306), (624, 306)], 'Grounds'),
    ('Old Meadow', 'Old Meadow: the meadow inside the loop trail below the museum',
     [(378, 449), (500, 448), (500, 471), (378, 472)], 'Old Meadow'),
]
SITES = [   # historic places along the trails: id, name, centre (dot on the map)
    ('Pergolas Site', 'Pergolas Site: overlook where Clara Endicott Sears’s summer house, The Pergolas, stood', (366, 477)),
    ('Willard Farm Site', 'Willard Farm Site (archaeological site)', (408, 365)),
    ('Glacial Beach', 'Glacial Beach', (124, 271)),
    ('Brickworks', 'Brickworks (site of a 19th-century brickyard)', (178, 240)),
]
LOTS = [   # id, name, a point in it
    ('Upper lot', 'Upper parking lot, by the Museum Store (accessible parking)', (596, 413)),
    ('Lower lot', 'Lower parking lot, by the Wayside and the galleries (accessible parking)', (582, 371)),
    ('Farmhouse lot', 'Turnaround above the Farmhouse', (628, 315)),
]
HOME = ['Admissions', 'Wayside', 'Farmhouse', 'Four Seasons Eye', 'Seasonal Gallery', 'Museum Hill']

AMENITIES = [   # type, PDF point
    ('entrance', 603, 487),                       # ENTRANCE from Prospect Hill Road
    ('info', 567, 421), ('shop', 572, 420), ('dining', 577, 419), ('restroom', 565, 424),   # Prospect House
    ('restroom', 599, 365),                       # Wayside Visitor Center
]
LABELS = [   # text, kind, PDF point
    ('Oxbow National Wildlife Refuge', 'note', 500, 200),
    ('Railroad tracks', 'note', 505, 238),
    ('Prospect Hill Road', 'note', 450, 500),
    ('ENTRANCE', 'area', 577, 505),
    ('P', 'area', 596, 413),
    ('P', 'area', 582, 371),
    ('Red Barn · service area (staff only)', 'note', 676, 485),
    ('Private property', 'note', 50, 432),
    ('Private property', 'note', 170, 545),
    ('Private residence', 'note', 312, 520),
    ('To Route 110 N and Route 2', 'note', 724, 505),
    ('Woodland trails: Red, Orange, Blue and White', 'note', 260, 330),
]


def build_floors():
    buildings, lines, lots = read_map(svg())
    rooms, closed = [], []

    # buildings: the rectangles near each point make one building
    groups = []
    for r in buildings:
        c = centroid(r)
        for g in groups:
            if any(math.dist(c, centroid(o)) < 9 for o in g): g.append(r); break
        else: groups.append([r])
    shapes = [hull([p for r in g for p in r]) for g in groups]
    shape_at = lambda pt: min(shapes, key=lambda s: math.dist(centroid(s), pt))
    for bid, kind, name, pt, f in BUILDINGS:
        pg = grow(shape_at(pt), f)
        if bid == 'Four Seasons':
            # two galleries: the larger (Across Boundaries Across Barriers) and the smaller (Eye of the Beholder)
            xs = sorted(p[0] for p in pg); cut = xs[0] + (xs[-1] - xs[0]) * 0.58
            left = [p for p in pg if p[0] <= cut]; right = [p for p in pg if p[0] >= cut]
            ys = [p[1] for p in pg]
            left_pg = hull(left + [[cut, min(ys)], [cut, max(ys)]])
            right_pg = hull(right + [[cut, min(ys)], [cut, max(ys)]])
            rooms.append({'id': 'Four Seasons Across', 'kind': 'gallery', 'z': 2, 'label': 'Across Boundaries',
                          'name': 'Four Seasons Gallery, larger gallery: Across Boundaries Across Barriers '
                                  '(Native American art; layout approximate)',
                          'poly': [P(*p) for p in left_pg]})
            rooms.append({'id': 'Four Seasons Eye', 'kind': 'gallery', 'z': 2, 'label': 'Eye of the Beholder',
                          'name': 'Four Seasons Gallery, smaller gallery: Eye of the Beholder (layout approximate)',
                          'poly': [P(*p) for p in right_pg]})
            continue
        r = {'id': bid, 'kind': kind, 'name': name, 'poly': [P(*p) for p in pg], 'z': 2}
        if kind == 'gallery': r['label'] = {'Shaker Gallery': 'Shaker', 'Seasonal Gallery': 'Seasonal'}.get(bid, bid)
        rooms.append(r)
    for pt in CLOSED_BUILDINGS:
        closed.append({'poly': [P(*p) for p in grow(shape_at(pt), 1.3)]})

    for pts in lots:
        c = centroid(pts)
        lid, name = min(LOTS, key=lambda l: math.dist(l[2], c))[:2]
        rooms.append({'id': lid, 'kind': 'space', 'name': name, 'poly': [P(*p) for p in pts], 'z': 1})
    for aid, name, pg, label in AREAS:
        rooms.append({'id': aid, 'kind': 'gallery', 'name': name, 'label': label, 'poly': [P(*p) for p in pg], 'z': 0})
    for sid, name, (x, y) in SITES:
        rooms.append({'id': sid, 'kind': 'gallery', 'name': name, 'label': sid.replace(' Site', ''),
                      'poly': [P(*p) for p in circle(x, y, 7)], 'z': 2})

    # paths: the drive, the lots' connectors and every trail, as the map draws them
    walks = []
    for i, (c, w, pts) in enumerate(lines):
        name, miles = TRAILS[c]
        half = 2.4 if name == 'Museum drive' else 1.3
        line = [P(*p) for p in pts]
        nm = name + (f' · {miles} long' if miles else '')
        r = {'id': f'path-{i + 1}', 'kind': 'corridor', 'name': nm, 'poly': band(line, half * K), 'z': 1}
        walks.append((r, line))
        rooms.append(r)
    doors = []
    # paths meet where one's end touches another
    for r, line in walks:
        for end in (line[0], line[-1]):
            best = None
            for r2, l2 in walks:
                if r2 is r: continue
                d, q = line_closest(end, l2)
                if best is None or d < best[0]: best = (d, q, r2)
            if best and best[0] < 4 * K:
                doors.append({'a': r['id'], 'b': best[2]['id'], 'at': [round(v, 1) for v in end], 'width': 8,
                              'axis': 'o'})
            else:
                near = sorted((x for x in rooms if x['kind'] == 'space'
                               and math.dist(end, centroid(x['poly'])) < 16 * K),
                              key=lambda x: math.dist(end, centroid(x['poly'])))
                if near:
                    doors.append({'a': r['id'], 'b': near[0]['id'], 'at': [round(v, 1) for v in end], 'width': 8,
                                  'axis': 'o'})
    # every place opens onto its nearest path
    for r in rooms:
        if r['kind'] == 'corridor': continue
        c = centroid(r['poly'])
        if r['id'] in ('Four Seasons Across',):            # the galleries' door is on the drive side
            c = [c[0] - 3 * K, c[1]]
        best = min(((line_closest(c, line), wr) for wr, line in walks), key=lambda t: t[0][0])
        (d, q), wr = best
        doors.append({'a': wr['id'], 'b': r['id'], 'at': [round(q[0], 1), round(q[1], 1)], 'width': 8, 'axis': 'o'})
        if d > 40 * K: print(f'  note: {r["id"]} is {d / K * M_PER_PT:.0f} m from the nearest path')
    doors.append({'a': 'Four Seasons Across', 'b': 'Four Seasons Eye',
                  'at': [round(v, 1) for v in centroid(next(r['poly'] for r in rooms if r['id'] == 'Four Seasons Eye'))],
                  'width': 8, 'axis': 'o'})

    seen, uniq = set(), []
    for d in doors:
        k = (frozenset((d['a'], d['b'])), tuple(d['at']))
        if k not in seen: seen.add(k); uniq.append(d)
    doors = uniq
    floor = {'id': 'G', 'label': 'Grounds', 'order': 0,
             'area': 'The 210-acre grounds: Admissions, Café and Store · Wayside Visitor Center · Four Seasons Gallery · '
                     'Seasonal Gallery · Shaker Gallery · Fruitlands Farmhouse · Old Meadow · woodland trails',
             'transform': [1, 0, 0], 'walkScale': WALK, 'homeView': HOME,
             'rooms': rooms, 'closed': closed,
             'amenities': [{'type': t, 'at': P(x, y)} for t, x, y in AMENITIES],
             'labels': [{'text': t, 'kind': k, 'at': P(x, y)} for t, k, x, y in LABELS], 'doors': doors}
    return {'about': 'Built by tools/build_fruitlands.py from Fruitlands Museum’s own trail map (The Trustees, '
                     'August 2024), kept as the museum prints it (north is up and to the right). Buildings, drive, '
                     'parking and trails are the map’s; buildings are drawn a little larger so they can be tapped. '
                     'Inside the buildings there is no published plan.',
            'source': SOURCE, 'units': f'PDF points of the trail map x {K} (about {M_PER_PT / K:.1f} m each)',
            'defaultFloor': 'G', 'galleryWord': 'Place', 'floors': [floor]}


# ---- works ----------------------------------------------------------------------------------------------------
CREDIT = 'Collection of Fruitlands Museum, The Trustees'
EYE = SITE + '/exhibit/eye-of-the-beholder/'
ACROSS = SITE + '/exhibit/across-boundaries-across-barriers/'

# Wikimedia Commons photos taken at Fruitlands (author, licence from the file page)
C = {
    'farmhouse': 'Fruitlands Museum - exterior Bronson Alcott farmhouse.jpg',
    'shaker': 'Fruitlands Museum - exterior Shaker Office.jpg',
    'seasonal': 'Fruitlands Museum - exterior Native American collection.jpg',
    'pumanangwet': 'Fruitlands Museum - sculpture 4.jpg',
    'wopeen': 'Fruitlands Museum - sculpture 5.jpg',
    'nymph': 'Fruitlands Museum - sculpture 6.jpg',
    'marble': 'Fruitlands Museum - sculpture 3.jpg',
    'wheelwright': 'Fruitlands Museum - sculpture 1.jpg',
    'thoreau': 'Thoreau desk at Fruitlands.jpg',
    'belongings': 'Alcott family belongings at Fruitlands.jpg',
    'sketch': 'Pencil sketch of Bronson Alcott by his daughter may.jpg',
    'candles': 'Colonial candle molds at fruitlands.jpg',
    'attic': 'Fruit lands Alcott house, 2015 attic.jpg',
    'initials': 'Initials and date at Fruitlands.jpg',
    'well': 'Well at fruitlands.jpg',
    'wetu': 'Wetu recreation at fruitlands.jpg',
    'herbs': 'Shaker herbs at fruitlands .jpg',
    'shakerroom': 'Shaker museum at fruitlands.jpg',
    'view': 'Fruitlands Museum - buildings 2.jpg',
}

# (key, gallery, title, artist, date, medium, accession, image (url or C key), url, description, note)
ON_VIEW = [
    # Four Seasons Gallery, Eye of the Beholder (April 30, 2026 – November 7, 2027)
    ('plymouth-rock', 'Four Seasons Eye', 'Piece of Plymouth Rock', 'Unknown', 'collected about 1929',
     'Stone, paper, wood and glass', 'FM.I.2011.20',
     SITE + '/wp-content/uploads/2026/02/Plymouth-Rock-1-scaled-608x0-c-default.jpeg', EYE, None, None),
    ('diamond-smuggler', 'Four Seasons Eye', 'Mrs. John Gray, The Diamond Smuggler', 'Henry Williams (1787–1830)', '1826',
     'Oil on canvas', 'FM.G.1946.20',
     SITE + '/wp-content/uploads/2026/02/Diamond-Smuggler-scaled-608x0-c-default.jpeg', EYE, None, None),
    ('cat-effigy', 'Four Seasons Eye', 'Cat Effigy', 'Ko-tyīt (Cochiti Pueblo)', '1880–1930', 'Clay and slip',
     'FM.I.1929.862', SITE + '/wp-content/uploads/2026/02/Cat-ceramic-figure-608x0-c-default.jpeg', EYE, None, None),
    ('washington-birthplace', 'Four Seasons Eye', 'Birthplace of George Washington', 'Thomas Chambers (1808–1869)',
     '1830–1850', 'Oil on canvas', 'FM.G.1946.252',
     SITE + '/wp-content/uploads/2026/02/Birthplace-of-Washington-scaled-608x0-c-default.jpeg', EYE, None, None),
    ('pinecone-ball', 'Four Seasons Eye', 'Pinecone ball on wood stand', 'Artist once known, Shaker (New England)',
     '1920–1930', 'Wood and pinecone', 'FM.S.1987.1150',
     SITE + '/wp-content/uploads/2026/02/Pinecone-ball-scaled-608x0-c-default.jpeg', EYE, None, None),
    # Four Seasons Gallery, Across Boundaries Across Barriers (June 15, 2024 – September 1, 2029). Objects named in
    # The Harvard Press's review of the show (2024), section by section; the museum shows no pictures of them.
    ('raven', 'Four Seasons Across', 'Raven Releases the Light', 'Tom Patterson', None, 'Carved and painted wood mask',
     None, None, ACROSS, 'A large mask, mostly black with yellow and red: strings open the raven’s beak to show a '
     'sun face inside.', 'East section, Radiant Traditions.'),
    ('halibut-hook', 'Four Seasons Across', 'Halibut Hook', 'Tlingit artist', '20th century', None, None, None, ACROSS,
     None, 'South section, Flowing Connections.'),
    ('ollas', 'Four Seasons Across', 'Ollas (water jars)', 'Pueblo artists', None, 'Clay and fiber', None, None, ACROSS,
     None, 'South section, Flowing Connections.'),
    ('pueblo-olla', 'Four Seasons Across', 'Olla with dancers', 'Pueblo artist', '1985', 'Clay, acrylic paint', None,
     None, ACROSS, 'Painted with traditional dancers.', 'West section, Cycles of Renewal.'),
    ('burl-bowl', 'Four Seasons Across', 'Burl bowl', 'A Seneca artist once known', 'early 20th century', 'Carved wood',
     None, None, ACROSS, None, 'North section, Roots and Reflection.'),
    ('cribbage-board', 'Four Seasons Across', 'Cribbage board', 'Alaska Native artist', '1920', 'Walrus ivory', None,
     None, ACROSS, 'Engraved with hunting scenes, shown over a mirror so both sides can be seen.',
     'North section, Roots and Reflection.'),
    ('aquinnah-vase', 'Four Seasons Across', 'Vase of Aquinnah clay', 'Wampanoag artist (Martha’s Vineyard)', None,
     'Clay', None, None, ACROSS, None, 'Center section, Embodied Homelands.'),
    ('bandolier-bag', 'Four Seasons Across', 'Bandolier bag', 'Unknown', '1900', 'Glass beads', None, None, ACROSS,
     'Beaded with plant life.', 'Center section, Embodied Homelands.'),
    ('bear-sun-necklace', 'Four Seasons Across', 'Bear and sun necklace', 'Elizabeth James-Perry (Aquinnah Wampanoag)',
     '2020', 'Quahog shell', None, None, ACROSS, None, 'Center section, Embodied Homelands.'),
    ('across-installation', 'Four Seasons Across', 'Across Boundaries Across Barriers (the exhibition)',
     'Curated by Tess Lukey (Aquinnah Wampanoag)', '2024', 'Installation view', None, 'across', ACROSS,
     'Historic and contemporary works from several Native American communities, arranged in five sections after the '
     'seven directions of the medicine wheel (East, South, West, North and Center). A back study room invites Native '
     'visitors to give a blessing to an object.', 'Photo of the installation by Mel Taing.'),
    ('quillbox', 'Four Seasons Across', 'Quillbox', 'Unknown', None, 'Birch bark, spruce, porcupine quills', None, None,
     ACROSS, None, None),
    # Shaker Gallery and Seasonal Gallery
    ('shaker-office', 'Shaker Gallery', 'The Shaker Office (1794)', 'Harvard Shaker Village', '1794', 'Building',
     None, 'shaker', PLACE,
     'The office of the Shaker community in Harvard, built in 1794, where the Shakers met the outside world. Clara '
     'Endicott Sears had it moved to Fruitlands in 1920 and opened it in 1922 as the first Shaker museum in the '
     'United States, with one of the earliest collections of Shaker objects.', None),
    ('shaker-room', 'Shaker Gallery', 'Shaker rooms and furniture', 'Shakers of the Harvard community', None,
     'Furniture and household objects', None, 'shakerroom', PLACE, None, 'Photographed in 2016; displays change.'),
    ('shaker-herbs', 'Shaker Gallery', 'Shaker herbs and medicines', 'Shakers', None, 'Glass jars, herbs, paper labels',
     None, 'herbs', PLACE, 'The Shakers grew, dried and sold medicinal herbs; their jars and packets are shown here.',
     'Photographed in 2016; displays change.'),
    ('seasonal-gallery', 'Seasonal Gallery', 'The Seasonal Gallery building (1928)', 'Fruitlands Museum', '1928',
     'Building', None, 'seasonal', PLACE,
     'Opened in 1928 as the Native American Museum, renamed the Seasonal Gallery in 2024. In 2026 it shows Shaker '
     'objects and a contemporary art installation in changing exhibitions.', None),
    # Fruitlands Farmhouse
    ('farmhouse', 'Farmhouse', 'Fruitlands Farmhouse', None, '1820s', 'Building', None, 'farmhouse', PLACE,
     'The only building original to the site. Amos Bronson Alcott and Charles Lane began their Transcendentalist '
     'community here in 1843; ten-year-old Louisa May Alcott lived here and later wrote about it. It lasted seven '
     'months. Clara Endicott Sears restored the house and opened it as a museum in 1914.', None),
    ('thoreau-desk', 'Farmhouse', 'Desk associated with Henry David Thoreau', None, None, 'Wood', None, 'thoreau', PLACE,
     None, 'Photographed in 2016; displays change.'),
    ('alcott-belongings', 'Farmhouse', 'Alcott family belongings', None, '19th century', None, None, 'belongings', PLACE,
     None, 'Photographed in 2016; displays change.'),
    ('alcott-sketch', 'Farmhouse', 'Bronson Alcott (pencil sketch)', 'May Alcott (1840–1879)', None, 'Pencil on paper',
     None, 'sketch', PLACE, 'Louisa May’s youngest sister drew their father at his desk.',
     'Photographed in 2016; displays change.'),
    ('candle-molds', 'Farmhouse', 'Candle molds', None, None, 'Tin and wood', None, 'candles', PLACE, None,
     'Photographed in 2016; displays change.'),
    ('attic', 'Farmhouse', 'The attic', None, None, None, None, 'attic', PLACE,
     'The attic where the Alcott girls slept during the Fruitlands experiment.', None),
    ('initials', 'Farmhouse', 'Initials and date on a beam', None, '1820s', 'Paint on wood', None, 'initials', PLACE,
     None, None),
    ('well', 'Farmhouse Grounds', 'The well', None, None, 'Wood and stone', None, 'well', PLACE, None, None),
    # outdoor sculptures (Smithsonian Inventory of American Sculpture numbers from the Commons pages)
    ('pumanangwet', 'Museum Hill', 'Pumanangwet (He Who Shoots the Stars)', 'Philip Shelton Sears (1867–1953)', '1929',
     'Bronze on a boulder', 'SIRIS MA000521', 'pumanangwet', PLACE,
     'A Native archer aiming at the sky, by the brother of Fruitlands founder Clara Endicott Sears.',
     'On the lawn between the Shaker Gallery and the Seasonal Gallery.'),
    ('wo-peen', 'Museum Hill', 'Wo-Peen', 'Philip Shelton Sears (1867–1953)', 'dedicated 1938', 'Bronze on a boulder',
     'SIRIS MA000520', 'wopeen', PLACE, None, 'Outside, near the Seasonal Gallery (the former Native American Museum).'),
    ('wood-nymph', 'Museum Hill', 'Wood nymph', None, None, 'Marble', 'SIRIS MA000519', 'nymph', PLACE, None,
     'A garden sculpture in the trees on the grounds (photographed in 2009; the exact spot is not published).'),
    ('marble-figure', 'Museum Hill', 'Marble garden figure', None, None, 'Marble', 'SIRIS MA000518', 'marble', PLACE,
     None, 'On the grounds (photographed in 2009; the exact spot is not published).'),
    ('wheelwright', 'Museum Hill', 'Figure', 'Joseph Wheelwright', None, 'Tree trunk and roots', None, 'wheelwright',
     PLACE, None, 'On the lawn looking west over the valley (photographed in 2009; it may have been moved).'),
    ('wetu', 'Museum Hill', 'Wetu (Wampanoag house), a recreation', None, None, 'Saplings and bark', None, 'wetu', PLACE,
     'A recreation of a wetu, the dome-shaped bark house of the Native people of southern New England.',
     'On the grounds (photographed in 2016).'),
]

# Fruitlands collection works shown in past exhibitions (museum page only; not on the map)
PAST = [
    ('portrait-of-a-woman', 'Portrait of a Woman', 'Francis Alexander (1800–1880)', '1837', 'Oil on canvas',
     'FM.G.1980.306', 'wind-from-the-hills'),
    ('the-notch', 'The Notch', 'Alvan Fisher (1792–1863)', '1834', 'Oil on canvas', 'FM.G.1967.287', 'wind-from-the-hills'),
    ('hudson-west-point', 'View of the Hudson River from West Point', 'Robert Weir (1803–1889)', '1897', 'Oil on canvas',
     'FM.G.1945.156', 'wind-from-the-hills'),
    ('decolonized-map', 'Decolonized Map of New England', 'Elizabeth James-Perry (Aquinnah Wampanoag)', '2020',
     'Watercolor and graphite on paper', None, 'decolonized-map-of-massachusetts'),
    ('chart-daniel-john', 'A Chronological Chart of the Visions of Daniel & John',
     'After a design by Charles Fitch and Apollos Hale', '1842', 'Hand-tinted lithograph on cloth', None,
     'recruiting-for-utopia-print-and-the-imagination'),
]


def commons_info():
    """Picture URL, author and licence of each Commons photo (one API call, cached)."""
    titles = '|'.join('File:' + t for t in C.values())
    q = urllib.parse.urlencode({'action': 'query', 'titles': titles, 'prop': 'imageinfo', 'format': 'json',
                                'iiprop': 'url|extmetadata', 'iiurlwidth': 1000})
    d = json.loads(get(f'{COMMONS}?{q}', 'commons.json'))
    out = {}
    for p in d['query']['pages'].values():
        ii = p['imageinfo'][0]; md = ii['extmetadata']
        g = lambda k: text(md.get(k, {}).get('value', ''))
        out[p['title'][5:]] = {'url': ii['thumburl'], 'credit': f'Photo: {g("Artist")}, {g("LicenseShortName")}, via '
                                                                f'Wikimedia Commons',
                               'page': ii['descriptionurl']}
    return out


def picture(key, url):
    """Download once (politely) and save a phone-sized JPEG; returns the app path."""
    if not url: return None
    raw = CACHE / 'img' / (key + (Path(urllib.parse.urlparse(url).path).suffix.lower() or '.jpg'))
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, url], capture_output=True).stdout
        time.sleep(1.5)
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
    return f'data/fruitlands/images/{key}.jpg'


def year_of(date):
    m = re.search(r'(\d{4})', date or '')
    return int(m[1]) if m else None


def slides(name, url):
    """(picture, caption) of each slide on an exhibition page."""
    page = get(url, name)
    out = []
    for m in re.finditer(r'class="slider-popup"[^>]*href="([^"]+)".*?<div class="slider__content">\s*(?:<p>(.*?)</p>)?',
                         page, re.S):
        out.append((m[1], text(m[2] or '')))
    return out


def eye_images():
    """The Eye of the Beholder pictures, matched to their captions on the exhibition page."""
    out = {}
    for img, cap in slides('ex-eye-of-the-beholder.html', EYE):
        acc = re.search(r'FM\.[A-Z]\.\d{4}\.\d+', cap)
        if acc: out[acc[0]] = img
    return out


def build_works(floors):
    rooms = {r['id']: r for r in floors['floors'][0]['rooms']}
    info = commons_info()
    eye = eye_images()
    out = []
    for key, room, title, artist, date, medium, acc, img, url, desc, note in ON_VIEW:
        credit = None
        if img == 'across':
            img = slides('ex-across-boundaries-across-barriers.html', ACROSS)[0][0]; credit = 'Photo: Mel Taing (The Trustees)'
        elif img in C:
            ci = info.get(C[img]); img = ci and ci['url']; credit = ci and ci['credit']
        elif acc in eye:
            img = eye[acc]; credit = 'Fruitlands Museum, The Trustees'
        elif img:
            credit = 'Fruitlands Museum, The Trustees'
        k = f'fruitlands-{key}'
        exhibition = ('Eye of the Beholder (April 30, 2026 – November 7, 2027)' if url == EYE else
                      'Across Boundaries Across Barriers (June 15, 2024 – September 1, 2029)' if url == ACROSS else None)
        a = {'id': k, 'title': title, 'artist': artist or ('Historic building' if medium == 'Building' else 'Unknown maker'), 'date': date, 'year': year_of(date),
             'medium': medium, 'accession': acc,
             'creditLine': CREDIT if acc and acc.startswith('FM.') else None,
             'gallery': room, 'galleryName': rooms[room]['name'], 'floor': 'G', 'placeNote': note,
             'description': desc, 'exhibition': exhibition, 'url': url, 'image': picture(k, img),
             'imageCredit': credit if img else None}
        out.append({k2: v for k2, v in a.items() if v not in (None, '')})
    return {'source': 'thetrustees.org exhibition pages, The Harvard Press (Across Boundaries), Wikimedia Commons photos '
                      'taken at Fruitlands',
            'checked': time.strftime('%Y-%m-%d'), 'count': len(out), 'complete': False, 'artworks': out}


def build_guide(works):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'),
                     'year': a.get('year'), 'medium': a.get('medium'), 'accession': a.get('accession'), 'url': a['url'],
                     'imageUrl': a.get('image'), 'onView': True, 'gallery': a['gallery'], 'floor': 'G'}.items()
                     if v not in (None, '')})
    for key, title, artist, date, medium, acc, show in PAST:
        url = f'{SITE}/exhibit/{show}/'
        img = None
        for pic, cap in slides(f'ex-{show}.html', url):
            if (acc and acc in cap) or (not acc and title.split()[0] in cap and title.split()[-1].strip('"') in cap):
                img = pic; break
        k = f'fruitlands-{key}'
        rows.append({k2: v for k2, v in {'id': k, 'title': title, 'artist': artist, 'date': date, 'year': year_of(date),
                     'medium': medium, 'accession': acc, 'url': url, 'imageUrl': picture(k, img),
                     'onView': False}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': 'Fruitlands Museum', 'checked': time.strftime('%Y-%m-%d'),
            'source': 'Fruitlands trail map, thetrustees.org exhibition pages, Wikimedia Commons', 'onViewKnown': True,
            'note': 'Fruitlands has about 6,000 objects (Shaker, Native American, Hudson River School landscapes and '
                    'some 230 folk portraits), but its collection is not online. Listed here: what the museum shows '
                    'in its galleries now, the historic buildings, the sculptures outside, and collection works from '
                    'past exhibitions. The buildings are closed from early November until spring; the grounds stay open.',
            'works': rows}


def main():
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works = build_works(floors)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': sum(w['onView'] for w in guide['works']), 'galleries': True,
                              'checked': guide['checked'],
                              'source': 'Fruitlands Museum: trail map and exhibition pages (thetrustees.org), Wikimedia Commons'}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    f = floors['floors'][0]
    print(f'map: {len(f["rooms"])} rooms ({sum(r["kind"] == "corridor" for r in f["rooms"])} paths), '
          f'{len(f["doors"])} doors, {len(f["closed"])} closed')
    print(f'{works["count"]} works on view, {sum("image" in a for a in works["artworks"])} with pictures; '
          f'museum page {len(guide["works"])}')


if __name__ == '__main__':
    sys.exit(main())
