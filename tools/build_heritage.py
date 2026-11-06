#!/usr/bin/env python3
"""Build the Heritage Museums & Gardens (Sandwich, MA) map guide (run: python3 tools/build_heritage.py).

    data/heritage/floors.json      the 100-acre grounds seen from above (a flat 2D plan): the three galleries, the
                                   Welcome Center, Lilly's Café, the gardens, paths, nature trails, parking, restrooms
    data/heritage/artworks.json    what is shown in each gallery and outdoors (cars, carousel, cranberries, Revolution,
                                   the Old East Mill, the wetu and mush8n, the gardens)
    data/heritage/images/          their pictures, made smaller for phones
    data/guides/Q5738956.json      the same list for the museum page, plus collection works not on view now

The map is traced from Heritage's own 2026 visitor map (the "Download a map" link on
heritagemuseumsandgardens.org/map-of-heritage-museums-gardens, a two-page PDF of June 22, 2026). Page 1 is a vector
drawing, so the paved paths, stairs, nature trails, roads and garden areas come straight out of it (via
`pdftocairo -svg`): every paved path and nature trail is the map's own line, turned into a walkable path, and the
coloured garden areas, lawns, Shawme Pond and the parking are the map's own shapes. The galleries and other buildings
are drawn on the map as pictures in white ovals; each is placed where its picture sits, as an oval of about that size.
The map is an illustrated plan, not drawn to an exact scale, and it is kept as the museum prints it (north points up
and to the left, as the compass on the map shows).
Map units are PDF points x K. The map gives walking times from the Welcome Center (Automobile Gallery 4 minutes,
Special Exhibitions Gallery 10, American Art & Carousel Gallery 15); along the map's paths, at the app's walking pace, that is about 1.2 m per point.

The museum publishes no floor plans. Each gallery is one room.

The works: the 26 cars of From Carriage to Classic (the museum's car pages, with their own photos), the objects
pictured on the Cranberries, Remembering the Revolution and Looff Carousel pages, the outdoor exhibits (Old East Mill,
wetu, mush8n, Concrete Distinction) and the gardens. Heritage has over 18,000 objects, but its collection is not
online; the other 17 cars and a few collection works from the museum's blog are listed on the museum page as not on
view.
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
OUT = ROOT / 'data' / 'heritage'
CACHE = ROOT / '.cache' / 'heritage'
MUSEUM = 'Q5738956'
SITE = 'https://heritagemuseumsandgardens.org'
CDN = 'https://bunny-wp-pullzone-94pwz2rapx.b-cdn.net/wp-content/uploads/'
MAP_PDF = CDN + '2026/06/2026-6.22.29-Updated-front_back-compressed.pdf'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SOURCE = 'Heritage Museums & Gardens 2026 visitor map (heritagemuseumsandgardens.org/map-of-heritage-museums-gardens)'

K = 4                    # map units per PDF point
M_PER_PT = 1.2           # metres per PDF point: the app (0.9 m/s) then gives the map's walking times
WALK = round(M_PER_PT / K / 0.35, 3)       # floor.walkScale: the app counts 0.35 m per unit


def get(url, name, binary=False):
    """Read a page once, politely, and keep it in .cache/heritage."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / name
    if not f.exists():
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
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


