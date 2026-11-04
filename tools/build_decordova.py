#!/usr/bin/env python3
"""Build the deCordova Sculpture Park and Museum (Lincoln, MA) map guide (run: python3 tools/build_decordova.py).

    data/decordova/floors.json      the sculpture park seen from above (a flat 2D plan)
    data/decordova/artworks.json    every sculpture on the park map, in the lawn or garden where it stands
    data/decordova/images/          their pictures, made smaller for phones
    data/guides/Q2019741.json       every deCordova work we know of, for the museum page

The museum's indoor galleries are closed for renovation (Nov 2026); the 30-acre sculpture park, the café and the
store are open. So the guide is the park.

The map is traced from deCordova's own park map (thetrustees.org/wp-content/uploads/2026/04/deCordova_ParkMap_Summer26.pdf,
linked from the Property Map on thetrustees.org/place/decordova). Coordinates are pixels of that PDF drawn at
150 dpi, less the map's top-left corner (640, 135). At that size one pixel is about 35 cm on the ground, which is
what the app's walking times assume. The numbered circles on the map are read from the PDF's own text, so each
sculpture's number sits exactly where the museum put it. Lawns and gardens are the museum's names (Pondside, The
Grove, Entrance Lawn, Alice's Garden, Sculpture Terrace, Linda's Lawn, South Lawn); their edges are drawn by eye
along the paths. The museum leaves the strip by Admission and the area around the Store unnamed, so they are
named here after what is in them.

The works: the list of 53 sculptures is the one printed on that map. Each one's picture, size, medium, credit line and
text come from its page on thetrustees.org (linked from thetrustees.org/content/decordovasculpturepark), read once
and slowly. The museum page also lists park works on that page that are not on the current map, and the Permanent
Collection highlights, as part of the collection (not placed).
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
OUT = ROOT / 'data' / 'decordova'
CACHE = ROOT / '.cache' / 'decordova'
MUSEUM = 'Q2019741'
SITE = 'https://thetrustees.org'
MAP_PDF = SITE + '/wp-content/uploads/2026/04/deCordova_ParkMap_Summer26.pdf'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SOURCE = 'deCordova Sculpture Park map, Summer 2026 (thetrustees.org/place/decordova, Property Map)'
OX, OY = 640, 135          # top-left corner of the map on the PDF page at 150 dpi


def get(url, name, binary=False):
    """Read a page once, politely, and keep it in .cache/decordova."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / name
    if not f.exists():
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, url], capture_output=True).stdout
        time.sleep(1.5)
        if not out: raise SystemExit(f'could not read {url}')
        f.write_bytes(out)
    return f.read_bytes() if binary else f.read_text(errors='replace')


