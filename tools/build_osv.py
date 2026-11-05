#!/usr/bin/env python3
"""Build the Old Sturbridge Village (Sturbridge, MA) map guide (run: python3 tools/build_osv.py).

    data/osv/floors.json      the Village seen from above: every building, garden, path and amenity (a flat 2D plan)
    data/osv/artworks.json    the historic buildings, gardens and exhibits, and the collection highlights we can place
    data/osv/images/          their pictures, made smaller for phones
    data/guides/Q7085141.json the same list for the museum page, plus collection highlights we can't place

The map: Old Sturbridge Village's own 2026 Map Guide (osv.org/content/uploads/2026/06/
25_0182_OSV_Mapguide-April-Nov-2026-FINAL-52726_nobleed-1.pdf, linked from osv.org/visit) is a painted bird's-eye
view seen from the south-east, not to scale, so the shapes come from OpenStreetMap instead (cached in
.cache/osv/osm.xml), where volunteers have traced every building of the Village, its paths and the Mill Pond, true to
scale and north up. The Map Guide says which building is which: its numbers (1 Ox & Yoke ... 46 River Walk) are kept,
and its restrooms, food, water fountains and first aid are placed where it puts them. One map unit is 0.35 m, the
size the app's walking times assume.

Some buildings have other names on OpenStreetMap; the Map Guide places them where these stand:
the "Parsonage" is the Richardson House (12) and the "Parsonage Barn" next to the Bullard Tavern is the Gebhardt Barn
(13; the Village's page "Richardson House & Gebhart Performance Barn" says the house was "previously known as the
Parsonage"), the "New England Changing Landscape" building by the Covered Bridge is the Countryside Gallery (38)
and the "Hands-on Crafts Center" by the Herb Garden is the David Wight Community Gallery (28).

The works: the Village's own pages for each building (osv.org/building/...) and its 62 collection highlights
(osv.org/collection/...), read once by tools/harvest_osv.py. Buildings are placed on their footprint; collection
highlights are placed only where the object belongs to a building (the carding machine in the Carding Mill, the
clocks in the J. Cheney Wells Clock Gallery...). The rest are listed on the museum page without a place.
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
OUT = ROOT / 'data' / 'osv'
CACHE = ROOT / '.cache' / 'osv'
MUSEUM = 'Q7085141'
SITE = 'https://www.osv.org'
MAP_PDF = SITE + '/content/uploads/2026/06/25_0182_OSV_Mapguide-April-Nov-2026-FINAL-52726_nobleed-1.pdf'
OSM_URL = 'https://www.openstreetmap.org/api/0.6/map?bbox=-72.1080,42.1030,-72.0920,42.1150'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SOURCE = ('OpenStreetMap (buildings, paths, Mill Pond) and Old Sturbridge Village’s 2026 Map Guide '
          '(building numbers and amenities; osv.org/visit)')

U = 0.35                                    # metres per map unit
LAT0, LON0 = 42.1095, -72.1015              # top-left corner of the map
LAT1, LON1 = 42.1025, -72.0915              # bottom-right corner
KX = 111320 * math.cos(math.radians(42.106)) / U
KY = 110950 / U


def xy(lat, lon):
    return [round((lon - LON0) * KX, 1), round((LAT0 - lat) * KY, 1)]


def in_box(lat, lon):
    return LAT1 <= lat <= LAT0 and LON0 <= lon <= LON1


def osm():
    f = CACHE / 'osm.xml'
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(['curl', '-s', '-f', '-m', '180', '-A', UA, OSM_URL], capture_output=True).stdout
        if not out: raise SystemExit('OpenStreetMap did not answer')
        f.write_bytes(out)
    t = ET.parse(f).getroot()
    nodes, ntags = {}, {}
    for n in t.iter('node'):
        nodes[n.get('id')] = (float(n.get('lat')), float(n.get('lon')))
        tags = {k.get('k'): k.get('v') for k in n.iter('tag')}
        if tags: ntags[n.get('id')] = tags
    ways = {}
    for w in t.iter('way'):
        ways[w.get('id')] = {'nodes': [nd.get('ref') for nd in w.iter('nd')],
                             'tags': {k.get('k'): k.get('v') for k in w.iter('tag')}}
    return nodes, ntags, ways


# ---- geometry ------------------------------------------------------------------------------------------------
def centroid(pg):
    return [sum(p[0] for p in pg) / len(pg), sum(p[1] for p in pg) / len(pg)]


def seg_closest(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return [ax + t * dx, ay + t * dy]


def line_closest(p, line):
    """The point of a polyline closest to p, and how far it is."""
    best = None
    for a, b in zip(line, line[1:]):
        q = seg_closest(p, a, b)
        d = math.dist(p, q)
        if best is None or d < best[0]: best = (d, q)
    return best


def edge_point(pg, toward):
    best = None
    for a, b in zip(pg, pg[1:] + pg[:1]):
        q = seg_closest(toward, a, b)
        d = math.dist(q, toward)
        if best is None or d < best[0]: best = (d, q)
    return [round(best[1][0], 1), round(best[1][1], 1)]


def poly_line_gap(pg, line):
    """Shortest distance between a polygon's outline and a polyline: (distance, point on the polygon)."""
    best = None
    for p in pg:
        d, _ = line_closest(p, line)
        if best is None or d < best[0]: best = (d, p)
    for q in line:
        e = edge_point(pg, q)
        d = math.dist(e, q)
        if d < best[0]: best = (d, e)
    return best


