#!/usr/bin/env python3
"""Build the Lyman Allyn Art Museum (New London, CT) map guide (run: python3 tools/build_lymanallyn.py).

    data/lymanallyn/floors.json     the Lower Level, Main Floor and Upper Floor seen from above (flat 2D)
    data/lymanallyn/artworks.json   the works the museum shows on its gallery pages, in their galleries
    data/lymanallyn/images/         their pictures, made smaller for phones
    data/guides/Q14714982.json      the same plus collection highlights, for the museum page

First run tools/harvest_lymanallyn.py: it reads the museum's gallery and exhibition pages into .cache/lymanallyn.

The map
-------
The rooms are traced from the museum's own floor plans in its Bloomberg Connects guide (read in the app on
Nov 11 2026; the three levels share one picture frame, so P() serves them all). Run with --floors-only to redraw the
map and move the saved works onto it without the harvest cache. Which room of the Palmer Galleries holds which century,
and which upstairs gallery holds which show, is still our guess, and each work says so.
"""
import html
import io
import json
import re
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harvest_lymanallyn import CACHE, get  # noqa: E402  (cached, polite fetch)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'lymanallyn'
MUSEUM = 'Q14714982'
NAME = 'Lyman Allyn Art Museum'
SITE = 'https://www.lymanallyn.org'
SOURCE = 'Lyman Allyn Art Museum: gallery and exhibition pages (lymanallyn.org); approximate plan'
def P(x, y):
    """Pixels of the museum's own floor-plan pictures (all three levels share one frame; north up) -> map units."""
    return [round(x * 0.75, 1), round(y * 0.75, 1)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


ELEVATOR = rect(545, 595, 640, 662)
STAIRS = rect(535, 665, 660, 812)

# ---- Lower Level ---------------------------------------------------------------------------------------------------
# rooms: (id, kind, name, polygon, short label for galleries)
FL = [
    ('Lower Hall', 'corridor', 'Lower Level hall', rect(465, 460, 545, 665), None),
    ('Restrooms L', 'space', 'Restrooms', rect(548, 462, 688, 545), None),
    ('Elevator L', 'corridor', 'Elevator', ELEVATOR, None),
    ('Stairs L', 'corridor', 'Stairs', rect(530, 665, 660, 915), None),
    ('Playthings of the Past', 'gallery', 'Playthings of the Past: the Hawthorne dollhouse, in the Lower Level hall',
     [(465, 665), (530, 665), (530, 915), (660, 915), (660, 1045), (410, 1045), (410, 915), (465, 915)], 'Playthings'),
    ('Lehman Auditorium', 'space', 'Lehman Auditorium (talks, films, student shows)', rect(678, 675, 945, 1045), None),
]
FL_CLOSED = [rect(218, 75, 797, 445), rect(70, 462, 452, 1045)]
FL_DOORS = [('Lower Hall', 'Restrooms L', (546, 500)), ('Lower Hall', 'Elevator L', (545, 628)),
            ('Lower Hall', 'Playthings of the Past', (497, 665)), ('Playthings of the Past', 'Stairs L', (530, 790)),
            ('Playthings of the Past', 'Stairs L', (595, 915)), ('Stairs L', 'Lehman Auditorium', (670, 860))]
FL_AMEN = [('elevator', 592, 628), ('stairs', 595, 740), ('restroom', 620, 500)]
FL_LABELS = []
FL_NOTES = []

# ---- First Level ---------------------------------------------------------------------------------------------------
F1 = [
    ('19th Century', 'gallery', 'Palmer Galleries: American Perspectives, the 19th century', rect(218, 75, 400, 235),
     '19th c.'),
    ('18th Century', 'gallery', 'Palmer Galleries: American Perspectives, the 18th century', rect(218, 235, 400, 395),
     '18th c.'),
    ('Palmer Center', 'gallery', 'Palmer Galleries (centre)', rect(415, 75, 600, 395), 'Palmer Galleries'),
    ('20th Century', 'gallery', 'Palmer Galleries: American Perspectives, the 20th century', rect(615, 75, 795, 225),
     '20th c.'),
    ('Post-War Art', 'gallery', 'Palmer Galleries: American Perspectives, post-war art', rect(615, 225, 795, 395),
     'Post-War'),
    ('Gallery Hall', 'corridor', 'Hall to the Palmer Galleries', rect(470, 395, 545, 670), None),
    ('Restrooms', 'space', 'Restroom (wheelchair-accessible)', rect(548, 465, 695, 545), None),
    ('Elevator 1', 'corridor', 'Elevator', ELEVATOR, None),
    ('Coat Room', 'space', 'Coat room (backpacks and large bags; stroller parking)', rect(415, 670, 465, 805), None),
    ('Stairs 1', 'corridor', 'Stairs', STAIRS, None),
    ('Family Restrooms', 'space', 'Restrooms (family restroom with changing table)', rect(668, 670, 740, 735), None),
    ('Lobby', 'corridor', 'Lobby: front desk',
     [(465, 670), (470, 670), (470, 812), (745, 812), (745, 905), (540, 905), (540, 1060), (470, 1060), (470, 905),
      (270, 905), (270, 812), (465, 812)], None),
    ('Hendel Library', 'space', 'Hendel Library', rect(65, 665, 270, 1050), None),
    ('Glassenberg Gallery', 'gallery', 'Glassenberg Gallery (contemporary shows, Near::New series)',
     rect(750, 670, 945, 912), 'Glassenberg'),
]
F1_CLOSED = []
F1_DOORS = [('Gallery Hall', 'Palmer Center', (507, 395)), ('Palmer Center', '18th Century', (408, 365)),
            ('Palmer Center', '19th Century', (408, 120)), ('Palmer Center', '20th Century', (608, 120)),
            ('Palmer Center', 'Post-War Art', (608, 365)), ('18th Century', '19th Century', (250, 235)),
            ('20th Century', 'Post-War Art', (760, 225)), ('Gallery Hall', 'Restrooms', (545, 500)),
            ('Gallery Hall', 'Elevator 1', (545, 628)), ('Gallery Hall', 'Lobby', (507, 670)),
            ('Lobby', 'Coat Room', (467, 760)), ('Lobby', 'Stairs 1', (597, 812)),
            ('Lobby', 'Family Restrooms', (705, 812)), ('Lobby', 'Hendel Library', (270, 860)),
            ('Lobby', 'Glassenberg Gallery', (747, 860))]
F1_AMEN = [('entrance', 505, 1055), ('info', 505, 950), ('coat', 440, 740), ('restroom', 620, 500),
           ('restroom-all', 705, 705), ('elevator', 592, 628), ('stairs', 597, 740)]
F1_LABELS = [('Main entrance under the portico ↓', 505, 1090)]
F1_NOTES = []

# ---- Second Level ----------------------------------------------------------------------------------------------------
F2 = [
    ('Art Studio', 'space', 'Art Studio (classes and drop-in art making)', rect(218, 75, 530, 452), None),
    ('Stamm North Gallery', 'gallery', 'Stamm North Gallery', rect(320, 460, 460, 660), 'Stamm North'),
    ('McDannel Gallery', 'gallery', 'McDannel Gallery', rect(545, 460, 690, 595), 'McDannel'),
    ('Elevator 2', 'corridor', 'Elevator', ELEVATOR, None),
    ('Stairs 2', 'corridor', 'Stairs', STAIRS, None),
    ('Upper Hall', 'corridor', 'Upper corridor',
     [(460, 455), (545, 455), (545, 660), (535, 660), (535, 815), (745, 815), (745, 880), (270, 880), (270, 815),
      (460, 815)], None),
    ('Stamm South Gallery', 'gallery', 'Stamm South Gallery', rect(285, 665, 460, 812), 'Stamm South'),
    ('McKee Gallery', 'gallery', 'McKee Gallery', rect(65, 670, 265, 1045), 'McKee'),
    ('Hazlewood Gallery', 'gallery', 'Hazlewood Gallery', rect(285, 882, 400, 1045), 'Hazlewood'),
    ('Powers Gallery', 'gallery', 'Powers Gallery', rect(405, 882, 615, 1045), 'Powers'),
    ('Miles Gallery', 'gallery', 'Miles Gallery', rect(620, 882, 735, 1045), 'Miles'),
    ('Chappell Gallery', 'gallery', 'Chappell Gallery: Louis Comfort Tiffany in New London', rect(750, 670, 945, 1045),
     'Chappell (Tiffany)'),
]
F2_CLOSED = []
F2_DOORS = [('Upper Hall', 'Art Studio', (500, 452)), ('Upper Hall', 'Stamm North Gallery', (460, 600)),
            ('Upper Hall', 'McDannel Gallery', (545, 480)), ('Upper Hall', 'Elevator 2', (545, 628)),
            ('Stamm North Gallery', 'Stamm South Gallery', (350, 662)), ('Upper Hall', 'Stamm South Gallery', (460, 790)),
            ('Upper Hall', 'Stairs 2', (597, 815)), ('Upper Hall', 'McKee Gallery', (267, 850)),
            ('Upper Hall', 'Hazlewood Gallery', (440, 880)), ('Upper Hall', 'Powers Gallery', (505, 880)),
            ('Upper Hall', 'Miles Gallery', (705, 880)), ('Upper Hall', 'Chappell Gallery', (747, 850))]
F2_AMEN = [('elevator', 592, 628), ('stairs', 597, 740)]
F2_LABELS = [('Top-lit galleries, no windows', 600, 1090)]
F2_NOTES = []

def inside(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def floor(fid, label, order, area, rooms, closed, doors, amen, labels, notes):
    rr = []
    for rid, kind, name, poly, short in rooms:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': [P(*q) for q in poly]}
        if kind == 'gallery': r['label'] = short
        rr.append(r)
    return {'id': fid, 'label': label, 'order': order, 'transform': [1, 0, 0], 'area': area, 'rooms': rr,
            'closed': [{'poly': [P(*q) for q in c]} for c in closed],
            'amenities': [{'type': t, 'at': P(x, y)} for t, x, y in amen],
            'labels': [{'text': t, 'kind': 'note', 'at': P(x, y)} for t, x, y in labels],
            'notes': [{'text': t, 'kind': 'note', 'at': P(x, y)} for t, x, y in notes],
            'doors': [{'a': a, 'b': b, 'at': P(*p), 'width': 16, 'axis': 'o'} for a, b, p in doors]}


def build_floors():
    floors = [
        floor('L', 'Lower Level', 0, 'Playthings of the Past (the dollhouse) · Lehman Auditorium · Restrooms',
              FL, FL_CLOSED, FL_DOORS, FL_AMEN, FL_LABELS, FL_NOTES),
        floor('1', 'First Level', 1, 'Entrance · Lobby · Coat room · Restrooms · Hendel Library · Palmer Galleries '
              '(American Perspectives) · Glassenberg Gallery', F1, F1_CLOSED, F1_DOORS, F1_AMEN, F1_LABELS, F1_NOTES),
        floor('2', 'Second Level', 2, 'Special exhibitions (McKee, Stamm, McDannel, Hazlewood, Powers and Miles '
              'Galleries) · Louis Comfort Tiffany (Chappell Gallery) · Art Studio', F2, F2_CLOSED, F2_DOORS, F2_AMEN,
              F2_LABELS, F2_NOTES),
    ]
    for f in floors:
        ids = [r['id'] for r in f['rooms']]
        assert len(ids) == len(set(ids)), f['id']
        for d in f['doors']:
            assert d['a'] in ids and d['b'] in ids, (f['id'], d)
        for a in f['amenities']:
            assert any(inside(a['at'], r['poly']) for r in f['rooms']), (f['id'], a)
    return {'about': 'Built by tools/build_lymanallyn.py. Rooms traced from the Lyman Allyn’s own floor plans in its '
                     'Bloomberg Connects guide (Nov 2026).',
            'source': 'Lyman Allyn floor plans in its Bloomberg Connects guide (Nov 2026)',
            'units': 'plan pixels x 0.75, north up', 'defaultFloor': '1', 'galleryWord': 'Gallery',
            'floors': floors}


# ---- works ---------------------------------------------------------------------------------------------------------

def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:60]


def picture(key, url):
    if not url: return None
    dest = OUT / 'images' / f'{key}.jpg'
    if dest.exists(): return f'data/lymanallyn/images/{key}.jpg'
    raw = get(url, CACHE / 'img' / f'{key}.bin', delay=1.5)
    if not raw: return None
    try:
        im = Image.open(io.BytesIO(raw))
    except Exception:
        (CACHE / 'img' / f'{key}.bin').unlink()
        return None
    im = im.convert('RGB')
    im.thumbnail((1000, 1000))
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/lymanallyn/images/{key}.jpg'


def page(slug_):
    return (CACHE / 'pages' / f'{slug_}.html').read_text(errors='replace')


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(s)).strip()


