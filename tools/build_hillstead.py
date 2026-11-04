#!/usr/bin/env python3
"""Build the Hill-Stead Museum (Farmington, CT) map guide (run: python3 tools/harvest_hillstead.py, then this).

    data/hillstead/floors.json       the grounds and both public floors of the house, seen from above (flat 2D)
    data/hillstead/artworks.json     the works in the house, each in its room
    data/hillstead/images/           their pictures, made smaller for phones
    data/guides/Q1618645.json        the same works, for the museum page

Where the information comes from
--------------------------------
hillstead.org answers every script with a Cloudflare 403 (its robots.txt also shuts out AI crawlers), so it is not read.

The map
  - Grounds (floor G): OpenStreetMap (www.openstreetmap.org/api/0.6/map, cached in .cache/hillstead/osm.xml):
    the house and barn outline (way 448994270), the Sunken Garden (530298224), the parking lot (530298249), the
    drive (530336316, 662478610), the path to Riddle's Pond (17185596) and the pond (945848798). Metres east/north of
    41.7219 N, 72.8200 W. The National Historic Landmark nomination (NPS, 1991) says the front of the house faces
    northwest, a long ell joins the barns at the back, the Y-shaped barn of 1917 holds the Makeshift Theater, and the
    Sunken Garden is across the drive to the south. The renovated Carriage Barn is the visitor center: Museum Shop
    (tickets), lockers, restrooms and an exhibition gallery (press coverage, 2022). Where in the barn each is, is our
    guess.
  - House floors 1 and 2: traced from the first- and second-floor plans in Hill-Stead's illustrated museum guide, as
    reproduced on bigoldhouses.blogspot.com (Nov 2013). Drawn as in the book (the servants' wing on the left, the
    verandah on the right); half a pixel of the scan per unit. The 19 rooms on the tour are the main block's.

The works: Hill-Stead's works on Google Arts & Culture (tools/harvest_hillstead.py, 27 works) and Wikidata (CC0,
18 works, 7 not on Google). The house stays as Theodate Pope Riddle left it in 1946 (her will says nothing may be moved,
lent or sold), so every work is in the house. Rooms come from captions and articles: Side of Culture (May 2022:
drawing room, dining room, morning room, Ada Pope's sitting room, a bedroom) and Galerie (2023: the living room, the
parlor bedroom). Where no source names the room, the room is our guess and the work says so.
"""
import html
import io
import json
import math
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'hillstead'
CACHE = ROOT / '.cache' / 'hillstead'
MUSEUM = 'Q1618645'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
APPROX = 'Approximate'

# ---- grounds (floor G) ----------------------------------------------------------------------------------------------

LAT0, LON0 = 41.7219, -72.8200
K = 2.2                     # map units per metre on the grounds


def G(x, y):
    """Metres east/north of the reference point -> map units (north up)."""
    return [round((x + 130) * K, 1), round((225 - y) * K, 1)]


def osm():
    f = CACHE / 'osm.xml'
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = 'https://www.openstreetmap.org/api/0.6/map?bbox=-72.8250,41.7185,-72.8130,41.7255'
        out = subprocess.run(['curl', '-s', '-f', '-m', '90', '-A', UA, url], capture_output=True).stdout
        if not out: raise SystemExit('OpenStreetMap did not answer')
        f.write_bytes(out)
    root = ET.parse(f).getroot()
    nodes = {n.get('id'): (float(n.get('lat')), float(n.get('lon'))) for n in root.iter('node')}
    ways = {}
    for w in root.iter('way'):
        pts = []
        for nd in w.findall('nd'):
            lat, lon = nodes[nd.get('ref')]
            pts.append(((lon - LON0) * 111320 * math.cos(math.radians(LAT0)), (lat - LAT0) * 110540))
        ways[w.get('id')] = pts
    return ways


def band(pts, half=3.0):
    """A path drawn as a band `half` metres either side of its line."""
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        nx, ny = -dy / n * half, dx / n * half
        left.append((x + nx, y + ny)); right.append((x - nx, y - ny))
    return left + right[::-1]


