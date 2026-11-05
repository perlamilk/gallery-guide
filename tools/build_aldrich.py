#!/usr/bin/env python3
"""Build The Aldrich Contemporary Art Museum (Ridgefield, CT) map guide (run: python3 tools/build_aldrich.py).

    data/aldrich/floors.json     the grounds and Sculpture Garden, the First and the Second Floor, seen from above
    data/aldrich/artworks.json   the works on view now (The Aldrich Decennial, inside and in the Sculpture Garden)
    data/aldrich/images/         their pictures, made smaller for phones
    data/guides/Q4713992.json    the same, for the museum page

First run tools/harvest_aldrich.py: it reads the museum's visit, exhibition and Sculpture Garden pages into
.cache/aldrich.

The map
-------
GROUNDS: traced from The Aldrich's own Sculpture Garden map ("Aldrich-Sculpture-Garden-Plan-Decennial.jpg" on
thealdrich.org/page/sculpture-garden, the landscape plan of STIMSON's 2024 renovation with the ten works outside
numbered). Units are pixels of that 2000 px image times 0.3; it is drawn about north up, Main Street on the left (west),
the parking lot to the north, Old Hundred (the 1783 house, now offices) by Main Street, the terraced steps up to the
museum's west door, the interior courtyard, the amphitheater and the paths of the garden to the east. About 10.5 image
pixels make a metre (checked against the OpenStreetMap outline, way 216577708, and Esri aerial photos).

INSIDE: the museum publishes no floor plan. The outline is the one on the garden map; the rooms are APPROXIMATE, placed
from the museum's own words: the visitor social narrative (2023) "the Front Desk to the left" as you come in; restrooms
"behind the Front Desk on the first floor"; "on the first floor, the Leir Gallery, Klein Kenealy Gallery, and Project
Space; on the second floor, the Balcony Gallery, South Gallery, Sound Gallery, and Opatrny Gallery"; "the steps in the
Leir Atrium or the elevator"; the Sculpture Garden "through the front or back doors"; the 52 Artists checklists (2022)
name the Lobby and Sloped Corridor, the Bridge and the Opatrny vestibule too; the 2004 opening articles: the two-story
Project Space with its east wall left open to the garden, the Leir Gallery for performances (100+ seats), the education
center (The Studio) open to the lobby and the outdoors, and visitors going "upstairs from the Leir Atrium" and
"clockwise around the galleries of the second floor". Which room is where inside the outline is our best reading; the
map says so. Building coordinates are metres east/south of the gallery building's north-west corner, times KB.
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
from harvest_aldrich import CACHE, get, page_path  # noqa: E402  (cached, polite fetch)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'aldrich'
MUSEUM = 'Q4713992'
NAME = 'The Aldrich Contemporary Art Museum'
SITE = 'https://thealdrich.org'
SOURCE = 'The Aldrich: Sculpture Garden map and exhibition pages (thealdrich.org); approximate floor plans'
DECENNIAL = f'{SITE}/exhibitions/the-aldrich-decennial-new-art-made-in-connecticut'
GARDEN = f'{SITE}/page/sculpture-garden'
SHOW = 'The Aldrich Decennial: I am what is around me'
SHOW_DATES = 'June 7, 2026 – January 10, 2027'
IMG = SITE + '/client-uploads/images-general/_aldrich_image_2000px_w/'

KG = 0.3              # grounds: map units per pixel of the museum's garden map
PXM = 10.5            # garden-map pixels per metre
KB = 24              # building floors: map units per metre
BX, BY = 673, 695     # the gallery building's north-west corner on the garden map


def G(x, y):
    """Garden-map pixels -> grounds map units."""
    return [round(x * KG, 1), round(y * KG, 1)]


def B(x, y):
    """Metres east / south of the building's north-west corner -> building map units."""
    return [round((x + 6) * KB, 1), round((y + 4) * KB, 1)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# The building's outline in metres (the garden map: west block, north wing, courtyard, south wing, entrance annex)
OUTLINE = [(0, 0), (35, 0), (35, 7.1), (20, 7.1), (20, 15.2), (39.5, 15.2), (39.5, 17.6), (48, 17.6), (48, 25.2),
           (-3.1, 25.2), (-3.1, 17.6), (0, 17.6)]
# the same, on the garden map
OUTLINE_PX = [(BX + x * PXM, BY + y * PXM) for x, y in OUTLINE]

# ---- Grounds & Sculpture Garden (garden-map pixels) -----------------------------------------------------------------
# rooms: (id, kind, name, polygon, short label for galleries)
GR = [
    ('Main Street Sidewalk', 'corridor', 'Main Street sidewalk (the museum is at 258 Main Street)', rect(0, 600, 40, 1129),
     None),
    ('Front Lawn', 'gallery', 'Front Lawn on Main Street (the Main Street Sculpture)', [
        (40, 660), (300, 660), (300, 690), (400, 690), (400, 840), (115, 840), (115, 1000), (40, 1000)], 'Front Lawn'),
    ('Old Hundred', 'space', 'Old Hundred, the 1783 house where Larry Aldrich opened the museum in 1964 (offices, '
     'not open to visitors)', rect(115, 840, 400, 1000), None),
    ('Front Terrace', 'gallery', 'Front Terrace: the terraced steps from Main Street up to the museum’s front door',
     [(300, 690), (300, 660), (640, 660), (665, 690), (665, 880), (640, 880), (640, 960), (400, 960), (400, 690)],
     'Terrace'),
    ('Drive', 'corridor', 'Driveway from Main Street to the parking lot, with the Pollinator Walkway beside it',
     [(0, 590), (580, 590), (640, 560), (640, 660), (300, 660), (0, 660)], None),
    ('Accessible Parking', 'space', 'Accessible parking spaces by the drive', rect(300, 490, 580, 590), None),
    ('Parking Lot', 'space', 'Parking lot (free for visitors)', rect(580, 30, 1265, 560), None),
    ('Garden Walk', 'corridor', 'Path along the north side of the museum, from the parking lot to the garden, with the '
     'new accessible ramp', [(640, 560), (1265, 560), (1265, 600), (1180, 700), (1090, 700), (1040, 695), (665, 690),
                             (640, 660)], None),
    ('Museum', 'space', 'The museum building (galleries on the First and Second Floor)', OUTLINE_PX, None),
    ('Amphitheater', 'gallery', 'The amphitheater: grass terraces stepping down from the museum to the garden',
     [(1090, 700), (1180, 700), (1600, 690), (1600, 870), (1190, 880), (1180, 880), (1090, 855)], 'Amphitheater'),
    ('South Lawn', 'gallery', 'South Lawn, behind the museum’s back doors', [
        (1180, 880), (1190, 880), (1600, 870), (1700, 1000), (1180, 990)], 'South Lawn'),
    ('Upper Garden', 'gallery', 'Upper Garden: the big lawn and meadow paths, with the Secret Garden in its north-west '
     'corner', [(1265, 70), (1700, 60), (1900, 250), (1920, 560), (1600, 690), (1180, 700), (1265, 600)],
     'Upper Garden'),
    ('East Lawn', 'gallery', 'East Lawn, at the far end of the garden loop', [
        (1920, 560), (1960, 900), (1800, 1000), (1700, 1000), (1600, 870), (1600, 690)], 'East Lawn'),
]
GR_CLOSED = [rect(290, 270, 560, 420)]           # the neighbouring church (First Church of Christ, Scientist)
GR_DOORS = [('Main Street Sidewalk', 'Front Lawn', (40, 750)), ('Main Street Sidewalk', 'Drive', (40, 625)),
            ('Front Lawn', 'Front Terrace', (400, 800)), ('Drive', 'Front Terrace', (450, 660)),
            ('Drive', 'Accessible Parking', (440, 590)), ('Drive', 'Parking Lot', (610, 575)),
            ('Drive', 'Garden Walk', (640, 610)), ('Parking Lot', 'Garden Walk', (900, 560)),
            ('Front Terrace', 'Museum', (665, 865)), ('Garden Walk', 'Amphitheater', (1135, 700)),
            ('Garden Walk', 'Upper Garden', (1230, 640)), ('Amphitheater', 'Upper Garden', (1400, 695)),
            ('Amphitheater', 'South Lawn', (1400, 875)), ('Amphitheater', 'East Lawn', (1600, 780)),
            ('South Lawn', 'East Lawn', (1650, 935)), ('Upper Garden', 'East Lawn', (1760, 625)),
            ('Museum', 'South Lawn', (1182, 905))]
GR_AMEN = [('entrance', 650, 870), ('entrance', 1190, 905)]
GR_LABELS = [('Main Street', 20, 1080), ('Front door at the top of the terraced steps', 520, 1000),
             ('Back doors to the garden', 1300, 1040), ('Sculpture Garden: open dawn to dusk, free', 1600, 30),
             ('Secret Garden', 1380, 150), ('Church (not the museum)', 425, 345)]
GR_NOTES = []

# ---- First Floor (metres) -------------------------------------------------------------------------------------------
F1 = [
    ('Leir Atrium', 'corridor', 'Leir Atrium, the lobby: Front Desk (tickets) on your left as you come in, the stairs '
     'up and the way to every gallery', [(-3.1, 17.6), (0, 17.6), (0, 10), (20, 10), (20, 25.2), (7, 25.2), (7, 21),
                                         (0, 21), (0, 25.2), (-3.1, 25.2)], None),
    ('The Shop', 'space', 'The Shop: artist editions, books and gifts (members 10% off)', rect(0, 21, 7, 25.2), None),
    ('Restrooms', 'space', 'Restrooms behind the Front Desk (accessible stalls with changing stations)',
     rect(0, 6, 6, 10), None),
    ('Klein Kenealy Gallery', 'gallery', 'Klein Kenealy Gallery', [(0, 0), (13, 0), (13, 10), (6, 10), (6, 6), (0, 6)],
     'Klein K.'),
    ('Elevator Hall', 'corridor', 'Hall with the elevator, to The Studio and the Sloped Corridor', rect(13, 0, 20, 10),
     None),
    ('The Studio', 'space', 'The Studio: drop-in art making for all ages, with materials on the tables (when open)',
     rect(20, 0, 35, 7.1), None),
    ('Sloped Corridor', 'corridor', 'Sloped Corridor beside the courtyard, down to the Leir Gallery', rect(20, 7.1, 23, 15.2),
     None),
    ('Courtyard', 'gallery', 'Interior Courtyard (open air)', rect(23, 7.1, 39.5, 15.2), 'Courtyard'),
    ('Leir Gallery', 'gallery', 'Leir Gallery: the tall main gallery, also used for talks and performances',
     rect(20, 15.2, 36, 25.2), 'Leir'),
    ('Project Space', 'gallery', 'Project Space: two stories high, its east wall glass onto the Sculpture Garden; the '
     'back doors to the garden', [(36, 15.2), (39.5, 15.2), (39.5, 17.6), (48, 17.6), (48, 25.2), (36, 25.2)],
     'Project'),
]
F1_CLOSED = []
F1_DOORS = [('Leir Atrium', 'The Shop', (7, 23)), ('Leir Atrium', 'Restrooms', (3, 10)),
            ('Leir Atrium', 'Elevator Hall', (16.5, 10)), ('Elevator Hall', 'Klein Kenealy Gallery', (13, 4)),
            ('Elevator Hall', 'The Studio', (20, 3.5)), ('Elevator Hall', 'Sloped Corridor', (20, 8.5)),
            ('Leir Atrium', 'Leir Gallery', (20, 20)), ('Sloped Corridor', 'Leir Gallery', (21.5, 15.2)),
            ('Sloped Corridor', 'Courtyard', (23, 11)), ('The Studio', 'Courtyard', (28, 7.1)),
            ('Leir Gallery', 'Project Space', (36, 20))]
F1_AMEN = [('entrance', -2.4, 19.5), ('info', 3, 12), ('shop', 3.5, 23), ('restroom', 3, 8), ('elevator', 18, 8.5),
           ('stairs', 8.5, 13), ('entrance', 47.2, 19.5)]
F1_LABELS = [('← Front door (from the terraced steps)', 8, 28.5),
             ('Back doors to the garden →', 36, 28.5), ('Approximate plan', 18, -2)]
F1_NOTES = []

# ---- Second Floor ---------------------------------------------------------------------------------------------------
F2 = [
    ('Balcony Gallery', 'gallery', 'Balcony Gallery and Stairway, above the Leir Atrium (the stairs arrive here)',
     rect(6, 9, 20, 15), 'Balcony'),
    ('South Gallery', 'gallery', 'South Gallery', rect(0, 15, 20, 25.2), 'South'),
    ('Bridge', 'corridor', 'The Bridge', rect(0, 9, 6, 15), None),
    ('Opatrny Gallery', 'gallery', 'Opatrny Gallery and its vestibule', rect(0, 0, 12, 9), 'Opatrny'),
    ('Sound Gallery', 'gallery', 'Sound Gallery', rect(12, 0, 20, 5), 'Sound'),
    ('Upper Hall', 'corridor', 'Upper hall by the elevator', rect(12, 5, 20, 9), None),
]
F2_CLOSED = [rect(20, 0, 35, 7.1), [(20, 15.2), (39.5, 15.2), (39.5, 17.6), (48, 17.6), (48, 25.2), (20, 25.2)]]
F2_DOORS = [('Balcony Gallery', 'South Gallery', (13, 15)), ('South Gallery', 'Bridge', (3, 15)),
            ('Bridge', 'Opatrny Gallery', (3, 9)), ('Opatrny Gallery', 'Sound Gallery', (12, 2.5)),
            ('Sound Gallery', 'Upper Hall', (16, 5)), ('Upper Hall', 'Balcony Gallery', (16, 9)),
            ('Bridge', 'Balcony Gallery', (6, 12))]
F2_AMEN = [('elevator', 18, 8.5), ('stairs', 8.5, 13)]
F2_LABELS = [('Walk the galleries clockwise from the top of the stairs (approximate plan)', 18, -2),
             ('Roof of the tall Leir Gallery and Project Space below', 34, 21.5), ('Roof of The Studio', 27.5, 3.5)]
F2_NOTES = []


def inside(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def floor(fid, label, order, area, rooms, closed, doors, amen, labels, notes, f, transform):
    rr = []
    for rid, kind, name, poly, short in rooms:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': [f(*q) for q in poly]}
        if kind == 'gallery': r['label'] = short
        rr.append(r)
    return {'id': fid, 'label': label, 'order': order, 'transform': transform, 'area': area, 'rooms': rr,
            'closed': [{'poly': [f(*q) for q in c]} for c in closed],
            'amenities': [{'type': t, 'at': f(x, y)} for t, x, y in amen],
            'labels': [{'text': t, 'kind': 'note', 'at': f(x, y)} for t, x, y in labels],
            'notes': [{'text': t, 'kind': 'note', 'at': f(x, y)} for t, x, y in notes],
            'doors': [{'a': a, 'b': b, 'at': f(*p), 'width': 16, 'axis': 'o'} for a, b, p in doors]}


def build_floors():
    # building units -> grounds units: G = (BX + (u/KB - 6) * PXM) * KG, the same for y
    s = PXM * KG / KB
    tr = [round(s, 5), round((BX - 6 * PXM) * KG, 2), round((BY - 4 * PXM) * KG, 2)]
    floors = [
        floor('G', 'Grounds & Sculpture Garden', 0, 'Front Lawn · terraced steps · parking · Sculpture Garden with the '
              'amphitheater and Secret Garden (open dawn to dusk)', GR, GR_CLOSED, GR_DOORS, GR_AMEN, GR_LABELS,
              GR_NOTES, G, [1, 0, 0]),
        floor('1', 'First Floor', 1, 'Leir Atrium (Front Desk) · The Shop · restrooms · The Studio · Klein Kenealy '
              'Gallery · Leir Gallery · Project Space · courtyard', F1, F1_CLOSED, F1_DOORS, F1_AMEN, F1_LABELS,
              F1_NOTES, B, tr),
        floor('2', 'Second Floor', 2, 'Balcony Gallery · South Gallery · Bridge · Opatrny Gallery · Sound Gallery',
              F2, F2_CLOSED, F2_DOORS, F2_AMEN, F2_LABELS, F2_NOTES, B, tr),
    ]
    for f in floors:
        ids = [r['id'] for r in f['rooms']]
        assert len(ids) == len(set(ids)), f['id']
        for d in f['doors']:
            assert d['a'] in ids and d['b'] in ids, (f['id'], d)
        for a in f['amenities']:
            assert any(inside(a['at'], r['poly']) for r in f['rooms']), (f['id'], a)
    return {'about': 'Built by tools/build_aldrich.py. The grounds are traced from The Aldrich’s own Sculpture Garden '
                     'map. The museum publishes no floor plan: the rooms inside are approximate, placed inside the '
                     'building’s real outline from the museum’s own descriptions (Front Desk on the left, restrooms '
                     'behind it, the galleries of each floor, the clockwise walk upstairs).',
            'source': 'The Aldrich’s Sculpture Garden map (2026); inside approximate, from the museum’s visit and '
                      'social-narrative pages and exhibition checklists',
            'units': f'grounds: pixels of the garden map x {KG} (about north up); building: metres x {KB}',
            'approximate': True, 'defaultFloor': '1', 'galleryWord': 'Gallery', 'floors': floors}


# ---- works ---------------------------------------------------------------------------------------------------------

def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower().replace('’', '')).strip('-')[:60]


def picture(key, url):
    if not url: return None
    dest = OUT / 'images' / f'{key}.jpg'
    if dest.exists(): return f'data/aldrich/images/{key}.jpg'
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
    return f'data/aldrich/images/{key}.jpg'


def page(slug_):
    return page_path(slug_).read_text(errors='replace')


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()


def main_text(slug_, start, n=1500):
    t = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', page(slug_), flags=re.S)
    s = clean(t)
    i = s.find(start)
    j = s.find('Overview', i)
    return s[i:j if j > i else i + n].strip()[:n]


def artists():
    """[(name, born)] from the Decennial page's Participating Artists list."""
    t = page('exhibitions/the-aldrich-decennial-new-art-made-in-connecticut')
    m = re.search(r'Participating Artists</h3>.*?<p>(.*?)</p>', t, re.S)
    out = []
    for line in re.split(r'<br\s*/?>', m.group(1)):
        line = clean(line)
        if not line: continue
        if '&' in line:
            mm = re.match(r'(.+?) \(b\. (\d{4})\) & (.+?) \(b\. (\d{4})\)', line)
            out.append((f'{mm.group(1)} & {mm.group(3)}', f'b. {mm.group(2)} and {mm.group(4)}'))
            continue
        mm = re.match(r'(.+?) \(b\. (\d{4})\)', line)
        out.append((mm.group(1), f'b. {mm.group(2)}'))
    return out


def audio():
    """{artist slug start: [(title, soundcloud url)]} from the Decennial page's Artist Audio list."""
    t = page('exhibitions/the-aldrich-decennial-new-art-made-in-connecticut')
    out = []
    for m in re.finditer(r'<a href="(https://soundcloud\.com/user-292598524/[^"]+)"[^>]*title="([^"]*)"', t):
        url, title = m.group(1), html.unescape(m.group(2))
        if url in [u for _, _, u in out]: continue
        who, _, work = title.partition(' - ')
        out.append((who.strip().replace("'", '’'), work.strip(), url))
    return out


# The works outside, numbered as on the museum's Sculpture Garden map: (n, room, (x, y) on the garden map)
GARDEN_AT = {1: 'Front Lawn', 2: 'Front Terrace', 3: 'Courtyard', 4: 'Amphitheater', 5: 'South Lawn', 6: 'East Lawn',
             7: 'Upper Garden', 8: 'Upper Garden', 9: 'Upper Garden', 10: 'Upper Garden'}
GARDEN_WHERE = {1: 'On the front lawn by Main Street, the first work you see', 2: 'On the museum’s front (west) wall, '
                'draped around a window, above the terraced steps', 3: 'In the open-air courtyard inside the museum',
                4: 'In the amphitheater behind the museum', 5: 'On the lawn south of the amphitheater',
                6: 'At the east end of the garden path', 7: 'In the middle of the Upper Garden',
                8: 'In the Upper Garden, near the path from the parking lot', 9: 'In the Upper Garden',
                10: 'At the north-east corner of the Upper Garden'}
# Works with the museum's own picture: id -> (picture file on thealdrich.org, credit)
PICTURES = {
    'kristy-hughes-portal-hope-as-practice': ('Kristy_Hughes_Portal-Hope_as_Practice_1.jpg', 'Courtesy of the artist'),
    'em-rooney-love-streams': ('260608_THEALDRICH_DECENNIAL_002.jpg', 'Installation view. Photo: Olympia Shannon'),
    'chris-domenick-lamp-float-1': ('260608_THEALDRICH_DECENNIAL_013.jpg', 'Installation view, left. Photo: Olympia '
                                    'Shannon'),
    'chris-domenick-lamp-scribble-1': ('260608_THEALDRICH_DECENNIAL_013.jpg', 'Installation view, right. Photo: '
                                       'Olympia Shannon'),
}
# Titles named by the museum's installation photos or by press about the show (with the source)
EXTRA_WORKS = [
    ('Chris Domenick', 'Lamp (float #1)', '2024', 'Hung from the ceiling, lit from inside', 'the museum’s installation '
     'photo'),
    ('Chris Domenick', 'Lamp (scribble #1)', '2026', 'Hung from the ceiling, lit from inside', 'the museum’s '
     'installation photo'),
    ('Felandus Thames', 'She did what she could', '', 'A wall work of thousands of colored hair beads', 'Midbrow’s '
     'review of the show, which places it in the first gallery on the ground floor'),
    ('Felandus Thames', 'Jubilee', '', 'A wall work of colored hair beads', 'Midbrow’s review of the show, which '
     'places it in the first gallery on the ground floor'),
    ('Faustin Adeniran', 'Arewa (Elegance)', '', 'A mosaic of colorful aluminum cans', 'Midbrow’s review of the show'),
    ('Anoka Faruqee & David Driscoll', '2026-P-02', '2026', 'Acrylic on linen, from a series of paintings',
     'Midbrow’s review of the show'),
]
# Audio-guide tracks that are not a work's title
NOT_TITLES = {'Introduction', 'Sound of Drawing', 'Ungrateful Son'}
INSIDE_NOTE = ('In the galleries: the Decennial fills every room of the museum, and the museum doesn’t say which room '
               'each artist is in. Ask at the Front Desk, or follow the Bloomberg Connects app’s guide.')


def garden_works():
    """The ten works on the museum's Sculpture Garden map, in its order."""
    t = clean(re.sub(r'<(script|style)[^>]*>.*?</\1>', '', page('page/sculpture-garden'), flags=re.S))
    i = t.find('Works of art currently on view in the Sculpture Garden El mapa')
    j = t.find('Plant Maps', i)
    body = t[i:j]
    out = []
    for m in re.finditer(r'(\d+)\) (.+?)(?= \d{1,2}\) [A-Z][^,()]+, |$)', body):
        n, txt = int(m.group(1)), m.group(2).strip()
        artist, rest = txt.split(', ', 1)
        mm = re.match(r'(.+?) , (\d{4}(?:–\d{2,4})?) (.*?) (Courtesy .*)$', rest)
        out.append({'n': n, 'artist': artist, 'title': mm.group(1).strip(), 'date': mm.group(2),
                    'medium': mm.group(3).strip(), 'credit': mm.group(4).strip()})
    assert len(out) == 10, out
    return out


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    born = dict(artists())
    works, seen = [], set()

    def add(a, room=None, location=None, note=None, guessed=False):
        if room:
            fl, gname = rooms[room]
            a.update({'gallery': room, 'galleryName': gname, 'floor': fl, 'placeNote': note})
            if guessed: a['placeGuessed'] = True
        else:
            a['location'] = location
        a.setdefault('exhibition', f'{SHOW} ({SHOW_DATES})')
        a['artistDetails'] = a.get('artistDetails') or (f'{born[a["artist"]]} · lives and works in Connecticut'
                                                         if a['artist'] in born else None)
        pic = PICTURES.get(a['id'])
        if pic:
            a['image'] = picture(a['id'], IMG + pic[0])
            if a['image']: a['imageCredit'] = f'The Aldrich Contemporary Art Museum (thealdrich.org). {pic[1]}'
        works.append({k: v for k, v in a.items() if v not in (None, '', [])})
        seen.add(a['id'])

    # the show itself
    text = main_text('exhibitions/the-aldrich-decennial-new-art-made-in-connecticut',
                     'The Aldrich Decennial: I am what is around me , the debut')
    a = {'id': 'aldrich-show-decennial', 'title': SHOW, 'artist': 'Exhibition', 'date': SHOW_DATES,
         'description': text.replace(' , ', ', ').replace('me , ', 'me, '), 'url': DECENNIAL, 'temporary': True,
         'image': picture('aldrich-show-decennial', IMG + '260608_THEALDRICH_DECENNIAL_003.jpg'),
         'imageCredit': 'The Aldrich Contemporary Art Museum (thealdrich.org). Installation view. Photo: Olympia Shannon'}
    add(a, location='Every gallery of the museum, the courtyard and the Sculpture Garden')

    # the Sculpture Garden map, exact places
    hughes = main_text('exhibitions/kristy-hughes', 'Kristy Hughes\' vibrant')
    for g in garden_works():
        aid = slug(f"{g['artist']} {re.sub(r' [(].*', '', g['title'])}")
        desc = f"{g['title']}, {g['date']}. {g['medium']}. {g['credit']}."
        if g['n'] == 1: desc = hughes.replace(' , ', ', ')
        a = {'id': aid, 'title': g['title'], 'artist': g['artist'], 'date': g['date'], 'medium': g['medium'],
             'description': desc, 'url': GARDEN if g['n'] != 1 else f'{SITE}/exhibitions/kristy-hughes',
             'number': g['n']}
        if g['n'] == 1: a['exhibition'] = 'Main Street Sculpture (November 20, 2025 – May 30, 2027)'
        add(a, GARDEN_AT[g['n']], note=f"Number {g['n']} on the museum’s Sculpture Garden map. {GARDEN_WHERE[g['n']]}.")

    garden_artists = {w['artist'] for w in works}
    # works named on the museum's audio guide, the installation photos and press
    named = {}
    for who, work, url in audio():
        if not work or work in NOT_TITLES or re.match(r'^\d|David \d', work): continue
        who = {'Lula Mae': 'Lula Mae Blocton', 'Scott Carrillo Azevedo': 'Scott Carrillo Azevedo'}.get(who, who)
        if who in garden_artists and work.startswith('A Sickness'): continue      # outside, number 7
        named.setdefault(who, []).append((work, '', None, url, 'the museum’s artist audio guide'))
    for who, work, date, what, src in EXTRA_WORKS:
        named.setdefault(who, []).append((work, date, what, None, src))
    for name, _ in artists():
        for work, date, what, track, src in named.get(name, []):
            aid = slug(f'{name} {work}')
            if aid in seen: continue
            desc = (f'{what}. ' if what else '') + f'Shown in {SHOW}; the title comes from {src}.'
            if track: desc += ' The artist talks about it on the museum’s audio guide (link below).'
            a = {'id': aid, 'title': work, 'artist': name, 'date': date, 'description': desc,
                 'url': track or DECENNIAL}
            add(a, location=INSIDE_NOTE if 'first gallery' not in src else
                'First Floor: the first gallery you walk into (from a review of the show; the museum doesn’t list rooms)')
    # artists with no named work: one card each, so every artist in the show can be found
    have = {w['artist'] for w in works}
    for name, _ in artists():
        if name in have: continue
        track = next((u for w, _, u in audio() if w.replace('Anoka and David', 'Anoka Faruqee & David Driscoll') == name), None)
        a = {'id': slug(f'{name} decennial'), 'title': f'Works by {name}', 'artist': name, 'date': 'Made 2016–2026',
             'description': f'{name} is one of the 40 Connecticut artists in {SHOW}; the museum doesn’t list the '
                            'works by title online.' + (' The artist talks about the work on the museum’s audio guide '
                                                        '(link below).' if track else ''),
             'url': track or DECENNIAL}
        add(a, location=INSIDE_NOTE)
    # Tim Youd's retyped novel, shown during the Decennial
    a = {'id': 'tim-youd-connecticut-retyped', 'title': 'Connecticut Retyped (Richard Yates’s Revolutionary Road)',
         'artist': 'Tim Youd', 'artistDetails': 'b. 1967, Worcester, MA · lives and works in Los Angeles',
         'date': '2026', 'description': main_text('exhibitions/tim-youd-connecticut-retyped',
                                                  'Beginning on opening day').replace(' , ', ', '),
         'url': f'{SITE}/exhibitions/tim-youd-connecticut-retyped', 'exhibition': 'Tim Youd: Connecticut Retyped '
         '(June 6, 2026 – January 10, 2027)'}
    add(a, location='In the galleries: the framed diptych made from the June performance (the museum doesn’t say '
                    'which room)')
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    works.sort(key=lambda a: (a['artist'] != 'Exhibition', 'gallery' not in a,
                              forder.get(a.get('floor'), 9), order.get(a.get('gallery'), 0), a.get('number', 0),
                              a['artist'].split(' & ')[0].split()[-1], a['title']))
    for a in works: a.pop('number', None)
    return {'source': SOURCE, 'checked': time.strftime('%Y-%m-%d'), 'count': len(works), 'complete': False,
            'artworks': works}


def build_guide(works):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'],
                     'date': a.get('date'), 'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'),
                     'onView': True, 'gallery': a.get('gallery'), 'floor': a.get('floor')}.items()
                     if v not in (None, '')})
    return {'museum': MUSEUM, 'name': NAME, 'checked': time.strftime('%Y-%m-%d'), 'source': SOURCE, 'onViewKnown': True,
            'note': 'The Aldrich has no permanent collection: it shows contemporary art in changing exhibitions. Listed '
                    'here is what is on view now, The Aldrich Decennial (40 Connecticut artists, to January 10, 2027): '
                    'the ten works in the Sculpture Garden where the museum’s map puts them, and the works inside by '
                    'artist (the museum doesn’t say which room each is in).',
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
    for a in works['artworks']: by[a.get('gallery', '(room not listed)')] = by.get(a.get('gallery', '(room not listed)'), 0) + 1
    print(f'{works["count"]} works ({sum("image" in a for a in works["artworks"])} with pictures)')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
