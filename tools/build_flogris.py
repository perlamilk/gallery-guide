#!/usr/bin/env python3
"""Build the Florence Griswold Museum map guide (run: python3 tools/build_flogris.py).

    data/flogris/floors.json      the grounds and the two floors of the Griswold House, seen from above (flat 2D)
    data/flogris/artworks.json    the works, in the room where they are (or most likely are)
    data/flogris/images/          pictures from the museum's website, made smaller for phones
    data/guides/Q5460633.json     the same works, for the museum page

The map. The grounds come from the museum's own numbered campus map (flogris.org/visit/museum-campus,
Numbered-Site-Map-2025.png, 600 x 766 px), traced by hand at 4 units per pixel: the Florence Griswold House (1),
the Krieble Gallery (2) with Café Flo (8), the Artists' Trail (3), the gardens (4), the Rafal Landscape Center (5),
the Chadwick Studio (6) and the Hartman Education Center (7), with the parking lot, the paths and the Lieutenant
River. Inside the Krieble Gallery, the museum says only that it holds the changing exhibitions, the Niblack Gallery
(collection highlights), the shop, restrooms, an introductory film and the café on the veranda; the rooms are placed
from the roof shapes on the campus map and the Matterport tours (the Niblack Gallery is under the saw-tooth roof).
The House floors are drawn from the museum's Matterport tour of the House (dining room with the painted panels on one
side of the center hall, the introduction room on the other, the galleries of "An American Place" upstairs) and are
approximate too. Restrooms: Krieble Gallery, Hartman Education Center and the House (museum FAQ).

The works. The collection database (an EmbARK kiosk at collections.flogris.org) forbids robots on every page but its
home page, so it is not read. The works come from pages the museum publishes for everyone (robots.txt allows them):
  - the Griswold House Painted Panels page: the 38 panels and 8 door panels the artists painted in the dining room,
    each with its wall, plus The Fox Chase; these never move, so they are exact;
  - the ongoing shows: From Art Colony to Connecticut Collection (Niblack Gallery) and An American Place (House,
    second floor), with the works they picture;
  - the 21 Collections Highlights and the Hartford Steam Boiler collection pages (portfolio items, via the
    WordPress API), whose works may be on view or in storage, so each says where it is likely to be;
  - Wikidata (CC0).
"""
import html
import io
import json
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'flogris'
CACHE = ROOT / '.cache' / 'flogris'
MUSEUM = 'Q5460633'
NAME = 'Florence Griswold Museum'
SITE = 'https://flogris.org'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
APPROX = 'Approximate layout'
K = 1.2        # campus: map scale (units per pixel of the museum's campus map)


