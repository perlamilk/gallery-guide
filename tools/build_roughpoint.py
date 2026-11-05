#!/usr/bin/env python3
"""Build the Rough Point (Doris Duke's Newport home) map guide (run: python3 tools/build_roughpoint.py).

    data/roughpoint/floors.json     the estate from above (floor G) and the two public floors of the house (1-2)
    data/roughpoint/artworks.json   the rooms, the Collection highlights placed where the pages say they are, and the
                                    2026 exhibitions
    data/roughpoint/images/         pictures, made smaller for phones
    data/guides/<QID>.json          the same list (with the highlights not placed) for the museum page

The map. The Newport Restoration Foundation (NRF) publishes no floor plan or grounds map (its map is inside the
"Newport Restoration Foundation" phone app), so:
  - Grounds (floor G): OpenStreetMap (api.openstreetmap.org/api/0.6/map, cached in .cache/roughpoint/osm.xml): the
    estate (way 1225567916), the house footprint (way 882221285), the entrance gate on Bellevue Avenue, the circular
    drive, the Cliff Walk round the estate, the rocky point itself and the RIPTA Route 67 bus stops. Everything is
    turned 32.8 degrees so the house stands straight: north is about a third of the way right of up. The ocean terrace
    and the formal (dahlia) garden are placed by hand (approximate).
  - House (floors 1-2): APPROXIMATE. Rooms are fitted into the OpenStreetMap footprint from what NRF publishes: the
    Great Hall you enter, the Stair Hall with the Dining Room seen from it, the Morning Room, Pine Room, Yellow Room,
    the Solarium reaching south toward the ocean, the Anteroom and the 1920s Music Room (nearly 2,000 sq ft, the big
    block at the north-east end), the service wing (kitchen, butler's pantry) at the south-west end; upstairs Doris
    Duke's bedroom, the stair landing with the Oudry studies and the exhibition galleries. NRF says there is an
    elevator to the second floor and accessible restrooms but not where: they are drawn in the service wing.

The works. Pages of newportrestoration.org (WordPress; robots.txt allows every robot), read once by
tools/harvest_roughpoint.py: the "Collection" highlights (with the museum's own photos), and the 2026 exhibitions.
A highlight is placed in a room only when its page names the room; the rest are listed on the museum page.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_osv import poly_line_gap, band, along  # noqa: E402  (shared geometry)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'roughpoint'
CACHE = ROOT / '.cache' / 'roughpoint'
MUSEUM = 'Q7370843'
SITE = 'https://www.newportrestoration.org'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SOURCE = ('OpenStreetMap (grounds and the house outline) and the Newport Restoration Foundation’s own descriptions '
          'of the rooms; the room layout is approximate')

LAT0, LON0 = 41.4553, -71.3053
TURN = math.radians(32.8)        # the house's long side runs 32.8 degrees north of east
U = 1 / 0.35                     # map units per metre (the app's walking scale: 0.35 m per unit)
HS = 4                           # house drawings: units per foot
FT = 0.3048


# ---- the grounds (OpenStreetMap) --------------------------------------------------------------------------------
def osm():
    f = CACHE / 'osm.xml'
    if not f.exists():
        out = subprocess.run(['curl', '-s', '-f', '-m', '120', '-A', UA,
                              'https://api.openstreetmap.org/api/0.6/map?bbox=-71.3095,41.4525,-71.3015,41.4580'],
                             capture_output=True, check=True).stdout
        f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(out)
    t = ET.parse(f).getroot()
    nodes = {n.get('id'): (float(n.get('lat')), float(n.get('lon'))) for n in t.findall('node')}
    ways = {w.get('id'): {'nodes': [n.get('ref') for n in w.findall('nd')],
                          'tags': {x.get('k'): x.get('v') for x in w.findall('tag')}} for w in t.findall('way')}
    return nodes, ways


def metres(lat, lon):
    """Metres east/south of the reference point, turned so the house stands straight."""
    x = (lon - LON0) * 111320 * math.cos(math.radians(LAT0))
    y = -(lat - LAT0) * 110540
    c, s = math.cos(TURN), math.sin(TURN)
    return x * c - y * s, x * s + y * c


def G(lat, lon):
    x, y = metres(lat, lon)
    return [round(x * U, 1), round(y * U, 1)]


# ---- the house, in feet (x along the house toward the ocean end, y from the entrance front toward the ocean) --------
def R(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


KITCHEN = [[20.4, 0], [0, 33.8], [22, 47.1], [22, 1]]
PANTRY = [[22, 1], [22, 47.1], [36.8, 56], [36.8, 62.8], [46, 62.8], [46, 15.4]]
GREAT_HALL = [[119, 27.7], [164, 27.7], [164, 71.1], [152.4, 71.3], [152.6, 77.9], [149.2, 81.2], [139.8, 81.4],
              [135.9, 78], [135.8, 71.8], [123.7, 71.8], [123.7, 45], [119, 45]]
DINING = [[93, 45], [123.7, 45], [123.7, 85.9], [94.8, 85.9], [94.8, 72.5], [93, 72.5]]
MUSIC = [[211.4, 19.3], [236.1, 19.5], [236.1, 29.1], [253.1, 29.2], [253.1, 66.8], [214.1, 66.6], [214.1, 64.9],
         [211.4, 64.9]]
TERRACE = [[123.7, 81.6], [164, 81.6], [164, 112], [95, 112], [95, 86.2], [123.7, 86.2]]
APPROX = 'Room shapes approximate: NRF publishes no floor plan'

FLOORS = {
    '1': {
        'label': 'House · First floor', 'area': 'Great Hall · Stair Hall · Dining Room · Morning Room · Yellow Room · Music Room · Solarium',
        'rooms': [
            ('Vestibule', 'corridor', 'Front entrance and vestibule (from the circular drive)', R(119.3, 5.3, 143, 27.7),
             None),
            ('Great Hall', 'gallery', 'The Great Hall: the oak-panelled hall you enter, with the tapestries', GREAT_HALL,
             'Great Hall'),
            ('Stair Hall', 'gallery', 'The Stair Hall: the main staircase, with the Dining Room beyond',
             R(93, 8.5, 119, 45), 'Stair Hall'),
            ('Morning Room', 'gallery', 'The Morning Room (oak panelling)', R(62.4, 27, 93, 72.5), 'Morning Room'),
            ('Dining Room', 'gallery', 'The Dining Room: the table set toward the ocean windows', DINING,
             'Dining Room'),
            ('Pine Room', 'gallery', 'The Pine Room', R(164, 27.7, 193.7, 50), 'Pine Room'),
            ('Yellow Room', 'gallery', 'The Yellow Room: Doris Duke’s sitting room', R(164, 50, 193.9, 71.1),
             'Yellow Room'),
            ('Solarium', 'gallery', 'The Solarium: glass on three sides, over the lawn and the ocean',
             R(164.8, 71.1, 194.4, 97.2), 'Solarium'),
            ('Anteroom', 'gallery', 'The Anteroom, on the way to the Music Room', R(193.7, 30.9, 211.4, 64.9),
             'Anteroom'),
            ('Music Room', 'gallery', 'The Music Room: the Dukes’ 1920s addition, nearly 2,000 square feet', MUSIC,
             'Music Room'),
            ('Butler’s Pantry', 'space', 'Butler’s pantry (service wing)', PANTRY, 'Butler’s Pantry'),
            ('Kitchen', 'gallery', 'The Kitchen (service wing)', KITCHEN, 'Kitchen'),
            ('Service Hall', 'corridor', 'Service wing hall', R(46, 15.4, 62.4, 62.8), None),
            ('Ocean Terrace', 'space', 'The terrace on the ocean side, guarded by the stone lions', TERRACE, None),
        ],
        'closed': [],
        'doors': [('Vestibule', 'Great Hall', (131, 27.7)), ('Great Hall', 'Stair Hall', (119, 36)),
                  ('Stair Hall', 'Morning Room', (93, 36)), ('Stair Hall', 'Dining Room', (106, 45)),
                  ('Great Hall', 'Dining Room', (123.7, 60)), ('Morning Room', 'Dining Room', (93, 60)), ('Great Hall', 'Pine Room', (164, 38)),
                  ('Great Hall', 'Yellow Room', (164, 62)), ('Pine Room', 'Yellow Room', (178, 50)),
                  ('Yellow Room', 'Solarium', (179, 71.1)), ('Pine Room', 'Anteroom', (193.7, 40)),
                  ('Yellow Room', 'Anteroom', (193.9, 58)), ('Anteroom', 'Music Room', (211.4, 46)),
                  ('Morning Room', 'Service Hall', (62.4, 50)), ('Service Hall', 'Butler’s Pantry', (46, 30)),
                  ('Butler’s Pantry', 'Kitchen', (22, 25)), ('Great Hall', 'Ocean Terrace', (144.5, 81.4)),
                  ('Dining Room', 'Ocean Terrace', (110, 85.9))],
        'amenities': [('entrance', (131, 3)), ('info', (126, 18)), ('stairs', (106, 22)), ('elevator', (54, 52)),
                      ('restroom-all', (54, 26)), ('entrance', (1, 30))],
        'labels': [('Front door (circular drive)', 'note', (131, -8)),
                   ('Service entrance', 'note', (8, 48)),
                   ('Elevator and restrooms: places approximate', 'note', (40, 76)),
                   ('Atlantic Ocean this way', 'note', (180, 128)),
                   (APPROX, 'note', (130, 140))],
    },
    '2': {
        'label': 'House · Second floor', 'area': 'Doris Duke’s bedroom · stair landing · exhibition galleries',
        'rooms': [
            ('Stair Landing', 'gallery', 'The stair landing: stained glass and the two Oudry studies',
             R(93, 8.5, 119, 45), 'Stair Landing'),
            ('Upper Hall', 'corridor', 'Second-floor hall', R(119.3, 5.3, 143, 35), None),
            ('Bedroom Hall', 'corridor', 'Bedroom corridor', R(143, 27.7, 211.4, 35), None),
            ('Doris Duke’s Bedroom', 'gallery', 'Doris Duke’s bedroom, over the ocean', R(164, 35, 193.9, 71.1),
             'Doris Duke’s Bedroom'),
            ('Doris Duke’s Bath', 'space', 'Her bathroom and dressing room', R(193.7, 35, 211.4, 64.9), 'Her Bath'),
            ('Fashion Gallery', 'gallery', 'The Doris Duke Fashion Gallery: Women Designers of the 20th Century and Fashioning Resiliency (place approximate)',
             DINING, 'Fashion Gallery'),
            ('Exhibition Gallery', 'gallery', 'Exhibition rooms: Keeping Rough Point Above Water (place approximate)', R(62.4, 27, 93, 72.5), 'Exhibitions'),
            ('Newport Galleries', 'gallery', 'The Newport Galleries: 18th-century Newport furniture and 1776 | 2026 '
             '(place approximate)', [[20.4, 0], [0, 33.8], [36.8, 56], [36.8, 62.8], [46, 62.8], [46, 15.4]],
             'Newport Galleries'),
            ('Service Hall (upper)', 'corridor', 'Service wing hall', R(46, 15.4, 62.4, 62.8), None),
        ],
        'closed': [[[119, 35], [164, 35]] + GREAT_HALL[2:],
                   R(211.4, 29.2, 253.1, 66.8)],
        'doors': [('Stair Landing', 'Upper Hall', (119, 18)), ('Upper Hall', 'Bedroom Hall', (143, 31)),
                  ('Bedroom Hall', 'Doris Duke’s Bedroom', (178, 35)),
                  ('Doris Duke’s Bedroom', 'Doris Duke’s Bath', (193.8, 50)),
                  ('Stair Landing', 'Fashion Gallery', (106, 45)), ('Stair Landing', 'Exhibition Gallery', (93, 36)),
                  ('Exhibition Gallery', 'Service Hall (upper)', (62.4, 50)),
                  ('Service Hall (upper)', 'Newport Galleries', (46, 30))],
        'amenities': [('stairs', (106, 22)), ('elevator', (54, 52))],
        'labels': [('Great Hall: open to the floor below', 'note', (133, 58)),
                   ('Music Room roof (one storey)', 'note', (232, 48)),
                   ('Galleries change with each year’s exhibitions; places approximate', 'note', (60, 90)),
                   (APPROX, 'note', (130, 140))],
    },
}
HOUSE_CENTRE = (126, 50)


def to_grounds(ox, oy):
    """feet in the house drawing -> grounds units (ox, oy: the house's corner on the grounds, in metres)."""
    return lambda x, y: [round((ox + x * FT) * U, 1), round((oy + y * FT) * U, 1)]


def house_frame(nodes, ways):
    pts = [metres(*nodes[n]) for n in ways['882221285']['nodes']]
    ox, oy = min(p[0] for p in pts), min(p[1] for p in pts)
    to_g = to_grounds(ox, oy)
    # The house floors are drawn larger than life (4 units per foot) so rooms are big enough to read; they are centred
    # on the house's place on the grounds and walk at their true size.
    cx, cy = to_g(*HOUSE_CENTRE)
    transform = [1, round(cx - HOUSE_CENTRE[0] * HS, 1), round(cy - HOUSE_CENTRE[1] * HS, 1)]
    return transform, to_g, [[round((p[0] - ox) / FT, 1), round((p[1] - oy) / FT, 1)] for p in pts[:-1]]


def F(p):
    return [round(p[0] * HS, 1), round(p[1] * HS, 1)]


def build_house_floor(fid, spec, order, transform):
    rooms = []
    for rid, kind, name, pg, label in spec['rooms']:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': [F(p) for p in pg], 'z': 2}
        if label: r['label'] = label
        rooms.append(r)
    doors = [{'a': a, 'b': b, 'at': F(p), 'width': 16, 'axis': 'o'} for a, b, p in spec['doors']]
    return {'id': fid, 'label': spec['label'], 'order': order, 'area': spec['area'], 'transform': transform,
            'walkScale': round(FT * U / HS, 4),
            'rooms': rooms, 'closed': [{'poly': [F(p) for p in pg]} for pg in spec['closed']],
            'amenities': [{'type': t, 'at': F(p)} for t, p in spec['amenities']],
            'labels': [{'text': t, 'kind': k, 'at': F(p)} for t, k, p in spec['labels']],
            'doors': doors, 'homeView': [r['id'] for r in rooms if r['kind'] == 'gallery']}


# walkways: OpenStreetMap way -> (name, half width in map units)
WALKS = {
    '874518511': ('Circular drive to the front door', 9),
    '874518512': ('Entrance drive from the gate on Bellevue Avenue', 8),
}


def build_grounds(nodes, ways, to_g, outline):
    def line(wid): return [G(*nodes[n]) for n in ways[wid]['nodes'] if n in nodes]
    rooms = []

    def add(rid, kind, name, pg, label=None, z=2):
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': pg, 'z': z}
        if label: r['label'] = label
        rooms.append(r); return r

    add('Grounds', 'space', 'Rough Point’s grounds: about 10 acres on the ocean, landscaped by the Olmsted firm '
        '(an accredited arboretum since 2026)', line('1225567916')[:-1], z=0)
    add('House', 'gallery', 'The house (1887–91, enlarged 1922–24): rooms, collections and exhibitions',
        [to_g(*p) for p in outline], 'Rough Point')
    add('Ocean Terrace', 'gallery', 'The ocean terrace with the stone lions', [to_g(*p) for p in TERRACE],
        'Lions Terrace', z=3)
    add('Ocean Lawn', 'gallery', 'The great lawn running down to the rocks and the Atlantic (place approximate)',
        [to_g(*p) for p in [[60, 115], [260, 115], [300, 260], [80, 300]]], 'Ocean Lawn', z=1)
    add('Formal Garden', 'gallery', 'The formal garden, with Doris Duke’s dahlias in late summer (place approximate)',
        [to_g(*p) for p in [[-75, 40], [-20, 60], [-45, 125], [-100, 105]]], 'Formal Garden')
    gate = G(*nodes['8140887800'])
    add('Gate Lodge', 'space', 'Small building by the gate (staff)', line('1200828902')[:-1], z=1)

    doors, walk_lines = [], []
    for wid, (name, half) in WALKS.items():
        ln = line(wid)
        rooms.append({'id': f'walk-{wid}', 'kind': 'corridor', 'name': name, 'poly': band(ln, half),
                      'labelAt': along(ln), 'z': 1})
        walk_lines.append((f'walk-{wid}', ways[wid]['nodes'], ln))
    near = [G(*nodes[n]) for n in ways['1225567916']['nodes']]
    nx0, nx1 = min(p[0] for p in near) - 60, max(p[0] for p in near) + 60
    ny0, ny1 = min(p[1] for p in near) - 60, max(p[1] for p in near) + 60
    cw = [p for p in line('432062186') if nx0 <= p[0] <= nx1 and ny0 <= p[1] <= ny1]
    rooms.append({'id': 'Cliff Walk', 'kind': 'space', 'name': 'The Cliff Walk: a public path along the edge of the '
                  'estate (visitors to the house come in from Bellevue Avenue)', 'poly': band(cw, 5), 'labelAt': along(cw, 0.35),
                  'label': 'Cliff Walk', 'z': 1})
    a, b = walk_lines
    common = set(a[1]) & set(b[1])
    if common:
        doors.append({'a': a[0], 'b': b[0], 'at': G(*nodes[sorted(common)[0]]), 'width': 10, 'axis': 'o'})
    else:
        d, pt = poly_line_gap(band(b[2], 8), a[2])
        doors.append({'a': a[0], 'b': b[0], 'at': [round(pt[0], 1), round(pt[1], 1)], 'width': 10, 'axis': 'o'})
    for rid in ('House', 'Gate Lodge', 'Formal Garden'):
        r = next(x for x in rooms if x['id'] == rid)
        best = min((poly_line_gap(r['poly'], ln) + (w,) for w, _, ln in walk_lines), key=lambda t: t[0])
        at = to_g(131, 5) if rid == 'House' else [round(best[1][0], 1), round(best[1][1], 1)]
        doors.append({'a': best[2], 'b': rid, 'at': at, 'width': 10, 'axis': 'o'})
    doors += [{'a': 'House', 'b': 'Ocean Terrace', 'at': to_g(144, 81.5), 'width': 10, 'axis': 'o'},
              {'a': 'Ocean Terrace', 'b': 'Ocean Lawn', 'at': to_g(130, 112), 'width': 10, 'axis': 'o'},
              {'a': 'Grounds', 'b': 'walk-874518512', 'at': gate, 'width': 10, 'axis': 'o'}]

    amen = [{'type': 'entrance', 'at': gate}, {'type': 'entrance', 'at': to_g(131, 0)},
            {'type': 'restroom-all', 'at': to_g(54, 26)}]
    def lab(t, k, p): return {'text': t, 'kind': k, 'at': p}
    stop = G(*nodes['11507597611'])
    labels = [lab('Gate on Bellevue Avenue (visitors’ way in)', 'note', [gate[0] - 70, gate[1]]),
              lab('Bus 67 stops “Bellevue after / opposite Rough Point”', 'note', [stop[0] - 40, stop[1] - 26]),
              lab('Bellevue Avenue', 'area', G(41.4565, -71.3070)),
              lab('P · Limited parking on site (accessible spaces); else Newport Gateway Center + free Route 67 trolley',
                  'note', to_g(40, -150)),
              lab('Rough Point (the rocks)', 'area', G(*nodes['7516155274'])),
              lab('Atlantic Ocean', 'area', G(41.4535, -71.3030)),
              lab('North is about a third of the way right of up (turned so the house stands straight)', 'note',
                  to_g(-60, 420)),
              lab('Lawn and formal garden placed approximately', 'note', to_g(40, 330))]
    return {'id': 'G', 'label': 'Grounds', 'order': 0,
            'area': 'Gate · drive · house · lions terrace · ocean lawn · formal garden · Cliff Walk',
            'transform': [1, 0, 0], 'rooms': rooms, 'closed': [], 'amenities': amen, 'labels': labels, 'doors': doors,
            'homeView': ['House', 'Ocean Terrace', 'Ocean Lawn', 'Formal Garden']}


def build_floors():
    nodes, ways = osm()
    transform, to_g, outline = house_frame(nodes, ways)
    floors = [build_grounds(nodes, ways, to_g, outline)]
    for i, (fid, spec) in enumerate(FLOORS.items()):
        floors.append(build_house_floor(fid, spec, i + 1, transform))
    return {'about': 'Built by tools/build_roughpoint.py. The grounds and the outline of the house come from '
                     'OpenStreetMap, turned 32.8° so the house stands straight. NRF publishes no floor plan: the rooms '
                     'are APPROXIMATE, fitted into the outline from the museum’s own descriptions (Great Hall, Stair '
                     'Hall, Dining Room, Morning Room, Pine and Yellow Rooms, Solarium, Anteroom, the 1920s Music Room; '
                     'Doris Duke’s bedroom and the exhibition galleries upstairs). The elevator and restrooms exist but '
                     'their places are guessed.',
            'source': SOURCE, 'units': 'grounds: map units of 0.35 m; house: 4 units per foot, drawn larger than life over its place on the grounds',
            'approximate': True, 'defaultFloor': '1', 'galleryWord': 'Room', 'floors': floors}


# ---- pictures ---------------------------------------------------------------------------------------------------
_last = [0.0]


def picture(key, url):
    """Download once (politely, 4 s apart) and save a phone-sized JPEG; returns the app path."""
    if not url: return None
    if not url.startswith('http'): url = SITE + '/wp-content/uploads/' + url
    raw = CACHE / 'img' / (key + (Path(url.split('?')[0]).suffix.lower() or '.jpg'))
    dest = OUT / 'images' / f'{key}.jpg'
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        out = b''
        for i in range(3):
            wait = _last[0] + 4 - time.time()
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
    return f'data/roughpoint/images/{key}.jpg'


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower().replace('’', '')).strip('-')[:44]


