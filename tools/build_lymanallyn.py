#!/usr/bin/env python3
"""Build the Lyman Allyn Art Museum (New London, CT) map guide (run: python3 tools/build_lymanallyn.py).

    data/lymanallyn/floors.json     the Lower Level, Main Floor and Upper Floor seen from above (flat 2D)
    data/lymanallyn/artworks.json   the works the museum shows on its gallery pages, in their galleries
    data/lymanallyn/images/         their pictures, made smaller for phones
    data/guides/Q14714982.json      the same plus collection highlights, for the museum page

First run tools/harvest_lymanallyn.py: it reads the museum's gallery and exhibition pages into .cache/lymanallyn.

The map
-------
The Lyman Allyn publishes no floor plan (no PDF, no map on its site; its app is Bloomberg Connects, which robots may
not read). The plan here is APPROXIMATE, drawn inside the building's real outline:
  - OpenStreetMap way 244881161 (ODbL): Charles A. Platt's 1932 granite block, 34 x 16 m (the 108' x 50' of the
    Connecticut Trust's inventory form), facing south, with the portico in the middle, and the later addition to the
    north joined by a narrower link; a notch on the east side of the link is the side porch. The outline is turned
    4.6 degrees so its walls are square; north is up.
  - the museum's own words: the lobby with the front desk (main entrance under the portico); the Hendel Library
    "adjacent to the lobby" and the kitchen; the coat room, the wheelchair-accessible restroom and the family restroom
    with a changing table "on the first floor"; a ramp at the side entrance, by the staff and accessible parking ("ring
    the doorbell"); the Glassenberg Gallery "on the first floor" (the Near::New contemporary shows); the American art
    galleries (Palmer Galleries, American Perspectives) on the first floor near the Hendel Library; the upper floor is
    windowless (top-lit galleries): "three adjacent galleries and the corridor on the second floor", "the 2nd floor
    hallway near the elevator"; the Lehman Auditorium and the Hawthorne dollhouse (Playthings of the Past) "on the
    lower level"; the Tiffany gallery is the Chappell Gallery, 1,070 sq ft.
Which room is where inside each part of the building, and which upstairs gallery holds which show, is our best
reading of those sources; the map and each work say so. Coordinates are metres east/south of the building's south-east
corner area, times K.
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
K = 16          # pixels per metre


def P(x, y):
    """Metres east / south in the building's frame -> map pixels (north up)."""
    return [round((x + 36) * K, 1), round((y + 22) * K, 1)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# The building's outline (OpenStreetMap way 244881161, squared): south block x -31.2..3.1, y 4.5..20.3; portico
# x -19.5..-6.9 to y 23.8; link x -22..-6.3, y 0..4.5; north addition x -23.8..0, y -18.7..0.
HALL = [(-22, 0), (-6.3, 0), (-6.3, 4.5), (3.1, 4.5), (3.1, 7.5), (-31.2, 7.5), (-31.2, 4.5), (-22, 4.5)]
NORTH = rect(-23.8, -18.7, 0, 0)

# ---- Lower Level ---------------------------------------------------------------------------------------------------
# rooms: (id, kind, name, polygon, short label for galleries)
FL = [
    ('Lower Hall', 'corridor', 'Lower Level hall: stairs and elevator', HALL, None),
    ('Lehman Auditorium', 'space', 'Lehman Auditorium (talks, films, student shows)', rect(-31.2, 7.5, -14, 20.3), None),
    ('Playthings of the Past', 'gallery', 'Playthings of the Past: toys, dolls and the Hawthorne dollhouse, with a '
     'hands-on play area for ages 3–10', rect(-14, 7.5, 3.1, 20.3), 'Playthings'),
    ('Art Studio', 'space', 'Art Studio (classes and drop-in art making)', rect(-23.8, -9, -10, 0), None),
]
FL_CLOSED = [rect(-23.8, -18.7, 0, -9), rect(-10, -9, 0, 0)]
FL_DOORS = [('Lower Hall', 'Lehman Auditorium', (-22, 7.5)), ('Lower Hall', 'Playthings of the Past', (-4, 7.5)),
            ('Lower Hall', 'Art Studio', (-16, 0))]
FL_AMEN = [('elevator', -20, 2.2), ('stairs', -9, 6.2)]
FL_LABELS = [('Lower Level (approximate plan)', -12, 26)]
FL_NOTES = []

# ---- Main Floor ----------------------------------------------------------------------------------------------------
F1 = [
    ('Lobby', 'corridor', 'Lobby: front desk (tickets, sketching materials, multilingual family guides, gallery '
     'stools)', [(-15.5, 4.5), (-7, 4.5), (-7, 20.3), (-19.5, 20.3), (-19.5, 8), (-15.5, 8)], None),
    ('Coat Room', 'space', 'Coat room (backpacks and large bags go here; stroller parking)', rect(-19.5, 4.5, -15.5, 8),
     None),
    ('Gallery Hall', 'corridor', 'Hall to the American galleries: elevator and side entrance', rect(-22, 0, -6.3, 4.5),
     None),
    ('Restrooms', 'space', 'Restrooms: wheelchair-accessible restroom and family restroom with changing table '
     '(diapers and wipes)', rect(-25, 4.5, -19.5, 9.5), None),
    ('Hendel Library', 'space', 'Hendel Library (open storage cases with more of the collection; events)',
     rect(-31.2, 9.5, -19.5, 20.3), None),
    ('Glassenberg Gallery', 'gallery', 'Glassenberg Gallery (contemporary shows, Near::New series)',
     rect(-7, 4.5, 3.1, 20.3), 'Glassenberg'),
    ('18th Century', 'gallery', 'American Perspectives: the 18th century (Palmer Galleries)',
     rect(-23.8, -9.5, -12, 0), '18th c.'),
    ('19th Century', 'gallery', 'American Perspectives: the 19th century (Palmer Galleries)',
     rect(-23.8, -18.7, -12, -9.5), '19th c.'),
    ('20th Century', 'gallery', 'American Perspectives: the 20th century (Palmer Galleries)',
     rect(-12, -18.7, 0, -9.5), '20th c.'),
    ('Post-War Art', 'gallery', 'American Perspectives: post-war art (Palmer Galleries)', rect(-12, -9.5, 0, 0),
     'Post-War'),
]
F1_CLOSED = [rect(-31.2, 4.5, -25, 9.5)]
F1_DOORS = [('Lobby', 'Gallery Hall', (-11, 4.5)), ('Lobby', 'Coat Room', (-17.5, 8)), ('Lobby', 'Hendel Library', (-19.5, 15)),
            ('Lobby', 'Glassenberg Gallery', (-7, 13)), ('Gallery Hall', 'Restrooms', (-20.7, 4.5)),
            ('Gallery Hall', '18th Century', (-17, 0)), ('Gallery Hall', 'Post-War Art', (-8.5, 0)),
            ('18th Century', '19th Century', (-18, -9.5)), ('19th Century', '20th Century', (-12, -14)),
            ('20th Century', 'Post-War Art', (-6, -9.5))]
F1_AMEN = [('entrance', -13.2, 19.3), ('entrance', -6.8, 2.2), ('info', -10, 15.5), ('coat', -17.5, 6.2),
           ('restroom', -23.6, 6.5), ('restroom-all', -21, 8.2), ('elevator', -20, 2.2), ('stairs', -9, 6.2)]
F1_LABELS = [('Main entrance under the portico ↓', -13.2, 25.5),
             ('Side entrance (east): ramp by the accessible parking, ring the bell · free parking behind the museum',
              -12, 28)]
F1_NOTES = [('Kitchen (staff)', -28.1, 7)]

# ---- Upper Floor ---------------------------------------------------------------------------------------------------
F2 = [
    ('Upper Hall', 'corridor', 'Upper floor corridor and the hallway by the elevator', HALL, None),
    ('Upper West Gallery', 'gallery', 'Upper West Gallery (special exhibitions)', rect(-31.2, 7.5, -16, 20.3), 'West'),
    ('Upper Center Gallery', 'gallery', 'Upper Center Gallery (special exhibitions)', rect(-16, 7.5, -7, 20.3), 'Center'),
    ('Chappell Gallery', 'gallery', 'Chappell Gallery: Louis Comfort Tiffany in New London', rect(-7, 7.5, 3.1, 20.3),
     'Tiffany'),
]
F2_CLOSED = []
F2_DOORS = [('Upper Hall', 'Upper West Gallery', (-24, 7.5)), ('Upper Hall', 'Upper Center Gallery', (-11.5, 7.5)),
            ('Upper Hall', 'Chappell Gallery', (-2, 7.5)), ('Upper West Gallery', 'Upper Center Gallery', (-16, 14))]
F2_AMEN = [('elevator', -20, 2.2), ('stairs', -9, 6.2)]
F2_LABELS = [('Top-lit galleries, no windows (approximate plan)', -12, 26)]
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
        floor('L', 'Lower Level', 0, 'Playthings of the Past (dollhouse, play area) · Lehman Auditorium · Art Studio',
              FL, FL_CLOSED, FL_DOORS, FL_AMEN, FL_LABELS, FL_NOTES),
        floor('1', 'Main Floor', 1, 'Entrance · Lobby · Coat room · Restrooms · Hendel Library · American Perspectives '
              '· Glassenberg Gallery', F1, F1_CLOSED, F1_DOORS, F1_AMEN, F1_LABELS, F1_NOTES),
        floor('2', 'Upper Floor', 2, 'Special exhibitions · Louis Comfort Tiffany in New London', F2, F2_CLOSED,
              F2_DOORS, F2_AMEN, F2_LABELS, F2_NOTES),
    ]
    for f in floors:
        ids = [r['id'] for r in f['rooms']]
        assert len(ids) == len(set(ids)), f['id']
        for d in f['doors']:
            assert d['a'] in ids and d['b'] in ids, (f['id'], d)
        for a in f['amenities']:
            assert any(inside(a['at'], r['poly']) for r in f['rooms']), (f['id'], a)
    return {'about': 'Built by tools/build_lymanallyn.py. The Lyman Allyn publishes no floor plan: this one is '
                     'approximate, drawn inside the building’s real outline (OpenStreetMap) from the museum’s own '
                     'descriptions of its rooms (lobby, Hendel Library, restrooms and coat room on the first floor, '
                     'top-lit galleries upstairs, auditorium and dollhouse on the lower level).',
            'source': 'Approximate: OpenStreetMap building outline and the Lyman Allyn’s visit, rental and exhibition '
                      'pages',
            'units': 'metres x 16, north up', 'approximate': True, 'defaultFloor': '1', 'galleryWord': 'Gallery',
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
    ('the-land-you-stand', 'Upper West Gallery', 'The Land You Stand On: Contemporary Art of Native and Indigenous '
     'Identity', 'October 10, 2026 – January 24, 2027'),
    ('isaac-sheffield-portraits-from-new-londons-whaling-era', 'Upper Center Gallery',
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
            add(a, 'Upper Center Gallery', True, 'Usually in American Perspectives; the museum’s page for the Isaac '
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
            'Gallery); that it is upstairs is our guess.')
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