def grounds(ways):
    b = ways['448994270'][:-1]            # house + ell + the Y-shaped barns, one outline in OpenStreetMap
    house = b[:10] + b[31:]                # the main block (northwest end) and the ell
    barn = b[9:32]                          # the barns at the back (southeast end)
    drive = ways['530336316'][13:]         # from the west lawn past the house and the barns to the parking lot
    pond_path = ways['17185596']
    rooms = [
        ('House', 'space', 'Pope-Riddle House (1901): guided tours of 19 rooms. Pick floor 1 or 2 above to see them',
         house),
        ('Carriage Barn', 'space', 'Carriage Barn: visitor center, Museum Shop (tickets), lockers, restrooms, exhibition '
                                   'gallery and the Makeshift Theater (inside layout approximate)', barn),
        ('Sunken Garden', 'space', 'Sunken Garden: Beatrix Farrand’s design (about 1920), with its summerhouse',
         ways['530298224'][:-1]),
        ('Riddle’s Pond', 'space', 'Riddle’s Pond and the Pond Loop trail', ways['945848798'][:-1]),
        ('drive', 'corridor', 'The drive past the house and the barns', band(drive, 3.5)),
        ('pond-path', 'corridor', 'Path north to Riddle’s Pond and the trails', band(pond_path, 2.5)),
    ]
    closed = [ways['530298249'][:-1], ways['530311179'][:-1], ways['944943458'][:-1], ways['530311178'][:-1]]
    doors = [('drive', 'House', (-40, -2)), ('drive', 'Carriage Barn', (-30, -37)), ('drive', 'Sunken Garden', (-75, -9)),
             ('drive', 'pond-path', (43, -10)), ('pond-path', 'Riddle’s Pond', (122, 106)),
             ('House', 'Carriage Barn', (-22, 0.5))]
    amen = [('entrance', 2, -40), ('info', -8, -30), ('shop', -16, -24), ('restroom', -20, -34), ('coat', -12, -16),
            ('entrance', -42, 4)]
    labels = [('P · Parking (free)', 'area', 45, -60), ('Visitor center', 'area', 22, -18),
              ('Pope-Riddle House', 'area', -58, 52), ('Sunken Garden', 'area', -82, -60),
              ('Drive from Mountain Road', 'area', -108, -24), ('Riddle’s Pond', 'area', 98, 225),
              ('Great lawn: once a six-hole golf course', 'area', -40, 120),
              ('Meadows and woodland trails: Pond Loop, Woodland, Swamp Oak, Bittersweet, Cedar Way', 'area', 95, 40),
              ('No café: no food is sold. Picnic only in marked areas', 'area', 20, -95),
              (APPROX + ' inside the Carriage Barn', 'area', 40, -105)]
    return rooms, closed, doors, amen, labels


# ---- the house (floors 1 and 2) ---------------------------------------------------------------------------------------
# Units: half a pixel of the guidebook scans (1600 x 1167 and 1600 x 977). The plans' top is south.

def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


HOUSE_1 = [
    ('Porte-Cochère', 'space', 'Porte-cochère: where the carriages stopped', rect(760, 58, 870, 210), None),
    ('Carriage Porch', 'corridor', 'Carriage Porch: the family’s everyday way in', rect(705, 210, 925, 318), None),
    ('Butler’s Pantry', 'gallery', 'Butler’s Pantry', rect(715, 350, 930, 470), 'Pantry'),
    ('Dining Room', 'gallery', 'Dining Room: family portraits, Degas’s Jockeys over the mantel; the table seats 30',
     rect(925, 265, 1105, 540), 'Dining Room'),
    ('Ell Room', 'gallery', 'Ell Room', rect(1050, 85, 1195, 265), 'Ell Room'),
    ('Solarium', 'gallery', 'Solarium', rect(1195, 85, 1290, 262), 'Solarium'),
    ('Drawing Room', 'gallery', 'Drawing Room: Monet’s Cap d’Antibes and grainstacks, Manet, Degas’s Dancers in Pink',
     [(1105, 262), (1335, 262), (1395, 335), (1395, 385), (1335, 430), (1105, 430)], 'Drawing Room'),
    ('Entry Hall', 'corridor', 'Entry Hall and main stair (front door to the verandah)', rect(1105, 430, 1315, 540),
     None),
    ('Parlor Bedroom', 'gallery', 'Parlor Bedroom: the ground-floor guest room (Degas’s The Tub)',
     [(1045, 540), (1165, 540), (1165, 720), (1090, 720), (1090, 892), (1045, 892)], 'Parlor'),
    ('First Library', 'gallery', 'First Library', rect(1165, 540, 1340, 720), 'First Library'),
    ('Second Library', 'gallery', 'Second Library (once Mr. Pope’s study and a porch)',
     [(1090, 720), (1340, 720), (1390, 780), (1390, 840), (1340, 892), (1090, 892)], 'Second Library'),
    ('Morning Room', 'gallery', 'Morning Room: Mr. Pope’s later study, a few steps down (Monet’s Fishing Boats at Sea)',
     rect(995, 892, 1240, 1045), 'Morning Room'),
    ('North Porch', 'space', 'North Porch', rect(1015, 1045, 1165, 1135), None),
    ('Verandah', 'space', 'Verandah: the two-story porch along the front of the house',
     [(1340, 262), (1555, 262), (1555, 905), (1240, 905), (1340, 892), (1390, 840), (1390, 780), (1340, 720),
      (1340, 540), (1315, 540), (1315, 430), (1335, 430), (1395, 385), (1395, 335)], None),
]
HOUSE_1_CLOSED = [[(160, 160), (345, 160), (345, 250), (705, 250), (705, 505), (300, 505), (300, 410), (85, 410),
                   (85, 255), (160, 255)]]