def text_of(s):
    s = re.sub(r'(?s)<(script|style|noscript|svg)[^>]*>.*?</\1>', '', s)
    s = re.sub(r'<(br|/p|/div|/h\d|/li)[^>]*>', '\n', s)
    s = html.unescape(re.sub(r'<[^>]+>', '', s))
    s = re.sub(r'[ \t\xa0]+', ' ', s)
    return re.sub(r'\n\s*\n+', '\n', s)


def page(path):
    f = CACHE / 'html' / (path.strip('/').replace('/', '_') + '.html')
    return f.read_text(encoding='utf-8', errors='ignore') if f.exists() else ''


# ---- the rooms (floor, place, title, words, picture in the NRF media library, page) -----------------------------
RP = 'programs-initiatives/telling-stories-dispersed-monument/rough-point/'
ROOMS = [
    ('1', 'Great Hall', 'The Great Hall',
     'The first room you enter: NRF calls it a room full of objects that stand for the Duke family’s success and '
     'taste. Look for the 17th-century Spanish curiosity cabinet with Bol’s Portrait of a Young Woman above it, and the '
     'red damask wingchairs already listed here in the Dukes’ 1925 inventory.', '2024/03/01010034-scaled.jpg', RP),
    ('1', 'Stair Hall', 'The Stair Hall and grand staircase',
     'Follow the full-length portraits up the grand staircase: a future king (Van Dyck’s Charles, Prince of Wales), a '
     'noblewoman, a marchioness, then Nanaline Duke and, beside her, Doris Duke as a girl of eleven. Three of the '
     'Scipio tapestries hang here too; there is a stained-glass window on the landing.', '2024/03/RP_Stairs-scaled.jpg',
     RP),
    ('1', 'Dining Room', 'The Dining Room',
     'Doris Duke set the dining table to take full advantage of the ocean views from the east windows; the two '
     'early-16th-century Flemish tapestries hang at either end of it.', '2024/04/DiningRoomFromStairHall-scaled.jpg', RP),
    ('1', 'Morning Room', 'The Morning Room',
     'A panelled sitting room. On NRF’s tour it holds a 3D-printed model of a Guanyin figure that you are welcome to '
     'touch.', '2024/03/RP_MorningRoom-scaled.jpg', RP),
    ('1', 'Pine Room', 'The Pine Room',
     'Where the 1700s meet the 1900s: an 18th-century mirror Doris Duke found in a Paris flea market hangs near her '
     'Sony reel-to-reel tape recorder.', '2024/03/RP_PineRoomChair_final-scaled.jpg', 'my-favorite-room-doris-dukes-bedroom'),
    ('1', 'Yellow Room', 'The Yellow Room',
     'Doris Duke’s sitting room. Hoppner’s portrait of Charles Oldfield Bowles hangs here.', None, RP),
    ('1', 'Solarium', 'The Solarium',
     'The sunroom on the ocean side of the house. The gilded wrought-iron console tables came from the New York '
     'mansion where Doris Duke grew up; she moved them here in the late 1950s.', '2024/01/solarium-website.jpg', RP),
    ('1', 'Anteroom', 'The Anteroom', 'The small room before the Music Room.', '2024/03/RP_AnteroomWall_finish-scaled.jpg',
     RP),
    ('1', 'Music Room', 'The Music Room',
     'Part of the Duke family’s 1920s addition, and filled with objects from many cultures. Doris Duke rearranged it '
     'many times as its use changed, and in the 1960s hung it with 18th-century Chinese wallpaper she had bought at '
     'auction in Paris.', None, RP),
    ('1', 'Kitchen', 'The Kitchen',
     'Late-20th-century appliances sit next to fittings from earlier in the century, including the porcelain-tiled '
     'humidor built around 1900 for James B. “Buck” Duke’s cigars.', None, 'my-favorite-room-doris-dukes-bedroom'),
    ('2', 'Stair Landing', 'The second-floor landing',
     'The two oil studies by Jean-Baptiste Oudry hang here: sketches for panels painted for a French dining room in '
     'the 1700s.', '2024/04/RP_Stairhall-scaled-e1712588345504.jpg', RP),
    ('2', 'Doris Duke’s Bedroom', 'Doris Duke’s bedroom',
     'Bright yellow walls (first painted purple), purple curtains and furniture faced with mother-of-pearl, one of her '
     'favourite materials. A Renoir of 1875 hangs near an AT&T Merlin phone system of the 1980s: “the place where the '
     '1880s and 90s meet the 1980s and 90s”, as NRF’s director of museums put it.',
     '2024/01/doris-bedroom_nrf-scaled.jpg', 'my-favorite-room-doris-dukes-bedroom'),
    ('G', 'House', 'Rough Point from the drive', 'Built in 1887–91 for Frederick W. Vanderbilt by Peabody & Stearns to '
     'look like a 16th-century English manor; the Dukes bought it in 1922 and had Horace Trumbauer enlarge it. Doris '
     'Duke left it to the Newport Restoration Foundation, and it opened as a museum in 2000.',
     '2024/03/RP_Exterior-scaled.jpg', RP),
    ('G', 'House', 'The ocean front of Rough Point', 'The house seen from the lawn on the ocean side.',
     '2024/03/RP_Rear_ext-scaled.jpg', RP),
    ('G', 'Ocean Terrace', 'The lions terrace', 'Stone lions guard the terrace on the ocean side of the house.',
     '2024/03/RP_Lions-scaled.jpg', RP),
    ('G', 'Ocean Lawn', 'The Olmsted landscape and arboretum',
     'The grounds were laid out by F.L. & J.C. Olmsted for the Vanderbilts. Hurricane Carol (1954) washed away the '
     'Cliff Walk bridge and badly damaged them. In April 2026 Rough Point was accredited as a Level 1 arboretum.',
     '2026/04/RoughPoint.Landscape.2026.jpg', RP),
    ('G', 'Formal Garden', 'The formal garden', 'The walled formal garden; NRF’s gardeners still grow dahlias, as '
     'Doris Duke did.', '2024/01/Rough-Point-Formal-Garden-scaled-1.jpg', RP),
]

