#!/usr/bin/env python3
"""Build The Mount (Edith Wharton's home, Lenox, MA) map guide (run: python3 tools/build_mount.py).

    data/mount/floors.json     the estate from above (floor G) and the three public floors of the Mansion (1-3)
    data/mount/artworks.json   the rooms, Wharton's own books, the gardens, and NightWood
    data/mount/images/         pictures, made smaller for phones
    data/guides/<QID>.json     the same list for the museum page

The map. The Mount publishes no floor plan and no grounds map, so:
  - Grounds (floor G): OpenStreetMap (api.openstreetmap.org/api/0.6/map, cached in .cache/mount/osm.xml): the Mansion,
    Stable, Ticket Booth, parking, entrance drive, the walk to the Mansion, the Lime Walk, the Walled (Italian) and Flower
    Gardens and the woodland trails. Everything is turned 16.6 degrees so the Mansion stands straight: north is a little
    to the left of up. The Rock Garden and Grass Steps are placed by hand (approximate).
  - Mansion (floors 1-3): APPROXIMATE. Drawn from The Mount's own room list and sizes (edithwharton.org/the-estate:
    entrance hall 34.5 x 12.5 ft, gallery 38 x 12, drawing room 36 x 20, library 20 x 25, den 15 x 18, dining room
    20.5 x 25.5, terrace 125 x 24 along the east front; the service wing to the south), its accessibility page (three
    public floors, elevator at the end of the service wing, restrooms across from it on floors 1 and 2, the Sewing Room
    first on the right on floor 3, accessible entrance right of the Forecourt) and the bookstore page (in the old
    laundry, ground floor). Floors use the museum's own numbering: 1 ground (entrance), 2 main (piano nobile), 3 bedrooms.

The works. Pages of edithwharton.org (WordPress; robots.txt allows every robot), read once by tools/harvest_mount.py:
the rooms on the Mansion tour, the six "Library Insights" books from Wharton's own 2,700-volume library (in the
Library), the gardens, the Stable, NightWood (Nov 21, 2026 - Jan 2, 2027) and the 2026 outdoor sculpture show (ended Oct
24, listed but not placed). Pictures come from the museum's media library (photographers credited as the museum does).
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
from build_osv import poly_line_gap, band, along  # noqa: E402  (shared geometry)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'mount'
CACHE = ROOT / '.cache' / 'mount'
MUSEUM = 'Q7752461'
SITE = 'https://edithwharton.org'
UP = SITE + '/wp-content/uploads/'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SOURCE = ('OpenStreetMap (grounds) and The Mount’s own descriptions of the house (edithwharton.org: The Estate, '
          'Accessibility, Bookstore); the Mansion floors are approximate')

LAT0, LON0 = 42.3310, -73.2820
TURN = math.radians(16.6)        # the Mansion's long side runs 16.6 degrees west of north
U = 1 / 0.35                     # map units per metre (the app's walking scale: 0.35 m per unit)
HS = 5                           # house drawings: units per foot
FT = 0.3048


# ---- the grounds (OpenStreetMap) --------------------------------------------------------------------------------
def osm():
    f = CACHE / 'osm.xml'
    if not f.exists():
        out = subprocess.run(['curl', '-s', '-f', '-m', '120', '-A', UA,
                              'https://api.openstreetmap.org/api/0.6/map?bbox=-73.2905,42.3255,-73.2775,42.3345'],
                             capture_output=True, check=True).stdout
        f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(out)
    t = ET.parse(f).getroot()
    nodes = {n.get('id'): (float(n.get('lat')), float(n.get('lon'))) for n in t.findall('node')}
    ntags = {n.get('id'): {x.get('k'): x.get('v') for x in n.findall('tag')} for n in t.findall('node')}
    ways = {w.get('id'): {'nodes': [n.get('ref') for n in w.findall('nd')],
                          'tags': {x.get('k'): x.get('v') for x in w.findall('tag')}} for w in t.findall('way')}
    return nodes, ntags, ways


def metres(lat, lon):
    """Metres east/south of the reference point, turned so the Mansion stands straight."""
    x = (lon - LON0) * 111320 * math.cos(math.radians(LAT0))
    y = -(lat - LAT0) * 110540
    c, s = math.cos(TURN), math.sin(TURN)
    return x * c + y * s, -x * s + y * c


def G(lat, lon):
    x, y = metres(lat, lon)
    return [round(x * U, 1), round(y * U, 1)]


# ---- the Mansion, in feet (x east, y south, origin: north-west corner of the main block) -------------------------
def R(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


MAIN = R(0, 0, 40, 92)                 # main block
WING = R(0, 92, 30, 138)               # service wing (south)
TERRACE = [[0, -24], [64, -24], [64, 101], [40, 101], [40, 0], [0, 0]]   # along the east front, round to the north

# id, kind, name, polygon (feet), label
FLOORS = {
    '1': {
        'label': 'Mansion · Floor 1 (ground)', 'area': 'Entrance Hall · Bookstore · kitchen · restrooms · elevator',
        'rooms': [
            ('Front Forecourt', 'space', 'The walled Forecourt (64 × 78 ft): the front door is on its east side',
             R(-64, 10, 0, 88), None),
            ('Entrance Hall', 'gallery', 'Entrance Hall: the grotto-like hall you enter from the Forecourt',
             R(0, 18.5, 12.5, 53), 'Entrance Hall'),
            ('Lower Staircase Hall', 'corridor', 'Staircase hall: the stairs up to the main floor', R(0, 53, 12, 71), None),
            ('Ground Floor Passage', 'corridor', 'Passage to the service wing', R(0, 71, 12, 92), None),
            ('Service Hall (ground)', 'corridor', 'Service wing hall', R(12, 92, 18, 138), None),
            ('Kitchen', 'gallery', 'Kitchen and scullery', R(0, 92, 12, 112), 'Kitchen'),
            ('Servants’ Dining Room', 'gallery', 'Servants’ Dining Room', R(0, 112, 12, 124), 'Servants’ Hall'),
            ('Bookstore', 'gallery', 'The Mount Gift & Bookstore (the old laundry; no ticket needed)',
             R(18, 92, 30, 118), 'Bookstore'),
            ('Restrooms (floor 1)', 'space', 'Restrooms (gender-neutral, accessible, changing table)',
             R(0, 124, 12, 138), None),
            ('Elevator (floor 1)', 'space', 'Elevator', R(18, 128, 30, 138), None),
            ('Accessible Entrance', 'space', 'Accessible entrance (right of the Forecourt, by the accessible parking)',
             R(18, 118, 30, 128), None),
        ],
        'closed': [R(12.5, 0, 40, 92), R(0, 0, 12.5, 18.5)],
        'doors': [('Front Forecourt', 'Entrance Hall', (0, 36)), ('Entrance Hall', 'Lower Staircase Hall', (6, 53)), ('Lower Staircase Hall', 'Ground Floor Passage', (6, 71)),
                  ('Ground Floor Passage', 'Kitchen', (6, 92)), ('Kitchen', 'Service Hall (ground)', (12, 102)),
                  ('Ground Floor Passage', 'Service Hall (ground)', (12, 90)),
                  ('Servants’ Dining Room', 'Service Hall (ground)', (12, 118)),
                  ('Restrooms (floor 1)', 'Service Hall (ground)', (12, 131)),
                  ('Bookstore', 'Service Hall (ground)', (18, 105)), ('Elevator (floor 1)', 'Service Hall (ground)', (18, 133)),
                  ('Accessible Entrance', 'Service Hall (ground)', (18, 123))],
        'amenities': [('entrance', (-2, 36)), ('stairs', (6, 62)), ('elevator', (24, 133)), ('restroom-all', (6, 131)),
                      ('shop', (24, 105)), ('entrance', (32, 123))],
        'labels': [('Front door', 'note', (-14, 30)),
                   ('Not open to visitors', 'note', (26, 45)),
                   ('Room shapes approximate: The Mount publishes no floor plan', 'note', (20, 150))],
    },
    '2': {
        'label': 'Mansion · Floor 2 (main floor)',
        'area': 'Gallery · Drawing Room · Library · Den · Dining Room · Terrace Café · restrooms',
        'rooms': [
            ('Gallery', 'gallery', 'The Gallery: the vaulted hall that opens to every room on this floor', R(0, 15, 12, 53),
             'Gallery'),
            ('Den', 'gallery', 'Teddy Wharton’s Den', R(0, 0, 18, 15), 'Den'),
            ('Library', 'gallery', 'Edith Wharton’s Library', R(18, 0, 40, 20), 'Library'),
            ('Drawing Room', 'gallery', 'Drawing Room', R(12, 20, 40, 56), 'Drawing Room'),
            ('Dining Room', 'gallery', 'Dining Room', R(12, 56, 40, 81), 'Dining Room'),
            ('Staircase Hall', 'corridor', 'Staircase hall', R(0, 53, 12, 71), None),
            ('Butler’s Pantry', 'gallery', 'Butler’s pantry and the passage to the service wing',
             [[0, 71], [12, 71], [12, 81], [40, 81], [40, 92], [0, 92]],
             'Butler’s Pantry'),
            ('Service Hall (main)', 'corridor', 'Servants’ hallway', R(12, 92, 18, 138), None),
            ('Household Offices', 'gallery', 'Housekeeper’s, butler’s and cook’s rooms (household management)',
             R(0, 92, 12, 124), 'Housekeeper'),
            ('Brush Room', 'gallery', 'Brush room (shoes and outdoor wear were cleaned here)', R(18, 92, 30, 118),
             'Brush Room'),
            ('Restrooms (floor 2)', 'space', 'Restrooms (gender-neutral, accessible, changing table)',
             R(0, 124, 12, 138), None),
            ('Elevator (floor 2)', 'space', 'Elevator', R(18, 128, 30, 138), None),
            ('Terrace', 'gallery', 'The Terrace and the Terrace Café (in season), over the gardens', TERRACE, 'Terrace'),
        ],
        'closed': [R(18, 118, 30, 128)],
        'doors': [('Gallery', 'Den', (6, 15)), ('Den', 'Library', (18, 8)), ('Gallery', 'Drawing Room', (12, 36)),
                  ('Library', 'Drawing Room', (29, 20)), ('Drawing Room', 'Dining Room', (26, 56)),
                  ('Gallery', 'Staircase Hall', (6, 53)), ('Staircase Hall', 'Dining Room', (12, 64)),
                  ('Staircase Hall', 'Butler’s Pantry', (6, 71)), ('Dining Room', 'Butler’s Pantry', (26, 81)),
                  ('Butler’s Pantry', 'Service Hall (main)', (15, 92)), ('Household Offices', 'Service Hall (main)', (12, 108)),
                  ('Brush Room', 'Service Hall (main)', (18, 105)), ('Restrooms (floor 2)', 'Service Hall (main)', (12, 131)),
                  ('Elevator (floor 2)', 'Service Hall (main)', (18, 133)),
                  ('Drawing Room', 'Terrace', (40, 38)), ('Dining Room', 'Terrace', (40, 68)), ('Library', 'Terrace', (29, 0))],
        'amenities': [('stairs', (6, 62)), ('elevator', (24, 133)), ('restroom-all', (6, 131)), ('dining', (52, 50))],
        'labels': [('Palladian staircase down to the gardens', 'note', (82, 45)),
                   ('The Terrace Café is open May–October', 'note', (82, 80)),
                   ('Room shapes approximate: The Mount publishes no floor plan', 'note', (20, 150))],
    },
    '3': {
        'label': 'Mansion · Floor 3 (bedrooms)',
        'area': 'Edith Wharton’s bedroom and boudoir · guest suites · Sewing Room · exhibits',
        'rooms': [
            ('Bedroom Hall', 'corridor', 'The bedroom hall (about 95 ft long)', R(12, 0, 18, 95), None),
            ('Boudoir', 'gallery', 'Edith Wharton’s Boudoir', R(0, 0, 12, 18), 'Boudoir'),
            ('Edith’s Bath', 'space', 'Edith Wharton’s bathroom', R(0, 18, 12, 28), None),
            ('Edith’s Bedroom', 'gallery', 'Edith Wharton’s Bedroom', R(18, 0, 40, 22), 'Edith’s Bedroom'),
            ('West Guest Suite', 'gallery', 'Two-room guest suite (west side, over the Forecourt)', R(0, 28, 12, 62),
             'Guest Suite'),
            ('Teddy’s Bedroom', 'gallery', 'Teddy Wharton’s bedroom, bath and dressing room', R(18, 22, 40, 46),
             'Teddy’s Room'),
            ('Henry James Suite', 'gallery', 'The Henry James suite: the largest guest bedroom', R(18, 46, 40, 72),
             'Henry James Suite'),
            ('Upper Staircase Hall', 'corridor', 'Staircase hall', R(0, 62, 12, 80), None),
            ('Exhibit Rooms', 'gallery', 'Rooms with The Mount’s informational exhibits (place approximate)',
             R(18, 72, 40, 95), 'Exhibits'),
            ('Service Hall (upper)', 'corridor', 'Service wing hall', R(12, 95, 18, 138), None),
            ('Sewing Room', 'gallery', 'Sewing Room and Wharton’s dress closet (the wheelchair lift is here)',
             R(18, 118, 30, 128), 'Sewing Room'),
            ('Maid’s Room', 'gallery', 'Linen closet, housemaid’s closet and the lady’s maid’s room', R(0, 95, 12, 138),
             'Maid’s Room'),
            ('Elevator (floor 3)', 'space', 'Elevator', R(18, 128, 30, 138), None),
        ],
        'closed': [R(0, 80, 12, 95), R(18, 95, 30, 118)],
        'doors': [('Bedroom Hall', 'Boudoir', (12, 9)), ('Boudoir', 'Edith’s Bedroom', (12, 4)),
                  ('Bedroom Hall', 'Edith’s Bedroom', (18, 12)), ('Boudoir', 'Edith’s Bath', (6, 18)),
                  ('Bedroom Hall', 'West Guest Suite', (12, 45)), ('Bedroom Hall', 'Teddy’s Bedroom', (18, 34)),
                  ('Bedroom Hall', 'Henry James Suite', (18, 58)), ('Bedroom Hall', 'Upper Staircase Hall', (12, 71)),
                  ('Bedroom Hall', 'Exhibit Rooms', (18, 84)), ('Bedroom Hall', 'Service Hall (upper)', (15, 95)),
                  ('Service Hall (upper)', 'Sewing Room', (18, 123)), ('Service Hall (upper)', 'Maid’s Room', (12, 110)),
                  ('Service Hall (upper)', 'Elevator (floor 3)', (18, 133))],
        'amenities': [('stairs', (6, 71)), ('elevator', (24, 133))],
        'labels': [('No restrooms on this floor: they are on floors 1 and 2', 'note', (20, 150)),
                   ('Wheelchair lift in the Sewing Room, from the service wing to the rest of the floor', 'note', (60, 123)),
                   ('Room shapes approximate: The Mount publishes no floor plan', 'note', (20, -14))],
    },
}


def house_frame(nodes, ways):
    """Where the Mansion's feet drawing sits on the grounds: [scale, dx, dy] and a feet -> grounds function."""
    pts = [metres(*nodes[n]) for n in ways['213733157']['nodes']]
    east = max(p[0] for p in pts); north = min(p[1] for p in pts)
    ox, oy = (east - 40 * FT - 2.5) * U, north * U        # the terrace side lines up with OpenStreetMap's east wall
    # The house floors are drawn larger than life (5 units per foot, about 5.7 times the grounds' scale) so rooms are
    # big enough to read; they are centred on the Mansion's place on the grounds and walk at their true size.
    cx, cy = ox + 20 * FT * U, oy + 69 * FT * U
    transform = [1, round(cx - 20 * HS, 1), round(cy - 69 * HS, 1)]
    return transform, (lambda x, y: [round(ox + x * FT * U, 1), round(oy + y * FT * U, 1)])