DATEISH = re.compile(r'^(?:about |ca\. ?|c\. ?|probably |late|early|mid|after |before |by |installed |no date|'
                     r'\d{4}|\d{3}0s|\d{1,2}th)', re.I)
MAKER = re.compile(r'\(.*\d|^(?:Unknown (?:maker|artist)|Workshop of|Attributed to|School of)|'
                   r'Company|Pottery|Studios|Glass Works|Works\b|Gillinder|Trott and', re.I)
ACC = re.compile(r'\b((?:19|20)\d{2}\.\d+(?:\.\d+)*(?:\s?[a-j](?:[-,]\s?[a-j])?\b)?)')


def parse_caption(cap):
    """'Artist (Nationality, dates), Title, date, medium. Credit, acc.'  or  'Title, date, Maker, medium. Credit, acc.'"""
    cap = clean(cap)
    accs = ACC.findall(cap)
    acc = accs[-1].strip() if accs else None
    m = re.match(r'^([^,(]{3,60}?)\s*,?\s*\(([^)]*)\)\s*,\s*(.*)$', cap)
    if m and re.search(r'\d|active|born', m.group(2)):
        artist, life, rest = m.group(1).strip(), m.group(2), m.group(3)
        if rest.lower().startswith('attributed,'):
            artist += ' (attributed)'
            rest = rest.split(',', 1)[1].strip()
        parts = [p.strip() for p in rest.split(',')]
        title = []
        for p in parts:
            if title and DATEISH.match(p): break
            title.append(p)
        title = ', '.join(title)
        date = parts[len(title.split(', '))] if len(parts) > len(title.split(', ')) else ''
        if title.startswith('Bust of the Fisherboy'): title = 'Bust of the Fisherboy'
        if len(title) > 110: title = title[:title.rfind(' ', 0, 100)] + '…'
        return fix({'title': title.rstrip('.'), 'artist': artist, 'life': life, 'date': date.split(';')[0].rstrip('.'),
                    'accession': acc, 'parts': []}, cap)
    parts = [p.strip() for p in re.split(r',(?![^(]*\))', cap)]
    title = parts[0].rstrip('.')
    date = next((re.match(r'^((?:ca\. ?|c\. ?)?[^.]*)', q).group(1) for q in parts[1:3] if DATEISH.match(q)), '')
    artist = next((p for p in parts[1:] if MAKER.search(p) and not p.startswith('Gift')), '')
    if title == 'Vase' and len(parts) > 2 and not DATEISH.match(parts[1]):
        title, date = f'Vase, {parts[1]}', parts[2]
    if not artist and date and len(parts) > 2 and parts[2][:1].isupper():
        artist = parts[2]
    artist = re.sub(r'\s*\(.*', '', artist).strip().rstrip('.') or 'Unknown maker'
    return fix({'title': title, 'artist': artist, 'date': date, 'accession': acc, 'parts': parts}, cap)


