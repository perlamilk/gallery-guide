#!/usr/bin/env python3
"""Build the Harriet Beecher Stowe Center (Stowe Center for Literary Activism, Hartford, CT) map guide:

    python3 tools/build_stowe.py

    data/stowe/floors.json         the campus, the Visitor Center and both floors of the Stowe House, seen from above (2D)
    data/stowe/artworks.json       the rooms, the objects and exhibitions, the gardens and sculptures, each in its place
    data/stowe/images/             their pictures, made smaller for phones
    data/guides/Q5664050.json      the same, for the museum page

Where the information comes from
--------------------------------
The map
  - Campus (floor G): OpenStreetMap (cached in .cache/stowe/osm.xml): the Stowe House (way 194716938), the Visitor
    Center, once the carriage house (194716933), the Katharine Seymour Day House (194716936), the Stowe lot
    (1452912784), the drives and footpaths, Forest Street and Farmington Avenue, the Mark Twain House next door.
    Metres east/north of a point on Forest Street. The gardens are placed from the Stowe Center's garden posts
    (the Wildflower Garden "just south of the Stowe House", the Woodland Garden "just east of the Visitor's Center",
    the Merrill Magnolia "on the west side" of the house, the new garden with Stowe's statue "just behind Stowe's
    House", the shade garden "on the north side of the Day House"): their outlines are approximate.
  - The Stowe House (floors 1, 2) and the Visitor Center (floor V): no floor plan is published, and the house has no
    Historic American Buildings Survey drawings. The outlines are OpenStreetMap's; the rooms inside follow the
    descriptions ("a conventional center-hall plan, with two parlors, dining room, kitchen, and pantry on the first
    floor, and bedrooms on the second"; Calvin Stowe's study; the kitchen is the last room of the tour; Stowe's
    bedroom upstairs; the Gallery for Hope & Freedom and the Gallery for Literary Activism) and are approximate.

The works
  The house and its rooms, the objects the Stowe Center names as on view there (New England Antiques Journal,
  Nov 2017, published on stowecenter.org; CT Explored; Fine Books), the current exhibitions, the gardens and
  sculptures, and highlights of the collection (stowecenter.org/collections), with the Stowe Center's own pictures.
  stowecenter.org's robots.txt asks for a 10-second crawl delay: every request waits 10 seconds.
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
OUT = ROOT / 'data' / 'stowe'
CACHE = ROOT / '.cache' / 'stowe'
MUSEUM = 'Q5664050'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SITE = 'https://stowecenter.org'
NEAJ = SITE + '/wp-content/uploads/2017/11/New-England-Antiques-Journal-11.17.pdf'
APPROX = 'Approximate'

LAT0, LON0 = 41.76698, -72.70078
K = 8.0                       # map units per metre


def P(x, y):
    """Metres east/north -> map units (north up)."""
    return [round((x + 70) * K, 1), round((60 - y) * K, 1)]


def osm():
    f = CACHE / 'osm.xml'
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = 'https://www.openstreetmap.org/api/0.6/map?bbox=-72.7030,41.7652,-72.6975,41.7685'
        out = subprocess.run(['curl', '-s', '-f', '-m', '90', '-A', UA, url], capture_output=True).stdout
        if not out: raise SystemExit('OpenStreetMap did not answer')
        f.write_bytes(out)
    root = ET.parse(f).getroot()
    nodes = {n.get('id'): (float(n.get('lat')), float(n.get('lon'))) for n in root.iter('node')}
    ways = {}
    for w in root.iter('way'):
        ways[w.get('id')] = [(round((nodes[nd.get('ref')][1] - LON0) * 111320 * math.cos(math.radians(LAT0)), 2),
                              round((nodes[nd.get('ref')][0] - LAT0) * 110540, 2))
                             for nd in w.findall('nd') if nd.get('ref') in nodes]
    return ways


def band(pts, half=1.5):
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        nx, ny = -dy / n * half, dx / n * half
        left.append((x + nx, y + ny)); right.append((x - nx, y - ny))
    return left + right[::-1]


def clip(pts, x0=-68, x1=95, y0=-58, y1=58):
    return [p for p in pts if x0 <= p[0] <= x1 and y0 <= p[1] <= y1]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def circle(cx, cy, r, n=16):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


# ---- campus (floor G) -----------------------------------------------------------------------------------------------

def campus(ways):
    forest = clip(ways['17174522'])
    farm = sorted(clip(ways['1380325845'] + ways['1357722992'] + ways['1380325855'] + ways['1382742105'], y1=90),
                  key=lambda p: p[0])
    rooms = [
        ('Campus', 'space', 'Stowe Center campus: 2.5 acres of historic and new gardens, open for picnics '
                            '(boundary approximate)', rect(-36.4, -52, 60, 46)),
        ('Stowe House', 'space', 'Harriet Beecher Stowe House (1871): Stowe’s home from 1873 to 1896, seen on '
                                 'guided tours only. Pick floor 1 or 2 above to see its rooms', ways['194716938'][:-1]),
        ('Visitor Center', 'space', 'Visitor Center (1873, once a carriage house): start here for tickets, the '
                                    'museum store and the restroom. Pick floor V above', ways['194716933'][:-1]),
        ('Day House', 'gallery', 'Katharine Seymour Day House (1884): research library (by appointment) and offices; '
                                 'open only for some exhibits, programs and tours', ways['194716936'][:-1]),
        ('Stowe Lot', 'space', 'Free parking for cars and buses (Forest Street lot)', ways['1452912784'][:-1]),
        ('Front Drive', 'corridor', 'Curved drive in front of the red Day House: drop-off for buses and vehicles '
                                    'with mobility aids', band(clip(ways['779455740'], y1=60), 2.5)),
        ('Campus Drive', 'corridor', 'Campus drive from Forest Street, past the lot and the Visitor Center, '
                                     'round to the front drive', band(ways['779455741'], 2.5)),
        ('Path to the House', 'corridor', 'Path from the Visitor Center to the Stowe House',
         band(ways['907532350'][:9] + [(24.6, -19.5), (25.3, -19.6)], 1.2)),
        ('South Path', 'corridor', 'Path along the south side of the Stowe House to Forest Street',
         band(ways['907532350'][8:], 1.2)),
        ('Garden Path', 'corridor', 'Path across the middle of the campus, behind the Stowe House',
         band(ways['907532348'], 1.2)),
        ('Day House Path', 'corridor', 'Path from the front drive to the Stowe House and the lot',
         band(ways['907532349'], 1.2)),
        ('Wildflower Garden', 'gallery', 'Wildflower Garden, just south of the Stowe House: peonies, lilac, old roses '
                                         'and “Uncle Tom” tulips (place approximate)', rect(41, -32, 55, -22)),
        ('Statue Garden', 'gallery', 'The new shade garden in the centre of the campus, behind the Stowe House, by '
                                     'Connecticut’s largest Star Magnolia, with the bronze statue of Stowe '
                                     '(place approximate)', rect(1, -17.3, 15.5, -5)),
        ('Merrill Magnolia', 'gallery', 'The state-champion Merrill Magnolia and the Sensory Garden under it, on the '
                                        'west side of the house (place approximate)', circle(21, -12, 3.5)),
        ('Woodland Garden', 'gallery', 'Woodland Garden, just east of the Visitor Center: rhododendron, mountain '
                                       'laurel, azaleas (place approximate)', rect(-3, -51, 7, -44.5)),
        ('North Garden', 'gallery', 'Shade garden on the north side of the Day House, on a lit, winding path with '
                                    'two wooden arbours (place approximate)', rect(14, 35, 34, 43)),
        ('Little Free Library', 'gallery', 'Little Free Library and Pantry, in front of the Day House: take a book, '
                                           'leave a book', rect(52.5, 2, 55, 4.6)),
        ('Forest Street', 'corridor', 'Forest Street (one way from Farmington Avenue): street parking on the left side',
         band(forest, 4)),
        ('Farmington Avenue', 'corridor', 'Farmington Avenue: CT Transit buses 60, 62, 64 and 66', band(farm, 7)),
        ('Mark Twain House', 'space', 'The Mark Twain House, next door: a separate museum with its own tickets',
         ways['194716932'][:-1]),
    ]
    doors = [('Stowe Lot', 'Campus Drive', (22, -42)), ('Campus Drive', 'Forest Street', (58, -43.7)),
             ('Campus Drive', 'Visitor Center', (-2.9, -32.3)), ('Path to the House', 'Visitor Center', (-2.2, -32)),
             ('Path to the House', 'Stowe House', (25.3, -19.6)), ('Path to the House', 'South Path', (23.9, -25.6)),
             ('South Path', 'Wildflower Garden', (41, -26)), ('South Path', 'Forest Street', (53.8, -7.9)),
             ('Garden Path', 'Statue Garden', (9, -18.8)), ('Garden Path', 'Path to the House', (24.6, -19.5)),
             ('Garden Path', 'Campus Drive', (-7, -20.6)), ('Day House Path', 'Front Drive', (30.5, 5.9)),
             ('Day House Path', 'Stowe Lot', (23.4, -29.9)), ('Front Drive', 'Forest Street', (63.3, -3)),
             ('Front Drive', 'Day House', (33, 20)), ('Campus Drive', 'Front Drive', (38, 5.4)),
             ('Campus', 'Merrill Magnolia', (21, -8.5)), ('Campus', 'Woodland Garden', (2, -44.5)),
             ('Campus', 'North Garden', (24, 35)), ('Front Drive', 'Little Free Library', (52.5, 3.3)),
             ('Campus', 'Mark Twain House', (-36.4, 10))]
    amen = [('entrance', -2.9, -32.3), ('entrance', -12.1, -27.9), ('info', -8, -31), ('shop', -14, -31),
            ('restroom', -6.5, -39.5), ('entrance', 25.3, -19.6), ('entrance', 40.5, -16.4)]
    labels = [('P · Stowe lot (free)', 'area', 24, -50),
              ('Start here: tickets, store, restroom', 'area', -12, -47),
              ('Bus stop: Farmington Ave at Woodland / Gillett St', 'area', 10, 64),
              ('Front door and porch (portable ramp)', 'area', 48, -14),
              ('Twain lot (free): 385 Farmington Ave', 'area', -55, -50),
              ('No restrooms in the house', 'area', 32, -2)]
    first = ['Campus', 'Forest Street', 'Farmington Avenue', 'Front Drive', 'Campus Drive', 'Stowe Lot']
    rooms.sort(key=lambda r: (r[0] not in first, r[1] == 'space' and r[0] not in first, r[1] == 'gallery' and
                              r[0] == 'Day House'))
    return rooms, [], doors, amen, labels


# ---- the Visitor Center (approximate) --------------------------------------------------------------------------------
VC = [
    ('Visitor Desk & Store', 'gallery', 'Visitor desk and the museum store, New Dawn Bookstore by River Bend Bookshop: '
                                        'tickets, and every tour starts here', [(-2.7, -28.5), (-12.1, -27.9),
                                                                                 (-12.4, -35.5), (-3.1, -36.2)],
     'Desk & Store'),
    ('Visitor Center Gallery', 'gallery', 'Exhibition space (place approximate)', [(-12.1, -27.9), (-17.7, -27.6),
                                                                                   (-18.1, -34.4), (-12.4, -35.5)],
     'Gallery'),
    ('Program Room', 'gallery', 'Back room of the Visitor Center: programs and groups (approximate)',
     [(-22.6, -34.1), (-12.4, -35.5), (-8.6, -36), (-8.6, -42.2), (-23, -41.2)], 'Programs'),
    ('VC Restroom', 'space', 'Restroom (wheelchair accessible)', [(-8.6, -36), (-3.1, -36.2), (-3.2, -36.9),
                                                                 (-4.5, -36.8), (-4.9, -42.4), (-8.6, -42.2)], None),
]
VC_DOORS = [('Visitor Desk & Store', 'Visitor Center Gallery', (-12.2, -31)),
            ('Visitor Desk & Store', 'VC Restroom', (-6, -36.1)),
            ('Visitor Center Gallery', 'Program Room', (-15, -35))]
VC_AMEN = [('entrance', -2.9, -32.3), ('entrance', -12.1, -27.9), ('info', -6, -31), ('shop', -9, -33),
           ('restroom', -6.5, -39.5)]
VC_LABELS = [(APPROX + ': no plan of the Visitor Center is published', 'area', -12, -44.5),
             ('Wheelchair accessible', 'area', -12, -26)]

# ---- the Stowe House (approximate) ----------------------------------------------------------------------------------
H1 = [
    ('Entrance Hall', 'gallery', 'Entrance hall and staircase (centre-hall plan)', rect(29, -20.5, 38.8, -17.9), None),
    ('Front Parlor', 'gallery', 'Front parlor, with its bay window: Stowe’s “salon”, where tours sit down to talk',
     [(33, -17.9), (39.1, -17.8), (40.6, -18), (41, -14.8), (39.6, -14.6), (40.3, -9), (33, -8.3)], None),
    ('Back Parlor', 'gallery', 'Back parlor', [(27.1, -17.9), (33, -17.9), (33, -8.3), (29.3, -7.7), (29, -10.1),
                                               (27.8, -9.9), (27.7, -11), (26.6, -11.8), (26.3, -13.9), (27.2, -15.2),
                                               (27.1, -15.9)], None),
    ('Dining Room', 'gallery', 'Dining room', [(33, -20.5), (38.8, -20.5), (38.5, -23.2), (37.6, -23.1), (37.3, -25.2),
                                               (33, -24.7)], None),
    ('Calvin’s Study', 'gallery', 'Calvin Stowe’s study, now a multimedia room', rect(29, -24.3, 33, -20.5), 'Study'),
    ('Kitchen', 'gallery', 'Kitchen: the last room of the tour', [(24.8, -23.7), (25.2, -20.5), (29, -20.5),
                                                                  (29, -24.3)], None),
    ('Back Entry', 'space', 'Back entry and pantry: the door to the path from the Visitor Center',
     [(25.2, -20.5), (25.7, -15.7), (27.1, -15.9), (27.1, -17.9), (29, -17.9), (29, -20.5)], 'Back entry'),
]
H1_DOORS = [('Entrance Hall', 'Front Parlor', (36, -17.9)), ('Entrance Hall', 'Back Parlor', (30.5, -17.9)),
            ('Front Parlor', 'Back Parlor', (33, -13)), ('Entrance Hall', 'Dining Room', (35, -20.5)),
            ('Entrance Hall', 'Calvin’s Study', (31, -20.5)), ('Entrance Hall', 'Back Entry', (29, -19.2)),
            ('Back Entry', 'Kitchen', (27, -20.5)), ('Dining Room', 'Calvin’s Study', (33, -22.5))]
H1_AMEN = [('entrance', 38.9, -19.2), ('entrance', 25.3, -19.6), ('stairs', 31.5, -19.2)]
H1_LABELS = [(APPROX + ': no plan of the house is published; rooms placed from descriptions', 'area', 33, -27.5),
             ('Front door (ramp)', 'area', 42.5, -20.5), ('Door from the Visitor Center', 'area', 25, -25)]
H2 = [
    ('Upper Hall', 'corridor', 'Upstairs hall', rect(29, -20.5, 38.8, -17.9), None),
    ('Stowe’s Bedroom', 'gallery', 'Harriet Beecher Stowe’s bedroom (rented out as “Harriet’s Writing Room”)',
     [(33, -17.9), (39.1, -17.8), (40.6, -18), (41, -14.8), (39.6, -14.6), (40.3, -9), (33, -8.3)], 'Stowe’s Room'),
    ('Gallery for Hope & Freedom', 'gallery', 'The Stowe Gallery for Hope & Freedom',
     [(27.1, -17.9), (33, -17.9), (33, -8.3), (29.3, -7.7), (29, -10.1), (27.8, -9.9), (27.7, -11), (26.6, -11.8),
      (26.3, -13.9), (27.2, -15.2), (27.1, -15.9)], 'Hope & Freedom'),
    ('Gallery for Literary Activism', 'gallery', 'Gallery for Literary Activism: changing exhibitions',
     [(33, -20.5), (38.8, -20.5), (38.5, -23.2), (37.6, -23.1), (37.3, -25.2), (33, -24.7)], 'Literary Activism'),
]
H2_CLOSED = [[(24.8, -23.7), (25.7, -15.7), (27.1, -15.9), (27.1, -17.9), (29, -17.9), (29, -20.5), (33, -20.5),
              (33, -24.7)]]
H2_DOORS = [('Upper Hall', 'Stowe’s Bedroom', (36, -17.9)), ('Upper Hall', 'Gallery for Hope & Freedom', (30.5, -17.9)),
            ('Upper Hall', 'Gallery for Literary Activism', (35, -20.5))]
H2_AMEN = [('stairs', 31.5, -19.2)]
H2_LABELS = [(APPROX + ': places on this floor are a guess', 'area', 33, -27.5),
             ('One flight of stairs, no elevator', 'area', 33, -5.5)]


def build_floors(ways):
    g_rooms, g_closed, g_doors, g_amen, g_labels = campus(ways)
    house = ways['194716938'][:-1]
    vc = ways['194716933'][:-1]
    def big(pts, f):
        # floors drawn larger than life around the building's centre (labels stay readable); walkScale undoes it
        cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
        return lambda x, y: [round((cx + 70 + (x - cx) * f) * K, 1), round((60 - cy - (y - cy) * f) * K, 1)], f

    spec = [
        ('G', 'Campus', 'Visitor Center · Stowe House · Day House · gardens · parking', 0, (P, 1),
         [(a, b, c, d, None) for a, b, c, d in g_rooms], g_closed, g_doors, g_amen, g_labels),
        ('V', 'Visitor Center', 'Tickets · store · restroom · exhibition (inside approximate)', 1, big(vc, 4),
         [('Visitor Center (outline)', 'space', 'Visitor Center', vc, None)] + VC, [], VC_DOORS, VC_AMEN, VC_LABELS),
        ('1', 'Stowe House · Floor 1', 'Parlors · dining room · Calvin’s study · kitchen (approximate)', 2,
         big(house, 5),
         [('Stowe House (floor 1)', 'space', 'Stowe House, first floor', house, None)] + H1, [], H1_DOORS, H1_AMEN,
         H1_LABELS),
        ('2', 'Stowe House · Floor 2', 'Stowe’s bedroom · the two galleries (approximate)', 3, big(house, 5),
         [('Stowe House (floor 2)', 'space', 'Stowe House, second floor', house, None)] + H2, H2_CLOSED, H2_DOORS,
         H2_AMEN, H2_LABELS),
    ]
    floors, seen = [], set()
    for fid, label, area, order, (P_, f), rooms_in, closed_in, doors_in, amen, labels in spec:
        rooms = []
        for rid, kind, name, poly, short in rooms_in:
            assert rid not in seen, rid
            seen.add(rid)
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': [P_(*q) for q in poly]}
            if kind == 'gallery': r['label'] = short or rid
            rooms.append(r)
        ids = {r['id'] for r in rooms}
        doors = [{'a': a, 'b': b, 'at': P_(x, y), 'width': 10 * f, 'axis': 'o'} for a, b, (x, y) in doors_in]
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order, 'transform': [1, 0, 0],
                       **({'walkScale': round(1 / f, 3)} if f != 1 else {}),
                       'rooms': rooms, 'closed': [{'poly': [P_(*q) for q in c]} for c in closed_in],
                       'amenities': [{'type': t, 'at': P_(x, y)} for t, x, y in amen],
                       'labels': [{'text': t, 'kind': k, 'at': P_(x, y)} for t, k, x, y in labels],
                       'doors': doors, **({'homeView': ['Stowe House', 'Visitor Center', 'Day House', 'Stowe Lot']}
                                          if fid == 'G' else {})})
    return {'about': 'Built by tools/build_stowe.py. The campus comes from OpenStreetMap (the property line and the '
                     'gardens are approximate). No floor plan of the Stowe House or the Visitor Center is published: '
                     'their outlines are OpenStreetMap’s and the rooms inside are placed from descriptions, so they '
                     'are approximate.',
            'source': 'OpenStreetMap (campus and building outlines), the Stowe Center’s visit, FAQ and garden pages '
                      '(parking, accessibility, gardens), published descriptions of the house',
            'units': f'metres x {K}, north up; the house floors are drawn 5 times larger and the Visitor Center 4 times, around their centres (walkScale)', 'defaultFloor': 'G', 'galleryWord': 'Room', 'floors': floors}


# ---- the works -------------------------------------------------------------------------------------------------------
SC = 'Stowe Center for Literary Activism'
NJ = 'Stowe Center, published in the New England Antiques Journal (Nov 2017)'
HBS = 'Harriet Beecher Stowe'
# id, title, artist, date, room, photo ('sc:' path under wp-content/uploads, 'neaj:' image n of the 2017 article),
# text, place guessed?, page
WORKS = [
    ('house', 'The Harriet Beecher Stowe House', 'Built for Franklin Chamberlin', '1871', 'Stowe House',
     'sc:2025/05/stowe_house.jpg',
     'A brick “Gothic cottage”, painted grey, built in 1871 as a speculative house. Stowe bought it in 1873 and lived '
     'here with her husband Calvin and their twin daughters for the last 23 years of her life; she died here in 1896. '
     'Her grand-niece Katharine Seymour Day saved it, and it opened as a museum in 1968, one of the first house museums '
     'about a woman. A National Historic Landmark, restored in 2016–17 with wallpapers and carpets based on Stowe’s own '
     'choices.', False, '/visit/'),
    ('house-1870s', 'The Stowe House about 1874–1882', None, 'c. 1874–1882', 'Stowe House', 'neaj:0',
     'One of the earliest photographs of the house, from Stowe’s own time. The Stowe Center used early photos like '
     'this one to plan all the outside repairs.', False, '/visit/'),
    ('visitor-center', 'The Visitor Center', None, '1873', 'Visitor Center', None,
     'Once the carriage house, now the first stop: buy tickets here for the Stowe House Experience, look around the '
     'museum store (New Dawn Bookstore by River Bend Bookshop) and use the accessible restroom. Every tour starts here.',
     False, '/visit/'),
    ('day-house', 'The Katharine Seymour Day House', 'Francis H. Kimball (architect)', '1884', 'Day House',
     'sc:2025/09/DH-Main-Entrance.png',
     'A Queen Anne mansion of rough pink granite, brick and carved wood, built for Franklin and Mary Chamberlin. '
     'Stowe’s grand-niece Katharine Seymour Day (1870–1964), who founded the Stowe Center in 1941, bought it that year '
     'to save it from demolition. It holds the research library, offices and collection storage, and opens only for '
     'some exhibits and programs. Its outside paint, shingles and finials were restored to their 1884 look.', False,
     '/visit/'),
    ('library', 'The Research Library', None, None, 'Day House', 'sc:2025/05/research_library.jpg',
     'More than 12,000 books, 4,000 pamphlets, 180,000 manuscripts and 12,000 images about Stowe, the Beecher family, '
     'Nook Farm and Uncle Tom’s Cabin. Open by appointment only (860-522-9258 ext. 313).', False, '/collections/'),
    ('gardens', 'Stowe’s gardens', None, None, 'Wildflower Garden', 'sc:2025/05/stowe_garden.jpg',
     'Stowe loved gardening and wrote about it. The beds are planted informally with the flowers she wrote about: '
     'sweet peas, peonies, foxglove, bee balm, nasturtium, daylilies, marigolds, asters and goldenrod, so something is '
     'in bloom from April to September. Look for grafts of the pink Stowe Dogwood and the award-winning heritage roses.',
     True, '/visit/'),
    ('tulips', '“Uncle Tom” tulips', None, 'variety 1939', 'Wildflower Garden',
     'sc:2023/05/20230501_111013-scaled-e1683317576656.jpg',
     'In late April and early May the south garden next to the house fills with deep red double tulips named “Uncle '
     'Tom”, a Dutch variety of 1939. Nobody knows how they got the name.', False, '/uncle-tom-tulips/'),
    ('statue', 'Harriet Beecher Stowe, reading', 'Brenda Councill', '2026', 'Statue Garden',
     'sc:2026/08/Stowe-Statue-scaled-500x383@2x.jpg',
     'A life-size bronze of Stowe, beautifully dressed and seated on a bench, reading the 1849 freedom narrative of '
     'Josiah Henson, the man who inspired her Uncle Tom. Sit down beside her. Gift of Rosamond Warren Allen.', True,
     '/two-new-gardens-in-harriets-backyard/'),
    ('star-magnolia', 'Connecticut’s largest Star Magnolia', None, None, 'Statue Garden', None,
     'The state’s biggest Star Magnolia stands at the centre of the campus. In 2026 a new shade garden was planted '
     'around it: dogwood, cornelian cherry, more than 125 shrubs, 130 ferns and 375 perennials, most native to New '
     'England.', True, '/two-new-gardens-in-harriets-backyard/'),
    ('merrill-magnolia', 'The Merrill Magnolia and the Sensory Garden', None, None, 'Merrill Magnolia',
     None,
     'The state-champion Merrill Magnolia towers over the west side of the house and blooms in May. Its limbs root '
     'where they touch the ground. A deep wind chime hangs in it above the Sensory Garden and its bird bath.', True,
     '/it-was-a-jungle/'),
    ('davidson', 'Abstract sculpture', 'Carol Kreeger Davidson', None, 'North Garden', None,
     'An abstract piece by the Connecticut sculptor Carol Kreeger Davidson (1929–2014), in the shade garden north of '
     'the Day House. Gift of the Marks family in memory of Leta Weiss Marks.', True,
     '/two-new-gardens-in-harriets-backyard/'),
    ('little-library', 'Little Free Library and Pantry', None, '2023', 'Little Free Library',
     None,
     'Built by the Stowe Center’s facilities manager and painted by Isys B., an Asylum Hill student: take a book or '
     'some food, or leave some for a neighbour.', False, '/sept-update-ada-site-and-structural-improvement-project/'),
    ('nook-farm', 'The Nook Farm neighbourhood', None, '19th century', 'Campus', 'sc:2025/05/nook_farm.jpg',
     'Nook Farm was home to writers, reformers and activists: Stowe, Mark Twain, her sister the suffragist Isabella '
     'Beecher Hooker, the writer Charles Dudley Warner and the actor William Gillette. The Twain House is next door; '
     'a self-guided audio tour of the neighbourhood costs $15.', False, '/visit/'),
    # House, floor 1
    ('entrance-hall', 'The entrance hall and its Madonnas', None, None, 'Entrance Hall', None,
     'Walking in, notice how many pictures of the Madonna hang in the house; Stowe painted some of them herself.',
     True, '/visit/'),
    ('front-parlor', 'The front parlor', None, 'restored 2017', 'Front Parlor',
     'sc:2025/07/HBS_8.16.1886_in_parlor_-_300dpi.jpg',
     'Stowe’s salon, where tours now sit down to talk about the issues she wrote about. The photo shows Stowe in her '
     'parlor in 1886; the Stowe Center used it, and visitors’ letters, to remake the room’s fancy black wallpaper '
     'border and its colours in 2017. The 1960s restoration had treated the two parlors as one room.', False,
     '/collections/'),
    ('reward-poster', '$2,500 Reward!', None, '19th century', 'Front Parlor', 'sc:2025/07/2_500_Reward__-scaled-1.jpg',
     'A reward poster for people who escaped slavery: one of the documents tours read closely together in the front '
     'parlor.', True, '/collections/'),
    ('secretary', 'The Stowe family’s Empire secretary', None, 'c. 1830s', 'Front Parlor', None,
     'The family’s mahogany Empire secretary (a desk with a bookcase above), shown in the formal parlor.', False,
     '/visit/'),
    ('fisher-portrait', 'Portrait of Harriet Beecher Stowe', 'Alanson Fisher', '1853', 'Front Parlor',
     'sc:2025/07/63.340_Fisher_portrait_of_HBS_1853.jpg',
     'Painted the year after Uncle Tom’s Cabin made her famous: a copy of the portrait commissioned by A. H. Purdy of '
     'the National Theatre in New York, home of one of the longest-running stage versions of the novel.', True,
     '/collections/'),
    ('african-woman', 'African Woman at the Well', 'Charles Cumberworth', 'given 1853', 'Front Parlor', 'neaj:6',
     'A bronze statuette awarded to Stowe by the managers of the Boston Anti-Slavery Fair in 1853. Stowe filled her '
     'parlors with gifts and souvenirs from her travels.', True, '/visit/'),
    ('oranges', 'Florida Orange Fruit & Blossoms', HBS, 'c. 1867–1884', 'Front Parlor', 'neaj:4',
     'Stowe painted all her life. This oil on panel shows oranges from Mandarin, Florida, where the family spent their '
     'winters; she gave some of her paintings to raise money for schools and churches for freed people in Florida.',
     True, '/visit/'),
    ('back-parlor', 'The back parlor', None, 'restored 2017', 'Back Parlor', 'neaj:2',
     'The second parlor, now decorated as its own room, with copies of old masters such as Raphael and Giorgione and '
     'souvenirs from Stowe’s travels. Where photos of this house were missing, the finishes follow her first Hartford '
     'house, Oakholm: the picture shows Oakholm’s double parlor about 1865.', False, '/visit/'),
    ('limoges-vase', 'Spill vase: Eliza crossing the ice', 'Limoges', '19th century', 'Back Parlor',
     'sc:2025/07/2000.01_UTC_Limoge_spill_vase_72dpi.jpg',
     'A porcelain vase painted to order with Eliza and her son Harry running across the frozen Ohio River to freedom: '
     'the most famous scene of Uncle Tom’s Cabin.', True, '/collections/'),
    ('dining-room', 'The dining room', None, 'restored 2017', 'Dining Room', 'neaj:7',
     'Set for a family meal. Its wallpaper is a reproduction of a paper kept in the Stowe Center’s archive, hung by '
     'Denis Picard of Kensington, CT, in 2017 (the photo).', False, '/visit/'),
    ('writing-table', 'The table where Stowe began Uncle Tom’s Cabin', None, '1830s', 'Dining Room', None,
     'A drop-leaf table, a wedding present from Stowe’s father. She wrote the first two chapters of Uncle Tom’s Cabin '
     'on it, in Brunswick, Maine, in 1851. Today passages of the book are projected on a screen behind it.', True,
     '/collections/'),
    ('calvin', 'Calvin Stowe', 'Georgie S. Allen', 'c. 1880', 'Calvin’s Study',
     'sc:2025/07/Calvin_Stowe_watercolor_by_Georgie_S._Allen_c1880.jpg',
     'Harriet’s husband, a professor of the Bible whom she described as “rich in Greek & Hebrew, Latin & Arabic, & '
     'alas! rich in nothing else”. His study is now a multimedia room.', True, '/collections/'),
    ('kitchen', 'The kitchen', None, '1870s', 'Kitchen', None,
     'The last room of the tour, set up as in Stowe’s day with a coal stove at one end and a big table in the middle. '
     'Stowe employed African American, Irish and German women here. Visitors sit at the table and write their own '
     'thoughts on the paper that covers it.', False, '/visit/'),
    # House, floor 2
    ('bedroom', 'Stowe’s bedroom', None, None, 'Stowe’s Bedroom', None,
     'Harriet Beecher Stowe’s bedroom. You can rent it for an hour or two as “Harriet’s Writing Room” and write there '
     '(Mondays and Tuesdays, $300 an hour).', True, '/visit/harriets-writing-room/'),
    ('hope-freedom', 'The Stowe Gallery for Hope & Freedom', 'Erika Slocumb (curator)', '2024', 'Gallery for Hope & Freedom',
     'sc:2025/07/Constellation-of-Hope-and-Freedom-500x383@2x.png',
     'The former “Global Impact of Uncle Tom’s Cabin” room, reinterpreted. It starts with Stowe’s 1853 Key to Uncle '
     'Tom’s Cabin and centres the Black writers who influenced her, from freedom narratives to Stowe Prize winners '
     'Ta-Nehisi Coates, Ruha Benjamin and Bettina Love. Seen on the 60-minute Inspiring Stowe tour.', True,
     '/a-gallery-for-hope-and-freedom/'),
    ('human', 'What Does It Mean to Be Human?', 'Amanda Mendoza', '2025', 'Gallery for Literary Activism',
     None,
     'Current exhibition: intimate works by the artist and muralist Amanda Mendoza, with research by Gamze Ozker, on '
     'how humanity is denied and reclaimed, from slavery to today’s immigrants, using hands and nature as symbols.',
     True, '/visit/exhibit-select-page/human/'),
    ('declarations', '6,000+ Declarations of Independence', 'Joe Young, Davide Gentile, Mirco Maiorano', '2026',
     'Visitor Center Gallery', 'sc:2026/07/KEMET-6000-COVER.jpg',
     'Exhibition for America’s 250th, on view through December 2026: large comic art from Joe Young’s Kemet comics '
     'on the Black abolitionists who declared their own independence, including Frederick Douglass, Harriet Jacobs, '
     'Sojourner Truth and Josiah Henson.', True, '/visit/exhibit-select-page/independence/'),
    # Collection highlights (in the research library; ask what is on view)
    ('frontispiece', 'Uncle Tom’s Cabin, first edition', 'John P. Jewett & Co.', '1852', 'Day House',
     'sc:2025/07/frontispiece_1852_300_dpi.jpg',
     'The novel came out week by week in The National Era in 1851–52 and as a book in March 1852; it sold 300,000 '
     'copies in its first year in the U.S. The Stowe Center has most American and foreign editions.', True,
     '/collections/'),
    ('bracelet', 'Gold “slave bracelet”', None, '1853', 'Day House', 'sc:2025/07/HBS_slave_bracelet_1853_72dpi.jpg',
     'Given to Stowe on her 1853 tour of Britain: a gold bracelet shaped like a slave’s shackle, with links engraved '
     'with dates of abolition. Stowe later had the date of American emancipation added.', True, '/collections/'),
    ('inkstand', 'Silver and crystal inkstand', None, '1853', 'Day House',
     'sc:2025/07/65.23_silver_and_cut_crystal_inkstand.jpg',
     'Another gift from her 1853 British tour, along with the Affectionate and Christian Address: an anti-slavery '
     'appeal signed by more than 500,000 British and Irish women, bound in 26 volumes.', True,
     '/incarcerated-women-and-the-christian-address/'),
    ('wallpaper', 'Uncle Tom’s Cabin wallpaper', None, '1853', 'Day House', 'neaj:5',
     'Cheap wallpaper printed in Britain with scenes from the novel at the height of its success: one of many '
     'souvenirs, plays and products “Uncle Tom mania” produced.', True, '/collections/'),
    ('stage-poster', 'Uncle Tom’s Cabin stage poster', None, 'late 19th century', 'Day House',
     'sc:2025/07/UTC_Stage_poster_2013.3.jpg',
     'Stage versions toured for decades, often with minstrel stereotypes that turned “Uncle Tom” into an insult, far '
     'from Stowe’s character.', True, '/collections/'),
    ('lantern-slide', 'Eva reading to Uncle Tom', None, 'late 19th century', 'Day House',
     'sc:2025/07/2011_1_Eva_Reading_to_Uncle_Tom_lantern_slide017.jpg',
     'A magic-lantern slide of one of the novel’s best-known scenes, shown on screens to audiences.', True,
     '/collections/'),
    ('alphabet', 'The Anti-Slavery Alphabet', None, '1847', 'Day House',
     'sc:2025/07/Antislavery_alphabet_1847-scaled-1.jpg',
     'A children’s book sold at an anti-slavery fair in Philadelphia: “A is an Abolitionist…”.', True, '/collections/'),
    ('hooker', 'Isabella Beecher Hooker', None, '1873', 'Day House', 'sc:2025/07/Isabella_B_Hooker_1873.jpg',
     'Stowe’s youngest sister and Nook Farm neighbour, a founder of the National Woman Suffrage Association.', True,
     '/collections/'),
    ('catharine', 'Catharine Beecher', None, 'c. 1870', 'Day House', 'sc:2025/07/Catharine_Beecher_c1870-scaled-1.jpg',
     'Stowe’s eldest sister, who raised her after their mother died and pioneered education for women at the Hartford '
     'Female Seminary, where Harriet studied and taught.', True, '/collections/'),
]


def fetch(url, dest):
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
        if 'stowecenter.org' in url: time.sleep(10)                      # robots.txt: Crawl-delay 10
        if not out: return None
        dest.write_bytes(out)
    return dest


def neaj_images():
    pdf = fetch(NEAJ, CACHE / 'neaj.pdf')
    d = CACHE / 'neaj'
    if pdf and not d.exists():
        d.mkdir(parents=True)
        subprocess.run(['pdfimages', '-j', str(pdf), str(d / 'i')], check=True, capture_output=True)
    return d


def picture(key, photo):
    """Download once and save a phone-sized JPEG; returns (app path, credit)."""
    if not photo: return None, None
    if photo.startswith('neaj:'):
        raw, credit = neaj_images() / f'i-{int(photo[5:]):03d}.jpg', NJ
        if not raw.exists(): return None, None
    else:
        raw = fetch(f'{SITE}/wp-content/uploads/{photo[3:]}', CACHE / 'img' / f'{key}.bin')
        credit = SC
        if not raw: return None, None
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
    return f'data/stowe/images/{key}.jpg', credit


def build_works(floors):
    names = {r['id']: (r['name'], f['id']) for f in floors['floors'] for r in f['rooms']}
    works = []
    for wid, title, artist, date, room, photo, text, guessed, page in WORKS:
        key = 'stowe-' + wid
        img, credit = picture(key, photo)
        name, floor = names[room]
        kind = ('Exhibition' if wid in ('human', 'declarations', 'hope-freedom') else
                'Historic room' if floor in ('1', '2') and not artist and wid in (
                    'entrance-hall', 'front-parlor', 'back-parlor', 'dining-room', 'kitchen', 'bedroom') else
                'Garden' if room in ('Wildflower Garden', 'Statue Garden', 'Merrill Magnolia', 'North Garden')
                and wid not in ('statue', 'davidson') else
                'Building' if wid in ('house', 'house-1870s', 'visitor-center', 'day-house', 'nook-farm', 'library',
                                      'little-library') else 'Object')
        a = {'id': key, 'title': title, 'artist': artist or kind, 'date': date,
             'year': int(date[-4:]) if date and date[-4:].isdigit() else (int(date[:4]) if date and date[:4].isdigit() else None),
             'type': kind, 'description': text, 'url': SITE + page, 'image': img, 'imageCredit': credit,
             'gallery': room, 'galleryName': name, 'floor': floor,
             'placeNote': ('Shown by the Stowe Center; the room it is in is our guess (no plan is published).'
                           if guessed and room != 'Day House' else
                           'In the Stowe Center’s collection: ask whether it is on view (the library is by appointment).'
                           if room == 'Day House' and wid not in ('day-house', 'library') else
                           'Place from the Stowe Center’s own pages.')}
        if guessed: a['placeGuessed'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '')})
    return {'source': 'Stowe Center for Literary Activism (stowecenter.org: visit, collections, exhibition and garden '
                      'pages; New England Antiques Journal article, Nov 2017)', 'checked': time.strftime('%Y-%m-%d'),
            'count': len(works), 'complete': False, 'artworks': works}


def build_guide(works):
    rows = [{k: v for k, v in {
        'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'), 'year': a.get('year'),
        'url': a['url'], 'imageUrl': a.get('image'), 'onView': a['gallery'] != 'Day House' or a['id'] in (
            'stowe-day-house', 'stowe-library'), 'gallery': a['gallery'], 'floor': a['floor']}.items()
        if v not in (None, '')} for a in works['artworks']]
    return {'museum': MUSEUM, 'name': 'Harriet Beecher Stowe Center', 'checked': works['checked'],
            'source': works['source'], 'onViewKnown': True,
            'note': 'Stowe’s 1871 home, seen on guided history tours: its parlors, dining room, kitchen and bedroom, '
                    'the objects the Stowe Center shows there, the two galleries and the current exhibitions, the '
                    'gardens and sculptures, and highlights of the collection (ask whether those are on view). No '
                    'flash or video in the house.',
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
                              'onView': sum(bool(w.get('onView')) for w in guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    print(f'{works["count"]} works, {sum("image" in a for a in works["artworks"])} pictures')


if __name__ == '__main__':
    sys.exit(main())