def get(url, name):
    """Read a page once, politely, and keep it."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / name
    if not f.exists():
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, url], capture_output=True).stdout
        time.sleep(1.5)
        if not out: raise SystemExit(f'could not read {url}')
        f.write_bytes(out)
    return f.read_text(errors='replace')


def text(s):
    s = re.sub(r'(?s)<(script|style)[^>]*>.*?</\1>', '', s or '')
    s = re.sub(r'<br\s*/?>', '\n', s)
    s = html.unescape(re.sub(r'<[^>]+>', ' ', s))
    return '\n'.join(re.sub(r'\s+', ' ', line).strip() for line in s.split('\n') if line.strip()).strip()


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# ---- map ----------------------------------------------------------------------------------------------------------

# Grounds, in pixels of the campus map (north is up: the Lieutenant River at the top, Lyme Street at the bottom).
HOUSE = [[422, 565], [452, 565], [452, 628], [465, 628], [465, 683], [405, 683], [405, 628], [422, 628]]
CAMPUS = [
    ('Exhibition Galleries', 'gallery', 'Krieble Gallery: changing exhibitions',
     [[150, 252], [232, 252], [232, 318], [175, 316], [170, 292], [150, 292]], 'Exhibitions'),
    ('Niblack Gallery', 'gallery', 'Niblack Gallery: From Art Colony to Connecticut Collection (collection highlights)',
     rect(232, 254, 300, 320), 'Niblack Gallery'),
    ('Lobby', 'corridor', 'Krieble Gallery lobby · admissions desk · FloGris Shop · introductory film', rect(300, 262, 355, 322),
     None),
    ('Café Flo', 'space', 'Café Flo, on the veranda over the Lieutenant River (seasonal, May–October)',
     [[318, 190], [370, 184], [397, 205], [382, 232], [355, 240], [355, 262], [318, 262]], None),
    ('Griswold House', 'space', 'Florence Griswold House (1817): the artists’ boardinghouse. Pick its floors above',
     HOUSE, None),
    ('Gardens', 'space', 'Miss Florence’s historic gardens', rect(387, 415, 418, 532), None),
    ('Rafal Landscape Center', 'space', 'Rafal Landscape Center: The Landscape of Lyme, in a 19th-century barn',
     rect(355, 412, 387, 452), None),
    ('Hartman Education Center', 'space', 'Hartman Education Center: hands-on art for all ages (restrooms)',
     rect(360, 477, 387, 530), None),
    ('Chadwick Studio', 'space', 'William Chadwick’s studio (1920–1962), with its furnishings', rect(22, 322, 56, 370), None),
    ('Riverfront', 'space', 'Riverfront meadow and gardens on the Lieutenant River', [[105, 112], [160, 98], [300, 96],
                                                                                        [300, 140], [160, 145], [110, 125]],
     None),
    ('walk', 'corridor', 'Path from the parking lot', [[56, 338], [300, 338], [300, 322], [340, 322], [340, 358], [56, 358]],
     None),
    ('terrace', 'corridor', 'Path to the gardens, the House and the trail', rect(355, 288, 505, 300), None),
    ('Artists’ Trail', 'space', 'Robert F. Schumann Artists’ Trail: an accessible walk past hedgerows and fields',
     [[505, 140], [520, 140], [522, 300], [552, 740], [538, 740], [505, 300]], None),
    ('garden-path', 'corridor', 'Garden path', rect(418, 300, 430, 565), None),
    ('river-path', 'corridor', 'Path down to the river', rect(300, 130, 325, 189), None),
    ('closed-parking', 'closed', None, rect(0, 400, 150, 540), None),
    ('closed-office', 'closed', None, rect(183, 470, 218, 535), None),
]
CAMPUS_DOORS = [('Exhibition Galleries', 'Niblack Gallery', (232, 285)), ('Niblack Gallery', 'Lobby', (300, 290)),
                ('Lobby', 'Café Flo', (336, 262)), ('Lobby', 'walk', (320, 322)), ('Lobby', 'terrace', (355, 294)),
                ('terrace', 'garden-path', (424, 300)), ('garden-path', 'Gardens', (418, 470)),
                ('garden-path', 'Griswold House', (426, 565)), ('Gardens', 'Rafal Landscape Center', (387, 432)),
                ('Gardens', 'Hartman Education Center', (387, 505)), ('walk', 'Chadwick Studio', (56, 348)),
                ('river-path', 'Café Flo', (321, 189)), ('river-path', 'Riverfront', (300, 135)),
                ('terrace', 'Artists’ Trail', (505, 294))]
CAMPUS_AMENITIES = [('entrance', 320, 332), ('info', 330, 300), ('shop', 345, 275), ('restroom', 310, 272),
                    ('water', 310, 312), ('dining', 352, 212), ('restroom', 372, 520), ('entrance', 437, 695)]
CAMPUS_LABELS = [('Lieutenant River', 'area', 300, 45), ('Lyme Street', 'area', 230, 752),
                 ('P · Parking', 'area', 75, 470), ('Artists’ Trail', 'area', 470, 160), ('Griswold House', 'area', 345, 650),
                 ('Café Flo', 'area', 405, 190), ('Rafal Center', 'area', 330, 400), ('Hartman Center', 'area', 330, 540),
                 ('Chadwick Studio', 'area', 40, 310), ('Riverfront', 'area', 200, 160),
                 ('Orchard', 'area', 470, 360), ('Brook', 'area', 60, 600), ('Gardens', 'area', 402, 548),
                 ('Front walk to the House', 'area', 500, 715), (APPROX + ' inside the Krieble Gallery', 'area', 250, 380)]

# The Griswold House, drawn on its own (units ≈ 2.5 cm): main block 600 x 480 with the kitchen wing behind it.
HOUSE_1 = [
    ('Center Hall', 'corridor', 'Center hall and staircase (Miss Florence sold the artists’ sketches here)',
     rect(240, 300, 360, 780), None),
    ('Dining Room', 'gallery', 'Dining Room: the painted panels the artists left on the walls and doors', rect(0, 540, 240, 780),
     'Dining Room'),
    ('Introduction', 'gallery', 'Introduction: A Country Retreat for Artists', rect(360, 540, 600, 780), 'Introduction'),
    ('Parlor', 'gallery', 'Parlor (period room)', rect(0, 300, 240, 540), 'Parlor'),
    ('Miss Florence’s Bedroom', 'gallery', 'Miss Florence’s bedroom', rect(360, 300, 600, 540), 'Miss Florence’s Bedroom'),
    ('Kitchen Wing', 'space', 'Back hall and kitchen wing (restroom)', rect(150, 0, 450, 300), None),
]
HOUSE_1_DOORS = [('Center Hall', 'Dining Room', (240, 660)), ('Center Hall', 'Introduction', (360, 660)),
                 ('Center Hall', 'Parlor', (240, 420)), ('Center Hall', 'Miss Florence’s Bedroom', (360, 420)),
                 ('Center Hall', 'Kitchen Wing', (300, 300))]
HOUSE_1_AMENITIES = [('entrance', 300, 790), ('stairs', 300, 380), ('restroom', 210, 120), ('entrance', 300, -10)]
HOUSE_1_LABELS = [('Front porch · Lyme Street', 'area', 300, 860), ('Ramp entrance (ground floor only)', 'area', 300, -70),
                  (APPROX, 'area', 760, 400)]

HOUSE_2 = [
    ('Stair Hall', 'corridor', 'Upstairs hall', rect(240, 300, 360, 780), None),
    ('Landscape of Lyme', 'gallery', 'An American Place: The Landscape of Lyme', rect(0, 540, 240, 780), 'Landscape of Lyme'),
    ('Tonalist Circle', 'gallery', 'An American Place: Henry Ward Ranger and his Tonalist circle', rect(360, 540, 600, 780),
     'Tonalists'),
    ('Painting Outdoors', 'gallery', 'An American Place: painting outdoors, the oil sketch', rect(0, 300, 240, 540),
     'Painting Outdoors'),
    ('Impressionists', 'gallery', 'An American Place: Childe Hassam and the American Impressionists', rect(360, 300, 600, 540),
     'Impressionists'),
    ('Artist’s Bedroom', 'gallery', 'Artist’s bedroom, as in the boardinghouse days', rect(150, 0, 450, 300),
     'Artist’s Bedroom'),
]
HOUSE_2_DOORS = [('Stair Hall', 'Landscape of Lyme', (240, 660)), ('Stair Hall', 'Tonalist Circle', (360, 660)),
                 ('Stair Hall', 'Painting Outdoors', (240, 420)), ('Stair Hall', 'Impressionists', (360, 420)),
                 ('Stair Hall', 'Artist’s Bedroom', (300, 300))]
HOUSE_2_AMENITIES = [('stairs', 300, 380)]
HOUSE_2_LABELS = [('17 stairs up: no wheelchair access to this floor', 'area', 300, 850), (APPROX, 'area', 760, 400)]

FLOORS = [
    ('G', 'Grounds & Krieble Gallery', 'Krieble Gallery (exhibitions, Niblack Gallery, shop, restrooms, Café Flo) · '
     'gardens · Rafal Landscape Center · Chadwick Studio · Hartman Education Center · Artists’ Trail', 0, K,
     CAMPUS, CAMPUS_DOORS, CAMPUS_AMENITIES, CAMPUS_LABELS),
    ('1', 'Griswold House · Floor 1', 'Center hall · Dining Room with the painted panels · Introduction · period rooms',
     1, 1, HOUSE_1, HOUSE_1_DOORS, HOUSE_1_AMENITIES, HOUSE_1_LABELS),
    ('2', 'Griswold House · Floor 2', 'An American Place: The Art Colony at Old Lyme · Artist’s bedroom', 2, 1,
     HOUSE_2, HOUSE_2_DOORS, HOUSE_2_AMENITIES, HOUSE_2_LABELS),
]


def build_floors():
    floors = []
    for fid, label, area, order, k, rooms_in, doors_in, amen, labels in FLOORS:
        def pt(x, y):
            return [x, y]
        rooms, closed = [], []
        for rid, kind, name, poly, short in rooms_in:
            if kind == 'closed':
                closed.append({'poly': [pt(*q) for q in poly]})
                continue
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': [pt(*q) for q in poly]}
            if kind == 'gallery': r['label'] = short or rid
            rooms.append(r)
        ids = {r['id'] for r in rooms}
        doors = [{'a': a, 'b': b, 'at': pt(x, y), 'width': 24, 'axis': 'o'} for a, b, (x, y) in doors_in]
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order, 'transform': [k, 0, 0],
                       'rooms': rooms, 'closed': closed,
                       'amenities': [{'type': t, 'at': pt(x, y)} for t, x, y in amen],
                       'labels': [{'text': t, 'kind': kk, 'at': pt(x, y)} for t, kk, x, y in labels],
                       'doors': doors})
    return {'about': 'Built by tools/build_flogris.py. The grounds are traced from the museum’s own campus map (2025); the '
                     'rooms inside the Krieble Gallery and the Griswold House are approximate, drawn from the museum’s '
                     'descriptions and virtual tours.',
            'source': 'Florence Griswold Museum campus map (flogris.org/visit/museum-campus), visit and FAQ pages and '
                      'Matterport virtual tours. Rooms drawn by hand, approximate',
            'units': 'grounds: pixels of the campus map (transform 1.2); House floors: about 2.5 cm per unit',
            'defaultFloor': 'G', 'galleryWord': 'Room', 'floors': floors}


# ---- works --------------------------------------------------------------------------------------------------------

def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
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
    return f'data/flogris/images/{key}.jpg'


def accession_from(url):
    """1941_404.jpg -> 1941.404 (the museum names its pictures by accession number)."""
    m = re.match(r'(\d{4})_(\d+)(?:_(\d+))?(?:[_-]|\.)', url.rsplit('/', 1)[1])
    if not m: return None
    return '.'.join(x for x in m.groups() if x)


# Door panels whose picture names the room the door belongs to
DOOR_ROOMS = [('ParlorDoor', 'Parlor', 'Painted on a door of the parlor.'),
              ('FlorenceBedroom', 'Miss Florence’s Bedroom', 'Painted on a door of Miss Florence’s bedroom.'),
              ('ArtistBedroom', 'Artist’s Bedroom', 'Painted on a door of an artist’s bedroom.')]
WALLS = {'WEST WALL': 'west wall', 'NORTH WALL': 'north wall', 'EAST WALL': 'east wall', 'SOUTH WALL': 'south wall',
         'PANEL DOORS': 'a door'}


def panels():
    page = get(f'{SITE}/home-2-2/collections/griswold-house-painted-panels/', 'panels.html')
    page = re.sub(r'(?s)<(script|style|noscript)[^>]*>.*?</\1>', '', page)
    out, wall = [], None
    for m in re.finditer(r'<h1[^>]*>([^<]+)</h1>|<div class="fusion-gallery-image[^"]*">(.*?)</p></div></div>', page, re.S):
        if m[1]:
            wall = WALLS.get(html.unescape(m[1]).strip())
            continue
        if not wall: continue
        g = m[2]
        img = re.search(r'<img[^>]*src="([^"]+)"', g)
        title = re.search(r'caption-title">([^<]*)<', g)
        artist = re.search(r'caption-text">([^<]*)', g)
        link = re.search(r'<a href="([^"]+)"', g)
        if not (img and title): continue
        out.append({'title': html.unescape(title[1]).strip(), 'artist': html.unescape(artist[1]).strip() if artist else '',
                    'image': img[1], 'wall': wall, 'url': link[1] if link and 'flogris.org' in link[1] else None})
    return out


def portfolio():
    rows = []
    for page in (1, 2):
        rows += json.loads(get(f'{SITE}/wp-json/wp/v2/avada_portfolio?per_page=100&page={page}', f'portfolio-{page}.json'))
    cats = {c['id']: html.unescape(c['name'])
            for c in json.loads(get(f'{SITE}/wp-json/wp/v2/portfolio_category?per_page=100', 'portfolio-cats.json'))}
    for r in rows:
        r['cats'] = [cats.get(c, '') for c in r['portfolio_category']]
    return rows


def dims_split(s):
    """'Oil on canvas, 18 x 28”' -> ('Oil on canvas', '18 x 28 in.')"""
    m = re.match(r'(.*?),\s*(\d[\d\s/.”″"]*(?:x|X|×)\s*\d.*)$', s)
    if not m: return s.strip(' .'), ''
    d = re.sub(r'\s*[”″"]', '', m[2]).replace(')', '').strip(' .')
    return m[1].strip(), d if d.endswith('in') or 'cm' in d else d + ' in'


def parse_item(r):
    """A collection page: picture, title, artist, date, medium, size, credit, accession, text."""
    c = r['content']['rendered']
    img = re.search(r'data-orig-src="([^"]+)"', c) or re.search(r'<img[^>]*src="(https[^"]+)"', c)
    h1 = [text(h) for h in re.findall(r'(?s)<h1[^>]*>(.*?)</h1>', c)]
    h1 = [h for h in h1 if h]
    if len(h1) < 3: return None
    w = {'image': img[1] if img else None, 'url': r['link'], 'title': html.unescape(r['title']['rendered']).strip(),
         'cats': r['cats']}
    if 'Collections Highlights' in r['cats']:
        if len(h1[0].split('\n')) == 1:   # one line: "Artist, Title, date. Medium, size. Credit accession"
            m = re.match(r'(.+?), (.+?), (\d{4})\. (.+?, [\d].+?in\.) (.+?) (\d{4}\.[\d.]+)$', h1[0])
            if not m: return None
            w.update(artist=m[1], title=m[2], date=m[3], credit=m[5], accession=m[6])
            w['medium'], w['dimensions'] = dims_split(m[4])
            life, body = h1[2], h1[3:]
        else:
            lines = h1[0].split('\n')
            m = re.match(r'(.+?),\s*((?:ca\.|c\.)?\s*\d{4}.*)$', lines[0])
            w['title'], w['date'] = (m[1].strip(), m[2].strip()) if m else (lines[0], '')
            w['medium'] = lines[1] if len(lines) > 2 else ''
            last = lines[-1]
            acc = re.search(r'(\d{4}\.[\d.]+[a-z-]*)\s*$', last)
            w['accession'] = acc[1] if acc else None
            w['credit'] = last[:acc.start()].strip() if acc else last
            w['artist'] = h1[1]
            life, body = h1[2], h1[3:]
        w['life'] = life
    else:
        lines = h1[0].split('\n')
        date = lines[0] if re.search(r'\d{4}|^c\.', lines[0]) and not re.search(r'\d\s*x\s*\d', lines[0]) else ''
        rest = lines[1:] if date else lines
        medium, dims = dims_split(rest[0]) if rest else ('', '')
        m = re.match(r'(.+?)\s*\((\d{4})\s*[-–]\s*(\d{4})\)', h1[2])
        w.update(date=date, medium=medium, dimensions=dims, artist=m[1] if m else h1[2],
                 life=f'{m[2]}–{m[3]}' if m else '', inscription=rest[1] if len(rest) > 1 else '')
        body = h1[3:]
        if 'HSBC' in r['cats']:
            w['credit'] = 'Gift of The Hartford Steam Boiler Inspection and Insurance Company'
    w['text'] = '\n\n'.join(body)
    m = (w.get('medium') or '').strip()
    w['medium'] = m[:1].upper() + m[1:]
    w['year'] = year_of(w.get('date'))
    return w


CAPTION = re.compile(r'^(?P<artist>[^(]+?)\s*\((?P<life>[^)]*)\),\s*(?P<title>.+?)\s*,\s*'
                     r'(?:(?P<date>(?:ca\.|c\.)?\s*\d{4}[^.]*)\.\s*)?(?P<medium>[^.]+?(?:\d in)?)\.?\s*'
                     r'(?:Florence Griswold Museum,?\s*(?P<credit>.+?)(?:,\s*(?P<acc>\d{4}\.[\d.\-]*\d))?\.?)?\s*$')


def show_pictures(slug, rows):
    """The works a show's page pictures, with their captions."""
    r = next(x for x in rows if x['slug'] == slug)
    c = re.sub(r'(?s)<(script|style)[^>]*>.*?</\1>', '', r['content']['rendered'])
    c = re.sub(r'<img[^>]*?(?:data-orig-src|src)="(https[^"]+)"[^>]*>', r'\n[IMG \1]\n', c)
    t = text(c)
    out = []
    for m in re.finditer(r'\[IMG (\S+)\]\s*\n([^\[]+)', t):
        cap = ' '.join(m[2].split('\n')).strip()
        cap = re.split(r' This exhibition is made possible| Share it!', cap)[0]
        cap = re.sub(r'\s+\.\s', ' , ', cap, count=1)      # "Late Summer . Oil on canvas." (no date)
        mm = CAPTION.match(cap)
        if not mm: continue
        medium, dims = dims_split(mm['medium'])
        out.append({'image': m[1], 'artist': mm['artist'].strip(), 'life': mm['life'], 'title': mm['title'].strip(),
                    'date': (mm['date'] or '').strip(), 'year': year_of(mm['date']), 'medium': medium,
                    'dimensions': dims, 'credit': (mm['credit'] or '').strip(' ,.'), 'accession': mm['acc'],
                    'url': r['link']})
    return out