# Collection highlights placed by what their pages say: slug -> (floor, room, how we know)
PLACE = {
    'curiosity-cabinet': ('1', 'Great Hall', 'room'),
    'wingchairs-in-the-william-and-mary-style': ('1', 'Great Hall', 'room'),
    'portrait-of-a-young-woman-by-bol': ('1', 'Great Hall', 'text'),
    'portrait-of-nanaline-holt-inman-duke': ('1', 'Stair Hall', 'room'),
    'portrait-of-caroline-spencer-fourth-duchess-of-marlborough-by-reynolds': ('1', 'Stair Hall', 'text'),
    'portrait-of-charles-prince-of-wales-later-charles-ii-by-van-dyck': ('1', 'Stair Hall', 'staircase'),
    'portrait-of-the-marchioness-of-wellesley-by-hoppner': ('1', 'Stair Hall', 'staircase'),
    'portrait-of-doris-duke-at-11-years-old': ('1', 'Stair Hall', 'staircase'),
    'series-of-scipio-tapestries': ('1', 'Stair Hall', 'text'),
    'tapestry-with-proclamation-scene': ('1', 'Dining Room', 'text'),
    'portrait-of-charles-oldfield-bowles-by-hoppner': ('1', 'Yellow Room', 'room'),
    'pair-of-wrought-iron-console-tables-with-gilding': ('1', 'Solarium', 'text'),
    '20-panels-of-hand-painted-chinese-wallpaper': ('1', 'Music Room', 'text'),
    'sunburst-wall-clock': ('1', 'Music Room', 'text'),
    'cigar-storage-case': ('1', 'Kitchen', 'post'),
    'study-for-decorative-panel-with-barbet-by-oudry': ('2', 'Stair Landing', 'text'),
    'study-for-decorative-panel-with-two-hounds-by-oudry': ('2', 'Stair Landing', 'text'),
    'jeune-fille-blonde-cousant-young-blonde-girl-sewing': ('2', 'Doris Duke’s Bedroom', 'post'),
}
HOW = {
    'room': 'The room is the one NRF’s collection page gives; its place on the map is approximate.',
    'text': 'NRF’s page says it is in this room; the room’s place on the map is approximate.',
    'staircase': 'NRF’s page on the Reynolds portrait lists it among the portraits up the grand staircase; the '
                 'room’s place on the map is approximate.',
    'post': 'Named in this room by NRF’s director of museums (2019); it may have moved since.',
}