def clip_box(pg, x0, y0, x1, y1):
    """Cut a polygon to a rectangle (Sutherland-Hodgman)."""
    def cut(pts, inside, meet):
        out = []
        for i, cur in enumerate(pts):
            prev = pts[i - 1]
            if inside(cur):
                if not inside(prev): out.append(meet(prev, cur))
                out.append(cur)
            elif inside(prev): out.append(meet(prev, cur))
        return out

    def at_x(x):
        return lambda a, b: [x, round(a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0]), 1)]

    def at_y(y):
        return lambda a, b: [round(a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]), 1), y]
    for inside, meet in ((lambda p: p[0] >= x0, at_x(x0)), (lambda p: p[0] <= x1, at_x(x1)),
                         (lambda p: p[1] >= y0, at_y(y0)), (lambda p: p[1] <= y1, at_y(y1))):
        if pg: pg = cut(pg, inside, meet)
    return pg


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
    """The point a fraction of the way along a polyline."""
    total = sum(math.dist(a, b) for a, b in zip(line, line[1:]))
    goal, run = total * frac, 0
    for a, b in zip(line, line[1:]):
        d = math.dist(a, b)
        if run + d >= goal and d:
            t = (goal - run) / d
            return [round(a[0] + t * (b[0] - a[0]), 1), round(a[1] + t * (b[1] - a[1]), 1)]
        run += d
    return line[-1]


def length(line):
    return sum(math.dist(a, b) for a, b in zip(line, line[1:]))