def wikidata():
    q = '''SELECT ?w ?title ?creator ?date ?img ?acc ?material WHERE {
      ?w wdt:P195 wd:%s . OPTIONAL { ?w rdfs:label ?title FILTER(lang(?title)="en") }
      OPTIONAL { ?w wdt:P170 ?c . ?c rdfs:label ?creator FILTER(lang(?creator)="en") }
      OPTIONAL { ?w wdt:P571 ?date } OPTIONAL { ?w wdt:P18 ?img } OPTIONAL { ?w wdt:P217 ?acc }
      OPTIONAL { ?w wdt:P186 ?m . ?m rdfs:label ?material FILTER(lang(?material)="en") } }''' % MUSEUM
    f = CACHE / 'wikidata.json'
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = 'https://query.wikidata.org/sparql?format=json&query=' + urllib.parse.quote(q)
        out = subprocess.run(['curl', '-s', '-f', '-m', '120', '-A', UA, url], capture_output=True).stdout
        if not out: raise SystemExit('Wikidata did not answer')
        f.write_bytes(out)
    rows = {}
    for b in json.loads(f.read_text())['results']['bindings']:
        v = {k: x['value'] for k, x in b.items()}
        qid = v['w'].rsplit('/', 1)[1]
        r = rows.setdefault(qid, {'qid': qid, 'title': v.get('title', ''), 'artist': set(), 'medium': set(), 'date': '',
                                  'image': None, 'accession': ''})
        if v.get('creator'): r['artist'].add(v['creator'])
        if v.get('material'): r['medium'].add(v['material'])
        if v.get('date'): r['date'] = v['date'][:4]
        if v.get('img'): r['image'] = v['img']
        if v.get('acc'): r['accession'] = v['acc']
    out = []
    for r in rows.values():
        if not r['title'] or re.fullmatch(r'Q\d+', r['title']): continue
        r['artist'] = ', '.join(sorted(r['artist'])) or 'Unknown artist'
        r['medium'] = ', '.join(sorted(r['medium'])).capitalize()
        out.append(r)
    return out