def text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def norm(s):
    s = unicodedata.normalize('NFKD', html.unescape(s or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '', s)


def P(x, y):
    """A point on the 150 dpi PDF page -> map units."""
    return [round(x - OX, 1), round(y - OY, 1)]


def poly(*pts):
    return [P(x, y) for x, y in pts]


# ---- the map --------------------------------------------------------------------------------------------------
# (id, kind, name, polygon on the 150 dpi page, label, holes)
ROOMS = [
    ('Pondside', 'gallery', 'Pondside: along Waleska’s Way above Flint’s Pond',
     poly((1110, 330), (1190, 270), (1260, 210), (1380, 180), (1470, 182), (1560, 212), (1615, 280), (1615, 400),
          (1548, 400), (1512, 474), (1482, 474), (1500, 445), (1430, 386), (1402, 393), (1352, 405), (1342, 425),
          (1140, 425), (1140, 400)), 'Pondside', [poly((1468, 322), (1528, 322), (1538, 380), (1468, 382))]),
    ('Pondside Terrace', 'space', 'Pondside Terrace (events lawn)',
     poly((1468, 322), (1528, 322), (1538, 380), (1468, 382)), None, None),
    ('Museum', 'space', 'Museum building: indoor galleries closed for renovation; programs and events go on. '
                        'Accessible restrooms on the 3rd floor (elevator).',
     poly((1352, 405), (1402, 393), (1430, 386), (1500, 445), (1482, 474), (1352, 474)), None, None),
    ('Alice’s Garden', 'gallery', 'Alice’s Garden and the stair garden beside the museum',
     poly((1140, 425), (1342, 425), (1352, 474), (1318, 474), (1318, 530), (1140, 530)), 'Alice’s Garden', None),
    ('Sculpture Terrace', 'gallery', 'Sculpture Terrace, in front of the museum',
     poly((1318, 474), (1500, 474), (1512, 562), (1318, 562)), 'Sculpture Terrace', None),
    ('The Grove', 'gallery', 'The Grove: a wooded loop by Sandy Pond Road',
     poly((790, 500), (800, 450), (860, 438), (930, 462), (952, 520), (905, 560), (820, 548)), 'The Grove', None),
    ('Entrance Lawn', 'gallery', 'Entrance Lawn',
     poly((930, 462), (1000, 385), (1110, 330), (1140, 400), (1140, 600), (1000, 600), (952, 560), (905, 560),
          (952, 520)), 'Entrance Lawn', None),
    ('By Admission', 'gallery', 'By Admission, along the woods on Sandy Pond Road',
     poly((790, 500), (820, 548), (905, 560), (952, 560), (1000, 600), (1000, 700), (900, 720), (800, 720),
          (755, 640)), 'By Admission', None),
    ('Linda’s Lawn', 'gallery', 'Linda’s Lawn',
     poly((1000, 600), (1140, 600), (1140, 530), (1318, 530), (1318, 562), (1340, 562), (1340, 700), (1250, 722),
          (1100, 722), (1000, 700)), 'Linda’s Lawn',
     [poly((1165, 612), (1238, 598), (1258, 668), (1192, 692))]),
    ('Carriage House', 'space', 'Carriage House (events; accessible restroom nearby)',
     poly((1165, 612), (1238, 598), (1258, 668), (1192, 692)), None, None),
    ('South Lawn', 'gallery', 'South Lawn and the woods below it',
     poly((800, 720), (900, 720), (1000, 700), (1100, 722), (1250, 722), (1340, 700), (1352, 700), (1352, 762),
          (1395, 800), (1490, 800), (1500, 1005), (900, 1005), (870, 800)), 'South Lawn', None),
    ('By the Store', 'gallery', 'By the Store and Café, the parking lot and the Trail Head',
     poly((1340, 562), (1512, 562), (1548, 400), (1615, 400), (1645, 400), (1645, 800), (1490, 800), (1462, 730),
          (1395, 712), (1352, 700)), 'By the Store',
     [poly((1388, 632), (1440, 622), (1492, 688), (1446, 722), (1386, 702))]),
    ('Store & Café', 'space', 'deCordova Store and Twisted Tree Café · restrooms',
     poly((1388, 632), (1440, 622), (1492, 688), (1446, 722), (1386, 702)), None, None),
]
# where an area's name goes, so it doesn't sit on the sculpture numbers
LABEL_AT = {'Alice’s Garden': (1268, 460), 'Sculpture Terrace': (1462, 540), 'By Admission': (945, 688),
            'Linda’s Lawn': (1060, 640), 'Pondside': (1560, 300)}
CLOSED = [  # not open to visitors
    poly((1395, 712), (1462, 730), (1490, 800), (1395, 800), (1352, 762), (1352, 700)),   # Lincoln Nursery School
]
DOORS = [
    ('The Grove', 'By Admission', (870, 553)), ('The Grove', 'Entrance Lawn', (941, 492)),
    ('Entrance Lawn', 'By Admission', (976, 580)), ('Entrance Lawn', 'Linda’s Lawn', (1070, 600)),
    ('Entrance Lawn', 'Alice’s Garden', (1140, 470)), ('Entrance Lawn', 'Pondside', (1125, 365)),
    ('Alice’s Garden', 'Pondside', (1230, 425)), ('Alice’s Garden', 'Sculpture Terrace', (1318, 500)),
    ('Alice’s Garden', 'Linda’s Lawn', (1230, 530)), ('Sculpture Terrace', 'Museum', (1420, 474)),
    ('Sculpture Terrace', 'Linda’s Lawn', (1329, 562)), ('Sculpture Terrace', 'By the Store', (1430, 562)),
    ('Pondside', 'Museum', (1395, 395)), ('Pondside', 'Pondside Terrace', (1498, 322)),
    ('Pondside', 'By the Store', (1580, 400)), ('By Admission', 'Linda’s Lawn', (1000, 650)),
    ('By Admission', 'South Lawn', (850, 720)), ('Linda’s Lawn', 'South Lawn', (1170, 722)),
    ('Linda’s Lawn', 'Carriage House', (1178, 650)), ('Linda’s Lawn', 'By the Store', (1340, 630)),
    ('By the Store', 'Store & Café', (1395, 667)), ('South Lawn', 'By the Store', (1470, 790)),
]
AMENITIES = [
    ('info', 990, 612),              # Admission booth
    ('entrance', 1000, 640),         # where the drive from Sandy Pond Road reaches Admission
    ('entrance', 1500, 490),         # museum's accessible entrance
    ('shop', 1420, 645), ('dining', 1455, 690), ('restroom', 1392, 708),
    ('restroom', 1147, 666),         # accessible restroom by the Carriage House
    ('restroom', 1420, 430),         # museum, 3rd floor, by elevator
]
LABELS = [
    ('Flint’s Pond', 'area', 890, 265),
    ('Sandy Pond Road', 'note', 790, 770),
    ('Waleska’s Way', 'area', 1225, 335),
    ('Admission', 'area', 960, 600),
    ('P · Parking', 'area', 1540, 610),
    ('Trail Head: woodland trails', 'note', 1590, 445),
    ('Lincoln Nursery School & Studios (grey; not open to visitors)', 'note', 1575, 830),
    ('Paved access route: Admission – Linda’s Lawn – Store – museum', 'note', 1200, 1025),
]


def map_numbers():
    """Where each numbered circle sits on the museum's map, read from the PDF's own text."""
    pdf = CACHE / 'park-map.pdf'
    get(MAP_PDF, 'park-map.pdf', binary=True)
    out = subprocess.run(['pdftotext', '-bbox', str(pdf), '-'], capture_output=True, text=True).stdout
    spots = {}
    for m in re.finditer(r'xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(\d{1,2})<', out):
        x = (float(m[1]) + float(m[3])) / 2 * 150 / 72
        y = (float(m[2]) + float(m[4])) / 2 * 150 / 72
        if x > OX and OY < y < 1010:         # the map, not the list beside it
            spots.setdefault(int(m[5]), []).append((round(x), round(y)))
    return spots


def inside(pt, pg):
    x, y = pt
    hit = False
    for (x1, y1), (x2, y2) in zip(pg, pg[1:] + pg[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def build_floors():
    rooms = []
    for rid, kind, name, pg, label, holes in ROOMS:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': pg}
        if holes: r['holes'] = holes
        if kind == 'gallery': r['label'] = label
        if rid in LABEL_AT: r['labelAt'] = P(*LABEL_AT[rid])
        rooms.append(r)
    ids = {r['id'] for r in rooms}
    doors = [{'a': a, 'b': b, 'at': P(x, y), 'width': 14, 'axis': 'o'} for a, b, (x, y) in DOORS]
    for d in doors:
        assert d['a'] in ids and d['b'] in ids, d
    numbers = map_numbers()
    labels = [{'text': t, 'kind': k, 'at': P(x, y)} for t, k, x, y in LABELS]
    # the museum's sculpture numbers, where its map prints them ('area' labels float above the lawns)
    labels += [{'text': str(n), 'kind': 'area', 'at': P(x, y)} for n, pts in sorted(numbers.items()) for x, y in pts]
    floor = {'id': 'park', 'label': 'Sculpture Park', 'order': 0,
             'area': 'The 30-acre park: Pondside · The Grove · Entrance Lawn · Alice’s Garden · Sculpture Terrace · '
                     'Linda’s Lawn · South Lawn · Store and Café',
             'transform': [1, 0, 0], 'rooms': rooms, 'closed': [{'poly': c} for c in CLOSED],
             'amenities': [{'type': t, 'at': P(x, y)} for t, x, y in AMENITIES],
             'labels': labels, 'doors': doors}
    return {'about': 'Built by tools/build_decordova.py, traced from deCordova’s own Sculpture Park map (Summer 2026). '
                     'Numbers on the map are the museum’s; sculptures come and go during the year.',
            'source': SOURCE, 'units': 'pixels of the park map at 150 dpi (about 35 cm each)', 'defaultFloor': 'park',
            'galleryWord': 'Area', 'floors': [floor]}, numbers


# ---- works ----------------------------------------------------------------------------------------------------
# The list printed on the map: (number, artist, title, year). * = special exhibition Nature Sanctuary (on view
# through Fall 2026); + = leaving the park in Fall 2026; ~ = new to the park in Spring 2026.
MAP_LIST = '''1|Fletcher Benton|Donut with 3 Balls|2002
2|John Buck|Dream World|1988
3|Venetia Dale|Within Time|2025*
4|Dorothy Dehner|Fortissimo|1993
5|Jim Dine|Two Big Black Hearts|1985
6|Carlos Dorrien|Little Red Riding Hood and Other Stories|2000
7|Lars Fisk|Street Ball|1996
8|Lars Fisk|DeCordova Ball|1999
9|Moko Fukuyama|Menagerie|2024
10|Christopher Frost|“A Mile from Any Neighbor from Walden”|1999
11|Andy Goldsworthy|Watershed|2019
12|Antony Gormley|Reflection II|2008
13|Dan Graham|Crazy Spheroid—Two Entrances|2009
14|George Greenamyer|Mass Art Vehicle|1970
15|Oded Halahmy|Lesh Lah (Why Not?)|2015
16|Hugh Hayden|Huff and a Puff|2023
17|Kapwani Kiwanga|On Growth|2023*+
18|Esther Kläs|Ferma (5)|2015
19|Dennis Kowal|Migration - Series No.7|1976
20|Robert Lobe|Environmental Impact Statement|1988
21|Silvia López Chavez|Chromatic Portals|2026~
22|Paul Matisse|The Musical Fence|1980
23|Jarrett Mellenbruch|Haven|2014
24|Saul Melman|Best of All Possible Worlds|2018
25|Joiri Minaya|Tropticon II|2025*
26|Reuben Nakian|La chambre à coucher de l’empereur|1954
27|William J. O’Brien|Sun & Moon Protector|2016
28|William J. O’Brien|Night Protector|2016
29|William J. O’Brien|Starfish|2016
30|Elliot Offner|Figure from the Sea|1964
31|Zohra Opoku|Self-Portraits series|2015/2016–2024*+
32|Beverly Pepper|Silent Presence|1982
33|Marianna Pineda|Eve Celebrant|1991
34|Reno Pisano|Torso|1950
35|Jaume Plensa|Humming|2011
36|Rona Pondick|Otter|2002–2005
37|John Raimondi|Lupus|1985
38|George Rickey|Three Lines|1965–1966
39|Richard Rosenblum|Venusvine|1990
40|Ron Rudnicki|Rain Gates|2000
41|Kathy Ruttenberg|A Snail’s Pace|2018*
42|Ursula von Rydingsvard|Elegantka|2010
43|Evelyn Rydz|Holding Water|2025*+
44|Robert Schelling|Time at the Museum|2002
45|Ed Shay|Acadian Gyro|1987
46|Arlene Shechet|Channel Liberty|2018~
47|Alyson Shotz|Temporal Shift|2021
48|Kenneth Snelson|Wiggins Fork|1967
49|William Tucker|Horse X|1987
50|Kitty Wales|Feral Goose|2005
51|Joseph Wheelwright|Listening Stone|1995
52|John Wilson|Eternal Presence|1987
53|Isaac Witkin|Jacob’s Dream|1986'''

# Nature Sanctuary works without a page of their own: from the exhibition page (thetrustees.org/exhibit/nature-sanctuary)
NS = SITE + '/exhibit/nature-sanctuary/'
BY_HAND = {
    17: {'image': SITE + '/wp-content/uploads/2025/06/1A3A5735-scaled-608x0-c-default.jpg', 'url': NS,
         'credit': 'A High Line Commission. Courtesy of the High Line, the artist, and Goodman Gallery'},
    43: {'image': SITE + '/wp-content/uploads/2025/06/1A3A5577-scaled-608x0-c-default.jpg', 'url': NS,
         'medium': 'Cast glass, steel, concrete, field stones', 'credit': 'Courtesy of the artist'},
}

# Zohra Opoku's self-portraits hang in several places; the work is filed under the area with most of them
HOME = {31: 'By Admission'}


def park_cards():
    """The sculpture cards on thetrustees.org/content/decordovasculpturepark: (heading, page, picture, alt)."""
    page = get(SITE + '/content/decordovasculpturepark/', 'sculpture-park.html')
    cards = []
    for m in re.finditer(r'<a class="arrow-link" href="([^"]+)">\s*<div class="featured-content-small__img-wrapper">'
                         r'(.*?)<h5>(.*?)</h5>', page, re.S):
        img = m[2]
        src = re.search(r'srcset="([^"]+)"', img)
        best = None
        if src:
            for part in src[1].split(','):
                u, _, w = part.strip().partition(' ')
                if w.endswith('w') and int(w[:-1]) <= 1100 and (not best or int(w[:-1]) > best[1]): best = (u, int(w[:-1]))
        plain = re.search(r'src="([^"]+)"', img)
        alt = re.search(r'alt="([^"]*)"', img)
        cards.append({'heading': text(m[3]), 'url': m[1], 'image': best[0] if best else plain and plain[1],
                      'alt': text(alt[1]) if alt else ''})
    seen, out = set(), []
    for c in cards:
        if c['url'] in seen: continue
        seen.add(c['url']); out.append(c)
    return out


MATERIAL = (r'bronze|steel|granite|alumin|iron|marble|resin|stone|glass|concrete|vinyl|pewter|fabric|corian|plastic|'
            r'yarn|wood|timber|chiffon|paint|lead\b|honeybees|plantings|water|mirror|brick|wire|cor-ten|corten|polaroid|'
            r'print|airstream|video|mortar|enamel')
CREDIT = (r'(deCordova (Museum )?Permanent Collection|Museum Purchase|Museum purchase|Gift|Courtesy|Lent by|Funding|'
          r'Commissioned|Anonymous|Bequest|Installation support)')
DIMS = r'^((?:[\d½¾¼/.]+\s*(?:′|″|"|\'|”|inches|in\.|feet|ft\.?)?\s*(?:x\s*)?)+(?:\s*(?:High|in diameter|overall|inches))?)\s*'


def fields(side, caption, artist, title):
    """Size, medium and credit line from a sculpture page's sidebar and picture caption (both written by hand,
    in several styles)."""
    d = {}
    segs = [s.strip() for s in re.split(r'\s*\|\s*', side) if s.strip()]
    cap = caption or ''
    if norm(artist.split()[-1]) in norm(cap[:60]):          # a citation: Artist. "Title". Year. Medium. Size. Credit.
        segs += [s.strip(' .,') for s in re.split(r'(?<=[a-z"”)\d])[.,]\s+(?=[A-Za-z0-9])', cap)]
    for s in segs:
        if 'credit' not in d:
            m = re.search(CREDIT + r'.*', s)
            if m and not re.match(r'(Born|Lives|B\.)', s):
                c = re.split(r'\s*(Year Created|Back to|Photo by|Photo:|Image Courtesy)', m[0])[0].strip(' .')
                if len(c) > 8: d['credit'] = c
        m = re.match(DIMS, s)
        rest = s
        if m and re.search(r'\d', m[1]) and re.search(r'x|High|diameter|inches|feet|′|″|"', m[1]):
            d.setdefault('dims', m[1].strip())
            rest = s[m.end():]
        rest = re.split(CREDIT, rest)[0].strip(' .,')
        if ('medium' not in d and re.search(MATERIAL, rest, re.I) and len(rest) < 140
                and not re.search(r'(Born|Lives|Worked|B\. \d|Created:|Acquired)', rest)
                and norm(title)[:10] not in norm(rest) and norm(artist)[:10] not in norm(rest)):
            d['medium'] = rest[0].upper() + rest[1:]
    if d.get('credit'):
        acc = re.search(r'\b((?:19|20)\d\d\.\d+(?:\.\d+)*)\b', d['credit'])
        if acc: d['accession'] = acc[1]
    return d


def detail(url, artist='', title=''):
    """A sculpture's page: size, medium, credit line, accession number and the text about it."""
    slug = url.rstrip('/').rsplit('/', 1)[1]
    page = get(url, f'work-{slug}.html')
    side = re.search(r'<h4>Related Information</h4>(.*?)</div>', page, re.S)
    side = side[1] if side else ''
    flat = text(re.sub(r'<br\s*/?>|</p>', ' | ', side))
    cap = re.search(r'<section class="body-photo">.*?<p>(.*?)</p>', page, re.S)
    cap = text(cap[1]) if cap else ''
    d = fields(flat, cap, artist, title)
    body = re.search(r'<section class="body-text">(.*?)</section>', page, re.S)
    paras = [text(p) for p in re.findall(r'<p>(.*?)</p>', body[1], re.S)] if body else []
    paras = [p for p in paras if len(p) > 60]
    if not paras and len(cap) > 200 and norm(artist.split()[-1]) not in norm(cap[:60]):
        paras = [cap]                 # some pages put their text in the picture's caption
    if paras: d['description'] = '\n\n'.join(paras[:3])
    return d


def match(cards, artist, title):
    t, a = norm(title)[:14], norm(artist.split()[-1])
    for c in cards:
        h = norm(c['heading'])
        if t and t in h: return c
    hits = [c for c in cards if a in norm(c['heading'])]
    return hits[0] if len(hits) == 1 or (hits and 'obrien' in a) else None


def picture(key, url):
    """Download once (politely) and save a phone-sized JPEG; returns the app path."""
    if not url: return None
    raw = CACHE / 'img' / (key + (Path(urllib.parse.urlparse(url).path).suffix.lower() or '.jpg'))
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, url], capture_output=True).stdout
        time.sleep(1.5)
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
        im = im.convert('RGBA') if im.mode in ('P', 'LA') else im
        if im.mode == 'RGBA':
            bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=im.split()[3]); im = bg
        im = im.convert('RGB')
        im.thumbnail((1000, 1000))
        im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/decordova/images/{key}.jpg'