# ---- the places --------------------------------------------------------------------------------------------
G, S = 'gallery', 'space'
# (Map Guide number or None, id, kind, short label, name, OpenStreetMap ways)
PLACES = [
    (1, 'Ox & Yoke', S, None, 'Ox & Yoke Mercantile and Café (store and café, restrooms)', ['216282304']),
    (2, 'Visitor Center', G, 'Visitor Center',
     'Country Bank Visitor Center: tickets, J. Cheney Wells Clock Gallery, American Reflections, Kidstory, '
     'Brewer Theater, restrooms', ['216282303']),
    (3, 'Bullard Tavern', G, 'Bullard Tavern', 'Bullard Tavern: Bullard Cafeteria and Exhibition Gallery, restrooms',
     ['216282210']),
    (4, 'Small House', G, 'Small House', 'Small House', ['216282339']),
    (None, 'Small House Garden', G, 'Small House Garden', '4 · Small House Garden', ['1412399142']),
    (5, 'Friends Meetinghouse', G, 'Friends Meetinghouse', 'Friends Meetinghouse', ['216282370']),
    (6, 'Center Meetinghouse', G, 'Center Meetinghouse', 'Center Meetinghouse', ['216282358']),
    (7, 'Cabinetmaking Shop', G, 'Cabinetmaking', 'Cabinetmaking Shop', ['1389208028']),
    (8, 'Town Pound', G, 'Town Pound', 'Town Pound', ['280175758']),
    (9, 'Shoe Shop', G, 'Shoe Shop', 'Shoe Shop', ['216282318']),
    (10, 'Asa Knight Store', G, 'Asa Knight Store', 'Asa Knight Store', ['216282331']),
    (11, 'Law Office', G, 'Law Office', 'Law Office', ['280175639']),
    (12, 'Richardson House', G, 'Richardson House', 'Richardson House and Garden (the Parsonage)', ['216282290']),
    (13, 'Gebhardt Barn', S, None, 'Gebhardt Barn (performances)', ['216282263']),
    (14, 'Tin Shop', G, 'Tin Shop', 'Tin Shop', ['216282235']),
    (15, 'Salem Towne House', G, 'Salem Towne House', 'Salem Towne House, Barn, and Garden', ['216282193']),
    (None, 'Towne Barn', G, 'Towne Barn', '15 · Salem Towne Barn', ['216282203']),
    (16, 'Cider Mill', G, 'Cider Mill', 'Cider Mill and Orchard (seasonal)', ['216282218']),
    (17, 'Printing Office', G, 'Printing Office', 'Printing Office', ['280176047']),
    (18, 'Miner Grant Store', S, None, 'Miner Grant Store & Bake Shop (cookies, drinks, gifts)', ['216282259']),
    (19, 'Thompson Bank', G, 'Thompson Bank', 'Thompson Bank', ['216282274']),
    (20, 'Fitch House', G, 'Fitch House', 'Fitch House and Garden', ['216282308']),
    (21, 'Fitch Barn', G, 'Fitch Barn', 'Fitch Barn: 19th-century farm tools', ['216282288']),
    (22, 'Fenno House', G, 'Fenno House', 'Fenno House (spinning, weaving and dyeing)', ['216282330']),
    (None, 'Fenno Barn', S, None, '22 · Fenno Barn', ['216282343']),
    (23, 'Glasshouse Gallery', G, 'Glasshouse Gallery', 'Glasshouse Gallery', ['216282279']),
    (24, 'Village Scoop Shop', S, None, 'Village Scoop Shop (ice cream, seasonal)', ['216282271']),
    (25, 'Armed & Equipped', G, 'Armed & Equipped', 'Armed & Equipped Militia Exhibit', ['216282234']),
    (26, 'Playground', S, None, 'Playground', ['1082938186']),
    (27, 'Dennison Building', G, 'Dennison Building', 'Dennison Building: textiles from the collection',
     ['216282199']),
    (28, 'David Wight Gallery', G, 'David Wight Gallery', 'David Wight Community Gallery', ['216282233']),
    (29, 'Beekeeping Exhibit', G, 'Beekeeping', 'Beekeeping Exhibit (seasonal)', ['216282215']),
    (None, 'Early Lighting Exhibit', G, 'Early Lighting', 'Early Lighting Exhibit', ['216282217']),
    (30, 'Herb Garden', G, 'Herb Garden', 'Herb Garden (seasonal)', ['280176048']),
    (31, 'District School', G, 'District School', 'District School', ['216282252']),
    (32, 'Pottery Shop', G, 'Pottery Shop', 'Pottery Shop and Kiln', ['216282214']),
    (33, 'Allen Piggery', G, 'Allen Piggery', 'Allen Piggery', ['1412399129']),
    (34, 'Freeman Farmhouse', G, 'Freeman Farm', 'Freeman Farm: the farmhouse', ['216282144']),
    (None, 'Freeman Barn', G, 'Freeman Barn', '34 · Freeman Farm: the barn and animals', ['216282134']),
    (None, 'Freeman Garden', G, 'Freeman Garden', '34 · Freeman Farm kitchen garden', ['1412399236']),
    (35, 'Cooper Shop', G, 'Cooper Shop', 'Cooper Shop', ['216282094']),
    (36, 'Bixby House', G, 'Bixby House', 'Bixby House and Garden', ['216282108']),
    (None, 'Bixby Garden', S, None, '36 · Bixby House garden', ['1412399131']),
    (37, 'Blacksmith Shop', G, 'Blacksmith', 'Blacksmith Shop', ['216282050']),
    (38, 'Countryside Gallery', G, 'Countryside Gallery', 'Countryside Gallery, restrooms', ['216282070']),
    (39, 'Carding Mill', G, 'Carding Mill', 'Carding Mill', ['216282023']),
    (40, 'Gristmill', G, 'Gristmill', 'Gristmill', ['216281979']),
    (41, 'Sawmill', G, 'Sawmill', 'Sawmill', ['216281968']),
    (42, 'Covered Bridge', G, 'Covered Bridge', 'Vermont Covered Bridge', ['240631873']),
    (44, 'Goods from the Woods', G, 'Goods from the Woods', 'Goods from the Woods', ['1412399136']),
    ('C', 'Village Common', S, None, 'Village Common', ['280176430']),
    (None, 'Horsesheds', S, None, 'Horse sheds by the Center Meetinghouse', ['216282381']),
    (None, 'Fuller Conference Center', S, None, 'Fuller Conference Center (events)', ['216282309']),
    (None, 'First Aid', S, None, 'First Aid and Security', ['216282441']),
    ('ED', 'Museum Education Center', S, None, 'Museum Education Center: Studios (classes), across the river',
     ['216281783']),
    ('L', 'Lunchroom', S, None, 'Museum Education Center Lunchroom', ['216281793']),
    (None, 'Mill Pond', S, None, 'Mill Pond (below the Covered Bridge)', ['129105587']),
    (None, 'Mill Pond North', S, None, 'Mill Pond (above the Covered Bridge)', ['129105588']),
]
# A place's door goes to the nearest path; these pick the path by a point near their real door instead.
DOOR_NEAR = {
    'Visitor Center': (42.1080791, -72.0982841),     # the Village side of the Visitor Center
    'Ox & Yoke': (42.1085, -72.0979),
}
NO_DOOR = {'Mill Pond', 'Mill Pond North'}