HOUSE_1_DOORS = [('Porte-Cochère', 'Carriage Porch', (815, 210)), ('Carriage Porch', 'Dining Room', (925, 290)),
                 ('Carriage Porch', 'Butler’s Pantry', (815, 318)), ('Butler’s Pantry', 'Dining Room', (928, 420)),
                 ('Dining Room', 'Entry Hall', (1105, 485)), ('Entry Hall', 'Drawing Room', (1200, 430)),
                 ('Drawing Room', 'Ell Room', (1120, 262)), ('Drawing Room', 'Solarium', (1240, 262)),
                 ('Entry Hall', 'Verandah', (1315, 490)), ('Entry Hall', 'First Library', (1255, 540)),
                 ('Entry Hall', 'Parlor Bedroom', (1100, 540)), ('First Library', 'Second Library', (1255, 720)),
                 ('Second Library', 'Parlor Bedroom', (1090, 800)), ('Second Library', 'Morning Room', (1115, 892)),
                 ('Morning Room', 'North Porch', (1090, 1045))]
HOUSE_1_AMENITIES = [('entrance', 815, 70), ('entrance', 1470, 490), ('stairs', 1150, 500)]
HOUSE_1_LABELS = [('Former servants’ wing: kitchen, pantry, laundry (now offices)', 'area', 400, 330),
                  ('Tours start at the visitor center (Carriage Barn)', 'area', 400, 600),
                  ('Restrooms: in the visitor center', 'area', 400, 660),
                  ('Front door', 'area', 1460, 560)]

HOUSE_2 = [
    ('Upstairs Hall', 'corridor', 'Upstairs Hall and stair',
     [(1030, 300), (1120, 300), (1120, 430), (1365, 430), (1365, 545), (1030, 545)], None),
    ('Theodate’s Bedroom', 'gallery', 'Theodate Pope Riddle’s Bedroom',
     [(1030, 60), (1250, 60), (1250, 240), (1185, 240), (1185, 300), (1030, 300)], 'Theodate’s Room'),
    ('John Riddle’s Bedroom', 'gallery', 'John Wallace Riddle’s Bedroom',
     [(1185, 240), (1365, 240), (1365, 430), (1215, 430), (1215, 300), (1185, 300)], 'John’s Room'),
    ('Green Guest Room', 'gallery', 'Green Guest Room', rect(1030, 545, 1175, 800), 'Green Room'),
    ('Mulberry Suite', 'gallery', 'Mulberry Suite', rect(1175, 545, 1365, 800), 'Mulberry'),
    ('back hall', 'corridor', 'Back hall to the linen closet and Mrs. Pope’s suite', rect(780, 320, 1030, 350), None),
    ('Linen Closet', 'gallery', 'Linen Closet', rect(780, 240, 1030, 320), 'Linen Closet'),
    ('Ada Brooks Pope’s Suite', 'gallery', 'Ada Brooks Pope’s Suite: her sitting room with Japanese prints',
     rect(780, 350, 1030, 475), 'Mrs. Pope’s Suite'),
]
HOUSE_2_CLOSED = [[(115, 150), (285, 150), (285, 265), (515, 265), (515, 235), (780, 235), (780, 480), (455, 480),
                   (455, 490), (290, 490), (290, 430), (115, 430)],
                  rect(1120, 300, 1215, 430), rect(1135, 800, 1310, 940)]