# 2026 exhibitions: (slug, floor, room) - the rooms they use are not published, so the places are approximate
SHOWS = [
    ('women-designers-of-the-20th-century', '2', 'Fashion Gallery'),
    ('keeping-rough-point-above-water', '2', 'Exhibition Gallery'),
    ('fashioning-resiliency', '2', 'Fashion Gallery'),
    ('1776-2026', '2', 'Newport Galleries'),
    ('newport-galleries', '2', 'Newport Galleries'),
]


def collection():
    sm = (CACHE / 'sm_collection.xml').read_text()
    rows = []
    for u in re.findall(r'<loc>([^<]+)</loc>', sm):
        m = re.search(r'/collection/([^/]+)/$', u)
        if not m: continue
        slug = m[1]
        s = page(f'collection/{slug}/')
        if not s: continue
        h1 = re.search(r'<h1[^>]*>(.*?)</h1>', s, re.S)
        title = html.unescape(re.sub('<[^>]+>', '', h1[1])).strip() if h1 else slug
        if re.fullmatch(r'\d+', slug) or not title: continue
        t = text_of(s)
        body = t.split('Collection \n / ', 1)[-1].split('\n Programs & Initiatives\n')[0]
        lines = [x.strip() for x in body.split('\n')[1:] if x.strip()]
        fields, words = {}, []
        keys = ('Artist', 'Place/Date of Manufacture', 'Materials', 'Accession Number', 'Location', 'Room',
                'Newportal Link', 'Dimensions', 'Credit Line', 'Credit')
        i = 0
        while i < len(lines):
            if lines[i] in keys:
                j = i + 1
                vals = []
                while j < len(lines) and lines[j] not in keys and len(vals) < 3:
                    vals.append(lines[j]); j += 1
                fields[lines[i]] = '; '.join(vals)
                i = j
            else:
                if not fields: words.append(lines[i])
                i += 1
        img = re.search(r'og:image" content="([^"]+)', s)
        rows.append({'slug': slug, 'title': title, 'words': ' '.join(words), 'artist': fields.get('Artist'),
                     'made': fields.get('Place/Date of Manufacture'), 'materials': fields.get('Materials'),
                     'room': fields.get('Room'), 'image': img[1] if img else None,
                     'accession': fields.get('Accession Number')})
    return rows


