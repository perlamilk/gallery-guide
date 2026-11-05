#!/usr/bin/env python3
"""Build the Hancock Shaker Village (Pittsfield, MA) map guide (run: python3 tools/build_hsv.py).

    data/hsv/floors.json        the Village seen from above: every building, garden, path and amenity (a flat 2D plan)
    data/hsv/artworks.json      the historic buildings, room settings and objects we can place, and the exhibitions
    data/hsv/images/            their pictures, made smaller for phones
    data/guides/<QID>.json      the same list for the museum page

The map: the Village's own Walking Tour Map (hancockshakervillage.org/wp-content/uploads/2012/07/HSV_handheldMap.pdf,
linked from /visit/walking-tour-guidemap/) is a painted bird's-eye view with north to the left, not to scale, so the
shapes come from OpenStreetMap instead (cached in .cache/hsv/osm.xml), where volunteers have traced and named nearly
every building of the Village, its paths, fences and the cemetery, true to scale and north up. The Walking Tour Map
says which building is which, where the restrooms are (Visitor Center and the Office Privy), the café, the store, the
picnic area, the trailheads and the Route 20 crossing. OpenStreetMap's unnamed buildings are named from it:
the two red barns at the west end are the Visitor Center, the small house between the Brick Dwelling and Route 20 is
the Brethren's Shop, and OSM's "Discovery Barn" is the 1910 Barn Complex with the Discovery Room.
One map unit is 0.35 m, the size the app's walking times assume.

The works: the Village's page for each historic building (shakers/museum/historic-architecture/...), read once by
tools/harvest_hsv.py, placed on its building; room settings and objects photographed inside the buildings (Wikimedia
Commons, with credits); and the 2026 exhibitions. The Village's online collection (PastPerfect) refuses robots, so
the 22,000 objects are not listed one by one.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_osv import centroid, line_closest, poly_line_gap, band, along, length  # noqa: E402  (shared geometry)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'hsv'
CACHE = ROOT / '.cache' / 'hsv'
MUSEUM = 'Q5647064'
SITE = 'https://hancockshakervillage.org'
MAP_PDF = SITE + '/wp-content/uploads/2012/07/HSV_handheldMap.pdf'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SOURCE = ('OpenStreetMap (buildings, paths, fences) and Hancock Shaker Village’s Walking Tour Map '
          '(which building is which, restrooms, café, store; hancockshakervillage.org/visit/walking-tour-guidemap)')

U = 0.35                                    # metres per map unit
LAT0, LON0 = 42.4326, -73.3402              # top-left corner of the map
LAT1, LON1 = 42.4290, -73.3338              # bottom-right corner
KX = 111320 * math.cos(math.radians(42.431)) / U
KY = 110950 / U


def xy(lat, lon):
    return [round((lon - LON0) * KX, 1), round((LAT0 - lat) * KY, 1)]


def in_box(lat, lon):
    return LAT1 <= lat <= LAT0 and LON0 <= lon <= LON1


def osm():
    t = ET.parse(CACHE / 'osm.xml').getroot()
    nodes = {n.get('id'): (float(n.get('lat')), float(n.get('lon'))) for n in t.iter('node')}
    ways = {w.get('id'): {'nodes': [nd.get('ref') for nd in w.iter('nd')],
                          'tags': {k.get('k'): k.get('v') for k in w.iter('tag')}} for w in t.iter('way')}
    return nodes, ways


# ---- the places --------------------------------------------------------------------------------------------
G, S = 'gallery', 'space'
# (id, kind, short label, name, OpenStreetMap way)
PLACES = [
    ('Visitor Center', G, 'Visitor Center', 'Visitor Center: tickets, galleries, theater, restrooms', '213402645'),
    ('Visitor Center North', S, None, 'Visitor Center: Shaker Mercantile (store) and café', '213402468'),
    ('Laundry & Machine Shop', G, 'Laundry & Machine Shop', 'Laundry & Machine Shop', '213402177'),
    ('Garden Tool Shed', G, 'Tool Shed', 'Garden Tool Shed', '213402213'),
    ('Garage', S, None, 'Garage', '213402791'),
    ('Brick Dwelling', G, 'Brick Dwelling', '1830 Brick Dwelling', '213402738'),
    ('Brethren’s Shop', G, 'Brethren’s Shop', 'Brethren’s Shop', '213401888'),
    ('Sisters’ Dairy & Weave Shop', G, 'Sisters’ Dairy', 'Sisters’ Dairy & Weave Shop', '213402153'),
    ('Ministry Wash House', G, 'Wash House', 'Ministry Wash House', '213402048'),
    ('Privy', S, None, 'Privy (historic; not a restroom)', '1086310788'),
    ('Brick Poultry House', G, 'Poultry House', 'Brick Poultry House (exhibitions)', '213402638'),
    ('Round Stone Barn', G, 'Round Stone Barn', '1826 Round Stone Barn (ramp)', '213402815'),
    ('Dairy Ell', G, 'Dairy Ell', 'Dairy Ell of the Round Stone Barn', '1086310798'),
    ('Tannery', G, 'Tannery', 'Tannery', '213401917'),
    ('Ice House', G, 'Ice House', 'Ice House', '213401961'),
    ('Brick Garage', S, None, 'Brick Garage', '213401758'),
    ('Hired Men’s Shop', G, 'Hired Men’s Shop', 'Hired Men’s Shop', '213401771'),
    ('1910 Barn', G, '1910 Barn', '1910 Barn Complex and the Discovery Room (farm animals)', '213401923'),
    ('Trustees’ Office', G, 'Trustees’ Office', 'Trustees’ Office & Store (ramp)', '215708819'),
    ('Office Privy', S, None, 'Office Privy: restrooms', '215708816'),
    ('Wood Poultry House', S, None, 'Wood Poultry House & Farmyard', '213402393'),
    ('Pet Cemetery', S, None, 'Pet Cemetery', '1086443869'),
    ('Meetinghouse', G, 'Meetinghouse', 'Meetinghouse (across Route 20)', '213402463'),
    ('Ministry’s Shop', G, 'Ministry’s Shop', 'Ministry’s Shop (across Route 20)', '213402489'),
    ('Horse Barn', G, 'Horse Barn', 'Horse Barn (across Route 20)', '213402417'),
    ('Schoolhouse', G, 'Schoolhouse', 'Schoolhouse & Outbuildings (across Route 20)', '213402499'),
    ('Shaker Cemetery', S, None, 'Shaker Cemetery', '372064397'),
    ('Picnic Area', S, None, 'Picnic Area', '1086315355'),
]
NO_DOOR = set()
# where a place's door is, when the nearest path would be the wrong one
DOOR_NEAR = {'Visitor Center': (42.43030, -73.33880)}
FENCE_TAGS = {'fence'}

# Amenities from the Walking Tour Map, at OpenStreetMap nodes or inside the building that has them.
AMENITIES = [
    ('entrance', 'node', '9953713221'),                                 # Visitor Center entrance (the map's arrow)
    ('info', 'place', 'Visitor Center'),                                # ticket desk
    ('restroom', 'node', '9952765031'),                                 # Visitor Center restrooms
    ('restroom', 'place', 'Office Privy'),
    ('dining', 'node', '9952759607'),                                   # café
    ('shop', 'place', 'Visitor Center North'),                          # Shaker Mercantile
    ('dining', 'node', '9952765740'),                                   # Bimi's Scoops by the 1910 Barn
]
LABELS = [
    ('Route 20 (Lebanon Mountain Road): cross only at the crosswalk', 'note', 42.43142, -73.3390),
    ('Gardens', 'area', 42.4303, -73.3372), ('Gardens', 'area', 42.4300, -73.3360),
    ('Orchard', 'area', 42.4312, -73.3367),
    ('Gardens', 'area', 42.43188, -73.33795),
    ('Farm & Forest Trail (1 mile) starts at the Round Stone Barn', 'note', 42.42985, -73.3350),
    ('Trail to the Shaker Reservoir, North Family site and Pittsfield State Forest', 'note', 42.43215, -73.3393),
    ('Parking', 'note', 42.43095, -73.33975),
]
WALK_KINDS = {'footway': 5, 'path': 5, 'service': 8, 'track': 5, 'trunk': 8}
CROSSING = (42.43138, -73.33705)            # the crosswalk on Route 20 (the map's "Caution" sign)


def walk_network(nodes, ways):
    """The Village's paths and lanes from OpenStreetMap, cut at every crossing into short pieces. Route 20 is only
    kept for a few metres either side of the crosswalk, so the map walks you across there and nowhere else."""
    picked = {}
    for wid, w in ways.items():
        hw = w['tags'].get('highway')
        if hw not in WALK_KINDS or w['tags'].get('access') == 'private': continue
        pts = [n for n in w['nodes'] if n in nodes]
        if hw == 'trunk':
            pts = [n for n in pts if math.dist(xy(*nodes[n]), xy(*CROSSING)) < 70]
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
    if tags.get('highway') == 'trunk': return 'Route 20 crosswalk'
    if tags.get('name'): return tags['name']
    mid = along(line)
    near = min(places, key=lambda p: math.dist(mid, p['c']))
    kind = {'service': 'Village lane'}.get(tags.get('highway'), 'Path')
    if tags.get('surface') == 'wood': kind = 'Boardwalk'
    return f'{kind} by the {near["short"]}'


def build_floors():
    nodes, ways = osm()
    rooms, doors, closed = [], [], []
    placed_ways = set()
    by_id = {}
    for pid, kind, label, name, wid in PLACES:
        w = ways[wid]
        pg = [xy(*nodes[n]) for n in w['nodes']]
        if pg[0] == pg[-1]: pg = pg[:-1]
        placed_ways.add(wid)
        r = {'id': pid, 'kind': kind, 'name': name, 'poly': pg,
             'z': 0 if 'Cemetery' in pid or pid == 'Picnic Area' else 2}
        if kind == G: r['label'] = label
        rooms.append(r); by_id[pid] = r
    # every other building in the box is drawn grey (farm buildings and sheds that aren't open)
    for wid, w in ways.items():
        t = w['tags']
        if wid in placed_ways or not ('building' in t or t.get('natural') == 'water'): continue
        pts = [nodes[n] for n in w['nodes'] if n in nodes]
        if not pts or not all(in_box(*p) for p in pts): continue
        pg = [xy(*p) for p in pts]
        closed.append({'poly': pg[:-1] if pg[0] == pg[-1] else pg})
    # Route 20 itself: a grey band you can't walk along
    for wid in ('8679082', '8679268', '8697244', '9409122', '1089349760', '1089349761'):
        if wid not in ways: continue
        pts = [xy(*nodes[n]) for n in ways[wid]['nodes'] if n in nodes and in_box(*nodes[n])]
        if len(pts) > 1: closed.append({'poly': band(pts, 16)})

    places = [{'c': centroid(r['poly']), 'short': r.get('label') or r['name'].split(':')[0].split(' (')[0]}
              for r in rooms]
    pieces = walk_network(nodes, ways)
    walks = []
    for i, (ns, tags) in enumerate(pieces):
        line = [xy(*nodes[n]) for n in ns]
        half = WALK_KINDS[tags['highway']]
        r = {'id': f'walk-{i + 1}', 'kind': 'corridor', 'name': walk_name(tags, line, places), 'poly': band(line, half),
             'labelAt': along(line), 'z': 1}
        walks.append((r, ns, line))
        rooms.append(r)
    ends = {}
    for r, ns, line in walks:
        for n in ns:
            ends.setdefault(n, []).append(r['id'])
    for n, ids in ends.items():
        ids = list(dict.fromkeys(ids))
        for a, b in zip(ids, ids[1:]):
            doors.append({'a': a, 'b': b, 'at': xy(*nodes[n]), 'width': 10, 'axis': 'o'})
    # keep only paths joined to the main network, so every place has a way back to the Visitor Center
    g = {}
    for d in doors: g.setdefault(d['a'], set()).add(d['b']); g.setdefault(d['b'], set()).add(d['a'])
    comps, left = [], {r['id'] for r, _, _ in walks}
    while left:
        st = [left.pop()]; comp = set(st)
        while st:
            for y in g.get(st.pop(), ()):
                if y in left: left.discard(y); comp.add(y); st.append(y)
        comps.append(comp)
    main = max(comps, key=lambda c: sum(length(l) for r, _, l in walks if r['id'] in c))
    walks = [w for w in walks if w[0]['id'] in main]
    print(f'  {len(comps) - 1} path pieces not joined to the network are drawn but not used for directions')
    for r in rooms:
        if r['kind'] == 'corridor' or r['id'] in NO_DOOR: continue
        if r['id'] in DOOR_NEAR:
            p = xy(*DOOR_NEAR[r['id']])
            wr, _, line = min(walks, key=lambda w: line_closest(p, w[2])[0])
        else:
            wr, _, line = min(walks, key=lambda w: poly_line_gap(r['poly'], w[2])[0])
        gap, at = poly_line_gap(r['poly'], line)
        doors.append({'a': wr['id'], 'b': r['id'], 'at': [round(at[0], 1), round(at[1], 1)], 'width': 8, 'axis': 'o'})
        if gap > 50: print(f'  note: {r["id"]} is {gap * U:.0f} m from the nearest path')

    amen = []
    for t, how, ref in AMENITIES:
        if how == 'node': at = xy(*nodes[ref])
        else:
            c = centroid(by_id[ref]['poly'])
            at = [round(c[0], 1), round(c[1], 1)]
        while any(math.dist(a['at'], at) < 8 for a in amen): at = [at[0] + 14, at[1]]
        amen.append({'type': t, 'at': at})
    labels = [{'text': t, 'kind': k, 'at': xy(la, lo)} for t, k, la, lo in LABELS]
    floor = {'id': 'G', 'label': 'Village Grounds', 'order': 0,
             'area': 'The Church Family village: Visitor Center, Brick Dwelling, the shops and barns, the Round Stone '
                     'Barn, the gardens, and across Route 20 the Meetinghouse, Ministry’s Shop, Horse Barn and '
                     'Schoolhouse',
             'transform': [1, 0, 0], 'rooms': rooms, 'closed': closed, 'amenities': amen, 'labels': labels,
             'doors': doors, 'homeView': ['Visitor Center', 'Trustees’ Office', 'Round Stone Barn', 'Meetinghouse']}
    return {'about': 'Built by tools/build_hsv.py. Buildings, paths and fences are OpenStreetMap’s, north up and to '
                     'scale; which building is which, the restrooms, café and store follow Hancock Shaker Village’s '
                     'own Walking Tour Map. Upper floors of the buildings are not drawn.',
            'source': SOURCE, 'units': 'map units of 0.35 m, north up', 'defaultFloor': 'G',
            'galleryWord': 'Building', 'floors': [floor]}


# ---- works ----------------------------------------------------------------------------------------------------
# hancockshakervillage.org/shakers/museum/historic-architecture/<slug> -> the place on the map
BUILDINGS = {
    'trustees-office-store': 'Trustees’ Office', 'brethrens-shop': 'Brethren’s Shop',
    '1830-brick-dwelling': 'Brick Dwelling', 'sisters-dairy-weave-shop': 'Sisters’ Dairy & Weave Shop',
    'garden-tool-shed': 'Garden Tool Shed', 'brick-poultry-house': 'Brick Poultry House', 'horse-barn': 'Horse Barn',
    '1910-barn-complex': '1910 Barn', 'ice-house': 'Ice House', 'schoolhouse': 'Schoolhouse', 'tannery': 'Tannery',
    'laundrymachine-shop': 'Laundry & Machine Shop', '1826-stone-barn': 'Round Stone Barn',
    'hired-mens-shop': 'Hired Men’s Shop', 'meetinghouse': 'Meetinghouse', 'ministrys-shop': 'Ministry’s Shop',
}
# When each building was built (from its page)
BUILT = {
    'trustees-office-store': (1813, '1813, enlarged later'), 'brethrens-shop': (1813, 'c. 1813'),
    '1830-brick-dwelling': (1830, '1830'), 'sisters-dairy-weave-shop': (1795, 'probably 1790s'),
    'garden-tool-shed': (1922, '1922'), 'brick-poultry-house': (1878, '1878'), 'horse-barn': (1850, 'moved here 1850'),
    '1910-barn-complex': (1910, '1880 and 1910; dairy ell 1939'), 'ice-house': (1894, '1894'),
    'tannery': (1835, 'enlarged 1835'), 'laundrymachine-shop': (1858, 'turbine of 1858'),
    '1826-stone-barn': (1826, '1826, rebuilt 1865–83'), 'meetinghouse': (1793, '1792–93, moved here in 1962'),
}

# Places on the Walking Tour Map with no page of their own: (title, words)
MAP_TEXT = {
    'Ministry Wash House': ('Ministry Wash House', 'The small wash house of the Ministry, the Shaker leaders, who '
                                                   'by the 1845 Millennial Laws lived, ate and worked apart from '
                                                   'the rest of the family. A stop on the Walking Tour Map.'),
    'Dairy Ell': ('Dairy Ell', 'The long wing of the Round Stone Barn where the Shakers’ dairy cows were milked; today '
                               'it opens onto the barnyard and the start of the Farm & Forest Trail.'),
    'Visitor Center': ('Visitor Center & Center for Shaker Studies', 'The Village’s gateway, rebuilt in 2025–26 by '
                       'the architects TSKP X IDK: tickets, an orientation, permanent galleries that introduce the '
                       'Hancock Shakers through their objects, open storage for some of the finest pieces in the '
                       'collection, the library, and modern restrooms.'),
}
# Photos of rooms and objects inside the buildings, from Wikimedia Commons: (place, file, title)
COMMONS_ROOMS = [
    ('Brick Dwelling', 'Kitchen Oven, Brick Dwelling, Hancock Shaker Village.jpg', 'Kitchen oven, Brick Dwelling'),
    ('Brick Dwelling', 'Food Preparation, Brick Dwelling, Hancock Shaker Village.jpg', 'Food preparation room'),
    ('Brick Dwelling', 'Wooden Cabinetry, Brick Dwelling, Hancock Shaker Village.jpg', 'Built-in cupboards and drawers'),
    ('Brick Dwelling', 'Shaker Quilt, Brick Dwelling, Hancock Shaker Village.jpg', 'Shaker quilt'),
    ('Brick Dwelling', 'Apothecary shop inside the Living Quarters building, where residents were segregated by sex, at '
                       'Hancock Shaker Village, by Carol M. Highsmith, 2019, from the Library of Congress - '
                       'master-pnp-highsm-57900-57910a.tif', 'Apothecary and infirmary'),
    ('Brick Dwelling', 'Bedroom inside the Brick Dwelling building, where residents were segregated by sex, at Hancock '
                       'Shaker Village, by Carol M. Highsmith, 2019, from the Library of Congress - '
                       'master-pnp-highsm-57900-57908a.tif', 'Retiring room (bedroom)'),
    ('Brick Dwelling', 'Meeting room inside the Brick Dwelling building, where residents were segregated by sex, at '
                       'Hancock Shaker Village in Hancock, M, by Carol M. Highsmith, 2019, from the Library of Congress '
                       '- master-pnp-highsm-57900-57904a.tif', 'Meeting room'),
    ('Brick Dwelling', 'Parlor and resting room inside the Brick Dwelling building, where residents were segregated by '
                       'sex, at Hancock Shaker Village, by Carol M. Highsmith, 2019, from the Library of Congress - '
                       'master-pnp-highsm-57900-57905a.tif', 'Parlor and resting room'),
    ('Brick Dwelling', 'Early kitchen stove inside the Brick Dwelling building, where residents were segregated by sex, '
                       'at Hancock Shaker Village, by Carol M. Highsmith, 2019, from the Library of Congress - '
                       'master-pnp-highsm-57900-57903a.tif', 'Early kitchen stove'),
    ('Brick Dwelling', 'Display of Shaker miscellany inside the Brick Dwelling building, where residents were '
                       'segregated by sex, at Hancock Shaker Villa, by Carol M. Highsmith, 2019, from the Library of '
                       'Congress - master-pnp-highsm-57900-57906a.tif', 'Shaker boxes, baskets and small wares'),
    ('Brick Dwelling', 'Reproductions of cautionary signs inside the Brick Dwelling building, where residents were '
                       'segregated by sex, at Hancock Shaker , by Carol M. Highsmith, 2019, from the Library of '
                       'Congress - master-pnp-highsm-57900-57911a.tif', 'Signs of the Shaker rules'),
    ('Trustees’ Office', 'Corridor inside the Trustees\' Office and Store at Hancock Shaker Village in Hancock, '
                         'Massachusetts, established in 1791, by Carol M. Highsmith, 2019, from the Library of Congress '
                         '- master-pnp-highsm-57800-57899a.tif', 'Corridor of the Trustees’ Office'),
    ('Trustees’ Office', 'Bell on top of Trustee\'s Office & Store, Hancock Shaker Village.jpg', 'The bell'),
    ('Sisters’ Dairy & Weave Shop', 'Butter & Cheese Production, Sister\'s Dairy, Hancock Shaker Village.jpg',
     'Butter and cheese making'),
    ('Brethren’s Shop', 'Shaker Boxes, Brethren\'s Shop, Hancock Shaker Village.jpg', 'Oval boxes'),
    ('Brethren’s Shop', 'Shaker Baskets, Brethren\'s Shop, Hancock Shaker Village.jpg', 'Shaker baskets'),
    ('Ministry’s Shop', 'Shaker Basket manufacture, Ministry Shop, Hancock Shaker Village.jpg', 'Basket making'),
    ('Tannery', 'Screw for Cider Press, Blacksmith-Tannery, Hancock Shaker Village.jpg', 'Cider press screw'),
    ('Tannery', 'Wheel of Windlass, Blacksmith-Tannery, Hancock Shaker Village.jpg', 'Windlass wheel'),
    ('Laundry & Machine Shop', 'Machine Shop, Hancock Shaker Village.jpg', 'The water-powered machine shop'),
    ('Dairy Ell', 'Two-Way Plow by Dairy Ell & Round Stone Barn, Hancock Shaker Village.jpg', 'Two-way plow'),
]
# Pictures for buildings whose page has none we can use
COMMONS_BUILDINGS = {
    'Brick Dwelling': '1830 Brick Dwelling at Hancock Shaker Village.jpg',
    'Brethren’s Shop': 'Brethren\'s Shop, Hancock Shaker Village.jpg',
    'Horse Barn': 'Horse Barn, Hancock Shaker Village.jpg',
    'Ice House': 'Ice House, Hancock Shaker Village.jpg',
    'Meetinghouse': 'Meetinghouse, Hancock Shaker Village.jpg',
    'Laundry & Machine Shop': 'Laundry-Machine Shop, Hancock Shaker Village.jpg',
    'Sisters’ Dairy & Weave Shop': 'The Sisters\' Dairy & Weave Shop at Hancock Shaker Village in Hancock, '
                                   'Massachusetts, established in 1791, by Carol M. Highsmith, 2019, from the Library of '
                                   'Congress - master-pnp-highsm-57900-57901a.tif',
    'Trustees’ Office': 'The Trustees\' Office and Store at Hancock Shaker Village in Hancock, Massachusetts, '
                        'established in 1791, by Carol M. Highsmith, 2019, from the Library of Congress - '
                        'master-pnp-highsm-57800-57898a.tif',
    'Round Stone Barn': 'Gardens with Round Stone Barn and Dairy Ell, Hancock Shaker Village.jpg',
    'Tannery': 'Blacksmith-Tannery (left) and Round Stone Barn, Hancock Shaker Village.jpg',
    'Dairy Ell': 'View from the Dairy Ell and Round Stone Barn, Hancock Shaker Village.jpg',
}
# Collection pieces shown online whose display place isn't published
COMMONS_COLLECTION = [
    ('Tree of Life - Shaker - painted by Hannah Cohoon.JPG',
     {'title': 'The Tree of Life', 'artist': 'Hannah Cohoon (1788–1864)', 'date': '1854', 'year': 1854,
      'medium': 'Ink and watercolor on paper (a Shaker “gift drawing”)',
      'description': 'Sister Hannah Cohoon of the Hancock community said this drawing came to her in a vision. It is '
                     'the best-known of the Village’s 25 gift (spirit) drawings, the largest such collection anywhere. '
                     'Gift drawings are fragile and shown only from time to time.'}),
    ('1923 Reo (51273307953).jpg',
     {'title': '1923 Reo touring car', 'artist': 'Reo Motor Car Company', 'date': '1923', 'year': 1923,
      'medium': 'Automobile', 'url': SITE + '/collections/1923reo/',
      'description': 'The Hancock Shakers’ own car, bought in the 1920s when the community still ran its farm. The '
                     'Village tells its story on its collection page.'}),
]
# 2026 exhibitions (from the Village's exhibition pages): slug -> (place or None, dates)
EXHIBITIONS = {
    'shaker-light-barbara-ernst-prey-austin-prey': ('Brick Poultry House', 'Through the end of the 2026 season'),
    'all-around-the-room-june-7-november-30': ('Brick Poultry House', 'June 21 – December 28, 2026'),
    'imagining-shaker-sisters-may-17-november-30': ('Brick Poultry House', 'May 17 – November 30, 2026'),
    'couture-from-the-world-inspired-by-the-shakers-june-7-november-30': ('Brick Dwelling', 'June 7 – November 30, 2026'),
    'elements-of-harmony-may-17-november-30': ('Brick Dwelling', 'May 17 – November 30, 2026'),
    'the-city-of-peace-photographs-by-dylan-kubis-april-12-november-30': ('Brick Dwelling',
                                                                          'April 12 – November 30, 2026'),
    'simple-gifts-visual-translations-of-shaker-hymns-and-copland-music-may-17-nov-30': (
        'Laundry & Machine Shop', 'May 17 – November 30, 2026 (in the Ironing Room)'),
    'steve-careau-chaste-may-17-november-30': ('Tannery', 'May 17 – November 30, 2026'),
    # "in the Believer’s Room, no admission ticket needed": the free part of the Visitor Center
    'peculiar-grace-on-exhibit-till-december-28': ('Visitor Center', 'Through December 28, 2026 (Believer’s Room, free)'),
}


def text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def page(name):
    f = CACHE / 'pages' / f'{name}.html'
    return f.read_text(errors='replace') if f.exists() else None


def body_of(src):
    i = src.find('<main')
    j = src.find('Getting Here')
    body = src[i if i > 0 else 0:j if j > 0 else None]
    k = body.find('class="fusion-sharing-box')
    return body[:k] if k > 0 else body


SKIP_P = r'^(The Shakers|Location|Visit)\b|Click here|Getting Here|^Hours'


def paragraphs(body):
    body = re.sub(r'<p[^>]*wp-caption-text[^>]*>.*?</p>|<figcaption.*?</figcaption>', '', body, flags=re.S)
    ps = [text(p) for p in re.findall(r'<p[^>]*>(.*?)</p>', body, re.S)]
    return [p for p in ps if len(p) > 50 and not re.search(SKIP_P, p)]


def og(src, prop):
    m = re.search(rf'<meta property="og:{prop}" content="([^"]+)"', src)
    return html.unescape(m[1]) if m else None


def page_image(body):
    """The full-size picture linked from the page body (WordPress links each small copy to its original)."""
    for url in re.findall(r'href="(https://hancockshakervillage\.org/wp-content/uploads/[^"]+\.(?:jpe?g|png))"', body,
                          re.I):
        if not re.search(r'logo|favicon|MCC|icon', url, re.I): return url
    for url in re.findall(r'(?:data-orig-src|src)="(https://hancockshakervillage\.org/wp-content/uploads/[^"]+\.'
                          r'(?:jpe?g|png))"', body, re.I):
        if not re.search(r'logo|favicon|MCC|icon|-\d{2,3}x\d{2,3}\.', url, re.I): return url
    return None


_last = [0.0]


def picture(key, url):
    """Download once (politely) and save a phone-sized JPEG; returns the app path."""
    if not url: return None
    raw = CACHE / 'img' / (key + (Path(urllib.parse.urlparse(url).path).suffix.lower() or '.jpg'))
    dest = OUT / 'images' / f'{key}.jpg'
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        for i in range(4):
            wait = _last[0] + 3 - time.time()
            if wait > 0: time.sleep(wait)
            out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
            _last[0] = time.time()
            if out: break
            time.sleep(15 * (i + 1))
        if not out: print('  no picture from', url); return None
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
    return f'data/hsv/images/{key}.jpg'


def commons_info(names):
    """Commons file info (1000-px thumbnail, author, licence) for many files, asked in batches of 40 and cached."""
    f = CACHE / 'commons.json'
    have = json.loads(f.read_text()) if f.exists() else {}
    want = [n for n in names if n not in have]
    for i in range(0, len(want), 40):
        batch = want[i:i + 40]
        url = ('https://commons.wikimedia.org/w/api.php?action=query&prop=imageinfo&iiprop=url|extmetadata'
               '&iiurlwidth=1000&format=json&titles=' + urllib.parse.quote('|'.join('File:' + n for n in batch)))
        for k in range(6):
            out = subprocess.run(['curl', '-s', '-m', '60', '-A', UA, url], capture_output=True).stdout
            try:
                d = json.loads(out); break
            except Exception: time.sleep(20 * (k + 1))
        else: raise SystemExit('Wikimedia Commons is not answering; try again later')
        norm = {x['to']: x['from'] for x in d['query'].get('normalized', [])}
        for p in d['query']['pages'].values():
            if 'imageinfo' not in p: print('  not on Commons:', p['title']); continue
            ii = p['imageinfo'][0]; em = ii.get('extmetadata', {})
            name = norm.get(p['title'], p['title'])[5:]
            have[name] = {'thumb': (ii.get('thumburl') or ii['url']).split('?')[0], 'page': ii.get('descriptionurl'),
                          'artist': text(em.get('Artist', {}).get('value')) or 'Unknown',
                          'license': text(em.get('LicenseShortName', {}).get('value'))}
        f.write_text(json.dumps(have, ensure_ascii=False, indent=1))
        time.sleep(3)
    return have


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower().replace('’', '')).strip('-')[:44]


def build_works(floors):
    rooms = {r['id']: r for r in floors['floors'][0]['rooms']}
    info = commons_info([n for _, n, _ in COMMONS_ROOMS] + list(COMMONS_BUILDINGS.values()) +
                        [n for n, _ in COMMONS_COLLECTION])
    placed, unplaced = [], []

    def credit(name):
        i = info[name]
        return f'{i["artist"]}, {i["license"]}, via Wikimedia Commons'

    def add(a, place):
        a = {k: v for k, v in a.items() if v not in (None, '')}
        if place:
            a.update(gallery=place, galleryName=rooms[place]['name'], floor='G')
            placed.append(a)
        else:
            unplaced.append(a)

    for slug, place in BUILDINGS.items():
        src = page(f'shakers__museum__historic-architecture__{slug}')
        if not src: print('  missing page', slug); continue
        body = body_of(src)
        title = text(re.search(r'<h1[^>]*>(.*?)</h1>', body, re.S)[1]) if '<h1' in body else place
        title = re.sub(r'\s*HSV Admin.*$', '', title)
        ps = paragraphs(body)
        key = f'hsv-{slugify(slug)}'
        img, cr = None, None
        if place in COMMONS_BUILDINGS and COMMONS_BUILDINGS[place] in info:
            n = COMMONS_BUILDINGS[place]
            img, cr = picture(key, info[n]['thumb']), credit(n)
        if not img:
            img = picture(key, page_image(body) or og(src, 'image')); cr = 'Hancock Shaker Village' if img else None
        year, date = BUILT.get(slug, (None, None))
        add({'id': key, 'title': title, 'artist': 'Built by the Hancock Shakers',
             'year': year, 'date': date, 'medium': 'Historic building',
             'description': '\n\n'.join(ps[:4]) or None, 'descriptionKind': 'From the Village’s page',
             'url': f'{SITE}/shakers/museum/historic-architecture/{slug}/', 'image': img, 'imageCredit': cr}, place)
    for place, (title, desc) in MAP_TEXT.items():
        key = f'hsv-{slugify(place)}'
        img, cr = None, None
        if place in COMMONS_BUILDINGS and COMMONS_BUILDINGS[place] in info:
            n = COMMONS_BUILDINGS[place]
            img, cr = picture(key, info[n]['thumb']), credit(n)
        add({'id': key, 'title': title, 'artist': 'Hancock Shaker Village',
             'medium': 'Historic building' if place != 'Visitor Center' else 'Visitor center and galleries',
             'description': desc, 'descriptionKind': 'From the Village’s Walking Tour Map and pages',
             'url': f'{SITE}/visit/', 'image': img, 'imageCredit': cr}, place)
    for place, name, title in COMMONS_ROOMS:
        if name not in info: continue
        key = f'hsv-r-{slugify(place)}-{slugify(title)}'[:60]
        add({'id': key, 'title': title, 'artist': 'Room setting from the Village’s collection',
             'medium': 'Room setting' if re.search(r'room|kitchen|corridor|apothecary|oven|stove|signs|cupboards',
                                                    title, re.I) else 'Shaker objects',
             'description': f'Photographed in the {rooms[place]["name"].split(" (")[0]}. Room settings change from '
                            'time to time.',
             'descriptionKind': 'Photo on Wikimedia Commons', 'url': info[name]['page'],
             'image': picture(key, info[name]['thumb']), 'imageCredit': credit(name)}, place)
    for name, a in COMMONS_COLLECTION:
        if name not in info: continue
        key = f'hsv-c-{slugify(a["title"])}'
        add({'id': key, **a, 'url': a.get('url') or info[name]['page'], 'descriptionKind': 'About this piece',
             'image': picture(key, info[name]['thumb']), 'imageCredit': credit(name),
             'placeNote': 'In the Village’s collection; ask at the Visitor Center whether it is out.'}, None)
    for slug, (place, dates) in EXHIBITIONS.items():
        src = page(f'exhibition__{slug}')
        if not src: print('  missing exhibition', slug); continue
        body = body_of(src)
        title = re.sub(r'\s*-\s*Hancock Shaker Village$', '', og(src, 'title') or slug)
        title = re.sub(r'\s*[–:,-]\s*(On exhibit|April|May|June).*$', '', title)
        ps = paragraphs(body)
        key = f'hsv-x-{slugify(slug)}'
        img = picture(key, og(src, 'image') or page_image(body))
        add({'id': key, 'title': title, 'artist': 'Exhibition', 'date': dates, 'medium': 'Exhibition',
             'description': '\n\n'.join(ps[:3]) or og(src, 'description'),
             'descriptionKind': 'From the Village’s exhibition page',
             'url': f'{SITE}/exhibition/{slug}/', 'image': img, 'imageCredit': 'Hancock Shaker Village' if img else None,
             'placeNote': None if place else 'Where in the Village it is shown isn’t published; ask at the Visitor '
                                             'Center.'}, place)
    order = {r['id']: i for i, r in enumerate(floors['floors'][0]['rooms'])}
    placed.sort(key=lambda a: (order[a['gallery']], a['medium'] != 'Historic building', a['id']))
    return {'source': 'Hancock Shaker Village website (building and exhibition pages) and Wikimedia Commons photos',
            'checked': time.strftime('%Y-%m-%d'), 'count': len(placed), 'complete': False, 'artworks': placed}, unplaced


def build_guide(works, unplaced):
    rows = []
    for a, on in [(a, True) for a in works['artworks']] + [(a, False) for a in unplaced]:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a.get('title') or a['id'], 'artist': a.get('artist'),
                     'date': a.get('date'), 'year': a.get('year'), 'medium': a.get('medium'), 'url': a['url'],
                     'imageUrl': a.get('image'), 'onView': on, 'gallery': a.get('gallery'),
                     'floor': a.get('floor')}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': 'Hancock Shaker Village', 'checked': time.strftime('%Y-%m-%d'),
            'source': 'Hancock Shaker Village Walking Tour Map and website; Wikimedia Commons', 'onViewKnown': True,
            'note': 'Hancock Shaker Village is the 1791 “City of Peace” of the Shakers: twenty historic buildings on a '
                    'working farm, with about fifty room settings drawn from a collection of more than 22,000 '
                    'objects. This guide lists the buildings from the Village’s own pages, room settings and objects '
                    'photographed inside them, and the 2026 exhibitions. The online collection database does not '
                    'allow robots, so single objects are not listed.',
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