# Captions the two patterns above read wrongly
FIX = {
    'Whale Oil Lamp': {'artist': 'Boston and Sandwich Glass Works'},
    'Norwich, CT, Risley Pottery, Norwich': {'title': 'Risley Pottery, Norwich', 'artist': 'Unknown artist'},
    'Cordial Set': {'artist': 'Tiffany Studios'},
    'Pierre Auguste Renoir': {'title': 'Maternity: Madame Renoir and Son', 'artist': 'Pierre Auguste Renoir',
                              'date': '1916'},
    'W. Langhine': {'title': 'President Abraham Lincoln', 'artist': 'W. Langhine'},
    'John Ewen': {'title': 'View of the ship Alert of New London (fore and aft)', 'artist': 'John Ewen, Jr.',
                  'date': '1845'},
}
CULTURE = re.compile(r'^(African|Egyptian|Japanese|Greek|Samoan|[A-Z][a-z]+ [Pp]eople)$')


def fix(p, cap):
    if p['title'] in FIX: p.update(FIX[p['title']])
    if p['artist'] == 'Unknown maker' and len(p['parts']) > 1 and CULTURE.match(p['parts'][1]):
        p['artist'] = p['parts'][1].replace(' people', ' People')
    p.pop('parts', None)
    return p


def gallery_captions(slug_):
    """(section heading, caption, full-size picture url) for each captioned picture on a page, in order."""
    t = page(slug_)
    ev = [(m.start(), 'H', clean(re.sub('<[^>]+>', '', m.group(1)))) for m in re.finditer(r'<h[23][^>]*>(.*?)</h[23]>', t, re.S)]
    ev += [(m.start(), 'C', (m.group(1), m.group(2)))
           for m in re.finditer(r'<a [^>]*data-caption="([^"]*)"[^>]*href="([^"]+)"', t)]
    ev.sort()
    out, head, seen = [], None, set()
    for _, k, v in ev:
        if k == 'H':
            head = v
            continue
        cap, href = clean(v[0]), v[1]
        if not cap or cap.lower().startswith('alternate view') or href in seen: continue
        seen.add(href)
        out.append((head, cap, href))
    return out