def F(p):
    return [round(p[0] * HS, 1), round(p[1] * HS, 1)]


def build_house_floor(fid, spec, order, transform):
    rooms = []
    for rid, kind, name, pg, label in spec['rooms']:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': [F(p) for p in pg], 'z': 2}
        if label: r['label'] = label
        if rid == 'Terrace': r['labelAt'] = F((52, 40))
        rooms.append(r)
    doors = []
    for a, b, p in spec['doors']:
        doors.append({'a': a, 'b': b, 'at': F(p), 'width': 20, 'axis': 'o'})
    return {'id': fid, 'label': spec['label'], 'order': order, 'area': spec['area'], 'transform': transform,
            'walkScale': round(FT * U / HS, 4),
            'rooms': rooms, 'closed': [{'poly': [F(p) for p in pg]} for pg in spec['closed']],
            'amenities': [{'type': t, 'at': F(p)} for t, p in spec['amenities']],
            'labels': [{'text': t, 'kind': k, 'at': F(p)} for t, k, p in spec['labels']],
            'doors': doors, 'homeView': [r['id'] for r in rooms if r['kind'] == 'gallery']}


# walkways: OpenStreetMap way -> (name, half width in map units)
WALKS = {
    '449213720': ('Entrance drive from Plunkett Street', 9),
    '449213702': ('Drive past the Stable', 8),
    '705739569': ('Parking lot lane', 7),
    '397355088': ('Walk to the Mansion (about ¼ mile; golf cart on request)', 7),
    '636378245': ('Path from the Mansion to the Flower Garden', 5),
    '636378244': ('Grass steps from the Terrace toward the Walled Garden', 5),
    '1460605496': ('Flower Garden paths', 4),
    '1460605500': ('Garden loop north of the Flower Garden', 4),
    '636378242': ('Woodland trail (north)', 4),
}