def year_of(date):
    m = re.search(r'(\d{4})', date or '')
    return int(m[1]) if m else None


def build_works(floors, numbers):
    floor = floors['floors'][0]
    rooms = {r['id']: r for r in floor['rooms']}
    cards = park_cards()
    used = set()
    out = []
    for line in MAP_LIST.splitlines():
        n, artist, title, year = line.split('|')
        n = int(n)
        flags = re.sub(r'[^*+~]', '', year)
        year = year.rstrip('*+~')
        spots = numbers.get(n, [])
        assert spots, f'number {n} not found on the map'
        room = HOME.get(n) or next((r['id'] for r in floor['rooms'] if r['kind'] == 'gallery' and
                                    inside(P(*spots[0]), r['poly'])), None)
        assert room, (n, spots)
        c = match(cards, artist, title)
        d = detail(c['url'], artist, title) if c else {}
        hand = BY_HAND.get(n, {})
        for k in ('medium', 'credit'):
            if hand.get(k): d.setdefault(k, hand[k])
        if c: used.add(c['url'])
        key = f'decordova-{n:02d}'
        notes = [f'No. {n} on the park map.']
        if len(spots) > 1:
            where = sorted({next((r['id'] for r in floor['rooms'] if r['kind'] == 'gallery' and
                                  inside(P(*s), r['poly'])), '') for s in spots} - {''})
            notes.append(f'Shown in {len(spots)} places: ' + ', '.join(where) + '.')
        if '*' in flags: notes.append('Part of the special exhibition Nature Sanctuary, which ended on October 4, 2026, '
                                      'so it may no longer be in the park.')
        elif '+' in flags: notes.append('Leaving the park in Fall 2026.')
        if '~' in flags: notes.append('New to the park in Spring 2026.')
        credit = d.get('credit', '')
        a = {'id': key, 'number': n, 'title': title, 'artist': artist, 'date': year, 'year': year_of(year),
             'medium': d.get('medium'), 'dimensions': d.get('dims'), 'accession': d.get('accession'),
             'creditLine': credit or None, 'gallery': room, 'galleryName': rooms[room]['name'], 'floor': 'park',
             'placeNote': ' '.join(notes), 'description': d.get('description'),
             'descriptionKind': 'From deCordova’s page about this sculpture' if d.get('description') else None,
             'exhibition': 'Nature Sanctuary (special exhibition, June 5, 2025 – October 4, 2026)' if '*' in flags else None,
             'url': c['url'] if c else hand.get('url', SITE + '/content/decordovasculpturepark/'),
             'image': picture(key, c['image'] if c else hand.get('image')),
             'imageCredit': 'deCordova Sculpture Park and Museum (The Trustees)' if c or hand else None}
        out.append({k: v for k, v in a.items() if v not in (None, '')})
    order = {r['id']: i for i, r in enumerate(floor['rooms'])}
    out.sort(key=lambda a: (order[a['gallery']], a['number']))
    extra = [c for c in cards if c['url'] not in used]
    return {'source': 'deCordova Sculpture Park map (Summer 2026) and the sculptures’ pages on thetrustees.org',
            'checked': time.strftime('%Y-%m-%d'), 'count': len(out), 'complete': True, 'artworks': out}, extra