AP_ROOM = {'The 18th Century': '18th Century', 'The 19th Century': '19th Century',
           'The 20th Century': '20th Century', 'Post-War Art': 'Post-War Art'}
AP_NOTE = ('American Perspectives is on the first floor (the museum’s Palmer Galleries); which of its rooms holds each '
           'century is our guess from the order of the museum’s gallery page.')
# Shows on view now (Nov 2026): slug -> (room, title, dates, which upstairs/downstairs room is a guess)
SHOWS = [
    ('the-land-you-stand', 'McKee Gallery', 'The Land You Stand On: Contemporary Art of Native and Indigenous '
     'Identity', 'October 10, 2026 – January 24, 2027'),
    ('isaac-sheffield-portraits-from-new-londons-whaling-era', 'Stamm South Gallery',
     'Isaac Sheffield: Portraits from New London’s Whaling Era', 'September 12, 2026 – January 3, 2027'),
    ('lydia-viscardi-time-takes-time', 'Glassenberg Gallery', 'Lydia Viscardi – Time Takes Time',
     'October 31, 2026 – January 10, 2027'),
]
SHOW_NOTE = ('A show on view now; the museum doesn’t say which gallery, so this room is our guess (the big shows are '
             'usually upstairs, the contemporary Near::New shows in the Glassenberg Gallery).')