def short(words, n=600):
    if len(words) <= n: return words
    cut = words[:n].rsplit('. ', 1)[0]
    return (cut if len(cut) > 200 else words[:n].rsplit(' ', 1)[0]) + '…'


def year_of(made):
    m = re.search(r'\b(1[0-9]{3})\b', made or '')
    return int(m[1]) if m else None


def date_of(made):
    if not made: return None
    parts = [p.strip() for p in made.split(',')]
    return parts[-1] if len(parts) > 1 else made


def place_of(made):
    if not made: return None
    parts = [p.strip() for p in made.split(',')]
    return ', '.join(parts[:-1]) if len(parts) > 1 else None


def exhibition(slug):
    s = page(f'exhibitions/{slug}/')
    h1 = re.search(r'<h1[^>]*>(.*?)</h1>', s, re.S)
    title = html.unescape(re.sub('<[^>]+>', '', h1[1])).strip() if h1 else slug
    t = text_of(s)
    body = t.split('Exhibition / \n', 1)[-1].split('\n Location\n')[0]
    lines = [x.strip() for x in body.split('\n') if x.strip() and x.strip() != title and len(x.strip()) > 40
             and not x.strip().startswith(('Included in admission', 'Special thank', 'This program is supported',
                                            'EXPLORE THE'))]
    img = re.search(r'og:image" content="([^"]+)', s)
    return title, short(' '.join(lines[:4]), 700), img[1] if img else None


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

    for floor, place, title, words, path, pg in ROOMS:
        key = f'rp-{slugify(title)}'
        im = picture(key, path)
        add({'id': key, 'title': title, 'artist': 'Rough Point',
             'medium': 'Room' if floor != 'G' else ('Garden' if place in ('Formal Garden', 'Ocean Lawn') else
                                                     'Historic place'),
             'description': words, 'descriptionKind': 'From the Newport Restoration Foundation’s pages',
             'url': f'{SITE}/{pg}/'.replace('//', '/').replace('https:/', 'https://'),
             'image': im, 'imageCredit': im and 'Newport Restoration Foundation',
             'placeNote': 'Room places on the map are approximate: NRF publishes no floor plan.' if floor != 'G'
             else None}, floor, place)
    for r in collection():
        key = f'rp-c-{slugify(r["title"])}'
        im = picture(key, r['image'])
        where = PLACE.get(r['slug'])
        add({'id': key, 'title': r['title'], 'artist': r['artist'] or 'Unrecorded maker',
             'date': date_of(r['made']), 'year': year_of(r['made']), 'place': place_of(r['made']),
             'medium': r['materials'], 'accession': r['accession'],
             'description': short(r['words']), 'descriptionKind': 'From the Newport Restoration Foundation’s Collection page',
             'url': f'{SITE}/collection/{r["slug"]}/', 'image': im, 'imageCredit': im and 'Newport Restoration Foundation',
             'placeNote': HOW[where[2]] if where else
             'In the Rough Point collection; NRF does not say which room it is in (fashion is shown in changing '
             'exhibitions, so it may be in storage).'}, *(where[:2] if where else (None, None)))
    for slug, floor, room in SHOWS:
        title, words, img = exhibition(slug)
        key = f'rp-x-{slugify(title)}'
        im = picture(key, img)
        add({'id': key, 'title': title, 'artist': 'Exhibition at Rough Point, 2026', 'date': '2026', 'year': 2026,
             'medium': 'Exhibition', 'description': words, 'descriptionKind': 'From the exhibition page',
             'url': f'{SITE}/exhibitions/{slug}/', 'image': im, 'imageCredit': im and 'Newport Restoration Foundation',
             'placeNote': 'NRF does not say which rooms each exhibition uses: the place on the map is approximate.'},
            floor, room)
    order = {(f['id'], r['id']): (fi, i) for fi, f in enumerate(floors['floors']) for i, r in enumerate(f['rooms'])}
    placed.sort(key=lambda a: (order[(a['floor'], a['gallery'])], a['artist'] != 'Rough Point', 'image' not in a))
    return {'source': 'Newport Restoration Foundation website (newportrestoration.org): Collection highlights, '
                      'exhibitions and room pages', 'checked': time.strftime('%Y-%m-%d'),
            'count': len(placed), 'complete': False, 'artworks': placed}, unplaced