HOUSE_2_DOORS = [('Upstairs Hall', 'Theodate’s Bedroom', (1080, 300)),
                 ('Upstairs Hall', 'John Riddle’s Bedroom', (1290, 430)),
                 ('Theodate’s Bedroom', 'John Riddle’s Bedroom', (1200, 250)),
                 ('Upstairs Hall', 'Green Guest Room', (1100, 545)), ('Upstairs Hall', 'Mulberry Suite', (1270, 545)),
                 ('Upstairs Hall', 'back hall', (1030, 335)), ('back hall', 'Linen Closet', (900, 320)),
                 ('back hall', 'Ada Brooks Pope’s Suite', (900, 350))]
HOUSE_2_AMENITIES = [('stairs', 1190, 490)]
HOUSE_2_LABELS = [('Former servants’ quarters (now offices)', 'area', 420, 330),
                  ('Stairs only: no wheelchair access to this floor', 'area', 700, 620)]

S = 0.5                 # house units per pixel of the scans
# The house floors are moved so their middle sits on the house on the grounds map: switching between the grounds and
# a house floor keeps the house in view.
HOUSE_SHIFT = (-212, 153)


def build_floors(ways):
    g_rooms, g_closed, g_doors, g_amen, g_labels = grounds(ways)
    spec = [
        ('G', 'Grounds & Visitor Center', 'Carriage Barn (visitor center, Museum Shop, restrooms, exhibition gallery) · '
         'Sunken Garden · parking · Riddle’s Pond and trails', 0, G,
         [(a, b, c, d, None) for a, b, c, d in g_rooms], g_closed, g_doors, g_amen, g_labels),
        ('1', 'House · Floor 1', 'Dining Room · Drawing Room · Entry Hall · libraries · Parlor Bedroom · Morning Room',
         1, lambda x, y: [round(x * S, 1), round(y * S, 1)], HOUSE_1, HOUSE_1_CLOSED, HOUSE_1_DOORS,
         HOUSE_1_AMENITIES, HOUSE_1_LABELS),
        ('2', 'House · Floor 2', 'Bedrooms of Theodate and John Riddle · guest rooms · Ada Brooks Pope’s suite', 2,
         lambda x, y: [round(x * S, 1), round(y * S, 1)], HOUSE_2, HOUSE_2_CLOSED, HOUSE_2_DOORS,
         HOUSE_2_AMENITIES, HOUSE_2_LABELS),
    ]
    floors = []
    for fid, label, area, order, pt, rooms_in, closed_in, doors_in, amen, labels in spec:
        rooms = []
        for rid, kind, name, poly, short in rooms_in:
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': [pt(*q) for q in poly]}
            if kind == 'gallery': r['label'] = short or rid
            rooms.append(r)
        ids = {r['id'] for r in rooms}
        doors = [{'a': a, 'b': b, 'at': pt(x, y), 'width': 14, 'axis': 'o'} for a, b, (x, y) in doors_in]
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        shift = [0, 0] if fid == 'G' else list(HOUSE_SHIFT)
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order, 'transform': [1, *shift],
                       'rooms': rooms, 'closed': [{'poly': [pt(*q) for q in c]} for c in closed_in],
                       'amenities': [{'type': t, 'at': pt(x, y)} for t, x, y in amen],
                       'labels': [{'text': t, 'kind': k, 'at': pt(x, y)} for t, k, x, y in labels],
                       'doors': doors, **({'homeView': ['House', 'Carriage Barn', 'Sunken Garden']}
                                          if fid == 'G' else {})})
    return {'about': 'Built by tools/build_hillstead.py. The grounds come from OpenStreetMap; the house rooms are traced '
                     'from the floor plans in Hill-Stead’s illustrated museum guide. Inside the Carriage Barn, places '
                     'are approximate.',
            'source': 'OpenStreetMap (grounds), Hill-Stead’s illustrated museum guide floor plans (house), the 1991 '
                      'National Historic Landmark nomination and press coverage (visitor center)',
            'units': f'grounds: metres x {K}, north up; house: half a pixel of the guidebook plans (south at the top)',
            'defaultFloor': '1', 'galleryWord': 'Room', 'floors': floors}


# ---- works ---------------------------------------------------------------------------------------------------------

SOC = 'Side of Culture, May 2022'
GALERIE = 'Galerie, 2023'
PRINTS = ('Ada Brooks Pope’s Suite', f'Japanese prints hang in Ada Pope’s sitting room ({SOC}); the ones on the walls '
                                     'may be facsimiles that keep the originals out of the light.', False)