# Amenities from the Map Guide, at OpenStreetMap nodes or inside the building that has them.
AMENITIES = [
    ('entrance', 'node', '2483524776'),                                 # Visitor Center main door
    ('info', 'node', '12875804435'),                                    # ticket desk
    ('restroom', 'place', 'Visitor Center'), ('restroom', 'place', 'Ox & Yoke'),
    ('restroom', 'place', 'Bullard Tavern'), ('restroom', 'node', '14106504098'),
    ('dining', 'node', '12869592159'), ('dining', 'node', '14170990907'),
    ('dining', 'place', 'Miner Grant Store'), ('dining', 'place', 'Village Scoop Shop'),
    ('shop', 'node', '12869592160'), ('shop', 'place', 'Miner Grant Store'),
    ('water', 'place', 'Ox & Yoke'), ('water', 'place', 'Bullard Tavern'), ('water', 'node', '14156473231'),
    ('emergency', 'place', 'First Aid'),
]
LABELS = [
    ('Mill Pond', 'area', 42.1059, -72.0950), ('Mill Pond', 'area', 42.1072, -72.0945),
    ('Center Village', 'area', 42.1072, -72.0985), ('Countryside', 'area', 42.1043, -72.0975),
    ('Parking', 'note', 42.1088, -72.1003), ('Parking', 'note', 42.1066, -72.0918),
    ('Picnic tables in the Grove', 'note', 42.10605, -72.0975),
    ('Picnic tables by the Covered Bridge', 'note', 42.10592, -72.0952),
    ('Walk to the Museum Education Center', 'note', 42.1051, -72.0935),
    ('Woodland Walk (43) and Pasture Walk (45) start here', 'note', 42.1062, -72.1007),
    ('River Walk (46)', 'note', 42.1048, -72.0945),
]

WALK_KINDS = {'footway': 6, 'path': 6, 'pedestrian': 8, 'service': 9, 'track': 6}


def walk_network(nodes, ways):
    """The Village's paths and dirt roads from OpenStreetMap, cut at every crossing into short pieces."""
    picked = {}
    for wid, w in ways.items():
        hw = w['tags'].get('highway')
        if hw not in WALK_KINDS or w['tags'].get('access') == 'private': continue
        pts = [n for n in w['nodes'] if n in nodes]
        inside = [n for n in pts if in_box(*nodes[n])]
        if len(inside) < 2: continue
        # keep the longest run of nodes inside the box
        runs, run = [], []
        for n in pts:
            if in_box(*nodes[n]): run.append(n)
            else:
                if len(run) > 1: runs.append(run)
                run = []
        if len(run) > 1: runs.append(run)
        for i, r in enumerate(runs):
            picked[f'{wid}.{i}'] = (r, w['tags'])
    use = {}
    for key, (r, _) in picked.items():
        for i, n in enumerate(r):
            use[n] = use.get(n, 0) + (1 if i in (0, len(r) - 1) else 2)
    pieces = []
    for key, (r, tags) in picked.items():
        cur = [r[0]]
        for n in r[1:]:
            cur.append(n)
            if use[n] > 2 and n != r[-1] or len(cur) > 1 and length([xy(*nodes[m]) for m in cur]) > 220:
                pieces.append((cur, tags)); cur = [n]
        if len(cur) > 1: pieces.append((cur, tags))
    return pieces


def walk_name(tags, line, places):
    if tags.get('name'): return tags['name']
    mid = along(line)
    near = min(places, key=lambda p: math.dist(mid, p['c']))
    kind = {'service': 'Village road', 'pedestrian': 'Village road'}.get(tags.get('highway'), 'Path')
    if tags.get('surface') in ('sand', 'dirt'): kind = 'Dirt road' if kind == 'Village road' else 'Dirt path'
    return f'{kind} by the {near["short"]}'