def inside(pt, pg):
    x, y = pt
    hit = False
    for (x1, y1), (x2, y2) in zip(pg, pg[1:] + pg[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def oval(cx, cy, rx, ry, n=18):
    return [[round(cx + rx * math.cos(2 * math.pi * i / n), 2), round(cy + ry * math.sin(2 * math.pi * i / n), 2)]
            for i in range(n)]


def simplify(pts, tol):
    """Drop points closer than tol to the last one kept (the PDF's curves are finely sampled)."""
    out = [pts[0]]
    for p in pts[1:]:
        if math.dist(p, out[-1]) >= tol: out.append(p)
    if len(out) > 1 and math.dist(out[-1], pts[-1]) > 0: out[-1] = pts[-1]
    return out


# ---- reading the museum's map ---------------------------------------------------------------------------------
def svg():
    get(MAP_PDF, 'visitor-map-2026.pdf', binary=True)
    f = CACHE / 'visitor-map-2026.svg'
    if not f.exists():
        subprocess.run(['pdftocairo', '-svg', '-f', '1', '-l', '1', str(CACHE / 'visitor-map-2026.pdf'), str(f)],
                       check=True, capture_output=True)
    return f.read_text()


def path_points(d, tr):
    """Each subpath of an SVG path as a list of points (curves sampled), with its transform applied."""
    a, b, c, dd, e, f = tr
    nums = [float(v) for v in re.findall(r'-?[\d.]+(?:e-?\d+)?', re.sub(r'[MLCZ]', ' ', d))]
    subs, cur, i, last = [], [], 0, None
    for cmd in re.findall(r'[MLCZ]', d):
        if cmd == 'M':
            if cur: subs.append(cur)
            last = nums[i:i + 2]; i += 2; cur = [last]
        elif cmd == 'L':
            last = nums[i:i + 2]; i += 2; cur.append(last)
        elif cmd == 'C':
            c1, c2, p3 = nums[i:i + 2], nums[i + 2:i + 4], nums[i + 4:i + 6]; i += 6
            for t in (0.25, 0.5, 0.75, 1):
                u = 1 - t
                cur.append([u ** 3 * last[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p3[0],
                            u ** 3 * last[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p3[1]])
            last = p3
    if cur: subs.append(cur)
    return [[[a * x + c * y + e, b * x + dd * y + f] for x, y in s] for s in subs]


def colour(s):
    return tuple(round(float(v)) for v in re.findall(r'([\d.]+)%', s))


def area(p):
    return abs(sum(p[i][0] * p[i - 1][1] - p[i - 1][0] * p[i][1] for i in range(len(p)))) / 2


LINES = {   # (stroke colour, width) -> kind
    ((16, 37, 35), 3.4): 'paved', ((35, 17, 15), 1.0): 'trail', ((7, 19, 25), 6.3): 'stairs',
    ((5, 25, 14), 10.7): 'road',
}
FILLS = {   # fill colour -> the map's garden areas, lawns, pond and parking
    (96, 51, 42): 'senses', (68, 76, 91): 'hydrangea', (98, 71, 84): 'dexter', (98, 77, 26): 'hollow',
    (48, 77, 16): 'lawn', (37, 48, 68): 'pond', (62, 85, 33): 'adventure', (83, 82, 83): 'fraser',
    (78, 78, 78): 'plaza',
}


def in_legend(pts):
    return all(x > 540 and y > 362 for x, y in pts) or all(y > 448 for x, y in pts)


BRIDGES = [   # where an icon printed over a path hides a piece of it (PDF points)
    ((144.6, 254.7), (164.5, 255.9)),          # Automobile Gallery path, under the Nickerson Field quill icon
]


def read_map(s):
    lines, fills = [], []
    for m in re.finditer(r'<path ([^>]*?)d="([^"]+)"([^>]*)/>', s):
        attrs = m[1] + m[3]
        tr = re.search(r'transform="matrix\(([^)]+)\)"', attrs)
        tr = [float(v) for v in tr[1].split(',')] if tr else [1, 0, 0, 1, 0, 0]
        fill = re.search(r'fill="(rgb[^"]+)"', attrs)
        stroke = re.search(r'stroke="(rgb[^"]+)"', attrs)
        width = re.search(r'stroke-width="([^"]+)"', attrs)
        if stroke and width:
            kind = LINES.get((colour(stroke[1]), round(float(width[1]), 1)))
            if not kind: continue
            for pts in path_points(m[2], tr):
                if len(pts) >= 2 and not in_legend(pts): lines.append((kind, pts))
        elif fill and not stroke and colour(fill[1]) in FILLS:
            for pts in path_points(m[2], tr):
                if len(pts) > 3 and area(pts) > 300:
                    fills.append((FILLS[colour(fill[1])], pts))
    lines += [('paved', [list(a), list(b)]) for a, b in BRIDGES]
    seen, out = set(), []
    for kind, pts in lines:     # the same line is sometimes drawn twice: keep one
        key = (kind, tuple(round(v) for p in pts[:2] + pts[-1:] for v in p))
        if key in seen: continue
        seen.add(key); out.append((kind, pts))
    return out, fills


# ---- the map --------------------------------------------------------------------------------------------------
# Buildings: drawn as pictures in white ovals on the map; centre and radii in PDF points
BUILDINGS = [
    # id, kind, label, name, centre, rx, ry
    ('Welcome Center', 'space', None,
     'Barbey Family Welcome Center: Ticketing Pavilion and K.A.H.R. Courtyard, The Shop at Heritage, restrooms, '
     'Clarissa S. Nye Visitor Center, Flume Plaza', (199, 333), 31, 14),
    ('Auto Gallery', 'gallery', 'Automobile Gallery',
     'J.K. Lilly III Automobile Gallery (a round Shaker-style barn) & Heald Conference Center: From Carriage to '
     'Classic', (100, 243), 30, 18),
    ('Lilly’s Café', 'space', None, 'Lilly’s Café · restrooms · picnic tables', (181, 186), 26, 12),
    ('Special Exhibitions', 'gallery', 'Special Exhibitions',
     'Special Exhibitions Gallery: Cranberries: From Cape Cod to American Icon', (540, 148), 30, 15),
    ('Carousel Gallery', 'gallery', 'Art & Carousel',
     'American Art & Carousel Gallery: the 1908 Looff Carousel and Remembering the Revolution', (706, 225), 38, 17),
    ('Old East Mill', 'gallery', 'Old East Mill', 'Old East Mill (1800), the windmill moved here from Orleans in 1967',
     (190, 92), 13, 13),
    ('Treehouse', 'gallery', 'Treehouse', 'Hidden Hollow Treehouse (first floor accessible)', (684, 135), 14, 14),
    ('Wetu', 'gallery', 'Wetu', 'Wampanoag wetu and Three Sisters-style garden', (611, 113), 9, 7),
    ('Outdoor Stage', 'space', None, 'Outdoor Stage', (274, 207), 8, 9),
]
CLOSED_BUILDINGS = [((303, 152), 17, 10)]          # Administration Building (offices)

# Places outdoors (PDF points): id, label, name, centre, rx, ry
PLACES = [
    ('Mush8n', 'Mush8n', 'Mush8n: a 12-foot Wampanoag dugout canoe you can sit in', (432, 81), 17, 6),
    ('Labyrinth', 'Labyrinth', 'Labyrinth: a winding path to walk under the trees', (368, 160), 12, 12),
    ('Sundial', 'Sundial', 'Sundial', (258, 229), 8, 8),
    ('Flume', 'Flume Fountain', 'Flume Fountain: water plunges 26 feet into a pool of aquatic plants, beside the '
                                'Donald Marvin Daylily Garden', (200, 289), 15, 15),
    ('Maze Garden', 'Maze', 'Hart Family Maze Garden', (113, 106), 13, 13),
    ('Herb Garden', 'Herb Garden', 'Herb Garden (beside the Administration Building)', (333, 157), 13, 5),
    ('Hydrangea Test Garden', 'Test Garden', 'North American Hydrangea Test Garden', (378, 183), 11, 9),
    ('McInnes Garden', 'McInnes', 'McInnes Garden & Garden Gate', (582, 115), 9, 9),
    ('Overlook', 'Overlook', 'Shawme Pond Overlook (on the nature trail)', (412, 46), 9, 7),
    ('Concrete Distinction', 'Concrete Distinction', 'Concrete Distinction: Marybeth Lensel’s installation in the woods '
                                                     'behind the Arbor Bowl', (281, 318), 10, 10),
    ('Daylily Garden', 'Daylilies', 'Donald Marvin Daylily Garden', (228, 252), 22, 8),
    ('Dexter Terrace', 'Dexter Terrace', 'Dexter Terrace', (595, 210), 14, 7),
    ('Arbor Bowl', 'Arbor Bowl', 'Arbor Bowl (on the nature trails)', (296, 293), 14, 10),
]
# The map's own areas: kind from FILLS -> id, room kind, label, name
AREAS = {
    'senses': ('Garden of the Senses', 'gallery', 'Garden of the Senses',
               'The McGraw Family Garden of the Senses: boardwalk, water features and the Old East Mill'),
    'hydrangea': ('Hydrangea Garden', 'gallery', 'Hydrangeas', 'Cape Cod Hydrangea Society Display Garden'),
    'dexter': ('Dexter Garden', 'gallery', 'Dexter Rhododendrons',
               'Dexter Rhododendron Garden: two acres of Charles O. Dexter’s rhododendrons'),
    'hollow': ('Hidden Hollow', 'gallery', 'Hidden Hollow',
               'Hidden Hollow: outdoor discovery area for children 2–10 (portable restrooms at its entrance)'),
    'fraser': ('Fraser Terrace', 'space', None, 'Fraser Terrace'),
    'plaza': ('Courtyard', 'space', None, 'Welcome Center courtyard and Flume Plaza'),
}
LAWNS = [   # the three lawns, by a point in each
    ('Nickerson Field', 'Nickerson Field', 'Nickerson Field and the lawns between the Café, the Automobile Gallery and '
                                           'the Welcome Center', (110, 300)),
    ('Parade Field', 'Parade Field', 'Parade Field (the wetu, mush8n and Three Sisters garden are around it)', (500, 120)),
    ('Stage Lawn', 'Lawn', 'Lawn by the Outdoor Stage, Labyrinth and Herb Garden', (300, 200)),
]
LOTS = [   # id, name, polygon (PDF points)
    ('Elm Lot', 'Elm Lot (parking)', [(84, 276), (108, 266), (134, 263), (140, 300), (160, 325), (163, 345),
                                      (150, 352), (122, 344), (96, 330), (80, 302)]),
    ('Oak Lot', 'Oak Lot (parking)', [(201, 372), (240, 377), (282, 385), (285, 400), (260, 410), (228, 405),
                                      (203, 398)]),
    ('Birch Lot', 'Birch Lot (parking); the Overflow Lot is across Shawme Road',
     [(291, 375), (310, 361), (340, 358), (365, 370), (370, 400), (355, 428), (320, 438), (296, 428), (286, 400)]),
]
LABEL_AT = {'Parade Field': (468, 118), 'Hidden Hollow': (648, 165), 'Garden of the Senses': (232, 118),
            'Nickerson Field': (150, 228)}
EXTRA_DOORS = [   # lots, courtyard and Welcome Center: people walk straight across (PDF points)
    ('Courtyard', 'Welcome Center', (190, 344)), ('Elm Lot', 'Courtyard', (158, 345)),
    ('Oak Lot', 'Courtyard', (199, 371)), ('Birch Lot', 'Oak Lot', (285, 393)),
]
MODEL_TRAIN = oval(482, 196, 58, 24)       # future Model Train Garden: under construction in 2026
HOME = ['Welcome Center', 'Auto Gallery', 'Special Exhibitions', 'Carousel Gallery', 'Garden of the Senses',
        'Dexter Garden']

AMENITIES = [   # type, PDF point
    ('entrance', 186, 346),                                            # Ticketing Pavilion
    ('info', 206, 338), ('shop', 194, 330), ('restroom', 212, 330), ('water', 218, 337),     # Welcome Center
    ('restroom', 96, 245), ('water', 106, 247), ('elevator', 120, 236),                     # Automobile Gallery
    ('dining', 178, 187), ('restroom', 188, 185),                                           # Lilly's Café
    ('water', 236, 165),                                                                    # Garden of the Senses
    ('water', 493, 174),                                                                    # Parade Field
    ('restroom', 600, 146),                                                                 # Hidden Hollow
    ('restroom', 700, 229), ('water', 712, 226),                                            # Carousel Gallery
]
LABELS = [   # text, kind, PDF point
    ('Shawme Pond', 'area', 560, 25),
    ('Grove Street', 'note', 60, 270),
    ('Pine Street', 'note', 70, 345),
    ('MAIN ENTRANCE', 'area', 135, 380),
    ('To Route 6', 'note', 45, 318),
    ('Shawme Road', 'note', 600, 345),
    ('Pocasset Road', 'note', 190, 440),
    ('P', 'area', 120, 305), ('P', 'area', 240, 392), ('P', 'area', 325, 400),
    ('Overflow Lot and The Adventure Park (separate ticket) across Shawme Road', 'note', 420, 440),
    ('Future Model Train Garden (construction)', 'note', 482, 196),
    ('The Hundred Acre School', 'note', 730, 185),
    ('Administration (offices)', 'note', 303, 140),
    ('Nature trails', 'note', 340, 340),
]


def build_floors():
    lines, fills = read_map(svg())
    rooms, closed = [], []

    for bid, kind, label, name, (x, y), rx, ry in BUILDINGS:
        r = {'id': bid, 'kind': kind, 'name': name, 'poly': [P(*p) for p in oval(x, y, rx, ry)], 'z': 3}
        if label: r['label'] = label
        rooms.append(r)
    for (x, y), rx, ry in CLOSED_BUILDINGS:
        closed.append({'poly': [P(*p) for p in oval(x, y, rx, ry, 10)], 'z': 3})
    for pid, label, name, (x, y), rx, ry in PLACES:
        rooms.append({'id': pid, 'kind': 'gallery', 'label': label, 'name': name,
                      'poly': [P(*p) for p in oval(x, y, rx, ry, 14)], 'z': 2})

    used = set()
    for kind, pts in sorted(fills, key=lambda f: -area(f[1])):
        pg = simplify(pts, 2.5)
        if kind in AREAS and kind not in used:
            aid, rk, label, name = AREAS[kind]
            used.add(kind)
            r = {'id': aid, 'kind': rk, 'name': name, 'poly': [P(*p) for p in pg], 'z': 0 if rk == 'gallery' else 1}
            if label: r['label'] = label
            rooms.append(r)
        elif kind == 'lawn':
            c = centroid(pg)
            box = (min(p[0] for p in pg), min(p[1] for p in pg), max(p[0] for p in pg), max(p[1] for p in pg))
            hit = [l for l in LAWNS if box[0] <= l[3][0] <= box[2] and box[1] <= l[3][1] <= box[3]]
            if hit and box[1] < 360:
                lid, label, name, _ = hit[0]
                rooms.append({'id': lid, 'kind': 'gallery', 'label': label, 'name': name,
                              'poly': [P(*p) for p in pg], 'z': 0})
        elif kind in ('pond', 'adventure'):
            pg = [[x, max(y, 22)] for x, y in pg] if kind == 'pond' else pg
            if kind == 'adventure': continue          # below the map's edge on this page
            closed.append({'poly': [P(*p) for p in pg], 'z': 0})
    closed.append({'poly': [P(*p) for p in MODEL_TRAIN], 'z': 1})
    for lid, name, pg in LOTS:
        rooms.append({'id': lid, 'kind': 'space', 'name': name, 'poly': [P(*p) for p in pg], 'z': 1})

    # roads (public streets, not part of the walk): drawn like the grey areas
    for kind, pts in lines:
        if kind == 'road':
            closed.append({'poly': [P(*p) for p in band(simplify(pts, 3), 5)], 'z': 1})

    # walkable lines: paved paths, stairs and nature trails
    walks = []
    names = {'paved': 'Paved path', 'stairs': 'Stairs', 'trail': 'Nature trail'}
    half = {'paved': 1.8, 'stairs': 2.2, 'trail': 1.0}
    n = 0
    for kind, pts in lines:
        if kind == 'road': continue
        pts = simplify(pts, 1.5)
        if len(pts) < 2 or sum(math.dist(a, b) for a, b in zip(pts, pts[1:])) < 2: continue
        n += 1
        line = [P(*p) for p in pts]
        r = {'id': f'path-{n}', 'kind': 'corridor', 'name': names[kind], 'poly': band(line, half[kind] * K), 'z': 1}
        walks.append((r, line, kind))
        rooms.append(r)

    doors = []
    # paths meet where one's end touches another
    for r, line, kind in walks:
        for end in (line[0], line[-1]):
            best = None
            for r2, l2, _ in walks:
                if r2 is r: continue
                d, q = line_closest(end, l2)
                if best is None or d < best[0]: best = (d, q, r2)
            if best and best[0] < 6 * K:
                doors.append({'a': r['id'], 'b': best[2]['id'], 'at': [round(v, 1) for v in end], 'width': 8,
                              'axis': 'o'})
    # every place opens onto its nearest paved path (or trail, for the places out on the trails)
    for r in rooms:
        if r['kind'] == 'corridor': continue
        c = centroid(r['poly'])
        on_trail = r['id'] in ('Overlook', 'Concrete Distinction', 'Arbor Bowl', 'Mush8n')
        cands = [(w, l) for w, l, k in walks if (k == 'trail') == on_trail] or [(w, l) for w, l, k in walks]
        (d, q), wr = min(((line_closest(c, l), w) for w, l in cands), key=lambda t: t[0][0])
        doors.append({'a': wr['id'], 'b': r['id'], 'at': [round(q[0], 1), round(q[1], 1)], 'width': 8, 'axis': 'o'})
        if d > 45 * K: print(f'  note: {r["id"]} is {d / K * M_PER_PT:.0f} m from the nearest path')

    # a path that ends at (or inside) a building, place or lot opens into it
    for r in rooms:
        if r['kind'] == 'corridor' or r.get('z', 0) == 0: continue
        pg = [[x, y] for x, y in r['poly']]
        c = centroid(pg); big = [[c[0] + (x - c[0]) * 1.3, c[1] + (y - c[1]) * 1.3] for x, y in pg]
        for wr, line, kind in walks:
            for end in (line[0], line[-1]):
                if inside(end, big):
                    doors.append({'a': wr['id'], 'b': r['id'], 'at': [round(v, 1) for v in end], 'width': 8,
                                  'axis': 'o'})
    for a, b, (x, y) in EXTRA_DOORS:
        doors.append({'a': a, 'b': b, 'at': P(x, y), 'width': 8, 'axis': 'o'})
    for r in rooms:
        if r['id'] in LABEL_AT: r['labelAt'] = P(*LABEL_AT[r['id']])

    seen, uniq = set(), []
    for d in doors:
        k = (frozenset((d['a'], d['b'])), tuple(d['at']))
        if k not in seen: seen.add(k); uniq.append(d)
    doors = uniq

    # check that everything can be reached from the Welcome Center
    adj = {}
    for d in doors: adj.setdefault(d['a'], set()).add(d['b']); adj.setdefault(d['b'], set()).add(d['a'])
    reach, todo = {'Welcome Center'}, ['Welcome Center']
    while todo:
        for nb in adj.get(todo.pop(), ()):
            if nb not in reach: reach.add(nb); todo.append(nb)
    lost = [r['id'] for r in rooms if r['id'] not in reach]
    if lost: print(f'  note: {len(lost)} places not reachable from the Welcome Center: {lost[:12]}')

    floor = {'id': 'G', 'label': 'Grounds', 'order': 0,
             'area': 'The 100-acre grounds: Barbey Family Welcome Center · J.K. Lilly III Automobile Gallery · '
                     'Lilly’s Café · Special Exhibitions Gallery · American Art & Carousel Gallery · Old East Mill · '
                     'gardens · Hidden Hollow · nature trails',
             'transform': [1, 0, 0], 'walkScale': WALK, 'homeView': HOME,
             'rooms': rooms, 'closed': closed,
             'amenities': [{'type': t, 'at': P(x, y)} for t, x, y in AMENITIES],
             'labels': [{'text': t, 'kind': k, 'at': P(x, y)} for t, k, x, y in LABELS], 'doors': doors}
    return {'about': 'Built by tools/build_heritage.py from Heritage Museums & Gardens’ own 2026 visitor map, kept as '
                     'the museum prints it (north is up and to the left). Paths, nature trails, stairs, gardens, lawns '
                     'and parking are the map’s own shapes; the buildings are placed where the map draws them. The '
                     'map is an illustrated plan, not to an exact scale; inside the galleries there is no published '
                     'plan.',
            'source': SOURCE, 'units': f'PDF points of the visitor map x {K} (about {M_PER_PT / K:.1f} m each)',
            'defaultFloor': 'G', 'galleryWord': 'Place', 'floors': [floor]}


# ---- works ----------------------------------------------------------------------------------------------------
CREDIT = 'Heritage Museums & Gardens'
CARS_URL = SITE + '/exhibits/auto-2026/'
CRAN = SITE + '/exhibits/cranberries-2/'
REV = SITE + '/exhibits/remembering-the-revolution/'
CAROUSEL = SITE + '/museums/1908-looff-carousel/'
WETU = SITE + '/exhibits/wetu/'
MILL = SITE + '/windmill/'
U = CDN

# The 26 cars of From Carriage to Classic (April 25 – October 18, 2026), as listed on the exhibition page
ON_VIEW_CARS = [
    '1899 Winton Motor Carriage', '1904 Oldsmobile Runabout', '1908 Waltham-Orient Buckboard',
    '1909 White Steam Car Model M', '1910 Cadillac Model 30 Roadster', '1910 Peerless Model 27 Roadster',
    '1910 Sears Model P Surrey', '1912 Mercer Raceabout', '1912 Packard 1-48 Victoria', '1913 Ford Model T Touring',
    '1913 Pope-Hartford Model 33 Roadster', '1915 Ford Model T Roadster Pickup', '1916 Simplex Crane Model 5 Touring',
    '1917 Milburn Light Electric', '1919 Pierce-Arrow Model 48 Touring', '1922 Ford Model T Howe Pumper',
    '1924 Brewster Brougham', '1925 Franklin Sport Runabout', '1925 Rickenbacker 8 Coupe',
    '1930 Cadillac V-16 Convertible Coupe', '1930 Duesenberg Model J Derham Tourster',
    '1931 Ford Model A Deluxe Phaeton', '1932 Auburn Boattail Speedster', '1935 Ford Phaeton',
    '1936 Cord 810 Westchester', '1962 Chevrolet Corvette',
]

# (key, place, title, artist, date, medium, accession, image url, page, description, note)
ON_VIEW = [
    # Special Exhibitions Gallery: Cranberries: From Cape Cod to American Icon (April 25 – October 18, 2026)
    ('woman-scooping', 'Special Exhibitions', 'Woman Scooping Cranberries in Harwich', 'Unidentified creator',
     'early 20th century', 'Photograph', None, U + '2025/10/Woman-Scooping-in-Harwich.jpg', CRAN, None, None),
    ('fuller-hammond', 'Special Exhibitions', 'Group of Workers at Fuller Hammond Bog', 'Unidentified creator',
     'early 20th century', 'Photograph', None, U + '2025/10/Fuller-Hammond-Bog-Workers001.jpg', CRAN, None, None),
    ('cranberry-picker', 'Special Exhibitions', 'Cranberry Picker', 'Geraldine West Powell', 'about 1940–1955',
     'Painting', '2024.45.1203', U + '2025/10/2024.45.1203-1.jpg', CRAN,
     'A barefoot boy rests against a tree by a stone wall, above a wide landscape.', None),
    ('magic-sauce', 'Special Exhibitions', 'The Magic Sauce', 'Eatmor Cranberries', 'about 1920–1959',
     'Advertising poster', None, U + '2025/03/Cranberries-1.jpg', CRAN, None, None),
    ('ocean-spray-jug', 'Special Exhibitions', 'Ocean Spray Brand Cranberry Juice Cocktail', 'Cranberry Canners Inc.',
     'about 1931–1950', 'Glass jug with paper label', None, U + '2025/03/Cranberries-2.jpg', CRAN, None, None),
    ('makepeace-scoop', 'Special Exhibitions', 'Makepeace Cranberry Scoop', 'A.D. Makepeace Company', None,
     'Wood', None, U + '2025/03/Cranberries-10.jpg', CRAN,
     'A wooden harvesting scoop with two handles and wooden tines. The show lets you feel the weight of a real one.',
     None),
    ('fancy-box', 'Special Exhibitions', 'Fancy Cape Cod Cranberries 1 lb. Box', 'New England Cranberry Sales Co.',
     'late 19th – early 20th century', 'Printed cardboard', None, U + '2025/03/Cranberries-3.jpg', CRAN, None, None),
    ('thorobred-label', 'Special Exhibitions', 'Cape Cod Cranberries Thorobred Quarter Barrel Crate Label',
     'Stecher-Traung', 'early 20th century', 'Lithograph', None, U + '2025/03/Cranberries-7.png', CRAN, None, None),
    ('delicious-label', 'Special Exhibitions', 'Delicious Cape Cod Cranberries Quarter Barrel Crate Label',
     'Unidentified creator', 'early 20th century', 'Lithograph', None, U + '2025/03/Cranberries-5.jpeg', CRAN, None,
     None),
    ('harvest-queen-label', 'Special Exhibitions', 'Harvest Queen Cape Cod Cranberries Quarter Barrel Crate Label',
     'Unidentified creator', 'early 20th century', 'Lithograph', None, U + '2025/03/Cranberries-6.png', CRAN, None,
     None),
    ('eatmor-box', 'Special Exhibitions', 'Eatmor Cape Cod Cranberries Quarter Barrel Box', 'Unidentified creator',
     'late 19th – early 20th century', 'Wood and paper', None, U + '2025/03/Cranberries-8.jpg', CRAN, None, None),
    # American Art & Carousel Gallery: the 1908 Looff Carousel and Remembering the Revolution
    ('looff-carousel', 'Carousel Gallery', 'The 1908 Looff Carousel', 'Charles I.D. Looff (1852–1918)', '1908',
     'Carved and painted wood, glass eyes, horsehair tails', None, U + '2021/02/carousel-horses-2-e1613429420458.jpg',
     CAROUSEL,
     'Made in Riverside, Rhode Island, for an amusement park in Mississippi; the oldest horses were carved in the '
     '1880s. J.K. Lilly III had this gallery built to look like a circus tent, and the carousel has run here since '
     '1972. Rides are unlimited with admission.', None),
    ('lead-horse', 'Carousel Gallery', 'Lead horse (Thunder)', 'Charles I.D. Looff', 'about 1908',
     'Carved and painted wood', None, U + '2021/07/lead4-scaled-e1626989746399.jpg', CAROUSEL,
     'The horse with the fanciest carved trappings, which helped the operator count the turns. Restored in 2021.',
     None),
    ('chariot', 'Carousel Gallery', 'Carousel chariot', 'Probably Charles Looff Jr.', 'about 1908',
     'Carved and painted wood', None, U + '2021/02/looff_1912_chariot.jpg', CAROUSEL,
     'A riding bench carved with a green dragon, for riders who would rather not sit on an animal.', None),
    ('goat', 'Carousel Gallery', 'Carousel goat', 'Charles I.D. Looff', 'about 1908', 'Carved and painted wood',
     None, U + '2023/01/Goat2.jpg', CAROUSEL,
     'The only “prancer” on the carousel (two feet on the ground) and its one menagerie animal.', None),
    ('band-organ', 'Carousel Gallery', 'Band organ', None, None, 'Wood, organ pipes, painted panel', None,
     U + '2023/01/Band-Organ.jpg', CAROUSEL,
     'A self-playing organ that once made the carousel’s music from punched paper rolls; it is now for display.',
     None),
    ('peace-plenty-jug', 'Carousel Gallery', '“Peace, Plenty, and Independence” Jug', None, 'about 1810',
     'Ceramic', None, U + '2026/03/Peace-Plenty-and-Independence-Jug.png', REV, None,
     'Remembering the Revolution (April 25 – October 18, 2026).'),
    ('revere-wine-cann', 'Carousel Gallery', 'Wine Cann', 'Paul Revere (1735–1818)', 'about 1775–1795', 'Silver',
     None, U + '2026/03/Paul-Revere-Wine-Cann.png', REV, None,
     'Remembering the Revolution. Photo © 2015 Lance Keimig Photographics.'),
    ('valley-forge', 'Carousel Gallery', 'Winter at Valley Forge (diorama)', None, 'about 1960',
     'Military miniatures', None, U + '2026/03/Winter-at-Valley-Forge.jpg', REV, None, 'Remembering the Revolution.'),
    ('yorktown', 'Carousel Gallery', 'The British surrender at Yorktown (diorama)', None, None,
     'Military miniatures', None, None, REV,
     'A 24-square-foot diorama, shown with nine regiments of military miniatures.', 'Remembering the Revolution.'),
    # Outdoors
    ('old-east-mill', 'Old East Mill', 'Old East Mill', 'Built in Orleans, Massachusetts', '1800',
     'Windmill (wood); vanes rebuilt by millwright Andrew Shrake in 2019', None, U + '2021/04/windmill4.jpg', MILL,
     'Built from leftover timber of the Orleans meeting house, it ground grain (and, from 1834, salt) until 1893. '
     'J.K. Lilly III had it moved here by truck in 1967: the ten-day trip needed every power line lifted by hand.',
     None),
    ('wetu', 'Wetu', 'Wetu (Wampanoag house)', 'SmokeSygnals (Mashpee Wampanoag)', '2021',
     'Cedar saplings, bark and mats; mats painted by Robert Peters', None,
     U + '2022/02/WETU_Exterior-View_photo-by-Kristyn-Mills.jpg', WETU,
     'A full-size reproduction of a Wampanoag summer house, built by members of the Mashpee Wampanoag Tribe with '
     'centuries-old methods; beside it, a Three Sisters-style garden of corn, squash and beans.',
     'Photo: Kristyn Mills.'),
    ('mush8n', 'Mush8n', 'Mush8n (dugout canoe)', 'SmokeSygnals (Mashpee Wampanoag)', '2023', 'White pine, burned '
     'and carved', None, U + '2023/01/Mish8n-768x1024.jpeg', WETU,
     'A 12-foot Wampanoag boat (pronounced mish-oon) made by burning and carving out a pine trunk. You can climb in.',
     'On the far side of the Parade Field, toward Shawme Pond.'),
    ('concrete-distinction', 'Concrete Distinction', 'Concrete Distinction', 'Marybeth Lensel', '2003, renewed 2023',
     'Site-specific installation', None, U + '2023/03/7-concretedistinction-detail.jpg',
     SITE + '/concrete-distinction/', None, 'In the woods along the nature trails behind the Arbor Bowl.'),
    # the gardens
    ('garden-of-senses', 'Garden of the Senses', 'The McGraw Family Garden of the Senses', None, None, 'Garden', None,
     U + '2021/01/800px02022021_000027.jpeg', SITE + '/hmg/mcgraw-family-garden-of-the-senses/',
     'An accessible garden for all the senses, with a boardwalk, water features and the 225-year-old windmill.', None),
    ('dexter-garden', 'Dexter Garden', 'Dexter Rhododendron Garden', 'Charles O. Dexter (hybridizer)', None, 'Garden',
     None, U + '2021/01/800x533rhodie.jpg', SITE + '/hmg/dexter-rhododendron-garden/',
     'Two acres of rhododendrons bred by Charles O. Dexter, who lived on this land from 1921 to 1943. Best in late '
     'May and early June.', None),
    ('hydrangea-display', 'Hydrangea Garden', 'Cape Cod Hydrangea Society Display Garden', None, None, 'Garden', None,
     U + '2021/01/800px02022021_001159.jpeg', SITE + '/hmg/cape-cod-hydrangea-display-garden/',
     'Hydrangeas at their best in July, when Heritage holds the Cape Cod Hydrangea Festival.', None),
    ('hydrangea-test', 'Hydrangea Test Garden', 'North American Hydrangea Test Garden', None, None, 'Garden', None,
     U + '2021/01/800xnahtg.jpg', SITE + '/hmg/north-american-hydrangea-test-garden/',
     'New hydrangea varieties tested side by side for how they grow and bloom on Cape Cod.', None),
    ('flume', 'Flume', 'The Flume and the Donald Marvin Daylily Garden', None, None, 'Fountain and garden', None,
     U + '2021/01/800xflume.jpg', SITE + '/hmg/the-flume/',
     'A water feature inspired by old gristmills: a narrow pool plunges 26 feet into a pool of aquatic plants.', None),
    ('mcinnes', 'McInnes Garden', 'McInnes Garden & Garden Gate', None, None, 'Garden', None,
     U + '2025/03/2021_McInnesGarden_PHOTOS_HMG_IrisClearwater-1.jpeg', SITE + '/hmg/mcinnes-garden/', None,
     'Photo: Iris Clearwater.'),
    ('herb-garden', 'Herb Garden', 'Herb Garden', None, None, 'Garden', None, U + '2021/02/800px02022021_000747.jpeg',
     SITE + '/hmg/herb-garden/', None, None),
]

# Heritage collection works shown in past years (museum page only; not on the map)
PAST = [
    # key, title, artist, date, medium, accession, image, page
    ('nantucket-basket', 'Nantucket basket (from the Medaugh collection)', 'Nantucket basket maker', None,
     'Woven rattan and wood', None, U + '2026/09/Basket2.jpg', SITE + '/nantucket-baskets/'),
    ('baxter-trade-sign', 'Pocket Watch Trade Sign of John Baxter', None, '19th century', 'Painted wood',
     '2023.5.1', U + '2024/01/2023.5.1-Baxter-Watch-Trade-Sign-Side-1-scaled.jpg', SITE + '/baxter-trade-sign/'),
    ('america-ii', 'America II (model ship)', None, None, 'Ship model', '1972.5.1',
     U + '2023/08/1972.5.1-America-II_1.jpg', SITE + '/america-ii/'),
    ('central-park-winter', 'Central Park, Winter: The Skating Pond', 'Currier & Ives', '1862',
     'Hand-colored lithograph', '1977.1.1', U + '2022/12/1977.1.1-reduced.jpg',
     SITE + '/america-through-the-eyes-of-currier-ives/'),
    ('falmouth-harbor', 'Falmouth Harbor', 'Frank Vining Smith (1879–1967)', '1950–1954', 'Oil on canvas',
     '1972.2.1', U + '2022/04/Frank-Vining-Smith_Falmouth-Harbor_1950-54_1972.2.1.jpg', SITE + '/frank-vining-smith/'),
    ('chatham-bars', 'Chatham Bars', 'Frank Vining Smith (1879–1967)', None, 'Oil on canvas', '1972.2.8',
     U + '2021/07/1972.2.8-Chatham-Bars.jpg', SITE + '/frank-vining-smith/'),
    ('yellowlegs', 'Yellowlegs', 'A. Elmer Crowell (1862–1952)', 'about 1920–1950', 'Carved and painted wood', None,
     U + '2022/04/Yellowlegs_A.E.-Crowell-circa-1920-1950.jpg', SITE + '/the-carver-behind-the-birds/'),
    ('sailors-picnic', 'Sailors’ Picnic Today', 'Ralph Cahoon (1910–1982)', None, 'Oil on board', None,
     U + '2022/08/Ralph-Cahoon_Sailors-Picnic-Today-scaled.jpg', REV),
    ('cranberry-flakes', 'Cranberry flakes (Army ration can)', 'Ocean Spray', 'about 1943', 'Tin can, printed label',
     None, U + '2025/11/Ocean-Spray-Can.jpg', SITE + '/wwii-cranberberries/'),
    ('uss-augusta-menu', 'U.S.S. Augusta Thanksgiving menu', None, '1942', 'Printed paper', None,
     U + '2025/11/USS-August-Thanksgiving-Menu.jpeg', SITE + '/wwii-cranberberries/'),
]


def cars():
    """Every car page of the collection (the museum's portfolio items), with photo and specifications."""
    d = json.loads(get(SITE + '/wp-json/wp/v2/avada_portfolio?per_page=100&_embed=wp:featuredmedia',
                       'portfolio.json'))
    out = {}
    for p in d:
        title = html.unescape(p['title']['rendered']).strip()
        if not re.match(r'^(18|19)\d\d ', title): continue
        body = text(p['content']['rendered'])
        body = body[len(title):].strip() if body.startswith(title) else body
        spec = {}
        for k in ('MANUFACTURER', 'PRICE NEW', 'ENGINE', 'HORSEPOWER'):
            m = re.search(k + r':\s*(.+?)\s*(?=MANUFACTURER:|PRICE NEW:|AVERAGE ANNUAL|PRICE TO BUY|ENGINE:|HORSEPOWER:|'
                              r'Sorry, your|Currently|In Collection|Not Currently|From Carriage|$)', body)
            if m: spec[k] = m[1].strip(' :')
        desc = re.split(r'\s(?:MANUFACTURER:|Generous gift|Gift of)', body)[0].strip()
        sentences = re.findall(r'[^.!?]+[.!?”"]+', desc)
        short = ''
        for s in sentences:
            if len(short) + len(s) > 520 and short: break
            short += s
        media = (p.get('_embedded', {}).get('wp:featuredmedia') or [{}])[0]
        sizes = media.get('media_details', {}).get('sizes', {})
        img = [sizes[k]['source_url'] for k in ('large', '1200', 'medium_large', '1024') if k in sizes][:1]
        img = [u for u in img + [media.get('source_url')] if u]        # the full picture if the smaller copy is gone
        out[title] = {'url': p['link'], 'desc': short.strip() or None, 'spec': spec, 'image': img}
    return out


def picture(key, url):
    """Download once (politely) and save a phone-sized JPEG; returns the app path."""
    if isinstance(url, list):
        for u in url:
            got = picture(key, u)
            if got: return got
        return None
    if not url: return None
    raw = CACHE / 'img' / (key + (Path(urllib.parse.urlparse(url).path).suffix.lower() or '.jpg'))
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
        time.sleep(1.5)
        if not out:
            print(f'  no picture: {url}')
            return None
        raw.write_bytes(out)
    dest = OUT / 'images' / f'{key}.jpg'
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            im = Image.open(io.BytesIO(raw.read_bytes()))
        except Exception:
            raw.unlink()
            return None
        if im.mode in ('RGBA', 'LA', 'P'):
            im = im.convert('RGBA'); bg = Image.new('RGB', im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[3])
            im = bg
        im = im.convert('RGB')
        im.thumbnail((1000, 1000))
        im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/heritage/images/{key}.jpg'


def year_of(date):
    m = re.search(r'(\d{4})', date or '')
    return int(m[1]) if m else None


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def car_row(title, c):
    spec = c['spec']
    make = spec.get('MANUFACTURER')
    medium = '; '.join(v for v in (spec.get('ENGINE') and f'Engine: {spec["ENGINE"]}',
                                   spec.get('HORSEPOWER') and f'{spec["HORSEPOWER"]} horsepower') if v) or 'Automobile'
    note = f'Price new: {spec["PRICE NEW"]}.' if spec.get('PRICE NEW') else None
    return {'title': title, 'artist': make or 'Automobile', 'date': title[:4], 'medium': medium, 'desc': c['desc'],
            'note': note, 'url': c['url'], 'image': c['image']}


def build_works(floors):
    rooms = {r['id']: r for r in floors['floors'][0]['rooms']}
    allcars = cars()
    out = []

    def add(key, room, title, artist, date, medium, acc, img, url, desc, note, exhibition=None, credit=None):
        k = f'heritage-{key}'
        a = {'id': k, 'title': title, 'artist': artist or 'Unknown maker', 'date': date, 'year': year_of(date),
             'medium': medium, 'accession': acc, 'creditLine': CREDIT, 'gallery': room,
             'galleryName': rooms[room]['name'], 'floor': 'G', 'placeNote': note, 'description': desc,
             'exhibition': exhibition, 'url': url, 'image': picture(k, img),
             'imageCredit': (credit or 'Heritage Museums & Gardens') if img else None}
        out.append({k2: v for k2, v in a.items() if v not in (None, '')})

    for title in ON_VIEW_CARS:
        c = allcars.get(title)
        if not c: raise SystemExit(f'car page not found: {title}')
        r = car_row(title, c)
        add(slug(title), 'Auto Gallery', title, r['artist'], r['date'], r['medium'], None, r['image'], r['url'],
            r['desc'], r['note'], 'From Carriage to Classic: How Automobiles Transformed America '
                                  '(April 25 – October 18, 2026)')
    for key, room, title, artist, date, medium, acc, img, url, desc, note in ON_VIEW:
        exhibition = ('Cranberries: From Cape Cod to American Icon (April 25 – October 18, 2026)' if url == CRAN else
                      'Remembering the Revolution (April 25 – October 18, 2026)' if url == REV else None)
        add(key, room, title, artist, date, medium, acc, img, url, desc, note, exhibition)
    return {'source': 'heritagemuseumsandgardens.org car, exhibition, garden and blog pages', 'checked':
            time.strftime('%Y-%m-%d'), 'count': len(out), 'complete': False, 'artworks': out}, allcars


def build_guide(works, allcars):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'),
                     'year': a.get('year'), 'medium': a.get('medium'), 'accession': a.get('accession'), 'url': a['url'],
                     'imageUrl': a.get('image'), 'onView': True, 'gallery': a['gallery'], 'floor': 'G'}.items()
                     if v not in (None, '')})
    for title, c in sorted(allcars.items()):
        if title in ON_VIEW_CARS: continue
        r = car_row(title, c)
        k = f'heritage-{slug(title)}'
        rows.append({k2: v for k2, v in {'id': k, 'title': title, 'artist': r['artist'], 'date': r['date'],
                     'year': year_of(r['date']), 'medium': r['medium'], 'url': r['url'],
                     'imageUrl': picture(k, r['image']), 'onView': False}.items() if v not in (None, '')})
    for key, title, artist, date, medium, acc, img, url in PAST:
        k = f'heritage-{key}'
        rows.append({k2: v for k2, v in {'id': k, 'title': title, 'artist': artist or 'Unknown maker', 'date': date,
                     'year': year_of(date), 'medium': medium, 'accession': acc, 'url': url,
                     'imageUrl': picture(k, img), 'onView': False}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': 'Heritage Museums & Gardens', 'checked': time.strftime('%Y-%m-%d'),
            'source': 'Heritage Museums & Gardens visitor map, car, exhibition and blog pages', 'onViewKnown': True,
            'note': 'Heritage has over 18,000 objects (antique cars, American folk art, Currier & Ives prints, '
                    'military miniatures, carousel figures and the new cranberry and Nantucket basket collections), '
                    'but its collection is not online. Listed here: what the galleries showed in the 2026 season '
                    '(April 25 – October 18), the outdoor exhibits and gardens, the cars in storage and a few '
                    'collection works from the museum’s blog. The galleries are closed until the 2027 season; '
                    'Gardens Aglow (holiday lights) runs on evenings from November 27 to December 27, 2026.',
            'works': rows}


def main():
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works, allcars = build_works(floors)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works, allcars)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': sum(w['onView'] for w in guide['works']), 'galleries': True,
                              'checked': guide['checked'],
                              'source': 'Heritage Museums & Gardens: 2026 visitor map, car and exhibition pages '
                                        '(heritagemuseumsandgardens.org)'}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    f = floors['floors'][0]
    print(f'map: {len(f["rooms"])} rooms ({sum(r["kind"] == "corridor" for r in f["rooms"])} paths), '
          f'{len(f["doors"])} doors, {len(f["closed"])} closed')
    print(f'{works["count"]} works on view, {sum("image" in a for a in works["artworks"])} with pictures; '
          f'museum page {len(guide["works"])} ({sum(bool(w.get("imageUrl")) for w in guide["works"])} pictures)')


if __name__ == '__main__':
    sys.exit(main())