# normalized title -> (room, how we know, guessed)
PLACES = {
    'viewofcapdantibes': ('Drawing Room', f'Over the drawing-room mantel ({SOC}).', False),
    'grainstackswhitefrosteffect': ('Drawing Room', f'In the drawing room ({SOC}).', False),
    'grainstacksinbrightsunlight': ('Drawing Room', f'One of the two grainstacks in the living room ({GALERIE}).', False),
    'theguitarplayer': ('Drawing Room', f'In the drawing room, next to Degas’s Dancers in Pink ({SOC}).', False),
    'dancersinpink': ('Drawing Room', f'In the living room, next to Manet’s The Guitar Player ({GALERIE}, {SOC}).',
                      False),
    'toreadors': ('Drawing Room', f'Hangs below The Guitar Player; two Manets are in the living room ({GALERIE}).',
                  False),
    'jockeys': ('Dining Room', f'Over the dining-room mantel ({SOC}).', False),
    'fishingboatsatsea': ('Morning Room', f'Over the morning-room mantel ({SOC}).', False),
    'thetub': ('Parlor Bedroom', f'In the parlor bedroom ({GALERIE}).', False),
    'sarahandingatoytothebaby': ('Theodate’s Bedroom', f'In a bedroom ({SOC}); which bedroom is our guess.', True),
    'symphonyinvioletandblue': ('Ell Room', f'In the room Hill-Stead calls the breakfast room ({SOC}); that this is the '
                                            'Ell Room is our guess.', True),
}
GUESS = {   # no source names the room: our guess, said on the work
    'theabsinthedrinker': 'First Library', 'thebluewavebiarritz': 'First Library', 'selseyshore': 'Second Library',
    'crimsonnotecarmen': 'Second Library', 'gatheringfruit': 'Second Library', 'stilllife': 'Dining Room',
    'lionwithaserpent': 'Entry Hall', 'indopersianrug': 'Entry Hall', 'peace': 'Upstairs Hall',
    'headofawoman': 'Green Guest Room', 'maternity': 'Mulberry Suite',
}
NOT_WORKS = {'diningroom', 'morningroom', 'mrspopesparlor', 'parlorbedroom'}       # photos of rooms, not works
ARCHIVE = {'theodatepoperiddlewithjimjam'}                                          # archive photograph
WIKIDATA_DUPES = {'Q96953521'}                  # “Woman in a Tub”: the same pastel as The Tub (Q84729390)
ARTISTS = {'Hokusai': 'Katsushika Hokusai', 'Hiroshige': 'Utagawa Hiroshige', 'Utamaro': 'Kitagawa Utamaro'}


def norm(s):
    s = unicodedata.normalize('NFKD', html.unescape(s or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '', s)


def year_of(date):
    m = re.search(r'(\d{4})', date or '')
    if m: return int(m[1])
    m = re.search(r'(\d+)(?:st|nd|rd|th)\s+century', (date or '').lower())
    return (int(m[1]) - 1) * 100 + 50 if m else None


def picture(key, url):
    """Download once (politely) and save a phone-sized JPEG; returns the app path."""
    if not url: return None
    raw = CACHE / 'img' / f'{key}.bin'
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, url], capture_output=True).stdout
        time.sleep(1)
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
    return f'data/hillstead/images/{key}.jpg'


def wikidata():
    q = '''SELECT ?w ?title ?creator ?date ?img ?material WHERE {
      ?w wdt:P195 wd:%s . OPTIONAL { ?w rdfs:label ?title FILTER(lang(?title)="en") }
      OPTIONAL { ?w wdt:P170 ?c . ?c rdfs:label ?creator FILTER(lang(?creator)="en") }
      OPTIONAL { ?w wdt:P571 ?date } OPTIONAL { ?w wdt:P18 ?img }
      OPTIONAL { ?w wdt:P186 ?m . ?m rdfs:label ?material FILTER(lang(?material)="en") } }''' % MUSEUM
    f = CACHE / 'wikidata.json'
    if not f.exists():
        url = 'https://query.wikidata.org/sparql?format=json&query=' + urllib.parse.quote(q)
        out = subprocess.run(['curl', '-s', '-f', '-m', '120', '-A', UA, url], capture_output=True).stdout
        if not out: raise SystemExit('Wikidata did not answer')
        f.write_bytes(out)
    rows = {}
    for b in json.loads(f.read_text())['results']['bindings']:
        v = {k: x['value'] for k, x in b.items()}
        qid = v['w'].rsplit('/', 1)[1]
        if qid in WIKIDATA_DUPES: continue
        r = rows.setdefault(qid, {'qid': qid, 'title': v.get('title') or '', 'artist': v.get('creator') or '',
                                  'date': '', 'image': None, 'medium': set()})
        if v.get('date'): r['date'] = v['date'][:4].lstrip('+')
        if v.get('img'): r['image'] = v['img']
        if v.get('material'): r['medium'].add(v['material'])
    for r in rows.values():
        r['medium'] = ', '.join(sorted(r['medium'])).capitalize()
    return list(rows.values())