def build_floors():
    nodes, ntags, ways = osm()
    rooms, doors, closed = [], [], []
    placed_ways = set()
    by_id = {}
    for num, pid, kind, label, name, wids in PLACES:
        pg = []
        for wid in wids:
            w = ways[wid]
            pg = [xy(*nodes[n]) for n in w['nodes']]
            if pg[0] == pg[-1]: pg = pg[:-1]
            if pid.startswith('Mill Pond'):            # the pond runs far north of the Village: keep its south end
                pg = clip_box(pg, 0, 0, *xy(LAT1, LON1))
                pg = clip_box(pg, 0, xy(42.1080, LON0)[1], *xy(LAT1, LON1))
            placed_ways.add(wid)
        if num is not None: name = f'{num} · {name}'
        r = {'id': pid, 'kind': kind, 'name': name, 'poly': pg,
             'z': 0 if pid in ('Village Common', 'Mill Pond') else 1 if 'Garden' in pid or pid == 'Playground' else 2}
        if kind == G: r['label'] = label
        if pid.startswith('Mill Pond'):              # water: drawn like the grey areas you can't walk into
            closed.append({'poly': pg}); continue
        rooms.append(r); by_id[pid] = r
    # every other building in the box is drawn grey (houses, barns and sheds that aren't open)
    for wid, w in ways.items():
        if wid in placed_ways or 'building' not in w['tags']: continue
        pts = [nodes[n] for n in w['nodes'] if n in nodes]
        if not pts or not all(in_box(*p) for p in pts): continue
        pg = [xy(*p) for p in pts]
        closed.append({'poly': pg[:-1] if pg[0] == pg[-1] else pg})

    places = [{'c': centroid(r['poly']), 'short': re.sub(r'^[\w&]+ · ', '', r['name']).split(':')[0].split(' (')[0]}
              for r in rooms if r['kind'] == G or r['id'] in ('Ox & Yoke', 'Visitor Center', 'Village Common')]
    pieces = walk_network(nodes, ways)
    walks = []
    for i, (ns, tags) in enumerate(pieces):
        line = [xy(*nodes[n]) for n in ns]
        half = WALK_KINDS[tags['highway']]
        wid = f'walk-{i + 1}'
        if max(p[1] for p in line) < 100: continue          # streets north of the Village
        r = {'id': wid, 'kind': 'corridor', 'name': walk_name(tags, line, places), 'poly': band(line, half),
             'labelAt': along(line), 'z': 1}
        walks.append((r, ns, line))
        rooms.append(r)
    # paths meet where they share a node
    ends = {}
    for r, ns, line in walks:
        for n in (ns[0], ns[-1]):
            ends.setdefault(n, []).append(r['id'])
    for n, ids in ends.items():
        for a, b in zip(ids, ids[1:]):
            doors.append({'a': a, 'b': b, 'at': xy(*nodes[n]), 'width': 10, 'axis': 'o'})
    # every place opens onto its nearest path
    for r in rooms:
        if r['kind'] == 'corridor' or r['id'] in NO_DOOR: continue
        if r['id'] in DOOR_NEAR:
            p = xy(*DOOR_NEAR[r['id']])
            wr, _, line = min(walks, key=lambda w: line_closest(p, w[2])[0])
        else:
            wr, _, line = min(walks, key=lambda w: poly_line_gap(r['poly'], w[2])[0])
        gap, at = poly_line_gap(r['poly'], line)
        doors.append({'a': wr['id'], 'b': r['id'], 'at': [round(at[0], 1), round(at[1], 1)], 'width': 8, 'axis': 'o'})
        if gap > 60: print(f'  note: {r["id"]} is {gap * U:.0f} m from the nearest path')

    amen = []
    for t, how, ref in AMENITIES:
        if how == 'node': at = xy(*nodes[ref])
        else:
            c = centroid(by_id[ref]['poly'])
            at = [round(c[0], 1), round(c[1], 1)]
        # two icons in one building sit side by side
        while any(a['at'] == at for a in amen): at = [at[0] + 14, at[1]]
        amen.append({'type': t, 'at': at})
    labels = [{'text': t, 'kind': k, 'at': xy(la, lo)} for t, k, la, lo in LABELS]
    floor = {'id': 'G', 'label': 'Village Grounds', 'order': 0,
             'area': 'The Village: Center Village and the Common · the Countryside with the farm and three water-powered '
                     'mills · the Covered Bridge over the Mill Pond',
             'transform': [1, 0, 0], 'rooms': rooms, 'closed': closed, 'amenities': amen, 'labels': labels,
             'doors': doors, 'homeView': ['Visitor Center', 'Freeman Barn', 'Gristmill', 'Center Meetinghouse']}
    return {'about': 'Built by tools/build_osv.py. Buildings, paths and the Mill Pond are OpenStreetMap’s, north up and '
                     'to scale; which building is which, the restrooms, food, water and first aid follow Old Sturbridge '
                     'Village’s own 2026 Map Guide. Upper floors of the houses are not drawn.',
            'source': SOURCE, 'units': 'map units of 0.35 m, north up', 'defaultFloor': 'G',
            'galleryWord': 'Building', 'floors': [floor]}


