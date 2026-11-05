#!/usr/bin/env python3
"""Build the Philip Johnson Glass House (New Canaan, CT) map guide:

    python3 tools/build_glasshouse.py

    data/glasshouse/floors.json     the 49-acre site and the Visitor Center in town, seen from above (2D)
    data/glasshouse/artworks.json   the buildings, the paintings and sculptures, each in its place
    data/glasshouse/images/         their pictures, made smaller for phones
    data/guides/Q1506237.json       the same, for the museum page

Where the information comes from
--------------------------------
The map
  - The site (floor G) is traced from the Glass House's own "Glass House Site Map" (the drawing behind the Explore
    pages of theglasshouse.org: wp-content/themes/glass-house/images/explore-map-with-logo.svg, 700 x 535, cached in
    .cache/glasshouse/). On that drawing NORTH IS TO THE RIGHT and Ponus Ridge Road runs along the bottom (east); it is
    turned here so north is up. Its scale is about 1.55 px per metre (checked against the OpenStreetMap outlines of the
    Glass House, Brick House and Sculpture Gallery, way 364907964/66/74). The buildings, the pond, the bridge and the
    drive are the drawing's own shapes (found by colour); the site map's pins name them. Footpaths across the lawns and
    fields are not drawn on it: those here are approximate.
  - The Visitor Center + Design Store in town (floor V) is from OpenStreetMap (way 365100513, Elm Street, Park Street,
    New Canaan station). Its inside isn't published; the Lumberyard Lot is placed at OpenStreetMap's 244 Elm Street.

The works
  The buildings (theglasshouse.org/explore/...), and every painting and sculpture with its own collection page
  (theglasshouse.org/learn/...), with the Glass House's own pictures. The pages don't say which building each work is
  in: paintings go in the Painting Gallery (its racks rotate, so only some are out), sculptures in the Sculpture Gallery
  in the order the Sculpture Gallery page gives, unless a page says otherwise. Those places are marked as our guess.
  theglasshouse.org's robots.txt asks for a 10-second crawl delay: every request waits 10 seconds.
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
OUT = ROOT / 'data' / 'glasshouse'
CACHE = ROOT / '.cache' / 'glasshouse'
MUSEUM = 'Q1506237'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SITE = 'https://theglasshouse.org'
APPROX = 'Approximate'
K = 4.0                                   # map units per metre
PXM = 1.55                                # site-map pixels per metre


# ---- the site (floor G): site-map pixels -> metres east/north of the Glass House -> map units, north up -------------
def S(sx, sy):
    e, n = (sy - 232) / PXM, (sx - 439) / PXM
    return [round((e + 160) * K, 1), round((180 - n) * K, 1)]


def band(pts, half=1.5):
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        nx, ny = -dy / n * half, dx / n * half
        left.append((x + nx, y + ny)); right.append((x - nx, y - ny))
    return left + right[::-1]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def circle(cx, cy, r, n=16):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


# shapes from the site map (pixels), found by colour in the drawing
GLASS = [(452.0, 222.8), (425.2, 224.0), (425.8, 241.2), (453.0, 240.0)]
BRICK = [(426.2, 282.2), (401.2, 283.0), (401.8, 293.0), (426.0, 292.2)]
PAINTING = [(567.5, 360.0), (567.5, 372.2), (568.8, 372.8), (567.2, 375.8), (561.8, 374.8), (558.2, 375.5),
            (555.8, 377.0), (552.8, 380.8), (552.0, 387.2), (553.8, 391.2), (557.0, 394.2), (560.5, 395.5),
            (564.0, 395.5), (568.0, 393.8), (568.5, 396.8), (570.5, 399.5), (572.5, 400.5), (575.8, 400.5),
            (577.5, 399.8), (579.5, 397.5), (580.0, 393.2), (579.0, 391.2), (583.8, 390.0), (586.5, 387.2),
            (587.8, 383.8), (587.5, 381.0), (586.2, 378.2), (582.5, 375.2), (579.0, 374.8), (575.0, 375.8),
            (574.8, 374.0), (573.5, 372.5), (575.0, 372.2), (575.0, 360.0)]
SCULPTURE = [(657.8, 302.8), (657.8, 312.8), (657.2, 313.0), (652.2, 308.5), (637.5, 323.2), (648.5, 323.5),
             (648.5, 345.8), (667.2, 345.8), (667.5, 337.8), (675.5, 345.2), (675.5, 323.0), (667.2, 323.0),
             (672.8, 317.2)]
STUDIO = [(189.0, 310.2), (175.8, 312.2), (177.0, 319.8), (176.5, 323.5), (177.8, 325.5), (179.2, 326.2),
          (182.0, 326.0), (186.2, 321.5), (190.5, 320.8)]
GHOST = [(157.2, 208.5), (148.5, 209.5), (149.2, 217.8), (158.2, 216.8)]
MONSTA = [(207.2, 408.2), (211.2, 409.2), (215.5, 413.2), (219.0, 414.0), (220.0, 416.0), (223.5, 418.8),
          (227.8, 418.0), (230.5, 416.2), (228.5, 412.0), (225.0, 410.0), (222.8, 407.5), (228.2, 401.0),
          (219.2, 399.5), (216.8, 401.8), (214.8, 401.5)]
PAVILION = [(374.0, 83.5), (374.2, 96.8), (382.5, 96.8), (383.0, 101.0), (387.5, 100.8), (387.2, 92.5),
            (391.5, 92.2), (391.5, 87.5), (383.0, 87.5), (382.8, 83.5)]
KIRSTEIN = [(321.8, 33.2), (316.0, 39.0), (319.2, 42.2), (321.8, 39.5), (324.0, 41.5), (327.0, 38.2)]
POPESTEAD = [(328.5, 397.5), (328.5, 420.5), (339.2, 420.5), (340.5, 421.8), (345.5, 421.8), (345.8, 418.5),
             (352.5, 418.0), (352.5, 410.0), (353.8, 408.5), (353.5, 401.2), (345.0, 401.5), (344.8, 397.5)]
CALLUNA = [(72.5, 413.2), (54.5, 414.2), (54.2, 421.0), (45.0, 421.5), (45.8, 431.5), (48.2, 431.2), (48.5, 434.2),
           (44.0, 434.5), (44.0, 440.5), (48.5, 440.8), (48.5, 448.2), (61.8, 448.2), (61.8, 437.2), (57.5, 437.0),
           (57.5, 431.0), (73.5, 429.8), (73.5, 427.2), (75.2, 427.0), (75.0, 420.8), (73.0, 420.5)]
SUCCULENT = [(33.2, 413.2), (16.5, 421.5), (24.8, 438.0), (41.5, 429.8)]
GRAINGER = [(33.2, 491.8), (18.5, 492.5), (18.8, 499.2), (33.5, 498.8)]
GATE = [(245.0, 420.8), (245.0, 425.8), (263.8, 425.5), (263.8, 420.5)]
JUDD = circle(355.2, 291.0, 6.4)
POOL = [(470.2, 273.8), (466.2, 276.8), (465.5, 283.0), (468.8, 287.0), (474.2, 287.8), (478.5, 284.8),
        (479.5, 279.0), (476.2, 274.5)]
SCHNABEL = [(613.8, 340.5), (613.8, 344.5), (632.0, 344.8), (632.0, 340.8)]
BRIDGE = rect(487.2, 323.0, 512.5, 330.2)
POND = [(395.8, 59.0), (381.5, 63.2), (376.2, 71.0), (375.0, 83.0), (374.0, 83.5), (374.2, 96.8), (375.5, 100.5),
        (379.0, 108.2), (372.8, 111.5), (372.5, 115.5), (376.8, 117.8), (377.0, 119.0), (380.8, 119.8),
        (383.5, 124.2), (389.2, 129.0), (399.0, 133.0), (405.8, 133.5), (415.2, 129.8), (418.8, 126.0),
        (420.8, 121.5), (419.0, 98.0), (421.5, 82.0), (421.2, 74.5), (419.0, 68.8), (410.2, 61.2), (404.5, 59.0)]
COURT = rect(375.0, 266.0, 398.0, 292.0)
LAWN = [(425.5, 241.5), (453, 240.2), (430, 282.2), (401.2, 283)]
ROAD = [(0, 470), (100, 456), (200, 446), (300, 439), (400, 435), (500, 434), (600, 438), (700, 448)]
DRIVE = [(254, 436), (254, 426), (258, 400), (275, 377), (300, 355), (318, 335), (327, 305), (338, 285), (352, 276),
         (375, 272)]
POPE_DRIVE = [(258, 403), (285, 393), (325, 388), (362, 392), (377, 405), (380, 434)]
POND_PATH = [(410, 223), (372, 196), (346, 172), (367, 177), (345, 150), (339, 131), (337, 120), (343, 101)]
TOWER_PATH = [(343, 101), (336, 80), (328, 60), (322, 43)]
GALLERY_PATH = [(512, 326.5), (570, 327.5), (637.5, 329)]
PG_PATH = [(570, 328), (571, 360)]
FIELD = [(430, 290), (455, 305), (487, 326.5)]
STUDIO_PATH = [(425, 236), (380, 250), (320, 270), (250, 290), (191, 316)]
GHOST_PATH = [(182, 311), (168, 270), (155, 218)]
MONSTA_PATH = [(262, 405), (243, 410), (229, 410)]

SITE_ROOMS = [
    # id, kind, name, polygon (site-map pixels), short label
    ('Grounds', 'space', 'The Glass House grounds: 49 acres of lawns, meadows and woods with 14 structures. Visit on a '
                         'tour only (outline approximate)', rect(5, 25, 695, 432), None),
    ('Ponus Ridge Road', 'corridor', 'Ponus Ridge Road: the site’s gate is here, but private cars, taxis and Uber '
                                     'are sent back to the Visitor Center: arrive by the tour shuttle', band(ROAD, 4),
     None),
    ('The Pond', 'space', 'The pond Johnson dug below the Glass House, with the Pavilion on its edge', POND, None),
    ('Lawn', 'space', 'The grassy court between the Glass House and the Brick House, “a single composition”', LAWN,
     None),
    ('Court', 'space', 'Gravel court at the end of the drive, by the Brick House', COURT, None),
    ('Drive', 'corridor', 'The drive from the entrance gate up to the houses (the tour shuttle)', band(DRIVE, 3), None),
    ('Popestead Drive', 'corridor', 'Drive past Popestead', band(POPE_DRIVE, 2.5), None),
    ('Pond Path', 'corridor', 'Path from the Glass House down the hill to the pond (steep, zigzag)',
     band(POND_PATH, 1.5), None),
    ('Tower Path', 'corridor', 'Path on to the Monument to Lincoln Kirstein (approximate)', band(TOWER_PATH, 1.2),
     None),
    ('Bridge', 'corridor', 'Footbridge over the brook to the galleries', BRIDGE, None),
    ('Gallery Path', 'corridor', 'Paved path from the bridge to the Painting and Sculpture Galleries',
     band(GALLERY_PATH, 2), None),
    ('Painting Gallery Path', 'corridor', 'Path to the Painting Gallery entrance', band(PG_PATH, 2), None),
    ('Field Walk', 'corridor', 'Across the grass from the Brick House to the bridge (approximate)', band(FIELD, 1.5),
     None),
    ('Meadow Walk', 'corridor', 'Through the field of tall grass to the Studio (approximate)', band(STUDIO_PATH, 1.5),
     None),
    ('Ghost House Walk', 'corridor', 'To the Ghost House at the edge of the woods (approximate)',
     band(GHOST_PATH, 1.2), None),
    ('Da Monsta Walk', 'corridor', 'From the drive to Da Monsta (approximate)', band(MONSTA_PATH, 1.5), None),
    ('Glass House', 'gallery', 'The Glass House (1949): Johnson’s home, 55 by 33 feet of glass', GLASS, 'Glass House'),
    ('Brick House', 'gallery', 'The Brick House (1949): guest house and bedroom with the Soane-style vault, Johnson’s '
                               'reading room', BRICK, 'Brick House'),
    ('Painting Gallery', 'gallery', 'Painting Gallery (1965): a grass-covered berm with three round rooms of rotating '
                                    'racks', PAINTING, 'Painting Gallery'),
    ('Sculpture Gallery', 'gallery', 'Sculpture Gallery (1970): five levels under a glass roof, Johnson’s “best single '
                                     'room”', SCULPTURE, 'Sculpture Gallery'),
    ('Studio', 'gallery', 'The Studio (1980): Johnson’s library and workroom, with a cone-shaped roof', STUDIO,
     'Studio'),
    ('Ghost House', 'gallery', 'Ghost House (1984): a chain-link “house” on an old barn foundation', GHOST,
     'Ghost House'),
    ('Da Monsta', 'gallery', 'Da Monsta (1995): Johnson’s last building on the site, by the entrance', MONSTA,
     'Da Monsta'),
    ('Pavilion in the Pond', 'gallery', 'Pavilion in the Pond (1962): a folly built at a smaller scale', PAVILION,
     'Pavilion'),
    ('Kirstein Tower', 'gallery', 'Monument to Lincoln Kirstein (1985): a 30-foot climbable tower of concrete blocks',
     KIRSTEIN, 'Kirstein Tower'),
    ('Popestead', 'gallery', 'Popestead (c. 1920, a barn turned house): not open on regular tours', POPESTEAD,
     'Popestead'),
    ('Calluna Farms', 'gallery', 'Calluna Farms (1905): David Whitney’s house, not open on regular tours', CALLUNA,
     'Calluna'),
    ('Succulent Garden', 'gallery', 'David Whitney’s Succulent Garden (1989), in front of Calluna', SUCCULENT,
     'Succulent Garden'),
    ('Grainger', 'gallery', 'Grainger (c. 1783), with Whitney’s Peony Garden: not open on regular tours', GRAINGER,
     'Grainger'),
    ('Entrance Gate', 'space', 'Entrance gate on Ponus Ridge Road (the shuttle comes in here)', GATE, None),
    ('Judd Sculpture', 'gallery', 'Donald Judd’s concrete ring, near the Brick House', JUDD, 'Judd'),
    ('Swimming Pool', 'space', 'Johnson’s round swimming pool', POOL, None),
    ('Schnabel Sculpture', 'gallery', 'Julian Schnabel’s sculpture, near the Sculpture Gallery', SCHNABEL, 'Schnabel'),
]
SITE_DOORS = [
    ('Drive', 'Ponus Ridge Road', (254, 434)), ('Drive', 'Entrance Gate', (254, 423)),
    ('Drive', 'Court', (375, 272)), ('Court', 'Brick House', (398, 287)), ('Court', 'Lawn', (398, 280)),
    ('Lawn', 'Glass House', (439, 241)), ('Lawn', 'Brick House', (414, 283)), ('Court', 'Grounds', (386, 266)),
    ('Pond Path', 'Glass House', (425.5, 228)), ('Pond Path', 'Pavilion in the Pond', (383, 101)),
    ('Pond Path', 'Tower Path', (343, 101)), ('Tower Path', 'Kirstein Tower', (321, 42)),
    ('Pond Path', 'The Pond', (370, 115)),
    ('Field Walk', 'Brick House', (426, 290)), ('Field Walk', 'Bridge', (487.5, 326.5)),
    ('Bridge', 'Gallery Path', (512, 326.5)), ('Gallery Path', 'Painting Gallery Path', (570, 327.5)),
    ('Painting Gallery Path', 'Painting Gallery', (571, 360)), ('Gallery Path', 'Sculpture Gallery', (637.5, 329)),
    ('Gallery Path', 'Schnabel Sculpture', (622, 340.5)), ('Grounds', 'Swimming Pool', (466, 280)),
    ('Meadow Walk', 'Glass House', (425.5, 236)), ('Meadow Walk', 'Studio', (190, 316)),
    ('Meadow Walk', 'Grounds', (320, 270)), ('Ghost House Walk', 'Studio', (182, 311)),
    ('Ghost House Walk', 'Ghost House', (155, 217)), ('Da Monsta Walk', 'Drive', (259, 404)),
    ('Da Monsta Walk', 'Da Monsta', (229, 410)), ('Popestead Drive', 'Drive', (258, 403)),
    ('Popestead Drive', 'Popestead', (353, 405)), ('Popestead Drive', 'Ponus Ridge Road', (380, 434)),
    ('Grounds', 'Judd Sculpture', (355, 284.6)), ('Grounds', 'Calluna Farms', (60, 413.5)),
    ('Grounds', 'Succulent Garden', (25, 417)), ('Ponus Ridge Road', 'Grainger', (26, 492)),
    ('Grounds', 'Ponus Ridge Road', (120, 432)),
]
SITE_AMEN = [('entrance', 254, 430), ('entrance', 439, 241), ('entrance', 414, 283), ('entrance', 571, 360),
             ('entrance', 637.5, 329), ('entrance', 190, 316)]
SITE_LABELS = [('Ponus Ridge Road', 'area', 520, 446),
               ('Shuttle only: tours start at the Visitor Center in town (199 Elm St, 10 min away)', 'area', 330, 470),
               ('Brook', 'area', 525, 290), ('Brook', 'area', 260, 125),
               ('Restrooms: not listed on the site map; ask at the Visitor Center', 'area', 560, 230),
               ('No food, drink or picnics on the grounds', 'area', 600, 255),
               ('Paths across the grass are approximate', 'area', 250, 330),
               ('Peony Garden', 'area', 23, 512), ('Dog house', 'area', 390, 252),
               ]

# ---- the Visitor Center in town (floor V), from OpenStreetMap ------------------------------------------------------
VLAT, VLON = 41.14645, -73.4968


def V(e, n):
    return [round((e + 260) * K, 1), round((140 - n) * K, 1)]


def town():
    root = ET.parse(CACHE / 'osm_town.xml').getroot()
    nodes = {n.get('id'): (float(n.get('lat')), float(n.get('lon'))) for n in root.iter('node')}
    ways = {}
    for w in root.iter('way'):
        ways[w.get('id')] = [(round((nodes[nd.get('ref')][1] - VLON) * 111320 * math.cos(math.radians(VLAT)), 1),
                              round((nodes[nd.get('ref')][0] - VLAT) * 110540, 1))
                             for nd in w.findall('nd') if nd.get('ref') in nodes]
    return ways


def clipv(pts, x0=-255, x1=255, y0=-135, y1=135):
    return [p for p in pts if x0 <= p[0] <= x1 and y0 <= p[1] <= y1]


def town_floor(ways):
    elm = sorted(clipv(ways['1473995961'] + ways['261576073'] + ways['38605667']), key=lambda p: p[0])
    park = sorted(clipv(ways['39689980'] + ways['1473995962'] + ways['616932667']), key=lambda p: p[1])
    vc = ways['365100513'][:-1]
    st = ways['327715962'][:-1]
    sx0 = sum(p[0] for p in st) / len(st); sy0 = sum(p[1] for p in st) / len(st)
    rooms = [
        ('Elm Street', 'corridor', 'Elm Street', band(elm, 5), None),
        ('Park Street', 'corridor', 'Park Street', band(park, 5), None),
        ('Visitor Center', 'gallery', 'Glass House Visitor Center + Design Store, 199 Elm Street: check in here 20 '
                                      'minutes before your tour; every tour leaves and returns here by shuttle', vc,
         'Visitor Center'),
        ('New Canaan Station', 'space', 'New Canaan station (Metro-North, New Canaan Branch), across the street',
         ways['327715962'][:-1], None),
        ('Platform', 'space', 'Train platform', band(ways['327715963'], 2.5), None),
        ('Station Walk', 'corridor', 'Across Elm Street to the station', band([(sx0, sy0), (sx0 + 12, sy0 + 40)], 2),
         None),
        ('Park Street Lot', 'space', 'Municipal lot on Park Street, just past No. 72: free for up to 3 hours. '
                                     'Recommended for the 9:45 and 10:30 am tours on Mon, Thu and Fri',
         ways['219393358'][:-1], None),
    ]
    doors = [('Visitor Center', 'Elm Street', None), ('Station Walk', 'Elm Street', None),
             ('Station Walk', 'New Canaan Station', None), ('Station Walk', 'Platform', None),
             ('Park Street Lot', 'Park Street', None), ('Elm Street', 'Park Street', None)]
    # door points: nearest points of each pair
    def near(a, b):
        pa = dict((r[0], r[3]) for r in rooms)
        best = min(((p, q) for p in pa[a] for q in pa[b]), key=lambda t: math.dist(t[0], t[1]))
        return ((best[0][0] + best[1][0]) / 2, (best[0][1] + best[1][1]) / 2)
    doors = [(a, b, near(a, b)) for a, b, _ in doors]
    cx = sum(p[0] for p in vc) / len(vc); cy = sum(p[1] for p in vc) / len(vc)
    sx, sy = sx0, sy0
    amen = [('entrance', *doors[0][2]), ('info', cx, cy + 3), ('shop', cx - 4, cy - 3)]
    labels = [('← P · Lumberyard Lot, 244 Elm St (west along Elm St): free after 10:30 am, 5 min walk', 'area', -170, -50),
              ('Shuttle to the Glass House (about 10 minutes)', 'area', cx - 30, cy + 22),
              ('Restrooms: ask at the desk (not published)', 'area', cx + 20, cy - 20),
              ('Trains from Grand Central (change at Stamford off-peak)', 'area', sx - 20, sy - 25)]
    return rooms, doors, amen, labels


def build_floors():
    t_rooms, t_doors, t_amen, t_labels = town_floor(town())
    spec = [
        ('G', 'The Site', 'Glass House · Brick House · galleries · Studio · pond and follies', 0, S,
         SITE_ROOMS, SITE_DOORS, SITE_AMEN, SITE_LABELS),
        ('V', 'Visitor Center', 'In town, 199 Elm St: check-in, Design Store, the shuttle, parking, the train', 1, V,
         t_rooms, t_doors, t_amen, t_labels),
    ]
    floors, seen = [], set()
    for fid, label, area, order, P_, rooms_in, doors_in, amen, labels in spec:
        rooms = []
        for rid, kind, name, poly, short in rooms_in:
            assert rid not in seen, rid
            seen.add(rid)
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': [P_(*q) for q in poly]}
            if kind == 'gallery': r['label'] = short or rid
            rooms.append(r)
        ids = {r['id'] for r in rooms}
        doors = [{'a': a, 'b': b, 'at': P_(x, y), 'width': 10, 'axis': 'o'} for a, b, (x, y) in doors_in]
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order, 'transform': [1, 0, 0],
                       'rooms': rooms, 'closed': [],
                       'amenities': [{'type': t, 'at': P_(x, y)} for t, x, y in amen],
                       'labels': [{'text': t, 'kind': k, 'at': P_(x, y)} for t, k, x, y in labels],
                       'doors': doors,
                       **({'homeView': ['Glass House', 'Brick House', 'Painting Gallery', 'Sculpture Gallery',
                                        'Da Monsta', 'Studio']} if fid == 'G' else {})})
    return {'about': 'Built by tools/build_glasshouse.py. The site is traced from the Glass House’s own site map '
                     '(turned so north is up; about 1.55 px per metre). Footpaths across the grass are approximate. '
                     'The Visitor Center in town is from OpenStreetMap; its inside is not published.',
            'source': 'The Glass House site map (theglasshouse.org Explore pages), OpenStreetMap (Visitor Center, '
                      'streets, station), the Glass House visit, hours, FAQ and policies pages',
            'units': f'metres x {K}, north up', 'defaultFloor': 'G', 'galleryWord': 'Building', 'floors': floors}


# ---- the works -------------------------------------------------------------------------------------------------------
GH = 'The Glass House (National Trust for Historic Preservation)'
# buildings: id, title, date, room, explore page, photo (wp-content/uploads path), text
BUILDINGS = [
    ('glass-house', 'The Glass House', '1949', 'Glass House', 'the-glass-house',
     '2014/10/GH_5_16_2017_shot_1-1365x1024.jpg',
     'A pavilion for looking at the landscape: 55 by 33 feet, with a glass door in the middle of each wall. Johnson '
     'lived here from 1949 until his death in 2005. There are no walls inside, but he called the areas “rooms”: '
     'kitchen, dining, living room, bedroom, hearth and a brick cylinder with the bathroom. Most of the furniture is by '
     'Mies van der Rohe, who designed the daybed for Johnson. Johnson said it was the only house where you can see the '
     'sunset and the moonrise at once.'),
    ('brick-house', 'The Brick House', '1949', 'Brick House', 'brick-house', '2025/01/BH-for-homepage-1536x1024.jpg',
     'The other half of the composition: as long as the Glass House but half as deep, and almost windowless, with round '
     'windows at the back (after Brunelleschi’s dome in Florence). It holds the heating and support for both houses. '
     'In 1953 Johnson remade the inside: a skylit corridor with prints by Brice Marden, a reading room with his own '
     'library, and a bedroom under low white vaults after Sir John Soane, lined in Fortuny fabric. Restored in 2024.'),
    ('painting-gallery', 'The Painting Gallery', '1965', 'Painting Gallery', 'painting-gallery',
     '2015/02/Painting-Gallery-int_Paul-Warchol-1544x1024.jpg',
     'Half sunk into a grassy mound with a red sandstone entrance, so it would not spoil the view from the Glass House. '
     'Inside are three round rooms with rotating racks like postcard stands: two paintings per spindle, 42 in all, six '
     'on show at a time. Works by Frank Stella, Andy Warhol, Robert Rauschenberg, David Salle, Cindy Sherman and Julian '
     'Schnabel. You may walk up onto the roof.'),
    ('sculpture-gallery', 'The Sculpture Gallery', '1970', 'Sculpture Gallery', 'sculpture-gallery',
     '2015/02/sculpture-gallery-1-robinhilll-1536x1024.jpg',
     'Inspired by Greek island villages where “every street is a staircase”: squares at 45 degrees, stairs spiralling '
     'down past bays of sculpture, under a glass roof whose steel rafters cast patterns of light. Johnson called it the '
     'best single room he ever designed. Skylights replaced in 2015.'),
    ('studio', 'The Studio (Library)', '1980', 'Studio', 'studio', '2015/02/GH_6_15_2017-Shot-14-1365x1024.jpg',
     'Johnson’s one-room library and workplace, “an air-conditioned monk’s cell”, reached through a field of tall '
     'grass: 1,400 architecture books, a fireplace, no bathroom, light from the skylight in its cone. From the Glass '
     'House dining table he watched the light change on the cone.'),
    ('ghost-house', 'The Ghost House', '1984', 'Ghost House', 'ghost-house', '2015/02/ghost-house-highsmith-2-1680x856.jpg',
     'A folly of chain-link fence in the shape of a simple house, on the stone foundation of a burnt barn: a nod to '
     'Frank Gehry’s ordinary materials and to Venturi and Scott Brown. It kept animals off the lilies inside.'),
    ('da-monsta', 'Da Monsta', '1995', 'Da Monsta', 'da-monsta', '2015/02/da-monsta-1-e1429743946174-1680x1024.jpg',
     'Johnson’s last building here, by the entrance: warped, torqued walls of sprayed concrete, far from the straight '
     'lines of the International Style. First called “Dresden Zwei” after a museum design by Frank Stella; the name '
     'came from a talk with the critic Herbert Muschamp. Today it holds the exhibitions.'),
    ('pavilion', 'Pavilion in the Pond', '1962', 'Pavilion in the Pond', 'pavilion-in-the-pond',
     '2015/02/GH_6_15_2017-Shot-8-1365x1024.jpg',
     'Prefabricated concrete arches on the edge of the pond Johnson dug, built smaller than life so it looks further '
     'away: a tall person can’t stand up inside, and a child “feels like a king”. It once had a 20-foot fountain.'),
    ('kirstein', 'Monument to Lincoln Kirstein', '1985', 'Kirstein Tower', 'monument-to-lincoln-kirstein',
     '2015/02/Kirstein-Highsmith-1680x857.jpg',
     'A 30-foot tower of stacked concrete blocks and steep steps, “a staircase to nowhere”, named for Johnson’s friend '
     'who founded the New York City Ballet. Kirstein chose an inscription for the top step, which only climbers read.'),
    ('vernacular', 'Popestead, Calluna Farms and Grainger', 'c. 1783–1920', 'Popestead', 'vernacular-buildings',
     '2015/02/Vernacular-Building.jpg',
     'Three older houses Johnson and his partner David Whitney bought and restored: Popestead (a barn turned house), '
     'Calluna Farms (Whitney’s home, 1905) and Grainger (an 18th-century central-chimney house). Not open on regular '
     'tours.'),
    ('succulent', 'The Succulent Garden', '1989', 'Succulent Garden', 'vernacular-buildings',
     '2015/02/SOT_215NY8273.jpg',
     'David Whitney’s garden in front of Calluna, laid out after a Suprematist drawing by Kazimir Malevich, on pink '
     'granite left over from Johnson’s AT&T Building.'),
    ('peony', 'The Peony Garden', '1991', 'Grainger', 'vernacular-buildings', '2015/02/peony-garden-web.jpg',
     'Whitney’s garden at Grainger: 10 tree peonies, 41 peonies and 25 irises, with Alessandro Twombly’s sculpture '
     'Nature Amassment #4. Only Whitney was allowed to work in it.'),
    ('landscape', 'The landscape', '1945–2005', 'Grounds', 'landscape', '2015/02/landscape-footbridge-1539x1024.jpg',
     'Johnson bought the first five acres in 1945 and, with Whitney, grew the site to 49. Old stone walls, barn '
     'foundations and big trees became its “organizing principle”; woods were cleared to open views to buildings he '
     'called “events on the landscape”, after English gardens such as Stourhead and Stowe. “To me, it’s one art.”'),
]

# collection pages: slug -> (room, guessed?)
PLACE = {
    'nicholas-poussin-burial-of-phocion-ca-1648-49': ('Glass House', False),
    'elie-nadelman-two-circus-women-1930': ('Glass House', False),
    'donald-judd-untitled-1971': ('Judd Sculpture', False),
    'julian-schnabel-ozymandias-1986-90': ('Schnabel Sculpture', True),
    'lynn-davis-library-pagan-burma-1993': ('Brick House', True),
    'lynn-davis-minaret-port-of-mokka-yemen-1996': ('Brick House', True),
    'lynn-davis-tomb-palmyra-syria-1995': ('Brick House', True),
}
SCULPTORS = ('michael-heizer', 'robert-rauschenberg-empire', 'george-segal', 'john-chamberlain',
             'frank-stella-raft-of-medusa', 'bruce-nauman', 'robert-morris', 'andrew-lord')
NOT_WORKS = ('conservation', 'restoration', 'repair', 'replacement', 'glass-house-', 'bedroom', 'promontory',
             'architecturaldrawings', 'donald-judd', 'nicolas-poussin', 'biography', 'david-whitney',
             'bloomberg', 'modern-homes', 'anni-albers', 'national-register', 'civics', 'texture-transparency')


def text_of(s):
    s = re.sub(r'(?s)<(script|style|noscript|svg)[^>]*>.*?</\1>', '', s)
    s = re.sub(r'<br\s*/?>|</p>|</h\d>|</li>|</div>', '\n', s)
    t = html.unescape(re.sub(r'<[^>]+>', '', s))
    return [l.strip() for l in t.split('\n') if l.strip()]


def collection():
    rows = []
    for f in sorted((CACHE / 'learn').glob('learn_*.html')):
        slug = f.stem[len('learn_'):]
        if (any(k in slug for k in NOT_WORKS) and slug not in PLACE) or slug == 'donald-judd':
            continue
        s = f.read_text(encoding='utf-8', errors='ignore')
        lines = text_of(s)
        try:
            i = next(i for i, l in enumerate(lines) if l.startswith('Home »'))
        except StopIteration:
            continue
        lines = lines[i + 1:]
        lines = lines[:next((j for j, l in enumerate(lines) if l in ('share', 'Related Content')), len(lines))]
        lines = [l for l in lines if not l.startswith('Collection')]
        heading = lines[0]
        caption = lambda l: (l.lower().startswith(('photo', 'image', '©', 'art ©')) or '©' in l or 'Photo by' in l
                             or 'Collection of' in l or l == heading)
        who = heading.split(',')[0].strip()
        start = next((j for j in range(1, len(lines)) if lines[j] == who), 1)
        body = [l for l in lines[start:] if not caption(l)]
        if body and body[0].startswith(who + ','):                       # "Frank Stella, Averroes, 1960"
            body = [who, body[0][len(who) + 1:].strip()] + body[1:]
        elif who not in lines[1:]:                                         # only the heading names the work
            body = [who, heading[len(who) + 1:].strip()] + body
        img = re.search(r'imgbg="([^"]+)"', s)
        credit = next((m.group(1) for l in lines[1:6] for m in [re.search(r'Photo(?:graph)? by ([^.,]+)', l)] if m),
                      None)
        if len(body) < 2: continue
        artist = body[0]
        m = re.match(r'(.*?),\s*((?:ca\.\s*)?\d{4}(?:[–-]\d{2,4})?)\s*$', body[1])
        title, date = (m.group(1), m.group(2)) if m else (body[1], None)
        title = re.sub(r',\s*\d{4}\.?$', '', title).strip()          # "Library, Pagan, Burma, 1993., 1993"
        rest = body[2:]
        medium = rest[0] if rest else None
        desc = ' · '.join(rest[1:]) if len(rest) > 1 else ''
        if slug in PLACE:
            room, guessed = PLACE[slug]
        elif any(slug.startswith(p) for p in SCULPTORS):
            room, guessed = 'Sculpture Gallery', True
        else:
            room, guessed = 'Painting Gallery', True
        rows.append(dict(slug=slug, title=title, artist=artist, date=date, medium=medium, desc=desc, room=room,
                         guessed=guessed, img=img.group(1) if img else None,
                         credit=credit.strip() if credit else None))
    return rows


def fetch(url, dest):
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
        time.sleep(10)                                          # robots.txt: Crawl-delay 10
        if not out: return None
        dest.write_bytes(out)
    return dest


def picture(key, url):
    if not url: return None
    raw = fetch(url, CACHE / 'img' / f'{key}.bin')
    if not raw: return None
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
    return f'data/glasshouse/images/{key}.jpg'


def year(date):
    m = re.search(r'\d{4}', date or '')
    return int(m.group()) if m else None


def build_works(floors):
    names = {r['id']: (r['name'], f['id']) for f in floors['floors'] for r in f['rooms']}
    works = []
    up = 'https://pjglasshouse.wpenginepowered.com/wp-content/uploads/'
    for wid, title, date, room, page, photo, text in BUILDINGS:
        key = 'gh-' + wid
        name, floor = names[room]
        a = {'id': key, 'title': title, 'artist': 'Philip Johnson' if wid not in (
            'vernacular', 'succulent', 'peony') else 'David Whitney' if wid != 'vernacular' else 'Building',
             'date': date, 'year': year(date), 'type': 'Garden' if wid in ('succulent', 'peony', 'landscape')
             else 'Building', 'description': text, 'url': f'{SITE}/explore/{page}/',
             'image': picture(key, up + photo), 'imageCredit': GH, 'gallery': room, 'galleryName': name,
             'floor': floor, 'placeNote': 'Place from the Glass House’s own site map.'}
        works.append({k: v for k, v in a.items() if v not in (None, '')})
    for w in collection():
        key = 'gh-' + w['slug'][:60]
        name, floor = names[w['room']]
        desc = ' · '.join(x for x in (w['medium'], w['desc']) if x)
        a = {'id': key, 'title': w['title'], 'artist': w['artist'], 'date': w['date'], 'year': year(w['date']),
             'type': 'Photograph' if re.search(r'photograph|gelatin', w['medium'] or '', re.I) else
             'Sculpture' if w['room'] in ('Sculpture Gallery', 'Judd Sculpture', 'Schnabel Sculpture')
             or 'Nadelman' in w['artist'] else 'Painting', 'medium': w['medium'],
             'description': desc + ('. The Painting Gallery’s racks rotate: ask whether it is out today.'
                                    if w['room'] == 'Painting Gallery' else ''),
             'url': f'{SITE}/learn/{w["slug"]}/', 'image': picture(key, w['img']),
             'imageCredit': GH + (f' · photo {w["credit"]}' if w['credit'] else ''),
             'gallery': w['room'], 'galleryName': name, 'floor': floor,
             'placeNote': ('In the Glass House collection; the building it is in is our guess (the collection pages '
                           'don’t say).' if w['guessed'] else 'Place from the Glass House’s own pages.')}
        if w['guessed']: a['placeGuessed'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '')})
    # the current exhibition
    works.append({'id': 'gh-catch-one', 'title': 'Tomashi Jackson and Robert Rauschenberg: The Catch One',
                  'artist': 'Exhibition', 'date': '2026', 'year': 2026, 'type': 'Exhibition',
                  'description': 'This season’s exhibition (April 16 – December 14, 2026): new work by Tomashi Jackson '
                                 'shown with Robert Rauschenberg. Where on the site it is shown is our guess.',
                  'url': f'{SITE}/whats-on/tomashi-jackson-robert-rauschenberg/', 'gallery': 'Da Monsta',
                  'galleryName': names['Da Monsta'][0], 'floor': 'G', 'placeGuessed': True,
                  'placeNote': 'Building guessed.'})
    return {'source': 'The Glass House (theglasshouse.org: Explore pages and collection pages)',
            'checked': time.strftime('%Y-%m-%d'), 'count': len(works), 'complete': False, 'artworks': works}


def build_guide(works):
    rows = [{k: v for k, v in {
        'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'), 'year': a.get('year'),
        'url': a['url'], 'imageUrl': a.get('image'), 'onView': True, 'gallery': a['gallery'],
        'floor': a['floor']}.items() if v not in (None, '')} for a in works['artworks']]
    return {'museum': MUSEUM, 'name': 'The Glass House', 'checked': works['checked'], 'source': works['source'],
            'onViewKnown': True,
            'note': 'Philip Johnson’s 49-acre site, seen on guided tours from the Visitor Center in town: the 14 '
                    'buildings and follies, and the paintings and sculptures he and David Whitney collected. The '
                    'Painting Gallery’s racks rotate, so only some paintings are out on a given day.',
            'works': rows}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works = build_works(floors)
    if '--check' in sys.argv:
        for a in works['artworks']: print(a['gallery'], '|', a['artist'], '|', a['title'], '|', a.get('date'))
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