def build_grounds(nodes, ntags, ways, to_g):
    def line(wid): return [G(*nodes[n]) for n in ways[wid]['nodes'] if n in nodes]
    rooms = []

    def add(rid, kind, name, pg, label=None, z=2):
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': pg, 'z': z}
        if label: r['label'] = label
        rooms.append(r); return r

    add('Grounds', 'space', 'The Mount’s grounds: 49.5 acres of meadows, woods and gardens (free, open dawn to dusk)',
        line('29787326')[:-1], z=0)
    add('Parking', 'space', 'Parking Field (free; accessible spaces in the front row)', line('705739567')[:-1], z=1)
    tb = line('705739574')[:-1]
    cx, cy = sum(p[0] for p in tb) / len(tb), sum(p[1] for p in tb) / len(tb)
    add('Ticket Booth', 'space', 'Admission Booth: tickets, maps, golf-cart help to the Mansion',
        [[round(cx - 9, 1), round(cy - 7, 1)], [round(cx + 9, 1), round(cy - 7, 1)], [round(cx + 9, 1), round(cy + 7, 1)],
         [round(cx - 9, 1), round(cy + 7, 1)]])
    add('Stable', 'gallery', 'The Stable (1902): programs, talks and restrooms', line('213733152')[:-1], 'Stable')
    # the Mansion with its terrace and forecourt, from the feet drawing
    outline = [[0, -24], [64, -24], [64, 101], [40, 101], [40, 92], [30, 92], [30, 138], [0, 138]]
    add('Mansion', 'gallery', 'The Mansion (1902): house tour, Bookstore and Terrace Café',
        [to_g(*p) for p in outline], 'The Mansion')
    add('Forecourt', 'space', 'The walled Forecourt (front door of the Mansion)', [to_g(*p) for p in R(-64, 10, 0, 88)], z=1)
    add('Italian Garden', 'gallery', 'The Italian Garden (sunken, walled, with the rock-pile fountain)',
        line('705739572')[:-1], 'Italian Garden')
    add('Flower Garden', 'gallery', 'The French Flower Garden (pool and dolphin fountain)', line('705739573')[:-1],
        'Flower Garden')
    lw = line('705739571')
    add('Lime Walk', 'gallery', 'The Lime Walk: pleached lindens between the two gardens', band(lw, 6), 'Lime Walk')
    rooms[-1]['labelAt'] = along(lw)
    add('Rock Garden', 'gallery', 'The Rock Garden and the Grass Steps (place approximate)',
        [to_g(*p) for p in [[70, 70], [130, 60], [150, 120], [80, 135]]], 'Rock Garden')
    wt = line('636378243')
    add('Woodland Walk', 'gallery', 'Woodland trail: the woods where NightWood is staged in winter', band(wt, 5),
        'Woodland Walk')
    rooms[-1]['labelAt'] = along(wt)

    # paths, joined where they share a node (or end close to another path)
    doors, walk_lines = [], []
    for wid, (name, half) in WALKS.items():
        ln = line(wid)
        rooms.append({'id': f'walk-{wid}', 'kind': 'corridor', 'name': name, 'poly': band(ln, half),
                      'labelAt': along(ln), 'z': 1})
        walk_lines.append((f'walk-{wid}', ways[wid]['nodes'], ln))
    walk_lines.append(('Lime Walk', ways['705739571']['nodes'], lw))
    walk_lines.append(('Woodland Walk', ways['636378243']['nodes'], wt))
    seen = set()
    for i, (a, an, al) in enumerate(walk_lines):
        for b, bn, bl in walk_lines[i + 1:]:
            common = set(an) & set(bn)
            if common:
                n = sorted(common)[0]
                doors.append({'a': a, 'b': b, 'at': G(*nodes[n]), 'width': 10, 'axis': 'o'}); seen.add((a, b))
    for a, an, al in walk_lines:          # ends that stop short of another path
        for end in (al[0], al[-1]):
            best = None
            for b, bn, bl in walk_lines:
                if b == a or (a, b) in seen or (b, a) in seen: continue
                d, pt = poly_line_gap([end], bl)
                if d < 12 * U and (best is None or d < best[0]): best = (d, b)
            if best:
                doors.append({'a': a, 'b': best[1], 'at': end, 'width': 10, 'axis': 'o'}); seen.add((a, best[1]))
    # each place opens onto its nearest path
    door_at = {'Mansion': to_g(-1, 36), 'Forecourt': to_g(-30, 10)}
    for r in rooms:
        if r['kind'] == 'corridor' or r['id'] in ('Grounds', 'Lime Walk', 'Woodland Walk'): continue
        best = None
        for wid, _, ln in walk_lines:
            d, pt = poly_line_gap(r['poly'], ln)
            if best is None or d < best[0]: best = (d, wid, pt)
        at = door_at.get(r['id'], [round(best[2][0], 1), round(best[2][1], 1)])
        doors.append({'a': best[1], 'b': r['id'], 'at': at, 'width': 10, 'axis': 'o'})
    doors.append({'a': 'Forecourt', 'b': 'Mansion', 'at': to_g(0, 36), 'width': 10, 'axis': 'o'})
    for a, b, p in [('Mansion', 'Rock Garden', (64, 75)), ('Rock Garden', 'Italian Garden', (110, 130)),
                    ('Mansion', 'Lime Walk', (64, 20)), ('Lime Walk', 'Italian Garden', None),
                    ('Lime Walk', 'Flower Garden', None), ('Grounds', 'Woodland Walk', None)]:
        doors.append({'a': a, 'b': b, 'at': to_g(*p) if p else (lw[0] if b == 'Italian Garden' else
                                                               lw[-1] if b == 'Flower Garden' else wt[0]),
                      'width': 10, 'axis': 'o'})

    toilets = next(G(*nodes[n]) for n, t in ntags.items() if t.get('amenity') == 'toilets')
    amen = [{'type': 'entrance', 'at': [round(cx, 1), round(cy, 1)]}, {'type': 'info', 'at': [round(cx + 14, 1), round(cy, 1)]},
            {'type': 'restroom-all', 'at': toilets}, {'type': 'entrance', 'at': to_g(-4, 36)},
            {'type': 'dining', 'at': to_g(52, 50)}, {'type': 'shop', 'at': to_g(24, 105)}]
    def lab(t, k, p): return {'text': t, 'kind': k, 'at': p}
    pk = line('705739567')
    labels = [lab('P · Parking (free)', 'area', [round(sum(p[0] for p in pk) / len(pk), 1), round(sum(p[1] for p in pk) / len(pk), 1)]),
              lab('Plunkett Street', 'note', line('449213720')[0]),
              lab('Accessible parking in front of the Mansion (placard)', 'note', to_g(-60, 120)),
              lab('Laurel Lake', 'area', G(42.3285, -73.2785)),
              lab('North is a little left of up (turned so the Mansion stands straight)', 'note', to_g(-150, -260)),
              lab('Rock Garden and Grass Steps placed approximately', 'note', to_g(110, 160))]
    return {'id': 'G', 'label': 'Grounds & gardens', 'order': 0,
            'area': 'Parking · Admission Booth · Stable (restrooms) · the walk to the Mansion · gardens · woods',
            'transform': [1, 0, 0], 'rooms': rooms, 'closed': [], 'amenities': amen, 'labels': labels, 'doors': doors,
            'homeView': ['Mansion', 'Italian Garden', 'Flower Garden', 'Stable']}