# ---- works ----------------------------------------------------------------------------------------------------
# osv.org/building/<slug> -> the place on the map (None: not on the 2026 map, listed on the museum page only)
BUILDINGS = {
    'country-bank-visitor-center': 'Visitor Center', 'bullard-tavern': 'Bullard Tavern', 'small-house': 'Small House',
    'friends-meetinghouse': 'Friends Meetinghouse', 'center-meetinghouse': 'Center Meetinghouse',
    'cabinetmaking': 'Cabinetmaking Shop', 'town-pound': 'Town Pound', 'shoe-shop': 'Shoe Shop',
    'asa-knight-store-2': 'Asa Knight Store', 'law-office': 'Law Office', 'richardson': 'Richardson House',
    'parsonage-garden': 'Richardson House', 'tin-shop': 'Tin Shop', 'salem-towne-house': 'Salem Towne House',
    'the-towne-garden': 'Salem Towne House', 'cider-mill': 'Cider Mill', 'printing-office': 'Printing Office',
    'thompson-bank': 'Thompson Bank', 'fitch-house': 'Fitch House', 'the-fitch-house-garden': 'Fitch House',
    'fenno-house': 'Fenno House', 'the-glasshouse-gallery': 'Glasshouse Gallery',
    'armed-and-equipped-firearms-and-the-militia-in-new-england-1790-1840': 'Armed & Equipped',
    'beekeeping-exhibit': 'Beekeeping Exhibit', 'early-lighting-exhibit': 'Early Lighting Exhibit',
    'the-herb-garden': 'Herb Garden', 'district-school': 'District School', 'pottery-shop-kiln': 'Pottery Shop',
    'allen-piggery': 'Allen Piggery', 'freeman-farm': 'Freeman Farmhouse', 'the-freeman-kitchen-garden': 'Freeman Garden',
    'cooper-shop': 'Cooper Shop', 'bixby-house': 'Bixby House', 'blacksmith-shop': 'Blacksmith Shop',
    'carding-mill': 'Carding Mill', 'gristmill': 'Gristmill', 'sawmill': 'Sawmill',
    'vermont-covered-bridge': 'Covered Bridge', 'goods-from-the-woods': 'Goods from the Woods',
    'quinebaug-river-bridge': None, 'simple-machines': None, 'dennison-schoolhouse-a-childs-world': None,
}
SKIP_BUILDINGS = {'village-scoop', 'fuller-conference-center', 'museum-ed', 'miner-grant-store-bakeshop'}
PAGES = {'american-reflections': 'Visitor Center'}          # other osv.org pages about what is on view
# Buildings with no page of their own: the 2026 Map Guide's words
MAPGUIDE_TEXT = {
    'Fitch Barn': ('Fitch Barn', 'This barn stores and displays a large collection of 19th-century agricultural tools '
                                 'and equipment.'),
    'Countryside Gallery': ('Countryside Gallery', 'An exhibition gallery by the Covered Bridge, on the way to the '
                                                   'mills and the Freeman Farm, with accessible restrooms next door.'),
    'David Wight Gallery': ('David Wight Community Gallery', 'A gallery by the Herb Garden for changing exhibitions, '
                                                             'like the members’ Friends of the Village Art Show.'),
    'Towne Barn': ('Salem Towne Barn', 'The barn of the Salem Towne House, the large, well-appointed home of a '
                                       'prosperous farming family.'),
    'Freeman Barn': ('Freeman Farm barn and animals', 'The farmhouse, barn, outbuildings, and animal pens show the '
                                                      'range of a farm family’s activities, with the Village’s '
                                                      'heritage-breed animals.'),
    'Dennison Building': ('Dennison Building', 'This gallery features exhibits that highlight original textiles from '
                                               'the museum collection.'),
}
# Collection highlights that belong to a building on the map: slug -> (place, why)
COLLECTION_PLACES = {
    'carding-machine': ('Carding Mill', 'Came to the Village with the carding mill it worked in.'),
}
# Pictures from Wikimedia Commons where the Village's page has none (or only a view of the whole Village)
COMMONS = {
    'osv-cabinetmaking': 'Cabinetmaking Shop, Old Sturbridge Village, Massachusetts (54221202181).jpg',
    'osv-allen-piggery': 'Allen Piggery, Old Sturbridge Village, Massachusetts (54221432624).jpg',
    'osv-countryside-gallery': 'Countryside Gallery, Old Sturbridge Village, Massachusetts (54221428258).jpg',
    'osv-david-wight-gallery': 'David Wight Community Gallery, Old Sturbridge Village (54572115979).jpg',
    'osv-towne-barn': 'Old Sturbridge Village, Towne Barn.jpg',
    'osv-freeman-barn': 'A look into the c. 1840 barn on the Freeman Farm at Old Sturbridge Village, by Carol M. '
                        'Highsmith, 2019, from the Library of Congress - master-pnp-highsm-57800-57841a.tif',
}
SKIP_IMG = r'footer-map|icons-|social-|adnxs|logo|favicon'


def text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def page(prefix, slug):
    f = CACHE / 'pages' / f'{prefix}-{slug}.html'
    return f.read_text(errors='replace') if f.exists() else None


def main_part(src):
    i, j = src.find('<h1'), src.find('MUSEUM HOURS')
    return src[i:j if j > 0 else None]


def best_src(tag):
    """The 960-pixel copy from an <img> srcset, else its src."""
    m = re.search(r'srcset="([^"]+)"', tag)
    if m:
        for part in m[1].split(','):
            url, _, w = part.strip().partition(' ')
            if w in ('960w', '800w'): return url
    return re.search(r'src="([^"]+)"', tag)[1]