# Lyme Art Colony painters, by the room of "An American Place" their work belongs to
TONALISTS = r'ranger|dessar|crane|talcott|bogert|howe|poore|carleton wiggins|cohen|turcas|bicknell|griffin|rook|kenyon'
COLONY = TONALISTS + r'|hassam|metcalf|browne|chadwick|foote|dumond|greacen|hoffman|irvine|warner|guy c\.? wiggins|' \
                     r'voorhees|vonnoh|ryder|nisbet|beal|yates|jongers|heming|robinson|white|ball|vezin|kimball|wiegand|' \
                     r'young|smith|newell|adams|fullonton'
# Artists the museum names in From Art Colony to Connecticut Collection (Niblack Gallery)
NIBLACK = r'browne|chadwick|hassam|metcalf|vonnoh|evans|friese|weir|carlsen|durrie|kensett|inness|ranger|sheffield|' \
          r'dion|sherwood|bridges|porter|avery|hale|rembert|dubois|audette|ligon|foote'


def place(w):
    """(room, note) for a collection work the museum doesn't say is on view."""
    a = (w.get('artist') or '').lower()
    y = w.get('year') or 0
    if re.search(NIBLACK, a):
        return 'Niblack Gallery', ('The Niblack Gallery’s collection highlights include this artist’s work; this '
                                   'painting may be on view there or in storage.')
    if re.search(COLONY, a) and (1895 <= y <= 1940 or not y):
        room = 'Tonalist Circle' if re.search(TONALISTS, a) else 'Impressionists'
        return room, ('A Lyme Art Colony work: room guessed from the House’s ongoing show An American Place. It may be '
                      'in another room or in storage.')
    return 'Niblack Gallery', ('Gallery guessed: the museum shows its collection in the Niblack Gallery; this work may '
                               'be in storage.')


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    out, seen = [], set()

    def key_of(title, artist):
        return norm(title) + norm(artist.split(' ')[-1] if artist else '')[:8]

    def add(a, room, note):
        k = key_of(a['title'], a.get('artist', ''))
        pic = (a.get('image') or '').rsplit('/', 1)[-1]
        if k in seen or (a.get('accession') and a['accession'] in seen) or (pic and pic in seen): return
        floor, gname = rooms[room]
        a.update({'gallery': room, 'galleryName': gname, 'floor': floor, 'placeNote': note})
        out.append({k2: v for k2, v in a.items() if v not in (None, '')})
        seen.add(k)
        if pic: seen.add(pic)
        if a.get('accession'): seen.add(a['accession'])

    rows = portfolio()

    # 1. The painted panels: in the dining room for good
    for p in panels():
        acc = accession_from(p['image'])
        key = 'flogris-panel-' + (acc.replace('.', '-') if acc else norm(p['title'])[:24])
        room, where = 'Dining Room', f'In the dining room, on the {p["wall"]}.'
        for hint, r, w in DOOR_ROOMS:
            if hint in p['image']: room, where = r, w
        add({'id': key, 'title': p['title'], 'artist': p['artist'],
             'medium': 'Oil on wood panel', 'type': 'Painted panel', 'accession': acc,
             'creditLine': 'Florence Griswold Museum',
             'description': f'One of the painted panels the artists of the Lyme Art Colony left in Miss Florence’s '
                            f'boardinghouse: from about 1905 they set double rows of them into all four walls of the '
                            f'dining room and painted the door panels too. "These are the paintings the artists '
                            f'selected to leave behind as their artistic legacy."',
             'onView': True, 'url': p['url'] or f'{SITE}/home-2-2/collections/griswold-house-painted-panels/',
             'image': picture(key, p['image']), 'imageCredit': 'Florence Griswold Museum'},
            room, where)
    fox = f'{SITE}/wp-content/uploads/2025/11/FoxChaseDiningRoom2025-scaled-e1762375435209.jpg'
    add({'id': 'flogris-fox-chase', 'title': 'The Fox Chase', 'artist': 'Henry Rankin Poore', 'date': '1901–1905; revised c. 1920',
         'year': 1905, 'medium': 'Oil on wood panel', 'creditLine': 'Florence Griswold Museum, Gift of the Artist',
         'description': 'The nearly 9-foot frieze over the dining room’s west wall shows the members of the Lyme Art Colony '
                        'in a mock fox hunt through Old Lyme, from the boardinghouse at the far right to the fox at the far '
                        'left. Look for Childe Hassam at his easel, shirt off, painting outdoors while the dogs rush past.',
         'onView': True, 'url': f'{SITE}/home-2-2/collections/griswold-house-painted-panels/',
         'image': picture('flogris-fox-chase', fox), 'imageCredit': 'Florence Griswold Museum'},
        'Dining Room', 'In the dining room, high on the west wall.')

    # 2. The ongoing shows, with the works their pages picture
    shows = [('from-art-colony-to-connecticut-collection-highlights-from-the-florence-griswold-museum', 'Niblack Gallery',
              'From Art Colony to Connecticut Collection (ongoing)'),
             ('an-american-place-the-art-colony-at-old-lyme', None, 'An American Place: The Art Colony at Old Lyme (ongoing)')]
    for slug, room, show in shows:
        for w in show_pictures(slug, rows):
            r = room or ('Landscape of Lyme' if 'Late Summer' in w['title'] else 'Impressionists')
            key = 'flogris-' + (w['accession'].replace('.', '-') if w['accession'] else norm(w['title'])[:24])
            note = ('Pictured on the museum’s page for this show.' if room else
                    'Pictured on the museum’s page for this show on the House’s second floor; the room is a guess.')
            add({'id': key, 'title': w['title'], 'artist': w['artist'], 'date': w['date'], 'year': w['year'],
                 'medium': w['medium'], 'dimensions': w['dimensions'], 'accession': w['accession'],
                 'creditLine': 'Florence Griswold Museum' + (', ' + w['credit'] if w['credit'] else ''),
                 'exhibition': show, 'onView': True, 'url': w['url'], 'image': picture(key, w['image']),
                 'imageCredit': 'Florence Griswold Museum'}, r, note)
    # The Bicentennial Quilt is on view in the Collections Highlights gallery (the Patchwork show page says so)
    add({'id': 'flogris-1989-4', 'title': 'Bicentennial Quilt',
         'artist': 'Sylvia Harding, Mary Connors, Josephine Brown, Ann Traver, Johanna Kooij, Winifred Laubach, Mary Gordon, '
                   'Ruby McClernon, Margaret Smith, Dorothy Smith and Joy Malloy',
         'date': '1976', 'year': 1976, 'medium': 'Cotton and dacron', 'dimensions': '86 x 60 in.', 'accession': '1989.4',
         'creditLine': 'Florence Griswold Museum, Gift of the makers', 'onView': True,
         'description': 'Made by eleven local women for the nation’s 200th birthday. It inspired the 2026 show Patchwork: '
                        'Connecticut Artists Consider 250 — “history is patched together, preserved, and reinterpreted '
                        'by each generation.”',
         'url': f'{SITE}/portfolio-items/patchwork/',
         'image': picture('flogris-1989-4', f'{SITE}/wp-content/uploads/2026/03/PatchworkQuilt.jpg'),
         'imageCredit': 'Florence Griswold Museum'},
        'Niblack Gallery', 'On view in the Collections Highlights gallery, says the museum.')

    # 3. Collection pages: highlights first (they carry accession numbers), then the themed HSBC pages
    items = [parse_item(r) for r in rows if set(r['cats']) & {'Collections Highlights', 'HSBC', 'Connecticut Landscape',
             'Still Life & Genre', 'Connecticut & American Impressionism', 'Cos Cob Art Colony', 'Mystic Silvermine & Beyond',
             'Portraiture in Early Connecticut'}]
    items = [w for w in items if w]
    items.sort(key=lambda w: 'Collections Highlights' not in w['cats'])
    for w in items:
        key = 'flogris-' + (w['accession'].replace('.', '-') if w.get('accession') else norm(w['title'])[:24])
        room, note = place(w)
        theme = next((c for c in w['cats'] if c not in ('Collections Highlights', 'HSBC')), None)
        add({'id': key, 'title': w['title'], 'artist': w['artist'], 'date': w.get('date'), 'year': w['year'],
             'medium': w.get('medium'), 'dimensions': w.get('dimensions'), 'accession': w.get('accession'),
             'creditLine': w.get('credit'), 'inscription': w.get('inscription'), 'type': theme,
             'description': w['text'][:1500] or None, 'url': w['url'], 'image': picture(key, w['image']),
             'imageCredit': 'Florence Griswold Museum'}, room, note)

    # 4. Wikidata
    for w in wikidata():
        img = None
        if w['image']:
            img = 'https://commons.wikimedia.org/wiki/Special:FilePath/' + \
                  urllib.parse.quote(urllib.parse.unquote(w['image'].rsplit('/', 1)[1])) + '?width=800'
        a = {'id': 'flogris-' + w['qid'], 'title': w['title'], 'artist': w['artist'], 'date': w['date'],
             'year': year_of(w['date']), 'medium': w['medium'], 'accession': w['accession'],
             'url': f'https://www.wikidata.org/wiki/{w["qid"]}', 'wikidata': w['qid'],
             'image': picture('flogris-' + w['qid'], img), 'imageCredit': 'Wikimedia Commons' if img else None}
        room, note = place(a)
        add(a, room, note)

    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    out.sort(key=lambda a: (forder[a['floor']], order[a['gallery']], a.get('year') or 0))
    return {'source': 'Florence Griswold Museum website (painted panels, current shows, collection highlights) and '
                      'Wikidata (CC0)', 'checked': time.strftime('%Y-%m-%d'), 'count': len(out), 'complete': False,
            'artworks': out}


def build_guide(works):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'),
                     'year': a.get('year'), 'medium': a.get('medium'), 'accession': a.get('accession'),
                     'url': a['url'], 'imageUrl': a.get('image'), 'onView': bool(a.get('onView')),
                     'gallery': a['gallery'], 'floor': a['floor']}.items() if v not in (None, '')})
    rows.sort(key=lambda w: (not w['onView'], norm(w.get('artist', '')), w.get('year') or 0))
    return {'museum': MUSEUM, 'name': NAME, 'checked': time.strftime('%Y-%m-%d'),
            'source': 'Florence Griswold Museum website and Wikidata', 'onViewKnown': False,
            'note': 'The painted panels in the Griswold House dining room are always there. The other works are the ones '
                    'the museum features on its website; those in the current shows are on view, the rest may be in '
                    'storage.',
            'works': rows}


def main():
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works = build_works(floors)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': sum(w['onView'] for w in guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{works["count"]} works on the map, {sum("image" in a for a in works["artworks"])} with pictures')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