def build_floors():
    nodes, ntags, ways = osm()
    transform, to_g = house_frame(nodes, ways)
    floors = [build_grounds(nodes, ntags, ways, to_g)]
    for i, (fid, spec) in enumerate(FLOORS.items()):
        floors.append(build_house_floor(fid, spec, i + 1, transform))
    return {'about': 'Built by tools/build_mount.py. The grounds come from OpenStreetMap, turned 16.6° so the Mansion '
                     'stands straight. The Mount publishes no floor plan: the three Mansion floors are APPROXIMATE, '
                     'drawn from the museum’s own list of rooms with their sizes and its accessibility page (elevator '
                     'at the end of the service wing, restrooms across from it on floors 1 and 2).',
            'source': SOURCE, 'units': 'grounds: map units of 0.35 m; Mansion: 5 units per foot, drawn larger than life over its place on the grounds',
            'approximate': True, 'defaultFloor': '2', 'galleryWord': 'Room', 'floors': floors}


# ---- pictures ---------------------------------------------------------------------------------------------------
_last = [0.0]


def picture(key, path):
    """Download once (politely, 3 s apart) and save a phone-sized JPEG; returns the app path."""
    if not path: return None
    url = UP + urllib.parse.quote(path)
    raw = CACHE / 'img' / (key + (Path(path).suffix.lower() or '.jpg'))
    dest = OUT / 'images' / f'{key}.jpg'
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        out = b''
        for i in range(3):
            wait = _last[0] + 3 - time.time()
            if wait > 0: time.sleep(wait)
            out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
            _last[0] = time.time()
            if out: break
            time.sleep(10 * (i + 1))
        if not out: print('  no picture from', url); return None
        raw.write_bytes(out)
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        try: im = Image.open(io.BytesIO(raw.read_bytes()))
        except Exception:
            print('  not a picture:', url); raw.unlink(); return None
        im = im.convert('RGBA') if im.mode in ('P', 'LA') else im
        if im.mode == 'RGBA':
            bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=im.split()[3]); im = bg
        im = im.convert('RGB')
        im.thumbnail((1000, 1000))
        im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/mount/images/{key}.jpg'


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower().replace('’', '')).strip('-')[:40]