def highlights():
    """The Permanent Collection highlights linked from thetrustees.org/content/decordova-permanent-collection."""
    page = get(SITE + '/content/decordova-permanent-collection/', 'permanent-collection.html')
    out = []
    for slug in ['blue-refuge', 'transcendental-wheatleys-desk-emersons-chair', 'second-vatican-council-wrap',
                 'decordova-window']:
        if f'/content/{slug}/' not in page: continue
        p = get(f'{SITE}/content/{slug}/', f'work-{slug}.html')
        hero = re.search(r'<section class="hero-text-only">.*?<p>(.*?)</p>.*?<h1>(.*?)</h1>', p, re.S)
        img = re.search(r'<section class="body-photo">.*?<img src="([^"]+)"', p, re.S)
        cap = re.search(r'<section class="body-photo">.*?<p>(.*?)</p>', p, re.S)
        if not hero: continue
        artist, title = text(hero[1]), text(hero[2])
        cap = text(cap[1]) if cap else ''
        out.append({'slug': slug, 'artist': artist, 'title': title, 'url': f'{SITE}/content/{slug}/',
                    'image': img[1] if img else None, 'date': (re.search(r'\b(1[89]\d\d|20\d\d)\b', cap) or [None, ''])[1],
                    'caption': cap})
    return out


