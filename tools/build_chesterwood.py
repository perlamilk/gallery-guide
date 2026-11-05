#!/usr/bin/env python3
"""Build the Chesterwood (Stockbridge, MA) map guide (run: python3 tools/build_chesterwood.py).

    data/chesterwood/floors.json     the estate seen from above: Residence, Studio (with its rooms), Barn Gallery,
                                     Woodshed Gallery, gardens, woodland walks, restrooms, parking (a flat 2D plan)
    data/chesterwood/artworks.json   what is in the Studio, room by room and wall by wall, and the buildings
    data/chesterwood/images/         pictures, made smaller for phones
    data/guides/<QID>.json           the same list for the museum page

The map: Chesterwood's own "Map of the Estate" (chesterwood.org/new-page-1, the drawing also used for the outdoor
sculpture show maps of 2019 and 2020), cached in .cache/chesterwood/maps/estate-map.png. The drawing has north to the
right; it is traced here at 1400 px wide and turned so north is up. It is a hand drawing, so distances are
approximate (about 0.23 m per traced pixel, checked against the Residence and Studio on aerial photographs).
OpenStreetMap has only unnamed outlines here, so it is not used. The rooms inside the Studio follow the
Studio guide (Main Room, Casting Room, Reception Room, the south piazza) but their shapes are approximate.

The works: Chesterwood's printable "Guide to the Studio" (chesterwood.org/s/Highlights-Guide-to-the-Studio.pdf), which
lists every piece in the Studio by room and wall with its National Trust number; the Collection and Studio pages; and
the 2026 exhibitions (the season ended Oct 31). Pages are read once by tools/harvest_chesterwood.py. Pictures come
from the museum's pages (credited to Chesterwood) and Wikimedia Commons (with credits).
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
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_osv import centroid, poly_line_gap, band, along  # noqa: E402  (shared geometry)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'chesterwood'
CACHE = ROOT / '.cache' / 'chesterwood'
MUSEUM = 'Q5093884'
SITE = 'https://www.chesterwood.org'
STUDIO_PDF = SITE + '/s/Highlights-Guide-to-the-Studio.pdf'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SOURCE = 'Chesterwood’s Map of the Estate (chesterwood.org, “Map of the Estate”) and its Guide to the Studio'

K = 0.66          # map units (0.35 m) per traced pixel of the estate map at 1400 px wide
W = 1400


def P(mx, my):
    """A point traced on the estate map (north to the right) -> map units, north up."""
    return [round(my * K, 1), round((W - mx) * K, 1)]


def poly(*pts):
    return [P(*p) for p in pts]


def rect(x0, y0, x1, y1):
    return poly((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def circle(cx, cy, r, n=14):
    return poly(*[(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)])


# ---- the places (traced on the estate map) ------------------------------------------------------------------
G, S = 'gallery', 'space'
# id, kind, short label, name, polygon (estate-map pixels), z
PLACES = [
    ('Barn Gallery', G, 'Barn Gallery', 'Barn Gallery and Visitor Center: admissions desk, Museum Shop, exhibitions',
     poly((668, 772), (698, 772), (698, 728), (758, 728), (772, 760), (762, 806), (668, 806)), 2),
    ('Woodshed Gallery', G, 'Woodshed', 'Woodshed Gallery (exhibitions)', rect(832, 795, 886, 818), 2),
    ('Standing Lincoln', G, 'Standing Lincoln', 'Standing Lincoln (bronze, outdoors by the Woodshed)',
     circle(928, 774, 9, 8), 2),
    ('Restrooms', S, None, 'Restrooms', rect(480, 718, 516, 770), 2),
    ('Residence', G, 'Residence', 'The Residence (1901, by Henry Bacon): guided tours; the Residence Galleries',
     poly((262, 585), (336, 585), (336, 690), (346, 690), (346, 724), (316, 724), (316, 690), (262, 690)), 2),
    ('Piazza', G, 'Piazza', 'Studio piazza: the 50-foot south porch with the view of Monument Mountain',
     rect(268, 378, 282, 455), 2),
    ('Casting Room', G, 'Casting Room', 'Studio: Casting Room', rect(282, 378, 318, 400), 2),
    ('Main Room', G, 'Studio', 'Studio: the Main Room (26-foot walls, the railroad flatcar)', rect(282, 400, 318, 436), 2),
    ('Reception Room', G, 'Reception', 'Studio: Reception Room', rect(282, 436, 318, 455), 2),
    ('Studio Garden', G, 'Garden', 'Studio Garden: the formal garden, the fountain by Henry Bacon and the hydrangea allée',
     poly((320, 238), (372, 238), (372, 250), (560, 260), (575, 470), (420, 482), (372, 500), (320, 500)), 0),
    ('Woodland Walk', G, 'Woodland Walk', 'Woodland Walk: the trails French laid out, and outdoor sculpture',
     poly((600, 420), (1000, 350), (1140, 360), (1160, 540), (1000, 570), (800, 600), (690, 680), (600, 650)), 0),
    ('Overlook', S, None, 'The Overlook (view of Stockbridge, Lenox and Lee) and the Circle', circle(1215, 603, 38), 0),
    ('Picnic Area', S, None, 'Picnic area', poly((195, 905), (360, 815), (372, 832), (210, 922)), 0),
]
DOOR_AT = {   # where a place's door is (estate-map pixels), when it isn't simply the nearest path
    'Barn Gallery': (672, 785), 'Residence': (346, 700), 'Main Room': (318, 418), 'Reception Room': (318, 446),
    'Restrooms': (500, 770), 'Woodshed Gallery': (850, 795), 'Standing Lincoln': (920, 776),
    'Studio Garden': (400, 420), 'Woodland Walk': (820, 600), 'Overlook': (1177, 590), 'Picnic Area': (360, 822),
}
# rooms joined to each other inside the Studio (estate-map pixels)
INNER_DOORS = [('Main Room', 'Casting Room', (300, 400)), ('Main Room', 'Reception Room', (300, 436)),
               ('Reception Room', 'Piazza', (282, 446)), ('Main Room', 'Piazza', (282, 418))]

# paths: (name, half width in map units, points in estate-map pixels)
WALKS = [
    ('Drive from the parking lot', 7, [(430, 1000), (430, 830)]),
    ('Drive by the Residence', 6, [(430, 830), (362, 800), (346, 720), (346, 600), (370, 520)]),
    ('Path to the Studio and the fountain', 5, [(370, 520), (376, 470), (382, 425), (330, 420), (318, 418)]),
    ('Path by the Restrooms', 6, [(370, 520), (450, 512), (530, 525), (575, 590), (580, 680), (540, 770),
                                  (470, 800), (430, 830)]),
    ('Path to the Barn Gallery', 5, [(540, 770), (600, 792), (672, 785)]),
    ('The Straight Path (hydrangea allée)', 5, [(382, 425), (480, 410), (580, 400)]),
    ('Woodland Walk (upper trail)', 4, [(580, 400), (760, 360), (900, 342), (1020, 338), (1060, 345), (1150, 480),
                                        (1177, 568)]),
    ('Woodland Walk (lower trail)', 4, [(700, 728), (700, 700), (800, 615), (1000, 580), (1177, 568)]),
    ('Path from the Barn Gallery to the woods', 4, [(672, 785), (690, 760), (700, 728)]),
    ('Garden walk along the Studio', 4, [(382, 425), (376, 330), (375, 245)]),
    ('Path to the Ledges Trail', 4, [(375, 245), (470, 222), (555, 205)]),
    ('Ledges Trail (steep, rocky)', 4, [(555, 205), (600, 165), (640, 135), (715, 70)]),
    ('Woods path to the Woodland Walk', 4, [(555, 205), (650, 280), (760, 360)]),
    ('Path to the Woodshed and Standing Lincoln', 4, [(762, 790), (850, 795), (920, 776)]),
]
AMENITIES = [   # estate-map pixels
    ('entrance', (672, 790)), ('info', (715, 790)), ('shop', (740, 765)),
    ('restroom', (498, 744)),
]
LABELS = [
    ('Parking', 'note', (430, 960)), ('Williamsville Road', 'note', (95, 760)),
    ('Hemlock Glade', 'area', (1290, 520)), ('Ledges Trail to the hilltop (about 1,200 ft)', 'note', (700, 40)),
    ('Pergola (south of the Studio)', 'note', (245, 470)), ('Fountain by Henry Bacon', 'area', (395, 395)),
    ('No café: picnic here or eat in Stockbridge', 'note', (230, 960)),
]


def build_floors():
    rooms, doors = [], []
    by_id = {}
    for pid, kind, label, name, pg, z in PLACES:
        r = {'id': pid, 'kind': kind, 'name': name, 'poly': pg, 'z': z}
        if kind == G: r['label'] = label
        rooms.append(r); by_id[pid] = r
    walks = []
    for i, (name, half, pts) in enumerate(WALKS):
        line = [P(*p) for p in pts]
        r = {'id': f'walk-{i + 1}', 'kind': 'corridor', 'name': name, 'poly': band(line, half),
             'labelAt': along(line), 'z': 1}
        rooms.append(r); walks.append((r, pts, line))
    # paths meet where they share an end point
    ends = {}
    for r, pts, _ in walks:
        for p in (pts[0], pts[-1]):
            ends.setdefault(p, []).append(r['id'])
    for r, pts, _ in walks:            # ...or where one ends on another's middle
        for p in pts[1:-1]:
            if p in ends and r['id'] not in ends[p]: ends[p].append(r['id'])
    for p, ids in ends.items():
        for a, b in zip(ids, ids[1:]):
            doors.append({'a': a, 'b': b, 'at': P(*p), 'width': 10, 'axis': 'o'})
    for pid, p in DOOR_AT.items():
        at = P(*p)
        wr, _, line = min(walks, key=lambda w: poly_line_gap([at], w[2])[0])
        doors.append({'a': wr['id'], 'b': pid, 'at': at, 'width': 8, 'axis': 'o'})
    for a, b, p in INNER_DOORS:
        doors.append({'a': a, 'b': b, 'at': P(*p), 'width': 6, 'axis': 'o'})
    amen = [{'type': t, 'at': P(*p)} for t, p in AMENITIES]
    labels = [{'text': t, 'kind': k, 'at': P(*p)} for t, k, p in LABELS]
    floor = {'id': 'G', 'label': 'The Estate', 'order': 0,
             'area': 'Barn Gallery and Visitor Center, the Residence, the Studio and its garden, the Woodshed Gallery, '
                     'the Woodland Walk and the Overlook',
             'transform': [1, 0, 0], 'rooms': rooms, 'closed': [], 'amenities': amen, 'labels': labels,
             'doors': doors, 'homeView': ['Barn Gallery', 'Residence', 'Main Room', 'Overlook']}
    return {'about': 'Built by tools/build_chesterwood.py, traced from Chesterwood’s own Map of the Estate (a hand '
                     'drawing, so distances are approximate) and turned so north is up. The rooms inside the Studio '
                     'follow Chesterwood’s Guide to the Studio; their shapes are approximate. Only the ground floor of '
                     'each building is drawn.',
            'source': SOURCE, 'units': 'map units of about 0.35 m, north up', 'approximate': True,
            'defaultFloor': 'G', 'galleryWord': 'Place', 'floors': [floor]}


# ---- pictures ---------------------------------------------------------------------------------------------------
SQ = 'https://images.squarespace-cdn.com/content/v1/59500a5be6f2e1bb5898ccd1/'
_last = [0.0]


def picture(key, url):
    """Download once (politely) and save a phone-sized JPEG; returns the app path."""
    if not url: return None
    raw = CACHE / 'img' / (key + (Path(urllib.parse.urlparse(url).path).suffix.lower() or '.jpg'))
    dest = OUT / 'images' / f'{key}.jpg'
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        out = b''
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
    return f'data/chesterwood/images/{key}.jpg'


def text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def commons_info(names):
    """Commons file info (1000-px thumbnail, author, licence) for many files, asked in one batch and cached."""
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
            except Exception: time.sleep(30 * (k + 1))
        else: raise SystemExit('Wikimedia Commons is not answering; try again later')
        norm = {x['to']: x['from'] for x in d['query'].get('normalized', [])}
        for p in d['query']['pages'].values():
            if 'imageinfo' not in p: print('  not on Commons:', p['title']); continue
            ii = p['imageinfo'][0]; em = ii.get('extmetadata', {})
            name = norm.get(p['title'], p['title'])[5:]
            have[name] = {'thumb': (ii.get('thumburl') or ii['url']).split('?')[0], 'page': ii.get('descriptionurl'),
                          'artist': text(em.get('Artist', {}).get('value')) or 'Unknown',
                          'license': text(em.get('LicenseShortName', {}).get('value')),
                          'about': text(em.get('ImageDescription', {}).get('value'))[:300]}
        f.write_text(json.dumps(have, ensure_ascii=False, indent=1))
        time.sleep(3)
    return have


# ---- the works ---------------------------------------------------------------------------------------------------
def studio_guide_lines():
    """The Guide to the Studio as clean lines of text (pdftotext; the PDF puts a tab, CR and nbsp between words)."""
    pdf = CACHE / 'pdf' / 'studio-guide.pdf'
    if not pdf.exists():
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, STUDIO_PDF],
                                       capture_output=True, check=True).stdout)
    s = subprocess.run(['pdftotext', '-layout', str(pdf), '-'], capture_output=True, check=True).stdout.decode()
    s = (s.replace('\r', '').replace('\t', ' ').replace(' ', ' ').replace('­', '').replace('‐', '-')
         .replace('--', '-'))
    s = re.sub(r' +', ' ', s)
    lines = [l.strip() for l in s.split('\n')]
    # drop the shelf diagrams (rows of item numbers) and stray superscripts
    return [l for l in lines if l and not re.fullmatch(r'(\d+[a-z]?|[A-D]|st)( +(\d+[a-z]?|[A-D]))*', l)]


HEAD = re.compile(r'^(Guide to the Studio|Main Room Studio Floor|East Wall.*|West Wall|South Wall|Casting Room|'
                  r'Reception Room|High Shelf|Wall Mounted.*|Left.*Shelf|Right.*Shelf|Right, Wall Mounted.*|'
                  r'Left, Below.*|Atop Half Wall.*|Right, Above the Casting Room Threshold|\(Top View of Shelf\))$')


def parse_studio(lines):
    """Items of the Guide to the Studio: room, wall, place on the wall, number and text."""
    room, wall, place = 'Main Room', '', ''
    items, cur, intro = [], None, False
    for l in lines:
        if HEAD.match(l):
            if cur: cur['done'] = True
            if l == 'Casting Room': room, wall, place = 'Casting Room', '', ''
            elif l == 'Reception Room': room, wall, place, intro = 'Reception Room', '', '', True
            elif l == 'Main Room Studio Floor': wall, place = 'On the studio floor', ''
            elif re.match(r'(East|West|South) Wall', l): wall, place = l.split(',')[0], ', '.join(l.split(', ')[1:])
            elif not l.startswith('(') and l != 'Guide to the Studio': place = l
            continue
        m = re.match(r'^(\d+|[A-D])\.(?:\s+(\D.*))?$', l)
        if m or (cur is None or cur['done']) and not intro and re.match(r'^[A-Z].*,', l):
            intro = False
            if cur: cur['done'] = True
            cur = {'room': room, 'wall': wall, 'place': place, 'no': m[1] if m else '',
                   'text': (m[2] or '') if m else l, 'done': False}
            items.append(cur)
        elif intro: continue
        elif cur and (not cur['done'] or l.startswith('(see')):
            cur['text'] = (cur['text'] + ' ' + l).strip()
        if cur and re.search(r'NT\s+[\d.]+(\s*&\s*NT\s+[\d.]+)?\s*$', cur['text']): cur['done'] = True
    return items


def studio_work(it):
    t = re.sub(r'\s+', ' ', it['text']).strip()
    acc = '; '.join(re.findall(r'NT\s+([\d.]+)', t))
    t = re.sub(r'\s*NT\s+[\d.]+(\s*&\s*NT\s+[\d.]+)?', '', t).strip()
    t = t.replace('1 Infantry', '1st Infantry').replace('“"', '“').replace('"', '”').replace('(1923. ', '(1923). ')
    m = re.match(r'^(.+?),\s*(.+?)\s*\(([^)]*\d[^)]*|ND)\)[.,]?\s*(.*)$', t)
    if m and len(m[1]) < 80:
        title, medium, date, rest = m[1], m[2], m[3], m[4]
    else:
        m2 = re.match(r'^(.+?)[.,]\s*(.*)$', t)
        title, medium, date, rest = (m2[1], None, None, m2[2]) if m2 else (t, None, None, '')
        m3 = re.match(r'^([a-z][a-z ]+)\.\s*(.*)$', rest)          # "plaster. After ..." / "plaster head. ..."
        if m3: medium, rest = m3[1], m3[2]
    medium = medium and (medium[0].upper() + medium[1:]).rstrip(', ')
    rest = re.sub(r'^of clay model\.\s*', '', rest)
    if 'reproduction (1960)' in t: medium, date = 'Plaster reproduction of the clay sketch', '1960'
    if date == 'ND': date = None
    low = (title + ' ' + (medium or '') + ' ' + rest).lower()
    if 'caproni' in low or 'commercial' in low or low.startswith('cast of'):
        artist = 'Commercial plaster cast' + (' (P. P. Caproni and Brother, Boston)' if 'caproni' in low else '')
        for name in ('Jean-Antoine Houdon', 'Antoine-Louis Barye', 'Desiderio da Settignano', 'Raphael'):
            if name.lower() in low: artist += f', after {name}'; break
    elif title.startswith('La Jeunesse'):
        artist = 'Herbert Adams (1858–1945)'
    elif title.startswith('Life Cast'):
        artist = 'Life cast made in Daniel Chester French’s studio'
    else:
        artist = 'Daniel Chester French (1850–1931)'
    year = re.search(r'\d{4}', date or '')
    where = ' · '.join(x for x in (it['room'], it['wall'], it['place']) if x)
    if it['no']: where += f" (no. {it['no']})"
    return {'title': title.strip(), 'artist': artist, 'date': date, 'year': int(year[0]) if year else None,
            'medium': medium, 'accession': acc or None, 'description': rest or None, 'where': where}


# Rooms and buildings, with their pictures: place -> (title, words, picture, credit or Commons file)
ROOM_ITEMS = [
    ('Main Room', 'The Studio’s Main Room',
     'The main work space is a 30 by 29-foot room with 26-foot walls, high enough for heroic equestrian models. Part of '
     'the floor is a standard-gauge railroad flatcar: French removed the floor panels next to it and pushed his work '
     'outdoors on tracks to judge it in daylight, often standing down in the field to see it at the right distance. '
     'The Seated Lincoln plaster model and the marble Andromeda are here.',
     ('commons', 'Chesterwood (Stockbridge, MA) - studio interior.JPG')),
    ('Main Room', 'The railroad track',
     'The tracks that carried French’s models out of the Studio on a flatcar, into the open air.',
     ('commons', 'CHESTERWOOD TRACKS.jpg')),
    ('Casting Room', 'The Casting Room',
     'Here clay models were cast in plaster for further work and, later, for casting in bronze. Through trap doors, '
     'plaster casts and discarded clay models were lowered to the cellar.', None),
    ('Reception Room', 'The Reception Room',
     'Fashionable artists’ studios of French’s time had a reception room to receive business visitors. French also '
     'drew and painted portraits of friends, family and neighbors here in the north light, and the family took '
     'afternoon tea here when it rained. A recess in the east wall, the “Cozy Corner”, has a built-in bookcase and a '
     'Pompeian-style day bed French built for his early studio in Concord.',
     ('sq', '1499716693908-JHDUQ779ZMHIBECVQ60V/Refurbished+Studio_web.jpg')),
    ('Piazza', 'The piazza',
     'The 50-foot porch on the south side of the Studio, with the view of Monument Mountain that French loved. The '
     'family took afternoon tea here in good weather.',
     ('sq', '1499716692963-BPFXFL85GMKDJ7ZS3G9X/CH-302_web.jpg')),
    ('Main Room', 'The Studio (1898) by Henry Bacon',
     'French asked his friend Henry Bacon, later the architect of the Lincoln Memorial, to design the Studio in 1897, '
     'where the old barn stood, for its view of Monument Mountain. French moved in on July 16, 1898, before it was '
     'finished. It was restored in 2014 to look as it did in French’s time.',
     ('commons', 'Chesterwood (Stockbridge, MA) - studio and garden.JPG')),
    ('Residence', 'The Residence (1901) by Henry Bacon',
     'The three-floor stucco house, with nine bedrooms, mixes English Georgian, American Colonial Revival and Italian '
     'villa ideas; it sits on a ridge with views from its porches. French’s sister-in-law Alice Helm French painted '
     'the fresco garlands on the Breakfast Porch and retouched them for 31 years. The rooms keep family heirlooms '
     'and antiques French bought at local auctions; doors and moldings came from the old Warner farmhouse. Seen on '
     'the guided tour.',
     ('commons', 'Chesterwood (Stockbridge, MA) - house.JPG')),
    ('Studio Garden', 'The Studio Garden and fountain',
     'French designed this formal garden in 1898 on an old apple orchard, as a series of outdoor rooms for parties, '
     'costume balls and tableaux vivants. In the round court in front of the Studio is a marble-cement fountain by '
     'Henry Bacon with dancing putti. The Straight Path, lined with standard hydrangeas and peonies, leads to the '
     'Woodland Walk; south of the Studio a pergola with benches designed by French looks out on the Berkshire Hills.',
     ('sq', '160a35ac-7550-4942-8516-f07139c3a7b6/Peonies+and+Studio_photo+Paul+Rocheleau.jpg')),
    ('Studio Garden', 'The hydrangea walk',
     'The Straight Path (allée) from the fountain, lined with standard hydrangeas, peonies and annuals.',
     ('sq', '2d3ff567-762a-42d3-8918-b16356bbd4fa/The+Studio+-+Hydrangea+Walk_photo+Don+Freeman+%283%29.jpg')),
    ('Woodland Walk', 'The Woodland Walk',
     'French laid out these trails around 1898 as a “classroom of nature” for his daughter Margaret: the Circle, the '
     'Glade and the Overlook, joined by footpaths with “vistas” cut through the trees. The Overlook looks across to '
     'Stockbridge, Lenox and Lee. The restored Ledges Trail climbs steeply over rocky ledges to a view at about 1,200 '
     'feet. The Woodland Walk is a mostly flat dirt path.',
     ('commons', 'The garden at Chesterwood looking toward the studio of Daniel Chester French, Stockbridge, '
                 'Massachusetts LCCN2010630505.tif')),
    ('Barn Gallery', 'The Barn Gallery and Visitor Center',
     'Start here: the admissions desk, the Museum Shop and exhibitions. Visitors can be dropped off at the door.',
     ('commons', 'Chesterwood Barn Gallery & Visitor Center.jpg')),
    ('Woodshed Gallery', 'The Woodshed Gallery',
     'A small gallery in the estate’s old woodshed, used for changing exhibitions in the summer season.', None),
    ('Standing Lincoln', 'Standing Lincoln',
     'A bronze of French’s standing Abraham Lincoln, whose original (1912) stands at the Nebraska State Capitol in '
     'Lincoln. It is outdoors at the edge of the woods by the Woodshed, as the Map of the Estate shows.', None),
]

# Highlights from the Studio guide that have a picture on Chesterwood's pages (studio item title -> picture)
STUDIO_PICTURES = {
    'Andromeda': ('sq', '1502652870939-QGDY5W8P6AMBU68AKL85/Andromeda_header.jpg'),
    'Seated Lincoln': ('sq', '09b689b5-2871-4e4d-a696-750014bf6b01/Home+Page+Banner+Option+-+Lincoln+in+Studio_Jason'
                             '+Baker+%281%29.jpeg'),
}
EXTRA_TEXT = {
    'Andromeda': 'French’s last work, left unfinished when he died in October 1931. Unlike the frantic Andromedas of '
                 'Rembrandt or Titian, his chained princess seems to doze in the sun; a young Stockbridge woman, Ethel '
                 'Cummings, posed for her. It was the piece the Studio’s flatcar was built for.',
}

# Collection pieces on Chesterwood's pages; where they are shown isn't published
COLLECTION = [
    ('1502074792079-PYMCVDPB6YHFZGLQCXRY/image-asset.jpeg',
     {'title': 'Daniel Chester French', 'artist': 'Robert Vonnoh (1858–1933)', 'date': '1913', 'year': 1913,
      'medium': 'Oil on canvas', 'description': 'A portrait of the sculptor by his friend, the painter Robert Vonnoh.'}),
    ('1502074956778-S1MDYF8T92X7JWUKZVW5/image-asset.jpeg',
     {'title': 'Architecture (maquette)', 'artist': 'Daniel Chester French (1850–1931)', 'medium': 'Bronze maquette',
      'description': 'Shown in the Collections Gallery, a former storage room made into a climate-controlled gallery '
                     'with a grant from the Henry Luce Foundation.'}),
    ('1502074617685-WYXW4DE5YNHH1O9VA95B/NT69.38.112MaquetteSpiritofLife.View1_header.jpg',
     {'title': 'Spirit of Life (maquette)', 'artist': 'Daniel Chester French (1850–1931)', 'accession': '69.38.112',
      'medium': 'Maquette', 'description': 'A small model for the Spencer Trask Memorial in Saratoga Springs, New York '
                                           '(1915). Its full-size head is in the Studio.'}),
    ('1502074624537-4CC837LDFGVHHTIHEVCZ/NTMaquetteAndromeda.View2_header.jpg',
     {'title': 'Andromeda (maquette)', 'artist': 'Daniel Chester French (1850–1931)', 'medium': 'Maquette',
      'description': 'A small model for French’s last work; the marble is in the Studio.'}),
    ('1502074628247-LULCU56JKGVKAC56ZPH9/NT69.38.272BronzeWorkingModelSpiritOfTheWaters_header.jpg',
     {'title': 'Spirit of the Waters (working model)', 'artist': 'Daniel Chester French (1850–1931)',
      'accession': '69.38.272', 'medium': 'Bronze working model',
      'description': 'French’s first idea for the Spencer Trask Memorial, which Katrina Trask did not like; he made '
                     'Spirit of Life instead.'}),
    ('1502074617406-IHLD2DKUY6GCJKX2KJBB/NT69.38.83HeadofManhattan_header.jpg',
     {'title': 'Head of Manhattan', 'artist': 'Daniel Chester French (1850–1931)', 'accession': '69.38.83',
      'medium': 'Study', 'description': 'A study for Manhattan, one of the two figures French made for the Manhattan '
                                        'Bridge approach in New York (1916), now at the Brooklyn Museum.'}),
    ('1502074625887-IV7IXXJA60NTULCHWB2O/NT69.38.260MaquetteofMemory_header.jpg',
     {'title': 'Memory (maquette)', 'artist': 'Daniel Chester French (1850–1931)', 'accession': '69.38.260',
      'medium': 'Maquette', 'description': 'A small model for Memory, whose marble is at the Metropolitan Museum of '
                                           'Art.'}),
    ('1502074614338-J2OJLWSME9HD0FRO8TT5/NT69.38.12MaquetteAmerica.View1_header.jpg',
     {'title': 'America (maquette)', 'artist': 'Daniel Chester French (1850–1931)', 'accession': '69.38.12',
      'medium': 'Maquette', 'description': 'A small model for America, one of The Four Continents French carved for '
                                           'the U.S. Custom House in New York (1907).'}),
]

# 2026 exhibitions (chesterwood.org/upcoming-exhibitions): title, place, dates, words, picture
EXHIBITIONS = [
    ('The Minute Man: Examining Patriotism, Victory, and Loss', 'Residence', 'May 15 – October 31, 2026',
     'Centered on French’s Minute Man, the lasting symbol of American patriotism, this show in the Residence Galleries '
     'explored liberty, victory and the sacrifices of military service through portraits, monuments and memorials by '
     'French and artists of his time, with contemporary works. Curated by Dana Pilson.',
     '676351ce-196f-495a-a729-be927d2b14c0/The+Minute+Man+-+Photo+by+Kevin+Fleming%2C+Courtesy+of+Chestewrwood.jpg'),
    ('In the Open: New England Sculptors Reclaim the Landscape', 'Woodland Walk', 'June 15 – October 31, 2026',
     'The 48th annual outdoor exhibition of contemporary sculpture: works by regional artists in the meadows and '
     'woodlands of the estate.', '80dd42df-8350-4a56-9287-9621e46f4ad6/Chesterwood+Sculpture-4-cropped.jpg'),
    ('Artist Intervention in Daniel Chester French’s Study', 'Residence', 'May 15 – October 31, 2026',
     'Caren Kinne placed two assemblage sculptures, based on a period typewriter and a candlestick telephone, in '
     'French’s home office.', None),
    ('Art Studios: How Artistic Processes Inform Architectural Design', 'Woodshed Gallery', 'May 15 – July 20, 2026',
     'Four artist-studio projects by the architect Grigori Fateyev, including the proposed Woodthrush Art Center at '
     'Chesterwood.', None),
    ('Revolutionary Teapots', 'Woodshed Gallery', 'August 1 – September 27, 2026',
     'The Berkshire Potters Collective’s teapots for the 250th anniversary of the Declaration of Independence.', None),
]


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower().replace('’', '')).strip('-')[:40]


def build_works(floors):
    rooms = {r['id']: r for r in floors['floors'][0]['rooms']}
    info = commons_info([src[1] for *_, src in ROOM_ITEMS if src and src[0] == 'commons'])
    placed, unplaced, used = [], [], set()

    def img(key, src):
        if not src: return None, None
        if src[0] == 'commons':
            i = info.get(src[1])
            if not i: return None, None
            return picture(key, i['thumb']), f'{i["artist"]}, {i["license"]}, via Wikimedia Commons'
        p = picture(key, SQ + src[1])
        return p, ('Chesterwood' if p else None)

    def add(a, place):
        a = {k: v for k, v in a.items() if v not in (None, '')}
        n, k = 2, a['id']
        while a['id'] in used: a['id'] = f'{k}-{n}'; n += 1
        used.add(a['id'])
        if place:
            a.update(gallery=place, galleryName=rooms[place]['name'].split(':')[0].split(' (')[0], floor='G')
            placed.append(a)
        else:
            unplaced.append(a)

    for place, title, words, src in ROOM_ITEMS:
        key = f'cw-{slugify(title)}'
        im, cr = img(key, src)
        add({'id': key, 'title': title, 'artist': 'Chesterwood', 'medium': 'Room' if place in (
            'Main Room', 'Casting Room', 'Reception Room', 'Piazza') else 'Historic place', 'description': words,
             'descriptionKind': 'From Chesterwood’s pages', 'url': SITE + '/the-residence-and-studio',
             'image': im, 'imageCredit': cr}, place)
    for it in parse_studio(studio_guide_lines()):
        w = studio_work(it)
        key = f'cw-s-{slugify(w["title"])}'
        im, cr = img(key, STUDIO_PICTURES.get(w['title']))
        desc = ' '.join(x for x in (EXTRA_TEXT.get(w['title']), w['description']) if x)
        add({'id': key, 'title': w['title'], 'artist': w['artist'], 'date': w['date'], 'year': w['year'],
             'medium': w['medium'], 'accession': w['accession'] and f'NT {w["accession"]}', 'description': desc,
             'descriptionKind': 'From Chesterwood’s Guide to the Studio', 'url': STUDIO_PDF,
             'placeNote': w['where'] + '. Pieces are sometimes moved.', 'image': im, 'imageCredit': cr},
            it['room'])
    for path, a in COLLECTION:
        key = f'cw-c-{slugify(a["title"])}'
        im, cr = img(key, ('sq', path))
        add({'id': key, **a, 'accession': a.get('accession') and f'NT {a["accession"]}',
             'descriptionKind': 'From Chesterwood’s Collection page', 'url': SITE + '/the-collection',
             'image': im, 'imageCredit': cr,
             'placeNote': 'In Chesterwood’s collection; where it is shown (Studio, Residence, Barn Gallery or the '
                          'Collections Gallery) isn’t published. Ask at the Visitor Center.'}, None)
    for title, place, dates, words, path in EXHIBITIONS:
        key = f'cw-x-{slugify(title)}'
        im, cr = img(key, path and ('sq', path))
        add({'id': key, 'title': title, 'artist': 'Exhibition', 'date': dates, 'medium': 'Exhibition, 2026 season',
             'description': words, 'descriptionKind': 'From Chesterwood’s exhibitions page',
             'url': SITE + '/upcoming-exhibitions', 'image': im, 'imageCredit': cr,
             'placeNote': f'Shown in the {rooms[place]["name"].split(":")[0].split(" (")[0]} in 2026; the season '
                          'ended October 31. The 2027 shows are not announced yet.'}, None)
    order = {r['id']: i for i, r in enumerate(floors['floors'][0]['rooms'])}
    placed.sort(key=lambda a: (order[a['gallery']], a['artist'] != 'Chesterwood', 'image' not in a))
    return {'source': 'Chesterwood’s Guide to the Studio and website; Wikimedia Commons photos',
            'checked': time.strftime('%Y-%m-%d'), 'count': len(placed), 'complete': False, 'artworks': placed}, unplaced


def build_guide(works, unplaced):
    rows = []
    for a, on in [(a, True) for a in works['artworks']] + [(a, False) for a in unplaced]:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a.get('title') or a['id'], 'artist': a.get('artist'),
                     'date': a.get('date'), 'year': a.get('year'), 'medium': a.get('medium'), 'url': a['url'],
                     'imageUrl': a.get('image'), 'onView': on, 'gallery': a.get('gallery'),
                     'floor': a.get('floor')}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': 'Chesterwood', 'checked': time.strftime('%Y-%m-%d'),
            'source': 'Chesterwood’s Guide to the Studio, Map of the Estate and website; Wikimedia Commons',
            'onViewKnown': True,
            'note': 'Chesterwood was the summer home and studio of Daniel Chester French, sculptor of the Lincoln '
                    'Memorial’s seated Lincoln and the Concord Minute Man. It holds the largest collection of his work '
                    'anywhere: about 500 sculptures, 23 oil paintings and 13 pastels by French. This guide lists '
                    'every piece in the Studio, wall by wall, from Chesterwood’s own Guide to the Studio, plus the '
                    'buildings, gardens and collection highlights from its website. The online collection is not '
                    'public, so the Residence’s contents are not listed one by one. Open May 15 – October 31.',
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
    empty = [r['id'] for r in floors['floors'][0]['rooms'] if r['kind'] == G
             and not any(a['gallery'] == r['id'] for a in works['artworks'])]
    print('places with nothing in them:', empty)


if __name__ == '__main__':
    sys.exit(main())