# Works in American Perspectives that the Isaac Sheffield show features (its page shows this portrait)
TO_SHEFFIELD = {'1964.246'}


def page_text(slug_, n=1500):
    t = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', page(slug_), flags=re.S)
    m = re.search(r'<main.*?</main>', t, re.S) or re.search(r'<body.*', t, re.S)
    s = clean(re.sub(r'<[^>]+>', ' ', m.group(0)))
    s = re.sub(r'\s*(Opening Reception|Members Free|RSVP to).*$', '', s)
    return s[:n]


def main_images(slug_):
    t = page(slug_)
    m = re.search(r'<main.*?</main>', t, re.S) or re.search(r'<body.*', t, re.S)
    return [u for u in dict.fromkeys(re.findall(r'<img [^>]*src="([^"]+)"', m.group(0)))
            if '/uploads/20' in u and not re.search(r'logo|foundation', u, re.I)]


def full_size(url):
    return re.sub(r'-\d+x\d+(\.\w+)$', r'\1', url)


MOVED = {'Upper West Gallery': 'McKee Gallery', 'Upper Center Gallery': 'Stamm South Gallery'}   # earlier map


def floors_only(floors):
    """Move the saved works onto the redrawn map (no harvest cache needed)."""
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    path = OUT / 'artworks.json'
    works = json.loads(path.read_text())
    for a in works['artworks']:
        g = MOVED.get(a['gallery'], a['gallery'])
        a['gallery'], (a['floor'], a['galleryName']) = g, rooms[g]
        if g == 'Chappell Gallery': a['placeNote'] = 'In the permanent Louis Comfort Tiffany in New London gallery (the Chappell Gallery, upstairs).'
        if g == 'Playthings of the Past': a.pop('placeGuessed', None)
    path.write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    gpath = ROOT / 'data' / 'guides' / f'{MUSEUM}.json'
    guide = json.loads(gpath.read_text())
    for w in guide['works']:
        if w.get('gallery'): w['gallery'] = MOVED.get(w['gallery'], w['gallery']); w['floor'] = rooms[w['gallery']][0]
    gpath.write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    works, seen, extra = [], set(), []

    def add(a, room, guessed, note):
        fl, gname = rooms[room]
        a.update({'gallery': room, 'galleryName': gname, 'floor': fl, 'placeNote': note})
        if guessed: a['placeGuessed'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '', [])})

    def work(cap, href, url, prefix):
        p = parse_caption(cap)
        key = f"{prefix}-{slug(p['accession'] or p['title'])}"
        if key in seen: return None, p
        seen.add(key)
        a = {'id': key, 'title': p['title'], 'artist': p['artist'], 'date': p.get('date'),
             'accession': p['accession'], 'description': cap, 'url': url, 'image': picture(key, href)}
        if a['image']: a['imageCredit'] = 'Lyman Allyn Art Museum (lymanallyn.org)'
        return a, p

    # exhibitions on view now: one card each
    for s, room, title, dates in SHOWS:
        imgs = main_images(s)
        text = page_text(s)
        text = text[len(title):].strip() if text.startswith(title[:20]) else text
        a = {'id': f'la-show-{slug(title)[:40]}', 'title': title, 'artist': 'Exhibition', 'date': dates,
             'description': text, 'url': f'{SITE}/{s}/', 'temporary': True,
             'image': picture(f'la-show-{slug(title)[:40]}', full_size(imgs[0]) if imgs else None)}
        if a['image']: a['imageCredit'] = 'Lyman Allyn Art Museum (lymanallyn.org)'
        add(a, room, True, SHOW_NOTE)
    # American Perspectives, by century
    for head, cap, href in gallery_captions('american-perspectives'):
        if head not in AP_ROOM: continue
        a, p = work(cap, href, f'{SITE}/american-perspectives/', 'la')
        if not a: continue
        if p['accession'] in TO_SHEFFIELD:
            add(a, 'Stamm South Gallery', True, 'Usually in American Perspectives; the museum’s page for the Isaac '
                'Sheffield show (to January 3, 2027) features it, so it is probably in that show now.')
        else:
            add(a, AP_ROOM[head], True, AP_NOTE)
    # Tiffany gallery
    for head, cap, href in gallery_captions('louis-comfort-tiffany-in-new-london'):
        if cap.startswith('Louis Comfort Tiffany, ca.'): continue      # a lent photograph of the artist
        a, p = work(cap, href, f'{SITE}/louis-comfort-tiffany-in-new-london/', 'la')
        if not a: continue
        if not p['artist'] or p['artist'] == 'Unknown maker': a['artist'] = 'Tiffany Studios'
        if 'Tiffany & Company' in cap: a['artist'] = 'Tiffany & Company'
        if 'Long-term loan' in cap: a['loan'] = True
        add(a, 'Chappell Gallery', True, 'In the permanent Louis Comfort Tiffany in New London gallery (the Chappell '
            'Gallery, upstairs).')
    # Playthings of the Past: the dollhouse
    imgs = main_images('playthings-of-the-past')
    doll = next((u for u in imgs if 'Dollhouse' in u), None)
    a = {'id': 'la-1962-47', 'title': 'American Victorian Dollhouse', 'artist': 'Harold Hawthorne', 'date': '1962',
         'accession': '1962.47', 'description': 'American Victorian Dollhouse, 1962, Harold Hawthorne, wood. Museum '
         'purchase, 1962.47. Built for the museum to house the Baratz collection of dolls and doll furniture: three '
         'floors with bedrooms, a dining room, a nursery, a sewing room and two kitchens, under a mansard roof with a '
         'widow’s walk.', 'url': f'{SITE}/playthings-of-the-past/',
         'image': picture('la-1962-47', full_size(doll) if doll else None)}
    if a['image']: a['imageCredit'] = 'Lyman Allyn Art Museum (lymanallyn.org)'
    add(a, 'Playthings of the Past', False, 'On the lower level, where the museum put it back in 2014.')
    # collection highlights (the museum doesn't say whether these are on view)
    for head, cap, href in gallery_captions('about-the-collection'):
        p = parse_caption(cap)
        key = f"la-{slug(p['accession'] or p['title'])}"
        if key in seen: continue
        seen.add(key)
        extra.append({'id': key, 'title': p['title'], 'artist': p['artist'], 'medium': p['accession'],
                      'url': f'{SITE}/about-the-collection/', 'imageUrl': picture(key, href), 'onView': False})
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    works.sort(key=lambda a: (forder[a['floor']], order[a['gallery']], a['artist'] != 'Exhibition'))
    return {'source': SOURCE, 'checked': time.strftime('%Y-%m-%d'), 'count': len(works), 'complete': False,
            'artworks': works}, extra


def build_guide(works, extra):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'],
                     'date': a.get('date'), 'medium': a.get('accession'), 'url': a['url'], 'imageUrl': a.get('image'),
                     'onView': True, 'gallery': a['gallery'], 'floor': a['floor']}.items() if v not in (None, '')})
    rows += [{k: v for k, v in r.items() if v not in (None, '')} for r in extra]
    return {'museum': MUSEUM, 'name': NAME, 'checked': time.strftime('%Y-%m-%d'), 'source': SOURCE, 'onViewKnown': True,
            'note': 'The Lyman Allyn has more than 20,000 works; its online catalogue can’t be read by this guide and '
                    'doesn’t say what is on view. Listed here are the works the museum shows on its gallery pages '
                    '(American Perspectives, the Tiffany gallery, Playthings of the Past) and the shows open now, in '
                    'the rooms of an approximate plan, plus a few collection highlights that may be in storage.',
            'works': rows}


def main():
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    if sys.argv[1:2] == ['--floors-only']: return floors_only(floors)
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
    print(f'{works["count"]} works on the map ({sum("image" in a for a in works["artworks"])} with pictures), '
          f'{len(extra)} more in the collection list')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