def building(slug):
    src = page('b', slug) or page('p', slug)
    if not src: return None
    body = main_part(src)
    title = text(re.search(r'<h1[^>]*>(.*?)</h1>', body, re.S)[1])
    ps = [text(p) for p in re.findall(r'<p[^>]*>(.*?)</p>', body, re.S)]
    ps = [p for p in ps if p and not re.search(r'click here|purchase tickets|^Exhibit Now Open', p, re.I)]
    made = [p for p in ps[:3] if len(p) < 70 and re.search(r'\d{4}', p)]        # "Barre, Massachusetts, c. 1808"
    desc = [p for p in ps if p not in made and len(p) > 60][:3]
    imgs = [best_src(t) for t in re.findall(r'<img[^>]+>', body) if not re.search(SKIP_IMG, t)]
    banner = [best_src(t) for t in re.findall(r'<img[^>]+>', src[:src.find('<h1')]) if '960x320' in t]
    img = (imgs or banner or [None])[0]
    year = re.search(r'(\d{4})', made[0]) if made else None
    return {'title': title, 'made': ' · '.join(made) or None, 'desc': '\n\n'.join(desc) or None, 'img': img,
            'year': int(year[1]) if year else None}


def collection_item(slug):
    src = page('c', slug)
    if not src: return None
    body = main_part(src)
    j = body.find('otheritems')
    body = body[:j if j > 0 else None]
    title = text(re.search(r'<h1[^>]*>(.*?)</h1>', body, re.S)[1])
    stats = dict((text(k).rstrip(':').strip(), text(v)) for k, v in re.findall(r'<p><b>(.*?)</b>(.*?)</p>', body, re.S))
    m = re.search(r'collectionitem_wysiwyg">(.*?)</div>', body, re.S)
    desc = '\n\n'.join(t for t in (text(p) for p in re.findall(r'<p[^>]*>(.*?)</p>', m[1], re.S)) if t) if m else None
    tag = re.search(r'<img[^>]+class="collectionitem_image"[^>]*>', body) or re.search(r'<img[^>]+>', body)
    img = best_src(tag[0]) if tag else None
    acc = re.search(r'/(\d+(?:\.\d+)+)[^/]*$', img or '')
    return {'title': title, 'stats': stats, 'desc': desc, 'img': img, 'accession': acc[1] if acc else None}


_last = [0.0]


def picture(key, url):
    """Download once (politely) and save a phone-sized JPEG; returns the app path."""
    if not url: return None
    raw = CACHE / 'img' / (key + (Path(url).suffix.lower() or '.jpg'))
    dest = OUT / 'images' / f'{key}.jpg'
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        wait = _last[0] + 2 - time.time()
        if wait > 0: time.sleep(wait)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
        _last[0] = time.time()
        if not out: return None
        raw.write_bytes(out)
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        try: im = Image.open(io.BytesIO(raw.read_bytes()))
        except Exception:
            raw.unlink(); return None
        im = im.convert('RGBA') if im.mode in ('P', 'LA') else im
        if im.mode == 'RGBA':
            bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=im.split()[3]); im = bg
        im = im.convert('RGB')
        im.thumbnail((1000, 1000))
        im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/osv/images/{key}.jpg'


def commons_picture(key, name):
    """A phone-sized copy of a Wikimedia Commons file, and its credit line."""
    meta = CACHE / 'commons' / f'{key}.json'
    if not meta.exists():
        meta.parent.mkdir(parents=True, exist_ok=True)
        url = ('https://commons.wikimedia.org/w/api.php?action=query&prop=imageinfo&iiprop=url|extmetadata'
               '&iiurlwidth=1000&format=json&titles=' + urllib.parse.quote('File:' + name))
        for i in range(5):
            out = subprocess.run(['curl', '-s', '-m', '60', '-A', UA, url], capture_output=True).stdout
            try:
                json.loads(out); meta.write_bytes(out); break
            except Exception: time.sleep(5 * (i + 1))
        else: return None, None
    info = next(iter(json.loads(meta.read_text())['query']['pages'].values()))['imageinfo'][0]
    em = info.get('extmetadata', {})
    who = text(em.get('Artist', {}).get('value')) or 'Unknown'
    lic = text(em.get('LicenseShortName', {}).get('value'))
    return picture(key, info['thumburl']), f'{who}, {lic}, via Wikimedia Commons'