def build_guide(works, extra):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'),
                     'year': a.get('year'), 'medium': a.get('medium'), 'accession': a.get('accession'),
                     'url': a['url'], 'imageUrl': a.get('image'), 'onView': True, 'gallery': a['gallery'],
                     'floor': a['floor']}.items() if v not in (None, '')})
    for c in extra:                       # on the museum's sculpture park page but not on the current map
        artist, _, title = c['heading'].partition(', ')
        artist = re.sub(r'^PLATFORM \d+:\s*', '', artist)
        if not title: artist, _, title = c['heading'].partition(' – ')
        if not title: continue                # a program page, not a work
        key = 'decordova-' + norm(c['url'].rstrip('/').rsplit('/', 1)[1])[:30]
        d = detail(c['url'], artist, title)
        rows.append({k: v for k, v in {'id': key, 'title': title or c['heading'], 'artist': artist,
                     'medium': d.get('medium'), 'accession': d.get('accession'), 'url': c['url'],
                     'imageUrl': picture(key, c['image']), 'onView': False}.items() if v not in (None, '')})
    for h in highlights():
        key = 'decordova-' + norm(h['slug'])[:30]
        rows.append({k: v for k, v in {'id': key, 'title': h['title'], 'artist': h['artist'], 'date': h['date'],
                     'year': year_of(h['date']), 'url': h['url'], 'imageUrl': picture(key, h['image']),
                     'onView': False}.items() if v not in (None, '')})
    rows.sort(key=lambda w: (not w['onView'], norm(w.get('artist', '')), w.get('year') or 0))
    return {'museum': MUSEUM, 'name': 'deCordova Sculpture Park and Museum', 'checked': time.strftime('%Y-%m-%d'),
            'source': 'deCordova park map (Summer 2026) and thetrustees.org', 'onViewKnown': True,
            'note': 'The indoor galleries are closed for renovation, so on view means in the Sculpture Park now (the 53 '
                    'sculptures on the Summer 2026 park map). deCordova’s permanent collection (more than 1,500 '
                    'photographs among its works) is not online; the Permanent Collection highlights and park works '
                    'shown on the museum’s website are listed too.',
            'works': rows}


def main():
    OUT.mkdir(exist_ok=True)
    floors, numbers = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works, extra = build_works(floors, numbers)
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
    print(f'{works["count"]} sculptures on the map, {sum("image" in a for a in works["artworks"])} with pictures, '
          f'{sum("description" in a for a in works["artworks"])} with text; collection list {len(guide["works"])}')
    for k, v in by.items(): print(f'  {k}: {v}')
    print('not matched to a page:', [a['number'] for a in works['artworks'] if 'image' not in a])
    print('park pages not on the map:', [c['heading'] for c in extra])


if __name__ == '__main__':
    sys.exit(main())
