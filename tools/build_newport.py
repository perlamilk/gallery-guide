#!/usr/bin/env python3
"""Build the Newport Art Museum (Newport, RI) map guide (run: python3 tools/harvest_newport.py, then this).

    data/newport/floors.json       the campus and the ground floors of both gallery buildings, seen from above (flat 2D)
    data/newport/artworks.json     the works in this season's shows, each in its gallery
    data/newport/images/           their pictures, made smaller for phones
    data/guides/Q7018775.json      the same works plus the collection highlights, for the museum page

Where the information comes from
--------------------------------
The museum publishes no floor plan or visitor map, so the map is put together from these:

  - Campus: OpenStreetMap (www.openstreetmap.org/api/0.6/map, cached in .cache/newport/osm.xml): the Griswold House
    (way 1417548843), the Cushing building (1417548836), the museum parking lot between them (896252710) and its drive
    from Downing Street (813467182), the walks from Bellevue Avenue and the lot to the round lawn between the buildings
    (813467480-3). Metres east/north of 41.4855 N, 71.3082 W, turned 6.5 degrees so Bellevue Avenue runs straight up
    the page (the buildings sit square to it). The museum's "Getting here" page: free parking off Downing Street and
    off Old Beach Road; the south lot off Downing Street is the step-free way into all three buildings; the Coleman
    Center (Museum School) is on Liberty Street.
  - Griswold House, ground floor: traced from the Historic American Buildings Survey's measured first-floor plan
    (HABS RI-322, sheet 2 of 4, 1969-70; Library of Congress, public domain; the copy on Wikimedia Commons), drawn
    with north at the bottom. Units are pixels of a 1400-pixel-wide copy; the plan is fitted over the house's outline
    in OpenStreetMap. Which room is which gallery: the Drury Gallery was the Griswolds' dining room, the Library and
    Parlor galleries keep their names, and the Ilgenfritz, Griswold Corridor and Wright galleries are in the house
    (exhibition listings). That the Ilgenfritz Gallery is the big 1920 gallery wing, the Wright Gallery the old
    stable at its end, the Blue Room the conservatory, and the Studio and Damon galleries the two rooms along the
    corridor are our guesses, and the map says so. The upper floor isn't drawn.
  - Cushing building: the 1919 Cushing Memorial Gallery (Delano & Aldrich) with the Sarah Rives lobby and the Morris
    Gallery added in 1990 (museum history page). Its outline is OpenStreetMap's; the rooms inside it are our guess.
    Admissions, the Museum Shop and the restrooms are placed in the lobby by guess too.

The works: tools/harvest_newport.py reads the museum's own pages (robots.txt crawl delay respected). The five
exhibitions now on view, with the captioned works on their pages, and the Cushing paintings from the museum's own
collection; Rediscoveries is in the Cushing Gallery and Unfurling in the Griswold House (their pages say so); the
other shows' galleries are our guesses and each work says so. The 60 collection highlights from the collection pages
go on the museum page as "in the collection", not on the map, because nothing says which are on view.
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
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'newport'
CACHE = ROOT / '.cache' / 'newport'
MUSEUM = 'Q7018775'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
GUESS = '(our guess)'

# ---- the map: metres, turned so Bellevue Avenue runs up the page ------------------------------------------------------

LAT0, LON0 = 41.4855, -71.3082
TURN = math.radians(-6.5)
K = 8                                   # map units per metre


def M(x, y):
    """Metres east/north (turned) -> map units."""
    return [round((x + 50) * K, 1), round((75 - y) * K, 1)]


def H(px, py):
    """A point on the HABS first-floor plan (1400-px copy, north at the bottom) -> metres.

    The plan's west end (the verandah, x=1180) and its east end (the old stable, x=247) fit OpenStreetMap's outline of
    the house at x = -8.4 m and 44.5 m (17.8 px a metre, the plan's own scale bar gives 17.7); its south and north
    ends (the conservatory, y=303; the north porch, y=715) fit y = 13.4 m and 34.7 m."""
    return (-8.4 + (1180 - px) / 17.8, 13.4 + (py - 303) / 19.3)


def osm():
    f = CACHE / 'osm.xml'
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = 'https://www.openstreetmap.org/api/0.6/map?bbox=-71.3105,41.4840,-71.3060,41.4870'
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
            x, y = (lon - LON0) * 111320 * math.cos(math.radians(LAT0)), (lat - LAT0) * 110540
            pts.append((x * math.cos(TURN) - y * math.sin(TURN), x * math.sin(TURN) + y * math.cos(TURN)))
        ways[w.get('id')] = pts
    return ways


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def band(pts, half=1.2):
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        nx, ny = -dy / n * half, dx / n * half
        left.append((x + nx, y + ny)); right.append((x - nx, y - ny))
    return left + right[::-1]


# Griswold House rooms on the HABS plan: (id, kind, name, polygon in plan pixels, short label, guessed)
GRISWOLD = [
    ('Wright Gallery', 'gallery', f'Wright Gallery {GUESS}: the old stable, moved here and joined to the house in 1920',
     rect(249, 480, 340, 687), 'Wright', True),
    ('Ilgenfritz Gallery', 'gallery', f'Ilgenfritz Gallery {GUESS}: the long 1920 gallery wing, the largest room',
     rect(340, 480, 652, 688), 'Ilgenfritz', True),
    ('Griswold Corridor', 'gallery', 'Griswold Corridor: the gallery hall through the house', rect(652, 510, 975, 553),
     'Corridor', False),
    ('Studio Gallery', 'gallery', f'Studio Gallery {GUESS}', rect(680, 553, 770, 650), 'Studio', True),
    ('Damon Gallery', 'gallery', f'Damon Gallery {GUESS}', rect(770, 553, 872, 650), 'Damon', True),
    ('Drury Gallery', 'gallery', 'Drury Gallery: the Griswolds’ dining room', rect(750, 398, 880, 510), 'Drury', False),
    ('Blue Room', 'gallery', f'Blue Room {GUESS}: the conservatory, with the garden door',
     [(882, 398), (893, 373), (893, 305), (945, 305), (945, 373), (965, 373), (975, 398), (975, 510), (882, 510)],
     'Blue Room', True),
    ('Library Gallery', 'gallery', 'Library Gallery: the Griswolds’ library, carved woodwork by Richard Morris Hunt',
     [(975, 405), (1085, 405), (1105, 430), (1105, 478), (1085, 505), (975, 505)], 'Library', False),
    ('Parlor Gallery', 'gallery', 'Parlor Gallery: the Griswolds’ parlor',
     [(975, 520), (1075, 520), (1090, 545), (1090, 625), (1075, 650), (975, 650)], 'Parlor', False),
    ('Stair Hall', 'corridor', 'Stair Hall: the front hall and main stair', rect(872, 553, 975, 655), None, False),
    ('North Porch', 'space', 'North Porch: the house’s front door, toward Old Beach Road', rect(868, 655, 975, 715),
     None, False),
    ('Verandah', 'space', 'Verandah along the west front, facing Bellevue Avenue',
     [(975, 335), (1180, 335), (1180, 700), (1090, 700), (1090, 545), (1105, 478), (1105, 405), (975, 405)],
     None, False),
]
GRISWOLD_CLOSED = [[(652, 368), (770, 368), (770, 398), (750, 398), (750, 510), (652, 510)],    # office and pantry
                   rect(770, 318, 873, 398)]                                                     # enclosed porch
GRISWOLD_DOORS = [('Wright Gallery', 'Ilgenfritz Gallery', (340, 600)),
                  ('Ilgenfritz Gallery', 'Griswold Corridor', (652, 530)),
                  ('Griswold Corridor', 'Drury Gallery', (810, 510)), ('Drury Gallery', 'Blue Room', (882, 455)),
                  ('Griswold Corridor', 'Blue Room', (928, 510)), ('Blue Room', 'Library Gallery', (975, 455)),
                  ('Griswold Corridor', 'Studio Gallery', (725, 553)), ('Griswold Corridor', 'Damon Gallery', (820, 553)),
                  ('Griswold Corridor', 'Stair Hall', (928, 553)), ('Stair Hall', 'Parlor Gallery', (975, 600)),
                  ('Stair Hall', 'North Porch', (920, 655)), ('Library Gallery', 'Verandah', (1105, 455)),
                  ('Parlor Gallery', 'Verandah', (1090, 590))]


def build_floors(ways):
    g = lambda pts: [H(*p) for p in pts]
    rooms = []                      # (id, kind, name, polygon in metres, short label)
    guessed_rooms = set()
    for rid, kind, name, poly, short, guessed in GRISWOLD:
        rooms.append((rid, kind, name, g(poly), short))
        if guessed: guessed_rooms.add(rid)
    # Cushing building: OpenStreetMap's outline (way 1417548836), rooms inside by guess.
    cushing = ways['1417548836'][:-1]
    rooms += [
        ('Cushing Memorial Gallery', 'gallery', 'Cushing Memorial Gallery (1919, Delano & Aldrich): Howard Gardiner '
         'Cushing’s paintings', [(-12.1, -25.0), (3.0, -24.8), (3.0, -12.6), (-12.2, -12.8), (-12.1, -16.7),
                                  (-13.2, -16.9), (-14.0, -17.5), (-14.3, -18.8), (-13.9, -20.1), (-13.2, -20.8),
                                  (-12.0, -20.9)], 'Cushing'),
        ('Rives Lobby', 'space', f'Sarah Rives Lobby {GUESS}: the visitor entrance, admissions, Museum Shop and '
         'restrooms', [(3.0, -18.0), (13.0, -18.0), (13.0, -12.45), (9.5, -12.5), (9.4, -11.1), (8.1, -10.1),
                       (4.8, -10.1), (3.6, -11.2), (3.6, -12.6), (3.0, -12.6)], None),
        ('Morris Gallery', 'gallery', f'Morris Gallery {GUESS} (1990)',
         [(13.0, -12.45), (21.0, -12.4), (21.1, -18.2), (26.2, -18.1), (26.3, -24.5), (3.0, -24.8), (3.0, -18.0),
          (13.0, -18.0)], 'Morris'),
    ]
    guessed_rooms |= {'Morris Gallery'}
    # Grounds
    rooms += [
        ('Front Lawn', 'corridor', 'Front lawn and the walk in from Bellevue Avenue',
         [(-46.5, -26.0), (-14.6, -26.0), (-14.6, -11.2), (-8.6, -11.2), (-8.6, 35.6), (-46.5, 35.6)], None),
        ('Center Lawn', 'corridor', 'The round lawn between the Griswold House and the Cushing building',
         rect(-8.6, -11.2, 30.9, 13.3), None),
        ('North Lawn', 'corridor', 'North lawn along Old Beach Road',
         [(-46.5, 35.6), (44.5, 35.6), (44.5, 66.5), (12.4, 56.4), (-38.4, 40.4), (-46.5, 39.2)], None),
        ('Parking', 'space', 'Museum parking lot (free): its drive comes in from Downing Street',
         ways['896252710'][:-1], None),
        ('Drive', 'corridor', 'Drive from Downing Street to the parking lot', band(ways['813467182'][:2], 2.5), None),
    ]
    closed = []
    for p in GRISWOLD_CLOSED: closed.append(g(p))
    doors = [(a, b, H(*p)) for a, b, p in GRISWOLD_DOORS] + [
        ('Cushing Memorial Gallery', 'Rives Lobby', (3.0, -15.3)), ('Rives Lobby', 'Morris Gallery', (13.0, -15.3)),
        ('Rives Lobby', 'Morris Gallery', (8.0, -18.0)), ('Rives Lobby', 'Center Lawn', (6.5, -10.6)),
        ('Front Lawn', 'Center Lawn', (-8.6, 0.0)), ('Front Lawn', 'North Lawn', (-30.0, 35.6)),
        ('Center Lawn', 'Parking', (30.9, -10.0)), ('Parking', 'Drive', (40.2, -18.0)),
        ('Center Lawn', 'Blue Room', H(919, 305)), ('North Lawn', 'North Porch', H(920, 715)),
        ('North Lawn', 'Wright Gallery', H(300, 687)), ('Front Lawn', 'Verandah', H(1180, 520)),
    ]
    entrance_lobby = (6.5, -9.5)
    amen = [('entrance', *entrance_lobby), ('info', 8.0, -14.0), ('shop', 11.0, -16.2), ('restroom', 5.0, -16.2),
            ('entrance', -45.5, -19.3), ('entrance', 40.2, -30.0), ('entrance', *H(920, 740)),
            ('stairs', *H(905, 600))]
    labels = [('BELLEVUE AVENUE', 'area', -52, 0), ('OLD BEACH ROAD', 'area', 0, 60),
              ('LIBERTY STREET', 'area', 56, 10), ('DOWNING STREET', 'area', 10, -42),
              ('Griswold House (1864, Richard Morris Hunt)', 'area', 18, 40),
              ('Cushing building', 'area', 8, -29),
              ('P · Free parking: the south lot is the step-free way into every building', 'area', 40, 22),
              ('Museum School (Coleman Center), 26 Liberty Street', 'area', 64, 46),
              ('No café in the museum', 'area', -30, -32),
              ('Rooms marked “our guess” and the lobby’s desk, shop and restrooms are approximate', 'area', -26, 70),
              ('Upper floor of the Griswold House not drawn', 'area', 26, 66)]
    floor_rooms = []
    for rid, kind, name, poly, short in rooms:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': [M(*q) for q in poly]}
        if kind == 'gallery': r['label'] = short or rid
        floor_rooms.append(r)
    ids = {r['id'] for r in floor_rooms}
    door_list = [{'a': a, 'b': b, 'at': M(*p), 'width': 14, 'axis': 'o'} for a, b, p in doors]
    for d in door_list:
        assert d['a'] in ids and d['b'] in ids, d
    floor = {'id': '1', 'label': 'Ground floor', 'order': 1, 'transform': [1, 0, 0],
             'area': 'Griswold House (Ilgenfritz, Drury, Library and Parlor galleries) · Cushing Memorial and Morris '
                     'galleries · lobby, shop and restrooms · parking',
             'rooms': floor_rooms, 'closed': [{'poly': [M(*q) for q in c]} for c in closed],
             'amenities': [{'type': t, 'at': M(x, y)} for t, x, y in amen],
             'labels': [{'text': t, 'kind': k, 'at': M(x, y)} for t, k, x, y in labels],
             'doors': door_list, 'homeView': ['Griswold House', 'Cushing Memorial Gallery', 'Ilgenfritz Gallery']}
    floor['homeView'] = [r for r in floor['homeView'] if r in ids]
    return ({'about': 'Built by tools/build_newport.py. The campus outlines come from OpenStreetMap; the Griswold '
                      'House rooms are traced from the Historic American Buildings Survey’s measured plan (1969-70). '
                      'The museum publishes no floor plan: rooms marked “our guess”, the Cushing building’s rooms and '
                      'the lobby’s desk, shop and restrooms are approximate.',
             'source': 'OpenStreetMap (campus), HABS RI-322 first-floor plan (Griswold House), the museum’s history, '
                       '“Getting here” and event-rental pages and exhibition listings (gallery names)',
             'units': f'metres x {K}, Bellevue Avenue up the page (north is 6.5 degrees to the left)',
             'approximate': True, 'defaultFloor': '1', 'galleryWord': 'Gallery', 'floors': [floor]},
            guessed_rooms)


# ---- works ---------------------------------------------------------------------------------------------------------

# show slug -> (gallery, how we know, guessed)
SHOW_PLACE = {
    'howard-gardiner-cushing-rediscoveries': ('Cushing Memorial Gallery', 'The exhibition page names the Cushing '
                                              'Gallery.', False),
    'unfurling-small-work-by-the-2027-art-cup-artists': ('Studio Gallery', 'The exhibition page says the Griswold '
                                                         'House; which room is our guess.', True),
    'angel-otero-the-ocean-forgot-your-garden': ('Morris Gallery', 'Which gallery is our guess; eight paintings from '
                                                 'Otero’s Poussin series are in the Griswold House.', True),
    'play-pretend': ('Drury Gallery', 'Which gallery is our guess; the show also spills into the Museum Shop.', True),
    'sheila-isham-between-worlds': ('Ilgenfritz Gallery', 'Which gallery is our guess (over 30 paintings, some nine '
                                    'feet wide, need the largest room).', True),
}
CUSHING_NOTE = ('The museum keeps many of its Cushing paintings on view in the Cushing Memorial Gallery, where '
                'Rediscoveries runs now; that this one is up today is our guess.')


def norm(s):
    s = unicodedata.normalize('NFKD', html.unescape(s or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '', s)


def year_of(date):
    m = re.search(r'(\d{4})', date or '')
    return int(m[1]) if m else None


MEDIUM = re.compile(r'\b(oil|acrylic|ink|pastel|watercolou?r|gouache|graphite|crayon|panel|canvas|paper|print|'
                    r'lithograph|serigraph|screenprint|woodcut|etching|photograph|gelatin|glass|bronze|marble|slate|'
                    r'embroider|collage|silk|mixed media|hair)', re.I)
YEAR = re.compile(r'^(c\.\s?)?\d{4}(s|\s?[–-]\s?\d{2,4}|\s?/\s?\d{4})?$|^undated$')


def split_caption(cap):
    """Split at commas and at '. ' before a capital, but never inside quotation marks."""
    parts, cur, inq = [], '', False
    for i, ch in enumerate(cap):
        if ch in '“”"':
            inq = (ch == '“') or (ch == '"' and not inq)
            cur += ch
        elif not inq and (ch == ',' or (ch == '.' and cap[i + 1:i + 2] == ' ' and re.match(r' [A-Z0-9]', cap[i + 1:i + 3])
                                         and not re.search(r'\b(c|St|Mr|Mrs|Dr|Jr|[A-Z])$', cur))):
            parts.append(cur); cur = ''
        else:
            cur += ch
    parts.append(cur)
    return [p.strip().strip(',').strip() for p in parts if p.strip().strip(',').strip()]


def parse_caption(cap, artist=None):
    """'Artist, Title, 1904, Oil on canvas, 30 x 40 in, Gift of ..., 1999.001.001.' -> fields."""
    cap = re.sub(r'\s+', ' ', cap.replace('\u2060', '')).strip().rstrip('.')
    cap = re.sub(r'\s*Photo by [^.]*\.?', '', cap)
    cap = re.sub(r',([”"])', r'\1,', cap)                     # 'series “Camp I Am,” 2021' -> '“Camp I Am”, 2021'
    cap = re.sub(r'\s+(Collection of|frame[d:])', r', \1', cap)
    cap = re.sub(r'([A-Za-z)])\s+(\d{4}),', r'\1, \2,', cap)            # "On the Veranda (The Blue Porch) 1909, ..."
    parts = split_caption(cap)
    if artist is None:
        artist, parts = parts[0], parts[1:]
    acc = credit = None
    if parts and re.fullmatch(r'\d{4}\.\d{3}\.\d{3}\S*', parts[-1]):
        acc = parts.pop()
    for i, p in enumerate(parts):
        if re.match(r'(Gift|Bequest|Museum Purchase|Purchased|Partial Gift|Collection of|Courtesy|©)', p):
            credit = None if re.match(r'(Courtesy|©)', p) else ', '.join(q for q in parts[i:] if not q.startswith('©'))
            parts = parts[:i]; break
    date_i = next((i for i, p in enumerate(parts) if i and YEAR.match(p)), None)
    med_i = next((i for i, p in enumerate(parts) if i and MEDIUM.search(p) and not YEAR.match(p)), None)
    stop = min(x for x in (date_i, med_i, len(parts)) if x is not None)
    title = ', '.join(parts[:max(stop, 1)])
    date = parts[date_i] if date_i is not None else None
    rest = [p for i, p in enumerate(parts) if i >= max(stop, 1) and i != date_i]
    dims = [p for p in rest if re.search(r'\d\s*(x|\*)\s*\d|\d\s*(in|ft|cm)\b|^frame', p)]
    medium = ', '.join(p for p in rest if p not in dims) or None
    if title.endswith(' undated'): title, date = title[:-8], date or 'undated'
    title = title.replace('"', '”').strip(' .') or 'Untitled'
    title = re.sub(r'“([^”]*)”', r'“\1”', re.sub(r'(^|\s)”', r'\1“', title))
    title = re.sub(r',\s*”', '”', title)
    return {'artist': artist.strip(), 'title': title, 'date': date,
            'medium': medium and (medium[:1].upper() + medium[1:]).rstrip('.'),
            'dimensions': ', '.join(dims).rstrip('.') or None, 'credit': credit, 'accession': acc}


def picture(key, url):
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
        if im.mode in ('RGBA', 'LA', 'P'):
            im = im.convert('RGBA'); bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=im.split()[-1]); im = bg
        im = im.convert('RGB')
        im.thumbnail((1000, 1000))
        im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/newport/images/{key}.jpg'


def slug(s, n=40):
    return norm(s)[:n] or 'x'


def build_works(floors, guessed_rooms):
    data = json.loads((CACHE / 'works.json').read_text())
    names = {r['id']: r['name'] for f in floors['floors'] for r in f['rooms']}
    works, seen = [], set()

    def add(a, room, note, guessed):
        a.update({'gallery': room, 'galleryName': names[room], 'floor': '1', 'placeNote': note})
        if guessed or room in guessed_rooms: a['placeGuessed'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '')})

    for s in data['shows']:
        room, how, guessed = SHOW_PLACE[s['slug']]
        key = 'newport-show-' + slug(s['slug'], 30)
        img = picture(key, s['image'])
        add({'id': key, 'title': s['title'], 'artist': 'Exhibition', 'date': s['dates'], 'type': 'Exhibition',
             'description': ' '.join(s['text'])[:1500] or None, 'url': s['url'], 'image': img,
             'imageCredit': 'Newport Art Museum' if img else None}, room,
            f'On view {s["dates"]}. {how}', guessed)
        for w in s['works']:
            f = parse_caption(w['caption'])
            k = norm(f['artist'] + f['title'])
            if k in seen: continue
            seen.add(k)
            key = 'newport-' + slug(f['artist'], 12) + '-' + slug(f['title'], 28)
            img = picture(key, w['image'])
            add({'id': key, 'title': f['title'], 'artist': f['artist'], 'date': f['date'], 'year': year_of(f['date']),
                 'medium': f['medium'], 'dimensions': f['dimensions'], 'creditLine': f['credit'],
                 'description': f'In “{s["title"]}”, on view {s["dates"]}.', 'url': s['url'], 'image': img,
                 'imageCredit': 'Newport Art Museum' if img else None}, room,
                f'In “{s["title"]}” ({s["dates"]}). {how}', guessed)
    for w in data['cushing']:
        f = parse_caption(w['caption'], artist='Howard Gardiner Cushing')
        k = norm(f['artist'] + f['title'])
        if k in seen: continue
        seen.add(k)
        key = 'newport-cushing-' + slug(f['title'], 30)
        img = picture(key, w['image'])
        add({'id': key, 'title': f['title'], 'artist': 'Howard Gardiner Cushing', 'date': f['date'],
             'year': year_of(f['date']), 'medium': f['medium'], 'dimensions': f['dimensions'],
             'creditLine': 'Collection of Newport Art Museum',
             'url': 'https://newportartmuseum.org/exhibitions/howard-gardiner-cushing-a-harmony-of-line-and-color/',
             'image': img, 'imageCredit': 'Newport Art Museum' if img else None},
            'Cushing Memorial Gallery', CUSHING_NOTE, True)
    collection = []
    for w in data['collection']:
        f = parse_caption(w['caption'])
        k = norm(f['artist'] + f['title'])
        if k in seen: continue
        seen.add(k)
        key = 'newport-coll-' + (f['accession'] or slug(f['artist'] + f['title'], 30)).replace('.', '-')
        img = picture(key, w['image'])
        collection.append({k2: v for k2, v in {
            'id': key, 'title': f['title'], 'artist': f['artist'], 'date': f['date'], 'year': year_of(f['date']),
            'medium': f['medium'], 'creditLine': f['credit'], 'accession': f['accession'],
            'url': f'https://newportartmuseum.org/collection/{w["area"]}/', 'image': img}.items()
            if v not in (None, '')})
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    works.sort(key=lambda a: (order[a['gallery']], a.get('type') != 'Exhibition', a.get('year') or 0))
    return ({'source': 'Newport Art Museum website (exhibitions now on view and collection pages)',
             'checked': data['checked'], 'count': len(works), 'complete': False, 'artworks': works}, collection)


def build_guide(works, collection):
    rows = []
    for a in works['artworks']:
        if a.get('type') == 'Exhibition': continue
        rows.append({k: v for k, v in {
            'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'), 'year': a.get('year'),
            'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'), 'onView': True,
            'gallery': a['gallery'], 'floor': a['floor']}.items() if v not in (None, '')})
    for a in collection:
        rows.append({k: v for k, v in {
            'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'), 'year': a.get('year'),
            'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'), 'onView': False}.items()
            if v not in (None, '')})
    return {'museum': MUSEUM, 'name': 'Newport Art Museum', 'checked': works['checked'],
            'source': 'Newport Art Museum website', 'onViewKnown': True,
            'note': 'The works in the five exhibitions now on view, and the collection highlights the museum shows on '
                    'its website. The collection holds about 3,000 works (three quarters of them on paper), with the '
                    'largest public collection of Howard Gardiner Cushing’s paintings.',
            'works': rows}


def main():
    if not (CACHE / 'works.json').exists():
        raise SystemExit('run tools/harvest_newport.py first')
    OUT.mkdir(exist_ok=True)
    floors, guessed_rooms = build_floors(osm())
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works, collection = build_works(floors, guessed_rooms)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works, collection)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': sum(w['onView'] for w in guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{works["count"]} on the map ({sum("image" in a for a in works["artworks"])} with pictures, '
          f'{sum(bool(a.get("placeGuessed")) for a in works["artworks"])} in a guessed room); '
          f'{len(collection)} collection highlights for the museum page')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