def build_works(floors):
    rooms = {r['id']: r for r in floors['floors'][0]['rooms']}
    placed, unplaced = [], []

    def add(a, place):
        a = {k: v for k, v in a.items() if v not in (None, '')}
        if a['id'] in COMMONS and (not a.get('image') or a['id'] == 'osv-goods-from-the-woods'):
            img, credit = commons_picture(a['id'], COMMONS[a['id']])
            if img: a.update(image=img, imageCredit=credit)
        if place:
            a.update(gallery=place, galleryName=rooms[place]['name'], floor='G')
            placed.append(a)
        else:
            unplaced.append(a)

    sm = (CACHE / 'osv_buildings-sitemap.xml').read_text()
    slugs = [u.rstrip('/').rsplit('/', 1)[1] for u in re.findall(r'<loc>([^<]+)</loc>', sm)]
    for slug in slugs + list(PAGES):
        if slug in SKIP_BUILDINGS: continue
        place = PAGES[slug] if slug in PAGES else BUILDINGS[slug]
        b = building(slug)
        if not b: continue
        key = f'osv-{slug[:40]}'
        exhibit = slug in PAGES or re.search(r'exhibit|gallery|armed', slug)
        add({'id': key, 'title': b['title'], 'artist': b['made'] or ('Exhibition' if exhibit else 'Old Sturbridge Village'),
             'date': None, 'year': b['year'], 'medium': 'Exhibition' if exhibit else
             'Historic garden' if 'garden' in slug else 'Historic building',
             'description': b['desc'], 'descriptionKind': 'From the Village’s page',
             'url': f'{SITE}/{"building/" if slug not in PAGES else ""}{slug}/',
             'image': picture(key, b['img']), 'imageCredit': 'Old Sturbridge Village' if b['img'] else None,
             'placeNote': None if place else 'Not on the Village’s 2026 map; ask at the Visitor Center.'}, place)
    for place, v in MAPGUIDE_TEXT.items():
        if not v: continue
        title, desc = v
        add({'id': 'osv-' + place.lower().replace(' ', '-'), 'title': title, 'artist': 'Old Sturbridge Village',
             'medium': 'Historic building' if 'Barn' in place else 'Exhibition building', 'description': desc,
             'descriptionKind': 'From the Village’s 2026 Map Guide', 'url': f'{SITE}/visit/'}, place)
    sm = (CACHE / 'osv_collectionitems-sitemap.xml').read_text()
    for url in re.findall(r'<loc>([^<]+)</loc>', sm):
        slug = url.rstrip('/').rsplit('/', 1)[1]
        c = collection_item(slug)
        if not c: continue
        st = c['stats']
        place, why = COLLECTION_PLACES.get(slug, (None, None))
        key = f'osv-c-{slug}'
        year = re.search(r'(\d{4})', st.get('Date', ''))
        artist = st.get('Artist') if st.get('Artist') not in (None, '', 'Unknown', 'unknown') else None
        add({'id': key, 'title': c['title'], 'artist': artist or (f'Made in {st["Location"]}' if st.get('Location') else None),
             'date': st.get('Date'), 'year': int(year[1]) if year else None, 'medium': st.get('Materials'),
             'dimensions': st.get('Measurements'), 'accession': c['accession'],
             'description': c['desc'], 'descriptionKind': 'From the Village’s collection page', 'url': url,
             'image': picture(key, c['img']), 'imageCredit': 'Old Sturbridge Village' if c['img'] else None,
             'placeNote': why or 'A highlight of the Village’s collection; where it is shown changes.'}, place)
    order = {r['id']: i for i, r in enumerate(floors['floors'][0]['rooms'])}
    placed.sort(key=lambda a: (order[a['gallery']], a['id']))
    return {'source': 'Old Sturbridge Village website (building pages and collection highlights)',
            'checked': time.strftime('%Y-%m-%d'), 'count': len(placed), 'complete': False, 'artworks': placed}, unplaced


def build_guide(works, unplaced):
    rows = []
    for a, on in [(a, True) for a in works['artworks']] + [(a, False) for a in unplaced]:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a.get('title') or a['id'], 'artist': a.get('artist'),
                     'date': a.get('date'), 'year': a.get('year'), 'medium': a.get('medium'), 'url': a['url'],
                     'imageUrl': a.get('image'), 'onView': on, 'gallery': a.get('gallery'),
                     'floor': a.get('floor')}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': 'Old Sturbridge Village', 'checked': time.strftime('%Y-%m-%d'),
            'source': 'Old Sturbridge Village 2026 Map Guide and website', 'onViewKnown': True,
            'note': 'Old Sturbridge Village is a 200-acre outdoor museum of New England life in the 1830s. This guide '
                    'lists what you walk through: the historic buildings, gardens and exhibits, from the Village’s own '
                    'pages, placed on the map, plus the 62 collection highlights the Village shows online (where each '
                    'is displayed is not published, so most are listed without a place).',
            'works': rows}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
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
          f'{sum("image" in a for a in works["artworks"] + unplaced)} with pictures')
    print('no picture:', [a['id'] for a in works['artworks'] + unplaced if 'image' not in a])
    empty = [r['id'] for r in floors['floors'][0]['rooms'] if r['kind'] == G
             and not any(a['gallery'] == r['id'] for a in works['artworks'])]
    print('buildings with nothing in them:', empty)


if __name__ == '__main__':
    sys.exit(main())
