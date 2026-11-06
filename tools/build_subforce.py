#!/usr/bin/env python3
"""Build the Submarine Force Museum and Historic Ship Nautilus (Groton, CT) map guide.
Run: python3 tools/build_subforce.py

    data/subforce/floors.json     the grounds and the museum's ground floor, its upper level, and the Nautilus (flat 2D)
    data/subforce/artworks.json   the submarines, artifacts, exhibits and the Nautilus's compartments, each in its place
    data/subforce/images/         pictures from Wikimedia Commons, made smaller for phones
    data/guides/Q7631596.json     the same list, plus the library's treasures (not on view), for the museum page

Where the information comes from
--------------------------------
The museum's own site (ussnautilus.org) sits behind a bot check that refuses this script, its visitor packet PDF
included, so it is not read. The Navy publishes no floor plan of the museum online. The plan is drawn from:
  - OpenStreetMap (ODbL, api.openstreetmap.org/api/0.6/map, read once into .cache/subforce/osm.xml): the museum
    building (way 472159509), the Nautilus (47997926) and her pier (47997916), the small pier building (1552510018),
    the parking lot, gardens, the memorial plaza with the USS George Washington sail (1552768032), the four
    small submarines on the lawn (1552768035-38), the Nautilus propellers, the Harpoon missile and the 41 for Freedom
    memorial (nodes from the hmdb.org markers), the picnic area and the railroad. These are true to scale.
  - visitors' and writers' descriptions (Recoil magazine, Coast2Coast with Kids, Katie Wanders, Wikipedia): the
    entrance with the Jules Verne Nautilus model and the gift shop beside it; restrooms near the entrance; a section
    with the theater and the modern-submarine displays; a main hallway with the cutaway model, the model wall, the
    mock control room and the periscope room (three working periscopes through the roof, looking at the Nautilus and
    the Thames); the large two-storey gallery with the Turtle, the Gato model, the McCann rescue chamber, torpedoes
    and the Polaris missile; an elevator to the upper level; the Nautilus reached through the museum, across the
    railroad; the Nautilus tour of the forward compartments (torpedo room, berthing, galley, crew's mess with the
    battery well under a glass hatch, attack center, wardroom and officers' staterooms), in and out by the deckhouse.
Which room inside the building holds which exhibit is our reading of those descriptions: the map says APPROXIMATE.
Which of the four small submarines on the lawn is which is read from their lengths in OpenStreetMap (HA-8 24 m,
X-1 15 m, SDV 6 m).
The Nautilus floor is a diagram (not to scale across: the hull is drawn three times as deep as it is).

Pictures: Wikimedia Commons files of the objects at this museum (photographers and licences in each credit).
The map is turned 16° so the museum's long front runs left to right: up is north-north-west.
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
OUT = ROOT / 'data' / 'subforce'
CACHE = ROOT / '.cache' / 'subforce'
MUSEUM = 'Q7631596'
NAME = 'Submarine Force Museum and Historic Ship Nautilus'
SITE = 'https://ussnautilus.org/'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
K = 4                                   # map units per metre
LAT0, LON0 = 41.3875, -72.0870
OSM_BBOX = '-72.0905,41.3855,-72.0835,41.3895'
TURN = math.atan2(10.2, 35.4)           # the museum's front wall, 16° north of east


def fetch(url, dest, pause=3):
    if dest.exists() and dest.stat().st_size > 500: return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    for wait in (0, 20, 60):
        time.sleep(wait or pause)
        r = subprocess.run(['curl', '-s', '-L', '-m', '120', '-A', UA, '-w', '%{http_code}', '-o', str(dest), url],
                           capture_output=True, text=True)
        if r.stdout.strip() == '200' and dest.stat().st_size > 500: return True
        dest.unlink(missing_ok=True)
    return False


def P(u, v):
    """Turned metres (u along the museum front, v towards the parking lot) -> map units."""
    return [round((u + 135) * K, 1), round((100 - v) * K, 1)]


def turn(p):
    x, y = p
    c, s = math.cos(TURN), math.sin(TURN)
    return (round(x * c + y * s, 2), round(-x * s + y * c, 2))


def rect(u0, v0, u1, v1):
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


def clip(poly, box):
    """The part of poly inside the rectangle box (Sutherland-Hodgman; the box is convex)."""
    x0, y0, x1, y1 = box
    edges = [(lambda p: p[0] >= x0, lambda a, b: (x0, a[1] + (b[1] - a[1]) * (x0 - a[0]) / (b[0] - a[0]))),
             (lambda p: p[0] <= x1, lambda a, b: (x1, a[1] + (b[1] - a[1]) * (x1 - a[0]) / (b[0] - a[0]))),
             (lambda p: p[1] >= y0, lambda a, b: (a[0] + (b[0] - a[0]) * (y0 - a[1]) / (b[1] - a[1]), y0)),
             (lambda p: p[1] <= y1, lambda a, b: (a[0] + (b[0] - a[0]) * (y1 - a[1]) / (b[1] - a[1]), y1))]
    out = list(poly)
    for inside_, cut in edges:
        src, out = out, []
        for i, cur in enumerate(src):
            prev = src[i - 1]
            if inside_(cur):
                if not inside_(prev): out.append(cut(prev, cur))
                out.append(cur)
            elif inside_(prev):
                out.append(cut(prev, cur))
    pts = []
    for p in out:
        p = (round(p[0], 2), round(p[1], 2))
        if not pts or p != pts[-1]: pts.append(p)
    if len(pts) > 1 and pts[0] == pts[-1]: pts.pop()
    return pts


def band(pts, half):
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        left.append((x - dy / n * half, y + dx / n * half)); right.append((x + dy / n * half, y - dx / n * half))
    return left + right[::-1]


def inside(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def osm():
    dest = CACHE / 'osm.xml'
    if not fetch(f'https://api.openstreetmap.org/api/0.6/map?bbox={OSM_BBOX}', dest):
        raise SystemExit('could not read OpenStreetMap')
    r = ET.parse(dest).getroot()
    c = math.cos(math.radians(LAT0))
    nodes = {n.get('id'): turn(((float(n.get('lon')) - LON0) * 111320 * c, (float(n.get('lat')) - LAT0) * 110540))
             for n in r.iter('node')}
    ways = {}
    for w in r.iter('way'):
        pts = [nodes[n.get('ref')] for n in w.findall('nd') if n.get('ref') in nodes]
        if len(pts) > 1 and pts[0] == pts[-1]: pts = pts[:-1]
        ways[w.get('id')] = pts
    named = {}
    for n in r.iter('node'):
        t = {x.get('k'): x.get('v') for x in n.findall('tag')}
        if 'name' in t: named[t['name']] = nodes[n.get('id')]
    return ways, named


def build_floors():
    w, named = osm()
    B = w['472159509']                    # the museum, u -40..36, v -14.9..8.4 once turned
    pts = w['1552517517'] + w['1552768032'] + [named[k] for k in ('41 For Freedom', 'USS Nautilus Propellers',
                                                                   'USS George Washington (SSBN 598) Sail')]
    plaza = rect(min(p[0] for p in pts) - 3, min(p[1] for p in pts) - 3, max(p[0] for p in pts) + 3,
                 max(p[1] for p in pts) + 3)
    rail = band(w['507227235'][5:10], 2.5)
    G = [
        # inside the museum (APPROXIMATE)
        ('Lobby', 'space', 'Lobby: the docent desk (free scavenger hunt for children), restrooms, and Jules Verne’s '
         'Nautilus hanging just inside the doors', clip(B, (3.3, -15, 14.3, 1.0)), None),
        ('Museum Store', 'space', 'Museum Store (run by the Submarine Force Library & Museum Association): submarine '
         'and Connecticut gifts; the way out goes through it', clip(B, (14.3, -15, 24, 9)), None),
        ('Theater', 'gallery', 'Theater (about 80 seats): a film on submarine history plays on a loop',
         clip(B, (24, -1.5, 37, 9)), 'Theater'),
        ('Today’s Submarine Force', 'gallery', 'Today’s Submarine Force: modern submarines, what they do and how the '
         'Submarine Force is organised', clip(B, (24, -15, 37, -1.5)), 'Today'),
        ('Main Hallway', 'gallery', 'Main Hallway: the cutaway model of a modern submarine and the wall of submarine '
         'models, all to one scale, from the Holland to the Columbia class', clip(B, (-10, -3, 3.3, 9)), 'Hallway'),
        ('Control Room', 'gallery', 'Control Room: the real control center of USS Sturgeon (SSN-637); take the '
         'controls and try steering a submarine', clip(B, (-10, -15, -3.5, -3)), 'Control'),
        ('Attack Center', 'gallery', 'Attack Center: three working periscopes through the roof; look at the Nautilus, '
         'the Thames and the Coast Guard Academy across the river', clip(B, (-3.5, -15, 3.3, -3)), 'Periscopes'),
        ('Main Gallery', 'gallery', 'Main Gallery (two storeys high): Bushnell’s Turtle, the big Gato model, the '
         'McCann rescue chamber, torpedoes, the Polaris missile and the history of the U.S. Submarine Force',
         clip(B, (-41, -15, -10, 9)), 'Main Gallery'),
        # outside (OpenStreetMap)
        ('Entrance Walk', 'corridor', 'Walk to the main entrance, under the two hull rings',
         [(3.6, 8.3), (14.2, 8.3), (14.2, 1.2), (12.1, 2.3), (8.6, 2.3), (8.6, 1.0), (3.4, 1.1)] , None),
        ('Front Lawn', 'gallery', 'Front lawn: the Japanese HA-8 and the U.S. X-1 midget submarines, a swimmer delivery '
         'vehicle, sections of the NR-1, a deck gun and the Harpoon missile at the door',
         [(-40, 8.4), (3.6, 8.3), (14.2, 8.4), (14.2, 22), (-6, 26), (-30, 34), (-40, 34)], 'Lawn'),
        ('Parking', 'space', 'Free parking (gates are locked after closing time); picnic tables at the far end of the lot',
         clip(w['47997870'], (-200, -200, 200, 70)), None),
        ('Memorial Plaza', 'gallery', 'Memorial Plaza: the sail of USS George Washington (SSBN-598), the Nautilus '
         'propellers and the 41 for Freedom memorial', plaza, 'Plaza'),
        ('Railroad', 'space', 'Railroad tracks (Providence and Worcester freight line)', clip(rail, (-70, 3, -40, 70)),
         None),
        ('Railroad south', 'space', 'Railroad tracks: cross only on the walkway', clip(rail, (-70, -70, -40, -3)),
         None),
        ('Walkway to the Nautilus', 'corridor', 'Walkway from the museum to the pier, across the railroad',
         [(-40.2, -3), (-40.2, 3), (-56.7, 3), (-56.7, -3)], None),
        ('Nautilus Pier', 'corridor', 'Nautilus Pier: at the small pier house a sailor on duty hands out the '
         'audio-tour wands', w['47997916'], None),
        ('Brow', 'corridor', 'Brow (gangway) onto the Nautilus', rect(-109.3, -14, -96.8, -9), None),
        ('USS Nautilus', 'gallery', 'Historic Ship Nautilus (SSN-571), the first nuclear-powered submarine: a '
         'self-guided audio tour of the forward compartments, about 30 minutes (see the Nautilus floor)',
         w['47997926'], 'Nautilus'),
    ]
    G_DOORS = [('Entrance Walk', 'Lobby', (8.6, 1.0)), ('Lobby', 'Museum Store', (14.3, -5)),
               ('Museum Store', 'Theater', (24, 3)), ('Museum Store', 'Today’s Submarine Force', (24, -7)),
               ('Lobby', 'Main Hallway', (3.3, -1)), ('Main Hallway', 'Control Room', (-6.7, -3)),
               ('Main Hallway', 'Attack Center', (0, -3)), ('Main Hallway', 'Main Gallery', (-10, 3)),
               ('Main Gallery', 'Walkway to the Nautilus', (-40.2, 0)),
               ('Walkway to the Nautilus', 'Nautilus Pier', (-56.7, -1)), ('Nautilus Pier', 'Brow', (-96.8, -11.5)),
               ('Brow', 'USS Nautilus', (-109.3, -11.5)), ('Entrance Walk', 'Front Lawn', (9, 8.3)),
               ('Front Lawn', 'Parking', (-5, 26))]
    G_AMEN = [('entrance', 8.6, 4), ('info', 6, -3), ('restroom', 5.5, -9), ('restroom-all', 9, -9),
              ('water', 12, -9), ('shop', 19, -2), ('elevator', -7, 6), ('stairs', -2, 6),
              ('entrance', -42, 0), ('info', -58, -2), ('entrance', -112, -12)]
    G_LABELS = [('Thames River', -135, -45), ('Crystal Lake Road →', 50, 30),
                ('Approximate rooms inside the real building outline (no plan is published)', -25, -25),
                ('Naval Submarine Base New London (no entry) ↑', 20, 80)]
    U = [
        ('Balcony', 'gallery', 'Upper level: the balcony over the Main Gallery, looking down on the Turtle and the Gato '
         'model', clip(B, (-41, -15, -10, 9)), 'Balcony'),
        ('Upper Hall', 'gallery', 'Upper level hall (approximate)', clip(B, (-10, -15, 3.3, 9)), 'Upper'),
        ('Library', 'space', 'Library and archives: some 6,000 books, documents and photographs (closed to the public; '
         'researchers by appointment)', clip(B, (3.3, -15, 37, 9)), None),
    ]
    U_DOORS = [('Balcony', 'Upper Hall', (-10, 3)), ('Upper Hall', 'Library', (3.3, -1))]
    U_AMEN = [('elevator', -7, 6), ('stairs', -2, 6)]
    U_LABELS = [('Upper level: approximate', 10, 16)]

    # ---- the Nautilus, a diagram: bow on the left, 97 m long, the hull drawn three times as deep ----
    f = 1.5                                  # map metres per metre of hull
    def m(x): return -112 + x * f
    top, mid, bot = 40, 26, 12              # v of the hull top, the deck between the levels, the keel
    hull = [(m(0), mid), (m(2), mid + 9), (m(6), top), (m(85), top), (m(95), mid + 6), (m(97), mid),
            (m(95), mid - 6), (m(85), bot), (m(6), bot), (m(2), mid - 9)]
    N = [
        ('Deckhouse', 'corridor', 'Deckhouse on the forward deck: the way in and out of the submarine, down a steep '
         'ladder', rect(m(10), top, m(18), top + 8), None),
        ('Forward Torpedo Room', 'gallery', 'Forward Torpedo Room: six torpedo tubes, reload racks and bunks squeezed '
         'between them', clip(hull, (m(0), bot, m(20), top)), 'Torpedo Room'),
        ('Wardroom', 'gallery', 'Wardroom, the officers’ dining and meeting room', rect(m(20), mid, m(27), top),
         'Wardroom'),
        ('Officers’ Staterooms', 'gallery', 'Officers’ country: the Captain’s and Executive Officer’s staterooms and '
         'the small arms locker', rect(m(27), mid, m(36), top), 'Officers'),
        ('Nautilus Attack Center', 'gallery', 'Attack Center: periscopes, fire control and the Officer of the Deck; '
         'a voice tube passes orders to the control room below', rect(m(36), mid, m(48), top), 'Attack Center'),
        ('Crew’s Berthing', 'gallery', 'Crew’s berthing and the chiefs’ quarters: three-high bunks',
         rect(m(20), bot, m(30), mid), 'Berthing'),
        ('Galley', 'gallery', 'Galley, where four cooks fed more than 100 men', rect(m(30), bot, m(35), mid), 'Galley'),
        ('Crew’s Mess', 'gallery', 'Crew’s mess: meals, movies, training and meetings; the battery well under a glass '
         'hatch in the deck', rect(m(35), bot, m(42), mid), 'Mess'),
        ('Nautilus Control Room', 'gallery', 'Control room: the diving and steering stations, under the attack '
         'center', rect(m(42), bot, m(48), mid), 'Control'),
        ('Engineering (closed)', 'space', 'Reactor compartment and engine rooms: not open to visitors (the tour '
         'stops here and goes back up to the deckhouse)', clip(hull, (m(48), bot - 10, m(97), top + 10)), None),
    ]
    N_DOORS = [('Deckhouse', 'Forward Torpedo Room', (m(14), top)), ('Forward Torpedo Room', 'Crew’s Berthing',
                                                                      (m(20), 18)),
               ('Crew’s Berthing', 'Galley', (m(30), 18)), ('Galley', 'Crew’s Mess', (m(35), 18)),
               ('Crew’s Mess', 'Nautilus Control Room', (m(42), 18)),
               ('Nautilus Control Room', 'Nautilus Attack Center', (m(45), mid)),
               ('Nautilus Attack Center', 'Officers’ Staterooms', (m(36), 33)),
               ('Officers’ Staterooms', 'Wardroom', (m(27), 33)), ('Wardroom', 'Forward Torpedo Room', (m(20), 33))]
    N_AMEN = [('entrance', m(14), top + 4), ('stairs', m(44), mid + 3)]
    N_LABELS = [('Bow ←', m(3), top + 8), ('→ Stern', m(92), top + 8),
                ('Diagram, not to scale: the hull is drawn three times as deep', m(48), bot - 8),
                ('Upper level', m(30), top + 13), ('Lower level', m(30), bot - 3)]

    def floor(fid, label, order, area, rooms, doors, amen, labels):
        rr = []
        for rid, kind, name, poly, short in rooms:
            assert len(poly) >= 3, rid
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': [P(*q) for q in poly]}
            if kind == 'gallery': r['label'] = short
            rr.append(r)
        return {'id': fid, 'label': label, 'order': order, 'transform': [1, 0, 0], 'area': area, 'rooms': rr,
                'closed': [], 'amenities': [{'type': t, 'at': P(x, y)} for t, x, y in amen],
                'labels': [{'text': t, 'kind': 'note', 'at': P(x, y)} for t, x, y in labels],
                'doors': [{'a': a, 'b': b, 'at': P(*p), 'width': 14, 'axis': 'o'} for a, b, p in doors]}
    floors = [
        floor('1', 'Museum · Grounds', 0, 'Entrance · Lobby · Main Gallery · Control Room · periscopes · outdoor '
              'submarines · the Nautilus pier', G, G_DOORS, G_AMEN, G_LABELS),
        floor('2', 'Upper level', 1, 'Balcony over the Main Gallery · Library (closed to the public)', U, U_DOORS,
              U_AMEN, U_LABELS),
        floor('N', 'Nautilus', 2, 'Historic Ship Nautilus: the tour of the forward compartments (diagram)', N,
              N_DOORS, N_AMEN, N_LABELS),
    ]
    for fl in floors:
        ids = [r['id'] for r in fl['rooms']]
        assert len(ids) == len(set(ids)), fl['id']
        for d in fl['doors']:
            assert d['a'] in ids and d['b'] in ids, (fl['id'], d)
        for a in fl['amenities']:
            assert any(inside(a['at'], r['poly']) for r in fl['rooms']), (fl['id'], a)
    return {'about': 'Built by tools/build_subforce.py. The building, the pier, the Nautilus, the lawn, the plaza and '
                     'the parking lot are traced from OpenStreetMap, true to scale, and turned 16° so the museum front '
                     'runs left to right (up is north-north-west). The Navy publishes no floor plan, so the rooms '
                     'inside the museum are placed from visitors’ descriptions and are approximate. The Nautilus is a '
                     'diagram of the compartments on the tour.',
            'source': 'OpenStreetMap (building, pier, Nautilus, grounds); visitors’ descriptions of the galleries; '
                      'rooms inside approximate',
            'units': f'metres x {K}, turned 16° (up is north-north-west); the Nautilus floor is a diagram',
            'approximate': True, 'defaultFloor': '1', 'galleryWord': 'Place', 'floors': floors}


# ---- the collection -----------------------------------------------------------------------------------------------

AUTHORS = {   # files whose page has no plain author line
    'Thresher_Commissioning_Bottle.JPG': 'Victor-ny',
    'HA-8,_Japanese_midget_submarine,_Submarine_Force_Library_&_Museum,_Groton,_Connecticut.jpg': 'Carol M. Highsmith',
}


def commons_meta(name):
    """Author and licence of a Commons file, read from its page (cached)."""
    dest = CACHE / 'files' / (name.replace('/', '_').replace('&', '_') + '.html')
    if not fetch('https://commons.wikimedia.org/wiki/File:' + urllib.parse.quote(name), dest, pause=2):
        raise SystemExit(f'no Commons page for {name}')
    s = dest.read_text(encoding='utf-8', errors='ignore')

    def row(label):
        i = s.find('>' + label)
        if i < 0: return ''
        t = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s[i + 1:i + 1500]))).strip()
        t = t[len(label):].strip()
        return re.split(r' (Permission|Source|Other versions|Camera location|Licensing|Date|Author) ', t)[0][:120]
    author = row('Author')
    author = re.sub(r'^Flickr user\s*:\s*https?://www\.flickr\.com/photos/([^/\s]+).*', r'\1 (Flickr)', author)
    author = re.sub(r'\s*\(.*?talk.*?\)', '', author)
    author = re.split(r' Object location| Camera location|<', author)[0].strip(' .:')
    if author.startswith('mw-parser-output') or not author:
        author = AUTHORS.get(name, '')
    cats = json.loads(re.search(r'"wgCategories":(\[[^\]]*\])', s).group(1))
    lic = next((c for c in cats if re.match(r'(CC[-‐ ]|PD[-‐ ]|Public domain|GFDL|Cc-zero|CC0)', c)), 'see Commons')
    return author or 'unknown', lic.replace('Cc-zero', 'CC0')


def picture(key, src):
    if not src: return None, None
    dest = OUT / 'images' / f'{key}.jpg'
    rel = f'data/subforce/images/{key}.jpg'
    author, lic = commons_meta(src)
    credit = f'{author}, {lic}, via Wikimedia Commons'
    if dest.exists(): return rel, credit
    raw = CACHE / 'img' / (key + '.bin')
    if not fetch('https://commons.wikimedia.org/wiki/Special:FilePath/' + urllib.parse.quote(src) + '?width=1000',
                 raw):
        print(f'  no picture: {src}')
        return None, None
    dest.parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(io.BytesIO(raw.read_bytes()))
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGB', im.size, 'white')
        bg.paste(im, mask=im.split()[-1])
        im = bg
    im = im.convert('RGB')
    im.thumbnail((1000, 1000))
    im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return rel, credit


# key, title, maker, date, type, place, place guessed?, Commons picture, words
WORKS = [
    # the Nautilus
    ('nautilus', 'USS Nautilus (SSN-571)', 'Electric Boat, Groton', '1954', 'Submarine', 'USS Nautilus', False,
     'USS_Nautilus_SSN571.JPG',
     'The world’s first nuclear-powered submarine. President Truman laid her keel at Electric Boat, across the river, '
     'in 1952, and Mamie Eisenhower christened her in January 1954. On January 17, 1955 she signalled “Underway on '
     'nuclear power”. On August 3, 1958 she was the first ship to reach the North Pole, passing under the Arctic ice '
     '(Operation Sunshine). Decommissioned in 1980, she has been a museum ship here since 1986: 97 m (319 ft) long.'),
    ('n-torpedo', 'Forward Torpedo Room', 'USS Nautilus', '1954', 'Compartment', 'Forward Torpedo Room', False,
     'Torpedo_tube_breech_doors_of_USS_Nautilus.jpg',
     'Where the tour begins, at the foot of the ladder from the deckhouse: the breech doors of the six bow torpedo '
     'tubes, the reload racks, and crew bunks tucked in between the torpedoes.'),
    ('n-berthing', 'Crew’s berthing and chiefs’ quarters', 'USS Nautilus', '1954', 'Compartment', 'Crew’s Berthing',
     False, None,
     'Bunks three high, each with a thin mattress, a reading light and a small locker: this was home for months at a '
     'time. Life-size mannequins show the crew at work and at rest throughout the boat.'),
    ('n-galley', 'Galley', 'USS Nautilus', '1954', 'Compartment', 'Galley', False, None,
     'A kitchen the size of a closet, where the cooks baked bread and made four meals a day for a crew of about 100. '
     'Good food was the submariner’s great comfort.'),
    ('n-mess', 'Crew’s mess', 'USS Nautilus', '1954', 'Compartment', 'Crew’s Mess', False, None,
     'The crew’s dining room was also their classroom, cinema and meeting room. Nautilus was one of the first '
     'submarines with an ice cream machine, a jukebox and a library.'),
    ('n-battery', 'Battery well', 'USS Nautilus', '1954', 'Compartment', 'Crew’s Mess', False,
     'Battery_well_of_USS_Nautilus.jpg',
     'Seen through a glass hatch in the deck: the batteries kept for emergencies, if the reactor shut down.'),
    ('n-eab', 'Emergency Air Breathing masks', 'USS Nautilus', '1954', 'Equipment', 'Crew’s Berthing', True, None,
     'Masks on hoses that plug into air manifolds all through the boat, so the crew could breathe in a fire or a '
     'smoke-filled compartment.'),
    ('n-attack', 'Attack center', 'USS Nautilus', '1954', 'Compartment', 'Nautilus Attack Center', False, None,
     'The heart of the boat: the periscopes, the fire-control equipment and a mannequin of the Officer of the Deck at '
     'the periscope. A voice tube passed orders down to the control room.'),
    ('n-control', 'Control room', 'USS Nautilus', '1954', 'Compartment', 'Nautilus Control Room', True, None,
     'The diving and steering stations, where the planesmen and helmsman drove the boat on the orders sent down from '
     'the attack center above.'),
    ('n-wardroom', 'Wardroom', 'USS Nautilus', '1954', 'Compartment', 'Wardroom', False, None,
     'The officers’ dining room, also their office and meeting room. Here the crew planned the 1958 voyage under the '
     'North Pole.'),
    ('n-captain', 'Captain’s and Executive Officer’s staterooms', 'USS Nautilus', '1954', 'Compartment',
     'Officers’ Staterooms', False, None,
     'The only private cabins on board, each barely bigger than a bunk and a desk. Commander William R. Anderson slept '
     'here on the North Pole voyage.'),
    ('n-arms', 'Small arms locker', 'USS Nautilus', '1954', 'Equipment', 'Officers’ Staterooms', True, None,
     'Shotguns and rifles kept for the watch on deck when the submarine was in port.'),
    ('n-engineering', 'Reactor and engine rooms', 'USS Nautilus', '1954', 'Compartment', 'Engineering (closed)', False,
     None,
     'The S2W reactor, built by Westinghouse under Admiral Hyman Rickover’s Naval Reactors program, and the steam '
     'turbines it drove are aft of the tour, and closed to visitors.'),
    # outside
    ('gw-sail', 'Sail of USS George Washington (SSBN-598)', 'Electric Boat, Groton', '1959', 'Submarine sail',
     'Memorial Plaza', False, 'USS_George_Washington_Sail.JPG',
     'The first ballistic-missile submarine, built in Groton and commissioned in 1959, carried 16 Polaris missiles. '
     'Strictly, the sail is that of USS Abraham Lincoln: George Washington’s own was replaced after she collided with '
     'the Japanese freighter Nissho Maru in 1981.'),
    ('propellers', 'USS Nautilus propellers', 'USS Nautilus', '1954–1980', 'Propellers', 'Memorial Plaza', False,
     'USS_Natilus_(SSN_571)_Propellers.jpg',
     'Two of the Nautilus’s propellers, taken off when she became a museum ship.'),
    ('41', '41 for Freedom memorial', 'Memorial', None, 'Memorial', 'Memorial Plaza', False, None,
     'A stone memorial to the “41 for Freedom”, the 41 Polaris ballistic-missile submarines built from 1959 to 1967, '
     'all named for Americans who stood for freedom, starting with the George Washington.'),
    ('harpoon', 'UGM-84 Harpoon missile', 'McDonnell Douglas', '1970s', 'Missile', 'Front Lawn', False,
     'UGM-84_Harpoon_at_Submarine_Force_Museum_entrance.jpg',
     'Developed in the 1970s as an anti-ship missile, the Harpoon was adapted in the early 1980s to be fired from '
     'submarines’ torpedo tubes in a capsule that pops it out of the water. By the museum entrance.'),
    ('rings', 'Hull rings: Holland and Ohio', 'Exhibit', None, 'Exhibit', 'Entrance Walk', False, None,
     'Two steel rings over the walk to the door show how big submarines have grown: the small one is as wide as USS '
     'Holland (1900), the Navy’s first submarine; the huge one as wide as an Ohio-class missile submarine.'),
    ('x1', 'X-1 midget submarine', 'Fairchild Engine and Airplane', '1955', 'Submarine', 'Front Lawn', False,
     'X-1_bow_view.jpg',
     'The U.S. Navy’s only midget submarine, built in 1955 for four men to test harbour defences. A hydrogen-peroxide '
     'explosion blew off her bow in 1957; she was rebuilt and used for research until 1973. 15 m long.'),
    ('ha8', 'HA-8, Japanese Type A midget submarine', 'Imperial Japanese Navy', '1940s', 'Submarine', 'Front Lawn',
     False, 'HA-8,_Japanese_midget_submarine,_Submarine_Force_Library_&_Museum,_Groton,_Connecticut.jpg',
     'A two-man Ko-hyoteki midget submarine carrying two torpedoes, of the kind used at Pearl Harbor. HA-8 was found '
     'at Guadalcanal in World War II and brought to the United States. 24 m long.'),
    ('sdv', 'Swimmer Delivery Vehicle Mk IX', 'U.S. Navy', '1980s', 'Submersible', 'Front Lawn', False,
     'SDV_Mk_IX_US_Navy_Submarine_Museum.jpg',
     'A flooded mini-submersible that carried two scuba-equipped Navy SEALs on secret missions; retired in 1995.'),
    ('nr1', 'NR-1 deep submergence vessel (sections)', 'Electric Boat, Groton', '1969', 'Submarine', 'Front Lawn',
     True, 'CNO_dedicates_the_NR-1_exhibit_at_the_Submarine_Force_Library_and_Museum._(18961376238).jpg',
     'The Navy’s only nuclear-powered deep-sea research submarine, in service for 39 years (1969–2008): it had wheels '
     'to drive on the sea floor and helped find the wreck of the space shuttle Challenger. Its exhibit was dedicated '
     'in 2015.'),
    ('deckgun', 'Submarine deck gun', 'U.S. Navy', '1940s', 'Gun', 'Front Lawn', True, None,
     'World War II submarines carried a deck gun to finish off small ships on the surface and save torpedoes.'),
    # inside
    ('verne', 'Model of Jules Verne’s Nautilus', 'Exhibit', None, 'Model', 'Lobby', False, None,
     'Hanging just inside the doors: Captain Nemo’s Nautilus from Twenty Thousand Leagues Under the Seas (1870), the '
     'novel that gave the first nuclear submarine its name.'),
    ('cutaway', 'Cutaway model of a modern submarine', 'Exhibit', None, 'Model', 'Main Hallway', False, None,
     'An interactive model cut open to show the inside of a modern attack submarine, compartment by compartment.'),
    ('models', 'The model wall', 'Exhibit', None, 'Models', 'Main Hallway', False, None,
     'Models of U.S. submarines, all at the same scale, in order: from the little Holland of 1900 to the coming '
     'Columbia class.'),
    ('sturgeon', 'Control center of USS Sturgeon (SSN-637)', 'U.S. Navy', '1967', 'Control room', 'Control Room',
     False, 'USS_Sturgeon_(SSN-637)_Control_Center.JPG',
     'The real control room of a Cold War attack submarine, where you can sit at the controls and try steering.'),
    ('periscopes', 'Working periscopes', 'Exhibit', None, 'Periscopes', 'Attack Center', False, None,
     'Three periscopes rise through the roof: turn them to see the Nautilus at her pier, the Thames River and the '
     'Coast Guard Academy on the far bank.'),
    ('turtle', 'Bushnell’s Turtle (full-size replica)', 'after David Bushnell', '1775 design', 'Submarine',
     'Main Gallery', False, 'Bushnell_Turtle_model_US_Navy_Submarine_Museum.jpg',
     'The first submarine used in war, invented by David Bushnell of Saybrook, Connecticut. In 1776 Sergeant Ezra Lee '
     'cranked it by hand under New York harbour to fix a bomb to HMS Eagle; the screw would not bite and he escaped. '
     'The replica is cut open to show the one-man cockpit.'),
    ('gato', 'USS Gato model (1/6 scale cutaway)', 'Exhibit', None, 'Model', 'Main Gallery', False, None,
     'A model about 15 m (50 ft) long of a World War II fleet submarine, opened up so you can look into every room. '
     'Gato-class boats, many built in Groton, fought the Pacific war.'),
    ('mccann', 'McCann Submarine Rescue Chamber', 'U.S. Navy', '1930s', 'Rescue chamber', 'Main Gallery', False, None,
     'A diving bell lowered to a sunken submarine’s escape hatch. In 1939 one like it brought up the 33 survivors of '
     'USS Squalus off New Hampshire, the first rescue of its kind.'),
    ('polaris', 'Polaris A3 missile', 'Lockheed', '1964', 'Missile', 'Main Gallery', False,
     'Polaris_A3_ballistic_missile_upper_stages.jpg',
     'The submarine-launched ballistic missile of the 1960s: 9.8 m (32.3 ft) long and 137 cm (54 in) wide, fired '
     'from under water. The 41 for Freedom submarines carried 16 each.'),
    ('maiale', 'Italian manned torpedo (SSB “Maiale”)', 'Regia Marina', '1940s', 'Manned torpedo', 'Main Gallery',
     True, 'Maiale_at_US_Navy_Submarine_Museum.jpg',
     'A torpedo ridden by two divers in breathing sets, who steered it into enemy harbours to fix its warhead under a '
     'ship. Italian “pigs” sank two British battleships at Alexandria in 1941; this SSB is the later type.'),
    ('torpedoes', 'Torpedoes', 'U.S. Navy', None, 'Weapons', 'Main Gallery', False, None,
     'A row of submarine torpedoes from World War II to the Cold War, from the troubled Mark 14 to modern '
     'wire-guided weapons.'),
    ('s51-bell', 'Bell of USS S-51', 'U.S. Navy', '1922', 'Ship’s bell', 'Main Gallery', True,
     'Bell_of_the_S-51_(SS-162).jpg',
     'S-51 sank off Block Island in 1925 after a collision with the steamer City of Rome; 33 men were lost and 3 '
     'survived. Raising her led the Navy to new rescue gear.'),
    ('thresher', 'Commissioning bottle of USS Thresher (SSN-593)', 'U.S. Navy', '1961', 'Memorial', 'Main Gallery',
     True, 'Thresher_Commissioning_Bottle.JPG',
     'Thresher was lost with all 129 men on board during deep-diving tests off New England on April 10, 1963. Her loss '
     'led to the SUBSAFE program that has kept U.S. submarines safe since.'),
    ('flag', 'World War II submarine battle flag', 'U.S. Navy', '1940s', 'Flag', 'Main Gallery', True, None,
     'Submarines sewed battle flags with a symbol for every ship they sank: a record of a boat’s war patrols.'),
    ('helmet', 'World War II Navy diving helmet', 'U.S. Navy', '1940s', 'Diving gear', 'Main Gallery', True, None,
     'A heavy brass diving helmet; scan the QR code beside it to see yourself inside one (augmented reality).'),
    ('film', 'Submarine history film', 'Exhibit', None, 'Film', 'Theater', False, None,
     'A film on the U.S. Submarine Force plays on a loop in the theater.'),
    ('today', 'Today’s submarines', 'Exhibit', None, 'Exhibit', 'Today’s Submarine Force', False, None,
     'Displays on modern submarines (the Virginia, Ohio and coming Columbia classes, many built across the river at '
     'Electric Boat), what submarines do today and how the Submarine Force is commanded.'),
]

# The library's treasures (not on view): from Wikipedia's summary of the collection
LIBRARY = [
    ('verne-1870', 'Twenty Thousand Leagues Under the Seas, 1870 copy', 'Jules Verne', '1870'),
    ('holland-notes', 'Notes of John Philip Holland', 'John Philip Holland', None),
]


def year(date):
    mm = re.search(r'1[789]\d\d|20[0-2]\d', date or '')
    return int(mm.group()) if mm else None


def build_works(floors):
    names = {r['id']: (r['name'], f['id']) for f in floors['floors'] for r in f['rooms']}
    works, rows = [], []
    for key, title, maker, date, typ, room, guessed, pic, words in WORKS:
        name, fl = names[room]
        img, credit = picture('sf-' + key, pic)
        a = {'id': 'sf-' + key, 'title': title, 'artist': maker, 'date': date, 'year': year(date), 'type': typ,
             'description': words, 'url': SITE, 'image': img, 'imageCredit': credit, 'gallery': room,
             'galleryName': name, 'floor': fl}
        if guessed:
            a['placeGuessed'] = True
            a['placeNote'] = 'The museum doesn’t say where this is shown: our guess by subject.'
        elif fl != 'N' and room not in ('USS Nautilus', 'Memorial Plaza', 'Front Lawn', 'Entrance Walk'):
            a['placeNote'] = 'Approximate: no floor plan is published, so this room’s place on the map is our reading.'
        works.append({k: v for k, v in a.items() if v not in (None, '')})
    for w in works:
        rows.append({k: v for k, v in {'id': w['id'], 'title': w['title'], 'artist': w['artist'], 'date': w.get('date'),
                                       'year': w.get('year'), 'url': w['url'], 'imageUrl': w.get('image'),
                                       'onView': True, 'gallery': w['gallery'], 'floor': w['floor']}.items() if v})
    for key, title, maker, date in LIBRARY:
        rows.append({k: v for k, v in {'id': 'sf-l-' + key, 'title': title, 'artist': maker, 'date': date,
                                       'year': year(date), 'url': SITE, 'onView': False}.items() if v})
    print(f'{len(works)} on the map ({sum(bool(w.get("image")) for w in works)} with pictures), '
          f'{len(rows)} on the museum page')
    return works, rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works, rows = build_works(floors)
    checked = time.strftime('%Y-%m-%d')
    source = ('Submarine Force Museum: exhibits as described by visitors and Wikipedia; pictures from Wikimedia '
              'Commons; the Nautilus tour compartments')
    (OUT / 'artworks.json').write_text(json.dumps({'source': source, 'checked': checked, 'count': len(works),
                                                   'complete': False, 'artworks': works},
                                                  ensure_ascii=False, separators=(',', ':')))
    guide = {'museum': MUSEUM, 'name': NAME, 'checked': checked, 'source': source, 'onViewKnown': True,
             'note': 'The museum holds about 33,000 artifacts, 20,000 documents and 30,000 photographs, but publishes '
                     'no online catalogue. Listed here: the Nautilus and her compartments on the tour, the submarines '
                     'and memorials outside, and the main exhibits inside. Two treasures of the library (closed to '
                     'the public) are marked not on view.',
             'works': rows}
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False,
                                                                         separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(rows), 'pictures': sum(bool(w.get('imageUrl')) for w in rows),
                              'onView': sum(bool(w.get('onView')) for w in rows), 'galleries': True,
                              'checked': checked, 'source': source}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    sys.exit(main())