# ---- the works -----------------------------------------------------------------------------------------------------
# (floor, place, title, words, picture path in uploads, credit, page)
ROOMS = [
    ('1', 'Entrance Hall', 'The Entrance Hall',
     'You enter at ground level from the walled Forecourt into a cool, grotto-like hall, meant as an extension of the '
     'landscape into the house; the main rooms are a floor above, which gave Wharton privacy from arriving guests. The '
     'hall is 34½ by 12½ feet; the staircase hall leads up to the main floor.',
     None, None, 'the-estate'),
    ('1', 'Kitchen', 'The Kitchen',
     'The ground floor of the service wing held the kitchen, a scullery for washing pots and pans, the servants’ dining '
     'room and the laundry. The recreated working rooms tell the stories of Wharton’s servants: many served her for '
     'decades, others were new immigrants.',
     '2017/10/Kitchen-Stories-by-Jody-Christopherson.jpg', 'Jody Christopherson / The Mount', 'the-mansion'),
    ('1', 'Bookstore', 'The Mount Gift & Bookstore',
     'In the old laundry: books, Wharton titles, jewelry, stationery, teas and toys. Open to everyone, no house ticket '
     'needed (May 9–October daily 10–5; November–December weekends 10–3). Phone 413-551-5118.',
     '2026/03/Shopping-Options.webp', 'The Mount', 'bookstore'),
    ('2', 'Gallery', 'The Gallery',
     'The 38-foot vaulted hall on the main floor, inspired by the galleries Wharton admired in Italy. It gives each room '
     'its own door and lets air flow through the house: Wharton and Ogden Codman’s rule from The Decoration of Houses '
     '(1897) that every room should be reached without passing through another.',
     '2019/06/Gallery-by-John-Seakwood_0027.jpg', 'John Seakwood / The Mount', 'the-mansion'),
    ('2', 'Drawing Room', 'The Drawing Room',
     'The largest room in the house, 36 by 20 feet, opening onto the Terrace and the gardens. Wharton and Codman planned '
     'its proportion and symmetry down to the doors: “Before beginning to decorate a room it is essential to consider '
     'for what purpose the room is to be used.”',
     '2026/04/The-Mount-Drawing-Room-4-by-David-Dashiell.jpg-1.webp', 'David Dashiell / The Mount', 'the-mansion'),
    ('2', 'Library', 'Edith Wharton’s Library',
     'The oak-paneled library holds Wharton’s own books, about 2,700 volumes the house bought back in 2005: books from '
     'every period of her life in English, French, German and Italian, many of her own works with penciled corrections, '
     'and books inscribed by friends. She marked them gently in pencil: ticks, underlining, sometimes words. Private '
     'library tours by reservation ($150 for two).',
     '2021/02/Edith-Whartons-Library-at-The-Mount-by-Eric-Limon-Photography-1-scaled-1.jpg',
     'Eric Limon Photography / The Mount', 'the-mansion'),
    ('2', 'Den', 'Teddy Wharton’s Den',
     'Edward (Teddy) Wharton’s office, 15 by 18 feet, with French doors. A “hidden” door in the bookcase leads straight '
     'into his wife’s Library.',
     '2019/11/Teddys-Den-6_Rebecka-McDougall.jpg', 'Rebecka McDougall / The Mount', 'the-mansion'),
    ('2', 'Dining Room', 'The Dining Room',
     'A small, intimate room, 20½ by 25½ feet, opening onto the Terrace. The only photograph from the Whartons’ time '
     'shows a round table with white-painted French armchairs; the room has been re-created.',
     '2019/06/Dining-Room_Holiday_Stephanie-Zollshan.jpg', 'Stephanie Zollshan / The Mount', 'the-mansion'),
    ('2', 'Butler’s Pantry', 'The Butler’s Pantry',
     'On the main floor, the servants worked in the butler’s pantry, the brush room (for cleaning shoes and outdoor '
     'wear) and the offices of household management.',
     None, None, 'the-mansion'),
    ('2', 'Terrace', 'The Terrace and Terrace Café',
     'The Italian-inspired terrace, 125 feet long along the garden front, which Wharton asked for; a Palladian staircase '
     'leads down to the gardens. In season the Terrace Café (KJ Nosh) serves sandwiches, salads, wine and beer, first '
     'come, first served; no ticket needed. Closed for the season now.',
     '2019/06/FFF_2017_Sarah-Kenyon-22.jpg', 'Sarah Kenyon / The Mount', 'terrace-cafe'),
    ('3', 'Edith’s Bedroom', 'Edith Wharton’s Bedroom',
     'Wharton’s bedroom at the north end of the house. She preferred to write in bed in the mornings rather than in her '
     'library; she wrote The House of Mirth (1905) at The Mount.',
     '2019/11/Ediths-Bedroom-2_Rebecka-McDougall-rotated-1.jpg', 'Rebecka McDougall / The Mount', 'the-estate'),
    ('3', 'Boudoir', 'Edith Wharton’s Boudoir',
     'Her private sitting room, next to her bedroom and bath at the north end of the bedroom floor.',
     '2019/11/Ediths-Boudoir-3_Rebecka-McDougall.jpg', 'Rebecka McDougall / The Mount', 'the-estate'),
    ('3', 'Henry James Suite', 'The Henry James Suite',
     'The largest guest bedroom, on the east side, known by the name of its most famous guest. Henry James stayed at The '
     'Mount in 1904 and 1905; Wharton called him “perhaps the most intimate friend I ever had.”',
     '2023/08/Ruby-Henry-James-Room-scaled.jpg', 'The Mount', 'the-estate'),
    ('3', 'West Guest Suite', 'The West Guest Suite',
     'A two-room guest suite with its bath on the west side, over the Forecourt.', None, None, 'the-estate'),
    ('3', 'Teddy’s Bedroom', 'Teddy Wharton’s Bedroom',
     'Teddy Wharton’s bedroom, bath and dressing room on the east side, smaller than his wife’s.', None, None, 'the-estate'),
    ('3', 'Sewing Room', 'The Sewing Room',
     'On the bedroom floor of the service wing: the sewing room, a closet for Wharton’s dresses, a linen closet and her '
     'personal maid’s room. The wheelchair lift to the rest of the floor is here, first room on the right from the '
     'elevator.', None, None, 'the-mansion'),
    ('3', 'Exhibit Rooms', 'Exhibits on the third floor',
     'Informational exhibits about Wharton, her house and her household. They are not on the audio guide; staff can help '
     'with reading them (413-551-5116). Which rooms they fill isn’t published: ask on the tour.', None, None,
     'accessibility'),
    ('G', 'Mansion', 'The Mansion (1902)',
     'Wharton designed the house herself with Ogden Codman Jr. and Francis L. V. Hoppin, built July 1901 – autumn 1902. '
     'The outside, by Hoppin, follows Belton House, a 17th-century English country house; the inside follows the rules '
     'of Wharton and Codman’s The Decoration of Houses. Four stories on the entrance side, three on the garden side. '
     'One of only five percent of National Historic Landmarks dedicated to women.',
     '2020/04/1.-The-Mount-in-Snow-3-by-David-Dashiell-scaled-1.jpg', 'David Dashiell / The Mount', 'the-estate'),
    ('G', 'Mansion', 'The Mount on a tinted postcard (c. 1902–03)',
     'The earliest known picture of the finished house, before the gardens were planted.',
     '2026/04/The-Mount-tinted-postcard.webp', 'The Mount Archives', 'the-estate'),
    ('G', 'Mansion', 'West elevation by Hoppin & Koen',
     'The architects’ drawing of the entrance front.', '2026/04/Hoppin-Koen-West-Elevation-1024x634.webp',
     'The Mount Archives', 'the-estate'),
    ('G', 'Stable', 'The Stable (1902)',
     'Modeled like the house on Belton House and designed by Hoppin & Koen for the Whartons’ horses and carriages, then '
     'their motorcars. “Mr. Wharton’s pride is the stable, which is indeed one of the finest in Lenox” (1904). Today it '
     'is The Mount’s main space for talks, readings, music and films, with accessible restrooms.',
     '2021/03/Stable_May2018-scaled.jpg', 'The Mount', 'the-stable'),
    ('G', 'Italian Garden', 'The Italian Garden',
     'The sunken walled garden in serene greens and whites, with porticos and alcoves in its stone walls: a cool, shady '
     'room against the summer sun. Its centerpiece is a rustic rock-pile fountain. The ramp to it is on the path to the '
     'right of the Mansion.',
     '2021/03/Italian-Garden-by-David-Dashiell.jpg', 'David Dashiell / The Mount', 'the-gardens'),
    ('G', 'Lime Walk', 'The Lime Walk',
     'A gravel promenade of pleached linden (lime) trees joining the Italian Garden to the French Flower Garden.',
     '2020/04/The-Mount-Lime-Walk-in-mist-by-David-Dashiell-scaled-1.jpg', 'David Dashiell / The Mount', 'the-gardens'),
    ('G', 'Flower Garden', 'The French Flower Garden',
     'A rectangular pool among beds of annuals, perennials and shrubs: phlox, stocks, lilies, hydrangea, dianthus, '
     'delphinium and dahlias, all flowers Wharton loved.',
     '2020/04/The-Mount-flower-garden-early-morning-by-David-Dashiell-scaled-1.jpg', 'David Dashiell / The Mount',
     'the-gardens'),
    ('G', 'Flower Garden', 'The dolphin fountain',
     'The fountain in the Flower Garden’s pool.',
     '2026/04/The-Mount-dolphin-fountain-through-flowers-by-David-Dashiell-copy.webp', 'David Dashiell / The Mount',
     'the-gardens'),
    ('G', 'Rock Garden', 'The Rock Garden and Grass Steps',
     'A rock garden with Grass Steps molded into the sloping hill, a landscape feature rarely seen in America. Wharton '
     'saw her gardens as outdoor rooms in harmony with the house: “Decidedly, I’m a better landscape gardener than '
     'novelist.”',
     '2020/03/11733903_915846398456586_144861055_o.jpg', 'The Mount', 'the-gardens'),
    ('G', 'Woodland Walk', 'The woods and trails',
     'Meadows, woods and wetlands around the gardens, free to walk from dawn to dusk all year (dogs on leash). Some '
     'trails are steep, rough or muddy.',
     '2026/03/The-Mounts-woodlands-by-Stephanie-Zollshan-for-the-Berkshire-Eagle-1.webp',
     'Stephanie Zollshan for the Berkshire Eagle / The Mount', 'accessibility'),
    ('G', 'Woodland Walk', 'NightWood (Nov 21, 2026 – Jan 2, 2027)',
     'The Mount’s sound-and-light walk through the woods returns with a longer path: November 21, 25, 27–28; December 4, '
     '5, 11–12, 17–23, 26–31; January 2. Separate ticket, after dark; dress for the weather, no strollers or dogs; '
     'uneven terrain with stairs (golf-cart rides at 4:30 pm on some days: 413-551-5111 ext. 5). A NightWood ticket gives '
     '50% off a house tour.',
     '2026/09/nightwood-2024-eric-blue-green_55548935348_o.jpg', 'Eric Limon Photography / The Mount', 'nightwood'),
]