def build_works(floors):
    names = {r['id']: (r['name'], f['id']) for f in floors['floors'] for r in f['rooms']}
    gac = json.loads((CACHE / 'gac-works.json').read_text())
    wd = {norm(w['title']): w for w in wikidata()}
    works, extra = [], []
    rows = [('gac', w) for w in gac] + [('wd', w) for k, w in wd.items()
                                        if k not in {norm(g['title']) for g in gac}]
    for src, w in rows:
        k = norm(w['title'])
        if k in NOT_WORKS: continue
        wdrow = wd.get(k)
        artist = ARTISTS.get(w.get('artist'), w.get('artist')) or 'Unknown maker'
        key = 'hillstead-' + (k[:40] if src == 'gac' else w['qid'])
        if src == 'gac':
            img = picture(key, w['image'] and w['image'] + '=w1000')
            credit = 'Hill-Stead Museum, via Google Arts & Culture'
            url = w['gac']
        else:
            img = ('https://commons.wikimedia.org/wiki/Special:FilePath/' +
                   urllib.parse.quote(urllib.parse.unquote(w['image'].rsplit('/', 1)[1])) + '?width=800'
                   if w['image'] else None)
            credit = 'Wikimedia Commons'
            url = f'https://www.wikidata.org/wiki/{w["qid"]}'
        a = {'id': key, 'title': w['title'], 'artist': artist, 'date': w.get('date'), 'year': year_of(w.get('date')),
             'medium': w.get('medium') or None, 'type': w.get('type') or None,
             'dimensions': w.get('dimensions') or None, 'description': (w.get('text') or '')[:1500] or None,
             'url': url, 'image': img, 'imageCredit': credit if img else None,
             'wikidata': wdrow['qid'] if wdrow else None}
        if k in ARCHIVE:
            extra.append({x: y for x, y in a.items() if y not in (None, '')})
            continue
        if k in PLACES:
            room, how, guessed = PLACES[k]
        elif re.search(r'Hokusai|Hiroshige|Utamaro', artist):
            room, how, guessed = PRINTS
        else:
            room = GUESS[k]
            how, guessed = 'Every work stays in the house, as Theodate Pope Riddle willed; no source names this one’s ' \
                           'room, so the room is our guess.', True
        name, floor = names[room]
        a.update({'gallery': room, 'galleryName': name, 'floor': floor, 'placeNote': how})
        if guessed: a['placeGuessed'] = True
        works.append({x: y for x, y in a.items() if y not in (None, '')})
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    works.sort(key=lambda a: (a['floor'], order[a['gallery']], a.get('year') or 0))
    return ({'source': 'Hill-Stead Museum on Google Arts & Culture and Wikidata (CC0); rooms from press photo captions',
             'checked': time.strftime('%Y-%m-%d'), 'count': len(works), 'complete': False, 'artworks': works}, extra)


def build_guide(works, extra):
    rows = []
    for a in works['artworks'] + extra:
        rows.append({k: v for k, v in {
            'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'), 'year': a.get('year'),
            'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'), 'onView': 'gallery' in a,
            'gallery': a.get('gallery'), 'floor': a.get('floor')}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': 'Hill-Stead Museum', 'checked': works['checked'],
            'source': 'Hill-Stead Museum on Google Arts & Culture and Wikidata (CC0)', 'onViewKnown': True,
            'note': 'Theodate Pope Riddle willed that the house and everything in it stay as she left it, so the works '
                    'are always on view, each in its room. This list is what Hill-Stead shows on Google Arts & Culture '
                    'plus its works on Wikidata; the house holds many more prints, letters and photographs.',
            'works': rows}


def main():
    if not (CACHE / 'gac-works.json').exists():
        raise SystemExit('run tools/harvest_hillstead.py first')
    OUT.mkdir(exist_ok=True)
    floors = build_floors(osm())
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works, extra = build_works(floors)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works, extra)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': sum(w['onView'] for w in guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{works["count"]} works on the map, {sum("image" in a for a in works["artworks"])} with pictures, '
          f'{sum(bool(a.get("placeGuessed")) for a in works["artworks"])} with a guessed room')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