def build_guide(works, unplaced):
    rows = []
    for a, on in [(a, True) for a in works['artworks']] + [(a, False) for a in unplaced]:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a.get('title') or a['id'], 'artist': a.get('artist'),
                     'date': a.get('date'), 'year': a.get('year'), 'medium': a.get('medium'), 'url': a['url'],
                     'imageUrl': a.get('image'), 'onView': on, 'gallery': a.get('gallery'),
                     'floor': a.get('floor')}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': 'Rough Point', 'checked': time.strftime('%Y-%m-%d'),
            'source': 'Newport Restoration Foundation website; OpenStreetMap', 'onViewKnown': False,
            'note': 'Rough Point was Doris Duke’s Newport home, left as she lived in it: Old Master paintings, '
                    'tapestries and French furniture beside 1980s phones and appliances. This guide lists the rooms, '
                    'every highlight the Newport Restoration Foundation publishes from the collection (placed in a '
                    'room only when NRF names it) and the 2026 exhibitions. The house is open through November 8, '
                    'then for “A Rough Point Holiday” on weekends from November 27 to December 27.',
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
    missing = set(PLACE) - {a['url'].rstrip('/').split('/')[-1] for a in works['artworks']}
    if missing: print('placed slugs not found:', sorted(missing))


if __name__ == '__main__':
    sys.exit(main())