# Library Insights: books from Wharton's own library, kept in the Library (title, author, date, words, picture, page)
BOOKS = [
    ('Fighting France: From Dunkerque to Belfort', 'Edith Wharton', '1915',
     'Wharton’s account of her journeys into the war zones of France with Walter Berry, inscribed by her to her '
     'chauffeur Charles Cook, who drove them. Cook, from Lenox, joined the household in 1903 and drove the Whartons for '
     'nearly twenty years; The Mount bought this copy in 2020.',
     '2026/04/Fighting-France-cover-The-Mount-Archives-scaled-1400x1867.jpg.webp', 'fighting-france-from-dunkerque-to-belfort'),
    ('Leaves of Grass', 'Walt Whitman', '1897 edition',
     'Heavily marked and fragile from use, given to Wharton in 1898 by Walter Berry, who wrote in it a line of “Song of '
     'Myself”: “Who can stray from me? I follow you whoever you are from the present hour.” When Berry died in 1927 '
     'Wharton wrote, “all my life goes with him.”',
     '2026/04/Leaves-of-Grass-cover-scaled-1400x1867.jpg.webp', 'leaves-of-grass'),
    ('The Age of Innocence', 'Edith Wharton', '1921 (first edition, sixth printing)',
     'Wharton’s own copy of her Pulitzer Prize novel, with her bookplate from Sainte-Claire-du-Château. She made about 30 '
     'corrections between the first and sixth printings. Given back to The Mount by Dennis and Andrea Kahn in 2020, the '
     'novel’s centenary.',
     '2026/04/Kahn-Cover-Cropped-rotated-1-rotated-1400x840.jpg.webp', 'the-age-of-innocence'),
    ('Misrepresentative Women', 'Harry Graham', '1906',
     'Light verse, a gift from Henry James, inscribed “To a much misrepresented woman from the largest of her admirers.” '
     'A favorite of visitors to the library.', '2026/04/MW-cover-cropped-1400x1722.jpg.webp', 'misrepresentative-women'),
    ('Poems', 'Alice Meynell', '1913',
     'The only book by Meynell in Wharton’s library, with John Singer Sargent’s portrait of the poet. It contains '
     '“Renouncement,” a favorite of Wharton’s, which she chose for her anthology Eternal Passion in English Poetry.',
     '2026/04/Meynell-Poems-Cover-1400x1867.jpg.webp', 'alice-meynell'),
    ('Poems', 'Matthew Arnold', '1881 (two volumes)',
     'Given to Wharton at 19. She marked two lines of “Resignation” and quoted them to Morton Fullerton in 1908: “They, '
     'believe me, who await no gifts from chance, have conquered fate.”', '2026/04/Arnold-2-e1610735076130-405x1024.jpg.webp',
     'happy-birthday-edith'),
    ('Lays of the Scottish Cavaliers', 'William Edmonstoune Aytoun', 'given January 24, 1876',
     'A present for Edith’s 14th birthday from her sister-in-law Minnie Cadwalader Jones, a friend for life.',
     '2026/04/Lays10-e1610734166166-228x1024.jpg.webp', 'happy-birthday-edith'),
]

# 2026 outdoor show (May 24 – Oct 24): (title, artist, picture)
SCULPTURE = [
    ('Flight', 'Elizabeth Schoonmaker', '2026/07/flight-by-elizabeth-schoonmaker_55355206613_o.webp'),
    ('Three Sisters', 'John Ruppert', '2026/07/0042_55355212683_o.webp'),
    ('Sputnik', 'Harold Grinspoon', '2026/07/0007_55355057586_o.webp'),
    ('Geranium', 'Daina Shobrys', '2026/07/daina-shobrys-geranium_55349744117_o.webp'),
    ('The Helm', 'Robert G. Osborne', '2026/07/0002_55355057841_o.webp'),
    ('Red Rhythm #21', 'Rob Lorenson', '2026/07/0009_55355476880_o.webp'),
    ('Two Together', 'Joy Brown', '2026/07/0015_55354114517_o.webp'),
    ('Eleven Eleven II', 'Paul Chaleff', '2026/07/0018_55355257754_o.webp'),
    ('Arisen Gaia', 'Gabrielle Vitollo', '2026/07/0021_55355257584_o.webp'),
    ('Finding Center', 'David Adilman', '2026/07/0027_55355213483_o.webp'),
    ('A Gift Between Two', 'Jon Isherwood', '2026/07/0032_55355056241_o.webp'),
    ('Cielo y Tierra', 'Jon Riedeman', '2026/07/0038_55355212813_o.webp'),
    ('New Best Friend', 'Colin Moore', '2026/07/0045_55355055511_o.webp'),
    ('Still We Reach', 'Helen Duncan', '2026/07/helen-duncan-still-we-reach_55355055056_o.webp'),
    ('Flower Power Tower: They Tried to Bury Us. They Didn’t Know We Were Seeds', 'Amy Cannon',
     '2026/07/0095_55355052116_o.webp'),
    ('Nestling', 'Xavier Letteron', '2026/07/0098_55355252489_o.webp'),
    ('Hybrid Vigor', 'Gregory M. Gomez', '2026/07/0105_55354108362_o.webp'),
    ('Big Inflatable Solid', 'Mike Hansel', '2026/07/big-inflatable-solid-by-mike-hansel_55355250849_o.webp'),
    ('OH DEAR', 'Cindy Pease Roe', '2026/07/cindy-pease-roe-oh-dear_55354109477_o.webp'),
    ('The Earth Laughs in Flowers', 'Gints Grinbergs',
     '2026/07/gints-grinbergs-the-earth-laughs-in-flowers_55355052576_o.webp'),
    ('Xabana (42º10’52”N 73º16’57”W)', 'Matthias Neumann',
     '2026/07/matthias-neumann-xabana-421052n-731657w_55355053561_o.webp'),
    ('Synonym', 'Paul Villinski', '2026/07/paul-villinski-synonym_55355680275_o.webp'),
    ('Fairy Ring', 'Stephen Paulson', '2026/07/stephen-paulson-fairy-ring_55354111427_o.webp'),
]


def build_works(floors):
    names = {(f['id'], r['id']): r['name'] for f in floors['floors'] for r in f['rooms']}
    placed, unplaced, used = [], [], set()

    def add(a, floor, place):
        a = {k: v for k, v in a.items() if v not in (None, '')}
        n, k = 2, a['id']
        while a['id'] in used: a['id'] = f'{k}-{n}'; n += 1
        used.add(a['id'])
        if place:
            a.update(gallery=place, galleryName=names[(floor, place)].split(':')[0].split(' (')[0], floor=floor)
            placed.append(a)
        else:
            unplaced.append(a)

    for floor, place, title, words, path, credit, page in ROOMS:
        key = f'mt-{slugify(title)}'
        im = picture(key, path)
        add({'id': key, 'title': title, 'artist': 'The Mount',
             'medium': 'Room' if floor != 'G' else ('Garden' if 'Garden' in place or place in ('Lime Walk', 'Rock Garden')
                                                     else 'Historic place'),
             'description': words, 'descriptionKind': 'From The Mount’s pages', 'url': f'{SITE}/{page}/',
             'image': im, 'imageCredit': im and credit,
             'placeNote': 'Room shapes on the map are approximate: The Mount publishes no floor plan.' if floor != 'G'
             else None}, floor, place)
    for title, author, date, words, path, page in BOOKS:
        key = f'mt-b-{slugify(title + " " + author)}'
        im = picture(key, path)
        year = re.search(r'\d{4}', date)
        add({'id': key, 'title': title, 'artist': author, 'date': date, 'year': int(year[0]) if year else None,
             'medium': 'Book from Edith Wharton’s own library', 'description': words,
             'descriptionKind': 'From The Mount’s Library Insights', 'url': f'{SITE}/library-insights/{page}/',
             'image': im, 'imageCredit': im and 'The Mount Archives',
             'placeNote': 'Kept in Wharton’s Library. The books are seen from the doorway on the house tour; to look '
                          'inside them, book a private library tour.'}, '2', 'Library')
    for title, artist, path in SCULPTURE:
        key = f'mt-s-{slugify(title)}'
        im = picture(key, path)
        add({'id': key, 'title': title, 'artist': artist, 'date': '2026', 'year': 2026,
             'medium': 'Outdoor sculpture, Sculpture at The Mount 2026 (“Flourish”)',
             'description': 'One of the works in the 2026 outdoor show in the woods, gardens and grounds.',
             'descriptionKind': 'From The Mount’s sculpture page', 'url': f'{SITE}/sculpture-at-the-mount/',
             'image': im, 'imageCredit': im and 'The Mount',
             'placeNote': 'The show ran May 24 – October 24, 2026; where each work stood isn’t published, and works '
                          'may have been removed.'}, None, None)
    order = {(f['id'], r['id']): (fi, i) for fi, f in enumerate(floors['floors']) for i, r in enumerate(f['rooms'])}
    placed.sort(key=lambda a: (order[(a['floor'], a['gallery'])], a['artist'] != 'The Mount', 'image' not in a))
    return {'source': 'The Mount’s website (edithwharton.org) and media library', 'checked': time.strftime('%Y-%m-%d'),
            'count': len(placed), 'complete': False, 'artworks': placed}, unplaced


def build_guide(works, unplaced):
    rows = []
    for a, on in [(a, True) for a in works['artworks']] + [(a, False) for a in unplaced]:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a.get('title') or a['id'], 'artist': a.get('artist'),
                     'date': a.get('date'), 'year': a.get('year'), 'medium': a.get('medium'), 'url': a['url'],
                     'imageUrl': a.get('image'), 'onView': on, 'gallery': a.get('gallery'),
                     'floor': a.get('floor')}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': 'The Mount, Edith Wharton’s Home', 'checked': time.strftime('%Y-%m-%d'),
            'source': 'The Mount’s website and media library; OpenStreetMap', 'onViewKnown': True,
            'note': 'The Mount is the house Edith Wharton designed and built in 1902, where she wrote The House of Mirth. '
                    'It has no art collection to speak of: what you see are the rooms she planned by the rules of The '
                    'Decoration of Houses, her own 2,700-book library, and the gardens she called better than her '
                    'novels. This guide lists every room on the house tour, the books The Mount shows from her library, '
                    'the gardens, the Stable, NightWood and the 2026 outdoor sculpture show (ended October 24). The '
                    'house is open weekends only from November to January 2, then closed until May; the grounds are '
                    'free all year.',
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
    for f in floors['floors']:
        empty = [r['id'] for r in f['rooms'] if r['kind'] == 'gallery'
                 and not any(a['gallery'] == r['id'] and a['floor'] == f['id'] for a in works['artworks'])]
        print(f['id'], 'rooms with nothing in them:', empty)


if __name__ == '__main__':
    sys.exit(main())
